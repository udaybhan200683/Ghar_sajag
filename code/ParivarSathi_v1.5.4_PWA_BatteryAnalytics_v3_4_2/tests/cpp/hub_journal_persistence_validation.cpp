#include "firmware/hub/components/storage/journal.hpp"
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

gs::DomainEvent event(std::uint64_t sequence, const char* physical = "device-A") {
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
        std::cout << "P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128 full=129 "
                     "replacement/dedupe/restart/tamper/write-fault\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-HUB-JOURNAL HOST FAIL " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
