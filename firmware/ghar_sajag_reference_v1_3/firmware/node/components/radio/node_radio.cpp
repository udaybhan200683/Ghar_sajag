#include "radio/node_radio.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs::node {

NodeRadio::NodeRadio(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Radio, "N02", "NodeRadio.enter", "-");}

bool NodeRadio::enqueue(const DomainEvent& event, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "enqueue.enter", "-");
    if (queue_.size() >= capacity_) {
        GS_ERROR(gs::log::Category::Radio, "N02", "enqueue.failed", "capacity_exhausted");
        return false;
    }
    queue_.push_back(PendingTx{event, 0, now_ms});
    return true;
}

std::optional<DomainEvent> NodeRadio::next_due(Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "next_due.enter", "-");
    auto it = std::find_if(queue_.begin(), queue_.end(), [now_ms](const PendingTx& pending) {
        return pending.next_attempt_ms <= now_ms;
    });
    if (it == queue_.end()) return std::nullopt;
    return it->event;
}

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
