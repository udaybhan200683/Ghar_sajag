"""T01 HTTP boundary checks against the real local lab and C++ child; @requirements E02,E04,F12,NFR-08."""
from pathlib import Path
import json
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/sim"))
from local_lab import Lab, WebLab, QuietRequests

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lab=Lab()
        cls.web=WebLab(cls.lab,0)
        cls.server=make_server("127.0.0.1",0,cls.web,handler_class=QuietRequests)
        cls.web.port=cls.server.server_port
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.thread.join(); cls.server.server_close(); cls.lab.close()

    def request(self,path,body=None,headers=None,raw=False):
        h={"Content-Type":"application/json",**(headers or {})}
        req=Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=h)
        try:
            with urlopen(req,timeout=15) as response:
                data=response.read(); return response.status,data if raw else json.loads(data)
        except HTTPError as error:
            return error.code,json.loads(error.read())

    def setUp(self):
        self.request("/sim/action",{"action":"reset"})

    def test_release_scenarios_through_http(self):
        status,report=self.request("/sim/run-suite",{})
        self.assertEqual(status,200);self.assertEqual(report["status"],"PASS")
        self.assertGreaterEqual(len(report["cases"]),60); self.assertEqual(report["passed"], report["total"])

    def test_web_assets_and_reused_modules(self):
        for path in ("/","/lab.mjs","/lab.css","/src/features/home/index.mjs","/src/features/incidents/index.mjs","/src/features/routines/index.mjs","/src/platform/logging.mjs"):
            with self.subTest(path=path):
                status,data=self.request(path,raw=True);self.assertEqual(status,200);self.assertGreater(len(data),100)

    def test_event_reaches_real_snapshot_api(self):
        self.request("/sim/action",{"action":"event","node":"kitchen","kind":"MOTION"})
        status,snapshot=self.request("/v1/homes/simulation-home/snapshot",headers={"X-Actor-Id":"primary"})
        self.assertEqual(status,200);self.assertEqual(snapshot["latest_activity"]["location"],"kitchen")


    def test_call_family_then_ok_remains_chronological_and_unresolved(self):
        self.request("/sim/action",{"action":"event","node":"room1","kind":"CALL_FAMILY"})
        self.request("/sim/action",{"action":"advance","seconds":60})
        _,state=self.request("/sim/action",{"action":"event","node":"room1","kind":"OK_PRESSED"})
        self.assertEqual(state["incidents"][0]["kind"],"CALL_FAMILY")
        self.assertEqual(state["incidents"][0]["state"],"OPEN")
        self.assertEqual([e["kind"] for e in state["home"]["recent_events"][:2]],["OK_PRESSED","CALL_FAMILY"])

    def test_door_left_open_and_close_duration(self):
        self.request("/sim/action",{"action":"event","node":"entry","kind":"DOOR_OPEN"})
        self.request("/sim/action",{"action":"advance","seconds":360})
        _,state=self.request("/sim/action",{"action":"event","node":"entry","kind":"DOOR_CLOSED"})
        self.assertTrue(any(e["kind"]=="DOOR_LEFT_OPEN" for e in state["timeline"]))
        close=state["home"]["recent_events"][0]
        self.assertEqual(close["kind"],"DOOR_CLOSED")
        self.assertGreaterEqual(close["details"]["open_duration_s"],360)
        self.assertTrue(close["details"]["resolved_left_open"])


    def test_household_settings_are_versioned_and_change_door_policy(self):
        _,state=self.request("/sim/state")
        settings={k:v for k,v in state["settings"].items() if k!="config_version"}
        settings["door_open_timeout_seconds"]=120
        settings["quiet_hours_enabled"]=False
        _,state=self.request("/sim/action",{"action":"settings","settings":settings})
        self.assertGreaterEqual(state["settings"]["config_version"],2)
        status,config=self.request("/v1/homes/simulation-home/config",headers={"X-Actor-Id":"simulation-owner"})
        self.assertEqual(status,200)
        self.assertEqual(config["config"]["activity_rules"]["door_open_timeout_seconds"],120)
        self.assertEqual(config["config"]["version"], config["version"])
        self.request("/sim/action",{"action":"event","node":"entry","kind":"DOOR_OPEN","late_night":True})
        _,state=self.request("/sim/action",{"action":"advance","seconds":120})
        door_open=next(e for e in state["home"]["recent_events"] if e["kind"]=="DOOR_OPEN")
        self.assertFalse(door_open["details"].get("unexpected",False))
        self.assertTrue(any(e["kind"]=="DOOR_LEFT_OPEN" for e in state["timeline"]))

    def test_daytime_inactivity_runs_through_rule_engine_and_backend(self):
        _,state=self.request("/sim/state")
        settings={k:v for k,v in state["settings"].items() if k!="config_version"}
        settings["daytime_inactivity_seconds"]=300
        self.request("/sim/action",{"action":"settings","settings":settings})
        self.request("/sim/action",{"action":"time","minute":600})
        _,state=self.request("/sim/action",{"action":"advance","seconds":300})
        self.assertTrue(any(e["kind"]=="DAYTIME_INACTIVITY" for e in state["timeline"]))
        self.assertEqual(sum(1 for i in state["incidents"] if i["kind"]=="DAYTIME_INACTIVITY"),1)

    def test_wrong_sensor_event_combination_is_rejected(self):
        status,_=self.request("/sim/action",{"action":"event","node":"kitchen","kind":"DOOR_OPEN"})
        self.assertEqual(status,400)

    def test_privacy_toggle_is_not_a_simulation_event(self):
        status,_=self.request("/sim/action",{"action":"event","node":"room1","kind":"PRIVACY_ON"})
        self.assertEqual(status,400)

    def test_device_fault_maps_to_error_code(self):
        _,state=self.request("/sim/action",{"action":"fault","target":"kitchen","fault":"BATTERY_DEPLETED"})
        _,state=self.request("/sim/action",{"action":"troubleshoot","target":"kitchen"})
        device=next(d for d in state["devices"] if d["id"]=="kitchen")
        self.assertEqual(device["code"],"GS-N002")
        self.assertFalse(device["active"])

    def test_browser_incident_actions_and_ownership(self):
        _,state=self.request("/sim/action",{"action":"advance","seconds":1300})
        iid=state["incidents"][0]["incident_id"]
        prefix=f"/v1/homes/simulation-home/incidents/{iid}"
        self.assertEqual(self.request(prefix+"/claim",{}, {"X-Actor-Id":"primary"})[0],200)
        self.assertEqual(self.request(prefix+"/claim",{}, {"X-Actor-Id":"backup"})[0],409)
        self.assertEqual(self.request(prefix+"/acknowledge",{}, {"X-Actor-Id":"primary"})[1]["state"],"ACKNOWLEDGED")
        self.assertEqual(self.request(prefix+"/resolve",{}, {"X-Actor-Id":"primary"})[1]["state"],"RESOLVED")

    def test_unknown_actor_denied(self):
        self.assertEqual(self.request("/v1/homes/simulation-home/snapshot",headers={"X-Actor-Id":"stranger"})[0],403)

    def test_cross_origin_denied(self):
        self.assertEqual(self.request("/sim/action",{"action":"reset"},{"Origin":"https://example.com"})[0],403)

    def test_invalid_step_rejected_without_crash(self):
        self.assertEqual(self.request("/sim/action",{"action":"advance","seconds":-1})[0],400)
        self.assertEqual(self.request("/sim/state")[1]["simulation"]["now"],1000)

    def test_source_files_not_served(self):
        self.assertEqual(self.request("/backend/ghar_sajag/store.py")[0],404)

    def test_offline_missing_intent_keeps_detection_time(self):
        self.request("/sim/action",{"action":"wan","enabled":False})
        self.request("/sim/action",{"action":"advance","seconds":1300})
        self.request("/sim/action",{"action":"advance","seconds":60})
        _,state=self.request("/sim/action",{"action":"wan","enabled":True})
        self.assertEqual(len(state["incidents"]),1)
        events=[e for e in state["timeline"] if e["kind"]=="MISSING_MORNING_ACTIVITY"]
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["occurred_at"],2300)
        self.assertEqual(events[0]["received_at"],2360)

if __name__=="__main__":
    unittest.main(verbosity=2)
