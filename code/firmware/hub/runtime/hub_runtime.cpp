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

#include <algorithm>
#include <charconv>
#include <limits>

namespace gs::hub {
namespace {
bool same_morning_policy(const ActivityRuleConfig& left, const ActivityRuleConfig& right) {
    if (left.morning_sequence_enabled != right.morning_sequence_enabled ||
        left.morning_start_minute != right.morning_start_minute ||
        left.morning_end_minute != right.morning_end_minute ||
        left.morning_sequence_window_seconds != right.morning_sequence_window_seconds ||
        left.morning_sequence_strict_order != right.morning_sequence_strict_order ||
        left.morning_bedroom_location != right.morning_bedroom_location ||
        left.morning_bathroom_location != right.morning_bathroom_location ||
        left.morning_kitchen_location != right.morning_kitchen_location ||
        left.morning_steps.size() != right.morning_steps.size()) return false;
    for (std::size_t i = 0; i < left.morning_steps.size(); ++i) {
        const auto& a = left.morning_steps[i];
        const auto& b = right.morning_steps[i];
        if (a.location != b.location || a.enabled != b.enabled || a.required != b.required)
            return false;
    }
    return true;
}

bool same_activity_config(const ActivityRuleConfig& left, const ActivityRuleConfig& right) {
    return same_morning_policy(left, right) &&
        left.quiet_hours_enabled == right.quiet_hours_enabled &&
        left.quiet_start_minute == right.quiet_start_minute &&
        left.quiet_end_minute == right.quiet_end_minute &&
        left.door_open_timeout_seconds == right.door_open_timeout_seconds &&
        left.daytime_inactivity_enabled == right.daytime_inactivity_enabled &&
        left.daytime_start_minute == right.daytime_start_minute &&
        left.daytime_end_minute == right.daytime_end_minute &&
        left.daytime_inactivity_seconds == right.daytime_inactivity_seconds &&
        left.night_activity_enabled == right.night_activity_enabled &&
        left.night_start_minute == right.night_start_minute &&
        left.night_end_minute == right.night_end_minute &&
        left.night_bathroom_location == right.night_bathroom_location &&
        left.night_bathroom_visit_threshold == right.night_bathroom_visit_threshold &&
        left.night_common_location == right.night_common_location &&
        left.night_common_visit_threshold == right.night_common_visit_threshold &&
        left.night_visit_merge_seconds == right.night_visit_merge_seconds &&
        left.post_door_inactivity_enabled == right.post_door_inactivity_enabled &&
        left.post_door_inactivity_seconds == right.post_door_inactivity_seconds;
}

void reset_morning_progress(ActivityRuleState& state) {
    state.morning_started = false;
    state.morning_bathroom_seen = false;
    state.morning_kitchen_seen = false;
    state.morning_completed = false;
    state.morning_started_at.reset();
    state.morning_seen_locations.clear();
}

bool parse_unsigned(const std::string& text, std::size_t begin, std::size_t end,
                    std::uint64_t& value) {
    if (begin >= end) return false;
    const auto parsed = std::from_chars(text.data() + begin, text.data() + end, value);
    return parsed.ec == std::errc{} && parsed.ptr == text.data() + end;
}

bool parse_identity_event_key(const std::string& text, EventKey& key) {
    if (text.empty()) return false;
    if (text[0] != 'p') {
        const auto last = text.rfind(':');
        if (last == std::string::npos || last == 0) return false;
        const auto prior = text.rfind(':', last - 1U);
        if (prior == std::string::npos || prior == 0) return false;
        std::uint64_t session = 0, sequence = 0;
        if (!parse_unsigned(text, prior + 1U, last, session) ||
            !parse_unsigned(text, last + 1U, text.size(), sequence)) return false;
        key = EventKey{text.substr(0, prior), session, sequence};
        return key.str() == text;
    }
    const auto physical_colon = text.find(':', 1U);
    std::uint64_t physical_size = 0;
    if (physical_colon == std::string::npos ||
        !parse_unsigned(text, 1U, physical_colon, physical_size) ||
        physical_size > text.size() - physical_colon - 1U) return false;
    const auto physical_begin = physical_colon + 1U;
    const auto source_marker = physical_begin + static_cast<std::size_t>(physical_size);
    if (source_marker >= text.size() || text[source_marker] != 'n') return false;
    const auto source_colon = text.find(':', source_marker + 1U);
    std::uint64_t source_size = 0;
    if (source_colon == std::string::npos ||
        !parse_unsigned(text, source_marker + 1U, source_colon, source_size) ||
        source_size > text.size() - source_colon - 1U) return false;
    const auto source_begin = source_colon + 1U;
    const auto session_marker = source_begin + static_cast<std::size_t>(source_size);
    if (session_marker >= text.size() || text[session_marker] != 's') return false;
    const auto sequence_marker = text.find('q', session_marker + 1U);
    std::uint64_t session = 0, sequence = 0;
    if (sequence_marker == std::string::npos ||
        !parse_unsigned(text, session_marker + 1U, sequence_marker, session) ||
        !parse_unsigned(text, sequence_marker + 1U, text.size(), sequence)) return false;
    key = EventKey{text.substr(source_begin, static_cast<std::size_t>(source_size)),
        session, sequence,
        text.substr(physical_begin, static_cast<std::size_t>(physical_size))};
    return key.str() == text;
}
}

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
    cloud_contacts_.erase(node_id);
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
    cloud_contacts_.erase(node_id);
    node_offline_timeouts_.erase(node_id);
    for (auto it = ingress_identity_owners_.begin(); it != ingress_identity_owners_.end();) {
        if (it->second.source_id == node_id) it = ingress_identity_owners_.erase(it);
        else ++it;
    }
    if (journal_replayed_) (void)checkpoint_state();
}

bool HubRuntime::observe_authenticated_health(
    const NodeHealthSnapshot& health, const std::string& authenticated_node_id,
    std::uint64_t transport_session, std::uint64_t now_monotonic_ms,
    EpochSeconds trusted_contact_at) {
    if (!valid_node_health(health) || health.node_id != authenticated_node_id ||
        health.session_id != transport_session || now_monotonic_ms == 0 ||
        !peers_.accepts_health(authenticated_node_id, transport_session)) return false;
    const auto found = node_health_.find(authenticated_node_id);
    if (found != node_health_.end() &&
        (health.health_sequence <= found->second.snapshot.health_sequence ||
         now_monotonic_ms < found->second.last_seen_monotonic_ms)) return false;
    if (!observe_authenticated_contact(authenticated_node_id, transport_session,
                                       now_monotonic_ms, trusted_contact_at,
                                       CloudContactKind::NodeHealth)) return false;
    // The compact C8 ACK trace deliberately omits unrelated health counters.
    // It refreshes the authenticated contact lease but cannot overwrite the
    // last complete NodeHealth snapshot used by operational status views.
    if (health.schema != NodeHealthSnapshot::c8_ack_wait_trace_schema_version)
        node_health_[authenticated_node_id] = {health, now_monotonic_ms};
    return true;
}

bool HubRuntime::observe_authenticated_contact(const std::string& node_id,
                                                std::uint64_t transport_session,
                                                std::uint64_t now_monotonic_ms, EpochSeconds trusted_contact_at,
                                                std::optional<CloudContactKind> cloud_contact_kind) {
    if (now_monotonic_ms == 0 ||
        !peers_.accepts_health(node_id, transport_session)) return false;
    const auto found = last_authenticated_contact_ms_.find(node_id);
    if (found != last_authenticated_contact_ms_.end() &&
        now_monotonic_ms < found->second) return false;
    last_authenticated_contact_ms_[node_id] = now_monotonic_ms;
    if (cloud_contact_kind) {
        constexpr auto max_revision = static_cast<std::uint64_t>(
            std::numeric_limits<std::int64_t>::max());
        auto found_cloud = cloud_contacts_.find(node_id);
        const auto prior_revision = found_cloud == cloud_contacts_.end()
            ? 0U : found_cloud->second.source_revision;
        if (prior_revision < max_revision) {
            cloud_contacts_[node_id] = AuthenticatedCloudContact{
                transport_session, now_monotonic_ms, prior_revision + 1U,
                *cloud_contact_kind};
        } else {
            // Exhaustion is fail closed for cloud freshness. Local liveness is
            // still updated above and no event/ACK behavior is affected.
            cloud_contacts_.erase(node_id);
        }
    }
    if (trusted_contact_at > 0) coverage_.observe(node_id, trusted_contact_at);
    return true;
}

std::optional<AuthenticatedNodeHealth> HubRuntime::node_health(
    const std::string& node_id) const {
    const auto found = node_health_.find(node_id);
    if (found == node_health_.end()) return std::nullopt;
    return found->second;
}

std::optional<AuthenticatedCloudContact> HubRuntime::cloud_contact(
    const std::string& node_id) const {
    const auto found = cloud_contacts_.find(node_id);
    if (found == cloud_contacts_.end() || found->second.session_id == 0 ||
        found->second.source_revision == 0 ||
        !peers_.accepts_health(node_id, found->second.session_id)) return std::nullopt;
    return found->second;
}

bool HubRuntime::cloud_contact_online(const std::string& node_id,
                                      std::uint64_t now_monotonic_ms) const {
    const auto contact = cloud_contact(node_id);
    const auto profile = node_offline_timeouts_.find(node_id);
    if (!contact || !node_profile_known(node_id) || now_monotonic_ms < contact->received_monotonic_ms)
        return false;
    const auto timeout = profile == node_offline_timeouts_.end()
        ? NodeProtocolPolicy::offline_after_seconds : *profile->second;
    return now_monotonic_ms - contact->received_monotonic_ms <=
        static_cast<std::uint64_t>(timeout) * 1000U;
}

void HubRuntime::set_node_offline_timeout(const std::string& node_id, std::optional<std::uint32_t> seconds) {
    node_offline_timeouts_[node_id] = seconds;
    coverage_.set_node_lease(node_id, seconds ? *seconds : 0);
}
bool HubRuntime::node_profile_known(const std::string& node_id) const {
    const auto profile = node_offline_timeouts_.find(node_id);
    return profile == node_offline_timeouts_.end() || profile->second.has_value();
}
std::optional<std::uint32_t> HubRuntime::node_offline_timeout_seconds(
    const std::string& node_id) const {
    const auto profile = node_offline_timeouts_.find(node_id);
    if (profile == node_offline_timeouts_.end())
        return NodeProtocolPolicy::offline_after_seconds;
    return profile->second;
}

bool HubRuntime::node_online(const std::string& node_id,
                             std::uint64_t now_monotonic_ms) const {
    const auto profile = node_offline_timeouts_.find(node_id);
    if (!node_profile_known(node_id)) return false;
    const auto timeout = profile == node_offline_timeouts_.end()
        ? NodeProtocolPolicy::offline_after_seconds : *profile->second;
    const auto found = last_authenticated_contact_ms_.find(node_id);
    return found != last_authenticated_contact_ms_.end() &&
           now_monotonic_ms >= found->second &&
           now_monotonic_ms - found->second <=
               static_cast<std::uint64_t>(timeout) * 1000U;
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
    return bind_replay_fence_diagnostic(snapshot, storage_epoch, reference, outbox) ==
           ReplayFenceBindResult::Bound;
}

ReplayFenceBindResult HubRuntime::bind_replay_fence_diagnostic(
        const durable::RetirementSnapshot& snapshot,
        std::uint32_t storage_epoch,
        const durable::RetirementSnapshotReference& reference,
        storage::DurableEventOutbox& outbox) {
    const auto* recovered = durability_owner_ ? durability_owner_->recovery_state() : nullptr;
    const auto fail = [this](ReplayFenceBindResult result) {
        replay_fence_fault_ = true;
        replay_fence_ready_ = false;
        return result;
    };
    if (!reference.valid()) return fail(ReplayFenceBindResult::InvalidReference);
    if (storage_epoch == 0) return fail(ReplayFenceBindResult::InvalidEpoch);
    if (snapshot.storage_epoch != storage_epoch)
        return fail(ReplayFenceBindResult::SnapshotEpochMismatch);
    if (snapshot.generation == 0)
        return fail(ReplayFenceBindResult::SnapshotGenerationMissing);
    if (snapshot.generation != reference.generation)
        return fail(ReplayFenceBindResult::SnapshotGenerationMismatch);
    if (!outbox.replay_fence_matches(storage_epoch, reference))
        return fail(ReplayFenceBindResult::OutboxFenceMismatch);
    if (durability_owner_ != nullptr) {
        if (recovered == nullptr || !recovered->checkpoint.report_snapshot)
            return fail(ReplayFenceBindResult::SelectedCheckpointMissing);
        if (recovered->checkpoint.report_snapshot->bank != reference.bank ||
            recovered->checkpoint.report_snapshot->generation != reference.generation ||
            recovered->checkpoint.report_snapshot->digest != reference.digest)
            return fail(ReplayFenceBindResult::SelectedCheckpointMismatch);
    }
    replay_snapshot_ = snapshot;
    replay_reference_ = reference;
    replay_epoch_ = storage_epoch;
    replay_fence_ready_ = true;
    replay_fence_fault_ = false;
    return ReplayFenceBindResult::Bound;
}

ReplayFenceReconcileResult HubRuntime::reconcile_selected_replay_fence(
        const durable::RecoveryState& selected_state,
        durable::RetirementSnapshotRepository& repository,
        storage::RuntimeStateStore& runtime_state,
        std::uint32_t storage_epoch,
        storage::DurableEventOutbox& outbox) {
    ReplayFenceReconcileResult result;
    if (!selected_state.checkpoint.report_snapshot) {
        result.stage = ReplayFenceReconcileStage::SnapshotReferenceMissing;
        return result;
    }

    const auto& reference = *selected_state.checkpoint.report_snapshot;
    durable::RetirementSnapshot snapshot;
    if (!repository.load(reference, snapshot)) {
        result.stage = ReplayFenceReconcileStage::SnapshotReload;
        return result;
    }

    security::Bytes reducer_checkpoint;
    std::uint64_t checkpoint_boundary = 0;
    bool checkpoint_found = false;
    if (!runtime_state.load_checkpoint(reducer_checkpoint, checkpoint_boundary,
                                       checkpoint_found)) {
        result.stage = ReplayFenceReconcileStage::ReducerCheckpointReload;
        return result;
    }
    if (!checkpoint_found) {
        result.stage = ReplayFenceReconcileStage::ReducerCheckpointMissing;
        return result;
    }

    result.publication = outbox.publish_replay_fence_diagnostic(
        storage_epoch, reference, checkpoint_boundary);
    if (result.publication != storage::ReplayFencePublishResult::Published &&
        result.publication != storage::ReplayFencePublishResult::AlreadyPublished) {
        result.stage = ReplayFenceReconcileStage::OutboxPublication;
        return result;
    }

    result.binding = bind_replay_fence_diagnostic(snapshot, storage_epoch,
                                                   reference, outbox);
    if (result.binding != ReplayFenceBindResult::Bound)
        result.stage = ReplayFenceReconcileStage::RuntimeBinding;
    return result;
}

ReplayFenceReconcileResult HubRuntime::reconcile_replay_fence(
        durable::DurableStore& durable_store,
        durable::RetirementSnapshotRepository& repository,
        storage::RuntimeStateStore& runtime_state,
        std::uint32_t storage_epoch,
        storage::DurableEventOutbox& outbox) {
    durable::RecoveryState selected_state;
    if (durability_owner_) {
        if (durability_owner_->durable_store() != &durable_store ||
            durability_owner_->epoch() != storage_epoch) {
            replay_fence_fault_ = true;
            return {ReplayFenceReconcileStage::DependenciesUnavailable};
        }
        if (!durability_owner_->refresh_recovery_state()) {
            replay_fence_fault_ = true;
            return {ReplayFenceReconcileStage::SelectedStateReload};
        }
        const auto* selected = durability_owner_->recovery_state();
        if (!selected) {
            replay_fence_fault_ = true;
            return {ReplayFenceReconcileStage::SelectedStateReload};
        }
        selected_state = *selected;
    } else if (!durable_store.recover(selected_state)) {
        replay_fence_fault_ = true;
        ReplayFenceReconcileResult result;
        result.stage = ReplayFenceReconcileStage::SelectedStateReload;
        return result;
    }
    return reconcile_selected_replay_fence(selected_state, repository,
                                           runtime_state, storage_epoch, outbox);
}

const char* replay_fence_bind_result_name(ReplayFenceBindResult result) {
    switch (result) {
        case ReplayFenceBindResult::Bound: return "BOUND";
        case ReplayFenceBindResult::InvalidReference: return "INVALID_REFERENCE";
        case ReplayFenceBindResult::InvalidEpoch: return "INVALID_EPOCH";
        case ReplayFenceBindResult::SnapshotEpochMismatch: return "SNAPSHOT_EPOCH_MISMATCH";
        case ReplayFenceBindResult::SnapshotGenerationMissing: return "SNAPSHOT_GENERATION_MISSING";
        case ReplayFenceBindResult::SnapshotGenerationMismatch: return "SNAPSHOT_GENERATION_MISMATCH";
        case ReplayFenceBindResult::OutboxFenceMismatch: return "OUTBOX_FENCE_MISMATCH";
        case ReplayFenceBindResult::SelectedCheckpointMissing: return "SELECTED_CHECKPOINT_MISSING";
        case ReplayFenceBindResult::SelectedCheckpointMismatch: return "SELECTED_CHECKPOINT_MISMATCH";
    }
    return "UNKNOWN";
}

const char* replay_fence_reconcile_stage_id(ReplayFenceReconcileStage stage) {
    switch (stage) {
        case ReplayFenceReconcileStage::Ready: return "RPF00";
        case ReplayFenceReconcileStage::SelectedStateReload: return "RPF01";
        case ReplayFenceReconcileStage::SnapshotReferenceMissing: return "RPF02";
        case ReplayFenceReconcileStage::SnapshotReload: return "RPF03";
        case ReplayFenceReconcileStage::ReducerCheckpointReload: return "RPF04";
        case ReplayFenceReconcileStage::ReducerCheckpointMissing: return "RPF05";
        case ReplayFenceReconcileStage::OutboxPublication: return "RPF06";
        case ReplayFenceReconcileStage::RuntimeBinding: return "RPF07";
        case ReplayFenceReconcileStage::DependenciesUnavailable: return "RPF08";
    }
    return "RPF99";
}

IdentityRetirementEligibility HubRuntime::identity_retirement_eligibility(
        const DomainEvent& event, std::uint8_t enrollment_slot,
        std::uint32_t enrollment_generation,
        const std::array<std::uint8_t, 32>& owner_binding_digest) {
    bool found = false, payload_matches = false;
    std::uint64_t ordinal = 0;
    std::optional<std::uint16_t> minute;
    storage::IdentityOwnerEvidence persisted_owner;
    security::Key32 persisted_digest{};
    if (runtime_state_ == nullptr ||
        !runtime_state_->lookup_identity(event, ordinal, minute, found, payload_matches,
            &persisted_owner, &persisted_digest) || !found || !payload_matches ||
        !persisted_owner.authenticated() || persisted_owner.enrollment_slot != enrollment_slot ||
        persisted_owner.enrollment_generation != enrollment_generation ||
        persisted_owner.binding_digest != owner_binding_digest) {
        return IdentityRetirementEligibility::NotEligible;
    }
    storage::IdentityCompactionRecord record;
    record.event_key = event.key.str();
    record.original_ordinal = ordinal;
    record.local_minute = minute;
    record.payload_digest = persisted_digest;
    record.owner = persisted_owner;
    return identity_record_retirement_eligibility(record);
}

IdentityRetirementEligibility HubRuntime::identity_record_retirement_eligibility(
        const storage::IdentityCompactionRecord& record) {
    EventKey key;
    if (!durable_admission_open() || !replay_fence_ready_ || runtime_state_ == nullptr ||
        record.original_ordinal == 0 || record.original_ordinal > applied_boundary_ ||
        !record.owner.authenticated() ||
        std::all_of(record.payload_digest.begin(), record.payload_digest.end(),
                    [](std::uint8_t b) { return b == 0; }) ||
        !parse_identity_event_key(record.event_key, key) || key.source_id.empty() ||
        key.session_id == 0 || key.sequence == 0 ||
        (!journal_.cloud_completed(key) &&
         (journal_.contains(key) ||
          record.original_ordinal > journal_.absent_body_retirement_boundary())) ||
        replay_snapshot_.nodes[record.owner.enrollment_slot].enrollment_generation !=
            record.owner.enrollment_generation ||
        replay_snapshot_.nodes[record.owner.enrollment_slot].binding_digest !=
            record.owner.binding_digest ||
        !retirement_proves_node_durable_retirement(replay_snapshot_,
            record.owner.enrollment_slot, record.owner.enrollment_generation,
            key.session_id, key.sequence))
        return IdentityRetirementEligibility::NotEligible;
    return IdentityRetirementEligibility::EligibleWithDurableReplayFence;
}

bool HubRuntime::plan_identity_compaction(storage::IdentityCompactionRetainedVisitor visitor,
        void* visitor_context, storage::IdentityCompactionPlan& plan) {
    plan = {};
    if (!durable_admission_open() || !replay_fence_ready_ || runtime_state_ == nullptr ||
        visitor == nullptr) return false;
    const auto fence_reference = replay_reference_;
    const auto fence_epoch = replay_epoch_;
    struct PlanContext {
        HubRuntime* runtime;
        storage::IdentityCompactionRetainedVisitor visitor;
        void* visitor_context;
    } context{this, visitor, visitor_context};
    auto classifier = [](void* context, const storage::IdentityCompactionRecord& record) {
        auto* plan_context = static_cast<PlanContext*>(context);
        if (!record.owner.authenticated()) return storage::IdentityCompactionDisposition::Retain;
        EventKey key;
        if (!parse_identity_event_key(record.event_key, key))
            return storage::IdentityCompactionDisposition::Blocked;
        if (plan_context->runtime->journal_.contains(key))
            return storage::IdentityCompactionDisposition::Retain;
        return plan_context->runtime->identity_record_retirement_eligibility(record) ==
                IdentityRetirementEligibility::EligibleWithDurableReplayFence
            ? storage::IdentityCompactionDisposition::Fenced
            : storage::IdentityCompactionDisposition::Retain;
    };
    auto visit = [](void* context, const storage::IdentityCompactionRecord& record) {
        auto* plan_context = static_cast<PlanContext*>(context);
        return plan_context->visitor(plan_context->visitor_context, record);
    };
    const bool planned = runtime_state_->plan_identity_compaction(
        classifier, visit, &context, plan);
    if (!planned || !durable_admission_open() || !replay_fence_ready_ ||
        replay_epoch_ != fence_epoch || replay_reference_.bank != fence_reference.bank ||
        replay_reference_.generation != fence_reference.generation ||
        replay_reference_.digest != fence_reference.digest) {
        plan.complete = false;
        if (plan.blocked_records == 0) ++plan.blocked_records;
        return false;
    }
    return true;
}

bool HubRuntime::compact_identity_generation(std::uint32_t safety_reserve_bytes,
        storage::IdentityCompactionPlan& plan) {
#if defined(ESP_PLATFORM) && (!defined(CONFIG_GS_IDENTITY_COMPACTION_ENABLED) || \
                              !CONFIG_GS_IDENTITY_COMPACTION_ENABLED)
    (void)safety_reserve_bytes;(void)plan;
    return false;
#endif
    plan={};
    if(!durable_admission_open() || !replay_fence_ready_ || runtime_state_==nullptr)
        return false;
    const auto reference=replay_reference_;
    const auto epoch=replay_epoch_;
    struct Context { HubRuntime* runtime; durable::RetirementSnapshotReference reference;
                     std::uint64_t epoch; } context{this,reference,epoch};
    const auto still_current=[](void* opaque) {
        const auto& current=*static_cast<Context*>(opaque);
        return current.runtime->durable_admission_open() &&
            current.runtime->replay_fence_ready_ && current.runtime->replay_epoch_==current.epoch &&
            current.runtime->replay_reference_.bank==current.reference.bank &&
            current.runtime->replay_reference_.generation==current.reference.generation &&
            current.runtime->replay_reference_.digest==current.reference.digest;
    };
    const auto classify=[](void* opaque,const storage::IdentityCompactionRecord& record) {
        auto& runtime=*static_cast<Context*>(opaque)->runtime;
        if(!record.owner.authenticated())return storage::IdentityCompactionDisposition::Retain;
        EventKey key;
        if(!parse_identity_event_key(record.event_key,key))
            return storage::IdentityCompactionDisposition::Blocked;
        // A retained body still participates in outbox replay and must keep its
        // exact identity row even when the backend and Node have completed.
        if(runtime.journal_.contains(key))return storage::IdentityCompactionDisposition::Retain;
        return runtime.identity_record_retirement_eligibility(record)==
                IdentityRetirementEligibility::EligibleWithDurableReplayFence
            ? storage::IdentityCompactionDisposition::Fenced
            : storage::IdentityCompactionDisposition::Retain;
    };
    security::Bytes authority{'R','F',1};
    const auto epoch_wide=static_cast<std::uint64_t>(epoch);
    for(unsigned i=0;i<8;++i)authority.push_back(static_cast<std::uint8_t>(epoch_wide>>(i*8U)));
    for(unsigned i=0;i<8;++i)authority.push_back(
        static_cast<std::uint8_t>(reference.generation>>(i*8U)));
    authority.push_back(reference.bank);
    authority.insert(authority.end(),reference.digest.begin(),reference.digest.end());
    return runtime_state_->compact_identity(classify,&context,authority,epoch,reference.generation,
        reference.bank,reference.digest,still_current,&context,safety_reserve_bytes,plan);
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
                                            transport_session, now_monotonic_ms, 0,
                                            CloudContactKind::AuthenticatedEvent);
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

bool HubRuntime::recover_native_outbox(storage::DurableEventOutbox& outbox,
        InitialEnrollmentResolver resolve, void* owner_context) {
    if (!runtime_state_ || !durability_owner_ || !resolve || journal_replayed_ ||
        state_applied_ || ingest_.size()!=0 ||
        durability_owner_->state()!=durable::DurabilityOwnerState::Ready) return false;
    security::Bytes initial_checkpoint; std::uint64_t initial_boundary=0; bool initial_found=false;
    if (!runtime_state_->load_checkpoint(initial_checkpoint,initial_boundary,initial_found) ||
        (!initial_found && !outbox.initial_storage_empty())) return false;
    struct Context {
        HubRuntime& runtime; storage::DurableEventOutbox& outbox;
        InitialEnrollmentResolver resolve; void* owner_context;
        const DomainEvent* event{nullptr}; storage::IdentityOwnerEvidence owner{};
    } context{*this,outbox,resolve,owner_context,nullptr,{}};
    // A noncapturing callback shares the existing runtime, not a second reducer.
    struct Proof {
        static bool candidate(void* opaque,std::uint64_t ordinal,const std::string& key,
                const security::Bytes& payload,std::uint32_t epoch,
                const durable::ReportSnapshotReference& witness) {
            auto& c=*static_cast<Context*>(opaque);
            DomainEvent event; security::Bytes checkpoint; bool found=false;
            storage::IdentityOwnerEvidence current;
            if (ordinal!=1 || !HubJournal::decode_event_payload(payload,event) ||
                event.key.str()!=key || !c.runtime.runtime_state_->inspect_initial(
                    &event,checkpoint,found,c.owner) || !found ||
                !c.resolve(c.owner_context,event,current) || !current.authenticated() ||
                current.enrollment_slot!=c.owner.enrollment_slot ||
                current.enrollment_generation!=c.owner.enrollment_generation ||
                current.binding_digest!=c.owner.binding_digest ||
                !HubCheckpointCodec::restore(c.runtime,checkpoint)) return false;
            c.event=&event;
            const auto validator=[](void* p,const durable::RetirementSnapshot& report) {
                auto& x=*static_cast<Context*>(p);
                if (report.storage_epoch!=1 || report.legacy_binding_domain ||
                    x.owner.enrollment_slot>=report.nodes.size()) return false;
                const auto slot=x.owner.enrollment_slot;
                if ((report.occupancy_mask & (1U<<slot))!=0 &&
                    (report.nodes[slot].enrollment_generation!=x.owner.enrollment_generation ||
                     report.nodes[slot].binding_digest!=x.owner.binding_digest)) return false;
                return !durable::retirement_proves_node_durable_retirement(report,slot,
                    x.owner.enrollment_generation,x.event->key.session_id,x.event->key.sequence);
            };
            const bool valid=c.runtime.durability_owner_->verify_native_zero_history(
                validator,&c,epoch,witness);
            c.event=nullptr;
            return valid;
        }
    };
    const auto recovery=outbox.recover(Proof::candidate,&context);
    if ((recovery!=storage::OutboxRecovery::Ready && recovery!=storage::OutboxRecovery::Empty) ||
        !outbox.healthy()) return false;
    security::Bytes checkpoint; std::uint64_t boundary=0; bool found=false;
    if (!runtime_state_->load_checkpoint(checkpoint,boundary,found)) return false;
    if (!found) {
        if (!outbox.initial_inventory_empty()) return false;
        const auto empty=[](void* opaque) {
            auto& c=*static_cast<Context*>(opaque);
            security::Bytes checkpoint; bool found=false;
            storage::IdentityOwnerEvidence unused;
            if (!c.outbox.initial_inventory_empty() ||
                !c.runtime.runtime_state_->inspect_initial(nullptr,checkpoint,found,unused) || found)
                return false;
            const auto report=[](void*,const durable::RetirementSnapshot& value) {
                return value.storage_epoch==1 && !value.legacy_binding_domain && value.occupancy_mask==0;
            };
            return c.runtime.durability_owner_->verify_native_zero_history(report,nullptr,0,{});
        };
        if (!runtime_state_->recover(0,empty,&context) ||
            !HubCheckpointCodec::encode(*this,checkpoint) ||
            !runtime_state_->save_checkpoint(checkpoint,0)) return false;
    }
    return true;
}

bool HubRuntime::restore_from_journal() {
    if (journal_replayed_ || state_applied_ || ingest_.size() != 0 || !journal_.persistent()) return false;
    if (runtime_state_) {
        // Fresh ledger is allowed only for a genuinely empty outbox. Existing
        // body-only installations require explicit migration, never auto-reset.
        if (!runtime_state_->recover(journal_.size()) ||
            !runtime_state_->compaction_authority_matches(
                replay_fence_ready_ ? replay_epoch_ : 0,
                replay_fence_ready_ ? replay_reference_.generation : 0,
                replay_fence_ready_ ? replay_reference_.bank : 0,
                replay_fence_ready_ ? replay_reference_.digest : security::Key32{})) {
            checkpoint_fault_=true; return false;
        }
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
        storage::IdentityDecisionAuthorityContext decision_context;
        if (runtime.runtime_state_ &&
            !runtime.runtime_state_->identity_context(event.key,ordinal,minute,&event,
                                                       &decision_context)) return false;
        if (ordinal <= runtime.applied_boundary_) return true;
        // A checkpoint permits absence only through its own boundary. Any gap
        // after that boundary leaves an uncheckpointed reducer transition
        // unprovable, so recovery must fail closed rather than skip it.
        if (ordinal != runtime.applied_boundary_ + 1U) return false;
        auto signals = runtime.apply_committed_event(event,minute);
        CloudAuthorityBinding recovered_binding;
        const CloudAuthorityBinding* binding = nullptr;
        if (decision_context.bound()) {
            recovered_binding = {decision_context.home_id,
                decision_context.hub_device_id, decision_context.ownership_epoch};
            binding = &recovered_binding;
        }
        const auto decided_at = decision_context.bound()
            ? decision_context.decided_at_utc
            : (event.received_at > 0 ? event.received_at : event.occurred_at);
        if (!runtime.append_rule_decisions(signals, decided_at, event.key.str(), binding))
            return false;
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
    // Preserve the source occurrence for chronology, but mark it unsuitable
    // as an inactivity anchor until an authenticated-time event re-establishes
    // the timer context.
    if (is_activity(event.kind) && (!activity_state_.last_activity_at ||
            event.occurred_at >= *activity_state_.last_activity_at)) {
        activity_state_.last_activity_at = event.occurred_at;
        activity_state_.last_activity_time_trusted = false;
        activity_state_.last_activity_event_id = event.key.str();
        activity_state_.inactivity_alerted = false;
    }
    return {};
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Consume one admitted event, apply privacy policy, commit and update the reducer.
// Duplicate journal identities receive an ACK without repeating reducer effects.
std::optional<ProcessResult> HubRuntime::run_state_once(
        std::optional<std::uint16_t> local_minute,
        const CloudAuthorityBinding* decision_authority) {
    GS_TRACE(gs::log::Category::Hub, "H00", "run_state_once.enter", "-");
    if (!durable_admission_open()) return std::nullopt;
    // Target rule state is scoped to the signed Home/epoch configuration that
    // initialized it. A missing or changed authority disables time-dependent
    // interpretation; raw Node events can still be durably admitted.
    if (activity_authority_binding_ && local_minute &&
        (decision_authority == nullptr ||
         !(*decision_authority == *activity_authority_binding_))) {
        local_minute.reset();
        decision_authority = nullptr;
    }
    auto event = ingest_.pop();
    if (!event) return std::nullopt;
    storage::IdentityOwnerEvidence ingress_owner;
    const auto owner_it = ingress_identity_owners_.find(event->key.str());
    if (owner_it != ingress_identity_owners_.end()) {
        ingress_owner = owner_it->second.evidence;
        ingress_identity_owners_.erase(owner_it);
    }
    // Hub receipt time is observation metadata, not a Node-authored field.
    // Keep the original durable timestamp across authenticated retries. All
    // Node payload fields still pass the exact identity digest check below.
    // No missing/reclaimed body is reconstructed or authorized by this step.
    if (ingress_owner.authenticated() && journal_.contains(event->key)) {
        struct OriginalReceipt { DomainEvent* incoming; bool found{false}; } receipt{&*event};
        if (!journal_.for_each([](void* opaque, const DomainEvent& stored) {
                auto& receipt = *static_cast<OriginalReceipt*>(opaque);
                if (stored.key.str() == receipt.incoming->key.str()) {
                    receipt.incoming->received_at = stored.received_at;
                    receipt.found = true;
                }
                return true;
            }, &receipt) || !receipt.found) {
            return ProcessResult{event->key, AckClass::Rejected, false, {}};
        }
    }
    const bool passive = is_passive_sensor_event(event->kind);
    // Identity selection happened after the original admission policy check.
    // Finish that owned native first transaction, even if configuration changed
    // while it was pending. Fresh passive evidence keeps the privacy policy;
    // reducer interpretation remains suppressed by the current mode.
    const auto* native = durability_owner_ ? durability_owner_->recovery_state() : nullptr;
    const bool initial_prepared = runtime_state_ && runtime_state_->has_prepared_identity() &&
        journal_.size()==0 && native && native->storage_epoch==1 &&
        native->checkpoint.fresh_registry_domain && native->checkpoint.registry_owner_domain;
    if (routine_.state().mode == HomeMode::Privacy && passive && !initial_prepared) {
        return ProcessResult{event->key, AckClass::DiscardedPolicy, false, {}};
    }
    bool duplicate = false;
    bool identity_already_prepared = false;
    CloudAuthorityBinding replay_binding;
    if (runtime_state_) {
        bool identity_found = false, payload_matches = false;
        std::uint64_t identity_ordinal = 0;
        std::optional<std::uint16_t> original_minute;
        storage::IdentityDecisionAuthorityContext original_decision_context;
        storage::IdentityOwnerEvidence prepared_owner;
        if (!runtime_state_->lookup_identity(*event, identity_ordinal,
                original_minute, identity_found, payload_matches,&prepared_owner,
                nullptr, &original_decision_context)) {
            checkpoint_fault_ = true;
            return ProcessResult{event->key, AckClass::Rejected, false, {}};
        }
        duplicate = journal_.contains(event->key);
        if (!identity_found && runtime_state_->has_prepared_identity())
            return ProcessResult{event->key,AckClass::Rejected,false,{}};
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
            if (prepared_owner.authenticated() &&
                (!ingress_owner.authenticated() ||
                 prepared_owner.enrollment_slot!=ingress_owner.enrollment_slot ||
                 prepared_owner.enrollment_generation!=ingress_owner.enrollment_generation ||
                 prepared_owner.binding_digest!=ingress_owner.binding_digest))
                return ProcessResult{event->key,AckClass::Rejected,false,{}};
            // A prepared identity can outlive a failed/unpublished event head.
            // Continue the same transaction so the outbox can finish publication.
            // Its original local-time context is part of the durable identity
            // row; a retry may arrive after the Hub's clock context changed.
            local_minute = original_minute;
            if (original_decision_context.bound()) {
                // A prepared event can only recreate its original publication
                // under the exact authority captured before its first commit.
                replay_binding = {original_decision_context.home_id,
                    original_decision_context.hub_device_id,
                    original_decision_context.ownership_epoch};
                decision_authority = &replay_binding;
            } else {
                decision_authority = nullptr;
            }
            identity_already_prepared = true;
        }
        // The single owner holds admission serialized through all writes below.
        // Check exact next reducer bounds, both indexes and complete immediate
        // workspace before publishing a new identity. Uncertain I/O still uses
        // the existing exact prepared retry; no identity abort/deletion is added.
        std::uint64_t workspace = 0;
        {
            security::Bytes next_checkpoint;
            storage::IdentityDecisionAuthorityContext decision_context;
            const auto decision_time = event->received_at > 0
                ? event->received_at : event->occurred_at;
            const storage::IdentityDecisionAuthorityContext* decision_context_ptr = nullptr;
            if (decision_authority != nullptr && local_minute && decision_time > 0 &&
                !decision_authority->home_id.empty() &&
                !decision_authority->hub_device_id.empty() &&
                decision_authority->ownership_epoch != 0) {
                decision_context.home_id = decision_authority->home_id;
                decision_context.hub_device_id = decision_authority->hub_device_id;
                decision_context.ownership_epoch = decision_authority->ownership_epoch;
                decision_context.decided_at_utc = decision_time;
                decision_context_ptr = &decision_context;
            }
            if (!HubCheckpointCodec::encode_after_event(*this, *event, local_minute,
                    decision_authority, next_checkpoint) || !runtime_state_->admission_workspace(*event,
                    journal_.size() + 1U, next_checkpoint.size(), workspace,
                    decision_context_ptr) ||
                !journal_.admission_ready(*event, workspace))
                return ProcessResult{event->key, AckClass::Rejected, false, {}};
        }
        storage::IdentityDecisionAuthorityContext decision_context;
        const auto decision_time = event->received_at > 0
            ? event->received_at : event->occurred_at;
        const storage::IdentityDecisionAuthorityContext* decision_context_ptr = nullptr;
        if (decision_authority != nullptr && local_minute && decision_time > 0 &&
            !decision_authority->home_id.empty() && !decision_authority->hub_device_id.empty() &&
            decision_authority->ownership_epoch != 0) {
            decision_context.home_id = decision_authority->home_id;
            decision_context.hub_device_id = decision_authority->hub_device_id;
            decision_context.ownership_epoch = decision_authority->ownership_epoch;
            decision_context.decided_at_utc = decision_time;
            decision_context_ptr = &decision_context;
        }
        if (duplicate || (!identity_already_prepared && !runtime_state_->prepare_identity(
                *event, journal_.size() + 1U, local_minute,
                ingress_owner.authenticated() ? &ingress_owner : nullptr,
                decision_context_ptr))) {
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
    const auto decision_time = event->received_at > 0
        ? event->received_at : event->occurred_at;
    if (!append_rule_decisions(signals, decision_time, event->key.str(),
                               decision_authority)) {
        checkpoint_fault_ = true;
        return ProcessResult{event->key, AckClass::Rejected, false, {}};
    }
    applied_boundary_=journal_.size();
    if (!checkpoint_state()) return ProcessResult{event->key,AckClass::Rejected,false,{}};
    return ProcessResult{event->key, AckClass::Durable, committed == CommitResult::Stored, signals};
}

bool HubRuntime::cloud_event_enrollment_generation(const DomainEvent& event,
                                                   std::uint32_t& generation) const {
    generation = 0;
    if (!runtime_state_ || !runtime_state_->healthy() || !durable_admission_open())
        return false;
    std::uint64_t ordinal = 0;
    std::optional<std::uint16_t> minute;
    bool found = false, payload_matches = false;
    storage::IdentityOwnerEvidence owner;
    if (!runtime_state_->lookup_identity(event, ordinal, minute, found,
            payload_matches, &owner) || !found || !payload_matches ||
        ordinal == 0 || !owner.authenticated()) return false;
    generation = owner.enrollment_generation;
    return generation != 0;
}

// @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
// Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
// still G06.
IncidentDecision HubRuntime::deadline(EpochSeconds now, bool clock_trusted,
        const CloudAuthorityBinding* decision_authority) {
    GS_TRACE(gs::log::Category::Hub, "H00", "deadline.enter", "-");
    if (activity_authority_binding_ &&
        (decision_authority == nullptr ||
         !(*decision_authority == *activity_authority_binding_))) {
        clock_trusted = false;
        decision_authority = nullptr;
    }
    routine_.set_coverage(coverage_.current(now));
    auto decision=routine_.deadline(now,clock_trusted);
    if (decision.create) {
        const std::vector<RuleSignalDecision> publication{{
            RuleSignalKind::MissingMorningActivity, RuleTone::Concern,
            decision.stable_key, decision.reason, 0, true, false}};
        if (!append_rule_decisions(publication, now, {}, decision_authority)) {
            checkpoint_fault_ = true;
            decision.create = false;
        }
    }
    if (!checkpoint_state()) decision.create=false;
    return decision;
}

void HubRuntime::configure_activity_rules(const ActivityRuleConfig& config) {
    if (activity_authority_binding_) {
        activity_state_ = ActivityRuleState{};
        activity_authority_binding_.reset();
    } else if (activity_rules_configured_ && !same_morning_policy(activity_config_, config))
        reset_morning_progress(activity_state_);
    activity_config_=config;
    activity_rules_configured_ = true;
    activity_config_version_ = 0;
    if(journal_replayed_) (void)checkpoint_state();
}
bool HubRuntime::configure_home_activity(const ActivityRuleConfig& config, HomeMode mode) {
    if (checkpoint_fault_ || static_cast<std::uint8_t>(mode) >
            static_cast<std::uint8_t>(HomeMode::Privacy)) return false;
    if (activity_authority_binding_) {
        // An unbound configuration cannot retain state previously established
        // under an authenticated Home authority.
        activity_state_ = ActivityRuleState{};
        activity_authority_binding_.reset();
    } else if (activity_rules_configured_ && !same_morning_policy(activity_config_, config))
        reset_morning_progress(activity_state_);
    activity_config_ = config;
    activity_rules_configured_ = true;
    activity_config_version_ = 0;
    routine_.set_mode(mode);
    return !journal_replayed_ || checkpoint_state();
}
bool HubRuntime::configure_home_activity(const ActivityRuleConfig& config, HomeMode mode,
        const CloudAuthorityBinding& authority) {
    if (checkpoint_fault_ || static_cast<std::uint8_t>(mode) >
            static_cast<std::uint8_t>(HomeMode::Privacy) || authority.home_id.empty() ||
        authority.hub_device_id.empty() || authority.ownership_epoch == 0) return false;
    const bool authority_changed = !activity_authority_binding_ ||
        !(*activity_authority_binding_ == authority);
    if (authority_changed)
        activity_state_ = ActivityRuleState{};
    else if (activity_rules_configured_ && !same_morning_policy(activity_config_, config))
        reset_morning_progress(activity_state_);
    activity_authority_binding_ = authority;
    activity_config_ = config;
    activity_rules_configured_ = true;
    activity_config_version_ = 0;
    routine_.set_mode(mode);
    return !journal_replayed_ || checkpoint_state();
}
bool HubRuntime::configure_home_activity(const ActivityRuleConfig& config,
        HomeMode mode, const CloudAuthorityBinding& authority,
        std::uint32_t version) {
    if (version == 0 || checkpoint_fault_ ||
        static_cast<std::uint8_t>(mode) > static_cast<std::uint8_t>(HomeMode::Privacy) ||
        authority.home_id.empty() || authority.hub_device_id.empty() ||
        authority.ownership_epoch == 0) return false;
    if (version < activity_config_version_) return false;
    if (version == activity_config_version_ && activity_config_version_ != 0)
        return home_activity_configuration_matches(config, mode, authority, version);
    const bool authority_changed = !activity_authority_binding_ ||
        !(*activity_authority_binding_ == authority);
    if (authority_changed) activity_state_ = ActivityRuleState{};
    else if (activity_rules_configured_ && !same_morning_policy(activity_config_, config))
        reset_morning_progress(activity_state_);
    activity_authority_binding_ = authority;
    activity_config_ = config;
    activity_rules_configured_ = true;
    activity_config_version_ = version;
    activity_timezone_.clear();
    routine_.set_mode(mode);
    return !journal_replayed_ || checkpoint_state();
}
bool HubRuntime::configure_home_activity(const ActivityRuleConfig& config,
        HomeMode mode, const CloudAuthorityBinding& authority,
        std::uint32_t version, const std::string& timezone) {
    if (version == 0 || checkpoint_fault_ || timezone.empty() || timezone.size() > 64 ||
        !std::all_of(timezone.begin(), timezone.end(), [](unsigned char ch) {
            return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
                   (ch >= '0' && ch <= '9') || ch == '/' || ch == '_' ||
                   ch == '-' || ch == '+';
        }) || static_cast<std::uint8_t>(mode) >
            static_cast<std::uint8_t>(HomeMode::Privacy) || authority.home_id.empty() ||
        authority.hub_device_id.empty() || authority.ownership_epoch == 0) return false;
    if (version < activity_config_version_) return false;
    if (version == activity_config_version_ && activity_config_version_ != 0)
        return home_activity_configuration_matches(config, mode, authority, version, timezone);
    const bool authority_changed = !activity_authority_binding_ ||
        !(*activity_authority_binding_ == authority);
    if (authority_changed || (activity_rules_configured_ &&
            (!same_morning_policy(activity_config_, config) || activity_timezone_ != timezone)))
        reset_morning_progress(activity_state_);
    activity_authority_binding_ = authority;
    activity_config_ = config;
    activity_rules_configured_ = true;
    activity_config_version_ = version;
    activity_timezone_ = timezone;
    routine_.set_mode(mode);
    return !journal_replayed_ || checkpoint_state();
}
bool HubRuntime::has_home_activity_configuration(
        const CloudAuthorityBinding& authority) const {
    return activity_rules_configured_ && activity_authority_binding_ &&
        *activity_authority_binding_ == authority;
}
bool HubRuntime::home_activity_configuration_matches(
        const ActivityRuleConfig& config, HomeMode mode,
        const CloudAuthorityBinding& authority, std::uint32_t version) const {
    return version > 0 && activity_config_version_ == version &&
        activity_rules_configured_ && activity_authority_binding_ &&
        *activity_authority_binding_ == authority && routine_.state().mode == mode &&
        same_activity_config(activity_config_, config);
}
bool HubRuntime::home_activity_configuration_matches(
        const ActivityRuleConfig& config, HomeMode mode,
        const CloudAuthorityBinding& authority, std::uint32_t version,
        const std::string& timezone) const {
    return !timezone.empty() && activity_timezone_ == timezone &&
        home_activity_configuration_matches(config, mode, authority, version);
}
void HubRuntime::set_mode(HomeMode mode) {
    routine_.set_mode(mode); if(journal_replayed_) (void)checkpoint_state();
}
void HubRuntime::start_activity_monitor(EpochSeconds at) {
    RulesCore::start_activity_monitor(activity_state_,at);
    if(journal_replayed_) (void)checkpoint_state();
}
std::vector<RuleSignalDecision> HubRuntime::activity_timers(EpochSeconds now,
        std::uint16_t local_minute, bool clock_trusted,
        const CloudAuthorityBinding* decision_authority) {
    if(checkpoint_fault_) return {};
    if (activity_authority_binding_ &&
        (decision_authority == nullptr ||
         !(*decision_authority == *activity_authority_binding_))) return {};
    const RuleEvaluationContext context{routine_.state().mode,coverage_.current(now),clock_trusted};
    auto signals=RulesCore::evaluate_activity_timers(activity_state_,activity_config_,now,local_minute,context);
    if (!append_rule_decisions(signals, now, {}, decision_authority)) {
        checkpoint_fault_ = true;
        return {};
    }
    if(!checkpoint_state()) return {};
    return signals;
}

bool HubRuntime::append_rule_decisions(const std::vector<RuleSignalDecision>& signals,
        EpochSeconds decided_at, const std::string& source_event_key,
        const CloudAuthorityBinding* authority) {
    if (signals.empty()) return true;
    // Without a current authenticated publication binding, the reducer may
    // still update its checkpoint, but no cloud intent is created. The target
    // composition supplies a binding only after trusted time and authority
    // verification; an unbound decision must never acquire a later Home.
    if (authority == nullptr) return true;
    if (authority->home_id.empty() || authority->hub_device_id.empty() ||
        authority->ownership_epoch == 0) return false;
    if (decided_at <= 0 || signals.size() > 8 || pending_rule_decisions_.size() > 32)
        return false;
    for (const auto& decision : signals) {
        if (!decision.create) continue;
        HubRuleDecisionIntent intent;
        intent.decision = decision;
        intent.decided_at = decided_at;
        // Event reducer outputs are tied to the event that drove this exact
        // transition. Timer decisions retain a source only when their stable
        // key names a source EventKey; a monitor-time anchor is not an event.
        intent.source_event_key = source_event_key;
        if (source_event_key.empty() && decision.kind == RuleSignalKind::DoorLeftOpen) {
            constexpr char prefix[] = "door-left-open:";
            if (decision.stable_key.compare(0, sizeof(prefix) - 1, prefix) == 0)
                intent.source_event_key = decision.stable_key.substr(sizeof(prefix) - 1);
        }
        intent.origin_home_id = authority->home_id;
        intent.origin_hub_device_id = authority->hub_device_id;
        intent.origin_ownership_epoch = authority->ownership_epoch;
        HubRuleDecisionRequest request{intent.decision, intent.decided_at,
                                       intent.source_event_key};
        const auto id = intent.decision_id();
        const auto body = request.json_body();
        if (id.empty() || body.empty()) return false;
        const auto existing = std::find_if(pending_rule_decisions_.begin(),
            pending_rule_decisions_.end(), [&](const HubRuleDecisionIntent& prior) {
                return prior.decision_id() == id;
            });
        if (existing != pending_rule_decisions_.end()) {
            HubRuleDecisionRequest prior{existing->decision, existing->decided_at,
                                         existing->source_event_key};
            if (prior.json_body() != body || existing->origin_home_id != intent.origin_home_id ||
                existing->origin_hub_device_id != intent.origin_hub_device_id ||
                existing->origin_ownership_epoch != intent.origin_ownership_epoch) return false;
            continue;
        }
        if (pending_rule_decisions_.size() >= 32) return false;
        pending_rule_decisions_.push_back(std::move(intent));
    }
    return true;
}

std::vector<HubRuleDecisionIntent> HubRuntime::pending_hub_rule_decisions(
        std::size_t limit) const {
    limit = std::min<std::size_t>(limit, 32);
    const auto count = std::min(limit, pending_rule_decisions_.size());
    return {pending_rule_decisions_.begin(),
            pending_rule_decisions_.begin() + static_cast<std::ptrdiff_t>(count)};
}

bool HubRuntime::acknowledge_hub_rule_decision(const HubRuleDecisionReceipt& receipt) {
    if (checkpoint_fault_ || receipt.decision_id.empty() || receipt.home_id.empty() ||
        receipt.hub_device_id.empty() || receipt.ownership_epoch == 0) return false;
    const auto found = std::find_if(pending_rule_decisions_.begin(),
        pending_rule_decisions_.end(), [&](const HubRuleDecisionIntent& intent) {
            return intent.decision_id() == receipt.decision_id && intent.origin_bound() &&
                intent.origin_home_id == receipt.home_id &&
                intent.origin_hub_device_id == receipt.hub_device_id &&
                intent.origin_ownership_epoch == receipt.ownership_epoch;
        });
    if (found == pending_rule_decisions_.end()) return false;
    pending_rule_decisions_.erase(found);
    if (!checkpoint_state()) {
        // The previous checkpoint remains authoritative. Reopen this process
        // only through recovery, which will retry the same idempotent id.
        return false;
    }
    return true;
}

}  // namespace gs::hub
