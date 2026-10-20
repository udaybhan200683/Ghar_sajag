#include "firmware/hub/target/esp32s3/esp_idf_encrypted_wifi_credential_slots.hpp"

#include "esp_efuse.h"
#include "esp_partition.h"
#include "esp_secure_boot.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "psa/crypto.h"

namespace gs::hub::target::esp32s3 {
namespace {
using gs::hub::connectivity::WifiCredentialIoResult;
using gs::hub::connectivity::WifiCredentialProtection;
using gs::hub::connectivity::WifiCredentialSlot;
constexpr char kNamespace[] = "gs58wifi";
// Writable ESP-IDF NVS requires at least three 4 KiB pages. The extra page
// permits normal copy-on-write/garbage-collection progress during updates.
constexpr std::size_t kMinimumWritableNvsBytes = 3u * 4096u;

void clear_security_cfg(nvs_sec_cfg_t& cfg) {
    volatile std::uint8_t* bytes = reinterpret_cast<volatile std::uint8_t*>(&cfg);
    for (std::size_t i = 0; i < sizeof(cfg); ++i) bytes[i] = 0;
}

WifiCredentialIoResult map_read_error(esp_err_t error) {
    if (error == ESP_ERR_NVS_NOT_FOUND) return WifiCredentialIoResult::NotFound;
    return WifiCredentialIoResult::IoError;
}
}  // namespace

bool EspIdfEncryptedWifiCredentialSlots::initialize() {
    initialized_ = false;
    if (!esp_secure_boot_enabled() || !esp_efuse_is_flash_encryption_enabled()) return false;

    const auto* key_partition = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS_KEYS, kKeyPartition);
    const auto* data_partition = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, kDataPartition);
    if (key_partition == nullptr || data_partition == nullptr ||
        !key_partition->encrypted || key_partition->size < 4096 ||
        data_partition->size < kMinimumWritableNvsBytes) return false;

    nvs_sec_cfg_t cfg{};
    const auto read_result = nvs_flash_read_security_cfg(key_partition, &cfg);
    if (read_result != ESP_OK) {
        clear_security_cfg(cfg);
        return false;
    }
    std::uint8_t fingerprint[32]{};
    std::size_t fingerprint_size = 0;
    const bool hash_ready = psa_crypto_init() == PSA_SUCCESS &&
        psa_hash_compute(PSA_ALG_SHA_256,
                         reinterpret_cast<const std::uint8_t*>(&cfg), sizeof(cfg),
                         fingerprint, sizeof(fingerprint), &fingerprint_size) == PSA_SUCCESS &&
        fingerprint_size == sizeof(fingerprint);
    const bool custody_verified = hash_ready &&
        custody_verifier_.verify_device_specific_key_fingerprint(fingerprint);
    volatile std::uint8_t* fingerprint_bytes = fingerprint;
    for (std::size_t i = 0; i < sizeof(fingerprint); ++i) fingerprint_bytes[i] = 0;
    if (!custody_verified) {
        clear_security_cfg(cfg);
        return false;
    }
    // This dedicated label is owned by this adapter and must not first be
    // opened with nvs_flash_init_partition(). The secure-init API reads the
    // existing NVS key configuration; no key-generation or erase API is used.
    const auto init_result = nvs_flash_secure_init_partition(kDataPartition, &cfg);
    clear_security_cfg(cfg);
    initialized_ = init_result == ESP_OK;
    return initialized_;
}

bool EspIdfEncryptedWifiCredentialSlots::ready() const {
    return initialized_ && esp_secure_boot_enabled() &&
        esp_efuse_is_flash_encryption_enabled();
}

WifiCredentialProtection EspIdfEncryptedWifiCredentialSlots::protection() const {
    return ready() ? WifiCredentialProtection::EncryptedWithVerifiedDeviceKey
                   : WifiCredentialProtection::Unavailable;
}

const char* EspIdfEncryptedWifiCredentialSlots::key_name(WifiCredentialSlot slot) {
    switch (slot) {
        case WifiCredentialSlot::SlotA: return "cred_a";
        case WifiCredentialSlot::SlotB: return "cred_b";
        case WifiCredentialSlot::Selector: return "cred_sel";
    }
    return nullptr;
}

WifiCredentialIoResult EspIdfEncryptedWifiCredentialSlots::read(
    WifiCredentialSlot slot, std::uint8_t* output, std::size_t capacity,
    std::size_t& size) {
    size = 0;
    const char* key = key_name(slot);
    if (!ready() || key == nullptr || output == nullptr) return WifiCredentialIoResult::IoError;
    nvs_handle_t handle{};
    auto error = nvs_open_from_partition(kDataPartition, kNamespace, NVS_READONLY, &handle);
    if (error != ESP_OK) return map_read_error(error);
    std::size_t required = 0;
    error = nvs_get_blob(handle, key, nullptr, &required);
    if (error != ESP_OK) {
        nvs_close(handle);
        return map_read_error(error);
    }
    if (required > capacity) {
        nvs_close(handle);
        return WifiCredentialIoResult::IoError;
    }
    error = nvs_get_blob(handle, key, output, &required);
    nvs_close(handle);
    if (error != ESP_OK) return map_read_error(error);
    size = required;
    return WifiCredentialIoResult::Ok;
}

WifiCredentialIoResult EspIdfEncryptedWifiCredentialSlots::write(
    WifiCredentialSlot slot, const std::uint8_t* input, std::size_t size) {
    const char* key = key_name(slot);
    if (!ready() || key == nullptr || input == nullptr || size == 0 ||
        size > ::gs::hub::connectivity::WifiCredentialSlotStorage::kMaxEncodedBytes)
        return WifiCredentialIoResult::IoError;
    nvs_handle_t handle{};
    auto error = nvs_open_from_partition(kDataPartition, kNamespace, NVS_READWRITE, &handle);
    if (error != ESP_OK) return WifiCredentialIoResult::Rejected;
    error = nvs_set_blob(handle, key, input, size);
    if (error != ESP_OK) {
        nvs_close(handle);
        return WifiCredentialIoResult::Rejected;
    }
    error = nvs_commit(handle);
    nvs_close(handle);
    return error == ESP_OK ? WifiCredentialIoResult::Ok
                           : WifiCredentialIoResult::OutcomeUnknown;
}

WifiCredentialIoResult EspIdfEncryptedWifiCredentialSlots::erase(
    WifiCredentialSlot slot) {
    const char* key = key_name(slot);
    if (!ready() || key == nullptr) return WifiCredentialIoResult::IoError;
    nvs_handle_t handle{};
    auto error = nvs_open_from_partition(kDataPartition, kNamespace, NVS_READWRITE, &handle);
    if (error != ESP_OK) return WifiCredentialIoResult::IoError;
    error = nvs_erase_key(handle, key);
    if (error == ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return WifiCredentialIoResult::NotFound;
    }
    if (error != ESP_OK) {
        nvs_close(handle);
        return WifiCredentialIoResult::IoError;
    }
    error = nvs_commit(handle);
    nvs_close(handle);
    return error == ESP_OK ? WifiCredentialIoResult::Ok
                           : WifiCredentialIoResult::OutcomeUnknown;
}

}  // namespace gs::hub::target::esp32s3
