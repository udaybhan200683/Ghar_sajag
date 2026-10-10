#include "https_backend_channel.hpp"
#include "esp_http_client.h"
#include "esp_timer.h"
#include <utility>

namespace gs::hub::target {
HttpsBackendChannel::HttpsBackendChannel(std::string origin, std::string trusted_ca,
                                         std::string authorization)
    : origin_(std::move(origin)), trusted_ca_(std::move(trusted_ca)),
      authorization_(std::move(authorization)) {}
HttpsBackendChannel::~HttpsBackendChannel() {
    volatile char* secret = authorization_.data();
    for (std::size_t i = 0; i < authorization_.size(); ++i) secret[i] = 0;
}
BackendHttpResponse HttpsBackendChannel::post(const std::string& path, const std::string& body) {
    BackendHttpResponse result;
    const auto deadline = esp_timer_get_time() + 5000000;
    // A fixed HTTPS origin; no userinfo, fragments, queries, redirects or paths.
    if (origin_.compare(0, 8, "https://") != 0 || origin_.size() > 256 ||
        origin_.size() == 8 || origin_.find_first_of("/@?#\r\n", 8) != std::string::npos ||
        trusted_ca_.empty() || trusted_ca_.size() > 8192 || authorization_.empty() ||
        authorization_.size() > 1024 || authorization_.find_first_of("\r\n") != std::string::npos ||
        path.compare(0, 10, "/v1/homes/") != 0 || path.size() > 128 ||
        body.empty() || body.size() > HttpBackendTransport::kMaximumRequestBytes) return result;
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
    auto client = esp_http_client_init(&config);
    if (client == nullptr) return result;
    struct Cleanup {
        esp_http_client_handle_t client;
        ~Cleanup() { esp_http_client_close(client); esp_http_client_cleanup(client); }
    } cleanup{client};
    if (esp_http_client_set_header(client, "Content-Type", "application/json") != ESP_OK ||
        esp_http_client_set_header(client, "Authorization", authorization_.c_str()) != ESP_OK ||
        esp_http_client_open(client, static_cast<int>(body.size())) != ESP_OK) return result;
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
