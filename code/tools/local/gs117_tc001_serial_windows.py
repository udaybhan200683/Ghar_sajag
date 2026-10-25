"""Windows COM helper for the exact, fixture-authorized TC-001 pair."""
from __future__ import annotations

import base64
import json
import re
import sys
import time

import serial
from serial.tools import list_ports


def ports() -> list[dict[str, str]]:
    return [{"port": item.device, "usb_hwid": item.hwid or "",
             "serial_number": item.serial_number or ""}
            for item in list_ports.comports() if re.fullmatch(r"COM[0-9]+", item.device)]


def collect(stream, pending: str, lines: list[str]) -> str:
    pending += stream.read(stream.in_waiting or 1).decode("utf-8", "replace")
    fragments = pending.split("\n")
    for line in fragments[:-1]:
        safe = "".join(c for c in line if 32 <= ord(c) < 127).strip()
        if re.search(r"HIL_(?:READY|STATE|OK|ERROR)|PIR -> NodeRuntime|NodeMessage sent|Application ACK|authenticated|durable|CloudSync|COMMITTED|HubRuntime|HubSecurity|ESP-NOW|outbox|storage|mount|Wi-Fi|STA_START|firmware|image", safe, re.I):
            safe = re.sub(r"(?i)(credential|secret|private.key|session.key|wifi_psk|password|token|authorization|ssid|certificate)\s*[:=]\s*\S+",
                          r"\1=[REDACTED]", safe)
            if len(lines) < 300:
                lines.append(safe[:300])
    return fragments[-1][-500:]


def exact_port(board: dict, candidates: list[dict]) -> bool:
    return any(item["port"] == board["port"] and
               item["usb_hwid"] == board["usb_hwid"] and
               item["serial_number"] == board["serial_number"]
               for item in candidates)


def observe(config: dict, *, serial_factory=None, port_finder=None,
            clock=None, sleep=None) -> dict:
    """Reset-aware, bounded status observation; never sends an event command."""
    c3, s3 = config["c3"], config["s3"]
    serial_factory = serial.Serial if serial_factory is None else serial_factory
    port_finder = ports if port_finder is None else port_finder
    clock = time.monotonic if clock is None else clock
    sleep = time.sleep if sleep is None else sleep
    if (c3.get("port") != "COM4" or c3.get("serial_number") != "14:63:93:C5:D1:58" or
            s3.get("port") != "COM10" or s3.get("serial_number") != "E0:72:A1:D3:8D:34" or
            c3["port"] == s3["port"] or
            not all(exact_port(board, port_finder()) for board in (c3, s3))):
        raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
    # Opening a USB serial endpoint can reset some boards. DTR/RTS are held low
    # before open, but this does not assert that the interface is reset-free.
    streams = []
    try:
        for board in (s3, c3):
            stream = serial_factory()
            stream.port = board["port"]
            stream.baudrate = 115200
            stream.timeout = 0.1
            stream.write_timeout = 1
            stream.dtr = False
            stream.rts = False
            stream.open()
            streams.append(stream)
        c3_stream, s3_stream = streams[1], streams[0]
        c3_lines: list[str] = []
        s3_lines: list[str] = []
        c3_tail = s3_tail = ""
        deadline = clock() + 4
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
            sleep(0.02)
        c3_stream.write(b"GET_STATE\n")
        c3_stream.flush()
        deadline = clock() + 6
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
            sleep(0.02)
        if not any("HIL_STATE role=c3" in line for line in c3_lines):
            raise ValueError("TC001_INSTALLED_C3_HIL_STATUS_NOT_OBSERVED")
        return {"c3": c3_lines, "s3": s3_lines}
    finally:
        for stream in reversed(streams):
            if stream.is_open:
                stream.close()


def run(config: dict) -> dict:
    c3, s3 = config["c3"], config["s3"]
    if (c3.get("hil_control") is not True or c3.get("hil_build") is not False or
            c3.get("physical_wake") is not False):
        raise ValueError("TC001_C3_PROFILE_MUST_BE_PRODUCT_RUNTIME_HIL_CONTROL_AWAKE")
    if (c3["port"] == s3["port"] or
            not all(exact_port(board, ports()) for board in (c3, s3))):
        raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
    # Set control lines before open. A board-specific reset-safe serial receipt
    # is still mandatory in the controller; this cannot prove driver behavior.
    c3_stream = serial.Serial()
    s3_stream = serial.Serial()
    for stream, board in ((c3_stream, c3), (s3_stream, s3)):
        stream.port = board["port"]
        stream.baudrate = 115200
        stream.timeout = 0.1
        stream.dtr = False
        stream.rts = False
    c3_lines: list[str] = []
    s3_lines: list[str] = []
    c3_tail = s3_tail = ""
    try:
        s3_stream.open()
        c3_stream.open()
        c3_stream.write(b"GET_STATE\n")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
            if (any("HIL_STATE role=c3" in line for line in c3_lines) and
                    any("HIL_OK command=GET_STATE" in line for line in c3_lines)):
                break
        if (not any("HIL_STATE role=c3" in line for line in c3_lines) or
                not any("HIL_OK command=GET_STATE" in line for line in c3_lines)):
            raise ValueError("TC001_INSTALLED_C3_HIL_MODE_UNVERIFIED")
        mode_line = next(line for line in c3_lines if "HIL_STATE role=c3" in line)
        if not all(marker in mode_line for marker in (
                "power_mode=HIL_AWAKE_TEST_ONLY", "hil_build=0", "hil_control=1",
                "physical_wake=0")):
            raise ValueError("TC001_C3_NOT_IN_HIL_AWAKE_TEST_ONLY_MODE")
        c3_stream.write(b"INJECT_MOTION\n")
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
        return {"c3": c3_lines, "s3": s3_lines}
    finally:
        if c3_stream.is_open:
            c3_stream.close()
        if s3_stream.is_open:
            s3_stream.close()


if __name__ == "__main__":
    try:
        config = json.loads(base64.b64decode(sys.argv[1], validate=True))
        action = config.get("action")
        if action == "List":
            value = ports()
        elif action == "Observe":
            value = observe(config)
        elif action == "Run":
            value = run(config)
        else:
            raise ValueError("TC001_SERIAL_ACTION_NOT_ALLOWED")
        print(json.dumps(value))
    except Exception as error:
        print(json.dumps({"error": str(error) if isinstance(error, ValueError) else type(error).__name__}))
        raise SystemExit(2)
