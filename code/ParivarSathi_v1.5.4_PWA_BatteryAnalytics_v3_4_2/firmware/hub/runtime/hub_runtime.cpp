// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module H05 Hub rules adapter
// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// RoutineService is the stateful shell around the pure RulesCore. start_window replaces configuration and
// resets the caller-owned routine state. It is the natural owner for future persisted window checkpoints,
// but the current code has no autonomous timer, calendar scheduler or prompt/grace coordinator.

#include "hub_runtime.hpp"
#include "hub_checkpoint_codec.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

HubRuntime::HubRuntime(std::size_t ingest_capacity, std::size_t journal_capacity)
    : ingest_(ingest_capacity), journal_(journal_capacity), coverage_(NodeProtocolPolicy::coverage_after_seconds) {
    GS_TRACE(gs::log::Category::Hub, "H00", "HubRuntime.enter", "-");}

HubRuntime::HubRuntime(std::size_t ingest_capacity, JournalEventBackend& backend)
    : ingest_(ingest_capacity), journal_(0), coverage_(NodeProtocolPolicy::coverage_after_seconds) {
    GS_TRACE(gs::log::Category::Hub, "H00", "HubRuntime.scalable_storage.enter", "-");
    (void)journal_.attach_backend(backend);
}

void HubRuntime::authorize_node(const std::string& node_id, std::uint64_t session_id, bool required_for_routine) {
    GS_TRACE(gs::log::Category::Hub, "H00", "authorize_node.enter", "-");
    node_health_.erase(node_id);
    last_authenticated_contact_ms_.erase(node_id);
    peers_.authorize(node_id, session_id);
    if (required_for_routine) coverage_.require_node(node_id);
    if (journal_replayed_) (void)checkpoint_state();
}

void HubRuntime::revoke_node(const std::string& node_id) {
    peers_.revoke(node_id);
    ingest_.discard_source(node_id);
    coverage_.forget_node(node_id);
    power_telemetry_.erase(node_id);
    node_health_.erase(node_id);
    last_authenticated_contact_ms_.erase(node_id);
    for (auto it = ingress_identity_owners_.begin(); it != ingress_identity_owners_.end();) {
        if (it->second.source_id == node_id) it = ingress_identity_owners_.erase(it);
        else ++it;
    }
    if (journal_replayed_) (void)checkpoint_state();
}

bool HubRuntime::observe_authenticated_health(
    const NodeHealthSnapshot& health, const std::string& authenticated_node_id,
    std::uint64_t transport_session, std::uint64_t now_monotonic_ms) {
    if (!valid_node_health(health) || health.node_id != authenticated_node_id ||
        health.session_id != transport_session || now_monotonic_ms == 0 ||
        !peers_.accepts_health(authenticated_node_id, transport_session)) return false;
    const auto found = node_health_.find(authenticated_node_id);
    if (found != node_health_.end() &&
        (health.health_sequence <= found->second.snapshot.health_sequence ||
         now_monotonic_ms < found->second.last_seen_monotonic_ms)) return false;
    if (!observe_authenticated_contact(authenticated_node_id, transport_session,
                                       now_monotonic_ms)) return false;
    node_health_[authenticated_node_id] = {health, now_monotonic_ms};
    return true;
}

bool HubRuntime::observe_authenticated_contact(const std::string& node_id,
                                                std::uint64_t transport_session,
                                                std::uint64_t now_monotonic_ms) {
    if (now_monotonic_ms == 0 ||
        !peers_.accepts_health(node_id, transport_session)) return false;
    const auto found = last_authenticated_contact_ms_.find(node_id);
    if (found != last_authenticated_contact_ms_.end() &&
        now_monotonic_ms < found->second) return false;
    last_authenticated_contact_ms_[node_id] = now_monotonic_ms;
    return true;
}

std::optional<AuthenticatedNodeHealth> HubRuntime::node_health(
    const std::string& node_id) const {
    const auto found = node_health_.find(node_id);
    if (found == node_health_.end()) return std::nullopt;
    return found->second;
}

bool HubRuntime::node_online(const std::string& node_id,
                             std::uint64_t now_monotonic_ms) const {
    const auto found = last_authenticated_contact_ms_.find(node_id);
    return found != last_authenticated_contact_ms_.end() &&
           now_monotonic_ms >= found->second &&
           now_monotonic_ms - found->second <=
               static_cast<std::uint64_t>(NodeProtocolPolicy::offline_after_seconds) * 1000U;
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Replace the active window state; production must persist the transition and define mid-window
// configuration policy.
void HubRuntime::start_window(const RoutineConfig& config, HomeMode mode) {
    GS_TRACE(gs::log::Category::Hub, "H00", "start_window.enter", "-");
    routine_.start_window(config, mode);
    if (journal_replayed_) (void)checkpoint_state();
}

bool HubRuntime::durable_admission_open() const {
    if (checkpoint_fault_ || replay_fence_fault_ ||
        (runtime_state_ && !runtime_state_->healthy())) return false;
    if (durability_owner_ == nullptr) return true;
    const auto* recovered = durability_owner_->recovery_state();
    if (recovered != nullptr && recovered->checkpoint.report_snapshot &&
        !replay_fence_ready_) return false;
    if (replay_fence_ready_ && (recovered == nullptr ||
        !recovered->checkpoint.report_snapshot ||
        recovered->checkpoint.report_snapshot->bank != replay_reference_.bank ||
        recovered->checkpoint.report_snapshot->generation != replay_reference_.generation ||
        recovered->checkpoint.report_snapshot->digest != replay_reference_.digest)) return false;
    const auto epoch = durability_owner_->epoch();
    return durability_owner_->state() == durable::DurabilityOwnerState::Ready &&
           epoch.has_value() && *epoch != 0 &&
           durability_owner_->durable_store() != nullptr &&
           durability_owner_->retirement_repository() != nullptr &&
           journal_.persistent();
}

bool HubRuntime::bind_replay_fence(const durable::RetirementSnapshot& snapshot,
        std::uint32_t storage_epoch,
        const durable::RetirementSnapshotReference& reference,
        storage::DurableEventOutbox& outbox) {
    const auto* recovered = durability_owner_ ? durability_owner_->recovery_state() : nullptr;
    if (!reference.valid() || storage_epoch == 0 || snapshot.storage_epoch != storage_epoch ||
        snapshot.generation == 0 || snapshot.generation != reference.generation ||
        !outbox.replay_fence_matches(storage_epoch, reference) ||
        (durability_owner_ != nullptr && (recovered == nullptr ||
         !recovered->checkpoint.report_snapshot ||
         recovered->checkpoint.report_snapshot->bank != reference.bank ||
         recovered->checkpoint.report_snapshot->generation != reference.generation ||
         recovered->checkpoint.report_snapshot->digest != reference.digest))) {
        replay_fence_fault_ = true;
        replay_fence_ready_ = false;
        return false;
    }
    replay_snapshot_ = snapshot;
    replay_reference_ = reference;
    replay_epoch_ = storage_epoch;
    replay_fence_ready_ = true;
    replay_fence_fault_ = false;
    return true;
}

IdentityRetirementEligibility HubRuntime::identity_retirement_eligibility(
        const DomainEvent& event, std::uint8_t enrollment_slot,
        std::uint32_t enrollment_generation,
        const std::array<std::uint8_t, 32>& owner_binding_digest) {
    if (!durable_admission_open() || !replay_fence_ready_ || runtime_state_ == nullptr ||
        enrollment_generation == 0 || enrollment_slot >= durable::kMaxRetirementNodes ||
        event.key.source_id.empty() || event.key.session_id == 0 || event.key.sequence == 0 ||
        !journal_.cloud_completed(event.key) ||
        replay_snapshot_.nodes[enrollment_slot].enrollment_generation != enrollment_generation ||
        replay_snapshot_.nodes[enrollment_slot].binding_digest != owner_binding_digest ||
        !retirement_proves_node_durable_retirement(replay_snapshot_, enrollment_slot,
            enrollment_generation, event.key.session_id, event.key.sequence))
        return IdentityRetirementEligibility::NotEligible;
    bool found = false, payload_matches = false;
    std::uint64_t ordinal = 0;
    std::optional<std::uint16_t> minute;
    storage::IdentityOwnerEvidence persisted_owner;
    if (!runtime_state_->lookup_identity(event, ordinal, minute, found, payload_matches,
            &persisted_owner) || !found || !payload_matches || ordinal == 0 ||
        ordinal > applied_boundary_ || !persisted_owner.authenticated() ||
        persisted_owner.enrollment_slot != enrollment_slot ||
        persisted_owner.enrollment_generation != enrollment_generation ||
        persisted_owner.binding_digest != owner_binding_digest)
        return IdentityRetirementEligibility::NotEligible;
    return IdentityRetirementEligibility::EligibleWithDurableReplayFence;
}

std::optional<std::uint32_t> HubRuntime::authoritative_storage_epoch() const {
    if (!durable_admission_open() || durability_owner_ == nullptr) return std::nullopt;
    return durability_owner_->epoch();
}

bool HubRuntime::radio_callback(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Hub, "H00", "radio_callback.enter", "-");
    if (!durable_admission_open() || replay_fence_ready_) return false;
    return ingest_.callback_copy(event, peers_);
}

bool HubRuntime::radio_message_callback(const NodeMessage& message, EpochSeconds hub_received_at) {
    if (!durable_admission_open()) return false;
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
    EpochSeconds hub_received_at, std::uint64_t now_monotonic_ms,
    std::uint8_t enrollment_slot, std::uint32_t enrollment_generation,
    std::array<std::uint8_t, 32> owner_binding_digest) {
    if (!durable_admission_open()) return false;
    if (!valid_node_message(message) || message.node_id != authenticated_node_id ||
        authenticated_device_id.empty()) {
        GS_ERROR(gs::log::Category::Hub, "H00", "wire_message.rejected",
                 "invalid_authenticated_node_message");
        return false;
    }
    auto event = domain_event_from_node_message(message, hub_received_at);
    event.key.physical_device_id = authenticated_device_id;
    const bool report_owner_matches = replay_fence_ready_ &&
        enrollment_slot < durable::kMaxRetirementNodes && enrollment_generation != 0 &&
        (replay_snapshot_.occupancy_mask & (1U << enrollment_slot)) != 0 &&
        replay_snapshot_.nodes[enrollment_slot].enrollment_generation == enrollment_generation &&
        replay_snapshot_.nodes[enrollment_slot].binding_digest == owner_binding_digest;
    if (replay_fence_ready_ && (enrollment_slot >= durable::kMaxRetirementNodes ||
        enrollment_generation == 0 || std::all_of(owner_binding_digest.begin(),
            owner_binding_digest.end(), [](std::uint8_t b) { return b == 0; }))) return false;
    if (report_owner_matches && retirement_proves_node_durable_retirement(
            replay_snapshot_, enrollment_slot, enrollment_generation,
            event.key.session_id, event.key.sequence)) {
        bool found = false, payload_matches = false;
        std::uint64_t ordinal = 0;
        std::optional<std::uint16_t> minute;
        if (!runtime_state_ || !runtime_state_->lookup_identity(event, ordinal, minute,
                found, payload_matches)) {
            replay_fence_fault_ = true;
            return false;
        }
        // Retained exact identities preserve ordinary duplicate and conflict
        // behavior. Once a body/identity is ever reclaimed, the fence remains
        // authoritative and rejects this stale key before new admission.
        if (!found) return false;
    }
    const bool accepted = ingest_.callback_copy_authenticated(
        event, peers_,
        authenticated_node_id, transport_session);
    if (accepted && enrollment_generation != 0 && enrollment_slot < durable::kMaxRetirementNodes &&
        std::any_of(owner_binding_digest.begin(), owner_binding_digest.end(),
                    [](std::uint8_t b) { return b != 0; })) {
        storage::IdentityOwnerEvidence owner;
        owner.enrollment_slot = enrollment_slot;
        owner.enrollment_generation = enrollment_generation;
        owner.binding_digest = owner_binding_digest;
        ingress_identity_owners_[event.key.str()] = {event.key.source_id, owner};
    }
    if (accepted && now_monotonic_ms != 0)
        (void)observe_authenticated_contact(authenticated_node_id,
                                            transport_session, now_monotonic_ms);
    if (accepted && message.power.has_value())
        power_telemetry_[message.node_id] = *message.power;
    return accepted;
}

bool HubRuntime::checkpoint_state() {
    if (!runtime_state_) return true;
    security::Bytes bytes;
    if (checkpoint_fault_ || !HubCheckpointCodec::encode(*this, bytes) ||
        !runtime_state_->save_checkpoint(bytes, applied_boundary_)) {
        checkpoint_fault_ = true;
        return false;
    }
    return true;
}

bool HubRuntime::restore_from_journal() {
    if (journal_replayed_ || state_applied_ || ingest_.size() != 0 || !journal_.persistent()) return false;
    if (runtime_state_) {
        // Fresh ledger is allowed only for a genuinely empty outbox. Existing
        // body-only installations require explicit migration, never auto-reset.
        if (!runtime_state_->recover(journal_.size())) { checkpoint_fault_=true; return false; }
        security::Bytes bytes; bool found=false; std::uint64_t boundary=0;
        if (!runtime_state_->load_checkpoint(bytes,boundary,found)) { checkpoint_fault_=true; return false; }
        if (found && !HubCheckpointCodec::restore(*this,bytes)) { checkpoint_fault_=true; return false; }
        applied_boundary_=boundary;
        if (!found && !checkpoint_state()) return false;
    }
    struct ReplayContext { HubRuntime* runtime; std::uint64_t last_ordinal{0}; } context{this};
    const auto replay_event = [](void* opaque, std::uint64_t ordinal,
                                 const DomainEvent& event) -> bool {
        auto& replay = *static_cast<ReplayContext*>(opaque);
        auto& runtime = *replay.runtime;
        if (ordinal == 0 || ordinal <= replay.last_ordinal) return false;
        replay.last_ordinal = ordinal;
        std::optional<std::uint16_t> minute;
        if (runtime.runtime_state_ &&
            !runtime.runtime_state_->identity_context(event.key,ordinal,minute,&event)) return false;
        if (ordinal <= runtime.applied_boundary_) return true;
        // A checkpoint permits absence only through its own boundary. Any gap
        // after that boundary leaves an uncheckpointed reducer transition
        // unprovable, so recovery must fail closed rather than skip it.
        if (ordinal != runtime.applied_boundary_ + 1U) return false;
        (void)runtime.apply_committed_event(event,minute);
        runtime.applied_boundary_=ordinal;
        return true; // Recovery never routes historical notification effects.
    };
    if (!journal_.for_each_with_ordinal(replay_event,&context) ||
        applied_boundary_ != journal_.size() || !checkpoint_state()) {
        checkpoint_fault_=true; return false;
    }
    journal_replayed_=true;
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
    if (!durable_admission_open()) return std::nullopt;
    const auto event = ingest_.pop();
    if (!event) return std::nullopt;
    storage::IdentityOwnerEvidence ingress_owner;
    const auto owner_it = ingress_identity_owners_.find(event->key.str());
    if (owner_it != ingress_identity_owners_.end()) {
        ingress_owner = owner_it->second.evidence;
        ingress_identity_owners_.erase(owner_it);
    }
    const bool passive = is_passive_sensor_event(event->kind);
    if (routine_.state().mode == HomeMode::Privacy && passive) {
        return ProcessResult{event->key, AckClass::DiscardedPolicy, false, {}};
    }
    bool duplicate = false;
    bool identity_already_prepared = false;
    if (runtime_state_) {
        bool identity_found = false, payload_matches = false;
        std::uint64_t identity_ordinal = 0;
        std::optional<std::uint16_t> original_minute;
        if (!runtime_state_->lookup_identity(*event, identity_ordinal,
                original_minute, identity_found, payload_matches)) {
            checkpoint_fault_ = true;
            return ProcessResult{event->key, AckClass::Rejected, false, {}};
        }
        duplicate = journal_.contains(event->key);
        if (identity_found) {
            if (!payload_matches) {
                return ProcessResult{event->key, AckClass::Rejected, false, {}};
            }
            // Exact identities remain durable after their backend-synchronized
            // bodies have been reclaimed. A retry for an identity covered by
            // the durable reducer checkpoint is acknowledged without replaying
            // business effects. A missing body beyond that boundary is corrupt.
            if (duplicate || identity_ordinal <= applied_boundary_)
                return ProcessResult{event->key, AckClass::Durable, false, {}};
            if (identity_ordinal != journal_.size() + 1U) {
                checkpoint_fault_ = true;
                return ProcessResult{event->key, AckClass::Rejected, false, {}};
            }
            // A prepared identity can outlive a failed/unpublished event head.
            // Continue the same transaction so the outbox can finish publication.
            // Its original local-time context is part of the durable identity
            // row; a retry may arrive after the Hub's clock context changed.
            local_minute = original_minute;
            identity_already_prepared = true;
        }
        if (duplicate || (!identity_already_prepared && !runtime_state_->prepare_identity(
                *event, journal_.size() + 1U, local_minute,
                ingress_owner.authenticated() ? &ingress_owner : nullptr))) {
            if (duplicate) checkpoint_fault_ = true;
            return ProcessResult{event->key, AckClass::Rejected, false, {}};
        }
    } else {
        duplicate = journal_.contains(event->key);
        if (duplicate)
            return ProcessResult{event->key, AckClass::Durable, false, {}};
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
    if(runtime_state_ && (!runtime_state_->confirm_event_publication(journal_.size()) ||
        !runtime_state_->identity_context(event->key,journal_.size(),local_minute,&*event))) {
        checkpoint_fault_=true; return ProcessResult{event->key,AckClass::Rejected,false,{}};
    }
    auto signals = apply_committed_event(*event, local_minute);
    applied_boundary_=journal_.size();
    if (!checkpoint_state()) return ProcessResult{event->key,AckClass::Rejected,false,{}};
    return ProcessResult{event->key, AckClass::Durable, committed == CommitResult::Stored, signals};
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
// still G06.
IncidentDecision HubRuntime::deadline(EpochSeconds now, bool clock_trusted) {
    GS_TRACE(gs::log::Category::Hub, "H00", "deadline.enter", "-");
    routine_.set_coverage(coverage_.current(now));
    auto decision=routine_.deadline(now,clock_trusted);
    if (!checkpoint_state()) decision.create=false;
    return decision;
}

void HubRuntime::configure_activity_rules(const ActivityRuleConfig& config) {
    activity_config_=config; if(journal_replayed_) (void)checkpoint_state();
}
void HubRuntime::set_mode(HomeMode mode) {
    routine_.set_mode(mode); if(journal_replayed_) (void)checkpoint_state();
}
void HubRuntime::start_activity_monitor(EpochSeconds at) {
    RulesCore::start_activity_monitor(activity_state_,at);
    if(journal_replayed_) (void)checkpoint_state();
}
std::vector<RuleSignalDecision> HubRuntime::activity_timers(EpochSeconds now,
        std::uint16_t local_minute, bool clock_trusted) {
    if(checkpoint_fault_) return {};
    const RuleEvaluationContext context{routine_.state().mode,coverage_.current(now),clock_trusted};
    auto signals=RulesCore::evaluate_activity_timers(activity_state_,activity_config_,now,local_minute,context);
    if(!checkpoint_state()) return {};
    return signals;
}

}  // namespace gs::hub
