#!/usr/bin/env python
"""One controlled S3 ROM entry and read-only identity/partition/OTA readback."""
from pathlib import Path
import hashlib
import sys

from esptool.cmds import attach_flash, connect_esp, detect_flash_size, run_stub

PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00"
OUT = Path(__file__).parent
EXPECTED_MAC = bytes.fromhex("7c4fadb72a20")

with connect_esp(
    port=PORT,
    chip="esp32s3",
    initial_baud=115200,
    # The prior recorded call already entered ROM. Reconnect without resetting.
    before="no-reset",
    connect_attempts=1,
    open_port_attempts=1,
) as esp:
    print(f"PORT={PORT}")
    print(f"CHIP={esp.CHIP_NAME}")
    mac = esp.read_mac("BASE_MAC")
    print(f"BASE_MAC={':'.join(f'{octet:02x}' for octet in mac)}")
    security = esp.get_security_info()
    print(f"CHIP_ID={security['chip_id']}")
    flags = security["parsed_flags"]
    crypt_cnt = int(security["flash_crypt_cnt"])
    print(f"SECURE_BOOT_EN={int(flags['SECURE_BOOT_EN'])}")
    print(f"SECURE_DOWNLOAD_ENABLE={int(flags['SECURE_DOWNLOAD_ENABLE'])}")
    print(f"FLASH_CRYPT_CNT=0x{crypt_cnt:02x}")
    if esp.CHIP_NAME != "ESP32-S3" or bytes(mac) != EXPECTED_MAC:
        raise SystemExit("STOP: target chip/MAC did not match the approved S3")
    if flags["SECURE_BOOT_EN"] or flags["SECURE_DOWNLOAD_ENABLE"] or crypt_cnt.bit_count() % 2:
        raise SystemExit("STOP: active security configuration is incompatible with the approved app-only write")

    esp = run_stub(esp)
    attach_flash(esp)
    flash_id = esp.flash_id(cache=False)
    flash_size = detect_flash_size(esp)
    print(f"FLASH_ID=0x{flash_id:06x}")
    print(f"FLASH_SIZE={flash_size}")
    if str(flash_size).upper() != "16MB":
        raise SystemExit("STOP: flash capacity did not resolve to 16 MiB")

    for name, offset, size in (
        ("p8_s3_partition_table_read.bin", 0x8000, 0x1000),
        ("p8_s3_otadata_read.bin", 0xF000, 0x2000),
    ):
        data = esp.read_flash(offset, size)
        path = OUT / name
        path.write_bytes(data)
        print(f"READ offset=0x{offset:x} size=0x{size:x} path={path}")
        print(f"READ_SHA256 {name}={hashlib.sha256(data).hexdigest()}")
print("ROM_READBACK_COMPLETE; no flash writes issued")
