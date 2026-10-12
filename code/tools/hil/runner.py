#!/usr/bin/env python3
# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module T02 Hardware-in-loop tools
# @requirements F03, E09, E10, NFR-05
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The HIL scripts model provisioning plans, installation checks and current summaries. They do not operate
# a board without serial, power and instrument adapters. Record measured evidence and instrument settings
# rather than marking a design target green.

"""T02 installation test-state reducer; physical adapters feed its observations."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InstallationRun:
    required: set[str]
    passed: set[str] = field(default_factory=set)
    failed: dict[str, str] = field(default_factory=dict)

    # @requirements F03, E09, E10, NFR-05
    # Refresh contact telemetry; a heartbeat must not erase an explicit sensor fault.
    def observe(self, check_id: str, passed: bool, detail: str = "") -> None:
        if check_id not in self.required:
            raise ValueError("unknown_check")
        if passed:
            self.failed.pop(check_id, None)
            self.passed.add(check_id)
        else:
            self.passed.discard(check_id)
            self.failed[check_id] = detail or "failed"

    def result(self) -> dict:
        missing = sorted(self.required - self.passed)
        return {"eligible": not missing, "missing": missing, "failures": self.failed.copy()}
