#pragma once

#include "gs/domain.hpp"

#include <cstddef>
#include <deque>
#include <optional>
#include <vector>

namespace gs::node {

struct PendingTx {
    DomainEvent event;
    std::size_t attempt{0};
    Milliseconds next_attempt_ms{0};
};

class NodeRadio {
public:
    explicit NodeRadio(std::size_t capacity = 32);
    bool enqueue(const DomainEvent& event, Milliseconds now_ms);
    std::optional<DomainEvent> next_due(Milliseconds now_ms);
    void record_transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms);
    bool apply_ack(const EventKey& key, AckClass ack);
    std::size_t pending() const { return queue_.size(); }

private:
    std::size_t capacity_;
    std::deque<PendingTx> queue_;
    const std::vector<Milliseconds> retry_delays_{200, 600, 1800, 10000};
};

}  // namespace gs::node
