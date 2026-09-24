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
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        Key32 wrapping_key{};
        require(crypto.random_bytes(wrapping_key.data(), wrapping_key.size()),
                "test key generation failed");
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
        std::cout << "P2-PERSIST-NODE-RECOVERY HOST PASS encrypted bounded recovery\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-NODE-RECOVERY HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
