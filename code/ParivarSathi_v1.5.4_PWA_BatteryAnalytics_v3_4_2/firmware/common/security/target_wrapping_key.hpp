#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"

namespace gs::security {

// One random wrapping key per target, committed before use. In production the
// NVS partition is protected by hardware flash encryption; the current HIL
// profile is explicitly test-only and does not qualify key-at-rest security.
// Corrupt or unreadable existing state is never replaced automatically.
bool load_or_create_target_wrapping_key(CommissioningCrypto& crypto, Key32& out);

}  // namespace gs::security
