#include "firmware/node/components/storage/node_recovery_persistence.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>

using gs::EventKind;
using gs::node::NodeRecoveryLoadStatus;
using gs::node::NodeRecoveryRepository;
using gs::node::NodeRuntime;
using gs::security::Bytes;
using gs::security::Key32;
using gs::host::security::OpenSslCommissioningCrypto;

namespace {
void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}

class MemoryBlob final : public gs::security::SecurityBlobStore {
public:
    bool read(Bytes& out, bool& found) override {
        if (read_error) return false;
        found = present;
        out = bytes;
        return true;
    }
    bool write(const Bytes& blob) override {
        if (persist_then_fail) {
            persist_then_fail = false;
            bytes = blob;
            present = true;
            return false;
        }
        if (fail_next_write) {
            fail_next_write = false;
            return false;
        }
        bytes = blob;
        present = true;
        return true;
    }
    Bytes bytes;
    bool present{false};
    bool read_error{false};
    bool fail_next_write{false};
    bool persist_then_fail{false};
};

void push_u64(Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8) out.push_back(static_cast<std::uint8_t>(value >> shift));
}
void push_u32(Bytes& out, std::uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8) out.push_back(static_cast<std::uint8_t>(value >> shift));
}
void push_string(Bytes& out, const std::string& value) {
    out.push_back(static_cast<std::uint8_t>(value.size()));out.insert(out.end(),value.begin(),value.end());
}
void install_v2_heartbeat(OpenSslCommissioningCrypto& crypto,const Key32& key,MemoryBlob& store) {
    Bytes plain;push_string(plain,"bathroom");push_u64(plain,7);plain.push_back(0);plain.push_back(1);
    push_string(plain,"room");push_u64(plain,7);push_u64(plain,11);
    plain.push_back(static_cast<std::uint8_t>(EventKind::Heartbeat));push_u64(plain,100);push_u64(plain,200);push_u64(plain,200);
    push_u32(plain,0);plain.insert(plain.end(),10,0);
    Bytes blob{'G','S','N','R',2};push_u64(blob,1);gs::security::Nonce12 nonce{};require(crypto.random_bytes(nonce.data(),nonce.size()),"legacy fixture nonce");blob.insert(blob.end(),nonce.begin(),nonce.end());blob.push_back(static_cast<std::uint8_t>(plain.size()>>8));blob.push_back(static_cast<std::uint8_t>(plain.size()));
    Bytes aad=blob;push_string(aad,"home-a");push_string(aad,"hub-a");push_string(aad,"bathroom");Bytes cipher;gs::security::GcmTag tag{};
    require(crypto.seal_aes256_gcm(key,nonce,aad,plain,cipher,tag),"legacy v2 fixture encryption");blob.insert(blob.end(),cipher.begin(),cipher.end());blob.insert(blob.end(),tag.begin(),tag.end());store.bytes=std::move(blob);store.present=true;
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        Key32 wrapping_key{};
        require(crypto.random_bytes(wrapping_key.data(), wrapping_key.size()),
                "test key generation failed");
        MemoryBlob store;
        MemoryBlob legacy_store;install_v2_heartbeat(crypto,wrapping_key,legacy_store);
        NodeRecoveryRepository legacy_repo(crypto,legacy_store,wrapping_key,"home-a","hub-a","bathroom");
        const auto legacy=legacy_repo.load();
        require(legacy.status==NodeRecoveryLoadStatus::Ready&&legacy.state&&
                legacy.state->retirement_epoch==0&&legacy.state->durable_admission_highwater==0&&
                legacy.state->pending.size()==1&&legacy.state->pending[0].event.kind==EventKind::Heartbeat,
                "v2 migration fabricated retirement data or lost a retryable heartbeat");
        NodeRuntime migrated("bathroom",8);
        require(migrated.restore_recovery(*legacy.state,0)&&migrated.set_retirement_epoch(9)&&
                legacy_repo.save(migrated.recovery_snapshot()),"v2 pending heartbeat did not migrate into v3");
        const auto migrated_state=legacy_repo.load();
        require(migrated_state.state&&migrated_state.state->retirement_epoch==9&&
                migrated_state.state->durable_admission_highwater==0&&
                migrated_state.state->pending.size()==1&&
                migrated_state.state->pending[0].event.key.session_id==7,
                "v3 migration lost old pending identity or invented current highwater");
        MemoryBlob ambiguous_store;
        NodeRuntime heartbeat_node("bathroom", 50);
        require(heartbeat_node.set_retirement_epoch(9) &&
                heartbeat_node.record(EventKind::Heartbeat, "", 101, 0).has_value(),
                "sequenced heartbeat persistence setup failed");
        NodeRecoveryRepository heartbeat_repo(crypto, ambiguous_store, wrapping_key,
                                               "home-a", "hub-a", "bathroom");
        NodeRuntime heartbeat_validation("bathroom", 51);
        require(heartbeat_validation.restore_recovery(heartbeat_node.recovery_snapshot(), 0),
                "heartbeat recovery state did not validate before persistence");
        ambiguous_store.persist_then_fail = true;
        const bool ambiguous_saved = heartbeat_repo.save(heartbeat_node.recovery_snapshot());
        const auto ambiguous_loaded = heartbeat_repo.load();
        require(ambiguous_saved,
                "persist-then-fail recovery write was not resolved by readback");
        const auto heartbeat_loaded = heartbeat_repo.load();
        NodeRuntime heartbeat_reboot("bathroom", 51);
        require(heartbeat_loaded.status == NodeRecoveryLoadStatus::Ready &&
                heartbeat_loaded.state && heartbeat_reboot.restore_recovery(*heartbeat_loaded.state, 0) &&
                heartbeat_loaded.state->durable_admission_highwater == 1 &&
                heartbeat_reboot.pending() == 1 &&
                heartbeat_reboot.recovery_snapshot().pending[0].event.kind == EventKind::Heartbeat &&
                heartbeat_reboot.recovery_snapshot().pending[0].event.key.session_id == 50 &&
                heartbeat_reboot.recovery_snapshot().durable_admission_highwater == 0,
                "heartbeat/highwater did not survive v3 persistence reboot");
        NodeRuntime original("bathroom", 7);
        const auto motion = original.record(EventKind::Motion, "Bathroom", 100, 0);
        require(motion.has_value(), "retained event setup failed");
        require(original.next_message(100).has_value(), "retry setup not due");
        original.transport_result(*motion, false, 100);
        {
            NodeRecoveryRepository repo(crypto, store, wrapping_key,
                                        "home-a", "hub-a", "bathroom");
            require(repo.load().status == NodeRecoveryLoadStatus::Missing,
                    "new store was not empty");
            require(repo.save(original.recovery_snapshot()),
                    "first encrypted recovery commit failed");
            require(store.bytes.size() < 8192 &&
                    std::search(store.bytes.begin(), store.bytes.end(),
                                "Bathroom", "Bathroom" + 8) == store.bytes.end(),
                    "recovery record exposed location plaintext or exceeded bound");
        }
        {
            NodeRecoveryRepository reopened(crypto, store, wrapping_key,
                                            "home-a", "hub-a", "bathroom");
            const auto loaded = reopened.load();
            require(loaded.status == NodeRecoveryLoadStatus::Ready &&
                    loaded.generation == 1 && loaded.state &&
                    loaded.state->pending.size() == 1 &&
                    loaded.state->retained.size() == 1 &&
                    loaded.state->pending[0].attempt == 1,
                    "encrypted recovery record did not survive reopen");
            NodeRuntime restarted("bathroom", 8);
            require(restarted.restore_recovery(*loaded.state, 0),
                    "new session could not restore persisted event");
            const auto retransmit = restarted.next_message(0);
            require(retransmit && retransmit->session_id == 7 &&
                    retransmit->sequence_number == motion->sequence,
                    "persisted in-flight event identity changed");
            store.fail_next_write = true;
            require(!reopened.save(restarted.recovery_snapshot()) &&
                    reopened.load().generation == 1,
                    "write failure replaced previous committed evidence");
            require(restarted.acknowledge(*motion, gs::AckClass::Durable),
                    "matching ACK did not retire restored evidence");
            require(reopened.save(restarted.recovery_snapshot()) &&
                    reopened.load().generation == 2 &&
                    reopened.load().state->pending.empty(),
                    "post-ACK empty state was not committed");
            require(!reopened.save(original.recovery_snapshot()) &&
                    reopened.load().generation == 2,
                    "older boot session replaced newer recovery state");
            NodeRuntime full("bathroom", 8);
            for (unsigned i = 0; i < 32; ++i)
                require(full.record(i < 28 ? EventKind::Motion : EventKind::DoorOpen,
                                    "Bathroom", i, 0).has_value(),
                        "capacity record setup failed");
            require(!full.record(EventKind::Motion, "Bathroom", 33, 0) &&
                    reopened.save(full.recovery_snapshot()) &&
                    store.bytes.size() <= 8192 &&
                    reopened.load().state->pending.size() == 32,
                    "32-event persistence boundary failed");
        }
        NodeRecoveryRepository foreign_hub(crypto, store, wrapping_key,
                                           "home-a", "hub-b", "bathroom");
        require(foreign_hub.load().status == NodeRecoveryLoadStatus::Corrupt,
                "foreign Hub opened bound recovery record");
        Key32 wrong_key = wrapping_key;
        wrong_key[0] ^= 1;
        NodeRecoveryRepository wrong(crypto, store, wrong_key,
                                     "home-a", "hub-a", "bathroom");
        require(wrong.load().status == NodeRecoveryLoadStatus::Corrupt,
                "wrong wrapping key opened recovery record");
        auto tampered = store.bytes;
        store.bytes.back() ^= 1;
        NodeRecoveryRepository repo(crypto, store, wrapping_key,
                                    "home-a", "hub-a", "bathroom");
        require(repo.load().status == NodeRecoveryLoadStatus::Corrupt &&
                !repo.save(original.recovery_snapshot()),
                "tampered record was silently overwritten");
        store.bytes = tampered;
        store.read_error = true;
        require(repo.load().status == NodeRecoveryLoadStatus::IoError &&
                !repo.save(original.recovery_snapshot()),
                "read error allowed a new recovery commit");
        store.read_error = false;
        auto over_capacity = original.recovery_snapshot();
        over_capacity.pending.resize(33, over_capacity.pending.front());
        require(!repo.save(over_capacity), "over-capacity recovery state committed");
        MemoryBlob summary_store;
        NodeRuntime summary_node("bathroom", 11);
        const gs::DomainEvent::MotionAggregate aggregate{17, 200, 900};
        const auto summary = summary_node.record(EventKind::MotionSummary, "Bathroom",
            900, 0, 0, 0, false, gs::SensorType::Pir, 0, aggregate);
        require(summary.has_value(), "typed summary admission failed");
        NodeRecoveryRepository summary_repo(crypto, summary_store, wrapping_key,
                                            "home-a", "hub-a", "bathroom");
        require(summary_repo.save(summary_node.recovery_snapshot()),
                "typed summary was not encrypted and persisted");
        const auto summary_loaded = summary_repo.load();
        require(summary_loaded.status == NodeRecoveryLoadStatus::Ready &&
                summary_loaded.state && summary_loaded.state->retained.size() == 1 &&
                summary_loaded.state->retained[0].motion_aggregate &&
                summary_loaded.state->retained[0].motion_aggregate->additional_count == 17,
                "summary aggregate was not restored exactly");
        NodeRuntime summary_reboot("bathroom", 12);
        require(summary_reboot.restore_recovery(*summary_loaded.state, 1000) &&
                summary_reboot.acknowledge(*summary, gs::AckClass::Durable) &&
                summary_reboot.persisted() == 0,
                "summary identity did not survive restart and ACK retirement");
        std::cout << "P2-PERSIST-NODE-RECOVERY HOST PASS encrypted bounded recovery\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-NODE-RECOVERY HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
