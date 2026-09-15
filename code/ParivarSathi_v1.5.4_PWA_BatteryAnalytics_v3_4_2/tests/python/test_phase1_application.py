"""Socket-free WSGI/application-path tests for the Phase 1 foundation."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from tools.sim.local_lab import Lab, WebLab


class Phase1ApplicationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "app.sqlite"
        self.lab = Lab(self.path)
        self.web = WebLab(self.lab, 8765)

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def call(self, method, path, body=None, actor="simulation-owner"):
        raw = json.dumps(body or {}).encode()
        statuses = []
        env = {"REQUEST_METHOD":method,"PATH_INFO":path,"HTTP_HOST":"127.0.0.1:8765",
               "HTTP_X_ACTOR_ID":actor,"CONTENT_TYPE":"application/json","CONTENT_LENGTH":str(len(raw)),"wsgi.input":BytesIO(raw)}
        value = json.loads(b"".join(self.web(env, lambda status, headers: statuses.append(status))))
        return int(statuses[0][:3]), value

    def test_home_save_restart_validation_and_authorization(self):
        code, home = self.call("GET", "/pwa/foundation/home")
        self.assertEqual(code, 200)
        self.assertEqual(home["display_name"], "Synthetic demo home")
        code, _ = self.call("PATCH", "/pwa/foundation/home", {"display_name":"","timezone":"Asia/Kolkata","language":"en-IN"})
        self.assertEqual(code, 400)
        code, _ = self.call("PATCH", "/pwa/foundation/home", {"display_name":"Family home","timezone":"Asia/Kolkata","language":"hi-IN"}, actor="unknown")
        self.assertEqual(code, 403)
        code, _ = self.call("PATCH", "/pwa/foundation/home", {"display_name":"Family home","timezone":"Asia/Kolkata","language":"hi-IN"})
        self.assertEqual(code, 200)
        self.lab.close()
        self.lab = Lab(self.path)
        self.web = WebLab(self.lab, 8765)
        self.assertEqual(self.call("GET", "/pwa/foundation/home")[1]["display_name"], "Family home")

    def test_family_crud_and_deactivation(self):
        member={"member_id":"anita-1","display_name":"Anita","relationship":"Daughter","role":"FAMILY","contact":"anita@example.org"}
        self.assertEqual(self.call("POST","/pwa/foundation/members",member)[0],201)
        self.assertEqual(self.call("POST","/pwa/foundation/members",member)[0],400)
        self.assertEqual(self.call("PATCH","/pwa/foundation/members/anita-1",{"display_name":"Anita Rao","relationship":"Daughter","role":"CAREGIVER","contact":"anita@example.org"})[0],200)
        self.assertEqual(self.call("DELETE","/pwa/foundation/members/simulation-owner",{})[0],400)
        self.assertEqual(self.call("DELETE","/pwa/foundation/members/anita-1",{})[0],200)
        self.assertFalse(next(m for m in self.call("GET","/pwa/foundation/members")[1] if m["member_id"]=="anita-1")["active"])

    def test_device_application_path_history_and_simulation(self):
        self.lab.pwa_reset_pass()
        before = len(self.lab.snapshot()["timeline"])
        d={"device_id":"bath-2","display_name":"Bathroom two","kind":"NODE","capability":"MOTION","room":"Bathroom"}
        self.assertEqual(self.call("POST","/pwa/foundation/devices",d)[0],201)
        self.assertEqual(self.call("POST","/pwa/foundation/devices",d)[0],400)
        self.assertEqual(self.call("POST","/pwa/foundation/devices",{**d,"device_id":"bad-2","capability":"DOOR_OPEN"})[0],400)
        self.assertEqual(self.call("GET","/pwa/foundation/devices/bath-2")[1]["room"],"Bathroom")
        self.assertEqual(self.call("PATCH","/pwa/foundation/devices/bath-2",{"display_name":"Renamed","room":"Kitchen","enabled":True})[0],200)
        self.assertEqual(self.call("POST","/pwa/foundation/devices/bath-2/health",{"online":True,"health":"ACTIVE","battery_mv":3900,"battery_percent":40,"drain_status":"NORMAL"})[0],200)
        self.assertEqual(next(x for x in self.lab.pwa_view()["devices"] if x["id"]=="bath-2")["battery"],40)
        self.assertEqual(self.call("DELETE","/pwa/foundation/devices/hub",{})[0],400)
        self.assertEqual(self.call("DELETE","/pwa/foundation/devices/bath-2",{})[0],200)
        self.assertNotIn("bath-2",{x["id"] for x in self.lab.pwa_view()["devices"]})
        self.assertGreaterEqual(len(self.lab.snapshot()["timeline"]),before)
        self.assertEqual(self.call("GET","/pwa/foundation/devices/absent")[0],404)

    def test_policy_persistence_and_backend_effect(self):
        baseline = self.call("GET","/pwa/foundation/policy")[1]
        settings = {**baseline["settings"],"battery_alert_percent":35,"critical_battery_percent":10,"night_bathroom_visit_threshold":2}
        self.assertEqual(self.call("PATCH","/pwa/foundation/policy",settings)[0],200)
        self.assertEqual(self.lab.household_settings["night_bathroom_visit_threshold"],2)
        self.assertEqual(self.lab.config_version,2)
        self.assertEqual(self.call("PATCH","/pwa/foundation/policy",{**settings,"critical_battery_percent":35})[0],400)
        self.assertEqual(self.call("GET","/pwa/foundation/policy")[1]["settings"]["critical_battery_percent"],10)
        self.assertEqual(self.call("PATCH","/pwa/foundation/policy",{**settings,"morning_start_minute":settings["morning_end_minute"]})[0],400)
        self.assertEqual(self.call("PATCH","/pwa/foundation/policy",{**settings,"battery_alert_percent":51})[0],400)
        self.assertEqual(self.call("PATCH","/pwa/foundation/policy",{**settings,"battery_alert_percent":1})[0],400)
        self.lab.close();self.lab=Lab(self.path);self.web=WebLab(self.lab,8765)
        self.assertEqual(self.lab.household_settings["battery_alert_percent"],35)

    def test_simulated_device_heartbeat_refresh_and_stale_expiry(self):
        d={"device_id":"stale-2","display_name":"Stale node","kind":"NODE","capability":"MOTION","room":"Kitchen"}
        health={"online":True,"health":"ACTIVE","battery_mv":3900,"battery_percent":40,"drain_status":"NORMAL"}
        self.assertEqual(self.call("POST","/pwa/foundation/devices",d)[0],201)
        self.assertEqual(self.call("POST","/pwa/foundation/devices/stale-2/health",{**health,"online":False})[0],400)
        self.assertEqual(self.call("POST","/pwa/foundation/devices/stale-2/health",health)[0],200)
        self.lab.action({"action":"advance","seconds":100})
        self.assertEqual(self.call("POST","/pwa/foundation/devices/stale-2/health",health)[0],200)
        self.lab.action({"action":"advance","seconds":100})
        self.assertTrue(next(x for x in self.lab.pwa_view()["devices"] if x["id"]=="stale-2")["active"])
        self.lab.action({"action":"advance","seconds":91})
        self.assertFalse(next(x for x in self.lab.pwa_view()["devices"] if x["id"]=="stale-2")["active"])
        self.assertEqual(self.call("GET","/pwa/foundation/devices/stale-2")[1]["health"],"OFFLINE")

    def test_storage_failure_is_explicit_and_does_not_change_state(self):
        prior=self.call("GET","/pwa/foundation/home")[1]
        self.lab.foundation.db.execute("PRAGMA query_only = ON")
        code,result=self.call("PATCH","/pwa/foundation/home",{"display_name":"Unsaved","timezone":"Asia/Kolkata","language":"en-IN"})
        self.lab.foundation.db.execute("PRAGMA query_only = OFF")
        self.assertEqual(code,500)
        self.assertIn("error",result)
        self.assertEqual(self.call("GET","/pwa/foundation/home")[1]["display_name"],prior["display_name"])


if __name__ == "__main__": unittest.main()
