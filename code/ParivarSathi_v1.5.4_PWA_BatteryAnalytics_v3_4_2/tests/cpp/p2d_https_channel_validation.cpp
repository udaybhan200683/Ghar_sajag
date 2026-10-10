#include "firmware/hub/target/esp32s3/https_backend_channel.hpp"
#include "esp_http_client.h"
#include "host/security/openssl_commissioning_crypto.hpp"
#include <algorithm>
#include <cstring>
#include <iostream>
#include <stdexcept>

namespace {
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
}
struct FakeHttpClient {
    std::string input, response;
    std::size_t read_offset{0}, initializations{0}, cleanups{0};
    bool open_failed{false}, write_failed{false}, truncated{false}, unknown_length{false};
    std::int64_t clock{0}, step{0};
    int status{201};
} fake;
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t* config) {
    require(config->transport_type == HTTP_TRANSPORT_OVER_SSL && !config->skip_cert_common_name_check &&
            config->disable_auto_redirect && config->cert_pem && std::strlen(config->cert_pem) != 0 &&
            config->timeout_ms <= 3000 && config->buffer_size <= 1024 && config->buffer_size_tx <= 1024,
            "production TLS/hostname/redirect/time/buffer configuration");
    require(std::string(config->url) == "https://backend.invalid/v1/homes/home-1/events", "established endpoint");
    ++fake.initializations; fake.input.clear(); fake.read_offset = 0; return &fake;
}
esp_err_t esp_http_client_set_header(esp_http_client_handle_t, const char*, const char*) { return ESP_OK; }
esp_err_t esp_http_client_open(esp_http_client_handle_t, int) { return fake.open_failed ? -1 : ESP_OK; }
int esp_http_client_write(esp_http_client_handle_t, const char* body, int length) {
    if (fake.write_failed) return -1;
    const int written = std::min(length, 7); fake.input.append(body, written); return written;
}
std::int64_t esp_http_client_fetch_headers(esp_http_client_handle_t) { return fake.unknown_length ? 0 : fake.response.size(); }
int esp_http_client_get_status_code(esp_http_client_handle_t) { return fake.status; }
int esp_http_client_read(esp_http_client_handle_t, char* output, int length) {
    const auto end = fake.truncated && !fake.response.empty() ? fake.response.size() - 1 : fake.response.size();
    const auto bytes = std::min({static_cast<std::size_t>(length), std::size_t{13}, end - fake.read_offset});
    std::memcpy(output, fake.response.data() + fake.read_offset, bytes); fake.read_offset += bytes;
    return static_cast<int>(bytes);
}
bool esp_http_client_is_complete_data_received(esp_http_client_handle_t) { return !fake.truncated && fake.read_offset == fake.response.size(); }
esp_err_t esp_http_client_close(esp_http_client_handle_t) { return ESP_OK; }
esp_err_t esp_http_client_cleanup(esp_http_client_handle_t) { ++fake.cleanups; return ESP_OK; }
std::int64_t esp_timer_get_time() { fake.clock += fake.step; return fake.clock; }

int main() {
    try {
        // Ephemeral bytes, no checked-in credential or key material.
        gs::host::security::OpenSslCommissioningCrypto crypto;
        std::uint8_t random[32]; require(crypto.random_bytes(random, sizeof(random)), "ephemeral input");
        constexpr char digits[] = "0123456789abcdef";
        std::string authorization;
        for (auto byte : random) { authorization += digits[byte >> 4]; authorization += digits[byte & 15]; }
        gs::hub::target::HttpsBackendChannel channel("https://backend.invalid", "public trust input", authorization);
        gs::hub::HttpBackendTransport transport(channel);
        gs::DomainEvent event; event.key = {"room1", 42, 1, "device-room1"}; event.kind = gs::EventKind::Motion;
        gs::hub::BackendCommitRequest request{"home-1", event};
        const std::string receipt = "{\"event_key\":{\"physical_device_id\":\"device-room1\",\"logical_node_id\":\"room1\",\"origin_session_id\":42,\"event_sequence\":1},\"status\":\"COMMITTED\",\"duplicate\":false}";
        for (int mode = 0; mode < 8; ++mode) {
            fake = {}; fake.response = receipt;
            if (mode == 1) fake.open_failed = true;
            if (mode == 2) fake.write_failed = true;
            if (mode == 3) fake.truncated = true;
            if (mode == 4) fake.status = 202;
            if (mode == 5) { fake.response.assign(1025, 'x'); fake.unknown_length = true; }
            if (mode == 6) fake.step = 2000000;
            if (mode == 7) fake.status = 302;
            const auto result = transport.submit(request);
            require((result.status == gs::hub::BackendReplyStatus::Committed) == (mode == 0),
                    "target adapter receipt fail-closed modes");
            require(fake.initializations == fake.cleanups && fake.initializations == 1, "client always cleaned up");
            if (mode == 0) require(fake.input == request.json_body(), "partial writes preserve complete original JSON");
        }
        gs::hub::target::HttpsBackendChannel plaintext("http://backend.invalid", "public trust input", authorization);
        require(!plaintext.post("/v1/homes/home-1/events", request.json_body()).server_authenticated, "plaintext refused");
        gs::hub::target::HttpsBackendChannel unconfigured("https://backend.invalid", "", "");
        require(!unconfigured.post("/v1/homes/home-1/events", request.json_body()).message_complete, "missing trust/auth fails closed");
        std::cout << "p2d_https_channel=PASS modes=8 body_max=2048 response_max=1024 io_buffer=256 deadline_us=5000000\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "p2d_https_channel=FAIL " << error.what() << '\n'; return 1; }
}
