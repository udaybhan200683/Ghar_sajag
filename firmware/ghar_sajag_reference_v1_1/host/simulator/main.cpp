#include "cloud/cloud_sync.hpp"
#include "coverage/coverage.hpp"
#include "ingest/ingest.hpp"
#include "rules/routine_service.hpp"
#include "storage/journal.hpp"
#include "host/logging/file_log_sink.hpp"

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
    routine.start_window(config, HomeMode::Home);

    DomainEvent motion{{"kitchen-node", 1, 1}, EventKind::Motion, "kitchen", 1500000, 1500, 1501, 1, 3810, false};
    radio_mailbox.callback_copy(motion, peers);  // radio callback: copy only
    const auto queued = radio_mailbox.pop();     // state-owning worker
    if (!queued) return 2;
    const auto committed = journal.commit(*queued);
    if (committed == hub::CommitResult::Full) return 3;
    coverage.observe(queued->key.source_id, queued->received_at, queued->battery_mv);
    routine.set_coverage(coverage.current(queued->received_at));
    routine.apply(*queued);

    hub::CloudSync cloud(journal);
    cloud.set_connected(false, 0);
    const auto local_decision = routine.deadline(config.grace_end_at, true);
    cloud.set_connected(true, 3000);
    const auto replay = cloud.next_batch(3000);

    std::cout << "{\n"
              << "  \"activity_seen\": " << (routine.state().activity_seen ? "true" : "false") << ",\n"
              << "  \"missing_incident_created\": " << (local_decision.create ? "true" : "false") << ",\n"
              << "  \"offline_records_replayed\": " << replay.size() << "\n"
              << "}\n";
    return routine.state().activity_seen && !local_decision.create && replay.size() == 1 ? 0 : 4;
}
