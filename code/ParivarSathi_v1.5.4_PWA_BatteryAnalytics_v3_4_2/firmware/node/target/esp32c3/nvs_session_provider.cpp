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

}  // namespace gs::node::target
