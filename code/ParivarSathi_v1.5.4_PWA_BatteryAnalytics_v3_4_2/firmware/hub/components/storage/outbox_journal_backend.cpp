#include "storage/outbox_journal_backend.hpp"

#include <algorithm>
#include <limits>

namespace gs::hub::storage {
namespace {
void clear_plaintext(security::Bytes& bytes) {
    volatile std::uint8_t* data = bytes.data();
    for (std::size_t i = 0; i < bytes.size(); ++i) data[i] = 0;
    bytes.clear();
}

struct VisitContext {
    JournalEventBackend::EventVisitor visitor;
    void* context;
};

bool decode_and_visit(void* opaque, std::uint64_t,
                      const std::string& canonical_key,
                      const security::Bytes& payload) {
    auto& visit = *static_cast<VisitContext*>(opaque);
    DomainEvent event;
    if (!HubJournal::decode_event_payload(payload, event) ||
        event.key.str() != canonical_key) return false;
    return visit.visitor(visit.context, event);
}
}  // namespace

std::size_t OutboxJournalBackend::size() const {
    const auto count = outbox_.record_count();
    return count > std::numeric_limits<std::size_t>::max()
        ? std::numeric_limits<std::size_t>::max()
        : static_cast<std::size_t>(count);
}

CommitResult OutboxJournalBackend::commit(const DomainEvent& event) {
    if (!outbox_.healthy()) return CommitResult::StorageFault;
    security::Bytes payload;
    if (!HubJournal::encode_event_payload(event, payload))
        return CommitResult::StorageFault;
    const auto admission_class = is_ordinary_motion(event.kind)
        ? AdmissionClass::Ordinary : AdmissionClass::Protected;
    const auto result = outbox_.append(event.key.str(), payload, admission_class);
    clear_plaintext(payload);
    switch (result) {
        case OutboxAdmission::Committed: return CommitResult::Stored;
        case OutboxAdmission::Duplicate: return CommitResult::Duplicate;
        case OutboxAdmission::ReserveProtected:
        case OutboxAdmission::CapacityExhausted: return CommitResult::Full;
        case OutboxAdmission::IdentityConflict:
        case OutboxAdmission::InvalidRecord:
        case OutboxAdmission::IndexMemoryUnavailable:
        case OutboxAdmission::StorageFailure:
        case OutboxAdmission::MetadataPublicationFailure:
        case OutboxAdmission::IntegrityFailure:
        case OutboxAdmission::RestartRequired:
        case OutboxAdmission::UnsupportedConfiguration:
            return CommitResult::StorageFault;
    }
    return CommitResult::StorageFault;
}

bool OutboxJournalBackend::contains(const EventKey& key) {
    if (!outbox_.healthy()) return false;
    bool found = false;
    const auto result = outbox_.contains(key.str(), found);
    return result == IdentityLookup::Found && found;
}

bool OutboxJournalBackend::for_each(EventVisitor visitor, void* context) {
    if (!outbox_.healthy() || visitor == nullptr) return false;
    VisitContext visit{visitor, context};
    return outbox_.for_each(decode_and_visit, &visit);
}

}  // namespace gs::hub::storage
