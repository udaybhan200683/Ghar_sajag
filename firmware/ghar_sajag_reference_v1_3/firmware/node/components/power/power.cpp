#include "power/power.hpp"
#include "gs/logging.hpp"

namespace gs::node {

BatteryReading PowerPolicy::classify(std::uint16_t millivolts, bool calibrated) const {
    GS_TRACE(gs::log::Category::Node, "N03", "classify.enter", "-");
    BatteryReading reading{millivolts, BatteryBand::Unknown, calibrated};
    if (!calibrated || millivolts == 0) return reading;
    if (millivolts <= 3300) reading.band = BatteryBand::Critical;
    else if (millivolts <= 3550) reading.band = BatteryBand::Low;
    else reading.band = BatteryBand::Normal;
    return reading;
}

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
