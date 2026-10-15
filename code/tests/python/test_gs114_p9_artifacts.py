"""Host-only safety checks for GS-114 signed qualification artifacts."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_gs114_p9_signed_artifacts import activated, keys, outside_repo


class SignedP9ArtifactSafety(unittest.TestCase):
    def test_s3_signed_fota_profile_excludes_recommissioning_controls(self):
        builder = (ROOT / "scripts/build_secure_fota_hub.py").read_text()
        control = (ROOT / "firmware/hub/target/esp32/idf/main/fixture_commissioning_control.cpp").read_text()
        self.assertIn('"-D", "GS_HIL_COMMISSIONING=OFF"', builder)
        self.assertIn('b"COMMISSION_EXPECTED_NODE" in data', builder)
        self.assertIn('#if GS_HIL_COMMISSIONING\n    if (std::strcmp(verb, "COMMISSION_EXPECTED_NODE")', control)

    def test_private_keys_must_stay_outside_repo(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            outside_repo(ROOT / "build" / "test_keys")

    def test_external_keys_require_private_permissions_and_distinct_files(self):
        with tempfile.TemporaryDirectory(prefix="gs114_test_keys_") as temp:
            directory = Path(temp)
            directory.chmod(0o700)
            trusted = directory / "gs114-p9-trusted.pem"
            negative = directory / "gs114-p9-negative.pem"
            trusted.write_text("test only")
            negative.write_text("different test only")
            trusted.chmod(0o600)
            negative.chmod(0o600)
            self.assertEqual(keys(directory, False), (trusted, negative))
            directory.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "mode 0700"):
                keys(directory, False)
            directory.chmod(0o700)
            negative.unlink()
            os.link(trusted, negative)
            with self.assertRaisesRegex(ValueError, "must differ"):
                keys(directory, False)

    def test_build_log_redacts_external_private_key_paths(self):
        with tempfile.TemporaryDirectory(prefix="gs114_log_") as temp:
            directory = Path(temp)
            trusted = directory / "trusted.pem"
            negative = directory / "negative.pem"
            fake = subprocess.CompletedProcess([], 0,
                f"command used {trusted} and {negative}; verification passed")
            log = directory / "build.log"
            with patch("prepare_gs114_p9_signed_artifacts.subprocess.run", return_value=fake):
                activated(["true"], log, (trusted, negative))
            content = log.read_text()
            self.assertNotIn(str(trusted), content)
            self.assertNotIn(str(negative), content)
            self.assertIn("<external-test-key>", content)


if __name__ == "__main__":
    unittest.main()
