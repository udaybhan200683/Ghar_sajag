#pragma once

#include "gs/domain.hpp"

#include <cstddef>
#include <deque>
#include <map>
#include <optional>
#include <string>

namespace gs::hub {

class PeerRegistry {
public:
    void authorize(const std::string& source_id, std::uint64_t session_id);
    bool accepts(const EventKey& key) const;

private:
    std::map<std::string, std::uint64_t> sessions_;
};

class IngestQueue {
public:
    explicit IngestQueue(std::size_t capacity = 32);
    bool callback_copy(const DomainEvent& event, const PeerRegistry& peers);
    std::optional<DomainEvent> pop();
    std::size_t rejected() const { return rejected_; }

private:
    std::size_t capacity_;
    std::deque<DomainEvent> queue_;
    std::size_t rejected_{0};
};

}  // namespace gs::hub
