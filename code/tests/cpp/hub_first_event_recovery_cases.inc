// Embedded in the existing production-backed storage fixture.
#include "storage/hub_durability_owner.hpp"
#include "firmware/hub/target/esp32/nvs_durable_key_codec.hpp"

namespace {
class NativeFirstInventory final : public gs::hub::durable::StoreInventory {
public:
    gs::hub::durable::MemoryBlobStore blobs;
    gs::hub::durable::InventorySnapshot scan() override {
        std::vector<std::string> names;
        for (const auto* prefix : {"cp", "sel", "ret"}) {
            for (unsigned n = 0; n < (std::string(prefix)=="ret" ? 3U : 2U); ++n) {
                const auto logical=std::string(prefix)+std::to_string(n);
                Bytes b; bool found=false;
                if (!blobs.read(logical,b,found)) return {};
                if (found) {
                    std::string physical;
                    require(gs::hub::target::durable_logical_to_physical_key(logical,physical), "inventory mapping");
                    names.push_back(physical);
                }
            }
        }
        gs::hub::durable::InventorySnapshot result;
        result.status=names.empty()?gs::hub::durable::InventoryStatus::Empty:
            gs::hub::durable::InventoryStatus::KnownCurrentRecords;
        for (const auto& physical:names) {
            gs::hub::target::DurablePhysicalKeyRecord record;
            require(gs::hub::target::durable_physical_key_record(physical,record), "inventory parse");
            result.records[result.count++]={static_cast<gs::hub::durable::InventoryRecord::Kind>(record.kind),record.id};
        }
        return result;
    }
};

#ifndef GS148_OLD_READER
[[maybe_unused]] void first_event_recovery_reproduction(bool empty) {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key=storage_key();
    NativeFirstInventory inventory;
    gs::hub::durable::HubDurabilityOwner owner(inventory.blobs,inventory,crypto,key,
        gs::hub::durable::InstallationFreshness::FreshInstallation);
    std::array<std::uint8_t,32> registry{}; registry.fill(0x3a);
    require(owner.recover(&registry)==gs::hub::durable::DurabilityOwnerState::Ready,
            "native authenticated epoch1 owner");
    MemorySegments segments(4U*1024U*1024U);
    StateFiles files;
    DurableEventOutbox first(segments,crypto,key);
    require(first.recover()==OutboxRecovery::Empty,"first empty outbox");
    OutboxJournalBackend backend(first);
    RuntimeStateStore state(files,crypto,key);
    gs::hub::HubRuntime runtime(32,backend);
    runtime.bind_runtime_state(state); runtime.bind_durability_owner(owner);
    if (empty) files.fail_replace="application.head";
    require(runtime.restore_from_journal()!=empty,"initial checkpoint cut");
    if (!empty) {
        runtime.authorize_node("room1",42,true);
        std::array<std::uint8_t,32> binding{};binding.fill(0x2d);
        require(runtime.authenticated_radio_message_callback(make_message(1),"room1","device-room1",
            42,0,1000,0,3,binding),"original authenticated owner ingress");
        segments.fail_next_publication();
        const auto result=runtime.run_state_once(173);
        require(result && result->ack==gs::AckClass::Rejected && !result->state_changed,
                "first failed publication has no Durable ACK");
    }
    files.halted=false; files.fail_replace.clear();
    DurableEventOutbox reboot(segments,crypto,key);
    OutboxJournalBackend second_backend(reboot);
    RuntimeStateStore second_state(files,crypto,key);
    gs::hub::HubRuntime second(32,0);
    second.bind_runtime_state(second_state);second.bind_durability_owner(owner);
    if (!empty) {
        auto candidate=gs::domain_event_from_node_message(make_message(1),0);
        candidate.key.physical_device_id="device-room1";
        Bytes cp;bool found=false;gs::hub::storage::IdentityOwnerEvidence evidence;
        require(second_state.inspect_initial(&candidate,cp,found,evidence),"candidate selected identity/checkpoint proof");
        require(found && gs::hub::HubCheckpointCodec::restore(second,cp),"candidate decoder proof");
        const auto report=[](void*,const gs::hub::durable::RetirementSnapshot&){return true;};
        require(owner.verify_native_zero_history(report,nullptr,0,{}),"candidate native NVS zero history proof");
    }
    const auto resolver=[](void*,const gs::DomainEvent& event,gs::hub::storage::IdentityOwnerEvidence& owner) {
        if (event.key.source_id!="room1" || event.key.physical_device_id!="device-room1") return false;
        owner.enrollment_slot=0;owner.enrollment_generation=3;owner.binding_digest.fill(0x2d);
        return true;
    };
    require(second.recover_native_outbox(reboot,resolver,nullptr) &&
        second.journal().attach_backend(second_backend) && second.restore_from_journal(),
        empty ? "APPROVED_EMPTY_REPAIR baseline fails" : "APPROVED_FIRST_PENDING baseline fails");
}
#endif
}

#include "firmware/hub/commissioning/registry/registry_persistence.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/security/rejoin_protocol.hpp"
#include <fstream>
namespace {
// Atomic old/new replacement is expanded into temp write, sync, rename and
// selected readback cuts. Any simulated crash halts BOTH persistence adapters.
class FirstFiles final : public SegmentStore, public gs::hub::storage::RuntimeStateFiles {
public:
    MemorySegments segments{4U*1024U*1024U}; StateFiles state;
    std::string target, phase; bool halted=false, reported_error=false, selected_write=false;
    unsigned body_syncs=0;std::string selected_object;bool body_barrier_seen=false;
    bool cut(const std::string& object,const std::string& where) {
        if (target!=object || phase!=where) return false;
        if (reported_error) {target.clear(); return true;}
        halted=true; return true;
    }
    void reset() {halted=false;target.clear();phase.clear();selected_write=false;selected_object.clear();body_barrier_seen=false;}
    bool replace_object(const std::string& name,const Bytes& bytes) {
        if (halted || cut(name,"before-write")) return false;
        state.files[name+".new"]=Bytes(bytes.begin(),bytes.begin()+bytes.size()/2);
        if (cut(name,"prefix")) return false;
        state.files[name+".new"]=bytes;
        if (cut(name,"before-sync") || cut(name,"after-sync") || cut(name,"before-rename")) return false;
        state.files[name]=bytes;state.files.erase(name+".new");++state.writes;
        selected_write=true;selected_object=name;
        return !cut(name,"after-rename");
    }
    std::uint64_t partition_capacity_bytes() const override {return segments.partition_capacity_bytes();}
    bool filesystem_usage(std::uint64_t& total,std::uint64_t& used) override {
        if (halted || !segments.filesystem_usage(total,used)) return false;
        for (const auto& f:state.files) used+=(f.second.size()+4095U)/4096U*4096U;
        return true;
    }
    bool segment_size(std::uint16_t n,bool& found,std::uint32_t& size) override {
        return !halted && segments.segment_size(n,found,size);
    }
    bool read(std::uint16_t n,std::uint32_t offset,std::uint8_t* out,std::size_t size,std::size_t& actual) override {
        if (halted || (body_barrier_seen && cut("body","before-readback"))) return false;
        const bool result=segments.read(n,offset,out,size,actual);
        return result && !(body_barrier_seen && cut("body","after-readback"));
    }
    bool append(std::uint16_t n,const std::uint8_t* data,std::size_t size) override {
        if (halted || cut("body","before-write")) return false;
        if (target=="body" && phase=="prefix") {
            (void)segments.append(n,data,size/2);(void)cut("body","prefix");return false;
        }
        const bool result=segments.append(n,data,size);
        return result && !cut("body","after-write");
    }
    bool sync(std::uint16_t n) override {
        ++body_syncs;body_barrier_seen=true;
        if (halted || cut("body","before-sync") || !segments.sync(n) || cut("body","after-sync")) return false;
        if (target=="body" && phase=="missing-readback") segments.missing_read_once=true;
        if (target=="body" && phase=="corrupt-readback") segments.corrupt_read_once=true;
        return true;
    }
    bool read_publication(Bytes& b,bool& found) override {
        if (halted || (selected_object=="publication" && cut("publication","before-readback"))) return false;
        const bool result=segments.read_publication(b,found);
        return result && !(selected_object=="publication" && cut("publication","after-readback"));
    }
    bool publish_publication(const Bytes& b) override {
        if (halted || cut("publication","before-write")) return false;
        state.files["event.head.new"]=Bytes(b.begin(),b.begin()+b.size()/2);
        if (cut("publication","prefix")) return false;
        state.files["event.head.new"]=b;
        if (cut("publication","before-sync") || cut("publication","after-sync") ||
            cut("publication","before-rename")) return false;
        const bool result=segments.publish_publication(b);
        state.files.erase("event.head.new");selected_write=true;selected_object="publication";
        return result && !cut("publication","after-rename");
    }
    bool read_lifecycle_root(Bytes& b,bool& f) override {return !halted && segments.read_lifecycle_root(b,f);}
    bool publish_lifecycle_root(const Bytes& b) override {return !halted && segments.publish_lifecycle_root(b);}
    bool remove_segment(std::uint16_t n) override {return !halted && segments.remove_segment(n);}
    bool completion_size(bool& f,std::uint32_t& size) override {return !halted && segments.completion_size(f,size);}
    bool read_completion(std::uint32_t o,std::uint8_t* p,std::size_t s,std::size_t& a) override {return !halted && segments.read_completion(o,p,s,a);}
    bool append_completion(const std::uint8_t* p,std::size_t s) override {return !halted && segments.append_completion(p,s);}
    bool sync_completion() override {return !halted && segments.sync_completion();}
    bool truncate_completion(std::uint32_t s) override {return !halted && segments.truncate_completion(s);}
    bool read_completion_publication(Bytes& b,bool& f) override {return !halted && segments.read_completion_publication(b,f);}
    bool publish_completion_publication(const Bytes& b) override {return !halted && segments.publish_completion_publication(b);}
    bool state_size(const char* n,bool& f,std::uint32_t& s) override {return !halted && state.state_size(n,f,s);}
    bool state_read(const char* n,std::uint32_t o,std::uint8_t* p,std::size_t s) override {
        if (halted || (selected_object==n && cut(n,"before-readback"))) return false;
        const bool result=state.state_read(n,o,p,s);
        return result && !(selected_object==n && cut(n,"after-readback"));
    }
    bool state_append_sync(const char* n,const Bytes& b) override {
        if (halted || cut(n,"before-write")) return false;
        if (target==n && phase=="prefix") {
            state.files[n].insert(state.files[n].end(),b.begin(),b.begin()+b.size()/2);
            (void)cut(n,"prefix");return false;
        }
        const bool result=state.state_append_sync(n,b);selected_object=n;
        return result && !cut(n,"before-sync") && !cut(n,"after-sync") && !cut(n,"after-write");
    }
    bool state_replace(const char* n,const Bytes& b) override {return replace_object(n,b);}
    bool state_truncate(const char* n,std::uint32_t s) override {return !halted && state.state_truncate(n,s);}
    bool state_capacity(std::uint64_t& t,std::uint64_t& u) override {return filesystem_usage(t,u);}
    bool state_remove(const char* n) override {return !halted && state.state_remove(n);}
    bool state_sync(const char* n) override {return !halted && state.state_sync(n);}
};
class FirstRegistryBlob final : public gs::security::SecurityBlobStore {
public:
    Bytes bytes;
    bool read(Bytes& out,bool& found) override {out=bytes;found=!out.empty();return true;}
    bool write(const Bytes& in) override {bytes=in;return true;}
};
[[maybe_unused]] gs::DomainEvent first_event(std::uint64_t sequence) {
    auto e=gs::domain_event_from_node_message(make_message(sequence),0);
    e.key.physical_device_id="device-room1";return e;
}
struct FirstFixture {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    Key32 key=storage_key(); NativeFirstInventory inventory; FirstFiles files;
    FirstRegistryBlob registry_blob;
    gs::security::CommissioningBinding binding;
    gs::hub::NodeRegistry registry{"home","hub",10,16};
    std::unique_ptr<gs::hub::HubRegistryRepository> registry_repository;
    std::unique_ptr<gs::hub::durable::HubDurabilityOwner> owner;
    std::unique_ptr<DurableEventOutbox> outbox;
    std::unique_ptr<RuntimeStateStore> state;
    std::unique_ptr<OutboxJournalBackend> backend;
    std::unique_ptr<gs::hub::HubRuntime> runtime;
    std::unique_ptr<gs::security::RuntimeFrameSecurity> tx,rx;
    std::uint64_t transport_session=41;
    FirstFixture() {
        gs::hub::EnrolledNode node;
        node.device_id="device-room1";node.logical_id="room1";node.home_id="home";node.hub_id="hub";
        node.room="room";node.function="motion";node.radio_mac={1,2,3,4,5,6};
        require(crypto.generate_test_identity("first-node") &&
            crypto.identity_public_key("first-node",node.p256_public_key),"Node public identity");
        require(registry.enroll(node)==gs::hub::RegistryResult::Accepted,"trusted commissioning result");
        binding.device_id=node.device_id;binding.logical_id=node.logical_id;
        binding.home_id="home";binding.hub_id="hub";binding.room="room";binding.function="motion";
        binding.device_public_key=node.p256_public_key;binding.installation_key=key;
        require(crypto.generate_test_identity("first-hub") &&
            crypto.identity_public_key("first-hub",binding.hub_public_key),"Hub public identity");
        registry_repository=std::make_unique<gs::hub::HubRegistryRepository>(crypto,registry_blob,key,
            "home","hub",binding.hub_public_key,10,16);
        require(registry_repository->save({registry.snapshot(),{binding},{}}),"authenticated registry save");
        reload_registry();
        owner=std::make_unique<gs::hub::durable::HubDurabilityOwner>(inventory.blobs,inventory,crypto,key,
            gs::hub::durable::InstallationFreshness::FreshInstallation);
        require(owner->recover()==gs::hub::durable::DurabilityOwnerState::Ready,"native NVS initial roots");
    }
    void reload_registry() {
        const auto loaded=registry_repository->load();
        require(loaded.status==gs::hub::HubRegistryLoadStatus::Ready && loaded.state &&
            loaded.state->migration.phase==gs::hub::RegistryMigrationPhase::FreshInstallation,
            "native authenticated registry readback");
        registry=gs::hub::NodeRegistry("home","hub",10,16);
        require(registry.restore(loaded.state->registry),"authorized registry restore");
    }
    static bool resolve(void* opaque,const gs::DomainEvent& event,gs::hub::storage::IdentityOwnerEvidence& out) {
        auto& f=*static_cast<FirstFixture*>(opaque);
        const auto node=f.registry.find(event.key.physical_device_id);
        if (!node || node->quarantined || node->logical_id!=event.key.source_id ||
            node->home_id!="home" || node->hub_id!="hub" || node->enrollment_slot>=10 ||
            node->device_id!=f.binding.device_id || node->p256_public_key!=f.binding.device_public_key)
            return false;
        const auto& descriptor=f.registry.enrollment_slots()[node->enrollment_slot];
        if (descriptor.state!=gs::hub::EnrollmentSlotState::Active ||
            descriptor.device_id!=node->device_id || descriptor.generation!=node->enrollment_generation)
            return false;
        out.enrollment_slot=node->enrollment_slot;out.enrollment_generation=node->enrollment_generation;
        out.binding_digest=descriptor.owner_digest;return out.authenticated();
    }
    bool boot(bool initialize_transport=true) {
        runtime.reset();backend.reset();state.reset();outbox.reset();owner.reset();files.reset();
        reload_registry();
        owner=std::make_unique<gs::hub::durable::HubDurabilityOwner>(inventory.blobs,inventory,crypto,key,
            gs::hub::durable::InstallationFreshness::ExistingInstallation);
        if (owner->recover()!=gs::hub::durable::DurabilityOwnerState::Ready) return false;
        outbox=std::make_unique<DurableEventOutbox>(files,crypto,key);
        state=std::make_unique<RuntimeStateStore>(files,crypto,key);
        backend=std::make_unique<OutboxJournalBackend>(*outbox);
        runtime=std::make_unique<gs::hub::HubRuntime>(32,0);
        runtime->bind_runtime_state(*state);runtime->bind_durability_owner(*owner);
#ifdef GS148_OLD_READER
        const auto old_recovered=outbox->recover();
        if (old_recovered!=OutboxRecovery::Empty && old_recovered!=OutboxRecovery::Ready) return false;
#else
        if (!runtime->recover_native_outbox(*outbox,resolve,this)) return false;
#endif
        if (!runtime->journal().attach_backend(*backend)) return false;
        const auto recovered=owner->recovery_state();
        if (recovered && recovered->checkpoint.report_snapshot &&
            !runtime->reconcile_selected_replay_fence(*recovered,*owner->retirement_repository(),
                *state,1,*outbox).succeeded()) return false;
        if (!runtime->restore_from_journal()) return false;
        if (initialize_transport) rejoin();
        return true;
    }
    void rejoin() {
        ++transport_session;
        gs::security::NodeRejoin node(crypto,binding,transport_session,2);
        gs::security::HubRejoin hub(crypto,binding,transport_session-1);
        const auto hello=node.begin();require(hello.has_value(),"Hello");
        const auto challenge=hub.accept(*hello);require(challenge.has_value(),"Challenge");
        const auto final=node.accept(*challenge);require(final.has_value(),"Final");
        const auto ack=hub.confirm(*final);require(ack && node.commit(*ack),"rejoin mutual proof");
        tx=std::make_unique<gs::security::RuntimeFrameSecurity>(crypto,binding);
        rx=std::make_unique<gs::security::RuntimeFrameSecurity>(crypto,binding);
        require(tx->start(transport_session,*node.session_salt()) &&
            rx->start(transport_session,*hub.session_salt()),"fresh authenticated transport");
        runtime->authorize_node("room1",transport_session,true);
    }
    std::optional<gs::hub::ProcessResult> send(gs::NodeMessage message,
            std::optional<std::uint16_t> minute=173,
            const gs::hub::storage::IdentityOwnerEvidence* override_owner=nullptr) {
        const auto encoded=gs::transport::encode_node_message(message);
        gs::security::SecureFrame secure; gs::transport::EncodedFrame opened;
        require(encoded && tx->seal(gs::security::RuntimeDirection::Uplink,encoded.frame,secure) &&
            rx->open(gs::security::RuntimeDirection::Uplink,secure,opened),"Node AEAD authentication");
        const auto decoded=gs::transport::decode_node_message(opened.bytes.data(),opened.size);
        require(static_cast<bool>(decoded),"wire message decode");
        auto event=gs::domain_event_from_node_message(message,0);event.key.physical_device_id=binding.device_id;
        gs::hub::storage::IdentityOwnerEvidence owner_evidence;
        if (!resolve(this,event,owner_evidence)) return {};
        if (override_owner) owner_evidence=*override_owner;
        if (!runtime->authenticated_radio_message_callback(*decoded.value,"room1","device-room1",
            transport_session,0,1000,owner_evidence.enrollment_slot,owner_evidence.enrollment_generation,
            owner_evidence.binding_digest)) return {};
        return runtime->run_state_once(minute);
    }
    void prepare_pending() {
        require(boot(),"fresh coordinated boot");
        files.target="publication";files.phase="before-write";
        const auto result=send(make_message(1));
        require(result && result->ack==gs::AckClass::Rejected && !result->state_changed,
            "unpublished first event must never ACK");files.reset();
    }
};
}
#ifndef GS148_OLD_READER
namespace {
void first_pending_oracle(FirstFixture& f) {
    require(f.outbox->record_count()==0 && f.state->identities()==1,"exact pending set {1}, public set empty");
    const auto e=first_event(1);
    require(!f.runtime->journal().contains(e.key),"pending is not committed duplicate");
    std::size_t replayed=0;
    const auto visit=[](void* p,const gs::DomainEvent&){++*static_cast<std::size_t*>(p);return true;};
    require(f.runtime->journal().for_each(visit,&replayed) && replayed==0,"pending never replay/cloud delivery");
}
void finish_first(FirstFixture& f,bool require_pending=true) {
    require(f.boot() && f.boot(),"two consecutive authenticated boots");
    if (require_pending) first_pending_oracle(f);
    const auto before=f.files.state.files;
    if (f.outbox->record_count()==0 && f.state->identities()==1) {
        const auto bad=f.send(make_message(2));
        require(bad && bad->ack==gs::AckClass::Rejected && f.files.state.files==before &&
            f.runtime->durable_admission_open(),"different key cannot overwrite or poison pending identity");
        auto conflict=make_message(1);conflict.location="different";
        const auto refused=f.send(conflict);
        require(refused && refused->ack==gs::AckClass::Rejected && f.files.state.files==before,
            "same key conflicting payload cannot replace original");
        auto original=first_event(1);gs::hub::storage::IdentityOwnerEvidence wrong;
        require(FirstFixture::resolve(&f,original,wrong),"stored owner resolver");
        ++wrong.enrollment_generation;
        const auto wrong_owner=f.send(make_message(1),173,&wrong);
        require(wrong_owner && wrong_owner->ack==gs::AckClass::Rejected && f.files.state.files==before,
            "same key replaced enrollment retry cannot commit");
    }
    const auto original=f.send(make_message(1),999);
    require(original && original->ack==gs::AckClass::Durable && f.outbox->record_count()>=1,
        "original authenticated retry completes normal durable ACK");
    std::optional<std::uint16_t> minute;
    const auto stored_event=first_event(1);
    require(f.state->identity_context(stored_event.key,1,minute,&stored_event),"original exact identity context");
    // If identity selection was interrupted, no selected minute existed. Other
    // cuts must preserve the original selected minute, despite a later retry.
    if (require_pending) require(minute==173,"original selected occurrence minute preserved");
    const auto duplicate=f.send(make_message(1),888);
    require(duplicate && duplicate->ack==gs::AckClass::Durable && !duplicate->state_changed &&
        duplicate->rule_signals.empty(),"lost ACK has no duplicate reducer effect");
    require(f.boot(),"post-commit reboot");
    const auto after=f.send(make_message(1));
    require(after && after->ack==gs::AckClass::Durable && !after->state_changed,
        "post-reboot exact duplicate has one logical effect");
    const auto next=f.send(make_message(2));
    require(next && next->ack==gs::AckClass::Durable && f.state->identities()==2 &&
        f.outbox->record_count()==2,"normal second event after recovery");
}
void option_a_cut_tests() {
    unsigned cuts=0;
    const std::vector<std::string> phases={"before-write","prefix","before-sync","after-sync",
        "before-rename","after-rename","before-readback","after-readback"};
    for (const auto* target:{"identity.head","application.head"}) {
        for (const auto& phase:phases) {
            FirstFixture f;f.files.target=target;f.files.phase=phase;
            // Create the initially empty objects without clearing the armed cut.
            f.outbox=std::make_unique<DurableEventOutbox>(f.files,f.crypto,f.key);
            require(f.outbox->recover()==OutboxRecovery::Empty,"initial empty scanner");
            f.state=std::make_unique<RuntimeStateStore>(f.files,f.crypto,f.key);
            f.backend=std::make_unique<OutboxJournalBackend>(*f.outbox);
            f.runtime=std::make_unique<gs::hub::HubRuntime>(32,*f.backend);
            f.runtime->bind_runtime_state(*f.state);f.runtime->bind_durability_owner(*f.owner);
            require(!f.runtime->restore_from_journal() && f.files.halted,"initial checkpoint crash cut reached");
            require(f.boot() && f.boot() && f.state->identities()==0,"interrupted empty initialization repairs twice");
            const auto result=f.send(make_message(1));
            require(result && result->ack==gs::AckClass::Durable,"admit after empty repair");++cuts;
        }
    }
    std::vector<std::pair<std::string,std::string>> event_cuts;
    for (const auto* target:{"identity.head","publication","application.head"})
        for (const auto& phase:phases) event_cuts.emplace_back(target,phase);
    for (const auto* target:{"identity.log","body"})
        for (const auto* phase:{"before-write","prefix","after-write"}) event_cuts.emplace_back(target,phase);
    for (const auto* target:{"body","identity.log"})
        for (const auto* phase:{"before-sync","after-sync","before-readback","after-readback"})
            event_cuts.emplace_back(target,phase);
    for (const auto& cut:event_cuts) {
        FirstFixture f;require(f.boot(),"event cut fresh initialized fixture");
        f.files.target=cut.first;f.files.phase=cut.second;f.files.selected_write=false;
        const auto result=f.send(make_message(1));
        require(f.files.halted && result && result->ack==gs::AckClass::Rejected && !result->state_changed,
            "event crash cut withholds ACK and result effect");
        require(f.boot() && f.boot(),"event fault twice recovered");
        const bool selected_pending=f.state->identities()==1 && f.outbox->record_count()==0;
        // Published-but-uncheckpointed events replay normally, never a boot ACK.
        finish_first(f,selected_pending);++cuts;
    }
    for (const auto* target:{"identity.log","body","identity.head","publication","application.head"}) {
        FirstFixture f;require(f.boot(),"API error fixture");
        f.files.target=target;
        f.files.phase=(std::string(target)=="body" || std::string(target)=="identity.log")?"after-write":"after-rename";
        f.files.reported_error=true;
        const auto result=f.send(make_message(1));
        require(result && result->ack==gs::AckClass::Rejected,"persisted but failed API never ACKs");
        f.files.reported_error=false;
        require(f.boot(),"succeed-then-error selected inventory recovery");
        const bool pending=f.state->identities()==1 && f.outbox->record_count()==0;
        finish_first(f,pending);++cuts;
    }
    std::cout<<"GS148-ARCH-001/002/003/004/005/006 PASS option_a_fault_cuts="<<cuts<<" reboot_per_cut=2\n";
}
void option_a_negative_tests() {
    unsigned negatives=0;
    const std::vector<std::string> cases={"missing-checkpoint","corrupt-checkpoint","malformed-head",
        "corrupt-identity","extra-identity-tail","corrupt-body","extra-body-tail","foreign-key",
        "future-epoch","fallback-history","report-fence","witness-epoch","witness-generation",
        "revoked","replaced","quarantined","completion-tail","completion-head","inactive-body","wrong-body-key","conflicting-body-payload","missing-identity","populated-missing-head"};
    for (const auto& name:cases) {
        FirstFixture f;f.prepare_pending();
        if (name=="missing-checkpoint") f.files.state.files.erase("application.head");
        if (name=="corrupt-checkpoint") f.files.state.files["application.head"][25]^=1;
        if (name=="malformed-head") require(f.files.segments.publish_publication(Bytes{0}),"malformed selected head");
        if (name=="corrupt-identity") f.files.state.files["identity.head"][25]^=1;
        if (name=="missing-identity") f.files.state.files.erase("identity.head");
        if (name=="extra-identity-tail") f.files.state.files["identity.log"].push_back(0);
        if (name=="extra-body-tail") {const std::uint8_t b=0;require(f.files.segments.append(0,&b,1),"extra body tail");}
        if (name=="corrupt-body") {
            bool found=false;std::uint32_t size=0;require(f.files.segment_size(0,found,size) && found,"corruption body size");
            Bytes bytes(size);std::size_t actual=0;
            require(f.files.read(0,0,bytes.data(),bytes.size(),actual) && actual==size,"corruption body read");
            bytes.at(32)^=1;MemorySegments damaged(4U*1024U*1024U);
            require(damaged.append(0,bytes.data(),bytes.size()),"persistent corrupted body bytes");
            f.files.segments=std::move(damaged);
        }
        if (name=="foreign-key") f.key[0]^=1;
        if (name=="future-epoch") {
            auto cp=f.owner->recovery_state()->checkpoint;cp.storage_epoch=2;cp.generation=1;
            require(f.owner->commit_candidate_epoch(cp),"future native epoch selection");
        }
        if (name=="fallback-history") {
            auto cp=f.owner->recovery_state()->checkpoint;cp.pending_effects.push_back({});
            cp.generation=1;Bytes encoded;
            require(gs::hub::durable::Codec::encode_checkpoint(f.crypto,f.key,cp,encoded) &&
                f.inventory.blobs.replace("cp0",encoded),"contradictory authenticated fallback root");
        }
        if (name=="report-fence" || name=="witness-epoch" || name=="witness-generation") {
            gs::hub::durable::RetirementSnapshot report;
            report.storage_epoch=1;report.generation=1;report.occupancy_mask=1;
            gs::hub::storage::IdentityOwnerEvidence current;
            require(FirstFixture::resolve(&f,first_event(1),current),"report original owner");
            auto& node=report.nodes[current.enrollment_slot];
            node.binding_digest=current.binding_digest;node.enrollment_generation=current.enrollment_generation;
            node.report_generation=1;node.report_hmac.fill(9);node.current_origin_session=42;
            node.durable_admission_highwater=1;
            if (name!="report-fence") {node.pending_count=1;node.pending[0]={42,1};}
            gs::hub::durable::ReportSnapshotReference reference;
            require(f.owner->retirement_repository()->prepare_bank(report,0,reference),"authenticated report bank");
            auto cp=f.owner->recovery_state()->checkpoint;cp.generation=3;cp.report_snapshot=reference;
            require(f.owner->durable_store()->checkpoint(cp),"report selected NVS root");
            if (name!="report-fence") {
                // Use a separate healthy empty outbox to encode the real v1 witness;
                // transplant its selected marker into the interrupted fixture.
                MemorySegments source(4U*1024U*1024U);DurableEventOutbox witness(source,f.crypto,f.key);
                require(witness.recover()==OutboxRecovery::Empty,"witness encoder");
                if (name=="witness-generation") ++reference.generation;
                require(witness.publish_replay_fence(name=="witness-epoch"?2:1,reference,0),"real witness publication");
                Bytes encoded;bool found=false;require(source.read_lifecycle_root(encoded,found) && found &&
                    f.files.segments.publish_lifecycle_root(encoded),"selected wrong witness");
            }
        }
        if (name=="revoked" || name=="replaced" || name=="quarantined") {
            auto loaded=f.registry_repository->load();require(loaded.state.has_value(),"authenticated registry mutation");
            auto changed=*loaded.state;
            if (name=="quarantined") changed.registry.active[0].quarantined=true;
            else {
                require(f.registry.remove("device-room1")==gs::hub::RegistryResult::Accepted,"owner revocation");
                changed.registry=f.registry.snapshot();changed.bindings.clear();
                if (name=="replaced") {
                    auto replacement=loaded.state->registry.active[0];replacement.device_id="replacement";
                    require(f.registry.enroll(replacement)==gs::hub::RegistryResult::Accepted,"replacement enrollment");
                    changed.registry=f.registry.snapshot();auto binding=f.binding;binding.device_id="replacement";
                    changed.bindings.push_back(binding);
                }
            }
            require(f.registry_repository->save(changed),"revoked/replaced/quarantined authenticated persistence");
        }
        if (name=="inactive-body") {
            const std::uint8_t byte=0;require(f.files.segments.append(16,&byte,1),"unselected compaction body evidence");
        }
        if (name=="completion-head") require(f.files.segments.publish_completion_publication(Bytes{0}),"malformed completion authority");
        if (name=="wrong-body-key" || name=="conflicting-body-payload") {
            auto candidate=first_event(name=="wrong-body-key"?2:1);
            if(name=="conflicting-body-payload") candidate.location="substituted";
            Bytes payload;require(gs::hub::HubJournal::encode_event_payload(candidate,payload),"conflicting authentic payload");
            MemorySegments source(4U*1024U*1024U);DurableEventOutbox other(source,f.crypto,f.key);
            require(other.recover()==OutboxRecovery::Empty,"other body encoder");source.fail_next_publication();
            require(other.append(candidate.key.str(),payload,AdmissionClass::Protected)==gs::hub::storage::OutboxAdmission::MetadataPublicationFailure,"real authenticated mismatching body");
            f.files.segments=std::move(source);
        }
        if (name=="completion-tail") {
            const std::uint8_t b=0;require(f.files.segments.append_completion(&b,1),"unowned completion prefix");
        }
        if (name=="populated-missing-head") {
            require(f.boot(),"pending before populated fixture");
            const auto result=f.send(make_message(1));require(result && result->ack==gs::AckClass::Durable,"previous ACKed event");
            // Empty present head is still present, and must remain invalid.
            require(f.files.segments.publish_publication(Bytes{}),"lost selected head bytes");
        }
        const auto original=f.files.state.files;
        const bool first=f.boot(),second=f.boot();
        if(first || second) throw std::runtime_error("negative authority case "+name+" boot1="+std::to_string(first)+" boot2="+std::to_string(second));
        require(f.files.state.files==original,"failed proof never heals or truncates selected identity evidence");++negatives;
    }
    // A truly absent head alongside acknowledged history (not malformed bytes).
    FirstFixture acknowledged;require(acknowledged.boot(),"acknowledged fixture");
    require(acknowledged.send(make_message(1))->ack==gs::AckClass::Durable,"acknowledged event");
    bool found=false;std::uint32_t size=0;require(acknowledged.files.segments.segment_size(0,found,size),"saved body size");
    Bytes body(size);std::size_t actual=0;require(acknowledged.files.segments.read(0,0,body.data(),size,actual),"saved body");
    MemorySegments absent(4U*1024U*1024U);require(absent.append(0,body.data(),body.size()),"head absent populated bytes");
    acknowledged.files.segments=std::move(absent);
    require(!acknowledged.boot() && !acknowledged.boot(),"acknowledged checkpoint1 forbids missing head recovery");++negatives;
    std::cout<<"GS148-ARCH-008/016/040/048 PASS option_a_negative_cases="<<negatives<<" reboot_per_case=2\n";
}
void option_a_retry_tests() {
    FirstFixture f;f.prepare_pending();require(f.boot() && f.boot(),"pending reboot twice");first_pending_oracle(f);
    const auto frames=f.outbox->committed_frame_bytes();const auto syncs=f.files.body_syncs;
    finish_first(f);
    require(f.files.body_syncs>syncs && f.outbox->committed_frame_bytes()>frames,
        "recovered body resync then ordinary second event");
    unsigned refusal=0;
    for (const auto* phase:{"before-sync","after-sync","before-readback","after-readback"}) {
        FirstFixture cut;cut.prepare_pending();require(cut.boot(),"resync fixture");
        cut.files.target="body";cut.files.phase=phase;
        const auto result=cut.send(make_message(1));
        require(result && result->ack==gs::AckClass::Rejected && cut.outbox->record_count()==0,
            "failed staged barrier/readback cannot publish ACK");
        finish_first(cut);++refusal;
    }
    for (const auto* fault:{"missing","corrupt"}) {
        FirstFixture cut;cut.prepare_pending();require(cut.boot(),"readback negative fixture");
        cut.files.target="body";cut.files.phase=std::string(fault)+"-readback";
        const auto result=cut.send(make_message(1));
        require(result && result->ack==gs::AckClass::Rejected && cut.outbox->record_count()==0,
            "unreadable pending body withholds ACK");finish_first(cut);++refusal;
    }
    FirstFixture full;full.prepare_pending();require(full.boot(),"capacity pending fixture");
    const auto selected=full.files.state.files;
    std::uint64_t total=0,used=0;
    require(full.files.filesystem_usage(total,used),"actual shared capacity inventory");
    full.files.segments.additional_usage=total-used;
    for (unsigned n=0;n<8;++n) {
        const auto result=full.send(make_message(1));
        require(result && result->ack==gs::AckClass::Rejected && full.outbox->record_count()==0 &&
            full.files.state.files==selected,"full capacity repeated rejection retains one owned pending identity");
    }
    full.files.segments.additional_usage=0;finish_first(full);
    FirstFixture low;require(low.boot(),"low-capacity native fixture");
    require(low.files.filesystem_usage(total,used),"low-capacity occupancy");
    low.files.segments.additional_usage=total-used-4096;
    const auto empty_selected=low.files.state.files;
    const auto refused=low.send(make_message(1));
    require(refused && refused->ack==gs::AckClass::Rejected && low.state->identities()==0 &&
        low.files.state.files==empty_selected,"low capacity refused before first irreversible identity work");
    low.files.segments.additional_usage=0;
    require(low.boot() && low.boot() && low.state->identities()==0,"low capacity rejection reboot bound");
    require(low.send(make_message(1))->ack==gs::AckClass::Durable,"fresh admission after released capacity");
    std::cout<<"GS148-ARCH-007/009/010 PASS option_a_exact_retry=1 staged_failures="<<refusal
        <<" capacity_refusals=8 second_event=1\n";
}
void option_a_report_tests() {
    for (unsigned kind=0;kind<4;++kind) {
        FirstFixture f;require(f.boot(),"pre-event report native fixture");
        if(kind<3) {
            gs::hub::durable::RetirementSnapshot report;report.storage_epoch=1;report.generation=1;
            gs::hub::storage::IdentityOwnerEvidence current;
            require(FirstFixture::resolve(&f,first_event(1),current),"original report owner");
            report.occupancy_mask=static_cast<std::uint16_t>(1U<<current.enrollment_slot);
            auto& node=report.nodes[current.enrollment_slot];node.binding_digest=current.binding_digest;
            node.enrollment_generation=current.enrollment_generation;node.current_origin_session=42;
            node.report_generation=1;node.report_hmac.fill(8);node.durable_admission_highwater=1;
            node.pending_count=1;node.pending[0]={42,1};
            gs::hub::durable::ReportSnapshotReference reference;
            require(f.owner->retirement_repository()->prepare_bank(report,0,reference),"zero-event report bank");
            auto cp=f.owner->recovery_state()->checkpoint;cp.generation=3;cp.report_snapshot=reference;
            require(f.owner->durable_store()->checkpoint(cp),"zero-event report selected");
            if(kind!=0) require(f.outbox->publish_replay_fence(1,reference,0),"zero-event compatible witness");
            if(kind==2) {
                report.generation=2;node.report_generation=2;
                require(f.owner->retirement_repository()->prepare_bank(report,static_cast<std::uint8_t>(1U<<reference.bank),reference),"NVS ahead report bank");
                cp.generation=4;cp.report_snapshot=reference;
                require(f.owner->durable_store()->checkpoint(cp),"NVS ahead selected reference");
            }
        }
        f.files.target="publication";f.files.phase="before-write";
        require(f.send(make_message(1))->ack==gs::AckClass::Rejected,"reported first event interrupted");
        f.files.reset();
        if(kind==3) require(f.inventory.blobs.replace("cp1",Bytes{0}),"damaged newest NVS bank fallback");
        require(f.boot() && f.boot(),"compatible report/fallback pending boot");first_pending_oracle(f);
        gs::hub::durable::RecoveryState recovered;
        require(f.owner->durable_store()->recover(recovered),"report root selected after boot");
        if(kind<3) {
            std::uint8_t pins=0;
            require(f.outbox->retirement_report_bank_mask(recovered,pins) &&
                (pins & recovered.recovery_report_bank_mask)==recovered.recovery_report_bank_mask,
                "active and fallback report banks remain pinned");
        }
        finish_first(f);
    }
    std::cout<<"GS148-ARCH-012/013/014/015/016 PASS option_a_report_cases=4 reboot_per_case=2\n";
}
[[maybe_unused]] void option_a_privacy_test() {
    FirstFixture f;f.prepare_pending();require(f.boot(),"pending before privacy configuration");
    f.runtime->set_mode(gs::HomeMode::Privacy);
    require(f.boot() && f.boot(),"pending original survives authenticated privacy checkpoint0");
    const auto different=f.send(make_message(2));
    require(different && different->ack==gs::AckClass::Rejected,"pending slot rejects another key before policy disposition");
    const auto original=f.send(make_message(1));
    require(original && original->ack==gs::AckClass::Durable && original->rule_signals.empty() &&
        f.outbox->record_count()==1,"already prepared original completes while privacy suppresses interpretation");
    const auto fresh=f.send(make_message(2));
    require(fresh && fresh->ack==gs::AckClass::DiscardedPolicy && f.state->identities()==1 &&
        f.outbox->record_count()==1,"fresh passive evidence retains privacy discard policy");
    std::cout<<"GS148-ARCH-007/009 PASS pending_privacy_context=1 fresh_privacy_suppressed=1\n";
}
void option_a_quarantine_test() {
    FirstFixture f;require(f.boot(),"native first prefix fixture");
    for(unsigned cut=0;cut<3;++cut) {
        f.files.target="body";f.files.phase="prefix";
        const auto result=f.send(make_message(1));
        require(result && result->ack==gs::AckClass::Rejected && f.outbox->record_count()==0,
            "repeated original body prefix cannot ACK");
        require(f.boot() && f.state->identities()==1 && f.outbox->record_count()==0,
            "one selected identity retains original retry through each quarantined prefix");
    }
    f.files.target="publication";f.files.phase="before-write";
    require(f.send(make_message(1))->ack==gs::AckClass::Rejected,"matching complete body still not published");
    require(f.boot() && f.boot(),"same-ordinal prefixes plus one matching body recover pending twice");
    require(f.outbox->capacity_budget_used_bytes()>=3U*128U*1024U,"quarantine remains charged and bounded");
    finish_first(f);
    std::cout<<"GS148-ARCH-004/005/009 PASS option_a_quarantine_cycles=3 publication_cut=1\n";
}
void option_a_empty_inventory_tests() {
    for (const auto* name:{"completion-tail","inactive-bank"}) {
        FirstFixture f;
        const std::uint8_t byte=0;
        if (std::string(name)=="completion-tail")
            require(f.files.segments.append_completion(&byte,1),"nonempty initial completion tail");
        else require(f.files.segments.append(16,&byte,1),"nonempty initial inactive bank");
        require(!f.boot() && !f.boot(),"nonempty raw inventory cannot authorize missing checkpoint repair");
        require(f.files.state.files.count("application.head")==0,"no invented empty checkpoint");
        bool found=false;std::uint32_t size=0;
        const bool inspected=std::string(name)=="completion-tail" ?
            f.files.completion_size(found,size):f.files.segment_size(16,found,size);
        require(inspected && found && size==1,"failed empty proof preserves raw evidence");
    }
    std::cout<<"GS148-ARCH-001/008 PASS option_a_raw_empty_negatives=2 reboot_per_case=2\n";
}
[[maybe_unused]] void option_a_tests() {option_a_cut_tests();option_a_negative_tests();option_a_retry_tests();option_a_report_tests();option_a_privacy_test();option_a_quarantine_test();option_a_empty_inventory_tests();}
}
#endif
