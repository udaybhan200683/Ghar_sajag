#!/usr/bin/env python3
"""Build a secure-runtime HIL Hub embedding one exact signed C3 OTA artifact."""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import shutil
import subprocess
import sys
import shlex
from pathlib import Path

from build_hw_pair import HUB_PROJECT, ROOT, activation_script, run_esptool, shlex_quote

REPO = ROOT.parent
S3_PROJECT = ROOT / "firmware/hub/target/esp32s3/idf"
EMBED = HUB_PROJECT / "main/node_firmware.bin"
OTA_SLOT_BYTES = 0x1E0000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def build_s3_fixture(image: Path, node_record: dict, args: argparse.Namespace) -> dict:
    """Build the isolated S3 owner-authenticated fixture without touching boards.

    The signed asset is staged under a unique ignored build directory. The
    classic Hub's shared embedded image and HIL profile are never changed.
    """
    activation = activation_script()
    build_root = (ROOT / "build/gs114_signed_s3").resolve()
    build_dir = (build_root / (args.build_dir or args.label)).resolve()
    if not build_dir.is_relative_to(build_root) or (build_dir.exists() and not args.build_dir):
        raise RuntimeError("S3 fixture label must select a new unique build directory")
    build_dir.mkdir(parents=True, exist_ok=bool(args.build_dir))
    asset = build_dir / "assets/node_firmware.bin"
    asset.parent.mkdir(exist_ok=True)
    shutil.copyfile(image, asset)
    if sha256(asset) != node_record["sha256"]:
        raise RuntimeError("staged S3 C3 asset differs from signed artifact")
    sdkconfig = build_dir / "sdkconfig"
    defaults = ";".join((str(S3_PROJECT / "sdkconfig.defaults"),
                         str(S3_PROJECT / "sdkconfig.defaults.outbox")))
    options = ["idf.py", "-C", str(S3_PROJECT), "-B", str(build_dir),
               "-D", "IDF_TARGET=esp32s3", "-D", f"SDKCONFIG={sdkconfig}",
               "-D", f"SDKCONFIG_DEFAULTS={defaults}",
               "-D", f"PROJECT_VER={args.label}",
               "-D", "GS_HIL_BUILD=OFF", "-D", "GS_HIL_CONTROL=OFF",
               "-D", "GS_HIL_COMMISSIONING=OFF", "-D", "GS_HIL_SIGNED_FOTA=ON",
               "-D", "GS_HIL_C8_ACK_DROP=OFF", "-D", "GS_HIL_C8_ACK_HOLD=OFF",
               "build"]
    environment = dict(os.environ)
    environment["GS_NODE_FIRMWARE_ASSET"] = str(asset)
    command = "source " + shlex.quote(str(activation)) + " >/dev/null 2>&1 && " + shlex.join(options)
    log = build_dir / "build.log"
    with log.open("w") as output:
        result = subprocess.run(["bash", "-c", command], cwd=ROOT, env=environment,
                                stdout=output, stderr=subprocess.STDOUT, timeout=1800)
    if result.returncode:
        raise RuntimeError(f"S3 signed fixture build failed; see {log}")
    built = build_dir / "gs_r1_s3_hub.bin"
    if not built.is_file() or built.stat().st_size > 0x400000:
        raise RuntimeError("S3 signed fixture is missing or exceeds its OTA slot")
    cache = (build_dir / "CMakeCache.txt").read_text(errors="replace")
    for required in ("GS_HIL_BUILD:BOOL=OFF", "GS_HIL_CONTROL:BOOL=OFF",
                     "GS_HIL_COMMISSIONING:BOOL=OFF", "GS_HIL_SIGNED_FOTA:BOOL=ON",
                     "GS_HIL_C8_ACK_DROP:BOOL=OFF", "GS_HIL_C8_ACK_HOLD:BOOL=OFF"):
        if required not in cache:
            raise RuntimeError(f"S3 signed fixture profile mismatch: {required}")
    data = built.read_bytes()
    if data.count(asset.read_bytes()) != 1 or b"START_SIGNED_C3_FOTA" not in data or \
            b"START_C3_FOTA" in data or b"START_AUTHENTICATED_SIGNED_C3_FOTA" in data or \
            b"COMMISSION_EXPECTED_NODE" in data or b"FIXTURE_STATUS" in data:
        raise RuntimeError("S3 signed fixture has wrong embedded image or UART controls")
    shutil.copy2(built, args.output)
    hub_metadata = run_esptool(args.output, activation)
    if hub_metadata.version != args.label:
        raise RuntimeError("S3 signed fixture version mismatch")
    record = {"schema": 1, "profile": "gs114-s3-signed-fota-fixture",
              "git_branch": git("branch", "--show-current"),
              "git_commit": git("rev-parse", "HEAD"),
              "git_dirty": bool(git("status", "--porcelain")),
              "label": args.label, "hub_app_version": hub_metadata.version,
              "idf_version": hub_metadata.idf_version, "build_dir": str(build_dir),
              "hub_image": str(args.output), "hub_sha256": sha256(args.output),
              "hub_size": args.output.stat().st_size,
              "embedded_c3_image": str(image), "embedded_c3_sha256": sha256(asset),
              "embedded_c3_size": asset.stat().st_size,
              "c3_version": node_record.get("version"),
              "signing_public_key_fingerprint_sha256":
                  node_record.get("signing_public_key_fingerprint_sha256"),
              "hil_control": False, "legacy_raw_fota": False,
              "hardware_actions": "NONE", "physical_status": "NOT_RUN"}
    args.output.with_suffix(args.output.suffix + ".json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-image", type=Path, required=True,
                        help="signed C3 image to embed byte-for-byte")
    parser.add_argument("--output", type=Path, required=True,
                        help="destination Hub binary (use a distinct path per candidate)")
    parser.add_argument("--label", required=True,
                        help="artifact label containing only letters, digits, dash, underscore")
    parser.add_argument("--build-dir", help="reuse this secure-profile build directory")
    parser.add_argument("--s3-fixture", action="store_true",
                        help="build an isolated S3 commissioning/authenticated-FOTA fixture; never flash")
    args = parser.parse_args()
    if not args.label or any(not (ch.isalnum() or ch in "-_") for ch in args.label):
        parser.error("label may contain only letters, digits, dash, underscore")
    image = args.node_image.resolve()
    if not image.is_file() or image.stat().st_size == 0:
        parser.error("signed C3 image is missing or empty")
    if image.stat().st_size > OTA_SLOT_BYTES:
        parser.error(f"signed C3 image exceeds OTA slot ({image.stat().st_size}>{OTA_SLOT_BYTES})")
    sidecar = image.with_suffix(image.suffix + ".json")
    if not sidecar.is_file():
        parser.error("signed image provenance sidecar is required")
    node_record = json.loads(sidecar.read_text(encoding="utf-8"))
    expected_hash = node_record.get("sha256")
    if expected_hash != sha256(image) or node_record.get("profile") != "signed-app-on-update":
        parser.error("signed image hash/profile does not match its provenance sidecar")
    if node_record.get("gs_hil_build") is not False or node_record.get("hil_control") is not True:
        parser.error("C3 image must retain secure runtime and explicit HIL-only controls")
    if args.s3_fixture:
        if args.build_dir and (Path(args.build_dir).is_absolute() or
                               any(part in (".", "..") for part in Path(args.build_dir).parts)):
            parser.error("S3 reuse build directory must be a simple relative name")
        record = build_s3_fixture(image, node_record, args)
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0

    activation = activation_script()
    build_root = (ROOT / "build").resolve()
    build_dir = ((Path(args.build_dir) if args.build_dir and Path(args.build_dir).is_absolute()
                  else build_root / (args.build_dir or f"secure_fota_hub_{args.label}")).resolve())
    if not build_dir.is_relative_to(build_root):
        parser.error("Hub build directory must remain under the product build directory")
    sdkconfig_path = build_dir / "sdkconfig"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_embed = EMBED.read_bytes() if EMBED.is_file() else None

    def restore_embed() -> None:
        if previous_embed is None:
            EMBED.unlink(missing_ok=True)
        else:
            EMBED.write_bytes(previous_embed)

    atexit.register(restore_embed)
    shutil.copyfile(image, EMBED)
    if sha256(EMBED) != expected_hash:
        raise RuntimeError("Hub embedded C3 bytes do not match signed artifact")
    idf_flags = (f"-B {shlex_quote(str(build_dir))} -DSDKCONFIG={shlex_quote(str(sdkconfig_path))} "
                 "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults -DGS_HIL_BUILD=OFF "
                 f"-DGS_HIL_CONTROL=ON -DPROJECT_VER={shlex_quote(args.label)}")
    cache = build_dir / "CMakeCache.txt"
    same_target = cache.is_file() and "IDF_TARGET:STRING=esp32\n" in cache.read_text(errors="ignore")
    target = "" if same_target else f"idf.py {idf_flags} set-target esp32 && "
    command = f"source {shlex_quote(str(activation))}; {target}idf.py {idf_flags} build"
    subprocess.run(["bash", "-lc", command], cwd=HUB_PROJECT, check=True)
    built = build_dir / "gs_hw_m1_hub.bin"
    if not built.is_file() or built.stat().st_size == 0:
        raise RuntimeError("Hub build did not produce the expected application image")
    if built.stat().st_size > OTA_SLOT_BYTES:
        raise RuntimeError("secure HIL Hub image exceeds its OTA slot")
    data = built.read_bytes()
    required = (b"START_AUTHENTICATED_SIGNED_C3_FOTA", b"COMMISSION_TEST_NODE",
                b"HIL_READY")
    missing = [marker.decode() for marker in required if marker not in data]
    if missing:
        raise RuntimeError(f"secure HIL Hub is missing required controls/artifact markers: {missing}")
    if b"START_C3_FOTA" in data:
        raise RuntimeError("secure HIL Hub unexpectedly contains the legacy raw FOTA trigger")
    shutil.copy2(built, output)
    hub_metadata = run_esptool(output, activation)
    if hub_metadata.version != args.label:
        raise RuntimeError(f"Hub version mismatch: {hub_metadata.version!r} != {args.label!r}")
    record = {"schema": 1, "profile": "secure-signed-fota-hil-control",
              "git_branch": git("branch", "--show-current"),
              "git_commit": git("rev-parse", "HEAD"),
              "git_dirty": bool(git("status", "--porcelain")),
              "label": args.label, "hub_app_version": hub_metadata.version,
              "idf_version": hub_metadata.idf_version,
              "build_dir": str(build_dir), "hub_image": str(output),
              "hub_sha256": sha256(output), "hub_size": output.stat().st_size,
              "embedded_c3_image": str(image), "embedded_c3_sha256": sha256(EMBED),
              "embedded_c3_size": EMBED.stat().st_size,
              "c3_version": node_record.get("version"),
              "signing_public_key_fingerprint_sha256":
                  node_record.get("signing_public_key_fingerprint_sha256"),
              "hil_control": True, "legacy_raw_fota": False}
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"SECURE FOTA HUB BUILD: FAIL — {exc}", file=sys.stderr)
        raise SystemExit(1)
