"""Replay selected raw Phase-1 evidence through the existing HIL parser/cursor rules."""
from __future__ import annotations

import json
import hashlib
import re
import unittest
from pathlib import Path

from tools.hil.phase1 import Campaign, SOFTWARE_RESET_EVIDENCE, normalize_rom_reset_class, parse_esptool_output


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/hil/phase1_real_replay.json"


class ReplayCapture:
    """Feed recorded lines to the actual Phase-1 reboot state machine."""

    def __init__(self, stale: list[str], fresh: list[str]):
        self.lines = list(stale)
        self.fresh = fresh
        self.commands: list[str] = []

    def cursor(self):
        return len(self.lines)

    def send(self, command):
        self.commands.append(command)
        self.lines.extend(self.fresh)

    def wait_for_predicate(self, predicate, description, timeout, start=0):
        for line in self.lines[start:]:
            if predicate(line):
                return line
        raise TimeoutError(description)

    def wait_for(self, pattern, timeout, start=0):
        for line in self.lines[start:]:
            if re.search(pattern, line):
                return line
        raise TimeoutError(pattern)


class RealEvidenceReplayTest(unittest.TestCase):
    def test_real_reset_and_readiness_transitions(self):
        fixtures = json.loads(FIXTURES.read_text())["fixtures"]
        for fixture in fixtures:
            if fixture["kind"] != "REAL_HARDWARE" or "serial.log" not in fixture["source"]:
                continue
            with self.subTest(fixture=fixture["id"]):
                capture = ReplayCapture(fixture.get("stale", []), fixture["fresh"])
                cursor = capture.cursor()
                fresh = fixture["fresh"]
                self.assertEqual(
                    sum(normalize_rom_reset_class(line) == SOFTWARE_RESET_EVIDENCE for line in capture.lines[cursor:]),
                    0,
                )
                self.assertFalse(any("HIL_READY" in line for line in capture.lines[cursor:]))
                if fixture["id"] != "P2-REPLAY-003":
                    Campaign("regression", {}, {}, {"image_version": "df60ed5-hil-a18d5c2"}, Path("/dev/null")) \
                        .reboot(capture, fixture["target"], 1)
                    self.assertEqual(capture.commands, ["SOFTWARE_RESTART"])
                else:
                    capture.send("SOFTWARE_RESTART")
                reset = next((i for i, line in enumerate(capture.lines[cursor:], cursor)
                              if normalize_rom_reset_class(line) == SOFTWARE_RESET_EVIDENCE), None)
                self.assertIsNotNone(reset)
                if fixture["id"] != "P2-REPLAY-003":
                    ready = next((i for i, line in enumerate(capture.lines[reset + 1:], reset + 1)
                                  if re.search(rf"HIL_READY role={fixture['target']} protocol=1 version=", line)), None)
                    self.assertIsNotNone(ready)
                    if fixture["target"] == "c3":
                        sensing = next((i for i, line in enumerate(capture.lines[ready + 1:], ready + 1)
                                        if "PIR ready on GPIO" in line), None)
                        self.assertIsNotNone(sensing)
                        self.assertLess(ready, sensing)
                else:
                    self.assertFalse(any(normalize_rom_reset_class(line) == SOFTWARE_RESET_EVIDENCE
                                         for line in fresh[:-1]))

    def test_real_esptool_v5_outputs(self):
        fixtures = json.loads(FIXTURES.read_text())["fixtures"]
        for fixture in fixtures:
            if "flash.log" not in fixture["source"]:
                continue
            with self.subTest(fixture=fixture["id"]):
                chip, mac = parse_esptool_output("\n".join(fixture["fresh"]))
                self.assertEqual(chip, fixture["expected_parser"])
                self.assertEqual(len(mac), 12)

    def test_provenance_and_labels(self):
        fixtures = json.loads(FIXTURES.read_text())["fixtures"]
        self.assertEqual(len({item["id"] for item in fixtures}), len(fixtures))
        for fixture in fixtures:
            self.assertIn(fixture["kind"], {"REAL_HARDWARE", "SYNTHETIC_NO_RAW_CAPTURE"})
            self.assertTrue(fixture["expected_parser"])
            self.assertTrue(fixture["expected_transition"])
            if fixture["kind"] == "REAL_HARDWARE":
                self.assertEqual(len(fixture["source_sha256"]), 64)
                source = FIXTURES.parents[5] / fixture["source"]
                if source.exists():
                    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), fixture["source_sha256"])
                    raw_lines = set(source.read_text(errors="replace").splitlines())
                    self.assertTrue(set(fixture.get("stale", []) + fixture["fresh"]).issubset(raw_lines))


if __name__ == "__main__":
    unittest.main()
