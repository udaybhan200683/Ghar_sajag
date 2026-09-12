// Ghar Sajag / Parivar Sathi node power policy and energy estimator.
// Runtime prediction is model-based: board currents must be calibrated from bench measurements.
#pragma once

#include "gs/domain.hpp"

#include <cstdint>
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

// Cumulative counters emitted by node firmware.  deep_sleep_ms + awake_ms is
// elapsed device time; sensor/radio counters are subsets of awake time.
struct EnergyCounters {
    std::uint64_t deep_sleep_ms{0};
    std::uint64_t awake_ms{0};
    std::uint64_t sensor_active_ms{0};
    std::uint64_t radio_tx_ms{0};
    std::uint64_t radio_rx_ms{0};
    std::uint64_t radio_tx_packets{0};
    std::uint64_t radio_retries{0};
    std::uint64_t wake_count{0};
    std::uint64_t heartbeat_count{0};
    std::uint64_t boot_count{0};
    std::uint64_t brownout_count{0};
};

// Device/hardware calibration.  Values come from measured hardware profiles,
// not family routine settings and not assumptions hidden inside the estimator.
struct PowerCalibration {
    double usable_capacity_mah{0.0};
    double reserve_percent{5.0};
    double sleep_current_ma{0.0};
    double awake_base_current_ma{0.0};
    double sensor_extra_current_ma{0.0};
    double radio_tx_extra_current_ma{0.0};
    double radio_rx_extra_current_ma{0.0};
};

struct EnergyEstimate {
    double modeled_consumed_mah{0.0};
    double average_daily_mah{0.0};
    double remaining_mah{0.0};
    double estimated_days{0.0};
    std::uint8_t percent{0};
    bool valid{false};
};

class PowerPolicy {
public:
    BatteryReading classify(std::uint16_t millivolts, bool calibrated) const;
    SleepPlan plan(const NodeConfig& config, bool retry_pending, BatteryBand band) const;

    // Conservative piecewise approximation for a 1S Li-ion cell.  Product
    // calibration may replace the curve after real-board characterization.
    std::uint8_t estimate_percent(std::uint16_t millivolts, bool calibrated) const;

    // Integrate calibrated current against cumulative state/activity time.
    double modeled_consumption_mah(const EnergyCounters& counters, const PowerCalibration& calibration) const;

    // Combine voltage-derived state of charge with calibrated usage rate.  The
    // result is invalid when telemetry/calibration is insufficient.
    EnergyEstimate estimate_runtime(const EnergyCounters& counters,
                                    const PowerCalibration& calibration,
                                    std::uint16_t millivolts,
                                    bool calibrated) const;
};

}  // namespace gs::node
