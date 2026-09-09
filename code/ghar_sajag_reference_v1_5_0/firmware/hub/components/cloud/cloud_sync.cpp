// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H08 Hub cloud link
// @requirements F12, E02, E03, E04, E07, E10, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CloudSync asks the journal for outstanding events, orders important events and applies backoff.
// Transport-level PUBACK does not call application_commit_ack. The backend acknowledgement must mean its
// transaction has committed the event and its required effects.

#include "cloud/cloud_sync.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace gs::hub {

CloudSync::CloudSync(HubJournal& journal) : journal_(journal) {
    GS_TRACE(gs::log::Category::Hub, "H08", "CloudSync.enter", "-");}

void CloudSync::set_connected(bool connected, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Hub, "H08", "set_connected.enter", "-");
    connected_ = connected;
    if (connected) {
        failures_ = 0;
        retry_after_ms_ = now_ms;
    }
}

std::vector<DomainEvent> CloudSync::next_batch(Milliseconds now_ms, std::size_t limit) {
    GS_TRACE(gs::log::Category::Hub, "H08", "next_batch.enter", "-");
    if (!connected_ || now_ms < retry_after_ms_) return {};
    auto batch = journal_.pending_cloud(limit);
    std::stable_sort(batch.begin(), batch.end(), [](const DomainEvent& left, const DomainEvent& right) {
    GS_TRACE(gs::log::Category::Hub, "H08", "stable_sort.enter", "-");
        const bool left_urgent = left.kind == EventKind::CallFamily;
        const bool right_urgent = right.kind == EventKind::CallFamily;
        if (left_urgent != right_urgent) return left_urgent;
        return left.occurred_at < right.occurred_at;
    });
    return batch;
}

// @requirements F12, E02, E03, E04, E07, E10, NFR-03
// Retire replay responsibility only after backend application commitment for this identity.
bool CloudSync::application_commit_ack(const EventKey& key) {
    GS_TRACE(gs::log::Category::Hub, "H08", "application_commit_ack.enter", "-");
    return journal_.acknowledge_cloud(key);
}

void CloudSync::record_failure(Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Hub, "H08", "record_failure.enter", "-");
    connected_ = false;
    const Milliseconds delays[] = {1000, 5000, 30000, 120000, 300000};
    const auto index = std::min(failures_, static_cast<std::size_t>(4));
    retry_after_ms_ = now_ms + delays[index];
    ++failures_;
}

}  // namespace gs::hub
