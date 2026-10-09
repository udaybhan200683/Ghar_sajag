#pragma once

#include "storage/durable_event_outbox.hpp"
#include "storage/journal.hpp"

namespace gs::hub::storage {

// Bridges the authenticated HubJournal event boundary to the encrypted,
// publication-verified segmented outbox. It deliberately does not implement
// backend completion or body retirement; until that ledger is integrated all
// records remain pending and protected from reclamation.
class OutboxJournalBackend final : public JournalEventBackend {
public:
    explicit OutboxJournalBackend(DurableEventOutbox& outbox) : outbox_(outbox) {}

    bool healthy() const override { return outbox_.healthy(); }
    std::size_t size() const override;
    CommitResult commit(const DomainEvent& event) override;
    bool contains(const EventKey& key) override;
    bool for_each(EventVisitor visitor, void* context) override;

private:
    DurableEventOutbox& outbox_;
};

}  // namespace gs::hub::storage
