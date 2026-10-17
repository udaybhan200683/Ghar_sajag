#include "firmware/hub/target/esp32s3/cloud_trust_provider.hpp"
#include "firmware/hub/target/esp32s3/https_backend_channel.hpp"
#include "gs/gs68_diag_protocol.hpp"

#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "mbedtls/base64.h"
#include "nvs_flash.h"

#include <array>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#if !defined(GS68_TEST_ONLY_BUILD) || GS68_TEST_ONLY_BUILD != 1
#error "GS-68 diagnostic must never be built as a production image"
#endif
#if defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE)
#error "Host fake-verifier compatibility APIs are forbidden in target firmware"
#endif
#if !CONFIG_ESP_TLS_USE_DS_PERIPHERAL || !CONFIG_MBEDTLS_SSL_PROTO_TLS1_2 || CONFIG_MBEDTLS_SSL_PROTO_TLS1_3
#error "GS-68 diagnostic requires the isolated TLS 1.2 + ESP DS configuration"
#endif

namespace {
constexpr char kTag[] = "gs68_diag";
constexpr std::size_t kCommandLimit = gs::diagnostic::kTargetCommandMaxBytes;
constexpr std::size_t kTimeProofBytes = 456;

class TargetMonotonicClock final : public gs::hub::target::S3HubMonotonicClock {
public:
    gs::hub::Milliseconds now_ms() const override {
        return static_cast<gs::hub::Milliseconds>(esp_timer_get_time() / 1000);
    }
};

TargetMonotonicClock g_monotonic_clock;
gs::hub::target::NvsAuthenticatedTimeFloorStore g_time_floor_store("gs68time");
gs::hub::target::S3AuthenticatedTimeRandomSource g_time_random;
std::unique_ptr<gs::hub::target::Rsa3072Sha256TimeProofVerifier> g_time_verifier;
std::unique_ptr<gs::hub::target::AuthenticatedHubTimeProvider> g_time_provider;
gs::hub::target::AuthenticatedTimeChallenge g_time_challenge{};
bool g_time_store_ready = false;
bool g_time_provider_started = false;

std::string hex(const std::uint8_t* bytes, std::size_t size) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string output(size * 2, '0');
    for (std::size_t i = 0; i < size; ++i) {
        output[2 * i] = digits[bytes[i] >> 4];
        output[2 * i + 1] = digits[bytes[i] & 0xf];
    }
    return output;
}

bool decode_hex_nonce(const char* encoded, std::array<std::uint8_t, 32>& nonce) {
    if (!gs::diagnostic::target_nonce_valid(encoded)) return false;
    for (std::size_t i = 0; i < nonce.size(); ++i) {
        auto nibble = [](char ch) -> std::uint8_t {
            return static_cast<std::uint8_t>(ch <= '9' ? ch - '0' : ch - 'a' + 10);
        };
        nonce[i] = static_cast<std::uint8_t>((nibble(encoded[2 * i]) << 4) |
                                             nibble(encoded[2 * i + 1]));
    }
    return true;
}

bool decode_base64(const char* encoded, std::size_t output_limit,
                   std::vector<std::uint8_t>& decoded) {
    decoded.clear();
    if (encoded == nullptr) return false;
    const auto encoded_size = std::strlen(encoded);
    if (encoded_size == 0 || encoded_size > 768) return false;
    decoded.resize(output_limit);
    std::size_t decoded_size = 0;
    const auto result = mbedtls_base64_decode(
        decoded.data(), decoded.size(), &decoded_size,
        reinterpret_cast<const unsigned char*>(encoded), encoded_size);
    if (result != 0 || decoded_size == 0 || decoded_size > output_limit) {
        decoded.clear();
        return false;
    }
    decoded.resize(decoded_size);
    return true;
}

bool ensure_test_time_store() {
    if (g_time_store_ready) return true;
    const auto result = nvs_flash_init();
    // Never erase, repair, or reinitialize NVS in the diagnostic. A damaged or
    // incompatible store is a failed test prerequisite, not permission to reset it.
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) return false;
    g_time_store_ready = true;
    return true;
}

bool ensure_time_provider_started() {
    if (!g_time_provider || !ensure_test_time_store()) return false;
    if (g_time_provider_started) return true;
    if (!g_time_provider->start()) return false;
    g_time_provider_started = true;
    return true;
}

void emit_ready() {
    const auto* app = esp_app_get_description();
    esp_chip_info_t chip{};
    esp_chip_info(&chip);
    std::array<std::uint8_t, 6> mac{};
    ESP_ERROR_CHECK(esp_read_mac(mac.data(), ESP_MAC_WIFI_STA));
    std::uint32_t flash_bytes = 0;
    const auto flash_status = esp_flash_get_physical_size(nullptr, &flash_bytes);
    const auto psram_bytes = esp_psram_get_size();
    const auto* partition = esp_ota_get_running_partition();
    std::array<std::uint8_t, 32> digest{};
    const auto hash_status = partition != nullptr
        ? esp_partition_get_sha256(partition, digest.data()) : ESP_FAIL;
    const auto image_hash = hash_status == ESP_OK ? hex(digest.data(), digest.size()) : "";
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"ready\","
                "\"source_commit\":\"%s\",\"profile_sha256\":\"%s\","
                "\"project_version\":\"%s\",\"idf_version\":\"%s\","
                "\"chip_model\":\"ESP32-S3\",\"chip_revision\":%u,\"mac_address\":\"%02x:%02x:%02x:%02x:%02x:%02x\","
                "\"flash_bytes\":%u,\"flash_status\":%d,\"psram_bytes\":%u,"
                "\"running_image_sha256\":\"%s\",\"ds_profile\":\"ESP_TLS_DS_RSA\","
                "\"tls_profile\":\"TLS1.2\",\"ds_identity\":\"NOT_PROVISIONED\","
                "\"trusted_time_authority\":\"TEST_ONLY_RUNTIME_KEY_REQUIRED\","
                "\"free_heap\":%u,\"largest_free_block\":%u,"
                "\"reset_reason\":%u,\"physical\":\"NOT_RUN\"}\n",
                GS68_SOURCE_COMMIT, GS68_PROFILE_SHA256,
                app != nullptr ? app->version : "unknown",
                app != nullptr ? app->idf_ver : "unknown",
                static_cast<unsigned>(chip.revision), mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
                static_cast<unsigned>(flash_bytes), static_cast<int>(flash_status),
                static_cast<unsigned>(psram_bytes), image_hash.c_str(),
                static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_8BIT)),
                static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_8BIT)),
                static_cast<unsigned>(esp_reset_reason()));
    std::fflush(stdout);
}

void emit_command_failure(const gs::diagnostic::TargetCommand& command,
                          const char* reason) {
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"case_result\","
                "\"case_id\":\"%s\",\"challenge_nonce\":\"%s\","
                "\"case_outcome\":\"FAIL\",\"reason\":\"%s\","
                "\"physical\":\"NOT_RUN\"}\n",
                command.case_id, command.challenge_nonce, reason);
    std::fflush(stdout);
}

void handle_missing_identity_case(const gs::diagnostic::TargetCommand& command) {
    // Reuse the existing provider contract. This diagnostic intentionally has
    // no Hub/Home/epoch, credential registry row, DS context, or trusted time.
    gs::hub::target::UnprovisionedS3CloudTrust identity;
    gs::hub::target::HttpsBackendChannel channel(
        "https://cloudsync.gs68.test", "", identity);
    const auto response = channel.post("/v1/homes/gs68-test/events", "{\"test_only\":true}");
    const auto disposition = gs::diagnostic::classify_missing_identity_response(
        response.status, response.server_authenticated, response.message_complete,
        response.body.size(), response.network_attempted);
    const bool blocked = disposition ==
        gs::diagnostic::DiagnosticPreflightDisposition::Blocked;
    const char* outcome = blocked ? "BLOCKED" : "FAIL";
    const char* reason = blocked ? "DS_HOME_EPOCH_CREDENTIAL_AND_TIME_NOT_PROVISIONED"
                                 : "UNEXPECTED_RESPONSE_OR_NETWORK_ATTEMPT";
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"case_result\","
                "\"case_id\":\"%s\",\"challenge_nonce\":\"%s\","
                "\"case_outcome\":\"%s\",\"reason\":\"%s\","
                "\"signing\":\"BLOCKED_NO_DS_CONTEXT\",\"backend_authenticated\":%s,"
                "\"network_attempted\":%s,\"private_key_exported\":false,"
                "\"tls_profile\":\"TLS1.2\",\"physical\":\"NOT_RUN\"}\n",
                command.case_id, command.challenge_nonce, outcome, reason,
                response.server_authenticated ? "true" : "false",
                response.network_attempted ? "true" : "false");
    std::fflush(stdout);
    ESP_LOGI(kTag, "identity preflight outcome=%s status=%u network_attempted=%s",
             outcome, response.status, response.network_attempted ? "true" : "false");
}

void handle_time_key(const gs::diagnostic::TargetCommand& command) {
    if (g_time_provider_started) {
        emit_command_failure(command, "TIME_KEY_IMMUTABLE_AFTER_START");
        return;
    }
    std::vector<std::uint8_t> public_key_der;
    if (!decode_base64(command.payload_base64, 1024, public_key_der)) {
        emit_command_failure(command, "INVALID_TEST_ONLY_PUBLIC_KEY_ENCODING");
        return;
    }
    // Runtime-only TEST_ONLY authority input. The diagnostic stores no private
    // key and has no compiled authority key or production trust anchor.
    g_time_verifier = std::make_unique<gs::hub::target::Rsa3072Sha256TimeProofVerifier>(
        std::move(public_key_der));
    const gs::hub::target::AuthenticatedTimeBootstrapPolicy test_policy{
        30000, 60000, 300};
    g_time_provider = std::make_unique<gs::hub::target::AuthenticatedHubTimeProvider>(
        g_time_floor_store, *g_time_verifier, g_time_random, g_monotonic_clock,
        test_policy);
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"time_key_result\","
                "\"case_id\":\"%s\",\"result\":\"TEST_ONLY_PUBLIC_KEY_LOADED\","
                "\"private_key_loaded\":false,\"production_anchor\":false,"
                "\"physical\":\"NOT_RUN\"}\n", command.case_id);
    std::fflush(stdout);
}

void handle_time_challenge(const gs::diagnostic::TargetCommand& command) {
    if (!ensure_time_provider_started()) {
        emit_command_failure(command, "TEST_TIME_STORE_OR_PROVIDER_UNAVAILABLE");
        return;
    }
    if (!g_time_provider->create_challenge(g_time_challenge)) {
        emit_command_failure(command, "PSA_RANDOM_OR_CHALLENGE_CREATION_FAILED");
        return;
    }
    const auto nonce = hex(g_time_challenge.nonce.data(), g_time_challenge.nonce.size());
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"time_challenge\","
                "\"case_id\":\"%s\",\"challenge_nonce\":\"%s\","
                "\"boot_generation\":%llu,\"created_monotonic_ms\":%lld,"
                "\"random_source\":\"ESP32_S3_PSA\",\"physical\":\"NOT_RUN\"}\n",
                command.case_id, nonce.c_str(),
                static_cast<unsigned long long>(g_time_challenge.boot_generation),
                static_cast<long long>(g_time_challenge.created_monotonic_ms));
    std::fflush(stdout);
}

void handle_time_proof(const gs::diagnostic::TargetCommand& command) {
    std::array<std::uint8_t, 32> supplied_nonce{};
    if (!g_time_provider_started || !decode_hex_nonce(command.challenge_nonce, supplied_nonce) ||
        supplied_nonce != g_time_challenge.nonce) {
        emit_command_failure(command, "NO_MATCHING_CURRENT_CHALLENGE");
        return;
    }
    std::vector<std::uint8_t> proof;
    if (!decode_base64(command.payload_base64, kTimeProofBytes, proof) ||
        proof.size() != kTimeProofBytes) {
        emit_command_failure(command, "INVALID_SIGNED_TIME_PROOF_ENCODING");
        g_time_challenge = {};
        return;
    }
    const bool accepted = g_time_provider->accept_authenticated_time(proof);
    g_time_challenge = {};
    gs::hub::TrustedHubTimeSnapshot snapshot{};
    const bool trusted = accepted && g_time_provider->trusted_hub_time(
        g_monotonic_clock.now_ms(), snapshot);
    if (!trusted) {
        emit_command_failure(command, "SIGNED_TIME_PROOF_REJECTED_OR_ROLLBACK_DETECTED");
        return;
    }
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"time_proof_result\","
                "\"case_id\":\"%s\",\"result\":\"PASS\",\"signature\":\"RSA3072_SHA256_VERIFIED\","
                "\"time_authority\":\"TEST_ONLY\",\"boot_generation\":%llu,"
                "\"trusted_utc_seconds\":%lld,\"private_key_exported\":false,"
                "\"physical\":\"NOT_RUN\"}\n",
                command.case_id,
                static_cast<unsigned long long>(snapshot.boot_generation),
                static_cast<long long>(snapshot.utc_now));
    std::fflush(stdout);
}

void handle_command(const char* command_text) {
    gs::diagnostic::TargetCommand command{};
    const auto parse_result = gs::diagnostic::parse_target_command(
        command_text, std::strlen(command_text), command);
    if (parse_result != gs::diagnostic::TargetCommandError::Ok) {
        gs::diagnostic::TargetCommand invalid{};
        std::strcpy(invalid.case_id, "GS68-PHY-001");
        std::strcpy(invalid.challenge_nonce, "0000000000000000000000000000000000000000000000000000000000000000");
        emit_command_failure(invalid, "INVALID_OR_OVERSIZED_COMMAND");
        return;
    }
    if (std::strcmp(command.operation, "RUN_CASE") == 0) {
        handle_missing_identity_case(command);
    } else if (std::strcmp(command.operation, "LOAD_TIME_KEY") == 0) {
        handle_time_key(command);
    } else if (std::strcmp(command.operation, "TIME_CHALLENGE") == 0) {
        handle_time_challenge(command);
    } else if (std::strcmp(command.operation, "TIME_PROOF") == 0) {
        handle_time_proof(command);
    } else {
        std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"command_result\","
                    "\"case_id\":\"%s\",\"operation\":\"%s\","
                    "\"result\":\"OBSERVED_NO_ACTION\",\"physical\":\"NOT_RUN\"}\n",
                    command.case_id, command.operation);
        std::fflush(stdout);
    }
}
}  // namespace

extern "C" void app_main() {
    ESP_LOGI(kTag, "TEST_ONLY GS-68 CloudSync identity/time diagnostic; no provisioning or network startup");
    emit_ready();
    char command[kCommandLimit + 2]{};
    while (std::fgets(command, sizeof(command), stdin) != nullptr) {
        const auto length = std::strlen(command);
        if (length == 0 || command[length - 1] != '\n' || length - 1 > kCommandLimit) {
            std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"capture_error\","
                        "\"reason\":\"truncated_command\",\"physical\":\"NOT_RUN\"}\n");
            std::fflush(stdout);
            std::memset(command, 0, sizeof(command));
            continue;
        }
        command[length - 1] = '\0';
        handle_command(command);
        std::memset(command, 0, sizeof(command));
    }
}
