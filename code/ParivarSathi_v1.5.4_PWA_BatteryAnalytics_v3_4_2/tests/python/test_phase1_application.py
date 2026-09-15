"""Socket-free WSGI/application-path tests for the Phase 1 foundation."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from tools.sim.local_lab import Lab, WebLab
from ghar_sajag.model import CloudEvent


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
        history_before=self.lab.foundation.db.execute("SELECT COUNT(*) FROM device_health_history WHERE device_id='bath-2'").fetchone()[0]
        self.assertEqual(self.call("DELETE","/pwa/foundation/devices/hub",{})[0],400)
        self.assertEqual(self.call("DELETE","/pwa/foundation/devices/bath-2",{})[0],200)
        self.assertNotIn("bath-2",{x["id"] for x in self.lab.pwa_view()["devices"]})
        self.assertGreater(history_before,0)
        self.assertEqual(self.lab.foundation.db.execute("SELECT COUNT(*) FROM device_health_history WHERE device_id='bath-2'").fetchone()[0],history_before)
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

    def test_pwa_schedule_action_round_trips_exact_value(self):
        settings = self.call("GET", "/pwa/foundation/policy")[1]["settings"]
        settings["night_bathroom_visit_threshold"] = 3
        code, projection = self.call("POST", "/pwa/action", {"action":"settings_save", "settings":settings})
        self.assertEqual(code, 200)
        self.assertEqual(projection["schedules"]["night_bathroom_visit_threshold"], 3)
        self.assertEqual(self.call("GET", "/pwa/foundation/policy")[1]["settings"]["night_bathroom_visit_threshold"], 3)
        self.lab.reset()
        self.assertEqual(self.call("GET", "/pwa/state")[1]["schedules"]["night_bathroom_visit_threshold"], 3)

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

    def test_test_fixture_isolated_but_normal_restart_is_durable(self):
        self.lab.pwa_reset_pass()
        edited={"display_name":"Durable family home","timezone":"Asia/Kolkata","language":"hi-IN"}
        self.assertEqual(self.call("PATCH","/pwa/foundation/home",edited)[0],200)
        self.assertEqual(self.call("POST","/pwa/foundation/devices",{"device_id":"extra-1","display_name":"Extra","kind":"NODE","capability":"MOTION","room":"Kitchen"})[0],201)
        self.assertEqual(self.call("POST","/pwa/foundation/devices/extra-1/health",{"online":True,"health":"ACTIVE","battery_mv":3900,"battery_percent":40,"drain_status":"NORMAL"})[0],200)
        self.lab.reset()  # normal simulator reset does not erase saved application state
        self.assertEqual(self.call("GET","/pwa/foundation/home")[1]["display_name"],edited["display_name"])
        self.lab.close();self.lab=Lab(self.path);self.web=WebLab(self.lab,8765)
        self.assertEqual(self.call("GET","/pwa/foundation/home")[1]["display_name"],edited["display_name"])
        self.assertIn("extra-1",{d["device_id"] for d in self.call("GET","/pwa/foundation/devices")[1]})
        self.lab.pwa_reset_pass()
        self.assertEqual(self.call("GET","/pwa/foundation/home")[1]["display_name"],"Synthetic demo home")
        self.assertNotIn("extra-1",{d["device_id"] for d in self.call("GET","/pwa/foundation/devices")[1]})
        self.assertEqual(self.lab.foundation.db.execute("SELECT COUNT(*) FROM device_health_history WHERE home_id=?",(self.lab.foundation.home_id,)).fetchone()[0],7)

    def test_daytime_inactivity_then_offline_missing_is_order_independent(self):
        settings={**self.lab.household_settings,"daytime_inactivity_seconds":300}
        self.lab.action({"action":"settings","settings":settings})
        self.lab.action({"action":"time","minute":600})
        self.lab.action({"action":"advance","seconds":300})
        self.assertIn("DAYTIME_INACTIVITY",{e["kind"] for e in self.lab.snapshot()["timeline"]})
        self.lab.reset(test_fixture=True)
        self.lab.action({"action":"wan","enabled":False})
        self.lab.action({"action":"advance","seconds":1300})
        self.lab.action({"action":"advance","seconds":60})
        self.lab.action({"action":"wan","enabled":True})
        concerns=[e for e in self.lab.snapshot()["timeline"] if e["kind"] in {"DAYTIME_INACTIVITY","MISSING_MORNING_ACTIVITY"}]
        self.assertEqual([(e["kind"],e["occurred_at"],e["received_at"]) for e in concerns],[("MISSING_MORNING_ACTIVITY",2300,2360)])

    def test_maintenance_audit_is_retained_but_excluded_from_home_feed(self):
        self.lab.pwa_reset_pass()
        view=self.lab.pwa_toggle("battery")
        self.assertTrue(any(e["domain"]=="device_health" and "battery" in e["title"].lower() for e in self.lab.pwa_audit))
        self.assertFalse(any("battery" in e["title"].lower() for e in view["events"]))
        self.assertFalse(view["care"]["alert"])
        self.assertTrue(view["device_health"]["attention"])
        self.lab.pwa_audit.append({"id":"debug-1","at":self.lab.state["now"]+1,"title":"Battery runtime recalculation confidence update","domain":"device_health","tone":"green","icon":"•"})
        self.assertFalse(any("confidence" in e["title"].lower() for e in self.lab.pwa_view()["events"]))
        at=self.lab.state["now"]
        raw=CloudEvent(self.lab.foundation.home_id,"raw-battery-1","BATTERY_RUNTIME_RECALCULATION","Kitchen",at,at,at)
        self.lab.service.store.events[(raw.home_id,raw.event_id)]=raw
        self.assertIn("BATTERY_RUNTIME_RECALCULATION",{e["kind"] for e in self.lab.snapshot()["timeline"]})
        self.assertFalse(any("Runtime Recalculation" in e["title"] for e in self.lab.pwa_view()["events"]))

    def test_pairwise_and_three_way_backend_projection(self):
        contract=json.loads((Path(__file__).resolve().parents[1]/"validation"/"phase1_ui_contract.json").read_text())
        for names in contract["pairwise"]+contract["high_risk_three_way"]:
            with self.subTest(names=names):
                self.lab.pwa_reset_pass()
                for name in names:
                    if name=="offline": self.lab.action({"action":"node","node":"kitchen","enabled":False})
                    else: self.lab.pwa_toggle(name)
                view=self.lab.pwa_view()
                self.assertEqual(view["morning"]["status"]=="MISSED","morning" in names)
                self.assertEqual(view["night"]["unusual"],"night" in names)
                self.assertEqual(view["door"]["left_open_alert"],"door" in names)
                self.assertEqual(view["iam_ok"]["ok"],"ok" not in names)
                self.assertEqual("kitchen" in view["device_health"]["offline_devices"],"offline" in names)
                self.assertNotIn("door",view["night"]["concern_text"].lower())
                self.assertFalse(any("battery" in e["title"].lower() for e in view["events"]))
                self.assertEqual([e["at"] for e in view["events"]],sorted((e["at"] for e in view["events"]),reverse=True))
                if set(names)<= {"battery","offline"}: self.assertFalse(view["care"]["alert"])

    def test_clear_fault_then_reboot_recovery_does_not_create_care_event(self):
        base=self.lab.pwa_reset_pass()
        titles=[e["title"] for e in base["events"]]
        self.lab.action({"action":"fault","target":"kitchen","fault":"LINK_LOSS"})
        bad=self.lab.pwa_view()
        self.assertIn("kitchen",bad["device_health"]["offline_devices"])
        self.assertFalse(bad["care"]["alert"])
        self.lab.action({"action":"clear_fault","target":"kitchen"})
        pending=self.lab.pwa_view()
        self.assertIn("kitchen",pending["device_health"]["offline_devices"])
        self.assertEqual(self.lab.device_faults["kitchen"],None)
        self.lab.action({"action":"reboot","target":"kitchen"})
        restored=self.lab.pwa_view()
        self.assertNotIn("kitchen",restored["device_health"]["offline_devices"])
        self.assertEqual([e["title"] for e in restored["events"]],titles)

    def test_family_read_is_allowed_but_owner_only_mutations_are_denied(self):
        member={"member_id":"family-1","display_name":"Family","relationship":"Daughter","role":"FAMILY","contact":None}
        self.assertEqual(self.call("POST","/pwa/foundation/members",member)[0],201)
        self.assertEqual(self.call("GET","/pwa/foundation/home",actor="family-1")[0],200)
        home=self.call("GET","/pwa/foundation/home")[1]
        update={"display_name":"Unauthorized","timezone":home["timezone"],"language":home["language"]}
        self.assertEqual(self.call("PATCH","/pwa/foundation/home",update,actor="family-1")[0],403)
        self.assertEqual(self.call("POST","/pwa/foundation/devices",{"device_id":"new-1","display_name":"New","kind":"NODE","capability":"MOTION","room":"Kitchen"},actor="family-1")[0],403)
        self.assertEqual(self.call("PATCH","/pwa/foundation/policy",self.lab.household_settings,actor="family-1")[0],403)
        self.assertEqual(self.call("GET","/pwa/foundation/home")[1]["display_name"],home["display_name"])

    def test_required_node_coverage_loss_and_restoration_are_domain_and_care_events(self):
        base=self.lab.pwa_reset_pass()
        self.assertEqual(base["coverage"],{"state":"COVERED","lost":False})
        self.lab.action({"action":"node","node":"kitchen","enabled":False})
        immediate=self.lab.pwa_view()
        self.assertEqual(immediate["coverage"]["state"],"COVERED")
        self.assertFalse(immediate["care"]["alert"])
        self.assertIn("kitchen",immediate["device_health"]["offline_devices"])
        self.assertFalse(any(e["title"]=="Monitoring coverage lost" for e in immediate["events"]))
        self.lab.action({"action":"advance","seconds":191})
        domain=self.lab.snapshot()
        self.assertEqual(domain["simulation"]["coverage"],"UNKNOWN")
        self.assertEqual([(e["kind"],e["details"].get("reason")) for e in domain["timeline"] if e["kind"]=="COVERAGE_CHANGED"],[("COVERAGE_CHANGED","coverage_lost")])
        self.assertEqual(domain["home"]["recent_events"][0]["kind"],"COVERAGE_CHANGED")
        self.assertEqual(domain["home"]["recent_events"][0]["tone"],"danger")
        lost=self.lab.pwa_view()
        self.assertTrue(lost["coverage"]["lost"])
        self.assertTrue(lost["care"]["alert"])
        self.assertEqual(lost["care"]["problem_kind"],"MONITORING_COVERAGE_LOST")
        self.assertTrue(lost["device_health"]["monitoring_coverage_lost"])
        self.assertEqual(lost["events"][0]["title"],"Monitoring coverage lost")
        self.assertEqual((lost["morning"]["status"],lost["iam_ok"]["status"],lost["door"]["open"],lost["night"]["unusual"],lost["device_health"]["low_percent"]),
                         (base["morning"]["status"],base["iam_ok"]["status"],base["door"]["open"],base["night"]["unusual"],base["device_health"]["low_percent"]))
        self.lab.action({"action":"node","node":"kitchen","enabled":True})
        self.lab.action({"action":"advance","seconds":60})
        restored=self.lab.pwa_view()
        self.assertEqual(restored["coverage"],{"state":"COVERED","lost":False})
        self.assertFalse(restored["care"]["alert"])
        self.assertNotIn("kitchen",restored["device_health"]["offline_devices"])
        self.assertEqual([e["title"] for e in restored["events"][:2]],["Monitoring coverage restored","Monitoring coverage lost"])
        self.assertEqual(self.lab.snapshot()["home"]["recent_events"][0]["tone"],"positive")

    def test_iam_ok_overdue_to_real_pressed_acknowledgement_preserves_other_domains(self):
        base=self.lab.pwa_reset_pass()
        overdue=self.lab.pwa_toggle("ok")
        self.assertEqual(overdue["iam_ok"]["ok"], False)
        self.assertEqual(overdue["iam_ok"]["status"], "OVERDUE")
        self.assertTrue(overdue["care"]["alert"])
        self.assertEqual(overdue["care"]["problem_kind"],"I_AM_OK_OVERDUE")
        self.assertEqual(overdue["events"][0]["title"],"I'm OK not confirmed")
        self.assertEqual((overdue["morning"]["status"],overdue["door"]["open"],overdue["night"]["unusual"],overdue["device_health"]["low_percent"]),
                         (base["morning"]["status"],base["door"]["open"],base["night"]["unusual"],base["device_health"]["low_percent"]))
        self.lab.action({"action":"advance","seconds":120})
        self.lab.action({"action":"event","node":"room1","kind":"OK_PRESSED"})
        acknowledged=self.lab.pwa_view()
        self.assertEqual(acknowledged["iam_ok"]["ok"], True)
        self.assertEqual(acknowledged["iam_ok"]["status"], "ACKNOWLEDGED")
        self.assertFalse(acknowledged["care"]["alert"])
        self.assertEqual([e["title"] for e in acknowledged["events"][:2]],["I'm OK received","I'm OK not confirmed"])
        self.assertGreater(acknowledged["events"][0]["at"],acknowledged["events"][1]["at"])
        self.assertIn("OK_PRESSED",{e["kind"] for e in self.lab.snapshot()["timeline"]})
        self.assertEqual((acknowledged["morning"]["status"],acknowledged["door"]["open"],acknowledged["night"]["unusual"],acknowledged["device_health"]["low_percent"]),
                         (base["morning"]["status"],base["door"]["open"],base["night"]["unusual"],base["device_health"]["low_percent"]))

    def test_generic_coverage_diagnostic_is_backend_only(self):
        self.lab.pwa_reset_pass()
        at=self.lab.state["now"]
        raw=CloudEvent(self.lab.foundation.home_id,"coverage-diagnostic-1","COVERAGE_CHANGED","home",at,at,at,payload={"reason":"lease_threshold_evaluation"})
        self.lab.service.store.events[(raw.home_id,raw.event_id)]=raw
        self.assertIn("COVERAGE_CHANGED",{e["kind"] for e in self.lab.snapshot()["timeline"]})
        self.assertFalse(any(e["kind"]=="COVERAGE_CHANGED" for e in self.lab.snapshot()["home"]["recent_events"]))
        view=self.lab.pwa_view()
        self.assertFalse(view["care"]["alert"])
        self.assertFalse(any("Monitoring coverage changed" in e["title"] for e in view["events"]))

    def test_iam_ok_offline_press_waits_for_backend_acceptance(self):
        self.lab.pwa_reset_pass()
        self.lab.pwa_toggle("ok")
        self.lab.action({"action":"wan","enabled":False})
        self.lab.action({"action":"advance","seconds":120})
        self.lab.action({"action":"event","node":"room1","kind":"OK_PRESSED"})
        offline=self.lab.pwa_view()
        self.assertEqual(offline["iam_ok"]["status"],"OVERDUE")
        self.assertTrue(offline["care"]["alert"])
        self.assertFalse(any(e["kind"]=="OK_PRESSED" for e in self.lab.snapshot()["timeline"]))
        self.lab.action({"action":"wan","enabled":True})
        delivered=self.lab.pwa_view()
        self.assertEqual(delivered["iam_ok"]["status"],"ACKNOWLEDGED")
        self.assertFalse(delivered["care"]["alert"])
        self.assertEqual(delivered["events"][0]["title"],"I'm OK received")
        self.assertIn("OK_PRESSED",{e["kind"] for e in self.lab.snapshot()["timeline"]})


if __name__ == "__main__": unittest.main()
