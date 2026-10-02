#include "storage/durable_journal_slot_store.hpp"
#include "firmware/common/transport/node_retirement_protocol.hpp"

#include <algorithm>

namespace gs::hub::durable {
namespace {
constexpr std::uint64_t kJournalArchivePrefix = 0x8000000000000000ULL;

std::uint32_t slot_of(const Effect& effect) {
    return (static_cast<std::uint32_t>(effect.id[0]) << 24) |
           (static_cast<std::uint32_t>(effect.id[1]) << 16) |
           (static_cast<std::uint32_t>(effect.id[2]) << 8) | effect.id[3];
}

void encode_slot(std::uint32_t slot, std::array<std::uint8_t, 32>& id) {
    id[0] = static_cast<std::uint8_t>(slot >> 24);
    id[1] = static_cast<std::uint8_t>(slot >> 16);
    id[2] = static_cast<std::uint8_t>(slot >> 8);
    id[3] = static_cast<std::uint8_t>(slot);
}

bool same_event(const gs::DomainEvent& left, const gs::DomainEvent& right) {
    security::Bytes a, b;
    return HubJournal::encode_event_payload(left, a) &&
           HubJournal::encode_event_payload(right, b) && a == b;
}

std::uint32_t read_u32(const security::Bytes& bytes) {
    if (bytes.size() != 4) return 0;
    return (static_cast<std::uint32_t>(bytes[0]) << 24) |
           (static_cast<std::uint32_t>(bytes[1]) << 16) |
           (static_cast<std::uint32_t>(bytes[2]) << 8) | bytes[3];
}

security::Bytes write_u32(std::uint32_t value) {
    return {static_cast<std::uint8_t>(value >> 24),
            static_cast<std::uint8_t>(value >> 16),
            static_cast<std::uint8_t>(value >> 8),
            static_cast<std::uint8_t>(value)};
}

}  // namespace

DurableJournalSlotStore::DurableJournalSlotStore(
    HubDurabilityOwner& owner, security::CommissioningCrypto& crypto,
    const security::Key32& journal_key)
    : owner_(owner), crypto_(crypto), journal_key_(journal_key) {}

DurableJournalSlotStore::~DurableJournalSlotStore() {
    crypto_.secure_zero(journal_key_.data(), journal_key_.size());
}

bool DurableJournalSlotStore::read_archive(std::uint64_t id, PendingEffectChunk& chunk) {
    auto* durable = owner_.migration_store();
    return durable != nullptr && durable->read_pending_chunk(id, chunk);
}

bool DurableJournalSlotStore::write_archive(std::uint64_t id,
                                            const PendingEffectChunk& chunk) {
    const auto key = "ef" + std::to_string(id);
    security::Bytes existing;
    bool found = false;
    if (!owner_.blobs_.read(key, existing, found)) return false;
    if (found) {
        PendingEffectChunk decoded;
        if (!Codec::decode_chunk(crypto_, owner_.key_, existing, decoded) ||
            decoded.chunk_id != id || decoded.storage_epoch != chunk.storage_epoch ||
            decoded.effects.size() != chunk.effects.size()) return false;
        for (std::size_t i = 0; i < chunk.effects.size(); ++i)
            if (decoded.effects[i].id != chunk.effects[i].id ||
                decoded.effects[i].kind != chunk.effects[i].kind ||
                decoded.effects[i].payload != chunk.effects[i].payload) return false;
        return true;
    }
    security::Bytes encoded;
    if (!Codec::encode_chunk(crypto_, owner_.key_, chunk, encoded)) return false;
    const bool wrote = owner_.blobs_.write_immutable(key, encoded);
    security::Bytes verify;
    PendingEffectChunk decoded;
    if (!owner_.blobs_.read(key, verify, found) || !found ||
        !Codec::decode_chunk(crypto_, owner_.key_, verify, decoded) ||
        decoded.chunk_id != id || decoded.storage_epoch != chunk.storage_epoch ||
        decoded.effects.size() != chunk.effects.size()) return false;
    for (std::size_t i = 0; i < chunk.effects.size(); ++i)
        if (decoded.effects[i].id != chunk.effects[i].id ||
            decoded.effects[i].kind != chunk.effects[i].kind ||
            decoded.effects[i].payload != chunk.effects[i].payload) return false;
    (void)wrote;
    return true;
}

bool DurableJournalSlotStore::rows(std::map<std::size_t, Row>& out,
                                   RecoveryState& recovery) {
    out.clear();
    auto* durable = owner_.migration_store();
    if (durable == nullptr || !durable->recover(recovery)) return false;
    for (const auto& ref : recovery.checkpoint.pending_chunks) {
        PendingEffectChunk chunk;
        if (!read_archive(ref.chunk_id, chunk)) return false;
        for (const auto& effect : chunk.effects) {
            Row row;
            row.completed = effect.kind == 1;
            if (effect.kind > 1 ||
                !HubJournal::decode_event_payload(effect.payload, row.event)) return false;
            if (!out.emplace(slot_of(effect), std::move(row)).second) return false;
        }
    }
    for (const auto& transition : recovery.tail) {
        if (transition.type != TransitionType::Event) continue;
        if (transition.decision.size() != 4) return false;
        const auto slot = read_u32(transition.decision);
        Row row;
        if (!HubJournal::decode_event_payload(transition.causal_input, row.event)) return false;
        const auto existing = out.find(slot);
        if (existing != out.end()) {
            if (!same_event(existing->second.event, row.event)) return false;
        } else {
            out.emplace(slot, std::move(row));
        }
    }
    for (const auto& [slot, completed] : import_completion_) {
        const auto found = out.find(slot);
        if (found != out.end()) found->second.completed = completed;
    }
    return true;
}

bool DurableJournalSlotStore::read(std::size_t slot, security::Bytes& blob, bool& found) {
    blob.clear(); found = false;
    std::map<std::size_t, Row> stored;
    RecoveryState recovery;
    if (slot > 127 || !rows(stored, recovery)) return false;
    const auto entry = stored.find(slot);
    if (entry == stored.end()) return true;
    if (!HubJournal::encode_slot_blob(crypto_, journal_key_, slot,
                                      entry->second.event, blob)) return false;
    found = true;
    return true;
}

bool DurableJournalSlotStore::append_event(std::size_t slot,
                                           const security::Bytes& blob,
                                           const gs::DomainEvent& event) {
    auto* durable = owner_.migration_store();
    if (durable == nullptr || slot > 127) return false;
    RecoveryState before;
    if (!durable->recover(before)) return false;
    if ((before.tail.size() >= 4 ||
         (before.tail.empty() && before.last_ordinal >= 4)) && !flush()) return false;
    security::Bytes payload;
    if (!HubJournal::encode_event_payload(event, payload)) return false;
    Transition transition;
    transition.type = TransitionType::Event;
    transition.event = {event.key.physical_device_id, event.key.source_id,
                        event.key.session_id, event.key.sequence};
    transport::RetirementEnrollmentBinding binding;
    if (!transport::derive_retirement_enrollment_binding(
            crypto_, journal_key_, event.key.source_id, binding)) return false;
    transition.enrollment_slot = binding.slot;
    transition.enrollment_generation = binding.generation;
    if (!crypto_.hmac_sha256(journal_key_, payload, transition.event_digest)) return false;
    transition.causal_input = std::move(payload);
    transition.decision = write_u32(static_cast<std::uint32_t>(slot));
    const auto status = durable->commit(std::move(transition));
    if (status != CommitStatus::Committed &&
        status != CommitStatus::AmbiguousResolvedCommitted) return false;
    (void)blob;
    return true;
}

bool DurableJournalSlotStore::write(std::size_t slot, const security::Bytes& blob) {
    if (faulted_ || slot > 127) return false;
    gs::DomainEvent event;
    if (!HubJournal::decode_slot_blob(crypto_, journal_key_, slot, blob, event)) {
        faulted_ = true; return false;
    }
    std::map<std::size_t, Row> stored;
    RecoveryState recovery;
    if (!rows(stored, recovery)) { faulted_ = true; return false; }
    const auto prior = stored.find(slot);
    if (prior != stored.end()) return same_event(prior->second.event, event);
    if (!append_event(slot, blob, event)) {
        faulted_ = true; return false;
    }
    return true;
}

bool DurableJournalSlotStore::read_completion(std::size_t slot,
                                              security::Bytes& blob, bool& found) {
    blob.clear(); found = false;
    std::map<std::size_t, Row> stored;
    RecoveryState recovery;
    if (slot > 127 || !rows(stored, recovery)) return false;
    const auto entry = stored.find(slot);
    if (entry == stored.end() || !entry->second.completed) return true;
    return HubJournal::encode_completion_receipt(crypto_, journal_key_, slot,
                                                 entry->second.event.key, blob) &&
           (found = true);
}

bool DurableJournalSlotStore::import_completion(std::size_t slot, bool completed) {
    if (faulted_ || slot > 127) return false;
    import_completion_[slot] = completed;
    return true;
}

bool DurableJournalSlotStore::verify_import(std::size_t slot,
                                            const gs::DomainEvent& event,
                                            bool completed) {
    std::map<std::size_t, Row> stored;
    RecoveryState recovery;
    if (slot > 127 || !rows(stored, recovery)) return false;
    const auto entry = stored.find(slot);
    return entry != stored.end() && same_event(entry->second.event, event) &&
           entry->second.completed == completed;
}

bool DurableJournalSlotStore::replace_completion(std::size_t slot, bool completed) {
    std::map<std::size_t, Row> stored;
    RecoveryState recovery;
    if (!rows(stored, recovery)) return false;
    const auto row = stored.find(slot);
    if (row == stored.end()) return false;
    bool located = false;
    for (const auto& ref : recovery.checkpoint.pending_chunks) {
        PendingEffectChunk chunk;
        if (!read_archive(ref.chunk_id, chunk)) return false;
        for (auto& effect : chunk.effects) {
            if (slot_of(effect) != slot) continue;
            effect.kind = completed ? 1U : 0U;
            security::Bytes encoded;
            if (!Codec::encode_chunk(crypto_, owner_.key_, chunk, encoded)) return false;
            const auto key = "ef" + std::to_string(ref.chunk_id);
            if (!owner_.blobs_.replace(key, encoded)) {
                security::Bytes verify; bool found = false;
                PendingEffectChunk decoded;
                if (!owner_.blobs_.read(key, verify, found) || !found || verify != encoded ||
                    !Codec::decode_chunk(crypto_, owner_.key_, verify, decoded)) return false;
            }
            located = true;
            break;
        }
        if (located) break;
    }
    return located;
}

bool DurableJournalSlotStore::write_completion(std::size_t slot,
                                               const security::Bytes& receipt) {
    if (faulted_ || slot > 127) return false;
    std::map<std::size_t, Row> stored;
    RecoveryState recovery;
    if (!rows(stored, recovery)) { faulted_ = true; return false; }
    const auto row = stored.find(slot);
    if (row == stored.end() ||
        !HubJournal::verify_completion_receipt(crypto_, journal_key_, slot,
                                               row->second.event.key, receipt)) return false;
    if (import_completion_.count(slot) != 0) {
        import_completion_[slot] = true;
        return true;
    }
    if (!recovery.tail.empty() && !flush()) { faulted_ = true; return false; }
    if (!replace_completion(slot, true)) { faulted_ = true; return false; }
    return true;
}

bool DurableJournalSlotStore::flush() {
    auto* durable = owner_.migration_store();
    if (durable == nullptr) return false;
    RecoveryState recovery;
    if (!durable->recover(recovery)) return false;
    if (recovery.tail.empty()) {
        // A prior boot may have stopped after the first checkpoint rotation.
        // Advance the unchanged state into both banks before any old transition
        // slot can be reused.
        Checkpoint first = recovery.checkpoint;
        first.generation = recovery.checkpoint_generation + 1U;
        first.covered_ordinal = recovery.last_ordinal;
        if (!durable->checkpoint(first) || !durable->recover(recovery)) return false;
        Checkpoint second = recovery.checkpoint;
        second.generation = recovery.checkpoint_generation + 1U;
        second.covered_ordinal = recovery.last_ordinal;
        return durable->checkpoint(second);
    }
    if (recovery.tail.size() > 4) return false;
    std::map<std::size_t, Row> stored;
    if (!rows(stored, recovery)) return false;
    PendingEffectChunk chunk;
    chunk.storage_epoch = recovery.storage_epoch;
    if (recovery.checkpoint_generation >= kJournalArchivePrefix - 1U) return false;
    chunk.chunk_id = kJournalArchivePrefix | (recovery.checkpoint_generation + 1U);
    std::map<std::size_t, Row> new_rows;
    for (const auto& transition : recovery.tail) {
        if (transition.type != TransitionType::Event) continue;
        const auto slot = read_u32(transition.decision);
        if (transition.decision.size() != 4 || stored.count(slot) == 0) return false;
        Row row = stored.at(slot);
        const auto imported = import_completion_.find(slot);
        if (imported != import_completion_.end()) row.completed = imported->second;
        security::Bytes payload;
        if (!HubJournal::encode_event_payload(row.event, payload) ||
            chunk.effects.size() >= kMaxEffectsPerChunk) return false;
        Effect effect;
        encode_slot(static_cast<std::uint32_t>(slot), effect.id);
        security::Key32 digest{};
        if (!crypto_.hmac_sha256(journal_key_, payload, digest)) return false;
        std::copy_n(digest.begin(), effect.id.size() - 4U, effect.id.begin() + 4);
        crypto_.secure_zero(digest.data(), digest.size());
        effect.kind = row.completed ? 1U : 0U;
        effect.payload = std::move(payload);
        chunk.effects.push_back(std::move(effect));
        new_rows.emplace(slot, std::move(row));
    }
    Checkpoint next = recovery.checkpoint;
    next.storage_epoch = recovery.storage_epoch;
    next.generation = recovery.checkpoint_generation + 1U;
    next.covered_ordinal = recovery.last_ordinal;
    if (!chunk.effects.empty()) {
        if (next.pending_chunks.size() >= kMaxCheckpointChunkRefs) return false;
        if (!write_archive(chunk.chunk_id, chunk)) return false;
        next.pending_chunks.push_back({chunk.chunk_id, {}});
    }
    if (!durable->checkpoint(next) || !durable->recover(recovery)) return false;
    Checkpoint shadow = recovery.checkpoint;
    shadow.generation = recovery.checkpoint_generation + 1U;
    shadow.covered_ordinal = recovery.last_ordinal;
    if (!durable->checkpoint(shadow)) return false;
    for (const auto& row : new_rows) import_completion_.erase(row.first);
    return true;
}

bool migrate_legacy_journal(HubJournal& legacy, JournalSlotStore& legacy_store,
                            DurableJournalSlotStore& durable_store) {
    if (!legacy.persistent() || legacy.storage_fault() || !durable_store.healthy()) return false;
    const auto& records = legacy.records();
    bool any_source = false;
    for (std::size_t slot = 0; slot < records.size(); ++slot) {
        security::Bytes blob; bool found = false;
        if (!legacy_store.read(slot, blob, found)) return false;
        any_source = any_source || found;
    }
    if (!any_source) {
        // Idempotent success after a prior run already committed and removed
        // all source slots (including when the caller retained its old object).
        for (std::size_t slot = 0; slot < records.size(); ++slot) {
            if (!durable_store.verify_import(slot, records[slot], false) &&
                !durable_store.verify_import(slot, records[slot], true)) return false;
            if (legacy.cloud_completed(records[slot].key) &&
                !durable_store.verify_import(slot, records[slot], true)) return false;
        }
        return true;
    }
    // Commit, recover/verify, then clean one bounded batch at a time. Removing
    // each committed high-slot batch before writing the next keeps the legacy
    // source plus destination footprint within the fixed NVS partition budget.
    std::size_t end = records.size();
    while (end != 0) {
        const std::size_t begin = ((end - 1U) / kMaxEffectsPerChunk) * kMaxEffectsPerChunk;
        for (std::size_t slot = begin; slot < end; ++slot) {
            security::Bytes blob; bool found = false;
            if (!legacy_store.read(slot, blob, found)) return false;
            if (found) {
                if (!durable_store.write(slot, blob)) return false;
                if (legacy.cloud_completed(records[slot].key) &&
                    !durable_store.import_completion(slot, true)) return false;
            } else if (!durable_store.verify_import(slot, records[slot], false) &&
                       !durable_store.verify_import(slot, records[slot], true)) {
                // A missing source is only acceptable after a previous batch
                // already committed that exact event to the durable owner.
                return false;
            }
        }
        if (!durable_store.flush()) return false;
        for (std::size_t slot = begin; slot < end; ++slot) {
            if (legacy.cloud_completed(records[slot].key)) {
                if (!durable_store.verify_import(slot, records[slot], true)) return false;
            } else if (!durable_store.verify_import(slot, records[slot], false) &&
                       !durable_store.verify_import(slot, records[slot], true)) return false;
        }
        for (std::size_t slot = end; slot > begin; --slot) {
            const auto index = slot - 1U;
            if (!legacy_store.erase_completion(index) || !legacy_store.erase(index)) return false;
        }
        end = begin;
    }
    return true;
}

}  // namespace gs::hub::durable
