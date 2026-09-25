#pragma once

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include "firmware/hub/target/esp32/hub_security_link.hpp"

namespace gs::hub::target {

constexpr std::size_t kTargetEspNowPayloadMax = 250U;

struct ReceivedFrame {
    std::array<std::uint8_t, 6> source_mac{};
    std::int8_t transport_rssi{-127};
    std::uint8_t channel{0};
    std::uint16_t size{0};
    std::array<std::uint8_t, kTargetEspNowPayloadMax> bytes{};
};

// Initializes channel 1 ESP-NOW and starts the sole HubRuntime owner task.
// The separate control-plane queue is the explicit handoff to the product
// FOTA worker and is never consumed as business data.
esp_err_t start_runtime_adapter();
QueueHandle_t control_plane_queue();
void set_control_plane_active(bool active);
// Installer-facing product boundary. Ownership of the exact candidate is
// transferred to the Hub owner only when the bounded request queue accepts it.
bool request_node_commissioning(HubSecurityLink::ExpectedNode exact);
// Product service boundary: only an authenticated/authorized local caller may
// request removal. The owner persists revocation before dropping admission.
bool request_node_removal(const std::string& physical_device_id);

#if GS_HIL_BUILD
void hil_set_logical_online(bool online);
void hil_log_state();
void hil_log_test_identity();
#endif

}  // namespace gs::hub::target
