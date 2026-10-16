#!/usr/bin/env python3
"""Host-only GS-40 qualification case runner.

mock and replay never enumerate or open devices. `live` is deliberately gated:
until an approved non-resetting telemetry provider is registered, it emits
BLOCKED case reports and performs no USB, serial, network, or board operation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PRODUCT = Path(__file__).resolve().parents[2]
REPO = PRODUCT.parent
CASE_REGISTRY = Path(__file__).with_name("gs40_cases.json")
MOCK_FIXTURE = PRODUCT / "tests/fixtures/hil/gs40_mock_observations.json"
CAPTURE_REPLAY_FIXTURE = PRODUCT / "tests/fixtures/hil/gs40_s3_capture_11158_replay.json"
CONFIG_PATH = PRODUCT / "config/node_health.json"
VALID_VERDICTS = {"HOST_PASS", "PHYSICAL_PASS", "FAIL", "BLOCKED", "NOT_RUN"}
EXPECTED_CASE_IDS = [f"GS40-TC{index:02d}" for index in range(1, 8)]
FAULT_CASES = {
    "usb_identity_mismatch": "IDENTITY_MISMATCH",
    "port_absent_or_stale": "PORT_UNAVAILABLE",
    "port_busy": "PORT_BUSY",
    "transport_loss": "TRANSPORT_LOSS",
    "truncated_log": "TRUNCATED_LOG",
    "reset_banner": "RESET_BANNER",
    "timestamp_gap": "TIMESTAMP_GAP",
    "timeout": "OBSERVATION_TIMEOUT",
    "boot_generation_change": "BOOT_GENERATION_CHANGE",
    "timestamp_wrap": "TIMESTAMP_WRAP",
}
PREFLIGHT_FAULTS = {"usb_identity_mismatch", "port_absent_or_stale", "port_busy"}
SOURCE_INPUTS = [
    "code/Makefile",
    "code/config/node_health.json",
    "code/backend/ghar_sajag/node_health_policy.py",
    "code/backend/ghar_sajag/foundation.py",
    "code/backend/ghar_sajag/http_api.py",
    "code/backend/ghar_sajag/queries.py",
    "code/backend/DATA_MODEL.md",
    "code/firmware/hub/cloud_sync/cloud_sync.hpp",
    "code/firmware/hub/cloud_sync/cloud_sync.cpp",
    "code/firmware/hub/runtime/hub_runtime.hpp",
    "code/firmware/hub/runtime/hub_runtime.cpp",
    "code/firmware/hub/target/esp32/hub_runtime_adapter.cpp",
    "code/firmware/hub/target/esp32/idf/main/app_main.cpp",
    "code/frontend/src/features/home/index.mjs",
    "code/frontend/public/app.mjs",
    "code/tests/cpp/gs40_node_health_validation.cpp",
    "code/tests/cpp/gs150_offline_sleep_validation.cpp",
    "code/tests/python/test_node_health_config.py",
    "code/tests/python/test_gs40_qualification.py",
    "code/tests/fixtures/hil/gs40_mock_observations.json",
    "code/tests/fixtures/hil/gs40_s3_capture_11158_replay.json",
    "code/tools/hil/gs40_qualification.py",
    "code/tools/hil/gs40_cases.json",
    "code/validation/suites.json",
    "docs/validation/MASTER_TRACEABILITY.csv",
    "docs/validation/PHYSICAL_HIL_CATALOGUE.csv",
    "docs/validation/PHYSICAL_QUALIFICATION.csv",
]


class QualificationError(RuntimeError):
    """A classified failure in host-side setup, assertion, or evidence input."""


def inspect_live_observation_sources() -> dict[str, Any]:
    """Read-only source audit for the live NodeHealth-to-caregiver evidence path.

    This is intentionally not a device probe. A source-level path is considered
    ready only when the S3 runtime publishes through an instantiated trusted
    CloudSync worker, the backend accepts and projects the publication, and the
    caregiver PWA renders that projection. Host simulations are not counted as
    production providers.
    """
    def read(relative: str) -> str:
        path = REPO / relative
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""

    hub_runtime = read("code/firmware/hub/target/esp32/hub_runtime_adapter.cpp")
    hub_entry = read("code/firmware/hub/target/esp32/idf/main/app_main.cpp")
    cloud_sync = read("code/firmware/hub/cloud_sync/cloud_sync.hpp") + read(
        "code/firmware/hub/cloud_sync/cloud_sync.cpp")
    backend_api = read("code/backend/ghar_sajag/http_api.py")
    backend_queries = read("code/backend/ghar_sajag/queries.py")
    backend_model = read("code/backend/DATA_MODEL.md")
    pwa_view = read("code/frontend/src/features/home/index.mjs")
    durable_api = read("code/backend/ghar_sajag/durable_api.py")

    checks = {
        "hub_authenticates_and_records_node_health": (
            "decode_node_health" in hub_runtime and
            "observe_authenticated_health" in hub_runtime),
        "cloudsync_has_node_health_publication": any(marker in cloud_sync for marker in (
            "publish_node_health", "submit_node_health", "NodeHealthPublication")),
        "s3_instantiates_cloudsync_worker": "CloudSyncWorker" in hub_entry,
        "s3_has_trusted_cloud_authority_source": (
            "CloudAuthoritySource" in hub_entry or
            "CloudAuthoritySource" in hub_runtime),
        "backend_has_authenticated_node_health_ingest": (
            "node-health" in backend_api or "node_health" in backend_api),
        "backend_snapshot_projects_node_health": (
            "node_health" in backend_queries and
            "node_health" in backend_model),
        "caregiver_pwa_projects_node_health": "node_health" in pwa_view,
        "backend_event_api_is_local_host_adapter": (
            "Small WSGI adapter for local integration tests" in backend_api and
            "deliberately does not authenticate Hub requests" in durable_api and
            "local development" in durable_api),
    }
    complete = all(checks[key] for key in (
        "hub_authenticates_and_records_node_health",
        "cloudsync_has_node_health_publication",
        "s3_instantiates_cloudsync_worker",
        "s3_has_trusted_cloud_authority_source",
        "backend_has_authenticated_node_health_ingest",
        "backend_snapshot_projects_node_health",
        "caregiver_pwa_projects_node_health",
    ))
    blockers = [key for key, passed in checks.items()
                if key != "hub_authenticates_and_records_node_health" and not passed]
    return {
        "schema_version": 1,
        "production_path_complete": complete,
        "checks": checks,
        "blockers": blockers,
        "device_access": "NONE",
        "physical_pass_claimed": False,
    }


def _parse_utc(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError(f"{field} must include a UTC timezone")
    return parsed.astimezone(dt.timezone.utc)


def assess_observation_bundle(bundle: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Correlate normalized Hub, backend and caregiver observations.

    This is a pure validator: it performs no device, USB, serial, network, or
    filesystem access. A collector must preserve the original source evidence
    and attest each live source through an approved provider. Provider
    authentication is deliberately not inferred from JSON fields. Even a
    valid synthetic bundle is only HOST_PASS; this function never promotes
    evidence to PHYSICAL_PASS.
    """
    required_layers = ("hub", "backend", "pwa")
    checks: list[dict[str, str]] = []

    def add(condition: bool, name: str, detail: str) -> None:
        checks.append({"check": name, "result": "PASS" if condition else "FAIL", "detail": detail})

    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        return {"verdict": "BLOCKED", "failure": "OBSERVATION_BUNDLE_SCHEMA_UNSUPPORTED",
                "assertions": checks, "physical_pass_claimed": False}
    if any(not isinstance(bundle.get(layer), dict) for layer in ("node", *required_layers)):
        return {"verdict": "BLOCKED", "failure": "OBSERVATION_BUNDLE_LAYER_MISSING",
                "assertions": checks, "physical_pass_claimed": False}

    try:
        health_config = config.get("node_health", {})
        profiles = config.get("deployment_profiles", {})
        heartbeat = health_config.get("heartbeat_interval_seconds") if isinstance(health_config, dict) else None
        if (not isinstance(config, dict) or set(config) != {"schema_version", "node_health", "deployment_profiles"} or
                type(config.get("schema_version")) is not int or config.get("schema_version") != 1 or
                not isinstance(health_config, dict) or
                set(health_config) != {"heartbeat_interval_seconds", "piggyback_on_events"} or
                type(heartbeat) is not int or not 15 <= heartbeat <= 3600 or
                health_config.get("piggyback_on_events") is not True or
                not isinstance(profiles, dict) or len(profiles) > 10 or
                any(not isinstance(key, str) or not re.fullmatch(r"c3-[0-9a-f]{12}", key) or
                    value not in {"configured", "legacy_60", "legacy_120"}
                    for key, value in profiles.items())):
            raise ValueError("effective NodeHealth configuration is invalid")
        captured_at = _parse_utc(bundle.get("captured_at_utc"), "captured_at_utc")
        layers = {name: bundle[name] for name in ("node", *required_layers)}
        observed_at: dict[str, dt.datetime] = {}
        for name, layer in layers.items():
            observed = _parse_utc(layer.get("observed_at_utc"), f"{name}.observed_at_utc")
            if observed > captured_at:
                raise ValueError(f"{name}.observed_at_utc is later than captured_at_utc")
            observed_at[name] = observed
        pwa_snapshot_at = _parse_utc(layers["pwa"].get("backend_snapshot_observed_at_utc"),
                                     "pwa.backend_snapshot_observed_at_utc")
        if pwa_snapshot_at > captured_at:
            raise ValueError("pwa.backend_snapshot_observed_at_utc is later than captured_at_utc")
        node = layers["node"]
        hub = layers["hub"]
        backend = layers["backend"]
        pwa = layers["pwa"]
        identity = node.get("identity")
        profile = profiles.get(identity) if isinstance(identity, str) else None
        if profile == "configured" and type(heartbeat) is int:
            offline_after = 3 * heartbeat + 10
        elif profile == "legacy_60":
            offline_after = 190
        elif profile == "legacy_120":
            offline_after = 310
        else:
            offline_after = None

        contact = node.get("last_authenticated_contact")
        contact_valid = (isinstance(contact, dict) and
                         contact.get("authenticated") is True and
                         contact.get("identity") == identity and
                         isinstance(contact.get("session_id"), str) and bool(contact.get("session_id")) and
                         ((isinstance(contact.get("contact_id"), str) and bool(contact.get("contact_id"))) or
                          (type(contact.get("contact_id")) is int and contact.get("contact_id") >= 0)))
        contact_at = (_parse_utc(contact.get("received_at_utc"), "node.last_authenticated_contact.received_at_utc")
                      if contact_valid else None)
        age = (captured_at - contact_at).total_seconds() if contact_at else None
        if age is not None and age < 0:
            raise ValueError("authenticated contact is later than captured_at_utc")

        identity_trusted = node.get("trusted_identity") is True
        profile_known = offline_after is not None
        if not identity_trusted or not profile_known or not contact_valid:
            expected_hub_status = "UNKNOWN"
        elif age <= offline_after:
            expected_hub_status = "ONLINE"
        else:  # Existing backend expiry uses a strict greater-than comparison.
            expected_hub_status = "OFFLINE"
        hub_observation_fresh = (captured_at - observed_at["hub"]).total_seconds() <= 190
        if hub.get("reachable") is not True or not hub_observation_fresh:
            expected_hub_status = "UNKNOWN"

        cloud_contact = hub.get("last_backend_contact_at_utc")
        cloud_fresh = False
        if isinstance(cloud_contact, str):
            cloud_age = (captured_at - _parse_utc(cloud_contact, "hub.last_backend_contact_at_utc")).total_seconds()
            cloud_fresh = 0 <= cloud_age <= 190
        backend_path_current = (hub.get("reachable") is True and
                                hub_observation_fresh and
                                hub.get("internet_connected") is True and
                                backend.get("reachable") is True and cloud_fresh and
                                (captured_at - observed_at["backend"]).total_seconds() <= 190)
        expected_backend_status = expected_hub_status if backend_path_current else "UNKNOWN"
        expected_backend_coverage = "COVERED" if expected_backend_status == "ONLINE" else "UNKNOWN"
        pwa_snapshot_fresh = (captured_at - pwa_snapshot_at).total_seconds() <= 190
        expected_pwa_status = (expected_backend_status if backend.get("reachable") is True and
                               pwa.get("reachable") is True and pwa_snapshot_fresh else "UNKNOWN")
        expected_pwa_coverage = "COVERED" if expected_pwa_status == "ONLINE" else "UNKNOWN"

        downstream_not_healthy = not (
            hub.get("node_status") == "ONLINE" or
            backend.get("node_status") == "ONLINE" or
            backend.get("coverage_status") == "COVERED" or
            pwa.get("node_status") == "ONLINE" or
            pwa.get("coverage_status") == "COVERED")
        add(identity_trusted or downstream_not_healthy, "trusted_node_identity",
            "Untrusted identity must remain unknown and can never be shown healthy.")
        add(profile_known or downstream_not_healthy, "known_deployment_profile",
            "Unknown profiles must remain unknown; known identities use configured 300/910 or explicit legacy timing.")
        add(contact_valid or downstream_not_healthy, "authenticated_received_contact",
            "Missing/unauthenticated contact must remain unknown; MAC send success is not accepted as received contact.")
        add(hub.get("node_status") == expected_hub_status, "hub_lease_status",
            f"Hub status must be {expected_hub_status}; configured offline boundary is strictly greater than {offline_after}s." if offline_after else
            "Hub status must remain UNKNOWN for an untrusted or unknown-profile identity.")
        add(backend.get("node_status") == expected_backend_status and
            backend.get("coverage_status") == expected_backend_coverage,
            "backend_status_and_coverage", "Backend must preserve the Node lease and report coverage UNKNOWN when its Hub/cloud source is unavailable.")
        add(pwa.get("node_status") == expected_pwa_status and
            pwa.get("coverage_status") == expected_pwa_coverage,
            "caregiver_pwa_status_and_coverage", "Caregiver PWA must mirror backend status; no stale or disconnected source may appear covered.")

        expected_contact = contact if contact_valid else None
        for layer_name, layer in (("hub", hub), ("backend", backend), ("pwa", pwa)):
            add(layer.get("source_contact") == expected_contact,
                f"{layer_name}_contact_correlation", "Identity, session and contact identifier must match the Hub-accepted contact.")
            add(layer.get("identity") == identity,
                f"{layer_name}_identity_correlation", "All layers must refer to the same physical Node identity.")
    except (AttributeError, TypeError, ValueError) as exc:
        return {"verdict": "BLOCKED", "failure": f"OBSERVATION_BUNDLE_INVALID:{exc}",
                "assertions": checks, "physical_pass_claimed": False}

    assertions_passed = all(row["result"] == "PASS" for row in checks)
    provenance = bundle.get("provenance")
    if not assertions_passed:
        verdict = "FAIL"
    elif provenance == "SYNTHETIC_DETERMINISTIC_FIXTURE":
        verdict = "HOST_PASS"
    elif provenance == "LIVE_CURRENT_TARGET":
        # No production provider currently attests the Hub/backend/PWA source
        # chain. User-supplied JSON cannot grant itself physical provenance.
        verdict = "BLOCKED"
    else:
        verdict = "BLOCKED"
    return {
        "verdict": verdict,
        "failure": None if verdict == "HOST_PASS" else
                   "LIVE_PROVIDER_ATTESTATION_UNAVAILABLE" if provenance == "LIVE_CURRENT_TARGET" and assertions_passed else
                   "OBSERVATION_PROVENANCE_NOT_ACCEPTED" if assertions_passed else "OBSERVATION_ASSERTION_FAILED",
        "assertions": checks,
        "assertion_count": len(checks),
        "assertions_passed": sum(row["result"] == "PASS" for row in checks),
        "physical_pass_claimed": False,
        "node_offline_after_seconds": offline_after,
        "hub_cloud_freshness_seconds": 190,
        "observed_node_status": expected_hub_status,
        "observed_caregiver_status": expected_pwa_status,
        "observed_caregiver_coverage": expected_pwa_coverage,
    }


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def current_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def current_branch() -> str:
    try:
        return subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for name in SOURCE_INPUTS:
        path = REPO / name
        if not path.is_file():
            continue
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationError(f"INPUT_INVALID:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise QualificationError(f"INPUT_INVALID:{path}:top-level JSON must be an object")
    return value


def load_registry(path: Path = CASE_REGISTRY) -> dict[str, Any]:
    registry = load_json(path)
    cases = registry.get("cases")
    ids = [case.get("id") for case in cases or [] if isinstance(case, dict)]
    if registry.get("schema_version") != 1 or ids != EXPECTED_CASE_IDS:
        raise QualificationError("CASE_REGISTRY_INVALID: expected schema 1 and ordered GS40-TC01..TC07")
    if len({case.get("physical_id") for case in cases if case.get("physical_id")}) != 6:
        raise QualificationError("CASE_REGISTRY_INVALID: six unique physical case links are required")
    return registry


def load_mock_fixture(path: Path = MOCK_FIXTURE) -> dict[str, Any]:
    fixture = load_json(path)
    if fixture.get("schema_version") != 1 or fixture.get("provenance") != "SYNTHETIC_DETERMINISTIC_FIXTURE":
        raise QualificationError("MOCK_FIXTURE_INVALID: schema/provenance is not recognized")
    cases = fixture.get("cases")
    if not isinstance(cases, dict):
        raise QualificationError("MOCK_FIXTURE_INVALID: cases must be an object")
    return fixture


def check(checks: list[dict[str, str]], condition: bool, name: str, detail: str) -> None:
    checks.append({"check": name, "result": "PASS" if condition else "FAIL", "detail": detail})


def evaluate_mock(case_id: str, fixture: dict[str, Any], config: dict[str, Any]) -> tuple[list[dict[str, str]], str | None]:
    registry = load_registry()
    case = next((item for item in registry["cases"] if item["id"] == case_id), None)
    if case is None:
        raise QualificationError(f"UNKNOWN_CASE:{case_id}")
    sample = fixture["cases"].get(case["mock_fixture"])
    if not isinstance(sample, dict):
        raise QualificationError(f"MOCK_CASE_INPUT_MISSING:{case_id}")
    checks: list[dict[str, str]] = []
    physical_disposition: str | None = None

    if case_id == "GS40-TC01":
        health = config.get("node_health", {})
        interval = health.get("heartbeat_interval_seconds")
        opportunities = sample.get("quiet_opportunities", [])
        stamps = [row.get("at_seconds") for row in opportunities]
        report_ids = [row.get("report_id") for row in opportunities]
        negatives = sample.get("negative_probes", {})
        check(checks, interval == 300 and health.get("piggyback_on_events") is True and
              sample.get("heartbeat_interval_seconds") == 300 and sample.get("offline_timeout_seconds") == 910,
              "configured_300_910", "Repository configuration and fixture identify 300 s / 910 s.")
        check(checks, stamps == [300, 600, 900, 1200, 1500, 1800], "six_quiet_opportunities",
              "Exactly six quiet opportunities are spaced at 300-second intervals.")
        check(checks, len(report_ids) == len(set(report_ids)) and all(row.get("authenticated") is True for row in opportunities),
              "authenticated_unique_health", "Every health report is authenticated and has a unique report identity.")
        check(checks, all(negatives.get(key) is True for key in
              ("missing_report_rejected", "duplicate_report_rejected", "unauthenticated_report_rejected")),
              "negative_health_reports", "Missing, duplicate, and unauthenticated health reports are rejected.")

    elif case_id == "GS40-TC02":
        mac = sample.get("mac_only_contact", {})
        app = sample.get("authenticated_event_contact", {})
        check(checks, mac.get("mac_tx_success") is True and mac.get("application_authenticated") is False and
              mac.get("health_suppressed") is False, "mac_is_not_contact",
              "MAC success alone does not create authenticated application contact or suppress health.")
        check(checks, bool(app.get("event_key")) and app.get("application_authenticated") is True and
              app.get("hub_accepted") is True and app.get("health_suppressed") is True,
              "authenticated_event_suppresses_health", "Accepted authenticated event contact suppresses redundant health.")
        check(checks, app.get("pending_event_retired") is False, "piggyback_preserves_pending_event",
              "Health piggyback does not retire an event without its durable application ACK.")

    elif case_id == "GS40-TC03":
        boundaries = {row.get("age_seconds"): row.get("status") for row in sample.get("node_age_boundaries", [])}
        check(checks, sample.get("timeout_seconds") == 910 and boundaries == {909: "ONLINE", 910: "ONLINE", 911: "OFFLINE"},
              "910_second_boundary", "The inclusive lease is online through 910 seconds and offline after expiry.")
        node = sample.get("unavailable_node", {})
        hub = sample.get("unavailable_hub", {})
        wan = sample.get("unavailable_internet", {})
        check(checks, node == {"node": "OFFLINE", "hub": "ONLINE", "wan": "ONLINE"} and
              hub == {"node": "UNKNOWN", "hub": "OFFLINE", "wan": "UNKNOWN"} and
              wan == {"node": "ONLINE", "hub": "ONLINE", "wan": "OFFLINE"},
              "node_hub_wan_distinction", "Node, Hub, and internet availability remain separately classified.")
        unknown = sample.get("unknown_profile", {})
        check(checks, unknown.get("node") == "UNKNOWN" and unknown.get("coverage") == "UNKNOWN" and
              unknown.get("healthy") is False, "unknown_fails_closed", "Unknown identity/profile never appears healthy or covered.")
        physical_disposition = "BLOCKED"

    elif case_id == "GS40-TC04":
        before = sample.get("event_keys_before", [])
        after = sample.get("event_keys_after_rejoin", [])
        counts = sample.get("logical_effects_by_key", {})
        stamps = sample.get("occurred_at_seconds", [])
        check(checks, sample.get("authenticated_rejoin") is True and before == after and len(before) > 0,
              "authenticated_rejoin_preserves_keys", "Authenticated rejoin preserves the exact pending EventKey set.")
        check(checks, sample.get("pending_before") == sample.get("pending_after_rejoin") == len(before),
              "pending_event_conservation", "Rejoin does not clear pending events before authenticated durable ACK.")
        check(checks, sample.get("replay_rejected") is True and all(counts.get(key) == 1 for key in before),
              "replay_and_duplicate_safety", "Replay is rejected and each EventKey has exactly one logical effect.")
        check(checks, stamps == sorted(stamps) and len(stamps) == len(before), "chronological_order",
              "Original event chronology remains ordered across recovery.")
        physical_disposition = "BLOCKED"

    elif case_id == "GS40-TC05":
        actual = [(row.get("profile"), row.get("heartbeat_seconds"), row.get("offline_seconds"), row.get("trusted"))
                  for row in sample.get("profiles", [])]
        expected = [("legacy_60", 60, 190, True), ("legacy_120", 120, 310, True), ("configured", 300, 910, True)]
        check(checks, actual == expected, "mixed_profile_policies", "Legacy 60/190 and 120/310 coexist with configured 300/910.")
        unknown = sample.get("unknown_identity", {})
        check(checks, unknown.get("trusted") is False and unknown.get("profile") is None and
              unknown.get("status") == "UNKNOWN" and unknown.get("healthy") is False,
              "untrusted_identity_unknown", "Unknown or untrusted identity cannot be assigned a healthy profile.")
        check(checks, sample.get("second_physical_node_available") is False, "physical_multi_node_prerequisite",
              "Host compatibility is checked; physical multi-Node acceptance remains blocked without a second Node/fixture.")
        physical_disposition = "BLOCKED"

    elif case_id == "GS40-TC06":
        states = {row.get("name"): row for row in sample.get("states", [])}
        check(checks, states.get("online", {}).get("backend_node") == "ONLINE" and
              states.get("online", {}).get("pwa_coverage") == "COVERED" and
              states.get("online", {}).get("authenticated_contact") is True,
              "online_requires_received_authenticated_contact", "Online/covered is backed by authenticated received contact.")
        check(checks, states.get("offline", {}).get("backend_node") == "OFFLINE" and
              states.get("offline", {}).get("pwa_coverage") == "UNKNOWN" and
              states.get("offline", {}).get("authenticated_contact") is False,
              "offline_coverage_visibility", "Offline sensor coverage is not shown as covered.")
        check(checks, states.get("unknown", {}).get("backend_node") == "UNKNOWN" and
              states.get("unknown", {}).get("pwa_coverage") == "UNKNOWN" and
              sample.get("online_requires_authenticated_received_contact") is True,
              "unknown_coverage_visibility", "Unknown identity/contact remains explicitly unknown.")
        check(checks, sample.get("resident_inactive_does_not_change_node_status") is True,
              "resident_inactivity_is_separate", "Resident inactivity alone does not mark a sensor offline.")
        physical_disposition = "NOT_RUN"

    elif case_id == "GS40-TC07":
        faults = sample.get("side_effects", {})
        decisions = {name: classify_observer_fault(name, sample.get(name, {}).get("evidence", {}))
                     for name in FAULT_CASES}
        check(checks, all(decisions[name]["classification"] == classification
                          for name, classification in FAULT_CASES.items()),
              "fault_classification_matrix", "Identity, absent/stale, busy, transport, truncation, reset, gap, timeout, boot-generation, and wrap faults classify distinctly.")
        check(checks, all(decisions[name]["simulated_initial_open_count"] == sample.get(name, {}).get("expected_open_count") and
                          decisions[name]["stop_immediately"] is True and
                          decisions[name]["preserve_input_evidence"] is True
                          for name in FAULT_CASES), "fail_stop_and_preserve_fault_evidence",
              "Preflight faults stop before open; runtime faults stop after the first simulated observer start and preserve input.")
        check(checks, faults == {"transmit_bytes": 0, "reopen_attempts": 0, "usb_reattach_attempts": 0, "resets_triggered": 0},
              "zero_side_effects", "Mock observer sends no bytes and never retries, reattaches, or resets.")
        c3 = sample.get("c3_usb_sleep_disappearance", {})
        check(checks, c3.get("sleep_entered") is True and c3.get("usb_endpoint_available_after_sleep") is False and
              c3.get("hub_authenticated_health_after_wake") is True and
              c3.get("node_offline_inferred_from_usb_loss") is False and
              classify_c3_usb_loss_during_sleep(c3) == "OBSERVER_LOSS_ONLY" and
              c3.get("classification") == "OBSERVER_LOSS_ONLY", "c3_sleep_usb_disappearance",
              "A sleeping C3 USB endpoint disappearing is observer loss, not proof of Node outage.")
        check(checks, sample.get("every_fault_stops_immediately_and_preserves_input") is True,
              "fail_stop_preserves_capture", "Every injected observation fault stops immediately and preserves source evidence.")
        physical_disposition = "NOT_RUN"

    else:
        raise QualificationError(f"UNKNOWN_CASE:{case_id}")

    return checks, physical_disposition


def classify_capture_lines(lines: list[str], *, max_gap_seconds: float | None = None) -> tuple[str, str]:
    """Classify a replay transcript; never retries, writes, or controls hardware."""
    if not lines:
        return "TRUNCATED_LOG", "No complete capture records were supplied."
    parsed: list[dt.datetime] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return "TRUNCATED_LOG", "A capture line is not complete JSON."
        stamp = record.get("host_utc")
        if stamp:
            try:
                parsed.append(dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                return "TRUNCATED_LOG", "A capture timestamp is invalid."
        if record.get("kind") in {"transport_lost", "transport_error", "usb_disappeared"}:
            return "TRANSPORT_LOSS", f"Capture stopped on {record.get('kind')}."
        if record.get("kind") == "anomaly_stop" and "reset" in str(record.get("reason", "")).lower():
            return "RESET_BANNER", "Reset/boot banner caused the observer to stop."
    if any(right < left for left, right in zip(parsed, parsed[1:])):
        return "TIMESTAMP_GAP", "Capture timestamps moved backwards."
    if max_gap_seconds is not None and any((right - left).total_seconds() > max_gap_seconds
                                           for left, right in zip(parsed, parsed[1:])):
        return "TIMESTAMP_GAP", "Capture exceeds its explicitly configured timestamp-gap limit."
    return "COMPLETE", "Capture records are complete and timestamps are ordered."


def classify_observer_fault(name: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Apply the observation stop policy to injected metadata; performs no I/O."""
    classification = "UNCLASSIFIED"
    if name == "usb_identity_mismatch":
        if evidence.get("expected_usb_identity") != evidence.get("observed_usb_identity"):
            classification = "IDENTITY_MISMATCH"
    elif name == "port_absent_or_stale":
        if evidence.get("path_exists") is not True or evidence.get("mapping_current") is not True:
            classification = "PORT_UNAVAILABLE"
    elif name == "port_busy":
        if evidence.get("exclusive_owner_present") is True:
            classification = "PORT_BUSY"
    elif name == "transport_loss":
        if evidence.get("transport_lost") is True:
            classification = "TRANSPORT_LOSS"
    elif name == "truncated_log":
        if evidence.get("record_complete") is not True:
            classification = "TRUNCATED_LOG"
    elif name == "reset_banner":
        if re.search(r"rst:0x[0-9a-f]+|POWERON|bootloader|panic|abort", str(evidence.get("text", "")), re.I):
            classification = "RESET_BANNER"
    elif name == "timestamp_gap":
        if evidence.get("gap_seconds", 0) > evidence.get("max_gap_seconds", 0):
            classification = "TIMESTAMP_GAP"
    elif name == "timeout":
        if evidence.get("elapsed_seconds", 0) > evidence.get("deadline_seconds", 0):
            classification = "OBSERVATION_TIMEOUT"
    elif name == "boot_generation_change":
        if evidence.get("start_generation") != evidence.get("end_generation"):
            classification = "BOOT_GENERATION_CHANGE"
    elif name == "timestamp_wrap":
        if (evidence.get("boot_generation_start") == evidence.get("boot_generation_end") and
                evidence.get("timestamp_start", 0) > evidence.get("timestamp_end", 0)):
            classification = "TIMESTAMP_WRAP"
    else:
        classification = "UNKNOWN_FAULT"

    return {
        "classification": classification,
        "stop_immediately": classification != "UNCLASSIFIED",
        "simulated_initial_open_count": 0 if name in PREFLIGHT_FAULTS else 1,
        "simulated_write_count": 0,
        "simulated_reopen_count": 0,
        "simulated_usb_reattach_count": 0,
        "simulated_reset_count": 0,
        "preserve_input_evidence": True,
    }


def classify_c3_usb_loss_during_sleep(evidence: dict[str, Any]) -> str:
    """USB visibility is not Node liveness; only accepted Hub contact proves return."""
    if (evidence.get("sleep_entered") is True and
            evidence.get("usb_endpoint_available_after_sleep") is False):
        return "OBSERVER_LOSS_ONLY"
    return "INSUFFICIENT_OBSERVATION"


def analyze_s3_capture(path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise QualificationError(f"REPLAY_INPUT_UNAVAILABLE:{path}:{exc}") from exc
    lines = raw.decode("utf-8", errors="strict").splitlines()
    classification, detail = classify_capture_lines(lines)
    if classification == "TRUNCATED_LOG":
        raise QualificationError(f"REPLAY_{classification}:{detail}")
    records = [json.loads(line) for line in lines]
    text_chunks: list[str] = []
    for record in records:
        if record.get("kind") == "rx" and isinstance(record.get("hex"), str):
            try:
                text_chunks.append(bytes.fromhex(record["hex"]).decode("utf-8", errors="replace"))
            except ValueError as exc:
                raise QualificationError(f"REPLAY_TRUNCATED_LOG: invalid RX hex: {exc}") from exc
    transcript = "\n".join(text_chunks)
    kinds = [row.get("kind") for row in records]
    boot = re.search(r"rst:0x[0-9a-f]+\s+\(([^)]+)\)", transcript, re.I)
    pre = next((row for row in records if row.get("kind") == "usbipd_pre"), {})
    post = next((row for row in reversed(records) if row.get("kind") == "usbipd_post"), {})
    pre_output = str(pre.get("output", ""))
    post_output = str(post.get("output", ""))
    method = next((row for row in records if row.get("kind") == "method"), {})
    capture_end = next((row for row in reversed(records) if row.get("kind") == "capture_end"), {})
    open_attempts = sum(row.get("kind") == "open_attempt_start" for row in records)
    transmit_bytes = sum(int(row.get("transmit_bytes", 0) or 0) for row in records)
    app_evidence = bool(re.search(r"NodeHealth|health_seq|session_id|config_sha|config fingerprint", transcript, re.I))
    checks: list[dict[str, str]] = []
    check(checks, "1a86:55d3" in pre_output and "5CBC401023" in "\n".join(lines),
          "historical_usb_identity", "Historical input identifies CH343 VID:PID 1a86:55d3 / serial 5CBC401023.")
    check(checks, method.get("baud") == 115200 and method.get("dtr_rts_set_false_before_open") is True and
          method.get("app_transmits") is False, "historical_receive_only_setup", "Capture records 115200 receive-only setup with DTR/RTS low requested and no app writes.")
    check(checks, open_attempts == 1 and int(capture_end.get("open_attempts", 0)) == 1 and transmit_bytes == 0,
          "one_historical_open_zero_writes", "Historical capture records at most one open and zero transmitted bytes.")
    check(checks, bool(boot) and ("POWERON" in boot.group(1).upper()) and "anomaly_stop" in kinds and
          capture_end.get("result") == "stopped on anomaly", "reset_banner_fail_stop", "POWERON boot banner was captured and the observer stopped immediately.")
    check(checks, "1a86:55d3" in post_output and "Attached" in post_output,
          "usb_transport_remained_attached", "Post-capture USB/IP snapshot still showed the same CH343 attached.")
    check(checks, not app_evidence, "no_current_application_evidence", "Capture contains no GS-40 config/session/NodeHealth evidence.")
    created = next((row for row in records if row.get("kind") == "capture_created"), {})
    detail_data = {
        "input_path": str(path),
        "input_sha256": sha256(raw),
        "source_jira_comment": "11158",
        "source_capture_sha256": created.get("source_sha256") or sha256(raw),
        "capture_time_utc": created.get("host_utc"),
        "capture_end_utc": next((row.get("host_utc") for row in reversed(records) if row.get("kind") == "capture_end"), None),
        "record_count": len(records),
        "historical_open_attempts": open_attempts,
        "historical_transmit_bytes": transmit_bytes,
        "reset_banner": boot.group(1) if boot else None,
        "reset_cause": "UNPROVEN_SERIAL_OPEN_CAUSALITY",
        "post_usb_state_attached": "1a86:55d3" in post_output and "Attached" in post_output,
        "application_level_gs40_evidence_present": app_evidence,
        "capture_timestamp_classification": classification,
        "capture_timestamp_detail": detail,
    }
    return checks, detail_data


def physical_status(case_id: str) -> tuple[str, str]:
    if case_id == "GS40-TC05":
        return "BLOCKED", "Only one C3 Node is available; mixed-profile physical acceptance needs a second identified Node or approved qualified fixture."
    if case_id == "GS40-TC03":
        return "BLOCKED", "No authorized 910-second Node silence/outage or matched current image/config/session evidence."
    if case_id == "GS40-TC04":
        return "BLOCKED", "No authorized return/rejoin scenario; pre/post pending EventKey baseline and safe observer are unavailable."
    return "NOT_RUN", "No real-target operation was performed in this host/replay execution."


def make_report(case: dict[str, Any], mode: str, verdict: str, checks: list[dict[str, str]], *,
                physical: str, physical_reason: str, input_path: Path | None = None,
                input_hash: str | None = None, replay: dict[str, Any] | None = None,
                failure: str | None = None) -> dict[str, Any]:
    if verdict not in VALID_VERDICTS or physical not in VALID_VERDICTS:
        raise ValueError("invalid verdict")
    config_raw = CONFIG_PATH.read_bytes() if CONFIG_PATH.is_file() else b""
    return {
        "schema_version": 1,
        "run_id": f"gs40-{mode}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "generated_at_utc": utc_now(),
        "test_case_id": case["id"],
        "physical_case_id": case.get("physical_id"),
        "title": case["title"],
        "mode": mode,
        "verdict": verdict,
        "physical_status": physical,
        "physical_blocker": physical_reason,
        "assertions": checks,
        "assertion_count": len(checks),
        "assertions_passed": sum(row.get("result") == "PASS" for row in checks),
        "assertions_failed": sum(row.get("result") == "FAIL" for row in checks),
        "failure": failure,
        "provenance": {
            "kind": "SYNTHETIC_DETERMINISTIC_FIXTURE" if mode == "mock" else
                    "HISTORICAL_CAPTURE_REPLAY" if mode == "replay" else "NO_LIVE_SOURCE",
            "input_path": str(input_path) if input_path else None,
            "input_sha256": input_hash,
            "repository_head": current_head(),
            "repository_branch": current_branch(),
            "qualification_source_fingerprint": source_fingerprint(),
            "repository_config_path": str(CONFIG_PATH.relative_to(REPO)),
            "repository_config_sha256": sha256(config_raw) if config_raw else None,
            "running_c3_image_sha256": None,
            "running_s3_image_sha256": None,
            "effective_running_config_sha256": None,
            "current_node_identity": "UNVERIFIED",
            "current_hub_identity": "UNVERIFIED",
            "current_authenticated_session": "UNVERIFIED",
            "live_observation_source_inventory": (
                inspect_live_observation_sources() if mode == "live" else None),
            "replay": replay,
        },
        "hardware_actions": {
            "serial_open_attempts": 0,
            "transmit_bytes": 0,
            "usb_reattach_attempts": 0,
            "resets_triggered": 0,
            "motion_stimuli": 0,
            "induced_outages": 0,
            "flash_or_nvs_operations": 0,
        },
        "cleanup": "No device handles, subprocesses, or temporary hardware state were created.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['test_case_id']} — {report['title']}",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Mode: `{report['mode']}`",
        f"- Result: **{report['verdict']}**",
        f"- Physical status: **{report['physical_status']}**",
        f"- Physical blocker: {report['physical_blocker']}",
        f"- Provenance: `{report['provenance']['kind']}`",
        f"- Repository HEAD: `{report['provenance']['repository_head']}`",
        f"- Branch: `{report['provenance']['repository_branch']}`",
        f"- Qualification source fingerprint: `{report['provenance']['qualification_source_fingerprint']}`",
        f"- Repository config SHA-256: `{report['provenance']['repository_config_sha256']}`",
        f"- Running C3/S3 image/config/session: `UNVERIFIED`",
        f"- Input: `{report['provenance']['input_path'] or 'none'}`",
        f"- Input SHA-256: `{report['provenance']['input_sha256'] or 'none'}`",
        "",
        "## Assertions",
        "",
        "| Result | Assertion | Detail |",
        "|---|---|---|",
    ]
    for row in report["assertions"]:
        lines.append(f"| {row['result']} | `{row['check']}` | {row['detail']} |")
    if not report["assertions"]:
        lines.append("| BLOCKED | `live_source_preflight` | No approved, verified, non-resetting live telemetry provider is configured. |")
    lines.extend([
        "",
        "## Device action audit",
        "",
        "```json",
        json.dumps(report["hardware_actions"], indent=2),
        "```",
        "",
        "Historical replay is not a current target observation. Synthetic/replay `HOST_PASS` never establishes `PHYSICAL_PASS`.",
        "",
    ])
    return "\n".join(lines)


def write_case_report(directory: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=False)
    stem = report["test_case_id"].lower().replace("-", "_")
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    with markdown_path.open("x", encoding="utf-8") as stream:
        stream.write(render_markdown(report))
    return json_path, markdown_path


def run(mode: str, selected: list[str], *, output_parent: Path, capture_path: Path | None = None) -> tuple[int, Path, list[dict[str, Any]]]:
    registry = load_registry()
    fixture = load_mock_fixture() if mode == "mock" else None
    config = load_json(CONFIG_PATH) if CONFIG_PATH.is_file() else {}
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = output_parent / f"{stamp}_{mode}"
    run_dir.mkdir(parents=True, exist_ok=False)
    cases = {item["id"]: item for item in registry["cases"]}
    reports: list[dict[str, Any]] = []
    overall = 0
    if mode == "replay" and capture_path is None:
        capture_path = CAPTURE_REPLAY_FIXTURE
    for case_id in selected:
        case = cases[case_id]
        checks: list[dict[str, str]] = []
        replay_data = None
        input_path = None
        input_hash = None
        failure = None
        physical, reason = physical_status(case_id)
        verdict = "HOST_PASS"
        try:
            if mode == "mock":
                fixture_raw = MOCK_FIXTURE.read_bytes()
                checks, case_physical = evaluate_mock(case_id, fixture, config)
                input_path = MOCK_FIXTURE
                input_hash = sha256(fixture_raw)
                if case_physical:
                    physical, reason = physical_status(case_id)
            elif mode == "replay":
                if case_id != "GS40-TC07":
                    verdict = "BLOCKED"
                    failure = "NO_HISTORICAL_CAPTURE_FOR_CASE"
                else:
                    input_path = capture_path
                    checks, replay_data = analyze_s3_capture(capture_path)
                    input_hash = replay_data["input_sha256"]
            else:
                source_inventory = inspect_live_observation_sources()
                missing = source_inventory["blockers"]
                verdict = "BLOCKED"
                failure = (
                    "LIVE_SOURCE_CHAIN_INCOMPLETE:" + ",".join(missing) +
                    "; no device/API connection attempted")
                reason = (
                    "Authenticated Hub NodeHealth has no active S3 CloudSync publisher, "
                    "backend ingest/read model, or caregiver PWA projection. "
                    "The host API context is not a production Hub identity provider. "
                    "No device or network access was attempted.")
        except QualificationError as exc:
            verdict = "FAIL" if str(exc).startswith(("INPUT_INVALID", "MOCK_FIXTURE_INVALID", "CASE_REGISTRY_INVALID", "REPLAY_TRUNCATED_LOG")) else "BLOCKED"
            failure = str(exc)
        except (KeyError, TypeError, ValueError) as exc:
            verdict = "FAIL"
            failure = f"ASSERTION_INPUT_INVALID:{exc}"
        if any(row.get("result") == "FAIL" for row in checks):
            verdict = "FAIL"
        report = make_report(case, mode, verdict, checks, physical=physical,
                             physical_reason=reason, input_path=input_path, input_hash=input_hash,
                             replay=replay_data, failure=failure)
        write_case_report(run_dir / case_id, report)
        reports.append(report)
        print(f"{verdict} {case_id} assertions={report['assertions_passed']}/{report['assertion_count']} physical={physical}")
        if verdict == "FAIL":
            overall = 1
        elif verdict in {"BLOCKED", "NOT_RUN"} and overall == 0:
            overall = 3
    index = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "mode": mode,
        "run_directory": str(run_dir),
        "case_count": len(reports),
        "verdict_counts": {value: sum(report["verdict"] == value for report in reports) for value in sorted(VALID_VERDICTS)},
        "physical_status_counts": {value: sum(report["physical_status"] == value for report in reports) for value in sorted(VALID_VERDICTS)},
        "hardware_actions": {"serial_open_attempts": 0, "transmit_bytes": 0, "usb_reattach_attempts": 0,
                             "resets_triggered": 0, "motion_stimuli": 0, "induced_outages": 0, "flash_or_nvs_operations": 0},
    }
    with (run_dir / "run.json").open("x", encoding="utf-8") as stream:
        json.dump(index, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return overall, run_dir, reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("mock", "replay", "live"), default="mock")
    parser.add_argument("--case", default="all", help="GS40-TC01..GS40-TC07 or all")
    parser.add_argument("--output-parent", type=Path,
                        default=REPO / "docs/hw/evidence/GS40_AUTOMATED_QUALIFICATION_20261016/runs")
    parser.add_argument("--capture", type=Path, help="existing JSONL capture to replay; never opened as a device")
    args = parser.parse_args(argv)
    try:
        registry = load_registry()
        cases = [row["id"] for row in registry["cases"]]
        selected = cases if args.case == "all" else [args.case]
        if any(case not in cases for case in selected):
            raise QualificationError("UNKNOWN_CASE_SELECTION")
        if args.mode == "replay" and any(case != "GS40-TC07" for case in selected):
            # Non-TC07 replay reports are explicitly BLOCKED; allow `all` to
            # produce a full disposition matrix when requested.
            if args.case != "all":
                raise QualificationError("REPLAY_ONLY_SUPPORTS_GS40-TC07_OR_ALL")
        result, run_dir, reports = run(args.mode, selected, output_parent=args.output_parent, capture_path=args.capture)
        print(f"GS40 QUALIFICATION: cases={len(reports)} run_dir={run_dir} hardware_actions=NONE")
        return result
    except (QualificationError, OSError) as exc:
        print(f"GS40 QUALIFICATION BLOCKED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
