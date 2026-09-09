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
            # HTTPError owns the response stream too. Negative tests must close
            # it explicitly, including when JSON decoding raises an exception.
            # This prevents implicit-cleanup ResourceWarnings on Python 3.14.
            with error:
                return error.code,json.loads(error.read())

    def setUp(self):
        self.request("/sim/action",{"action":"reset"})

    def test_13_scenarios_through_http(self):
        status,report=self.request("/sim/run-suite",{})
        self.assertEqual(status,200);self.assertEqual(report["status"],"PASS")
        self.assertEqual(len(report["cases"]),13)

    def test_web_assets_and_reused_modules(self):
        for path in ("/","/lab.mjs","/lab.css","/src/features/home/index.mjs","/src/features/incidents/index.mjs","/src/platform/logging.mjs"):
            with self.subTest(path=path):
                status,data=self.request(path,raw=True);self.assertEqual(status,200);self.assertGreater(len(data),100)

    def test_event_reaches_real_snapshot_api(self):
        self.request("/sim/action",{"action":"event","node":"kitchen","kind":"MOTION"})
        status,snapshot=self.request("/v1/homes/simulation-home/snapshot",headers={"X-Actor-Id":"primary"})
        self.assertEqual(status,200);self.assertEqual(snapshot["latest_activity"]["location"],"kitchen")

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
