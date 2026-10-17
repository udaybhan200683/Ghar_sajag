"""Authenticated, bounded capture primitives for future GS-68 physical runs.

Importing this module is side-effect free.  USB/serial is opened only by an
explicit physical runner invocation after fixture and approval checks pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_FRAME_BYTES = 16 * 1024
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_OBSERVATION_SECONDS = 900
FRAME_PREFIX = b"GS68/1 "
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CASE_ID = re.compile(r"^GS68-PHY-(00[1-9]|010)$")


class CaptureError(RuntimeError):
    pass


class WindowsPortPreflightError(CaptureError):
    """Windows device/driver policy cannot prove a reset-safe observation."""


class WindowsSerialPlatform:
    """Fail-closed platform seam for a qualified Windows serial provider.

    The stock pySerial/Windows stack cannot prove that CreateFile and its driver
    will leave DTR/RTS unchanged during open. A platform provider must supply
    current PnP identity, process ownership, and an independently qualified
    no-transition open policy before this transport can touch a COM port.
    """
    def inspect_pnp_identity(self, port: str) -> dict | None:
        return None

    def port_owner(self, port: str) -> int | None:
        return None

    def reset_safe_open_policy(self, port: str) -> dict:
        return {"verified": False, "description": "no qualified Windows driver policy"}

    def open_serial(self, port: str, *, baudrate: int, timeout: float,
                    write_timeout: float, flow_control: bool):
        raise WindowsPortPreflightError("no qualified Windows serial provider is installed")

    def take_control_line_events(self, port: str) -> list[dict]:
        return []

    def take_port_events(self, port: str) -> list[dict]:
        return []


class WindowsNativeSerialTransport:
    """Single-open, identity-pinned Windows observation transport.

    This adapter deliberately requires a provider that can prove all of the
    following before opening: exact PnP identity, no competing process, and a
    driver/open policy that does not pulse reset-related control lines. Merely
    setting DTR/RTS low after open is not accepted as proof.
    """
    def __init__(self, port: str, *, expected_port: str, expected_pnp: dict[str, str],
                 platform=None, baudrate: int = 115200):
        if not isinstance(port, str) or not re.fullmatch(r"COM[1-9][0-9]*", port.upper()):
            raise WindowsPortPreflightError("Windows transport requires an explicit COM port")
        required = ("instance_id", "vid", "pid", "serial")
        if not isinstance(expected_pnp, dict) or any(
                not isinstance(expected_pnp.get(key), str) or not expected_pnp[key]
                for key in required):
            raise WindowsPortPreflightError("verified spare PnP identity is incomplete")
        if not 1 <= baudrate <= 1_000_000:
            raise WindowsPortPreflightError("baud rate is outside the bounded range")
        self.port = port.upper()
        if not isinstance(expected_port, str) or expected_port.upper() != self.port:
            raise WindowsPortPreflightError("COM port substitution differs from the approved spare manifest")
        self.expected_pnp = dict(expected_pnp)
        self.platform = platform or WindowsSerialPlatform()
        self.baudrate = baudrate
        self.device = None
        self.disconnected = False
        self.ever_opened = False
        self.control_events: list[dict] = []
        self.opened_monotonic_ns: int | None = None

    def open(self):
        if self.ever_opened:
            raise WindowsPortPreflightError("Windows serial port may be opened only once per session")
        if sys.platform != "win32" and isinstance(self.platform, WindowsSerialPlatform):
            raise WindowsPortPreflightError("Windows-native transport is unavailable on this host")
        observed = self.platform.inspect_pnp_identity(self.port)
        if not isinstance(observed, dict) or any(
                observed.get(key) != value for key, value in self.expected_pnp.items()):
            raise WindowsPortPreflightError("COM port PnP identity does not match the designated spare")
        owner = self.platform.port_owner(self.port)
        if owner is None:
            raise WindowsPortPreflightError("COM port ownership could not be checked")
        if owner:
            raise WindowsPortPreflightError("COM port is owned by another process")
        policy = self.platform.reset_safe_open_policy(self.port)
        if not isinstance(policy, dict) or policy.get("verified") is not True or not policy.get("description"):
            raise WindowsPortPreflightError("Windows driver cannot prove reset-safe port opening")
        # The provider, not pySerial line-state requests, is responsible for
        # proving no DTR/RTS transition occurs during CreateFile/open.
        self.control_events.append({"operation": "open_policy", "result": "verified",
                                    "description": str(policy["description"]),
                                    "monotonic_ns": time.monotonic_ns()})
        try:
            self.device = self.platform.open_serial(self.port, baudrate=self.baudrate,
                timeout=0.2, write_timeout=1.0, flow_control=False)
        except Exception as error:
            self.control_events.append({"operation": "open", "result": "failed",
                                        "error_type": type(error).__name__,
                                        "monotonic_ns": time.monotonic_ns()})
            self.ever_opened = True
            raise WindowsPortPreflightError("Windows serial open failed; reconnect is forbidden") from error
        self.ever_opened = True
        self.opened_monotonic_ns = time.monotonic_ns()
        self.control_events.append({"operation": "open", "result": "success",
                                    "monotonic_ns": self.opened_monotonic_ns})
        self._record_control_line_events()
        self._record_port_events("open")

    def write(self, payload: bytes):
        if self.device is None:
            raise CaptureError("Windows serial transport is not open")
        if not isinstance(payload, bytes) or len(payload) > MAX_FRAME_BYTES:
            raise CaptureError("Windows serial write exceeds bound")
        written = self.device.write(payload)
        self.device.flush()
        if written != len(payload):
            raise CaptureError("short Windows serial write")

    def read_line(self, timeout: float) -> bytes:
        if self.device is None:
            raise CaptureError("Windows serial transport is not open")
        deadline = time.monotonic() + min(max(timeout, 0.05), 30.0)
        data = bytearray()
        while time.monotonic() < deadline:
            try:
                part = self.device.read(1)
            except Exception as error:
                self.disconnected = True
                self.control_events.append({"operation": "serial_read", "result": "failed",
                    "error_type": type(error).__name__, "monotonic_ns": time.monotonic_ns()})
                raise CaptureError("Windows serial disconnected; automatic reconnect is disabled") from error
            if not part:
                continue
            data.extend(part)
            if len(data) > MAX_FRAME_BYTES:
                raise CaptureError("Windows serial line exceeds size limit")
            if part == b"\n":
                self._record_control_line_events()
                self._record_port_events("read")
                if self.disconnected:
                    raise CaptureError("Windows serial disconnected; automatic reconnect is disabled")
                return bytes(data)
        self._record_control_line_events()
        self._record_port_events("read_timeout")
        if self.disconnected:
            raise CaptureError("Windows serial disconnected; automatic reconnect is disabled")
        return bytes(data) if data else b""

    def _record_control_line_events(self):
        try:
            for event in self.platform.take_control_line_events(self.port) or ():
                self.control_events.append({"operation": "control_line", "detail": dict(event),
                                            "monotonic_ns": time.monotonic_ns()})
                line = str(event.get("line", "")).upper()
                action = str(event.get("operation", "")).lower()
                if line in {"DTR", "RTS"} and (
                        event.get("changed") is True or event.get("status") == "FAIL" or
                        action in {"set", "write", "toggle", "assert", "deassert", "pulse"}):
                    raise WindowsPortPreflightError(f"unexpected {line} control-line activity")
        except Exception as error:
            if isinstance(error, WindowsPortPreflightError):
                raise
            self.control_events.append({"operation": "control_line_observation", "result": "failed",
                                        "error_type": type(error).__name__,
                                        "monotonic_ns": time.monotonic_ns()})
            raise WindowsPortPreflightError("reset-related control-line observation failed") from error

    def _record_port_events(self, event: str):
        try:
            for item in self.platform.take_port_events(self.port) or ():
                if item.get("kind") in {"removed", "disconnected", "arrival_lost"}:
                    self.disconnected = True
                self.control_events.append({"operation": "host_port_event", "event": event,
                                            "detail": dict(item), "monotonic_ns": time.monotonic_ns()})
        except Exception as error:
            self.control_events.append({"operation": "host_port_event_observation", "event": event,
                                        "result": "failed", "error_type": type(error).__name__,
                                        "monotonic_ns": time.monotonic_ns()})

    def close(self):
        if self.device is not None:
            self.device.close()
            self.device = None
            self.control_events.append({"operation": "close", "result": "success",
                                        "monotonic_ns": time.monotonic_ns()})
            self._record_control_line_events()
            self._record_port_events("close")


def classify_ready_transition(previous: dict, current: dict) -> str:
    """Classify only evidence-supported boot transitions; never infer from logs."""
    old_generation, new_generation = previous.get("boot_generation"), current.get("boot_generation")
    if (isinstance(old_generation, int) and not isinstance(old_generation, bool) and
            isinstance(new_generation, int) and not isinstance(new_generation, bool)):
        if new_generation > old_generation:
            return "NEW_BOOT_CONFIRMED_BY_GENERATION"
        if new_generation == old_generation:
            return "SAME_GENERATION_OR_REPLAY"
    old_uptime, new_uptime = previous.get("uptime_ms"), current.get("uptime_ms")
    if (isinstance(old_uptime, int) and not isinstance(old_uptime, bool) and old_uptime >= 0 and
            isinstance(new_uptime, int) and not isinstance(new_uptime, bool) and new_uptime >= 0):
        if new_uptime < old_uptime:
            return "UPTIME_REGRESSION_POSSIBLE_NEW_BOOT"
        return "UPTIME_NONDECREASING"
    return "BOOT_TRANSITION_AMBIGUOUS_INSUFFICIENT_TARGET_EVIDENCE"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _public_key_from_pem(pem: bytes) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise CaptureError("evidence verifier key must be Ed25519")
    return key


def verify_backend_receipt(receipt: object, public_key_pem: bytes,
                           expected_binding: dict[str, str]) -> list[str]:
    """Verify a TEST_ONLY backend signature and exact source/fixture binding."""
    if not isinstance(receipt, dict):
        return ["backend receipt is not an object"]
    errors: list[str] = []
    signature_text = receipt.get("signature_b64")
    unsigned = {key: value for key, value in receipt.items() if key != "signature_b64"}
    schema = unsigned.get("schema")
    if schema not in {"gs68.backend.receipt.v1", "gs68.backend.readiness.v1"}:
        errors.append("backend receipt schema is invalid")
    try:
        signature = base64.b64decode(signature_text, validate=True)
        _public_key_from_pem(public_key_pem).verify(signature, canonical_json(unsigned))
    except Exception:
        errors.append("backend evidence signature is invalid")
    for key, expected in expected_binding.items():
        if unsigned.get(key) != expected:
            errors.append(f"backend evidence binding mismatch: {key}")
    if unsigned.get("environment") != "TEST_ONLY":
        errors.append("backend receipt is not TEST_ONLY")
    if unsigned.get("tls_version") != "TLSv1.2":
        errors.append("backend receipt does not prove TLS 1.2")
    if not HEX64.fullmatch(str(unsigned.get("client_certificate_sha256", ""))):
        errors.append("backend receipt lacks authenticated client certificate fingerprint")
    if not HEX64.fullmatch(str(unsigned.get("server_certificate_sha256", ""))):
        errors.append("backend receipt lacks server certificate fingerprint")
    if schema == "gs68.backend.readiness.v1":
        required = ("fixture_id", "source_commit", "image_sha256", "profile_sha256",
                    "case_plan_sha256", "case_id", "challenge_nonce", "hub_id",
                    "home_id", "installation_epoch", "trusted_time_utc")
        for key in required:
            if not unsigned.get(key):
                errors.append(f"backend readiness evidence lacks {key}")
        for key in ("image_sha256", "profile_sha256", "case_plan_sha256"):
            if not HEX64.fullmatch(str(unsigned.get(key, ""))):
                errors.append(f"backend readiness evidence has invalid {key}")
        c3_hashes = ("c3_image_sha256", "c3_profile_sha256")
        if any(key in unsigned for key in c3_hashes):
            if any(not HEX64.fullmatch(str(unsigned.get(key, ""))) for key in c3_hashes):
                errors.append("backend readiness C3 image/profile binding is incomplete or invalid")
        if not re.fullmatch(r"[0-9a-f]{40}", str(unsigned.get("source_commit", ""))):
            errors.append("backend readiness evidence has invalid source_commit")
        if unsigned.get("status") != "READY" or unsigned.get("physical") != "NOT_RUN":
            errors.append("backend readiness status or physical classification is invalid")
        try:
            trusted_time = datetime.fromisoformat(str(unsigned["trusted_time_utc"]).replace("Z", "+00:00"))
            if trusted_time.tzinfo is None:
                errors.append("backend readiness trusted time lacks an explicit UTC offset")
        except (KeyError, ValueError):
            errors.append("backend readiness trusted time is invalid")
    return errors


def verify_node_hub_event_key(node_observation: object, hub_event_key: object) -> list[str]:
    """Require an authenticated, durable Node ACK for the exact Hub EventKey."""
    if not isinstance(node_observation, dict) or not isinstance(hub_event_key, dict):
        return ["Node/Hub EventKey correlation evidence is missing"]
    errors: list[str] = []
    fields = ("physical_device_id", "source_id", "session_id", "sequence")
    node_key = node_observation.get("last_ack_event_key")
    if not isinstance(node_key, dict):
        return ["authenticated Node ACK EventKey is missing"]
    for field in fields:
        if str(node_key.get(field, "")) != str(hub_event_key.get(field, "")):
            errors.append(f"Node/Hub EventKey mismatch: {field}")
    for field in ("last_ack_authenticated", "last_ack_matched_pending",
                  "last_ack_retired", "last_ack_durable"):
        if node_observation.get(field) is not True:
            errors.append(f"Node ACK lacks required {field[9:] if field.startswith('last_ack_') else field} proof")
    return errors


def verify_node_observation_frame(frame: object, *, case_id: str, nonce: str,
                                  binding: dict[str, str]) -> list[str]:
    """Check a bounded C3 response against its case challenge and image build."""
    if not isinstance(frame, dict):
        return ["C3 observation frame is not an object"]
    errors: list[str] = []
    if frame.get("schema") != "gs68.target.event.v1" or frame.get("event") != "node_observation":
        errors.append("C3 observation frame schema or event type is invalid")
    if frame.get("role") != "c3":
        errors.append("C3 observation role is invalid")
    if not CASE_ID.fullmatch(case_id) or frame.get("case_id") != case_id:
        errors.append("C3 observation case ID does not match the requested case")
    if not HEX64.fullmatch(nonce) or frame.get("challenge_nonce") != nonce:
        errors.append("C3 observation challenge nonce does not match")
    for field in ("source_commit", "profile_sha256", "running_image_sha256"):
        expected = binding.get(field)
        if not expected or frame.get(field) != expected:
            errors.append(f"C3 observation binding mismatch: {field}")
    if frame.get("physical") != "NOT_RUN":
        errors.append("C3 software observer cannot declare physical execution")
    return errors


def parse_device_frame(raw: bytes) -> dict:
    if len(raw) > MAX_FRAME_BYTES:
        raise CaptureError("device frame exceeds size limit")
    if not raw.startswith(FRAME_PREFIX):
        raise CaptureError("device frame prefix is invalid")
    try:
        value = json.loads(raw[len(FRAME_PREFIX):].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureError("device frame is malformed") from exc
    if not isinstance(value, dict) or value.get("schema") != "gs68.target.event.v1":
        raise CaptureError("device frame schema is invalid")
    return value


def verify_case_frame(frame: dict, *, case_id: str, nonce: str,
                      binding: dict[str, str], verifier_pem: bytes) -> list[str]:
    errors: list[str] = []
    if frame.get("schema") != "gs68.target.event.v1" or frame.get("event") != "case_result":
        errors.append("target case-result frame schema or event type is invalid")
    if not CASE_ID.fullmatch(case_id) or frame.get("case_id") != case_id:
        errors.append("frame case ID does not match the requested case")
    if frame.get("challenge_nonce") != nonce:
        errors.append("frame challenge does not match this capture")
    receipt = frame.get("backend_receipt")
    errors.extend(verify_backend_receipt(receipt, verifier_pem, binding))
    observation = frame.get("observation")
    if not isinstance(observation, dict):
        errors.append("target observation is missing or is not an object")
    elif isinstance(receipt, dict):
        observation_sha256 = _sha256(canonical_json(observation))
        if receipt.get("event_body_sha256") != observation_sha256:
            errors.append("signed backend receipt does not bind the exact target observation")
        if isinstance(receipt.get("event_key"), dict):
            errors.extend(verify_node_hub_event_key(observation, receipt["event_key"]))
    if not isinstance(receipt, dict) or receipt.get("case_id") != case_id:
        errors.append("backend receipt case ID does not match")
    if not isinstance(receipt, dict) or receipt.get("challenge_nonce") != nonce:
        errors.append("backend receipt challenge does not match")
    outcome = frame.get("case_outcome")
    if outcome not in {"PASS", "FAIL", "BLOCKED"}:
        errors.append("device case outcome is missing or invalid")
    if isinstance(receipt, dict) and receipt.get("case_outcome") != outcome:
        errors.append("backend receipt does not attest the target case outcome")
    if outcome == "PASS" and isinstance(receipt, dict) and (
            receipt.get("status") != "COMMITTED" or receipt.get("durable") is not True):
        errors.append("PASS requires a signed durable COMMITTED backend receipt")
    if outcome == "FAIL" and isinstance(receipt, dict) and receipt.get("status") != "REJECTED":
        errors.append("FAIL requires a signed REJECTED backend receipt")
    if outcome == "BLOCKED":
        errors.append("blocked target case is not adjudicable")
    return errors


def make_hash_chain(records: list[dict]) -> list[dict]:
    previous = "0" * 64
    chain: list[dict] = []
    for record in records:
        unsigned = dict(record, previous_record_sha256=previous)
        digest = _sha256(canonical_json(unsigned))
        chain.append(dict(unsigned, record_sha256=digest))
        previous = digest
    return chain


def verify_hash_chain(records: object) -> list[str]:
    if not isinstance(records, list) or not records:
        return ["evidence record chain is missing"]
    errors: list[str] = []
    previous = "0" * 64
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"evidence record {index} is not an object")
            continue
        supplied = record.get("record_sha256")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        if unsigned.get("previous_record_sha256") != previous:
            errors.append(f"evidence record {index} chain link is invalid")
        actual = _sha256(canonical_json(unsigned))
        if supplied != actual:
            errors.append(f"evidence record {index} checksum is invalid")
        previous = supplied if isinstance(supplied, str) else actual
    return errors


@dataclass
class CaptureRecord:
    case_id: str
    challenge_nonce: str
    frame: dict
    received_monotonic: float


class BoundedCapture:
    """Read bounded JSONL frames from an injected transport, with no discovery."""
    def __init__(self, transport, *, max_bytes: int = MAX_CAPTURE_BYTES,
                 timeout_seconds: int = MAX_OBSERVATION_SECONDS):
        if not 1 <= max_bytes <= MAX_CAPTURE_BYTES:
            raise ValueError("capture byte bound is invalid")
        if not 1 <= timeout_seconds <= MAX_OBSERVATION_SECONDS:
            raise ValueError("capture timeout is invalid")
        self.transport = transport
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds
        self.bytes_read = 0
        self.started = None

    def open(self):
        self.transport.open()
        self.started = time.monotonic()

    def wait_ready(self, timeout_seconds: int = 30) -> dict:
        if self.started is None:
            raise CaptureError("capture is not open")
        deadline = min(self.started + self.timeout_seconds,
                       time.monotonic() + max(1, min(timeout_seconds, 60)))
        while time.monotonic() < deadline:
            raw = self.transport.read_line(max(0.1, deadline - time.monotonic()))
            if not raw:
                continue
            self.bytes_read += len(raw)
            if self.bytes_read > self.max_bytes:
                raise CaptureError("capture byte bound exceeded")
            if not raw.endswith(b"\n"):
                raise CaptureError("capture frame is truncated")
            if not raw.startswith(FRAME_PREFIX):
                continue
            frame = parse_device_frame(raw[:-1])
            if frame.get("event") == "ready":
                return frame
        raise CaptureError("target readiness frame was not captured within the bound")

    def request_case(self, case_id: str, nonce: str, command: dict) -> dict:
        if self.started is None:
            raise CaptureError("capture is not open")
        if not CASE_ID.fullmatch(case_id):
            raise CaptureError("unknown physical case ID")
        if not HEX64.fullmatch(nonce):
            raise CaptureError("challenge nonce must be 32 random bytes in hex")
        if time.monotonic() - self.started > self.timeout_seconds:
            raise CaptureError("capture time bound exceeded")
        request = dict(command, schema="gs68.target.command.v1", case_id=case_id,
                       challenge_nonce=nonce)
        self.transport.write(canonical_json(request) + b"\n")
        raw = self.transport.read_line(timeout=min(30, self.timeout_seconds))
        if not raw:
            raise CaptureError("capture interrupted before a complete response")
        self.bytes_read += len(raw)
        if self.bytes_read > self.max_bytes:
            raise CaptureError("capture byte bound exceeded")
        if not raw.endswith(b"\n"):
            raise CaptureError("capture frame is truncated")
        return parse_device_frame(raw[:-1])

    def request_node_observation(self, case_id: str, nonce: str,
                                 binding: dict[str, str]) -> dict:
        """Issue only the C3 read-only OBSERVE command and verify its binding."""
        frame = self.request_case(case_id, nonce, {"operation": "OBSERVE"})
        errors = verify_node_observation_frame(frame, case_id=case_id,
            nonce=nonce, binding=binding)
        if errors:
            raise CaptureError("; ".join(errors))
        return frame

    def close(self):
        self.transport.close()
        self.started = None


class PySerialTransport:
    """Explicitly open only a caller-supplied, fixture-manifest port.

    This is never constructed by dry-run code. It performs no discovery and
    configures control lines low before opening to reduce reset risk.
    """
    def __init__(self, port: str, *, baudrate: int = 115200, serial_module=None):
        if not isinstance(port, str) or not port.startswith("/dev/serial/by-id/"):
            raise CaptureError("physical capture requires an exact by-id fixture port")
        self.port = port
        self.baudrate = baudrate
        self.serial_module = serial_module
        self.device = None

    def open(self):
        if self.device is not None:
            raise CaptureError("serial transport is already open")
        if self.serial_module is None:
            import serial as serial_module
            self.serial_module = serial_module
        device = self.serial_module.Serial(port=None, baudrate=self.baudrate,
            timeout=0.2, write_timeout=1.0, dsrdtr=False, rtscts=False,
            xonxoff=False, exclusive=True)
        device.dtr = False
        device.rts = False
        device.port = self.port
        device.open()
        device.dtr = False
        device.rts = False
        self.device = device

    def write(self, payload: bytes):
        if self.device is None:
            raise CaptureError("serial transport is closed")
        self.device.write(payload)
        self.device.flush()

    def read_line(self, timeout: float) -> bytes:
        if self.device is None:
            raise CaptureError("serial transport is closed")
        deadline = time.monotonic() + timeout
        data = bytearray()
        while time.monotonic() < deadline:
            part = self.device.read(1)
            if not part:
                continue
            data.extend(part)
            if len(data) > MAX_FRAME_BYTES:
                raise CaptureError("serial frame exceeds size limit")
            if part == b"\n":
                return bytes(data)
        return b""

    def close(self):
        if self.device is not None:
            self.device.close()
            self.device = None


def write_evidence_bundle(path: Path, bundle: dict):
    """Atomically persist bounded, verifiable evidence without partial PASS."""
    path = Path(path)
    payload = canonical_json(bundle) + b"\n"
    if len(payload) > MAX_CAPTURE_BYTES:
        raise CaptureError("evidence bundle exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".partial-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def verify_evidence_bundle(bundle: object, verifier_pem: bytes,
                           required_case_ids: list[str]) -> list[str]:
    if not isinstance(bundle, dict):
        return ["evidence bundle is not an object"]
    errors = verify_hash_chain(bundle.get("records"))
    records = bundle.get("records", [])
    if bundle.get("capture_complete") is not True:
        errors.append("physical evidence capture is interrupted or incomplete")
    observed = []
    binding = bundle.get("binding")
    if not isinstance(binding, dict):
        binding = {key: bundle.get(key) for key in
                   ("fixture_id", "source_commit", "image_sha256", "profile_sha256", "backend_id",
                    "case_plan_sha256", "client_certificate_sha256", "server_certificate_sha256",
                    "hub_id", "home_id", "installation_epoch")}
    if any(not isinstance(binding.get(key), str) or not binding[key] for key in
           ("fixture_id", "source_commit", "image_sha256", "profile_sha256", "case_plan_sha256", "backend_id",
            "client_certificate_sha256", "server_certificate_sha256", "hub_id", "home_id",
            "installation_epoch")):
        return errors + ["evidence source/image/profile/fixture/backend binding is incomplete"]
    for key in ("fixture_id", "source_commit", "image_sha256", "profile_sha256", "case_plan_sha256",
                "backend_id", "hub_id", "home_id", "installation_epoch",
                "client_certificate_sha256", "server_certificate_sha256"):
        if bundle.get(key) != binding.get(key):
            errors.append(f"evidence bundle top-level {key} differs from its authenticated binding")
    if bundle.get("adapter_id") != "gs68-authenticated-serial-v1":
        errors.append("evidence bundle capture adapter identity is missing or invalid")
    if bundle.get("capture_started") is not True:
        errors.append("evidence bundle does not prove capture started")
    for record in records:
        if not isinstance(record, dict):
            continue
        case_id = record.get("case_id")
        frame = record.get("device_frame")
        if not isinstance(case_id, str) or not isinstance(frame, dict):
            errors.append("record lacks case ID or device frame")
            continue
        observed.append(case_id)
        errors.extend(verify_case_frame(frame, case_id=case_id,
            nonce=str(record.get("challenge_nonce", "")), binding=binding,
            verifier_pem=verifier_pem))
    if len(observed) != len(set(observed)):
        errors.append("duplicate case evidence record")
    missing = sorted(set(required_case_ids) - set(observed))
    if missing:
        errors.append("required physical cases are missing: " + ",".join(missing))
    if bundle.get("physical") != "NOT_RUN" and bundle.get("physical") != "CAPTURED_UNADJUDICATED":
        errors.append("physical status must remain NOT_RUN until approved case adjudication")
    return errors
