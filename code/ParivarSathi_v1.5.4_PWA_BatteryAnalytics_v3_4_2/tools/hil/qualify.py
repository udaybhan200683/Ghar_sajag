#!/usr/bin/env python3
"""WSL-first Phase-1 HIL qualification supervisor."""
from __future__ import annotations

import dataclasses
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Callable

SCRIPT_PRODUCT = Path(__file__).resolve().parents[2]
if str(SCRIPT_PRODUCT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PRODUCT))

from tools.hil.core import REPO
from tools.hil.phase1 import discover, stable_fixture_usb_snapshot
from tools.hil.usb_attach import FixtureBlocked, FixtureFailed, ensure_verified_fixture

STAGES = ("validation-fast", "release-gate-final", "usb-fixture", "hil-setup",
          "hil-preflight", "hil-smoke", "hil-regression")
LATEST_REPORT = REPO / "evidence/hil/latest.txt"


@dataclasses.dataclass(frozen=True)
class StageResult:
    returncode: int


def run_make_stage(name: str) -> StageResult:
    completed = subprocess.run(["make", name], cwd=REPO)
    return StageResult(completed.returncode)


def verify_fixture() -> object:
    config = {"HIL_IDF_ACTIVATE": str(Path.home() / ".espressif/tools/activate_idf_v6.0.3.sh")}
    return ensure_verified_fixture(lambda: discover(config)[0],
                                   presence_probe=lambda: stable_fixture_usb_snapshot(config))


def latest_report() -> str | None:
    if not LATEST_REPORT.is_file():
        return None
    value = LATEST_REPORT.read_text().splitlines()
    return value[0].strip() if value and value[0].strip() else None


class QualificationSupervisor:
    def __init__(self, *, stage_runner: Callable[[str], object] = run_make_stage,
                 fixture_runner: Callable[[], object] = verify_fixture,
                 report_reader: Callable[[], str | None] = latest_report,
                 output: Callable[[str], None] = print):
        self.stage_runner = stage_runner
        self.fixture_runner = fixture_runner
        self.report_reader = report_reader
        self.output = output
        self.statuses: OrderedDict[str, str] = OrderedDict((name, "BLOCKED") for name in STAGES)
        self.executed = 0
        self.report_eligible = False

    def run(self) -> int:
        failure_kind: str | None = None
        for name in STAGES:
            if failure_kind is not None:
                self.statuses[name] = "BLOCKED"
                continue
            self.output(f"PHASE-1: {name} - START")
            self.executed += 1
            try:
                if name == "usb-fixture":
                    self.fixture_runner()
                    code = 0
                else:
                    result = self.stage_runner(name)
                    code = int(result.returncode if hasattr(result, "returncode") else result)
                    if name in ("hil-smoke", "hil-regression"):
                        self.report_eligible = True
            except FixtureBlocked as exc:
                self.output(f"PHASE-1: {name} - BLOCKED: {exc}")
                self.statuses[name] = "BLOCKED"
                failure_kind = "BLOCKED"
                continue
            except Exception as exc:
                self.output(f"PHASE-1: {name} - FAIL: {type(exc).__name__}: {exc}")
                self.statuses[name] = "FAIL"
                failure_kind = "FAIL"
                continue
            if code == 0:
                self.statuses[name] = "PASS"
                self.output(f"PHASE-1: {name} - PASS")
            else:
                self.statuses[name] = "FAIL"
                self.output(f"PHASE-1: {name} - FAIL (exit {code})")
                failure_kind = "FAIL"

        if self.executed == 0:
            failure_kind = "FAIL"
            self.output("FAIL_NO_QUALIFICATION_EXECUTED")
        all_passed = bool(STAGES) and self.executed == len(STAGES) and all(
            value == "PASS" for value in self.statuses.values())
        if all_passed:
            exit_code, overall = 0, "PASS"
        elif failure_kind == "BLOCKED":
            exit_code, overall = 2, "BLOCKED"
        else:
            exit_code, overall = 1, "FAIL"
        self.print_summary(overall)
        return exit_code

    def print_summary(self, overall: str) -> None:
        self.output("PHASE-1 HIL QUALIFICATION")
        for name, status in self.statuses.items():
            self.output(f"{name:<20} {status}")
        self.output(f"{'OVERALL':<20} {overall}")
        report = None
        if self.report_eligible:
            try:
                report = self.report_reader()
            except Exception as exc:
                self.output(f"REPORT READ ERROR    {exc}")
        self.output(f"{'REPORT':<20} {report or '<none>'}")


def main() -> int:
    return QualificationSupervisor().run()


if __name__ == "__main__":
    raise SystemExit(main())
