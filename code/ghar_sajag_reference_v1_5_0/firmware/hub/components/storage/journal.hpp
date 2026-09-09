// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H02 Hub persistence
// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// A commit result has three meanings: Stored adds a new record, Duplicate refers to an already known key,
// and Full refuses new evidence. The name journal describes intended semantics; the current deque is
// volatile. Cloud acknowledgements mark records but do not currently free capacity.

#pragma once

#include "gs/domain.hpp"

#include <cstddef>
#include <map>
#include <optional>
#include <set>
#include <vector>

namespace gs::hub {

enum class CommitResult { Stored, Duplicate, Full };

class HubJournal {
public:
    explicit HubJournal(std::size_t capacity = 1024);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Return Stored, Duplicate or Full for this event identity; this reference container is volatile, not
    // flash.
    CommitResult commit(const DomainEvent& event);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Expose records without a backend application commit ACK; a transport PUBACK is insufficient.
    std::vector<DomainEvent> pending_cloud(std::size_t limit) const;
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Mark backend commitment; current reference does not reclaim journal records or implement flash
    // compaction.
    bool acknowledge_cloud(const EventKey& key);
    bool contains(const EventKey& key) const;
    std::size_t size() const { return records_.size(); }

private:
    std::size_t capacity_;
    std::vector<DomainEvent> records_;
    std::set<std::string> ids_;
    std::set<std::string> cloud_acked_;
};

}  // namespace gs::hub
