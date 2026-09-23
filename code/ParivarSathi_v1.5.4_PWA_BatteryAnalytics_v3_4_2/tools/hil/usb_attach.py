#!/usr/bin/env python3
"""WSL-owned access to the USB-only Windows attachment helper."""
from __future__ import annotations

import dataclasses
import platform
import subprocess
import time
from pathlib import Path
from typing import Callable

PRODUCT = Path(__file__).resolve().parents[2]
REPO = PRODUCT.parents[1]
WINDOWS_HELPER = REPO / "tools/hil/ensure-usb-attached.ps1"


@dataclasses.dataclass(frozen=True)
class HelperResult:
    returncode: int
    stdout: str
    stderr: str


class FixtureBlocked(RuntimeError):
    """The fixture cannot become ready without an external prerequisite."""


class FixtureFailed(RuntimeError):
    """The fixture appeared, but failed authoritative identity verification."""


def is_wsl() -> bool:
    return platform.system() == "Linux" and "microsoft" in platform.release().lower()


def invoke_windows_helper(*, timeout: float = 45.0,
                          runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
                          helper: Path = WINDOWS_HELPER) -> HelperResult:
    """Run the path-independent PowerShell helper synchronously through stdin.

    Passing source on stdin avoids converting the WSL repository path to a
    Windows UNC path. The helper has no repository or Linux path responsibility.
    """
    if not helper.is_file():
        raise FixtureBlocked(f"Windows USB helper is missing: {helper}")
    command = ["powershell.exe", "-NoProfile", "-NonInteractive",
               "-ExecutionPolicy", "Bypass", "-Command",
               "$source=[Console]::In.ReadToEnd(); & ([ScriptBlock]::Create($source))"]
    try:
        completed = runner(command, input=helper.read_text(encoding="ascii"), text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, cwd=REPO)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FixtureBlocked(f"Windows USB helper could not complete: {exc}") from exc
    result = HelperResult(completed.returncode, completed.stdout or "", completed.stderr or "")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", flush=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise FixtureBlocked(
            f"Windows USB helper exit={result.returncode}: {detail or 'no diagnostic'}")
    return result


def ensure_verified_fixture(discover: Callable[[], object], *, presence_probe: Callable[[], object] | None = None,
                            timeout: float = 30.0,
                            interval: float = 0.5,
                            helper_invoker: Callable[[], object] = invoke_windows_helper,
                            monotonic: Callable[[], float] = time.monotonic,
                            sleeper: Callable[[float], None] = time.sleep) -> object:
    """Return verified devices after cheap presence/stability and one MAC check.

    `presence_probe` must not open a target or run esptool.  It is used before
    attachment/reconciliation so a transient native-USB tty is never handed to
    an identity probe merely to determine whether the fixture exists.
    """
    if presence_probe is None:
        # Compatibility path for callers that have no cheap metadata probe.
        # The WSL qualification path always supplies one.
        first_error: Exception | None = None
        try:
            return discover()
        except Exception as exc:
            first_error = exc
        helper_invoker()
        deadline = monotonic() + timeout
        last_error: Exception = first_error
        while True:
            try:
                return discover()
            except Exception as exc:
                last_error = exc
            if monotonic() >= deadline:
                message = str(last_error)
                identity_failure = any(token in message.lower() for token in (
                    "mac is not", "board type mismatch", "conflicting mac", "identity changed"))
                error_type = FixtureFailed if identity_failure else FixtureBlocked
                raise error_type(f"WSL fixture readiness timeout after {timeout:g}s: {message}") from last_error
            sleeper(min(interval, max(0.0, deadline - monotonic())))

    readiness_probe = presence_probe
    first_error: Exception | None = None
    ready = False
    try:
        readiness_probe()
        ready = True
    except Exception as exc:  # discovery provides the authoritative diagnostic
        first_error = exc
        helper_invoker()
    deadline = monotonic() + timeout
    last_error: Exception = first_error
    while not ready:
        try:
            readiness_probe()
            ready = True
            break
        except Exception as exc:
            last_error = exc
        if monotonic() >= deadline:
            message = str(last_error)
            identity_failure = any(token in message.lower() for token in (
                "mac is not", "board type mismatch", "conflicting mac", "identity changed"))
            error_type = FixtureFailed if identity_failure else FixtureBlocked
            raise error_type(
                f"WSL fixture readiness timeout after {timeout:g}s: {message}") from last_error
        sleeper(min(interval, max(0.0, deadline - monotonic())))

    # Metadata presence is not identity.  Verify chip/MAC only after a stable
    # WSL tty exists.  If that controlled probe detects a transition or times
    # out, reconcile usbipd once and retry within the same bounded deadline.
    reconciled_after_identity_error = False
    while True:
        try:
            return discover()
        except Exception as exc:
            last_error = exc
        if not reconciled_after_identity_error:
            reconciled_after_identity_error = True
            helper_invoker()
        if monotonic() >= deadline:
            message = str(last_error)
            identity_failure = any(token in message.lower() for token in (
                "mac is not", "board type mismatch", "conflicting mac", "identity changed"))
            error_type = FixtureFailed if identity_failure else FixtureBlocked
            reason = "IDENTITY_REVERIFY_FAILED" if "identity_probe" in message.lower() else "FIXTURE_RECOVERY_TIMEOUT"
            raise error_type(f"{reason} after {timeout:g}s: {message}") from last_error
        try:
            readiness_probe()
        except Exception as exc:
            last_error = exc
        sleeper(min(interval, max(0.0, deadline - monotonic())))
