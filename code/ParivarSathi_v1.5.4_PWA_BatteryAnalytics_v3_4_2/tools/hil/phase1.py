#!/usr/bin/env python3
"""Unattended real Hub+C3 Phase-1 HIL setup, preflight, smoke and regression."""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_PRODUCT = Path(__file__).resolve().parents[2]
if str(SCRIPT_PRODUCT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PRODUCT))

from serial.tools import list_ports

from tools.hil.core import (EXPECTED_C3_MAC, EXPECTED_HUB_MAC, PRODUCT, REPO,
                            Device, FixtureLock, Results, SerialCapture,
                            assign_devices, host_metadata, load_env,
                            normalize_mac, source_fingerprint, write_report)
from tools.hil.usb_attach import invoke_windows_helper, is_wsl

CONFIG = REPO / "config/hil.local.env"
MANIFEST = PRODUCT / "build/hw_pair/provenance.json"
RUNS = REPO / "evidence/hil/runs"
LOCK = Path(os.environ.get("GS_HIL_LOCK", "/tmp/ghar-sajag-hil.lock"))
NODE_PROJECT = PRODUCT / "firmware/node/target/esp32c3/idf"
HUB_PROJECT = PRODUCT / "firmware/hub/target/esp32/idf"
IDENTITY_WORKER = Path(__file__).with_name("identity_probe.py")
IDENTITY_PROBE_TIMEOUT = 8.0
FIXTURE_STABILITY_SAMPLES = 2
FIXTURE_STABILITY_INTERVAL = .35
EXPECTED_USB_IDS = {"hub": "10c4:ea60", "c3": "303a:1001"}
# The target-side HIL acknowledgement is useful diagnostics, but it is emitted
# immediately before esp_restart() and can be truncated at the reset boundary.
# ROM reset reasons are normalized before campaign logic evaluates them.
SOFTWARE_RESET_EVIDENCE = "SOFTWARE_RESET"
SOFTWARE_RESET_REASONS = frozenset({"SW_CPU_RESET", "RTC_SW_CPU_RST"})
ROM_RESET_REASON = re.compile(r"\brst:0x[0-9a-f]+\s+\((?P<reason>[A-Z0-9_]+)\)", re.IGNORECASE)


def normalize_rom_reset_class(line: str) -> str | None:
    """Map only supported ESP32 ROM software-reset reasons to one class."""
    match = ROM_RESET_REASON.search(line)
    if not match:
        return None
    reason = match.group("reason").upper()
    return SOFTWARE_RESET_EVIDENCE if reason in SOFTWARE_RESET_REASONS else "OTHER_RESET"
_ACTIVE_IDENTITY_PROBES: dict[str, "ActiveIdentityProbe"] = {}

SMOKE_IDS = [f"HIL-SMOKE-{n:03d}" for n in range(1, 18)]
RADIO_IDS = [f"HIL-RADIO-{n:03d}" for n in range(1, 11)]
OR_IDS = [f"HIL-OR-{n:03d}" for n in range(1, 21)]
HUB_RST_IDS = [f"HIL-HUB-RST-{n:03d}" for n in range(1, 11)]
C3_RST_IDS = [f"HIL-C3-RST-{n:03d}" for n in range(1, 9)]
BOTH_RST_IDS = [f"HIL-BOTH-RST-{n:03d}" for n in range(1, 7)]


@dataclasses.dataclass(frozen=True)
class ProbeRecord:
    port: str
    vid: int | None
    pid: int | None
    usb_serial: str | None
    stable_path: str
    probe: str = "FAIL"
    chip: str = "unknown"
    mac: str = "unknown"
    classification: str = "unknown"
    rejection_reason: str = ""
    device: Device | None = None

    def diagnostic(self) -> str:
        vid_pid = f"{self.vid or 0:04x}:{self.pid or 0:04x}"
        serial = self.usb_serial or "none"
        reason = self.rejection_reason or "none"
        return (f"candidate {self.port} VID:PID={vid_pid} usb_serial={serial} "
                f"esptool probe={self.probe} chip={self.chip} MAC={self.mac} "
                f"classification={self.classification} rejection reason={reason}")


class IdentityProbeError(RuntimeError):
    """A bounded, classified identity-probe failure."""


@dataclasses.dataclass
class ActiveIdentityProbe:
    process: object
    result: Path
    child_pid: Path
    started: float
    timed_out: bool = False


def activation(config: dict[str, str]) -> Path:
    return Path(config.get("HIL_IDF_ACTIVATE", str(Path.home() / ".espressif/tools/activate_idf_v6.0.3.sh")))


def idf_command(config: dict[str, str], command: str, cwd: Path, timeout=1800):
    script = activation(config)
    return subprocess.run(["bash", "-lc", f"source {shlex.quote(str(script))}; {command}"],
                          cwd=cwd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout,
                          env={**os.environ, "PYTHONUNBUFFERED": "1"})


def _identity_probe_paths(port: str) -> tuple[Path, Path]:
    digest = hashlib.sha256(port.encode()).hexdigest()[:16]
    base = Path(tempfile.gettempdir()) / f"ghar-sajag-identity-{digest}"
    return base.with_suffix(".json"), base.with_suffix(".pid")


def _finish_identity_probe(port: str, active: ActiveIdentityProbe):
    """Retire only a completed worker; never synchronously reap a stuck one."""
    if active.process.poll() is None:
        return False
    _ACTIVE_IDENTITY_PROBES.pop(port, None)
    return True


def _stop_identity_probe(active: ActiveIdentityProbe):
    """Signal only esptool; leave its worker alive to reap a D-state child."""
    try:
        child = int(active.child_pid.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(child, signal.SIGTERM)


def run_identity_probe(config: dict[str, str], port: str, *, timeout: float = IDENTITY_PROBE_TIMEOUT,
                       popen=subprocess.Popen, monotonic=time.monotonic, sleeper=time.sleep):
    """Return one esptool result without allowing an uninterruptible USB wait to block us.

    The isolated worker reaps its own esptool child if it eventually leaves D
    state.  This supervisor only uses non-blocking poll(), retains at most one
    active worker per port, and therefore cannot accumulate probes during a
    repeated USB recovery cycle.
    """
    path = Path(port)
    if not path.exists():
        raise IdentityProbeError(f"IDENTITY_PROBE_STALE_TTY port={port}: path absent before probe")
    active = _ACTIVE_IDENTITY_PROBES.get(port)
    if active:
        if not _finish_identity_probe(port, active):
            raise IdentityProbeError(f"IDENTITY_PROBE_STALE_TTY port={port}: prior probe still active")
    for active_port, active_probe in list(_ACTIVE_IDENTITY_PROBES.items()):
        if active_port != port and not _finish_identity_probe(active_port, active_probe):
            raise IdentityProbeError(
                f"IDENTITY_PROBE_STALE_TTY port={port}: prior timed-out probe remains active on {active_port}")
    result, child_pid = _identity_probe_paths(port)
    for path_to_clear in (result, child_pid):
        with contextlib.suppress(FileNotFoundError): path_to_clear.unlink()
    command = [sys.executable, str(IDENTITY_WORKER), "--activate", str(activation(config)),
               "--port", port, "--result", str(result), "--pid", str(child_pid)]
    try:
        process = popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
    except OSError as exc:
        raise IdentityProbeError(f"IDENTITY_PROBE_LAUNCH_FAILED port={port}: {exc}") from exc
    active = ActiveIdentityProbe(process, result, child_pid, monotonic())
    _ACTIVE_IDENTITY_PROBES[port] = active
    deadline = active.started + timeout
    while monotonic() < deadline:
        if not path.exists():
            _stop_identity_probe(active)
            raise IdentityProbeError(f"IDENTITY_PROBE_USB_DISAPPEARED port={port}")
        if result.is_file():
            try:
                payload = json.loads(result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _stop_identity_probe(active)
                raise IdentityProbeError(f"IDENTITY_PROBE_RESULT_INVALID port={port}: {exc}") from exc
            # Result publication occurs only after esptool has exited and the
            # worker owns no stuck child.  Do not delay qualification waiting
            # for the worker's final interpreter shutdown.
            _ACTIVE_IDENTITY_PROBES.pop(port, None)
            return subprocess.CompletedProcess(command, int(payload.get("returncode", 127)),
                                               payload.get("stdout", "") + payload.get("error", ""))
        if _finish_identity_probe(port, active):
            raise IdentityProbeError(f"IDENTITY_PROBE_WORKER_EXITED port={port}: no result")
        sleeper(min(.1, max(.01, deadline - monotonic())))
    _stop_identity_probe(active)
    active.timed_out = True
    elapsed = monotonic() - active.started
    raise IdentityProbeError(f"IDENTITY_PROBE_TIMEOUT port={port} elapsed={elapsed:.1f}s")


def fixture_usb_snapshot(config: dict[str, str]) -> dict[str, object]:
    """Cheap metadata-only fixture presence check; never touches esptool."""
    wanted = {role: config.get(f"HIL_{role.upper()}_VID_PID", expected).lower()
              for role, expected in EXPECTED_USB_IDS.items()}
    snapshot: dict[str, object] = {}
    for role, identity in wanted.items():
        matches = [item for item in list_ports.comports()
                   if is_usb_candidate(item) and f"{item.vid or 0:04x}:{item.pid or 0:04x}" == identity]
        if len(matches) != 1:
            raise RuntimeError(f"FIXTURE_RECOVERY_TIMEOUT {role}: expected one USB candidate {identity}; found {len(matches)}")
        item = matches[0]
        if not Path(item.device).exists():
            raise RuntimeError(f"IDENTITY_PROBE_STALE_TTY {role}: {item.device} vanished during metadata check")
        snapshot[role] = item
    return snapshot


def stable_fixture_usb_snapshot(config: dict[str, str], *, samples: int = FIXTURE_STABILITY_SAMPLES,
                                interval: float = FIXTURE_STABILITY_INTERVAL, sleeper=time.sleep):
    """Require repeated identical pyserial/sysfs observations before esptool."""
    first = fixture_usb_snapshot(config)
    for _ in range(1, samples):
        sleeper(interval)
        current = fixture_usb_snapshot(config)
        for role in EXPECTED_USB_IDS:
            before, after = first[role], current[role]
            if (before.device, before.vid, before.pid, before.serial_number) != (
                    after.device, after.vid, after.pid, after.serial_number):
                raise RuntimeError(f"IDENTITY_PROBE_STALE_TTY {role}: USB enumeration is transitioning")
    return first


def stable_path(port: str) -> str:
    root = Path("/dev/serial/by-id")
    if root.is_dir():
        actual = Path(port).resolve()
        for candidate in root.iterdir():
            with contextlib.suppress(OSError):
                if candidate.resolve() == actual: return str(candidate)
    return port


def parse_esptool_output(output: str) -> tuple[str, str]:
    """Parse esptool 4.x/5.x chip and repeated MAC output fail-closed."""
    chip_matches = re.findall(r"(?:Chip type:|Chip is)\s*([^\r\n]+)", output, re.IGNORECASE)
    mac_matches = re.findall(
        r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b", output,
        re.IGNORECASE)
    if not chip_matches:
        raise ValueError("esptool output has no Chip type/Chip is line")
    if not mac_matches:
        raise ValueError("esptool output has no six-octet MAC line")
    normalized_macs = {normalize_mac(value) for value in mac_matches}
    if len(normalized_macs) != 1:
        raise ValueError(f"esptool output contains conflicting MACs: {sorted(normalized_macs)}")
    chip = chip_matches[0].split("(", 1)[0].strip()
    if not chip:
        raise ValueError("esptool chip value is empty")
    return chip, normalized_macs.pop()


def probe_port(port_info, config: dict[str, str]) -> ProbeRecord:
    expected = {"hub": normalize_mac(config.get("HIL_HUB_MAC", EXPECTED_HUB_MAC)),
                "c3": normalize_mac(config.get("HIL_C3_MAC", EXPECTED_C3_MAC))}
    stable = stable_path(port_info.device)
    base = dict(port=port_info.device, vid=port_info.vid, pid=port_info.pid,
                usb_serial=port_info.serial_number, stable_path=stable)
    try:
        cp = run_identity_probe(config, port_info.device)
    except IdentityProbeError as exc:
        return ProbeRecord(**base, rejection_reason=str(exc))
    output = cp.stdout or ""
    if cp.returncode:
        tail = " ".join(output.splitlines()[-3:])
        return ProbeRecord(**base, rejection_reason=f"esptool exit={cp.returncode}: {tail[-500:]}")
    try:
        chip, mac = parse_esptool_output(output)
    except ValueError as exc:
        return ProbeRecord(**base, probe="PASS", rejection_reason=str(exc))
    role = "hub" if mac == expected["hub"] else "c3" if mac == expected["c3"] else "unknown"
    classification = "Hub" if role == "hub" else "C3" if role == "c3" else "unknown"
    is_c3 = "esp32-c3" in chip.lower()
    if role == "hub" and is_c3:
        return ProbeRecord(**base, probe="PASS", chip=chip, mac=mac,
                           classification=classification,
                           rejection_reason="expected Hub MAC reported as ESP32-C3")
    if role == "c3" and not is_c3:
        return ProbeRecord(**base, probe="PASS", chip=chip, mac=mac,
                           classification=classification,
                           rejection_reason="expected C3 MAC reported as non-C3 chip")
    if role == "unknown":
        return ProbeRecord(**base, probe="PASS", chip=chip, mac=mac,
                           classification=classification,
                           rejection_reason="MAC is not a configured Hub or C3 identity")
    device = Device(port_info.device, mac, chip, port_info.vid, port_info.pid,
                    port_info.serial_number, port_info.location, stable)
    return ProbeRecord(**base, probe="PASS", chip=chip, mac=mac,
                       classification=classification, device=device)


def is_usb_candidate(port_info) -> bool:
    """Exclude explicit non-USB kernel serial devices from esptool probing."""
    # pyserial reports WSL/Linux ttyS* entries as None (rendered by our
    # diagnostics as 0000:0000).  They cannot be ESP USB candidates.  Keep
    # probing unknown non-ttyS bridges: missing metadata alone must not hide
    # a board.
    no_usb_identity = (port_info.vid or 0) == 0 and (port_info.pid or 0) == 0
    return not (no_usb_identity and Path(port_info.device).name.startswith("ttyS"))


def discover(config: dict[str, str]) -> tuple[dict[str, Device], list[Device]]:
    ports = list(list_ports.comports())
    skipped = [info for info in ports if not is_usb_candidate(info)]
    for info in skipped:
        print(f"HIL DISCOVERY: skipped non-USB serial candidate {info.device} "
              f"VID:PID={info.vid or 0:04x}:{info.pid or 0:04x}")
    records = [probe_port(info, config) for info in ports if is_usb_candidate(info)]
    observations = [record.device for record in records if record.device is not None]
    expected_hub = config.get("HIL_HUB_MAC", EXPECTED_HUB_MAC)
    expected_c3 = config.get("HIL_C3_MAC", EXPECTED_C3_MAC)
    try:
        resolved = assign_devices(observations, expected_hub, expected_c3)
    except RuntimeError as exc:
        diagnostics = "\n".join(f"- {record.diagnostic()}" for record in records)
        suffix = f"\nProbe diagnostics:\n{diagnostics}" if diagnostics else "\nProbe diagnostics: no serial candidates reported by pyserial"
        raise RuntimeError(f"{exc}{suffix}") from exc
    for record in records:
        print(f"HIL DISCOVERY: {record.diagnostic()}")
    return resolved, observations


def _verified_runtime_port(config: dict[str, str], role: str) -> str:
    """Resolve one tty and re-verify its actual ESP chip/MAC identity."""
    stable = config.get(f"HIL_{role.upper()}_STABLE_PATH", "")
    serial_number = config.get(f"HIL_{role.upper()}_USB_SERIAL", "")
    vid_pid = config.get(f"HIL_{role.upper()}_VID_PID", "").lower()
    candidates = []
    for item in list_ports.comports():
        identity = f"{item.vid or 0:04x}:{item.pid or 0:04x}"
        stable_match = False
        if stable and Path(stable).exists():
            with contextlib.suppress(OSError):
                stable_match = Path(item.device).resolve() == Path(stable).resolve()
        if stable_match or (serial_number and item.serial_number == serial_number) or (
                not serial_number and identity == vid_pid):
            candidates.append(item)
    unique = {item.device: item for item in candidates}
    if len(unique) != 1:
        raise RuntimeError(f"cannot uniquely rediscover {role}: {sorted(unique)}")
    record = probe_port(next(iter(unique.values())), config)
    if record.device is None or record.classification.lower() != role:
        raise RuntimeError(f"{role} reconnect identity verification failed: {record.diagnostic()}")
    return record.device.port


def runtime_port(config: dict[str, str], role: str, *, timeout: float = 15.0,
                 grace_seconds: float = 2.0,
                 helper_invoker=None, monotonic=time.monotonic,
                 sleeper=time.sleep) -> str:
    """WSL-owned bounded rediscovery, attachment and chip/MAC verification."""
    first_error = None
    try:
        return _verified_runtime_port(config, role)
    except RuntimeError as exc:
        first_error = exc
        if not is_wsl():
            raise
    overall_deadline = monotonic() + timeout
    grace_deadline = min(overall_deadline, monotonic() + grace_seconds)
    while monotonic() < grace_deadline:
        sleeper(min(.25, max(0.0, grace_deadline - monotonic())))
        try:
            return _verified_runtime_port(config, role)
        except RuntimeError as exc:
            first_error = exc
    remaining = max(.1, overall_deadline - monotonic())
    if helper_invoker is None:
        invoke_windows_helper(timeout=remaining)
    else:
        helper_invoker()
    last_error = first_error
    while True:
        try:
            return _verified_runtime_port(config, role)
        except RuntimeError as exc:
            last_error = exc
        if monotonic() >= overall_deadline:
            raise RuntimeError(
                f"bounded {role} USB reattachment failed after {timeout:g}s: {last_error}") from last_error
        sleeper(min(.5, max(0.0, overall_deadline - monotonic())))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def setup() -> int:
    provisional = {"HIL_IDF_ACTIVATE": str(Path.home() / ".espressif/tools/activate_idf_v6.0.3.sh")}
    devices, observations = discover(provisional)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Generated by make hil-setup; local fixture identity, never commit.",
             f"HIL_HUB_MAC={EXPECTED_HUB_MAC}", f"HIL_C3_MAC={EXPECTED_C3_MAC}",
             f"HIL_HUB_STABLE_PATH={devices['hub'].stable_path}",
             f"HIL_C3_STABLE_PATH={devices['c3'].stable_path}",
             f"HIL_HUB_USB_SERIAL={devices['hub'].serial_number or ''}",
             f"HIL_C3_USB_SERIAL={devices['c3'].serial_number or ''}",
             f"HIL_HUB_VID_PID={devices['hub'].vid or 0:04x}:{devices['hub'].pid or 0:04x}",
             f"HIL_C3_VID_PID={devices['c3'].vid or 0:04x}:{devices['c3'].pid or 0:04x}",
             f"HIL_EXPECTED_BRANCH={git('branch','--show-current')}",
             f"HIL_EXPECTED_COMMIT={git('rev-parse','HEAD')}",
             f"HIL_SOURCE_FINGERPRINT={source_fingerprint()}",
             f"HIL_IDF_ACTIVATE={provisional['HIL_IDF_ACTIVATE']}",
             "HIL_FLASH=auto", "HIL_REQUIRE_CLEAN=0"]
    CONFIG.write_text("\n".join(lines) + "\n")
    print("HIL SETUP: PASS (no flash performed)")
    for role, device in devices.items():
        print(f"{role}: {device.stable_path} chip={device.chip} mac={device.mac} "
              f"usb={device.vid!s}:{device.pid!s} serial={device.serial_number or 'none'}")
    print(f"Config: {CONFIG}")
    return 0


def preflight(config: dict[str, str] | None = None, quiet=False) -> tuple[dict[str, Device], dict]:
    if config is None:
        if not CONFIG.is_file(): raise RuntimeError(f"missing {CONFIG}; run make hil-setup")
        config = load_env(CONFIG)
    checks: dict[str, str] = {}
    required = {"HIL_HUB_MAC", "HIL_C3_MAC", "HIL_EXPECTED_BRANCH", "HIL_EXPECTED_COMMIT",
                "HIL_SOURCE_FINGERPRINT", "HIL_IDF_ACTIVATE"}
    missing = sorted(required - config.keys())
    if missing: raise RuntimeError(f"invalid HIL config; missing {missing}")
    if git("branch", "--show-current") != config["HIL_EXPECTED_BRANCH"]:
        raise RuntimeError("repository branch differs from HIL setup")
    if git("rev-parse", "HEAD") != config["HIL_EXPECTED_COMMIT"]:
        raise RuntimeError("repository commit differs from HIL setup; rerun setup")
    if source_fingerprint() != config["HIL_SOURCE_FINGERPRINT"]:
        raise RuntimeError("source changed since HIL setup; rerun setup")
    dirty = bool(git("status", "--porcelain"))
    if config.get("HIL_REQUIRE_CLEAN", "1") == "1" and dirty:
        raise RuntimeError("HIL configuration requires a clean source tree")
    checks["repo"] = f"branch/commit/fingerprint match dirty={dirty}"
    script = activation(config)
    if not script.is_file(): raise RuntimeError(f"ESP-IDF activation missing: {script}")
    cp = idf_command(config, "idf.py --version && esptool version", PRODUCT, 60)
    if cp.returncode: raise RuntimeError(f"ESP-IDF/esptool unavailable: {cp.stdout[-1000:]}")
    checks["idf"] = (cp.stdout or "").strip().replace("\n", "; ")
    import serial  # dependency check
    checks["pyserial"] = serial.VERSION
    free = shutil.disk_usage(REPO).free
    if free < 2 * 1024**3: raise RuntimeError(f"insufficient disk space: {free} bytes")
    checks["disk_free_bytes"] = str(free)
    ac_values = []
    for path in Path("/sys/class/power_supply").glob("*/online"):
        with contextlib.suppress(OSError): ac_values.append(path.read_text().strip())
    checks["ac_power"] = "online" if "1" in ac_values else "unknown/offline; keep laptop on AC"
    devices, observations = discover(config)
    for role, device in devices.items():
        import serial
        try:
            stream = serial.Serial(device.port, 115200, timeout=.2, exclusive=True)
            stream.close()
        except Exception as exc:
            raise RuntimeError(f"{role} serial unavailable/stale owner on {device.port}: {exc}") from exc
        checks[role] = f"{device.chip} mac={device.mac} path={device.stable_path}"
    if platform.system() == "Linux" and "microsoft" in platform.release().lower():
        checks["warning_wsl"] = "WSL detected: prevent Windows sleep and preserve USB attachment"
    checks["warning_power"] = "Best effort only: keep laptop on AC and disable sleep manually"
    if not quiet:
        print("HIL PREFLIGHT: PASS")
        for key, value in checks.items(): print(f"- {key}: {value}")
    return devices, {"checks": checks, "observed": [vars(x) for x in observations],
                     "config": config}


def build_pair(config: dict[str, str], run_dir: Path) -> dict:
    cp = subprocess.run([sys.executable, "scripts/build_hil_pair.py"], cwd=PRODUCT,
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        timeout=3600)
    (run_dir / "pair_build.log").write_text(cp.stdout or "")
    if cp.returncode: raise RuntimeError("HIL pair build failed")
    manifest = json.loads(MANIFEST.read_text())
    if not manifest.get("hil_control") or manifest["source_fingerprint"] != source_fingerprint():
        raise RuntimeError("HIL pair provenance mismatch")
    if manifest["c3"]["sha256"] != manifest["hub_embedding_input"]["sha256"]:
        raise RuntimeError("standalone and embedded C3 images differ")
    (run_dir / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def flash(config: dict[str, str], devices: dict[str, Device], manifest: dict, run_dir: Path):
    state_path = CONFIG.with_name("hil.flash-state.json")
    desired = {"hub": manifest["hub"]["sha256"], "c3": manifest["c3"]["sha256"]}
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    if config.get("HIL_FLASH", "auto") == "auto" and state == desired:
        return
    for role, project in (("hub", HUB_PROJECT), ("c3", NODE_PROJECT)):
        current, _ = discover(config)
        port = current[role].port
        cp = idf_command(config, f"idf.py -p {shlex.quote(port)} flash", project, 900)
        (run_dir / f"{role}_flash.log").write_text(cp.stdout or "")
        if cp.returncode: raise RuntimeError(f"{role} flash failed")
        time.sleep(2)
        rediscovered, _ = discover(config)
        if rediscovered[role].mac != devices[role].mac:
            raise RuntimeError(f"{role} identity changed after flash")
    state_path.write_text(json.dumps(desired, indent=2) + "\n")


class Campaign:
    def __init__(self, mode: str, config: dict[str, str], devices: dict[str, Device],
                 manifest: dict, run_dir: Path):
        self.mode, self.config, self.devices, self.manifest, self.run_dir = mode, config, devices, manifest, run_dir
        self.results = Results(); self.hub = None; self.c3 = None
        self.recovery_status = "RECOVERY_NOT_ATTEMPTED"

    def start_capture(self):
        current, _ = discover(self.config)
        self.hub = SerialCapture("hub", current["hub"].port, self.run_dir / "hub_serial.log",
                                 port_resolver=lambda: runtime_port(self.config, "hub"))
        self.c3 = SerialCapture("c3", current["c3"].port, self.run_dir / "c3_serial.log",
                                port_resolver=lambda: runtime_port(self.config, "c3"))
        self.hub.start(); self.c3.start(); time.sleep(.5)

    def close(self):
        if self.hub: self.hub.close()
        if self.c3: self.c3.close()

    def pass_ids(self, ids: list[str], detail: str):
        for tc in ids: self.results.add(tc, "PASS", detail)

    def scenario(self, ids: list[str], fn, name: str) -> bool:
        try:
            fn(); self.pass_ids(ids, f"real-target {name} evidence captured"); return True
        except Exception as exc:
            self.results.add(ids[0], "FAIL", f"{type(exc).__name__}: {exc}")
            for tc in ids[1:]: self.results.add(tc, "BLOCKED_BY_FIXTURE_STATE", f"blocked after {ids[0]}")
            (self.run_dir / "failures").mkdir(exist_ok=True)
            (self.run_dir / "failures" / f"{ids[0]}.txt").write_text(f"{type(exc).__name__}: {exc}\n")
            return False

    def command(self, target: SerialCapture, command: str, expect: str | None = None, timeout=8):
        cursor = target.cursor(); target.send(command)
        return target.wait_for(expect or rf"HIL_OK command={re.escape(command)}", timeout, cursor)

    def motion(self, timeout=20):
        h = self.hub.cursor(); c = self.c3.cursor()
        self.command(self.c3, "INJECT_MOTION")
        self.c3.wait_for(r"PIR -> NodeRuntime", 8, c)
        self.c3.wait_for(r"NodeMessage sent", 10, c)
        self.hub.wait_for(r"Processed session=.*ack_send=ESP_OK", timeout, h)
        self.c3.wait_for(r"Application ACK .*retired=1", timeout, c)

    def reboot(self, target: SerialCapture, role: str, timeout=25):
        # Capture the evidence boundary before writing the command.  This
        # prevents a stale reset/ready line from proving a new restart.
        cursor = target.cursor(); target.send("SOFTWARE_RESTART")
        # reset_class is retained as useful diagnostics, but a normalized ROM
        # software-reset reason is mandatory.  This avoids treating a
        # pre-reset acknowledgement as proof by itself when UART output is
        # truncated while esp_restart() resets the target.
        target.wait_for_predicate(
            lambda line: normalize_rom_reset_class(line) == SOFTWARE_RESET_EVIDENCE,
            "normalized SOFTWARE_RESET ROM evidence", 5, cursor)
        target.wait_for(rf"HIL_READY role={role} protocol=1 version={re.escape(self.manifest['image_version'])}", timeout, cursor)
        # HIL_READY means that the command parser is alive, not that every
        # sensing boundary has been initialized.  The C3 PIR task announces
        # its own readiness roughly ten seconds later on the real target.
        # Do not inject synthetic motion into a not-yet-live sensing path.
        if role == "c3":
            target.wait_for(r"PIR ready on GPIO", timeout, cursor)

    def smoke(self):
        def run():
            self.reboot(self.hub, "hub"); self.reboot(self.c3, "c3")
            self.command(self.hub, "GET_STATE", r"HIL_STATE role=hub")
            first_state = self.command(self.c3, "GET_STATE", r"HIL_STATE role=c3")
            self.command(self.c3, "GET_HEALTH")
            self.hub.wait_for(r"NodeHealth schema=", 15)
            self.motion()
            final_state = self.command(self.c3, "GET_STATE", r"HIL_STATE role=c3 .*retained=0 in_flight=0")
            first_live = int(re.search(r"runtime_live=(\d+)", first_state).group(1))
            final_live = int(re.search(r"runtime_live=(\d+)", final_state).group(1))
            first_sensing = int(re.search(r"sensing_live=(\d+)", first_state).group(1))
            final_sensing = int(re.search(r"sensing_live=(\d+)", final_state).group(1))
            if final_live <= first_live or final_sensing <= first_sensing:
                raise RuntimeError("runtime/sensing liveness did not progress")
            self._check_resets_resources()
        return self.scenario(SMOKE_IDS, run, "discovery/identity/pair/boot/health/motion/ACK/idle/resources")

    def radio(self):
        def run():
            self.motion(); time.sleep(.3); self.motion(); time.sleep(2); self.motion()
            self.reboot(self.hub, "hub"); self.motion()
            self.reboot(self.c3, "c3"); cursor = self.hub.cursor()
            self.command(self.c3, "GET_HEALTH")
            self.hub.wait_for(r"NodeHealth schema=", 15, cursor); self.motion()
            for _ in range(9): self.motion(timeout=25); time.sleep(.25)
            self.command(self.c3, "GET_HEALTH")
            self.hub.wait_for(r"NodeHealth schema=.*tx=.*mac_ok=.*RSSI=.*CH=", 15)
            self.command(self.c3, "GET_STATE", r"retained=0 in_flight=0")
        return self.scenario(RADIO_IDS, run, "ESP-NOW baseline/repeat/ACK/health/idle/restart recovery/burst")

    def offline(self):
        def run():
            self.motion(); self.command(self.hub, "SET_HUB_LOGICAL_OFFLINE")
            start = self.c3.cursor()
            for _ in range(3): self.command(self.c3, "INJECT_MOTION"); time.sleep(.3)
            self.c3.wait_for(r"NodeMessage sent", 8, start)
            retry_cursor = self.c3.cursor()
            self.c3.wait_for(r"NodeMessage sent", 12, retry_cursor)
            self.command(self.c3, "GET_STATE", r"HIL_STATE role=c3 .*retained=[1-9]")
            cursor = self.hub.cursor()
            self.command(self.hub, "SET_HUB_LOGICAL_ONLINE")
            self.command(self.c3, "INJECT_MOTION")
            self.hub.wait_count(r"Processed session=", 4, 30, cursor)
            self.c3.wait_for(r"Application ACK .*retired=1", 25, start)
            for _ in range(2):
                self.command(self.hub, "SET_HUB_LOGICAL_OFFLINE"); self.command(self.c3, "INJECT_MOTION")
                time.sleep(2); self.command(self.hub, "SET_HUB_LOGICAL_ONLINE"); time.sleep(3)
            self.command(self.c3, "GET_STATE", r"retained=0 in_flight=0", 25)
            health_cursor = self.hub.cursor(); self.command(self.c3, "GET_HEALTH")
            self.hub.wait_for(r"NodeHealth schema=", 15, health_cursor)
            self._check_resets_resources()
        return self.scenario(OR_IDS, run, "logical outage/retention/retry/recovery/drain/cycles")

    def hub_restart(self):
        def run():
            self.reboot(self.hub, "hub"); self.motion()
            self.command(self.hub, "SET_HUB_LOGICAL_OFFLINE")
            self.command(self.c3, "INJECT_MOTION"); time.sleep(1)
            self.reboot(self.hub, "hub"); self.motion()
            self.reboot(self.hub, "hub"); self.motion()
            self.command(self.c3, "GET_STATE", r"retained=0 in_flight=0")
        return self.scenario(HUB_RST_IDS, run, "Hub software restart idle/pending/repeated/recovery")

    def c3_restart(self):
        def run():
            old = self._last_session()
            cursor = self.hub.cursor(); self.reboot(self.c3, "c3"); self.command(self.c3, "GET_HEALTH")
            line = self.hub.wait_for(r"NodeHealth schema=.*session=", 15, cursor)
            new = int(re.search(r"session=(\d+)", line).group(1))
            if old and new <= old: raise RuntimeError(f"C3 session did not advance: {old}->{new}")
            self.motion(); self.reboot(self.c3, "c3"); self.motion()
        return self.scenario(C3_RST_IDS, run, "C3 software reset/session/health/motion/ACK/repeat")

    def both_restart(self):
        def run():
            self.reboot(self.hub, "hub"); self.reboot(self.c3, "c3"); self.motion()
            self.reboot(self.c3, "c3"); self.reboot(self.hub, "hub"); self.motion()
            hc, cc = self.hub.cursor(), self.c3.cursor()
            self.hub.send("SOFTWARE_RESTART"); self.c3.send("SOFTWARE_RESTART")
            for target, start in ((self.hub, hc), (self.c3, cc)):
                target.wait_for_predicate(
                    lambda line: normalize_rom_reset_class(line) == SOFTWARE_RESET_EVIDENCE,
                    "normalized SOFTWARE_RESET ROM evidence", 5, start)
            version = re.escape(self.manifest['image_version'])
            self.hub.wait_for(rf"HIL_READY role=hub protocol=1 version={version}", 25, hc)
            self.c3.wait_for(rf"HIL_READY role=c3 protocol=1 version={version}", 25, cc)
            self.c3.wait_for(r"PIR ready on GPIO", 25, cc)
            self.motion()
        return self.scenario(BOTH_RST_IDS, run, "independent and near-simultaneous software restart")

    def _last_session(self) -> int:
        for line in reversed(self.hub.lines):
            match = re.search(r"NodeHealth schema=.*session=(\d+)", line)
            if match: return int(match.group(1))
        return 0

    def _check_resets_resources(self):
        combined = "\n".join(self.hub.lines + self.c3.lines)
        if re.search(r"reset=(4|5|6|7|8|9|14|15)\b|BROWNOUT|WATCHDOG", combined, re.I):
            raise RuntimeError("unexpected watchdog/brownout reset")
        heaps = [int(x) for x in re.findall(r"(?:heap|min_heap)=(\d+)", combined)]
        if heaps and min(heaps) < 8192: raise RuntimeError(f"unsafe free heap: {min(heaps)}")
        states = [int(x) for x in re.findall(r"HIL_STATE role=(?:c3|hub).*? heap=(\d+)", combined)]
        if len(states) > 1 and states[-1] < states[0] * .7:
            raise RuntimeError(f"obvious progressive heap degradation: {states[0]}->{states[-1]}")
        health_lines = [line for line in self.hub.lines if "NodeHealth schema=" in line]
        if health_lines:
            latest = health_lines[-1]
            for field in ("store_full", "motion_drop", "priority_rejected"):
                match = re.search(rf"{field}=(\d+)", latest)
                if match and int(match.group(1)) != 0:
                    raise RuntimeError(f"unexpected {field}={match.group(1)}")

    def recover(self) -> bool:
        try:
            self.reboot(self.hub, "hub")
            health_cursor = self.hub.cursor()
            self.reboot(self.c3, "c3")
            self.command(self.c3, "GET_HEALTH")
            self.hub.wait_for(r"NodeHealth schema=", 15, health_cursor)
            self.motion(); self.recovery_status = "RECOVERED"; return True
        except Exception as exc:
            code = self._recovery_failure_code(exc)
            self.recovery_status = code
            detail = f"{code}: {type(exc).__name__}: {exc}"
            failures = self.run_dir / "failures"
            failures.mkdir(parents=True, exist_ok=True)
            (failures / "recovery.txt").write_text(detail + "\n")
            return False

    @staticmethod
    def _recovery_failure_code(exc: Exception) -> str:
        """Make recovery evidence distinguish transport, boot and HIL failures."""
        detail = str(exc)
        if "bounded c3 USB reattachment failed" in detail:
            return "RECOVERY_FAILED_C3_TTY_TIMEOUT"
        if "bounded hub USB reattachment failed" in detail:
            return "RECOVERY_FAILED_HUB_TTY_TIMEOUT"
        if "reconnect identity" in detail or "cannot uniquely rediscover" in detail:
            return "RECOVERY_FAILED_IDENTITY"
        if "USB reconnect failed" in detail or "serial stopped" in detail:
            return "RECOVERY_FAILED_SERIAL_RECONNECT"
        if "PIR ready on GPIO" in detail:
            return "RECOVERY_FAILED_C3_SENSING_READY_TIMEOUT"
        if "HIL_READY role=" in detail:
            return "RECOVERY_FAILED_BOOT_READY_TIMEOUT"
        if "NodeHealth schema=" in detail or "GET_HEALTH" in detail:
            return "RECOVERY_FAILED_HIL_HEALTH_TIMEOUT"
        if "PIR -> NodeRuntime" in detail or "NodeMessage sent" in detail:
            return "RECOVERY_FAILED_POST_RESTART_MOTION_TIMEOUT"
        return "RECOVERY_FAILED_UNKNOWN"


def run_campaign(mode: str) -> int:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = RUNS / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "failures").mkdir()
    campaign = None; overall_error = None
    with FixtureLock(LOCK):
        try:
            devices, info = preflight(quiet=True); config = info["config"]
            manifest = build_pair(config, run_dir); flash(config, devices, manifest, run_dir)
            campaign = Campaign(mode, config, devices, manifest, run_dir); campaign.start_capture()
            healthy = campaign.smoke()
            if mode == "regression" and healthy:
                for suite in (campaign.radio, campaign.offline, campaign.hub_restart,
                              campaign.c3_restart, campaign.both_restart):
                    if not suite():
                        recovered = campaign.recover()
                        print("FIXTURE RECOVERY:", campaign.recovery_status)
                        if not recovered: break
            expected = SMOKE_IDS if mode == "smoke" else (SMOKE_IDS + RADIO_IDS + OR_IDS + HUB_RST_IDS + C3_RST_IDS + BOTH_RST_IDS)
            recorded = {row["id"] for row in campaign.results.rows}
            for tc in expected:
                if tc not in recorded:
                    campaign.results.add(tc, "BLOCKED_BY_FIXTURE_STATE",
                                         "earlier mandatory scenario left fixture state unqualified")
            gaps = [("PHYSICAL-HUB-POWER", "true electrical Hub power cut"),
                    ("PHYSICAL-C3-POWER", "true electrical C3 power cut"),
                    ("PHYSICAL-BROWNOUT", "controlled brownout requires power fixture"),
                    ("PHYSICAL-CURRENT", "current/battery endurance requires instrumentation"),
                    ("PHYSICAL-PIR", "AM312 optical sensitivity needs physical stimulus fixture"),
                    ("PHYSICAL-RF", "house-range RF/thermal qualification needs external fixture")]
            for tc, detail in gaps: campaign.results.add(tc, "BLOCKED_EXTRA_FIXTURE", detail)
        except KeyboardInterrupt:
            overall_error = "interrupted by user"
        except Exception as exc:
            overall_error = f"{type(exc).__name__}: {exc}"
        finally:
            if campaign: campaign.close()
    if campaign is None:
        results = Results(); results.add("HIL-PREFLIGHT", "FAIL", overall_error or "startup failed")
        metadata = {"commit": git("rev-parse", "HEAD"), "mode": mode, **host_metadata()}
        for name in ("hub_serial.log", "c3_serial.log"):
            (run_dir / name).touch()
        if not (run_dir / "provenance.json").exists():
            (run_dir / "provenance.json").write_text(json.dumps({"status": "UNAVAILABLE", "reason": overall_error}, indent=2) + "\n")
    else:
        results = campaign.results
        if overall_error: results.add("HIL-RUNNER", "FAIL", overall_error)
        metadata = {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
                    "mode": mode, "hub": manifest["hub"], "c3": manifest["c3"],
                    "embedded_c3": manifest["hub_embedding_input"], **host_metadata()}
    payload = write_report(run_dir, metadata, results)
    latest = RUNS.parent / "latest.txt"; latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(str(run_dir) + "\n")
    counts = results.counts()
    print(f"HIL {mode.upper()}: {payload['overall']}")
    print(f"commit={metadata['commit']}")
    if campaign:
        print(f"Hub version={manifest['hub']['app_version']} sha256={manifest['hub']['sha256']}")
        print(f"C3 version={manifest['c3']['app_version']} sha256={manifest['c3']['sha256']}")
        for label, prefix in (("smoke", "HIL-SMOKE-"), ("radio", "HIL-RADIO-"),
                              ("offline", "HIL-OR-"), ("Hub restart", "HIL-HUB-RST-"),
                              ("C3 restart", "HIL-C3-RST-"), ("both-target restart", "HIL-BOTH-RST-")):
            rows = [row for row in results.rows if row["id"].startswith(prefix)]
            state = "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL/BLOCKED"
            print(f"{label}={state}")
        serial_text = "\n".join(campaign.hub.lines + campaign.c3.lines)
        resets = len(re.findall(r"reset=(4|5|6|7|8|9|14|15)\b|BROWNOUT|WATCHDOG", serial_text, re.I))
        states = re.findall(r"HIL_STATE role=c3 .*retained=(\d+) in_flight=(\d+)", serial_text)
        final_retained, final_in_flight = states[-1] if states else ("unknown", "unknown")
        print(f"unexpected_resets={resets} final_retained={final_retained} final_in_flight={final_in_flight}")
    print(f"PASS={counts['PASS']} FAIL={counts['FAIL']} "
          f"BLOCKED={counts['BLOCKED_EXTRA_FIXTURE'] + counts['BLOCKED_BY_FIXTURE_STATE']}")
    print(f"overall={payload['overall']}")
    print(f"report={run_dir}")
    return 0 if payload["overall"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("setup", "preflight", "smoke", "regression"))
    args = parser.parse_args()
    try:
        if args.command == "setup": return setup()
        if args.command == "preflight": preflight(); return 0
        return run_campaign(args.command)
    except Exception as exc:
        print(f"HIL {args.command.upper()}: FAIL — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__": raise SystemExit(main())
