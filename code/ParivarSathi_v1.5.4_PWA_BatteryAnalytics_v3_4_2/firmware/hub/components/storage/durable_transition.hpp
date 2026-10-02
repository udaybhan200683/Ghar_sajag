#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace gs::hub::durable {

constexpr std::size_t kMaxTransitionBytes = 1332;
constexpr std::size_t kMaxCheckpointBytes = 4514;
constexpr std::size_t kMaxPendingChunkBytes = 1260;
constexpr std::size_t kMaxDedupeEvidenceChunkBytes = 320;
constexpr std::size_t kMaxBitmapBytes = 384;
constexpr std::size_t kMaxCausalInputBytes = 448;
constexpr std::size_t kMaxDecisionBytes = 128;
constexpr std::size_t kMaxEffectPayloadBytes = 256;
constexpr std::size_t kMaxEffectsPerTransition = 3;
constexpr std::size_t kMaxPendingEffects = 16;
constexpr std::size_t kMaxEffectsPerChunk = 4;
constexpr std::size_t kMaxCheckpointEffectRefs = 16;
constexpr std::size_t kMaxCheckpointChunkRefs = 32;
constexpr std::size_t kMaxDedupeEvidenceRefs = 32;

enum class TransitionType : std::uint8_t { Event = 1, Timer = 2, Registry = 3, ConfigApply = 4 };

struct EventIdentity {
    std::string physical_device_id;
    std::string source_id;
    std::uint64_t session_id{0};
    std::uint64_t sequence{0};
    bool operator==(const EventIdentity& other) const;
    bool operator<(const EventIdentity& other) const;
};

struct Effect {
    std::array<std::uint8_t, 32> id{};
    std::uint32_t kind{0};
    security::Bytes payload;
};

struct Transition {
    std::uint32_t storage_epoch{0};
    std::uint64_t ordinal{0};
    EventIdentity event;
    std::uint8_t enrollment_slot{0};
    std::uint32_t enrollment_generation{0};
    std::array<std::uint8_t, 32> event_digest{};
    bool event_digest_present{true};
    std::uint32_t config_version{0};
    std::array<std::uint8_t, 32> config_hash{};
    TransitionType type{TransitionType::Event};
    // Minimal causal fields after EventIdentity, included in the 228-byte event block.
    security::Bytes causal_input;
    security::Bytes decision;
    std::vector<Effect> effects;
};

struct EffectReference {
    std::uint64_t ordinal{0};
    std::uint8_t index{0};
    std::array<std::uint8_t, 32> id{};
    // 0xff means log-owned; otherwise upper five bits select a chunk ref and
    // lower two bits select its item. Kept in the bounded ten-byte reference.
    std::uint8_t location{0xff};
};

struct ChunkReference {
    std::uint64_t chunk_id{0};
    std::array<std::uint8_t, 32> digest{};
};

struct DedupeEvidenceReference {
    std::uint64_t chunk_id{0};
    std::array<std::uint8_t, 32> digest{};
};

struct ReportSnapshotReference {
    std::uint8_t bank{0xff};
    std::uint64_t generation{0};
    std::array<std::uint8_t, 32> digest{};
    bool valid() const;
};

struct DedupeEvidenceEntry {
    std::uint8_t enrollment_slot{0};
    std::uint32_t enrollment_generation{0};
    std::uint64_t origin_session{0};
    std::uint64_t sequence{0};
    std::array<std::uint8_t, 32> digest{};
};

struct DedupeEvidenceChunk {
    std::uint32_t storage_epoch{0};
    std::uint64_t chunk_id{0};
    std::array<DedupeEvidenceEntry, 4> entries{};
    std::uint8_t count{0};
};

struct Checkpoint {
    std::uint32_t storage_epoch{0};
    std::uint64_t generation{0};
    std::uint64_t covered_ordinal{0};
    std::uint32_t config_version{0};
    std::array<std::uint8_t, 32> config_hash{};
    // Versioned opaque reducer/security state, capped by the whole codec.
    security::Bytes reducer_state;
    std::vector<EffectReference> pending_effects;
    std::vector<ChunkReference> pending_chunks;
    std::vector<DedupeEvidenceReference> dedupe_evidence_chunks;
    std::optional<ReportSnapshotReference> report_snapshot;
    // Decoded schema-1 frontiers have no exact digest and cannot authorize
    // admission or be silently rewritten as exact evidence.
    bool legacy_dedupe_unverified{false};
};

struct PendingEffectChunk {
    std::uint32_t storage_epoch{0};
    std::uint64_t chunk_id{0};
    std::vector<EffectReference> refs;
    std::vector<Effect> effects;
};

struct CompletionBitmap {
    std::uint32_t storage_epoch{0};
    std::uint64_t generation{0};
    std::uint64_t checkpoint_generation{0};
    std::array<std::uint8_t, 32> mapping_digest{};
    std::uint16_t committed_bits{0};
};

class Codec {
public:
    static bool encode_transition(security::CommissioningCrypto&, const security::Key32&,
                                  const Transition&, security::Bytes&);
    static bool decode_transition(security::CommissioningCrypto&, const security::Key32&,
                                  const security::Bytes&, Transition&);
    static bool encode_checkpoint(security::CommissioningCrypto&, const security::Key32&,
                                  const Checkpoint&, security::Bytes&);
    static bool decode_checkpoint(security::CommissioningCrypto&, const security::Key32&,
                                  const security::Bytes&, Checkpoint&);
    static bool encode_chunk(security::CommissioningCrypto&, const security::Key32&,
                             const PendingEffectChunk&, security::Bytes&);
    static bool decode_chunk(security::CommissioningCrypto&, const security::Key32&,
                             const security::Bytes&, PendingEffectChunk&);
    static bool encode_evidence_chunk(security::CommissioningCrypto&, const security::Key32&,
                                      const DedupeEvidenceChunk&, security::Bytes&);
    static bool decode_evidence_chunk(security::CommissioningCrypto&, const security::Key32&,
                                      const security::Bytes&, DedupeEvidenceChunk&);
    static bool encode_bitmap(security::CommissioningCrypto&, const security::Key32&,
                              const CompletionBitmap&, security::Bytes&);
    static bool decode_bitmap(security::CommissioningCrypto&, const security::Key32&,
                              const security::Bytes&, CompletionBitmap&);
    static bool encode_selector(security::CommissioningCrypto&, const security::Key32&,
                                std::uint64_t generation, std::uint8_t checkpoint_index,
                                security::Bytes&);
    static bool decode_selector(security::CommissioningCrypto&, const security::Key32&,
                                const security::Bytes&, std::uint64_t& generation,
                                std::uint8_t& checkpoint_index);
};

enum class CommitStatus { Committed, NotCommitted, StorageFault, AmbiguousResolvedCommitted, Conflict };
enum class FaultMode { None, FailBeforeWrite, PartialWrite, PersistThenFail, PowerLossAfterPersist };

class BlobStore {
public:
    virtual ~BlobStore() = default;
    virtual bool read(const std::string& key, security::Bytes& value, bool& found) = 0;
    virtual bool write_immutable(const std::string& key, const security::Bytes& value) = 0;
    virtual bool replace(const std::string& key, const security::Bytes& value) = 0;
};

// Deterministic host store. Production target adapters can implement BlobStore.
class MemoryBlobStore final : public BlobStore {
public:
    bool read(const std::string&, security::Bytes&, bool&) override;
    bool write_immutable(const std::string&, const security::Bytes&) override;
    bool replace(const std::string&, const security::Bytes&) override;
    void inject(FaultMode mode) { next_fault_ = mode; }
    void inject_after(std::size_t successful_writes, FaultMode mode) {
        writes_before_fault_ = successful_writes;
        next_fault_ = mode;
    }
    void power_cycle() { next_fault_ = FaultMode::None; writes_before_fault_ = 0; }
    std::size_t write_count() const { return write_count_; }
private:
    bool perform(const std::string&, const security::Bytes&, bool immutable);
    std::map<std::string, security::Bytes> values_;
    FaultMode next_fault_{FaultMode::None};
    std::size_t writes_before_fault_{0};
    std::size_t write_count_{0};
};

struct RecoveryState {
    std::uint32_t storage_epoch{0};
    std::uint64_t last_ordinal{0};
    std::uint64_t checkpoint_generation{0};
    Checkpoint checkpoint;
    std::vector<Transition> tail;
};

class DurableStore {
public:
    DurableStore(BlobStore&, security::CommissioningCrypto&, security::Key32 key,
                 std::uint32_t epoch);
    ~DurableStore();
    DurableStore(const DurableStore&) = delete;
    DurableStore& operator=(const DurableStore&) = delete;
    CommitStatus commit(Transition candidate);
    bool recover(RecoveryState&);
    // Cover the complete tail, or keep the current coverage boundary for a
    // metadata-only checkpoint. Uncovered transitions remain recovery-owned.
    bool checkpoint(const Checkpoint&);
    bool handoff_effects(const std::vector<EffectReference>&,
                         const std::vector<Effect>&, std::uint64_t chunk_id,
                         Checkpoint& next_checkpoint);
    CommitStatus commit_bitmap(CompletionBitmap bitmap);
    bool read_bitmap(const std::array<std::uint8_t, 32>& mapping_digest,
                     CompletionBitmap& out);
    bool read_pending_chunk(std::uint64_t chunk_id, PendingEffectChunk& out);
    bool read_evidence_chunk(std::uint64_t chunk_id, DedupeEvidenceChunk& out);
    bool read_evidence_chunk(const DedupeEvidenceReference&, DedupeEvidenceChunk& out);
private:
    BlobStore& store_;
    security::CommissioningCrypto& crypto_;
    security::Key32 key_;
    std::uint32_t epoch_;
};

}  // namespace gs::hub::durable
