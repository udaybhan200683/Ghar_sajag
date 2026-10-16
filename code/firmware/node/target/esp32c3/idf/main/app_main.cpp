#include "fota_receiver.hpp"
#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"

#include "esp_check.h"
#include "esp_log.h"
#if GS_GS68_NODE_OBSERVER
#include "firmware/node/target/esp32c3/gs68_node_observer.hpp"
#endif

#ifndef GS_BAT_C8_FIXTURE_SECURITY
#define GS_BAT_C8_FIXTURE_SECURITY 0
#endif

namespace {
constexpr char kTag[] = "gs_node_product";
}
#if GS_HIL_CONTROL
#include "firmware/node/target/esp32c3/zero_length_aead_qualification.hpp"
void start_hil_control();
#endif

extern "C" void app_main() {
    ESP_LOGI(kTag, "Starting HW-M1.3 ESP32-C3 product composition");
#if GS_BAT_C8_FIXTURE_SECURITY
    ESP_LOGW(kTag, "GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF");
#endif
#if GS_HIL_CONTROL
    if(!gs::node::target::qualify_zero_length_aead()) {
        ESP_LOGE(kTag,"Zero-length AEAD qualification failed closed; admission not started");
        return;
    }
#endif
    ESP_ERROR_CHECK(gs::node::target::start_runtime_adapter());
    ESP_ERROR_CHECK(gs::node::target::start_fota_receiver());
#if GS_GS68_NODE_OBSERVER
    gs::node::target::gs68::start_node_observer();
#endif
#if GS_HIL_CONTROL
    start_hil_control();
#endif
}
