#include "gs40_test_only_bootstrap.hpp"
#include "firmware/hub/lifecycle/configuration/config_service.hpp"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <limits>
#include <utility>

#if defined(ESP_PLATFORM)
#include "esp_timer.h"
#include "mbedtls/md.h"
#include "mbedtls/pk.h"
#include "mbedtls/oid.h"
#include "mbedtls/x509_crt.h"
#include "psa/crypto.h"
#else
#include <openssl/core_names.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/kdf.h>
#include <openssl/param_build.h>
#include <openssl/pem.h>
#include <openssl/rand.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#include <openssl/sha.h>
#endif

namespace gs::hub::target {
namespace {
constexpr std::size_t kHeaderBytes = 116;
constexpr std::size_t kTagBytes = 16;
constexpr std::size_t kSignatureBytes = 384;
constexpr char kConfigDomain[] = "GS40T/1/CONFIG\0";
constexpr char kKdfInfo[] = "GS40T/1/CONFIG/AES256GCM\0";
constexpr char kAuthorityDomain[] = "GS40T/1/AUTHORITY\0";

void clear_string(std::string& value) {
    volatile char* bytes = value.empty() ? nullptr : value.data();
    for (std::size_t i = 0; i < value.size(); ++i) bytes[i] = 0;
    value.clear();
}

bool valid_ascii(const std::string& value, std::size_t maximum) {
    return !value.empty() && value.size() <= maximum &&
        std::all_of(value.begin(), value.end(), [](unsigned char ch) {
            return ch >= 0x21 && ch <= 0x7e;
        });
}

bool supported_household_timezone(const std::string& value) {
    return value == "Etc/UTC" || value == "Asia/Kolkata";
}

bool valid_hostname(const std::string& value) {
    if (value.empty() || value.size() > 253 || value.front() == '.' || value.back() == '.') return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
            (ch >= '0' && ch <= '9') || ch == '-' || ch == '.';
    });
}

// TEST_ONLY destinations: synthetic DNS names, loopback or RFC1918 IPv4.
// Exact hostname/CA authentication still applies; redirects are never accepted.
bool isolated_destination(const std::string& host) {
    if (host == "localhost" || (host.size() > 5 && host.compare(host.size()-5, 5, ".test") == 0))
        return valid_hostname(host);
    unsigned octets[4]{}; std::size_t at = 0;
    for (unsigned i = 0; i < 4; ++i) {
        const auto begin = at;
        while (at < host.size() && host[at] >= '0' && host[at] <= '9') {
            if (at-begin >= 3) return false;
            octets[i] = octets[i]*10 + static_cast<unsigned>(host[at++]-'0');
        }
        if (at == begin || octets[i] > 255 || (at-begin > 1 && host[begin] == '0')) return false;
        if (i < 3 && (at >= host.size() || host[at++] != '.')) return false;
    }
    return at == host.size() && (octets[0] == 127 || octets[0] == 10 ||
        (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31) ||
        (octets[0] == 192 && octets[1] == 168));
}

bool valid_backend_port(const std::string& authority, const std::string& host) {
    if (authority == host) return true;
    if (authority.size() <= host.size()+1 || authority[host.size()] != ':') return false;
    unsigned port = 0;
    for (std::size_t i = host.size()+1; i < authority.size(); ++i) {
        if (authority[i] < '0' || authority[i] > '9' || port > 6553) return false;
        port = port*10 + static_cast<unsigned>(authority[i]-'0');
    }
    return port > 0 && port <= 65535;
}

std::string hex_bytes(const std::uint8_t* bytes, std::size_t size) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(size * 2);
    for (std::size_t i = 0; i < size; ++i) {
        result.push_back(digits[bytes[i] >> 4]);
        result.push_back(digits[bytes[i] & 0x0f]);
    }
    return result;
}

#if defined(ESP_PLATFORM)
bool sha256_concat(const char* domain, std::size_t domain_size,
                   const std::uint8_t* bytes, std::size_t size,
                   std::array<unsigned char, 32>& digest) {
    if ((domain == nullptr && domain_size != 0) ||
        (bytes == nullptr && size != 0) || size > 24576) return false;
    std::vector<unsigned char> input;
    input.reserve(domain_size + size);
    if (domain_size != 0)
        input.insert(input.end(), domain, domain + domain_size);
    if (size != 0) input.insert(input.end(), bytes, bytes + size);
    const auto* sha256 = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    return sha256 != nullptr &&
        mbedtls_md(sha256, input.data(), input.size(), digest.data()) == 0;
}
#endif

bool valid_tls_identity(const std::string& certificate_pem,
                        const std::string& private_key_pem,
                        const std::string& fingerprint) {
#if defined(ESP_PLATFORM)
    mbedtls_x509_crt certificate;
    mbedtls_x509_crt_init(&certificate);
    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    const auto rsa_sha256 = PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_SHA_256);
    bool valid = mbedtls_x509_crt_parse(&certificate,
            reinterpret_cast<const unsigned char*>(certificate_pem.c_str()),
            certificate_pem.size() + 1) == 0 &&
        mbedtls_pk_parse_key(&key,
            reinterpret_cast<const unsigned char*>(private_key_pem.c_str()),
            private_key_pem.size() + 1, nullptr, 0) == 0 &&
        mbedtls_pk_get_bitlen(&certificate.pk) == 3072 &&
        mbedtls_pk_get_bitlen(&key) == 3072 &&
        mbedtls_pk_can_do_psa(&certificate.pk, rsa_sha256, PSA_KEY_USAGE_VERIFY_HASH) &&
        mbedtls_pk_can_do_psa(&key, rsa_sha256, PSA_KEY_USAGE_SIGN_HASH) &&
        mbedtls_pk_check_pair(&certificate.pk, &key) == 0;
    bool client_auth = false;
    for (const mbedtls_x509_sequence* item = &certificate.ext_key_usage;
         valid && item != nullptr && item->buf.p != nullptr; item = item->next) {
        if (item->buf.len == MBEDTLS_OID_SIZE(MBEDTLS_OID_CLIENT_AUTH) &&
            std::memcmp(item->buf.p, MBEDTLS_OID_CLIENT_AUTH, item->buf.len) == 0)
            client_auth = true;
    }
    std::array<unsigned char, 32> digest{};
    if (valid && client_auth && certificate.raw.p != nullptr && certificate.raw.len > 0) {
        const auto* sha256 = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
        valid = sha256 != nullptr &&
            mbedtls_md(sha256, certificate.raw.p, certificate.raw.len,
                       digest.data()) == 0;
        valid = valid && hex_bytes(digest.data(), digest.size()) == fingerprint;
    } else {
        valid = false;
    }
    mbedtls_pk_free(&key);
    mbedtls_x509_crt_free(&certificate);
    return valid;
#else
    BIO* cert_bio = BIO_new_mem_buf(certificate_pem.data(), static_cast<int>(certificate_pem.size()));
    BIO* key_bio = BIO_new_mem_buf(private_key_pem.data(), static_cast<int>(private_key_pem.size()));
    X509* certificate = cert_bio == nullptr ? nullptr : PEM_read_bio_X509(cert_bio, nullptr, nullptr, nullptr);
    EVP_PKEY* key = key_bio == nullptr ? nullptr : PEM_read_bio_PrivateKey(key_bio, nullptr, nullptr, nullptr);
    unsigned char* der = nullptr;
    const int der_size = certificate == nullptr ? -1 : i2d_X509(certificate, &der);
    std::array<unsigned char, 32> digest{};
    bool client_auth = false;
    if (certificate != nullptr) {
        auto* usages = static_cast<EXTENDED_KEY_USAGE*>(
            X509_get_ext_d2i(certificate, NID_ext_key_usage, nullptr, nullptr));
        if (usages != nullptr) {
            for (int i = 0; i < sk_ASN1_OBJECT_num(usages); ++i) {
                if (OBJ_obj2nid(sk_ASN1_OBJECT_value(usages, i)) == NID_client_auth)
                    client_auth = true;
            }
        }
        EXTENDED_KEY_USAGE_free(usages);
    }
    const bool valid = certificate != nullptr && key != nullptr && der_size > 0 &&
        EVP_PKEY_base_id(X509_get0_pubkey(certificate)) == EVP_PKEY_RSA &&
        EVP_PKEY_bits(X509_get0_pubkey(certificate)) == 3072 && EVP_PKEY_bits(key) == 3072 &&
        X509_check_private_key(certificate, key) == 1 && client_auth &&
        SHA256(der, static_cast<std::size_t>(der_size), digest.data()) != nullptr &&
        hex_bytes(digest.data(), digest.size()) == fingerprint;
    OPENSSL_free(der);
    EVP_PKEY_free(key);
    X509_free(certificate);
    BIO_free(key_bio);
    BIO_free(cert_bio);
    return valid;
#endif
}

bool valid_rsa3072_public_der(const std::vector<std::uint8_t>& der) {
    if (der.empty() || der.size() > 2048) return false;
#if defined(ESP_PLATFORM)
    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    const bool valid = mbedtls_pk_parse_public_key(&key, der.data(), der.size()) == 0 &&
        mbedtls_pk_get_bitlen(&key) == 3072 &&
        mbedtls_pk_can_do_psa(&key, PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_SHA_256),
                              PSA_KEY_USAGE_VERIFY_HASH);
    mbedtls_pk_free(&key);
    return valid;
#else
    const unsigned char* cursor = der.data();
    EVP_PKEY* key = d2i_PUBKEY(nullptr, &cursor, static_cast<long>(der.size()));
    const bool valid = key != nullptr && cursor == der.data() + der.size() &&
        EVP_PKEY_base_id(key) == EVP_PKEY_RSA && EVP_PKEY_bits(key) == 3072;
    EVP_PKEY_free(key);
    return valid;
#endif
}

bool read_u16(const std::vector<std::uint8_t>& in, std::size_t offset,
              std::uint16_t& out) {
    if (offset + 2 > in.size()) return false;
    out = static_cast<std::uint16_t>((in[offset] << 8) | in[offset + 1]);
    return true;
}

bool read_u64(const std::vector<std::uint8_t>& in, std::size_t offset,
              std::uint64_t& out) {
    if (offset + 8 > in.size()) return false;
    out = 0;
    for (unsigned i = 0; i < 8; ++i) out = (out << 8) | in[offset + i];
    return true;
}

bool read_rule_u16(const std::uint8_t* bytes, std::size_t size,
                   std::size_t& offset, std::uint16_t& value) {
    if (offset + 2 > size) return false;
    value = static_cast<std::uint16_t>((bytes[offset] << 8) | bytes[offset + 1]);
    offset += 2;
    return true;
}

bool read_rule_u32(const std::uint8_t* bytes, std::size_t size,
                   std::size_t& offset, std::uint32_t& value) {
    if (offset + 4 > size) return false;
    value = (static_cast<std::uint32_t>(bytes[offset]) << 24) |
        (static_cast<std::uint32_t>(bytes[offset + 1]) << 16) |
        (static_cast<std::uint32_t>(bytes[offset + 2]) << 8) | bytes[offset + 3];
    offset += 4;
    return true;
}

bool read_rule_location(const std::uint8_t* bytes, std::size_t size,
                        std::size_t& offset, std::string& value) {
    if (offset >= size) return false;
    const auto length = bytes[offset++];
    if (length == 0 || length > 32 || offset + length > size) return false;
    value.assign(reinterpret_cast<const char*>(bytes + offset), length);
    offset += length;
    return valid_ascii(value, 32) && std::all_of(value.begin(), value.end(),
        [](unsigned char ch) {
            return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
                (ch >= '0' && ch <= '9') || ch == '-' || ch == '_';
        });
}

bool parse_activity_rule_config(const std::uint8_t* bytes, std::size_t size,
                                ActivityRuleConfig& rules) {
    // AR1 is a compact, versioned representation of the existing deterministic
    // ActivityRuleConfig. It carries no algorithm or alternate rule engine.
    if (bytes == nullptr || size < 40 || size > 512 ||
        std::memcmp(bytes, "AR1", 3) != 0 || (bytes[3] & 0xe0U) != 0) return false;
    const auto flags = bytes[3];
    std::size_t offset = 4;
    rules.quiet_hours_enabled = (flags & 1U) != 0;
    rules.daytime_inactivity_enabled = (flags & 2U) != 0;
    rules.morning_sequence_enabled = (flags & 4U) != 0;
    rules.night_activity_enabled = (flags & 8U) != 0;
    rules.post_door_inactivity_enabled = (flags & 16U) != 0;
    std::uint32_t door_timeout = 0, daytime_timeout = 0, morning_window = 0;
    std::uint32_t night_merge = 0, post_door_timeout = 0;
    if (!read_rule_u16(bytes, size, offset, rules.quiet_start_minute) ||
        !read_rule_u16(bytes, size, offset, rules.quiet_end_minute) ||
        !read_rule_u32(bytes, size, offset, door_timeout) ||
        !read_rule_u16(bytes, size, offset, rules.daytime_start_minute) ||
        !read_rule_u16(bytes, size, offset, rules.daytime_end_minute) ||
        !read_rule_u32(bytes, size, offset, daytime_timeout) ||
        !read_rule_u16(bytes, size, offset, rules.morning_start_minute) ||
        !read_rule_u16(bytes, size, offset, rules.morning_end_minute) ||
        !read_rule_u32(bytes, size, offset, morning_window) ||
        !read_rule_location(bytes, size, offset, rules.morning_bedroom_location) ||
        !read_rule_location(bytes, size, offset, rules.morning_bathroom_location) ||
        !read_rule_location(bytes, size, offset, rules.morning_kitchen_location) ||
        !read_rule_u16(bytes, size, offset, rules.night_start_minute) ||
        !read_rule_u16(bytes, size, offset, rules.night_end_minute) ||
        !read_rule_location(bytes, size, offset, rules.night_bathroom_location) ||
        !read_rule_u16(bytes, size, offset, rules.night_bathroom_visit_threshold) ||
        !read_rule_location(bytes, size, offset, rules.night_common_location) ||
        !read_rule_u16(bytes, size, offset, rules.night_common_visit_threshold) ||
        !read_rule_u32(bytes, size, offset, night_merge) ||
        !read_rule_u32(bytes, size, offset, post_door_timeout) || offset != size)
        return false;
    rules.door_open_timeout_seconds = door_timeout;
    rules.daytime_inactivity_seconds = daytime_timeout;
    rules.morning_sequence_window_seconds = morning_window;
    rules.night_visit_merge_seconds = night_merge;
    rules.post_door_inactivity_seconds = post_door_timeout;
    return true;
}

bool parse_payload(const std::vector<std::uint8_t>& bytes,
                   Gs40TestOnlyRuntimeConfig& config) {
    if (bytes.size() < 5 || bytes.size() > Gs40TestOnlyEnvelopeSession::kMaximumPlaintextBytes ||
        std::memcmp(bytes.data(), "G40P", 4) != 0 || bytes[4] != 1) return false;
    std::size_t offset = 5;
    std::uint32_t seen = 0;
    while (offset < bytes.size()) {
        if (offset + 3 > bytes.size()) return false;
        const auto id = bytes[offset++];
        std::uint16_t size = 0;
        if (!read_u16(bytes, offset, size)) return false;
        offset += 2;
        if (id < 1 || id > 21 || offset + size > bytes.size()) return false;
        const auto bit = 1U << id;
        if ((seen & bit) != 0) return false;
        seen |= bit;
        const auto* value = bytes.data() + offset;
        const auto string_value = [&]() {
            return std::string(reinterpret_cast<const char*>(value), size);
        };
        switch (id) {
            case 1: config.wifi_ssid = string_value(); break;
            case 2: config.wifi_psk = string_value(); break;
            case 3: config.backend_origin = string_value(); break;
            case 4: config.backend_hostname = string_value(); break;
            case 5: config.backend_ca_pem = string_value(); break;
            case 6: config.time_host = string_value(); break;
            case 7:
                if (size != 2) return false;
                config.time_port = static_cast<std::uint16_t>((value[0] << 8) | value[1]);
                break;
            case 8: config.time_public_key_der.assign(value, value + size); break;
            case 9: config.permanent_hub_id = string_value(); break;
            case 10: config.client_certificate_pem = string_value(); break;
            case 11: config.client_private_key_pem = string_value(); break;
            case 12: config.credential_fingerprint_sha256 = string_value(); break;
            case 13:
                if (size != 8 || !read_u64(bytes, offset, config.credential_generation)) return false;
                break;
            case 14:
                if (size != 8 || !read_u64(bytes, offset, config.envelope_generation)) return false;
                break;
            case 15:
                if (size != 8 || !read_u64(bytes, offset, config.envelope_expiry_utc)) return false;
                break;
            case 16: config.authority_public_key_der.assign(value, value + size); break;
            case 17: config.activity_home_id = string_value(); break;
            case 18: config.household_timezone = string_value(); break;
            case 19:
                if (!parse_activity_rule_config(value, size, config.activity_rules)) return false;
                config.activity_rules_present = true;
                break;
            case 20:
                if (size != 1 || value[0] > static_cast<std::uint8_t>(HomeMode::Privacy)) return false;
                config.home_mode = static_cast<HomeMode>(value[0]);
                break;
            case 21:
                config.fixture_home_id = string_value();
                config.fixture_home_id_present = true;
                break;
            default: return false;
        }
        offset += size;
    }
    constexpr std::uint32_t base_fields = 0x1fffeU;  // Fields 1..16.
    constexpr std::uint32_t rule_fields = (1U << 17) | (1U << 18) |
        (1U << 19) | (1U << 20);
    constexpr std::uint32_t fixture_home_field = 1U << 21;
    const auto supplied_rule_fields = seen & rule_fields;
    const bool fields_valid = (seen & base_fields) == base_fields &&
        (seen & ~(base_fields | rule_fields | fixture_home_field)) == 0 &&
        (supplied_rule_fields == 0 || supplied_rule_fields == rule_fields);
    return fields_valid && config.valid_shape();
}

bool verify_config_signature(const std::vector<std::uint8_t>& root_der,
                             const std::vector<std::uint8_t>& envelope,
                             std::size_t signed_size) {
    if (root_der.empty() || root_der.size() > 2048 || signed_size + kSignatureBytes != envelope.size())
        return false;
#if defined(ESP_PLATFORM)
    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    bool ok = false;
    if (mbedtls_pk_parse_public_key(&key, root_der.data(), root_der.size()) == 0 &&
        mbedtls_pk_get_bitlen(&key) == 3072 &&
        mbedtls_pk_can_do_psa(&key, PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_SHA_256), PSA_KEY_USAGE_VERIFY_HASH)) {
        std::array<unsigned char, 32> digest{};
        ok = sha256_concat(kConfigDomain, sizeof(kConfigDomain) - 1,
                envelope.data(), signed_size, digest) &&
            mbedtls_pk_verify(&key, MBEDTLS_MD_SHA256, digest.data(), digest.size(),
                envelope.data() + signed_size, kSignatureBytes) == 0;
    }
    mbedtls_pk_free(&key);
    return ok;
#else
    const unsigned char* cursor = root_der.data();
    EVP_PKEY* key = d2i_PUBKEY(nullptr, &cursor, static_cast<long>(root_der.size()));
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_PKEY_CTX* key_ctx = nullptr;
    bool ok = key != nullptr && cursor == root_der.data() + root_der.size() &&
        EVP_PKEY_base_id(key) == EVP_PKEY_RSA && EVP_PKEY_bits(key) == 3072 &&
        ctx != nullptr && EVP_DigestVerifyInit(ctx, &key_ctx, EVP_sha256(), nullptr, key) == 1 &&
        key_ctx != nullptr && EVP_PKEY_CTX_set_rsa_padding(key_ctx, RSA_PKCS1_PADDING) == 1 &&
        EVP_DigestVerifyUpdate(ctx, kConfigDomain, sizeof(kConfigDomain) - 1) == 1 &&
        EVP_DigestVerifyUpdate(ctx, envelope.data(), signed_size) == 1 &&
        EVP_DigestVerifyFinal(ctx, envelope.data() + signed_size, kSignatureBytes) == 1;
    EVP_MD_CTX_free(ctx);
    EVP_PKEY_free(key);
    return ok;
#endif
}

bool derive_session_key(const std::vector<std::uint8_t>& private_key_der,
                        std::uint32_t key_id,
                        const std::vector<std::uint8_t>& peer_public,
                        const std::array<std::uint8_t, 32>& salt,
                        std::array<std::uint8_t, 32>& output) {
#if defined(ESP_PLATFORM)
    std::array<std::uint8_t, 32> shared{};
    size_t shared_size = 0;
    const auto agreement = psa_raw_key_agreement(PSA_ALG_ECDH,
        static_cast<psa_key_id_t>(key_id), peer_public.data(), peer_public.size(),
        shared.data(), shared.size(), &shared_size);
    if (agreement != PSA_SUCCESS || shared_size != shared.size()) return false;
    psa_key_derivation_operation_t op = PSA_KEY_DERIVATION_OPERATION_INIT;
    const auto info = reinterpret_cast<const std::uint8_t*>(kKdfInfo);
    const bool ok = psa_key_derivation_setup(&op, PSA_ALG_HKDF(PSA_ALG_SHA_256)) == PSA_SUCCESS &&
        psa_key_derivation_input_bytes(&op, PSA_KEY_DERIVATION_INPUT_SALT,
            salt.data(), salt.size()) == PSA_SUCCESS &&
        psa_key_derivation_input_bytes(&op, PSA_KEY_DERIVATION_INPUT_SECRET,
            shared.data(), shared.size()) == PSA_SUCCESS &&
        psa_key_derivation_input_bytes(&op, PSA_KEY_DERIVATION_INPUT_INFO,
            info, sizeof(kKdfInfo) - 1) == PSA_SUCCESS &&
        psa_key_derivation_output_bytes(&op, output.data(), output.size()) == PSA_SUCCESS;
    psa_key_derivation_abort(&op);
    volatile std::uint8_t* secret = shared.data();
    for (std::size_t i = 0; i < shared.size(); ++i) secret[i] = 0;
    return ok;
#else
    (void)key_id;
    const unsigned char* cursor = private_key_der.data();
    EVP_PKEY* local = d2i_AutoPrivateKey(nullptr, &cursor,
                                         static_cast<long>(private_key_der.size()));
    EVP_PKEY* peer = nullptr;
    EVP_PKEY_CTX* import = EVP_PKEY_CTX_new_from_name(nullptr, "EC", nullptr);
    OSSL_PARAM_BLD* builder = OSSL_PARAM_BLD_new();
    OSSL_PARAM* params = nullptr;
    if (import != nullptr && builder != nullptr && peer_public.size() == 65 &&
        OSSL_PARAM_BLD_push_utf8_string(builder, OSSL_PKEY_PARAM_GROUP_NAME,
            "prime256v1", 0) == 1 &&
        OSSL_PARAM_BLD_push_octet_string(builder, OSSL_PKEY_PARAM_PUB_KEY,
            peer_public.data(), peer_public.size()) == 1 &&
        (params = OSSL_PARAM_BLD_to_param(builder)) != nullptr &&
        EVP_PKEY_fromdata_init(import) == 1 &&
        EVP_PKEY_fromdata(import, &peer, EVP_PKEY_PUBLIC_KEY, params) != 1) {
        EVP_PKEY_free(peer);
        peer = nullptr;
    }
    OSSL_PARAM_free(params);
    OSSL_PARAM_BLD_free(builder);
    EVP_PKEY_CTX_free(import);
    EVP_PKEY_CTX* agreement = local == nullptr || peer == nullptr ? nullptr : EVP_PKEY_CTX_new(local, nullptr);
    std::array<unsigned char, 32> shared{};
    std::size_t shared_size = shared.size();
    bool ok = agreement != nullptr && cursor == private_key_der.data() + private_key_der.size() &&
        EVP_PKEY_derive_init(agreement) == 1 && EVP_PKEY_derive_set_peer(agreement, peer) == 1 &&
        EVP_PKEY_derive(agreement, shared.data(), &shared_size) == 1 && shared_size == shared.size();
    EVP_PKEY_CTX_free(agreement);
    EVP_PKEY_free(local);
    EVP_PKEY_free(peer);
    EVP_PKEY_CTX* hkdf = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, nullptr);
    std::size_t output_size = output.size();
    ok = ok && hkdf != nullptr && EVP_PKEY_derive_init(hkdf) == 1 &&
        EVP_PKEY_CTX_set_hkdf_md(hkdf, EVP_sha256()) == 1 &&
        EVP_PKEY_CTX_set1_hkdf_salt(hkdf, salt.data(), salt.size()) == 1 &&
        EVP_PKEY_CTX_set1_hkdf_key(hkdf, shared.data(), shared.size()) == 1 &&
        EVP_PKEY_CTX_add1_hkdf_info(hkdf,
            reinterpret_cast<const unsigned char*>(kKdfInfo), sizeof(kKdfInfo) - 1) == 1 &&
        EVP_PKEY_derive(hkdf, output.data(), &output_size) == 1 && output_size == output.size();
    EVP_PKEY_CTX_free(hkdf);
    OPENSSL_cleanse(shared.data(), shared.size());
    return ok;
#endif
}

bool decrypt_payload(const std::array<std::uint8_t, 32>& key,
                     const std::vector<std::uint8_t>& envelope,
                     std::size_t cipher_offset, std::size_t cipher_size,
                     std::vector<std::uint8_t>& plaintext) {
    const auto* iv = envelope.data() + 102;
    const auto* ciphertext = envelope.data() + cipher_offset;
#if defined(ESP_PLATFORM)
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, PSA_KEY_TYPE_AES);
    psa_set_key_bits(&attributes, 256);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DECRYPT);
    psa_set_key_algorithm(&attributes, PSA_ALG_GCM);
    psa_key_id_t key_id = 0;
    auto result = psa_import_key(&attributes, key.data(), key.size(), &key_id);
    psa_reset_key_attributes(&attributes);
    plaintext.resize(cipher_size);
    std::size_t written = 0;
    if (result == PSA_SUCCESS)
        result = psa_aead_decrypt(key_id, PSA_ALG_GCM, iv, 12,
            envelope.data(), kHeaderBytes, ciphertext, cipher_size + kTagBytes,
            plaintext.data(), plaintext.size(), &written);
    if (key_id != 0) (void)psa_destroy_key(key_id);
    if (result != PSA_SUCCESS || written != cipher_size) {
        plaintext.clear();
        return false;
    }
    return true;
#else
    const auto* tag = ciphertext + cipher_size;
    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    plaintext.resize(cipher_size);
    int out = 0, final = 0;
    bool ok = ctx != nullptr && EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) == 1 &&
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, nullptr) == 1 &&
        EVP_DecryptInit_ex(ctx, nullptr, nullptr, key.data(), iv) == 1 &&
        EVP_DecryptUpdate(ctx, nullptr, &out, envelope.data(), kHeaderBytes) == 1 &&
        EVP_DecryptUpdate(ctx, plaintext.data(), &out, ciphertext, static_cast<int>(cipher_size)) == 1 &&
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, kTagBytes, const_cast<std::uint8_t*>(tag)) == 1 &&
        EVP_DecryptFinal_ex(ctx, plaintext.data() + out, &final) == 1 &&
        static_cast<std::size_t>(out + final) == cipher_size;
    EVP_CIPHER_CTX_free(ctx);
    if (!ok) plaintext.clear();
    return ok;
#endif
}

}  // namespace

bool gs40_test_only_hub_id_allowed(const std::string& hub_id) {
    constexpr char kTestPrefix[] = "test-hub-";
    constexpr char kPhysicalPrefix[] = "hub-";
    if (hub_id.size() > 64) return false;
    if (hub_id.rfind(kTestPrefix, 0) == 0) {
        const auto suffix = hub_id.substr(sizeof(kTestPrefix) - 1);
        return !suffix.empty() && std::all_of(suffix.begin(), suffix.end(),
            [](unsigned char ch) {
                return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
                    (ch >= '0' && ch <= '9') || ch == '_' || ch == '-';
            });
    }
    if (hub_id.size() != sizeof(kPhysicalPrefix) - 1 + 12 ||
        hub_id.rfind(kPhysicalPrefix, 0) != 0) return false;
    return std::all_of(hub_id.begin() + static_cast<std::ptrdiff_t>(sizeof(kPhysicalPrefix) - 1),
        hub_id.end(), [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        });
}

bool gs40_test_only_hub_id_matches_runtime(const std::string& configured_hub_id,
                                           const std::string& runtime_hub_id) {
    return gs40_test_only_hub_id_allowed(configured_hub_id) &&
        !runtime_hub_id.empty() && configured_hub_id == runtime_hub_id;
}

bool gs40_test_only_fixture_home_binding_allowed(
    const std::string& permanent_hub_id, const std::string& fixture_home_id) {
    return permanent_hub_id == "hub-e072a1d38d34" &&
        fixture_home_id == "gs177-test-product";
}

Gs40TestOnlyRuntimeConfig::Gs40TestOnlyRuntimeConfig(Gs40TestOnlyRuntimeConfig&& other) noexcept {
    *this = std::move(other);
}

Gs40TestOnlyRuntimeConfig& Gs40TestOnlyRuntimeConfig::operator=(Gs40TestOnlyRuntimeConfig&& other) noexcept {
    if (this == &other) return *this;
    clear_string(wifi_psk);
    clear_string(client_private_key_pem);
    wifi_ssid = std::move(other.wifi_ssid);
    wifi_psk = std::move(other.wifi_psk);
    backend_origin = std::move(other.backend_origin);
    backend_hostname = std::move(other.backend_hostname);
    backend_ca_pem = std::move(other.backend_ca_pem);
    time_host = std::move(other.time_host);
    time_port = other.time_port;
    time_public_key_der = std::move(other.time_public_key_der);
    authority_public_key_der = std::move(other.authority_public_key_der);
    permanent_hub_id = std::move(other.permanent_hub_id);
    fixture_home_id = std::move(other.fixture_home_id);
    fixture_home_id_present = other.fixture_home_id_present;
    client_certificate_pem = std::move(other.client_certificate_pem);
    client_private_key_pem = std::move(other.client_private_key_pem);
    credential_fingerprint_sha256 = std::move(other.credential_fingerprint_sha256);
    credential_generation = other.credential_generation;
    envelope_generation = other.envelope_generation;
    envelope_expiry_utc = other.envelope_expiry_utc;
    activity_home_id = std::move(other.activity_home_id);
    household_timezone = std::move(other.household_timezone);
    activity_rules = std::move(other.activity_rules);
    home_mode = other.home_mode;
    activity_rules_present = other.activity_rules_present;
    other.time_port = 0;
    other.credential_generation = other.envelope_generation = other.envelope_expiry_utc = 0;
    other.activity_rules_present = false;
    other.fixture_home_id_present = false;
    return *this;
}

Gs40TestOnlyRuntimeConfig::~Gs40TestOnlyRuntimeConfig() {
    clear_string(wifi_psk);
    clear_string(client_private_key_pem);
}

bool Gs40TestOnlyRuntimeConfig::valid_shape() const {
    return valid_ascii(wifi_ssid, 32) && wifi_psk.size() >= 8 &&
        wifi_psk.size() <= 63 && valid_material_shape() &&
        fixture_home_id_present == !fixture_home_id.empty() &&
        (!fixture_home_id_present || gs40_test_only_fixture_home_binding_allowed(
            permanent_hub_id, fixture_home_id)) &&
        ((!activity_rules_present && activity_home_id.empty() && household_timezone.empty()) ||
         valid_activity_rules_shape());
}

bool Gs40TestOnlyRuntimeConfig::valid_activity_rules_shape() const {
    if (!activity_rules_present || !valid_ascii(activity_home_id, 64) ||
        !supported_household_timezone(household_timezone) ||
        static_cast<std::uint8_t>(home_mode) > static_cast<std::uint8_t>(HomeMode::Privacy))
        return false;
    const auto& rules = activity_rules;
    if (rules.quiet_start_minute >= 1440 || rules.quiet_end_minute >= 1440 ||
        rules.daytime_start_minute >= 1440 || rules.daytime_end_minute >= 1440 ||
        rules.morning_start_minute >= 1440 || rules.morning_end_minute >= 1440 ||
        rules.night_start_minute >= 1440 || rules.night_end_minute >= 1440 ||
        rules.door_open_timeout_seconds < 30 || rules.door_open_timeout_seconds > 86400 ||
        rules.daytime_inactivity_seconds < 300 || rules.daytime_inactivity_seconds > 86400 ||
        rules.morning_sequence_window_seconds <= 0 || rules.morning_sequence_window_seconds > 86400 ||
        rules.night_bathroom_visit_threshold == 0 || rules.night_bathroom_visit_threshold > 32 ||
        rules.night_common_visit_threshold == 0 || rules.night_common_visit_threshold > 32 ||
        rules.night_visit_merge_seconds <= 0 || rules.night_visit_merge_seconds > 86400 ||
        rules.post_door_inactivity_seconds < 300 || rules.post_door_inactivity_seconds > 86400)
        return false;
    HomeConfig home;
    home.version = 1;
    home.home_id = activity_home_id;
    home.timezone = household_timezone;
    home.mode = home_mode;
    home.activity_rules = rules;
    // This envelope carries the deterministic ActivityRuleConfig. The separate
    // morning RoutineConfig is intentionally not part of GS40T/1 v1.
    home.morning.enabled = false;
    ConfigService validator;
    return validator.apply(home).applied;
}

bool gs40_test_only_local_minute_from_utc(const std::string& timezone,
        EpochSeconds trusted_utc, std::uint16_t& local_minute) {
    if (trusted_utc <= 0 || !supported_household_timezone(timezone)) return false;
    constexpr EpochSeconds kSecondsPerDay = 24 * 60 * 60;
    constexpr EpochSeconds kIndiaOffsetSeconds = 5 * 60 * 60 + 30 * 60;
    EpochSeconds local_epoch = trusted_utc;
    if (timezone == "Asia/Kolkata") {
        if (trusted_utc > std::numeric_limits<EpochSeconds>::max() - kIndiaOffsetSeconds)
            return false;
        local_epoch += kIndiaOffsetSeconds;
    }
    const auto seconds_of_local_day = local_epoch % kSecondsPerDay;
    const auto minute = static_cast<std::uint16_t>(seconds_of_local_day / 60);
    if (minute >= 24 * 60) return false;
    local_minute = minute;
    return true;
}

bool Gs40TestOnlyRuntimeConfig::valid_material_shape() const {
    const auto authority = backend_origin.size() > 8 ? backend_origin.substr(8) : std::string{};
    const auto authority_end = authority.find_first_of(":/?#@\r\n");
    const auto host = authority.substr(0, authority_end);
    if (!valid_ascii(wifi_ssid, 32) || backend_origin.size() > 256 || backend_origin.rfind("https://", 0) != 0 ||
        !valid_hostname(backend_hostname) || !isolated_destination(backend_hostname) ||
        !valid_backend_port(authority, host) ||
        host != backend_hostname || backend_origin.find_first_of("?#@\r\n", 8) != std::string::npos ||
        authority.find('/') != std::string::npos ||
        backend_ca_pem.size() < 64 || backend_ca_pem.size() > 4096 ||
        !valid_hostname(time_host) || !isolated_destination(time_host) || time_port == 0 ||
        !valid_rsa3072_public_der(time_public_key_der) ||
        !valid_rsa3072_public_der(authority_public_key_der) ||
        time_public_key_der == authority_public_key_der ||
        !gs40_test_only_hub_id_allowed(permanent_hub_id) ||
        client_certificate_pem.empty() || client_certificate_pem.size() > 4096 ||
        client_private_key_pem.empty() || client_private_key_pem.size() > 4096 ||
        credential_fingerprint_sha256.size() != 64 || credential_generation == 0 ||
        envelope_generation == 0 || envelope_expiry_utc == 0) return false;
    return std::all_of(credential_fingerprint_sha256.begin(),
        credential_fingerprint_sha256.end(), [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        }) && valid_tls_identity(client_certificate_pem, client_private_key_pem,
            credential_fingerprint_sha256);
}

void Gs40TestOnlyRuntimeConfig::clear_wifi_secret() { clear_string(wifi_psk); }

Gs40TestOnlyEnvelopeSession::Gs40TestOnlyEnvelopeSession(
    std::vector<std::uint8_t> root_public_key_der)
    : root_public_key_der_(std::move(root_public_key_der)) {}

Gs40TestOnlyEnvelopeSession::~Gs40TestOnlyEnvelopeSession() { clear(); }

bool Gs40TestOnlyEnvelopeSession::begin(
    std::array<std::uint8_t, 32>& challenge,
    std::vector<std::uint8_t>& target_public_key_sec1) {
    clear();
#if defined(ESP_PLATFORM)
    if (psa_crypto_init() != PSA_SUCCESS) return false;
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_SECP_R1));
    psa_set_key_bits(&attributes, 256);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DERIVE | PSA_KEY_USAGE_EXPORT);
    psa_set_key_algorithm(&attributes, PSA_ALG_ECDH);
    psa_key_id_t id = 0;
    if (psa_generate_key(&attributes, &id) != PSA_SUCCESS) return false;
    psa_reset_key_attributes(&attributes);
    std::array<std::uint8_t, 100> public_bytes{};
    std::size_t public_size = 0;
    if (psa_export_public_key(id, public_bytes.data(), public_bytes.size(), &public_size) != PSA_SUCCESS ||
        public_size != 65 || public_bytes[0] != 0x04 ||
        psa_generate_random(challenge.data(), challenge.size()) != PSA_SUCCESS) {
        (void)psa_destroy_key(id);
        return false;
    }
    key_id_ = static_cast<std::uint32_t>(id);
    target_public_key_sec1.assign(public_bytes.begin(), public_bytes.begin() + public_size);
#else
    EVP_PKEY_CTX* context = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, nullptr);
    EVP_PKEY* key = nullptr;
    bool ok = context != nullptr && EVP_PKEY_keygen_init(context) == 1 &&
        EVP_PKEY_CTX_set_ec_paramgen_curve_nid(context, NID_X9_62_prime256v1) == 1 &&
        EVP_PKEY_keygen(context, &key) == 1 && RAND_bytes(challenge.data(), challenge.size()) == 1;
    EVP_PKEY_CTX_free(context);
    if (!ok || key == nullptr) { EVP_PKEY_free(key); return false; }
    const int private_size = i2d_PrivateKey(key, nullptr);
    const int public_size = i2d_PUBKEY(key, nullptr);
    if (private_size <= 0 || public_size <= 0 || public_size > 256) {
        EVP_PKEY_free(key); return false;
    }
    private_key_der_.resize(static_cast<std::size_t>(private_size));
    unsigned char* private_cursor = private_key_der_.data();
    i2d_PrivateKey(key, &private_cursor);
    target_public_key_sec1.resize(65);
    std::size_t sec1_size = 0;
    const bool export_ok = EVP_PKEY_get_octet_string_param(key,
        OSSL_PKEY_PARAM_PUB_KEY, target_public_key_sec1.data(),
        target_public_key_sec1.size(), &sec1_size) == 1 && sec1_size == 65;
    EVP_PKEY_free(key);
    if (!export_ok) { clear(); return false; }
#endif
    challenge_ = challenge;
    active_ = true;
    return true;
}

bool Gs40TestOnlyEnvelopeSession::accept(
    const std::vector<std::uint8_t>& envelope,
    Gs40TestOnlyRuntimeConfig& config) {
    if (!active_) return false;
    // A challenge is one-shot even when the supplied envelope is malformed.
    active_ = false;
    const auto reject = [this]() { clear(); return false; };
    if (envelope.size() < kHeaderBytes + kTagBytes + kSignatureBytes ||
        envelope.size() > kMaximumEnvelopeBytes || std::memcmp(envelope.data(), "G40E", 4) != 0 ||
        envelope[4] != 1 || !std::equal(challenge_.begin(), challenge_.end(), envelope.begin() + 5))
        return reject();
    std::uint16_t cipher_size = 0;
    if (!read_u16(envelope, 114, cipher_size) || cipher_size == 0 ||
        cipher_size > kMaximumPlaintextBytes ||
        envelope.size() != kHeaderBytes + cipher_size + kTagBytes + kSignatureBytes)
        return reject();
    const auto signed_size = envelope.size() - kSignatureBytes;
    if (!verify_config_signature(root_public_key_der_, envelope, signed_size)) return reject();
    std::vector<std::uint8_t> peer_public(envelope.begin() + 37, envelope.begin() + 102);
    std::array<std::uint8_t, 32> key{};
    if (!derive_session_key(private_key_der_, key_id_, peer_public, challenge_, key)) return reject();
    std::vector<std::uint8_t> plaintext;
    const bool decrypted = decrypt_payload(key, envelope, kHeaderBytes, cipher_size, plaintext);
    volatile std::uint8_t* key_bytes = key.data();
    for (std::size_t i = 0; i < key.size(); ++i) key_bytes[i] = 0;
    if (!decrypted) return reject();
    Gs40TestOnlyRuntimeConfig candidate;
    const bool parsed = parse_payload(plaintext, candidate);
    volatile std::uint8_t* plain = plaintext.data();
    for (std::size_t i = 0; i < plaintext.size(); ++i) plain[i] = 0;
    if (!parsed || candidate.envelope_generation == 0 ||
        candidate.time_public_key_der == root_public_key_der_ ||
        candidate.authority_public_key_der == root_public_key_der_) return reject();
    config = std::move(candidate);
    clear();
    return true;
}

void Gs40TestOnlyEnvelopeSession::clear() {
#if defined(ESP_PLATFORM)
    if (key_id_ != 0) (void)psa_destroy_key(static_cast<psa_key_id_t>(key_id_));
    key_id_ = 0;
#else
    if (!private_key_der_.empty()) OPENSSL_cleanse(private_key_der_.data(), private_key_der_.size());
    private_key_der_.clear();
#endif
    std::fill(challenge_.begin(), challenge_.end(), 0);
    active_ = false;
}

Gs40TestOnlyMaterialSource::Gs40TestOnlyMaterialSource(
    Gs40TestOnlyRuntimeConfig&& config, const S3TrustedHubTimeSource& time,
    const S3HubMonotonicClock& clock)
    : config_(std::move(config)), time_(time), clock_(clock) {}

bool Gs40TestOnlyMaterialSource::install_authority_lease(
    const Gs40TestOnlyAuthorityLease& lease, std::uint64_t now_ms,
    std::uint64_t current_generation) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!config_.valid_material_shape() || !lease.active || lease.revoked ||
        lease.binding.home_id.empty() || lease.binding.home_id.size() > 64 ||
        lease.binding.hub_device_id != config_.permanent_hub_id ||
        lease.binding.ownership_epoch == 0 || lease.authority_revision == 0 ||
        lease.credential_generation != config_.credential_generation ||
        lease.certificate_fingerprint_sha256 != config_.credential_fingerprint_sha256 ||
        (lease_ready_ && (lease.authority_revision < lease_.authority_revision ||
         (lease.authority_revision == lease_.authority_revision &&
          !(lease.binding == lease_.binding)))) ||
        lease.boot_generation == 0 || lease.boot_generation != current_generation ||
        lease.expires_monotonic_ms <= now_ms ||
        lease.expires_monotonic_ms - now_ms > kLeaseMaximumMs) {
        lease_ready_ = false;
        return false;
    }
    lease_ = lease;
    lease_ready_ = true;
    return true;
}

void Gs40TestOnlyMaterialSource::invalidate() {
    std::lock_guard<std::mutex> lock(mutex_);
    lease_ready_ = false;
    lease_ = {};
}

bool Gs40TestOnlyAuthorityLeaseVerifier::verify(
    const std::string& response, const std::array<std::uint8_t, 32>& nonce,
    std::uint64_t boot_generation, std::uint64_t now_utc,
    std::uint64_t now_monotonic_ms, Gs40TestOnlyAuthorityLease& lease) const {
    constexpr std::size_t fixed_prefix = 119;
    if (public_key_der_.empty() || public_key_der_.size() > 2048 ||
        response.size() < fixed_prefix + 2 + kSignatureBytes || response.size() > 1024 ||
        std::memcmp(response.data(), "G40A", 4) != 0 || response[4] != 1 ||
        std::memcmp(nonce.data(), response.data() + 5, nonce.size()) != 0) return false;
    const auto* bytes = reinterpret_cast<const std::uint8_t*>(response.data());
    std::vector<std::uint8_t> wire(bytes, bytes + response.size());
    std::uint64_t generation = 0, issued = 0, expires = 0, revision = 0,
                  credential_generation = 0, epoch = 0;
    if (!read_u64(wire, 37, generation) || !read_u64(wire, 45, issued) ||
        !read_u64(wire, 53, expires) || !read_u64(wire, 61, revision) ||
        !read_u64(wire, 69, credential_generation) || !read_u64(wire, 77, epoch) ||
        generation != boot_generation || generation == 0 || revision == 0 ||
        credential_generation == 0 || epoch == 0 || wire[85] != 1 ||
        issued == 0 || issued > now_utc || now_utc - issued > 15 ||
        expires <= now_utc || expires <= issued || expires - issued > 60 ||
        now_monotonic_ms > std::numeric_limits<std::uint64_t>::max() - (expires - now_utc) * 1000)
        return false;
    const auto hub_length = wire[118];
    if (hub_length == 0 || hub_length > 64 || 119U + static_cast<std::size_t>(hub_length) >= wire.size()) return false;
    const std::string hub(reinterpret_cast<const char*>(wire.data() + 119), hub_length);
    const auto home_length_offset = 119 + hub_length;
    const auto home_length = wire[home_length_offset];
    const auto home_offset = home_length_offset + 1;
    const auto signed_size = wire.size() - kSignatureBytes;
    if (home_length == 0 || home_length > 64 || home_offset + static_cast<std::size_t>(home_length) != signed_size ||
        !gs40_test_only_hub_id_allowed(hub) || !valid_ascii(hub, 64) || !valid_ascii(
            std::string(reinterpret_cast<const char*>(wire.data() + home_offset), home_length), 64))
        return false;
    const std::string home(reinterpret_cast<const char*>(wire.data() + home_offset), home_length);
    bool signature_valid = false;
#if defined(ESP_PLATFORM)
    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    if (mbedtls_pk_parse_public_key(&key, public_key_der_.data(), public_key_der_.size()) == 0 &&
        mbedtls_pk_get_bitlen(&key) == 3072 &&
        mbedtls_pk_can_do_psa(&key, PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_SHA_256), PSA_KEY_USAGE_VERIFY_HASH)) {
        std::array<unsigned char, 32> digest{};
        signature_valid = sha256_concat(kAuthorityDomain,
                sizeof(kAuthorityDomain) - 1, wire.data(), signed_size, digest) &&
            mbedtls_pk_verify(&key, MBEDTLS_MD_SHA256, digest.data(), digest.size(),
                wire.data() + signed_size, kSignatureBytes) == 0;
    }
    mbedtls_pk_free(&key);
#else
    const unsigned char* cursor = public_key_der_.data();
    EVP_PKEY* key = d2i_PUBKEY(nullptr, &cursor, static_cast<long>(public_key_der_.size()));
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_PKEY_CTX* key_ctx = nullptr;
    signature_valid = key != nullptr && cursor == public_key_der_.data() + public_key_der_.size() &&
        EVP_PKEY_base_id(key) == EVP_PKEY_RSA && EVP_PKEY_bits(key) == 3072 && ctx != nullptr &&
        EVP_DigestVerifyInit(ctx, &key_ctx, EVP_sha256(), nullptr, key) == 1 && key_ctx != nullptr &&
        EVP_PKEY_CTX_set_rsa_padding(key_ctx, RSA_PKCS1_PADDING) == 1 &&
        EVP_DigestVerifyUpdate(ctx, kAuthorityDomain, sizeof(kAuthorityDomain) - 1) == 1 &&
        EVP_DigestVerifyUpdate(ctx, wire.data(), signed_size) == 1 &&
        EVP_DigestVerifyFinal(ctx, wire.data() + signed_size, kSignatureBytes) == 1;
    EVP_MD_CTX_free(ctx);
    EVP_PKEY_free(key);
#endif
    if (!signature_valid) return false;
    Gs40TestOnlyAuthorityLease candidate;
    candidate.binding.hub_device_id = hub;
    candidate.binding.home_id = home;
    candidate.binding.ownership_epoch = epoch;
    candidate.authority_revision = revision;
    candidate.credential_generation = credential_generation;
    candidate.boot_generation = generation;
    candidate.expires_monotonic_ms = now_monotonic_ms + (expires - now_utc) * 1000;
    candidate.active = true;
    const auto* fp = bytes + 86;
    static constexpr char hex[] = "0123456789abcdef";
    candidate.certificate_fingerprint_sha256.reserve(64);
    for (std::size_t i = 0; i < 32; ++i) {
        candidate.certificate_fingerprint_sha256.push_back(hex[fp[i] >> 4]);
        candidate.certificate_fingerprint_sha256.push_back(hex[fp[i] & 15]);
    }
    lease = std::move(candidate);
    return true;
}

bool Gs40TestOnlyMaterialSource::current_material(S3CloudTrustMaterial& material) const {
    std::lock_guard<std::mutex> lock(mutex_);
    TrustedHubTimeSnapshot time;
    const auto now_ms = clock_.now_ms();
    if (!lease_ready_ || now_ms < 0 || static_cast<std::uint64_t>(now_ms) >= lease_.expires_monotonic_ms ||
        !time_.trusted_hub_time(now_ms, time) || !time.trusted ||
        time.boot_generation != lease_.boot_generation ||
        lease_.credential_generation != config_.credential_generation ||
        lease_.certificate_fingerprint_sha256 != config_.credential_fingerprint_sha256)
        return false;
    S3CloudTrustMaterial result;
    result.binding = lease_.binding;
    result.authority_revision = lease_.authority_revision;
    result.authority_authenticated = true;
    result.authority_active = lease_.active;
    result.authority_revoked = lease_.revoked;
    result.permanent_hub_id = config_.permanent_hub_id;
    result.certificate_fingerprint_sha256 = config_.credential_fingerprint_sha256;
    result.client_certificate_pem = config_.client_certificate_pem;
    result.test_only_client_private_key_pem = config_.client_private_key_pem;
    result.rsa_bits = 3072;
    result.credential_generation = config_.credential_generation;
    result.credential_state = CloudCredentialState::Active;
    result.credential_purpose = CloudCredentialPurpose::CloudTlsClient;
    result.test_only = true;
    material = std::move(result);
    return true;
}

bool Gs40TestOnlyMaterialSource::bootstrap_identity(
    const TrustedHubTimeSnapshot& time, CloudTlsIdentity& identity) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!config_.valid_material_shape() || !time.trusted || time.utc_now <= 0 ||
        time.boot_generation == 0) return false;
    CloudTlsIdentity result;
    result.client_certificate_pem = config_.client_certificate_pem;
    result.test_only_client_private_key_pem = config_.client_private_key_pem;
    result.test_only_software_identity = true;
    result.rsa_bits = 3072;
    result.permanent_hub_id = config_.permanent_hub_id;
    result.certificate_fingerprint_sha256 = config_.credential_fingerprint_sha256;
    result.credential_generation = config_.credential_generation;
    result.trusted_utc_seconds = time.utc_now;
    result.trusted_monotonic_ms = time.monotonic_ms;
    result.trusted_time_boot_generation = time.boot_generation;
    result.purpose = CloudTlsIdentity::Purpose::CloudTlsClient;
    identity = std::move(result);
    return true;
}

bool Gs40TestOnlyBootstrapIdentityProvider::current_identity(
    CloudTlsIdentity& identity) {
    const auto now_ms = clock_.now_ms();
    TrustedHubTimeSnapshot snapshot;
    return now_ms > 0 && time_.trusted_hub_time(now_ms, snapshot) &&
        material_.bootstrap_identity(snapshot, identity);
}

bool gs40_test_only_refresh_authority(
    Gs40TestOnlyMaterialSource& material,
    const S3TrustedHubTimeSource& time,
    const S3HubMonotonicClock& clock,
    AuthenticatedTimeRandomSource& random,
    HttpsBackendChannel& channel,
    Gs40TestOnlyAuthorityLeaseVerifier& verifier) {
    const auto fail = [&]() { material.invalidate(); return false; };
    const auto now_ms = clock.now_ms();
    TrustedHubTimeSnapshot snapshot;
    if (now_ms <= 0 || !time.trusted_hub_time(now_ms, snapshot) ||
        !snapshot.trusted || snapshot.utc_now <= 0 || snapshot.boot_generation == 0)
        return fail();
    std::array<std::uint8_t, 32> nonce{};
    if (!random.fill(nonce.data(), nonce.size()) ||
        std::all_of(nonce.begin(), nonce.end(), [](std::uint8_t v) { return v == 0; }))
        return fail();
    const auto& config = material.config();
    if (!config.valid_material_shape()) return fail();
    // This endpoint returns a binary signed G40A lease. It is distinct from
    // NodeHealth and uses the bootstrap certificate only for authentication.
    const auto body = std::string("{\"protocol\":\"GS40T/1\",\"hub_id\":\"") +
        config.permanent_hub_id + "\",\"credential_generation\":" +
        std::to_string(config.credential_generation) +
        ",\"certificate_fingerprint_sha256\":\"" +
        config.credential_fingerprint_sha256 + "\",\"boot_generation\":" +
        std::to_string(snapshot.boot_generation) + ",\"nonce\":\"" +
        hex_bytes(nonce.data(), nonce.size()) + "\"}";
    auto response = channel.post("/v1/test/authority/refresh", body);
    if (!response.network_attempted || !response.server_authenticated ||
        !response.message_complete || response.status != 200 ||
        response.body.empty() || response.body.size() > 1024)
        return fail();
    // Evaluate server issuance against authenticated time AFTER the round trip.
    // A proof issued in the next UTC second is not future-dated merely because
    // the request began just before that boundary. Never add clock tolerance.
    const auto received_ms = clock.now_ms();
    TrustedHubTimeSnapshot received_time;
    if (received_ms < now_ms || received_ms - now_ms > 30000 ||
        !time.trusted_hub_time(received_ms, received_time) || !received_time.trusted ||
        received_time.boot_generation != snapshot.boot_generation || received_time.utc_now <= 0)
        return fail();
    Gs40TestOnlyAuthorityLease lease;
    if (!verifier.verify(response.body, nonce, received_time.boot_generation,
            static_cast<std::uint64_t>(received_time.utc_now),
            static_cast<std::uint64_t>(received_ms), lease) ||
        !material.install_authority_lease(lease,
            static_cast<std::uint64_t>(clock.now_ms()), received_time.boot_generation))
        return fail();
    return true;
}

}  // namespace gs::hub::target
