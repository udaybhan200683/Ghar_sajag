#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/target/esp32/hub_target_config.hpp"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>

namespace gs::hub::target {
namespace {

constexpr char kTag[] = "gs_hub_runtime";
constexpr UBaseType_t kDataQueueDepth = 16U;
constexpr UBaseType_t kControlQueueDepth = 8U;
constexpr UBaseType_t kHealthQueueDepth = 1U;

StaticQueue_t g_data_queue_state{};
StaticQueue_t g_control_queue_state{};
StaticQueue_t g_health_queue_state{};
alignas(ReceivedFrame) std::array<std::uint8_t, kDataQueueDepth * sizeof(ReceivedFrame)> g_data_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kControlQueueDepth * sizeof(ReceivedFrame)> g_control_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kHealthQueueDepth * sizeof(ReceivedFrame)> g_health_storage{};
QueueHandle_t g_data_queue = nullptr;
QueueHandle_t g_control_queue = nullptr;
QueueHandle_t g_health_queue = nullptr;
std::atomic<std::uint32_t> g_data_queue_drops{0};
std::atomic<std::uint32_t> g_control_queue_drops{0};
std::atomic<bool> g_control_plane_active{false};
#if GS_HIL_BUILD
std::atomic<bool> g_hil_logical_online{true};
std::atomic<std::uint32_t> g_hil_processed{0};
std::atomic<std::uint32_t> g_hil_durable_ack{0};
std::atomic<std::uint32_t> g_hil_health_received{0};
#endif

bool from_qualified_node(const std::uint8_t* mac) {
    return mac != nullptr &&
           std::memcmp(mac, kQualifiedNodeMac.data(), kQualifiedNodeMac.size()) == 0;
}

void receive_callback(const esp_now_recv_info_t* info, const std::uint8_t* data,
                      int length) {
#if GS_HIL_BUILD
    if (!g_hil_logical_online.load(std::memory_order_acquire)) return;
#endif
    if (info == nullptr || !from_qualified_node(info->src_addr) || data == nullptr ||
        length <= 0 || static_cast<std::size_t>(length) > kTargetEspNowPayloadMax) {
        return;
    }

    const auto frame_class = transport::classify_frame(data, static_cast<std::size_t>(length));
    QueueHandle_t destination = nullptr;
    if (frame_class == transport::FrameClass::NodeMessage &&
        static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_data_queue;
    } else if (frame_class == transport::FrameClass::ControlFota) {
        destination = g_control_queue;
    } else if (frame_class == transport::FrameClass::NodeHealth &&
               static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_health_queue;
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
    if (destination == g_health_queue) {
        // Depth one deliberately keeps only the latest best-effort snapshot.
        (void)xQueueOverwrite(destination, &envelope);
    } else if (xQueueSend(destination, &envelope, 0) != pdTRUE) {
        // No durable ACK is emitted, so dropped data remains retained and is
        // retried. The owner reports the counter outside callback context.
        if (destination == g_data_queue) {
            g_data_queue_drops.fetch_add(1U, std::memory_order_relaxed);
        } else {
            g_control_queue_drops.fetch_add(1U, std::memory_order_relaxed);
        }
    }
}

const char* ack_reason(const ProcessResult& result) {
    switch (result.ack) {
        case AckClass::Durable:
            return result.state_changed ? "journal_committed" : "already_committed";
        case AckClass::ReceivedVolatile: return "received_volatile";
        case AckClass::DiscardedPolicy: return "discarded_policy";
        case AckClass::Rejected: return "journal_rejected";
    }
    return "unknown";
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

    std::array<std::uint8_t, 6> actual_mac{};
    if ((result = esp_wifi_get_mac(WIFI_IF_STA, actual_mac.data())) != ESP_OK) return result;
    if (actual_mac != kQualifiedHubMac) {
        ESP_LOGE(kTag, "STA MAC does not match qualified Hub");
        return ESP_ERR_INVALID_STATE;
    }
    return ESP_OK;
}

esp_err_t initialize_esp_now() {
    esp_err_t result = esp_now_init();
    if (result != ESP_OK) return result;
    if ((result = esp_now_register_recv_cb(receive_callback)) != ESP_OK) return result;

    esp_now_peer_info_t peer{};
    std::memcpy(peer.peer_addr, kQualifiedNodeMac.data(), kQualifiedNodeMac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;  // Production peer key management remains open.
    if (!esp_now_is_peer_exist(kQualifiedNodeMac.data())) {
        result = esp_now_add_peer(&peer);
    }
    return result;
}

void owner_task(void*) {
    HubRuntime runtime(32, 1024);
    std::uint64_t authorized_session = 0;
    ESP_LOGI(kTag, "HubRuntime owner started channel=%u",
             static_cast<unsigned>(kEspNowChannel));

    for (;;) {
        if (g_control_plane_active.load(std::memory_order_acquire)) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        ReceivedFrame health_frame;
        if (xQueueReceive(g_health_queue, &health_frame, 0) == pdTRUE) {
            const auto health = transport::decode_node_health(
                health_frame.bytes.data(), health_frame.size);
            if (!health || health.value->node_id != kAuthorizedNodeId ||
                health_frame.source_mac != kQualifiedNodeMac) {
                ESP_LOGW(kTag, "Rejected malformed/unmapped NodeHealth error=%d RSSI=%d CH=%u",
                         static_cast<int>(health.error), health_frame.transport_rssi,
                         static_cast<unsigned>(health_frame.channel));
            } else {
                const NodeHealthSnapshot& value = *health.value;
#if GS_HIL_BUILD
                g_hil_health_received.fetch_add(1U, std::memory_order_relaxed);
#endif
                ESP_LOGI(kTag,
                         "NodeHealth schema=%u session=%llu health_seq=%llu uptime_ms=%llu reset=%u pir_raw=%d pir_edges=%u pir_ok=%u pir_rejected=%u store_full=%u motion_drop=%u priority_rejected=%u sensing_live=%u runtime_live=%u retained=%u oldest_seq=%llu in_flight=%d tx=%u mac_ok=%u mac_fail=%u durable_ack=%u volatile_ack=%u retry=%u backoff=%u breadcrumb=%u error=%u heap=%u min_heap=%u maintenance=%d RSSI=%d CH=%u",
                         static_cast<unsigned>(value.schema),
                         static_cast<unsigned long long>(value.session_id),
                         static_cast<unsigned long long>(value.health_sequence),
                         static_cast<unsigned long long>(value.uptime_ms),
                         static_cast<unsigned>(value.reset_reason), value.raw_pir_level,
                         static_cast<unsigned>(value.raw_pir_edges),
                         static_cast<unsigned>(value.accepted_pir),
                         static_cast<unsigned>(value.rejected_pir),
                         static_cast<unsigned>(value.store_full),
                         static_cast<unsigned>(value.dropped_motion),
                         static_cast<unsigned>(value.priority_rejected),
                         static_cast<unsigned>(value.sensing_liveness),
                         static_cast<unsigned>(value.runtime_liveness),
                         static_cast<unsigned>(value.retained_count),
                         static_cast<unsigned long long>(value.oldest_sequence),
                         value.radio_in_flight, static_cast<unsigned>(value.tx_attempts),
                         static_cast<unsigned>(value.mac_success),
                         static_cast<unsigned>(value.mac_failure),
                         static_cast<unsigned>(value.durable_acks),
                         static_cast<unsigned>(value.volatile_acks),
                         static_cast<unsigned>(value.retries),
                         static_cast<unsigned>(value.periodic_backoff_entries),
                         static_cast<unsigned>(value.last_breadcrumb),
                         static_cast<unsigned>(value.last_error),
                         static_cast<unsigned>(value.free_heap),
                         static_cast<unsigned>(value.minimum_free_heap),
                         value.maintenance_active, health_frame.transport_rssi,
                         static_cast<unsigned>(health_frame.channel));
            }
        }
        ReceivedFrame frame;
        if (xQueueReceive(g_data_queue, &frame, pdMS_TO_TICKS(200)) != pdTRUE) {
            const auto data_drops = g_data_queue_drops.exchange(0U, std::memory_order_relaxed);
            const auto control_drops = g_control_queue_drops.exchange(0U, std::memory_order_relaxed);
            if (data_drops != 0U || control_drops != 0U) {
                ESP_LOGW(kTag, "Callback queue drops DATA=%u CONTROL=%u",
                         static_cast<unsigned>(data_drops),
                         static_cast<unsigned>(control_drops));
            }
            continue;
        }
        const auto decoded = transport::decode_node_message(frame.bytes.data(), frame.size);
        if (!decoded) {
            ESP_LOGW(kTag, "Rejected malformed NodeMessage error=%d RSSI=%d CH=%u",
                     static_cast<int>(decoded.error), frame.transport_rssi,
                     static_cast<unsigned>(frame.channel));
            continue;
        }
        const NodeMessage& message = *decoded.value;
        if (message.node_id != kAuthorizedNodeId ||
            frame.source_mac != kQualifiedNodeMac) {
            ESP_LOGW(kTag, "Rejected unmapped node identity");
            continue;
        }
        if (authorized_session == 0 || message.session_id > authorized_session) {
            authorized_session = message.session_id;
            runtime.authorize_node(message.node_id, authorized_session, true);
            ESP_LOGI(kTag, "Authorized boot session=%llu",
                     static_cast<unsigned long long>(authorized_session));
        } else if (message.session_id != authorized_session) {
            ESP_LOGW(kTag, "Rejected stale session=%llu active=%llu",
                     static_cast<unsigned long long>(message.session_id),
                     static_cast<unsigned long long>(authorized_session));
            continue;
        }

        // No trusted SNTP/epoch source exists in HW-M1.3 target composition.
        // Zero preserves the existing untrusted-time semantics without
        // fabricating wall-clock time. Transport RSSI stays diagnostic-only.
        constexpr EpochSeconds hub_received_at = 0;
        if (!runtime.radio_message_callback(message, hub_received_at)) {
            ESP_LOGW(kTag, "HubRuntime admission rejected session=%llu seq=%llu RSSI=%d CH=%u",
                     static_cast<unsigned long long>(message.session_id),
                     static_cast<unsigned long long>(message.sequence_number),
                     frame.transport_rssi, static_cast<unsigned>(frame.channel));
            continue;
        }
        const auto processed = runtime.run_state_once();
        if (!processed) {
            ESP_LOGW(kTag, "HubRuntime had no admitted event to process");
            continue;
        }

        const auto ack = make_node_ack(processed->key, processed->ack,
                                       hub_received_at, ack_reason(*processed));
        const auto encoded_ack = transport::encode_node_ack(ack);
        if (!encoded_ack) {
            ESP_LOGE(kTag, "NodeAck encode failed error=%d", static_cast<int>(encoded_ack.error));
            continue;
        }
        const esp_err_t sent = esp_now_send(frame.source_mac.data(),
                                            encoded_ack.frame.bytes.data(),
                                            encoded_ack.frame.size);
        ESP_LOGI(kTag,
                 "Processed session=%llu seq=%llu app_ack=%d ack_send=%s RSSI=%d CH=%u",
                 static_cast<unsigned long long>(processed->key.session_id),
                 static_cast<unsigned long long>(processed->key.sequence),
                 static_cast<int>(processed->ack), esp_err_to_name(sent),
                 frame.transport_rssi, static_cast<unsigned>(frame.channel));
#if GS_HIL_BUILD
        g_hil_processed.fetch_add(1U, std::memory_order_relaxed);
        if (processed->ack == AckClass::Durable) {
            g_hil_durable_ack.fetch_add(1U, std::memory_order_relaxed);
        }
#endif
    }
}

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

void set_control_plane_active(bool active) {
    g_control_plane_active.store(active, std::memory_order_release);
}

#if GS_HIL_BUILD
void hil_set_logical_online(bool online) {
    g_hil_logical_online.store(online, std::memory_order_release);
    ESP_LOGI(kTag, "HIL hub logical state online=%d", online);
}

void hil_log_state() {
    ESP_LOGI(kTag,
             "HIL_STATE role=hub online=%d processed=%u durable_ack=%u health=%u data_queue=%u heap=%u min_heap=%u",
             g_hil_logical_online.load(std::memory_order_acquire),
             static_cast<unsigned>(g_hil_processed.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_durable_ack.load(std::memory_order_acquire)),
             static_cast<unsigned>(g_hil_health_received.load(std::memory_order_acquire)),
             static_cast<unsigned>(uxQueueMessagesWaiting(g_data_queue)),
             static_cast<unsigned>(esp_get_free_heap_size()),
             static_cast<unsigned>(esp_get_minimum_free_heap_size()));
}

void hil_log_test_identity() {
    static security::TargetIdentitySigner identity("hub", 0x7001);
    static bool identity_ready = identity.initialize();
    security::P256PublicKey public_key{};
    std::array<std::uint8_t, 6> mac{};
    if (!identity_ready || !identity.public_key("hub", public_key) ||
        esp_wifi_get_mac(WIFI_IF_STA, mac.data()) != ESP_OK) {
        ESP_LOGE(kTag, "HIL_ERROR command=GET_TEST_IDENTITY reason=identity_unavailable");
        return;
    }
    char key_hex[public_key.size() * 2 + 1]{};
    constexpr char hex[] = "0123456789abcdef";
    for (std::size_t i = 0; i < public_key.size(); ++i) {
        key_hex[2 * i] = hex[public_key[i] >> 4];
        key_hex[2 * i + 1] = hex[public_key[i] & 0x0f];
    }
    ESP_LOGI(kTag,
             "HIL_TEST_IDENTITY profile=TEST_ONLY hub_id=hub-%02x%02x%02x%02x%02x%02x public_key=%s",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], key_hex);
    ESP_LOGI(kTag, "HIL_OK command=GET_TEST_IDENTITY");
}
#endif

esp_err_t start_runtime_adapter() {
    esp_err_t result = nvs_flash_init();
    if (result != ESP_OK) return result;
    g_data_queue = xQueueCreateStatic(kDataQueueDepth, sizeof(ReceivedFrame),
                                      g_data_storage.data(), &g_data_queue_state);
    g_control_queue = xQueueCreateStatic(kControlQueueDepth, sizeof(ReceivedFrame),
                                         g_control_storage.data(), &g_control_queue_state);
    g_health_queue = xQueueCreateStatic(kHealthQueueDepth, sizeof(ReceivedFrame),
                                        g_health_storage.data(), &g_health_queue_state);
    if (g_data_queue == nullptr || g_control_queue == nullptr || g_health_queue == nullptr) {
        return ESP_ERR_NO_MEM;
    }
    if ((result = initialize_wifi()) != ESP_OK) return result;
    if ((result = initialize_esp_now()) != ESP_OK) return result;
    if (xTaskCreate(owner_task, "gs_hub_owner", 8192, nullptr, 8, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

}  // namespace gs::hub::target
