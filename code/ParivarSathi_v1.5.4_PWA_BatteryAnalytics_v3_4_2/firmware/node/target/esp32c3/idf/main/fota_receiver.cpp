#include "fota_receiver.hpp"

#include "firmware/common/transport/fota_protocol.hpp"
#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"
#include "firmware/node/target/esp32c3/node_target_config.hpp"

#include "esp_log.h"
#include "esp_now.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace gs::node::target {
namespace {

constexpr char kTag[] = "gs_node_fota";

struct Context {
    bool active{false};
    std::uint32_t session_id{0};
    std::uint32_t expected_sequence{0};
    std::uint32_t expected_size{0};
    std::uint32_t expected_crc{0};
    std::uint32_t bytes_written{0};
    std::uint32_t running_crc{0};
    esp_ota_handle_t ota_handle{0};
    const esp_partition_t* partition{nullptr};
};

Context g_context;

void send_ack(std::uint32_t session_id, fota::Status status, std::uint32_t sequence) {
    fota::Ack ack{};
    ack.magic = fota::kMagic;
    ack.protocol_version = fota::kProtocolVersion;
    ack.type = fota::kAckFrameType;
    ack.session_id = session_id;
    ack.acknowledged_sequence = sequence;
    ack.next_sequence = g_context.expected_sequence;
    ack.status = static_cast<std::int32_t>(status);
    ack.bytes_written = g_context.bytes_written;
    const esp_err_t result = esp_now_send(kQualifiedHubMac.data(),
                                           reinterpret_cast<const std::uint8_t*>(&ack),
                                           sizeof(ack));
    if (result != ESP_OK) {
        ESP_LOGE(kTag, "FOTA ACK send failed: %s", esp_err_to_name(result));
    }
}

void reset(bool abort_ota) {
    if (abort_ota && g_context.active) {
        const esp_err_t result = esp_ota_abort(g_context.ota_handle);
        if (result != ESP_OK) ESP_LOGW(kTag, "esp_ota_abort failed: %s", esp_err_to_name(result));
    }
    g_context = {};
    set_control_plane_active(false);
}

void handle_begin(const fota::Packet& packet) {
    if (g_context.active && g_context.session_id == packet.session_id) {
        send_ack(packet.session_id, fota::Status::Ready, 0);
        return;
    }
    if (g_context.active) reset(true);

    const esp_partition_t* partition = esp_ota_get_next_update_partition(nullptr);
    if (partition == nullptr || packet.image_size == 0U ||
        packet.image_size > partition->size) {
        g_context.session_id = packet.session_id;
        send_ack(packet.session_id,
                 partition == nullptr ? fota::Status::OtaBegin : fota::Status::BadSize, 0);
        reset(false);
        return;
    }

    esp_ota_handle_t handle = 0;
    const esp_err_t result = esp_ota_begin(partition, packet.image_size, &handle);
    if (result != ESP_OK) {
        g_context.session_id = packet.session_id;
        send_ack(packet.session_id, fota::Status::OtaBegin, 0);
        reset(false);
        return;
    }

    g_context.active = true;
    g_context.session_id = packet.session_id;
    g_context.expected_size = packet.image_size;
    g_context.expected_crc = packet.image_crc32;
    g_context.running_crc = 0xFFFFFFFFU;
    g_context.ota_handle = handle;
    g_context.partition = partition;
    set_control_plane_active(true);
    ESP_LOGI(kTag, "FOTA BEGIN session=%lu target=%s size=%lu",
             static_cast<unsigned long>(packet.session_id), partition->label,
             static_cast<unsigned long>(packet.image_size));
    send_ack(packet.session_id, fota::Status::Ready, 0);
}

void handle_data(const fota::Packet& packet) {
    if (!g_context.active || packet.session_id != g_context.session_id) {
        send_ack(packet.session_id, fota::Status::BadSession, packet.sequence);
        return;
    }
    if (packet.sequence < g_context.expected_sequence) {
        send_ack(packet.session_id, fota::Status::Duplicate, packet.sequence);
        return;
    }
    if (packet.sequence != g_context.expected_sequence) {
        send_ack(packet.session_id, fota::Status::BadSequence, packet.sequence);
        return;
    }
    if (packet.payload_length == 0U || packet.payload_length > fota::kChunkBytes ||
        g_context.bytes_written + packet.payload_length > g_context.expected_size) {
        send_ack(packet.session_id, fota::Status::BadSize, packet.sequence);
        return;
    }
    if (fota::crc32(packet.payload, packet.payload_length) != packet.payload_crc32) {
        send_ack(packet.session_id, fota::Status::BadCrc, packet.sequence);
        return;
    }
    const esp_err_t result = esp_ota_write(g_context.ota_handle, packet.payload,
                                            packet.payload_length);
    if (result != ESP_OK) {
        send_ack(packet.session_id, fota::Status::OtaWrite, packet.sequence);
        reset(true);
        return;
    }
    g_context.running_crc = fota::crc32_update(g_context.running_crc, packet.payload,
                                                packet.payload_length);
    g_context.bytes_written += packet.payload_length;
    ++g_context.expected_sequence;
    if ((packet.sequence % 100U) == 0U ||
        g_context.bytes_written == g_context.expected_size) {
        ESP_LOGI(kTag, "FOTA RX %lu/%lu bytes",
                 static_cast<unsigned long>(g_context.bytes_written),
                 static_cast<unsigned long>(g_context.expected_size));
    }
    send_ack(packet.session_id, fota::Status::DataOk, packet.sequence);
}

void handle_end(const fota::Packet& packet) {
    if (!g_context.active || packet.session_id != g_context.session_id) {
        send_ack(packet.session_id, fota::Status::BadSession, packet.sequence);
        return;
    }
    if (g_context.bytes_written != g_context.expected_size) {
        send_ack(packet.session_id, fota::Status::BadSize, packet.sequence);
        return;
    }
    if ((g_context.running_crc ^ 0xFFFFFFFFU) != g_context.expected_crc) {
        send_ack(packet.session_id, fota::Status::BadCrc, packet.sequence);
        reset(true);
        return;
    }
    if (esp_ota_end(g_context.ota_handle) != ESP_OK) {
        send_ack(packet.session_id, fota::Status::OtaEnd, packet.sequence);
        reset(false);
        return;
    }
    if (esp_ota_set_boot_partition(g_context.partition) != ESP_OK) {
        send_ack(packet.session_id, fota::Status::SetBoot, packet.sequence);
        reset(false);
        return;
    }
    ESP_LOGI(kTag, "FOTA COMPLETE; next boot partition=%s", g_context.partition->label);
    send_ack(packet.session_id, fota::Status::Complete, packet.sequence);
    vTaskDelay(pdMS_TO_TICKS(1000));
    esp_restart();
}

void worker(void*) {
    ReceivedFrame frame;
    for (;;) {
        if (xQueueReceive(control_plane_queue(), &frame, portMAX_DELAY) != pdTRUE) continue;
        if (frame.size != sizeof(fota::Packet)) {
            ESP_LOGW(kTag, "Rejected FOTA frame length=%u", static_cast<unsigned>(frame.size));
            continue;
        }
        fota::Packet packet{};
        std::memcpy(&packet, frame.bytes.data(), sizeof(packet));
        if (packet.magic != fota::kMagic ||
            packet.protocol_version != fota::kProtocolVersion) continue;
        switch (static_cast<fota::MessageType>(packet.type)) {
            case fota::MessageType::Begin: handle_begin(packet); break;
            case fota::MessageType::Data: handle_data(packet); break;
            case fota::MessageType::End: handle_end(packet); break;
            case fota::MessageType::Abort:
                if (g_context.active && packet.session_id == g_context.session_id) reset(true);
                break;
            default:
                send_ack(packet.session_id, fota::Status::BadPacket, packet.sequence);
                break;
        }
    }
}

void validate_running_image(void*) {
    const esp_partition_t* running = esp_ota_get_running_partition();
    esp_ota_img_states_t state{};
    if (esp_ota_get_state_partition(running, &state) == ESP_OK &&
        state == ESP_OTA_IMG_PENDING_VERIFY) {
        ESP_LOGW(kTag, "OTA image pending validation");
        vTaskDelay(pdMS_TO_TICKS(5000));
        const esp_err_t result = esp_ota_mark_app_valid_cancel_rollback();
        if (result == ESP_OK) ESP_LOGI(kTag, "OTA image marked VALID");
        else ESP_LOGE(kTag, "Could not mark OTA image valid: %s", esp_err_to_name(result));
    }
    vTaskDelete(nullptr);
}

}  // namespace

esp_err_t start_fota_receiver() {
    if (control_plane_queue() == nullptr) return ESP_ERR_INVALID_STATE;
    if (xTaskCreate(worker, "gs_node_fota", 6144, nullptr, 7, nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    if (xTaskCreate(validate_running_image, "gs_ota_validate", 3072, nullptr, 6,
                    nullptr) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

}  // namespace gs::node::target
