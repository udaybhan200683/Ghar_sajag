#include "host/multinode/scheduled_harness.hpp"
#include "firmware/common/security/commissioning_protocol.hpp"
#include "firmware/common/security/rejoin_protocol.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace gs::host::multinode {

ScheduledHarness::ScheduledHarness(std::size_t count, std::size_t journal_capacity)
    : hub_(32, journal_capacity),
      registry_("sim-home", "sim-hub", std::max<std::size_t>(count, 10),
                2 * std::max<std::size_t>(count, 10)) {
    if (count == 0 || count > 25) throw std::invalid_argument("host node count must be 1..25");
    if (!crypto_.generate_test_identity("sim-hub-key"))
        throw std::runtime_error("host Hub identity generation failed");
    nodes_.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        Node node;
        node.physical_id = "sim-physical-" + std::to_string(i + 1);
        node.logical_id = "sim-node-" + std::to_string(i + 1);
        node.location = "sim-room-" + std::to_string(i + 1);
        node.radio_mac = {0x14, 0x63, 0x93, 0x00,
                          static_cast<std::uint8_t>((i + 1) >> 8),
                          static_cast<std::uint8_t>(i + 1)};
        node.runtime = std::make_unique<node::NodeRuntime>(node.logical_id, node.session);
        const auto key_reference = "sim-node-key-" + std::to_string(i + 1);
        gs::security::P256PublicKey node_public{};
        gs::security::Key32 installer_code{};
        if (!crypto_.generate_test_identity(key_reference) ||
            !crypto_.identity_public_key(key_reference, node_public) ||
            !crypto_.random_bytes(installer_code.data(), installer_code.size()))
            throw std::runtime_error("host Node identity generation failed");
        gs::security::HubCommissioning hub_pairing(crypto_, "sim-hub-key", "sim-hub", "sim-home",
                                                node.physical_id, node_public, installer_code,
                                                node.logical_id, node.location, "motion");
        gs::security::NodeCommissioning node_pairing(crypto_, key_reference, node.physical_id,
                                                  installer_code);
        crypto_.secure_zero(installer_code.data(), installer_code.size());
        const auto offer = hub_pairing.open(0, 5000);
        if (!offer || !node_pairing.enable_window(0, 5000))
            throw std::runtime_error("host commissioning window failed");
        const auto node_proof = node_pairing.respond(*offer, 1);
        const auto hub_proof = node_proof ? hub_pairing.accept(*node_proof, 2) : std::nullopt;
        const auto final = hub_proof ? node_pairing.finish(*hub_proof, 3) : std::nullopt;
        const auto ack = final ? hub_pairing.confirm(*final, 4) : std::nullopt;
        if (!ack || !node_pairing.commit(*ack, 5) ||
            !hub_pairing.binding() || !node_pairing.binding() ||
            hub_pairing.binding()->installation_key != node_pairing.binding()->installation_key)
            throw std::runtime_error("host asymmetric commissioning failed");
        node.node_binding = std::make_unique<gs::security::CommissioningBinding>(
            *node_pairing.binding());
        node.hub_binding = std::make_unique<gs::security::CommissioningBinding>(
            *hub_pairing.binding());
        hub::EnrolledNode record;
        record.device_id = node.hub_binding->device_id;
        record.p256_public_key = node.hub_binding->device_public_key;
        record.radio_mac = node.radio_mac;
        record.home_id = node.hub_binding->home_id;
        record.hub_id = node.hub_binding->hub_id;
        record.logical_id = node.hub_binding->logical_id;
        record.room = node.hub_binding->room;
        record.function = node.hub_binding->function;
        if (registry_.enroll(record) != hub::RegistryResult::Accepted)
            throw std::runtime_error("host registry setup failed");
        if (!establish_session(node, 0))
            throw std::runtime_error("host authenticated rejoin failed");
        nodes_.push_back(std::move(node));
    }
}

ScheduledHarness::~ScheduledHarness() {
    for (auto& node : nodes_) {
        if (node.node_binding)
            crypto_.secure_zero(node.node_binding->installation_key.data(),
                                node.node_binding->installation_key.size());
        if (node.hub_binding)
            crypto_.secure_zero(node.hub_binding->installation_key.data(),
                                node.hub_binding->installation_key.size());
    }
}

bool ScheduledHarness::establish_session(Node& node, std::uint64_t last_session) {
        gs::security::NodeRejoin node_rejoin(crypto_, *node.node_binding, node.session);
        gs::security::HubRejoin hub_rejoin(crypto_, *node.hub_binding, last_session);
        const auto hello = node_rejoin.begin();
        const auto challenge = hello ? hub_rejoin.accept(*hello) : std::nullopt;
        const auto rejoin_final = challenge ? node_rejoin.accept(*challenge) : std::nullopt;
        const auto rejoin_ack = rejoin_final ? hub_rejoin.confirm(*rejoin_final) : std::nullopt;
        if (!rejoin_ack || !hub_rejoin.session_salt() ||
            registry_.rejoin(node.physical_id, node.radio_mac,
                             hub_rejoin.authenticated_session()) != hub::RegistryResult::Accepted ||
            !node_rejoin.commit(*rejoin_ack) || !node_rejoin.session_salt() ||
            *node_rejoin.session_salt() != *hub_rejoin.session_salt())
            return false;
        node.node_security = std::make_unique<gs::security::RuntimeFrameSecurity>(
            crypto_, *node.node_binding);
        node.hub_security = std::make_unique<gs::security::RuntimeFrameSecurity>(
            crypto_, *node.hub_binding);
        if (!node.node_security->start(node.session, *node_rejoin.session_salt()) ||
            !node.hub_security->start(node.session, *hub_rejoin.session_salt()))
            return false;
        node.commissioned = true;
        hub_.authorize_node(node.logical_id, node.session, true);
        return true;
}

bool ScheduledHarness::restart_node(std::size_t index) {
    auto& node = nodes_.at(index);
    if (node.session == UINT64_MAX || node.runtime->pending() != 0) return false;
    const auto record = registry_.find(node.physical_id);
    if (!record || record->quarantined) return false;
    ++node.session;
    node.runtime = std::make_unique<node::NodeRuntime>(node.logical_id, node.session);
    return establish_session(node, record->last_session);
}

std::optional<EventKey> ScheduledHarness::record(std::size_t index, EventKind kind) {
    auto& node = nodes_.at(index);
    return node.runtime->record(kind, node.location, now_ms_, 0, 0, 3800);
}

void ScheduledHarness::set_node_online(std::size_t index, bool online) {
    nodes_.at(index).online = online;
}

void ScheduledHarness::drop_next_ack(std::size_t index) {
    nodes_.at(index).drop_ack = true;
}

void ScheduledHarness::redirect_next_ack(std::size_t from_index, std::size_t to_index) {
    if (to_index >= nodes_.size()) throw std::out_of_range("ACK destination missing");
    nodes_.at(from_index).redirect_ack_to = to_index;
}

hub::RegistryResult ScheduledHarness::remove_node(std::size_t index) {
    return registry_.remove(nodes_.at(index).physical_id);
}

void ScheduledHarness::send_due_nodes() {
    for (std::size_t i = 0; i < nodes_.size(); ++i) {
        auto& node = nodes_[i];
        if (!node.online) continue;
        const auto message = node.runtime->next_message(now_ms_);
        if (!message) continue;
        const EventKey key{message->node_id, message->session_id, message->sequence_number};
        const auto encoded = transport::encode_node_message(*message);
        if (!encoded) throw std::runtime_error("production NodeMessage encoder failed");
        gs::security::SecureFrame protected_frame;
        if (!node.node_security->seal(gs::security::RuntimeDirection::Uplink,
                                       encoded.frame, protected_frame))
            throw std::runtime_error("authenticated uplink encoding failed");
        ++node.uplink_attempts;
        node.runtime->transport_result(key, hub_online_, now_ms_);
        if (hub_online_) frames_.push_back({Frame::Direction::Uplink, i, protected_frame,
                                           now_ms_ + 1, now_ms_});
    }
}

void ScheduledHarness::deliver(const Frame& frame) {
    auto& node = nodes_.at(frame.node_index);
    if (!hub_online_ || !node.online) return;
    if (frame.direction == Frame::Direction::Uplink) {
        transport::EncodedFrame plain;
        if (!node.hub_security->open(gs::security::RuntimeDirection::Uplink,
                                      frame.wire, plain)) {
            ++node.registry_rejections;
            return;
        }
        const auto decoded = transport::decode_node_message(plain.bytes.data(), plain.size);
        if (!decoded) throw std::runtime_error("production NodeMessage decoder failed");
        if (decoded.value->node_id != node.logical_id || decoded.value->session_id != node.session)
            throw std::runtime_error("cross-node uplink identity");
        const auto assigned = registry_.find(node.physical_id);
        if (!assigned || assigned->quarantined || assigned->radio_mac != node.radio_mac ||
            assigned->logical_id != decoded.value->node_id ||
            assigned->last_session != decoded.value->session_id) {
            ++node.registry_rejections;
            return;
        }
        if (!hub_.radio_message_callback(*decoded.value, 0)) return;
        ++node.hub_admissions;
        const auto processed = hub_.run_state_once();
        if (!processed) throw std::runtime_error("HubRuntime did not process admitted frame");
        const auto ack = make_node_ack(processed->key, processed->ack, 0, "host_transport");
        const auto encoded = transport::encode_node_ack(ack);
        if (!encoded) throw std::runtime_error("production NodeAck encoder failed");
        gs::security::SecureFrame protected_ack;
        if (!node.hub_security->seal(gs::security::RuntimeDirection::Downlink,
                                      encoded.frame, protected_ack))
            throw std::runtime_error("authenticated ACK encoding failed");
        if (node.drop_ack) {
            node.drop_ack = false;
            return;
        }
        const auto destination = node.redirect_ack_to.value_or(frame.node_index);
        node.redirect_ack_to.reset();
        frames_.push_back({Frame::Direction::Ack, destination, protected_ack,
                           now_ms_ + 1, frame.originated_ms});
        return;
    }
    transport::EncodedFrame plain;
    if (!node.node_security->open(gs::security::RuntimeDirection::Downlink,
                                    frame.wire, plain)) {
        ++node.ack_mismatches;
        return;
    }
    const auto decoded = transport::decode_node_ack(plain.bytes.data(), plain.size);
    if (!decoded) throw std::runtime_error("production NodeAck decoder failed");
    const EventKey key{decoded.value->node_id, decoded.value->session_id,
                       decoded.value->sequence_number};
    if (key.source_id != node.logical_id || key.session_id != node.session) {
        ++node.ack_mismatches;
        return;
    }
    if (node.runtime->acknowledge(key, decoded.value->ack_type)) {
        ++node.matching_acks;
        node.maximum_ack_latency_ms = std::max(node.maximum_ack_latency_ms,
            static_cast<std::uint64_t>(now_ms_ - frame.originated_ms));
    } else {
        ++node.ack_mismatches;
    }
}

void ScheduledHarness::deliver_due_frames() {
    std::vector<Frame> due;
    std::vector<Frame> later;
    for (const auto& frame : frames_) {
        (frame.due_ms <= now_ms_ ? due : later).push_back(frame);
    }
    frames_ = std::move(later);
    for (const auto& frame : due) deliver(frame);
}

void ScheduledHarness::advance(Milliseconds delta_ms) {
    if (delta_ms < 0) throw std::invalid_argument("negative virtual-time advance");
    const Milliseconds target = now_ms_ + delta_ms;
    do {
        send_due_nodes();
        deliver_due_frames();
        if (now_ms_ == target) break;
        ++now_ms_;
    } while (true);
}

void ScheduledHarness::run_until_quiet(Milliseconds maximum_ms) {
    for (Milliseconds elapsed = 0; elapsed <= maximum_ms; ++elapsed) {
        advance(1);
        if (frames_.empty() && std::all_of(nodes_.begin(), nodes_.end(), [](const Node& item) {
                return item.runtime->pending() == 0;
            })) return;
    }
    throw std::runtime_error("host transport did not drain within virtual-time bound");
}

NodeSnapshot ScheduledHarness::snapshot(std::size_t index) const {
    const auto& node = nodes_.at(index);
    return {node.physical_id, node.logical_id, node.location, node.session,
            node.runtime->next_sequence(), node.runtime->persisted(), node.runtime->pending(),
            node.uplink_attempts, node.hub_admissions, node.matching_acks,
            node.ack_mismatches, node.registry_rejections,
            node.maximum_ack_latency_ms, node.commissioned};
}

}  // namespace gs::host::multinode
