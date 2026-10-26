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
from gs179_verified_endpoint import verify_caregiver_origin_alias

STATE = Path.home() / ".local/state/ghar-sajag/gs117-tc001"
FIXTURE = Path.home() / ".config/ghar-sajag/gs117-tc001/fixture.json"
OBSERVE_APPROVAL = Path.home() / ".config/ghar-sajag/gs117-tc001/read-only-observe-approval.json"
CAMPAIGN_APPROVAL = Path.home() / ".config/ghar-sajag/gs117-tc001/five-run-campaign-approval.json"
ORIGIN = "http://127.0.0.1:18791"
STATUSES = ("PASS", "FAIL", "BLOCKED", "PARTIAL", "NOT_VERIFIED")
CAMPAIGN_RUNS = 5
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
    elif action == "AndroidVerify":
        payload.update({"phone": fixture["phone_receipt"],
                        "home_id": fixture["home_id"],
                        "backend_origin": fixture["phone_receipt"]["backend_origin"],
                        "event_key": fixture["event_key"]})
    if action == "Observe":
        payload.update({"query_s3_status": True, "s3_boot_reset": False,
                        "observation_seconds": 10})
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", encoded):
        raise ValueError("invalid_serial_helper_payload")
    command = ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
               "-NoProfile", "-NonInteractive", "-Command",
               'py -3 "' + script + '" "' + encoded + '"']
    timeout = 90 if action == "AndroidVerify" else 50
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
               "LAPTOP_LAN_ENDPOINT_TLS_READY", "HUB_INGRESS_READY")
    data = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in allowed:
            data[key] = value.split()[0]
    data["exit_code"] = result.returncode
    return data


def active_hub_ingress_listener() -> dict:
    """Read the kernel listen table; do not connect to or probe the TLS socket."""
    try:
        result = subprocess.run(["ss", "-H", "-ltn"], capture_output=True,
                                text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return {"status": "NOT_VERIFIED", "reason": type(error).__name__,
                "persistent_service": "NOT_INFERRED"}
    if result.returncode != 0:
        return {"status": "NOT_VERIFIED", "reason": "listen_table_unavailable",
                "persistent_service": "NOT_INFERRED"}
    listeners = []
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 4:
            continue
        local = columns[3]
        if local.rsplit(":", 1)[-1] == "8445":
            listeners.append(local)
    return {"status": "PASS" if listeners else "BLOCKED",
            "listener": "ACTIVE" if listeners else "NOT_LISTENING",
            "addresses": listeners,
            "persistent_service": "NOT_INFERRED_FROM_ACTIVE_LISTENER"}


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
        self._readiness_at = 0.0
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
            approval_status = {"status": "BLOCKED", "reason": "fixture_not_available"}
            android_status = {"status": "NOT_VERIFIED", "reason": "fixture_not_available"}
            try:
                fixture = exact_fixture()
                fixture_status = {"status": "PASS", "reason": "exact owner-only fixture and current receipts verified"}
                try:
                    campaign_approval(CAMPAIGN_APPROVAL, fixture)
                    approval_status = {"status": "PASS", "reason": "one-use five-run approval present; not consumed"}
                except (ValueError, OSError) as error:
                    approval_status = {"status": "BLOCKED", "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}
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
                               "campaign_approval": approval_status,
                               "android_apk": android_status,
                               "hub_ingress": ingress_status}
            self._readiness_at = time.monotonic()
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

    def mark(self, report: dict, name: str, status: str, reason: str) -> None:
        stage(report, name, status, reason)
        self.save(report)
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
                            readiness["backend"].get("CAREGIVER_HTTPS_READY") == "PASS"
            home_ready = readiness["caregiver_home"].get("caregiver_home_ready") is True
            boards_ready = readiness["physical_boards"].get("c3") == "PASS" and \
                           readiness["physical_boards"].get("s3") == "PASS"
            ingress_ready = readiness.get("hub_ingress", {}).get("status") == "PASS"
            if not backend_ready or not home_ready or not boards_ready or \
                    readiness.get("fixture", {}).get("status") != "PASS" or \
                    readiness.get("android_apk", {}).get("status") != "PASS" or not ingress_ready:
                reasons = []
                if not backend_ready: reasons.append("backend/PostgreSQL/caregiver HTTPS unavailable")
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
                             **readiness})
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
        else:
            self.reply(404, {"error": "unknown_action"})


HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ghar Sajag TC-001</title><style>body{font:16px system-ui;max-width:950px;margin:2rem auto;padding:0 1rem;background:#f7f7f3;color:#18252b}button{padding:.8rem 1rem;background:#13495a;color:white;border:0;border-radius:5px;cursor:pointer;font-weight:700}button:disabled{opacity:.5;cursor:not-allowed}section{background:white;padding:1rem;margin:1rem 0;border-radius:7px}li{margin:.5rem 0}code{overflow-wrap:anywhere}.pass{color:#176b3a}.fail{color:#a12622}img{max-width:100%;max-height:70vh;border:1px solid #ccd4d5;border-radius:5px}</style>
<h1>TC-001 — Bedroom Motion</h1><p>Five consecutive physical C3 HIL injections → physical S3 → GS-179 → actual Parivar Saathi APK. Event provenance: <code>C3_HIL_INJECTED</code>. The campaign stops at the first non-PASS result.</p>
<section><h2>Readiness</h2><pre id="readiness">Loading…</pre><p id="power-mode">C3 power/HIL mode: NOT_VERIFIED</p><p id="reset-risk">COM4 serial-open risk: may reboot C3; COM10 is metadata-only and will not be opened.</p><button id="run" disabled>Run Test — five-event campaign</button><p id="blocked"></p></section>
<section><h2>Current campaign</h2><div id="current">No campaign yet.</div></section>
<section><h2>Previous evidence</h2><div id="previous"></div></section>
<script>let csrf='',current=null;const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const esc=s=>escape(s);const stageList=x=>'<ol>'+Object.entries(x.stages||{}).map(([k,v])=>{const value=typeof v==='string'?{status:v,reason:''}:v||{};return '<li>'+esc(k)+': <b>'+esc(value.status||'NOT_VERIFIED')+'</b> — '+esc(value.reason||'')+' <small>'+esc(value.at||'')+'</small></li>'}).join('')+'</ol>';
function oneRun(x){if(!x)return '<p>No individual run started.</p>';let key=x.event_key?JSON.stringify(x.event_key):'not observed';let image=x.apk_evidence&&x.apk_evidence.screenshot_file&&/^TC001-[A-Za-z0-9_-]+-android\\.png$/.test(x.apk_evidence.screenshot_file)?'<p><img alt="Private Android APK event evidence" src="/evidence/'+esc(x.apk_evidence.screenshot_file)+'"></p>':'';return '<p><b>'+esc(x.run_id)+'</b> — '+esc(x.overall)+' — APK '+esc(x.apk_observation||'NOT_VERIFIED')+'</p><p>EventKey: <code>'+esc(key)+'</code></p><p>Duplicate durable rows: '+esc(x.duplicate_count??'NOT_VERIFIED')+'</p>'+stageList(x)+image}
function campaign(x){if(!x)return 'No campaign yet.';let active=x.active_run;return '<p><b>'+esc(x.run_id)+'</b> — '+esc(x.overall)+' — '+esc(x.passed_runs||0)+'/'+esc(x.planned_runs||5)+' PASS; '+esc(x.completed_runs||0)+' completed.</p>'+stageList(x)+(active?'<h3>Active or latest individual run</h3>'+oneRun(active):'')+(x.not_run||[]).map(n=>'<p>'+esc(n.run_number)+': '+esc(n.status)+' — '+esc(n.reason)+'</p>').join('')}
async function refresh(){let r=await fetch('/api/status',{cache:'no-store'}),d=await r.json();csrf=d.csrf;current=d.current;const readiness={backend:d.backend,caregiver_home:d.caregiver_home,physical_boards:d.physical_boards,fixture:d.fixture,campaign_approval:d.campaign_approval,hub_ingress:d.hub_ingress,android_apk:d.android_apk};document.getElementById('readiness').textContent=JSON.stringify(readiness,null,2);document.getElementById('power-mode').textContent='C3 power/HIL mode: '+(current&&current.active_run&&current.active_run.c3_power_mode||'HIL_AWAKE_TEST_ONLY profile receipt only; runtime checked before injection');const ready=d.backend&&d.backend.POSTGRES_READY==='PASS'&&d.backend.CAREGIVER_HTTPS_READY==='PASS'&&d.caregiver_home&&d.caregiver_home.caregiver_home_ready===true&&d.physical_boards&&d.physical_boards.c3==='PASS'&&d.physical_boards.s3==='PASS'&&d.fixture&&d.fixture.status==='PASS'&&d.campaign_approval&&d.campaign_approval.status==='PASS'&&d.hub_ingress&&d.hub_ingress.status==='PASS'&&d.android_apk&&d.android_apk.status==='PASS';document.getElementById('run').disabled=!!d.running||!ready;document.getElementById('blocked').textContent=ready?'All software, fixture and device-readiness gates pass. Owner approval will be consumed once before the first COM4 operation.':(d.campaign_approval&&d.campaign_approval.reason)||'Readiness gates are not all PASS.';document.getElementById('current').innerHTML=campaign(current);document.getElementById('previous').innerHTML=d.previous.map(x=>'<details><summary>'+esc(x.run_id)+' — '+esc(x.overall)+'</summary>'+oneRun(x)+(x.runs||[]).map(id=>'<p>Run: '+esc(id)+'</p>').join('')+'</details>').join('')||'No saved runs yet.';}
async function post(path,payload){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});if(!r.ok)alert((await r.json()).error||'Request failed');await refresh()}
document.getElementById('run').onclick=()=>post('/api/run',{});refresh();setInterval(refresh,2000);
</script></html>"""


if __name__ == "__main__":
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
