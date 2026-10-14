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

#include <cstddef>
#include <cstdint>
#include <optional>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace gs::hub {

class HubRuntime;

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
enum class BackendReceiptResult { Completed, RetryScheduled, PermanentError, StorageFault };

class CloudBackendTransport {
public:
    virtual ~CloudBackendTransport() = default;
    // Implementations set authenticated_backend only after validating the
    // backend TLS identity and decoding an exact EventKey response.
    virtual BackendCommitReply submit(const BackendCommitRequest& request) = 0;
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

class CloudAuthoritySource {
public:
    virtual ~CloudAuthoritySource() = default;
    virtual bool current_binding(CloudAuthorityBinding& binding) = 0;
    // Must compare the durable ORIGINAL event owner with the current binding.
    // A replacement Node or a transferred Home cannot authorize old data.
    virtual bool original_event_owned(const DomainEvent& event,
                                      const CloudAuthorityBinding& binding) = 0;
};

enum class CloudWorkerState { Offline, AuthorityUnavailable, AuthorityChanged,
                              Ready, StorageFault };
struct CloudWorkerResult {
    CloudWorkerState state{CloudWorkerState::AuthorityUnavailable};
    std::size_t submitted{0};
    std::size_t completed{0};
    std::size_t refused_original{0};
};

// Call only from a separately owned, bounded network worker, never the ESP-NOW
// admission task. No target task instantiates this until its trusted authority,
// credential and owner/worker concurrency contracts exist.
class CloudSyncWorker {
public:
    CloudSyncWorker(HubJournal& journal, HubRuntime& runtime,
                    CloudAuthoritySource& authority, CloudBackendTransport& transport);
    CloudWorkerResult run_once(bool network_ready, Milliseconds now_ms,
                               std::size_t limit = 4);
private:
    bool same_authority(const CloudAuthorityBinding& expected);
    HubJournal& journal_;
    CloudSync sync_;
    CloudAuthoritySource& authority_;
    CloudBackendTransport& transport_;
    std::optional<CloudAuthorityBinding> pinned_;
    bool authority_changed_{false};
};

}  // namespace gs::hub
