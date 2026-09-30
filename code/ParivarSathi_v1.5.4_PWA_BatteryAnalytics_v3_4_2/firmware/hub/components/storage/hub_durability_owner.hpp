#pragma once

#include "storage/durable_transition.hpp"
#include "storage/node_retirement_snapshot.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>

namespace gs::hub::durable {

class DurableJournalSlotStore;

constexpr std::size_t kMaxInventoryRecords = 384;

enum class InstallationFreshness { FreshInstallation, ExistingInstallation, Ambiguous };
enum class InventoryStatus {
    Empty,
    KnownCurrentRecords,
    KnownLegacyRecords,
    KnownMixedRecords,
    UnknownOrphanRecord,
    MalformedRecord,
    ScanFailure,
    LimitExceeded
};

struct InventoryRecord {
    enum Kind : std::uint8_t {
        Checkpoint = 1, Selector = 2, Transition = 3, EffectChunk = 4,
        EvidenceChunk = 5, Bitmap = 6, RetirementBank = 7,
        LegacyEvent = 8, LegacyCompletion = 9, MigrationMetadata = 10
    } kind{Checkpoint};
    std::uint64_t id{0};
};

struct InventorySnapshot {
    InventoryStatus status{InventoryStatus::ScanFailure};
    std::array<InventoryRecord, kMaxInventoryRecords> records{};
    std::uint16_t count{0};
};

class StoreInventory {
public:
    virtual ~StoreInventory() = default;
    virtual InventorySnapshot scan() = 0;
};

enum class DurabilityOwnerState {
    Uninitialized,
    Recovering,
    MigrationRequired,
    Ready,
    FailedClosed
};

enum class DurabilityOwnerError {
    None,
    SecurityStateAmbiguous,
    FreshnessMismatch,
    UnknownOrMalformedStorage,
    InventoryFailure,
    InvalidCheckpoint,
    InvalidSelector,
    RecoveryFailure,
    OrphanChunk,
    EpochOverflow,
    BootstrapWriteFailure,
    MigrationRequired
};

// Portable owner of the existing durable codecs/repositories. It deliberately
// has no ESP-IDF dependency; target persistence is supplied through BlobStore
// and StoreInventory.
class HubDurabilityOwner {
public:
    HubDurabilityOwner(BlobStore&, StoreInventory&,
                       security::CommissioningCrypto&, security::Key32 key,
                       InstallationFreshness);
    ~HubDurabilityOwner();
    HubDurabilityOwner(const HubDurabilityOwner&) = delete;
    HubDurabilityOwner& operator=(const HubDurabilityOwner&) = delete;

    DurabilityOwnerState recover();
    DurabilityOwnerState state() const { return state_; }
    DurabilityOwnerError error() const { return error_; }
    std::optional<std::uint32_t> epoch() const;
    std::optional<std::uint32_t> candidate_next_epoch() const;
    // Commit an empty-history epoch change. History transfer/reclamation is
    // intentionally a separate operation and cannot be requested here.
    bool commit_candidate_epoch(const Checkpoint& replacement);
    const RecoveryState* recovery_state() const;
    DurableStore* durable_store();
    RetirementSnapshotRepository* retirement_repository();
    // Migration-only access. This never makes an epoch authoritative for
    // admission while legacy records remain.
    DurableStore* migration_store();
    std::optional<std::uint32_t> migration_epoch() const;

private:
    friend class DurableJournalSlotStore;
    bool initialize_epoch_one();
    bool inspect_checkpoint_set(std::uint32_t& epoch, bool& can_resume_genesis,
                               RecoveryState& recovered);
    bool inventory_chunks_owned(const InventorySnapshot&,
                                const RecoveryState&) const;

    BlobStore& blobs_;
    StoreInventory& inventory_;
    security::CommissioningCrypto& crypto_;
    security::Key32 key_{};
    InstallationFreshness freshness_;
    DurabilityOwnerState state_{DurabilityOwnerState::Uninitialized};
    DurabilityOwnerError error_{DurabilityOwnerError::None};
    std::uint32_t epoch_{0};
    std::optional<RecoveryState> recovered_;
    std::unique_ptr<DurableStore> durable_;
    std::unique_ptr<RetirementSnapshotRepository> retirement_;
};

}  // namespace gs::hub::durable
