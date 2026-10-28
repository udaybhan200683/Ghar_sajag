#pragma once
#include "cloud_sync/http_backend_transport.hpp"
#include <cstdint>

namespace gs::hub::target {
// Restricted cloud TLS identity. The provider owns the opaque DS context for
// the entire request. No private key or arbitrary sign operation is exposed.
// A future GS-165/172 adapter supplies a separately approved per-Hub identity.
struct CloudTlsIdentity {
    std::string client_certificate_pem;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    // Isolated software-key path. This field is absent from normal product
    // builds and is accepted only for identities explicitly marked TEST_ONLY.
    std::string test_only_client_private_key_pem;
    bool test_only_software_identity{false};
#endif
    void* ds_context{nullptr};
    unsigned rsa_bits{0};
    std::string permanent_hub_id;
    std::string certificate_fingerprint_sha256;
    std::uint64_t credential_generation{0};
    std::int64_t trusted_utc_seconds{0};
    std::int64_t trusted_monotonic_ms{0};
    std::uint64_t trusted_time_boot_generation{0};
    enum class Purpose { CloudTlsClient, Commissioning } purpose{Purpose::Commissioning};
};
class CloudTlsIdentityProvider {
public:
    virtual ~CloudTlsIdentityProvider() = default;
    virtual bool current_identity(CloudTlsIdentity& identity) = 0;
};
// Deployment supplies the existing endpoint's trust anchor and opaque HTTP
// Authorization value. This does not define or provision a credential scheme.
// No secrets/configuration are compiled into the firmware. Missing configuration
// refuses all requests. Production Hub middleware/provisioning remains a gate.
class HttpsBackendChannel final : public BackendHttpChannel {
public:
    HttpsBackendChannel(std::string origin, std::string trusted_ca,
                        std::string authorization);
    HttpsBackendChannel(std::string origin, std::string trusted_ca,
                        CloudTlsIdentityProvider& cloud_identity);
    ~HttpsBackendChannel() override;
    BackendHttpResponse post(const std::string& path, const std::string& body) override;
    BackendHttpResponse get(const std::string& path) override;
private:
    BackendHttpResponse request(const std::string& path, const std::string& body,
                                bool get_request);
    std::string origin_, trusted_ca_, authorization_;
    CloudTlsIdentityProvider* cloud_identity_{nullptr};
};
}
