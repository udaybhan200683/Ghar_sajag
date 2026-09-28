// Ghar Sajag / Parivar Sathi node power policy and energy estimator.
// Runtime prediction is model-based: board currents must be calibrated from bench measurements.
#pragma once

#include "gs/domain.hpp"

#include <cstdint>
#include <limits>
#include <optional>
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

// Owner-local scheduling of the existing NodeHealth frame. Only a verified
// application ACK can defer health as authenticated Hub contact; a MAC send
// callback alone cannot. No timer, persistence or extra radio owner is added.
class NodeHealthCadence {
public:
    NodeHealthCadence(Milliseconds interval_ms, Milliseconds first_due_ms)
        : interval_ms_(interval_ms), next_due_ms_(first_due_ms) {}
    void observe_authenticated_contact(Milliseconds now_ms);
    void observe_health_attempt(Milliseconds now_ms, Milliseconds retry_interval_ms = -1);
    void schedule_now(Milliseconds now_ms) { next_due_ms_ = now_ms; }
    bool due(Milliseconds now_ms, bool application_due, bool pending_work,
             bool outage, bool maintenance) const;
    Milliseconds next_due_ms() const { return next_due_ms_; }
private:
    Milliseconds interval_ms_;
    Milliseconds next_due_ms_;
};

// Owner-local light-sleep bounds. The 30 s cap forces the existing owner to
// recheck queues and maintenance state regularly; the 500 ms margin protects
// product deadlines from sleep entry/wake overhead. The minimum window avoids
// paying the light-sleep transition cost for a negligible idle interval.
inline constexpr Milliseconds kLightSleepMaximumMs = 30000;
inline constexpr Milliseconds kLightSleepDeadlineMarginMs = 500;
inline constexpr Milliseconds kLightSleepMinimumMs = 500;

enum LightSleepInhibitor : std::uint32_t {
    LightSleepInhibitNone = 0,
    LightSleepInhibitClock = 1U << 0,
    LightSleepInhibitAuthentication = 1U << 1,
    LightSleepInhibitRejoin = 1U << 2,
    LightSleepInhibitProductNotReady = 1U << 3,
    LightSleepInhibitPendingTx = 1U << 4,
    LightSleepInhibitEventInFlight = 1U << 5,
    LightSleepInhibitAckWait = 1U << 6,
    LightSleepInhibitRetryDue = 1U << 7,
    LightSleepInhibitRecoveryWork = 1U << 8,
    LightSleepInhibitPersistence = 1U << 9,
    LightSleepInhibitFota = 1U << 10,
    LightSleepInhibitBootHealth = 1U << 11,
    LightSleepInhibitMaintenance = 1U << 12,
    LightSleepInhibitHealthDue = 1U << 13,
    LightSleepInhibitSecurityDue = 1U << 14,
    LightSleepInhibitPirHigh = 1U << 15,
    LightSleepInhibitPirUnstable = 1U << 16,
    LightSleepInhibitDebounce = 1U << 17,
    LightSleepInhibitWakeUnavailable = 1U << 18,
    LightSleepInhibitRuntimeUnknown = 1U << 19,
    LightSleepInhibitOtherOwnerWork = 1U << 20,
    LightSleepInhibitShortWindow = 1U << 21,
    LightSleepInhibitOutage = 1U << 22
};

// A snapshot built only by the existing Node owner. All times are absolute
// monotonic milliseconds; absent deadlines use -1. A missing/uncertain fact
// defaults to inhibited.
struct LightSleepObservation {
    Milliseconds now_ms{-1};
    Milliseconds next_health_ms{-1};
    Milliseconds next_retry_ms{-1};
    Milliseconds next_maintenance_ms{-1};
    Milliseconds next_security_ms{-1};
    bool authenticated{false};
    bool rejoin_active{false};
    bool rejoin_backoff{false};
    bool product_ready{false};
    bool pending_tx{false};
    bool event_in_flight{false};
    bool ack_wait{false};
    bool retry_due{false};
    bool recovery_work{false};
    bool persistence_clean{false};
    bool fota_active{false};
    bool boot_health_active{false};
    bool maintenance_active{false};
    bool health_due{false};
    bool security_due{false};
    bool pir_high{true};
    bool pir_low_stable{false};
    bool debounce_safe{false};
    bool wake_source_ready{false};
    bool runtime_state_known{false};
    bool other_owner_work{false};
    bool outage_active{false};
};

struct LightSleepDecision {
    std::uint32_t inhibitors{LightSleepInhibitRuntimeUnknown};
    Milliseconds earliest_deadline_ms{-1};
    Milliseconds requested_sleep_ms{0};
    bool eligible{false};
};

// Portable labels for the qualification log; the adapter maps ESP-IDF wake bits.
enum class LightSleepWakeKind : std::uint8_t {
    Unknown = 0,
    Timer = 1,
    Gpio = 2,
    Other = 3
};
inline LightSleepWakeKind classify_light_sleep_wake(bool gpio, bool timer) {
    if (gpio) return LightSleepWakeKind::Gpio;
    if (timer) return LightSleepWakeKind::Timer;
    return LightSleepWakeKind::Other;
}
inline const char* light_sleep_wake_name(LightSleepWakeKind kind) {
    switch (kind) {
        case LightSleepWakeKind::Gpio: return "GPIO";
        case LightSleepWakeKind::Timer: return "TIMER";
        case LightSleepWakeKind::Other: return "OTHER";
        default: return "UNKNOWN";
    }
}

// RAM-only diagnostics. record_sleep_attempt() is called only on the existing
// path immediately before esp_light_sleep_start(), after both wake sources are
// armed and all final entry checks pass. Counts saturate rather than wrapping.
struct LightSleepTelemetry {
    std::uint32_t light_sleep_entry_count{0};
    std::uint32_t timer_wake_count{0};
    std::uint32_t gpio_wake_count{0};
    std::uint32_t other_wake_count{0};
    LightSleepWakeKind last_wake_cause{LightSleepWakeKind::Unknown};
    std::uint32_t last_sleep_requested_ms{0};
    std::uint32_t last_sleep_elapsed_ms{0};

    void record_sleep_attempt(Milliseconds requested_ms) {
        increment(light_sleep_entry_count);
        last_sleep_requested_ms = bounded_ms(requested_ms);
        last_sleep_elapsed_ms = 0;
    }

    void record_sleep_return(bool entered, bool gpio_wake, bool timer_wake,
                             Milliseconds elapsed_ms) {
        last_sleep_elapsed_ms = bounded_ms(elapsed_ms);
        if (!entered) return;
        if (gpio_wake) increment(gpio_wake_count);
        if (timer_wake) increment(timer_wake_count);
        if (!gpio_wake && !timer_wake) increment(other_wake_count);
        last_wake_cause = classify_light_sleep_wake(gpio_wake, timer_wake);
    }

private:
    static void increment(std::uint32_t& counter) {
        if (counter != std::numeric_limits<std::uint32_t>::max()) ++counter;
    }

    static std::uint32_t bounded_ms(Milliseconds value) {
        if (value <= 0) return 0;
        const auto unsigned_value = static_cast<std::uint64_t>(value);
        return unsigned_value > std::numeric_limits<std::uint32_t>::max()
            ? std::numeric_limits<std::uint32_t>::max()
            : static_cast<std::uint32_t>(unsigned_value);
    }
};
inline const char* light_sleep_deadline_name(const LightSleepObservation& o,
                                             Milliseconds deadline) {
    if (deadline == o.next_health_ms) return "health";
    if (deadline == o.next_retry_ms) return "retry";
    if (deadline == o.next_maintenance_ms) return "maintenance";
    if (deadline == o.next_security_ms) return "security";
    return "none";
}

LightSleepDecision evaluate_light_sleep(const LightSleepObservation& observation);

// Owner-local PIR episode state. The first event is admitted by NodeRuntime
// before note_first() is called. Repeats remain in RAM until emitted as a
// separate, immutable MotionSummary event; no observation writes flash.
class ActivityEpisode {
public:
    static constexpr Milliseconds quiet_ms = 45000;
    static constexpr Milliseconds max_ms = 300000;
    static constexpr Milliseconds offline_idle_ms = 1800000;
    struct Summary {
        std::string room;
        DomainEvent::MotionAggregate aggregate;
    };
    bool needs_first(const std::string& room, Milliseconds now_ms, bool outage);
    void note_first(const std::string& room, Milliseconds now_ms, bool outage);
    void note_repeat(Milliseconds now_ms);
    void poll(Milliseconds now_ms, bool outage);
    const std::optional<Summary>& pending() const { return pending_; }
    Milliseconds next_deadline_ms() const;
    void summary_committed() { pending_.reset(); ++summaries_; }
    std::uint64_t coalesced() const { return coalesced_; }
    std::uint64_t omitted() const { return omitted_; }
    std::uint64_t summaries() const { return summaries_; }
private:
    void close();
    std::string room_;
    Milliseconds started_ms_{-1};
    Milliseconds first_repeat_ms_{-1};
    Milliseconds last_ms_{-1};
    std::uint32_t repeats_{0};
    bool outage_{false};
    std::optional<Summary> pending_;
    std::uint64_t coalesced_{0};
    std::uint64_t omitted_{0};
    std::uint64_t summaries_{0};
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

// Diagnostics only: noisy input never disables sensing or rejects events.
struct PirNoiseSnapshot {
    std::uint32_t raw_edges{0};
    std::uint32_t rapid_edges{0};
    std::uint32_t noisy_windows{0};
    std::uint32_t stuck_high_reports{0};
    bool stuck_high{false};
};

class PirNoiseMonitor {
public:
    // Returns true only when a new bounded fault indication is warranted.
    bool observe(bool raw_high, bool qualified, Milliseconds now_ms);
    const PirNoiseSnapshot& snapshot() const { return snapshot_; }
private:
    PirNoiseSnapshot snapshot_;
    Milliseconds last_change_ms_{-1};
    Milliseconds high_since_ms_{-1};
    Milliseconds window_start_ms_{-1};
    std::uint16_t rapid_in_window_{0};
    std::uint16_t qualified_in_window_{0};
    bool warned_this_window_{false};
    bool initialized_{false};
    bool last_level_{false};
};

enum class LedSignal : std::uint8_t { Delivery, Ready, FotaSuccess, Fault };

// A bounded pattern evaluator. The owner sets the GPIO level on each poll;
// no task, timer, sleep call, or blocking delay is added.
class NodeLedPolicy {
public:
    void trigger(LedSignal signal, Milliseconds now_ms);
    bool on(Milliseconds now_ms) const;
    bool active(Milliseconds now_ms) const;
private:
    LedSignal signal_{LedSignal::Delivery};
    Milliseconds started_ms_{-1};
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
