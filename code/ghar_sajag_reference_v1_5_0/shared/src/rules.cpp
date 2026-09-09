// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S02 Deterministic rules core
// @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The reducer has no network or storage I/O and mutates only the supplied RoutineState. apply_event uses
// window overlap including timestamp uncertainty. evaluate_deadline returns a stable incident key after
// ordered gates. Evidence IDs are not deduplicated or bounded here; callers must not assume pure means
// resource-safe.

#include "gs/rules.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs {

// @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
// Use the event uncertainty interval at inclusive window boundaries; validate numeric ranges at the
// input adapter.
bool RulesCore::event_overlaps_window(const DomainEvent& event, const RoutineConfig& config) {
    GS_TRACE(gs::log::Category::Rules, "S00", "event_overlaps_window.enter", "-");
    const auto lower = event.occurred_at - static_cast<EpochSeconds>(event.uncertainty_s);
    const auto upper = event.occurred_at + static_cast<EpochSeconds>(event.uncertainty_s);
    return upper >= config.start_at && lower <= config.end_at;
}

// @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
// Update caller-owned routine evidence; current evidence IDs are neither bounded nor deduplicated
// (G02).
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

// @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
// Evaluate ordered due/time/mode/coverage/evidence gates and issue a stable intent once for the
// current in-memory state.
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

}  // namespace gs
