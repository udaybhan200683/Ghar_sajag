#include "firmware/hub/connectivity/wifi_onboarding.hpp"
#include "firmware/hub/connectivity/wifi_credential_slots.hpp"

#include <algorithm>
#include <array>
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
    bool completion_allowed{true};
    std::uint64_t generation{1};
    std::uint64_t current_generation(std::uint64_t) const override {
        return current ? generation : 0;
    }
    bool complete_setup_operation(std::uint64_t now_ms,
                                  std::uint64_t expected) override {
        return completion_allowed && current_generation(now_ms) == expected;
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
    Authority* revoke_during_stage{nullptr};
    WifiCredentialProtection protection_state{WifiCredentialProtection::Unavailable};
    WifiCredentialStoreResult result{WifiCredentialStoreResult::CandidateStaged};
    WifiCredentialRecord active{};
    WifiCredentialRecord candidate{};
    std::uint32_t candidate_generation{0};
    bool active_present{false};
    bool candidate_present{false};
    unsigned writes{0};
    unsigned discards{0};
    WifiCredentialProtection protection() const override { return protection_state; }
    WifiCredentialStoreResult load(WifiCredentialRecord& out) override {
        out = active;
        return active_present ? WifiCredentialStoreResult::Ok : WifiCredentialStoreResult::NotFound;
    }
    WifiCredentialStoreResult stage_candidate(const WifiCredentialRecord& input,
                                              std::uint32_t& generation) override {
        ++writes;
        generation = 0;
        if (result == WifiCredentialStoreResult::CandidateStaged) {
            candidate = input;
            candidate_generation = active_present ? 2U : 1U;
            candidate_present = true;
            generation = candidate_generation;
        }
        if (revoke_during_stage) revoke_during_stage->current = false;
        return result;
    }
    WifiCredentialStoreResult load_candidate(std::uint32_t& generation,
                                             WifiCredentialRecord& out) override {
        if (!candidate_present) return WifiCredentialStoreResult::NotFound;
        generation = candidate_generation;
        out = candidate;
        return WifiCredentialStoreResult::CandidateStaged;
    }
    WifiCredentialStoreResult activate_candidate(std::uint32_t generation) override {
        if (!candidate_present || generation != candidate_generation)
            return WifiCredentialStoreResult::CommitRejected;
        active = candidate;
        active_present = true;
        candidate.clear();
        candidate_present = false;
        return WifiCredentialStoreResult::Ok;
    }
    WifiCredentialStoreResult discard_candidate(std::uint32_t generation) override {
        ++discards;
        if (!candidate_present || generation != candidate_generation)
            return WifiCredentialStoreResult::NotFound;
        candidate.clear();
        candidate_present = false;
        return WifiCredentialStoreResult::Ok;
    }
    WifiCredentialStoreResult erase() override { return WifiCredentialStoreResult::CommitRejected; }
};

class MemorySlotStorage final : public WifiCredentialSlotStorage {
public:
    struct Cell {
        bool present{false};
        std::array<std::uint8_t, kMaxEncodedBytes> bytes{};
        std::size_t size{0};
    };
    std::array<Cell, 3> cells{};
    WifiCredentialProtection protection() const override {
        return WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    }
    static std::size_t index(WifiCredentialSlot slot) {
        return static_cast<std::size_t>(slot);
    }
    WifiCredentialIoResult read(WifiCredentialSlot slot, std::uint8_t* output,
                                std::size_t capacity, std::size_t& size) override {
        const auto& cell = cells[index(slot)];
        size = 0;
        if (!cell.present) return WifiCredentialIoResult::NotFound;
        if (output == nullptr || capacity < cell.size) return WifiCredentialIoResult::IoError;
        std::copy_n(cell.bytes.begin(), cell.size, output);
        size = cell.size;
        return WifiCredentialIoResult::Ok;
    }
    WifiCredentialIoResult write(WifiCredentialSlot slot, const std::uint8_t* input,
                                 std::size_t size) override {
        auto& cell = cells[index(slot)];
        if (input == nullptr || size > cell.bytes.size()) return WifiCredentialIoResult::IoError;
        cell = Cell{};
        cell.present = true;
        cell.size = size;
        std::copy_n(input, size, cell.bytes.begin());
        return WifiCredentialIoResult::Ok;
    }
    WifiCredentialIoResult erase(WifiCredentialSlot slot) override {
        cells[index(slot)] = Cell{};
        return WifiCredentialIoResult::Ok;
    }
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

bool same(const WifiCredentialRecord& a, const WifiCredentialRecord& b) {
    return a.ssid_size == b.ssid_size && a.password_size == b.password_size &&
        std::equal(a.ssid.begin(), a.ssid.begin() + a.ssid_size, b.ssid.begin()) &&
        std::equal(a.password.begin(), a.password.begin() + a.password_size, b.password.begin());
}

void test_authority_stages_without_activating_or_reconnecting() {
    Authority authority;
    Scanner scanner;
    scanner.entry = network();
    StoreBackend backend;
    WifiCredentialStore store(backend);
    WifiOnboarding flow(authority, store, scanner);
    WifiScanEntry found[WifiOnboarding::kMaxScanEntries]{};
    std::size_t count = 99;
    auto input = credentials();
    auto old = credentials();
    old.password[0] = 'o';
    backend.active = old;
    backend.active_present = true;
    const auto initial_notifications = ready_notifications;
    std::uint32_t candidate_generation = 0;

    expect(flow.scan(100, found, 20, count) == WifiSetupResult::Unauthorized && count == 0,
           "unauthorized scan fails closed");
    expect(flow.stage_candidate(100, input, scanner.entry, candidate_generation) == WifiSetupResult::Unauthorized &&
           backend.writes == 0, "unauthorized credential submission cannot write");
    authority.current = true;
    expect(flow.stage_candidate(100, input, scanner.entry, candidate_generation) == WifiSetupResult::InvalidNetwork,
           "credential submission needs a current Hub scan");
    expect(flow.scan(100, found, 20, count) == WifiSetupResult::Ok && count == 1 &&
           found[0].channel == 11, "authorized scan returns Hub-observed supported AP");
    expect(flow.stage_candidate(100, input, found[0], candidate_generation) ==
           WifiSetupResult::ProtectedStorageUnavailable && backend.writes == 0,
           "missing verified protected store prevents credential write");
    backend.protection_state = WifiCredentialProtection::PlaintextOnly;
    expect(flow.stage_candidate(100, input, found[0], candidate_generation) ==
           WifiSetupResult::ProtectedStorageUnavailable && backend.writes == 0,
           "plaintext provider is refused");
    backend.protection_state = WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    backend.result = WifiCredentialStoreResult::CommitRejected;
    expect(flow.stage_candidate(100, input, found[0], candidate_generation) == WifiSetupResult::CommitRejected &&
           ready_notifications == initial_notifications,
           "rejected candidate cannot change active configuration or reconnect");
    backend.result = WifiCredentialStoreResult::CommitOutcomeUnknown;
    expect(flow.stage_candidate(100, input, found[0], candidate_generation) == WifiSetupResult::CommitOutcomeUnknown &&
           ready_notifications == initial_notifications,
           "unknown candidate outcome cannot change active configuration or reconnect");
    backend.result = WifiCredentialStoreResult::CandidateStaged;
    expect(flow.stage_candidate(100, input, found[0], candidate_generation) ==
               WifiSetupResult::CredentialStaged && candidate_generation == 2 &&
               ready_notifications == initial_notifications,
           "durable candidate is reported separately without reconnect or setup success");
    WifiCredentialRecord loaded;
    expect(store.load(loaded) == WifiCredentialStoreResult::Ok &&
               loaded.password[0] == old.password[0],
           "staged replacement preserves the previously active verified credential");
    std::uint32_t loaded_generation = 0;
    expect(store.load_candidate(loaded_generation, loaded) ==
               WifiCredentialStoreResult::CandidateStaged &&
               loaded_generation == candidate_generation &&
               loaded.password[0] == input.password[0],
           "candidate can be recovered independently after restart");
    expect(flow.stage_candidate(100, input, found[0], candidate_generation) ==
               WifiSetupResult::InvalidNetwork,
           "staging consumes the scan result");
    expect(flow.scan(200, found, 20, count) == WifiSetupResult::Ok,
           "authorized change Wi-Fi requires a new scan");
    ++authority.generation;
    expect(flow.stage_candidate(200, input, found[0], candidate_generation) == WifiSetupResult::Unauthorized,
           "ownership/session generation change invalidates scanned AP");
    expect(flow.scan(201, found, 20, count) == WifiSetupResult::Ok,
           "new current binding needs a fresh scan");
    authority.current = false;
    expect(flow.stage_candidate(200, input, found[0], candidate_generation) == WifiSetupResult::Unauthorized &&
           ready_notifications == initial_notifications,
           "revocation before candidate storage blocks stage/reconnect");
    authority.current = true;
    expect(flow.stage_candidate(202, input, found[0], candidate_generation) == WifiSetupResult::InvalidNetwork,
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
    std::uint32_t candidate_generation = 0;
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
    expect(flow.stage_candidate(10, input, forged, candidate_generation) == WifiSetupResult::InvalidNetwork,
           "unscanned AP/channel substitution is refused");
    input.password_size = 7;
    expect(flow.stage_candidate(10, input, found[0], candidate_generation) == WifiSetupResult::InvalidPassword,
           "short WPA password is refused");
    input = credentials();
    input.password[2] = 0;
    expect(flow.stage_candidate(10, input, found[0], candidate_generation) == WifiSetupResult::InvalidPassword,
           "embedded terminator cannot truncate the supplied password");
    input = credentials();
    input.ssid[0] = 'X';
    expect(flow.stage_candidate(10, input, found[0], candidate_generation) == WifiSetupResult::InvalidNetwork,
           "SSID substitution is refused");
    input = credentials();
    expect(flow.stage_candidate(30011, input, found[0], candidate_generation) == WifiSetupResult::InvalidNetwork,
           "stale scan result cannot commit after thirty seconds");
    expect(flow.stage_candidate(9, input, found[0], candidate_generation) == WifiSetupResult::InvalidNetwork,
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
    backend.revoke_during_stage = &authority;
    const auto prior_notifications = ready_notifications;
    expect(flow.stage_candidate(14, credentials(), found[0], candidate_generation) == WifiSetupResult::Unauthorized &&
           ready_notifications == prior_notifications && !backend.candidate_present &&
           backend.discards == 1,
           "revocation during stage discards the candidate when possible without activation/reconnect");
    authority.current = true;
    expect(flow.stage_candidate(15, credentials(), found[0], candidate_generation) == WifiSetupResult::InvalidNetwork,
           "revocation during stage consumes the old scan");
    authority.completion_allowed = false;
    expect(flow.scan(16, found, 20, count) == WifiSetupResult::Ok,
           "failed one-use completion requires a new scan");
    expect(flow.stage_candidate(16, credentials(), found[0], candidate_generation) ==
               WifiSetupResult::Unauthorized && !backend.candidate_present &&
               backend.discards == 2,
           "failed permit completion removes staged candidate while preserving prior active record");
}

void test_onboarding_stages_through_real_two_slot_backend() {
    Authority authority;
    authority.current = true;
    Scanner scanner;
    scanner.entry = network();
    MemorySlotStorage storage;
    TwoSlotWifiCredentialStoreBackend backend(storage);
    auto old = credentials();
    old.password[0] = 'o';
    std::uint32_t initial_generation = 0;
    expect(backend.stage_candidate(old, initial_generation) ==
               WifiCredentialStoreResult::CandidateStaged &&
               backend.activate_candidate(initial_generation) == WifiCredentialStoreResult::Ok,
           "real slot adapter seeds a previously verified credential");

    WifiCredentialStore store(backend);
    WifiOnboarding flow(authority, store, scanner);
    WifiScanEntry found[WifiOnboarding::kMaxScanEntries]{};
    std::size_t count = 0;
    expect(flow.scan(500, found, WifiOnboarding::kMaxScanEntries, count) ==
               WifiSetupResult::Ok && count == 1,
           "production onboarding scanner path obtains the selected AP");
    std::uint32_t candidate_generation = 0;
    const auto new_credentials = credentials();
    const auto notifications_before = ready_notifications;
    expect(flow.stage_candidate(500, new_credentials, found[0], candidate_generation) ==
               WifiSetupResult::CredentialStaged && candidate_generation == initial_generation + 1,
           "production onboarding path stages candidate in two-slot backend");
    WifiCredentialRecord active;
    expect(store.load(active) == WifiCredentialStoreResult::Ok && same(active, old),
           "integrated stage leaves old credential selected");
    expect(ready_notifications == notifications_before,
           "integrated stage does not signal station reconnect before verification");

    TwoSlotWifiCredentialStoreBackend recovered_backend(storage);
    WifiCredentialStore recovered_store(recovered_backend);
    expect(recovered_store.load(active) == WifiCredentialStoreResult::Ok && same(active, old),
           "integrated restart continues on old active credential");
    std::uint32_t recovered_generation = 0;
    expect(recovered_store.load_candidate(recovered_generation, active) ==
               WifiCredentialStoreResult::CandidateStaged &&
               recovered_generation == candidate_generation && same(active, new_credentials),
           "integrated restart can inspect staged candidate without activating it");
}
}

int main() {
    try {
        test_authority_stages_without_activating_or_reconnecting();
        test_invalid_network_password_and_expiry();
        test_onboarding_stages_through_real_two_slot_backend();
        std::cout << "GS-58 onboarding checks=" << checks << " PASS\n";
    } catch (const std::exception& error) {
        std::cerr << "GS-58 onboarding FAIL: " << error.what() << '\n';
        return 1;
    }
}
