#pragma once

#include "firmware/common/security/commissioning_protocol.hpp"

#include <cstdint>
#include <optional>

namespace gs::security {

enum class AssociationStatus { Missing, Paired, Unpaired, Corrupt, IoError };

struct AssociationState {
    AssociationStatus status{AssociationStatus::Missing};
    std::uint64_t generation{0};
    std::optional<CommissioningBinding> binding;
};

// A single write must atomically replace one bounded blob. Target adapters
// must not report success until the flash/NVS commit is complete. Key storage
// is separate and must be protected in production.
class AssociationBlobStore {
public:
    virtual ~AssociationBlobStore() = default;
    virtual bool read(Bytes& blob, bool& found) = 0;
    virtual bool write(const Bytes& blob) = 0;
};

class AssociationRepository {
public:
    AssociationRepository(CommissioningCrypto& crypto, AssociationBlobStore& store,
                          const Key32& protected_wrapping_key);
    ~AssociationRepository();
    AssociationRepository(const AssociationRepository&) = delete;
    AssociationRepository& operator=(const AssociationRepository&) = delete;
    AssociationState load();
    bool save_initial(const CommissioningBinding& binding);
    bool factory_reset();

private:
    bool write_record(std::uint64_t generation, bool paired,
                      const CommissioningBinding* binding);
    CommissioningCrypto& crypto_;
    AssociationBlobStore& store_;
    Key32 wrapping_key_{};
};

}  // namespace gs::security
