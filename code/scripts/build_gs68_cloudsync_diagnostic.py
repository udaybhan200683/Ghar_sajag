#!/usr/bin/env python3
"""Build the isolated GS-68 ESP32-S3 diagnostic image; never flashes devices."""
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
IDF_DIR = REPO / "code/firmware/hub/target/esp32s3/idf"
IDF_EXPORT = Path("/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh")
PROFILE = IDF_DIR / "sdkconfig.gs68_cloudsync_hil.defaults"
VALIDATION_BUILD_ROOT = (REPO / "code/build/validation_targets").resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args, cwd=REPO, check=True):
    return subprocess.run(args, cwd=cwd, text=True, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main() -> int:
    if not IDF_EXPORT.is_file():
        print("BLOCKED: required ESP-IDF 6.0.3 export.sh is unavailable")
        return 2
    if not PROFILE.is_file():
        print("BLOCKED: GS-68 DS/TLS test profile is missing")
        return 2
    profile_config = PROFILE.read_text()
    profile_required = (
        "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
        "# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set",
        "# CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG is not set",
        "CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y",
    )
    if any(entry not in profile_config for entry in profile_required):
        print("BLOCKED: GS-68 DS/TLS test profile is missing or incomplete")
        return 2
    branch = run("git", "branch", "--show-current").stdout.strip()
    source_commit = run("git", "rev-parse", "HEAD").stdout.strip()
    source_code_tree_oid = run("git", "rev-parse", f"{source_commit}:code").stdout.strip()
    source_status = run("git", "status", "--porcelain=v1", "--untracked-files=normal", "--", "code").stdout.splitlines()
    # Preserve known, pre-existing user assets in the canonical worktree while
    # still blocking any other uncommitted source input from a source-bound build.
    allowed_untracked = {
        "?? code/firmware/hub/target/esp32s3/idf/managed_components/",
        "?? code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/",
        "?? code/parivar_saathi_android_app/",
    }
    unexpected = [line for line in source_status if line not in allowed_untracked]
    if unexpected:
        print("BLOCKED: tracked or untracked source changes must be committed before source-bound image build")
        for line in unexpected:
            print(line)
        return 2
    if branch != "feature/r1-commercial-baseline":
        print(f"BLOCKED: unexpected branch {branch}")
        return 2
    profile_sha = sha256(PROFILE)
    requested_root = os.environ.get("GS68_DIAGNOSTIC_BUILD_ROOT")
    if requested_root:
        root = Path(requested_root).resolve()
        if (root.parent not in (Path("/tmp"), VALIDATION_BUILD_ROOT) or
                not root.name.startswith("gs68_cloudsync_diag_")):
            print("BLOCKED: reusable build root must be a dedicated gs68_cloudsync_diag_* directory under /tmp or code/build/validation_targets")
            return 2
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    else:
        root = Path(tempfile.mkdtemp(prefix="gs68_cloudsync_diag_", dir="/tmp"))
    build_dir = root / "build"
    sdkconfig = root / "sdkconfig"
    # The generic S3 diagnostic overlay contains an obsolete Kconfig symbol
    # and is not part of this CloudSync-only image. Use only the board's
    # commercial flash/PSRAM baseline plus the isolated GS-68 DS/TLS profile.
    defaults = ";".join(("sdkconfig.defaults", "sdkconfig.gs68_cloudsync_hil.defaults"))
    command = [
        "idf.py", "-C", str(IDF_DIR), "-B", str(build_dir),
        "-D", f"SDKCONFIG={sdkconfig}", "-D", "IDF_TARGET=esp32s3",
        "-D", f"SDKCONFIG_DEFAULTS={defaults}",
        "-D", "GS68_CLOUDSYNC_DIAGNOSTIC_ONLY=ON",
        "-D", f"GS68_SOURCE_COMMIT={source_commit}",
        "-D", f"GS68_PROFILE_SHA256={profile_sha}",
        "-D", "GS_HIL_BUILD=OFF", "-D", "GS_HIL_CONTROL=OFF",
        "-D", "GS_HIL_COMMISSIONING=OFF", "-D", "GS_HIL_C8_ACK_DROP=OFF",
        "build", "size",
    ]
    shell = "source " + shlex.quote(str(IDF_EXPORT)) + " >/dev/null && exec " + " ".join(map(shlex.quote, command))
    print(f"BUILD_DIR={build_dir}")
    print(f"SOURCE_COMMIT={source_commit}")
    print(f"PROFILE_SHA256={profile_sha}")
    build_env = dict(os.environ, CMAKE_BUILD_PARALLEL_LEVEL="2")
    result = subprocess.run(["bash", "-lc", shell], cwd=REPO, env=build_env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    build_log = root / "build.log"
    build_log.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        print("\n".join(result.stdout.splitlines()[-120:]))
        print(f"BUILD_LOG={build_log}")
        print(f"GS68_DIAGNOSTIC_BUILD=FAIL exit={result.returncode}")
        return result.returncode or 1
    config = sdkconfig.read_text(encoding="utf-8")
    required = ("CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y",
                "CONFIG_MBEDTLS_SSL_PROTO_TLS1_2=y",
                "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y")
    if any(entry not in config for entry in required):
        print("GS68_DIAGNOSTIC_BUILD=FAIL sdkconfig omitted a required DS/TLS/USB-console option")
        return 1
    if "CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y" in config:
        print("GS68_DIAGNOSTIC_BUILD=FAIL TLS 1.3 is enabled in a TLS 1.2-only profile")
        return 1
    if ("CONFIG_ESP_CONSOLE_UART_DEFAULT=y" in config or
            "CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y" in config):
        print("GS68_DIAGNOSTIC_BUILD=FAIL USB Serial/JTAG is not the exclusive primary console")
        return 1
    image = build_dir / "gs_r1_s3_hub.bin"
    if not image.is_file():
        print("GS68_DIAGNOSTIC_BUILD=FAIL expected standalone image is missing")
        return 1
    report = {
        "schema_version": 1,
        "status": "BUILD_ONLY_PASS",
        "physical": "NOT_RUN",
        "hardware_actions": [],
        "target": "ESP32-S3",
        "flash_mb": 16,
        "psram_mb": 8,
        "profile_id": "GS68_CLOUDSYNC_DS_MTLS_HIL",
        "source_branch": branch,
        "source_commit": source_commit,
        "source_code_tree_oid": source_code_tree_oid,
        "profile_sha256": profile_sha,
        "sdkconfig_sha256": sha256(sdkconfig),
        "build_configuration": {
            "idf_target": "esp32s3", "diagnostic_profile": "GS68_CLOUDSYNC_DS_MTLS_HIL",
            "gs68_cloudsync_diagnostic_only": True, "gs_hil_build": False,
            "gs_hil_control": False, "gs_hil_commissioning": False,
            "gs_hil_c8_ack_drop": False, "tls_version": "TLS1.2",
            "console_primary": "USB_SERIAL_JTAG",
            "console_uart0_primary": False,
            "console_usb_secondary": False,
            "stdin_read_mode": "USB_DRIVER_BLOCKING",
            "hardware_signer": "ESP32_DS_PERIPHERAL_SELECTED_NOT_PROVISIONED",
        },
        "image_path": str(image),
        "image_sha256": sha256(image),
        "image_bytes": image.stat().st_size,
        "build_directory": str(build_dir),
        "build_log": str(build_log),
        "idf_version": "v6.0.3",
        "flash_or_serial_used": False,
        "limitations": [
            "No DS/HMAC identity is provisioned; target TLS execution remains blocked.",
            "USB command framing and target crypto have not been observed on silicon.",
            "Build output is not physical qualification or proof of running image identity.",
        ],
    }
    report_path = root / "gs68_build_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"BUILD_REPORT={report_path}")
    print(f"BUILD_LOG={build_log}")
    print(f"IMAGE_SHA256={report['image_sha256']}")
    print(f"IMAGE_BYTES={report['image_bytes']}")
    print("GS68_DIAGNOSTIC_BUILD=PASS hardware_actions=0 physical=NOT_RUN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
