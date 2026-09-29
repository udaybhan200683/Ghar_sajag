#include "storage/durable_transition.hpp"

#include <algorithm>
#include <limits>

namespace gs::hub::durable {
namespace {
using security::Bytes;
constexpr std::uint8_t kSchema = 1;
constexpr std::size_t kTransitionHeader = 72;
constexpr std::size_t kAeadOverhead = 28;
constexpr std::size_t kChunkHeader = 64;
constexpr std::size_t kBitmapPlain = kMaxBitmapBytes - kAeadOverhead;

struct Writer {
    Bytes b;
    void u8(std::uint8_t v) { b.push_back(v); }
    void u16(std::uint16_t v) { b.push_back(v >> 8); b.push_back(v); }
    void u32(std::uint32_t v) { for (int s=24;s>=0;s-=8) b.push_back(v >> s); }
    void u64(std::uint64_t v) { for (int s=56;s>=0;s-=8) b.push_back(v >> s); }
    void raw(const std::uint8_t* p, std::size_t n) { b.insert(b.end(), p, p+n); }
    void raw(const Bytes& v) { b.insert(b.end(), v.begin(), v.end()); }
    bool str(const std::string& s, std::size_t cap) {
        if (s.empty() || s.size() > cap) return false;
        u8(static_cast<std::uint8_t>(s.size())); raw(reinterpret_cast<const std::uint8_t*>(s.data()),s.size()); return true;
    }
};
struct Reader {
    const Bytes& b; std::size_t p{0};
    bool room(std::size_t n) const { return p <= b.size() && n <= b.size()-p; }
    bool u8(std::uint8_t& v) { if(!room(1))return false;v=b[p++];return true; }
    bool u16(std::uint16_t& v) { if(!room(2))return false;v=(std::uint16_t(b[p])<<8)|b[p+1];p+=2;return true; }
    bool u32(std::uint32_t& v) { if(!room(4))return false;v=0;for(int i=0;i<4;++i)v=(v<<8)|b[p++];return true; }
    bool u64(std::uint64_t& v) { if(!room(8))return false;v=0;for(int i=0;i<8;++i)v=(v<<8)|b[p++];return true; }
    bool raw(std::uint8_t* out,std::size_t n){if(!room(n))return false;std::copy_n(b.begin()+p,n,out);p+=n;return true;}
    bool str(std::string& out,std::size_t cap){std::uint8_t n=0;if(!u8(n)||n==0||n>cap||!room(n))return false;out.assign(reinterpret_cast<const char*>(b.data()+p),n);p+=n;return true;}
};
Bytes aad(const char* label) { return Bytes(label,label+std::char_traits<char>::length(label)); }
bool seal(security::CommissioningCrypto& c,const security::Key32& key,const char* label,
          const Bytes& plain,Bytes& blob,std::size_t cap) {
    if(plain.size()+kAeadOverhead>cap)return false;
    security::Nonce12 nonce{};security::GcmTag tag{};Bytes cipher;
    if(!c.random_bytes(nonce.data(),nonce.size())||!c.seal_aes256_gcm(key,nonce,aad(label),plain,cipher,tag))return false;
    blob.assign(nonce.begin(),nonce.end());blob.insert(blob.end(),cipher.begin(),cipher.end());blob.insert(blob.end(),tag.begin(),tag.end());
    return blob.size()<=cap;
}
bool open(security::CommissioningCrypto& c,const security::Key32& key,const char* label,
          const Bytes& blob,Bytes& plain,std::size_t cap) {
    if(blob.size()<kAeadOverhead||blob.size()>cap)return false;
    security::Nonce12 nonce{};security::GcmTag tag{};std::copy_n(blob.begin(),12,nonce.begin());std::copy_n(blob.end()-16,16,tag.begin());
    Bytes cipher(blob.begin()+12,blob.end()-16);return c.open_aes256_gcm(key,nonce,aad(label),cipher,tag,plain);
}
bool same(const Effect& a,const Effect& b){return a.id==b.id&&a.kind==b.kind&&a.payload==b.payload;}
bool valid_effects(const std::vector<Effect>& effects){
    for(std::size_t i=0;i<effects.size();++i){
        if(effects[i].payload.size()>kMaxEffectPayloadBytes||
           std::all_of(effects[i].id.begin(),effects[i].id.end(),[](std::uint8_t b){return b==0;}))return false;
        for(std::size_t j=0;j<i;++j)if(effects[i].id==effects[j].id)return false;
    }
    return true;
}
std::string trkey(std::size_t i){return "tr"+std::to_string(i);}
std::string cpkey(std::size_t i){return "cp"+std::to_string(i);}
std::string selkey(std::size_t i){return "sel"+std::to_string(i);}

bool encode_selector_blob(security::CommissioningCrypto& c,const security::Key32& key,
                     std::uint64_t generation,std::uint8_t index,Bytes& out){
    Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GSS1"),4);w.u64(generation);w.u8(index);return seal(c,key,"hub-selector-v1",w.b,out,64);
}
bool decode_selector_blob(security::CommissioningCrypto& c,const security::Key32& key,
                     const Bytes& in,std::uint64_t& generation,std::uint8_t& index){
    Bytes p;if(!open(c,key,"hub-selector-v1",in,p,64))return false;Reader r{p};std::uint8_t magic[4]{};
    return r.raw(magic,4)&&std::equal(magic,magic+4,reinterpret_cast<const std::uint8_t*>("GSS1"))&&r.u64(generation)&&r.u8(index)&&index<2&&r.p==p.size();
}

bool encode_identity(Writer& w,const EventIdentity& e){return w.str(e.physical_device_id,64)&&w.str(e.source_id,24)&&(w.u64(e.session_id),w.u64(e.sequence),true);}
bool decode_identity(Reader& r,EventIdentity& e){return r.str(e.physical_device_id,64)&&r.str(e.source_id,24)&&r.u64(e.session_id)&&r.u64(e.sequence)&&e.session_id!=0&&e.sequence!=0;}
void encode_effect(Writer& w,const Effect& e){w.raw(e.id.data(),e.id.size());w.u16(static_cast<std::uint16_t>(e.kind));w.u16(static_cast<std::uint16_t>(e.payload.size()));w.raw(e.payload);}
bool decode_effect(Reader& r,Effect& e){std::uint16_t kind=0,n=0;if(!r.raw(e.id.data(),e.id.size())||!r.u16(kind)||!r.u16(n)||n>kMaxEffectPayloadBytes||!r.room(n))return false;e.kind=kind;e.payload.assign(r.b.begin()+r.p,r.b.begin()+r.p+n);r.p+=n;return true;}
} // namespace

bool EventIdentity::operator==(const EventIdentity& o)const{return physical_device_id==o.physical_device_id&&source_id==o.source_id&&session_id==o.session_id&&sequence==o.sequence;}
bool EventIdentity::operator<(const EventIdentity& o)const{return std::tie(physical_device_id,source_id,session_id,sequence)<std::tie(o.physical_device_id,o.source_id,o.session_id,o.sequence);}

bool Codec::encode_transition(security::CommissioningCrypto& c,const security::Key32& key,const Transition& t,Bytes& out){
    out.clear();if(t.storage_epoch==0||t.ordinal==0||t.event.physical_device_id.empty()||t.event.source_id.empty()||t.event.session_id==0||t.event.sequence==0||t.causal_input.size()>kMaxCausalInputBytes||t.decision.size()>kMaxDecisionBytes||t.effects.size()>kMaxEffectsPerTransition||!valid_effects(t.effects)||static_cast<unsigned>(t.type)<1||static_cast<unsigned>(t.type)>4)return false;
    Writer event; if(!encode_identity(event,t.event))return false;event.raw(t.causal_input);if(event.b.size()>kMaxCausalInputBytes)return false;
    Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GDT1"),4);w.u8(kSchema);w.u32(t.storage_epoch);w.u64(t.ordinal);w.u32(t.config_version);w.raw(t.config_hash.data(),32);w.u8(static_cast<std::uint8_t>(t.type));w.u16(static_cast<std::uint16_t>(event.b.size()));w.u16(static_cast<std::uint16_t>(t.decision.size()));w.u8(static_cast<std::uint8_t>(t.effects.size()));
    while(w.b.size()<kTransitionHeader)w.u8(0);
    w.raw(event.b);w.raw(t.decision);
    for(const auto& e:t.effects){if(e.kind>65535||e.payload.size()>kMaxEffectPayloadBytes)return false;encode_effect(w,e);}
    if(w.b.size()+kAeadOverhead>kMaxTransitionBytes)return false;
    return seal(c,key,"hub-transition-v1",w.b,out,kMaxTransitionBytes);
}
bool Codec::decode_transition(security::CommissioningCrypto& c,const security::Key32& key,const Bytes& blob,Transition& t){
    Bytes p;if(!open(c,key,"hub-transition-v1",blob,p,kMaxTransitionBytes)||p.size()<kTransitionHeader)return false;Reader r{p};std::uint8_t magic[4]{},ver=0,type=0,count=0;std::uint16_t event_len=0,decision_len=0;
    if(!r.raw(magic,4)||!std::equal(magic,magic+4,reinterpret_cast<const std::uint8_t*>("GDT1"))||!r.u8(ver)||ver!=kSchema||!r.u32(t.storage_epoch)||!r.u64(t.ordinal)||!r.u32(t.config_version)||!r.raw(t.config_hash.data(),32)||!r.u8(type)||type<1||type>4||!r.u16(event_len)||event_len>kMaxCausalInputBytes||!r.u16(decision_len)||decision_len>kMaxDecisionBytes||!r.u8(count)||count>kMaxEffectsPerTransition)return false;
    for (std::size_t i = r.p; i < kTransitionHeader; ++i) {
        if (p[i] != 0) return false;
    }
    r.p = kTransitionHeader;
    if (!r.room(event_len + decision_len)) return false;
    Bytes ev(p.begin() + r.p, p.begin() + r.p + event_len);
    r.p += event_len;
    Reader er{ev};
    if (!decode_identity(er, t.event)) return false;
    t.causal_input.assign(ev.begin() + er.p, ev.end());
    t.decision.assign(p.begin() + r.p, p.begin() + r.p + decision_len);
    r.p += decision_len;
    t.type = static_cast<TransitionType>(type);
    t.effects.clear();
    for (unsigned i = 0; i < count; ++i) {
        Effect e;
        if (!decode_effect(r, e)) return false;
        t.effects.push_back(std::move(e));
    }
    return t.storage_epoch != 0 && t.ordinal != 0 && r.p == p.size() && valid_effects(t.effects);
}

bool Codec::encode_checkpoint(security::CommissioningCrypto& c,const security::Key32& key,const Checkpoint& cp,Bytes& out){
    out.clear();if(cp.storage_epoch==0||cp.generation==0||cp.reducer_state.size()>kMaxCheckpointBytes||cp.pending_effects.size()>kMaxCheckpointEffectRefs||cp.pending_chunks.size()>kMaxCheckpointChunkRefs||cp.dedupe_frontiers.size()>kMaxDedupeFrontiers)return false;
    Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GCP1"),4);w.u8(kSchema);w.u32(cp.storage_epoch);w.u64(cp.generation);w.u64(cp.covered_ordinal);w.u32(cp.config_version);w.raw(cp.config_hash.data(),32);w.u16(static_cast<std::uint16_t>(cp.reducer_state.size()));w.raw(cp.reducer_state);w.u8(static_cast<std::uint8_t>(cp.pending_effects.size()));for(const auto& ref:cp.pending_effects){w.u64(ref.ordinal);w.u8(ref.index);w.u8(ref.location);}w.u8(static_cast<std::uint8_t>(cp.pending_chunks.size()));for(const auto& ref:cp.pending_chunks)w.u64(ref.chunk_id);w.u8(static_cast<std::uint8_t>(cp.dedupe_frontiers.size()));for(const auto& frontier:cp.dedupe_frontiers)if(!encode_identity(w,frontier))return false;
    return seal(c,key,"hub-checkpoint-v1",w.b,out,kMaxCheckpointBytes);
}
bool Codec::decode_checkpoint(security::CommissioningCrypto& c,const security::Key32& key,const Bytes& blob,Checkpoint& cp){
    Bytes p;if(!open(c,key,"hub-checkpoint-v1",blob,p,kMaxCheckpointBytes))return false;Reader r{p};std::uint8_t magic[4]{},ver=0,n8=0;std::uint16_t n16=0;
    if (!r.raw(magic, 4) ||
        !std::equal(magic, magic + 4, reinterpret_cast<const std::uint8_t*>("GCP1")) ||
        !r.u8(ver) || ver != kSchema || !r.u32(cp.storage_epoch) ||
        !r.u64(cp.generation) || !r.u64(cp.covered_ordinal) ||
        !r.u32(cp.config_version) || !r.raw(cp.config_hash.data(), 32) ||
        !r.u16(n16) || n16 > kMaxCheckpointBytes || !r.room(n16)) return false;
    cp.reducer_state.assign(p.begin() + r.p, p.begin() + r.p + n16);
    r.p += n16;
    if (!r.u8(n8) || n8 > kMaxCheckpointEffectRefs) return false;
    cp.pending_effects.clear();
    for (unsigned i = 0; i < n8; ++i) {
        EffectReference ref;
        std::uint8_t reserved = 0;
        if (!r.u64(ref.ordinal) || !r.u8(ref.index) || !r.u8(reserved) ||
            (reserved != 0xff && (reserved >> 2) >= kMaxCheckpointChunkRefs)) return false;
        ref.location = reserved;
        cp.pending_effects.push_back(ref);
    }
    if (!r.u8(n8) || n8 > kMaxCheckpointChunkRefs) return false;
    cp.pending_chunks.clear();
    for (unsigned i = 0; i < n8; ++i) {
        ChunkReference ref;
        if (!r.u64(ref.chunk_id)) return false;
        cp.pending_chunks.push_back(ref);
    }
    if (!r.u8(n8) || n8 > kMaxDedupeFrontiers) return false;
    cp.dedupe_frontiers.clear();
    for (unsigned i = 0; i < n8; ++i) {
        EventIdentity frontier;
        if (!decode_identity(r, frontier)) return false;
        cp.dedupe_frontiers.push_back(std::move(frontier));
    }
    if (r.p != p.size()) return false;
    return cp.storage_epoch != 0 && cp.generation != 0;
}

bool Codec::encode_chunk(security::CommissioningCrypto& c,const security::Key32& key,const PendingEffectChunk& chunk,Bytes& out){
    out.clear();if(chunk.storage_epoch==0||chunk.effects.empty()||chunk.effects.size()>kMaxEffectsPerChunk||chunk.effects.size()>kMaxPendingEffects||!valid_effects(chunk.effects))return false;Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GEC1"),4);w.u8(kSchema);w.u32(chunk.storage_epoch);w.u64(chunk.chunk_id);w.u8(static_cast<std::uint8_t>(chunk.effects.size()));while(w.b.size()<kChunkHeader)w.u8(0);for(const auto& e:chunk.effects){if(e.kind>65535)return false;encode_effect(w,e);}return seal(c,key,"hub-effect-chunk-v1",w.b,out,kMaxPendingChunkBytes);
}
bool Codec::decode_chunk(security::CommissioningCrypto& c,const security::Key32& key,const Bytes& blob,PendingEffectChunk& chunk){
    Bytes p;if(!open(c,key,"hub-effect-chunk-v1",blob,p,kMaxPendingChunkBytes)||p.size()<kChunkHeader)return false;Reader r{p};std::uint8_t magic[4]{},ver=0,count=0;if(!r.raw(magic,4)||!std::equal(magic,magic+4,reinterpret_cast<const std::uint8_t*>("GEC1"))||!r.u8(ver)||ver!=kSchema||!r.u32(chunk.storage_epoch)||!r.u64(chunk.chunk_id)||!r.u8(count)||count==0||count>kMaxEffectsPerChunk)return false;for(std::size_t i=r.p;i<kChunkHeader;++i)if(p[i]!=0)return false;r.p=kChunkHeader;chunk.effects.clear();for(unsigned i=0;i<count;++i){Effect e;if(!decode_effect(r,e))return false;chunk.effects.push_back(std::move(e));}return r.p==p.size()&&chunk.storage_epoch!=0&&valid_effects(chunk.effects);
}

bool Codec::encode_bitmap(security::CommissioningCrypto& c,const security::Key32& key,const CompletionBitmap& bm,Bytes& out){
    out.clear();if(bm.storage_epoch==0||bm.generation==0)return false;Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GBM1"),4);w.u8(kSchema);w.u32(bm.storage_epoch);w.u64(bm.generation);w.u64(bm.checkpoint_generation);w.raw(bm.mapping_digest.data(),32);w.u16(bm.committed_bits);while(w.b.size()<kBitmapPlain)w.u8(0);return seal(c,key,"hub-completion-bitmap-v1",w.b,out,kMaxBitmapBytes);
}
bool Codec::decode_bitmap(security::CommissioningCrypto& c,const security::Key32& key,const Bytes& blob,CompletionBitmap& bm){
    Bytes p;if(!open(c,key,"hub-completion-bitmap-v1",blob,p,kMaxBitmapBytes)||p.size()!=kBitmapPlain)return false;Reader r{p};std::uint8_t magic[4]{},ver=0;if(!r.raw(magic,4)||!std::equal(magic,magic+4,reinterpret_cast<const std::uint8_t*>("GBM1"))||!r.u8(ver)||ver!=kSchema||!r.u32(bm.storage_epoch)||!r.u64(bm.generation)||!r.u64(bm.checkpoint_generation)||!r.raw(bm.mapping_digest.data(),32)||!r.u16(bm.committed_bits))return false;for(std::size_t i=r.p;i<p.size();++i)if(p[i]!=0)return false;return bm.storage_epoch!=0&&bm.generation!=0;
}
bool Codec::encode_selector(security::CommissioningCrypto& c,const security::Key32& key,
                            std::uint64_t generation,std::uint8_t index,Bytes& out){
    return encode_selector_blob(c,key,generation,index,out);
}
bool Codec::decode_selector(security::CommissioningCrypto& c,const security::Key32& key,
                            const Bytes& blob,std::uint64_t& generation,std::uint8_t& index){
    return decode_selector_blob(c,key,blob,generation,index);
}

bool MemoryBlobStore::read(const std::string& k,Bytes& v,bool& f){auto i=values_.find(k);f=i!=values_.end();v=f?i->second:Bytes{};return true;}
bool MemoryBlobStore::write_immutable(const std::string& k,const Bytes& v){return perform(k,v,true);}
bool MemoryBlobStore::replace(const std::string& k,const Bytes& v){return perform(k,v,false);}
bool MemoryBlobStore::perform(const std::string& k,const Bytes& v,bool immutable){
    ++write_count_;
    if (writes_before_fault_ != 0) { --writes_before_fault_; }
    else {
        const FaultMode mode = next_fault_;
        next_fault_ = FaultMode::None;
        auto i = values_.find(k);
        if (immutable && i != values_.end()) return false;
        if (mode == FaultMode::FailBeforeWrite) return false;
        if (mode == FaultMode::PartialWrite) {
            values_[k] = Bytes(v.begin(), v.begin() + v.size() / 2);
            return false;
        }
        values_[k] = v;
        return mode != FaultMode::PersistThenFail && mode != FaultMode::PowerLossAfterPersist;
    }
    auto i = values_.find(k);
    if (immutable && i != values_.end()) return false;
    values_[k] = v;
    return true;
}

DurableStore::DurableStore(BlobStore& s,security::CommissioningCrypto& c,security::Key32 k,std::uint32_t e):store_(s),crypto_(c),key_(k),epoch_(e){}
DurableStore::~DurableStore(){crypto_.secure_zero(key_.data(),key_.size());}

bool DurableStore::recover(RecoveryState& state){
    state={};state.storage_epoch=epoch_;std::array<Checkpoint,2> cps{};std::array<bool,2> valid{};std::array<bool,2> present{};for(std::size_t i=0;i<2;++i){Bytes b;bool f=false;if(!store_.read(cpkey(i),b,f))return false;present[i]=f;if(f)valid[i]=Codec::decode_checkpoint(crypto_,key_,b,cps[i])&&cps[i].storage_epoch==epoch_;}
    std::uint64_t selgen=0;std::uint8_t selidx=0;bool have_sel=false;bool selector_present=false;for(std::size_t i=0;i<2;++i){Bytes b;bool f=false;if(!store_.read(selkey(i),b,f))return false;selector_present=selector_present||f;std::uint64_t g=0;std::uint8_t idx=0;if(f&&decode_selector_blob(crypto_,key_,b,g,idx)&&valid[idx]&&cps[idx].generation==g&&(!have_sel||g>selgen)){selgen=g;selidx=idx;have_sel=true;}}
    int selected=-1;if(have_sel)selected=selidx;else if(valid[0]||valid[1])selected=(!valid[0]?1:!valid[1]?0:(cps[1].generation>cps[0].generation?1:0));else if(present[0]||present[1]||selector_present)return false;
    std::uint64_t boundary=0;if(selected>=0){state.checkpoint=cps[selected];state.checkpoint_generation=cps[selected].generation;boundary=cps[selected].covered_ordinal;}
    std::vector<Transition> all;for(std::size_t i=0;i<4;++i){Bytes b;bool f=false;if(!store_.read(trkey(i),b,f))return false;if(!f)continue;Transition t;if(!Codec::decode_transition(crypto_,key_,b,t)||t.storage_epoch!=epoch_)return false;if(t.ordinal>boundary)all.push_back(std::move(t));}
    std::sort(all.begin(),all.end(),[](const Transition&a,const Transition&b){return a.ordinal<b.ordinal;});std::uint64_t expected=boundary+1;for(const auto&t:all){if(t.ordinal!=expected++)return false;state.tail.push_back(t);}state.last_ordinal=state.tail.empty()?boundary:state.tail.back().ordinal;return true;
}

CommitStatus DurableStore::commit(Transition candidate){
    RecoveryState s;if(!recover(s))return CommitStatus::StorageFault;if(s.last_ordinal==std::numeric_limits<std::uint64_t>::max())return CommitStatus::NotCommitted;
    auto same_source = [](const EventIdentity& a, const EventIdentity& b) {
        return a.physical_device_id == b.physical_device_id &&
               a.source_id == b.source_id && a.session_id == b.session_id;
    };
    auto frontiers = s.checkpoint.dedupe_frontiers;
    for (const auto& t : s.tail) {
        auto it = std::find_if(frontiers.begin(), frontiers.end(),
            [&](const EventIdentity& f) { return same_source(f, t.event); });
        if (it == frontiers.end()) frontiers.push_back(t.event);
        else if (t.event.sequence > it->sequence) *it = t.event;
    }
    for (const auto& frontier : frontiers) {
        if (same_source(frontier, candidate.event)) {
            if (frontier.sequence == candidate.event.sequence) return CommitStatus::Committed;
            if (frontier.sequence > candidate.event.sequence) return CommitStatus::NotCommitted;
        }
    }
    for(const auto&t:s.tail)if(t.event==candidate.event)return CommitStatus::Committed;
    std::size_t pending_effect_count = s.checkpoint.pending_effects.size() + candidate.effects.size();
    for (const auto& t : s.tail) pending_effect_count += t.effects.size();
    if (pending_effect_count > kMaxPendingEffects) return CommitStatus::NotCommitted;
    if(s.last_ordinal-s.checkpoint.covered_ordinal>=4)return CommitStatus::NotCommitted;
    candidate.storage_epoch=epoch_;candidate.ordinal=s.last_ordinal+1;Bytes blob;if(!Codec::encode_transition(crypto_,key_,candidate,blob))return CommitStatus::NotCommitted;const auto slot=static_cast<std::size_t>((candidate.ordinal-1)%4);Bytes prior;bool found=false;if(!store_.read(trkey(slot),prior,found))return CommitStatus::StorageFault;
    if(found){
#if defined(GS_DURABLE_TEST_SLOT_REUSE)
        Transition old;if(!Codec::decode_transition(crypto_,key_,prior,old))return CommitStatus::StorageFault;std::array<Checkpoint,2> cps{};std::array<bool,2> valid{};for(std::size_t i=0;i<2;++i){Bytes b;bool f=false;if(!store_.read(cpkey(i),b,f))return CommitStatus::StorageFault;valid[i]=f&&Codec::decode_checkpoint(crypto_,key_,b,cps[i])&&cps[i].storage_epoch==epoch_;}if(!valid[0]||!valid[1]||old.ordinal>std::min(cps[0].covered_ordinal,cps[1].covered_ordinal))return CommitStatus::NotCommitted;
#else
        return CommitStatus::NotCommitted;
#endif
    }
    const bool wrote=found?store_.replace(trkey(slot),blob):store_.write_immutable(trkey(slot),blob);Bytes verify;bool vf=false;Transition decoded;if(store_.read(trkey(slot),verify,vf)&&vf&&verify==blob&&Codec::decode_transition(crypto_,key_,verify,decoded)&&decoded.ordinal==candidate.ordinal&&decoded.event==candidate.event)return wrote?CommitStatus::Committed:CommitStatus::AmbiguousResolvedCommitted;return wrote?CommitStatus::StorageFault:CommitStatus::NotCommitted;
}

bool DurableStore::checkpoint(const Checkpoint& input){
    RecoveryState s;if(!recover(s)||s.last_ordinal!=input.covered_ordinal||input.storage_epoch!=epoch_||input.generation<=s.checkpoint_generation)return false;Checkpoint cp=input;
    for (const auto& old_frontier : s.checkpoint.dedupe_frontiers) {
        const auto it = std::find_if(cp.dedupe_frontiers.begin(), cp.dedupe_frontiers.end(),
            [&](const EventIdentity& x) {
                return x.physical_device_id == old_frontier.physical_device_id &&
                       x.source_id == old_frontier.source_id &&
                       x.session_id == old_frontier.session_id;
            });
        if (it == cp.dedupe_frontiers.end()) cp.dedupe_frontiers.push_back(old_frontier);
    }
    auto same_source = [](const EventIdentity& a, const EventIdentity& b) {
        return a.physical_device_id == b.physical_device_id &&
               a.source_id == b.source_id && a.session_id == b.session_id;
    };
    for (const auto& t : s.tail) {
        auto it = std::find_if(cp.dedupe_frontiers.begin(), cp.dedupe_frontiers.end(),
            [&](const EventIdentity& x) { return same_source(x, t.event); });
        if (it == cp.dedupe_frontiers.end()) {
            if (cp.dedupe_frontiers.size() == kMaxDedupeFrontiers) return false;
            cp.dedupe_frontiers.push_back(t.event);
        } else if (t.event.sequence > it->sequence) {
            *it = t.event;
        }
    }
    if (cp.dedupe_frontiers.empty()) cp.dedupe_frontiers = s.checkpoint.dedupe_frontiers;
    Bytes blob;if(!Codec::encode_checkpoint(crypto_,key_,cp,blob))return false;
    std::array<Checkpoint,2> cps{};std::array<bool,2> valid{};for(std::size_t i=0;i<2;++i){Bytes b;bool f=false;if(!store_.read(cpkey(i),b,f))return false;valid[i]=f&&Codec::decode_checkpoint(crypto_,key_,b,cps[i])&&cps[i].storage_epoch==epoch_;}
    std::size_t inactive=!valid[0]?0:!valid[1]?1:(cps[0].generation<=cps[1].generation?0:1);
    (void)store_.replace(cpkey(inactive), blob);
    Bytes check;bool found=false;Checkpoint round;if(!store_.read(cpkey(inactive),check,found)||!found||check!=blob||!Codec::decode_checkpoint(crypto_,key_,check,round)||round.generation!=cp.generation)return false;
    Bytes selector;if(!encode_selector_blob(crypto_,key_,cp.generation,static_cast<std::uint8_t>(inactive),selector))return false;const std::size_t sidx=static_cast<std::size_t>(cp.generation%2);(void)store_.replace(selkey(sidx),selector);Bytes verify;bool sf=false;std::uint64_t g=0;std::uint8_t idx=0;return store_.read(selkey(sidx),verify,sf)&&sf&&verify==selector&&decode_selector_blob(crypto_,key_,verify,g,idx)&&g==cp.generation&&idx==inactive;
}

bool DurableStore::handoff_effects(const std::vector<EffectReference>& refs,const std::vector<Effect>& effects,std::uint64_t chunk_id,Checkpoint& cp){
    if (refs.empty() || refs.size() != effects.size() ||
        refs.size() > kMaxEffectsPerChunk ||
        cp.pending_chunks.size() >= kMaxCheckpointChunkRefs ||
        cp.pending_effects.size() + refs.size() > kMaxCheckpointEffectRefs) return false;
    PendingEffectChunk chunk;
    chunk.storage_epoch = epoch_; chunk.chunk_id = chunk_id;
    chunk.refs = refs; chunk.effects = effects;
    Bytes blob;
    if (!Codec::encode_chunk(crypto_, key_, chunk, blob)) return false;
    const auto k = "ef" + std::to_string(chunk_id);
    (void)store_.write_immutable(k, blob);
    Bytes check; bool found = false; PendingEffectChunk round;
    if (!store_.read(k, check, found) || !found || check != blob ||
        !Codec::decode_chunk(crypto_, key_, check, round) ||
        round.effects.size() != effects.size()) return false;
    for (std::size_t i = 0; i < effects.size(); ++i)
        if (!same(round.effects[i], effects[i])) return false;
    const auto chunk_ref_index = cp.pending_chunks.size();
    ChunkReference ref; ref.chunk_id = chunk_id; cp.pending_chunks.push_back(ref);
    for (std::size_t i = 0; i < refs.size(); ++i) {
        auto owned_ref = refs[i];
        owned_ref.location = static_cast<std::uint8_t>((chunk_ref_index << 2) | i);
        cp.pending_effects.push_back(owned_ref);
    }
    return cp.pending_chunks.size() <= kMaxCheckpointChunkRefs &&
           cp.pending_effects.size() <= kMaxCheckpointEffectRefs;
}
CommitStatus DurableStore::commit_bitmap(CompletionBitmap bm){
    bm.storage_epoch=epoch_;CompletionBitmap old;bool found=read_bitmap(bm.mapping_digest,old);if(found){if((bm.committed_bits|old.committed_bits)!=bm.committed_bits)return CommitStatus::NotCommitted;if(bm.committed_bits==old.committed_bits)return CommitStatus::Committed;bm.generation=old.generation+1;}else if(bm.generation==0)bm.generation=1;Bytes blob;if(!Codec::encode_bitmap(crypto_,key_,bm,blob))return CommitStatus::NotCommitted;Bytes a,b;bool fa=false,fb=false;if(!store_.read("bm0",a,fa)||!store_.read("bm1",b,fb))return CommitStatus::StorageFault;CompletionBitmap va,vb;const bool ga=fa&&Codec::decode_bitmap(crypto_,key_,a,va);const bool gb=fb&&Codec::decode_bitmap(crypto_,key_,b,vb);const std::size_t i=!ga?0:!gb?1:(va.generation<=vb.generation?0:1);const std::string k="bm"+std::to_string(i);bool wrote=store_.replace(k,blob);Bytes check;bool f=false;CompletionBitmap decoded;if(store_.read(k,check,f)&&f&&check==blob&&Codec::decode_bitmap(crypto_,key_,check,decoded)&&decoded.generation==bm.generation)return wrote?CommitStatus::Committed:CommitStatus::AmbiguousResolvedCommitted;return wrote?CommitStatus::StorageFault:CommitStatus::NotCommitted;
}
bool DurableStore::read_bitmap(const std::array<std::uint8_t,32>& digest,CompletionBitmap& out){bool found=false;for(const char*k:{"bm0","bm1"}){Bytes b;bool f=false;if(!store_.read(k,b,f))return false;if(!f)continue;CompletionBitmap bm;if(Codec::decode_bitmap(crypto_,key_,b,bm)&&bm.storage_epoch==epoch_&&bm.mapping_digest==digest&&(!found||bm.generation>out.generation)){out=bm;found=true;}}return found;}
bool DurableStore::read_pending_chunk(std::uint64_t chunk_id,PendingEffectChunk& out){Bytes blob;bool found=false;const auto key="ef"+std::to_string(chunk_id);return store_.read(key,blob,found)&&found&&Codec::decode_chunk(crypto_,key_,blob,out)&&out.storage_epoch==epoch_&&out.chunk_id==chunk_id;}

} // namespace gs::hub::durable
