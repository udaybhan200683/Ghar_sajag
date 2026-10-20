#include "firmware/hub/target/esp32s3/esp_idf_wifi_setup_scanner.hpp"

#include "esp_wifi.h"

#include <algorithm>
#include <memory>
#include <new>

namespace gs::hub::target {
namespace {
connectivity::WifiScanSecurity security(wifi_auth_mode_t mode) {
    switch (mode) {
    case WIFI_AUTH_OPEN: return connectivity::WifiScanSecurity::Open;
    case WIFI_AUTH_WEP: return connectivity::WifiScanSecurity::Wep;
    case WIFI_AUTH_WPA2_PSK:
    case WIFI_AUTH_WPA_WPA2_PSK:
        return connectivity::WifiScanSecurity::Wpa2;
    case WIFI_AUTH_WPA3_PSK:
    case WIFI_AUTH_WPA2_WPA3_PSK:
        return connectivity::WifiScanSecurity::Wpa3;
    default: return connectivity::WifiScanSecurity::Unknown;
    }
}
}  // namespace

bool EspIdfWifiSetupScanner::scan(connectivity::WifiScanEntry* output,
                                  std::size_t capacity, std::size_t& count) {
    count = 0;
    if (output == nullptr || capacity == 0 ||
        capacity > connectivity::WifiOnboarding::kMaxScanEntries) return false;
    wifi_scan_config_t config{};
    config.scan_type = WIFI_SCAN_TYPE_ACTIVE;
    config.scan_time.active.max = 120;
    config.coex_background_scan = true;
    // IN-V1 permits only 2.4 GHz channels 1–13. Bit zero bypasses the 5 GHz
    // band in ESP-IDF 6.0.3's scan bitmap representation.
    config.channel_bitmap.ghz_2_channels = 0x3ffe;
    config.channel_bitmap.ghz_5_channels = 1;
    if (esp_wifi_scan_start(&config, true) != ESP_OK) return false;
    auto records = std::unique_ptr<wifi_ap_record_t[]>(new (std::nothrow)
        wifi_ap_record_t[capacity]{});
    if (!records) {
        (void)esp_wifi_clear_ap_list();
        return false;
    }
    auto record_count = static_cast<std::uint16_t>(capacity);
    if (esp_wifi_scan_get_ap_records(&record_count, records.get()) != ESP_OK)
        return false;
    for (std::size_t i = 0; i < record_count; ++i) {
        auto& entry = output[count];
        const auto& record = records[i];
        const auto end = std::find(record.ssid, record.ssid + sizeof(record.ssid), 0);
        const auto length = static_cast<std::size_t>(end - record.ssid);
        if (length == 0 || length > entry.ssid.size()) continue;
        entry.ssid_size = static_cast<std::uint8_t>(length);
        std::copy(record.ssid, record.ssid + length, entry.ssid.begin());
        entry.channel = record.primary;
        entry.security = security(record.authmode);
        ++count;
    }
    return true;
}

}  // namespace gs::hub::target
