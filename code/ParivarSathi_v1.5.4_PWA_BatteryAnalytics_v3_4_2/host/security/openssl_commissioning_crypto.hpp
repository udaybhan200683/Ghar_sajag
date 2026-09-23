#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"

#include <map>
#include <memory>
#include <string>

#include <openssl/evp.h>

namespace gs::host::security {

using gs::security::Bytes;
using gs::security::EphemeralP256;
using gs::security::GcmTag;
using gs::security::Key32;
using gs::security::Nonce12;
using gs::security::P256PublicKey;
using gs::security::P256Signature;

// Host qualification backend. Identities are generated in process and never
// written to source, fixtures or reports. This is not production key storage.
class OpenSslCommissioningCrypto final : public gs::security::CommissioningCrypto {
public:
    bool generate_test_identity(const std::string& reference);
    bool random_bytes(std::uint8_t* out, std::size_t length) override;
    bool identity_public_key(const std::string& reference, P256PublicKey& out) override;
    bool sign_identity(const std::string& reference, const Bytes& transcript,
                       P256Signature& out) override;
    bool verify_identity(const P256PublicKey& public_key, const Bytes& transcript,
                         const P256Signature& signature) override;
    bool generate_ephemeral(EphemeralP256& out) override;
    bool derive_shared(const EphemeralP256& local, const P256PublicKey& remote,
                       Key32& out) override;
    bool hkdf_sha256(const Key32& shared, const Bytes& salt,
                     const Bytes& context, Key32& out) override;
    bool hmac_sha256(const Key32& key, const Bytes& message, Key32& out) override;
    bool constant_time_equal(const std::uint8_t* left,
                             const std::uint8_t* right, std::size_t length) override;
    bool seal_aes256_gcm(const Key32& key, const Nonce12& nonce,
                         const Bytes& aad, const Bytes& plain,
                         Bytes& cipher, GcmTag& tag) override;
    bool open_aes256_gcm(const Key32& key, const Nonce12& nonce,
                         const Bytes& aad, const Bytes& cipher,
                         const GcmTag& tag, Bytes& plain) override;

private:
    std::map<std::string, std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)>> identities_;
};

}  // namespace gs::host::security
