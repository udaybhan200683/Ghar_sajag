"""Battery consumption analytics and runtime prediction.

This module deliberately separates *measured/telemetry inputs* from the prediction
policy.  The estimator never pretends the ESP32 can measure its own full supply
current.  Current values are calibration inputs obtained from bench measurements;
node telemetry contributes cumulative time/activity counters and battery voltage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import statistics
from typing import Iterable

from .logging_config import traced
from .store import InMemoryStore

DAY_MS = 86_400_000


@dataclass(slots=True)
class BatteryPowerProfile:
    device_id: str
    usable_capacity_mah: float
    reserve_percent: float
    sleep_current_ma: float
    awake_base_current_ma: float
    sensor_extra_current_ma: float
    radio_tx_extra_current_ma: float
    radio_rx_extra_current_ma: float
    high_drain_ratio: float = 1.75


@dataclass(slots=True)
class EnergyCounters:
    deep_sleep_ms: int = 0
    awake_ms: int = 0
    sensor_active_ms: int = 0
    radio_tx_ms: int = 0
    radio_rx_ms: int = 0
    radio_tx_packets: int = 0
    radio_retries: int = 0
    wake_count: int = 0
    heartbeat_count: int = 0
    boot_count: int = 0
    brownout_count: int = 0

    def elapsed_ms(self) -> int:
        return self.deep_sleep_ms + self.awake_ms


@dataclass(slots=True)
class BatterySample:
    device_id: str
    sampled_at: int
    battery_mv: int
    counters: EnergyCounters
    charging: bool = False


@dataclass(slots=True)
class BatteryEstimate:
    device_id: str
    battery_mv: int
    percent: int
    remaining_mah: float
    daily_mah: float | None
    estimated_days: float | None
    confidence: str
    drain_status: str
    sample_count: int
    observation_hours: float
    modeled_consumed_mah: float
    recent_daily_mah: float | None
    baseline_daily_mah: float | None
    recent_wakeups_per_day: float | None
    recent_retries_per_day: float | None
    recent_tx_packets_per_day: float | None
    charging: bool

    def as_dict(self) -> dict:
        value = asdict(self)
        for key in ("remaining_mah", "daily_mah", "estimated_days", "observation_hours", "modeled_consumed_mah",
                    "recent_daily_mah", "baseline_daily_mah", "recent_wakeups_per_day",
                    "recent_retries_per_day", "recent_tx_packets_per_day"):
            if value[key] is not None:
                value[key] = round(value[key], 3)
        return value


class BatteryAnalyticsService:
    """Estimate remaining energy from voltage plus calibrated usage counters.

    The model uses a non-linear 1S Li-ion open-circuit-voltage approximation for
    state of charge and derives consumption rate from cumulative activity counters.
    Calibration values are per device/profile and therefore are not household
    routine constants.
    """

    # (millivolts, percent).  Profile/device calibration can replace this curve in
    # production.  It is intentionally conservative near the knee.
    SOC_CURVE: tuple[tuple[int, int], ...] = (
        (3300, 0), (3500, 5), (3600, 12), (3700, 25), (3800, 45),
        (3900, 65), (4000, 80), (4100, 92), (4200, 100),
    )

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    @staticmethod
    def _validate_profile(profile: BatteryPowerProfile) -> None:
        numeric = (
            profile.usable_capacity_mah, profile.reserve_percent, profile.sleep_current_ma,
            profile.awake_base_current_ma, profile.sensor_extra_current_ma,
            profile.radio_tx_extra_current_ma, profile.radio_rx_extra_current_ma,
            profile.high_drain_ratio,
        )
        if not all(math.isfinite(x) for x in numeric):
            raise ValueError("invalid_battery_profile")
        if profile.usable_capacity_mah <= 0 or not 0 <= profile.reserve_percent < 50:
            raise ValueError("invalid_battery_capacity")
        if min(profile.sleep_current_ma, profile.awake_base_current_ma, profile.sensor_extra_current_ma,
               profile.radio_tx_extra_current_ma, profile.radio_rx_extra_current_ma) < 0:
            raise ValueError("invalid_current_calibration")
        if profile.high_drain_ratio <= 1.0:
            raise ValueError("invalid_high_drain_ratio")

    @staticmethod
    def _validate_counters(counters: EnergyCounters) -> None:
        if any(v < 0 for v in asdict(counters).values()):
            raise ValueError("negative_energy_counter")
        if counters.sensor_active_ms > counters.awake_ms:
            raise ValueError("sensor_time_exceeds_awake")
        if counters.radio_tx_ms > counters.awake_ms or counters.radio_rx_ms > counters.awake_ms:
            raise ValueError("radio_time_exceeds_awake")

    @traced("B12")
    def set_profile(self, profile: BatteryPowerProfile) -> None:
        self._validate_profile(profile)
        self.store.battery_profiles[profile.device_id] = profile

    @traced("B12")
    def clear_device(self, device_id: str) -> None:
        self.store.battery_samples.pop(device_id, None)

    @classmethod
    def percent_from_mv(cls, battery_mv: int) -> int:
        if battery_mv <= cls.SOC_CURVE[0][0]:
            return cls.SOC_CURVE[0][1]
        if battery_mv >= cls.SOC_CURVE[-1][0]:
            return cls.SOC_CURVE[-1][1]
        for (lo_mv, lo_pct), (hi_mv, hi_pct) in zip(cls.SOC_CURVE, cls.SOC_CURVE[1:]):
            if lo_mv <= battery_mv <= hi_mv:
                fraction = (battery_mv - lo_mv) / float(hi_mv - lo_mv)
                return int(round(lo_pct + fraction * (hi_pct - lo_pct)))
        return 0

    @staticmethod
    def consumption_mah(counters: EnergyCounters, profile: BatteryPowerProfile) -> float:
        # Base awake/sleep states partition elapsed time. Sensor/radio are modeled as
        # incremental current above awake base so overlapping activity is not double
        # counted as a second full awake period.
        terms = (
            (counters.deep_sleep_ms, profile.sleep_current_ma),
            (counters.awake_ms, profile.awake_base_current_ma),
            (counters.sensor_active_ms, profile.sensor_extra_current_ma),
            (counters.radio_tx_ms, profile.radio_tx_extra_current_ma),
            (counters.radio_rx_ms, profile.radio_rx_extra_current_ma),
        )
        return sum(ms * ma / 3_600_000.0 for ms, ma in terms)

    @staticmethod
    def _counter_delta(newer: EnergyCounters, older: EnergyCounters) -> EnergyCounters | None:
        values = {}
        for key in asdict(newer):
            delta = getattr(newer, key) - getattr(older, key)
            if delta < 0:
                # Counter reset/reboot: do not manufacture a negative-energy interval.
                return None
            values[key] = delta
        return EnergyCounters(**values)

    @traced("B12")
    def record(self, sample: BatterySample) -> BatteryEstimate:
        if sample.device_id not in self.store.battery_profiles:
            raise ValueError("battery_profile_missing")
        if not 2500 <= sample.battery_mv <= 5000:
            raise ValueError("invalid_battery_mv")
        self._validate_counters(sample.counters)
        history = self.store.battery_samples.setdefault(sample.device_id, [])
        if history and sample.sampled_at <= history[-1].sampled_at:
            raise ValueError("battery_sample_not_monotonic")
        history.append(sample)
        if len(history) > 64:
            del history[:-64]
        return self.estimate(sample.device_id)

    def _interval_rates(self, samples: Iterable[BatterySample], profile: BatteryPowerProfile) -> list[tuple[int, float]]:
        seq = list(samples)
        rates: list[tuple[int, float]] = []
        for older, newer in zip(seq, seq[1:]):
            seconds = newer.sampled_at - older.sampled_at
            if seconds <= 0:
                continue
            delta = self._counter_delta(newer.counters, older.counters)
            if delta is None:
                continue
            used = self.consumption_mah(delta, profile)
            rates.append((newer.sampled_at, used * 86400.0 / seconds))
        return rates

    @traced("B12")
    def estimate(self, device_id: str) -> BatteryEstimate:
        profile = self.store.battery_profiles.get(device_id)
        history = self.store.battery_samples.get(device_id, [])
        if profile is None or not history:
            raise ValueError("battery_telemetry_missing")
        latest = history[-1]
        samples_for_voltage = history[-3:]
        smoothed_mv = int(round(statistics.median(s.battery_mv for s in samples_for_voltage)))
        percent = self.percent_from_mv(smoothed_mv)
        usable_percent = max(0.0, percent - profile.reserve_percent)
        remaining_mah = profile.usable_capacity_mah * usable_percent / 100.0

        rates = self._interval_rates(history, profile)
        elapsed_ms = latest.counters.elapsed_ms()
        modeled_total = self.consumption_mah(latest.counters, profile)
        lifetime_rate = None
        if elapsed_ms >= 3_600_000 and modeled_total > 0:
            lifetime_rate = modeled_total * DAY_MS / elapsed_ms

        # Median interval rate suppresses one-off bursts.  A sustained recent
        # increase is surfaced separately and, once classified HIGH, the prediction
        # deliberately uses the recent rate so the dashboard does not over-promise.
        interval_values = [rate for _, rate in rates if rate > 0]
        recent_daily_mah = statistics.median(interval_values[-2:]) if interval_values else lifetime_rate
        baseline_values = interval_values[:-2]
        baseline_daily_mah = statistics.median(baseline_values) if baseline_values else None

        observation_hours = elapsed_ms / 3_600_000.0
        if len(history) >= 8 and observation_hours >= 72:
            confidence = "HIGH"
        elif len(history) >= 3 and observation_hours >= 24:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        drain_status = "LEARNING"
        if len(interval_values) >= 4 and baseline_daily_mah is not None and recent_daily_mah is not None:
            drain_status = "HIGH" if baseline_daily_mah > 0.001 and recent_daily_mah >= baseline_daily_mah * profile.high_drain_ratio else "NORMAL"
        elif recent_daily_mah is not None:
            drain_status = "NORMAL" if observation_hours >= 24 else "LEARNING"

        stable_rate = statistics.median(interval_values[-7:]) if interval_values else lifetime_rate
        daily_mah = recent_daily_mah if drain_status == "HIGH" else stable_rate
        estimated_days = None
        if not latest.charging and daily_mah is not None and daily_mah > 0.001 and remaining_mah > 0:
            estimated_days = remaining_mah / daily_mah

        recent_wakeups_per_day = recent_retries_per_day = recent_tx_packets_per_day = None
        if len(history) >= 2:
            older = history[-2]
            seconds = latest.sampled_at - older.sampled_at
            delta = self._counter_delta(latest.counters, older.counters)
            if seconds > 0 and delta is not None:
                scale = 86400.0 / seconds
                recent_wakeups_per_day = delta.wake_count * scale
                recent_retries_per_day = delta.radio_retries * scale
                recent_tx_packets_per_day = delta.radio_tx_packets * scale

        return BatteryEstimate(
            device_id=device_id,
            battery_mv=smoothed_mv,
            percent=percent,
            remaining_mah=remaining_mah,
            daily_mah=daily_mah,
            estimated_days=estimated_days,
            confidence=confidence,
            drain_status=drain_status,
            sample_count=len(history),
            observation_hours=observation_hours,
            modeled_consumed_mah=modeled_total,
            recent_daily_mah=recent_daily_mah,
            baseline_daily_mah=baseline_daily_mah,
            recent_wakeups_per_day=recent_wakeups_per_day,
            recent_retries_per_day=recent_retries_per_day,
            recent_tx_packets_per_day=recent_tx_packets_per_day,
            charging=latest.charging,
        )

    def all_estimates(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for device_id in sorted(self.store.battery_profiles):
            if self.store.battery_samples.get(device_id):
                result[device_id] = self.estimate(device_id).as_dict()
        return result
