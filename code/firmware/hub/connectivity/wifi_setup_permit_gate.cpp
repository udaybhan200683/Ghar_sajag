#include "firmware/hub/connectivity/wifi_setup_permit_gate.hpp"

#include <algorithm>

namespace gs::hub::connectivity {
namespace {
bool nonzero(const std::uint8_t* data, std::size_t size) {
    std::uint8_t aggregate = 0;
    for (std::size_t i = 0; i < size; ++i) aggregate |= data[i];
    return aggregate != 0;
}

bool same_challenge(const WifiSetupChallenge& a, const WifiSetupChallenge& b) {
    if (a.hub_id_size > a.hub_id.size() || b.hub_id_size > b.hub_id.size() ||
        a.home_id_size > a.home_id.size() || b.home_id_size > b.home_id.size())
        return false;
    return a.hub_id_size == b.hub_id_size && a.home_id_size == b.home_id_size &&
        a.ownership_epoch == b.ownership_epoch && a.operation == b.operation &&
        a.boot_generation == b.boot_generation &&
        a.security2_session_id == b.security2_session_id &&
        a.created_at_ms == b.created_at_ms &&
        std::equal(a.hub_id.begin(), a.hub_id.begin() + a.hub_id_size, b.hub_id.begin()) &&
        std::equal(a.home_id.begin(), a.home_id.begin() + a.home_id_size, b.home_id.begin()) &&
        std::equal(a.nonce.begin(), a.nonce.end(), b.nonce.begin());
}
}  // namespace

bool WifiSetupPermitGate::valid_challenge(const WifiSetupChallenge& challenge,
                                          std::uint64_t now_ms) const {
    if (challenge.hub_id_size == 0 || challenge.hub_id_size > challenge.hub_id.size() ||
        challenge.home_id_size == 0 || challenge.home_id_size > challenge.home_id.size() ||
        challenge.ownership_epoch == 0 || challenge.boot_generation == 0 ||
        challenge.security2_session_id == 0 || challenge.created_at_ms == 0 ||
        challenge.created_at_ms > UINT64_MAX - kMaxPermitLifetimeMs ||
        now_ms < challenge.created_at_ms ||
        now_ms - challenge.created_at_ms > kMaxChallengeAgeMs ||
        !nonzero(challenge.hub_id.data(), challenge.hub_id_size) ||
        !nonzero(challenge.home_id.data(), challenge.home_id_size) ||
        !nonzero(challenge.nonce.data(), challenge.nonce.size())) return false;
    return challenge.operation == WifiSetupOperation::InitialClaim ||
           challenge.operation == WifiSetupOperation::ChangeNetwork;
}

bool WifiSetupPermitGate::was_consumed(const WifiSetupChallenge& challenge) const {
    return std::any_of(replay_.begin(), replay_.end(), [&](const ReplayEntry& entry) {
        return entry.used && entry.boot_generation == challenge.boot_generation &&
            std::equal(entry.nonce.begin(), entry.nonce.end(), challenge.nonce.begin());
    });
}

void WifiSetupPermitGate::remember(const WifiSetupChallenge& challenge) {
    auto& entry = replay_[replay_cursor_];
    entry.nonce = challenge.nonce;
    entry.boot_generation = challenge.boot_generation;
    entry.used = true;
    replay_cursor_ = (replay_cursor_ + 1) % replay_.size();
}

WifiSetupPermitResult WifiSetupPermitGate::open(
    WifiSecurity2Session& session, const WifiSetupChallenge& challenge,
    const std::uint8_t* signed_permit, std::size_t permit_size,
    Gs109SetupPermitVerifier& verifier, std::uint64_t now_ms) {
    if (session_ != nullptr && current_generation(now_ms) != 0)
        return WifiSetupPermitResult::Busy;
    close();
    if (!valid_challenge(challenge, now_ms) || signed_permit == nullptr ||
        permit_size == 0 || permit_size > 4096)
        return WifiSetupPermitResult::InvalidInput;
    if (!session.authenticated() || session.security_version() != 2 ||
        session.session_id() == 0)
        return WifiSetupPermitResult::Security2Required;
    if (session.session_id() != challenge.security2_session_id)
        return WifiSetupPermitResult::BindingMismatch;
    if (was_consumed(challenge)) return WifiSetupPermitResult::Replay;

    VerifiedGs109SetupPermit verified;
    if (!verifier.verify_and_consume_one_use_permit(
            signed_permit, permit_size, challenge, now_ms, verified))
        return WifiSetupPermitResult::PermitRejected;
    if (!session.authenticated() || session.security_version() != 2 ||
        session.session_id() == 0)
        return WifiSetupPermitResult::Security2Required;
    if (session.session_id() != challenge.security2_session_id)
        return WifiSetupPermitResult::BindingMismatch;
    if (!same_challenge(verified.binding, challenge) ||
        verified.authority_generation == 0)
        return WifiSetupPermitResult::BindingMismatch;
    if (verified.verified_at_ms > now_ms || verified.expires_at_ms <= now_ms ||
        verified.expires_at_ms <= verified.verified_at_ms ||
        verified.expires_at_ms > challenge.created_at_ms + kMaxPermitLifetimeMs)
        return WifiSetupPermitResult::Expired;
    if (verified.verified_at_ms < challenge.created_at_ms ||
        current_authority_.current_generation(now_ms) != verified.authority_generation)
        return WifiSetupPermitResult::AuthorityStale;

    remember(challenge);
    session_ = &session;
    session_id_ = session.session_id();
    authority_generation_ = verified.authority_generation;
    opened_at_ms_ = now_ms;
    expires_at_ms_ = verified.expires_at_ms;
    return WifiSetupPermitResult::Ok;
}

void WifiSetupPermitGate::close() {
    session_ = nullptr;
    session_id_ = 0;
    authority_generation_ = 0;
    opened_at_ms_ = 0;
    expires_at_ms_ = 0;
}

std::uint64_t WifiSetupPermitGate::current_generation(std::uint64_t now_ms) const {
    if (session_ == nullptr || authority_generation_ == 0 || session_id_ == 0 ||
        !session_->authenticated() || session_->security_version() != 2 ||
        session_->session_id() != session_id_ || now_ms < opened_at_ms_ ||
        now_ms >= expires_at_ms_ ||
        current_authority_.current_generation(now_ms) != authority_generation_)
        return 0;
    return authority_generation_;
}

bool WifiSetupPermitGate::complete_setup_operation(std::uint64_t now_ms,
                                                   std::uint64_t generation) {
    if (generation == 0 || current_generation(now_ms) != generation) return false;
    close();
    return true;
}

}  // namespace gs::hub::connectivity
