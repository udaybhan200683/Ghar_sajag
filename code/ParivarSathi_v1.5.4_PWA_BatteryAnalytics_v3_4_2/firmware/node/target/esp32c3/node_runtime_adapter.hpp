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
// that owns NodeRuntime. The caller must compose the returned control-plane
// queue with the existing FOTA maintenance path; data-plane code never consumes
// or journals those frames.
esp_err_t start_runtime_adapter();
QueueHandle_t control_plane_queue();

}  // namespace gs::node::target
