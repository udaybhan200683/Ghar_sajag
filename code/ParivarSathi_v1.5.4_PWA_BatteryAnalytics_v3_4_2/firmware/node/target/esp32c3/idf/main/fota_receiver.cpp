#include "fota_receiver.hpp"

#include "firmware/node/fota/fota_receiver.hpp"
#include "firmware/node/target/esp32c3/node_runtime_adapter.hpp"
#include "firmware/node/target/esp32c3/node_target_config.hpp"

#include "esp_log.h"
#include "esp_now.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace gs::node::target {
namespace {

constexpr char kTag[] = "gs_node_fota";
constexpr TickType_t kControlReceivePoll = pdMS_TO_TICKS(1000);

std::uint64_t monotonic_ms() {
    return static_cast<std::uint64_t>(esp_timer_get_time() / 1000);
}

class EspIdfOtaWriter final : public fota_receiver::IOtaWriter {
public:
    std::size_t capacity() override {
        partition_ = esp_ota_get_next_update_partition(nullptr);
        return partition_ == nullptr ? 0U : partition_->size;
    }

    bool begin(std::size_t image_size) override {
        if (partition_ == nullptr) return false;
        const esp_err_t result = esp_ota_begin(partition_, image_size, &handle_);
        open_ = result == ESP_OK;
        if (!open_) ESP_LOGE(kTag, "esp_ota_begin failed: %s", esp_err_to_name(result));
        return open_;
    }

    bool write(const std::uint8_t* data, std::size_t size) override {
        const esp_err_t result = esp_ota_write(handle_, data, size);
        if (result != ESP_OK) ESP_LOGE(kTag, "esp_ota_write failed: %s", esp_err_to_name(result));
        return result == ESP_OK;
    }

    bool finalize() override {
        const esp_err_t result = esp_ota_end(handle_);
        open_ = false;
        if (result != ESP_OK) ESP_LOGE(kTag, "esp_ota_end failed: %s", esp_err_to_name(result));
        return result == ESP_OK;
    }

    bool commit_boot() override {
        const esp_err_t result = esp_ota_set_boot_partition(partition_);
        if (result != ESP_OK) {
            ESP_LOGE(kTag, "esp_ota_set_boot_partition failed: %s", esp_err_to_name(result));
        }
        return result == ESP_OK;
    }

    void abort() override {
        if (!open_) return;
        const esp_err_t result = esp_ota_abort(handle_);
        open_ = false;
        if (result != ESP_OK) ESP_LOGW(kTag, "esp_ota_abort failed: %s", esp_err_to_name(result));
    }

    const char* partition_label() const {
        return partition_ == nullptr ? "<none>" : partition_->label;
    }

private:
    esp_ota_handle_t handle_{0};
    const esp_partition_t* partition_{nullptr};
    bool open_{false};
};

class TargetCallbacks final : public fota_receiver::IReceiverCallbacks {
public:
    explicit TargetCallbacks(EspIdfOtaWriter& writer) : writer_(writer) {}

    void send_ack(const gs::fota::Ack& ack) override {
        const esp_err_t result = esp_now_send(
            kQualifiedHubMac.data(), reinterpret_cast<const std::uint8_t*>(&ack), sizeof(ack));
        if (result != ESP_OK) {
            ESP_LOGE(kTag, "FOTA ACK send failed: %s", esp_err_to_name(result));
        }
    }

    void set_maintenance(bool active) override {
        set_control_plane_active(active);
        ESP_LOGI(kTag, "FOTA maintenance %s", active ? "ACTIVE" : "INACTIVE");
    }

    void report_timeout() override {
        ESP_LOGE(kTag, "FOTA session timed out; resuming local data plane");
        report_control_plane_timeout();
    }

    void request_restart() override {
        ESP_LOGI(kTag, "FOTA COMPLETE; next boot partition=%s", writer_.partition_label());
        vTaskDelay(pdMS_TO_TICKS(1000));
        esp_restart();
    }

private:
    EspIdfOtaWriter& writer_;
};

EspIdfOtaWriter g_writer;
TargetCallbacks g_callbacks(g_writer);
fota_receiver::Receiver g_receiver(g_writer, g_callbacks);

void worker(void*) {
    ReceivedFrame frame;
    for (;;) {
        const bool received =
            xQueueReceive(control_plane_queue(), &frame, kControlReceivePoll) == pdTRUE;
        g_receiver.poll(monotonic_ms());
        if (!received) continue;
        if (frame.size != sizeof(gs::fota::Packet)) {
            ESP_LOGW(kTag, "Rejected FOTA frame length=%u", static_cast<unsigned>(frame.size));
            continue;
        }
        gs::fota::Packet packet{};
        std::memcpy(&packet, frame.bytes.data(), sizeof(packet));
        (void)g_receiver.process(packet, monotonic_ms());
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
