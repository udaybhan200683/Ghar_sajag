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
#include <optional>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace gs::hub {

struct BackendCommitRequest {
    std::string home_id;
    DomainEvent event;
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
    explicit CloudSync(HubJournal& journal);
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

private:
    HubJournal& journal_;
    bool connected_{false};
    std::size_t failures_{0};
    Milliseconds retry_after_ms_{0};
    std::map<std::string, Milliseconds> event_retry_after_;
    std::map<std::string, std::size_t> event_failures_;
    std::set<std::string> permanent_errors_;
};

}  // namespace gs::hub
