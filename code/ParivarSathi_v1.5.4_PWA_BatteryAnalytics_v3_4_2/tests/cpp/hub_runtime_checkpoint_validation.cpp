// Reuse the established host flash adapter and exact event generator.
#define main prior_outbox_test_main
#include "hub_segmented_outbox_runtime_validation.cpp"
#undef main
#include "firmware/hub/runtime/hub_checkpoint_codec.hpp"
#include "storage/runtime_state_store.hpp"

namespace {
class StateFiles final : public gs::hub::storage::RuntimeStateFiles {
public:
    std::map<std::string,Bytes> files;
    std::string fail_replace;
    bool partial_append=false;
    std::string persist_then_fail;
    bool halted=false;
    std::size_t writes=0;
    bool state_size(const char* n,bool& found,std::uint32_t& size) override {
        if(halted)return false;
        found=files.count(n);size=found?files[n].size():0;return true;
    }
    bool state_read(const char* n,std::uint32_t offset,std::uint8_t* out,std::size_t size) override {
        if(halted || !files.count(n) || offset+size>files[n].size())return false;
        std::copy_n(files[n].data()+offset,size,out);return true;
    }
    bool state_append_sync(const char* n,const Bytes& data) override {
        if(halted)return false;
        ++writes;
        const auto size=partial_append?data.size()/2:data.size();
        files[n].insert(files[n].end(),data.begin(),data.begin()+size);
        if(partial_append){partial_append=false;halted=true;return false;}
        return true;
    }
    bool state_replace(const char* n,const Bytes& data) override {
        if(halted)return false;
        if(fail_replace==n){halted=true;return false;}
        ++writes;files[n]=data;
        if(persist_then_fail==n){halted=true;return false;}
        return true;
    }
    bool state_truncate(const char* n,std::uint32_t size) override {
        if(halted || (files.count(n) && files[n].size()<size))return false;
        files[n].resize(size);return true;
    }
};
using gs::hub::storage::RuntimeStateStore;

class ScriptedBackendTransport final : public gs::hub::CloudBackendTransport {
public:
    gs::hub::BackendCommitReply reply;
    std::size_t calls{0};
    gs::hub::BackendCommitReply submit(const gs::hub::BackendCommitRequest&) override {
        ++calls;
        return reply;
    }
};

class SparseOrdinalBackend final : public gs::hub::JournalEventBackend {
public:
    std::uint64_t highwater{0};
    std::vector<std::pair<std::uint64_t,gs::DomainEvent>> retained;
    bool healthy() const override { return true; }
    std::size_t size() const override { return static_cast<std::size_t>(highwater); }
    gs::hub::CommitResult commit(const gs::DomainEvent&) override {
        return gs::hub::CommitResult::StorageFault;
    }
    bool contains(const gs::EventKey& key) override {
        return std::any_of(retained.begin(),retained.end(),[&](const auto& row) {
            return row.second.key.str()==key.str();
        });
    }
    bool for_each(EventVisitor visitor,void* context) override {
        for(const auto& row:retained) if(!visitor(context,row.second)) return false;
        return true;
    }
    bool for_each_with_ordinal(OrdinalEventVisitor visitor,void* context) override {
        for(const auto& row:retained)
            if(!visitor(context,row.first,row.second)) return false;
        return true;
    }
};
gs::DomainEvent event(std::uint64_t sequence) {
    gs::DomainEvent e; e.key={"room1",42,sequence,"device-room1"};
    e.kind=gs::EventKind::Motion;e.location="bedroom";
    e.occurred_at=100+sequence;e.received_at=e.occurred_at;e.monotonic_ms=sequence*1000;
    return e;
}
void checkpoint_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key=storage_key();
    MemorySegments segments(4U*1024U*1024U); StateFiles files;
    DurableEventOutbox outbox(segments,crypto,key);
    require(outbox.recover()==OutboxRecovery::Empty,"empty outbox");
    OutboxJournalBackend backend(outbox);
    RuntimeStateStore state(files,crypto,key);
    gs::hub::HubRuntime runtime(32,backend);
    runtime.bind_runtime_state(state);
    runtime.authorize_node("room1",1,true);
    require(state.recover(0),"state empty recover");
    Bytes init;require(gs::hub::HubCheckpointCodec::encode(runtime,init),"initial codec");
    require(state.save_checkpoint(init,0),"initial checkpoint save");
    require(runtime.restore_from_journal(),"fresh checkpoint initialized");
    gs::RoutineConfig window;window.window_id="morning";window.start_at=1;window.end_at=5000;window.grace_end_at=5100;
    runtime.start_window(window,gs::HomeMode::Home);
    runtime.start_activity_monitor(1);
    for(std::uint64_t seq: {1ULL,3ULL,10ULL}) {
        auto e=event(seq); runtime.authorize_node(e.key.source_id,e.key.session_id,true);
        require(runtime.radio_callback(e),"event authorized");
        const auto result=runtime.run_state_once(100);
        require(result && result->ack==gs::AckClass::Durable,"ACK after checkpoint and identity");
    }
    Bytes uninterrupted;
    require(gs::hub::HubCheckpointCodec::encode(runtime,uninterrupted),"snapshot encoded");
    // Interrupted checkpoint after both event and identity publication.
    auto e=event(11);runtime.authorize_node(e.key.source_id,e.key.session_id,true);
    require(runtime.radio_callback(e),"tail event queued");
    files.fail_replace="application.head";
    const auto result=runtime.run_state_once(101);
    require(result && result->ack==gs::AckClass::Rejected && !runtime.durable_admission_open(),"checkpoint failure no ACK");
    Bytes expected;require(gs::hub::HubCheckpointCodec::encode(runtime,expected),"expected tail state");
    files.halted=false;files.fail_replace.clear();
    RuntimeStateStore recovered(files,crypto,key);
    gs::hub::HubRuntime restarted(32,backend);restarted.bind_runtime_state(recovered);
    require(restarted.restore_from_journal(),"checkpoint plus streaming tail replay");
    Bytes actual;require(gs::hub::HubCheckpointCodec::encode(restarted,actual)&&actual==expected,"checkpoint replay equivalence");
    restarted.authorize_node(e.key.source_id,e.key.session_id,true);
    require(restarted.radio_callback(e),"lost ACK retry queues");
    const auto retry=restarted.run_state_once(999);
    require(retry && retry->ack==gs::AckClass::Durable && !retry->state_changed && retry->rule_signals.empty(),"no repeated reducer/notification effects");
    bool found=false;require(recovered.contains_identity(e.key,found)&&found,"independent identity exact");
    auto forged=e.key;forged.physical_device_id="other-owner";
    require(recovered.contains_identity(forged,found)&&!found,"physical owner scoped");
    forged=e.key;forged.session_id++;
    require(recovered.contains_identity(forged,found)&&!found,"origin session scoped");
    forged=e.key;forged.sequence=2;
    require(recovered.contains_identity(forged,found)&&!found,"sequence gap is not watermark");
    require(!restarted.node_online(e.key.source_id,1),"old boot monotonic lease not live");
    const auto writes=files.writes;require(restarted.checkpoint_state(),"unchanged checkpoint valid");
    require(files.writes==writes,"unchanged state no extra flash write");
    const auto good=files.files;
    files.files["application.head"][42]^=1;
    RuntimeStateStore corrupt(files,crypto,key);
    gs::hub::HubRuntime bad(32,backend);bad.bind_runtime_state(corrupt);
    require(!bad.restore_from_journal()&&!bad.durable_admission_open(),"corrupt checkpoint fails closed");
    files.files=good;files.files.erase("application.head");
    RuntimeStateStore missing(files,crypto,key);require(!missing.recover(4),"missing checkpoint fails closed");
    files.files=good;files.files["identity.log"][50]^=1;
    RuntimeStateStore broken_identity(files,crypto,key);require(!broken_identity.recover(4),"corrupt identity fails closed");
    files.files=good;
    RuntimeStateStore standalone(files,crypto,key);
    require(standalone.recover(4),"identity-only adapter restores without body IO");
    auto conflict=event(11);conflict.kind=gs::EventKind::DoorOpen;
    require(!standalone.verify_event_identity(conflict,4),"conflicting immutable payload rejected");
    std::cout<<"checkpoint_bytes="<<recovered.checkpoint_bytes()<<" identity_bytes="<<recovered.identity_bytes()<<" records=4\n";
}
void interruption_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;const auto key=storage_key();
    for(const auto& failure: {std::string("append"),std::string("identity.head")}) {
        MemorySegments segments(4U*1024U*1024U); StateFiles files;
        DurableEventOutbox outbox(segments,crypto,key);require(outbox.recover()==OutboxRecovery::Empty,"empty fixture");
        OutboxJournalBackend backend(outbox);RuntimeStateStore state(files,crypto,key);
        gs::hub::HubRuntime runtime(32,backend);runtime.bind_runtime_state(state);
        require(runtime.restore_from_journal(),"initialize");auto e=event(1);runtime.authorize_node(e.key.source_id,e.key.session_id,true);
        if(failure=="append")files.partial_append=true;else files.fail_replace=failure;
        require(runtime.radio_callback(e),"queue");const auto r=runtime.run_state_once(100);
        require(r&&r->ack==gs::AckClass::Rejected&&outbox.record_count()==0,"identity interruption before body no ACK");
        files.halted=false;files.fail_replace.clear();
        RuntimeStateStore recovery(files,crypto,key);gs::hub::HubRuntime reboot(32,backend);reboot.bind_runtime_state(recovery);
        require(reboot.restore_from_journal(),"unpublished identity tail recovered");
        reboot.authorize_node(e.key.source_id,e.key.session_id,true);require(reboot.radio_callback(e),"retry");
        require(reboot.run_state_once(101)->ack==gs::AckClass::Durable,"retry commits");
    }
    // Published identity, failed event head. Recovery allows exactly one staged key.
    MemorySegments segments(4U*1024U*1024U);StateFiles files;
    DurableEventOutbox outbox(segments,crypto,key);require(outbox.recover()==OutboxRecovery::Empty,"empty");
    OutboxJournalBackend backend(outbox);RuntimeStateStore state(files,crypto,key);gs::hub::HubRuntime runtime(32,backend);
    runtime.bind_runtime_state(state);require(runtime.restore_from_journal(),"init");
    auto first=event(1);runtime.authorize_node(first.key.source_id,first.key.session_id,true);
    require(runtime.radio_callback(first)&&runtime.run_state_once(100)->ack==gs::AckClass::Durable,"first publication");
    auto e=event(3);segments.fail_next_publication();
    require(runtime.radio_callback(e),"queue");require(runtime.run_state_once(100)->ack==gs::AckClass::Rejected,"unpublished body no ACK");
    DurableEventOutbox recovered(segments,crypto,key);require(recovered.recover()==OutboxRecovery::Ready,"body staged behind existing root");
    OutboxJournalBackend rb(recovered);RuntimeStateStore rs(files,crypto,key);gs::hub::HubRuntime rr(32,rb);rr.bind_runtime_state(rs);
    require(rr.restore_from_journal(),"staged identity recovery");rr.authorize_node(e.key.source_id,e.key.session_id,true);
    require(rr.radio_callback(e)&&rr.run_state_once(999)->ack==gs::AckClass::Durable,"original context retry");
    require(rs.identities()==2,"retry no duplicate identity");
}
void published_checkpoint_interruption() {
    gs::host::security::OpenSslCommissioningCrypto crypto;const auto key=storage_key();
    MemorySegments segments(4U*1024U*1024U);StateFiles files;
    DurableEventOutbox outbox(segments,crypto,key);require(outbox.recover()==OutboxRecovery::Empty,"empty");
    OutboxJournalBackend backend(outbox);RuntimeStateStore state(files,crypto,key);gs::hub::HubRuntime runtime(32,backend);
    runtime.bind_runtime_state(state);require(runtime.restore_from_journal(),"init");
    auto e=event(1);runtime.authorize_node(e.key.source_id,e.key.session_id,true);
    files.persist_then_fail="application.head";
    require(runtime.radio_callback(e)&&runtime.run_state_once(100)->ack==gs::AckClass::Rejected,"crash after publication before ACK");
    files.halted=false;files.persist_then_fail.clear();
    RuntimeStateStore recovered(files,crypto,key);gs::hub::HubRuntime reboot(32,backend);reboot.bind_runtime_state(recovered);
    require(reboot.restore_from_journal(),"new published checkpoint recovery");
    reboot.authorize_node(e.key.source_id,e.key.session_id,true);
    require(reboot.radio_callback(e),"retry queued");
    auto result=reboot.run_state_once(999);
    require(result && result->ack==gs::AckClass::Durable && !result->state_changed && result->rule_signals.empty(),"published state not repeated");
}

void timer_and_scale_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;const auto key=storage_key();
    MemorySegments segments(4U*1024U*1024U);StateFiles files;
    DurableEventOutbox outbox(segments,crypto,key);require(outbox.recover()==OutboxRecovery::Empty,"empty");
    OutboxJournalBackend backend(outbox);RuntimeStateStore state(files,crypto,key);gs::hub::HubRuntime runtime(32,backend);
    runtime.bind_runtime_state(state);require(runtime.restore_from_journal(),"fresh");
    const auto fresh=files.files;
    files.files.erase("application.head");
    RuntimeStateStore lost(files,crypto,key);require(!lost.recover(0),"missing checkpoint detected before any event");
    files.files=fresh;
    RuntimeStateStore unsupported(files,crypto,key);require(unsupported.recover(0),"valid fresh restore");
    require(unsupported.save_checkpoint(Bytes{9,0,0,0},0),"authenticated unsupported schema fixture");
    gs::hub::HubRuntime wrong_schema(32,backend);wrong_schema.bind_runtime_state(unsupported);
    require(!wrong_schema.restore_from_journal()&&!wrong_schema.durable_admission_open(),"unsupported checkpoint closes admission");
    files.files=fresh;
    runtime.authorize_node("room1",42,true);
    gs::RoutineConfig config;config.window_id="timer";config.start_at=1;config.end_at=110;config.grace_end_at=120;
    runtime.start_window(config,gs::HomeMode::Home);runtime.start_activity_monitor(1);
    auto heartbeat=event(1);heartbeat.kind=gs::EventKind::Heartbeat;
    require(runtime.radio_callback(heartbeat)&&runtime.run_state_once(100)->ack==gs::AckClass::Durable,"coverage event");
    require(runtime.deadline(130,true).create,"deadline creates once");
    require(!runtime.deadline(100,false).create,"untrusted time suppresses conclusion");
    RuntimeStateStore recovered(files,crypto,key);gs::hub::HubRuntime reboot(32,backend);reboot.bind_runtime_state(recovered);
    require(reboot.restore_from_journal(),"timer checkpoint restore");
    require(!reboot.deadline(130,true).create,"deadline latch prevents repeated external effect");
    gs::hub::CoverageTracker coverage(300);coverage.require_node("room1");coverage.observe("room1",500);
    require(coverage.current(499)==gs::CoverageState::Unknown,"backward clock no invented coverage");
    require(coverage.current(801)==gs::CoverageState::Unknown,"stale coverage no activity claim");
    // No active evidence-collecting window: test scalable storage rather than
    // silently enlarge the bounded routine checkpoint schema.
    config.enabled=false;runtime.start_window(config,gs::HomeMode::Home);
    std::uint32_t identity_at_high_records=0;
    for(std::uint64_t i=2;i<=6556;++i) {
        auto e=event(i);require(runtime.radio_callback(e),"scale queues");
        auto r=runtime.run_state_once(100);
        require(r && r->ack==gs::AckClass::Durable,"scale checkpoint admission");
        if(i==3278) identity_at_high_records=state.identity_bytes();
    }
    RuntimeStateStore scale(files,crypto,key);gs::hub::HubRuntime rr(32,backend);rr.bind_runtime_state(scale);
    require(rr.restore_from_journal(),"6556 checkpoint recovery");
    bool found=false;require(scale.contains_identity(event(129).key,found)&&found,"identity 129");
    require(scale.contains_identity(event(385).key,found)&&found,"identity 385");
    require(scale.contains_identity(event(3278).key,found)&&found,"identity 3278");
    require(scale.contains_identity(event(6556).key,found)&&found,"identity 6556");
    std::cout<<"identity_3278_bytes="<<identity_at_high_records
             <<" identity_6556_bytes="<<scale.identity_bytes()
             <<" checkpoint_bytes="<<scale.checkpoint_bytes()
             <<" outbox_index_bytes="<<outbox.index_memory_bytes()
             <<" runtime_object_bytes="<<sizeof(gs::hub::HubRuntime)<<"\n";
}

void backend_completion_lifecycle_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key=storage_key();
    MemorySegments segments(4U*1024U*1024U);
    DurableEventOutbox outbox(segments,crypto,key);
    require(outbox.recover()==OutboxRecovery::Empty,"completion fixture empty");
    OutboxJournalBackend backend(outbox);
    gs::hub::HubJournal journal(0);
    require(journal.attach_backend(backend),"completion backend attached");
    const auto committed=event(9001);
    require(journal.commit(committed)==gs::hub::CommitResult::Stored,"completion body durable");
    gs::hub::CloudSync cloud(journal);
    cloud.set_connected(true,0);
    require(cloud.next_batch(0,4).size()==1,"pending body selected");

    ScriptedBackendTransport transport;
    transport.reply={gs::hub::BackendReplyStatus::NetworkFailure,committed.key,false,false};
    require(cloud.drive_batch(transport,"home",0,4)==1,"network attempt executed");
    bool completed=false;
    require(outbox.backend_completed(committed.key.str(),completed)&&!completed,
            "network attempt does not complete body");
    require(cloud.next_batch(1001,4).size()==1,"lost reply remains retryable");

    auto wrong=committed.key;wrong.sequence++;
    transport.reply={gs::hub::BackendReplyStatus::Committed,wrong,true,false};
    require(cloud.drive_batch(transport,"home",1001,4)==1,"wrong-key reply processed");
    require(outbox.backend_completed(committed.key.str(),completed)&&!completed,
            "wrong identity cannot complete body");

    transport.reply={gs::hub::BackendReplyStatus::Committed,committed.key,true,true};
    require(cloud.drive_batch(transport,"home",6001,4)==1,"authenticated duplicate commit retry");
    require(outbox.backend_completed(committed.key.str(),completed)&&completed,
            "exact authenticated completion published");
    const auto completion_count=outbox.backend_completed_count();
    require(cloud.handle_backend_reply(committed.key,transport.reply,6002)==
                gs::hub::BackendReceiptResult::Completed &&
            outbox.backend_completed_count()==completion_count,
            "duplicate receipt is idempotent");
    require(cloud.next_batch(6002,4).empty(),"completed body omitted from pending sync");

    DurableEventOutbox rebooted(segments,crypto,key);
    require(rebooted.recover()==OutboxRecovery::Ready,"completion survives outbox reboot");
    OutboxJournalBackend reboot_backend(rebooted);
    gs::hub::HubJournal reboot_journal(0);
    require(reboot_journal.attach_backend(reboot_backend),"reboot completion backend attached");
    gs::hub::CloudSync reboot_cloud(reboot_journal);
    reboot_cloud.set_connected(true,6000);
    require(reboot_cloud.next_batch(6000,4).empty() &&
            reboot_journal.cloud_completed(committed.key),
            "reboot preserves completion and suppresses replay");
}

void sparse_checkpoint_replay_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key=storage_key();
    MemorySegments segments(4U*1024U*1024U);StateFiles files;
    DurableEventOutbox outbox(segments,crypto,key);
    require(outbox.recover()==OutboxRecovery::Empty,"sparse source empty");
    OutboxJournalBackend backend(outbox);RuntimeStateStore state(files,crypto,key);
    gs::hub::HubRuntime source(32,backend);source.bind_runtime_state(state);
    require(source.restore_from_journal(),"sparse source initialized");
    source.authorize_node("room1",42,true);
    for(std::uint64_t sequence=1;sequence<=3;++sequence) {
        auto e=event(sequence);
        e.kind=sequence==1 ? gs::EventKind::Heartbeat :
              sequence==2 ? gs::EventKind::DoorOpen : gs::EventKind::CallFamily;
        require(source.radio_callback(e)&&source.run_state_once(100)->ack==gs::AckClass::Durable,
                "checkpoint prefix event committed");
    }
    const auto prefix_segments=segments;
    const auto prefix_files=files;
    auto fourth=event(4);
    fourth.kind=gs::EventKind::DoorClosed;

    MemorySegments expected_segments=prefix_segments;StateFiles expected_files=prefix_files;
    DurableEventOutbox expected_outbox(expected_segments,crypto,key);
    require(expected_outbox.recover()==OutboxRecovery::Ready,"expected prefix recovered");
    OutboxJournalBackend expected_backend(expected_outbox);
    RuntimeStateStore expected_state(expected_files,crypto,key);
    gs::hub::HubRuntime uninterrupted(32,expected_backend);
    uninterrupted.bind_runtime_state(expected_state);
    require(uninterrupted.restore_from_journal(),"expected prefix runtime restored");
    uninterrupted.authorize_node("room1",42,true);
    require(uninterrupted.radio_callback(fourth)&&
            uninterrupted.run_state_once(100)->ack==gs::AckClass::Durable,
            "uninterrupted fourth transition");
    Bytes expected;require(gs::hub::HubCheckpointCodec::encode(uninterrupted,expected),
                           "uninterrupted checkpoint encoded");

    RuntimeStateStore staged_state(files,crypto,key);
    require(staged_state.recover(3)&&staged_state.prepare_identity(fourth,4,100)&&
            staged_state.confirm_event_publication(4),"sparse event identity committed");
    SparseOrdinalBackend sparse;
    sparse.highwater=4;sparse.retained.push_back({4,fourth});
    RuntimeStateStore sparse_state(files,crypto,key);
    gs::hub::HubRuntime recovered(32,sparse);recovered.bind_runtime_state(sparse_state);
    require(recovered.restore_from_journal(),"checkpoint plus sparse ordinal tail recovered");
    Bytes actual;require(gs::hub::HubCheckpointCodec::encode(recovered,actual)&&actual==expected,
                         "sparse replay equals uninterrupted state");

    auto gap_files=prefix_files;
    RuntimeStateStore gap_writer(gap_files,crypto,key);
    require(gap_writer.recover(3),"gap fixture recovered");
    require(gap_writer.prepare_identity(fourth,4,100)&&gap_writer.confirm_event_publication(4),
            "missing checkpoint-tail body identity committed");
    const auto fifth=event(5);
    require(gap_writer.prepare_identity(fifth,5,100)&&gap_writer.confirm_event_publication(5),
            "uncheckpointed gap identity staged");
    SparseOrdinalBackend gap;
    gap.highwater=5;gap.retained.push_back({5,fifth});
    RuntimeStateStore gap_state(gap_files,crypto,key);
    gs::hub::HubRuntime rejected(32,gap);rejected.bind_runtime_state(gap_state);
    require(!rejected.restore_from_journal()&&!rejected.durable_admission_open(),
            "uncheckpointed missing body fails closed");
}

}
int main() {
    try {checkpoint_tests();interruption_tests();published_checkpoint_interruption();timer_and_scale_tests();
        backend_completion_lifecycle_tests();sparse_checkpoint_replay_tests();
        std::cout<<"PASS: runtime checkpoint, replay, exact identity, crash boundaries\n";return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
