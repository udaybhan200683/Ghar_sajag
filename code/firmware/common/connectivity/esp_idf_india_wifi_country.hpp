#pragma once

#include "firmware/common/connectivity/india_wifi_profile.hpp"

#include "esp_err.h"
#include "esp_wifi.h"

namespace gs::connectivity {

class EspIdfWifiCountryApi {
public:
    static constexpr esp_err_t success = ESP_OK;

    esp_err_t set_country_code(const char* code, bool ieee80211d) {
        const auto result = esp_wifi_set_country_code(code, ieee80211d);
        if (result != ESP_OK) last_error_ = result;
        return result;
    }

    esp_err_t get_country_code(char* code) {
        const auto result = esp_wifi_get_country_code(code);
        if (result != ESP_OK) last_error_ = result;
        return result;
    }

    esp_err_t last_error() const { return last_error_; }

private:
    esp_err_t last_error_{ESP_OK};
};

inline esp_err_t configure_india_wifi_country() {
    EspIdfWifiCountryApi api;
    if (IndiaWifiProfileV1::configure_country(api)) return ESP_OK;
    return api.last_error() == ESP_OK ? ESP_ERR_INVALID_STATE : api.last_error();
}

}  // namespace gs::connectivity
