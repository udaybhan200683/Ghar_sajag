// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H02 Hub persistence
// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Persistent target slots retain accepted events for reducer replay and deduplication.
// Backend completion receipts are separate write-once slots; neither frees capacity.

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
class CloudSync;

// One immutable record per slot. Target implementation commits and verifies
// each NVS blob in the dedicated journal partition before returning success.
class JournalSlotStore {
public:
    virtual ~JournalSlotStore() = default;
    virtual bool read(std::size_t slot, security::Bytes& blob, bool& found) = 0;
    virtual bool write(std::size_t slot, const security::Bytes& blob) = 0;
    // A separate, write-once receipt for the same numbered event slot.
    virtual bool read_completion(std::size_t, security::Bytes& blob, bool& found) {
        blob.clear(); found = false; return true;
    }
    virtual bool write_completion(std::size_t, const security::Bytes&) { return false; }
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
    // Return Stored, Duplicate, Full, or StorageFault. Target persistence writes
    // and verifies a slot before Stored is returned.
    CommitResult commit(const DomainEvent& event);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Expose records without a backend application commit ACK; a transport PUBACK is insufficient.
    std::vector<DomainEvent> pending_cloud(std::size_t limit) const;
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    bool contains(const EventKey& key) const;
    bool cloud_completed(const EventKey& key) const { return cloud_acked_.count(key.str()) != 0; }
    std::size_t cloud_completed_count() const { return cloud_acked_.size(); }
    std::size_t size() const { return records_.size(); }
    bool storage_fault() const { return storage_fault_; }
    bool persistent() const { return store_ != nullptr && !storage_fault_; }
    const std::vector<DomainEvent>& records() const { return records_; }

private:
    friend class CloudSync;
    // Only CloudSync may persist completion after an authenticated matching
    // backend COMMITTED response. Journal records remain intact.
    bool acknowledge_cloud(const EventKey& key);
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
