// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module S01 Node/hub protocol contract
// @requirements E01, E02, E04, E05, NFR-03, NFR-08
#pragma once

#include "gs/domain.hpp"

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <utility>

namespace gs {

// Canonical P0 node<->hub transport policy. Physical ESP-NOW/BLE/Wi-Fi adapters may change,
// but event identity, acknowledgement, heartbeat and retry semantics must not.
struct NodeProtocolPolicy {
    static constexpr std::uint32_t wire_schema = 2;
    static constexpr std::uint32_t ack_schema = 1;
    static constexpr std::uint32_t heartbeat_seconds = 60;
    static constexpr std::uint32_t missed_heartbeats_before_offline = 3;
    static constexpr std::uint32_t offline_grace_seconds = 10;
    static constexpr EpochSeconds offline_after_seconds =
        static_cast<EpochSeconds>(heartbeat_seconds * missed_heartbeats_before_offline + offline_grace_seconds);
    // Fast recovery for transient loss, followed by a low-rate periodic probe.
    // The last delay repeats indefinitely; retries never depend on a new sensor event.
    inline static constexpr std::array<Milliseconds, 5> retry_delays_ms{{200, 600, 1800, 10000, 60000}};
    static constexpr Milliseconds retry_jitter_max_ms = 100;
};

enum class NodeBreadcrumb : std::uint8_t {
    Boot = 1,
    SensingIdle,
    PirRaw,
    PirAccepted,
    EventRecordEnter,
    EventRecordOk,
    EventRecordRejected,
    StoreFull,
    TxIdle,
    TxPrepare,
    TxSend,
    WaitMac,
    MacOk,
    MacFail,
    WaitAppAck,
    AppAck,
    EventRetired,
    RetryBackoff,
    RetryWake,
    FotaPause,
    FotaResume
};

enum class NodeHealthError : std::uint16_t {
    None = 0,
    StoreFull,
    TxQueueFull,
    EncodeFailed,
    SendRejected,
    MacCallbackTimeout,
    AckQueueDrop,
    ControlQueueDrop,
    SendQueueDrop,
    FotaTimeout
};

// Best-effort engineering diagnostics. This is not a business event, has its
// own sequence space, is never retained, and never receives a Durable ACK.
struct NodeHealthSnapshot {
    static constexpr std::uint32_t schema_version = 1;

    std::uint32_t schema{schema_version};
    std::string node_id;
    std::uint64_t session_id{0};
    std::uint64_t health_sequence{0};
    std::uint64_t uptime_ms{0};
    std::uint32_t reset_reason{0};
    bool raw_pir_level{false};
    std::uint32_t raw_pir_edges{0};
    std::uint32_t accepted_pir{0};
    std::uint32_t rejected_pir{0};
    std::uint32_t store_full{0};
    std::uint32_t dropped_motion{0};
    std::uint32_t priority_rejected{0};
    std::uint32_t sensing_liveness{0};
    std::uint32_t runtime_liveness{0};
    NodeBreadcrumb last_breadcrumb{NodeBreadcrumb::Boot};
    std::uint16_t retained_count{0};
    std::uint64_t oldest_sequence{0};
    bool radio_in_flight{false};
    std::uint32_t tx_attempts{0};
    std::uint32_t mac_success{0};
    std::uint32_t mac_failure{0};
    std::uint32_t durable_acks{0};
    std::uint32_t volatile_acks{0};
    std::uint32_t retries{0};
    std::uint32_t periodic_backoff_entries{0};
    NodeHealthError last_error{NodeHealthError::None};
    std::uint32_t free_heap{0};
    std::uint32_t minimum_free_heap{0};
    bool maintenance_active{false};
};

inline bool valid_node_health(const NodeHealthSnapshot& health) {
    return health.schema == NodeHealthSnapshot::schema_version &&
           !health.node_id.empty() && health.session_id > 0 &&
           health.health_sequence > 0;
}

inline SensorType sensor_type_for(EventKind kind) {
    switch (kind) {
        case EventKind::Motion: return SensorType::Pir;
        case EventKind::DoorOpen:
        case EventKind::DoorClosed: return SensorType::Reed;
        case EventKind::OkPressed:
        case EventKind::CallFamily: return SensorType::Button;
        case EventKind::Heartbeat: return SensorType::Heartbeat;
        case EventKind::Gap:
        case EventKind::PrivacyOn:
        case EventKind::PrivacyOff: return SensorType::System;
    }
    return SensorType::Unknown;
}

// Cumulative power telemetry carried with normal node messages/heartbeats. These
// counters are measured by firmware state accounting; current-to-mAh conversion
// is performed against a separately provisioned, bench-calibrated power profile.
struct NodePowerTelemetry {
    std::uint64_t deep_sleep_ms{0};
    std::uint64_t awake_ms{0};
    std::uint64_t sensor_active_ms{0};
    std::uint64_t radio_tx_ms{0};
    std::uint64_t radio_rx_ms{0};
    std::uint64_t radio_tx_packets{0};
    std::uint64_t radio_retries{0};
    std::uint64_t wake_count{0};
    std::uint64_t heartbeat_count{0};
    std::uint64_t boot_count{0};
    std::uint64_t brownout_count{0};
};

inline bool valid_power_telemetry(const NodePowerTelemetry& power) {
    // Sensor/radio activity are subsets of the node's awake interval.
    return power.sensor_active_ms <= power.awake_ms &&
           power.radio_tx_ms <= power.awake_ms &&
           power.radio_rx_ms <= power.awake_ms;
}

// Semantic wire record. The physical adapter may encode this as CBOR, protobuf or a bounded binary
// frame, but it must preserve these fields and meanings. payload_json is a host/reference convenience;
// firmware may instead encode a bounded typed payload union.
struct NodeMessage {
    std::uint32_t schema{NodeProtocolPolicy::wire_schema};
    std::string node_id;
    std::uint64_t session_id{0};
    std::uint64_t sequence_number{0};
    SensorType sensor_type{SensorType::Unknown};
    EventKind event_type{EventKind::Heartbeat};
    std::string location;
    Milliseconds monotonic_ms{0};
    std::optional<EpochSeconds> occurred_at;
    std::uint32_t time_uncertainty_ms{0};
    std::uint16_t battery_mv{0};
    std::int16_t rssi_dbm{0};
    bool is_test{false};
    std::optional<NodePowerTelemetry> power;
    std::string payload_json{"{}"};
};

struct NodeAckMessage {
    std::uint32_t schema{NodeProtocolPolicy::ack_schema};
    std::string node_id;
    std::uint64_t session_id{0};
    std::uint64_t sequence_number{0};
    AckClass ack_type{AckClass::Rejected};
    EpochSeconds hub_received_at{0};
    std::string reason;
};

inline bool valid_node_message(const NodeMessage& message) {
    return message.schema == NodeProtocolPolicy::wire_schema &&
           !message.node_id.empty() && message.session_id > 0 && message.sequence_number > 0 &&
           !message.location.empty() && message.monotonic_ms >= 0 && message.battery_mv <= 6000 &&
           message.rssi_dbm >= -127 && message.rssi_dbm <= 20 &&
           message.time_uncertainty_ms <= 24U * 60U * 60U * 1000U &&
           (!message.power.has_value() || valid_power_telemetry(*message.power));
}

inline NodeMessage node_message_from_event(const DomainEvent& event) {
    return NodeMessage{
        NodeProtocolPolicy::wire_schema,
        event.key.source_id,
        event.key.session_id,
        event.key.sequence,
        event.sensor_type == SensorType::Unknown ? sensor_type_for(event.kind) : event.sensor_type,
        event.kind,
        event.location,
        event.monotonic_ms,
        event.occurred_at > 0 ? std::optional<EpochSeconds>{event.occurred_at} : std::nullopt,
        static_cast<std::uint32_t>(event.uncertainty_s * 1000U),
        event.battery_mv,
        event.rssi_dbm,
        event.is_test,
        std::nullopt,
        "{}"
    };
}

inline DomainEvent domain_event_from_node_message(const NodeMessage& message, EpochSeconds hub_received_at) {
    const auto uncertainty_s = static_cast<std::uint32_t>((message.time_uncertainty_ms + 999U) / 1000U);
    return DomainEvent{
        {message.node_id, message.session_id, message.sequence_number},
        message.event_type,
        message.location,
        message.monotonic_ms,
        message.occurred_at.value_or(0),
        hub_received_at,
        uncertainty_s,
        message.battery_mv,
        message.is_test,
        message.sensor_type,
        message.rssi_dbm
    };
}

inline NodeAckMessage make_node_ack(const EventKey& key, AckClass ack, EpochSeconds hub_received_at,
                                    std::string reason = {}) {
    return NodeAckMessage{NodeProtocolPolicy::ack_schema, key.source_id, key.session_id, key.sequence,
                          ack, hub_received_at, std::move(reason)};
}

}  // namespace gs
