#include "firmware/node/target/esp32c3/nvs_session_provider.hpp"

#include "firmware/common/transport/session_id.hpp"

#include "nvs.h"

namespace gs::node::target {
namespace {

class NvsSessionCounterStore final : public transport::SessionCounterStore {
public:
    ~NvsSessionCounterStore() override {
        if (handle_ != 0) nvs_close(handle_);
    }

    bool load(std::uint64_t& value, bool& found) override {
        if (!open()) return false;
        const esp_err_t result = nvs_get_u64(handle_, "boot_session", &value);
        if (result == ESP_ERR_NVS_NOT_FOUND) {
            value = 0;
            found = false;
            return true;
        }
        found = result == ESP_OK;
        return result == ESP_OK;
    }

    bool save(std::uint64_t value) override {
        return open() && nvs_set_u64(handle_, "boot_session", value) == ESP_OK &&
               nvs_commit(handle_) == ESP_OK;
    }

private:
    bool open() {
        if (handle_ != 0) return true;
        return nvs_open("gs_node", NVS_READWRITE, &handle_) == ESP_OK;
    }

    nvs_handle_t handle_{0};
};

}  // namespace

std::optional<std::uint64_t> allocate_nvs_session_id() {
    NvsSessionCounterStore store;
    return transport::next_boot_session(store);
}

std::optional<bool> health_ack_pinned_for_hub(const std::string& hub_id) {
    nvs_handle_t handle = 0;
    if (nvs_open("gs_node", NVS_READONLY, &handle) != ESP_OK) return std::nullopt;
    char stored[65]{};
    std::size_t size = sizeof(stored);
    const esp_err_t result = nvs_get_str(handle, "health_ack_hub", stored, &size);
    nvs_close(handle);
    if (result == ESP_ERR_NVS_NOT_FOUND) return false;
    if (result != ESP_OK) return std::nullopt;
    return hub_id == stored;
}

bool pin_health_ack_for_hub(const std::string& hub_id) {
    if (hub_id.empty() || hub_id.size() >= 65) return false;
    nvs_handle_t handle = 0;
    if (nvs_open("gs_node", NVS_READWRITE, &handle) != ESP_OK) return false;
    const bool okay = nvs_set_str(handle, "health_ack_hub", hub_id.c_str()) == ESP_OK &&
                       nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    return okay;
}

}  // namespace gs::node::target
