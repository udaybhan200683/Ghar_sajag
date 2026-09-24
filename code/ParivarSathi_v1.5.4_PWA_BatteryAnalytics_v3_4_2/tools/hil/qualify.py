#!/usr/bin/env python3
"""WSL-first Phase-1 HIL qualification supervisor."""
from __future__ import annotations

import dataclasses
import argparse
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
CHECKPOINT_SMOKE_STAGES = ("usb-fixture", "hil-setup", "hil-preflight", "hil-smoke")
CHECKPOINT_FOTA_STAGES = ("usb-fixture", "hil-setup", "hil-preflight", "hil-fota")
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
                 output: Callable[[str], None] = print,
                 stages: tuple[str, ...] | None = None,
                 label: str = "PHASE-1 HIL QUALIFICATION"):
        self.stage_runner = stage_runner
        self.fixture_runner = fixture_runner
        self.report_reader = report_reader
        self.output = output
        self.stages = tuple(STAGES if stages is None else stages)
        self.label = label
        self.prefix = ("HIL CHECKPOINT" if self.stages in
                       (CHECKPOINT_SMOKE_STAGES, CHECKPOINT_FOTA_STAGES) else "PHASE-1")
        self.statuses: OrderedDict[str, str] = OrderedDict((name, "BLOCKED") for name in self.stages)
        self.executed = 0
        self.report_eligible = False

    def run(self) -> int:
        failure_kind: str | None = None
        for name in self.stages:
            if failure_kind is not None:
                self.statuses[name] = "BLOCKED"
                continue
            self.output(f"{self.prefix}: {name} - START")
            self.executed += 1
            try:
                if name == "usb-fixture":
                    self.fixture_runner()
                    code = 0
                else:
                    result = self.stage_runner(name)
                    code = int(result.returncode if hasattr(result, "returncode") else result)
                    if name in ("hil-smoke", "hil-regression", "hil-fota"):
                        self.report_eligible = True
            except FixtureBlocked as exc:
                self.output(f"{self.prefix}: {name} - BLOCKED: {exc}")
                self.statuses[name] = "BLOCKED"
                failure_kind = "BLOCKED"
                continue
            except Exception as exc:
                self.output(f"{self.prefix}: {name} - FAIL: {type(exc).__name__}: {exc}")
                self.statuses[name] = "FAIL"
                failure_kind = "FAIL"
                continue
            if code == 0:
                self.statuses[name] = "PASS"
                self.output(f"{self.prefix}: {name} - PASS")
            else:
                self.statuses[name] = "FAIL"
                self.output(f"{self.prefix}: {name} - FAIL (exit {code})")
                failure_kind = "FAIL"

        if self.executed == 0:
            failure_kind = "FAIL"
            self.output("FAIL_NO_QUALIFICATION_EXECUTED")
        all_passed = bool(self.stages) and self.executed == len(self.stages) and all(
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
        self.output(self.label)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-smoke", action="store_true",
                        help="refresh fixture setup and preflight before the focused physical smoke")
    parser.add_argument("--checkpoint-fota", action="store_true",
                        help="refresh fixture setup and preflight before same-image C3 FOTA")
    args = parser.parse_args()
    if args.checkpoint_smoke and args.checkpoint_fota:
        parser.error("choose one focused checkpoint")
    if args.checkpoint_smoke:
        return QualificationSupervisor(stages=CHECKPOINT_SMOKE_STAGES,
                                       label="HIL CHECKPOINT SMOKE").run()
    if args.checkpoint_fota:
        return QualificationSupervisor(stages=CHECKPOINT_FOTA_STAGES,
                                       label="HIL CHECKPOINT C3 FOTA").run()
    return QualificationSupervisor().run()


if __name__ == "__main__":
    raise SystemExit(main())
