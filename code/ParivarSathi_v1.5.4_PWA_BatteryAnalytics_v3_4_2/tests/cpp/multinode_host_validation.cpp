#include "host/multinode/scheduled_harness.hpp"

#include <iostream>
#include <fstream>
#include <cstdio>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using gs::host::multinode::ScheduledHarness;

namespace {
struct CaseReport {
    std::string id;
    std::vector<gs::host::multinode::NodeSnapshot> nodes;
    std::size_t journal{0};
    std::size_t ingress_high_water{0};
    std::size_t ingress_rejected{0};
};
std::vector<CaseReport> reports;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void capture(const std::string& id, ScheduledHarness& harness) {
    CaseReport report;
    report.id = id;
    report.journal = harness.journal_size();
    report.ingress_high_water = harness.ingest_high_water();
    report.ingress_rejected = harness.ingest_rejected();
    for (std::size_t i = 0; i < harness.node_count(); ++i)
        report.nodes.push_back(harness.snapshot(i));
    reports.push_back(std::move(report));
}

void write_report() {
    require(reports.size() == 13, "multi-node case manifest was not fully executed");
    std::ofstream out("build/multinode_host_summary.json", std::ios::trunc);
    require(out.good(), "could not create multi-node per-node evidence");
    out << "{\n  \"classification\": \"HOST/SIMULATED\",\n"
        << "  \"expected_cases\": 13, \"executed_cases\": 13, \"passed_cases\": 13,\n"
        << "  \"cases\": [\n";
    for (std::size_t i = 0; i < reports.size(); ++i) {
        const auto& report = reports[i];
        if (i) out << ",\n";
        out << "    {\"id\": \"" << report.id << "\", \"status\": \"PASS\", "
            << "\"expected_nodes\": " << report.nodes.size()
            << ", \"executed_nodes\": " << report.nodes.size()
            << ", \"passed_nodes\": " << report.nodes.size()
            << ", \"journal\": " << report.journal
            << ", \"ingress_high_water\": " << report.ingress_high_water
            << ", \"ingress_rejected\": " << report.ingress_rejected
            << ", \"nodes\": [";
        for (std::size_t n = 0; n < report.nodes.size(); ++n) {
            const auto& node = report.nodes[n];
            if (n) out << ',';
            // These identifiers are generated from fixed ASCII host test
            // prefixes and numeric indexes, so no JSON escaping is needed.
            out << "{\"status\":\"PASS\",\"physical_id\":\"" << node.physical_id
                << "\",\"logical_id\":\"" << node.logical_id
                << "\",\"room\":\"" << node.location
                << "\",\"session\":" << node.session
                << ",\"next_sequence\":" << node.next_sequence
                << ",\"retained\":" << node.retained
                << ",\"pending\":" << node.pending
                << ",\"uplink_attempts\":" << node.uplink_attempts
                << ",\"hub_admissions\":" << node.hub_admissions
                << ",\"matching_acks\":" << node.matching_acks
                << ",\"ack_mismatches\":" << node.ack_mismatches
                << ",\"stale_acks\":" << node.stale_acks
                << ",\"registry_rejections\":" << node.registry_rejections
                << ",\"ingress_rejections\":" << node.ingress_rejections
                << ",\"application_rejections\":" << node.application_rejections
                << ",\"volatile_receipts\":" << node.volatile_receipts
                << ",\"maximum_ack_latency_ms\":" << node.maximum_ack_latency_ms
                << ",\"commissioned\":" << (node.commissioned ? "true" : "false")
                << '}';
        }
        out << "]}";
    }
    out << "\n  ]\n}\n";
    require(out.good(), "multi-node per-node evidence write failed");
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
    capture(count == 1 ? "P2-MN01" : count == 4 ? "P2-MN04" :
            count == 10 ? "P2-MN10" : "P2-MN25", harness);
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
    capture("P2-MN04-RETRY", harness);
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
    capture("P2-MN04-ACK-ISOLATION", harness);
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
    capture("P2-MN10-OUTAGE", harness);
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
    capture("P2-MN10-REMOVE", harness);
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
    capture("P2-MN10-REJOIN", harness);
    std::cout << "P2-MN10-REJOIN HOST/SIMULATED PASS nine unaffected\n";
}

void one_of_ten_restarts_with_inflight_event() {
    ScheduledHarness harness(10);
    std::vector<gs::EventKey> old_keys;
    for (std::size_t i = 0; i < 10; ++i) {
        const auto key = harness.record(i);
        require(key.has_value(), "in-flight reboot burst setup failed");
        old_keys.push_back(*key);
    }
    harness.advance(0);  // Encrypted uplinks exist but no Hub delivery yet.
    require(harness.restart_node(4), "pending event blocked authenticated rejoin");
    harness.run_until_quiet(5000);
    require(harness.journal_size() == 10 && harness.contains(old_keys[4]),
            "restarted Node lost or rewrote its original event identity");
    for (std::size_t i = 0; i < 10; ++i) {
        const auto state = harness.snapshot(i);
        require(state.matching_acks == 1 && state.pending == 0 && state.retained == 0 &&
                state.session == (i == 4 ? 2U : 1U),
                "in-flight restart disturbed another Node or stranded evidence");
    }
    require(harness.snapshot(4).registry_rejections >= 1,
            "old-session encrypted frame was not rejected after rejoin");
    const auto fresh = harness.record(4);
    require(fresh && fresh->session_id == 2 && fresh->sequence == 1,
            "new event reused the prior boot event identity");
    harness.run_until_quiet();
    require(harness.journal_size() == 11 && harness.contains(*fresh),
            "new-session event failed after recovery");
    capture("P2-MN10-INFLIGHT-REJOIN", harness);
    std::cout << "P2-MN10-INFLIGHT-REJOIN HOST/SIMULATED PASS old event identity retained\n";
}

void ten_node_ingress_pressure_recovers() {
    ScheduledHarness harness(10);
    harness.set_hub_processing_budget(0);
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.record(i).has_value(), "ingress pressure setup failed");
    harness.advance(3000);
    require(harness.ingest_depth() == 32 && harness.ingest_high_water() == 32 &&
            harness.ingest_rejected() > 0 && harness.journal_size() == 0,
            "bounded Hub ingress did not reject excess authenticated traffic");
    harness.set_hub_processing_budget(32);
    harness.run_until_quiet(5000);
    require(harness.ingest_depth() == 0 && harness.journal_size() == 10,
            "queue recovery lost or duplicated business events");
    std::uint64_t rejected_sum = 0;
    for (std::size_t i = 0; i < 10; ++i) {
        const auto state = harness.snapshot(i);
        require(state.matching_acks == 1 && state.ack_mismatches == 0 &&
                state.pending == 0 && state.retained == 0,
                "queue pressure starved or contaminated one Node");
        rejected_sum += state.ingress_rejections;
    }
    require(rejected_sum == harness.ingest_rejected(),
            "per-node ingress rejection accounting differs from Hub total");
    capture("P2-MN10-INGRESS-FULL", harness);
    std::cout << "P2-MN10-INGRESS-FULL HOST/SIMULATED PASS bound=32\n";
}

void ten_node_journal_full_is_explicit() {
    ScheduledHarness harness(10, 8);
    for (std::size_t i = 0; i < 10; ++i)
        require(harness.record(i).has_value(), "journal pressure setup failed");
    harness.advance(5);
    require(harness.journal_size() == 8, "Hub journal exceeded configured capacity");
    for (std::size_t i = 0; i < 10; ++i) {
        const auto state = harness.snapshot(i);
        if (i < 8) {
            require(state.matching_acks == 1 && state.retained == 0,
                    "accepted journal event failed to retire at Node");
        } else {
            require(state.application_rejections == 1 && state.matching_acks == 0 &&
                    state.retained == 1 && state.pending == 1,
                    "journal-full rejection silently retired retained evidence");
        }
    }
    capture("P2-MN10-JOURNAL-FULL", harness);
    std::cout << "P2-MN10-JOURNAL-FULL HOST/SIMULATED PASS bound=8\n";
}

void noisy_node_does_not_starve_quiet_nodes() {
    ScheduledHarness harness(10);
    for (unsigned i = 0; i < 20; ++i)
        require(harness.record(0).has_value(), "noisy Node setup failed");
    for (std::size_t i = 1; i < 10; ++i)
        require(harness.record(i).has_value(), "quiet Node setup failed");
    harness.run_until_quiet(20000);
    require(harness.journal_size() == 29, "noisy/quiet event accounting failed");
    require(harness.snapshot(0).matching_acks == 20,
            "noisy Node evidence did not drain");
    for (std::size_t i = 1; i < 10; ++i) {
        const auto state = harness.snapshot(i);
        require(state.matching_acks == 1 && state.maximum_ack_latency_ms < 100 &&
                state.pending == 0 && state.ack_mismatches == 0,
                "quiet Node starved or received wrong ACK");
    }
    capture("P2-MN10-FAIRNESS", harness);
    std::cout << "P2-MN10-FAIRNESS HOST/SIMULATED PASS noisy=20 quiet=9\n";
}
}  // namespace

int main() {
    try {
        (void)std::remove("build/multinode_host_summary.json");
        for (std::size_t count : {1U, 4U, 10U, 25U}) qualify_count(count);
        lost_ack_retries_same_identity();
        misrouted_ack_is_rejected();
        outage_recovers();
        removal_isolated_from_other_nine();
        one_of_ten_rejoins_without_repairing();
        one_of_ten_restarts_with_inflight_event();
        ten_node_ingress_pressure_recovers();
        ten_node_journal_full_is_explicit();
        noisy_node_does_not_starve_quiet_nodes();
        write_report();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-MULTINODE HOST/SIMULATED FAIL " << error.what() << '\n';
        return 1;
    }
}
