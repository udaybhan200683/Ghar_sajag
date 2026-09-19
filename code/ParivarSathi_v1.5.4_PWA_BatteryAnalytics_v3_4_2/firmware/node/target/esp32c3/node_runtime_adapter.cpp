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
    if (g_send_queue == nullptr) return;
    const SendResult result{status == ESP_NOW_SEND_SUCCESS};
    (void)xQueueSend(g_send_queue, &result, 0);
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
    QualifiedInput pir(EventKind::Motion, std::nullopt, kPirDebounceMs,
                       kPirMinimumRetriggerMs);
    std::optional<EventKey> in_flight;
    Milliseconds sent_at_ms = 0;
    Milliseconds led_off_at_ms = 0;

    ESP_LOGI(kTag, "NodeRuntime owner started session=%llu channel=%u tx_power_qdbm=%d",
             static_cast<unsigned long long>(g_session_id),
             static_cast<unsigned>(kEspNowChannel),
             kTxPowerQuarterDbm);
    vTaskDelay(pdMS_TO_TICKS(kPirStabilizationMs));
    ESP_LOGI(kTag, "PIR ready on GPIO%d", kPirGpio);

    for (;;) {
        const Milliseconds now = monotonic_ms();
        const auto ack_drops = g_ack_queue_drops.exchange(0U, std::memory_order_relaxed);
        const auto control_drops = g_control_queue_drops.exchange(0U, std::memory_order_relaxed);
        if (ack_drops != 0U || control_drops != 0U) {
            ESP_LOGW(kTag, "Callback queue drops ACK=%u CONTROL=%u",
                     static_cast<unsigned>(ack_drops), static_cast<unsigned>(control_drops));
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
            ESP_LOGI(kTag, "Application ACK session=%llu seq=%llu class=%d retired=%d",
                     static_cast<unsigned long long>(key.session_id),
                     static_cast<unsigned long long>(key.sequence),
                     static_cast<int>(decoded.value->ack_type), retired);
        }

        SendResult send_result;
        while (xQueueReceive(g_send_queue, &send_result, 0) == pdTRUE) {
            if (in_flight) {
                runtime.transport_result(*in_flight, send_result.accepted_by_radio, now);
                ESP_LOGI(kTag, "MAC result session=%llu seq=%llu accepted=%d",
                         static_cast<unsigned long long>(in_flight->session_id),
                         static_cast<unsigned long long>(in_flight->sequence),
                         send_result.accepted_by_radio);
                in_flight.reset();
            }
        }
        if (in_flight && now - sent_at_ms >= kSendCallbackTimeoutMs) {
            runtime.transport_result(*in_flight, false, now);
            ESP_LOGW(kTag, "MAC callback timeout session=%llu seq=%llu",
                     static_cast<unsigned long long>(in_flight->session_id),
                     static_cast<unsigned long long>(in_flight->sequence));
            in_flight.reset();
        }

        const bool raw_pir = gpio_get_level(static_cast<gpio_num_t>(kPirGpio)) != 0;
        const auto sensed = pir.sample(raw_pir, now);
        if (sensed) {
            const auto key = runtime.record(*sensed, kLocation, now, 0, 24U * 60U * 60U,
                                            0, false, SensorType::Pir, 0);
            if (key) {
                ESP_LOGI(kTag, "PIR -> NodeRuntime session=%llu seq=%llu",
                         static_cast<unsigned long long>(key->session_id),
                         static_cast<unsigned long long>(key->sequence));
                (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio), kLedActiveLow ? 0 : 1);
                led_off_at_ms = now + 200;
            }
        }
        if (led_off_at_ms != 0 && now >= led_off_at_ms) {
            (void)gpio_set_level(static_cast<gpio_num_t>(kLedGpio), kLedActiveLow ? 1 : 0);
            led_off_at_ms = 0;
        }

        if (!in_flight) {
            const auto message = runtime.next_message(now);
            if (message) {
                const EventKey key{message->node_id, message->session_id,
                                   message->sequence_number};
                const auto encoded = transport::encode_node_message(*message);
                if (!encoded) {
                    ESP_LOGE(kTag, "NodeMessage encode failed error=%d", static_cast<int>(encoded.error));
                    runtime.transport_result(key, false, now);
                } else {
                    const esp_err_t sent = esp_now_send(kQualifiedHubMac.data(),
                                                        encoded.frame.bytes.data(),
                                                        encoded.frame.size);
                    if (sent == ESP_OK) {
                        in_flight = key;
                        sent_at_ms = now;
                        ESP_LOGI(kTag, "NodeMessage sent session=%llu seq=%llu bytes=%u",
                                 static_cast<unsigned long long>(key.session_id),
                                 static_cast<unsigned long long>(key.sequence),
                                 static_cast<unsigned>(encoded.frame.size));
                    } else {
                        runtime.transport_result(key, false, now);
                        ESP_LOGW(kTag, "esp_now_send failed error=%s", esp_err_to_name(sent));
                    }
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(kPirPollMs));
    }
}

}  // namespace

QueueHandle_t control_plane_queue() {
    return g_control_queue;
}

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
