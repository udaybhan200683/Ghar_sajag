#pragma once

#include "firmware/common/security/association_persistence.hpp"
#include "firmware/hub/components/registry/node_registry.hpp"

#include <optional>
#include <vector>

namespace gs::hub {

enum class RegistryMigrationPhase : std::uint8_t {
    Uninitialized = 0,
    Prepared = 1,
    Activated = 2
};

struct RegistryMigrationBarrier {
    RegistryMigrationPhase phase{RegistryMigrationPhase::Uninitialized};
    std::uint32_t source_epoch{0};
    std::uint64_t source_checkpoint_generation{0};
    std::array<std::uint8_t, 32> target_checkpoint_digest{};
};

// The binding array is indexed by physical Device ID, never logical room ID.
// Production callers must handle these symmetric keys as secret material.
struct HubRegistryState {
    RegistrySnapshot registry;
    std::vector<security::CommissioningBinding> bindings;
    RegistryMigrationBarrier migration;
};

enum class HubRegistryLoadStatus { Missing, Ready, Corrupt, IoError };

struct HubRegistryLoad {
    HubRegistryLoadStatus status{HubRegistryLoadStatus::Missing};
    std::uint64_t generation{0};
    std::uint8_t schema_version{0};
    std::optional<HubRegistryState> state;
};

// One authenticated bounded snapshot includes registry authorization state
// and every enrolled installation key. The caller supplies a protected Hub
// wrapping key. Target startup wiring and power-cut proof remain separate.
class HubRegistryRepository {
public:
    HubRegistryRepository(security::CommissioningCrypto& crypto,
                          security::SecurityBlobStore& store,
                          const security::Key32& protected_wrapping_key,
                          std::string home_id, std::string hub_id,
                          const security::P256PublicKey& hub_public_key,
                          std::size_t installed_capacity,
                          std::size_t tombstone_capacity);
    ~HubRegistryRepository();
    HubRegistryRepository(const HubRegistryRepository&) = delete;
    HubRegistryRepository& operator=(const HubRegistryRepository&) = delete;

    HubRegistryLoad load();
    bool save(const HubRegistryState& state);
    // Deterministic GSRG v1 -> v2 preparation. The caller persists the GMM2
    // Prepared intent first, then saves this exact candidate to the existing
    // snapshot key. This does not make v2 authorization live.
    bool prepare_v2(const HubRegistryState& authenticated_source,
                    std::uint32_t source_epoch,
                    std::uint64_t source_checkpoint_generation,
                    HubRegistryState& prepared) const;
    bool enrollment_table_digest(const HubRegistryState&,
                                 std::array<std::uint8_t, 32>&) const;
    // load() returns installation keys to the caller; clear them when the
    // authenticated rejoin owner no longer needs this copy.
    void clear_keys(HubRegistryState& state);

private:
    bool valid(const HubRegistryState& state, std::uint8_t schema_version = 2) const;
    bool valid_owner_digests(const HubRegistryState& state) const;
    bool prepare_owner_digests(HubRegistryState& state) const;
    bool preserves_security_state(const HubRegistryState& previous,
                                  const HubRegistryState& next) const;

    security::CommissioningCrypto& crypto_;
    security::SecurityBlobStore& store_;
    security::Key32 wrapping_key_{};
    std::string home_id_;
    std::string hub_id_;
    security::P256PublicKey hub_public_key_{};
    std::size_t installed_capacity_;
    std::size_t tombstone_capacity_;
};

}  // namespace gs::hub
