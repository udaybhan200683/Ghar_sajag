#!/usr/bin/env python3
"""Compile and execute the portable bounded GS-68 target command parser tests."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check_console_contract() -> None:
    profile = (ROOT / "firmware/hub/target/esp32s3/idf/sdkconfig.gs68_cloudsync_hil.defaults").read_text()
    for required in (
        "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
        "# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set",
        "# CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG is not set",
    ):
        if required not in profile:
            raise AssertionError(f"GS-68 diagnostic profile is missing console guard: {required}")

    app = (ROOT / "firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/app_main.cpp").read_text()
    for required in (
        "usb_serial_jtag_driver_install",
        "usb_serial_jtag_vfs_use_driver",
        "driver_config.rx_buffer_size = 4096",
        "fcntl(STDIN_FILENO, F_SETFL, 0)",
        "std::fgetc(stdin)",
        "std::clearerr(stdin)",
        "for (;;) {"):
        if required not in app:
            raise AssertionError(f"GS-68 command loop is missing blocking/persistent behavior: {required}")
    if "std::fgets(command" in app:
        raise AssertionError("GS-68 must not use a one-shot nonblocking fgets command loop")


def main() -> int:
    check_console_contract()
    with tempfile.TemporaryDirectory(prefix="gs68-node-protocol-") as directory:
        executable = Path(directory) / "gs68_node_protocol_test"
        subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-I", str(ROOT / "firmware/common/shared/include"),
            str(ROOT / "tests/cpp/gs68_diag_protocol_test.cpp"), "-o", str(executable)],
            check=True, cwd=ROOT)
        return subprocess.run([str(executable)], check=False, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
