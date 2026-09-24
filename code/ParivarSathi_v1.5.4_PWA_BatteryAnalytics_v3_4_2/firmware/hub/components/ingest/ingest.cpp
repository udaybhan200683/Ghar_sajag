// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H01 Hub ingest
// @requirements F05, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The callback boundary should validate and copy bounded values, then return quickly. The reference uses
// STL values and a deque, so it models the ownership rule rather than proving an allocation-free interrupt
// path. The physical frame parser must validate length, version, authentication and numeric ranges before
// constructing a DomainEvent.

#include "ingest/ingest.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

void PeerRegistry::authorize(const std::string& source_id, std::uint64_t session_id) {
    GS_TRACE(gs::log::Category::Hub, "H01", "authorize.enter", "-");
    sessions_[source_id] = session_id;
}

bool PeerRegistry::accepts(const EventKey& key) const {
    GS_TRACE(gs::log::Category::Hub, "H01", "accepts.enter", "-");
    const auto it = sessions_.find(key.source_id);
    return it != sessions_.end() && it->second == key.session_id && key.sequence > 0;
}

bool PeerRegistry::accepts_authenticated(const EventKey& key,
                                         const std::string& source_id,
                                         std::uint64_t transport_session) const {
    const auto it = sessions_.find(source_id);
    return it != sessions_.end() && key.source_id == source_id &&
           transport_session != 0 && it->second == transport_session &&
           key.session_id != 0 && key.session_id <= transport_session &&
           key.sequence > 0;
}

IngestQueue::IngestQueue(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Hub, "H01", "IngestQueue.enter", "-");}

// @requirements F05, E02, NFR-04
// Copy admitted event data for later state-owner processing; real frame authentication and bounds
// precede this call.
bool IngestQueue::callback_copy(const DomainEvent& event, const PeerRegistry& peers) {
    GS_TRACE(gs::log::Category::Hub, "H01", "callback_copy.enter", "-");
    if (!peers.accepts(event.key) || queue_.size() >= capacity_) {
        ++rejected_;
        GS_ERROR(gs::log::Category::Hub, "H01", "ingest.rejected",
                 queue_.size() >= capacity_ ? "ingest_queue_full" : "unauthorized_peer");
        return false;
    }
    queue_.push_back(event);
    return true;
}

bool IngestQueue::callback_copy_authenticated(const DomainEvent& event,
                                               const PeerRegistry& peers,
                                               const std::string& source_id,
                                               std::uint64_t transport_session) {
    if (!peers.accepts_authenticated(event.key, source_id, transport_session) ||
        queue_.size() >= capacity_) {
        ++rejected_;
        GS_ERROR(gs::log::Category::Hub, "H01", "ingest.rejected",
                 queue_.size() >= capacity_ ? "ingest_queue_full" : "unauthorized_peer");
        return false;
    }
    queue_.push_back(event);
    return true;
}

std::optional<DomainEvent> IngestQueue::pop() {
    GS_TRACE(gs::log::Category::Hub, "H01", "pop.enter", "-");
    if (queue_.empty()) return std::nullopt;
    DomainEvent value = queue_.front();
    queue_.pop_front();
    return value;
}

}  // namespace gs::hub
