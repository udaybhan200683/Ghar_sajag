#include "storage/node_store.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs::node {

NodeStore::NodeStore(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Storage, "N05", "NodeStore.enter", "-");}

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

}  // namespace gs::node
