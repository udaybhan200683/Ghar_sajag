#pragma once

#include "firmware/common/security/psa_commissioning_crypto.hpp"

#include "psa/crypto.h"

#include <string>

namespace gs::security {

// Production provisioning owns this persistent PSA key ID. This adapter never
// generates or exports a production private key. The HIL implementation uses
// explicitly test-only NVS storage so prototype boards need no eFuse changes.
class TargetIdentitySigner final : public IdentitySigner {
public:
    TargetIdentitySigner(std::string reference, psa_key_id_t production_key_id);
    ~TargetIdentitySigner() override;
    TargetIdentitySigner(const TargetIdentitySigner&) = delete;
    TargetIdentitySigner& operator=(const TargetIdentitySigner&) = delete;
    bool initialize();
    bool ready() const { return key_ != 0; }
    bool public_key(const std::string& reference, P256PublicKey& out) override;
    bool sign_hash(const std::string& reference, const Key32& digest,
                   P256Signature& out) override;

private:
    std::string reference_;
    psa_key_id_t production_key_id_{0};
    psa_key_id_t key_{0};
};

}  // namespace gs::security
