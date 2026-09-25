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

bool HubRuntime::authenticated_radio_message_callback(
    const NodeMessage& message, const std::string& authenticated_node_id,
    const std::string& authenticated_device_id, std::uint64_t transport_session,
    EpochSeconds hub_received_at) {
    if (!valid_node_message(message) || message.node_id != authenticated_node_id ||
        authenticated_device_id.empty()) {
        GS_ERROR(gs::log::Category::Hub, "H00", "wire_message.rejected",
                 "invalid_authenticated_node_message");
        return false;
    }
    auto event = domain_event_from_node_message(message, hub_received_at);
    event.key.physical_device_id = authenticated_device_id;
    const bool accepted = ingest_.callback_copy_authenticated(
        event, peers_,
        authenticated_node_id, transport_session);
    if (accepted && message.power.has_value())
        power_telemetry_[message.node_id] = *message.power;
    return accepted;
}

bool HubRuntime::restore_from_journal() {
    if (journal_replayed_ || state_applied_ || ingest_.size() != 0 ||
        !journal_.persistent()) return false;
    for (const auto& event : journal_.records())
        (void)apply_committed_event(event, std::nullopt);
    journal_replayed_ = true;
    return true;
}

std::vector<RuleSignalDecision> HubRuntime::apply_committed_event(
    const DomainEvent& event, std::optional<std::uint16_t> local_minute) {
    coverage_.observe(event.key.source_id, event.received_at, event.battery_mv);
    routine_.set_coverage(coverage_.current(event.received_at));
    routine_.apply(event);
    state_applied_ = true;
    if (local_minute.has_value()) {
        const RuleEvaluationContext context{
            routine_.state().mode, coverage_.current(event.received_at), true};
        return RulesCore::apply_activity_event(
            activity_state_, activity_config_, event, *local_minute, context);
    }
    if (is_activity(event.kind)) {
        activity_state_.last_activity_at = event.occurred_at;
        activity_state_.last_activity_event_id = event.key.str();
        activity_state_.inactivity_alerted = false;
    }
    return {};
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Consume one admitted event, apply privacy policy, commit and update the reducer.
// Duplicate journal identities receive an ACK without repeating reducer effects.
std::optional<ProcessResult> HubRuntime::run_state_once(std::optional<std::uint16_t> local_minute) {
    GS_TRACE(gs::log::Category::Hub, "H00", "run_state_once.enter", "-");
    const auto event = ingest_.pop();
    if (!event) return std::nullopt;
    const bool passive = is_activity(event->kind);
    if (routine_.state().mode == HomeMode::Privacy && passive) {
        return ProcessResult{event->key, AckClass::DiscardedPolicy, false, {}};
    }
    const auto committed = journal_.commit(*event);
    if (committed == CommitResult::Full || committed == CommitResult::StorageFault) {
        GS_ERROR(gs::log::Category::Storage, "H00", "event.rejected",
                 committed == CommitResult::Full ? "hub_journal_full" : "hub_journal_fault");
        return ProcessResult{event->key, AckClass::Rejected, false, {}};
    }
    if (committed == CommitResult::Duplicate) {
        // A lost ACK may replay the same business event after a Node reboot.
        // Acknowledge the known identity without applying rules a second time.
        return ProcessResult{event->key, AckClass::Durable, false, {}};
    }
    auto signals = apply_committed_event(*event, local_minute);
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
