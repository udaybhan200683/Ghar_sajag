from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.build_hw_pair as pair
from scripts.build_hw_pair import (
    ImageMetadata,
    PairBuildError,
    RUNTIME_IMPLEMENTATION_COMMIT,
    RUNTIME_IMPLEMENTATION_SHORT,
    image_record,
    parse_image_info,
    require_clean_tree,
    require_rebuilt,
    synchronize_node_image,
    validate_pair,
    validate_version,
    write_manifest,
)


class HwPairBuildTest(unittest.TestCase):
    def test_image_info_parser_and_dirty_version_rejection(self):
        metadata = parse_image_info("App version: abc1234\nESP-IDF: v6.0.3\n")
        self.assertEqual(metadata, ImageMetadata("abc1234", "v6.0.3"))
        validate_version(metadata, "abc1234", "C3")
        with self.assertRaises(PairBuildError):
            validate_version(ImageMetadata("abc1234-dirty", "v6.0.3"), "abc1234-dirty", "C3")

    def test_stale_embedding_is_replaced_byte_identically_and_sha_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "node.bin"
            destination = root / "hub/node_firmware.bin"
            source.write_bytes(b"new-c3-image")
            destination.parent.mkdir()
            destination.write_bytes(b"7c08bdd-dirty-stale")
            result = synchronize_node_image(source, destination)
            self.assertEqual(source.read_bytes(), destination.read_bytes())
            self.assertEqual(result["source_sha256"], result["destination_sha256"])
            self.assertEqual(result["size"], len(b"new-c3-image"))

    def test_missing_source_and_mismatched_pair_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(PairBuildError):
                synchronize_node_image(root / "missing.bin", root / "embed.bin")
            c3 = {"app_version": "abc1234", "size": 3, "sha256": "aaa", "idf_version": "v6.0.3"}
            embedded = {**c3, "sha256": "bbb"}
            hub = {**c3}
            with self.assertRaises(PairBuildError):
                validate_pair(c3, embedded, hub, "abc1234")

    def test_clean_pair_and_manifest_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c3_path = root / "c3.bin"
            c3_path.write_bytes(b"c3")
            expected_hash = hashlib.sha256(b"c3").hexdigest()
            metadata = ImageMetadata("abc1234", "v6.0.3")
            c3 = image_record(c3_path, metadata)
            embedded = {**c3, "path": "hub/node_firmware.bin"}
            hub = {**c3, "path": "hub.bin"}
            checks = validate_pair(c3, embedded, hub, "abc1234")
            self.assertEqual(checks["pair_validation"], "PASS")
            self.assertEqual(c3["sha256"], expected_hash)

            with mock.patch.object(pair, "MANIFEST", root / "manifest.json"):
                manifest_path = write_manifest(
                    {"branch": "fix/test", "commit_full": "abc123456789", "commit_short": "abc1234"},
                    c3, embedded, hub, checks)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["qualification_artifact_commit_short"], "abc1234")
            self.assertEqual(manifest["runtime_implementation_commit_short"], "cfcee97")
            self.assertFalse(manifest["runtime_delta_after_cfcee97"])
            self.assertEqual(manifest["c3"]["sha256"], expected_hash)

    def test_dirty_tree_is_rejected(self):
        with self.assertRaises(PairBuildError):
            require_clean_tree({"dirty": True})
        require_clean_tree({"dirty": False})

    def test_rebuild_marker_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.S"
            path.write_bytes(b"generated")
            with self.assertRaises(PairBuildError):
                require_rebuilt(path, path.stat().st_mtime_ns + 1, "embedded object")
            require_rebuilt(path, path.stat().st_mtime_ns, "embedded object")

    def test_runtime_provenance_is_fixed(self):
        self.assertEqual(RUNTIME_IMPLEMENTATION_COMMIT, "cfcee972dab6045bbb8f7fbfeb51bf66097cfae9")
        self.assertEqual(RUNTIME_IMPLEMENTATION_SHORT, "cfcee97")

    def test_tooling_delta_contains_no_runtime_paths(self):
        changed = subprocess.run(
            ["git", "diff", "--name-only", "cfcee972dab6045bbb8f7fbfeb51bf66097cfae9"],
            cwd=Path(__file__).resolve().parents[2], text=True,
            stdout=subprocess.PIPE, check=True).stdout.splitlines()
        forbidden = ("firmware/node/runtime/", "firmware/node/components/",
                     "firmware/hub/runtime/", "firmware/common/transport/")
        self.assertFalse([path for path in changed if path.startswith(forbidden)])


if __name__ == "__main__":
    unittest.main()
