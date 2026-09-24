// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N05 Node storage
// @requirements E02, E05, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Business events are retained while ordinary heartbeats need not be journalled in the same way. A full
// store raises a gap requirement. In the current composition a stored event can remain after transmit
// enqueue fails; do not retry by recording a fresh event, because that changes identity. Add a
// replay/refill path.

#include "storage/node_store.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs::node {

NodeStore::NodeStore(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Storage, "N05", "NodeStore.enter", "-");}

// @requirements E02, E05, NFR-03
// Retain a business event before sending it and surface capacity exhaustion instead of silently
// dropping evidence.
bool NodeStore::append(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Storage, "N05", "append.enter", "-");
    if (!is_business_event(event.kind)) return true;
    const auto duplicate = std::any_of(records_.begin(), records_.end(), [&event](const DomainEvent& existing) {
        return existing.key.str() == event.key.str();
    });
    if (duplicate) return true;
    if (records_.size() >= capacity_) {
        gap_marker_required_ = true;
        GS_ERROR(gs::log::Category::Storage, "N05", "append.failed", "capacity_exhausted");
        return false;
    }
    records_.push_back(event);
    return true;
}

// @requirements E02, E05, NFR-03
// Apply the explicit acknowledgement policy; resident check-in and caregiver acknowledgement remain
// separate concepts.
bool NodeStore::acknowledge(const EventKey& key, AckClass ack) {
    GS_TRACE(gs::log::Category::Storage, "N05", "acknowledge.enter", "-");
    if (ack != AckClass::Durable && ack != AckClass::DiscardedPolicy) return false;
    auto it = std::find_if(records_.begin(), records_.end(), [&key](const DomainEvent& event) {
        return event.key.str() == key.str();
    });
    if (it == records_.end()) return false;
    records_.erase(it);
    return true;
}

std::optional<DomainEvent> NodeStore::oldest() const {
    GS_TRACE(gs::log::Category::Storage, "N05", "oldest.enter", "-");
    if (records_.empty()) return std::nullopt;
    return records_.front();
}

std::vector<DomainEvent> NodeStore::retained_snapshot() const {
    return {records_.begin(), records_.end()};
}

}  // namespace gs::node
