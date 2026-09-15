#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess, time, urllib.request, signal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("PWA_BASE_URL", "http://127.0.0.1:8765")
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)
LAB_LOG = EVIDENCE / "playwright-lab.log"

def wait_http(url: str, proc: subprocess.Popen, timeout: int = 60) -> None:
    """Wait for HTTP readiness, but fail immediately if the server process exits."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        rc = proc.poll()
        if rc is not None:
            output = ""
            try:
                output = proc.stdout.read() if proc.stdout else ""
            except Exception:
                pass
            LAB_LOG.write_text(output or "", encoding="utf-8")
            raise RuntimeError(
                f"lab server exited before becoming ready (exit={rc}). "
                f"See {LAB_LOG}\n{output[-4000:]}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return
        except Exception as e:
            last = e
        time.sleep(0.5)
    raise RuntimeError(
        f"server not ready after {timeout}s: {url}: {last}. "
        f"See {LAB_LOG}"
    )

# IMPORTANT:
# release-gate runs sanitizer/trace stages which may clean the build directory.
# Building the interactive lab can take ~40-60 seconds on WSL.
# Do the build synchronously BEFORE starting the HTTP-readiness timer.
print("Preparing Playwright lab build...")
subprocess.run(["make", "lab-build"], cwd=ROOT, check=True)

print("Starting Parivar Sathi / Ghar Sajag local lab...")
lab = subprocess.Popen(
    ["python3", "tools/sim/local_lab.py"],
    cwd=ROOT,
    env={**os.environ, "GS_APP_DB": ":memory:"},
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    start_new_session=True,
)

try:
    wait_http(BASE, lab, timeout=60)
    print(f"Lab ready: {BASE}")

    env = os.environ.copy()
    env["PWA_BASE_URL"] = BASE
    rc = subprocess.call(["npx", "playwright", "test"], cwd=ROOT, env=env)
    raise SystemExit(rc)
finally:
    try:
        os.killpg(lab.pid, signal.SIGTERM)
    except Exception:
        try:
            lab.terminate()
        except Exception:
            pass

    try:
        out, _ = lab.communicate(timeout=5)
    except Exception:
        try:
            lab.kill()
        except Exception:
            pass
        out, _ = lab.communicate()

    LAB_LOG.write_text(out or "", encoding="utf-8")
