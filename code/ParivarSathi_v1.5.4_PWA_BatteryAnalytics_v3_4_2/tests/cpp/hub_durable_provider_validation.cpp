#include "firmware/hub/components/storage/hub_durability_owner.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/target/esp32/nvs_durable_key_codec.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>

namespace {
using namespace gs::hub::durable;
using namespace gs::hub::target;
using gs::security::Bytes;
using gs::security::Key32;
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
Key32 key() { Key32 k{}; for (std::size_t i=0;i<k.size();++i) k[i]=static_cast<std::uint8_t>(i+1); return k; }

class Fixture final : public BlobStore, public StoreInventory {
public:
    bool read(const std::string& logical, Bytes& value, bool& found) override {
        if (read_failure) return false;
        std::string physical;
        if (!durable_logical_to_physical_key(logical, physical)) return false;
        const auto it = values.find(physical); found = it != values.end();
        value = found ? it->second : Bytes{}; return true;
    }
    bool write_immutable(const std::string& k, const Bytes& b) override { return write(k,b,true); }
    bool replace(const std::string& k, const Bytes& b) override { return write(k,b,false); }
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
};

void inventory_tests() {
    Fixture fixture;
    check(fixture.scan().status==InventoryStatus::Empty,"empty inventory");
    fixture.values["cp0"]={1}; fixture.values["sel1"]={1}; fixture.values["tr2"]={1};
    check(fixture.scan().status==InventoryStatus::KnownCurrentRecords,"known fixed records inventory");
    fixture.values["ef0000000000000"]={1}; fixture.values["ev0000000000001"]={1};
    check(fixture.scan().status==InventoryStatus::KnownCurrentRecords,"dynamic records inventory");
    fixture.values["e000"]={1}; fixture.values["c127"]={1};
    check(fixture.scan().status==InventoryStatus::KnownMixedRecords,"legacy records inventory");
    check(fixture.writes==0,"inventory is read only");
    Fixture unknown; unknown.values["odd"]={1};
    check(unknown.scan().status==InventoryStatus::UnknownOrphanRecord,"unknown record recognized");
    Fixture malformed; malformed.values["efINVALID"]={1};
    check(malformed.scan().status==InventoryStatus::MalformedRecord,"malformed dynamic record rejected");
    Fixture noncanonical; noncanonical.values["evzzzzzzzzzzzzz"]={1};
    check(noncanonical.scan().status==InventoryStatus::MalformedRecord,"overflow dynamic key rejected");
    Fixture failure; failure.forced_status=InventoryStatus::ScanFailure;
    check(failure.scan().status==InventoryStatus::ScanFailure,"scan failure propagated");
    Fixture limit; limit.forced_status=InventoryStatus::LimitExceeded;
    check(limit.scan().status==InventoryStatus::LimitExceeded,"inventory bound propagated");
    Fixture full;
    for(std::uint64_t id=0;id<kMaxInventoryRecords+1;++id) {
        std::string physical; check(durable_logical_to_physical_key("ef"+std::to_string(id),physical),"limit fixture key maps");
        full.values[physical]={1};
    }
    check(full.scan().status==InventoryStatus::LimitExceeded,"record limit enforced");
    Fixture provider;
    check(provider.write_immutable("ef0",Bytes{1,2,3}),"provider maps and writes immutable logical key");
    check(!provider.write_immutable("ef0",Bytes{1,2,3})&&provider.immutable_collision,
          "immutable physical collision is rejected");
    Bytes readback; bool found=false;
    check(provider.read("ef0",readback,found)&&found&&readback==Bytes({1,2,3}),"provider logical read maps to physical key");
    check(provider.replace("ev1",Bytes{4,5}),"provider replacement maps logical key");
    check(provider.writes==3,"read-only inventory does not add writes");
}

void codec_tests() {
    for(const auto* prefix:{"ef","ev"}) for(const auto id:{0ULL,1ULL,9ULL,10ULL,31ULL,32ULL,255ULL,256ULL,
            static_cast<unsigned long long>(UINT32_MAX),static_cast<unsigned long long>(UINT64_MAX)}) {
        const std::string logical=std::string(prefix)+std::to_string(id);
        std::string physical; check(durable_logical_to_physical_key(logical,physical),"dynamic key maps");
        check(physical.size()<=15 && physical.size()==15,"physical dynamic key length");
        DurablePhysicalKeyRecord record; check(durable_physical_key_record(physical,record),"physical key decodes");
        check(record.id==id,"u64 mapping round trips");
        check((prefix[1]=='f')==(record.kind==DurablePhysicalKeyKind::EffectChunk),"families do not collide");
    }
    for(const auto& bad:{std::string("ef"),std::string("ef01"),std::string("ef000000000000"),
                         std::string("efzzzzzzzzzzzzz"),std::string("EF0000000000000"),
                         std::string("xx0000000000000")}) {
        DurablePhysicalKeyRecord r; check(!durable_physical_key_record(bad,r),"malformed physical key rejected");
    }
    for (const auto& k:{std::string("cp0"),std::string("cp1"),std::string("sel0"),std::string("sel1"),
                        std::string("tr0"),std::string("tr3"),std::string("bm0"),std::string("bm1"),
                        std::string("ret0"),std::string("ret2"),std::string("e000"),std::string("e127"),
                        std::string("c000"),std::string("c127"),std::string("mig0"),std::string("mig1")}) {
        std::string p; check(durable_logical_to_physical_key(k,p)&&p==k,"fixed and legacy key remains canonical");
    }
}

void owner_tests(gs::host::security::OpenSslCommissioningCrypto& crypto) {
    const auto k=key();
    Fixture fresh; HubDurabilityOwner owner(fresh,fresh,crypto,k,InstallationFreshness::FreshInstallation);
    gs::hub::HubRuntime gated_runtime;
    gated_runtime.authorize_node("node", 7, false);
    gated_runtime.bind_durability_owner(owner);
    check(!gated_runtime.durable_admission_open() && !gated_runtime.authoritative_storage_epoch(),
          "uninitialized owner exposes no epoch and keeps runtime admission closed");
    const gs::DomainEvent sample{{"node", 7, 1}, gs::EventKind::Motion, "room", 1, 1, 1, 0, 3800, false};
    check(!gated_runtime.radio_callback(sample) && !gated_runtime.run_state_once(),
          "event admission and processing cannot bypass an unready owner");
    check(owner.recover()==DurabilityOwnerState::Ready && owner.epoch()==1,"fresh empty starts epoch one");
    check(gated_runtime.durable_admission_open() && gated_runtime.authoritative_storage_epoch()==1,
          "fresh owner Ready exposes authoritative epoch one to runtime");
    check(gated_runtime.radio_callback(sample) && gated_runtime.run_state_once().has_value(),
          "event admission opens only after fresh owner readiness");
    check(owner.recover()==DurabilityOwnerState::Ready && owner.epoch()==1,"repeated recovery is deterministic");
    check(owner.durable_store() && owner.retirement_repository() && owner.recovery_state(),"repositories compose when ready");
    HubDurabilityOwner reboot(fresh,fresh,crypto,k,InstallationFreshness::ExistingInstallation);
    check(reboot.recover()==DurabilityOwnerState::Ready && reboot.epoch()==1,"reboot preserves epoch");
    gs::hub::HubRuntime reboot_runtime;
    reboot_runtime.authorize_node("node", 7, false);
    reboot_runtime.bind_durability_owner(reboot);
    check(reboot_runtime.authoritative_storage_epoch()==1 && reboot_runtime.radio_callback(sample),
          "valid existing store opens admission with the same recovered epoch");
    check(owner.candidate_next_epoch()==2,"candidate epoch increments");
    Checkpoint replacement; replacement.storage_epoch=2;
    check(owner.commit_candidate_epoch(replacement) && owner.epoch()==2,
          "controlled epoch increments only after both new checkpoints and selectors verify");
    HubDurabilityOwner after_transition(fresh,fresh,crypto,k,InstallationFreshness::ExistingInstallation);
    check(after_transition.recover()==DurabilityOwnerState::Ready && after_transition.epoch()==2,
          "committed controlled epoch survives reboot");
    Fixture nonempty; HubDurabilityOwner protected_owner(nonempty,nonempty,crypto,k,InstallationFreshness::FreshInstallation);
    check(protected_owner.recover()==DurabilityOwnerState::Ready,"nonempty transition fixture bootstraps");
    Transition timer; timer.storage_epoch=1; timer.ordinal=1; timer.type=TransitionType::Timer;
    timer.event={"hub","timer",1,1}; timer.event_digest_present=false;
    check(protected_owner.durable_store()->commit(timer)==CommitStatus::Committed,"durable nonempty history committed");
    Checkpoint discard; discard.storage_epoch=2;
    check(!protected_owner.commit_candidate_epoch(discard) && protected_owner.epoch()==1,
          "controlled epoch helper refuses to discard existing history");
    HubDurabilityOwner erased(fresh,fresh,crypto,k,InstallationFreshness::ExistingInstallation);
    Fixture empty; HubDurabilityOwner lost(empty,empty,crypto,k,InstallationFreshness::ExistingInstallation);
    check(lost.recover()==DurabilityOwnerState::FailedClosed && !lost.epoch(),"existing identity plus empty storage fails closed");
    gs::hub::HubRuntime erased_runtime;
    erased_runtime.authorize_node("node", 7, false);
    erased_runtime.bind_durability_owner(lost);
    check(!erased_runtime.durable_admission_open() && !erased_runtime.authoritative_storage_epoch() &&
          !erased_runtime.radio_callback(sample), "bare erase keeps event admission closed");
    Fixture orphan; orphan.values["zz"]={1};
    HubDurabilityOwner orphan_owner(orphan,orphan,crypto,k,InstallationFreshness::FreshInstallation);
    check(orphan_owner.recover()==DurabilityOwnerState::FailedClosed,"unknown orphan blocks fresh bootstrap");
    gs::hub::HubRuntime orphan_runtime;
    orphan_runtime.authorize_node("node", 7, false);
    orphan_runtime.bind_durability_owner(orphan_owner);
    check(!orphan_runtime.radio_callback(sample) && !orphan_runtime.authoritative_storage_epoch(),
          "orphan storage keeps event admission closed");
    Fixture scan_fail; scan_fail.forced_status=InventoryStatus::ScanFailure;
    HubDurabilityOwner scan_owner(scan_fail,scan_fail,crypto,k,InstallationFreshness::FreshInstallation);
    check(scan_owner.recover()==DurabilityOwnerState::FailedClosed,"inventory scan error fails closed");
    Fixture bad_cps; bad_cps.values["cp0"]={0}; bad_cps.values["cp1"]={0};
    HubDurabilityOwner bad_history(bad_cps,bad_cps,crypto,k,InstallationFreshness::ExistingInstallation);
    check(bad_history.recover()==DurabilityOwnerState::FailedClosed,"both unusable checkpoint banks fail closed");
    Fixture legacy; legacy.values["e000"]={1};
    HubDurabilityOwner legacy_owner(legacy,legacy,crypto,k,InstallationFreshness::ExistingInstallation);
    check(legacy_owner.recover()==DurabilityOwnerState::MigrationRequired,"legacy records require migration");
    gs::hub::HubRuntime migration_runtime;
    migration_runtime.authorize_node("node", 7, false);
    migration_runtime.bind_durability_owner(legacy_owner);
    check(!migration_runtime.durable_admission_open() && !migration_runtime.authoritative_storage_epoch() &&
          !migration_runtime.radio_callback(sample) && legacy.values.count("e000") == 1,
          "MigrationRequired blocks admission and preserves legacy records");
    Fixture migration; migration.values["mig0"]={1};
    HubDurabilityOwner migration_owner(migration,migration,crypto,k,InstallationFreshness::ExistingInstallation);
    check(migration_owner.recover()==DurabilityOwnerState::MigrationRequired,"migration metadata requires migration state");
    Fixture ambiguous; HubDurabilityOwner ambiguous_owner(ambiguous,ambiguous,crypto,k,InstallationFreshness::Ambiguous);
    check(ambiguous_owner.recover()==DurabilityOwnerState::FailedClosed,"ambiguous identity fails closed");
    Fixture read_fail; read_fail.read_failure=true;
    // Inventory is initially empty, but the bootstrap read fails before a checkpoint can be trusted.
    HubDurabilityOwner read_owner(read_fail,read_fail,crypto,k,InstallationFreshness::FreshInstallation);
    check(read_owner.recover()==DurabilityOwnerState::FailedClosed,"provider read error fails closed");

    for(std::size_t fail_at=1; fail_at<=4; ++fail_at) {
        Fixture interrupted; interrupted.fail_at=fail_at; interrupted.fault=FaultMode::PowerLossAfterPersist;
        HubDurabilityOwner first(interrupted,interrupted,crypto,k,InstallationFreshness::FreshInstallation);
        const auto initial=first.recover();
        check(initial!=DurabilityOwnerState::Ready || first.epoch()==1,"bootstrap exposes only complete epoch");
        HubDurabilityOwner after(interrupted,interrupted,crypto,k,InstallationFreshness::ExistingInstallation);
        const auto resumed=after.recover();
        check(resumed==DurabilityOwnerState::Ready && after.epoch()==1,"interrupted genesis recovers deterministically");
    }
    Fixture partial_second; partial_second.fail_at=3; partial_second.fault=FaultMode::PartialWrite;
    HubDurabilityOwner interrupted_second(partial_second,partial_second,crypto,k,InstallationFreshness::FreshInstallation);
    check(interrupted_second.recover()==DurabilityOwnerState::FailedClosed,"partial second checkpoint is not advertised");
    HubDurabilityOwner resumed_second(partial_second,partial_second,crypto,k,InstallationFreshness::ExistingInstallation);
    check(resumed_second.recover()==DurabilityOwnerState::Ready && resumed_second.epoch()==1,
          "partial second checkpoint resumes from authenticated genesis");
    Fixture partial_first; partial_first.fail_at=1; partial_first.fault=FaultMode::PartialWrite;
    HubDurabilityOwner partial_boot(partial_first,partial_first,crypto,k,InstallationFreshness::FreshInstallation);
    check(partial_boot.recover()==DurabilityOwnerState::FailedClosed,"partial first checkpoint fails closed");
    HubDurabilityOwner partial_reboot(partial_first,partial_first,crypto,k,InstallationFreshness::ExistingInstallation);
    check(partial_reboot.recover()==DurabilityOwnerState::FailedClosed,"corrupt first checkpoint cannot resume");
    Fixture partial_selector; partial_selector.fail_at=2; partial_selector.fault=FaultMode::PartialWrite;
    HubDurabilityOwner selector_boot(partial_selector,partial_selector,crypto,k,InstallationFreshness::FreshInstallation);
    check(selector_boot.recover()==DurabilityOwnerState::FailedClosed,"partial selector fails closed");
    HubDurabilityOwner selector_reboot(partial_selector,partial_selector,crypto,k,InstallationFreshness::ExistingInstallation);
    check(selector_reboot.recover()==DurabilityOwnerState::FailedClosed,"corrupt selector cannot authorize an epoch");
    Fixture api_fail; api_fail.fail_at=1; api_fail.fault=FaultMode::PersistThenFail;
    HubDurabilityOwner failed(api_fail,api_fail,crypto,k,InstallationFreshness::FreshInstallation);
    check(failed.recover()==DurabilityOwnerState::Ready && failed.epoch()==1,
          "persist then failed API is accepted only after exact readback and completed bootstrap");
    HubDurabilityOwner retry(api_fail,api_fail,crypto,k,InstallationFreshness::ExistingInstallation);
    check(retry.recover()==DurabilityOwnerState::Ready && retry.epoch()==1,"persisted checkpoint restarts safely");
    check(!api_fail.immutable_collision,"bootstrap uses replaceable checkpoint banks only");
    Fixture max_epoch;
    Checkpoint max_cp; max_cp.storage_epoch=std::numeric_limits<std::uint32_t>::max();
    max_cp.generation=7;
    Bytes cp_bytes, selector_bytes;
    check(Codec::encode_checkpoint(crypto,k,max_cp,cp_bytes),"maximum epoch checkpoint encodes");
    check(Codec::encode_selector(crypto,k,max_cp.generation,0,selector_bytes),"maximum epoch selector encodes");
    max_epoch.values["cp0"]=cp_bytes; max_epoch.values["sel1"]=selector_bytes;
    HubDurabilityOwner at_max(max_epoch,max_epoch,crypto,k,InstallationFreshness::FreshInstallation);
    check(at_max.recover()==DurabilityOwnerState::FailedClosed,"new security identity cannot adopt preexisting durable history");
    HubDurabilityOwner existing_max(max_epoch,max_epoch,crypto,k,InstallationFreshness::ExistingInstallation);
    check(existing_max.recover()==DurabilityOwnerState::Ready &&
          existing_max.epoch()==std::numeric_limits<std::uint32_t>::max(),"maximum epoch recovers");
    check(!existing_max.candidate_next_epoch(),"epoch overflow is refused");
    Fixture gen_overflow;
    Checkpoint overflow_cp; overflow_cp.storage_epoch=9;
    overflow_cp.generation=std::numeric_limits<std::uint64_t>::max();
    check(Codec::encode_checkpoint(crypto,k,overflow_cp,cp_bytes),"maximum checkpoint generation encodes");
    check(Codec::encode_selector(crypto,k,overflow_cp.generation,0,selector_bytes),"maximum generation selector encodes");
    gen_overflow.values["cp0"]=cp_bytes; gen_overflow.values["sel1"]=selector_bytes;
    HubDurabilityOwner generation_owner(gen_overflow,gen_overflow,crypto,k,InstallationFreshness::ExistingInstallation);
    check(generation_owner.recover()==DurabilityOwnerState::Ready,"maximum checkpoint generation recovers");
    Checkpoint next_history; next_history.storage_epoch=10;
    check(!generation_owner.commit_candidate_epoch(next_history) && generation_owner.epoch()==9,
          "checkpoint generation overflow refuses controlled epoch commit without changing authority");
}
}

int main() {
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        codec_tests(); inventory_tests(); owner_tests(crypto);
        std::cout << "Hub durable provider validation passed\n";
        return 0;
    } catch(const std::exception& e) {
        std::cerr << "Hub durable provider validation failed: " << e.what() << '\n';
        return 1;
    }
}
