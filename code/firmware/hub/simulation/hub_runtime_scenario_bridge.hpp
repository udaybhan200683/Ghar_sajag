#pragma once

#include "hub_scenario_simulator.hpp"
#include "runtime/hub_runtime.hpp"

namespace gs::hub::simulation {

// TEST_ONLY bridge that submits generated events to the existing HubRuntime
// owner. It is inert unless the scenario simulator is explicitly compiled on.
// The caller must provide the same authenticated TEST_ONLY Home/session check
// used by the scenario control boundary and must pass the isolated Home's
// HubRuntime instance.
class HubRuntimeScenarioBridge {
public:
    bool begin(HubRuntime& runtime, const ScenarioPlan& plan,
               TestHomeAuthorizationCheck authorize, void* authorization_context);
    RunStatus advance();
    void cancel();
    bool active() const { return active_; }
    const ScenarioRunResult& result() const { return simulator_.result(); }

private:
    static bool process_test_event(void* context, const DomainEvent& event,
                                   std::uint16_t local_minute,
                                   HubRuntimeEventReceipt& receipt);
    bool process(const DomainEvent& event, std::uint16_t local_minute,
                 HubRuntimeEventReceipt& receipt);
    void revoke_simulation_peer();

    HubRuntime* runtime_{nullptr};
    HubScenarioSimulator simulator_{};
    TestHomeAuthorizationCheck authorize_{nullptr};
    void* authorization_context_{nullptr};
    std::string home_id_;
    std::uint64_t session_id_{0};
    std::uint64_t runtime_run_id_{0};
    bool active_{false};
};

}  // namespace gs::hub::simulation
