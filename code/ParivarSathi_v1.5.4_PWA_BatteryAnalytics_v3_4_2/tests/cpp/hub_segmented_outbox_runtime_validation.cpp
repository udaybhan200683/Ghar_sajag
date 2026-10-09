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
    void fail_next_publication() { fail_publication_once = true; }
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

private:
    std::uint64_t capacity_;
    std::vector<Bytes> segments_;
    std::vector<bool> exists_;
    Bytes publication_;
    bool publication_found_{false};
    bool fail_publication_once{false};
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

        for (std::uint64_t sequence = 1; sequence <= 2048; ++sequence) {
            admit(runtime, sequence);
            if (sequence == 129 || sequence == 385)
                require(runtime.journal().size() == sequence,
                        "event beyond legacy slot range is durably admitted");
        }
        require(runtime.journal().size() == 2048 && outbox.record_count() == 2048,
                "runtime admits thousands without a physical slot cap");
        require(flash.event_nonces_unique(),
                "AES-GCM nonces are unique across the admitted records");

        // A successful commit whose ACK is lost is retried with the same key.
        const auto retry = make_message(2048);
        require(runtime.authenticated_radio_message_callback(
                    retry, "room1", "device-room1", 42, 0, 2048000),
                "same-process retry ingress");
        const auto duplicate = runtime.run_state_once();
        require(duplicate && duplicate->ack == gs::AckClass::Durable &&
                    !duplicate->state_changed,
                "same-process duplicate ACK does not repeat reducer effect");
        require(runtime.journal().size() == 2048,
                "same-process retry does not append a second event");

        auto wrong_owner = make_message(2049);
        require(!runtime.authenticated_radio_message_callback(
                    wrong_owner, "room2", "device-room2", 42, 0, 2049000),
                "mismatched authenticated owner is rejected before admission");
    }

    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready && recovered.record_count() == 2048,
            "published outbox recovers after Hub restart");
    OutboxJournalBackend recovered_backend(recovered);
    gs::hub::HubRuntime restarted(32, recovered_backend);
    restarted.authorize_node("room1", 42, true);
    require(restarted.restore_from_journal(), "Hub reducer state replays by bounded stream");
    require(restarted.activity_state().last_activity_event_id ==
                gs::EventKey("room1", 42, 2048, "device-room1").str(),
            "latest committed activity is reconstructed");
    const auto retry = make_message(2048);
    require(restarted.authenticated_radio_message_callback(
                retry, "room1", "device-room1", 42, 0, 2048000),
            "post-reboot retry ingress");
    const auto duplicate = restarted.run_state_once();
    require(duplicate && duplicate->ack == gs::AckClass::Durable &&
                !duplicate->state_changed,
            "post-reboot duplicate ACK does not repeat reducer effect");
    require(restarted.journal().size() == 2048,
            "lost ACK retry after reboot is deduplicated");

    std::pair<std::uint64_t, bool> stream{0, true};
    require(restarted.journal().for_each(check_stream, &stream) &&
                stream.first == 2048 && stream.second,
            "stream replay preserves exact ordered owner-bound identities");

    gs::hub::CloudSync cloud(restarted.journal());
    cloud.set_connected(true, 0);
    require(cloud.next_batch(0, 7).size() == 7,
            "cloud replay selects a bounded batch from the streamed outbox");
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
        storage_full_rejects_without_ack(crypto);
        std::cout << "PASS: authenticated Hub runtime uses segmented durable outbox, "
                     "replays reducer state, deduplicates retries, and rejects unsafe admission\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
