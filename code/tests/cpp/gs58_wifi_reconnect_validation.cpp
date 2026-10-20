#include "firmware/hub/connectivity/wifi_reconnect_policy.hpp"
#include "firmware/hub/connectivity/wifi_credential_store.hpp"
#include "firmware/common/connectivity/india_wifi_profile.hpp"

#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
int checks = 0;

void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

void test_bounded_retry_and_success_reset() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_credentials_ready(0);
    check(policy.take_due_attempt(0),
          "secure credential readiness permits initial station attempt");
    policy.on_disconnected(100);
    check(policy.scheduled(), "disconnect must schedule reconnect");
    check(policy.next_attempt_ms() == 1100,
          "first reconnect must wait one second");
    check(policy.retry_delay_ms() == 2000,
          "next reconnect delay advances after link loss");
    check(!policy.take_due_attempt(1099),
          "reconnect must not run before its deadline");
    check(policy.take_due_attempt(1100),
          "reconnect runs at its deadline");
    check(!policy.take_due_attempt(1100),
          "a due reconnect may be claimed only once");

    policy.on_attempt_failed(1100);
    check(policy.next_attempt_ms() == 3100,
          "failed reconnect request must use the next two-second delay");
    policy.on_disconnected(1200);
    check(policy.next_attempt_ms() == 3100,
          "duplicate disconnect notification must not postpone a retry");

    for (std::uint64_t now = 4000; policy.retry_delay_ms() < 60000; now += 61000) {
        policy.on_disconnected(now);
        check(policy.take_due_attempt(policy.next_attempt_ms()),
              "scheduled bounded-backoff attempt is available");
        policy.on_attempt_failed(now);
    }
    check(policy.retry_delay_ms() == 60000,
          "retry delay must stop growing at its cap");
    const auto pending = policy.next_attempt_ms();
    check(policy.take_due_attempt(pending),
          "a capped retry remains claimable at its deadline");
    policy.on_disconnected(pending);
    check(policy.next_attempt_ms() == pending + 60000,
          "retry interval remains capped after repeated outages");

    policy.on_connected();
    check(!policy.scheduled(), "connected state cancels retry");
    check(policy.retry_delay_ms() == 1000,
          "connected state resets retry stage");
}

void test_ready_credentials_request_immediate_attempt() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_disconnected(0);
    check(!policy.scheduled(),
          "disconnect without committed credentials must not reconnect");
    policy.on_credentials_ready(42);
    check(policy.next_attempt_ms() == 42,
          "committed credentials request immediate station attempt");
    check(policy.take_due_attempt(42),
          "immediate credential retry is available exactly once");
}

void test_uncredentialed_attempt_failure_is_ignored() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_attempt_failed(10);
    check(!policy.scheduled(),
          "driver failure without committed credentials must not schedule retries");
}

void test_deadline_saturates() {
    gs::hub::connectivity::WifiReconnectPolicy policy;
    policy.on_credentials_ready(0);
    check(policy.take_due_attempt(0),
          "secure credential readiness permits station attempt before deadline test");
    const auto now = std::numeric_limits<std::uint64_t>::max() - 500;
    policy.on_disconnected(now);
    check(policy.next_attempt_ms() == std::numeric_limits<std::uint64_t>::max(),
          "retry deadline addition must saturate");
    check(!policy.take_due_attempt(now),
          "saturated retry deadline is not immediately due");
}

struct TestCountryApi {
    static constexpr int success = 0;
    int set_result{success};
    int get_result{success};
    char active_country[3]{'I', 'N', '\0'};
    bool set_called{false};
    bool get_called{false};
    bool ieee80211d{true};
    std::string configured_country;

    int set_country_code(const char* country, bool enable_ieee80211d) {
        set_called = true;
        ieee80211d = enable_ieee80211d;
        configured_country = country;
        return set_result;
    }
    int get_country_code(char* country) {
        get_called = true;
        country[0] = active_country[0];
        country[1] = active_country[1];
        country[2] = active_country[2];
        return get_result;
    }
};

void test_india_regulatory_profile_and_country_guard() {
    using gs::connectivity::IndiaWifiProfileV1;
    check(IndiaWifiProfileV1::version == 1 &&
              std::string(IndiaWifiProfileV1::country_code) == "IN" &&
              IndiaWifiProfileV1::channel_count == 13,
          "shared profile must be India v1 and contain thirteen 2.4 GHz channels");
    for (std::uint8_t channel = 1; channel <= 13; ++channel)
        check(IndiaWifiProfileV1::allows_channel(channel),
              "India profile includes channels 1 through 13");
    check(!IndiaWifiProfileV1::allows_channel(0) &&
              !IndiaWifiProfileV1::allows_channel(14) &&
              !IndiaWifiProfileV1::allows_channel(36),
          "India profile rejects channel zero, channel 14 and 5 GHz channels");
    check(IndiaWifiProfileV1::next_channel(13) == 1 &&
              IndiaWifiProfileV1::next_channel(0) == 1 &&
              IndiaWifiProfileV1::next_channel(14) == 1,
          "channel cursor wraps only within the approved India range");

    TestCountryApi api;
    check(IndiaWifiProfileV1::configure_country(api) && api.set_called &&
              api.get_called && api.configured_country == "IN" &&
              !api.ieee80211d,
          "country guard sets IN with AP country override disabled then verifies it");
    TestCountryApi setter_failure;
    setter_failure.set_result = 1;
    check(!IndiaWifiProfileV1::configure_country(setter_failure) &&
              !setter_failure.get_called,
          "country setter failure prevents radio startup verification from passing");
    TestCountryApi mismatch;
    mismatch.active_country[0] = 'U';
    mismatch.active_country[1] = 'S';
    check(!IndiaWifiProfileV1::configure_country(mismatch),
          "unexpected active country fails closed");
    TestCountryApi getter_failure;
    getter_failure.get_result = 2;
    check(!IndiaWifiProfileV1::configure_country(getter_failure),
          "country readback failure fails closed");
}

void test_bounded_authenticated_channel_discovery() {
    using gs::connectivity::IndiaWifiChannelDiscovery;
    using gs::connectivity::IndiaWifiProfileV1;
    IndiaWifiChannelDiscovery discovery;
    for (std::uint8_t expected = 1; expected <= 13; ++expected) {
        const auto channel = discovery.next_rejoin_hello_channel();
        check(channel && *channel == expected,
              "scheduled authenticated Hello advances one permitted channel");
    }
    check(discovery.next_rejoin_hello_channel() ==
              std::optional<std::uint8_t>{1},
          "bounded channel discovery wraps at thirteen without channel fourteen");
    check(!discovery.pin_authenticated_challenge(14) &&
              !discovery.pin_authenticated_challenge(0),
          "out-of-profile channel cannot pin a rejoin candidate");
    check(discovery.pin_authenticated_challenge(7) &&
              discovery.candidate_pinned() && discovery.current_channel() == 7 &&
              discovery.next_rejoin_hello_channel() ==
                  std::optional<std::uint8_t>{7},
          "authenticated challenge pins its channel through session retries");
    check(discovery.complete_authenticated_session(7) &&
              discovery.last_authenticated_channel() == 7,
          "only a complete authenticated session records the preferred channel");
    discovery.begin_rejoin();
    check(discovery.next_rejoin_hello_channel() ==
              std::optional<std::uint8_t>{7},
          "subsequent outage starts on the last authenticated channel");
    discovery.begin_rejoin();
    check(discovery.next_rejoin_hello_channel() ==
              std::optional<std::uint8_t>{8},
          "an unsuccessful search keeps advancing instead of pinning stale state");
    check(!discovery.complete_authenticated_session(36) &&
              IndiaWifiProfileV1::allows_channel(discovery.current_channel()),
          "invalid session channel is rejected and current channel remains permitted");
}

class MemoryCredentialBackend final
    : public gs::hub::connectivity::WifiCredentialStoreBackend {
public:
    using Record = gs::hub::connectivity::WifiCredentialRecord;
    using Protection = gs::hub::connectivity::WifiCredentialProtection;
    using Result = gs::hub::connectivity::WifiCredentialStoreResult;

    Protection protection_state{Protection::EncryptedWithVerifiedDeviceKey};
    Result next_replace_result{Result::Ok};
    Record persisted{};
    bool has_record{false};
    unsigned loads{0};
    unsigned replacements{0};
    unsigned erases{0};

    Protection protection() const override { return protection_state; }
    Result load(Record& record) override {
        ++loads;
        if (!has_record) return Result::NotFound;
        record = persisted;
        return Result::Ok;
    }
    Result replace_atomically(const Record& record) override {
        ++replacements;
        const auto result = next_replace_result;
        next_replace_result = Result::Ok;
        if (result == Result::Ok) {
            persisted = record;
            has_record = true;
        }
        return result;
    }
    Result erase() override {
        ++erases;
        has_record = false;
        return Result::Ok;
    }
};

gs::hub::connectivity::WifiCredentialRecord credential(
    std::uint8_t ssid_byte, std::uint8_t password_byte) {
    gs::hub::connectivity::WifiCredentialRecord result;
    result.ssid[0] = ssid_byte;
    result.ssid_size = 1;
    result.password[0] = password_byte;
    result.password_size = 1;
    return result;
}

void test_protected_credential_store_fail_closed_and_atomicity() {
    using namespace gs::hub::connectivity;
    MemoryCredentialBackend backend;
    WifiCredentialStore store(backend);
    const auto original = credential(0x11, 0x22);
    const auto replacement = credential(0x33, 0x44);
    check(store.replace(original) == WifiCredentialStoreResult::Ok &&
              backend.has_record,
          "encrypted device-key backend accepts first committed record");

    backend.next_replace_result = WifiCredentialStoreResult::CommitRejected;
    check(store.replace(replacement) == WifiCredentialStoreResult::CommitRejected,
          "atomic provider reports a rejected replacement without claiming commit");
    WifiCredentialRecord loaded;
    check(store.load(loaded) == WifiCredentialStoreResult::Ok &&
              loaded.ssid[0] == original.ssid[0] &&
              loaded.password[0] == original.password[0],
          "failed replacement preserves the prior complete credential record");

    backend.next_replace_result = WifiCredentialStoreResult::CommitOutcomeUnknown;
    check(store.replace(replacement) ==
              WifiCredentialStoreResult::CommitOutcomeUnknown,
          "ambiguous commit outcome is returned as failure, never as connected-ready");

    auto invalid = replacement;
    invalid.ssid_size = static_cast<std::uint8_t>(invalid.ssid.size() + 1U);
    check(store.replace(invalid) == WifiCredentialStoreResult::InvalidRecord,
          "oversized credential input is rejected before backend mutation");
    invalid = replacement;
    invalid.password_size =
        static_cast<std::uint8_t>(invalid.password.size() + 1U);
    check(store.replace(invalid) == WifiCredentialStoreResult::InvalidRecord,
          "oversized password input is rejected before backend mutation");

    const auto calls_before_unprotected =
        backend.loads + backend.replacements + backend.erases;
    backend.protection_state = WifiCredentialProtection::Unavailable;
    WifiCredentialRecord unavailable = credential(0x55, 0x66);
    check(store.load(unavailable) ==
              WifiCredentialStoreResult::ProtectedStorageUnavailable &&
              unavailable.ssid_size == 0 && unavailable.password_size == 0 &&
              unavailable.ssid[0] == 0 && unavailable.password[0] == 0,
          "unavailable protected storage is refused and input buffers are erased");
    check(store.replace(replacement) ==
              WifiCredentialStoreResult::ProtectedStorageUnavailable &&
              backend.loads + backend.replacements + backend.erases ==
                  calls_before_unprotected,
          "unavailable storage cannot load, replace or silently initialize");

    backend.protection_state = WifiCredentialProtection::PlaintextOnly;
    WifiCredentialRecord refused = credential(0x55, 0x66);
    check(store.load(refused) ==
              WifiCredentialStoreResult::ProtectedStorageUnavailable &&
              refused.ssid_size == 0 && refused.password_size == 0 &&
              refused.ssid[0] == 0 && refused.password[0] == 0,
          "plaintext-only backend is refused and output buffer is erased");
    check(store.replace(replacement) ==
              WifiCredentialStoreResult::ProtectedStorageUnavailable &&
              store.erase() == WifiCredentialStoreResult::ProtectedStorageUnavailable &&
              backend.loads + backend.replacements + backend.erases ==
                  calls_before_unprotected,
          "unprotected storage cannot load, replace, erase or fall back");

    backend.protection_state =
        WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    check(store.erase() == WifiCredentialStoreResult::Ok && !backend.has_record,
          "explicit erase delegates only through verified encrypted storage");
}

void test_credential_store_rejects_corrupt_provider_record() {
    using namespace gs::hub::connectivity;
    MemoryCredentialBackend backend;
    backend.has_record = true;
    backend.persisted.ssid_size = 33;
    WifiCredentialStore store(backend);
    WifiCredentialRecord record = credential(0x77, 0x88);
    check(store.load(record) == WifiCredentialStoreResult::CorruptRecord &&
              record.ssid_size == 0 && record.password_size == 0,
          "malformed provider record is rejected and its output is erased");
}
}

int main() {
    try {
        test_bounded_retry_and_success_reset();
        test_ready_credentials_request_immediate_attempt();
        test_uncredentialed_attempt_failure_is_ignored();
        test_deadline_saturates();
        test_india_regulatory_profile_and_country_guard();
        test_bounded_authenticated_channel_discovery();
        test_protected_credential_store_fail_closed_and_atomicity();
        test_credential_store_rejects_corrupt_provider_record();
        std::cout << "GS-58 Wi-Fi reconnect checks=" << checks << " PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "GS-58 Wi-Fi reconnect FAIL: " << error.what() << '\n';
        return 1;
    }
}
