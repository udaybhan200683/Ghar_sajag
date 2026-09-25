#!/usr/bin/env python3
"""Build and sign a C3 OTA image with an external RSA-3072 key.

This software-signed profile does not enable hardware Secure Boot or program eFuses.
The first image installed on a device must also be signed by the same key: ESP-IDF
uses its signature block as the trusted public key for later OTA verification.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from build_hw_pair import NODE_PROJECT, ROOT


def run(*args: str) -> None:
    idf_py = Path(os.environ["IDF_PATH"]) / "tools/idf.py"
    subprocess.run((sys.executable, str(idf_py), *args), cwd=NODE_PROJECT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signing-key", type=Path, required=True,
                        help="external RSA-3072 private key; never place it in the repository")
    args = parser.parse_args()
    key = args.signing_key.resolve()
    if not key.is_file() or key.is_relative_to(ROOT.parents[1]):
        parser.error("signing key must exist outside the repository")
    if "IDF_PATH" not in os.environ:
        parser.error("activate ESP-IDF 6.0.3 before running")

    run("-B", "build_signed", "-DSDKCONFIG=sdkconfig.signed",
        "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.signed.defaults",
        "-DGS_HIL_BUILD=OFF", "build")
    config = (NODE_PROJECT / "sdkconfig.signed").read_text()
    required = ("CONFIG_SECURE_SIGNED_APPS_NO_SECURE_BOOT=y",
                "CONFIG_SECURE_SIGNED_APPS_RSA_SCHEME=y",
                "CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT=y")
    if any(f"{line}\n" not in config for line in required):
        raise RuntimeError("signed-app configuration missing; refusing unsigned artifact")
    if "CONFIG_SECURE_BOOT=y\n" in config or "CONFIG_SECURE_BOOT_BUILD_SIGNED_BINARIES=y\n" in config:
        raise RuntimeError("unexpected hardware Secure Boot or build-time signing")

    unsigned = NODE_PROJECT / "build_signed/gs_hw_m1_node.bin"
    signed = NODE_PROJECT / "build_signed/gs_hw_m1_node.signed.bin"
    run("-B", "build_signed", "secure-sign-data", "--version", "2", "--keyfile", str(key),
        "--output", str(signed), str(unsigned))
    run("-B", "build_signed", "secure-verify-signature", "--keyfile", str(key), str(signed))
    if signed.stat().st_size > 0x1E0000:
        raise RuntimeError("signed image exceeds the C3 OTA partition")
    image = signed.read_bytes()
    if b"HIL_READY" in image or b"INJECT_MOTION" in image:
        raise RuntimeError("HIL marker in signed production image")
    print(f"SIGNED C3 IMAGE: {signed}")
    print(f"SIZE: {len(image)} / {0x1E0000} bytes")
    print(f"SHA256: {hashlib.sha256(image).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
