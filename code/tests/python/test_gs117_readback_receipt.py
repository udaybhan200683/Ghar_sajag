"""Offline tests for the bounded GS-117 receipt collector and one-use authority."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "local"
sys.path.insert(0, str(TOOLS))
import gs117_hil_authorization as auth
import gs117_tc001_readback as collector
import gs117_tc001_console as console


class ReadbackRangeTests(unittest.TestCase):
    def test_authorized_ranges_match_collector_allowlist_exactly(self):
        expected = [
            {"role": role, "name": name, "offset": offset, "size": size}
            for role, regions in collector.READ_RANGES.items()
            for name, (offset, size) in regions.items()
        ]
        self.assertEqual(auth.READBACK_RECEIPT_RANGES, expected)

    def test_exact_approved_fixture_ranges_are_accepted(self):
        capacities = {"c3": 4 * 1024 * 1024, "s3": 16 * 1024 * 1024}
        count = 0
        for role, ranges in collector.READ_RANGES.items():
            for name, (offset, size) in ranges.items():
                self.assertIsNone(collector.validate_read_range(
                    role, name, offset, size, capacities[role]))
                count += 1
        self.assertEqual(count, 7)

    def test_only_s3_bootloader_region_is_readable_below_partition_table(self):
        self.assertIsNone(collector.validate_read_range(
            "s3", "bootloader-region", 0, 0x8000, 16 * 1024 * 1024))
        with self.assertRaises(collector.GuardFailure):
            collector.validate_read_range("c3", "bootloader-region", 0, 0x8000,
                                          4 * 1024 * 1024)

    def test_nvs_generic_dump_and_unlisted_regions_are_rejected(self):
        for role, name, offset, size in (
                ("s3", "nvs", 0x9000, 0x6000),
                ("c3", "all-flash", 0, 4 * 1024 * 1024),
                ("s3", "bootloader-region", 0x1000, 0x7000)):
            with self.subTest(role=role, name=name):
                with self.assertRaises(collector.GuardFailure):
                    collector.validate_read_range(role, name, offset, size,
                                                  16 * 1024 * 1024)

    def test_bounds_reject_negative_zero_overflow_bool_and_capacity_overrun(self):
        invalid = (
            (-1, 0x8000, 16 * 1024 * 1024),
            (0, 0, 16 * 1024 * 1024),
            (0, 0x8001, 16 * 1024 * 1024),
            (True, 0x8000, 16 * 1024 * 1024),
            (0, 0x8000, True),
            (0, 0x8000, 0),
            (2**128, 0x8000, 16 * 1024 * 1024),
            (16 * 1024 * 1024 - 1, 0x8000, 16 * 1024 * 1024),
        )
        for offset, size, capacity in invalid:
            with self.subTest(offset=offset, size=size, capacity=capacity):
                with self.assertRaises(collector.GuardFailure):
                    collector.validate_read_range("s3", "bootloader-region",
                                                  offset, size, capacity)

    def test_wrong_role_or_malformed_range_types_fail_closed(self):
        for args in ((None, "bootloader-region", 0, 0x8000, 16 * 1024 * 1024),
                     ([], "bootloader-region", 0, 0x8000, 16 * 1024 * 1024),
                     ("s3", [], 0, 0x8000, 16 * 1024 * 1024),
                     ("s3", "bootloader-region", "0", 0x8000, 16 * 1024 * 1024)):
            with self.subTest(args=args), self.assertRaises((collector.GuardFailure, TypeError)):
                collector.validate_read_range(*args)

    def test_region_read_is_exact_private_and_hash_recorded(self):
        class FakeTarget:
            calls = []

            def read_flash(self, offset, size):
                self.calls.append((offset, size))
                return b"B" * size

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            receipt = {"flash_reads": []}
            target = FakeTarget()
            data = collector.read_flash_region(
                target, collector.EXPECTED["s3"], out, "s3", "bootloader-region",
                0, 0x8000, receipt)
            output = out / "s3-bootloader-region.bin"
            self.assertEqual(len(data), 0x8000)
            self.assertEqual(target.calls, [(0, 0x8000)])
            self.assertEqual(output.read_bytes(), data)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(receipt["flash_reads"], [{
                "region": "bootloader-region", "offset": 0, "size": 0x8000,
                "sha256": hashlib.sha256(data).hexdigest()}])

    def test_invalid_range_is_rejected_before_target_read(self):
        class FakeTarget:
            called = False

            def read_flash(self, offset, size):
                self.called = True
                return b"x" * size

        with tempfile.TemporaryDirectory() as directory:
            target = FakeTarget()
            with self.assertRaises(collector.GuardFailure):
                collector.read_flash_region(
                    target, collector.EXPECTED["s3"], Path(directory), "s3",
                    "bootloader-region", 1, 0x7fff, {"flash_reads": []})
            self.assertFalse(target.called)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_authorization_session_is_rejected_before_wsl_validation(self):
        with patch.object(collector.subprocess, "run") as run:
            with self.assertRaisesRegex(collector.GuardFailure,
                                        "READBACK_AUTHORIZATION_SESSION_REQUIRED"):
                collector.claim_authorized_role("c3", "")
            run.assert_not_called()

    def test_console_fails_before_windows_launch_when_authority_is_missing(self):
        with patch.object(auth, "load_readback_receipt_authorization",
                          side_effect=ValueError("readback_receipt_policy_not_private")), \
                patch.object(console.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "policy_not_private"):
                console.readback_receipts_once()
            run.assert_not_called()

    def test_short_or_non_bytes_read_is_not_receipted(self):
        class FakeTarget:
            def read_flash(self, _offset, _size):
                return b"short"

        with tempfile.TemporaryDirectory() as directory:
            receipt = {"flash_reads": []}
            with self.assertRaises(collector.GuardFailure):
                collector.read_flash_region(
                    FakeTarget(), collector.EXPECTED["s3"], Path(directory), "s3",
                    "bootloader-region", 0, 0x8000, receipt)
            self.assertEqual(receipt["flash_reads"], [])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_region_output_cannot_overwrite_existing_evidence(self):
        class FakeTarget:
            def read_flash(self, _offset, size):
                return b"B" * size

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "s3-bootloader-region.bin"
            output.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                collector.read_flash_region(
                    FakeTarget(), collector.EXPECTED["s3"], Path(directory), "s3",
                    "bootloader-region", 0, 0x8000, {"flash_reads": []})
            self.assertEqual(output.read_bytes(), b"preserve")

    def test_artifact_size_hash_version_and_elf_are_bound(self):
        content = b"reviewed-image"
        image_hash = hashlib.sha256(content).hexdigest()
        info = ("App version: reviewed-version\nELF file SHA256: " + "a" * 64 +
                "\nChecksum: image (valid)\nValidation hash: test\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "candidate.bin").write_bytes(content)
            (root / "MANIFEST.json").write_text(json.dumps({
                "files": {"candidate.bin": {"sha256": image_hash}}}))
            (root / "candidate.bin.image-info.txt").write_text(info)
            spec = {"artifact": "candidate.bin", "image_sha256": image_hash,
                    "image_size": len(content), "version": "reviewed-version",
                    "elf": "a" * 64}
            with patch.object(collector, "CHECKPOINT", root), \
                    patch.dict(collector.EXPECTED, {"s3": spec}):
                result, digest, _ = collector.artifact("s3")
                self.assertEqual((result, digest), (content, image_hash))
                spec["image_size"] += 1
                with self.assertRaises(collector.GuardFailure):
                    collector.artifact("s3")

    def test_collector_has_one_read_path_and_no_write_or_secret_read_api(self):
        import ast
        tree = ast.parse(Path(collector.__file__).read_text())
        calls = [node.func.attr if isinstance(node.func, ast.Attribute) else
                 node.func.id if isinstance(node.func, ast.Name) else ""
                 for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertEqual(calls.count("read_flash"), 1)
        for prohibited in ("write_flash", "erase_flash", "flash_id", "read_nvs",
                           "read_efuse", "read_flash_slow"):
            self.assertNotIn(prohibited, calls)


class ReadbackAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "receipt-state"
        self.state.mkdir(mode=0o700)
        self.state.chmod(0o700)
        self.hardware_state = self.root / "standing-state"
        self.dev_state = self.root / "development-state"
        for directory in (self.hardware_state, self.dev_state):
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
        self.hardware_audit = self.hardware_state / "audit.jsonl"
        self.dev_audit = self.dev_state / "audit.jsonl"
        self.hardware_audit.write_text('{"event":"historical-hardware-record"}\n')
        self.dev_audit.write_text('{"event":"historical-dev-record"}\n')
        self.hardware_audit.chmod(0o600)
        self.dev_audit.chmod(0o600)
        self.policy_path = self.root / "receipt-policy.json"
        self.audit_path = self.state / "audit.jsonl"
        self.fake_partition_parser = self.root / "gen_esp32part.py"
        self.fake_partition_parser.write_text("offline partition-parser source")
        self.fake_partition_parser.chmod(0o600)
        self.partition_patch = patch.object(
            auth, "READBACK_RECEIPT_PARTITION_PARSER", self.fake_partition_parser)
        self.partition_patch.start()
        self.addCleanup(self.partition_patch.stop)
        self.authorization_id = "a" * 32
        self.approval_ref = "GS-117#11999"
        self.activated = datetime.now(timezone.utc).replace(microsecond=0)
        self.expires = self.activated + timedelta(hours=1)
        self.tool_files = {}
        for name in auth.READBACK_RECEIPT_TOOL_NAMES:
            if name == "authorization_module":
                path = Path(auth.__file__).resolve()
            elif name == "controller":
                path = auth.READBACK_RECEIPT_CONTROLLER.resolve()
            elif name == "collector":
                path = Path(collector.__file__).resolve()
            elif name == "partition_parser":
                path = auth.READBACK_RECEIPT_PARTITION_PARSER.resolve()
            else:
                path = self.root / (name + ".source")
                path.write_text("offline tool fixture: " + name)
                path.chmod(0o600)
            self.tool_files[name] = {"path": str(path), "sha256": auth.digest(path)}
        self.versions = {"python": "3.12.1", "esptool": "5.4.0",
                         "pyserial": "3.5", "esp_idf": "6.0.3"}
        self.policy = {
            "schema_version": 1, "profile": auth.READBACK_RECEIPT_PROFILE,
            "operation": auth.READBACK_RECEIPT_OPERATION,
            "authorization_id": self.authorization_id,
            "owner_approval_ref": self.approval_ref, "owner_approved": True,
            "active": True, "revoked": False,
            "activated_at": self.activated.isoformat(), "expires_at": self.expires.isoformat(),
            "max_uses": 1, "renewable": False,
            "fixture": auth.READBACK_RECEIPT_FIXTURE,
            "read_ranges": auth.READBACK_RECEIPT_RANGES,
            "reset_budget": auth.READBACK_RECEIPT_RESET_BUDGET,
            "prohibited_operations": auth.READBACK_RECEIPT_PROHIBITED,
            "tool_files": self.tool_files, "tool_versions": self.versions,
            "activation_record_sha256": "0" * 64,
        }
        self.activation = None
        self.write_grant()
        self.patches = [
            patch.object(auth, "READBACK_RECEIPT_POLICY", self.policy_path),
            patch.object(auth, "READBACK_RECEIPT_STATE", self.state),
            patch.object(auth, "STATE", self.hardware_state),
            patch.object(auth, "DEV_STATE", self.dev_state),
            patch.object(auth, "READBACK_RECEIPT_PROCEDURE", Path(collector.__file__).resolve()),
            patch.object(auth, "READBACK_RECEIPT_CONTROLLER",
                         Path(auth.__file__).resolve().with_name("gs117_tc001_console.py")),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def write_grant(self, *, include_activation=True):
        scope = auth._readback_receipt_scope_sha256(self.policy)
        if include_activation:
            activation = {
                "event": "readback_receipt_activated",
                "authorization_id": self.authorization_id,
                "activation_id": self.authorization_id,
                "approval_ref": self.approval_ref,
                "scope_sha256": scope,
                "activated_at": self.policy["activated_at"],
                "expires_at": self.policy["expires_at"],
                "fixture": auth.READBACK_RECEIPT_FIXTURE,
                "operation": auth.READBACK_RECEIPT_OPERATION,
                "read_ranges": auth.READBACK_RECEIPT_RANGES,
                "reset_budget": auth.READBACK_RECEIPT_RESET_BUDGET,
                "tool_hashes": {k: v["sha256"] for k, v in self.tool_files.items()},
                "tool_versions": self.versions,
                "max_uses": 1,
                "previous_record_sha256": auth.READBACK_RECEIPT_ZERO_HASH,
            }
            activation["record_sha256"] = auth._canonical_record_sha256(activation)
            self.policy["activation_record_sha256"] = activation["record_sha256"]
            self.activation = activation
            self.audit_path.write_text(json.dumps(activation, sort_keys=True) + "\n")
            self.audit_path.chmod(0o600)
        else:
            self.audit_path.write_text("")
            self.audit_path.chmod(0o600)
        self.policy_path.write_text(json.dumps(self.policy, sort_keys=True))
        self.policy_path.chmod(0o600)

    def test_valid_exact_owner_activated_scope_is_accepted(self):
        result = auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))
        self.assertEqual(result["operation"], "readback_receipt")
        self.assertEqual(auth.readback_receipt_status(now=self.activated + timedelta(minutes=1))["status"],
                         "ACTIVE")

    def test_matching_reference_without_audited_activation_is_not_authority(self):
        self.write_grant(include_activation=False)
        with self.assertRaisesRegex(ValueError, "activation_missing_or_replayed"):
            auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))

    def test_missing_policy_is_not_authority(self):
        self.policy_path.unlink()
        self.assertEqual(auth.readback_receipt_status()["status"], "BLOCKED")
        with self.assertRaises(ValueError):
            auth.load_readback_receipt_authorization()

    def test_wrong_fixture_is_rejected(self):
        self.policy["fixture"] = dict(self.policy["fixture"], home_id="other-home")
        self.write_grant()
        with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
            auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))

    def test_wrong_device_id_or_usb_identity_is_rejected(self):
        for role, field, value in (("c3", "device_id", "c3-other"),
                                   ("c3", "serial_number", "00:00:00:00:00:00"),
                                   ("s3", "device_id", "hub-other"),
                                   ("s3", "port", "COM11")):
            with self.subTest(role=role, field=field):
                self.policy["fixture"] = json.loads(json.dumps(auth.READBACK_RECEIPT_FIXTURE))
                self.policy["fixture"][role][field] = value
                self.write_grant()
                with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
                    auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))
        self.policy["fixture"] = auth.READBACK_RECEIPT_FIXTURE
        self.write_grant()

    def test_wrong_collector_hash_is_rejected(self):
        self.policy["tool_files"]["collector"]["sha256"] = "f" * 64
        self.write_grant()
        with self.assertRaisesRegex(ValueError, "tool_identity_mismatch"):
            auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))

    def test_wrong_controller_runtime_or_authorization_source_hash_is_rejected(self):
        for name in ("controller", "python_runtime", "authorization_module", "esptool_loader"):
            with self.subTest(tool=name):
                original = self.tool_files[name]["sha256"]
                self.policy["tool_files"][name]["sha256"] = "f" * 64
                self.write_grant()
                with self.assertRaisesRegex(ValueError, "tool_identity_mismatch"):
                    auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))
                self.policy["tool_files"][name]["sha256"] = original
                self.write_grant()

    def test_range_or_reset_scope_change_is_rejected(self):
        self.policy["read_ranges"] = list(auth.READBACK_RECEIPT_RANGES[:-1])
        self.write_grant()
        with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
            auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))

    def test_expired_or_future_grants_fail_closed(self):
        before = self.activated - timedelta(seconds=1)
        after = self.expires
        for moment in (before, after):
            with self.subTest(moment=moment), self.assertRaisesRegex(
                    ValueError, "expired_or_not_yet_active"):
                auth.load_readback_receipt_authorization(now=moment)

    def test_wrong_schema_use_count_or_renewal_setting_is_rejected(self):
        for key, value in (("max_uses", 2), ("max_uses", True), ("renewable", True)):
            with self.subTest(key=key, value=value):
                self.policy[key] = value
                self.write_grant()
                with self.assertRaises(ValueError):
                    auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))
                self.policy[key] = 1 if key == "max_uses" else False
                self.write_grant()

    def test_changed_activation_record_or_replayed_activation_is_rejected(self):
        rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        rows[0]["read_ranges"] = []
        self.audit_path.write_text(json.dumps(rows[0], sort_keys=True) + "\n")
        self.audit_path.chmod(0o600)
        with self.assertRaises(ValueError):
            auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))

    def test_session_is_reserved_before_use_and_cannot_replay(self):
        with auth.readback_receipt_session(now=self.activated + timedelta(minutes=1)) as receipt:
            self.claim_role(receipt, "c3")
            self.claim_role(receipt, "s3")
            self.write_receipt(receipt, "c3")
            self.write_receipt(receipt, "s3")
            receipt["outcome"] = "PASS"
            self.assertEqual(auth.readback_receipt_status()["status"], "CONSUMED")
        with self.assertRaisesRegex(ValueError, "authorization_consumed"):
            with auth.readback_receipt_session():
                self.fail("one-use authorization replayed")
        rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        events = [row["event"] for row in rows]
        self.assertEqual(events, ["readback_receipt_activated", "readback_receipt_reserved",
                                  "readback_receipt_role_started", "readback_receipt_role_started",
                                  "readback_receipt_completed"])
        self.assertEqual(rows[-1]["outcome"], "PASS")
        self.assertRegex(rows[-1]["evidence_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(rows[-1]["evidence_entries"], auth._readback_receipt_evidence_hash(
            rows[-1]["evidence_dir"])[1])

    def claim_role(self, operation, role):
        runtime_names = set(auth.READBACK_RECEIPT_TOOL_NAMES) - {
            "authorization_module", "controller", "collector", "python_runtime"}
        runtime_hashes = {name: self.tool_files[name]["sha256"] for name in runtime_names}
        return auth.claim_readback_receipt_role(
            operation["session_id"], role,
            self.tool_files["collector"]["sha256"],
            self.tool_files["python_runtime"]["sha256"],
            self.versions["python"], self.versions["pyserial"], runtime_hashes,
            now=self.activated + timedelta(minutes=1))

    def write_receipt(self, operation, role):
        directory = Path(operation["evidence_dir"]) / role
        directory.mkdir(mode=0o700)
        receipt = {"role": role, "status": "PASS",
                   "procedure_sha256": self.tool_files["collector"]["sha256"],
                   "application_restoration": {"status": "USB_IDENTITY_REENUMERATED"}}
        output = directory / (role + "-readback.json")
        output.write_text(json.dumps(receipt))
        output.chmod(0o600)

    def test_failed_or_partial_capture_is_terminal_and_preserved(self):
        with auth.readback_receipt_session() as receipt:
            receipt["outcome"] = "PARTIAL"
            note = Path(receipt["evidence_dir"]) / "partial.json"
            note.write_text('{"status":"PARTIAL"}')
            note.chmod(0o600)
        rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        self.assertEqual(rows[-1]["event"], "readback_receipt_completed")
        self.assertEqual(rows[-1]["outcome"], "PARTIAL")
        self.assertEqual(auth.readback_receipt_status()["status"], "CONSUMED")

    def test_pass_claim_without_both_verified_target_receipts_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pass_evidence_validation_failed"):
            with auth.readback_receipt_session() as operation:
                operation["outcome"] = "PASS"
                partial = Path(operation["evidence_dir"]) / "controller-only.json"
                partial.write_text('{"status":"PASS"}')
                partial.chmod(0o600)
        rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        self.assertEqual(rows[-1]["event"], "readback_receipt_completed")
        self.assertEqual(rows[-1]["outcome"], "FAIL")


    def test_exception_fails_closed_and_keeps_partial_evidence_hash(self):
        with self.assertRaisesRegex(RuntimeError, "capture failed"):
            with auth.readback_receipt_session() as operation:
                note = Path(operation["evidence_dir"]) / "partial.json"
                note.write_text('{"status":"IN_PROGRESS"}')
                note.chmod(0o600)
                raise RuntimeError("capture failed")
        failed_rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        self.assertEqual(failed_rows[-1]["event"], "readback_receipt_failed")
        self.assertRegex(failed_rows[-1]["evidence_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(auth.readback_receipt_status()["status"], "CONSUMED")

    def test_revocation_before_reservation_is_audited_and_blocks_use(self):
        result = auth.revoke_readback_receipt_authorization("owner cancelled before device access")
        self.assertEqual(result["status"], "REVOKED")
        self.assertEqual(auth.readback_receipt_status()["status"], "REVOKED")
        with self.assertRaisesRegex(ValueError, "authorization_revoked"):
            with auth.readback_receipt_session():
                self.fail("revoked authorization used")

    def test_revocation_rejected_after_reservation_and_no_second_reservation(self):
        with auth.readback_receipt_session():
            with self.assertRaisesRegex(ValueError, "operation_already_active"):
                auth.revoke_readback_receipt_authorization("too late")

    def test_role_claim_mismatch_or_replay_is_rejected(self):
        with auth.readback_receipt_session(now=self.activated + timedelta(minutes=1)) as operation:
            self.claim_role(operation, "c3")
            with self.assertRaisesRegex(ValueError, "role_replay"):
                self.claim_role(operation, "c3")
            with self.assertRaisesRegex(ValueError, "session_or_procedure_mismatch"):
                auth.claim_readback_receipt_role(
                    operation["session_id"], "s3", "f" * 64,
                    self.tool_files["python_runtime"]["sha256"],
                    self.versions["python"], self.versions["pyserial"],
                    {name: entry["sha256"] for name, entry in self.tool_files.items()
                     if name not in {"authorization_module", "controller", "collector", "python_runtime"}},
                    now=self.activated + timedelta(minutes=1))
            operation["outcome"] = "BLOCKED"

    def test_concurrent_session_is_rejected_without_second_audit_entry(self):
        with auth.readback_receipt_session():
            with self.assertRaisesRegex(ValueError, "operation_already_active"):
                with auth.readback_receipt_session():
                    self.fail("concurrent receipt operation opened")
        rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        self.assertEqual(sum(row["event"] == "readback_receipt_reserved" for row in rows), 1)

    def test_existing_hil_session_lock_blocks_receipt_reservation(self):
        import fcntl
        lock_path = self.hardware_state / "session.lock"
        lock_path.write_text("")
        lock_path.chmod(0o600)
        with lock_path.open("r+") as active:
            fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "hardware_operation_already_active"):
                with auth.readback_receipt_session():
                    self.fail("receipt operation overlapped existing HIL session")
        rows = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        self.assertEqual([row["event"] for row in rows], ["readback_receipt_activated"])

    def test_corrupt_or_missing_audit_fails_closed(self):
        self.audit_path.write_text("not-json\n")
        self.audit_path.chmod(0o600)
        with self.assertRaises(ValueError):
            auth.load_readback_receipt_authorization(now=self.activated + timedelta(minutes=1))

    def test_existing_hardware_authorization_constants_are_unchanged(self):
        self.assertIn("readback", auth.PROHIBITED)
        self.assertNotIn("readback_receipt", auth.DEV_OPERATIONS)
        self.assertNotIn("readback_receipt", auth.OPERATIONS)
        self.assertNotEqual(auth.READBACK_RECEIPT_POLICY, auth.POLICY)
        self.assertNotEqual(auth.READBACK_RECEIPT_STATE, auth.STATE)
        self.assertTrue({"flash", "erase", "credentials", "readback"}
                        .issubset(set(auth.PROHIBITED)))
        self.assertTrue({"generic_readback", "flash_write", "flash_erase", "credentials",
                         "keys", "efuses", "nvs", "unrelated_flash"}
                        .issubset(set(auth.READBACK_RECEIPT_PROHIBITED)))

    def test_receipt_operation_does_not_modify_hardware_or_dev_ledgers(self):
        before = (hashlib.sha256(self.hardware_audit.read_bytes()).hexdigest(),
                  hashlib.sha256(self.dev_audit.read_bytes()).hexdigest())
        with auth.readback_receipt_session() as operation:
            evidence = Path(operation["evidence_dir"]) / "capture-note.json"
            evidence.write_text('{"status":"NOT_RUN"}')
            evidence.chmod(0o600)
            operation["outcome"] = "BLOCKED"
        after = (hashlib.sha256(self.hardware_audit.read_bytes()).hexdigest(),
                 hashlib.sha256(self.dev_audit.read_bytes()).hexdigest())
        self.assertEqual(after, before)


class ScopeGrantIssuanceTests(unittest.TestCase):
    """Exercise the separate owner-driven issuance/activation path offline."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.issue_state = self.root / 'issuance'
        self.config = self.root / 'config'
        self.config.mkdir(mode=0o700)
        self.readback_policy = self.config / 'readback.json'
        self.motion_policy = self.config / 'motion.json'
        self.readback_state = self.root / 'readback-state'
        self.motion_state = self.root / 'motion-state'
        self.hardware_state = self.root / 'hardware-state'
        self.dev_state = self.root / 'dev-state'
        self.hardware_state.mkdir(mode=0o700)
        self.historical_latch = self.hardware_state / 'historical-latch.json'
        self.historical_latch.write_bytes(b'{"status":"SAFETY_LATCHED","used":1,"limit":1}\n')
        self.historical_latch.chmod(0o600)
        self.historical_latch_bytes = self.historical_latch.read_bytes()
        self.review = {
            'reviewed_commit': 'a' * 40,
            'reviewer': auth.GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID,
            'source_fingerprints': {name: ('b' * 64) for name in auth.GS117_SCOPE_SOURCE_NAMES},
            'test_evidence_path': str(self.root / 'test-evidence.json'),
            'test_evidence_sha256': 'c' * 64,
            'validation_summary': {'gs117_focused': 'PASS', 'framework': 'PASS',
                                   'feature_coverage': 'PASS'},
        }
        for name in auth.MOTION_EVENT_ONCE_TOOLS:
            self.review['source_fingerprints'][name] = 'e' * 64
        self.approval = {
            'issue_key': auth.GS117_SCOPE_APPROVAL_ISSUE,
            'comment_id': auth.GS117_SCOPE_APPROVAL_COMMENT_ID,
            'author_account_id': auth.GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID,
            'body_sha256': auth.GS117_SCOPE_APPROVAL_BODY_SHA256,
            'approval_ref': auth.GS117_SCOPE_APPROVAL_REF,
        }
        self.approval_evidence = {'issue_key': 'GS-117', 'comment_id': '11933',
                                  'author_account_id': 'owner', 'body': 'verified approval'}
        self.receipt_tools = {
            name: {'path': str(self.root / (name + '.tool')), 'sha256': 'd' * 64}
            for name in auth.READBACK_RECEIPT_TOOL_NAMES
        }
        self.motion_tools = {
            name: {'path': str(path), 'sha256': 'e' * 64}
            for name, path in auth.MOTION_EVENT_ONCE_TOOLS.items()
        }
        self.versions = {'python': '3.12.1', 'esptool': '5.4.0',
                         'pyserial': '3.5', 'esp_idf': '6.0.3'}
        self.scope_a_receipt = {
            'authorization_id': 'f' * 32, 'scope_sha256': '1' * 64,
            'session_id': '2' * 32, 'evidence_dir': str(self.root / 'scope-a-evidence'),
            'evidence_sha256': '3' * 64, 'completed_at': datetime.now(timezone.utc).isoformat(),
            'receipt_sha256': {'c3': '4' * 64, 's3': '5' * 64},
        }
        self.patches = [
            patch.object(auth, 'GS117_SCOPE_ISSUANCE_STATE', self.issue_state),
            patch.object(auth, 'READBACK_RECEIPT_POLICY', self.readback_policy),
            patch.object(auth, 'MOTION_EVENT_ONCE_POLICY', self.motion_policy),
            patch.object(auth, 'READBACK_RECEIPT_STATE', self.readback_state),
            patch.object(auth, 'MOTION_EVENT_ONCE_STATE', self.motion_state),
            patch.object(auth, 'STATE', self.hardware_state),
            patch.object(auth, 'DEV_STATE', self.dev_state),
            patch.object(auth, '_verify_gs117_scope_source_review', return_value=self.review),
            patch.object(auth, '_readback_receipt_tool_hashes',
                         return_value={name: 'd' * 64 for name in auth.READBACK_RECEIPT_TOOL_NAMES}),
            patch.object(auth, '_motion_event_tool_hashes',
                         return_value={name: 'e' * 64 for name in auth.MOTION_EVENT_ONCE_TOOLS}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_untrusted_or_changed_owner_approval_is_rejected(self):
        for evidence in (
                {},
                {'issue_key': 'GS-117', 'comment_id': '11932',
                 'author_account_id': auth.GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID, 'body': 'x'},
                {'issue_key': 'GS-117', 'comment_id': '11933',
                 'author_account_id': 'not-owner', 'body': 'x'},
                {'issue_key': 'GS-117', 'comment_id': '11933',
                 'author_account_id': auth.GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID, 'body': 'x'},
        ):
            with self.subTest(evidence=evidence), self.assertRaisesRegex(
                    ValueError, 'owner_scope_approval_not_verified'):
                auth._verify_gs117_11933_approval(evidence)

    def test_exact_owner_jira_approval_snapshot_is_accepted(self):
        body = """2026-11-06 — OWNER APPROVAL FOR TWO INDEPENDENT ONE-USE GS-117 DEVELOPMENT OPERATIONS

Owner explicitly replied \"approved\" to the consolidated, conditional Scope A / Scope B proposal from GS117_ONE_EVENT_USB_ANDROID_READINESS_20261106.md, as presented in chat. This comment records owner intent; it is not a completed technical authorization, a receipt or a PASS.

Scope A: One use of the already reviewed installed-device receipt workflow on exactly the documented Home/C3/S3 fixture, limited to the seven previously reviewed read regions. The existing procedure's one ROM entry and one USB-aware restore reset per target are included and acknowledged. No retry, writes, erase, credentials, protected/unrelated flash, extra resets, bootstrap, event or firmware change.

Scope B: Conditional authorization for exactly one no-flash USB-triggered motion_event_once through the existing C3→authenticated S3→durable Hub/CloudSync→PostgreSQL→caregiver API→actual installed Android path, ONLY after Scope A returns verified matching fresh receipts and all current fixture, source/tool pin, separate audit/authorization, Android and authenticated-readiness guards pass. Use current reviewed one-event code path; C3 COM-open incidental reset risk acknowledged, no S3 UART opening, no explicit reset, no bootstrap, no retries, no second injection or five-event campaign. A Scope A failure/UNKNOWN blocks Scope B.

Both operations require their distinct reviewed one-use grants via the existing audited mechanism, exact final source/tool/fixture hashes and unchanged current safeguards; do not edit/renew/reuse old manifest. Scope B must not activate ahead of verified Scope A and current Android/readiness checks. Preserve historical GS-117 #11897 SAFETY_LATCHED 1/1 and #11886 unchanged. Prior GS-179 network authorization does not confer hardware rights. GS-D029 rollback requirement continues for firmware installation, which is not approved. Stop and report on identity/security/hash/receipt/authorization mismatch rather than bypassing a guard.

No actual device, software authorization activation or event test is claimed by posting this comment. Goal is one fresh physical-board USB-input event visible in Android; it is not optical PIR TC-001 acceptance or 5/5 campaign. Follow AGENTS.md/Jira/Git audit, existing test/authorization mechanism, preserve evidence and untracked work, document resulting status and next priority."""
        evidence = {
            'issue_key': 'GS-117', 'comment_id': '11933',
            'author_account_id': auth.GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID,
            'body': body,
        }
        verified = auth._verify_gs117_11933_approval(evidence)
        self.assertEqual(verified['approval_ref'], 'GS-117#11933')

    def test_source_review_requires_current_commit_fingerprints_and_private_test_receipt(self):
        for active_patch in self.patches:
            active_patch.stop()
        root = Path(auth.__file__).resolve().parents[3]
        head = __import__('subprocess').run(
            ['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
            text=True, check=True).stdout.strip()
        commands = {
            'authorization_receipt': ['python3', 'code/tests/python/test_gs117_readback_receipt.py'],
            'console': ['python3', 'code/tests/python/test_gs117_tc001_console.py'],
            'framework': ['make', '-C', 'code', 'validation-framework-test'],
            'feature_coverage': ['make', '-C', 'code', 'feature-coverage-test'],
        }
        tests = [{'name': name, 'command': command, 'returncode': 0, 'test_count': 1,
                  'skipped_count': 0, 'stdout_sha256': 'a' * 64, 'stderr_sha256': 'b' * 64}
                 for name, command in commands.items()]
        evidence_path = self.root / 'source-review-tests.json'
        evidence_path.write_text(json.dumps({
            'schema_version': 1, 'reviewed_commit': head,
            'source_fingerprints': {name: auth.digest(path)
                                    for name, path in auth.GS117_SCOPE_SOURCE_PATHS.items()},
            'reviewed_negative_tests': sorted(auth.GS117_SCOPE_ISSUANCE_REVIEW_TESTS),
            'tests': tests,
        }, sort_keys=True))
        evidence_path.chmod(0o600)
        review = {
            'reviewed_commit': head, 'reviewer': auth.GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID,
            'source_fingerprints': {name: auth.digest(path)
                                    for name, path in auth.GS117_SCOPE_SOURCE_PATHS.items()},
            'reviewed_negative_tests': sorted(auth.GS117_SCOPE_ISSUANCE_REVIEW_TESTS),
            'test_evidence_path': str(evidence_path),
            'test_evidence_sha256': auth.digest(evidence_path),
        }
        commands = [
            SimpleNamespace(returncode=0, stdout=str(root) + '\n'),
            SimpleNamespace(returncode=0, stdout='feature/r1-commercial-baseline\n'),
            SimpleNamespace(returncode=0, stdout=head + '\n'),
            SimpleNamespace(returncode=0, stdout=''),
        ]
        with patch.object(auth.subprocess, 'run', side_effect=commands):
            verified = auth._verify_gs117_scope_source_review(review)
        self.assertEqual(verified['reviewed_commit'], head)
        self.assertEqual(verified['validation_summary'], {
            'gs117_focused': 'PASS', 'framework': 'PASS', 'feature_coverage': 'PASS'})
        untrusted_reviewer = dict(review, reviewer='unverified-reviewer')
        with self.assertRaisesRegex(ValueError, 'scope_source_review_invalid'):
            auth._verify_gs117_scope_source_review(untrusted_reviewer)
        stale = dict(review, source_fingerprints=dict(review['source_fingerprints']))
        stale['source_fingerprints']['controller'] = '0' * 64
        with patch.object(auth.subprocess, 'run', side_effect=commands), \
             self.assertRaisesRegex(ValueError, 'source_fingerprint_stale'):
            auth._verify_gs117_scope_source_review(stale)
        malformed_evidence = json.loads(evidence_path.read_text())
        malformed_evidence['tests'][0]['command'] = ['python3', 'arbitrary-test.py']
        evidence_path.write_text(json.dumps(malformed_evidence, sort_keys=True))
        evidence_path.chmod(0o600)
        review['test_evidence_sha256'] = auth.digest(evidence_path)
        with patch.object(auth.subprocess, 'run', side_effect=commands), \
             self.assertRaisesRegex(ValueError, 'test_evidence_incomplete'):
            auth._verify_gs117_scope_source_review(review)
        malformed_evidence['tests'][0]['command'] = [
            'python3', 'code/tests/python/test_gs117_readback_receipt.py']
        malformed_evidence['tests'][0]['skipped_count'] = 1
        evidence_path.write_text(json.dumps(malformed_evidence, sort_keys=True))
        evidence_path.chmod(0o600)
        review['test_evidence_sha256'] = auth.digest(evidence_path)
        with patch.object(auth.subprocess, 'run', side_effect=commands), \
             self.assertRaisesRegex(ValueError, 'test_evidence_incomplete'):
            auth._verify_gs117_scope_source_review(review)

    def test_unknown_scope_and_stale_source_review_are_rejected_before_issue(self):
        with self.assertRaisesRegex(ValueError, 'operation_not_allowlisted'):
            auth.issue_gs117_scope_grant('flash', self.approval_evidence, {})
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             patch.object(auth, '_verify_gs117_scope_source_review',
                          side_effect=ValueError('gs117_scope_source_fingerprint_stale')):
            with self.assertRaisesRegex(ValueError, 'source_fingerprint_stale'):
                auth.issue_gs117_scope_grant('readback_receipt', self.approval_evidence,
                                             self.review, tool_files=self.receipt_tools,
                                             tool_versions=self.versions)
        self.assertFalse(self.issue_state.exists())

    def test_readback_grant_issuance_is_pending_until_separate_activation(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            issued = auth.issue_gs117_scope_grant(
                'readback_receipt', self.approval_evidence, self.review,
                tool_files=self.receipt_tools, tool_versions=self.versions)
        self.assertEqual(issued['status'], 'ISSUED_PENDING_ACTIVATION')
        self.assertFalse(self.readback_policy.exists())
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            active = auth.activate_gs117_scope_grant(
                issued['authorization_id'], self.approval_evidence, self.review)
        self.assertEqual(active['status'], 'ACTIVE')
        self.assertEqual(active['operation'], 'readback_receipt')
        with patch.object(auth, '_readback_receipt_tool_hashes',
                          return_value={name: 'd' * 64 for name in auth.READBACK_RECEIPT_TOOL_NAMES}):
            policy = auth.load_readback_receipt_authorization()
        self.assertEqual(policy['authorization_id'], issued['authorization_id'])
        self.assertEqual(policy['read_ranges'], auth.READBACK_RECEIPT_RANGES)
        self.assertEqual(policy['reset_budget'], auth.READBACK_RECEIPT_RESET_BUDGET)

    def test_scope_a_issuance_is_exactly_the_approved_fixture_ranges_and_resets(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            issued = auth.issue_gs117_scope_grant(
                'readback_receipt', self.approval_evidence, self.review,
                tool_files=self.receipt_tools, tool_versions=self.versions)
        pending = next(self.issue_state.glob('readback_receipt-*.pending.json'))
        record = json.loads(pending.read_text())
        self.assertEqual(record['authorization_id'], issued['authorization_id'])
        self.assertEqual(record['scope']['fixture'], auth.READBACK_RECEIPT_FIXTURE)
        self.assertEqual(record['scope']['read_ranges'], auth.READBACK_RECEIPT_RANGES)
        self.assertEqual(record['scope']['reset_budget'], auth.READBACK_RECEIPT_RESET_BUDGET)
        self.assertEqual(record['max_uses'], 1)
        self.assertIs(record['renewable'], False)

    def test_issuance_rejects_unverified_approval_without_creating_state(self):
        with self.assertRaisesRegex(ValueError, 'owner_scope_approval_not_verified'):
            auth.issue_gs117_scope_grant(
                'readback_receipt', {}, self.review,
                tool_files=self.receipt_tools, tool_versions=self.versions)
        self.assertFalse(self.issue_state.exists())

    def test_private_policy_writer_rejects_group_or_world_accessible_parent(self):
        unsafe = self.root / 'unsafe'
        unsafe.mkdir(mode=0o700)
        unsafe.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'parent_not_private'):
            auth._write_private_json_exclusive(unsafe / 'grant.json', {'active': False})
        self.assertFalse((unsafe / 'grant.json').exists())

    def test_duplicate_issuance_activation_and_scope_replay_are_rejected(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            issued = auth.issue_gs117_scope_grant(
                'readback_receipt', self.approval_evidence, self.review,
                tool_files=self.receipt_tools, tool_versions=self.versions)
            with self.assertRaisesRegex(ValueError, 'already_issued|already_pending'):
                auth.issue_gs117_scope_grant(
                    'readback_receipt', self.approval_evidence, self.review,
                    tool_files=self.receipt_tools, tool_versions=self.versions)
            auth.activate_gs117_scope_grant(issued['authorization_id'],
                                            self.approval_evidence, self.review)
            with self.assertRaisesRegex(ValueError, 'already_activated'):
                auth.activate_gs117_scope_grant(issued['authorization_id'],
                                                self.approval_evidence, self.review)

    def test_readback_wrong_tool_versions_and_incomplete_scope_fail_closed(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            with self.assertRaisesRegex(ValueError, 'tool_version_mismatch'):
                auth.issue_gs117_scope_grant(
                    'readback_receipt', self.approval_evidence, self.review,
                    tool_files=self.receipt_tools,
                    tool_versions={**self.versions, 'esptool': 'other'})
            with self.assertRaisesRegex(ValueError, 'reviewed_tool_inventory_required'):
                auth.issue_gs117_scope_grant(
                    'readback_receipt', self.approval_evidence, self.review,
                    tool_files=None, tool_versions=self.versions)
        self.assertFalse(self.readback_policy.exists())

    def test_motion_grant_cannot_be_issued_before_scope_a_pass(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             patch.object(auth, '_verify_scope_a_readback_pass',
                          side_effect=ValueError('motion_event_once_scope_a_receipt_pass_required')):
            with self.assertRaisesRegex(ValueError, 'scope_a_receipt_pass_required'):
                auth.issue_gs117_scope_grant(
                    'motion_event_once', self.approval_evidence, self.review,
                    tool_files=self.motion_tools)
        self.assertFalse(self.motion_policy.exists())
        self.assertFalse(self.issue_state.exists())

    def test_motion_grant_is_isolated_one_use_and_revocable(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             patch.object(auth, '_verify_scope_a_readback_pass', return_value=self.scope_a_receipt):
            issued = auth.issue_gs117_scope_grant(
                'motion_event_once', self.approval_evidence, self.review,
                tool_files=self.motion_tools)
            self.assertFalse(self.motion_policy.exists())
            activated = auth.activate_gs117_scope_grant(
                issued['authorization_id'], self.approval_evidence, self.review)
        self.assertEqual(activated['status'], 'ACTIVE')
        with patch.object(auth, '_verify_gs117_scope_source_review', return_value=self.review), \
             patch.object(auth, '_motion_event_tool_hashes',
                          return_value={name: 'e' * 64 for name in auth.MOTION_EVENT_ONCE_TOOLS}), \
             patch.object(auth, '_verify_scope_a_readback_pass', return_value=self.scope_a_receipt):
            policy = auth.load_development(self.motion_policy)
            self.assertEqual(policy['procedures'], ['motion_event_once'])
            self.assertEqual(policy['allowed_operations'], ['motion_event_once'])
            self.assertEqual(policy['max_sessions'], 1)
            self.assertEqual(auth.motion_event_once_status()['status'], 'ACTIVE')
            with auth.motion_event_once_session() as (_active, reservation):
                reservation['functional_outcome'] = 'PASS'
            self.assertEqual(auth.motion_event_once_status()['status'], 'CONSUMED')
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                auth.revoke_motion_event_once_authorization('after consumption')

    def test_scope_issuance_audit_corruption_blocks_activation(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            issued = auth.issue_gs117_scope_grant(
                'readback_receipt', self.approval_evidence, self.review,
                tool_files=self.receipt_tools, tool_versions=self.versions)
        audit = self.issue_state / 'issuance.jsonl'
        audit.write_text(audit.read_text() + '{corrupt\n')
        audit.chmod(0o600)
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             self.assertRaisesRegex(ValueError, 'audit_corrupt'):
            auth.activate_gs117_scope_grant(issued['authorization_id'],
                                            self.approval_evidence, self.review)
        self.assertFalse(self.readback_policy.exists())

    def test_interrupted_pending_issuance_without_audit_cannot_activate(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval):
            issued = auth.issue_gs117_scope_grant(
                'readback_receipt', self.approval_evidence, self.review,
                tool_files=self.receipt_tools, tool_versions=self.versions)
        audit = self.issue_state / 'issuance.jsonl'
        audit.unlink()
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             self.assertRaisesRegex(ValueError, 'grant_issue_missing'):
            auth.activate_gs117_scope_grant(issued['authorization_id'],
                                            self.approval_evidence, self.review)
        self.assertFalse(self.readback_policy.exists())

    def test_scope_b_activation_rejects_changed_scope_a_receipt(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             patch.object(auth, '_verify_scope_a_readback_pass', return_value=self.scope_a_receipt):
            issued = auth.issue_gs117_scope_grant(
                'motion_event_once', self.approval_evidence, self.review,
                tool_files=self.motion_tools)
        changed = dict(self.scope_a_receipt, evidence_sha256='0' * 64)
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             patch.object(auth, '_verify_scope_a_readback_pass', return_value=changed), \
             self.assertRaisesRegex(ValueError, 'scope_a_receipt_changed'):
            auth.activate_gs117_scope_grant(issued['authorization_id'],
                                            self.approval_evidence, self.review)
        self.assertFalse(self.motion_policy.exists())

    def test_unconsumed_motion_grant_can_be_revoked_without_touching_hardware_state(self):
        with patch.object(auth, '_verify_gs117_11933_approval', return_value=self.approval), \
             patch.object(auth, '_verify_scope_a_readback_pass', return_value=self.scope_a_receipt):
            issued = auth.issue_gs117_scope_grant(
                'motion_event_once', self.approval_evidence, self.review,
                tool_files=self.motion_tools)
            auth.activate_gs117_scope_grant(
                issued['authorization_id'], self.approval_evidence, self.review)
        with patch.object(auth, '_verify_gs117_scope_source_review', return_value=self.review), \
             patch.object(auth, '_motion_event_tool_hashes',
                          return_value={name: 'e' * 64 for name in auth.MOTION_EVENT_ONCE_TOOLS}), \
             patch.object(auth, '_verify_scope_a_readback_pass', return_value=self.scope_a_receipt):
            result = auth.revoke_motion_event_once_authorization('owner revoked before use')
            self.assertEqual(result['status'], 'REVOKED')
            self.assertEqual(auth.motion_event_once_status()['status'], 'REVOKED')
        self.assertEqual(self.historical_latch.read_bytes(), self.historical_latch_bytes)
        self.assertEqual(self.historical_latch.stat().st_mode & 0o777, 0o600)
        self.assertEqual({path.name for path in self.hardware_state.iterdir()},
                         {'session.lock', 'historical-latch.json'})


if __name__ == "__main__":
    unittest.main()
