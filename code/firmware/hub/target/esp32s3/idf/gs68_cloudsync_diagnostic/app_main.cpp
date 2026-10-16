#include "firmware/hub/target/esp32s3/https_backend_channel.hpp"

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

#include <array>
#include <cstdio>
#include <cstring>
#include <string>

#if !defined(GS68_TEST_ONLY_BUILD) || GS68_TEST_ONLY_BUILD != 1
#error "GS-68 diagnostic must never be built as a production image"
#endif
#if !CONFIG_ESP_TLS_USE_DS_PERIPHERAL || !CONFIG_MBEDTLS_SSL_PROTO_TLS1_2 || CONFIG_MBEDTLS_SSL_PROTO_TLS1_3
#error "GS-68 diagnostic requires the isolated TLS 1.2 + ESP DS configuration"
#endif

namespace {
constexpr char kTag[] = "gs68_diag";
constexpr std::size_t kCommandLimit = 1024;

class UnprovisionedTestIdentity final : public gs::hub::target::CloudTlsIdentityProvider {
public:
    bool current_identity(gs::hub::target::CloudTlsIdentity& identity) override {
        identity = {};
        return false;
    }
};

std::string hex(const std::uint8_t* bytes, std::size_t size) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string output(size * 2, '0');
    for (std::size_t i = 0; i < size; ++i) {
        output[2 * i] = digits[bytes[i] >> 4];
        output[2 * i + 1] = digits[bytes[i] & 0xf];
    }
    return output;
}

std::string running_image_sha256() {
    const auto* partition = esp_ota_get_running_partition();
    if (partition == nullptr) return {};
    std::array<std::uint8_t, 32> digest{};
    if (esp_partition_get_sha256(partition, digest.data()) != ESP_OK) return {};
    return hex(digest.data(), digest.size());
}

void emit_ready() {
    const auto* app = esp_app_get_description();
    esp_chip_info_t chip{};
    esp_chip_info(&chip);
    const auto image_hash = running_image_sha256();
    std::array<std::uint8_t, 6> mac{};
    ESP_ERROR_CHECK(esp_read_mac(mac.data(), ESP_MAC_WIFI_STA));
    std::uint32_t flash_bytes = 0;
    const auto flash_status = esp_flash_get_physical_size(nullptr, &flash_bytes);
    const auto psram_bytes = esp_psram_get_size();
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"ready\","
                "\"source_commit\":\"%s\",\"profile_sha256\":\"%s\","
                "\"project_version\":\"%s\",\"idf_version\":\"%s\","
                "\"chip_model\":\"ESP32-S3\",\"chip_revision\":%u,\"mac_address\":\"%02x:%02x:%02x:%02x:%02x:%02x\","
                "\"flash_bytes\":%u,\"flash_status\":%d,\"psram_bytes\":%u,"
                "\"running_image_sha256\":\"%s\",\"ds_profile\":\"ESP_TLS_DS_RSA\","
                "\"tls_profile\":\"TLS1.2\",\"ds_identity\":\"NOT_PROVISIONED\","
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

bool valid_nonce(const std::string& nonce) {
    if (nonce.size() != 64) return false;
    for (const char ch : nonce) {
        if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return false;
    }
    return true;
}

const char* skip_space(const char* cursor, const char* end) {
    while (cursor < end && (*cursor == ' ' || *cursor == '\t' ||
           *cursor == '\r' || *cursor == '\n')) ++cursor;
    return cursor;
}

bool parse_ascii_string(const char*& cursor, const char* end, std::string& value) {
    if (cursor >= end || *cursor != '"') return false;
    ++cursor;
    value.clear();
    while (cursor < end && *cursor != '"') {
        const auto ch = static_cast<unsigned char>(*cursor++);
        // Commands use a deliberately narrow JSON subset: printable unescaped
        // ASCII only. This rejects control characters, escapes, and ambiguity.
        if (ch < 0x21 || ch > 0x7e || ch == '\\' || value.size() >= 128) return false;
        value.push_back(static_cast<char>(ch));
    }
    if (cursor >= end || *cursor != '"') return false;
    ++cursor;
    return true;
}

bool parse_command(const char* command, std::string& nonce, std::string& case_id,
                   std::string& operation) {
    const char* cursor = command;
    const char* end = command + std::strlen(command);
    cursor = skip_space(cursor, end);
    if (cursor >= end || *cursor++ != '{') return false;
    bool schema_seen = false, nonce_seen = false, case_seen = false, operation_seen = false;
    for (unsigned fields = 0; fields < 4; ++fields) {
        cursor = skip_space(cursor, end);
        std::string key, value;
        if (!parse_ascii_string(cursor, end, key)) return false;
        cursor = skip_space(cursor, end);
        if (cursor >= end || *cursor++ != ':') return false;
        cursor = skip_space(cursor, end);
        if (!parse_ascii_string(cursor, end, value)) return false;
        if (key == "schema" && !schema_seen) {
            schema_seen = true;
            if (value != "gs68.target.command.v1") return false;
        } else if (key == "challenge_nonce" && !nonce_seen) {
            nonce_seen = true;
            nonce = value;
        } else if (key == "case_id" && !case_seen) {
            case_seen = true;
            case_id = value;
        } else if (key == "operation" && !operation_seen) {
            operation_seen = true;
            operation = value;
        } else {
            return false;
        }
        cursor = skip_space(cursor, end);
        const char expected_separator = fields == 3 ? '}' : ',';
        if (cursor >= end || *cursor++ != expected_separator) return false;
    }
    cursor = skip_space(cursor, end);
    return cursor == end && schema_seen && nonce_seen && case_seen && operation_seen;
}

bool valid_case_id(const std::string& case_id) {
    return case_id.size() == 12 && case_id.compare(0, 9, "GS68-PHY-") == 0 &&
        ((case_id[9] == '0' && case_id[10] == '0' &&
          case_id[11] >= '1' && case_id[11] <= '9') ||
         (case_id[9] == '0' && case_id[10] == '1' && case_id[11] == '0'));
}

void handle_command(const char* command) {
    std::string nonce;
    std::string case_id;
    std::string operation;
    if (std::strlen(command) >= kCommandLimit ||
        !parse_command(command, nonce, case_id, operation) || !valid_nonce(nonce) ||
        !valid_case_id(case_id) || operation != "RUN_CASE") {
        std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"command_result\","
                    "\"case_id\":\"GS68-PHY-000\",\"case_outcome\":\"BLOCKED\","
                    "\"reason\":\"invalid_or_oversized_command\",\"physical\":\"NOT_RUN\"}\n");
        std::fflush(stdout);
        return;
    }
    // The test image intentionally has no DS credential loader. A later, separately
    // approved D12 provisioning design must supply an opaque ESP-DS context through
    // the restricted CloudTlsIdentityProvider before a network operation can occur.
    UnprovisionedTestIdentity identity;
    gs::hub::target::HttpsBackendChannel channel(
        "https://cloudsync.gs68.test", "", identity);
    const auto response = channel.post("/v1/homes/gs68-test/events", "{\"test_only\":true}");
    const bool blocked = response.status == 0 && !response.server_authenticated;
    std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"case_result\","
                "\"case_id\":\"%s\",\"challenge_nonce\":\"%s\","
                "\"case_outcome\":\"BLOCKED\",\"reason\":\"DS_TEST_IDENTITY_NOT_PROVISIONED\","
                "\"signing\":\"BLOCKED_NO_DS_CONTEXT\",\"backend_authenticated\":false,"
                "\"network_attempted\":false,\"private_key_exported\":false,\"tls_profile\":\"TLS1.2\","
                "\"physical\":\"NOT_RUN\"}\n", case_id.c_str(), nonce.c_str());
    std::fflush(stdout);
    ESP_LOGI(kTag, "diagnostic command blocked; test identity is not provisioned (channel_blocked=%s)",
             blocked ? "true" : "false");
}
}

extern "C" void app_main() {
    ESP_LOGI(kTag, "test-only GS-68 CloudSync DS/TLS diagnostic; no provisioning or network startup");
    emit_ready();
    char command[kCommandLimit + 1]{};
    while (std::fgets(command, sizeof(command), stdin) != nullptr) {
        const auto length = std::strlen(command);
        if (length == 0 || command[length - 1] != '\n') {
            std::printf("GS68/1 {\"schema\":\"gs68.target.event.v1\",\"event\":\"capture_error\","
                        "\"reason\":\"truncated_command\",\"physical\":\"NOT_RUN\"}\n");
            std::fflush(stdout);
            continue;
        }
        handle_command(command);
        std::memset(command, 0, sizeof(command));
    }
}
