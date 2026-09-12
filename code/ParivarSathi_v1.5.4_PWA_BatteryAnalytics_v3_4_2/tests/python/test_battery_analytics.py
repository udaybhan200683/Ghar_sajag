from __future__ import annotations

import unittest

from ghar_sajag.battery import BatteryAnalyticsService, BatteryPowerProfile, BatterySample, EnergyCounters
from ghar_sajag.store import InMemoryStore


class BatteryAnalyticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryStore()
        self.svc = BatteryAnalyticsService(self.store)
        self.profile = BatteryPowerProfile(
            "n1", usable_capacity_mah=2700.0, reserve_percent=8.0,
            sleep_current_ma=0.2, awake_base_current_ma=18.0,
            sensor_extra_current_ma=0.8, radio_tx_extra_current_ma=70.0,
            radio_rx_extra_current_ma=45.0, high_drain_ratio=1.75,
        )
        self.svc.set_profile(self.profile)

    @staticmethod
    def add(a: EnergyCounters, b: EnergyCounters) -> EnergyCounters:
        return EnergyCounters(**{k: getattr(a, k) + getattr(b, k) for k in a.__dataclass_fields__})

    @staticmethod
    def normal_day(mult: float = 1.0) -> EnergyCounters:
        awake = int(180_000 * mult)
        return EnergyCounters(
            deep_sleep_ms=86_400_000 - awake,
            awake_ms=awake,
            sensor_active_ms=int(70_000 * mult),
            radio_tx_ms=int(8_000 * mult),
            radio_rx_ms=int(10_000 * mult),
            radio_tx_packets=int(60 * mult),
            radio_retries=int(2 * mult),
            wake_count=int(35 * mult),
            heartbeat_count=24,
        )

    def seed(self, days: int = 8, mv: int = 3950) -> None:
        counters = EnergyCounters(boot_count=1)
        for day in range(days):
            counters = self.add(counters, self.normal_day())
            self.svc.record(BatterySample("n1", day * 86_400, mv, counters))

    def test_voltage_curve_is_non_linear_and_bounded(self) -> None:
        self.assertEqual(self.svc.percent_from_mv(3300), 0)
        self.assertEqual(self.svc.percent_from_mv(3900), 65)
        self.assertEqual(self.svc.percent_from_mv(4200), 100)
        self.assertEqual(self.svc.percent_from_mv(5000), 100)

    def test_history_produces_remaining_days_and_high_confidence(self) -> None:
        self.seed()
        e = self.svc.estimate("n1")
        self.assertEqual(e.confidence, "HIGH")
        self.assertEqual(e.drain_status, "NORMAL")
        self.assertGreater(e.daily_mah or 0, 0)
        self.assertGreater(e.estimated_days or 0, 100)
        self.assertGreater(e.recent_wakeups_per_day or 0, 0)

    def test_sustained_high_activity_shortens_prediction_and_flags_drain(self) -> None:
        self.seed()
        before = self.svc.estimate("n1")
        counters = self.store.battery_samples["n1"][-1].counters
        at = self.store.battery_samples["n1"][-1].sampled_at
        for _ in range(2):
            counters = self.add(counters, self.normal_day(20.0))
            at += 86_400
            self.svc.record(BatterySample("n1", at, 3950, counters))
        after = self.svc.estimate("n1")
        self.assertEqual(after.drain_status, "HIGH")
        self.assertGreater(after.recent_daily_mah or 0, after.baseline_daily_mah or 0)
        self.assertLess(after.estimated_days or 1e9, before.estimated_days or 1e9)

    def test_counter_reset_is_tolerated_without_negative_consumption(self) -> None:
        self.seed()
        previous = self.svc.estimate("n1")
        reset = EnergyCounters(
            deep_sleep_ms=7_000_000, awake_ms=200_000, sensor_active_ms=50_000,
            radio_tx_ms=5_000, radio_rx_ms=8_000, boot_count=2,
        )
        self.svc.record(BatterySample("n1", 8 * 86_400, 3940, reset))
        e = self.svc.estimate("n1")
        self.assertGreaterEqual(e.modeled_consumed_mah, 0)
        self.assertGreaterEqual(e.percent, 0)
        self.assertIsNotNone(e.daily_mah)
        self.assertEqual(e.sample_count, 9)
        self.assertGreater(previous.estimated_days or 0, 0)

    def test_profile_capacity_changes_runtime_without_changing_usage_rate(self) -> None:
        self.seed()
        before = self.svc.estimate("n1")
        self.svc.set_profile(BatteryPowerProfile(
            "n1", usable_capacity_mah=4000.0, reserve_percent=8.0,
            sleep_current_ma=0.2, awake_base_current_ma=18.0,
            sensor_extra_current_ma=0.8, radio_tx_extra_current_ma=70.0,
            radio_rx_extra_current_ma=45.0, high_drain_ratio=1.75,
        ))
        after = self.svc.estimate("n1")
        self.assertAlmostEqual(after.daily_mah or 0, before.daily_mah or 0, places=5)
        self.assertGreater(after.estimated_days or 0, before.estimated_days or 0)

    def test_invalid_or_non_monotonic_telemetry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "sensor_time_exceeds_awake"):
            self.svc.record(BatterySample("n1", 1, 3900, EnergyCounters(awake_ms=10, sensor_active_ms=11)))
        self.svc.record(BatterySample("n1", 2, 3900, EnergyCounters(deep_sleep_ms=3_600_000, boot_count=1)))
        with self.assertRaisesRegex(ValueError, "battery_sample_not_monotonic"):
            self.svc.record(BatterySample("n1", 2, 3900, EnergyCounters(deep_sleep_ms=7_200_000, boot_count=1)))


if __name__ == "__main__":
    unittest.main()
