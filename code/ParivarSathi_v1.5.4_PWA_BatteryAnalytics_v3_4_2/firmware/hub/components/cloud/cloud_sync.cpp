// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H08 Hub cloud link
// @requirements F12, E02, E03, E04, E07, E10, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CloudSync asks the journal for outstanding events, orders important events and applies backoff.
// Transport-level PUBACK does not complete an event. The backend acknowledgement must mean its
// transaction has committed the event and its required effects.

#include "cloud/cloud_sync.hpp"
#include "gs/logging.hpp"

#include <algorithm>
#include <limits>
#include <sstream>

namespace {
std::string json_string(const std::string& value) {
    constexpr char hex[] = "0123456789abcdef";
    std::string out = "\"";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 0x20) {
            out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15];
        } else out += static_cast<char>(c);
    }
    return out + '"';
}

const char* kind_name(gs::EventKind kind) {
    switch (kind) {
        case gs::EventKind::Motion: return "MOTION";
        case gs::EventKind::DoorOpen: return "DOOR_OPEN";
        case gs::EventKind::DoorClosed: return "DOOR_CLOSED";
        case gs::EventKind::OkPressed: return "OK_PRESSED";
        case gs::EventKind::CallFamily: return "CALL_FAMILY";
        case gs::EventKind::Heartbeat: return "HEARTBEAT";
        case gs::EventKind::PrivacyOn: return "PRIVACY_ON";
        case gs::EventKind::PrivacyOff: return "PRIVACY_OFF";
        case gs::EventKind::Gap: return "GAP";
        case gs::EventKind::MotionSummary: return "MOTION_SUMMARY";
    }
    return nullptr;
}

gs::Milliseconds backoff(std::size_t failures) {
    const gs::Milliseconds delays[] = {1000, 5000, 30000, 120000, 300000};
    return delays[std::min(failures, static_cast<std::size_t>(4))];
}

bool batch_before(const gs::DomainEvent& left, const gs::DomainEvent& right) {
    const bool left_urgent = left.kind == gs::EventKind::CallFamily;
    const bool right_urgent = right.kind == gs::EventKind::CallFamily;
    if (left_urgent != right_urgent) return left_urgent;
    return left.occurred_at < right.occurred_at;
}
}  // namespace

namespace gs::hub {

std::string BackendCommitRequest::json_body() const {
    const auto& key = event.key;
    const auto* kind = kind_name(event.kind);
    if (home_id.empty() || key.physical_device_id.empty() || key.physical_device_id.size() > 64 ||
        key.source_id.empty() || key.source_id.size() > 24 || event.location.size() > 64 ||
        key.session_id == 0 || key.session_id > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) ||
        key.sequence == 0 || key.sequence > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) ||
        kind == nullptr ||
        (event.kind == EventKind::MotionSummary) != event.motion_aggregate.has_value()) return {};
    std::ostringstream out;
    out << "{\"event_key\":{\"physical_device_id\":" << json_string(key.physical_device_id)
        << ",\"logical_node_id\":" << json_string(key.source_id)
        << ",\"origin_session_id\":" << key.session_id
        << ",\"event_sequence\":" << key.sequence
        << "},\"event_type\":" << json_string(kind)
        << ",\"occurred_at\":" << event.occurred_at
        << ",\"hub_received_at\":" << event.received_at
        << ",\"location\":" << json_string(event.location)
        << ",\"uncertainty_s\":" << event.uncertainty_s
        << ",\"is_test\":" << (event.is_test ? "true" : "false")
        << ",\"payload\":{\"sensor_type\":" << static_cast<int>(event.sensor_type)
        << ",\"battery_mv\":" << event.battery_mv
        << ",\"rssi_dbm\":" << event.rssi_dbm
        << ",\"monotonic_ms\":" << event.monotonic_ms;
    if (event.motion_aggregate) {
        const auto& aggregate = *event.motion_aggregate;
        if (!valid_motion_aggregate(aggregate)) return {};
        out << ",\"additional_count\":" << aggregate.additional_count
            << ",\"first_ms\":" << aggregate.first_ms
            << ",\"last_ms\":" << aggregate.last_ms;
    }
    out << "}}";
    return out.str();
}

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
    if (!connected_ || journal_.storage_fault() || now_ms < retry_after_ms_ || limit == 0)
        return {};

    // Scan durable storage without materializing the complete backlog. Keep
    // only the globally highest-priority `limit` events, preserving the old
    // urgent-first/occurred-time ordering and stable order for ties.
    struct BatchContext {
        CloudSync* sync;
        Milliseconds now_ms;
        std::size_t limit;
        std::vector<DomainEvent>* batch;
    } context{this, now_ms, limit, nullptr};
    std::vector<DomainEvent> batch;
    context.batch = &batch;
    const auto select = [](void* opaque, const DomainEvent& event) -> bool {
        auto& state = *static_cast<BatchContext*>(opaque);
        if (state.sync->journal_.cloud_completed(event.key)) return true;
        const auto id = event.key.str();
        const auto retry = state.sync->event_retry_after_.find(id);
        if (state.sync->permanent_errors_.count(id) != 0 ||
            (retry != state.sync->event_retry_after_.end() &&
             state.now_ms < retry->second)) return true;

        auto& selected = *state.batch;
        const auto position = std::find_if(selected.begin(), selected.end(),
            [&event](const DomainEvent& current) { return batch_before(event, current); });
        selected.insert(position, event);
        if (selected.size() > state.limit) selected.pop_back();
        return true;
    };
    if (!journal_.for_each(select, &context)) return {};
    return batch;
}

std::optional<BackendCommitRequest> CloudSync::request_for(const std::string& home_id,
                                                            const DomainEvent& event) const {
    if (journal_.storage_fault() || !journal_.contains(event.key) ||
        journal_.cloud_completed(event.key)) return std::nullopt;
    BackendCommitRequest request{home_id, event};
    if (request.json_body().empty()) return std::nullopt;
    return request;
}

BackendReceiptResult CloudSync::handle_backend_reply(const EventKey& requested,
                                                      const BackendCommitReply& reply,
                                                      Milliseconds now_ms) {
    const auto id = requested.str();
    if (journal_.storage_fault()) return BackendReceiptResult::StorageFault;
    if (!journal_.contains(requested)) return BackendReceiptResult::PermanentError;
    if (journal_.cloud_completed(requested)) return BackendReceiptResult::Completed;
    if (reply.authenticated_backend && reply.key.str() == id &&
        reply.status == BackendReplyStatus::Committed) {
        if (!journal_.acknowledge_cloud(requested)) return BackendReceiptResult::StorageFault;
        event_failures_.erase(id);
        event_retry_after_.erase(id);
        return BackendReceiptResult::Completed;
    }
    if (reply.authenticated_backend && reply.key.str() == id &&
        reply.status == BackendReplyStatus::Conflict) {
        permanent_errors_.insert(id);
        return BackendReceiptResult::PermanentError;
    }
    const auto failures = event_failures_[id]++;
    event_retry_after_[id] = now_ms + backoff(failures);
    return BackendReceiptResult::RetryScheduled;
}

std::size_t CloudSync::drive_batch(CloudBackendTransport& transport, const std::string& home_id,
                                   Milliseconds now_ms, std::size_t limit) {
    std::size_t processed = 0;
    for (const auto& event : next_batch(now_ms, limit)) {
        const auto request = request_for(home_id, event);
        if (!request) {
            permanent_errors_.insert(event.key.str());
            continue;
        }
        const auto result = handle_backend_reply(event.key, transport.submit(*request), now_ms);
        ++processed;
        if (result == BackendReceiptResult::StorageFault) break;
    }
    return processed;
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
