// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S02 Deterministic rules core
// @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The reducer has no network or storage I/O and mutates only the supplied RoutineState. apply_event uses
// window overlap including timestamp uncertainty. evaluate_deadline returns a stable incident key after
// ordered gates. Evidence IDs are not deduplicated or bounded here; callers must not assume pure means
// resource-safe.

#pragma once

#include "gs/domain.hpp"

#include <optional>

namespace gs {

class RulesCore {
public:
    // @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
    // Use the event uncertainty interval at inclusive window boundaries; validate numeric ranges at the
    // input adapter.
    static bool event_overlaps_window(const DomainEvent& event, const RoutineConfig& config);
    // @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
    // Update caller-owned routine evidence; current evidence IDs are neither bounded nor deduplicated
    // (G02).
    static void apply_event(RoutineState& state, const RoutineConfig& config, const DomainEvent& event);
    // @requirements F04, F05, F06, F08, F09, F10, E06, AI08, NFR-01
    // Evaluate ordered due/time/mode/coverage/evidence gates and issue a stable intent once for the
    // current in-memory state.
    static IncidentDecision evaluate_deadline(
        RoutineState& state,
        const RoutineConfig& config,
        EpochSeconds now,
        bool clock_trusted);
};

}  // namespace gs
