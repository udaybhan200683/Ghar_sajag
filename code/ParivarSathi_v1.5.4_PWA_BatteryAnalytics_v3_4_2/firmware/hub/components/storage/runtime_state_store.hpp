#pragma once
#include "firmware/common/security/commissioning_crypto.hpp"
#include "gs/domain.hpp"
#include <array>
#include <optional>

namespace gs::hub::storage {
struct IdentityOwnerEvidence {
    std::uint8_t enrollment_slot{0xff};
    std::uint32_t enrollment_generation{0};
    std::array<std::uint8_t, 32> binding_digest{};
    bool authenticated() const;
};
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
};

class RuntimeStateStore {
public:
    static constexpr std::size_t maximum_checkpoint_bytes = 64U * 1024U;
    // Candidate byte budget, not an identity expiration/event-count policy.
    static constexpr std::uint32_t maximum_identity_bytes = 1024U * 1024U;
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
                         IdentityOwnerEvidence* owner = nullptr);
    // Exact identities, no contiguous watermark across sequence gaps. Body
    // eligibility is separate; this ledger never expires evidence in Phase 1.
    bool contains_identity(const EventKey&, bool& found);
    bool verify_event_identity(const DomainEvent&, std::uint64_t ordinal);
    // Called only after the event outbox's authenticated publication succeeds.
    bool confirm_event_publication(std::uint64_t boundary);
    bool healthy() const { return ready_ && !faulted_; }
    std::uint64_t identities() const { return count_; }
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
                   IdentityOwnerEvidence* owner = nullptr);
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
    std::size_t checkpoint_bytes_{0};
    std::uint64_t cursor_ordinal_{0};
    std::uint32_t cursor_offset_{0};
    bool ready_{false}, faulted_{false}, key_valid_{false};
};
} // namespace gs::hub::storage
