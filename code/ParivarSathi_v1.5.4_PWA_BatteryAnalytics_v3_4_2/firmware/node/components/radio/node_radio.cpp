// Ghar Sajag traceability edition 2.0 | source release 1.5.4
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
#include <iterator>
#include <utility>

namespace gs::node {

NodeRadio::NodeRadio(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Radio, "N02", "NodeRadio.enter", "-");}

bool NodeRadio::can_enqueue(EventKind kind) const {
    if (queue_.size() >= capacity_) return false;
    // Repetitive PIR evidence cannot consume every slot. Preserve a small
    // bounded reserve for buttons, door state, privacy and gap evidence.
    const std::size_t priority_reserve = std::min<std::size_t>(4U, capacity_ / 4U);
    return kind != EventKind::Motion || queue_.size() < capacity_ - priority_reserve;
}

// @requirements E01, E02, NFR-04
// Retain the existing event identity for retries; report capacity refusal to the state owner.
bool NodeRadio::enqueue(const DomainEvent& event, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "enqueue.enter", "-");
    if (!can_enqueue(event.kind)) {
        GS_ERROR(gs::log::Category::Radio, "N02", "enqueue.failed", "capacity_exhausted");
        return false;
    }
    queue_.push_back(PendingTx{event, 0, now_ms, false});
    refresh_earliest_due();
    return true;
}

// @requirements E01, E02, NFR-04
// Expose work eligible at this elapsed time; this method does not transmit a radio frame.
std::optional<DomainEvent> NodeRadio::next_due(Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Radio, "N02", "next_due.enter", "-");
    if (queue_.empty() || now_ms < next_radio_opportunity_ms_) return std::nullopt;
    for (std::size_t offset = 0; offset < queue_.size(); ++offset) {
        const std::size_t index = (round_robin_cursor_ + offset) % queue_.size();
        if (queue_[index].next_attempt_ms <= now_ms) {
            round_robin_cursor_ = (index + 1U) % queue_.size();
            return queue_[index].event;
        }
    }
    return std::nullopt;
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
    ++stats_.transport_results;
    if (accepted_by_radio) ++stats_.mac_success;
    else ++stats_.mac_failure;
    if (it->attempt > 0U) ++stats_.retries;
    const auto index = std::min(it->attempt, NodeProtocolPolicy::retry_delays_ms.size() - 1);
    const auto base = NodeProtocolPolicy::retry_delays_ms[index];
    const auto deterministic_jitter = static_cast<Milliseconds>(
        (key.sequence * 37U) % (static_cast<std::uint64_t>(NodeProtocolPolicy::retry_jitter_max_ms) + 1U));
    it->next_attempt_ms = now_ms + base + deterministic_jitter;
    // One global opportunity gate prevents N retained events from becoming an
    // N-packet burst every backoff period while the Hub is absent.
    next_radio_opportunity_ms_ = it->next_attempt_ms;
    if (it->attempt < NodeProtocolPolicy::retry_delays_ms.size()) ++it->attempt;
    if (index == NodeProtocolPolicy::retry_delays_ms.size() - 1U &&
        !it->periodic_backoff_counted) {
        it->periodic_backoff_counted = true;
        ++stats_.periodic_backoff_entries;
    }
    refresh_earliest_due();
}

std::optional<EventKey> NodeRadio::oldest_key() const {
    if (queue_.empty()) return std::nullopt;
    return queue_.front().event.key;
}

void NodeRadio::refresh_earliest_due() {
    earliest_due_ms_.reset();
    for (const auto& item : queue_) {
        if (!earliest_due_ms_ || item.next_attempt_ms < *earliest_due_ms_)
            earliest_due_ms_ = item.next_attempt_ms;
    }
}

std::vector<PendingTx> NodeRadio::pending_snapshot() const {
    return {queue_.begin(), queue_.end()};
}

bool NodeRadio::restore_pending(const std::vector<PendingTx>& pending,
                                Milliseconds now_ms) {
    if (now_ms < 0 || !queue_.empty() || pending.size() > capacity_) return false;
    NodeRadio candidate(capacity_);
    for (const auto& saved : pending) {
        if (saved.event.key.source_id.empty() || saved.event.key.session_id == 0 ||
            saved.event.key.sequence == 0 ||
            saved.attempt > NodeProtocolPolicy::retry_delays_ms.size() ||
            !candidate.can_enqueue(saved.event.kind)) return false;
        const auto duplicate = std::any_of(candidate.queue_.begin(), candidate.queue_.end(),
            [&saved](const PendingTx& item) {
                return item.event.key.str() == saved.event.key.str();
            });
        if (duplicate) return false;
        PendingTx restored = saved;
        restored.next_attempt_ms = now_ms;
        candidate.queue_.push_back(std::move(restored));
    }
    queue_.swap(candidate.queue_);
    round_robin_cursor_ = 0;
    next_radio_opportunity_ms_ = 0;
    refresh_earliest_due();
    return true;
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
    const auto erased_index = static_cast<std::size_t>(std::distance(queue_.begin(), it));
    queue_.erase(it);
    if (queue_.empty()) round_robin_cursor_ = 0;
    else {
        if (erased_index < round_robin_cursor_ && round_robin_cursor_ > 0U) {
            --round_robin_cursor_;
        }
        round_robin_cursor_ %= queue_.size();
    }
    // A valid application retirement proves Hub progress; allow the next
    // retained identity to drain immediately rather than waiting on offline backoff.
    next_radio_opportunity_ms_ = 0;
    refresh_earliest_due();
    return true;
}

}  // namespace gs::node
