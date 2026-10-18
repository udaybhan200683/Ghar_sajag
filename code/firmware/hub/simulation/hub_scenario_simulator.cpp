#include "hub_scenario_simulator.hpp"

#include <algorithm>
#include <limits>

namespace gs::hub::simulation {
namespace {
constexpr const char* kSyntheticHubSource = "hub-sim-test";
constexpr char kTestHomePrefix[] = "test-home-";
constexpr std::size_t kMaxScenarioIdBytes = 48;
constexpr std::size_t kMaxHomeIdBytes = 64;
constexpr std::size_t kMaxLocationBytes = 24;
constexpr std::size_t kMaxRoutineLocations = 8;

bool allowed_event_kind(EventKind kind) {
    switch (kind) {
        case EventKind::Motion:
        case EventKind::DoorOpen:
        case EventKind::DoorClosed:
        case EventKind::OkPressed:
        case EventKind::CallFamily:
        case EventKind::Heartbeat:
            return true;
        case EventKind::PrivacyOn:
        case EventKind::PrivacyOff:
        case EventKind::Gap:
        case EventKind::MotionSummary:
            return false;
    }
    return false;
}

#if GS_HUB_SCENARIO_SIMULATOR_TEST_ONLY
TraceStageResult stage(TraceStage name, EvidenceState state) {
    return {name, state};
}
#endif
}  // namespace

bool HubScenarioSimulator::valid_plan(const ScenarioPlan& plan) const {
    if (plan.scenario_id.empty() || plan.scenario_id.size() > kMaxScenarioIdBytes ||
        plan.home_id.size() <= sizeof(kTestHomePrefix) - 1U ||
        plan.home_id.size() > kMaxHomeIdBytes ||
        plan.home_id.compare(0, sizeof(kTestHomePrefix) - 1U, kTestHomePrefix) != 0 ||
        plan.run_id == 0 || plan.authenticated_session == 0 ||
        plan.configuration_version == 0 || plan.virtual_start_epoch <= 0 ||
        plan.step_count == 0 || plan.step_count > kMaxScenarioSteps)
        return false;

    const auto& routine = plan.morning_routine;
    if (routine.window_id.size() > kMaxScenarioIdBytes ||
        routine.qualifying_locations.size() > kMaxRoutineLocations)
        return false;
    for (const auto& location : routine.qualifying_locations) {
        if (location.empty() || location.size() > kMaxLocationBytes) return false;
    }
    if (plan.evaluate_morning_routine) {
        if (routine.window_id.empty() ||
            routine.start_at < plan.virtual_start_epoch ||
            routine.end_at < routine.start_at || routine.grace_end_at < routine.end_at ||
            routine.grace_end_at - plan.virtual_start_epoch >
                static_cast<EpochSeconds>(kMaxScenarioDurationSeconds))
            return false;
    }

    for (std::size_t i = 0; i < plan.step_count; ++i) {
        const auto& step = plan.steps[i];
        if (step.offset_seconds > kMaxScenarioDurationSeconds ||
            step.local_minute >= 24U * 60U ||
            plan.virtual_start_epoch > std::numeric_limits<EpochSeconds>::max() -
                static_cast<EpochSeconds>(step.offset_seconds))
            return false;
        if (step.kind == StepKind::Event) {
            if (!allowed_event_kind(step.event_kind) ||
                step.location.size() > kMaxLocationBytes)
                return false;
        } else if (step.kind != StepKind::EvaluateActivityTimers) {
            return false;
        }
        if (step.event_sequence == std::numeric_limits<std::uint64_t>::max())
            return false;
    }
    return true;
}

bool HubScenarioSimulator::still_authorized() const {
    return authorize_ != nullptr && authorize_(authorization_context_, plan_.home_id,
                                                plan_.authenticated_session);
}

bool HubScenarioSimulator::begin(const ScenarioPlan& plan,
                                 TestHomeAuthorizationCheck authorize,
                                 void* authorization_context,
                                 TestOnlyEventProcessor test_event_processor,
                                 void* event_processor_context) {
    cancel();
    result_ = {};
#if !GS_HUB_SCENARIO_SIMULATOR_TEST_ONLY
    (void)plan;
    (void)authorize;
    (void)authorization_context;
    (void)test_event_processor;
    (void)event_processor_context;
    result_.status = RunStatus::Disabled;
    return false;
#else
    if (!valid_plan(plan) || authorize == nullptr) {
        result_.status = RunStatus::Rejected;
        return false;
    }
    plan_ = plan;
    authorize_ = authorize;
    authorization_context_ = authorization_context;
    test_event_processor_ = test_event_processor;
    event_processor_context_ = event_processor_context;
    next_step_ = 0;
    activity_state_ = {};
    if (plan.evaluate_morning_routine) {
        routine_service_.start_window(plan.morning_routine, plan.mode);
        routine_service_.set_coverage(plan.coverage);
        result_.routine_state = routine_service_.state();
    }
    result_.scenario_id = plan.scenario_id;
    result_.home_id = plan.home_id;
    result_.run_id = plan.run_id;
    result_.configuration_version = plan.configuration_version;
    result_.deterministic_seed = plan.deterministic_seed;
    result_.stages = {{
        stage(TraceStage::HubSimulationSource, EvidenceState::Observed),
        stage(TraceStage::SharedRulesCore, EvidenceState::NotRun),
        stage(TraceStage::HubRuntimeAdmission, EvidenceState::NotRun),
        stage(TraceStage::DurableHubCommit, EvidenceState::NotRun),
        stage(TraceStage::CloudSync, EvidenceState::NotRun),
        stage(TraceStage::BackendCommit, EvidenceState::NotRun),
        stage(TraceStage::CaregiverProjection, EvidenceState::NotRun)}};
    if (!still_authorized()) {
        result_.status = RunStatus::Rejected;
        return false;
    }
    RulesCore::start_activity_monitor(activity_state_, plan.virtual_start_epoch);
    result_.status = RunStatus::Running;
    return true;
#endif
}

void HubScenarioSimulator::record_decisions(
    std::size_t step_index, const std::vector<RuleSignalDecision>& decisions) {
    for (const auto& decision : decisions) {
        if (result_.decision_count >= result_.decisions.size()) {
            result_.status = RunStatus::Rejected;
            return;
        }
        result_.decisions[result_.decision_count++] = {step_index, decision};
    }
}

void HubScenarioSimulator::record_routine_decision(
    std::size_t step_index, const IncidentDecision& decision) {
    if (result_.routine_decision_count >= result_.routine_decisions.size()) {
        result_.status = RunStatus::Rejected;
        return;
    }
    result_.routine_decisions[result_.routine_decision_count++] = {step_index, decision};
    result_.routine_state = routine_service_.state();
}

RunStatus HubScenarioSimulator::advance() {
    if (result_.status != RunStatus::Running) return result_.status;
    if (!still_authorized()) {
        result_.status = RunStatus::AuthorizationExpired;
        return result_.status;
    }
    if (next_step_ >= plan_.step_count) {
        result_.status = RunStatus::Completed;
        return result_.status;
    }

    const auto index = next_step_++;
    const auto& step = plan_.steps[index];
    const auto occurred_at = plan_.virtual_start_epoch + step.offset_seconds;
    const auto monotonic_ms = static_cast<Milliseconds>(step.offset_seconds) * 1000;
    const RuleEvaluationContext context{plan_.mode, plan_.coverage,
                                        plan_.virtual_clock_trusted};
    if (step.kind == StepKind::Event) {
        if (result_.event_count >= result_.events.size()) {
            result_.status = RunStatus::Rejected;
            return result_.status;
        }
        const auto sequence = step.event_sequence == 0
            ? static_cast<std::uint64_t>(index + 1U) : step.event_sequence;
        DomainEvent event;
        event.key = EventKey{kSyntheticHubSource, plan_.run_id, sequence};
        event.kind = step.event_kind;
        event.location = step.location;
        event.monotonic_ms = monotonic_ms;
        event.occurred_at = occurred_at;
        event.received_at = occurred_at;
        event.is_test = true;
        // A Hub-generated test event is a system simulation observation. It
        // never claims a physical PIR, Reed, C3 identity, RSSI, or battery.
        event.sensor_type = SensorType::System;
        result_.events[result_.event_count++] = event;

        if (test_event_processor_ != nullptr) {
            HubRuntimeEventReceipt receipt;
            const bool processed = test_event_processor_(event_processor_context_, event,
                                                          step.local_minute, receipt);
            if (!processed || receipt.event_key.str() != event.key.str() ||
                !receipt.admission_accepted || !receipt.processing_observed) {
                result_.runtime_failure_reason = "hub_runtime_test_event_rejected";
                result_.status = RunStatus::Rejected;
                return result_.status;
            }
            result_.stages[2].evidence = EvidenceState::Observed;
            if (receipt.durable_commit_observed)
                result_.stages[3].evidence = EvidenceState::Observed;
            if (receipt.activity_decision_count > receipt.activity_decisions.size() ||
                receipt.activity_decision_count > result_.runtime_activity_decisions.size() -
                    result_.runtime_activity_decision_count) {
                result_.runtime_failure_reason = "hub_runtime_decision_capacity_exceeded";
                result_.status = RunStatus::Rejected;
                return result_.status;
            }
            for (std::size_t i = 0; i < receipt.activity_decision_count; ++i) {
                result_.runtime_activity_decisions[result_.runtime_activity_decision_count++] = {
                    index, receipt.activity_decisions[i]};
            }
        }

        // Evaluate an ephemeral sandbox copy through the production
        // deterministic RulesCore. The TEST_ONLY event retained in the run
        // result remains marked synthetic and is never submitted or persisted
        // by this module. The real runtime continues to ignore is_test events.
        auto evaluation_event = event;
        evaluation_event.is_test = false;
        if (plan_.evaluate_morning_routine) {
            routine_service_.apply(evaluation_event);
            result_.routine_state = routine_service_.state();
        }
        const auto decisions = RulesCore::apply_activity_event(
            activity_state_, plan_.rules, evaluation_event, step.local_minute, context);
        record_decisions(index, decisions);
        if (result_.status == RunStatus::Rejected) return result_.status;
        result_.stages[1].evidence = EvidenceState::Observed;
    } else {
        if (plan_.evaluate_morning_routine) {
            const auto decision = routine_service_.deadline(occurred_at,
                                                             plan_.virtual_clock_trusted);
            record_routine_decision(index, decision);
            if (result_.status == RunStatus::Rejected) return result_.status;
        }
        const auto decisions = RulesCore::evaluate_activity_timers(
            activity_state_, plan_.rules, occurred_at, step.local_minute, context);
        record_decisions(index, decisions);
        if (result_.status == RunStatus::Rejected) return result_.status;
        result_.stages[1].evidence = EvidenceState::Observed;
    }

    if (next_step_ == plan_.step_count) result_.status = RunStatus::Completed;
    return result_.status;
}

void HubScenarioSimulator::cancel() {
    if (result_.status == RunStatus::Running) result_.status = RunStatus::Cancelled;
    authorize_ = nullptr;
    authorization_context_ = nullptr;
    test_event_processor_ = nullptr;
    event_processor_context_ = nullptr;
}

const char* run_status_name(RunStatus status) {
    switch (status) {
        case RunStatus::Idle: return "IDLE";
        case RunStatus::Running: return "RUNNING";
        case RunStatus::Completed: return "COMPLETED";
        case RunStatus::Cancelled: return "CANCELLED";
        case RunStatus::Disabled: return "DISABLED";
        case RunStatus::Rejected: return "REJECTED";
        case RunStatus::AuthorizationExpired: return "AUTHORIZATION_EXPIRED";
    }
    return "UNKNOWN";
}

const char* trace_stage_name(TraceStage stage) {
    switch (stage) {
        case TraceStage::HubSimulationSource: return "HUB_SIMULATION_SOURCE";
        case TraceStage::SharedRulesCore: return "SHARED_RULES_CORE";
        case TraceStage::HubRuntimeAdmission: return "HUB_RUNTIME_ADMISSION";
        case TraceStage::DurableHubCommit: return "DURABLE_HUB_COMMIT";
        case TraceStage::CloudSync: return "CLOUDSYNC";
        case TraceStage::BackendCommit: return "BACKEND_COMMIT";
        case TraceStage::CaregiverProjection: return "CAREGIVER_PROJECTION";
    }
    return "UNKNOWN";
}

}  // namespace gs::hub::simulation
