#include "firmware/hub/components/registry/node_registry.hpp"

#include <algorithm>
#include <utility>

namespace gs::hub {

NodeRegistry::NodeRegistry(std::string home_id, std::string hub_id,
                           std::size_t installed_capacity, std::size_t tombstone_capacity)
    : home_id_(std::move(home_id)), hub_id_(std::move(hub_id)),
      installed_capacity_(installed_capacity), tombstone_capacity_(tombstone_capacity) {
    if (home_id_.empty() || hub_id_.empty() || installed_capacity_ < 10 ||
        tombstone_capacity_ == 0) {
        // ESP-IDF product builds disable C++ exceptions. An invalid registry
        // must refuse all mutations rather than panic or become unbounded.
        installed_capacity_ = 0;
        tombstone_capacity_ = 0;
    }
}

bool NodeRegistry::valid(const EnrolledNode& record) const {
    return !record.device_id.empty() && record.device_id.size() <= 64 &&
           !record.logical_id.empty() && record.logical_id.size() <= 24 &&
           !record.room.empty() && record.room.size() <= 24 &&
           !record.function.empty() && record.function.size() <= 24 &&
           record.p256_public_key.front() == 0x04 && !record.quarantined &&
           std::any_of(record.radio_mac.begin(), record.radio_mac.end(),
                       [](std::uint8_t value) { return value != 0; });
}

RegistryResult NodeRegistry::reject(RegistryResult reason) {
    ++counters_.rejected;
    return reason;
}

RegistryResult NodeRegistry::conflict(const EnrolledNode& record,
                                      const std::string& excluded_device_id) const {
    for (const auto& [id, existing] : active_) {
        if (id == excluded_device_id) continue;
        if (existing.radio_mac == record.radio_mac) return RegistryResult::DuplicateRadioAddress;
        if (existing.logical_id == record.logical_id) return RegistryResult::DuplicateLogicalIdentity;
    }
    return RegistryResult::Accepted;
}

RegistryResult NodeRegistry::enroll(const EnrolledNode& record) {
    if (installed_capacity_ == 0) return reject(RegistryResult::InvalidRecord);
    if (!valid(record)) return reject(RegistryResult::InvalidRecord);
    if (record.home_id != home_id_ || record.hub_id != hub_id_)
        return reject(RegistryResult::ForeignInstallation);
    if (is_revoked(record.device_id)) return reject(RegistryResult::RevokedDevice);
    const auto existing = active_.find(record.device_id);
    if (existing != active_.end()) {
        if (existing->second.p256_public_key == record.p256_public_key &&
            existing->second.radio_mac == record.radio_mac && !existing->second.quarantined) {
            if (existing->second.logical_id == record.logical_id &&
                existing->second.room == record.room &&
                existing->second.function == record.function)
                return RegistryResult::AlreadyEnrolled;
            return reject(RegistryResult::DuplicateLogicalIdentity);
        }
        existing->second.quarantined = true;
        ++counters_.quarantined;
        return reject(RegistryResult::DuplicatePhysicalIdentity);
    }
    const auto clash = conflict(record);
    if (clash != RegistryResult::Accepted) return reject(clash);
    if (active_.size() >= installed_capacity_) return reject(RegistryResult::CapacityFull);
    active_.emplace(record.device_id, record);
    ++counters_.enrolled;
    return RegistryResult::Accepted;
}

RegistryResult NodeRegistry::rejoin(const std::string& device_id,
                                    const std::array<std::uint8_t, 6>& radio_mac,
                                    std::uint64_t session) {
    if (installed_capacity_ == 0) return reject(RegistryResult::InvalidRecord);
    auto found = active_.find(device_id);
    if (found == active_.end())
        return reject(is_revoked(device_id) ? RegistryResult::RevokedDevice
                                            : RegistryResult::UnknownDevice);
    auto& record = found->second;
    if (record.quarantined) return reject(RegistryResult::DuplicatePhysicalIdentity);
    if (record.radio_mac != radio_mac) {
        record.quarantined = true;
        ++counters_.quarantined;
        return reject(RegistryResult::DuplicatePhysicalIdentity);
    }
    if (session == 0 || session <= record.last_session)
        return reject(RegistryResult::StaleSession);
    record.last_session = session;
    ++counters_.rejoined;
    return RegistryResult::Accepted;
}

void NodeRegistry::tombstone(const std::string& device_id) {
    tombstones_.push_back(device_id);
}

RegistryResult NodeRegistry::reject_revocation_at_capacity(EnrolledNode& record) {
    // A requested removal must not leave its physical identity usable when
    // the bounded revocation store is full. Keep the record and every prior
    // tombstone for explicit service recovery; admit no new session.
    if (!record.quarantined) {
        record.quarantined = true;
        ++counters_.quarantined;
    }
    return reject(RegistryResult::RevocationCapacityFull);
}

RegistryResult NodeRegistry::remove(const std::string& device_id) {
    if (installed_capacity_ == 0) return reject(RegistryResult::InvalidRecord);
    const auto found = active_.find(device_id);
    if (found == active_.end())
        return reject(is_revoked(device_id) ? RegistryResult::RevokedDevice
                                            : RegistryResult::UnknownDevice);
    if (tombstones_.size() >= tombstone_capacity_)
        return reject_revocation_at_capacity(found->second);
    active_.erase(found);
    tombstone(device_id);
    ++counters_.removed;
    return RegistryResult::Accepted;
}

RegistryResult NodeRegistry::replace(const std::string& old_device_id,
                                     const EnrolledNode& replacement) {
    if (installed_capacity_ == 0) return reject(RegistryResult::InvalidRecord);
    const auto old = active_.find(old_device_id);
    if (old == active_.end()) return reject(RegistryResult::UnknownDevice);
    if (!valid(replacement)) return reject(RegistryResult::InvalidRecord);
    if (replacement.home_id != home_id_ || replacement.hub_id != hub_id_)
        return reject(RegistryResult::ForeignInstallation);
    if (replacement.device_id == old_device_id || is_revoked(replacement.device_id) ||
        active_.count(replacement.device_id) != 0)
        return reject(RegistryResult::DuplicatePhysicalIdentity);
    if (replacement.logical_id != old->second.logical_id ||
        replacement.room != old->second.room || replacement.function != old->second.function)
        return reject(RegistryResult::DuplicateLogicalIdentity);
    const auto clash = conflict(replacement, old_device_id);
    if (clash != RegistryResult::Accepted) return reject(clash);
    if (tombstones_.size() >= tombstone_capacity_)
        return reject_revocation_at_capacity(old->second);
    // Validate before mutation. The logical slot remains occupied throughout
    // replacement, including when the registry is at installed capacity.
    active_.emplace(replacement.device_id, replacement);
    active_.erase(old);
    tombstone(old_device_id);
    ++counters_.replaced;
    return RegistryResult::Accepted;
}

std::optional<EnrolledNode> NodeRegistry::find(const std::string& device_id) const {
    const auto found = active_.find(device_id);
    return found == active_.end() ? std::nullopt : std::optional<EnrolledNode>{found->second};
}

bool NodeRegistry::can_retry_unactivated(const EnrolledNode& exact) const {
    const auto found = active_.find(exact.device_id);
    if (found == active_.end() || is_revoked(exact.device_id)) return false;
    const auto& current = found->second;
    return !current.quarantined && current.last_session == 0 &&
           current.p256_public_key == exact.p256_public_key &&
           current.radio_mac == exact.radio_mac &&
           current.home_id == exact.home_id && current.hub_id == exact.hub_id &&
           current.logical_id == exact.logical_id && current.room == exact.room &&
           current.function == exact.function;
}

bool NodeRegistry::is_revoked(const std::string& device_id) const {
    return std::find(tombstones_.begin(), tombstones_.end(), device_id) != tombstones_.end();
}

RegistrySnapshot NodeRegistry::snapshot() const {
    RegistrySnapshot state;
    state.home_id = home_id_;
    state.hub_id = hub_id_;
    state.active.reserve(active_.size());
    for (const auto& [id, record] : active_) {
        (void)id;
        state.active.push_back(record);
    }
    state.revoked_device_ids.assign(tombstones_.begin(), tombstones_.end());
    return state;
}

bool NodeRegistry::restore(const RegistrySnapshot& state) {
    if (installed_capacity_ == 0 || !active_.empty() || !tombstones_.empty() ||
        state.home_id != home_id_ || state.hub_id != hub_id_ ||
        state.active.size() > installed_capacity_ ||
        state.revoked_device_ids.size() > tombstone_capacity_) return false;

    NodeRegistry candidate(home_id_, hub_id_, installed_capacity_, tombstone_capacity_);
    for (const auto& id : state.revoked_device_ids) {
        if (id.empty() || id.size() > 64 || candidate.is_revoked(id)) return false;
        candidate.tombstone(id);
    }
    for (const auto& saved : state.active) {
        EnrolledNode record = saved;
        record.quarantined = false;
        if (candidate.enroll(record) != RegistryResult::Accepted) return false;
        if (saved.quarantined) candidate.active_.find(saved.device_id)->second.quarantined = true;
    }
    active_.swap(candidate.active_);
    tombstones_.swap(candidate.tombstones_);
    counters_ = {};
    return true;
}

}  // namespace gs::hub
