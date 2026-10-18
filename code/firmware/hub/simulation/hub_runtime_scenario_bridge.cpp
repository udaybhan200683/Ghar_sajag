#include "hub_runtime_scenario_bridge.hpp"

namespace gs::hub::simulation {
namespace {
constexpr const char* kSyntheticHubSource = "hub-sim-test";
}

bool HubRuntimeScenarioBridge::begin(HubRuntime& runtime,
                                     const ScenarioPlan& plan,
                                     TestHomeAuthorizationCheck authorize,
                                     void* authorization_context) {
    cancel();
    if (!runtime.durable_admission_open() || authorize == nullptr ||
        !authorize(authorization_context, plan.home_id, plan.authenticated_session))
        return false;

    runtime_ = &runtime;
    authorize_ = authorize;
    authorization_context_ = authorization_context;
    home_id_ = plan.home_id;
    session_id_ = plan.authenticated_session;
    runtime_run_id_ = plan.run_id;

    if (!simulator_.begin(plan, authorize, authorization_context,
                          &HubRuntimeScenarioBridge::process_test_event, this)) {
        runtime_ = nullptr;
        authorize_ = nullptr;
        authorization_context_ = nullptr;
        home_id_.clear();
        session_id_ = 0;
        runtime_run_id_ = 0;
        return false;
    }

    // This virtual peer is bound only to the already-authorized TEST_ONLY run.
    // It has no physical Node identity and cannot enter the authenticated radio
    // callback. The source remains distinct and is revoked after the run.
    runtime.authorize_node(kSyntheticHubSource, plan.run_id, false);
    runtime.set_mode(plan.mode);
    runtime.configure_activity_rules(plan.rules);
    runtime.start_activity_monitor(plan.virtual_start_epoch);
    if (plan.evaluate_morning_routine)
        runtime.start_window(plan.morning_routine, plan.mode);
    active_ = true;
    return true;
}

RunStatus HubRuntimeScenarioBridge::advance() {
    const auto status = simulator_.advance();
    if (status != RunStatus::Running) {
        revoke_simulation_peer();
        active_ = false;
    }
    return status;
}

void HubRuntimeScenarioBridge::cancel() {
    simulator_.cancel();
    revoke_simulation_peer();
    active_ = false;
}

void HubRuntimeScenarioBridge::revoke_simulation_peer() {
    if (runtime_ != nullptr) runtime_->revoke_node(kSyntheticHubSource);
    runtime_ = nullptr;
    authorize_ = nullptr;
    authorization_context_ = nullptr;
    home_id_.clear();
    session_id_ = 0;
    runtime_run_id_ = 0;
}

bool HubRuntimeScenarioBridge::process_test_event(
    void* context, const DomainEvent& event, std::uint16_t local_minute,
    HubRuntimeEventReceipt& receipt) {
    if (context == nullptr) return false;
    return static_cast<HubRuntimeScenarioBridge*>(context)->process(
        event, local_minute, receipt);
}

bool HubRuntimeScenarioBridge::process(const DomainEvent& event,
                                      std::uint16_t local_minute,
                                      HubRuntimeEventReceipt& receipt) {
#if !GS_HUB_SCENARIO_SIMULATOR_TEST_ONLY
    (void)event;
    (void)local_minute;
    (void)receipt;
    return false;
#else
    if (!active_ || runtime_ == nullptr || authorize_ == nullptr ||
        event.key.source_id != kSyntheticHubSource || event.key.session_id == 0 ||
        event.key.session_id != runtime_run_id_ || !event.is_test ||
        event.sensor_type != SensorType::System ||
        !event.key.physical_device_id.empty() ||
        !authorize_(authorization_context_, home_id_, session_id_))
        return false;

    if (!runtime_->radio_callback(event)) return false;
    const auto processed = runtime_->run_state_once(local_minute);
    if (!processed || processed->key.str() != event.key.str() ||
        processed->ack == AckClass::Rejected ||
        processed->rule_signals.size() > receipt.activity_decisions.size())
        return false;

    receipt = {};
    receipt.event_key = event.key;
    receipt.admission_accepted = true;
    receipt.processing_observed = true;
    receipt.durable_commit_observed = runtime_->journal().persistent() &&
        processed->ack == AckClass::Durable && runtime_->journal().contains(event.key);
    receipt.activity_decision_count = processed->rule_signals.size();
    for (std::size_t i = 0; i < receipt.activity_decision_count; ++i)
        receipt.activity_decisions[i] = processed->rule_signals[i];
    return true;
#endif
}

}  // namespace gs::hub::simulation
