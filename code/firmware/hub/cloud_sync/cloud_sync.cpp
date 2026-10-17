// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H08 Hub cloud link
// @requirements F12, E02, E03, E04, E07, E10, NFR-03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CloudSync asks the journal for outstanding events, orders important events and applies backoff.
// Transport-level PUBACK does not complete an event. The backend acknowledgement must mean its
// transaction has committed the event and its required effects.

#include "cloud_sync/cloud_sync.hpp"
#include "gs/logging.hpp"
#include "../runtime/hub_runtime.hpp"

#include <algorithm>
#include <iterator>
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

bool NodeHealthPublication::valid() const {
    constexpr auto max_integer = static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
    const auto safe_id = [](const std::string& value, std::size_t max) {
        if (value.empty() || value.size() > max) return false;
        for (unsigned char c : value)
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                  (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == ':')) return false;
        return true;
    };
    if (!safe_id(physical_node_id, 64) || !safe_id(logical_node_id, 64) ||
        node_enrollment_generation == 0 || session_id == 0 || session_id > max_integer ||
        boot_generation == 0 || boot_generation > max_integer || source_revision == 0 ||
        source_revision > max_integer || time_readiness != HubTimeReadiness::Trusted ||
        (contact_kind != NodeHealthContactKind::NodeHealth &&
         contact_kind != NodeHealthContactKind::AuthenticatedEvent) ||
        hub_received_at <= 0 || hub_snapshot_at < hub_received_at ||
        heartbeat_seconds == 0 || heartbeat_seconds > 3600 ||
        profile_id.empty()) return false;
    if (profile_id == "configured") return heartbeat_seconds == 300 && offline_seconds == 910;
    if (profile_id == "legacy_60") return heartbeat_seconds == 60 && offline_seconds == 190;
    if (profile_id == "legacy_120") return heartbeat_seconds == 120 && offline_seconds == 310;
    return false;
}

bool CloudRuntimeAuthoritySource::current_binding(CloudAuthorityBinding& binding) {
    CloudAuthorityBinding candidate;
    if (!provider_.current_binding(candidate) || candidate.home_id.empty() ||
        candidate.home_id.size() > 64 || candidate.hub_device_id.empty() ||
        candidate.hub_device_id.size() > 64 || candidate.ownership_epoch == 0) {
        clear_snapshot();
        return false;
    }
    binding = std::move(candidate);
    return true;
}

bool CloudRuntimeAuthoritySource::original_event_owned(
    const DomainEvent& event, const CloudAuthorityBinding& binding) {
    return provider_.original_event_owned(event, binding);
}

void CloudRuntimeAuthoritySource::clear_snapshot() {
    std::lock_guard<std::mutex> lock(snapshot_mutex_);
    snapshot_binding_.reset();
    snapshot_.clear();
}

bool CloudRuntimeAuthoritySource::refresh_node_health(
    const CloudAuthorityBinding& binding, const HubRuntime& runtime,
    Milliseconds now_ms) {
    CloudAuthorityBinding current;
    TrustedHubTimeSnapshot time;
    std::vector<CloudNodeEnrollment> nodes;
    if (!provider_.current_binding(current) || !(current == binding) ||
        !provider_.trusted_hub_time(now_ms, time) || !time.trusted ||
        now_ms <= 0 || time.monotonic_ms != now_ms || time.utc_now <= 0 ||
        time.boot_generation == 0 ||
        !provider_.active_nodes(binding, nodes) || nodes.size() > 10) {
        clear_snapshot();
        return false;
    }
    if (boot_generation_ != 0 && time.boot_generation < boot_generation_) {
        clear_snapshot();
        return false;
    }

    bool binding_changed = false;
    {
        std::lock_guard<std::mutex> lock(snapshot_mutex_);
        binding_changed = !snapshot_binding_ || !(*snapshot_binding_ == binding);
    }
    const bool new_boot = boot_generation_ != time.boot_generation;
    if (new_boot || binding_changed) {
        next_revision_.clear();
        round_robin_ = 0;
        last_trusted_utc_ = 0;
        boot_generation_ = time.boot_generation;
    }
    if (last_trusted_utc_ != 0 && time.utc_now < last_trusted_utc_) {
        clear_snapshot();
        return false;
    }
    last_trusted_utc_ = time.utc_now;
    const auto now_monotonic = static_cast<std::uint64_t>(now_ms);

    std::set<std::string> physical_ids;
    std::set<std::string> logical_ids;
    for (const auto& node : nodes) {
        if (node.physical_node_id.empty() || node.logical_node_id.empty() ||
            node.enrollment_generation == 0 || node.session_id == 0 ||
            !physical_ids.insert(node.physical_node_id).second ||
            !logical_ids.insert(node.logical_node_id).second) {
            clear_snapshot();
            return false;
        }
    }
    for (auto it = next_revision_.begin(); it != next_revision_.end();) {
        if (physical_ids.find(it->first) == physical_ids.end())
            it = next_revision_.erase(it);
        else
            ++it;
    }

    constexpr std::size_t kMaximumPublications = 4;
    const auto examined = nodes.size();
    std::vector<NodeHealthPublication> selected;
    selected.reserve(std::min(kMaximumPublications, nodes.size()));
    if (examined != 0) {
        const auto start = round_robin_ % examined;
        for (std::size_t offset = 0; offset < examined &&
             selected.size() < kMaximumPublications; ++offset) {
            const auto& node = nodes[(start + offset) % examined];
            const auto contact = runtime.cloud_contact(node.logical_node_id);
            if (!contact || contact->session_id != node.session_id ||
                contact->received_monotonic_ms == 0 || now_monotonic < contact->received_monotonic_ms ||
                contact->source_revision == 0) continue;
            const auto age_seconds = (now_monotonic - contact->received_monotonic_ms) / 1000U;
            if (age_seconds > static_cast<std::uint64_t>(time.utc_now)) continue;
            auto& revision = next_revision_[node.physical_node_id];
            constexpr auto max_revision = static_cast<std::uint64_t>(
                std::numeric_limits<std::int64_t>::max());
            if (revision >= max_revision) continue;
            ++revision;
            const auto received_at = time.utc_now - static_cast<EpochSeconds>(age_seconds);
            NodeHealthPublication publication{
                node.physical_node_id, node.logical_node_id,
                node.enrollment_generation, node.session_id,
                time.boot_generation, revision,
                contact->kind == CloudContactKind::NodeHealth
                    ? NodeHealthContactKind::NodeHealth
                    : NodeHealthContactKind::AuthenticatedEvent,
                node.profile_id, node.heartbeat_seconds, node.offline_seconds,
                received_at, time.utc_now, HubTimeReadiness::Trusted};
            if (publication.valid()) selected.push_back(std::move(publication));
        }
        round_robin_ = (start + std::min(kMaximumPublications, examined)) % examined;
    }
    if (!provider_.current_binding(current) || !(current == binding)) {
        clear_snapshot();
        return false;
    }
    {
        std::lock_guard<std::mutex> lock(snapshot_mutex_);
        snapshot_binding_ = binding;
        snapshot_ = std::move(selected);
    }
    return true;
}

bool CloudRuntimeAuthoritySource::current_node_health(
    const CloudAuthorityBinding& binding, const HubRuntime& runtime,
    Milliseconds now_ms, std::vector<NodeHealthPublication>& out) {
    if (!refresh_node_health(binding, runtime, now_ms)) return false;
    return latest_node_health(binding, out);
}

bool CloudRuntimeAuthoritySource::latest_node_health(
    const CloudAuthorityBinding& binding, std::vector<NodeHealthPublication>& out) {
    std::lock_guard<std::mutex> lock(snapshot_mutex_);
    if (!snapshot_binding_ || !(*snapshot_binding_ == binding)) {
        out.clear();
        return false;
    }
    out = snapshot_;
    return true;
}

std::string NodeHealthPublication::json_body(const std::string& home_id) const {
    if (!valid() || home_id.empty() || home_id.size() > 64) return {};
    for (unsigned char c : home_id)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return {};
    std::ostringstream out;
    out << "{\"home_id\":" << json_string(home_id)
        << ",\"physical_node_id\":" << json_string(physical_node_id)
        << ",\"logical_node_id\":" << json_string(logical_node_id)
        << ",\"node_enrollment_generation\":" << node_enrollment_generation
        << ",\"session_id\":" << session_id
        << ",\"boot_generation\":" << boot_generation
        << ",\"source_revision\":" << source_revision
        << ",\"contact_kind\":" << json_string(contact_kind == NodeHealthContactKind::NodeHealth
                ? "NODE_HEALTH" : "AUTHENTICATED_EVENT")
        << ",\"profile_id\":" << json_string(profile_id)
        << ",\"heartbeat_seconds\":" << heartbeat_seconds
        << ",\"offline_seconds\":" << offline_seconds
        << ",\"hub_received_at\":" << hub_received_at
        << ",\"hub_snapshot_at\":" << hub_snapshot_at << '}';
    const auto body = out.str();
    return body.size() <= 4096 ? body : std::string{};
}

std::string BackendCommitRequest::json_body() const {
    const auto& key = event.key;
    const auto* kind = kind_name(event.kind);
    if (home_id.empty() || key.physical_device_id.empty() || key.physical_device_id.size() > 64 ||
        key.source_id.empty() || key.source_id.size() > 24 || event.location.size() > 64 ||
        key.session_id == 0 || key.session_id > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) ||
        key.sequence == 0 || key.sequence > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) ||
        kind == nullptr ||
        (cloudsync_version != 1 && cloudsync_version != 2) ||
        (cloudsync_version == 2 && node_enrollment_generation == 0) ||
        (cloudsync_version == 1 && node_enrollment_generation != 0) ||
        (event.kind == EventKind::MotionSummary) != event.motion_aggregate.has_value()) return {};
    std::ostringstream out;
    out << "{";
    if (cloudsync_version == 2)
        out << "\"cloudsync_version\":2,\"node_enrollment_generation\":"
            << node_enrollment_generation << ",";
    out << "\"event_key\":{\"physical_device_id\":" << json_string(key.physical_device_id)
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

CloudSync::CloudSync(HubJournal& journal, HubRuntime& runtime)
    : journal_(journal), runtime_(&runtime) {
    GS_TRACE(gs::log::Category::Hub, "H08", "CloudSync.secure_provenance.enter", "-");
}

void CloudSync::set_connected(bool connected, Milliseconds now_ms) {
    GS_TRACE(gs::log::Category::Hub, "H08", "set_connected.enter", "-");
    if (connected && !connected_) {
        failures_ = 0;
        retry_after_ms_ = now_ms;
    }
    connected_ = connected;
}

std::vector<DomainEvent> CloudSync::next_batch(Milliseconds now_ms, std::size_t limit) {
    GS_TRACE(gs::log::Category::Hub, "H08", "next_batch.enter", "-");
    if (!connected_ || journal_.storage_fault() || now_ms < retry_after_ms_ || limit == 0)
        return {};

    limit = std::min(limit, kMaximumBatch);
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
    batch.reserve(limit);
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
        const auto index = static_cast<std::size_t>(position - selected.begin());
        if (selected.size() == state.limit) {
            if (position == selected.end()) return true;
            selected.pop_back();
        }
        selected.insert(selected.begin() + index, event);
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
    if (runtime_ != nullptr) {
        request.cloudsync_version = 2;
        if (!runtime_->cloud_event_enrollment_generation(
                event, request.node_enrollment_generation)) return std::nullopt;
    }
    if (request.json_body().empty()) return std::nullopt;
    // The caller cannot substitute new content under an existing EventKey.
    // The original journal body is the only retry/serialization authority.
    struct Match { const DomainEvent* event; bool found{false}; bool exact{false}; } match{&event};
    const auto verify = [](void* opaque, const DomainEvent& stored) {
        auto& state = *static_cast<Match*>(opaque);
        if (stored.key.str() != state.event->key.str()) return true;
        security::Bytes original, supplied;
        state.found = true;
        state.exact = HubJournal::encode_event_payload(stored, original) &&
            HubJournal::encode_event_payload(*state.event, supplied) && original == supplied;
        return true;
    };
    if (!journal_.for_each(verify, &match) || !match.found || !match.exact) return std::nullopt;
    return request;
}

void CloudSync::make_retry_room(const std::string& id) {
    if (event_failures_.count(id) || permanent_errors_.count(id)) return;
    if (retry_entries() < kMaximumRetryEntries) return;
    // Eviction only forgets a scheduling hint. Durable pending/completion state
    // remains authoritative; retrying an evicted conflict is backend-idempotent.
    if (!event_failures_.empty()) {
        event_retry_after_.erase(event_failures_.begin()->first);
        event_failures_.erase(event_failures_.begin());
    } else permanent_errors_.erase(permanent_errors_.begin());
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
        permanent_errors_.erase(id);
        return BackendReceiptResult::Completed;
    }
    if (reply.authenticated_backend && reply.key.str() == id &&
        reply.status == BackendReplyStatus::Conflict) {
        event_failures_.erase(id);
        event_retry_after_.erase(id);
        make_retry_room(id);
        permanent_errors_.insert(id);
        return BackendReceiptResult::PermanentError;
    }
    if (permanent_errors_.count(id)) return BackendReceiptResult::PermanentError;
    make_retry_room(id);
    auto& failures = event_failures_[id];
    const auto delay = backoff(failures);
    failures = std::min(failures + 1, std::size_t{4});
    event_retry_after_[id] = now_ms > std::numeric_limits<Milliseconds>::max() - delay
        ? std::numeric_limits<Milliseconds>::max() : now_ms + delay;
    return BackendReceiptResult::RetryScheduled;
}

std::size_t CloudSync::drive_batch(CloudBackendTransport& transport, const std::string& home_id,
                                   Milliseconds now_ms, std::size_t limit) {
    std::size_t processed = 0;
    for (const auto& event : next_batch(now_ms, limit)) {
        const auto request = request_for(home_id, event);
        if (!request) {
            event_failures_.erase(event.key.str());
            event_retry_after_.erase(event.key.str());
            make_retry_room(event.key.str());
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
    retry_after_ms_ = now_ms > std::numeric_limits<Milliseconds>::max() - delays[index]
        ? std::numeric_limits<Milliseconds>::max() : now_ms + delays[index];
    failures_ = std::min(failures_ + 1, std::size_t{4});
}

CloudSyncWorker::CloudSyncWorker(HubJournal& journal, HubRuntime& runtime,
                                 CloudAuthoritySource& authority,
                                 CloudBackendTransport& transport)
    : journal_(journal), runtime_(runtime), sync_(journal, runtime), authority_(authority),
      transport_(transport) {}

bool CloudSyncWorker::same_authority(const CloudAuthorityBinding& expected) {
    CloudAuthorityBinding current;
    if (!authority_.current_binding(current)) return false;
    if (!(current == expected)) {
        authority_changed_ = true;
        return false;
    }
    return true;
}

CloudWorkerResult CloudSyncWorker::run_once(bool network_ready, Milliseconds now_ms,
                                            std::size_t limit) {
    CloudWorkerResult result;
    if (journal_.storage_fault()) {
        result.state = CloudWorkerState::StorageFault;
        return result;
    }
    if (!network_ready) {
        sync_.set_connected(false, now_ms);
        result.state = CloudWorkerState::Offline;
        return result;
    }
    CloudAuthorityBinding binding;
    if (!authority_.current_binding(binding) || binding.home_id.empty() ||
        binding.hub_device_id.empty() || binding.ownership_epoch == 0) {
        sync_.set_connected(false, now_ms);
        return result;
    }
    if (authority_changed_ || (pinned_ && !(*pinned_ == binding))) {
        authority_changed_ = true;
        sync_.set_connected(false, now_ms);
        result.state = CloudWorkerState::AuthorityChanged;
        return result;
    }
    if (!pinned_) pinned_ = binding;
    sync_.set_connected(true, now_ms);
    result.state = CloudWorkerState::Ready;
    for (const auto& event : sync_.next_batch(now_ms, limit)) {
        if (!same_authority(binding)) {
            sync_.set_connected(false, now_ms);
            result.state = CloudWorkerState::AuthorityUnavailable;
            break;
        }
        if (!authority_.original_event_owned(event, binding)) {
            ++result.refused_original;
            continue;
        }
        const auto request = sync_.request_for(binding.home_id, event);
        if (!request || request->cloudsync_version != 2 ||
            request->node_enrollment_generation == 0) {
            ++result.refused_original;
            continue;
        }
        // Recheck immediately before I/O. Backend current-epoch policy is the
        // final authority if ownership changes after this snapshot.
        if (!same_authority(binding) ||
            !authority_.original_event_owned(event, binding)) {
            sync_.set_connected(false, now_ms);
            result.state = CloudWorkerState::AuthorityUnavailable;
            break;
        }
        const auto reply = transport_.submit(*request);
        ++result.submitted;
        // A response arriving after transfer/revocation cannot close the old
        // Hub's local obligation even when the server committed it earlier.
        if (!same_authority(binding) ||
            !authority_.original_event_owned(event, binding)) {
            sync_.set_connected(false, now_ms);
            result.state = CloudWorkerState::AuthorityUnavailable;
            break;
        }
        const auto outcome = sync_.handle_backend_reply(event.key, reply, now_ms);
        if (outcome == BackendReceiptResult::Completed) ++result.completed;
        if (outcome == BackendReceiptResult::StorageFault) {
            result.state = CloudWorkerState::StorageFault;
            break;
        }
    }
    // Current NodeHealth state is an additive CloudSync side channel. It is
    // supplied only by the trusted identity/time/profile adapter and has no
    // interaction with journal events, EventKeys, ACKs or Node retirement.
    std::vector<NodeHealthPublication> node_health;
    if (same_authority(binding) && authority_.current_node_health(
            binding, runtime_, now_ms, node_health)) {
        if (node_health.size() <= 4) {
            for (const auto& publication : node_health) {
                if (!publication.valid() || !same_authority(binding)) continue;
                const auto health_reply = transport_.submit_node_health(binding, publication);
                ++result.node_health_submitted;
                if (health_reply.status == NodeHealthReplyStatus::Accepted)
                    ++result.node_health_accepted;
                if (!same_authority(binding)) {
                    sync_.set_connected(false, now_ms);
                    result.state = CloudWorkerState::AuthorityUnavailable;
                    break;
                }
            }
        }
    }
    return result;
}

bool CloudSyncWorker::refresh_node_health_snapshot(Milliseconds now_ms) {
    CloudAuthorityBinding binding;
    if (!authority_.current_binding(binding) || binding.home_id.empty() ||
        binding.hub_device_id.empty() || binding.ownership_epoch == 0) return false;
    return authority_.refresh_node_health(binding, runtime_, now_ms);
}

CloudWorkerResult CloudSyncWorker::run_node_health_once(bool network_ready,
                                                         Milliseconds now_ms) {
    CloudWorkerResult result;
    if (!network_ready) {
        result.state = CloudWorkerState::Offline;
        return result;
    }
    CloudAuthorityBinding binding;
    if (!authority_.current_binding(binding) || binding.home_id.empty() ||
        binding.hub_device_id.empty() || binding.ownership_epoch == 0) {
        result.state = CloudWorkerState::AuthorityUnavailable;
        return result;
    }
    if (node_health_authority_changed_ ||
        (node_health_pinned_ && !(*node_health_pinned_ == binding))) {
        node_health_authority_changed_ = true;
        result.state = CloudWorkerState::AuthorityChanged;
        return result;
    }
    if (!node_health_pinned_) node_health_pinned_ = binding;
    result.state = CloudWorkerState::Ready;

    std::vector<NodeHealthPublication> publications;
    if (!authority_.latest_node_health(binding, publications)) return result;
    if (publications.size() > 4) return result;

    const auto still_current = [&]() {
        CloudAuthorityBinding current;
        if (!authority_.current_binding(current)) return false;
        if (!(current == binding)) {
            node_health_authority_changed_ = true;
            return false;
        }
        return true;
    };
    constexpr Milliseconds delays[] = {1000, 5000, 30000, 120000, 300000};
    for (const auto& publication : publications) {
        if (!publication.valid() || !still_current()) {
            if (node_health_authority_changed_) result.state = CloudWorkerState::AuthorityChanged;
            continue;
        }
        const auto accepted = node_health_accepted_revisions_.find(
            publication.physical_node_id);
        if (accepted != node_health_accepted_revisions_.end() &&
            accepted->second.first == publication.boot_generation &&
            accepted->second.second >= publication.source_revision) continue;
        auto& retry = node_health_retries_[publication.physical_node_id];
        if (now_ms < retry.retry_after_ms) continue;
        const auto reply = transport_.submit_node_health(binding, publication);
        ++result.node_health_submitted;
        if (reply.status == NodeHealthReplyStatus::Accepted) {
            ++result.node_health_accepted;
            node_health_retries_.erase(publication.physical_node_id);
            node_health_accepted_revisions_[publication.physical_node_id] = {
                publication.boot_generation, publication.source_revision};
        } else {
            const auto delay = delays[std::min(retry.failures, std::size(delays) - 1U)];
            if (retry.failures < std::size(delays) - 1U) ++retry.failures;
            retry.retry_after_ms = now_ms > std::numeric_limits<Milliseconds>::max() - delay
                ? std::numeric_limits<Milliseconds>::max() : now_ms + delay;
        }
        if (!still_current()) {
            result.state = node_health_authority_changed_
                ? CloudWorkerState::AuthorityChanged
                : CloudWorkerState::AuthorityUnavailable;
            break;
        }
    }
    while (node_health_retries_.size() > 10)
        node_health_retries_.erase(node_health_retries_.begin());
    while (node_health_accepted_revisions_.size() > 10)
        node_health_accepted_revisions_.erase(node_health_accepted_revisions_.begin());
    return result;
}

}  // namespace gs::hub
