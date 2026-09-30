#include "firmware/hub/components/cloud/cloud_sync.hpp"
#include "firmware/hub/components/storage/durable_journal_slot_store.hpp"
#include "firmware/hub/target/esp32/nvs_durable_key_codec.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <array>
#include <iostream>
#include <map>
#include <stdexcept>

namespace {
using namespace gs::hub;
using namespace gs::hub::durable;
using namespace gs::hub::target;
using gs::security::Bytes;
using gs::security::Key32;

void check(bool value, const char* why) { if (!value) throw std::runtime_error(why); }

Key32 key() {
    Key32 value{};
    for (std::size_t i = 0; i < value.size(); ++i) value[i] = static_cast<std::uint8_t>(i + 9);
    return value;
}

gs::DomainEvent event(std::uint64_t sequence) {
    gs::DomainEvent value;
    value.key = {"room-1", 72, sequence, "device-1"};
    value.kind = gs::EventKind::Motion;
    value.location = "Kitchen";
    value.occurred_at = 100 + sequence;
    value.received_at = 101 + sequence;
    value.battery_mv = 3800;
    return value;
}

class Fixture final : public BlobStore, public StoreInventory, public JournalSlotStore {
public:
    bool read(const std::string& logical, Bytes& value, bool& found) override {
        std::string physical;
        if (!durable_logical_to_physical_key(logical, physical)) return false;
        const auto item = blobs.find(physical);
        found = item != blobs.end(); value = found ? item->second : Bytes{}; return true;
    }
    bool write_immutable(const std::string& logical, const Bytes& value) override {
        if (fail_writes) return false;
        std::string physical;
        if (!durable_logical_to_physical_key(logical, physical) || blobs.count(physical)) return false;
        blobs[physical] = value; return true;
    }
    bool replace(const std::string& logical, const Bytes& value) override {
        if (fail_writes) return false;
        std::string physical;
        if (!durable_logical_to_physical_key(logical, physical)) return false;
        blobs[physical] = value; return true;
    }
    InventorySnapshot scan() override {
        InventorySnapshot out;
        for (const auto& [physical, bytes] : blobs) {
            (void)bytes;
            DurablePhysicalKeyRecord record;
            if (!durable_physical_key_record(physical, record) || out.count == out.records.size()) {
                out.status = InventoryStatus::MalformedRecord; return out;
            }
            out.records[out.count++] = {static_cast<InventoryRecord::Kind>(record.kind), record.id};
        }
        for (std::size_t i = 0; i < events.size(); ++i) {
            if (!events[i].empty()) out.records[out.count++] = {InventoryRecord::LegacyEvent, i};
            if (!completions[i].empty()) out.records[out.count++] = {InventoryRecord::LegacyCompletion, i};
        }
        bool old = false, current = false;
        for (std::size_t i = 0; i < out.count; ++i) {
            const auto kind = out.records[i].kind;
            old |= kind == InventoryRecord::LegacyEvent || kind == InventoryRecord::LegacyCompletion;
            current |= !(kind == InventoryRecord::LegacyEvent || kind == InventoryRecord::LegacyCompletion);
        }
        out.status = old && current ? InventoryStatus::KnownMixedRecords :
                     old ? InventoryStatus::KnownLegacyRecords :
                     current ? InventoryStatus::KnownCurrentRecords : InventoryStatus::Empty;
        return out;
    }
    bool read(std::size_t slot, Bytes& value, bool& found) override {
        if (slot >= events.size()) return false;
        value = events[slot]; found = !value.empty(); return true;
    }
    bool write(std::size_t slot, const Bytes& value) override {
        if (slot >= events.size() || !events[slot].empty()) return false;
        events[slot] = value; return true;
    }
    bool read_completion(std::size_t slot, Bytes& value, bool& found) override {
        if (slot >= completions.size()) return false;
        value = completions[slot]; found = !value.empty(); return true;
    }
    bool write_completion(std::size_t slot, const Bytes& value) override {
        if (slot >= completions.size() || !completions[slot].empty()) return false;
        completions[slot] = value; return true;
    }
    bool erase(std::size_t slot) override {
        if (fail_erase || fail_event_erase) return false;
        if (slot >= events.size()) return false;
        events[slot].clear(); return true;
    }
    bool erase_completion(std::size_t slot) override {
        if (fail_erase) return false;
        if (slot >= completions.size()) return false;
        completions[slot].clear(); return true;
    }
    std::map<std::string, Bytes> blobs;
    std::array<Bytes, 128> events{}, completions{};
    bool fail_writes{false}, fail_erase{false}, fail_event_erase{false};
};

void seed_legacy(Fixture& fixture, gs::host::security::OpenSslCommissioningCrypto& crypto,
                 const Key32& event_key, bool completed) {
    HubJournal old(128);
    check(old.attach_persistence(crypto, fixture, event_key), "legacy journal attaches");
    const auto first = event(1), second = event(2);
    check(old.commit(first) == CommitResult::Stored && old.commit(second) == CommitResult::Stored,
          "legacy events stored");
    if (completed) {
        CloudSync cloud(old);
        cloud.set_connected(true, 0);
        const auto reply = BackendCommitReply{BackendReplyStatus::Committed, first.key, true, false};
        check(cloud.handle_backend_reply(first.key, reply, 0) == BackendReceiptResult::Completed,
              "legacy backend receipt stored");
        const auto second_reply = BackendCommitReply{BackendReplyStatus::Committed, second.key, true, false};
        check(cloud.handle_backend_reply(second.key, second_reply, 0) == BackendReceiptResult::Completed,
              "second legacy backend receipt stored");
    }
}

bool open_legacy(Fixture& fixture, gs::host::security::OpenSslCommissioningCrypto& crypto,
                 const Key32& event_key, HubJournal& journal) {
    return journal.attach_persistence(crypto, fixture, event_key);
}

void run(gs::host::security::OpenSslCommissioningCrypto& crypto) {
    const auto storage_key = key();
    Key32 event_key = storage_key;
    // Clean copy, receipt preservation, restart, repeat migration, and stable epoch.
    Fixture clean; seed_legacy(clean, crypto, event_key, true);
    HubDurabilityOwner owner(clean, clean, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(owner.recover() == DurabilityOwnerState::MigrationRequired && !owner.epoch() &&
          owner.migration_epoch() == 1, "legacy owner gates admission but preserves epoch");
    HubJournal legacy(128);
    check(open_legacy(clean, crypto, event_key, legacy), "legacy source reopens");
    DurableJournalSlotStore durable(owner, crypto, event_key);
    check(migrate_legacy_journal(legacy, clean, durable), "clean migration commits");
    check(clean.events[0].empty() && clean.events[1].empty() &&
          clean.completions[0].empty(), "source data erased after committed copy");
    check(owner.recover() == DurabilityOwnerState::Ready && owner.epoch() == 1,
          "owner ready at same epoch after migration");
    check(migrate_legacy_journal(legacy, clean, durable), "repeated migration is idempotent");
    HubDurabilityOwner reboot(clean, clean, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(reboot.recover() == DurabilityOwnerState::Ready && reboot.epoch() == 1,
          "restart preserves migrated epoch");
    DurableJournalSlotStore reboot_store(reboot, crypto, event_key);
    HubJournal restored(128);
    check(restored.attach_persistence(crypto, reboot_store, event_key) && restored.size() == 2 &&
          restored.cloud_completed(event(1).key) && restored.cloud_completed(event(2).key),
          "migrated events and receipt recover");

    // Failure before the first durable transition leaves every old source slot intact.
    Fixture before; seed_legacy(before, crypto, event_key, false);
    HubDurabilityOwner before_owner(before, before, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(before_owner.recover() == DurabilityOwnerState::MigrationRequired, "precommit owner state");
    HubJournal before_legacy(128); check(open_legacy(before, crypto, event_key, before_legacy), "precommit source opens");
    DurableJournalSlotStore before_store(before_owner, crypto, event_key);
    before.fail_writes = true;
    check(!migrate_legacy_journal(before_legacy, before, before_store) &&
          !before.events[0].empty() && !before.events[1].empty(), "interrupted precommit preserves source");
    before.fail_writes = false;
    HubDurabilityOwner before_resume(before, before, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(before_resume.recover() == DurabilityOwnerState::MigrationRequired,
          "precommit restart remains migration gated");
    DurableJournalSlotStore before_resume_store(before_resume, crypto, event_key);
    check(migrate_legacy_journal(before_legacy, before, before_resume_store), "precommit migration resumes");

    // Fail the first legacy erase after durable checkpoint and verification.
    Fixture after; seed_legacy(after, crypto, event_key, true);
    HubDurabilityOwner after_owner(after, after, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(after_owner.recover() == DurabilityOwnerState::MigrationRequired, "postcommit owner state");
    HubJournal after_legacy(128); check(open_legacy(after, crypto, event_key, after_legacy), "postcommit source opens");
    DurableJournalSlotStore after_store(after_owner, crypto, event_key);
    after.fail_erase = true;
    check(!migrate_legacy_journal(after_legacy, after, after_store) &&
          !after.events[0].empty() && !after.events[1].empty(), "postcommit interruption retains source");
    after.fail_erase = false;
    HubDurabilityOwner after_resume(after, after, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(after_resume.recover() == DurabilityOwnerState::MigrationRequired &&
          after_resume.migration_epoch() == 1, "postcommit restart recovers same epoch");
    DurableJournalSlotStore after_resume_store(after_resume, crypto, event_key);
    check(migrate_legacy_journal(after_legacy, after, after_resume_store), "postcommit migration resumes");
    check(after_resume.recover() == DurabilityOwnerState::Ready && after_resume.epoch() == 1,
          "postcommit restart reaches ready at stable epoch");

    Fixture partial_cleanup; seed_legacy(partial_cleanup, crypto, event_key, true);
    HubDurabilityOwner partial_owner(partial_cleanup, partial_cleanup, crypto, storage_key,
                                     InstallationFreshness::ExistingInstallation);
    check(partial_owner.recover() == DurabilityOwnerState::MigrationRequired,
          "partial cleanup owner enters migration");
    HubJournal partial_source(128);
    check(open_legacy(partial_cleanup, crypto, event_key, partial_source),
          "partial cleanup source attaches");
    DurableJournalSlotStore partial_store(partial_owner, crypto, event_key);
    partial_cleanup.fail_event_erase = true;
    check(!migrate_legacy_journal(partial_source, partial_cleanup, partial_store) &&
          partial_cleanup.completions[1].empty() && !partial_cleanup.events[1].empty(),
          "interrupted cleanup can remove receipt only after durable commit");
    partial_cleanup.fail_event_erase = false;
    HubDurabilityOwner partial_resume(partial_cleanup, partial_cleanup, crypto, storage_key,
                                      InstallationFreshness::ExistingInstallation);
    check(partial_resume.recover() == DurabilityOwnerState::MigrationRequired,
          "partial cleanup restart stays admission gated");
    HubJournal partial_reopened(128);
    check(open_legacy(partial_cleanup, crypto, event_key, partial_reopened) &&
          !partial_reopened.cloud_completed(event(2).key),
          "missing legacy receipt does not fabricate source completion");
    DurableJournalSlotStore partial_resume_store(partial_resume, crypto, event_key);
    check(migrate_legacy_journal(partial_reopened, partial_cleanup, partial_resume_store) &&
          partial_resume.recover() == DurabilityOwnerState::Ready && partial_resume.epoch() == 1,
          "partial cleanup restart is idempotent and reaches ready");
    DurableJournalSlotStore partial_final_store(partial_resume, crypto, event_key);
    HubJournal partial_final(128);
    check(partial_final.attach_persistence(crypto, partial_final_store, event_key) &&
          partial_final.size() == 2 && partial_final.cloud_completed(event(2).key),
          "committed receipt survives receipt-first legacy cleanup");

    // Empty legacy store is a no-op; a completion with no matching event fails closed.
    Fixture empty;
    HubDurabilityOwner empty_owner(empty, empty, crypto, storage_key, InstallationFreshness::FreshInstallation);
    check(empty_owner.recover() == DurabilityOwnerState::Ready, "empty new owner ready");
    HubJournal empty_legacy(128); check(open_legacy(empty, crypto, event_key, empty_legacy), "empty source opens");
    DurableJournalSlotStore empty_store(empty_owner, crypto, event_key);
    check(migrate_legacy_journal(empty_legacy, empty, empty_store), "no legacy records is a no-op");
    Fixture orphan; orphan.completions[0] = Bytes{1,2,3};
    HubDurabilityOwner orphan_owner(orphan, orphan, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(orphan_owner.recover() == DurabilityOwnerState::MigrationRequired, "orphan source requires migration");
    HubJournal orphan_legacy(128);
    check(!open_legacy(orphan, crypto, event_key, orphan_legacy) && !orphan.completions[0].empty(),
          "orphan completion fails closed and is preserved");

    // New runtime events use the durable path and survive a fresh process owner.
    Fixture live;
    HubDurabilityOwner live_owner(live, live, crypto, storage_key, InstallationFreshness::FreshInstallation);
    check(live_owner.recover() == DurabilityOwnerState::Ready && live_owner.epoch() == 1,
          "fresh event owner initialized");
    DurableJournalSlotStore live_store(live_owner, crypto, event_key);
    HubJournal live_journal(128);
    check(live_journal.attach_persistence(crypto, live_store, event_key), "new durable journal attaches");
    const auto live_result = live_journal.commit(event(7));
    check(live_result == CommitResult::Stored, "new event commits to durable owner");
    auto largest_event = event(8);
    largest_event.key.physical_device_id = std::string(64, 'p');
    largest_event.key.source_id = std::string(24, 's');
    largest_event.location = std::string(64, 'l');
    largest_event.kind = gs::EventKind::MotionSummary;
    largest_event.motion_aggregate = gs::DomainEvent::MotionAggregate{1, 1, 2};
    check(live_journal.commit(largest_event) == CommitResult::Stored,
          "largest supported DomainEvent commits within transition bound");
    for (std::uint64_t sequence = 9; sequence <= 11; ++sequence) {
        const auto result = live_journal.commit(event(sequence));
        check(result == CommitResult::Stored, "additional durable event commits");
    }
    HubDurabilityOwner live_reboot(live, live, crypto, storage_key, InstallationFreshness::ExistingInstallation);
    check(live_reboot.recover() == DurabilityOwnerState::Ready && live_reboot.epoch() == 1,
          "live event owner restarts with stable epoch");
    DurableJournalSlotStore live_reboot_store(live_reboot, crypto, event_key);
    HubJournal live_recovered(128);
    check(live_recovered.attach_persistence(crypto, live_reboot_store, event_key) &&
          live_recovered.size() == 5 && live_recovered.records()[0].key.str() == event(7).key.str() &&
          live_recovered.records()[1].key.str() == largest_event.key.str() &&
          live_recovered.records()[4].key.str() == event(11).key.str(),
          "new durable-path event recovers");
}
}  // namespace

int main() {
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        run(crypto);
        std::cout << "Hub journal migration validation passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Hub journal migration validation failed: " << error.what() << '\n';
        return 1;
    }
}
