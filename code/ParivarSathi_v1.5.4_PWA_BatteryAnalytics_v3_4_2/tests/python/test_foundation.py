import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from pathlib import Path

from ghar_sajag.foundation import FoundationError, FoundationService


class FoundationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "application.sqlite"
        self.svc = FoundationService(self.path, clock=lambda: 100)
        self.svc.seed({"battery_alert_percent": 20}, [{"id":"hub","name":"Hub","kind":"HUB","capability":"HUB","room":"Central hub"}])
        self.owner = "simulation-owner"

    def tearDown(self):
        self.svc.close()
        self.temp.cleanup()

    def test_home_validation_and_restart(self):
        self.assertEqual(self.svc.home(self.owner)["display_name"], "Synthetic demo home")
        with self.assertRaises(FoundationError):
            self.svc.update_home(self.owner, {"display_name":"", "timezone":"Asia/Kolkata", "language":"en-IN"})
        self.svc.update_home(self.owner, {"display_name":"My home", "timezone":"Asia/Kolkata", "language":"hi-IN"})
        self.svc.close()
        self.svc = FoundationService(self.path, clock=lambda: 101)
        self.svc.seed({"battery_alert_percent": 20}, [{"id":"hub","name":"Other","kind":"HUB","capability":"HUB","room":"Central hub"}])
        self.assertEqual(self.svc.home(self.owner)["display_name"], "My home")

    def test_family_crud_contact_and_last_owner(self):
        m={"member_id":"family-1","display_name":"Anita","relationship":"Daughter","role":"FAMILY","contact":"anita@example.org"}
        self.svc.add_member(self.owner,m)
        with self.assertRaisesRegex(FoundationError,"duplicate"):
            self.svc.add_member(self.owner,{**m,"member_id":"family-2"})
        self.svc.update_member(self.owner,"family-1",{**m,"display_name":"Anita Rao","role":"CAREGIVER"})
        with self.assertRaisesRegex(FoundationError,"last_owner"):
            self.svc.deactivate_member(self.owner,self.owner)
        self.svc.deactivate_member(self.owner,"family-1")
        self.assertEqual(self.svc._row("family_members","member_id","family-1")["display_name"],"Anita Rao")
        with self.assertRaisesRegex(FoundationError,"member_inactive"):
            self.svc.update_member(self.owner,"family-1",{**m,"display_name":"Should not save"})
        with self.assertRaises(PermissionError):
            self.svc.add_member("family-1",m)

    def test_device_registry_health_removal_and_history(self):
        d={"device_id":"bathroom-2","display_name":"Bathroom Node","kind":"NODE","capability":"MOTION","room":"Bathroom"}
        self.svc.register_device(self.owner,d)
        with self.assertRaisesRegex(FoundationError,"duplicate"):
            self.svc.register_device(self.owner,d)
        with self.assertRaisesRegex(FoundationError,"invalid_capability"):
            self.svc.register_device(self.owner,{**d,"device_id":"bad-2","capability":"DOOR_OPEN"})
        self.svc.update_device(self.owner,"bathroom-2",{"display_name":"Bath sensor","room":"Kitchen","enabled":True})
        self.svc.record_health("bathroom-2",True,"ACTIVE",3920,65,"NORMAL")
        self.assertEqual(self.svc.device(self.owner,"bathroom-2")["battery_percent"],65)
        with self.assertRaisesRegex(FoundationError,"inconsistent_health"):
            self.svc.record_health("bathroom-2",False,"ACTIVE",3920,65,"NORMAL")
        with self.assertRaisesRegex(FoundationError,"last_hub"):
            self.svc.unregister_device(self.owner,"hub")
        self.svc.unregister_device(self.owner,"bathroom-2")
        self.assertEqual(len(self.svc.devices(self.owner)),1)
        with self.assertRaisesRegex(FoundationError,"device_unregistered"):
            self.svc.record_health("bathroom-2",True,"ACTIVE",3920,65,"NORMAL")
        self.assertEqual(self.svc.db.execute("SELECT count(*) FROM device_health_history WHERE device_id='bathroom-2'").fetchone()[0],1)

    def test_policy_failure_preserves_previous_commit(self):
        def validate(x):
            if not 1 <= x["battery_alert_percent"] <= 50: raise FoundationError("invalid_battery_policy")
        with self.assertRaises(FoundationError):
            self.svc.save_policy(self.owner,{"battery_alert_percent":90},validate)
        self.assertEqual(self.svc.policy(self.owner)["settings"]["battery_alert_percent"],20)
        self.svc.save_policy(self.owner,{"battery_alert_percent":25},validate)
        self.assertEqual(self.svc.policy(self.owner)["version"],2)

    def test_storage_write_failure_does_not_report_a_save(self):
        previous=self.svc.home(self.owner)["display_name"]
        self.svc.db.execute("PRAGMA query_only = ON")
        with self.assertRaises(Exception):
            self.svc.update_home(self.owner,{"display_name":"Should not save","timezone":"Asia/Kolkata","language":"en-IN"})
        self.svc.db.execute("PRAGMA query_only = OFF")
        self.assertEqual(self.svc.home(self.owner)["display_name"],previous)

    def test_editable_boundaries_and_rejected_mutations(self):
        valid={"display_name":"H"*80,"timezone":"Asia/Kolkata","language":"en-IN"}
        self.svc.update_home(self.owner,valid)
        with self.assertRaisesRegex(FoundationError,"invalid_display_name"):
            self.svc.update_home(self.owner,{**valid,"display_name":"H"*81})
        with self.assertRaisesRegex(FoundationError,"invalid_timezone"):
            self.svc.update_home(self.owner,{**valid,"timezone":"Invalid/Timezone"})
        self.assertEqual(self.svc.home(self.owner)["display_name"],"H"*80)
        member={"member_id":"care-1","display_name":"Caregiver","relationship":"","role":"CAREGIVER","contact":None}
        self.svc.add_member(self.owner,member)
        with self.assertRaises(PermissionError):
            self.svc.add_member("care-1",{**member,"member_id":"care-2"})
        with self.assertRaisesRegex(FoundationError,"invalid_role"):
            self.svc.add_member(self.owner,{**member,"member_id":"care-2","role":"ADMIN"})
        with self.assertRaisesRegex(FoundationError,"invalid_contact"):
            self.svc.add_member(self.owner,{**member,"member_id":"care-2","contact":"not-an-email"})
        device={"device_id":"node-2","display_name":"Node","kind":"NODE","capability":"MOTION","room":"Kitchen"}
        with self.assertRaisesRegex(FoundationError,"invalid_device_id"):
            self.svc.register_device(self.owner,{**device,"device_id":"../bad"})
        with self.assertRaisesRegex(FoundationError,"invalid_room"):
            self.svc.register_device(self.owner,{**device,"room":"Unknown"})
        self.svc.register_device(self.owner,device)
        with self.assertRaisesRegex(FoundationError,"invalid_display_name"):
            self.svc.update_device(self.owner,"node-2",{"display_name":"","room":"Kitchen","enabled":True})
        self.assertEqual(self.svc.device(self.owner,"node-2")["display_name"],"Node")

    def test_concurrent_local_requests_share_one_transactional_registry(self):
        def register(number):
            return self.svc.register_device(self.owner,{"device_id":f"node-{number}","display_name":f"Node {number}","kind":"NODE","capability":"MOTION","room":"Kitchen"})
        with ThreadPoolExecutor(max_workers=4) as pool:
            records=list(pool.map(register,range(2,10)))
        self.assertEqual(len({r["device_id"] for r in records}),8)
        self.assertEqual(len(self.svc.devices(self.owner)),9)

    def test_failed_family_device_and_policy_writes_leave_state_unchanged(self):
        node={"device_id":"node-2","display_name":"Node","kind":"NODE","capability":"MOTION","room":"Kitchen"}
        self.svc.register_device(self.owner,node)
        prior_policy=self.svc.policy(self.owner)
        self.svc.db.execute("PRAGMA query_only = ON")
        try:
            with self.assertRaises(Exception):
                self.svc.add_member(self.owner,{"member_id":"care-2","display_name":"Caregiver","relationship":"","role":"CAREGIVER","contact":None})
            with self.assertRaises(Exception):
                self.svc.update_device(self.owner,"node-2",{"display_name":"Unsaved","room":"Bathroom","enabled":True})
            with self.assertRaises(Exception):
                self.svc.unregister_device(self.owner,"node-2")
            with self.assertRaises(Exception):
                self.svc.save_policy(self.owner,{"battery_alert_percent":25},lambda _: None)
        finally:
            self.svc.db.execute("PRAGMA query_only = OFF")
        self.assertEqual(self.svc.device(self.owner,"node-2")["display_name"],"Node")
        self.assertTrue(self.svc.device(self.owner,"node-2")["registered"])
        self.assertEqual(self.svc.policy(self.owner),prior_policy)
        self.assertEqual(len(self.svc.members(self.owner)),1)


if __name__ == "__main__": unittest.main()
