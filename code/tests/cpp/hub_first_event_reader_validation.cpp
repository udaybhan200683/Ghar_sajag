// Same saved v1 bytes, actual historical and corrected production readers.
// GS148_OLD_READER selects only startup wiring appropriate to the old interface;
// old production translation units/codecs come from the pinned Git baseline.
#define GS_CHECKPOINT_EMBEDDED
#include "hub_runtime_checkpoint_validation.cpp"
#include "hub_first_event_recovery_cases.inc"
#include "firmware/node/storage/node_recovery_persistence.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
namespace {
void blob_out(std::ofstream& file,const Bytes& bytes) {
    const std::uint32_t size=bytes.size();file.write(reinterpret_cast<const char*>(&size),sizeof(size));
    file.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
}
Bytes blob_in(std::ifstream& file) {
    std::uint32_t size=0;file.read(reinterpret_cast<char*>(&size),sizeof(size));
    require(file.good() && size<=4U*1024U*1024U,"bounded host snapshot read");
    Bytes bytes(size);file.read(reinterpret_cast<char*>(bytes.data()),bytes.size());
    require(file.good(),"complete host snapshot read");return bytes;
}
[[maybe_unused]] void snapshot(FirstFixture& f,const std::string& path,bool absent_head) {
    std::ofstream file(path,std::ios::binary);require(file.good(),"host snapshot output");
    blob_out(file,Bytes(f.binding.hub_public_key.begin(),f.binding.hub_public_key.end()));
    blob_out(file,Bytes(f.binding.device_public_key.begin(),f.binding.device_public_key.end()));
    blob_out(file,f.registry_blob.bytes);
    for (const auto* prefix:{"cp","sel","ret"}) for (unsigned n=0;n<(std::string(prefix)=="ret"?3U:2U);++n) {
        Bytes bytes;bool found=false;require(f.inventory.blobs.read(std::string(prefix)+std::to_string(n),bytes,found),"NVS snapshot");
        file.put(found?1:0);blob_out(file,bytes);
    }
    const std::uint32_t count=f.files.state.files.size();file.write(reinterpret_cast<const char*>(&count),sizeof(count));
    for (const auto& state:f.files.state.files) {
        blob_out(file,Bytes(state.first.begin(),state.first.end()));blob_out(file,state.second);
    }
    for (std::uint16_t n=0;n<32;++n) {
        bool found=false;std::uint32_t size=0;require(f.files.segment_size(n,found,size),"segment snapshot size");
        Bytes bytes(size);std::size_t actual=0;
        require(f.files.read(n,0,bytes.data(),bytes.size(),actual) && actual==size,"segment snapshot bytes");
        file.put(found?1:0);blob_out(file,bytes);
    }
    for (unsigned n=0;n<4;++n) {
        Bytes bytes;bool found=false;
        if (n==0) {require(f.files.read_publication(bytes,found),"head snapshot");if(absent_head){found=false;bytes.clear();}}
        if (n==1) require(f.files.read_lifecycle_root(bytes,found),"lifecycle snapshot");
        if (n==2) {std::uint32_t size=0;require(f.files.completion_size(found,size),"completion size");bytes.resize(size);std::size_t actual=0;
            require(f.files.read_completion(0,bytes.data(),bytes.size(),actual) && actual==size,"completion snapshot");}
        if (n==3) require(f.files.read_completion_publication(bytes,found),"completion head snapshot");
        file.put(found?1:0);blob_out(file,bytes);
    }
    require(file.good(),"complete snapshot serialization");
}
void load_snapshot(FirstFixture& f,const std::string& path) {
    std::ifstream file(path,std::ios::binary);require(file.good(),"host snapshot input");
    const auto hub=blob_in(file),node=blob_in(file);
    require(hub.size()==65 && node.size()==65,"snapshot public identities");
    std::copy(hub.begin(),hub.end(),f.binding.hub_public_key.begin());
    std::copy(node.begin(),node.end(),f.binding.device_public_key.begin());
    f.registry_blob.bytes=blob_in(file);
    f.registry_repository=std::make_unique<gs::hub::HubRegistryRepository>(f.crypto,f.registry_blob,f.key,
        "home","hub",f.binding.hub_public_key,10,16);
    for (const auto* prefix:{"cp","sel","ret"}) for(unsigned n=0;n<(std::string(prefix)=="ret"?3U:2U);++n) {
        const bool found=file.get()==1;const auto bytes=blob_in(file);const auto name=std::string(prefix)+std::to_string(n);
        if(found) require(f.inventory.blobs.replace(name,bytes),"restore NVS v1 bytes");
        else {Bytes old;bool exists=false;require(f.inventory.blobs.read(name,old,exists),"existing fixture NVS");
            if(exists) require(f.inventory.blobs.erase_if_equals(name,old),"remove constructor-only fixture record");}
    }
    f.files.state.files.clear();std::uint32_t count=0;file.read(reinterpret_cast<char*>(&count),sizeof(count));
    require(count<64,"bounded state fixture inventory");
    for(unsigned n=0;n<count;++n) {const auto name=blob_in(file),bytes=blob_in(file);f.files.state.files[std::string(name.begin(),name.end())]=bytes;}
    for(std::uint16_t n=0;n<32;++n) {const bool found=file.get()==1;const auto bytes=blob_in(file);
        if(found) require(f.files.segments.append(n,bytes.data(),bytes.size()),"restore encrypted body bytes");}
    for(unsigned n=0;n<4;++n) {const bool found=file.get()==1;const auto bytes=blob_in(file);if(!found)continue;
        if(n==0) require(f.files.segments.publish_publication(bytes),"restore selected head");
        if(n==1) require(f.files.segments.publish_lifecycle_root(bytes),"restore lifecycle");
        if(n==2) require(f.files.segments.append_completion(bytes.data(),bytes.size()),"restore completion");
        if(n==3) require(f.files.segments.publish_completion_publication(bytes),"restore completion head");}
    require(file.peek()==std::char_traits<char>::eof(),"no unparsed host snapshot tail");
}
#ifndef GS148_OLD_READER
void export_projection(const std::string& node_path,const std::string& cloud_path) {
    FirstFixture f;require(f.boot(),"Node/Hub first-event fixture");
    gs::node::NodeRuntime node("room1",42);
    FirstRegistryBlob retained;
    gs::node::NodeRecoveryRepository repository(f.crypto,retained,f.key,"home","hub","room1");
    const auto key=node.record(gs::EventKind::Motion,"bedroom",1000,1800000001,0,2970,false,gs::SensorType::Pir,-47);
    require(key.has_value() && repository.save(node.recovery_snapshot()),"C3 retained durable event before radio exposure");
    const auto message=node.next_message(1000);require(message.has_value(),"C3 actual first wire payload");
    f.files.target="publication";f.files.phase="before-write";
    const auto refused=f.send(*message);
    require(refused && refused->ack==gs::AckClass::Rejected && node.pending()==1,"no first-event Durable ACK");
    require(f.boot() && f.boot(),"two S3 boots preserve original C3 event");
    gs::hub::CloudSync pending_cloud(f.runtime->journal(),*f.runtime);
    pending_cloud.set_connected(true,1);require(pending_cloud.next_batch(1).empty(),"no pending cloud delivery");
    const auto saved=repository.load();require(saved.state.has_value(),"encrypted C3 recovery snapshot");
    gs::node::NodeRuntime rebooted("room1",43);
    require(rebooted.restore_recovery(*saved.state,2000),"C3 reboot keeps original EventKey/payload");
    const auto retry=rebooted.next_message(2000);
    require(retry && retry->session_id==message->session_id && retry->sequence_number==message->sequence_number &&
        retry->occurred_at==message->occurred_at,"exact retained wire identity after C3 reboot");
    const auto durable=f.send(*retry,999);
    require(durable && durable->ack==gs::AckClass::Durable && durable->state_changed && rebooted.pending()==1,
        "corrected S3 publication/checkpoint precede deliberately lost first ACK");
    require(f.boot(),"S3 reboot after lost ACK");
    const auto duplicate=f.send(*retry);
    require(duplicate && duplicate->ack==gs::AckClass::Durable && !duplicate->state_changed,
        "actual Node retry after lost ACK has no duplicate reducer effect");
    const auto retire=[&](const gs::NodeMessage& value) {
        gs::NodeAckMessage ack;ack.node_id=value.node_id;ack.session_id=value.session_id;
        ack.sequence_number=value.sequence_number;ack.ack_type=gs::AckClass::Durable;
        const auto encoded=gs::transport::encode_node_ack(ack);
        gs::security::SecureFrame secured;gs::transport::EncodedFrame opened;
        require(encoded && f.rx->seal(gs::security::RuntimeDirection::Downlink,encoded.frame,secured) &&
            f.tx->open(gs::security::RuntimeDirection::Downlink,secured,opened),"authenticated Durable ACK downlink");
        const auto decoded=gs::transport::decode_node_ack(opened.bytes.data(),opened.size);
        require(decoded && rebooted.acknowledge({decoded.value->node_id,decoded.value->session_id,
            decoded.value->sequence_number},decoded.value->ack_type) &&
            repository.save(rebooted.recovery_snapshot()),"C3 retirement only after authenticated application ACK");
    };
    retire(*retry);require(rebooted.pending()==0,"retired C3 original pending set empty");
    const auto next=rebooted.record(gs::EventKind::Motion,"bedroom",3000,1800000002,0,2970,false,gs::SensorType::Pir,-47);
    require(next.has_value() && repository.save(rebooted.recovery_snapshot()),"fresh second C3 event durably retained");
    const auto second=rebooted.next_message(3000);require(second.has_value(),"second C3 message");
    const auto admitted=f.send(*second);require(admitted && admitted->ack==gs::AckClass::Durable,"second ordinary S3 event");
    retire(*second);
    gs::hub::CloudSync cloud(f.runtime->journal(),*f.runtime);cloud.set_connected(true,3000);
    const auto batch=cloud.next_batch(3000);require(batch.size()==2,"only two committed original caregiver events");
    std::ofstream requests(cloud_path);
    requests<<'[';
    for(std::size_t i=0;i<batch.size();++i) {
        const auto request=cloud.request_for("home",batch[i]);require(request.has_value(),"production CloudSync owner serializer");
        if(i) requests<<',';
        requests<<request->json_body();
    }
    requests<<"]\n";require(requests.good(),"CloudSync exports complete committed requests");
    std::ofstream evidence(node_path);
    evidence<<"{\"original_event_key\":\""<<key->str()<<"\",\"original_occurred_at\":1800000001,"
        <<"\"pending_before_retry\":true,\"retired_after_authenticated_ack\":true,\"committed_events\":2}\n";
    require(evidence.good(),"Node/Hub recovery projection evidence");
    std::cout<<"GS148-ARCH-007/009/051 PASS production_c3_s3_recovery=1 lost_ack=1 committed_events=2\n";
}
void write_state(const std::string& name,const std::string& path) {
    FirstFixture f;bool absent=false;
    if (name=="empty-interrupted") {
        DurableEventOutbox outbox(f.files,f.crypto,f.key);require(outbox.recover()==OutboxRecovery::Empty,"empty outbox");
        RuntimeStateStore state(f.files,f.crypto,f.key);OutboxJournalBackend backend(outbox);
        gs::hub::HubRuntime runtime(32,backend);runtime.bind_runtime_state(state);runtime.bind_durability_owner(*f.owner);
        f.files.target="application.head";f.files.phase="before-write";
        require(!runtime.restore_from_journal(),"interrupted initial checkpoint");f.files.reset();
    } else {
        require(f.boot(),"writer native boot");
        if(name=="prepared" || name=="pending" || name=="pending-two-boots" || name=="published") {
            f.files.target=name=="prepared"?"body":name=="published"?"application.head":"publication";
            f.files.phase="before-write";
            const auto result=f.send(make_message(1));require(result && result->ack==gs::AckClass::Rejected,"writer interrupted event");
            f.files.reset();
            if(name=="pending-two-boots") require(f.boot() && f.boot(),"fixed pending reader repeated boot");
        } else if(name!="empty") {
            require(f.send(make_message(1))->ack==gs::AckClass::Durable,"writer committed first event");
            if(name=="populated-missing-head") {require(f.send(make_message(2))->ack==gs::AckClass::Durable,"second populated event");absent=true;}
            if(name=="acked-missing-head") absent=true;
        }
        if(name=="malformed-head") require(f.files.segments.publish_publication(Bytes{0}),"malformed authority");
        if(name=="pending-missing-checkpoint") {
            // Transform the retained selected state into the exact unauthorised
            // combination; this is test fault injection, never production repair.
            absent=true;f.files.state.files.erase("application.head");
        }
    }
    snapshot(f,path,absent);
}
#endif
}
int main(int argc,char** argv) {
    try {
        require(argc==4,"reader arguments: write/probe state snapshot");
#ifndef GS148_OLD_READER
        if(std::string(argv[1])=="projection") {export_projection(argv[2],argv[3]);return 0;}
        if(std::string(argv[1])=="write") {write_state(argv[2],argv[3]);return 0;}
#endif
        require(std::string(argv[1])=="probe","reader mode");FirstFixture f;load_snapshot(f,argv[3]);
        const bool first=f.boot(false);const bool second=f.boot(false);
        require(first==second,"reader reboot classification idempotent");
        std::cout<<"GS148 READER "<<argv[2]<<" "<<(second?"READY":"FAIL_CLOSED")
            <<" public="<<(second?f.outbox->record_count():0)<<" identities="<<(second?f.state->identities():0)<<" boots=2\n";
        return second?0:2;
    } catch(const std::exception& error) {std::cerr<<"reader fixture FAIL: "<<error.what()<<'\n';return 1;}
}
