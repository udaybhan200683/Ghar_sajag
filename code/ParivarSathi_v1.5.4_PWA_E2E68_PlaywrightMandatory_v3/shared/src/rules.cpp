// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module S02 Deterministic rules core
// Pure domain rules. Hardware adapters translate GPIO/RF input into DomainEvent before entering here.

#include "gs/rules.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs {

bool RulesCore::event_overlaps_window(const DomainEvent& event, const RoutineConfig& config) {
    GS_TRACE(gs::log::Category::Rules, "S00", "event_overlaps_window.enter", "-");
    const auto lower = event.occurred_at - static_cast<EpochSeconds>(event.uncertainty_s);
    const auto upper = event.occurred_at + static_cast<EpochSeconds>(event.uncertainty_s);
    return upper >= config.start_at && lower <= config.end_at;
}

void RulesCore::apply_event(RoutineState& state, const RoutineConfig& config, const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Rules, "S00", "apply_event.enter", "-");
    if (state.window_id != config.window_id || event.is_test) return;

    if (event.kind == EventKind::PrivacyOn) {
        state.mode = HomeMode::Privacy;
        return;
    }
    if (event.kind == EventKind::PrivacyOff && state.mode == HomeMode::Privacy) {
        state.mode = HomeMode::Home;
        return;
    }
    if (state.mode == HomeMode::Privacy || state.mode == HomeMode::Away || state.mode == HomeMode::Paused) return;

    if (event.kind == EventKind::OkPressed && event_overlaps_window(event, config)) {
        state.explicit_ok = true;
        state.evidence_ids.push_back(event.key.str());
        return;
    }

    const bool location_allowed = config.qualifying_locations.empty() ||
        config.qualifying_locations.count(event.location) > 0;
    if (is_activity(event.kind) && location_allowed && event_overlaps_window(event, config)) {
        state.activity_seen = true;
        state.evidence_ids.push_back(event.key.str());
    }
}

IncidentDecision RulesCore::evaluate_deadline(
    RoutineState& state,
    const RoutineConfig& config,
    EpochSeconds now,
    bool clock_trusted) {
    GS_TRACE(gs::log::Category::Rules, "S00", "evaluate_deadline.enter", "-");
    IncidentDecision result;
    result.stable_key = "missing-morning:" + config.window_id;

    if (!config.enabled || now < config.grace_end_at) {
        result.reason = "window_not_due";
        return result;
    }
    if (!clock_trusted) {
        result.reason = "time_untrusted";
        return result;
    }
    if (state.mode != HomeMode::Home) {
        result.reason = "mode_suppressed";
        return result;
    }
    if (state.coverage != CoverageState::Covered) {
        result.reason = "coverage_unknown";
        return result;
    }
    if (state.activity_seen || state.explicit_ok) {
        result.reason = "evidence_present";
        return result;
    }
    if (state.missing_incident_created) {
        result.reason = "already_created";
        return result;
    }
    state.missing_incident_created = true;
    result.create = true;
    result.reason = "no_qualifying_evidence";
    return result;
}

bool RulesCore::minute_in_window(std::uint16_t minute, std::uint16_t start, std::uint16_t end) {
    if (minute >= 24U * 60U || start >= 24U * 60U || end >= 24U * 60U) return false;
    if (start == end) return true;  // explicit all-day window
    if (start < end) return minute >= start && minute < end;
    return minute >= start || minute < end;  // window crosses midnight
}


void RulesCore::start_activity_monitor(ActivityRuleState& state, EpochSeconds at) {
    GS_TRACE(gs::log::Category::Rules, "S00", "start_activity_monitor.enter", "-");
    state.monitoring_started_at = at;
    state.last_activity_at.reset();
    state.last_activity_event_id.clear();
    state.inactivity_alerted = false;
}

std::vector<RuleSignalDecision> RulesCore::apply_activity_event(
    ActivityRuleState& state,
    const ActivityRuleConfig& config,
    const DomainEvent& event,
    std::uint16_t local_minute,
    RuleEvaluationContext context) {
    GS_TRACE(gs::log::Category::Rules, "S00", "apply_activity_event.enter", "-");
    std::vector<RuleSignalDecision> result;
    if (event.is_test) return result;

    if (!state.monitoring_started_at.has_value()) state.monitoring_started_at = event.occurred_at;

    if (is_activity(event.kind)) {
        state.last_activity_at = event.occurred_at;
        state.last_activity_event_id = event.key.str();
        state.inactivity_alerted = false;
    }

    if (event.kind == EventKind::DoorOpen) {
        state.door_opened_at = event.occurred_at;
        state.door_open_event_id = event.key.str();
        state.door_left_open_alerted = false;
        if (context.mode == HomeMode::Home && context.clock_trusted &&
            config.quiet_hours_enabled &&
            minute_in_window(local_minute, config.quiet_start_minute, config.quiet_end_minute)) {
            result.push_back({RuleSignalKind::UnexpectedDoorOpen, RuleTone::Concern,
                              "unexpected-door:" + event.key.str(), "quiet_hours", 0, true, false});
        }
        return result;
    }

    if (event.kind == EventKind::DoorClosed && state.door_opened_at.has_value()) {
        const auto duration = std::max<EpochSeconds>(0, event.occurred_at - *state.door_opened_at);
        if (state.door_left_open_alerted || duration >= config.door_open_timeout_seconds) {
            result.push_back({RuleSignalKind::DoorClosedAfterLongOpen, RuleTone::Expected,
                              "door-left-open:" + state.door_open_event_id, "door_closed", duration,
                              true, true});
        }
        state.door_opened_at.reset();
        state.door_open_event_id.clear();
        state.door_left_open_alerted = false;
    }
    return result;
}

std::vector<RuleSignalDecision> RulesCore::evaluate_activity_timers(
    ActivityRuleState& state,
    const ActivityRuleConfig& config,
    EpochSeconds now,
    std::uint16_t local_minute,
    RuleEvaluationContext context) {
    GS_TRACE(gs::log::Category::Rules, "S00", "evaluate_activity_timers.enter", "-");
    std::vector<RuleSignalDecision> result;

    const bool rules_eligible = context.mode == HomeMode::Home &&
        context.coverage == CoverageState::Covered && context.clock_trusted;

    if (rules_eligible && state.door_opened_at.has_value() && !state.door_left_open_alerted) {
        const auto duration = std::max<EpochSeconds>(0, now - *state.door_opened_at);
        if (duration >= config.door_open_timeout_seconds) {
            state.door_left_open_alerted = true;
            result.push_back({RuleSignalKind::DoorLeftOpen, RuleTone::Concern,
                              "door-left-open:" + state.door_open_event_id, "door_open_timeout",
                              duration, true, false});
        }
    }

    const bool daytime = rules_eligible && config.daytime_inactivity_enabled &&
        minute_in_window(local_minute, config.daytime_start_minute, config.daytime_end_minute);
    const auto inactivity_anchor = state.last_activity_at.has_value()
        ? state.last_activity_at : state.monitoring_started_at;
    if (daytime && inactivity_anchor.has_value() && !state.inactivity_alerted) {
        const auto duration = std::max<EpochSeconds>(0, now - *inactivity_anchor);
        if (duration >= config.daytime_inactivity_seconds) {
            state.inactivity_alerted = true;
            const auto anchor_id = !state.last_activity_event_id.empty()
                ? state.last_activity_event_id
                : "monitor:" + std::to_string(*inactivity_anchor);
            result.push_back({RuleSignalKind::DaytimeInactivity, RuleTone::Concern,
                              "daytime-inactivity:" + anchor_id,
                              "no_activity_threshold", duration, true, false});
        }
    }
    return result;
}

}  // namespace gs
