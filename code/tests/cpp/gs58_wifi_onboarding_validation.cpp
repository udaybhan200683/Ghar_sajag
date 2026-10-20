#include "firmware/hub/connectivity/wifi_onboarding.hpp"

#include <cstring>
#include <iostream>
#include <stdexcept>

namespace gs::hub::connectivity {
unsigned ready_notifications = 0;
void notify_s3_wifi_credentials_ready() { ++ready_notifications; }
}

namespace {
using namespace gs::hub::connectivity;
unsigned checks = 0;
void expect(bool ok, const char* what) {
    ++checks;
    if (!ok) throw std::runtime_error(what);
}

class Authority final : public WifiSetupAuthority {
public:
    bool current{false};
    std::uint64_t generation{1};
    std::uint64_t current_generation(std::uint64_t) const override {
        return current ? generation : 0;
    }
};

class Scanner final : public WifiSetupScanner {
public:
    bool available{true};
    Authority* revoke_during_scan{nullptr};
    WifiScanEntry entry{};
    bool scan(WifiScanEntry* output, std::size_t capacity,
              std::size_t& count) override {
        if (!available || capacity == 0) return false;
        output[0] = entry;
        count = 1;
        if (revoke_during_scan) revoke_during_scan->current = false;
        return true;
    }
};

class StoreBackend final : public WifiCredentialStoreBackend {
public:
    Authority* revoke_during_replace{nullptr};
    WifiCredentialProtection protection_state{WifiCredentialProtection::Unavailable};
    WifiCredentialStoreResult result{WifiCredentialStoreResult::Ok};
    WifiCredentialRecord saved{};
    unsigned writes{0};
    WifiCredentialProtection protection() const override { return protection_state; }
    WifiCredentialStoreResult load(WifiCredentialRecord& out) override {
        out = saved;
        return writes ? WifiCredentialStoreResult::Ok : WifiCredentialStoreResult::NotFound;
    }
    WifiCredentialStoreResult replace_atomically(const WifiCredentialRecord& input) override {
        ++writes;
        if (result == WifiCredentialStoreResult::Ok) saved = input;
        if (revoke_during_replace) revoke_during_replace->current = false;
        return result;
    }
    WifiCredentialStoreResult erase() override { return WifiCredentialStoreResult::CommitRejected; }
};

WifiScanEntry network() {
    WifiScanEntry entry;
    const char* name = "Home24";
    std::memcpy(entry.ssid.data(), name, 6);
    entry.ssid_size = 6;
    entry.channel = 11;
    entry.security = WifiScanSecurity::Wpa2;
    return entry;
}

WifiCredentialRecord credentials() {
    WifiCredentialRecord value;
    const char* name = "Home24";
    const char* password = "strong-example-password";
    std::memcpy(value.ssid.data(), name, 6);
    std::memcpy(value.password.data(), password, std::strlen(password));
    value.ssid_size = 6;
    value.password_size = std::strlen(password);
    return value;
}

void test_authority_scan_commit_and_recovery() {
    Authority authority;
    Scanner scanner;
    scanner.entry = network();
    StoreBackend backend;
    WifiCredentialStore store(backend);
    WifiOnboarding flow(authority, store, scanner);
    WifiScanEntry found[WifiOnboarding::kMaxScanEntries]{};
    std::size_t count = 99;
    auto input = credentials();
    const auto initial_notifications = ready_notifications;

    expect(flow.scan(100, found, 20, count) == WifiSetupResult::Unauthorized && count == 0,
           "unauthorized scan fails closed");
    expect(flow.commit(100, input, scanner.entry) == WifiSetupResult::Unauthorized &&
           backend.writes == 0, "unauthorized credential submission cannot write");
    authority.current = true;
    expect(flow.commit(100, input, scanner.entry) == WifiSetupResult::InvalidNetwork,
           "credential submission needs a current Hub scan");
    expect(flow.scan(100, found, 20, count) == WifiSetupResult::Ok && count == 1 &&
           found[0].channel == 11, "authorized scan returns Hub-observed supported AP");
    expect(flow.commit(100, input, found[0]) ==
           WifiSetupResult::ProtectedStorageUnavailable && backend.writes == 0,
           "missing verified protected store prevents credential write");
    backend.protection_state = WifiCredentialProtection::PlaintextOnly;
    expect(flow.commit(100, input, found[0]) ==
           WifiSetupResult::ProtectedStorageUnavailable && backend.writes == 0,
           "plaintext provider is refused");
    backend.protection_state = WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    backend.result = WifiCredentialStoreResult::CommitRejected;
    expect(flow.commit(100, input, found[0]) == WifiSetupResult::CommitRejected &&
           ready_notifications == initial_notifications,
           "rejected replacement cannot start station retry");
    backend.result = WifiCredentialStoreResult::CommitOutcomeUnknown;
    expect(flow.commit(100, input, found[0]) == WifiSetupResult::CommitOutcomeUnknown &&
           ready_notifications == initial_notifications,
           "unknown commit outcome cannot start station retry");
    backend.result = WifiCredentialStoreResult::Ok;
    expect(flow.commit(100, input, found[0]) == WifiSetupResult::Ok &&
           ready_notifications == initial_notifications + 1 &&
           backend.saved.ssid_size == 6, "committed protected generation alone notifies station");
    expect(flow.commit(100, input, found[0]) == WifiSetupResult::InvalidNetwork,
           "successful setup consumes the scan result");
    expect(flow.scan(200, found, 20, count) == WifiSetupResult::Ok,
           "authorized change Wi-Fi requires a new scan");
    ++authority.generation;
    expect(flow.commit(200, input, found[0]) == WifiSetupResult::Unauthorized,
           "ownership/session generation change invalidates scanned AP");
    expect(flow.scan(201, found, 20, count) == WifiSetupResult::Ok,
           "new current binding needs a fresh scan");
    authority.current = false;
    expect(flow.commit(200, input, found[0]) == WifiSetupResult::Unauthorized &&
           ready_notifications == initial_notifications + 1,
           "revocation before replacement blocks reconnect");
    authority.current = true;
    expect(flow.commit(202, input, found[0]) == WifiSetupResult::InvalidNetwork,
           "restored authority cannot reuse an invalidated scan");
}

void test_invalid_network_password_and_expiry() {
    Authority authority;
    authority.current = true;
    Scanner scanner;
    scanner.entry = network();
    StoreBackend backend;
    backend.protection_state = WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    WifiCredentialStore store(backend);
    WifiOnboarding flow(authority, store, scanner);
    WifiScanEntry found[20]{};
    std::size_t count = 0;
    scanner.entry.channel = 36;
    expect(flow.scan(5, found, 20, count) == WifiSetupResult::NoSupportedNetworks,
           "5 GHz AP is excluded from Hub-visible choices");
    scanner.entry = network();
    scanner.entry.security = WifiScanSecurity::Open;
    expect(flow.scan(6, found, 20, count) == WifiSetupResult::NoSupportedNetworks,
           "open network is excluded from supported secure choices");
    scanner.entry = network();
    expect(flow.scan(10, found, 20, count) == WifiSetupResult::Ok,
           "supported network can be scanned again");
    auto input = credentials();
    auto forged = found[0];
    forged.channel = 12;
    expect(flow.commit(10, input, forged) == WifiSetupResult::InvalidNetwork,
           "unscanned AP/channel substitution is refused");
    input.password_size = 7;
    expect(flow.commit(10, input, found[0]) == WifiSetupResult::InvalidPassword,
           "short WPA password is refused");
    input = credentials();
    input.password[2] = 0;
    expect(flow.commit(10, input, found[0]) == WifiSetupResult::InvalidPassword,
           "embedded terminator cannot truncate the supplied password");
    input = credentials();
    input.ssid[0] = 'X';
    expect(flow.commit(10, input, found[0]) == WifiSetupResult::InvalidNetwork,
           "SSID substitution is refused");
    input = credentials();
    expect(flow.commit(30011, input, found[0]) == WifiSetupResult::InvalidNetwork,
           "stale scan result cannot commit after thirty seconds");
    expect(flow.commit(9, input, found[0]) == WifiSetupResult::InvalidNetwork,
           "monotonic rollback invalidates scan");
    expect(backend.writes == 0, "invalid scan or password never reaches storage");
    scanner.available = false;
    expect(flow.scan(12, found, 20, count) == WifiSetupResult::ScanFailed && count == 0,
           "driver scan failure returns no stale choices");
    scanner.available = true;
    scanner.revoke_during_scan = &authority;
    expect(flow.scan(13, found, 20, count) == WifiSetupResult::Unauthorized && count == 0,
           "authority revoked during scan cannot return an authorized result");
    authority.current = true;
    scanner.revoke_during_scan = nullptr;
    expect(flow.scan(14, found, 20, count) == WifiSetupResult::Ok,
           "fresh authority requires a fresh scan");
    backend.revoke_during_replace = &authority;
    const auto prior_notifications = ready_notifications;
    expect(flow.commit(14, credentials(), found[0]) == WifiSetupResult::Unauthorized &&
           ready_notifications == prior_notifications,
           "revocation during protected replacement cannot start station retry");
    authority.current = true;
    expect(flow.commit(15, credentials(), found[0]) == WifiSetupResult::InvalidNetwork,
           "revocation during replacement consumes the old scan");
}
}

int main() {
    try {
        test_authority_scan_commit_and_recovery();
        test_invalid_network_password_and_expiry();
        std::cout << "GS-58 onboarding checks=" << checks << " PASS\n";
    } catch (const std::exception& error) {
        std::cerr << "GS-58 onboarding FAIL: " << error.what() << '\n';
        return 1;
    }
}
