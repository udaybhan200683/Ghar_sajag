#include "firmware/hub/simulation/hub_scenario_simulator.hpp"

#include <iostream>

int main() {
    gs::hub::simulation::HubScenarioSimulator simulator;
    gs::hub::simulation::ScenarioPlan plan;
    if (simulator.begin(plan, nullptr, nullptr) ||
        simulator.result().status != gs::hub::simulation::RunStatus::Disabled) {
        std::cerr << "FAIL scenario simulator must be disabled in the default build\n";
        return 1;
    }
    std::cout << "HUB SCENARIO SIMULATOR DEFAULT-OFF PASS checks=1\n";
    return 0;
}
