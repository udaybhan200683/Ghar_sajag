// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N02 Node radio
// @requirements E01, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The pending transmission queue owns retry timing but does not own physical RF. A caller asks next_due,
// transmits through an adapter, then reports the transport result. Only an application acknowledgement
// with the expected event identity may retire retained business data. Call this component from one owner,
// not directly from concurrent radio callbacks.

#include "radio/node_radio.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs::node {

NodeRadio::NodeRadio(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Radio, "N02", "NodeRadio.enter", "-");}

// @requirements E01, E02, NFR-04
// Retain the existing event identity for retries; report capacity refusal to the state owner.
bool NodeRadio::enqueue(const DomainEvent& event, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "enqueue.enter", "-");
    if (queue_.size() >= capacity_) {
        GS_ERROR(gs::log::Category::Radio, "N02", "enqueue.failed", "capacity_exhausted");
        return false;
    }
    queue_.push_back(PendingTx{event, 0, now_ms});
    return true;
}

// @requirements E01, E02, NFR-04
// Expose work eligible at this elapsed time; this method does not transmit a radio frame.
std::optional<DomainEvent> NodeRadio::next_due(Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "next_due.enter", "-");
    auto it = std::find_if(queue_.begin(), queue_.end(), [now_ms](const PendingTx& pending) {
        return pending.next_attempt_ms <= now_ms;
    });
    if (it == queue_.end()) return std::nullopt;
    return it->event;
}

// @requirements E01, E02, NFR-04
// Schedule retry after a radio result; transport acceptance does not prove durable application
// storage.
void NodeRadio::record_transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "record_transport_result.enter", "-");
    auto it = std::find_if(queue_.begin(), queue_.end(), [&key](const PendingTx& pending) {
        return pending.event.key.str() == key.str();
    });
    if (it == queue_.end()) return;
    const auto index = std::min(it->attempt, retry_delays_.size() - 1);
    const auto base = retry_delays_[index];
    const auto deterministic_jitter = static_cast<Milliseconds>((key.sequence * 37U) % 101U);
    it->next_attempt_ms = now_ms + base + deterministic_jitter;
    it->attempt += accepted_by_radio ? 1U : 2U;
}

// @requirements E01, E02, NFR-04
// Retire pending work only under the explicit application ACK policy; volatile receipt preserves
// business evidence.
bool NodeRadio::apply_ack(const EventKey& key, AckClass ack) {
    GS_TRACE(gs::log::Category::Radio, "N02", "apply_ack.enter", "-");
    if (ack == AckClass::Rejected) return false;
    auto it = std::find_if(queue_.begin(), queue_.end(), [&key](const PendingTx& pending) {
        return pending.event.key.str() == key.str();
    });
    if (it == queue_.end()) return false;
    if (is_business_event(it->event.kind) && ack == AckClass::ReceivedVolatile) return false;
    queue_.erase(it);
    return true;
}

}  // namespace gs::node
