import base64
import hashlib
import csv
import json
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import gs68_capture as capture
import gs68_cloudsync_hil as runner


class GS68CloudSyncRunnerTests(unittest.TestCase):
    def setUp(self):
        self.source = "a" * 40
        self.cases = json.loads(runner.CASE_PLAN.read_text(encoding="utf-8"))
        self.protected = json.loads(runner.PROTECTED_FIXTURE.read_text(encoding="utf-8"))
        self.backend_dir = Path(tempfile.mkdtemp(prefix="gs68-backend-descriptor-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.backend_dir, ignore_errors=True))

    def _sha(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _valid_fixture(self, root):
        root = Path(root)
        s3 = root / "candidate-s3.bin"
        c3 = root / "candidate-c3.bin"
        s3.write_bytes(b"synthetic S3 image")
        c3.write_bytes(b"synthetic C3 image")
        profile_hash = self._sha(runner.PROFILE)
        build = root / "build-report.json"
        build_commit = runner.subprocess.run(["git", "-C", str(runner.REPO), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
        code_tree_oid = runner._current_code_tree_oid()
        build.write_text(json.dumps({
            "source_commit": build_commit,
            "source_code_tree_oid": code_tree_oid,
            "profile_sha256": profile_hash,
            "s3_image_sha256": self._sha(s3),
        }))
        fixture = {
            "schema_version": 1,
            "fixture_id": "GS68-SPARE-UNIT-001",
            "fixture_class": "DISPOSABLE_RND_ONLY",
            "physical_authorization": {"status": "NOT_AUTHORIZED", "jira_comment": None, "authorized_case_ids": []},
            "source_commit": self.source,
            "profile": {
                "profile_id": "GS68_CLOUDSYNC_DS_MTLS_HIL",
                "config_path": "code/firmware/hub/target/esp32s3/idf/sdkconfig.gs68_cloudsync_hil.defaults",
                "profile_sha256": profile_hash,
                "build_report": str(build),
            },
            "boards": {
                "s3": {
                    "target": "ESP32-S3", "flash_mb": 16, "psram_mb": 8,
                    "identity": {"mac_address": "02:00:00:00:68:01", "usb_serial_short": "GS68-TEST-S3", "port_by_id": "/dev/serial/by-id/gs68-test-s3"},
                    "image": {"path": str(s3), "sha256": self._sha(s3)},
                },
                "c3": {
                    "target": "ESP32-C3", "flash_mb": 4, "psram_mb": 0,
                    "identity": {"mac_address": "02:00:00:00:68:02", "usb_serial_short": "GS68-TEST-C3", "port_by_id": "/dev/serial/by-id/gs68-test-c3"},
                    "image": {"path": str(c3), "sha256": self._sha(c3)},
                },
            },
        }
        identity_receipt = root / "identity-receipt.json"
        identity_receipt.write_text(json.dumps({
            "fixture_id": fixture["fixture_id"],
            "method": "READ_ONLY_DEVICE_IDENTITY",
            "observed_at_utc": "2026-10-16T00:00:00Z",
            "boards": {
                name: {
                    "target": board["target"], "flash_mb": board["flash_mb"], "psram_mb": board["psram_mb"],
                    "identity": dict(board["identity"]),
                }
                for name, board in fixture["boards"].items()
            },
        }))
        fixture["identity_receipt"] = {"method": "READ_ONLY_DEVICE_IDENTITY", "path": str(identity_receipt),
                                       "sha256": self._sha(identity_receipt)}
        return fixture, s3, c3, build

    def _valid_backend(self):
        signer = Ed25519PrivateKey.generate()
        public_pem = signer.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        nonce = "9" * 64
        unsigned = {
            "schema": "gs68.backend.readiness.v1", "backend_id": "gs68-test-backend",
            "environment": "TEST_ONLY", "status": "READY", "tls_version": "TLSv1.2",
            "created_utc": "2026-10-16T00:00:00+00:00", "trusted_time_utc": "2026-10-16T00:00:00+00:00",
            "physical": "NOT_RUN", "fixture_id": "GS68-SPARE-UNIT-001",
            "source_commit": self.source, "image_sha256": "b" * 64,
            "profile_sha256": self._sha(runner.PROFILE),
            "c3_image_sha256": "f" * 64, "c3_profile_sha256": "1" * 64,
            "case_plan_sha256": self._sha(runner.CASE_PLAN), "case_id": "GS68-PHY-001",
            "challenge_nonce": nonce, "hub_id": "hub-001", "home_id": "home-001",
            "installation_epoch": "7", "client_certificate_sha256": "2" * 64,
            "server_certificate_sha256": "4" * 64,
        }
        receipt = dict(unsigned, signature_b64=base64.b64encode(
            signer.sign(capture.canonical_json(unsigned))).decode("ascii"))
        receipt_path = self.backend_dir / "readiness-receipt.json"
        key_path = self.backend_dir / "readiness-verifier.pem"
        receipt_bytes = capture.canonical_json(receipt) + b"\n"
        receipt_path.write_bytes(receipt_bytes)
        key_path.write_bytes(public_pem)
        return {
            "backend_id": "gs68-test-backend", "environment": "TEST_ONLY", "base_url": "https://cloudsync.gs68.test/api",
            "server_name": "cloudsync.gs68.test", "tls_version": "TLS1.2",
            "trusted_ca_sha256": "1" * 64, "server_certificate_sha256": "4" * 64,
            "client_certificate_sha256": "2" * 64,
            "hub_id": "hub-001", "home_id": "home-001", "installation_epoch": 7,
            "credential_reference": "test-secret://gs68/fixture-001/client-key",
            "trusted_time_evidence_reference": "receipt:trusted-time-test-01",
            "ownership_fixture_reference": "fixture:hub-home-epoch-test-01",
            "fixture_id": "GS68-SPARE-UNIT-001", "source_commit": self.source,
            "image_sha256": "b" * 64, "profile_sha256": self._sha(runner.PROFILE),
            "c3_image_sha256": "f" * 64, "c3_profile_sha256": "1" * 64,
            "case_plan_sha256": self._sha(runner.CASE_PLAN),
            "readiness_case_id": "GS68-PHY-001", "readiness_challenge_nonce": nonce,
            "evidence_signing_public_key_path": str(key_path),
            "evidence_signing_public_key_sha256": hashlib.sha256(public_pem).hexdigest(),
            "readiness_receipt_path": str(receipt_path),
            "readiness_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "commercial_sending_enabled": False, "production_credentials_used": False,
        }

    def test_case_plan_has_ten_stable_cases_with_execution_fields(self):
        cases = self.cases["cases"]
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({item["case_id"] for item in cases}), 10)
        for case in cases:
            self.assertTrue(case["prerequisites"])
            self.assertTrue(case["expected"])
            self.assertTrue(case["evidence_required"])
            self.assertTrue(case["blocked_when"])
            self.assertTrue(case["separate_approval"])

    def test_spare_fixture_template_is_unassigned_and_not_authorized(self):
        fixture = json.loads(runner.FIXTURE_TEMPLATE.read_text())
        self.assertEqual(fixture["physical_authorization"]["status"], "NOT_AUTHORIZED")
        self.assertIsNone(fixture["source_commit"])
        self.assertIsNone(fixture["boards"]["s3"]["identity"]["mac_address"])
        self.assertIsNone(fixture["boards"]["c3"]["identity"]["mac_address"])

    def test_physical_catalogue_remains_release_blocking_and_not_run(self):
        with (runner.REPO / "docs/validation/PHYSICAL_HIL_CATALOGUE.csv").open(newline="", encoding="utf-8") as stream:
            row = next(item for item in csv.DictReader(stream) if item["TEST_ID"] == "PHY-GS68-CLOUD-MTLS")
        self.assertEqual(row["STATUS"], "NOT_RUN")
        self.assertEqual(row["RELEASE_BLOCKING"], "YES")
        self.assertIn("GS68-PHY-001..010", row["DESCRIPTION"])

    def test_valid_fixture_matches_source_profile_images_and_separate_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            self.assertEqual(runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected), [])

    def test_incomplete_fixture_fails_closed(self):
        fixture = json.loads(runner.FIXTURE_TEMPLATE.read_text())
        errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
        self.assertTrue(any("source_commit" in error for error in errors))
        self.assertTrue(any("mac_address" in error or "usb_serial_short" in error for error in errors))
        self.assertTrue(any("image" in error for error in errors))

    def test_non_object_manifest_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad_fixture = root / "fixture.json"
            bad_fixture.write_text("[]")
            report_dir = root / "evidence"
            with patch.object(runner.common, "current_source_head", return_value=self.source):
                self.assertEqual(runner.main(["--fixture", str(bad_fixture), "--evidence-dir", str(report_dir)]), 0)
            result = json.loads((report_dir / "gs68_cloudsync_hil_results.json").read_text())
            self.assertTrue(any("JSON object" in error for error in result["fixture_errors"]))
            self.assertTrue(all(case["status"] == "BLOCKED" for case in result["cases"]))

    def test_wrong_source_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            errors = runner.validate_fixture(fixture, "b" * 40, self.cases, protected=self.protected)
            self.assertTrue(any("source_commit" in error for error in errors))

    def test_wrong_s3_identity_is_rejected_as_protected_c8(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            fixture["boards"]["s3"]["identity"]["mac_address"] = self.protected["boards"]["s3"]["mac"]
            errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
            self.assertTrue(any("protected C8" in error for error in errors))

    def test_wrong_observed_serial_is_rejected(self):
        expected = {"mac_address": "02:00:00:00:68:01", "usb_serial_short": "GS68-S3", "port_by_id": "/dev/serial/by-id/s3"}
        observed = dict(expected, usb_serial_short="OTHER-SERIAL")
        errors = runner.validate_observed_identity("s3", expected, observed)
        self.assertTrue(any("usb_serial_short" in error for error in errors))

    def test_identity_receipt_wrong_serial_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            receipt_path = Path(fixture["identity_receipt"]["path"])
            receipt = json.loads(receipt_path.read_text())
            receipt["boards"]["s3"]["identity"]["usb_serial_short"] = "C8-OTHER-SERIAL"
            receipt_path.write_text(json.dumps(receipt))
            fixture["identity_receipt"]["sha256"] = self._sha(receipt_path)
            errors = runner.validate_identity_receipt(fixture, base=Path(temporary))
            self.assertTrue(any("usb_serial_short" in error for error in errors))

    def test_wrong_observed_mac_and_port_are_rejected(self):
        expected = {"mac_address": "02:00:00:00:68:01", "usb_serial_short": "GS68-S3", "port_by_id": "/dev/serial/by-id/s3"}
        observed = dict(expected, mac_address="02:00:00:00:00:01", port_by_id="/dev/ttyUSB0")
        errors = runner.validate_observed_identity("s3", expected, observed)
        self.assertEqual(len(errors), 2)

    def test_s3_wrong_flash_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            fixture["boards"]["s3"]["flash_mb"] = 4
            errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
            self.assertTrue(any("16 MiB" in error for error in errors))

    def test_image_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            fixture["boards"]["c3"]["image"]["sha256"] = "0" * 64
            errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
            self.assertTrue(any("image SHA-256" in error for error in errors))

    def test_profile_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, _ = self._valid_fixture(temporary)
            fixture["profile"]["profile_sha256"] = "0" * 64
            errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
            self.assertTrue(any("profile_sha256" in error or "profile build report" in error for error in errors))

    def test_build_report_source_or_image_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, build = self._valid_fixture(temporary)
            report = json.loads(build.read_text())
            report["s3_image_sha256"] = "3" * 64
            build.write_text(json.dumps(report))
            errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
            self.assertTrue(any("build report S3 image hash" in error for error in errors))

    def test_build_report_rejects_different_committed_code_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, _, _, build = self._valid_fixture(temporary)
            report = json.loads(build.read_text())
            report["source_code_tree_oid"] = "f" * 40
            build.write_text(json.dumps(report))
            errors = runner.validate_fixture(fixture, self.source, self.cases, protected=self.protected)
            self.assertTrue(any("code tree" in error for error in errors))

    def test_backend_descriptor_accepts_test_only_nonproduction_profile(self):
        self.assertEqual(runner.validate_backend_descriptor(self._valid_backend(),
            base_dir=self.backend_dir), [])

    def test_backend_readiness_signature_and_source_binding_are_verified_offline(self):
        backend = self._valid_backend()
        receipt_path = Path(backend["readiness_receipt_path"])
        receipt = json.loads(receipt_path.read_text())
        receipt["image_sha256"] = "f" * 64
        receipt_path.write_text(json.dumps(receipt))
        backend["readiness_receipt_sha256"] = self._sha(receipt_path)
        errors = runner.validate_backend_descriptor(backend, base_dir=self.backend_dir)
        self.assertTrue(any("signature is invalid" in error for error in errors))
        self.assertTrue(any("image_sha256" in error for error in errors))

    def test_missing_backend_credentials_and_readiness_are_blocked(self):
        backend = self._valid_backend()
        backend["credential_reference"] = None
        backend["readiness_receipt_path"] = None
        errors = runner.validate_backend_descriptor(backend, base_dir=self.backend_dir)
        self.assertTrue(any("credential_reference" in error for error in errors))
        self.assertTrue(any("readiness_receipt_path" in error for error in errors))

    def test_production_backend_endpoint_or_credentials_are_rejected(self):
        backend = self._valid_backend()
        backend.update(base_url="https://api.example.com", environment="PRODUCTION",
                       commercial_sending_enabled=True, production_credentials_used=True)
        errors = runner.validate_backend_descriptor(backend, base_dir=self.backend_dir)
        self.assertTrue(any("TEST_ONLY" in error for error in errors))
        self.assertTrue(any(".test" in error for error in errors))
        self.assertTrue(any("commercial sending" in error for error in errors))
        self.assertTrue(any("production credentials" in error for error in errors))

    def test_authorization_requires_exact_fixture_case_plan_and_expiry(self):
        case_ids = [case["case_id"] for case in self.cases["cases"]]
        plan_hash = runner._sha256(runner.CASE_PLAN)
        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        auth = {"status": "APPROVED", "jira_comment": "12345", "fixture_id": "GS68-SPARE-UNIT-001",
                "authorized_case_ids": case_ids, "plan_sha256": plan_hash, "approved_by": "owner",
                "expires_utc": "2026-10-17T00:00:00Z"}
        self.assertEqual(runner.validate_authorization(auth, auth["fixture_id"], case_ids, plan_hash, now), [])
        auth["fixture_id"] = "GS114-DISPOSABLE-C3-S3"
        self.assertTrue(runner.validate_authorization(auth, "GS68-SPARE-UNIT-001", case_ids, plan_hash, now))

    def test_missing_or_expired_operator_authorization_is_blocked(self):
        case_ids = [case["case_id"] for case in self.cases["cases"]]
        errors = runner.validate_authorization({}, "GS68-SPARE-UNIT-001", case_ids, "a" * 64)
        self.assertTrue(any("not APPROVED" in error for error in errors))

    def test_interrupted_capture_cannot_be_adjudicated(self):
        errors = runner.verify_evidence_artifacts(".", [{"path": "capture.log", "sha256": "0" * 64}], False)
        self.assertIn("capture is interrupted or incomplete", errors)

    def test_missing_and_corrupted_evidence_artifacts_are_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "capture.log"
            log.write_text("captured evidence")
            descriptor = [{"path": "capture.log", "sha256": self._sha(log)}]
            self.assertEqual(runner.verify_evidence_artifacts(root, descriptor, True), [])
            descriptor[0]["sha256"] = "0" * 64
            self.assertTrue(any("checksum mismatch" in error for error in runner.verify_evidence_artifacts(root, descriptor, True)))
            self.assertTrue(runner.verify_evidence_artifacts(root, [{"path": "missing.log", "sha256": "1" * 64}], True))

    def test_simulated_evidence_never_passes_a_physical_case(self):
        case = self.cases["cases"][0]
        status, reason = runner.adjudicate_case(case, {"evidence_origin": "SIMULATED"}, {}, {}, "0" * 64,
                                                self.cases, self._valid_backend(), self.source)
        self.assertEqual(status, "BLOCKED")
        self.assertIn("cannot pass", reason)

    def test_synthetic_complete_bundle_cannot_pass_with_self_declared_physical_origin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture, s3_image, _, _ = self._valid_fixture(root)
            case_ids = [item["case_id"] for item in self.cases["cases"]]
            plan_hash = runner._sha256(runner.CASE_PLAN)
            authorization = {"status": "APPROVED", "jira_comment": "22222", "fixture_id": fixture["fixture_id"],
                             "authorized_case_ids": case_ids, "plan_sha256": plan_hash, "approved_by": "owner",
                             "expires_utc": "2035-01-01T00:00:00Z"}
            fixture["physical_authorization"] = authorization
            capture = root / "case.log"
            capture.write_text("synthetic unit-test bytes; never physical qualification evidence")
            case = self.cases["cases"][0]
            evidence = {
                "evidence_origin": "PHYSICAL", "case_id": case["case_id"],
                "fixture_id": fixture["fixture_id"], "source_commit": self.source,
                "plan_sha256": plan_hash, "profile_sha256": fixture["profile"]["profile_sha256"],
                "backend_id": "gs68-test-backend",
                "image_sha256": self._sha(s3_image), "authorization_ref": "22222",
                "capture_complete": True,
                "artifacts": [{"path": "case.log", "sha256": self._sha(capture)}],
                "observations": {name: "unit-fixture-value" for name in case["evidence_required"]},
                "outcome": "EXPECTED",
            }
            status, reason = runner.adjudicate_case(case, evidence, fixture, authorization, plan_hash,
                                                     self.cases, self._valid_backend(), self.source, evidence_root=root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("bounded GS-68 capture adapter", reason)

    def test_incomplete_physical_failure_claim_is_blocked(self):
        case = self.cases["cases"][0]
        # Incomplete provenance cannot be promoted to a physical failure or pass.
        status, _ = runner.adjudicate_case(case, {"evidence_origin": "PHYSICAL", "outcome": "UNEXPECTED"}, {}, {},
                                           "0" * 64, self.cases, self._valid_backend(), self.source)
        self.assertEqual(status, "BLOCKED")

    def test_case_outside_authorized_set_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture, s3_image, _, _ = self._valid_fixture(root)
            case = self.cases["cases"][0]
            auth = {"status": "APPROVED", "jira_comment": "22", "fixture_id": fixture["fixture_id"],
                    "authorized_case_ids": [self.cases["cases"][1]["case_id"]],
                    "plan_sha256": runner._sha256(runner.CASE_PLAN), "approved_by": "owner",
                    "expires_utc": "2035-01-01T00:00:00Z"}
            fixture["physical_authorization"] = auth
            capture = root / "case.log"
            capture.write_text("unit-test only")
            evidence = {"evidence_origin": "PHYSICAL", "case_id": case["case_id"],
                        "fixture_id": fixture["fixture_id"], "source_commit": self.source,
                        "plan_sha256": runner._sha256(runner.CASE_PLAN),
                        "profile_sha256": fixture["profile"]["profile_sha256"],
                        "backend_id": "gs68-test-backend",
                        "image_sha256": self._sha(s3_image), "authorization_ref": "22",
                        "capture_complete": True,
                        "artifacts": [{"path": "case.log", "sha256": self._sha(capture)}],
                        "observations": {name: "unit-value" for name in case["evidence_required"]},
                        "outcome": "EXPECTED"}
            status, _ = runner.adjudicate_case(case, evidence, fixture, auth,
                                               runner._sha256(runner.CASE_PLAN), self.cases,
                                               self._valid_backend(), self.source, evidence_root=root)
            self.assertEqual(status, "BLOCKED")

    def test_unexpected_acceptance_claim_is_blocked_without_trusted_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture, s3_image, _, _ = self._valid_fixture(root)
            case = self.cases["cases"][3]
            case_ids = [item["case_id"] for item in self.cases["cases"]]
            plan_hash = runner._sha256(runner.CASE_PLAN)
            auth = {"status": "APPROVED", "jira_comment": "33333", "fixture_id": fixture["fixture_id"],
                    "authorized_case_ids": case_ids, "plan_sha256": plan_hash, "approved_by": "owner",
                    "expires_utc": "2035-01-01T00:00:00Z"}
            fixture["physical_authorization"] = auth
            capture = root / "case.log"
            capture.write_text("unit-test only")
            evidence = {"evidence_origin": "PHYSICAL", "case_id": case["case_id"],
                        "fixture_id": fixture["fixture_id"], "source_commit": self.source,
                        "plan_sha256": plan_hash, "profile_sha256": fixture["profile"]["profile_sha256"],
                        "backend_id": "gs68-test-backend",
                        "image_sha256": self._sha(s3_image), "authorization_ref": "33333",
                        "capture_complete": True,
                        "artifacts": [{"path": "case.log", "sha256": self._sha(capture)}],
                        "observations": {name: "unit-value" for name in case["evidence_required"]},
                        "outcome": "UNEXPECTED"}
            status, reason = runner.adjudicate_case(case, evidence, fixture, auth, plan_hash, self.cases,
                                                    self._valid_backend(), self.source, evidence_root=root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("bounded GS-68 capture adapter", reason)

    def test_default_dry_run_never_opens_device_or_network_interfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_dir = Path(temporary) / "evidence"
            with patch.object(runner.common, "current_source_head", return_value=self.source), \
                 patch.object(runner.common.subprocess, "run", side_effect=AssertionError("subprocess device operation")), \
                 patch.object(socket, "socket", side_effect=AssertionError("network socket opened")), \
                 patch("urllib.request.urlopen", side_effect=AssertionError("backend contacted")):
                self.assertEqual(runner.main(["--evidence-dir", str(report_dir)]), 0)
            result = json.loads((report_dir / "gs68_cloudsync_hil_results.json").read_text())
            self.assertEqual(result["mode"], "SAFE_DRY_RUN")
            self.assertEqual(result["physical"], "NOT_RUN")
            self.assertEqual(result["hardware_actions"], [])
            self.assertEqual(len(result["cases"]), 10)
            rendered = json.dumps(result)
            self.assertNotIn("vault://", rendered)
            self.assertNotIn("test-secret://", rendered)
            self.assertNotIn("-----BEGIN", rendered)

    def test_requested_physical_execution_without_fixture_authorization_is_blocked_before_io(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_dir = Path(temporary) / "evidence"
            with patch.object(runner.common, "current_source_head", return_value=self.source), \
                 patch.object(runner.common.subprocess, "run", side_effect=AssertionError("subprocess device operation")), \
                 patch.object(socket, "socket", side_effect=AssertionError("network socket opened")), \
                 patch("gs68_capture.PySerialTransport.open", side_effect=AssertionError("serial opened")), \
                 patch("urllib.request.urlopen", side_effect=AssertionError("backend contacted")):
                self.assertEqual(runner.main(["--run-physical", "--evidence-dir", str(report_dir)]), 3)
            result = json.loads((report_dir / "gs68_cloudsync_hil_results.json").read_text())
            self.assertEqual(result["mode"], "PHYSICAL_REQUEST_BLOCKED")
            self.assertEqual(result["overall"], "BLOCKED")
            self.assertEqual(result["physical"], "NOT_RUN")
            self.assertEqual(result["hardware_actions"], [])
            self.assertTrue(any("fixture-specific physical authorization" in item
                                for item in result["physical_blocker"]))

    def test_test_profile_enables_only_ds_and_tls12(self):
        profile = runner.PROFILE.read_text()
        self.assertIn("CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y", profile)
        self.assertIn("CONFIG_MBEDTLS_SSL_PROTO_TLS1_2=y", profile)
        self.assertNotIn("CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y", profile)
        self.assertNotIn("CONFIG_GS_CLOUDSYNC_ENABLED=y", profile)
        self.assertNotIn("GS_HIL_BUILD=y", profile)
        self.assertNotIn("PRIVATE KEY", profile)
        defaults = (runner.PRODUCT / "firmware/hub/target/esp32s3/idf/sdkconfig.defaults").read_text()
        cmake = (runner.PRODUCT / "firmware/hub/target/esp32s3/idf/CMakeLists.txt").read_text()
        self.assertNotIn("CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y", defaults)
        self.assertNotIn("sdkconfig.gs68_cloudsync_hil.defaults", cmake)


if __name__ == "__main__":
    unittest.main(verbosity=2)
