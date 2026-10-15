#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"
#if GS_HIL_C8_ACK_DROP
#include "firmware/hub/target/esp32/hil_c8_ack_drop_gate.hpp"
#endif
#if GS_HIL_C8_ACK_HOLD
#include "firmware/hub/target/esp32/hil_c8_ack_hold_gate.hpp"
#endif
#if GS_HIL_SIGNED_FOTA
#include "fota_sender.hpp"
#endif

#include "esp_err.h"
#include "esp_log.h"
#include "freertos/task.h"
#include "mbedtls/platform_util.h"

#include <array>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>

namespace {
constexpr char kTag[] = "gs_fixture_commissioning";
constexpr std::size_t kCommandCapacity = 512;

char* next_token(char*& cursor) {
    while (*cursor == ' ' || *cursor == '\t') ++cursor;
    if (*cursor == '\0') return nullptr;
    char* token = cursor;
    while (*cursor != '\0' && *cursor != ' ' && *cursor != '\t') ++cursor;
    if (*cursor != '\0') *cursor++ = '\0';
    return token;
}

bool decode_hex(const char* encoded, std::uint8_t* output, std::size_t size) {
    if (encoded == nullptr || std::strlen(encoded) != size * 2U) return false;
    const auto nibble = [](char ch) -> int {
        if (ch >= '0' && ch <= '9') return ch - '0';
        if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
        if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
        return -1;
    };
    for (std::size_t index = 0; index < size; ++index) {
        const int high = nibble(encoded[2U * index]);
        const int low = nibble(encoded[2U * index + 1U]);
        if (high < 0 || low < 0) return false;
        output[index] = static_cast<std::uint8_t>((high << 4) | low);
    }
    return true;
}

#if GS_HIL_COMMISSIONING
const char* status_name(gs::hub::target::FixtureCommissioningStatus status) {
    using S = gs::hub::target::FixtureCommissioningStatus;
    switch (status) {
        case S::Idle: return "idle";
        case S::Queued: return "queued";
        case S::OfferActive: return "offer_active";
        case S::Rejected: return "rejected";
        case S::TimedOut: return "timed_out";
        case S::AuthenticatedRejoin: return "authenticated_rejoin";
    }
    return "unknown";
}
#endif

void dispatch(char* command) {
    char* cursor = command;
    char* verb = next_token(cursor);
    if (verb == nullptr) return;
#if GS_HIL_COMMISSIONING
    if (std::strcmp(verb, "FIXTURE_STATUS") == 0) {
        if (next_token(cursor) != nullptr) {
            ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=invalid_arguments");
            return;
        }
        ESP_LOGI(kTag, "HIL_FIXTURE_STATUS state=%s commissioning_window_ms=120000",
                 status_name(gs::hub::target::fixture_commissioning_status()));
        return;
    }
#endif
#if GS_HIL_C8_ACK_DROP
    if (std::strcmp(verb, "DROP_NEXT_DURABLE_ACK") == 0) {
        if (next_token(cursor) != nullptr) {
            ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=invalid_arguments");
            return;
        }
        const bool armed = gs::hub::target::arm_c8_ack_drop_fixture();
        ESP_LOGI(kTag, "HIL_C8_ACK_DROP_%s window_ms=%llu",
                 armed ? "ARMED" : "ARM_REJECTED",
                 static_cast<unsigned long long>(
                     gs::hub::target::C8AckDropGate::kWindowMs));
        return;
    }
#endif
#if GS_HIL_SIGNED_FOTA
    if (std::strcmp(verb, "START_SIGNED_C3_FOTA") == 0) {
        char* device_id = next_token(cursor);
        char* version = next_token(cursor);
        if (device_id == nullptr || version == nullptr || next_token(cursor) != nullptr ||
            std::strcmp(device_id, "c3-146393c5d158") != 0 ||
            std::strlen(version) == 0 || std::strlen(version) > 31) {
            ESP_LOGW(kTag, "HIL_SIGNED_FOTA_ERROR reason=invalid_exact_node_or_version");
            return;
        }
        gs::hub::target::FotaStartRequest request;
        request.physical_device_id = device_id;
        request.board = "esp32c3";
        request.version = version;
        const bool queued = gs::hub::target::request_authenticated_fota(std::move(request));
        ESP_LOGI(kTag, "HIL_SIGNED_FOTA_TRIGGER result=%s node=c3-146393c5d158 version=%s authentication=OWNER_REQUIRED",
                 queued ? "QUEUED" : "REJECTED", version);
        return;
    }
#endif
#if GS_HIL_C8_ACK_HOLD
    if (std::strcmp(verb, "ARM_C8_ACK_HOLD") == 0 ||
        std::strcmp(verb, "RELEASE_C8_ACK_HOLD") == 0 ||
        std::strcmp(verb, "CANCEL_C8_ACK_HOLD") == 0 ||
        std::strcmp(verb, "C8_ACK_HOLD_STATUS") == 0) {
        if (next_token(cursor) != nullptr) {
            ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=invalid_arguments");
            return;
        }
        if (std::strcmp(verb, "C8_ACK_HOLD_STATUS") == 0) {
            gs::hub::target::log_c8_ack_hold_fixture();
            return;
        }
        const bool accepted = std::strcmp(verb, "ARM_C8_ACK_HOLD") == 0
            ? gs::hub::target::arm_c8_ack_hold_fixture()
            : std::strcmp(verb, "RELEASE_C8_ACK_HOLD") == 0
            ? gs::hub::target::release_c8_ack_hold_fixture()
            : gs::hub::target::cancel_c8_ack_hold_fixture();
        ESP_LOGI(kTag, "HIL_C8_ACK_HOLD_COMMAND command=%s result=%s hold_ms=%llu watchdog_ms=%llu",
                 verb, accepted ? "ACCEPTED" : "REJECTED",
                 static_cast<unsigned long long>(gs::hub::target::C8AckHoldGate::kHoldMs),
                 static_cast<unsigned long long>(gs::hub::target::C8AckHoldGate::kWatchdogMs));
        gs::hub::target::log_c8_ack_hold_fixture();
        return;
    }
#endif
#if GS_HIL_COMMISSIONING
    if (std::strcmp(verb, "COMMISSION_EXPECTED_NODE") != 0) {
        ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=unsupported_command");
        return;
    }

    char* device_id = next_token(cursor);
    char* mac_hex = next_token(cursor);
    char* public_key_hex = next_token(cursor);
    char* installer_code_hex = next_token(cursor);
    char* logical_id = next_token(cursor);
    char* room = next_token(cursor);
    char* function = next_token(cursor);
    if (device_id == nullptr || mac_hex == nullptr || public_key_hex == nullptr ||
        installer_code_hex == nullptr || logical_id == nullptr || room == nullptr ||
        function == nullptr || next_token(cursor) != nullptr) {
        ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=invalid_arguments");
        return;
    }

    gs::hub::target::HubSecurityLink::ExpectedNode node;
    node.device_id = device_id;
    node.logical_id = logical_id;
    node.room = room;
    node.function = function;
    const bool decoded = decode_hex(mac_hex, node.radio_mac.data(), node.radio_mac.size()) &&
        decode_hex(public_key_hex, node.public_key.data(), node.public_key.size()) &&
        decode_hex(installer_code_hex, node.installer_code.data(),
                   node.installer_code.size());
    // The task wipes the complete UART command buffer, including installer code.
    if (!decoded) {
        mbedtls_platform_zeroize(node.installer_code.data(), node.installer_code.size());
        ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=invalid_identity_encoding");
        return;
    }
    const bool accepted = gs::hub::target::request_node_commissioning(std::move(node));
    ESP_LOGI(kTag, "HIL_FIXTURE_%s request=exact_node",
             accepted ? "OK" : "ERROR");
#else
    ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=unsupported_command");
#endif
}

void control_task(void*) {
    std::array<char, kCommandCapacity> command{};
    std::size_t length = 0;
#if GS_HIL_COMMISSIONING && GS_HIL_C8_ACK_HOLD && GS_HIL_SIGNED_FOTA
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=COMMISSION_EXPECTED_NODE,FIXTURE_STATUS,ARM_C8_ACK_HOLD,RELEASE_C8_ACK_HOLD,CANCEL_C8_ACK_HOLD,C8_ACK_HOLD_STATUS,START_SIGNED_C3_FOTA");
#elif GS_HIL_C8_ACK_HOLD && GS_HIL_SIGNED_FOTA
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=ARM_C8_ACK_HOLD,RELEASE_C8_ACK_HOLD,CANCEL_C8_ACK_HOLD,C8_ACK_HOLD_STATUS,START_SIGNED_C3_FOTA");
#elif GS_HIL_COMMISSIONING && GS_HIL_C8_ACK_HOLD
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=COMMISSION_EXPECTED_NODE,FIXTURE_STATUS,ARM_C8_ACK_HOLD,RELEASE_C8_ACK_HOLD,CANCEL_C8_ACK_HOLD,C8_ACK_HOLD_STATUS");
#elif GS_HIL_C8_ACK_HOLD
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=ARM_C8_ACK_HOLD,RELEASE_C8_ACK_HOLD,CANCEL_C8_ACK_HOLD,C8_ACK_HOLD_STATUS");
#elif GS_HIL_COMMISSIONING && GS_HIL_SIGNED_FOTA
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=COMMISSION_EXPECTED_NODE,FIXTURE_STATUS,START_SIGNED_C3_FOTA");
#elif GS_HIL_SIGNED_FOTA
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=START_SIGNED_C3_FOTA");
#elif GS_HIL_C8_ACK_DROP
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=COMMISSION_EXPECTED_NODE,FIXTURE_STATUS,DROP_NEXT_DURABLE_ACK");
#elif GS_HIL_COMMISSIONING
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=COMMISSION_EXPECTED_NODE,FIXTURE_STATUS");
#else
    ESP_LOGI(kTag, "HIL_FIXTURE_READY protocol=1 commands=NONE");
#endif
    for (;;) {
        const int value = std::fgetc(stdin);
        if (value == EOF) {
            clearerr(stdin);
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        const char ch = static_cast<char>(value);
        if (ch == '\r') continue;
        if (ch == '\n') {
            command[length] = '\0';
            dispatch(command.data());
            mbedtls_platform_zeroize(command.data(), command.size());
            length = 0;
        } else if (length + 1U < command.size()) {
            command[length++] = ch;
        } else {
            mbedtls_platform_zeroize(command.data(), command.size());
            length = 0;
            ESP_LOGW(kTag, "HIL_FIXTURE_ERROR reason=command_too_long");
        }
    }
}
}  // namespace

void start_fixture_commissioning_control() {
    ESP_ERROR_CHECK(xTaskCreate(control_task, "gs_fixture_uart", 4096, nullptr, 5, nullptr) == pdPASS
                        ? ESP_OK : ESP_ERR_NO_MEM);
}
