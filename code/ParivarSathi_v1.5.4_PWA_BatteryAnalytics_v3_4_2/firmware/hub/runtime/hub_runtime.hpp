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
#include "storage/hub_durability_owner.hpp"
#include "gs/rules.hpp"
#include "storage/runtime_state_store.hpp"
#include "storage/node_retirement_snapshot.hpp"
#include "storage/durable_event_outbox.hpp"

#include <array>
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

struct AuthenticatedNodeHealth {
    NodeHealthSnapshot snapshot;
    std::uint64_t last_seen_monotonic_ms{0};
};

enum class IdentityRetirementEligibility : std::uint8_t {
    NotEligible,
    EligibleWithDurableReplayFence
};

class HubRuntime {
public:
    HubRuntime(std::size_t ingest_capacity = 32, std::size_t journal_capacity = 1024);
    // Production scalable-storage constructor. The journal has no physical
    // record count; its bounded durable backend owns capacity accounting.
    HubRuntime(std::size_t ingest_capacity, JournalEventBackend& backend);
    // Bind the production runtime to the owner recovered during target boot.
    // While bound, event ingress and processing remain closed unless the owner
    // currently exposes a Ready state and a nonzero authoritative epoch.
    void bind_durability_owner(durable::HubDurabilityOwner& owner) {
        durability_owner_ = &owner;
    }
    bool durable_admission_open() const;
    std::optional<std::uint32_t> authoritative_storage_epoch() const;
    void authorize_node(const std::string& node_id, std::uint64_t session_id, bool required_for_routine);
    void revoke_node(const std::string& node_id);
    // The caller must first verify AEAD and physical-to-logical registry
    // mapping. Monotonic time tracks liveness without inventing epoch time.
    bool observe_authenticated_health(const NodeHealthSnapshot& health,
                                      const std::string& authenticated_node_id,
                                      std::uint64_t transport_session,
                                      std::uint64_t now_monotonic_ms);
    // Called only after exact-node, current-session authentication by the
    // security owner. Rejoin and admitted control traffic can refresh the
    // same monotonic lease without inventing a NodeHealth packet.
    bool observe_authenticated_contact(const std::string& node_id,
                                       std::uint64_t transport_session,
                                       std::uint64_t now_monotonic_ms);
    std::optional<AuthenticatedNodeHealth> node_health(const std::string& node_id) const;
    bool node_online(const std::string& node_id, std::uint64_t now_monotonic_ms) const;
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
                                              EpochSeconds hub_received_at,
                                              std::uint64_t now_monotonic_ms = 0,
                                              std::uint8_t enrollment_slot = 0xff,
                                              std::uint32_t enrollment_generation = 0,
                                              std::array<std::uint8_t, 32> owner_binding_digest = {});
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Consume one admitted event, apply privacy policy, commit and update the reducer.
    // A duplicate journal identity does not repeat reducer effects.
    std::optional<ProcessResult> run_state_once(std::optional<std::uint16_t> local_minute = std::nullopt);
    // @requirements F04, F05, F06, F07, F08, F09, F10, E03, E06, AI05, NFR-01
    // Evaluate absence only with explicit clock and coverage state; full prompt/grace orchestration is
    // still G06.
    IncidentDecision deadline(EpochSeconds now, bool clock_trusted);
    void configure_activity_rules(const ActivityRuleConfig& config);
    void set_mode(HomeMode mode);
    void start_activity_monitor(EpochSeconds at);
    std::vector<RuleSignalDecision> activity_timers(EpochSeconds now, std::uint16_t local_minute,
                                                   bool clock_trusted = true);
    const ActivityRuleState& activity_state() const { return activity_state_; }
    std::optional<NodePowerTelemetry> latest_power_telemetry(const std::string& node_id) const {
        const auto it = power_telemetry_.find(node_id);
        return it == power_telemetry_.end() ? std::nullopt : std::optional<NodePowerTelemetry>{it->second};
    }
    HubJournal& journal() { return journal_; }
    // Rebuild event-derived state once after attaching a persistent journal,
    // before processing any new event. It emits no rule signals.
    bool restore_from_journal();
    // Bind before replay. Registry authentication remains a separate authority.
    void bind_runtime_state(storage::RuntimeStateStore& store) { runtime_state_ = &store; }
    bool bind_replay_fence(const durable::RetirementSnapshot& snapshot,
                           std::uint32_t storage_epoch,
                           const durable::RetirementSnapshotReference& reference,
                           storage::DurableEventOutbox& outbox);
    IdentityRetirementEligibility identity_retirement_eligibility(
        const DomainEvent&, std::uint8_t enrollment_slot,
        std::uint32_t enrollment_generation,
        const std::array<std::uint8_t, 32>& owner_binding_digest);
    // Read-only P2-A3a plan. Retained rows are visited in source order; this
    // does not write a candidate or alter the active identity authority.
    bool plan_identity_compaction(storage::IdentityCompactionRetainedVisitor,
                                  void* visitor_context,
                                  storage::IdentityCompactionPlan&);
    bool compact_identity_generation(std::uint32_t safety_reserve_bytes,
                                     storage::IdentityCompactionPlan&);
    bool checkpoint_state();

    std::size_t ingest_depth() const { return ingest_.size(); }
    std::size_t ingest_capacity() const { return ingest_.capacity(); }
    std::size_t ingest_high_water() const { return ingest_.high_water(); }
    std::size_t ingest_rejected() const { return ingest_.rejected(); }
    const RoutineState& routine_state() const { return routine_.state(); }

private:
    struct IngressIdentityOwner {
        std::string source_id;
        storage::IdentityOwnerEvidence evidence;
    };
    IdentityRetirementEligibility identity_record_retirement_eligibility(
        const storage::IdentityCompactionRecord&);
    friend class HubCheckpointCodec;
    std::vector<RuleSignalDecision> apply_committed_event(
        const DomainEvent& event, std::optional<std::uint16_t> local_minute);
    storage::RuntimeStateStore* runtime_state_{nullptr};
    bool checkpoint_fault_{false};
    bool replay_fence_ready_{false};
    durable::RetirementSnapshot replay_snapshot_{};
    durable::RetirementSnapshotReference replay_reference_{};
    std::uint32_t replay_epoch_{0};
    std::map<std::string, IngressIdentityOwner> ingress_identity_owners_;
    std::uint64_t applied_boundary_{0};
    PeerRegistry peers_;
    IngestQueue ingest_;
    HubJournal journal_;
    CoverageTracker coverage_;
    RoutineService routine_;
    ActivityRuleConfig activity_config_{};
    ActivityRuleState activity_state_{};
    std::map<std::string, NodePowerTelemetry> power_telemetry_;
    std::map<std::string, AuthenticatedNodeHealth> node_health_;
    std::map<std::string, std::uint64_t> last_authenticated_contact_ms_;
    bool state_applied_{false};
    bool journal_replayed_{false};
    bool replay_fence_fault_{false};
    durable::HubDurabilityOwner* durability_owner_{nullptr};
};

}  // namespace gs::hub
