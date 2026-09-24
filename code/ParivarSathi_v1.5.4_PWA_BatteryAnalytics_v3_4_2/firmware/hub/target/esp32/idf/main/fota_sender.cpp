#include "fota_sender.hpp"

#include "firmware/common/transport/fota_protocol.hpp"
#include "firmware/hub/target/esp32/hub_runtime_adapter.hpp"
#include "firmware/hub/target/esp32/hub_target_config.hpp"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_now.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace gs::hub::target {
namespace {

constexpr char kTag[] = "gs_hub_fota";
constexpr gpio_num_t kTriggerGpio = GPIO_NUM_0;
constexpr std::uint32_t kTriggerHoldMs = 2000U;
constexpr std::uint32_t kTriggerPollMs = 50U;
constexpr std::uint32_t kAckTimeoutMs = 1500U;
constexpr unsigned kMaximumRetries = 8U;

extern const std::uint8_t node_firmware_start[]
    asm("_binary_node_firmware_bin_start");
extern const std::uint8_t node_firmware_end[]
    asm("_binary_node_firmware_bin_end");

QueueHandle_t g_start_queue = nullptr;

bool decode_ack(const ReceivedFrame& frame, fota::Ack& ack) {
    if (frame.source_mac != kQualifiedNodeMac || frame.size != sizeof(ack)) return false;
    std::memcpy(&ack, frame.bytes.data(), sizeof(ack));
    return ack.magic == fota::kMagic && ack.protocol_version == fota::kProtocolVersion &&
           ack.type == fota::kAckFrameType;
}

void clear_ack_queue() {
    ReceivedFrame stale;
    while (xQueueReceive(control_plane_queue(), &stale, 0) == pdTRUE) {}
}

bool wait_for_ack(std::uint32_t session, std::uint32_t sequence,
                  fota::Status expected, bool allow_duplicate) {
    const TickType_t started = xTaskGetTickCount();
    const TickType_t timeout = pdMS_TO_TICKS(kAckTimeoutMs);
    while (xTaskGetTickCount() - started < timeout) {
        const TickType_t remaining = timeout - (xTaskGetTickCount() - started);
        ReceivedFrame frame;
        if (xQueueReceive(control_plane_queue(), &frame, remaining) != pdTRUE) return false;
        fota::Ack ack{};
        if (!decode_ack(frame, ack) || ack.session_id != session ||
            ack.acknowledged_sequence != sequence) continue;
        const auto status = static_cast<fota::Status>(ack.status);
        if (status == expected || (allow_duplicate && status == fota::Status::Duplicate)) {
            return true;
        }
        ESP_LOGE(kTag, "FOTA rejected status=%ld seq=%lu next=%lu bytes=%lu",
                 static_cast<long>(ack.status), static_cast<unsigned long>(sequence),
                 static_cast<unsigned long>(ack.next_sequence),
                 static_cast<unsigned long>(ack.bytes_written));
        return false;
    }
    return false;
}

bool send_with_retry(const fota::Packet& packet, fota::Status expected,
                     bool allow_duplicate) {
    for (unsigned attempt = 1; attempt <= kMaximumRetries; ++attempt) {
        clear_ack_queue();
        const esp_err_t result = esp_now_send(
            kQualifiedNodeMac.data(), reinterpret_cast<const std::uint8_t*>(&packet),
            sizeof(packet));
        if (result == ESP_OK &&
            wait_for_ack(packet.session_id, packet.sequence, expected, allow_duplicate)) {
            return true;
        }
        ESP_LOGW(kTag, "FOTA retry %u/%u seq=%lu", attempt, kMaximumRetries,
                 static_cast<unsigned long>(packet.sequence));
    }
    return false;
}

void send_abort(std::uint32_t session, std::uint32_t sequence) {
    fota::Packet packet{};
    packet.magic = fota::kMagic;
    packet.protocol_version = fota::kProtocolVersion;
    packet.type = static_cast<std::uint8_t>(fota::MessageType::Abort);
    packet.session_id = session;
    packet.sequence = sequence;
    (void)esp_now_send(kQualifiedNodeMac.data(),
                       reinterpret_cast<const std::uint8_t*>(&packet), sizeof(packet));
}

bool perform_update() {
    const std::uint8_t* image = node_firmware_start;
    const std::size_t image_size = static_cast<std::size_t>(node_firmware_end - node_firmware_start);
    if (image_size == 0U || image_size > std::numeric_limits<std::uint32_t>::max()) {
        ESP_LOGE(kTag, "Embedded C3 image size is invalid");
        return false;
    }
    const std::uint32_t image_crc = fota::crc32(image, image_size);
    std::uint32_t session = esp_random();
    if (session == 0U) session = 1U;
    const auto chunks = static_cast<std::uint32_t>(
        (image_size + fota::kChunkBytes - 1U) / fota::kChunkBytes);

    ESP_LOGI(kTag, "NODE FOTA START size=%lu crc=0x%08lX chunks=%lu session=%lu",
             static_cast<unsigned long>(image_size), static_cast<unsigned long>(image_crc),
             static_cast<unsigned long>(chunks), static_cast<unsigned long>(session));

    fota::Packet begin{};
    begin.magic = fota::kMagic;
    begin.protocol_version = fota::kProtocolVersion;
    begin.type = static_cast<std::uint8_t>(fota::MessageType::Begin);
    begin.session_id = session;
    begin.image_size = static_cast<std::uint32_t>(image_size);
    begin.image_crc32 = image_crc;
    if (!send_with_retry(begin, fota::Status::Ready, false)) {
        send_abort(session, 0);
        return false;
    }

    std::size_t offset = 0;
    for (std::uint32_t sequence = 0; sequence < chunks; ++sequence) {
        const std::size_t length = std::min(fota::kChunkBytes, image_size - offset);
        fota::Packet packet{};
        packet.magic = fota::kMagic;
        packet.protocol_version = fota::kProtocolVersion;
        packet.type = static_cast<std::uint8_t>(fota::MessageType::Data);
        packet.session_id = session;
        packet.sequence = sequence;
        packet.image_size = static_cast<std::uint32_t>(image_size);
        packet.image_crc32 = image_crc;
        packet.payload_length = static_cast<std::uint16_t>(length);
        std::memcpy(packet.payload, image + offset, length);
        packet.payload_crc32 = fota::crc32(packet.payload, length);
        if (!send_with_retry(packet, fota::Status::DataOk, true)) {
            send_abort(session, sequence);
            return false;
        }
        offset += length;
        if ((sequence % 100U) == 0U || offset == image_size) {
            ESP_LOGI(kTag, "FOTA TX %lu/%lu bytes chunk=%lu/%lu",
                     static_cast<unsigned long>(offset), static_cast<unsigned long>(image_size),
                     static_cast<unsigned long>(sequence + 1U),
                     static_cast<unsigned long>(chunks));
        }
    }

    fota::Packet end{};
    end.magic = fota::kMagic;
    end.protocol_version = fota::kProtocolVersion;
    end.type = static_cast<std::uint8_t>(fota::MessageType::End);
    end.session_id = session;
    end.sequence = chunks;
    end.image_size = static_cast<std::uint32_t>(image_size);
    end.image_crc32 = image_crc;
    return send_with_retry(end, fota::Status::Complete, false);
}

void sender_task(void*) {
    std::uint8_t command = 0;
    for (;;) {
        if (xQueueReceive(g_start_queue, &command, portMAX_DELAY) != pdTRUE) continue;
        set_control_plane_active(true);
        const bool passed = perform_update();
        set_control_plane_active(false);
        ESP_LOGI(kTag, "FOTA RESULT: %s", passed ? "PASS" : "FAIL");
    }
}

void trigger_task(void*) {
    std::uint32_t held_ms = 0;
    bool triggered = false;
    ESP_LOGI(kTag, "Hold BOOT for %lu ms to start C3 FOTA",
             static_cast<unsigned long>(kTriggerHoldMs));
    for (;;) {
        if (gpio_get_level(kTriggerGpio) == 0) {
            if (!triggered) {
                held_ms += kTriggerPollMs;
                if (held_ms >= kTriggerHoldMs) {
                    const std::uint8_t command = 1U;
                    if (xQueueSend(g_start_queue, &command, 0) == pdTRUE) {
                        ESP_LOGW(kTag, "BOOT long-press: C3 FOTA requested");
                    }
                    triggered = true;
                }
            }
        } else {
            held_ms = 0;
            triggered = false;
        }
        vTaskDelay(pdMS_TO_TICKS(kTriggerPollMs));
    }
}

}  // namespace

esp_err_t start_fota_sender() {
    if (control_plane_queue() == nullptr) return ESP_ERR_INVALID_STATE;
    gpio_config_t trigger{};
    trigger.pin_bit_mask = 1ULL << kTriggerGpio;
    trigger.mode = GPIO_MODE_INPUT;
    trigger.pull_up_en = GPIO_PULLUP_ENABLE;
    trigger.pull_down_en = GPIO_PULLDOWN_DISABLE;
    trigger.intr_type = GPIO_INTR_DISABLE;
    esp_err_t result = gpio_config(&trigger);
    if (result != ESP_OK) return result;
    g_start_queue = xQueueCreate(1U, sizeof(std::uint8_t));
    if (g_start_queue == nullptr) return ESP_ERR_NO_MEM;
    if (xTaskCreate(sender_task, "gs_fota_sender", 6144, nullptr, 8, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    if (xTaskCreate(trigger_task, "gs_fota_trigger", 3072, nullptr, 4, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(kTag, "Embedded C3 image=%lu bytes",
             static_cast<unsigned long>(node_firmware_end - node_firmware_start));
    return ESP_OK;
}

#if GS_HIL_BUILD
bool hil_request_fota() {
    if (g_start_queue == nullptr) return false;
    const std::uint8_t command = 1U;
    return xQueueSend(g_start_queue, &command, 0) == pdTRUE;
}
#endif

}  // namespace gs::hub::target
