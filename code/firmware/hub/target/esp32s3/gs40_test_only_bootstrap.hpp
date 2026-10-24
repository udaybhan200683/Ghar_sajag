#pragma once

#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
#error "GS-40 TEST_ONLY bootstrap must never be compiled into commercial builds"
#endif

#include "cloud_trust_provider.hpp"
#include <array>
#include <cstdint>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace gs::hub::target {

// TEST_ONLY accepts the preserved HOST_SIM namespace and the physical
// MAC-derived `hub-<12 lowercase hex>` namespace. These are syntax checks only;
// target code must additionally match the actual HubSecurityLink identity and
// backend authorization must continue to prove certificate ownership, Home,
// epoch and enrollment.
bool gs40_test_only_hub_id_allowed(const std::string& hub_id);
bool gs40_test_only_hub_id_matches_runtime(const std::string& configured_hub_id,
                                           const std::string& runtime_hub_id);

// Secrets in this value are transient TEST_ONLY inputs. Do not serialize this
// object, log it, or persist it. Destruction overwrites the secret strings.
struct Gs40TestOnlyRuntimeConfig {
    std::string wifi_ssid;
    std::string wifi_psk;
    std::string backend_origin;
    std::string backend_hostname;
    std::string backend_ca_pem;
    std::string time_host;
    std::uint16_t time_port{0};
    std::vector<std::uint8_t> time_public_key_der;
    std::vector<std::uint8_t> authority_public_key_der;
    std::string permanent_hub_id;
    std::string client_certificate_pem;
    std::string client_private_key_pem;
    std::string credential_fingerprint_sha256;
    std::uint64_t credential_generation{0};
    std::uint64_t envelope_generation{0};
    std::uint64_t envelope_expiry_utc{0};
    // Optional authenticated Home behavior snapshot used only by the isolated
    // GS-40 product profile. It is enabled only when the signed envelope's
    // Home matches the live authority lease. The bounded target timezone adapter
    // supports Etc/UTC and Asia/Kolkata only and fails closed for other zones.
    std::string activity_home_id;
    std::string household_timezone;
    ActivityRuleConfig activity_rules{};
    HomeMode home_mode{HomeMode::Home};
    bool activity_rules_present{false};

    Gs40TestOnlyRuntimeConfig() = default;
    Gs40TestOnlyRuntimeConfig(const Gs40TestOnlyRuntimeConfig&) = delete;
    Gs40TestOnlyRuntimeConfig& operator=(const Gs40TestOnlyRuntimeConfig&) = delete;
    Gs40TestOnlyRuntimeConfig(Gs40TestOnlyRuntimeConfig&&) noexcept;
    Gs40TestOnlyRuntimeConfig& operator=(Gs40TestOnlyRuntimeConfig&&) noexcept;
    ~Gs40TestOnlyRuntimeConfig();
    bool valid_shape() const;
    bool valid_material_shape() const;
    bool valid_activity_rules_shape() const;
    void clear_wifi_secret();
};

// Deterministic conversion for explicitly supported TEST_ONLY household zones.
// The input must already be authenticated trusted UTC; this function does not
// establish time trust or accept host/local wall-clock time.
bool gs40_test_only_local_minute_from_utc(const std::string& timezone,
    EpochSeconds trusted_utc, std::uint16_t& local_minute);

// GS40T/1 config envelope. Public key is the TEST_ONLY config-signing root DER
// supplied to this isolated build; the matching private key stays host-side.
// A fresh target challenge and P-256 ECDH session key bind each envelope.
class Gs40TestOnlyEnvelopeSession {
public:
    explicit Gs40TestOnlyEnvelopeSession(std::vector<std::uint8_t> root_public_key_der);
    ~Gs40TestOnlyEnvelopeSession();
    Gs40TestOnlyEnvelopeSession(const Gs40TestOnlyEnvelopeSession&) = delete;
    Gs40TestOnlyEnvelopeSession& operator=(const Gs40TestOnlyEnvelopeSession&) = delete;

    bool begin(std::array<std::uint8_t, 32>& challenge,
               std::vector<std::uint8_t>& target_public_key_sec1);
    bool accept(const std::vector<std::uint8_t>& envelope,
                Gs40TestOnlyRuntimeConfig& config);
    void clear();

    static constexpr std::size_t kMaximumEnvelopeBytes = 24576;
    static constexpr std::size_t kMaximumPlaintextBytes = 16384;
private:
    std::vector<std::uint8_t> root_public_key_der_;
    std::array<std::uint8_t, 32> challenge_{};
    std::vector<std::uint8_t> private_key_der_;
    std::uint32_t key_id_{0};
    bool active_{false};
};

// TEST_ONLY current authority snapshot. The lease is issued only by a
// certificate-authenticated, CA/hostname-verified authority refresh response.
// Backend ingest independently rechecks ownership/revocation transactionally.
struct Gs40TestOnlyAuthorityLease {
    CloudAuthorityBinding binding;
    std::uint64_t authority_revision{0};
    std::uint64_t credential_generation{0};
    std::string certificate_fingerprint_sha256;
    std::uint64_t expires_monotonic_ms{0};
    std::uint64_t boot_generation{0};
    bool active{false};
    bool revoked{false};
};

class Gs40TestOnlyAuthorityLeaseVerifier {
public:
    explicit Gs40TestOnlyAuthorityLeaseVerifier(
        std::vector<std::uint8_t> public_key_der)
        : public_key_der_(std::move(public_key_der)) {}
    bool verify(const std::string& response,
                const std::array<std::uint8_t, 32>& nonce,
                std::uint64_t boot_generation, std::uint64_t now_utc,
                std::uint64_t now_monotonic_ms,
                Gs40TestOnlyAuthorityLease& lease) const;
private:
    const std::vector<std::uint8_t> public_key_der_;
};

class Gs40TestOnlyMaterialSource final : public S3CloudTrustMaterialSource {
public:
    Gs40TestOnlyMaterialSource(Gs40TestOnlyRuntimeConfig&& config,
                               const S3TrustedHubTimeSource& time,
                               const S3HubMonotonicClock& clock);
    bool install_authority_lease(const Gs40TestOnlyAuthorityLease& lease,
                                std::uint64_t now_monotonic_ms,
                                std::uint64_t current_boot_generation);
    void invalidate();
    bool current_material(S3CloudTrustMaterial& material) const override;
    bool bootstrap_identity(const TrustedHubTimeSnapshot& time,
                            CloudTlsIdentity& identity) const;
    const Gs40TestOnlyRuntimeConfig& config() const { return config_; }
private:
    static constexpr std::uint64_t kLeaseMaximumMs = 60000;
    mutable std::mutex mutex_;
    Gs40TestOnlyRuntimeConfig config_;
    const S3TrustedHubTimeSource& time_;
    const S3HubMonotonicClock& clock_;
    Gs40TestOnlyAuthorityLease lease_;
    bool lease_ready_{false};
};

// Initial mTLS identity is allowed to call only the test authority refresh
// endpoint. It cannot provide a Home binding or authorize CloudSync.
class Gs40TestOnlyBootstrapIdentityProvider final : public CloudTlsIdentityProvider {
public:
    Gs40TestOnlyBootstrapIdentityProvider(const Gs40TestOnlyMaterialSource& material,
        const S3TrustedHubTimeSource& time, const S3HubMonotonicClock& clock)
        : material_(material), time_(time), clock_(clock) {}
    bool current_identity(CloudTlsIdentity& identity) override;
private:
    const Gs40TestOnlyMaterialSource& material_;
    const S3TrustedHubTimeSource& time_;
    const S3HubMonotonicClock& clock_;
};

// One composition shared by product startup and the host vertical. Endpoint
// material must come from its live owner after the initial config was moved.
struct Gs40TestOnlyCloudComposition {
    Gs40TestOnlyBootstrapIdentityProvider bootstrap_identity;
    ProvisionedS3CloudTrust trust;
    HttpsBackendChannel bootstrap_channel;
    HttpsBackendChannel cloud_channel;
    Gs40TestOnlyCloudComposition(Gs40TestOnlyMaterialSource& material,
        const S3TrustedHubTimeSource& time, const S3HubMonotonicClock& clock)
        : bootstrap_identity(material, time, clock), trust(material, time, clock),
          bootstrap_channel(material.config().backend_origin,
              material.config().backend_ca_pem, bootstrap_identity),
          cloud_channel(material.config().backend_origin,
              material.config().backend_ca_pem, trust) {}
};

bool gs40_test_only_refresh_authority(
    Gs40TestOnlyMaterialSource& material,
    const S3TrustedHubTimeSource& time,
    const S3HubMonotonicClock& clock,
    AuthenticatedTimeRandomSource& random,
    HttpsBackendChannel& channel,
    Gs40TestOnlyAuthorityLeaseVerifier& verifier);

}  // namespace gs::hub::target
