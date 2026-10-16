#!/usr/bin/env python3
"""Build the isolated GS-68 ESP32-C3 read-only observer image; never flashes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
IDF_DIR = REPO / "code/firmware/node/target/esp32c3/idf"
IDF_EXPORT = Path("/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh")
BASE_PROFILE = IDF_DIR / "sdkconfig.defaults"
OBSERVER_PROFILE = IDF_DIR / "sdkconfig.gs68_node_observer.defaults"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run(*args: str) -> str:
    return subprocess.run(args, cwd=REPO, text=True, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()


def main() -> int:
    if not IDF_EXPORT.is_file():
        print("BLOCKED: required ESP-IDF 6.0.3 export.sh is unavailable")
        return 2
    if not BASE_PROFILE.is_file() or not OBSERVER_PROFILE.is_file():
        print("BLOCKED: C3 observer profile inputs are missing")
        return 2
    branch = run("git", "branch", "--show-current")
    source_commit = run("git", "rev-parse", "HEAD")
    source_code_tree_oid = run("git", "rev-parse", f"{source_commit}:code")
    source_status = run("git", "status", "--porcelain=v1", "--untracked-files=normal", "--", "code").splitlines()
    allowed_untracked = {"?? code/firmware/hub/target/esp32s3/idf/managed_components/"}
    unexpected = [line for line in source_status if line not in allowed_untracked]
    if unexpected:
        print("BLOCKED: source changes must be committed before source-bound C3 image build")
        for line in unexpected:
            print(line)
        return 2
    if branch != "feature/r1-gs68-gs109-mtls-feasibility":
        print(f"BLOCKED: unexpected branch {branch}")
        return 2

    profile_material = (b"sdkconfig.defaults\0" + BASE_PROFILE.read_bytes() +
                        b"\0sdkconfig.gs68_node_observer.defaults\0" + OBSERVER_PROFILE.read_bytes())
    profile_sha = sha256_bytes(profile_material)
    requested_root = os.environ.get("GS68_C3_DIAGNOSTIC_BUILD_ROOT")
    if requested_root:
        root = Path(requested_root).resolve()
        if root.parent != Path("/tmp") or not root.name.startswith("gs68_cloudsync_c3_"):
            print("BLOCKED: build root must be a dedicated gs68_cloudsync_c3_* directory under /tmp")
            return 2
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    else:
        root = Path(tempfile.mkdtemp(prefix="gs68_cloudsync_c3_", dir="/tmp"))
    build_dir = root / "build"
    sdkconfig = root / "sdkconfig"
    defaults = ";".join(("sdkconfig.defaults", "sdkconfig.gs68_node_observer.defaults"))
    command = ["idf.py", "-C", str(IDF_DIR), "-B", str(build_dir),
        "-D", f"SDKCONFIG={sdkconfig}", "-D", "IDF_TARGET=esp32c3",
        "-D", f"SDKCONFIG_DEFAULTS={defaults}",
        "-D", "GS_GS68_NODE_OBSERVER=ON", "-D", "GS_HIL_BUILD=OFF",
        "-D", "GS_HIL_CONTROL=OFF", "-D", "GS_BAT_C8_PHYSICAL_WAKE=OFF",
        "-D", f"GS68_NODE_SOURCE_COMMIT={source_commit}",
        "-D", f"GS68_NODE_PROFILE_SHA256={profile_sha}", "build", "size"]
    shell = "source " + shlex.quote(str(IDF_EXPORT)) + " >/dev/null && exec " + " ".join(map(shlex.quote, command))
    print(f"BUILD_DIR={build_dir}")
    print(f"SOURCE_COMMIT={source_commit}")
    print(f"PROFILE_SHA256={profile_sha}")
    result = subprocess.run(["bash", "-lc", shell], cwd=REPO,
        env=dict(os.environ, CMAKE_BUILD_PARALLEL_LEVEL="2"), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    build_log = root / "build.log"
    build_log.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        print("\n".join(result.stdout.splitlines()[-140:]))
        print(f"BUILD_LOG={build_log}")
        print(f"GS68_C3_DIAGNOSTIC_BUILD=FAIL exit={result.returncode}")
        return result.returncode or 1

    config = sdkconfig.read_text(encoding="utf-8")
    if "CONFIG_IDF_TARGET=\"esp32c3\"" not in config:
        print("GS68_C3_DIAGNOSTIC_BUILD=FAIL sdkconfig target is not ESP32-C3")
        return 1
    if "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y" not in config:
        print("GS68_C3_DIAGNOSTIC_BUILD=FAIL USB serial observation console is disabled")
        return 1
    image = build_dir / "gs_hw_m1_node.bin"
    if not image.is_file():
        print("GS68_C3_DIAGNOSTIC_BUILD=FAIL expected standalone image is missing")
        return 1
    report = {
        "schema_version": 1, "status": "BUILD_ONLY_PASS", "physical": "NOT_RUN",
        "hardware_actions": [], "target": "ESP32-C3", "profile_id": "GS68_C3_READ_ONLY_OBSERVER",
        "source_branch": branch, "source_commit": source_commit,
        "source_code_tree_oid": source_code_tree_oid,
        "profile_sha256": profile_sha, "profile_inputs": {
            "sdkconfig.defaults_sha256": sha256_file(BASE_PROFILE),
            "sdkconfig.gs68_node_observer.defaults_sha256": sha256_file(OBSERVER_PROFILE)},
        "sdkconfig_sha256": sha256_file(sdkconfig),
        "build_configuration": {"idf_target": "esp32c3", "gs_gs68_node_observer": True,
            "gs_hil_build": False, "gs_hil_control": False,
            "gs_bat_c8_physical_wake": False, "sdkconfig_defaults": defaults},
        "image_path": str(image), "image_sha256": sha256_file(image),
        "image_bytes": image.stat().st_size, "build_directory": str(build_dir),
        "build_log": str(build_log), "idf_version": "v6.0.3",
        "flash_or_serial_used": False,
        "limitations": ["No board was connected, flashed, reset, or observed.",
            "Compilation does not prove runtime observation, EventKey correlation, or physical qualification."],
    }
    report_path = root / "gs68_c3_build_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"BUILD_REPORT={report_path}")
    print(f"BUILD_LOG={build_log}")
    print(f"IMAGE_SHA256={report['image_sha256']}")
    print(f"IMAGE_BYTES={report['image_bytes']}")
    print("GS68_C3_DIAGNOSTIC_BUILD=PASS hardware_actions=0 physical=NOT_RUN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
