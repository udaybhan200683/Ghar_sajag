#include "cloud_trust_provider.hpp"

#include <algorithm>
#include <cstring>
#include <limits>
#include <utility>

#if defined(ESP_PLATFORM)
#include "nvs.h"
#include "nvs_flash.h"
#include "mbedtls/md.h"
#include "mbedtls/pk.h"
#include "mbedtls/x509_crt.h"
#include "mbedtls/oid.h"
#include "psa/crypto.h"
#else
#include <openssl/evp.h>
#include <openssl/pem.h>
#include <openssl/rand.h>
#include <openssl/rsa.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#endif

namespace gs::hub::target {
namespace {

bool safe_identifier(const std::string& value) {
    if (value.empty() || value.size() > 64) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
               (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.';
    });
}

bool valid_time_snapshot(Milliseconds requested_ms,
                         const TrustedHubTimeSnapshot& time) {
    return requested_ms > 0 && time.trusted &&
        time.monotonic_ms == requested_ms && time.utc_now > 0 &&
        time.boot_generation > 0;
}

bool all_zero(const std::array<std::uint8_t, 32>& nonce) {
    return std::all_of(nonce.begin(), nonce.end(),
                       [](std::uint8_t byte) { return byte == 0; });
}

void append_u64(std::vector<std::uint8_t>& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

bool read_u64(const std::vector<std::uint8_t>& in, std::size_t offset,
              std::uint64_t& value) {
    if (offset > in.size() || in.size() - offset < 8) return false;
    value = 0;
    for (std::size_t i = 0; i < 8; ++i)
        value = (value << 8) | in[offset + i];
    return true;
}

constexpr std::size_t kTimeProofSignedBytes = 72;
constexpr std::size_t kRsa3072SignatureBytes = 384;
constexpr std::size_t kTimeProofBytes = kTimeProofSignedBytes +
                                          kRsa3072SignatureBytes;

bool cloud_client_certificate_matches(const S3CloudTrustMaterial& material) {
    if (material.client_certificate_pem.empty() ||
        material.client_certificate_pem.size() > 8192) return false;
    std::array<unsigned char, 32> fingerprint{};
    bool valid = false;
#if defined(ESP_PLATFORM)
    mbedtls_x509_crt certificate;
    mbedtls_x509_crt_init(&certificate);
    const auto parse_status = mbedtls_x509_crt_parse(
        &certificate,
        reinterpret_cast<const unsigned char*>(material.client_certificate_pem.c_str()),
        material.client_certificate_pem.size() + 1);
    const auto* sha256 = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    const bool digest_valid = sha256 != nullptr && certificate.raw.p != nullptr &&
        mbedtls_md(sha256, certificate.raw.p, certificate.raw.len,
                   fingerprint.data()) == 0;
    bool client_auth = false;
    for (const auto* usage = &certificate.ext_key_usage;
         usage != nullptr && usage->buf.p != nullptr; usage = usage->next) {
        if (usage->buf.len == MBEDTLS_OID_SIZE(MBEDTLS_OID_CLIENT_AUTH) &&
            std::memcmp(usage->buf.p, MBEDTLS_OID_CLIENT_AUTH,
                        usage->buf.len) == 0)
            client_auth = true;
    }
    valid = parse_status == 0 && digest_valid && client_auth &&
        mbedtls_pk_can_do_psa(
            &certificate.pk, PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_SHA_256),
            PSA_KEY_USAGE_VERIFY_HASH) &&
        mbedtls_pk_get_bitlen(&certificate.pk) == 3072;
    mbedtls_x509_crt_free(&certificate);
#else
    BIO* input = BIO_new_mem_buf(material.client_certificate_pem.data(),
                                 static_cast<int>(material.client_certificate_pem.size()));
    X509* certificate = input == nullptr ? nullptr :
        PEM_read_bio_X509(input, nullptr, nullptr, nullptr);
    EVP_PKEY* key = certificate == nullptr ? nullptr : X509_get_pubkey(certificate);
    EXTENDED_KEY_USAGE* purposes = certificate == nullptr ? nullptr :
        static_cast<EXTENDED_KEY_USAGE*>(
            X509_get_ext_d2i(certificate, NID_ext_key_usage, nullptr, nullptr));
    bool client_auth = false;
    for (int i = 0; purposes != nullptr && i < sk_ASN1_OBJECT_num(purposes); ++i)
        client_auth = client_auth ||
            OBJ_obj2nid(sk_ASN1_OBJECT_value(purposes, i)) == NID_client_auth;
    unsigned int fingerprint_size = 0;
    const bool digest_valid = certificate != nullptr &&
        X509_digest(certificate, EVP_sha256(), fingerprint.data(),
                    &fingerprint_size) == 1 && fingerprint_size == fingerprint.size();
    valid = key != nullptr && EVP_PKEY_base_id(key) == EVP_PKEY_RSA &&
        EVP_PKEY_bits(key) == 3072 && client_auth && digest_valid;
    EXTENDED_KEY_USAGE_free(purposes);
    EVP_PKEY_free(key);
    X509_free(certificate);
    BIO_free(input);
#endif
    if (!valid) return false;
    static constexpr char kHex[] = "0123456789abcdef";
    std::string observed;
    observed.reserve(fingerprint.size() * 2);
    for (const auto byte : fingerprint) {
        observed.push_back(kHex[(byte >> 4) & 0x0f]);
        observed.push_back(kHex[byte & 0x0f]);
    }
    return observed == material.certificate_fingerprint_sha256;
}

#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
bool test_only_private_key_matches(const S3CloudTrustMaterial& material) {
    if (!material.test_only || material.test_only_client_private_key_pem.empty() ||
        material.test_only_client_private_key_pem.size() > 8192) return false;
#if defined(ESP_PLATFORM)
    mbedtls_x509_crt certificate;
    mbedtls_x509_crt_init(&certificate);
    const int cert_status = mbedtls_x509_crt_parse(
        &certificate,
        reinterpret_cast<const unsigned char*>(material.client_certificate_pem.c_str()),
        material.client_certificate_pem.size() + 1);
    mbedtls_pk_context private_key;
    mbedtls_pk_init(&private_key);
    const int key_status = mbedtls_pk_parse_key(
        &private_key,
        reinterpret_cast<const unsigned char*>(
            material.test_only_client_private_key_pem.c_str()),
        material.test_only_client_private_key_pem.size() + 1,
        nullptr, 0);
    const bool matches = cert_status == 0 && key_status == 0 &&
        mbedtls_pk_check_pair(&certificate.pk, &private_key) == 0;
    mbedtls_pk_free(&private_key);
    mbedtls_x509_crt_free(&certificate);
    return matches;
#else
    BIO* cert_input = BIO_new_mem_buf(material.client_certificate_pem.data(),
        static_cast<int>(material.client_certificate_pem.size()));
    X509* certificate = cert_input == nullptr ? nullptr :
        PEM_read_bio_X509(cert_input, nullptr, nullptr, nullptr);
    BIO* key_input = BIO_new_mem_buf(material.test_only_client_private_key_pem.data(),
        static_cast<int>(material.test_only_client_private_key_pem.size()));
    EVP_PKEY* private_key = key_input == nullptr ? nullptr :
        PEM_read_bio_PrivateKey(key_input, nullptr, nullptr, nullptr);
    EVP_PKEY* public_key = certificate == nullptr ? nullptr :
        X509_get_pubkey(certificate);
    const bool matches = public_key != nullptr && private_key != nullptr &&
        EVP_PKEY_base_id(private_key) == EVP_PKEY_RSA &&
        EVP_PKEY_bits(private_key) == 3072 && EVP_PKEY_eq(public_key, private_key) == 1;
    EVP_PKEY_free(public_key);
    EVP_PKEY_free(private_key);
    X509_free(certificate);
    BIO_free(key_input);
    BIO_free(cert_input);
    return matches;
#endif
}
#endif

}  // namespace

std::vector<std::uint8_t> encode_authenticated_time_proof_payload(
    const std::array<std::uint8_t, 32>& nonce,
    std::uint64_t boot_generation,
    const AuthenticatedTimeStatement& statement) {
    if (all_zero(nonce) || boot_generation == 0 ||
        statement.issued_at_utc <= 0 || statement.valid_from_utc <= 0 ||
        statement.valid_until_utc <= statement.issued_at_utc ||
        statement.valid_from_utc > statement.issued_at_utc)
        return {};
    std::vector<std::uint8_t> payload;
    payload.reserve(kTimeProofSignedBytes);
    payload.insert(payload.end(), {'G', 'S', 'T', 'P', 1, 1, 0, 0});
    append_u64(payload, boot_generation);
    payload.insert(payload.end(), nonce.begin(), nonce.end());
    append_u64(payload, static_cast<std::uint64_t>(statement.issued_at_utc));
    append_u64(payload, static_cast<std::uint64_t>(statement.valid_from_utc));
    append_u64(payload, static_cast<std::uint64_t>(statement.valid_until_utc));
    return payload.size() == kTimeProofSignedBytes ? payload : std::vector<std::uint8_t>{};
}

bool Rsa3072Sha256TimeProofVerifier::verify(
    const std::vector<std::uint8_t>& proof,
    const std::array<std::uint8_t, 32>& nonce,
    std::uint64_t boot_generation,
    AuthenticatedTimeStatement& statement) const {
    if (proof.size() != kTimeProofBytes || public_key_der_.empty() ||
        public_key_der_.size() > 2048 || boot_generation == 0 ||
        all_zero(nonce) || proof[0] != 'G' || proof[1] != 'S' ||
        proof[2] != 'T' || proof[3] != 'P' || proof[4] != 1 ||
        proof[5] != 1 || proof[6] != 0 || proof[7] != 0)
        return false;

    std::uint64_t proof_generation = 0, issued = 0, valid_from = 0, valid_until = 0;
    if (!read_u64(proof, 8, proof_generation) ||
        !read_u64(proof, 48, issued) || !read_u64(proof, 56, valid_from) ||
        !read_u64(proof, 64, valid_until) || proof_generation != boot_generation ||
        !std::equal(nonce.begin(), nonce.end(), proof.begin() + 16) ||
        issued == 0 || valid_from == 0 || valid_until <= issued ||
        valid_from > issued ||
        issued > static_cast<std::uint64_t>(std::numeric_limits<EpochSeconds>::max()) ||
        valid_from > static_cast<std::uint64_t>(std::numeric_limits<EpochSeconds>::max()) ||
        valid_until > static_cast<std::uint64_t>(std::numeric_limits<EpochSeconds>::max()))
        return false;

    bool signature_valid = false;
#if defined(ESP_PLATFORM)
    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    const auto parse_result = mbedtls_pk_parse_public_key(
        &key, public_key_der_.data(), public_key_der_.size());
    std::array<unsigned char, 32> digest{};
    const auto* sha256 = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    const bool digest_valid = sha256 != nullptr &&
        mbedtls_md(sha256, proof.data(), kTimeProofSignedBytes,
                   digest.data()) == 0;
    if (parse_result == 0 && mbedtls_pk_can_do_psa(
            &key, PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_SHA_256),
            PSA_KEY_USAGE_VERIFY_HASH) &&
        mbedtls_pk_get_bitlen(&key) == 3072 && digest_valid) {
        const auto verify_result = mbedtls_pk_verify(
            &key, MBEDTLS_MD_SHA256, digest.data(), digest.size(),
            proof.data() + kTimeProofSignedBytes, kRsa3072SignatureBytes);
        signature_valid = verify_result == 0;
    }
    mbedtls_pk_free(&key);
#else
    const unsigned char* der = public_key_der_.data();
    EVP_PKEY* key = d2i_PUBKEY(nullptr, &der,
                               static_cast<long>(public_key_der_.size()));
    if (key != nullptr && der == public_key_der_.data() + public_key_der_.size() &&
        EVP_PKEY_base_id(key) == EVP_PKEY_RSA && EVP_PKEY_bits(key) == 3072) {
        EVP_MD_CTX* context = EVP_MD_CTX_new();
        EVP_PKEY_CTX* key_context = nullptr;
        if (context != nullptr && EVP_DigestVerifyInit(
                context, &key_context, EVP_sha256(), nullptr, key) == 1 &&
            key_context != nullptr &&
            EVP_PKEY_CTX_set_rsa_padding(key_context, RSA_PKCS1_PADDING) == 1 &&
            EVP_DigestVerifyUpdate(context, proof.data(), kTimeProofSignedBytes) == 1 &&
            EVP_DigestVerifyFinal(context, proof.data() + kTimeProofSignedBytes,
                                  kRsa3072SignatureBytes) == 1)
            signature_valid = true;
        EVP_MD_CTX_free(context);
    }
    EVP_PKEY_free(key);
#endif
    if (!signature_valid) return false;

    AuthenticatedTimeStatement candidate;
    candidate.issued_at_utc = static_cast<EpochSeconds>(issued);
    candidate.valid_from_utc = static_cast<EpochSeconds>(valid_from);
    candidate.valid_until_utc = static_cast<EpochSeconds>(valid_until);
    statement = candidate;
    return true;
}

bool S3AuthenticatedTimeRandomSource::fill(std::uint8_t* output,
                                           std::size_t length) {
    if (output == nullptr || length == 0) return false;
#if defined(ESP_PLATFORM)
    if (psa_crypto_init() != PSA_SUCCESS) return false;
    return psa_generate_random(output, length) == PSA_SUCCESS;
#else
    if (length > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        return false;
    return RAND_bytes(output, static_cast<int>(length)) == 1;
#endif
}

#if defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE)
namespace {
AuthenticatedTimeRandomSource& compatibility_test_random() {
    static S3AuthenticatedTimeRandomSource random;
    return random;
}
}  // namespace

AuthenticatedHubTimeProvider::AuthenticatedHubTimeProvider(
    AuthenticatedTimeFloorStore& store,
    const AuthenticatedTimeProofVerifier& verifier,
    const S3HubMonotonicClock& clock,
    AuthenticatedTimeBootstrapPolicy policy)
    : AuthenticatedHubTimeProvider(store, verifier, compatibility_test_random(),
                                   clock, policy) {}

bool AuthenticatedHubTimeProvider::accept_authenticated_time(
    const std::vector<std::uint8_t>& proof,
    const std::array<std::uint8_t, 32>& nonce,
    Milliseconds challenge_started_monotonic_ms) {
    if (all_zero(nonce) || challenge_started_monotonic_ms <= 0) return false;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!started_ || monotonic_faulted_) return false;
        pending_challenge_ = {nonce, boot_generation_,
                              challenge_started_monotonic_ms};
        challenge_pending_ = true;
        test_only_fake_proof_pending_ = true;
    }
    return accept_authenticated_time(proof);
}
#endif

bool ProvisionedS3CloudTrust::valid_fingerprint(const std::string& value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(),
        [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        });
}

bool ProvisionedS3CloudTrust::valid_material(
    const S3CloudTrustMaterial& material) {
#if defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE) || \
    (defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD)
    if (!material.test_only) return false;
#else
    if (material.test_only) return false;
#endif
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    const bool test_software_key = material.test_only && material.ds_context == nullptr &&
        !material.key_custody_verified && test_only_private_key_matches(material);
    const bool hardware_ds_key = material.ds_context != nullptr &&
        material.key_custody_verified;
#else
    const bool test_software_key = false;
    const bool hardware_ds_key = material.ds_context != nullptr &&
        material.key_custody_verified;
#endif
    return material.authority_authenticated && material.authority_active &&
        !material.authority_revoked && material.authority_revision > 0 &&
        safe_identifier(material.binding.home_id) &&
        safe_identifier(material.binding.hub_device_id) &&
        material.binding.ownership_epoch > 0 &&
        safe_identifier(material.permanent_hub_id) &&
        material.permanent_hub_id == material.binding.hub_device_id &&
        valid_fingerprint(material.certificate_fingerprint_sha256) &&
        material.client_certificate_pem.size() <= 8192 &&
        material.client_certificate_pem.find(
            "-----BEGIN CERTIFICATE-----") == 0 &&
        material.client_certificate_pem.find(
            "-----END CERTIFICATE-----") != std::string::npos &&
        material.client_certificate_pem.find("PRIVATE KEY") == std::string::npos &&
        (hardware_ds_key || test_software_key) && material.rsa_bits == 3072 &&
        material.credential_generation > 0 &&
        material.credential_state == CloudCredentialState::Active &&
        material.credential_purpose == CloudCredentialPurpose::CloudTlsClient &&
        (test_software_key || material.key_custody_verified) &&
        cloud_client_certificate_matches(material);
}

bool ProvisionedS3CloudTrust::current_material(
    S3CloudTrustMaterial& material) const {
    std::lock_guard<std::mutex> lock(read_mutex_);
    S3CloudTrustMaterial candidate;
    if (!material_.current_material(candidate) || !valid_material(candidate))
        return false;
    material = std::move(candidate);
    return true;
}

bool ProvisionedS3CloudTrust::current_binding(CloudAuthorityBinding& binding) {
    S3CloudTrustMaterial material;
    if (!current_material(material)) return false;
    binding = material.binding;
    return true;
}

bool ProvisionedS3CloudTrust::trusted_hub_time(
    Milliseconds monotonic_ms, TrustedHubTimeSnapshot& time) {
    S3CloudTrustMaterial material;
    TrustedHubTimeSnapshot candidate;
    if (!current_material(material) ||
        !time_.trusted_hub_time(monotonic_ms, candidate) ||
        !valid_time_snapshot(monotonic_ms, candidate)) return false;
    time = candidate;
    return true;
}

bool ProvisionedS3CloudTrust::current_identity(CloudTlsIdentity& identity) {
    const auto now_ms = clock_.now_ms();
    TrustedHubTimeSnapshot trusted_time;
    S3CloudTrustMaterial material;
    if (now_ms <= 0 || !current_material(material) ||
        material.binding.hub_device_id != material.permanent_hub_id ||
        !trusted_hub_time(now_ms, trusted_time)) return false;

    // Re-read the complete generation after the time lookup. Transfer,
    // revocation, credential renewal, or replacement during composition must
    // fence the candidate rather than mix fields from two snapshots.
    S3CloudTrustMaterial current;
    if (!current_material(current) ||
        current.authority_revision != material.authority_revision ||
        current.credential_generation != material.credential_generation ||
        !(current.binding == material.binding) ||
        current.permanent_hub_id != material.permanent_hub_id ||
        current.certificate_fingerprint_sha256 != material.certificate_fingerprint_sha256 ||
        current.client_certificate_pem != material.client_certificate_pem ||
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
        current.test_only_client_private_key_pem != material.test_only_client_private_key_pem ||
#endif
        current.ds_context != material.ds_context ||
        current.credential_state != material.credential_state ||
        current.authority_revoked != material.authority_revoked ||
        current.test_only != material.test_only)
        return false;

    CloudTlsIdentity candidate;
    candidate.client_certificate_pem = material.client_certificate_pem;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    candidate.test_only_software_identity = material.test_only &&
        material.ds_context == nullptr;
    if (candidate.test_only_software_identity)
        candidate.test_only_client_private_key_pem = material.test_only_client_private_key_pem;
#endif
    candidate.ds_context = material.ds_context;
    candidate.rsa_bits = material.rsa_bits;
    candidate.purpose = CloudTlsIdentity::Purpose::CloudTlsClient;
    candidate.permanent_hub_id = material.permanent_hub_id;
    candidate.certificate_fingerprint_sha256 =
        material.certificate_fingerprint_sha256;
    candidate.credential_generation = material.credential_generation;
    candidate.trusted_utc_seconds = trusted_time.utc_now;
    candidate.trusted_monotonic_ms = trusted_time.monotonic_ms;
    candidate.trusted_time_boot_generation = trusted_time.boot_generation;
    identity = std::move(candidate);
    return true;
}

bool AuthenticatedHubTimeProvider::start() {
    std::lock_guard<std::mutex> lock(mutex_);
    ready_ = false;
    started_ = false;
    boot_generation_ = 0;
    utc_floor_ = 0;
    highest_monotonic_ms_ = 0;
    last_floor_checkpoint_monotonic_ms_ = 0;
    monotonic_faulted_ = false;
    accepted_monotonic_ms_ = 0;
    accepted_utc_ = 0;
    expires_monotonic_ms_ = 0;
    challenge_pending_ = false;
#if defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE)
    test_only_fake_proof_pending_ = false;
#endif
    have_last_nonce_ = false;
    last_nonce_.fill(0);

    std::uint64_t generation = 0;
    if (!store_.begin_boot(generation) || generation == 0) return false;
    EpochSeconds floor = 0;
    const auto floor_state = store_.read_floor(floor);
    if (floor_state == TrustedTimeFloorRead::Unavailable) return false;
    if (floor_state != TrustedTimeFloorRead::Valid || floor <= 0) floor = 0;
    const auto monotonic_now = clock_.now_ms();
    if (monotonic_now <= 0) return false;
    boot_generation_ = generation;
    utc_floor_ = floor;
    highest_monotonic_ms_ = monotonic_now;
    started_ = true;
    return true;
}

bool AuthenticatedHubTimeProvider::create_challenge(
    AuthenticatedTimeChallenge& challenge) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!started_ || monotonic_faulted_) return false;
    const auto now_ms = clock_.now_ms();
    if (now_ms <= 0 || now_ms < highest_monotonic_ms_) {
        monotonic_faulted_ = true;
        ready_ = false;
        challenge_pending_ = false;
        return false;
    }
    highest_monotonic_ms_ = now_ms;
    AuthenticatedTimeChallenge candidate;
    if (!random_.fill(candidate.nonce.data(), candidate.nonce.size()) ||
        all_zero(candidate.nonce) ||
        (have_last_nonce_ && candidate.nonce == last_nonce_)) {
        challenge_pending_ = false;
        return false;
    }
    candidate.boot_generation = boot_generation_;
    candidate.created_monotonic_ms = now_ms;
    pending_challenge_ = candidate;
    challenge_pending_ = true;
#if defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE)
    test_only_fake_proof_pending_ = false;
#endif
    challenge = candidate;
    return true;
}

bool AuthenticatedHubTimeProvider::accept_authenticated_time(
    const std::vector<std::uint8_t>& proof) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!started_ || monotonic_faulted_ || !challenge_pending_ ||
        policy_.max_response_age_ms <= 0 ||
        policy_.floor_checkpoint_interval_ms <= 0)
        return false;
    const auto challenge = pending_challenge_;
    challenge_pending_ = false;
    last_nonce_ = challenge.nonce;
    have_last_nonce_ = true;
#if defined(GS_CLOUD_TRUST_TEST_ONLY_FIXTURE)
    const bool fake_test_proof = test_only_fake_proof_pending_;
    test_only_fake_proof_pending_ = false;
    if ((!fake_test_proof && proof.size() != kTimeProofBytes) ||
        (fake_test_proof && (proof.empty() || proof.size() > 4096)) ||
        (!fake_test_proof && policy_.max_statement_validity_seconds == 0))
        return false;
#else
    constexpr bool fake_test_proof = false;
    if (proof.size() != kTimeProofBytes ||
        policy_.max_statement_validity_seconds == 0)
        return false;
#endif
    const auto now_ms = clock_.now_ms();
    if (now_ms <= 0 || now_ms < highest_monotonic_ms_) {
        monotonic_faulted_ = true;
        ready_ = false;
        return false;
    }
    highest_monotonic_ms_ = now_ms;
    if (challenge.boot_generation != boot_generation_ ||
        now_ms < challenge.created_monotonic_ms ||
        now_ms - challenge.created_monotonic_ms > policy_.max_response_age_ms)
        return false;

    AuthenticatedTimeStatement statement;
    if (!verifier_.verify(proof, challenge.nonce, challenge.boot_generation, statement) ||
        statement.issued_at_utc <= 0 || statement.valid_from_utc <= 0 ||
        statement.valid_until_utc <= statement.issued_at_utc ||
        statement.valid_from_utc > statement.issued_at_utc ||
        (!fake_test_proof &&
         static_cast<std::uint64_t>(statement.valid_until_utc - statement.issued_at_utc) >
            policy_.max_statement_validity_seconds))
        return false;

    if (statement.issued_at_utc < utc_floor_) return false;
    // Expiry disables trusted-time reads, but it does not erase the monotonic
    // lower bound while this boot's monotonic clock is still continuous.
    // Otherwise a delayed recovery response could roll the Hub back slightly
    // after the prior signed validity interval expired.
    if (accepted_monotonic_ms_ > 0) {
        if (now_ms < accepted_monotonic_ms_) return false;
        const auto elapsed_seconds =
            static_cast<EpochSeconds>((now_ms - accepted_monotonic_ms_) / 1000);
        if (accepted_utc_ > std::numeric_limits<EpochSeconds>::max() -
                elapsed_seconds ||
            statement.issued_at_utc < accepted_utc_ + elapsed_seconds)
            return false;
    }
    ready_ = false;

    const auto validity_seconds =
        statement.valid_until_utc - statement.issued_at_utc;
    if (validity_seconds >
        (std::numeric_limits<Milliseconds>::max() - now_ms) / 1000)
        return false;
    const auto expires_ms = now_ms + validity_seconds * 1000;
    const auto new_floor = std::max(utc_floor_, statement.issued_at_utc);
    if (!store_.commit_floor(new_floor)) {
        ready_ = false;
        return false;
    }

    utc_floor_ = new_floor;
    accepted_monotonic_ms_ = now_ms;
    accepted_utc_ = statement.issued_at_utc;
    last_floor_checkpoint_monotonic_ms_ = now_ms;
    expires_monotonic_ms_ = expires_ms;
    ready_ = true;
    return true;
}

bool AuthenticatedHubTimeProvider::trusted_hub_time(
    Milliseconds monotonic_ms, TrustedHubTimeSnapshot& time) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!started_ || monotonic_faulted_ || monotonic_ms <= 0) return false;
    const auto actual_now_ms = clock_.now_ms();
    if (actual_now_ms <= 0 || actual_now_ms < highest_monotonic_ms_ ||
        monotonic_ms < highest_monotonic_ms_ || actual_now_ms < monotonic_ms) {
        monotonic_faulted_ = true;
        ready_ = false;
        return false;
    }
    highest_monotonic_ms_ = actual_now_ms;
    if (!ready_ || monotonic_ms < accepted_monotonic_ms_ ||
        actual_now_ms < accepted_monotonic_ms_ ||
        actual_now_ms > expires_monotonic_ms_) return false;

    const auto elapsed_seconds =
        static_cast<EpochSeconds>((monotonic_ms - accepted_monotonic_ms_) / 1000);
    if (accepted_utc_ > std::numeric_limits<EpochSeconds>::max() -
            elapsed_seconds) return false;
    const auto utc_now = accepted_utc_ + elapsed_seconds;
    if (utc_now < utc_floor_) return false;

    if (actual_now_ms - last_floor_checkpoint_monotonic_ms_ >=
        policy_.floor_checkpoint_interval_ms) {
        const auto checkpoint_elapsed_seconds =
            static_cast<EpochSeconds>((actual_now_ms - accepted_monotonic_ms_) / 1000);
        if (accepted_utc_ > std::numeric_limits<EpochSeconds>::max() -
                checkpoint_elapsed_seconds) return false;
        const auto checkpoint_floor = std::max(
            utc_floor_, accepted_utc_ + checkpoint_elapsed_seconds);
        if (!store_.commit_floor(checkpoint_floor)) {
            ready_ = false;
            return false;
        }
        utc_floor_ = checkpoint_floor;
        last_floor_checkpoint_monotonic_ms_ = actual_now_ms;
        if (utc_now < utc_floor_) return false;
    }

    TrustedHubTimeSnapshot candidate;
    candidate.trusted = true;
    candidate.monotonic_ms = monotonic_ms;
    candidate.utc_now = utc_now;
    candidate.boot_generation = boot_generation_;
    time = candidate;
    return true;
}

std::uint64_t AuthenticatedHubTimeProvider::boot_generation() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return boot_generation_;
}

#if defined(ESP_PLATFORM)
bool NvsAuthenticatedTimeFloorStore::valid_namespace(
    const std::string& name_space) {
    return !name_space.empty() && name_space.size() <= 15 &&
        std::all_of(name_space.begin(), name_space.end(),
            [](unsigned char ch) {
                return (ch >= 'a' && ch <= 'z') ||
                       (ch >= 'A' && ch <= 'Z') ||
                       (ch >= '0' && ch <= '9') || ch == '_';
            });
}

bool NvsAuthenticatedTimeFloorStore::begin_boot(
    std::uint64_t& boot_generation) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!valid_namespace(namespace_)) return false;
    nvs_handle_t handle{};
    if (nvs_open(namespace_.c_str(), NVS_READWRITE, &handle) != ESP_OK)
        return false;
    std::uint64_t previous = 0;
    const auto read_status = nvs_get_u64(handle, "boot_gen", &previous);
    if (read_status != ESP_OK && read_status != ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return false;
    }
    if (previous == std::numeric_limits<std::uint64_t>::max()) {
        nvs_close(handle);
        return false;
    }
    const auto next = previous + 1;
    const auto set_status = nvs_set_u64(handle, "boot_gen", next);
    const auto commit_status = set_status == ESP_OK ? nvs_commit(handle) : set_status;
    nvs_close(handle);
    if (commit_status != ESP_OK) return false;
    boot_generation = next;
    return true;
}

TrustedTimeFloorRead NvsAuthenticatedTimeFloorStore::read_floor(
    EpochSeconds& utc_floor) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!valid_namespace(namespace_)) return TrustedTimeFloorRead::Unavailable;
    nvs_handle_t handle{};
    const auto open_status = nvs_open(namespace_.c_str(), NVS_READONLY, &handle);
    if (open_status == ESP_ERR_NVS_NOT_FOUND) return TrustedTimeFloorRead::Missing;
    if (open_status != ESP_OK) return TrustedTimeFloorRead::Unavailable;
    std::uint64_t stored = 0;
    const auto read_status = nvs_get_u64(handle, "utc_floor", &stored);
    nvs_close(handle);
    if (read_status == ESP_ERR_NVS_NOT_FOUND) return TrustedTimeFloorRead::Missing;
    if (read_status != ESP_OK) return TrustedTimeFloorRead::Unavailable;
    if (stored == 0 || stored > static_cast<std::uint64_t>(
            std::numeric_limits<EpochSeconds>::max()))
        return TrustedTimeFloorRead::Corrupt;
    utc_floor = static_cast<EpochSeconds>(stored);
    return TrustedTimeFloorRead::Valid;
}

bool NvsAuthenticatedTimeFloorStore::commit_floor(EpochSeconds utc_floor) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!valid_namespace(namespace_) || utc_floor <= 0) return false;
    nvs_handle_t handle{};
    if (nvs_open(namespace_.c_str(), NVS_READWRITE, &handle) != ESP_OK)
        return false;
    std::uint64_t current = 0;
    const auto read_status = nvs_get_u64(handle, "utc_floor", &current);
    if ((read_status != ESP_OK && read_status != ESP_ERR_NVS_NOT_FOUND) ||
        (read_status == ESP_OK && static_cast<std::uint64_t>(utc_floor) < current)) {
        nvs_close(handle);
        return false;
    }
    const auto set_status = nvs_set_u64(
        handle, "utc_floor", static_cast<std::uint64_t>(utc_floor));
    const auto commit_status = set_status == ESP_OK ? nvs_commit(handle) : set_status;
    nvs_close(handle);
    return commit_status == ESP_OK;
}
#endif

}  // namespace gs::hub::target
