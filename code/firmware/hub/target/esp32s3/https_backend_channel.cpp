#include "https_backend_channel.hpp"
#include "esp_http_client.h"
#include "esp_timer.h"
#include <utility>
#if defined(ESP_PLATFORM)
#include <sys/time.h>
#include <time.h>
#endif

#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD && \
    CONFIG_ESP_TLS_USE_DS_PERIPHERAL
#error "GS-40 TEST_ONLY software-key profile must disable ESP-TLS DS mode"
#endif

namespace gs::hub::target {
namespace {
bool valid_cloud_identity_reference(const CloudTlsIdentity& identity) {
    if (identity.permanent_hub_id.empty() || identity.permanent_hub_id.size() > 64 ||
        identity.credential_generation == 0 ||
        identity.certificate_fingerprint_sha256.size() != 64) return false;
    for (const auto ch : identity.certificate_fingerprint_sha256) {
        if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return false;
    }
    return true;
}
}

HttpsBackendChannel::HttpsBackendChannel(std::string origin, std::string trusted_ca,
                                         std::string authorization)
    : origin_(std::move(origin)), trusted_ca_(std::move(trusted_ca)),
      authorization_(std::move(authorization)) {}
HttpsBackendChannel::HttpsBackendChannel(std::string origin, std::string trusted_ca,
                                         CloudTlsIdentityProvider& cloud_identity)
    : origin_(std::move(origin)), trusted_ca_(std::move(trusted_ca)),
      cloud_identity_(&cloud_identity) {}
HttpsBackendChannel::~HttpsBackendChannel() {
    volatile char* secret = authorization_.data();
    for (std::size_t i = 0; i < authorization_.size(); ++i) secret[i] = 0;
}
BackendHttpResponse HttpsBackendChannel::post(const std::string& path, const std::string& body) {
    BackendHttpResponse result;
    const auto deadline = esp_timer_get_time() + 5000000;
    CloudTlsIdentity identity;
    bool test_only_software_identity = false;
    if (cloud_identity_ != nullptr) {
        if (!cloud_identity_->current_identity(identity)) return result;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
        test_only_software_identity = identity.test_only_software_identity &&
            identity.ds_context == nullptr &&
            !identity.test_only_client_private_key_pem.empty();
#endif
        if (
            identity.purpose != CloudTlsIdentity::Purpose::CloudTlsClient ||
            identity.rsa_bits != 3072 ||
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
            (!test_only_software_identity && identity.ds_context == nullptr) ||
            (test_only_software_identity &&
             (identity.ds_context != nullptr ||
              identity.test_only_client_private_key_pem.empty())) ||
#else
            identity.ds_context == nullptr ||
#endif
            identity.trusted_utc_seconds <= 0 ||
            identity.trusted_monotonic_ms <= 0 ||
            identity.trusted_time_boot_generation == 0 ||
            !valid_cloud_identity_reference(identity) ||
            identity.client_certificate_pem.empty() ||
            identity.client_certificate_pem.size() > 8192 ||
            identity.client_certificate_pem.find("-----BEGIN CERTIFICATE-----") != 0 ||
            !authorization_.empty()) return result;
#if !CONFIG_ESP_TLS_USE_DS_PERIPHERAL
#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
        // The SDK must be built with DS-backed ESP-TLS. Never fall back to a
        // software key, commissioning key or bearer authorization.
        return result;
#else
        if (!test_only_software_identity) return result;
#endif
#endif
#if CONFIG_ESP_TLS_USE_DS_PERIPHERAL
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (test_only_software_identity) return result;
#endif
#else
#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (cloud_identity_ != nullptr) return result;
#else
    if (!test_only_software_identity) return result;
#endif
#endif
    }
    // A fixed HTTPS origin; no userinfo, fragments, queries, redirects or paths.
    const bool node_health_path = path.compare(0, 10, "/v1/homes/") == 0;
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    const bool test_authority_path = path == "/v1/test/authority/refresh" &&
        test_only_software_identity;
#else
    constexpr bool test_authority_path = false;
#endif
    if (origin_.compare(0, 8, "https://") != 0 || origin_.size() > 256 ||
        origin_.size() == 8 || origin_.find_first_of("/@?#\r\n", 8) != std::string::npos ||
        trusted_ca_.empty() || trusted_ca_.size() > 8192 ||
        (cloud_identity_ == nullptr && authorization_.empty()) ||
        authorization_.size() > 1024 || authorization_.find_first_of("\r\n") != std::string::npos ||
        (!node_health_path && !test_authority_path) || path.size() > 128 ||
        body.empty() || body.size() > HttpBackendTransport::kMaximumRequestBytes) return result;
#if defined(ESP_PLATFORM)
    if (cloud_identity_ != nullptr) {
        // ESP-TLS validates X.509 validity using the system clock. Set that
        // clock only from the provider's authenticated snapshot; unauthenticated
        // SNTP/wall-clock values never establish readiness or this TLS time.
        const auto trusted_time = static_cast<time_t>(identity.trusted_utc_seconds);
        if (trusted_time <= 0 ||
            static_cast<std::int64_t>(trusted_time) != identity.trusted_utc_seconds)
            return result;
        timeval tv{};
        tv.tv_sec = trusted_time;
        tv.tv_usec = 0;
        if (settimeofday(&tv, nullptr) != 0) return result;
    }
#endif
    const auto url = origin_ + path;
    esp_http_client_config_t config{};
    config.url = url.c_str();
    config.cert_pem = trusted_ca_.c_str();
    config.transport_type = HTTP_TRANSPORT_OVER_SSL;
    config.skip_cert_common_name_check = false;
    config.disable_auto_redirect = true;
    config.timeout_ms = 3000;
    config.buffer_size = 1024;
    config.buffer_size_tx = 1024;
    config.method = HTTP_METHOD_POST;
#if CONFIG_ESP_TLS_USE_DS_PERIPHERAL
    if (cloud_identity_ != nullptr && !test_only_software_identity) {
        // Candidate profile exercised by the host mTLS integration and current
        // ESP-IDF 6.0.3 S3 build. Production TLS-profile approval is still pending.
        config.tls_version = ESP_HTTP_CLIENT_TLS_VER_TLS_1_2;
        config.client_cert_pem = identity.client_certificate_pem.c_str();
        config.ds_data = identity.ds_context;
    }
#endif
#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD
    if (test_only_software_identity) {
        config.tls_version = ESP_HTTP_CLIENT_TLS_VER_TLS_1_2;
        config.client_cert_pem = identity.client_certificate_pem.c_str();
        config.client_key_pem = identity.test_only_client_private_key_pem.c_str();
    }
#endif
    auto client = esp_http_client_init(&config);
    if (client == nullptr) return result;
    struct Cleanup {
        esp_http_client_handle_t client;
        ~Cleanup() { esp_http_client_close(client); esp_http_client_cleanup(client); }
    } cleanup{client};
    if (esp_http_client_set_header(client, "Content-Type", "application/json") != ESP_OK ||
        (cloud_identity_ == nullptr &&
         esp_http_client_set_header(client, "Authorization", authorization_.c_str()) != ESP_OK)) return result;
    result.network_attempted = true;
    if (esp_http_client_open(client, static_cast<int>(body.size())) != ESP_OK) return result;
    std::size_t sent = 0;
    while (sent < body.size()) {
        if (esp_timer_get_time() >= deadline) return result;
        const int written = esp_http_client_write(client, body.data() + sent,
                                                  static_cast<int>(body.size() - sent));
        if (written <= 0 || static_cast<std::size_t>(written) > body.size() - sent) return result;
        sent += static_cast<std::size_t>(written);
    }
    const auto length = esp_http_client_fetch_headers(client);
    if (length < 0 || length > static_cast<std::int64_t>(HttpBackendTransport::kMaximumResponseBytes)) return result;
    result.status = static_cast<unsigned>(esp_http_client_get_status_code(client));
    // open completed SSL handshake with required CA and hostname verification.
    // A later framing/read error still cannot make this a usable receipt.
    result.server_authenticated = true;
    char buffer[256];
    for (std::size_t reads = 0; reads <= HttpBackendTransport::kMaximumResponseBytes; ++reads) {
        if (esp_timer_get_time() >= deadline) return result;
        const int received = esp_http_client_read(client, buffer, sizeof(buffer));
        if (received < 0) return result;
        if (received == 0) break;
        if (result.body.size() + static_cast<std::size_t>(received) > HttpBackendTransport::kMaximumResponseBytes)
            return result;
        result.body.append(buffer, static_cast<std::size_t>(received));
    }
    result.message_complete = esp_timer_get_time() < deadline &&
        esp_http_client_is_complete_data_received(client);
    return result;
}
}
