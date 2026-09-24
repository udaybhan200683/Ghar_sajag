#include "firmware/common/security/target_identity_signer.hpp"

#include "mbedtls/platform_util.h"
#include "nvs.h"
#include "sdkconfig.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <utility>

namespace gs::security {
namespace {
constexpr auto kP256 = PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_SECP_R1);
constexpr auto kEcdsaSha256 = PSA_ALG_ECDSA(PSA_ALG_SHA_256);

#if GS_HIL_BUILD
constexpr char kDevelopmentNamespace[] = "gs_dev_ident";
constexpr char kDevelopmentKey[] = "private_p256";

bool read_or_generate_development_scalar(std::array<std::uint8_t, 32>& scalar) {
    nvs_handle_t handle = 0;
    if (nvs_open(kDevelopmentNamespace, NVS_READWRITE, &handle) != ESP_OK) return false;
    std::size_t length = scalar.size();
    const auto read = nvs_get_blob(handle, kDevelopmentKey, scalar.data(), &length);
    if (read == ESP_OK) {
        nvs_close(handle);
        return length == scalar.size();
    }
    if (read != ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return false;  // Corruption must not silently replace an identity.
    }
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, kP256);
    psa_set_key_bits(&attributes, 256);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_EXPORT | PSA_KEY_USAGE_SIGN_HASH);
    psa_set_key_algorithm(&attributes, kEcdsaSha256);
    psa_key_id_t generated = 0;
    const auto created = psa_generate_key(&attributes, &generated);
    psa_reset_key_attributes(&attributes);
    length = 0;
    const bool exported = created == PSA_SUCCESS &&
        psa_export_key(generated, scalar.data(), scalar.size(), &length) == PSA_SUCCESS &&
        length == scalar.size();
    if (generated != 0) (void)psa_destroy_key(generated);
    if (!exported) {
        nvs_close(handle);
        return false;
    }
    const bool saved = nvs_set_blob(handle, kDevelopmentKey, scalar.data(),
                                     scalar.size()) == ESP_OK &&
                       nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    if (!saved) return false;
    nvs_handle_t verify = 0;
    if (nvs_open(kDevelopmentNamespace, NVS_READONLY, &verify) != ESP_OK) return false;
    std::array<std::uint8_t, 32> readback{};
    length = readback.size();
    const bool committed = nvs_get_blob(verify, kDevelopmentKey,
                                        readback.data(), &length) == ESP_OK &&
                           length == scalar.size() && readback == scalar;
    nvs_close(verify);
    mbedtls_platform_zeroize(readback.data(), readback.size());
    return committed;
}
#endif
}  // namespace

TargetIdentitySigner::TargetIdentitySigner(std::string reference,
                                           psa_key_id_t production_key_id)
    : reference_(std::move(reference)), production_key_id_(production_key_id) {}

TargetIdentitySigner::~TargetIdentitySigner() {
    if (key_ == 0) return;
#if GS_HIL_BUILD
    (void)psa_destroy_key(key_);
#endif
}

bool TargetIdentitySigner::initialize() {
    if (key_ != 0 || reference_.empty() || production_key_id_ == 0 ||
        psa_crypto_init() != PSA_SUCCESS) return false;
#if GS_HIL_BUILD
    std::array<std::uint8_t, 32> scalar{};
    const bool loaded = read_or_generate_development_scalar(scalar);
    if (!loaded) {
        mbedtls_platform_zeroize(scalar.data(), scalar.size());
        return false;
    }
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, kP256);
    psa_set_key_bits(&attributes, 256);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_SIGN_HASH | PSA_KEY_USAGE_EXPORT);
    psa_set_key_algorithm(&attributes, kEcdsaSha256);
    const auto imported = psa_import_key(&attributes, scalar.data(), scalar.size(), &key_);
    psa_reset_key_attributes(&attributes);
    mbedtls_platform_zeroize(scalar.data(), scalar.size());
    if (imported != PSA_SUCCESS) {
        key_ = 0;
        return false;
    }
#else
    // Persistent PSA storage alone is not evidence of protected key storage.
    // Manufacturing must enable both protections before this identity can be
    // used in a production runtime. Prototype/HIL boards are exempt only in
    // their compile-gated development profile.
#if !defined(CONFIG_SECURE_BOOT) || !defined(CONFIG_SECURE_FLASH_ENC_ENABLED)
    return false;
#endif
    // ESP-IDF 6.0.3 PSA accesses persistent keys by ID; psa_open_key() and
    // psa_close_key() are absent from its crypto API.
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    const bool provisioned =
        psa_get_key_attributes(production_key_id_, &attributes) == PSA_SUCCESS &&
        psa_get_key_type(&attributes) == kP256 &&
        psa_get_key_bits(&attributes) == 256 &&
        psa_get_key_algorithm(&attributes) == kEcdsaSha256 &&
        (psa_get_key_usage_flags(&attributes) & PSA_KEY_USAGE_SIGN_HASH) != 0 &&
        !PSA_KEY_LIFETIME_IS_VOLATILE(psa_get_key_lifetime(&attributes));
    psa_reset_key_attributes(&attributes);
    if (!provisioned) return false;
    key_ = production_key_id_;
#endif
    P256PublicKey checked{};
    if (!public_key(reference_, checked)) {
#if GS_HIL_BUILD
        (void)psa_destroy_key(key_);
#endif
        key_ = 0;
        return false;
    }
    return true;
}

bool TargetIdentitySigner::public_key(const std::string& reference,
                                       P256PublicKey& out) {
    if (key_ == 0 || reference != reference_) return false;
    std::size_t length = 0;
    return psa_export_public_key(key_, out.data(), out.size(), &length) == PSA_SUCCESS &&
           length == out.size() && out[0] == 0x04;
}

bool TargetIdentitySigner::sign_hash(const std::string& reference,
                                      const Key32& digest, P256Signature& out) {
    if (key_ == 0 || reference != reference_) return false;
    std::size_t length = 0;
    return psa_sign_hash(key_, kEcdsaSha256, digest.data(), digest.size(),
                         out.data(), out.size(), &length) == PSA_SUCCESS &&
           length == out.size();
}

}  // namespace gs::security
