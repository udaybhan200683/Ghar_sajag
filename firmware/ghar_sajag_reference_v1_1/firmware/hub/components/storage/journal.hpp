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
    CommitResult commit(const DomainEvent& event);
    std::vector<DomainEvent> pending_cloud(std::size_t limit) const;
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
