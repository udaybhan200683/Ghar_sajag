#pragma once

#include "firmware/hub/cloud_sync/cloud_sync.hpp"
#include "firmware/hub/target/esp32s3/https_backend_channel.hpp"

#include <array>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

namespace gs::hub::target {

enum class CloudCredentialState : std::uint8_t {
    Unavailable,
    Active,
    Revoked,
    Quarantined,
};

enum class CloudCredentialPurpose : std::uint8_t {
    Unspecified,
    CloudTlsClient,
    Commissioning,
};

// One atomic, immutable read of the device-specific identity and current
// backend-authorized Home binding. The source is the trusted provisioning /
// authority boundary; it must return false when its registry proof is stale,
// revoked, corrupt, or cannot be authenticated. This adapter does not infer
// authority from MAC, serial, QR, HTTP headers, or Node commissioning keys.
struct S3CloudTrustMaterial {
    CloudAuthorityBinding binding;
    std::uint64_t authority_revision{0};
    bool authority_authenticated{false};
    bool authority_active{false};
    bool authority_revoked{false};

    std::string permanent_hub_id;
    std::string certificate_fingerprint_sha256;
    std::string client_certificate_pem;
    void* ds_context{nullptr};
    unsigned rsa_bits{0};
    std::uint64_t credential_generation{0};
    CloudCredentialState credential_state{CloudCredentialState::Unavailable};
    CloudCredentialPurpose credential_purpose{CloudCredentialPurpose::Unspecified};
    // Set only by the approved provisioning/key-custody source after it has
    // verified the per-device DS context and its cloud-only purpose. A pointer
    // to ESP-IDF DS data by itself is not evidence of protected key custody.
    bool key_custody_verified{false};
    bool test_only{false};
};

class S3CloudTrustMaterialSource {
public:
    virtual ~S3CloudTrustMaterialSource() = default;
    // Return one atomic immutable identity/authority/credential generation.
    // Certificate storage and DS context must remain valid until an in-flight
    // HTTPS request using that generation has completed; revocation fences new
    // snapshots immediately and defers reclamation until readers drain.
    virtual bool current_material(S3CloudTrustMaterial& material) const = 0;
};

class S3HubMonotonicClock {
public:
    virtual ~S3HubMonotonicClock() = default;
    virtual Milliseconds now_ms() const = 0;
};

class S3TrustedHubTimeSource {
public:
    virtual ~S3TrustedHubTimeSource() = default;
    virtual bool trusted_hub_time(Milliseconds monotonic_ms,
                                  TrustedHubTimeSnapshot& time) const = 0;
};

class S3CloudTrustProvisioning {
public:
    virtual ~S3CloudTrustProvisioning() = default;
    virtual bool current_binding(CloudAuthorityBinding& binding) = 0;
    virtual bool trusted_hub_time(Milliseconds monotonic_ms,
                                  TrustedHubTimeSnapshot& time) = 0;
};

// Production-capable fail-closed adapter for GS-109/GS-68 factory and current
// ownership providers. It deliberately contains no key loader, CA, issuer,
// credentials, Home claim flow, or untrusted clock fallback.
class ProvisionedS3CloudTrust final : public S3CloudTrustProvisioning,
                                     public CloudTlsIdentityProvider {
public:
    ProvisionedS3CloudTrust(const S3CloudTrustMaterialSource& material,
                            const S3TrustedHubTimeSource& time,
                            const S3HubMonotonicClock& clock)
        : material_(material), time_(time), clock_(clock) {}

    bool current_binding(CloudAuthorityBinding& binding) override;
    bool trusted_hub_time(Milliseconds monotonic_ms,
                          TrustedHubTimeSnapshot& time) override;
    bool current_identity(CloudTlsIdentity& identity) override;

private:
    bool current_material(S3CloudTrustMaterial& material) const;
    static bool valid_material(const S3CloudTrustMaterial& material);
    static bool valid_fingerprint(const std::string& fingerprint);

    const S3CloudTrustMaterialSource& material_;
    const S3TrustedHubTimeSource& time_;
    const S3HubMonotonicClock& clock_;
    mutable std::mutex read_mutex_;
};

class UnprovisionedS3CloudTrust final : public S3CloudTrustProvisioning,
                                       public CloudTlsIdentityProvider {
public:
    bool current_binding(CloudAuthorityBinding&) override { return false; }
    bool trusted_hub_time(Milliseconds, TrustedHubTimeSnapshot&) override { return false; }
    bool current_identity(CloudTlsIdentity&) override { return false; }
};

enum class TrustedTimeFloorRead : std::uint8_t {
    Valid,
    Missing,
    Corrupt,
    Unavailable,
};

struct AuthenticatedTimeStatement {
    EpochSeconds issued_at_utc{0};
    EpochSeconds valid_from_utc{0};
    EpochSeconds valid_until_utc{0};
};

// The store must advance boot_generation atomically and durably, and persist
// the time floor atomically. Implementations must fail closed on storage or
// anti-rollback-counter failure. No production NVS namespace is selected here.
class AuthenticatedTimeFloorStore {
public:
    virtual ~AuthenticatedTimeFloorStore() = default;
    virtual bool begin_boot(std::uint64_t& boot_generation) = 0;
    virtual TrustedTimeFloorRead read_floor(EpochSeconds& utc_floor) = 0;
    virtual bool commit_floor(EpochSeconds utc_floor) = 0;
};

// A verifier must authenticate the approved time authority independently of
// TLS certificate validity, bind the exact 32-byte one-use nonce and current
// boot generation, and validate the signed validity interval. No verifier or
// trust anchor is enabled by the S3 product composition yet.
class AuthenticatedTimeProofVerifier {
public:
    virtual ~AuthenticatedTimeProofVerifier() = default;
    virtual bool verify(const std::vector<std::uint8_t>& proof,
                        const std::array<std::uint8_t, 32>& nonce,
                        std::uint64_t boot_generation,
                        AuthenticatedTimeStatement& statement) const = 0;
};

struct AuthenticatedTimeBootstrapPolicy {
    // Both values are required before readiness: one limits authenticated
    // bootstrap response age, the other bounds durable floor writes. Production
    // thresholds require the D06 owner decision; tests inject TEST_ONLY values.
    Milliseconds max_response_age_ms{0};
    // Persist a monotonic UTC high-water mark at this interval. Zero leaves the
    // provider fail closed because the post-reboot rollback bound would not be
    // maintained. The production wear/freshness tradeoff remains a D06 decision.
    Milliseconds floor_checkpoint_interval_ms{0};
};

// Startup and recovery state machine for D06. A persisted floor alone never
// establishes current time after reboot; a new authenticated, nonce-bound
// statement is required. SNTP and wall-clock input are not accepted here.
class AuthenticatedHubTimeProvider final : public S3TrustedHubTimeSource {
public:
    AuthenticatedHubTimeProvider(AuthenticatedTimeFloorStore& store,
                                 const AuthenticatedTimeProofVerifier& verifier,
                                 const S3HubMonotonicClock& clock,
                                 AuthenticatedTimeBootstrapPolicy policy = {})
        : store_(store), verifier_(verifier), clock_(clock), policy_(policy) {}

    bool start();
    // The bootstrap caller supplies a nonce from the approved CSPRNG and the
    // monotonic time captured when that one-use challenge was created. The
    // verifier must reject nonce reuse, including within the current boot.
    bool accept_authenticated_time(const std::vector<std::uint8_t>& proof,
                                   const std::array<std::uint8_t, 32>& nonce,
                                   Milliseconds challenge_started_monotonic_ms);
    bool trusted_hub_time(Milliseconds monotonic_ms,
                          TrustedHubTimeSnapshot& time) const override;
    std::uint64_t boot_generation() const;

private:
    AuthenticatedTimeFloorStore& store_;
    const AuthenticatedTimeProofVerifier& verifier_;
    const S3HubMonotonicClock& clock_;
    const AuthenticatedTimeBootstrapPolicy policy_;
    mutable std::mutex mutex_;
    bool started_{false};
    mutable bool ready_{false};
    std::uint64_t boot_generation_{0};
    mutable EpochSeconds utc_floor_{0};
    mutable Milliseconds highest_monotonic_ms_{0};
    mutable Milliseconds last_floor_checkpoint_monotonic_ms_{0};
    mutable bool monotonic_faulted_{false};
    Milliseconds accepted_monotonic_ms_{0};
    EpochSeconds accepted_utc_{0};
    Milliseconds expires_monotonic_ms_{0};
};

}  // namespace gs::hub::target
