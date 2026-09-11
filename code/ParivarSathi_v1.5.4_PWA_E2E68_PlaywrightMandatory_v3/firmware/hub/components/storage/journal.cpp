// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H02 Hub persistence
// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// A commit result has three meanings: Stored adds a new record, Duplicate refers to an already known key,
// and Full refuses new evidence. The name journal describes intended semantics; the current deque is
// volatile. Cloud acknowledgements mark records but do not currently free capacity.

#include "storage/journal.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

HubJournal::HubJournal(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Storage, "H02", "HubJournal.enter", "-");}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Return Stored, Duplicate or Full for this event identity; this reference container is volatile, not
// flash.
CommitResult HubJournal::commit(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Storage, "H02", "commit.enter", "-");
    const auto id = event.key.str();
    if (ids_.count(id)) return CommitResult::Duplicate;
    if (records_.size() >= capacity_) {
        GS_ERROR(gs::log::Category::Storage, "H02", "commit.failed", "capacity_exhausted");
        return CommitResult::Full;
    }
    records_.push_back(event);
    ids_.insert(id);
    return CommitResult::Stored;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Expose records without a backend application commit ACK; a transport PUBACK is insufficient.
std::vector<DomainEvent> HubJournal::pending_cloud(std::size_t limit) const {
    GS_TRACE(gs::log::Category::Storage, "H02", "pending_cloud.enter", "-");
    std::vector<DomainEvent> result;
    for (const auto& event : records_) {
        if (!cloud_acked_.count(event.key.str())) result.push_back(event);
        if (result.size() >= limit) break;
    }
    return result;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Mark backend commitment; current reference does not reclaim journal records or implement flash
// compaction.
bool HubJournal::acknowledge_cloud(const EventKey& key) {
    GS_TRACE(gs::log::Category::Storage, "H02", "acknowledge_cloud.enter", "-");
    if (!ids_.count(key.str())) return false;
    cloud_acked_.insert(key.str());
    return true;
}

bool HubJournal::contains(const EventKey& key) const {
    GS_TRACE(gs::log::Category::Storage, "H02", "contains.enter", "-");
    return ids_.count(key.str()) > 0;
}

}  // namespace gs::hub
