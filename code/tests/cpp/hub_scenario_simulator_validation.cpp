#include "firmware/hub/simulation/hub_scenario_simulator.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {
using namespace gs;
using namespace gs::hub::simulation;

struct Authorization {
    bool allowed{true};
    unsigned calls{0};
};

bool authorize_test_home(void* opaque, const std::string& home_id,
                         std::uint64_t session) {
    auto& auth = *static_cast<Authorization*>(opaque);
    ++auth.calls;
    return auth.allowed && home_id.rfind("test-home-", 0) == 0 && session == 7001;
}

void require(bool condition, const std::string& message, unsigned& checks) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL " << message << '\n';
        std::exit(1);
    }
}

ScenarioPlan base_plan(const char* id) {
    ScenarioPlan plan;
    plan.scenario_id = id;
    plan.home_id = "test-home-r1-simulator";
    plan.run_id = 42001;
    plan.authenticated_session = 7001;
    plan.configuration_version = 3;
    plan.deterministic_seed = 19;
    plan.virtual_start_epoch = 1'800'000'000;
    return plan;
}

ScenarioStep event_step(EventKind kind, const char* location,
                        std::uint32_t offset, std::uint16_t minute,
                        std::uint64_t sequence = 0) {
    ScenarioStep step;
    step.kind = StepKind::Event;
    step.event_kind = kind;
    step.location = location;
    step.offset_seconds = offset;
    step.local_minute = minute;
    step.event_sequence = sequence;
    return step;
}

ScenarioStep timer_step(std::uint32_t offset, std::uint16_t minute) {
    ScenarioStep step;
    step.kind = StepKind::EvaluateActivityTimers;
    step.offset_seconds = offset;
    step.local_minute = minute;
    return step;
}

void configure_morning_routine(ScenarioPlan& plan, CoverageState coverage) {
    plan.evaluate_morning_routine = true;
    plan.coverage = coverage;
    plan.morning_routine.window_id = "morning-r1-test-window";
    plan.morning_routine.start_at = plan.virtual_start_epoch + 6U * 60U * 60U;
    plan.morning_routine.end_at = plan.virtual_start_epoch + 8U * 60U * 60U;
    plan.morning_routine.grace_end_at = plan.virtual_start_epoch +
        8U * 60U * 60U + 30U * 60U;
    plan.morning_routine.qualifying_locations = {"kitchen", "bathroom"};
}

void finish(HubScenarioSimulator& simulator, unsigned& checks) {
    unsigned guard = 0;
    while (simulator.active() && guard++ < kMaxScenarioSteps)
        (void)simulator.advance();
    require(simulator.result().status == RunStatus::Completed,
            "bounded scenario reaches completed state", checks);
    require(guard <= kMaxScenarioSteps, "bounded scenario terminates within step cap", checks);
}

void test_morning_sequence(unsigned& checks) {
    auto plan = base_plan("morning-sequence-v1");
    plan.step_count = 3;
    plan.steps[0] = event_step(EventKind::Motion, "room1", 0, 420);
    plan.steps[1] = event_step(EventKind::Motion, "bathroom", 60, 430);
    plan.steps[2] = event_step(EventKind::Motion, "kitchen", 120, 440);
    Authorization auth;
    HubScenarioSimulator simulator;
    const auto accepted = simulator.begin(plan, authorize_test_home, &auth);
    require(accepted,
            std::string("authenticated TEST_ONLY Home accepts a bounded scenario status=") +
                run_status_name(simulator.result().status) + " auth_calls=" +
                std::to_string(auth.calls), checks);
    finish(simulator, checks);
    const auto& result = simulator.result();
    require(result.event_count == 3, "morning scenario records all three generated events", checks);
    require(result.decision_count == 1 &&
            result.decisions[0].decision.kind == RuleSignalKind::MorningRoutineCompleted,
            "existing RulesCore evaluates the configured morning sequence", checks);
    require(result.events[0].is_test && result.events[0].sensor_type == SensorType::System &&
            result.events[0].key.source_id == "hub-sim-test" &&
            result.events[0].key.physical_device_id.empty(),
            "synthetic events cannot claim a physical C3/PIR identity", checks);
    require(result.stages[0].evidence == EvidenceState::Observed &&
            result.stages[1].evidence == EvidenceState::Observed,
            "only generator and shared RulesCore stages are observed", checks);
    require(result.stages[2].evidence == EvidenceState::NotRun &&
            result.stages[3].evidence == EvidenceState::NotRun &&
            result.stages[4].evidence == EvidenceState::NotRun,
            "runtime admission, durable commit and CloudSync are not fabricated", checks);
}

void test_night_and_door_rules(unsigned& checks) {
    auto plan = base_plan("night-bathroom-v1");
    plan.step_count = 5;
    for (std::size_t i = 0; i < plan.step_count; ++i)
        plan.steps[i] = event_step(EventKind::Motion, "bathroom",
            static_cast<std::uint32_t>(i * 360U),
            static_cast<std::uint16_t>(1380U + i * 6U));
    Authorization auth;
    HubScenarioSimulator simulator;
    require(simulator.begin(plan, authorize_test_home, &auth),
            "night scenario starts under an authorized TEST_ONLY session", checks);
    finish(simulator, checks);
    require(simulator.result().decision_count == 1 &&
            simulator.result().decisions[0].decision.kind ==
                RuleSignalKind::UnusualNightBathroomActivity,
            "night visit threshold is evaluated by the existing RulesCore", checks);

    plan = base_plan("door-open-close-v1");
    plan.step_count = 2;
    plan.steps[0] = event_step(EventKind::DoorOpen, "main-door", 0, 120);
    plan.steps[1] = event_step(EventKind::DoorClosed, "main-door", 3U * 3600U, 300);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "door scenario begins", checks);
    finish(simulator, checks);
    require(simulator.result().decision_count == 2 &&
            simulator.result().decisions[0].decision.kind == RuleSignalKind::UnexpectedDoorOpen &&
            simulator.result().decisions[1].decision.kind == RuleSignalKind::DoorClosedAfterLongOpen,
            std::string("door concern and recovery are both produced by the shared rule engine count=") +
                std::to_string(simulator.result().decision_count) +
                (simulator.result().decision_count > 0 ? " first=" +
                    std::to_string(static_cast<int>(simulator.result().decisions[0].decision.kind)) : ""), checks);
}

void test_inactivity_coverage_and_time(unsigned& checks) {
    auto plan = base_plan("daytime-inactivity-v1");
    plan.step_count = 1;
    plan.steps[0] = timer_step(3U * 3600U, 660);
    Authorization auth;
    HubScenarioSimulator simulator;
    require(simulator.begin(plan, authorize_test_home, &auth),
            "inactivity timer scenario begins", checks);
    finish(simulator, checks);
    require(simulator.result().decision_count == 1 &&
            simulator.result().decisions[0].decision.kind == RuleSignalKind::DaytimeInactivity,
            "covered observation window produces the deterministic inactivity signal", checks);

    plan = base_plan("unknown-coverage-no-inactivity-v1");
    plan.coverage = CoverageState::Unknown;
    plan.step_count = 1;
    plan.steps[0] = timer_step(3U * 3600U, 660);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "unknown-coverage scenario begins", checks);
    finish(simulator, checks);
    require(simulator.result().decision_count == 0,
            "unknown coverage does not become an inactivity finding", checks);

    plan = base_plan("untrusted-simulated-clock-v1");
    plan.virtual_clock_trusted = false;
    plan.step_count = 1;
    plan.steps[0] = timer_step(3U * 3600U, 660);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "untrusted virtual clock remains a runnable negative case", checks);
    finish(simulator, checks);
    require(simulator.result().decision_count == 0,
            "untrusted virtual time suppresses time-dependent decisions", checks);
}

void test_deterministic_morning_routine(unsigned& checks) {
    auto plan = base_plan("morning-activity-missing-v1");
    configure_morning_routine(plan, CoverageState::Covered);
    plan.step_count = 1;
    plan.steps[0] = timer_step(8U * 3600U + 30U * 60U, 510);
    Authorization auth;
    HubScenarioSimulator simulator;
    require(simulator.begin(plan, authorize_test_home, &auth),
            "covered morning-routine deadline scenario begins", checks);
    finish(simulator, checks);
    const auto& missing = simulator.result();
    require(missing.routine_decision_count == 1 &&
            missing.routine_decisions[0].decision.create &&
            missing.routine_decisions[0].decision.reason == "no_qualifying_evidence" &&
            missing.routine_decisions[0].decision.kind == IncidentKind::MissingMorningActivity,
            "existing RoutineService reports missing morning activity from covered evidence", checks);
    require(missing.routine_state.missing_incident_created &&
            !missing.routine_state.activity_seen && !missing.routine_state.explicit_ok,
            "routine snapshot preserves the deterministic missing-evidence decision", checks);

    plan = base_plan("morning-explicit-ok-v1");
    configure_morning_routine(plan, CoverageState::Covered);
    plan.step_count = 2;
    plan.steps[0] = event_step(EventKind::OkPressed, "caregiver-check-in", 7U * 3600U, 420);
    plan.steps[1] = timer_step(8U * 3600U + 30U * 60U, 510);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "morning check-in suppression scenario begins", checks);
    finish(simulator, checks);
    const auto& check_in = simulator.result();
    require(check_in.routine_state.explicit_ok &&
            check_in.routine_decision_count == 1 &&
            !check_in.routine_decisions[0].decision.create &&
            check_in.routine_decisions[0].decision.reason == "evidence_present",
            "I Am OK evidence suppresses the same existing missing-activity incident", checks);
    require(check_in.routine_state.evidence_ids.size() == 1 &&
            check_in.routine_state.evidence_ids[0] == check_in.events[0].key.str(),
            "routine evidence retains the original synthetic event identity", checks);

    plan = base_plan("morning-motion-satisfies-v1");
    configure_morning_routine(plan, CoverageState::Covered);
    plan.step_count = 2;
    plan.steps[0] = event_step(EventKind::Motion, "kitchen", 7U * 3600U, 420);
    plan.steps[1] = timer_step(8U * 3600U + 30U * 60U, 510);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "qualifying morning activity scenario begins", checks);
    finish(simulator, checks);
    require(simulator.result().routine_state.activity_seen &&
            !simulator.result().routine_decisions[0].decision.create &&
            simulator.result().routine_decisions[0].decision.reason == "evidence_present",
            "qualifying activity in the configured window prevents a missing-routine incident", checks);

    plan = base_plan("morning-unknown-coverage-v1");
    configure_morning_routine(plan, CoverageState::Unknown);
    plan.step_count = 1;
    plan.steps[0] = timer_step(8U * 3600U + 30U * 60U, 510);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "unknown-coverage routine scenario begins", checks);
    finish(simulator, checks);
    require(!simulator.result().routine_decisions[0].decision.create &&
            simulator.result().routine_decisions[0].decision.reason == "coverage_unknown",
            "missing coverage remains unknown rather than an inactivity finding", checks);

    plan = base_plan("morning-untrusted-time-v1");
    configure_morning_routine(plan, CoverageState::Covered);
    plan.virtual_clock_trusted = false;
    plan.step_count = 1;
    plan.steps[0] = timer_step(8U * 3600U + 30U * 60U, 510);
    require(simulator.begin(plan, authorize_test_home, &auth),
            "untrusted-clock routine scenario begins", checks);
    finish(simulator, checks);
    require(!simulator.result().routine_decisions[0].decision.create &&
            simulator.result().routine_decisions[0].decision.reason == "time_untrusted",
            "untrusted virtual time cannot create a missing-activity incident", checks);

    plan = base_plan("morning-invalid-window-v1");
    configure_morning_routine(plan, CoverageState::Covered);
    plan.morning_routine.grace_end_at = plan.morning_routine.start_at - 1;
    plan.step_count = 1;
    plan.steps[0] = timer_step(60, 10);
    require(!simulator.begin(plan, authorize_test_home, &auth) &&
            simulator.result().status == RunStatus::Rejected,
            "invalid routine chronology is rejected before scenario execution", checks);

    plan = base_plan("disabled-routine-input-bound-v1");
    plan.step_count = 1;
    plan.steps[0] = timer_step(60, 10);
    plan.morning_routine.qualifying_locations.insert(std::string(25, 'x'));
    require(!simulator.begin(plan, authorize_test_home, &auth) &&
            simulator.result().status == RunStatus::Rejected,
            "routine strings stay bounded even when routine evaluation is disabled", checks);
}

void test_authorization_bounds_and_duplicates(unsigned& checks) {
    auto plan = base_plan("auth-expiry-and-duplicate-v1");
    plan.step_count = 2;
    plan.steps[0] = event_step(EventKind::Motion, "room", 0, 720, 8);
    plan.steps[1] = event_step(EventKind::Motion, "room", 1, 720, 8);
    Authorization auth;
    HubScenarioSimulator simulator;
    require(simulator.begin(plan, authorize_test_home, &auth),
            "authorized run begins", checks);
    require(simulator.advance() == RunStatus::Running &&
            simulator.result().event_count == 1,
            "one bounded event is emitted per Hub-owner step", checks);
    auth.allowed = false;
    require(simulator.advance() == RunStatus::AuthorizationExpired &&
            simulator.result().event_count == 1,
            "revoked authorization prevents later events in the same run", checks);

    auth.allowed = true;
    require(simulator.begin(plan, authorize_test_home, &auth),
            "deterministic duplicate test run begins", checks);
    finish(simulator, checks);
    require(simulator.result().event_count == 2 &&
            simulator.result().events[0].key.str() == simulator.result().events[1].key.str(),
            "explicit duplicate sequence preserves the original synthetic identity", checks);

    auto invalid = plan;
    invalid.home_id = "real-home-1";
    require(!simulator.begin(invalid, authorize_test_home, &auth) &&
            simulator.result().status == RunStatus::Rejected,
            "real Home identifiers are rejected before scenario execution", checks);
    invalid = plan;
    invalid.steps[0].event_kind = EventKind::PrivacyOn;
    require(!simulator.begin(invalid, authorize_test_home, &auth),
            "scenario input cannot change Hub privacy state", checks);
    invalid = plan;
    invalid.steps[0].location.assign(25, 'x');
    require(!simulator.begin(invalid, authorize_test_home, &auth),
            "oversized event input is rejected", checks);
    invalid = plan;
    invalid.step_count = kMaxScenarioSteps + 1U;
    require(!simulator.begin(invalid, authorize_test_home, &auth),
            "scenario step count is bounded", checks);
    require(!simulator.begin(plan, nullptr, nullptr),
            "missing authenticated authorization adapter is rejected", checks);
}

void test_cancel_and_repeatability(unsigned& checks) {
    auto plan = base_plan("repeatable-motion-pair-v1");
    plan.step_count = 2;
    plan.steps[0] = event_step(EventKind::Motion, "room", 0, 720);
    plan.steps[1] = event_step(EventKind::Motion, "room", 10, 720);
    Authorization auth;
    HubScenarioSimulator first;
    require(first.begin(plan, authorize_test_home, &auth), "first repeat run begins", checks);
    finish(first, checks);
    HubScenarioSimulator second;
    require(second.begin(plan, authorize_test_home, &auth), "second repeat run begins", checks);
    finish(second, checks);
    require(first.result().events[0].key.str() == second.result().events[0].key.str() &&
            first.result().events[1].occurred_at == second.result().events[1].occurred_at &&
            first.result().decision_count == second.result().decision_count,
            "same plan, run identifier and virtual clock reproduce the same output", checks);

    require(second.begin(plan, authorize_test_home, &auth), "cancellable run begins", checks);
    (void)second.advance();
    second.cancel();
    require(second.result().status == RunStatus::Cancelled &&
            second.result().event_count == 1 && !second.active(),
            "cancellation stops the bounded scenario before its next step", checks);
}

}  // namespace

int main() {
    unsigned checks = 0;
    test_morning_sequence(checks);
    test_night_and_door_rules(checks);
    test_inactivity_coverage_and_time(checks);
    test_deterministic_morning_routine(checks);
    test_authorization_bounds_and_duplicates(checks);
    test_cancel_and_repeatability(checks);
    std::cout << "HUB SCENARIO SIMULATOR PASS checks=" << checks
              << " events=TEST_ONLY downstream=NOT_RUN\n";
    return 0;
}
