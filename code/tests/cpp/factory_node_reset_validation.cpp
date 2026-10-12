#include "firmware/common/security/association_persistence.hpp"
#include "firmware/common/security/psa_commissioning_crypto.hpp"
#include "tests/cpp/node_empty_aead_checks.hpp"
#include <algorithm>
#include <iostream>
#include <fstream>
#include <map>
#include <stdexcept>
using namespace gs::security;
extern "C" int idf_gcm_pointer_guard(const unsigned char*, size_t, unsigned char*, size_t);
namespace {
void check(bool b,const char* why){if(!b)throw std::runtime_error(why);}
struct Identity final:IdentitySigner{bool public_key(const std::string&,P256PublicKey&)override{return false;}bool sign_hash(const std::string&,const Key32&,P256Signature&)override{return false;}};
struct Store final:AssociationBlobStore{
    Bytes blob;unsigned writes=0;bool fail=false;
    bool read(Bytes& b,bool& f)override{b=blob;f=!blob.empty();return true;}
    bool write(const Bytes& b)override{if(fail)return false;blob=b;++writes;return true;}
};
// Applies the actual IDF esp_aes_gcm_update pointer-validation prefix, then
// delegates successful cases to the real production PSA/software backend.
struct Guard final:CommissioningCrypto {
    PsaCommissioningCrypto& c;bool accelerated=true;size_t observed_plain=99,observed_aad=99;
    explicit Guard(PsaCommissioningCrypto& p):c(p){}
    bool random_bytes(uint8_t* p,size_t n)override{return c.random_bytes(p,n);}
    bool identity_public_key(const std::string& s,P256PublicKey& o)override{return c.identity_public_key(s,o);}
    bool sign_identity(const std::string& s,const Bytes& b,P256Signature& o)override{return c.sign_identity(s,b,o);}
    bool verify_identity(const P256PublicKey& p,const Bytes& b,const P256Signature& s)override{return c.verify_identity(p,b,s);}
    bool generate_ephemeral(EphemeralP256& e)override{return c.generate_ephemeral(e);}
    bool derive_shared(const EphemeralP256& e,const P256PublicKey& p,Key32& k)override{return c.derive_shared(e,p,k);}
    bool hkdf_sha256(const Key32& k,const Bytes& s,const Bytes& x,Key32& o)override{return c.hkdf_sha256(k,s,x,o);}
    bool hmac_sha256(const Key32& k,const Bytes& b,Key32& o)override{return c.hmac_sha256(k,b,o);}
    bool constant_time_equal(const uint8_t* a,const uint8_t* b,size_t n)override{return c.constant_time_equal(a,b,n);}
    void secure_zero(void* p,size_t n)override{c.secure_zero(p,n);}
    bool seal_aes256_gcm(const Key32& k,const Nonce12& nonce,const Bytes& aad,const Bytes& p,Bytes& out,GcmTag& tag)override{
        observed_plain=p.size();observed_aad=aad.size();
        if(accelerated&&p.empty()){
            check(p.data()==nullptr,"empty record unexpectedly has storage");
            check(nonce.size()==12&&tag.size()==16,"nonce/tag sizes changed");
            uint8_t combined[16]{};
            check(idf_gcm_pointer_guard(p.data(),0,combined,sizeof(combined))!=0,"official guard did not reject null input");
            return false;
        }
        return c.seal_aes256_gcm(k,nonce,aad,p,out,tag);
    }
    bool open_aes256_gcm(const Key32& k,const Nonce12& n,const Bytes& a,const Bytes& p,const GcmTag& t,Bytes& o)override{return c.open_aes256_gcm(k,n,a,p,t,o);}
};
}
int main(int argc,char** argv){try{
    Identity identity;PsaCommissioningCrypto psa(identity);check(psa.ready(),"PSA init failed");
    const auto shared=gs::qualification::check_node_empty_aead(psa);
    check(shared.passed,shared.stage);
    std::cout<<"NODE EMPTY AEAD SHARED CHECKS PASS checks="<<shared.checks<<"\n";
    Guard crypto(psa);Key32 wrap{};check(crypto.random_bytes(wrap.data(),wrap.size()),"RNG failed");
    EphemeralP256 node{},hub{};check(crypto.generate_ephemeral(node)&&crypto.generate_ephemeral(hub),"P256 failed");
    CommissioningBinding b;b.device_id="c3-test";b.hub_id="hub-test";b.home_id="home-test";b.logical_id="pir";b.room="test";b.function="pir";b.device_public_key=node.public_key;b.hub_public_key=hub.public_key;check(crypto.random_bytes(b.installation_key.data(),b.installation_key.size()),"installation RNG");
    Store store;AssociationRepository repo(crypto,store,wrap);check(repo.save_initial(b),"paired save failed");const auto old=store.blob;const auto writes=store.writes;
    check(!repo.factory_reset(),"accelerated null-input fault not reproduced");
    check(crypto.observed_plain==0&&crypto.observed_aad==28&&store.blob==old&&store.writes==writes,"failed reset changed persistence");
    check(repo.load().status==AssociationStatus::Paired&&repo.load().generation==1,"failed reset revoked association");
    crypto.accelerated=false;
    store.fail=true;check(!repo.factory_reset()&&store.blob==old,"write fault not fail closed");store.fail=false;
    check(repo.factory_reset(),"software PSA reset failed");
    check(store.blob.size()==44&&store.blob[4]==1&&store.blob[5]==2,"reset format changed");
    AssociationRepository reboot(psa,store,wrap);const auto reset=reboot.load();
    check(reset.status==AssociationStatus::Unpaired&&reset.generation==2&&!reset.binding,"reset authentication/reboot failed");
    const auto tombstone=store.blob;const auto count=store.writes;
    check(reboot.factory_reset()&&store.writes==count,"reset rerun was not idempotent");
    store.blob[13]^=1;check(reboot.load().status==AssociationStatus::Corrupt,"AAD forgery accepted");store.blob=tombstone;
    store.blob.back()^=1;check(reboot.load().status==AssociationStatus::Corrupt,"tag forgery accepted");store.blob=tombstone;
    auto wrong=wrap;wrong[0]^=1;AssociationRepository wrong_repo(psa,store,wrong);check(wrong_repo.load().status==AssociationStatus::Corrupt,"wrong key accepted");
    check(reboot.save_initial(b)&&reboot.load().generation==3,"reenrollment generation failed");
    uint8_t tag_only[16]{};check(idf_gcm_pointer_guard(tag_only,0,nullptr,0)!=0,"empty-output restore incompatibility not reproduced");
    if(argc==2){
        std::ifstream input(argv[1],std::ios::binary);check(bool(input),"missing offline records");
        auto u=[&](){uint32_t value=0;input.read(reinterpret_cast<char*>(&value),4);check(bool(input),"truncated offline records");return value;};
        std::map<std::string,Bytes> records;const auto n=u();check(n<128,"record count bound");
        for(unsigned i=0;i<n;++i){auto len=u();check(len<128,"key bound");std::string name(len,' ');input.read(name.data(),len);len=u();check(len<8192,"blob bound");Bytes value(len);input.read(reinterpret_cast<char*>(value.data()),len);check(bool(input),"truncated record");records[name]=value;}
        check(!records.count("gs_node_rec:snapshot"),"post-failure recovery must be missing");
        Key32 actual_wrap{};const auto& value=records.at("gs_security:wrap_key");check(value.size()==32,"wrapping length");std::copy(value.begin(),value.end(),actual_wrap.begin());
        Store copy;copy.blob=records.at("gs_assoc:binding");AssociationRepository partial(psa,copy,actual_wrap);
        check(partial.load().status==AssociationStatus::Paired&&partial.load().generation==1,"actual partial association decode");
        check(partial.factory_reset(),"actual partial association reset");
        check(partial.load().status==AssociationStatus::Unpaired&&partial.load().generation==2,"actual partial reset readback");
        const auto count_before=copy.writes;check(partial.factory_reset()&&copy.writes==count_before,"actual partial idempotency");
        psa.secure_zero(actual_wrap.data(),actual_wrap.size());
        std::cout<<"POSTFAIL NODE SNAPSHOT PASS production PSA authenticated generation 1 -> 2 in memory only\n";
    }
    std::cout<<"FACTORY NODE RESET PASS exact IDF null-input guard / real PSA software reset / generation / reboot / tamper / write fault / idempotency; corrected PSA boundary supports empty reset/load\n";
    return 0;
}catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
