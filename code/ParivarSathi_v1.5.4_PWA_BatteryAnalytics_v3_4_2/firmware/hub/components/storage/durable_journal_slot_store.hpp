#pragma once

#include "storage/hub_durability_owner.hpp"
#include "storage/journal.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>

namespace gs::hub::durable {

// Adapts HubJournal's stable event/receipt contract onto DurableStore. Events
// stay in the authenticated transition tail until a bounded batch is archived
// in an effect chunk and checkpointed.
class DurableJournalSlotStore final : public JournalSlotStore {
public:
    DurableJournalSlotStore(HubDurabilityOwner&, security::CommissioningCrypto&,
                            const security::Key32& journal_key);
    ~DurableJournalSlotStore() override;
    bool read(std::size_t slot, security::Bytes& blob, bool& found) override;
    bool write(std::size_t slot, const security::Bytes& blob) override;
    bool read_completion(std::size_t slot, security::Bytes& blob, bool& found) override;
    bool write_completion(std::size_t slot, const security::Bytes& blob) override;
    bool import_completion(std::size_t slot, bool completed);
    bool verify_import(std::size_t slot, const gs::DomainEvent& event, bool completed);
    bool flush();
    bool healthy() const { return !faulted_; }

private:
    struct Row { gs::DomainEvent event; bool completed{false}; };
    bool rows(std::map<std::size_t, Row>& out, RecoveryState& recovery);
    bool write_archive(std::uint64_t chunk_id, const PendingEffectChunk& chunk);
    bool read_archive(std::uint64_t chunk_id, PendingEffectChunk& chunk);
    static std::string completion_key(std::size_t slot);
    bool publish_completion(std::size_t slot, const gs::EventKey&,
                            const security::Bytes& receipt);
    bool replace_completion(std::size_t slot, bool completed);
    bool append_event(std::size_t slot, const security::Bytes& blob,
                      const gs::DomainEvent& event);

    HubDurabilityOwner& owner_;
    security::CommissioningCrypto& crypto_;
    security::Key32 journal_key_{};
    std::map<std::size_t, bool> import_completion_;
    bool faulted_{false};
};

// Copies and verifies every legacy slot before deleting any source slot. The
// caller re-runs owner recovery after this returns true to open admission.
bool migrate_legacy_journal(HubJournal& legacy, JournalSlotStore& legacy_store,
                            DurableJournalSlotStore& durable_store);

}  // namespace gs::hub::durable
