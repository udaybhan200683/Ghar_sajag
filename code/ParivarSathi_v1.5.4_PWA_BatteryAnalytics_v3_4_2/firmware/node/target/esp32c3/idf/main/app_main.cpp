#include "fota_receiver.hpp"
#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"

#include "esp_check.h"
#include "esp_log.h"

namespace {
constexpr char kTag[] = "gs_node_product";
}
#if GS_HIL_BUILD
void start_hil_control();
#endif

extern "C" void app_main() {
    ESP_LOGI(kTag, "Starting HW-M1.3 ESP32-C3 product composition");
    ESP_ERROR_CHECK(gs::node::target::start_runtime_adapter());
    ESP_ERROR_CHECK(gs::node::target::start_fota_receiver());
#if GS_HIL_BUILD
    start_hil_control();
#endif
}
