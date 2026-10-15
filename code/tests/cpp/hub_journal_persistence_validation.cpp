#include "firmware/hub/storage/journal.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "tests/support/host/security/openssl_commissioning_crypto.hpp"

#include <array>
#include <cstdlib>
#include <iostream>
#include <stdexcept>

namespace {
using gs::security::Bytes;
using gs::hub::CommitResult;
using gs::hub::HubJournal;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

struct MemorySlots final : gs::hub::JournalSlotStore {
    std::array<Bytes, 128> data{};
    bool fail_read{false};
    bool fail_write{false};
    bool ambiguous_commit{false};
    bool read(std::size_t slot, Bytes& blob, bool& found) override {
        if (fail_read || slot >= data.size()) return false;
        blob = data[slot];
        found = !blob.empty();
        return true;
    }
    bool write(std::size_t slot, const Bytes& blob) override {
        if (fail_write || slot >= data.size()) return false;
        data[slot] = blob;
        return !ambiguous_commit;
    }
};

gs::DomainEvent event(std::uint64_t sequence, const char* physical = "device-A");

void require_wire_ack(gs::hub::ProcessResult const& result, gs::AckClass expected) {
    const auto encoded = gs::transport::encode_node_ack(
        gs::make_node_ack(result.key,result.ack,0,"journal_result"));
    require(static_cast<bool>(encoded),"runtime ACK encoding");
    const auto decoded = gs::transport::decode_node_ack(
        encoded.frame.bytes.data(),encoded.frame.size);
    require(static_cast<bool>(decoded) && decoded.value->ack_type==expected,
            "serialized ACK class did not match journal result");
}

void runtime_ack_mapping(gs::host::security::OpenSslCommissioningCrypto& crypto,
                         const gs::security::Key32& key) {
    {
        MemorySlots slots;
        gs::hub::HubRuntime runtime(4,128);
        require(runtime.journal().attach_persistence(crypto,slots,key),
                "full mapping persistence setup");
        runtime.authorize_node("bathroom",17,false);
        require(runtime.radio_callback(event(1)),"full mapping first ingress");
        const auto stored=runtime.run_state_once();
        require(stored && stored->ack==gs::AckClass::Durable &&
                runtime.journal().size()==1,"stored event did not commit before ACK");
        require_wire_ack(*stored,gs::AckClass::Durable);
        require(runtime.radio_callback(event(1)),"duplicate mapping ingress");
        const auto duplicate=runtime.run_state_once();
        require(duplicate && duplicate->ack==gs::AckClass::Durable &&
                !duplicate->state_changed && runtime.journal().size()==1,
                "duplicate did not retain durable idempotent outcome");
        require_wire_ack(*duplicate,gs::AckClass::Durable);
        for (std::uint64_t sequence=2;sequence<=128;++sequence) {
            require(runtime.radio_callback(event(sequence)),"full mapping capacity ingress");
            const auto capacity_result=runtime.run_state_once();
            require(capacity_result && capacity_result->ack==gs::AckClass::Durable,
                    "legacy journal capacity prefix failed to commit");
        }
        require(runtime.journal().size()==128,"legacy journal did not reach full capacity");
        require(runtime.radio_callback(event(129)),"full mapping overflow ingress");
        const auto full=runtime.run_state_once();
        require(full && full->ack==gs::AckClass::Rejected &&
                runtime.journal().size()==128,"Full outcome changed committed journal state");
        require_wire_ack(*full,gs::AckClass::Rejected);
    }
    {
        MemorySlots slots;
        gs::hub::HubRuntime runtime(4,128);
        require(runtime.journal().attach_persistence(crypto,slots,key),
                "StorageFault mapping persistence setup");
        runtime.authorize_node("bathroom",17,false);
        slots.fail_write=true;
        require(runtime.radio_callback(event(3)),"StorageFault mapping ingress");
        const auto fault=runtime.run_state_once();
        require(fault && fault->ack==gs::AckClass::Rejected &&
                runtime.journal().size()==0,"StorageFault outcome changed committed journal state");
        require_wire_ack(*fault,gs::AckClass::Rejected);
    }
}

gs::DomainEvent event(std::uint64_t sequence, const char* physical) {
    gs::DomainEvent result;
    result.key = {"bathroom", 17, sequence, physical};
    result.kind = gs::EventKind::Motion;
    result.location = "Bathroom";
    result.occurred_at = 42;
    result.received_at = 43;
    result.sensor_type = gs::SensorType::Pir;
    return result;
}
}  // namespace

int main() {
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        gs::security::Key32 key{};
        require(crypto.random_bytes(key.data(), key.size()), "test key generation");
        runtime_ack_mapping(crypto,key);
        MemorySlots slots;
        {
            HubJournal journal(128);
            require(journal.attach_persistence(crypto, slots, key), "empty journal load");
            require(journal.commit(event(1)) == CommitResult::Stored, "first commit");
            require(!slots.data[0].empty(), "sealed slot written");
            require(journal.commit(event(1)) == CommitResult::Duplicate, "exact dedupe");
            require(journal.commit(event(1, "device-B")) == CommitResult::Stored,
                    "replacement identity isolated");
            for (std::uint64_t sequence = 2; sequence <= 127; ++sequence)
                require(journal.commit(event(sequence)) == CommitResult::Stored,
                        "capacity minus one or capacity commit");
            require(journal.size() == 128, "capacity exactly 128");
            require(journal.commit(event(128)) == CommitResult::Full,
                    "capacity plus one rejected");
        }
        {
            HubJournal rebooted(128);
            require(rebooted.attach_persistence(crypto, slots, key), "restart load");
            require(rebooted.size() == 128 && rebooted.contains(event(1).key) &&
                    rebooted.contains(event(1, "device-B").key), "restart dedupe");
            require(rebooted.commit(event(1)) == CommitResult::Duplicate,
                    "lost ACK retry after restart");
            require(rebooted.commit(event(128)) == CommitResult::Full,
                    "full state persists");
        }
        MemorySlots bad = slots;
        bad.data[0][18] ^= 0x01;
        HubJournal corrupt(128);
        require(!corrupt.attach_persistence(crypto, bad, key) && corrupt.storage_fault(),
                "tampered record fails closed");
        require(corrupt.commit(event(200)) == CommitResult::StorageFault,
                "no ACK after corrupt load");
        gs::security::Key32 wrong = key;
        wrong[0] ^= 1;
        HubJournal wrong_key(128);
        require(!wrong_key.attach_persistence(crypto, slots, wrong),
                "wrong installation key fails closed");
        MemorySlots interrupted;
        interrupted.ambiguous_commit = true;
        HubJournal before_restart(128);
        require(before_restart.attach_persistence(crypto, interrupted, key),
                "interrupted setup");
        require(before_restart.commit(event(1)) == CommitResult::StorageFault &&
                before_restart.storage_fault(), "ambiguous commit is not ACKed");
        interrupted.ambiguous_commit = false;
        HubJournal after_restart(128);
        require(after_restart.attach_persistence(crypto, interrupted, key) &&
                after_restart.commit(event(1)) == CommitResult::Duplicate,
                "committed event recovered after ambiguous return");
        MemorySlots reducer_slots;
        {
            gs::hub::HubRuntime before_crash(4, 128);
            require(before_crash.journal().attach_persistence(crypto, reducer_slots, key),
                    "reducer crash setup");
            require(before_crash.journal().commit(event(77)) == CommitResult::Stored &&
                    !before_crash.routine_state().activity_seen,
                    "crash window did not leave committed event unapplied");
        }
        gs::hub::HubRuntime recovered(4, 128);
        recovered.authorize_node("bathroom", 17, true);
        gs::RoutineConfig window;
        window.window_id = "morning";
        window.end_at = 100;
        window.grace_end_at = 120;
        recovered.start_window(window, gs::HomeMode::Home);
        require(recovered.journal().attach_persistence(crypto, reducer_slots, key) &&
                recovered.restore_from_journal() &&
                recovered.routine_state().activity_seen &&
                recovered.routine_state().evidence_ids.size() == 1 &&
                recovered.activity_state().last_activity_event_id == event(77).key.str(),
                "committed event did not rebuild reducer state after restart");
        require(!recovered.restore_from_journal(), "journal state replayed twice");
        require(recovered.radio_callback(event(77)), "duplicate restart input rejected");
        const auto duplicate = recovered.run_state_once();
        require(duplicate && duplicate->ack == gs::AckClass::Durable &&
                !duplicate->state_changed &&
                recovered.routine_state().evidence_ids.size() == 1,
                "post-restart duplicate reapplied reducer");
        require(recovered.radio_callback(event(78)), "new event after restart rejected");
        const auto fresh = recovered.run_state_once();
        require(fresh && fresh->state_changed &&
                recovered.routine_state().evidence_ids.size() == 2,
                "new event after replay did not update reducer");
        MemorySlots summary_slots;
        auto compacted = event(300);
        compacted.kind = gs::EventKind::MotionSummary;
        compacted.motion_aggregate = gs::DomainEvent::MotionAggregate{12, 100, 900};
        {
            HubJournal summary_journal(128);
            require(summary_journal.attach_persistence(crypto, summary_slots, key) &&
                    summary_journal.commit(compacted) == CommitResult::Stored,
                    "typed summary did not commit durably");
        }
        HubJournal restored_summary(128);
        require(restored_summary.attach_persistence(crypto, summary_slots, key) &&
                restored_summary.contains(compacted.key) &&
                restored_summary.records().size() == 1 &&
                restored_summary.records().front().motion_aggregate &&
                restored_summary.records().front().motion_aggregate->additional_count == 12 &&
                restored_summary.commit(compacted) == CommitResult::Duplicate,
                "typed summary lost payload or dedupe after Hub restart");
        MemorySlots maximum_slots;
        auto maximum_event = event(301, std::string(64, 'd').c_str());
        maximum_event.key.source_id = std::string(24, 'n');
        maximum_event.location = std::string(64, 'r');
        maximum_event.kind = gs::EventKind::MotionSummary;
        maximum_event.motion_aggregate = gs::DomainEvent::MotionAggregate{0xffffffffU, 1, 2};
        maximum_event.uncertainty_s = 0xffffffffU;
        maximum_event.battery_mv = 0xffffU;
        maximum_event.rssi_dbm = static_cast<std::int16_t>(0x7fff);
        {
            HubJournal maximum_journal(128);
            require(maximum_journal.attach_persistence(crypto, maximum_slots, key) &&
                    maximum_journal.commit(maximum_event) == CommitResult::Stored,
                    "maximum bounded event did not commit");
            // Current codec: 228-byte maximum plaintext under field bounds,
            // plus 12-byte nonce and 16-byte GCM tag = 256-byte NVS blob.
            require(maximum_slots.data[0].size() == 256,
                    "maximum event serialization size changed");
        }
        std::cout << "P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128 full=129 "
                     "replacement/dedupe/restart/tamper/write-fault/reducer-replay\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-HUB-JOURNAL HOST FAIL " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
