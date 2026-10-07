#include "host/storage/density_fixture.hpp"
#include "storage/journal.hpp"
#include "storage/durable_transition.hpp"
#include "storage/node_retirement_snapshot.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <chrono>
#include <cstdio>
#include <cstdlib>

using namespace gs::host::storage;
using namespace gs::host::storage::density;
static volatile std::uint64_t sink=0;
static void require(bool v){if(!v)std::abort();}
static gs::DomainEvent domain(const Event& e) {
    gs::DomainEvent d;auto physical=std::string(32,'p');physical.back()=static_cast<char>('a'+e.key.node);
    d.key=gs::EventKey("node-"+std::to_string(e.key.node+1),e.key.session,e.key.sequence,physical);
    d.location="kitchen";d.kind=static_cast<gs::EventKind>(e.kind);d.sensor_type=static_cast<gs::SensorType>(e.sensor);
    d.monotonic_ms=e.monotonic;d.occurred_at=e.occurred;d.received_at=e.received;d.uncertainty_s=e.uncertainty;
    d.battery_mv=e.battery;d.rssi_dbm=e.rssi;d.is_test=e.test;
    if(e.kind==9)d.motion_aggregate=gs::DomainEvent::MotionAggregate{e.additional,e.first,e.last};
    return d;
}
using Clock=std::chrono::steady_clock;
template<class Op>static double timing(Op op,std::size_t iterations=30000){
    std::array<double,9> samples{};
    for(unsigned round=0;round<10;++round){const auto start=Clock::now();
        for(std::size_t i=0;i<iterations;++i)sink+=op(i);
        const auto elapsed=std::chrono::duration<double,std::nano>(Clock::now()-start).count()/iterations;
        if(round)samples[round-1]=elapsed;}
    std::sort(samples.begin(),samples.end());return samples[4];
}
struct Stats {
    std::array<std::size_t,512> histogram{};
    std::size_t count=0,total=0,min=512,max=0;
    void add(std::size_t size){require(size<histogram.size());++histogram[size];++count;total+=size;min=std::min(min,size);max=std::max(max,size);}
    std::size_t quantile(unsigned percent) const {auto wanted=(count*percent+99)/100;std::size_t cumulative=0;
        for(std::size_t i=0;i<histogram.size();++i){cumulative+=histogram[i];if(cumulative>=wanted)return i;}return 0;}
};
static const char* name(Mode m){return m==Mode::Fixed?"FIXED":m==Mode::Varint?"VARINT":m==Mode::Delta?"DELTA":m==Mode::Context?"CONTEXT":m==Mode::Presence?"PRESENCE_DICTIONARY":"CONTEXT_RELATIONS";}
static void distribution(std::uint32_t rate,Mode m,FILE* cold,std::size_t identity_extra=0,bool jitter=false) {
    Stats raw,hot,warm;Context c=context_for(0,rate,1,jitter);std::size_t hot_sectors=1,warm_sectors=1;
    const auto header=(m<=Mode::Varint?64:authenticated_context_bytes)+identity_extra;
    std::size_t hot_used=header,warm_used=hot_used;
    std::size_t hcount=0,wcount=0;
    // Warm context refresh is independent of hot packing; measure separately.
    Context warm_context=c;
    for(std::size_t i=0;i<rate;++i){const auto e=trace(i,rate,jitter);Buffer b{};std::size_t n=0;
        require(encode(m,c,e,b,n));Event decoded;require(decode(m,c,b.data(),n,decoded)&&equal(e,decoded));
        const auto h=m==Mode::Fixed?n+20:hot_bytes(n);
        if(hot_used+h>4096||hcount==max_records){++hot_sectors;c=context_for(i,rate,hot_sectors,jitter);
            hot_used=header;hcount=0;require(encode(m,c,e,b,n));}
        raw.add(n);hot.add(m==Mode::Fixed?n+20:hot_bytes(n));
        hot_used+=m==Mode::Fixed?n+20:hot_bytes(n);++hcount;
        Buffer wb{};std::size_t wn=0;require(encode(m,warm_context,e,wb,wn));
        if(warm_used+warm_bytes(wn)>4096||wcount==max_records){++warm_sectors;warm_context=context_for(i,rate,warm_sectors,jitter);
            warm_used=header;wcount=0;require(encode(m,warm_context,e,wb,wn));}
        warm.add(warm_bytes(wn));warm_used+=warm_bytes(wn);++wcount;
        if(cold){std::uint8_t length[2]{};put_be(length,wn,2);require(std::fwrite(length,1,2,cold)==2);require(std::fwrite(wb.data(),1,wn,cold)==wn);}
    }
    std::printf("DISTRIBUTION rate=%u model=%s raw_min=%zu raw_p50=%zu raw_p95=%zu raw_max=%zu raw_avg=%.4f hot_min=%zu hot_p50=%zu hot_p95=%zu hot_max=%zu hot_avg=%.4f hot_total_B=%zu hot_sectors=%zu warm_sectors=%zu hot_alloc_B=%zu warm_alloc_B=%zu\n",
        rate,name(m),raw.min,raw.quantile(50),raw.quantile(95),raw.max,double(raw.total)/raw.count,
        hot.min,hot.quantile(50),hot.quantile(95),hot.max,double(hot.total)/hot.count,hot.total,hot_sectors,warm_sectors,hot_sectors*4096,warm_sectors*4096);
    std::printf("WARM rate=%u model=%s min=%zu p50=%zu p95=%zu max=%zu average=%.4f payload_B=%zu headers_B=%zu last_used_B=%zu\n",rate,name(m),warm.min,warm.quantile(50),warm.quantile(95),warm.max,double(warm.total)/warm.count,warm.total,warm_sectors*header,warm_used);
    if(identity_extra||jitter)std::printf("SIZING_VARIANT identity_extra_B=%zu jitter=%u header_B=%zu rate=%u source_only_one_day_no_daily\n",identity_extra,jitter?1U:0U,header,rate);
}
static void capacity(std::uint32_t rate,Mode mode,std::size_t identity_extra=0,bool jitter=false) {
    const auto header=(mode==Mode::Fixed?64:authenticated_context_bytes)+identity_extra;
    require(header+302<sector_bytes);
    Context c=context_for(0,rate,1,jitter);std::size_t pages=1,used=header,records=0;
    std::size_t fit_records=0,three_pages=0,three_used=0;
    for(std::uint64_t i=0;i<6ULL*rate;++i){Buffer b{};std::size_t n=0;
        require(encode(mode,c,trace(i,rate,jitter),b,n));
        if(used+warm_bytes(n)>4096||records==max_records){++pages;c=context_for(i,rate,pages,jitter);used=header;records=0;
            require(encode(mode,c,trace(i,rate,jitter),b,n));}
        used+=warm_bytes(n);++records;
        if((i+1)%rate==0) { // daily300-byte plaintext + framing, no duplicated per-day tag
            if(used+302>4096||records==max_records){++pages;c=context_for(i+1,rate,pages,jitter);used=header;records=0;}
            used+=302;++records;
        }
        if(pages<=7)fit_records=static_cast<std::size_t>(i+1);
        if(i+1==3ULL*rate){three_pages=pages;three_used=used;}
    }
    std::printf("CAPACITY model=%s rate=%u identity_extra_B=%zu jitter=%u normal_pool_sectors=7 source_records_fit=%zu hours=%.6f days=%.6f three_day_source=%u daily_records=3 three_day_sectors=%zu total_with_fixed100KiB=%zu last_used=%zu\n",name(mode),rate,identity_extra,jitter?1U:0U,fit_records,fit_records*24.0/rate,double(fit_records)/rate,3*rate,three_pages,102400+three_pages*4096,three_used);
}
static void codecs() {
    auto c=context_for(0,384);std::array<Event,192> events{};
    std::array<Buffer,192> encoded{};std::array<std::size_t,192> lengths{};
    for(std::size_t i=0;i<events.size();++i)events[i]=trace(i,384);
    for(auto m:{Mode::Fixed,Mode::Varint,Mode::Delta,Mode::Context,Mode::Presence,Mode::Relations}) {
        for(std::size_t i=0;i<events.size();++i)require(encode(m,c,events[i],encoded[i],lengths[i]));
        const auto enc=timing([&](std::size_t i){Buffer out{};std::size_t n=0;require(encode(m,c,events[i%192],out,n));return n+out[0];});
        const auto dec=timing([&](std::size_t i){Event out;require(decode(m,c,encoded[i%192].data(),lengths[i%192],out));return out.key.sequence;});
        std::printf("CODEC model=%s encode_ns=%.2f decode_ns=%.2f buffer_RAM=%zu context_RAM=%zu\n",name(m),enc,dec,sizeof(Buffer),sizeof(Context));
    }
    ExactIndex<416> index;for(std::size_t i=0;i<192;++i)require(index.insert(events[i].key,static_cast<std::uint32_t>(i))==Insert::Added);
    const auto lookup=timing([&](std::size_t i){std::uint32_t h=0;require(index.find(events[i%192].key,h));return h;});
    Sector sector;require(sector.init(c));for(std::size_t i=0;i<32;++i)require(sector.append(events[i]));
    const auto random=timing([&](std::size_t i){Event out;require(sector.read(i%32,out));return out.key.sequence;});
    const auto boot=timing([&](std::size_t){ExactIndex<416> rebuilt;
        require(sector.recover(sector.extent,sector.count,c.serial,c.epoch,c.domain));Event out;
        for(std::size_t i=0;i<sector.count;++i){require(sector.read(i,out));require(rebuilt.insert(out.key,sector.offsets[i])==Insert::Added);}return rebuilt.size();},1000);
    std::printf("RETRIEVAL lookup_ns=%.2f random_read_ns=%.2f rebuild_32_records_ns=%.2f scan_B=%zu sector_fixture_RAM=%zu index_RAM=%zu\n",lookup,random,boot,sector.extent,sizeof(Sector),sizeof(index));
    auto d=domain(events[0]);gs::security::Bytes bytes;
    const auto current=timing([&](std::size_t){require(gs::hub::HubJournal::encode_event_payload(d,bytes));return bytes.size();});
    std::printf("CURRENT_PAYLOAD encode_ns=%.2f ordinary_plain_B=%zu (no AEAD/flash)\n",current,bytes.size());
}
static void current_ledger() {
    using namespace gs::hub::durable;
    gs::host::security::OpenSslCommissioningCrypto crypto;gs::security::Key32 key{};key[0]=42;
    std::size_t writes=0;
    for(unsigned batch=1;batch<=32;++batch){PendingEffectChunk chunk;chunk.storage_epoch=1;chunk.chunk_id=batch;
        DedupeEvidenceChunk evidence;evidence.storage_epoch=1;evidence.chunk_id=batch;evidence.count=4;evidence.registry_owner_domain=true;
        std::size_t transitions=0;
        for(unsigned i=0;i<4;++i){auto e=trace((batch-1)*4+i,384);e.kind=0;e.additional=0;e.first=0;e.last=0;
            auto d=domain(e);gs::security::Bytes payload,blob;require(gs::hub::HubJournal::encode_event_payload(d,payload));
            Transition t;t.storage_epoch=1;t.ordinal=(batch-1)*4+i+1;t.event={d.key.physical_device_id,d.key.source_id,d.key.session_id,d.key.sequence};
            t.enrollment_slot=e.key.node;t.enrollment_generation=1;t.registry_owner_domain=true;
            require(crypto.hmac_sha256(key,payload,t.event_digest));t.causal_input=payload;t.decision={0,0,0,static_cast<std::uint8_t>(t.ordinal-1)};
            require(Codec::encode_transition(crypto,key,t,blob));transitions+=blob.size();
            Effect effect;effect.id=t.event_digest;effect.id[0]=static_cast<std::uint8_t>(t.ordinal);effect.payload=payload;chunk.effects.push_back(effect);
            evidence.entries[i]={e.key.node,1,e.key.session,e.key.sequence,t.event_digest};}
        gs::security::Bytes archive,ev,cp,selector;
        require(Codec::encode_chunk(crypto,key,chunk,archive));require(Codec::encode_evidence_chunk(crypto,key,evidence,ev));
        Checkpoint checkpoint;checkpoint.storage_epoch=1;checkpoint.generation=batch;checkpoint.covered_ordinal=4*batch;
        checkpoint.registry_owner_domain=true;checkpoint.fresh_registry_domain=true;
        for(unsigned i=0;i<batch;++i){checkpoint.pending_chunks.push_back({i+1,{}});DedupeEvidenceReference ref;ref.chunk_id=i+1;ref.digest[0]=1;checkpoint.dedupe_evidence_chunks.push_back(ref);}
        require(Codec::encode_checkpoint(crypto,key,checkpoint,cp));require(Codec::encode_selector(crypto,key,batch,0,selector));
        const auto batch_bytes=transitions+archive.size()+ev.size()+2*cp.size()+2*selector.size()+4*32;
        writes+=batch_bytes;
        if(batch==1||batch==32)std::printf("CURRENT_LEDGER batch=%u transitions=%zu archive=%zu evidence=%zu checkpoints=%zu selectors=%zu receipts=128 total=%zu per_event=%.2f (logical blob writes, empty reducer/no reports)\n",batch,transitions,archive.size(),ev.size(),2*cp.size(),2*selector.size(),batch_bytes,batch_bytes/4.0);
    }
    RetirementSnapshot snapshot;snapshot.storage_epoch=1;snapshot.generation=1;snapshot.occupancy_mask=63;
    for(unsigned i=0;i<6;++i){auto& node=snapshot.nodes[i];node.enrollment_generation=1;node.report_generation=1;node.report_hmac[0]=1;node.current_origin_session=1;node.durable_admission_highwater=32;node.pending_count=32;
        for(unsigned j=0;j<32;++j)node.pending[j]={1,j+1};}
    gs::security::Bytes report;require(RetirementSnapshotRepository::encode(crypto,key,snapshot,report));
    std::printf("CURRENT_LIFETIME_128 logical_blob_write_B=%zu average_B=%.2f native_six_node_snapshot_B=%zu\n",writes,writes/128.0,report.size());
}
static void cold_fixture() {
    auto* file=std::fopen("/tmp/gs-density-cold-blocks.trace","wb");require(file);
    for(unsigned start=0;start<384;start+=32) {
        const auto c=context_for(start,384,start/32+1);ContextBuffer context{};std::size_t cn=0;
        require(encode_context(c,context,cn));std::array<std::uint8_t,4096> block{};
        put_be(block.data(),cn,2);std::copy_n(context.begin(),cn,block.begin()+2);
        put_be(block.data()+cn+2,32,2);std::size_t at=cn+4;
        for(unsigned j=0;j<32;++j){Buffer b{};std::size_t n=0;
            require(encode(Mode::Relations,c,trace(start+j,384),b,n));
            require(at+n+2<=block.size());put_be(block.data()+at,n,2);at+=2;
            std::copy_n(b.begin(),n,block.begin()+at);at+=n;}
        std::uint8_t length[2]{};put_be(length,at,2);
        require(std::fwrite(length,1,2,file)==2&&std::fwrite(block.data(),1,at,file)==at);
    }
    std::fclose(file);
}
int main(int argc,char** argv){
    if(argc==2 && std::string(argv[1])=="--closeout-sizing") {
        std::puts("CLOSEOUT_SIZING existing_codec_only; no lifetime/sanitizer/timing benchmark rerun");
        for(auto extra:{std::size_t{0},std::size_t{324},std::size_t{966}})
            for(bool jitter:{false,true})distribution(384,Mode::Relations,nullptr,extra,jitter);
        return 0;
    }
    std::puts("DENSITY_BENCHMARK median9_after_warmup compiler_CXX17_O2 host_wall_clock_no_target_cycles");
    current_ledger();
    for(auto rate:{384U,1776U,23232U})for(auto m:{Mode::Fixed,Mode::Varint,Mode::Delta,Mode::Context,Mode::Presence,Mode::Relations}){
        FILE* cold=rate==384&&m==Mode::Presence?std::fopen("/tmp/gs-density-normal-warm.trace","wb"):nullptr;
        distribution(rate,m,cold);if(cold)std::fclose(cold);}
    for(auto rate:{384U,1776U,23232U}) {
        for(auto mode:{Mode::Fixed,Mode::Relations})capacity(rate,mode);
        // Self-contained source strings: three bounded length-prefixed fields
        // per context, plus native config version4/hash32 needed by replay.
        // Fixed numeric representation also needs exact ID bindings.
        capacity(rate,Mode::Relations,36+6*(3+32+6+7));
        capacity(rate,Mode::Relations,36+6*(3+64+24+64));
        capacity(rate,Mode::Fixed,36+6*(9+3+32+6+7));
        capacity(rate,Mode::Relations,36+6*(3+32+6+7),true);
        capacity(rate,Mode::Relations,36+6*(3+64+24+64),true);
        capacity(rate,Mode::Fixed,36+6*(9+3+32+6+7),true);
    }
    codecs();cold_fixture();std::printf("CHECKSUM=%llu\n",static_cast<unsigned long long>(sink));
}
