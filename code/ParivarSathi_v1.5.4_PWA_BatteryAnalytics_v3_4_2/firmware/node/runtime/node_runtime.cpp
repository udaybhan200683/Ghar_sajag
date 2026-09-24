// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module N02 Node radio
// @requirements E01, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The pending transmission queue owns retry timing but does not own physical RF. A caller asks next_due,
// transmits through an adapter, then reports the transport result. Only an application acknowledgement
// with the expected event identity may retire retained business data. Call this component from one owner,
// not directly from concurrent radio callbacks.

#include "node_runtime.hpp"
#include "gs/logging.hpp"
#include "gs/protocol.hpp"

#include <utility>
#include <algorithm>
#include <set>

namespace gs::node {
namespace {
bool same_event(const DomainEvent& left, const DomainEvent& right) {
    return left.key.source_id == right.key.source_id &&
           left.key.session_id == right.key.session_id &&
           left.key.sequence == right.key.sequence &&
           left.kind == right.kind && left.location == right.location &&
           left.monotonic_ms == right.monotonic_ms &&
           left.occurred_at == right.occurred_at &&
           left.received_at == right.received_at &&
           left.uncertainty_s == right.uncertainty_s &&
           left.battery_mv == right.battery_mv && left.is_test == right.is_test &&
           left.sensor_type == right.sensor_type && left.rssi_dbm == right.rssi_dbm;
}
}

NodeRuntime::NodeRuntime(std::string node_id, std::uint64_t session_id,
                         std::size_t journal_capacity, std::size_t tx_capacity)
    : node_id_(std::move(node_id)),
      session_id_(session_id),
      store_(journal_capacity),
      radio_(tx_capacity) {
    GS_TRACE(gs::log::Category::Node, "N00", "NodeRuntime.enter", "-");}

// @requirements E01, E02, NFR-04
// Create one identity and retain before enqueue; failed enqueue can strand the stored event until a
// refill adapter is added (G05).
std::optional<EventKey> NodeRuntime::record(EventKind kind, const std::string& location,
                                            Milliseconds monotonic_ms, EpochSeconds occurred_at,
                                            std::uint32_t uncertainty_s, std::uint16_t battery_mv,
                                            bool is_test, SensorType sensor_type, std::int16_t rssi_dbm) {
    GS_TRACE(gs::log::Category::Node, "N00", "record.enter", "-");
    ++stats_.record_calls;
    EventKey key{node_id_, session_id_, next_sequence_++};
    const auto resolved_sensor = sensor_type == SensorType::Unknown ? sensor_type_for(kind) : sensor_type;
    DomainEvent event{key, kind, location, monotonic_ms, occurred_at, occurred_at,
                      uncertainty_s, battery_mv, is_test, resolved_sensor, rssi_dbm};
    // Preflight the transport queue before retaining so an admission failure
    // cannot create an unreachable/stranded journal record.
    if (!radio_.can_enqueue(kind)) {
        ++stats_.tx_queue_full;
        if (kind == EventKind::Motion) ++stats_.dropped_motion;
        else ++stats_.priority_rejected;
        GS_ERROR(gs::log::Category::Radio, "N00", "record.failed", "tx_queue_full");
        return std::nullopt;
    }
    if (!store_.append(event)) {
        ++stats_.store_full;
        if (kind == EventKind::Motion) ++stats_.dropped_motion;
        else ++stats_.priority_rejected;
        GS_ERROR(gs::log::Category::Storage, "N00", "record.failed", "node_journal_full");
        return std::nullopt;
    }
    if (!radio_.enqueue(event, monotonic_ms)) {
        // Single-owner preflight makes this defensive path unexpected, but
        // preserve the store/radio invariant if capacities ever diverge.
        (void)store_.acknowledge(key, AckClass::DiscardedPolicy);
        ++stats_.tx_queue_full;
        if (kind == EventKind::Motion) ++stats_.dropped_motion;
        else ++stats_.priority_rejected;
        GS_ERROR(gs::log::Category::Radio, "N00", "record.failed", "tx_queue_full");
        return std::nullopt;
    }
    ++stats_.accepted;
    return key;
}

// @requirements E01, E02, NFR-04
// Apply the explicit acknowledgement policy; resident check-in and caregiver acknowledgement remain
// separate concepts.
bool NodeRuntime::acknowledge(const EventKey& key, AckClass ack) {
    GS_TRACE(gs::log::Category::Node, "N00", "acknowledge.enter", "-");
    const bool radio_removed = radio_.apply_ack(key, ack);
    if (ack == AckClass::ReceivedVolatile) {
        ++stats_.volatile_acks;
        return radio_removed;
    }
    const bool store_removed = store_.acknowledge(key, ack);
    if (ack == AckClass::Durable && radio_removed && store_removed) ++stats_.durable_acks;
    return radio_removed && (store_removed || ack == AckClass::DiscardedPolicy);
}

std::optional<DomainEvent> NodeRuntime::next_transmission(Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Node, "N00", "next_transmission.enter", "-");
    return radio_.next_due(now_ms);
}

std::optional<NodeMessage> NodeRuntime::next_message(Milliseconds now_ms) {
    const auto event = next_transmission(now_ms);
    if (!event.has_value()) return std::nullopt;
    auto message = node_message_from_event(*event);
    message.power = power_telemetry_;
    return message;
}

void NodeRuntime::transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Node, "N00", "transport_result.enter", "-");
    radio_.record_transport_result(key, accepted_by_radio, now_ms);
}

NodeRuntimeRecoveryState NodeRuntime::recovery_snapshot() const {
    return {node_id_, session_id_, store_.retained_snapshot(),
            radio_.pending_snapshot(), store_.gap_marker_required()};
}

bool NodeRuntime::restore_recovery(const NodeRuntimeRecoveryState& state,
                                   Milliseconds now_ms) {
    if (now_ms < 0 || node_id_.empty() || state.node_id != node_id_ ||
        state.prior_boot_session == 0 || session_id_ <= state.prior_boot_session ||
        store_.size() != 0 || radio_.pending() != 0 || next_sequence_ != 1 ||
        state.retained.size() > store_.capacity() ||
        state.pending.size() > radio_.capacity()) return false;
    std::set<EventKey> pending_keys;
    for (const auto& item : state.pending) {
        const auto& event = item.event;
        if (event.key.source_id != node_id_ || event.key.session_id == 0 ||
            event.key.session_id > state.prior_boot_session ||
            event.key.sequence == 0 || !pending_keys.insert(event.key).second)
            return false;
        const auto retained = std::find_if(state.retained.begin(), state.retained.end(),
            [&event](const DomainEvent& value) {
                return value.key.source_id == event.key.source_id &&
                       value.key.session_id == event.key.session_id &&
                       value.key.sequence == event.key.sequence;
            });
        if (is_business_event(event.kind)) {
            if (retained == state.retained.end() || !same_event(event, *retained)) return false;
        } else if (retained != state.retained.end()) return false;
    }
    std::set<EventKey> retained_keys;
    NodeStore restored_store(store_.capacity());
    for (const auto& event : state.retained) {
        if (!is_business_event(event.kind) ||
            !retained_keys.insert(event.key).second ||
            pending_keys.count(event.key) == 0 ||
            !restored_store.append(event)) return false;
    }
    restored_store.restore_gap_marker(state.gap_marker_required);
    NodeRadio restored_radio(radio_.capacity());
    if (!restored_radio.restore_pending(state.pending, now_ms)) return false;
    store_ = std::move(restored_store);
    radio_ = std::move(restored_radio);
    return true;
}

}  // namespace gs::node
