#!/usr/bin/env python3
"""Build and verify the GS-177 dashboard-only Android APK on a provisioned runner."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "parivar_saathi_android_app" / "android"
APK = PROJECT / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
TEST_RESULTS = PROJECT / "app" / "build" / "test-results" / "testDebugUnitTest"
SDK_ROOT = Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME", ""))
BUILD_TOOLS = SDK_ROOT / "build-tools" / "35.0.0"


def run(command: list[str], *, cwd: Path) -> int:
    print("COMMAND:", " ".join(command), flush=True)
    try:
        result = subprocess.run(command, cwd=cwd, check=False)
    except FileNotFoundError as error:
        print(f"GS177 ANDROID DASHBOARD BLOCKED dependency={error.filename}", flush=True)
        return 127
    return result.returncode


def junit_counts() -> tuple[int, int, int]:
    files = sorted(TEST_RESULTS.glob("TEST-*.xml"))
    tests = failures = errors = 0
    for path in files:
        root = ET.parse(path).getroot()
        tests += int(root.attrib.get("tests", "0"))
        failures += int(root.attrib.get("failures", "0"))
        errors += int(root.attrib.get("errors", "0"))
    return tests, failures, errors


def main() -> int:
    gradle = shutil.which("gradle")
    if not gradle:
        print("GS177 ANDROID DASHBOARD BLOCKED dependency=gradle", flush=True)
        return 127
    if not os.environ.get("ANDROID_SDK_ROOT") and not os.environ.get("ANDROID_HOME"):
        print("GS177 ANDROID DASHBOARD BLOCKED dependency=ANDROID_SDK_ROOT_OR_ANDROID_HOME", flush=True)
        return 127

    rc = run(
        [gradle, "--no-daemon", "--stacktrace", "--console=plain", ":app:testDebugUnitTest", ":app:assembleDebug"],
        cwd=PROJECT,
    )
    if rc:
        print(f"GS177 ANDROID DASHBOARD FAIL gradle_exit={rc}", flush=True)
        return rc

    tests, failures, errors = junit_counts()
    if tests < 1 or failures or errors:
        print(f"GS177 ANDROID DASHBOARD FAIL junit_tests={tests} failures={failures} errors={errors}", flush=True)
        return 1
    if not APK.is_file():
        print(f"GS177 ANDROID DASHBOARD FAIL apk_missing={APK}", flush=True)
        return 1

    apksigner = BUILD_TOOLS / "apksigner"
    if not apksigner.is_file():
        print(f"GS177 ANDROID DASHBOARD BLOCKED dependency={apksigner}", flush=True)
        return 127
    rc = run([str(apksigner), "verify", "--verbose", str(APK)], cwd=PROJECT)
    if rc:
        print(f"GS177 ANDROID DASHBOARD FAIL apksigner_exit={rc}", flush=True)
        return rc

    digest = hashlib.sha256(APK.read_bytes()).hexdigest()
    print("CASE GS177-ANDROID-ORIGIN-001 PASS", flush=True)
    print(f"GS177 ANDROID DASHBOARD PASS tests={tests} apk_sha256={digest}", flush=True)
    print(f"APK={APK.relative_to(ROOT)}", flush=True)
    print(f"SOURCE_REVISION={os.environ.get('GITHUB_SHA', 'local')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
