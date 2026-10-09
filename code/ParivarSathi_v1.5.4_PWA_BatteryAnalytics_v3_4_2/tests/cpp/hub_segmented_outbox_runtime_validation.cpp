#include "firmware/hub/components/storage/durable_event_outbox.hpp"
#include "firmware/hub/components/storage/outbox_journal_backend.hpp"
#include "firmware/hub/components/cloud/cloud_sync.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using gs::security::Bytes;
using gs::security::Key32;
using gs::hub::storage::AdmissionClass;
using gs::hub::storage::DurableEventOutbox;
using gs::hub::storage::OutboxLimits;
using gs::hub::storage::OutboxRecovery;
using gs::hub::storage::OutboxJournalBackend;
using gs::hub::storage::SegmentStore;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

class MemorySegments final : public SegmentStore {
public:
    explicit MemorySegments(std::uint64_t capacity, std::size_t segment_count = 16)
        : capacity_(capacity), segments_(segment_count), exists_(segment_count, false) {}

    std::uint64_t partition_capacity_bytes() const override { return capacity_; }
    bool segment_size(std::uint16_t segment, bool& exists,
                      std::uint32_t& bytes) override {
        if (segment >= segments_.size()) return false;
        exists = exists_[segment];
        bytes = static_cast<std::uint32_t>(segments_[segment].size());
        return true;
    }
    bool read(std::uint16_t segment, std::uint32_t offset,
              std::uint8_t* output, std::size_t requested,
              std::size_t& actual) override {
        if (segment >= segments_.size() || (requested != 0 && output == nullptr)) return false;
        const auto& bytes = segments_[segment];
        if (offset > bytes.size()) { actual = 0; return true; }
        actual = std::min(requested, bytes.size() - offset);
        std::copy_n(bytes.data() + offset, actual, output);
        return true;
    }
    bool append(std::uint16_t segment, const std::uint8_t* data,
                std::size_t length) override {
        if (segment >= segments_.size() || (length != 0 && data == nullptr)) return false;
        segments_[segment].insert(segments_[segment].end(), data, data + length);
        exists_[segment] = true;
        return true;
    }
    bool sync(std::uint16_t segment) override { return segment < segments_.size(); }
    bool read_publication(Bytes& marker, bool& found) override {
        marker = publication_;
        found = publication_found_;
        return true;
    }
    bool publish_publication(const Bytes& marker) override {
        if (fail_publication_once) {
            fail_publication_once = false;
            return false;
        }
        publication_ = marker;
        publication_found_ = true;
        return true;
    }
    bool read_lifecycle_root(Bytes& marker, bool& found) override {
        marker = lifecycle_root_; found = lifecycle_root_found_; return true;
    }
    bool publish_lifecycle_root(const Bytes& marker) override {
        if (fail_lifecycle_publication_once) {
            fail_lifecycle_publication_once = false;
            return false;
        }
        lifecycle_root_ = marker; lifecycle_root_found_ = true;
        if (fail_lifecycle_publication_after_write_once) {
            fail_lifecycle_publication_after_write_once = false;
            return false;
        }
        return true;
    }
    bool remove_segment(std::uint16_t segment) override {
        if (segment >= segments_.size()) return false;
        if (fail_remove_once) { fail_remove_once = false; return false; }
        segments_[segment].clear(); exists_[segment] = false; return true;
    }
    bool completion_size(bool& exists, std::uint32_t& bytes) override {
        exists = completion_exists_;
        bytes = static_cast<std::uint32_t>(completion_.size());
        return true;
    }
    bool read_completion(std::uint32_t offset, std::uint8_t* output,
                        std::size_t requested, std::size_t& actual) override {
        if (offset > completion_.size()) { actual = 0; return true; }
        actual = std::min(requested, completion_.size() - offset);
        std::copy_n(completion_.data() + offset, actual, output);
        return true;
    }
    bool append_completion(const std::uint8_t* data, std::size_t length) override {
        if (partial_completion_append_bytes_ != static_cast<std::size_t>(-1)) {
            const auto partial = std::min(partial_completion_append_bytes_, length);
            completion_.insert(completion_.end(), data, data + partial);
            completion_exists_ = !completion_.empty();
            partial_completion_append_bytes_ = static_cast<std::size_t>(-1);
            return false;
        }
        completion_.insert(completion_.end(), data, data + length);
        completion_exists_ = true;
        return true;
    }
    bool sync_completion() override { return true; }
    bool truncate_completion(std::uint32_t bytes) override {
        if (bytes > completion_.size()) return false;
        completion_.resize(bytes);
        completion_exists_ = !completion_.empty();
        if (fail_truncate_after_write_once) {
            fail_truncate_after_write_once = false;
            return false;
        }
        return true;
    }
    bool read_completion_publication(Bytes& marker, bool& found) override {
        marker = completion_publication_;
        found = completion_publication_found_;
        return true;
    }
    bool publish_completion_publication(const Bytes& marker) override {
        if (fail_completion_publication_once) {
            fail_completion_publication_once = false;
            return false;
        }
        completion_publication_ = marker;
        completion_publication_found_ = true;
        return true;
    }
    void fail_next_publication() { fail_publication_once = true; }
    bool fail_remove_once{false};
    bool fail_lifecycle_publication_once{false};
    bool fail_lifecycle_publication_after_write_once{false};
    bool fail_truncate_after_write_once{false};
    void fail_next_completion_publication() { fail_completion_publication_once = true; }
    void fail_completion_append_after(std::size_t bytes) {
        partial_completion_append_bytes_ = bytes;
    }
    bool event_nonces_unique() const {
        std::set<std::array<std::uint8_t, 12>> nonces;
        for (const auto& segment : segments_) {
            std::size_t offset = 0;
            while (offset < segment.size()) {
                if (segment.size() - offset < 20) return false;
                const auto* prefix = segment.data() + offset;
                const std::uint32_t plain_bytes =
                    (static_cast<std::uint32_t>(prefix[16]) << 24U) |
                    (static_cast<std::uint32_t>(prefix[17]) << 16U) |
                    (static_cast<std::uint32_t>(prefix[18]) << 8U) |
                    static_cast<std::uint32_t>(prefix[19]);
                const std::size_t frame_bytes = 20U + 12U + plain_bytes + 16U + 4U;
                if (frame_bytes > segment.size() - offset) return false;
                std::array<std::uint8_t, 12> nonce{};
                std::copy_n(prefix + 20, nonce.size(), nonce.begin());
                if (!nonces.insert(nonce).second) return false;
                offset += frame_bytes;
            }
        }
        return true;
    }
    bool completion_nonces_unique() const {
        std::set<std::array<std::uint8_t, 12>> nonces;
        std::size_t offset = 0;
        while (offset < completion_.size()) {
            if (completion_.size() - offset < 20) return false;
            const auto* prefix = completion_.data() + offset;
            const std::uint32_t plain_bytes =
                (static_cast<std::uint32_t>(prefix[16]) << 24U) |
                (static_cast<std::uint32_t>(prefix[17]) << 16U) |
                (static_cast<std::uint32_t>(prefix[18]) << 8U) |
                static_cast<std::uint32_t>(prefix[19]);
            const std::size_t frame_bytes = 20U + 12U + plain_bytes + 16U + 4U;
            if (frame_bytes > completion_.size() - offset) return false;
            std::array<std::uint8_t, 12> nonce{};
            std::copy_n(prefix + 20, nonce.size(), nonce.begin());
            if (!nonces.insert(nonce).second) return false;
            offset += frame_bytes;
        }
        return true;
    }

private:
    std::uint64_t capacity_;
    std::vector<Bytes> segments_;
    std::vector<bool> exists_;
    Bytes publication_;
    Bytes lifecycle_root_;
    Bytes completion_;
    Bytes completion_publication_;
    bool publication_found_{false};
    bool lifecycle_root_found_{false};
    bool completion_exists_{false};
    bool completion_publication_found_{false};
    bool fail_publication_once{false};
    bool fail_completion_publication_once{false};
    std::size_t partial_completion_append_bytes_{static_cast<std::size_t>(-1)};
};

Key32 storage_key() {
    Key32 key{};
    for (std::size_t i = 0; i < key.size(); ++i)
        key[i] = static_cast<std::uint8_t>(0x39U + i);
    return key;
}

gs::NodeMessage make_message(std::uint64_t sequence) {
    gs::NodeMessage message;
    message.node_id = "room1";
    message.session_id = 42;
    message.sequence_number = sequence;
    message.sensor_type = gs::SensorType::Pir;
    message.event_type = gs::EventKind::Motion;
    message.location = "bedroom";
    message.monotonic_ms = static_cast<gs::Milliseconds>(sequence * 1000U);
    message.occurred_at = static_cast<gs::EpochSeconds>(1800000000U + sequence);
    message.time_uncertainty_ms = 250;
    message.battery_mv = 2970;
    message.rssi_dbm = -47;
    return message;
}

void admit(gs::hub::HubRuntime& runtime, std::uint64_t sequence,
           gs::AckClass expected = gs::AckClass::Durable) {
    const auto message = make_message(sequence);
    require(runtime.authenticated_radio_message_callback(
                message, "room1", "device-room1", 42, 0, sequence * 1000U),
            "authenticated ingress accepted");
    const auto result = runtime.run_state_once();
    require(result.has_value() && result->key.physical_device_id == "device-room1" &&
            result->ack == expected, "processing result/ACK class");
}

bool check_stream(void* context, const gs::DomainEvent& event) {
    auto& state = *static_cast<std::pair<std::uint64_t, bool>*>(context);
    ++state.first;
    state.second = state.second && event.key.sequence == state.first &&
                   event.key.physical_device_id == "device-room1" &&
                   event.kind == gs::EventKind::Motion;
    return state.second;
}

struct CompletionStressState {
    gs::hub::CloudSync* cloud{nullptr};
    std::size_t limit{0};
    std::size_t completed{0};
};

bool complete_prefix_with_authenticated_receipts(void* context,
                                                 const gs::DomainEvent& event) {
    auto& state = *static_cast<CompletionStressState*>(context);
    if (state.completed >= state.limit) return true;
    const gs::hub::BackendCommitReply receipt{
        gs::hub::BackendReplyStatus::Committed, event.key, true, false};
    if (state.cloud->handle_backend_reply(event.key, receipt, state.completed) !=
        gs::hub::BackendReceiptResult::Completed) return false;
    ++state.completed;
    return true;
}

void runtime_admission_and_recovery(gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(4U * 1024U * 1024U);
    const auto key = storage_key();
    OutboxLimits limits;
    {
        DurableEventOutbox outbox(flash, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty, "new outbox starts empty");
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.authorize_node("room1", 42, true);
        require(runtime.journal().persistent(), "runtime uses persistent outbox backend");

        for (std::uint64_t sequence = 1; sequence <= 6556; ++sequence) {
            admit(runtime, sequence);
            if (sequence == 129 || sequence == 385 || sequence == 3278)
                require(runtime.journal().size() == sequence,
                        "event beyond legacy slot range is durably admitted");
        }
        require(runtime.journal().size() == 6556 && outbox.record_count() == 6556,
                "runtime admits the 6556-record stress fixture without a physical slot cap");
        require(flash.event_nonces_unique(),
                "AES-GCM nonces are unique across the admitted records");

        // A successful commit whose ACK is lost is retried with the same key.
        const auto retry = make_message(6556);
        require(runtime.authenticated_radio_message_callback(
                    retry, "room1", "device-room1", 42, 0, 6556000),
                "same-process retry ingress");
        const auto duplicate = runtime.run_state_once();
        require(duplicate && duplicate->ack == gs::AckClass::Durable &&
                    !duplicate->state_changed,
                "same-process duplicate ACK does not repeat reducer effect");
        require(runtime.journal().size() == 6556,
                "same-process retry does not append a second event");

        auto wrong_owner = make_message(6557);
        require(!runtime.authenticated_radio_message_callback(
                    wrong_owner, "room2", "device-room2", 42, 0, 6557000),
                "mismatched authenticated owner is rejected before admission");
    }

    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready && recovered.record_count() == 6556,
            "published outbox recovers after Hub restart");
    OutboxJournalBackend recovered_backend(recovered);
    gs::hub::HubRuntime restarted(32, recovered_backend);
    restarted.authorize_node("room1", 42, true);
    require(restarted.restore_from_journal(), "Hub reducer state replays by bounded stream");
    require(restarted.activity_state().last_activity_event_id ==
                gs::EventKey("room1", 42, 6556, "device-room1").str(),
            "latest committed activity is reconstructed");
    const auto retry = make_message(6556);
    require(restarted.authenticated_radio_message_callback(
                retry, "room1", "device-room1", 42, 0, 6556000),
            "post-reboot retry ingress");
    const auto duplicate = restarted.run_state_once();
    require(duplicate && duplicate->ack == gs::AckClass::Durable &&
                !duplicate->state_changed,
            "post-reboot duplicate ACK does not repeat reducer effect");
    require(restarted.journal().size() == 6556,
            "lost ACK retry after reboot is deduplicated");

    std::pair<std::uint64_t, bool> stream{0, true};
    require(restarted.journal().for_each(check_stream, &stream) &&
                stream.first == 6556 && stream.second,
            "stream replay preserves exact ordered owner-bound identities");

    gs::hub::CloudSync cloud(restarted.journal());
    cloud.set_connected(true, 0);
    require(cloud.next_batch(0, 7).size() == 7,
            "cloud replay selects a bounded batch from the streamed outbox");
    CompletionStressState completion_stress{&cloud, 3278, 0};
    require(restarted.journal().for_each(complete_prefix_with_authenticated_receipts,
                                         &completion_stress) &&
            completion_stress.completed == 3278 &&
            restarted.journal().cloud_completed_count() == 3278 &&
            recovered.completion_bytes() <= limits.filesystem_workspace_bytes &&
            flash.completion_nonces_unique(),
            "authenticated HIGH-volume completions fit their bounded durable stream");
    const auto remaining = cloud.next_batch(3278, 7);
    require(remaining.size() == 7 && remaining.front().key.sequence == 3279,
            "only incomplete event bodies remain eligible for backend replay");
}

void publication_failure_never_acks(gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(4U * 1024U * 1024U);
    const auto key = storage_key();
    OutboxLimits limits;
    {
        DurableEventOutbox outbox(flash, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty, "publication fixture starts empty");
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.authorize_node("room1", 42, true);
        admit(runtime, 1);
        flash.fail_next_publication();
        admit(runtime, 2, gs::AckClass::Rejected);
        require(runtime.journal().size() == 1,
                "unpublished event is not reported as durable");
    }
    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready && recovered.record_count() == 1,
            "recovery trusts only the previous published root");
    OutboxJournalBackend backend(recovered);
    gs::hub::HubRuntime restarted(32, backend);
    restarted.authorize_node("room1", 42, true);
    require(restarted.restore_from_journal(), "published prefix reducer replay succeeds");
    admit(restarted, 2, gs::AckClass::Durable);
    require(restarted.journal().size() == 2,
            "Node retry publishes the staged exact event after reboot");
}

void backend_completion_is_published_and_recovers(
        gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(4U * 1024U * 1024U);
    const auto key = storage_key();
    const auto event_key = gs::EventKey("room1", 42, 1, "device-room1");
    OutboxLimits limits;
    {
        DurableEventOutbox outbox(flash, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty, "completion fixture starts empty");
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.authorize_node("room1", 42, true);
        admit(runtime, 1);
        gs::hub::CloudSync cloud(runtime.journal());
        cloud.set_connected(true, 0);
        const auto pending = cloud.next_batch(0, 1);
        require(pending.size() == 1 && pending.front().key.str() == event_key.str(),
                "uncompleted durable event remains pending for backend");

        const gs::hub::BackendCommitReply unauthenticated{
            gs::hub::BackendReplyStatus::Committed, event_key, false, false};
        require(cloud.handle_backend_reply(event_key, unauthenticated, 1) ==
                    gs::hub::BackendReceiptResult::RetryScheduled &&
                !runtime.journal().cloud_completed(event_key),
                "unauthenticated COMMITTED reply does not complete event");

        flash.fail_next_completion_publication();
        const gs::hub::BackendCommitReply authenticated_duplicate{
            gs::hub::BackendReplyStatus::Committed, event_key, true, true};
        require(cloud.handle_backend_reply(event_key, authenticated_duplicate, 2) ==
                    gs::hub::BackendReceiptResult::StorageFault &&
                !runtime.journal().cloud_completed(event_key),
                "completion marker failure cannot report durable completion");
    }

    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready,
            "unpublished but authenticated completion record permits conservative restart");
    OutboxJournalBackend backend(recovered);
    gs::hub::HubRuntime restarted(32, backend);
    restarted.authorize_node("room1", 42, true);
    require(restarted.restore_from_journal(), "reducer replay remains available after receipt interruption");
    gs::hub::CloudSync cloud(restarted.journal());
    cloud.set_connected(true, 0);
    require(cloud.next_batch(0, 1).size() == 1,
            "unpublished completion remains pending until exact backend retry");
    const gs::hub::BackendCommitReply authenticated_duplicate{
        gs::hub::BackendReplyStatus::Committed, event_key, true, true};
    require(cloud.handle_backend_reply(event_key, authenticated_duplicate, 3) ==
                gs::hub::BackendReceiptResult::Completed &&
            restarted.journal().cloud_completed(event_key) &&
            restarted.journal().cloud_completed_count() == 1,
            "authenticated duplicate COMMITTED publishes completion after reboot");
    const auto completed_bytes = recovered.capacity_budget_used_bytes();
    require(cloud.handle_backend_reply(event_key, authenticated_duplicate, 4) ==
                gs::hub::BackendReceiptResult::Completed &&
            restarted.journal().cloud_completed_count() == 1 &&
            recovered.capacity_budget_used_bytes() == completed_bytes,
            "duplicate completion is idempotent and does not rewrite the event body");
    require(cloud.next_batch(4, 1).empty(),
            "durably completed event is removed from backend replay");
    require(restarted.journal().contains(event_key),
            "backend completion does not retire the event body needed for reducer replay");

    DurableEventOutbox rebooted(flash, crypto, key, limits);
    require(rebooted.recover() == OutboxRecovery::Ready,
            "published backend completion recovers after a second Hub restart");
    OutboxJournalBackend rebooted_backend(rebooted);
    require(rebooted_backend.cloud_completed(event_key) &&
            rebooted_backend.cloud_completed_count() == 1 &&
            rebooted_backend.contains(event_key),
            "completion receipt is durable across reboot");
}

void partial_completion_append_recovers_pending(
        gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(4U * 1024U * 1024U);
    const auto key = storage_key();
    const auto event_key = gs::EventKey("room1", 42, 1, "device-room1");
    OutboxLimits limits;
    {
        DurableEventOutbox outbox(flash, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty,
                "partial completion fixture starts empty");
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.authorize_node("room1", 42, true);
        admit(runtime, 1);
        gs::hub::CloudSync cloud(runtime.journal());
        cloud.set_connected(true, 0);
        require(cloud.next_batch(0, 1).size() == 1,
                "event remains uploadable before completion attempt");
        flash.fail_completion_append_after(8);
        const gs::hub::BackendCommitReply committed{
            gs::hub::BackendReplyStatus::Committed, event_key, true, false};
        require(cloud.handle_backend_reply(event_key, committed, 1) ==
                    gs::hub::BackendReceiptResult::StorageFault,
                "partial completion append cannot be reported as complete");
    }

    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready,
            "partial unpublished completion tail is discarded during recovery");
    OutboxJournalBackend backend(recovered);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.authorize_node("room1", 42, true);
    require(runtime.restore_from_journal(),
            "event reducer state replays after partial completion write");
    gs::hub::CloudSync cloud(runtime.journal());
    cloud.set_connected(true, 0);
    require(cloud.next_batch(0, 1).size() == 1,
            "event stays pending after incomplete completion append");
    const gs::hub::BackendCommitReply committed{
        gs::hub::BackendReplyStatus::Committed, event_key, true, false};
    require(cloud.handle_backend_reply(event_key, committed, 2) ==
                gs::hub::BackendReceiptResult::Completed &&
            runtime.journal().cloud_completed(event_key),
            "reverified exact backend receipt can publish completion after restart");
}

void completion_capacity_rejects_without_retiring_body(
        gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(4U * 1024U * 1024U);
    const auto key = storage_key();
    const auto event_key = gs::EventKey("room1", 42, 1, "device-room1");
    OutboxLimits limits;
    limits.filesystem_workspace_bytes = 1;
    DurableEventOutbox outbox(flash, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty,
            "completion-capacity fixture starts empty");
    OutboxJournalBackend backend(outbox);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.authorize_node("room1", 42, true);
    admit(runtime, 1);
    gs::hub::CloudSync cloud(runtime.journal());
    cloud.set_connected(true, 0);
    require(cloud.next_batch(0, 1).size() == 1,
            "event is pending before completion capacity rejection");
    const gs::hub::BackendCommitReply committed{
        gs::hub::BackendReplyStatus::Committed, event_key, true, false};
    require(cloud.handle_backend_reply(event_key, committed, 1) ==
                gs::hub::BackendReceiptResult::StorageFault &&
            !runtime.journal().cloud_completed(event_key) &&
            runtime.journal().contains(event_key) &&
            cloud.next_batch(2, 1).size() == 1,
            "full completion ledger reports failure and preserves the pending body");
}

void completion_update_preserves_previous_publication(
        gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(4U * 1024U * 1024U);
    const auto key = storage_key();
    const auto first_key = gs::EventKey("room1", 42, 1, "device-room1");
    const auto second_key = gs::EventKey("room1", 42, 2, "device-room1");
    OutboxLimits limits;
    {
        DurableEventOutbox outbox(flash, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty,
                "multi-completion fixture starts empty");
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.authorize_node("room1", 42, true);
        admit(runtime, 1);
        admit(runtime, 2);
        gs::hub::CloudSync cloud(runtime.journal());
        cloud.set_connected(true, 0);
        const gs::hub::BackendCommitReply first_receipt{
            gs::hub::BackendReplyStatus::Committed, first_key, true, false};
        require(cloud.handle_backend_reply(first_key, first_receipt, 1) ==
                    gs::hub::BackendReceiptResult::Completed,
                "first exact receipt publishes completion head");
        flash.fail_next_completion_publication();
        const gs::hub::BackendCommitReply second_receipt{
            gs::hub::BackendReplyStatus::Committed, second_key, true, false};
        require(cloud.handle_backend_reply(second_key, second_receipt, 2) ==
                    gs::hub::BackendReceiptResult::StorageFault,
                "failed replacement does not report completion");
    }

    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready,
            "recovery selects prior valid head and stages later receipt");
    OutboxJournalBackend backend(recovered);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.authorize_node("room1", 42, true);
    require(runtime.restore_from_journal(), "events replay after interrupted head replacement");
    gs::hub::CloudSync cloud(runtime.journal());
    cloud.set_connected(true, 0);
    require(runtime.journal().cloud_completed(first_key) &&
            !runtime.journal().cloud_completed(second_key),
            "only the previously published completion remains authoritative");
    const gs::hub::BackendCommitReply second_receipt{
        gs::hub::BackendReplyStatus::Committed, second_key, true, true};
    require(cloud.handle_backend_reply(second_key, second_receipt, 3) ==
                gs::hub::BackendReceiptResult::Completed &&
            runtime.journal().cloud_completed_count() == 2 &&
            flash.completion_nonces_unique(),
            "exact retry publishes second receipt with unique completion nonce");
}

void storage_full_rejects_without_ack(gs::host::security::OpenSslCommissioningCrypto& crypto) {
    MemorySegments flash(8192, 2);
    auto key = storage_key();
    OutboxLimits limits;
    limits.segment_count = 2;
    limits.segment_bytes = 4096;
    limits.filesystem_workspace_bytes = 0;
    limits.protected_capacity_bytes = 0;
    DurableEventOutbox outbox(flash, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "small capacity fixture starts empty");
    OutboxJournalBackend backend(outbox);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.authorize_node("room1", 42, true);

    std::uint64_t accepted = 0;
    for (std::uint64_t sequence = 1; sequence <= 256; ++sequence) {
        const auto message = make_message(sequence);
        require(runtime.authenticated_radio_message_callback(
                    message, "room1", "device-room1", 42, 0, sequence * 1000U),
                "full-capacity fixture ingress");
        const auto result = runtime.run_state_once();
        require(result.has_value(), "full-capacity fixture processing result");
        if (result->ack == gs::AckClass::Durable) {
            ++accepted;
            continue;
        }
        require(result->ack == gs::AckClass::Rejected,
                "capacity failure must not produce a Durable ACK");
        require(runtime.journal().size() == accepted &&
                    outbox.record_count() == accepted,
                "capacity rejection preserves the committed prefix");
        return;
    }
    require(false, "small journal should reach a safe bounded rejection");
}
}  // namespace

int main() {
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        runtime_admission_and_recovery(crypto);
        publication_failure_never_acks(crypto);
        backend_completion_is_published_and_recovers(crypto);
        partial_completion_append_recovers_pending(crypto);
    completion_capacity_rejects_without_retiring_body(crypto);
        completion_update_preserves_previous_publication(crypto);
        storage_full_rejects_without_ack(crypto);
        std::cout << "PASS: authenticated Hub runtime uses segmented durable outbox, "
                     "replays reducer state, deduplicates retries, and rejects unsafe admission\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
