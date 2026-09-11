// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module S02 Deterministic rules core
// @requirements F04, F05, F06, F08, F09, F10, E06, NFR-01
// The core consumes DomainEvent values only. It has no GPIO, radio, storage, network or UI dependency.

#pragma once

#include "gs/domain.hpp"

#include <optional>
#include <string>
#include <vector>

namespace gs {

enum class RuleSignalKind {
    UnexpectedDoorOpen,
    DoorLeftOpen,
    DoorClosedAfterLongOpen,
    DaytimeInactivity
};

enum class RuleTone { Expected, Concern };

struct ActivityRuleState {
    // Anchor used when the monitoring period begins before any activity has been observed. This lets
    // the inactivity rule detect "no activity at all for X hours" without depending on a GPIO event.
    std::optional<EpochSeconds> monitoring_started_at;
    std::optional<EpochSeconds> last_activity_at;
    std::string last_activity_event_id;
    std::optional<EpochSeconds> door_opened_at;
    std::string door_open_event_id;
    bool door_left_open_alerted{false};
    bool inactivity_alerted{false};
};

struct RuleEvaluationContext {
    HomeMode mode{HomeMode::Home};
    CoverageState coverage{CoverageState::Covered};
    bool clock_trusted{true};
};

struct RuleSignalDecision {
    RuleSignalKind kind{RuleSignalKind::DaytimeInactivity};
    RuleTone tone{RuleTone::Concern};
    std::string stable_key;
    std::string reason;
    EpochSeconds duration_seconds{0};
    bool create{false};
    bool resolves_prior{false};
};

class RulesCore {
public:
    static bool event_overlaps_window(const DomainEvent& event, const RoutineConfig& config);
    static void apply_event(RoutineState& state, const RoutineConfig& config, const DomainEvent& event);
    static IncidentDecision evaluate_deadline(
        RoutineState& state,
        const RoutineConfig& config,
        EpochSeconds now,
        bool clock_trusted);

    // Start/restart the observation anchor without inventing a sensor event. The hub calls this when
    // monitoring becomes eligible (for example after boot/config/coverage establishment).
    static void start_activity_monitor(ActivityRuleState& state, EpochSeconds at);

    // Generic activity policy used by simulation and, later, ESP32-backed hub adapters. local_minute is
    // supplied by the trusted-time adapter so the pure rule engine does not own a timezone library.
    static std::vector<RuleSignalDecision> apply_activity_event(
        ActivityRuleState& state,
        const ActivityRuleConfig& config,
        const DomainEvent& event,
        std::uint16_t local_minute,
        RuleEvaluationContext context = {});

    // Timer-driven checks for a door left open and daytime inactivity. Callers persist/route returned
    // decisions; the core only owns deterministic state transitions.
    static std::vector<RuleSignalDecision> evaluate_activity_timers(
        ActivityRuleState& state,
        const ActivityRuleConfig& config,
        EpochSeconds now,
        std::uint16_t local_minute,
        RuleEvaluationContext context = {});

    static bool minute_in_window(std::uint16_t minute, std::uint16_t start, std::uint16_t end);
};

}  // namespace gs
