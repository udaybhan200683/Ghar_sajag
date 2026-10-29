"""Focused Phase 3B durable-history and caregiver-projection regressions."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ghar_sajag.database import initialize_sqlite  # noqa: E402
from ghar_sajag.model import CloudEvent, Incident, IncidentState  # noqa: E402
from ghar_sajag.sqlite_events import SQLiteEventMap  # noqa: E402
from tools.sim.local_lab import HOME, OWNER, Lab  # noqa: E402


class EventQueryIndexTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        initialize_sqlite(self.db)
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("scale-home", "Scale home", "UTC", 1, 1),
        )
        self.events = SQLiteEventMap(self.db)
        kinds = ("MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY")
        for index in range(100):
            kind = kinds[index % len(kinds)]
            event = CloudEvent(
                "scale-home", f"event-{index:03d}", kind, "room1", 1000 + index // 10,
                2000 + index, 2000 + index, payload={},
            )
            self.events[(event.home_id, event.event_id)] = event

    def tearDown(self):
        self.db.close()

    def _plan(self, sql, values):
        return " | ".join(
            row[3] for row in self.db.execute("EXPLAIN QUERY PLAN " + sql, values)
        )

    def test_phase3b_indexes_remove_hot_query_temp_sorts(self):
        indexes = {
            row[0]: row[1]
            for row in self.db.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='events'"
            )
        }
        self.assertIn("occurred_at DESC, canonical_event_id DESC", indexes["idx_events_home_time"])
        self.assertIn("COALESCE(NULLIF(occurred_at, 0), received_at)",
                      indexes["idx_events_home_effective_time"])
        self.assertIn("idx_events_home_type_time", indexes)
        self.assertIn("idx_events_home_type_received", indexes)

        plans = {
            "timeline": self._plan(
                "SELECT * FROM events WHERE home_id=? AND is_test=0 "
                "ORDER BY COALESCE(NULLIF(occurred_at,0),received_at) DESC,"
                "canonical_event_id DESC LIMIT ?",
                ("scale-home", 40),
            ),
            "activity": self._plan(
                "SELECT * FROM events WHERE home_id=? AND event_type IN (?,?,?,?) "
                "ORDER BY occurred_at DESC,canonical_event_id DESC LIMIT ?",
                ("scale-home", "DOOR_CLOSED", "DOOR_OPEN", "MOTION", "OK_PRESSED", 1),
            ),
            "single_type": self._plan(
                "SELECT * FROM events WHERE home_id=? AND event_type=? "
                "ORDER BY occurred_at DESC,canonical_event_id DESC LIMIT ?",
                ("scale-home", "MOTION", 6),
            ),
            "latest_received": self._plan(
                "SELECT * FROM events WHERE home_id=? AND event_type=? "
                "ORDER BY received_at DESC,canonical_event_id DESC LIMIT 1",
                ("scale-home", "MOTION"),
            ),
            "counts": self._plan(
                "SELECT event_type,COUNT(*) FROM events WHERE home_id=? GROUP BY event_type",
                ("scale-home",),
            ),
        }
        for name, plan in plans.items():
            self.assertNotIn("TEMP B-TREE", plan, f"{name}: {plan}")
        self.assertIn("idx_events_home_type_time", plans["single_type"])
        self.assertIn("idx_events_home_type_received", plans["latest_received"])
        self.assertIn("idx_events_home_effective_time", plans["timeline"])

    def test_indexed_queries_preserve_tied_timestamp_order_and_counts(self):
        latest = self.events.home_events("scale-home", newest_first=True, limit=12)
        self.assertEqual(
            [item.event_id for item in latest],
            sorted((f"event-{index:03d}" for index in range(90, 100)), reverse=True)
            + ["event-089", "event-088"],
        )
        motion = self.events.home_events(
            "scale-home", kinds={"MOTION"}, newest_first=True, limit=3
        )
        self.assertEqual([item.event_id for item in motion], ["event-095", "event-090", "event-085"])
        self.assertEqual(self.events.latest_home_received("scale-home", "MOTION").event_id, "event-095")
        self.assertEqual(self.events.home_event_counts("scale-home")["CALL_FAMILY"], 20)

    def test_effective_timestamp_orders_before_limit_and_keeps_sequence_100(self):
        expected_keys = []
        for sequence in range(70, 102):
            event_id = f"c3-146393c5d158/bedroom/118/{sequence:03d}"
            expected_keys.append(event_id)
            received_at = 5000 + sequence
            if sequence in {100, 101}:
                received_at = 9000
            event = CloudEvent(
                "scale-home", event_id, "MOTION", "bedroom", 0,
                received_at, received_at, payload={},
            )
            original, duplicate = self.events.accept_once(event)
            self.assertIs(original, event)
            self.assertFalse(duplicate)

        # Exact-key retry remains idempotent and cannot consume another timeline row.
        retry = CloudEvent(
            "scale-home", expected_keys[-2], "MOTION", "bedroom", 0,
            99999, 99999, payload={"retry": True},
        )
        original, duplicate = self.events.accept_once(retry)
        self.assertTrue(duplicate)
        self.assertEqual(original.server_received_at, 9000)

        # A later Home event must not leak into this Home's bounded timeline.
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
            "VALUES(?,?,?,?,?)", ("other-home", "Other", "UTC", 1, 1),
        )
        other = CloudEvent("other-home", "other/latest", "MOTION", "bedroom", 0,
                           20000, 20000, payload={})
        self.events[(other.home_id, other.event_id)] = other

        timeline = self.events.home_events("scale-home", include_test=False,
                                           newest_first=True, limit=100)
        identifiers = [item.event_id for item in timeline]
        self.assertEqual(len(identifiers), 100)
        self.assertEqual(len(set(identifiers)), 100)
        self.assertTrue(set(expected_keys).issubset(identifiers))
        self.assertIn("c3-146393c5d158/bedroom/118/100", identifiers)
        self.assertLess(identifiers.index(expected_keys[-1]),
                        identifiers.index(expected_keys[-2]))
        self.assertNotIn(other.event_id, identifiers)

    def test_mixed_timestamp_ties_are_deterministic_and_limit_is_applied_in_sql(self):
        # Include a TEST_ONLY row and an event from another Home in the source data;
        # neither may displace authorized non-test rows from this Home's limit.
        same_time = ["tie-b", "tie-a"]
        for event_id, occurred_at, received_at in (
            ("positive-time", 7000, 8000),
            (same_time[0], 0, 9000),
            (same_time[1], None, 9000),
        ):
            event = CloudEvent("scale-home", event_id, "MOTION", "bedroom",
                               occurred_at, received_at, received_at, payload={})
            self.events[(event.home_id, event.event_id)] = event
        test_event = CloudEvent("scale-home", "test-newest", "MOTION", "bedroom",
                                0, 10000, 10000, is_test=True, payload={})
        self.events[(test_event.home_id, test_event.event_id)] = test_event

        timeline = self.events.home_events("scale-home", include_test=False,
                                           newest_first=True, limit=3)
        self.assertEqual([item.event_id for item in timeline],
                         ["tie-b", "tie-a", "positive-time"])
        self.assertEqual([item.occurred_at for item in timeline], [9000, 9000, 7000])
        self.assertEqual(len(timeline), 3)

        plan = self._plan(
            "SELECT * FROM events WHERE home_id=? AND is_test=0 "
            "ORDER BY COALESCE(NULLIF(occurred_at,0),received_at) DESC,"
            "canonical_event_id DESC LIMIT ?",
            ("scale-home", 3),
        )
        self.assertIn("idx_events_home_effective_time", plan)
        self.assertNotIn("TEMP B-TREE", plan)


class CaregiverProjectionScaleTest(unittest.TestCase):
    def test_in_memory_timeline_uses_received_time_when_generation_time_is_unavailable(self):
        lab = Lab()
        self.addCleanup(lab.close)
        lab.service.store.events = {
            ("scale-home", "received-later"): CloudEvent(
                "scale-home", "received-later", "MOTION", "bedroom", 0, 0, 500,
            ),
            ("scale-home", "generated-earlier"): CloudEvent(
                "scale-home", "generated-earlier", "MOTION", "bedroom", 300, 300, 700,
            ),
        }
        latest = lab.service.queries._events(
            "scale-home", include_test=False, newest_first=True, limit=1,
        )
        self.assertEqual([event.event_id for event in latest], ["received-later"])

    def test_historical_incidents_are_not_recursively_projected(self):
        lab = Lab()
        self.addCleanup(lab.close)
        for index in range(1000):
            lab.service.store.incidents[f"resolved-{index}"] = Incident(
                f"resolved-{index}", HOME, f"history:{index}", "CALL_FAMILY", index,
                state=IncidentState.RESOLVED,
            )
        for index in range(500):
            lab.service.store.incidents[f"active-{index}"] = Incident(
                f"active-{index}", HOME, f"active:{index}", "CALL_FAMILY", 2000 + index,
            )
        lab.service.store.incidents["active-daytime"] = Incident(
            "active-daytime", HOME, "active:daytime", "DAYTIME_INACTIVITY", 3000,
        )

        self.assertEqual(lab._active_incident_kinds(), ["CALL_FAMILY", "DAYTIME_INACTIVITY"])
        with patch("tools.sim.local_lab.asdict", wraps=asdict) as convert:
            view = lab.pwa_view("home")
        incident_conversions = [
            call for call in convert.call_args_list if isinstance(call.args[0], Incident)
        ]
        self.assertEqual(incident_conversions, [])
        self.assertTrue(view["care"]["alert"])
        self.assertIn(view["care"]["problem_kind"], {"CALL_FAMILY", "DAYTIME_INACTIVITY"})
        self.assertLessEqual(len(view["events"]), 20)

    def test_public_snapshot_keeps_active_ids_while_pwa_snapshot_can_skip_them(self):
        lab = Lab()
        self.addCleanup(lab.close)
        incident = Incident("active-one", HOME, "active:one", "CALL_FAMILY", 1)
        lab.service.store.incidents[incident.incident_id] = incident
        public = lab.service.queries.snapshot(HOME, OWNER, lab.state["now"])
        compact = lab.service.queries.snapshot(
            HOME, OWNER, lab.state["now"], include_active_incident_ids=False
        )
        self.assertIn("active-one", public["active_incidents"])
        self.assertEqual(compact["active_incidents"], [])


class StressObservabilityTest(unittest.TestCase):
    def test_cli_progress_stays_on_stderr_and_json_has_stage_timings(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/stress/run_stress.py"), "--profile", "SMALL"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        result = json.loads(completed.stdout)
        self.assertNotIn("[stress]", completed.stdout)
        self.assertIn("[stress] setup/devices: start", completed.stderr)
        self.assertIn("accepted event ingestion: 120/120 (100%)", completed.stderr)
        self.assertIn("[stress] final verification: complete", completed.stderr)
        timings = result["diagnostics"]["stage_duration_ms"]
        self.assertEqual(
            set(timings),
            {
                "setup_devices", "accepted_event_ingestion", "duplicate_replay",
                "malformed_rejection", "api_pwa_reads", "report_cycles", "final_verification",
            },
        )
        self.assertTrue(all(value >= 0 for value in timings.values()))
        self.assertEqual(
            set(result["diagnostics"]["report_period_duration_ms"]),
            {"TODAY", "WEEK", "MONTH"},
        )
        self.assertEqual(result["correctness_gate"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
