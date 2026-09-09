// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N02 Node radio
// @requirements E01, E02, NFR-04
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The pending transmission queue owns retry timing but does not own physical RF. A caller asks next_due,
// transmits through an adapter, then reports the transport result. Only an application acknowledgement
// with the expected event identity may retire retained business data. Call this component from one owner,
// not directly from concurrent radio callbacks.

#include "node_runtime.hpp"
#include "gs/logging.hpp"

#include <utility>

namespace gs::node {

NodeRuntime::NodeRuntime(std::string node_id, std::uint64_t session_id,
                         std::size_t journal_capacity, std::size_t tx_capacity)
    : node_id_(std::move(node_id)),
      session_id_(session_id),
      store_(journal_capacity),
      radio_(tx_capacity) {
    GS_TRACE(gs::log::Category::Node, "N00", "NodeRuntime.enter", "-");}

// @requirements E01, E02, NFR-04
// Create one identity and retain before enqueue; failed enqueue can strand the stored event until a
// refill adapter is added (G05).
std::optional<EventKey> NodeRuntime::record(EventKind kind, const std::string& location,
                                            Milliseconds monotonic_ms, EpochSeconds occurred_at,
                                            std::uint32_t uncertainty_s, std::uint16_t battery_mv,
                                            bool is_test) {
    GS_TRACE(gs::log::Category::Node, "N00", "record.enter", "-");
    EventKey key{node_id_, session_id_, next_sequence_++};
    DomainEvent event{key, kind, location, monotonic_ms, occurred_at, occurred_at,
                      uncertainty_s, battery_mv, is_test};
    if (!store_.append(event)) {
        GS_ERROR(gs::log::Category::Storage, "N00", "record.failed", "node_journal_full");
        return std::nullopt;
    }
    if (!radio_.enqueue(event, monotonic_ms)) {
        GS_ERROR(gs::log::Category::Radio, "N00", "record.failed", "tx_queue_full");
        return std::nullopt;
    }
    return key;
}

// @requirements E01, E02, NFR-04
// Apply the explicit acknowledgement policy; resident check-in and caregiver acknowledgement remain
// separate concepts.
bool NodeRuntime::acknowledge(const EventKey& key, AckClass ack) {
    GS_TRACE(gs::log::Category::Node, "N00", "acknowledge.enter", "-");
    const bool radio_removed = radio_.apply_ack(key, ack);
    if (ack == AckClass::ReceivedVolatile) return radio_removed;
    const bool store_removed = store_.acknowledge(key, ack);
    return radio_removed && (store_removed || ack == AckClass::DiscardedPolicy);
}

std::optional<DomainEvent> NodeRuntime::next_transmission(Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Node, "N00", "next_transmission.enter", "-");
    return radio_.next_due(now_ms);
}

void NodeRuntime::transport_result(const EventKey& key, bool accepted_by_radio, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Node, "N00", "transport_result.enter", "-");
    radio_.record_transport_result(key, accepted_by_radio, now_ms);
}

}  // namespace gs::node
