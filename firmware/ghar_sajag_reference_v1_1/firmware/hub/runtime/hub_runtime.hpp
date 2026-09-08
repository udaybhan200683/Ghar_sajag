#pragma once

#include "coverage/coverage.hpp"
#include "gs/domain.hpp"
#include "ingest/ingest.hpp"
#include "rules/routine_service.hpp"
#include "storage/journal.hpp"

#include <cstddef>
#include <optional>
#include <string>

namespace gs::hub {

struct ProcessResult {
    EventKey key;
    AckClass ack{AckClass::Rejected};
    bool state_changed{false};
};

class HubRuntime {
public:
    HubRuntime(std::size_t ingest_capacity = 32, std::size_t journal_capacity = 1024);
    void authorize_node(const std::string& node_id, std::uint64_t session_id, bool required_for_routine);
    void start_window(const RoutineConfig& config, HomeMode mode);
    bool radio_callback(const DomainEvent& event);
    std::optional<ProcessResult> run_state_once();
    IncidentDecision deadline(EpochSeconds now, bool clock_trusted);
    HubJournal& journal() { return journal_; }
    const RoutineState& routine_state() const { return routine_.state(); }

private:
    PeerRegistry peers_;
    IngestQueue ingest_;
    HubJournal journal_;
    CoverageTracker coverage_;
    RoutineService routine_;
};

}  // namespace gs::hub
