"""Composition tests for the file-backed authenticated Hub commit API."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.durable_api import open_durable_event_api
from ghar_sajag.model import Resident
from ghar_sajag.service import GharSajagService


class DurableApiCompositionTest(unittest.TestCase):
    def test_GS130_DURABLE_001_backlog_delivery_restart_projection_and_privacy(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'backend.sqlite'
            def fresh_service():
                service=GharSajagService()
                service.homes.create('home-1','Fixture','Asia/Kolkata','en-IN','owner-1',
                                     [Resident('resident-1','Resident',True,10)],10)
                return service
            def authorized(context,home,key):
                return (context.get('gs.verified_hub')=='hub-1' and home=='home-1' and
                        key['physical_device_id']=='device-1' and key['logical_node_id']=='room-1')
            service=fresh_service();clock=[120]
            api=open_durable_event_api(service,path,authorized,now=lambda:clock[0])
            try:
                with api.db:
                    api.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Fixture','UTC',10,10)")
                    api.db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES('owner-1','Owner',10)")
                    api.db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-1','owner-1','PRIMARY')")
                context={'gs.verified_hub':'hub-1'}
                key={'physical_device_id':'device-1','logical_node_id':'room-1',
                     'origin_session_id':4,'event_sequence':2}
                motion={'event_key':key,'event_type':'MOTION','occurred_at':110,
                        'hub_received_at':115,'location':'kitchen','payload':{}}
                self.assertTrue(api.api.dispatch('POST','/v1/homes/home-1/events','',motion,request_context=context)[0].startswith('201'))
                backlog={**motion,'event_key':{**key,'event_sequence':1},'event_type':'CALL_FAMILY',
                         'occurred_at':90,'hub_received_at':95,'location':'room',
                         'payload':{'reason':'offline_backlog','credential':'private-token','resident_name':'Private name'}}
                clock[0]=200
                receipt=api.api.dispatch('POST','/v1/homes/home-1/events','',backlog,request_context=context)[1]
                self.assertEqual((receipt['status'],receipt['event_key']),('COMMITTED',backlog['event_key']))
                committer=api.api.durable_events
                outbox=committer.due_outbox(200)
                self.assertEqual(len(outbox),1)
                self.assertTrue(committer.mark_delivered(outbox[0][0],'provider-fixture-accepted'))
                api.close()

                # Recreate the process composition, including its query service.
                # Household actor setup remains a fixture, not production OIDC.
                service=fresh_service();clock[0]=500
                api=open_durable_event_api(service,path,authorized,now=lambda:clock[0])
                status,retry=api.api.dispatch('POST','/v1/homes/home-1/events','',backlog,request_context=context)
                self.assertTrue(status.startswith('200'))
                self.assertEqual((retry['duplicate'],retry['event_key']),(True,backlog['event_key']))
                self.assertEqual([api.db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                                  for t in ('events','durable_event_commits','alerts','notification_jobs','durable_notification_outbox')],
                                 [2,2,1,1,1])
                self.assertEqual(len(api.api.durable_events.due_outbox(500)),0)
                delivery=api.db.execute('SELECT state,provider_reference FROM durable_notification_outbox').fetchone()
                self.assertEqual(tuple(delivery),('DELIVERED','provider-fixture-accepted'))
                snapshot=service.queries.snapshot('home-1','owner-1',500)
                self.assertEqual(snapshot['latest_activity']['occurred_at'],110)
                rows=snapshot['recent_events']
                self.assertEqual([e['occurred_at'] for e in rows],[110,90])
                self.assertEqual((rows[1]['kind'],rows[1]['received_at'],rows[1]['delayed']),('CALL_FAMILY',200,True))
                original=api.db.execute('SELECT canonical_event_id FROM events WHERE sequence_number=1').fetchone()[0]
                self.assertEqual(rows[1]['event_id'],original)
                self.assertEqual(rows[1]['details'],{'reason':'offline_backlog'})
                with self.assertRaises(PermissionError):
                    service.queries.snapshot('home-1','outsider',500)
                with self.assertRaises(PermissionError):
                    api.api.dispatch('POST','/v1/homes/another-home/events','',backlog,request_context=context)
            finally:api.close()

    def test_requires_file_store_and_trusted_authorizer(self):
        with tempfile.TemporaryDirectory() as directory:
            service = GharSajagService()
            with self.assertRaisesRegex(ValueError, "trusted_hub_authorizer_required"):
                open_durable_event_api(service, Path(directory) / "missing-auth.sqlite", None)
            with self.assertRaisesRegex(ValueError, "requires_file_database"):
                open_durable_event_api(service, ":memory:", lambda *_: True)

    def test_committed_event_survives_reopen_and_uses_existing_query_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backend.sqlite"
            service = GharSajagService()
            service.homes.create(
                "home-1", "Fixture", "Asia/Kolkata", "en-IN", "owner-1",
                [Resident("resident-1", "Resident", True, 100)], 100,
            )
            api = open_durable_event_api(
                service, path,
                lambda context, home, key: (
                    context.get("gs.verified_hub") == "hub-1" and home == "home-1" and
                    key == {"physical_device_id": "device-1", "logical_node_id": "room-1",
                            "origin_session_id": 4, "event_sequence": 9}
                ),
                now=lambda: 120,
            )
            with sqlite3.connect(path) as db:
                db.execute(
                    "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Fixture','UTC',100,100)"
                )
            body = {
                "event_key": {"physical_device_id": "device-1", "logical_node_id": "room-1",
                              "origin_session_id": 4, "event_sequence": 9},
                "event_type": "MOTION", "occurred_at": 110, "hub_received_at": 115,
                "location": "bathroom", "uncertainty_s": 1, "payload": {},
            }
            context = {"gs.verified_hub": "hub-1"}
            status, receipt = api.api.dispatch(
                "POST", "/v1/homes/home-1/events", "", body,
                request_context=context,
            )
            self.assertTrue(status.startswith("201"))
            self.assertEqual(receipt["status"], "COMMITTED")
            verification = sqlite3.connect(path)
            self.assertEqual(verification.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0], 1)
            verification.close()
            event_id = api.db.execute("SELECT canonical_event_id FROM events").fetchone()[0]
            api.close()

            api = open_durable_event_api(service, path,
                lambda context, home, key: context.get("gs.verified_hub") == "hub-1" and home == "home-1",
                now=lambda: 121,
            )
            retry_status, retry = api.api.dispatch(
                "POST", "/v1/homes/home-1/events", "", body,
                request_context=context,
            )
            self.assertTrue(retry_status.startswith("200"))
            self.assertTrue(retry["duplicate"])
            snapshot = service.queries.snapshot("home-1", "owner-1", 121)
            self.assertEqual(snapshot["latest_activity"]["event_id"], event_id)
            self.assertEqual(snapshot["latest_activity"]["occurred_at"], 110)
            self.assertEqual(snapshot["latest_activity"]["location"], "bathroom")
            api.close()


if __name__ == "__main__":
    unittest.main()
