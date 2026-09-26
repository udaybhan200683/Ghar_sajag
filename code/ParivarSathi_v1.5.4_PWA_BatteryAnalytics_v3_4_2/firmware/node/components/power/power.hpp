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
    // Owner-local diagnostics. These are not yet added to the wire schema.
    std::uint64_t sensing_loops{0};
    std::uint64_t qualified_pir{0};
    std::uint64_t application_tx_attempts{0};
    std::uint64_t mac_send_attempts{0};
    std::uint64_t authenticated_rejoins{0};
    std::uint64_t recovery_nvs_commits{0};
    std::uint64_t unexpected_resets{0};
    std::uint32_t queue_high_water{0};
    void record_sensing_loop(std::uint64_t active_ms, bool qualified) {
        ++sensing_loops;
        sensor_active_ms += active_ms;
        if (qualified) ++qualified_pir;
    }
    void record_mac_attempt(bool application, bool accepted) {
        ++mac_send_attempts;
        if (application) ++application_tx_attempts;
        if (accepted) ++radio_tx_packets;
    }
    void record_recovery_commit() { ++recovery_nvs_commits; }
    void observe_pending(std::uint32_t pending) {
        if (pending > queue_high_water) queue_high_water = pending;
    }
};

enum class PowerRuntimeState : std::uint8_t {
    BootAuth, ReadyIdle, ActivityEpisode, Outage, Maintenance
};

enum PowerInhibitor : std::uint32_t {
    PowerInhibitNone = 0,
    PowerInhibitAuthentication = 1U << 0,
    PowerInhibitMaintenance = 1U << 1,
    PowerInhibitPersistence = 1U << 2,
    PowerInhibitRadio = 1U << 3,
    PowerInhibitAck = 1U << 4,
    PowerInhibitDueWork = 1U << 5,
    PowerInhibitSensor = 1U << 6,
    PowerInhibitWakeUnproven = 1U << 7,
    PowerInhibitUnknown = 1U << 8
};

// One snapshot per Node owner iteration. Other tasks/callbacks must report
// through the existing queues/atomics; they never mutate PowerPolicy.
struct PowerObservation {
    Milliseconds now_ms{-1};
    Milliseconds next_retry_ms{-1};
    Milliseconds next_health_ms{-1};
    bool authenticated{false};
    bool sensor_ready{false};
    bool sensor_safe{false};
    bool wake_proven{false};
    bool persistence_clean{false};
    bool maintenance{false};
    bool radio_in_flight{false};
    bool ack_wait{false};
    bool due_work{false};
    bool pending_work{false};
    bool qualified_motion{false};
};

struct PowerDecision {
    PowerRuntimeState state{PowerRuntimeState::BootAuth};
    Milliseconds next_deadline_ms{-1};
    std::uint32_t inhibitors{PowerInhibitUnknown};
    bool future_sleep_eligible{false};
    bool outage_retry_profile{false};
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
    // Mutating methods are called only by the existing Node owner task.
    void observe_authenticated_contact();
    void observe_unacknowledged_attempt();
    PowerDecision evaluate(const PowerObservation& observation);
    PowerRuntimeState state() const { return state_; }
    std::uint8_t consecutive_unacknowledged() const { return unacknowledged_; }
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
private:
    PowerRuntimeState state_{PowerRuntimeState::BootAuth};
    std::uint8_t unacknowledged_{0};
};

}  // namespace gs::node
