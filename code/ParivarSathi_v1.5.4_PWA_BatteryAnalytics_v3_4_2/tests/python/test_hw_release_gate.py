from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.validation.hw_release_gate import (
    OTA_SLOT_BYTES,
    evaluate_image_size,
    missing_patterns,
    parse_partitions,
    resolve_idf_environment,
)


class HwReleaseGateTest(unittest.TestCase):
    def test_image_within_slot_passes_with_exact_headroom(self):
        result = evaluate_image_size(OTA_SLOT_BYTES // 2)
        self.assertTrue(result.ok)
        self.assertFalse(result.warning)
        self.assertEqual(result.headroom, OTA_SLOT_BYTES // 2)

    def test_image_exceeding_slot_fails(self):
        result = evaluate_image_size(OTA_SLOT_BYTES + 1)
        self.assertFalse(result.ok)
        self.assertIn("exceeds slot", result.detail)

    def test_low_headroom_is_warning_but_not_failure(self):
        result = evaluate_image_size(OTA_SLOT_BYTES - 10, warning_percent=15)
        self.assertTrue(result.ok)
        self.assertTrue(result.warning)

    def test_malformed_partition_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partitions.csv"
            path.write_text("ota_0,app,ota_0,0x20000\n")
            with self.assertRaises(ValueError):
                parse_partitions(path)

    def test_wrong_invariant_is_detected(self):
        missing = missing_patterns("kEspNowChannel = 6", [("channel 1", r"kEspNowChannel\s*=\s*1")])
        self.assertEqual(missing, ["channel 1"])

    def test_missing_idf_is_not_available(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_activation = Path(directory) / "missing_activate.sh"
            self.assertIsNone(resolve_idf_environment(missing_activation, which=lambda _: None))


if __name__ == "__main__":
    unittest.main()
