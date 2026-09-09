// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H05 Hub rules adapter
// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// RoutineService is the stateful shell around the pure RulesCore. start_window replaces configuration and
// resets the caller-owned routine state. It is the natural owner for future persisted window checkpoints,
// but the current code has no autonomous timer, calendar scheduler or prompt/grace coordinator.

#include "rules/routine_service.hpp"
#include "gs/logging.hpp"

#include "gs/rules.hpp"

namespace gs::hub {

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Replace the active window state; production must persist the transition and define mid-window
// configuration policy.
void RoutineService::start_window(const RoutineConfig& config, HomeMode mode) {
    GS_TRACE(gs::log::Category::Rules, "H05", "start_window.enter", "-");
    config_ = config;
    state_ = RoutineState{};
    state_.window_id = config.window_id;
    state_.mode = mode;
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Supply observation eligibility independently from activity; current coverage does not reconstruct
// historical gaps.
void RoutineService::set_coverage(CoverageState state) {
    GS_TRACE(gs::log::Category::Rules, "H05", "set_coverage.enter", "-");
    state_.coverage = state;
}

void RoutineService::apply(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Rules, "H05", "apply.enter", "-");
    RulesCore::apply_event(state_, config_, event);
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
// still G06.
IncidentDecision RoutineService::deadline(EpochSeconds now, bool clock_trusted) {
    GS_TRACE(gs::log::Category::Rules, "H05", "deadline.enter", "-");
    return RulesCore::evaluate_deadline(state_, config_, now, clock_trusted);
}

}  // namespace gs::hub
