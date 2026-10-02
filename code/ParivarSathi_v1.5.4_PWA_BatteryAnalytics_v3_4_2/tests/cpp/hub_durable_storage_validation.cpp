#include "firmware/hub/components/storage/durable_transition.hpp"
#include "firmware/hub/components/storage/node_retirement_snapshot.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
using namespace gs::hub::durable;
using gs::security::Bytes;
using gs::security::Key32;
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
Key32 test_key() { Key32 k{}; for (std::size_t i=0;i<k.size();++i) k[i]=static_cast<std::uint8_t>(i+1); return k; }
EventIdentity identity(std::uint64_t n) { return {"node-"+std::to_string((n%10)+1),"sensor",77,n}; }
Effect effect(std::size_t n, std::size_t payload=256) {
    Effect e; for(std::size_t i=0;i<e.id.size();++i)e.id[i]=static_cast<std::uint8_t>(n+i);
    e.kind=static_cast<std::uint32_t>(n%65535);e.payload.assign(payload,static_cast<std::uint8_t>(n));return e;
}
Transition transition(std::uint64_t n, bool maximum=false) {
    Transition t;t.storage_epoch=1;t.ordinal=n;t.event=maximum?EventIdentity{std::string(64,'n'),std::string(24,'s'),77,n}:identity(n);
    t.config_version=7;t.config_hash.fill(0x31);t.type=TransitionType::Event;t.enrollment_slot=static_cast<std::uint8_t>((n-1)%10);t.enrollment_generation=1;t.event_digest.fill(static_cast<std::uint8_t>((n%251)+1));
    const std::size_t key_bytes=1+t.event.physical_device_id.size()+1+t.event.source_id.size()+16;
    t.causal_input.assign(maximum?kMaxCausalInputBytes-key_bytes-37:50,0x42);
    t.decision.assign(maximum?kMaxDecisionBytes:32,0x53);
    if(maximum){t.effects.push_back(effect(0,183));t.effects.push_back(effect(1,183));t.effects.push_back(effect(2,182));}
    return t;
}
Checkpoint checkpoint(std::uint64_t generation,std::uint64_t ordinal,bool maximum=false) {
    Checkpoint cp;cp.storage_epoch=1;cp.generation=generation;cp.covered_ordinal=ordinal;cp.config_version=7;cp.config_hash.fill(0x31);
    if(maximum){for(std::uint64_t i=0;i<16;++i)cp.pending_effects.push_back({i+1,static_cast<std::uint8_t>(i),{}});for(std::uint64_t i=0;i<32;++i)cp.pending_chunks.push_back({i+1,{}});for(std::uint64_t i=0;i<32;++i){DedupeEvidenceReference ref;ref.chunk_id=i+1;ref.digest.fill(static_cast<std::uint8_t>(i+1));cp.dedupe_evidence_chunks.push_back(ref);}cp.reducer_state.assign(2723,0x66);}
    else cp.reducer_state={static_cast<std::uint8_t>(ordinal>>24),static_cast<std::uint8_t>(ordinal>>16),static_cast<std::uint8_t>(ordinal>>8),static_cast<std::uint8_t>(ordinal)};
    return cp;
}
void codec_sizes(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key,
                 std::size_t& transition_max,std::size_t& checkpoint_max,
                 std::size_t& chunk_max,std::size_t& bitmap_size,
                 std::size_t& transition_typical,std::size_t& checkpoint_typical,
                 std::size_t& selector_size) {
    Bytes b;auto t=transition(1,true);require(Codec::encode_transition(crypto,key,t,b),"maximum transition encodes");transition_max=b.size();require(transition_max==kMaxTransitionBytes,"transition hard maximum exact");Transition decoded;require(Codec::decode_transition(crypto,key,b,decoded)&&decoded.event==t.event&&decoded.effects.size()==3,"transition round trip");
    t.causal_input.push_back(1);require(!Codec::encode_transition(crypto,key,t,b),"oversize event rejected");
    require(Codec::encode_transition(crypto,key,transition(1),b),"typical transition encodes");transition_typical=b.size();require(transition_typical==249,"typical transition byte count");
    auto cp=checkpoint(1,2,true);require(Codec::encode_checkpoint(crypto,key,cp,b),"maximum checkpoint encodes");checkpoint_max=b.size();require(checkpoint_max==kMaxCheckpointBytes,"checkpoint hard maximum exact");Checkpoint cpd;require(Codec::decode_checkpoint(crypto,key,b,cpd)&&cpd.reducer_state.size()==2723,"checkpoint round trip");
    require(Codec::encode_checkpoint(crypto,key,checkpoint(1,0),b),"typical checkpoint encodes");checkpoint_typical=b.size();
    PendingEffectChunk ch;ch.storage_epoch=1;ch.chunk_id=99;for(std::size_t i=0;i<4;++i)ch.effects.push_back(effect(i));require(Codec::encode_chunk(crypto,key,ch,b),"max pending chunk encodes");chunk_max=b.size();require(chunk_max==kMaxPendingChunkBytes,"chunk hard maximum exact");PendingEffectChunk chd;require(Codec::decode_chunk(crypto,key,b,chd)&&chd.effects.size()==4,"chunk round trip");
    CompletionBitmap bm;bm.storage_epoch=1;bm.generation=1;bm.checkpoint_generation=2;bm.mapping_digest.fill(0x77);bm.committed_bits=0x55;require(Codec::encode_bitmap(crypto,key,bm,b),"bitmap encodes");bitmap_size=b.size();require(bitmap_size==kMaxBitmapBytes,"bitmap fixed bound");CompletionBitmap bmd;require(Codec::decode_bitmap(crypto,key,b,bmd)&&bmd.committed_bits==0x55,"bitmap round trip");b[40]^=1;require(!Codec::decode_bitmap(crypto,key,b,bmd),"corrupt bitmap rejected");
    std::uint64_t selector_generation=1;std::uint8_t selector_index=0;require(Codec::encode_selector(crypto,key,selector_generation,selector_index,b),"selector encodes");selector_size=b.size();require(selector_size==41,"selector metadata size");require(Codec::decode_selector(crypto,key,b,selector_generation,selector_index)&&selector_generation==1&&selector_index==0,"selector round trip");
}
void write_faults(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    for (FaultMode mode : {FaultMode::FailBeforeWrite,FaultMode::PartialWrite,FaultMode::PersistThenFail,FaultMode::PowerLossAfterPersist}) {
        MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);mem.inject(mode);const auto result=store.commit(transition(1));
        if(mode==FaultMode::PersistThenFail||mode==FaultMode::PowerLossAfterPersist){require(result==CommitStatus::AmbiguousResolvedCommitted,"persisted failed write classified committed");mem.power_cycle();DurableStore reboot(mem,crypto,key,1);RecoveryState recovered;require(reboot.recover(recovered)&&recovered.last_ordinal==1,"persisted transition recovers");require(reboot.commit(transition(1))==CommitStatus::Committed,"duplicate retry reuses ordinal");}
        else {require(result==CommitStatus::NotCommitted,"missing/partial write not acknowledged");if(mode==FaultMode::FailBeforeWrite)require(store.commit(transition(1))==CommitStatus::Committed,"same ordinal can retry after pre-write failure");else{mem.power_cycle();DurableStore reboot(mem,crypto,key,1);RecoveryState recovered;require(!reboot.recover(recovered),"partial durable slot fails closed");}}
    }
    MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);require(store.commit(transition(1))==CommitStatus::Committed,"seed transition");RecoveryState state;require(store.recover(state),"seed recovery");require(store.commit(transition(2))==CommitStatus::Committed,"second transition");auto cp=checkpoint(1,2);require(store.checkpoint(cp),"select initial checkpoint");
    MemoryBlobStore overflow_mem;DurableStore overflow_store(overflow_mem,crypto,key,1);
    auto overflow=checkpoint(1,std::numeric_limits<std::uint64_t>::max());Bytes encoded;
    require(Codec::encode_checkpoint(crypto,key,overflow,encoded)&&overflow_mem.write_immutable("cp0",encoded),"install max ordinal fixture");
    require(overflow_store.commit(transition(1))==CommitStatus::NotCommitted,"ordinal overflow refuses append");
}
void checkpoint_faults(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    MemoryBlobStore first;DurableStore first_store(first,crypto,key,1);
    for(std::uint64_t i=1;i<=2;++i)require(first_store.commit(transition(i))==CommitStatus::Committed,"seed initial checkpoint");
    require(first_store.checkpoint(checkpoint(1,2)),"initial A selected");
    for(std::uint64_t i=3;i<=4;++i)require(first_store.commit(transition(i))==CommitStatus::Committed,"seed pending B");
    first.inject(FaultMode::PartialWrite);
    require(!first_store.checkpoint(checkpoint(2,4)),"partial B rejected");
    first.power_cycle();RecoveryState first_recovery;
    require(first_store.recover(first_recovery)&&first_recovery.checkpoint_generation==1&&first_recovery.last_ordinal==4,"partial B keeps valid A plus tail");

    MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);for(std::uint64_t i=1;i<=2;++i)require(store.commit(transition(i))==CommitStatus::Committed,"seed checkpoint transitions");auto first_cp=checkpoint(1,2);Bytes first_bytes;Checkpoint first_decoded;require(Codec::encode_checkpoint(crypto,key,first_cp,first_bytes)&&Codec::decode_checkpoint(crypto,key,first_bytes,first_decoded),"checkpoint A codec");require(store.checkpoint(first_cp),"checkpoint A selected");for(std::uint64_t i=3;i<=4;++i)require(store.commit(transition(i))==CommitStatus::Committed,"second generation tail");require(store.checkpoint(checkpoint(2,4)),"checkpoint B selected");RecoveryState recovered;require(store.recover(recovered)&&recovered.checkpoint_generation==2&&recovered.last_ordinal==4,"A/B selector chooses B");
    for(std::uint64_t i=5;i<=6;++i) {
        require(store.commit(transition(i))==CommitStatus::Committed,"tail after B");
    }
    mem.inject(FaultMode::PartialWrite);
    require(!store.checkpoint(checkpoint(3,6)),"partial inactive checkpoint rejected");
    mem.power_cycle();
    require(store.recover(recovered)&&recovered.checkpoint_generation==2&&recovered.last_ordinal==6&&recovered.checkpoint.reducer_state[3]==4,"partial B preserves old checkpoint and complete tail");
    require(store.checkpoint(checkpoint(3,6)),"checkpoint B selected after earlier partial persistence");mem.power_cycle();require(store.recover(recovered)&&recovered.checkpoint_generation==3&&recovered.last_ordinal==6&&recovered.checkpoint.reducer_state[3]==6,"selected checkpoint recovers");
    // A corrupt newest checkpoint leaves the older checkpoint usable while its tail remains.
    Bytes corrupt(4,0);require(mem.replace("cp0",corrupt),"corrupt B fixture");require(store.recover(recovered)&&recovered.checkpoint_generation==2&&recovered.last_ordinal==6&&recovered.checkpoint.reducer_state[3]==4,"fallback A replays retained tail");
    require(mem.replace("cp1",corrupt),"corrupt remaining checkpoint fixture");
    require(!store.recover(recovered),"both invalid checkpoints fail closed");
}
void metadata_checkpoint_faults(gs::host::security::OpenSslCommissioningCrypto& crypto,
                                const Key32& key) {
    for (const auto fault : {FaultMode::FailBeforeWrite, FaultMode::PartialWrite,
                            FaultMode::PersistThenFail, FaultMode::PowerLossAfterPersist}) {
        for (std::size_t boundary = 0; boundary < 2; ++boundary) {
            MemoryBlobStore mem;
            DurableStore store(mem, crypto, key, 1);
            Checkpoint initial; initial.storage_epoch = 1; initial.generation = 1;
            require(store.checkpoint(initial), "metadata initial checkpoint");
            require(store.commit(transition(1)) == CommitStatus::Committed,
                    "metadata retained transition");
            Checkpoint metadata = initial; metadata.generation = 2;
            mem.inject_after(boundary, fault);
            (void)store.checkpoint(metadata);
            mem.power_cycle();
            DurableStore reboot(mem, crypto, key, 1);
            RecoveryState recovered;
            require(reboot.recover(recovered) && recovered.last_ordinal == 1 &&
                    recovered.checkpoint.covered_ordinal == 0 && recovered.tail.size() == 1 &&
                    recovered.checkpoint.dedupe_evidence_chunks.empty(),
                    "metadata interruption preserves event tail without duplicate evidence");
            metadata.generation = recovered.checkpoint_generation + 1;
            require(reboot.checkpoint(metadata), "metadata retry after interruption");
            require(reboot.recover(recovered) && recovered.tail.size() == 1,
                    "metadata retry retains logical event");
        }
    }
}

void report_checkpoint_ownership(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);RetirementSnapshotRepository reports(mem,crypto,key,1);
    RetirementSnapshot snapshot;snapshot.storage_epoch=1;snapshot.generation=1;snapshot.node_count=1;
    auto& node=snapshot.nodes[0];node.binding_digest.fill(0x31);node.enrollment_generation=1;node.report_generation=1;node.report_hmac.fill(0x32);node.current_origin_session=7;
    ReportSnapshotReference ref;require(reports.prepare_bank(snapshot,0,ref),"verified report bank fixture");
    auto cp=checkpoint(1,0);cp.report_snapshot=ref;require(store.checkpoint(cp),"checkpoint did not select verified report bank");
    RecoveryState recovered;require(store.recover(recovered)&&recovered.checkpoint.report_snapshot&&recovered.checkpoint.report_snapshot->generation==1,"checkpoint failed to recover report ownership");
    Bytes corrupt{0,1,2};require(mem.replace("ret"+std::to_string(ref.bank),corrupt),"corrupt selected report bank fixture");
    require(!store.recover(recovered),"checkpoint accepted a missing or changed report bank");
}
void exact_evidence_checkpoint_and_retirement(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);auto event=transition(1);
    event.causal_input={static_cast<std::uint8_t>(gs::EventKind::Heartbeat)};
    require(store.commit(event)==CommitStatus::Committed,"Hub heartbeat commit before lost ACK");
    require(store.checkpoint(checkpoint(1,1)),"event digest handoff to checkpoint failed");
    DurableStore reboot(mem,crypto,key,1);RecoveryState recovered;
    require(reboot.recover(recovered)&&recovered.checkpoint.dedupe_evidence_chunks.size()==1,"checkpoint did not own exact digest evidence");
    require(reboot.commit(event)==CommitStatus::Committed,"lost ACK Heartbeat retry was not exact duplicate after Hub reboot");
    auto conflict=event;conflict.event_digest[0]^=1;
    require(reboot.commit(conflict)==CommitStatus::Conflict,"conflicting duplicate passed after Hub reboot");

    RetirementSnapshotRepository reports(mem,crypto,key,1);RetirementSnapshot snapshot;
    snapshot.storage_epoch=1;snapshot.generation=1;snapshot.node_count=1;
    auto& node=snapshot.nodes[0];node.binding_digest.fill(0x41);node.enrollment_generation=1;
    node.report_generation=1;node.report_hmac.fill(0x42);node.current_origin_session=77;
    node.durable_admission_highwater=1;
    ReportSnapshotReference ref;require(reports.prepare_bank(snapshot,0,ref),"drained report bank write failed");
    auto next=checkpoint(2,1);next.report_snapshot=ref;
    require(reboot.checkpoint(next),"checkpoint did not select report closure");
    require(reboot.recover(recovered)&&recovered.checkpoint.dedupe_evidence_chunks.empty(),"retired digest was not released by complete report");
    require(reboot.commit(event)==CommitStatus::NotCommitted,"retired key was admitted after report coverage");
}
void stream_validation(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    MemoryBlobStore gap;Bytes blob;require(Codec::encode_transition(crypto,key,transition(2),blob)&&gap.write_immutable("tr1",blob),"install ordinal gap");DurableStore gap_store(gap,crypto,key,1);RecoveryState state;require(!gap_store.recover(state),"ordinal gap fails closed");
    MemoryBlobStore duplicate;require(Codec::encode_transition(crypto,key,transition(1),blob)&&duplicate.write_immutable("tr0",blob),"install first ordinal");require(duplicate.write_immutable("tr1",blob),"install duplicate ordinal");DurableStore duplicate_store(duplicate,crypto,key,1);require(!duplicate_store.recover(state),"duplicate ordinals fail closed");
    MemoryBlobStore replay;DurableStore replay_store(replay,crypto,key,1);auto newest=transition(2);newest.event={"node-x","sensor",90,2};require(replay_store.commit(newest)==CommitStatus::Committed,"newest source sequence accepted");auto stale=transition(1);stale.event={"node-x","sensor",90,1};require(replay_store.commit(stale)==CommitStatus::Committed,"N+1 before N is accepted absent retirement proof");auto exact=newest;require(replay_store.commit(exact)==CommitStatus::Committed,"exact retry is deduplicated");auto conflict=newest;conflict.event_digest[0]^=0xff;require(replay_store.commit(conflict)==CommitStatus::Conflict,"same EventKey with different digest fails closed");
    MemoryBlobStore full;auto full_cp=checkpoint(1,0);for(std::uint64_t i=0;i<kMaxPendingEffects;++i)full_cp.pending_effects.push_back({i+1,0,{}});require(Codec::encode_checkpoint(crypto,key,full_cp,blob)&&full.write_immutable("cp0",blob),"install full pending-effect state");DurableStore full_store(full,crypto,key,1);auto extra=transition(1);extra.effects.push_back(effect(101));require(full_store.commit(extra)==CommitStatus::NotCommitted,"full pending-effect bound backpressures");
}
void selector_ordering(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);
    require(store.commit(transition(1))==CommitStatus::Committed&&store.commit(transition(2))==CommitStatus::Committed,"selector seed A");
    require(store.checkpoint(checkpoint(1,2)),"selector A commit");
    RecoveryState recovered;require(store.recover(recovered)&&recovered.checkpoint_generation==1&&recovered.last_ordinal==2,"valid A with empty B");
    require(store.commit(transition(3))==CommitStatus::Committed&&store.commit(transition(4))==CommitStatus::Committed,"selector seed B");
    auto cp_b=checkpoint(2,4);Bytes cp_blob;require(Codec::encode_checkpoint(crypto,key,cp_b,cp_blob)&&mem.write_immutable("cp1",cp_blob),"write unselected checkpoint B");
    require(store.recover(recovered)&&recovered.checkpoint_generation==1&&recovered.last_ordinal==4,"old selector retains A with complete tail");
    Bytes selector;require(Codec::encode_selector(crypto,key,2,1,selector)&&mem.replace("sel0",selector),"switch selector to B");
    require(store.recover(recovered)&&recovered.checkpoint_generation==2&&recovered.last_ordinal==4,"selector switch publishes B");
    Bytes corrupt(4,0);require(mem.replace("sel0",corrupt)&&mem.replace("sel1",corrupt),"corrupt both selector copies");
    require(store.recover(recovered)&&recovered.checkpoint_generation==2&&recovered.last_ordinal==4,"corrupt selectors select newest complete checkpoint");
}
void handoff_faults(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    for(FaultMode mode:{FaultMode::FailBeforeWrite,FaultMode::PartialWrite,FaultMode::PersistThenFail,FaultMode::PowerLossAfterPersist}){
        MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);std::vector<Effect> effects{effect(9)};std::vector<EffectReference> refs{{1,0,effects[0].id}};auto cause=transition(1);cause.effects=effects;require(store.commit(cause)==CommitStatus::Committed,"handoff causal transition committed");Checkpoint cp=checkpoint(1,1);mem.inject(mode);const bool handed=store.handoff_effects(refs,effects,41,cp);
        if(mode==FaultMode::FailBeforeWrite||mode==FaultMode::PartialWrite)require(!handed,"unverified chunk not handed off");else require(handed,"exact persisted chunk verified after ambiguous write");
        mem.power_cycle();RecoveryState recovered;require(store.recover(recovered)&&recovered.last_ordinal==1&&recovered.tail.size()==1&&recovered.tail[0].effects[0].id==effects[0].id,"causal log still owns payload before selector");
        if(handed){require(cp.pending_chunks.size()==1&&cp.pending_effects.size()==1&&cp.pending_effects[0].location==0,"checkpoint can reference verified chunk and item");require(store.checkpoint(cp),"checkpoint selects chunk ownership");require(store.recover(recovered)&&recovered.checkpoint.pending_chunks.size()==1&&recovered.tail.empty(),"selected checkpoint owns payload reference");PendingEffectChunk restored;require(store.read_pending_chunk(41,restored)&&restored.effects.size()==1&&restored.effects[0].id==effects[0].id,"checkpoint reference restores canonical payload");}
    }
}
void bitmap_and_stress(gs::host::security::OpenSslCommissioningCrypto& crypto,const Key32& key) {
    MemoryBlobStore mem;DurableStore store(mem,crypto,key,1);CompletionBitmap bm;bm.mapping_digest.fill(8);bm.checkpoint_generation=1;bm.committed_bits=1;require(store.commit_bitmap(bm)==CommitStatus::Committed,"first completion bitmap");const auto writes=mem.write_count();require(store.commit_bitmap(bm)==CommitStatus::Committed,"duplicate committed state is idempotently recorded");CompletionBitmap got;require(store.read_bitmap(bm.mapping_digest,got)&&got.committed_bits==1&&got.generation==1&&mem.write_count()==writes,"bitmap duplicate avoids a write");
    MemoryBlobStore stress_mem;DurableStore stress(stress_mem,crypto,key,1);
    Checkpoint rolling=checkpoint(1,0);std::uint16_t completed_group=0;std::uint64_t current_group=std::numeric_limits<std::uint64_t>::max();
    for(std::uint64_t n=1;n<=1000;++n){
        auto candidate=transition(n);candidate.type=TransitionType::Timer;
        if(n%100==0)candidate.effects.push_back(effect(static_cast<std::size_t>(n),8));
        const auto status=stress.commit(candidate);require(status==CommitStatus::Committed||status==CommitStatus::AmbiguousResolvedCommitted,"stress transition commit");
        const auto group=(n-1)/16;if(group!=current_group){current_group=group;completed_group=0;}
        completed_group=static_cast<std::uint16_t>(completed_group|(1U<<((n-1)%16)));
        CompletionBitmap receipt;receipt.mapping_digest.fill(static_cast<std::uint8_t>(group+1));receipt.checkpoint_generation=(n+1)/2;receipt.committed_bits=completed_group;
        require(stress.commit_bitmap(receipt)==CommitStatus::Committed,"stress backend completion");
        if(n%2==0){
            RecoveryState pending;require(stress.recover(pending)&&pending.last_ordinal==n,"checkpoint candidate recovery");
            rolling.generation=n/2;rolling.covered_ordinal=n;rolling.reducer_state={static_cast<std::uint8_t>(n>>24),static_cast<std::uint8_t>(n>>16),static_cast<std::uint8_t>(n>>8),static_cast<std::uint8_t>(n)};
            std::vector<Effect> effects;std::vector<EffectReference> refs;
            for(const auto& item:pending.tail)for(std::size_t i=0;i<item.effects.size();++i){effects.push_back(item.effects[i]);refs.push_back({item.ordinal,static_cast<std::uint8_t>(i),item.effects[i].id});}
            if(!effects.empty())require(stress.handoff_effects(refs,effects,n/2,rolling),"stress effect payload handoff");
            require(stress.checkpoint(rolling),"every-two checkpoint");
        }
        if(n%25==0){RecoveryState s;require(stress.recover(s)&&s.last_ordinal==n,"stress restore cycle");}
    }
    RecoveryState final;require(stress.recover(final)&&final.last_ordinal==1000&&final.tail.size()<=4&&final.checkpoint.pending_effects.size()==10,"1000 transition bounded recovery with handed-off effects");for(std::uint64_t n=100;n<=1000;n+=100){PendingEffectChunk restored;require(stress.read_pending_chunk(n/2,restored)&&restored.effects.size()==1,"stress effect chunk restores");}CompletionBitmap final_receipt;std::array<std::uint8_t,32> last_mapping{};last_mapping.fill(63);require(stress.read_bitmap(last_mapping,final_receipt)&&final_receipt.committed_bits==0x00ff,"stress completion bitmap restores");auto after_stress=transition(1001);after_stress.type=TransitionType::Timer;require(stress.commit(after_stress)==CommitStatus::Committed,"timer transition follows stress");require(stress.recover(final)&&final.last_ordinal==1001,"next ordinal advances exactly once");
}
void modeled_migration_budget() {
    const auto entries = [](std::size_t bytes) {
        return 2U + (bytes + 31U) / 32U; // blob index, chunk metadata, data entries
    };
    const std::size_t legacy = 128U * entries(284U) + 128U * entries(32U);
    const std::size_t transition_log = 4U * entries(kMaxTransitionBytes);
    const std::size_t pending_node_events = 16U * entries(1004U);
    const std::size_t effect_chunks = 4U * entries(kMaxPendingChunkBytes);
    const std::size_t checkpoints = 3U * (3U + (4253U + 31U) / 32U);
    const std::size_t bitmaps = 3U * entries(kMaxBitmapBytes);
    const std::size_t metadata = 5U * entries(128U);
    const auto total_entries = legacy + transition_log + pending_node_events +
        effect_chunks + checkpoints + bitmaps + metadata;
    const std::size_t raw_peak = 40448U + 4U*kMaxTransitionBytes +
        2U*kMaxCheckpointBytes + 16U*1004U + 4U*kMaxPendingChunkBytes +
        2U*kMaxBitmapBytes + 512U + kMaxCheckpointBytes +
        kMaxBitmapBytes + 128U + 1004U;
    require(legacy==1792&&total_entries==3160,"base migration NVS entry budget");
    const std::size_t implementation_entries=total_entries+3U*((kMaxCheckpointBytes-4253U+31U)/32U)+34U;
    require(implementation_entries==3221,"retirement migration NVS entry budget");
    require(raw_peak==83218&&131072U-raw_peak==47854,"migration raw byte budget");
    require((4032U-implementation_entries)*100U>=4032U*20U,"migration NVS entry margin");
    // Conservative reservation: existing migration peak plus all independent
    // cNNN receipts, even where source and destination share the same key.
    const auto completion_bytes = 128U * 32U;
    const auto completion_entries = 128U * entries(32U);
    require(raw_peak + completion_bytes == 87314U &&
            131072U - raw_peak - completion_bytes == 43758U,
            "independent completion raw storage bound");
    require(implementation_entries + completion_entries == 3605U &&
            4032U - implementation_entries - completion_entries == 427U,
            "independent completion NVS entry bound");
}
}
int main(){
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;const auto key=test_key();std::size_t t=0,c=0,ch=0,bm=0,tt=0,ct=0,selector=0;
        codec_sizes(crypto,key,t,c,ch,bm,tt,ct,selector);write_faults(crypto,key);checkpoint_faults(crypto,key);metadata_checkpoint_faults(crypto,key);report_checkpoint_ownership(crypto,key);exact_evidence_checkpoint_and_retirement(crypto,key);stream_validation(crypto,key);selector_ordering(crypto,key);handoff_faults(crypto,key);bitmap_and_stress(crypto,key);modeled_migration_budget();
        std::cout<<"durable transition storage: PASS transition="<<tt<<"/"<<t<<" checkpoint="<<ct<<"/"<<c<<" chunk="<<ch<<" bitmap="<<bm<<" selector="<<selector<<"\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"durable transition storage: FAIL: "<<e.what()<<"\n";return 1;}
}
