#!/usr/bin/env python3
"""T02 installation test-state reducer; physical adapters feed its observations."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InstallationRun:
    required: set[str]
    passed: set[str] = field(default_factory=set)
    failed: dict[str, str] = field(default_factory=dict)

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
