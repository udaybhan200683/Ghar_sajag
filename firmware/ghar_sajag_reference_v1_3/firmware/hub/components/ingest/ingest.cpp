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

IngestQueue::IngestQueue(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Hub, "H01", "IngestQueue.enter", "-");}

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

std::optional<DomainEvent> IngestQueue::pop() {
    GS_TRACE(gs::log::Category::Hub, "H01", "pop.enter", "-");
    if (queue_.empty()) return std::nullopt;
    DomainEvent value = queue_.front();
    queue_.pop_front();
    return value;
}

}  // namespace gs::hub
