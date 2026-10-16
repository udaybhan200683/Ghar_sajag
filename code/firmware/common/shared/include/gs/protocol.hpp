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
    static constexpr std::uint32_t wire_schema = 3;
    static constexpr std::uint32_t previous_wire_schema = 2;
    static constexpr std::uint32_t ack_schema = 1;
    // GS-40 safe default. Target startup uses validated JSON deployment policy.
    // Only the heartbeat is adjustable; offline lease is three intervals + 10 s.
    static constexpr std::uint32_t heartbeat_seconds = 300;
    static constexpr std::uint32_t missed_heartbeats_before_offline = 3;
    static constexpr std::uint32_t offline_grace_seconds = 10;
    static constexpr EpochSeconds offline_after_seconds =
        static_cast<EpochSeconds>(heartbeat_seconds * missed_heartbeats_before_offline + offline_grace_seconds);
    // Historical fallback for callers without a deployment profile. Production
    // per-Node contact coverage uses its explicitly selected deployment lease.
    static constexpr EpochSeconds coverage_after_seconds = 190;
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
    static constexpr std::uint32_t legacy_schema_version = 1;
    static constexpr std::uint32_t schema_version = 2;
    static constexpr std::uint32_t c8_physical_trace_schema_version = 3;
    // Compact authenticated test-only report. The isolated C8 profile emits it
    // only after an ACK-wait trace has closed; commercial images remain on the
    // existing schema and wire layout.
    static constexpr std::uint32_t c8_ack_wait_trace_schema_version = 4;

    enum class SleepWakeCause : std::uint8_t {
        Unknown = 0,
        Timer = 1,
        Gpio = 2,
        Other = 3
    };

    struct C8PhysicalSleepTrace {
        std::uint32_t pir_high_episodes{0};
        std::uint32_t pir_high_total_ms{0};
        std::uint32_t pir_high_max_episode_ms{0};
        std::uint32_t sleep_decisions_inhibited_pir_high{0};
        std::uint32_t entry_races_aborted_pir_high{0};
        std::uint32_t sleep_entries_with_gpio4_high{0};
        bool last_sleep_entry_gpio4_high{false};
        bool last_wake_gpio4_high{false};
        // 0=unknown/no wake observed, 1=radio restore succeeded, 2=failed.
        std::uint8_t last_radio_restore_result{0};
        bool last_owner_resumed{false};
    };

    struct C8AckWaitTrace {
        static constexpr std::size_t event_capacity = 16U;
        static constexpr std::size_t sleep_reason_capacity = 3U;

        enum class EventKind : std::uint8_t {
            MacResult = 1,
            AckWaitStart = 2,
            SleepInhibited = 3,
            SleepAllowedDuringWait = 4,
            DurableAckAccepted = 5,
            AckWaitEnd = 6,
            SleepEligibleAfterWait = 7,
            SleepEntry = 8,
            Wake = 9,
            EventKeyMismatch = 10
        };

        enum class EndReason : std::uint8_t {
            DurableAck = 1,
            ReceiveWindowElapsed = 2,
            SessionReplaced = 3,
            Other = 4
        };

        enum Flag : std::uint16_t {
            Overflow = 1U << 0U,
            MissingInterval = 1U << 1U,
            EventKeyMismatch = 1U << 2U,
            WatchdogExpired = 1U << 3U,
            SleepAllowedWhileWaiting = 1U << 4U,
            CounterSaturated = 1U << 5U,
            TimestampInvalid = 1U << 6U,
            PostAckSleepEligible = 1U << 7U,
            PostAckSleepObserved = 1U << 8U,
            RadioRestoreFailed = 1U << 9U,
            PostAckWakeObserved = 1U << 10U
        };

        struct Event {
            // Monotonic milliseconds since this boot; event order is the array order.
            std::uint32_t uptime_ms{0};
            EventKind kind{EventKind::MacResult};
            // Values are compact context codes: reason slot, result bit,
            // sleep context, or packed wake/radio-restore nibbles.
            std::uint8_t value{0};
        };

        std::uint32_t boot_generation{0};
        std::uint64_t event_key_session_id{0};
        std::uint64_t event_key_sequence{0};
        std::uint8_t event_count{0};
        std::uint8_t overflow_count{0};
        std::uint8_t missing_intervals{0};
        std::uint8_t sleep_entries_during_ack_wait{0};
        std::uint8_t post_ack_sleep_entries{0};
        std::uint8_t post_ack_sleep_eligible_count{0};
        std::uint16_t sleep_inhibit_decisions{0};
        std::uint32_t sleep_inhibitor_mask{0};
        std::uint8_t sleep_reason_count{0};
        std::array<std::uint32_t, sleep_reason_capacity> sleep_reason_masks{};
        std::uint16_t flags{0};
        bool interval_open{false};
        bool evidence_complete{false};
        std::array<Event, event_capacity> events{};
    };

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
    // RAM-only light-sleep diagnostics. They reset with the C3 and are carried
    // only on the existing best-effort NodeHealth frame.
    std::uint32_t light_sleep_entry_count{0};
    std::uint32_t timer_wake_count{0};
    std::uint32_t gpio_wake_count{0};
    std::uint32_t other_wake_count{0};
    SleepWakeCause last_wake_cause{SleepWakeCause::Unknown};
    std::uint32_t last_sleep_requested_ms{0};
    std::uint32_t last_sleep_elapsed_ms{0};
    // Present only in the isolated GS-114 C8 physical HIL profile. It is
    // carried inside the existing authenticated, non-business NodeHealth frame.
    std::optional<C8PhysicalSleepTrace> c8_physical_sleep_trace;
    // Present only in the isolated C8 ACK-wait qualification profile.
    std::optional<C8AckWaitTrace> c8_ack_wait_trace;
};

inline bool valid_node_health(const NodeHealthSnapshot& health) {
    const bool supported_schema =
        health.schema == NodeHealthSnapshot::legacy_schema_version ||
        health.schema == NodeHealthSnapshot::schema_version ||
        health.schema == NodeHealthSnapshot::c8_physical_trace_schema_version ||
        health.schema == NodeHealthSnapshot::c8_ack_wait_trace_schema_version;
    const auto wake_cause = static_cast<std::uint8_t>(health.last_wake_cause);
    const bool trace_matches_schema =
        (health.schema == NodeHealthSnapshot::c8_physical_trace_schema_version) ==
            health.c8_physical_sleep_trace.has_value() &&
        (health.schema == NodeHealthSnapshot::c8_ack_wait_trace_schema_version) ==
            health.c8_ack_wait_trace.has_value() &&
        !(health.c8_physical_sleep_trace && health.c8_ack_wait_trace);
    bool ack_trace_valid = true;
    if (health.c8_ack_wait_trace) {
        const auto& trace = *health.c8_ack_wait_trace;
        constexpr std::uint16_t known_flags =
            NodeHealthSnapshot::C8AckWaitTrace::Overflow |
            NodeHealthSnapshot::C8AckWaitTrace::MissingInterval |
            NodeHealthSnapshot::C8AckWaitTrace::EventKeyMismatch |
            NodeHealthSnapshot::C8AckWaitTrace::WatchdogExpired |
            NodeHealthSnapshot::C8AckWaitTrace::SleepAllowedWhileWaiting |
            NodeHealthSnapshot::C8AckWaitTrace::CounterSaturated |
            NodeHealthSnapshot::C8AckWaitTrace::TimestampInvalid |
            NodeHealthSnapshot::C8AckWaitTrace::PostAckSleepEligible |
            NodeHealthSnapshot::C8AckWaitTrace::PostAckSleepObserved |
            NodeHealthSnapshot::C8AckWaitTrace::RadioRestoreFailed |
            NodeHealthSnapshot::C8AckWaitTrace::PostAckWakeObserved;
        std::uint32_t previous_ms = 0;
        bool ordered = true;
        std::size_t starts = 0;
        std::size_t ends = 0;
        std::size_t mac_results = 0;
        std::size_t durable_acks = 0;
        bool interval_open = false;
        bool sleep_open = false;
        for (std::size_t i = 0; i < trace.event_count &&
             i < trace.events.size(); ++i) {
            const auto& event = trace.events[i];
            const auto kind = static_cast<std::uint8_t>(event.kind);
            if (kind < static_cast<std::uint8_t>(
                           NodeHealthSnapshot::C8AckWaitTrace::EventKind::MacResult) ||
                kind > static_cast<std::uint8_t>(
                           NodeHealthSnapshot::C8AckWaitTrace::EventKind::EventKeyMismatch) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepInhibited &&
                 event.value >= trace.sleep_reason_count) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::MacResult &&
                 event.value > 1U) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::AckWaitStart &&
                 event.value != 0U && event.value != 1U && event.value != 0xffU) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::AckWaitEnd &&
                 event.value > static_cast<std::uint8_t>(
                     NodeHealthSnapshot::C8AckWaitTrace::EndReason::Other)) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepEligibleAfterWait &&
                 event.value > 1U) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepEntry &&
                 event.value > 2U) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::Wake &&
                 event.value > 0x33U) ||
                (event.kind ==
                     NodeHealthSnapshot::C8AckWaitTrace::EventKind::Wake &&
                 (event.value & 0x0fU) != 1U && (event.value & 0x0fU) != 2U) ||
                (i != 0U && event.uptime_ms < previous_ms)) ordered = false;
            if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::MacResult)
                ++mac_results;
            if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::AckWaitStart) {
                ++starts;
                if (interval_open) ordered = false;
                interval_open = true;
            }
            if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::AckWaitEnd) {
                ++ends;
                if (!interval_open) ordered = false;
                interval_open = false;
            }
            if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepEntry) {
                if (sleep_open) ordered = false;
                sleep_open = true;
            }
            if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::Wake) {
                if (!sleep_open) ordered = false;
                sleep_open = false;
            }
            if (event.kind ==
                NodeHealthSnapshot::C8AckWaitTrace::EventKind::DurableAckAccepted)
                ++durable_acks;
            previous_ms = event.uptime_ms;
        }
        ack_trace_valid = trace.boot_generation != 0U &&
            trace.event_count <= trace.events.size() &&
            trace.sleep_reason_count <= trace.sleep_reason_masks.size() &&
            trace.event_key_session_id != 0U && trace.event_key_sequence != 0U &&
            (trace.flags & static_cast<std::uint16_t>(~known_flags)) == 0U && ordered &&
            interval_open == trace.interval_open && ends <= starts &&
            (!trace.evidence_complete || !sleep_open) &&
            (!trace.evidence_complete ||
             (!trace.interval_open && starts > 0U && starts == ends &&
              mac_results > 0U && durable_acks == 1U &&
              trace.post_ack_sleep_eligible_count > 0U &&
              trace.post_ack_sleep_entries > 0U &&
              trace.overflow_count == 0U &&
              trace.missing_intervals == 0U &&
              trace.sleep_entries_during_ack_wait == 0U &&
              (trace.flags & (NodeHealthSnapshot::C8AckWaitTrace::Overflow |
                              NodeHealthSnapshot::C8AckWaitTrace::MissingInterval |
                              NodeHealthSnapshot::C8AckWaitTrace::EventKeyMismatch |
                              NodeHealthSnapshot::C8AckWaitTrace::WatchdogExpired |
                              NodeHealthSnapshot::C8AckWaitTrace::SleepAllowedWhileWaiting |
                              NodeHealthSnapshot::C8AckWaitTrace::CounterSaturated |
                              NodeHealthSnapshot::C8AckWaitTrace::TimestampInvalid |
                              NodeHealthSnapshot::C8AckWaitTrace::RadioRestoreFailed)) == 0U &&
              (trace.flags & (NodeHealthSnapshot::C8AckWaitTrace::PostAckSleepEligible |
                              NodeHealthSnapshot::C8AckWaitTrace::PostAckSleepObserved |
                              NodeHealthSnapshot::C8AckWaitTrace::PostAckWakeObserved)) ==
                  (NodeHealthSnapshot::C8AckWaitTrace::PostAckSleepEligible |
                   NodeHealthSnapshot::C8AckWaitTrace::PostAckSleepObserved |
                   NodeHealthSnapshot::C8AckWaitTrace::PostAckWakeObserved)));
    }
    return supported_schema && !health.node_id.empty() &&
           health.session_id > 0 && health.health_sequence > 0 &&
           trace_matches_schema &&
           ack_trace_valid &&
           (!health.c8_physical_sleep_trace ||
            health.c8_physical_sleep_trace->last_radio_restore_result <= 2U) &&
           (health.schema == NodeHealthSnapshot::legacy_schema_version ||
            health.schema == NodeHealthSnapshot::c8_ack_wait_trace_schema_version ||
            wake_cause <= static_cast<std::uint8_t>(NodeHealthSnapshot::SleepWakeCause::Other));
}

inline const char* node_health_sleep_wake_cause_name(
    NodeHealthSnapshot::SleepWakeCause cause) {
    switch (cause) {
        case NodeHealthSnapshot::SleepWakeCause::Timer: return "TIMER";
        case NodeHealthSnapshot::SleepWakeCause::Gpio: return "GPIO";
        case NodeHealthSnapshot::SleepWakeCause::Other: return "OTHER";
        default: return "UNKNOWN";
    }
}

inline SensorType sensor_type_for(EventKind kind) {
    switch (kind) {
        case EventKind::Motion:
        case EventKind::MotionSummary: return SensorType::Pir;
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
    std::optional<DomainEvent::MotionAggregate> motion_aggregate{std::nullopt};
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
    return (message.schema == NodeProtocolPolicy::wire_schema ||
            message.schema == NodeProtocolPolicy::previous_wire_schema) &&
           !message.node_id.empty() && message.session_id > 0 && message.sequence_number > 0 &&
           !message.location.empty() && message.monotonic_ms >= 0 && message.battery_mv <= 6000 &&
           message.rssi_dbm >= -127 && message.rssi_dbm <= 20 &&
           message.time_uncertainty_ms <= 24U * 60U * 60U * 1000U &&
           (!message.power.has_value() || valid_power_telemetry(*message.power)) &&
           (message.event_type == EventKind::MotionSummary
                ? message.schema == NodeProtocolPolicy::wire_schema &&
                  message.motion_aggregate.has_value() &&
                  valid_motion_aggregate(*message.motion_aggregate)
                : !message.motion_aggregate.has_value());
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
        "{}",
        event.motion_aggregate
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
        message.rssi_dbm,
        message.motion_aggregate
    };
}

inline NodeAckMessage make_node_ack(const EventKey& key, AckClass ack, EpochSeconds hub_received_at,
                                    std::string reason = {}) {
    return NodeAckMessage{NodeProtocolPolicy::ack_schema, key.source_id, key.session_id, key.sequence,
                          ack, hub_received_at, std::move(reason)};
}

}  // namespace gs
