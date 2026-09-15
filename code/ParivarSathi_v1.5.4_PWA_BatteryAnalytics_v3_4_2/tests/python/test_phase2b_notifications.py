"""Socket-free Phase 2B notification preference, policy and persistence checks."""
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


class Phase2BNotificationsTest(unittest.TestCase):
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

    def restart(self):
        self.lab.close()
        self.lab = Lab(self.path)
        self.web = WebLab(self.lab, 8766)

    def records(self):
        return self.call("GET", "/pwa/foundation/notifications/records")[1]

    def test_preferences_validate_and_survive_restart(self):
        code, prefs = self.call("GET", "/pwa/foundation/notifications/preferences")
        self.assertEqual(code, 200)
        updated = {**prefs["preferences"], "safety_alerts": False, "browser_alerts_enabled": True}
        self.assertEqual(self.call("PATCH", "/pwa/foundation/notifications/preferences", updated)[0], 200)
        self.assertEqual(self.call("PATCH", "/pwa/foundation/notifications/preferences", {**updated, "extra": True})[0], 400)
        self.assertEqual(self.call("PATCH", "/pwa/foundation/notifications/preferences", {**updated, "safety_alerts": "yes"})[0], 400)
        self.restart()
        self.assertEqual(self.call("GET", "/pwa/foundation/notifications/preferences")[1]["preferences"], updated)

    def test_care_event_creates_persisted_notification_record(self):
        self.assertEqual(self.call("POST", "/sim/action", {"action": "event", "node": "room1", "kind": "CALL_FAMILY"})[0], 200)
        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["category"], "SAFETY")
        self.assertEqual(records[0]["severity"], "URGENT")
        self.assertEqual(records[0]["state"], "DELIVERED")
        self.assertEqual(records[0]["title"], "Call Family requested")
        self.assertNotIn("CALL_FAMILY", json.dumps(records))
        self.restart()
        self.assertEqual(len(self.records()), 1)

    def test_disabled_category_suppresses_without_losing_event(self):
        prefs = self.call("GET", "/pwa/foundation/notifications/preferences")[1]["preferences"]
        self.call("PATCH", "/pwa/foundation/notifications/preferences", {**prefs, "safety_alerts": False})
        self.assertEqual(self.call("POST", "/sim/action", {"action": "event", "node": "room1", "kind": "CALL_FAMILY"})[0], 200)
        records = self.records()
        self.assertEqual(records[0]["state"], "SUPPRESSED")
        self.assertEqual(records[0]["suppressed_reason"], "preference_disabled")
        self.assertIn("CALL_FAMILY", {event["kind"] for event in self.lab.snapshot()["timeline"]})

    def test_delivery_failure_is_explicit_and_event_remains_recorded(self):
        self.call("POST", "/sim/action", {"action": "notification_delivery", "available": False})
        self.assertEqual(self.call("POST", "/sim/action", {"action": "event", "node": "room1", "kind": "CALL_FAMILY"})[0], 200)
        records = self.records()
        self.assertEqual(records[0]["state"], "FAILED")
        self.assertEqual(records[0]["suppressed_reason"], "delivery_unavailable")
        self.assertIn("CALL_FAMILY", {event["kind"] for event in self.lab.snapshot()["timeline"]})

    def test_duplicate_and_repeated_unresolved_concern_do_not_spam(self):
        at = self.lab.state["now"]
        event = CloudEvent("simulation-home", "manual-call-1", "CALL_FAMILY", "room1", at, at, at)
        self.lab.service.accept_hub_event(event)
        self.lab.foundation.apply_notification_event(event)
        self.lab.foundation.apply_notification_event(event)
        self.restart()
        event = self.lab.service.store.events[("simulation-home", "manual-call-1")]
        self.lab.foundation.apply_notification_event(event)
        self.assertEqual(len(self.records()), 1)

    def test_check_in_and_coverage_resolution_update_notification_state(self):
        self.lab.reset(test_fixture=True)
        original_pwa_view = self.lab.pwa_view
        self.lab.pwa_view = lambda: (_ for _ in ()).throw(AssertionError("pwa_view must not create overdue notification"))
        self.lab.action({"action": "advance", "seconds": 121})
        self.lab.pwa_view = original_pwa_view
        self.assertEqual(self.records()[0]["category"], "CHECK_IN")
        self.assertEqual(self.records()[0]["state"], "DELIVERED")
        self.lab.action({"action": "advance", "seconds": 0})
        self.assertEqual(len(self.records()), 1)
        self.restart()
        self.assertEqual(self.records()[0]["state"], "DELIVERED")
        self.lab.api_call("POST", "/v1/homes/simulation-home/events", {
            "event_id": "ok-resolves-overdue-after-restart",
            "kind": "OK_PRESSED",
            "location": "room1",
            "occurred_at": self.lab.state["now"],
            "hub_received_at": self.lab.state["now"],
            "payload": {},
        })
        self.assertEqual(self.records()[0]["state"], "RESOLVED")

        self.lab.pwa_reset_pass()
        self.call("POST", "/sim/action", {"action": "node", "node": "kitchen", "enabled": False})
        self.call("POST", "/sim/action", {"action": "advance", "seconds": 191})
        self.assertEqual(self.records()[0]["title"], "Monitoring coverage lost")
        self.call("POST", "/sim/action", {"action": "node", "node": "kitchen", "enabled": True})
        self.call("POST", "/sim/action", {"action": "advance", "seconds": 60})
        self.assertEqual(self.records()[0]["state"], "RESOLVED")

    def test_maintenance_and_raw_telemetry_do_not_create_care_notification(self):
        self.lab.pwa_reset_pass()
        at = self.lab.state["now"]
        raw = CloudEvent("simulation-home", "battery-raw", "BATTERY_RUNTIME_RECALCULATION", "kitchen", at, at, at)
        self.lab.service.store.events[(raw.home_id, raw.event_id)] = raw
        self.assertIsNone(self.lab.foundation.apply_notification_event(raw))
        self.assertEqual(self.records(), [])

    def test_explicit_test_fixture_reset_clears_notification_records(self):
        self.call("POST", "/sim/action", {"action": "event", "node": "room1", "kind": "CALL_FAMILY"})
        self.assertEqual(len(self.records()), 1)
        self.restart()
        self.assertEqual(len(self.records()), 1)
        self.lab.reset(test_fixture=True)
        self.assertEqual(self.records(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
