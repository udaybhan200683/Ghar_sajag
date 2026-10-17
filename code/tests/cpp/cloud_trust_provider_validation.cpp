#include "firmware/hub/target/esp32s3/cloud_trust_provider.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"

#include <atomic>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <utility>

using namespace gs::hub;
using namespace gs::hub::target;
using gs::EpochSeconds;
using gs::Milliseconds;

namespace {

constexpr AuthenticatedTimeBootstrapPolicy kTestTimePolicy{5000, 2000};

void check(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

class FakeClock final : public S3HubMonotonicClock {
public:
    Milliseconds now_ms() const override { return now.load(); }
    std::atomic<Milliseconds> now{1000};
};

class FakeMaterialSource final : public S3CloudTrustMaterialSource {
public:
    bool current_material(S3CloudTrustMaterial& out) const override {
        std::lock_guard<std::mutex> lock(mutex);
        if (!available) return false;
        out = value;
        return true;
    }
    void update(const S3CloudTrustMaterial& next) {
        std::lock_guard<std::mutex> lock(mutex);
        value = next;
    }
    mutable std::mutex mutex;
    bool available{true};
    S3CloudTrustMaterial value;
};

class FakeTimeSource final : public S3TrustedHubTimeSource {
public:
    explicit FakeTimeSource(const FakeClock& input) : clock(input) {}
    bool trusted_hub_time(Milliseconds now, TrustedHubTimeSnapshot& out) const override {
        if (!ready || now != clock.now_ms()) return false;
        out = {true, now, utc, generation};
        return true;
    }
    const FakeClock& clock;
    bool ready{false};
    EpochSeconds utc{1'800'000'000};
    std::uint64_t generation{1};
};

class MemoryTimeStore final : public AuthenticatedTimeFloorStore {
public:
    bool begin_boot(std::uint64_t& generation) override {
        if (!available) return false;
        generation = ++boot;
        return true;
    }
    TrustedTimeFloorRead read_floor(EpochSeconds& out) override {
        out = floor;
        return read_state;
    }
    bool commit_floor(EpochSeconds value) override {
        if (!available || !commit_ok || value <= 0 || value < floor) return false;
        floor = value;
        read_state = TrustedTimeFloorRead::Valid;
        return true;
    }
    bool available{true};
    bool commit_ok{true};
    std::uint64_t boot{0};
    EpochSeconds floor{0};
    TrustedTimeFloorRead read_state{TrustedTimeFloorRead::Missing};
};

class FakeProofVerifier final : public AuthenticatedTimeProofVerifier {
public:
    bool verify(const std::vector<std::uint8_t>& proof,
                const std::array<std::uint8_t, 32>& nonce,
                std::uint64_t boot_generation,
                AuthenticatedTimeStatement& out) const override {
        if (!signature_valid || proof != std::vector<std::uint8_t>{0x47, 0x53} ||
            nonce != expected_nonce || boot_generation != expected_boot) return false;
        if (has_verified_nonce && last_boot == boot_generation &&
            last_nonce == nonce) return false;
        last_nonce = nonce;
        last_boot = boot_generation;
        has_verified_nonce = true;
        out = statement;
        return true;
    }
    bool signature_valid{true};
    std::array<std::uint8_t, 32> expected_nonce{};
    std::uint64_t expected_boot{1};
    mutable std::array<std::uint8_t, 32> last_nonce{};
    mutable std::uint64_t last_boot{0};
    mutable bool has_verified_nonce{false};
    AuthenticatedTimeStatement statement{1'800'000'000, 1'800'000'000,
                                         1'800'000'010};
};

S3CloudTrustMaterial valid_material() {
    S3CloudTrustMaterial material;
    material.binding = {"home-a", "hub-permanent-1", 7};
    material.authority_revision = 11;
    material.authority_authenticated = true;
    material.authority_active = true;
    material.permanent_hub_id = "hub-permanent-1";
    material.certificate_fingerprint_sha256 = std::string(64, 'a');
    material.client_certificate_pem =
        "-----BEGIN CERTIFICATE-----\nTEST ONLY\n-----END CERTIFICATE-----\n";
    material.ds_context = reinterpret_cast<void*>(0x1);
    material.rsa_bits = 3072;
    material.credential_generation = 3;
    material.credential_state = CloudCredentialState::Active;
    material.credential_purpose = CloudCredentialPurpose::CloudTlsClient;
    material.key_custody_verified = true;
    material.test_only = true;
    return material;
}

void test_identity_and_ownership_provider() {
    FakeClock clock;
    FakeTimeSource time{clock};
    FakeMaterialSource source;
    source.value = valid_material();
    ProvisionedS3CloudTrust provider(source, time, clock);

    CloudAuthorityBinding binding;
    check(provider.current_binding(binding) && binding == source.value.binding,
          "active verified Home binding is available");
    CloudTlsIdentity identity;
    check(!provider.current_identity(identity),
          "TLS identity is blocked before trusted time");
    time.ready = true;
    check(provider.current_identity(identity) &&
          identity.permanent_hub_id == "hub-permanent-1" &&
          identity.certificate_fingerprint_sha256 == std::string(64, 'a') &&
          identity.credential_generation == 3 && identity.rsa_bits == 3072 &&
          identity.ds_context == reinterpret_cast<void*>(0x1),
          "current dedicated cloud credential is returned without private key");

    const auto original = binding;
    auto next = source.value;
    next.binding.home_id = "home-b";
    next.binding.ownership_epoch = 8;
    next.authority_revision++;
    source.update(next);
    check(provider.current_binding(binding) && binding.home_id == "home-b" &&
          binding.ownership_epoch == 8 && !(binding == original),
          "authority transfer replaces immutable current binding");

    std::atomic<bool> start{false};
    std::atomic<unsigned> invalid_reads{0};
    std::vector<std::thread> readers;
    for (unsigned i = 0; i < 4; ++i) {
        readers.emplace_back([&] {
            while (!start.load()) std::this_thread::yield();
            for (unsigned n = 0; n < 500; ++n) {
                CloudAuthorityBinding observed;
                if (provider.current_binding(observed) &&
                    (observed.home_id.empty() || observed.ownership_epoch == 0))
                    invalid_reads.fetch_add(1);
            }
        });
    }
    start.store(true);
    next.authority_active = false;
    next.authority_revoked = true;
    next.authority_revision++;
    source.update(next);
    for (auto& reader : readers) reader.join();
    check(invalid_reads.load() == 0, "concurrent revocation never returns partial binding");
    check(!provider.current_binding(binding) && !provider.current_identity(identity),
          "revoked binding disables identity and publication authority");
}

void test_identity_negative_matrix() {
    FakeClock clock;
    FakeTimeSource time{clock};
    time.ready = true;
    const auto baseline = valid_material();
    const std::vector<std::pair<const char*, std::function<void(S3CloudTrustMaterial&)>>> mutations{
        {"wrong permanent Hub", [](auto& x) { x.permanent_hub_id = "other-hub"; }},
        {"wrong binding Hub", [](auto& x) { x.binding.hub_device_id = "other-hub"; }},
        {"empty Home", [](auto& x) { x.binding.home_id.clear(); }},
        {"zero epoch", [](auto& x) { x.binding.ownership_epoch = 0; }},
        {"missing authority proof", [](auto& x) { x.authority_authenticated = false; }},
        {"inactive authority", [](auto& x) { x.authority_active = false; }},
        {"revoked authority", [](auto& x) { x.authority_revoked = true; }},
        {"zero authority revision", [](auto& x) { x.authority_revision = 0; }},
        {"revoked credential", [](auto& x) { x.credential_state = CloudCredentialState::Revoked; }},
        {"quarantined credential", [](auto& x) { x.credential_state = CloudCredentialState::Quarantined; }},
        {"wrong credential purpose", [](auto& x) { x.credential_purpose = CloudCredentialPurpose::Commissioning; }},
        {"wrong RSA size", [](auto& x) { x.rsa_bits = 2048; }},
        {"missing DS context", [](auto& x) { x.ds_context = nullptr; }},
        {"missing custody evidence", [](auto& x) { x.key_custody_verified = false; }},
        {"malformed fingerprint", [](auto& x) { x.certificate_fingerprint_sha256 = "00"; }},
        {"private key in certificate field", [](auto& x) { x.client_certificate_pem += "PRIVATE KEY"; }},
        {"missing certificate", [](auto& x) { x.client_certificate_pem.clear(); }},
        {"zero credential generation", [](auto& x) { x.credential_generation = 0; }},
        {"non-test fixture in test build", [](auto& x) { x.test_only = false; }},
    };
    for (const auto& mutation : mutations) {
        FakeMaterialSource source;
        source.value = baseline;
        mutation.second(source.value);
        ProvisionedS3CloudTrust provider(source, time, clock);
        CloudAuthorityBinding binding;
        CloudTlsIdentity identity;
        check(!provider.current_binding(binding) && !provider.current_identity(identity),
              mutation.first);
    }
}

void test_authenticated_time_bootstrap_and_recovery() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x5a;
    verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider time(store, verifier, clock, kTestTimePolicy);
    check(time.start() && time.boot_generation() == 1,
          "cold boot advances durable boot generation");
    TrustedHubTimeSnapshot snapshot;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "cold boot without authenticated time remains untrusted");
    auto wrong_nonce = nonce;
    wrong_nonce[0]++;
    check(!time.accept_authenticated_time({0x47, 0x53}, wrong_nonce, clock.now_ms()),
          "proof bound to another nonce is rejected");
    check(!time.accept_authenticated_time({0x47, 0x53}, {}, clock.now_ms()),
          "empty nonce is rejected");
    check(time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          time.trusted_hub_time(clock.now_ms(), snapshot) &&
          snapshot.utc_now == 1'800'000'000 && snapshot.boot_generation == 1,
          "verified startup time is persisted before readiness");
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "authenticated time proof cannot reuse a one-use nonce");
    clock.now = 3500;
    check(time.trusted_hub_time(clock.now_ms(), snapshot) &&
          snapshot.utc_now == 1'800'000'002 && store.floor == snapshot.utc_now,
          "trusted time follows monotonic elapsed time and checkpoints its durable floor");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'799'999'999, 1'799'999'999, 1'800'000'020};
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "authenticated time rollback is rejected");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'002, 1'800'000'003, 1'800'000'020};
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "not-yet-valid authenticated time statement is rejected");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'002, 1'800'000'002, 1'800'000'020};
    check(time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "fresh authenticated time restores expired network session");

    clock.now = 22'501;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "trusted time expires at signed validity bound during outage");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'020, 1'800'000'020, 1'800'000'030};
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "expired-session recovery cannot roll back monotonic elapsed time");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'021, 1'800'000'021, 1'800'000'031};
    check(time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          time.trusted_hub_time(clock.now_ms(), snapshot),
          "network recovery accepts a newer authenticated time statement");
}

void test_authenticated_time_corruption_reboot_and_failures() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x2a;
    verifier.expected_nonce = nonce;

    AuthenticatedHubTimeProvider first(store, verifier, clock, kTestTimePolicy);
    check(first.start(), "missing floor permits fail-closed startup");
    check(first.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "fresh signed time repairs missing floor");
    const auto first_floor = store.floor;

    AuthenticatedHubTimeProvider rebooted(store, verifier, clock, kTestTimePolicy);
    check(rebooted.start() && rebooted.boot_generation() == 2,
          "restart advances persistent boot generation");
    TrustedHubTimeSnapshot snapshot;
    check(!rebooted.trusted_hub_time(clock.now_ms(), snapshot),
          "persisted floor does not masquerade as current after restart");
    verifier.expected_boot = 2;
    verifier.statement = {first_floor - 1, first_floor - 1, first_floor + 10};
    check(!rebooted.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "reboot proof below persistent floor is rejected");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {first_floor + 1, first_floor + 1, first_floor + 20};
    check(rebooted.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "fresh post-reboot signed time restores readiness");

    store.read_state = TrustedTimeFloorRead::Corrupt;
    AuthenticatedHubTimeProvider recovered(store, verifier, clock, kTestTimePolicy);
    check(recovered.start() &&
          !recovered.trusted_hub_time(clock.now_ms(), snapshot),
          "corrupt stored time never establishes startup trust");
    verifier.expected_boot = 3;
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {first_floor + 2, first_floor + 2, first_floor + 30};
    check(recovered.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          store.read_state == TrustedTimeFloorRead::Valid,
          "new authenticated proof atomically repairs corrupt floor");

    MemoryTimeStore unavailable;
    unavailable.available = false;
    AuthenticatedHubTimeProvider no_counter(unavailable, verifier, clock);
    check(!no_counter.start(), "missing durable boot counter fails closed");

    MemoryTimeStore write_failure;
    FakeProofVerifier write_failure_verifier;
    write_failure_verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider no_commit(write_failure, write_failure_verifier,
                                           clock, kTestTimePolicy);
    check(no_commit.start(), "time provider starts without current time");
    write_failure_verifier.expected_boot = 1;
    write_failure.commit_ok = false;
    write_failure_verifier.statement = {1'900'000'000, 1'900'000'000,
                                        1'900'000'010};
    check(!no_commit.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          !no_commit.trusted_hub_time(clock.now_ms(), snapshot),
          "time persistence failure prevents readiness");

    FakeProofVerifier invalid_verifier;
    invalid_verifier.expected_nonce = nonce;
    invalid_verifier.signature_valid = false;
    MemoryTimeStore invalid_store;
    AuthenticatedHubTimeProvider invalid_proof(invalid_store, invalid_verifier, clock,
                                               kTestTimePolicy);
    check(invalid_proof.start() &&
          !invalid_proof.accept_authenticated_time({0x47, 0x53}, nonce,
                                                   clock.now_ms()),
          "unauthenticated proof is rejected");

    MemoryTimeStore delayed_store;
    FakeClock delayed_clock;
    FakeProofVerifier delayed_verifier;
    delayed_verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider delayed(delayed_store, delayed_verifier,
                                         delayed_clock, kTestTimePolicy);
    check(delayed.start(), "delayed-proof fixture starts without time");
    const auto challenge_started = delayed_clock.now_ms();
    delayed_clock.now = challenge_started + kTestTimePolicy.max_response_age_ms + 1;
    check(!delayed.accept_authenticated_time({0x47, 0x53}, nonce,
                                              challenge_started),
          "proof response outside the injected freshness window is rejected");
    delayed_clock.now = 1000;
    AuthenticatedHubTimeProvider no_approved_window(delayed_store, delayed_verifier,
                                                     delayed_clock);
    check(no_approved_window.start() &&
          !no_approved_window.accept_authenticated_time({0x47, 0x53}, nonce,
                                                          delayed_clock.now_ms()),
          "missing D06 freshness policy remains fail closed");
    AuthenticatedHubTimeProvider no_floor_checkpoint(
        delayed_store, delayed_verifier, delayed_clock,
        AuthenticatedTimeBootstrapPolicy{5000, 0});
    check(no_floor_checkpoint.start() &&
          !no_floor_checkpoint.accept_authenticated_time(
              {0x47, 0x53}, nonce, delayed_clock.now_ms()),
          "missing D06 durable-floor checkpoint policy remains fail closed");

    MemoryTimeStore zero_window_store;
    FakeProofVerifier zero_window_verifier;
    zero_window_verifier.expected_nonce = nonce;
    zero_window_verifier.statement = {1'800'000'000, 1'800'000'000,
                                      1'800'000'000};
    AuthenticatedHubTimeProvider zero_window(
        zero_window_store, zero_window_verifier, delayed_clock, kTestTimePolicy);
    check(zero_window.start() &&
          !zero_window.accept_authenticated_time({0x47, 0x53}, nonce,
                                                  delayed_clock.now_ms()),
          "zero-length signed validity window is rejected");
}

void test_same_boot_clock_rollback_latches_fail_closed() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x31;
    verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider time(store, verifier, clock, kTestTimePolicy);
    check(time.start() &&
          time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "rollback fixture reaches authenticated time");
    TrustedHubTimeSnapshot snapshot;
    clock.now = 999;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "same-boot monotonic rollback is rejected");
    clock.now = 1000;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "monotonic rollback remains fail-closed for the boot");
}

void test_provider_to_nodehealth_cloudsync_path() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x73;
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'000, 1'800'000'000, 1'800'100'000};
    AuthenticatedHubTimeProvider trusted_time(store, verifier, clock, kTestTimePolicy);
    check(trusted_time.start(), "integrated provider starts without trusted time");

    FakeMaterialSource material;
    material.value = valid_material();
    class CombinedTime final : public S3TrustedHubTimeSource {
    public:
        explicit CombinedTime(AuthenticatedHubTimeProvider& source) : source_(source) {}
        bool trusted_hub_time(Milliseconds now,
                              TrustedHubTimeSnapshot& out) const override {
            return source_.trusted_hub_time(now, out);
        }
    private:
        AuthenticatedHubTimeProvider& source_;
    } combined_time(trusted_time);

    ProvisionedS3CloudTrust cloud_trust(material, combined_time, clock);
    CloudAuthorityBinding pre_recovery_binding;
    check(cloud_trust.current_binding(pre_recovery_binding) &&
          pre_recovery_binding.ownership_epoch == 7,
          "current Home authority is available while time is untrusted");
    auto transferred_during_recovery = material.value;
    transferred_during_recovery.binding.home_id = "home-b";
    transferred_during_recovery.binding.ownership_epoch++;
    transferred_during_recovery.authority_revision++;
    material.update(transferred_during_recovery);
    check(trusted_time.accept_authenticated_time({0x47, 0x53}, nonce,
                                                 clock.now_ms()),
          "authenticated time recovers after an ownership-epoch change");
    CloudAuthorityBinding recovered_binding;
    check(cloud_trust.current_binding(recovered_binding) &&
          recovered_binding.home_id == "home-b" &&
          recovered_binding.ownership_epoch == 8,
          "recovery exposes only the latest Home authority epoch");
    CloudTlsIdentity identity;
    check(cloud_trust.current_identity(identity) &&
          identity.permanent_hub_id == "hub-permanent-1",
          "S3 TLS credential and authenticated time resolve together");

    struct Authority final : CloudRuntimeAuthorityProvider {
        explicit Authority(ProvisionedS3CloudTrust& provider) : provider(provider) {}
        ProvisionedS3CloudTrust& provider;
        std::vector<CloudNodeEnrollment> nodes{{"node-physical", "room-a", 4, 55,
                                                 "configured", 300, 910}};
        bool current_binding(CloudAuthorityBinding& out) override {
            return provider.current_binding(out);
        }
        bool original_event_owned(const gs::DomainEvent&,
                                  const CloudAuthorityBinding& binding) override {
            CloudAuthorityBinding current;
            return provider.current_binding(current) && current == binding;
        }
        bool trusted_hub_time(Milliseconds now,
                              TrustedHubTimeSnapshot& out) override {
            return provider.trusted_hub_time(now, out);
        }
        bool active_nodes(const CloudAuthorityBinding& binding,
                          std::vector<CloudNodeEnrollment>& out) override {
            CloudAuthorityBinding current;
            if (!provider.current_binding(current) || !(current == binding)) return false;
            out = nodes;
            return true;
        }
    } authority(cloud_trust);

    struct Transport final : CloudBackendTransport {
        unsigned sent{0};
        CloudAuthorityBinding last_binding;
        NodeHealthPublication last_status;
        BackendCommitReply submit(const BackendCommitRequest&) override { return {}; }
        NodeHealthReply submit_node_health(const CloudAuthorityBinding& binding,
                                           const NodeHealthPublication& status) override {
            ++sent;
            last_binding = binding;
            last_status = status;
            return {NodeHealthReplyStatus::Accepted};
        }
    } transport;

    HubRuntime runtime;
    constexpr Milliseconds now_ms = 1000;
    clock.now = now_ms;
    runtime.authorize_node("room-a", 55, true);
    runtime.set_node_offline_timeout("room-a", 910);
    check(runtime.observe_authenticated_contact("room-a", 55, now_ms, 0,
          CloudContactKind::NodeHealth),
          "authenticated current-session Node contact enters HubRuntime");

    CloudRuntimeAuthoritySource authority_source(authority);
    CloudSyncWorker worker(runtime.journal(), runtime, authority_source, transport);
    check(worker.refresh_node_health_snapshot(now_ms),
          "credential and time providers authorize owner snapshot composition");
    const auto published = worker.run_node_health_once(true, now_ms);
    check(published.node_health_submitted == 1 &&
          published.node_health_accepted == 1 && transport.sent == 1 &&
          transport.last_status.valid() &&
          transport.last_binding == material.value.binding &&
          transport.last_status.physical_node_id == "node-physical" &&
          transport.last_status.offline_seconds == 910,
          "authenticated Node contact reaches bounded CloudSync status transport");

    auto transferred = material.value;
    transferred.binding.home_id = "home-c";
    transferred.binding.ownership_epoch++;
    transferred.authority_revision++;
    material.update(transferred);
    const auto after_transfer = worker.run_node_health_once(true, now_ms + 1);
    check(after_transfer.state == CloudWorkerState::AuthorityChanged &&
          transport.sent == 1,
          "Home transfer fences the pinned worker before another publication");
}

}  // namespace

int main() {
    try {
        test_identity_and_ownership_provider();
        std::cout << "GS68-D05-AUTHORITY-PROVIDER PASS\n";
        test_identity_negative_matrix();
        std::cout << "GS68-D12-CREDENTIAL-PROVIDER PASS\n";
        test_authenticated_time_bootstrap_and_recovery();
        test_authenticated_time_corruption_reboot_and_failures();
        test_same_boot_clock_rollback_latches_fail_closed();
        std::cout << "GS68-D06-TIME-STATE-MACHINE PASS\n";
        test_provider_to_nodehealth_cloudsync_path();
        std::cout << "GS40-PROVIDER-CLOUDSYNC-INTEGRATION PASS\n";
        std::cout << "GS-CLOUD-TRUST-PROVIDER PASS suites=5 physical=NOT_RUN\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "GS-CLOUD-TRUST-PROVIDER FAIL " << error.what() << '\n';
        return 1;
    }
}
