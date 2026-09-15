"""Focused Phase 2C Home/Settings/cross-feature integration checks."""
import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from tools.sim.local_lab import Lab, WebLab


class Phase2CIntegrationTest(unittest.TestCase):
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
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "", "HTTP_HOST": "127.0.0.1:8766",
               "HTTP_X_ACTOR_ID": actor, "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": BytesIO(raw)}
        payload = json.loads(b"".join(self.web(env, lambda status, headers: statuses.append(status))))
        return int(statuses[0][:3]), payload

    def records(self):
        return self.call("GET", "/pwa/foundation/notifications/records")[1]

    def test_backend_check_in_overdue_drives_home_without_pwa_request(self):
        self.lab.reset(test_fixture=True)
        original_pwa_view = self.lab.pwa_view
        self.lab.pwa_view = lambda: (_ for _ in ()).throw(AssertionError("pwa_view must not create overdue state"))
        self.lab.action({"action": "advance", "seconds": 121})
        self.lab.pwa_view = original_pwa_view

        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["category"], "CHECK_IN")
        self.assertEqual(records[0]["state"], "DELIVERED")

        view = self.lab.pwa_view()
        self.assertEqual(view["iam_ok"]["status"], "OVERDUE")
        self.assertTrue(view["care"]["alert"])
        self.lab.action({"action": "advance", "seconds": 0})
        self.assertEqual(len(self.records()), 1)

        self.lab.action({"action": "event", "node": "room1", "kind": "OK_PRESSED"})
        resolved = self.records()
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["state"], "RESOLVED")
        acknowledged = self.lab.pwa_view()
        self.assertEqual(acknowledged["iam_ok"]["status"], "ACKNOWLEDGED")
        self.assertTrue(any(event["kind"] == "OK_PRESSED" for event in self.lab.snapshot()["timeline"]))

    def test_i_am_ok_elapsed_time_is_backend_derived(self):
        self.lab.pwa_reset_pass()
        self.lab.action({"action": "advance", "seconds": 120})
        view = self.lab.pwa_view()
        self.assertTrue(view["iam_ok"]["ok"])
        self.assertEqual(view["iam_ok"]["last_ok_age_s"], 120)
        self.assertFalse(view["care"]["alert"])

    def test_suppressed_check_in_overdue_still_drives_home_until_resolved(self):
        prefs = self.call("GET", "/pwa/foundation/notifications/preferences")[1]["preferences"]
        self.call("PATCH", "/pwa/foundation/notifications/preferences", {**prefs, "check_in_alerts": False})
        self.lab.reset(test_fixture=True)
        prefs = self.call("GET", "/pwa/foundation/notifications/preferences")[1]["preferences"]
        self.call("PATCH", "/pwa/foundation/notifications/preferences", {**prefs, "check_in_alerts": False})
        self.lab.action({"action": "advance", "seconds": 121})
        self.assertEqual(self.records()[0]["state"], "SUPPRESSED")
        self.assertEqual(self.lab.pwa_view()["iam_ok"]["status"], "OVERDUE")
        self.lab.action({"action": "event", "node": "room1", "kind": "OK_PRESSED"})
        self.assertEqual(self.records()[0]["state"], "RESOLVED")
        self.assertTrue(self.lab.pwa_view()["iam_ok"]["ok"])

    def test_device_maintenance_notification_is_separate_from_care_and_reports(self):
        prefs = self.call("GET", "/pwa/foundation/notifications/preferences")[1]["preferences"]
        self.call("PATCH", "/pwa/foundation/notifications/preferences", {**prefs, "device_maintenance_alerts": True})
        view = self.lab.pwa_toggle("battery")

        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["category"], "DEVICE_MAINTENANCE")
        self.assertEqual(records[0]["state"], "DELIVERED")
        self.assertIn("Kitchen Node battery needs attention", records[0]["title"])
        self.assertNotIn("mAh", json.dumps(records))
        self.assertFalse(view["care"]["alert"])
        self.assertFalse(any("battery" in event["text"].lower() for event in view["events"]))

        report = self.lab.service.queries.report("simulation-home", "simulation-owner", self.lab.state["now"], "TODAY")
        self.assertEqual(report["summary"]["event_count"], 0)
        self.lab.pwa_toggle("battery")
        self.assertEqual(self.records()[0]["state"], "RESOLVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
