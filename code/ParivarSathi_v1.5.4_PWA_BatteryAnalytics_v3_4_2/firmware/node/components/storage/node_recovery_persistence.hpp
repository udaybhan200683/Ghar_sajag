#pragma once

#include "firmware/common/security/association_persistence.hpp"
#include "firmware/node/runtime/node_runtime.hpp"

#include <optional>
#include <string>

namespace gs::node {

enum class NodeRecoveryLoadStatus { Missing, Ready, Corrupt, IoError };

struct NodeRecoveryLoad {
    NodeRecoveryLoadStatus status{NodeRecoveryLoadStatus::Missing};
    std::uint64_t generation{0};
    std::optional<NodeRuntimeRecoveryState> state;
};

// The owner must commit a new snapshot before exposing a newly accepted event
// to radio, and after retiring an ACK. A failed commit leaves the earlier
// snapshot in place and must be treated as a storage fault. Target wiring,
// protected-key sourcing and physical power-cut behavior are separate gates.
class NodeRecoveryRepository {
public:
    NodeRecoveryRepository(security::CommissioningCrypto& crypto,
                           security::SecurityBlobStore& store,
                           const security::Key32& protected_wrapping_key,
                           std::string home_id, std::string hub_id,
                           std::string node_id);
    ~NodeRecoveryRepository();
    NodeRecoveryRepository(const NodeRecoveryRepository&) = delete;
    NodeRecoveryRepository& operator=(const NodeRecoveryRepository&) = delete;

    NodeRecoveryLoad load();
    bool save(const NodeRuntimeRecoveryState& state);

private:
    bool valid(const NodeRuntimeRecoveryState& state) const;
    security::CommissioningCrypto& crypto_;
    security::SecurityBlobStore& store_;
    security::Key32 wrapping_key_{};
    std::string home_id_;
    std::string hub_id_;
    std::string node_id_;
};

}  // namespace gs::node
