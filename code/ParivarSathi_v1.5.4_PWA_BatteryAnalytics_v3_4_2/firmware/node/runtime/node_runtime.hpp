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

namespace gs::node {

class NodeRuntime {
public:
    NodeRuntime(std::string node_id, std::uint64_t session_id,
                std::size_t journal_capacity = 64, std::size_t tx_capacity = 32);
    // @requirements E01, E02, NFR-04
    // Create one identity and retain before enqueue; failed enqueue can strand the stored event until a
    // refill adapter is added (G05).
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

private:
    std::string node_id_;
    std::uint64_t session_id_;
    std::uint64_t next_sequence_{1};
    NodeStore store_;
    NodeRadio radio_;
    std::optional<NodePowerTelemetry> power_telemetry_;
};

}  // namespace gs::node
