#include "firmware/common/security/target_wrapping_key.hpp"

#include "nvs.h"
#include "sdkconfig.h"

#include <algorithm>

namespace gs::security {

bool load_or_create_target_wrapping_key(CommissioningCrypto& crypto, Key32& out) {
    out.fill(0);
#if !GS_HIL_BUILD
#if !defined(CONFIG_SECURE_BOOT) || !defined(CONFIG_SECURE_FLASH_ENC_ENABLED)
    return false;
#endif
#endif
    nvs_handle_t handle = 0;
    if (nvs_open("gs_security", NVS_READWRITE, &handle) != ESP_OK) return false;
    std::size_t length = out.size();
    const auto read = nvs_get_blob(handle, "wrap_key", out.data(), &length);
    if (read == ESP_OK) {
        nvs_close(handle);
        if (length == out.size() &&
            !std::all_of(out.begin(), out.end(), [](std::uint8_t byte) { return byte == 0; }))
            return true;
        crypto.secure_zero(out.data(), out.size());
        return false;
    }
    if (read != ESP_ERR_NVS_NOT_FOUND ||
        !crypto.random_bytes(out.data(), out.size()) ||
        nvs_set_blob(handle, "wrap_key", out.data(), out.size()) != ESP_OK ||
        nvs_commit(handle) != ESP_OK) {
        nvs_close(handle);
        crypto.secure_zero(out.data(), out.size());
        return false;
    }
    nvs_close(handle);
    nvs_handle_t verify = 0;
    if (nvs_open("gs_security", NVS_READONLY, &verify) != ESP_OK) {
        crypto.secure_zero(out.data(), out.size());
        return false;
    }
    Key32 checked{};
    length = checked.size();
    const bool committed = nvs_get_blob(verify, "wrap_key", checked.data(),
                                        &length) == ESP_OK &&
                           length == out.size() &&
                           crypto.constant_time_equal(out.data(), checked.data(), out.size());
    nvs_close(verify);
    crypto.secure_zero(checked.data(), checked.size());
    if (!committed) crypto.secure_zero(out.data(), out.size());
    return committed;
}

}  // namespace gs::security
