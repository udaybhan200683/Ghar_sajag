#include "firmware/node/components/storage/node_recovery_persistence.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"

#include <algorithm>
#include <array>
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
};

// Rewrap a single ordinary Motion in the actual legacy v1 envelope. V1 used
// the same authenticated header and event fields, without the v2 aggregate flag.
void convert_single_motion_to_v1(MemoryBlob& store, OpenSslCommissioningCrypto& crypto,
                                  const Key32& key) {
    auto& blob = store.bytes;
    require(blob.size() > 43 && blob[4] == 2, "v2 fixture missing");
    gs::security::Nonce12 nonce{};
    std::copy_n(blob.begin() + 13, nonce.size(), nonce.begin());
    Bytes aad(blob.begin(), blob.begin() + 27);
    for (const char* value : {"home-a", "hub-a", "bathroom"}) {
        const auto length = std::char_traits<char>::length(value);
        aad.push_back(static_cast<std::uint8_t>(length));
        aad.insert(aad.end(), value, value + length);
    }
    gs::security::GcmTag tag{};
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    Bytes cipher(blob.begin() + 27, blob.end() - tag.size());
    Bytes plain;
    require(crypto.open_aes256_gcm(key, nonce, aad, cipher, tag, plain) &&
            !plain.empty() && plain.back() == 0, "v2 fixture decrypt failed");
    plain.pop_back();
    blob[4] = 1;
    blob[25] = static_cast<std::uint8_t>(plain.size() >> 8);
    blob[26] = static_cast<std::uint8_t>(plain.size());
    require(crypto.random_bytes(nonce.data(), nonce.size()), "v1 nonce failed");
    std::copy(nonce.begin(), nonce.end(), blob.begin() + 13);
    aad.assign(blob.begin(), blob.begin() + 27);
    for (const char* value : {"home-a", "hub-a", "bathroom"}) {
        const auto length = std::char_traits<char>::length(value);
        aad.push_back(static_cast<std::uint8_t>(length));
        aad.insert(aad.end(), value, value + length);
    }
    require(crypto.seal_aes256_gcm(key, nonce, aad, plain, cipher, tag),
            "v1 fixture encrypt failed");
    blob.resize(27);
    blob.insert(blob.end(), cipher.begin(), cipher.end());
    blob.insert(blob.end(), tag.begin(), tag.end());
}

void persisted_ack_case(OpenSslCommissioningCrypto& crypto, const Key32& key,
                        bool legacy_v1, bool current_origin) {
    MemoryBlob store;
    NodeRecoveryRepository repo(crypto, store, key, "home-a", "hub-a", "bathroom");
    NodeRuntime before("bathroom", current_origin ? 409 : 406);
    const auto event = before.record(EventKind::Motion, "Bathroom", 100, 0);
    require(event && repo.save(before.recovery_snapshot()), "persisted ACK fixture failed");
    if (legacy_v1) convert_single_motion_to_v1(store, crypto, key);
    const auto loaded = repo.load();
    require(loaded.status == NodeRecoveryLoadStatus::Ready && loaded.state &&
            loaded.state->pending.size() == 1 && loaded.state->retained.size() == 1,
            "persisted ACK restore decode failed");
    NodeRuntime after("bathroom", current_origin ? 410 : 409);
    require(after.restore_recovery(*loaded.state, 0), "persisted ACK runtime restore failed");
    const auto snapshot = after.recovery_snapshot();
    require(snapshot.pending[0].event.key.str() == event->str() &&
            snapshot.retained[0].key.str() == event->str() &&
            after.has_pending_key(*event), "restored pending/retained identity mismatch");
    const auto resend = after.next_message(0);
    require(resend && resend->node_id == event->source_id &&
            resend->session_id == event->session_id &&
            resend->sequence_number == event->sequence,
            "persisted ACK resend changed business key");
    const auto rejected_wire = gs::transport::encode_node_ack(
        gs::make_node_ack(*event, gs::AckClass::Rejected, 0, "journal_rejected"));
    require(static_cast<bool>(rejected_wire), "rejected ACK encode failed");
    const auto rejected = gs::transport::decode_node_ack(
        rejected_wire.frame.bytes.data(), rejected_wire.frame.size);
    require(static_cast<bool>(rejected) &&
            static_cast<int>(rejected.value->ack_type) == 3 &&
            !after.acknowledge(*event, rejected.value->ack_type) &&
            after.pending() == 1 && after.persisted() == 1,
            "journal rejection unexpectedly retired retained evidence");
    const auto encoded = gs::transport::encode_node_ack(
        gs::make_node_ack(*event, gs::AckClass::Durable, 0, "journal_committed"));
    require(static_cast<bool>(encoded), "production ACK encode failed");
    const auto decoded = gs::transport::decode_node_ack(encoded.frame.bytes.data(),
                                                         encoded.frame.size);
    require(static_cast<bool>(decoded), "production ACK decode failed");
    const gs::EventKey ack_key{decoded.value->node_id, decoded.value->session_id,
                               decoded.value->sequence_number};
    require(after.acknowledge(ack_key, decoded.value->ack_type) &&
            after.pending() == 0 && after.persisted() == 0,
            "persisted ACK retirement failed");
    require(repo.save(after.recovery_snapshot()), "post-ACK persistence failed");
    const auto empty = repo.load();
    require(empty.status == NodeRecoveryLoadStatus::Ready && empty.state &&
            empty.state->pending.empty() && empty.state->retained.empty(),
            "retired event survived repository reload");
    std::cout << "ACKDIAG-PERSIST "
              << (legacy_v1 ? "v1" : current_origin ? "current-origin-v2" : "v2")
              << " PASS rejected-preserves durable-retires\n";
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        Key32 wrapping_key{};
        require(crypto.random_bytes(wrapping_key.data(), wrapping_key.size()),
                "test key generation failed");
        persisted_ack_case(crypto, wrapping_key, true, false);
        persisted_ack_case(crypto, wrapping_key, false, false);
        persisted_ack_case(crypto, wrapping_key, false, true);
        MemoryBlob store;
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
