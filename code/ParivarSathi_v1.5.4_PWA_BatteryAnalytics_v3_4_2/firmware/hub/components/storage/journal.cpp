// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H02 Hub persistence
// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Persistent target slots retain accepted events for reducer replay and deduplication.
// Backend completion receipts are separate write-once slots; neither frees capacity.

#include "storage/journal.hpp"
#include "gs/logging.hpp"

#include <algorithm>

namespace {
using gs::security::Bytes;

void put64(Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

bool get64(const Bytes& in, std::size_t& at, std::uint64_t& value) {
    if (at > in.size() || in.size() - at < 8) return false;
    value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8) | in[at++];
    return true;
}

bool put_string(Bytes& out, const std::string& value, std::size_t maximum,
                bool allow_empty = false) {
    if (value.size() > maximum || (!allow_empty && value.empty())) return false;
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
    return true;
}

bool get_string(const Bytes& in, std::size_t& at, std::string& value,
                std::size_t maximum, bool allow_empty = false) {
    if (at >= in.size()) return false;
    const auto length = in[at++];
    if (length > maximum || (!allow_empty && length == 0) || length > in.size() - at)
        return false;
    value.assign(reinterpret_cast<const char*>(in.data() + at), length);
    at += length;
    return true;
}

bool encode_event(const gs::DomainEvent& event, Bytes& out) {
    if ((event.kind == gs::EventKind::MotionSummary) != event.motion_aggregate.has_value() ||
        (event.motion_aggregate && !gs::valid_motion_aggregate(*event.motion_aggregate)))
        return false;
    out.clear();
    out.push_back(2);
    if (!put_string(out, event.key.physical_device_id, 64, true) ||
        !put_string(out, event.key.source_id, 24) ||
        !put_string(out, event.location, 64, true)) return false;
    put64(out, event.key.session_id);
    put64(out, event.key.sequence);
    put64(out, event.monotonic_ms);
    put64(out, static_cast<std::uint64_t>(event.occurred_at));
    put64(out, static_cast<std::uint64_t>(event.received_at));
    out.push_back(static_cast<std::uint8_t>(event.kind));
    out.push_back(static_cast<std::uint8_t>(event.sensor_type));
    out.push_back(static_cast<std::uint8_t>(event.uncertainty_s >> 24));
    out.push_back(static_cast<std::uint8_t>(event.uncertainty_s >> 16));
    out.push_back(static_cast<std::uint8_t>(event.uncertainty_s >> 8));
    out.push_back(static_cast<std::uint8_t>(event.uncertainty_s));
    out.push_back(static_cast<std::uint8_t>(event.battery_mv >> 8));
    out.push_back(static_cast<std::uint8_t>(event.battery_mv));
    out.push_back(event.is_test ? 1 : 0);
    const auto rssi = static_cast<std::uint16_t>(event.rssi_dbm);
    out.push_back(static_cast<std::uint8_t>(rssi >> 8));
    out.push_back(static_cast<std::uint8_t>(rssi));
    out.push_back(event.motion_aggregate ? 1 : 0);
    if (event.motion_aggregate) {
        const auto& aggregate = *event.motion_aggregate;
        if (!gs::valid_motion_aggregate(aggregate)) return false;
        out.push_back(static_cast<std::uint8_t>(aggregate.additional_count >> 24));
        out.push_back(static_cast<std::uint8_t>(aggregate.additional_count >> 16));
        out.push_back(static_cast<std::uint8_t>(aggregate.additional_count >> 8));
        out.push_back(static_cast<std::uint8_t>(aggregate.additional_count));
        put64(out, static_cast<std::uint64_t>(aggregate.first_ms));
        put64(out, static_cast<std::uint64_t>(aggregate.last_ms));
    }
    return out.size() <= 256;
}

bool decode_event(const Bytes& in, gs::DomainEvent& event) {
    std::size_t at = 0;
    if (in.empty() || (in[0] != 1 && in[0] != 2)) return false;
    const auto version = in[at++];
    if (
        !get_string(in, at, event.key.physical_device_id, 64, true) ||
        !get_string(in, at, event.key.source_id, 24) ||
        !get_string(in, at, event.location, 64, true) ||
        !get64(in, at, event.key.session_id) ||
        !get64(in, at, event.key.sequence)) return false;
    std::uint64_t monotonic = 0, occurred = 0, received = 0;
    if (!get64(in, at, monotonic) || !get64(in, at, occurred) ||
        !get64(in, at, received) ||
        in.size() - at < (version == 1 ? 11U : 12U)) return false;
    event.monotonic_ms = static_cast<gs::Milliseconds>(monotonic);
    event.occurred_at = static_cast<gs::EpochSeconds>(occurred);
    event.received_at = static_cast<gs::EpochSeconds>(received);
    if (in[at] > static_cast<std::uint8_t>(gs::EventKind::MotionSummary) ||
        in[at + 1] > static_cast<std::uint8_t>(gs::SensorType::System)) return false;
    event.kind = static_cast<gs::EventKind>(in[at++]);
    event.sensor_type = static_cast<gs::SensorType>(in[at++]);
    event.uncertainty_s = (static_cast<std::uint32_t>(in[at]) << 24) |
        (static_cast<std::uint32_t>(in[at + 1]) << 16) |
        (static_cast<std::uint32_t>(in[at + 2]) << 8) | in[at + 3];
    at += 4;
    event.battery_mv = static_cast<std::uint16_t>((in[at] << 8) | in[at + 1]);
    at += 2;
    if (in[at] > 1) return false;
    event.is_test = in[at++] != 0;
    event.rssi_dbm = static_cast<std::int16_t>((in[at] << 8) | in[at + 1]);
    at += 2;
    if (version == 2) {
        if (at >= in.size() || in[at] > 1) return false;
        if (in[at++] != 0) {
            if (in.size() - at < 20) return false;
            gs::DomainEvent::MotionAggregate aggregate;
            aggregate.additional_count = (static_cast<std::uint32_t>(in[at]) << 24) |
                (static_cast<std::uint32_t>(in[at + 1]) << 16) |
                (static_cast<std::uint32_t>(in[at + 2]) << 8) | in[at + 3];
            at += 4;
            std::uint64_t first = 0, last = 0;
            if (!get64(in, at, first) || !get64(in, at, last)) return false;
            aggregate.first_ms = static_cast<gs::Milliseconds>(first);
            aggregate.last_ms = static_cast<gs::Milliseconds>(last);
            event.motion_aggregate = aggregate;
        }
    }
    return !event.key.physical_device_id.empty() &&
           event.key.session_id != 0 && event.key.sequence != 0 &&
           at == in.size() &&
           (event.kind == gs::EventKind::MotionSummary) == event.motion_aggregate.has_value() &&
           (!event.motion_aggregate || gs::valid_motion_aggregate(*event.motion_aggregate));
}

Bytes slot_aad(std::size_t slot) {
    Bytes aad{'G', 'S', 'J', 1};
    put64(aad, slot);
    return aad;
}

bool completion_mac(gs::security::CommissioningCrypto& crypto,
                    const gs::security::Key32& key, std::size_t slot,
                    const gs::EventKey& event_key, gs::security::Bytes& out) {
    constexpr char context_text[] = "GharSajag/HubCompletion/v1";
    const gs::security::Bytes context(context_text, context_text + sizeof(context_text) - 1);
    const gs::security::Bytes salt{'G', 'S', 'C', 1};
    gs::security::Key32 receipt_key{};
    if (!crypto.hkdf_sha256(key, salt, context, receipt_key)) return false;
    gs::security::Bytes message{'G', 'S', 'C', 1};
    put64(message, slot);
    const auto identity = event_key.str();
    message.insert(message.end(), identity.begin(), identity.end());
    gs::security::Key32 digest{};
    const bool sealed = crypto.hmac_sha256(receipt_key, message, digest);
    crypto.secure_zero(receipt_key.data(), receipt_key.size());
    if (!sealed) return false;
    out.assign(digest.begin(), digest.end());
    crypto.secure_zero(digest.data(), digest.size());
    return true;
}

bool open_slot(gs::security::CommissioningCrypto& crypto,
               const gs::security::Key32& key, std::size_t slot,
               const Bytes& blob, gs::DomainEvent& event) {
    if (blob.size() < 12 + 16 || blob.size() > 12 + 256 + 16) return false;
    gs::security::Nonce12 nonce{};
    gs::security::GcmTag tag{};
    std::copy_n(blob.begin(), nonce.size(), nonce.begin());
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    Bytes cipher(blob.begin() + nonce.size(), blob.end() - tag.size());
    Bytes plain;
    const bool opened = crypto.open_aes256_gcm(key, nonce, slot_aad(slot),
                                                cipher, tag, plain);
    const bool valid = opened && decode_event(plain, event);
    if (!plain.empty()) crypto.secure_zero(plain.data(), plain.size());
    return valid;
}
}  // namespace

namespace gs::hub {

HubJournal::HubJournal(std::size_t capacity) : capacity_(capacity) {
    GS_TRACE(gs::log::Category::Storage, "H02", "HubJournal.enter", "-");}

HubJournal::~HubJournal() {
    volatile std::uint8_t* key = storage_key_.data();
    for (std::size_t i = 0; i < storage_key_.size(); ++i) key[i] = 0;
}

bool HubJournal::encode_event_payload(const DomainEvent& event, security::Bytes& out) {
    return encode_event(event, out);
}

bool HubJournal::decode_event_payload(const security::Bytes& in, DomainEvent& event) {
    return decode_event(in, event);
}

bool HubJournal::encode_slot_blob(security::CommissioningCrypto& crypto,
                                  const security::Key32& key, std::size_t slot,
                                  const DomainEvent& event, security::Bytes& blob) {
    security::Bytes plain;
    if (!encode_event(event, plain)) return false;
    security::Nonce12 nonce{};
    security::GcmTag tag{};
    security::Bytes cipher;
    const bool sealed = crypto.random_bytes(nonce.data(), nonce.size()) &&
        crypto.seal_aes256_gcm(key, nonce, slot_aad(slot), plain, cipher, tag);
    crypto.secure_zero(plain.data(), plain.size());
    if (!sealed) return false;
    blob.assign(nonce.begin(), nonce.end());
    blob.insert(blob.end(), cipher.begin(), cipher.end());
    blob.insert(blob.end(), tag.begin(), tag.end());
    return blob.size() <= 12 + 256 + 16;
}

bool HubJournal::decode_slot_blob(security::CommissioningCrypto& crypto,
                                  const security::Key32& key, std::size_t slot,
                                  const security::Bytes& blob, DomainEvent& event) {
    return open_slot(crypto, key, slot, blob, event);
}

bool HubJournal::encode_completion_receipt(security::CommissioningCrypto& crypto,
                                           const security::Key32& key, std::size_t slot,
                                           const EventKey& event_key,
                                           security::Bytes& out) {
    return completion_mac(crypto, key, slot, event_key, out);
}

bool HubJournal::verify_completion_receipt(security::CommissioningCrypto& crypto,
                                           const security::Key32& key, std::size_t slot,
                                           const EventKey& event_key,
                                           const security::Bytes& receipt) {
    security::Bytes expected;
    return receipt.size() == 32 &&
           completion_mac(crypto, key, slot, event_key, expected) &&
           crypto.constant_time_equal(receipt.data(), expected.data(), expected.size());
}

bool HubJournal::attach_persistence(security::CommissioningCrypto& crypto,
                                    JournalSlotStore& store,
                                    const security::Key32& protected_key,
                                    void (*recovery_cooperate)()) {
    if (store_ || backend_ || !records_.empty() || capacity_ != 128 ||
        !std::any_of(protected_key.begin(), protected_key.end(),
                     [](std::uint8_t byte) { return byte != 0; })) {
        storage_fault_ = true;
        return false;
    }
    crypto_ = &crypto;
    store_ = &store;
    storage_key_ = protected_key;
    bool saw_empty = false;
    for (std::size_t slot = 0; slot < capacity_; ++slot) {
        if (recovery_cooperate) recovery_cooperate();
        security::Bytes blob;
        bool found = false;
        if (!store.read(slot, blob, found)) { storage_fault_ = true; break; }
        if (!found) { saw_empty = true; continue; }
        DomainEvent event;
        if (saw_empty || !open_slot(crypto, storage_key_, slot, blob, event) ||
            !ids_.insert(event.key.str()).second) { storage_fault_ = true; break; }
        records_.push_back(std::move(event));
    }
    if (!storage_fault_) for (std::size_t slot = 0; slot < capacity_; ++slot) {
        if (recovery_cooperate) recovery_cooperate();
        security::Bytes receipt;
        bool found = false;
        if (!store.read_completion(slot, receipt, found)) { storage_fault_ = true; break; }
        if (!found) continue;
        security::Bytes expected;
        if (slot >= records_.size() || receipt.size() != 32 ||
            !completion_mac(crypto, storage_key_, slot, records_[slot].key, expected) ||
            !crypto.constant_time_equal(receipt.data(), expected.data(), expected.size())) {
            storage_fault_ = true;
            break;
        }
        cloud_acked_.insert(records_[slot].key.str());
    }
    return !storage_fault_;
}

bool HubJournal::attach_backend(JournalEventBackend& backend) {
    if (store_ || backend_ || !records_.empty() || !ids_.empty() ||
        !backend.healthy()) {
        storage_fault_ = true;
        return false;
    }
    backend_ = &backend;
    return true;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Persistent target writes and verifies a slot before returning Stored.
CommitResult HubJournal::commit(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Storage, "H02", "commit.enter", "-");
    if (backend_ != nullptr)
        return backend_->healthy() ? backend_->commit(event) : CommitResult::StorageFault;
    if (storage_fault_) return CommitResult::StorageFault;
    const auto id = event.key.str();
    if (ids_.count(id)) return CommitResult::Duplicate;
    if (records_.size() >= capacity_) {
        GS_ERROR(gs::log::Category::Storage, "H02", "commit.failed", "capacity_exhausted");
        return CommitResult::Full;
    }
    if (store_) {
        if (event.key.physical_device_id.empty() || event.key.session_id == 0 ||
            event.key.sequence == 0) return CommitResult::StorageFault;
        security::Bytes plain;
        if (!encode_event(event, plain)) return CommitResult::StorageFault;
        security::Nonce12 nonce{};
        security::GcmTag tag{};
        security::Bytes cipher;
        const auto slot = records_.size();
        if (!crypto_->random_bytes(nonce.data(), nonce.size()) ||
            !crypto_->seal_aes256_gcm(storage_key_, nonce, slot_aad(slot),
                                       plain, cipher, tag)) {
            crypto_->secure_zero(plain.data(), plain.size());
            storage_fault_ = true;
            return CommitResult::StorageFault;
        }
        crypto_->secure_zero(plain.data(), plain.size());
        security::Bytes blob(nonce.begin(), nonce.end());
        blob.insert(blob.end(), cipher.begin(), cipher.end());
        blob.insert(blob.end(), tag.begin(), tag.end());
        security::Bytes verified;
        bool found = false;
        DomainEvent roundtrip;
        Bytes expected_event, verified_event;
        // Durable adapters may materialize the same encrypted slot with a new
        // nonce on read. Verify the full decoded event rather than ciphertext
        // identity; the legacy NVS adapter still returns its exact stored blob.
        if (!store_->write(slot, blob) || !store_->read(slot, verified, found) ||
            !found ||
            !open_slot(*crypto_, storage_key_, slot, verified, roundtrip) ||
            roundtrip.key.str() != id || !encode_event(event, expected_event) ||
            !encode_event(roundtrip, verified_event) || expected_event != verified_event) {
            storage_fault_ = true;
            return CommitResult::StorageFault;
        }
    }
    records_.push_back(event);
    ids_.insert(id);
    return CommitResult::Stored;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Expose records without a backend application commit ACK; a transport PUBACK is insufficient.
std::vector<DomainEvent> HubJournal::pending_cloud(std::size_t limit) const {
    GS_TRACE(gs::log::Category::Storage, "H02", "pending_cloud.enter", "-");
    std::vector<DomainEvent> result;
    if (backend_ != nullptr) {
        struct PendingContext {
            JournalEventBackend* backend;
            std::vector<DomainEvent>* result;
            std::size_t limit;
        } context{backend_, &result, limit};
        const auto append_pending = [](void* opaque, const DomainEvent& event) -> bool {
            auto& state = *static_cast<PendingContext*>(opaque);
            if (state.result->size() < state.limit &&
                !state.backend->cloud_completed(event.key))
                state.result->push_back(event);
            return true;
        };
        if (limit != 0) (void)backend_->for_each(append_pending, &context);
        return result;
    }
    for (const auto& event : records_) {
        if (!cloud_acked_.count(event.key.str())) result.push_back(event);
        if (result.size() >= limit) break;
    }
    return result;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Persist backend completion in a bounded receipt slot without reclaiming the event.
bool HubJournal::acknowledge_cloud(const EventKey& key) {
    GS_TRACE(gs::log::Category::Storage, "H02", "acknowledge_cloud.enter", "-");
    if (backend_ != nullptr)
        return backend_->healthy() && backend_->acknowledge_cloud(key);
    if (!ids_.count(key.str())) return false;
    if (cloud_acked_.count(key.str())) return true;
    if (storage_fault_) return false;
    if (store_) {
        const auto found = std::find_if(records_.begin(), records_.end(), [&key](const DomainEvent& event) {
            return event.key.str() == key.str();
        });
        if (found == records_.end()) return false;
        const auto slot = static_cast<std::size_t>(std::distance(records_.begin(), found));
        security::Bytes receipt;
        security::Bytes verified;
        bool present = false;
        if (!completion_mac(*crypto_, storage_key_, slot, key, receipt) ||
            !store_->write_completion(slot, receipt) ||
            !store_->read_completion(slot, verified, present) ||
            !present || verified != receipt) {
            storage_fault_ = true;
            return false;
        }
    }
    cloud_acked_.insert(key.str());
    return true;
}

bool HubJournal::contains(const EventKey& key) const {
    GS_TRACE(gs::log::Category::Storage, "H02", "contains.enter", "-");
    if (backend_ != nullptr) return backend_->healthy() && backend_->contains(key);
    return ids_.count(key.str()) > 0;
}

bool HubJournal::cloud_completed(const EventKey& key) const {
    if (backend_ != nullptr) return backend_->cloud_completed(key);
    return cloud_acked_.count(key.str()) != 0;
}

std::size_t HubJournal::cloud_completed_count() const {
    if (backend_ != nullptr) return backend_->cloud_completed_count();
    return cloud_acked_.size();
}

std::size_t HubJournal::size() const {
    if (backend_ != nullptr) return backend_->size();
    return records_.size();
}

bool HubJournal::storage_fault() const {
    if (backend_ != nullptr) return !backend_->healthy();
    return storage_fault_;
}

bool HubJournal::persistent() const {
    if (backend_ != nullptr) return backend_->healthy();
    return store_ != nullptr && !storage_fault_;
}

bool HubJournal::for_each(JournalEventBackend::EventVisitor visitor,
                          void* context) const {
    if (visitor == nullptr) return false;
    if (backend_ != nullptr)
        return backend_->healthy() && backend_->for_each(visitor, context);
    for (const auto& event : records_)
        if (!visitor(context, event)) return false;
    return !storage_fault_;
}

}  // namespace gs::hub
