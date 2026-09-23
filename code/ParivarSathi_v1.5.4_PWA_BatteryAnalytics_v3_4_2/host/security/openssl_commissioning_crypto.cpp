#include "host/security/openssl_commissioning_crypto.hpp"

#include <array>
#include <climits>
#include <memory>

#include <openssl/bn.h>
#include <openssl/crypto.h>
#include <openssl/core_names.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/kdf.h>
#include <openssl/param_build.h>
#include <openssl/rand.h>

namespace gs::host::security {
namespace {
using PKey = std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)>;
using PKeyCtx = std::unique_ptr<EVP_PKEY_CTX, decltype(&EVP_PKEY_CTX_free)>;
using MdCtx = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
using Bn = std::unique_ptr<BIGNUM, decltype(&BN_free)>;
using Signature = std::unique_ptr<ECDSA_SIG, decltype(&ECDSA_SIG_free)>;
using Params = std::unique_ptr<OSSL_PARAM, decltype(&OSSL_PARAM_free)>;
using ParamBuilder = std::unique_ptr<OSSL_PARAM_BLD, decltype(&OSSL_PARAM_BLD_free)>;
using Kdf = std::unique_ptr<EVP_KDF, decltype(&EVP_KDF_free)>;
using KdfCtx = std::unique_ptr<EVP_KDF_CTX, decltype(&EVP_KDF_CTX_free)>;
using Mac = std::unique_ptr<EVP_MAC, decltype(&EVP_MAC_free)>;
using MacCtx = std::unique_ptr<EVP_MAC_CTX, decltype(&EVP_MAC_CTX_free)>;
using CipherCtx = std::unique_ptr<EVP_CIPHER_CTX, decltype(&EVP_CIPHER_CTX_free)>;

PKey generate_p256() {
    PKeyCtx context(EVP_PKEY_CTX_new_from_name(nullptr, "EC", nullptr), EVP_PKEY_CTX_free);
    EVP_PKEY* raw = nullptr;
    if (!context || EVP_PKEY_keygen_init(context.get()) != 1 ||
        EVP_PKEY_CTX_set_group_name(context.get(), "prime256v1") != 1 ||
        EVP_PKEY_generate(context.get(), &raw) != 1) return {nullptr, EVP_PKEY_free};
    return {raw, EVP_PKEY_free};
}

bool export_public(EVP_PKEY* key, P256PublicKey& out) {
    std::size_t size = 0;
    return key != nullptr &&
           EVP_PKEY_get_octet_string_param(key, OSSL_PKEY_PARAM_PUB_KEY,
                                            out.data(), out.size(), &size) == 1 &&
           size == out.size() && out[0] == 0x04;
}

PKey import_p256(const P256PublicKey& public_key, const Key32* private_scalar = nullptr) {
    if (public_key[0] != 0x04) return {nullptr, EVP_PKEY_free};
    ParamBuilder builder(OSSL_PARAM_BLD_new(), OSSL_PARAM_BLD_free);
    Bn private_bn(nullptr, BN_free);
    if (!builder || OSSL_PARAM_BLD_push_utf8_string(builder.get(), OSSL_PKEY_PARAM_GROUP_NAME,
                                                    "prime256v1", 0) != 1 ||
        OSSL_PARAM_BLD_push_octet_string(builder.get(), OSSL_PKEY_PARAM_PUB_KEY,
                                         public_key.data(), public_key.size()) != 1)
        return {nullptr, EVP_PKEY_free};
    if (private_scalar != nullptr) {
        private_bn.reset(BN_bin2bn(private_scalar->data(), private_scalar->size(), nullptr));
        if (!private_bn || OSSL_PARAM_BLD_push_BN(builder.get(), OSSL_PKEY_PARAM_PRIV_KEY,
                                                  private_bn.get()) != 1)
            return {nullptr, EVP_PKEY_free};
    }
    Params params(OSSL_PARAM_BLD_to_param(builder.get()), OSSL_PARAM_free);
    PKeyCtx context(EVP_PKEY_CTX_new_from_name(nullptr, "EC", nullptr), EVP_PKEY_CTX_free);
    EVP_PKEY* raw = nullptr;
    if (!params || !context || EVP_PKEY_fromdata_init(context.get()) != 1 ||
        EVP_PKEY_fromdata(context.get(), &raw,
                          private_scalar == nullptr ? EVP_PKEY_PUBLIC_KEY : EVP_PKEY_KEYPAIR,
                          params.get()) != 1) return {nullptr, EVP_PKEY_free};
    return {raw, EVP_PKEY_free};
}

bool sign(EVP_PKEY* key, const Bytes& message, P256Signature& out) {
    MdCtx context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    if (!context || EVP_DigestSignInit(context.get(), nullptr, EVP_sha256(), nullptr, key) != 1)
        return false;
    std::size_t size = 0;
    if (EVP_DigestSign(context.get(), nullptr, &size, message.data(), message.size()) != 1)
        return false;
    Bytes der(size);
    if (EVP_DigestSign(context.get(), der.data(), &size, message.data(), message.size()) != 1)
        return false;
    const unsigned char* cursor = der.data();
    Signature signature(d2i_ECDSA_SIG(nullptr, &cursor, static_cast<long>(size)), ECDSA_SIG_free);
    if (!signature) return false;
    const BIGNUM* r = nullptr;
    const BIGNUM* s = nullptr;
    ECDSA_SIG_get0(signature.get(), &r, &s);
    return r != nullptr && s != nullptr &&
           BN_bn2binpad(r, out.data(), 32) == 32 &&
           BN_bn2binpad(s, out.data() + 32, 32) == 32;
}

bool verify(EVP_PKEY* key, const Bytes& message, const P256Signature& raw) {
    Signature signature(ECDSA_SIG_new(), ECDSA_SIG_free);
    Bn r(BN_bin2bn(raw.data(), 32, nullptr), BN_free);
    Bn s(BN_bin2bn(raw.data() + 32, 32, nullptr), BN_free);
    if (!signature || !r || !s || ECDSA_SIG_set0(signature.get(), r.get(), s.get()) != 1)
        return false;
    (void)r.release(); (void)s.release();
    const int size = i2d_ECDSA_SIG(signature.get(), nullptr);
    if (size <= 0) return false;
    Bytes der(static_cast<std::size_t>(size));
    unsigned char* cursor = der.data();
    if (i2d_ECDSA_SIG(signature.get(), &cursor) != size) return false;
    MdCtx context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    return context && EVP_DigestVerifyInit(context.get(), nullptr, EVP_sha256(), nullptr, key) == 1 &&
           EVP_DigestVerify(context.get(), der.data(), der.size(), message.data(), message.size()) == 1;
}
}  // namespace

bool OpenSslCommissioningCrypto::generate_test_identity(const std::string& reference) {
    if (reference.empty() || identities_.count(reference) != 0) return false;
    auto key = generate_p256();
    if (!key) return false;
    identities_.emplace(reference, std::move(key));
    return true;
}

bool OpenSslCommissioningCrypto::random_bytes(std::uint8_t* out, std::size_t length) {
    return out != nullptr && length <= INT_MAX &&
           RAND_bytes(out, static_cast<int>(length)) == 1;
}

bool OpenSslCommissioningCrypto::identity_public_key(const std::string& reference,
                                                       P256PublicKey& out) {
    const auto found = identities_.find(reference);
    return found != identities_.end() && export_public(found->second.get(), out);
}

bool OpenSslCommissioningCrypto::sign_identity(const std::string& reference,
                                                const Bytes& transcript,
                                                P256Signature& out) {
    const auto found = identities_.find(reference);
    return found != identities_.end() && sign(found->second.get(), transcript, out);
}

bool OpenSslCommissioningCrypto::verify_identity(const P256PublicKey& public_key,
                                                  const Bytes& transcript,
                                                  const P256Signature& signature) {
    auto key = import_p256(public_key);
    return key && verify(key.get(), transcript, signature);
}

bool OpenSslCommissioningCrypto::generate_ephemeral(EphemeralP256& out) {
    auto key = generate_p256();
    BIGNUM* raw = nullptr;
    Bn scalar(nullptr, BN_free);
    if (!key || !export_public(key.get(), out.public_key) ||
        EVP_PKEY_get_bn_param(key.get(), OSSL_PKEY_PARAM_PRIV_KEY, &raw) != 1)
        return false;
    scalar.reset(raw);
    return BN_bn2binpad(scalar.get(), out.private_scalar.data(),
                        out.private_scalar.size()) == static_cast<int>(out.private_scalar.size());
}

bool OpenSslCommissioningCrypto::derive_shared(const EphemeralP256& local,
                                                const P256PublicKey& remote, Key32& out) {
    auto own = import_p256(local.public_key, &local.private_scalar);
    auto peer = import_p256(remote);
    PKeyCtx context(own ? EVP_PKEY_CTX_new(own.get(), nullptr) : nullptr, EVP_PKEY_CTX_free);
    std::size_t size = out.size();
    return own && peer && context && EVP_PKEY_derive_init(context.get()) == 1 &&
           EVP_PKEY_derive_set_peer(context.get(), peer.get()) == 1 &&
           EVP_PKEY_derive(context.get(), out.data(), &size) == 1 && size == out.size();
}

bool OpenSslCommissioningCrypto::hkdf_sha256(const Key32& shared, const Bytes& salt,
                                              const Bytes& context, Key32& out) {
    Kdf kdf(EVP_KDF_fetch(nullptr, "HKDF", nullptr), EVP_KDF_free);
    KdfCtx kdf_context(kdf ? EVP_KDF_CTX_new(kdf.get()) : nullptr, EVP_KDF_CTX_free);
    if (!kdf_context) return false;
    std::array<OSSL_PARAM, 5> params{
        OSSL_PARAM_construct_utf8_string(OSSL_KDF_PARAM_DIGEST, const_cast<char*>("SHA256"), 0),
        OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_KEY,
                                          const_cast<std::uint8_t*>(shared.data()), shared.size()),
        OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_SALT,
                                          const_cast<std::uint8_t*>(salt.data()), salt.size()),
        OSSL_PARAM_construct_octet_string(OSSL_KDF_PARAM_INFO,
                                          const_cast<std::uint8_t*>(context.data()), context.size()),
        OSSL_PARAM_construct_end()
    };
    return EVP_KDF_derive(kdf_context.get(), out.data(), out.size(), params.data()) == 1;
}

bool OpenSslCommissioningCrypto::hmac_sha256(const Key32& key, const Bytes& message,
                                              Key32& out) {
    Mac mac(EVP_MAC_fetch(nullptr, "HMAC", nullptr), EVP_MAC_free);
    MacCtx context(mac ? EVP_MAC_CTX_new(mac.get()) : nullptr, EVP_MAC_CTX_free);
    if (!context) return false;
    std::array<OSSL_PARAM, 2> params{
        OSSL_PARAM_construct_utf8_string(OSSL_MAC_PARAM_DIGEST, const_cast<char*>("SHA256"), 0),
        OSSL_PARAM_construct_end()
    };
    std::size_t size = out.size();
    return EVP_MAC_init(context.get(), key.data(), key.size(), params.data()) == 1 &&
           EVP_MAC_update(context.get(), message.data(), message.size()) == 1 &&
           EVP_MAC_final(context.get(), out.data(), &size, out.size()) == 1 && size == out.size();
}

bool OpenSslCommissioningCrypto::constant_time_equal(const std::uint8_t* left,
                                                       const std::uint8_t* right,
                                                       std::size_t length) {
    return left != nullptr && right != nullptr && CRYPTO_memcmp(left, right, length) == 0;
}

void OpenSslCommissioningCrypto::secure_zero(void* data, std::size_t length) {
    if (data != nullptr && length != 0) OPENSSL_cleanse(data, length);
}

bool OpenSslCommissioningCrypto::seal_aes256_gcm(const Key32& key, const Nonce12& nonce,
                                                  const Bytes& aad, const Bytes& plain,
                                                  Bytes& cipher, GcmTag& tag) {
    if (plain.size() > INT_MAX || aad.size() > INT_MAX) return false;
    CipherCtx context(EVP_CIPHER_CTX_new(), EVP_CIPHER_CTX_free);
    if (!context || EVP_EncryptInit_ex(context.get(), EVP_aes_256_gcm(), nullptr,
                                       key.data(), nonce.data()) != 1) return false;
    int written = 0;
    if (!aad.empty() && EVP_EncryptUpdate(context.get(), nullptr, &written,
                                          aad.data(), static_cast<int>(aad.size())) != 1) return false;
    cipher.resize(plain.size() + 16);
    int total = 0;
    if (!plain.empty() && EVP_EncryptUpdate(context.get(), cipher.data(), &written,
                                            plain.data(), static_cast<int>(plain.size())) != 1) return false;
    total += written;
    if (EVP_EncryptFinal_ex(context.get(), cipher.data() + total, &written) != 1) return false;
    total += written;
    cipher.resize(static_cast<std::size_t>(total));
    return EVP_CIPHER_CTX_ctrl(context.get(), EVP_CTRL_GCM_GET_TAG,
                               tag.size(), tag.data()) == 1;
}

bool OpenSslCommissioningCrypto::open_aes256_gcm(const Key32& key, const Nonce12& nonce,
                                                  const Bytes& aad, const Bytes& cipher,
                                                  const GcmTag& tag, Bytes& plain) {
    if (cipher.size() > INT_MAX || aad.size() > INT_MAX) return false;
    CipherCtx context(EVP_CIPHER_CTX_new(), EVP_CIPHER_CTX_free);
    if (!context || EVP_DecryptInit_ex(context.get(), EVP_aes_256_gcm(), nullptr,
                                       key.data(), nonce.data()) != 1) return false;
    int written = 0;
    if (!aad.empty() && EVP_DecryptUpdate(context.get(), nullptr, &written,
                                          aad.data(), static_cast<int>(aad.size())) != 1) return false;
    plain.resize(cipher.size() + 16);
    int total = 0;
    if (!cipher.empty() && EVP_DecryptUpdate(context.get(), plain.data(), &written,
                                             cipher.data(), static_cast<int>(cipher.size())) != 1) return false;
    total += written;
    if (EVP_CIPHER_CTX_ctrl(context.get(), EVP_CTRL_GCM_SET_TAG,
                            tag.size(), const_cast<std::uint8_t*>(tag.data())) != 1 ||
        EVP_DecryptFinal_ex(context.get(), plain.data() + total, &written) != 1) {
        OPENSSL_cleanse(plain.data(), plain.size());
        plain.clear();
        return false;
    }
    total += written;
    plain.resize(static_cast<std::size_t>(total));
    return true;
}

}  // namespace gs::host::security
