#!/usr/bin/env python3
"""Build the paired target images with the compile-time HIL control plane."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build_hw_pair import (HUB_BINARY, HUB_EMBEDDED_ASM, HUB_EMBEDDED_NODE,
                           HUB_PROJECT, MANIFEST, NODE_BINARY, NODE_PROJECT,
                           PairBuildError, activation_script, image_record,
                           parse_image_info, require_rebuilt, run_esptool, sha256,
                           shlex_quote, synchronize_node_image, validate_pair)

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def fingerprint() -> str:
    sys.path.insert(0, str(ROOT))
    from tools.hil.core import source_fingerprint
    return source_fingerprint()


def build(project: Path, target: str, label: str, version: str, activation: Path):
    build_dir = project / "build"
    if build_dir.exists(): shutil.rmtree(build_dir)
    config_args = ""
    if target == "esp32c3":
        hil_sdkconfig = project / "sdkconfig.hil"
        if hil_sdkconfig.exists(): hil_sdkconfig.unlink()
        config_args = ("-DSDKCONFIG=sdkconfig.hil "
                       "-DSDKCONFIG_DEFAULTS='sdkconfig.defaults;sdkconfig.hil.defaults' ")
    command = (f"source {shlex_quote(str(activation))}; "
               f"idf.py {config_args}-DGS_HIL_BUILD=ON -DPROJECT_VER={shlex_quote(version)} "
               f"set-target {target} build")
    cp = subprocess.run(["bash", "-lc", command], cwd=project, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800,
                        env={**os.environ, "PYTHONUNBUFFERED": "1"})
    log = ROOT / "build/hw_pair" / f"{label}.log"
    log.parent.mkdir(parents=True, exist_ok=True); log.write_text(cp.stdout or "")
    if cp.returncode: raise PairBuildError(f"{label} failed; see {log}")


def main() -> int:
    try:
        commit = git("rev-parse", "HEAD")
        short = git("rev-parse", "--short=7", "HEAD")
        branch = git("branch", "--show-current")
        dirty = bool(git("status", "--porcelain"))
        source_sha = fingerprint()
        version = f"{short}-hil-{source_sha[:7]}"
        activation = activation_script()
        build(NODE_PROJECT, "esp32c3", "c3-hil-build", version, activation)
        c3_meta = run_esptool(NODE_BINARY, activation)
        if c3_meta.version != version or "-dirty" in c3_meta.version:
            raise PairBuildError(f"C3 HIL version mismatch: {c3_meta.version} != {version}")
        c3 = image_record(NODE_BINARY, c3_meta)
        sync = synchronize_node_image()
        embedded = image_record(HUB_EMBEDDED_NODE, run_esptool(HUB_EMBEDDED_NODE, activation))
        build(HUB_PROJECT, "esp32", "hub-hil-build", version, activation)
        require_rebuilt(HUB_EMBEDDED_ASM, int(sync["destination_mtime_ns"]), "Hub embedded object")
        hub_meta = run_esptool(HUB_BINARY, activation)
        if hub_meta.version != version or "-dirty" in hub_meta.version:
            raise PairBuildError(f"Hub HIL version mismatch: {hub_meta.version} != {version}")
        hub = image_record(HUB_BINARY, hub_meta)
        c3_bytes, hub_bytes = NODE_BINARY.read_bytes(), HUB_BINARY.read_bytes()
        if b"HIL_READY" not in c3_bytes or b"INJECT_MOTION" not in c3_bytes:
            raise PairBuildError("C3 HIL control markers missing from HIL image")
        if b"HIL_READY" not in hub_bytes or b"SET_HUB_LOGICAL_OFFLINE" not in hub_bytes:
            raise PairBuildError("Hub HIL control markers missing from HIL image")
        verification = validate_pair(c3, embedded, hub, version)
        verification["clean_tree"] = not dirty
        verification["source_fingerprint_match"] = True
        verification["hil_control_present"] = True
        manifest = {"schema_version": 2, "kind": "HIL_PHASE1", "branch": branch,
                    "git_commit_full": commit, "git_commit_short": short,
                    "git_dirty": dirty, "source_fingerprint": source_sha,
                    "image_version": version, "hil_control": True,
                    "qualification_release_image": False, "idf_version": c3_meta.idf_version,
                    "c3": c3, "hub_embedding_input": embedded, "hub": hub,
                    "verification": verification}
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"HIL PAIR BUILD: PASS version={version}")
        print(f"C3 / EMBEDDED MATCH: {c3['sha256'] == embedded['sha256']}")
        return 0
    except (PairBuildError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"HIL PAIR BUILD: FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__": raise SystemExit(main())
