#include "host/multinode/scheduled_harness.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace gs::host::multinode {

ScheduledHarness::ScheduledHarness(std::size_t count, std::size_t journal_capacity)
    : hub_(32, journal_capacity) {
    if (count == 0 || count > 25) throw std::invalid_argument("host node count must be 1..25");
    nodes_.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        Node node;
        node.physical_id = "sim-physical-" + std::to_string(i + 1);
        node.logical_id = "sim-node-" + std::to_string(i + 1);
        node.location = "sim-room-" + std::to_string(i + 1);
        node.runtime = std::make_unique<node::NodeRuntime>(node.logical_id, node.session);
        // Test setup authorization; production commissioning is a later checkpoint.
        hub_.authorize_node(node.logical_id, node.session, true);
        nodes_.push_back(std::move(node));
    }
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

void ScheduledHarness::send_due_nodes() {
    for (std::size_t i = 0; i < nodes_.size(); ++i) {
        auto& node = nodes_[i];
        if (!node.online) continue;
        const auto message = node.runtime->next_message(now_ms_);
        if (!message) continue;
        const EventKey key{message->node_id, message->session_id, message->sequence_number};
        const auto encoded = transport::encode_node_message(*message);
        if (!encoded) throw std::runtime_error("production NodeMessage encoder failed");
        ++node.uplink_attempts;
        node.runtime->transport_result(key, hub_online_, now_ms_);
        if (hub_online_) frames_.push_back({Frame::Direction::Uplink, i, encoded.frame, now_ms_ + 1, now_ms_});
    }
}

void ScheduledHarness::deliver(const Frame& frame) {
    auto& node = nodes_.at(frame.node_index);
    if (!hub_online_ || !node.online) return;
    if (frame.direction == Frame::Direction::Uplink) {
        const auto decoded = transport::decode_node_message(frame.wire.bytes.data(), frame.wire.size);
        if (!decoded) throw std::runtime_error("production NodeMessage decoder failed");
        if (decoded.value->node_id != node.logical_id || decoded.value->session_id != node.session)
            throw std::runtime_error("cross-node uplink identity");
        if (!hub_.radio_message_callback(*decoded.value, 0)) return;
        ++node.hub_admissions;
        const auto processed = hub_.run_state_once();
        if (!processed) throw std::runtime_error("HubRuntime did not process admitted frame");
        const auto ack = make_node_ack(processed->key, processed->ack, 0, "host_transport");
        const auto encoded = transport::encode_node_ack(ack);
        if (!encoded) throw std::runtime_error("production NodeAck encoder failed");
        if (node.drop_ack) {
            node.drop_ack = false;
            return;
        }
        frames_.push_back({Frame::Direction::Ack, frame.node_index, encoded.frame,
                           now_ms_ + 1, frame.originated_ms});
        return;
    }
    const auto decoded = transport::decode_node_ack(frame.wire.bytes.data(), frame.wire.size);
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
            node.ack_mismatches, node.maximum_ack_latency_ms};
}

}  // namespace gs::host::multinode
