"""GS-125 inactive design exercise: no production acceptance or physical PASS."""
import copy
from dataclasses import replace
import unittest

from ghar_sajag.node_health_policy import NodeHealthPolicy, Legacy120Policy
from review_model import (FixtureGrant, Observation, ReviewWindow, ExpectedDevice,
                          InstallationReview, STAGES, canonical_key, diagnostic_key,
                          trace, contact_health, ack_meaning)

KEY = {"physical_device_id": "device-A", "logical_node_id": "room-1",
       "origin_session_id": 17, "event_sequence": 1}


def grant(**changes):
    return replace(FixtureGrant("fixture-tech", "home", 100,
                               frozenset({"READ_DIAGNOSTICS"})), **changes)


def obs(stage="node_created", result="PASS", key=None, **changes):
    return replace(Observation(1, "home", canonical_key(key or KEY), stage, result,
                              "fixture-owner", "isolated-source-evidence", "HOST_SIMULATION",
                              11, "fixture-boot", 110, "OBSERVED"), **changes)


def device(**changes):
    return replace(ExpectedDevice("device-A", "room-1", 7, "bathroom", "MOTION",
                                  frozenset({"node_created", "hub_persisted", "backend_committed"})), **changes)


class ReviewModelTest(unittest.TestCase):
    def test_identity_uses_original_production_canonical_key(self):
        self.assertEqual(canonical_key(KEY), "p8:device-An6:room-1s17q1")

    def test_replacement_same_logical_session_sequence_is_distinct(self):
        self.assertNotEqual(canonical_key(KEY), canonical_key({**KEY, "physical_device_id": "device-B"}))

    def test_original_session_is_not_current_transport_session(self):
        self.assertNotEqual(canonical_key(KEY), canonical_key({**KEY, "origin_session_id": 18}))

    def test_large_identity_is_exact_in_browser_projection(self):
        key = {**KEY, "origin_session_id": 2**53 + 1, "event_sequence": 2**63 - 1}
        self.assertEqual(diagnostic_key(key)["origin_session_id"], "9007199254740993")
        self.assertEqual(diagnostic_key(key)["event_sequence"], str(2**63 - 1))

    def test_invalid_identity_boundaries_and_bool_rejected(self):
        for value in (True, 0, -1, 2**63, 1.5, "17"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid_event_key"):
                canonical_key({**KEY, "origin_session_id": value})

    def test_extra_identity_fields_rejected(self):
        with self.assertRaises(ValueError):
            canonical_key({**KEY, "transport_session": 19})

    def test_downstream_commit_does_not_prove_prior_stages(self):
        view = trace("home", KEY, [obs("backend_committed")], grant(), 10)
        self.assertEqual(len(view["stages"]), 10)
        self.assertEqual(view["stages"][8]["result"], "PASS")
        self.assertTrue(all(s["result"] == "UNKNOWN" for s in view["stages"][:8]))
        self.assertEqual(view["stages"][9]["result"], "UNKNOWN")

    def test_duplicate_observations_one_event_multiple_attempts(self):
        view = trace("home", KEY, [obs(), obs(cursor=12)], grant(), 10)
        self.assertEqual(len(view["stages"][1]["observations"]), 2)
        self.assertEqual(view["canonical_event_id"], canonical_key(KEY))

    def test_conflicting_observations_never_last_success_wins(self):
        view = trace("home", KEY, [obs(result="FAIL"), obs(cursor=12)], grant(), 10)
        self.assertEqual(view["stages"][1]["result"], "WARNING")
        self.assertEqual(view["stages"][1]["reason_code"], "CONFLICTING_OBSERVATIONS")

    def test_foreign_home_and_other_key_observations_not_joined(self):
        view = trace("home", KEY, [obs(home="other-home"), obs(key={**KEY, "event_sequence": 2})], grant(), 10)
        self.assertTrue(all(s["result"] == "UNKNOWN" for s in view["stages"]))

    def test_caregiver_generic_read_does_not_grant_diagnostics(self):
        with self.assertRaises(PermissionError):
            trace("home", KEY, [], grant(permissions=frozenset({"read"})), 10)

    def test_cross_home_denial_occurs_before_invalid_key_lookup(self):
        with self.assertRaises(PermissionError):
            trace("foreign", {}, [], grant(), 10)

    def test_expired_revoked_missing_actor_grants_denied(self):
        for g, now in ((grant(), 100), (grant(active=False), 10), (grant(actor=""), 10)):
            with self.subTest(g=g), self.assertRaises(PermissionError):
                trace("home", KEY, [], g, now)

    def test_strict_observation_schema_and_provenance(self):
        for changes in ({"schema_version": True}, {"schema_version": 2}, {"stage": "invented"},
                        {"result": "OK"}, {"cursor": True}, {"environment": "PHYSICAL_PASS"},
                        {"evidence": ""}, {"observed_ms": -1}, {"producer": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                obs(**changes)

    def test_raw_secrets_or_unbounded_reason_not_accepted(self):
        for changes in ({"reason_code": "Bearer secret"}, {"evidence": "x" * 257}):
            with self.assertRaises(ValueError):
                obs(**changes)

    def test_clock_domains_kept_not_sorted_as_one_time(self):
        view = trace("home", KEY, [obs(observed_ms=999), obs(cursor=12, clock_domain="next-boot", observed_ms=1)], grant(), 10)
        self.assertEqual([o["clock_domain"] for o in view["stages"][1]["observations"]], ["fixture-boot", "next-boot"])

    def test_lease_equality_and_one_ms_expiry_use_production_policy(self):
        policy = NodeHealthPolicy()
        self.assertEqual(policy.offline_seconds, 910)
        self.assertEqual(contact_health(1, 910001, policy), "HEALTHY")
        self.assertEqual(contact_health(1, 910002, policy), "OFFLINE")

    def test_trusted_legacy_profiles_use_existing_leases(self):
        self.assertEqual(NodeHealthPolicy(60).offline_seconds, 190)
        self.assertEqual(Legacy120Policy(120).offline_seconds, 310)

    def test_unknown_profile_contact_clock_or_authentication_is_unknown(self):
        for args in ((None, 10, NodeHealthPolicy()), (10, 9, NodeHealthPolicy()),
                     (1, 10, None), (1, 10, NodeHealthPolicy(), False),
                     (1, 10, NodeHealthPolicy(), True, False)):
            self.assertEqual(contact_health(*args), "UNKNOWN")

    def test_authenticated_recovery_restores_communication_health(self):
        self.assertEqual(contact_health(1, 1000000, NodeHealthPolicy()), "OFFLINE")
        self.assertEqual(contact_health(1000000, 1000001, NodeHealthPolicy()), "HEALTHY")

    def test_mac_send_and_volatile_ack_not_retirement_proof(self):
        self.assertEqual(ack_meaning("MAC_SUCCESS"), "RADIO_RESULT_ONLY")
        self.assertEqual(ack_meaning("HUB_ACK_SENT"), "NODE_RECEIPT_UNKNOWN")
        self.assertEqual(ack_meaning("RECEIVED_VOLATILE"), "RETAINED_PENDING")
        self.assertEqual(ack_meaning("unsupported"), "UNKNOWN")

    def test_count_bound_keeps_gap_and_recent_evidence(self):
        window = ReviewWindow(2, 4096)
        for cursor in range(11, 15):
            self.assertTrue(window.append(obs(cursor=cursor)))
        self.assertEqual([o.cursor for o in window.observations()], [13, 14])
        self.assertEqual(window.dropped, 2)

    def test_byte_bound_rejects_oversize_record_without_evicting_product(self):
        window = ReviewWindow(10, 20)
        self.assertFalse(window.append(obs()))
        self.assertEqual((window.bytes, window.dropped, len(window.rows)), (0, 1, 0))

    def test_byte_budget_also_limits_count(self):
        window = ReviewWindow(100, 700)
        for cursor in range(1, 101):
            window.append(obs(cursor=cursor))
        self.assertLessEqual(window.bytes, 700)
        self.assertLess(len(window.rows), 100)
        self.assertGreater(window.dropped, 0)

    def test_window_requires_explicit_valid_budget(self):
        for limits in ((0, 1), (1, 0), (True, 1)):
            with self.assertRaises(ValueError):
                ReviewWindow(*limits)


class InstallationReviewTest(unittest.TestCase):
    def setUp(self):
        self.session = InstallationReview("home", (device(),), timeout_ms=1000)
        self.session.arm(0, 100, 10, "fixture-boot")

    def observe(self, stage="node_created", key=None, **changes):
        key = key or KEY
        generation = changes.pop("generation", 7)
        room = changes.pop("room", "bathroom")
        kind = changes.pop("kind", "MOTION")
        now = changes.pop("now_ms", 120)
        return self.session.observe(key, generation, room, kind, obs(stage, key=key, **changes), now)

    def test_exact_event_requires_all_stages(self):
        self.assertEqual(self.observe(), "LOCAL_OBSERVED")
        self.assertEqual(self.observe("hub_persisted"), "LOCAL_OBSERVED")
        self.assertEqual(self.session.result(), "PARTIAL")
        self.assertEqual(self.observe("backend_committed"), "PASS")
        self.assertEqual(self.session.result(), "PASS")

    def test_wrong_physical_logical_generation_room_kind_do_not_pass(self):
        for kwargs in ({"key": {**KEY, "physical_device_id": "wrong"}},
                       {"key": {**KEY, "logical_node_id": "wrong"}},
                       {"generation": 8}, {"room": "kitchen"}, {"kind": "DOOR_OPEN"}):
            self.assertEqual(self.observe(**kwargs), "WRONG_DEVICE_OR_CONTEXT")
            self.assertEqual(self.session.states, ["ARMED"])

    def test_backend_delivery_without_fresh_creation_cannot_pass(self):
        self.assertEqual(self.observe("backend_committed"), "CREATION_EVIDENCE_REQUIRED")
        self.assertEqual(self.session.result(), "PARTIAL")

    def test_delayed_backlog_old_cursor_or_boot_cannot_satisfy_stimulus(self):
        for kwargs in ({"cursor": 10}, {"observed_ms": 99}, {"clock_domain": "old-boot"}, {"observed_ms": 121}):
            self.assertEqual(self.observe(**kwargs), "NOT_FRESH_STIMULUS")
        self.assertEqual(self.session.states, ["ARMED"])

    def test_timeout_boundary_nonpass_and_retry_preserves_attempt(self):
        self.session.tick(1099)
        self.assertEqual(self.session.states, ["ARMED"])
        self.session.tick(1100)
        self.assertEqual(self.session.states, ["TIMEOUT"])
        self.session.arm(0, 1200, 20, "fixture-boot")
        self.assertEqual(len(self.session.attempts[0]), 2)
        self.assertEqual(self.session.attempts[0][0]["result"], "TIMEOUT")
        self.assertEqual(self.session.result(), "PARTIAL")

    def test_duplicate_same_stage_does_not_satisfy_missing_stage(self):
        self.observe()
        self.observe(cursor=12)
        self.assertEqual(len(self.session.evidence[0]), 1)
        self.assertEqual(self.session.result(), "PARTIAL")

    def test_different_candidate_cannot_borrow_commit(self):
        self.observe()
        self.assertEqual(self.observe("backend_committed", key={**KEY, "event_sequence": 2}), "DIFFERENT_CANDIDATE")
        self.assertEqual(self.session.result(), "PARTIAL")

    def test_nonpass_stage_does_not_satisfy_requirement(self):
        self.observe()
        self.assertEqual(self.observe("hub_persisted", result="FAIL"), "NON_PASS_EVIDENCE")
        self.assertNotIn("hub_persisted", self.session.evidence[0])

    def test_unexercised_second_device_blocks_overall_pass(self):
        self.session = InstallationReview("home", (device(), device(physical="device-B", logical="room-2")), 1000)
        self.session.arm(0, 100, 10, "fixture-boot")
        for stage in ("node_created", "hub_persisted", "backend_committed"):
            self.observe(stage)
        self.assertEqual(self.session.states, ["PASS", "NOT_TESTED"])
        self.assertEqual(self.session.result(), "PARTIAL")
        self.session.arm(1, 100, 10, "fixture-boot")
        self.assertEqual(self.observe(), "WRONG_DEVICE_OR_CONTEXT")
        key = {**KEY, "physical_device_id": "device-B", "logical_node_id": "room-2"}
        for stage in ("node_created", "hub_persisted", "backend_committed"):
            self.observe(stage, key=key)
        self.assertEqual(self.session.result(), "PASS")

    def test_unsupported_required_capability_never_passes(self):
        session = InstallationReview("home", (device(supported=False),), 1000)
        session.arm(0, 100, 10, "fixture-boot")
        self.assertEqual(session.states, ["UNSUPPORTED"])
        self.assertEqual(session.result(), "PARTIAL")

    def test_concurrent_arm_and_passing_step_rearm_rejected(self):
        with self.assertRaises(ValueError):
            self.session.arm(0, 100, 10, "fixture-boot")
        for stage in ("node_created", "hub_persisted", "backend_committed"):
            self.observe(stage)
        with self.assertRaises(ValueError):
            self.session.arm(0, 200, 10, "fixture-boot")

    def test_manifest_no_duplicate_device_or_missing_stage_policy(self):
        for devices in ((device(), device()), (device(required_stages=frozenset()),)):
            with self.assertRaises(ValueError):
                InstallationReview("home", devices, 1000)


if __name__ == "__main__":
    unittest.main()
