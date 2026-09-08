#pragma once

#include "gs/domain.hpp"

#include <optional>

namespace gs {

class RulesCore {
public:
    static bool event_overlaps_window(const DomainEvent& event, const RoutineConfig& config);
    static void apply_event(RoutineState& state, const RoutineConfig& config, const DomainEvent& event);
    static IncidentDecision evaluate_deadline(
        RoutineState& state,
        const RoutineConfig& config,
        EpochSeconds now,
        bool clock_trusted);
};

}  // namespace gs
