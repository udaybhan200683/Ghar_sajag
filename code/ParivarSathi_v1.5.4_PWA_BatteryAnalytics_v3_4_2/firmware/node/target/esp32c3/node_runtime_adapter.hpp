#pragma once

#include "firmware/node/fota/boot_health_gate.hpp"
#include "firmware/common/transport/fota_secure_wire.hpp"

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
    std::uint64_t authenticated_session{0};
    std::array<std::uint8_t, kTargetEspNowPayloadMax> bytes{};
};

#if !GS_HIL_BUILD
struct AuthenticatedFotaAck {
    std::uint64_t authenticated_session{0};
    gs::fota::secure_wire::Message message{};
};
// Called by the OTA worker; only the Node owner may seal or send this ACK.
bool submit_authenticated_fota_ack(const AuthenticatedFotaAck& ack);
#endif

// Initializes the qualified GPIO/radio configuration and starts the sole task
// that owns NodeRuntime. The product FOTA worker consumes the returned
// control-plane queue; data-plane code never consumes or journals those frames.
esp_err_t start_runtime_adapter();
QueueHandle_t control_plane_queue();
void set_control_plane_active(bool active);
void report_control_plane_timeout();
fota::BootHealthObservation ota_boot_health_observation();

#if GS_HIL_CONTROL
void hil_inject_motion();
void hil_request_health();
void hil_log_state();
void hil_log_test_qr();
#endif

}  // namespace gs::node::target
