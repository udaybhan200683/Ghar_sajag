#include "firmware/hub/target/esp32s3/gs40_test_only_bootstrap.hpp"

#include <openssl/evp.h>
#include <openssl/core_names.h>
#include <openssl/hmac.h>
#include <openssl/kdf.h>
#include <openssl/param_build.h>
#include <openssl/pem.h>
#include <openssl/rand.h>
#include <openssl/rsa.h>
#include <openssl/sha.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>

#include <array>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using namespace gs::hub::target;

namespace gs::hub::target {
BackendHttpResponse HttpsBackendChannel::post(const std::string&, const std::string&) {
    return {};
}
}

namespace {
int checks = 0;
void check(bool ok, const char* label) {
    ++checks;
    if (!ok) { std::cerr << "FAIL " << label << '\n'; std::exit(1); }
}

EVP_PKEY* rsa_key() {
    EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new_id(EVP_PKEY_RSA, nullptr);
    EVP_PKEY* key = nullptr;
    const bool ok = ctx && EVP_PKEY_keygen_init(ctx) == 1 &&
        EVP_PKEY_CTX_set_rsa_keygen_bits(ctx, 3072) == 1 &&
        EVP_PKEY_keygen(ctx, &key) == 1;
    EVP_PKEY_CTX_free(ctx);
    if (!ok) { EVP_PKEY_free(key); return nullptr; }
    return key;
}

std::vector<std::uint8_t> public_der(EVP_PKEY* key) {
    const int length = i2d_PUBKEY(key, nullptr);
    std::vector<std::uint8_t> der(static_cast<std::size_t>(length));
    auto* cursor = der.data();
    i2d_PUBKEY(key, &cursor);
    return der;
}

std::string pem_key(EVP_PKEY* key) {
    BIO* bio = BIO_new(BIO_s_mem());
    PEM_write_bio_PrivateKey(bio, key, nullptr, nullptr, 0, nullptr, nullptr);
    char* data = nullptr;
    const auto length = BIO_get_mem_data(bio, &data);
    std::string result(data, static_cast<std::size_t>(length));
    BIO_free(bio);
    return result;
}

std::string pem_cert(EVP_PKEY* key, std::string& fingerprint) {
    X509* cert = X509_new();
    X509_set_version(cert, 2);
    ASN1_INTEGER_set(X509_get_serialNumber(cert), 77);
    X509_gmtime_adj(X509_getm_notBefore(cert), -30);
    X509_gmtime_adj(X509_getm_notAfter(cert), 3600);
    X509_set_pubkey(cert, key);
    X509_NAME* name = X509_get_subject_name(cert);
    X509_NAME_add_entry_by_txt(name, "CN", MBSTRING_ASC,
        reinterpret_cast<const unsigned char*>("test-hub-000001"), -1, -1, 0);
    X509_set_issuer_name(cert, name);
    X509_EXTENSION* usage = X509V3_EXT_conf_nid(nullptr, nullptr,
        NID_ext_key_usage, const_cast<char*>("clientAuth"));
    X509_add_ext(cert, usage, -1);
    X509_EXTENSION_free(usage);
    X509_sign(cert, key, EVP_sha256());
    unsigned char* der = nullptr;
    const int der_length = i2d_X509(cert, &der);
    std::array<unsigned char, 32> digest{};
    SHA256(der, static_cast<std::size_t>(der_length), digest.data());
    static constexpr char digits[] = "0123456789abcdef";
    for (auto b : digest) { fingerprint.push_back(digits[b >> 4]); fingerprint.push_back(digits[b & 15]); }
    OPENSSL_free(der);
    BIO* bio = BIO_new(BIO_s_mem());
    PEM_write_bio_X509(bio, cert);
    char* data = nullptr;
    const auto length = BIO_get_mem_data(bio, &data);
    std::string result(data, static_cast<std::size_t>(length));
    BIO_free(bio);
    X509_free(cert);
    return result;
}

void put16(std::vector<std::uint8_t>& out, std::uint16_t value) {
    out.push_back(static_cast<std::uint8_t>(value >> 8)); out.push_back(static_cast<std::uint8_t>(value));
}
void put32(std::vector<std::uint8_t>& out, std::uint32_t value) {
    out.push_back(static_cast<std::uint8_t>(value >> 24));
    out.push_back(static_cast<std::uint8_t>(value >> 16));
    out.push_back(static_cast<std::uint8_t>(value >> 8));
    out.push_back(static_cast<std::uint8_t>(value));
}
void put_location(std::vector<std::uint8_t>& out, const std::string& value) {
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
}
std::vector<std::uint8_t> activity_rules() {
    std::vector<std::uint8_t> out{'A','R','1',0x1f};
    put16(out,60);put16(out,300);put32(out,7200);
    put16(out,480);put16(out,1260);put32(out,10800);
    put16(out,360);put16(out,660);put32(out,14400);
    put_location(out,"bedroom");put_location(out,"bathroom");put_location(out,"kitchen");
    put16(out,1320);put16(out,360);put_location(out,"bathroom");put16(out,4);
    put_location(out,"common");put16(out,4);put32(out,300);put32(out,7200);
    return out;
}
void put64(std::vector<std::uint8_t>& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8) out.push_back(static_cast<std::uint8_t>(value >> shift));
}
void field(std::vector<std::uint8_t>& out, std::uint8_t id, const std::vector<std::uint8_t>& value) {
    out.push_back(id); put16(out, static_cast<std::uint16_t>(value.size())); out.insert(out.end(), value.begin(), value.end());
}
void field(std::vector<std::uint8_t>& out, std::uint8_t id, const std::string& value) {
    field(out, id, std::vector<std::uint8_t>(value.begin(), value.end()));
}
std::vector<std::uint8_t> number(std::uint64_t value) {
    std::vector<std::uint8_t> out; put64(out, value); return out;
}

EVP_PKEY* p256_key() {
    EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, nullptr);
    EVP_PKEY* key = nullptr;
    const bool ok = ctx && EVP_PKEY_keygen_init(ctx) == 1 &&
        EVP_PKEY_CTX_set_ec_paramgen_curve_nid(ctx, NID_X9_62_prime256v1) == 1 &&
        EVP_PKEY_keygen(ctx, &key) == 1;
    EVP_PKEY_CTX_free(ctx);
    if (!ok) { EVP_PKEY_free(key); return nullptr; }
    return key;
}

bool derive(EVP_PKEY* private_key, const std::vector<std::uint8_t>& peer_sec1,
            const std::array<std::uint8_t, 32>& salt, std::array<std::uint8_t, 32>& output) {
    EVP_PKEY_CTX* import = EVP_PKEY_CTX_new_from_name(nullptr, "EC", nullptr);
    OSSL_PARAM_BLD* builder = OSSL_PARAM_BLD_new();
    OSSL_PARAM* params = nullptr;
    EVP_PKEY* peer = nullptr;
    bool ok = import && builder && OSSL_PARAM_BLD_push_utf8_string(builder,
        OSSL_PKEY_PARAM_GROUP_NAME, "prime256v1", 0) == 1 &&
        OSSL_PARAM_BLD_push_octet_string(builder, OSSL_PKEY_PARAM_PUB_KEY,
            peer_sec1.data(), peer_sec1.size()) == 1 &&
        (params = OSSL_PARAM_BLD_to_param(builder)) != nullptr &&
        EVP_PKEY_fromdata_init(import) == 1 &&
        EVP_PKEY_fromdata(import, &peer, EVP_PKEY_PUBLIC_KEY, params) == 1;
    EVP_PKEY_CTX* agreement = ok ? EVP_PKEY_CTX_new(private_key, nullptr) : nullptr;
    std::array<std::uint8_t, 32> shared{};
    std::size_t shared_size = shared.size();
    ok = ok && agreement && EVP_PKEY_derive_init(agreement) == 1 &&
        EVP_PKEY_derive_set_peer(agreement, peer) == 1 &&
        EVP_PKEY_derive(agreement, shared.data(), &shared_size) == 1 && shared_size == shared.size();
    EVP_PKEY_CTX_free(agreement); EVP_PKEY_free(peer); OSSL_PARAM_free(params);
    OSSL_PARAM_BLD_free(builder); EVP_PKEY_CTX_free(import);
    EVP_PKEY_CTX* hkdf = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, nullptr);
    std::size_t output_size = output.size();
    static constexpr char info[] = "GS40T/1/CONFIG/AES256GCM\0";
    ok = ok && hkdf && EVP_PKEY_derive_init(hkdf) == 1 &&
        EVP_PKEY_CTX_set_hkdf_md(hkdf, EVP_sha256()) == 1 &&
        EVP_PKEY_CTX_set1_hkdf_salt(hkdf, salt.data(), salt.size()) == 1 &&
        EVP_PKEY_CTX_set1_hkdf_key(hkdf, shared.data(), shared.size()) == 1 &&
        EVP_PKEY_CTX_add1_hkdf_info(hkdf, reinterpret_cast<const unsigned char*>(info), sizeof(info) - 1) == 1 &&
        EVP_PKEY_derive(hkdf, output.data(), &output_size) == 1 && output_size == output.size();
    EVP_PKEY_CTX_free(hkdf); OPENSSL_cleanse(shared.data(), shared.size());
    return ok;
}

std::vector<std::uint8_t> signed_config(EVP_PKEY* signer,
    const std::array<std::uint8_t, 32>& challenge, const std::vector<std::uint8_t>& target_public,
    const std::vector<std::uint8_t>& time_der, const std::vector<std::uint8_t>& authority_der,
    const std::string& cert, const std::string& key, const std::string& fingerprint) {
    std::vector<std::uint8_t> plain{'G','4','0','P',1};
    field(plain,1,"gs40-lab"); field(plain,2,"test-passphrase");
    field(plain,3,"https://127.0.0.1:9443"); field(plain,4,"127.0.0.1");
    field(plain,5,"-----BEGIN CERTIFICATE-----\nTEST ROOT\n-----END CERTIFICATE-----\n");
    field(plain,6,"127.0.0.1"); field(plain,7,std::vector<std::uint8_t>{0x12,0x34});
    field(plain,8,time_der); field(plain,9,"test-hub-000001"); field(plain,10,cert); field(plain,11,key);
    field(plain,12,fingerprint); field(plain,13,number(1)); field(plain,14,number(1));
    field(plain,15,number(1893456000)); field(plain,16,authority_der);
    field(plain,17,"home1"); field(plain,18,"Etc/UTC");
    field(plain,19,activity_rules()); field(plain,20,std::vector<std::uint8_t>{0});
    EVP_PKEY* peer = p256_key();
    std::array<std::uint8_t, 65> peer_public{}; std::size_t peer_length = peer_public.size();
    check(peer && EVP_PKEY_get_octet_string_param(peer, OSSL_PKEY_PARAM_PUB_KEY,
        peer_public.data(), peer_public.size(), &peer_length) == 1 && peer_length == 65, "sender P256 key");
    std::array<std::uint8_t, 32> aes{}; check(derive(peer, target_public, challenge, aes), "derive ECDH/HKDF");
    std::array<std::uint8_t, 12> iv{}; RAND_bytes(iv.data(), iv.size());
    std::vector<std::uint8_t> envelope(116, 0);
    std::memcpy(envelope.data(), "G40E", 4); envelope[4]=1;
    std::copy(challenge.begin(), challenge.end(), envelope.begin()+5);
    std::copy(peer_public.begin(), peer_public.end(), envelope.begin()+37);
    std::copy(iv.begin(), iv.end(), envelope.begin()+102);
    envelope[114]=static_cast<std::uint8_t>(plain.size() >> 8); envelope[115]=static_cast<std::uint8_t>(plain.size());
    EVP_CIPHER_CTX* cipher=EVP_CIPHER_CTX_new(); int n=0, final=0;
    std::vector<std::uint8_t> ciphertext(plain.size()+16);
    bool ok=cipher && EVP_EncryptInit_ex(cipher,EVP_aes_256_gcm(),nullptr,nullptr,nullptr)==1 &&
      EVP_CIPHER_CTX_ctrl(cipher,EVP_CTRL_GCM_SET_IVLEN,iv.size(),nullptr)==1 &&
      EVP_EncryptInit_ex(cipher,nullptr,nullptr,aes.data(),iv.data())==1 &&
      EVP_EncryptUpdate(cipher,nullptr,&n,envelope.data(),envelope.size())==1 &&
      EVP_EncryptUpdate(cipher,ciphertext.data(),&n,plain.data(),plain.size())==1;
    const auto cipher_len=static_cast<std::size_t>(n);
    ok=ok && EVP_EncryptFinal_ex(cipher,ciphertext.data()+n,&final)==1 &&
      static_cast<std::size_t>(n+final)==plain.size();
    std::array<std::uint8_t,16> tag{};
    ok=ok && EVP_CIPHER_CTX_ctrl(cipher,EVP_CTRL_GCM_GET_TAG,tag.size(),tag.data())==1;
    EVP_CIPHER_CTX_free(cipher); EVP_PKEY_free(peer); OPENSSL_cleanse(aes.data(),aes.size());
    check(ok, "encrypt envelope");
    envelope.insert(envelope.end(),ciphertext.begin(),ciphertext.begin()+static_cast<std::ptrdiff_t>(cipher_len));
    envelope.insert(envelope.end(),tag.begin(),tag.end());
    static constexpr char domain[]="GS40T/1/CONFIG\0";
    EVP_MD_CTX* md=EVP_MD_CTX_new(); EVP_PKEY_CTX* pkctx=nullptr;
    ok=md && EVP_DigestSignInit(md,&pkctx,EVP_sha256(),nullptr,signer)==1 &&
      EVP_PKEY_CTX_set_rsa_padding(pkctx,RSA_PKCS1_PADDING)==1 &&
      EVP_DigestSignUpdate(md,domain,sizeof(domain)-1)==1 &&
      EVP_DigestSignUpdate(md,envelope.data(),envelope.size())==1;
    std::size_t siglen=0; ok=ok && EVP_DigestSignFinal(md,nullptr,&siglen)==1;
    std::vector<std::uint8_t> sig(siglen); ok=ok && EVP_DigestSignFinal(md,sig.data(),&siglen)==1;
    EVP_MD_CTX_free(md); check(ok && siglen==384,"sign envelope");
    envelope.insert(envelope.end(),sig.begin(),sig.end());
    return envelope;
}

void sign_lease(EVP_PKEY* signer, std::vector<std::uint8_t>& wire) {
    static constexpr char domain[]="GS40T/1/AUTHORITY\0";
    EVP_MD_CTX* ctx=EVP_MD_CTX_new(); EVP_PKEY_CTX* key_ctx=nullptr;
    bool ok=ctx && EVP_DigestSignInit(ctx,&key_ctx,EVP_sha256(),nullptr,signer)==1 &&
      EVP_PKEY_CTX_set_rsa_padding(key_ctx,RSA_PKCS1_PADDING)==1 &&
      EVP_DigestSignUpdate(ctx,domain,sizeof(domain)-1)==1 && EVP_DigestSignUpdate(ctx,wire.data(),wire.size())==1;
    std::size_t size=0; ok=ok && EVP_DigestSignFinal(ctx,nullptr,&size)==1;
    std::vector<std::uint8_t> signature(size); ok=ok && EVP_DigestSignFinal(ctx,signature.data(),&size)==1;
    EVP_MD_CTX_free(ctx); check(ok && size==384,"sign authority lease");
    wire.insert(wire.end(),signature.begin(),signature.end());
}
}

int main() {
    EVP_PKEY* config_root=rsa_key(); EVP_PKEY* time_root=rsa_key();
    EVP_PKEY* authority_root=rsa_key(); EVP_PKEY* client_key=rsa_key();
    check(config_root && time_root && authority_root && client_key,"RSA fixture keys");
    std::string fingerprint;
    const auto cert=pem_cert(client_key,fingerprint);
    const auto client_private=pem_key(client_key);
    const auto config_der=public_der(config_root); const auto time_der=public_der(time_root);
    const auto authority_der=public_der(authority_root);

    Gs40TestOnlyEnvelopeSession session(config_der);
    std::array<std::uint8_t,32> challenge{}; std::vector<std::uint8_t> target_public;
    check(session.begin(challenge,target_public),"session challenge");
    const auto envelope=signed_config(config_root,challenge,target_public,time_der,authority_der,
        cert,client_private,fingerprint);
    Gs40TestOnlyRuntimeConfig config;
    check(session.accept(envelope,config),"valid signed encrypted config");
    check(config.valid_shape() && config.permanent_hub_id=="test-hub-000001" &&
          config.activity_rules_present && config.activity_home_id=="home1" &&
          config.household_timezone=="Etc/UTC" &&
          config.activity_rules.morning_bedroom_location=="bedroom",
          "parsed signed Home activity configuration");
    check(!session.accept(envelope,config),"config envelope replay");
    config.backend_origin="https://api.example.com"; config.backend_hostname="api.example.com";
    check(!config.valid_shape(),"public/commercial endpoint rejected even with signed material");
    config.backend_origin="https://127.0.0.1:0"; config.backend_hostname="127.0.0.1";
    check(!config.valid_shape(),"zero backend port rejected");
    config.backend_origin="https://192.168.50.2:9443"; config.backend_hostname="192.168.50.2";
    check(config.valid_shape(),"isolated private fixture endpoint accepted with exact CA/hostname");
    config.time_host="169.254.169.254";
    check(!config.valid_shape(),"metadata/public signed-time carrier rejected");
    config.backend_origin="https://127.0.0.1:9443"; config.backend_hostname="127.0.0.1"; config.time_host="127.0.0.1";


    Gs40TestOnlyEnvelopeSession tampered_session(config_der);
    std::array<std::uint8_t,32> challenge2{}; std::vector<std::uint8_t> target2;
    check(tampered_session.begin(challenge2,target2),"tamper challenge");
    auto bad=signed_config(config_root,challenge2,target2,time_der,authority_der,cert,client_private,fingerprint);
    bad[110]^=0x10;
    check(!tampered_session.accept(bad,config),"modified envelope rejected");
    check(!tampered_session.accept(bad,config),"failed challenge consumed");

    Gs40TestOnlyEnvelopeSession wrong_root(public_der(time_root));
    std::array<std::uint8_t,32> challenge3{}; std::vector<std::uint8_t> target3;
    check(wrong_root.begin(challenge3,target3),"wrong root challenge");
    auto wrong=signed_config(config_root,challenge3,target3,time_der,authority_der,cert,client_private,fingerprint);
    check(!wrong_root.accept(wrong,config),"wrong config root rejected");

    std::array<std::uint8_t,32> nonce{}; nonce[0]=0xff; nonce[31]=0x80;
    std::vector<std::uint8_t> lease{'G','4','0','A',1};
    lease.insert(lease.end(),nonce.begin(),nonce.end()); put64(lease,7); put64(lease,1700000000);
    put64(lease,1700000060); put64(lease,2); put64(lease,1); put64(lease,3); lease.push_back(1);
    lease.insert(lease.end(),32,0x44); lease.push_back(15);
    const std::string hub="test-hub-000001"; lease.insert(lease.end(),hub.begin(),hub.end());
    lease.push_back(5); const std::string home="home1"; lease.insert(lease.end(),home.begin(),home.end());
    sign_lease(authority_root,lease);
    Gs40TestOnlyAuthorityLeaseVerifier lease_verifier(authority_der);
    Gs40TestOnlyAuthorityLease parsed_lease;
    check(lease_verifier.verify(std::string(lease.begin(),lease.end()),nonce,7,1700000010,5000,parsed_lease),"valid current authority lease");
    check(parsed_lease.binding.home_id==home && parsed_lease.expires_monotonic_ms==55000,"lease binding and bound");
    auto wrong_nonce=nonce; wrong_nonce[1]=1;
    check(!lease_verifier.verify(std::string(lease.begin(),lease.end()),wrong_nonce,7,1700000010,5000,parsed_lease),"lease nonce mismatch");
    check(!lease_verifier.verify(std::string(lease.begin(),lease.end()),nonce,8,1700000010,5000,parsed_lease),"lease boot generation mismatch");
    auto corrupted=lease; corrupted[85]=0;
    check(!lease_verifier.verify(std::string(corrupted.begin(),corrupted.end()),nonce,7,1700000010,5000,parsed_lease),"inactive authority rejected");
    check(!lease_verifier.verify(std::string(lease.begin(),lease.end()),nonce,7,1700000100,5000,parsed_lease),"expired lease rejected");
    std::cout << "GS40 TEST_ONLY bootstrap checks=" << checks << " PASS\n";
    EVP_PKEY_free(config_root); EVP_PKEY_free(time_root); EVP_PKEY_free(authority_root); EVP_PKEY_free(client_key);
}
