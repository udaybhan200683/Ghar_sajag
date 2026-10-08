#include "host/storage/native_transaction.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>

namespace {
using namespace gs::host::storage::native;
using gs::hub::durable::MemoryBlobStore;
using gs::hub::durable::FaultMode;
using gs::host::security::OpenSslCommissioningCrypto;
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Crash {};
enum class Cut { None, BeforeBank, DuringBank, AfterBank, BeforePublish, DuringPublish, AfterPublish };

// Existing fault store plus one throw to prohibit post-power-cut writes.
class CutStore final : public gs::hub::durable::BlobStore {
public:
    MemoryBlobStore media;Cut cut=Cut::None;
    bool read(const std::string& k,Bytes& b,bool& found) override{return media.read(k,b,found);}
    bool write_immutable(const std::string& k,const Bytes& b) override{return media.write_immutable(k,b);}
    bool replace(const std::string& k,const Bytes& b) override {
        const auto selected=cut;cut=Cut::None;
        if(selected==Cut::BeforeBank)throw Crash{};
        if(selected==Cut::DuringBank)media.inject(FaultMode::PartialWrite);
        const bool okay=media.replace(k,b);
        if(selected==Cut::DuringBank||selected==Cut::AfterBank)throw Crash{};
        return okay;
    }
    bool erase_if_equals(const std::string& k,const Bytes& b) override{return media.erase_if_equals(k,b);}
};

// Fixed-size persistent host authority emulates the explicitly missing trusted
// CAS/freshness primitive. The witness survives Transaction destruction/reboot.
// This is NOT an implementation of that primitive on ESP32 NVS. Real bank data,
// codecs, AEAD/HMAC and report validation are exercised around this boundary.
class TrustedHostAuthority final : public PublicationAuthority {
public:
    MemoryBlobStore media;Bytes witness;Cut cut=Cut::None;bool available=true;
    bool read(Bytes& out) override {
        bool found=false;Bytes head;
        if(!available||!media.read("head",head,found)||head!=witness)return false;
        out=head;return true;
    }
    bool provision(const Bytes& head) override {
        Bytes old;if(!read(old)||!old.empty())return false;
        if(!media.write_immutable("head",head))return false;
        witness=head;return true;
    }
    bool compare_publish(const Bytes& expected,const Bytes& next) override {
        Bytes old;if(!read(old)||old!=expected)return false;
        const auto selected=cut;cut=Cut::None;
        if(selected==Cut::BeforePublish)throw Crash{};
        if(selected==Cut::DuringPublish) {
            media.inject(FaultMode::PartialWrite);media.replace("head",next);throw Crash{};
        }
        const bool okay=media.replace("head",next);
        Bytes check;bool found=false;media.read("head",check,found);
        if(found&&check==next)witness=next;
        if(selected==Cut::AfterPublish)throw Crash{};
        return okay;
    }
};
Key32 key(unsigned value){Key32 k{};k.fill(static_cast<std::uint8_t>(value));return k;}
struct Fixture {
    CutStore blobs;TrustedHostAuthority authority;OpenSslCommissioningCrypto crypto;
    Transaction tx{blobs,crypto,authority,key(0x77),7,32};
    Fixture(){require(tx.provision_fresh(),"explicit native provisioning");}
    Proof enroll(unsigned n) {
        require(tx.enroll(key(10+n),key(30+n))==Result::Committed,"authenticated owner enrollment");
        for(unsigned slot=0;slot<6;++slot)if(tx.state()->owners[slot].binding==key(10+n)) {
            const auto& o=tx.state()->owners[slot];return {static_cast<std::uint8_t>(slot),o.generation,o.binding,10};
        }
        throw std::runtime_error("enrolled owner missing");
    }
    Key32 mac(const Proof& p,std::uint64_t seq,const Bytes& body={0x42}) {
        Key32 m{};Event e{p,1,seq,body};
        require(tx.event_mac(tx.state()->owners[p.slot].report_key,e,m),"event boundary authentication");return m;
    }
    Result admit(const Proof& p,std::uint64_t seq,const Bytes& reducer={0x22},const Bytes& body={0x42}) {
        return tx.admit({p,1,seq,body},mac(p,seq,body),reducer);
    }
    NodeRetirementReportV1 report_value(std::uint64_t generation,std::uint64_t high,
                std::initializer_list<std::uint64_t> pending={}) {
        NodeRetirementReportV1 r;r.epoch=7;r.generation=generation;r.current_origin_session=1;
        r.durable_admission_highwater=high;r.pending_count=pending.size();unsigned i=0;
        for(auto seq:pending)r.pending[i++]={1,seq};
        return r;
    }
    Key32 report_mac(const Proof& p,const NodeRetirementReportV1& r) {
        Bytes logical;Key32 m{};require(gs::transport::encode_retirement_report(r,logical),"report canonical encode");
        require(crypto.hmac_sha256(tx.state()->owners[p.slot].report_key,logical,m),"report HMAC");return m;
    }
    void reboot() { blobs.media.power_cycle();authority.media.power_cycle();require(tx.recover(),"latest native restart"); }
};

void admission_and_reports() {
    Fixture f;const auto p=f.enroll(0);
    for(unsigned s=1;s<=32;++s)require(f.admit(p,s,{static_cast<std::uint8_t>(s)})==Result::Committed,"durable uncovered admit");
    require(f.admit(p,33)==Result::Full,"33rd uncovered admission rejected");
    f.reboot();require(f.tx.state()->owners[0].charged==32&&f.tx.state()->rows.size()==32,"credit persisted on restart");
    const auto gen=f.tx.state()->generation;
    require(f.admit(p,32,{0xee})==Result::Duplicate&&f.tx.state()->generation==gen&&
            f.tx.state()->reducer==Bytes{32},"lost ACK retry has no reducer/credit effects");
    auto rejoin=p;++rejoin.transport_session;
    require(f.admit(rejoin,32,{0xee})==Result::Duplicate,"transport change preserves immutable body digest");
    require(f.admit(p,32,{0xee},{0x43})==Result::Conflict,"same key changed body conflicts");
    auto r=f.report_value(1,0);
    require(f.tx.report(p,r,f.report_mac(p,r))==Result::Committed,"generation only report persists");
    f.reboot();require(f.tx.state()->owners[0].charged==32,"report generation does not refill");
    require(f.tx.report(p,r,f.report_mac(p,r))==Result::Duplicate,"repeated authenticated report idempotent");
    auto bad=r;bad.durable_admission_highwater=32;
    require(f.tx.report(p,bad,key(0xfa))==Result::Invalid,"forged report rejected");
    require(f.tx.report(p,bad,f.report_mac(p,bad))==Result::Conflict,"same report generation conflict");
    r=f.report_value(2,32,{1});
    require(f.tx.report(p,r,f.report_mac(p,r))==Result::Committed,"complete report retirement selected");
    f.reboot();require(f.tx.state()->owners[0].charged==0&&f.tx.state()->rows.size()==32,"retry credit independent of backend/local body");
    require(f.admit(p,1)==Result::Duplicate,"accepted pending identity remains");
    require(f.admit(p,33)==Result::Committed,"real report progress restores uncovered capacity");
    auto resurrect=f.report_value(3,32,{2});
    require(f.tx.report(p,resurrect,f.report_mac(p,resurrect))==Result::Conflict,"retired identity cannot resurrect");
    auto wrong=p;wrong.binding=key(99);
    require(f.tx.report(wrong,r,f.report_mac(p,r))==Result::Invalid,"foreign owner proof rejected");
    require(!f.tx.observation_available(),"restart does not imply observation coverage");
    std::cout<<"ADMISSION_REPORT_PASS W=32 credit_reboot=32 report_progress=only_auth_complete forged=reject\n";
}

void owner_bound_and_revocation() {
    Fixture f;std::array<Proof,6> owners{};for(unsigned n=0;n<6;++n)owners[n]=f.enroll(n);
    require(f.tx.enroll(key(99),key(98))==Result::Full,"seventh owner rejected");
    const auto p=owners[0];require(f.admit(p,1)==Result::Committed,"revocation seed");
    require(f.tx.revoke(p)==Result::Committed,"retiring owner persists");f.reboot();
    require(f.admit(p,1)==Result::Duplicate&&f.admit(p,2)==Result::Retired,"revoked retry is effect-free, new event refused");
    require(f.tx.enroll(key(99),key(98))==Result::Full,"retiring owner still consumes slot");
    require(f.tx.release_owner(p)==Result::Full,"revocation cannot forget live identity");
    require(f.tx.dependencies_complete(p,1,1,true,true)==Result::Committed,"consumer completion before report");
    require(f.tx.state()->rows.size()==1,"retry dependency still pins body");
    auto pending=f.report_value(1,1,{1});
    require(f.tx.report(p,pending,f.report_mac(p,pending))==Result::Committed,"retiring owner can report");
    require(f.tx.release_owner(p)==Result::Full,"pending report prevents release");
    auto drained=f.report_value(2,1);
    require(f.tx.report(p,drained,f.report_mac(p,drained))==Result::Committed,"complete drained report");
    require(f.tx.state()->rows.empty()&&f.tx.release_owner(p)==Result::Committed,"safe owner release only after all dependencies");
    const auto replacement=f.enroll(6);require(replacement.generation>p.generation,"generation never reused");
    require(f.tx.admit({p,1,1,{0x42}},key(1),{0xff})==Result::Invalid,"old enrollment delayed retry not new owner");
    f.reboot();require(f.tx.state()->owners[0].generation==replacement.generation,"replacement fence durable");
    std::cout<<"OWNER_BOUND_PASS retained=6 seventh=Full retiring=charged release=dependency_gated\n";
}

void full_identity_bound() {
    Fixture f;
    const Bytes maximum_body(gs::hub::durable::kMaxCausalInputBytes,0x42);
    const Bytes maximum_reducer(kReducerBytes,0x22);
    for(unsigned n=0;n<6;++n) {
        const auto p=f.enroll(n);auto r=f.report_value(1,32);r.pending_count=32;
        for(unsigned s=1;s<=32;++s)r.pending[s-1]={1,s};
        require(f.tx.report(p,r,f.report_mac(p,r))==Result::Committed,"full pending report");
        for(unsigned s=1;s<=64;++s)require(f.admit(p,s,maximum_reducer,maximum_body)==Result::Committed,"full six-owner flight");
        require(f.admit(p,65)==Result::Full,"per-owner window full");
    }
    f.reboot();require(f.tx.state()->rows.size()==384&&f.tx.identity_bound()==384,"durable six*(32+W) bound");
    for(const auto& o:f.tx.state()->owners)require(o.charged==32,"all six credit counts recovered");
    Bytes published,bank;bool found=false;require(f.authority.read(published),"max snapshot authority");
    require(f.blobs.read("hn_bank"+std::to_string(published[18]),bank,found)&&found&&
            bank.size()==Transaction::maximum_bank_bytes(),"maximum serialized bank exact bound");
    std::cout<<"FULL_BOUND_PASS exact_identities=384 owners=6 W=32 fixed_keys=2 banks_max_bytes="
             <<Transaction::maximum_bank_bytes()<<" authority_bytes="<<Transaction::head_bytes<<'\n';
}

// A correctly authenticated but internally contradictory checkpoint represents
// a producer/credit-serialization fault. Re-seal with synthetic fixture keys so
// validation must catch inconsistency, rather than merely reject an AEAD tag.
void authenticated_credit_contradiction() {
    Fixture f;const auto p=f.enroll(0);require(f.admit(p,1)==Result::Committed,"credit contradiction seed");
    Bytes published,bank;bool found=false;require(f.authority.read(published),"credit authority");
    const auto name="hn_bank"+std::to_string(published[18]);
    require(f.blobs.read(name,bank,found)&&found,"credit bank");
    gs::security::Nonce12 nonce{};gs::security::GcmTag tag{};
    std::copy_n(bank.begin(),12,nonce.begin());std::copy_n(bank.end()-16,16,tag.begin());
    const char aad_text[]="GS-HOST-NATIVE-BANK-v1";
    Bytes aad(aad_text,aad_text+sizeof(aad_text)-1),plain,cipher(bank.begin()+12,bank.end()-16);
    require(f.crypto.open_aes256_gcm(key(0x77),nonce,aad,cipher,tag,plain),"open synthetic credit fixture");
    require(plain.size()>102&&plain[102]==1,"serialized credit offset bound");
    plain[102]=0; // Accepted uncovered key still exists; persisted credit falsely reset.
    const auto generation=f.tx.state()->generation+1;
    for(unsigned i=0;i<8;++i) {
        plain[11+i]=static_cast<std::uint8_t>(generation>>(8*(7-i)));
        published[10+i]=plain[11+i];
    }
    require(f.crypto.random_bytes(nonce.data(),nonce.size())&&
        f.crypto.seal_aes256_gcm(key(0x77),nonce,aad,plain,cipher,tag),"seal contradictory authenticated bank");
    bank.assign(nonce.begin(),nonce.end());bank.insert(bank.end(),cipher.begin(),cipher.end());
    bank.insert(bank.end(),tag.begin(),tag.end());require(f.blobs.media.replace(name,bank),"install contradictory bank");
    Key32 digest{};require(f.crypto.hmac_sha256(key(0x77),bank,digest),"contradictory bank binding");
    std::copy(digest.begin(),digest.end(),published.begin()+19);
    const char head_domain[]="GS-HOST-NATIVE-PUBLICATION-v1";
    Bytes message(head_domain,head_domain+sizeof(head_domain)-1);
    message.insert(message.end(),published.begin(),published.end()-32);
    require(f.crypto.hmac_sha256(key(0x77),message,digest),"authenticate contradictory publication");
    std::copy(digest.begin(),digest.end(),published.end()-32);
    Bytes old;require(f.authority.read(old)&&f.authority.compare_publish(old,published),"trusted publication fixture advance");
    require(!f.tx.recover()&&!f.tx.state(),"authenticated inconsistent credit metadata fails closed");
    std::cout<<"CREDIT_CONTRADICTION_PASS valid_aead_and_head=1 false_credit_reset=fail_closed\n";
}

void crash_points() {
    for(const auto cut:{Cut::BeforeBank,Cut::DuringBank,Cut::AfterBank,Cut::BeforePublish,Cut::DuringPublish,Cut::AfterPublish}) {
        Fixture f;const auto p=f.enroll(0);require(f.tx.checkpoint_reducer({0x11})==Result::Committed,"old reducer state");
        const auto oldgen=f.tx.state()->generation;const auto eventmac=f.mac(p,1);
        f.blobs.cut=cut<=Cut::AfterBank?cut:Cut::None;
        f.authority.cut=cut>=Cut::BeforePublish?cut:Cut::None;
        bool notified=false,crashed=false;
        try { notified=f.tx.admit({p,1,1,{0x42}},eventmac,{0x22})==Result::Committed; }
        catch(const Crash&){crashed=true;}
        require(crashed&&!notified,"power interruption never notifies ACK");
        f.blobs.media.power_cycle();f.authority.media.power_cycle();
        Transaction reboot(f.blobs,f.crypto,f.authority,key(0x77),7,32);
        const bool recovered=reboot.recover();
        if(cut==Cut::DuringPublish) {
            require(!recovered&&!reboot.state(),"torn authority fails closed with old bank present");
            require(reboot.admit({p,1,1,{0x42}},eventmac,{0x22})==Result::Invalid,"failed recovery cannot ACK");
        } else {
            require(recovered,"old or committed latest state recovers");
            const bool committed=cut==Cut::AfterPublish;
            require(reboot.state()->generation==oldgen+(committed?1:0)&&
                reboot.state()->reducer==Bytes{static_cast<std::uint8_t>(committed?0x22:0x11)}&&
                reboot.state()->rows.size()==(committed?1U:0U)&&
                reboot.state()->owners[0].charged==(committed?1:0),"reducer/body/credit recovery atomic");
            require(reboot.admit({p,1,1,{0x42}},eventmac,{0x22})==
                (committed?Result::Duplicate:Result::Committed),"reboot retry exact effect semantics");
        }
        std::cout<<"CRASH_PASS cut="<<static_cast<unsigned>(cut)<<" recovery="<<(recovered?"valid":"fail_closed")<<" notification=none\n";
    }
}

void root_and_credit_damage() {
    for(bool missing:{false,true}) {
        Fixture f;f.enroll(0);
        require(f.tx.checkpoint_reducer({0x11})==Result::Committed,"regression old reducer");
        require(f.tx.checkpoint_reducer({0x22})==Result::Committed,"regression new reducer");
        Bytes head;require(f.authority.read(head),"published authority read");
        const unsigned bank=head[18];Bytes blob;bool found=false;const auto name="hn_bank"+std::to_string(bank);
        require(f.blobs.read(name,blob,found)&&found,"latest checkpoint child exists");
        if(missing)require(f.blobs.erase_if_equals(name,blob),"missing latest child fixture");
        else {blob.back()^=1;require(f.blobs.media.replace(name,blob),"corrupt latest credit/checkpoint tag");}
        require(!f.tx.recover()&&!f.tx.state(),"exact stale-root regression now fails closed");
        require(f.tx.checkpoint_reducer({0xff})==Result::Invalid,"no mutation after failed recovery");
        std::cout<<"STALE_ROOT_REGRESSION_PASS child="<<(missing?"missing":"corrupt")<<" old_bank_present=1 fallback=forbidden\n";
    }
    Fixture f;const auto p=f.enroll(0);Bytes oldhead;require(f.authority.read(oldhead),"save prior authentic head");
    require(f.admit(p,1)==Result::Committed,"published event before authority rollback");
    require(f.authority.media.replace("head",oldhead),"restore old authentic authority bytes fixture");
    require(!f.tx.recover(),"trusted witness detects whole authentic-head rollback");
    f.authority.available=false;require(!f.tx.recover(),"missing freshness primitive fails closed");
    Fixture missing;Bytes selected;require(missing.authority.read(selected)&&
        missing.authority.media.erase_if_equals("head",selected),"delete authority fixture");
    require(!missing.tx.recover()&&!missing.tx.provision_fresh(),"missing published authority never triggers fresh initialization");
    Fixture incompatible;
    Transaction wrong_window(incompatible.blobs,incompatible.crypto,incompatible.authority,key(0x77),7,31);
    Transaction wrong_epoch(incompatible.blobs,incompatible.crypto,incompatible.authority,key(0x77),8,32);
    require(!wrong_window.recover()&&!wrong_epoch.recover(),"authenticated format/configuration context is exact");
    std::cout<<"FRESHNESS_PRIMITIVE_PASS old_authenticated_head=reject unavailable_authority=fail_closed\n";
}

void retirement_crash_points() {
    for(const auto cut:{Cut::AfterBank,Cut::AfterPublish}) {
        Fixture f;const auto p=f.enroll(0);require(f.admit(p,1)==Result::Committed,"retirement crash accepted input");
        const auto r=f.report_value(1,1);const auto mac=f.report_mac(p,r);
        f.blobs.cut=cut==Cut::AfterBank?cut:Cut::None;
        f.authority.cut=cut==Cut::AfterPublish?cut:Cut::None;
        bool notified=false;
        try {notified=f.tx.report(p,r,mac)==Result::Committed;}
        catch(const Crash&){}
        require(!notified,"crashed retirement not notified");f.reboot();
        const bool selected=cut==Cut::AfterPublish;
        require(f.tx.state()->rows.size()==1&&f.tx.state()->rows[0].retry==!selected&&
            f.tx.state()->owners[0].charged==(selected?0:1),"report selection and credit recovery atomic");
        require(f.tx.report(p,r,mac)==(selected?Result::Duplicate:Result::Committed),"lost report ACK replay idempotent");
        std::cout<<"RETIREMENT_CRASH_PASS cut="<<static_cast<unsigned>(cut)<<" accepted_body=preserved credit="<<(selected?0:1)<<'\n';
    }
}

void write_failures_and_dependencies() {
    Fixture f;const auto p=f.enroll(0);const auto oldgen=f.tx.state()->generation;
    f.blobs.media.inject(FaultMode::FailBeforeWrite);
    require(f.admit(p,1)==Result::Fault,"insufficient-space/IO failure not ACKed");f.reboot();
    require(f.tx.state()->generation==oldgen&&f.tx.state()->rows.empty(),"failed candidate preserves selected root");
    f.blobs.media.inject(FaultMode::PartialWrite);
    require(f.admit(p,1)==Result::Fault,"partial credit metadata rejected");f.reboot();
    require(f.tx.state()->generation==oldgen,"partial inactive candidate never authority");
    f.blobs.media.inject(FaultMode::PersistThenFail);
    require(f.admit(p,1)==Result::Committed,"candidate API ambiguity resolved through exact bytes");
    f.authority.media.inject(FaultMode::PersistThenFail);
    require(f.admit(p,2)==Result::Committed,"publication API ambiguity resolved through trusted read");
    auto r=f.report_value(1,2);require(f.tx.report(p,r,f.report_mac(p,r))==Result::Committed,"retry identity retirement");
    require(f.tx.state()->rows.size()==2,"retired identity does not release backend/local inputs");
    require(f.tx.dependencies_complete(p,1,1,true,false)==Result::Committed,"local owner completion");
    f.reboot();require(f.tx.state()->rows.size()==2&&f.tx.state()->rows[0].backend,"backend owner still protects journal body");
    require(f.tx.dependencies_complete(p,1,1,false,true)==Result::Committed,"durable backend completion assertion boundary");
    f.reboot();require(f.tx.state()->rows.size()==1&&f.tx.state()->rows[0].sequence==2,"only fully released row reclaimed");
    require(f.admit(p,1)==Result::Retired,"retired/reclaimed identity not re-applied");
    std::cout<<"DEPENDENCY_FAILURE_PASS no_unsafe_reclaim=1 api_ambiguity=resolved partial_credit=not_selected\n";
}
}
int main() {
    try {
        admission_and_reports();owner_bound_and_revocation();full_identity_bound();
        crash_points();root_and_credit_damage();retirement_crash_points();
        authenticated_credit_contradiction();write_failures_and_dependencies();
        std::cout<<"NATIVE_TRANSACTION_HOST_PASS gate_A=PASS_DEFINED_SCOPE gate_B=PASS_WITH_TRUSTED_AUTHORITY gate_C=OPEN\n";
    } catch(const std::exception& e) {std::cerr<<"NATIVE_TRANSACTION_HOST_FAIL "<<e.what()<<'\n';return 1;}
}
