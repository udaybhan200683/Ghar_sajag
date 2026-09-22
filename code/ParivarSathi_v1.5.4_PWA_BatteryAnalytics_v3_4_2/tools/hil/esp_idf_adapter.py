#!/usr/bin/env python3
"""Repository ESP-IDF HIL adapter.

Automates only capabilities the current targets safely expose: clean paired
build/provenance, station-MAC identity, deterministic IDF flash, serial capture,
boot readiness, and NodeHealth collection. Missing runtime control seams are
reported BLOCKED; they are never converted into a PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
NODE = ROOT / "firmware/node/target/esp32c3/idf"
HUB = ROOT / "firmware/hub/target/esp32/idf"
MANIFEST = ROOT / "build/hw_pair/provenance.json"


def activation_script() -> Path:
    path = Path(os.environ.get(
        "HW_IDF_ACTIVATE", str(Path.home() / ".espressif/tools/activate_idf_v6.0.3.sh")))
    if not path.is_file():
        raise RuntimeError(f"ESP-IDF activation script not found: {path}")
    return path


def idf_shell(command: str, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    activate = shlex.quote(str(activation_script()))
    return subprocess.run(["bash", "-lc", f"source {activate}; {command}"], cwd=cwd,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout, env={**os.environ, "PYTHONUNBUFFERED": "1"})


def normalize_identity(value: str) -> str:
    return re.sub(r"[^0-9a-f]", "", value.lower())


def read_mac(port: str) -> tuple[str, str]:
    cp = idf_shell(f"esptool --port {shlex.quote(port)} read-mac", ROOT, 60)
    match = re.search(r"MAC:\s*([0-9a-fA-F:.-]{12,})", cp.stdout or "")
    if cp.returncode or not match:
        raise RuntimeError(f"cannot read target MAC on {port}: {(cp.stdout or '')[-2000:]}")
    return normalize_identity(match.group(1)), cp.stdout or ""


def resolve_ports(hub: str, c3: str, expected_hub: str, expected_c3: str) -> tuple[str, str, dict[str, str]]:
    requested = {"hub": hub, "c3": c3}
    candidates = sorted({item.device for item in list_ports.comports()})
    for role in ("hub", "c3"):
        if requested[role] and requested[role].lower() != "auto":
            candidates.append(requested[role])
    observations: dict[str, str] = {}
    by_mac: dict[str, str] = {}
    for port in sorted(set(candidates)):
        try:
            mac, _ = read_mac(port)
            observations[port] = mac
            by_mac[mac] = port
        except RuntimeError as exc:
            observations[port] = f"ERROR: {exc}"
    expected = {"hub": normalize_identity(expected_hub), "c3": normalize_identity(expected_c3)}
    resolved = {}
    for role in ("hub", "c3"):
        explicit = requested[role]
        if explicit and explicit.lower() != "auto":
            resolved[role] = explicit
        elif expected[role] in by_mac:
            resolved[role] = by_mac[expected[role]]
        else:
            raise RuntimeError(f"could not auto-discover {role} MAC {expected[role]}; observed={observations}")
        actual = observations.get(resolved[role])
        if actual != expected[role]:
            raise RuntimeError(f"{role} identity mismatch on {resolved[role]}: expected {expected[role]}, got {actual}")
    if resolved["hub"] == resolved["c3"]:
        raise RuntimeError("Hub and C3 resolved to the same serial port")
    return resolved["hub"], resolved["c3"], observations


class SerialCapture:
    def __init__(self, port: str, path: Path):
        self.port = port
        self.path = path
        self.stop = threading.Event()
        self.lines: list[str] = []
        self.error = ""
        self.thread = threading.Thread(target=self._run, name=f"hil-{path.stem}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        try:
            with serial.Serial(self.port, 115200, timeout=0.25, exclusive=True) as stream:
                while not self.stop.is_set():
                    raw = stream.readline()
                    if raw:
                        self.lines.append(raw.decode("utf-8", errors="replace"))
        except Exception as exc:  # evidence, assessed by caller
            self.error = f"{type(exc).__name__}: {exc}"

    def finish(self) -> str:
        self.stop.set()
        self.thread.join(timeout=3)
        text = "".join(self.lines)
        if self.error:
            text += f"\nSERIAL_CAPTURE_ERROR: {self.error}\n"
        self.path.write_text(text)
        return text


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage(identifier: str, status: str, detail: str) -> dict[str, str]:
    return {"id": identifier, "status": status, "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-port", required=True)
    parser.add_argument("--c3-port", required=True)
    parser.add_argument("--expected-hub-id", required=True,
                        help="qualified Hub station MAC")
    parser.add_argument("--expected-c3-id", required=True,
                        help="qualified C3 station MAC")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--soak-minutes", type=int, default=0)
    args = parser.parse_args()
    evidence = args.report.parent
    evidence.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"schema": 1, "status": "BLOCKED", "commit": args.commit,
                                 "suites": [], "capabilities": {}, "reasons": []}
    captures: list[SerialCapture] = []
    started = time.monotonic()
    try:
        actual_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        if actual_commit != args.commit:
            raise RuntimeError(f"commit changed before HIL: {actual_commit} != {args.commit}")
        hub_port, c3_port, discovery = resolve_ports(
            args.hub_port, args.c3_port, args.expected_hub_id, args.expected_c3_id)
        report["port_discovery"] = discovery
        report["resolved_ports"] = {"hub": hub_port, "c3": c3_port}

        build = subprocess.run([sys.executable, "scripts/build_hw_pair.py"], cwd=ROOT,
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=3600)
        (evidence / "pair-build.log").write_text(build.stdout or "")
        if build.returncode:
            raise RuntimeError("clean paired build failed; see pair-build.log")
        manifest = json.loads(MANIFEST.read_text())
        if manifest.get("git_commit_full") != args.commit or manifest.get("git_dirty") is not False:
            raise RuntimeError("paired-build provenance does not match clean requested commit")

        # Flash Hub first and capture it while the C3 is flashed. Each idf.py
        # flash is scoped to its explicit project and explicit verified port.
        hub_flash = idf_shell(f"idf.py -p {shlex.quote(hub_port)} flash", HUB)
        (evidence / "hub-flash.log").write_text(hub_flash.stdout or "")
        if hub_flash.returncode: raise RuntimeError("Hub flash failed")
        hub_capture = SerialCapture(hub_port, evidence / "hub-serial.log")
        hub_capture.start(); captures.append(hub_capture)

        c3_flash = idf_shell(f"idf.py -p {shlex.quote(c3_port)} flash", NODE)
        (evidence / "c3-flash.log").write_text(c3_flash.stdout or "")
        if c3_flash.returncode: raise RuntimeError("C3 flash failed")
        c3_capture = SerialCapture(c3_port, evidence / "c3-serial.log")
        c3_capture.start(); captures.append(c3_capture)

        capture_seconds = max(75, args.soak_minutes * 60)
        deadline = time.monotonic() + capture_seconds
        while time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
        hub_text = hub_capture.finish(); captures.remove(hub_capture)
        c3_text = c3_capture.finish(); captures.remove(c3_capture)

        hub_ready = "HubRuntime owner started" in hub_text
        c3_ready = "NodeRuntime owner started" in c3_text
        health = "NodeHealth schema=" in hub_text
        suites = report["suites"]
        assert isinstance(suites, list)
        suites.append(stage("HIL-SMOKE", "PASS" if hub_ready and c3_ready and health else "BLOCKED",
                            f"hub_ready={hub_ready} c3_ready={c3_ready} node_health={health}"))
        suites += [
            stage("HIL-OFFLINE", "BLOCKED", "no HIL-only logical Hub receive-disable/enable control exists"),
            stage("HIL-FOTA", "BLOCKED", "C3 FOTA trigger is physical Hub BOOT long-press only; no test-only software trigger exists"),
            stage("HIL-RESTART", "BLOCKED", "no target command/acknowledgement seam for deterministic software restart and state collection"),
            stage("HIL-STRESS", "BLOCKED", "no HIL-only synthetic motion or deterministic transport-fault injection seam exists"),
            stage("HIL-SOAK", "BLOCKED", "serial/NodeHealth capture exists but event injection and final state query do not"),
        ]
        report["hub"] = {"identity": args.expected_hub_id,
                         "version": manifest["hub"]["app_version"],
                         "sha256": sha256(ROOT / str(manifest["hub"]["path"]))}
        report["c3"] = {"identity": args.expected_c3_id,
                        "version": manifest["c3"]["app_version"],
                        "sha256": sha256(ROOT / str(manifest["c3"]["path"]))}
        report["capabilities"] = {
            "auto_port_discovery_by_mac": True, "paired_clean_build": True,
            "artifact_hashes_and_provenance": True, "target_flash": True,
            "serial_capture": True, "readiness_detection": True,
            "node_health_collection": health, "logical_hub_outage": False,
            "synthetic_motion": False, "transport_fault": False,
            "software_fota_trigger": False, "software_restart": False,
            "electrical_power_cycle": False,
        }
        report["reasons"] = [row["detail"] for row in suites if row["status"] == "BLOCKED"]
    except Exception as exc:
        report["status"] = "BLOCKED"
        report["reasons"] = [f"{type(exc).__name__}: {exc}"]
    finally:
        for capture in captures:
            capture.finish()
        report["duration"] = round(time.monotonic() - started, 3)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"ESP-IDF HIL ADAPTER: {report['status']}")
    for reason in report.get("reasons", []): print(f"- {reason}")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
