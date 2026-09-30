#include "storage/hub_durability_owner.hpp"

#include <algorithm>
#include <array>
#include <limits>
#include <set>
#include <string>
#include <utility>

namespace gs::hub::durable {
namespace {
std::string cp_key(std::size_t i) { return "cp" + std::to_string(i); }
std::string selector_key(std::size_t i) { return "sel" + std::to_string(i); }
bool empty_genesis(const Checkpoint& cp) {
    return cp.generation == 1 && cp.covered_ordinal == 0 &&
           cp.pending_effects.empty() && cp.pending_chunks.empty() &&
           cp.dedupe_evidence_chunks.empty() && !cp.report_snapshot &&
           cp.reducer_state.empty();
}
}

HubDurabilityOwner::HubDurabilityOwner(BlobStore& blobs, StoreInventory& inventory,
        security::CommissioningCrypto& crypto, security::Key32 key,
        InstallationFreshness freshness)
    : blobs_(blobs), inventory_(inventory), crypto_(crypto), key_(key),
      freshness_(freshness) {}

HubDurabilityOwner::~HubDurabilityOwner() { crypto_.secure_zero(key_.data(), key_.size()); }

std::optional<std::uint32_t> HubDurabilityOwner::epoch() const {
    return state_ == DurabilityOwnerState::Ready ? std::optional<std::uint32_t>(epoch_) : std::nullopt;
}
std::optional<std::uint32_t> HubDurabilityOwner::candidate_next_epoch() const {
    if (state_ != DurabilityOwnerState::Ready || epoch_ == std::numeric_limits<std::uint32_t>::max())
        return std::nullopt;
    return epoch_ + 1;
}
bool HubDurabilityOwner::commit_candidate_epoch(const Checkpoint& replacement) {
    const auto candidate = candidate_next_epoch();
    if (!candidate || !durable_ || replacement.storage_epoch != *candidate) return false;
    RecoveryState latest;
    if (!durable_->recover(latest)) {
        state_ = DurabilityOwnerState::FailedClosed; epoch_ = 0;
        recovered_.reset(); durable_.reset(); retirement_.reset();
        error_ = DurabilityOwnerError::RecoveryFailure;
        return false;
    }
    recovered_ = latest;
    const auto& old = latest.checkpoint;
    const bool current_history_empty = latest.last_ordinal == 0 && latest.tail.empty() &&
        old.covered_ordinal == 0 && old.reducer_state.empty() && old.pending_effects.empty() &&
        old.pending_chunks.empty() && old.dedupe_evidence_chunks.empty() && !old.report_snapshot;
    const bool replacement_empty = replacement.covered_ordinal == 0 &&
        replacement.reducer_state.empty() && replacement.pending_effects.empty() &&
        replacement.pending_chunks.empty() && replacement.dedupe_evidence_chunks.empty() &&
        !replacement.report_snapshot && replacement.config_version == old.config_version &&
        replacement.config_hash == old.config_hash && !replacement.legacy_dedupe_unverified;
    if (!current_history_empty || !replacement_empty || latest.checkpoint_generation >
            std::numeric_limits<std::uint64_t>::max() - 2) return false;
    const auto first_generation = latest.checkpoint_generation + 1;
    Checkpoint first = replacement;
    first.storage_epoch = *candidate; first.generation = first_generation;
    Checkpoint second = first; second.generation = first_generation + 1;
    security::Bytes first_blob, second_blob;
    if (!Codec::encode_checkpoint(crypto_, key_, first, first_blob) ||
        !Codec::encode_checkpoint(crypto_, key_, second, second_blob)) return false;
    state_ = DurabilityOwnerState::Recovering;
    const auto fail_closed = [&]() {
        durable_.reset(); retirement_.reset(); recovered_.reset(); epoch_ = 0;
        error_ = DurabilityOwnerError::BootstrapWriteFailure;
        state_ = DurabilityOwnerState::FailedClosed;
        return false;
    };
    (void)blobs_.replace(cp_key(0), first_blob);
    security::Bytes verify; bool found = false; Checkpoint decoded;
    if (!blobs_.read(cp_key(0), verify, found) || !found || verify != first_blob ||
        !Codec::decode_checkpoint(crypto_, key_, verify, decoded) ||
        decoded.storage_epoch != *candidate || decoded.generation != first_generation) return fail_closed();
    (void)blobs_.replace(cp_key(1), second_blob);
    if (!blobs_.read(cp_key(1), verify, found) || !found || verify != second_blob ||
        !Codec::decode_checkpoint(crypto_, key_, verify, decoded) ||
        decoded.storage_epoch != *candidate || decoded.generation != first_generation + 1) return fail_closed();
    for (const auto& item : {std::pair<std::uint64_t, std::uint8_t>{first_generation,0},
                             std::pair<std::uint64_t, std::uint8_t>{first_generation+1,1}}) {
        security::Bytes selector;
        if (!Codec::encode_selector(crypto_, key_, item.first, item.second, selector)) return fail_closed();
        (void)blobs_.replace(selector_key(item.first % 2), selector);
        if (!blobs_.read(selector_key(item.first % 2), verify, found) || !found || verify != selector) return fail_closed();
        std::uint64_t generation = 0; std::uint8_t bank = 0;
        if (!Codec::decode_selector(crypto_, key_, verify, generation, bank) ||
            generation != item.first || bank != item.second) return fail_closed();
    }
    auto next = std::make_unique<DurableStore>(blobs_, crypto_, key_, *candidate);
    RecoveryState recovered;
    if (!next->recover(recovered) || recovered.storage_epoch != *candidate ||
        recovered.checkpoint_generation != first_generation + 1) return fail_closed();
    durable_ = std::move(next); epoch_ = *candidate; recovered_ = std::move(recovered);
    retirement_ = std::make_unique<RetirementSnapshotRepository>(blobs_, crypto_, key_, epoch_);
    error_ = DurabilityOwnerError::None; state_ = DurabilityOwnerState::Ready;
    freshness_ = InstallationFreshness::ExistingInstallation;
    return true;
}
const RecoveryState* HubDurabilityOwner::recovery_state() const {
    return state_ == DurabilityOwnerState::Ready && recovered_ ? &*recovered_ : nullptr;
}
DurableStore* HubDurabilityOwner::durable_store() {
    return state_ == DurabilityOwnerState::Ready ? durable_.get() : nullptr;
}
RetirementSnapshotRepository* HubDurabilityOwner::retirement_repository() {
    return state_ == DurabilityOwnerState::Ready ? retirement_.get() : nullptr;
}

bool HubDurabilityOwner::inspect_checkpoint_set(std::uint32_t& found_epoch,
        bool& can_resume_genesis, RecoveryState& recovered) {
    found_epoch = 0; can_resume_genesis = false;
    std::array<Checkpoint, 2> cps{};
    std::array<bool, 2> present{};
    std::array<bool, 2> valid{};
    for (std::size_t i = 0; i < 2; ++i) {
        security::Bytes b; bool f = false;
        if (!blobs_.read(cp_key(i), b, f)) return false;
        present[i] = f;
        if (f) valid[i] = Codec::decode_checkpoint(crypto_, key_, b, cps[i]) && cps[i].storage_epoch != 0;
    }
    if (!valid[0] && !valid[1]) return !(present[0] || present[1]);
    if (valid[0] && valid[1] && cps[0].storage_epoch != cps[1].storage_epoch) return false;
    found_epoch = valid[0] ? cps[0].storage_epoch : cps[1].storage_epoch;
    // Selectors authenticate independently. A valid older selector may remain
    // usable when the newer checkpoint bank is damaged; never invent an epoch
    // from a selector that points at an invalid bank.
    bool saw_selector = false, saw_valid_selector = false;
    for (std::size_t i = 0; i < 2; ++i) {
        security::Bytes b; bool f = false;
        if (!blobs_.read(selector_key(i), b, f)) return false;
        if (!f) continue;
        saw_selector = true;
        std::uint64_t generation = 0; std::uint8_t bank = 0;
        if (!Codec::decode_selector(crypto_, key_, b, generation, bank) || bank > 1) return false;
        if (valid[bank] && cps[bank].storage_epoch == found_epoch &&
            cps[bank].generation == generation) saw_valid_selector = true;
    }
    if (saw_selector && !saw_valid_selector) return false;
    durable_ = std::make_unique<DurableStore>(blobs_, crypto_, key_, found_epoch);
    if (!durable_->recover(recovered) || recovered.storage_epoch != found_epoch ||
        recovered.checkpoint_generation == 0) { durable_.reset(); return false; }
    can_resume_genesis = empty_genesis(recovered.checkpoint) && recovered.last_ordinal == 0;
    if (!saw_selector && !can_resume_genesis) { durable_.reset(); return false; }
    return true;
}

bool HubDurabilityOwner::inventory_chunks_owned(const InventorySnapshot& snapshot,
                                                 const RecoveryState& recovered) const {
    std::set<std::uint64_t> effects, evidence;
    for (const auto& ref : recovered.checkpoint.pending_chunks) effects.insert(ref.chunk_id);
    for (const auto& ref : recovered.checkpoint.dedupe_evidence_chunks) evidence.insert(ref.chunk_id);
    // A chunk may also be referenced by the other valid bank during checkpoint rotation.
    for (std::size_t i = 0; i < snapshot.count; ++i) {
        const auto& r = snapshot.records[i];
        if (r.kind == InventoryRecord::Bitmap) {
            security::Bytes bytes; bool found = false; CompletionBitmap bitmap;
            if (!blobs_.read("bm" + std::to_string(r.id), bytes, found) || !found ||
                !Codec::decode_bitmap(crypto_, key_, bytes, bitmap) ||
                bitmap.storage_epoch != recovered.storage_epoch ||
                bitmap.checkpoint_generation > recovered.checkpoint_generation) return false;
            continue;
        }
        if (r.kind != InventoryRecord::EffectChunk && r.kind != InventoryRecord::EvidenceChunk) continue;
        security::Bytes b; bool found = false;
        const auto logical = std::string(r.kind == InventoryRecord::EffectChunk ? "ef" : "ev") + std::to_string(r.id);
        if (!blobs_.read(logical, b, found) || !found) return false;
        bool owned = r.kind == InventoryRecord::EffectChunk ? effects.count(r.id) != 0
                                                            : evidence.count(r.id) != 0;
        if (!owned) {
            // Also accept references from either authenticated checkpoint bank.
            for (std::size_t bank = 0; bank < 2 && !owned; ++bank) {
                security::Bytes cb; bool cf = false; Checkpoint cp;
                if (!blobs_.read(cp_key(bank), cb, cf)) return false;
                if (!cf || !Codec::decode_checkpoint(crypto_, key_, cb, cp) || cp.storage_epoch != epoch_) continue;
                if (r.kind == InventoryRecord::EffectChunk)
                    owned = std::any_of(cp.pending_chunks.begin(), cp.pending_chunks.end(), [&](const auto& x){return x.chunk_id == r.id;});
                else
                    owned = std::any_of(cp.dedupe_evidence_chunks.begin(), cp.dedupe_evidence_chunks.end(), [&](const auto& x){return x.chunk_id == r.id;});
            }
        }
        if (!owned) return false;
    }
    return true;
}

bool HubDurabilityOwner::initialize_epoch_one() {
    durable_ = std::make_unique<DurableStore>(blobs_, crypto_, key_, 1);
    Checkpoint cp; cp.storage_epoch = 1; cp.generation = 1;
    if (!durable_->checkpoint(cp)) { durable_.reset(); return false; }
    cp.generation = 2;
    if (!durable_->checkpoint(cp)) { durable_.reset(); return false; }
    RecoveryState recovered;
    if (!durable_->recover(recovered) || recovered.storage_epoch != 1 ||
        recovered.checkpoint_generation != 2 || recovered.last_ordinal != 0) {
        durable_.reset(); return false;
    }
    epoch_ = 1; recovered_ = std::move(recovered);
    freshness_ = InstallationFreshness::ExistingInstallation;
    return true;
}

DurabilityOwnerState HubDurabilityOwner::recover() {
    state_ = DurabilityOwnerState::Recovering; error_ = DurabilityOwnerError::None;
    epoch_ = 0; recovered_.reset(); durable_.reset(); retirement_.reset();
    const auto inventory = inventory_.scan();
    if (inventory.status == InventoryStatus::ScanFailure || inventory.status == InventoryStatus::LimitExceeded) {
        error_ = DurabilityOwnerError::InventoryFailure; state_ = DurabilityOwnerState::FailedClosed; return state_;
    }
    if (inventory.status == InventoryStatus::UnknownOrphanRecord || inventory.status == InventoryStatus::MalformedRecord) {
        error_ = DurabilityOwnerError::UnknownOrMalformedStorage; state_ = DurabilityOwnerState::FailedClosed; return state_;
    }
    if (freshness_ == InstallationFreshness::Ambiguous) {
        error_ = DurabilityOwnerError::SecurityStateAmbiguous; state_ = DurabilityOwnerState::FailedClosed; return state_;
    }
    const bool has_legacy = inventory.status == InventoryStatus::KnownLegacyRecords ||
                            inventory.status == InventoryStatus::KnownMixedRecords;
    const bool has_migration = std::any_of(inventory.records.begin(),
        inventory.records.begin() + inventory.count, [](const auto& r) {
            return r.kind == InventoryRecord::MigrationMetadata;
        });
    if (has_legacy || has_migration) {
        error_ = DurabilityOwnerError::MigrationRequired; state_ = DurabilityOwnerState::MigrationRequired; return state_;
    }
    if (inventory.status == InventoryStatus::Empty) {
        if (freshness_ != InstallationFreshness::FreshInstallation) {
            error_ = DurabilityOwnerError::FreshnessMismatch; state_ = DurabilityOwnerState::FailedClosed; return state_;
        }
        if (!initialize_epoch_one()) {
            error_ = DurabilityOwnerError::BootstrapWriteFailure; state_ = DurabilityOwnerState::FailedClosed; return state_;
        }
    } else {
        std::uint32_t discovered_epoch = 0; bool genesis = false; RecoveryState recovered;
        if (!inspect_checkpoint_set(discovered_epoch, genesis, recovered) || discovered_epoch == 0) {
            error_ = DurabilityOwnerError::InvalidCheckpoint; state_ = DurabilityOwnerState::FailedClosed; return state_;
        }
        epoch_ = discovered_epoch;
        if (freshness_ == InstallationFreshness::FreshInstallation) {
            error_ = DurabilityOwnerError::FreshnessMismatch; state_ = DurabilityOwnerState::FailedClosed; return state_;
        }
        if (inventory.status == InventoryStatus::KnownCurrentRecords && genesis &&
            inventory.count <= 4) {
            // Narrow restart recovery for an interrupted epoch-1 genesis. The only
            // permitted records are the two checkpoint and two selector banks.
            bool allowed = true;
            for (std::size_t i = 0; i < inventory.count; ++i)
                allowed = allowed && (inventory.records[i].kind == InventoryRecord::Checkpoint ||
                                      inventory.records[i].kind == InventoryRecord::Selector);
            if (allowed && recovered.checkpoint_generation < 2) {
                Checkpoint cp; cp.storage_epoch = discovered_epoch; cp.generation = 2;
                if (!durable_->checkpoint(cp) || !durable_->recover(recovered) || recovered.checkpoint_generation != 2) {
                    error_ = DurabilityOwnerError::BootstrapWriteFailure; state_ = DurabilityOwnerState::FailedClosed; return state_;
                }
            }
        }
        if (!inventory_chunks_owned(inventory, recovered)) {
            error_ = DurabilityOwnerError::OrphanChunk; state_ = DurabilityOwnerState::FailedClosed; return state_;
        }
        epoch_ = discovered_epoch; recovered_ = std::move(recovered);
    }
    if (epoch_ == 0 || !recovered_ || !durable_) {
        error_ = DurabilityOwnerError::RecoveryFailure; state_ = DurabilityOwnerState::FailedClosed; return state_;
    }
    retirement_ = std::make_unique<RetirementSnapshotRepository>(blobs_, crypto_, key_, epoch_);
    state_ = DurabilityOwnerState::Ready; return state_;
}

}  // namespace gs::hub::durable
