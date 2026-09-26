#include "power/power.hpp"
#include "gs/logging.hpp"

#include <algorithm>
#include <array>
#include <cmath>

namespace gs::node {

void PowerPolicy::observe_authenticated_contact() {
    unacknowledged_ = 0;
}

void PowerPolicy::observe_unacknowledged_attempt() {
    if (unacknowledged_ < 3) ++unacknowledged_;
}

PowerDecision PowerPolicy::evaluate(const PowerObservation& input) {
    PowerDecision result;
    result.inhibitors = PowerInhibitNone;
    if (input.now_ms < 0) result.inhibitors |= PowerInhibitUnknown;
    if (!input.authenticated) result.inhibitors |= PowerInhibitAuthentication;
    if (input.maintenance) result.inhibitors |= PowerInhibitMaintenance;
    if (!input.persistence_clean) result.inhibitors |= PowerInhibitPersistence;
    if (input.radio_in_flight) result.inhibitors |= PowerInhibitRadio;
    if (input.ack_wait) result.inhibitors |= PowerInhibitAck;
    if (input.due_work) result.inhibitors |= PowerInhibitDueWork;
    if (!input.sensor_ready || !input.sensor_safe)
        result.inhibitors |= PowerInhibitSensor;
    if (!input.wake_proven) result.inhibitors |= PowerInhibitWakeUnproven;
    if (input.next_retry_ms >= 0) result.next_deadline_ms = input.next_retry_ms;
    if (input.next_health_ms >= 0 &&
        (result.next_deadline_ms < 0 || input.next_health_ms < result.next_deadline_ms))
        result.next_deadline_ms = input.next_health_ms;
    if (result.next_deadline_ms < 0) result.inhibitors |= PowerInhibitUnknown;
    if (result.next_deadline_ms >= 0 && input.now_ms >= result.next_deadline_ms)
        result.inhibitors |= PowerInhibitDueWork;

    if (!input.authenticated) state_ = PowerRuntimeState::BootAuth;
    else if (input.maintenance) state_ = PowerRuntimeState::Maintenance;
    else if (unacknowledged_ >= 3 && input.pending_work)
        state_ = PowerRuntimeState::Outage;
    else if (input.qualified_motion) state_ = PowerRuntimeState::ActivityEpisode;
    else state_ = PowerRuntimeState::ReadyIdle;
    result.state = state_;
    result.outage_retry_profile = state_ == PowerRuntimeState::Outage;
    result.future_sleep_eligible = result.inhibitors == PowerInhibitNone;
    return result;
}

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

std::uint8_t PowerPolicy::estimate_percent(std::uint16_t millivolts, bool calibrated) const {
    if (!calibrated || millivolts == 0) return 0;
    constexpr std::array<std::pair<std::uint16_t, std::uint8_t>, 9> curve{{
        {3300, 0}, {3500, 5}, {3600, 12}, {3700, 25}, {3800, 45},
        {3900, 65}, {4000, 80}, {4100, 92}, {4200, 100}
    }};
    if (millivolts <= curve.front().first) return curve.front().second;
    if (millivolts >= curve.back().first) return curve.back().second;
    for (std::size_t i = 1; i < curve.size(); ++i) {
        if (millivolts <= curve[i].first) {
            const auto lo = curve[i - 1];
            const auto hi = curve[i];
            const double fraction = static_cast<double>(millivolts - lo.first) /
                                    static_cast<double>(hi.first - lo.first);
            const double pct = static_cast<double>(lo.second) + fraction * static_cast<double>(hi.second - lo.second);
            return static_cast<std::uint8_t>(std::clamp(std::lround(pct), 0L, 100L));
        }
    }
    return 0;
}

double PowerPolicy::modeled_consumption_mah(const EnergyCounters& c, const PowerCalibration& p) const {
    const auto integrate = [](std::uint64_t ms, double ma) {
        return static_cast<double>(ms) * ma / 3600000.0;
    };
    return integrate(c.deep_sleep_ms, p.sleep_current_ma) +
           integrate(c.awake_ms, p.awake_base_current_ma) +
           integrate(c.sensor_active_ms, p.sensor_extra_current_ma) +
           integrate(c.radio_tx_ms, p.radio_tx_extra_current_ma) +
           integrate(c.radio_rx_ms, p.radio_rx_extra_current_ma);
}

EnergyEstimate PowerPolicy::estimate_runtime(const EnergyCounters& c,
                                             const PowerCalibration& p,
                                             std::uint16_t millivolts,
                                             bool calibrated) const {
    EnergyEstimate out;
    if (!calibrated || p.usable_capacity_mah <= 0.0 || p.reserve_percent < 0.0 || p.reserve_percent >= 50.0 ||
        p.sleep_current_ma < 0.0 || p.awake_base_current_ma < 0.0 || p.sensor_extra_current_ma < 0.0 ||
        p.radio_tx_extra_current_ma < 0.0 || p.radio_rx_extra_current_ma < 0.0) {
        return out;
    }
    const std::uint64_t elapsed_ms = c.deep_sleep_ms + c.awake_ms;
    if (elapsed_ms < 3600000ULL) return out;
    out.percent = estimate_percent(millivolts, calibrated);
    out.modeled_consumed_mah = modeled_consumption_mah(c, p);
    if (out.modeled_consumed_mah <= 0.0) return out;
    out.average_daily_mah = out.modeled_consumed_mah * 86400000.0 / static_cast<double>(elapsed_ms);
    const double usable_percent = std::max(0.0, static_cast<double>(out.percent) - p.reserve_percent);
    out.remaining_mah = p.usable_capacity_mah * usable_percent / 100.0;
    if (out.average_daily_mah <= 0.001 || out.remaining_mah <= 0.0) return out;
    out.estimated_days = out.remaining_mah / out.average_daily_mah;
    out.valid = std::isfinite(out.estimated_days) && out.estimated_days > 0.0;
    return out;
}

}  // namespace gs::node
