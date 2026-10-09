#include "storage/durable_event_outbox.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>

#ifdef ESP_PLATFORM
#include "esp_heap_caps.h"
#endif

namespace gs::hub::storage {
namespace {
constexpr std::size_t kPrefixBytes = 20;
constexpr std::size_t kNonceBytes = 12;
constexpr std::size_t kTagBytes = 16;
constexpr std::size_t kCrcBytes = 4;
constexpr std::size_t kFrameOverheadBytes = kPrefixBytes + kNonceBytes + kTagBytes + kCrcBytes;
constexpr std::size_t kMinimumFrameBytes = kFrameOverheadBytes + 2;
constexpr std::uint8_t kFormatVersion = 1;
constexpr std::uint8_t kEventRecord = 1;
constexpr std::uint8_t kMagic[4] = {'G', 'S', 'O', 'X'};
constexpr std::uint8_t kPublicationMagic[4] = {'G', 'S', 'H', 'D'};
constexpr std::size_t kPublicationBodyBytes = 48;
constexpr std::size_t kPublicationBytes = kPublicationBodyBytes + 32;
constexpr std::size_t kIndexBlockEntries = 256;
constexpr char kKeyContext[] = "GharSajag/HubOutbox/EventEncryption/v1";
constexpr char kIdentityContext[] = "GharSajag/HubOutbox/EventIdentity/v1";
constexpr char kPublicationContext[] = "GharSajag/HubOutbox/Publication/v1";

void put_u16(security::Bytes& out, std::uint16_t value) {
    out.push_back(static_cast<std::uint8_t>(value >> 8));
    out.push_back(static_cast<std::uint8_t>(value));
}

void put_u32(std::uint8_t* out, std::uint32_t value) {
    out[0] = static_cast<std::uint8_t>(value >> 24);
    out[1] = static_cast<std::uint8_t>(value >> 16);
    out[2] = static_cast<std::uint8_t>(value >> 8);
    out[3] = static_cast<std::uint8_t>(value);
}

void put_u64(std::uint8_t* out, std::uint64_t value) {
    for (unsigned i = 0; i < 8; ++i)
        out[i] = static_cast<std::uint8_t>(value >> (56U - 8U * i));
}

std::uint16_t get_u16(const std::uint8_t* in) {
    return static_cast<std::uint16_t>((static_cast<std::uint16_t>(in[0]) << 8) | in[1]);
}

std::uint32_t get_u32(const std::uint8_t* in) {
    return (static_cast<std::uint32_t>(in[0]) << 24) |
           (static_cast<std::uint32_t>(in[1]) << 16) |
           (static_cast<std::uint32_t>(in[2]) << 8) | in[3];
}

std::uint64_t get_u64(const std::uint8_t* in) {
    std::uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8) | in[i];
    return value;
}

std::uint32_t crc32(const std::uint8_t* data, std::size_t length) {
    std::uint32_t crc = 0xffffffffU;
    for (std::size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return ~crc;
}

void* allocate_index(std::size_t bytes) {
#ifdef ESP_PLATFORM
    return heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
#else
    return std::malloc(bytes);
#endif
}

void release_index(void* memory) {
#ifdef ESP_PLATFORM
    heap_caps_free(memory);
#else
    std::free(memory);
#endif
}

int compare_digest(const std::uint8_t left[32], const std::uint8_t right[32]) {
    return std::memcmp(left, right, 32);
}
}  // namespace

struct DurableEventOutbox::IndexEntry {
    std::uint8_t identity_digest[32]{};
    std::uint64_t ordinal{0};
    std::uint32_t offset{0};
    std::uint32_t frame_bytes{0};
    std::uint16_t segment{0};
    std::uint16_t reserved{0};
};

bool StorageCapacityPolicy::permits(AdmissionClass admission_class,
                                    std::uint64_t charged_bytes,
                                    std::uint64_t used_bytes,
                                    std::uint64_t log_capacity_bytes) const {
    if (used_bytes > log_capacity_bytes || charged_bytes > log_capacity_bytes - used_bytes)
        return false;
    if (admission_class == AdmissionClass::Protected) return true;
    const auto remaining = log_capacity_bytes - used_bytes - charged_bytes;
    return remaining >= protected_capacity_bytes_;
}

DurableEventOutbox::DurableEventOutbox(
    SegmentStore& storage, security::CommissioningCrypto& crypto,
    const security::Key32& master_storage_key, OutboxLimits limits)
    : storage_(storage), crypto_(crypto), limits_(limits),
      capacity_policy_(limits.protected_capacity_bytes) {
    (void)derive_keys(master_storage_key);
}

DurableEventOutbox::~DurableEventOutbox() {
    for (std::size_t i = 0; i < index_block_count_; ++i) {
        crypto_.secure_zero(index_blocks_[i], kIndexBlockEntries * sizeof(IndexEntry));
        release_index(index_blocks_[i]);
    }
    if (index_blocks_ != nullptr) {
        crypto_.secure_zero(index_blocks_, index_table_capacity_ * sizeof(IndexEntry*));
        release_index(index_blocks_);
    }
    crypto_.secure_zero(event_key_.data(), event_key_.size());
    crypto_.secure_zero(identity_key_.data(), identity_key_.size());
    crypto_.secure_zero(publication_key_.data(), publication_key_.size());
    crypto_.secure_zero(staged_frame_digest_, sizeof(staged_frame_digest_));
}

bool DurableEventOutbox::derive_keys(const security::Key32& master_storage_key) {
    security::Key32 master = master_storage_key;
    const security::Bytes salt{'G', 'S', 'O', 'X', 1};
    const security::Bytes context(kKeyContext, kKeyContext + sizeof(kKeyContext) - 1);
    const bool event_ok = crypto_.hkdf_sha256(master, salt, context, event_key_);
    const security::Bytes identity_context(kIdentityContext,
        kIdentityContext + sizeof(kIdentityContext) - 1);
    const bool identity_ok = crypto_.hkdf_sha256(master, salt, identity_context,
                                                   identity_key_);
    const security::Bytes publication_context(kPublicationContext,
        kPublicationContext + sizeof(kPublicationContext) - 1);
    const bool publication_ok = crypto_.hkdf_sha256(master, salt,
                                                      publication_context,
                                                      publication_key_);
    crypto_.secure_zero(master.data(), master.size());
    const auto nonzero = [](const security::Key32& key) {
        return std::any_of(key.begin(), key.end(), [](std::uint8_t value) {
            return value != 0;
        });
    };
    key_valid_ = event_ok && identity_ok && publication_ok && nonzero(event_key_) &&
                 nonzero(identity_key_) && nonzero(publication_key_);
    return key_valid_;
}

bool DurableEventOutbox::reserve_index(std::size_t required) {
    const auto blocks_required = (required + kIndexBlockEntries - 1) / kIndexBlockEntries;
    if (blocks_required > index_table_capacity_) {
        std::size_t next = index_table_capacity_ == 0 ? 1 : index_table_capacity_;
        while (next < blocks_required) {
            if (next > std::numeric_limits<std::size_t>::max() / 2) return false;
            next *= 2;
        }
        if (next > std::numeric_limits<std::size_t>::max() / sizeof(IndexEntry*))
            return false;
        auto** replacement = static_cast<IndexEntry**>(
            allocate_index(next * sizeof(IndexEntry*)));
        if (replacement == nullptr) return false;
        for (std::size_t i = 0; i < next; ++i)
            ::new (static_cast<void*>(replacement + i)) IndexEntry*(nullptr);
        if (index_block_count_ != 0)
            std::copy_n(index_blocks_, index_block_count_, replacement);
        if (index_blocks_ != nullptr) {
            crypto_.secure_zero(index_blocks_,
                                index_table_capacity_ * sizeof(IndexEntry*));
            release_index(index_blocks_);
        }
        index_blocks_ = replacement;
        index_table_capacity_ = next;
    }
    while (index_block_count_ < blocks_required) {
        auto* block = static_cast<IndexEntry*>(
            allocate_index(kIndexBlockEntries * sizeof(IndexEntry)));
        if (block == nullptr) return false;
        for (std::size_t i = 0; i < kIndexBlockEntries; ++i)
            ::new (static_cast<void*>(block + i)) IndexEntry{};
        index_blocks_[index_block_count_++] = block;
    }
    return true;
}

DurableEventOutbox::IndexEntry& DurableEventOutbox::entry_at(std::size_t index) {
    return index_blocks_[index / kIndexBlockEntries][index % kIndexBlockEntries];
}

const DurableEventOutbox::IndexEntry& DurableEventOutbox::entry_at(
    std::size_t index) const {
    return index_blocks_[index / kIndexBlockEntries][index % kIndexBlockEntries];
}

void DurableEventOutbox::clear_index() {
    for (std::size_t i = 0; i < index_block_count_; ++i)
        crypto_.secure_zero(index_blocks_[i], kIndexBlockEntries * sizeof(IndexEntry));
    index_size_ = 0;
}

std::size_t DurableEventOutbox::find_index(const std::uint8_t digest[32]) const {
    std::size_t first = 0;
    std::size_t count = index_size_;
    while (count != 0) {
        const auto step = count / 2;
        const auto middle = first + step;
        const int order = compare_digest(entry_at(middle).identity_digest, digest);
        if (order < 0) {
            first = middle + 1;
            count -= step + 1;
        } else {
            count = step;
        }
    }
    return first;
}

bool DurableEventOutbox::insert_index(const IndexEntry& entry) {
    if (!reserve_index(index_size_ + 1)) return false;
    const auto at = find_index(entry.identity_digest);
    if (at < index_size_ &&
        compare_digest(entry_at(at).identity_digest, entry.identity_digest) == 0)
        return false;
    for (std::size_t cursor = index_size_; cursor > at; --cursor)
        entry_at(cursor) = entry_at(cursor - 1);
    entry_at(at) = entry;
    ++index_size_;
    return true;
}

bool DurableEventOutbox::digest_identity(const std::string& key, std::uint8_t digest[32]) {
    security::Bytes message(kIdentityContext, kIdentityContext + sizeof(kIdentityContext) - 1);
    message.insert(message.end(), key.begin(), key.end());
    security::Key32 result{};
    if (!crypto_.hmac_sha256(identity_key_, message, result)) return false;
    std::memcpy(digest, result.data(), result.size());
    crypto_.secure_zero(result.data(), result.size());
    crypto_.secure_zero(message.data(), message.size());
    return true;
}

bool DurableEventOutbox::encode_record(std::uint64_t ordinal, const std::string& key,
                                       const security::Bytes& payload,
                                       security::Bytes& frame) {
    if (!key_valid_ || key.empty() || key.size() > limits_.maximum_key_bytes ||
        payload.size() > limits_.maximum_payload_bytes || key.size() > 0xffffU ||
        payload.size() > std::numeric_limits<std::uint32_t>::max() - key.size() - 2U)
        return false;
    security::Bytes plain;
    plain.reserve(2 + key.size() + payload.size());
    put_u16(plain, static_cast<std::uint16_t>(key.size()));
    plain.insert(plain.end(), key.begin(), key.end());
    plain.insert(plain.end(), payload.begin(), payload.end());

    std::array<std::uint8_t, kPrefixBytes> prefix{};
    std::memcpy(prefix.data(), kMagic, sizeof(kMagic));
    prefix[4] = kFormatVersion;
    prefix[5] = kEventRecord;
    prefix[6] = 0;
    prefix[7] = 0;
    put_u64(prefix.data() + 8, ordinal);
    put_u32(prefix.data() + 16, static_cast<std::uint32_t>(plain.size()));

    security::Nonce12 nonce{};
    security::GcmTag tag{};
    security::Bytes cipher;
    const security::Bytes aad(prefix.begin(), prefix.end());
    if (!crypto_.random_bytes(nonce.data(), nonce.size()) ||
        !crypto_.seal_aes256_gcm(event_key_, nonce, aad, plain, cipher, tag)) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    frame.clear();
    frame.reserve(prefix.size() + nonce.size() + cipher.size() + tag.size() + kCrcBytes);
    frame.insert(frame.end(), prefix.begin(), prefix.end());
    frame.insert(frame.end(), nonce.begin(), nonce.end());
    frame.insert(frame.end(), cipher.begin(), cipher.end());
    frame.insert(frame.end(), tag.begin(), tag.end());
    const auto crc = crc32(frame.data(), frame.size());
    frame.push_back(static_cast<std::uint8_t>(crc >> 24));
    frame.push_back(static_cast<std::uint8_t>(crc >> 16));
    frame.push_back(static_cast<std::uint8_t>(crc >> 8));
    frame.push_back(static_cast<std::uint8_t>(crc));
    crypto_.secure_zero(plain.data(), plain.size());
    return true;
}

bool DurableEventOutbox::encode_publication(
    std::uint64_t ordinal, const std::uint8_t frame_digest[32],
    security::Bytes& marker) {
    if (!key_valid_ || ordinal == 0 || frame_digest == nullptr) return false;
    marker.assign(kPublicationBytes, 0);
    std::copy_n(kPublicationMagic, sizeof(kPublicationMagic), marker.begin());
    marker[4] = kFormatVersion;
    put_u64(marker.data() + 8, ordinal);
    std::copy_n(frame_digest, 32, marker.begin() + 16);
    security::Bytes authenticated(marker.begin(), marker.begin() + kPublicationBodyBytes);
    security::Key32 mac{};
    const bool ok = crypto_.hmac_sha256(publication_key_, authenticated, mac);
    crypto_.secure_zero(authenticated.data(), authenticated.size());
    if (!ok) {
        crypto_.secure_zero(mac.data(), mac.size());
        marker.clear();
        return false;
    }
    std::copy(mac.begin(), mac.end(), marker.begin() + kPublicationBodyBytes);
    crypto_.secure_zero(mac.data(), mac.size());
    return true;
}

bool DurableEventOutbox::decode_publication(
    const security::Bytes& marker, std::uint64_t& ordinal,
    std::uint8_t frame_digest[32]) {
    if (!key_valid_ || marker.size() != kPublicationBytes || frame_digest == nullptr ||
        !std::equal(std::begin(kPublicationMagic), std::end(kPublicationMagic),
                    marker.begin()) || marker[4] != kFormatVersion || marker[5] != 0 ||
        marker[6] != 0 || marker[7] != 0)
        return false;
    security::Bytes authenticated(marker.begin(), marker.begin() + kPublicationBodyBytes);
    security::Key32 expected{};
    const bool mac_ok = crypto_.hmac_sha256(publication_key_, authenticated, expected);
    crypto_.secure_zero(authenticated.data(), authenticated.size());
    const bool equal = mac_ok && crypto_.constant_time_equal(
        expected.data(), marker.data() + kPublicationBodyBytes, expected.size());
    crypto_.secure_zero(expected.data(), expected.size());
    if (!equal) return false;
    ordinal = get_u64(marker.data() + 8);
    if (ordinal == 0) return false;
    std::copy_n(marker.data() + 16, 32, frame_digest);
    return true;
}

bool DurableEventOutbox::publish_through(
    std::uint64_t ordinal, const std::uint8_t frame_digest[32]) {
    security::Bytes marker;
    if (!encode_publication(ordinal, frame_digest, marker) ||
        !storage_.publish_publication(marker))
        return false;
    security::Bytes observed;
    bool found = false;
    if (!storage_.read_publication(observed, found) || !found || observed != marker)
        return false;
    std::uint64_t observed_ordinal = 0;
    std::uint8_t observed_digest[32]{};
    const bool valid = decode_publication(observed, observed_ordinal, observed_digest) &&
        observed_ordinal == ordinal &&
        crypto_.constant_time_equal(observed_digest, frame_digest, sizeof(observed_digest));
    crypto_.secure_zero(observed_digest, sizeof(observed_digest));
    if (!valid) return false;
    published_ordinal_ = ordinal;
    crypto_.secure_zero(staged_frame_digest_, sizeof(staged_frame_digest_));
    return true;
}

bool DurableEventOutbox::decode_record(std::uint16_t segment, std::uint32_t offset,
                                       std::uint32_t frame_bytes,
                                       std::uint64_t expected_ordinal,
                                       IndexEntry* index_entry, std::string& key,
                                       security::Bytes& payload,
                                       std::uint8_t frame_digest[32]) {
    if (frame_bytes < kMinimumFrameBytes) return false;
    security::Bytes frame(frame_bytes);
    std::size_t actual = 0;
    if (!storage_.read(segment, offset, frame.data(), frame.size(), actual) ||
        actual != frame.size()) return false;
    if (std::memcmp(frame.data(), kMagic, sizeof(kMagic)) != 0 ||
        frame[4] != kFormatVersion || frame[5] != kEventRecord ||
        frame[6] != 0 || frame[7] != 0 ||
        get_u64(frame.data() + 8) != expected_ordinal ||
        static_cast<std::uint64_t>(get_u32(frame.data() + 16)) +
            kFrameOverheadBytes != frame_bytes)
        return false;
    const auto expected_crc = get_u32(frame.data() + frame.size() - kCrcBytes);
    if (crc32(frame.data(), frame.size() - kCrcBytes) != expected_crc) return false;

    const auto plain_bytes = get_u32(frame.data() + 16);
    security::Nonce12 nonce{};
    std::copy_n(frame.data() + kPrefixBytes, nonce.size(), nonce.data());
    security::GcmTag tag{};
    std::copy_n(frame.data() + kPrefixBytes + nonce.size() + plain_bytes,
                tag.size(), tag.data());
    const security::Bytes aad(frame.begin(), frame.begin() + kPrefixBytes);
    const security::Bytes cipher(frame.begin() + kPrefixBytes + nonce.size(),
                                 frame.begin() + kPrefixBytes + nonce.size() + plain_bytes);
    security::Bytes plain;
    if (!crypto_.open_aes256_gcm(event_key_, nonce, aad, cipher, tag, plain) ||
        plain.size() < 2) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    const auto key_bytes = get_u16(plain.data());
    if (key_bytes == 0 || key_bytes > limits_.maximum_key_bytes ||
        key_bytes > plain.size() - 2) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    key.assign(reinterpret_cast<const char*>(plain.data() + 2), key_bytes);
    payload.assign(plain.begin() + 2 + key_bytes, plain.end());
    crypto_.secure_zero(plain.data(), plain.size());
    if (payload.size() > limits_.maximum_payload_bytes) {
        crypto_.secure_zero(payload.data(), payload.size());
        return false;
    }
    security::Key32 record_digest{};
    if (!crypto_.hmac_sha256(publication_key_, frame, record_digest)) return false;
    if (frame_digest != nullptr)
        std::copy(record_digest.begin(), record_digest.end(), frame_digest);
    if (index_entry != nullptr) {
        *index_entry = {};
        if (!digest_identity(key, index_entry->identity_digest)) {
            crypto_.secure_zero(record_digest.data(), record_digest.size());
            return false;
        }
        index_entry->ordinal = expected_ordinal;
        index_entry->offset = offset;
        index_entry->frame_bytes = frame_bytes;
        index_entry->segment = segment;
    }
    crypto_.secure_zero(record_digest.data(), record_digest.size());
    return true;
}

OutboxRecovery DurableEventOutbox::fail(OutboxRecovery result) {
    faulted_ = true;
    initialized_ = true;
    return result;
}

OutboxRecovery DurableEventOutbox::recover() {
    initialized_ = false;
    faulted_ = false;
    has_records_ = false;
    committed_frame_bytes_ = 0;
    capacity_budget_used_bytes_ = 0;
    next_ordinal_ = 1;
    published_ordinal_ = 0;
    crypto_.secure_zero(staged_frame_digest_, sizeof(staged_frame_digest_));
    append_segment_ = 0;
    append_offset_ = 0;
    clear_index();
    if (!key_valid_ || limits_.segment_count == 0 || limits_.segment_bytes == 0 ||
        limits_.maximum_key_bytes == 0 ||
        limits_.segment_count > std::numeric_limits<std::uint64_t>::max() /
                                    limits_.segment_bytes)
        return fail(OutboxRecovery::UnsupportedConfiguration);
    log_capacity_bytes_ = static_cast<std::uint64_t>(limits_.segment_count) *
                          limits_.segment_bytes;
    const auto partition_bytes = storage_.partition_capacity_bytes();
    if (log_capacity_bytes_ > partition_bytes ||
        limits_.filesystem_workspace_bytes > partition_bytes - log_capacity_bytes_ ||
        limits_.protected_capacity_bytes > log_capacity_bytes_)
        return fail(OutboxRecovery::UnsupportedConfiguration);

    security::Bytes publication;
    bool publication_found = false;
    if (!storage_.read_publication(publication, publication_found))
        return fail(OutboxRecovery::StorageFailure);
    std::uint64_t publication_ordinal = 0;
    std::uint8_t publication_digest[32]{};
    if (publication_found && !decode_publication(publication, publication_ordinal,
                                                  publication_digest))
        return fail(OutboxRecovery::IntegrityFailure);

    std::int32_t last_existing = -1;
    bool gap = false;
    std::uint64_t physical_file_bytes = 0;
    for (std::uint16_t segment = 0; segment < limits_.segment_count; ++segment) {
        bool exists = false;
        std::uint32_t bytes = 0;
        if (!storage_.segment_size(segment, exists, bytes))
            return fail(OutboxRecovery::StorageFailure);
        if (!exists) { gap = true; continue; }
        if (gap || bytes > limits_.segment_bytes)
            return fail(OutboxRecovery::IntegrityFailure);
        last_existing = segment;
        physical_file_bytes += bytes;
    }

    std::uint64_t expected_ordinal = 1;
    bool torn_tail = false;
    bool last_segment_torn_tail = false;
    std::uint64_t last_torn_ordinal = 0;
    bool publication_record_seen = false;
    for (std::int32_t segment_i = 0; segment_i <= last_existing; ++segment_i) {
        const auto segment = static_cast<std::uint16_t>(segment_i);
        bool exists = false;
        std::uint32_t bytes = 0;
        if (!storage_.segment_size(segment, exists, bytes) || !exists)
            return fail(OutboxRecovery::StorageFailure);
        std::uint32_t offset = 0;
        while (offset < bytes) {
            const auto remaining = bytes - offset;
            if (remaining < kPrefixBytes) {
                torn_tail = true;
                last_segment_torn_tail = segment_i == last_existing;
                last_torn_ordinal = std::max(last_torn_ordinal, expected_ordinal);
                break;
            }
            std::array<std::uint8_t, kPrefixBytes> prefix{};
            std::size_t actual = 0;
            if (!storage_.read(segment, offset, prefix.data(), prefix.size(), actual) ||
                actual != prefix.size()) return fail(OutboxRecovery::StorageFailure);
            if (std::memcmp(prefix.data(), kMagic, sizeof(kMagic)) != 0 ||
                prefix[4] != kFormatVersion || prefix[5] != kEventRecord ||
                prefix[6] != 0 || prefix[7] != 0 ||
                get_u64(prefix.data() + 8) != expected_ordinal)
                return fail(OutboxRecovery::IntegrityFailure);
            const auto plain_bytes = get_u32(prefix.data() + 16);
            const std::uint64_t frame_size_wide =
                static_cast<std::uint64_t>(plain_bytes) + kFrameOverheadBytes;
            if (plain_bytes < 3 || plain_bytes >
                    static_cast<std::uint32_t>(limits_.maximum_key_bytes) +
                    limits_.maximum_payload_bytes + 2U ||
                frame_size_wide > limits_.segment_bytes)
                return fail(OutboxRecovery::IntegrityFailure);
            const auto frame_size = static_cast<std::uint32_t>(frame_size_wide);
            if (frame_size > remaining) {
                torn_tail = true;
                last_segment_torn_tail = segment_i == last_existing;
                last_torn_ordinal = std::max(last_torn_ordinal, expected_ordinal);
                break;
            }
            IndexEntry entry;
            std::string key;
            security::Bytes payload;
            std::uint8_t frame_digest[32]{};
            if (!decode_record(segment, offset, frame_size, expected_ordinal,
                               &entry, key, payload, frame_digest))
                return fail(OutboxRecovery::IntegrityFailure);
            if (publication_found && expected_ordinal == publication_ordinal) {
                if (!crypto_.constant_time_equal(frame_digest, publication_digest,
                                                  sizeof(frame_digest))) {
                    crypto_.secure_zero(frame_digest, sizeof(frame_digest));
                    crypto_.secure_zero(payload.data(), payload.size());
                    return fail(OutboxRecovery::IntegrityFailure);
                }
                publication_record_seen = true;
            }
            if (publication_found && expected_ordinal > publication_ordinal)
                std::copy(frame_digest, frame_digest + sizeof(frame_digest),
                          staged_frame_digest_);
            crypto_.secure_zero(frame_digest, sizeof(frame_digest));
            const auto identity_at = find_index(entry.identity_digest);
            if (identity_at < index_size_ &&
                compare_digest(entry_at(identity_at).identity_digest,
                               entry.identity_digest) == 0) {
                crypto_.secure_zero(payload.data(), payload.size());
                return fail(OutboxRecovery::IntegrityFailure);
            }
            if (!insert_index(entry)) {
                crypto_.secure_zero(payload.data(), payload.size());
                return fail(OutboxRecovery::IndexMemoryUnavailable);
            }
            crypto_.secure_zero(payload.data(), payload.size());
            ++expected_ordinal;
            committed_frame_bytes_ += frame_size;
            offset += frame_size;
        }
    }
    next_ordinal_ = expected_ordinal;
    const auto complete_records = expected_ordinal - 1;
    if (!publication_found) {
        // Without an authenticated publication record, even a well-formed
        // event could have been acknowledged before its marker disappeared.
        if (complete_records != 0) return fail(OutboxRecovery::IntegrityFailure);
    } else if (publication_ordinal > complete_records || !publication_record_seen ||
               complete_records - publication_ordinal > 1) {
        return fail(OutboxRecovery::IntegrityFailure);
    }
    // A single complete record beyond the publication marker can only be the
    // interrupted next admission. Keep its identity so an exact Node retry can
    // finish publication; never expose it to replay or ACK it as committed.
    if (complete_records > publication_ordinal && torn_tail &&
        last_torn_ordinal > complete_records)
        return fail(OutboxRecovery::IntegrityFailure);
    published_ordinal_ = publication_found ? publication_ordinal : 0;
    has_records_ = published_ordinal_ != 0;
    if (last_existing < 0) {
        append_segment_ = 0;
        append_offset_ = 0;
        capacity_budget_used_bytes_ = 0;
    } else {
        const auto last = static_cast<std::uint16_t>(last_existing);
        bool exists = false;
        std::uint32_t bytes = 0;
        if (!storage_.segment_size(last, exists, bytes) || !exists)
            return fail(OutboxRecovery::StorageFailure);
        capacity_budget_used_bytes_ =
            static_cast<std::uint64_t>(last) * limits_.segment_bytes;
        if (last_segment_torn_tail) {
            capacity_budget_used_bytes_ += limits_.segment_bytes;
            append_segment_ = static_cast<std::uint16_t>(last + 1U);
            append_offset_ = 0;
        } else if (bytes == limits_.segment_bytes) {
            capacity_budget_used_bytes_ += limits_.segment_bytes;
            append_segment_ = static_cast<std::uint16_t>(last + 1U);
            append_offset_ = 0;
        } else {
            capacity_budget_used_bytes_ += bytes;
            append_segment_ = last;
            append_offset_ = bytes;
        }
    }
    (void)physical_file_bytes;  // Kept separate from logical budget for future health reporting.
    initialized_ = true;
    return has_records_ ? OutboxRecovery::Ready : OutboxRecovery::Empty;
}

OutboxAdmission DurableEventOutbox::append(
    const std::string& canonical_event_key, const security::Bytes& versioned_payload,
    AdmissionClass admission_class) {
    if (!initialized_ || faulted_) return OutboxAdmission::RestartRequired;
    if (canonical_event_key.empty() || canonical_event_key.size() > limits_.maximum_key_bytes ||
        versioned_payload.size() > limits_.maximum_payload_bytes)
        return OutboxAdmission::InvalidRecord;

    std::uint8_t digest[32]{};
    if (!digest_identity(canonical_event_key, digest)) {
        faulted_ = true;
        return OutboxAdmission::StorageFailure;
    }
    const auto identity_at = find_index(digest);
    if (identity_at < index_size_ &&
        compare_digest(entry_at(identity_at).identity_digest, digest) == 0) {
        std::string stored_key;
        security::Bytes stored_payload;
        const auto& existing = entry_at(identity_at);
        if (!decode_record(existing.segment, existing.offset, existing.frame_bytes,
                           existing.ordinal, nullptr, stored_key, stored_payload)) {
            crypto_.secure_zero(stored_payload.data(), stored_payload.size());
            faulted_ = true;
            return OutboxAdmission::IntegrityFailure;
        }
        if (stored_key != canonical_event_key) {
            crypto_.secure_zero(stored_payload.data(), stored_payload.size());
            faulted_ = true;
            return OutboxAdmission::IntegrityFailure;
        }
        if (stored_payload != versioned_payload) {
            crypto_.secure_zero(stored_payload.data(), stored_payload.size());
            return OutboxAdmission::IdentityConflict;
        }
        crypto_.secure_zero(stored_payload.data(), stored_payload.size());
        if (existing.ordinal <= published_ordinal_)
            return OutboxAdmission::Duplicate;
        if (existing.ordinal != published_ordinal_ + 1 ||
            next_ordinal_ != existing.ordinal + 1)
            return OutboxAdmission::RestartRequired;
        if (!publish_through(existing.ordinal, staged_frame_digest_)) {
            faulted_ = true;
            return OutboxAdmission::MetadataPublicationFailure;
        }
        has_records_ = true;
        return OutboxAdmission::Committed;
    }
    if (!reserve_index(index_size_ + 1)) return OutboxAdmission::IndexMemoryUnavailable;
    if (next_ordinal_ != published_ordinal_ + 1)
        return OutboxAdmission::RestartRequired;

    security::Bytes frame;
    if (!encode_record(next_ordinal_, canonical_event_key, versioned_payload, frame))
        return OutboxAdmission::InvalidRecord;
    if (frame.size() > limits_.segment_bytes) return OutboxAdmission::InvalidRecord;

    auto target_segment = append_segment_;
    auto target_offset = append_offset_;
    std::uint64_t charge = frame.size();
    if (target_offset > limits_.segment_bytes ||
        frame.size() > limits_.segment_bytes - target_offset) {
        charge += limits_.segment_bytes - target_offset;
        ++target_segment;
        target_offset = 0;
    }
    if (target_segment >= limits_.segment_count) return OutboxAdmission::CapacityExhausted;
    if (capacity_budget_used_bytes_ > log_capacity_bytes_ ||
        charge > log_capacity_bytes_ - capacity_budget_used_bytes_)
        return OutboxAdmission::CapacityExhausted;
    if (!capacity_policy_.permits(admission_class, charge,
                                  capacity_budget_used_bytes_, log_capacity_bytes_))
        return OutboxAdmission::ReserveProtected;

    const auto target_offset32 = static_cast<std::uint32_t>(target_offset);
    if (!storage_.append(target_segment, frame.data(), frame.size())) {
        faulted_ = true;
        return OutboxAdmission::RestartRequired;
    }
    if (!storage_.sync(target_segment)) {
        faulted_ = true;
        return OutboxAdmission::RestartRequired;
    }

    IndexEntry entry;
    std::string verified_key;
    security::Bytes verified_payload;
    std::uint8_t frame_digest[32]{};
    if (!decode_record(target_segment, target_offset32,
                       static_cast<std::uint32_t>(frame.size()), next_ordinal_,
                       &entry, verified_key, verified_payload, frame_digest) ||
        verified_key != canonical_event_key || verified_payload != versioned_payload ||
        compare_digest(entry.identity_digest, digest) != 0 ||
        !insert_index(entry)) {
        crypto_.secure_zero(frame_digest, sizeof(frame_digest));
        crypto_.secure_zero(verified_payload.data(), verified_payload.size());
        faulted_ = true;
        return OutboxAdmission::RestartRequired;
    }
    crypto_.secure_zero(verified_payload.data(), verified_payload.size());
    std::copy(frame_digest, frame_digest + sizeof(frame_digest), staged_frame_digest_);
    append_segment_ = target_segment;
    append_offset_ = target_offset32 + static_cast<std::uint32_t>(frame.size());
    capacity_budget_used_bytes_ += charge;
    committed_frame_bytes_ += frame.size();
    ++next_ordinal_;
    has_records_ = true;
    if (append_offset_ == limits_.segment_bytes) {
        ++append_segment_;
        append_offset_ = 0;
    }
    if (!publish_through(entry.ordinal, frame_digest)) {
        crypto_.secure_zero(frame_digest, sizeof(frame_digest));
        faulted_ = true;
        return OutboxAdmission::MetadataPublicationFailure;
    }
    crypto_.secure_zero(frame_digest, sizeof(frame_digest));
    return OutboxAdmission::Committed;
}

IdentityLookup DurableEventOutbox::contains(const std::string& canonical_event_key,
                                             bool& found) {
    found = false;
    if (!initialized_ || faulted_ || canonical_event_key.empty() ||
        canonical_event_key.size() > limits_.maximum_key_bytes)
        return IdentityLookup::IntegrityFailure;
    std::uint8_t digest[32]{};
    if (!digest_identity(canonical_event_key, digest)) {
        faulted_ = true;
        return IdentityLookup::IntegrityFailure;
    }
    const auto at = find_index(digest);
    if (at >= index_size_ || compare_digest(entry_at(at).identity_digest, digest) != 0)
        return IdentityLookup::Missing;
    std::string stored_key;
    security::Bytes payload;
    const auto& entry = entry_at(at);
    if (!decode_record(entry.segment, entry.offset, entry.frame_bytes,
                       entry.ordinal, nullptr, stored_key, payload) ||
        stored_key != canonical_event_key) {
        crypto_.secure_zero(payload.data(), payload.size());
        faulted_ = true;
        return IdentityLookup::IntegrityFailure;
    }
    crypto_.secure_zero(payload.data(), payload.size());
    found = true;
    return entry.ordinal <= published_ordinal_ ? IdentityLookup::Found
                                               : IdentityLookup::Staged;
}

bool DurableEventOutbox::for_each(RecordVisitor visitor, void* context) {
    if (!initialized_ || faulted_ || visitor == nullptr) return false;
    std::uint64_t ordinal = 1;
    for (std::uint16_t segment = 0; segment < limits_.segment_count; ++segment) {
        bool exists = false;
        std::uint32_t bytes = 0;
        if (!storage_.segment_size(segment, exists, bytes)) return false;
        if (!exists) break;
        std::uint32_t offset = 0;
        bool partial_tail = false;
        while (offset < bytes) {
            if (bytes - offset < kPrefixBytes) {
                partial_tail = true;
                break;
            }
            std::array<std::uint8_t, kPrefixBytes> prefix{};
            std::size_t actual = 0;
            if (!storage_.read(segment, offset, prefix.data(), prefix.size(), actual) ||
                actual != prefix.size()) return false;
            const auto plain_bytes = get_u32(prefix.data() + 16);
            const std::uint64_t frame_size_wide = plain_bytes + kFrameOverheadBytes;
            if (frame_size_wide > bytes - offset) {
                partial_tail = true;
                break;
            }
            const auto frame_size = static_cast<std::uint32_t>(frame_size_wide);
            std::string key;
            security::Bytes payload;
            if (ordinal > published_ordinal_) return true;
            if (!decode_record(segment, offset, frame_size, ordinal, nullptr, key, payload) ||
                !visitor(context, ordinal, key, payload)) {
                crypto_.secure_zero(payload.data(), payload.size());
                return false;
            }
            crypto_.secure_zero(payload.data(), payload.size());
            offset += frame_size;
            ++ordinal;
        }
        (void)partial_tail;  // Recovery already proved this is only an uncommitted tail.
    }
    return ordinal == published_ordinal_ + 1;
}

}  // namespace gs::hub::storage
