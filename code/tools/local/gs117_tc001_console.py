#!/usr/bin/env python3
"""Loopback TC-001 controller; never opens a board without a current fixture receipt."""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "code" / "backend"))
from ghar_sajag.identity_namespaces import (
    is_gs179_test_hub_id,
    is_gs179_test_hub_home,
    is_gs179_test_node_id,
    is_physical_hub_id,
    is_physical_node_id,
)
from gs179_verified_endpoint import verify_caregiver_origin_alias, wsl_ipv4

STATE = Path.home() / ".local/state/ghar-sajag/gs117-tc001"
FIXTURE = Path.home() / ".config/ghar-sajag/gs117-tc001/fixture.json"
OBSERVE_APPROVAL = Path.home() / ".config/ghar-sajag/gs117-tc001/read-only-observe-approval.json"
CAMPAIGN_APPROVAL = Path.home() / ".config/ghar-sajag/gs117-tc001/five-run-campaign-approval.json"
MORNING_APPROVAL = Path.home() / ".config/ghar-sajag/gs117-tc001/morning-routine-one-run-approval.json"
ORIGIN = "http://127.0.0.1:18791"
STATUSES = ("NOT_STARTED", "RUNNING", "PASS", "FAIL", "BLOCKED", "PARTIAL", "NOT_VERIFIED", "NOT_IMPLEMENTED")
CAMPAIGN_RUNS = 5
MORNING_STAGES = ("caregiver_network", "applied_household_policy", "enrolled_room_nodes", "trusted_hub_configuration",
                  "fresh_physical_ingress", "hardware_authorization", "hub_rule_decision",
                  "postgres_decision", "caregiver_api", "android_apk")
STAGES = ("environment", "c3_identity", "s3_identity", "c3_injection",
          "node_event_key", "s3_admission", "hub_cloudsync", "backend_commit",
          "postgres_exactly_once", "caregiver_api", "android_apk")
SERIAL = HERE / "gs117_tc001_serial_windows.py"
HEALTH = HERE / "gs179-laptop-server.sh"
BACKEND = HERE / "gs117-tc001-backend.sh"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def stage(report: dict, name: str, status: str, reason: str) -> None:
    assert name in STAGES and status in STATUSES
    report["stages"][name] = {"status": status, "reason": reason, "at": utc()}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_only_observe_approval(path: Path) -> dict:
    """Validate the one-use owner consent without calling it reset-safe."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise ValueError("one_use_read_only_observation_approval_missing_or_consumed") from None
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or
            info.st_uid != os.geteuid()):
        raise ValueError("one_use_observation_approval_must_be_owner_only_regular_file")
    try:
        approval = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("one_use_observation_approval_invalid") from None
    required = {
        "schema_version", "test_id", "profile", "approval_ref", "approval_scope",
        "approved_at", "serial_open_reset_risk_accepted", "reset_safe_uart_verified",
        "motion_injection_authorized", "c3", "s3",
    }
    if (not isinstance(approval, dict) or set(approval) != required or
            approval.get("schema_version") != 1 or approval.get("test_id") != "TC-001" or
            approval.get("profile") != "GS179_TEST_ONLY" or
            approval.get("approval_ref") != "owner-chat-approval-2026-10-26-read-only-observe" or
            approval.get("approval_scope") !=
            "C3 GET_STATE and S3 FIXTURE_STATUS only; one serial-open observation; reset risk accepted" or
            approval.get("serial_open_reset_risk_accepted") is not True or
            approval.get("reset_safe_uart_verified") is not False or
            approval.get("motion_injection_authorized") is not False or
            approval.get("c3") != {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"} or
            approval.get("s3") != {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}):
        raise ValueError("one_use_observation_approval_scope_or_identity_mismatch")
    try:
        approved_at = datetime.fromisoformat(approval["approved_at"])
    except (TypeError, ValueError):
        raise ValueError("one_use_observation_approval_timestamp_invalid") from None
    if approved_at.tzinfo is None or approved_at > datetime.now(timezone.utc):
        raise ValueError("one_use_observation_approval_timestamp_invalid")
    return approval


def exact_fixture() -> dict:
    if not FIXTURE.is_file() or FIXTURE.stat().st_mode & 0o777 != 0o600:
        raise ValueError("owner_only_fixture_approval_and_identity_file_missing")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if (fixture.get("schema_version") != 1 or fixture.get("test_id") != "TC-001" or
            fixture.get("profile") != "GS179_TEST_ONLY" or
            fixture.get("home_id") != "gs177-test-product" or
            fixture.get("logical_node_id") != "bedroom"):
        raise ValueError("owner_only_TC001_fixture_identity_missing_or_mismatched")
    if (not is_gs179_test_hub_home(fixture.get("hub_id"), fixture.get("home_id")) or
            not isinstance(fixture.get("installation_epoch"), int) or
            fixture["installation_epoch"] < 1):
        raise ValueError("TEST_ONLY_Hub_Home_epoch_identity_missing")
    installed_receipts = {}
    for name in ("c3", "s3"):
        board = fixture.get(name, {})
        if (not re.fullmatch(r"COM[0-9]+", board.get("port", "")) or
                not board.get("usb_hwid") or not board.get("serial_number")):
            raise ValueError(name + "_exact_COM_and_USB_identity_missing")
        image = Path(board.get("image", ""))
        receipt = Path(board.get("installed_image_receipt", ""))
        expected = board.get("image_sha256", "")
        if (not image.is_file() or not receipt.is_file() or
                not re.fullmatch(r"[0-9a-f]{64}", expected) or sha256(image) != expected):
            raise ValueError(name + "_image_artifact_mismatch")
        installed = json.loads(receipt.read_text(encoding="utf-8"))
        installed_receipts[name] = installed
        try:
            observed_at = datetime.fromisoformat(installed["observed_at"])
            age = (datetime.now(timezone.utc) - observed_at).total_seconds()
        except (KeyError, TypeError, ValueError):
            raise ValueError(name + "_running_image_observation_time_missing") from None
        if (installed.get("running_image_sha256") != expected or
                installed.get("target") != ("ESP32-C3" if name == "c3" else "ESP32-S3") or
                installed.get("usb_hwid") != board["usb_hwid"] or
                installed.get("serial_number") != board["serial_number"] or
                installed.get("firmware_source_head") != board.get("firmware_source_head") or
                installed.get("installed_at") is None or
                installed.get("active_ota_slot") not in {"factory", "ota_0", "ota_1"} or
                not re.fullmatch(r"[0-9a-f]{64}", installed.get("partition_table_sha256", "")) or
                not isinstance(installed.get("flash_size_bytes"), int) or
                (name == "c3" and installed["flash_size_bytes"] < 4 * 1024 * 1024) or
                (name == "s3" and installed["flash_size_bytes"] != 16 * 1024 * 1024) or
                (name == "s3" and (not isinstance(installed.get("psram_size_bytes"), int) or
                                    installed["psram_size_bytes"] != 8 * 1024 * 1024)) or
                observed_at.tzinfo is None or not 0 <= age <= 86400):
            raise ValueError(name + "_current_installed_image_provenance_missing")
    if fixture["c3"]["port"] == fixture["s3"]["port"]:
        raise ValueError("c3_and_s3_ports_must_differ")
    if (fixture["c3"].get("hil_control") is not True or
            fixture["c3"].get("physical_wake") is not False or
            fixture["c3"].get("hil_build") is not False or
            fixture["s3"].get("full_product_composition") is not True):
        raise ValueError("installed_C3_HIL_or_full_S3_product_profile_unverified")
    physical_device_id = fixture.get("physical_device_id")
    physical_hub_id = fixture.get("hub_id")
    if not is_gs179_test_node_id(physical_device_id):
        raise ValueError("test_only_C3_ownership_identity_missing")
    if is_physical_node_id(physical_device_id) != is_physical_hub_id(physical_hub_id):
        raise ValueError("physical_C3_and_S3_identity_profiles_must_match")
    if is_physical_node_id(physical_device_id):
        if (physical_device_id != "c3-146393c5d158" or
                physical_hub_id != "hub-e072a1d38d34" or
                installed_receipts["c3"].get("permanent_device_id") != physical_device_id or
                installed_receipts["s3"].get("permanent_device_id") != physical_hub_id):
            raise ValueError("physical_MAC_derived_identity_receipts_do_not_match_fixture")
    expected_origin = fixture.get("expected_caregiver_origin", "")
    if not re.fullmatch(r"https://[a-z0-9-]+\.local", expected_origin):
        raise ValueError("TEST_ONLY_caregiver_origin_missing")
    phone_path = Path(fixture.get("phone_install_receipt", ""))
    if not phone_path.is_file():
        raise ValueError("actual_Android_APK_installation_receipt_missing")
    phone = json.loads(phone_path.read_text(encoding="utf-8"))
    try:
        phone_observed = datetime.fromisoformat(phone["observed_at"])
        phone_age = (datetime.now(timezone.utc) - phone_observed).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise ValueError("current_Android_APK_observation_time_missing") from None
    if (phone.get("profile") != "GS179_TEST_ONLY" or
            phone.get("package") not in {"in.gharsajag.caregiver", "in.gharsajag.caregiver.discoverytest"} or
            phone.get("installed") is not True or
            phone.get("home_id") != fixture["home_id"] or
            not re.fullmatch(r"[0-9a-f]{64}", phone.get("signer_sha256", "")) or
            phone_observed.tzinfo is None or not 0 <= phone_age <= 86400):
        raise ValueError("installed_APK_backend_Home_or_signer_unverified")
    adb_serial = phone.get("adb_serial") or phone.get("device_serial")
    if not isinstance(adb_serial, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", adb_serial):
        raise ValueError("actual_Android_ADB_device_identity_receipt_missing")
    if phone.get("backend_origin") != expected_origin:
        tls_dir = Path.home() / ".local/share/ghar-sajag/gs179-laptop/tls/android"
        try:
            fixture["caregiver_origin_verification"] = verify_caregiver_origin_alias(
                expected_origin, phone.get("backend_origin"),
                tls_dir / "ca.pem", tls_dir / "server.pem")
        except (ValueError, OSError):
            raise ValueError("installed_APK_backend_Home_or_signer_unverified") from None
    if not fixture.get("hub_ingress_receipt"):
        raise ValueError("authenticated_persistent_Hub_ingress_receipt_missing")
    ingress = json.loads(Path(fixture["hub_ingress_receipt"]).read_text(encoding="utf-8"))
    try:
        ingress_observed = datetime.fromisoformat(ingress["observed_at"])
        ingress_age = (datetime.now(timezone.utc) - ingress_observed).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise ValueError("current_Hub_ingress_observation_time_missing") from None
    if (ingress.get("profile") != "GS179_TEST_ONLY" or
            ingress.get("home_id") != fixture["home_id"] or
            ingress.get("hub_id") != fixture.get("hub_id") or
            ingress.get("installation_epoch") != fixture.get("installation_epoch") or
            ingress.get("node_device_id") != fixture["physical_device_id"] or
            ingress.get("node_enrollment_verified") is not True or
            not re.fullmatch(r"[0-9a-f]{64}", ingress.get("mtls_client_cert_sha256", "")) or
            not re.fullmatch(r"[0-9a-f]{64}", ingress.get("server_cert_sha256", "")) or
            ingress.get("authenticated_hub_identity") is not True or
            ingress.get("trusted_time_ready") is not True or
            not (ingress.get("persistent_listener_ready") is True or
                 ingress.get("bounded_listener_ready") is True or
                 ingress.get("listener_ready") is True) or
            ingress_observed.tzinfo is None or not 0 <= ingress_age <= 86400):
        raise ValueError("authenticated_Hub_ingress_Home_epoch_or_time_unverified")
    fixture["phone_receipt"] = {
        "adb_serial": adb_serial, "package": phone["package"],
        "version_name": phone.get("version_name") or phone.get("version"),
        "signer_sha256": phone["signer_sha256"], "home_id": phone["home_id"],
        "backend_origin": phone["backend_origin"],
    }
    return fixture


def campaign_approval(path: Path, fixture: dict) -> dict:
    """Validate the one-use owner approval for five reset-risk-aware C3 runs."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise ValueError("five_run_owner_approval_missing") from None
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or
            info.st_uid != os.geteuid()):
        raise ValueError("five_run_approval_must_be_owner_only_regular_file")
    try:
        approval = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("five_run_approval_invalid") from None
    expected = {
        "schema_version": 1,
        "test_id": "TC-001",
        "profile": "GS179_TEST_ONLY",
        "run_count": CAMPAIGN_RUNS,
        "operation": "C3_INJECT_MOTION_FIVE_RUN_CAMPAIGN",
        "home_id": fixture["home_id"],
        "physical_device_id": fixture["physical_device_id"],
        "hub_id": fixture["hub_id"],
        "c3": {"port": fixture["c3"]["port"],
               "serial_number": fixture["c3"]["serial_number"]},
        "s3": {"port": fixture["s3"]["port"],
               "serial_number": fixture["s3"]["serial_number"],
               "uart_open_authorized": False},
        "c3_serial_open_reset_risk_accepted": True,
        "stop_on_first_failure": True,
        "android_auto_verify_each_event": True,
        "firmware_write_authorized": False,
        "commissioning_authorized": False,
        "ownership_or_enrollment_mutation_authorized": False,
        "database_mutation_authorized": False,
    }
    if not isinstance(approval, dict) or any(approval.get(key) != value
                                              for key, value in expected.items()):
        raise ValueError("five_run_approval_scope_or_fixture_mismatch")
    if not isinstance(approval.get("approval_ref"), str) or not approval["approval_ref"].strip():
        raise ValueError("five_run_owner_approval_reference_missing")
    try:
        approved_at = datetime.fromisoformat(approval["approved_at"])
        age = (datetime.now(timezone.utc) - approved_at).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise ValueError("five_run_owner_approval_timestamp_invalid") from None
    if approved_at.tzinfo is None or not 0 <= age <= 86400:
        raise ValueError("five_run_owner_approval_expired_or_future")
    return approval


def morning_run_approval(path: Path, fixture: dict, policy_version: int) -> dict:
    """Validate one Bedroom-only injected run, separately from TC-001 campaign consent."""
    if type(policy_version) is not int or policy_version <= 0:
        raise ValueError("morning_routine_applied_configuration_version_required")
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise ValueError("morning_routine_one_run_owner_approval_missing") from None
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or
            info.st_uid != os.geteuid()):
        raise ValueError("morning_routine_approval_must_be_owner_only_regular_file")
    try:
        approval = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("morning_routine_approval_invalid") from None
    expected = {
        "schema_version": 1, "test_id": "MORNING_ROUTINE",
        "profile": "GS179_TEST_ONLY", "operation": "C3_INJECT_MOTION_ONE_BEDROOM_RUN",
        "run_count": 1, "home_id": fixture["home_id"],
        "hub_id": fixture["hub_id"], "installation_epoch": fixture["installation_epoch"],
        "physical_device_id": fixture["physical_device_id"], "logical_node_id": "bedroom",
        "desired_config_version": policy_version,
        "c3": {"port": fixture["c3"]["port"],
               "serial_number": fixture["c3"]["serial_number"]},
        "s3": {"port": fixture["s3"]["port"],
               "serial_number": fixture["s3"]["serial_number"],
               "uart_open_authorized": False},
        "c3_serial_open_reset_risk_accepted": True,
        "stop_on_first_failure": True,
        "firmware_write_authorized": False, "commissioning_authorized": False,
        "ownership_or_enrollment_mutation_authorized": False,
        "database_mutation_authorized": False,
    }
    if not isinstance(approval, dict) or set(approval) != set(expected) | {
            "approval_ref", "approved_at"} or any(
                approval.get(key) != value for key, value in expected.items()):
        raise ValueError("morning_routine_approval_scope_or_fixture_mismatch")
    if not isinstance(approval.get("approval_ref"), str) or not approval["approval_ref"].strip():
        raise ValueError("morning_routine_approval_reference_missing")
    try:
        approved_at = datetime.fromisoformat(approval["approved_at"])
        age = (datetime.now(timezone.utc) - approved_at).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise ValueError("morning_routine_approval_timestamp_invalid") from None
    if approved_at.tzinfo is None or not 0 <= age <= 86400:
        raise ValueError("morning_routine_approval_expired_or_future")
    return approval


def powershell(action: str, fixture: dict | None = None) -> object:
    script = subprocess.check_output(["wslpath", "-w", str(SERIAL)], text=True, timeout=5).strip()
    payload = {"action": action}
    if action in {"Run", "Observe"}:
        payload.update({name: {key: fixture[name][key] for key in
                               (("port", "usb_hwid", "serial_number", "hil_control", "hil_build",
                                 "physical_wake") if action == "Run" and name == "c3" else
                                ("port", "usb_hwid", "serial_number",))}
                        for name in ("c3", "s3")})
    elif action == "AndroidReady":
        payload["phone"] = fixture
    elif action in {"AndroidVerify", "AndroidVerifyDecision"}:
        payload.update({"phone": fixture["phone_receipt"],
                        "home_id": fixture["home_id"],
                        "backend_origin": fixture["phone_receipt"]["backend_origin"],
                        "event_key": fixture.get("event_key"),
                        "decision_id": fixture.get("decision_id")})
    if action == "Observe":
        payload.update({"query_s3_status": True, "s3_boot_reset": False,
                        "observation_seconds": 10})
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", encoded):
        raise ValueError("invalid_serial_helper_payload")
    command = ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
               "-NoProfile", "-NonInteractive", "-Command",
               'py -3 "' + script + '" "' + encoded + '"']
    timeout = 90 if action in {"AndroidVerify", "AndroidVerifyDecision"} else 50
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
    value = json.loads(result.stdout.strip() or "[]")
    if isinstance(value, dict) and value.get("error"):
        raise ValueError(value["error"])
    return value


def backend(request: dict) -> dict:
    result = subprocess.run(["bash", str(BACKEND)], input=json.dumps(request),
                            capture_output=True, text=True, timeout=18)
    try:
        value = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        raise ValueError("local_backend_read_unavailable") from None
    if result.returncode or value.get("error"):
        raise ValueError(value.get("reason", "local_backend_read_failed"))
    return value


def health() -> dict:
    result = subprocess.run(["bash", str(HEALTH), "health"],
                            capture_output=True, text=True, timeout=20)
    allowed = ("POSTGRES_READY", "CAREGIVER_HTTPS_READY", "LOCAL_BACKEND_READY",
               "LAPTOP_LAN_ENDPOINT_TLS_READY", "LAN_FORWARDING_READY",
               "DEVELOPMENT_ENDPOINT_READY", "HUB_INGRESS_READY")
    data = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in allowed:
            data[key] = value.split()[0]
            if "reason=" in value:
                data[key + "_REASON"] = value.partition("reason=")[2].split()[0]
    data["exit_code"] = result.returncode
    return data


def active_hub_ingress_listener() -> dict:
    """Require the WSL socket and its existing Windows LAN route to be live.

    This is listener readiness only. It does not establish Hub authentication or
    a physical ingress receipt; those remain separately evidenced by the fixture.
    """
    try:
        result = subprocess.run(["ss", "-H", "-ltn"], capture_output=True,
                                text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return {"status": "NOT_VERIFIED", "reason": type(error).__name__,
                "persistent_service": "NOT_INFERRED",
                "authenticated_hub": "NOT_VERIFIED"}
    if result.returncode != 0:
        return {"status": "NOT_VERIFIED", "reason": "listen_table_unavailable",
                "persistent_service": "NOT_INFERRED",
                "authenticated_hub": "NOT_VERIFIED"}
    listeners = []
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 4:
            continue
        local = columns[3]
        if local.rsplit(":", 1)[-1] == "8445":
            listeners.append(local)
    base = {"addresses": listeners,
            "persistent_service": "NOT_INFERRED_FROM_ACTIVE_LISTENER",
            "authenticated_hub": "NOT_VERIFIED",
            "fresh_physical_receipt": "NOT_VERIFIED"}
    if not listeners:
        return {**base, "status": "BLOCKED", "listener": "NOT_LISTENING",
                "reason": "wsl_physical_ingress_listener_not_listening"}

    try:
        current_wsl = wsl_ipv4()
        listener_hosts = {address.rsplit(":", 1)[0].strip("[]") for address in listeners}
        if not listener_hosts.intersection({current_wsl, "0.0.0.0"}):
            return {**base, "status": "BLOCKED", "listener": "MISBOUND",
                    "reason": "wsl_listener_not_bound_to_current_ipv4"}
        script = subprocess.check_output(
            ["wslpath", "-w", str(HERE / "gs179-windows-lan-proxy.ps1")],
            text=True, timeout=5).strip()
        audit_result = subprocess.run(
            ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
             "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", script, "-Action", "Audit", "-EndpointKind",
             "PhysicalHubIngress", "-WslAddress", current_wsl],
            capture_output=True, text=True, timeout=15, check=False)
        if audit_result.returncode != 0:
            raise ValueError("windows_physical_ingress_audit_failed")
        audit = json.loads(audit_result.stdout.strip())
        if not isinstance(audit, dict):
            raise ValueError("windows_physical_ingress_audit_invalid")
        rows_value = audit.get("PortProxyRows", "[]")
        rows = json.loads(rows_value) if isinstance(rows_value, str) else rows_value
        if isinstance(rows, dict):
            rows = [rows]
        wifi = audit.get("WifiAddress")
        mapped = any(
            isinstance(row, dict) and
            row.get("ListenAddress") == wifi and
            row.get("ListenPort") == 8445 and
            row.get("TargetAddress") == current_wsl and
            row.get("TargetPort") == 8445
            for row in rows if isinstance(rows, list))
        listener_count = audit.get("ListenerCount")
        listener_readable = audit.get("ListenerReadStatus") in {
            "READABLE", "READABLE_NETSTAT"}
        route_valid = (
            audit.get("Action") == "Audit" and
            audit.get("EndpointKind") == "PhysicalHubIngress" and
            audit.get("WslAddress") == current_wsl and
            audit.get("NetworkCategory") in {"Private", "DomainAuthenticated"} and
            audit.get("ListenPort") == 8445 and audit.get("TargetPort") == 8445 and
            mapped and listener_readable and type(listener_count) is int and
            listener_count > 0)
        if not route_valid:
            reason = ("windows_physical_ingress_listener_missing" if
                      listener_readable and listener_count == 0 else
                      "windows_physical_ingress_mapping_or_trusted_network_mismatch")
            return {**base, "status": "BLOCKED", "listener": "WSL_ONLY",
                    "wsl_address": current_wsl, "windows_audit": audit,
                    "reason": reason}
        return {**base, "status": "PASS", "listener": "WSL_AND_WINDOWS_ACTIVE",
                "wsl_address": current_wsl, "windows_audit": audit,
                "reason": "current_WSL_listener_and_trusted_Windows_ingress_route_active"}
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError,
            KeyError, TypeError) as error:
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        return {**base, "status": "NOT_VERIFIED", "listener": "WSL_ONLY",
                "reason": reason}


def physical_key(lines: list[str]) -> tuple[int, int] | None:
    if not any("HIL_OK command=INJECT_MOTION" in line for line in lines):
        return None
    candidates = []
    for line in lines:
        match = re.search(r"PIR -> NodeRuntime session=(\d+) seq=(\d+)", line)
        if match:
            candidates.append((int(match[1]), int(match[2])))
    return candidates[0] if len(candidates) == 1 else None


def s3_durable_event(lines: list[str], session: int, sequence: int,
                     physical_device_id: str) -> bool:
    event_id = event_key_text(physical_device_id, session, sequence)
    pattern = re.compile(
        rf"\bAuthenticated event logical=bedroom session={session} seq={sequence} "
        rf"sensor=PIR event=MOTION event_id={re.escape(event_id)} "
        r"room=[A-Za-z0-9 _-]+ ack=0 send=ESP_OK"
    )
    return any(pattern.search(line) for line in lines)


def c3_application_durable_ack(lines: list[str], session: int, sequence: int) -> bool:
    """The Node's authenticated class-0 Application ACK proves Hub durable admission."""
    pattern = re.compile(
        rf"\bApplication ACK session={session} seq={sequence} class=0 retired=1\b")
    return any(pattern.search(line) for line in lines)


def event_key_text(physical_device_id: str, session: int, sequence: int) -> str:
    return (f"p{len(physical_device_id)}:{physical_device_id}"
            f"n7:bedrooms{session}q{sequence}")


def same_https_origin(left: str | None, right: str | None) -> bool:
    try:
        a, b = urlsplit(left or ""), urlsplit(right or "")
        return (a.scheme.casefold() == b.scheme.casefold() == "https" and
                a.hostname is not None and b.hostname is not None and
                a.hostname.casefold() == b.hostname.casefold() and
                (a.port or 443) == (b.port or 443) and
                a.path in {"", "/"} and b.path in {"", "/"} and
                not a.query and not b.query and not a.fragment and not b.fragment)
    except ValueError:
        return False


class Controller:
    def __init__(self):
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        STATE.chmod(0o700)
        self.csrf = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.current: dict | None = None
        self.morning_current: dict | None = None
        self._morning_active_report: dict | None = None
        self._readiness_at = 0.0
        self._readiness_observed_at: str | None = None
        self._readiness: dict = {}

    def readiness(self, force: bool = False) -> dict:
        if force or time.monotonic() - self._readiness_at > 15:
            try:
                observed = health()
            except (OSError, subprocess.SubprocessError) as error:
                observed = {"LOCAL_BACKEND_READY": "FAIL", "reason": type(error).__name__}
            try:
                home = backend({"action": "readiness", "home_id": "gs177-test-product"})
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                home = {"caregiver_home_ready": False,
                        "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}
            hardware = {"status": "NOT_VERIFIED", "c3": "NOT_VERIFIED", "s3": "NOT_VERIFIED",
                        "s3_uart_opened": False,
                        "serial_risk": "COM4 open may reboot the C3; DTR/RTS low is not reset-safe evidence"}
            fixture = None
            try:
                ports = powershell("List")
                if isinstance(ports, dict):
                    ports = [ports]
                hardware["visible_com_ports"] = [item["port"] for item in ports]
                identities = {"c3": "14:63:93:C5:D1:58", "s3": "E0:72:A1:D3:8D:34"}
                for name, identity in identities.items():
                    matches = [item for item in ports
                               if item.get("serial_number", "").casefold() == identity.casefold() and
                               re.search(r"SER=" + re.escape(identity) + r"(?:\s|$)",
                                         item.get("usb_hwid", ""), re.I)]
                    hardware[name] = "PASS" if len(matches) == 1 else "BLOCKED"
                    if len(matches) == 1:
                        hardware[name + "_port"] = matches[0]["port"]
                        hardware[name + "_identity"] = identity
                hardware["status"] = "PARTIAL" if hardware["c3"] == hardware["s3"] == "PASS" else "BLOCKED"
                hardware["reason"] = ("USB descriptors match; no serial port opened during readiness" if
                                       hardware["status"] == "PARTIAL" else
                                       "one or both expected physical USB identities are not uniquely enumerated")
            except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
                hardware["status"] = "BLOCKED"
                hardware["reason"] = str(error) if isinstance(error, ValueError) else type(error).__name__
            fixture_status = {"status": "BLOCKED", "reason": "not_checked"}
            enrollment_status = {"status": "BLOCKED", "reason": "fixture_not_available"}
            morning_approval_status = {"status": "BLOCKED", "reason": "fixture_not_available"}
            approval_status = {"status": "BLOCKED", "reason": "fixture_not_available"}
            android_status = {"status": "NOT_VERIFIED", "reason": "fixture_not_available"}
            try:
                fixture = exact_fixture()
                fixture_status = {"status": "PASS", "reason": "exact owner-only fixture and current receipts verified"}
                try:
                    enrollment = backend({
                        "action": "baseline", "home_id": fixture["home_id"],
                        "physical_device_id": fixture["physical_device_id"],
                        "logical_node_id": "bedroom", "hub_id": fixture["hub_id"],
                        "installation_epoch": fixture["installation_epoch"],
                    })
                    enrollment_status = {
                        "status": "PASS" if enrollment.get("authority_ready") is True else "BLOCKED",
                        "reason": ("current Hub/Home/epoch and Bedroom Node enrollment verified"
                                   if enrollment.get("authority_ready") is True else
                                   "current Hub/Home/epoch or Bedroom Node enrollment is not active"),
                        "enrollment_generation": enrollment.get("enrollment_generation"),
                    }
                except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
                    enrollment_status = {
                        "status": "BLOCKED",
                        "reason": str(error) if isinstance(error, ValueError) else type(error).__name__,
                    }
                try:
                    campaign_approval(CAMPAIGN_APPROVAL, fixture)
                    approval_status = {"status": "PASS", "reason": "one-use five-run approval present; not consumed"}
                except (ValueError, OSError) as error:
                    approval_status = {"status": "BLOCKED", "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}
                try:
                    config = home.get("configuration", {}) if isinstance(home, dict) else {}
                    version = config.get("applied_version") if isinstance(config, dict) else None
                    morning_run_approval(MORNING_APPROVAL, fixture, version)
                    morning_approval_status = {
                        "status": "PASS", "reason": "one-use Bedroom approval is current and fixture/config-bound"}
                except (ValueError, OSError, TypeError) as error:
                    morning_approval_status = {
                        "status": "BLOCKED",
                        "reason": str(error) if isinstance(error, ValueError) else type(error).__name__,
                    }
                try:
                    android_status = powershell("AndroidReady", fixture["phone_receipt"])
                    android_status["reason"] = "approved phone and installed APK package/version verified; no event injected"
                except (ValueError, OSError, subprocess.SubprocessError) as error:
                    android_status = {"status": "BLOCKED", "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}
            except (ValueError, OSError, json.JSONDecodeError) as error:
                fixture_status = {"status": "BLOCKED", "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}
            ingress_status = active_hub_ingress_listener()
            ingress_status["caregiver_health_configured"] = observed.get(
                "HUB_INGRESS_READY", "NOT_REPORTED")
            ingress_status["fixture_identity_time_receipt"] = fixture_status["status"]
            self._readiness = {"backend": observed, "caregiver_home": home,
                               "physical_boards": hardware,
                               "fixture": fixture_status,
                               "physical_enrollment": enrollment_status,
                               "campaign_approval": approval_status,
                               "morning_run_approval": morning_approval_status,
                               "android_apk": android_status,
                               "hub_ingress": ingress_status}
            self._readiness_at = time.monotonic()
            self._readiness_observed_at = utc()
        return self._readiness

    def save(self, report: dict) -> None:
        report["updated_at"] = utc()
        target = STATE / (report["run_id"] + ".json")
        temp = STATE / (report["run_id"] + ".tmp")
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, target)

    @staticmethod
    def recent_morning_reports() -> list[dict]:
        reports = []
        for path in sorted(STATE.glob("MORNING-ROUTINE-*.json"), reverse=True)[:10]:
            try:
                info = path.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                        info.st_mode & 0o077):
                    continue
                report = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(report, dict) and report.get("scenario_id") == "MORNING_ROUTINE":
                    reports.append(report)
            except (OSError, json.JSONDecodeError):
                continue
        return reports

    @staticmethod
    def morning_policy_status(readiness: dict | None = None) -> dict:
        """Show the authenticated TEST_ONLY desired/applied policy without device I/O."""
        readiness = readiness if isinstance(readiness, dict) else {}
        caregiver = readiness.get("caregiver_home", {})
        configuration = (caregiver.get("configuration")
                         if isinstance(caregiver, dict) else None)
        configuration = configuration if isinstance(configuration, dict) else {}
        desired_version = configuration.get("desired_version")
        applied_version = configuration.get("applied_version")
        desired_config = configuration.get("desired_config")
        applied_config = configuration.get("applied_config")
        config_ready = (
            configuration.get("status") == "PASS" and
            configuration.get("source") == "AUTHENTICATED_GS148_TEST_ONLY_SETTINGS" and
            configuration.get("test_only") is True and
            configuration.get("home_id") == "gs177-test-product" and
            configuration.get("schema_version") == 1 and
            type(desired_version) is int and desired_version > 0 and
            type(applied_version) is int and applied_version == desired_version and
            configuration.get("desired_status") == "APPLIED" and
            isinstance(desired_config, dict) and desired_config == applied_config
        )
        if config_ready:
            policy_reason = "authenticated TEST_ONLY Hub acknowledgement confirms the exact desired version"
        elif configuration.get("status") != "PASS":
            policy_reason = str(configuration.get(
                "reason", "authenticated caregiver Settings configuration is unavailable"))
        elif type(desired_version) is not int or desired_version == 0:
            policy_reason = "no household Morning Routine policy has been published"
        else:
            policy_reason = (
                f"desired version {desired_version} is not confirmed applied; "
                f"backend applied version is {applied_version}"
            )

        display_config = applied_config if config_ready else desired_config
        activity_rules = (display_config.get("activity_rules", {})
                          if isinstance(display_config, dict) else {})
        steps = activity_rules.get("morning_steps", []) if isinstance(activity_rules, dict) else []
        enabled_steps = [step for step in steps
                         if isinstance(step, dict) and step.get("enabled") is True]
        enabled_locations = [step.get("location") for step in steps
                             if isinstance(step, dict) and step.get("enabled") is True and
                             isinstance(step.get("location"), str)]
        unavailable_locations = [location for location in enabled_locations
                                 if location.casefold() != "bedroom"]
        physical = readiness.get("physical_boards", {})
        fixture = readiness.get("fixture", {})
        enrollment = readiness.get("physical_enrollment", {})
        morning_window = display_config.get("morning", {}) if isinstance(display_config, dict) else {}
        bedroom_only_policy = (
            isinstance(morning_window, dict) and morning_window.get("enabled") is True and
            len(enabled_steps) == 1 and enabled_steps[0].get("location") == "bedroom" and
            enabled_steps[0].get("required") is True
        )
        room_ready = (config_ready and bedroom_only_policy and not unavailable_locations and
                      enabled_locations == ["bedroom"] and
                      isinstance(physical, dict) and physical.get("c3") == "PASS" and
                      isinstance(fixture, dict) and fixture.get("status") == "PASS" and
                      isinstance(enrollment, dict) and enrollment.get("status") == "PASS")
        if not config_ready:
            fixture_reason = "room enrollment cannot be resolved until an exact policy is confirmed applied"
        elif unavailable_locations:
            fixture_reason = ("no established enrolled physical Node is available for: " +
                              ", ".join(unavailable_locations) +
                              "; the Bedroom Node cannot represent another room")
        elif not bedroom_only_policy:
            fixture_reason = (
                "this first physical Run requires an applied policy with Morning Routine enabled "
                "and Bedroom as its sole enabled required location"
            )
        elif room_ready:
            fixture_reason = "Bedroom resolves to the current enrolled C3 under the owner-only fixture"
        else:
            fixture_reason = (
                "Bedroom is the only established room fixture, but current C3/S3 fixture, "
                "image, JEDEC, enrollment or authenticated ingress evidence is not qualified"
            )
        ingress = readiness.get("hub_ingress", {})
        listener = (ingress.get("status") if isinstance(ingress, dict) else "NOT_VERIFIED")
        ingress_ready = (config_ready and isinstance(fixture, dict) and
                         fixture.get("status") == "PASS" and listener == "PASS" and
                         isinstance(physical, dict) and physical.get("s3") == "PASS")
        return {
            "scenario": "MORNING_ROUTINE",
            "status": "BLOCKED",
            "applied_policy": {
                "status": "PASS" if config_ready else "BLOCKED",
                "reason": policy_reason,
                "source": configuration.get("source"),
                "desired_version": desired_version,
                "desired_status": configuration.get("desired_status"),
                "applied_version": applied_version,
                "schema_version": configuration.get("schema_version"),
                "desired_config": desired_config,
                "applied_config": applied_config,
                "display_config": display_config,
            },
            "room_fixtures": {
                "status": "PASS" if room_ready else "BLOCKED",
                "scenario_policy_ready": bedroom_only_policy,
                "known_established_location": "bedroom",
                "configured_enabled_locations": enabled_locations,
                "unavailable_locations": unavailable_locations,
                "enrollment_verified": isinstance(enrollment, dict) and enrollment.get("status") == "PASS",
                "reason": fixture_reason,
            },
            "hardware_authorization": {
                "status": ("PASS" if readiness.get("morning_run_approval", {}).get("status") == "PASS"
                           else "BLOCKED"),
                "reason": readiness.get("morning_run_approval", {}).get(
                    "reason", "no separate Morning Routine physical-run authorization is available; TC-001 campaign approval is not reusable"),
            },
            "physical_ingress": {
                "status": "PASS" if ingress_ready else "BLOCKED",
                "listener_status": listener,
                "reason": ("current fixture receipt and 8445 listener are present"
                           if ingress_ready else
                           "no fresh authenticated physical S3 receipt is established; listener status alone is not an S3 receipt"),
            },
        }

    def start_morning_routine(self, interval_seconds: object = 10) -> dict | None:
        """Run one Bedroom-only target scenario after every live guard and one-use approval pass."""
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 600:
            raise ValueError("test_stimulus_interval_must_be_1_to_600_seconds")
        if not self.lock.acquire(blocking=False):
            return None
        started = False
        try:
            readiness = self.readiness(force=True)
            policy_status = self.morning_policy_status(readiness)
            fixture = None
            fixture_error = "current_owner_only_fixture_unavailable"
            if readiness.get("fixture", {}).get("status") == "PASS":
                try:
                    fixture = exact_fixture()
                except (ValueError, OSError, json.JSONDecodeError) as error:
                    fixture_error = str(error) if isinstance(error, ValueError) else type(error).__name__

            backend_ready = (readiness.get("backend", {}).get("POSTGRES_READY") == "PASS" and
                             readiness.get("backend", {}).get("CAREGIVER_HTTPS_READY") == "PASS" and
                             readiness.get("backend", {}).get("DEVELOPMENT_ENDPOINT_READY") == "PASS" and
                             readiness.get("caregiver_home", {}).get("caregiver_home_ready") is True)
            caregiver_network_ready = (
                readiness.get("backend", {}).get("POSTGRES_READY") == "PASS" and
                readiness.get("backend", {}).get("CAREGIVER_HTTPS_READY") == "PASS" and
                readiness.get("backend", {}).get("DEVELOPMENT_ENDPOINT_READY") == "PASS" and
                readiness.get("backend", {}).get("LAPTOP_LAN_ENDPOINT_TLS_READY") == "PASS")
            android_ready = readiness.get("android_apk", {}).get("status") == "PASS"
            enrollment_ready = readiness.get("physical_enrollment", {}).get("status") == "PASS"
            policy_ready = policy_status["applied_policy"]["status"] == "PASS"
            rooms_ready = policy_status["room_fixtures"]["status"] == "PASS" and enrollment_ready
            ingress_ready = (policy_status["physical_ingress"]["status"] == "PASS" and
                             readiness.get("hub_ingress", {}).get("status") == "PASS")
            applied_gate_ready = backend_ready and policy_ready
            applied_gate_reason = (policy_status["applied_policy"]["reason"] if backend_ready else
                                   "PostgreSQL, local HTTPS, verified LAN HTTPS forwarding or authenticated Home readiness is unavailable")
            approval = None
            approval_reason = "approval evaluation waits until policy, fixture, enrollment and ingress gates pass"
            if all((backend_ready, android_ready, policy_ready, rooms_ready, ingress_ready)):
                try:
                    if fixture is None:
                        raise ValueError(fixture_error)
                    approval = morning_run_approval(
                        MORNING_APPROVAL, fixture,
                        policy_status["applied_policy"]["applied_version"])
                    approval_reason = "one-use Bedroom Morning Routine approval is valid and fixture-bound"
                except (ValueError, OSError) as error:
                    approval_reason = str(error) if isinstance(error, ValueError) else type(error).__name__

            now = datetime.now(timezone.utc)
            run_id = "MORNING-ROUTINE-" + now.strftime("%Y%m%dT%H%M%S") + "Z-" + secrets.token_hex(4)
            checks = {
                "caregiver_network": (caregiver_network_ready,
                    "PostgreSQL/local HTTPS and certificate-verified laptop LAN HTTPS are ready" if
                    caregiver_network_ready else
                    "local PostgreSQL/HTTPS or certificate-verified laptop LAN HTTPS forwarding is unavailable"),
                "applied_household_policy": (applied_gate_ready, applied_gate_reason),
                "enrolled_room_nodes": (rooms_ready, policy_status["room_fixtures"]["reason"]
                                        if not enrollment_ready else
                                        readiness.get("physical_enrollment", {}).get("reason", "not verified")),
                "trusted_hub_configuration": (policy_ready, policy_status["applied_policy"]["reason"]),
                "hardware_authorization": (approval is not None, approval_reason),
                "fresh_physical_ingress": (ingress_ready, policy_status["physical_ingress"]["reason"]),
            }
            stages = {}
            for name in MORNING_STAGES:
                if name in checks:
                    passed, reason = checks[name]
                    status = "PASS" if passed else "BLOCKED"
                else:
                    status, reason = "NOT_STARTED", "not reached before physical execution"
                stages[name] = {"status": status, "reason": reason, "at": now.isoformat()}
            first = next((name for name in MORNING_STAGES
                          if stages[name]["status"] == "BLOCKED"), None)
            report = {
                "run_id": run_id,
                "scenario_id": "MORNING_ROUTINE",
                "created_at": now.isoformat(),
                "git_head": self._git_head(),
                "readiness_observed_at": self._readiness_observed_at,
                "execution_profile": "REAL_DEVICE_REQUIRED",
                "test_stimulus_interval_seconds": interval_seconds,
                "git_tracked_dirty": self._tracked_dirty(),
                "applied_policy": policy_status["applied_policy"],
                "room_fixtures": policy_status["room_fixtures"],
                "readiness_snapshot": {
                    "postgres": (readiness.get("backend", {}).get("POSTGRES_READY", "NOT_VERIFIED")
                                 if isinstance(readiness.get("backend"), dict) else "NOT_VERIFIED"),
                    "caregiver_https": (readiness.get("backend", {}).get("CAREGIVER_HTTPS_READY", "NOT_VERIFIED")
                                        if isinstance(readiness.get("backend"), dict) else "NOT_VERIFIED"),
                    "physical_boards": ({"status": readiness.get("physical_boards", {}).get("status", "NOT_VERIFIED"),
                                         "c3": readiness.get("physical_boards", {}).get("c3", "NOT_VERIFIED"),
                                         "s3": readiness.get("physical_boards", {}).get("s3", "NOT_VERIFIED")}
                                        if isinstance(readiness.get("physical_boards"), dict) else
                                        {"status": "NOT_VERIFIED", "c3": "NOT_VERIFIED", "s3": "NOT_VERIFIED"}),
                    "owner_fixture": ({"status": readiness.get("fixture", {}).get("status", "NOT_VERIFIED"),
                                       "reason": readiness.get("fixture", {}).get("reason", "not reported")}
                                      if isinstance(readiness.get("fixture"), dict) else
                                      {"status": "NOT_VERIFIED", "reason": "not reported"}),
                    "physical_enrollment": (readiness.get("physical_enrollment", {})
                                            if isinstance(readiness.get("physical_enrollment"), dict) else
                                            {"status": "NOT_VERIFIED", "reason": "not reported"}),
                    "morning_run_approval": (readiness.get("morning_run_approval", {})
                                             if isinstance(readiness.get("morning_run_approval"), dict) else
                                             {"status": "NOT_VERIFIED", "reason": "not reported"}),
                    "android_apk": ({"status": readiness.get("android_apk", {}).get("status", "NOT_VERIFIED"),
                                     "reason": readiness.get("android_apk", {}).get("reason", "not reported")}
                                    if isinstance(readiness.get("android_apk"), dict) else
                                    {"status": "NOT_VERIFIED", "reason": "not reported"}),
                },
                "hardware_authorization": {
                    "status": "PASS" if approval is not None else "BLOCKED",
                    "reason": approval_reason,
                },
                "physical_ingress": policy_status["physical_ingress"],
                "physical_operations": [],
                "planned_operations": ["C3_COM4_INJECT_MOTION_ONCE"],
                "event_keys": [],
                "hub_rule_decision": None,
                "approval_ref": None,
                "first_failing_stage": first,
                "overall": "BLOCKED" if first else "RUNNING",
                "acceptance": "NOT_RUN" if first else "RUNNING",
                "stages": stages,
            }
            self.save(report)
            self.morning_current = report
            if first is None:
                consumed = MORNING_APPROVAL.with_name(
                    MORNING_APPROVAL.stem + ".consumed." +
                    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") +
                    MORNING_APPROVAL.suffix)
                os.rename(MORNING_APPROVAL, consumed)
                os.chmod(consumed, 0o600)
                report["approval_ref"] = approval["approval_ref"]
                report["approval_consumed_at"] = utc()
                self._morning_active_report = report
                self.save(report)
                threading.Thread(target=self.execute_morning_routine,
                                 args=(report, fixture, interval_seconds), daemon=True).start()
                started = True
            return report
        finally:
            if not started and self.lock.locked():
                self.lock.release()

    @staticmethod
    def _morning_mark(report: dict, name: str, status: str, reason: str) -> None:
        report["stages"][name] = {"status": status, "reason": reason, "at": utc()}
        if status in {"FAIL", "BLOCKED"} and report.get("first_failing_stage") is None:
            report["first_failing_stage"] = name

    def execute_morning_routine(self, report: dict, fixture: dict,
                                interval_seconds: int) -> None:
        """Reuse TC-001's real C3 path, then require the Hub decision in DB, API and APK."""
        try:
            approved_version = report.get("applied_policy", {}).get("applied_version")
            readiness = self.readiness(force=True)
            current_policy = self.morning_policy_status(readiness)
            current_fixture = exact_fixture()
            same_fixture = all(
                current_fixture.get(key) == fixture.get(key)
                for key in ("home_id", "hub_id", "installation_epoch", "physical_device_id")
            ) and all(
                current_fixture.get(board, {}).get(key) == fixture.get(board, {}).get(key)
                for board in ("c3", "s3") for key in ("port", "serial_number", "usb_hwid")
            )
            if (not same_fixture or current_policy["applied_policy"].get("status") != "PASS" or
                    current_policy["applied_policy"].get("applied_version") != approved_version or
                    current_policy["room_fixtures"].get("status") != "PASS" or
                    current_policy["physical_ingress"].get("status") != "PASS" or
                    readiness.get("physical_enrollment", {}).get("status") != "PASS" or
                    readiness.get("android_apk", {}).get("status") != "PASS"):
                reason = ("fresh configuration, exact fixture, enrollment, ingress or APK differs "
                          "from the one-use approval snapshot")
                self._morning_mark(report, "trusted_hub_configuration", "BLOCKED", reason)
                report["overall"], report["acceptance"] = "BLOCKED", "NOT_RUN"
                self.save(report)
                return
            fixture = current_fixture
            event_report = {
                "run_id": report["run_id"] + "-NODE-EVENT",
                "test_id": "MORNING_ROUTINE", "started_at": utc(),
                "overall": "PARTIAL", "apk_observation": "NOT_VERIFIED",
                "stages": {name: {"status": "NOT_VERIFIED", "reason": "not reached", "at": utc()}
                           for name in STAGES},
            }
            self.execute(event_report, fixture_override=fixture, release_lock=False)
            report["node_event_run"] = event_report
            if event_report.get("overall") != "PASS":
                failed = next((name for name in STAGES
                               if event_report.get("stages", {}).get(name, {}).get("status") != "PASS"),
                              "environment")
                self._morning_mark(report, "hub_rule_decision", "BLOCKED",
                                   "C3-to-APK motion path did not pass; first motion stage=" + failed)
                for name in MORNING_STAGES[MORNING_STAGES.index("postgres_decision"):]:
                    if report["stages"][name]["status"] == "NOT_STARTED":
                        self._morning_mark(report, name, "NOT_STARTED",
                                           "not reached because the physical motion path did not pass")
                report["overall"] = event_report.get("overall", "BLOCKED")
                report["acceptance"] = "NOT_RUN"
                self.save(report)
                return

            source_key = event_report.get("event_key")
            if (not isinstance(source_key, dict) or source_key.get("logical_node_id") != "bedroom" or
                    source_key.get("physical_device_id") != fixture["physical_device_id"]):
                self._morning_mark(report, "hub_rule_decision", "FAIL",
                                   "fresh C3 EventKey is missing or does not match the approved Bedroom Node")
                report["overall"], report["acceptance"] = "FAIL", "FAIL"
                self.save(report)
                return
            report["event_keys"] = [source_key]
            decision_id = "morning-complete:" + event_key_text(
                fixture["physical_device_id"], source_key["origin_session_id"],
                source_key["event_sequence"])
            report["expected_decision_id"] = decision_id
            query = {
                "action": "morning_decision", "home_id": fixture["home_id"],
                "physical_device_id": fixture["physical_device_id"],
                "logical_node_id": "bedroom", "hub_id": fixture["hub_id"],
                "installation_epoch": fixture["installation_epoch"],
                "origin_session_id": source_key["origin_session_id"],
                "event_sequence": source_key["event_sequence"],
                "decision_id": decision_id,
            }
            decision = {"decision_count": 0, "caregiver_decision_count": 0}
            for _ in range(15):
                decision = backend(query)
                if decision.get("decision_count", 0) != 0:
                    break
                time.sleep(2)
            report["hub_rule_decision"] = decision
            exact_decision = (decision.get("decision_count") == 1 and
                              decision.get("decision_id") == decision_id and
                              decision.get("kind") == "MORNING_ROUTINE_COMPLETED" and
                              decision.get("tone") == "EXPECTED" and
                              decision.get("physical_device_id") == fixture["physical_device_id"] and
                              decision.get("logical_node_id") == "bedroom" and
                              decision.get("origin_session_id") == source_key["origin_session_id"] and
                              decision.get("event_sequence") == source_key["event_sequence"] and
                              decision.get("hub_device_id") == fixture["hub_id"] and
                              decision.get("installation_epoch") == fixture["installation_epoch"])
            if not exact_decision:
                self._morning_mark(report, "hub_rule_decision", "FAIL",
                                   "actual S3 MORNING_ROUTINE_COMPLETED decision is absent, duplicated, or mismatched")
                report["overall"], report["acceptance"] = "FAIL", "FAIL"
                self.save(report)
                return
            self._morning_mark(report, "hub_rule_decision", "PASS",
                               "physical S3 committed the exact configured Bedroom completion decision")
            self._morning_mark(report, "postgres_decision", "PASS",
                               "exact Hub decision has one PostgreSQL row linked to the original C3 EventKey")
            caregiver_decision = decision.get("caregiver_decision")
            if (decision.get("caregiver_decision_count") != 1 or
                    not isinstance(caregiver_decision, dict) or
                    caregiver_decision.get("decision_id") != decision_id or
                    caregiver_decision.get("kind") != "MORNING_ROUTINE_COMPLETED" or
                    caregiver_decision.get("source_type") != "HUB_RULE"):
                self._morning_mark(report, "caregiver_api", "FAIL",
                                   "authenticated caregiver API did not return the exact Hub decision once")
                report["overall"], report["acceptance"] = "FAIL", "FAIL"
                self.save(report)
                return
            self._morning_mark(report, "caregiver_api", "PASS",
                               "authenticated caregiver timeline returned the Hub decision exactly once")
            phone_fixture = dict(fixture)
            phone_fixture["decision_id"] = decision_id
            apk = powershell("AndroidVerifyDecision", phone_fixture)
            screenshot_b64 = apk.pop("screenshot_png_b64", None)
            ui_b64 = apk.pop("ui_hierarchy_xml_b64", None)
            if (apk.get("status") != "PASS" or apk.get("observation") != "AUTOMATED_PASS" or
                    apk.get("decision_id") != decision_id or
                    apk.get("decision_kind") != "MORNING_ROUTINE_COMPLETED" or
                    apk.get("home_id") != fixture["home_id"] or
                    not isinstance(screenshot_b64, str) or not isinstance(ui_b64, str)):
                self._morning_mark(report, "android_apk", "FAIL",
                                   "installed APK did not show the exact Morning Routine decision in Reports")
                report["overall"], report["acceptance"] = "FAIL", "FAIL"
                self.save(report)
                return
            screenshot = base64.b64decode(screenshot_b64, validate=True)
            hierarchy = base64.b64decode(ui_b64, validate=True)
            if (not screenshot.startswith(b"\x89PNG\r\n\x1a\n") or len(screenshot) > 8 * 1024 * 1024 or
                    len(hierarchy) > 2 * 1024 * 1024 or
                    hashlib.sha256(hierarchy).hexdigest() != apk.get("ui_dump_sha256")):
                self._morning_mark(report, "android_apk", "FAIL",
                                   "APK screenshot/accessibility evidence is invalid or failed its digest")
                report["overall"], report["acceptance"] = "FAIL", "FAIL"
                self.save(report)
                return
            screenshot_path = STATE / (report["run_id"] + "-android.png")
            hierarchy_path = STATE / (report["run_id"] + "-android.xml")
            for target, payload in ((screenshot_path, screenshot), (hierarchy_path, hierarchy)):
                with target.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(target, 0o600)
            report["android_evidence"] = {
                "decision_id": decision_id, "decision_kind": "MORNING_ROUTINE_COMPLETED",
                "home_id": fixture["home_id"], "backend_origin": apk.get("backend_origin"),
                "backend_status": apk.get("backend_status"),
                "package": apk.get("package"), "device_serial": apk.get("device_serial"),
                "event_label": apk.get("event_label"),
                "screenshot_file": screenshot_path.name,
                "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
                "ui_hierarchy_file": hierarchy_path.name,
                "ui_hierarchy_sha256": hashlib.sha256(hierarchy).hexdigest(),
            }
            self._morning_mark(report, "android_apk", "PASS",
                               "installed APK Reports displayed the exact Hub decision after refresh")
            report["overall"], report["acceptance"] = "PASS", "TARGET_TEST_INPUT_PASS"
        except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
            stage_name = next((name for name in MORNING_STAGES
                               if report["stages"][name]["status"] == "NOT_STARTED"), "android_apk")
            self._morning_mark(report, stage_name, "BLOCKED",
                               str(error) if isinstance(error, ValueError) else type(error).__name__)
            report["overall"], report["acceptance"] = "BLOCKED", "NOT_RUN"
        finally:
            self.save(report)
            self._morning_active_report = None
            if self.lock.locked():
                self.lock.release()

    @staticmethod
    def _git_head() -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                text=True, timeout=2, stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _tracked_dirty() -> bool | None:
        try:
            return bool(subprocess.check_output(
                ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
                text=True, timeout=2, stderr=subprocess.DEVNULL,
            ).strip())
        except (OSError, subprocess.SubprocessError):
            return None

    def mark(self, report: dict, name: str, status: str, reason: str) -> None:
        stage(report, name, status, reason)
        self.save(report)
        morning = self._morning_active_report
        if (isinstance(morning, dict) and report.get("run_id") ==
                morning.get("run_id", "") + "-NODE-EVENT"):
            morning["node_event_run"] = report
            morning["node_event_stages"] = report["stages"]
            if name == "c3_injection" and status in {"PASS", "FAIL", "BLOCKED"}:
                morning["physical_operations"] = ["C3_COM4_INJECT_MOTION_ATTEMPTED"]
            self.save(morning)
        campaign = self.current
        if campaign is not None and campaign.get("run_id") != report.get("run_id"):
            active = campaign.get("active_run")
            if isinstance(active, dict) and active.get("run_id") == report.get("run_id"):
                campaign["stages"] = report["stages"]
                campaign["event_key"] = report.get("event_key")
                campaign["apk_observation"] = report.get("apk_observation", "NOT_VERIFIED")
                self.save(campaign)

    def save_observation(self, report: dict, path: Path | None = None) -> Path:
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        STATE.chmod(0o700)
        target = path or (STATE / (report["run_id"] + ".json"))
        temp = target.with_suffix(target.suffix + ".tmp")
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, target)
        return target

    def observe_once(self, *, approval_path: Path | None = None,
                     evidence_path: Path | None = None) -> dict:
        """One bounded read-only status query under an explicit reset-risk receipt."""
        if not self.lock.acquire(blocking=False):
            raise ValueError("TC001_OPERATION_ALREADY_RUNNING")
        try:
            approval_path = OBSERVE_APPROVAL if approval_path is None else Path(approval_path)
            report = {
                "run_id": "OBSERVE-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-") + secrets.token_hex(4),
                "test_id": "TC-001", "profile": "GS179_TEST_ONLY",
                "operation": "READ_ONLY_SERIAL_OBSERVATION", "started_at": utc(),
                "overall": "BLOCKED", "tc001_acceptance": "NOT_RUN",
                "serial_open_reset_risk_accepted": True,
                "reset_safe_uart_verified": False, "motion_injection": "NOT_AUTHORIZED",
                "stages": {"approval": "BLOCKED", "identity": "NOT_RUN",
                           "c3_get_state": "NOT_RUN", "s3_fixture_status": "NOT_RUN",
                           "cloudsync": "NOT_VERIFIED"},
            }
            approval = read_only_observe_approval(approval_path)
            report["approval_ref"] = approval["approval_ref"]
            visible = powershell("List")
            if isinstance(visible, dict):
                visible = [visible]
            boards = {}
            for name in ("c3", "s3"):
                expected = approval[name]
                matches = [item for item in visible if
                           item.get("port") == expected["port"] and
                           item.get("serial_number") == expected["serial_number"] and
                           item.get("usb_hwid", "").startswith(
                               "USB VID:PID=303A:1001 SER=" + expected["serial_number"])]
                if len(matches) != 1:
                    raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
                boards[name] = {"port": expected["port"],
                                "serial_number": expected["serial_number"],
                                "usb_hwid": matches[0]["usb_hwid"]}
            report["stages"]["identity"] = "PASS"
            report["devices"] = {name: {"port": board["port"],
                                        "serial_number": board["serial_number"]}
                                 for name, board in boards.items()}

            consumed = approval_path.with_name(
                approval_path.stem + ".consumed." +
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + approval_path.suffix)
            os.rename(approval_path, consumed)
            os.chmod(consumed, 0o600)
            report["approval_consumed_at"] = utc()
            report["approval_receipt_consumed"] = True

            try:
                observed = powershell("Observe", boards)
            except Exception as error:
                report["overall"] = "FAIL"
                report["failure"] = (str(error) if isinstance(error, ValueError)
                                     else type(error).__name__)
                report["completed_at"] = utc()
                self.save_observation(report, evidence_path)
                return report

            c3 = observed.get("c3", []) if isinstance(observed, dict) else []
            s3 = observed.get("s3", []) if isinstance(observed, dict) else []
            report["s3_config_receive_pending"] = (
                observed.get("s3_config_receive_pending") is True
                if isinstance(observed, dict) else False)
            report["s3_status_command_ready"] = (
                observed.get("s3_status_command_ready") is True
                if isinstance(observed, dict) else False)
            report["s3_status_command_sent"] = (
                observed.get("s3_status_command_sent") is True
                if isinstance(observed, dict) else False)
            safe_markers = (
                "ESP-ROM:", "rst:", "boot: Loaded app from partition", "app_init: App version:",
                "app_init: ELF file SHA256:", "HIL_STATE role=c3", "HIL_OK command=GET_STATE",
                "HIL_FIXTURE_STATUS", "HIL_FIXTURE_ERROR", "HIL_FIXTURE_READY",
                "gs_hub_product:", "gs_hub_runtime:", "HubRuntime", "CloudSync",
                "storage", "outbox", "panic", "abort()", "assert failed:",
                "Guru Meditation", "watchdog", "Stack canary", "Stack overflow",
            )
            report["serial_evidence"] = {
                role: [line for line in lines if isinstance(line, str) and
                       any(marker.casefold() in line.casefold() for marker in safe_markers)][:80]
                for role, lines in (("c3", c3), ("s3", s3))
            }
            c3_state = next((line for line in c3 if "HIL_STATE role=c3" in line), "")
            c3_ack = any("HIL_OK command=GET_STATE" in line for line in c3)
            s3_status = next((line for line in s3 if "HIL_FIXTURE_STATUS" in line), "")
            report["c3_power_mode"] = (
                "HIL_AWAKE_TEST_ONLY" if all(marker in c3_state for marker in
                ("power_mode=HIL_AWAKE_TEST_ONLY", "hil_build=0", "hil_control=1",
                 "physical_wake=0")) else "NOT_VERIFIED")
            report["c3_runtime_live"] = bool(re.search(r"\bruntime_live=[1-9][0-9]*\b", c3_state))
            report["c3_sensing_live"] = bool(re.search(r"\bsensing_live=[1-9][0-9]*\b", c3_state))
            report["s3_fixture_state"] = (
                re.search(r"\bstate=([a-z_]+)", s3_status).group(1)
                if re.search(r"\bstate=([a-z_]+)", s3_status) else "NOT_REPORTED")
            report["reset_reason_observed"] = next(
                (line for role in ("c3", "s3") for line in report["serial_evidence"][role]
                 if "rst:" in line), "NOT_OBSERVED")
            report["serial_open_reset_assessment"] = (
                "reset transcript observed; reset may be from power-cycle or port-open"
                if report["reset_reason_observed"] != "NOT_OBSERVED" else
                "no reset transcript observed; this does not prove port-open was reset-free")
            report["stages"]["c3_get_state"] = (
                "PASS" if c3_state and c3_ack else "FAIL")
            report["stages"]["s3_fixture_status"] = "PASS" if s3_status else "NOT_VERIFIED"
            report["stages"]["approval"] = "PASS"
            report["stages"]["cloudsync"] = "NOT_VERIFIED"
            report["overall"] = (
                "PASS" if report["stages"]["c3_get_state"] == "PASS" and
                report["stages"]["s3_fixture_status"] == "PASS" else "PARTIAL")
            report["completed_at"] = utc()
            self.save_observation(report, evidence_path)
            return report
        finally:
            self.lock.release()

    def start(self) -> dict | None:
        if not self.lock.acquire(blocking=False):
            return None
        campaign = {"run_id": datetime.now(timezone.utc).strftime("TC001-CAMPAIGN-%Y%m%dT%H%M%S-") +
                    secrets.token_hex(4), "test_id": "TC-001", "planned_source": "C3_HIL_INJECTED",
                    "planned_runs": CAMPAIGN_RUNS, "completed_runs": 0, "passed_runs": 0,
                    "started_at": utc(), "overall": "PARTIAL", "apk_observation": "NOT_VERIFIED",
                    "runs": [], "stages": {"campaign_preflight": {
                        "status": "NOT_VERIFIED", "reason": "not reached", "at": utc()}}}
        self.current = campaign
        self.save(campaign)
        threading.Thread(target=self.execute_campaign, args=(campaign,), daemon=True).start()
        return campaign

    def execute_campaign(self, campaign: dict) -> None:
        approval_path = CAMPAIGN_APPROVAL
        consumed_path = None
        try:
            readiness = self.readiness(force=True)
            backend_ready = readiness["backend"].get("POSTGRES_READY") == "PASS" and \
                            readiness["backend"].get("CAREGIVER_HTTPS_READY") == "PASS" and \
                            readiness["backend"].get("DEVELOPMENT_ENDPOINT_READY") == "PASS"
            home_ready = readiness["caregiver_home"].get("caregiver_home_ready") is True
            boards_ready = readiness["physical_boards"].get("c3") == "PASS" and \
                           readiness["physical_boards"].get("s3") == "PASS"
            ingress_ready = readiness.get("hub_ingress", {}).get("status") == "PASS"
            if not backend_ready or not home_ready or not boards_ready or \
                    readiness.get("fixture", {}).get("status") != "PASS" or \
                    readiness.get("android_apk", {}).get("status") != "PASS" or not ingress_ready:
                reasons = []
                if not backend_ready:
                    reasons.append("backend/PostgreSQL/local HTTPS or verified LAN HTTPS forwarding unavailable")
                if not home_ready: reasons.append("authorized caregiver Home unavailable")
                if not boards_ready: reasons.append("exact physical USB identities not enumerated")
                if not ingress_ready:
                    reasons.append("GS-179 mTLS listener not currently bound on 8445; " +
                                   readiness.get("hub_ingress", {}).get("reason", "not ready"))
                for field in ("fixture", "android_apk"):
                    if readiness.get(field, {}).get("status") != "PASS":
                        reasons.append(field + ": " + readiness.get(field, {}).get("reason", "not ready"))
                self._campaign_stage(campaign, "campaign_preflight", "BLOCKED", "; ".join(reasons))
                campaign["overall"] = "BLOCKED"
                return
            fixture = exact_fixture()
            approval = campaign_approval(approval_path, fixture)
            self._campaign_stage(campaign, "campaign_preflight", "PASS",
                                  "TEST_ONLY fixture, current backend/Home, both USB identities, and ADB package ready; no board serial opened")
            # One-use approval is consumed only after all static readiness checks
            # pass and immediately before the first C3 serial operation.
            consumed_path = approval_path.with_name(
                approval_path.stem + ".consumed." +
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + approval_path.suffix)
            os.rename(approval_path, consumed_path)
            os.chmod(consumed_path, 0o600)
            campaign["approval_ref"] = approval["approval_ref"]
            campaign["approval_consumed_at"] = utc()
            campaign["reset_safe_uart_verified"] = False
            campaign["c3_serial_open_reset_risk_accepted"] = True
            campaign["s3_serial_opened"] = False
            self.save(campaign)

            for index in range(1, CAMPAIGN_RUNS + 1):
                run_report = {
                    "run_id": campaign["run_id"].replace("TC001-CAMPAIGN-", "TC001-") + f"-{index:02d}",
                    "campaign_id": campaign["run_id"], "run_number": index,
                    "test_id": "TC-001", "planned_source": "C3_HIL_INJECTED",
                    "event_source": "NOT_VERIFIED", "started_at": utc(),
                    "overall": "PARTIAL", "apk_observation": "NOT_VERIFIED",
                    "stages": {name: {"status": "NOT_VERIFIED", "reason": "not reached", "at": utc()}
                               for name in STAGES}}
                campaign["active_run"] = run_report
                campaign["runs"].append(run_report["run_id"])
                self.save(run_report)
                self.save(campaign)
                self.execute(run_report, fixture_override=fixture, release_lock=False)
                campaign["completed_runs"] = index
                if run_report["overall"] == "PASS":
                    campaign["passed_runs"] += 1
                    campaign["apk_observation"] = "AUTOMATED_PASS"
                else:
                    campaign["overall"] = run_report["overall"]
                    campaign["stop_reason"] = f"run_{index}_{run_report['overall'].lower()}"
                    for skipped in range(index + 1, CAMPAIGN_RUNS + 1):
                        campaign.setdefault("not_run", []).append({
                            "run_number": skipped, "status": "NOT_RUN",
                            "reason": "campaign stopped after first non-PASS result"})
                    return
                self.save(campaign)
            campaign["overall"] = "PASS" if campaign["passed_runs"] == CAMPAIGN_RUNS else "PARTIAL"
            campaign["completed_at"] = utc()
        except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
            self._campaign_stage(campaign, "campaign_preflight", "BLOCKED",
                                 str(error) if isinstance(error, ValueError) else type(error).__name__)
            campaign["overall"] = "BLOCKED"
        finally:
            campaign["updated_at"] = utc()
            self.save(campaign)
            if self.lock.locked():
                self.lock.release()

    def _campaign_stage(self, campaign: dict, name: str, status: str, reason: str) -> None:
        campaign["stages"][name] = {"status": status, "reason": reason, "at": utc()}
        self.save(campaign)

    def execute(self, report: dict, *, fixture_override: dict | None = None,
                release_lock: bool = True) -> None:
        try:
            readiness = self.readiness(force=True)
            observed = readiness["backend"]
            if (observed.get("POSTGRES_READY") != "PASS" or
                    observed.get("CAREGIVER_HTTPS_READY") != "PASS" or
                    readiness["caregiver_home"].get("caregiver_home_ready") is not True or
                    readiness.get("android_apk", {}).get("status") != "PASS" or
                    readiness.get("hub_ingress", {}).get("status") != "PASS"):
                self.mark(report, "environment", "BLOCKED",
                          "backend/PostgreSQL, caregiver Home, or approved ADB APK readiness unavailable")
                return
            fixture = fixture_override if fixture_override is not None else exact_fixture()
            if readiness["caregiver_home"].get("backend_origin") != fixture["expected_caregiver_origin"]:
                self.mark(report, "environment", "BLOCKED", "installed_APK_and_caregiver_Home_use_different_backends")
                return
            report["source_head"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=5).strip()
            report["fixture"] = {
                "home_id": fixture["home_id"],
                "hub_id": fixture["hub_id"], "installation_epoch": fixture["installation_epoch"],
                "c3": {"port": fixture["c3"]["port"], "image_sha256": fixture["c3"]["image_sha256"],
                       "firmware_source_head": fixture["c3"]["firmware_source_head"]},
                "s3": {"port": fixture["s3"]["port"], "image_sha256": fixture["s3"]["image_sha256"],
                       "firmware_source_head": fixture["s3"]["firmware_source_head"]},
                "android_package": fixture["phone_receipt"]["package"],
                "android_signer_sha256": fixture["phone_receipt"]["signer_sha256"],
            }
            if "caregiver_origin_verification" in fixture:
                report["caregiver_origin_verification"] = fixture["caregiver_origin_verification"]
            self.mark(report, "environment", "PASS", "TEST_ONLY backend/Home, exact fixture, and installed ADB APK verified")
            ports = powershell("List")
            if isinstance(ports, dict):
                ports = [ports]
            for board, name in (("c3", "c3_identity"), ("s3", "s3_identity")):
                expected = fixture[board]
                if not any(item.get("port") == expected["port"] and
                           item.get("usb_hwid") == expected["usb_hwid"] and
                           item.get("serial_number") == expected["serial_number"] for item in ports):
                    self.mark(report, name, "BLOCKED", "exact COM/USB interface absent or changed")
                    return
                self.mark(report, name, "PASS", "exact COM/USB metadata and current installed-image receipt matched; no S3 UART open")
            request = {"action": "baseline", "home_id": fixture["home_id"],
                       "physical_device_id": fixture["physical_device_id"],
                       "logical_node_id": "bedroom", "hub_id": fixture["hub_id"],
                       "installation_epoch": fixture["installation_epoch"]}
            before = backend(request)
            if before.get("authority_ready") is not True:
                self.mark(report, "environment", "BLOCKED", "current backend Hub/Home/epoch or Node enrollment is not active")
                return
            report["enrollment_generation"] = before["enrollment_generation"]
            serial = powershell("Run", fixture)
            c3 = serial.get("c3", [])
            s3 = serial.get("s3", [])
            if serial.get("s3_serial_opened") is not False or s3:
                self.mark(report, "s3_identity", "FAIL", "serial helper returned S3 UART evidence; S3 UART must remain unopened")
                return
            report["serial_evidence"] = {
                "c3": [line for line in c3 if any(marker in line for marker in
                       ("HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime", "NodeMessage sent", "Application ACK"))][:20],
                "s3_uart_opened": False,
                "s3_admission_source": serial.get("s3_admission_source"),
            }
            mode_line = serial.get("c3_state", "")
            report["c3_power_mode"] = (
                "HIL_AWAKE_TEST_ONLY" if
                "power_mode=HIL_AWAKE_TEST_ONLY" in mode_line and
                "hil_build=0" in mode_line and "hil_control=1" in mode_line and
                "physical_wake=0" in mode_line else "NOT_VERIFIED")
            if report["c3_power_mode"] != "HIL_AWAKE_TEST_ONLY":
                self.mark(report, "c3_injection", "BLOCKED",
                          "installed C3 did not report HIL_AWAKE_TEST_ONLY with active runtime/sensing and empty pending state")
                return
            if not any("HIL_OK command=INJECT_MOTION" in line for line in c3):
                self.mark(report, "c3_injection", "FAIL", "installed C3 did not accept INJECT_MOTION")
                return
            self.mark(report, "c3_injection", "PASS", "physical C3 acknowledged existing HIL command; profile and positive runtime/sensing were checked before injection")
            pair = physical_key(c3)
            if pair is None or list(pair) in before["keys"]:
                self.mark(report, "node_event_key", "FAIL", "one fresh C3 NodeRuntime session/sequence was not observed")
                return
            request.update({"action": "event", "origin_session_id": pair[0],
                            "event_sequence": pair[1]})
            report["event_key"] = {k: request[k] for k in
                                   ("physical_device_id", "logical_node_id",
                                    "origin_session_id", "event_sequence")}
            report["event_source"] = "C3_HIL_INJECTED"
            self.mark(report, "node_event_key", "PASS", "fresh C3 NodeRuntime event after injection")
            if c3_application_durable_ack(c3, *pair):
                self.mark(report, "s3_admission", "PASS", "C3 observed matching authenticated class-0 application ACK; S3 serial was not opened")
            else:
                self.mark(report, "s3_admission", "FAIL", "matching authenticated durable S3 application ACK absent")
                return
            for _ in range(15):
                outcome = backend(request)
                if (outcome.get("durable_count") == 1 and outcome.get("caregiver_count") == 1) or \
                        (isinstance(outcome.get("durable_count"), int) and
                         outcome["durable_count"] > 1):
                    break
                time.sleep(2)
            durable_count = outcome.get("durable_count")
            report["backend_durable_count_observed"] = durable_count
            report["caregiver_count_observed"] = outcome.get("caregiver_count")
            report["duplicate_count"] = (
                max(0, durable_count - 1) if type(durable_count) is int else "NOT_VERIFIED")
            if durable_count == 0:
                self.mark(report, "hub_cloudsync", "NOT_VERIFIED", "no authenticated Hub delivery receipt captured")
                self.mark(report, "backend_commit", "FAIL", "original EventKey absent from persistent backend")
                return
            if type(durable_count) is not int or durable_count < 0:
                self.mark(report, "hub_cloudsync", "NOT_VERIFIED", "backend returned an invalid durable row count")
                self.mark(report, "backend_commit", "NOT_VERIFIED", "PostgreSQL commit count was not a valid integer")
                return
            self.mark(report, "backend_commit", "PASS", "original C3 EventKey has at least one durable PostgreSQL COMMITTED row")
            if durable_count != 1:
                self.mark(report, "postgres_exactly_once", "FAIL",
                          f"durable rows for original EventKey={durable_count}; duplicate rows={report['duplicate_count']}")
                self.mark(report, "hub_cloudsync", "NOT_VERIFIED",
                          "backend duplicate count prevents unambiguous one-commit CloudSync acceptance")
                return
            self.mark(report, "postgres_exactly_once", "PASS",
                      f"durable rows for original EventKey=1; duplicate rows={report['duplicate_count']}")
            if (outcome.get("committing_hub_id") != fixture["hub_id"] or
                    outcome.get("ownership_epoch") != fixture["installation_epoch"] or
                    outcome.get("node_enrollment_generation") != before["enrollment_generation"]):
                self.mark(report, "hub_cloudsync", "FAIL", "durable row lacks exact Hub/Home/epoch/enrollment provenance")
                return
            self.mark(report, "hub_cloudsync", "PASS", "fresh original EventKey committed with exact authenticated physical Hub/Home/epoch/enrollment provenance")
            report["backend_evidence"] = {key: outcome.get(key) for key in
                                          ("durable_count", "caregiver_count", "event_id",
                                           "caregiver_event_id",
                                           "committed_at", "event_kind", "event_location",
                                           "occurred_at", "received_at", "committing_hub_id",
                                           "ownership_epoch", "node_enrollment_generation")}
            if (outcome.get("caregiver_count") != 1 or outcome.get("event_kind") != "MOTION" or
                    outcome.get("caregiver_event_id") != event_key_text(
                        fixture["physical_device_id"], *pair) or
                    str(outcome.get("event_location") or "").casefold() != "bedroom"):
                self.mark(report, "caregiver_api", "FAIL", "authorized Home/room/motion presentation mismatch")
                return
            report["source_freshness"] = outcome.get("source_freshness", "NOT_VERIFIED")
            report["monitoring"] = outcome.get("monitoring", "NOT_VERIFIED")
            self.mark(report, "caregiver_api", "PASS", "authorized TEST_ONLY caregiver API returned original EventKey once; monitoring freshness recorded separately")
            apk_request = {**fixture, "event_key": report["event_key"]}
            apk = powershell("AndroidVerify", apk_request)
            screenshot_b64 = apk.pop("screenshot_png_b64", None)
            ui_hierarchy_b64 = apk.pop("ui_hierarchy_xml_b64", None)
            if (apk.get("status") != "PASS" or apk.get("observation") != "AUTOMATED_PASS" or
                    apk.get("event_key") != report["event_key"] or
                    apk.get("home_id") != fixture["home_id"] or
                    not isinstance(screenshot_b64, str) or
                    not isinstance(ui_hierarchy_b64, str)):
                report["apk_observation"] = "AUTOMATED_FAIL"
                self.mark(report, "android_apk", "FAIL", "actual installed APK did not expose the exact EventKey in Reports/Event details with bounded UI evidence")
                return
            if (not same_https_origin(apk.get("backend_origin"),
                                      fixture["phone_receipt"]["backend_origin"]) or
                    "CONNECTED" not in str(apk.get("backend_status", ""))):
                report["apk_observation"] = "AUTOMATED_FAIL"
                self.mark(report, "android_apk", "FAIL",
                          "actual APK Settings backend origin or authenticated connection differs from the approved receipt")
                return
            try:
                screenshot = base64.b64decode(screenshot_b64, validate=True)
                ui_hierarchy = base64.b64decode(ui_hierarchy_b64, validate=True)
            except ValueError:
                self.mark(report, "android_apk", "FAIL", "Android screenshot or UI hierarchy evidence was not valid base64")
                return
            if not screenshot.startswith(b"\x89PNG\r\n\x1a\n") or len(screenshot) > 8 * 1024 * 1024:
                self.mark(report, "android_apk", "FAIL", "Android screenshot evidence was invalid or exceeded the size bound")
                return
            if (len(ui_hierarchy) > 2 * 1024 * 1024 or
                    hashlib.sha256(ui_hierarchy).hexdigest() != apk.get("ui_dump_sha256")):
                self.mark(report, "android_apk", "FAIL", "Android UI hierarchy exceeded its size limit or failed its digest check")
                return
            screenshot_path = STATE / (report["run_id"] + "-android.png")
            ui_path = STATE / (report["run_id"] + "-android.xml")
            with screenshot_path.open("xb") as stream:
                stream.write(screenshot)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(screenshot_path, 0o600)
            with ui_path.open("xb") as stream:
                stream.write(ui_hierarchy)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(ui_path, 0o600)
            report["apk_observation"] = "AUTOMATED_PASS"
            report["apk_evidence"] = {key: apk.get(key) for key in
                                      ("package", "device_serial", "version_name", "signer_sha256",
                                       "signer_source",
                                       "home_id", "backend_origin", "backend_status", "reports_view",
                                       "event_details_open", "event_key",
                                       "event_label", "logical_node_id", "ui_dump_sha256")}
            report["apk_evidence"]["screenshot_file"] = screenshot_path.name
            report["apk_evidence"]["screenshot_sha256"] = hashlib.sha256(screenshot).hexdigest()
            report["apk_evidence"]["ui_hierarchy_file"] = ui_path.name
            report["apk_evidence"]["ui_hierarchy_sha256"] = hashlib.sha256(ui_hierarchy).hexdigest()
            self.mark(report, "android_apk", "PASS", "actual foreground Parivar Saathi APK Reports/Event details exposed the exact new EventKey; private screenshot saved")
            report["overall"] = "PASS" if all(
                report["stages"][name]["status"] == "PASS" for name in STAGES) else "PARTIAL"
        except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
            target = next((name for name in STAGES if report["stages"][name]["reason"] == "not reached"), "environment")
            self.mark(report, target, "BLOCKED", str(error) if isinstance(error, ValueError) else type(error).__name__)
        finally:
            if any(item["status"] == "FAIL" for item in report["stages"].values()):
                report["overall"] = "FAIL"
            elif any(item["status"] == "BLOCKED" for item in report["stages"].values()):
                report["overall"] = "BLOCKED"
            self.save(report)
            if release_lock and self.lock.locked():
                self.lock.release()


CONTROLLER = Controller()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return  # no request bodies, credentials or query strings in logs

    def reply(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def safe_host(self) -> bool:
        return self.headers.get("Host") == "127.0.0.1:18791"

    def safe_read_origin(self) -> bool:
        origin = self.headers.get("Origin")
        fetch_site = self.headers.get("Sec-Fetch-Site", "").casefold()
        return ((origin is None or origin == ORIGIN) and
                fetch_site not in {"same-site", "cross-site"})

    def do_GET(self):
        if not self.safe_host() or not self.safe_read_origin():
            self.reply(403, {"error": "invalid_host_or_origin"}); return
        if self.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif re.fullmatch(r"/evidence/TC001-[A-Za-z0-9_-]+-android\.png", self.path):
            name = self.path.rsplit("/", 1)[1]
            target = STATE / name
            try:
                info = target.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
                        target.parent.resolve() != STATE.resolve()):
                    raise FileNotFoundError
                body = target.read_bytes()
            except OSError:
                self.reply(404, {"error": "evidence_not_found"}); return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif self.path == "/api/status":
            recent = sorted(STATE.glob("TC001-*.json"), reverse=True)[:10]
            readiness = CONTROLLER.readiness()
            self.reply(200, {"csrf": CONTROLLER.csrf, "current": CONTROLLER.current,
                             "previous": [json.loads(path.read_text()) for path in recent],
                             "running": CONTROLLER.lock.locked(),
                             "morning_routine": CONTROLLER.morning_current,
                             "morning_history": CONTROLLER.recent_morning_reports(),
                             "morning_readiness": CONTROLLER.morning_policy_status(readiness),
                             **readiness})
        elif self.path == "/api/scenarios/morning-routine":
            readiness = CONTROLLER.readiness()
            self.reply(200, {"scenario_id": "MORNING_ROUTINE",
                             "readiness": CONTROLLER.morning_policy_status(readiness),
                             "current": CONTROLLER.morning_current})
        else:
            self.reply(404, {"error": "unknown_route"})

    def do_POST(self):
        if (not self.safe_host() or self.headers.get("Origin") != ORIGIN or
                self.headers.get("X-CSRF-Token") != CONTROLLER.csrf or
                self.headers.get("Content-Type") != "application/json" or
                int(self.headers.get("Content-Length", "0")) > 1024):
            self.reply(403, {"error": "origin_csrf_or_content_type_rejected"}); return
        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except (ValueError, TypeError):
            self.reply(400, {"error": "invalid_json"}); return
        if self.path == "/api/run" and request == {}:
            report = CONTROLLER.start()
            self.reply(202 if report else 409, report or {"error": "test_already_running"})
        elif (self.path == "/api/scenarios/morning-routine/run" and
              isinstance(request, dict) and set(request) <= {"interval_seconds"}):
            try:
                report = CONTROLLER.start_morning_routine(request.get("interval_seconds", 10))
            except ValueError as error:
                self.reply(400, {"error": str(error)}); return
            self.reply(200 if report else 409, report or {"error": "another_scenario_is_running"})
        else:
            self.reply(404, {"error": "unknown_action"})


HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ghar Sajag TC-001</title><style>body{font:16px system-ui;max-width:950px;margin:2rem auto;padding:0 1rem;background:#f7f7f3;color:#18252b}button{padding:.8rem 1rem;background:#13495a;color:white;border:0;border-radius:5px;cursor:pointer;font-weight:700}button:disabled{opacity:.5;cursor:not-allowed}section{background:white;padding:1rem;margin:1rem 0;border-radius:7px}li{margin:.5rem 0}code{overflow-wrap:anywhere}.pass{color:#176b3a}.fail{color:#a12622}img{max-width:100%;max-height:70vh;border:1px solid #ccd4d5;border-radius:5px}</style>
<h1>TC-001 — Bedroom Motion</h1><p>Five consecutive physical C3 HIL injections → physical S3 → GS-179 → actual Parivar Saathi APK. Event provenance: <code>C3_HIL_INJECTED</code>. The campaign stops at the first non-PASS result.</p>
<section><h2>Readiness</h2><pre id="readiness">Loading…</pre><p id="power-mode">C3 power/HIL mode: NOT_VERIFIED</p><p id="reset-risk">COM4 serial-open risk: may reboot C3; COM10 is metadata-only and will not be opened.</p><button id="run" disabled>Run Test — five-event campaign</button><p id="blocked"></p></section>
<section><h2>Current campaign</h2><div id="current">No campaign yet.</div></section>
<section id="morning-routine"><h2>Morning Routine — real-device workflow</h2><p>This scenario uses the household's applied Hub policy and enrolled room Nodes. It does not change household policy. Physical Run stays blocked until the trusted configuration, room fixtures, current S3 ingress, and separate hardware authorization are verified.</p><label for="stimulus-interval">Test stimulus interval (seconds)</label> <input id="stimulus-interval" type="number" min="1" max="600" value="10"><dl><dt>Desired / applied policy version</dt><dd id="morning-version">Unavailable</dd><dt>Included rooms</dt><dd id="morning-included">Unavailable</dd><dt>Required rooms</dt><dd id="morning-required">Unavailable</dd><dt>Optional rooms</dt><dd id="morning-optional">Unavailable</dd></dl><p id="morning-policy">Loading applied household policy…</p><p id="morning-blocked"></p><button id="morning-run">Run Morning Routine</button><div id="morning-current">No Morning Routine attempt yet.</div><h3>Previous attempts</h3><div id="morning-history"></div></section>
<section><h2>Previous evidence</h2><div id="previous"></div></section>
<script>let csrf='',current=null;const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const esc=s=>escape(s);const stageList=x=>'<ol>'+Object.entries(x.stages||{}).map(([k,v])=>{const value=typeof v==='string'?{status:v,reason:''}:v||{};return '<li>'+esc(k)+': <b>'+esc(value.status||'NOT_VERIFIED')+'</b> — '+esc(value.reason||'')+' <small>'+esc(value.at||'')+'</small></li>'}).join('')+'</ol>';
function oneRun(x){if(!x)return '<p>No individual run started.</p>';let key=x.event_key?JSON.stringify(x.event_key):'not observed';let image=x.apk_evidence&&x.apk_evidence.screenshot_file&&/^TC001-[A-Za-z0-9_-]+-android\\.png$/.test(x.apk_evidence.screenshot_file)?'<p><img alt="Private Android APK event evidence" src="/evidence/'+esc(x.apk_evidence.screenshot_file)+'"></p>':'';return '<p><b>'+esc(x.run_id)+'</b> — '+esc(x.overall)+' — APK '+esc(x.apk_observation||'NOT_VERIFIED')+'</p><p>EventKey: <code>'+esc(key)+'</code></p><p>Duplicate durable rows: '+esc(x.duplicate_count??'NOT_VERIFIED')+'</p>'+stageList(x)+image}
function campaign(x){if(!x)return 'No campaign yet.';let active=x.active_run;return '<p><b>'+esc(x.run_id)+'</b> — '+esc(x.overall)+' — '+esc(x.passed_runs||0)+'/'+esc(x.planned_runs||5)+' PASS; '+esc(x.completed_runs||0)+' completed.</p>'+stageList(x)+(active?'<h3>Active or latest individual run</h3>'+oneRun(active):'')+(x.not_run||[]).map(n=>'<p>'+esc(n.run_number)+': '+esc(n.status)+' — '+esc(n.reason)+'</p>').join('')}
async function refresh(){let r=await fetch('/api/status',{cache:'no-store'}),d=await r.json();csrf=d.csrf;current=d.current;const readiness={backend:d.backend,caregiver_home:d.caregiver_home,physical_boards:d.physical_boards,fixture:d.fixture,campaign_approval:d.campaign_approval,hub_ingress:d.hub_ingress,android_apk:d.android_apk};document.getElementById('readiness').textContent=JSON.stringify(readiness,null,2);document.getElementById('power-mode').textContent='C3 power/HIL mode: '+(current&&current.active_run&&current.active_run.c3_power_mode||'HIL_AWAKE_TEST_ONLY profile receipt only; runtime checked before injection');const ready=d.backend&&d.backend.POSTGRES_READY==='PASS'&&d.backend.CAREGIVER_HTTPS_READY==='PASS'&&d.backend.DEVELOPMENT_ENDPOINT_READY==='PASS'&&d.caregiver_home&&d.caregiver_home.caregiver_home_ready===true&&d.physical_boards&&d.physical_boards.c3==='PASS'&&d.physical_boards.s3==='PASS'&&d.fixture&&d.fixture.status==='PASS'&&d.campaign_approval&&d.campaign_approval.status==='PASS'&&d.hub_ingress&&d.hub_ingress.status==='PASS'&&d.android_apk&&d.android_apk.status==='PASS';document.getElementById('run').disabled=!!d.running||!ready;document.getElementById('blocked').textContent=ready?'All software, fixture and device-readiness gates pass. Owner approval will be consumed once before the first COM4 operation.':(d.campaign_approval&&d.campaign_approval.reason)||'Readiness gates are not all PASS.';document.getElementById('current').innerHTML=campaign(current);document.getElementById('previous').innerHTML=d.previous.map(x=>'<details><summary>'+esc(x.run_id)+' — '+esc(x.overall)+'</summary>'+oneRun(x)+(x.runs||[]).map(id=>'<p>Run: '+esc(id)+'</p>').join('')+'</details>').join('')||'No saved runs yet.';}
function morningStages(x){if(!x)return 'No Morning Routine attempt yet.';const nodeStages=x.node_event_stages||{};return '<p><b>'+esc(x.run_id)+'</b> — '+esc(x.overall)+'; acceptance '+esc(x.acceptance)+'</p><p>First blocked stage: <code>'+esc(x.first_failing_stage)+'</code></p><ol>'+Object.entries(x.stages||{}).map(([k,v])=>'<li>'+esc(k)+': <b>'+esc(v.status)+'</b> — '+esc(v.reason)+'</li>').join('')+'</ol><h4>Physical Node event path</h4><ol>'+Object.entries(nodeStages).map(([k,v])=>'<li>'+esc(k)+': <b>'+esc(v.status)+'</b> — '+esc(v.reason)+'</li>').join('')+'</ol><p>Physical operations: '+esc(JSON.stringify(x.physical_operations||[]))+'; EventKeys: '+esc(JSON.stringify(x.event_keys||[]))+'</p>'}
function roomNames(steps,filter){if(!Array.isArray(steps))return 'Unavailable';return steps.filter(s=>s&&s.enabled===true&&(filter==='all'||s.required===(filter==='required'))).map(s=>s.location).join(', ')||'None'}
async function refresh(){let r=await fetch('/api/status',{cache:'no-store'}),d=await r.json();csrf=d.csrf;current=d.current;const readiness={backend:d.backend,caregiver_home:d.caregiver_home,physical_boards:d.physical_boards,fixture:d.fixture,campaign_approval:d.campaign_approval,hub_ingress:d.hub_ingress,android_apk:d.android_apk};document.getElementById('readiness').textContent=JSON.stringify(readiness,null,2);document.getElementById('power-mode').textContent='C3 power/HIL mode: '+(current&&current.active_run&&current.active_run.c3_power_mode||'HIL_AWAKE_TEST_ONLY profile receipt only; runtime checked before injection');const ready=d.backend&&d.backend.POSTGRES_READY==='PASS'&&d.backend.CAREGIVER_HTTPS_READY==='PASS'&&d.backend.DEVELOPMENT_ENDPOINT_READY==='PASS'&&d.caregiver_home&&d.caregiver_home.caregiver_home_ready===true&&d.physical_boards&&d.physical_boards.c3==='PASS'&&d.physical_boards.s3==='PASS'&&d.fixture&&d.fixture.status==='PASS'&&d.campaign_approval&&d.campaign_approval.status==='PASS'&&d.hub_ingress&&d.hub_ingress.status==='PASS'&&d.android_apk&&d.android_apk.status==='PASS';document.getElementById('run').disabled=!!d.running||!ready;document.getElementById('blocked').textContent=ready?'All software, fixture and device-readiness gates pass. Owner approval will be consumed once before the first COM4 operation.':(d.campaign_approval&&d.campaign_approval.reason)||'Readiness gates are not all PASS.';document.getElementById('current').innerHTML=campaign(current);document.getElementById('previous').innerHTML=d.previous.map(x=>'<details><summary>'+esc(x.run_id)+' — '+esc(x.overall)+'</summary>'+oneRun(x)+(x.runs||[]).map(id=>'<p>Run: '+esc(id)+'</p>').join('')+'</details>').join('')||'No saved runs yet.';const mr=d.morning_readiness||{},policy=mr.applied_policy||{},display=policy.display_config||policy.applied_config||policy.desired_config||{},steps=display.activity_rules&&display.activity_rules.morning_steps;document.getElementById('morning-version').textContent=String(policy.desired_version??'Unavailable')+' / '+String(policy.applied_version??'Unavailable');document.getElementById('morning-included').textContent=roomNames(steps,'all');document.getElementById('morning-required').textContent=roomNames(steps,'required');document.getElementById('morning-optional').textContent=roomNames(steps,'optional');document.getElementById('morning-policy').textContent='Desired / applied household configuration: '+(policy.status||'BLOCKED')+' — '+(policy.reason||'unavailable');document.getElementById('morning-blocked').textContent='Caregiver LAN HTTPS: '+((d.backend&&d.backend.LAPTOP_LAN_ENDPOINT_TLS_READY)||'NOT_VERIFIED')+((d.backend&&d.backend.LAPTOP_LAN_ENDPOINT_TLS_READY_REASON)?' ('+d.backend.LAPTOP_LAN_ENDPOINT_TLS_READY_REASON+')':'')+'; '+(mr.room_fixtures&&mr.room_fixtures.reason||'Room fixture status unavailable')+'; '+(mr.hardware_authorization&&mr.hardware_authorization.reason||'hardware authorization unavailable')+'; '+(mr.physical_ingress&&mr.physical_ingress.reason||'physical ingress unavailable');const morningReady=d.backend&&d.backend.POSTGRES_READY==='PASS'&&d.backend.CAREGIVER_HTTPS_READY==='PASS'&&d.backend.DEVELOPMENT_ENDPOINT_READY==='PASS'&&d.caregiver_home&&d.caregiver_home.caregiver_home_ready===true&&d.android_apk&&d.android_apk.status==='PASS'&&d.hub_ingress&&d.hub_ingress.status==='PASS'&&mr.applied_policy&&mr.applied_policy.status==='PASS'&&mr.room_fixtures&&mr.room_fixtures.status==='PASS'&&mr.hardware_authorization&&mr.hardware_authorization.status==='PASS'&&mr.physical_ingress&&mr.physical_ingress.status==='PASS';document.getElementById('morning-run').disabled=!!d.running||!morningReady;document.getElementById('morning-current').innerHTML=morningStages(d.morning_routine);document.getElementById('morning-history').innerHTML=(d.morning_history||[]).map(x=>'<details><summary>'+esc(x.run_id)+' — '+esc(x.overall)+'</summary>'+morningStages(x)+'</details>').join('')||'No saved attempts.';}
async function post(path,payload){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});let data=await r.json();if(!r.ok)alert(data.error||'Request failed');if(path==='/api/scenarios/morning-routine/run'&&r.ok){document.getElementById('morning-current').innerHTML=morningStages(data)}await refresh()}
document.getElementById('run').onclick=()=>post('/api/run',{});document.getElementById('morning-run').onclick=()=>post('/api/scenarios/morning-routine/run',{interval_seconds:Number(document.getElementById('stimulus-interval').value)});refresh();setInterval(refresh,2000);
</script></html>"""


def standing_readiness():
    """Execute only the pinned existing Bootstrap, retaining all target guards."""
    import gs117_hil_authorization as auth
    with auth.session("protected_gs40_bootstrap") as (policy, audit):
        if health().get("exit_code") != 0:
            raise ValueError("standing_readiness_backend_preflight_failed")
        if active_hub_ingress_listener().get("status") != "PASS":
            raise ValueError("standing_readiness_physical_listener_not_ready")
        visible = powershell("List")
        if isinstance(visible, dict): visible = [visible]
        for role in ("c3", "s3"):
            wanted = policy["identity"][role]
            if sum(item.get("port") == wanted["port"] and
                   item.get("serial_number") == wanted["serial_number"] and
                   item.get("usb_hwid", "").startswith("USB VID:PID=303A:1001 SER=" + wanted["serial_number"])
                   for item in visible) != 1:
                raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
        evidence = auth.STATE / ("bootstrap-" + secrets.token_hex(12))
        evidence.mkdir(mode=0o700)
        env = dict(os.environ, GS117_APPROVED_RECOVERY="GS117-S3-RUNTIME-RECOVERY-ONE-ATTEMPT",
                   GS117_RECOVERY_EVIDENCE_DIR=str(evidence))
        result = subprocess.run([sys.executable, policy["bootstrap_script"]["path"]],
                                env=env, capture_output=True, text=True, timeout=150)
        for name, content in (("stdout.json", result.stdout), ("stderr.log", result.stderr)):
            fd = os.open(evidence / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as out: out.write(content)
        audit["evidence"] = str(evidence)
        if result.returncode:
            raise ValueError("standing_readiness_bootstrap_failed_see_private_evidence")
        observed = json.loads(result.stdout)
        c3 = "\n".join(observed.get("c3", []))
        s3 = "\n".join(observed.get("s3", []))
        if any(word in (s3 + c3).lower() for word in ("failed", "unavailable", "reject", "panic", "assert")):
            raise ValueError("standing_readiness_s3_guard_failed_see_private_evidence")
        states = [line for line in observed.get("c3", []) if "HIL_STATE role=c3" in line]
        def fields(line):
            return {key: int(value) for key, value in re.findall(
                r"\b(session|runtime_live|sensing_live)=([0-9]+)\b", line)}
        values = [fields(line) for line in states]
        if len(values) < 2 or any(set(v) != {"session", "runtime_live", "sensing_live"} for v in values):
            raise ValueError("standing_readiness_liveness_progress_not_observed")
        last = values[-1]
        prior = values[-2]
        if (last["session"] != prior["session"] or
            last["runtime_live"] <= prior["runtime_live"] or
            last["sensing_live"] <= prior["sensing_live"] or
            not re.search(r"Authenticated rejoin device=c3-146393c5d158 logical=bedroom session="
                          + str(last["session"]) + r"\b", s3)):
            raise ValueError("standing_readiness_authenticated_liveness_not_verified")
        fixture = exact_fixture()  # Existing independent Home/epoch/time/mTLS/image/phone guards.
        ingress = json.loads(Path(fixture["hub_ingress_receipt"]).read_text())
        if datetime.fromisoformat(ingress["observed_at"]) < datetime.fromisoformat(audit["started_at"]):
            raise ValueError("standing_readiness_requires_new_physical_ingress_receipt")
        if active_hub_ingress_listener().get("status") != "PASS":
            raise ValueError("standing_readiness_physical_listener_not_ready")
        print(json.dumps({"overall": "READY", "evidence": str(evidence),
                          "tc001_campaign": "NOT_AUTHORIZED"}))


if __name__ == "__main__":
    if "--hil-policy-status" in sys.argv:
        import gs117_hil_authorization as auth
        result = auth.status()
        print(json.dumps(result))
        raise SystemExit(0 if result["status"] == "ACTIVE" else 2)
    if "--hil-readiness" in sys.argv:
        try:
            standing_readiness()
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            print(json.dumps({"overall": "BLOCKED", "reason": str(error)}))
            raise SystemExit(2)
    if sys.argv[1:] == ["--observe-once"]:
        try:
            observation = CONTROLLER.observe_once()
            print(json.dumps(observation, sort_keys=True))
            raise SystemExit(0 if observation["overall"] == "PASS" else 2)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            print(json.dumps({"overall": "BLOCKED", "tc001_acceptance": "NOT_RUN",
                              "reason": (str(error) if isinstance(error, ValueError)
                                         else type(error).__name__),
                              "reset_safe_uart_verified": False,
                              "motion_injection": "NOT_AUTHORIZED"}, sort_keys=True))
            raise SystemExit(2)
    server = ThreadingHTTPServer(("127.0.0.1", 18791), Handler)
    print(ORIGIN, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
