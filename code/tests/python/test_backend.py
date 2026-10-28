# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module T01 Simulation/CI
# @requirements E08, E10, V01, AI01, AI03, NFR-08
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The Makefile builds host C++17 and runs Python/JavaScript tests plus simulator fixtures. Tests prove
# their asserted paths, not every SRD criterion. Keep a clean command transcript and attach additional
# scenario tests as requirements are integrated.

from __future__ import annotations

import unittest
import copy
import json
import sqlite3
import tempfile
from io import BytesIO
from pathlib import Path

from ghar_sajag import GharSajagService
from ghar_sajag.identity import AuthorizationError
from ghar_sajag.ingest import EventValidationError
from ghar_sajag.incidents import IncidentConflict
from ghar_sajag.model import CloudEvent, Device, HomeMode, IncidentState, Resident
from ghar_sajag.http_api import JsonApi
from ghar_sajag.configuration_repository import (
    ConfigurationConflict, ConfigurationDenied, PostgresConfigurationRepository,
)
from ghar_sajag.cloud_client_identity import TimeReadiness, VerifiedHubContext
from ghar_sajag.diagnostic_authorization import ActorSession
from ghar_sajag.human_authentication import (
    CurrentSession, HumanAuthenticationBoundary, IssuerPolicy, VerifiedAssertion,
)
from ghar_sajag.database import initialize_sqlite


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

    def test_motion_summary_is_stored_once_without_second_activity_trigger(self) -> None:
        first = self.cloud_event("node-1:1:1", "MOTION", received=100)
        summary = self.cloud_event("node-1:1:2", "MOTION_SUMMARY", received=145,
                                   payload={"additional_count": 12,
                                            "first_ms": 101000, "last_ms": 140000})
        self.service.accept_hub_event(first)
        accepted, duplicate = self.service.accept_hub_event(summary)
        self.assertFalse(duplicate)
        self.assertEqual(accepted.payload["additional_count"], 12)
        self.assertTrue(self.service.accept_hub_event(summary)[1])
        self.assertEqual(len(self.service.store.events), 2)
        self.assertEqual(len(self.service.store.incidents), 0)
        snapshot = self.service.queries.snapshot("home-1", "care-1", 145)
        self.assertEqual(snapshot["latest_activity"]["kind"], "MOTION")
        with self.assertRaises(EventValidationError):
            self.service.accept_hub_event(self.cloud_event(
                "node-1:1:3", "MOTION_SUMMARY", received=146,
                payload={"additional_count": 0, "first_ms": 140000, "last_ms": 130000}))

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

    def test_GS130_claim_expiry_boundary_allows_reconnection_retry(self) -> None:
        self.service.accept_hub_event(self.cloud_event("hub-1:1:11", "CALL_FAMILY"))
        incident = next(iter(self.service.store.incidents.values()))
        self.service.incidents.claim("home-1", incident.incident_id, "care-1", 110, lease_seconds=5)
        with self.assertRaises(IncidentConflict):
            self.service.incidents.claim("home-1", incident.incident_id, "care-2", 114)
        reclaimed = self.service.incidents.claim("home-1", incident.incident_id, "care-2", 115)
        self.assertEqual(reclaimed.owner_id, "care-2")
        self.assertEqual(reclaimed.owner_lease_until, 415)
        self.assertEqual(len(self.service.store.incidents), 1)

    def test_B06_config_version_and_device_binding(self) -> None:
        device = Device("hub-1", "home-1", "HUB", "esp32-devkit-v1", "common", "hub", 1, "0.1.0")
        self.service.fleet.register_device(device, "owner-1", 50)
        base = {
            "schema": 1, "home_id": "home-1", "timezone": "Asia/Kolkata",
            "morning": {"enabled": True, "start_minute": 420, "end_minute": 600, "grace_minutes": 30},
            "activity_rules": {
                "quiet_hours_enabled": True, "quiet_start_minute": 60, "quiet_end_minute": 300,
                "door_open_timeout_seconds": 300, "daytime_inactivity_enabled": True,
                "daytime_start_minute": 480, "daytime_end_minute": 1260,
                "daytime_inactivity_seconds": 10800,
            },
        }
        first = self.service.fleet.publish_config("home-1", "owner-1", {**base, "mode": "HOME"}, 51)
        second = self.service.fleet.publish_config("home-1", "owner-1", {**base, "mode": "AWAY"}, 52)
        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(self.service.fleet.record_applied("home-1", 2, 53).applied_version, 2)

    def test_GS117_configurable_morning_steps_are_validated_and_versioned(self) -> None:
        base = {
            "schema": 1, "home_id": "home-1", "timezone": "Asia/Kolkata", "mode": "HOME",
            "morning": {"enabled": True, "start_minute": 360, "end_minute": 660,
                        "grace_minutes": 20},
            "activity_rules": {
                "quiet_start_minute": 60, "quiet_end_minute": 300,
                "door_open_timeout_seconds": 300, "daytime_start_minute": 480,
                "daytime_end_minute": 1260, "daytime_inactivity_seconds": 10800,
                "morning_steps": [
                    {"location": "bedroom", "enabled": True, "required": False},
                    {"location": "bathroom", "enabled": True, "required": True},
                    {"location": "kitchen", "enabled": True, "required": True},
                ],
                "morning_sequence_strict_order": True,
            },
        }
        desired = self.service.fleet.publish_config("home-1", "owner-1", base, 61)
        self.assertEqual(desired.version, 1)
        self.assertTrue(desired.body["activity_rules"]["morning_sequence_strict_order"])
        self.assertEqual(len(desired.body["activity_rules"]["morning_steps"]), 3)
        before = copy.deepcopy(desired.body)
        for invalid_steps in (
                [base["activity_rules"]["morning_steps"][0]] * 2,
                [{"location": "pooja", "enabled": True, "required": False}],
                [{"location": "bad room", "enabled": True, "required": True}],
                [{"location": "pooja", "enabled": 1, "required": True}],
                []):
            with self.subTest(steps=invalid_steps):
                invalid = copy.deepcopy(base)
                invalid["activity_rules"]["morning_steps"] = invalid_steps
                with self.assertRaises(ValueError):
                    self.service.fleet.publish_config("home-1", "owner-1", invalid, 62)
                self.assertEqual(self.service.store.configs["home-1"].body, before)
                self.assertEqual(self.service.store.configs["home-1"].version, 1)
        with self.assertRaises(ValueError):
            self.service.fleet.publish_config("home-1", "owner-1",
                {**base, "activity_rules": {**base["activity_rules"],
                    "morning_sequence_strict_order": "true"}}, 63)
        self.assertEqual(self.service.store.configs["home-1"].version, 1)

    def test_B07_B08_snapshot_separates_activity_from_reachability(self) -> None:
        self.service.accept_hub_event(self.cloud_event("node-1:1:3", "MOTION", received=100))
        stale = self.service.queries.snapshot("home-1", "care-1", 500)
        self.assertFalse(stale["hub_reachable"])
        self.assertEqual(stale["latest_activity"]["kind"], "MOTION")
        self.service.accept_hub_event(self.cloud_event("hub-1:1:4", "HUB_HEARTBEAT", received=501, location="hub"))
        fresh = self.service.queries.snapshot("home-1", "care-1", 502)
        self.assertTrue(fresh["hub_reachable"])
        self.assertGreaterEqual(self.service.operations.diagnostics("home-1")["audit_entries"], 1)

    def test_GS130_CONFIG_001_json_rejection_preserves_applied_policy(self) -> None:
        api=JsonApi(self.service,now=lambda:100)
        def request(body,actor='owner-1'):
            raw=body.encode() if isinstance(body,str) else json.dumps(body).encode()
            statuses=[]
            response=b''.join(api({'REQUEST_METHOD':'POST','PATH_INFO':'/v1/homes/home-1/config',
                'HTTP_X_ACTOR_ID':actor,'CONTENT_LENGTH':str(len(raw)),
                'wsgi.input':BytesIO(raw)},lambda status,headers:statuses.append(status)))
            return int(statuses[0][:3]),json.loads(response)
        config={'morning':{'enabled':True,'start_minute':420,'end_minute':600},
                'activity_rules':{'quiet_start_minute':1320,'quiet_end_minute':360,
                    'daytime_start_minute':480,'daytime_end_minute':1260,
                    'door_open_timeout_seconds':300,'daytime_inactivity_seconds':7200}}
        self.assertEqual(request(config)[0],202)
        self.service.fleet.record_applied('home-1',1,100)
        baseline=copy.deepcopy(api.dispatch('GET','/v1/homes/home-1/config','owner-1',{})[1])
        audits=len(self.service.store.audit)
        invalid=[None,[],{},'{']
        for field,values in {
            'quiet_start_minute':[True,-1,1440,'0',0.5],
            'daytime_end_minute':[None,1440],
            'door_open_timeout_seconds':[True,29,86401],
            'daytime_inactivity_seconds':[True,299,86401]
        }.items():
            for value in values:
                bad=copy.deepcopy(config);bad['activity_rules'][field]=value;invalid.append(bad)
        for bad in invalid:
            with self.subTest(body=bad):
                self.assertEqual(request(bad)[0],400)
                self.assertEqual(api.dispatch('GET','/v1/homes/home-1/config','owner-1',{})[1],baseline)
                self.assertEqual(len(self.service.store.audit),audits)
        self.assertEqual(request(config,'care-1')[0],403)
        self.assertEqual(len(self.service.store.audit),audits)
        for index,(door,inactivity) in enumerate(((30,300),(86400,86400)),start=2):
            accepted=copy.deepcopy(config)
            accepted['activity_rules'].update(door_open_timeout_seconds=door,daytime_inactivity_seconds=inactivity)
            status,version=request(accepted)
            self.assertEqual((status,version['version'],version['applied_version']),(202,index,None))
        self.assertEqual(self.service.fleet.record_applied('home-1',3,101).applied_version,3)

    def test_test_alert_never_creates_production_incident(self) -> None:
        self.service.accept_hub_event(self.cloud_event("hub-1:1:99", "CALL_FAMILY", is_test=True))
        self.assertEqual(len(self.service.store.incidents), 0)


    def test_daytime_inactivity_creates_one_checkin_incident_and_routes(self) -> None:
        event = self.cloud_event("rule:daytime-inactivity:monitor:100", "DAYTIME_INACTIVITY", received=500, payload={"duration_s": 10800})
        self.service.accept_hub_event(event)
        self.service.accept_hub_event(event)
        incidents = [i for i in self.service.store.incidents.values() if i.kind == "DAYTIME_INACTIVITY"]
        self.assertEqual(len(incidents), 1)
        self.assertEqual(len(self.service.store.notification_jobs), 2)

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


class ConfigurationRepositoryTest(unittest.TestCase):
    """Migration-backed repository contract tests; no production auth route is installed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = sqlite3.connect(Path(self.temp.name) / "config.db", isolation_level=None)
        self.db.row_factory = sqlite3.Row
        initialize_sqlite(self.db)
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
            "VALUES('home-1','Home','Asia/Kolkata',1,1)")
        self.fingerprint = "a" * 64
        self.db.execute(
            """INSERT INTO hub_ownership_registry
               (hub_device_id,identity_key_fingerprint,state,home_id,installation_epoch,created_at,updated_at)
               VALUES('hub-1',?,'ACTIVE','home-1',7,1,1)""", (self.fingerprint,))
        self.actor = ActorSession("owner-1", "session-1", "issuer-ref", 1000)
        self.hub = VerifiedHubContext(
            "hub-1", "home-1", 7, "b" * 64, self.fingerprint, True, TimeReadiness.TRUSTED)
        self.policy = {
            "morning": {"enabled": True, "start_minute": 420,
                        "end_minute": 600, "grace_minutes": 30},
            "activity_rules": {
                "quiet_hours_enabled": True, "quiet_start_minute": 60,
                "quiet_end_minute": 300, "door_open_timeout_seconds": 300,
                "daytime_inactivity_enabled": True, "daytime_start_minute": 480,
                "daytime_end_minute": 1260, "daytime_inactivity_seconds": 10800,
                "morning_steps": [
                    {"location": "bedroom", "enabled": True, "required": False},
                    {"location": "bathroom", "enabled": True, "required": True},
                ],
            },
        }
        self.repo = PostgresConfigurationRepository(
            self.db, authorize_caregiver_settings=lambda actor, home, at: True,
            authorize_hub_configuration=lambda context, home, at: True,
        )

    def tearDown(self):
        self.db.close()

    def _authorized_config_api(self):
        class Verifier:
            def verify(inner, credential):
                if credential != "fixture-credential":
                    return None
                return VerifiedAssertion("https://issuer.test", "subject-1",
                                         ("ghar-sajag-api",), "session-1",
                                         "access", 90, 90, 150)

        class Directory:
            def current(inner, issuer, subject, session_id):
                if (issuer, subject, session_id) != (
                        "https://issuer.test", "subject-1", "session-1"):
                    return None
                return CurrentSession(issuer, subject, session_id,
                                     "owner-1", True, True)

        boundary = HumanAuthenticationBoundary(
            IssuerPolicy("https://issuer.test", "ghar-sajag-api", "access"),
            Verifier(), Directory(), lambda: 100)
        repository = PostgresConfigurationRepository(
            self.db,
            authorize_caregiver_settings=lambda actor, home, at:
                actor.actor_id == "owner-1" and home == "home-1" and at < actor.expires_at,
            authorize_hub_configuration=lambda context, home, at:
                context.permanent_hub_id == "hub-1" and home == "home-1")
        from ghar_sajag.http_api import JsonApi
        api = JsonApi(
            now=lambda: 100, configuration_repository=repository,
            human_authentication=boundary,
            caregiver_credential_from_request=lambda env: env.get("HTTP_AUTHORIZATION"),
            verified_hub_context_from_request=lambda env: env.get("gs.test_verified_hub"))
        return api

    def _request_config_api(self, api, method, path, body=None, **env):
        raw = b"" if body is None else json.dumps(body).encode()
        status = []
        if "gs_test_verified_hub" in env:
            env["gs.test_verified_hub"] = env.pop("gs_test_verified_hub")
        response = b"".join(api({"REQUEST_METHOD": method, "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(raw)), "wsgi.input": BytesIO(raw), **env},
            lambda value, _headers: status.append(value)))
        return int(status[0][:3]), json.loads(response)

    def test_authenticated_api_desired_fetch_and_applied_ack_share_repository(self):
        api = self._authorized_config_api()
        path = "/v1/homes/home-1/config"
        status, denied = self._request_config_api(
            api, "POST", path, {"expected_version": 0, "config": self.policy},
            HTTP_X_ACTOR_ID="owner-1")
        self.assertEqual((status, denied["error"]), (401, "human_not_authenticated"))

        status, desired = self._request_config_api(
            api, "POST", path, {"expected_version": 0, "config": self.policy},
            HTTP_AUTHORIZATION="fixture-credential", HTTP_X_ACTOR_ID="attacker")
        self.assertEqual((status, desired["desired_version"], desired["applied_version"]),
                         (202, 1, None))

        hub_path = "/v1/homes/home-1/config/desired"
        status, fetched = self._request_config_api(
            api, "GET", hub_path, gs_test_verified_hub=self.hub)
        self.assertEqual((status, fetched["version"], fetched["config"]),
                         (200, 1, self.policy))
        status, state = self._request_config_api(
            api, "POST", "/v1/homes/home-1/config/applied", {"version": 1},
            gs_test_verified_hub=self.hub)
        self.assertEqual((status, state["desired_version"], state["applied_version"]),
                         (200, 1, 1))
        status, caregiver_state = self._request_config_api(
            api, "GET", path, HTTP_AUTHORIZATION="fixture-credential")
        self.assertEqual((status, caregiver_state["desired_status"],
                          caregiver_state["applied_config"]),
                         (200, "APPLIED", self.policy))

    def test_repository_api_missing_adapters_and_unverified_hub_fail_closed(self):
        from ghar_sajag.http_api import JsonApi
        api = JsonApi(now=lambda: 100, configuration_repository=self.repo)
        status, body = self._request_config_api(
            api, "POST", "/v1/homes/home-1/config",
            {"expected_version": 0, "config": self.policy},
            HTTP_X_ACTOR_ID="owner-1")
        self.assertEqual((status, body["error"]),
                         (503, "caregiver_configuration_authentication_unavailable"))
        secured = self._authorized_config_api()
        status, body = self._request_config_api(
            secured, "GET", "/v1/homes/home-1/config/desired")
        self.assertEqual((status, body["error"]), (403, "verified_hub_context_required"))

    def test_test_only_caregiver_product_view_routes_routine_config_to_shared_repository(self):
        from ghar_sajag.caregiver_product import CaregiverProductView
        from ghar_sajag.configuration_repository import HouseholdConfigurationSnapshot
        policy = self.policy

        class Identity:
            def require(self, home, actor, _action, _now):
                if (home, actor) != ("home-1", "owner-1"):
                    raise PermissionError("not_authorized")

        class Service:
            identity = Identity()

        class Repository:
            def get_for_caregiver(self, *, actor, home_id, at):
                self.read = (actor, home_id, at)
                return HouseholdConfigurationSnapshot(home_id, 4, "DESIRED",
                    policy, 3, policy, 1)

            def publish_desired(self, *, actor, home_id, config, expected_version, at):
                self.write = (actor, home_id, config, expected_version, at)
                return HouseholdConfigurationSnapshot(home_id, 5, "DESIRED",
                    config, 3, policy, 1)

        repository = Repository()
        view = CaregiverProductView(Service(), source="TEST_ONLY",
                                    configuration_repository=repository)
        session = {"account_id": "owner-1", "session_id": "session-1",
                   "expires_at": 200, "role": "ADMIN", "test_only": True}
        snapshot = view.dispatch(session, "home-1", "routine-config", "GET", {}, 100)
        self.assertEqual((snapshot["home_id"], snapshot["desired_version"],
                          snapshot["applied_version"]), ("home-1", 4, 3))
        self.assertEqual(repository.read[0].issuer_reference, "GS179_TEST_ONLY_LITE")
        status, updated = view.dispatch(session, "home-1", "routine-config", "POST",
            {"expected_version": 4, "config": policy}, 101)
        self.assertEqual((status, updated["desired_version"]), ("202 Accepted", 5))
        self.assertEqual(repository.write[3:], (4, 101))

    def test_desired_and_applied_are_distinct_and_ack_is_idempotent(self):
        desired = self.repo.publish_desired(
            actor=self.actor, home_id="home-1",
            config={**self.policy, "schema": 1, "home_id": "home-1", "version": 0},
            expected_version=0, at=10)
        self.assertEqual((desired.desired_version, desired.desired_status), (1, "DESIRED"))
        self.assertIsNone(desired.applied_version)
        state = self.repo.get_for_hub(context=self.hub, home_id="home-1", at=11)
        self.assertEqual(state.desired_config, self.policy)
        self.assertIsNone(state.applied_config)

        applied = self.repo.record_applied(context=self.hub, home_id="home-1", version=1, at=12)
        self.assertEqual((applied.desired_version, applied.applied_version), (1, 1))
        self.assertEqual(applied.desired_config, applied.applied_config)
        duplicate = self.repo.record_applied(context=self.hub, home_id="home-1", version=1, at=13)
        self.assertEqual(duplicate.applied_version, 1)

    def test_bedroom_only_required_policy_round_trips_as_desired_then_applied(self):
        policy = copy.deepcopy(self.policy)
        policy["activity_rules"]["morning_steps"] = [
            {"location": "bedroom", "enabled": True, "required": True},
        ]
        desired = self.repo.publish_desired(
            actor=self.actor, home_id="home-1", config=policy,
            expected_version=0, at=20)
        self.assertEqual(desired.desired_config["activity_rules"]["morning_steps"],
                         [{"location": "bedroom", "enabled": True, "required": True}])
        self.assertEqual(desired.desired_status, "DESIRED")
        self.assertIsNone(desired.applied_version)

        before_apply = self.repo.get_for_hub(context=self.hub, home_id="home-1", at=21)
        self.assertEqual(before_apply.desired_config, policy)
        self.assertIsNone(before_apply.applied_config)

        applied = self.repo.record_applied(context=self.hub, home_id="home-1",
                                           version=desired.desired_version, at=22)
        self.assertEqual(applied.applied_config, policy)
        self.assertEqual(applied.applied_version, desired.desired_version)

    def test_new_desired_version_preserves_last_applied_and_rejects_stale_ack(self):
        first = self.repo.publish_desired(
            actor=self.actor, home_id="home-1", config=self.policy, expected_version=0, at=10)
        self.repo.record_applied(context=self.hub, home_id="home-1", version=first.desired_version, at=11)
        revised_policy = copy.deepcopy(self.policy)
        revised_policy["activity_rules"]["morning_sequence_strict_order"] = True
        second = self.repo.publish_desired(
            actor=self.actor, home_id="home-1", config=revised_policy, expected_version=1, at=12)
        self.assertEqual(second.desired_version, 2)
        self.assertEqual(second.desired_status, "DESIRED")
        self.assertEqual(second.applied_version, 1)
        self.assertEqual(second.applied_config, self.policy)
        with self.assertRaisesRegex(ConfigurationConflict, "stale_or_unknown"):
            self.repo.record_applied(context=self.hub, home_id="home-1", version=1, at=13)
        with self.assertRaisesRegex(ConfigurationConflict, "stale_desired"):
            self.repo.publish_desired(
                actor=self.actor, home_id="home-1", config=self.policy, expected_version=1, at=14)
        self.assertEqual(self.repo.get_for_hub(context=self.hub, home_id="home-1", at=15).desired_version, 2)

    def test_missing_or_denied_authority_and_invalid_policy_fail_without_writes(self):
        no_auth = PostgresConfigurationRepository(self.db)
        with self.assertRaisesRegex(ConfigurationDenied, "authority_unavailable"):
            no_auth.publish_desired(actor=self.actor, home_id="home-1", config=self.policy,
                                    expected_version=0, at=10)
        with self.assertRaisesRegex(ConfigurationDenied, "authority_unavailable"):
            no_auth.get_for_hub(context=self.hub, home_id="home-1", at=10)
        denied = PostgresConfigurationRepository(
            self.db, authorize_caregiver_settings=lambda actor, home, at: False,
            authorize_hub_configuration=lambda context, home, at: False,
        )
        with self.assertRaisesRegex(ConfigurationDenied, "membership_required"):
            denied.publish_desired(actor=self.actor, home_id="home-1", config=self.policy,
                                   expected_version=0, at=10)
        with self.assertRaisesRegex(ConfigurationDenied, "authority_required"):
            denied.get_for_hub(context=self.hub, home_id="home-1", at=10)
        invalid = copy.deepcopy(self.policy)
        invalid["activity_rules"]["morning_steps"][1]["required"] = False
        with self.assertRaisesRegex(ValueError, "required_step"):
            self.repo.publish_desired(actor=self.actor, home_id="home-1", config=invalid,
                                      expected_version=0, at=10)
        mismatched_home = {**self.policy, "home_id": "other-home"}
        with self.assertRaisesRegex(ValueError, "configuration_home_mismatch"):
            self.repo.publish_desired(actor=self.actor, home_id="home-1", config=mismatched_home,
                                      expected_version=0, at=10)
        mismatched_version = {**self.policy, "version": 1}
        with self.assertRaisesRegex(ConfigurationConflict, "request_configuration_version"):
            self.repo.publish_desired(actor=self.actor, home_id="home-1", config=mismatched_version,
                                      expected_version=0, at=10)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM configurations").fetchone()[0], 0)

    def test_hub_home_epoch_and_fingerprint_are_rechecked_against_current_registry(self):
        wrong_home = VerifiedHubContext(
            "hub-1", "other-home", 7, "b" * 64, self.fingerprint, True, TimeReadiness.TRUSTED)
        with self.assertRaisesRegex(ConfigurationDenied, "verified_current_hub_context"):
            self.repo.get_for_hub(context=wrong_home, home_id="home-1", at=10)
        wrong_certificate = VerifiedHubContext(
            "hub-1", "home-1", 7, "not-a-certificate-fingerprint", self.fingerprint,
            True, TimeReadiness.TRUSTED)
        with self.assertRaisesRegex(ConfigurationDenied, "verified_current_hub_context"):
            self.repo.get_for_hub(context=wrong_certificate, home_id="home-1", at=10)
        stale_epoch = VerifiedHubContext(
            "hub-1", "home-1", 6, "b" * 64, self.fingerprint, True, TimeReadiness.TRUSTED)
        with self.assertRaisesRegex(ConfigurationDenied, "ownership_changed"):
            self.repo.get_for_hub(context=stale_epoch, home_id="home-1", at=10)
        self.db.execute("UPDATE hub_ownership_registry SET state='REVOKED' WHERE hub_device_id='hub-1'")
        with self.assertRaisesRegex(ConfigurationDenied, "ownership_changed"):
            self.repo.get_for_hub(context=self.hub, home_id="home-1", at=10)

    def test_unknown_schema_or_corrupt_persisted_policy_fails_closed(self):
        self.repo.publish_desired(actor=self.actor, home_id="home-1", config=self.policy,
                                  expected_version=0, at=10)
        self.db.execute("UPDATE configurations SET schema_version=2 WHERE home_id='home-1'")
        with self.assertRaisesRegex(ConfigurationConflict, "unsupported_household_configuration_schema"):
            self.repo.get_for_hub(context=self.hub, home_id="home-1", at=11)
        self.db.execute("UPDATE configurations SET schema_version=1,config_json='{}' WHERE home_id='home-1'")
        with self.assertRaisesRegex(ConfigurationConflict, "stored_household_configuration_invalid"):
            self.repo.get_for_hub(context=self.hub, home_id="home-1", at=12)


if __name__ == "__main__":
    unittest.main()
