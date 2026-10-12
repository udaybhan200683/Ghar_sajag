// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N05 Node storage
// @requirements E02, E05, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Business events are retained while ordinary heartbeats need not be journalled in the same way. A full
// store raises a gap requirement. NodeRuntime performs single-owner preflight and rollback so a record
// cannot remain here without corresponding bounded retry state.

#pragma once

#include "gs/domain.hpp"

#include <cstddef>
#include <deque>
#include <optional>
#include <vector>

namespace gs::node {

class NodeStore {
public:
    explicit NodeStore(std::size_t capacity = 32);
    // @requirements E02, E05, NFR-03
    // Retain a business event before sending it and surface capacity exhaustion instead of silently
    // dropping evidence.
    bool append(const DomainEvent& event);
    // @requirements E02, E05, NFR-03
    // Apply the explicit acknowledgement policy; resident check-in and caregiver acknowledgement remain
    // separate concepts.
    bool acknowledge(const EventKey& key, AckClass ack);
    std::optional<DomainEvent> oldest() const;
    std::vector<DomainEvent> retained_snapshot() const;
    bool gap_marker_required() const { return gap_marker_required_; }
    void clear_gap_marker() { gap_marker_required_ = false; }
    void restore_gap_marker(bool required) { gap_marker_required_ = required; }
    std::size_t size() const { return records_.size(); }
    std::size_t capacity() const { return capacity_; }

private:
    std::size_t capacity_;
    std::deque<DomainEvent> records_;
    bool gap_marker_required_{false};
};

}  // namespace gs::node
