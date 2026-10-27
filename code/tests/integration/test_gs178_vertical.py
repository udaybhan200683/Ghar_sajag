"""GS178 software-only Node -> authenticated Hub -> mTLS/DB -> caregiver cases."""
import json
import hashlib
import os
from pathlib import Path
import unittest
import subprocess
from datetime import datetime, timezone

from gs178_stack import ProductStack, HOME, product_stack_for_test
from ghar_sajag.ownership_registry import AuthorizedHomeOperation

CODE_ROOT = Path(__file__).resolve().parents[2]
CAREGIVER_BROWSER = CODE_ROOT / "tests" / "support" / "gs178_browser.cjs"


class NodeOriginVertical(unittest.TestCase):
    def setUp(self):
        self.stack = product_stack_for_test()
        self.addCleanup(self.stack.close)
        self.stage = "NODE_HUB_BOOTSTRAP"
        self.expected = "Existing production-path assertions in " + self._testMethodName
        self.addCleanup(self.record_execution)
        campaign_id = os.environ.get("GS178_CAMPAIGN_RUN_ID")
        session_seed = os.environ.get("GS178_NODE_SESSION_ID")
        if campaign_id and (
                session_seed is None or not 1 <= len(campaign_id) <= 48 or
                not all(ch.isalnum() or ch in "-_" for ch in campaign_id)):
            raise ValueError("campaign_run_requires_safe_id_and_unique_node_session_seed")
        self.ready = self.stack.start_node(
            session_id=int(session_seed, 10) if session_seed is not None else None)
        self.cookie = self.stack.login()
        self.now = self.ready["utc"]
        self.domain = 1000
        self.stage = "PRODUCT_ASSERTIONS"

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

    def test_23_hub_link_and_wan_outage_recovery_exact_keys_and_caregiver_view(self):
        self.expected = ("Hub-link loss retains a Node event without Hub admission; restored local link "
                         "durably ACKs during WAN outage; restart and WAN recovery preserve exactly "
                         "two original EventKeys through API and caregiver browser")
        self.stage = "CURRENT_NODE_COVERAGE"
        self.covered_without_activity()
        self.assertEqual(self.view()["recent_events"], [])

        self.stage = "NODE_TO_HUB_LINK_LOSS"
        self.assertEqual(self.stack.command("radio 0")["hub_radio_available"], False)
        first = self.input(0, "motion", minute=12 * 60)
        self.assertEqual(first["delivery"], "NODE_RETAINED_NO_HUB_RESPONSE", first)
        self.assertEqual((first["ack"], first["pending"]), ("NONE", 1), first)
        first_node_key = first["event_key"]
        self.assertEqual(first_node_key,
                         f"bedroom:{self.stack.node_session_id}:1")
        self.assertEqual(self.sync()["stored"], 0)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 0)
        self.assertEqual(self.view()["recent_events"], [])

        # Existing source-freshness semantics mark old authenticated contact
        # stale; no event or activity is fabricated while the Node is unseen.
        self.domain += 200_000
        self.stack.domain_now = self.now + self.domain // 1000
        stale = self.view()
        self.assertEqual((stale["monitoring"], stale["source_freshness"]),
                         ("UNKNOWN", "STALE"), stale)
        self.assertEqual(stale["recent_events"], [])
        reports = Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        reports.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(["node", str(CAREGIVER_BROWSER)],
            input=json.dumps({"base": self.stack.human_origin,
                              "password": self.stack.password,
                              "dom": str(reports / "caregiver_outage_dom.html"),
                              "outageOnly": True}),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=90, env={**os.environ, "NODE_EXTRA_CA_CERTS": str(self.stack.ca_path)})
        self.assertEqual(result.returncode, 0, result.stdout)
        outage_browser = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(outage_browser["status"], "HOST_SIM_PASS")

        self.stage = "LOCAL_DURABLE_ACK_WITH_WAN_UNAVAILABLE"
        self.assertEqual(self.stack.command("radio 1")["hub_radio_available"], True)
        self.stack.wan_up = False
        retry_domain = self.domain + 10_000
        self.domain = retry_domain
        self.stack.domain_now = self.now + retry_domain // 1000
        retried = self.stack.command(
            f"retry 0 motion {self.now + 3} {self.stack.domain_now} "
            f"{retry_domain} {12 * 60} 0")
        first_canonical_key = (
            f"p{len('test-c3-bedroom')}:test-c3-bedroom"
            f"n{len('bedroom')}:bedroom"
            f"s{self.stack.node_session_id}q1")
        self.assertEqual((retried["ack"], retried["event_key"], retried["pending"]),
                         ("DURABLE", first_canonical_key, 0), retried)
        local_only = self.sync(connected=False)
        self.assertEqual((local_only["completed"], local_only["stored"]), (0, 1), local_only)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 0)
        self.assertEqual(self.view()["recent_events"], [])

        second = self.input(0, "motion", minute=12 * 60)
        second_canonical_key = (
            f"p{len('test-c3-bedroom')}:test-c3-bedroom"
            f"n{len('bedroom')}:bedroom"
            f"s{self.stack.node_session_id}q2")
        self.assertEqual((second["ack"], second["event_key"], second["pending"]),
                         ("DURABLE", second_canonical_key, 0), second)
        local_only = self.sync(connected=False)
        self.assertEqual((local_only["completed"], local_only["stored"]), (0, 2), local_only)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 0)
        self.assertEqual(self.view()["recent_events"], [])

        self.stage = "HUB_DURABLE_RESTART_RECOVERY"
        self.assertTrue(self.stack.command("restart")["restart"])
        self.assertEqual(self.sync(connected=False)["stored"], 2)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 0)

        self.stage = "WAN_CLOUDSYNC_AND_CAREGIVER_RECOVERY"
        self.stack.wan_up = True
        self.assertTrue(self.stack.command("refresh")["authority"])
        restored = self.sync()
        self.assertEqual((restored["submitted"], restored["completed"], restored["stored"]),
                         (2, 2, 2), restored)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 2)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM durable_event_commits").fetchone()[0], 2)

        events = self.view()["recent_events"]
        expected_keys = [
            {"physical_device_id": "test-c3-bedroom", "logical_node_id": "bedroom",
             "origin_session_id": self.stack.node_session_id, "event_sequence": 2},
            {"physical_device_id": "test-c3-bedroom", "logical_node_id": "bedroom",
             "origin_session_id": self.stack.node_session_id, "event_sequence": 1},
        ]
        self.assertEqual([event["kind"] for event in events], ["MOTION", "MOTION"])
        self.assertEqual([event["event_key"] for event in events], expected_keys)
        self.assertGreater(events[0]["occurred_at"], events[1]["occurred_at"])
        for expected_key in expected_keys:
            rows = self.stack.durable.db.execute(
                """SELECT COUNT(*) FROM events e JOIN durable_event_commits c ON c.event_id=e.event_id
                   WHERE c.home_id=? AND c.physical_device_id=? AND c.logical_node_id=?
                     AND c.origin_session_id=? AND c.event_sequence=?""",
                (HOME, expected_key["physical_device_id"], expected_key["logical_node_id"],
                 expected_key["origin_session_id"], expected_key["event_sequence"])).fetchone()[0]
            self.assertEqual(rows, 1, expected_key)

        self.stage = "CAREGIVER_BROWSER_EXACT_EVENT_KEYS"
        result = subprocess.run(["node", str(CAREGIVER_BROWSER)],
            input=json.dumps({"base": self.stack.human_origin,
                              "password": self.stack.password,
                              "dom": str(reports / "caregiver_recovered_dom.html"),
                              "eventKeys": [event["event_key"] for event in events],
                              "eventKeysOnly": True,
                              "rooms": ["bedroom"]}),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=90, env={**os.environ, "NODE_EXTRA_CA_CERTS": str(self.stack.ca_path)})
        self.assertEqual(result.returncode, 0, result.stdout)
        recovered_browser = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(recovered_browser["status"], "HOST_SIM_PASS")
        self.save_report("P0-UC-09-HUB-WAN-CAREGIVER-RECOVERY",
                         {"expected": self.expected,
                          "node_event_key_before_hub": first_node_key,
                          "api_event_keys": [event["event_key"] for event in events],
                          "outage_browser": outage_browser,
                          "recovered_browser": recovered_browser,
                          "backend_event_count": 2,
                          "durable_commit_count": 2})

    def test_03_online_silent_offline_unknown_and_authenticated_recovery(self):
        self.stack.command("health 0 1000")
        self.stack.domain_now=self.now+1
        self.assertEqual(self.stack.command("sync 1000 1")["health_accepted"],1)
        device=next(d for d in self.view("devices")["devices"] if d["logical_node_id"]=="bedroom")
        self.assertEqual((device["status"],device["coverage"]),("ONLINE","COVERED"))
        self.stack.domain_now=self.now+912
        # No new Node packet: owner snapshot alone publishes lease expiry.
        expired=self.stack.command("sync 912000 1")
        self.assertEqual(expired["health_accepted"],1,expired)
        device=next(d for d in self.view("devices")["devices"] if d["logical_node_id"]=="bedroom")
        self.assertEqual((device["status"],device["coverage"]),("OFFLINE","UNKNOWN"))
        offline_view=self.view()
        self.assertEqual(offline_view["monitoring"],"UNKNOWN")
        self.assertEqual(offline_view["source_freshness"],"CURRENT")
        self.stack.domain_now+=191
        stale_view=self.view()
        self.assertEqual(stale_view["source_freshness"],"STALE")
        self.assertEqual(stale_view["monitoring"],"UNKNOWN")
        self.assertEqual(next(d for d in self.view("devices")["devices"]
                              if d["logical_node_id"]=="bedroom")["status"],"UNKNOWN")
        self.stack.domain_now=self.now+1104
        self.stack.command("health 0 1104000")
        self.assertEqual(self.stack.command("sync 1104000 1")["health_accepted"],1)
        self.assertEqual(next(d for d in self.view("devices")["devices"]
                              if d["logical_node_id"]=="bedroom")["status"],"ONLINE")
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
        synchronized=self.sync()
        self.assertEqual((synchronized["completed"],synchronized["rules_completed"]),(3,1),synchronized)
        decisions=self.stack.durable.db.execute(
            "SELECT kind,source_event_id FROM hub_rule_decisions").fetchall()
        self.assertEqual(len(decisions),1)
        self.assertEqual(decisions[0][0],"MORNING_ROUTINE_COMPLETED")
        self.assertIsNotNone(decisions[0][1])
        self.assertIn("MORNING_ROUTINE_COMPLETED",[e["kind"] for e in self.view()["recent_events"]])
        self.assertEqual(self.view("incidents")["incidents"],[])
        self.save_report("P0-B-M-HUB_RULE_SYNC",self.view())

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
        self.stack.wan_up=False
        self.assertEqual(self.sync()["rules_completed"],0)
        self.stack.command("restart")
        self.stack.wan_up=True
        self.assertTrue(self.stack.command("refresh")["authority"])
        self.stack.drop_rule_receipt=True
        first=self.sync()
        self.assertEqual((first["completed"],first["rules_completed"]),(6,0),first)
        retried=self.sync()
        self.assertEqual((retried["completed"],retried["rules_completed"]),(0,1),retried)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM hub_rule_decisions").fetchone()[0],1)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM alerts WHERE alert_type='UNUSUAL_NIGHT_BATHROOM_ACTIVITY'").fetchone()[0],1)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT is_test FROM alerts WHERE alert_type='UNUSUAL_NIGHT_BATHROOM_ACTIVITY'").fetchone()[0],1)
        self.assertIn("UNUSUAL_NIGHT_BATHROOM_ACTIVITY",[e["kind"] for e in self.view()["recent_events"]])
        concern=[i for i in self.view("incidents")["incidents"] if i["kind"]=="UNUSUAL_NIGHT_BATHROOM_ACTIVITY"]
        self.assertEqual(len(concern),1)
        self.assertTrue(concern[0]["is_test"])
        self.stack.restart_backend()
        self.assertEqual(len([i for i in self.view("incidents")["incidents"] if i["kind"]=="UNUSUAL_NIGHT_BATHROOM_ACTIVITY"]),1)
        self.save_report("P0-C-HUB_RULE_SYNC",self.view())

    def test_11_checkin_does_not_resolve_unrelated_assistance(self):
        for node in range(4):
            self.stack.command(f"health {node} 1000")
        self.input(1,"help")
        self.input(2,"ok")
        self.assertEqual(self.stack.command(f"deadline {self.now+120} 1")["reason"],
                         "evidence_present")
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

    def test_13_hub_rule_receipt_idempotency_conflict_and_revocation(self):
        for index, minute in ((0,420),(1,421),(2,422)):
            self.input(index,"motion",minute=minute)
        self.assertEqual(self.sync()["rules_completed"],1)
        receipt=next(r for r in self.stack.receipts if r.get("path","").endswith("/hub-rule-decisions"))
        path=receipt["path"]
        original=receipt["request"]
        status, response=self.stack.hub_request(path,original)
        self.assertEqual(status,200,response)
        self.assertTrue(json.loads(response)["duplicate"])
        changed={**original,"reason":original["reason"]+" changed"}
        self.assertEqual(self.stack.hub_request(path,changed)[0],409)
        invalid={**original,"decision_id":"new-decision","source_event_key":"wrong/source"}
        self.assertEqual(self.stack.hub_request(path,invalid)[0],409)
        future={**original,"decision_id":"future-decision",
                "decided_at":self.stack.domain_now+301}
        self.assertEqual(self.stack.hub_request(path,future)[0],400)
        self.stack.issuer.revoke(self.stack.credential.fingerprint)
        self.assertEqual(self.stack.hub_request(path,original)[0],403)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM hub_rule_decisions").fetchone()[0],1)

    def test_14_rule_publication_fenced_after_home_transfer(self):
        for index, minute in ((0,420),(1,421),(2,422)):
            self.input(index,"motion",minute=minute)
        self.assertEqual(self.stack.command("restart")["restart"],True)
        owner=self.stack.durable.api.hub_ownership_registry
        self.stack.durable.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("gs177-test-new-home","Transfer fixture","UTC",self.now,self.now))
        owner.begin_transfer(self.stack.identity,AuthorizedHomeOperation("test-installer",HOME,"TRANSFER_HUB","test-transfer-rule"),
            "gs177-test-new-home",self.now+1)
        self.assertFalse(self.stack.command("refresh")["authority"])
        result=self.sync()
        self.assertEqual((result["completed"],result["rules_completed"]),(0,0),result)
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM hub_rule_decisions").fetchone()[0],0)

    def test_15_caregiver_browser_renders_hub_decision_separately(self):
        for index, minute in ((0,420),(1,421),(2,422)):
            self.input(index,"motion",minute=minute)
        self.assertEqual(self.sync()["rules_completed"],1)
        reports=Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        reports.mkdir(parents=True,exist_ok=True)
        env={**os.environ,"NODE_EXTRA_CA_CERTS":str(self.stack.ca_path)}
        result=subprocess.run(["node",str(CAREGIVER_BROWSER)],
            input=json.dumps({"base":self.stack.human_origin,"password":self.stack.password,
                              "dom":str(reports/"caregiver_rule_dom.html"),
                              "ruleKind":"MORNING_ROUTINE_COMPLETED","nodeEventCount":3}),
            text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90,env=env)
        self.assertEqual(result.returncode,0,result.stdout)
        report=json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report["status"],"HOST_SIM_PASS")
        self.save_report("P0-B-CAREGIVER-RULE-BROWSER",report)

    def test_16_door_left_open_then_close_clears_warning_without_erasing_history(self):
        opened=self.input(3,"door_open",minute=420)
        self.assertEqual(opened["ack"],"DURABLE")
        self.domain=7_200_000
        for index, kind in ((2,"motion"),(1,"motion"),(0,"motion"),(3,"ok")):
            self.input(index,kind,minute=420)
        timed=self.stack.command(f"timer {self.now+7210} 420 1")
        self.assertEqual(timed["rule_signals"],1,timed)
        self.assertEqual(self.sync()["rules_completed"],1)
        warning=[i for i in self.view("incidents")["incidents"] if i["kind"]=="DOOR_LEFT_OPEN"]
        self.assertEqual(len(warning),1)
        self.assertEqual(warning[0]["state"],"OPEN")
        closed=self.input(3,"door_close",at=self.now+7212,minute=420)
        self.assertTrue(any(s["kind"]==2 and s["resolves_prior"] for s in closed["signals"]),closed)
        self.assertEqual(self.sync()["rules_completed"],1)
        warning=[i for i in self.view("incidents")["incidents"] if i["kind"]=="DOOR_LEFT_OPEN"]
        self.assertEqual(len(warning),1)
        self.assertEqual(warning[0]["state"],"RESOLVED")
        self.assertIn("DOOR_CLOSED_AFTER_LONG_OPEN",[e["kind"] for e in self.view()["recent_events"]])
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM hub_rule_decisions").fetchone()[0],2)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM hub_rule_decisions WHERE source_event_id IS NOT NULL").fetchone()[0],2)
        self.stack.restart_backend()
        self.assertEqual([i for i in self.view("incidents")["incidents"] if i["kind"]=="DOOR_LEFT_OPEN"][0]["state"],"RESOLVED")
        self.save_report("P0-D-DOOR-CLEAR-RULE",self.view())

    def test_17_hub_rule_endpoint_is_disabled_without_explicit_test_composition(self):
        from ghar_sajag.durable_api import open_durable_event_api
        from ghar_sajag.service import GharSajagService
        ordinary=open_durable_event_api(GharSajagService(),
            self.stack.path/"default-disabled.sqlite", require_registered_ownership=True)
        try:
            self.assertIsNone(ordinary.api.hub_rule_decisions)
            status, body=ordinary.api.dispatch("POST",
                f"/v1/homes/{HOME}/hub-rule-decisions", "", {})
            self.assertEqual(status,"503 Service Unavailable")
            self.assertEqual(body["error"],"hub_rule_decision_commit_unavailable")
        finally:
            ordinary.close()

    def test_18_committed_hub_decisions_feed_the_caregiver_routines_view(self):
        for index in range(4):
            self.stack.command(f"health {index} 1000")
        for index, minute in ((0, 420), (1, 421), (2, 422)):
            result = self.input(index, "motion", minute=minute)
        self.assertTrue(any(signal["kind"] == 4 for signal in result["signals"]), result)
        synced = self.sync()
        self.assertEqual((synced["completed"], synced["rules_completed"]), (3, 1), synced)
        routines = self.view("routines")
        self.assertEqual(routines["source"], "NODE_ORIGIN_HOST_SIM")
        self.assertEqual(routines["learning_status"], "NOT_ENABLED")
        self.assertEqual(len(routines["decisions"]), 1)
        self.assertEqual(routines["decisions"][0]["kind"], "MORNING_ROUTINE_COMPLETED")
        if self.stack.postgres_dsn is not None:
            self.assertEqual(self.stack.service.store.memberships[(HOME, self.stack.actor)].role.value,
                             "CAREGIVER")
            with self.stack.lite_store.connect() as lite_db:
                session = self.stack.lite._session(
                    lite_db, {"HTTP_COOKIE": self.cookie}, HOME)
            for changed in (
                {**dict(session), "test_only": False},
                {**dict(session), "home_id": "gs177-test-other"},
                {**dict(session), "ownership_epoch": session["ownership_epoch"] + 1},
                {**dict(session), "expires_at": self.stack.domain_now},
                {**dict(session), "account_id": "gs177-test-unrostered"},
            ):
                with self.assertRaises(PermissionError):
                    self.stack.lite.product_view.dispatch(
                        changed, HOME, "overview", "GET", {}, self.stack.domain_now)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM hub_rule_decisions").fetchone()[0], 1)

        reports = Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        reports.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "NODE_EXTRA_CA_CERTS": str(self.stack.ca_path)}
        result = subprocess.run(["node", str(CAREGIVER_BROWSER)],
            input=json.dumps({"base": self.stack.human_origin, "password": self.stack.password,
                              "dom": str(reports / "caregiver_routines_dom.html"),
                              "ruleKind": "MORNING_ROUTINE_COMPLETED", "routineKind": "MORNING_ROUTINE_COMPLETED",
                              "nodeEventCount": 3}), text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=90, env=env)
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report["status"], "HOST_SIM_PASS")
        self.save_report("GS179-HUB-RULE-CAREGIVER-ROUTINES", report)

    def covered_without_activity(self):
        """Authenticated NodeHealth is coverage input, never resident activity."""
        for node in range(4):
            self.assertTrue(self.stack.command(f"health {node} 1000")["health"])
        self.stack.domain_now = self.now + 1
        self.assertEqual(self.stack.command("sync 1000 1")["health_accepted"], 4)
        self.assertEqual(self.view()["monitoring"], "COVERED")
        self.assertEqual(self.view()["recent_events"], [])

    def deadline(self, elapsed, trusted=True):
        self.domain = elapsed * 1000
        self.stack.domain_now = self.now + elapsed
        return self.stack.command(f"deadline {self.stack.domain_now} {int(trusted)}")

    def assert_no_concern(self):
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM hub_rule_decisions").fetchone()[0], 0)
        self.assertEqual(self.view("incidents")["incidents"], [])

    def observe_rule_browser(self, *, kind=None, monitoring=None):
        reports = Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        reports.mkdir(parents=True, exist_ok=True)
        config = {"base": self.stack.human_origin, "password": self.stack.password,
                  "dom": str(reports / (self._testMethodName + ".html")),
                  "nodeEventCount": 0}
        if kind:
            config["ruleKind"] = kind
        else:
            config.update(coverageOnly=True, monitoring=monitoring,
                          sourceFreshness="CURRENT", nodeCount=4)
        result = subprocess.run(["node", str(CAREGIVER_BROWSER)], input=json.dumps(config),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
            env={**os.environ, "NODE_EXTRA_CA_CERTS": str(self.stack.ca_path)})
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report["status"], "HOST_SIM_PASS")
        return report

    def test_19_covered_absence_boundary_receipt_loss_and_restart(self):
        self.expected = ("Health-only covered window: no concern before grace; one missing-morning "
                         "decision at grace; WAN/lost receipt/restarts preserve one concern and no fabricated Node event")
        self.stage = "AUTHENTICATED_COVERAGE"
        self.covered_without_activity()
        self.stage = "DEADLINE_BOUNDARY"
        self.assertEqual(self.deadline(119)["reason"], "window_not_due")
        due = self.deadline(120)
        self.assertTrue(due["create"], due)
        self.assertEqual(due["reason"], "no_qualifying_evidence")
        self.stage = "WAN_AND_HUB_RECOVERY"
        self.stack.wan_up = False
        self.assertEqual(self.sync()["rules_completed"], 0)
        self.assert_no_concern()
        self.stack.command("restart")
        for node in range(4):
            self.stack.command(f"health {node} 123000")
        self.assertEqual(self.deadline(123)["reason"], "already_created")
        self.stack.wan_up = True
        self.assertTrue(self.stack.command("refresh")["authority"])
        self.stack.drop_rule_receipt = True
        self.stage = "DURABLE_COMMIT_LOST_RECEIPT"
        self.assertEqual(self.sync()["rules_completed"], 0)
        self.stack.command("restart")
        self.assertEqual(self.sync()["rules_completed"], 1)
        self.assertEqual(self.sync()["rules_completed"], 0)
        rows = self.stack.durable.db.execute(
            "SELECT decision_id,kind,source_event_id FROM hub_rule_decisions").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0][0], rows[0][1], rows[0][2]),
                         (due["decision_id"], "MISSING_MORNING_ACTIVITY", None))
        receipts = [r for r in self.stack.receipts
                    if r.get("path", "").endswith("/hub-rule-decisions") and r["status"] in (200, 201)]
        self.assertEqual(len(receipts), 2)
        self.assertEqual({r["response"]["decision_id"] for r in receipts}, {due["decision_id"]})
        self.assertEqual([r["response"]["duplicate"] for r in receipts], [False, True])
        self.stage = "CAREGIVER_API_AND_REOPEN"
        self.stack.restart_backend()
        incidents = self.view("incidents")["incidents"]
        self.assertEqual([(i["kind"], i["severity"], i["state"]) for i in incidents],
                         [("MISSING_MORNING_ACTIVITY", "CONCERN", "OPEN")])
        self.assertEqual(self.stack.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
        timeline = self.view()["recent_events"]
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["decision_id"], due["decision_id"])
        self.assertIsNone(timeline[0].get("event_key"))
        self.stage = "CAREGIVER_BROWSER"
        self.save_report("R1AUTO-018-019-033-038", self.observe_rule_browser(kind="MISSING_MORNING_ACTIVITY"))

    def test_20_never_seen_node_is_missing_observation_not_inactivity(self):
        self.expected = "One never-seen required Node keeps monitoring UNKNOWN and creates no absence concern, including restart"
        self.stage = "PARTIAL_NODE_COVERAGE"
        for node in range(3):
            self.stack.command(f"health {node} 1000")
        self.stack.domain_now = self.now + 1
        self.assertEqual(self.stack.command("sync 1000 1")["health_accepted"], 3)
        self.stage = "UNKNOWN_SUPPRESSES_ABSENCE"
        self.assertEqual(self.deadline(120)["reason"], "coverage_unknown")
        self.stack.command("restart")
        self.assertEqual(self.deadline(121)["reason"], "coverage_unknown")
        self.sync()
        self.assert_no_concern()
        self.assertEqual(self.view()["monitoring"], "UNKNOWN")
        self.stage = "CAREGIVER_UNKNOWN_BROWSER"
        self.save_report("R1AUTO-012-018-NO-OBSERVATION", self.observe_rule_browser(monitoring="UNKNOWN"))

    def test_21_expired_coverage_suppresses_absence_then_contact_recovers(self):
        self.expected = "Expired Node coverage suppresses inactivity; authenticated contact restores coverage without inventing activity or a concern"
        self.covered_without_activity()
        self.stage = "EXPIRED_COVERAGE"
        self.assertEqual(self.deadline(912)["reason"], "coverage_unknown")
        self.assertEqual(self.sync()["health_accepted"], 4)
        self.assertEqual(self.view()["monitoring"], "UNKNOWN")
        self.assert_no_concern()
        self.stage = "AUTHENTICATED_CONTACT_RECOVERY"
        for node in range(4):
            self.stack.command(f"health {node} {self.domain+1000}")
        self.domain += 1000
        self.assertEqual(self.sync()["health_accepted"], 4)
        self.assertEqual(self.view()["monitoring"], "COVERED")
        self.assertEqual(self.view()["recent_events"], [])
        self.assert_no_concern()
        # Present contact cannot establish whether the preceding window was
        # observed. Full-window gap history remains a separate implementation gap.
        self.save_report("R1AUTO-012-013-018-RECOVERY", self.view())

    def test_22_untrusted_rule_time_and_modes_suppress_until_eligible(self):
        self.expected = "Untrusted domain time and Away/Paused/Privacy suppress concern; trusted Home eligibility permits one decision"
        self.covered_without_activity()
        self.stage = "UNTRUSTED_RULE_TIME"
        self.assertEqual(self.deadline(120, trusted=False)["reason"], "time_untrusted")
        for mode in ("away", "paused", "privacy"):
            with self.subTest(mode=mode):
                self.stage = "MODE_SUPPRESSION_" + mode.upper()
                self.stack.command("mode " + mode)
                self.assertEqual(self.deadline(121)["reason"], "mode_suppressed")
                self.sync()
                self.assert_no_concern()
        self.stage = "ELIGIBLE_HOME_RECOVERY"
        self.stack.command("mode home")
        due = self.deadline(130)
        self.assertTrue(due["create"], due)
        self.assertEqual(self.sync()["rules_completed"], 1)
        self.assertEqual(len(self.view("incidents")["incidents"]), 1)
        self.save_report("R1AUTO-018-019-021-022", self.view())

    def record_execution(self):
        result = self._outcome.result
        failures = [message for test, message in result.failures + result.errors if test is self]
        # Subtest failures carry the parent test in test_case.
        failures += [message for test, message in result.failures + result.errors
                     if getattr(test, "test_case", None) is self]
        self.save_report(self._testMethodName,
            {"expected": self.expected, "failure": "\n".join(failures) or None},
            status="FAIL" if failures else "HOST_SIM_PASS",
            first_failed_stage=self.stage if failures else None)

    def save_report(self, case_id, outcome, *, status="HOST_SIM_PASS", first_failed_stage=None):
        path=Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        path.mkdir(parents=True,exist_ok=True)
        payload={"scenario_id":case_id,"status":status,"physical_status":"NOT_RUN",
            "actual_android_status":"APK_NOT_VERIFIED", "first_failed_stage":first_failed_stage,
            "test_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_revision":subprocess_revision(),"trace":self.stack.trace,
            "backend_receipts":self.stack.receipts,"caregiver":outcome,
            "generated_at_utc":datetime.now(timezone.utc).isoformat()}
        campaign_id = os.environ.get("GS178_CAMPAIGN_RUN_ID")
        if campaign_id:
            payload["campaign_run_id"] = campaign_id
            payload["node_session_id"] = self.stack.node_session_id
        (path/(case_id+".json")).write_text(json.dumps(payload,indent=2)+"\n")

    def test_07_actual_shared_caregiver_browser_and_actions(self):
        # Establish current, authenticated contact for every enrolled Node so
        # the Home card can assert COVERED rather than merely rendering events.
        for node in range(4):
            self.stack.command(f"health {node} 1000")
        self.stack.domain_now = self.now + 1
        health = self.stack.command("sync 1000 1")
        self.assertEqual(health["health_accepted"], 4, health)
        initial_view = self.view()
        self.assertEqual(initial_view["monitoring"], "COVERED", initial_view)
        self.assertEqual(initial_view["source_freshness"], "CURRENT", initial_view)
        self.input(0,"motion")
        self.input(1,"help")
        self.assertEqual(self.sync()["completed"],2)
        active_incidents=[item for item in self.view("incidents")["incidents"]
                          if item["state"] in {"OPEN","CLAIMED","ROUTE_EXHAUSTED"}]
        expected_heading=("Urgent incident needs attention"
                          if any(item["severity"]=="URGENT" for item in active_incidents)
                          else "A home concern needs attention"
                          if any(item["severity"]=="CONCERN" for item in active_incidents)
                          else "Monitoring coverage is current")
        committed = [receipt for receipt in self.stack.receipts
            if receipt.get("path") == f"/v1/homes/{HOME}/events"
            and receipt.get("status") in (200, 201)
            and receipt.get("response", {}).get("status") == "COMMITTED"]
        self.assertEqual(len(committed), 2, self.stack.receipts)
        receipt_keys = [receipt["request"]["event_key"] for receipt in committed]
        stored_keys = []
        for receipt in committed:
            key = receipt["response"].get("event_key")
            self.assertEqual(key, receipt["request"].get("event_key"))
            rows = self.stack.durable.db.execute(
                """SELECT e.canonical_event_id FROM events e
                   JOIN durable_event_commits c ON c.event_id=e.event_id
                   WHERE c.home_id=? AND c.physical_device_id=? AND c.logical_node_id=?
                     AND c.origin_session_id=? AND c.event_sequence=?""",
                (HOME, key["physical_device_id"], key["logical_node_id"],
                 key["origin_session_id"], key["event_sequence"])).fetchall()
            self.assertEqual(len(rows), 1, key)
            provenance = self.stack.service.store.events.event_provenance(
                HOME, rows[0]["canonical_event_id"])
            self.assertEqual(provenance.get("event_key"), key)
            stored_keys.append(provenance["event_key"])
        self.assertCountEqual(stored_keys, receipt_keys)
        campaign_id = os.environ.get("GS178_CAMPAIGN_RUN_ID")
        if campaign_id:
            self.assertRegex(campaign_id, r"^[A-Za-z0-9_-]{1,48}$")
            bedroom_keys = [key for key in receipt_keys
                            if key["physical_device_id"] == "test-c3-bedroom"]
            self.assertEqual(len(bedroom_keys), 1, bedroom_keys)
            self.assertEqual(
                bedroom_keys[0], {
                    "physical_device_id": "test-c3-bedroom",
                    "logical_node_id": "bedroom",
                    "origin_session_id": self.stack.node_session_id,
                    "event_sequence": 1,
                })
        timeline_keys = [event["event_key"] for event in self.view()["recent_events"]]
        self.assertCountEqual(timeline_keys, receipt_keys)
        reports=Path(os.environ.get("GS178_REPORT_DIR", "build/gs178_evidence"))
        reports.mkdir(parents=True,exist_ok=True)
        env={**os.environ,"NODE_EXTRA_CA_CERTS":str(self.stack.ca_path)}
        result=subprocess.run(["node",str(CAREGIVER_BROWSER)],
            input=json.dumps({"base":self.stack.human_origin,"password":self.stack.password,
                              "dom":str(reports/"caregiver_dom.html"),
                              "eventKeys":timeline_keys,
                              "nodeCount":4,
                              "monitoring":"COVERED",
                              "sourceFreshness":"CURRENT",
                              "expectedMonitoringHeading":expected_heading,
                              "source":"TEST_ONLY · authenticated GS-148 caregiver data"}),
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
