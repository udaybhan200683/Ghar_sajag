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
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "code" / "backend"))
from ghar_sajag.identity_namespaces import (
    is_gs179_test_hub_id,
    is_gs179_test_node_id,
    is_physical_hub_id,
    is_physical_node_id,
)

STATE = Path.home() / ".local/state/ghar-sajag/gs117-tc001"
FIXTURE = Path.home() / ".config/ghar-sajag/gs117-tc001/fixture.json"
ORIGIN = "http://127.0.0.1:18791"
STATUSES = ("PASS", "FAIL", "BLOCKED", "PARTIAL", "NOT_VERIFIED")
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


def exact_fixture() -> dict:
    if not FIXTURE.is_file() or FIXTURE.stat().st_mode & 0o777 != 0o600:
        raise ValueError("owner_only_fixture_approval_and_identity_file_missing")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if (fixture.get("schema_version") != 1 or fixture.get("test_id") != "TC-001" or
            fixture.get("profile") != "GS179_TEST_ONLY" or
            fixture.get("home_id") != "gs177-test-product" or
            fixture.get("logical_node_id") != "bedroom" or
            not fixture.get("approval_ref") or
            fixture.get("approval_scope") != "C3 GET_STATE and INJECT_MOTION; C3/S3 UART observation" or
            fixture.get("reset_safe_uart_verified") is not True):
        raise ValueError("fixture_specific_authorization_or_reset_safe_receipt_missing")
    if (not is_gs179_test_hub_id(fixture.get("hub_id")) or
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
        if (installed_receipts["c3"].get("permanent_device_id") != physical_device_id or
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
            phone.get("backend_origin") != expected_origin or
            not re.fullmatch(r"[0-9a-f]{64}", phone.get("signer_sha256", "")) or
            phone_observed.tzinfo is None or not 0 <= phone_age <= 86400):
        raise ValueError("installed_APK_backend_Home_or_signer_unverified")
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
            ingress.get("persistent_listener_ready") is not True or
            ingress_observed.tzinfo is None or not 0 <= ingress_age <= 86400):
        raise ValueError("authenticated_Hub_ingress_Home_epoch_or_time_unverified")
    return fixture


def powershell(action: str, fixture: dict | None = None) -> object:
    script = subprocess.check_output(["wslpath", "-w", str(SERIAL)], text=True, timeout=5).strip()
    payload = {"action": action}
    if action == "Run":
        payload.update({name: {key: fixture[name][key] for key in
                               (("port", "usb_hwid", "serial_number", "hil_control", "hil_build",
                                 "physical_wake") if name == "c3" else
                                ("port", "usb_hwid", "serial_number",))}
                        for name in ("c3", "s3")})
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", encoded):
        raise ValueError("invalid_serial_helper_payload")
    command = ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
               "-NoProfile", "-NonInteractive", "-Command",
               'py -3 "' + script + '" "' + encoded + '"']
    result = subprocess.run(command, capture_output=True, text=True, timeout=50, check=True)
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


def event_key_text(physical_device_id: str, session: int, sequence: int) -> str:
    return (f"p{len(physical_device_id)}:{physical_device_id}"
            f"n7:bedrooms{session}q{sequence}")


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
            hardware = {"status": "NOT_VERIFIED", "c3": "NOT_VERIFIED", "s3": "NOT_VERIFIED"}
            try:
                ports = powershell("List")
                if isinstance(ports, dict):
                    ports = [ports]
                hardware["visible_com_ports"] = [item["port"] for item in ports]
                fixture = exact_fixture()
                for name in ("c3", "s3"):
                    board = fixture[name]
                    hardware[name] = "PASS" if any(
                        item.get("port") == board["port"] and
                        item.get("usb_hwid") == board["usb_hwid"] and
                        item.get("serial_number") == board["serial_number"] for item in ports
                    ) else "BLOCKED"
                hardware["c3_power_mode"] = (
                    "HIL_AWAKE_TEST_ONLY (installed image claimed; runtime NOT_VERIFIED until GET_STATE)"
                    if fixture["c3"].get("hil_control") is True and
                       fixture["c3"].get("hil_build") is False and
                       fixture["c3"].get("physical_wake") is False
                    else "UNSUPPORTED_OR_UNVERIFIED")
                hardware["status"] = "PARTIAL" if hardware["c3"] == hardware["s3"] == "PASS" else "BLOCKED"
                hardware["reason"] = "USB/image receipts matched; live runtime requires authorized Run" if hardware["status"] == "PARTIAL" else "exact board interface absent"
            except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
                hardware["status"] = "BLOCKED"
                hardware["reason"] = str(error) if isinstance(error, ValueError) else type(error).__name__
            self._readiness = {"backend": observed, "caregiver_home": home,
                               "physical_boards": hardware}
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

    def start(self) -> dict | None:
        if not self.lock.acquire(blocking=False):
            return None
        report = {"run_id": datetime.now(timezone.utc).strftime("TC001-%Y%m%dT%H%M%S-") +
                  secrets.token_hex(4), "test_id": "TC-001", "planned_source": "C3_HIL_INJECTED",
                  "event_source": "NOT_VERIFIED",
                  "started_at": utc(), "overall": "PARTIAL", "apk_observation": "NOT_VERIFIED",
                  "stages": {name: {"status": "NOT_VERIFIED", "reason": "not reached"} for name in STAGES}}
        self.current = report
        self.save(report)
        threading.Thread(target=self.execute, args=(report,), daemon=True).start()
        return report

    def execute(self, report: dict) -> None:
        try:
            readiness = self.readiness(force=True)
            observed = readiness["backend"]
            if (observed.get("POSTGRES_READY") != "PASS" or
                    observed.get("CAREGIVER_HTTPS_READY") != "PASS" or
                    readiness["caregiver_home"].get("caregiver_home_ready") is not True):
                stage(report, "environment", "BLOCKED", "local PostgreSQL, caregiver HTTPS or authorized Home unavailable")
                return
            fixture = exact_fixture()
            if readiness["caregiver_home"].get("backend_origin") != fixture["expected_caregiver_origin"]:
                stage(report, "environment", "BLOCKED", "installed_APK_and_caregiver_Home_use_different_backends")
                return
            report["source_head"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=5).strip()
            report["fixture"] = {
                "approval_ref": fixture["approval_ref"], "home_id": fixture["home_id"],
                "hub_id": fixture["hub_id"], "installation_epoch": fixture["installation_epoch"],
                "c3": {"port": fixture["c3"]["port"], "image_sha256": fixture["c3"]["image_sha256"],
                       "firmware_source_head": fixture["c3"]["firmware_source_head"]},
                "s3": {"port": fixture["s3"]["port"], "image_sha256": fixture["s3"]["image_sha256"],
                       "firmware_source_head": fixture["s3"]["firmware_source_head"]},
            }
            stage(report, "environment", "PASS", "TEST_ONLY backend and exact approval receipt present")
            ports = powershell("List")
            if isinstance(ports, dict):
                ports = [ports]
            for board, name in (("c3", "c3_identity"), ("s3", "s3_identity")):
                expected = fixture[board]
                if not any(item.get("port") == expected["port"] and
                           item.get("usb_hwid") == expected["usb_hwid"] and
                           item.get("serial_number") == expected["serial_number"] for item in ports):
                    stage(report, name, "BLOCKED", "exact COM/USB interface absent or changed")
                    return
                stage(report, name, "PASS", "exact COM/USB and installed-image receipt matched")
            request = {"action": "baseline", "home_id": fixture["home_id"],
                       "physical_device_id": fixture["physical_device_id"],
                       "logical_node_id": "bedroom", "hub_id": fixture["hub_id"],
                       "installation_epoch": fixture["installation_epoch"]}
            before = backend(request)
            if before.get("authority_ready") is not True:
                stage(report, "environment", "BLOCKED", "current backend Hub/Home/epoch or Node enrollment is not active")
                return
            report["enrollment_generation"] = before["enrollment_generation"]
            serial = powershell("Run", fixture)
            c3, s3 = serial.get("c3", []), serial.get("s3", [])
            report["serial_evidence"] = {
                "c3": [line for line in c3 if any(marker in line for marker in
                       ("HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime", "NodeMessage sent", "Application ACK"))][:20],
                "s3": [line for line in s3 if "Authenticated event logical=" in line][:20],
            }
            mode_line = next((line for line in c3 if "HIL_STATE role=c3" in line), "")
            report["c3_power_mode"] = (
                "HIL_AWAKE_TEST_ONLY" if
                "power_mode=HIL_AWAKE_TEST_ONLY" in mode_line and
                "hil_build=0" in mode_line and "hil_control=1" in mode_line and
                "physical_wake=0" in mode_line else "NOT_VERIFIED")
            if report["c3_power_mode"] != "HIL_AWAKE_TEST_ONLY":
                stage(report, "c3_injection", "BLOCKED",
                      "installed C3 did not report the required HIL_AWAKE_TEST_ONLY runtime profile")
                return
            if not any("HIL_OK command=INJECT_MOTION" in line for line in c3):
                stage(report, "c3_injection", "FAIL", "installed C3 did not accept INJECT_MOTION")
                return
            stage(report, "c3_injection", "PASS", "physical C3 acknowledged existing HIL command")
            pair = physical_key(c3)
            if pair is None or list(pair) in before["keys"]:
                stage(report, "node_event_key", "FAIL", "one fresh C3 NodeRuntime session/sequence was not observed")
                return
            request.update({"action": "event", "origin_session_id": pair[0],
                            "event_sequence": pair[1]})
            report["event_key"] = {k: request[k] for k in
                                   ("physical_device_id", "logical_node_id",
                                    "origin_session_id", "event_sequence")}
            report["event_source"] = "C3_HIL_INJECTED"
            stage(report, "node_event_key", "PASS", "fresh C3 NodeRuntime event after injection")
            if s3_durable_event(s3, *pair, fixture["physical_device_id"]):
                stage(report, "s3_admission", "PASS", "physical S3 authenticated exact session/sequence and durable ACK")
            else:
                stage(report, "s3_admission", "FAIL", "same EventKey authenticated durable S3 admission absent")
                return
            for _ in range(15):
                outcome = backend(request)
                if outcome.get("durable_count") == 1 and outcome.get("caregiver_count") == 1:
                    break
                time.sleep(2)
            if outcome.get("durable_count") != 1:
                stage(report, "hub_cloudsync", "NOT_VERIFIED", "no authenticated Hub delivery receipt captured")
                stage(report, "backend_commit", "FAIL", "original EventKey absent from persistent backend")
                return
            stage(report, "backend_commit", "PASS", "original C3 EventKey has durable backend row")
            stage(report, "postgres_exactly_once", "PASS", "one durable row for original EventKey")
            if (outcome.get("committing_hub_id") != fixture["hub_id"] or
                    outcome.get("ownership_epoch") != fixture["installation_epoch"] or
                    outcome.get("node_enrollment_generation") != before["enrollment_generation"]):
                stage(report, "hub_cloudsync", "FAIL", "durable row lacks exact Hub/Home/epoch/enrollment provenance")
                return
            stage(report, "hub_cloudsync", "PASS", "fresh original EventKey committed with exact authenticated Hub ownership provenance")
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
                stage(report, "caregiver_api", "FAIL", "authorized Home/room/motion presentation mismatch")
                return
            report["source_freshness"] = outcome.get("source_freshness", "NOT_VERIFIED")
            report["monitoring"] = outcome.get("monitoring", "NOT_VERIFIED")
            stage(report, "caregiver_api", "PASS", "authorized TEST_ONLY Home API returned original EventKey once; source freshness recorded separately")
            stage(report, "android_apk", "NOT_VERIFIED", "awaiting actual phone observation")
        except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
            target = next((name for name in STAGES if report["stages"][name]["reason"] == "not reached"), "environment")
            stage(report, target, "BLOCKED", str(error) if isinstance(error, ValueError) else type(error).__name__)
        finally:
            if any(item["status"] == "FAIL" for item in report["stages"].values()):
                report["overall"] = "FAIL"
            elif any(item["status"] == "BLOCKED" for item in report["stages"].values()):
                report["overall"] = "BLOCKED"
            self.save(report)
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

    def do_GET(self):
        if not self.safe_host():
            self.reply(403, {"error": "invalid_host"}); return
        if self.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
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
        elif self.path == "/api/confirm" and set(request) == {"run_id", "event_key", "seen_in_apk"}:
            report = CONTROLLER.current
            if (report is None or CONTROLLER.lock.locked() or request["run_id"] != report["run_id"] or
                    request["event_key"] != report.get("event_key") or request["seen_in_apk"] is not True or
                    report["stages"]["caregiver_api"]["status"] != "PASS"):
                self.reply(409, {"error": "phone_confirmation_must_match_completed_run"}); return
            stage(report, "android_apk", "PASS", "explicit operator confirmation on actual Android APK")
            report["apk_observation"] = "USER_CONFIRMED"
            report["overall"] = "PARTIAL" if any(report["stages"][name]["status"] != "PASS" for name in STAGES) else "PASS"
            CONTROLLER.save(report)
            self.reply(200, report)
        else:
            self.reply(404, {"error": "unknown_action"})


HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ghar Sajag TC-001</title><style>body{font:16px system-ui;max-width:850px;margin:2rem auto;padding:0 1rem;background:#f7f7f3;color:#18252b}button{padding:.7rem 1rem;background:#13495a;color:white;border:0;border-radius:5px;cursor:pointer}button:disabled{opacity:.5}section{background:white;padding:1rem;margin:1rem 0;border-radius:7px}li{margin:.5rem 0}code{overflow-wrap:anywhere}</style>
<h1>TC-001 — Bedroom Motion</h1><p>Physical C3 HIL stimulus → physical S3 → GS-179 backend → Parivar Saathi Android APK. Sensor source: C3_HIL_INJECTED.</p>
<section><h2>Readiness</h2><pre id="readiness">Loading…</pre><p id="power-mode">C3 power/HIL mode: NOT_VERIFIED</p><button id="run">Run Test</button></section>
<section><h2>Current run</h2><div id="current">No run yet.</div><button id="confirm" disabled>Confirm visible in actual APK</button></section>
<section><h2>Previous runs</h2><div id="previous"></div></section>
<script>let csrf='',current=null;const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function refresh(){let r=await fetch('/api/status',{cache:'no-store'}),d=await r.json();csrf=d.csrf;current=d.current;document.getElementById('readiness').textContent=JSON.stringify({backend:d.backend,caregiver_home:d.caregiver_home,physical_boards:d.physical_boards},null,2);document.getElementById('power-mode').textContent='C3 power/HIL mode: '+(current&&current.c3_power_mode||d.physical_boards&&d.physical_boards.c3_power_mode||'NOT_VERIFIED');document.getElementById('run').disabled=!!d.running;
const show=x=>x?'<p><b>'+escape(x.run_id)+'</b> — '+escape(x.overall)+' — APK '+escape(x.apk_observation)+'</p><p>EventKey: <code>'+escape(JSON.stringify(x.event_key||'not observed'))+'</code></p><ol>'+Object.entries(x.stages).map(([k,v])=>'<li>'+escape(k)+': <b>'+escape(v.status)+'</b> — '+escape(v.reason)+'</li>').join('')+'</ol>':'No run yet.';
document.getElementById('current').innerHTML=show(current);document.getElementById('previous').innerHTML=d.previous.map(x=>'<details><summary>'+escape(x.run_id)+' — '+escape(x.overall)+'</summary>'+show(x)+'</details>').join('');document.getElementById('confirm').disabled=!(current&&current.stages.caregiver_api.status==='PASS'&&current.apk_observation==='NOT_VERIFIED');}
async function post(path,payload){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});if(!r.ok)alert((await r.json()).error);await refresh()}
document.getElementById('run').onclick=()=>post('/api/run',{});document.getElementById('confirm').onclick=()=>{if(current&&confirm('Have you seen this exact new Bedroom Motion event in the correct Home on the actual Parivar Saathi Android APK?'))post('/api/confirm',{run_id:current.run_id,event_key:current.event_key,seen_in_apk:true})};refresh();setInterval(refresh,3000);
</script></html>"""


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 18791), Handler)
    print(ORIGIN, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
