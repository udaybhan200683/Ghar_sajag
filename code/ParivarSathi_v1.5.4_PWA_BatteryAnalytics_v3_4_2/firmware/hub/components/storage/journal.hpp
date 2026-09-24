// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H02 Hub persistence
// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// A commit result has three meanings: Stored adds a new record, Duplicate refers to an already known key,
// and Full refuses new evidence. The name journal describes intended semantics; the current deque is
// volatile. Cloud acknowledgements mark records but do not currently free capacity.

#pragma once

#include "gs/domain.hpp"
#include "firmware/common/security/commissioning_crypto.hpp"

#include <cstddef>
#include <map>
#include <optional>
#include <set>
#include <vector>

namespace gs::hub {

enum class CommitResult { Stored, Duplicate, Full, StorageFault };

// One immutable record per slot. Target implementation commits and verifies
// each NVS blob in the dedicated journal partition before returning success.
class JournalSlotStore {
public:
    virtual ~JournalSlotStore() = default;
    virtual bool read(std::size_t slot, security::Bytes& blob, bool& found) = 0;
    virtual bool write(std::size_t slot, const security::Bytes& blob) = 0;
};

class HubJournal {
public:
    explicit HubJournal(std::size_t capacity = 1024);
    ~HubJournal();
    HubJournal(const HubJournal&) = delete;
    HubJournal& operator=(const HubJournal&) = delete;
    // A failed or ambiguous load locks the journal closed until repaired.
    // Existing prototype callers remain volatile until they opt in.
    bool attach_persistence(security::CommissioningCrypto& crypto,
                            JournalSlotStore& store,
                            const security::Key32& protected_key);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Return Stored, Duplicate or Full for this event identity; this reference container is volatile, not
    // flash.
    CommitResult commit(const DomainEvent& event);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Expose records without a backend application commit ACK; a transport PUBACK is insufficient.
    std::vector<DomainEvent> pending_cloud(std::size_t limit) const;
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Mark backend commitment; current reference does not reclaim journal records or implement flash
    // compaction.
    bool acknowledge_cloud(const EventKey& key);
    bool contains(const EventKey& key) const;
    std::size_t size() const { return records_.size(); }
    bool storage_fault() const { return storage_fault_; }

private:
    std::size_t capacity_;
    std::vector<DomainEvent> records_;
    std::set<std::string> ids_;
    std::set<std::string> cloud_acked_;
    security::CommissioningCrypto* crypto_{nullptr};
    JournalSlotStore* store_{nullptr};
    security::Key32 storage_key_{};
    bool storage_fault_{false};
};

}  // namespace gs::hub
