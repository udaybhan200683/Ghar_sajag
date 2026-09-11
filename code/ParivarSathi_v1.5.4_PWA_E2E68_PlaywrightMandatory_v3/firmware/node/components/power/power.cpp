// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module N03 Node power
// @requirements E01, NFR-05
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Battery classification is a policy applied to a calibrated reading, not a fuel gauge. A 3.7 V cell label
// is nominal voltage, not a regulated MCU supply. Sleep planning must be reconciled with the heartbeat
// lease and the actual board current; a sleep duration is not a battery-life promise.

#include "power/power.hpp"
#include "gs/logging.hpp"

namespace gs::node {

// @requirements E01, NFR-05
// Keep an uncalibrated battery reading UNKNOWN instead of inventing a percentage.
BatteryReading PowerPolicy::classify(std::uint16_t millivolts, bool calibrated) const {
    GS_TRACE(gs::log::Category::Node, "N03", "classify.enter", "-");
    BatteryReading reading{millivolts, BatteryBand::Unknown, calibrated};
    if (!calibrated || millivolts == 0) return reading;
    if (millivolts <= 3300) reading.band = BatteryBand::Critical;
    else if (millivolts <= 3550) reading.band = BatteryBand::Low;
    else reading.band = BatteryBand::Normal;
    return reading;
}

// @requirements E01, NFR-05
// Select the next wake plan from pending work and voltage policy; hardware current is measured
// separately.
SleepPlan PowerPolicy::plan(const NodeConfig& config, bool retry_pending, BatteryBand band) const {
    GS_TRACE(gs::log::Category::Node, "N03", "plan.enter", "-");
    SleepPlan result;
    result.wake_after_ms = static_cast<Milliseconds>(config.heartbeat_seconds) * 1000;
    if (retry_pending) result.wake_after_ms = 10000;
    if (band == BatteryBand::Critical) result.wake_after_ms = 300000;
    result.wake_on_pir = config.pir_enabled;
    result.wake_on_reed = config.reed_enabled;
    return result;
}

}  // namespace gs::node
