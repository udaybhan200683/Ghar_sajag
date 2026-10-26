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
        if re.search(r"HIL_(?:READY|STATE|OK|ERROR|FIXTURE)|GS117_TEST_ONLY|GS40T/1|PIR -> NodeRuntime|NodeMessage sent|Application ACK|authenticated|durable|CloudSync|COMMITTED|HubRuntime|HubSecurity|gs_hub_product|gs_hub_runtime|ESP-NOW|outbox|storage|mount|Wi-Fi|STA_START|firmware|image|boot:|ESP-ROM|rst:|panic|abort\(\)|Backtrace|app_init:|assert failed:|Guru Meditation Error|Stack canary|stack overflow", safe, re.I):
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


def bootstrap_config(stream, *, incoming=None, outgoing=None, clock=None,
                     challenge_timeout_seconds=20, require_boot=False,
                     expected_boot=None, evidence=None, identity_check=None) -> int:
    """Carry the existing GS40 encrypted envelope; private material stays host-side.

    The parent receives only a public target challenge and returns an encrypted,
    signed GS40 wire frame. Firmware remains the signature/AEAD authority.
    This child process accepts one response with a bounded wait and never logs it.
    """
    incoming = sys.stdin if incoming is None else incoming
    outgoing = sys.stdout if outgoing is None else outgoing
    clock = time.monotonic if clock is None else clock
    if (type(challenge_timeout_seconds) is not int or
            not 5 <= challenge_timeout_seconds <= 75):
        raise ValueError("TC001_BOOTSTRAP_CHALLENGE_TIMEOUT_OUT_OF_RANGE")
    evidence = {} if evidence is None else evidence
    started = clock()
    deadline = started + challenge_timeout_seconds
    pending = ""
    challenge = None
    boot_seen = False
    boot = {}
    stale_challenges = 0
    while clock() < deadline and challenge is None:
        lines = []
        pending = collect(stream, pending, lines)
        for line in lines:
            if re.search(r"ESP-ROM:|rst:0x|boot: ESP-IDF", line):
                boot_seen = True
                boot = {}
                challenge = None
            loaded = re.search(r"boot: Loaded app from partition at offset (0x[0-9a-f]+)", line)
            version = re.search(r"app_init: App version:\s+(\S+)", line)
            elf = re.search(r"app_init: ELF file SHA256:\s+([0-9a-f]+)", line)
            if loaded:
                boot["app_offset"] = loaded[1]
            if version:
                boot["app_version"] = version[1]
            if elf:
                boot["elf_sha256_prefix"] = elf[1]
            match = re.search(r"GS40T/1 CHALLENGE nonce=([0-9a-f]{64}) "
                              r"public_key=(04[0-9a-f]{128}) max_envelope=([0-9]+)", line)
            if match:
                if require_boot and not (boot_seen and len(boot) == 3):
                    stale_challenges += 1
                    continue
                challenge = match
        if challenge is None:
            time.sleep(0.01)
    evidence.update({"boot": boot, "post_reset_boot_verified": require_boot and boot_seen,
                     "ignored_pre_boot_challenges": stale_challenges})
    if challenge is None or not any(bytes.fromhex(challenge[1])):
        raise ValueError("TC001_BOOTSTRAP_TARGET_CHALLENGE_NOT_OBSERVED")
    if expected_boot is not None and boot != expected_boot:
        raise ValueError("TC001_BOOTSTRAP_RUNNING_IMAGE_MISMATCH")
    challenge_at = clock()
    evidence["challenge_wait_ms"] = int((challenge_at - started) * 1000)
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
    response_at = clock()
    if response_at - challenge_at > 25:
        raise ValueError("TC001_BOOTSTRAP_RESPONSE_EXCEEDED_TARGET_BUDGET")
    if identity_check is not None and not identity_check():
        raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
    evidence.update({"host_dtr": getattr(stream, "dtr", None),
                     "host_rts": getattr(stream, "rts", None)})
    # A reset while the parent signs the response invalidates this challenge.
    # Do not reopen or send a frame to a different boot generation.
    if stream.in_waiting:
        later_lines = []
        pending = collect(stream, pending, later_lines)
        if any(re.search(r"ESP-ROM:|rst:0x|boot: ESP-IDF|GS40T/1 (?:CHALLENGE|RX status=timeout)",
                         line) for line in later_lines):
            raise ValueError("TC001_BOOTSTRAP_TARGET_RESTARTED_OR_EXPIRED")
    # Send the challenge-bound, length-prefixed envelope as one bounded host
    # write. A successful pyserial write proves host-side acceptance only;
    # target receipt must be confirmed independently in the S3 receive log.
    if stream.write(frame) != len(frame):
        raise ValueError("TC001_BOOTSTRAP_ENVELOPE_WRITE_INCOMPLETE")
    stream.flush()
    evidence.update({"response_generation_ms": int((response_at - challenge_at) * 1000),
                     "host_write_ms": int((clock() - response_at) * 1000)})
    return len(frame)


def commission_fixture(c3, s3, c3_lines, s3_lines, *, clock=time.monotonic,
                       sleep=time.sleep, expected_public_key=None) -> dict:
    """One approved exact-fixture commissioning; QR proof stays only in memory."""
    state = next((line for line in reversed(c3_lines) if "HIL_STATE role=c3" in line), "")
    if (not all(token in state for token in (
            "retained=0 ", "in_flight=0 ", "HIL_AWAKE_TEST_ONLY",
            "hil_build=0", "hil_control=1", "physical_wake=0",
            "runtime_live=0", "sensing_live=0", "pending_inject=0")) or
            not any(re.search(r"HIL_FIXTURE_STATUS state=(?:idle|timed_out|rejected) ", line)
                    for line in s3_lines)):
        raise ValueError("TC001_COMMISSION_FIXTURE_NOT_IDLE_OR_EMPTY")
    c3.write(b"GET_TEST_QR\n")
    c3.flush()
    pending, public_key, installer_code = "", None, None
    deadline = clock() + 5
    while clock() < deadline and (public_key is None or installer_code is None):
        pending += c3.read(c3.in_waiting or 1).decode("ascii", "replace")
        lines = pending.split("\n")
        pending = lines[-1][-1024:]
        for line in lines[:-1]:
            key = re.search(r"HIL_TEST_QR profile=TEST_ONLY device_id=c3-146393c5d158 public_key=(04[0-9a-f]{128})", line)
            code = re.search(r"HIL_TEST_CODE profile=TEST_ONLY device_id=c3-146393c5d158 installer_code=([0-9a-f]{64})", line)
            if key: public_key = key[1]
            if code: installer_code = code[1]
        sleep(0.01)
    if public_key is None or installer_code is None or not any(bytes.fromhex(installer_code)):
        raise ValueError("TC001_EXACT_NODE_QR_PROOF_UNAVAILABLE")
    if expected_public_key is not None and public_key != expected_public_key:
        raise ValueError("TC001_NODE_IDENTITY_KEY_CHANGED")
    command = ("COMMISSION_EXPECTED_NODE c3-146393c5d158 146393c5d158 " +
               public_key + " " + installer_code + " bedroom Bedroom motion\n").encode()
    try:
        if s3.write(command) != len(command):
            raise ValueError("TC001_COMMISSION_REQUEST_WRITE_INCOMPLETE")
        s3.flush()
    finally:
        installer_code, command, pending, lines = None, None, "", []
        key, code, line = None, None, None
    tail = ""
    deadline = clock() + 5
    first = len(s3_lines)
    while clock() < deadline and not any("HIL_FIXTURE_OK request=exact_node" in x
                                         for x in s3_lines[first:]):
        tail = collect(s3, tail, s3_lines)
        sleep(0.02)
    if not any("HIL_FIXTURE_OK request=exact_node" in x for x in s3_lines[first:]):
        raise ValueError("TC001_HUB_COMMISSION_REQUEST_NOT_ACCEPTED")
    # Existing firmware verifies its encrypted recovery/association backups
    # before the owner-approved retirement; factory keys/counters are preserved.
    c3.write(b"FRESH_COMMISSION_GS117_TEST_FIXTURE\n")
    c3.flush()
    c3_tail, deadline, query_at = "", clock() + 90, clock()
    while clock() < deadline:
        c3_tail = collect(c3, c3_tail, c3_lines)
        tail = collect(s3, tail, s3_lines)
        # These are incrementing uint32 liveness counters, not booleans.
        latest_state = next((x for x in reversed(c3_lines) if "HIL_STATE role=c3" in x), "")
        runtime = re.search(r"\bruntime_live=([0-9]+)(?:\s|$)", latest_state)
        sensing = re.search(r"\bsensing_live=([0-9]+)(?:\s|$)", latest_state)
        ready = runtime is not None and sensing is not None and 0 < int(runtime[1]) < 2**32 and 0 < int(sensing[1]) < 2**32
        joined = any("HIL_FIXTURE_STATUS state=authenticated_rejoin" in x for x in s3_lines)
        backed_up = any("GS117_TEST_ONLY_FRESH_COMMISSIONING started" in x and
                        "prior_association_backed_up=1" in x for x in c3_lines)
        if ready and joined and backed_up:
            return {"status": "PASS", "node_id": "c3-146393c5d158",
                    "hub_id": "hub-e072a1d38d34", "home_id": "gs177-test-product",
                    "node_public_key": public_key,
                    "liveness": {"runtime": int(runtime[1]), "sensing": int(sensing[1])},
                    "proof": "AUTHENTICATED_REJOIN_AND_ACTIVE_NODE"}
        if any("GS117_TEST_ONLY_FRESH_COMMISSIONING rejected" in x for x in c3_lines):
            break
        if clock() >= query_at:
            c3.write(b"GET_STATE\n"); c3.flush()
            s3.write(b"FIXTURE_STATUS\n"); s3.flush()
            query_at = clock() + 5
        sleep(0.02)
    return {"status": "FAIL", "reason": "authenticated_session_not_observed",
            "node_public_key": public_key}


def observe(config: dict, *, serial_factory=None, port_finder=None,
            clock=None, sleep=None, boot_reset=None, bootstrap_exchange=None,
            fixture_exchange=None) -> dict:
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
        # Reuse Espressif's native-USB reset sequence; never enter a flash
        # operation.
        if s3_boot_reset:
            if boot_reset is None:
                from esptool.reset import HardReset

                boot_reset = lambda stream: HardReset(stream, uses_usb=True).reset()
            # Discard the previous application's buffered challenge before the
            # approved reset, then fence the exchange on the new boot transcript.
            if bootstrap_exchange is not None:
                s3_stream.reset_input_buffer()
            boot_reset(s3_stream)

        bootstrap_started = clock()
        bootstrap_evidence = {}
        try:
            bootstrap_tx_bytes = (bootstrap_exchange(
                                      s3_stream, require_boot=s3_boot_reset,
                                      expected_boot=config.get("expected_s3_boot"),
                                      evidence=bootstrap_evidence,
                                      identity_check=lambda: exact_port(s3, port_finder()))
                                  if bootstrap_exchange is not None else None)
        except ValueError as error:
            error.bootstrap_timeline = bootstrap_evidence
            raise
        bootstrap_exchange_ms = (max(0, int((clock() - bootstrap_started) * 1000))
                                 if bootstrap_tx_bytes is not None else None)
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
        s3_config_receive_pending = any("GS40T/1 CHALLENGE" in line for line in s3_lines)
        s3_status_command_ready = any(
            "HIL_FIXTURE_READY" in line and "FIXTURE_STATUS" in line for line in s3_lines)
        s3_status_command_sent = False
        if query_s3_status:
            # GS40 TEST_ONLY boot waits for the encrypted, length-prefixed
            # configuration envelope before HubRuntime/fixture command parsing
            # starts. Sending plain-text FIXTURE_STATUS into that receiver is
            # interpreted as an invalid envelope length and aborts startup.
            # Send only after the running firmware advertises this exact
            # command; otherwise retain passive boot evidence and fail closed.
            if s3_status_command_ready and not s3_config_receive_pending:
                s3_stream.write(b"FIXTURE_STATUS\n")
                s3_stream.flush()
                s3_status_command_sent = True
        deadline = clock() + observation_seconds - 4
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
            sleep(0.02)
        if not any("HIL_STATE role=c3" in line for line in c3_lines):
            raise ValueError("TC001_INSTALLED_C3_HIL_STATUS_NOT_OBSERVED")
        result = {"c3": c3_lines, "s3": s3_lines,
                  "s3_config_receive_pending": s3_config_receive_pending,
                  "s3_status_command_ready": s3_status_command_ready,
                  "s3_status_command_sent": s3_status_command_sent}
        if fixture_exchange is not None:
            result["commissioning"] = fixture_exchange(c3_stream, s3_stream,
                c3_lines, s3_lines, clock=clock, sleep=sleep,
                expected_public_key=config.get("expected_node_public_key"))
        if bootstrap_tx_bytes is not None:
            # This confirms only host API acceptance; target receipt is proven
            # separately by its GS40 RX/policy response in the captured logs.
            result["bootstrap_host_write_bytes"] = bootstrap_tx_bytes
            result["bootstrap_exchange_ms"] = bootstrap_exchange_ms
            result["bootstrap_timeline"] = bootstrap_evidence
            # GS40's authenticated receiver has a 60-second device-side
            # deadline. Preserve that entire observation window after the
            # host has delivered the challenge-bound frame, then allow a short
            # bounded margin for the target's fixed rejection/startup log.
            deadline = clock() + 10
            while clock() < deadline:
                c3_tail = collect(c3_stream, c3_tail, c3_lines)
                s3_tail = collect(s3_stream, s3_tail, s3_lines)
                sleep(0.02)
            result["s3"] = s3_lines
        return result
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
        elif action == "CommissionFixture":
            if (config.get("test_only_fixture_authorized") is not True or
                    config.get("home_id") != "gs177-test-product" or
                    config.get("s3_boot_reset", False) or
                    re.fullmatch(r"04[0-9a-f]{128}", config.get("expected_node_public_key", "")) is None):
                raise ValueError("TC001_EXACT_FIXTURE_COMMISSION_APPROVAL_REQUIRED")
            config["query_s3_status"] = True
            value = observe(config, fixture_exchange=commission_fixture)
        elif action == "Bootstrap":
            def exchange(stream, **kwargs):
                return bootstrap_config(
                    stream,
                    challenge_timeout_seconds=config.get(
                        "bootstrap_challenge_timeout_seconds", 20),
                    **kwargs)

            value = {"stage": "OBSERVATION",
                     **observe(config, bootstrap_exchange=exchange)}
        elif action == "Run":
            value = run(config)
        else:
            raise ValueError("TC001_SERIAL_ACTION_NOT_ALLOWED")
        print(json.dumps(value))
    except Exception as error:
        failure = {"error": str(error) if isinstance(error, ValueError) else type(error).__name__}
        if hasattr(error, "bootstrap_timeline"):
            failure["bootstrap_timeline"] = error.bootstrap_timeline
        print(json.dumps(failure))
        raise SystemExit(2)
