// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S01 Shared contracts
// @requirements F01, E02, E06, E07, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Contracts are the shared vocabulary across languages. Field names and event identity require explicit
// adapters; the C++ enum spelling is not the JSON wire spelling. The current contracts check validates
// source structure, so add producer/consumer golden payload tests before relying on schema compatibility.

#pragma once

#include <cstdint>
#include <optional>
#include <set>
#include <string>
#include <vector>

namespace gs {

using EpochSeconds = std::int64_t;
using Milliseconds = std::int64_t;

enum class EventKind {
    Motion,
    DoorOpen,
    DoorClosed,
    OkPressed,
    CallFamily,
    Heartbeat,
    PrivacyOn,
    PrivacyOff,
    Gap
};

enum class AckClass { Durable, ReceivedVolatile, DiscardedPolicy, Rejected };
enum class HomeMode { Home, Away, Paused, Visitor, Privacy };
enum class CoverageState { Covered, Unknown, Fault };
enum class IncidentKind { MissingMorningActivity, CallFamily, Connectivity, Storage };
enum class IncidentState { Open, Claimed, Acknowledged, Resolved, RouteExhausted };

struct EventKey {
    std::string source_id;
    std::uint64_t session_id{0};
    std::uint64_t sequence{0};

    std::string str() const {
        return source_id + ":" + std::to_string(session_id) + ":" + std::to_string(sequence);
    }

    bool operator<(const EventKey& other) const {
        if (source_id != other.source_id) return source_id < other.source_id;
        if (session_id != other.session_id) return session_id < other.session_id;
        return sequence < other.sequence;
    }
};

struct DomainEvent {
    EventKey key;
    EventKind kind{EventKind::Heartbeat};
    std::string location;
    Milliseconds monotonic_ms{0};
    EpochSeconds occurred_at{0};
    EpochSeconds received_at{0};
    std::uint32_t uncertainty_s{0};
    std::uint16_t battery_mv{0};
    bool is_test{false};
};

struct RoutineConfig {
    std::string window_id;
    EpochSeconds start_at{0};
    EpochSeconds end_at{0};
    EpochSeconds grace_end_at{0};
    std::set<std::string> qualifying_locations;
    bool enabled{true};
};

struct RoutineState {
    std::string window_id;
    bool activity_seen{false};
    bool explicit_ok{false};
    bool missing_incident_created{false};
    CoverageState coverage{CoverageState::Unknown};
    HomeMode mode{HomeMode::Home};
    std::vector<std::string> evidence_ids;
};

struct IncidentDecision {
    IncidentKind kind{IncidentKind::MissingMorningActivity};
    std::string stable_key;
    std::string reason;
    bool create{false};
};

struct NodeConfig {
    std::uint32_t version{0};
    std::string node_id;
    std::string location;
    bool pir_enabled{false};
    bool reed_enabled{false};
    std::uint32_t heartbeat_seconds{60};
};

struct HomeConfig {
    std::uint32_t version{0};
    std::string home_id;
    std::string timezone;
    HomeMode mode{HomeMode::Home};
    RoutineConfig morning;
};

inline bool is_business_event(EventKind kind) {
    return kind != EventKind::Heartbeat;
}

inline bool is_activity(EventKind kind) {
    return kind == EventKind::Motion || kind == EventKind::DoorOpen || kind == EventKind::DoorClosed;
}

}  // namespace gs
