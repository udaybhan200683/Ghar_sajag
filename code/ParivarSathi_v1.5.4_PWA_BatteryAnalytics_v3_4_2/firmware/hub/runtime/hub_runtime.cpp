// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module H05 Hub rules adapter
// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// RoutineService is the stateful shell around the pure RulesCore. start_window replaces configuration and
// resets the caller-owned routine state. It is the natural owner for future persisted window checkpoints,
// but the current code has no autonomous timer, calendar scheduler or prompt/grace coordinator.

#include "hub_runtime.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

HubRuntime::HubRuntime(std::size_t ingest_capacity, std::size_t journal_capacity)
    : ingest_(ingest_capacity), journal_(journal_capacity), coverage_(NodeProtocolPolicy::offline_after_seconds) {
    GS_TRACE(gs::log::Category::Hub, "H00", "HubRuntime.enter", "-");}

void HubRuntime::authorize_node(const std::string& node_id, std::uint64_t session_id, bool required_for_routine) {
    GS_TRACE(gs::log::Category::Hub, "H00", "authorize_node.enter", "-");
    peers_.authorize(node_id, session_id);
    if (required_for_routine) coverage_.require_node(node_id);
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Replace the active window state; production must persist the transition and define mid-window
// configuration policy.
void HubRuntime::start_window(const RoutineConfig& config, HomeMode mode) {
    GS_TRACE(gs::log::Category::Hub, "H00", "start_window.enter", "-");
    routine_.start_window(config, mode);
}

bool HubRuntime::radio_callback(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Hub, "H00", "radio_callback.enter", "-");
    return ingest_.callback_copy(event, peers_);
}

bool HubRuntime::radio_message_callback(const NodeMessage& message, EpochSeconds hub_received_at) {
    if (!valid_node_message(message)) {
        GS_ERROR(gs::log::Category::Hub, "H00", "wire_message.rejected", "invalid_node_message");
        return false;
    }
    const bool accepted = radio_callback(domain_event_from_node_message(message, hub_received_at));
    if (accepted && message.power.has_value()) {
        power_telemetry_[message.node_id] = *message.power;
    }
    return accepted;
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Consume one admitted event, apply privacy policy, commit and update the reducer. Duplicate reducer
// effects remain G02.
std::optional<ProcessResult> HubRuntime::run_state_once(std::optional<std::uint16_t> local_minute) {
    GS_TRACE(gs::log::Category::Hub, "H00", "run_state_once.enter", "-");
    const auto event = ingest_.pop();
    if (!event) return std::nullopt;
    const bool passive = is_activity(event->kind);
    if (routine_.state().mode == HomeMode::Privacy && passive) {
        return ProcessResult{event->key, AckClass::DiscardedPolicy, false, {}};
    }
    const auto committed = journal_.commit(*event);
    if (committed == CommitResult::Full) {
        GS_ERROR(gs::log::Category::Storage, "H00", "event.rejected", "hub_journal_full");
        return ProcessResult{event->key, AckClass::Rejected, false, {}};
    }
    coverage_.observe(event->key.source_id, event->received_at, event->battery_mv);
    routine_.set_coverage(coverage_.current(event->received_at));
    routine_.apply(*event);
    std::vector<RuleSignalDecision> signals;
    if (local_minute.has_value()) {
        const RuleEvaluationContext context{routine_.state().mode, coverage_.current(event->received_at), true};
        signals = RulesCore::apply_activity_event(activity_state_, activity_config_, *event, *local_minute, context);
    } else if (is_activity(event->kind)) {
        activity_state_.last_activity_at = event->occurred_at;
        activity_state_.last_activity_event_id = event->key.str();
        activity_state_.inactivity_alerted = false;
    }
    return ProcessResult{event->key, AckClass::Durable, committed == CommitResult::Stored, signals};
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
// still G06.
IncidentDecision HubRuntime::deadline(EpochSeconds now, bool clock_trusted) {
    GS_TRACE(gs::log::Category::Hub, "H00", "deadline.enter", "-");
    routine_.set_coverage(coverage_.current(now));
    return routine_.deadline(now, clock_trusted);
}

}  // namespace gs::hub
