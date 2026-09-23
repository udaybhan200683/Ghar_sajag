#!/usr/bin/env python3
"""Run the minimal USB helper's real PowerShell parser and fake-native self-test."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[2]
REPO = PRODUCT.parents[1]
HELPER = REPO / "tools/hil/ensure-usb-attached.ps1"


def run_powershell(command: str, source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-Command", command], input=source, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, cwd=REPO)


def unavailable(detail: str) -> bool:
    lowered = detail.lower()
    return ("utilbindvsockanyport" in lowered or "socket failed" in lowered or
            "powershell.exe: not found" in lowered)


def main() -> int:
    raw = HELPER.read_bytes()
    if any(byte >= 128 for byte in raw):
        print("HIL-USB POWERSHELL CHECK: FAIL - helper is not ASCII", file=sys.stderr)
        return 1
    if shutil.which("powershell.exe") is None:
        print("HIL-USB POWERSHELL CHECK: SKIP - Windows interop is unavailable")
        return 0
    source = raw.decode("ascii")
    parser = (
        "$source=[Console]::In.ReadToEnd();$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,"
        "[ref]$errors)|Out-Null;if($errors.Count){$errors|ForEach-Object{Write-Error "
        "$_.Message};exit 2};Write-Output 'HIL-USB PARSER-CHECK: PASS'")
    try:
        parsed = run_powershell(parser, source)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"HIL-USB POWERSHELL CHECK: SKIP - Windows interop unavailable: {exc}")
        return 0
    detail = (parsed.stdout or "") + (parsed.stderr or "")
    if parsed.returncode and unavailable(detail):
        print("HIL-USB POWERSHELL CHECK: SKIP - Windows interop unavailable")
        return 0
    if parsed.returncode:
        print(detail, file=sys.stderr)
        return parsed.returncode
    selftest = ("$source=[Console]::In.ReadToEnd();"
                "& ([ScriptBlock]::Create($source)) -SelfTest")
    tested = run_powershell(selftest, source)
    detail = (tested.stdout or "") + (tested.stderr or "")
    if tested.returncode and unavailable(detail):
        print("HIL-USB POWERSHELL CHECK: SKIP - Windows interop unavailable")
        return 0
    if tested.returncode:
        print(detail, file=sys.stderr)
        return tested.returncode
    print((parsed.stdout or "").strip())
    print((tested.stdout or "").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
