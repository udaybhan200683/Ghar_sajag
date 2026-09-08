#include "rules/routine_service.hpp"
#include "gs/logging.hpp"

#include "gs/rules.hpp"

namespace gs::hub {

void RoutineService::start_window(const RoutineConfig& config, HomeMode mode) {
    GS_TRACE(gs::log::Category::Rules, "H05", "start_window.enter", "-");
    config_ = config;
    state_ = RoutineState{};
    state_.window_id = config.window_id;
    state_.mode = mode;
}

void RoutineService::set_coverage(CoverageState state) {
    GS_TRACE(gs::log::Category::Rules, "H05", "set_coverage.enter", "-");
    state_.coverage = state;
}

void RoutineService::apply(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Rules, "H05", "apply.enter", "-");
    RulesCore::apply_event(state_, config_, event);
}

IncidentDecision RoutineService::deadline(EpochSeconds now, bool clock_trusted) {
    GS_TRACE(gs::log::Category::Rules, "H05", "deadline.enter", "-");
    return RulesCore::evaluate_deadline(state_, config_, now, clock_trusted);
}

}  // namespace gs::hub
