"""Small, testable subprocess wrapper for release-gate stages."""
from __future__ import annotations

import subprocess
from typing import Mapping, Sequence


def _as_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def execute_stage(
    name: str,
    cmd: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout: int,
) -> tuple[str, str]:
    """Return a controlled PASS/FAIL and captured output for one stage."""
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _as_text(exc.stdout if exc.stdout is not None else exc.output)
        stderr = _as_text(exc.stderr)
        details = [f"TIMEOUT stage={name} configured_timeout={timeout}s"]
        if stdout:
            details.extend(("--- retained stdout ---", stdout.rstrip()))
        if stderr:
            details.extend(("--- retained stderr ---", stderr.rstrip()))
        return "FAIL", "\n".join(details) + "\n"

    output = _as_text(completed.stdout) + _as_text(completed.stderr)
    return ("PASS" if completed.returncode == 0 else "FAIL"), output
