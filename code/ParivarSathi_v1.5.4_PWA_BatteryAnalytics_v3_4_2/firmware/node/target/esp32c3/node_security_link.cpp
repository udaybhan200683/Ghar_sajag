#include "firmware/node/target/esp32c3/node_security_link.hpp"

#include "firmware/common/security/target_wrapping_key.hpp"

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
        crypto_, store_, wrapping_key_);
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

bool NodeSecurityLink::restore_recovery(node::NodeRuntime& runtime,
                                        Milliseconds now_ms) {
    if (!ready() || !binding_ || recovery_repository_) return false;
    recovery_repository_ = std::make_unique<node::NodeRecoveryRepository>(
        crypto_, recovery_store_, recovery_key_, binding_->home_id,
        binding_->hub_id, binding_->logical_id);
    crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
    const auto loaded = recovery_repository_->load();
    if (loaded.status == node::NodeRecoveryLoadStatus::Corrupt ||
        loaded.status == node::NodeRecoveryLoadStatus::IoError ||
        (loaded.status == node::NodeRecoveryLoadStatus::Ready &&
         (!loaded.state || !runtime.restore_recovery(*loaded.state, now_ms)))) {
        phase_ = Phase::Fault;
        return false;
    }
    return true;
}

bool NodeSecurityLink::persist_recovery(const node::NodeRuntime& runtime) {
    if (!ready() || !recovery_repository_ ||
        !recovery_repository_->save(runtime.recovery_snapshot())) {
        phase_ = Phase::Fault;
        return false;
    }
    return true;
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
    rejoin_ = std::make_unique<security::NodeRejoin>(crypto_, *binding_, session_);
    const auto hello = rejoin_->begin();
    security::wire::Message message;
    if (!hello || !security::wire::encode(*hello, message)) {
        phase_ = Phase::Fault;
        return std::nullopt;
    }
    phase_ = Phase::Rejoining;
    return reply(hub_mac_, message);
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
        if (message->kind == security::wire::Kind::Offer && hub_mac_ == Mac{}) {
            security::CommissioningOffer offer;
            if (!security::wire::decode(*message, offer) ||
                offer.hub_id != id_for_mac(source, "hub")) return std::nullopt;
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
                !repository_->save_initial(*commissioning_->binding())) {
                phase_ = Phase::Fault;
                return std::nullopt;
            }
            binding_ = *commissioning_->binding();
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
        return reply(source, outbound);
    }
    if (message->kind == security::wire::Kind::RejoinAck) {
        security::RejoinAck ack;
        if (!security::wire::decode(*message, ack) || !rejoin_ ||
            !rejoin_->commit(ack) || !rejoin_->session_salt() || !binding_)
            return std::nullopt;
        frames_ = std::make_unique<security::RuntimeFrameSecurity>(crypto_, *binding_);
        if (!frames_->start(session_, *rejoin_->session_salt())) {
            phase_ = Phase::Fault;
            return std::nullopt;
        }
        rejoin_.reset();
        phase_ = Phase::Ready;
    }
    return std::nullopt;
}

}  // namespace gs::node::target
