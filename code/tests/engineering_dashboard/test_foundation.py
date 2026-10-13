"""Actual inactive source tests. Authority adapters below are TEST ONLY.

No OIDC, production issuer/grantor, target exporter, HTTP route or browser is
qualified. Fixture expiry/budget values are test inputs, never product defaults.
"""
from dataclasses import replace
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from ghar_sajag.database import initialize_sqlite
from ghar_sajag.diagnostic_authorization import (
    ActorSession, HomeMembership, DiagnosticGrant, TrustedAccessSnapshot,
    DiagnosticAuthorizer, DiagnosticAction, DiagnosticDenied, EventAccess,
)
from ghar_sajag.diagnostics import DiagnosticReadService, DiagnosticLimits, TechnicalRecord, TechnicalPage
from ghar_sajag.durable_commit import DurableEventCommit
from ghar_sajag.http_api import JsonApi
from ghar_sajag.model import Role, Resident
from ghar_sajag.ownership_registry import (
    HubOwnershipRegistry, VerifiedHubIdentity, AuthorizedHomeOperation, VerifiedNodeEnrollment,
)
from ghar_sajag.service import GharSajagService


class FixtureAuthority:
    """Object capability is local test input; this is NOT an identity verifier."""
    def __init__(self):
        self.capability = object()
        self.state = TrustedAccessSnapshot(
            ActorSession("fixture-owner", "fixture-session", "fixture-issuer", 1000),
            HomeMembership("home-a", "fixture-owner", Role.OWNER, 1, True),
            DiagnosticGrant("home-a", "fixture-owner", 1, 1, 1, 500, False), 1)
        self.generation, self.binding_active = 1, True
        self.resolve_calls = 0

    def resolve(self, context, home_id):
        self.resolve_calls += 1
        return self.state if context is self.capability else None

    def event_access(self, context, home_id, canonical):
        if context is not self.capability or not self.binding_active:
            return None
        return EventAccess(home_id, canonical, self.state.ownership_epoch, self.generation)


class FixtureTechnicalSource:
    def __init__(self, records):
        self.records, self.revision, self.calls = records, "fixture-revision-1", []
        self.after_read = None

    def page(self, home, epoch, offset, limit):
        self.calls.append((home, epoch, offset, limit))
        records = tuple(self.records[offset:offset+limit])
        if self.after_read:
            self.after_read()
        return TechnicalPage(self.revision, records, offset+len(records)<len(self.records))


class FoundationFixture(unittest.TestCase):
    def setUp(self):
        self.authority = FixtureAuthority()
        self.guard = DiagnosticAuthorizer(self.authority)
        self.at = 100
        self.limits = DiagnosticLimits(2, 20000, 2, 80, 20)
        self.source = FixtureTechnicalSource([
            TechnicalRecord("home-a", 1, "node-1", "a"*64, 95,
                            {"connectivity": "HEALTHY", "rx_rssi_dbm": -70}),
            TechnicalRecord("home-a", 1, "node-2", "a"*64, 94, {}),
            TechnicalRecord("home-a", 1, "node-3", "a"*64, 93, {}),
        ])
        self.view = DiagnosticReadService(self.guard, clock=lambda:self.at,
                                         limits=self.limits, technical_source=self.source)

    def read(self, operation="health", query=None, context=None, home="home-a"):
        return self.view.read(self.authority.capability if context is None else context, home, operation, query)

    def grant(self, **changes):
        self.authority.state = replace(self.authority.state,
                                       grant=replace(self.authority.state.grant, **changes))


class AuthorizationFoundationTest(FoundationFixture):
    def test_A01_unknown_and_write_actions_deny_before_resolver(self):
        for action in ("read", "manage", "GRANT_DIAGNOSTICS", "DEVICE_CONTROL", "unknown", None, [], True):
            with self.subTest(action=action), self.assertRaises(DiagnosticDenied):
                self.guard.require(self.authority.capability, "home-a", action, 100)
        self.assertEqual(self.authority.resolve_calls, 0)

    def test_A02_existing_identity_unknown_permission_denies_all_roles(self):
        service = GharSajagService()
        for role in Role:
            service.identity.grant("home-a", "fixture-user", role, 1)
            for verb in ("READ_DIAGNOSTICS", "garbage", "READ", None, []):
                with self.assertRaises(PermissionError):
                    service.identity.require("home-a", "fixture-user", verb, 2)

    def test_A03_existing_read_manage_role_behavior_preserved(self):
        service = GharSajagService()
        for role in Role:
            service.identity.grant("home-a", "fixture-user", role, 1)
            self.assertEqual(service.identity.require("home-a", "fixture-user", "read", 2).role, role)
            if role is Role.OWNER:
                service.identity.require("home-a", "fixture-user", "manage", 2)
            else:
                with self.assertRaises(PermissionError):service.identity.require("home-a", "fixture-user", "manage", 2)

    def test_A04_roles_without_explicit_grant_denied(self):
        for role in Role:
            self.authority.state = replace(self.authority.state, grant=None,
                membership=replace(self.authority.state.membership, role=role))
            self.assertEqual(self.read().status, 403)
        self.assertEqual(self.source.calls, [])

    def test_A05_forged_headers_dict_principal_and_verified_flag_denied(self):
        for forged in ({"HTTP_X_ACTOR_ID":"fixture-owner", "verified":True},
                       {"gs.verified_actor":"fixture-owner"}, self.authority.state.actor, "fixture-owner", True):
            self.assertEqual(self.read(context=forged).status, 401)
        self.assertEqual(self.source.calls, [])

    def test_A06_missing_production_authority_default_denies(self):
        self.view = DiagnosticReadService(clock=lambda:100, limits=self.limits)
        self.assertEqual(self.read(context={"verified":True}).status, 401)

    def test_A07_trusted_adapter_cannot_return_request_dict(self):
        self.authority.resolve = lambda *_:{"verified":True, "grant":True}
        self.assertEqual(self.read().status, 403)
        self.guard.authority = object()
        self.assertEqual(self.read().status, 401)

    def test_A08_wrong_home_denies_before_source_query(self):
        self.assertEqual(self.read(home="home-b").status, 403)
        self.assertEqual(self.source.calls, [])

    def test_A09_grant_expiry_boundary_denies(self):
        self.at=499;self.assertEqual(self.read().status, 200)
        self.at=500;self.assertEqual(self.read().status, 403)

    def test_A10_revocation_and_regrant_version_invalidate_cursor(self):
        token=self.read(query={"limit":1}).body["next_cursor"]
        self.grant(revoked=True);self.assertEqual(self.read().status, 403)
        self.grant(revoked=False, version=2)
        self.assertEqual(self.read(query={"cursor":token}).status, 403)

    def test_A11_stale_owner_epoch_denies(self):
        self.authority.state=replace(self.authority.state, ownership_epoch=2)
        self.assertEqual(self.read().status, 403)

    def test_A12_membership_revoke_expiry_role_version_deny(self):
        original=self.authority.state
        for changes in ({"active":False},{"expires_at":100},{"role":Role.CAREGIVER,"version":2}):
            self.authority.state=replace(original, membership=replace(original.membership, **changes))
            self.assertEqual(self.read().status, 403)

    def test_A13_actor_session_expiry_or_absent_issuer_denies(self):
        original=self.authority.state
        for changes in ({"expires_at":100},{"issuer_reference":""}):
            self.authority.state=replace(original, actor=replace(original.actor, **changes))
            self.assertEqual(self.read().status, 401)

    def test_A14_grant_actor_home_action_and_bool_versions_rejected(self):
        original=self.authority.state
        for changes in ({"actor_id":"someone"},{"home_id":"home-b"},{"action":"read"},
                        {"version":True},{"ownership_epoch":True},{"expires_at":False}):
            self.authority.state=original;self.grant(**changes)
            self.assertEqual(self.read().status, 403)

    def test_A15_inflight_revocation_returns_no_source_data(self):
        self.source.after_read=lambda:self.grant(revoked=True)
        response=self.read(query={"limit":1})
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body, {"error":"diagnostic_not_authorized"})
        self.assertEqual(len(self.view._cursors),0)

    def test_A16_session_switch_invalidates_cursor(self):
        token=self.read(query={"limit":1}).body["next_cursor"]
        self.authority.state=replace(self.authority.state,
            actor=replace(self.authority.state.actor, session_id="fixture-new-session"))
        self.assertEqual(self.read(query={"cursor":token}).status,403)

    def test_A17_unauthorized_grant_and_control_routes_absent(self):
        api=JsonApi()
        for suffix in ("diagnostics/grants","diagnostics/restart","diagnostics/recommission"):
            status,body=api.dispatch("POST","/v1/homes/home-a/"+suffix,"fixture-owner",{"verified":True})
            self.assertEqual(status,"404 Not Found");self.assertEqual(body,{"error":"route_not_found"})
        self.assertEqual(self.read(operation="GRANT_DIAGNOSTICS").status,403)

    def test_A18_production_jsonapi_has_no_diagnostic_get(self):
        api=JsonApi();status=[]
        env={"REQUEST_METHOD":"GET","PATH_INFO":"/v1/homes/home-a/diagnostics/trace",
             "HTTP_X_ACTOR_ID":"fixture-owner","HTTP_VERIFIED":"true","wsgi.input":io.BytesIO()}
        payload=b"".join(api(env,lambda s,h:status.append(s)))
        self.assertEqual(status,["404 Not Found"])
        self.assertEqual(json.loads(payload),{"error":"route_not_found"})


class PrivacyFoundationTest(FoundationFixture):
    def test_P01_class_a_allowlist_excludes_raw_personal_and_secret_fields(self):
        self.source.records[0].fields.update({"payload":"SECRET-WIFI", "resident_name":"Private Person",
            "phone":"secret-phone", "raw_logs":"SECRET-LOG", "firmware_version":"SECRET-TOKEN"})
        response=self.read();serialized=json.dumps(response.body)
        self.assertEqual(response.status,200)
        for secret in ("SECRET","Private Person","secret-phone","raw_logs","resident_name"):
            self.assertNotIn(secret,serialized)
        self.assertEqual(response.body["devices"][0]["fields"]["firmware_version"],{"status":"UNKNOWN","value":None})

    def test_P02_stale_record_suppresses_health_values(self):
        self.at=120
        device=self.read().body["devices"][0]
        self.assertEqual(device["status"],"STALE")
        self.assertIsNone(device["fields"]["connectivity"]["value"])

    def test_P03_unknown_time_fingerprint_and_unsupported_fields(self):
        self.source.records=[replace(self.source.records[0], observed_at=0, source_fingerprint="unverified")]
        d=self.read().body["devices"][0]
        self.assertEqual(d["status"],"UNKNOWN");self.assertIsNone(d["source_fingerprint"])
        self.assertEqual(d["fields"]["battery_mv"],{"status":"UNSUPPORTED","value":None})

    def test_P04_missing_technical_source_is_unsupported_not_healthy(self):
        self.view.technical_source=None
        body=self.read().body
        self.assertEqual(body["status"],"UNSUPPORTED");self.assertEqual(body["devices"],[])

    def test_P05_unsafe_nested_metric_is_unknown(self):
        self.source.records[0].fields["rx_rssi_dbm"]={"secret":"SECRET"}
        field=self.read().body["devices"][0]["fields"]["rx_rssi_dbm"]
        self.assertEqual(field,{"status":"UNKNOWN","value":None})

    def test_P06_foreign_or_stale_epoch_source_row_rejected(self):
        original=self.source.records[0]
        for changes in ({"home_id":"home-b"},{"ownership_epoch":2},{"ownership_epoch":True}):
            self.source.records=[replace(original,**changes)]
            self.assertEqual(self.read().status,403)

    def test_P07_raw_columns_include_payload_filters_rejected(self):
        for query in ({"raw":True},{"columns":["payload"]},{"include_payload":True},{"start":1}):
            self.assertEqual(self.read(query=query).status,400)
        self.assertEqual(self.source.calls,[])

    def test_P08_page_limits_bool_zero_overflow_rejected_before_fetch(self):
        for limit in (True,0,3,-1,"2"):
            self.assertEqual(self.read(query={"limit":limit}).status,400)
        self.assertEqual(self.source.calls,[])

    def test_P09_opaque_cursor_scopes_next_bounded_source_page(self):
        first=self.read(query={"limit":2});token=first.body["next_cursor"]
        self.assertNotIn("home",token)
        second=self.read(query={"limit":2,"cursor":token})
        self.assertEqual([r["device_id"] for r in second.body["devices"]],["node-3"])
        self.assertEqual(self.source.calls,[("home-a",1,0,2),("home-a",1,2,2)])

    def test_P10_cross_home_cursor_denied_without_query(self):
        token=self.read(query={"limit":1}).body["next_cursor"];calls=len(self.source.calls)
        s=self.authority.state
        self.authority.state=replace(s,membership=replace(s.membership,home_id="home-b"),grant=replace(s.grant,home_id="home-b"))
        self.assertEqual(self.read(query={"cursor":token},home="home-b").status,403)
        self.assertEqual(len(self.source.calls),calls)

    def test_P11_stale_source_revision_and_unknown_cursor_deny(self):
        token=self.read(query={"limit":1}).body["next_cursor"]
        self.source.revision="fixture-revision-2"
        self.assertEqual(self.read(query={"cursor":token}).status,403)
        self.assertEqual(self.read(query={"cursor":"forged"}).status,403)

    def test_P12_cursor_store_bounded_eviction_is_explicit_denial(self):
        tokens=[self.read(query={"limit":1}).body["next_cursor"] for _ in range(3)]
        self.assertEqual(len(self.view._cursors),2)
        self.assertEqual(self.read(query={"cursor":tokens[0]}).status,403)

    def test_P13_encoded_byte_limit_does_not_return_partial_data(self):
        self.view.limits=replace(self.limits,max_bytes=100)
        r=self.read();self.assertEqual(r.status,503)
        self.assertEqual(r.body,{"error":"diagnostic_source_unavailable"})
        self.assertEqual(len(self.view._cursors),0)

    def test_P14_missing_numeric_policy_disables_projection(self):
        self.view.limits=None
        self.assertEqual(self.read().status,503);self.assertEqual(self.source.calls,[])
        for value in (0,True,-1):
            with self.assertRaises(ValueError):DiagnosticLimits(value,100,1,5,5)

    def test_P15_source_exceeding_fetch_bound_fails(self):
        self.source.page=lambda *_:TechnicalPage("r",tuple(self.source.records))
        self.assertEqual(self.read().status,503)

    def test_P16_no_store_on_success_denial_invalid_and_fault(self):
        for response in (self.read(),self.read(context={"verified":True}),self.read(query={"raw":True})):
            self.assertEqual(dict(response.headers)["Cache-Control"],"no-store")
        self.source.page=lambda *_:(_ for _ in ()).throw(RuntimeError("SECRET PASSWORD"))
        response=self.read();self.assertEqual(response.status,503)
        self.assertNotIn("SECRET",json.dumps(response.body));self.assertEqual(dict(response.headers)["Cache-Control"],"no-store")


class DurableTraceFoundationTest(FoundationFixture):
    def setUp(self):
        super().setUp()
        temp=tempfile.TemporaryDirectory(prefix="gs125-auth-");self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/"event.sqlite"
        self.db=sqlite3.connect(self.path,isolation_level=None);self.db.row_factory=sqlite3.Row
        self.addCleanup(self.db.close);initialize_sqlite(self.db)
        for home in ("home-a","home-b"):
            self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,'UTC',1,1)",(home,"Private Home"))
        self.registry=HubOwnershipRegistry(self.db)
        self.hub=VerifiedHubIdentity("hub-1","a"*64,"fixture-proof")
        self.registry.register_unclaimed_identity(self.hub,1)
        self.registry.claim_home(self.hub,AuthorizedHomeOperation("fixture-owner","home-a","CLAIM_HUB","fixture-authority"),2)
        self.registry.enroll_node(self.hub,AuthorizedHomeOperation("fixture-owner","home-a","ENROLL_NODE","fixture-enrollment"),
            VerifiedNodeEnrollment("physical-1","logical-1",1,"b"*64,"fixture-proof"),3)
        self.key={"physical_device_id":"physical-1","logical_node_id":"logical-1","origin_session_id":2**53+1,"event_sequence":1}
        self.body={"cloudsync_version":2,"node_enrollment_generation":1,"event_key":self.key,
            "event_type":"MOTION","location":"bathroom","occurred_at":0,"hub_received_at":0,
            "payload":{"resident_name":"Private Person","wifi_password":"SECRET-WIFI","raw":"SECRET-LOG"}}
        self.hub_context={"gs.verified_hub":"hub-1","gs.hub_key_fingerprint":"a"*64,"gs.installation_epoch":1}
        self.committer=DurableEventCommit(self.db)
        self.commit()
        self.read_db=sqlite3.connect(f"file:{self.path}?mode=ro",uri=True);self.read_db.row_factory=sqlite3.Row
        self.addCleanup(self.read_db.close);self.view.db=self.read_db
        self.statements=[];self.read_db.set_trace_callback(self.statements.append)

    def commit(self):
        return self.committer.commit("home-a",self.body,90,
            authorization_guard=lambda db,home,body:self.registry.authorize_cloud_event(db,self.hub_context,home,body))

    def trace(self,key=None):return self.read("trace",{"event_key":self.key if key is None else key})

    def test_T01_original_key_time_room_and_generation_exact(self):
        r=self.trace();self.assertEqual(r.status,200)
        b=r.body;self.assertEqual(b["event_key"]["origin_session_id"],str(2**53+1))
        self.assertEqual(b["canonical_event_id"],DurableEventCommit._identity(self.body)[1])
        self.assertEqual(b["location"],"bathroom");self.assertEqual(b["enrollment_generation"],"1")
        self.assertEqual(b["times"]["occurred_at"],{"value":None,"status":"UNKNOWN","clock_trust":"UNKNOWN"})
        self.assertEqual(b["times"]["hub_received_at"]["status"],"UNKNOWN")
        self.assertEqual(b["times"]["committed_at"]["value"],90)
        self.assertEqual(b["times"]["committed_at"]["clock_trust"],"UNKNOWN")

    def test_T02_missing_stages_unknown_backend_commit_independent(self):
        stages=self.trace().body["stages"]
        self.assertEqual(len(stages),12);self.assertEqual(sum(s["result"]=="UNKNOWN" for s in stages),11)
        self.assertEqual(stages[8]["result"],"PASS")
        self.assertEqual(stages[8]["provenance"]["observation"],"READ_ONLY_SQLITE_JOIN")
        self.assertEqual(stages[8]["provenance"]["deployment"],"UNKNOWN")
        self.assertIsNone(stages[8]["provenance"]["source_fingerprint"])
        self.assertEqual(stages[-1]["result"],"UNKNOWN")

    def test_T03_class_b_privacy_allowlist_and_payload_free_sql(self):
        body=self.trace().body;text=json.dumps(body)
        for forbidden in ("SECRET","Private Person","payload","phone","proof","payload_sha256"):
            self.assertNotIn(forbidden,text)
        self.assertTrue(all("payload_json" not in sql and "SELECT *" not in sql for sql in self.statements))
        self.assertEqual(set(body),{"schema_version","class","home_id","status","canonical_event_id","event_key","ownership_epoch","enrollment_generation","category","location","times","stages"})

    def test_T04_wrong_home_deny_before_database(self):
        self.assertEqual(self.read("trace",{"event_key":self.key},home="home-b").status,403)
        self.assertEqual(self.statements,[])

    def test_T05_wrong_key_absent_and_old_window_have_identical_unknown(self):
        wrong=self.trace(dict(self.key,event_sequence=2)).body
        self.at=200;old=self.trace().body
        self.assertEqual(wrong,old);self.assertEqual(old["status"],"UNKNOWN")

    def test_T06_stale_or_unqualified_device_generation_never_joined(self):
        self.authority.generation=2
        self.assertEqual(self.trace().body["status"],"UNKNOWN")
        self.authority.binding_active=False;self.statements.clear()
        self.assertEqual(self.trace().body["status"],"UNKNOWN");self.assertEqual(self.statements,[])

    def test_T07_duplicate_commit_reopen_one_row_and_unchanged_original(self):
        self.assertTrue(self.commit()["duplicate"])
        before=self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.read_db.close();self.read_db=sqlite3.connect(f"file:{self.path}?mode=ro",uri=True);self.read_db.row_factory=sqlite3.Row
        self.addCleanup(self.read_db.close);self.view.db=self.read_db
        self.assertEqual(self.trace().body["location"],"bathroom")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],before)
        self.assertEqual(before,1)

    def test_T08_invalid_key_and_raw_projection_controls_rejected(self):
        for key in (dict(self.key,event_sequence=True),dict(self.key,origin_session_id=2**63),dict(self.key,raw=True)):
            self.assertEqual(self.trace(key).status,400)
        self.assertEqual(self.read("trace",{"event_key":self.key,"include_payload":True}).status,400)
        self.assertEqual(self.statements,[])

    def test_T09_closed_or_missing_database_safe_and_no_store(self):
        self.read_db.close();r=self.trace();self.assertEqual(r.status,503)
        self.assertEqual(dict(r.headers)["Cache-Control"],"no-store")
        self.view.db=None;self.assertEqual(self.trace().status,503)

    def test_T10_commit_without_owned_provenance_unknown(self):
        self.db.execute("UPDATE durable_event_commits SET node_enrollment_generation=NULL WHERE home_id='home-a'")
        self.assertEqual(self.trace().body["status"],"UNKNOWN")

    def test_T11_binding_revoked_during_read_returns_no_trace(self):
        self.read_db.set_trace_callback(lambda _:setattr(self.authority,"binding_active",False))
        r=self.trace();self.assertEqual(r.status,403)
        self.assertNotIn("canonical_event_id",r.body)

    def test_T12_read_only_source_does_not_mutate_or_open_new_storage(self):
        before=self.db.total_changes
        self.assertEqual(self.trace().status,200)
        self.assertEqual(self.db.total_changes,before)
        self.assertTrue(all(sql.lstrip().startswith("SELECT") for sql in self.statements))

    def test_T13_deterministic_trigger_commit_query_expire_revoke_recovery(self):
        self.assertEqual(self.trace().body["stages"][8]["result"],"PASS")
        self.grant(revoked=True);self.assertEqual(self.trace().status,403)
        self.grant(revoked=False,version=2);self.assertEqual(self.trace().status,200)
        self.at=500;self.assertEqual(self.trace().status,403)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0],1)

    def test_T14_caregiver_product_query_behavior_unchanged(self):
        service=GharSajagService()
        service.homes.create("home-a","Fixture Home","Asia/Kolkata","en-IN","fixture-owner",
                            [Resident("fixture-resident","Fixture",True,1)],1)
        from ghar_sajag.sqlite_events import SQLiteEventMap
        service.store.events=SQLiteEventMap(self.read_db)
        snapshot=service.queries.snapshot("home-a","fixture-owner",100)
        self.assertEqual(snapshot["latest_activity"]["location"],"bathroom")
        self.assertEqual(snapshot["latest_activity"]["event_id"],self.trace().body["canonical_event_id"])


if __name__ == "__main__":unittest.main()
