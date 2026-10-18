#include "firmware/hub/simulation/hub_runtime_scenario_bridge.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {
using namespace gs;
using namespace gs::hub;
using namespace gs::hub::simulation;

struct Authorization {
    bool allowed{true};
};

bool authorize_test_home(void* context, const std::string& home_id,
                         std::uint64_t session) {
    const auto& auth = *static_cast<Authorization*>(context);
    return auth.allowed && home_id.rfind("test-home-", 0) == 0 && session == 7001;
}

void require(bool condition, const char* message, unsigned& checks) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL " << message << '\n';
        std::exit(1);
    }
}

ScenarioPlan plan(const char* scenario_id, std::size_t steps = 1) {
    ScenarioPlan value;
    value.scenario_id = scenario_id;
    value.home_id = "test-home-runtime-bridge";
    value.run_id = 83001;
    value.authenticated_session = 7001;
    value.configuration_version = 1;
    value.virtual_start_epoch = 1'800'000'000;
    value.step_count = steps;
    for (std::size_t i = 0; i < steps; ++i) {
        value.steps[i].kind = StepKind::Event;
        value.steps[i].event_kind = EventKind::Motion;
        value.steps[i].location = "room1";
        value.steps[i].offset_seconds = static_cast<std::uint32_t>(i * 10U);
        value.steps[i].local_minute = 720;
        value.steps[i].event_sequence = steps > 1 ? 1U : 0U;
    }
    return value;
}

void test_shared_runtime_processing(unsigned& checks) {
    HubRuntime runtime(16, 32);
    Authorization auth;
    HubRuntimeScenarioBridge bridge;
    const auto scenario = plan("runtime-admission-and-reducer-v1");
    require(bridge.begin(runtime, scenario, authorize_test_home, &auth),
            "authorized TEST_ONLY scenario binds to the isolated HubRuntime", checks);
    require(bridge.advance() == RunStatus::Completed,
            "one scenario step is processed by the HubRuntime owner", checks);
    const auto& result = bridge.result();
    require(result.event_count == 1 && result.events[0].is_test &&
            result.events[0].sensor_type == SensorType::System &&
            result.events[0].key.source_id == "hub-sim-test" &&
            result.events[0].key.physical_device_id.empty(),
            "runtime receives explicit synthetic provenance without a physical Node identity", checks);
    require(result.stages[2].evidence == EvidenceState::Observed &&
            result.stages[3].evidence == EvidenceState::NotRun &&
            result.stages[4].evidence == EvidenceState::NotRun,
            "actual runtime admission is observed while volatile journal is not called durable", checks);
    require(runtime.journal().size() == 1,
            "existing HubRuntime journal records the admitted synthetic event", checks);
    require(!runtime.journal().persistent(),
            "host runtime journal is correctly identified as volatile", checks);
    require(runtime.activity_state().last_activity_event_id.empty(),
            "HubRuntime keeps TEST_ONLY motion out of resident activity state", checks);
}

void test_duplicate_and_revocation(unsigned& checks) {
    HubRuntime runtime(16, 32);
    Authorization auth;
    HubRuntimeScenarioBridge bridge;
    auto scenario = plan("runtime-duplicate-v1", 2);
    scenario.steps[1].offset_seconds = 0;
    require(bridge.begin(runtime, scenario, authorize_test_home, &auth),
            "duplicate TEST_ONLY run begins", checks);
    require(bridge.advance() == RunStatus::Running,
            "first generated event is processed by HubRuntime", checks);
    require(bridge.advance() == RunStatus::Completed,
            "repeated synthetic key reaches the HubRuntime duplicate boundary", checks);
    require(runtime.journal().size() == 1 && bridge.result().event_count == 2 &&
            bridge.result().events[0].key.str() == bridge.result().events[1].key.str(),
            "HubRuntime keeps one event effect for the repeated synthetic key", checks);

    HubRuntime revoked_runtime(16, 32);
    HubRuntimeScenarioBridge revoked_bridge;
    auto revoke_scenario = plan("runtime-revoke-v1", 2);
    revoke_scenario.steps[1].event_sequence = 2;
    require(revoked_bridge.begin(revoked_runtime, revoke_scenario,
                                 authorize_test_home, &auth),
            "revocation run begins under authorized session", checks);
    require(revoked_bridge.advance() == RunStatus::Running,
            "first event is accepted before revocation", checks);
    auth.allowed = false;
    require(revoked_bridge.advance() == RunStatus::AuthorizationExpired &&
            revoked_runtime.journal().size() == 1,
            "revoked TEST_ONLY session stops the next runtime event", checks);
    auth.allowed = true;
    DomainEvent stale;
    stale.key = {"hub-sim-test", revoke_scenario.run_id, 99};
    stale.kind = EventKind::Motion;
    stale.is_test = true;
    stale.sensor_type = SensorType::System;
    require(!revoked_runtime.radio_callback(stale),
            "terminal simulation revokes its temporary HubRuntime peer", checks);
}

}  // namespace

int main() {
    unsigned checks = 0;
    test_shared_runtime_processing(checks);
    test_duplicate_and_revocation(checks);
    std::cout << "HUB SCENARIO RUNTIME BRIDGE PASS checks=" << checks
              << " events=TEST_ONLY durable=NOT_RUN\n";
    return 0;
}
