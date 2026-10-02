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
        if (physical.size() == 4 && physical.front() == 'c') {
            ++completion_writes;
            const auto fault = completion_fault;
            completion_fault = FaultMode::None;
            if (fault == FaultMode::FailBeforeWrite) return false;
            if (fault == FaultMode::PartialWrite) {
                blobs[physical] = Bytes(value.begin(), value.begin() + value.size()/2);
                return false;
            }
            blobs[physical] = value;
            return fault != FaultMode::PersistThenFail && fault != FaultMode::PowerLossAfterPersist;
        }
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
    FaultMode completion_fault{FaultMode::None};
    std::size_t completion_writes{0};
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
void completion_contract(gs::host::security::OpenSslCommissioningCrypto& crypto) {
    const auto k = key();
    Fixture f;
    HubDurabilityOwner owner(f, f, crypto, k, InstallationFreshness::FreshInstallation);
    check(owner.recover() == DurabilityOwnerState::Ready, "completion owner ready");
    DurableJournalSlotStore store(owner, crypto, k);
    HubJournal journal(128);
    check(journal.attach_persistence(crypto, store, k), "completion journal attaches");
    check(journal.commit(event(1)) == CommitResult::Stored &&
          journal.commit(event(2)) == CommitResult::Stored, "two independent events stored");
    CloudSync cloud(journal);
    check(journal.pending_cloud(128).size() == 2 && cloud.request_for("home", event(1)),
          "incomplete effects remain retryable");
    const auto archived_before = f.blobs;
    const auto reply = BackendCommitReply{BackendReplyStatus::Committed, event(1).key, true, false};
    check(cloud.handle_backend_reply(event(1).key, reply, 0) == BackendReceiptResult::Completed,
          "backend authenticated completion durably publishes receipt");
    check(f.blobs.count("c000") && f.blobs.at("c000").size() == 32 &&
          journal.pending_cloud(128).size() == 1 && !cloud.request_for("home", event(1)) &&
          cloud.request_for("home", event(2)), "completion A never completes B");
    for (const auto& entry : archived_before)
        check(f.blobs.at(entry.first) == entry.second, "completion does not mutate event archive or checkpoint");
    const auto writes = f.completion_writes;
    check(cloud.handle_backend_reply(event(1).key, reply, 0) == BackendReceiptResult::Completed &&
          f.completion_writes == writes, "duplicate completion has no write");
    HubDurabilityOwner reboot(f, f, crypto, k, InstallationFreshness::ExistingInstallation);
    check(reboot.recover() == DurabilityOwnerState::Ready, "new owner accepts independent receipts");
    DurableJournalSlotStore restarted(reboot, crypto, k);
    HubJournal recovered(128);
    check(recovered.attach_persistence(crypto, restarted, k) && recovered.size() == 2 &&
          recovered.cloud_completed(event(1).key) && !recovered.cloud_completed(event(2).key),
          "fresh provider recovers exact completion independent of kind marker");
    CloudSync recovered_cloud(recovered);
    check(!recovered_cloud.request_for("home", event(1)) &&
          recovered_cloud.request_for("home", event(2)), "reboot suppresses completed external request");

    // A report metadata checkpoint leaves unarchived event tail recovery-owned,
    // preserving receipt identity without consuming partial archive chunks.
    RecoveryState report_before;
    check(reboot.durable_store()->recover(report_before), "report checkpoint base recovers");
    RetirementSnapshot snapshot;
    snapshot.storage_epoch = 1; snapshot.generation = 1;
    RetirementSnapshotReference snapshot_ref;
    check(reboot.retirement_repository()->prepare_bank(snapshot, 0, snapshot_ref),
          "report snapshot bank prepares");
    auto report_cp = report_before.checkpoint;
    report_cp.generation = report_before.checkpoint_generation + 1;
    report_cp.covered_ordinal = report_before.checkpoint.covered_ordinal;
    report_cp.report_snapshot = snapshot_ref;
    check(reboot.durable_store()->checkpoint(report_cp), "report checkpoint selects snapshot");
    HubDurabilityOwner report_reboot(f, f, crypto, k, InstallationFreshness::ExistingInstallation);
    check(report_reboot.recover() == DurabilityOwnerState::Ready, "report lifecycle reboot owner");
    DurableJournalSlotStore report_store(report_reboot, crypto, k);
    HubJournal report_journal(128);
    check(report_journal.attach_persistence(crypto, report_store, k) && report_journal.size() == 2 &&
          report_journal.cloud_completed(event(1).key) && !report_journal.cloud_completed(event(2).key),
          "report installation and retry preserve retained events and independent completion");
    RecoveryState report_after;
    check(report_reboot.durable_store()->recover(report_after) && report_after.tail.size() == 2,
          "metadata checkpoint preserves uncovered event tail");

    // Wrong-slot, wrong-event, and corrupted evidence must stop journal attachment.
    for (int mutation = 0; mutation < 3; ++mutation) {
        Fixture bad = f;
        if (mutation == 0) bad.blobs["c001"] = bad.blobs["c000"];
        else if (mutation == 1) {
            Bytes wrong;
            check(HubJournal::encode_completion_receipt(crypto, k, 0, event(99).key, wrong),
                  "wrong identity fixture");
            bad.blobs["c000"] = wrong;
        } else bad.blobs["c000"][0] ^= 1;
        HubDurabilityOwner bad_owner(bad, bad, crypto, k, InstallationFreshness::ExistingInstallation);
        check(bad_owner.recover() == DurabilityOwnerState::Ready, "completion authentication occurs at journal bind");
        DurableJournalSlotStore bad_store(bad_owner, crypto, k);
        HubJournal bad_journal(128);
        check(!bad_journal.attach_persistence(crypto, bad_store, k) && bad_journal.storage_fault(),
              "conflicting or corrupt completion fails closed");
    }

    for (auto fault : {FaultMode::FailBeforeWrite, FaultMode::PartialWrite,
                       FaultMode::PersistThenFail, FaultMode::PowerLossAfterPersist}) {
        Fixture interrupted = f;
        HubDurabilityOwner before(interrupted, interrupted, crypto, k, InstallationFreshness::ExistingInstallation);
        check(before.recover() == DurabilityOwnerState::Ready, "fault owner ready");
        DurableJournalSlotStore before_store(before, crypto, k);
        HubJournal before_journal(128);
        check(before_journal.attach_persistence(crypto, before_store, k), "fault journal ready");
        CloudSync before_cloud(before_journal);
        interrupted.completion_fault = fault;
        const auto response = BackendCommitReply{BackendReplyStatus::Committed, event(2).key, true, false};
        const auto result = before_cloud.handle_backend_reply(event(2).key, response, 0);
        const bool persisted = fault == FaultMode::PersistThenFail || fault == FaultMode::PowerLossAfterPersist;
        check((result == BackendReceiptResult::Completed) == persisted,
              "only exact durable completion readback proves completion");
        HubDurabilityOwner after(interrupted, interrupted, crypto, k, InstallationFreshness::ExistingInstallation);
        check(after.recover() == DurabilityOwnerState::Ready, "interrupted owner restores archives");
        DurableJournalSlotStore after_store(after, crypto, k);
        HubJournal after_journal(128);
        const bool opened = after_journal.attach_persistence(crypto, after_store, k);
        if (fault == FaultMode::PartialWrite) {
            check(!opened && after_journal.storage_fault(), "partial completion fails closed after reboot");
        } else {
            check(opened && after_journal.cloud_completed(event(2).key) == persisted,
                  "before/after commit reboot reconstructs correct completion");
        }
    }

    // Existing archive kind=1 is a compatibility source. Fail before publication,
    // restart, publish independently, and keep the archive bytes unchanged.
    Fixture legacy; seed_legacy(legacy, crypto, k, true);
    HubDurabilityOwner migrating(legacy, legacy, crypto, k, InstallationFreshness::ExistingInstallation);
    check(migrating.recover() == DurabilityOwnerState::MigrationRequired, "kind1 migration owner");
    HubJournal source(128); check(open_legacy(legacy, crypto, k, source), "kind1 source");
    DurableJournalSlotStore destination(migrating, crypto, k);
    check(migrate_legacy_journal(source, legacy, destination) &&
          migrating.recover() == DurabilityOwnerState::Ready, "kind1 archives committed");
    const auto legacy_archives = legacy.blobs;
    legacy.completion_fault = FaultMode::FailBeforeWrite;
    DurableJournalSlotStore failed_publish(migrating, crypto, k);
    HubJournal failed_journal(128);
    check(!failed_journal.attach_persistence(crypto, failed_publish, k),
          "failed legacy publication prevents runtime opening");
    for (const auto& entry : legacy_archives)
        check(legacy.blobs.at(entry.first) == entry.second, "failed publication keeps legacy proof");
    // Stop after publishing one legacy receipt; the next record still has its
    // archive marker. A fresh runtime must safely finish this mixed state.
    Bytes first_receipt; bool first_found = false;
    check(failed_publish.read_completion(0, first_receipt, first_found) && first_found,
          "first legacy receipt publishes independently");
    legacy.completion_fault = FaultMode::FailBeforeWrite;
    DurableJournalSlotStore partial_publish(migrating, crypto, k);
    HubJournal partial_journal(128);
    check(!partial_journal.attach_persistence(crypto, partial_publish, k) &&
          legacy.blobs.count("c000") && !legacy.blobs.count("c001"),
          "interrupted partial legacy publication preserves mixed evidence");
    HubDurabilityOwner resumed(legacy, legacy, crypto, k, InstallationFreshness::ExistingInstallation);
    check(resumed.recover() == DurabilityOwnerState::Ready, "publication restart owner");
    legacy.completion_fault = FaultMode::PowerLossAfterPersist;
    DurableJournalSlotStore resume_store(resumed, crypto, k);
    HubJournal resume_journal(128);
    check(resume_journal.attach_persistence(crypto, resume_store, k) &&
          resume_journal.cloud_completed_count() == 2 && legacy.blobs.count("c000") && legacy.blobs.count("c001"),
          "legacy completion independently published and verified after interrupted API");
    for (const auto& entry : legacy_archives)
        check(legacy.blobs.at(entry.first) == entry.second, "legacy kind1 markers remain intact");
    const auto publications = legacy.completion_writes;
    HubDurabilityOwner again(legacy, legacy, crypto, k, InstallationFreshness::ExistingInstallation);
    check(again.recover() == DurabilityOwnerState::Ready, "published legacy completion restart");
    DurableJournalSlotStore again_store(again, crypto, k);
    HubJournal again_journal(128);
    check(again_journal.attach_persistence(crypto, again_store, k) &&
          again_journal.pending_cloud(128).empty() && legacy.completion_writes == publications,
          "legacy publication idempotent and replay suppression preserved");

    check(again_journal.commit(event(3)) == CommitResult::Stored &&
          again_journal.commit(event(4)) == CommitResult::Stored,
          "new events coexist with legacy-completed archives");
    CloudSync mixed_cloud(again_journal);
    const auto mixed_reply = BackendCommitReply{BackendReplyStatus::Committed, event(4).key, true, false};
    check(mixed_cloud.handle_backend_reply(event(4).key, mixed_reply, 0) == BackendReceiptResult::Completed,
          "new completion coexists with old published markers");
    HubDurabilityOwner mixed_owner(legacy, legacy, crypto, k, InstallationFreshness::ExistingInstallation);
    check(mixed_owner.recover() == DurabilityOwnerState::Ready, "mixed evidence owner recovery");
    DurableJournalSlotStore mixed_store(mixed_owner, crypto, k);
    HubJournal mixed_journal(128);
    check(mixed_journal.attach_persistence(crypto, mixed_store, k) && mixed_journal.size() == 4 &&
          mixed_journal.cloud_completed_count() == 3 && mixed_journal.pending_cloud(128).size() == 1 &&
          mixed_journal.pending_cloud(128).front().key.str() == event(3).key.str(),
          "mixed legacy/new completion retains incomplete event exactly");

    Fixture full;
    HubDurabilityOwner full_owner(full, full, crypto, k, InstallationFreshness::FreshInstallation);
    check(full_owner.recover() == DurabilityOwnerState::Ready, "boundary owner ready");
    DurableJournalSlotStore full_store(full_owner, crypto, k);
    HubJournal full_journal(128);
    check(full_journal.attach_persistence(crypto, full_store, k), "boundary journal attaches");
    CloudSync full_cloud(full_journal);
    RetirementSnapshot full_snapshot;
    full_snapshot.storage_epoch = 1; full_snapshot.generation = 1;
    RetirementSnapshotReference full_snapshot_ref;
    check(full_owner.retirement_repository()->prepare_bank(full_snapshot, 0, full_snapshot_ref),
          "boundary report snapshot prepared");
    for (std::uint64_t i = 1; i <= 128; ++i) {
        check(full_journal.commit(event(i)) == CommitResult::Stored, "retained boundary event");
        const auto success = BackendCommitReply{BackendReplyStatus::Committed, event(i).key, true, false};
        check(full_cloud.handle_backend_reply(event(i).key, success, 0) == BackendReceiptResult::Completed,
              "all 128 effect identities independently complete");
        RecoveryState metadata_before;
        check(full_owner.durable_store()->recover(metadata_before), "boundary metadata base");
        auto metadata = metadata_before.checkpoint;
        metadata.generation = metadata_before.checkpoint_generation + 1;
        metadata.report_snapshot = full_snapshot_ref;
        check(full_owner.durable_store()->checkpoint(metadata),
              "report after every event preserves archive batching and tail");
    }
    check(full_journal.size() == 128 && full_journal.pending_cloud(128).empty() &&
          full_journal.commit(event(129)) == CommitResult::Full && full.blobs.count("c127"),
          "completion neither retires payload nor frees logical event capacity");
    HubDurabilityOwner full_reboot(full, full, crypto, k, InstallationFreshness::ExistingInstallation);
    check(full_reboot.recover() == DurabilityOwnerState::Ready, "128 receipt inventory remains bounded");
    DurableJournalSlotStore full_reboot_store(full_reboot, crypto, k);
    HubJournal full_recovered(128);
    check(full_recovered.attach_persistence(crypto, full_reboot_store, k) &&
          full_recovered.size() == 128 && full_recovered.cloud_completed_count() == 128,
          "all retained history and independent completion survives reboot");
    std::cout << "Independent backend completion contract validation passed\n";
}

}  // namespace

int main() {
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        run(crypto);
        completion_contract(crypto);
        std::cout << "Hub journal migration validation passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Hub journal migration validation failed: " << error.what() << '\n';
        return 1;
    }
}
