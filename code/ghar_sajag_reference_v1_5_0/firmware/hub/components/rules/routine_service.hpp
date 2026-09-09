// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H05 Hub rules adapter
// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// RoutineService is the stateful shell around the pure RulesCore. start_window replaces configuration and
// resets the caller-owned routine state. It is the natural owner for future persisted window checkpoints,
// but the current code has no autonomous timer, calendar scheduler or prompt/grace coordinator.

#pragma once

#include "gs/domain.hpp"

namespace gs::hub {

class RoutineService {
public:
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Replace the active window state; production must persist the transition and define mid-window
    // configuration policy.
    void start_window(const RoutineConfig& config, HomeMode mode);
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Supply observation eligibility independently from activity; current coverage does not reconstruct
    // historical gaps.
    void set_coverage(CoverageState state);
    void apply(const DomainEvent& event);
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
    // still G06.
    IncidentDecision deadline(EpochSeconds now, bool clock_trusted);
    const RoutineState& state() const { return state_; }

private:
    RoutineConfig config_;
    RoutineState state_;
};

}  // namespace gs::hub
