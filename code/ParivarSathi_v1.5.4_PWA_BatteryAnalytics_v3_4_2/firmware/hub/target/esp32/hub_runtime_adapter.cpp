#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/target/esp32/nvs_journal_slot_store.hpp"
#include "firmware/hub/target/esp32/hub_target_config.hpp"

#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include <array>
#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <memory>
#include <map>
#include <vector>

namespace gs::hub::target {
namespace {

constexpr char kTag[] = "gs_hub_runtime";
constexpr UBaseType_t kDataQueueDepth = 16U;
constexpr UBaseType_t kControlQueueDepth = 8U;
constexpr UBaseType_t kHealthQueueDepth = 1U;
constexpr UBaseType_t kSecurityQueueDepth = 8U;

StaticQueue_t g_data_queue_state{};
StaticQueue_t g_control_queue_state{};
StaticQueue_t g_health_queue_state{};
StaticQueue_t g_security_queue_state{};
StaticQueue_t g_request_queue_state{};
StaticQueue_t g_security_send_queue_state{};
alignas(ReceivedFrame) std::array<std::uint8_t, kDataQueueDepth * sizeof(ReceivedFrame)> g_data_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kControlQueueDepth * sizeof(ReceivedFrame)> g_control_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kHealthQueueDepth * sizeof(ReceivedFrame)> g_health_storage{};
alignas(ReceivedFrame) std::array<std::uint8_t, kSecurityQueueDepth * sizeof(ReceivedFrame)> g_security_storage{};
alignas(HubSecurityLink::ExpectedNode*) std::array<std::uint8_t, sizeof(HubSecurityLink::ExpectedNode*)> g_request_storage{};
alignas(bool) std::array<std::uint8_t, sizeof(bool)> g_security_send_storage{};
QueueHandle_t g_data_queue = nullptr;
QueueHandle_t g_control_queue = nullptr;
QueueHandle_t g_health_queue = nullptr;
QueueHandle_t g_security_queue = nullptr;
QueueHandle_t g_request_queue = nullptr;
QueueHandle_t g_security_send_queue = nullptr;
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
    if (info == nullptr || data == nullptr ||
        length <= 0 || static_cast<std::size_t>(length) > kTargetEspNowPayloadMax) {
        return;
    }
#if GS_HIL_BUILD
    if (!from_qualified_node(info->src_addr)) return;
#endif

    const auto frame_class = transport::classify_frame(data, static_cast<std::size_t>(length));
    QueueHandle_t destination = nullptr;
    if (length >= 3 && data[0] == 0x47 && data[1] == 0x53 && data[2] == 1) {
        destination = g_security_queue;
    } else if (length >= 3 && data[0] == 0x47 && data[1] == 0x53 && data[2] == 2) {
        destination = g_data_queue;
    }
#if GS_HIL_BUILD
    else if (frame_class == transport::FrameClass::NodeMessage &&
        static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_data_queue;
    }
    else if (frame_class == transport::FrameClass::ControlFota) {
        destination = g_control_queue;
    }
    else if (frame_class == transport::FrameClass::NodeHealth &&
               static_cast<std::size_t>(length) <= transport::kMaxFrameBytes) {
        destination = g_health_queue;
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

#if ESP_IDF_VERSION_MAJOR >= 6
void send_callback(const esp_now_send_info_t*, esp_now_send_status_t status) {
#else
void send_callback(const std::uint8_t*, esp_now_send_status_t status) {
#endif
    if (g_security_send_queue != nullptr) {
        const bool delivered = status == ESP_NOW_SEND_SUCCESS;
        (void)xQueueOverwrite(g_security_send_queue, &delivered);
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
#if GS_HIL_BUILD
    if (actual_mac != kQualifiedHubMac) {
        ESP_LOGE(kTag, "STA MAC does not match qualified Hub");
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
    std::memcpy(peer.peer_addr, kQualifiedNodeMac.data(), kQualifiedNodeMac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;  // Production peer key management remains open.
    if (!esp_now_is_peer_exist(kQualifiedNodeMac.data())) {
        result = esp_now_add_peer(&peer);
    }
#endif
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

#if !GS_HIL_BUILD
bool add_runtime_peer(const HubSecurityLink::Mac& mac) {
    if (esp_now_is_peer_exist(mac.data())) return true;
    esp_now_peer_info_t peer{};
    std::memcpy(peer.peer_addr, mac.data(), mac.size());
    peer.channel = 0;
    peer.ifidx = WIFI_IF_STA;
    // Runtime frames carry their own authenticated encryption. Native
    // encrypted-peer capacity is below the installed-node requirement.
    peer.encrypt = false;
    return esp_now_add_peer(&peer) == ESP_OK;
}

bool send_security_message(const HubSecurityLink::Outbound& outbound) {
    if (!add_runtime_peer(outbound.destination)) return false;
    std::vector<security::wire::Packet> packets;
    std::uint32_t transaction = esp_random();
    if (transaction == 0) transaction = 1;
    if (!security::wire::fragment(outbound.message, transaction, packets)) return false;
    for (const auto& packet : packets) {
        (void)xQueueReset(g_security_send_queue);
        if (esp_now_send(outbound.destination.data(), packet.bytes.data(),
                         packet.size) != ESP_OK) return false;
        bool delivered = false;
        if (xQueueReceive(g_security_send_queue, &delivered,
                          pdMS_TO_TICKS(1000)) != pdTRUE || !delivered) return false;
    }
    return true;
}

void secure_owner_task(void*) {
    HubSecurityLink security_link;
    HubSecurityLink::Mac physical_mac{};
    if (esp_wifi_get_mac(WIFI_IF_STA, physical_mac.data()) != ESP_OK ||
        !security_link.initialize(physical_mac)) {
        ESP_LOGE(kTag, "Hub security bootstrap failed closed");
        vTaskDelete(nullptr);
        return;
    }
    for (const auto& mac : security_link.enrolled_macs()) {
        if (!add_runtime_peer(mac)) {
            ESP_LOGE(kTag, "Could not restore enrolled ESP-NOW peer");
            vTaskDelete(nullptr);
            return;
        }
    }
    // The dedicated partition contains a bounded append-only encrypted journal.
    // Do not start authenticated event admission if restore or persistence fails.
    NvsJournalSlotStore journal_store;
    HubRuntime runtime(32, 128);
    if (!journal_store.initialize() ||
        !security_link.attach_event_journal(runtime.journal(), journal_store) ||
        !runtime.restore_from_journal()) {
        ESP_LOGE(kTag, "Hub durable event journal unavailable; refusing event admission");
        vTaskDelete(nullptr);
        return;
    }
    std::map<HubSecurityLink::Mac, std::uint64_t> authorized;
    ESP_LOGI(kTag, "Authenticated Hub owner started enrolled=%u",
             static_cast<unsigned>(security_link.enrolled_macs().size()));
    for (;;) {
        const auto now_ms = static_cast<std::uint64_t>(esp_timer_get_time() / 1000);
        if (const auto expired = security_link.expire_candidate(now_ms)) {
            (void)esp_now_del_peer(expired->data());
            ESP_LOGI(kTag, "Expired uncommissioned peer removed");
        }
        if (g_control_plane_active.load(std::memory_order_acquire)) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        HubSecurityLink::ExpectedNode* requested = nullptr;
        if (xQueueReceive(g_request_queue, &requested, 0) == pdTRUE) {
            std::unique_ptr<HubSecurityLink::ExpectedNode> exact(requested);
            const auto outbound = security_link.begin_commissioning(
                *exact, static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
            if (outbound && send_security_message(*outbound)) {
                ESP_LOGI(kTag, "Exact-node commissioning offer sent");
            } else {
                ESP_LOGW(kTag, "Exact-node commissioning request rejected");
            }
            std::fill(exact->installer_code.begin(), exact->installer_code.end(), 0);
        }
        ReceivedFrame control;
        if (xQueueReceive(g_security_queue, &control, pdMS_TO_TICKS(20)) == pdTRUE) {
            const auto outbound = security_link.accept(control.source_mac,
                control.bytes.data(), control.size,
                static_cast<std::uint64_t>(esp_timer_get_time() / 1000));
            if (outbound && !send_security_message(*outbound))
                ESP_LOGW(kTag, "Authenticated control reply delivery failed");
            if (const auto* node = security_link.ready_node(control.source_mac)) {
                const auto prior = authorized.find(control.source_mac);
                if (prior == authorized.end() || prior->second != node->last_session) {
                    runtime.authorize_node(node->logical_id, node->last_session, true);
                    authorized[control.source_mac] = node->last_session;
                    ESP_LOGI(kTag, "Authenticated rejoin logical=%s session=%llu",
                             node->logical_id.c_str(),
                             static_cast<unsigned long long>(node->last_session));
                }
            }
        }
        ReceivedFrame frame;
        if (xQueueReceive(g_data_queue, &frame, 0) != pdTRUE) continue;
        const auto* node = security_link.ready_node(frame.source_mac);
        auto* frames = security_link.frames_for(frame.source_mac);
        if (node == nullptr || frames == nullptr) continue;
        security::SecureFrame protected_frame;
        protected_frame.size = frame.size;
        std::copy_n(frame.bytes.data(), frame.size, protected_frame.bytes.data());
        transport::EncodedFrame plain;
        if (!frames->open(security::RuntimeDirection::Uplink,
                          protected_frame, plain)) {
            ESP_LOGW(kTag, "Rejected unauthenticated/replayed runtime frame");
            continue;
        }
        const auto classification = transport::classify_frame(plain.bytes.data(), plain.size);
        if (classification == transport::FrameClass::NodeHealth) {
            const auto health = transport::decode_node_health(plain.bytes.data(), plain.size);
            if (health && health.value->node_id == node->logical_id &&
                health.value->session_id == node->last_session) {
                ESP_LOGI(kTag, "Authenticated NodeHealth logical=%s session=%llu heap=%u min_heap=%u retained=%u RSSI=%d",
                         node->logical_id.c_str(),
                         static_cast<unsigned long long>(node->last_session),
                         static_cast<unsigned>(health.value->free_heap),
                         static_cast<unsigned>(health.value->minimum_free_heap),
                         static_cast<unsigned>(health.value->retained_count),
                         frame.transport_rssi);
            }
            continue;
        }
        if (classification != transport::FrameClass::NodeMessage) continue;
        const auto decoded = transport::decode_node_message(plain.bytes.data(), plain.size);
        if (!decoded || decoded.value->node_id != node->logical_id) continue;
        constexpr EpochSeconds hub_received_at = 0;  // No trusted clock yet.
        if (!runtime.authenticated_radio_message_callback(
                *decoded.value, node->logical_id, node->device_id,
                node->last_session, hub_received_at)) continue;
        const auto processed = runtime.run_state_once();
        if (!processed) continue;
        const auto ack = make_node_ack(processed->key, processed->ack,
                                       hub_received_at, ack_reason(*processed));
        const auto encoded = transport::encode_node_ack(ack);
        security::SecureFrame protected_ack;
        if (!encoded || !frames->seal(security::RuntimeDirection::Downlink,
                                      encoded.frame, protected_ack)) continue;
        const auto sent = esp_now_send(frame.source_mac.data(),
                                       protected_ack.bytes.data(), protected_ack.size);
        ESP_LOGI(kTag, "Authenticated event logical=%s seq=%llu ack=%d send=%s",
                 node->logical_id.c_str(),
                 static_cast<unsigned long long>(processed->key.sequence),
                 static_cast<int>(processed->ack), esp_err_to_name(sent));
    }
}
#endif

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

void set_control_plane_active(bool active) {
    g_control_plane_active.store(active, std::memory_order_release);
}

bool request_node_commissioning(HubSecurityLink::ExpectedNode exact) {
    if (g_request_queue == nullptr) return false;
    auto candidate = std::make_unique<HubSecurityLink::ExpectedNode>(std::move(exact));
    auto* pointer = candidate.get();
    if (xQueueSend(g_request_queue, &pointer, 0) != pdTRUE) return false;
    candidate.release();
    return true;
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
    g_security_queue = xQueueCreateStatic(kSecurityQueueDepth, sizeof(ReceivedFrame),
                                          g_security_storage.data(), &g_security_queue_state);
    g_request_queue = xQueueCreateStatic(1U, sizeof(HubSecurityLink::ExpectedNode*),
                                         g_request_storage.data(), &g_request_queue_state);
    g_security_send_queue = xQueueCreateStatic(1U, sizeof(bool),
        g_security_send_storage.data(), &g_security_send_queue_state);
    if (g_data_queue == nullptr || g_control_queue == nullptr || g_health_queue == nullptr ||
        g_security_queue == nullptr || g_request_queue == nullptr ||
        g_security_send_queue == nullptr) {
        return ESP_ERR_NO_MEM;
    }
    if ((result = initialize_wifi()) != ESP_OK) return result;
    if ((result = initialize_esp_now()) != ESP_OK) return result;
#if GS_HIL_BUILD
    if (xTaskCreate(owner_task, "gs_hub_owner", 8192, nullptr, 8, nullptr) != pdPASS) {
#else
    if (xTaskCreate(secure_owner_task, "gs_hub_owner", 16384, nullptr, 8, nullptr) != pdPASS) {
#endif
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

}  // namespace gs::hub::target
