// GS-130 B: production C3 policy/runtime/security + S3 segmented-storage runtime.
// Host adapters replace GPIO/time/channel/files/OTA writer. No SDK task emulation,
// flash electrical model, bootloader, live backend or physical qualification.
#include "../support/authenticated_pair.hpp"
#include "../support/file_flash.hpp"
#include "firmware/hub/components/storage/outbox_journal_backend.hpp"
#include "firmware/hub/components/cloud/cloud_sync.hpp"
#include "firmware/node/fota/secure_fota_adapter.hpp"
#include "host/multinode/scheduled_harness.hpp"
#include "firmware/node/fota/boot_health_gate.hpp"
#include <openssl/evp.h>
#include <functional>
#include <fstream>

namespace {
struct BoardStack:Pair{
    gs::test::TempFlash files;
    gs::test::FileBlob node_flash{files.path/"node"};
    gs::test::FileSegments hub_flash{files.path/"hub"};
    std::unique_ptr<hub::storage::DurableEventOutbox> outbox;
    std::unique_ptr<hub::storage::OutboxJournalBackend> backend;
    BoardStack(){
        repository=std::make_unique<NodeRecoveryRepository>(crypto,node_flash,key,"home","hub","room");
        require(repository->save(node->recovery_snapshot()),"initial file-backed Node recovery");
        restart_s3();
    }
    ~BoardStack(){hub.reset();}
    void restart_s3(){
        hub.reset();backend.reset();outbox.reset();
        outbox=std::make_unique<hub::storage::DurableEventOutbox>(hub_flash,crypto,key,hub::storage::OutboxLimits{});
        auto result=outbox->recover();
        require(result==hub::storage::OutboxRecovery::Empty||result==hub::storage::OutboxRecovery::Ready,"S3 file-backed encrypted outbox recovery");
        backend=std::make_unique<hub::storage::OutboxJournalBackend>(*outbox);
        hub=std::make_unique<hub::HubRuntime>(32,*backend);
        RoutineConfig config;config.window_id="day";config.end_at=2000000000;
        hub->start_window(config,HomeMode::Home);hub->authorize_node("room",session,true);
        hub->set_node_offline_timeout("room",910);
        require(hub->restore_from_journal(),"S3 recovered reducer state");
    }
    SecureFrame send_at(Milliseconds now,bool& changed){
        auto msg=node->next_message(now);require(bool(msg),"scheduled automatic retransmission opportunity");
        return deliver(*msg,now,changed);
    }
};
void motion_to_ack(){
    BoardStack b;QualifiedInput pir(EventKind::Motion,std::nullopt,150,1000);
    require(!pir.sample(false,0)&&!pir.sample(true,200),"GPIO4 initialized and edge sampled");
    auto qualified=pir.sample(true,350);require(qualified==EventKind::Motion,"first qualified PIR promptly reaches application");
    auto key=b.admit(*qualified,350);auto retained=b.repository->load();
    require(retained.state&&retained.state->retained.size()==1&&retained.state->retained[0].key.str()==key.str(),"encrypted Node admission durable before radio");
    bool changed=false;auto ack=b.send_at(350,changed);
    require(changed&&b.outbox->record_count()==1&&b.node->pending()==1,"S3 durable commit precedes Node retirement");
    require(b.ack(ack)&&b.node->pending()==0&&b.repository->load().state->retained.empty(),"authenticated application ACK durably retires exact event");
    require(b.hub->activity_state().last_activity_at==1700000000,"original occurrence timestamp reaches reducer");
}
void lossy_channel(){
    BoardStack b;auto key=b.admit(EventKind::Motion,1000);bool changed=false;auto lost=b.send_at(1000,changed);
    require(changed&&b.node->pending()==1,"lost ACK leaves event pending");
    auto spoof=lost;spoof.bytes[spoof.size-1]^=1;
    require(!b.ack(spoof)&&b.node->pending()==1,"tampered ACK cannot retire");
    require(!b.node->acknowledge(key,AckClass::ReceivedVolatile),"MAC receipt is never Durable ACK");
    b.node->transport_result(key,false,1000);auto deadline=*b.node->next_retry_deadline();
    auto duplicate=b.send_at(deadline,changed);
    require(!changed&&b.outbox->record_count()==1&&b.hub->routine_state().evidence_ids.size()==1,"same EventKey retransmission has one durable logical effect");
    require(b.ack(lost)&&!b.ack(lost)&&!b.ack(duplicate),"late authenticated ACK accepted; packet replay/second retirement rejected");
    // A protected uplink re-presented byte-for-byte must fail the production replay guard.
    NodeMessage msg;msg.node_id="room";msg.session_id=key.session_id;msg.sequence_number=key.sequence;msg.location="room";msg.event_type=EventKind::Motion;msg.sensor_type=SensorType::Pir;
    auto plain=transport::encode_node_message(msg);SecureFrame frame;transport::EncodedFrame opened;
    require(plain&&b.nf->seal(RuntimeDirection::Uplink,plain.frame,frame)&&b.hf->open(RuntimeDirection::Uplink,frame,opened)&&!b.hf->open(RuntimeDirection::Uplink,frame,opened),"uplink frame replay rejected before Hub application dispatch");
}
void restarts_without_pir(){
    BoardStack b;auto original=b.admit(EventKind::Motion,1000);bool changed=false;auto old_ack=b.send_at(1000,changed);
    b.restart_s3();b.rejoin(b.session+1); // C3 runtime remains alive.
    require(!b.ack(old_ack)&&b.node->pending()==1,"Hub reboot fresh session rejects stale ACK and retains event");
    b.node->transport_result(original,false,1000);auto next=*b.node->next_retry_deadline();
    auto retry=b.send_at(next,changed);require(!changed&&b.outbox->record_count()==1,"Hub reboot recovers durable dedupe with active C3");
    b.reboot_node(0);require(b.node->oldest_pending_key()->str()==original.str(),"C3 reboot restores original pending key");
    require(!b.ack(retry),"C3 reboot rejects previous session reply");
    auto restored=b.send_at(0,changed);require(!changed&&b.ack(restored),"automatic rejoin/retry retires backlog without new PIR");
    b.restart_s3();require(b.outbox->record_count()==1&&b.hub->routine_state().evidence_ids.size()==1,"repeated restart preserves one logical event");
}
void sleep_and_outage(){
    BoardStack b;auto key=b.admit(EventKind::Motion,1000);auto msg=b.node->next_message(1000);require(bool(msg),"outage transmission due");
    b.node->set_outage_profile(true,1000);b.node->transport_result(key,false,1000);
    AckListeningWindow window;window.application_transport_completed(1000,false);
    auto o=observation(10999);o.outage_active=true;o.next_retry_ms=*b.node->next_retry_deadline();
    observe_retained_delivery(o,window,true,true);require(!evaluate_light_sleep(o).eligible,"10-second required best-effort reception stays awake");
    o=observation(11000);o.outage_active=true;o.next_retry_ms=*b.node->next_retry_deadline();observe_retained_delivery(o,window,true,true);auto plan=evaluate_light_sleep(o);
    require(plan.eligible&&plan.requested_sleep_ms<=30000&&b.node->pending()==1,"confirmed outage safely sleeps with durable pending event and timer cap");
    o.now_ms+=plan.requested_sleep_ms;require(o.now_ms<o.next_retry_ms,"timer wakes before required retry deadline");
    for(auto inhibit:{0,1,2,3}){auto blocked=o;if(inhibit==0)blocked.fota_active=true;if(inhibit==1)blocked.persistence_clean=false;if(inhibit==2)blocked.event_in_flight=true;if(inhibit==3)blocked.pir_high=true;require(!evaluate_light_sleep(blocked).eligible,"control/persistence/TX/held-HIGH sleep inhibition");}
    auto due=*b.node->next_retry_deadline();b.rejoin(b.session+1);bool changed=false;auto ack=b.send_at(due,changed);
    require(changed&&b.ack(ack)&&b.node->pending()==0,"Hub return drains scheduled pending event without motion");
}
void health_and_wan(){
    BoardStack b;NodeHealthCadence cadence(300000,300000);
    require(!cadence.due(299999,false,false,false,false)&&cadence.due(300000,false,false,false,false),"default five-minute health boundary");
    NodeHealthSnapshot health;health.node_id="room";health.session_id=b.session;health.health_sequence=7;
    auto encoded=transport::encode_node_health(health);SecureFrame frame;transport::EncodedFrame opened;
    require(encoded&&b.nf->seal(RuntimeDirection::Uplink,encoded.frame,frame)&&b.hf->open(RuntimeDirection::Uplink,frame,opened),"health travels through authenticated production codec");
    auto decoded=transport::decode_node_health(opened.bytes.data(),opened.size);
    require(decoded&&b.hub->observe_authenticated_health(*decoded.value,"room",b.session,300000),"Hub health processing is independent of resident movement");
    require(b.hub->node_online("room",1210000)&&!b.hub->node_online("room",1210001),"300-second profile gives exact910-second silent-node expiry");
    require(!b.hub->observe_authenticated_health(*decoded.value,"room",b.session+1,300001),"wrong session does not falsely refresh liveness");
    cadence.observe_health_attempt(300000);require(cadence.next_due_ms()==600000,"health attempt schedules next opportunity without claiming verified contact");
    auto payload=transport::encode_node_health_ack(7);SecureFrame health_ack;
    require(payload&&b.hf->seal(RuntimeDirection::Downlink,payload.frame,health_ack)&&b.nf->open(RuntimeDirection::Downlink,health_ack,opened),"authenticated matching NodeHealthAck received");
    auto sequence=transport::decode_node_health_ack(opened.bytes.data(),opened.size);
    require(sequence&&SessionRecoveryPolicy::health_ack_matches(true,7,*sequence.value),"health response nonce matches outstanding request");
    cadence.observe_authenticated_contact(300040);
    require(cadence.next_due_ms()==600040,"verified contact resets next standalone health deadline");
    for(auto profile:std::vector<std::pair<std::string,unsigned>>{{"legacy60",190},{"legacy120",310}}){b.hub->authorize_node(profile.first,1,true);b.hub->set_node_offline_timeout(profile.first,profile.second);require(b.hub->observe_authenticated_contact(profile.first,1,1000)&&b.hub->node_online(profile.first,1000+profile.second*1000ULL)&&!b.hub->node_online(profile.first,1001+profile.second*1000ULL),"legacy profiles retain exact per-device expiry");}
    b.hub->authorize_node("unknown",1,true);b.hub->set_node_offline_timeout("unknown",std::nullopt);
    require(b.hub->observe_authenticated_contact("unknown",1,1000)&&!b.hub->node_online("unknown",1000),"unknown identity profile never falsely online");
    hub::CloudSync cloud(b.hub->journal());cloud.set_connected(false,300000);
    b.admit(EventKind::CallFamily,300050);bool changed=false;
    auto event=*b.node->next_message(300050);EnergyCounters energy;event.power=energy.telemetry();
    auto ack=b.deliver(event,300050,changed);
    require(b.node->pending()==1&&cadence.next_due_ms()==600040,"piggyback MAC-only success does not renew contact");
    require(changed&&b.ack(ack)&&cloud.next_batch(300050).empty()&&b.hub->node_online("room",300050),"WAN-only outage keeps local durable ACK and authenticated Node liveness alive");
    cadence.observe_authenticated_contact(300050);
    require(cadence.next_due_ms()==600050&&!cadence.due(600040,false,false,false,false),"authenticated event piggyback replaces standalone health opportunity");
    cloud.set_connected(true,300060);auto batch=cloud.next_batch(300060);
    require(batch.size()==1&&batch[0].kind==EventKind::CallFamily,"implemented cloud interface backfills important retained event");
    hub::BackendCommitReply receipt{hub::BackendReplyStatus::Committed,batch[0].key,false,false};
    require(cloud.handle_backend_reply(batch[0].key,receipt,300060)!=hub::BackendReceiptResult::Completed,"unauthenticated local receipt stub cannot complete cloud event");
    receipt.authenticated_backend=true;
    require(cloud.handle_backend_reply(batch[0].key,receipt,400000)==hub::BackendReceiptResult::Completed,"exact authenticated contract fixture durably completes backend interface only");
    b.restart_s3();require(b.hub->journal().cloud_completed(batch[0].key),"completion survives S3 simulated restart");
}
void faults_and_priority(){
    { // Without any valid committed authority root, recovery must fail closed.
        gs::test::TempFlash files;gs::test::FileSegments flash(files.path/"first-root");
        OpenSslCommissioningCrypto crypto;Key32 key{};key.fill(7);
        hub::storage::DurableEventOutbox outbox(flash,crypto,key,hub::storage::OutboxLimits{});
        require(outbox.recover()==hub::storage::OutboxRecovery::Empty,"new empty S3 storage");
        // A body without authenticated publication authority cannot be adopted.
        const std::uint8_t orphan[]={1,2,3};require(flash.append(1,orphan,sizeof(orphan)),"interrupted first publication body fixture");
        require(outbox.recover()==hub::storage::OutboxRecovery::IntegrityFailure,"missing first authority root remains fail closed");
    }
    BoardStack b;b.admit(EventKind::Motion,500);bool seed_changed=false;require(b.ack(b.send_at(500,seed_changed)),"valid committed prefix before interrupted append");
    auto key=b.admit(EventKind::Motion,1000);b.hub_flash.fail_publication=true;
    auto msg=*b.node->next_message(1000);auto plain=transport::encode_node_message(msg);SecureFrame wire;transport::EncodedFrame opened;
    require(plain&&b.nf->seal(RuntimeDirection::Uplink,plain.frame,wire)&&b.hf->open(RuntimeDirection::Uplink,wire,opened),"faulted transmission authenticates");
    auto decoded=transport::decode_node_message(opened.bytes.data(),opened.size);
    require(decoded&&b.hub->authenticated_radio_message_callback(*decoded.value,"room","device",b.session,1700000001,1000),"faulted Hub ingress");
    auto result=b.hub->run_state_once();require(result&&result->ack!=AckClass::Durable&&b.node->pending()==1,"failed storage publication cannot emit Durable ACK or erase Node pending");
    b.restart_s3();b.node->transport_result(key,false,1000);bool changed=false;auto ack=b.send_at(*b.node->next_retry_deadline(),changed);
    require(b.ack(ack)&&b.outbox->record_count()==2,"interrupted publication recovers safe same-key progress");
    b.node_flash.fail_write=true;auto pending=b.node->record(EventKind::DoorOpen,"room",2000,1700000002);
    require(pending&&!b.repository->save(b.node->recovery_snapshot()),"Node persistence failure cannot authorize exposure/sleep");
    b.node_flash.fail_write=false;require(b.repository->save(b.node->recovery_snapshot()),"safe retry persists unfinished admission");
    NodeRuntime pressure("room",50);for(unsigned i=0;i<28;++i)require(bool(pressure.record(EventKind::Motion,"room",i,i)),"ordinary32 queue preserves four priority slots");
    require(!pressure.record(EventKind::Motion,"room",29,29),"ordinary reserve overflow rejected");
    pressure.set_outage_profile(true,99);
    for(auto kind:{EventKind::DoorOpen,EventKind::DoorClosed,EventKind::OkPressed,EventKind::CallFamily}){auto urgent=pressure.record(kind,"room",100,100);require(urgent&&pressure.next_message(100)->sequence_number==urgent->sequence,"critical/resident/door event has immediate priority despite backlog");pressure.transport_result(*urgent,false,100);}
    require(pressure.pending()==32&&!pressure.record(EventKind::CallFamily,"room",101,101),"bounded protocol limit never masquerades as unlimited retention");
    auto bytes=gs::test::read_file(b.node_flash.path);bytes.back()^=1;require(gs::test::write_file(b.node_flash.path,bytes)&&b.repository->load().status==NodeRecoveryLoadStatus::Corrupt,"corrupted encrypted Node recovery fails closed");
}
void multiple_nodes(){
    // Two independent production AEAD/session owners share the actual S3 backend.
    BoardStack s3;Pair second;second.binding.device_id="device2";second.binding.logical_id="room2";
    second.node=std::make_unique<NodeRuntime>("room2",second.session);
    gs::test::FileBlob blob(s3.files.path/"node2");
    second.repository=std::make_unique<NodeRecoveryRepository>(second.crypto,blob,second.key,"home","hub","room2");
    second.nf=std::make_unique<RuntimeFrameSecurity>(second.crypto,second.binding);
    second.hf=std::make_unique<RuntimeFrameSecurity>(second.crypto,second.binding);second.rejoin(second.session+1);
    s3.hub->authorize_node("room2",second.session,true);
    s3.admit(EventKind::Motion,1000);bool changed=false;require(s3.ack(s3.send_at(1000,changed)),"first S3 Node durable exchange");
    auto key=second.admit(EventKind::CallFamily,1000);auto msg=*second.node->next_message(1000);
    auto encoded=transport::encode_node_message(msg);SecureFrame frame;transport::EncodedFrame opened;
    require(encoded&&second.nf->seal(RuntimeDirection::Uplink,encoded.frame,frame)&&second.hf->open(RuntimeDirection::Uplink,frame,opened),"second S3 Node authenticated transport");
    auto decoded=transport::decode_node_message(opened.bytes.data(),opened.size);
    require(decoded&&s3.hub->authenticated_radio_message_callback(*decoded.value,"room2","device2",second.session,1700000001,1000),"second owner isolated S3 admission");
    auto result=s3.hub->run_state_once();require(result&&result->ack==AckClass::Durable&&s3.outbox->record_count()==2,"two Node S3 durable identity isolation");
    NodeAckMessage reply;reply.node_id="room2";reply.session_id=key.session_id;reply.sequence_number=key.sequence;reply.ack_type=result->ack;
    auto payload=transport::encode_node_ack(reply);SecureFrame ack;
    require(payload&&second.hf->seal(RuntimeDirection::Downlink,payload.frame,ack)&&!s3.ack(ack)&&second.ack(ack),"wrong S3 Node rejects ACK; exact owner durably retires");
    s3.restart_s3();require(s3.outbox->record_count()==2,"multiple S3 Node durable identities survive restart");
    // Existing scheduled host adapter exercises production commissioning/AEAD/NodeRuntime/HubRuntime.
    gs::host::multinode::ScheduledHarness nodes(4);
    for(unsigned i=0;i<4;++i)require(bool(nodes.record(i,EventKind::Motion)),"multiple independent Node admissions");
    nodes.redirect_next_ack(0,1);nodes.drop_next_ack(2);nodes.run_until_quiet(10000);
    for(unsigned i=0;i<4;++i)require(nodes.snapshot(i).pending==0&&nodes.snapshot(i).retained==0,"lost/wrong-node ACK recovery isolated per Node");
    require(nodes.journal_size()==4,"multi-node wrong-ACK retries have exactly four effects");
    nodes.set_hub_online(false);require(bool(nodes.record(0,EventKind::CallFamily)),"important event retained during RF outage");nodes.advance(3000);
    require(nodes.snapshot(0).pending==1,"RF outage never fakes retirement");nodes.set_hub_online(true);nodes.run_until_quiet(10000);
    require(nodes.snapshot(0).pending==0&&nodes.journal_size()==5,"RF return without motion resumes backlog");
}
struct OtaWriter:node::fota_receiver::IOtaWriter{
    bool aborted=false;std::size_t capacity()override{return 4096;}bool begin(std::size_t)override{return true;}bool write(const std::uint8_t*,std::size_t)override{return true;}bool finalize()override{return true;}bool commit_boot()override{return true;}void abort()override{aborted=true;}
};
struct OtaCallbacks:node::fota_receiver::IReceiverCallbacks{
    bool maintenance=false;unsigned timeouts=0;
    void send_ack(const gs::fota::Ack&)override{}void set_maintenance(bool x)override{maintenance=x;}void report_timeout()override{++timeouts;}void request_restart()override{}
};
struct OtaDigest:node::fota_receiver::IImageDigest{
    EVP_MD_CTX* context=EVP_MD_CTX_new();~OtaDigest()override{EVP_MD_CTX_free(context);}
    bool start()override{return context&&EVP_DigestInit_ex(context,EVP_sha256(),nullptr)==1;}bool add(const std::uint8_t* p,std::size_t n)override{return EVP_DigestUpdate(context,p,n)==1;}bool finish(std::array<std::uint8_t,32>& out)override{unsigned n=0;return EVP_DigestFinal_ex(context,out.data(),&n)==1&&n==out.size();}void abort()override{EVP_MD_CTX_reset(context);}
};
void fota_interruption(){
    BoardStack b;auto pending=b.admit(EventKind::CallFamily,1000);
    OtaWriter writer;OtaCallbacks callbacks;OtaDigest digest;node::fota_receiver::Receiver receiver(writer,callbacks);node::fota_receiver::SecureFotaAdapter adapter(receiver,digest,"esp32c3");
    gs::fota::secure_wire::Message begin;begin.type=gs::fota::secure_wire::Type::Begin;begin.transfer_id=7;begin.image_size=192;begin.board_size=7;std::copy_n("esp32c3",7,begin.board.begin());begin.version_size=3;std::copy_n("2.0",3,begin.version.begin());
    auto payload=gs::fota::secure_wire::encode(begin);SecureFrame frame;transport::EncodedFrame opened;
    require(payload&&b.hf->seal(RuntimeDirection::Downlink,payload.frame,frame)&&b.nf->open(RuntimeDirection::Downlink,frame,opened),"FOTA control delivered over real authenticated transport");
    auto decoded=gs::fota::secure_wire::decode(opened.bytes.data(),opened.size);
    require(decoded&&adapter.process(decoded.message,b.session,1000)&&callbacks.maintenance,"authenticated FOTA Begin enters production maintenance");
    auto o=observation(12000);o.fota_active=callbacks.maintenance;require(!evaluate_light_sleep(o).eligible,"FOTA maintenance prevents light sleep");
    adapter.poll(31000);require(!adapter.active()&&writer.aborted&&callbacks.timeouts==1&&!callbacks.maintenance,"interrupted OTA times out and aborts writer safely");
    require(b.node->has_pending_key(pending)&&b.repository->load().state->pending.size()==1,"FOTA interruption preserves durable critical backlog");
    bool changed=false;auto ack=b.send_at(31000,changed);require(changed&&b.ack(ack),"event delivery resumes after maintenance interruption");
    node::fota::BootHealthObservation health;require(node::fota::evaluate_boot_health(health,90000)==node::fota::BootHealthDecision::Rollback,"unhealthy boot selects rollback policy; no physical bootloader claim");
}
void export_product_motion_event(const std::string& path,const std::string& cloud_path){
    BoardStack b;
    const auto key=b.admit(EventKind::Motion,1000);
    const auto first=b.node->next_message(1000);
    require(first&&first->event_type==EventKind::Motion&&first->location=="room",
            "production Node runtime creates the P0 PIR event");
    bool changed=false;
    b.deliver(*first,1000,changed);
    require(changed&&b.outbox->record_count()==1&&b.node->pending()==1,
            "production S3 durably commits before lost application ACK");
    // The radio callback succeeds, but the authenticated application Durable
    // ACK is deliberately dropped at the Node. The retry must remain same-key.
    b.node->transport_result(key,true,1000);
    require(b.node->radio_stats().mac_success==1&&b.node->pending()==1,
            "MAC success without application ACK does not retire the durable event");
    const auto retry_deadline=b.node->next_retry_deadline();
    require(retry_deadline.has_value(),"retained event has existing retry deadline");
    const auto retry=b.node->next_message(*retry_deadline);
    require(retry&&retry->sequence_number==key.sequence&&retry->session_id==key.session_id,
            "retry preserves the immutable Node EventKey");
    const auto durable_ack=b.deliver(*retry,*retry_deadline,changed);
    require(!changed&&b.outbox->record_count()==1,
            "Hub deduplicates same EventKey after ACK loss");
    require(b.ack(durable_ack)&&b.node->pending()==0,
            "only authenticated Durable ACK retires the persisted Node event");
    const auto occurred_at=b.hub->activity_state().last_activity_at;
    require(occurred_at.has_value()&&*occurred_at==1700000001,
            "Hub reducer preserves the original occurrence timestamp through retry");
    std::ofstream out(path,std::ios::binary|std::ios::trunc);
    require(bool(out),"open isolated P0 event export");
    out << "{\"event_id\":\"" << key.str()
        << "\",\"event_key\":\"" << key.str()
        << "\",\"kind\":\"MOTION\",\"location\":\"" << first->location
        << "\",\"occurred_at\":" << *occurred_at << ",\"hub_received_at\":" << *occurred_at
        << ",\"uncertainty_s\":0,\"payload\":{\"source\":\"production_c3_pir_runtime\"} }\n";
    out.close();require(bool(out),"flush isolated P0 event export");
    hub::CloudSync cloud(b.hub->journal());
    cloud.set_connected(true,*retry_deadline);
    const auto batch=cloud.next_batch(*retry_deadline);
    require(batch.size()==1,"production S3 CloudSync selects the committed motion event");
    const auto request=cloud.request_for("home",batch.front());
    require(request.has_value()&&!request->json_body().empty(),
            "production S3 CloudSync serializes its backend commit request");
    std::ofstream cloud_out(cloud_path,std::ios::binary|std::ios::trunc);
    require(bool(cloud_out),"open isolated CloudSync request export");
    cloud_out<<request->json_body()<<'\n';cloud_out.close();
    require(bool(cloud_out),"flush isolated CloudSync request export");
    std::cout << "P0-STACK-EVENT PASS retries=1 durable_effects=1 key=" << key.str()
              << " physical=NOT_RUN\n";
}
}
int main(int argc,char** argv){
    if(argc==4&&std::string(argv[1])=="--emit-p0-event"){
        try{export_product_motion_event(argv[2],argv[3]);return 0;}
        catch(const std::exception& error){std::cerr<<"P0-STACK-EVENT FAIL "<<error.what()<<'\n';return 1;}
    }
    const std::vector<std::pair<std::string,std::function<void()>>> cases={
        {"BOARD-TC-130-001",motion_to_ack},{"BOARD-TC-130-002",lossy_channel},
        {"BOARD-TC-130-003",restarts_without_pir},{"BOARD-TC-130-004",sleep_and_outage},
        {"BOARD-TC-130-005",health_and_wan},{"BOARD-TC-130-006",faults_and_priority},
        {"BOARD-TC-130-007",multiple_nodes},{"BOARD-TC-130-008",fota_interruption}};
    std::string select=argc>1?argv[1]:"";unsigned selected=0,failed=0;
    for(const auto& item:cases){if(!select.empty()&&select!=item.first)continue;++selected;
        try{item.second();const char* injection=std::getenv("GS_BOARD_E2E_INJECT_FAILURE");if(injection&&item.first==injection)require(false,"controlled board-stack negative self-test");std::cout<<item.first<<" PASS\n";}
        catch(const std::exception& error){++failed;std::cerr<<item.first<<" FAIL "<<error.what()<<'\n';}}
    if(!selected){std::cerr<<"zero selected board cases\n";return 2;}
    std::cout<<"BOARD STACK E2E "<<(failed?"FAIL":"PASS")<<" cases="<<selected<<" checks="<<checks<<" failed="<<failed<<" physical=NOT_RUN\n";
    return failed?1:0;
}
