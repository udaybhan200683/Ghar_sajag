#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/target/esp32/hub_target_config.hpp"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <optional>
#include <string>

namespace gs::hub::target {
namespace {

constexpr char kTag[] = "gs_hub_runtime";
constexpr UBaseType_t kDataQueueDepth = 16U;
constexpr UBaseType_t kControlQueueDepth = 8U;

StaticQueue_t g_data_queue_state{};
StaticQueue_t g_control_queue_state{};
alignas(ReceivedFrame) std::array<std::uint8_t, kDataQueueDepth * sizeof(ReceivedFrame)> g_data_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kControlQueueDepth * sizeof(ReceivedFrame)> g_control_storage{};
QueueHandle_t g_data_queue = nullptr;
QueueHandle_t g_control_queue = nullptr;
std::atomic<std::uint32_t> g_data_queue_drops{0};
std::atomic<std::uint32_t> g_control_queue_drops{0};
std::atomic<bool> g_control_plane_active{false};

bool from_qualified_node(const std::uint8_t* mac) {
    return mac != nullptr &&
           std::memcmp(mac, kQualifiedNodeMac.data(), kQualifiedNodeMac.size()) == 0;
}

void receive_callback(const esp_now_recv_info_t* info, const std::uint8_t* data,
                      int length) {
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

#if defined(GS_HW_M1_3_NEGATIVE_HIL)
enum class HilAckScenario : std::uint8_t { DropAck, WrongEventKey, ReceivedVolatile };

struct HilAckState {
    std::optional<EventKey> active_key;
    std::uint8_t next_scenario{0};
    bool first_attempt{true};
};

bool same_event_key(const EventKey& lhs, const EventKey& rhs) {
    return lhs.source_id == rhs.source_id && lhs.session_id == rhs.session_id &&
           lhs.sequence == rhs.sequence;
}

std::optional<HilAckScenario> current_hil_scenario(const HilAckState& state) {
    if (state.next_scenario > 2U) return std::nullopt;
    return static_cast<HilAckScenario>(state.next_scenario);
}
#endif

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
#if defined(GS_HW_M1_3_NEGATIVE_HIL)
    HilAckState hil_ack_state;
#endif
    ESP_LOGI(kTag, "HubRuntime owner started channel=%u",
             static_cast<unsigned>(kEspNowChannel));

    for (;;) {
        if (g_control_plane_active.load(std::memory_order_acquire)) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        ReceivedFrame frame;
        if (xQueueReceive(g_data_queue, &frame, pdMS_TO_TICKS(1000)) != pdTRUE) {
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
#if defined(GS_HW_M1_3_NEGATIVE_HIL)
        ESP_LOGI(kTag, "HIL RSSI semantic_rssi=%d transport_rssi=%d channel=%u",
                 static_cast<int>(message.rssi_dbm), static_cast<int>(frame.transport_rssi),
                 static_cast<unsigned>(frame.channel));
#endif
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

        NodeAckMessage ack = make_node_ack(processed->key, processed->ack,
                                            hub_received_at, ack_reason(*processed));
#if defined(GS_HW_M1_3_NEGATIVE_HIL)
        enum class HilPostSendAction : std::uint8_t { None, FirstInjected, RetryNormal };
        HilPostSendAction hil_post_send = HilPostSendAction::None;
        ESP_LOGI(kTag, "HIL PROCESS session=%llu seq=%llu state_changed=%d app_ack=%d",
                 static_cast<unsigned long long>(processed->key.session_id),
                 static_cast<unsigned long long>(processed->key.sequence),
                 processed->state_changed, static_cast<int>(processed->ack));

        const bool is_active_retry = hil_ack_state.active_key.has_value() &&
                                     same_event_key(*hil_ack_state.active_key, processed->key) &&
                                     !hil_ack_state.first_attempt;
        if (!hil_ack_state.active_key.has_value() && current_hil_scenario(hil_ack_state)) {
            hil_ack_state.active_key = processed->key;
            hil_ack_state.first_attempt = true;
        }

        bool send_ack = true;
        if (hil_ack_state.active_key.has_value() &&
            same_event_key(*hil_ack_state.active_key, processed->key)) {
            const auto scenario = current_hil_scenario(hil_ack_state);
            if (hil_ack_state.first_attempt && scenario.has_value()) {
                switch (*scenario) {
                    case HilAckScenario::DropAck:
                        ESP_LOGW(kTag, "HIL DROP_ACK session=%llu seq=%llu",
                                 static_cast<unsigned long long>(processed->key.session_id),
                                 static_cast<unsigned long long>(processed->key.sequence));
                        // Dropping the ACK is the complete first action. The
                        // next matching frame is therefore the retry phase.
                        hil_ack_state.first_attempt = false;
                        send_ack = false;
                        break;
                    case HilAckScenario::WrongEventKey: {
                        EventKey wrong_key = processed->key;
                        wrong_key.sequence = wrong_key.sequence == UINT64_MAX
                                                 ? wrong_key.sequence - 1U
                                                 : wrong_key.sequence + 1U;
                        ack = make_node_ack(wrong_key, AckClass::Durable,
                                            hub_received_at, "hil_wrong_event_key");
                        ESP_LOGW(kTag,
                                 "HIL WRONG_ACK original_session=%llu original_seq=%llu ack_session=%llu ack_seq=%llu",
                                 static_cast<unsigned long long>(processed->key.session_id),
                                 static_cast<unsigned long long>(processed->key.sequence),
                                 static_cast<unsigned long long>(wrong_key.session_id),
                                 static_cast<unsigned long long>(wrong_key.sequence));
                        hil_post_send = HilPostSendAction::FirstInjected;
                        break;
                    }
                    case HilAckScenario::ReceivedVolatile:
                        ack = make_node_ack(processed->key, AckClass::ReceivedVolatile,
                                            hub_received_at, "hil_received_volatile");
                        ESP_LOGW(kTag, "HIL VOLATILE_ACK session=%llu seq=%llu",
                                 static_cast<unsigned long long>(processed->key.session_id),
                                 static_cast<unsigned long long>(processed->key.sequence));
                        hil_post_send = HilPostSendAction::FirstInjected;
                        break;
                }
            } else if (is_active_retry) {
                const auto scenario = current_hil_scenario(hil_ack_state);
                if (scenario.has_value()) {
                    switch (*scenario) {
                        case HilAckScenario::DropAck:
                            ESP_LOGI(kTag, "HIL DROP_ACK_RETRY session=%llu seq=%llu",
                                     static_cast<unsigned long long>(processed->key.session_id),
                                     static_cast<unsigned long long>(processed->key.sequence));
                            break;
                        case HilAckScenario::WrongEventKey:
                            ESP_LOGI(kTag, "HIL WRONG_ACK_RETRY session=%llu seq=%llu",
                                     static_cast<unsigned long long>(processed->key.session_id),
                                     static_cast<unsigned long long>(processed->key.sequence));
                            break;
                        case HilAckScenario::ReceivedVolatile:
                            ESP_LOGI(kTag, "HIL VOLATILE_ACK_RETRY session=%llu seq=%llu",
                                     static_cast<unsigned long long>(processed->key.session_id),
                                     static_cast<unsigned long long>(processed->key.sequence));
                            break;
                    }
                    hil_post_send = HilPostSendAction::RetryNormal;
                }
            }
        }
        if (!send_ack) continue;
#endif
        const auto encoded_ack = transport::encode_node_ack(ack);
        if (!encoded_ack) {
            ESP_LOGE(kTag, "NodeAck encode failed error=%d", static_cast<int>(encoded_ack.error));
            continue;
        }
        const esp_err_t sent = esp_now_send(frame.source_mac.data(),
                                            encoded_ack.frame.bytes.data(),
                                            encoded_ack.frame.size);
#if defined(GS_HW_M1_3_NEGATIVE_HIL)
        if (sent == ESP_OK) {
            if (hil_post_send == HilPostSendAction::FirstInjected) {
                hil_ack_state.first_attempt = false;
                ESP_LOGI(kTag, "HIL FIRST_ACK_ACTION_COMMITTED session=%llu seq=%llu",
                         static_cast<unsigned long long>(processed->key.session_id),
                         static_cast<unsigned long long>(processed->key.sequence));
            } else if (hil_post_send == HilPostSendAction::RetryNormal) {
                ++hil_ack_state.next_scenario;
                hil_ack_state.active_key.reset();
                hil_ack_state.first_attempt = true;
                ESP_LOGI(kTag, "HIL RETRY_ACK_ACTION_COMMITTED session=%llu seq=%llu",
                         static_cast<unsigned long long>(processed->key.session_id),
                         static_cast<unsigned long long>(processed->key.sequence));
            }
        }
#endif
        ESP_LOGI(kTag,
                 "Processed session=%llu seq=%llu app_ack=%d ack_send=%s RSSI=%d CH=%u",
                 static_cast<unsigned long long>(processed->key.session_id),
                 static_cast<unsigned long long>(processed->key.sequence),
                 static_cast<int>(processed->ack), esp_err_to_name(sent),
                 frame.transport_rssi, static_cast<unsigned>(frame.channel));
    }
}

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

void set_control_plane_active(bool active) {
    g_control_plane_active.store(active, std::memory_order_release);
}

esp_err_t start_runtime_adapter() {
    esp_err_t result = nvs_flash_init();
    if (result != ESP_OK) return result;
    g_data_queue = xQueueCreateStatic(kDataQueueDepth, sizeof(ReceivedFrame),
                                      g_data_storage.data(), &g_data_queue_state);
    g_control_queue = xQueueCreateStatic(kControlQueueDepth, sizeof(ReceivedFrame),
                                         g_control_storage.data(), &g_control_queue_state);
    if (g_data_queue == nullptr || g_control_queue == nullptr) return ESP_ERR_NO_MEM;
    if ((result = initialize_wifi()) != ESP_OK) return result;
    if ((result = initialize_esp_now()) != ESP_OK) return result;
    if (xTaskCreate(owner_task, "gs_hub_owner", 8192, nullptr, 8, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

}  // namespace gs::hub::target
