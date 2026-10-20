#pragma once

#include "firmware/hub/connectivity/wifi_credential_store.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::hub::connectivity {

enum class WifiCredentialSlot : std::uint8_t { SlotA, SlotB, Selector };
enum class WifiCredentialIoResult : std::uint8_t {
    Ok,
    NotFound,
    Rejected,
    OutcomeUnknown,
    IoError,
};

// The storage adapter must expose an already initialized encrypted-NVS
// partition protected by the verified per-device key. It must never format,
// erase, or generate keys during initialization.
class WifiCredentialSlotStorage {
public:
    static constexpr std::size_t kMaxEncodedBytes = 112;
    virtual ~WifiCredentialSlotStorage() = default;
    virtual WifiCredentialProtection protection() const = 0;
    virtual WifiCredentialIoResult read(WifiCredentialSlot slot,
                                        std::uint8_t* output,
                                        std::size_t capacity,
                                        std::size_t& size) = 0;
    virtual WifiCredentialIoResult write(WifiCredentialSlot slot,
                                         const std::uint8_t* input,
                                         std::size_t size) = 0;
    virtual WifiCredentialIoResult erase(WifiCredentialSlot slot) = 0;
};

// Recoverable two-slot transaction adapter. Record and selector checksums
// detect accidental corruption; they are not cryptographic authentication.
// Confidentiality and device-key custody remain the storage adapter's job.
class TwoSlotWifiCredentialStoreBackend final : public WifiCredentialStoreBackend {
public:
    explicit TwoSlotWifiCredentialStoreBackend(WifiCredentialSlotStorage& storage)
        : storage_(storage) {}

    WifiCredentialProtection protection() const override;
    WifiCredentialStoreResult load(WifiCredentialRecord& record) override;
    WifiCredentialStoreResult replace_atomically(
        const WifiCredentialRecord& record) override;
    WifiCredentialStoreResult erase() override;

private:
    struct ActiveState {
        bool tombstone{false};
        std::uint8_t slot{0};
        std::uint32_t generation{0};
        WifiCredentialRecord record{};
    };

    WifiCredentialStoreResult read_state(ActiveState& state);
    WifiCredentialStoreResult write_selector_verified(
        std::uint8_t slot, std::uint32_t generation, bool tombstone,
        const ActiveState& previous);
    WifiCredentialSlotStorage& storage_;
};

}  // namespace gs::hub::connectivity
