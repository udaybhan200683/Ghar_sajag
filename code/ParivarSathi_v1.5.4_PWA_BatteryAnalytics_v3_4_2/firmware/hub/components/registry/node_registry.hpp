#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <optional>
#include <string>

namespace gs::hub {

// Physical identity, installation binding and user-facing identity are
// deliberately separate. Public keys and identifiers are not credentials.
struct EnrolledNode {
    std::string device_id;
    std::array<std::uint8_t, 65> p256_public_key{};
    std::array<std::uint8_t, 6> radio_mac{};
    std::string home_id;
    std::string hub_id;
    std::string logical_id;
    std::string room;
    std::string function;
    std::uint64_t last_session{0};
    bool quarantined{false};
};

enum class RegistryResult {
    Accepted,
    AlreadyEnrolled,
    UnknownDevice,
    RevokedDevice,
    ForeignInstallation,
    DuplicatePhysicalIdentity,
    DuplicateRadioAddress,
    DuplicateLogicalIdentity,
    CapacityFull,
    RevocationCapacityFull,
    StaleSession,
    InvalidRecord
};

struct RegistryCounters {
    std::uint32_t enrolled{0};
    std::uint32_t removed{0};
    std::uint32_t replaced{0};
    std::uint32_t rejected{0};
    std::uint32_t rejoined{0};
    std::uint32_t quarantined{0};
};

// This bounded store is downstream of authenticated commissioning/rejoin.
// The radio callback must never call enroll() merely because a MAC or product
// signature matches. The cryptographic proof gate is a separate component.
class NodeRegistry {
public:
    NodeRegistry(std::string home_id, std::string hub_id,
                 std::size_t installed_capacity, std::size_t tombstone_capacity);

    RegistryResult enroll(const EnrolledNode& authenticated_record);
    RegistryResult rejoin(const std::string& device_id,
                          const std::array<std::uint8_t, 6>& radio_mac,
                          std::uint64_t authenticated_session);
    RegistryResult remove(const std::string& device_id);
    RegistryResult replace(const std::string& old_device_id,
                           const EnrolledNode& authenticated_replacement);
    std::optional<EnrolledNode> find(const std::string& device_id) const;
    bool is_revoked(const std::string& device_id) const;
    std::size_t size() const { return active_.size(); }
    std::size_t capacity() const { return installed_capacity_; }
    std::size_t tombstone_count() const { return tombstones_.size(); }
    const RegistryCounters& counters() const { return counters_; }

private:
    bool valid(const EnrolledNode& record) const;
    RegistryResult conflict(const EnrolledNode& record,
                            const std::string& excluded_device_id = "") const;
    void tombstone(const std::string& device_id);
    RegistryResult reject_revocation_at_capacity(EnrolledNode& record);
    RegistryResult reject(RegistryResult reason);

    std::string home_id_;
    std::string hub_id_;
    std::size_t installed_capacity_;
    std::size_t tombstone_capacity_;
    std::map<std::string, EnrolledNode> active_;
    std::deque<std::string> tombstones_;
    RegistryCounters counters_{};
};

}  // namespace gs::hub
