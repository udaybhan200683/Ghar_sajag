#include <chrono>
#include "cloud/http_backend_transport.hpp"
#define GS_MIXED_BODY_EMBEDDED
#include "hub_mixed_body_compaction_validation.cpp"
#undef GS_MIXED_BODY_EMBEDDED
#include <sstream>

namespace {
std::string receipt_json(const gs::EventKey& key, bool duplicate = false) {
    // Fixture IDs are ASCII, production escapes are covered separately below.
    return "{\"event_key\":{\"physical_device_id\":\"" + key.physical_device_id +
        "\",\"logical_node_id\":\"" + key.source_id + "\",\"origin_session_id\":" +
        std::to_string(key.session_id) + ",\"event_sequence\":" + std::to_string(key.sequence) +
        "},\"status\":\"COMMITTED\",\"duplicate\":" + (duplicate ? "true}" : "false}");
}
class ScriptChannel : public gs::hub::BackendHttpChannel {
public:
    gs::hub::BackendHttpResponse response;
    std::size_t calls{0};
    gs::hub::BackendHttpResponse post(const std::string& path, const std::string& body) override {
        require(path == "/v1/homes/home-1/events" && !body.empty(), "existing endpoint request");
        ++calls; return response;
    }
};
void protocol_and_bounds() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    MemorySegments flash(4U * 1024U * 1024U); auto key = storage_key();
    DurableEventOutbox outbox(flash, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty, "contract empty");
    OutboxJournalBackend backend(outbox); gs::hub::HubJournal journal;
    require(journal.attach_backend(backend), "attach segmented journal");
    for (unsigned i = 1; i <= 200; ++i) {
        gs::DomainEvent e; e.key = {"room1", 42, i, "device-room1"};
        e.kind = gs::EventKind::Motion; e.occurred_at = i; e.received_at = i + 1;
        require(journal.commit(e) == gs::hub::CommitResult::Stored, "no 128 lifetime limit");
    }
    gs::hub::CloudSync cloud(journal); cloud.set_connected(true, 0);
    auto batch = cloud.next_batch(0, 1000000);
    require(batch.size() == 16 && batch.capacity() == 16, "bounded batch staging");
    const auto request = cloud.request_for("home-1", batch.front());
    require(request.has_value(), "immutable request");
    auto changed = batch.front(); ++changed.occurred_at;
    require(!cloud.request_for("home-1", changed), "reject same-key modified source");
    ScriptChannel channel; gs::hub::HttpBackendTransport transport(channel);
    channel.response = {201, true, true, receipt_json(request->event.key)};
    require(transport.submit(*request).status == gs::hub::BackendReplyStatus::Committed,
            "exact complete authenticated COMMITTED parses");
    for (int mode = 0; mode < 14; ++mode) {
        auto response = channel.response;
        if (mode == 0) response.server_authenticated = false;
        if (mode == 1) response.message_complete = false;
        if (mode == 2) response.status = 202;
        if (mode == 3) response.status = 204;
        if (mode == 4) response.body.pop_back();
        if (mode == 5) response.body += "trailing";
        if (mode == 6) response.body = std::string(1025, 'x');
        if (mode == 7) { auto wrong = request->event.key; wrong.physical_device_id = "other"; response.body = receipt_json(wrong); }
        if (mode == 8) { auto wrong = request->event.key; ++wrong.session_id; response.body = receipt_json(wrong); }
        if (mode == 9) { auto wrong = request->event.key; ++wrong.sequence; response.body = receipt_json(wrong); }
        if (mode == 10) { auto wrong = request->event.key; wrong.source_id = "other"; response.body = receipt_json(wrong); }
        if (mode == 11) response.body.insert(1, "\"status\":\"COMMITTED\",");
        if (mode == 12) response.body.replace(response.body.find("COMMITTED"), 9, "DURABLE_MODEL");
        if (mode == 13) response.body.replace(response.body.find("\"event_sequence\":1"), 18, "\"event_sequence\":1e0");
        auto reply = gs::hub::HttpBackendTransport::decode(*request, response);
        require(reply.status != gs::hub::BackendReplyStatus::Committed && !reply.authenticated_backend,
                "invalid/unbound response never becomes receipt");
        require(cloud.handle_backend_reply(request->event.key, reply, mode) != gs::hub::BackendReceiptResult::Completed &&
                !journal.cloud_completed(request->event.key), "invalid receipt preserves pending state");
    }
    for (unsigned i = 1; i <= 200; ++i) {
        gs::EventKey pending("room1", 42, i, "device-room1");
        cloud.handle_backend_reply(pending, {}, 0);
        require(cloud.retry_entries() <= 64, "failing backlog has bounded retry memory");
    }
    require(journal.cloud_completed_count() == 0 && journal.size() == 200, "all failing events retained");
    for (unsigned i = 1; i <= 200; ++i) {
        gs::EventKey pending("room1", 42, i, "device-room1");
        cloud.handle_backend_reply(pending, {gs::hub::BackendReplyStatus::Conflict, pending, true, false}, 0);
        require(cloud.retry_entries() <= 64, "conflict quarantine bounded");
    }
    auto unicode = *request;
    unicode.event.key.physical_device_id = "device-\xc3\xa9";
    auto encoded = receipt_json(unicode.event.key);
    encoded.replace(encoded.find("\xc3\xa9"), 2, "\\u00e9");
    require(gs::hub::HttpBackendTransport::decode(unicode, {200, true, true, encoded}).authenticated_backend,
            "escaped UTF8 receipt identity is lossless");
    for (std::size_t length = 0; length < channel.response.body.size(); ++length)
        require(!gs::hub::HttpBackendTransport::decode(*request,
                    {201, true, true, channel.response.body.substr(0, length)}).authenticated_backend,
                "all response truncation boundaries fail closed");
    std::cout << "p2d_protocol=PASS invalid_receipt_modes=14 pending=200 batch_peak=16 retry_peak=64\n";
}
void completion_failure() {
    gs::host::security::OpenSslCommissioningCrypto crypto; const auto key = storage_key();
    for (bool torn : {false, true}) {
        MemorySegments flash(4U * 1024U * 1024U); DurableEventOutbox outbox(flash, crypto, key);
        require(outbox.recover() == OutboxRecovery::Empty, "receipt cut starts");
        OutboxJournalBackend backend(outbox); gs::hub::HubJournal journal;
        require(journal.attach_backend(backend), "receipt cut journal");
        gs::DomainEvent event; event.key = {"room1", 42, 1, "device-room1"};
        event.kind = gs::EventKind::Motion;
        require(journal.commit(event) == gs::hub::CommitResult::Stored, "receipt cut original");
        if (torn) flash.fail_completion_append_after(8); else flash.fail_next_completion_publication();
        gs::hub::CloudSync cloud(journal);
        gs::hub::BackendCommitRequest request{"home-1", event};
        auto reply = gs::hub::HttpBackendTransport::decode(request, {201, true, true, receipt_json(event.key)});
        require(cloud.handle_backend_reply(event.key, reply, 0) == gs::hub::BackendReceiptResult::StorageFault,
                "authenticated backend commit cannot conceal local persistence failure");
        DurableEventOutbox recovered(flash, crypto, key);
        require(recovered.recover() == OutboxRecovery::Ready, "interrupted completion recovers");
        OutboxJournalBackend recovered_backend(recovered); gs::hub::HubJournal rebooted;
        require(rebooted.attach_backend(recovered_backend), "reboot journal");
        gs::hub::CloudSync retry(rebooted);
        require(retry.handle_backend_reply(event.key, reply, 1) == gs::hub::BackendReceiptResult::Completed,
                "exact committed retry repairs completion");
        require(recovered.recover() == OutboxRecovery::Ready && recovered.backend_completed_count() == 1,
                "local completion survives another reboot");
    }
    std::cout << "p2d_completion_persistence_cuts=PASS modes=2\n";
}
class BridgeChannel : public gs::hub::BackendHttpChannel {
public:
    std::size_t calls{0}, rejected{0};
    gs::hub::BackendHttpResponse post(const std::string& path, const std::string& body) override {
        require(path == "/v1/homes/home-1/events", "bridge endpoint");
        ++calls; std::cout << body << std::endl;
        std::string metadata, json;
        require(static_cast<bool>(std::getline(std::cin, metadata)) &&
                static_cast<bool>(std::getline(std::cin, json)), "bridge response lines");
        gs::hub::BackendHttpResponse response;
        unsigned authenticated = 0, complete = 0;
        std::istringstream fields(metadata);
        require(static_cast<bool>(fields >> response.status >> authenticated >> complete), "bridge framing");
        response.server_authenticated = authenticated == 1;
        response.message_complete = complete == 1; response.body = std::move(json);
        if (!response.server_authenticated || !response.message_complete || response.status >= 400) ++rejected;
        return response;
    }
};
void durable_bridge() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key(); OutboxLimits limits;
    limits.segment_bytes = 128U * 1024U;
    PosixSegments files(4U * 1024U * 1024U); StateFiles state_files;
    DurableEventOutbox outbox(files, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "bridge starts empty");
    RuntimeStateStore state(state_files, crypto, key);
    OutboxJournalBackend backend(outbox);
    {
        gs::hub::HubRuntime runtime(32, backend); runtime.bind_runtime_state(state);
        for (unsigned slot = 0; slot < 6; ++slot) runtime.authorize_node("room" + std::to_string(slot), 42, true);
        require(runtime.restore_from_journal(), "bridge startup");
        for (unsigned sequence = 1; sequence <= 50; ++sequence) {
            for (unsigned slot = 0; slot < 6; ++slot) {
                auto message = make_message(sequence); message.node_id = "room" + std::to_string(slot);
                message.location = "location" + std::to_string(slot);
                if (sequence % 10 == 0) { message.event_type = gs::EventKind::CallFamily; message.sensor_type = gs::SensorType::Button; }
                std::array<std::uint8_t, 32> owner{}; owner.fill(static_cast<std::uint8_t>(0x31 + slot));
                require(runtime.authenticated_radio_message_callback(message, message.node_id,
                            "device-" + message.node_id, 42, 0, sequence * 1000U + 90000U, slot, 3, owner), "bridge auth admission");
                auto processed = runtime.run_state_once(static_cast<std::uint16_t>(sequence));
                require(processed && processed->ack == gs::AckClass::Durable, "bridge durable-before-ACK");
            }
        }
        gs::hub::CloudSync offline(runtime.journal());
        require(offline.next_batch(259200000, 16).empty() && outbox.backend_completed_count() == 0,
                "offline boot creates no completion");
    }
    const auto original = capture(outbox);
    require(outbox.recover() == OutboxRecovery::Ready && capture(outbox) == original, "offline reboot preserves all original bodies");
    BridgeChannel channel; gs::hub::HttpBackendTransport transport(channel);
    gs::Milliseconds now = 0;
    const auto catchup_started = std::chrono::steady_clock::now();
    const auto offline_logical = files.bytes(false);
    std::uint64_t peak_logical = offline_logical, peak_allocated = files.bytes(true);
    for (unsigned restart = 0; restart < 3; ++restart) {
        require(outbox.recover() == OutboxRecovery::Ready, "catchup reboot");
        RuntimeStateStore recovered_state(state_files, crypto, key);
        gs::hub::HubRuntime runtime(32, backend); runtime.bind_runtime_state(recovered_state);
        require(runtime.restore_from_journal(), "catchup checkpoints");
        gs::hub::CloudSync cloud(runtime.journal()); cloud.set_connected(true, now);
        for (unsigned attempt = 0; attempt < 100 && outbox.backend_completed_count() < (restart + 1) * 100; ++attempt) {
            cloud.drive_batch(transport, "home-1", now, 4);
            now += 300001;
            peak_logical = std::max(peak_logical, files.bytes(false));
            peak_allocated = std::max(peak_allocated, files.bytes(true));
            require(cloud.retry_entries() <= 64 && capture(outbox) == original, "partial catchup preserves every body");
        }
        require(outbox.backend_completed_count() >= (restart + 1) * 100, "partial progress before restart");
    }
    require(outbox.backend_completed_count() == 300 && capture(outbox) == original, "all commits recovered without deletion");
    const auto before = files.bytes(true);
    require(outbox.recover() == OutboxRecovery::Ready && outbox.backend_completed_count() == 300, "local completion survives reboot");
    std::cout << "RESULT p2d_bridge=PASS events=300 completed=300 pending=0 requests=" << channel.calls
              << " rejected=" << channel.rejected << " logical_bytes=" << files.bytes(false)
              << " allocated_bytes=" << before << " identity_logical_bytes=" << state.identity_bytes()
              << " offline_logical_bytes=" << offline_logical
              << " peak_logical_bytes=" << peak_logical << " peak_allocated_bytes=" << peak_allocated
              << " catchup_ms=" << std::chrono::duration_cast<std::chrono::milliseconds>(
                     std::chrono::steady_clock::now() - catchup_started).count()
              << " configured_reserve=" << limits.protected_capacity_bytes << "\n" << std::flush;
}
}
int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--bridge") durable_bridge();
        else { protocol_and_bounds(); completion_failure(); }
        return 0;
    } catch (const std::exception& error) { std::cerr << "p2d_cloud_contract_validation=FAIL " << error.what() << '\n'; return 1; }
}
