from __future__ import annotations

import unittest

from ghar_sajag import GharSajagService
from ghar_sajag.identity import AuthorizationError
from ghar_sajag.incidents import IncidentConflict
from ghar_sajag.model import CloudEvent, Device, HomeMode, IncidentState, Resident


class BackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GharSajagService()
        resident = Resident("resident-1", "Resident", True, 10)
        self.service.homes.create("home-1", "Parents' home", "Asia/Kolkata", "hi-IN", "owner-1", [resident], 10)
        self.service.homes.set_caregivers("home-1", "owner-1", "care-1", "care-2", 11)

    def cloud_event(self, event_id: str, kind: str, received: int = 100, **kwargs) -> CloudEvent:
        return CloudEvent(
            "home-1", event_id, kind, kwargs.get("location", "kitchen"),
            kwargs.get("occurred_at", received - 1), received - 1, received,
            kwargs.get("uncertainty_s", 0), kwargs.get("is_test", False), kwargs.get("payload", {}),
        )

    def test_B01_F01_membership_is_tenant_scoped(self) -> None:
        self.assertEqual(self.service.identity.require("home-1", "care-1", "read", 20).actor_id, "care-1")
        with self.assertRaises(AuthorizationError):
            self.service.identity.require("home-1", "unknown", "read", 20)

    def test_B02_consent_withdrawal_enters_privacy(self) -> None:
        home = self.service.homes.withdraw_resident_consent("home-1", "resident-1", "owner-1", 30)
        self.assertEqual(home.mode, HomeMode.PRIVACY)
        self.assertFalse(home.residents["resident-1"].consent_active)

    def test_B03_ingest_is_idempotent(self) -> None:
        event = self.cloud_event("node-1:1:1", "MOTION")
        _, duplicate1 = self.service.accept_hub_event(event)
        _, duplicate2 = self.service.accept_hub_event(event)
        self.assertFalse(duplicate1)
        self.assertTrue(duplicate2)
        self.assertEqual(len(self.service.store.events), 1)

    def test_B04_B05_call_creates_one_incident_and_two_bounded_routes(self) -> None:
        event = self.cloud_event("hub-1:1:9", "CALL_FAMILY", received=100)
        self.service.accept_hub_event(event)
        self.service.accept_hub_event(event)
        self.assertEqual(len(self.service.store.incidents), 1)
        self.assertEqual(len(self.service.store.notification_jobs), 2)
        self.assertEqual([job.stage for job in self.service.notifications.due(100)], [1])
        self.assertEqual([job.stage for job in self.service.notifications.due(400)], [1, 2])

    def test_B04_claim_lease_prevents_double_ownership(self) -> None:
        self.service.accept_hub_event(self.cloud_event("hub-1:1:10", "CALL_FAMILY"))
        incident = next(iter(self.service.store.incidents.values()))
        self.service.incidents.claim("home-1", incident.incident_id, "care-1", 110)
        with self.assertRaises(IncidentConflict):
            self.service.incidents.claim("home-1", incident.incident_id, "care-2", 111)
        acknowledged = self.service.incidents.acknowledge("home-1", incident.incident_id, "care-1", 112)
        self.service.notifications.human_acknowledged(incident.incident_id)
        self.assertEqual(acknowledged.state, IncidentState.ACKNOWLEDGED)
        self.assertEqual(self.service.notifications.due(500), [])

    def test_B06_config_version_and_device_binding(self) -> None:
        device = Device("hub-1", "home-1", "HUB", "esp32-devkit-v1", "common", "hub", 1, "0.1.0")
        self.service.fleet.register_device(device, "owner-1", 50)
        first = self.service.fleet.publish_config("home-1", "owner-1", {"mode": "HOME"}, 51)
        second = self.service.fleet.publish_config("home-1", "owner-1", {"mode": "AWAY"}, 52)
        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(self.service.fleet.record_applied("home-1", 2, 53).applied_version, 2)

    def test_B07_B08_snapshot_separates_activity_from_reachability(self) -> None:
        self.service.accept_hub_event(self.cloud_event("node-1:1:3", "MOTION", received=100))
        stale = self.service.queries.snapshot("home-1", "care-1", 500)
        self.assertFalse(stale["hub_reachable"])
        self.assertEqual(stale["latest_activity"]["kind"], "MOTION")
        self.service.accept_hub_event(self.cloud_event("hub-1:1:4", "HUB_HEARTBEAT", received=501, location="hub"))
        fresh = self.service.queries.snapshot("home-1", "care-1", 502)
        self.assertTrue(fresh["hub_reachable"])
        self.assertGreaterEqual(self.service.operations.diagnostics("home-1")["audit_entries"], 1)

    def test_test_alert_never_creates_production_incident(self) -> None:
        self.service.accept_hub_event(self.cloud_event("hub-1:1:99", "CALL_FAMILY", is_test=True))
        self.assertEqual(len(self.service.store.incidents), 0)

    def test_B05_F09_quiet_door_notice_is_opt_in_and_idempotent(self) -> None:
        first = self.service.notifications.create_door_notice("home-1", "door:1", 200, True)
        second = self.service.notifications.create_door_notice("home-1", "door:1", 201, True)
        self.assertIsNotNone(first)
        self.assertEqual(first.notice_id, second.notice_id)
        self.assertIsNone(self.service.notifications.create_door_notice("home-1", "door:2", 202, False))

    def test_B05_F14_summary_is_opt_in_single_and_coverage_honest(self) -> None:
        self.assertIsNone(self.service.notifications.build_daily_summary("home-1", "2026-09-07", 1, 500, False, True, True))
        first = self.service.notifications.build_daily_summary("home-1", "2026-09-07", 1, 501, True, True, False)
        second = self.service.notifications.build_daily_summary("home-1", "2026-09-07", 1, 502, True, True, True)
        self.assertEqual(first.content["observation"], "observation_incomplete")
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
