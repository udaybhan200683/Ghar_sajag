#!/usr/bin/env python3
"""Build and sign a C3 OTA image with an external RSA-3072 key.

This software-signed profile does not enable hardware Secure Boot or program eFuses.
The first image installed on a device must also be signed by the same key: ESP-IDF
uses its signature block as the trusted public key for later OTA verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build_hw_pair import NODE_PROJECT, ROOT, activation_script, run_esptool


def run(*args: str) -> None:
    idf_py = Path(os.environ["IDF_PATH"]) / "tools/idf.py"
    subprocess.run((sys.executable, str(idf_py), *args), cwd=NODE_PROJECT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signing-key", type=Path, required=True,
                        help="external RSA-3072 private key; never place it in the repository")
    parser.add_argument("--version", help="explicit firmware version for A/B qualification artifacts")
    parser.add_argument("--output", type=Path,
                        help="copy signed image here and write adjacent JSON provenance")
    parser.add_argument("--hil-control", action="store_true",
                        help="include UART test controls while GS_HIL_BUILD remains OFF and secure runtime stays enabled")
    parser.add_argument("--trusted-key", type=Path,
                        help="optional existing trust-anchor key; verification must succeed for matching signer")
    parser.add_argument("--build-dir", default="build_signed",
                        help="ESP-IDF build directory (default: build_signed)")
    args = parser.parse_args()
    key = args.signing_key.resolve()
    if not key.is_file() or key.is_relative_to(ROOT.parents[1]):
        parser.error("signing key must exist outside the repository")
    if "IDF_PATH" not in os.environ:
        parser.error("activate ESP-IDF 6.0.3 before running")

    build_args = ["-B", args.build_dir, "-DSDKCONFIG=sdkconfig.signed",
                  "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.signed.defaults",
                  "-DGS_HIL_BUILD=OFF", f"-DGS_HIL_CONTROL={'ON' if args.hil_control else 'OFF'}"]
    if args.version:
        if not args.version.strip() or len(args.version) > 31 or any(ch.isspace() for ch in args.version):
            parser.error("version must be 1..31 non-whitespace characters")
        build_args.append(f"-DPROJECT_VER={args.version}")
    build_args.append("build")
    run(*build_args)
    config = (NODE_PROJECT / "sdkconfig.signed").read_text()
    required = ("CONFIG_SECURE_SIGNED_APPS_NO_SECURE_BOOT=y",
                "CONFIG_SECURE_SIGNED_APPS_RSA_SCHEME=y",
                "CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT=y")
    if any(f"{line}\n" not in config for line in required):
        raise RuntimeError("signed-app configuration missing; refusing unsigned artifact")
    if "CONFIG_SECURE_BOOT=y\n" in config or "CONFIG_SECURE_BOOT_BUILD_SIGNED_BINARIES=y\n" in config:
        raise RuntimeError("unexpected hardware Secure Boot or build-time signing")

    build_dir = NODE_PROJECT / args.build_dir
    unsigned = build_dir / "gs_hw_m1_node.bin"
    signed = build_dir / "gs_hw_m1_node.signed.bin"
    run("-B", args.build_dir, "secure-sign-data", "--version", "2", "--keyfile", str(key),
        "--output", str(signed), str(unsigned))
    run("-B", args.build_dir, "secure-verify-signature", "--keyfile", str(key), str(signed))
    if signed.stat().st_size > 0x1E0000:
        raise RuntimeError("signed image exceeds the C3 OTA partition")
    image = signed.read_bytes()
    if args.hil_control:
        if b"HIL_READY" not in image or b"INJECT_MOTION" not in image or b"GET_TEST_QR" not in image:
            raise RuntimeError("secure HIL-control image is missing expected diagnostic controls")
    elif b"HIL_READY" in image or b"INJECT_MOTION" in image:
        raise RuntimeError("HIL marker in signed production image")
    trusted_key = args.trusted_key.resolve() if args.trusted_key else key
    verify = subprocess.run([sys.executable, str(Path(os.environ["IDF_PATH"]) / "tools/idf.py"),
                             "-B", args.build_dir, "secure-verify-signature", "--keyfile",
                             str(trusted_key), str(signed)], cwd=NODE_PROJECT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if args.trusted_key and trusted_key != key:
        if verify.returncode == 0:
            raise RuntimeError("candidate unexpectedly verifies with the trusted A-image key")
        print("TRUSTED-KEY SIGNATURE CHECK: REJECTED (expected for negative candidate)")
    elif verify.returncode:
        raise RuntimeError("signed image failed trusted-key signature verification: " + verify.stdout[-1200:])
    def public_key_der(path: Path) -> bytes:
        return subprocess.run(["openssl", "pkey", "-in", str(path), "-pubout", "-outform", "DER"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout

    def require_rsa_3072(der: bytes, label: str) -> None:
        info = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER", "-text", "-noout"],
                              input=der, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                              text=False).stdout.decode("ascii", errors="replace")
        if "Public-Key: (3072 bit)" not in info:
            raise RuntimeError(f"{label} must be RSA-3072")

    public_der = public_key_der(key)
    trusted_public_der = public_key_der(trusted_key)
    require_rsa_3072(public_der, "signing key")
    require_rsa_3072(trusted_public_der, "trusted key")
    image_metadata = run_esptool(signed, activation_script())
    if args.version and image_metadata.version != args.version:
        raise RuntimeError(f"signed image version mismatch: {image_metadata.version!r} != {args.version!r}")
    fingerprint = hashlib.sha256(public_der).hexdigest()
    output = args.output.resolve() if args.output else signed
    if output != signed.resolve():
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(signed, output)
    record = {"version": args.version or "unspecified", "profile": "signed-app-on-update",
              "hil_control": args.hil_control, "gs_hil_build": False,
              "image": str(output), "size": output.stat().st_size,
              "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "signing_public_key_fingerprint_sha256": fingerprint,
              "trusted_public_key_fingerprint_sha256": hashlib.sha256(
                  trusted_public_der).hexdigest(),
              "idf_version": image_metadata.idf_version,
              "build_dir": str(build_dir),
              "git_branch": subprocess.run(["git", "branch", "--show-current"], cwd=ROOT.parents[1],
                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip(),
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parents[1],
                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip(),
              "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT.parents[1],
                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip())}
    if args.output:
        output.with_suffix(output.suffix + ".json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"SIGNED C3 IMAGE: {signed}")
    print(f"SIZE: {output.stat().st_size} / {0x1E0000} bytes")
    print(f"SHA256: {record['sha256']}")
    print(f"SIGNING PUBLIC KEY SHA256: {fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
