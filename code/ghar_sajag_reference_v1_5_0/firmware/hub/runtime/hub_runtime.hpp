// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H05 Hub rules adapter
// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// RoutineService is the stateful shell around the pure RulesCore. start_window replaces configuration and
// resets the caller-owned routine state. It is the natural owner for future persisted window checkpoints,
// but the current code has no autonomous timer, calendar scheduler or prompt/grace coordinator.

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
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Replace the active window state; production must persist the transition and define mid-window
    // configuration policy.
    void start_window(const RoutineConfig& config, HomeMode mode);
    bool radio_callback(const DomainEvent& event);
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Consume one admitted event, apply privacy policy, commit and update the reducer. Duplicate reducer
    // effects remain G02.
    std::optional<ProcessResult> run_state_once();
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
    // still G06.
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
