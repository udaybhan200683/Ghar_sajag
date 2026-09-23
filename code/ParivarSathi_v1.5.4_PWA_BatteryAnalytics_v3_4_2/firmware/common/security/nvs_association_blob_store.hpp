#pragma once

#include "firmware/common/security/association_persistence.hpp"

namespace gs::security {

// Stores only AEAD-wrapped association data. The wrapping key is supplied
// separately by a protected production key source or a test-only HIL source.
// NVS power-cut atomicity still requires physical qualification.
class NvsAssociationBlobStore final : public AssociationBlobStore {
public:
    bool read(Bytes& blob, bool& found) override;
    bool write(const Bytes& blob) override;
};

}  // namespace gs::security
