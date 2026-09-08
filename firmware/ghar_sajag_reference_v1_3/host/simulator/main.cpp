#include "cloud/cloud_sync.hpp"
#include "coverage/coverage.hpp"
#include "ingest/ingest.hpp"
#include "rules/routine_service.hpp"
#include "storage/journal.hpp"
#include "host/logging/file_log_sink.hpp"
#include "gs/feature_flags.hpp"

#include <iostream>

int main() {
    using namespace gs;
    host::FileLogSink sink("logs/simulator.txt", 32768, 1);
    log::set_sink(&sink);
    hub::PeerRegistry peers;
    peers.authorize("kitchen-node", 1);
    hub::IngestQueue radio_mailbox(16);
    hub::HubJournal journal(128);
    hub::CoverageTracker coverage;
    coverage.require_node("kitchen-node");

    RoutineConfig config{"2026-09-07-morning", 1000, 2000, 2300, {"kitchen"}, true};
    hub::RoutineService routine;
    if (FeatureFlags::enabled(Feature::MorningRoutine)) routine.start_window(config, HomeMode::Home);

    DomainEvent motion{{"kitchen-node", 1, 1}, EventKind::Motion, "kitchen", 1500000, 1500, 1501, 1, 3810, false};
    radio_mailbox.callback_copy(motion, peers);  // radio callback: copy only
    const auto queued = radio_mailbox.pop();     // state-owning worker
    if (!queued) return 2;
    const auto committed = journal.commit(*queued);
    if (committed == hub::CommitResult::Full) return 3;
    coverage.observe(queued->key.source_id, queued->received_at, queued->battery_mv);
    if (FeatureFlags::enabled(Feature::MorningRoutine)) {
        routine.set_coverage(coverage.current(queued->received_at));
        routine.apply(*queued);
    }

    hub::CloudSync cloud(journal);
    cloud.set_connected(false, 0);
    const auto local_decision = routine.deadline(config.grace_end_at, true);
    if (FeatureFlags::enabled(Feature::LocalOffline)) cloud.set_connected(true, 3000);
    const auto replay = FeatureFlags::enabled(Feature::LocalOffline) ? cloud.next_batch(3000) : std::vector<DomainEvent>{};

    std::cout << "{\n"
              << "  \"features\": {\"morning_routine\": " << (FeatureFlags::enabled(Feature::MorningRoutine) ? "true" : "false")
              << ", \"call_family\": " << (FeatureFlags::enabled(Feature::CallFamily) ? "true" : "false")
              << ", \"local_offline\": " << (FeatureFlags::enabled(Feature::LocalOffline) ? "true" : "false") << "},\n"
              << "  \"activity_seen\": " << (routine.state().activity_seen ? "true" : "false") << ",\n"
              << "  \"missing_incident_created\": " << (local_decision.create ? "true" : "false") << ",\n"
              << "  \"offline_records_replayed\": " << replay.size() << "\n"
              << "}\n";
    const bool activity_expected = FeatureFlags::enabled(Feature::MorningRoutine);
    const std::size_t replay_expected = FeatureFlags::enabled(Feature::LocalOffline) ? 1U : 0U;
    return routine.state().activity_seen == activity_expected && !local_decision.create && replay.size() == replay_expected ? 0 : 4;
}
