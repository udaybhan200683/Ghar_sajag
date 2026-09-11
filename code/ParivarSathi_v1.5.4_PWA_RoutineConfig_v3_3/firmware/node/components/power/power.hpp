// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N03 Node power
// @requirements E01, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Battery classification is a policy applied to a calibrated reading, not a fuel gauge. A 3.7 V cell label
// is nominal voltage, not a regulated MCU supply. Sleep planning must be reconciled with the heartbeat
// lease and the actual board current; a sleep duration is not a battery-life promise.

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
    // @requirements E01, NFR-05
    // Keep an uncalibrated battery reading UNKNOWN instead of inventing a percentage.
    BatteryReading classify(std::uint16_t millivolts, bool calibrated) const;
    // @requirements E01, NFR-05
    // Select the next wake plan from pending work and voltage policy; hardware current is measured
    // separately.
    SleepPlan plan(const NodeConfig& config, bool retry_pending, BatteryBand band) const;
};

}  // namespace gs::node
