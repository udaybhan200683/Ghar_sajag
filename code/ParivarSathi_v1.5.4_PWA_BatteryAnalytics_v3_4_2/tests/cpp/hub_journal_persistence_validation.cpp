#include "firmware/hub/components/storage/journal.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

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

gs::DomainEvent event(std::uint64_t sequence, const char* physical = "device-A",
                      std::uint64_t session = 17) {
    gs::DomainEvent result;
    result.key = {"bathroom", session, sequence, physical};
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
            require(journal.acknowledge_cloud(event(1).key) &&
                    journal.commit(event(129)) == CommitResult::Full,
                    "cloud receipt unexpectedly reclaimed append-only journal capacity");
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

        MemorySlots replay_slots;
        gs::hub::HubRuntime replay_hub(8, 128);
        require(replay_hub.journal().attach_persistence(crypto, replay_slots, key),
                "retained-session replay journal setup");
        replay_hub.authorize_node("bathroom", 409, true);
        for (const auto& retained : {event(31, "device-A", 406),
                                     event(1, "device-A", 409)}) {
            const auto message = gs::node_message_from_event(retained);
            require(replay_hub.authenticated_radio_message_callback(
                        message, "bathroom", "device-A", 409, 0),
                    "old/current retained key rejected by newer transport session");
            const auto accepted = replay_hub.run_state_once();
            require(accepted && accepted->ack == gs::AckClass::Durable &&
                    accepted->journal_result == CommitResult::Stored,
                    "old/current retained key did not commit");
            require(replay_hub.authenticated_radio_message_callback(
                        message, "bathroom", "device-A", 409, 0),
                    "replayed retained key rejected at authenticated ingress");
            const auto duplicate_runtime = replay_hub.run_state_once();
            require(duplicate_runtime && duplicate_runtime->ack == gs::AckClass::Durable &&
                    duplicate_runtime->journal_result == CommitResult::Duplicate &&
                    duplicate_runtime->journal_count_before ==
                        duplicate_runtime->journal_count_after,
                    "old/current duplicate consumed another journal slot");
        }
        require(replay_hub.journal().size() == 2,
                "old/current retained identity cardinality mismatch");
        gs::hub::HubRuntime restored_replay(8, 128);
        restored_replay.authorize_node("bathroom", 409, true);
        require(restored_replay.journal().attach_persistence(crypto, replay_slots, key) &&
                restored_replay.restore_from_journal() &&
                restored_replay.journal().size() == 2,
                "old/current retained keys did not restore near capacity");
        for (const auto& retained : {event(31, "device-A", 406),
                                     event(1, "device-A", 409)}) {
            require(restored_replay.authenticated_radio_message_callback(
                        gs::node_message_from_event(retained), "bathroom", "device-A", 409, 0),
                    "restored old/current retained replay ingress rejected");
            const auto duplicate_after_restart = restored_replay.run_state_once();
            require(duplicate_after_restart &&
                    duplicate_after_restart->ack == gs::AckClass::Durable &&
                    duplicate_after_restart->journal_result == CommitResult::Duplicate &&
                    restored_replay.journal().size() == 2,
                    "restored old/current replay consumed journal capacity");
        }

        gs::hub::HubRuntime full_hub(4, 1);
        full_hub.authorize_node("bathroom", 17, true);
        require(full_hub.radio_callback(event(1)), "Full mapping first event ingress");
        const auto first_result = full_hub.run_state_once();
        require(first_result && first_result->ack == gs::AckClass::Durable &&
                first_result->journal_result == CommitResult::Stored,
                "normal HubRuntime commit/ACK mapping failed");
        require(full_hub.radio_callback(event(2)), "Full mapping overflow ingress");
        const auto full_result = full_hub.run_state_once();
        require(full_result && full_result->journal_result == CommitResult::Full &&
                full_result->ack == gs::AckClass::Rejected &&
                full_result->journal_count_before == 1 &&
                full_result->journal_count_after == 1 &&
                full_result->journal_capacity == 1,
                "Hub Full did not map to Rejected with exact counts");
        const auto full_ack = gs::transport::encode_node_ack(
            gs::make_node_ack(full_result->key, full_result->ack, 0, "journal_rejected"));
        require(static_cast<bool>(full_ack), "Hub Full Rejected ACK encoding failed");
        const auto decoded_full_ack = gs::transport::decode_node_ack(
            full_ack.frame.bytes.data(), full_ack.frame.size);
        require(static_cast<bool>(decoded_full_ack) &&
                decoded_full_ack.value->ack_type == gs::AckClass::Rejected,
                "Hub Full Rejected ACK codec mapping failed");

        MemorySlots failing_slots;
        failing_slots.fail_write = true;
        gs::hub::HubRuntime fault_hub(4, 128);
        require(fault_hub.journal().attach_persistence(crypto, failing_slots, key),
                "StorageFault mapping setup");
        fault_hub.authorize_node("bathroom", 17, true);
        require(fault_hub.radio_callback(event(70)), "StorageFault ingress");
        const auto fault_result = fault_hub.run_state_once();
        require(fault_result && fault_result->journal_result == CommitResult::StorageFault &&
                fault_result->ack == gs::AckClass::Rejected &&
                fault_result->journal_count_before == 0 &&
                fault_result->journal_count_after == 0,
                "StorageFault did not map to Rejected ACK");

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
        std::cout << "P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128 full=129 "
                     "replacement/dedupe/restart/tamper/write-fault/reducer-replay\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-HUB-JOURNAL HOST FAIL " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
