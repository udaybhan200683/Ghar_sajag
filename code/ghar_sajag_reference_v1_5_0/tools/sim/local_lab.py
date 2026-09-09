#!/usr/bin/env python3
"""T01 local integration laboratory, release 1.5.0.

@requirements E01-E05,F01,F05-F08,F10,F12,F13,NFR-08,NFR-09.
One WSGI owner drives one C++ child. Pipes substitute for device transport;
JsonApi and the existing backend services handle the API-side business logic.
Never deploy this test-identity/in-memory adapter as a production service.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from io import BytesIO
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import selectors
import subprocess
import sys
import time
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from ghar_sajag.http_api import JsonApi
from ghar_sajag.model import HomeMode
from ghar_sajag.service import GharSajagService

HOME = "simulation-home"
OWNER = "simulation-owner"
NODES = ["room1", "kitchen", "entry", "pooja"]
KINDS = ["MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY", "HEARTBEAT", "PRIVACY_ON", "PRIVACY_OFF"]


class Lab:
    """Owns process lifetime, synthetic clock, fixture data and bounded diagnostic trail."""
    def __init__(self):
        (ROOT / "logs").mkdir(exist_ok=True)
        self.log = logging.getLogger("simulation_lab")
        if not self.log.handlers:
            h = RotatingFileHandler(ROOT / "logs/e2e_flow.txt", maxBytes=131072, backupCount=2)
            h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self.log.addHandler(h)
            self.log.setLevel(logging.INFO)
            self.log.propagate = False
        self.stderr = open(ROOT / "logs/e2e_child_stderr.txt", "w", encoding="utf-8")
        self.proc = subprocess.Popen([str(ROOT / "build/ghar_sajag_interactive")], cwd=ROOT,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                                     text=True, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.report = {"status": "NOT_RUN", "cases": []}
        try:
            self.reset()
        except Exception:
            self.close()
            raise

    def close(self):
        self.selector.close()
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.stderr):
            stream.close()

    def command(self, line):
        # Only server-generated fixed command tokens cross this boundary.
        if self.proc.poll() is not None:
            raise RuntimeError("C++ simulator stopped; restart the laboratory")
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        if not self.selector.select(timeout=5):
            self.proc.kill()
            raise RuntimeError("C++ simulator timed out; restart the laboratory")
        output = self.proc.stdout.readline()
        if not output:
            raise RuntimeError("C++ simulator exited")
        self.state = json.loads(output)
        if "error" in self.state:
            raise ValueError("Simulator refused command; reset after capacity exhaustion")
        self.log.info("category=SIM module=T01 event=command command=%s sim_time=%s", line, self.state["now"])
        return self.state

    def api_call(self, method, path, body=None, actor=OWNER):
        """Run the real WSGI JSON adapter, including JSON encoding and route matching."""
        raw = json.dumps(body or {}).encode()
        captured = []
        chunks = self.api({"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_X_ACTOR_ID": actor,
                           "CONTENT_LENGTH": str(len(raw)), "wsgi.input": BytesIO(raw)},
                          lambda status, headers: captured.append(status))
        result = json.loads(b"".join(chunks))
        if not captured[0].startswith("2"):
            raise ValueError(result.get("error", captured[0]))
        return result

    def reset(self):
        self.command("reset")
        self.service = GharSajagService()
        self.api = JsonApi(self.service, now=lambda: self.state["now"])
        self.api_call("POST", "/v1/homes", {"home_id": HOME, "display_name": "Synthetic demo home",
                      "timezone": "Asia/Kolkata", "residents": [{"resident_id": "demo-resident",
                      "display_name": "Demo resident", "consent_active": True}]})
        self.service.homes.set_caregivers(HOME, OWNER, "primary", "backup", self.state["now"])
        self.heartbeat_id = 0
        self.sync()

    def sync(self):
        if not self.state["wan"]:
            return
        events = list(self.state["events"])
        for event in events:
            result = self.api_call("POST", f"/v1/homes/{HOME}/events", event)
            self.log.info("category=SIM module=B03 event=ingest id=%s duplicate=%s", event["event_id"], result["duplicate"])
            # Existing API says DURABLE, but its store is memory. Label this MODEL commitment in UI/docs.
            if result.get("commit") != "DURABLE":
                raise RuntimeError("Missing backend model acknowledgement")
            self.command("ack " + event["event_id"])
        if self.state["missing_pending"]:
            self.api_call("POST", f"/v1/homes/{HOME}/events", {"event_id": "missing:sim-morning",
                          "kind": "MISSING_MORNING_ACTIVITY", "occurred_at": self.state["missing_at"],
                          "hub_received_at": self.state["missing_at"], "payload": {"window_id": "sim-morning"}})
            self.command("ack_missing")
        self.heartbeat_id += 1
        self.api_call("POST", f"/v1/homes/{HOME}/events", {"event_id": f"hub:{self.heartbeat_id}",
                      "kind": "HUB_HEARTBEAT", "occurred_at": self.state["now"],
                      "hub_received_at": self.state["now"]})

    def action(self, body):
        """Translate lab controls only; eligibility decisions stay inside the original C++ rules."""
        action = body.get("action")
        if action == "reset":
            self.reset()
        elif action == "event":
            node = NODES.index(body.get("node"))
            kind = KINDS.index(body.get("kind"))
            self.command(f"event {node} {kind}")
            if kind in (6, 7):
                self.service.homes.set_mode(HOME, OWNER, HomeMode(self.state["mode"]), self.state["now"])
            self.sync()
        elif action == "advance":
            seconds = body.get("seconds")
            if type(seconds) is not int or not 0 <= seconds <= 3600:
                raise ValueError("seconds must be an integer from 0 to 3600")
            self.command(f"advance {seconds}")
            self.sync()
        elif action in ("wan", "clock", "node"):
            if type(body.get("enabled")) is not bool:
                raise ValueError("enabled must be a boolean")
            value = int(body["enabled"])
            token = f"node {NODES.index(body.get('node'))} {value}" if action == "node" else f"{action} {value}"
            self.command(token)
            self.sync()
        elif action in ("duplicate", "deadline"):
            self.command(action)
            self.sync()
        elif action == "notify":
            for job in self.service.notifications.due(self.state["now"]):
                self.service.notifications.provider_result(job.job_id, body.get("accepted", True) is True, "FAKE-PROVIDER")
        elif action in ("claim", "acknowledge", "resolve"):
            incident = body.get("incident_id")
            if not isinstance(incident, str) or not incident.startswith("inc_") or not incident[4:].isalnum():
                raise ValueError("invalid incident id")
            actor = body.get("actor", "primary")
            if actor not in ("primary", "backup"):
                raise ValueError("invalid simulation caregiver")
            self.api_call("POST", f"/v1/homes/{HOME}/incidents/{incident}/{action}", actor=actor)
        else:
            raise ValueError("unknown action")
        return self.snapshot()

    def snapshot(self):
        return {"simulation": {k: v for k, v in self.state.items() if k != "events"},
                "home": self.api_call("GET", f"/v1/homes/{HOME}/snapshot"),
                "incidents": [asdict(v) for v in self.service.store.incidents.values()],
                "notifications": [asdict(v) for v in self.service.store.notification_jobs.values()],
                "timeline": self.service.queries.timeline(HOME, OWNER, self.state["now"], limit=40),
                "limitations": ["Synthetic sensors, clock, transport and notification provider",
                                "Node, hub and backend data are volatile; reset/restart clears them",
                                "Coverage is a current lease, not proof of continuous historical coverage",
                                "Duplicate journal writes are suppressed; duplicate reducer evidence remains a known gap",
                                "No physical prompts, SMS, push, OTA, RF or battery simulation"]}

    def run_suite(self):
        """Independent assertions across implemented cross-language flows, not full P0 sign-off."""
        results = []
        def run(name, steps, predicate, expected):
            try:
                self.reset()
                for step in steps:
                    self.action(step)
                state = self.snapshot()
                passed = bool(predicate(state))
                results.append({"name": name, "passed": passed, "expected": expected,
                                "reason": state["simulation"]["reason"],
                                "incident_count": len(state["incidents"])})
            except Exception as error:
                results.append({"name": name, "passed": False, "expected": expected, "error": type(error).__name__})
        motion = {"action":"event", "node":"kitchen", "kind":"MOTION"}
        end = {"action":"advance", "seconds":1300}
        run("normal_morning", [motion,end], lambda s:s["simulation"]["activity_seen"] and not s["incidents"], "Activity travels node → hub → backend; no absence incident")
        run("quiet_covered", [end], lambda s:len(s["incidents"])==1 and len(s["notifications"])==2, "One missing-activity incident and primary/backup jobs")
        run("quiet_uncovered", [{"action":"node","node":"kitchen","enabled":False},end], lambda s:s["simulation"]["reason"]=="coverage_unknown" and not s["incidents"], "Unavailable coverage suppresses absence incident")
        run("clock_untrusted", [{"action":"clock","enabled":False},end], lambda s:s["simulation"]["reason"]=="time_untrusted" and not s["incidents"], "Untrusted time suppresses absence incident")
        run("resident_ok", [{"action":"event","node":"room1","kind":"OK_PRESSED"},end], lambda s:s["simulation"]["explicit_ok"] and not s["incidents"], "Resident check-in supplies evidence")
        run("privacy", [{"action":"event","node":"room1","kind":"PRIVACY_ON"},motion,end], lambda s:s["home"]["mode"]=="PRIVACY" and not s["incidents"] and not s["home"]["event_counts"].get("MOTION"), "Privacy drops passive motion before cloud ingestion")
        run("wan_loss", [{"action":"wan","enabled":False},motion,{"action":"advance","seconds":240}], lambda s:s["simulation"]["activity_seen"] and s["simulation"]["pending_cloud"]>0 and not s["home"]["hub_reachable"] and not s["home"]["event_counts"].get("MOTION"), "Local evidence progresses; backend becomes stale")
        run("wan_replay", [{"action":"wan","enabled":False},motion,{"action":"wan","enabled":True}], lambda s:s["home"]["event_counts"].get("MOTION")==1 and s["simulation"]["pending_cloud"]==0, "Reconnect replays and acknowledges pending model records")
        run("manual_call_replay", [{"action":"wan","enabled":False},{"action":"event","node":"room1","kind":"CALL_FAMILY"},{"action":"wan","enabled":True}], lambda s:len(s["incidents"])==1 and s["incidents"][0]["kind"]=="CALL_FAMILY", "Offline call produces incident after reconnect")
        run("duplicate_storage", [motion,{"action":"duplicate"}], lambda s:s["home"]["event_counts"].get("MOTION")==1 and s["simulation"]["evidence_count"]==2, "One backend motion; known duplicate reducer evidence is explicitly exposed")
        run("notification_acceptance", [end,{"action":"notify"}], lambda s:s["incidents"][0]["state"]=="OPEN" and s["notifications"][0]["state"]=="PROVIDER_ACCEPTED", "Fake provider acceptance does not acknowledge the incident")
        run("node_link_replay", [{"action":"node","node":"kitchen","enabled":False},motion,{"action":"node","node":"kitchen","enabled":True}], lambda s:s["home"]["event_counts"].get("MOTION")==1 and s["simulation"]["nodes"][1]["retained"]==0, "Retained node event reaches the hub after its link is restored")
        # Dynamic incident identity must come from the real backend, never a canned fixture ID.
        self.reset(); self.action(end)
        identity = self.snapshot()["incidents"][0]["incident_id"]
        self.action({"action":"claim","incident_id":identity})
        self.action({"action":"acknowledge","incident_id":identity})
        self.action({"action":"resolve","incident_id":identity})
        final = self.snapshot()
        results.append({"name":"caregiver_lifecycle", "passed": final["incidents"][0]["state"]=="RESOLVED" and all(j["state"]=="CANCELLED" for j in final["notifications"]), "expected":"Claim → acknowledge → resolve, cancel pending escalation"})
        self.report = {"version":"1.5.0", "status":"PASS" if all(r["passed"] for r in results) else "FAIL",
                       "scope":"Host adapter integration; not complete P0 acceptance", "cases":results,
                       "limitations":final["limitations"]}
        (ROOT/"logs/e2e_report.json").write_text(json.dumps(self.report,indent=2)+"\n")
        (ROOT/"logs/e2e_report.txt").write_text("Ghar Sajag host integration 1.5.0\n"+"\n".join(f"{'PASS' if r['passed'] else 'FAIL'} {r['name']}: {r['expected']}" for r in results)+"\n")
        return self.report


class WebLab:
    def __init__(self, lab, port):
        self.lab, self.port = lab, port

    def __call__(self, environ, start_response):
        # Restrict the local lab to its own origin. No wildcard bind/CORS or real user authentication.
        host = environ.get("HTTP_HOST", "")
        allowed = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        origin = environ.get("HTTP_ORIGIN")
        if host not in allowed or (origin and origin not in {"http://"+h for h in allowed}):
            status, result = "403 Forbidden", {"error":"local_origin_required"}
        else:
            try:
                return self.route(environ, start_response)
            except (ValueError, KeyError, TypeError) as error:
                status, result = "400 Bad Request", {"error":str(error)[:200]}
            except PermissionError:
                status, result = "403 Forbidden", {"error":"not_authorized"}
            except RuntimeError as error:
                status, result = "409 Conflict", {"error":str(error)[:200]}
            except Exception:
                self.lab.log.exception("category=SIM module=T01 event=request_failed")
                status, result = "500 Internal Server Error", {"error":"See logs/e2e_flow.txt"}
        return self.json_response(start_response, result, status)

    @staticmethod
    def json_response(start, result, status="200 OK"):
        data = json.dumps(result).encode()
        start(status, [("Content-Type","application/json"),("Content-Length",str(len(data))),("Cache-Control","no-store")])
        return [data]

    def route(self, env, start):
        path, method = env.get("PATH_INFO","/"), env.get("REQUEST_METHOD","GET")
        if method == "GET" and path == "/sim/state":
            return self.json_response(start,self.lab.snapshot())
        if method == "GET" and path == "/sim/report":
            return self.json_response(start,self.lab.report)
        if method == "POST" and path in ("/sim/action","/sim/run-suite"):
            if not env.get("CONTENT_TYPE", "").startswith("application/json"):
                raise ValueError("application/json required")
            length = int(env.get("CONTENT_LENGTH") or 0)
            if not 0 <= length <= 8192:
                raise ValueError("request too large")
            body = json.loads(env["wsgi.input"].read(length) or b"{}")
            if not isinstance(body,dict):
                raise ValueError("object required")
            result = self.lab.run_suite() if path.endswith("run-suite") else self.lab.action(body)
            return self.json_response(start,result)
        if path.startswith("/v1/") or path == "/healthz":
            if int(env.get("CONTENT_LENGTH") or 0)>8192:
                raise ValueError("request too large")
            return self.lab.api(env,start)
        # Exact allowlist keeps source/config/log files out of the HTTP file surface.
        assets = {"/":("tools/sim/web/index.html","text/html"),
                  "/lab.mjs":("tools/sim/web/lab.mjs","text/javascript"),
                  "/lab.css":("tools/sim/web/lab.css","text/css"),
                  "/src/features/home/index.mjs":("app/src/features/home/index.mjs","text/javascript"),
                  "/src/features/incidents/index.mjs":("app/src/features/incidents/index.mjs","text/javascript"),
                  "/src/platform/logging.mjs":("app/src/platform/logging.mjs","text/javascript")}
        if method != "GET" or path not in assets:
            return self.json_response(start,{"error":"not_found"},"404 Not Found")
        file, mime = assets[path]
        data = (ROOT/file).read_bytes()
        start("200 OK",[("Content-Type",mime),("Content-Length",str(len(data))),("Cache-Control","no-store"),("X-Content-Type-Options","nosniff")])
        return [data]


class QuietRequests(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--test",action="store_true")
    args=parser.parse_args()
    lab=Lab()
    try:
        if args.test:
            report=lab.run_suite()
            print(json.dumps(report,indent=2))
            return 0 if report["status"]=="PASS" else 1
        with make_server("127.0.0.1",args.port,WebLab(lab,args.port),handler_class=QuietRequests) as server:
            print(f"Ghar Sajag local simulation: http://localhost:{args.port}",flush=True)
            print("Synthetic data only. Ctrl+C stops both processes. Reset clears scenario state.",flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        lab.close()

if __name__ == "__main__":
    raise SystemExit(main())
