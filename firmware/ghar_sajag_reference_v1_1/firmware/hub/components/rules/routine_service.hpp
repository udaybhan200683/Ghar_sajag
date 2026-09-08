#pragma once

#include "gs/domain.hpp"

namespace gs::hub {

class RoutineService {
public:
    void start_window(const RoutineConfig& config, HomeMode mode);
    void set_coverage(CoverageState state);
    void apply(const DomainEvent& event);
    IncidentDecision deadline(EpochSeconds now, bool clock_trusted);
    const RoutineState& state() const { return state_; }

private:
    RoutineConfig config_;
    RoutineState state_;
};

}  // namespace gs::hub
