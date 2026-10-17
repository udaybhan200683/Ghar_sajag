#include "cloud_trust_provider.hpp"

#include <algorithm>
#include <limits>
#include <utility>

namespace gs::hub::target {
namespace {

bool safe_identifier(const std::string& value) {
    if (value.empty() || value.size() > 64) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
               (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.';
    });
}

bool valid_time_snapshot(Milliseconds requested_ms,
                         const TrustedHubTimeSnapshot& time) {
    return requested_ms > 0 && time.trusted &&
        time.monotonic_ms == requested_ms && time.utc_now > 0 &&
        time.boot_generation > 0;
}

bool all_zero(const std::array<std::uint8_t, 32>& nonce) {
    return std::all_of(nonce.begin(), nonce.end(),
                       [](std::uint8_t byte) { return byte == 0; });
}

}  // namespace

bool ProvisionedS3CloudTrust::valid_fingerprint(const std::string& value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(),
        [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        });
}

bool ProvisionedS3CloudTrust::valid_material(
    const S3CloudTrustMaterial& material) {
#if !defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE)
    if (material.test_only) return false;
#else
    if (!material.test_only) return false;
#endif
    return material.authority_authenticated && material.authority_active &&
        !material.authority_revoked && material.authority_revision > 0 &&
        safe_identifier(material.binding.home_id) &&
        safe_identifier(material.binding.hub_device_id) &&
        material.binding.ownership_epoch > 0 &&
        safe_identifier(material.permanent_hub_id) &&
        material.permanent_hub_id == material.binding.hub_device_id &&
        valid_fingerprint(material.certificate_fingerprint_sha256) &&
        material.client_certificate_pem.size() <= 8192 &&
        material.client_certificate_pem.find(
            "-----BEGIN CERTIFICATE-----") == 0 &&
        material.client_certificate_pem.find(
            "-----END CERTIFICATE-----") != std::string::npos &&
        material.client_certificate_pem.find("PRIVATE KEY") == std::string::npos &&
        material.ds_context != nullptr && material.rsa_bits == 3072 &&
        material.credential_generation > 0 &&
        material.credential_state == CloudCredentialState::Active &&
        material.credential_purpose == CloudCredentialPurpose::CloudTlsClient &&
        material.key_custody_verified;
}

bool ProvisionedS3CloudTrust::current_material(
    S3CloudTrustMaterial& material) const {
    std::lock_guard<std::mutex> lock(read_mutex_);
    S3CloudTrustMaterial candidate;
    if (!material_.current_material(candidate) || !valid_material(candidate))
        return false;
    material = std::move(candidate);
    return true;
}

bool ProvisionedS3CloudTrust::current_binding(CloudAuthorityBinding& binding) {
    S3CloudTrustMaterial material;
    if (!current_material(material)) return false;
    binding = material.binding;
    return true;
}

bool ProvisionedS3CloudTrust::trusted_hub_time(
    Milliseconds monotonic_ms, TrustedHubTimeSnapshot& time) {
    S3CloudTrustMaterial material;
    TrustedHubTimeSnapshot candidate;
    if (!current_material(material) ||
        !time_.trusted_hub_time(monotonic_ms, candidate) ||
        !valid_time_snapshot(monotonic_ms, candidate)) return false;
    time = candidate;
    return true;
}

bool ProvisionedS3CloudTrust::current_identity(CloudTlsIdentity& identity) {
    const auto now_ms = clock_.now_ms();
    CloudAuthorityBinding binding;
    TrustedHubTimeSnapshot trusted_time;
    S3CloudTrustMaterial material;
    if (now_ms <= 0 || !current_material(material) ||
        !current_binding(binding) ||
        binding.hub_device_id != material.permanent_hub_id ||
        !trusted_hub_time(now_ms, trusted_time)) return false;

    CloudTlsIdentity candidate;
    candidate.client_certificate_pem = material.client_certificate_pem;
    candidate.ds_context = material.ds_context;
    candidate.rsa_bits = material.rsa_bits;
    candidate.purpose = CloudTlsIdentity::Purpose::CloudTlsClient;
    candidate.permanent_hub_id = material.permanent_hub_id;
    candidate.certificate_fingerprint_sha256 =
        material.certificate_fingerprint_sha256;
    candidate.credential_generation = material.credential_generation;
    candidate.trusted_utc_seconds = trusted_time.utc_now;
    candidate.trusted_monotonic_ms = trusted_time.monotonic_ms;
    candidate.trusted_time_boot_generation = trusted_time.boot_generation;
    identity = std::move(candidate);
    return true;
}

bool AuthenticatedHubTimeProvider::start() {
    std::lock_guard<std::mutex> lock(mutex_);
    ready_ = false;
    started_ = false;
    boot_generation_ = 0;
    utc_floor_ = 0;
    highest_monotonic_ms_ = 0;
    last_floor_checkpoint_monotonic_ms_ = 0;
    monotonic_faulted_ = false;
    accepted_monotonic_ms_ = 0;
    accepted_utc_ = 0;
    expires_monotonic_ms_ = 0;

    std::uint64_t generation = 0;
    if (!store_.begin_boot(generation) || generation == 0) return false;
    EpochSeconds floor = 0;
    const auto floor_state = store_.read_floor(floor);
    if (floor_state == TrustedTimeFloorRead::Unavailable) return false;
    if (floor_state != TrustedTimeFloorRead::Valid || floor <= 0) floor = 0;
    const auto monotonic_now = clock_.now_ms();
    if (monotonic_now <= 0) return false;
    boot_generation_ = generation;
    utc_floor_ = floor;
    highest_monotonic_ms_ = monotonic_now;
    started_ = true;
    return true;
}

bool AuthenticatedHubTimeProvider::accept_authenticated_time(
    const std::vector<std::uint8_t>& proof,
    const std::array<std::uint8_t, 32>& nonce,
    Milliseconds challenge_started_monotonic_ms) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!started_ || monotonic_faulted_ || proof.empty() || proof.size() > 4096 || all_zero(nonce) ||
        policy_.max_response_age_ms <= 0 ||
        policy_.floor_checkpoint_interval_ms <= 0 ||
        challenge_started_monotonic_ms <= 0)
        return false;
    const auto now_ms = clock_.now_ms();
    if (now_ms <= 0 || now_ms < highest_monotonic_ms_) {
        monotonic_faulted_ = true;
        ready_ = false;
        return false;
    }
    highest_monotonic_ms_ = now_ms;
    if (now_ms < challenge_started_monotonic_ms ||
        now_ms - challenge_started_monotonic_ms > policy_.max_response_age_ms)
        return false;

    AuthenticatedTimeStatement statement;
    if (!verifier_.verify(proof, nonce, boot_generation_, statement) ||
        statement.issued_at_utc <= 0 || statement.valid_from_utc <= 0 ||
        statement.valid_until_utc <= statement.issued_at_utc ||
        statement.valid_from_utc > statement.issued_at_utc)
        return false;

    if (statement.issued_at_utc < utc_floor_) return false;
    // Expiry disables trusted-time reads, but it does not erase the monotonic
    // lower bound while this boot's monotonic clock is still continuous.
    // Otherwise a delayed recovery response could roll the Hub back slightly
    // after the prior signed validity interval expired.
    if (accepted_monotonic_ms_ > 0) {
        if (now_ms < accepted_monotonic_ms_) return false;
        const auto elapsed_seconds =
            static_cast<EpochSeconds>((now_ms - accepted_monotonic_ms_) / 1000);
        if (accepted_utc_ > std::numeric_limits<EpochSeconds>::max() -
                elapsed_seconds ||
            statement.issued_at_utc < accepted_utc_ + elapsed_seconds)
            return false;
    }
    ready_ = false;

    const auto validity_seconds =
        statement.valid_until_utc - statement.issued_at_utc;
    if (validity_seconds >
        (std::numeric_limits<Milliseconds>::max() - now_ms) / 1000)
        return false;
    const auto expires_ms = now_ms + validity_seconds * 1000;
    const auto new_floor = std::max(utc_floor_, statement.issued_at_utc);
    if (!store_.commit_floor(new_floor)) {
        ready_ = false;
        return false;
    }

    utc_floor_ = new_floor;
    accepted_monotonic_ms_ = now_ms;
    accepted_utc_ = statement.issued_at_utc;
    last_floor_checkpoint_monotonic_ms_ = now_ms;
    expires_monotonic_ms_ = expires_ms;
    ready_ = true;
    return true;
}

bool AuthenticatedHubTimeProvider::trusted_hub_time(
    Milliseconds monotonic_ms, TrustedHubTimeSnapshot& time) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!started_ || monotonic_faulted_ || monotonic_ms <= 0) return false;
    const auto actual_now_ms = clock_.now_ms();
    if (actual_now_ms <= 0 || actual_now_ms < highest_monotonic_ms_ ||
        monotonic_ms < highest_monotonic_ms_ || actual_now_ms < monotonic_ms) {
        monotonic_faulted_ = true;
        ready_ = false;
        return false;
    }
    highest_monotonic_ms_ = actual_now_ms;
    if (!ready_ || monotonic_ms < accepted_monotonic_ms_ ||
        actual_now_ms < accepted_monotonic_ms_ ||
        actual_now_ms > expires_monotonic_ms_) return false;

    const auto elapsed_seconds =
        static_cast<EpochSeconds>((monotonic_ms - accepted_monotonic_ms_) / 1000);
    if (accepted_utc_ > std::numeric_limits<EpochSeconds>::max() -
            elapsed_seconds) return false;
    const auto utc_now = accepted_utc_ + elapsed_seconds;
    if (utc_now < utc_floor_) return false;

    if (actual_now_ms - last_floor_checkpoint_monotonic_ms_ >=
        policy_.floor_checkpoint_interval_ms) {
        const auto checkpoint_elapsed_seconds =
            static_cast<EpochSeconds>((actual_now_ms - accepted_monotonic_ms_) / 1000);
        if (accepted_utc_ > std::numeric_limits<EpochSeconds>::max() -
                checkpoint_elapsed_seconds) return false;
        const auto checkpoint_floor = std::max(
            utc_floor_, accepted_utc_ + checkpoint_elapsed_seconds);
        if (!store_.commit_floor(checkpoint_floor)) {
            ready_ = false;
            return false;
        }
        utc_floor_ = checkpoint_floor;
        last_floor_checkpoint_monotonic_ms_ = actual_now_ms;
        if (utc_now < utc_floor_) return false;
    }

    TrustedHubTimeSnapshot candidate;
    candidate.trusted = true;
    candidate.monotonic_ms = monotonic_ms;
    candidate.utc_now = utc_now;
    candidate.boot_generation = boot_generation_;
    time = candidate;
    return true;
}

std::uint64_t AuthenticatedHubTimeProvider::boot_generation() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return boot_generation_;
}

}  // namespace gs::hub::target
