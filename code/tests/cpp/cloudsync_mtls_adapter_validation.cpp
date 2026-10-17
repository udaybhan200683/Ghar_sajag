#include "firmware/hub/target/esp32s3/https_backend_channel.hpp"
#include "esp_http_client.h"
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>

struct FakeHttpClient { bool opened{false}; };
namespace {
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
struct Provider final : gs::hub::target::CloudTlsIdentityProvider {
    bool available{true};
    gs::hub::target::CloudTlsIdentity value;
    Provider() {
        value.client_certificate_pem =
            "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
        value.ds_context = reinterpret_cast<void*>(0x1);
        value.rsa_bits = 3072;
        value.permanent_hub_id = "test-hub-permanent";
        value.certificate_fingerprint_sha256 = std::string(64, 'a');
        value.credential_generation = 1;
        value.trusted_utc_seconds = 1'800'000'000;
        value.trusted_monotonic_ms = 1;
        value.trusted_time_boot_generation = 1;
        value.purpose = gs::hub::target::CloudTlsIdentity::Purpose::CloudTlsClient;
    }
    bool current_identity(gs::hub::target::CloudTlsIdentity& output) override {
        if (!available) return false;
        output = value;
        return true;
    }
};
FakeHttpClient client;
unsigned initialized = 0, cleaned = 0, authorization_headers = 0;
std::string certificate;
void* ds_context = nullptr;
}  // namespace

esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t* config) {
    check(config && config->client_cert_pem && config->ds_data && config->cert_pem &&
          config->transport_type == HTTP_TRANSPORT_OVER_SSL &&
          config->tls_version == ESP_HTTP_CLIENT_TLS_VER_TLS_1_2 &&
          !config->skip_cert_common_name_check && config->disable_auto_redirect,
          "DS client cert and verified server TLS required");
    certificate = config->client_cert_pem;
    ds_context = config->ds_data;
    ++initialized;
    return &client;
}
esp_err_t esp_http_client_set_header(esp_http_client_handle_t, const char* name, const char*) {
    if (std::strcmp(name, "Authorization") == 0) ++authorization_headers;
    return ESP_OK;
}
esp_err_t esp_http_client_open(esp_http_client_handle_t, int) { client.opened = true; return ESP_OK; }
int esp_http_client_write(esp_http_client_handle_t, const char*, int length) { return length; }
std::int64_t esp_http_client_fetch_headers(esp_http_client_handle_t) { return 2; }
int esp_http_client_get_status_code(esp_http_client_handle_t) { return 201; }
int esp_http_client_read(esp_http_client_handle_t, char* buffer, int) {
    static bool read = false;
    if (read) { read = false; return 0; }
    buffer[0] = '{'; buffer[1] = '}'; read = true; return 2;
}
bool esp_http_client_is_complete_data_received(esp_http_client_handle_t) { return true; }
esp_err_t esp_http_client_close(esp_http_client_handle_t) { return ESP_OK; }
esp_err_t esp_http_client_cleanup(esp_http_client_handle_t) { ++cleaned; return ESP_OK; }
std::int64_t esp_timer_get_time() { return 1; }

int main() {
    try {
        Provider provider;
        gs::hub::target::HttpsBackendChannel channel("https://backend.invalid", "test CA", provider);
        constexpr auto path = "/v1/homes/home-1/events";
        auto success = channel.post(path, "{}");
        check(success.server_authenticated && success.message_complete && success.network_attempted && initialized == 1 &&
              cleaned == 1 && authorization_headers == 0 && ds_context == provider.value.ds_context &&
              certificate == provider.value.client_certificate_pem, "mTLS DS path without bearer fallback");
        std::cout << "GS-CLOUD-MTLS-UT-001 PASS\n";
        provider.available = false;
        const auto missing_identity = channel.post(path, "{}");
        check(!missing_identity.server_authenticated && !missing_identity.network_attempted && initialized == 1,
              "missing identity refused before network attempt");
        std::cout << "GS-CLOUD-MTLS-UT-002 PASS\n";
        provider.available = true;
        provider.value.purpose = gs::hub::target::CloudTlsIdentity::Purpose::Commissioning;
        check(!channel.post(path, "{}").server_authenticated && initialized == 1, "commissioning purpose refused");
        std::cout << "GS-CLOUD-MTLS-UT-003 PASS\n";
        provider.value.purpose = gs::hub::target::CloudTlsIdentity::Purpose::CloudTlsClient;
        provider.value.rsa_bits = 2048;
        check(!channel.post(path, "{}").server_authenticated && initialized == 1, "wrong RSA size refused");
        std::cout << "GS-CLOUD-MTLS-UT-004 PASS\n";
        provider.value.rsa_bits = 3072;
        provider.value.ds_context = nullptr;
        check(!channel.post(path, "{}").server_authenticated && initialized == 1, "missing DS context refused");
        std::cout << "GS-CLOUD-MTLS-UT-005 PASS\n";
        provider.value.ds_context = reinterpret_cast<void*>(0x1);
        provider.value.client_certificate_pem = "bad certificate";
        check(!channel.post(path, "{}").server_authenticated && initialized == 1, "malformed cert refused");
        std::cout << "GS-CLOUD-MTLS-UT-006 PASS\n";
        provider.value.client_certificate_pem = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
        gs::hub::target::HttpsBackendChannel no_ca("https://backend.invalid", "", provider);
        check(!no_ca.post(path, "{}").server_authenticated && initialized == 1, "missing CA refused");
        std::cout << "GS-CLOUD-MTLS-UT-007 PASS\n";
        check(channel.post(path, "{}").server_authenticated && initialized == 2 && cleaned == 2 &&
              authorization_headers == 0, "repeat initialization and cleanup");
        std::cout << "GS-CLOUD-MTLS-UT-008 PASS\n";
        provider.value.trusted_utc_seconds = 0;
        check(!channel.post(path, "{}").server_authenticated && initialized == 2,
              "untrusted time is refused before TLS initialization");
        std::cout << "GS-CLOUD-MTLS-UT-009 PASS\n";
        std::cout << "CLOUDSYNC MTLS ADAPTER PASS cases=9 physical=NOT_RUN\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "CLOUDSYNC MTLS ADAPTER FAIL " << error.what() << '\n';
        return 1;
    }
}
