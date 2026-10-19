"""GS178 software-only Node -> authenticated Hub -> mTLS/DB -> caregiver cases."""
import json
import os
from pathlib import Path
import unittest
import subprocess

from gs178_stack import ProductStack, HOME
from ghar_sajag.ownership_registry import AuthorizedHomeOperation


class NodeOriginVertical(unittest.TestCase):
    def setUp(self):
        self.stack = ProductStack()
        self.addCleanup(self.stack.close)
        self.ready = self.stack.start_node()
        self.cookie = self.stack.login()
        self.now = self.ready["utc"]
        self.domain = 1000

    def input(self, node, kind, *, at=None, minute=7*60, drop=False):
        self.domain += 2000
        self.stack.domain_now = self.now + self.domain//1000
        return self.stack.command(f"input {node} {kind} {at or self.stack.domain_now} {self.stack.domain_now} {self.domain} {minute} {int(drop)}")

    def view(self, sub="overview", cookie=None):
        status, data, _ = self.stack.human("GET", f"/lite/v1/homes/{HOME}/{sub}", cookie=self.cookie if cookie is None else cookie)
        self.assertEqual(status, 200, data)
        return data

    def sync(self, connected=True):
        self.domain += 2000
        self.stack.domain_now = self.now+self.domain//1000
        return self.stack.command(f"sync {self.domain} {int(connected)}")

    def test_01_motion_door_ok_help_and_caregiver_persistent_actions(self):
        self.assertEqual(self.ready["stage"], "CLOUDSYNC_READY")
        for node,kind in [(0,"motion"),(3,"door_open"),(3,"door_close"),(2,"ok"),(1,"help")]:
            result=self.input(node,kind)
            self.assertEqual((result["ack"], result["pending"]), ("DURABLE",0))
            self.assertTrue(result["changed"])
        result=self.sync()
        self.assertEqual((result["submitted"],result["completed"]),(5,5), result)
        view=self.view()
        self.assertEqual([e["kind"] for e in view["recent_events"]],
                         ["CALL_FAMILY","OK_PRESSED","DOOR_CLOSED","DOOR_OPEN","MOTION"])
        self.assertEqual(view["recent_events"][-1]["event_key"]["logical_node_id"],"bedroom")
        self.assertTrue(all(e.get("event_key") for e in view["recent_events"]))
        self.assertEqual(view["door_status"]["state"],"CLOSED")
        incidents=self.view("incidents")["incidents"]
        self.assertEqual([(i["kind"],i["state"],i["severity"]) for i in incidents],[("CALL_FAMILY","OPEN","URGENT")])
        incident=incidents[0]["incident_id"]
        self.assertEqual(len(self.stack.durable.api.durable_events.due_outbox(self.stack.domain_now)),1)
        for action,state in [("claim","CLAIMED"),("acknowledge","ACKNOWLEDGED"),("resolve","RESOLVED")]:
            status,body,_=self.stack.human("POST",f"/lite/v1/homes/{HOME}/incidents/{incident}/{action}",{},self.cookie)
            self.assertEqual((status,body.get("state")),(200,state),body)
        self.stack.restart_backend()
        self.assertEqual(self.view("incidents")["incidents"][0]["state"],"RESOLVED")
        self.assertEqual(self.view("reports")["event_count"],5)
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM acknowledgements").fetchone()[0],3)
        self.assertEqual(self.stack.durable.api.durable_events.due_outbox(self.stack.domain_now),[])
        self.save_report("P0-A-D-E-F-K-L",view)

    def test_02_wan_loss_lost_ack_restart_exactly_once_and_delayed_chronology(self):
        first=self.input(0,"motion",drop=True)
        self.assertEqual(first["pending"],1)
        self.stack.wan_up=False
        failed=self.sync()
        self.assertEqual(failed["completed"],0)
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],0)
        self.stack.command("restart")
        self.domain+=10000
        duplicate=self.stack.command(f"retry 0 motion {self.now} {self.now+20} {self.domain} 420 0")
        self.assertEqual((duplicate["changed"],duplicate["event_key"],duplicate["pending"]),(False,first["event_key"],0))
        self.stack.wan_up=True
        self.assertTrue(self.stack.command("refresh")["authority"])
        self.stack.drop_receipt=True
        lost=self.sync()
        self.assertEqual(lost["completed"],0)
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0],1)
        self.stack.command("restart")
        self.assertEqual(self.sync()["completed"],1)
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],1)
        # Backlogged event arrives later but retains original occurrence time.
        delayed=self.input(2,"motion",at=self.now-3600)
        self.assertEqual(delayed["last_activity_at"],self.now+3)
        self.assertEqual(self.sync()["completed"],1)
        events=self.view()["recent_events"]
        self.assertEqual(len(events),2)
        self.assertEqual(events[-1]["occurred_at"],self.now-3600)
        self.assertTrue(events[-1]["delayed"])
        self.stack.restart_backend()
        self.assertEqual(len(self.view()["recent_events"]),2)
        self.save_report("P0-I-J-K",events)

    def test_03_online_silent_offline_unknown_and_authenticated_recovery(self):
        self.stack.command("health 0 1000")
        self.stack.domain_now=self.now+1
        self.assertEqual(self.stack.command("sync 1000 1")["health_accepted"],1)
        device=self.view("devices")["devices"][0]
        self.assertEqual((device["status"],device["coverage"]),("ONLINE","COVERED"))
        self.stack.domain_now=self.now+912
        # No new Node packet: owner snapshot alone publishes lease expiry.
        expired=self.stack.command("sync 912000 1")
        self.assertEqual(expired["health_accepted"],1,expired)
        device=self.view("devices")["devices"][0]
        self.assertEqual((device["status"],device["coverage"]),("OFFLINE","UNKNOWN"))
        self.assertEqual(self.view()["monitoring"],"UNKNOWN")
        self.stack.domain_now+=191
        self.assertEqual(self.view("devices")["devices"][0]["status"],"UNKNOWN")
        self.stack.domain_now=self.now+1104
        self.stack.command("health 0 1104000")
        self.assertEqual(self.stack.command("sync 1104000 1")["health_accepted"],1)
        self.assertEqual(self.view("devices")["devices"][0]["status"],"ONLINE")
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],0)
        self.save_report("P0-G-H",self.view("devices"))

    def test_04_current_ownership_revocation_and_session_home_denials(self):
        self.input(0,"motion")
        self.assertEqual(self.sync()["completed"],1)
        self.assertEqual(self.stack.human("GET",f"/lite/v1/homes/{HOME}/overview")[0],403)
        self.assertEqual(self.stack.human("GET","/lite/v1/homes/gs177-test-other/overview",cookie=self.cookie)[0],403)
        self.stack.issuer.revoke(self.stack.credential.fingerprint)
        self.assertFalse(self.stack.command("refresh")["authority"])
        self.input(2,"motion")
        self.assertEqual(self.sync()["submitted"],0)
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],1)
        self.stack.human("POST","/lite/v1/auth/logout",{},self.cookie)
        self.assertEqual(self.stack.human("GET",f"/lite/v1/homes/{HOME}/overview",cookie=self.cookie)[0],403)

    def test_05_transfer_fences_old_home(self):
        owner=self.stack.durable.api.hub_ownership_registry
        self.stack.durable.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("gs177-test-new-home","Transfer fixture","UTC",self.now,self.now))
        owner.begin_transfer(self.stack.identity,AuthorizedHomeOperation("test-installer",HOME,"TRANSFER_HUB","test-transfer"),"gs177-test-new-home",self.now+1)
        self.assertFalse(self.stack.command("refresh")["authority"])
        self.input(0,"motion")
        self.assertEqual(self.sync()["submitted"],0)

    def test_06_existing_deterministic_morning_and_mode_suppression(self):
        for i in range(4): self.stack.command(f"health {i} 1000")
        self.input(0,"motion",minute=420)
        self.input(1,"motion",minute=421)
        completed=self.input(2,"motion",minute=422)
        self.assertTrue(any(s["kind"]==4 for s in completed["signals"]),completed)
        self.assertFalse(self.stack.command(f"deadline {self.now+121} 1")["create"])
        self.assertFalse(self.stack.command(f"deadline {self.now+121} 0")["create"])
        for mode in ("away","paused","privacy"):
            self.stack.command("mode "+mode)
            self.assertFalse(self.stack.command(f"deadline {self.now+121} 1")["create"])
        # Do not claim rule concern delivery: the durable derived-rule cloud
        # outbox is still an explicit product seam, separate from raw events.
        self.assertEqual(self.sync()["completed"],3)
        self.save_report("P0-B-M-HUB_RULE_ONLY",completed)

    def test_08_mixed_trusted_profiles_strict_boundaries(self):
        for index,profile,interval in [(0,"configured",300),(1,"legacy_60",60),(2,"legacy_120",120)]:
            self.stack.profiles["test-c3-"+["bedroom","bathroom","kitchen"][index]]=profile
            self.stack.command(f"profile {index} {profile} {interval}")
            self.stack.command(f"health {index} 1000")
        self.stack.domain_now=self.now+1
        self.assertEqual(self.stack.command("sync 1000 1")["health_accepted"],3)
        for seconds,expected in [(191,["ONLINE","ONLINE","ONLINE"]),(192,["ONLINE","OFFLINE","ONLINE"]),
                                 (311,["ONLINE","OFFLINE","ONLINE"]),(312,["ONLINE","OFFLINE","OFFLINE"]),
                                 (911,["ONLINE","OFFLINE","OFFLINE"]),(912,["OFFLINE","OFFLINE","OFFLINE"])]:
            self.stack.domain_now=self.now+seconds
            self.stack.command(f"sync {seconds*1000} 1")
            # Read freshness expires without a new Hub snapshot; UNKNOWN is
            # truthful and must not be mistaken for another lease transition.
            rows={r["logical_node_id"]:r for r in self.view("devices")["devices"]}
            for room,status in zip(("bedroom","bathroom","kitchen"),expected):
                actual=rows[room]["status"]
                self.assertIn(actual,(status,"UNKNOWN"))
            if seconds in (192,312,912):
                room={192:"bathroom",312:"kitchen",912:"bedroom"}[seconds]
                self.assertEqual(rows[room]["status"],"OFFLINE")
        self.save_report("P0-G-MIXED-PROFILES",self.view("devices"))

    def test_09_changed_payload_is_rejected_but_original_retry_survives_restart(self):
        first=self.input(0,"motion",drop=True)
        self.stack.command("restart")
        self.domain+=10000
        conflict=self.stack.command(f"conflict 0 motion {self.now} {self.now+20} {self.domain} 420 1")
        self.assertEqual((conflict["ack"],conflict["pending"]),("REJECTED",1))
        self.domain+=10000
        retry=self.stack.command(f"retry 0 motion {self.now} {self.now+30} {self.domain} 420 0")
        self.assertEqual((retry["ack"],retry["changed"],retry["event_key"]),("DURABLE",False,first["event_key"]))
        self.assertEqual(self.sync()["completed"],1)
        self.save_report("P0-J-IMMUTABLE-CONFLICT",retry)

    def test_10_deterministic_night_rule_and_unknown_clock_boundary(self):
        # Software rule inputs are configured; this is not a GS104 learned baseline.
        for i in range(4): self.input(i,"motion",minute=60)
        self.domain+=301000
        second=self.input(1,"motion",minute=66)
        self.assertFalse(any(s["kind"]==5 and s["create"] for s in second["signals"]))
        self.domain+=301000
        result=self.input(1,"motion",minute=72)
        self.assertTrue(any(s["kind"]==5 and s["create"] for s in result["signals"]),result)
        self.assertFalse(self.stack.command(f"deadline {self.now+121} 0")["create"])
        self.assertEqual(self.sync()["completed"],6)
        self.save_report("P0-C-HUB_RULE_ONLY",result)

    def test_11_checkin_does_not_resolve_unrelated_assistance(self):
        self.input(1,"help")
        self.input(2,"ok")
        self.assertEqual(self.sync()["completed"],2)
        self.assertEqual(self.view()["recent_events"][0]["kind"],"OK_PRESSED")
        concern=self.view("incidents")["incidents"][0]
        self.assertEqual((concern["kind"],concern["state"]),("CALL_FAMILY","OPEN"))
        path=f"/lite/v1/homes/{HOME}/incidents/{concern['incident_id']}/resolve"
        self.assertEqual(self.stack.human("POST",path,{})[0],403)
        self.assertEqual(self.stack.human("POST",path.replace(HOME,"gs177-test-other"),{},self.cookie)[0],403)
        self.stack.restart_backend()
        self.assertEqual(self.view("incidents")["incidents"][0]["state"],"OPEN")
        self.save_report("P0-E-L-UNRELATED-CONCERN",self.view())

    def test_12_existing_privacy_drop_and_explicit_assistance(self):
        self.stack.command("mode privacy")
        dropped=self.input(0,"motion")
        self.assertEqual((dropped["ack"],dropped["pending"]),("DISCARDED_POLICY",0))
        self.assertEqual(self.sync()["completed"],0)
        self.assertEqual(self.view()["recent_events"],[])
        self.input(1,"help")
        self.assertEqual(self.sync()["completed"],1)
        self.assertEqual(self.view("incidents")["incidents"][0]["kind"],"CALL_FAMILY")
        self.save_report("P0-M-PRIVACY-POLICY",self.view())

    def save_report(self, case_id, outcome):
        path=Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        path.mkdir(parents=True,exist_ok=True)
        payload={"scenario_id":case_id,"status":"HOST_SIM_PASS","physical_status":"NOT_RUN",
            "source_revision":subprocess_revision(),"trace":self.stack.trace,
            "backend_receipts":self.stack.receipts,"caregiver":outcome}
        (path/(case_id+".json")).write_text(json.dumps(payload,indent=2)+"\n")

    def test_07_actual_shared_caregiver_browser_and_actions(self):
        self.input(0,"motion")
        self.input(1,"help")
        self.assertEqual(self.sync()["completed"],2)
        reports=Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        reports.mkdir(parents=True,exist_ok=True)
        env={**os.environ,"NODE_EXTRA_CA_CERTS":str(self.stack.ca_path)}
        result=subprocess.run(["node","tests/support/gs178_browser.cjs"],
            input=json.dumps({"base":self.stack.human_origin,"password":self.stack.password,
                              "dom":str(reports/"caregiver_dom.html")}),
            text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90,env=env)
        self.assertEqual(result.returncode,0,result.stdout)
        report=json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report["status"],"HOST_SIM_PASS")
        self.assertEqual(self.view("incidents")["incidents"][0]["state"],"RESOLVED")
        self.save_report("P0-L-CAREGIVER-BROWSER",report)


def subprocess_revision():
    import subprocess
    return subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()


if __name__=="__main__": unittest.main()
