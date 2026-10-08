// Executable NVS mapping experiment. Ordinary single-writer flash publication
// below is deliberately NOT the non-rollback native PublicationAuthority.
// The intact-image replay case demonstrates the missing primitive.
#include "host/storage/compact_nvs_representation.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <sys/wait.h>

namespace compact_sdk {
using namespace gs::host::storage::native;
using gs::host::security::OpenSslCommissioningCrypto;
Key32 key(unsigned v){Key32 k{};k.fill(v);return k;}
class Store final : public CompactObjectStore {
public:
    nvs_handle_t h{};esp_err_t error=ESP_OK,last_write_error=ESP_OK;
    unsigned writes=0;std::size_t payload_written=0;
    bool protected_space=false;
    SpaceOutcome outcome=SpaceOutcome::Ready;
    Workspace reservation{};
    std::size_t certified_free=0, plan_index=0;
    std::vector<std::size_t> planned_blobs;
    enum class RefuseIO { None, Immutable, Manifest, Head };
    RefuseIO refuse_io=RefuseIO::None; // Explicit API refusal, NOT a power cut.
    bool prepare_publication(const PublicationPlan& plan) override {
        if(!protected_space)return true;
        outcome=SpaceOutcome::Ready;plan_index=0;planned_blobs.clear();
        reservation=workspace(plan);
        // Protect the bounded reducer-object slot as well as physical pages.
        // Failed publications can leave authenticated but unselected orphans.
        if(plan.event_objects_after>CompactRepresentation::event_objects||
           plan.reducer_objects_after+unsigned(plan.ordinary_admission)>
               CompactRepresentation::reducer_objects) {
            outcome=SpaceOutcome::InsufficientProtectedSpace;return false;
        }
        // Read-only physical certificate. NVS has already completed mount and
        // recovery; every namespace on this partition shares the writer lock.
        // An activated, lazily initialized page can still be entirely 0xff.
        // Subtract one such page, never counting garbage/corrupt/torn pages.
        if(!diag::part||diag::part->size%4096||diag::part->size<131072||
           diag::part->size>262144) {
            outcome=SpaceOutcome::UnsupportedConfiguration;return false;
        }
        std::array<std::uint8_t,4096> raw{};std::size_t erased=0;
        for(std::size_t at=0;at<diag::part->size;at+=raw.size()) {
            if(esp_partition_read_raw(diag::part,at,raw.data(),raw.size())!=ESP_OK) {
                outcome=SpaceOutcome::IntegrityRecoveryFailure;return false;
            }
            erased+=std::all_of(raw.begin(),raw.end(),[](auto b){return b==255;});
        }
        certified_free=erased?erased-1:0;
        if(certified_free<reservation.required_free_pages) {
            outcome=SpaceOutcome::InsufficientProtectedSpace;return false;
        }
        planned_blobs=plan.blobs;return true;
    }
    SpaceOutcome result(Result r) {
        if(r==Result::Committed)return outcome=SpaceOutcome::Committed;
        if(r==Result::Duplicate)return outcome=SpaceOutcome::Duplicate;
        if(r==Result::Full)return outcome=SpaceOutcome::AdmissionLimit;
        if(r!=Result::Fault)return outcome=SpaceOutcome::InvalidRequest;
        if(outcome==SpaceOutcome::Ready)outcome=SpaceOutcome::IntegrityRecoveryFailure;
        return outcome;
    }
    void open(){REQUIRE(nvs_open_from_partition("life","compact",NVS_READWRITE,&h)==ESP_OK);}
    void close(){nvs_close(h);h=0;}
    static std::string mapped(const std::string& k) {
        if(k=="hn_bank0")return "cb0";
        if(k=="hn_bank1")return "cb1";
        return k;
    }
    bool read(const std::string& k,Bytes& b,bool& found) override {
        const auto name=mapped(k);size_t n=0;error=nvs_get_blob(h,name.c_str(),nullptr,&n);
        found=error==ESP_OK;if(error==ESP_ERR_NVS_NOT_FOUND){b.clear();return true;}
        if(error!=ESP_OK||n>Transaction::maximum_bank_bytes())return false;
        b.resize(n);error=nvs_get_blob(h,name.c_str(),b.data(),&n);return error==ESP_OK&&n==b.size();
    }
    bool replace(const std::string& k,const Bytes& b) override {
        if(protected_space) {
            if(plan_index>=planned_blobs.size()||planned_blobs[plan_index++]!=b.size()) {
                outcome=SpaceOutcome::IntegrityRecoveryFailure;return false;
            }
            const bool metadata=k=="head"||k=="hn_bank0"||k=="hn_bank1";
            if((refuse_io==RefuseIO::Immutable&&!metadata)||
               (refuse_io==RefuseIO::Manifest&&k.starts_with("hn_bank"))||
               (refuse_io==RefuseIO::Head&&k=="head")) {
                error=last_write_error=ESP_ERR_FLASH_OP_FAIL;
                outcome=metadata?SpaceOutcome::MetadataPublicationFailure:SpaceOutcome::RestartRequired;
                return false;
            }
        }
        ++writes;payload_written+=b.size();const auto name=mapped(k);
        error=nvs_set_blob(h,name.c_str(),b.data(),b.size());
        if(error==ESP_OK)error=nvs_commit(h);
        last_write_error=error;
        if(protected_space&&error!=ESP_OK)outcome=
            (k=="head"||k=="hn_bank0"||k=="hn_bank1")?
            SpaceOutcome::MetadataPublicationFailure:SpaceOutcome::RestartRequired;
        return error==ESP_OK;
    }
    bool write_immutable(const std::string& k,const Bytes& b) override {
        Bytes old;bool found=false;if(!read(k,old,found))return false;
        if(found)return old==b;
        return replace(k,b);
    }
    bool erase_if_equals(const std::string& k,const Bytes& expected) override {
        Bytes old;bool found=false;if(!read(k,old,found)||!found||old!=expected)return false;
        const auto name=mapped(k);error=nvs_erase_key(h,name.c_str());
        return error==ESP_OK&&nvs_commit(h)==ESP_OK;
    }
    bool objects(std::vector<std::string>& out) override {
        out.clear();nvs_iterator_t it=nullptr;
        auto rc=nvs_entry_find("life","compact",NVS_TYPE_BLOB,&it);
        while(rc==ESP_OK) {
            nvs_entry_info_t info{};nvs_entry_info(it,&info);
            if((info.key[0]=='e'||info.key[0]=='r')&&std::strlen(info.key)==15)out.emplace_back(info.key);
            if(out.size()>CompactRepresentation::event_objects+CompactRepresentation::reducer_objects) {
                nvs_release_iterator(it);return false;
            }
            rc=nvs_entry_next(&it);
        }
        nvs_release_iterator(it);return rc==ESP_ERR_NVS_NOT_FOUND;
    }
};
class OrdinaryFlashAuthority final : public PublicationAuthority {
public:
    Store& s;bool factory;
    OrdinaryFlashAuthority(Store& store,bool fresh=false):s(store),factory(fresh){}
    bool read(Bytes& b) override {bool found=false;return s.read("head",b,found)&&(found||factory);}
    bool provision(const Bytes& b) override {
        Bytes old;if(!factory||!read(old)||!old.empty())return false;
        factory=false;return s.write_immutable("head",b);
    }
    bool compare_publish(const Bytes& expected,const Bytes& next) override {
        // Serialized writer read/replace/read, NOT NVS multi-key CAS or trusted
        // monotonic storage. A valid older flash image passes this interface.
        Bytes old;if(!read(old)||old!=expected)return false;
        (void)s.replace("head",next);Bytes check;return read(check)&&check==next;
    }
};
struct Fixture {
    Store s;OpenSslCommissioningCrypto crypto;OrdinaryFlashAuthority a;
    CompactRepresentation compact;Transaction tx;
    Fixture(bool fresh):a(s,fresh),compact(s,crypto,key(0x77),7),tx(s,crypto,a,key(0x77),7,32,&compact) {
        s.open();REQUIRE(fresh?tx.provision_fresh():tx.recover());
    }
    ~Fixture(){s.close();}
    void collect(){REQUIRE(tx.state()!=nullptr&&compact.collect_selected(*tx.state()));}
    Proof enroll(unsigned n) {
        REQUIRE(tx.enroll(key(10+n),key(30+n))==Result::Committed);collect();
        const auto& o=tx.state()->owners[n];return {static_cast<std::uint8_t>(n),o.generation,o.binding,10};
    }
    Result admit(const Proof& p,unsigned seq,const Bytes& body,const Bytes& reducer) {
        s.outcome=SpaceOutcome::Ready;
        Event e{p,1,seq,body};Key32 mac{};
        REQUIRE(tx.event_mac(key(30+p.slot),e,mac));return tx.admit(e,mac,reducer);
    }
    Result report(const Proof& p,unsigned gen,unsigned high,bool pending=false) {
        s.outcome=SpaceOutcome::Ready;
        NodeRetirementReportV1 r;r.epoch=7;r.generation=gen;r.current_origin_session=1;
        r.durable_admission_highwater=high;Bytes bytes;Key32 mac{};
        if(pending){r.pending_count=32;for(unsigned i=0;i<32;++i)r.pending[i]={1,i+1};}
        REQUIRE(gs::transport::encode_retirement_report(r,bytes));
        REQUIRE(crypto.hmac_sha256(key(30+p.slot),bytes,mac));return tx.report(p,r,mac);
    }
};
std::size_t payload(Store& s) {
    std::vector<std::string> keys;REQUIRE(s.objects(keys));
    keys.insert(keys.end(),{"hn_bank0","hn_bank1","head"});std::size_t n=0;
    for(const auto& k:keys){Bytes b;bool found=false;REQUIRE(s.read(k,b,found));if(found)n+=b.size();}return n;
}
void remount(const esp_partition_t* p) {
    REQUIRE(nvs_flash_deinit_partition("life")==ESP_OK);
    REQUIRE(nvs_flash_init_partition_ptr(p)==ESP_OK);
}
void prime_gc(Store& s) {
    unsigned count=0;for(;count<64;++count) {
        if(!s.replace("pad"+std::to_string(count),Bytes(4096,count)))break;
    }
    REQUIRE(count>=10);
    for(unsigned i=0;i<count;i+=2) {
        Bytes b;bool found=false;const auto k="pad"+std::to_string(i);
        REQUIRE(s.read(k,b,found)&&found&&s.erase_if_equals(k,b));
    }
    std::printf("COMPACT_GC_PRIME pads=%u\n",count);
}
}

#include "protected_probe.hpp"

int compact_probe(int argc,char** argv) {
    using namespace compact_sdk;
    const std::string mode=argc>2?argv[2]:"basic";
    const auto* original=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_NVS,"life");
    REQUIRE(original);auto part=*original;
    if(const auto* n=std::getenv("GS_DIAG_PAGES"))part.size=std::strtoul(n,nullptr,10)*4096;
    REQUIRE(part.size>=131072&&part.size<=262144);pages=part.size/4096;diag::part=&part;
    REQUIRE(esp_partition_erase_range(&part,0,part.size)==ESP_OK);
    REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);
    if(mode=="gmax")return protected_max_report_probe(&part);
    if(mode=="gio")return protected_io_probe();
    if(mode=="guard"||mode=="guardfull"||mode=="guardbusy")return protected_probe(&part,mode=="guardfull",
        argc>3?std::strtoul(argv[3],nullptr,10):448,mode=="guardbusy");
    Proof owner;std::uint64_t baseline=0;Bytes flash;
    {
        Fixture f(true);owner=f.enroll(0);
        if(mode=="basic") {
            for(unsigned n=1;n<=32;++n){REQUIRE(f.admit(owner,n,Bytes(36,0x42),Bytes{0x22})==Result::Committed);f.collect();}
            REQUIRE(f.admit(owner,33,Bytes(36,0x42),Bytes{0x22})==Result::Full);
            REQUIRE(f.tx.recover()&&f.tx.state()->owners[0].charged==32);
            const auto writes=f.s.writes;
            REQUIRE(f.admit(owner,32,Bytes(36,0x42),Bytes{0xee})==Result::Duplicate&&f.s.writes==writes);
            REQUIRE(f.report(owner,1,32)==Result::Committed);f.collect();
            REQUIRE(f.tx.recover()&&f.tx.state()->owners[0].charged==0&&f.tx.state()->rows.size()==32);
            REQUIRE(f.report(owner,1,32)==Result::Duplicate);
            REQUIRE(f.tx.dependencies_complete(owner,1,1,true,false)==Result::Committed);f.collect();
            REQUIRE(f.tx.state()->rows.size()==32); // backend still owns body
            REQUIRE(f.tx.dependencies_complete(owner,1,1,false,true)==Result::Committed);f.collect();
            REQUIRE(f.tx.state()->rows.size()==31);
            for(unsigned n=1;n<6;++n)f.enroll(n);
            REQUIRE(f.tx.enroll(key(99),key(98))==Result::Full);
            REQUIRE(f.tx.revoke(owner)==Result::Committed);f.collect();
            REQUIRE(f.admit(owner,32,Bytes(36,0x42),Bytes{0xee})==Result::Duplicate);
            REQUIRE(f.admit(owner,33,Bytes(36,0x42),Bytes{0xee})==Result::Retired);
            std::printf("COMPACT_BASIC_PASS credit_reports_lost_ack_dependency_owners_revocation payload=%zu\n",payload(f.s));
            metric("compact_basic",32,&part);return 0;
        }
        REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x11))==Result::Committed);f.collect();
        baseline=f.tx.state()->generation;
        if(mode=="capacity") {
            std::array<Proof,6> owners{};owners[0]=owner;
            for(unsigned i=1;i<6;++i)owners[i]=f.enroll(i);
            for(const auto& p:owners){REQUIRE(f.report(p,1,32,true)==Result::Committed);f.collect();}
            const unsigned bytes=argc>3?std::strtoul(argv[3],nullptr,10):448;REQUIRE(bytes<=448);
            unsigned admitted=0;bool stopped=false;
            for(const auto& p:owners) {
                for(unsigned seq=1;seq<=64;++seq) {
                    const auto r=f.admit(p,seq,Bytes(bytes,0x42),Bytes(4096,0x11));
                    if(r!=Result::Committed){stopped=true;break;}++admitted;f.collect();
                }
                if(stopped)break;
            }
            REQUIRE(f.tx.recover()&&f.tx.state()->rows.size()==admitted);
            std::printf("COMPACT_CAPACITY pages=%u body=%u admitted=%u target=384 payload=%zu guard=UNPROVEN\n",pages,bytes,admitted,payload(f.s));
            metric("compact_capacity",admitted,&part);return 0;
        }
        if(mode=="rfault") {
            REQUIRE(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x11))==Result::Committed);f.collect();
            baseline=f.tx.state()->generation;
        }
        if(mode=="cfault") {
            REQUIRE(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x11))==Result::Committed);f.collect();
            REQUIRE(f.report(owner,1,1)==Result::Committed);
            REQUIRE(f.tx.dependencies_complete(owner,1,1,true,true)==Result::Committed);
            REQUIRE(f.admit(owner,2,Bytes(448,0x42),Bytes(4096,0x22))==Result::Committed);
            baseline=f.tx.state()->generation; // leave old unreferenced objects for collection
        }
        if(mode=="rollback") {
            flash.resize(part.size);REQUIRE(esp_partition_read(&part,0,flash.data(),flash.size())==ESP_OK);
            REQUIRE(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22))==Result::Committed);f.collect();
            REQUIRE(f.tx.state()->generation==baseline+1);
        } else if(mode=="damage"||mode=="missing"||mode=="child"||mode=="head"||mode=="dupmissing"||mode=="reportmissing") {
            REQUIRE(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22))==Result::Committed);
            if(mode=="reportmissing")REQUIRE(f.report(owner,1,1)==Result::Committed);
            // Older bank bytes remain. Selected dependency loss forbids fallback.
            Bytes head;REQUIRE(f.a.read(head));const auto bank=head[18];
            Bytes b;bool found=false;const auto k="hn_bank"+std::to_string(bank);
            REQUIRE(f.s.read(k,b,found)&&found);
            if(mode=="damage"){b.back()^=1;REQUIRE(f.s.replace(k,b));}
            else if(mode=="missing"){REQUIRE(f.s.erase_if_equals(k,b));}
            else if(mode=="head"){REQUIRE(f.s.erase_if_equals("head",head));}
            else if(mode=="dupmissing"||mode=="reportmissing") {
                std::vector<std::string> objects;REQUIRE(f.s.objects(objects));
                for(const auto& object:objects)if(object[0]=='e') {
                    Bytes body;bool exists=false;REQUIRE(f.s.read(object,body,exists)&&exists);
                    REQUIRE(f.s.erase_if_equals(object,body));
                }
                const auto writes=f.s.writes;
                REQUIRE((mode=="reportmissing"?f.report(owner,1,1):
                    f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22)))==Result::Fault);
                REQUIRE(!f.tx.state()&&f.s.writes==writes);
            }
            else {
                // Remove only new reducer dependency; keep the older complete bank.
                std::vector<std::string> objects;REQUIRE(f.s.objects(objects));
                for(const auto& object:objects)if(object[0]=='r') {
                    Bytes old;bool exists=false;REQUIRE(f.s.read(object,old,exists)&&exists);
                    // Open with the exact object AAD to identify the new checkpoint.
                    gs::security::Nonce12 nonce{};gs::security::GcmTag tag{};
                    std::copy_n(old.begin(),12,nonce.begin());std::copy_n(old.end()-16,16,tag.begin());
                    Bytes plain,aad;const std::string label="GS-COMPACT-NVS-OBJECT-v1";
                    aad.assign(label.begin(),label.end());aad.insert(aad.end(),{'r',0,0,0,7});
                    REQUIRE(f.crypto.open_aes256_gcm(key(0x77),nonce,aad,Bytes(old.begin()+12,old.end()-16),tag,plain));
                    if(plain==Bytes(4096,0x22))REQUIRE(f.s.erase_if_equals(object,old));
                }
            }
            REQUIRE(!f.tx.recover()&&!f.tx.state());
            std::printf("COMPACT_FAIL_CLOSED_PASS mode=%s older_bank_present=1\n",mode.c_str());return 0;
        } else if(mode=="pressure") {
            REQUIRE(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x11))==Result::Committed);f.collect();
            baseline=f.tx.state()->generation;
            unsigned n=0;for(;n<64;++n)if(!f.s.replace("pad"+std::to_string(n),Bytes(4096,n)))break;
            const auto saved=payload(f.s);
            for(unsigned attempt=0;attempt<3;++attempt) {
                const auto result=f.admit(owner,2,Bytes(448,0x42),Bytes(4096,0x22));
                std::printf("COMPACT_PRESSURE_ATTEMPT result=%u write_error=%s\n",unsigned(result),esp_err_to_name(f.s.last_write_error));
                REQUIRE(result!=Result::Committed&&f.tx.recover());
                REQUIRE(f.tx.state()->generation==baseline&&f.tx.state()->rows.size()==1&&
                    f.tx.state()->owners[0].charged==1&&f.tx.state()->rows[0].body==Bytes(448,0x42)&&f.tx.state()->reducer==Bytes(4096,0x11));
            }
            const auto report=f.report(owner,1,1);
            const auto report_error=f.s.last_write_error;
            REQUIRE(f.tx.recover()&&f.tx.state()->rows.size()==1);
            const auto selected=f.tx.state()->generation;
            const auto cp=f.tx.checkpoint_reducer(Bytes(4096,0x22));
            const auto cp_error=f.s.last_write_error;
            REQUIRE(cp!=Result::Committed&&f.tx.recover()&&f.tx.state()->generation==selected&&f.tx.state()->reducer==Bytes(4096,0x11));
            std::printf("COMPACT_PRESSURE_CONTROL report=%u report_error=%s checkpoint=%u checkpoint_error=%s accepted_body_preserved=1\n",unsigned(report),esp_err_to_name(report_error),unsigned(cp),esp_err_to_name(cp_error));
            std::printf("COMPACT_PRESSURE_PASS attempts=3 ack=0 committed_payload_before=%zu payload_after=%zu protected_progress=UNPROVEN\n",saved,payload(f.s));
            metric("compact_pressure",n,&part);return 0;
        } else if(mode=="gcrecover"||(argc>4&&std::strcmp(argv[4],"gc")==0))prime_gc(f.s);
    }
    REQUIRE(nvs_flash_deinit_partition("life")==ESP_OK);
    if(mode=="rollback") {
        REQUIRE(esp_partition_erase_range(&part,0,part.size)==ESP_OK);
        REQUIRE(esp_partition_write(&part,0,flash.data(),flash.size())==ESP_OK);
        REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);Fixture replay(false);
        REQUIRE(replay.tx.state()->generation==baseline&&replay.tx.state()->rows.empty());
        std::printf("COMPACT_ROLLBACK_WITNESS old_authentic_image_accepted=1 latest_ack_eligible_event_missing=1 independent_anchor=ABSENT\n");return 0;
    }
    REQUIRE(mode=="fault"||mode=="rfault"||mode=="cfault"||mode=="gcut"||mode=="gcrecover");const auto child=fork();REQUIRE(child>=0);
    if(child==0) {
        REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);Fixture f(false);
        if(mode=="gcut")f.s.protected_space=true;
        diag::active=true;diag::hard_stop=true;diag::units=0;diag::calls=0;
        diag::verbose=std::getenv("GS_DIAG_TRACE")!=nullptr;
        const auto cut=argc>3?std::strtoul(argv[3],nullptr,10):999999;
        const auto erase_before=esp_partition_get_erase_ops();
        esp_partition_fail_after(cut,ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        const auto result=mode=="cfault"?(f.compact.collect_selected(*f.tx.state())?Result::Committed:Result::Fault):
            mode=="rfault"?f.report(owner,1,1):f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22));
        std::printf("COMPACT_CHILD result=%u io_units=%zu io_calls=%zu gc_erase_delta=%zu peak_allocated_pages=%u peak_live_entries=%u\n",unsigned(result),diag::units,diag::calls,esp_partition_get_erase_ops()-erase_before,diag::peak_pages,diag::peak_live);
        _exit(result==Result::Committed?0:78);
    }
    int status=0;REQUIRE(waitpid(child,&status,0)==child&&WIFEXITED(status));
    REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);Fixture recovered(false);
    if(mode=="gcut"||mode=="gcrecover")recovered.s.protected_space=true;
    const auto* state=recovered.tx.state();REQUIRE(state);
    if(mode=="cfault") {
        REQUIRE(state->generation==baseline&&state->rows.size()==1&&state->rows[0].sequence==2&&
            state->rows[0].body==Bytes(448,0x42)&&state->reducer==Bytes(4096,0x22)&&state->owners[0].charged==1);
        REQUIRE(recovered.admit(owner,2,Bytes(448,0x42),Bytes(4096,0x22))==Result::Duplicate);recovered.collect();
        std::printf("COMPACT_COLLECTION_CUT_PASS child_exit=%d selected_dependencies_preserved=1 retry=duplicate\n",WEXITSTATUS(status));return 0;
    }
    REQUIRE(state->generation==baseline||state->generation==baseline+1);
    const bool committed=state->generation==baseline+1;
    if(mode=="rfault") {
        REQUIRE(state->reducer==Bytes(4096,0x11)&&state->rows.size()==1&&state->owners[0].charged==unsigned(!committed));
        REQUIRE(recovered.report(owner,1,1)==(committed?Result::Duplicate:Result::Committed));
    } else {
        REQUIRE(state->reducer==Bytes(4096,committed?0x22:0x11)&&state->rows.size()==unsigned(committed)&&state->owners[0].charged==unsigned(committed));
        const auto retry=recovered.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22));
        if(mode=="gcrecover"&&!committed) {
            REQUIRE(recovered.s.result(retry)==SpaceOutcome::InsufficientProtectedSpace);
            REQUIRE(recovered.s.writes==0&&recovered.tx.state()->generation==baseline);
            std::printf("PROTECTED_GC_RESTART_SAFE_REJECT cut=%s ack=0 retry_writes=0\n",argv[3]);
        } else REQUIRE(retry==(committed?Result::Duplicate:Result::Committed));
    }
    REQUIRE(WEXITSTATUS(status)!=0||committed);
    recovered.collect();
    std::printf("COMPACT_POWERFAIL_PASS cut=%s child_exit=%d recovered=%s retry=%s payload=%zu gc_erases=%zu\n",argc>3?argv[3]:"none",WEXITSTATUS(status),committed?"new":"old",committed?"duplicate":mode=="gcrecover"?"space_rejected":"commit",payload(recovered.s),esp_partition_get_erase_ops());
    metric("compact_recovery",0,&part);return 0;
}
