#pragma once

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::node::target {

constexpr std::size_t kTargetEspNowPayloadMax = 250U;

struct ReceivedFrame {
    std::array<std::uint8_t, 6> source_mac{};
    std::int8_t transport_rssi{-127};
    std::uint8_t channel{0};
    std::uint16_t size{0};
    std::array<std::uint8_t, kTargetEspNowPayloadMax> bytes{};
};

// Initializes the qualified GPIO/radio configuration and starts the sole task
// that owns NodeRuntime. The product FOTA worker consumes the returned
// control-plane queue; data-plane code never consumes or journals those frames.
esp_err_t start_runtime_adapter();
QueueHandle_t control_plane_queue();
void set_control_plane_active(bool active);
void report_control_plane_timeout();

#if GS_HIL_BUILD
void hil_inject_motion();
void hil_request_health();
void hil_log_state();
#endif

}  // namespace gs::node::target
