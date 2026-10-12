#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"

namespace gs::security {

// Platform identity storage is deliberately separate from protocol crypto.
// Production implementations must sign without exporting the device private
// key. Development/HIL implementations must be marked test-only.
class IdentitySigner {
public:
    virtual ~IdentitySigner() = default;
    virtual bool public_key(const std::string& reference, P256PublicKey& out) = 0;
    virtual bool sign_hash(const std::string& reference, const Key32& sha256_hash,
                           P256Signature& out) = 0;
};

class PsaCommissioningCrypto final : public CommissioningCrypto {
public:
    explicit PsaCommissioningCrypto(IdentitySigner& identities);
    bool ready() const { return ready_; }
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
    void secure_zero(void* data, std::size_t length) override;
    bool seal_aes256_gcm(const Key32& key, const Nonce12& nonce,
                         const Bytes& aad, const Bytes& plain,
                         Bytes& cipher, GcmTag& tag) override;
    bool open_aes256_gcm(const Key32& key, const Nonce12& nonce,
                         const Bytes& aad, const Bytes& cipher,
                         const GcmTag& tag, Bytes& plain) override;

private:
    IdentitySigner& identities_;
    bool ready_{false};
};

}  // namespace gs::security
