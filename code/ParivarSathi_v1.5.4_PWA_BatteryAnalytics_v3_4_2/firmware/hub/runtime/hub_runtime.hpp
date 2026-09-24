// Ghar Sajag traceability edition 2.0 | source release 1.5.4
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
#include "gs/protocol.hpp"
#include "ingest/ingest.hpp"
#include "rules/routine_service.hpp"
#include "storage/journal.hpp"
#include "gs/rules.hpp"

#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace gs::hub {

struct ProcessResult {
    EventKey key;
    AckClass ack{AckClass::Rejected};
    bool state_changed{false};
    std::vector<RuleSignalDecision> rule_signals;
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
    // Physical transport adapters validate/decode NodeMessage then enter the same generic event path.
    bool radio_message_callback(const NodeMessage& message, EpochSeconds hub_received_at);
    // Call only after current-session AEAD verification and physical-to-logical
    // registry admission. Preserves an older retained event key across reboot.
    bool authenticated_radio_message_callback(const NodeMessage& message,
                                              const std::string& authenticated_node_id,
                                              const std::string& authenticated_device_id,
                                              std::uint64_t transport_session,
                                              EpochSeconds hub_received_at);
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Consume one admitted event, apply privacy policy, commit and update the reducer.
    // A duplicate journal identity does not repeat reducer effects.
    std::optional<ProcessResult> run_state_once(std::optional<std::uint16_t> local_minute = std::nullopt);
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
    // still G06.
    IncidentDecision deadline(EpochSeconds now, bool clock_trusted);
    void configure_activity_rules(const ActivityRuleConfig& config) { activity_config_ = config; }
    void set_mode(HomeMode mode) { routine_.set_mode(mode); }
    // Called by the trusted scheduler when daytime observation becomes eligible. This is intentionally
    // independent of the morning-routine window.
    void start_activity_monitor(EpochSeconds at) { RulesCore::start_activity_monitor(activity_state_, at); }
    std::vector<RuleSignalDecision> activity_timers(EpochSeconds now, std::uint16_t local_minute,
                                                   bool clock_trusted = true) {
        const RuleEvaluationContext context{routine_.state().mode, coverage_.current(now), clock_trusted};
        return RulesCore::evaluate_activity_timers(activity_state_, activity_config_, now, local_minute, context);
    }
    const ActivityRuleState& activity_state() const { return activity_state_; }
    std::optional<NodePowerTelemetry> latest_power_telemetry(const std::string& node_id) const {
        const auto it = power_telemetry_.find(node_id);
        return it == power_telemetry_.end() ? std::nullopt : std::optional<NodePowerTelemetry>{it->second};
    }
    HubJournal& journal() { return journal_; }
    std::size_t ingest_depth() const { return ingest_.size(); }
    std::size_t ingest_capacity() const { return ingest_.capacity(); }
    std::size_t ingest_high_water() const { return ingest_.high_water(); }
    std::size_t ingest_rejected() const { return ingest_.rejected(); }
    const RoutineState& routine_state() const { return routine_.state(); }

private:
    PeerRegistry peers_;
    IngestQueue ingest_;
    HubJournal journal_;
    CoverageTracker coverage_;
    RoutineService routine_;
    ActivityRuleConfig activity_config_{};
    ActivityRuleState activity_state_{};
    std::map<std::string, NodePowerTelemetry> power_telemetry_;
};

}  // namespace gs::hub
