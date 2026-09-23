#include "fota_sender.hpp"
#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"

#include "esp_log.h"

namespace {
constexpr char kTag[] = "gs_hub_product";
}
#if GS_HIL_BUILD
void start_hil_control();
#endif

extern "C" void app_main() {
    ESP_LOGI(kTag, "Starting HW-M1.3 ESP32 Hub product composition");
    ESP_ERROR_CHECK(gs::hub::target::start_runtime_adapter());
    ESP_ERROR_CHECK(gs::hub::target::start_fota_sender());
#if GS_HIL_BUILD
    start_hil_control();
#endif
}
