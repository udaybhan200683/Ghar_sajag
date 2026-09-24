// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H02 Hub persistence
// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// A commit result has three meanings: Stored adds a new record, Duplicate refers to an already known key,
// and Full refuses new evidence. The name journal describes intended semantics; the current deque is
// volatile. Cloud acknowledgements mark records but do not currently free capacity.

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
    out.clear();
    out.push_back(1);
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
    return out.size() <= 256;
}

bool decode_event(const Bytes& in, gs::DomainEvent& event) {
    std::size_t at = 0;
    if (in.empty() || in[at++] != 1 ||
        !get_string(in, at, event.key.physical_device_id, 64, true) ||
        !get_string(in, at, event.key.source_id, 24) ||
        !get_string(in, at, event.location, 64, true) ||
        !get64(in, at, event.key.session_id) ||
        !get64(in, at, event.key.sequence)) return false;
    std::uint64_t monotonic = 0, occurred = 0, received = 0;
    if (!get64(in, at, monotonic) || !get64(in, at, occurred) ||
        !get64(in, at, received) ||
        in.size() - at != 11) return false;
    event.monotonic_ms = static_cast<gs::Milliseconds>(monotonic);
    event.occurred_at = static_cast<gs::EpochSeconds>(occurred);
    event.received_at = static_cast<gs::EpochSeconds>(received);
    if (in[at] > static_cast<std::uint8_t>(gs::EventKind::Gap) ||
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
    return !event.key.physical_device_id.empty() &&
           event.key.session_id != 0 && event.key.sequence != 0;
}

Bytes slot_aad(std::size_t slot) {
    Bytes aad{'G', 'S', 'J', 1};
    put64(aad, slot);
    return aad;
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

bool HubJournal::attach_persistence(security::CommissioningCrypto& crypto,
                                    JournalSlotStore& store,
                                    const security::Key32& protected_key) {
    if (store_ || !records_.empty() || capacity_ != 128 ||
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
        security::Bytes blob;
        bool found = false;
        if (!store.read(slot, blob, found)) { storage_fault_ = true; break; }
        if (!found) { saw_empty = true; continue; }
        DomainEvent event;
        if (saw_empty || !open_slot(crypto, storage_key_, slot, blob, event) ||
            !ids_.insert(event.key.str()).second) { storage_fault_ = true; break; }
        records_.push_back(std::move(event));
    }
    return !storage_fault_;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Return Stored, Duplicate or Full for this event identity; this reference container is volatile, not
// flash.
CommitResult HubJournal::commit(const DomainEvent& event) {
    GS_TRACE(gs::log::Category::Storage, "H02", "commit.enter", "-");
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
        if (!store_->write(slot, blob) || !store_->read(slot, verified, found) ||
            !found || verified != blob ||
            !open_slot(*crypto_, storage_key_, slot, verified, roundtrip) ||
            roundtrip.key.str() != id) {
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
    for (const auto& event : records_) {
        if (!cloud_acked_.count(event.key.str())) result.push_back(event);
        if (result.size() >= limit) break;
    }
    return result;
}

// @requirements F05, F06, F07, E02, E03, E05, E10, NFR-03, NFR-05
// Mark backend commitment; current reference does not reclaim journal records or implement flash
// compaction.
bool HubJournal::acknowledge_cloud(const EventKey& key) {
    GS_TRACE(gs::log::Category::Storage, "H02", "acknowledge_cloud.enter", "-");
    if (!ids_.count(key.str())) return false;
    cloud_acked_.insert(key.str());
    return true;
}

bool HubJournal::contains(const EventKey& key) const {
    GS_TRACE(gs::log::Category::Storage, "H02", "contains.enter", "-");
    return ids_.count(key.str()) > 0;
}

}  // namespace gs::hub
