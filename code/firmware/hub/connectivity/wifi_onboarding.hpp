#pragma once

#include "firmware/common/connectivity/india_wifi_profile.hpp"
#include "firmware/hub/connectivity/wifi_credential_store.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::hub::connectivity {

// This is a station/provisioning policy, not a pairing protocol or Home claim.
// An implementation of this port must verify the device-specific installer
// proof and current Hub/Home/epoch through the approved GS-109 authority.
class WifiSetupAuthority {
public:
    virtual ~WifiSetupAuthority() = default;
    // An immutable current-binding snapshot, returned atomically. Zero means
    // unauthorized/unavailable. A nonzero value binds the exact Hub,
    // device-specific installer session and current Home/ownership epoch; it
    // must change on transfer, revocation or a new session.
    virtual std::uint64_t current_generation(std::uint64_t now_ms) const = 0;
    // Called only after a successful protected credential commit and a final
    // current-generation check. One-use permit authorities close the session
    // here; simple host policy authorities may retain their current behavior.
    virtual bool complete_setup_operation(std::uint64_t now_ms,
                                          std::uint64_t generation) {
        return generation != 0 && current_generation(now_ms) == generation;
    }
};

enum class WifiScanSecurity : std::uint8_t { Open, Wep, Wpa2, Wpa3, Unknown };
struct WifiScanEntry {
    std::array<std::uint8_t, WifiCredentialRecord::kSsidCapacity> ssid{};
    std::uint8_t ssid_size{0};
    std::uint8_t channel{0};
    WifiScanSecurity security{WifiScanSecurity::Unknown};
};

class WifiSetupScanner {
public:
    virtual ~WifiSetupScanner() = default;
    virtual bool scan(WifiScanEntry* output, std::size_t capacity,
                      std::size_t& count) = 0;
};

enum class WifiSetupResult : std::uint8_t {
    Ok, Unauthorized, ProtectedStorageUnavailable, ScanFailed,
    NoSupportedNetworks, InvalidNetwork, InvalidPassword,
    CommitRejected, CommitOutcomeUnknown,
};

// No commercial target supplies WifiSetupAuthority or protected storage yet.
// In that configuration all operations fail closed. The BLE transport may
// call these methods only after Espressif Security 2 session authentication.
class WifiOnboarding {
public:
    static constexpr std::size_t kMaxScanEntries = 20;
    static constexpr std::uint64_t kScanValidityMs = 30000;
    WifiOnboarding(WifiSetupAuthority& authority, WifiCredentialStore& store,
                   WifiSetupScanner& scanner)
        : authority_(authority), store_(store), scanner_(scanner) {}

    WifiSetupResult scan(std::uint64_t now_ms, WifiScanEntry* output,
                         std::size_t capacity, std::size_t& count);
    WifiSetupResult commit(std::uint64_t now_ms,
                           const WifiCredentialRecord& candidate,
                           const WifiScanEntry& selected);

private:
    WifiSetupAuthority& authority_;
    WifiCredentialStore& store_;
    WifiSetupScanner& scanner_;
    std::array<WifiScanEntry, kMaxScanEntries> last_scan_{};
    std::size_t last_scan_count_{0};
    std::uint64_t last_scan_ms_{0};
    std::uint64_t last_binding_generation_{0};
};

}  // namespace gs::hub::connectivity
