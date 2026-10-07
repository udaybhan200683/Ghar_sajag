#include "firmware/hub/components/storage/hub_durability_owner.hpp"
#include "firmware/hub/components/storage/durable_journal_slot_store.hpp"
#include "firmware/hub/components/registry/registry_persistence.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/target/esp32/nvs_durable_key_codec.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/security/rejoin_protocol.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <algorithm>
#include <iostream>
#include <map>
#include <stdexcept>
#include <chrono>
#include <thread>
using namespace gs; using namespace gs::hub; using namespace gs::hub::durable; using namespace gs::hub::target;
using security::Bytes; using security::Key32;
namespace {
void check(bool b,const char* m){if(!b)throw std::runtime_error(m);}
class Fixture final : public BlobStore, public StoreInventory {
public:
    bool read(const std::string& logical, Bytes& value, bool& found) override {
        if (read_failure) return false;
        if (slow_checkpoint_read && logical == "cp0")
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
        std::string physical;
        if (!durable_logical_to_physical_key(logical, physical)) return false;
        const auto it = values.find(physical); found = it != values.end();
        value = found ? it->second : Bytes{}; return true;
    }
    bool write_immutable(const std::string& k, const Bytes& b) override { return write(k,b,true); }
    bool replace(const std::string& k, const Bytes& b) override { return write(k,b,false); }
    bool erase_if_equals(const std::string& logical, const Bytes& expected) override {
        std::string physical;
        DurablePhysicalKeyRecord record;
        if (!durable_logical_to_physical_key(logical, physical) ||
            !durable_physical_key_record(physical, record) || expected.empty() ||
            record.kind == DurablePhysicalKeyKind::LegacyEvent ||
            record.kind == DurablePhysicalKeyKind::LegacyCompletion) return false;
        const auto found = values.find(physical);
        if (found == values.end()) return true;
        if (found->second != expected) return false;
        values.erase(found);
        return values.count(physical) == 0;
    }
    bool write(const std::string& logical, const Bytes& bytes, bool immutable) {
        ++writes;
        std::string physical;
        if (!durable_logical_to_physical_key(logical, physical)) return false;
        auto it=values.find(physical);
        if (immutable && it!=values.end()) { immutable_collision=true; return false; }
        if (fail_at != writes) { values[physical]=bytes; return true; }
        switch (fault) {
            case FaultMode::FailBeforeWrite: return false;
            case FaultMode::PartialWrite: values[physical]=Bytes(bytes.begin(),bytes.begin()+bytes.size()/2); return false;
            case FaultMode::PersistThenFail:
            case FaultMode::PowerLossAfterPersist: values[physical]=bytes; return false;
            case FaultMode::None: values[physical]=bytes; return true;
        }
        return false;
    }
    InventorySnapshot scan() override {
        ++scans;
        InventorySnapshot out; out.status=forced_status.value_or(InventoryStatus::Empty);
        if (forced_status) return out;
        for (const auto& entry: values) {
            DurablePhysicalKeyRecord r;
            if (!durable_physical_key_record(entry.first,r)) {
                const auto& p=entry.first;
                const bool family=p.rfind("ef",0)==0||p.rfind("ev",0)==0||p.rfind("cp",0)==0||
                    p.rfind("sel",0)==0||p.rfind("tr",0)==0||p.rfind("bm",0)==0||
                    p.rfind("ret",0)==0||p.rfind("mig",0)==0||(!p.empty()&&(p[0]=='e'||p[0]=='c'));
                out.status=family?InventoryStatus::MalformedRecord:InventoryStatus::UnknownOrphanRecord; return out;
            }
            if (out.count==out.records.size()) { out.status=InventoryStatus::LimitExceeded; return out; }
            out.records[out.count++]={static_cast<InventoryRecord::Kind>(r.kind),r.id};
        }
        bool cur=false, legacy=false;
        for(std::size_t i=0;i<out.count;++i) {
            const auto k=out.records[i].kind;
            if(k==InventoryRecord::LegacyEvent||k==InventoryRecord::LegacyCompletion) legacy=true;
            else cur=true;
        }
        out.status=cur&&legacy?InventoryStatus::KnownMixedRecords:legacy?InventoryStatus::KnownLegacyRecords:
                   cur?InventoryStatus::KnownCurrentRecords:InventoryStatus::Empty;
        return out;
    }
    std::map<std::string,Bytes> values;
    std::optional<InventoryStatus> forced_status;
    std::size_t writes{0}, scans{0};
    std::size_t fail_at{0};
    FaultMode fault{FaultMode::None};
    bool read_failure{false}, immutable_collision{false};
    bool slow_checkpoint_read{false};
};

class RegistryBlob final : public security::SecurityBlobStore {
public:
    Bytes data;
    bool read(Bytes& out, bool& found) override {
        out = data; found = !data.empty(); return true;
    }
    bool write(const Bytes& value) override { data = value; return true; }
};

void gate(std::uint64_t origin = 7) {
    const bool reported = origin >= 1502;
    const std::uint64_t transport_session = reported ? 1503 : 7;
    host::security::OpenSslCommissioningCrypto crypto;
    Key32 key{}; key.fill(9);
    Fixture storage;
    check(storage.values.empty(), "genuinely empty storage");
    HubDurabilityOwner owner(storage, storage, crypto, key, InstallationFreshness::FreshInstallation);
    check(owner.recover() == DurabilityOwnerState::Ready, "fresh genesis Ready");
    check(owner.recovery_state()->checkpoint.fresh_registry_domain &&
          owner.recovery_state()->checkpoint.registry_owner_domain, "native registry ownership genesis");
    check(!storage.values.count("mig0") && !storage.values.count("mig1"), "no fabricated migration");

    NodeRegistry registry("home", "hub", 10, 16);
    EnrolledNode node;
    node.device_id = "device"; node.logical_id = "pir";
    node.home_id = "home"; node.hub_id = "hub";
    node.room = "room"; node.function = "motion"; node.last_session = transport_session - 1;
    check(crypto.generate_test_identity("node") &&
          crypto.identity_public_key("node", node.p256_public_key), "node identity");
    node.radio_mac = {1, 2, 3, 4, 5, 6};
    check(registry.enroll(node) == RegistryResult::Accepted, "registry enrollment");
    // Commissioning/rejoin mutual-proof gates are separate. Here a trusted
    // commissioning result is persisted and read back through the real codec.
    security::CommissioningBinding binding;
    binding.device_id = node.device_id; binding.logical_id = node.logical_id;
    binding.home_id = "home"; binding.hub_id = "hub";
    binding.room = "room"; binding.function = "motion";
    binding.device_public_key = node.p256_public_key; binding.installation_key = key;
    check(crypto.generate_test_identity("hub") &&
          crypto.identity_public_key("hub", binding.hub_public_key), "hub identity");
    RegistryBlob registry_blob;
    HubRegistryRepository repository(crypto, registry_blob, key, "home", "hub",
                                     binding.hub_public_key, 10, 16);
    HubRegistryState candidate{registry.snapshot(), {binding}, {}};
    check(repository.save(candidate), "fresh registry authenticated save");
    auto load = repository.load();
    registry = NodeRegistry("home", "hub", 10, 16);
    check(load.status == HubRegistryLoadStatus::Ready && load.schema_version == 2 &&
          load.state && load.state->migration.phase == RegistryMigrationPhase::FreshInstallation &&
          registry.restore(load.state->registry), "native registry authenticated restore");
    check(load.state->migration.source_epoch == 0 &&
          load.state->migration.source_checkpoint_generation == 0, "registry has no migration source");
    check(repository.save(*load.state), "native registry update preserves ownership");

    auto resolver = [&](const std::string& physical, const std::string& logical,
                        DurableJournalSlotStore::EnrollmentOwner& out) {
        auto record = registry.find(physical);
        if (!record || record->logical_id != logical || record->quarantined ||
            record->home_id != "home" || record->hub_id != "hub") return false;
        const auto& descriptor = registry.enrollment_slots()[record->enrollment_slot];
        if (descriptor.state != EnrollmentSlotState::Active || descriptor.device_id != physical ||
            descriptor.generation != record->enrollment_generation) return false;
        out = {record->enrollment_slot, record->enrollment_generation, descriptor.owner_digest};
        return true;
    };
    if (reported) {
        // Mirror the target report publication path: two authenticated pending
        // reports rotate the native root from generation 2 to generation 4.
        RetirementSnapshot current; current.storage_epoch = 1;
        DurableJournalSlotStore::EnrollmentOwner enrollment;
        check(resolver("device", "pir", enrollment), "report enrollment binding");
        Key32 report_key{};
        check(transport::derive_retirement_report_key(crypto, binding.installation_key, report_key), "report key");
        for (std::uint64_t generation = 1; generation <= 2; ++generation) {
            transport::NodeRetirementReportV1 report;
            report.epoch = 1; report.generation = generation;
            report.current_origin_session = generation == 1 ? 1502 : 1503;
            report.durable_admission_highwater = 1;
            report.pending_count = static_cast<std::uint8_t>(generation);
            report.pending[0] = {1502, 1};
            if (generation == 2) report.pending[1] = {1503, 1};
            transport::RetirementFragmentSet fragments;
            check(transport::fragment_retirement_report(crypto, report_key, report, fragments), "report fragments");
            transport::RetirementReportReassembler assembly;
            transport::NodeRetirementReportV1 verified;
            Key32 hmac{};
            security::RuntimeFrameSecurity tx(crypto, binding), rx(crypto, binding);
            check(tx.start(transport_session, key) && rx.start(transport_session, key), "report AEAD session");
            for (std::size_t i = 0; i < fragments.count; ++i) {
                security::SecureFrame secure; transport::EncodedFrame plain;
                check(tx.seal(security::RuntimeDirection::Uplink, fragments.frames[i], secure) &&
                      rx.open(security::RuntimeDirection::Uplink, secure, plain), "report AEAD");
                const auto result = assembly.accept(crypto, report_key, plain, verified, hmac);
                check(result == (i + 1 == fragments.count ? transport::RetirementAssemblyResult::Complete :
                               transport::RetirementAssemblyResult::AcceptedFragment), "report HMAC verification");
            }
            RetirementSnapshot candidate;
            auto* reports = owner.retirement_repository();
            check(reports->apply_authenticated_report(current, enrollment.owner_digest, enrollment.slot,
                     enrollment.generation, transport_session, verified, hmac, candidate) == RetirementReportApply::Prepared,
                  "authenticated pending report");
            RecoveryState before;
            check(owner.durable_store()->recover(before), "report checkpoint input");
            ReportSnapshotReference ref;
            const auto banks = before.checkpoint.report_snapshot ?
                static_cast<std::uint8_t>(1U << before.checkpoint.report_snapshot->bank) : 0;
            check(reports->prepare_bank(candidate, banks, ref), "report bank readback");
            auto cp = before.checkpoint; cp.generation = before.checkpoint_generation + 1;
            cp.report_snapshot = ref;
            check(owner.durable_store()->checkpoint(cp), "report metadata checkpoint");
            current = candidate;
        }
    }
    HubDurabilityOwner first_boot(storage, storage, crypto, key, InstallationFreshness::ExistingInstallation);
    check(first_boot.recover() == DurabilityOwnerState::Ready, "pre-first-event reboot Ready");
    check(first_boot.epoch() == 1 && first_boot.recovery_state()->checkpoint_generation == (reported ? 4 : 2) &&
          first_boot.recovery_state()->checkpoint.fresh_registry_domain &&
          first_boot.recovery_state()->checkpoint.registry_owner_domain,
          "recovered native checkpoint ownership");
    auto registry_before_event = repository.load();
    registry = NodeRegistry("home", "hub", 10, 16);
    check(registry_before_event.state && registry.restore(registry_before_event.state->registry), "enrollment reboot restore");
    security::NodeRejoin joining(crypto, binding, transport_session);
    security::HubRejoin hub_join(crypto, binding, transport_session - 1);
    auto hello = joining.begin(); check(bool(hello), "rejoin hello");
    auto challenge = hub_join.accept(*hello); check(bool(challenge), "rejoin challenge");
    auto final = joining.accept(*challenge); check(bool(final), "rejoin mutual proof");
    auto ack = hub_join.confirm(*final); check(ack && joining.commit(*ack), "rejoin committed");
    check(registry.rejoin("device", node.radio_mac, transport_session) == RegistryResult::Accepted, "registry authenticated session");
    auto updated = *registry_before_event.state; updated.registry = registry.snapshot();
    check(repository.save(updated), "rejoin registry persistence");
    const auto rejoined_state = repository.load();
    check(rejoined_state.status == HubRegistryLoadStatus::Ready && rejoined_state.state &&
          rejoined_state.state->migration.phase == RegistryMigrationPhase::FreshInstallation &&
          rejoined_state.state->migration.source_epoch == 0,
          "rejoin preserves native registry ownership without migration");
    if (reported) {
        Fixture probe_storage = storage;
        DurableStore probe(probe_storage, crypto, key, 1);
        Transition candidate;
        candidate.type = TransitionType::Event; candidate.registry_owner_domain = true;
        candidate.event = {"device", "pir", origin, 1}; candidate.enrollment_slot = 0;
        candidate.enrollment_generation = 1; candidate.event_digest.fill(1);
        candidate.causal_input = {1}; candidate.decision = {0, 0, 0, 0};
        const auto status = probe.commit(candidate);
        std::cout << "R1-FIRST-EVENT probe origin=" << origin << " native=1 generation=4 commit="
                  << (status == CommitStatus::Conflict ? "Conflict" : status == CommitStatus::Committed ? "Committed" : "OTHER") << '\n';
        check(status == CommitStatus::Committed, "reported pending key must remain eligible");
        check(probe.commit(candidate) == CommitStatus::Committed, "reported pending exact duplicate");
        auto conflict = candidate; conflict.event_digest[0] ^= 1;
        check(probe.commit(conflict) == CommitStatus::Conflict, "reported pending digest conflict remains closed");
        auto retired = candidate; retired.event.session_id = 1501;
        check(probe.commit(retired) == CommitStatus::NotCommitted, "covered absent key remains retired");
    }
    DurableJournalSlotStore slots(first_boot, crypto, key, resolver);
    HubRuntime runtime(4, 128);
    runtime.bind_durability_owner(first_boot); runtime.authorize_node("pir", transport_session, true);
    RoutineConfig config;
    config.window_id = "morning"; config.end_at = 100; config.grace_end_at = 120;
    runtime.start_window(config, HomeMode::Home);
    check(runtime.journal().attach_persistence(crypto, slots, key), "production journal attached");
    NodeMessage message;
    message.node_id = "pir"; message.session_id = origin; message.sequence_number = 1;
    message.sensor_type = SensorType::Pir; message.event_type = EventKind::Motion;
    message.location = "room"; message.occurred_at = 10; message.battery_mv = 3800;
    security::RuntimeFrameSecurity node_radio(crypto, binding), hub_radio(crypto, binding);
    check(node_radio.start(transport_session, *joining.session_salt()) && hub_radio.start(transport_session, *hub_join.session_salt()), "authenticated transport session");
    auto admit = [&](HubRuntime& target) {
        auto encoded = transport::encode_node_message(message);
        check(bool(encoded), "wire encode");
        security::SecureFrame secure;
        transport::EncodedFrame plain;
        check(node_radio.seal(security::RuntimeDirection::Uplink, encoded.frame, secure) &&
              hub_radio.open(security::RuntimeDirection::Uplink, secure, plain), "uplink AEAD");
        auto decoded = transport::decode_node_message(plain.bytes.data(), plain.size);
        check(bool(decoded) && target.authenticated_radio_message_callback(
                  *decoded.value, "pir", "device", transport_session, 11), "authenticated runtime admission");
        return target.run_state_once();
    };
    auto first = admit(runtime);
    if (reported) std::cout << "R1-FIRST-EVENT runtime ack=" << (first ? static_cast<int>(first->ack) : -1) << " records=" << runtime.journal().size() << " state_changed=" << (first && first->state_changed) << "\n";
    check(first && first->ack == AckClass::Durable && first->state_changed &&
          runtime.journal().size() == 1 && runtime.routine_state().evidence_ids.size() == 1,
          "first event durable with exactly one logical effect");
    RecoveryState committed;
    check(first_boot.durable_store()->recover(committed) && committed.last_ordinal == 1 &&
          committed.tail.size() == 1, "durable commit precedes ACK");

    // Reconstruct all authorization and durability objects as a Hub reboot would.
    auto registry_reboot = repository.load();
    registry = NodeRegistry("home", "hub", 10, 16);
    check(registry_reboot.status == HubRegistryLoadStatus::Ready && registry_reboot.state &&
          registry.restore(registry_reboot.state->registry), "registry reboot recovery");
    HubDurabilityOwner reboot(storage, storage, crypto, key, InstallationFreshness::ExistingInstallation);
    check(reboot.recover() == DurabilityOwnerState::Ready, "durability reboot Ready");
    DurableJournalSlotStore restored_slots(reboot, crypto, key, resolver);
    HubRuntime restored(4, 128);
    restored.bind_durability_owner(reboot); restored.authorize_node("pir", transport_session + 1, true);
    restored.start_window(config, HomeMode::Home);
    check(restored.journal().attach_persistence(crypto, restored_slots, key) &&
          restored.restore_from_journal(), "durable event rebuilds reducer");
    check(node_radio.start(transport_session + 1, key) && hub_radio.start(transport_session + 1, key), "new transport session after reboot");
    auto replay = [&]() {
        auto encoded = transport::encode_node_message(message);
        check(bool(encoded), "old retained EventKey encode");
        security::SecureFrame secure;
        transport::EncodedFrame plain;
        check(node_radio.seal(security::RuntimeDirection::Uplink, encoded.frame, secure) &&
              hub_radio.open(security::RuntimeDirection::Uplink, secure, plain), "retry AEAD");
        auto decoded = transport::decode_node_message(plain.bytes.data(), plain.size);
        check(bool(decoded) && restored.authenticated_radio_message_callback(
                  *decoded.value, "pir", "device", transport_session + 1, 12), "old EventKey in new transport session");
        return restored.run_state_once();
    };
    auto duplicate = replay();
    check(duplicate && duplicate->ack == AckClass::Durable && !duplicate->state_changed &&
          restored.journal().size() == 1 && restored.routine_state().evidence_ids.size() == 1,
          "lost ACK replay has one logical effect");
    Checkpoint next = reboot.recovery_state()->checkpoint;
    ++next.generation;
    check(reboot.durable_store()->checkpoint(next), "native ownership survives checkpoint publication");
    HubDurabilityOwner checkpoint_reboot(storage, storage, crypto, key,
                                         InstallationFreshness::ExistingInstallation);
    check(checkpoint_reboot.recover() == DurabilityOwnerState::Ready &&
          checkpoint_reboot.recovery_state()->checkpoint.fresh_registry_domain,
          "native ownership checkpoint reboot");

    Transition wrong;
    wrong.type = TransitionType::Event; wrong.event = {"device", "pir", 7, 2};
    wrong.enrollment_slot = 0; wrong.enrollment_generation = 1; wrong.event_digest.fill(1);
    wrong.registry_owner_domain = false;
    check(reboot.durable_store()->commit(wrong) == CommitStatus::NotCommitted,
          "wrong ownership domain remains rejected");
    Checkpoint invalid = next;
    invalid.allow_legacy_event_slots = true;
    Bytes encoded;
    check(!Codec::encode_checkpoint(crypto, key, invalid, encoded), "fresh root cannot authorize legacy slots");
    invalid = next; invalid.registry_owner_domain = false;
    check(!Codec::encode_checkpoint(crypto, key, invalid, encoded), "fresh root cannot drop registry ownership");

    Fixture failed_write;
    HubDurabilityOwner failed_owner(failed_write, failed_write, crypto, key,
                                    InstallationFreshness::FreshInstallation);
    check(failed_owner.recover() == DurabilityOwnerState::Ready, "event write fault genesis");
    DurableJournalSlotStore failed_slots(failed_owner, crypto, key, resolver);
    HubRuntime failed_runtime(4, 128);
    failed_runtime.bind_durability_owner(failed_owner); failed_runtime.authorize_node("pir", transport_session + 1, true);
    check(failed_runtime.journal().attach_persistence(crypto, failed_slots, key), "fault journal attached");
    failed_write.fail_at = failed_write.writes + 1; failed_write.fault = FaultMode::FailBeforeWrite;
    auto frame = transport::encode_node_message(message);
    check(bool(frame), "fault frame");
    security::SecureFrame secured; transport::EncodedFrame plain;
    check(node_radio.seal(security::RuntimeDirection::Uplink, frame.frame, secured) &&
          hub_radio.open(security::RuntimeDirection::Uplink, secured, plain), "fault event AEAD");
    auto decoded = transport::decode_node_message(plain.bytes.data(), plain.size);
    check(bool(decoded) && failed_runtime.authenticated_radio_message_callback(
              *decoded.value, "pir", "device", transport_session + 1, 12), "fault event admission");
    auto rejected = failed_runtime.run_state_once();
    check(rejected && rejected->ack == AckClass::Rejected && !rejected->state_changed &&
          failed_runtime.journal().size() == 0, "failed commit never produces Durable ACK");

    Fixture broken;
    broken.fail_at = 1; broken.fault = FaultMode::PartialWrite;
    HubDurabilityOwner interrupted(broken, broken, crypto, key, InstallationFreshness::FreshInstallation);
    check(interrupted.recover() == DurabilityOwnerState::FailedClosed, "interrupted genesis closed");
    HubDurabilityOwner broken_reboot(broken, broken, crypto, key, InstallationFreshness::ExistingInstallation);
    check(broken_reboot.recover() == DurabilityOwnerState::FailedClosed, "invalid genesis reboot closed");
    Fixture legacy; legacy.values["e000"] = {1};
    const auto before = legacy.values;
    HubDurabilityOwner unsupported(legacy, legacy, crypto, key, InstallationFreshness::FreshInstallation);
    check(unsupported.recover() == DurabilityOwnerState::FailedClosed && legacy.values == before,
          "unsupported legacy state never silently migrates");
    std::cout << "R1-FRESH-INSTALL PASS authenticated genesis/registry/event/reboot/duplicate/fault/domain/legacy\n";
}

#ifdef GS_RECOVERY_SCHEDULING_TEST
std::size_t recovery_handoffs = 0;
std::chrono::steady_clock::time_point last_handoff;
std::chrono::steady_clock::duration longest_segment{};
void cooperate() {
    const auto now = std::chrono::steady_clock::now();
    longest_segment = std::max(longest_segment, now - last_handoff);
    last_handoff = now;
    ++recovery_handoffs;
}

void recovery_scheduling_gate() {
    host::security::OpenSslCommissioningCrypto crypto;
    Key32 key{}; key.fill(9);
    Fixture storage;
    HubDurabilityOwner initial(storage, storage, crypto, key, InstallationFreshness::FreshInstallation);
    check(initial.recover() == DurabilityOwnerState::Ready, "scheduling fresh owner Ready");
    auto resolver = [](const std::string& physical, const std::string& logical,
                       DurableJournalSlotStore::EnrollmentOwner& out) {
        if (physical != "device" || logical != "pir") return false;
        out.slot = 0; out.generation = 1; out.owner_digest.fill(7); return true;
    };
    DurableJournalSlotStore writer(initial, crypto, key, resolver);
    HubJournal journal(128);
    recovery_handoffs = 0; longest_segment = {};
    last_handoff = std::chrono::steady_clock::now();
    check(journal.attach_persistence(crypto, writer, key, cooperate), "scheduling initial attach");
    check(recovery_handoffs == 256, "empty slots also cooperate");
    for (std::size_t i = 0; i < 128; ++i) {
        DomainEvent event;
        event.key = {"pir", 7, i + 1, "device"};
        event.sensor_type = SensorType::Pir; event.kind = EventKind::Motion;
        event.location = "room"; event.occurred_at = 10;
        check(journal.commit(event) == CommitResult::Stored, "all 128 genuine events stored");
    }
    check(writer.flush(), "archive all durable events");
    HubDurabilityOwner reboot(storage, storage, crypto, key, InstallationFreshness::ExistingInstallation);
    check(reboot.recover() == DurabilityOwnerState::Ready &&
          reboot.recovery_state()->checkpoint.fresh_registry_domain &&
          reboot.recovery_state()->checkpoint.registry_owner_domain,
          "full journal native reboot Ready");
    DurableJournalSlotStore reader(reboot, crypto, key, resolver);
    // Inject bounded provider latency, never replace the production codec or
    // recovery algorithm. Old uninterrupted attachment exceeds the 5s TWDT.
    storage.slow_checkpoint_read = true;
    const auto writes = storage.writes;
    HubJournal baseline(128);
    auto start = std::chrono::steady_clock::now();
    check(baseline.attach_persistence(crypto, reader, key), "unscheduled baseline recovery");
    const auto baseline_time = std::chrono::steady_clock::now() - start;
    check(baseline_time > std::chrono::seconds(5), "old recovery exceeds watchdog interval");
    recovery_handoffs = 0; longest_segment = {};
    last_handoff = std::chrono::steady_clock::now();
    HubJournal cooperative(128);
    check(cooperative.attach_persistence(crypto, reader, key, cooperate), "cooperative recovery");
    longest_segment = std::max(longest_segment, std::chrono::steady_clock::now() - last_handoff);
    check(recovery_handoffs == 256, "handoff covers every event and completion slot");
    check(longest_segment < std::chrono::seconds(5), "bounded independent operations");
    check(storage.writes == writes, "recovery scheduling never writes");
    check(cooperative.size() == 128 && baseline.size() == cooperative.size(), "all events identical count");
    for (std::size_t i = 0; i < 128; ++i) {
        Bytes old_payload, new_payload;
        check(HubJournal::encode_event_payload(baseline.records()[i], old_payload) &&
              HubJournal::encode_event_payload(cooperative.records()[i], new_payload) &&
              old_payload == new_payload, "same ordered authenticated event payloads");
        check(cooperative.commit(journal.records()[i]) == CommitResult::Duplicate, "duplicates remain duplicates");
    }
    storage.slow_checkpoint_read = false;
    // Inject faults at the production slot boundary; authentication and
    // duplicate-index reconstruction still execute in the real HubJournal.
    class FaultView final : public JournalSlotStore {
    public:
        FaultView(DurableJournalSlotStore& store, security::CommissioningCrypto& crypto,
                  const Key32& key, const DomainEvent& first, bool duplicate)
            : store(store), crypto(crypto), key(key), first(first), duplicate(duplicate) {}
        bool read(std::size_t slot, Bytes& blob, bool& found) override {
            if (!store.read(slot, blob, found)) return false;
            if (!duplicate && slot == 0 && found) blob.back() ^= 1;
            if (duplicate && slot == 1 && found)
                return HubJournal::encode_slot_blob(crypto, key, slot, first, blob);
            return true;
        }
        bool write(std::size_t, const Bytes&) override { return false; }
        bool read_completion(std::size_t slot, Bytes& blob, bool& found) override {
            return store.read_completion(slot, blob, found);
        }
        DurableJournalSlotStore& store;
        security::CommissioningCrypto& crypto;
        const Key32& key;
        const DomainEvent& first;
        bool duplicate;
    };
    const auto successful_handoffs = recovery_handoffs;
    for (bool duplicate : {false, true}) {
        FaultView bad(reader, crypto, key, journal.records().front(), duplicate);
        HubJournal closed(128);
        check(!closed.attach_persistence(crypto, bad, key, cooperate) && closed.storage_fault() &&
              closed.commit(journal.records().front()) == CommitResult::StorageFault,
              "cooperative tamper/duplicate-entry recovery fails closed");
    }
    Fixture corrupt = storage;
    check(!corrupt.values.at("cp0").empty(), "authenticated checkpoint exists");
    corrupt.values.at("cp0").back() ^= 1;
    corrupt.values.at("cp1").back() ^= 1;
    HubDurabilityOwner failed(corrupt, corrupt, crypto, key, InstallationFreshness::ExistingInstallation);
    check(failed.recover() == DurabilityOwnerState::FailedClosed, "corruption stays fail closed");
    std::cout << "R1-RECOVERY-SCHEDULING PASS records=128 handoffs=" << successful_handoffs
              << " old_interval_ms=" << std::chrono::duration_cast<std::chrono::milliseconds>(baseline_time).count()
              << " max_segment_ms=" << std::chrono::duration_cast<std::chrono::milliseconds>(longest_segment).count()
              << " production_codecs=YES latency_injected=YES\n";
}
#endif

}
int main() {
    try { gate(); gate(1502); gate(1503);
#ifdef GS_RECOVERY_SCHEDULING_TEST
        recovery_scheduling_gate();
#endif
        return 0; }
    catch (const std::exception& error) {
        std::cerr << "R1-FRESH-INSTALL FAIL " << error.what() << '\n'; return 1;
    }
}
