#pragma once

#include "firmware/hub/connectivity/wifi_onboarding.hpp"

namespace gs::hub::target {

// Invoked only through WifiOnboarding after current installer authorization.
// No BLE service or commercial credential path instantiates it yet.
class EspIdfWifiSetupScanner final : public connectivity::WifiSetupScanner {
public:
    bool scan(connectivity::WifiScanEntry* output, std::size_t capacity,
              std::size_t& count) override;
};

}  // namespace gs::hub::target
