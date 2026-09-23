#include "host/multinode/scheduled_harness.hpp"

#include <iostream>
#include <set>
#include <stdexcept>
#include <string>

using gs::host::multinode::ScheduledHarness;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void qualify_count(std::size_t count) {
    ScheduledHarness harness(count, 1024);
    std::set<std::string> physical, logical, locations;
    std::vector<gs::EventKey> keys;
    for (std::size_t i = 0; i < count; ++i) {
        const auto snapshot = harness.snapshot(i);
        require(snapshot.commissioned, "Node lacked authenticated commissioning");
        physical.insert(snapshot.physical_id);
        logical.insert(snapshot.logical_id);
        locations.insert(snapshot.location);
        const auto key = harness.record(i);
        require(key.has_value(), "NodeRuntime did not retain an event");
        keys.push_back(*key);
    }
    require(physical.size() == count && logical.size() == count && locations.size() == count,
            "node identities or room attribution collided");
    harness.run_until_quiet();
    require(harness.journal_size() == count, "Hub journal count mismatch");
    for (std::size_t i = 0; i < count; ++i) {
        const auto snapshot = harness.snapshot(i);
        require(harness.contains(keys[i]), "wrong-node journal attribution");
        require(snapshot.matching_acks == 1 && snapshot.ack_mismatches == 0,
                "per-node ACK identity mismatch");
        require(snapshot.retained == 0 && snapshot.pending == 0,
                "per-node event did not drain");
        require(snapshot.next_sequence == 2 && snapshot.maximum_ack_latency_ms >= 2,
                "per-node sequence or transport timing mismatch");
    }
    std::cout << "P2-MN" << count << " HOST/SIMULATED PASS nodes=" << count
              << " journal=" << harness.journal_size() << '\n';
}

void lost_ack_retries_same_identity() {
    ScheduledHarness harness(4);
    harness.drop_next_ack(2);
    const auto key = harness.record(2);
    require(key.has_value(), "retry setup failed");
    harness.run_until_quiet(2000);
    const auto snapshot = harness.snapshot(2);
    require(snapshot.uplink_attempts >= 2 && snapshot.matching_acks == 1,
            "lost ACK did not cause matched retry");
    require(harness.journal_size() == 1 && harness.contains(*key),
            "retry duplicated or misattributed journal event");
    for (std::size_t i : {0U, 1U, 3U})
        require(harness.snapshot(i).matching_acks == 0, "cross-node ACK leakage");
    std::cout << "P2-MN-RETRY HOST/SIMULATED PASS\n";
}

void misrouted_ack_is_rejected() {
    ScheduledHarness harness(4);
    harness.redirect_next_ack(0, 1);
    const auto key = harness.record(0);
    require(key.has_value(), "misrouted ACK setup failed");
    harness.run_until_quiet(2000);
    require(harness.snapshot(0).matching_acks == 1 &&
            harness.snapshot(0).uplink_attempts >= 2 &&
            harness.snapshot(1).matching_acks == 0 &&
            harness.snapshot(1).ack_mismatches == 1 &&
            harness.journal_size() == 1 && harness.contains(*key),
            "wrong-node authenticated ACK leaked or blocked sender retry");
    std::cout << "P2-MN-ACK-ISOLATION HOST/SIMULATED PASS\n";
}

void outage_recovers() {
    ScheduledHarness harness(10);
    harness.set_hub_online(false);
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.record(i).has_value(), "outage record failed");
    harness.advance(1000);
    require(harness.journal_size() == 0, "Hub accepted traffic while offline");
    harness.set_hub_online(true);
    harness.run_until_quiet(5000);
    require(harness.journal_size() == 10, "recovery storm lost events");
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.snapshot(i).matching_acks == 1, "per-node recovery failed");
    std::cout << "P2-MN10-OUTAGE HOST/SIMULATED PASS\n";
}

void removal_isolated_from_other_nine() {
    ScheduledHarness harness(10);
    require(harness.remove_node(3) == gs::hub::RegistryResult::Accepted,
            "registry removal failed");
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.record(i).has_value(), "removal burst setup failed");
    harness.advance(500);
    require(harness.journal_size() == 9, "removed device entered journal or another node was lost");
    for (std::size_t i = 0; i < 10; ++i) {
        const auto snapshot = harness.snapshot(i);
        if (i == 3) {
            require(snapshot.matching_acks == 0 && snapshot.registry_rejections > 0 &&
                    snapshot.retained == 1, "removed device was admitted or lost its retained event");
        } else {
            require(snapshot.matching_acks == 1 && snapshot.registry_rejections == 0 &&
                    snapshot.retained == 0, "removal disturbed another node");
        }
    }
    std::cout << "P2-MN10-REMOVE HOST/SIMULATED PASS nine unaffected\n";
}

void one_of_ten_rejoins_without_repairing() {
    ScheduledHarness harness(10);
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.record(i).has_value(), "first ten-node burst failed");
    harness.run_until_quiet();
    require(harness.restart_node(4), "individual authenticated rejoin failed");
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.record(i).has_value(), "post-rejoin burst failed");
    harness.run_until_quiet();
    require(harness.journal_size() == 20, "rejoin lost or duplicated another Node event");
    for (std::size_t i = 0; i < 10; ++i) {
        const auto state = harness.snapshot(i);
        require(state.session == (i == 4 ? 2U : 1U) &&
                state.matching_acks == 2 && state.ack_mismatches == 0 &&
                state.registry_rejections == 0 && state.pending == 0,
                "one-Node rejoin contaminated another Node state");
    }
    std::cout << "P2-MN10-REJOIN HOST/SIMULATED PASS nine unaffected\n";
}
}  // namespace

int main() {
    try {
        for (std::size_t count : {1U, 4U, 10U, 25U}) qualify_count(count);
        lost_ack_retries_same_identity();
        misrouted_ack_is_rejected();
        outage_recovers();
        removal_isolated_from_other_nine();
        one_of_ten_rejoins_without_repairing();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-MULTINODE HOST/SIMULATED FAIL " << error.what() << '\n';
        return 1;
    }
}
