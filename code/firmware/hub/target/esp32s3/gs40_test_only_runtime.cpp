#include "gs40_test_only_runtime.hpp"
#include "gs40_test_only_wifi.hpp"

#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "driver/uart.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "cJSON.h"
#include "firmware/hub/lifecycle/configuration/config_service.hpp"
#include "firmware/hub/cloud_sync/http_backend_transport.hpp"
#include "freertos/FreeRTOS.h"
#include "mbedtls/pk.h"
#include "psa/crypto.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <limits>
#include <set>
#include <string_view>
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

bool read_exact(std::uint8_t* output, std::size_t length,
                std::uint64_t deadline_us, std::size_t* received_bytes = nullptr) {
    std::size_t received = 0;
    if (received_bytes != nullptr) *received_bytes = 0;
    while (received < length && static_cast<std::uint64_t>(esp_timer_get_time()) < deadline_us) {
        const auto left_us = deadline_us - static_cast<std::uint64_t>(esp_timer_get_time());
        const auto wait_ms = static_cast<std::uint32_t>(std::min<std::uint64_t>(left_us / 1000, 500));
#if CONFIG_ESP_CONSOLE_UART_NUM == 0
        const int count = uart_read_bytes(UART_NUM_0, output + received,
            static_cast<std::uint32_t>(length - received), pdMS_TO_TICKS(wait_ms));
#else
        const int count = usb_serial_jtag_read_bytes(output + received,
            static_cast<std::uint32_t>(length - received), pdMS_TO_TICKS(wait_ms));
#endif
        if (count < 0 || static_cast<std::size_t>(count) > length - received) return false;
        received += static_cast<std::size_t>(count);
        if (received_bytes != nullptr) *received_bytes = received;
    }
    return received == length;
}

void append_u64(std::vector<std::uint8_t>& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

bool only_members(const cJSON* object,
                  std::initializer_list<std::string_view> allowed) {
    if (!cJSON_IsObject(object)) return false;
    for (const auto* member = object->child; member != nullptr; member = member->next) {
        if (member->string == nullptr || std::none_of(allowed.begin(), allowed.end(),
                [&](std::string_view key) { return key == member->string; })) return false;
    }
    return true;
}

bool json_boolean(const cJSON* object, const char* key, bool& value,
                  bool required = false) {
    const auto* item = cJSON_GetObjectItemCaseSensitive(object, key);
    if (item == nullptr) return !required;
    if (!cJSON_IsBool(item)) return false;
    value = cJSON_IsTrue(item);
    return true;
}

bool json_integer(const cJSON* object, const char* key, std::int64_t& value,
                  std::int64_t minimum, std::int64_t maximum,
                  bool required = false) {
    const auto* item = cJSON_GetObjectItemCaseSensitive(object, key);
    if (item == nullptr) return !required;
    if (!cJSON_IsNumber(item) || !std::isfinite(item->valuedouble) ||
        std::trunc(item->valuedouble) != item->valuedouble ||
        item->valuedouble < static_cast<double>(minimum) ||
        item->valuedouble > static_cast<double>(maximum)) return false;
    value = static_cast<std::int64_t>(item->valuedouble);
    return true;
}

bool json_ascii(const cJSON* object, const char* key, std::string& value,
                std::size_t maximum, bool required = false) {
    const auto* item = cJSON_GetObjectItemCaseSensitive(object, key);
    if (item == nullptr) return !required;
    if (!cJSON_IsString(item) || item->valuestring == nullptr) return false;
    value = item->valuestring;
    if (value.empty() || value.size() > maximum) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return ch >= 0x21 && ch <= 0x7e;
    });
}

bool parse_mode(const cJSON* object, gs::HomeMode& mode) {
    std::string value = "HOME";
    if (!json_ascii(object, "mode", value, 16)) return false;
    if (value == "HOME") mode = gs::HomeMode::Home;
    else if (value == "AWAY") mode = gs::HomeMode::Away;
    else if (value == "PAUSED") mode = gs::HomeMode::Paused;
    else if (value == "VISITOR") mode = gs::HomeMode::Visitor;
    else if (value == "PRIVACY") mode = gs::HomeMode::Privacy;
    else return false;
    return true;
}

bool parse_activity_rules(const cJSON* object, bool morning_enabled,
                          std::uint16_t morning_start,
                          std::uint16_t morning_end,
                          gs::ActivityRuleConfig& rules) {
    if (!only_members(object, {
            "quiet_hours_enabled", "quiet_start_minute", "quiet_end_minute",
            "door_open_timeout_seconds", "daytime_inactivity_enabled",
            "daytime_start_minute", "daytime_end_minute", "daytime_inactivity_seconds",
            "morning_sequence_enabled", "morning_start_minute", "morning_end_minute",
            "morning_sequence_window_seconds", "morning_bedroom_location",
            "morning_bathroom_location", "morning_kitchen_location",
            "morning_sequence_strict_order", "morning_steps", "night_activity_enabled",
            "night_start_minute", "night_end_minute", "night_bathroom_location",
            "night_bathroom_visit_threshold", "night_common_location",
            "night_common_visit_threshold", "night_visit_merge_seconds",
            "post_door_inactivity_enabled", "post_door_inactivity_seconds"})) return false;
    std::int64_t number = 0;
    if (!json_boolean(object, "quiet_hours_enabled", rules.quiet_hours_enabled) ||
        !json_boolean(object, "daytime_inactivity_enabled", rules.daytime_inactivity_enabled) ||
        !json_boolean(object, "morning_sequence_enabled", rules.morning_sequence_enabled) ||
        !json_boolean(object, "night_activity_enabled", rules.night_activity_enabled) ||
        !json_boolean(object, "post_door_inactivity_enabled", rules.post_door_inactivity_enabled) ||
        !json_boolean(object, "morning_sequence_strict_order", rules.morning_sequence_strict_order))
        return false;

    number = rules.quiet_start_minute;
    if (!json_integer(object, "quiet_start_minute", number, 0, 1439)) return false;
    rules.quiet_start_minute = static_cast<std::uint16_t>(number);
    number = rules.quiet_end_minute;
    if (!json_integer(object, "quiet_end_minute", number, 0, 1439)) return false;
    rules.quiet_end_minute = static_cast<std::uint16_t>(number);
    number = rules.door_open_timeout_seconds;
    if (!json_integer(object, "door_open_timeout_seconds", number, 30, 86400)) return false;
    rules.door_open_timeout_seconds = number;
    number = rules.daytime_start_minute;
    if (!json_integer(object, "daytime_start_minute", number, 0, 1439)) return false;
    rules.daytime_start_minute = static_cast<std::uint16_t>(number);
    number = rules.daytime_end_minute;
    if (!json_integer(object, "daytime_end_minute", number, 0, 1439)) return false;
    rules.daytime_end_minute = static_cast<std::uint16_t>(number);
    number = rules.daytime_inactivity_seconds;
    if (!json_integer(object, "daytime_inactivity_seconds", number, 300, 86400)) return false;
    rules.daytime_inactivity_seconds = number;
    number = morning_start;
    if (!json_integer(object, "morning_start_minute", number, 0, 1439) || number != morning_start)
        return false;
    rules.morning_start_minute = morning_start;
    number = morning_end;
    if (!json_integer(object, "morning_end_minute", number, 0, 1439) || number != morning_end)
        return false;
    rules.morning_end_minute = morning_end;
    if (cJSON_GetObjectItemCaseSensitive(object, "morning_sequence_enabled") != nullptr &&
        rules.morning_sequence_enabled != morning_enabled) return false;
    rules.morning_sequence_enabled = morning_enabled;
    number = rules.morning_sequence_window_seconds;
    if (!json_integer(object, "morning_sequence_window_seconds", number, 1, 86400)) return false;
    rules.morning_sequence_window_seconds = number;
    if (!json_ascii(object, "morning_bedroom_location", rules.morning_bedroom_location, 32) ||
        !json_ascii(object, "morning_bathroom_location", rules.morning_bathroom_location, 32) ||
        !json_ascii(object, "morning_kitchen_location", rules.morning_kitchen_location, 32)) return false;
    if (!json_boolean(object, "night_activity_enabled", rules.night_activity_enabled) ||
        !json_boolean(object, "post_door_inactivity_enabled", rules.post_door_inactivity_enabled)) return false;
    number = rules.night_start_minute;
    if (!json_integer(object, "night_start_minute", number, 0, 1439)) return false;
    rules.night_start_minute = static_cast<std::uint16_t>(number);
    number = rules.night_end_minute;
    if (!json_integer(object, "night_end_minute", number, 0, 1439)) return false;
    rules.night_end_minute = static_cast<std::uint16_t>(number);
    if (!json_ascii(object, "night_bathroom_location", rules.night_bathroom_location, 32) ||
        !json_ascii(object, "night_common_location", rules.night_common_location, 32)) return false;
    number = rules.night_bathroom_visit_threshold;
    if (!json_integer(object, "night_bathroom_visit_threshold", number, 1, 32)) return false;
    rules.night_bathroom_visit_threshold = static_cast<std::uint16_t>(number);
    number = rules.night_common_visit_threshold;
    if (!json_integer(object, "night_common_visit_threshold", number, 1, 32)) return false;
    rules.night_common_visit_threshold = static_cast<std::uint16_t>(number);
    number = rules.night_visit_merge_seconds;
    if (!json_integer(object, "night_visit_merge_seconds", number, 1, 86400)) return false;
    rules.night_visit_merge_seconds = number;
    number = rules.post_door_inactivity_seconds;
    if (!json_integer(object, "post_door_inactivity_seconds", number, 300, 86400)) return false;
    rules.post_door_inactivity_seconds = number;

    const auto* steps = cJSON_GetObjectItemCaseSensitive(object, "morning_steps");
    if (!cJSON_IsArray(steps) || cJSON_GetArraySize(steps) < 1 ||
        cJSON_GetArraySize(steps) > 24) return false;
    rules.morning_steps.clear();
    std::set<std::string> locations;
    for (const auto* item = steps->child; item != nullptr; item = item->next) {
        if (!only_members(item, {"location", "enabled", "required"})) return false;
        gs::MorningRoutineStep step;
        if (!json_ascii(item, "location", step.location, 32, true) ||
            !json_boolean(item, "enabled", step.enabled, true) ||
            !json_boolean(item, "required", step.required, true) ||
            !locations.insert(step.location).second) return false;
        rules.morning_steps.push_back(std::move(step));
    }
    return true;
}

bool parse_desired_config(const std::string& json, const std::string& expected_home,
                          std::uint32_t& version, gs::HomeConfig& home) {
    const char* parse_end = nullptr;
    auto* root = cJSON_ParseWithLengthOpts(json.c_str(), json.size(), &parse_end, 0);
    if (root == nullptr) return false;
    struct JsonCleanup { cJSON* value; ~JsonCleanup() { cJSON_Delete(value); } } cleanup{root};
    const auto* end = parse_end;
    const auto* limit = json.c_str() + json.size();
    while (end != nullptr && end < limit && (*end == ' ' || *end == '\r' ||
            *end == '\n' || *end == '\t')) ++end;
    if (end != limit || !only_members(root, {"home_id", "version", "schema", "status",
                                            "config", "applied_version"}) ||
        cJSON_GetArraySize(root) != 6) return false;
    std::string home_id, status;
    if (!json_ascii(root, "home_id", home_id, 128, true) || home_id != expected_home)
        return false;
    std::int64_t schema = 0, numeric_version = 0;
    if (!json_integer(root, "schema", schema, 1, 1, true) ||
        !json_integer(root, "version", numeric_version, 0,
                      std::numeric_limits<std::uint32_t>::max(), true)) return false;
    version = static_cast<std::uint32_t>(numeric_version);
    const auto* body = cJSON_GetObjectItemCaseSensitive(root, "config");
    const auto* applied = cJSON_GetObjectItemCaseSensitive(root, "applied_version");
    if (version == 0)
        return cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(root, "status")) &&
            cJSON_IsNull(body) && cJSON_IsNull(applied);
    if (!json_ascii(root, "status", status, 16, true)) return false;
    std::int64_t applied_version = 0;
    if (cJSON_IsNull(applied)) {
        applied_version = 0;
    } else if (!json_integer(root, "applied_version", applied_version, 0,
                             std::numeric_limits<std::uint32_t>::max(), true)) {
        return false;
    }
    if ((!status.empty() && status != "DESIRED" && status != "APPLIED") ||
        (status == "APPLIED" && applied_version != version) ||
        (status == "DESIRED" && applied_version >= version) ||
        !only_members(body, {"timezone", "mode", "morning", "activity_rules"}) ||
        cJSON_GetArraySize(body) != 4) return false;

    home = gs::HomeConfig{};
    home.version = version;
    home.home_id = home_id;
    if (!json_ascii(body, "timezone", home.timezone, 64, true) ||
        !parse_mode(body, home.mode)) return false;
    const auto* morning = cJSON_GetObjectItemCaseSensitive(body, "morning");
    const auto* rules = cJSON_GetObjectItemCaseSensitive(body, "activity_rules");
    if (!only_members(morning, {"enabled", "start_minute", "end_minute", "grace_minutes"}) ||
        !only_members(rules, {"quiet_hours_enabled", "quiet_start_minute", "quiet_end_minute",
            "door_open_timeout_seconds", "daytime_inactivity_enabled", "daytime_start_minute",
            "daytime_end_minute", "daytime_inactivity_seconds", "morning_sequence_enabled",
            "morning_start_minute", "morning_end_minute", "morning_sequence_window_seconds",
            "morning_bedroom_location", "morning_bathroom_location", "morning_kitchen_location",
            "morning_sequence_strict_order", "morning_steps", "night_activity_enabled",
            "night_start_minute", "night_end_minute", "night_bathroom_location",
            "night_bathroom_visit_threshold", "night_common_location",
            "night_common_visit_threshold", "night_visit_merge_seconds",
            "post_door_inactivity_enabled", "post_door_inactivity_seconds"})) return false;
    std::int64_t start = 0, finish = 0, grace = 0;
    if (!json_boolean(morning, "enabled", home.morning.enabled, true) ||
        !json_integer(morning, "start_minute", start, 0, 1439, true) ||
        !json_integer(morning, "end_minute", finish, 0, 1439, true) ||
        !json_integer(morning, "grace_minutes", grace, 0, 1440, true)) return false;
    if (home.morning.enabled && finish <= start) return false;
    home.morning.start_at = start * 60;
    home.morning.end_at = finish * 60;
    home.morning.grace_end_at = home.morning.end_at + grace * 60;
    auto& activity = home.activity_rules;
    if (!parse_activity_rules(rules, home.morning.enabled,
            static_cast<std::uint16_t>(start), static_cast<std::uint16_t>(finish), activity))
        return false;
    return true;
}

bool decode_applied_ack(const std::string& json, const std::string& home_id,
                        std::uint32_t version) {
    const char* parse_end = nullptr;
    auto* root = cJSON_ParseWithLengthOpts(json.c_str(), json.size(), &parse_end, 0);
    if (root == nullptr) return false;
    struct JsonCleanup { cJSON* value; ~JsonCleanup() { cJSON_Delete(value); } } cleanup{root};
    const auto* end = parse_end;
    const auto* limit = json.c_str() + json.size();
    while (end != nullptr && end < limit && (*end == ' ' || *end == '\r' ||
            *end == '\n' || *end == '\t')) ++end;
    std::string returned_home, state;
    std::int64_t desired = 0, applied = 0;
    return end == limit && json_ascii(root, "home_id", returned_home, 128, true) &&
        returned_home == home_id &&
        json_integer(root, "desired_version", desired, 1,
                     std::numeric_limits<std::uint32_t>::max(), true) &&
        json_integer(root, "applied_version", applied, 1,
                     std::numeric_limits<std::uint32_t>::max(), true) &&
        json_ascii(root, "desired_status", state, 16, true) && state == "APPLIED" &&
        desired == version && applied == version;
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

    // Use the console selected by this explicit TEST_ONLY image. UART0 is the
    // identified CH343 control path on the GS-117 fixture; USB Serial/JTAG
    // remains the default for boards that expose the native USB interface.
#if CONFIG_ESP_CONSOLE_UART_NUM == 0
    if (!uart_is_driver_installed(UART_NUM_0)) {
        const auto installed = uart_driver_install(UART_NUM_0, 4096, 0, 0, nullptr, 0);
        if (installed != ESP_OK && installed != ESP_ERR_INVALID_STATE)
            return installed;
    }
    if (!uart_is_driver_installed(UART_NUM_0)) return ESP_ERR_INVALID_STATE;
#else
    // The normal product console starts with the simple VFS, which does not
    // install the interrupt-driven transport used by read_exact(). Reuse the
    // existing GS-68 diagnostic's driver/VFS setup for this TEST_ONLY profile.
    if (!usb_serial_jtag_is_driver_installed()) {
        usb_serial_jtag_driver_config_t driver_config{};
        driver_config.tx_buffer_size = 256;
        driver_config.rx_buffer_size = kGs40TestOnlyConfigRxBufferBytes;
        const auto installed = usb_serial_jtag_driver_install(&driver_config);
        if (installed != ESP_OK) return installed;
    }
    usb_serial_jtag_vfs_set_rx_line_endings(ESP_LINE_ENDINGS_LF);
    usb_serial_jtag_vfs_use_driver();
    if (std::setvbuf(stdin, nullptr, _IONBF, 0) != 0) return ESP_FAIL;
    ESP_LOGI("gs40_test_config",
        "GS40T/1 RX transport=usb_serial_jtag driver=%d connected=%d buffer=%u",
        usb_serial_jtag_is_driver_installed(), usb_serial_jtag_is_connected(),
        static_cast<unsigned>(kGs40TestOnlyConfigRxBufferBytes));
#endif
    std::printf("GS40T/1 CHALLENGE nonce=%s public_key=%s max_envelope=%u\n",
        hex(challenge.data(), challenge.size()).c_str(),
        hex(target_public.data(), target_public.size()).c_str(),
        static_cast<unsigned>(Gs40TestOnlyEnvelopeSession::kMaximumEnvelopeBytes));
    std::fflush(stdout);

    const auto deadline = static_cast<std::uint64_t>(esp_timer_get_time()) + 60000000ULL;
    std::array<std::uint8_t, 4> length_bytes{};
    std::size_t received_bytes = 0;
    if (!read_exact(length_bytes.data(), length_bytes.size(), deadline,
                    &received_bytes)) {
#if CONFIG_ESP_CONSOLE_UART_NUM == 0
        ESP_LOGW("gs40_test_config",
            "GS40T/1 RX status=timeout stage=length bytes=%u",
            static_cast<unsigned>(received_bytes));
#else
        ESP_LOGW("gs40_test_config",
            "GS40T/1 RX status=timeout stage=length bytes=%u driver=%d connected=%d buffer=%u",
            static_cast<unsigned>(received_bytes),
            usb_serial_jtag_is_driver_installed(), usb_serial_jtag_is_connected(),
            static_cast<unsigned>(kGs40TestOnlyConfigRxBufferBytes));
#endif
        return ESP_ERR_TIMEOUT;
    }
    const auto length = (static_cast<std::uint32_t>(length_bytes[0]) << 24) |
        (static_cast<std::uint32_t>(length_bytes[1]) << 16) |
        (static_cast<std::uint32_t>(length_bytes[2]) << 8) | length_bytes[3];
    if (length < 517 || length > Gs40TestOnlyEnvelopeSession::kMaximumEnvelopeBytes) {
        ESP_LOGW("gs40_test_config", "GS40T/1 RX status=invalid stage=length");
        return ESP_ERR_INVALID_SIZE;
    }
    std::vector<std::uint8_t> envelope(length);
    if (!read_exact(envelope.data(), envelope.size(), deadline,
                    &received_bytes)) {
        ESP_LOGW("gs40_test_config",
            "GS40T/1 RX status=timeout stage=envelope received=%u expected=%u",
            static_cast<unsigned>(received_bytes), static_cast<unsigned>(length));
        return ESP_ERR_TIMEOUT;
    }
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
    (void)floor_store;
    return gs40_test_only_refresh_time(config, time_provider);
}

esp_err_t gs40_test_only_refresh_time(
    const Gs40TestOnlyRuntimeConfig& config,
    AuthenticatedHubTimeProvider& time_provider) {
    if (!config.valid_material_shape()) return ESP_ERR_INVALID_STATE;
    auto* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    esp_netif_ip_info_t ip{};
    wifi_ap_record_t ap{};
    if (netif == nullptr || esp_wifi_sta_get_ap_info(&ap) != ESP_OK ||
        esp_netif_get_ip_info(netif, &ip) != ESP_OK || ip.ip.addr == 0) {
        // Driver retains only RAM configuration. Retry is paced by the existing
        // 15-second refresh task; it never reloads a stale envelope or writes NVS.
        (void)esp_wifi_connect();
        return ESP_ERR_INVALID_STATE;
    }
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
            if (!gs40_test_only_wifi_channel_supported(ap.primary))
                return ESP_ERR_INVALID_STATE;
            auto* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
            esp_netif_ip_info_t ip{};
            if (netif != nullptr && esp_netif_get_ip_info(netif, &ip) == ESP_OK &&
                ip.ip.addr != 0) return ESP_OK;
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
    return ESP_ERR_TIMEOUT;
}

bool gs40_test_only_apply_activity_home(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& current_authority, HubRuntime& runtime) {
    if (!config.valid_activity_rules_shape() ||
        current_authority.home_id != config.activity_home_id ||
        current_authority.hub_device_id.empty() ||
        current_authority.ownership_epoch == 0) return false;
    // The authenticated fixture HomeConfig is applied in one reducer
    // checkpoint. The test-only timezone helper validates the signed zone and
    // computes minutes without mutating process-global TZ state.
    return runtime.configure_home_activity(config.activity_rules, config.home_mode,
                                           current_authority);
}

Gs40TestOnlyConfigSyncResult gs40_test_only_fetch_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& current_authority,
    gs::hub::BackendHttpChannel& channel,
    Gs40TestOnlyHouseholdPolicy& policy) {
    if (config.activity_home_id.empty() ||
        config.activity_home_id != current_authority.home_id ||
        current_authority.hub_device_id != config.permanent_hub_id ||
        current_authority.ownership_epoch == 0) {
        return Gs40TestOnlyConfigSyncResult::Rejected;
    }
    const auto path = "/v1/homes/" + current_authority.home_id + "/config/desired";
    const auto response = channel.get(path);
    if (!response.server_authenticated || !response.message_complete)
        return Gs40TestOnlyConfigSyncResult::Unavailable;
    if (response.status >= 500) return Gs40TestOnlyConfigSyncResult::Unavailable;
    if (response.status != 200) return Gs40TestOnlyConfigSyncResult::Rejected;

    std::uint32_t version = 0;
    HomeConfig desired;
    if (!parse_desired_config(response.body, current_authority.home_id, version, desired))
        return Gs40TestOnlyConfigSyncResult::Rejected;
    if (version == 0) return Gs40TestOnlyConfigSyncResult::NoDesired;
    std::uint16_t timezone_probe = 0;
    if (!gs40_test_only_local_minute_from_utc(desired.timezone, 1, timezone_probe))
        return Gs40TestOnlyConfigSyncResult::Rejected;

    ConfigService validator;
    const auto validation = validator.apply(desired);
    if (!validation.applied) return Gs40TestOnlyConfigSyncResult::Rejected;
    policy.home = std::move(desired);
    policy.authority = current_authority;
    return Gs40TestOnlyConfigSyncResult::PolicyReady;
}

bool gs40_test_only_apply_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const Gs40TestOnlyHouseholdPolicy& policy,
    HubRuntime& runtime) {
    const auto& desired = policy.home;
    const auto& current_authority = policy.authority;
    if (desired.version == 0 || config.activity_home_id.empty() ||
        config.activity_home_id != current_authority.home_id ||
        current_authority.hub_device_id != config.permanent_hub_id ||
        current_authority.ownership_epoch == 0) return false;
    std::uint16_t timezone_probe = 0;
    if (!gs40_test_only_local_minute_from_utc(desired.timezone, 1, timezone_probe))
        return false;
    ConfigService validator;
    if (!validator.apply(desired).applied) return false;
    const auto applied_version = runtime.applied_home_configuration_version();
    if (desired.version < applied_version) return false;
    if (desired.version == applied_version) {
        if (!runtime.home_activity_configuration_matches(
                desired.activity_rules, desired.mode, current_authority,
                desired.version, desired.timezone))
            return false;
    } else if (!runtime.configure_home_activity(
                   desired.activity_rules, desired.mode, current_authority,
                   desired.version, desired.timezone)) {
        return false;
    }
    // The runtime checkpoint above is the commit point. The server is told
    // by a separate network task only after the whole snapshot is durable.
    return true;
}

bool gs40_test_only_ack_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& authority,
    std::uint32_t version,
    gs::hub::BackendHttpChannel& channel) {
    if (version == 0 || authority.home_id != config.activity_home_id ||
        authority.hub_device_id != config.permanent_hub_id || authority.ownership_epoch == 0)
        return false;
    const auto ack_path = "/v1/homes/" + authority.home_id + "/config/applied";
    const auto acknowledgement = channel.post(
        ack_path, "{\"version\":" + std::to_string(version) + "}");
    if (!acknowledgement.server_authenticated || !acknowledgement.message_complete ||
        acknowledgement.status != 200 ||
        !decode_applied_ack(acknowledgement.body, authority.home_id, version)) return false;
    return true;
}

Gs40TestOnlyConfigSyncResult gs40_test_only_sync_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& current_authority,
    HubRuntime& runtime,
    gs::hub::BackendHttpChannel& channel) {
    Gs40TestOnlyHouseholdPolicy policy;
    const auto fetched = gs40_test_only_fetch_household_config(
        config, current_authority, channel, policy);
    if (fetched != Gs40TestOnlyConfigSyncResult::PolicyReady) return fetched;
    if (!gs40_test_only_apply_household_config(config, policy, runtime))
        return Gs40TestOnlyConfigSyncResult::Rejected;
    if (!gs40_test_only_ack_household_config(
            config, current_authority, policy.home.version, channel))
        return Gs40TestOnlyConfigSyncResult::AppliedAckPending;
    return Gs40TestOnlyConfigSyncResult::Applied;
}

bool gs40_test_only_local_minute(const Gs40TestOnlyRuntimeConfig& config,
        EpochSeconds trusted_utc, std::uint16_t& local_minute) {
    return config.valid_activity_rules_shape() &&
        gs40_test_only_local_minute_from_utc(config.household_timezone,
                                             trusted_utc, local_minute);
}

bool gs40_test_only_local_minute(const Gs40TestOnlyRuntimeConfig& config,
        const HubRuntime& runtime, EpochSeconds trusted_utc,
        std::uint16_t& local_minute) {
    const auto& applied_timezone = runtime.applied_home_timezone();
    if (!applied_timezone.empty())
        return gs40_test_only_local_minute_from_utc(
            applied_timezone, trusted_utc, local_minute);
    return gs40_test_only_local_minute(config, trusted_utc, local_minute);
}

}  // namespace gs::hub::target
