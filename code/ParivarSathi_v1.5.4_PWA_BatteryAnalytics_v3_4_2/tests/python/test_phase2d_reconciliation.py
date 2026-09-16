"""Phase 2D reconciliation/performance contracts."""
import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.sim.local_lab import Lab, WebLab
from tools.validation.functional_scenarios import _assert_one
from tools.validation.pwa_frontend_validation import execute_for_frontend


class Phase2DReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lab = Lab(Path(self.temp.name) / "app.sqlite")
        self.web = WebLab(self.lab, 8766)

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def call(self, method, path, body=None, query=""):
        raw = json.dumps(body or {}).encode()
        statuses = []
        env = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "HTTP_HOST": "127.0.0.1:8766",
            "HTTP_X_ACTOR_ID": "simulation-owner",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": BytesIO(raw),
        }
        payload = json.loads(b"".join(self.web(env, lambda status, headers: statuses.append(status))))
        return int(statuses[0][:3]), payload

    def test_home_state_scope_excludes_on_demand_phase2_payloads(self):
        self.call("POST", "/sim/action", {"action": "node", "node": "kitchen", "enabled": False})
        status, home = self.call("GET", "/pwa/state", query="scope=home")
        self.assertEqual(status, 200)
        self.assertIn("care", home)
        self.assertIn("device_health", home)
        self.assertIn("events", home)
        self.assertLessEqual(len(home["events"]), 20)
        self.assertIn("kitchen", home["device_health"]["offline_devices"])
        self.assertEqual(home["device_health"]["offline_device_names"]["kitchen"], "Kitchen Node")
        self.assertNotEqual(home["device_health"]["offline_device_names"]["kitchen"], "kitchen")
        for on_demand_key in ("devices", "home_details", "family_members", "schedules", "network", "reports", "notifications", "raw"):
            self.assertNotIn(on_demand_key, home)

        status, full = self.call("GET", "/pwa/state")
        self.assertEqual(status, 200)
        self.assertIn("devices", full)
        self.assertIn("schedules", full)
        self.assertIn("home_details", full)

    def test_home_state_rejects_unknown_scope(self):
        status, payload = self.call("GET", "/pwa/state", query="scope=everything")
        self.assertEqual(status, 400)
        self.assertIn("invalid PWA state scope", payload["error"])

    def test_pwa_validation_run_isolates_durable_event_history(self):
        first = execute_for_frontend(self.lab, "motion-kitchen-visible")
        self.assertTrue(first["steps_passed"])

        replay = execute_for_frontend(self.lab, "wan-reconnect-replays")
        self.assertTrue(replay["steps_passed"])
        motion_count = {
            "select": "timeline",
            "where": {"kind": "MOTION"},
            "count": 1,
        }
        ok, detail = _assert_one(replay["state"], motion_count)
        self.assertTrue(ok, detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
