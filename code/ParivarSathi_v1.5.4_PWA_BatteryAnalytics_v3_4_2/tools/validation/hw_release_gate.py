#!/usr/bin/env python3
"""Repeatable software/target gate for the HW-M1 firmware compositions.

This gate validates host code, the two ESP-IDF compositions, fixed partition
invariants, qualified target constants, and image size. Connected Phase-1 HIL
is invoked only with --hil; otherwise its fixture status is explicit and no
physical PASS is claimed. FOTA, power, performance, and endurance remain
outside Phase 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parents[1]
NODE_PROJECT = ROOT / "firmware/node/target/esp32c3/idf"
HUB_PROJECT = ROOT / "firmware/hub/target/esp32/idf"
NODE_BINARY = NODE_PROJECT / "build/gs_hw_m1_node.bin"
HUB_BINARY = HUB_PROJECT / "build/gs_hw_m1_hub.bin"
OTA_SLOT_BYTES = 0x1E0000
DEFAULT_OTA_WARNING_PERCENT = 15.0

EXPECTED_PARTITIONS = {
    "nvs": ("data", "nvs", 0x9000, 0x6000),
    "otadata": ("data", "ota", 0xF000, 0x2000),
    "phy_init": ("data", "phy", 0x11000, 0x1000),
    "ota_0": ("app", "ota_0", 0x20000, 0x1E0000),
    "ota_1": ("app", "ota_1", 0x200000, 0x1E0000),
}


@dataclass(frozen=True)
class ImageCheck:
    ok: bool
    warning: bool
    size: int
    headroom: int
    percent: float
    detail: str


def evaluate_image_size(size: int, slot_size: int = OTA_SLOT_BYTES,
                        warning_percent: float = DEFAULT_OTA_WARNING_PERCENT) -> ImageCheck:
    """Evaluate a binary against its OTA slot without touching the filesystem."""
    headroom = slot_size - size
    percent = (headroom / slot_size) * 100.0 if slot_size else 0.0
    if size > slot_size:
        return ImageCheck(False, False, size, headroom, percent,
                          f"size={size} exceeds slot={slot_size}")
    warning = percent <= warning_percent
    detail = (f"size={size} headroom={headroom} ({percent:.1f}%)"
              + (f" warning_threshold={warning_percent:.1f}%" if warning else ""))
    return ImageCheck(True, warning, size, headroom, percent, detail)


def parse_number(value: str) -> int:
    value = value.strip()
    if not value:
        raise ValueError("empty numeric field")
    return int(value, 0)


def parse_partitions(path: Path) -> dict[str, tuple[str, str, int, int]]:
    """Parse the small CSV format used by both checked-in ESP-IDF projects."""
    rows: dict[str, tuple[str, str, int, int]] = {}
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 fields")
        name, kind, subtype, offset, size = fields
        if name in rows:
            raise ValueError(f"{path}:{line_number}: duplicate partition {name}")
        rows[name] = (kind, subtype, parse_number(offset), parse_number(size))
    return rows


def partition_errors(path: Path) -> list[str]:
    if not path.is_file():
        return [f"missing partition file: {path}"]
    try:
        actual = parse_partitions(path)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors: list[str] = []
    for name, expected in EXPECTED_PARTITIONS.items():
        if actual.get(name) != expected:
            errors.append(f"{name}: expected {expected}, got {actual.get(name)}")
    unexpected = sorted(set(actual) - set(EXPECTED_PARTITIONS))
    if unexpected:
        errors.append(f"unexpected partitions: {', '.join(unexpected)}")
    for name, (_, _, offset, size) in actual.items():
        if offset + size > 0x400000:
            errors.append(f"{name}: exceeds 4 MB flash")
    return errors


def config_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        if raw.startswith("CONFIG_") and "=" in raw:
            key, value = raw.split("=", 1)
            values[key] = value
    return values


def rollback_errors(project: Path) -> list[str]:
    errors: list[str] = []
    defaults = config_values(project / "sdkconfig.defaults")
    if defaults.get("CONFIG_ESPTOOLPY_FLASHSIZE_4MB") != "y":
        errors.append(f"{project}: 4 MB flash default is not enabled")
    if defaults.get("CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE") != "y":
        errors.append(f"{project}: rollback default is not enabled")
    generated = project / "sdkconfig"
    if generated.is_file():
        values = config_values(generated)
        if values.get("CONFIG_ESPTOOLPY_FLASHSIZE_4MB") != "y":
            errors.append(f"{project}: generated config is not 4 MB")
        if values.get("CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE") != "y":
            errors.append(f"{project}: generated rollback is not enabled")
    return errors


def missing_patterns(text: str, patterns: Iterable[tuple[str, str]]) -> list[str]:
    return [label for label, pattern in patterns if re.search(pattern, text, re.MULTILINE) is None]


def config_invariant_errors() -> list[str]:
    node_config = (ROOT / "firmware/node/target/esp32c3/node_target_config.hpp")
    node_adapter = (ROOT / "firmware/node/target/esp32c3/node_runtime_adapter.cpp")
    hub_config = (ROOT / "firmware/hub/target/esp32/hub_target_config.hpp")
    hub_adapter = (ROOT / "firmware/hub/target/esp32/hub_runtime_adapter.cpp")
    required = {
        node_config: [
            ("C3 PIR GPIO4", r"kPirGpio\s*=\s*4\b"),
            ("C3 LED GPIO8", r"kLedGpio\s*=\s*8\b"),
            ("C3 LED active-low", r"kLedActiveLow\s*=\s*true\b"),
            ("C3 channel 1", r"kEspNowChannel\s*=\s*1\b"),
            ("C3 TX API 40", r"kTxPowerQuarterDbm\s*=\s*40\b"),
        ],
        node_adapter: [
            ("C3 channel applied", r"esp_wifi_set_channel\(kEspNowChannel"),
            ("C3 TX power applied", r"esp_wifi_set_max_tx_power\(kTxPowerQuarterDbm"),
        ],
        hub_config: [("Hub channel 1", r"kEspNowChannel\s*=\s*1\b")],
        hub_adapter: [("Hub channel applied", r"esp_wifi_set_channel\(kEspNowChannel")],
    }
    errors: list[str] = []
    for path, patterns in required.items():
        if not path.is_file():
            errors.append(f"missing invariant source: {path}")
            continue
        errors.extend(f"{path}: {label}" for label in missing_patterns(path.read_text(), patterns))
    return errors


def structural_errors() -> list[str]:
    required_files = [
        ROOT / "firmware/common/transport/data_plane_codec.hpp",
        ROOT / "firmware/common/transport/data_plane_codec.cpp",
        ROOT / "firmware/common/transport/fota_protocol.hpp",
        NODE_PROJECT / "CMakeLists.txt",
        NODE_PROJECT / "main/CMakeLists.txt",
        NODE_PROJECT / "main/fota_receiver.cpp",
        HUB_PROJECT / "CMakeLists.txt",
        HUB_PROJECT / "main/CMakeLists.txt",
        HUB_PROJECT / "main/fota_sender.cpp",
        ROOT / "scripts/build_hw_pair.py",
        REPO_ROOT / "docs/hw/evidence/HW_M1_2/README.md",
        REPO_ROOT / "docs/hw/evidence/HW_M1_FOTA/README.md",
    ]
    errors = [f"missing required artifact: {path}" for path in required_files if not path.is_file()]
    source_roots = [ROOT / "firmware/common/transport", ROOT / "firmware/node/target",
                    ROOT / "firmware/hub/target"]
    for source_root in source_roots:
        if not source_root.is_dir():
            continue
        for path in source_root.rglob("*"):
            if path.suffix not in {".c", ".cc", ".cpp", ".h", ".hpp"}:
                continue
            text = path.read_text(errors="replace")
            if "docs/hw/evidence" in text or "HW_M1_2" in text or "HW_M1_FOTA" in text:
                errors.append(f"production source depends on immutable evidence path: {path}")
    return errors


def resolve_idf_environment(activation: Path | None = None,
                            which: Callable[[str], str | None] = shutil.which) -> tuple[str, Path] | None:
    activation = activation or Path(
        os.environ.get("HW_IDF_ACTIVATE", str(Path.home() / ".espressif/tools/activate_idf_v6.0.3.sh")))
    if activation.is_file():
        return ("activation", activation)
    idf = which("idf.py")
    if idf:
        return ("path", Path(idf))
    return None


def command_for_build(target: str, environment: tuple[str, Path], configure: bool) -> list[str]:
    mode, value = environment
    if not configure:
        if mode == "activation":
            return ["bash", "-lc", f"source {shlex.quote(str(value))}; idf.py build"]
        return ["bash", "-lc", f"{shlex.quote(str(value))} build"]
    if mode == "activation":
        command = (f"source {shlex.quote(str(value))}; "
                   f"idf.py set-target {target}; rc=$?; "
                   f"if [ $rc -ne 0 ]; then exit $rc; fi; idf.py build")
        return ["bash", "-lc", command]
    command = (f"{shlex.quote(str(value))} set-target {target}; rc=$?; "
               f"if [ $rc -ne 0 ]; then exit $rc; fi; {shlex.quote(str(value))} build")
    return ["bash", "-lc", command]


def run_logged(name: str, command: list[str], cwd: Path, timeout: int = 900,
               env_update: dict[str, str] | None = None) -> tuple[bool, str]:
    log_dir = ROOT / "build/hw_release_gate"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        environment = {**os.environ, "PYTHONUNBUFFERED": "1", **(env_update or {})}
        result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout,
                                env=environment)
        output = result.stdout or ""
        (log_dir / f"{name}.log").write_text(output)
        return result.returncode == 0, output
    except (OSError, subprocess.TimeoutExpired) as exc:
        (log_dir / f"{name}.log").write_text(str(exc) + "\n")
        return False, str(exc)


def project_description(project: Path) -> dict[str, object] | None:
    path = project / "build/project_description.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def target_build(name: str, project: Path, target: str, binary: Path,
                 environment: tuple[str, Path]) -> tuple[str, str]:
    description = project_description(project)
    configure = description is None or description.get("target") != target or not (project / "build/build.ninja").is_file()
    ok, output = run_logged(name, command_for_build(target, environment, configure), project)
    if not ok:
        return "FAIL", f"build failed; see build/hw_release_gate/{name}.log"
    description = project_description(project)
    if not description or description.get("target") != target:
        return "FAIL", f"project target is not {target}"
    if not binary.is_file() or binary.stat().st_size == 0:
        return "FAIL", f"missing binary: {binary}"
    return "PASS", f"target={target} binary={binary.stat().st_size} bytes"


def image_detail(binary: Path, warning_percent: float) -> tuple[str, str]:
    if not binary.is_file():
        return "FAIL", f"missing binary: {binary}"
    result = evaluate_image_size(binary.stat().st_size, warning_percent=warning_percent)
    if not result.ok:
        return "FAIL", result.detail
    warning = "; EARLY_WARNING" if result.warning else ""
    return "PASS", result.detail + warning


def print_stage(name: str, status: str, detail: str = "") -> None:
    print(f"{status} {name}" + (f" — {detail}" if detail else ""))


def run_gate(full: bool, warning_percent: float, hil: bool = False) -> int:
    failures = False
    results: list[dict[str, str]] = []

    def stage(name: str, status: str, detail: str = "") -> None:
        nonlocal failures
        print_stage(name, status, detail)
        results.append({"stage": name, "status": status, "detail": detail})
        if status not in {"PASS", "WARN", "MANUAL_REQUIRED", "BLOCKED_HIL_FIXTURE_UNAVAILABLE",
                          "NOT_BASELINED", "NOT_RUN"}:
            failures = True

    compiler = os.environ.get("CXX", "/usr/bin/g++")
    host_ok, host_output = run_logged(
        "host-regression", ["make", "cpp-test", f"CXX={compiler}"], ROOT,
        env_update={"PATH": "/usr/bin:/bin"})
    stage("host-regression", "PASS" if host_ok else "FAIL",
          "245 C++ checks expected" if host_ok else "see build/hw_release_gate/host-regression.log")

    partition_problems = partition_errors(NODE_PROJECT / "partitions.csv")
    partition_problems += partition_errors(HUB_PROJECT / "partitions.csv")
    stage("partition-layout", "PASS" if not partition_problems else "FAIL",
          "4 MB dual-OTA layout" if not partition_problems else "; ".join(partition_problems))

    rollback_problems = rollback_errors(NODE_PROJECT) + rollback_errors(HUB_PROJECT)
    stage("rollback-config", "PASS" if not rollback_problems else "FAIL",
          "4 MB and rollback enabled" if not rollback_problems else "; ".join(rollback_problems))

    invariant_problems = config_invariant_errors()
    stage("hw-config-invariants", "PASS" if not invariant_problems else "FAIL",
          "qualified channel/GPIO/TX settings" if not invariant_problems else "; ".join(invariant_problems))

    structure_problems = structural_errors()
    stage("hw-static-structure", "PASS" if not structure_problems else "FAIL",
          "target/FOTA/data-plane artifacts present" if not structure_problems else "; ".join(structure_problems))

    if full:
        environment = resolve_idf_environment()
        if environment is None:
            stage("pair-integrity", "BLOCKED / ENVIRONMENT_MISSING",
                  "source ESP-IDF v6.0.3 activation or provide idf.py")
            stage("c3-target-build", "BLOCKED / ENVIRONMENT_MISSING",
                  "source ESP-IDF v6.0.3 activation or provide idf.py")
            stage("hub-target-build", "BLOCKED / ENVIRONMENT_MISSING",
                  "source ESP-IDF v6.0.3 activation or provide idf.py")
        else:
            pair_ok, pair_output = run_logged(
                "pair-integrity", [sys.executable, str(ROOT / "scripts/build_hw_pair.py")], ROOT,
                timeout=2400)
            stage("pair-integrity", "PASS" if pair_ok else "FAIL",
                  "clean C3/Hub provenance pair" if pair_ok else
                  "see build/hw_release_gate/pair-integrity.log")
            c3_status, c3_detail = target_build("c3-target-build", NODE_PROJECT, "esp32c3",
                                                 NODE_BINARY, environment)
            stage("c3-target-build", c3_status, c3_detail)
            if c3_status == "PASS":
                hub_status, hub_detail = target_build("hub-target-build", HUB_PROJECT, "esp32",
                                                      HUB_BINARY, environment)
                stage("hub-target-build", hub_status, hub_detail)
            else:
                stage("hub-target-build", "BLOCKED / PREREQUISITE",
                      "C3 target build did not produce the embedded node image")
        c3_image_status, c3_image_detail = image_detail(NODE_BINARY, warning_percent)
        hub_image_status, hub_image_detail = image_detail(HUB_BINARY, warning_percent)
        stage("image-size", "PASS" if c3_image_status == hub_image_status == "PASS" else "FAIL",
              f"C3: {c3_image_detail}; Hub: {hub_image_detail}")
    else:
        stage("pair-integrity", "NOT_RUN", "fast gate")
        stage("c3-target-build", "NOT_RUN", "fast gate")
        stage("hub-target-build", "NOT_RUN", "fast gate")
        stage("image-size", "NOT_RUN", "fast gate")

    if hil:
        hil_ok, hil_output = run_logged("hil-phase1-regression", ["make", "hil-qualify"], REPO_ROOT,
                                        timeout=7200)
        if hil_ok:
            stage("hil-phase1-regression", "PASS",
                  "authoritative HIL-SMOKE/RADIO/OR/restart suite")
        elif "BLOCKED" in hil_output or "no serial" in hil_output.lower() or "fixture" in hil_output.lower():
            stage("hil-phase1-regression", "BLOCKED_HIL_FIXTURE_UNAVAILABLE",
                  "connected fixture unavailable; inspect hil-phase1-regression.log")
        else:
            stage("hil-phase1-regression", "FAIL",
                  "authoritative Phase-1 HIL regression failed")
    else:
        stage("hil-phase1-regression", "BLOCKED_HIL_FIXTURE_UNAVAILABLE",
              "run make hw-release-gate HIL=1; connected HIL uses the WSL-first supervisor")
    stage("hil-fota", "MANUAL_REQUIRED", "see docs/hw/HW_M1_3_HIL_VALIDATION.md")
    stage("power-performance", "NOT_BASELINED", "HW-M1.4 measurement plan")
    stage("endurance", "NOT_RUN", "HW-M1.4 Hub-off 8-12h and recovery matrix")

    report = {"full": full, "ota_warning_percent": warning_percent,
              "stages": results, "physical_qualification": "PENDING"}
    report_path = ROOT / "build/hw_release_gate/report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        print("SOFTWARE/TARGET GATE: BLOCKED or FAIL")
    else:
        print("SOFTWARE/TARGET GATE: PASS")
    print("PHYSICAL QUALIFICATION: PENDING")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="skip ESP-IDF target builds and image checks")
    parser.add_argument("--hil", action="store_true",
                        help="run the authoritative connected Phase-1 HIL regression")
    parser.add_argument("--ota-warning-percent", type=float,
                        default=float(os.environ.get("HW_OTA_WARNING_PERCENT",
                                                     DEFAULT_OTA_WARNING_PERCENT)),
                        help="warn when remaining OTA headroom is at or below this percentage")
    args = parser.parse_args()
    if args.ota_warning_percent < 0 or args.ota_warning_percent > 100:
        parser.error("--ota-warning-percent must be between 0 and 100")
    return run_gate(not args.fast, args.ota_warning_percent, args.hil)


if __name__ == "__main__":
    raise SystemExit(main())
