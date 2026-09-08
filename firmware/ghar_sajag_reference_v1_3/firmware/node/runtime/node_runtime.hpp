#pragma once

#include "gs/domain.hpp"
#include "radio/node_radio.hpp"
#include "storage/node_store.hpp"

#include <cstddef>
#include <optional>
#include <string>

namespace gs::node {

class NodeRuntime {
public:
    NodeRuntime(std::string node_id, std::uint64_t session_id,
                std::size_t journal_capacity = 64, std::size_t tx_capacity = 32);
    std::optional<EventKey> record(EventKind kind, const std::string& location,
                                   Milliseconds monotonic_ms, EpochSeconds occurred_at,
                                   std::uint32_t uncertainty_s = 0, std::uint16_t battery_mv = 0,
                                   bool is_test = false);
    bool acknowledge(const EventKey& key, AckClass ack);
    std::optional<DomainEvent> next_transmission(Milliseconds now_ms);
    void transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms);
    std::size_t persisted() const { return store_.size(); }

private:
    std::string node_id_;
    std::uint64_t session_id_;
    std::uint64_t next_sequence_{1};
    NodeStore store_;
    NodeRadio radio_;
};

}  // namespace gs::node
