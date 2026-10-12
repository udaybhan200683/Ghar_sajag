#!/usr/bin/env python3
"""Isolated esptool identity probe worker.

This process deliberately owns the potentially USB-blocked esptool child.  A
WSL supervisor polls its result file and never waits synchronously on this
worker, so an uninterruptible USB kernel wait cannot stall qualification.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activate", required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--pid", required=True)
    args = parser.parse_args()
    command = (f"source {shlex.quote(args.activate)}; "
               f"python -m esptool --port {shlex.quote(args.port)} read-mac")
    try:
        child = subprocess.Popen(["bash", "-lc", command], text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        Path(args.pid).write_text(str(child.pid), encoding="ascii")
        stdout, _ = child.communicate()
        completed = subprocess.CompletedProcess(child.args, child.returncode, stdout)
        payload = {"returncode": completed.returncode, "stdout": completed.stdout or ""}
    except Exception as exc:
        payload = {"returncode": 127, "stdout": "", "error": f"{type(exc).__name__}: {exc}"}
    result = Path(args.result)
    temporary = result.with_suffix(result.suffix + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
