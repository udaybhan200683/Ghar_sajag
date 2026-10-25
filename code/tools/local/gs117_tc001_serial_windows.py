"""Windows COM helper for the exact, fixture-authorized TC-001 pair."""
from __future__ import annotations

import base64
import json
import queue
import re
import sys
import threading
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
        if re.search(r"HIL_(?:READY|STATE|OK|ERROR|FIXTURE)|GS40T/1|PIR -> NodeRuntime|NodeMessage sent|Application ACK|authenticated|durable|CloudSync|COMMITTED|HubRuntime|HubSecurity|gs_hub_product|gs_hub_runtime|ESP-NOW|outbox|storage|mount|Wi-Fi|STA_START|firmware|image|boot:|ESP-ROM|rst:|panic|abort\(\)|Backtrace|app_init:", safe, re.I):
            safe = re.sub(r"(?i)(credential|secret|private.key|session.key|installer.code|wifi_psk|password|token|authorization|ssid|certificate)\s*[:=]\s*\S+",
                          r"\1=[REDACTED]", safe)
            if len(lines) < 300:
                lines.append(safe[:1024])
    return fragments[-1][-2048:]


def exact_port(board: dict, candidates: list[dict]) -> bool:
    return any(item["port"] == board["port"] and
               item["usb_hwid"] == board["usb_hwid"] and
               item["serial_number"] == board["serial_number"]
               for item in candidates)


def bootstrap_config(stream, *, incoming=None, outgoing=None, clock=None) -> None:
    """Carry the existing GS40 encrypted envelope; private material stays host-side.

    The parent receives only a public target challenge and returns an encrypted,
    signed GS40 wire frame. Firmware remains the signature/AEAD authority.
    This child process accepts one response with a bounded wait and never logs it.
    """
    incoming = sys.stdin if incoming is None else incoming
    outgoing = sys.stdout if outgoing is None else outgoing
    clock = time.monotonic if clock is None else clock
    deadline = clock() + 20
    pending = ""
    challenge = None
    while clock() < deadline and challenge is None:
        lines = []
        pending = collect(stream, pending, lines)
        for line in lines:
            match = re.search(r"GS40T/1 CHALLENGE nonce=([0-9a-f]{64}) "
                              r"public_key=(04[0-9a-f]{128}) max_envelope=([0-9]+)", line)
            if match:
                challenge = match
                break
        if challenge is None:
            time.sleep(0.01)
    if challenge is None or not any(bytes.fromhex(challenge[1])):
        raise ValueError("TC001_BOOTSTRAP_TARGET_CHALLENGE_NOT_OBSERVED")
    maximum = int(challenge[3])
    if not 517 <= maximum <= 24576:
        raise ValueError("TC001_BOOTSTRAP_TARGET_LIMIT_INVALID")
    print(json.dumps({"stage": "CONFIG_CHALLENGE", "nonce": challenge[1],
                      "public_key": challenge[2], "max_envelope": maximum}),
          file=outgoing, flush=True)
    responses = queue.Queue(maxsize=1)

    def receive():
        try:
            responses.put(incoming.readline(40000))
        except Exception:
            responses.put("")

    # One daemon reader per CLI child. Timeout exits the child; it cannot leave
    # a blocked worker in the long-lived web console or own another COM port.
    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    try:
        response = responses.get(timeout=20)
        payload = json.loads(response)
        if not isinstance(payload, dict) or set(payload) != {"encrypted_envelope_b64"}:
            raise ValueError("invalid response shape")
        frame = base64.b64decode(payload["encrypted_envelope_b64"], validate=True)
        if (not 521 <= len(frame) <= maximum + 4 or
                int.from_bytes(frame[:4], "big") != len(frame) - 4 or
                frame[4:9] != b"G40E\x01" or
                frame[9:41] != bytes.fromhex(challenge[1])):
            raise ValueError("invalid target-bound encrypted frame")
    except queue.Empty:
        raise ValueError("TC001_BOOTSTRAP_HOST_RESPONSE_TIMEOUT") from None
    except (ValueError, TypeError, KeyError):
        raise ValueError("TC001_BOOTSTRAP_ENCRYPTED_RESPONSE_INVALID") from None
    # Deliver the length prefix first so the S3 receiver enters its exact-body
    # read before the encrypted payload begins. Then keep packets smaller than
    # the USB Serial/JTAG RX ring and yield so Windows cannot overrun it.
    if stream.write(frame[:4]) != 4:
        raise ValueError("TC001_BOOTSTRAP_ENVELOPE_WRITE_INCOMPLETE")
    stream.flush()
    time.sleep(0.02)
    for offset in range(4, len(frame), 256):
        chunk = frame[offset:offset + 256]
        if stream.write(chunk) != len(chunk):
            raise ValueError("TC001_BOOTSTRAP_ENVELOPE_WRITE_INCOMPLETE")
        stream.flush()
        time.sleep(0.002)


def observe(config: dict, *, serial_factory=None, port_finder=None,
            clock=None, sleep=None, boot_reset=None, bootstrap_exchange=None) -> dict:
    """Reset-aware, bounded status observation; never sends an event command."""
    c3, s3 = config["c3"], config["s3"]
    query_s3_status = config.get("query_s3_status", False)
    if type(query_s3_status) is not bool:
        raise ValueError("TC001_S3_STATUS_QUERY_FLAG_MUST_BE_BOOLEAN")
    s3_boot_reset = config.get("s3_boot_reset", False)
    if type(s3_boot_reset) is not bool:
        raise ValueError("TC001_S3_BOOT_RESET_FLAG_MUST_BE_BOOLEAN")
    observation_seconds = config.get("observation_seconds", 10)
    if type(observation_seconds) is not int or not 10 <= observation_seconds <= 60:
        raise ValueError("TC001_OBSERVATION_SECONDS_OUT_OF_RANGE")
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
        # Opt-in only under the exact fixture's reset-aware inspection approval.
        # Keep the same open stream to retain early boot diagnostics. Reuse
        # Espressif's native-USB reset sequence; never enter a flash operation.
        if s3_boot_reset:
            if boot_reset is None:
                from esptool.reset import HardReset

                boot_reset = lambda stream: HardReset(stream, uses_usb=True).reset()
            boot_reset(s3_stream)
        if bootstrap_exchange is not None:
            bootstrap_exchange(s3_stream)
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
        if query_s3_status:
            s3_stream.write(b"FIXTURE_STATUS\n")
            s3_stream.flush()
        deadline = clock() + observation_seconds - 4
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
        elif action == "Bootstrap":
            value = {"stage": "OBSERVATION", **observe(config, bootstrap_exchange=bootstrap_config)}
        elif action == "Run":
            value = run(config)
        else:
            raise ValueError("TC001_SERIAL_ACTION_NOT_ALLOWED")
        print(json.dumps(value))
    except Exception as error:
        print(json.dumps({"error": str(error) if isinstance(error, ValueError) else type(error).__name__}))
        raise SystemExit(2)
