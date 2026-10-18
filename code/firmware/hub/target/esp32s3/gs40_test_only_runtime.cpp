#include "gs40_test_only_runtime.hpp"

#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "mbedtls/pk.h"
#include "psa/crypto.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <sys/socket.h>
#include <sys/time.h>
#include <netdb.h>
#include <unistd.h>

namespace gs::hub::target {
namespace {
extern const std::uint8_t _binary_gs40_test_config_root_der_start[] asm(
    "_binary_gs40_test_config_root_der_start");
extern const std::uint8_t _binary_gs40_test_config_root_der_end[] asm(
    "_binary_gs40_test_config_root_der_end");

std::string hex(const std::uint8_t* bytes, std::size_t size) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(size * 2);
    for (std::size_t i = 0; i < size; ++i) {
        out.push_back(digits[bytes[i] >> 4]);
        out.push_back(digits[bytes[i] & 15]);
    }
    return out;
}

bool read_exact(std::uint8_t* output, std::size_t length, std::uint64_t deadline_us) {
    std::size_t received = 0;
    while (received < length && static_cast<std::uint64_t>(esp_timer_get_time()) < deadline_us) {
        const auto left_us = deadline_us - static_cast<std::uint64_t>(esp_timer_get_time());
        const auto wait_ms = static_cast<std::uint32_t>(std::min<std::uint64_t>(left_us / 1000, 500));
        const int count = usb_serial_jtag_read_bytes(output + received,
            static_cast<std::uint32_t>(length - received), pdMS_TO_TICKS(wait_ms));
        if (count < 0 || static_cast<std::size_t>(count) > length - received) return false;
        received += static_cast<std::size_t>(count);
    }
    return received == length;
}

void append_u64(std::vector<std::uint8_t>& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

}  // namespace

esp_err_t gs40_test_only_receive_config(Gs40TestOnlyRuntimeConfig& config) {
    const auto root_size = static_cast<std::size_t>(
        _binary_gs40_test_config_root_der_end - _binary_gs40_test_config_root_der_start);
    if (root_size == 0 || root_size > 2048) return ESP_ERR_INVALID_STATE;
    std::vector<std::uint8_t> root(_binary_gs40_test_config_root_der_start,
        _binary_gs40_test_config_root_der_start + root_size);
    Gs40TestOnlyEnvelopeSession session(std::move(root));
    std::array<std::uint8_t, 32> challenge{};
    std::vector<std::uint8_t> target_public;
    if (!session.begin(challenge, target_public)) return ESP_FAIL;

    // sdkconfig selects USB Serial/JTAG as the primary console, so ESP-IDF
    // owns driver/VFS installation. Refuse if startup did not install it.
    if (!usb_serial_jtag_is_driver_installed()) return ESP_ERR_INVALID_STATE;
    std::printf("GS40T/1 CHALLENGE nonce=%s public_key=%s max_envelope=%u\n",
        hex(challenge.data(), challenge.size()).c_str(),
        hex(target_public.data(), target_public.size()).c_str(),
        static_cast<unsigned>(Gs40TestOnlyEnvelopeSession::kMaximumEnvelopeBytes));
    std::fflush(stdout);

    const auto deadline = static_cast<std::uint64_t>(esp_timer_get_time()) + 60000000ULL;
    std::array<std::uint8_t, 4> length_bytes{};
    if (!read_exact(length_bytes.data(), length_bytes.size(), deadline)) return ESP_ERR_TIMEOUT;
    const auto length = (static_cast<std::uint32_t>(length_bytes[0]) << 24) |
        (static_cast<std::uint32_t>(length_bytes[1]) << 16) |
        (static_cast<std::uint32_t>(length_bytes[2]) << 8) | length_bytes[3];
    if (length < 517 || length > Gs40TestOnlyEnvelopeSession::kMaximumEnvelopeBytes)
        return ESP_ERR_INVALID_SIZE;
    std::vector<std::uint8_t> envelope(length);
    if (!read_exact(envelope.data(), envelope.size(), deadline)) return ESP_ERR_TIMEOUT;
    if (!session.accept(envelope, config)) return ESP_ERR_INVALID_ARG;
    volatile std::uint8_t* bytes = envelope.data();
    for (std::size_t i = 0; i < envelope.size(); ++i) bytes[i] = 0;
    return ESP_OK;
}

esp_err_t gs40_test_only_bootstrap_time(
    const Gs40TestOnlyRuntimeConfig& config,
    AuthenticatedTimeFloorStore& floor_store,
    AuthenticatedHubTimeProvider& time_provider) {
    if (!config.valid_material_shape() || !time_provider.start()) return ESP_ERR_INVALID_STATE;
    AuthenticatedTimeChallenge challenge;
    if (!time_provider.create_challenge(challenge)) return ESP_FAIL;
    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_DGRAM;
    char service[6]{};
    std::snprintf(service, sizeof(service), "%u", config.time_port);
    addrinfo* addresses = nullptr;
    if (getaddrinfo(config.time_host.c_str(), service, &hints, &addresses) != 0 || addresses == nullptr)
        return ESP_ERR_NOT_FOUND;
    int socket_fd = -1;
    addrinfo* selected = nullptr;
    for (auto* address = addresses; address != nullptr; address = address->ai_next) {
        socket_fd = ::socket(address->ai_family, address->ai_socktype, address->ai_protocol);
        if (socket_fd >= 0) { selected = address; break; }
    }
    if (socket_fd < 0 || selected == nullptr) { freeaddrinfo(addresses); return ESP_FAIL; }
    timeval timeout{2, 0};
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    std::vector<std::uint8_t> request{'G','S','T','Q',1};
    append_u64(request, challenge.boot_generation);
    request.insert(request.end(), challenge.nonce.begin(), challenge.nonce.end());
    const auto sent = sendto(socket_fd, request.data(), request.size(), 0,
        selected->ai_addr, selected->ai_addrlen);
    std::array<std::uint8_t, 457> response{};
    const auto received = sent == static_cast<ssize_t>(request.size())
        ? recv(socket_fd, response.data(), response.size(), 0) : -1;
    close(socket_fd);
    freeaddrinfo(addresses);
    if (received != 456) return received < 0 ? ESP_ERR_TIMEOUT : ESP_ERR_INVALID_SIZE;
    std::vector<std::uint8_t> proof(response.begin(), response.begin() + received);
    if (!time_provider.accept_authenticated_time(proof)) return ESP_ERR_INVALID_RESPONSE;
    TrustedHubTimeSnapshot snapshot;
    const auto now_ms = static_cast<Milliseconds>(esp_timer_get_time() / 1000);
    if (!time_provider.trusted_hub_time(now_ms, snapshot) || !snapshot.trusted || snapshot.utc_now <= 0 ||
        static_cast<std::uint64_t>(snapshot.utc_now) >= config.envelope_expiry_utc)
        return ESP_ERR_INVALID_STATE;
    timeval clock{};
    clock.tv_sec = static_cast<time_t>(snapshot.utc_now);
    if (static_cast<std::int64_t>(clock.tv_sec) != snapshot.utc_now || settimeofday(&clock, nullptr) != 0)
        return ESP_FAIL;
    (void)floor_store;
    return ESP_OK;
}

esp_err_t gs40_test_only_connect_wifi(Gs40TestOnlyRuntimeConfig& config) {
    if (!config.valid_shape()) return ESP_ERR_INVALID_ARG;
    wifi_config_t station{};
    if (config.wifi_ssid.size() >= sizeof(station.sta.ssid) ||
        config.wifi_psk.size() >= sizeof(station.sta.password)) return ESP_ERR_INVALID_SIZE;
    std::memcpy(station.sta.ssid, config.wifi_ssid.data(), config.wifi_ssid.size());
    std::memcpy(station.sta.password, config.wifi_psk.data(), config.wifi_psk.size());
    station.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    auto result = esp_wifi_set_config(WIFI_IF_STA, &station);
    volatile std::uint8_t* station_secret = station.sta.password;
    for (std::size_t i = 0; i < sizeof(station.sta.password); ++i) station_secret[i] = 0;
    config.clear_wifi_secret();
    if (result != ESP_OK) return result;
    result = esp_wifi_connect();
    if (result != ESP_OK) return result;
    const auto deadline = static_cast<std::uint64_t>(esp_timer_get_time()) + 20000000ULL;
    while (static_cast<std::uint64_t>(esp_timer_get_time()) < deadline) {
        wifi_ap_record_t ap{};
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            return ap.primary == 1 ? ESP_OK : ESP_ERR_INVALID_STATE;
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
    return ESP_ERR_TIMEOUT;
}

}  // namespace gs::hub::target
