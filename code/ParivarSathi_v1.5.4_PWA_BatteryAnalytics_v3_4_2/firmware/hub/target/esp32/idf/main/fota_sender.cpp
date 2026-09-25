#include "fota_sender.hpp"

#include "firmware/common/transport/fota_protocol.hpp"
#include "firmware/common/transport/fota_secure_wire.hpp"
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
#include <memory>
#include <string>

#if !GS_HIL_BUILD
#include "psa/crypto.h"
#endif

#if GS_HIL_BUILD
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
#if GS_HIL_BUILD
    if (xTaskCreate(trigger_task, "gs_fota_trigger", 3072, nullptr, 4, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
#endif
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
#else
namespace gs::hub::target {
namespace {
constexpr char kTag[] = "gs_hub_fota";
constexpr std::uint32_t kAckTimeoutMs = 1500;
constexpr unsigned kMaximumRetries = 8;
extern const std::uint8_t node_firmware_start[] asm("_binary_node_firmware_bin_start");
extern const std::uint8_t node_firmware_end[] asm("_binary_node_firmware_bin_end");
QueueHandle_t g_start_queue = nullptr;

bool owner_command(FotaOwnerAction action, const FotaStartRequest& target,
                   const gs::fota::secure_wire::Message& message,
                   std::uint64_t session, FotaOwnerResult& result) {
    FotaOwnerCommand command;
    command.action = action;
    command.physical_device_id = target.physical_device_id;
    command.message = message;
    return submit_fota_owner_command(std::move(command), result) &&
           (action == FotaOwnerAction::Abort ||
            (result.authenticated_session != 0 &&
             (session == 0 || result.authenticated_session == session)));
}

bool send_with_retry(const FotaStartRequest& target,
                     const gs::fota::secure_wire::Message& message,
                     std::uint64_t session, gs::fota::Status expected,
                     bool allow_duplicate) {
    for (unsigned attempt = 0; attempt < kMaximumRetries; ++attempt) {
        FotaOwnerResult result;
        if (!owner_command(FotaOwnerAction::Send, target, message, session, result))
            return false;
        const TickType_t started = xTaskGetTickCount();
        const TickType_t timeout = pdMS_TO_TICKS(kAckTimeoutMs);
        while (xTaskGetTickCount() - started < timeout) {
            const auto elapsed = xTaskGetTickCount() - started;
            FotaOwnerAck verified;
            if (!wait_fota_owner_ack(verified,
                    static_cast<std::uint32_t>(pdTICKS_TO_MS(timeout - elapsed)))) break;
            if (verified.aborted) return false;
            const auto& ack = verified.message;
            if (ack.type != gs::fota::secure_wire::Type::Ack ||
                ack.transfer_id != message.transfer_id ||
                ack.index != message.index) continue;
            return ack.ack_status == expected ||
                   (allow_duplicate && ack.ack_status == gs::fota::Status::Duplicate);
        }
    }
    return false;
}

bool perform_update(const FotaStartRequest& target) {
    using gs::fota::secure_wire::Message;
    using gs::fota::secure_wire::Type;
    const auto* image = node_firmware_start;
    const auto size = static_cast<std::size_t>(node_firmware_end - node_firmware_start);
    if (size == 0 || size > std::numeric_limits<std::uint32_t>::max() ||
        target.board.empty() || target.board.size() > gs::fota::secure_wire::kMaxClaimBytes ||
        target.version.empty() || target.version.size() > gs::fota::secure_wire::kMaxClaimBytes)
        return false;
    Message begin;
    begin.type = Type::Begin;
    begin.transfer_id = esp_random();
    if (begin.transfer_id == 0) return false;
    begin.image_size = static_cast<std::uint32_t>(size);
    begin.image_crc32 = gs::fota::crc32(image, size);
    std::size_t hash_length = 0;
    if (psa_crypto_init() != PSA_SUCCESS ||
        psa_hash_compute(PSA_ALG_SHA_256, image, size,
            begin.image_sha256.data(), begin.image_sha256.size(),
            &hash_length) != PSA_SUCCESS ||
        hash_length != begin.image_sha256.size()) return false;
    begin.board_size = static_cast<std::uint8_t>(target.board.size());
    begin.version_size = static_cast<std::uint8_t>(target.version.size());
    std::copy(target.board.begin(), target.board.end(), begin.board.begin());
    std::copy(target.version.begin(), target.version.end(), begin.version.begin());
    FotaOwnerResult start_result;
    if (!owner_command(FotaOwnerAction::Begin, target, begin, 0, start_result))
        return false;
    const auto session = start_result.authenticated_session;
    const auto abort = [&]() {
        Message stop;
        stop.type = Type::Abort;
        stop.transfer_id = begin.transfer_id;
        FotaOwnerResult ignored;
        (void)owner_command(FotaOwnerAction::Send, target, stop, session, ignored);
        (void)owner_command(FotaOwnerAction::Abort, target, stop, 0, ignored);
    };
    if (!send_with_retry(target, begin, session, gs::fota::Status::Ready, false)) {
        abort();
        return false;
    }
    std::size_t offset = 0;
    std::uint32_t index = 0;
    while (offset < size) {
        Message data;
        data.type = Type::Data;
        data.transfer_id = begin.transfer_id;
        data.index = index;
        data.data_size = static_cast<std::uint16_t>(std::min(
            gs::fota::secure_wire::kMaxChunkBytes, size - offset));
        std::copy_n(image + offset, data.data_size, data.data.begin());
        if (!send_with_retry(target, data, session, gs::fota::Status::DataOk, true)) {
            abort();
            return false;
        }
        offset += data.data_size;
        ++index;
    }
    Message end;
    end.type = Type::End;
    end.transfer_id = begin.transfer_id;
    end.index = index;
    const bool complete = send_with_retry(target, end, session,
                                          gs::fota::Status::Complete, false);
    FotaOwnerResult ignored;
    (void)owner_command(FotaOwnerAction::Abort, target, end, 0, ignored);
    return complete;
}

void sender_task(void*) {
    FotaStartRequest* request = nullptr;
    for (;;) {
        if (xQueueReceive(g_start_queue, &request, portMAX_DELAY) != pdTRUE) continue;
        std::unique_ptr<FotaStartRequest> owned(request);
        const bool passed = perform_update(*owned);
        ESP_LOGI(kTag, "Authenticated FOTA sender result=%s", passed ? "TRANSFER_COMPLETE" : "FAIL");
    }
}
}  // namespace

esp_err_t start_fota_sender() {
    g_start_queue = xQueueCreate(1U, sizeof(FotaStartRequest*));
    if (g_start_queue == nullptr) return ESP_ERR_NO_MEM;
    return xTaskCreate(sender_task, "gs_fota_sender", 6144, nullptr, 8, nullptr) == pdPASS
        ? ESP_OK : ESP_ERR_NO_MEM;
}

bool request_authenticated_fota(FotaStartRequest request) {
    if (g_start_queue == nullptr || request.physical_device_id.empty() ||
        request.physical_device_id.size() > 64) return false;
    auto owned = std::make_unique<FotaStartRequest>(std::move(request));
    auto* pointer = owned.get();
    if (xQueueSend(g_start_queue, &pointer, 0) != pdTRUE) return false;
    owned.release();
    return true;
}
}  // namespace gs::hub::target
#endif
