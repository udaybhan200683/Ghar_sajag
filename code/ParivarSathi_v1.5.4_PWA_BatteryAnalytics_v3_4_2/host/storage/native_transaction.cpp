#include "host/storage/native_transaction.hpp"
#include <algorithm>
#include <limits>

namespace gs::host::storage::native {
namespace {
constexpr char kAad[]="GS-HOST-NATIVE-BANK-v1";
constexpr char kHeadDomain[]="GS-HOST-NATIVE-PUBLICATION-v1";
bool nonzero(const Key32& k) { return std::any_of(k.begin(),k.end(),[](auto b){return b!=0;}); }
struct Writer {
    Bytes b;
    void number(std::uint64_t n, unsigned size) {
        for(unsigned i=size;i>0;--i)b.push_back(static_cast<std::uint8_t>(n>>(8*(i-1))));
    }
    void raw(const std::uint8_t* p,std::size_t n){if(n)b.insert(b.end(),p,p+n);}
    void bytes(const Bytes& v){number(v.size(),2);raw(v.data(),v.size());}
};
struct Reader {
    const Bytes& b; std::size_t pos=0; bool ok=true;
    std::uint64_t number(unsigned n) {
        if(!ok||n>b.size()-pos){ok=false;return 0;}
        std::uint64_t v=0;while(n--)v=(v<<8)|b[pos++];return v;
    }
    void raw(std::uint8_t* p,std::size_t n) {
        if(!ok||n>b.size()-pos){ok=false;return;}
        std::copy_n(b.begin()+pos,n,p);pos+=n;
    }
    Bytes bytes(std::size_t maximum) {
        const auto n=number(2);if(!ok||n>maximum||n>b.size()-pos){ok=false;return {};}
        Bytes v(b.begin()+pos,b.begin()+pos+n);pos+=n;return v;
    }
};
bool covers(const Owner& owner,const Row& row) {
    return owner.report.generation && (row.origin<owner.report.current_origin_session ||
        (row.origin==owner.report.current_origin_session &&
         row.sequence<=owner.report.durable_admission_highwater));
}
bool contains(const Owner& owner,const Row& row) {
    for(unsigned i=0;i<owner.report.pending_count;++i)
        if(owner.report.pending[i].origin_session==row.origin &&
           owner.report.pending[i].sequence==row.sequence)return true;
    return false;
}
std::string bank_key(unsigned bank){return "hn_bank"+std::to_string(bank);}
Bytes event_bytes(std::uint32_t epoch,const Event& e) {
    Writer w;w.number(epoch,4);w.number(e.owner.slot,1);w.number(e.owner.generation,4);
    w.raw(e.owner.binding.data(),32);w.number(e.origin,8);w.number(e.sequence,8);
    w.bytes(e.body);return w.b;
}
Bytes domain(const char* label,const Bytes& b) {
    Bytes out(label,label+std::char_traits<char>::length(label));
    out.insert(out.end(),b.begin(),b.end());return out;
}
}
Transaction::Transaction(hub::durable::BlobStore& b,security::CommissioningCrypto& c,
        PublicationAuthority& a,Key32 key,std::uint32_t epoch,unsigned window,
        BankRepresentation* representation)
    :blobs_(b),crypto_(c),authority_(a),key_(key),epoch_(epoch),window_(window),representation_(representation){}
Transaction::~Transaction(){crypto_.secure_zero(key_.data(),key_.size());
    for(auto& o:state_.owners)crypto_.secure_zero(o.report_key.data(),o.report_key.size());}

bool Transaction::event_mac(const Key32& peer_key,const Event& e,Key32& out) const {
    if(e.body.size()>hub::durable::kMaxCausalInputBytes)return false;
    Writer authenticated;authenticated.b=event_bytes(epoch_,e);
    authenticated.number(e.owner.transport_session,8);
    return crypto_.hmac_sha256(peer_key,domain("GS-HOST-AUTH-EVENT-v1",authenticated.b),out);
}
bool Transaction::digest(const Row& row,const Owner& owner,Key32& out) const {
    Event e{{row.slot,row.owner_generation,owner.binding,0},row.origin,row.sequence,row.body};
    return crypto_.hmac_sha256(key_,domain("GS-HOST-EXACT-BODY-v1",event_bytes(epoch_,e)),out);
}
void Transaction::recompute(State& s) const {
    for(auto& o:s.owners)o.charged=0;
    for(auto& row:s.rows) {
        auto& o=s.owners[row.slot];
        if(covers(o,row)&&!contains(o,row))row.retry=false;
        if(row.retry&&!covers(o,row))++o.charged;
    }
    s.rows.erase(std::remove_if(s.rows.begin(),s.rows.end(),[](const Row& r){
        return !r.retry&&!r.local&&!r.backend;
    }),s.rows.end());
}
bool Transaction::validate(const State& s) const {
    if(!epoch_||!nonzero(key_)||window_<1||window_>32||!s.generation||
       !s.next_owner_generation||s.rows.size()>kRows||s.reducer.size()>kReducerBytes)return false;
    std::array<unsigned,kOwners> charge{},pending{},live{};
    for(unsigned n=0;n<kOwners;++n) {
        const auto& o=s.owners[n];
        if(o.phase==Phase::Empty) {
            if(o.generation||o.charged||nonzero(o.binding)||nonzero(o.report_key)||o.report.generation)return false;
            continue;
        }
        if((o.phase!=Phase::Active&&o.phase!=Phase::Retiring)||!o.generation||
           o.generation>=s.next_owner_generation||!nonzero(o.binding)||!nonzero(o.report_key))return false;
        for(unsigned j=0;j<n;++j)if(s.owners[j].phase!=Phase::Empty &&
            (o.binding==s.owners[j].binding||o.generation==s.owners[j].generation||
             o.report_key==s.owners[j].report_key))return false;
        if(o.report.generation) {
            Bytes logical;Key32 mac{};
            if(o.report.epoch!=epoch_||!transport::encode_retirement_report(o.report,logical)||
               !crypto_.hmac_sha256(o.report_key,logical,mac)||
               !crypto_.constant_time_equal(mac.data(),o.report_mac.data(),32))return false;
        } else if(o.report.pending_count||o.report.current_origin_session||
                  o.report.durable_admission_highwater||nonzero(o.report_mac))return false;
    }
    for(std::size_t i=0;i<s.rows.size();++i) {
        const auto& r=s.rows[i];
        if(r.slot>=kOwners||!r.origin||!r.sequence||r.body.size()>hub::durable::kMaxCausalInputBytes)return false;
        const auto& o=s.owners[r.slot];
        if(o.phase==Phase::Empty||r.owner_generation!=o.generation)return false;
        Key32 actual{};if(!digest(r,o,actual)||
            !crypto_.constant_time_equal(actual.data(),r.digest.data(),32))return false;
        const bool covered=covers(o,r);
        if(r.retry!=(!covered||contains(o,r)))return false;
        if(r.retry){++live[r.slot];if(!covered)++charge[r.slot];else ++pending[r.slot];}
        if(!r.retry&&!r.local&&!r.backend)return false;
        for(std::size_t j=0;j<i;++j) {
            const auto& p=s.rows[j];
            if(p.slot==r.slot&&p.owner_generation==r.owner_generation&&p.origin==r.origin&&p.sequence==r.sequence)return false;
        }
    }
    for(unsigned n=0;n<kOwners;++n)if(charge[n]!=s.owners[n].charged||charge[n]>window_||
        pending[n]>kPending||live[n]>kPending+window_)return false;
    return true;
}
bool Transaction::encode(const State& s,unsigned bank,Bytes& blob) {
    if(bank>1||!validate(s))return false;
    Writer w;w.number(0x474e5431,4);w.number(1,1);w.number(epoch_,4);w.number(window_,1);
    w.number(bank,1);w.number(s.generation,8);w.number(s.next_owner_generation,4);
    for(unsigned i=0;i<10;++i)w.number(0,1);
    for(const auto& o:s.owners) {
        w.number(static_cast<unsigned>(o.phase),1);if(o.phase==Phase::Empty)continue;
        w.number(o.generation,4);w.raw(o.binding.data(),32);w.raw(o.report_key.data(),32);
        w.number(o.charged,1);Bytes logical;
        if(o.report.generation&&!transport::encode_retirement_report(o.report,logical))return false;
        w.bytes(logical);w.raw(o.report_mac.data(),32);
    }
    w.number(s.rows.size(),2);
    for(const auto& r:s.rows) {
        w.number(r.slot,1);w.number(r.owner_generation,4);w.number(r.origin,8);w.number(r.sequence,8);
        w.raw(r.digest.data(),32);w.number(r.retry|(r.local<<1)|(r.backend<<2),1);w.bytes(r.body);
    }
    w.bytes(s.reducer);
    if(representation_) {
        Bytes packed;if(!representation_->pack(w.b,packed))return false;
        w.b=std::move(packed);
    }
    security::Nonce12 nonce{};security::GcmTag tag{};Bytes cipher;
    if(!crypto_.random_bytes(nonce.data(),nonce.size())||
       !crypto_.seal_aes256_gcm(key_,nonce,domain(kAad,{}),w.b,cipher,tag))return false;
    blob.assign(nonce.begin(),nonce.end());blob.insert(blob.end(),cipher.begin(),cipher.end());
    blob.insert(blob.end(),tag.begin(),tag.end());
    return blob.size()<=maximum_bank_bytes();
}
bool Transaction::decode(const Bytes& blob,unsigned bank,State& s) {
    if(blob.size()<28||blob.size()>maximum_bank_bytes())return false;
    security::Nonce12 nonce{};security::GcmTag tag{};
    std::copy_n(blob.begin(),12,nonce.begin());std::copy_n(blob.end()-16,16,tag.begin());
    Bytes cipher(blob.begin()+12,blob.end()-16),plain;
    if(!crypto_.open_aes256_gcm(key_,nonce,domain(kAad,{}),cipher,tag,plain))return false;
    if(representation_) {
        Bytes restored;if(!representation_->unpack(plain,restored))return false;
        plain=std::move(restored);
    }
    Reader r{plain};
    if(r.number(4)!=0x474e5431||r.number(1)!=1||r.number(4)!=epoch_||
       r.number(1)!=window_||r.number(1)!=bank)return false;
    s={};s.generation=r.number(8);s.next_owner_generation=static_cast<std::uint32_t>(r.number(4));
    for(unsigned i=0;i<10;++i)if(r.number(1)!=0)return false;
    for(auto& o:s.owners) {
        o.phase=static_cast<Phase>(r.number(1));if(o.phase==Phase::Empty)continue;
        o.generation=static_cast<std::uint32_t>(r.number(4));r.raw(o.binding.data(),32);r.raw(o.report_key.data(),32);
        o.charged=static_cast<std::uint8_t>(r.number(1));const auto logical=r.bytes(542);
        if(!logical.empty()&&!transport::decode_retirement_report(logical.data(),logical.size(),o.report))return false;
        r.raw(o.report_mac.data(),32);
    }
    const auto count=r.number(2);if(!r.ok||count>kRows)return false;s.rows.reserve(count);
    for(unsigned i=0;i<count;++i) {
        Row row;row.slot=static_cast<std::uint8_t>(r.number(1));
        row.owner_generation=static_cast<std::uint32_t>(r.number(4));row.origin=r.number(8);row.sequence=r.number(8);
        r.raw(row.digest.data(),32);const auto flags=r.number(1);if(flags>7)return false;
        row.retry=flags&1;row.local=flags&2;row.backend=flags&4;
        row.body=r.bytes(hub::durable::kMaxCausalInputBytes);s.rows.push_back(std::move(row));
    }
    s.reducer=r.bytes(kReducerBytes);
    return r.ok&&r.pos==plain.size()&&validate(s);
}
bool Transaction::make_head(std::uint64_t generation,unsigned bank,const Key32& digest,Bytes& out) {
    Writer w;w.number(0x474e5031,4);w.number(1,1);w.number(epoch_,4);w.number(window_,1);
    w.number(generation,8);w.number(bank,1);w.raw(digest.data(),32);
    for(unsigned i=0;i<3;++i)w.number(0,1);
    Key32 mac{};if(!crypto_.hmac_sha256(key_,domain(kHeadDomain,w.b),mac))return false;
    w.raw(mac.data(),32);out=std::move(w.b);return out.size()==head_bytes;
}
bool Transaction::head(const Bytes& b,std::uint64_t& generation,unsigned& bank,Key32& digest) {
    if(b.size()!=head_bytes)return false;
    Key32 mac{};
    const Bytes prefix(b.begin(),b.end()-32);
    if(!crypto_.hmac_sha256(key_,domain(kHeadDomain,prefix),mac)||
       !crypto_.constant_time_equal(mac.data(),b.data()+prefix.size(),32))return false;
    Reader r{prefix};if(r.number(4)!=0x474e5031||r.number(1)!=1||r.number(4)!=epoch_||r.number(1)!=window_)return false;
    generation=r.number(8);bank=r.number(1);r.raw(digest.data(),32);
    for(unsigned i=0;i<3;++i)if(r.number(1)!=0)return false;
    return r.ok&&r.pos==prefix.size()&&generation&&bank<2&&nonzero(digest);
}
bool Transaction::recover() {
    ready_=false;Bytes selected,blob;std::uint64_t generation=0;unsigned bank=0;Key32 binding{};
    bool found=false;State decoded;
    if(!authority_.read(selected)||!head(selected,generation,bank,binding)||
       !blobs_.read(bank_key(bank),blob,found)||!found)return false;
    Key32 actual{};
    if(!crypto_.hmac_sha256(key_,blob,actual)||
       !crypto_.constant_time_equal(actual.data(),binding.data(),32)||!decode(blob,bank,decoded)||
       decoded.generation!=generation)return false;
    // No scan/fallback to the older bank. Authority alone selects the state.
    state_=std::move(decoded);head_=std::move(selected);bank_=bank;ready_=true;return true;
}
bool Transaction::provision_fresh() {
    Bytes existing; if(!authority_.read(existing)||!existing.empty())return false;
    for(unsigned bank=0;bank<2;++bank) {
        bool found=false;Bytes blob;if(!blobs_.read(bank_key(bank),blob,found)||found)return false;
    }
    State genesis;Bytes blob,published;Key32 binding{};
    if(!encode(genesis,0,blob))return false;
    (void)blobs_.write_immutable(bank_key(0),blob);
    Bytes check;bool found=false;
    if(!blobs_.read(bank_key(0),check,found)||!found||check!=blob||
       !crypto_.hmac_sha256(key_,blob,binding)||!make_head(1,0,binding,published))return false;
    (void)authority_.provision(published);return recover();
}
Result Transaction::publish(State next) {
    if(!ready_||state_.generation==std::numeric_limits<std::uint64_t>::max())return Result::Fault;
    next.generation=state_.generation+1;const unsigned bank=1-bank_;
    Bytes blob,published;Key32 binding{};
    if(!validate(next))return Result::Invalid;
    if(!encode(next,bank,blob))return Result::Fault;
    // After optional immutable-dependency preparation: candidate bank, then
    // trusted authority. The full reference has exactly these two operations.
    // An API failure may have persisted; exact bank/authority readback decides.
    (void)blobs_.replace(bank_key(bank),blob);
    Bytes check;bool found=false;State verified;
    if(!blobs_.read(bank_key(bank),check,found)||!found||check!=blob||!decode(check,bank,verified))
        return Result::Fault;
    if(!crypto_.hmac_sha256(key_,blob,binding)||!make_head(next.generation,bank,binding,published))return Result::Fault;
    (void)authority_.compare_publish(head_,published);
    if(!recover())return Result::Fault;
    return head_==published ? Result::Committed : Result::Fault;
}
bool Transaction::owner_matches(const Proof& p) const {
    return ready_&&p.slot<kOwners&&state_.owners[p.slot].phase!=Phase::Empty&&
        state_.owners[p.slot].generation==p.generation&&state_.owners[p.slot].binding==p.binding;
}
Result Transaction::enroll(const Key32& binding,const Key32& report_key) {
    if(!ready_||!nonzero(binding)||!nonzero(report_key))return Result::Invalid;
    if(state_.next_owner_generation==std::numeric_limits<std::uint32_t>::max())return Result::Full;
    for(const auto& o:state_.owners)if(o.phase!=Phase::Empty&&o.binding==binding)return Result::Conflict;
    State next=state_;
    for(auto& o:next.owners)if(o.phase==Phase::Empty) {
        o.phase=Phase::Active;o.generation=next.next_owner_generation++;
        o.binding=binding;o.report_key=report_key;return publish(std::move(next));
    }
    return Result::Full;
}
Result Transaction::revoke(const Proof& p) {
    if(!owner_matches(p))return Result::Invalid;
    if(state_.owners[p.slot].phase==Phase::Retiring)return Result::Duplicate;
    State next=state_;next.owners[p.slot].phase=Phase::Retiring;return publish(std::move(next));
}
Result Transaction::release_owner(const Proof& p) {
    if(!owner_matches(p)||state_.owners[p.slot].phase!=Phase::Retiring)return Result::Invalid;
    const auto& o=state_.owners[p.slot];
    if(!o.report.generation||o.report.pending_count)return Result::Full;
    for(const auto& r:state_.rows)if(r.slot==p.slot)return Result::Full;
    State next=state_;next.owners[p.slot]={};return publish(std::move(next));
}
Result Transaction::report(const Proof& p,const NodeRetirementReportV1& incoming,const Key32& mac) {
    if(!owner_matches(p))return Result::Invalid;
    Bytes logical;Key32 verified{};const auto& owner=state_.owners[p.slot];
    if(!transport::encode_retirement_report(incoming,logical)||
       !crypto_.hmac_sha256(owner.report_key,logical,verified)||
       !crypto_.constant_time_equal(verified.data(),mac.data(),32))return Result::Invalid;
    hub::durable::RetirementSnapshot current,candidate;current.storage_epoch=epoch_;current.generation=state_.generation;
    for(unsigned n=0;n<kOwners;++n) {
        const auto& o=state_.owners[n];if(o.phase==Phase::Empty||!o.report.generation)continue;
        current.occupancy_mask|=1U<<n;auto& r=current.nodes[n];r.enrollment_generation=o.generation;
        r.report_generation=o.report.generation;r.report_hmac=o.report_mac;
        r.current_origin_session=o.report.current_origin_session;r.durable_admission_highwater=o.report.durable_admission_highwater;
        r.pending_count=o.report.pending_count;r.pending=o.report.pending;
    }
    hub::durable::RetirementSnapshotRepository repository(blobs_,crypto_,key_,epoch_);
    const auto applied=repository.apply_authenticated_report(current,p.binding,p.slot,p.generation,
        p.transport_session,incoming,verified,candidate);
    using Apply=hub::durable::RetirementReportApply;
    if(applied==Apply::Duplicate)return Result::Duplicate;
    if(applied==Apply::Conflict)return Result::Conflict;
    if(applied!=Apply::Prepared)return Result::Invalid;
    State next=state_;next.owners[p.slot].report=incoming;next.owners[p.slot].report_mac=verified;
    recompute(next);return publish(std::move(next));
}
Result Transaction::admit(const Event& e,const Key32& mac,const Bytes& reducer) {
    if(!owner_matches(e.owner)||!e.origin||!e.sequence||e.origin>e.owner.transport_session||
       reducer.size()>kReducerBytes||e.body.size()>hub::durable::kMaxCausalInputBytes)return Result::Invalid;
    const auto& owner=state_.owners[e.owner.slot];Key32 verified{};
    if(!event_mac(owner.report_key,e,verified)||!crypto_.constant_time_equal(verified.data(),mac.data(),32))return Result::Invalid;
    Row row;row.slot=e.owner.slot;row.owner_generation=e.owner.generation;row.origin=e.origin;
    row.sequence=e.sequence;row.body=e.body;if(!digest(row,owner,row.digest))return Result::Fault;
    for(const auto& r:state_.rows)if(r.slot==row.slot&&r.owner_generation==row.owner_generation&&r.origin==row.origin&&r.sequence==row.sequence)
        return crypto_.constant_time_equal(r.digest.data(),row.digest.data(),32) ? Result::Duplicate : Result::Conflict;
    if(owner.phase!=Phase::Active)return Result::Retired;
    if(covers(owner,row)&&!contains(owner,row))return Result::Retired;
    if(!covers(owner,row)&&owner.charged>=window_)return Result::Full;
    if(state_.rows.size()==kRows)return Result::Full;
    State next=state_;next.rows.push_back(std::move(row));next.reducer=reducer;recompute(next);
    return publish(std::move(next));
}
Result Transaction::dependencies_complete(const Proof& p,std::uint64_t origin,std::uint64_t sequence,bool local,bool backend) {
    if(!owner_matches(p))return Result::Invalid;
    State next=state_;
    for(auto& row:next.rows)if(row.slot==p.slot&&row.origin==origin&&row.sequence==sequence) {
        if(local)row.local=false;
        if(backend)row.backend=false;
        recompute(next);return publish(std::move(next));
    }
    return Result::Invalid;
}
Result Transaction::checkpoint_reducer(const Bytes& reducer) {
    if(!ready_||reducer.size()>kReducerBytes)return Result::Invalid;
    State next=state_;next.reducer=reducer;return publish(std::move(next));
}
} // namespace gs::host::storage::native
