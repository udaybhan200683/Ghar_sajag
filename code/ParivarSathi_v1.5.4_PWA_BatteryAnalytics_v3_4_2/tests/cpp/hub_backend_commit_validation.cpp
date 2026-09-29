#include "firmware/hub/components/cloud/cloud_sync.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <array>
#include <cstdlib>
#include <iostream>
#include <stdexcept>

namespace {
using gs::security::Bytes;
using gs::hub::BackendCommitReply;
using gs::hub::BackendReceiptResult;
using gs::hub::BackendReplyStatus;
using gs::hub::CloudSync;
using gs::hub::HubJournal;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

struct Slots final : gs::hub::JournalSlotStore {
    std::array<Bytes, 128> events{};
    std::array<Bytes, 128> completions{};
    unsigned completion_writes{0};
    bool fail_completion{false};
    bool read(std::size_t slot, Bytes& blob, bool& found) override {
        blob = events.at(slot); found = !blob.empty(); return true;
    }
    bool write(std::size_t slot, const Bytes& blob) override {
        if (!events.at(slot).empty()) return false;
        events[slot] = blob; return true;
    }
    bool read_completion(std::size_t slot, Bytes& blob, bool& found) override {
        blob = completions.at(slot); found = !blob.empty(); return true;
    }
    bool write_completion(std::size_t slot, const Bytes& blob) override {
        if (fail_completion || !completions.at(slot).empty()) return false;
        completions[slot] = blob; ++completion_writes; return true;
    }
};

struct ScriptTransport final : gs::hub::CloudBackendTransport {
    unsigned submissions{0};
    BackendCommitReply submit(const gs::hub::BackendCommitRequest& request) override {
        ++submissions;
        require(!request.json_body().empty(), "transport received invalid request");
        if (request.event.key.physical_device_id == "device-A")
            return {BackendReplyStatus::NetworkFailure, request.event.key, false, false};
        return {BackendReplyStatus::Committed, request.event.key, true, false};
    }
};

gs::DomainEvent event(const char* device, std::uint64_t session, std::uint64_t seq) {
    gs::DomainEvent value;
    value.key = {"room-1", session, seq, device};
    value.kind = gs::EventKind::CallFamily;
    value.location = "Kitchen";
    value.occurred_at = 100;
    value.received_at = 101;
    value.sensor_type = gs::SensorType::Button;
    return value;
}

BackendCommitReply reply(const gs::EventKey& key, BackendReplyStatus status,
                         bool authenticated = true, bool duplicate = false) {
    return {status, key, authenticated, duplicate};
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--emit") {
            const gs::hub::BackendCommitRequest request{"home-1", event("device-A", 17, 1)};
            std::cout << request.json_body() << '\n';
            return EXIT_SUCCESS;
        }
        if (argc == 2 && std::string(argv[1]) == "--bridge") {
            gs::host::security::OpenSslCommissioningCrypto bridge_crypto;
            gs::security::Key32 bridge_key{};
            require(bridge_crypto.random_bytes(bridge_key.data(), bridge_key.size()), "bridge key");
            Slots bridge_slots;
            const auto item = event("device-A", 17, 1);
            std::string instruction;
            {
                HubJournal hub(128);
                require(hub.attach_persistence(bridge_crypto, bridge_slots, bridge_key) &&
                        hub.commit(item) == gs::hub::CommitResult::Stored, "bridge event journaled");
                CloudSync cloud(hub);
                cloud.set_connected(true, 0);
                const auto request = cloud.request_for("home-1", item);
                require(request.has_value(), "bridge first request");
                std::cout << request->json_body() << std::endl;
                require(static_cast<bool>(std::getline(std::cin, instruction)) && instruction == "LOST",
                        "bridge first response must be lost");
                require(!hub.cloud_completed(item.key), "lost response recorded completion");
            }
            {
                HubJournal rebooted(128);
                require(rebooted.attach_persistence(bridge_crypto, bridge_slots, bridge_key) &&
                        rebooted.pending_cloud(16).size() == 1, "bridge restart pending");
                CloudSync cloud(rebooted);
                cloud.set_connected(true, 0);
                const auto request = cloud.request_for("home-1", item);
                require(request.has_value(), "bridge retry request");
                std::cout << request->json_body() << std::endl;
                require(static_cast<bool>(std::getline(std::cin, instruction)) &&
                        instruction == "AUTHENTICATED_COMMITTED_DUPLICATE",
                        "bridge duplicate backend response");
                require(cloud.handle_backend_reply(item.key,
                        reply(item.key, BackendReplyStatus::Committed, true, true), 0) ==
                        BackendReceiptResult::Completed && bridge_slots.completion_writes == 1,
                        "bridge completion receipt");
            }
            HubJournal final_hub(128);
            require(final_hub.attach_persistence(bridge_crypto, bridge_slots, bridge_key) &&
                    final_hub.pending_cloud(16).empty(), "bridge final restart completion");
            std::cout << "COMPLETED_AFTER_RESTART" << std::endl;
            return EXIT_SUCCESS;
        }
        gs::host::security::OpenSslCommissioningCrypto crypto;
        gs::security::Key32 key{};
        require(crypto.random_bytes(key.data(), key.size()), "test key");
        Slots slots;
        auto a = event("device-A", 17, 1);
        auto b = event("device-B", 17, 1);
        {
            HubJournal hub(128);
            require(hub.attach_persistence(crypto, slots, key), "empty restore");
            require(hub.commit(a) == gs::hub::CommitResult::Stored, "first event");
            require(hub.commit(b) == gs::hub::CommitResult::Stored, "second node event");
            CloudSync cloud(hub);
            cloud.set_connected(true, 0);
            const auto request = cloud.request_for("home-1", a);
            require(request.has_value() &&
                    request->json_body().find("\"physical_device_id\":\"device-A\"") != std::string::npos &&
                    request->json_body().find("\"origin_session_id\":17") != std::string::npos,
                    "canonical request mapping");
            require(cloud.next_batch(0, 16).size() == 2, "both nodes pending");
            require(cloud.handle_backend_reply(a.key, reply(a.key, BackendReplyStatus::NetworkFailure, false), 0) ==
                    BackendReceiptResult::RetryScheduled, "lost response remains pending");
            require(slots.completion_writes == 0, "network retry wrote NVS");
            require(cloud.next_batch(1, 16).size() == 1 &&
                    cloud.next_batch(1, 16).front().key.str() == b.key.str(),
                    "failed Node does not starve other Node");
            require(cloud.handle_backend_reply(b.key, reply(b.key, BackendReplyStatus::Committed), 1) ==
                    BackendReceiptResult::Completed, "second Node committed");
            require(slots.completion_writes == 1, "one durable completion write");
            require(cloud.handle_backend_reply(b.key, reply(b.key, BackendReplyStatus::Committed), 2) ==
                    BackendReceiptResult::Completed && slots.completion_writes == 1,
                    "duplicate COMMITTED wrote no receipt");
        }
        {
            HubJournal restarted(128);
            require(restarted.attach_persistence(crypto, slots, key), "restore after in-flight request");
            require(restarted.cloud_completed(b.key) && !restarted.cloud_completed(a.key),
                    "completion restored without losing pending event");
            CloudSync cloud(restarted);
            cloud.set_connected(true, 0);
            require(cloud.next_batch(0, 16).size() == 1, "confirmed event not resent");
            require(cloud.handle_backend_reply(a.key,
                    reply(a.key, BackendReplyStatus::Committed, true, true), 0) ==
                    BackendReceiptResult::Completed, "lost response duplicate committed");
            require(slots.completion_writes == 2 && cloud.next_batch(0, 16).empty(),
                    "lost response completion durable");
        }
        {
            HubJournal restarted(128);
            require(restarted.attach_persistence(crypto, slots, key) &&
                    restarted.cloud_completed(a.key) && restarted.cloud_completed(b.key) &&
                    restarted.pending_cloud(16).empty(), "both completions survive reboot");
        }
        Slots before_send;
        {
            HubJournal hub(128);
            require(hub.attach_persistence(crypto, before_send, key) &&
                    hub.commit(a) == gs::hub::CommitResult::Stored,
                    "pre-send journal commit");
        }
        {
            HubJournal rebooted(128);
            require(rebooted.attach_persistence(crypto, before_send, key) &&
                    rebooted.pending_cloud(16).size() == 1,
                    "restart before send preserves pending event");
            CloudSync cloud(rebooted);
            cloud.set_connected(true, 0);
            require(cloud.handle_backend_reply(a.key,
                    reply(a.key, BackendReplyStatus::InvalidResponse), 0) ==
                    BackendReceiptResult::RetryScheduled && before_send.completion_writes == 0,
                    "invalid backend response cannot complete");
        }
        Slots tampered = slots;
        tampered.completions[0][0] ^= 1;
        HubJournal corrupt(128);
        require(!corrupt.attach_persistence(crypto, tampered, key) && corrupt.storage_fault(),
                "tampered completion fails restore closed");
        Slots failed;
        {
            HubJournal hub(128);
            require(hub.attach_persistence(crypto, failed, key) &&
                    hub.commit(a) == gs::hub::CommitResult::Stored &&
                    hub.commit(b) == gs::hub::CommitResult::Stored, "failure setup");
            CloudSync cloud(hub);
            cloud.set_connected(true, 0);
            require(cloud.handle_backend_reply(a.key, reply(a.key, BackendReplyStatus::Conflict), 0) ==
                    BackendReceiptResult::PermanentError && !hub.cloud_completed(a.key),
                    "conflict never completes");
            require(cloud.next_batch(0, 16).size() == 1, "conflict does not starve second Node");
            require(cloud.handle_backend_reply(b.key,
                    reply(b.key, BackendReplyStatus::Committed, false), 1) ==
                    BackendReceiptResult::RetryScheduled && failed.completion_writes == 0,
                    "unauthenticated response ignored");
            require(cloud.handle_backend_reply(b.key,
                    reply(b.key, BackendReplyStatus::AuthenticationFailure), 2) ==
                    BackendReceiptResult::RetryScheduled, "authentication failure explicit");
            require(cloud.handle_backend_reply(b.key,
                    reply(b.key, BackendReplyStatus::TransientFailure), 3) ==
                    BackendReceiptResult::RetryScheduled, "transient failure backed off");
            failed.fail_completion = true;
            require(cloud.handle_backend_reply(b.key,
                    reply(b.key, BackendReplyStatus::Committed), 4) ==
                    BackendReceiptResult::StorageFault && hub.storage_fault(),
                    "receipt storage fault cannot become completion");
        }
        Slots driven;
        {
            HubJournal hub(128);
            require(hub.attach_persistence(crypto, driven, key) &&
                    hub.commit(a) == gs::hub::CommitResult::Stored &&
                    hub.commit(b) == gs::hub::CommitResult::Stored, "driver setup");
            CloudSync cloud(hub);
            cloud.set_connected(true, 0);
            ScriptTransport transport;
            require(cloud.drive_batch(transport, "home-1", 0, 16) == 2 &&
                    transport.submissions == 2 && hub.cloud_completed(b.key) &&
                    !hub.cloud_completed(a.key), "batch driver progresses independent Node");
            require(cloud.drive_batch(transport, "home-1", 1, 16) == 0 &&
                    transport.submissions == 2, "backoff avoids high-rate resend");
        }
        std::cout << "HUB-BACKEND-COMMIT HOST PASS\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "HUB-BACKEND-COMMIT HOST FAIL " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
