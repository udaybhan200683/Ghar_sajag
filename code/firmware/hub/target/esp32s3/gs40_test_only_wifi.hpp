#pragma once

namespace gs::hub::target {

// The isolated physical fixture accepts standard 2.4 GHz channels only.
// Channel 0 means unknown and channel 14/5 GHz values are rejected.
constexpr bool gs40_test_only_wifi_channel_supported(int channel) {
    return channel >= 1 && channel <= 13;
}

}  // namespace gs::hub::target
