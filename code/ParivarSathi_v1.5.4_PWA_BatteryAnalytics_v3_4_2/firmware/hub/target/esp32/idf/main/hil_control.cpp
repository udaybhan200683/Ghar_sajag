#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"

#include "esp_log.h"
#include "esp_app_desc.h"
#include "esp_system.h"
#include "freertos/task.h"

#include <cstdio>
#include <cstring>
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
