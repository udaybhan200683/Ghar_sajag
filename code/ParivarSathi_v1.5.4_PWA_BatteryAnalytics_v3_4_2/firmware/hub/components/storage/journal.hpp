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
#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <vector>

namespace gs::hub {

enum class CommitResult { Stored, Duplicate, Full, StorageFault };
class CloudSync;

// Streaming event backend used by scalable target stores. The interface keeps
// runtime/reducer code independent from a physical slot count. Implementations
// must return Stored only after the event and its recovery identity are durable.
class JournalEventBackend {
public:
    using EventVisitor = bool (*)(void* context, const DomainEvent& event);
    using OrdinalEventVisitor = bool (*)(void* context, std::uint64_t ordinal,
                                         const DomainEvent& event);
    virtual ~JournalEventBackend() = default;
    virtual bool healthy() const = 0;
    virtual std::size_t size() const = 0;
    virtual CommitResult commit(const DomainEvent& event) = 0;
    virtual bool contains(const EventKey& key) = 0;
    virtual bool for_each(EventVisitor visitor, void* context) = 0;
    // ordinal is the immutable publication ordinal, not the position in this
    // iteration. Sparse backends may omit bodies covered by a durable reducer
    // checkpoint while retaining the lifetime high-water mark returned by size().
    virtual bool for_each_with_ordinal(OrdinalEventVisitor visitor, void* context);
    // Scalable backends may persist authenticated completion independently.
    // The compatibility defaults keep unsupported backends pending; completion
    // alone never authorizes event-body retirement.
    virtual bool cloud_completed(const EventKey&) const { return false; }
    virtual std::size_t cloud_completed_count() const { return 0; }
    // Authenticated lifecycle prefix whose bodies were retired only after all
    // exact backend receipts and Node/checkpoint proofs were verified.
    virtual std::uint64_t backend_completion_retired_through() const { return 0; }
    virtual bool acknowledge_cloud(const EventKey&) { return false; }
};

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
    virtual bool erase(std::size_t) { return false; }
    virtual bool erase_completion(std::size_t) { return false; }
};

class HubJournal {
public:
    explicit HubJournal(std::size_t capacity = 1024);
    ~HubJournal();
    HubJournal(const HubJournal&) = delete;
    HubJournal& operator=(const HubJournal&) = delete;
    // A failed or ambiguous load locks the journal closed until repaired.
    // Existing prototype callers remain volatile until they opt in.
    // Optional startup scheduling hook: called between independent slot operations.
    // The owner must keep event admission closed until attachment succeeds.
    bool attach_persistence(security::CommissioningCrypto& crypto,
                            JournalSlotStore& store,
                            const security::Key32& protected_key,
                            void (*recovery_cooperate)() = nullptr);
    // Attach a recovered streaming backend before any event admission. Unlike
    // the legacy slot store this has no event-count-derived storage capacity.
    bool attach_backend(JournalEventBackend& backend);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Return Stored, Duplicate, Full, or StorageFault. Target persistence writes
    // and verifies a slot before Stored is returned.
    CommitResult commit(const DomainEvent& event);
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    // Expose records without a backend application commit ACK; a transport PUBACK is insufficient.
    std::vector<DomainEvent> pending_cloud(std::size_t limit) const;
    // @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
    bool contains(const EventKey& key) const;
    bool cloud_completed(const EventKey& key) const;
    std::size_t cloud_completed_count() const;
    std::uint64_t backend_completion_retired_through() const;
    std::size_t size() const;
    bool storage_fault() const;
    bool persistent() const;
    // For scalable backends this is the immutable publication high-water mark;
    // it may exceed the count of currently retained bodies after retirement.
    const std::vector<DomainEvent>& records() const { return records_; }
    bool for_each(JournalEventBackend::EventVisitor visitor, void* context) const;
    bool for_each_with_ordinal(JournalEventBackend::OrdinalEventVisitor visitor,
                               void* context) const;
    static bool encode_event_payload(const DomainEvent&, security::Bytes&);
    static bool decode_event_payload(const security::Bytes&, DomainEvent&);
    static bool encode_slot_blob(security::CommissioningCrypto&, const security::Key32&,
                                 std::size_t slot, const DomainEvent&, security::Bytes&);
    static bool decode_slot_blob(security::CommissioningCrypto&, const security::Key32&,
                                 std::size_t slot, const security::Bytes&, DomainEvent&);
    static bool encode_completion_receipt(security::CommissioningCrypto&,
                                          const security::Key32&, std::size_t slot,
                                          const EventKey&, security::Bytes&);
    static bool verify_completion_receipt(security::CommissioningCrypto&,
                                          const security::Key32&, std::size_t slot,
                                          const EventKey&, const security::Bytes&);

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
    JournalEventBackend* backend_{nullptr};
    security::Key32 storage_key_{};
    bool storage_fault_{false};
};

}  // namespace gs::hub
