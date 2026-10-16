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
import re
import shutil
import subprocess
import sys
from pathlib import Path

from build_hw_pair import NODE_PROJECT, ROOT, activation_script, run_esptool


def run(*args: str) -> None:
    idf_py = Path(os.environ["IDF_PATH"]) / "tools/idf.py"
    subprocess.run((sys.executable, str(idf_py), *args), cwd=NODE_PROJECT, check=True)


def signed_hil_control_sdkconfig(config_text: str) -> str:
    """Keep the signed profile while routing HIL control over native USB JTAG."""
    values = {
        "ESP_CONSOLE_UART_DEFAULT": "# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set",
        "ESP_CONSOLE_USB_SERIAL_JTAG": "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
        "ESP_CONSOLE_UART_CUSTOM": "# CONFIG_ESP_CONSOLE_UART_CUSTOM is not set",
        "ESP_CONSOLE_NONE": "# CONFIG_ESP_CONSOLE_NONE is not set",
        "ESP_CONSOLE_SECONDARY_NONE": "CONFIG_ESP_CONSOLE_SECONDARY_NONE=y",
        "ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG":
            "# CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG is not set",
        "ESP_CONSOLE_UART": "# CONFIG_ESP_CONSOLE_UART is not set",
        "ESP_CONSOLE_UART_NUM": "CONFIG_ESP_CONSOLE_UART_NUM=-1",
        "ESP_CONSOLE_ROM_SERIAL_PORT_NUM": "CONFIG_ESP_CONSOLE_ROM_SERIAL_PORT_NUM=3",
    }
    lines = config_text.splitlines()
    for symbol, replacement in values.items():
        pattern = re.compile(rf"^(?:# )?CONFIG_{re.escape(symbol)}(?:=.*| is not set)$")
        matching = [index for index, line in enumerate(lines) if pattern.match(line)]
        if len(matching) != 1:
            raise RuntimeError(f"signed sdkconfig must contain exactly one CONFIG_{symbol} entry")
        lines[matching[0]] = replacement
    return "\n".join(lines) + "\n"


def signed_uart0_console_sdkconfig(config_text: str) -> str:
    """Select a UART0 primary console for signed, non-HIL physical profiles."""
    values = {
        "ESP_CONSOLE_UART_DEFAULT": "CONFIG_ESP_CONSOLE_UART_DEFAULT=y",
        "ESP_CONSOLE_USB_SERIAL_JTAG": "# CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG is not set",
        "ESP_CONSOLE_UART_CUSTOM": "# CONFIG_ESP_CONSOLE_UART_CUSTOM is not set",
        "ESP_CONSOLE_NONE": "# CONFIG_ESP_CONSOLE_NONE is not set",
        "ESP_CONSOLE_SECONDARY_NONE": "CONFIG_ESP_CONSOLE_SECONDARY_NONE=y",
        "ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG":
            "# CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG is not set",
        "ESP_CONSOLE_UART": "CONFIG_ESP_CONSOLE_UART=y",
        "ESP_CONSOLE_UART_NUM": "CONFIG_ESP_CONSOLE_UART_NUM=0",
        "ESP_CONSOLE_ROM_SERIAL_PORT_NUM": "CONFIG_ESP_CONSOLE_ROM_SERIAL_PORT_NUM=0",
    }
    lines = config_text.splitlines()
    for symbol, replacement in values.items():
        pattern = re.compile(rf"^(?:# )?CONFIG_{re.escape(symbol)}(?:=.*| is not set)$")
        matching = [index for index, line in enumerate(lines) if pattern.match(line)]
        if len(matching) != 1:
            raise RuntimeError(f"signed sdkconfig must contain exactly one CONFIG_{symbol} entry")
        lines[matching[0]] = replacement
    return "\n".join(lines) + "\n"


def signed_profile_cmake_options(*, hil_control: bool,
                                 force_boot_health_fail: bool,
                                 physical_wake: bool = False,
                                 ack_trace: bool = False,
                                 bat_c8_fixture_security: bool = False) -> list[str]:
    """Return signed C3 profile flags, rejecting the test fault in production."""
    if force_boot_health_fail and not hil_control:
        raise ValueError("forced boot-health failure requires --hil-control")
    if ack_trace and not physical_wake:
        raise ValueError("BAT-C8 ACK trace requires --physical-wake")
    if bat_c8_fixture_security and (not physical_wake or hil_control):
        raise ValueError("BAT-C8 fixture security requires --physical-wake and HIL controls disabled")
    options = ["-DGS_HIL_BUILD=OFF",
               f"-DGS_HIL_CONTROL={'ON' if hil_control else 'OFF'}"]
    if physical_wake:
        options.append("-DGS_BAT_C8_PHYSICAL_WAKE=ON")
    if ack_trace:
        options.append("-DGS_BAT_C8_ACK_TRACE=ON")
    if bat_c8_fixture_security:
        options.append("-DGS_BAT_C8_FIXTURE_SECURITY=ON")
    options.append(f"-DGS_HIL_FORCE_BOOT_HEALTH_FAIL={'ON' if force_boot_health_fail else 'OFF'}")
    return options


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signing-key", type=Path, required=True,
                        help="external RSA-3072 private key; never place it in the repository")
    parser.add_argument("--version", help="explicit firmware version for A/B qualification artifacts")
    parser.add_argument("--output", type=Path,
                        help="copy signed image here and write adjacent JSON provenance")
    parser.add_argument("--hil-control", action="store_true",
                        help="include HIL test controls while GS_HIL_BUILD remains OFF and secure runtime stays enabled")
    parser.add_argument("--force-boot-health-fail", action="store_true",
                        help="TEST ONLY: force rollback in a signed HIL candidate for a disposable fixture")
    parser.add_argument("--physical-wake", action="store_true",
                        help="TEST ONLY: retain real BAT-C8 GPIO4/timer light sleep in a signed HIL candidate")
    parser.add_argument("--ack-trace", action="store_true",
                        help="TEST ONLY: include bounded P9-A ACK-wait diagnostics; requires --physical-wake")
    parser.add_argument("--bat-c8-fixture-security", action="store_true",
                        help="TEST ONLY: read existing R&D identity state without HIL commands or NVS creation")
    parser.add_argument("--trusted-key", type=Path,
                        help="optional existing trust-anchor key; verification must succeed for matching signer")
    parser.add_argument("--build-dir", default="build_signed",
                        help="ESP-IDF build directory (default: build_signed)")
    args = parser.parse_args()
    try:
        profile_options = signed_profile_cmake_options(
            hil_control=args.hil_control,
            force_boot_health_fail=args.force_boot_health_fail,
            physical_wake=args.physical_wake,
            ack_trace=args.ack_trace,
            bat_c8_fixture_security=args.bat_c8_fixture_security)
    except ValueError as exc:
        parser.error(str(exc))
    key = args.signing_key.resolve()
    if not key.is_file() or key.is_relative_to(ROOT.parent):
        parser.error("signing key must exist outside the repository")
    if "IDF_PATH" not in os.environ:
        parser.error("activate ESP-IDF 6.0.3 before running")

    sdkconfig = NODE_PROJECT / "sdkconfig.signed"
    defaults = "sdkconfig.defaults;sdkconfig.signed.defaults"
    if args.hil_control:
        profile_build_dir = NODE_PROJECT / args.build_dir
        profile_build_dir.mkdir(parents=True, exist_ok=True)
        sdkconfig = profile_build_dir / "sdkconfig.signed.hil-control"
        existing_signed_config = NODE_PROJECT / "sdkconfig.signed"
        if existing_signed_config.is_file():
            sdkconfig.write_text(signed_hil_control_sdkconfig(
                existing_signed_config.read_text()))
        defaults += ";sdkconfig.hil.defaults"
    elif args.bat_c8_fixture_security:
        profile_build_dir = NODE_PROJECT / args.build_dir
        profile_build_dir.mkdir(parents=True, exist_ok=True)
        sdkconfig = profile_build_dir / "sdkconfig.signed.c8-fixture"
        base_signed = NODE_PROJECT / "sdkconfig.signed"
        if not sdkconfig.exists() and base_signed.is_file():
            sdkconfig.write_text(signed_uart0_console_sdkconfig(base_signed.read_text()))
        c8_defaults = profile_build_dir / "sdkconfig.c8-fixture.defaults"
        c8_defaults.write_text("""CONFIG_ESP_CONSOLE_UART_DEFAULT=y
# CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG is not set
# CONFIG_ESP_CONSOLE_UART_CUSTOM is not set
# CONFIG_ESP_CONSOLE_NONE is not set
CONFIG_ESP_CONSOLE_SECONDARY_NONE=y
# CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG is not set
CONFIG_ESP_CONSOLE_UART=y
CONFIG_ESP_CONSOLE_UART_NUM=0
CONFIG_ESP_CONSOLE_ROM_SERIAL_PORT_NUM=0
""")
        defaults += ";" + str(c8_defaults)
    build_args = ["-B", args.build_dir, "-DIDF_TARGET=esp32c3", f"-DSDKCONFIG={sdkconfig}",
                  f"-DSDKCONFIG_DEFAULTS={defaults}", *profile_options]
    if args.version:
        if not args.version.strip() or len(args.version) > 31 or any(ch.isspace() for ch in args.version):
            parser.error("version must be 1..31 non-whitespace characters")
        build_args.append(f"-DPROJECT_VER={args.version}")
    build_args.append("build")
    run(*build_args)
    config = sdkconfig.read_text()
    if args.bat_c8_fixture_security and any(
            line not in config.splitlines() for line in (
                "CONFIG_ESP_CONSOLE_UART_DEFAULT=y",
                "CONFIG_ESP_CONSOLE_UART_NUM=0",
                "CONFIG_ESP_CONSOLE_ROM_SERIAL_PORT_NUM=0")):
        raise RuntimeError("signed BAT-C8 fixture must select UART0 as its primary console")
    if args.bat_c8_fixture_security and "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y" in config.splitlines():
        raise RuntimeError("signed BAT-C8 fixture must not use the USB HIL primary console")
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
    elif any(marker in image for marker in (
            b"HIL_READY", b"INJECT_MOTION", b"GET_HEALTH", b"GET_STATE",
            b"GET_TEST_QR", b"SOFTWARE_RESTART")):
        raise RuntimeError("HIL command marker in signed non-HIL image")
    if args.bat_c8_fixture_security and (
            b"GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF" not in image or
            b"gs_dev_ident" not in image):
        raise RuntimeError("signed BAT-C8 image is missing its test-only identity profile marker")
    if args.ack_trace and b"GS114_ACK_WAIT_TRACE_SCHEMA=1" not in image:
        raise RuntimeError("signed BAT-C8 image is missing the ACK-wait trace marker")
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
    record = {"version": args.version or "unspecified",
              "profile": "signed-app-on-update",
              "hil_control": args.hil_control,
              "physical_wake": args.physical_wake,
              "ack_trace": args.ack_trace,
              "bat_c8_fixture_security": args.bat_c8_fixture_security,
              "force_boot_health_fail": args.force_boot_health_fail,
              "gs_hil_build": False,
              "image": str(output), "size": output.stat().st_size,
              "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "signing_public_key_fingerprint_sha256": fingerprint,
              "trusted_public_key_fingerprint_sha256": hashlib.sha256(
                  trusted_public_der).hexdigest(),
              "idf_version": image_metadata.idf_version,
              "build_dir": str(build_dir),
              "git_branch": subprocess.run(["git", "branch", "--show-current"], cwd=ROOT.parent,
                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip(),
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent,
                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip(),
              "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT.parent,
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
