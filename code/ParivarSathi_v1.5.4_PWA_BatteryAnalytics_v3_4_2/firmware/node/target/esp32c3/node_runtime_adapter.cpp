#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "firmware/node/target/esp32c3/node_target_config.hpp"
#include "firmware/node/target/esp32c3/nvs_session_provider.hpp"
#include "sensing/sensing.hpp"

#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <optional>

namespace gs::node::target {
namespace {

constexpr char kTag[] = "gs_node_runtime";
constexpr UBaseType_t kAckQueueDepth = 8U;
constexpr UBaseType_t kControlQueueDepth = 8U;
constexpr UBaseType_t kSendQueueDepth = 4U;
constexpr Milliseconds kSendCallbackTimeoutMs = 1000;
constexpr Milliseconds kHealthIntervalMs = 60000;

struct SendResult {
    bool accepted_by_radio{false};
};

StaticQueue_t g_ack_queue_state{};
StaticQueue_t g_control_queue_state{};
StaticQueue_t g_send_queue_state{};
alignas(ReceivedFrame) std::array<std::uint8_t, kAckQueueDepth * sizeof(ReceivedFrame)> g_ack_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kControlQueueDepth * sizeof(ReceivedFrame)> g_control_storage{};
alignas(SendResult) std::array<std::uint8_t, kSendQueueDepth * sizeof(SendResult)> g_send_storage{};
QueueHandle_t g_ack_queue = nullptr;
QueueHandle_t g_control_queue = nullptr;
QueueHandle_t g_send_queue = nullptr;
std::uint64_t g_session_id = 0;
std::atomic<std::uint32_t> g_ack_queue_drops{0};
std::atomic<std::uint32_t> g_control_queue_drops{0};
std::atomic<std::uint32_t> g_send_queue_drops{0};
std::atomic<std::uint32_t> g_fota_timeouts{0};
std::atomic<bool> g_control_plane_active{false};
std::atomic<bool> g_ota_owner_started{false};
std::atomic<bool> g_ota_sensing_ready{false};
std::atomic<bool> g_ota_post_sensing_radio_confirmed{false};
std::atomic<std::uint32_t> g_ota_post_sensing_runtime_ticks{0};
#if GS_HIL_BUILD
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

bool from_qualified_hub(const std::uint8_t* mac) {
    return mac != nullptr &&
           std::memcmp(mac, kQualifiedHubMac.data(), kQualifiedHubMac.size()) == 0;
}

void receive_callback(const esp_now_recv_info_t* info, const std::uint8_t* data,
                      int length) {
    if (info == nullptr || !from_qualified_hub(info->src_addr) || data == nullptr ||
        length <= 0 || static_cast<std::size_t>(length) > kTargetEspNowPayloadMax) {
        return;
    }

    const auto frame_class = transport::classify_frame(data, static_cast<std::size_t>(length));
    QueueHandle_t destination = nullptr;
    if (frame_class == transport::FrameClass::NodeAck &&
        static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_ack_queue;
    } else if (frame_class == transport::FrameClass::ControlFota) {
        destination = g_control_queue;
    } else {
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
    if (actual_mac != kQualifiedNodeMac) {
        ESP_LOGE(kTag, "STA MAC does not match qualified C3");
        return ESP_ERR_INVALID_STATE;
    }
    return ESP_OK;
}

esp_err_t initialize_esp_now() {
    esp_err_t result = esp_now_init();
    if (result != ESP_OK) return result;
    if ((result = esp_now_register_recv_cb(receive_callback)) != ESP_OK) return result;
    if ((result = esp_now_register_send_cb(send_callback)) != ESP_OK) return result;

    esp_now_peer_info_t peer{};
    std::memcpy(peer.peer_addr, kQualifiedHubMac.data(), kQualifiedHubMac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;  // Production peer key management remains open.
    if (!esp_now_is_peer_exist(kQualifiedHubMac.data())) {
        result = esp_now_add_peer(&peer);
    }
    return result;
}

void owner_task(void*) {
    NodeRuntime runtime(kNodeId, g_session_id);
    g_ota_owner_started.store(true, std::memory_order_release);
    QualifiedInput pir(EventKind::Motion, std::nullopt, kPirDebounceMs,
                       kPirMinimumRetriggerMs);
    std::optional<EventKey> in_flight;
    bool health_in_flight = false;
    Milliseconds sent_at_ms = 0;
    Milliseconds led_off_at_ms = 0;
    Milliseconds next_health_ms =
#if GS_HIL_BUILD
        1000;
#else
        kHealthIntervalMs;
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
    const esp_partition_t* running = esp_ota_get_running_partition();
    esp_ota_img_states_t ota_state{};
    if (running != nullptr &&
        esp_ota_get_state_partition(running, &ota_state) == ESP_OK &&
        ota_state == ESP_OTA_IMG_PENDING_VERIFY) {
        // A pending image needs fresh post-sensing radio evidence. Ordinary
        // boots keep the configured health interval.
        next_health_ms = monotonic_ms();
    }

    for (;;) {
        const Milliseconds now = monotonic_ms();
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
            const auto decoded = transport::decode_node_ack(
                ack_frame.bytes.data(), ack_frame.size);
            if (!decoded) {
                ESP_LOGW(kTag, "Rejected malformed ACK error=%d", static_cast<int>(decoded.error));
                continue;
            }
            const EventKey key{decoded.value->node_id, decoded.value->session_id,
                               decoded.value->sequence_number};
            const bool retired = runtime.acknowledge(key, decoded.value->ack_type);
            breadcrumb = retired ? NodeBreadcrumb::EventRetired : NodeBreadcrumb::AppAck;
            ESP_LOGI(kTag, "Application ACK session=%llu seq=%llu class=%d retired=%d",
                     static_cast<unsigned long long>(key.session_id),
                     static_cast<unsigned long long>(key.sequence),
                     static_cast<int>(decoded.value->ack_type), retired);
        }

        SendResult send_result;
        while (xQueueReceive(g_send_queue, &send_result, 0) == pdTRUE) {
            if (send_result.accepted_by_radio) ++mac_success_count;
            else ++mac_failure_count;
            if (in_flight) {
                runtime.transport_result(*in_flight, send_result.accepted_by_radio, now);
                breadcrumb = send_result.accepted_by_radio
                    ? NodeBreadcrumb::WaitAppAck : NodeBreadcrumb::RetryBackoff;
                ESP_LOGI(kTag, "MAC result session=%llu seq=%llu accepted=%d",
                         static_cast<unsigned long long>(in_flight->session_id),
                         static_cast<unsigned long long>(in_flight->sequence),
                         send_result.accepted_by_radio);
                in_flight.reset();
            } else if (health_in_flight) {
                if (send_result.accepted_by_radio &&
                    g_ota_sensing_ready.load(std::memory_order_acquire)) {
                    g_ota_post_sensing_radio_confirmed.store(true,
                                                             std::memory_order_release);
                }
                health_in_flight = false;
            }
        }
        if (in_flight && now - sent_at_ms >= kSendCallbackTimeoutMs) {
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
#if GS_HIL_BUILD
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
            // GPIO8 is a local qualified-PIR indication. It is deliberately
            // independent of store admission, radio delivery and Hub ACK.
            (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio),
                                 kLedActiveLow ? 0 : 1);
            led_off_at_ms = now + 200;
            if (!maintenance) {
                breadcrumb = NodeBreadcrumb::EventRecordEnter;
                const auto store_full_before = runtime.stats().store_full;
                const auto key = runtime.record(*sensed, kLocation, now, 0,
                                                24U * 60U * 60U, 0, false,
                                                SensorType::Pir, 0);
                if (key) {
                    breadcrumb = NodeBreadcrumb::EventRecordOk;
                    ESP_LOGI(kTag, "PIR -> NodeRuntime session=%llu seq=%llu",
                             static_cast<unsigned long long>(key->session_id),
                             static_cast<unsigned long long>(key->sequence));
                } else {
                    ++rejected_pir;
                    const bool store_full = runtime.stats().store_full != store_full_before;
                    breadcrumb = store_full ? NodeBreadcrumb::StoreFull
                                            : NodeBreadcrumb::EventRecordRejected;
                    last_error = store_full ? NodeHealthError::StoreFull
                                            : NodeHealthError::TxQueueFull;
                }
            } else {
                ++rejected_pir;
            }
        }
        if (led_off_at_ms != 0 && now >= led_off_at_ms) {
            (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio), kLedActiveLow ? 1 : 0);
            led_off_at_ms = 0;
        }

        if (!in_flight && !health_in_flight && !maintenance &&
            (now >= next_health_ms
#if GS_HIL_BUILD
             || g_hil_force_health.exchange(false, std::memory_order_acq_rel)
#endif
            )) {
            const auto& stats = runtime.stats();
            const auto& radio_stats = runtime.radio_stats();
            const auto oldest = runtime.oldest_pending_key();
            NodeHealthSnapshot health;
            health.node_id = kNodeId;
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
            const auto encoded = transport::encode_node_health(health);
            next_health_ms = now + kHealthIntervalMs;
            if (encoded) {
                ++send_attempts;
                const esp_err_t sent = esp_now_send(kQualifiedHubMac.data(),
                                                    encoded.frame.bytes.data(),
                                                    encoded.frame.size);
                if (sent == ESP_OK) {
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
                    ++send_attempts;
                    const esp_err_t sent = esp_now_send(kQualifiedHubMac.data(),
                                                        encoded.frame.bytes.data(),
                                                        encoded.frame.size);
                    if (sent == ESP_OK) {
                        in_flight = key;
                        sent_at_ms = now;
                        breadcrumb = NodeBreadcrumb::WaitMac;
                        ESP_LOGI(kTag, "NodeMessage sent session=%llu seq=%llu bytes=%u",
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

#if GS_HIL_BUILD
        g_hil_retained.store(static_cast<std::uint32_t>(runtime.persisted()),
                             std::memory_order_release);
        g_hil_in_flight.store(in_flight ? 1U : 0U, std::memory_order_release);
        g_hil_runtime_live.store(runtime_liveness, std::memory_order_release);
        g_hil_sensing_live.store(sensing_liveness, std::memory_order_release);
#endif

        g_ota_post_sensing_runtime_ticks.fetch_add(1U, std::memory_order_relaxed);

        vTaskDelay(pdMS_TO_TICKS(kPirPollMs));
    }
}

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

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

#if GS_HIL_BUILD
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
    g_send_queue = xQueueCreateStatic(kSendQueueDepth, sizeof(SendResult),
                                      g_send_storage.data(), &g_send_queue_state);
    if (g_ack_queue == nullptr || g_control_queue == nullptr || g_send_queue == nullptr) {
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
