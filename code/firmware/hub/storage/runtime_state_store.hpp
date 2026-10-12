#pragma once
#include "firmware/common/security/commissioning_crypto.hpp"
#include "gs/domain.hpp"
#include <array>
#include <optional>
#include <string>

namespace gs::hub::storage {
struct IdentityOwnerEvidence {
    std::uint8_t enrollment_slot{0xff};
    std::uint32_t enrollment_generation{0};
    std::array<std::uint8_t, 32> binding_digest{};
    bool authenticated() const;
};
struct IdentityCompactionRecord {
    std::string event_key;
    std::uint64_t original_ordinal{0};
    std::uint32_t encoded_bytes{0};
    std::optional<std::uint16_t> local_minute;
    security::Key32 payload_digest{};
    IdentityOwnerEvidence owner{};
};
enum class IdentityCompactionDisposition : std::uint8_t { Retain, Fenced, Blocked };
struct IdentityCompactionPlan {
    std::uint64_t source_records{0};
    std::uint32_t source_bytes{0};
    std::uint64_t retained_records{0};
    std::uint64_t fenced_records{0};
    std::uint64_t blocked_records{0};
    std::uint32_t candidate_record_bytes{0};
    // During planning this is the record-only lower bound. A compaction run
    // raises it to candidate bytes plus the enforced free-space reserve.
    std::uint32_t minimum_temporary_bytes{0};
    std::uint32_t temporary_safety_reserve_bytes{0};
    // Authenticated fingerprints of the exact source head and ordered future
    // retained-row stream. These are planning evidence, not publication roots.
    security::Key32 source_head_digest{};
    security::Key32 candidate_digest{};
    bool complete{false};
};
using IdentityCompactionClassifier = IdentityCompactionDisposition (*)(
    void*, const IdentityCompactionRecord&);
using IdentityCompactionRetainedVisitor = bool (*)(
    void*, const IdentityCompactionRecord&);
using IdentityCompactionAuthorityValidator = bool (*)(void*);
// All files belong to the SAME serialized LittleFS writer as the event log.
// replace is atomic old-or-new with a durability barrier; append_sync may tear.
class RuntimeStateFiles {
public:
    virtual ~RuntimeStateFiles() = default;
    virtual bool state_size(const char* name, bool& found, std::uint32_t& size) = 0;
    virtual bool state_read(const char* name, std::uint32_t offset,
                           std::uint8_t* out, std::size_t size) = 0;
    virtual bool state_append_sync(const char* name, const security::Bytes& data) = 0;
    virtual bool state_replace(const char* name, const security::Bytes& data) = 0;
    virtual bool state_truncate(const char* name, std::uint32_t size) = 0;
    // Identity generation staging primitives. Capacity is filesystem free
    // space from the backing adapter, not a logical quota estimate.
    virtual bool state_capacity(std::uint64_t& total, std::uint64_t& used) = 0;
    virtual bool state_remove(const char* name) = 0;
    virtual bool state_sync(const char* name) = 0;
};

class RuntimeStateStore {
public:
    static constexpr std::size_t maximum_checkpoint_bytes = 64U * 1024U;
    // Candidate byte budget, not an identity expiration/event-count policy.
    static constexpr std::uint32_t maximum_identity_bytes = 1024U * 1024U;
    static constexpr std::uint32_t minimum_compaction_safety_reserve_bytes = 16U * 1024U;
    RuntimeStateStore(RuntimeStateFiles&, security::CommissioningCrypto&, const security::Key32&);
    ~RuntimeStateStore();
    // The argument is the outbox publication high-water mark, not the count of
    // physical bodies currently retained. A durable reducer checkpoint may
    // cover bodies that a later lifecycle phase safely retires.
    bool recover(std::uint64_t published_event_highwater);
    bool load_checkpoint(security::Bytes&, std::uint64_t& boundary, bool& found);
    bool save_checkpoint(const security::Bytes&, std::uint64_t boundary);
    bool prepare_identity(const DomainEvent&, std::uint64_t ordinal,
                          std::optional<std::uint16_t> local_minute,
                          const IdentityOwnerEvidence* owner = nullptr);
    bool identity_context(const EventKey&, std::uint64_t ordinal,
                          std::optional<std::uint16_t>& local_minute,
                          const DomainEvent* expected_event = nullptr);
    // Finds exact retry identities independently of outbox body retention.
    // `payload_matches` is false when an authenticated key is reused with
    // different immutable event contents; callers must reject that conflict.
    bool lookup_identity(const DomainEvent&, std::uint64_t& ordinal,
                         std::optional<std::uint16_t>& local_minute,
                         bool& found, bool& payload_matches,
                         IdentityOwnerEvidence* owner = nullptr,
                         security::Key32* payload_digest = nullptr);
    // Exact identities, no contiguous watermark across sequence gaps. Body
    // eligibility is separate; this ledger never expires evidence in Phase 1.
    bool contains_identity(const EventKey&, bool& found);
    bool verify_event_identity(const DomainEvent&, std::uint64_t ordinal);
    // Read-only streaming plan. The visitor sees retained rows in original
    // order; no identity or authority file is changed. Candidate bytes are a
    // lower bound because a future manifest/publication format is not defined.
    bool plan_identity_compaction(IdentityCompactionClassifier,
                                 IdentityCompactionRetainedVisitor,
                                 void* context, IdentityCompactionPlan&);
    bool compact_identity(IdentityCompactionClassifier, void* classifier_context,
                          const security::Bytes& replay_authority,
                          std::uint64_t replay_epoch,
                          std::uint64_t replay_generation,
                          std::uint8_t replay_bank,
                          const security::Key32& replay_digest,
                          IdentityCompactionAuthorityValidator authority_current,
                          void* authority_context,
                          std::uint32_t safety_reserve_bytes,
                          IdentityCompactionPlan&);
    bool compaction_authority_matches(std::uint64_t replay_epoch,
                                      std::uint64_t replay_generation,
                                      std::uint8_t replay_bank,
                                      const security::Key32& replay_digest) const;
    // Called only after the event outbox's authenticated publication succeeds.
    bool confirm_event_publication(std::uint64_t boundary);
    bool healthy() const { return ready_ && !faulted_; }
    std::size_t identities() const { return identity_index_size_; }
    std::uint32_t identity_bytes() const { return bytes_; }
    std::size_t checkpoint_bytes() const { return checkpoint_bytes_; }
private:
    struct IdentityIndexEntry;
    bool seal(std::uint8_t type, std::uint64_t ordinal, const security::Bytes&, security::Bytes&);
    bool open(std::uint8_t type, const security::Bytes&, std::uint64_t&, security::Bytes&);
    bool read_object(const char*, security::Bytes&, bool&, std::size_t maximum);
    bool record_at(std::uint32_t offset, std::uint64_t expected, std::string& key,
                   std::optional<std::uint16_t>& minute, security::Bytes& frame,
                   security::Key32* event_digest = nullptr,
                   IdentityOwnerEvidence* owner = nullptr,
                   std::uint64_t* actual_ordinal = nullptr,
                   const char* file = "identity.log");
    bool reserve_identity_index(std::size_t required);
    bool insert_identity_index(const std::string& key, std::uint64_t ordinal,
                               std::uint32_t offset);
    bool find_identity_index(const std::string& key, std::uint64_t& ordinal,
                             std::uint32_t& offset, bool& found);
    void clear_identity_index();
    bool fault() { faulted_ = true; return false; }
    RuntimeStateFiles& files_;
    security::CommissioningCrypto& crypto_;
    security::Key32 key_{};
    IdentityIndexEntry* identity_index_{nullptr};
    std::size_t identity_index_capacity_{0};
    std::size_t identity_index_size_{0};
    std::uint64_t count_{0};
    std::uint64_t committed_highwater_{0};
    std::uint32_t bytes_{0};
    std::uint8_t active_slot_{0};
    std::string active_identity_file_{"identity.log"};
    std::uint64_t replay_epoch_{0}, replay_generation_{0};
    std::uint8_t replay_bank_{0};
    security::Key32 replay_digest_{};
    security::Key32 compacted_plan_digest_{};
    bool compacted_{false};
    std::size_t checkpoint_bytes_{0};
    std::uint64_t cursor_ordinal_{0};
    std::uint32_t cursor_offset_{0};
    bool ready_{false}, faulted_{false}, key_valid_{false};
};
} // namespace gs::hub::storage
