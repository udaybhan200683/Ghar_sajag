#pragma once

#include "storage/durable_event_outbox.hpp"
#include "storage/journal.hpp"

namespace gs::hub::storage {

// Bridges the authenticated HubJournal boundary to the encrypted segmented
// outbox, including independently published backend completion receipts.
class OutboxJournalBackend final : public JournalEventBackend {
public:
    explicit OutboxJournalBackend(DurableEventOutbox& outbox) : outbox_(outbox) {}

    bool healthy() const override { return outbox_.healthy(); }
    std::size_t size() const override;
    CommitResult commit(const DomainEvent& event) override;
    bool contains(const EventKey& key) override;
    bool for_each(EventVisitor visitor, void* context) override;
    bool for_each_with_ordinal(OrdinalEventVisitor visitor, void* context) override;
    bool cloud_completed(const EventKey& key) const override;
    std::size_t cloud_completed_count() const override;
    std::uint64_t backend_completion_retired_through() const override;
    std::uint64_t absent_body_retirement_boundary() const override;
    bool acknowledge_cloud(const EventKey& key) override;

private:
    DurableEventOutbox& outbox_;
};

}  // namespace gs::hub::storage
