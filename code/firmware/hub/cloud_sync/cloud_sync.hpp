// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H08 Hub cloud link
// @requirements F12, E02, E03, E04, E07, E10, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CloudSync asks the journal for outstanding events, orders important events and applies backoff.
// Transport-level PUBACK does not complete an event. The backend acknowledgement must mean its
// transaction has committed the event and its required effects.

#pragma once

#include "gs/domain.hpp"
#include "storage/journal.hpp"
#include "gs/rules.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <vector>

namespace gs::hub {

class HubRuntime;
struct CloudAuthorityBinding;
struct HubRuleDecisionRequest;
struct HubRuleDecisionReply;

struct BackendCommitRequest {
    std::string home_id;
    DomainEvent event;
    std::uint32_t cloudsync_version{1};
    std::uint32_t node_enrollment_generation{0};
    // Deterministic JSON for POST /v1/homes/{home_id}/events.
    std::string json_body() const;
};

enum class BackendReplyStatus { Committed, Conflict, TransientFailure, AuthenticationFailure,
                                NetworkFailure, InvalidResponse };
struct BackendCommitReply {
    BackendReplyStatus status{BackendReplyStatus::InvalidResponse};
    EventKey key;
    bool authenticated_backend{false};
    bool duplicate{false};
};
enum class HubTimeReadiness : std::uint8_t { Untrusted, Trusted };
enum class NodeHealthContactKind : std::uint8_t { NodeHealth, AuthenticatedEvent };
struct NodeHealthPublication {
    std::string physical_node_id;
    std::string logical_node_id;
    std::uint32_t node_enrollment_generation{0};
    std::uint64_t session_id{0};
    std::uint64_t boot_generation{0};
    std::uint64_t source_revision{0};
    NodeHealthContactKind contact_kind{NodeHealthContactKind::NodeHealth};
    std::string profile_id;
    std::uint32_t heartbeat_seconds{0};
    std::uint32_t offline_seconds{0};
    EpochSeconds hub_received_at{0};
    EpochSeconds hub_snapshot_at{0};
    HubTimeReadiness time_readiness{HubTimeReadiness::Untrusted};
    std::string json_body(const std::string& home_id) const;
    bool valid() const;
};
enum class NodeHealthReplyStatus : std::uint8_t { Accepted, TransientFailure, AuthenticationFailure, InvalidResponse };
struct NodeHealthReply {
    NodeHealthReplyStatus status{NodeHealthReplyStatus::InvalidResponse};
};
enum class BackendReceiptResult { Completed, RetryScheduled, PermanentError, StorageFault };

class CloudBackendTransport {
public:
    virtual ~CloudBackendTransport() = default;
    // Implementations set authenticated_backend only after validating the
    // backend TLS identity and decoding an exact EventKey response.
    virtual BackendCommitReply submit(const BackendCommitRequest& request) = 0;
    // Additive current-state channel; it never produces EventKeys or durable ACKs.
    virtual NodeHealthReply submit_node_health(const CloudAuthorityBinding&,
                                               const NodeHealthPublication&) {
        return {};
    }
    virtual HubRuleDecisionReply submit_hub_rule_decision(
        const CloudAuthorityBinding&, const HubRuleDecisionRequest&);
};

struct CloudNodeEnrollment {
    std::string physical_node_id;
    std::string logical_node_id;
    std::uint32_t enrollment_generation{0};
    std::uint64_t session_id{0};
    std::string profile_id;
    std::uint32_t heartbeat_seconds{0};
    std::uint32_t offline_seconds{0};
};

struct TrustedHubTimeSnapshot {
    bool trusted{false};
    Milliseconds monotonic_ms{0};
    EpochSeconds utc_now{0};
    std::uint64_t boot_generation{0};
};

// Implemented by the approved GS-109/GS-68 authority and Hub registry
// adapters. TEST_ONLY providers are confined to deterministic host fixtures.
class CloudRuntimeAuthorityProvider {
public:
    virtual ~CloudRuntimeAuthorityProvider() = default;
    // CloudSyncWorker rechecks this on its network task before and after
    // publication. Implementations must be thread-safe and return false when
    // current ownership, revocation, or epoch proof is unavailable.
    virtual bool current_binding(CloudAuthorityBinding& binding) = 0;
    virtual bool original_event_owned(const DomainEvent& event,
                                     const CloudAuthorityBinding& binding) = 0;
    virtual bool trusted_hub_time(Milliseconds monotonic_ms,
                                  TrustedHubTimeSnapshot& time) = 0;
    virtual bool active_nodes(const CloudAuthorityBinding& binding,
                              std::vector<CloudNodeEnrollment>& nodes) = 0;
};

class CloudSync {
public:
    static constexpr std::size_t kMaximumBatch = 16;
    static constexpr std::size_t kMaximumRetryEntries = 64;
    explicit CloudSync(HubJournal& journal);
    // Secure CloudSync uses the Hub's encrypted original-owner identity ledger.
    // If provenance is absent/corrupt, this path refuses to build a request.
    CloudSync(HubJournal& journal, HubRuntime& runtime);
    void set_connected(bool connected, Milliseconds now_ms);
    std::vector<DomainEvent> next_batch(Milliseconds now_ms, std::size_t limit = 16);
    std::optional<BackendCommitRequest> request_for(const std::string& home_id,
                                                     const DomainEvent& event) const;
    BackendReceiptResult handle_backend_reply(const EventKey& requested,
                                               const BackendCommitReply& reply,
                                               Milliseconds now_ms);
    std::size_t drive_batch(CloudBackendTransport& transport, const std::string& home_id,
                            Milliseconds now_ms, std::size_t limit = 16);
    void record_failure(Milliseconds now_ms);
    bool connected() const { return connected_; }
    std::size_t retry_entries() const { return event_failures_.size() + permanent_errors_.size(); }

private:
    void make_retry_room(const std::string& id);
    HubJournal& journal_;
    HubRuntime* runtime_{nullptr};
    bool connected_{false};
    std::size_t failures_{0};
    Milliseconds retry_after_ms_{0};
    std::map<std::string, Milliseconds> event_retry_after_;
    std::map<std::string, std::size_t> event_failures_;
    std::set<std::string> permanent_errors_;
};

// Only a trusted installation/credential owner may supply this capability.
// The commercial S3 runtime has no such source until GS-109 issuance and
// ownership binding are defined. In particular a Home ID, MAC or HTTP header
// alone is not an authority to upload old durable events.
struct CloudAuthorityBinding {
    std::string home_id;
    std::string hub_device_id;
    std::uint64_t ownership_epoch{0};
    bool operator==(const CloudAuthorityBinding& other) const {
        return home_id == other.home_id && hub_device_id == other.hub_device_id &&
               ownership_epoch == other.ownership_epoch;
    }
};

// Hub rule decisions have their own identity and receipt. They are never
// serialized into DomainEvent or assigned a Node EventKey.
struct HubRuleDecisionRequest {
    RuleSignalDecision decision;
    EpochSeconds decided_at{0};
    std::string source_event_key;
    std::string decision_id() const;
    std::string json_body() const;
};
enum class HubRuleDecisionReplyStatus : std::uint8_t {
    Committed, Conflict, TransientFailure, AuthenticationFailure, InvalidResponse
};
struct HubRuleDecisionReply {
    HubRuleDecisionReplyStatus status{HubRuleDecisionReplyStatus::InvalidResponse};
    bool duplicate{false};
};

struct HubRuleDecisionIntent {
    RuleSignalDecision decision;
    EpochSeconds decided_at{0};
    std::string source_event_key;
    std::string origin_home_id;
    std::string origin_hub_device_id;
    std::uint64_t origin_ownership_epoch{0};
    std::string decision_id() const;
    bool origin_bound() const {
        return !origin_home_id.empty() && !origin_hub_device_id.empty() &&
               origin_ownership_epoch != 0;
    }
    CloudAuthorityBinding origin_binding() const;
};

struct HubRuleDecisionReceipt {
    std::string decision_id;
    std::string home_id;
    std::string hub_device_id;
    std::uint64_t ownership_epoch{0};
};

class CloudAuthoritySource {
public:
    virtual ~CloudAuthoritySource() = default;
    virtual bool current_binding(CloudAuthorityBinding& binding) = 0;
    // Must compare the durable ORIGINAL event owner with the current binding.
    // A replacement Node or a transferred Home cannot authorize old data.
    virtual bool original_event_owned(const DomainEvent& event,
                                      const CloudAuthorityBinding& binding) = 0;
    // Only an approved owner/time/profile adapter may create these records.
    // False or empty keeps status publication disabled without affecting events.
    virtual bool current_node_health(const CloudAuthorityBinding&,
                                     const HubRuntime&, Milliseconds,
                                     std::vector<NodeHealthPublication>&) { return false; }
    // Called by the HubRuntime owner task. Implementations copy bounded,
    // immutable snapshots for the separate network worker to consume.
    virtual bool refresh_node_health(const CloudAuthorityBinding&,
                                     const HubRuntime&, Milliseconds) { return false; }
    virtual bool latest_node_health(const CloudAuthorityBinding&,
                                    std::vector<NodeHealthPublication>&) { return false; }
};

class CloudRuntimeAuthoritySource final : public CloudAuthoritySource {
public:
    explicit CloudRuntimeAuthoritySource(CloudRuntimeAuthorityProvider& provider)
        : provider_(provider) {}
    bool current_binding(CloudAuthorityBinding& binding) override;
    bool original_event_owned(const DomainEvent& event,
                              const CloudAuthorityBinding& binding) override;
    bool current_node_health(const CloudAuthorityBinding& binding,
                             const HubRuntime& runtime, Milliseconds now_ms,
                             std::vector<NodeHealthPublication>& out) override;
    bool refresh_node_health(const CloudAuthorityBinding& binding,
                             const HubRuntime& runtime, Milliseconds now_ms) override;
    bool latest_node_health(const CloudAuthorityBinding& binding,
                            std::vector<NodeHealthPublication>& out) override;
private:
    void clear_snapshot();
    CloudRuntimeAuthorityProvider& provider_;
    std::mutex snapshot_mutex_;
    std::optional<CloudAuthorityBinding> snapshot_binding_;
    std::vector<NodeHealthPublication> snapshot_;
    std::map<std::string, std::uint64_t> next_revision_;
    std::uint64_t boot_generation_{0};
    EpochSeconds last_trusted_utc_{0};
    std::size_t round_robin_{0};
};

enum class CloudWorkerState { Offline, AuthorityUnavailable, AuthorityChanged,
                              Ready, StorageFault };
struct CloudWorkerResult {
    CloudWorkerState state{CloudWorkerState::AuthorityUnavailable};
    std::size_t submitted{0};
    std::size_t completed{0};
    std::size_t refused_original{0};
    std::size_t node_health_submitted{0};
    std::size_t node_health_accepted{0};
};

// Call only from a separately owned, bounded network worker, never the ESP-NOW
// admission task. No target task instantiates this until its trusted authority,
// credential and owner/worker concurrency contracts exist.
class CloudSyncWorker {
public:
    CloudSyncWorker(HubJournal& journal, HubRuntime& runtime,
                    CloudAuthoritySource& authority, CloudBackendTransport& transport);
    CloudWorkerResult run_once(bool network_ready, Milliseconds now_ms,
                               std::size_t limit = 4,
                               bool include_live_node_health = true);
    // Split owner-thread capture from bounded network I/O. The capture method
    // never sends; the network method never reads HubRuntime or the journal.
    bool refresh_node_health_snapshot(Milliseconds now_ms);
    CloudWorkerResult run_node_health_once(bool network_ready, Milliseconds now_ms);
    // Owner-task snapshot and receipt handoff keep the network worker away from
    // mutable HubRuntime and checkpoint state.
    bool refresh_hub_rule_decision_snapshot();
    CloudWorkerResult run_hub_rule_decision_once(bool network_ready,
                                                  Milliseconds now_ms,
                                                  std::size_t limit = 2);
    bool take_hub_rule_decision_receipts(std::vector<HubRuleDecisionReceipt>& out);
    void finish_hub_rule_decision_receipt(const HubRuleDecisionReceipt& receipt,
                                          bool checkpointed);
private:
    bool same_authority(const CloudAuthorityBinding& expected);
    HubJournal& journal_;
    HubRuntime& runtime_;
    CloudSync sync_;
    CloudAuthoritySource& authority_;
    CloudBackendTransport& transport_;
    std::optional<CloudAuthorityBinding> pinned_;
    bool authority_changed_{false};
    std::optional<CloudAuthorityBinding> node_health_pinned_;
    bool node_health_authority_changed_{false};
    struct HealthRetry { std::size_t failures{0}; Milliseconds retry_after_ms{0}; };
    std::map<std::string, HealthRetry> node_health_retries_;
    std::map<std::string, std::pair<std::uint64_t, std::uint64_t>>
        node_health_accepted_revisions_;
    mutable std::mutex rule_decision_mutex_;
    std::vector<HubRuleDecisionIntent> rule_decision_snapshot_;
    std::vector<HubRuleDecisionReceipt> rule_decision_receipts_;
    std::map<std::string, HealthRetry> rule_decision_retries_;
    std::set<std::string> rule_decision_receipts_waiting_owner_;
    std::optional<CloudAuthorityBinding> rule_decision_pinned_;
    bool rule_decision_authority_changed_{false};
};

}  // namespace gs::hub
