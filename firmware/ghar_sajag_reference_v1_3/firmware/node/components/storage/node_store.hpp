#pragma once

#include "gs/domain.hpp"

#include <cstddef>
#include <deque>
#include <optional>

namespace gs::node {

class NodeStore {
public:
    explicit NodeStore(std::size_t capacity = 64);
    bool append(const DomainEvent& event);
    bool acknowledge(const EventKey& key, AckClass ack);
    std::optional<DomainEvent> oldest() const;
    bool gap_marker_required() const { return gap_marker_required_; }
    void clear_gap_marker() { gap_marker_required_ = false; }
    std::size_t size() const { return records_.size(); }

private:
    std::size_t capacity_;
    std::deque<DomainEvent> records_;
    bool gap_marker_required_{false};
};

}  // namespace gs::node
