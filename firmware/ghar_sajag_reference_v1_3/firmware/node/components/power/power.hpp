#pragma once

#include "gs/domain.hpp"

#include <string>

namespace gs::node {

enum class BatteryBand { Unknown, Normal, Low, Critical };

struct BatteryReading {
    std::uint16_t millivolts{0};
    BatteryBand band{BatteryBand::Unknown};
    bool calibrated{false};
};

struct SleepPlan {
    Milliseconds wake_after_ms{60000};
    bool wake_on_pir{true};
    bool wake_on_reed{true};
};

class PowerPolicy {
public:
    BatteryReading classify(std::uint16_t millivolts, bool calibrated) const;
    SleepPlan plan(const NodeConfig& config, bool retry_pending, BatteryBand band) const;
};

}  // namespace gs::node
