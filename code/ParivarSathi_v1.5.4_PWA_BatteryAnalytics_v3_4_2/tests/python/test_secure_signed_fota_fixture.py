from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.hil.secure_signed_fota import hub_flash_command


class SecureSignedFotaFixtureTest(unittest.TestCase):
    def test_hub_flash_uses_exact_candidate_artifact_for_shared_build_dir(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_dir = root / "shared-build"
            build_dir.mkdir()
            otadata = build_dir / "ota_data_initial.bin"
            otadata.write_bytes(bytes(0x2000))
            negative = root / "negative-hub.bin"
            positive = root / "positive-hub.bin"
            negative.write_bytes(b"negative candidate")
            positive.write_bytes(b"positive candidate")

            def record(path: Path) -> dict:
                return {"profile": "secure-signed-fota-hil-control",
                        "legacy_raw_fota": False,
                        "build_dir": str(build_dir),
                        "hub_image": str(path),
                        "hub_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

            negative_command = hub_flash_command(record(negative), "/dev/ttyUSB-hub")
            positive_command = hub_flash_command(record(positive), "/dev/ttyUSB-hub")
            self.assertIn(str(negative), negative_command)
            self.assertIn(str(positive), positive_command)
            self.assertNotIn("idf.py", negative_command)
            self.assertNotIn("idf.py", positive_command)
            self.assertIn("0xf000", negative_command)
            self.assertIn("0x20000", positive_command)

    def test_hub_flash_rejects_image_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_dir = root / "build"
            build_dir.mkdir()
            (build_dir / "ota_data_initial.bin").write_bytes(bytes(0x2000))
            image = root / "hub.bin"
            image.write_bytes(b"candidate")
            record = {"profile": "secure-signed-fota-hil-control",
                      "legacy_raw_fota": False,
                      "build_dir": str(build_dir),
                      "hub_image": str(image),
                      "hub_sha256": "0" * 64}
            with self.assertRaisesRegex(RuntimeError, "profile/hash"):
                hub_flash_command(record, "/dev/ttyUSB-hub")


if __name__ == "__main__":
    unittest.main()
