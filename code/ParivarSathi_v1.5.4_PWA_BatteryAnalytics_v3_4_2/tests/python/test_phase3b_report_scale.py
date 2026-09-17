"""Phase 3B report scalability and exact-semantics regressions."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from ghar_sajag.model import CloudEvent  # noqa: E402
from tools.sim.local_lab import HOME, OWNER, Lab  # noqa: E402


class ReportScaleTest(unittest.TestCase):
    def setUp(self):
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.at = int(datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp())
        self.events = self.lab.service.store.events

    def add_event(self, event_id, kind, occurred_at, location="room1", *, payload=None, is_test=False):
        event = CloudEvent(
            HOME, event_id, kind, location, occurred_at, occurred_at, occurred_at,
            is_test=is_test, payload=payload or {},
        )
        self.events[(HOME, event_id)] = event

    def seed_report_semantics(self):
        queries = self.lab.service.queries
        month_start, _ = queries._report_window(self.at, "MONTH", ZoneInfo("Asia/Kolkata"))
        today_start, today_end = queries._report_window(self.at, "TODAY", ZoneInfo("Asia/Kolkata"))
        self.add_event("month-call", "CALL_FAMILY", month_start + 60)
        self.add_event("week-morning", "MORNING_ROUTINE_COMPLETED", today_start - 2 * 86400)
        self.add_event("today-motion-night", "MOTION", today_start + 30 * 60, "room1")
        self.add_event("today-motion-day", "MOTION", today_start + 12 * 3600, "bedroom")
        self.add_event("today-motion-no-room", "MOTION", today_start + 12 * 3600 + 1, "")
        self.add_event("today-door", "DOOR_OPEN", today_start + 13 * 3600, "entry", payload={"unexpected": True})
        self.add_event("today-coverage", "COVERAGE_CHANGED", today_start + 14 * 3600, "hub", payload={"reason": "coverage_lost"})
        self.add_event("today-coverage-ignored", "COVERAGE_CHANGED", today_start + 15 * 3600, "hub", payload={"reason": "heartbeat"})
        self.add_event("today-maintenance", "BATTERY_RUNTIME_RECALCULATION", today_start + 16 * 3600)
        self.add_event("today-test", "OK_PRESSED", today_start + 17 * 3600, is_test=True)
        self.add_event("today-end-exclusive", "OK_PRESSED", today_end)

    def test_sql_projection_matches_reference_history_projection_exactly(self):
        self.seed_report_semantics()
        queries = self.lab.service.queries
        optimized = {
            period: queries.report(HOME, OWNER, self.at, period)
            for period in ("TODAY", "WEEK", "MONTH")
        }

        durable_events = self.lab.service.store.events
        reference_events = dict(durable_events.items())
        self.lab.service.store.events = reference_events
        try:
            reference = {
                period: queries.report(HOME, OWNER, self.at, period)
                for period in ("TODAY", "WEEK", "MONTH")
            }
        finally:
            self.lab.service.store.events = durable_events

        self.assertEqual(optimized, reference)
        self.assertEqual(optimized["TODAY"]["summary"]["night_activity"], 1)
        self.assertEqual(optimized["TODAY"]["summary"]["care_concerns"], 2)
        self.assertEqual(optimized["TODAY"]["room_activity"][0], {"location": "Bedroom", "count": 2})
        self.assertNotIn("", {item["location"] for item in optimized["TODAY"]["room_activity"]})

    def test_large_report_path_materializes_only_bounded_highlights(self):
        today_start, _ = self.lab.service.queries._report_window(
            self.at, "TODAY", ZoneInfo("Asia/Kolkata")
        )
        for index in range(500):
            self.add_event(
                f"scale-{index:04d}",
                ("MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY")[index % 5],
                today_start + index,
                "room1" if index % 2 else "entry",
            )

        with patch.object(self.events, "_row_to_event", wraps=self.events._row_to_event) as materialize:
            report = self.lab.service.queries.report(HOME, OWNER, self.at, "TODAY")

        self.assertEqual(report["summary"]["event_count"], 500)
        self.assertEqual(len(report["highlights"]), 6)
        self.assertEqual(materialize.call_count, 6)

    def test_sql_projection_preserves_dst_calendar_and_night_semantics(self):
        timezone = ZoneInfo("America/New_York")
        self.lab.service.store.homes[HOME].timezone = "America/New_York"
        at = int(datetime(2026, 3, 8, 12, 0, tzinfo=timezone).timestamp())
        start, end = self.lab.service.queries._report_window(at, "TODAY", timezone)
        self.assertEqual(end - start, 23 * 3600)
        self.add_event("dst-night", "MOTION", start + 3600, "room1")
        self.add_event("dst-day", "MOTION", start + 8 * 3600, "common")

        optimized = self.lab.service.queries.report(HOME, OWNER, at, "TODAY")
        durable_events = self.lab.service.store.events
        self.lab.service.store.events = dict(durable_events.items())
        try:
            reference = self.lab.service.queries.report(HOME, OWNER, at, "TODAY")
        finally:
            self.lab.service.store.events = durable_events

        self.assertEqual(optimized, reference)
        self.assertEqual(optimized["summary"]["night_activity"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
