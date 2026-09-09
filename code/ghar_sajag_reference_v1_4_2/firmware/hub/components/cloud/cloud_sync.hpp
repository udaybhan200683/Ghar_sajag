// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H08 Hub cloud link
// @requirements F12, E02, E03, E04, E07, E10, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CloudSync asks the journal for outstanding events, orders important events and applies backoff.
// Transport-level PUBACK does not call application_commit_ack. The backend acknowledgement must mean its
// transaction has committed the event and its required effects.

#pragma once

#include "gs/domain.hpp"
#include "storage/journal.hpp"

#include <cstddef>
#include <optional>
#include <vector>

namespace gs::hub {

class CloudSync {
public:
    explicit CloudSync(HubJournal& journal);
    void set_connected(bool connected, Milliseconds now_ms);
    std::vector<DomainEvent> next_batch(Milliseconds now_ms, std::size_t limit = 16);
    // @requirements F12, E02, E03, E04, E07, E10, NFR-03
    // Retire replay responsibility only after backend application commitment for this identity.
    bool application_commit_ack(const EventKey& key);
    void record_failure(Milliseconds now_ms);
    bool connected() const { return connected_; }

private:
    HubJournal& journal_;
    bool connected_{false};
    std::size_t failures_{0};
    Milliseconds retry_after_ms_{0};
};

}  // namespace gs::hub
