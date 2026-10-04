#include "storage/durable_transition.hpp"
#include "storage/node_retirement_snapshot.hpp"

#include <algorithm>
#include <limits>

namespace gs::hub::durable {
namespace {
using security::Bytes;
constexpr std::uint8_t kSchema = 1;
constexpr std::uint8_t kTransitionLegacyOwnedSchema = 2;
constexpr std::uint8_t kTransitionSchema = 3;
constexpr std::uint8_t kCheckpointLegacySchema = 2;
constexpr std::uint8_t kCheckpointSchema = 3;
constexpr std::uint8_t kEvidenceSchema = 2;
constexpr std::size_t kMigrationManifestHeaderBytes = 18;
constexpr std::size_t kMigrationManifestBodyBytes = 184;
constexpr std::size_t kTransitionHeader = 72;
constexpr std::size_t kAeadOverhead = 28;
constexpr std::size_t kChunkHeader = 64;
constexpr std::size_t kEvidenceHeader = 32;
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

bool retirement_covers(const DedupeEvidenceEntry& entry,
                       const RetirementSnapshot& snapshot) {
    if (entry.enrollment_slot >= kMaxRetirementNodes ||
        (snapshot.occupancy_mask & (1U << entry.enrollment_slot)) == 0) return false;
    const auto& node = snapshot.nodes[entry.enrollment_slot];
    if (entry.enrollment_generation != node.enrollment_generation ||
        entry.origin_session > node.current_origin_session) return false;
    for (std::size_t i = 0; i < node.pending_count; ++i)
        if (node.pending[i].origin_session == entry.origin_session &&
            node.pending[i].sequence == entry.sequence) return false;
    return entry.origin_session < node.current_origin_session ||
        entry.sequence <= node.durable_admission_highwater;
}

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
bool nonzero(const std::uint8_t* p, std::size_t n) {
    return std::any_of(p, p + n, [](std::uint8_t b) { return b != 0; });
}
bool all_zero(const std::uint8_t* p, std::size_t n) {
    return std::all_of(p, p + n, [](std::uint8_t b) { return b == 0; });
}
bool same_manifest(const MigrationManifest& a, const MigrationManifest& b) {
    return a.epoch==b.epoch&&a.migration_id==b.migration_id&&a.phase==b.phase&&
        a.source_bank==b.source_bank&&a.source_generation==b.source_generation&&
        a.source_compound_digest==b.source_compound_digest&&
        a.registry_table_digest==b.registry_table_digest&&a.batch_family==b.batch_family&&
        a.source_key_id==b.source_key_id&&a.target_key_id==b.target_key_id&&
        a.source_child_digest==b.source_child_digest&&a.frontier==b.frontier&&
        a.target_root_generation==b.target_root_generation&&
        a.target_root_digest==b.target_root_digest&&
        a.source_live_tail_count==b.source_live_tail_count&&
        a.normal_publication==b.normal_publication&&
        a.virtual_legacy_source==b.virtual_legacy_source&&
        a.cancelled_normal_publication==b.cancelled_normal_publication;
}
bool same_batch_source(const MigrationManifest& a, const MigrationManifest& b) {
    return a.epoch==b.epoch&&a.migration_id==b.migration_id&&
        a.source_bank==b.source_bank&&a.source_generation==b.source_generation&&
        a.source_compound_digest==b.source_compound_digest&&
        a.registry_table_digest==b.registry_table_digest&&a.batch_family==b.batch_family&&
        a.source_key_id==b.source_key_id&&a.target_key_id==b.target_key_id&&
        a.source_child_digest==b.source_child_digest&&a.frontier==b.frontier&&
        a.source_live_tail_count==b.source_live_tail_count&&
        a.normal_publication==b.normal_publication&&
        a.virtual_legacy_source==b.virtual_legacy_source;
}
bool legal_manifest_successor(const MigrationManifest& old, const MigrationManifest& next) {
    if (old.epoch!=next.epoch || old.migration_id!=next.migration_id ||
        old.registry_table_digest!=next.registry_table_digest) return false;
    if (old.phase==MigrationPhase::BatchDone && next.phase==MigrationPhase::Prepared &&
        old.frontier<128 && next.frontier==static_cast<std::uint16_t>(old.frontier+1) &&
        next.source_bank==static_cast<std::uint8_t>(1U-old.source_bank) &&
        next.source_generation==old.target_root_generation &&
        next.source_compound_digest==old.target_root_digest &&
        next.batch_family!=MigrationBatchFamily::None &&
        !next.normal_publication && !next.virtual_legacy_source) return true;
    // Ordinary authenticated mutations use the same completed frontier. The
    // selector lineage is the exact last published root, not a generation
    // search over otherwise valid checkpoint banks.
    if (old.phase==MigrationPhase::Activated && next.phase==MigrationPhase::Prepared &&
        next.normal_publication && next.frontier==old.frontier &&
        next.source_generation>old.target_root_generation &&
        next.source_bank==static_cast<std::uint8_t>(1U-old.source_bank) &&
        next.source_compound_digest==old.target_root_digest &&
        next.batch_family!=MigrationBatchFamily::None &&
        !next.virtual_legacy_source) return true;
    if (old.frontier!=next.frontier || !same_batch_source(old,next)) return false;
    const auto a=static_cast<std::uint8_t>(old.phase);
    const auto b=static_cast<std::uint8_t>(next.phase);
    if (b==a+1 && b<=static_cast<std::uint8_t>(MigrationPhase::BatchDone)) {
        if (next.phase==MigrationPhase::TargetVerified) {
            if (old.phase!=MigrationPhase::Copying || next.target_root_generation==0 ||
                !nonzero(next.target_root_digest.data(),32)) return false;
            if (old.normal_publication) {
                const bool unchanged_plan = old.target_root_generation==next.target_root_generation &&
                    old.target_root_digest==next.target_root_digest;
                const bool cancelled = !old.cancelled_normal_publication &&
                    next.cancelled_normal_publication &&
                    (next.batch_family==MigrationBatchFamily::FinalActivation ||
                     (next.source_key_id!=old.source_key_id &&
                      next.target_key_id!=old.target_key_id));
                return unchanged_plan || cancelled;
            }
            return !old.virtual_legacy_source || next.virtual_legacy_source;
        }
        if (next.cancelled_normal_publication!=old.cancelled_normal_publication) return false;
        return old.target_root_generation==next.target_root_generation &&
            old.target_root_digest==next.target_root_digest;
    }
    return old.phase==MigrationPhase::BatchDone&&next.phase==MigrationPhase::Activated&&
        same_batch_source(old,next)&&old.target_root_generation==next.target_root_generation&&
        old.target_root_digest==next.target_root_digest &&
        old.cancelled_normal_publication==next.cancelled_normal_publication;
}
bool valid_migration_manifest(const MigrationManifest& m) {
    const auto phase = static_cast<std::uint8_t>(m.phase);
    const auto family = static_cast<std::uint8_t>(m.batch_family);
    if (m.epoch == 0 || all_zero(m.migration_id.data(), m.migration_id.size()) ||
        phase == 0 || phase > static_cast<std::uint8_t>(MigrationPhase::Activated) ||
        m.source_bank > 1 || m.source_generation == 0 || m.frontier == 0 ||
        m.frontier > 128 || m.source_live_tail_count > 4 ||
        all_zero(m.source_compound_digest.data(), 32) ||
        all_zero(m.registry_table_digest.data(), 32) || family == 0 || family > 4)
        return false;
    if (m.cancelled_normal_publication && !m.normal_publication) return false;
    if (m.virtual_legacy_source && (m.normal_publication || m.source_bank != 0 ||
        m.source_generation != 1 || m.frontier != 1)) return false;
    if (m.normal_publication && m.frontier == 0) return false;
    if (m.source_key_id != 0 && m.source_key_id == m.target_key_id) return false;
    const bool target_required = phase >= static_cast<std::uint8_t>(MigrationPhase::TargetVerified);
    const bool normal_plan_required=m.normal_publication &&
        phase<=static_cast<std::uint8_t>(MigrationPhase::Copying);
    if (target_required || normal_plan_required) {
        if (m.target_root_generation == 0 ||
            all_zero(m.target_root_digest.data(), m.target_root_digest.size())) return false;
    } else if (m.target_root_generation != 0 ||
               !all_zero(m.target_root_digest.data(), m.target_root_digest.size())) {
        return false;
    }
    if (m.batch_family == MigrationBatchFamily::FinalActivation &&
        (m.source_key_id != 0 || m.target_key_id != 0)) return false;
    if (m.batch_family == MigrationBatchFamily::FinalActivation &&
        !all_zero(m.source_child_digest.data(),m.source_child_digest.size())) return false;
    if (m.batch_family != MigrationBatchFamily::FinalActivation &&
        all_zero(m.source_child_digest.data(),m.source_child_digest.size())) return false;
    if (m.batch_family == MigrationBatchFamily::TailPair) {
        if (m.source_generation == std::numeric_limits<std::uint64_t>::max()) return false;
        const auto next_generation=m.source_generation+1U;
        if (next_generation >= 0x8000000000000000ULL || next_generation >
            (std::numeric_limits<std::uint64_t>::max() >> 8) ||
            m.source_key_id != (0x8000000000000000ULL | next_generation) ||
            m.target_key_id != (next_generation << 8 | 1U)) return false;
    }
    if (m.cancelled_normal_publication && phase <
        static_cast<std::uint8_t>(MigrationPhase::TargetVerified)) return false;
    return true;
}
void encode_effect(Writer& w,const Effect& e){w.raw(e.id.data(),e.id.size());w.u16(static_cast<std::uint16_t>(e.kind));w.u16(static_cast<std::uint16_t>(e.payload.size()));w.raw(e.payload);}
bool decode_effect(Reader& r,Effect& e){std::uint16_t kind=0,n=0;if(!r.raw(e.id.data(),e.id.size())||!r.u16(kind)||!r.u16(n)||n>kMaxEffectPayloadBytes||!r.room(n))return false;e.kind=kind;e.payload.assign(r.b.begin()+r.p,r.b.begin()+r.p+n);r.p+=n;return true;}
} // namespace

bool EventIdentity::operator==(const EventIdentity& o)const{return physical_device_id==o.physical_device_id&&source_id==o.source_id&&session_id==o.session_id&&sequence==o.sequence;}
bool EventIdentity::operator<(const EventIdentity& o)const{return std::tie(physical_device_id,source_id,session_id,sequence)<std::tie(o.physical_device_id,o.source_id,o.session_id,o.sequence);}
bool ReportSnapshotReference::valid() const {
    return bank < 3 && generation != 0 && nonzero(digest.data(), digest.size());
}

bool Codec::encode_transition(security::CommissioningCrypto& c,const security::Key32& key,const Transition& t,Bytes& out){
    out.clear();if(t.storage_epoch==0||t.ordinal==0||t.event.physical_device_id.empty()||t.event.source_id.empty()||t.event.session_id==0||t.event.sequence==0||t.causal_input.size()>kMaxCausalInputBytes||t.decision.size()>kMaxDecisionBytes||t.effects.size()>kMaxEffectsPerTransition||!valid_effects(t.effects)||static_cast<unsigned>(t.type)<1||static_cast<unsigned>(t.type)>4)return false;
    if(t.type==TransitionType::Event&&(!t.registry_owner_domain||
       t.enrollment_slot>=kMaxRetirementNodes||t.enrollment_generation==0||
       !t.event_digest_present||
       std::all_of(t.event_digest.begin(),t.event_digest.end(),[](std::uint8_t b){return b==0;})))return false;
    Writer event; if(!encode_identity(event,t.event))return false;event.u8(t.enrollment_slot);event.u32(t.enrollment_generation);event.raw(t.event_digest.data(),t.event_digest.size());event.raw(t.causal_input);if(event.b.size()>kMaxCausalInputBytes)return false;
    Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GDT1"),4);w.u8(kTransitionSchema);w.u32(t.storage_epoch);w.u64(t.ordinal);w.u32(t.config_version);w.raw(t.config_hash.data(),32);w.u8(static_cast<std::uint8_t>(t.type));w.u16(static_cast<std::uint16_t>(event.b.size()));w.u16(static_cast<std::uint16_t>(t.decision.size()));w.u8(static_cast<std::uint8_t>(t.effects.size()));
    while(w.b.size()<kTransitionHeader)w.u8(0);
    w.raw(event.b);w.raw(t.decision);
    for(const auto& e:t.effects){if(e.kind>65535||e.payload.size()>kMaxEffectPayloadBytes)return false;encode_effect(w,e);}
    if(w.b.size()+kAeadOverhead>kMaxTransitionBytes)return false;
    return seal(c,key,"hub-transition-v1",w.b,out,kMaxTransitionBytes);
}
bool Codec::decode_transition(security::CommissioningCrypto& c,const security::Key32& key,const Bytes& blob,Transition& t){
    Bytes p;if(!open(c,key,"hub-transition-v1",blob,p,kMaxTransitionBytes)||p.size()<kTransitionHeader)return false;Reader r{p};std::uint8_t magic[4]{},ver=0,type=0,count=0;std::uint16_t event_len=0,decision_len=0;
    if(!r.raw(magic,4)||!std::equal(magic,magic+4,reinterpret_cast<const std::uint8_t*>("GDT1"))||!r.u8(ver)||(ver!=kSchema&&ver!=kTransitionLegacyOwnedSchema&&ver!=kTransitionSchema)||!r.u32(t.storage_epoch)||!r.u64(t.ordinal)||!r.u32(t.config_version)||!r.raw(t.config_hash.data(),32)||!r.u8(type)||type<1||type>4||!r.u16(event_len)||event_len>kMaxCausalInputBytes||!r.u16(decision_len)||decision_len>kMaxDecisionBytes||!r.u8(count)||count>kMaxEffectsPerTransition)return false;
    for (std::size_t i = r.p; i < kTransitionHeader; ++i) {
        if (p[i] != 0) return false;
    }
    r.p = kTransitionHeader;
    if (!r.room(event_len + decision_len)) return false;
    Bytes ev(p.begin() + r.p, p.begin() + r.p + event_len);
    r.p += event_len;
    Reader er{ev};
    if (!decode_identity(er, t.event)) return false;
    if (ver >= kTransitionLegacyOwnedSchema) {
        if (!er.u8(t.enrollment_slot) || !er.u32(t.enrollment_generation) ||
            !er.raw(t.event_digest.data(), t.event_digest.size())) return false;
        t.event_digest_present = true;
    } else {
        t.enrollment_slot = 0;
        t.enrollment_generation = 0;
        t.event_digest.fill(0);
        t.event_digest_present = false;
    }
    t.registry_owner_domain = ver >= kTransitionSchema;
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
    if(t.type==TransitionType::Event&&t.registry_owner_domain&&
       (t.enrollment_slot>=kMaxRetirementNodes||t.enrollment_generation==0))return false;
    if(t.type==TransitionType::Event&&t.event_digest_present&&
       (t.enrollment_slot>=kMaxRetirementNodes||t.enrollment_generation==0||
        std::all_of(t.event_digest.begin(),t.event_digest.end(),[](std::uint8_t b){return b==0;})))return false;
    return t.storage_epoch != 0 && t.ordinal != 0 && r.p == p.size() && valid_effects(t.effects);
}

bool Codec::encode_checkpoint(security::CommissioningCrypto& c,const security::Key32& key,const Checkpoint& cp,Bytes& out){
    out.clear();if(cp.storage_epoch==0||cp.generation==0||cp.reducer_state.size()>kMaxCheckpointBytes||cp.pending_effects.size()>kMaxCheckpointEffectRefs||cp.pending_chunks.size()>kMaxCheckpointChunkRefs||cp.dedupe_evidence_chunks.size()>kMaxDedupeEvidenceRefs||cp.legacy_dedupe_unverified||cp.migration_frontier>128)return false;
    if(cp.protected_live_tail_count>4)return false;
    if(cp.registry_owner_domain){if(cp.migration_frontier==0||!nonzero(cp.registry_table_digest.data(),32))return false;}
    else if(cp.migration_frontier!=0||!all_zero(cp.registry_table_digest.data(),32)||
            cp.allow_legacy_event_tail||cp.allow_legacy_event_slots||cp.protected_live_tail_count!=0)return false;
    if(cp.migration_view&&!cp.registry_owner_domain)return false;
    Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GCP1"),4);w.u8(kCheckpointSchema);w.u32(cp.storage_epoch);w.u64(cp.generation);w.u64(cp.covered_ordinal);w.u32(cp.config_version);w.raw(cp.config_hash.data(),32);w.u16(static_cast<std::uint16_t>(cp.reducer_state.size()));w.raw(cp.reducer_state);w.u8(static_cast<std::uint8_t>(cp.pending_effects.size()));for(const auto& ref:cp.pending_effects){w.u64(ref.ordinal);w.u8(ref.index);w.u8(ref.location);}w.u8(static_cast<std::uint8_t>(cp.pending_chunks.size()));for(const auto& ref:cp.pending_chunks)w.u64(ref.chunk_id);w.u8(static_cast<std::uint8_t>(cp.dedupe_evidence_chunks.size()));for(const auto& ref:cp.dedupe_evidence_chunks){if(!nonzero(ref.digest.data(),ref.digest.size()))return false;w.u64(ref.chunk_id);w.raw(ref.digest.data(),ref.digest.size());}w.u8(cp.report_snapshot.has_value()?1:0);if(cp.report_snapshot){if(!cp.report_snapshot->valid())return false;w.u8(cp.report_snapshot->bank);w.u64(cp.report_snapshot->generation);w.raw(cp.report_snapshot->digest.data(),cp.report_snapshot->digest.size());}
    w.raw(cp.registry_table_digest.data(),cp.registry_table_digest.size());w.u16(cp.migration_frontier);
    const std::uint8_t flags=static_cast<std::uint8_t>((cp.registry_owner_domain?1U:0U)|
        (cp.migration_view?2U:0U)|(cp.allow_legacy_event_tail?4U:0U)|
        (cp.allow_legacy_event_slots?8U:0U)|(cp.protected_live_tail_count<<4));w.u8(flags);
    return seal(c,key,"hub-checkpoint-v1",w.b,out,kMaxCheckpointBytes);
}
bool Codec::decode_checkpoint(security::CommissioningCrypto& c,const security::Key32& key,const Bytes& blob,Checkpoint& cp){
    Bytes p;if(!open(c,key,"hub-checkpoint-v1",blob,p,kMaxCheckpointBytes))return false;Reader r{p};std::uint8_t magic[4]{},ver=0,n8=0;std::uint16_t n16=0;
    if (!r.raw(magic, 4) ||
        !std::equal(magic, magic + 4, reinterpret_cast<const std::uint8_t*>("GCP1")) ||
        !r.u8(ver) || (ver != kSchema && ver != kCheckpointLegacySchema && ver != kCheckpointSchema) || !r.u32(cp.storage_epoch) ||
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
    cp.dedupe_evidence_chunks.clear();cp.report_snapshot.reset();cp.legacy_dedupe_unverified=false;
    if (!r.u8(n8)) return false;
    if(ver==kSchema){
        if(n8>10)return false;
        for(unsigned i=0;i<n8;++i){EventIdentity ignored;if(!decode_identity(r,ignored))return false;}
        cp.legacy_dedupe_unverified=n8!=0;
    }else{
        if(n8>kMaxDedupeEvidenceRefs)return false;
        for(unsigned i=0;i<n8;++i){DedupeEvidenceReference ref;if(!r.u64(ref.chunk_id)||!r.raw(ref.digest.data(),ref.digest.size())||!nonzero(ref.digest.data(),ref.digest.size()))return false;cp.dedupe_evidence_chunks.push_back(ref);}
        std::uint8_t has_report=0;if(!r.u8(has_report)||has_report>1)return false;
        if(has_report){ReportSnapshotReference ref;if(!r.u8(ref.bank)||!r.u64(ref.generation)||!r.raw(ref.digest.data(),ref.digest.size())||!ref.valid())return false;cp.report_snapshot=ref;}
    }
    cp.registry_table_digest.fill(0);cp.migration_frontier=0;cp.migration_view=false;
    cp.registry_owner_domain=false;cp.allow_legacy_event_tail=false;
    cp.allow_legacy_event_slots=false;cp.protected_live_tail_count=0;
    if(ver==kCheckpointSchema){
        std::uint8_t flags=0;
        if(!r.raw(cp.registry_table_digest.data(),cp.registry_table_digest.size())||
           !r.u16(cp.migration_frontier)||!r.u8(flags)||(flags&0x80U)!=0||cp.migration_frontier>128)return false;
        cp.registry_owner_domain=(flags&1U)!=0;cp.migration_view=(flags&2U)!=0;
        cp.allow_legacy_event_tail=(flags&4U)!=0;cp.allow_legacy_event_slots=(flags&8U)!=0;
        cp.protected_live_tail_count=static_cast<std::uint8_t>((flags>>4)&7U);
        if(cp.protected_live_tail_count>4)return false;
        if(cp.registry_owner_domain){if(cp.migration_frontier==0||!nonzero(cp.registry_table_digest.data(),32))return false;}
        else if(cp.migration_frontier!=0||!all_zero(cp.registry_table_digest.data(),32)||
                cp.allow_legacy_event_tail||cp.allow_legacy_event_slots||cp.protected_live_tail_count!=0)return false;
        if(cp.migration_view&&!cp.registry_owner_domain)return false;
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

bool Codec::encode_evidence_chunk(security::CommissioningCrypto& c,const security::Key32& key,
                                  const DedupeEvidenceChunk& chunk,Bytes& out){
    out.clear();if(chunk.storage_epoch==0||chunk.chunk_id==0||chunk.count==0||chunk.count>chunk.entries.size()||!chunk.registry_owner_domain)return false;
    Writer w;w.raw(reinterpret_cast<const std::uint8_t*>("GDE1"),4);w.u8(kEvidenceSchema);w.u32(chunk.storage_epoch);w.u64(chunk.chunk_id);w.u8(chunk.count);
    for(std::size_t i=0;i<chunk.count;++i){const auto&e=chunk.entries[i];if(e.enrollment_slot>=kMaxRetirementNodes||e.enrollment_generation==0||e.origin_session==0||e.sequence==0||!nonzero(e.digest.data(),e.digest.size()))return false;w.u8(e.enrollment_slot);w.u32(e.enrollment_generation);w.u64(e.origin_session);w.u64(e.sequence);w.raw(e.digest.data(),e.digest.size());}
    return seal(c,key,"hub-dedupe-evidence-v1",w.b,out,kMaxDedupeEvidenceChunkBytes);
}
bool Codec::decode_evidence_chunk(security::CommissioningCrypto& c,const security::Key32& key,
                                  const Bytes& blob,DedupeEvidenceChunk& chunk){
    Bytes p;if(!open(c,key,"hub-dedupe-evidence-v1",blob,p,kMaxDedupeEvidenceChunkBytes))return false;Reader r{p};std::uint8_t magic[4]{},ver=0,count=0;
    if(!r.raw(magic,4)||!std::equal(magic,magic+4,reinterpret_cast<const std::uint8_t*>("GDE1"))||!r.u8(ver)||(ver!=kSchema&&ver!=kEvidenceSchema)||!r.u32(chunk.storage_epoch)||!r.u64(chunk.chunk_id)||!r.u8(count)||count==0||count>chunk.entries.size())return false;
    chunk.registry_owner_domain=ver==kEvidenceSchema;
    chunk.count=count;for(std::size_t i=0;i<count;++i){auto&e=chunk.entries[i];if(!r.u8(e.enrollment_slot)||!r.u32(e.enrollment_generation)||!r.u64(e.origin_session)||!r.u64(e.sequence)||!r.raw(e.digest.data(),e.digest.size())||e.enrollment_slot>=kMaxRetirementNodes||e.enrollment_generation==0||e.origin_session==0||e.sequence==0||!nonzero(e.digest.data(),e.digest.size()))return false;}
    return r.p==p.size()&&chunk.storage_epoch!=0&&chunk.chunk_id!=0;
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

bool Codec::encode_migration_manifest(security::CommissioningCrypto& crypto,
        const security::Key32& key, const MigrationManifest& manifest, Bytes& blob) {
    blob.clear();
    if (!valid_migration_manifest(manifest)) return false;
    Writer header;
    header.raw(reinterpret_cast<const std::uint8_t*>("GMM2"),4);
    header.u8(2);
    const auto flags=static_cast<std::uint8_t>(manifest.source_bank |
        (manifest.source_live_tail_count<<1) |
        (manifest.normal_publication?0x10U:0U) |
        (manifest.virtual_legacy_source?0x20U:0U) |
        (manifest.cancelled_normal_publication?0x40U:0U));
    header.u8(flags);
    security::Nonce12 nonce{};
    if (!crypto.random_bytes(nonce.data(),nonce.size())) return false;
    header.raw(nonce.data(),nonce.size());
    if (header.b.size()!=kMigrationManifestHeaderBytes) return false;
    Writer body;
    body.u32(manifest.epoch);body.raw(manifest.migration_id.data(),manifest.migration_id.size());
    body.u8(static_cast<std::uint8_t>(manifest.phase));body.u64(manifest.source_generation);
    body.raw(manifest.source_compound_digest.data(),32);
    body.raw(manifest.registry_table_digest.data(),32);
    body.u8(static_cast<std::uint8_t>(manifest.batch_family));
    body.u64(manifest.source_key_id);body.u64(manifest.target_key_id);
    body.raw(manifest.source_child_digest.data(),32);body.u16(manifest.frontier);
    body.u64(manifest.target_root_generation);body.raw(manifest.target_root_digest.data(),32);
    if (body.b.size()!=kMigrationManifestBodyBytes) return false;
    static constexpr char kManifestAad[]="hub-enrollment-migration-v2";
    Bytes aad(kManifestAad,kManifestAad+sizeof(kManifestAad)-1);
    aad.insert(aad.end(),header.b.begin(),header.b.end());
    security::GcmTag tag{};Bytes cipher;
    if (!crypto.seal_aes256_gcm(key,nonce,aad,body.b,cipher,tag) ||
        cipher.size()!=kMigrationManifestBodyBytes) return false;
    blob=header.b;blob.insert(blob.end(),cipher.begin(),cipher.end());
    blob.insert(blob.end(),tag.begin(),tag.end());
    return blob.size()==kMigrationManifestBankBytes;
}

bool Codec::decode_migration_manifest(security::CommissioningCrypto& crypto,
        const security::Key32& key, const Bytes& blob, MigrationManifest& manifest) {
    if (blob.size()!=kMigrationManifestBankBytes) return false;
    if (!std::equal(blob.begin(),blob.begin()+4,
                    reinterpret_cast<const std::uint8_t*>("GMM2")) ||
        blob[4]!=2 || (blob[5]&0x80U)!=0 || ((blob[5]>>1)&7U)>4) return false;
    Bytes header(blob.begin(),blob.begin()+kMigrationManifestHeaderBytes);
    security::Nonce12 nonce{};std::copy_n(blob.begin()+6,nonce.size(),nonce.begin());
    security::GcmTag tag{};std::copy_n(blob.end()-tag.size(),tag.size(),tag.begin());
    Bytes cipher(blob.begin()+kMigrationManifestHeaderBytes,blob.end()-tag.size());
    static constexpr char kManifestAad[]="hub-enrollment-migration-v2";
    Bytes aad(kManifestAad,kManifestAad+sizeof(kManifestAad)-1);
    aad.insert(aad.end(),header.begin(),header.end());
    Bytes plain;
    if (!crypto.open_aes256_gcm(key,nonce,aad,cipher,tag,plain) ||
        plain.size()!=kMigrationManifestBodyBytes) return false;
    Reader r{plain};std::uint8_t phase=0,family=0;
    manifest={};manifest.source_bank=static_cast<std::uint8_t>(blob[5]&1U);
    manifest.source_live_tail_count=static_cast<std::uint8_t>((blob[5]>>1)&7U);
    manifest.normal_publication=(blob[5]&0x10U)!=0;
    manifest.virtual_legacy_source=(blob[5]&0x20U)!=0;
    manifest.cancelled_normal_publication=(blob[5]&0x40U)!=0;
    const bool okay=r.u32(manifest.epoch)&&r.raw(manifest.migration_id.data(),16)&&
        r.u8(phase)&&r.u64(manifest.source_generation)&&
        r.raw(manifest.source_compound_digest.data(),32)&&
        r.raw(manifest.registry_table_digest.data(),32)&&r.u8(family)&&
        r.u64(manifest.source_key_id)&&r.u64(manifest.target_key_id)&&
        r.raw(manifest.source_child_digest.data(),32)&&r.u16(manifest.frontier)&&
        r.u64(manifest.target_root_generation)&&r.raw(manifest.target_root_digest.data(),32)&&
        r.p==plain.size();
    if (!okay || phase==0 || phase>static_cast<std::uint8_t>(MigrationPhase::Activated) ||
        family==0 || family>static_cast<std::uint8_t>(MigrationBatchFamily::FinalActivation)) {
        crypto.secure_zero(plain.data(),plain.size());return false;
    }
    manifest.phase=static_cast<MigrationPhase>(phase);
    manifest.batch_family=static_cast<MigrationBatchFamily>(family);
    const bool valid=valid_migration_manifest(manifest);
    crypto.secure_zero(plain.data(),plain.size());
    return valid;
}

MigrationManifestRepository::MigrationManifestRepository(BlobStore& store,
        security::CommissioningCrypto& crypto,const security::Key32& key,std::uint32_t epoch)
    :store_(store),crypto_(crypto),key_(key),epoch_(epoch){}
MigrationManifestRepository::~MigrationManifestRepository(){
    crypto_.secure_zero(key_.data(),key_.size());
}

MigrationManifestStatus MigrationManifestRepository::load(MigrationManifest& out,
        std::uint8_t* selected_bank) {
    out={};if(selected_bank)*selected_bank=0xff;
    if(epoch_==0)return MigrationManifestStatus::Corrupt;
    std::array<MigrationManifest,2> records{};std::array<bool,2> present{};
    for(std::uint8_t i=0;i<2;++i){Bytes blob;bool found=false;
        if(!store_.read("mig"+std::to_string(i),blob,found))return MigrationManifestStatus::IoError;
        present[i]=found;if(!found)continue;
        if(!Codec::decode_migration_manifest(crypto_,key_,blob,records[i])||records[i].epoch!=epoch_)
            return MigrationManifestStatus::Corrupt;
    }
    if(!present[0]&&!present[1])return MigrationManifestStatus::Missing;
    std::uint8_t selected=present[0]?0:1;
    if(present[0]&&present[1]){
        const auto& a=records[0];const auto& b=records[1];
        if(a.epoch!=b.epoch||a.migration_id!=b.migration_id||
           a.registry_table_digest!=b.registry_table_digest)return MigrationManifestStatus::Conflict;
        if(same_manifest(a,b))selected=1;
        else {
            const bool ab=legal_manifest_successor(a,b);
            const bool ba=legal_manifest_successor(b,a);
            if(ab==ba)return MigrationManifestStatus::Conflict;
            selected=ab?1:0;
        }
    }
    out=records[selected];if(selected_bank)*selected_bank=selected;
    return MigrationManifestStatus::Ready;
}

bool MigrationManifestRepository::advance(const MigrationManifest& next) {
    if(!valid_migration_manifest(next)||next.epoch!=epoch_)return false;
    MigrationManifest current;std::uint8_t current_bank=0xff;
    const auto status=load(current,&current_bank);
    if(status==MigrationManifestStatus::IoError||status==MigrationManifestStatus::Corrupt||
       status==MigrationManifestStatus::Conflict)return false;
    std::uint8_t target_bank=0;
    if(status==MigrationManifestStatus::Missing){
        if(next.phase!=MigrationPhase::Prepared||next.frontier!=1)return false;
    }else{
        if(same_manifest(current,next))return true;
        if(!legal_manifest_successor(current,next))return false;
        target_bank=static_cast<std::uint8_t>(1U-current_bank);
    }
    Bytes blob;if(!Codec::encode_migration_manifest(crypto_,key_,next,blob)||
                 blob.size()!=kMigrationManifestBankBytes)return false;
    const bool write_reported_success=store_.replace("mig"+std::to_string(target_bank),blob);
    Bytes verify;bool found=false;MigrationManifest decoded;
    if(!store_.read("mig"+std::to_string(target_bank),verify,found)||!found||verify!=blob||
       !Codec::decode_migration_manifest(crypto_,key_,verify,decoded)||!same_manifest(decoded,next))
        return false;
    MigrationManifest selected;
    if(load(selected,nullptr)!=MigrationManifestStatus::Ready||!same_manifest(selected,next))return false;
    // Readback is authoritative when replace reports an error after persisting.
    (void)write_reported_success;
    return true;
}

bool MemoryBlobStore::read(const std::string& k,Bytes& v,bool& f){auto i=values_.find(k);f=i!=values_.end();v=f?i->second:Bytes{};return true;}
bool MemoryBlobStore::write_immutable(const std::string& k,const Bytes& v){return perform(k,v,true);}
bool MemoryBlobStore::replace(const std::string& k,const Bytes& v){return perform(k,v,false);}
bool MemoryBlobStore::erase_if_equals(const std::string& k,const Bytes& expected){
    auto i=values_.find(k);
    if(i==values_.end())return true;
    if(i->second!=expected)return false;
    ++write_count_;
    if(writes_before_fault_!=0){--writes_before_fault_;}
    else{
        const FaultMode mode=next_fault_;
        next_fault_=FaultMode::None;
        if(mode==FaultMode::FailBeforeWrite||mode==FaultMode::PartialWrite)return false;
        values_.erase(i);
        return mode!=FaultMode::PersistThenFail&&mode!=FaultMode::PowerLossAfterPersist;
    }
    values_.erase(i);
    return true;
}
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
    state={};state.storage_epoch=epoch_;
    std::array<Checkpoint,2> cps{};std::array<bool,2> present{},valid{};
    std::array<Bytes,2> cp_blobs{};
    for(std::size_t i=0;i<2;++i){Bytes b;bool found=false;
        if(!store_.read(cpkey(i),b,found))return false;
        present[i]=found;
        if(found)cp_blobs[i]=b;
        if(found)valid[i]=Codec::decode_checkpoint(crypto_,key_,b,cps[i])&&cps[i].storage_epoch==epoch_;
    }
    std::array<bool,2> selector_present{},selector_valid{};
    std::array<std::uint64_t,2> selector_generation{};
    std::array<std::uint8_t,2> selector_bank{};
    std::uint64_t selected_selector_generation=0;std::uint8_t selected_selector_bank=0;
    bool have_selector=false;
    for(std::size_t i=0;i<2;++i){Bytes b;bool found=false;
        if(!store_.read(selkey(i),b,found))return false;
        selector_present[i]=found;
        if(!found)continue;
        const bool decoded=decode_selector_blob(crypto_,key_,b,selector_generation[i],selector_bank[i]);
        selector_valid[i]=decoded&&valid[selector_bank[i]]&&
            cps[selector_bank[i]].generation==selector_generation[i];
        if(selector_valid[i]&&(!have_selector||selector_generation[i]>selected_selector_generation)){
            selected_selector_generation=selector_generation[i];
            selected_selector_bank=selector_bank[i];have_selector=true;
        }
    }
    MigrationManifest manifest;MigrationManifestRepository manifests(store_,crypto_,key_,epoch_);
    const auto manifest_status=manifests.load(manifest,nullptr);
    if(manifest_status==MigrationManifestStatus::IoError||
       manifest_status==MigrationManifestStatus::Corrupt||
       manifest_status==MigrationManifestStatus::Conflict)return false;
    int selected=-1;
    if(manifest_status==MigrationManifestStatus::Ready){
        if(manifest.phase<=MigrationPhase::TargetVerified){
            const auto source=manifest.source_bank;
            if(manifest.virtual_legacy_source||!valid[source]||
               cps[source].generation!=manifest.source_generation)return false;
            std::array<std::uint8_t,32> digest{};
            bool source_selector=false;
            for(std::size_t i=0;i<2;++i)
                source_selector=source_selector||(selector_valid[i]&&selector_bank[i]==source&&
                    selector_generation[i]==manifest.source_generation);
            if(!source_selector||!compound_root_digest(source,digest,
                    manifest.source_live_tail_count)||digest!=manifest.source_compound_digest)return false;
            selected=source;
        }else if(manifest.phase<MigrationPhase::Activated){
            const auto target=static_cast<std::uint8_t>(1U-manifest.source_bank);
            if(!valid[target]||cps[target].generation!=manifest.target_root_generation||
               !cps[target].registry_owner_domain||
               cps[target].registry_table_digest!=manifest.registry_table_digest||
               cps[target].migration_frontier!=manifest.frontier)return false;
            std::array<std::uint8_t,32> digest{};
            if(!compound_root_digest(target,digest)||digest!=manifest.target_root_digest)return false;
            bool selector_published=false;
            for(std::size_t i=0;i<2;++i){
                selector_published=selector_published||
                    (selector_valid[i]&&selector_bank[i]==target&&
                     selector_generation[i]==manifest.target_root_generation);
            }
            if(!selector_published)return false;
            if(manifest.phase>=MigrationPhase::Cleanup){
                std::array<std::uint8_t,32> shadow_digest{};
                if(!valid[manifest.source_bank]||
                   cp_blobs[manifest.source_bank]!=cp_blobs[target]||
                   !compound_root_digest(manifest.source_bank,shadow_digest)||
                   shadow_digest!=manifest.target_root_digest)return false;
            }
            selected=target;
        }else{
            if(!have_selector)return false;
            bool selected_authorized=false;
            for(std::size_t i=0;i<2;++i){
                if(!selector_valid[i])continue; // A valid, stale selector is not authority.
                const auto candidate=selector_bank[i];
                if(!valid[candidate]||!cps[candidate].registry_owner_domain||
                   cps[candidate].migration_view||
                   cps[candidate].registry_table_digest!=manifest.registry_table_digest||
                   cps[candidate].migration_frontier!=manifest.frontier)continue;
                std::array<std::uint8_t,32> digest{};
                if(!compound_root_digest(candidate,digest)||digest!=manifest.target_root_digest)
                    continue;
                if(selector_generation[i]!=manifest.target_root_generation)return false;
                selected=candidate;selected_authorized=true;
            }
            if(!selected_authorized)return false;
            if(!valid[0]||!valid[1]||cp_blobs[0]!=cp_blobs[1])return false;
            std::array<std::uint8_t,32> a{},b{};
            if(cps[0].generation!=manifest.target_root_generation||
               cps[1].generation!=manifest.target_root_generation||
               !compound_root_digest(0,a)||!compound_root_digest(1,b)||
               a!=manifest.target_root_digest||b!=manifest.target_root_digest)return false;
        }
    }else{
        if(have_selector)selected=selected_selector_bank;
        else if(present[0]||present[1]||selector_present[0]||selector_present[1])return false;
    }
    std::uint64_t boundary=0;
    if(selected>=0){
        state.checkpoint=cps[static_cast<std::size_t>(selected)];
        state.checkpoint_generation=state.checkpoint.generation;boundary=state.checkpoint.covered_ordinal;
        if(state.checkpoint.legacy_dedupe_unverified)return false;
        for(const auto& ref:state.checkpoint.dedupe_evidence_chunks){
            DedupeEvidenceChunk chunk;if(!read_evidence_chunk(ref,chunk)||
                (!state.checkpoint.migration_view&&
                 chunk.registry_owner_domain!=state.checkpoint.registry_owner_domain))return false;
        }
        if(state.checkpoint.report_snapshot){
            RetirementSnapshotRepository reports(store_,crypto_,key_,epoch_);RetirementSnapshot snapshot;
            if(!reports.load(*state.checkpoint.report_snapshot,snapshot))return false;
        }
    }
    std::vector<Transition> all;
    for(std::size_t i=0;i<4;++i){Bytes b;bool found=false;
        if(!store_.read(trkey(i),b,found))return false;
        if(!found)continue;
        Transition t;if(!Codec::decode_transition(crypto_,key_,b,t)||t.storage_epoch!=epoch_)return false;
        if(t.ordinal>boundary){
            if(selected>=0&&!state.checkpoint.migration_view&&t.type==TransitionType::Event&&
               t.registry_owner_domain!=state.checkpoint.registry_owner_domain)return false;
            all.push_back(std::move(t));
        }
    }
    std::sort(all.begin(),all.end(),[](const Transition&a,const Transition&b){return a.ordinal<b.ordinal;});
    std::uint64_t expected=boundary+1;
    for(const auto&t:all){if(t.ordinal!=expected++)return false;state.tail.push_back(t);}
    state.last_ordinal=state.tail.empty()?boundary:state.tail.back().ordinal;
    return true;
}

CommitStatus DurableStore::commit(Transition candidate){
    RecoveryState s;if(!recover(s))return CommitStatus::StorageFault;if(s.last_ordinal==std::numeric_limits<std::uint64_t>::max())return CommitStatus::NotCommitted;
    MigrationManifest active_manifest;
    MigrationManifestRepository manifests(store_,crypto_,key_,epoch_);
    const auto manifest_status=manifests.load(active_manifest,nullptr);
    if(manifest_status==MigrationManifestStatus::IoError||
       manifest_status==MigrationManifestStatus::Corrupt||
       manifest_status==MigrationManifestStatus::Conflict)return CommitStatus::StorageFault;
    if(s.checkpoint.migration_view||
       (manifest_status==MigrationManifestStatus::Ready&&
        active_manifest.phase!=MigrationPhase::Activated))return CommitStatus::NotCommitted;
    if(candidate.type==TransitionType::Event&&s.checkpoint.generation!=0&&
       candidate.registry_owner_domain!=s.checkpoint.registry_owner_domain)
        return CommitStatus::NotCommitted;
    if(candidate.type==TransitionType::Event){
        if(!candidate.event_digest_present||candidate.enrollment_slot>=kMaxRetirementNodes||candidate.enrollment_generation==0||!nonzero(candidate.event_digest.data(),candidate.event_digest.size()))return CommitStatus::StorageFault;
        auto classify=[&](std::uint8_t slot,std::uint32_t slot_generation,std::uint64_t session,std::uint64_t sequence,const std::array<std::uint8_t,32>& digest){
            if(slot!=candidate.enrollment_slot||slot_generation!=candidate.enrollment_generation||session!=candidate.event.session_id||sequence!=candidate.event.sequence)return CommitStatus::NotCommitted;
            return digest==candidate.event_digest?CommitStatus::Committed:CommitStatus::Conflict;
        };
        for(const auto&t:s.tail)if(t.type==TransitionType::Event&&t.event==candidate.event){if(!t.event_digest_present)return CommitStatus::StorageFault;return t.enrollment_slot==candidate.enrollment_slot&&t.enrollment_generation==candidate.enrollment_generation?(t.event_digest==candidate.event_digest?CommitStatus::Committed:CommitStatus::Conflict):CommitStatus::Conflict;}
        for(const auto&ref:s.checkpoint.dedupe_evidence_chunks){DedupeEvidenceChunk chunk;if(!read_evidence_chunk(ref,chunk))return CommitStatus::StorageFault;for(std::size_t i=0;i<chunk.count;++i){const auto&e=chunk.entries[i];const auto result=classify(e.enrollment_slot,e.enrollment_generation,e.origin_session,e.sequence,e.digest);if(result!=CommitStatus::NotCommitted)return result;}}
        if(s.checkpoint.report_snapshot){RetirementSnapshotRepository reports(store_,crypto_,key_,epoch_);RetirementSnapshot snapshot;if(!reports.load(*s.checkpoint.report_snapshot,snapshot))return CommitStatus::StorageFault;
            const auto&report= snapshot.nodes[candidate.enrollment_slot];
            if(report.enrollment_generation==candidate.enrollment_generation&&candidate.event.session_id<=report.current_origin_session){
                for(std::size_t i=0;i<report.pending_count;++i)if(report.pending[i].origin_session==candidate.event.session_id&&report.pending[i].sequence==candidate.event.sequence)return CommitStatus::Conflict;
                if(candidate.event.session_id<report.current_origin_session||candidate.event.sequence<=report.durable_admission_highwater)return CommitStatus::NotCommitted;
            }
        }
    }
    std::size_t pending_effect_count = s.checkpoint.pending_effects.size() + candidate.effects.size();
    for (const auto& t : s.tail) pending_effect_count += t.effects.size();
    if (pending_effect_count > kMaxPendingEffects) return CommitStatus::NotCommitted;
    if(s.last_ordinal-s.checkpoint.covered_ordinal>=4)return CommitStatus::NotCommitted;
    candidate.storage_epoch=epoch_;candidate.ordinal=s.last_ordinal+1;Bytes blob;if(!Codec::encode_transition(crypto_,key_,candidate,blob))return CommitStatus::NotCommitted;const auto slot=static_cast<std::size_t>((candidate.ordinal-1)%4);Bytes prior;bool found=false;if(!store_.read(trkey(slot),prior,found))return CommitStatus::StorageFault;
    if(found){
        Transition old;if(!Codec::decode_transition(crypto_,key_,prior,old))return CommitStatus::StorageFault;std::array<Checkpoint,2> cps{};std::array<bool,2> valid{};for(std::size_t i=0;i<2;++i){Bytes b;bool f=false;if(!store_.read(cpkey(i),b,f))return CommitStatus::StorageFault;valid[i]=f&&Codec::decode_checkpoint(crypto_,key_,b,cps[i])&&cps[i].storage_epoch==epoch_;}if(!valid[0]||!valid[1]||old.ordinal>std::min(cps[0].covered_ordinal,cps[1].covered_ordinal))return CommitStatus::NotCommitted;
    }
    const bool wrote=found?store_.replace(trkey(slot),blob):store_.write_immutable(trkey(slot),blob);Bytes verify;bool vf=false;Transition decoded;if(store_.read(trkey(slot),verify,vf)&&vf&&verify==blob&&Codec::decode_transition(crypto_,key_,verify,decoded)&&decoded.ordinal==candidate.ordinal&&decoded.event==candidate.event&&decoded.type==candidate.type&&decoded.event_digest==candidate.event_digest&&decoded.enrollment_slot==candidate.enrollment_slot&&decoded.enrollment_generation==candidate.enrollment_generation)return wrote?CommitStatus::Committed:CommitStatus::AmbiguousResolvedCommitted;return wrote?CommitStatus::StorageFault:CommitStatus::NotCommitted;
}

bool DurableStore::checkpoint(const Checkpoint& input){
    RecoveryState s;if(!recover(s)||s.checkpoint.legacy_dedupe_unverified||(input.covered_ordinal!=s.last_ordinal&&input.covered_ordinal!=s.checkpoint.covered_ordinal)||input.storage_epoch!=epoch_||input.generation<=s.checkpoint_generation)return false;
    MigrationManifest active_manifest;MigrationManifestRepository manifests(store_,crypto_,key_,epoch_);
    const auto manifest_status=manifests.load(active_manifest,nullptr);
    if(manifest_status==MigrationManifestStatus::Corrupt||manifest_status==MigrationManifestStatus::Conflict||
       manifest_status==MigrationManifestStatus::IoError||
       (manifest_status==MigrationManifestStatus::Ready&&active_manifest.phase!=MigrationPhase::Activated))return false;
    Checkpoint cp=input;
    if(s.checkpoint.registry_owner_domain){
        if((cp.registry_owner_domain&&cp.registry_table_digest!=s.checkpoint.registry_table_digest)||
           (cp.migration_frontier!=0&&cp.migration_frontier<s.checkpoint.migration_frontier))return false;
        cp.registry_owner_domain=true;cp.registry_table_digest=s.checkpoint.registry_table_digest;
        cp.migration_frontier=std::max(cp.migration_frontier,s.checkpoint.migration_frontier);
        cp.allow_legacy_event_tail=cp.allow_legacy_event_tail||s.checkpoint.allow_legacy_event_tail;
    }
    if(!cp.report_snapshot)cp.report_snapshot=s.checkpoint.report_snapshot;
    if(cp.dedupe_evidence_chunks.empty()&&!cp.report_snapshot)cp.dedupe_evidence_chunks=s.checkpoint.dedupe_evidence_chunks;
    std::optional<RetirementSnapshot> retirement_snapshot;
    if(cp.report_snapshot){RetirementSnapshotRepository reports(store_,crypto_,key_,epoch_);RetirementSnapshot snapshot;if(!reports.load(*cp.report_snapshot,snapshot))return false;retirement_snapshot=std::move(snapshot);}
    if(s.checkpoint.report_snapshot&&cp.report_snapshot){
        const auto& old=*s.checkpoint.report_snapshot;const auto& next=*cp.report_snapshot;
        const bool same_ref=old.bank==next.bank&&old.generation==next.generation&&old.digest==next.digest;
        if(!same_ref&&next.generation<=old.generation)return false;
    }
    for(const auto& old:s.checkpoint.dedupe_evidence_chunks){
        if(std::find_if(cp.dedupe_evidence_chunks.begin(),cp.dedupe_evidence_chunks.end(),[&](const auto& x){return x.chunk_id==old.chunk_id&&x.digest==old.digest;})!=cp.dedupe_evidence_chunks.end())continue;
        DedupeEvidenceChunk chunk;if(!read_evidence_chunk(old,chunk))return false;
        bool all_retired=retirement_snapshot.has_value();
        for(std::size_t i=0;all_retired&&i<chunk.count;++i)all_retired=retirement_covers(chunk.entries[i],*retirement_snapshot);
        if(!all_retired)cp.dedupe_evidence_chunks.push_back(old);
    }
    for(const auto& ref:cp.dedupe_evidence_chunks){DedupeEvidenceChunk ignored;if(!read_evidence_chunk(ref,ignored))return false;}
    std::vector<DedupeEvidenceEntry> new_entries;for(const auto&t:s.tail)if(t.ordinal<=cp.covered_ordinal&&t.type==TransitionType::Event){if(!t.event_digest_present)return false;DedupeEvidenceEntry entry;entry.enrollment_slot=t.enrollment_slot;entry.enrollment_generation=t.enrollment_generation;entry.origin_session=t.event.session_id;entry.sequence=t.event.sequence;entry.digest=t.event_digest;new_entries.push_back(entry);}
    for(std::size_t offset=0;offset<new_entries.size();offset+=4){if(cp.dedupe_evidence_chunks.size()>=kMaxDedupeEvidenceRefs)return false;DedupeEvidenceChunk chunk;chunk.storage_epoch=epoch_;chunk.chunk_id=(cp.generation<<8)|static_cast<std::uint64_t>(offset/4+1);chunk.count=static_cast<std::uint8_t>(std::min<std::size_t>(4,new_entries.size()-offset));chunk.registry_owner_domain=cp.registry_owner_domain;for(std::size_t i=0;i<chunk.count;++i)chunk.entries[i]=new_entries[offset+i];Bytes ev_blob;if(!Codec::encode_evidence_chunk(crypto_,key_,chunk,ev_blob))return false;const auto ev_key="ev"+std::to_string(chunk.chunk_id);Bytes prior;bool prior_found=false;if(!store_.read(ev_key,prior,prior_found))return false;DedupeEvidenceChunk prior_chunk;bool prior_matches=prior_found&&Codec::decode_evidence_chunk(crypto_,key_,prior,prior_chunk)&&prior_chunk.storage_epoch==chunk.storage_epoch&&prior_chunk.chunk_id==chunk.chunk_id&&prior_chunk.count==chunk.count&&prior_chunk.registry_owner_domain==chunk.registry_owner_domain;for(std::size_t i=0;prior_matches&&i<chunk.count;++i){const auto&a=prior_chunk.entries[i];const auto&b=chunk.entries[i];prior_matches=a.enrollment_slot==b.enrollment_slot&&a.enrollment_generation==b.enrollment_generation&&a.origin_session==b.origin_session&&a.sequence==b.sequence&&a.digest==b.digest;}if(prior_matches)ev_blob=prior;else if(prior_found)(void)store_.replace(ev_key,ev_blob);else(void)store_.write_immutable(ev_key,ev_blob);Bytes verify;bool found=false;DedupeEvidenceChunk round;if(!store_.read(ev_key,verify,found)||!found||!Codec::decode_evidence_chunk(crypto_,key_,verify,round)||round.count!=chunk.count||round.registry_owner_domain!=cp.registry_owner_domain)return false;DedupeEvidenceReference ref;ref.chunk_id=chunk.chunk_id;if(!crypto_.hmac_sha256(key_,verify,ref.digest))return false;cp.dedupe_evidence_chunks.push_back(ref);}
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
    RecoveryState selected;
    if(!recover(selected))return CommitStatus::StorageFault;
    MigrationManifest manifest;MigrationManifestRepository manifests(store_,crypto_,key_,epoch_);
    const auto manifest_status=manifests.load(manifest,nullptr);
    if(manifest_status==MigrationManifestStatus::IoError||
       manifest_status==MigrationManifestStatus::Corrupt||
       manifest_status==MigrationManifestStatus::Conflict)return CommitStatus::StorageFault;
    if(selected.checkpoint.migration_view||
       (manifest_status==MigrationManifestStatus::Ready&&
        manifest.phase!=MigrationPhase::Activated))return CommitStatus::NotCommitted;
    bm.storage_epoch=epoch_;CompletionBitmap old;bool found=read_bitmap(bm.mapping_digest,old);if(found){if((bm.committed_bits|old.committed_bits)!=bm.committed_bits)return CommitStatus::NotCommitted;if(bm.committed_bits==old.committed_bits)return CommitStatus::Committed;bm.generation=old.generation+1;}else if(bm.generation==0)bm.generation=1;Bytes blob;if(!Codec::encode_bitmap(crypto_,key_,bm,blob))return CommitStatus::NotCommitted;Bytes a,b;bool fa=false,fb=false;if(!store_.read("bm0",a,fa)||!store_.read("bm1",b,fb))return CommitStatus::StorageFault;CompletionBitmap va,vb;const bool ga=fa&&Codec::decode_bitmap(crypto_,key_,a,va);const bool gb=fb&&Codec::decode_bitmap(crypto_,key_,b,vb);const std::size_t i=!ga?0:!gb?1:(va.generation<=vb.generation?0:1);const std::string k="bm"+std::to_string(i);bool wrote=store_.replace(k,blob);Bytes check;bool f=false;CompletionBitmap decoded;if(store_.read(k,check,f)&&f&&check==blob&&Codec::decode_bitmap(crypto_,key_,check,decoded)&&decoded.generation==bm.generation)return wrote?CommitStatus::Committed:CommitStatus::AmbiguousResolvedCommitted;return wrote?CommitStatus::StorageFault:CommitStatus::NotCommitted;
}
bool DurableStore::read_bitmap(const std::array<std::uint8_t,32>& digest,CompletionBitmap& out){bool found=false;for(const char*k:{"bm0","bm1"}){Bytes b;bool f=false;if(!store_.read(k,b,f))return false;if(!f)continue;CompletionBitmap bm;if(Codec::decode_bitmap(crypto_,key_,b,bm)&&bm.storage_epoch==epoch_&&bm.mapping_digest==digest&&(!found||bm.generation>out.generation)){out=bm;found=true;}}return found;}
bool DurableStore::read_pending_chunk(std::uint64_t chunk_id,PendingEffectChunk& out){Bytes blob;bool found=false;const auto key="ef"+std::to_string(chunk_id);return store_.read(key,blob,found)&&found&&Codec::decode_chunk(crypto_,key_,blob,out)&&out.storage_epoch==epoch_&&out.chunk_id==chunk_id;}
bool DurableStore::read_evidence_chunk(std::uint64_t chunk_id,DedupeEvidenceChunk& out){Bytes blob;bool found=false;const auto key="ev"+std::to_string(chunk_id);return store_.read(key,blob,found)&&found&&Codec::decode_evidence_chunk(crypto_,key_,blob,out)&&out.storage_epoch==epoch_&&out.chunk_id==chunk_id;}
bool DurableStore::read_evidence_chunk(const DedupeEvidenceReference& ref,DedupeEvidenceChunk& out){Bytes blob;bool found=false;const auto key="ev"+std::to_string(ref.chunk_id);security::Key32 digest{};return store_.read(key,blob,found)&&found&&crypto_.hmac_sha256(key_,blob,digest)&&crypto_.constant_time_equal(digest.data(),ref.digest.data(),digest.size())&&Codec::decode_evidence_chunk(crypto_,key_,blob,out)&&out.storage_epoch==epoch_&&out.chunk_id==ref.chunk_id;}

bool DurableStore::compound_root_digest(std::uint8_t bank,
        std::array<std::uint8_t,32>& out, std::uint8_t source_live_tail_count,
        bool include_legacy_event_slots) {
    out.fill(0);
    if(bank>1)return false;
    using RootIdentity=std::pair<std::uint8_t,std::string>;
    std::map<RootIdentity,Bytes> objects;
    const auto padded_id=[](std::uint64_t value) {
        auto text=std::to_string(value);
        return std::string(20U-text.size(),'0')+text;
    };
    auto add=[&](std::uint8_t kind,const std::string& id,const Bytes& bytes) {
        if(id.empty()||id.size()>255||bytes.empty()||
           bytes.size()>std::numeric_limits<std::uint32_t>::max())return false;
        return objects.emplace(RootIdentity{kind,id},bytes).second;
    };
    auto read_raw=[&](const std::string& key,Bytes& bytes,bool required) {
        bool found=false;
        return store_.read(key,bytes,found)&&(!required||found)&&(!found||!bytes.empty());
    };

    Bytes cp_blob;
    Checkpoint cp;
    if(!read_raw(cpkey(bank),cp_blob,true)||
       !Codec::decode_checkpoint(crypto_,key_,cp_blob,cp)||cp.storage_epoch!=epoch_)
        return false;
    const bool frozen_source_scope=source_live_tail_count!=0xff;
    if(!frozen_source_scope)
        source_live_tail_count=cp.protected_live_tail_count;
    if(source_live_tail_count>4||
       !add(1,"checkpoint/"+padded_id(cp.generation),cp_blob))return false;

    for(const auto& ref:cp.pending_chunks) {
        PendingEffectChunk chunk;
        const auto logical="ef"+std::to_string(ref.chunk_id);
        Bytes bytes;
        if(!read_pending_chunk(ref.chunk_id,chunk)||!read_raw(logical,bytes,true)||
           !add(2,padded_id(ref.chunk_id),bytes))return false;
    }
    for(const auto& ref:cp.dedupe_evidence_chunks) {
        DedupeEvidenceChunk chunk;
        const auto logical="ev"+std::to_string(ref.chunk_id);
        Bytes bytes;
        if(!read_evidence_chunk(ref,chunk)||
           (!cp.migration_view&&chunk.registry_owner_domain!=cp.registry_owner_domain)||
           !read_raw(logical,bytes,true)||!add(3,padded_id(ref.chunk_id),bytes))return false;
    }
    if(cp.report_snapshot) {
        const auto logical="ret"+std::to_string(cp.report_snapshot->bank);
        Bytes bytes;
        security::Key32 actual{};
        if(!read_raw(logical,bytes,true)||!crypto_.hmac_sha256(key_,bytes,actual)||
           !crypto_.constant_time_equal(actual.data(),cp.report_snapshot->digest.data(),32)||
           !add(4,std::to_string(cp.report_snapshot->bank),bytes))return false;
    }

    if(source_live_tail_count!=0) {
        if(cp.covered_ordinal>std::numeric_limits<std::uint64_t>::max()-source_live_tail_count)
            return false;
        for(std::uint8_t offset=0;offset<source_live_tail_count;++offset) {
            const auto ordinal=cp.covered_ordinal+1U+offset;
            const auto logical=trkey(static_cast<std::size_t>((ordinal-1U)%4U));
            Bytes bytes;
            Transition transition;
            if(!read_raw(logical,bytes,true)||
               !Codec::decode_transition(crypto_,key_,bytes,transition)||
               transition.storage_epoch!=epoch_||transition.ordinal!=ordinal||
               !add(5,padded_id(ordinal),bytes))return false;
        }
    }
    if(frozen_source_scope) {
        std::uint8_t live_count=0;
        for(std::size_t i=0;i<4;++i) {
            Bytes bytes;
            if(!read_raw(trkey(i),bytes,false))return false;
            bool found=false;
            if(!store_.read(trkey(i),bytes,found))return false;
            if(!found)continue;
            Transition transition;
            if(!Codec::decode_transition(crypto_,key_,bytes,transition)||
               transition.storage_epoch!=epoch_)return false;
            if(transition.ordinal<=cp.covered_ordinal)continue;
            if(live_count>=source_live_tail_count)return false;
            ++live_count;
        }
        if(live_count!=source_live_tail_count)return false;
    }

    bool has_legacy_event_slots=include_legacy_event_slots||cp.allow_legacy_event_slots;
    if(!has_legacy_event_slots) {
        for(std::size_t slot=0;slot<128;++slot) {
            const auto digits=std::to_string(slot);
            const auto logical="e"+std::string(3U-digits.size(),'0')+digits;
            Bytes ignored;bool found=false;
            if(!store_.read(logical,ignored,found))return false;
            has_legacy_event_slots=has_legacy_event_slots||found;
        }
    }
    if(has_legacy_event_slots) {
        for(std::size_t slot=0;slot<128;++slot) {
            const auto digits=std::to_string(slot);
            const auto logical="e"+std::string(3U-digits.size(),'0')+digits;
            Bytes bytes;
            bool found=false;
            if(!read_raw(logical,bytes,false)||!store_.read(logical,bytes,found))return false;
            if(found&&!add(6,padded_id(slot),bytes))return false;
        }
    }

    static constexpr char kRootDomain[]="hub-durable-compound-root-v2";
    Bytes context(kRootDomain,kRootDomain+sizeof(kRootDomain)-1U);
    Writer fields;
    fields.u32(epoch_);
    fields.u8(cp.registry_owner_domain?1U:0U);
    fields.u64(cp.generation);
    fields.u16(cp.migration_frontier);
    fields.raw(cp.registry_table_digest.data(),cp.registry_table_digest.size());
    context.insert(context.end(),fields.b.begin(),fields.b.end());
    if(!crypto_.hmac_sha256(key_,context,out))return false;
    crypto_.secure_zero(context.data(),context.size());
    for(const auto& [identity,bytes]:objects) {
        const auto& [kind,id]=identity;
        if(id.size()>std::numeric_limits<std::uint16_t>::max()||
           bytes.size()>std::numeric_limits<std::uint32_t>::max())return false;
        Writer step;
        step.raw(out.data(),out.size());
        step.u8(kind);
        step.u16(static_cast<std::uint16_t>(id.size()));
        step.raw(reinterpret_cast<const std::uint8_t*>(id.data()),id.size());
        step.u32(static_cast<std::uint32_t>(bytes.size()));
        step.raw(bytes);
        security::Key32 next{};
        if(!crypto_.hmac_sha256(key_,step.b,next)) {
            crypto_.secure_zero(out.data(),out.size());
            crypto_.secure_zero(step.b.data(),step.b.size());
            return false;
        }
        out=next;
        crypto_.secure_zero(step.b.data(),step.b.size());
    }
    return nonzero(out.data(),out.size());
}

} // namespace gs::hub::durable
