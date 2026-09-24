#!/usr/bin/env python3
"""Build and validate one provenance-safe ESP32 Hub+C3 firmware pair.

This is the qualification path.  It deliberately refuses a tracked dirty
tree, rebuilds both ESP-IDF projects from fresh generated directories, owns
the C3-to-Hub synchronization, and emits one machine-readable manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
NODE_PROJECT = ROOT / "firmware/node/target/esp32c3/idf"
HUB_PROJECT = ROOT / "firmware/hub/target/esp32/idf"
NODE_BINARY = NODE_PROJECT / "build/gs_hw_m1_node.bin"
HUB_EMBEDDED_NODE = HUB_PROJECT / "main/node_firmware.bin"
HUB_BINARY = HUB_PROJECT / "build/gs_hw_m1_hub.bin"
HUB_EMBEDDED_ASM = HUB_PROJECT / (
    "build/esp-idf/main/CMakeFiles/__idf_main.dir/__/__/node_firmware.bin.S.obj")
MANIFEST = ROOT / "build/hw_pair/provenance.json"
RUNTIME_IMPLEMENTATION_COMMIT = "cfcee972dab6045bbb8f7fbfeb51bf66097cfae9"
RUNTIME_IMPLEMENTATION_SHORT = "cfcee97"
SCHEMA_VERSION = 1
HIL_MARKERS = (b"HIL_READY", b"INJECT_MOTION", b"SET_HUB_LOGICAL_OFFLINE",
               b"START_C3_FOTA", b"HIL_TEST_QR", b"HIL_TEST_CODE", b"HIL_TEST_IDENTITY",
               b"GET_TEST_QR", b"GET_TEST_IDENTITY")


class PairBuildError(RuntimeError):
    """A fail-closed pair-build validation error."""


@dataclass(frozen=True)
class ImageMetadata:
    version: str
    idf_version: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_record(path: Path, metadata: ImageMetadata) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise PairBuildError(f"missing or empty image: {path}")
    try:
        display_path = str(path.relative_to(ROOT))
    except ValueError:
        display_path = str(path)
    return {"path": display_path, "app_version": metadata.version,
            "idf_version": metadata.idf_version, "size": path.stat().st_size,
            "sha256": sha256(path)}


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise PairBuildError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def git_state() -> dict[str, object]:
    # Ignored ESP-IDF/generated output is intentionally absent; source/tooling
    # untracked files must still fail closed before qualification.
    status = run_git("status", "--porcelain")
    return {"branch": run_git("branch", "--show-current"),
            "commit_full": run_git("rev-parse", "HEAD"),
            "commit_short": run_git("rev-parse", "--short=7", "HEAD"),
            "dirty": bool(status)}


def require_clean_tree(state: dict[str, object]) -> None:
    if state["dirty"]:
        raise PairBuildError("tracked working tree is dirty; qualification requires a clean commit")


def parse_image_info(output: str) -> ImageMetadata:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    version = fields.get("app version")
    idf_version = fields.get("esp-idf")
    if not version or not idf_version:
        raise PairBuildError("esptool image-info did not report App version and ESP-IDF")
    return ImageMetadata(version, idf_version)


def validate_version(metadata: ImageMetadata, expected_short: str, label: str) -> None:
    if metadata.version != expected_short:
        raise PairBuildError(f"{label} app version {metadata.version!r} != {expected_short!r}")
    if "-dirty" in metadata.version:
        raise PairBuildError(f"{label} app version contains -dirty")


def activation_script() -> Path:
    candidate = Path(os.environ.get(
        "HW_IDF_ACTIVATE", str(Path.home() / ".espressif/tools/activate_idf_v6.0.3.sh")))
    if not candidate.is_file():
        raise PairBuildError(f"ESP-IDF activation script not found: {candidate}")
    return candidate


def run_idf(project: Path, target: str, name: str, activation: Path) -> str:
    command = ["bash", "-lc", f"source {shlex_quote(str(activation))}; "
               f"idf.py set-target {target} && idf.py build"]
    log_dir = ROOT / "build/hw_pair"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(command, cwd=project, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=1800, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        (log_dir / f"{name}.log").write_text(str(exc) + "\n")
        raise PairBuildError(f"{name} failed: {exc}") from exc
    output = result.stdout or ""
    (log_dir / f"{name}.log").write_text(output)
    if result.returncode:
        raise PairBuildError(f"{name} failed; see {log_dir / (name + '.log')}")
    return output


def shlex_quote(value: str) -> str:
    # Keep this script stdlib-only while avoiding shell interpolation in source paths.
    return "'" + value.replace("'", "'\\''") + "'"


def run_esptool(path: Path, activation: Path) -> ImageMetadata:
    command = ["bash", "-lc", f"source {shlex_quote(str(activation))}; "
               f"esptool image-info {shlex_quote(str(path))}"]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        raise PairBuildError(f"esptool image-info failed for {path}: {result.stdout}")
    return parse_image_info(result.stdout)


def fresh_build_directory(project: Path) -> None:
    build = project / "build"
    if build.exists():
        shutil.rmtree(build)


def synchronize_node_image(source: Path = NODE_BINARY,
                           destination: Path = HUB_EMBEDDED_NODE) -> dict[str, object]:
    if not source.is_file() or source.stat().st_size == 0:
        raise PairBuildError(f"C3 artifact missing or empty: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_hash = sha256(source)
    destination_hash = sha256(destination)
    if source_hash != destination_hash or source.read_bytes() != destination.read_bytes():
        raise PairBuildError("C3/Hub embedding synchronization is not byte-identical")
    return {"source_sha256": source_hash, "destination_sha256": destination_hash,
            "destination_mtime_ns": destination.stat().st_mtime_ns,
            "size": destination.stat().st_size}


def require_rebuilt(path: Path, synchronized_mtime_ns: int, label: str) -> None:
    if not path.is_file() or path.stat().st_mtime_ns < synchronized_mtime_ns:
        raise PairBuildError(f"{label} was not rebuilt after node synchronization: {path}")


def validate_pair(c3: dict[str, object], embedded: dict[str, object], hub: dict[str, object],
                  expected_short: str) -> dict[str, bool | str]:
    checks = {
        "clean_tree": True,
        "c3_version_match": c3["app_version"] == expected_short,
        "embedded_version_match": embedded["app_version"] == expected_short,
        "hub_version_match": hub["app_version"] == expected_short,
        "standalone_equals_embedded": c3["sha256"] == embedded["sha256"] and c3["size"] == embedded["size"],
        "standalone_embedded_sha_match": c3["sha256"] == embedded["sha256"],
        "no_dirty_versions": all("-dirty" not in str(record["app_version"])
                                  for record in (c3, embedded, hub)),
    }
    if not all(bool(value) for value in checks.values()):
        raise PairBuildError("pair validation failed: " + ", ".join(k for k, v in checks.items() if not v))
    checks["pair_validation"] = "PASS"
    return checks


def require_production_isolation(*images: Path) -> None:
    for image in images:
        data = image.read_bytes()
        present = [marker.decode() for marker in HIL_MARKERS if marker in data]
        if present:
            raise PairBuildError(f"production image exposes HIL control markers {present}: {image}")


def write_manifest(state: dict[str, object], c3: dict[str, object], embedded: dict[str, object],
                   hub: dict[str, object], verification: dict[str, object]) -> Path:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "branch": state["branch"],
        "git_commit_full": state["commit_full"],
        "git_commit_short": state["commit_short"],
        "qualification_artifact_commit_full": state["commit_full"],
        "qualification_artifact_commit_short": state["commit_short"],
        "git_dirty": False,
        "runtime_implementation_commit_full": RUNTIME_IMPLEMENTATION_COMMIT,
        "runtime_implementation_commit_short": RUNTIME_IMPLEMENTATION_SHORT,
        "runtime_delta_after_cfcee97": False,
        "idf_version": c3["idf_version"],
        "c3": c3,
        "hub_embedding_input": embedded,
        "hub": hub,
        "verification": verification,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return MANIFEST


def build_pair() -> int:
    state = git_state()
    require_clean_tree(state)
    expected_short = str(state["commit_short"])
    activation = activation_script()
    fresh_build_directory(NODE_PROJECT)
    fresh_build_directory(HUB_PROJECT)
    run_idf(NODE_PROJECT, "esp32c3", "c3-build", activation)
    c3_meta = run_esptool(NODE_BINARY, activation)
    validate_version(c3_meta, expected_short, "C3")
    c3 = image_record(NODE_BINARY, c3_meta)
    sync = synchronize_node_image()
    embedded_meta = run_esptool(HUB_EMBEDDED_NODE, activation)
    validate_version(embedded_meta, expected_short, "embedded C3")
    embedded = image_record(HUB_EMBEDDED_NODE, embedded_meta)
    if c3["sha256"] != embedded["sha256"]:
        raise PairBuildError("standalone C3 and Hub embedding input SHA differ")
    run_idf(HUB_PROJECT, "esp32", "hub-build", activation)
    require_rebuilt(HUB_EMBEDDED_ASM, int(sync["destination_mtime_ns"]), "Hub embedded object")
    require_rebuilt(HUB_BINARY, int(sync["destination_mtime_ns"]), "Hub image")
    hub_meta = run_esptool(HUB_BINARY, activation)
    validate_version(hub_meta, expected_short, "Hub")
    hub = image_record(HUB_BINARY, hub_meta)
    require_production_isolation(NODE_BINARY, HUB_BINARY)
    verification = validate_pair(c3, embedded, hub, expected_short)
    verification["production_hil_control_absent"] = True
    manifest = write_manifest(state, c3, embedded, hub, verification)
    print("HW PAIR BUILD: PASS")
    print(f"Runtime implementation: {RUNTIME_IMPLEMENTATION_SHORT}")
    print(f"Qualification artifact: {state['commit_short']}")
    print(f"Git: branch={state['branch']} commit={state['commit_short']} clean=YES")
    print(f"C3: version={c3['app_version']} size={c3['size']} sha256={c3['sha256']}")
    print(f"Embedded C3: version={embedded['app_version']} size={embedded['size']} sha256={embedded['sha256']}")
    print("C3 / EMBEDDED MATCH: PASS")
    print(f"Hub: version={hub['app_version']} size={hub['size']} sha256={hub['sha256']}")
    print("NO DIRTY VERSION: PASS")
    print("PAIR VALIDATION: PASS")
    print(f"Manifest: {manifest}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        return build_pair()
    except PairBuildError as exc:
        print(f"HW PAIR BUILD: FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
