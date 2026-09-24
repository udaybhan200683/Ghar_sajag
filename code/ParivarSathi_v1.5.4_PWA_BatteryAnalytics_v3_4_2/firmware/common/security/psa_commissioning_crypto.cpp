#include "firmware/common/security/psa_commissioning_crypto.hpp"

#include <algorithm>
#include <utility>

// ESP-IDF 6.0.3's constant_time.h lacks an extern-C guard, although its
// implementation is C. Keep the C symbol name when this C++ provider links.
extern "C" {
#include "mbedtls/constant_time.h"
}
#include "mbedtls/platform_util.h"
#include "psa/crypto.h"

namespace gs::security {
namespace {
constexpr auto kP256 = PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_SECP_R1);
constexpr auto kP256Public = PSA_KEY_TYPE_ECC_PUBLIC_KEY(PSA_ECC_FAMILY_SECP_R1);
constexpr auto kEcdsaSha256 = PSA_ALG_ECDSA(PSA_ALG_SHA_256);

struct TemporaryKey {
    psa_key_id_t id{0};
    ~TemporaryKey() { if (id != 0) psa_destroy_key(id); }
    TemporaryKey() = default;
    TemporaryKey(const TemporaryKey&) = delete;
    TemporaryKey& operator=(const TemporaryKey&) = delete;
};

bool import_key(psa_key_type_t type, psa_key_usage_t usage, psa_algorithm_t algorithm,
                const std::uint8_t* bytes, std::size_t length, TemporaryKey& result) {
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, type);
    psa_set_key_bits(&attributes, (type == kP256 || type == kP256Public) ? 256 : length * 8);
    psa_set_key_usage_flags(&attributes, usage);
    psa_set_key_algorithm(&attributes, algorithm);
    const auto status = psa_import_key(&attributes, bytes, length, &result.id);
    psa_reset_key_attributes(&attributes);
    return status == PSA_SUCCESS;
}

bool hash(const Bytes& message, Key32& out) {
    std::size_t length = 0;
    return psa_hash_compute(PSA_ALG_SHA_256, message.data(), message.size(),
                            out.data(), out.size(), &length) == PSA_SUCCESS &&
           length == out.size();
}
}  // namespace

PsaCommissioningCrypto::PsaCommissioningCrypto(IdentitySigner& identities)
    : identities_(identities), ready_(psa_crypto_init() == PSA_SUCCESS) {}

bool PsaCommissioningCrypto::random_bytes(std::uint8_t* out, std::size_t length) {
    return ready_ && out != nullptr && psa_generate_random(out, length) == PSA_SUCCESS;
}

bool PsaCommissioningCrypto::identity_public_key(const std::string& reference,
                                                  P256PublicKey& out) {
    return ready_ && identities_.public_key(reference, out) && out[0] == 0x04;
}

bool PsaCommissioningCrypto::sign_identity(const std::string& reference,
                                            const Bytes& transcript, P256Signature& out) {
    Key32 digest{};
    const bool okay = ready_ && hash(transcript, digest) &&
                       identities_.sign_hash(reference, digest, out);
    mbedtls_platform_zeroize(digest.data(), digest.size());
    return okay;
}

bool PsaCommissioningCrypto::verify_identity(const P256PublicKey& public_key,
                                              const Bytes& transcript,
                                              const P256Signature& signature) {
    if (!ready_ || public_key[0] != 0x04) return false;
    TemporaryKey key;
    Key32 digest{};
    const bool okay = import_key(kP256Public, PSA_KEY_USAGE_VERIFY_HASH, kEcdsaSha256,
                                  public_key.data(), public_key.size(), key) &&
                       hash(transcript, digest) &&
                       psa_verify_hash(key.id, kEcdsaSha256, digest.data(), digest.size(),
                                       signature.data(), signature.size()) == PSA_SUCCESS;
    mbedtls_platform_zeroize(digest.data(), digest.size());
    return okay;
}

bool PsaCommissioningCrypto::generate_ephemeral(EphemeralP256& out) {
    if (!ready_) return false;
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, kP256);
    psa_set_key_bits(&attributes, 256);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_EXPORT | PSA_KEY_USAGE_DERIVE);
    psa_set_key_algorithm(&attributes, PSA_ALG_ECDH);
    TemporaryKey key;
    const auto status = psa_generate_key(&attributes, &key.id);
    psa_reset_key_attributes(&attributes);
    std::size_t private_length = 0, public_length = 0;
    const bool okay = status == PSA_SUCCESS &&
        psa_export_key(key.id, out.private_scalar.data(), out.private_scalar.size(),
                       &private_length) == PSA_SUCCESS &&
        psa_export_public_key(key.id, out.public_key.data(), out.public_key.size(),
                              &public_length) == PSA_SUCCESS &&
        private_length == out.private_scalar.size() &&
        public_length == out.public_key.size() && out.public_key[0] == 0x04;
    if (!okay) mbedtls_platform_zeroize(out.private_scalar.data(), out.private_scalar.size());
    return okay;
}

bool PsaCommissioningCrypto::derive_shared(const EphemeralP256& local,
                                            const P256PublicKey& remote, Key32& out) {
    if (!ready_ || remote[0] != 0x04) return false;
    TemporaryKey key;
    std::size_t length = 0;
    const bool okay = import_key(kP256, PSA_KEY_USAGE_DERIVE, PSA_ALG_ECDH,
                                  local.private_scalar.data(), local.private_scalar.size(), key) &&
                       psa_raw_key_agreement(PSA_ALG_ECDH, key.id,
                                             remote.data(), remote.size(),
                                             out.data(), out.size(), &length) == PSA_SUCCESS &&
                       length == out.size();
    if (!okay) mbedtls_platform_zeroize(out.data(), out.size());
    return okay;
}

bool PsaCommissioningCrypto::hkdf_sha256(const Key32& shared, const Bytes& salt,
                                          const Bytes& context, Key32& out) {
    if (!ready_) return false;
    psa_key_derivation_operation_t operation = PSA_KEY_DERIVATION_OPERATION_INIT;
    const bool okay =
        psa_key_derivation_setup(&operation, PSA_ALG_HKDF(PSA_ALG_SHA_256)) == PSA_SUCCESS &&
        psa_key_derivation_input_bytes(&operation, PSA_KEY_DERIVATION_INPUT_SALT,
                                       salt.data(), salt.size()) == PSA_SUCCESS &&
        psa_key_derivation_input_bytes(&operation, PSA_KEY_DERIVATION_INPUT_SECRET,
                                       shared.data(), shared.size()) == PSA_SUCCESS &&
        psa_key_derivation_input_bytes(&operation, PSA_KEY_DERIVATION_INPUT_INFO,
                                       context.data(), context.size()) == PSA_SUCCESS &&
        psa_key_derivation_output_bytes(&operation, out.data(), out.size()) == PSA_SUCCESS;
    psa_key_derivation_abort(&operation);
    if (!okay) mbedtls_platform_zeroize(out.data(), out.size());
    return okay;
}

bool PsaCommissioningCrypto::hmac_sha256(const Key32& key, const Bytes& message,
                                          Key32& out) {
    if (!ready_) return false;
    TemporaryKey imported;
    std::size_t length = 0;
    return import_key(PSA_KEY_TYPE_HMAC, PSA_KEY_USAGE_SIGN_MESSAGE,
                      PSA_ALG_HMAC(PSA_ALG_SHA_256), key.data(), key.size(), imported) &&
           psa_mac_compute(imported.id, PSA_ALG_HMAC(PSA_ALG_SHA_256),
                           message.data(), message.size(), out.data(), out.size(),
                           &length) == PSA_SUCCESS && length == out.size();
}

bool PsaCommissioningCrypto::constant_time_equal(const std::uint8_t* left,
                                                  const std::uint8_t* right,
                                                  std::size_t length) {
    return left != nullptr && right != nullptr &&
           mbedtls_ct_memcmp(left, right, length) == 0;
}

void PsaCommissioningCrypto::secure_zero(void* data, std::size_t length) {
    if (data != nullptr && length != 0) mbedtls_platform_zeroize(data, length);
}

bool PsaCommissioningCrypto::seal_aes256_gcm(const Key32& key, const Nonce12& nonce,
                                              const Bytes& aad, const Bytes& plain,
                                              Bytes& cipher, GcmTag& tag) {
    if (!ready_) return false;
    TemporaryKey imported;
    if (!import_key(PSA_KEY_TYPE_AES, PSA_KEY_USAGE_ENCRYPT, PSA_ALG_GCM,
                    key.data(), key.size(), imported)) return false;
    Bytes combined(plain.size() + tag.size());
    std::size_t length = 0;
    if (psa_aead_encrypt(imported.id, PSA_ALG_GCM, nonce.data(), nonce.size(),
                         aad.data(), aad.size(), plain.data(), plain.size(),
                         combined.data(), combined.size(), &length) != PSA_SUCCESS ||
        length != combined.size()) return false;
    cipher.assign(combined.begin(), combined.begin() + plain.size());
    std::copy(combined.begin() + plain.size(), combined.end(), tag.begin());
    return true;
}

bool PsaCommissioningCrypto::open_aes256_gcm(const Key32& key, const Nonce12& nonce,
                                              const Bytes& aad, const Bytes& cipher,
                                              const GcmTag& tag, Bytes& plain) {
    plain.clear();
    if (!ready_) return false;
    TemporaryKey imported;
    if (!import_key(PSA_KEY_TYPE_AES, PSA_KEY_USAGE_DECRYPT, PSA_ALG_GCM,
                    key.data(), key.size(), imported)) return false;
    Bytes combined(cipher);
    combined.insert(combined.end(), tag.begin(), tag.end());
    Bytes opened(cipher.size());
    std::size_t length = 0;
    if (psa_aead_decrypt(imported.id, PSA_ALG_GCM, nonce.data(), nonce.size(),
                         aad.data(), aad.size(), combined.data(), combined.size(),
                         opened.data(), opened.size(), &length) != PSA_SUCCESS ||
        length != cipher.size()) {
        mbedtls_platform_zeroize(opened.data(), opened.size());
        return false;
    }
    plain = std::move(opened);
    return true;
}

}  // namespace gs::security
