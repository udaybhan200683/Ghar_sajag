#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/common/security/psa_commissioning_crypto.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "firmware/common/security/target_wrapping_key.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "power/power.hpp"
#include "firmware/node/target/esp32c3/node_security_link.hpp"
#include "firmware/node/target/esp32c3/node_target_config.hpp"
#include "firmware/node/target/esp32c3/nvs_session_provider.hpp"
#include "sensing/sensing.hpp"

#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_random.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <optional>
#include <vector>

namespace gs::node::target {
namespace {

constexpr char kTag[] = "gs_node_runtime";
constexpr UBaseType_t kAckQueueDepth = 8U;
constexpr UBaseType_t kControlQueueDepth = 8U;
constexpr UBaseType_t kSecurityQueueDepth = 8U;
constexpr UBaseType_t kSendQueueDepth = 4U;
constexpr Milliseconds kSendCallbackTimeoutMs = 1000;
#if GS_HIL_BUILD
constexpr Milliseconds kHealthIntervalMs = 60000;  // Keep the qualified raw HIL cadence.
#else
constexpr Milliseconds kHealthIntervalMs =
    static_cast<Milliseconds>(NodeProtocolPolicy::heartbeat_seconds) * 1000;
#endif
#if GS_HIL_CONTROL
#define GS_NODE_PROGRESS_LOG ESP_LOGI
#else
#define GS_NODE_PROGRESS_LOG ESP_LOGD
#endif

struct SendResult {
    bool accepted_by_radio{false};
};

StaticQueue_t g_ack_queue_state{};
StaticQueue_t g_control_queue_state{};
StaticQueue_t g_security_queue_state{};
StaticQueue_t g_security_send_queue_state{};
StaticQueue_t g_send_queue_state{};
#if !GS_HIL_BUILD
StaticQueue_t g_fota_ack_queue_state{};
alignas(AuthenticatedFotaAck) std::array<std::uint8_t, 4U * sizeof(AuthenticatedFotaAck)> g_fota_ack_storage{};
QueueHandle_t g_fota_ack_queue = nullptr;
#endif
alignas(ReceivedFrame) std::array<std::uint8_t, kAckQueueDepth * sizeof(ReceivedFrame)> g_ack_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kControlQueueDepth * sizeof(ReceivedFrame)> g_control_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kSecurityQueueDepth * sizeof(ReceivedFrame)> g_security_storage{};
alignas(SendResult) std::array<std::uint8_t, sizeof(SendResult)> g_security_send_storage{};
alignas(SendResult) std::array<std::uint8_t, kSendQueueDepth * sizeof(SendResult)> g_send_storage{};
QueueHandle_t g_ack_queue = nullptr;
QueueHandle_t g_control_queue = nullptr;
QueueHandle_t g_security_queue = nullptr;
QueueHandle_t g_security_send_queue = nullptr;
QueueHandle_t g_send_queue = nullptr;
std::uint64_t g_session_id = 0;
std::atomic<std::uint32_t> g_ack_queue_drops{0};
std::atomic<std::uint32_t> g_control_queue_drops{0};
std::atomic<std::uint32_t> g_send_queue_drops{0};
std::atomic<std::uint32_t> g_fota_timeouts{0};
std::atomic<bool> g_control_plane_active{false};
std::atomic<bool> g_security_phase{true};
std::atomic<bool> g_ota_owner_started{false};
std::atomic<bool> g_ota_sensing_ready{false};
std::atomic<bool> g_ota_post_sensing_radio_confirmed{false};
std::atomic<std::uint32_t> g_ota_post_sensing_runtime_ticks{0};
#if GS_HIL_CONTROL
std::atomic<std::uint32_t> g_hil_motion_pending{0};
std::atomic<bool> g_hil_force_health{false};
std::atomic<std::uint32_t> g_hil_retained{0};
std::atomic<std::uint32_t> g_hil_in_flight{0};
std::atomic<std::uint32_t> g_hil_runtime_live{0};
std::atomic<std::uint32_t> g_hil_sensing_live{0};
#endif

Milliseconds monotonic_ms() {
    return static_cast<Milliseconds>(esp_timer_get_time() / 1000);
}

#if GS_HIL_BUILD
bool from_qualified_hub(const std::uint8_t* mac) {
    return mac != nullptr &&
           std::memcmp(mac, kQualifiedHubMac.data(), kQualifiedHubMac.size()) == 0;
}
#endif

void receive_callback(const esp_now_recv_info_t* info, const std::uint8_t* data,
                      int length) {
    if (info == nullptr || data == nullptr ||
        length <= 0 || static_cast<std::size_t>(length) > kTargetEspNowPayloadMax) {
        return;
    }

    const bool security_wire = length >= 3 && data[0] == 0x47 &&
                               data[1] == 0x53 && data[2] == 1;
    const bool secured_runtime = length >= 3 && data[0] == 0x47 &&
                                 data[1] == 0x53 && data[2] == 2;
    QueueHandle_t destination = nullptr;
    if (security_wire) {
        destination = g_security_queue;
    } else if (secured_runtime) {
        destination = g_ack_queue;
    }
#if GS_HIL_BUILD
    else if (transport::classify_frame(data, static_cast<std::size_t>(length)) ==
                 transport::FrameClass::NodeAck &&
               from_qualified_hub(info->src_addr)) {
        destination = g_ack_queue;
    }
    else if (transport::classify_frame(data, static_cast<std::size_t>(length)) ==
                 transport::FrameClass::ControlFota &&
               from_qualified_hub(info->src_addr)) {
        destination = g_control_queue;
    }
#endif
    else {
        return;
    }
    if (destination == nullptr) return;

    ReceivedFrame envelope;
    std::memcpy(envelope.source_mac.data(), info->src_addr, envelope.source_mac.size());
    envelope.size = static_cast<std::uint16_t>(length);
    if (info->rx_ctrl != nullptr) {
        envelope.transport_rssi = info->rx_ctrl->rssi;
        envelope.channel = info->rx_ctrl->channel;
    }
    std::memcpy(envelope.bytes.data(), data, envelope.size);
    if (xQueueSend(destination, &envelope, 0) != pdTRUE) {
        if (destination == g_ack_queue) {
            g_ack_queue_drops.fetch_add(1U, std::memory_order_relaxed);
        } else {
            g_control_queue_drops.fetch_add(1U, std::memory_order_relaxed);
        }
    }
}

#if ESP_IDF_VERSION_MAJOR >= 6
void send_callback(const esp_now_send_info_t*, esp_now_send_status_t status) {
#else
void send_callback(const std::uint8_t*, esp_now_send_status_t status) {
#endif
    // FOTA ACK sends use the same peer and produce indistinguishable MAC
    // callbacks. They belong to the control-plane worker, not NodeRuntime.
    if (g_security_phase.load(std::memory_order_acquire)) {
        if (g_security_send_queue != nullptr) {
            const SendResult result{status == ESP_NOW_SEND_SUCCESS};
            (void)xQueueOverwrite(g_security_send_queue, &result);
        }
        return;
    }
    if (g_send_queue == nullptr ||
        g_control_plane_active.load(std::memory_order_acquire)) return;
    const SendResult result{status == ESP_NOW_SEND_SUCCESS};
    if (xQueueSend(g_send_queue, &result, 0) != pdTRUE) {
        g_send_queue_drops.fetch_add(1U, std::memory_order_relaxed);
    }
}

esp_err_t initialize_gpio() {
    gpio_config_t led{};
    led.pin_bit_mask = 1ULL << kLedGpio;
    led.mode = GPIO_MODE_OUTPUT;
    led.pull_up_en = GPIO_PULLUP_DISABLE;
    led.pull_down_en = GPIO_PULLDOWN_DISABLE;
    led.intr_type = GPIO_INTR_DISABLE;
    esp_err_t result = gpio_config(&led);
    if (result != ESP_OK) return result;
    result = gpio_set_level(static_cast<gpio_num_t>(kLedGpio), kLedActiveLow ? 1 : 0);
    if (result != ESP_OK) return result;

    gpio_config_t pir{};
    pir.pin_bit_mask = 1ULL << kPirGpio;
    pir.mode = GPIO_MODE_INPUT;
    pir.pull_up_en = GPIO_PULLUP_DISABLE;
    pir.pull_down_en = GPIO_PULLDOWN_ENABLE;
    pir.intr_type = GPIO_INTR_DISABLE;
    return gpio_config(&pir);
}

esp_err_t initialize_wifi() {
    esp_err_t result = esp_netif_init();
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) return result;
    result = esp_event_loop_create_default();
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) return result;
    const wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    if ((result = esp_wifi_init(&config)) != ESP_OK) return result;
    if ((result = esp_wifi_set_storage(WIFI_STORAGE_RAM)) != ESP_OK) return result;
    if ((result = esp_wifi_set_mode(WIFI_MODE_STA)) != ESP_OK) return result;
    if ((result = esp_wifi_start()) != ESP_OK) return result;
    if ((result = esp_wifi_set_ps(WIFI_PS_NONE)) != ESP_OK) return result;
    if ((result = esp_wifi_set_channel(kEspNowChannel, WIFI_SECOND_CHAN_NONE)) != ESP_OK) return result;
    if ((result = esp_wifi_set_max_tx_power(kTxPowerQuarterDbm)) != ESP_OK) return result;

    std::array<std::uint8_t, 6> actual_mac{};
    if ((result = esp_wifi_get_mac(WIFI_IF_STA, actual_mac.data())) != ESP_OK) return result;
    #if GS_HIL_CONTROL
    if (actual_mac != kQualifiedNodeMac) {
        ESP_LOGE(kTag, "STA MAC does not match qualified C3");
        return ESP_ERR_INVALID_STATE;
    }
    #endif
    return ESP_OK;
}

esp_err_t initialize_esp_now() {
    esp_err_t result = esp_now_init();
    if (result != ESP_OK) return result;
    if ((result = esp_now_register_recv_cb(receive_callback)) != ESP_OK) return result;
    if ((result = esp_now_register_send_cb(send_callback)) != ESP_OK) return result;

    #if GS_HIL_BUILD
    esp_now_peer_info_t peer{};
    std::memcpy(peer.peer_addr, kQualifiedHubMac.data(), kQualifiedHubMac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;  // Production peer key management remains open.
    if (!esp_now_is_peer_exist(kQualifiedHubMac.data())) {
        result = esp_now_add_peer(&peer);
    }
    #endif
    return result;
}

#if !GS_HIL_BUILD
bool send_security_message(const NodeSecurityLink::Outbound& outbound) {
    security::wire::Message message = outbound.message;
    std::vector<security::wire::Packet> packets;
    std::uint32_t transaction = esp_random();
    if (transaction == 0) transaction = 1;
    if (!security::wire::fragment(message, transaction, packets)) return false;
    if (!esp_now_is_peer_exist(outbound.destination.data())) {
        esp_now_peer_info_t peer{};
        std::memcpy(peer.peer_addr, outbound.destination.data(), outbound.destination.size());
        peer.channel = 0;
        peer.ifidx = WIFI_IF_STA;
        peer.encrypt = false;  // Application AEAD protects runtime after rejoin.
        if (esp_now_add_peer(&peer) != ESP_OK) return false;
    }
    for (const auto& packet : packets) {
        (void)xQueueReset(g_security_send_queue);
        if (esp_now_send(outbound.destination.data(), packet.bytes.data(),
                         packet.size) != ESP_OK) return false;
        SendResult result;
        if (xQueueReceive(g_security_send_queue, &result,
                          pdMS_TO_TICKS(kSendCallbackTimeoutMs)) != pdTRUE ||
            !result.accepted_by_radio) return false;
    }
    return true;
}
#endif

void owner_task(void*) {
    PowerPolicy power_policy;
    NodeLedPolicy led_policy;
    EnergyCounters energy;
    energy.boot_count = 1;
    const auto boot_reset = esp_reset_reason();
    if (boot_reset == ESP_RST_BROWNOUT) energy.brownout_count = 1;
    if (boot_reset == ESP_RST_PANIC || boot_reset == ESP_RST_TASK_WDT ||
        boot_reset == ESP_RST_INT_WDT || boot_reset == ESP_RST_WDT ||
        boot_reset == ESP_RST_BROWNOUT) energy.unexpected_resets = 1;
#if !GS_HIL_BUILD
    NodeSecurityLink security_link;
    std::array<std::uint8_t, 6> physical_mac{};
    if (esp_wifi_get_mac(WIFI_IF_STA, physical_mac.data()) != ESP_OK ||
        !security_link.initialize(physical_mac, g_session_id, monotonic_ms())) {
        ESP_LOGE(kTag, "Node security bootstrap failed closed");
        vTaskDelete(nullptr);
        return;
    }
    auto last_outbound = security_link.initial_message();
    const bool rejoining_existing_association = last_outbound.has_value();
    if (last_outbound) (void)send_security_message(*last_outbound);
    Milliseconds next_security_retry_ms = monotonic_ms() + 1500;
    while (!security_link.ready()) {
        if (security_link.faulted()) {
            ESP_LOGE(kTag, "Node security owner faulted; runtime admission disabled");
            vTaskDelete(nullptr);
            return;
        }
        ReceivedFrame frame;
        if (xQueueReceive(g_security_queue, &frame, pdMS_TO_TICKS(100)) == pdTRUE) {
            const auto response = security_link.accept(frame.source_mac,
                frame.bytes.data(), frame.size, monotonic_ms());
            if (response) {
                last_outbound = response;
                (void)send_security_message(*response);
                next_security_retry_ms = monotonic_ms() + 1500;
            }
        }
        if (last_outbound && monotonic_ms() >= next_security_retry_ms) {
            (void)send_security_message(*last_outbound);
            next_security_retry_ms = monotonic_ms() + 3000;
        }
    }
    if (rejoining_existing_association) energy.authenticated_rejoins = 1;
    g_security_phase.store(false, std::memory_order_release);
    NodeRuntime runtime(security_link.binding()->logical_id, g_session_id);
#else
    g_security_phase.store(false, std::memory_order_release);
    NodeRuntime runtime(kNodeId, g_session_id);
#endif
#if !GS_HIL_BUILD
    // Restore retained identities only after the new boot session has been
    // authenticated. A corrupt or unreadable record must not start sensing.
    if (!security_link.restore_recovery(runtime, monotonic_ms())) {
        ESP_LOGE(kTag, "Node recovery restore failed; refusing event admission");
        vTaskDelete(nullptr);
        return;
    }
#endif
    g_ota_owner_started.store(true, std::memory_order_release);
    QualifiedInput pir(EventKind::Motion, std::nullopt, kPirDebounceMs,
                       kPirMinimumRetriggerMs);
    PirNoiseMonitor pir_noise;
    std::optional<EventKey> in_flight;
    bool health_in_flight = false;
    Milliseconds sent_at_ms = 0;
#if GS_HIL_BUILD
    Milliseconds led_off_at_ms = 0;
#else
    bool led_was_on = false;
#endif
    NodeHealthCadence health_cadence(kHealthIntervalMs,
#if GS_HIL_CONTROL
        1000);
#else
        monotonic_ms() + kHealthIntervalMs);
#endif
    std::uint64_t health_sequence = 1;
    std::uint32_t raw_pir_edges = 0;
    std::uint32_t accepted_pir = 0;
    std::uint32_t rejected_pir = 0;
    std::uint32_t sensing_liveness = 0;
    std::uint32_t runtime_liveness = 0;
    std::uint32_t send_attempts = 0;
    std::uint32_t mac_success_count = 0;
    std::uint32_t mac_failure_count = 0;
    bool previous_raw_pir = false;
    bool raw_initialized = false;
    bool previous_maintenance = false;
    NodeBreadcrumb breadcrumb = NodeBreadcrumb::Boot;
    NodeHealthError last_error = NodeHealthError::None;
    const std::uint32_t reset_reason = static_cast<std::uint32_t>(esp_reset_reason());

    ESP_LOGI(kTag, "NodeRuntime owner started session=%llu channel=%u tx_power_qdbm=%d",
             static_cast<unsigned long long>(g_session_id),
             static_cast<unsigned>(kEspNowChannel),
             kTxPowerQuarterDbm);
    vTaskDelay(pdMS_TO_TICKS(kPirStabilizationMs));
    ESP_LOGI(kTag, "PIR ready on GPIO%d", kPirGpio);
    g_ota_sensing_ready.store(true, std::memory_order_release);
#if !GS_HIL_BUILD
    led_policy.trigger(LedSignal::Ready, monotonic_ms());
#endif
    const esp_partition_t* running = esp_ota_get_running_partition();
    esp_ota_img_states_t ota_state{};
    const bool ota_pending_verify = running != nullptr &&
        esp_ota_get_state_partition(running, &ota_state) == ESP_OK &&
        ota_state == ESP_OTA_IMG_PENDING_VERIFY;
    if (ota_pending_verify) {
        // A pending image needs fresh post-sensing radio evidence. Ordinary
        // boots keep the configured health interval.
        health_cadence.schedule_now(monotonic_ms());
    }

    for (;;) {
        const Milliseconds now = monotonic_ms();
        energy.awake_ms = static_cast<std::uint64_t>(now);
        const auto ack_drops = g_ack_queue_drops.exchange(0U, std::memory_order_relaxed);
        ++sensing_liveness;
        ++runtime_liveness;
        const auto control_drops = g_control_queue_drops.exchange(0U, std::memory_order_relaxed);
        const auto send_drops = g_send_queue_drops.exchange(0U, std::memory_order_relaxed);
        const auto fota_timeouts = g_fota_timeouts.exchange(0U, std::memory_order_relaxed);
        if (ack_drops != 0U || control_drops != 0U || send_drops != 0U) {
            ESP_LOGW(kTag, "Callback queue drops ACK=%u CONTROL=%u SEND=%u",
                     static_cast<unsigned>(ack_drops), static_cast<unsigned>(control_drops),
                     static_cast<unsigned>(send_drops));
            if (ack_drops != 0U) last_error = NodeHealthError::AckQueueDrop;
            else if (control_drops != 0U) last_error = NodeHealthError::ControlQueueDrop;
            else last_error = NodeHealthError::SendQueueDrop;
        }
        if (fota_timeouts != 0U) {
            last_error = NodeHealthError::FotaTimeout;
        }
        ReceivedFrame ack_frame;
        while (xQueueReceive(g_ack_queue, &ack_frame, 0) == pdTRUE) {
#if !GS_HIL_BUILD
            if (ack_frame.source_mac != security_link.hub_mac()) continue;
            security::SecureFrame protected_ack;
            protected_ack.size = ack_frame.size;
            std::copy_n(ack_frame.bytes.data(), ack_frame.size,
                        protected_ack.bytes.data());
            transport::EncodedFrame verified_ack;
            if (!security_link.frames()->open(security::RuntimeDirection::Downlink,
                                              protected_ack, verified_ack)) {
                ESP_LOGW(kTag, "Rejected unauthenticated or replayed ACK");
                continue;
            }
            if (verified_ack.size >= 2 && verified_ack.bytes[0] == 'G' &&
                verified_ack.bytes[1] == 'F') {
                const auto decoded_fota = gs::fota::secure_wire::decode(
                    verified_ack.bytes.data(), verified_ack.size);
                if (!decoded_fota || decoded_fota.message.type ==
                                     gs::fota::secure_wire::Type::Ack) {
                    ESP_LOGW(kTag, "Rejected malformed protected FOTA control");
                    continue;
                }
                ReceivedFrame verified_control;
                verified_control.source_mac = ack_frame.source_mac;
                verified_control.authenticated_session = security_link.frames()->session();
                verified_control.size = verified_ack.size;
                std::copy_n(verified_ack.bytes.data(), verified_ack.size,
                            verified_control.bytes.data());
                if (xQueueSend(g_control_queue, &verified_control, 0) != pdTRUE)
                    g_control_queue_drops.fetch_add(1U, std::memory_order_relaxed);
                continue;
            }
            const auto decoded = transport::decode_node_ack(
                verified_ack.bytes.data(), verified_ack.size);
#else
            if (!from_qualified_hub(ack_frame.source_mac.data())) continue;
            const auto decoded = transport::decode_node_ack(
                ack_frame.bytes.data(), ack_frame.size);
#endif
            if (!decoded) {
                ESP_LOGW(kTag, "Rejected malformed ACK error=%d", static_cast<int>(decoded.error));
                continue;
            }
            const EventKey key{decoded.value->node_id, decoded.value->session_id,
                               decoded.value->sequence_number};
#if !GS_HIL_BUILD
            const auto pending_before = runtime.pending();
            const auto retained_before = runtime.persisted();
#endif
#if !GS_HIL_BUILD
            const bool matched_pending = runtime.has_pending_key(key);
#endif
            const bool retired = runtime.acknowledge(key, decoded.value->ack_type);
#if !GS_HIL_BUILD
            if (matched_pending) health_cadence.observe_authenticated_contact(now);
#endif
            if (retired) {
                power_policy.observe_authenticated_contact();
                runtime.set_outage_profile(false, now);
#if !GS_HIL_BUILD
                led_policy.trigger(LedSignal::Delivery, now);
#endif
            }
#if !GS_HIL_BUILD
            if ((runtime.pending() != pending_before ||
                 runtime.persisted() != retained_before) &&
                !security_link.persist_recovery(runtime)) {
                ESP_LOGE(kTag, "Node recovery ACK retirement commit failed; stopping owner");
                vTaskDelete(nullptr);
                return;
            }
            if (runtime.pending() != pending_before ||
                runtime.persisted() != retained_before)
                energy.record_recovery_commit();
#endif
            breadcrumb = retired ? NodeBreadcrumb::EventRetired : NodeBreadcrumb::AppAck;
            GS_NODE_PROGRESS_LOG(kTag, "Application ACK session=%llu seq=%llu class=%d retired=%d",
                     static_cast<unsigned long long>(key.session_id),
                     static_cast<unsigned long long>(key.sequence),
                     static_cast<int>(decoded.value->ack_type), retired);
        }

#if !GS_HIL_BUILD
        AuthenticatedFotaAck fota_ack;
        while (xQueueReceive(g_fota_ack_queue, &fota_ack, 0) == pdTRUE) {
            // A failed transfer may have left an ACK queued before the OTA
            // worker cleared maintenance. Do not let its MAC callback be
            // mistaken for a normal NodeRuntime send after resumption.
            if (!g_control_plane_active.load(std::memory_order_acquire) ||
                !security_link.ready() ||
                security_link.frames()->session() != fota_ack.authenticated_session ||
                fota_ack.message.type != gs::fota::secure_wire::Type::Ack) continue;
            const auto encoded = gs::fota::secure_wire::encode(fota_ack.message);
            security::SecureFrame protected_fota_ack;
            if (!encoded || !security_link.frames()->seal(
                    security::RuntimeDirection::Uplink, encoded.frame,
                    protected_fota_ack)) continue;
            if (esp_now_send(security_link.hub_mac().data(),
                             protected_fota_ack.bytes.data(),
                             protected_fota_ack.size) != ESP_OK) {
                ESP_LOGW(kTag, "Authenticated FOTA ACK send rejected");
            }
        }
#endif

        SendResult send_result;
        while (xQueueReceive(g_send_queue, &send_result, 0) == pdTRUE) {
            if (send_result.accepted_by_radio) ++mac_success_count;
            else ++mac_failure_count;
            if (in_flight) {
                if (runtime.has_pending_key(*in_flight)) {
                    power_policy.observe_unacknowledged_attempt();
                    if (power_policy.consecutive_unacknowledged() >= 3)
                        runtime.set_outage_profile(true, now);
                }
                runtime.transport_result(*in_flight, send_result.accepted_by_radio, now);
                breadcrumb = send_result.accepted_by_radio
                    ? NodeBreadcrumb::WaitAppAck : NodeBreadcrumb::RetryBackoff;
                GS_NODE_PROGRESS_LOG(kTag, "MAC result session=%llu seq=%llu accepted=%d",
                         static_cast<unsigned long long>(in_flight->session_id),
                         static_cast<unsigned long long>(in_flight->sequence),
                         send_result.accepted_by_radio);
                in_flight.reset();
            } else if (health_in_flight) {
                if (send_result.accepted_by_radio &&
                    g_ota_sensing_ready.load(std::memory_order_acquire)) {
                    g_ota_post_sensing_radio_confirmed.store(true,
                                                             std::memory_order_release);
                    if (ota_pending_verify)
                        health_cadence.observe_health_attempt(now);
                }
                health_in_flight = false;
            }
        }
        if (in_flight && now - sent_at_ms >= kSendCallbackTimeoutMs) {
            if (runtime.has_pending_key(*in_flight)) {
                power_policy.observe_unacknowledged_attempt();
                if (power_policy.consecutive_unacknowledged() >= 3)
                    runtime.set_outage_profile(true, now);
            }
            runtime.transport_result(*in_flight, false, now);
            ESP_LOGW(kTag, "MAC callback timeout session=%llu seq=%llu",
                     static_cast<unsigned long long>(in_flight->session_id),
                     static_cast<unsigned long long>(in_flight->sequence));
            in_flight.reset();
            ++mac_failure_count;
            breadcrumb = NodeBreadcrumb::RetryBackoff;
            last_error = NodeHealthError::MacCallbackTimeout;
        } else if (health_in_flight && now - sent_at_ms >= kSendCallbackTimeoutMs) {
            health_in_flight = false;
            ++mac_failure_count;
            last_error = NodeHealthError::MacCallbackTimeout;
        }

        const bool maintenance = g_control_plane_active.load(std::memory_order_acquire);
        if (maintenance != previous_maintenance) {
            breadcrumb = maintenance ? NodeBreadcrumb::FotaPause : NodeBreadcrumb::FotaResume;
            previous_maintenance = maintenance;
        }
        const bool raw_pir = gpio_get_level(static_cast<gpio_num_t>(kPirGpio)) != 0;
        if (!raw_initialized) {
            previous_raw_pir = raw_pir;
            raw_initialized = true;
        } else if (raw_pir != previous_raw_pir) {
            previous_raw_pir = raw_pir;
            ++raw_pir_edges;
            breadcrumb = NodeBreadcrumb::PirRaw;
        }
        auto sensed = pir.sample(raw_pir, now);
        if (pir_noise.observe(raw_pir, sensed.has_value(), now)) {
            const auto& noise = pir_noise.snapshot();
            ESP_LOGW(kTag, "PIR diagnostic rapid_edges=%u noisy_windows=%u stuck_high=%d",
                     static_cast<unsigned>(noise.rapid_edges),
                     static_cast<unsigned>(noise.noisy_windows), noise.stuck_high);
#if !GS_HIL_BUILD
            led_policy.trigger(LedSignal::Fault, now);
#endif
        }
#if GS_HIL_CONTROL
        auto pending = g_hil_motion_pending.load(std::memory_order_acquire);
        while (pending != 0U &&
               !g_hil_motion_pending.compare_exchange_weak(
                   pending, pending - 1U, std::memory_order_acq_rel)) {}
        if (pending != 0U) {
            // HIL injection replaces only the electrical/optical observation.
            // Everything from EventKind admission onward is the production path.
            sensed = EventKind::Motion;
            ESP_LOGI(kTag, "HIL synthetic sensing boundary accepted");
        }
#endif
        if (sensed) {
            ++accepted_pir;
            breadcrumb = NodeBreadcrumb::PirAccepted;
            // Legacy raw HIL retains its qualified-PIR indicator. Production
            // indicates application delivery, not sensing alone.
#if GS_HIL_BUILD
            (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio),
                                 kLedActiveLow ? 0 : 1);
            led_off_at_ms = now + 200;
#endif
            if (!maintenance) {
                breadcrumb = NodeBreadcrumb::EventRecordEnter;
                const auto store_full_before = runtime.stats().store_full;
#if !GS_HIL_BUILD
                const bool gap_was_required = runtime.gap_marker_required();
#endif
                const auto key = runtime.record(*sensed,
#if !GS_HIL_BUILD
                                                security_link.binding()->room,
#else
                                                kLocation,
#endif
                                                now, 0,
                                                24U * 60U * 60U, 0, false,
                                                SensorType::Pir, 0);
                if (key) {
#if !GS_HIL_BUILD
                    // Commit the event and its retry identity before any
                    // ESP-NOW send can make this event visible to the Hub.
                    if (!security_link.persist_recovery(runtime)) {
                        ESP_LOGE(kTag, "Node recovery event commit failed; stopping owner");
                        vTaskDelete(nullptr);
                        return;
                    }
                    energy.record_recovery_commit();
#endif
                    breadcrumb = NodeBreadcrumb::EventRecordOk;
                    GS_NODE_PROGRESS_LOG(kTag, "PIR -> NodeRuntime session=%llu seq=%llu",
                             static_cast<unsigned long long>(key->session_id),
                             static_cast<unsigned long long>(key->sequence));
                } else {
                    ++rejected_pir;
                    const bool store_full = runtime.stats().store_full != store_full_before;
                    breadcrumb = store_full ? NodeBreadcrumb::StoreFull
                                            : NodeBreadcrumb::EventRecordRejected;
                    last_error = store_full ? NodeHealthError::StoreFull
                                            : NodeHealthError::TxQueueFull;
#if !GS_HIL_BUILD
                    if (!gap_was_required && runtime.gap_marker_required() &&
                        !security_link.persist_recovery(runtime)) {
                        ESP_LOGE(kTag, "Node recovery gap commit failed; stopping owner");
                        vTaskDelete(nullptr);
                        return;
                    }
                    if (!gap_was_required && runtime.gap_marker_required())
                        energy.record_recovery_commit();
#endif
                }
            } else {
                ++rejected_pir;
            }
        }
#if GS_HIL_BUILD
        if (led_off_at_ms != 0 && now >= led_off_at_ms) {
            (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio), kLedActiveLow ? 1 : 0);
            led_off_at_ms = 0;
        }
#else
        const bool led_on = led_policy.on(now);
        if (led_on != led_was_on) {
            (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio),
                                 kLedActiveLow ? !led_on : led_on);
            led_was_on = led_on;
        }
#endif

        const bool boot_health_probe = ota_pending_verify &&
            !g_ota_post_sensing_radio_confirmed.load(std::memory_order_acquire);
        const auto application_deadline = runtime.next_retry_deadline();
        const bool application_due = application_deadline && *application_deadline <= now;
#if GS_HIL_BUILD
        // Preserve Phase-1 raw HIL's periodic health evidence during outages.
        const bool suppress_for_pending = false;
        const bool suppress_for_outage = false;
#else
        const bool suppress_for_pending = runtime.pending() != 0 && !boot_health_probe;
        const bool suppress_for_outage = runtime.outage_profile() && !boot_health_probe;
#endif
        if (!in_flight && !health_in_flight && !maintenance && !application_due &&
            (health_cadence.due(now, application_due,
                                suppress_for_pending, suppress_for_outage,
                                maintenance)
#if GS_HIL_CONTROL
             || g_hil_force_health.load(std::memory_order_acquire)
#endif
            )) {
#if GS_HIL_CONTROL
            g_hil_force_health.store(false, std::memory_order_release);
#endif
            const auto& stats = runtime.stats();
            const auto& radio_stats = runtime.radio_stats();
            const auto oldest = runtime.oldest_pending_key();
            NodeHealthSnapshot health;
#if !GS_HIL_BUILD
            health.node_id = security_link.binding()->logical_id;
#else
            health.node_id = kNodeId;
#endif
            health.session_id = g_session_id;
            health.health_sequence = health_sequence++;
            health.uptime_ms = static_cast<std::uint64_t>(now);
            health.reset_reason = reset_reason;
            health.raw_pir_level = raw_pir;
            health.raw_pir_edges = raw_pir_edges;
            health.accepted_pir = accepted_pir;
            health.rejected_pir = rejected_pir;
            health.store_full = stats.store_full;
            health.dropped_motion = stats.dropped_motion;
            health.priority_rejected = stats.priority_rejected;
            health.sensing_liveness = sensing_liveness;
            health.runtime_liveness = runtime_liveness;
            health.last_breadcrumb = breadcrumb;
            health.retained_count = static_cast<std::uint16_t>(runtime.persisted());
            health.oldest_sequence = oldest ? oldest->sequence : 0U;
            health.radio_in_flight = false;
            health.tx_attempts = send_attempts;
            health.mac_success = mac_success_count;
            health.mac_failure = mac_failure_count;
            health.durable_acks = stats.durable_acks;
            health.volatile_acks = stats.volatile_acks;
            health.retries = radio_stats.retries;
            health.periodic_backoff_entries = radio_stats.periodic_backoff_entries;
            health.last_error = last_error;
            health.free_heap = esp_get_free_heap_size();
            health.minimum_free_heap = esp_get_minimum_free_heap_size();
            health.maintenance_active = maintenance;
            ESP_LOGI(kTag,
                     "Power counters uptime_ms=%llu loops=%llu pir=%llu app_tx=%llu "
                     "mac_attempt=%llu retry=%llu health=%llu rejoin=%llu "
                     "recovery_commit=%llu queue_hwm=%u unexpected_reset=%llu",
                     static_cast<unsigned long long>(energy.awake_ms),
                     static_cast<unsigned long long>(energy.sensing_loops),
                     static_cast<unsigned long long>(energy.qualified_pir),
                     static_cast<unsigned long long>(energy.application_tx_attempts),
                     static_cast<unsigned long long>(energy.mac_send_attempts),
                     static_cast<unsigned long long>(energy.radio_retries),
                     static_cast<unsigned long long>(energy.heartbeat_count),
                     static_cast<unsigned long long>(energy.authenticated_rejoins),
                     static_cast<unsigned long long>(energy.recovery_nvs_commits),
                     static_cast<unsigned>(energy.queue_high_water),
                     static_cast<unsigned long long>(energy.unexpected_resets));
            const auto encoded = transport::encode_node_health(health);
            health_cadence.observe_health_attempt(now,
                boot_health_probe ? 60000 : -1);
            if (encoded) {
#if !GS_HIL_BUILD
                security::SecureFrame protected_health;
                if (!security_link.frames()->seal(security::RuntimeDirection::Uplink,
                                                  encoded.frame, protected_health)) {
                    last_error = NodeHealthError::EncodeFailed;
                    continue;
                }
                ++send_attempts;
                const esp_err_t sent = esp_now_send(security_link.hub_mac().data(),
                                                    protected_health.bytes.data(),
                                                    protected_health.size);
#else
                ++send_attempts;
                const esp_err_t sent = esp_now_send(kQualifiedHubMac.data(),
                                                    encoded.frame.bytes.data(),
                                                    encoded.frame.size);
#endif
                energy.record_mac_attempt(false, sent == ESP_OK);
                if (sent == ESP_OK) {
                    ++energy.heartbeat_count;
                    health_in_flight = true;
                    sent_at_ms = now;
                }
            }
        }

        if (!in_flight && !health_in_flight && !maintenance) {
            const auto message = runtime.next_message(now);
            if (message) {
                breadcrumb = NodeBreadcrumb::TxPrepare;
                const EventKey key{message->node_id, message->session_id,
                                   message->sequence_number};
                const auto encoded = transport::encode_node_message(*message);
                if (!encoded) {
                    ESP_LOGE(kTag, "NodeMessage encode failed error=%d", static_cast<int>(encoded.error));
                    runtime.transport_result(key, false, now);
                    last_error = NodeHealthError::EncodeFailed;
                    breadcrumb = NodeBreadcrumb::RetryBackoff;
                } else {
#if !GS_HIL_BUILD
                    security::SecureFrame protected_message;
                    if (!security_link.frames()->seal(security::RuntimeDirection::Uplink,
                                                      encoded.frame, protected_message)) {
                        runtime.transport_result(key, false, now);
                        last_error = NodeHealthError::EncodeFailed;
                        breadcrumb = NodeBreadcrumb::RetryBackoff;
                        continue;
                    }
                    ++send_attempts;
                    const esp_err_t sent = esp_now_send(security_link.hub_mac().data(),
                                                        protected_message.bytes.data(),
                                                        protected_message.size);
#else
                    ++send_attempts;
                    const esp_err_t sent = esp_now_send(kQualifiedHubMac.data(),
                                                        encoded.frame.bytes.data(),
                                                        encoded.frame.size);
#endif
                    energy.record_mac_attempt(true, sent == ESP_OK);
                    if (sent == ESP_OK) {
                        in_flight = key;
                        sent_at_ms = now;
                        breadcrumb = NodeBreadcrumb::WaitMac;
                        GS_NODE_PROGRESS_LOG(kTag, "NodeMessage sent session=%llu seq=%llu bytes=%u",
                                 static_cast<unsigned long long>(key.session_id),
                                 static_cast<unsigned long long>(key.sequence),
                                 static_cast<unsigned>(encoded.frame.size));
                    } else {
                        runtime.transport_result(key, false, now);
                        last_error = NodeHealthError::SendRejected;
                        breadcrumb = NodeBreadcrumb::RetryBackoff;
                        ESP_LOGW(kTag, "esp_now_send failed error=%s", esp_err_to_name(sent));
                    }
                }
            }
        }

#if GS_HIL_CONTROL
        g_hil_retained.store(static_cast<std::uint32_t>(runtime.persisted()),
                             std::memory_order_release);
        g_hil_in_flight.store(in_flight ? 1U : 0U, std::memory_order_release);
        g_hil_runtime_live.store(runtime_liveness, std::memory_order_release);
        g_hil_sensing_live.store(sensing_liveness, std::memory_order_release);
#endif

        energy.radio_retries = runtime.radio_stats().retries;
        energy.observe_pending(static_cast<std::uint32_t>(runtime.pending()));
        const auto retry_due = runtime.next_retry_deadline();
        PowerObservation power_input;
        power_input.now_ms = now;
        power_input.next_retry_ms = retry_due.value_or(-1);
        power_input.next_health_ms =
            (!suppress_for_pending && !suppress_for_outage && !maintenance) ||
                boot_health_probe
                ? health_cadence.next_due_ms() : -1;
        power_input.authenticated = true;
        power_input.sensor_ready = g_ota_sensing_ready.load(std::memory_order_acquire);
        power_input.sensor_safe = !raw_pir;
        power_input.wake_proven = false;  // No target sleep/wake path in BAT-C1/C2.
        power_input.persistence_clean = true;  // Required commit failures stop this owner.
        power_input.maintenance = maintenance;
        power_input.radio_in_flight = in_flight.has_value() || health_in_flight;
        power_input.ack_wait = runtime.pending() != 0;
        power_input.due_work = retry_due && *retry_due <= now;
        power_input.pending_work = runtime.pending() != 0;
        power_input.qualified_motion = sensed.has_value();
        const auto power_decision = power_policy.evaluate(power_input);
        (void)power_decision;  // Diagnostic-only until a later validated power wave.
        energy.record_sensing_loop(static_cast<std::uint64_t>(
            std::max<Milliseconds>(0, monotonic_ms() - now)), sensed.has_value());

        g_ota_post_sensing_runtime_ticks.fetch_add(1U, std::memory_order_relaxed);

        vTaskDelay(pdMS_TO_TICKS(kPirPollMs));
    }
}

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

#if !GS_HIL_BUILD
bool submit_authenticated_fota_ack(const AuthenticatedFotaAck& ack) {
    return g_fota_ack_queue != nullptr && ack.authenticated_session != 0 &&
           ack.message.type == gs::fota::secure_wire::Type::Ack &&
           xQueueSend(g_fota_ack_queue, &ack, 0) == pdTRUE;
}
#endif

void set_control_plane_active(bool active) {
    g_control_plane_active.store(active, std::memory_order_release);
}

void report_control_plane_timeout() {
    g_fota_timeouts.fetch_add(1U, std::memory_order_relaxed);
}

fota::BootHealthObservation ota_boot_health_observation() {
    return {g_ota_owner_started.load(std::memory_order_acquire),
            g_ota_sensing_ready.load(std::memory_order_acquire),
            g_ota_post_sensing_radio_confirmed.load(std::memory_order_acquire),
            g_control_plane_active.load(std::memory_order_acquire),
            g_ota_post_sensing_runtime_ticks.load(std::memory_order_acquire),
            esp_get_minimum_free_heap_size()};
}

#if GS_HIL_CONTROL
void hil_inject_motion() {
    g_hil_motion_pending.fetch_add(1U, std::memory_order_release);
}

void hil_request_health() {
    g_hil_force_health.store(true, std::memory_order_release);
}

void hil_log_state() {
    const esp_partition_t* running_partition = esp_ota_get_running_partition();
    ESP_LOGI(kTag,
             "HIL_STATE role=c3 session=%llu retained=%u in_flight=%u sensing_live=%u runtime_live=%u pending_inject=%u heap=%u min_heap=%u ota_slot=%s",
             static_cast<unsigned long long>(g_session_id),
             static_cast<unsigned>(g_hil_retained.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_in_flight.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_sensing_live.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_runtime_live.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_motion_pending.load(std::memory_order_acquire)),
             static_cast<unsigned>(esp_get_free_heap_size()),
             static_cast<unsigned>(esp_get_minimum_free_heap_size()),
             running_partition == nullptr ? "unknown" : running_partition->label);
}

void hil_log_test_qr() {
    // Development-only provisioning evidence. A production QR is issued by
    // manufacturing and must never expose the device private signing key.
    static security::TargetIdentitySigner identity("node", 0x7001);
    static bool identity_ready = identity.initialize();
    if (!identity_ready) {
        ESP_LOGE(kTag, "HIL_ERROR command=GET_TEST_QR reason=identity_unavailable");
        return;
    }
    security::PsaCommissioningCrypto crypto(identity);
    security::P256PublicKey public_key{};
    security::Key32 code{};
    std::array<std::uint8_t, 6> mac{};
    if (!crypto.ready() || !identity.public_key("node", public_key) ||
        !security::load_target_installer_code(crypto, code) ||
        esp_wifi_get_mac(WIFI_IF_STA, mac.data()) != ESP_OK) {
        crypto.secure_zero(code.data(), code.size());
        ESP_LOGE(kTag, "HIL_ERROR command=GET_TEST_QR reason=provisioning_unavailable");
        return;
    }
    char key_hex[public_key.size() * 2 + 1]{};
    char code_hex[code.size() * 2 + 1]{};
    constexpr char hex[] = "0123456789abcdef";
    for (std::size_t i = 0; i < public_key.size(); ++i) {
        key_hex[2 * i] = hex[public_key[i] >> 4];
        key_hex[2 * i + 1] = hex[public_key[i] & 0x0f];
    }
    for (std::size_t i = 0; i < code.size(); ++i) {
        code_hex[2 * i] = hex[code[i] >> 4];
        code_hex[2 * i + 1] = hex[code[i] & 0x0f];
    }
    ESP_LOGI(kTag,
             "HIL_TEST_QR profile=TEST_ONLY device_id=c3-%02x%02x%02x%02x%02x%02x public_key=%s",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], key_hex);
    ESP_LOGI(kTag,
             "HIL_TEST_CODE profile=TEST_ONLY device_id=c3-%02x%02x%02x%02x%02x%02x installer_code=%s",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], code_hex);
    crypto.secure_zero(code.data(), code.size());
    std::memset(code_hex, 0, sizeof(code_hex));
    ESP_LOGI(kTag, "HIL_OK command=GET_TEST_QR");
}
#endif

esp_err_t start_runtime_adapter() {
    esp_err_t result = nvs_flash_init();
    if (result != ESP_OK) {
        ESP_LOGE(kTag, "NVS init failed; refusing reusable session identity: %s",
                 esp_err_to_name(result));
        return result;
    }
    const auto session = allocate_nvs_session_id();
    if (!session) {
        ESP_LOGE(kTag, "Could not durably allocate boot session");
        return ESP_FAIL;
    }
    g_session_id = *session;

    g_ack_queue = xQueueCreateStatic(kAckQueueDepth, sizeof(ReceivedFrame),
                                     g_ack_storage.data(), &g_ack_queue_state);
    g_control_queue = xQueueCreateStatic(kControlQueueDepth, sizeof(ReceivedFrame),
                                         g_control_storage.data(), &g_control_queue_state);
    g_security_queue = xQueueCreateStatic(kSecurityQueueDepth, sizeof(ReceivedFrame),
                                          g_security_storage.data(), &g_security_queue_state);
    g_security_send_queue = xQueueCreateStatic(1U, sizeof(SendResult),
        g_security_send_storage.data(), &g_security_send_queue_state);
    g_send_queue = xQueueCreateStatic(kSendQueueDepth, sizeof(SendResult),
        g_send_storage.data(), &g_send_queue_state);
#if !GS_HIL_BUILD
    g_fota_ack_queue = xQueueCreateStatic(4U, sizeof(AuthenticatedFotaAck),
        g_fota_ack_storage.data(), &g_fota_ack_queue_state);
#endif
    if (g_ack_queue == nullptr || g_control_queue == nullptr ||
        g_security_queue == nullptr || g_security_send_queue == nullptr ||
        g_send_queue == nullptr
#if !GS_HIL_BUILD
        || g_fota_ack_queue == nullptr
#endif
        ) {
        return ESP_ERR_NO_MEM;
    }
    if ((result = initialize_gpio()) != ESP_OK) return result;
    if ((result = initialize_wifi()) != ESP_OK) return result;
    if ((result = initialize_esp_now()) != ESP_OK) return result;
    if (xTaskCreate(owner_task, "gs_node_owner", 8192, nullptr, 8, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

}  // namespace gs::node::target
