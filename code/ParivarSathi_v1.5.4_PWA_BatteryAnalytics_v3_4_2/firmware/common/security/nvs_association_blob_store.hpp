#pragma once

#include "firmware/common/security/association_persistence.hpp"

namespace gs::security {

// Stores only AEAD-wrapped security records. Each namespace/key has a strict
// size bound. The wrapping key is supplied separately by a protected key
// source. NVS power-cut atomicity still requires physical qualification.
class NvsBoundedSecurityBlobStore : public SecurityBlobStore {
public:
    NvsBoundedSecurityBlobStore(const char* storage_namespace, const char* key,
                                std::size_t maximum_blob);
    bool read(Bytes& blob, bool& found) override;
    bool write(const Bytes& blob) override;

private:
    const char* storage_namespace_;
    const char* key_;
    std::size_t maximum_blob_;
};

class NvsAssociationBlobStore final : public NvsBoundedSecurityBlobStore {
public:
    NvsAssociationBlobStore();
};

class NvsRegistryBlobStore final : public NvsBoundedSecurityBlobStore {
public:
    NvsRegistryBlobStore();
};

class NvsNodeRecoveryBlobStore final : public NvsBoundedSecurityBlobStore {
public:
    NvsNodeRecoveryBlobStore();
};

}  // namespace gs::security
