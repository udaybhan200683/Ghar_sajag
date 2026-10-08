#include "host/storage/compact_nvs_representation.hpp"
#include <algorithm>
#include <set>

namespace gs::host::storage::native {
namespace {
struct Cursor {
    const Bytes& b; std::size_t p=0; bool ok=true;
    unsigned number(unsigned n) {
        if(!ok||n>b.size()-p){ok=false;return 0;}
        unsigned v=0;while(n--)v=(v<<8)|b[p++];return v;
    }
    Bytes take(std::size_t n) {
        if(!ok||n>b.size()-p){ok=false;return {};}
        Bytes out(b.begin()+p,b.begin()+p+n);p+=n;return out;
    }
};
void append(Bytes& b,const Bytes& value){b.insert(b.end(),value.begin(),value.end());}
void number(Bytes& b,std::uint64_t v,unsigned n){while(n--)b.push_back(v>>(8*n));}
Bytes context(char kind,std::uint32_t epoch) {
    const std::string label="GS-COMPACT-NVS-OBJECT-v1";
    Bytes b(label.begin(),label.end());b.push_back(kind);number(b,epoch,4);return b;
}
Bytes event_plain(const Row& r) {
    Bytes b;number(b,r.slot,1);number(b,r.owner_generation,4);number(b,r.origin,8);
    number(b,r.sequence,8);b.insert(b.end(),r.digest.begin(),r.digest.end());
    number(b,r.body.size(),2);append(b,r.body);return b;
}
}
CompactRepresentation::CompactRepresentation(CompactObjectStore& s,
        security::CommissioningCrypto& c,Key32 k,std::uint32_t epoch)
    :store_(s),crypto_(c),key_(k),epoch_(epoch){}
CompactRepresentation::~CompactRepresentation(){crypto_.secure_zero(key_.data(),key_.size());}
std::string CompactRepresentation::object_name(char kind,const Key32& digest) {
    constexpr char hex[]="0123456789abcdef";std::string k(1,kind);
    for(unsigned i=0;i<7;++i){k+=hex[digest[i]>>4];k+=hex[digest[i]&15];}return k;
}
bool CompactRepresentation::id(char kind,const Bytes& plain,Key32& out) {
    Bytes input=context(kind,epoch_);append(input,plain);
    return crypto_.hmac_sha256(key_,input,out);
}
bool CompactRepresentation::get(char kind,const Key32& expected,Bytes& plain) {
    Bytes b;bool found=false;
    if(!store_.read(object_name(kind,expected),b,found)||!found||b.size()<28||
       b.size()>(kind=='e'?531U:4124U))return false;
    security::Nonce12 nonce{};security::GcmTag tag{};
    std::copy_n(b.begin(),12,nonce.begin());std::copy_n(b.end()-16,16,tag.begin());
    const Bytes cipher(b.begin()+12,b.end()-16);
    Key32 actual{};
    return crypto_.open_aes256_gcm(key_,nonce,context(kind,epoch_),cipher,tag,plain)&&
        id(kind,plain,actual)&&crypto_.constant_time_equal(actual.data(),expected.data(),32);
}
bool CompactRepresentation::put(char kind,const Bytes& plain,Key32& digest) {
    if((kind!='e'&&kind!='r')||plain.size()>(kind=='e'?503U:4096U)||!id(kind,plain,digest))return false;
    const auto name=object_name(kind,digest);Bytes existing;bool found=false;
    if(!store_.read(name,existing,found))return false;
    if(found){Bytes decoded;return get(kind,digest,decoded)&&decoded==plain;}
    std::vector<std::string> keys;if(!store_.objects(keys))return false;
    unsigned count=0;for(const auto& k:keys)count+=!k.empty()&&k[0]==kind;
    if(count>=(kind=='e'?event_objects:reducer_objects))return false;
    security::Nonce12 nonce{};security::GcmTag tag{};Bytes cipher;
    if(!crypto_.random_bytes(nonce.data(),nonce.size())||
       !crypto_.seal_aes256_gcm(key_,nonce,context(kind,epoch_),plain,cipher,tag))return false;
    Bytes b(nonce.begin(),nonce.end());append(b,cipher);b.insert(b.end(),tag.begin(),tag.end());
    (void)store_.write_immutable(name,b);Bytes decoded;
    return get(kind,digest,decoded)&&decoded==plain;
}
bool CompactRepresentation::pack(const Bytes& input,Bytes& out) {
    if(input.size()>Transaction::maximum_bank_bytes()-28)return false;
    Cursor c{input};c.take(33);
    for(unsigned n=0;n<kOwners;++n) {
        const auto phase=c.number(1);if(phase==0)continue;
        if(phase>2)return false;
        c.take(4+32+32+1);const auto len=c.number(2);if(len>542)return false;
        c.take(len+32);
    }
    if(!c.ok)return false;
    out={'C','N','P','1'};number(out,c.p,2);
    out.insert(out.end(),input.begin(),input.begin()+c.p);
    const auto rows=c.number(2);if(rows>kRows)return false;number(out,rows,2);
    // Read/authenticate every reused object and build the complete write set
    // before any write. A rejected plan leaves the committed root untouched.
    std::vector<std::pair<char,Bytes>> missing;
    PublicationPlan plan;plan.ordinary_admission=ordinary_;
    plan.control_manifest_bytes=control_manifest_bound(rows);
    auto prepare=[&](char kind,const Bytes& plain,Key32& digest) {
        if(!id(kind,plain,digest))return false;
        Bytes b;bool found=false;
        if(!store_.read(object_name(kind,digest),b,found))return false;
        if(found){Bytes check;return get(kind,digest,check)&&check==plain;}
        missing.emplace_back(kind,plain);plan.blobs.push_back(plain.size()+28);return true;
    };
    for(unsigned i=0;i<rows;++i) {
        Bytes body=c.take(53);const auto flags=c.number(1),len=c.number(2);
        if(flags>7||len>hub::durable::kMaxCausalInputBytes)return false;
        number(body,len,2);append(body,c.take(len));if(!c.ok)return false;
        Key32 digest{};if(!prepare('e',body,digest))return false;
        out.push_back(flags);out.insert(out.end(),digest.begin(),digest.end());
    }
    const auto len=c.number(2);if(len>kReducerBytes)return false;
    const auto reducer=c.take(len);if(!c.ok||c.p!=input.size())return false;
    Key32 digest{};if(!prepare('r',reducer,digest))return false;
    out.insert(out.end(),digest.begin(),digest.end());
    std::vector<std::string> objects;if(!store_.objects(objects))return false;
    for(const auto& name:objects) {
        plan.event_objects_after+=!name.empty()&&name[0]=='e';
        plan.reducer_objects_after+=!name.empty()&&name[0]=='r';
    }
    for(const auto& object:missing) {
        plan.event_objects_after+=object.first=='e';
        plan.reducer_objects_after+=object.first=='r';
    }
    plan.blobs.push_back(out.size()+28);plan.blobs.push_back(Transaction::head_bytes);
    if(!store_.prepare_publication(plan))return false;
    for(const auto& object:missing)if(!put(object.first,object.second,digest))return false;
    return true;
}
bool CompactRepresentation::unpack(const Bytes& input,Bytes& out) {
    Cursor c{input};if(c.take(4)!=Bytes({'C','N','P','1'}))return false;
    const auto prefix=c.number(2);if(prefix<39||prefix>3909)return false;
    out=c.take(prefix);const auto rows=c.number(2);if(rows>kRows)return false;
    number(out,rows,2);
    for(unsigned i=0;i<rows;++i) {
        const auto flags=c.number(1);if(flags>7)return false;
        Key32 digest{};const auto ref=c.take(32);if(!c.ok)return false;
        std::copy(ref.begin(),ref.end(),digest.begin());Bytes body;
        if(!get('e',digest,body)||body.size()<55||body.size()>503)return false;
        out.insert(out.end(),body.begin(),body.begin()+53);out.push_back(flags);
        out.insert(out.end(),body.begin()+53,body.end());
    }
    const auto ref=c.take(32);if(!c.ok||c.p!=input.size())return false;
    Key32 digest{};std::copy(ref.begin(),ref.end(),digest.begin());Bytes reducer;
    if(!get('r',digest,reducer)||reducer.size()>kReducerBytes)return false;
    number(out,reducer.size(),2);append(out,reducer);return true;
}
bool CompactRepresentation::collect_selected(const State& s) {
    std::set<std::string> protected_keys;Key32 digest{};
    for(const auto& row:s.rows) {
        const auto plain=event_plain(row);Bytes check;
        if(!id('e',plain,digest)||!get('e',digest,check)||check!=plain)return false;
        protected_keys.insert(object_name('e',digest));
    }
    Bytes check;if(!id('r',s.reducer,digest)||!get('r',digest,check)||check!=s.reducer)return false;
    protected_keys.insert(object_name('r',digest));
    std::vector<std::string> keys;if(!store_.objects(keys))return false;
    for(const auto& k:keys)if(!protected_keys.count(k)) {
        Bytes b;bool found=false;if(!store_.read(k,b,found)||!found||!store_.erase_if_equals(k,b))return false;
    }
    return true;
}
} // namespace
