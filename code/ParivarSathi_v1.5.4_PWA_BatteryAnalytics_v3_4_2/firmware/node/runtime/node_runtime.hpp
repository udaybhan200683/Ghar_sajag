// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module N02 Node radio
// @requirements E01, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The pending transmission queue owns retry timing but does not own physical RF. A caller asks next_due,
// transmits through an adapter, then reports the transport result. Only an application acknowledgement
// with the expected event identity may retire retained business data. Call this component from one owner,
// not directly from concurrent radio callbacks.

#pragma once

#include "gs/domain.hpp"
#include "gs/protocol.hpp"
#include "radio/node_radio.hpp"
#include "storage/node_store.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace gs::node {

struct NodeRuntimeStats {
    std::uint32_t record_calls{0};
    std::uint32_t accepted{0};
    std::uint32_t store_full{0};
    std::uint32_t tx_queue_full{0};
    std::uint32_t dropped_motion{0};
    std::uint32_t priority_rejected{0};
    std::uint32_t durable_acks{0};
    std::uint32_t volatile_acks{0};
};

struct NodeRuntimeRecoveryState {
    std::string node_id;
    std::uint64_t prior_boot_session{0};
    std::vector<DomainEvent> retained;
    std::vector<PendingTx> pending;
    bool gap_marker_required{false};
};

class NodeRuntime {
public:
    NodeRuntime(std::string node_id, std::uint64_t session_id,
                std::size_t journal_capacity = 32, std::size_t tx_capacity = 32);
    // @requirements E01, E02, NFR-04
    // Allocate one identity and atomically admit it to both bounded retained
    // and retry state. A refusal is counted and cannot strand a store record.
    std::optional<EventKey> record(EventKind kind, const std::string& location,
                                   Milliseconds monotonic_ms, EpochSeconds occurred_at,
                                   std::uint32_t uncertainty_s = 0, std::uint16_t battery_mv = 0,
                                   bool is_test = false, SensorType sensor_type = SensorType::Unknown,
                                   std::int16_t rssi_dbm = 0);
    // @requirements E01, E02, NFR-04
    // Apply the explicit acknowledgement policy; resident check-in and caregiver acknowledgement remain
    // separate concepts.
    bool acknowledge(const EventKey& key, AckClass ack);
    std::optional<DomainEvent> next_transmission(Milliseconds now_ms);
    // Typed wire contract for the eventual ESP-NOW/other physical adapter.
    std::optional<NodeMessage> next_message(Milliseconds now_ms);
    // Platform code updates cumulative counters; the semantic wire message then
    // carries them with the next event/heartbeat.
    void set_power_telemetry(const NodePowerTelemetry& power) { power_telemetry_ = power; }
    const std::optional<NodePowerTelemetry>& power_telemetry() const { return power_telemetry_; }
    void transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms);
    std::size_t persisted() const { return store_.size(); }
    std::size_t pending() const { return radio_.pending(); }
    bool gap_marker_required() const { return store_.gap_marker_required(); }
    std::uint64_t next_sequence() const { return next_sequence_; }
    std::optional<EventKey> oldest_pending_key() const { return radio_.oldest_key(); }
    bool has_pending_key(const EventKey& key) const { return radio_.contains(key); }
    std::optional<Milliseconds> next_retry_deadline() const { return radio_.next_due_at(); }
    void set_outage_profile(bool enabled, Milliseconds now_ms) {
        radio_.set_outage_profile(enabled, now_ms);
    }
    bool outage_profile() const { return radio_.outage_profile(); }
    const NodeRuntimeStats& stats() const { return stats_; }
    const NodeRadioStats& radio_stats() const { return radio_.stats(); }
    NodeRuntimeRecoveryState recovery_snapshot() const;
    // Only a fresh runtime with a strictly newer authenticated boot session
    // may restore prior event identities. Target flash commit is separate.
    bool restore_recovery(const NodeRuntimeRecoveryState& state, Milliseconds now_ms);

private:
    std::string node_id_;
    std::uint64_t session_id_;
    std::uint64_t next_sequence_{1};
    NodeStore store_;
    NodeRadio radio_;
    std::optional<NodePowerTelemetry> power_telemetry_;
    NodeRuntimeStats stats_;
};

}  // namespace gs::node
