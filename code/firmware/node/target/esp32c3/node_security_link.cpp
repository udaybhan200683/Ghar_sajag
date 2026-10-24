#include "firmware/node/target/esp32c3/node_security_link.hpp"
#include "firmware/common/transport/node_retirement_protocol.hpp"

#include "firmware/common/security/target_wrapping_key.hpp"
#include "firmware/node/target/esp32c3/nvs_session_provider.hpp"

#include <cstdio>
#include <utility>

namespace gs::node::target {
namespace {

std::string id_for_mac(const NodeSecurityLink::Mac& mac, const char* prefix) {
    char text[32]{};
    std::snprintf(text, sizeof(text), "%s-%02x%02x%02x%02x%02x%02x", prefix,
                  mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return text;
}

bool mac_from_hub_id(const std::string& id, NodeSecurityLink::Mac& mac) {
    if (id.size() != 16 || id.compare(0, 4, "hub-") != 0) return false;
    for (std::size_t index = 0; index < mac.size(); ++index) {
        const auto decode = [](char ch) -> int {
            if (ch >= '0' && ch <= '9') return ch - '0';
            if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
            return -1;
        };
        const int high = decode(id[4 + index * 2]);
        const int low = decode(id[5 + index * 2]);
        if (high < 0 || low < 0) return false;
        mac[index] = static_cast<std::uint8_t>((high << 4) | low);
    }
    return true;
}
}  // namespace

NodeSecurityLink::NodeSecurityLink() = default;

NodeSecurityLink::~NodeSecurityLink() {
    if (binding_)
        crypto_.secure_zero(binding_->installation_key.data(),
                            binding_->installation_key.size());
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
    crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
}

bool NodeSecurityLink::initialize(const Mac& physical_mac, std::uint64_t session,
                                   std::uint64_t now_ms) {
    if (phase_ != Phase::Uninitialized || session == 0 || !crypto_.ready() ||
        !identity_.initialize() ||
        !security::load_or_create_target_wrapping_key(crypto_, wrapping_key_)) {
        phase_ = Phase::Fault;
        return false;
    }
    physical_id_ = id_for_mac(physical_mac, "c3");
    session_ = session;
    security::Bytes recovery_salt(physical_id_.begin(), physical_id_.end());
    constexpr char kRecoveryContext[] = "GharSajag/NodeRecovery/v1";
    const security::Bytes recovery_context(
        kRecoveryContext, kRecoveryContext + sizeof(kRecoveryContext) - 1U);
    if (!crypto_.hkdf_sha256(wrapping_key_, recovery_salt, recovery_context,
                             recovery_key_)) {
        crypto_.secure_zero(recovery_salt.data(), recovery_salt.size());
        crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
        phase_ = Phase::Fault;
        return false;
    }
    crypto_.secure_zero(recovery_salt.data(), recovery_salt.size());
    repository_ = std::make_unique<security::AssociationRepository>(
        crypto_, store_, wrapping_key_, &previous_store_);
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
    const auto loaded = repository_->load();
    if (loaded.status == security::AssociationStatus::Corrupt ||
        loaded.status == security::AssociationStatus::IoError) {
        phase_ = Phase::Fault;
        return false;
    }
    if (loaded.status == security::AssociationStatus::Paired) {
        if (!loaded.binding || loaded.binding->device_id != physical_id_ ||
            !mac_from_hub_id(loaded.binding->hub_id, hub_mac_)) {
            phase_ = Phase::Fault;
            return false;
        }
        security::P256PublicKey actual_public{};
        if (!identity_.public_key("node", actual_public) ||
            !crypto_.constant_time_equal(actual_public.data(),
                                         loaded.binding->device_public_key.data(),
                                         actual_public.size())) {
            phase_ = Phase::Fault;
            return false;
        }
        binding_ = *loaded.binding;
        const auto pinned = health_ack_pinned_for_hub(binding_->hub_id);
        if (!pinned) {
            phase_ = Phase::Fault;
            return false;
        }
        pinned_v2_ = *pinned;
        phase_ = Phase::Rejoining;
        return true;
    }
    security::Key32 installer_code{};
    if (!security::load_target_installer_code(crypto_, installer_code)) {
        phase_ = Phase::Fault;
        return false;
    }
    commissioning_ = std::make_unique<security::NodeCommissioning>(
        crypto_, "node", physical_id_, installer_code);
    crypto_.secure_zero(installer_code.data(), installer_code.size());
    if (!commissioning_->enable_window(now_ms, 10U * 60U * 1000U)) {
        phase_ = Phase::Fault;
        return false;
    }
    phase_ = Phase::Commissioning;
    return true;
}

Gs117ReassociationStatus NodeSecurityLink::begin_gs117_test_reassociation(
        const std::string& expected_hub_id, std::uint64_t now_ms) {
    constexpr char kFixtureHub[] = "hub-e072a1d38d34";
    constexpr char kFixtureHome[] = "gs177-test-product";
    Mac target_hub_mac{};
    const auto preflight = gs117_reassociation_preflight(
        phase_ == Phase::Rejoining, binding_.has_value() && repository_ != nullptr,
        expected_hub_id == kFixtureHub && mac_from_hub_id(expected_hub_id, target_hub_mac),
        binding_ && binding_->hub_id == expected_hub_id,
        binding_ && binding_->home_id == kFixtureHome);
    if (preflight != Gs117ReassociationStatus::Ready) return preflight;

    // Prove that the previous recovery state is readable before any live
    // association change. Its encrypted bytes are copied to a separate NVS
    // namespace and are retained after a successful re-association.
    node::NodeRecoveryRepository prior_recovery(
        crypto_, recovery_store_, recovery_key_, binding_->home_id,
        binding_->hub_id, binding_->logical_id);
    const auto prior_state = prior_recovery.load();
    if (prior_state.status == node::NodeRecoveryLoadStatus::Corrupt)
        return Gs117ReassociationStatus::RecoveryCorrupt;
    if (prior_state.status == node::NodeRecoveryLoadStatus::IoError)
        return Gs117ReassociationStatus::RecoveryIoError;

    security::Bytes recovery_blob;
    bool recovery_found = false;
    if (!recovery_store_.read(recovery_blob, recovery_found))
        return Gs117ReassociationStatus::RecoverySnapshotReadFailed;
    security::Bytes backup_blob;
    bool backup_found = false;
    if (!previous_recovery_store_.read(backup_blob, backup_found))
        return Gs117ReassociationStatus::RecoverySnapshotReadFailed;
    if (recovery_found) {
        if (prior_state.status != node::NodeRecoveryLoadStatus::Ready ||
            !prior_state.state) return Gs117ReassociationStatus::RecoveryStateUnavailable;
        if (backup_found) {
            if (backup_blob != recovery_blob)
                return Gs117ReassociationStatus::RecoveryBackupConflict;
        } else if (!previous_recovery_store_.write(recovery_blob)) {
            return Gs117ReassociationStatus::RecoveryBackupWriteFailed;
        }
        if (!previous_recovery_store_.read(backup_blob, backup_found) ||
            !backup_found || backup_blob != recovery_blob)
            return Gs117ReassociationStatus::RecoveryBackupVerifyFailed;
    } else if (backup_found) {
        return Gs117ReassociationStatus::RecoveryBackupConflict;
    }
    if (!repository_->preserve_previous_for_reassociation())
        return Gs117ReassociationStatus::AssociationBackupFailed;

    security::Key32 installer_code{};
    if (!security::load_target_installer_code(crypto_, installer_code)) {
        crypto_.secure_zero(installer_code.data(), installer_code.size());
        return Gs117ReassociationStatus::InstallerCodeUnavailable;
    }
    commissioning_ = std::make_unique<security::NodeCommissioning>(
        crypto_, "node", physical_id_, installer_code);
    crypto_.secure_zero(installer_code.data(), installer_code.size());
    if (!commissioning_->enable_window(now_ms, 10U * 60U * 1000U)) {
        commissioning_.reset();
        return Gs117ReassociationStatus::CommissioningWindowFailed;
    }
    hub_mac_ = target_hub_mac;
    expected_reassociation_hub_id_ = expected_hub_id;
    test_reassociation_pending_ = true;
    frames_.reset();
    rejoin_.reset();
    assembler_.reset();
    phase_ = Phase::Commissioning;
    return Gs117ReassociationStatus::Ready;
}

bool NodeSecurityLink::restore_recovery(node::NodeRuntime& runtime,
                                        Milliseconds now_ms) {
    if (!ready() || !binding_ || recovery_repository_) return false;
    recovery_repository_ = std::make_unique<node::NodeRecoveryRepository>(
        crypto_, recovery_store_, recovery_key_, binding_->home_id,
        binding_->hub_id, binding_->logical_id);
    const auto loaded = recovery_repository_->load();
    if (loaded.status == node::NodeRecoveryLoadStatus::Ready) {
        crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
        if (!loaded.state || !runtime.restore_recovery(*loaded.state, now_ms)) {
            phase_ = Phase::Fault;
            return false;
        }
        return true;
    }
    if (loaded.status == node::NodeRecoveryLoadStatus::Missing) {
        crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
        return true;
    }
    if (loaded.status == node::NodeRecoveryLoadStatus::Corrupt) {
        // An interrupted authenticated Hub reassociation can leave the prior
        // AEAD-bound snapshot under the previous binding. Recover it only from
        // the verified opaque backup and migrate every original EventKey into
        // a new snapshot bound to the new authenticated Hub.
        const auto previous = repository_->load_previous_association();
        if (previous.status != security::AssociationStatus::Paired ||
            !previous.binding || previous.binding->hub_id == binding_->hub_id ||
            previous.binding->home_id != binding_->home_id ||
            previous.binding->device_id != binding_->device_id ||
            previous.binding->logical_id != binding_->logical_id ||
            previous.binding->room != binding_->room ||
            previous.binding->function != binding_->function) {
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            phase_ = Phase::Fault;
            return false;
        }
        security::Bytes saved_recovery;
        bool saved_found = false;
        if (!previous_recovery_store_.read(saved_recovery, saved_found) || !saved_found) {
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            phase_ = Phase::Fault;
            return false;
        }
        security::Bytes current_recovery;
        bool current_found = false;
        if (!recovery_store_.read(current_recovery, current_found) || !current_found ||
            current_recovery != saved_recovery) {
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            phase_ = Phase::Fault;
            return false;
        }
        node::NodeRecoveryRepository prior_repository(
            crypto_, previous_recovery_store_, recovery_key_,
            previous.binding->home_id, previous.binding->hub_id,
            previous.binding->logical_id);
        crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
        const auto prior = prior_repository.load();
        if (prior.status != node::NodeRecoveryLoadStatus::Ready || !prior.state ||
            !runtime.restore_recovery(*prior.state, now_ms) ||
            !recovery_repository_->rebind_from_authenticated_previous(
                runtime.recovery_snapshot(), prior.generation, saved_recovery,
                previous.binding->home_id, previous.binding->hub_id)) {
            phase_ = Phase::Fault;
            return false;
        }
        return true;
    }
    crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
    phase_ = Phase::Fault;
    return false;
}

bool NodeSecurityLink::persist_recovery(const node::NodeRuntime& runtime) {
    if ((phase_ != Phase::Ready && phase_ != Phase::Rejoining) ||
        !recovery_repository_ ||
        !recovery_repository_->save(runtime.recovery_snapshot())) {
        phase_ = Phase::Fault;
        return false;
    }
    return true;
}

bool NodeSecurityLink::retirement_report_key(security::Key32& out) {
    if (!ready() || !binding_) return false;
    return transport::derive_retirement_report_key(
        crypto_, binding_->installation_key, out);
}

bool NodeSecurityLink::fragment_retirement_report(
        const transport::NodeRetirementReportV1& report,
        transport::RetirementFragmentSet& fragments) {
    if (!ready() || !binding_) return false;
    security::Key32 report_key{};
    const bool okay = transport::derive_retirement_report_key(
        crypto_, binding_->installation_key, report_key) &&
        transport::fragment_retirement_report(crypto_, report_key, report, fragments);
    crypto_.secure_zero(report_key.data(), report_key.size());
    return okay;
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::reply(
    const Mac& destination, const security::wire::Message& message) {
    return Outbound{destination, message};
}

bool NodeSecurityLink::matching_hub(const Mac& source) const {
    return source == hub_mac_;
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::begin_rejoin() {
    if (!binding_) return std::nullopt;
    challenge_seen_ = false;
    rejoin_ = std::make_unique<security::NodeRejoin>(crypto_, *binding_, session_,
                                                     rejoin_version_);
    const auto hello = rejoin_->begin();
    security::wire::Message message;
    if (!hello || !security::wire::encode(*hello, message)) {
        phase_ = Phase::Fault;
        return std::nullopt;
    }
    phase_ = Phase::Rejoining;
    return reply(hub_mac_, message);
}

bool NodeSecurityLink::start_rejoin(std::uint64_t session, std::uint8_t version) {
    if (!binding_ || session <= session_ || (version != 1 && version != 2) ||
        (pinned_v2_ && version != 2)) return false;
    frames_.reset();
    rejoin_.reset();
    assembler_.reset();
    health_ack_supported_ = false;
    session_ = session;
    rejoin_version_ = version;
    phase_ = Phase::Rejoining;
    return true;
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::fallback_to_v1() {
    if (phase_ != Phase::Rejoining || rejoin_version_ != 2 || pinned_v2_ ||
        challenge_seen_) return std::nullopt;
    rejoin_version_ = 1;
    rejoin_.reset();
    assembler_.reset();
    return begin_rejoin();
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::initial_message() {
    if (phase_ != Phase::Rejoining || rejoin_) return std::nullopt;
    return begin_rejoin();
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::accept(
    const Mac& source, const std::uint8_t* packet, std::size_t length,
    std::uint64_t now_ms) {
    if (phase_ != Phase::Commissioning && phase_ != Phase::Rejoining)
        return std::nullopt;
    if (phase_ == Phase::Rejoining && !matching_hub(source)) return std::nullopt;
    if (phase_ == Phase::Commissioning && commissioning_ &&
        hub_mac_ != Mac{} && !matching_hub(source)) return std::nullopt;
    const auto message = assembler_.push(packet, length, now_ms);
    if (!message) return std::nullopt;
    security::wire::Message outbound;
    if (phase_ == Phase::Commissioning) {
        if (message->kind == security::wire::Kind::Offer &&
            (hub_mac_ == Mac{} || test_reassociation_pending_)) {
            security::CommissioningOffer offer;
            if (!security::wire::decode(*message, offer) ||
                offer.hub_id != id_for_mac(source, "hub") ||
                (test_reassociation_pending_ &&
                 (!binding_ || offer.hub_id != expected_reassociation_hub_id_ ||
                  offer.device_public_key != binding_->device_public_key ||
                  offer.home_id != binding_->home_id ||
                  offer.logical_id != binding_->logical_id ||
                  offer.room != binding_->room ||
                  offer.function != binding_->function))) return std::nullopt;
            const auto proof = commissioning_->respond(offer, now_ms);
            if (!proof || !security::wire::encode(*proof, outbound)) return std::nullopt;
            hub_mac_ = source;
            return reply(source, outbound);
        }
        if (message->kind == security::wire::Kind::HubProof && hub_mac_ == source) {
            security::HubProof proof;
            if (!security::wire::decode(*message, proof)) return std::nullopt;
            const auto final = commissioning_->finish(proof, now_ms);
            if (!final || !security::wire::encode(*final, outbound)) return std::nullopt;
            return reply(source, outbound);
        }
        if (message->kind == security::wire::Kind::CommissioningAck &&
            hub_mac_ == source) {
            security::CommissioningAck ack;
            if (!security::wire::decode(*message, ack) ||
                !commissioning_->commit(ack, now_ms) ||
                !commissioning_->binding() ||
                !(test_reassociation_pending_
                    ? repository_->save_reassociation(*commissioning_->binding())
                    : repository_->save_initial(*commissioning_->binding()))) {
                phase_ = Phase::Fault;
                return std::nullopt;
            }
            binding_ = *commissioning_->binding();
            if (test_reassociation_pending_) {
                pinned_v2_ = false;
                health_ack_supported_ = false;
            }
            commissioning_.reset();
            return begin_rejoin();
        }
        return std::nullopt;
    }
    if (message->kind == security::wire::Kind::RejoinChallenge) {
        security::RejoinChallenge challenge;
        if (!security::wire::decode(*message, challenge) || !rejoin_)
            return std::nullopt;
        const auto final = rejoin_->accept(challenge);
        if (!final || !security::wire::encode(*final, outbound)) return std::nullopt;
        challenge_seen_ = true;
        return reply(source, outbound);
    }
    if (message->kind == security::wire::Kind::RejoinAck) {
        security::RejoinAck ack;
        if (!security::wire::decode(*message, ack) || !rejoin_ ||
            !rejoin_->commit(ack) || !rejoin_->session_salt() || !binding_)
            return std::nullopt;
        const bool negotiated =
            (rejoin_->negotiated_capabilities() & security::kHealthAckCapability) != 0;
        if (pinned_v2_ && !negotiated) {
            phase_ = Phase::Fault;
            return std::nullopt;
        }
        if (negotiated && (!pinned_v2_ || test_reassociation_pending_)) {
            if (!pin_health_ack_for_hub(binding_->hub_id)) {
                phase_ = Phase::Fault;
                return std::nullopt;
            }
            pinned_v2_ = true;
        }
        frames_ = std::make_unique<security::RuntimeFrameSecurity>(crypto_, *binding_);
        if (!frames_->start(session_, *rejoin_->session_salt())) {
            phase_ = Phase::Fault;
            return std::nullopt;
        }
        rejoin_.reset();
        health_ack_supported_ = negotiated;
        test_reassociation_pending_ = false;
        expected_reassociation_hub_id_.clear();
        phase_ = Phase::Ready;
    }
    return std::nullopt;
}

}  // namespace gs::node::target
