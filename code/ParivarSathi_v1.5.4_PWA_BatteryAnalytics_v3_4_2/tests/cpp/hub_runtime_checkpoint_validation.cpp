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
    gs::ActivityRuleConfig activity_config;
    activity_config.morning_start_minute = 0;
    activity_config.morning_end_minute = 200;
    runtime.configure_activity_rules(activity_config);
    auto first=event(1);runtime.authorize_node(first.key.source_id,first.key.session_id,true);
    require(runtime.radio_callback(first)&&runtime.run_state_once(100)->ack==gs::AckClass::Durable,"first publication");
    auto e=event(3);segments.fail_next_publication();
    require(runtime.radio_callback(e),"queue");require(runtime.run_state_once(100)->ack==gs::AckClass::Rejected,"unpublished body no ACK");
    DurableEventOutbox recovered(segments,crypto,key);require(recovered.recover()==OutboxRecovery::Ready,"body staged behind existing root");
    OutboxJournalBackend rb(recovered);RuntimeStateStore rs(files,crypto,key);gs::hub::HubRuntime rr(32,rb);rr.bind_runtime_state(rs);
    require(rr.restore_from_journal(),"staged identity recovery");rr.authorize_node(e.key.source_id,e.key.session_id,true);
    require(rr.radio_callback(e)&&rr.run_state_once(999)->ack==gs::AckClass::Durable,"original context retry");
    require(rs.identities()==2,"retry no duplicate identity");

    MemorySegments reference_segments(4U*1024U*1024U);StateFiles reference_files;
    DurableEventOutbox reference_outbox(reference_segments,crypto,key);
    require(reference_outbox.recover()==OutboxRecovery::Empty,"reference begins empty");
    OutboxJournalBackend reference_backend(reference_outbox);
    RuntimeStateStore reference_state(reference_files,crypto,key);
    gs::hub::HubRuntime reference(32,reference_backend);
    reference.bind_runtime_state(reference_state);
    require(reference.restore_from_journal(),"reference checkpoint initializes");
    reference.configure_activity_rules(activity_config);
    auto reference_first=event(1);
    reference.authorize_node(reference_first.key.source_id,reference_first.key.session_id,true);
    require(reference.radio_callback(reference_first) &&
            reference.run_state_once(100)->ack==gs::AckClass::Durable,
            "reference first event commits with original local-time context");
    reference.authorize_node(e.key.source_id,e.key.session_id,true);
    require(reference.radio_callback(e) && reference.run_state_once(100)->ack==gs::AckClass::Durable,
            "reference retry event commits with persisted local-time context");
    Bytes recovered_checkpoint, reference_checkpoint;
    std::uint64_t recovered_boundary=0, reference_boundary=0;
    bool recovered_checkpoint_found=false, reference_checkpoint_found=false;
    require(rs.load_checkpoint(recovered_checkpoint,recovered_boundary,recovered_checkpoint_found) &&
            reference_state.load_checkpoint(reference_checkpoint,reference_boundary,
                                             reference_checkpoint_found) &&
            recovered_checkpoint_found && reference_checkpoint_found &&
            recovered_boundary==reference_boundary &&
            recovered_checkpoint==reference_checkpoint,
            "retry uses the original persisted time context for reducer state");
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

struct NodeRetirementProof {
    std::uint64_t highwater{0};
    bool allow{true};
    std::uint32_t owner_session{42};
};
bool node_report_covers_event(void* opaque, std::uint64_t,
        const std::string& canonical_key, const Bytes& payload) {
    const auto& proof = *static_cast<NodeRetirementProof*>(opaque);
    gs::DomainEvent event;
    if (!proof.allow || !gs::hub::HubJournal::decode_event_payload(payload, event) ||
        event.key.str() != canonical_key || event.key.source_id != "room1" ||
        event.key.physical_device_id != "device-room1" || event.key.session_id != proof.owner_session ||
        event.key.sequence > proof.highwater) return false;
    return true;
}

void complete_outbox_cycle(gs::hub::HubRuntime& runtime, std::uint64_t first,
                           std::uint64_t last) {
    gs::hub::CloudSync cloud(runtime.journal());
    cloud.set_connected(true, first);
    for (std::uint64_t sequence = first; sequence <= last; ++sequence) {
        const gs::EventKey key("room1", 42, sequence, "device-room1");
        const gs::hub::BackendCommitReply receipt{
            gs::hub::BackendReplyStatus::Committed, key, true, false};
        require(cloud.handle_backend_reply(key, receipt, sequence) ==
                    gs::hub::BackendReceiptResult::Completed,
                "only exact authenticated backend receipts publish completion");
    }
}

struct RetainedIdentityCapture {
    std::vector<gs::hub::storage::IdentityCompactionRecord> records;
};
bool capture_retained_identity(void* opaque,
        const gs::hub::storage::IdentityCompactionRecord& record) {
    static_cast<RetainedIdentityCapture*>(opaque)->records.push_back(record);
    return true;
}

void identity_compaction_planning_test() {
    using namespace gs::hub::storage;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    DurableEventOutbox outbox(segments, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty,
            "identity plan fixture starts with empty outbox");
    RuntimeStateStore state(files, crypto, key);
    OutboxJournalBackend backend(outbox);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    runtime.authorize_node("room1", 42, true);
    require(runtime.restore_from_journal(), "identity plan runtime recovery");

    auto legacy = gs::domain_event_from_node_message(make_message(1), 0);
    legacy.key.physical_device_id = "device-room1";
    require(runtime.radio_callback(legacy) &&
            runtime.run_state_once(100)->ack == gs::AckClass::Durable,
            "legacy identity row admitted before owner fence and retained in plan");
    std::array<std::uint8_t, 32> binding{};
    binding.fill(0x3d);
    const auto second = make_message(2);
    require(runtime.authenticated_radio_message_callback(second, "room1", "device-room1",
                42, 0, 2000, 0, 3, binding) &&
            runtime.run_state_once(200)->ack == gs::AckClass::Durable,
            "owner-bound identity row admitted after legacy row");

    gs::hub::durable::RetirementSnapshot snapshot;
    snapshot.storage_epoch = 7;
    snapshot.generation = 1;
    snapshot.occupancy_mask = 1;
    auto& node = snapshot.nodes[0];
    node.binding_digest = binding;
    node.enrollment_generation = 3;
    node.report_generation = 1;
    node.report_hmac.fill(0x22);
    node.current_origin_session = 42;
    node.durable_admission_highwater = 2;
    node.pending_count = 1;
    node.pending[0] = {42, 2};
    gs::hub::durable::ReportSnapshotReference reference;
    reference.bank = 0;
    reference.generation = 1;
    reference.digest.fill(0x44);
    require(outbox.publish_replay_fence(7, reference, 2) &&
            runtime.bind_replay_fence(snapshot, 7, reference, outbox),
            "identity plan is bound to the selected durable fence");
    complete_outbox_cycle(runtime, 1, 2);

    RetainedIdentityCapture retained;
    IdentityCompactionPlan plan;
    const auto original_bytes = state.identity_bytes();
    const auto original_log = files.files.at("identity.log");
    const auto original_head = files.files.at("identity.head");
    require(runtime.plan_identity_compaction(capture_retained_identity, &retained, plan) &&
            plan.complete && plan.source_records == 2 && plan.retained_records == 2 &&
            plan.fenced_records == 0 && retained.records.size() == 2,
            "pending owner-bound and legacy rows are retained");
    require(plan.candidate_record_bytes == original_bytes &&
            retained.records[0].original_ordinal == 1 &&
            retained.records[1].original_ordinal == 2 &&
            retained.records[0].local_minute == std::optional<std::uint16_t>{100} &&
            retained.records[1].local_minute == std::optional<std::uint16_t>{200} &&
            retained.records[1].event_key == gs::EventKey(
                "room1", 42, 2, "device-room1").str() &&
            retained.records[1].owner.authenticated() &&
            retained.records[1].owner.enrollment_generation == 3 &&
            std::any_of(retained.records[1].payload_digest.begin(),
                retained.records[1].payload_digest.end(), [](std::uint8_t b) { return b != 0; }),
            "pending and legacy metadata remain ordered in planned output");

    node.pending_count = 0;
    node.durable_admission_highwater = 1;
    reference.generation = 2;
    reference.bank = 1;
    reference.digest.fill(0x55);
    snapshot.generation = 2;
    require(outbox.publish_replay_fence(7, reference, 2) &&
            runtime.bind_replay_fence(snapshot, 7, reference, outbox),
            "retirement high-water advances only through the covered prefix");
    retained.records.clear();
    require(runtime.plan_identity_compaction(capture_retained_identity, &retained, plan) &&
            plan.fenced_records == 0 && plan.retained_records == 2,
            "sequence above a gap boundary remains retained");

    node.durable_admission_highwater = 2;
    reference.generation = 3;
    reference.bank = 2;
    reference.digest.fill(0x56);
    snapshot.generation = 3;
    require(outbox.publish_replay_fence(7, reference, 2) &&
            runtime.bind_replay_fence(snapshot, 7, reference, outbox),
            "drained authenticated report advances the retirement fence");
    retained.records.clear();
    require(runtime.plan_identity_compaction(capture_retained_identity, &retained, plan) &&
            plan.complete && plan.source_records == 2 && plan.retained_records == 1 &&
            plan.fenced_records == 1 && retained.records.size() == 1 &&
            retained.records[0].original_ordinal == 1 &&
            plan.candidate_record_bytes < plan.source_bytes,
            "mixed plan retains legacy exact identity and excludes only fenced identity");
    require(files.files.at("identity.log") == original_log &&
            files.files.at("identity.head") == original_head &&
            state.identity_bytes() == original_bytes,
            "planning does not modify the authoritative original ledger");
    const auto successful_plan = plan;
    std::cout << "identity_plan_original_bytes=" << successful_plan.source_bytes
              << " candidate_record_bytes=" << successful_plan.candidate_record_bytes
              << " retained=" << successful_plan.retained_records
              << " fenced=" << successful_plan.fenced_records
              << " extra_flash_reclaimed=0\n";
    retained.records.clear();
    require(runtime.plan_identity_compaction(capture_retained_identity, &retained, plan) &&
            plan.candidate_digest == successful_plan.candidate_digest &&
            plan.source_head_digest == successful_plan.source_head_digest &&
            plan.candidate_record_bytes == successful_plan.candidate_record_bytes,
            "repeated preparation is deterministic and leaves original authoritative");

    DurableEventOutbox reboot_outbox(segments, crypto, key);
    require(reboot_outbox.recover() == OutboxRecovery::Ready,
            "identity plan reboot recovers current outbox");
    OutboxJournalBackend reboot_backend(reboot_outbox);
    RuntimeStateStore reboot_state(files, crypto, key);
    gs::hub::HubRuntime reboot_runtime(32, reboot_backend);
    reboot_runtime.bind_runtime_state(reboot_state);
    reboot_runtime.authorize_node("room1", 42, true);
    require(reboot_runtime.restore_from_journal() &&
            reboot_runtime.bind_replay_fence(snapshot, 7, reference, reboot_outbox),
            "identity plan reboot restores selected fence and exact identities");
    retained.records.clear();
    IdentityCompactionPlan reboot_plan;
    require(reboot_runtime.plan_identity_compaction(capture_retained_identity,
                &retained, reboot_plan) &&
            reboot_plan.candidate_digest == successful_plan.candidate_digest,
            "reboot reproduces the same guarded compaction plan");

    auto changed_reference = reference;
    changed_reference.generation = 4;
    changed_reference.bank = 0;
    changed_reference.digest.fill(0x66);
    struct FenceChangeContext {
        gs::hub::HubRuntime* runtime;
        DurableEventOutbox* outbox;
        gs::hub::durable::RetirementSnapshot snapshot;
        gs::hub::durable::ReportSnapshotReference reference;
        bool changed{false};
    } change{&reboot_runtime, &reboot_outbox, snapshot, changed_reference};
    auto change_fence_during_visit = [](void* opaque,
            const IdentityCompactionRecord& record) {
        auto& state = *static_cast<FenceChangeContext*>(opaque);
        if (!state.changed) {
            state.snapshot.generation = state.reference.generation;
            if (state.outbox->publish_replay_fence(7, state.reference, 2) &&
                state.runtime->bind_replay_fence(state.snapshot, 7,
                    state.reference, *state.outbox)) state.changed = true;
        }
        return state.changed && !record.event_key.empty();
    };
    require(!reboot_runtime.plan_identity_compaction(change_fence_during_visit,
                &change, reboot_plan) && change.changed && !reboot_plan.complete,
            "fence change during iteration invalidates the plan");
    require(files.files.at("identity.log") == original_log &&
            files.files.at("identity.head") == original_head,
            "invalidated plan leaves the authoritative original unchanged");

    // The plan is a lower bound on temporary bytes: any available space below
    // this amount is necessarily insufficient even before envelope overhead.
    retained.records.clear();
    require(reboot_runtime.plan_identity_compaction(capture_retained_identity,
                &retained, reboot_plan), "plan can be regenerated after fence change");
    require(reboot_plan.candidate_record_bytes > 0 &&
            reboot_plan.minimum_temporary_bytes == reboot_plan.candidate_record_bytes &&
            reboot_plan.minimum_temporary_bytes - 1U < reboot_plan.minimum_temporary_bytes,
            "temporary capacity below the record lower bound is insufficient");

    auto& corrupt_log = files.files.at("identity.log");
    corrupt_log[4] ^= 0x80;
    retained.records.clear();
    require(!reboot_runtime.plan_identity_compaction(capture_retained_identity,
                &retained, reboot_plan) && reboot_plan.blocked_records != 0,
            "corrupt authenticated identity row blocks planning");
}

void replay_fence_and_eligibility_tests() {
    using namespace gs::hub::storage;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    DurableEventOutbox outbox(segments, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty, "replay fence empty outbox");
    RuntimeStateStore state(files, crypto, key);
    OutboxJournalBackend backend(outbox);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    runtime.authorize_node("room1", 42, true);
    require(runtime.restore_from_journal(), "replay fence runtime recovery");

    std::array<std::uint8_t, 32> binding_digest{};
    binding_digest.fill(0x2d);
    const auto message = make_message(1);
    require(runtime.authenticated_radio_message_callback(message, "room1", "device-room1",
                42, 0, 1000, 0, 3, binding_digest), "authenticated owner event accepted");
    const auto processed = runtime.run_state_once();
    require(processed && processed->ack == gs::AckClass::Durable,
            "event and identity are durable before ACK");
    gs::hub::durable::RetirementSnapshot snapshot;
    snapshot.storage_epoch = 7;
    snapshot.generation = 2;
    snapshot.occupancy_mask = 1;
    auto& node = snapshot.nodes[0];
    node.binding_digest = binding_digest;
    node.enrollment_generation = 3;
    node.current_origin_session = 42;
    node.durable_admission_highwater = 3;
    auto exact = gs::domain_event_from_node_message(message, 0);
    exact.key.physical_device_id = "device-room1";
    require(runtime.identity_retirement_eligibility(exact, 0, 3, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::NotEligible,
            "missing persisted Node retirement proof fails closed");
    gs::hub::durable::ReportSnapshotReference reference;
    reference.bank = 1;
    reference.generation = 2;
    reference.digest.fill(0x5a);
    require(outbox.publish_replay_fence(snapshot.storage_epoch, reference, 1) &&
            runtime.bind_replay_fence(snapshot, snapshot.storage_epoch, reference, outbox),
            "selected retirement reference is witnessed by lifecycle root");

    std::array<std::uint8_t, 32> wrong_binding{};
    wrong_binding.fill(0xee);
    require(runtime.identity_retirement_eligibility(exact, 0, 3, wrong_binding) ==
                gs::hub::IdentityRetirementEligibility::NotEligible,
            "retirement eligibility requires the authenticated owner binding digest");
    require(runtime.identity_retirement_eligibility(exact, 0, 3, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::NotEligible,
            "missing durable backend completion blocks identity eligibility");
    complete_outbox_cycle(runtime, 1, 1);
    require(runtime.identity_retirement_eligibility(exact, 0, 3, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::EligibleWithDurableReplayFence,
            "exact completed identity with checkpoint, retirement and replay fence is eligible");
    DurableEventOutbox owner_reboot_outbox(segments, crypto, key);
    require(owner_reboot_outbox.recover() == OutboxRecovery::Ready,
            "replay fence recovers before restart eligibility check");
    OutboxJournalBackend owner_reboot_backend(owner_reboot_outbox);
    RuntimeStateStore owner_reboot_state(files, crypto, key);
    gs::hub::HubRuntime owner_reboot_runtime(32, owner_reboot_backend);
    owner_reboot_runtime.bind_runtime_state(owner_reboot_state);
    require(owner_reboot_runtime.restore_from_journal() &&
            owner_reboot_runtime.bind_replay_fence(snapshot, snapshot.storage_epoch,
                reference, owner_reboot_outbox) &&
            owner_reboot_runtime.identity_retirement_eligibility(exact, 0, 3,
                binding_digest) ==
                gs::hub::IdentityRetirementEligibility::EligibleWithDurableReplayFence,
            "restart preserves authenticated identity owner and eligibility proof");
    auto wrong_session = exact;
    wrong_session.key.session_id = 41;
    require(runtime.identity_retirement_eligibility(wrong_session, 0, 3, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::NotEligible,
            "wrong original EventKey session is not eligible");
    require(runtime.authenticated_radio_message_callback(message, "room1", "device-room1",
                42, 0, 2000, 0, 3, binding_digest),
            "retained exact duplicate keeps ordinary duplicate handling");
    const auto duplicate = runtime.run_state_once();
    require(duplicate && duplicate->ack == gs::AckClass::Durable && !duplicate->state_changed,
            "exact retry after fence does not reapply effects");

    auto stale = make_message(3);
    require(!runtime.authenticated_radio_message_callback(stale, "room1", "device-room1",
                42, 0, 3000, 0, 3, binding_digest),
            "covered retired key without retained identity is rejected before admission");
    require(runtime.identity_retirement_eligibility(exact, 1, 3, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::NotEligible &&
            runtime.identity_retirement_eligibility(exact, 0, 4, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::NotEligible,
            "wrong owner slot or stale enrollment generation fails eligibility closed");

    snapshot.generation = 3;
    snapshot.nodes[0].pending_count = 1;
    snapshot.nodes[0].pending[0] = {42, 1};
    reference.generation = 3;
    reference.bank = 2;
    reference.digest.fill(0x6b);
    require(outbox.publish_replay_fence(snapshot.storage_epoch, reference, 1) &&
            runtime.bind_replay_fence(snapshot, snapshot.storage_epoch, reference, outbox),
            "pending exception is published in next bounded fence snapshot");
    require(runtime.identity_retirement_eligibility(exact, 0, 3, binding_digest) ==
                gs::hub::IdentityRetirementEligibility::NotEligible,
            "pending exact key blocks identity eligibility");

    Bytes first_root;
    bool root_found = false;
    require(segments.read_lifecycle_root(first_root, root_found) && root_found,
            "bounded replay fence lifecycle root exists");
    for (std::uint64_t generation = 4; generation <= 20; ++generation) {
        snapshot.generation = generation;
        reference.generation = generation;
        reference.bank = static_cast<std::uint8_t>(generation % 3U);
        reference.digest.fill(static_cast<std::uint8_t>(generation));
        require(outbox.publish_replay_fence(snapshot.storage_epoch, reference, 1) &&
                runtime.bind_replay_fence(snapshot, snapshot.storage_epoch, reference, outbox),
                "bounded NVS bank rotation and fence advance");
        Bytes observed;
        require(segments.read_lifecycle_root(observed, root_found) && root_found &&
                observed.size() == first_root.size(),
                "repeated fence advances reuse fixed-size lifecycle metadata");
    }

    DurableEventOutbox recovered(segments, crypto, key);
    require(recovered.recover() == OutboxRecovery::Ready &&
            recovered.replay_fence_matches(snapshot.storage_epoch, reference),
            "replay fence authority survives restart");
}

void replay_fence_publication_cut_tests() {
    using namespace gs::hub::storage;
    for (bool fail_after_write : {false, true}) {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = storage_key();
        MemorySegments segments(4U * 1024U * 1024U);
        DurableEventOutbox outbox(segments, crypto, key);
        require(outbox.recover() == OutboxRecovery::Empty, "fence cut starts empty");
        gs::hub::durable::ReportSnapshotReference reference;
        reference.bank = 0;
        reference.generation = 1;
        reference.digest.fill(0x3c);
        segments.fail_lifecycle_publication_after_write_once = fail_after_write;
        segments.fail_lifecycle_publication_once = !fail_after_write;
        require(!outbox.publish_replay_fence(9, reference, 0),
                "ambiguous lifecycle publication does not open the writer");
        DurableEventOutbox rebooted(segments, crypto, key);
        const auto recovered = rebooted.recover();
        require(recovered == OutboxRecovery::Empty,
                "publication cut recovers without fabricated outbox data");
        require(rebooted.replay_fence_matches(9, reference) == fail_after_write,
                "pre-publication cut keeps old authority; post-publication cut selects new fence");
    }
}

void segmented_lifecycle_reuse_tests() {
    using namespace gs::hub::storage;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    OutboxLimits limits;
    limits.segment_count = 16;
    limits.segment_bytes = 16U * 1024U;
    limits.filesystem_workspace_bytes = 128U * 1024U;
    limits.protected_capacity_bytes = 0;
    limits.body_retirement_enabled = true;  // Host-only approved retention gate fixture.

    for (std::uint64_t cycle = 0; cycle < 3; ++cycle) {
        const std::uint64_t first = cycle * 100U + 1U;
        const std::uint64_t last = first + 99U;
        DurableEventOutbox outbox(segments, crypto, key, limits);
        const auto recovery = outbox.recover();
        require(recovery == OutboxRecovery::Empty &&
                outbox.record_count() == first - 1U &&
                outbox.retired_through() == first - 1U,
                "outbox recovers before each refill cycle");
        RuntimeStateStore state(files, crypto, key);
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.bind_runtime_state(state);
        require(runtime.restore_from_journal(), "runtime restores checkpoint before refill");
        runtime.authorize_node("room1", 42, true);
        for (std::uint64_t sequence = first; sequence <= last; ++sequence) {
            const auto message = make_message(sequence);
            require(runtime.authenticated_radio_message_callback(message, "room1",
                        "device-room1", 42, 0, sequence * 1000U),
                    "Node event enters authenticated production runtime path");
            const auto processed = runtime.run_state_once(100);
            require(processed && processed->ack == gs::AckClass::Durable,
                    "runtime ACK follows event, identity and reducer checkpoint publication");
        }
        require(outbox.record_count() == last && outbox.capacity_budget_used_bytes() != 0,
                "refill cycle stores exact event bodies in segment capacity");

        NodeRetirementProof node_proof{last, true};
        RetirementAuthorization authorization;
        authorization.checkpoint_boundary = last;
        authorization.authenticated_report_generation = cycle + 1;
        authorization.authenticated_report_digest.fill(
            static_cast<std::uint8_t>(0x41U + cycle));
        authorization.post_sync_retention_satisfied = true;
        authorization.node_retired = node_report_covers_event;
        authorization.context = &node_proof;
        require(outbox.reclaim_completed_history(authorization) ==
                    ReclaimResult::PendingBackendCompletion,
                "Node report and checkpoint cannot retire backend-pending bodies");

        complete_outbox_cycle(runtime, first, last);
        authorization.post_sync_retention_satisfied = false;
        require(outbox.reclaim_completed_history(authorization) ==
                    ReclaimResult::DisabledByRetentionGate,
                "default post-sync retention gate blocks deletion");
        authorization.post_sync_retention_satisfied = true;
        node_proof.allow = false;
        require(outbox.reclaim_completed_history(authorization) ==
                    ReclaimResult::MissingNodeRetirementProof,
                "missing authenticated Node retirement coverage blocks deletion");
        node_proof.allow = true;
        if (cycle == 0) segments.fail_remove_once = true;
        const auto reclaimed = outbox.reclaim_completed_history(authorization);
        if (cycle == 0) {
            require(reclaimed == ReclaimResult::RestartRequired,
                    "interruption after lifecycle-root publication is not reported complete");
        } else {
            require(reclaimed == ReclaimResult::Reclaimed,
                    "completed/checkpointed/Node-retired bodies are reclaimed");
        }
    }

    // The first reclamation was interrupted after publishing the lifecycle root.
    // Recovery completes completion-log reset and segment removal idempotently.
    DurableEventOutbox recovered(segments, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Empty &&
            recovered.record_count() == 300 && recovered.retired_through() == 300 &&
            recovered.capacity_budget_used_bytes() == 0 && recovered.completion_bytes() == 0,
            "recovery finishes pending lifecycle transaction and restores capacity");
    RuntimeStateStore state(files, crypto, key);
    OutboxJournalBackend backend(recovered);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    require(runtime.restore_from_journal(),
            "retired body prefix restores from checkpoint and exact identity log");
    runtime.authorize_node("room1", 42, true);
    const auto old_retry = make_message(17);
    require(runtime.authenticated_radio_message_callback(old_retry, "room1",
                "device-room1", 42, 0, 999999) ,
            "retry after body retirement reaches identity ledger");
    const auto duplicate = runtime.run_state_once(100);
    require(duplicate && duplicate->ack == gs::AckClass::Durable &&
            !duplicate->state_changed && runtime.journal().size() == 300,
            "retired-body retry is ACKed from exact identity without reapplying effects");
}

void lifecycle_publication_cut_tests() {
    using namespace gs::hub::storage;
    for (unsigned cut = 0; cut < 3; ++cut) {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = storage_key();
        MemorySegments segments(4U * 1024U * 1024U);
        StateFiles files;
        OutboxLimits limits;
        limits.protected_capacity_bytes = 0;
        limits.body_retirement_enabled = true;
        DurableEventOutbox outbox(segments, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty, "cut fixture starts empty");
        RuntimeStateStore state(files, crypto, key);
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.bind_runtime_state(state);
        require(runtime.restore_from_journal(), "cut fixture runtime recovers");
        runtime.authorize_node("room1", 42, true);
        for (std::uint64_t sequence = 1; sequence <= 2; ++sequence) {
            const auto message = make_message(sequence);
            require(runtime.authenticated_radio_message_callback(message, "room1",
                        "device-room1", 42, 0, sequence * 1000U) &&
                    runtime.run_state_once(100)->ack == gs::AckClass::Durable,
                    "cut fixture event admission is durable");
        }
        complete_outbox_cycle(runtime, 1, 2);

        NodeRetirementProof node_proof{2, true};
        RetirementAuthorization authorization;
        authorization.checkpoint_boundary = 2;
        authorization.authenticated_report_generation = 1;
        authorization.authenticated_report_digest.fill(0x73);
        authorization.post_sync_retention_satisfied = true;
        authorization.node_retired = node_report_covers_event;
        authorization.context = &node_proof;
        if (cut == 0) segments.fail_lifecycle_publication_once = true;
        if (cut == 1) segments.fail_lifecycle_publication_after_write_once = true;
        if (cut == 2) segments.fail_truncate_after_write_once = true;
        const auto result = outbox.reclaim_completed_history(authorization);
        require(result != ReclaimResult::Reclaimed,
                "injected lifecycle cut cannot report reclamation complete");

        // Stop using the failed instance immediately, then recover through the
        // production outbox API as after a power interruption.
        DurableEventOutbox recovered(segments, crypto, key, limits);
        const auto recovery = recovered.recover();
        const bool recovered_valid = recovery == OutboxRecovery::Ready ||
            (cut != 0 && recovery == OutboxRecovery::Empty);
        if (!recovered_valid)
            std::cerr << "lifecycle_cut=" << cut << " recovery="
                      << static_cast<unsigned>(recovery) << "\n";
        require(recovered_valid,
                "lifecycle cut recovers a valid committed generation");
        if (cut == 0) {
            require(recovered.retired_through() == 0 && recovered.record_count() == 2 &&
                    recovered.capacity_budget_used_bytes() != 0 &&
                    recovered.backend_completed_count() == 2,
                    "pre-publication failure preserves all completed bodies");
        } else {
            require(recovered.retired_through() == 2 && recovered.record_count() == 2 &&
                    recovered.capacity_budget_used_bytes() == 0 &&
                    recovered.backend_completed_count() == 0,
                    "published lifecycle root completes reset and body reclaim on restart");
        }
    }
}

void high_volume_lifecycle_test() {
    using namespace gs::hub::storage;
    constexpr std::uint64_t count = 3278;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    OutboxLimits limits;
    limits.protected_capacity_bytes = 0;
    limits.body_retirement_enabled = true;  // Deterministic host authorization fixture.
    DurableEventOutbox outbox(segments, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "HIGH lifecycle starts empty");
    RuntimeStateStore state(files, crypto, key);
    OutboxJournalBackend backend(outbox);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    require(runtime.restore_from_journal(), "HIGH lifecycle runtime restores");
    runtime.authorize_node("room1", 42, true);
    for (std::uint64_t sequence = 1; sequence <= count; ++sequence) {
        auto fixture_event = event(sequence);
        switch (sequence % 8U) {
            case 0: fixture_event.kind = gs::EventKind::Motion; break;
            case 1: fixture_event.kind = gs::EventKind::DoorOpen;
                    fixture_event.sensor_type = gs::SensorType::Reed; break;
            case 2: fixture_event.kind = gs::EventKind::DoorClosed;
                    fixture_event.sensor_type = gs::SensorType::Reed; break;
            case 3: fixture_event.kind = gs::EventKind::CallFamily;
                    fixture_event.sensor_type = gs::SensorType::Button; break;
            case 4: fixture_event.kind = gs::EventKind::OkPressed;
                    fixture_event.sensor_type = gs::SensorType::Button; break;
            case 5: fixture_event.kind = gs::EventKind::Gap;
                    fixture_event.sensor_type = gs::SensorType::System; break;
            case 6: fixture_event.kind = gs::EventKind::Heartbeat;
                    fixture_event.sensor_type = gs::SensorType::Heartbeat; break;
            default:
                fixture_event.kind = gs::EventKind::MotionSummary;
                fixture_event.sensor_type = gs::SensorType::Pir;
                fixture_event.motion_aggregate = gs::DomainEvent::MotionAggregate{
                    3, fixture_event.monotonic_ms - 1500, fixture_event.monotonic_ms};
                break;
        }
        const auto message = gs::node_message_from_event(fixture_event);
        require(runtime.authenticated_radio_message_callback(message, "room1",
                    "device-room1", 42, 0, sequence * 1000U),
                "HIGH mixed exact event admitted through authenticated runtime path");
        const auto processed = runtime.run_state_once(100);
        require(processed && processed->ack == gs::AckClass::Durable,
                "HIGH Durable ACK follows event publication");
    }
    bool first_identity_found = false;
    bool last_identity_found = false;
    require(outbox.record_count() == count && state.identity_bytes() != 0 &&
            state.contains_identity(event(1).key, first_identity_found) && first_identity_found &&
            state.contains_identity(event(count).key, last_identity_found) && last_identity_found,
            "HIGH body and independent identities both retained");
    const auto high_event_bytes = outbox.capacity_budget_used_bytes();

    gs::hub::CloudSync cloud(runtime.journal());
    cloud.set_connected(true, count);
    for (std::uint64_t sequence = 1; sequence <= count; ++sequence) {
        const auto event_key = event(sequence).key;
        const gs::hub::BackendCommitReply receipt{
            gs::hub::BackendReplyStatus::Committed, event_key, true, false};
        require(cloud.handle_backend_reply(event_key, receipt, sequence) ==
                    gs::hub::BackendReceiptResult::Completed,
                "HIGH event retirement requires exact authenticated backend receipt");
    }
    const auto high_completion_bytes = outbox.completion_bytes();

    NodeRetirementProof node_proof{count, true};
    RetirementAuthorization authorization;
    authorization.checkpoint_boundary = count;
    authorization.authenticated_report_generation = 1;
    authorization.authenticated_report_digest.fill(0x65);
    authorization.post_sync_retention_satisfied = true;
    authorization.node_retired = node_report_covers_event;
    authorization.context = &node_proof;
    require(outbox.reclaim_completed_history(authorization) == ReclaimResult::Reclaimed &&
            outbox.retired_through() == count && outbox.capacity_budget_used_bytes() == 0,
            "HIGH completed history reclaims physical segment capacity");

    const auto refill = make_message(count + 1);
    require(runtime.authenticated_radio_message_callback(refill, "room1",
                "device-room1", 42, 0, (count + 1U) * 1000U) &&
            runtime.run_state_once(100)->ack == gs::AckClass::Durable &&
            outbox.record_count() == count + 1U && outbox.capacity_budget_used_bytes() != 0,
            "HIGH reclaimed capacity accepts a new durable event");
    std::cout << "high_lifecycle_records=" << count
              << " event_bytes_before_reclaim=" << high_event_bytes
              << " retained_identity_bytes=" << state.identity_bytes()
              << " completion_bytes_before_reclaim=" << high_completion_bytes
              << " completion_bytes_after_reclaim=" << outbox.completion_bytes()
              << " refill_bytes=" << outbox.capacity_budget_used_bytes() << "\n";
}

void incremental_completion_reuse_test() {
    using namespace gs::hub::storage;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    std::uint64_t cumulative = 0;
    constexpr std::uint64_t total = 6556;
    for (std::uint64_t window = 0; cumulative < total; ++window) {
        DurableEventOutbox outbox(segments, crypto, key);
        require(outbox.recover() == (window == 0 ? OutboxRecovery::Empty : OutboxRecovery::Ready),
                "incremental window recovers retained mixed history");
        RuntimeStateStore state(files, crypto, key);
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.bind_runtime_state(state);
        require(runtime.restore_from_journal(), "incremental reducer checkpoint restores");
        runtime.authorize_node("room1", 42, true);
        if (window != 0) {
            require(outbox.backend_completed_count() == cumulative, "snapshot completions survive reboot");
            const auto duplicate = make_message(2);
            require(runtime.authenticated_radio_message_callback(duplicate, "room1", "device-room1",
                        42, 0, 999999) && !runtime.run_state_once(100)->state_changed,
                    "ACK-loss duplicate after compaction does not reapply reducer effect");
            gs::hub::CloudSync cloud(runtime.journal());
            cloud.set_connected(true, 0);
            const auto pending = cloud.next_batch(0, total + 1);
            require(pending.size() == (window == 1 ? 2U : 1U) && pending.front().key.sequence == 1,
                    "reboot selects only pending event; completed backend operations are suppressed");
        }
        const auto count = std::min<std::uint64_t>(window == 0 ? 5589 : 500, total - cumulative);
        const auto first = cumulative + 2;
        const auto last = cumulative + count + 1;
        for (auto sequence = window == 0 ? 1 : first; sequence <= last; ++sequence) {
            const auto message = make_message(sequence);
            require(runtime.authenticated_radio_message_callback(message, "room1", "device-room1",
                        42, 0, sequence * 1000) &&
                    runtime.run_state_once(100)->ack == gs::AckClass::Durable,
                    "refill appends authenticated bodies and exact identities without deleting any");
        }
        complete_outbox_cycle(runtime, first, last);
        cumulative += count;
        if (window == 0) {
            const auto extra = make_message(last + 1);
            require(runtime.authenticated_radio_message_callback(extra, "room1", "device-room1", 42,
                        0, (last + 1) * 1000) && runtime.run_state_once(100)->ack == gs::AckClass::Durable,
                    "append pending body beside a full completion stream");
            require(outbox.completion_reclamation_needed() &&
                    !outbox.mark_backend_completed(event(last + 1).key.str()) && outbox.healthy(),
                    "receipt stream is actually full before capacity reclamation");
        }
        const auto body_bytes = outbox.committed_frame_bytes();
        const auto identity_bytes = state.identity_bytes();
        bool exists = false;
        std::uint32_t before = 0, after = 0;
        require(segments.completion_size(exists, before) && exists && before == outbox.completion_bytes(),
                "measure actual adapter receipt bytes before reclaim");
        NodeRetirementProof proof{last, true};
        RetirementAuthorization authorization;
        authorization.checkpoint_boundary = outbox.record_count();
        authorization.authenticated_report_generation = window + 1;
        authorization.authenticated_report_digest.fill(static_cast<std::uint8_t>(0x71 + window));
        authorization.node_retired = node_report_covers_event;
        authorization.context = &proof;
        if (window == 0) {
            proof.allow = false;
            require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::MissingNodeRetirementProof &&
                    outbox.completion_bytes() == before, "missing retirement proof preserves authoritative receipts");
            proof.allow = true;
            proof.owner_session = 41;
            require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::MissingNodeRetirementProof,
                    "stale owner generation in Node proof cannot replace an exact completion");
            proof.owner_session = 42;
            proof.highwater = last - 1;
            require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::MissingNodeRetirementProof,
                    "incomplete report cannot substitute a later completion");
            proof.highwater = last;
            --authorization.checkpoint_boundary;
            require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::CheckpointBehind,
                    "checkpoint dependency must cover snapshot boundary");
            ++authorization.checkpoint_boundary;
        } else {
            --authorization.authenticated_report_generation;
            require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::InvalidAuthorization,
                    "same generation with different report digest cannot replace ownership fence");
            if (window > 1) {
                --authorization.authenticated_report_generation;
                require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::InvalidAuthorization,
                        "stale report generation cannot replace retirement fence");
                ++authorization.authenticated_report_generation;
            }
            ++authorization.authenticated_report_generation;
        }
        require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::Reclaimed,
                "mixed pending and completed history reclaims receipts with body deletion disabled");
        require(segments.completion_size(exists, after) && after == 0 && outbox.completion_bytes() == 0 &&
                outbox.backend_completed_count() == cumulative && outbox.retired_through() == 0 &&
                outbox.committed_frame_bytes() == body_bytes && state.identity_bytes() == identity_bytes,
                "actual writable receipt bytes recovered; bodies and identity evidence stay intact");
        Bytes root; bool found = false;
        require(segments.read_lifecycle_root(root, found) && found && root.size() < 1100,
                "replacement root has bounded compact actual byte size");
        std::cout << "incremental_window=" << window << " cumulative_completions=" << cumulative
                  << " completion_bytes_before=" << before << " completion_bytes_after=" << after
                  << " lifecycle_root_bytes=" << root.size() << " retained_body_bytes=" << body_bytes
                  << " retained_identity_bytes=" << identity_bytes << "\n";
    }
    require(!segments.reused_completion_nonce && segments.all_completion_nonces.size() == total,
            "completion nonce uniqueness survives ordinal reuse across reclamation windows");
    DurableEventOutbox reboot(segments, crypto, key);
    require(reboot.recover() == OutboxRecovery::Ready && reboot.backend_completed_count() == total,
            "6556 cumulative completions recover after repeated append, compact and refill");
}

void incremental_completion_cut_tests() {
    using namespace gs::hub::storage;
    for (unsigned cut = 0; cut < 6; ++cut) {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = storage_key();
        MemorySegments segments(4U * 1024U * 1024U);
        StateFiles files;
        DurableEventOutbox outbox(segments, crypto, key);
        require(outbox.recover() == OutboxRecovery::Empty, "incremental crash fixture empty");
        RuntimeStateStore state(files, crypto, key);
        OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.bind_runtime_state(state);
        require(runtime.restore_from_journal(), "incremental crash fixture checkpoint");
        runtime.authorize_node("room1", 42, true);
        for (std::uint64_t sequence = 1; sequence <= 3; ++sequence) {
            require(runtime.radio_callback(event(sequence)) && runtime.run_state_once(100)->ack == gs::AckClass::Durable,
                    "mixed crash events durably admitted");
        }
        gs::hub::CloudSync cloud(runtime.journal()); cloud.set_connected(true, 0);
        auto wrong = event(2).key; wrong.session_id = 41;
        require(cloud.handle_backend_reply(event(2).key,
                    {gs::hub::BackendReplyStatus::Committed, wrong, true, false}, 0) !=
                    gs::hub::BackendReceiptResult::Completed,
                "wrong owner generation receipt cannot set snapshot bit");
        wrong = event(2).key; wrong.sequence = 3;
        require(cloud.handle_backend_reply(event(2).key,
                    {gs::hub::BackendReplyStatus::Committed, wrong, true, false}, 0) !=
                    gs::hub::BackendReceiptResult::Completed, "wrong-key receipt rejected");
        complete_outbox_cycle(runtime, 2, 2);
        NodeRetirementProof proof{3, true};
        RetirementAuthorization authorization;
        authorization.checkpoint_boundary = 3;
        authorization.authenticated_report_generation = 1;
        authorization.authenticated_report_digest.fill(0x61);
        authorization.node_retired = node_report_covers_event; authorization.context = &proof;
        const auto body_bytes = outbox.committed_frame_bytes();
        if (cut == 0) segments.fail_lifecycle_publication_once = true;
        if (cut == 1) segments.fail_lifecycle_publication_after_write_once = true;
        if (cut == 2) segments.fail_next_completion_publication();
        if (cut == 3) segments.fail_truncate_after_write_once = true;
        if (cut == 4) segments.fail_lifecycle_at = 2;
        if (cut == 5) { segments.fail_lifecycle_at = 2; segments.fail_lifecycle_at_after_write = true; }
        require(outbox.reclaim_completion_metadata(authorization) == ReclaimResult::RestartRequired &&
                !outbox.healthy(), "ambiguous completion compaction requires recovery");
        DurableEventOutbox recovered(segments, crypto, key);
        require(recovered.recover() == OutboxRecovery::Ready && recovered.backend_completed_count() == 1 &&
                recovered.committed_frame_bytes() == body_bytes && recovered.retired_through() == 0,
                "each completion publication cut preserves completed effect and pending bodies");
        bool completed = false;
        require(recovered.backend_completed(event(2).key.str(), completed) && completed &&
                recovered.backend_completed(event(1).key.str(), completed) && !completed &&
                recovered.backend_completed(event(3).key.str(), completed) && !completed,
                "cut recovery restores exact mixed completion identities");
        require(recovered.mark_backend_completed(event(2).key.str()) && recovered.backend_completed_count() == 1,
                "duplicate completion after crash is idempotent");
        require(recovered.mark_backend_completed(event(3).key.str()) && recovered.backend_completed_count() == 2,
                "recovered capacity accepts new completion receipt");
        if (cut == 0) require(recovered.reclaim_completion_metadata(authorization) == ReclaimResult::Reclaimed,
                              "prepublication failure can retry safely");
        if (cut != 0) require(recovered.reclaim_completion_metadata(authorization) == ReclaimResult::Reclaimed,
                              "repeated compaction joins snapshot with new receipt");
        Bytes root; bool found = false;
        require(segments.read_lifecycle_root(root, found) && found, "snapshot present");
        if (cut == 0) {
            auto reused_segments = segments;
            OutboxLimits host_limits; host_limits.body_retirement_enabled = true;
            DurableEventOutbox reused(reused_segments, crypto, key, host_limits);
            require(reused.recover() == OutboxRecovery::Ready &&
                    reused.mark_backend_completed(event(1).key.str()) &&
                    ([&]() { auto body_authorization = authorization;
                        body_authorization.post_sync_retention_satisfied = true;
                        return reused.reclaim_completed_history(body_authorization); })() == ReclaimResult::Reclaimed,
                    "host-only body retirement supersedes completion snapshot safely");
            OutboxJournalBackend reuse_backend(reused);
            gs::hub::HubJournal reuse_journal(0);
            require(reuse_journal.attach_backend(reuse_backend) &&
                    reuse_journal.commit(event(4)) == gs::hub::CommitResult::Stored &&
                    reused.mark_backend_completed(event(4).key.str()),
                    "segment reuse preserves monotonic event ordinals after snapshot retirement");
            proof.highwater = 4;
            auto next_authorization = authorization;
            next_authorization.post_sync_retention_satisfied = true;
            next_authorization.checkpoint_boundary = 4;
            next_authorization.authenticated_report_generation = 2;
            next_authorization.authenticated_report_digest.fill(0x62);
            require(reused.reclaim_completion_metadata(next_authorization) == ReclaimResult::Reclaimed,
                    "receipt snapshot can restart after segment reuse with a nonzero retired prefix");
            DurableEventOutbox reuse_reboot(reused_segments, crypto, key, host_limits);
            require(reuse_reboot.recover() == OutboxRecovery::Ready && reuse_reboot.retired_through() == 3 &&
                    reuse_reboot.record_count() == 4 && reuse_reboot.backend_completed_count() == 1,
                    "nonzero-prefix snapshot and reused segment recover exact completion");
        }
        auto missing_root = segments;
        missing_root.forget_lifecycle_root();
        DurableEventOutbox no_root(missing_root, crypto, key);
        require(no_root.recover() == OutboxRecovery::IntegrityFailure,
                "missing completion snapshot cannot turn completed effects into pending retries");
        auto missing_head = segments;
        missing_head.forget_completion_head();
        DurableEventOutbox no_head(missing_head, crypto, key);
        require(no_head.recover() == OutboxRecovery::IntegrityFailure,
                "missing generation-bound head fails closed beside a snapshot");
        require(recovered.mark_backend_completed(event(1).key.str()), "new receipt after snapshot");
        auto missing_root_with_receipt = segments;
        missing_root_with_receipt.forget_lifecycle_root();
        DurableEventOutbox missing_with_tail(missing_root_with_receipt, crypto, key);
        require(missing_with_tail.recover() == OutboxRecovery::IntegrityFailure,
                "appended heads also require their exact snapshot generation");
        segments.corrupt_completion_receipt();
        require(recovered.reclaim_completion_metadata(authorization) == ReclaimResult::IntegrityFailure,
                "compaction revalidates durable receipts; corrupt evidence cannot be hidden by RAM bits");
        root.back() ^= 1;
        require(segments.publish_lifecycle_root(root), "inject corrupted root");
        DurableEventOutbox corrupt(segments, crypto, key);
        require(corrupt.recover() == OutboxRecovery::IntegrityFailure,
                "corrupt completion snapshot cannot fall back to empty log");
    }
    std::cout << "incremental_crash_cuts=6 wrong_key_and_owner=PASS missing_proof=PASS\n";
}

}
int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--incremental-completion") {
            backend_completion_lifecycle_tests();
            incremental_completion_reuse_test(); incremental_completion_cut_tests();
            std::cout << "PASS: incremental completion reclamation, mixed replay and crash recovery\n";
            return 0;
        }
checkpoint_tests();interruption_tests();published_checkpoint_interruption();timer_and_scale_tests();
        backend_completion_lifecycle_tests();sparse_checkpoint_replay_tests();
        segmented_lifecycle_reuse_tests();
        identity_compaction_planning_test();
        replay_fence_and_eligibility_tests();
        replay_fence_publication_cut_tests();
        lifecycle_publication_cut_tests();
        high_volume_lifecycle_test();
        std::cout<<"PASS: runtime checkpoint, replay, exact identity, crash boundaries\n";return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
