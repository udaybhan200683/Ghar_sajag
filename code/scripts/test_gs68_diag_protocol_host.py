#!/usr/bin/env python3
"""Compile and execute the portable bounded GS-68 target command parser tests."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gs68-node-protocol-") as directory:
        executable = Path(directory) / "gs68_node_protocol_test"
        subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-I", str(ROOT / "firmware/common/shared/include"),
            str(ROOT / "tests/cpp/gs68_diag_protocol_test.cpp"), "-o", str(executable)],
            check=True, cwd=ROOT)
        return subprocess.run([str(executable)], check=False, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
