#pragma once

#include "gs/domain.hpp"
#include "gs/rules.hpp"
#include "routines/routine_service.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

// This engine is compiled into firmware only by an explicitly selected
// TEST_ONLY profile. The ordinary product build keeps the control path inert.
#ifndef GS_HUB_SCENARIO_SIMULATOR_TEST_ONLY
#define GS_HUB_SCENARIO_SIMULATOR_TEST_ONLY 0
#endif

namespace gs::hub::simulation {

constexpr std::size_t kMaxScenarioSteps = 16;
constexpr std::size_t kMaxScenarioEvents = kMaxScenarioSteps;
constexpr std::size_t kMaxScenarioDecisions = 16;
constexpr std::uint32_t kMaxScenarioDurationSeconds = 24U * 60U * 60U;

enum class StepKind : std::uint8_t { Event, EvaluateActivityTimers };

struct ScenarioStep {
    StepKind kind{StepKind::Event};
    EventKind event_kind{EventKind::Motion};
    std::string location;
    // Time is relative to this run's isolated virtual clock. It never changes
    // ESP-IDF/system trusted time and is carried only by TEST_ONLY events.
    std::uint32_t offset_seconds{0};
    std::uint16_t local_minute{0};
    // Zero allocates the next deterministic Hub-simulation sequence. A
    // repeated nonzero value is available for duplicate/replay scenarios.
    std::uint64_t event_sequence{0};
};

struct ScenarioPlan {
    std::string scenario_id;
    std::string home_id;
    std::uint64_t run_id{0};
    std::uint64_t authenticated_session{0};
    std::uint32_t configuration_version{0};
    std::uint32_t deterministic_seed{0};
    EpochSeconds virtual_start_epoch{0};
    HomeMode mode{HomeMode::Home};
    CoverageState coverage{CoverageState::Covered};
    bool virtual_clock_trusted{true};
    // Routine evaluation is opt-in per scenario; the engine does not infer a
    // morning window or resident model from unrelated event scenarios.
    bool evaluate_morning_routine{false};
    RoutineConfig morning_routine{};
    ActivityRuleConfig rules{};
    std::array<ScenarioStep, kMaxScenarioSteps> steps{};
    std::size_t step_count{0};
};

// The caller must bind this verifier to the authenticated, currently active
// administrator session and current TEST_ONLY Home membership. It is called
// at run start and before every step, so revocation stops an in-flight run.
using TestHomeAuthorizationCheck = bool (*)(void* context,
                                             const std::string& home_id,
                                             std::uint64_t authenticated_session);

enum class RunStatus : std::uint8_t {
    Idle,
    Running,
    Completed,
    Cancelled,
    Disabled,
    Rejected,
    AuthorizationExpired
};

enum class EvidenceState : std::uint8_t { Observed, NotRun };
enum class TraceStage : std::uint8_t {
    HubSimulationSource,
    SharedRulesCore,
    HubRuntimeAdmission,
    DurableHubCommit,
    CloudSync,
    BackendCommit,
    CaregiverProjection
};

struct TraceStageResult {
    TraceStage stage{TraceStage::HubSimulationSource};
    EvidenceState evidence{EvidenceState::NotRun};
};

// Optional TEST_ONLY handoff from the scenario source into a caller-owned
// HubRuntime adapter. A receipt is accepted only for the exact generated key;
// durable completion remains unobserved unless the adapter confirms a
// persistent journal and the actual HubRuntime result.
struct HubRuntimeEventReceipt {
    EventKey event_key{};
    bool admission_accepted{false};
    bool processing_observed{false};
    bool durable_commit_observed{false};
    std::array<RuleSignalDecision, kMaxScenarioDecisions> activity_decisions{};
    std::size_t activity_decision_count{0};
};

using TestOnlyEventProcessor = bool (*)(void* context,
                                        const DomainEvent& event,
                                        std::uint16_t local_minute,
                                        HubRuntimeEventReceipt& receipt);

struct ObservedDecision {
    std::size_t step_index{0};
    RuleSignalDecision decision{};
};

struct ObservedIncidentDecision {
    std::size_t step_index{0};
    IncidentDecision decision{};
};

struct ObservedRuntimeDecision {
    std::size_t step_index{0};
    RuleSignalDecision decision{};
};

struct ScenarioRunResult {
    RunStatus status{RunStatus::Idle};
    std::string scenario_id;
    std::string home_id;
    std::uint64_t run_id{0};
    std::uint32_t configuration_version{0};
    std::uint32_t deterministic_seed{0};
    std::string runtime_failure_reason;
    std::array<DomainEvent, kMaxScenarioEvents> events{};
    std::size_t event_count{0};
    std::array<ObservedDecision, kMaxScenarioDecisions> decisions{};
    std::size_t decision_count{0};
    std::array<ObservedIncidentDecision, kMaxScenarioDecisions> routine_decisions{};
    std::size_t routine_decision_count{0};
    std::array<ObservedRuntimeDecision, kMaxScenarioDecisions> runtime_activity_decisions{};
    std::size_t runtime_activity_decision_count{0};
    RoutineState routine_state{};
    std::array<TraceStageResult, 7> stages{};
};

class HubScenarioSimulator {
public:
    bool begin(const ScenarioPlan& plan, TestHomeAuthorizationCheck authorize,
               void* authorization_context,
               TestOnlyEventProcessor test_event_processor = nullptr,
               void* event_processor_context = nullptr);
    // Executes exactly one bounded event/rule/timer step. The caller schedules
    // repeated calls on the Hub owner task; no worker or unbounded loop is made.
    RunStatus advance();
    void cancel();
    const ScenarioRunResult& result() const { return result_; }
    bool active() const { return result_.status == RunStatus::Running; }

private:
    bool valid_plan(const ScenarioPlan& plan) const;
    bool still_authorized() const;
    void record_decisions(std::size_t step_index,
                          const std::vector<RuleSignalDecision>& decisions);
    void record_routine_decision(std::size_t step_index,
                                 const IncidentDecision& decision);

    ScenarioPlan plan_{};
    TestHomeAuthorizationCheck authorize_{nullptr};
    void* authorization_context_{nullptr};
    TestOnlyEventProcessor test_event_processor_{nullptr};
    void* event_processor_context_{nullptr};
    std::size_t next_step_{0};
    ActivityRuleState activity_state_{};
    gs::hub::RoutineService routine_service_{};
    ScenarioRunResult result_{};
};

const char* run_status_name(RunStatus status);
const char* trace_stage_name(TraceStage stage);

}  // namespace gs::hub::simulation
