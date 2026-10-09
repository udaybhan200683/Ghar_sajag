#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"

#include <cstddef>
#include <cstdint>
#include <string>

namespace gs::hub::storage {

enum class AdmissionClass : std::uint8_t { Ordinary, Protected };

enum class OutboxAdmission : std::uint8_t {
    Committed,
    Duplicate,
    ReserveProtected,
    CapacityExhausted,
    IdentityConflict,
    InvalidRecord,
    IndexMemoryUnavailable,
    StorageFailure,
    MetadataPublicationFailure,
    IntegrityFailure,
    RestartRequired,
    UnsupportedConfiguration,
};

enum class OutboxRecovery : std::uint8_t {
    Ready,
    Empty,
    UnsupportedConfiguration,
    StorageFailure,
    IntegrityFailure,
    IndexMemoryUnavailable,
};

enum class IdentityLookup : std::uint8_t { Found, Staged, Missing, IntegrityFailure };

// SegmentStore owns the block/filesystem adapter. Append is allowed to leave a
// torn tail when it returns false; the outbox never ACKs that operation and
// requires recovery before another admission. sync() is the durability barrier.
class SegmentStore {
public:
    virtual ~SegmentStore() = default;
    virtual std::uint64_t partition_capacity_bytes() const = 0;
    virtual bool segment_size(std::uint16_t segment, bool& exists,
                              std::uint32_t& bytes) = 0;
    virtual bool read(std::uint16_t segment, std::uint32_t offset,
                      std::uint8_t* output, std::size_t requested,
                      std::size_t& actual) = 0;
    virtual bool append(std::uint16_t segment, const std::uint8_t* data,
                        std::size_t length) = 0;
    virtual bool sync(std::uint16_t segment) = 0;
    // One atomically replaced, authenticated publication marker anchors the
    // latest committed ordinal to its exact encrypted record. A missing marker
    // beside any record is recovery uncertainty and must fail closed.
    virtual bool read_publication(security::Bytes& marker, bool& found) = 0;
    virtual bool publish_publication(const security::Bytes& marker) = 0;
};

struct OutboxLimits {
    // The S3 candidate uses 16 bounded segment files of 240 KiB each. The
    // remaining partition bytes are left to LittleFS metadata and GC workspace.
    std::uint16_t segment_count{16};
    std::uint32_t segment_bytes{240U * 1024U};
    std::uint32_t filesystem_workspace_bytes{256U * 1024U};
    // Engineering candidate only; this is not a product critical-event guarantee.
    std::uint32_t protected_capacity_bytes{512U * 1024U};
    std::uint16_t maximum_key_bytes{256};
    std::uint16_t maximum_payload_bytes{1024};
};

class StorageCapacityPolicy {
public:
    explicit StorageCapacityPolicy(std::uint32_t protected_capacity_bytes)
        : protected_capacity_bytes_(protected_capacity_bytes) {}

    bool permits(AdmissionClass admission_class, std::uint64_t charged_bytes,
                 std::uint64_t used_bytes, std::uint64_t log_capacity_bytes) const;

private:
    std::uint32_t protected_capacity_bytes_;
};

// Append-only first slice of the S3 storage lifecycle. Every record contains
// the exact canonical EventKey and the caller's versioned event payload, both
// authenticated and encrypted. The reconstructible identity index is bounded
// by bytes actually stored and uses PSRAM on ESP32; event bodies are streamed.
// Backend completion and segment retirement are deliberately separate follow-up
// transitions so this class cannot reclaim an event on transport activity alone.
class DurableEventOutbox {
public:
    using RecordVisitor = bool (*)(void* context, std::uint64_t ordinal,
                                   const std::string& canonical_event_key,
                                   const security::Bytes& payload);

    DurableEventOutbox(SegmentStore& storage, security::CommissioningCrypto& crypto,
                       const security::Key32& master_storage_key,
                       OutboxLimits limits = {});
    ~DurableEventOutbox();
    DurableEventOutbox(const DurableEventOutbox&) = delete;
    DurableEventOutbox& operator=(const DurableEventOutbox&) = delete;

    OutboxRecovery recover();
    OutboxAdmission append(const std::string& canonical_event_key,
                           const security::Bytes& versioned_payload,
                           AdmissionClass admission_class);
    IdentityLookup contains(const std::string& canonical_event_key, bool& found);
    bool for_each(RecordVisitor visitor, void* context);

    std::uint64_t record_count() const { return published_ordinal_; }
    std::uint64_t committed_frame_bytes() const { return committed_frame_bytes_; }
    std::uint64_t capacity_budget_used_bytes() const { return capacity_budget_used_bytes_; }
    std::uint64_t log_capacity_bytes() const { return log_capacity_bytes_; }
    bool healthy() const { return initialized_ && !faulted_; }

private:
    struct IndexEntry;

    bool derive_keys(const security::Key32& master_storage_key);
    bool reserve_index(std::size_t required);
    IndexEntry& entry_at(std::size_t index);
    const IndexEntry& entry_at(std::size_t index) const;
    void clear_index();
    bool insert_index(const IndexEntry& entry);
    std::size_t find_index(const std::uint8_t digest[32]) const;
    bool digest_identity(const std::string& key, std::uint8_t digest[32]);
    bool encode_record(std::uint64_t ordinal, const std::string& key,
                       const security::Bytes& payload, security::Bytes& frame);
    bool encode_publication(std::uint64_t ordinal,
                            const std::uint8_t frame_digest[32],
                            security::Bytes& marker);
    bool decode_publication(const security::Bytes& marker,
                            std::uint64_t& ordinal,
                            std::uint8_t frame_digest[32]);
    bool publish_through(std::uint64_t ordinal,
                         const std::uint8_t frame_digest[32]);
    bool decode_record(std::uint16_t segment, std::uint32_t offset,
                       std::uint32_t frame_bytes, std::uint64_t expected_ordinal,
                       IndexEntry* index_entry, std::string& key,
                       security::Bytes& payload,
                       std::uint8_t frame_digest[32] = nullptr);
    OutboxRecovery fail(OutboxRecovery result);

    SegmentStore& storage_;
    security::CommissioningCrypto& crypto_;
    OutboxLimits limits_;
    StorageCapacityPolicy capacity_policy_;
    security::Key32 event_key_{};
    security::Key32 identity_key_{};
    security::Key32 publication_key_{};
    IndexEntry** index_blocks_{nullptr};
    std::size_t index_size_{0};
    std::size_t index_block_count_{0};
    std::size_t index_table_capacity_{0};
    std::uint64_t log_capacity_bytes_{0};
    std::uint64_t committed_frame_bytes_{0};
    std::uint64_t capacity_budget_used_bytes_{0};
    std::uint64_t next_ordinal_{1};
    std::uint64_t published_ordinal_{0};
    std::uint8_t staged_frame_digest_[32]{};
    std::uint16_t append_segment_{0};
    std::uint32_t append_offset_{0};
    bool initialized_{false};
    bool faulted_{false};
    bool has_records_{false};
    bool key_valid_{false};
};

}  // namespace gs::hub::storage
