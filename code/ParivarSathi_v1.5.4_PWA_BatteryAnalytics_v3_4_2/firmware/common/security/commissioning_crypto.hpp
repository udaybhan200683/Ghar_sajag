#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace gs::security {

using Bytes = std::vector<std::uint8_t>;
using Key32 = std::array<std::uint8_t, 32>;
using Nonce12 = std::array<std::uint8_t, 12>;
using P256PublicKey = std::array<std::uint8_t, 65>;
using P256Signature = std::array<std::uint8_t, 64>;
using GcmTag = std::array<std::uint8_t, 16>;

struct EphemeralP256 {
    Key32 private_scalar{};
    P256PublicKey public_key{};
};

// All methods fail closed. Private factory identities are addressed by a
// storage reference and are never serialized into a commissioning packet.
// Development and target backends must use reviewed crypto libraries.
class CommissioningCrypto {
public:
    virtual ~CommissioningCrypto() = default;
    virtual bool random_bytes(std::uint8_t* out, std::size_t length) = 0;
    virtual bool identity_public_key(const std::string& reference, P256PublicKey& out) = 0;
    virtual bool sign_identity(const std::string& reference, const Bytes& transcript,
                               P256Signature& out) = 0;
    virtual bool verify_identity(const P256PublicKey& public_key, const Bytes& transcript,
                                 const P256Signature& signature) = 0;
    virtual bool generate_ephemeral(EphemeralP256& out) = 0;
    virtual bool derive_shared(const EphemeralP256& local, const P256PublicKey& remote,
                               Key32& out) = 0;
    virtual bool hkdf_sha256(const Key32& shared, const Bytes& salt,
                             const Bytes& context, Key32& out) = 0;
    virtual bool hmac_sha256(const Key32& key, const Bytes& message, Key32& out) = 0;
    virtual bool constant_time_equal(const std::uint8_t* left,
                                     const std::uint8_t* right, std::size_t length) = 0;
    virtual bool seal_aes256_gcm(const Key32& key, const Nonce12& nonce,
                                 const Bytes& aad, const Bytes& plain,
                                 Bytes& cipher, GcmTag& tag) = 0;
    virtual bool open_aes256_gcm(const Key32& key, const Nonce12& nonce,
                                 const Bytes& aad, const Bytes& cipher,
                                 const GcmTag& tag, Bytes& plain) = 0;
};

}  // namespace gs::security
