#pragma once

#include "firmware/hub/connectivity/wifi_credential_slots.hpp"

#include <cstdint>

namespace gs::hub::target::esp32s3 {

class NvsDeviceKeyCustodyVerifier {
public:
    virtual ~NvsDeviceKeyCustodyVerifier() = default;
    // Must bind this ephemeral fingerprint to the permanent Hub identity and
    // approved per-device manufacturing custody record. GS-168 certificate
    // enrollment alone is not evidence for the NVS encryption key.
    virtual bool verify_device_specific_key_fingerprint(
        const std::uint8_t fingerprint[32]) const = 0;
};

// Explicitly initialized adapter for a future approved partition layout:
// encrypted NVS key partition "nvs_keys" plus dedicated NVS data partition
// "wifi_credentials". Initialization reads existing key material only.
// It never generates keys, formats partitions, or changes eFuses.
class EspIdfEncryptedWifiCredentialSlots final
    : public ::gs::hub::connectivity::WifiCredentialSlotStorage {
public:
    static constexpr const char* kKeyPartition = "nvs_keys";
    static constexpr const char* kDataPartition = "wifi_credentials";

    explicit EspIdfEncryptedWifiCredentialSlots(
        NvsDeviceKeyCustodyVerifier& custody_verifier)
        : custody_verifier_(custody_verifier) {}

    bool initialize();
    ::gs::hub::connectivity::WifiCredentialProtection protection() const override;
    ::gs::hub::connectivity::WifiCredentialIoResult read(
        ::gs::hub::connectivity::WifiCredentialSlot slot, std::uint8_t* output,
        std::size_t capacity, std::size_t& size) override;
    ::gs::hub::connectivity::WifiCredentialIoResult write(
        ::gs::hub::connectivity::WifiCredentialSlot slot, const std::uint8_t* input,
        std::size_t size) override;
    ::gs::hub::connectivity::WifiCredentialIoResult erase(
        ::gs::hub::connectivity::WifiCredentialSlot slot) override;

private:
    bool ready() const;
    static const char* key_name(::gs::hub::connectivity::WifiCredentialSlot slot);
    NvsDeviceKeyCustodyVerifier& custody_verifier_;
    bool initialized_{false};
};

}  // namespace gs::hub::target::esp32s3
