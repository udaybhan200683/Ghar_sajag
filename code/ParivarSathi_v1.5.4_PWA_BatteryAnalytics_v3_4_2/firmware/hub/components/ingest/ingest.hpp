// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H01 Hub ingest
// @requirements F05, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The callback boundary should validate and copy bounded values, then return quickly. The reference uses
// STL values and a deque, so it models the ownership rule rather than proving an allocation-free interrupt
// path. The physical frame parser must validate length, version, authentication and numeric ranges before
// constructing a DomainEvent.

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
    // @requirements F05, E02, NFR-04
    // Copy admitted event data for later state-owner processing; real frame authentication and bounds
    // precede this call.
    bool callback_copy(const DomainEvent& event, const PeerRegistry& peers);
    std::optional<DomainEvent> pop();
    std::size_t rejected() const { return rejected_; }

private:
    std::size_t capacity_;
    std::deque<DomainEvent> queue_;
    std::size_t rejected_{0};
};

}  // namespace gs::hub
