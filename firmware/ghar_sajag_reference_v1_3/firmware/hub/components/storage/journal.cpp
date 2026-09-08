#include "storage/journal.hpp"
#include "gs/logging.hpp"

namespace gs::hub {

HubJournal::HubJournal(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Storage, "H02", "HubJournal.enter", "-");}

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

std::vector<DomainEvent> HubJournal::pending_cloud(std::size_t limit) const {
    GS_TRACE(gs::log::Category::Storage, "H02", "pending_cloud.enter", "-");
    std::vector<DomainEvent> result;
    for (const auto& event : records_) {
        if (!cloud_acked_.count(event.key.str())) result.push_back(event);
        if (result.size() >= limit) break;
    }
    return result;
}

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
