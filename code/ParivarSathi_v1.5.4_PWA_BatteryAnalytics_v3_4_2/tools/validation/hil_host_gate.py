#!/usr/bin/env python3
"""Fast, hardware-independent Phase-1 HIL integration/isolation checks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
HIL_MARKERS = (b"HIL_READY", b"INJECT_MOTION", b"SET_HUB_LOGICAL_OFFLINE")


def fail(message: str) -> None:
    raise RuntimeError(message)


def check_source_isolation() -> None:
    projects = (
        ROOT / "firmware/node/target/esp32c3/idf",
        ROOT / "firmware/hub/target/esp32/idf",
    )
    for project in projects:
        cmake = project / "main/CMakeLists.txt"
        top = project / "CMakeLists.txt"
        app = project / "main/app_main.cpp"
        control = project / "main/hil_control.cpp"
        for path in (cmake, top, app, control):
            if not path.is_file():
                fail(f"missing HIL isolation artifact: {path}")
        cmake_text = cmake.read_text()
        top_text = top.read_text()
        app_text = app.read_text()
        if "if(GS_HIL_BUILD)" not in cmake_text or "GS_HIL_BUILD=$<BOOL:${GS_HIL_BUILD}>" not in cmake_text:
            fail(f"HIL source is not compile-time gated: {cmake}")
        if 'option(GS_HIL_BUILD "Enable the USB HIL control plane (never for release images)" OFF)' not in top_text:
            fail(f"production HIL default is not OFF: {top}")
        if "#if GS_HIL_BUILD" not in app_text:
            fail(f"HIL startup is not compile-time gated: {app}")


def check_supervisor_contract() -> None:
    qualifier = ROOT / "tools/hil/qualify.py"
    usb_helper = REPO / "tools/hil/ensure-usb-attached.ps1"
    legacy = REPO / "tools/hil/run-hil.ps1"
    for path in (qualifier, usb_helper, legacy):
        if not path.is_file():
            fail(f"missing WSL-first supervisor artifact: {path}")
    qualifier_text = qualifier.read_text()
    required_stages = ("validation-fast", "release-gate-final", "usb-fixture",
                       "hil-setup", "hil-preflight", "hil-smoke", "hil-regression")
    if any(stage not in qualifier_text for stage in required_stages):
        fail("WSL qualifier stage contract is incomplete")
    helper_text = usb_helper.read_text()
    required_usb = ("usbipd.exe", "--parsable", "Select-ExpectedUsbDevices",
                    "Ensure-UsbAttached", "BLOCKED_NEEDS_USBIPD_BIND", "Invoke-SelfTest")
    if any(token not in helper_text for token in required_usb):
        fail("minimal Windows USB helper contract is incomplete")
    forbidden_helper = ("wsl.exe", "hil-setup", "hil-preflight", "hil-smoke",
                        "hil-regression", "validation-fast", "release-gate-final")
    if any(token in helper_text for token in forbidden_helper):
        fail("Windows USB helper contains master orchestration")
    if re.search(r"COM[34]|BUSID.*(?:3-1|3-3)", helper_text, re.IGNORECASE):
        fail("USB helper contains a prohibited fixed COM/BUSID identity")
    if "deprecated" not in legacy.read_text().lower():
        fail("legacy PowerShell master is not explicitly deprecated")


def check_existing_images() -> None:
    manifest = ROOT / "build/hw_pair/provenance.json"
    node = ROOT / "firmware/node/target/esp32c3/idf/build/gs_hw_m1_node.bin"
    hub = ROOT / "firmware/hub/target/esp32/idf/build/gs_hw_m1_hub.bin"
    if not (node.is_file() and hub.is_file()):
        return
    kind = ""
    if manifest.is_file():
        try:
            kind = json.loads(manifest.read_text()).get("kind", "")
        except (OSError, json.JSONDecodeError):
            fail(f"invalid pair provenance: {manifest}")
    # Existing HIL artifacts are valid evidence for the HIL build check. A
    # release-gate cleanup may remove the provenance manifest, so recognize the
    # deterministic HIL version/configuration before judging stale binaries.
    hil_signal = kind == "HIL_PHASE1" or (ROOT / "firmware/node/target/esp32c3/idf/sdkconfig.hil").is_file()
    image_bytes = {image: image.read_bytes() for image in (node, hub)}
    hil_signal = hil_signal or any(b"-hil-" in data for data in image_bytes.values())
    if hil_signal:
        for image in (node, hub):
            data = image_bytes[image]
            if not all(marker in data for marker in (b"HIL_READY",)):
                fail(f"HIL artifact lacks required marker: {image}")
        return
    for image in (node, hub):
        data = image_bytes[image]
        present = [marker.decode() for marker in HIL_MARKERS if marker in data]
        if present:
            fail(f"production artifact exposes HIL markers {present}: {image}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="retained for gate readability")
    parser.parse_args()
    check_source_isolation()
    check_supervisor_contract()
    check_existing_images()
    print("HIL HOST GATE: PASS (hardware-independent isolation/contract checks)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"HIL HOST GATE: FAIL — {exc}", file=sys.stderr)
        raise SystemExit(1)
