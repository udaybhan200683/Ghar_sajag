#include "hub_runtime.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

HubRuntime::HubRuntime(std::size_t ingest_capacity, std::size_t journal_capacity)
    : ingest_(ingest_capacity), journal_(journal_capacity), coverage_(190) {
    GS_TRACE(gs::log::Category::Hub, "H00", "HubRuntime.enter", "-");}

void HubRuntime::authorize_node(const std::string& node_id, std::uint64_t session_id, bool required_for_routine) {
    GS_TRACE(gs::log::Category::Hub, "H00", "authorize_node.enter", "-");
    peers_.authorize(node_id, session_id);
    if (required_for_routine) coverage_.require_node(node_id);
}

void HubRuntime::start_window(const RoutineConfig& config, HomeMode mode) {
    GS_TRACE(gs::log::Category::Hub, "H00", "start_window.enter", "-");
    routine_.start_window(config, mode);
}

bool HubRuntime::radio_callback(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Hub, "H00", "radio_callback.enter", "-");
    return ingest_.callback_copy(event, peers_);
}

std::optional<ProcessResult> HubRuntime::run_state_once() {
    GS_TRACE(gs::log::Category::Hub, "H00", "run_state_once.enter", "-");
    const auto event = ingest_.pop();
    if (!event) return std::nullopt;
    const bool passive = is_activity(event->kind);
    if (routine_.state().mode == HomeMode::Privacy && passive) {
        return ProcessResult{event->key, AckClass::DiscardedPolicy, false};
    }
    const auto committed = journal_.commit(*event);
    if (committed == CommitResult::Full) {
        GS_ERROR(gs::log::Category::Storage, "H00", "event.rejected", "hub_journal_full");
        return ProcessResult{event->key, AckClass::Rejected, false};
    }
    coverage_.observe(event->key.source_id, event->received_at, event->battery_mv);
    routine_.set_coverage(coverage_.current(event->received_at));
    routine_.apply(*event);
    return ProcessResult{event->key, AckClass::Durable, committed == CommitResult::Stored};
}

IncidentDecision HubRuntime::deadline(EpochSeconds now, bool clock_trusted) {
    GS_TRACE(gs::log::Category::Hub, "H00", "deadline.enter", "-");
    routine_.set_coverage(coverage_.current(now));
    return routine_.deadline(now, clock_trusted);
}

}  // namespace gs::hub
