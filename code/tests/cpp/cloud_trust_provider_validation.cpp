#include "firmware/hub/target/esp32s3/cloud_trust_provider.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"

#include <atomic>
#include <ctime>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <utility>

#include <openssl/evp.h>
#include <openssl/pem.h>
#include <openssl/rsa.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>

using namespace gs::hub;
using namespace gs::hub::target;
using gs::EpochSeconds;
using gs::Milliseconds;

namespace {

constexpr AuthenticatedTimeBootstrapPolicy kTestTimePolicy{5000, 2000, 300};

void check(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

class FakeClock final : public S3HubMonotonicClock {
public:
    Milliseconds now_ms() const override { return now.load(); }
    std::atomic<Milliseconds> now{1000};
};

class TestTimeAuthority {
public:
    TestTimeAuthority() : key_(generate_key()), public_key_der_(encode_public_key(key_)),
                          verifier_(public_key_der_) {}
    ~TestTimeAuthority() { EVP_PKEY_free(key_); }
    TestTimeAuthority(const TestTimeAuthority&) = delete;
    TestTimeAuthority& operator=(const TestTimeAuthority&) = delete;

    const Rsa3072Sha256TimeProofVerifier& verifier() const { return verifier_; }
    std::vector<std::uint8_t> sign(const AuthenticatedTimeChallenge& challenge,
                                   const AuthenticatedTimeStatement& statement) const {
        auto payload = encode_authenticated_time_proof_payload(
            challenge.nonce, challenge.boot_generation, statement);
        if (payload.size() != 72) return {};
        EVP_MD_CTX* context = EVP_MD_CTX_new();
        EVP_PKEY_CTX* key_context = nullptr;
        std::vector<std::uint8_t> signature(384);
        std::size_t signature_size = signature.size();
        const bool ok = context != nullptr &&
            EVP_DigestSignInit(context, &key_context, EVP_sha256(), nullptr, key_) == 1 &&
            key_context != nullptr &&
            EVP_PKEY_CTX_set_rsa_padding(key_context, RSA_PKCS1_PADDING) == 1 &&
            EVP_DigestSignUpdate(context, payload.data(), payload.size()) == 1 &&
            EVP_DigestSignFinal(context, signature.data(), &signature_size) == 1 &&
            signature_size == 384;
        EVP_MD_CTX_free(context);
        if (!ok) return {};
        payload.insert(payload.end(), signature.begin(), signature.end());
        return payload;
    }

private:
    static EVP_PKEY* generate_key() {
        EVP_PKEY_CTX* context = EVP_PKEY_CTX_new_id(EVP_PKEY_RSA, nullptr);
        EVP_PKEY* key = nullptr;
        const bool ok = context != nullptr && EVP_PKEY_keygen_init(context) == 1 &&
            EVP_PKEY_CTX_set_rsa_keygen_bits(context, 3072) == 1 &&
            EVP_PKEY_keygen(context, &key) == 1;
        EVP_PKEY_CTX_free(context);
        if (!ok) {
            EVP_PKEY_free(key);
            throw std::runtime_error("test-only time authority key generation failed");
        }
        return key;
    }
    static std::vector<std::uint8_t> encode_public_key(EVP_PKEY* key) {
        const int length = i2d_PUBKEY(key, nullptr);
        if (length <= 0 || length > 2048)
            throw std::runtime_error("test-only time public key encoding failed");
        std::vector<std::uint8_t> result(static_cast<std::size_t>(length));
        unsigned char* output = result.data();
        if (i2d_PUBKEY(key, &output) != length)
            throw std::runtime_error("test-only time public key encoding failed");
        return result;
    }

    EVP_PKEY* key_;
    const std::vector<std::uint8_t> public_key_der_;
    const Rsa3072Sha256TimeProofVerifier verifier_;
};

struct TestClientCertificate {
    std::string pem;
    std::string fingerprint;
    EVP_PKEY* key{nullptr};
    TestClientCertificate() = default;
    TestClientCertificate(const TestClientCertificate&) = delete;
    TestClientCertificate& operator=(const TestClientCertificate&) = delete;
    TestClientCertificate(TestClientCertificate&& other) noexcept
        : pem(std::move(other.pem)), fingerprint(std::move(other.fingerprint)),
          key(std::exchange(other.key, nullptr)) {}
    ~TestClientCertificate() { EVP_PKEY_free(key); }
};

TestClientCertificate make_test_client_certificate(EVP_PKEY* key,
                                                    EpochSeconds not_before,
                                                    EpochSeconds not_after) {
    TestClientCertificate value;
    if (key == nullptr || not_before <= 0 || not_after <= not_before ||
        EVP_PKEY_up_ref(key) != 1)
        throw std::runtime_error("TEST_ONLY cloud identity key reference failed");
    value.key = key;

    X509* certificate = X509_new();
    bool cert_ok = certificate != nullptr && X509_set_version(certificate, 2) == 1 &&
        ASN1_INTEGER_set(X509_get_serialNumber(certificate), 7) == 1 &&
        ASN1_TIME_set(X509_getm_notBefore(certificate),
                      static_cast<std::time_t>(not_before)) != nullptr &&
        ASN1_TIME_set(X509_getm_notAfter(certificate),
                      static_cast<std::time_t>(not_after)) != nullptr &&
        X509_set_pubkey(certificate, key) == 1;
    X509_NAME* subject = certificate == nullptr ? nullptr : X509_get_subject_name(certificate);
    cert_ok = cert_ok && subject != nullptr &&
        X509_NAME_add_entry_by_txt(subject, "CN", MBSTRING_ASC,
            reinterpret_cast<const unsigned char*>("TEST_ONLY:test-hub-1"), -1, -1, 0) == 1 &&
        X509_set_issuer_name(certificate, subject) == 1;
    X509V3_CTX extension_context;
    if (certificate != nullptr)
        X509V3_set_ctx(&extension_context, certificate, certificate, nullptr, nullptr, 0);
    X509_EXTENSION* basic = cert_ok ? X509V3_EXT_conf_nid(
        nullptr, &extension_context, NID_basic_constraints,
        const_cast<char*>("critical,CA:FALSE")) : nullptr;
    X509_EXTENSION* usage = cert_ok ? X509V3_EXT_conf_nid(
        nullptr, &extension_context, NID_ext_key_usage,
        const_cast<char*>("clientAuth")) : nullptr;
    cert_ok = cert_ok && basic != nullptr && usage != nullptr &&
        X509_add_ext(certificate, basic, -1) == 1 &&
        X509_add_ext(certificate, usage, -1) == 1 &&
        X509_sign(certificate, key, EVP_sha256()) > 0;
    X509_EXTENSION_free(basic);
    X509_EXTENSION_free(usage);
    if (!cert_ok) {
        X509_free(certificate);
        throw std::runtime_error("TEST_ONLY cloud identity certificate generation failed");
    }

    BIO* output = BIO_new(BIO_s_mem());
    if (output == nullptr || PEM_write_bio_X509(output, certificate) != 1) {
        BIO_free(output);
        X509_free(certificate);
        throw std::runtime_error("TEST_ONLY cloud identity certificate encoding failed");
    }
    char* data = nullptr;
    const auto size = BIO_get_mem_data(output, &data);
    value.pem.assign(data, static_cast<std::size_t>(size));
    std::array<unsigned char, 32> fingerprint{};
    unsigned int fingerprint_size = 0;
    if (X509_digest(certificate, EVP_sha256(), fingerprint.data(),
                    &fingerprint_size) != 1 || fingerprint_size != fingerprint.size()) {
        BIO_free(output);
        X509_free(certificate);
        throw std::runtime_error("TEST_ONLY cloud identity fingerprint failed");
    }
    static constexpr char kHex[] = "0123456789abcdef";
    for (auto byte : fingerprint) {
        value.fingerprint.push_back(kHex[(byte >> 4) & 0x0f]);
        value.fingerprint.push_back(kHex[byte & 0x0f]);
    }
    BIO_free(output);
    X509_free(certificate);
    return value;
}

const TestClientCertificate& test_client_certificate() {
    static const TestClientCertificate result = [] {
        EVP_PKEY_CTX* key_context = EVP_PKEY_CTX_new_id(EVP_PKEY_RSA, nullptr);
        EVP_PKEY* key = nullptr;
        const bool key_ok = key_context != nullptr &&
            EVP_PKEY_keygen_init(key_context) == 1 &&
            EVP_PKEY_CTX_set_rsa_keygen_bits(key_context, 3072) == 1 &&
            EVP_PKEY_keygen(key_context, &key) == 1;
        EVP_PKEY_CTX_free(key_context);
        if (!key_ok) {
            EVP_PKEY_free(key);
            throw std::runtime_error("TEST_ONLY cloud identity key generation failed");
        }
        auto value = make_test_client_certificate(key, 1'799'999'000, 1'800'001'000);
        EVP_PKEY_free(key);
        return value;
    }();
    return result;
}

class FailingRandom final : public AuthenticatedTimeRandomSource {
public:
    bool fill(std::uint8_t*, std::size_t) override { return false; }
};

bool accept_signed_time(AuthenticatedHubTimeProvider& provider,
                        const TestTimeAuthority& authority,
                        const AuthenticatedTimeStatement& statement,
                        AuthenticatedTimeChallenge* used_challenge = nullptr) {
    AuthenticatedTimeChallenge challenge;
    if (!provider.create_challenge(challenge)) return false;
    if (used_challenge != nullptr) *used_challenge = challenge;
    return provider.accept_authenticated_time(authority.sign(challenge, statement));
}

class FakeMaterialSource final : public S3CloudTrustMaterialSource {
public:
    bool current_material(S3CloudTrustMaterial& out) const override {
        std::lock_guard<std::mutex> lock(mutex);
        if (!available) return false;
        out = value;
        return true;
    }
    void update(const S3CloudTrustMaterial& next) {
        std::lock_guard<std::mutex> lock(mutex);
        value = next;
    }
    mutable std::mutex mutex;
    bool available{true};
    S3CloudTrustMaterial value;
};

class FakeTimeSource final : public S3TrustedHubTimeSource {
public:
    explicit FakeTimeSource(const FakeClock& input) : clock(input) {}
    bool trusted_hub_time(Milliseconds now, TrustedHubTimeSnapshot& out) const override {
        if (!ready || now != clock.now_ms()) return false;
        if (on_read) {
            auto callback = std::move(on_read);
            callback();
        }
        out = {true, now, utc, generation};
        return true;
    }
    const FakeClock& clock;
    bool ready{false};
    EpochSeconds utc{1'800'000'000};
    std::uint64_t generation{1};
    mutable std::function<void()> on_read;
};

class MemoryTimeStore final : public AuthenticatedTimeFloorStore {
public:
    bool begin_boot(std::uint64_t& generation) override {
        if (!available) return false;
        generation = ++boot;
        return true;
    }
    TrustedTimeFloorRead read_floor(EpochSeconds& out) override {
        out = floor;
        return read_state;
    }
    bool commit_floor(EpochSeconds value) override {
        if (!available || !commit_ok || value <= 0 || value < floor) return false;
        floor = value;
        read_state = TrustedTimeFloorRead::Valid;
        return true;
    }
    bool available{true};
    bool commit_ok{true};
    std::uint64_t boot{0};
    EpochSeconds floor{0};
    TrustedTimeFloorRead read_state{TrustedTimeFloorRead::Missing};
};

class FakeProofVerifier final : public AuthenticatedTimeProofVerifier {
public:
    bool verify(const std::vector<std::uint8_t>& proof,
                const std::array<std::uint8_t, 32>& nonce,
                std::uint64_t boot_generation,
                AuthenticatedTimeStatement& out) const override {
        if (!signature_valid || proof != std::vector<std::uint8_t>{0x47, 0x53} ||
            nonce != expected_nonce || boot_generation != expected_boot) return false;
        if (has_verified_nonce && last_boot == boot_generation &&
            last_nonce == nonce) return false;
        last_nonce = nonce;
        last_boot = boot_generation;
        has_verified_nonce = true;
        out = statement;
        return true;
    }
    bool signature_valid{true};
    std::array<std::uint8_t, 32> expected_nonce{};
    std::uint64_t expected_boot{1};
    mutable std::array<std::uint8_t, 32> last_nonce{};
    mutable std::uint64_t last_boot{0};
    mutable bool has_verified_nonce{false};
    AuthenticatedTimeStatement statement{1'800'000'000, 1'800'000'000,
                                         1'800'000'010};
};

S3CloudTrustMaterial valid_material() {
    const auto& certificate = test_client_certificate();
    S3CloudTrustMaterial material;
    material.binding = {"home-a", "hub-permanent-1", 7};
    material.authority_revision = 11;
    material.authority_authenticated = true;
    material.authority_active = true;
    material.permanent_hub_id = "hub-permanent-1";
    material.certificate_fingerprint_sha256 = certificate.fingerprint;
    material.client_certificate_pem = certificate.pem;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    BIO* key_output = BIO_new(BIO_s_mem());
    if (key_output == nullptr || PEM_write_bio_PrivateKey(
            key_output, certificate.key, nullptr, nullptr, 0, nullptr, nullptr) != 1)
        throw std::runtime_error("TEST_ONLY private key serialization failed");
    char* key_data = nullptr;
    const auto key_size = BIO_get_mem_data(key_output, &key_data);
    material.test_only_client_private_key_pem.assign(
        key_data, static_cast<std::size_t>(key_size));
    BIO_free(key_output);
#else
    material.ds_context = reinterpret_cast<void*>(0x1);
#endif
    material.rsa_bits = 3072;
    material.credential_generation = 3;
    material.credential_state = CloudCredentialState::Active;
    material.credential_purpose = CloudCredentialPurpose::CloudTlsClient;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    material.key_custody_verified = false;
#else
    material.key_custody_verified = true;
#endif
    material.test_only = true;
    return material;
}

void test_identity_and_ownership_provider() {
    FakeClock clock;
    FakeTimeSource time{clock};
    FakeMaterialSource source;
    source.value = valid_material();
    ProvisionedS3CloudTrust provider(source, time, clock);

    CloudAuthorityBinding binding;
    check(provider.current_binding(binding) && binding == source.value.binding,
          "active verified Home binding is available");
    CloudTlsIdentity identity;
    check(!provider.current_identity(identity),
          "TLS identity is blocked before trusted time");
    time.ready = true;
    check(provider.current_identity(identity) &&
          identity.permanent_hub_id == "hub-permanent-1" &&
          identity.certificate_fingerprint_sha256 == source.value.certificate_fingerprint_sha256 &&
          identity.credential_generation == 3 && identity.rsa_bits == 3072 &&
          identity.ds_context == (source.value.test_only_client_private_key_pem.empty()
              ? reinterpret_cast<void*>(0x1) : nullptr),
          "current dedicated cloud credential matches selected test/production key mode");
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    check(identity.test_only_software_identity &&
          identity.test_only_client_private_key_pem ==
              source.value.test_only_client_private_key_pem,
          "isolated provider supplies only its matched TEST_ONLY software key");
#endif

    FakeMaterialSource changing_source;
    changing_source.value = valid_material();
    FakeTimeSource changing_time{clock};
    changing_time.ready = true;
    changing_time.on_read = [&] {
        auto transferred = changing_source.value;
        transferred.binding.home_id = "home-raced";
        ++transferred.binding.ownership_epoch;
        ++transferred.authority_revision;
        changing_source.update(transferred);
    };
    ProvisionedS3CloudTrust racing_provider(changing_source, changing_time, clock);
    check(!racing_provider.current_identity(identity),
          "Home transfer during identity/time composition fences mixed generations");

    const auto original = binding;
    auto next = source.value;
    next.binding.home_id = "home-b";
    next.binding.ownership_epoch = 8;
    next.authority_revision++;
    source.update(next);
    check(provider.current_binding(binding) && binding.home_id == "home-b" &&
          binding.ownership_epoch == 8 && !(binding == original),
          "authority transfer replaces immutable current binding");

    std::atomic<bool> start{false};
    std::atomic<unsigned> invalid_reads{0};
    std::vector<std::thread> readers;
    for (unsigned i = 0; i < 4; ++i) {
        readers.emplace_back([&] {
            while (!start.load()) std::this_thread::yield();
            for (unsigned n = 0; n < 500; ++n) {
                CloudAuthorityBinding observed;
                if (provider.current_binding(observed) &&
                    (observed.home_id.empty() || observed.ownership_epoch == 0))
                    invalid_reads.fetch_add(1);
            }
        });
    }
    start.store(true);
    next.authority_active = false;
    next.authority_revoked = true;
    next.authority_revision++;
    source.update(next);
    for (auto& reader : readers) reader.join();
    check(invalid_reads.load() == 0, "concurrent revocation never returns partial binding");
    check(!provider.current_binding(binding) && !provider.current_identity(identity),
          "revoked binding disables identity and publication authority");
}

void test_identity_negative_matrix() {
    FakeClock clock;
    FakeTimeSource time{clock};
    time.ready = true;
    const auto baseline = valid_material();
    const std::vector<std::pair<const char*, std::function<void(S3CloudTrustMaterial&)>>> mutations{
        {"wrong permanent Hub", [](auto& x) { x.permanent_hub_id = "other-hub"; }},
        {"wrong binding Hub", [](auto& x) { x.binding.hub_device_id = "other-hub"; }},
        {"empty Home", [](auto& x) { x.binding.home_id.clear(); }},
        {"zero epoch", [](auto& x) { x.binding.ownership_epoch = 0; }},
        {"missing authority proof", [](auto& x) { x.authority_authenticated = false; }},
        {"inactive authority", [](auto& x) { x.authority_active = false; }},
        {"revoked authority", [](auto& x) { x.authority_revoked = true; }},
        {"zero authority revision", [](auto& x) { x.authority_revision = 0; }},
        {"revoked credential", [](auto& x) { x.credential_state = CloudCredentialState::Revoked; }},
        {"quarantined credential", [](auto& x) { x.credential_state = CloudCredentialState::Quarantined; }},
        {"wrong credential purpose", [](auto& x) { x.credential_purpose = CloudCredentialPurpose::Commissioning; }},
        {"wrong RSA size", [](auto& x) { x.rsa_bits = 2048; }},
#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
        {"missing DS context", [](auto& x) { x.ds_context = nullptr; }},
        {"missing custody evidence", [](auto& x) { x.key_custody_verified = false; }},
#else
        {"missing TEST_ONLY private key", [](auto& x) { x.test_only_client_private_key_pem.clear(); }},
        {"mismatched TEST_ONLY private key", [](auto& x) { x.test_only_client_private_key_pem = "not a private key"; }},
#endif
        {"malformed fingerprint", [](auto& x) { x.certificate_fingerprint_sha256 = "00"; }},
        {"certificate fingerprint mismatch", [](auto& x) { x.certificate_fingerprint_sha256[0] = x.certificate_fingerprint_sha256[0] == 'a' ? 'b' : 'a'; }},
        {"private key in certificate field", [](auto& x) { x.client_certificate_pem += "PRIVATE KEY"; }},
        {"missing certificate", [](auto& x) { x.client_certificate_pem.clear(); }},
        {"zero credential generation", [](auto& x) { x.credential_generation = 0; }},
        {"non-test fixture in test build", [](auto& x) { x.test_only = false; }},
    };
    for (const auto& mutation : mutations) {
        FakeMaterialSource source;
        source.value = baseline;
        mutation.second(source.value);
        ProvisionedS3CloudTrust provider(source, time, clock);
        CloudAuthorityBinding binding;
        CloudTlsIdentity identity;
        check(!provider.current_binding(binding) && !provider.current_identity(identity),
              mutation.first);
    }
}

void test_hub_identity_rejects_certificate_outside_authenticated_time() {
    FakeClock clock;
    FakeTimeSource time{clock};
    time.ready = true;
    FakeMaterialSource source;
    source.value = valid_material();
    ProvisionedS3CloudTrust provider(source, time, clock);

    auto assert_rejected = [&](EpochSeconds not_before, EpochSeconds not_after,
                               const char* reason) {
        const auto& base = test_client_certificate();
        const auto invalid = make_test_client_certificate(
            base.key, not_before, not_after);
        auto material = valid_material();
        material.client_certificate_pem = invalid.pem;
        material.certificate_fingerprint_sha256 = invalid.fingerprint;
        source.update(material);
        CloudTlsIdentity identity;
        check(!provider.current_identity(identity), reason);
    };

    // The fake trusted clock is exactly 1,800,000,000 UTC seconds.
    assert_rejected(1'799'000'000, 1'799'999'999,
                    "expired Hub client certificate is rejected using trusted time");
    assert_rejected(1'800'000'001, 1'801'000'000,
                    "not-yet-valid Hub client certificate is rejected using trusted time");
}

void test_signed_time_proof_cryptography_and_replay() {
    TestTimeAuthority authority;
    TestTimeAuthority other_authority;
    S3AuthenticatedTimeRandomSource random;
    FakeClock clock;
    MemoryTimeStore store;
    AuthenticatedHubTimeProvider time(store, authority.verifier(), random,
                                     clock, kTestTimePolicy);
    check(time.start() && time.boot_generation() == 1,
          "signed-time provider starts with durable boot generation");
    TrustedHubTimeSnapshot snapshot;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "cold start has no trusted time before a signed proof");

    AuthenticatedTimeChallenge challenge;
    check(time.create_challenge(challenge) && challenge.boot_generation == 1,
          "CSPRNG creates a nonce bound to the current boot");
    const AuthenticatedTimeStatement statement{
        1'900'000'000, 1'899'999'990, 1'900'000'030};
    auto proof = authority.sign(challenge, statement);
    check(proof.size() == 456 && time.accept_authenticated_time(proof) &&
          time.trusted_hub_time(clock.now_ms(), snapshot) &&
          snapshot.utc_now == statement.issued_at_utc && store.floor == snapshot.utc_now,
          "RSA-3072/SHA-256 signed proof commits floor before trusted readiness");
    check(!time.accept_authenticated_time(proof),
          "accepted nonce cannot be replayed without a new provider challenge");

    AuthenticatedTimeChallenge next;
    check(time.create_challenge(next), "next challenge is fresh");
    check(!time.accept_authenticated_time(proof),
          "proof replay is rejected against a different fresh nonce");
    auto altered = authority.sign(next, {1'900'000'001, 1'900'000'001,
                                        1'900'000'031});
    altered[48] ^= 1;
    check(!time.accept_authenticated_time(altered),
          "payload modification invalidates the cryptographic signature");

    AuthenticatedTimeChallenge wrong_key_challenge;
    check(time.create_challenge(wrong_key_challenge), "wrong-key challenge created");
    check(!time.accept_authenticated_time(other_authority.sign(
              wrong_key_challenge, {1'900'000'002, 1'900'000'002,
                                    1'900'000'032})),
          "signature from an unpinned time key is rejected");

    FailingRandom failing_random;
    MemoryTimeStore no_nonce_store;
    AuthenticatedHubTimeProvider no_nonce(no_nonce_store, authority.verifier(),
                                          failing_random, clock, kTestTimePolicy);
    check(no_nonce.start() && !no_nonce.create_challenge(next),
          "CSPRNG failure prevents challenge issuance and readiness");
}

void test_signed_time_boot_recovery_rollback_and_storage_failure() {
    TestTimeAuthority authority;
    S3AuthenticatedTimeRandomSource random;
    FakeClock clock;
    MemoryTimeStore store;
    AuthenticatedHubTimeProvider first(store, authority.verifier(), random,
                                       clock, kTestTimePolicy);
    check(first.start() && accept_signed_time(first, authority,
          {1'910'000'000, 1'910'000'000, 1'910'000'020}),
          "first boot accepts a signed time proof");
    const auto floor = store.floor;

    AuthenticatedHubTimeProvider rebooted(store, authority.verifier(), random,
                                          clock, kTestTimePolicy);
    check(rebooted.start() && rebooted.boot_generation() == 2,
          "restart advances durable boot generation");
    TrustedHubTimeSnapshot snapshot;
    check(!rebooted.trusted_hub_time(clock.now_ms(), snapshot),
          "stored floor alone does not create trusted time after reboot");
    AuthenticatedTimeChallenge old_boot = {};
    check(rebooted.create_challenge(old_boot), "reboot challenge created");
    auto stale_boot = old_boot;
    stale_boot.boot_generation = 1;
    check(!rebooted.accept_authenticated_time(authority.sign(
              stale_boot, {floor + 1, floor + 1, floor + 10})),
          "cross-boot proof replay is rejected");
    check(!accept_signed_time(rebooted, authority,
          {floor - 1, floor - 1, floor + 10}),
          "signed time below the persisted trusted floor is rejected");
    check(accept_signed_time(rebooted, authority,
          {floor + 1, floor + 1, floor + 20}),
          "fresh generation-two proof restores time after reboot");

    MemoryTimeStore corrupt_store;
    corrupt_store.floor = floor;
    corrupt_store.read_state = TrustedTimeFloorRead::Corrupt;
    AuthenticatedHubTimeProvider corrupt_recovery(
        corrupt_store, authority.verifier(), random, clock, kTestTimePolicy);
    check(corrupt_recovery.start() &&
          accept_signed_time(corrupt_recovery, authority,
              {floor + 2, floor + 2, floor + 20}) &&
          corrupt_store.read_state == TrustedTimeFloorRead::Valid,
          "fresh signed time recovers a corrupt stored floor without lowering it");

    MemoryTimeStore write_failure;
    write_failure.commit_ok = false;
    AuthenticatedHubTimeProvider no_commit(write_failure, authority.verifier(),
                                           random, clock, kTestTimePolicy);
    check(no_commit.start() && !accept_signed_time(no_commit, authority,
          {1'920'000'000, 1'920'000'000, 1'920'000'010}) &&
          !no_commit.trusted_hub_time(clock.now_ms(), snapshot),
          "time floor persistence failure leaves the provider untrusted");

    MemoryTimeStore delayed_store;
    AuthenticatedHubTimeProvider delayed(delayed_store, authority.verifier(),
                                         random, clock, kTestTimePolicy);
    check(delayed.start(), "delayed signed-time fixture starts");
    AuthenticatedTimeChallenge delayed_challenge;
    check(delayed.create_challenge(delayed_challenge), "delayed challenge created");
    clock.now = delayed_challenge.created_monotonic_ms +
                kTestTimePolicy.max_response_age_ms + 1;
    check(!delayed.accept_authenticated_time(authority.sign(
              delayed_challenge, {1'930'000'000, 1'930'000'000,
                                  1'930'000'010})),
          "valid signature outside the local response-age window is rejected");
}

void test_authenticated_time_bootstrap_and_recovery() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x5a;
    verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider time(store, verifier, clock, kTestTimePolicy);
    check(time.start() && time.boot_generation() == 1,
          "cold boot advances durable boot generation");
    TrustedHubTimeSnapshot snapshot;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "cold boot without authenticated time remains untrusted");
    auto wrong_nonce = nonce;
    wrong_nonce[0]++;
    check(!time.accept_authenticated_time({0x47, 0x53}, wrong_nonce, clock.now_ms()),
          "proof bound to another nonce is rejected");
    check(!time.accept_authenticated_time({0x47, 0x53}, {}, clock.now_ms()),
          "empty nonce is rejected");
    check(time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          time.trusted_hub_time(clock.now_ms(), snapshot) &&
          snapshot.utc_now == 1'800'000'000 && snapshot.boot_generation == 1,
          "verified startup time is persisted before readiness");
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "authenticated time proof cannot reuse a one-use nonce");
    clock.now = 3500;
    check(time.trusted_hub_time(clock.now_ms(), snapshot) &&
          snapshot.utc_now == 1'800'000'002 && store.floor == snapshot.utc_now,
          "trusted time follows monotonic elapsed time and checkpoints its durable floor");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'799'999'999, 1'799'999'999, 1'800'000'020};
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "authenticated time rollback is rejected");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'002, 1'800'000'003, 1'800'000'020};
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "not-yet-valid authenticated time statement is rejected");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'002, 1'800'000'002, 1'800'000'020};
    check(time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "fresh authenticated time restores expired network session");

    clock.now = 22'501;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "trusted time expires at signed validity bound during outage");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'020, 1'800'000'020, 1'800'000'030};
    check(!time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "expired-session recovery cannot roll back monotonic elapsed time");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {1'800'000'021, 1'800'000'021, 1'800'000'031};
    check(time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          time.trusted_hub_time(clock.now_ms(), snapshot),
          "network recovery accepts a newer authenticated time statement");
}

void test_authenticated_time_corruption_reboot_and_failures() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x2a;
    verifier.expected_nonce = nonce;

    AuthenticatedHubTimeProvider first(store, verifier, clock, kTestTimePolicy);
    check(first.start(), "missing floor permits fail-closed startup");
    check(first.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "fresh signed time repairs missing floor");
    const auto first_floor = store.floor;

    AuthenticatedHubTimeProvider rebooted(store, verifier, clock, kTestTimePolicy);
    check(rebooted.start() && rebooted.boot_generation() == 2,
          "restart advances persistent boot generation");
    TrustedHubTimeSnapshot snapshot;
    check(!rebooted.trusted_hub_time(clock.now_ms(), snapshot),
          "persisted floor does not masquerade as current after restart");
    verifier.expected_boot = 2;
    verifier.statement = {first_floor - 1, first_floor - 1, first_floor + 10};
    check(!rebooted.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "reboot proof below persistent floor is rejected");
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {first_floor + 1, first_floor + 1, first_floor + 20};
    check(rebooted.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "fresh post-reboot signed time restores readiness");

    store.read_state = TrustedTimeFloorRead::Corrupt;
    AuthenticatedHubTimeProvider recovered(store, verifier, clock, kTestTimePolicy);
    check(recovered.start() &&
          !recovered.trusted_hub_time(clock.now_ms(), snapshot),
          "corrupt stored time never establishes startup trust");
    verifier.expected_boot = 3;
    ++nonce[1];
    verifier.expected_nonce = nonce;
    verifier.statement = {first_floor + 2, first_floor + 2, first_floor + 30};
    check(recovered.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          store.read_state == TrustedTimeFloorRead::Valid,
          "new authenticated proof atomically repairs corrupt floor");

    MemoryTimeStore unavailable;
    unavailable.available = false;
    AuthenticatedHubTimeProvider no_counter(unavailable, verifier, clock);
    check(!no_counter.start(), "missing durable boot counter fails closed");

    MemoryTimeStore write_failure;
    FakeProofVerifier write_failure_verifier;
    write_failure_verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider no_commit(write_failure, write_failure_verifier,
                                           clock, kTestTimePolicy);
    check(no_commit.start(), "time provider starts without current time");
    write_failure_verifier.expected_boot = 1;
    write_failure.commit_ok = false;
    write_failure_verifier.statement = {1'900'000'000, 1'900'000'000,
                                        1'900'000'010};
    check(!no_commit.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()) &&
          !no_commit.trusted_hub_time(clock.now_ms(), snapshot),
          "time persistence failure prevents readiness");

    FakeProofVerifier invalid_verifier;
    invalid_verifier.expected_nonce = nonce;
    invalid_verifier.signature_valid = false;
    MemoryTimeStore invalid_store;
    AuthenticatedHubTimeProvider invalid_proof(invalid_store, invalid_verifier, clock,
                                               kTestTimePolicy);
    check(invalid_proof.start() &&
          !invalid_proof.accept_authenticated_time({0x47, 0x53}, nonce,
                                                   clock.now_ms()),
          "unauthenticated proof is rejected");

    MemoryTimeStore delayed_store;
    FakeClock delayed_clock;
    FakeProofVerifier delayed_verifier;
    delayed_verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider delayed(delayed_store, delayed_verifier,
                                         delayed_clock, kTestTimePolicy);
    check(delayed.start(), "delayed-proof fixture starts without time");
    const auto challenge_started = delayed_clock.now_ms();
    delayed_clock.now = challenge_started + kTestTimePolicy.max_response_age_ms + 1;
    check(!delayed.accept_authenticated_time({0x47, 0x53}, nonce,
                                              challenge_started),
          "proof response outside the injected freshness window is rejected");
    delayed_clock.now = 1000;
    AuthenticatedHubTimeProvider no_approved_window(delayed_store, delayed_verifier,
                                                     delayed_clock);
    check(no_approved_window.start() &&
          !no_approved_window.accept_authenticated_time({0x47, 0x53}, nonce,
                                                          delayed_clock.now_ms()),
          "missing D06 freshness policy remains fail closed");
    AuthenticatedHubTimeProvider no_floor_checkpoint(
        delayed_store, delayed_verifier, delayed_clock,
        AuthenticatedTimeBootstrapPolicy{5000, 0});
    check(no_floor_checkpoint.start() &&
          !no_floor_checkpoint.accept_authenticated_time(
              {0x47, 0x53}, nonce, delayed_clock.now_ms()),
          "missing D06 durable-floor checkpoint policy remains fail closed");

    MemoryTimeStore zero_window_store;
    FakeProofVerifier zero_window_verifier;
    zero_window_verifier.expected_nonce = nonce;
    zero_window_verifier.statement = {1'800'000'000, 1'800'000'000,
                                      1'800'000'000};
    AuthenticatedHubTimeProvider zero_window(
        zero_window_store, zero_window_verifier, delayed_clock, kTestTimePolicy);
    check(zero_window.start() &&
          !zero_window.accept_authenticated_time({0x47, 0x53}, nonce,
                                                  delayed_clock.now_ms()),
          "zero-length signed validity window is rejected");
}

void test_same_boot_clock_rollback_latches_fail_closed() {
    FakeClock clock;
    MemoryTimeStore store;
    FakeProofVerifier verifier;
    std::array<std::uint8_t, 32> nonce{};
    nonce[0] = 0x31;
    verifier.expected_nonce = nonce;
    AuthenticatedHubTimeProvider time(store, verifier, clock, kTestTimePolicy);
    check(time.start() &&
          time.accept_authenticated_time({0x47, 0x53}, nonce, clock.now_ms()),
          "rollback fixture reaches authenticated time");
    TrustedHubTimeSnapshot snapshot;
    clock.now = 1100;
    check(time.trusted_hub_time(1100, snapshot), "platform clock advances normally");
    clock.now = 1200;
    check(time.trusted_hub_time(1150, snapshot) && snapshot.monotonic_ms == 1150,
          "nested provider read accepts prior reference while platform clock advances");
    clock.now = 999;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "same-boot monotonic rollback is rejected");
    clock.now = 1000;
    check(!time.trusted_hub_time(clock.now_ms(), snapshot),
          "monotonic rollback remains fail-closed for the boot");
}

void test_provider_to_nodehealth_cloudsync_path() {
    FakeClock clock;
    MemoryTimeStore store;
    TestTimeAuthority time_authority;
    S3AuthenticatedTimeRandomSource random;
    AuthenticatedHubTimeProvider trusted_time(
        store, time_authority.verifier(), random, clock, kTestTimePolicy);
    check(trusted_time.start(), "integrated provider starts without trusted time");

    FakeMaterialSource material;
    material.value = valid_material();
    class CombinedTime final : public S3TrustedHubTimeSource {
    public:
        explicit CombinedTime(AuthenticatedHubTimeProvider& source) : source_(source) {}
        bool trusted_hub_time(Milliseconds now,
                              TrustedHubTimeSnapshot& out) const override {
            return source_.trusted_hub_time(now, out);
        }
    private:
        AuthenticatedHubTimeProvider& source_;
    } combined_time(trusted_time);

    ProvisionedS3CloudTrust cloud_trust(material, combined_time, clock);
    CloudAuthorityBinding pre_recovery_binding;
    check(cloud_trust.current_binding(pre_recovery_binding) &&
          pre_recovery_binding.ownership_epoch == 7,
          "current Home authority is available while time is untrusted");
    auto transferred_during_recovery = material.value;
    transferred_during_recovery.binding.home_id = "home-b";
    transferred_during_recovery.binding.ownership_epoch++;
    transferred_during_recovery.authority_revision++;
    material.update(transferred_during_recovery);
    check(accept_signed_time(trusted_time, time_authority,
          {1'800'000'000, 1'800'000'000, 1'800'000'100}),
          "authenticated time recovers after an ownership-epoch change");
    CloudAuthorityBinding recovered_binding;
    check(cloud_trust.current_binding(recovered_binding) &&
          recovered_binding.home_id == "home-b" &&
          recovered_binding.ownership_epoch == 8,
          "recovery exposes only the latest Home authority epoch");
    CloudTlsIdentity identity;
    check(cloud_trust.current_identity(identity) &&
          identity.permanent_hub_id == "hub-permanent-1",
          "S3 TLS credential and authenticated time resolve together");

    struct Authority final : CloudRuntimeAuthorityProvider {
        explicit Authority(ProvisionedS3CloudTrust& provider) : provider(provider) {}
        ProvisionedS3CloudTrust& provider;
        std::vector<CloudNodeEnrollment> nodes{{"node-physical", "room-a", 4, 55,
                                                 "configured", 300, 910}};
        bool current_binding(CloudAuthorityBinding& out) override {
            return provider.current_binding(out);
        }
        bool original_event_owned(const gs::DomainEvent&,
                                  const CloudAuthorityBinding& binding) override {
            CloudAuthorityBinding current;
            return provider.current_binding(current) && current == binding;
        }
        bool trusted_hub_time(Milliseconds now,
                              TrustedHubTimeSnapshot& out) override {
            return provider.trusted_hub_time(now, out);
        }
        bool active_nodes(const CloudAuthorityBinding& binding,
                          std::vector<CloudNodeEnrollment>& out) override {
            CloudAuthorityBinding current;
            if (!provider.current_binding(current) || !(current == binding)) return false;
            out = nodes;
            return true;
        }
    } authority(cloud_trust);

    struct Transport final : CloudBackendTransport {
        unsigned sent{0};
        CloudAuthorityBinding last_binding;
        NodeHealthPublication last_status;
        BackendCommitReply submit(const BackendCommitRequest&) override { return {}; }
        NodeHealthReply submit_node_health(const CloudAuthorityBinding& binding,
                                           const NodeHealthPublication& status) override {
            ++sent;
            last_binding = binding;
            last_status = status;
            return {NodeHealthReplyStatus::Accepted};
        }
    } transport;

    HubRuntime runtime;
    constexpr Milliseconds now_ms = 1000;
    clock.now = now_ms;
    runtime.authorize_node("room-a", 55, true);
    runtime.set_node_offline_timeout("room-a", 910);
    check(runtime.observe_authenticated_contact("room-a", 55, now_ms, 0,
          CloudContactKind::NodeHealth),
          "authenticated current-session Node contact enters HubRuntime");

    CloudRuntimeAuthoritySource authority_source(authority);
    CloudSyncWorker worker(runtime.journal(), runtime, authority_source, transport);
    check(worker.refresh_node_health_snapshot(now_ms),
          "credential and time providers authorize owner snapshot composition");
    const auto published = worker.run_node_health_once(true, now_ms);
    check(published.node_health_submitted == 1 &&
          published.node_health_accepted == 1 && transport.sent == 1 &&
          transport.last_status.valid() &&
          transport.last_binding == material.value.binding &&
          transport.last_status.physical_node_id == "node-physical" &&
          transport.last_status.offline_seconds == 910,
          "authenticated Node contact reaches bounded CloudSync status transport");

    auto transferred = material.value;
    transferred.binding.home_id = "home-c";
    transferred.binding.ownership_epoch++;
    transferred.authority_revision++;
    material.update(transferred);
    const auto after_transfer = worker.run_node_health_once(true, now_ms + 1);
    check(after_transfer.state == CloudWorkerState::AuthorityChanged &&
          transport.sent == 1,
          "Home transfer fences the pinned worker before another publication");
}

}  // namespace

int main() {
    try {
        test_identity_and_ownership_provider();
        std::cout << "GS68-D05-AUTHORITY-PROVIDER PASS\n";
        test_hub_identity_rejects_certificate_outside_authenticated_time();
        std::cout << "GS68-D05-CERT-VALIDITY-001 PASS\n";
        test_identity_negative_matrix();
        std::cout << "GS68-D12-CREDENTIAL-PROVIDER PASS\n";
        test_authenticated_time_bootstrap_and_recovery();
        test_authenticated_time_corruption_reboot_and_failures();
        test_same_boot_clock_rollback_latches_fail_closed();
        std::cout << "GS68-D06-TIME-STATE-MACHINE PASS\n";
        test_signed_time_proof_cryptography_and_replay();
        test_signed_time_boot_recovery_rollback_and_storage_failure();
        std::cout << "GS68-D06-SIGNED-PROOF-CRYPTO PASS\n";
        test_provider_to_nodehealth_cloudsync_path();
        std::cout << "GS40-PROVIDER-CLOUDSYNC-INTEGRATION PASS\n";
        std::cout << "GS-CLOUD-TRUST-PROVIDER PASS suites=5 physical=NOT_RUN\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "GS-CLOUD-TRUST-PROVIDER FAIL " << error.what() << '\n';
        return 1;
    }
}
