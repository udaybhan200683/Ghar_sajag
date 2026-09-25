#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"
#include "fota_sender.hpp"

#include "esp_log.h"
#include "esp_app_desc.h"
#include "esp_system.h"
#include "freertos/task.h"

#include <cstdio>
#include <cstring>
#include <sstream>
#include <utility>
#include <vector>
#include <string>

namespace {
constexpr char kTag[] = "gs_hil_control";

void dispatch_command(const char* command) {
    if (std::strcmp(command, "SET_HUB_LOGICAL_ONLINE") == 0) {
        gs::hub::target::hil_set_logical_online(true);
        ESP_LOGI(kTag, "HIL_OK command=SET_HUB_LOGICAL_ONLINE");
    } else if (std::strcmp(command, "SET_HUB_LOGICAL_OFFLINE") == 0) {
        gs::hub::target::hil_set_logical_online(false);
        ESP_LOGI(kTag, "HIL_OK command=SET_HUB_LOGICAL_OFFLINE");
    } else if (std::strcmp(command, "GET_STATE") == 0 ||
               std::strcmp(command, "GET_HEALTH") == 0) {
        gs::hub::target::hil_log_state();
        ESP_LOGI(kTag, "HIL_OK command=%s", command);
    } else if (std::strcmp(command, "GET_TEST_IDENTITY") == 0) {
        gs::hub::target::hil_log_test_identity();
    } else if (std::strcmp(command, "SOFTWARE_RESTART") == 0) {
        ESP_LOGI(kTag, "HIL_OK command=SOFTWARE_RESTART reset_class=SOFTWARE_RESET");
        std::fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(50));
        esp_restart();
#if GS_HIL_BUILD
    } else if (std::strcmp(command, "START_C3_FOTA") == 0) {
        if (gs::hub::target::hil_request_fota())
            ESP_LOGI(kTag, "HIL_OK command=START_C3_FOTA");
        else
            ESP_LOGW(kTag, "HIL_ERROR command=START_C3_FOTA reason=busy_or_unavailable");
#else
    } else if (std::strncmp(command, "START_AUTHENTICATED_SIGNED_C3_FOTA ", 35) == 0) {
        std::istringstream input(command + 35);
        gs::hub::target::FotaStartRequest request;
        std::string extra;
        if (!(input >> request.physical_device_id >> request.board >> request.version) ||
            (input >> extra)) {
            ESP_LOGW(kTag, "HIL_ERROR command=START_AUTHENTICATED_SIGNED_C3_FOTA reason=invalid_arguments");
        } else if (gs::hub::target::hil_request_authenticated_fota(std::move(request))) {
            ESP_LOGI(kTag, "HIL_OK command=START_AUTHENTICATED_SIGNED_C3_FOTA");
        } else {
            ESP_LOGW(kTag, "HIL_ERROR command=START_AUTHENTICATED_SIGNED_C3_FOTA reason=busy_or_unavailable");
        }
    } else if (std::strncmp(command, "COMMISSION_TEST_NODE ", 21) == 0) {
        std::istringstream input(command + 21);
        gs::hub::target::HubSecurityLink::ExpectedNode node;
        std::string mac_hex, key_hex, code_hex, extra;
        if (!(input >> node.device_id >> mac_hex >> key_hex >> code_hex >> node.logical_id >>
              node.room >> node.function) || (input >> extra) || mac_hex.size() != 12 ||
            key_hex.size() != node.public_key.size() * 2 ||
            code_hex.size() != node.installer_code.size() * 2) {
            ESP_LOGW(kTag, "HIL_ERROR command=COMMISSION_TEST_NODE reason=invalid_arguments");
        } else {
            const auto decode_hex = [](const std::string& encoded, std::uint8_t* output,
                                       std::size_t size) {
                const auto nibble = [](char ch) -> int {
                    if (ch >= '0' && ch <= '9') return ch - '0';
                    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
                    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
                    return -1;
                };
                for (std::size_t i = 0; i < size; ++i) {
                    const int high = nibble(encoded[2 * i]);
                    const int low = nibble(encoded[2 * i + 1]);
                    if (high < 0 || low < 0) return false;
                    output[i] = static_cast<std::uint8_t>((high << 4) | low);
                }
                return true;
            };
            const bool decoded = decode_hex(mac_hex, node.radio_mac.data(), node.radio_mac.size()) &&
                decode_hex(key_hex, node.public_key.data(), node.public_key.size()) &&
                decode_hex(code_hex, node.installer_code.data(), node.installer_code.size());
            const bool queued = decoded && gs::hub::target::request_node_commissioning(std::move(node));
            if (queued)
                ESP_LOGI(kTag, "HIL_OK command=COMMISSION_TEST_NODE");
            else
                ESP_LOGW(kTag, "HIL_ERROR command=COMMISSION_TEST_NODE reason=invalid_or_busy");
        }
#endif
    } else if (command[0] != '\0') {
        ESP_LOGW(kTag, "HIL_ERROR unknown_command");
    }
}

void control_task(void*) {
    std::string command;
    ESP_LOGI(kTag, "HIL_READY role=hub protocol=1 version=%s",
             esp_app_get_description()->version);
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
            dispatch_command(command.c_str());
            command.clear();
        } else if (command.size() < 511) {
            command.push_back(ch);
        } else {
            ESP_LOGW(kTag, "HIL_ERROR command_too_long");
            command.clear();
        }
    }
}
}  // namespace

void start_hil_control() {
    ESP_ERROR_CHECK(xTaskCreate(control_task, "gs_hil_uart", 4096, nullptr, 6, nullptr) == pdPASS
                        ? ESP_OK : ESP_ERR_NO_MEM);
}
