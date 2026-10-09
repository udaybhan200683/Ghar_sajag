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
std::uint64_t get(const Bytes& b, std::size_t p) {
    std::uint64_t n=0; for(unsigned i=0;i<8;++i) n|=std::uint64_t(b[p+i])<<(8*i); return n;
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
            if (!record_at(entry.offset, entry.ordinal, stored_key, minute, frame) ||
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
    if(!read_object(kHead,identity_head,head_found,128))return fault();
    if(count_==0 && !head_found) {
        Bytes genesis;
        if(!seal(2,0,Bytes(32,0),genesis)||!files_.state_replace(kHead,genesis)||
           !read_object(kHead,identity_head,head_found,128)||!head_found||identity_head!=genesis)
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
        security::Key32* event_digest, IdentityOwnerEvidence* owner) {
    std::uint8_t prefix[4]{};
    if(!files_.state_read(kIdentities,offset,prefix,4)) return false;
    const std::uint32_t n=std::uint32_t(prefix[0])|(std::uint32_t(prefix[1])<<8)|
        (std::uint32_t(prefix[2])<<16)|(std::uint32_t(prefix[3])<<24);
    if(n<44 || n>512 || offset>maximum_identity_bytes-n-4) return false;
    frame.resize(n+4); std::copy_n(prefix,4,frame.begin());
    if(!files_.state_read(kIdentities,offset+4,frame.data()+4,n)) return false;
    std::uint64_t ordinal=0; Bytes plain;
    if(!open(1,Bytes(frame.begin()+4,frame.end()),ordinal,plain)||ordinal!=expected||plain.size()<35)
        return false;
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
    clear_identity_index();
    if(!key_valid_) return fault();
    Bytes head,plain; bool found=false,exists=false; std::uint32_t size=0;
    if(!read_object(kHead,head,found,128)||!files_.state_size(kIdentities,exists,size)) return fault();
    if(found) {
        if(!open(2,head,count_,plain)||plain.size()!=32||
           count_<published_event_highwater||
           count_-published_event_highwater>1) return fault();
        Bytes frame; std::string key; std::optional<std::uint16_t> minute;
        for(std::uint64_t i=1;i<=count_;++i) {
            if(!record_at(bytes_,i,key,minute,frame)) return fault();
            if(!insert_identity_index(key,i,bytes_)) return fault();
            bytes_+=frame.size();
        }
        security::Key32 digest{};
        if(count_!=0 && !crypto_.hmac_sha256(key_,frame,digest))return fault();
        if(!crypto_.constant_time_equal(digest.data(),plain.data(),32))return fault();
    } else if(published_event_highwater!=0) {
        // Only an explicit retained-body migration may create the independent ledger.
        return fault();
    }
    if(size<bytes_ || size-bytes_>516) return fault();
    if(size>bytes_ && !files_.state_truncate(kIdentities,bytes_)) return fault();
    Bytes checkpoint; std::uint64_t boundary=0; bool cp=false;
    if(!load_checkpoint(checkpoint,boundary,cp)||boundary>published_event_highwater||
       (!cp && (count_!=0 || found))) return fault();
    committed_highwater_=published_event_highwater; ready_=true; return true;
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
       !files_.state_append_sync(kIdentities,frame)) return fault();
    Bytes verify; std::string exact; std::optional<std::uint16_t> m;
    if(!record_at(bytes_,ordinal,exact,m,verify)||verify!=frame||
       !files_.state_replace(kHead,head)) return fault();
    bool found=false;
    if(!read_object(kHead,verify,found,128)||!found||verify!=head) return fault();
    if(!insert_identity_index(canonical, ordinal, bytes_)) return fault();
    count_=ordinal; bytes_+=frame.size(); return true;
}
bool RuntimeStateStore::identity_context(const EventKey& key, std::uint64_t ordinal,
                                         std::optional<std::uint16_t>& minute, const DomainEvent* expected_event) {
    if(!healthy() || ordinal==0 || ordinal>count_) return false;
    std::uint32_t offset=ordinal>cursor_ordinal_ ? cursor_offset_ : 0;
    const auto start=ordinal>cursor_ordinal_ ? cursor_ordinal_+1 : 1;
    Bytes frame; std::string exact;security::Key32 expected{};
    for(std::uint64_t i=start;i<=ordinal;++i) {
        if(!record_at(offset,i,exact,minute,frame,&expected)) return fault();
        offset+=frame.size();
    }
    if(expected_event){
        Bytes payload;security::Key32 digest{};
        if(!HubJournal::encode_event_payload(*expected_event,payload)||
           !crypto_.hmac_sha256(key_,payload,digest))return fault();
        crypto_.secure_zero(payload.data(),payload.size());
        if(!crypto_.constant_time_equal(digest.data(),expected.data(),32))return fault();
    }
    cursor_ordinal_=ordinal; cursor_offset_=offset;
    return exact==key.str() || fault();
}
bool RuntimeStateStore::lookup_identity(const DomainEvent& event, std::uint64_t& ordinal,
        std::optional<std::uint16_t>& local_minute, bool& found, bool& payload_matches,
        IdentityOwnerEvidence* owner) {
    ordinal = 0;
    local_minute.reset();
    found = false;
    payload_matches = false;
    if (owner != nullptr) *owner = {};
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
    if (!record_at(offset, ordinal, exact, minute, frame, &stored_digest, owner) ||
        exact != event.key.str()) {
        crypto_.secure_zero(expected_digest.data(), expected_digest.size());
        crypto_.secure_zero(stored_digest.data(), stored_digest.size());
        return fault();
    }
    local_minute = minute;
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
    std::uint32_t offset=0;Bytes frame;std::string exact;
    std::optional<std::uint16_t> minute;security::Key32 digest{},expected{};
    // This integrity check streams; it retains no historical payloads in RAM.
    for(std::uint64_t i=1;i<=ordinal;++i){
        if(!record_at(offset,i,exact,minute,frame,&expected))return fault();
        offset+=frame.size();
    }
    Bytes payload;
    if(exact!=event.key.str() || !HubJournal::encode_event_payload(event,payload)||
       !crypto_.hmac_sha256(key_,payload,digest))return fault();
    crypto_.secure_zero(payload.data(),payload.size());
    return crypto_.constant_time_equal(digest.data(),expected.data(),32) || fault();
}
} // namespace gs::hub::storage
