#!/usr/bin/env python3
"""Build a secure-runtime HIL Hub embedding one exact signed C3 OTA artifact."""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from build_hw_pair import HUB_PROJECT, ROOT, activation_script, run_esptool, shlex_quote

REPO = ROOT.parents[1]
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-image", type=Path, required=True,
                        help="signed C3 image to embed byte-for-byte")
    parser.add_argument("--output", type=Path, required=True,
                        help="destination Hub binary (use a distinct path per candidate)")
    parser.add_argument("--label", required=True,
                        help="artifact label containing only letters, digits, dash, underscore")
    parser.add_argument("--build-dir", help="reuse this secure-profile build directory")
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
