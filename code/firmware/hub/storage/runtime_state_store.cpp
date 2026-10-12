#include "storage/runtime_state_store.hpp"
#include "storage/journal.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>

#ifdef ESP_PLATFORM
#include "esp_heap_caps.h"
#endif

namespace gs::hub::storage {
namespace {
using security::Bytes;
void u64(Bytes& b, std::uint64_t n) { for (unsigned i=0;i<8;++i) b.push_back(n>>(i*8)); }
void u32(Bytes& b, std::uint32_t n) { for (unsigned i=0;i<4;++i) b.push_back(n>>(i*8)); }
std::uint64_t get(const Bytes& b, std::size_t p) {
    std::uint64_t n=0; for(unsigned i=0;i<8;++i) n|=std::uint64_t(b[p+i])<<(8*i); return n;
}
std::uint32_t get32(const Bytes& b, std::size_t p) {
    return std::uint32_t(b[p]) | (std::uint32_t(b[p+1])<<8) |
        (std::uint32_t(b[p+2])<<16) | (std::uint32_t(b[p+3])<<24);
}
constexpr const char* kIdentities="identity.log";
constexpr const char* kHead="identity.head";
constexpr const char* kCheckpoint="application.head";
void* allocate_identity_index(std::size_t bytes) {
#ifdef ESP_PLATFORM
    return heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
#else
    return std::malloc(bytes);
#endif
}
void free_identity_index(void* memory) {
#ifdef ESP_PLATFORM
    heap_caps_free(memory);
#else
    std::free(memory);
#endif
}
std::size_t digest_slot(const security::Key32& digest) {
    std::size_t value = 0;
    for (std::size_t i = 0; i < sizeof(value); ++i)
        value = (value << 8U) | digest[i];
    return value;
}
}
struct RuntimeStateStore::IdentityIndexEntry {
    security::Key32 digest{};
    std::uint64_t ordinal{0};
    std::uint32_t offset{0};
    bool occupied{false};
};
bool IdentityOwnerEvidence::authenticated() const {
    return enrollment_slot < 10 && enrollment_generation != 0 &&
        std::any_of(binding_digest.begin(), binding_digest.end(),
                    [](std::uint8_t b) { return b != 0; });
}
RuntimeStateStore::RuntimeStateStore(RuntimeStateFiles& f, security::CommissioningCrypto& c,
        const security::Key32& master) : files_(f), crypto_(c) {
    const Bytes label{'g','s','-','r','u','n','t','i','m','e','-','v','1'};
    key_valid_=std::any_of(master.begin(),master.end(),[](std::uint8_t b){return b!=0;}) &&
        crypto_.hkdf_sha256(master,label,label,key_);
}
RuntimeStateStore::~RuntimeStateStore() {
    clear_identity_index();
    if (identity_index_ != nullptr) free_identity_index(identity_index_);
    crypto_.secure_zero(key_.data(),key_.size());
}
void RuntimeStateStore::clear_identity_index() {
    if (identity_index_ != nullptr)
        crypto_.secure_zero(identity_index_, identity_index_capacity_ * sizeof(IdentityIndexEntry));
    identity_index_size_ = 0;
}
bool RuntimeStateStore::reserve_identity_index(std::size_t required) {
    if (required > std::numeric_limits<std::size_t>::max() / 2U) return false;
    const auto minimum = std::max<std::size_t>(64U, required * 2U);
    if (identity_index_capacity_ >= minimum) return true;
    std::size_t next = identity_index_capacity_ == 0 ? 64U : identity_index_capacity_;
    while (next < minimum) {
        if (next > std::numeric_limits<std::size_t>::max() / 2U) return false;
        next *= 2U;
    }
    if (next > std::numeric_limits<std::size_t>::max() / sizeof(IdentityIndexEntry))
        return false;
    auto* replacement = static_cast<IdentityIndexEntry*>(
        allocate_identity_index(next * sizeof(IdentityIndexEntry)));
    if (replacement == nullptr) return false;
    for (std::size_t i = 0; i < next; ++i)
        ::new (static_cast<void*>(replacement + i)) IdentityIndexEntry{};
    for (std::size_t i = 0; i < identity_index_capacity_; ++i) {
        const auto& old = identity_index_[i];
        if (!old.occupied) continue;
        auto at = digest_slot(old.digest) & (next - 1U);
        while (replacement[at].occupied) at = (at + 1U) & (next - 1U);
        replacement[at] = old;
    }
    if (identity_index_ != nullptr) {
        crypto_.secure_zero(identity_index_, identity_index_capacity_ * sizeof(IdentityIndexEntry));
        free_identity_index(identity_index_);
    }
    identity_index_ = replacement;
    identity_index_capacity_ = next;
    return true;
}
bool RuntimeStateStore::insert_identity_index(const std::string& key,
        std::uint64_t ordinal, std::uint32_t offset) {
    if (key.empty() || ordinal == 0 || !reserve_identity_index(identity_index_size_ + 1U))
        return false;
    security::Key32 digest{};
    const auto key_bytes = security::Bytes(key.begin(), key.end());
    if (!crypto_.hmac_sha256(key_, key_bytes, digest)) return false;
    auto at = digest_slot(digest) & (identity_index_capacity_ - 1U);
    while (identity_index_[at].occupied) {
        if (identity_index_[at].digest == digest) {
            crypto_.secure_zero(digest.data(), digest.size());
            return false;
        }
        at = (at + 1U) & (identity_index_capacity_ - 1U);
    }
    identity_index_[at].digest = digest;
    identity_index_[at].ordinal = ordinal;
    identity_index_[at].offset = offset;
    identity_index_[at].occupied = true;
    ++identity_index_size_;
    crypto_.secure_zero(digest.data(), digest.size());
    return true;
}
bool RuntimeStateStore::find_identity_index(const std::string& key,
        std::uint64_t& ordinal, std::uint32_t& offset, bool& found) {
    ordinal = 0; offset = 0; found = false;
    if (key.empty()) return false;
    if (identity_index_size_ == 0) return true;
    security::Key32 digest{};
    const auto key_bytes = security::Bytes(key.begin(), key.end());
    if (!crypto_.hmac_sha256(key_, key_bytes, digest)) return fault();
    auto at = digest_slot(digest) & (identity_index_capacity_ - 1U);
    for (std::size_t probes = 0; probes < identity_index_capacity_; ++probes) {
        const auto& entry = identity_index_[at];
        if (!entry.occupied) break;
        if (entry.digest == digest) {
            std::string stored_key;
            std::optional<std::uint16_t> minute;
            security::Bytes frame;
            if (!record_at(entry.offset, entry.ordinal, stored_key, minute, frame,
                           nullptr,nullptr,nullptr,active_identity_file_.c_str()) ||
                stored_key != key) {
                crypto_.secure_zero(digest.data(), digest.size());
                return fault();
            }
            ordinal = entry.ordinal;
            offset = entry.offset;
            found = true;
            break;
        }
        at = (at + 1U) & (identity_index_capacity_ - 1U);
    }
    crypto_.secure_zero(digest.data(), digest.size());
    return true;
}
bool RuntimeStateStore::seal(std::uint8_t type, std::uint64_t ordinal,
        const Bytes& plain, Bytes& out) {
    if(!key_valid_) return false;
    Bytes aad{'G','S','R',1,type}; u64(aad,ordinal);
    security::Nonce12 nonce{}; security::GcmTag tag{}; Bytes cipher;
    if(!crypto_.random_bytes(nonce.data(),nonce.size()) ||
       !crypto_.seal_aes256_gcm(key_,nonce,aad,plain,cipher,tag)) return false;
    out=aad; out.insert(out.end(),nonce.begin(),nonce.end());
    out.insert(out.end(),tag.begin(),tag.end()); out.insert(out.end(),cipher.begin(),cipher.end());
    return true;
}
bool RuntimeStateStore::open(std::uint8_t type, const Bytes& blob,
        std::uint64_t& ordinal, Bytes& plain) {
    if(blob.size()<41 || blob[0]!='G'||blob[1]!='S'||blob[2]!='R'||blob[3]!=1||blob[4]!=type)
        return false;
    ordinal=get(blob,5); security::Nonce12 nonce{}; security::GcmTag tag{};
    std::copy_n(blob.begin()+13,12,nonce.begin()); std::copy_n(blob.begin()+25,16,tag.begin());
    return crypto_.open_aes256_gcm(key_,nonce,Bytes(blob.begin(),blob.begin()+13),
                                Bytes(blob.begin()+41,blob.end()),tag,plain);
}
bool RuntimeStateStore::read_object(const char* name, Bytes& out, bool& found,
                                    std::size_t maximum) {
    std::uint32_t n=0; out.clear();
    if(!files_.state_size(name,found,n)) return false;
    if(!found) return true;
    if(n==0 || n>maximum) return false;
    out.resize(n); return files_.state_read(name,0,out.data(),out.size());
}
bool RuntimeStateStore::load_checkpoint(Bytes& plain, std::uint64_t& boundary, bool& found) {
    Bytes blob;
    if(!read_object(kCheckpoint,blob,found,maximum_checkpoint_bytes+41)) return fault();
    if(!found) { plain.clear(); boundary=0; return true; }
    checkpoint_bytes_=blob.size();
    return open(3,blob,boundary,plain) || fault();
}
bool RuntimeStateStore::save_checkpoint(const Bytes& plain, std::uint64_t boundary) {
    if(!healthy() || plain.empty() || plain.size()>maximum_checkpoint_bytes || boundary>count_)
        return fault();
    Bytes previous; std::uint64_t old_boundary=0; bool old_found=false;
    if(!load_checkpoint(previous,old_boundary,old_found)) return false;
    bool head_found=false;Bytes identity_head;
    if(!read_object(kHead,identity_head,head_found,256))return fault();
    if(count_==0 && !head_found) {
        Bytes genesis;
        if(!seal(2,0,Bytes(32,0),genesis)||!files_.state_replace(kHead,genesis)||
           !read_object(kHead,identity_head,head_found,256)||!head_found||identity_head!=genesis)
            return fault();
        // A crash here before the first checkpoint is safely unavailable.
    }
    if(old_found && old_boundary==boundary && previous==plain) return true;
    Bytes blob,verify; bool found=false;
    if(!seal(3,boundary,plain,blob) || !files_.state_replace(kCheckpoint,blob) ||
       !read_object(kCheckpoint,verify,found,maximum_checkpoint_bytes+41) || !found || verify!=blob)
        return fault();
    checkpoint_bytes_=blob.size(); return true;
}
bool RuntimeStateStore::record_at(std::uint32_t offset, std::uint64_t expected,
        std::string& key, std::optional<std::uint16_t>& minute, Bytes& frame,
        security::Key32* event_digest, IdentityOwnerEvidence* owner,
        std::uint64_t* actual_ordinal, const char* file) {
    std::uint8_t prefix[4]{};
    if(!files_.state_read(file,offset,prefix,4)) return false;
    const std::uint32_t n=std::uint32_t(prefix[0])|(std::uint32_t(prefix[1])<<8)|
        (std::uint32_t(prefix[2])<<16)|(std::uint32_t(prefix[3])<<24);
    if(n<44 || n>512 || offset>maximum_identity_bytes-n-4) return false;
    frame.resize(n+4); std::copy_n(prefix,4,frame.begin());
    if(!files_.state_read(file,offset+4,frame.data()+4,n)) return false;
    std::uint64_t ordinal=0; Bytes plain;
    if(!open(1,Bytes(frame.begin()+4,frame.end()),ordinal,plain)||
       (expected!=0 && ordinal!=expected)||plain.size()<35)
        return false;
    if(actual_ordinal)*actual_ordinal=ordinal;
    const bool owner_format = (plain[0] & 0x80U) != 0;
    if ((owner_format && (plain[0] & 0x7eU) != 0) || (!owner_format && plain[0] > 1))
        return false;
    const auto m=std::uint16_t(plain[1])|(std::uint16_t(plain[2])<<8);
    const bool has_minute = (plain[0] & 1U) != 0;
    if(has_minute && m>=1440) return false;
    minute=has_minute ? std::optional<std::uint16_t>(m) : std::nullopt;
    if(event_digest)std::copy_n(plain.begin()+3,32,event_digest->begin());
    std::size_t key_offset = 35;
    if (owner != nullptr) *owner = {};
    if (owner_format) {
        if (plain.size() < 72) return false;
        IdentityOwnerEvidence parsed;
        parsed.enrollment_slot = plain[35];
        parsed.enrollment_generation = static_cast<std::uint32_t>(plain[36]) |
            (static_cast<std::uint32_t>(plain[37]) << 8) |
            (static_cast<std::uint32_t>(plain[38]) << 16) |
            (static_cast<std::uint32_t>(plain[39]) << 24);
        std::copy_n(plain.begin() + 40, 32, parsed.binding_digest.begin());
        if (parsed.enrollment_slot == 0xff) {
            if (parsed.enrollment_generation != 0 || std::any_of(
                    parsed.binding_digest.begin(), parsed.binding_digest.end(),
                    [](std::uint8_t b) { return b != 0; })) return false;
        } else if (!parsed.authenticated()) return false;
        if (owner != nullptr) *owner = parsed;
        key_offset = 72;
    }
    key.assign(plain.begin()+key_offset,plain.end()); return !key.empty() && key.size()<=256;
}
bool RuntimeStateStore::recover(std::uint64_t published_event_highwater) {
    ready_=false; faulted_=false; count_=0; bytes_=0; cursor_ordinal_=0; cursor_offset_=0;
    active_slot_=0;active_identity_file_="identity.log";compacted_=false;
    replay_epoch_=replay_generation_=0;replay_bank_=0;replay_digest_.fill(0);
    compacted_plan_digest_.fill(0);
    clear_identity_index();
    if(!key_valid_) return fault();
    Bytes head,plain; bool found=false,exists=false; std::uint32_t size=0;
    if(!read_object(kHead,head,found,256)) return fault();
    if(found) {
        std::uint64_t head_ordinal=0;
        if(open(4,head,head_ordinal,plain)) {
            if(plain.size()!=130 || plain[0]!='G' || plain[1]!='I' || plain[2]!='C' ||
               plain[3]!=1 || plain[4]<1 || plain[4]>2 || head_ordinal==0 ||
               get(plain,5)!=head_ordinal) return fault();
            active_slot_=plain[4];
            active_identity_file_=active_slot_==1 ? "identity.a" : "identity.b";
            count_=head_ordinal;bytes_=get32(plain,13);
            replay_epoch_=get(plain,49);replay_generation_=get(plain,57);replay_bank_=plain[65];
            std::copy_n(plain.begin()+66,32,replay_digest_.begin());
            std::copy_n(plain.begin()+98,32,compacted_plan_digest_.begin());
            compacted_=true;
        } else {
            if(!open(2,head,count_,plain)||plain.size()!=32) return fault();
            active_slot_=0;active_identity_file_="identity.log";
        }
    }
    if(!files_.state_size(active_identity_file_.c_str(),exists,size))return fault();
    if(found) {
        if(count_<published_event_highwater || count_-published_event_highwater>1 ||
           (!exists && (bytes_!=0 || count_!=0))) return fault();
        std::uint32_t offset=0;std::uint64_t previous=0,actual=0;
        Bytes frame;std::string key;std::optional<std::uint16_t> minute;
        security::Key32 digest{},expected_tail{};
        if(compacted_)std::copy_n(plain.begin()+17,32,expected_tail.begin());
        if(compacted_) {
            const auto row_limit=bytes_;
            if(size<row_limit || size-row_limit>516)return fault();
            while(offset<row_limit) {
                if(!record_at(offset,0,key,minute,frame,nullptr,nullptr,&actual,
                              active_identity_file_.c_str()) || actual<=previous ||
                   actual>count_ || !insert_identity_index(key,actual,offset))return fault();
                previous=actual;offset+=static_cast<std::uint32_t>(frame.size());
            }
            if(offset!=row_limit || (row_limit!=0 && previous==0) ||
               (row_limit==0 && std::any_of(expected_tail.begin(),expected_tail.end(),
                    [](std::uint8_t b){return b!=0;})))return fault();
            if(row_limit!=0 && (!crypto_.hmac_sha256(key_,frame,digest) ||
               !crypto_.constant_time_equal(digest.data(),expected_tail.data(),32)))return fault();
            if(size>row_limit && !files_.state_truncate(active_identity_file_.c_str(),row_limit))
                return fault();
            if(compacted_ && previous<count_) {
                // The final identity may have been fenced. The root's high-water
                // still preserves the reducer/event ordinal domain.
            }
        } else {
            for(std::uint64_t ordinal=1;ordinal<=count_;++ordinal) {
                if(!record_at(offset,ordinal,key,minute,frame,nullptr,nullptr,&actual,
                              active_identity_file_.c_str()) || actual!=ordinal ||
                   !insert_identity_index(key,actual,offset))return fault();
                previous=actual;offset+=static_cast<std::uint32_t>(frame.size());
            }
            bytes_=offset;
            if(size<bytes_ || size-bytes_>516)return fault();
            if(previous!=0 && (!crypto_.hmac_sha256(key_,frame,digest) ||
               !crypto_.constant_time_equal(digest.data(),plain.data(),32)))return fault();
            if(size>bytes_ && !files_.state_truncate(active_identity_file_.c_str(),bytes_))
                return fault();
        }
    } else if(published_event_highwater!=0) {
        // Only an explicit retained-body migration may create the independent ledger.
        return fault();
    }
    if(!found && exists) {
        if(published_event_highwater!=0 || size>516 ||
           !files_.state_truncate(active_identity_file_.c_str(),0))return fault();
    }
    Bytes checkpoint; std::uint64_t boundary=0; bool cp=false;
    if(!load_checkpoint(checkpoint,boundary,cp)||boundary>published_event_highwater||
       (!cp && (count_!=0 || found))) return fault();
    committed_highwater_=published_event_highwater; ready_=true;
    // Non-authoritative candidate files are safe to remove only after the
    // selected generation has been authenticated and indexed successfully.
    if(compacted_) {
        if(active_slot_!=1 && !files_.state_remove("identity.a"))return fault();
        if(active_slot_!=2 && !files_.state_remove("identity.b"))return fault();
        if(!files_.state_remove(kIdentities))return fault();
    } else {
        if(!files_.state_remove("identity.a") || !files_.state_remove("identity.b"))
            return fault();
    }
    return true;
}
bool RuntimeStateStore::prepare_identity(const DomainEvent& event, std::uint64_t ordinal,
                                         std::optional<std::uint16_t> minute,
                                         const IdentityOwnerEvidence* owner) {
    const auto& key=event.key;
    if(!healthy() || !ordinal || (minute && *minute>=1440) ||
       (owner != nullptr && !owner->authenticated())) return false;
    if(ordinal<=count_) {
        std::optional<std::uint16_t> existing;
        return identity_context(key,ordinal,existing) && verify_event_identity(event,ordinal);
        // Retry uses the original decision context; accepted bytes are immutable.
    }
    if(ordinal!=count_+1) return fault();
    const auto canonical=key.str();
    if(canonical.empty() || canonical.size()>256) return false;
    if(!reserve_identity_index(identity_index_size_ + 1U)) return false;
    Bytes plain{static_cast<std::uint8_t>(0x80U | (minute.has_value() ? 1U : 0U)),
                std::uint8_t(minute.value_or(0)),
                std::uint8_t(minute.value_or(0)>>8)},blob,frame;
    Bytes payload;security::Key32 digest_of_event{};
    if(!HubJournal::encode_event_payload(event,payload)||
       !crypto_.hmac_sha256(key_,payload,digest_of_event))return fault();
    crypto_.secure_zero(payload.data(),payload.size());
    plain.insert(plain.end(),digest_of_event.begin(),digest_of_event.end());
    if (owner != nullptr) {
        plain.push_back(owner->enrollment_slot);
        for (unsigned i = 0; i < 4; ++i)
            plain.push_back(static_cast<std::uint8_t>(owner->enrollment_generation >> (i * 8U)));
        plain.insert(plain.end(), owner->binding_digest.begin(), owner->binding_digest.end());
    } else {
        plain.push_back(0xff);
        plain.insert(plain.end(), 4, 0);
        plain.insert(plain.end(), 32, 0);
    }
    plain.insert(plain.end(),canonical.begin(),canonical.end());
    if(!seal(1,ordinal,plain,blob)) return fault();
    const auto n=blob.size(); frame={std::uint8_t(n),std::uint8_t(n>>8),std::uint8_t(n>>16),std::uint8_t(n>>24)};
    frame.insert(frame.end(),blob.begin(),blob.end());
    if(frame.size()>maximum_identity_bytes-bytes_) return false;
    security::Key32 digest{}; Bytes head;
    if(!crypto_.hmac_sha256(key_,frame,digest)||
       !seal(2,ordinal,Bytes(digest.begin(),digest.end()),head)||
       !files_.state_append_sync(active_identity_file_.c_str(),frame)) return fault();
    Bytes verify; std::string exact; std::optional<std::uint16_t> m;
    if(!record_at(bytes_,ordinal,exact,m,verify,nullptr,nullptr,nullptr,
                  active_identity_file_.c_str())||verify!=frame) return fault();
    if(compacted_) {
        Bytes root{'G','I','C',1,active_slot_};u64(root,ordinal);
        u32(root,bytes_+static_cast<std::uint32_t>(frame.size()));
        root.insert(root.end(),digest.begin(),digest.end());
        u64(root,replay_epoch_);u64(root,replay_generation_);root.push_back(replay_bank_);
        root.insert(root.end(),replay_digest_.begin(),replay_digest_.end());
        root.insert(root.end(),compacted_plan_digest_.begin(),compacted_plan_digest_.end());
        if(!seal(4,ordinal,root,head))return fault();
    }
    if(!files_.state_replace(kHead,head)) return fault();
    bool found=false;
    if(!read_object(kHead,verify,found,256)||!found||verify!=head) return fault();
    if(!insert_identity_index(canonical, ordinal, bytes_)) return fault();
    count_=ordinal; bytes_+=frame.size(); return true;
}
bool RuntimeStateStore::identity_context(const EventKey& key, std::uint64_t ordinal,
                                         std::optional<std::uint16_t>& minute, const DomainEvent* expected_event) {
    if(!healthy() || ordinal==0 || ordinal>count_) return false;
    std::uint64_t indexed_ordinal=0;std::uint32_t offset=0;bool found=false;
    if(!find_identity_index(key.str(),indexed_ordinal,offset,found))return false;
    if(!found || indexed_ordinal!=ordinal)return false;
    Bytes frame;std::string exact;security::Key32 expected{};
    if(!record_at(offset,ordinal,exact,minute,frame,&expected,nullptr,nullptr,
                  active_identity_file_.c_str()))return fault();
    if(expected_event){
        Bytes payload;security::Key32 digest{};
        if(!HubJournal::encode_event_payload(*expected_event,payload)||
           !crypto_.hmac_sha256(key_,payload,digest))return fault();
        crypto_.secure_zero(payload.data(),payload.size());
        if(!crypto_.constant_time_equal(digest.data(),expected.data(),32))return fault();
    }
    cursor_ordinal_=ordinal; cursor_offset_=offset+static_cast<std::uint32_t>(frame.size());
    return exact==key.str() || fault();
}
bool RuntimeStateStore::lookup_identity(const DomainEvent& event, std::uint64_t& ordinal,
        std::optional<std::uint16_t>& local_minute, bool& found, bool& payload_matches,
        IdentityOwnerEvidence* owner, security::Key32* payload_digest) {
    ordinal = 0;
    local_minute.reset();
    found = false;
    payload_matches = false;
    if (owner != nullptr) *owner = {};
    if (payload_digest != nullptr) payload_digest->fill(0);
    if (!healthy()) return false;
    Bytes event_payload;
    security::Key32 expected_digest{};
    if (!HubJournal::encode_event_payload(event, event_payload) ||
        !crypto_.hmac_sha256(key_, event_payload, expected_digest)) {
        crypto_.secure_zero(event_payload.data(), event_payload.size());
        return fault();
    }
    crypto_.secure_zero(event_payload.data(), event_payload.size());
    std::uint32_t offset = 0;
    if (!find_identity_index(event.key.str(), ordinal, offset, found)) {
        crypto_.secure_zero(expected_digest.data(), expected_digest.size());
        return false;
    }
    if (!found) {
        crypto_.secure_zero(expected_digest.data(), expected_digest.size());
        return true;
    }
    Bytes frame;
    std::string exact;
    std::optional<std::uint16_t> minute;
    security::Key32 stored_digest{};
    if (!record_at(offset, ordinal, exact, minute, frame, &stored_digest, owner,nullptr,
                   active_identity_file_.c_str()) ||
        exact != event.key.str()) {
        crypto_.secure_zero(expected_digest.data(), expected_digest.size());
        crypto_.secure_zero(stored_digest.data(), stored_digest.size());
        return fault();
    }
    local_minute = minute;
    if (payload_digest != nullptr) *payload_digest = stored_digest;
    payload_matches = crypto_.constant_time_equal(expected_digest.data(),
                                                   stored_digest.data(),
                                                   expected_digest.size());
    crypto_.secure_zero(expected_digest.data(), expected_digest.size());
    crypto_.secure_zero(stored_digest.data(), stored_digest.size());
    return true;
}
bool RuntimeStateStore::contains_identity(const EventKey& key, bool& found) {
    found=false; if(!healthy()) return false;
    std::uint64_t ordinal=0;std::uint32_t offset=0;
    return find_identity_index(key.str(),ordinal,offset,found);
}
bool RuntimeStateStore::confirm_event_publication(std::uint64_t boundary) {
    if(!healthy() || boundary<committed_highwater_ || boundary>count_)return fault();
    committed_highwater_=boundary;return true;
}
bool RuntimeStateStore::verify_event_identity(const DomainEvent& event, std::uint64_t ordinal) {
    if(!healthy() || ordinal==0 || ordinal>count_)return false;
    std::uint32_t offset=0;std::uint64_t indexed_ordinal=0;bool found=false;
    if(!find_identity_index(event.key.str(),indexed_ordinal,offset,found))return false;
    if(!found || indexed_ordinal!=ordinal)return false;
    Bytes frame;std::string exact;
    std::optional<std::uint16_t> minute;security::Key32 digest{},expected{};
    if(!record_at(offset,ordinal,exact,minute,frame,&expected,nullptr,nullptr,
                  active_identity_file_.c_str()))return fault();
    Bytes payload;
    if(exact!=event.key.str() || !HubJournal::encode_event_payload(event,payload)||
       !crypto_.hmac_sha256(key_,payload,digest))return fault();
    crypto_.secure_zero(payload.data(),payload.size());
    return crypto_.constant_time_equal(digest.data(),expected.data(),32) || fault();
}
bool RuntimeStateStore::plan_identity_compaction(
        IdentityCompactionClassifier classify,
        IdentityCompactionRetainedVisitor visit_retained,
        void* context, IdentityCompactionPlan& plan) {
    plan = {};
    if (!healthy() || classify == nullptr || visit_retained == nullptr) return false;
    bool head_found = false, log_found = false;
    Bytes source_head;
    std::uint32_t log_size = 0;
    if (!read_object(kHead, source_head, head_found, 256) ||
        !files_.state_size(active_identity_file_.c_str(), log_found, log_size) ||
        log_size != bytes_ || (count_ != 0 && (!head_found || !log_found))) {
        plan.blocked_records = 1;
        return fault();
    }
    if (!crypto_.hmac_sha256(key_, source_head, plan.source_head_digest)) return fault();
    plan.source_records = identity_index_size_;
    plan.source_bytes = bytes_;
    Bytes chain{'G','S','I','C',1};
    chain.insert(chain.end(), plan.source_head_digest.begin(), plan.source_head_digest.end());
    if (!crypto_.hmac_sha256(key_, chain, plan.candidate_digest)) return fault();

    std::uint32_t offset = 0;
    for (std::uint64_t row = 0; row < identity_index_size_; ++row) {
        IdentityCompactionRecord record;
        Bytes frame;
        std::uint64_t ordinal=0;
        if (!record_at(offset, compacted_ ? 0 : row+1, record.event_key,
                       record.local_minute, frame, &record.payload_digest,
                       &record.owner,&ordinal,active_identity_file_.c_str()) ||
            ordinal==0 || ordinal>count_) {
            plan.blocked_records = 1;
            crypto_.secure_zero(chain.data(), chain.size());
            return fault();
        }
        record.original_ordinal = ordinal;
        record.encoded_bytes = static_cast<std::uint32_t>(frame.size());
        offset += record.encoded_bytes;
        const auto disposition = classify(context, record);
        if (disposition == IdentityCompactionDisposition::Blocked) {
            ++plan.blocked_records;
            crypto_.secure_zero(chain.data(), chain.size());
            return false;
        }
        if (disposition == IdentityCompactionDisposition::Fenced) {
            ++plan.fenced_records;
            continue;
        }
        if (record.encoded_bytes > UINT32_MAX - plan.candidate_record_bytes ||
            !visit_retained(context, record)) {
            ++plan.blocked_records;
            crypto_.secure_zero(chain.data(), chain.size());
            return false;
        }
        ++plan.retained_records;
        plan.candidate_record_bytes += record.encoded_bytes;

        Bytes next(plan.candidate_digest.begin(), plan.candidate_digest.end());
        u64(next, record.original_ordinal);
        u64(next, plan.retained_records);
        for (unsigned i = 0; i < 4; ++i)
            next.push_back(static_cast<std::uint8_t>(record.encoded_bytes >> (i * 8U)));
        next.push_back(static_cast<std::uint8_t>(record.event_key.size() >> 8U));
        next.push_back(static_cast<std::uint8_t>(record.event_key.size()));
        next.insert(next.end(), record.event_key.begin(), record.event_key.end());
        next.push_back(record.local_minute ? 1 : 0);
        const auto minute = record.local_minute.value_or(0);
        next.push_back(static_cast<std::uint8_t>(minute));
        next.push_back(static_cast<std::uint8_t>(minute >> 8U));
        next.insert(next.end(), record.payload_digest.begin(), record.payload_digest.end());
        next.push_back(record.owner.enrollment_slot);
        for (unsigned i = 0; i < 4; ++i)
            next.push_back(static_cast<std::uint8_t>(record.owner.enrollment_generation >> (i * 8U)));
        next.insert(next.end(), record.owner.binding_digest.begin(), record.owner.binding_digest.end());
        if (!crypto_.hmac_sha256(key_, next, plan.candidate_digest)) {
            crypto_.secure_zero(chain.data(), chain.size());
            crypto_.secure_zero(next.data(), next.size());
            return fault();
        }
        crypto_.secure_zero(next.data(), next.size());
    }
    bool final_head_found = false, final_log_found = false;
    Bytes final_head;
    std::uint32_t final_log_size = 0;
    security::Key32 final_head_digest{};
    const bool stable = read_object(kHead, final_head, final_head_found, 256) &&
        files_.state_size(active_identity_file_.c_str(), final_log_found, final_log_size) &&
        final_head_found == head_found && final_log_found == log_found &&
        final_log_size == log_size && final_head == source_head &&
        crypto_.hmac_sha256(key_, final_head, final_head_digest) &&
        crypto_.constant_time_equal(final_head_digest.data(),
            plan.source_head_digest.data(), plan.source_head_digest.size());
    crypto_.secure_zero(chain.data(), chain.size());
    crypto_.secure_zero(final_head_digest.data(), final_head_digest.size());
    if (!stable || offset != bytes_ ||
        plan.retained_records + plan.fenced_records != plan.source_records) {
        ++plan.blocked_records;
        return fault();
    }
    plan.minimum_temporary_bytes = plan.candidate_record_bytes;
    plan.complete = true;
    return true;
}

bool RuntimeStateStore::compact_identity(IdentityCompactionClassifier classify,
        void* classifier_context,
        const security::Bytes& replay_authority, std::uint64_t replay_epoch,
        std::uint64_t replay_generation, std::uint8_t replay_bank,
        const security::Key32& replay_digest,
        IdentityCompactionAuthorityValidator authority_current,
        void* authority_context, std::uint32_t safety_reserve_bytes,
        IdentityCompactionPlan& result) {
    result={};
#if defined(ESP_PLATFORM) && (!defined(CONFIG_GS_IDENTITY_COMPACTION_ENABLED) || \
                              !CONFIG_GS_IDENTITY_COMPACTION_ENABLED)
    (void)classify;(void)classifier_context;(void)replay_authority;(void)replay_epoch;(void)replay_generation;
    (void)replay_bank;(void)replay_digest;(void)authority_current;(void)authority_context;
    (void)safety_reserve_bytes;
    return false;
#endif
    if(!healthy() || classify==nullptr || replay_authority.empty() ||
       replay_generation==0 || replay_epoch==0 || replay_bank>=3 ||
       std::all_of(replay_digest.begin(),replay_digest.end(),[](std::uint8_t b){return b==0;}))
        return false;
    struct ClassifierOnly { IdentityCompactionClassifier classifier; void* context; } classifier_only{
        classify,classifier_context};
    const auto dispatch_classifier=[](void* opaque,const IdentityCompactionRecord& record) {
        auto& dispatch=*static_cast<ClassifierOnly*>(opaque);
        return dispatch.classifier(dispatch.context,record);
    };
    const auto noop=[](void*,const IdentityCompactionRecord&){return true;};
    IdentityCompactionPlan expected;
    if(!plan_identity_compaction(dispatch_classifier,noop,&classifier_only,expected))return false;
    std::uint64_t total=0,used=0;
    const auto reserve=std::max(safety_reserve_bytes,
        minimum_compaction_safety_reserve_bytes);
    const std::uint64_t required_temporary=
        static_cast<std::uint64_t>(expected.candidate_record_bytes)+reserve;
    if(required_temporary>UINT32_MAX || !files_.state_capacity(total,used) ||
       used>total || required_temporary>total-used)return false;
    expected.minimum_temporary_bytes=static_cast<std::uint32_t>(required_temporary);
    expected.temporary_safety_reserve_bytes=reserve;
    const std::uint8_t candidate_slot=active_slot_==1 ? 2 : 1;
    const char* candidate_file=candidate_slot==1 ? "identity.a" : "identity.b";
    if(!files_.state_remove(candidate_file) || !files_.state_replace(candidate_file,Bytes{}))
        return false;
    struct CopyContext { RuntimeStateStore* store; const char* file;
        IdentityCompactionClassifier classifier; void* classifier_context; } copy{
            this,candidate_file,classify,classifier_context};
    const auto classify_copy=[](void* opaque,const IdentityCompactionRecord& record) {
        auto& context=*static_cast<CopyContext*>(opaque);
        return context.classifier(context.classifier_context,record);
    };
    const auto append_retained=[](void* opaque,const IdentityCompactionRecord& record) {
        auto& context=*static_cast<CopyContext*>(opaque);
        std::uint64_t indexed=0;std::uint32_t offset=0;bool found=false;
        if(!context.store->find_identity_index(record.event_key,indexed,offset,found) ||
           !found || indexed!=record.original_ordinal)return false;
        Bytes frame;std::string key;std::optional<std::uint16_t> minute;
        std::uint64_t actual=0;
        if(!context.store->record_at(offset,indexed,key,minute,frame,nullptr,nullptr,&actual,
                    context.store->active_identity_file_.c_str()) || actual!=indexed ||
           key!=record.event_key || minute!=record.local_minute ||
           frame.size()!=record.encoded_bytes)return false;
        return context.store->files_.state_append_sync(context.file,frame);
    };
    IdentityCompactionPlan written;
    const bool staged=plan_identity_compaction(classify_copy,append_retained,&copy,written) &&
        written.source_head_digest==expected.source_head_digest &&
        written.candidate_digest==expected.candidate_digest &&
        written.candidate_record_bytes==expected.candidate_record_bytes &&
        written.retained_records==expected.retained_records &&
        written.fenced_records==expected.fenced_records;
    if(!staged || !files_.state_sync(candidate_file))return false;

    bool candidate_found=false;std::uint32_t candidate_size=0;
    if(!files_.state_size(candidate_file,candidate_found,candidate_size) || !candidate_found ||
       candidate_size!=expected.candidate_record_bytes)return false;
    // Re-read every candidate frame and compare it byte-for-byte with the
    // retained source stream. This authenticates the staged generation before
    // a root can select it and keeps memory bounded to one frame.
    struct VerifyContext { RuntimeStateStore* store; const char* file; std::uint32_t offset{0};
        IdentityCompactionClassifier classifier; void* classifier_context; } verify{
            this,candidate_file,0,classify,classifier_context};
    const auto classify_verify=[](void* opaque,const IdentityCompactionRecord& record) {
        auto& context=*static_cast<VerifyContext*>(opaque);
        return context.classifier(context.classifier_context,record);
    };
    const auto verify_retained=[](void* opaque,const IdentityCompactionRecord& record) {
        auto& context=*static_cast<VerifyContext*>(opaque);
        std::uint64_t indexed=0;std::uint32_t source_offset=0;bool found=false;
        if(!context.store->find_identity_index(record.event_key,indexed,source_offset,found) ||
           !found || indexed!=record.original_ordinal)return false;
        Bytes source,candidate;std::string source_key,candidate_key;
        std::optional<std::uint16_t> source_minute,candidate_minute;std::uint64_t actual=0;
        if(!context.store->record_at(source_offset,indexed,source_key,source_minute,source,
                nullptr,nullptr,&actual,context.store->active_identity_file_.c_str()) ||
           actual!=indexed ||
           !context.store->record_at(context.offset,0,candidate_key,candidate_minute,candidate,
                nullptr,nullptr,&actual,context.file) || actual!=indexed ||
           candidate!=source || candidate_key!=record.event_key ||
           candidate_minute!=record.local_minute)return false;
        context.offset+=static_cast<std::uint32_t>(candidate.size());return true;
    };
    IdentityCompactionPlan verified;
    if(!plan_identity_compaction(classify_verify,verify_retained,&verify,verified) ||
       verified.candidate_digest!=expected.candidate_digest ||
       verified.retained_records!=expected.retained_records ||
       verify.offset!=candidate_size || !authority_current ||
       !authority_current(authority_context))return false;

    // The candidate carries the original ordinal domain. The encrypted root
    // atomically switches the active generation and binds it to both the
    // exact source plan and the authenticated replay-fence publication.
    Bytes root_plain{'G','I','C',1,candidate_slot};u64(root_plain,count_);
    u32(root_plain,candidate_size);
    security::Key32 tail_digest{};
    if(candidate_size!=0) {
        Bytes last;std::uint32_t at=0;std::string key;std::optional<std::uint16_t> minute;
        while(at<candidate_size) {
            if(!record_at(at,0,key,minute,last,nullptr,nullptr,nullptr,candidate_file))return false;
            at+=static_cast<std::uint32_t>(last.size());
        }
        if(at!=candidate_size || !crypto_.hmac_sha256(key_,last,tail_digest))return fault();
    }
    root_plain.insert(root_plain.end(),tail_digest.begin(),tail_digest.end());
    u64(root_plain,replay_epoch);u64(root_plain,replay_generation);root_plain.push_back(replay_bank);
    root_plain.insert(root_plain.end(),replay_digest.begin(),replay_digest.end());
    root_plain.insert(root_plain.end(),expected.candidate_digest.begin(),expected.candidate_digest.end());
    Bytes root;Bytes observed;bool root_found=false;
    if(!seal(4,count_,root_plain,root) || !files_.state_replace(kHead,root) ||
       !read_object(kHead,observed,root_found,256) || !root_found || observed!=root ||
       !authority_current(authority_context))return fault();
    if(!recover(committed_highwater_))return false;
    result=expected;
    return true;
}
bool RuntimeStateStore::compaction_authority_matches(std::uint64_t replay_epoch,
        std::uint64_t replay_generation, std::uint8_t replay_bank,
        const security::Key32& replay_digest) const {
    if(!compacted_)return true;
    if(replay_epoch==0 || replay_epoch!=replay_epoch_ || replay_generation<replay_generation_)
        return false;
    if(replay_generation==replay_generation_)
        return replay_bank==replay_bank_ && replay_digest==replay_digest_;
    // Replay-fence generations are monotonic in the authenticated lifecycle
    // root; a later generation cannot retract previously proven retirement.
    return replay_bank<3 && std::any_of(replay_digest.begin(),replay_digest.end(),
                                         [](std::uint8_t b){return b!=0;});
}
} // namespace gs::hub::storage
