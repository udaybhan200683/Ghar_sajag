#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"

#include "esp_log.h"
#include "esp_app_desc.h"
#include "esp_system.h"
#include "freertos/task.h"

#include <cstdio>
#include <cstring>
#include <string>

namespace {
constexpr char kTag[] = "gs_hil_control";

#if GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE
constexpr char kPowerMode[] = "HIL_AWAKE_TEST_ONLY";
#elif GS_BAT_C8_PHYSICAL_WAKE
constexpr char kPowerMode[] = "BAT_C8_PHYSICAL_WAKE_QUALIFICATION";
#else
constexpr char kPowerMode[] = "SLEEP_ENABLED";
#endif

void dispatch_command(const char* command) {
    if (std::strcmp(command, "INJECT_MOTION") == 0) {
#if GS_BAT_C8_PHYSICAL_WAKE
        ESP_LOGW(kTag, "HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake");
#else
        gs::node::target::hil_inject_motion();
        ESP_LOGI(kTag, "HIL_OK command=INJECT_MOTION");
#endif
    } else if (std::strcmp(command, "GET_HEALTH") == 0) {
#if GS_BAT_C8_PHYSICAL_WAKE
        ESP_LOGW(kTag, "HIL_ERROR command=GET_HEALTH disabled_for_physical_wake");
#else
        gs::node::target::hil_request_health();
        ESP_LOGI(kTag, "HIL_OK command=GET_HEALTH");
#endif
    } else if (std::strcmp(command, "GET_STATE") == 0) {
        gs::node::target::hil_log_state();
        ESP_LOGI(kTag, "HIL_OK command=GET_STATE");
    } else if (std::strcmp(command, "GET_TEST_QR") == 0) {
        gs::node::target::hil_log_test_qr();
#if GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE
    } else if (std::strcmp(command, "REASSOCIATE_GS117_TEST_HUB") == 0) {
        gs::node::target::hil_request_gs117_reassociation();
        ESP_LOGI(kTag, "HIL_OK command=REASSOCIATE_GS117_TEST_HUB status=REQUESTED_TEST_ONLY");
    } else if (std::strcmp(command, "FRESH_COMMISSION_GS117_TEST_FIXTURE") == 0) {
        gs::node::target::hil_request_gs117_fresh_commissioning();
        ESP_LOGI(kTag, "HIL_OK command=FRESH_COMMISSION_GS117_TEST_FIXTURE status=REQUESTED_TEST_ONLY");
#endif
    } else if (std::strcmp(command, "SOFTWARE_RESTART") == 0) {
        ESP_LOGI(kTag, "HIL_OK command=SOFTWARE_RESTART reset_class=SOFTWARE_RESET");
        std::fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(50));
        esp_restart();
    } else if (command[0] != '\0') {
        ESP_LOGW(kTag, "HIL_ERROR unknown_command=%s", command);
    }
}

void control_task(void*) {
    std::string command;
    ESP_LOGI(kTag,
             "HIL_READY role=c3 protocol=1 version=%s power_mode=%s hil_build=%d hil_control=%d physical_wake=%d",
             esp_app_get_description()->version, kPowerMode,
             GS_HIL_BUILD, GS_HIL_CONTROL, GS_BAT_C8_PHYSICAL_WAKE);
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
        } else if (command.size() < 63) {
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
