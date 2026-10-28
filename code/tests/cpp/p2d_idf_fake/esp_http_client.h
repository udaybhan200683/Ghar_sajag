#pragma once
#include <cstdint>
using esp_err_t = int;
constexpr esp_err_t ESP_OK = 0;
enum esp_http_client_transport_t { HTTP_TRANSPORT_OVER_SSL };
enum esp_http_client_method_t { HTTP_METHOD_GET, HTTP_METHOD_POST };
enum esp_http_client_tls_version_t { ESP_HTTP_CLIENT_TLS_VER_TLS_1_2 };
struct esp_http_client_config_t {
    const char* url{};
    const char* cert_pem{};
    const char* client_cert_pem{};
    const char* client_key_pem{};
    void* ds_data{};
    esp_http_client_transport_t transport_type{};
    esp_http_client_tls_version_t tls_version{};
    bool skip_cert_common_name_check{};
    bool disable_auto_redirect{};
    int timeout_ms{}, buffer_size{}, buffer_size_tx{};
    esp_http_client_method_t method{};
};
struct FakeHttpClient;
using esp_http_client_handle_t = FakeHttpClient*;
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t*);
esp_err_t esp_http_client_set_header(esp_http_client_handle_t, const char*, const char*);
esp_err_t esp_http_client_open(esp_http_client_handle_t, int);
int esp_http_client_write(esp_http_client_handle_t, const char*, int);
std::int64_t esp_http_client_fetch_headers(esp_http_client_handle_t);
int esp_http_client_get_status_code(esp_http_client_handle_t);
int esp_http_client_read(esp_http_client_handle_t, char*, int);
bool esp_http_client_is_complete_data_received(esp_http_client_handle_t);
esp_err_t esp_http_client_close(esp_http_client_handle_t);
esp_err_t esp_http_client_cleanup(esp_http_client_handle_t);
