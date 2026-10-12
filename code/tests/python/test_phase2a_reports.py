"""Socket-free Phase 2A Reports projection/API checks."""
import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from ghar_sajag.model import CloudEvent
from tools.sim.local_lab import Lab, WebLab


class Phase2AReportsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "app.sqlite"
        self.lab = Lab(self.path)
        self.web = WebLab(self.lab, 8766)

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def call(self, method, path, body=None, actor="simulation-owner"):
        raw = json.dumps(body or {}).encode()
        statuses = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
            "HTTP_HOST": "127.0.0.1:8766",
            "HTTP_X_ACTOR_ID": actor,
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": BytesIO(raw),
        }
        payload = json.loads(b"".join(self.web(environ, lambda status, headers: statuses.append(status))))
        return int(statuses[0][:3]), payload

    def restart(self):
        self.lab.close()
        self.lab = Lab(self.path)
        self.web = WebLab(self.lab, 8766)

    def event(self, event_id, kind, occurred_at, location="room1", payload=None):
        event = {
            "event_id": event_id,
            "kind": kind,
            "location": location,
            "occurred_at": occurred_at,
            "hub_received_at": occurred_at,
            "payload": payload or {},
        }
        return self.call("POST", "/v1/homes/simulation-home/events", event)

    def report(self, period):
        return self.call("GET", f"/v1/homes/simulation-home/reports?period={period}")

    def test_no_data_is_explicit_and_not_an_error(self):
        code, report = self.report("TODAY")
        self.assertEqual(code, 200)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "NO_DATA")
        self.assertEqual(report["summary"]["event_count"], 0)
        self.assertEqual(report["window"]["boundary"], "start_inclusive_end_exclusive")

    def test_today_week_and_month_reports_are_backend_derived(self):
        _, today = self.report("TODAY")
        start, end = today["window"]["start_at"], today["window"]["end_at"]
        self.assertEqual(self.event("today-start", "OK_PRESSED", start)[0], 202)
        self.assertEqual(self.event("today-door", "DOOR_OPEN", start + 60, "entry")[0], 202)
        self.assertEqual(self.event("today-morning", "MORNING_ROUTINE_COMPLETED", start + 120, "kitchen")[0], 202)
        self.lab.service.store.events[("simulation-home", "today-excluded")] = CloudEvent("simulation-home", "today-excluded", "CALL_FAMILY", "room1", end, end, end)
        self.lab.service.store.events[("simulation-home", "week-history")] = CloudEvent("simulation-home", "week-history", "CALL_FAMILY", "room1", start - 3600, start - 3600, start - 3600)

        code, today = self.report("TODAY")
        self.assertEqual(code, 200)
        self.assertEqual(today["status"], "DATA")
        self.assertEqual(today["summary"]["event_count"], 3)
        self.assertEqual(today["summary"]["check_ins"], 1)
        self.assertEqual(today["summary"]["door_openings"], 1)
        self.assertEqual(today["summary"]["morning_completed"], 1)

        self.assertEqual(self.report("WEEK")[1]["summary"]["event_count"], 4)
        month = self.report("MONTH")[1]
        self.assertGreaterEqual(month["summary"]["event_count"], 4)
        self.assertGreaterEqual(len(month["trend"]), 28)

    def test_event_history_survives_normal_restart_for_all_report_periods(self):
        _, today = self.report("TODAY")
        start = today["window"]["start_at"]
        self.assertEqual(self.event("persist-ok", "OK_PRESSED", start + 30)[0], 202)
        self.assertEqual(self.event("persist-door", "DOOR_OPEN", start + 60, "entry")[0], 202)
        self.lab.service.store.events[("simulation-home", "persist-week")] = CloudEvent("simulation-home", "persist-week", "CALL_FAMILY", "room1", start - 3600, start - 3600, start - 3600)

        self.restart()

        today = self.report("TODAY")[1]
        week = self.report("WEEK")[1]
        month = self.report("MONTH")[1]
        self.assertEqual(today["summary"]["event_count"], 2)
        self.assertEqual(today["summary"]["check_ins"], 1)
        self.assertEqual(week["summary"]["event_count"], 3)
        self.assertEqual(month["summary"]["event_count"], 2)
        self.assertEqual([item["at"] for item in week["highlights"]], sorted((item["at"] for item in week["highlights"]), reverse=True))

    def test_duplicate_replayed_events_are_counted_once(self):
        _, today = self.report("TODAY")
        start = today["window"]["start_at"]
        self.assertEqual(self.event("dup-ok", "OK_PRESSED", start + 30)[0], 202)
        self.restart()
        self.assertEqual(self.event("dup-ok", "OK_PRESSED", start + 30)[0], 200)
        report = self.report("TODAY")[1]
        self.assertEqual(report["summary"]["check_ins"], 1)
        self.assertEqual(report["summary"]["event_count"], 1)

    def test_removed_device_history_remains_reportable(self):
        _, today = self.report("TODAY")
        start = today["window"]["start_at"]
        device = {"device_id": "bath-2", "display_name": "Bathroom two", "kind": "NODE", "capability": "MOTION", "room": "Bathroom"}
        self.assertEqual(self.call("POST", "/pwa/foundation/devices", device)[0], 201)
        self.assertEqual(self.event("removed-device-history", "MOTION", start + 90, "bath-2")[0], 202)
        self.assertEqual(self.call("DELETE", "/pwa/foundation/devices/bath-2", {})[0], 200)
        self.restart()
        report = self.report("TODAY")[1]
        self.assertEqual(report["summary"]["activity_events"], 1)
        self.assertIn("Bath 2", {item["location"] for item in report["room_activity"]})
        self.assertEqual(self.call("GET", "/pwa/foundation/devices/bath-2")[1]["registered"], 0)

    def test_concerns_resolved_history_and_coverage_are_separate_from_maintenance(self):
        _, today = self.report("TODAY")
        start = today["window"]["start_at"]
        self.assertEqual(self.event("coverage-lost", "COVERAGE_CHANGED", start + 10, "kitchen", {"reason": "coverage_lost"})[0], 202)
        self.assertEqual(self.event("coverage-restored", "COVERAGE_CHANGED", start + 20, "kitchen", {"reason": "coverage_restored"})[0], 202)
        self.lab.service.store.events[("simulation-home", "raw-battery")] = CloudEvent("simulation-home", "raw-battery", "BATTERY_RUNTIME_RECALCULATION", "kitchen", start + 30, start + 30, start + 30)
        report = self.report("TODAY")[1]
        self.assertEqual(report["summary"]["coverage_lost"], 1)
        self.assertEqual(report["summary"]["coverage_restored"], 1)
        self.assertEqual(report["summary"]["event_count"], 2)
        self.assertNotIn("battery", json.dumps(report).lower())

    def test_invalid_report_requests_are_rejected(self):
        self.assertEqual(self.report("YEAR")[0], 400)
        self.assertEqual(self.call("GET", "/v1/homes/simulation-home/reports")[0], 400)
        self.assertEqual(self.call("GET", "/v1/homes/simulation-home/reports?period=TODAY&range=all")[0], 400)

    def test_explicit_test_fixture_reset_clears_durable_event_history(self):
        _, today = self.report("TODAY")
        start = today["window"]["start_at"]
        self.assertEqual(self.event("reset-clears", "OK_PRESSED", start + 30)[0], 202)
        self.restart()
        self.assertEqual(self.report("TODAY")[1]["summary"]["event_count"], 1)
        self.lab.reset(test_fixture=True)
        self.assertEqual(self.report("TODAY")[1]["summary"]["event_count"], 0)

    def test_persisted_household_timezone_drives_report_window_after_restart(self):
        original = self.call("GET", "/pwa/foundation/home")[1]
        self.assertEqual(original["timezone"], "Asia/Kolkata")
        asia_start = self.report("TODAY")[1]["window"]["start_at"]
        self.assertLess(asia_start, 0)

        updated = {"display_name": original["display_name"], "timezone": "Etc/UTC", "language": original["language"]}
        self.assertEqual(self.call("PATCH", "/pwa/foundation/home", updated)[0], 200)
        self.restart()

        report = self.report("TODAY")[1]
        self.assertEqual(report["timezone"], "Etc/UTC")
        self.assertEqual(report["window"]["start_at"], 0)
        self.assertEqual(self.call("GET", "/pwa/foundation/home")[1]["timezone"], "Etc/UTC")


if __name__ == "__main__":
    unittest.main(verbosity=2)
