#include "firmware/hub/connectivity/wifi_onboarding.hpp"
#include "firmware/hub/connectivity/wifi_station.hpp"

#include <algorithm>

namespace gs::hub::connectivity {
namespace {
bool supported(const WifiScanEntry& entry) {
    return entry.ssid_size > 0 && entry.ssid_size <= entry.ssid.size() &&
           std::all_of(entry.ssid.begin(), entry.ssid.begin() + entry.ssid_size,
                       [](std::uint8_t ch) { return ch != 0; }) &&
           gs::connectivity::IndiaWifiProfileV1::allows_channel(entry.channel) &&
           (entry.security == WifiScanSecurity::Wpa2 ||
            entry.security == WifiScanSecurity::Wpa3);
}

bool same_ssid(const WifiCredentialRecord& candidate,
               const WifiScanEntry& selected) {
    return candidate.ssid_size == selected.ssid_size &&
           std::equal(candidate.ssid.begin(),
                      candidate.ssid.begin() + candidate.ssid_size,
                      selected.ssid.begin());
}

bool valid_wpa_password(const WifiCredentialRecord& candidate) {
    // WPA passphrase: 8–63 octets, or a 64-character hexadecimal PSK.
    if (candidate.password_size >= 8 && candidate.password_size <= 63)
        return std::all_of(candidate.password.begin(),
                           candidate.password.begin() + candidate.password_size,
                           [](std::uint8_t ch) { return ch >= 0x20 && ch <= 0x7e; });
    if (candidate.password_size != 64) return false;
    return std::all_of(candidate.password.begin(), candidate.password.end(),
                       [](std::uint8_t ch) {
                           return (ch >= '0' && ch <= '9') ||
                                  (ch >= 'a' && ch <= 'f') ||
                                  (ch >= 'A' && ch <= 'F');
                       });
}
}  // namespace

WifiSetupResult WifiOnboarding::scan(std::uint64_t now_ms,
                                     WifiScanEntry* output,
                                     std::size_t capacity,
                                     std::size_t& count) {
    count = 0;
    last_scan_count_ = 0;
    last_binding_generation_ = 0;
    const auto generation = authority_.current_generation(now_ms);
    if (generation == 0) return WifiSetupResult::Unauthorized;
    if (capacity == 0 || capacity > kMaxScanEntries || output == nullptr)
        return WifiSetupResult::ScanFailed;
    std::array<WifiScanEntry, kMaxScanEntries> entries{};
    std::size_t observed = 0;
    if (!scanner_.scan(entries.data(), capacity, observed) || observed > capacity)
        return WifiSetupResult::ScanFailed;
    if (authority_.current_generation(now_ms) != generation)
        return WifiSetupResult::Unauthorized;
    for (std::size_t i = 0; i < observed; ++i) {
        if (supported(entries[i])) {
            last_scan_[count] = entries[i];
            output[count++] = entries[i];
        }
    }
    last_scan_count_ = count;
    last_scan_ms_ = now_ms;
    last_binding_generation_ = generation;
    return count == 0 ? WifiSetupResult::NoSupportedNetworks : WifiSetupResult::Ok;
}

WifiSetupResult WifiOnboarding::commit(std::uint64_t now_ms,
                                       const WifiCredentialRecord& candidate,
                                       const WifiScanEntry& selected) {
    const auto generation = authority_.current_generation(now_ms);
    if (generation == 0) {
        last_scan_count_ = 0;
        last_binding_generation_ = 0;
        return WifiSetupResult::Unauthorized;
    }
    if (last_binding_generation_ == 0) return WifiSetupResult::InvalidNetwork;
    if (generation != last_binding_generation_) {
        last_scan_count_ = 0;
        last_binding_generation_ = 0;
        return WifiSetupResult::Unauthorized;
    }
    if (now_ms < last_scan_ms_ || now_ms - last_scan_ms_ > kScanValidityMs)
        return WifiSetupResult::InvalidNetwork;
    const bool scanned = std::any_of(last_scan_.begin(),
        last_scan_.begin() + last_scan_count_, [&](const WifiScanEntry& entry) {
            return entry.ssid_size == selected.ssid_size &&
                   entry.channel == selected.channel &&
                   entry.security == selected.security &&
                   std::equal(entry.ssid.begin(), entry.ssid.end(), selected.ssid.begin());
        });
    if (!scanned) return WifiSetupResult::InvalidNetwork;
    if (!supported(selected) || !candidate.valid() ||
        !same_ssid(candidate, selected)) return WifiSetupResult::InvalidNetwork;
    if (!valid_wpa_password(candidate)) return WifiSetupResult::InvalidPassword;
    const auto result = store_.replace(candidate);
    if (result == WifiCredentialStoreResult::ProtectedStorageUnavailable)
        return WifiSetupResult::ProtectedStorageUnavailable;
    if (result == WifiCredentialStoreResult::CommitOutcomeUnknown)
        return WifiSetupResult::CommitOutcomeUnknown;
    if (result != WifiCredentialStoreResult::Ok)
        return WifiSetupResult::CommitRejected;
    // A revocation between the preflight and commit must not start a station
    // connection. The store's committed generation remains available for the
    // approved recovery owner; it cannot authorize Home publication.
    if (authority_.current_generation(now_ms) != generation) {
        last_scan_count_ = 0;
        last_binding_generation_ = 0;
        return WifiSetupResult::Unauthorized;
    }
    last_scan_count_ = 0;
    last_binding_generation_ = 0;
    notify_s3_wifi_credentials_ready();
    return WifiSetupResult::Ok;
}

}  // namespace gs::hub::connectivity
