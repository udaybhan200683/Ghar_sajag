#include "host/storage/compact_nvs_representation.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <algorithm>
#include <iostream>
#include <set>
#include <stdexcept>
namespace {
using namespace gs::host::storage::native;
using gs::host::security::OpenSslCommissioningCrypto;
void check(bool v){if(!v)throw std::runtime_error("compact representation invariant");}
Key32 key(unsigned v){Key32 k{};k.fill(v);return k;}
class Store final : public CompactObjectStore {
public:
    gs::hub::durable::MemoryBlobStore media;std::set<std::string> names;
    bool read(const std::string& k,Bytes& b,bool& f)override{return media.read(k,b,f);}
    bool replace(const std::string& k,const Bytes& b)override{names.insert(k);return media.replace(k,b);}
    bool write_immutable(const std::string& k,const Bytes& b)override{names.insert(k);return media.write_immutable(k,b);}
    bool erase_if_equals(const std::string& k,const Bytes& b)override{
        if(!media.erase_if_equals(k,b))return false;
        names.erase(k);return true;
    }
    bool objects(std::vector<std::string>& out)override{
        out.clear();for(const auto& k:names)if(k.size()==15&&(k[0]=='e'||k[0]=='r'))out.push_back(k);return true;
    }
};
// Independent test witness; this positive host scope must not be attributed to NVS.
class Authority final : public PublicationAuthority {
public:
    Bytes head,witness;
    bool read(Bytes& b)override{if(head!=witness)return false;b=head;return true;}
    bool provision(const Bytes& b)override{if(!head.empty())return false;head=witness=b;return true;}
    bool compare_publish(const Bytes& expected,const Bytes& b)override{
        if(head!=witness||head!=expected)return false;
        head=witness=b;return true;
    }
};
}
int main() {
    Store s;Authority a;OpenSslCommissioningCrypto c;CompactRepresentation compact(s,c,key(77),7);
    Transaction t(s,c,a,key(77),7,32,&compact);check(t.provision_fresh());
    std::array<Proof,6> owners{};
    for(unsigned n=0;n<6;++n) {
        check(t.enroll(key(10+n),key(30+n))==Result::Committed);
        const auto& o=t.state()->owners[n];owners[n]={static_cast<std::uint8_t>(n),o.generation,o.binding,9};
        NodeRetirementReportV1 r;r.epoch=7;r.generation=1;r.current_origin_session=1;r.durable_admission_highwater=32;
        r.pending_count=32;for(unsigned j=0;j<32;++j)r.pending[j]={1,j+1};
        Bytes logical;Key32 mac{};check(gs::transport::encode_retirement_report(r,logical)&&c.hmac_sha256(key(30+n),logical,mac));
        check(t.report(owners[n],r,mac)==Result::Committed);check(compact.collect_selected(*t.state()));
    }
    for(const auto& p:owners)for(unsigned seq=1;seq<=64;++seq) {
        Event e{p,1,seq,Bytes(448,0x42)};Key32 mac{};check(t.event_mac(key(30+p.slot),e,mac));
        check(t.admit(e,mac,Bytes(4096,0x11))==Result::Committed);check(compact.collect_selected(*t.state()));
    }
    check(t.recover()&&t.state()->rows.size()==384);
    for(const auto& o:t.state()->owners)check(o.charged==32);
    Bytes bank;bool found=false;check(s.read("hn_bank"+std::to_string(a.head[18]),bank,found)&&found);
    check(bank.size()==16649);std::size_t payload=a.head.size();
    for(const auto& name:s.names){Bytes b;check(s.read(name,b,found)&&found);payload+=b.size();}
    // The previous bank has one fewer reference, hence exactly33 fewer bytes.
    check(payload==241379);
    Bytes unused;for(const Bytes& bad:{Bytes{},Bytes{'C','N','P','1'},Bytes{'C','N','P','1',255,255}})check(!compact.unpack(bad,unused));
    // Tampered selected dependency cannot cause an older-bank fallback.
    std::vector<std::string> names;check(s.objects(names));
    const auto event=*std::find_if(names.begin(),names.end(),[](const auto& k){return k[0]=='e';});
    Bytes body;check(s.read(event,body,found)&&found);body.back()^=1;check(s.replace(event,body));
    check(!t.recover()&&!t.state());
    std::cout<<"COMPACT_HOST_PASS exact_identities=384 charged_per_owner=32 manifest_bytes=16649 retained_payload=241379 dependency_corruption=fail_closed malformed_manifest=reject authority=INDEPENDENT_HOST_WITNESS_ONLY\n";
}
