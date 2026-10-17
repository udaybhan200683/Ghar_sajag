"""Authenticated, bounded capture primitives for future GS-68 physical runs.

Importing this module is side-effect free.  USB/serial is opened only by an
explicit physical runner invocation after fixture and approval checks pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
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


class WindowsPortBusyError(WindowsPortPreflightError):
    """The exclusive Windows COM open was denied because it is already held."""


class _Win32SerialHandle:
    """Small synchronous Win32 serial handle with bounded I/O timeouts.

    This configures data/flow-control parameters only. It does not call
    EscapeCommFunction, SetCommBreak, or any DTR/RTS operation. CreateFileW
    itself is still driver-dependent and therefore remains policy-gated.
    """
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _DCB(ctypes.Structure):
        _fields_ = [("DCBlength", ctypes.c_uint32), ("BaudRate", ctypes.c_uint32),
            ("fFlags", ctypes.c_uint32), ("wReserved", ctypes.c_uint16),
            ("XonLim", ctypes.c_uint16), ("XoffLim", ctypes.c_uint16),
            ("ByteSize", ctypes.c_uint8), ("Parity", ctypes.c_uint8),
            ("StopBits", ctypes.c_uint8), ("XonChar", ctypes.c_int8),
            ("XoffChar", ctypes.c_int8), ("ErrorChar", ctypes.c_int8),
            ("EofChar", ctypes.c_int8), ("EvtChar", ctypes.c_int8),
            ("wReserved1", ctypes.c_uint16)]

    class _COMMTIMEOUTS(ctypes.Structure):
        _fields_ = [("ReadIntervalTimeout", ctypes.c_uint32),
            ("ReadTotalTimeoutMultiplier", ctypes.c_uint32),
            ("ReadTotalTimeoutConstant", ctypes.c_uint32),
            ("WriteTotalTimeoutMultiplier", ctypes.c_uint32),
            ("WriteTotalTimeoutConstant", ctypes.c_uint32)]

    def __init__(self, port: str, *, baudrate: int, timeout: float,
                 write_timeout: float, kernel32=None):
        if sys.platform != "win32" and kernel32 is None:
            raise WindowsPortPreflightError("Win32 serial handles are available only on Windows")
        self.kernel32 = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        self._declare_win32_signatures()
        self.handle = self.kernel32.CreateFileW("\\\\.\\" + port, self.GENERIC_READ | self.GENERIC_WRITE,
            0, None, self.OPEN_EXISTING, 0, None)
        if self.handle in (None, self.INVALID_HANDLE_VALUE):
            error = ctypes.get_last_error()
            if error in (5, 32, 33):
                raise WindowsPortBusyError("exclusive COM open denied; owner is unavailable or port is busy")
            raise OSError(error, "Windows COM open failed")
        try:
            dcb = self._DCB()
            dcb.DCBlength = ctypes.sizeof(dcb)
            if not self.kernel32.GetCommState(self.handle, ctypes.byref(dcb)):
                raise OSError(ctypes.get_last_error(), "GetCommState failed")
            # Never alter DTR/RTS state after CreateFile: first reject inherited
            # DCBs that request either line, then preserve their disabled bits.
            # A transition during CreateFile is outside this process's control
            # and must be covered by the independent reset-safe policy.
            if dcb.fFlags & (0x3 << 4) or dcb.fFlags & (0x3 << 12):
                raise WindowsPortPreflightError("inherited DCB enables DTR/RTS control; refusing line change")
            # Disable CTS/DSR hardware and XON/XOFF software flow control only.
            dcb.fFlags &= ~((1 << 2) | (1 << 3) | (1 << 8) | (1 << 9))
            dcb.BaudRate = baudrate
            dcb.ByteSize, dcb.Parity, dcb.StopBits = 8, 0, 0
            if not self.kernel32.SetCommState(self.handle, ctypes.byref(dcb)):
                raise OSError(ctypes.get_last_error(), "SetCommState failed")
            limits = self._COMMTIMEOUTS(0xFFFFFFFF, 0, max(1, int(timeout * 1000)),
                                        0, max(1, int(write_timeout * 1000)))
            if not self.kernel32.SetCommTimeouts(self.handle, ctypes.byref(limits)):
                raise OSError(ctypes.get_last_error(), "SetCommTimeouts failed")
        except Exception:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None
            raise

    def _declare_win32_signatures(self):
        """Prevent default ctypes int conversions from truncating 64-bit handles."""
        declarations = {
            "CreateFileW": ([ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p], ctypes.c_void_p),
            "GetCommState": ([ctypes.c_void_p, ctypes.POINTER(self._DCB)], ctypes.c_int),
            "SetCommState": ([ctypes.c_void_p, ctypes.POINTER(self._DCB)], ctypes.c_int),
            "SetCommTimeouts": ([ctypes.c_void_p, ctypes.POINTER(self._COMMTIMEOUTS)], ctypes.c_int),
            "ReadFile": ([ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p], ctypes.c_int),
            "WriteFile": ([ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p], ctypes.c_int),
            "FlushFileBuffers": ([ctypes.c_void_p], ctypes.c_int),
            "CloseHandle": ([ctypes.c_void_p], ctypes.c_int),
        }
        for name, (argtypes, restype) in declarations.items():
            function = getattr(self.kernel32, name)
            function.argtypes = argtypes
            function.restype = restype

    def read(self, count: int) -> bytes:
        if self.handle is None:
            raise OSError("COM handle is closed")
        count = min(max(1, int(count)), MAX_FRAME_BYTES)
        buffer = ctypes.create_string_buffer(count)
        read_count = ctypes.c_uint32()
        if not self.kernel32.ReadFile(self.handle, buffer, count, ctypes.byref(read_count), None):
            raise OSError(ctypes.get_last_error(), "ReadFile failed")
        return buffer.raw[:read_count.value]

    def write(self, payload: bytes) -> int:
        if self.handle is None:
            raise OSError("COM handle is closed")
        if len(payload) > MAX_FRAME_BYTES:
            raise CaptureError("Windows serial write exceeds bound")
        buffer = ctypes.create_string_buffer(payload)
        written = ctypes.c_uint32()
        if not self.kernel32.WriteFile(self.handle, buffer, len(payload), ctypes.byref(written), None):
            raise OSError(ctypes.get_last_error(), "WriteFile failed")
        return written.value

    def flush(self):
        if self.handle is not None and not self.kernel32.FlushFileBuffers(self.handle):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers failed")

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            if not self.kernel32.CloseHandle(handle):
                raise OSError(ctypes.get_last_error(), "CloseHandle failed")


class WindowsSerialPlatform:
    """Windows PnP/native serial provider; reset-safety is never inferred.

    Device enumeration uses the Windows PnP cmdlets and does not open COM.
    Port-owner PID is not available through a documented, reliable Windows
    interface. The subsequent share-mode-zero CreateFile is the atomic
    exclusive-access test. Default opening requires a qualified reset-safe
    policy. A separate transport mode can tolerate an opening reset for the
    one owner-authorized spare fixture; it does not establish reset safety.

    `native_api` and `reset_safe_policy` are injectable for deterministic tests.
    The policy callback must be backed by external qualification evidence; a
    callback is not itself evidence and this repository supplies none.
    """
    _PNP_SCRIPT = r"""
$ErrorActionPreference='Stop'
$rows = @(Get-PnpDevice -Class Ports -PresentOnly | ForEach-Object {
  $name = $_.FriendlyName
  $m = [regex]::Match($name, '\((COM[0-9]+)\)$', 'IgnoreCase')
  if ($m.Success) {
    $id = $_.InstanceId
    $version = (Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverVersion -ErrorAction SilentlyContinue).Data
    [pscustomobject]@{port=$m.Groups[1].Value.ToUpperInvariant(); instance_id=$id;
      driver_version=[string]$version; present=$true}
  }
})
ConvertTo-Json -InputObject $rows -Compress -Depth 3
"""

    def __init__(self, *, native_api=None, reset_safe_policy=None):
        self.native_api = native_api
        self.reset_safe_policy = reset_safe_policy
        self._last_identity: dict | None = None
        self._port_presence: dict[str, bool] = {}
        self._port_events: dict[str, list[dict]] = {}
        self._control_events: dict[str, list[dict]] = {}
        self._line_unobservable_reported: set[str] = set()

    def _api(self):
        if self.native_api is None:
            if sys.platform != "win32":
                raise WindowsPortPreflightError("Windows PnP provider is unavailable on this host")
            self.native_api = _WindowsNativeApi()
        return self.native_api

    def _ports(self) -> list[dict]:
        return self._api().enumerate_pnp_ports()

    def inspect_pnp_identity(self, port: str) -> dict | None:
        if not re.fullmatch(r"COM[1-9][0-9]*", str(port).upper()):
            return None
        matches = [row for row in self._ports() if row.get("port", "").upper() == port.upper()]
        if len(matches) != 1 or matches[0].get("present") is not True:
            return None
        row = matches[0]
        match = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})[^\\]*\\([^\\]+)$",
                          str(row.get("instance_id", "")), re.IGNORECASE)
        if not match:
            return None
        identity = {"instance_id": row["instance_id"], "vid": match.group(1).lower(),
                    "pid": match.group(2).lower(), "serial": match.group(3),
                    "driver_version": row.get("driver_version", "")}
        self._last_identity = identity
        self._port_presence[port.upper()] = True
        return identity

    def port_owner(self, port: str) -> int | None:
        # Windows has no documented reliable arbitrary-COM-handle -> PID query.
        return None

    def exclusive_open_is_ownership_check(self, port: str) -> bool:
        return True

    def reset_safe_open_policy(self, port: str) -> dict:
        identity = self.inspect_pnp_identity(port)
        if identity is None:
            return {"verified": False, "description": "current PnP identity unavailable"}
        if self.reset_safe_policy is None:
            return {"verified": False,
                    "description": "no externally qualified reset-safe policy for the active Windows driver"}
        try:
            result = self.reset_safe_policy(dict(identity))
        except Exception:
            return {"verified": False, "description": "reset-safe policy verification failed"}
        if not isinstance(result, dict) or result.get("verified") is not True or not result.get("evidence_id"):
            return {"verified": False, "description": "reset-safe policy evidence is absent or invalid"}
        return {"verified": True, "description": str(result["evidence_id"])}

    def open_serial(self, port: str, *, baudrate: int, timeout: float,
                    write_timeout: float, flow_control: bool, expected_pnp: dict | None = None):
        if flow_control or not (0 < timeout <= 1 and 0 < write_timeout <= 2):
            raise WindowsPortPreflightError("serial parameters exceed the bounded observer policy")
        if expected_pnp is not None:
            current = self.inspect_pnp_identity(port)
            if not isinstance(current, dict) or any(current.get(key) != value
                    for key, value in expected_pnp.items()):
                raise WindowsPortPreflightError("PnP identity changed immediately before exclusive open")
        return self._api().open_exclusive(port, baudrate=baudrate, timeout=timeout,
                                          write_timeout=write_timeout)

    def take_control_line_events(self, port: str) -> list[dict]:
        events = self._control_events.pop(port.upper(), [])
        if not events and port.upper() not in self._line_unobservable_reported:
            events.append({"kind": "driver_line_state_unobservable",
                           "note": "Win32 provider issues no DTR/RTS IOCTL; driver transitions are not observable here"})
            self._line_unobservable_reported.add(port.upper())
        return events

    def take_port_events(self, port: str) -> list[dict]:
        port = port.upper()
        events = self._port_events.setdefault(port, [])
        try:
            present = any(row.get("port", "").upper() == port and row.get("present") is True
                          for row in self._ports())
        except Exception:
            events.append({"kind": "presence_unknown"})
            result, self._port_events[port] = events, []
            return result
        old = self._port_presence.get(port)
        if old is True and not present:
            events.append({"kind": "removed"})
        elif old is False and present:
            events.append({"kind": "reenumerated"})
        self._port_presence[port] = present
        result, self._port_events[port] = events, []
        return result


class _WindowsNativeApi:
    def enumerate_pnp_ports(self) -> list[dict]:
        command = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                   "-Command", WindowsSerialPlatform._PNP_SCRIPT]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True,
                                    timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            rows = json.loads(result.stdout or "[]")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            raise WindowsPortPreflightError("Windows PnP enumeration failed or timed out") from error
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise WindowsPortPreflightError("Windows PnP enumeration returned malformed data")
        return rows

    def open_exclusive(self, port: str, *, baudrate: int, timeout: float, write_timeout: float):
        return _Win32SerialHandle(port, baudrate=baudrate, timeout=timeout,
                                  write_timeout=write_timeout)


class WindowsNativeSerialTransport:
    """Single-open, identity-pinned Windows observation transport.

    This adapter deliberately requires a provider that can prove all of the
    following before opening: exact PnP identity, no competing process, and a
    driver/open policy that does not pulse reset-related control lines. Merely
    setting DTR/RTS low after open is not accepted as proof.
    """
    OWNER_AUTHORIZED_SPARE_FIXTURE = "GS68-SPARE-S3-OWNER-DESIGNATED"

    def __init__(self, port: str, *, expected_port: str, expected_pnp: dict[str, str],
                 platform=None, baudrate: int = 115200, fixture_id: str | None = None,
                 opening_mode: str = "reset_safe"):
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
        if opening_mode not in {"reset_safe", "controlled_reset_tolerant"}:
            raise WindowsPortPreflightError("unsupported Windows port opening mode")
        if opening_mode == "controlled_reset_tolerant" and fixture_id != self.OWNER_AUTHORIZED_SPARE_FIXTURE:
            raise WindowsPortPreflightError("controlled-reset opening is restricted to the owner-authorized spare fixture")
        self.fixture_id = fixture_id
        self.opening_mode = opening_mode
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
        self.control_events.append({"operation": "pnp_identity", "result": "matched",
            "port": self.port,
            "instance_id_sha256": hashlib.sha256(str(observed["instance_id"]).encode()).hexdigest(),
            "driver_version": observed.get("driver_version", ""),
            "monotonic_ns": time.monotonic_ns()})
        owner = self.platform.port_owner(self.port)
        exclusive_open_check = getattr(self.platform, "exclusive_open_is_ownership_check", None)
        if owner is None and not (callable(exclusive_open_check) and
                                  exclusive_open_check(self.port) is True):
            raise WindowsPortPreflightError("COM port ownership could not be checked")
        if owner:
            raise WindowsPortPreflightError("COM port is owned by another process")
        if self.opening_mode == "controlled_reset_tolerant":
            # This is a fixture-scoped authorization to tolerate an opening
            # reset, not evidence that the Windows driver is reset-safe.
            if observed.get("vid", "").lower() != "303a" or observed.get("pid", "").lower() != "1001":
                raise WindowsPortPreflightError("controlled-reset opening requires the expected Espressif USB Serial/JTAG identity")
            policy = {"verified": True, "description": "owner-authorized controlled reset is tolerated for this spare only",
                      "reset_safety_proven": False}
            event_result = "owner_authorized_reset_tolerant"
        else:
            policy = self.platform.reset_safe_open_policy(self.port)
            if not isinstance(policy, dict) or policy.get("verified") is not True or not policy.get("description"):
                raise WindowsPortPreflightError("Windows driver cannot prove reset-safe port opening")
            event_result = "verified_reset_safe"
        self.control_events.append({"operation": "open_policy", "result": event_result,
                                    "description": str(policy["description"]),
                                    "reset_safety_proven": policy.get("reset_safety_proven", True),
                                    "reset_during_open_acceptable": self.opening_mode == "controlled_reset_tolerant",
                                    "monotonic_ns": time.monotonic_ns()})
        if owner is None:
            self.control_events.append({"operation": "port_owner", "result": "UNKNOWN",
                "verification": "share-mode-zero CreateFile is the atomic exclusive check",
                "monotonic_ns": time.monotonic_ns()})
        # Count the attempt before invoking the driver. A failed CreateFile or
        # post-open DCB check must never trigger an automatic second open.
        self.ever_opened = True
        try:
            self.device = self.platform.open_serial(self.port, baudrate=self.baudrate,
                timeout=0.2, write_timeout=1.0, flow_control=False,
                expected_pnp=self.expected_pnp)
        except WindowsPortBusyError:
            self.control_events.append({"operation": "open", "result": "BUSY_OR_ACCESS_DENIED",
                                        "monotonic_ns": time.monotonic_ns()})
            raise
        except WindowsPortPreflightError:
            self.control_events.append({"operation": "open", "result": "preflight_rejected",
                                        "monotonic_ns": time.monotonic_ns()})
            raise
        except Exception as error:
            self.control_events.append({"operation": "open", "result": "failed",
                                        "error_type": type(error).__name__,
                                        "monotonic_ns": time.monotonic_ns()})
            raise WindowsPortPreflightError("Windows serial open failed; reconnect is forbidden") from error
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
                if item.get("kind") in {"removed", "disconnected", "arrival_lost",
                                         "reenumerated", "presence_unknown"}:
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
