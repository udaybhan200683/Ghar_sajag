// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N02 Node radio
// @requirements E01, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The pending transmission queue owns retry timing but does not own physical RF. A caller asks next_due,
// transmits through an adapter, then reports the transport result. Only an application acknowledgement
// with the expected event identity may retire retained business data. Call this component from one owner,
// not directly from concurrent radio callbacks.

#pragma once

#include "gs/domain.hpp"
#include "gs/protocol.hpp"

#include <cstddef>
#include <deque>
#include <optional>

namespace gs::node {

struct PendingTx {
    DomainEvent event;
    std::size_t attempt{0};
    Milliseconds next_attempt_ms{0};
    bool periodic_backoff_counted{false};
};

struct NodeRadioStats {
    std::uint32_t transport_results{0};
    std::uint32_t mac_success{0};
    std::uint32_t mac_failure{0};
    std::uint32_t retries{0};
    std::uint32_t periodic_backoff_entries{0};
};

class NodeRadio {
public:
    explicit NodeRadio(std::size_t capacity = 32);
    bool can_enqueue(EventKind kind) const;
    // @requirements E01, E02, NFR-04
    // Retain the existing event identity for retries; report capacity refusal to the state owner.
    bool enqueue(const DomainEvent& event, Milliseconds now_ms);
    // @requirements E01, E02, NFR-04
    // Expose work eligible at this elapsed time; this method does not transmit a radio frame.
    std::optional<DomainEvent> next_due(Milliseconds now_ms);
    // @requirements E01, E02, NFR-04
    // Schedule retry after a radio result; transport acceptance does not prove durable application
    // storage.
    void record_transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms);
    // @requirements E01, E02, NFR-04
    // Retire pending work only under the explicit application ACK policy; volatile receipt preserves
    // business evidence.
    bool apply_ack(const EventKey& key, AckClass ack);
    std::size_t pending() const { return queue_.size(); }
    std::size_t capacity() const { return capacity_; }
    std::optional<EventKey> oldest_key() const;
    const NodeRadioStats& stats() const { return stats_; }

private:
    std::size_t capacity_;
    std::deque<PendingTx> queue_;
    NodeRadioStats stats_;
    std::size_t round_robin_cursor_{0};
    Milliseconds next_radio_opportunity_ms_{0};
};

}  // namespace gs::node
