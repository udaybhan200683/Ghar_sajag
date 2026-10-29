"""Windows COM helper for the exact, fixture-authorized TC-001 pair."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import subprocess
import uuid
from urllib.parse import urlsplit

import serial
from serial.tools import list_ports

ANDROID_REPORTS_MAX_SCROLLS = 55
ANDROID_REPORTS_END_NO_PROGRESS = 2
ANDROID_REPORTS_SCROLL_POLL_ATTEMPTS = 2


def ports() -> list[dict[str, str]]:
    return [{"port": item.device, "usb_hwid": item.hwid or "",
             "serial_number": item.serial_number or ""}
            for item in list_ports.comports() if re.fullmatch(r"COM[0-9]+", item.device)]


def collect(stream, pending: str, lines: list[str]) -> str:
    pending += stream.read(stream.in_waiting or 1).decode("utf-8", "replace")
    fragments = pending.split("\n")
    for line in fragments[:-1]:
        safe = "".join(c for c in line if 32 <= ord(c) < 127).strip()
        if re.search(r"HIL_(?:READY|STATE|OK|ERROR|FIXTURE)|GS117_TEST_ONLY|GS117_DEV_REJOIN|GS40T/1|PIR -> NodeRuntime|NodeMessage sent|Application ACK|authenticated|durable|CloudSync|COMMITTED|HubRuntime|HubSecurity|gs_hub_product|gs_hub_runtime|ESP-NOW|outbox|storage|mount|Wi-Fi|STA_START|firmware|image|boot:|ESP-ROM|rst:|panic|abort\(\)|Backtrace|app_init:|SPI\s+Flash(?:\s+Size)?\s*[:=]|esp_psram|octal_psram|spiram|assert failed:|Guru Meditation Error|Stack canary|stack overflow", safe, re.I):
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
    memory_evidence_lines = []
    while clock() < deadline and challenge is None:
        lines = []
        pending = collect(stream, pending, lines)
        for line in lines:
            if (re.search(r"\bSPI\s+Flash(?:\s+Size)?\s*[:=]", line, re.I) or
                    re.search(r"\bFound\s+[0-9]+\s*(?:B|KB|MB|GB|KiB|MiB|GiB)\s+PSRAM\b", line, re.I) or
                    re.search(r"\bpsram_size\s*[:=]", line, re.I)):
                memory_evidence_lines.append(line)
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
    evidence["s3_memory_capacity"] = s3_memory_capacity(memory_evidence_lines)
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
        memory_evidence_lines.extend(
            line for line in later_lines
            if (re.search(r"\bSPI\s+Flash(?:\s+Size)?\s*[:=]", line, re.I) or
                re.search(r"\bFound\s+[0-9]+\s*(?:B|KB|MB|GB|KiB|MiB|GiB)\s+PSRAM\b", line, re.I) or
                re.search(r"\bpsram_size\s*[:=]", line, re.I)))
    # Send the challenge-bound, length-prefixed envelope as one bounded host
    # write. A successful pyserial write proves host-side acceptance only;
    # target receipt must be confirmed independently in the S3 receive log.
    if stream.write(frame) != len(frame):
        raise ValueError("TC001_BOOTSTRAP_ENVELOPE_WRITE_INCOMPLETE")
    stream.flush()
    evidence.update({"response_generation_ms": int((response_at - challenge_at) * 1000),
                     "host_write_ms": int((clock() - response_at) * 1000)})
    evidence["s3_memory_capacity"] = s3_memory_capacity(memory_evidence_lines)
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


READINESS_TRANSIENT_MARKERS = ("signed-time bootstrap unavailable",
    "time/authority refresh failed", "authority bootstrap unavailable")


def readiness_guard(config, c3_lines, s3_lines):
    """Standing readiness stops collection/commands at the first target failure."""
    if config.get("stop_on_readiness_error") is not True:
        return
    markers = ("failed closed", "startup refused", "Node recovery restore failed",
               "Node recovery checkpoint failed", "Node rejoin failed", "Node security owner faulted",
               "signed-time bootstrap unavailable", "time/authority refresh failed",
               "authority bootstrap unavailable", "GS40T/1 REJECT", "panic", "assert failed",
               "TLS validation=end valid=0", "signature verification failed", "identity mismatch")
    if config.get("defer_transient_refresh_failure") is True:
        markers = tuple(m for m in markers if m not in READINESS_TRANSIENT_MARKERS)
    if any(marker.lower() in line.lower() for line in c3_lines + s3_lines for marker in markers):
        error = ValueError("TC001_TARGET_READINESS_GUARD_FAILED")
        error.captured_observation = {"c3": c3_lines, "s3": s3_lines}
        raise error


def s3_memory_capacity(lines: list[str]) -> dict:
    """Extract only explicit ESP-IDF flash/PSRAM startup capacity evidence."""
    multipliers = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3,
                   "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3}
    flash_values = []
    psram_values = []
    matched_lines = []
    flash_pattern = re.compile(
        r"\bSPI\s+Flash(?:\s+Size)?\s*[:=]\s*([0-9]+)\s*(B|KB|MB|GB|KiB|MiB|GiB)\b", re.I)
    psram_found_pattern = re.compile(
        r"\bFound\s+([0-9]+)\s*(B|KB|MB|GB|KiB|MiB|GiB)\s+PSRAM\b", re.I)
    psram_bytes_pattern = re.compile(r"\bpsram_size\s*[:=]\s*([0-9]+)\b", re.I)
    for line in lines:
        flash = flash_pattern.search(line)
        psram = psram_found_pattern.search(line)
        psram_bytes = psram_bytes_pattern.search(line)
        if flash:
            flash_values.append(int(flash[1]) * multipliers[flash[2].upper()])
            matched_lines.append(line)
        if psram:
            psram_values.append(int(psram[1]) * multipliers[psram[2].upper()])
            matched_lines.append(line)
        elif psram_bytes:
            psram_values.append(int(psram_bytes[1]))
            matched_lines.append(line)
    flash_unique = set(flash_values)
    psram_unique = set(psram_values)
    status = ("CONFLICT" if len(flash_unique) > 1 or len(psram_unique) > 1 else
              "PASS" if flash_unique and psram_unique else "INCOMPLETE")
    return {"status": status,
            "flash_size_bytes": next(iter(flash_unique)) if len(flash_unique) == 1 else None,
            "psram_size_bytes": next(iter(psram_unique)) if len(psram_unique) == 1 else None,
            "evidence_lines": matched_lines}


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
    if type(config.get("c3_boot_reset", False)) is not bool:
        raise ValueError("TC001_C3_BOOT_RESET_FLAG_MUST_BE_BOOLEAN")
    require_s3_memory_profile = config.get("require_s3_memory_profile", False)
    if type(require_s3_memory_profile) is not bool:
        raise ValueError("TC001_S3_MEMORY_PROFILE_FLAG_MUST_BE_BOOLEAN")
    expected_s3_memory_profile = config.get("expected_s3_memory_profile")
    if require_s3_memory_profile and expected_s3_memory_profile != {
            "flash_size_bytes": 16 * 1024 * 1024,
            "psram_size_bytes": 8 * 1024 * 1024}:
        raise ValueError("TC001_S3_MEMORY_PROFILE_EXPECTATION_INVALID")
    observation_seconds = config.get("observation_seconds", 10)
    if type(observation_seconds) is not int or not 10 <= observation_seconds <= 60:
        raise ValueError("TC001_OBSERVATION_SECONDS_OUT_OF_RANGE")
    c3_status_interval_seconds = config.get("c3_status_interval_seconds", 0)
    if (type(c3_status_interval_seconds) is not int or
            c3_status_interval_seconds != 0 and not 5 <= c3_status_interval_seconds <= 30):
        raise ValueError("TC001_C3_STATUS_INTERVAL_OUT_OF_RANGE")
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
        if config.get("c3_boot_reset"):
            from esptool.reset import HardReset
            HardReset(c3_stream, uses_usb=True).reset()
        c3_lines: list[str] = []
        s3_lines: list[str] = []
        c3_tail = s3_tail = ""
        deadline = clock() + 4
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
            readiness_guard(config, c3_lines, s3_lines)
            sleep(0.02)
        c3_stream.write(b"GET_STATE\n")
        c3_stream.flush()
        c3_status_queries = 1
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
        next_c3_status = (clock() + c3_status_interval_seconds
                          if c3_status_interval_seconds else None)
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            s3_tail = collect(s3_stream, s3_tail, s3_lines)
            readiness_guard(config, c3_lines, s3_lines)
            if next_c3_status is not None and clock() >= next_c3_status:
                c3_stream.write(b"GET_STATE\n")
                c3_stream.flush()
                c3_status_queries += 1
                next_c3_status = clock() + c3_status_interval_seconds
            sleep(0.02)
        if not any("HIL_STATE role=c3" in line for line in c3_lines):
            raise ValueError("TC001_INSTALLED_C3_HIL_STATUS_NOT_OBSERVED")
        result = {"c3": c3_lines, "s3": s3_lines,
                  "c3_status_queries": c3_status_queries,
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
                readiness_guard(config, c3_lines, s3_lines)
                sleep(0.02)
            result["s3"] = s3_lines
        bootstrap_memory = bootstrap_evidence.get("s3_memory_capacity", {})
        memory_lines = list(bootstrap_memory.get("evidence_lines", [])) + s3_lines
        memory = s3_memory_capacity(memory_lines)
        if require_s3_memory_profile and (
                memory["status"] != "PASS" or
                memory["flash_size_bytes"] != expected_s3_memory_profile["flash_size_bytes"] or
                memory["psram_size_bytes"] != expected_s3_memory_profile["psram_size_bytes"]):
            error = ValueError("TC001_S3_MEMORY_PROFILE_NOT_VERIFIED")
            error.captured_observation = {
                "c3": c3_lines, "s3": s3_lines, "s3_memory_capacity": memory}
            raise error
        result["s3_memory_capacity"] = memory
        return result
    finally:
        for stream in reversed(streams):
            if stream.is_open:
                stream.close()


def observe_node(config: dict) -> dict:
    """Bounded existing GET_STATE observation; S3 stays metadata-only."""
    c3, s3 = config['c3'], config['s3']
    if (c3.get('port') != 'COM4' or c3.get('serial_number') != '14:63:93:C5:D1:58' or
        s3.get('port') != 'COM10' or s3.get('serial_number') != 'E0:72:A1:D3:8D:34' or
        not all(exact_port(board, ports()) for board in (c3,s3))):
        raise ValueError('TC001_VERIFIED_USB_INTERFACE_MISMATCH')
    duration = config.get('observation_seconds', 30)
    if type(duration) is not int or not 10 <= duration <= 60:
        raise ValueError('TC001_OBSERVATION_SECONDS_OUT_OF_RANGE')
    stream = serial.Serial();stream.port=c3['port'];stream.baudrate=115200
    stream.timeout=.1;stream.write_timeout=1;stream.dtr=False;stream.rts=False
    lines=[];pending=''
    try:
        stream.open();deadline=time.monotonic()+duration;query=0
        while time.monotonic()<deadline:
            pending=collect(stream,pending,lines)
            readiness_guard({'stop_on_readiness_error':True},lines,[])
            if time.monotonic()>=query:
                stream.write(b'GET_STATE\n');stream.flush();query=time.monotonic()+10
            time.sleep(.02)
        return {'c3':lines,'s3_serial_opened':False,'motion_injection':False}
    finally:
        if stream.is_open:stream.close()


def run(config: dict) -> dict:
    """Run one approved C3 injection; enumerate S3, but never open its UART.

    Opening the physical S3 UART can reboot the Hub and discard its RAM-only
    GS40 envelope. The Node's authenticated class-0 application ACK is the
    evidence of durable Hub admission; CloudSync is checked independently at
    GS-179 using the original EventKey.
    """
    c3, s3 = config["c3"], config["s3"]
    if (c3.get("hil_control") is not True or c3.get("hil_build") is not False or
            c3.get("physical_wake") is not False):
        raise ValueError("TC001_C3_PROFILE_MUST_BE_PRODUCT_RUNTIME_HIL_CONTROL_AWAKE")
    if (c3["port"] == s3["port"] or
            not all(exact_port(board, ports()) for board in (c3, s3))):
        raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
    # Current USB descriptors are checked for both devices. Only COM4 is
    # opened; DTR/RTS low is not represented as proof of reset safety.
    c3_stream = serial.Serial()
    c3_stream.port = c3["port"]
    c3_stream.baudrate = 115200
    c3_stream.timeout = 0.1
    c3_stream.write_timeout = 1
    c3_stream.dtr = False
    c3_stream.rts = False
    c3_lines: list[str] = []
    c3_tail = ""
    try:
        c3_stream.open()
        c3_stream.write(b"GET_STATE\n")
        deadline = time.monotonic() + 30
        next_query = time.monotonic() + 2
        mode_line = ""
        while time.monotonic() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            mode_line = next((line for line in reversed(c3_lines)
                              if "HIL_STATE role=c3" in line), "")
            live = re.search(r"\bruntime_live=([0-9]+)\b", mode_line)
            sensing = re.search(r"\bsensing_live=([0-9]+)\b", mode_line)
            pending = re.search(r"\bpending_inject=([0-9]+)\b", mode_line)
            retained = re.search(r"\bretained=([0-9]+)\b", mode_line)
            in_flight = re.search(r"\bin_flight=([0-9]+)\b", mode_line)
            ready = (all(marker in mode_line for marker in (
                "power_mode=HIL_AWAKE_TEST_ONLY", "hil_build=0", "hil_control=1",
                "physical_wake=0")) and live and sensing and pending and retained and
                     in_flight and int(live[1]) > 0 and int(sensing[1]) > 0 and
                     int(pending[1]) == 0 and int(retained[1]) == 0 and
                     int(in_flight[1]) == 0)
            if (ready and any("HIL_OK command=GET_STATE" in line for line in c3_lines)):
                break
            if time.monotonic() >= next_query:
                c3_stream.write(b"GET_STATE\n")
                c3_stream.flush()
                next_query = time.monotonic() + 2
        if not (ready and any("HIL_OK command=GET_STATE" in line for line in c3_lines)):
            raise ValueError("TC001_INSTALLED_C3_HIL_MODE_UNVERIFIED")
        c3_state = mode_line
        runtime_value, sensing_value = int(live[1]), int(sensing[1])
        # Drain already buffered runtime diagnostics before the single HIL
        # trigger so pre-existing or ambient events cannot be correlated as
        # this run's stimulus.
        drain_deadline = time.monotonic() + 0.3
        while time.monotonic() < drain_deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
        c3_lines = []
        c3_tail = ""
        c3_stream.write(b"INJECT_MOTION\n")
        c3_stream.flush()
        command_sent_at = time.monotonic()
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines)
            pair = node_event_pair(c3_lines)
            if pair is not None and c3_durable_ack(c3_lines, *pair):
                break
        pair = node_event_pair(c3_lines)
        return {"c3": c3_lines, "s3": [], "s3_serial_opened": False,
                "c3_serial_opened": True, "c3_power_mode": "HIL_AWAKE_TEST_ONLY",
                "c3_state": c3_state, "runtime_live": runtime_value,
                "sensing_live": sensing_value,
                "injection_command_sent": True,
                "injection_command_acknowledged": any(
                    "HIL_OK command=INJECT_MOTION" in line for line in c3_lines),
                "node_event_observed": pair is not None,
                "hub_application_acknowledged": bool(
                    pair is not None and c3_durable_ack(c3_lines, *pair)),
                "s3_admission_source": "C3_AUTHENTICATED_APPLICATION_ACK_CLASS_0",
                "event_wait_ms": int((time.monotonic() - command_sent_at) * 1000)}
    finally:
        if c3_stream.is_open:
            c3_stream.close()


def c3_durable_ack(lines: list[str], session: int, sequence: int) -> bool:
    expected = re.compile(
        rf"\bApplication ACK session={session} seq={sequence} class=0 retired=1\b")
    return any(expected.search(line) for line in lines)


def node_event_pair(lines: list[str]) -> tuple[int, int] | None:
    if not any("HIL_OK command=INJECT_MOTION" in line for line in lines):
        return None
    pairs = []
    for line in lines:
        match = re.search(r"PIR -> NodeRuntime session=(\d+) seq=(\d+)", line)
        if match:
            pairs.append((int(match[1]), int(match[2])))
    return pairs[0] if len(pairs) == 1 else None


def find_adb() -> Path:
    candidates = []
    found = shutil.which("adb.exe") or shutil.which("adb")
    if found:
        candidates.append(Path(found))
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        downloads = Path(user_profile) / "Downloads"
        candidates.extend(downloads.glob("platform-tools*/platform-tools/adb.exe"))
        candidates.extend(downloads.glob("platform-tools*/adb.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError("TC001_ANDROID_ADB_NOT_FOUND_IN_PATH_OR_DOWNLOADS")


def adb_call(adb: Path, serial_number: str, *arguments: str,
             timeout_seconds: int = 12) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", serial_number):
        raise ValueError("TC001_ANDROID_ADB_SERIAL_INVALID")
    try:
        result = subprocess.run([str(adb), "-s", serial_number, *arguments],
                                capture_output=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError("TC001_ANDROID_ADB_COMMAND_TIMEOUT") from None
    if result.returncode != 0:
        raise ValueError("TC001_ANDROID_ADB_COMMAND_FAILED")
    return result.stdout


def android_device_ready(config: dict, *, adb_locator=find_adb,
                         call=adb_call) -> dict:
    """Read-only check of the already installed, receipt-bound Android app."""
    phone = config.get("phone", {})
    serial_number = phone.get("adb_serial") or phone.get("device_serial")
    package = phone.get("package")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", str(serial_number or "")):
        raise ValueError("TC001_ANDROID_ADB_IDENTITY_RECEIPT_MISSING")
    if package not in {"in.gharsajag.caregiver", "in.gharsajag.caregiver.discoverytest"}:
        raise ValueError("TC001_ANDROID_PACKAGE_NOT_APPROVED")
    adb = adb_locator()
    try:
        devices = subprocess.run([str(adb), "devices", "-l"], capture_output=True,
                                 text=True, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError("TC001_ANDROID_ADB_DEVICE_QUERY_TIMEOUT") from None
    if devices.returncode != 0:
        raise ValueError("TC001_ANDROID_ADB_DEVICE_QUERY_FAILED")
    authorized = {line.split()[0] for line in devices.stdout.splitlines()[1:]
                  if len(line.split()) >= 2 and line.split()[1] == "device"}
    if serial_number not in authorized:
        raise ValueError("TC001_APPROVED_ANDROID_DEVICE_NOT_AUTHORIZED_OR_CONNECTED")
    installed = call(adb, serial_number, "shell", "pm", "path", package).decode(
        "utf-8", "replace").strip()
    if not installed.startswith("package:/data/app/"):
        raise ValueError("TC001_APPROVED_ANDROID_PACKAGE_NOT_INSTALLED")
    package_dump = call(adb, serial_number, "shell", "dumpsys", "package", package,
                        timeout_seconds=15).decode("utf-8", "replace")
    version = re.search(r"\bversionName=([^\s]+)", package_dump)
    version_code = re.search(r"\bversionCode=([0-9]+)", package_dump)
    expected_version = phone.get("version_name") or phone.get("version")
    if not version or not version_code or (expected_version and version[1] != expected_version):
        raise ValueError("TC001_ANDROID_INSTALLED_VERSION_RECEIPT_MISMATCH")
    return {"status": "PASS", "device_serial": serial_number, "package": package,
            "version_name": version[1], "version_code": int(version_code[1]),
            "signer_sha256": phone.get("signer_sha256"),
            "signer_source": "CURRENT_OWNER_ONLY_INSTALL_RECEIPT",
            "installed_path_verified": True}


def ui_dump(adb: Path, serial_number: str) -> tuple[ET.Element, bytes]:
    remote = "/sdcard/gs117_tc001_" + uuid.uuid4().hex + ".xml"
    try:
        adb_call(adb, serial_number, "shell", "uiautomator", "dump", "--compressed", remote,
                 timeout_seconds=15)
        raw = adb_call(adb, serial_number, "shell", "cat", remote,
                       timeout_seconds=8)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("TC001_ANDROID_UI_TREE_EXCEEDS_SIZE_LIMIT")
        return ET.fromstring(raw), raw
    except ET.ParseError:
        raise ValueError("TC001_ANDROID_UI_TREE_INVALID") from None
    finally:
        try:
            adb_call(adb, serial_number, "shell", "rm", "-f", remote,
                     timeout_seconds=5)
        except Exception:
            pass


def ui_texts(root: ET.Element) -> list[str]:
    # Android exposes navigation and expandable controls as either visible text
    # or an accessibility content description. Read both without weakening any
    # Home, backend-origin, authentication, or exact-outcome checks.
    values = []
    for node in root.iter("node"):
        for attribute in ("text", "content-desc"):
            value = node.get(attribute, "").strip()
            if value:
                values.append(value)
    return values


def ui_node_bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                         node.get("bounds", ""))
    if not match:
        return None
    bounds = tuple(map(int, match.groups()))
    return bounds if bounds[2] > bounds[0] and bounds[3] > bounds[1] else None


def bounds_intersect(bounds: tuple[int, int, int, int] | None,
                     clip: tuple[int, int, int, int]) -> bool:
    if bounds is None:
        return False
    left, top, right, bottom = bounds
    clip_left, clip_top, clip_right, clip_bottom = clip
    return left < clip_right and right > clip_left and top < clip_bottom and bottom > clip_top


def bounds_contained(bounds: tuple[int, int, int, int] | None,
                     clip: tuple[int, int, int, int]) -> bool:
    if bounds is None:
        return False
    left, top, right, bottom = bounds
    clip_left, clip_top, clip_right, clip_bottom = clip
    return (clip_left <= left < right <= clip_right and
            clip_top <= top < bottom <= clip_bottom)


def exact_key_in_ui(root: ET.Element, expected: dict, *,
                    visible_bounds: tuple[int, int, int, int] | None = None) -> bool:
    for node in root.iter("node"):
        if visible_bounds is not None and not bounds_contained(ui_node_bounds(node), visible_bounds):
            continue
        text = node.get("text", "").strip() or node.get("content-desc", "").strip()
        if not text.startswith("EventKey:"):
            continue
        raw = text.partition(":")[2].strip()
        try:
            decoded, end = json.JSONDecoder().raw_decode(raw)
        except json.JSONDecodeError:
            continue
        if decoded == expected and not raw[end:].strip():
            return True
    return False


def exact_decision_in_ui(root: ET.Element, expected: str, *,
                         visible_bounds: tuple[int, int, int, int] | None = None) -> bool:
    """Match a Hub-owned decision identity, never a Node EventKey."""
    return any((visible_bounds is None or bounds_contained(ui_node_bounds(node), visible_bounds)) and
               (node.get("text", "").strip() == "Decision ID: " + expected or
                node.get("content-desc", "").strip() == "Decision ID: " + expected)
               for node in root.iter("node"))


def canonical_https_origin(value: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme.casefold() != "https" or not parsed.hostname or
                parsed.username or parsed.password or parsed.path not in {"", "/"} or
                parsed.query or parsed.fragment):
            return None
        return ("https", parsed.hostname.casefold(), parsed.port or 443)
    except (TypeError, ValueError):
        return None


def tap_text(adb: Path, serial_number: str, root: ET.Element,
             target: str, *, index: int = 0, call=adb_call,
             visible_bounds: tuple[int, int, int, int] | None = None) -> bool:
    matches = [node for node in root.iter("node")
               if target in {node.get("text", "").strip(),
                             node.get("content-desc", "").strip()} and
               (visible_bounds is None or
                bounds_contained(ui_node_bounds(node), visible_bounds))]
    if index >= len(matches):
        return False
    bounds = ui_node_bounds(matches[index])
    if bounds is None:
        return False
    x1, y1, x2, y2 = bounds
    call(adb, serial_number, "shell", "input", "tap",
         str((x1 + x2) // 2), str((y1 + y2) // 2), timeout_seconds=5)
    return True


def reports_scroll_region(root: ET.Element) -> tuple[int, int, int, int]:
    """Find a bounded gesture area inside the Reports WebView, above its tabs."""
    reports_tab = any(node.get("clickable") == "true" and
                      "Reports" in {node.get("text", "").strip(),
                                    node.get("content-desc", "").strip()}
                      for node in root.iter("node"))
    if not reports_tab:
        raise ValueError("TC001_ANDROID_REPORTS_TAB_NOT_CONFIRMED_FOR_SCROLL")
    webviews = [node for node in root.iter("node")
                if node.get("class") == "android.webkit.WebView" and
                node.get("scrollable") == "true"]
    if len(webviews) != 1:
        raise ValueError("TC001_ANDROID_REPORTS_SCROLL_CONTAINER_UNAVAILABLE")
    web = ui_node_bounds(webviews[0])
    if web is None:
        raise ValueError("TC001_ANDROID_REPORTS_SCROLL_BOUNDS_INVALID")
    web_left, web_top, web_right, web_bottom = web
    nav_labels = {"Home", "Devices", "Reports", "Settings"}
    nav_tops = [bounds[1] for node in root.iter("node")
                if node.get("clickable") == "true" and
                ({node.get("text", "").strip(), node.get("content-desc", "").strip()} & nav_labels) and
                (bounds := ui_node_bounds(node)) is not None and
                bounds[1] > web_top + (web_bottom - web_top) // 2]
    if not nav_tops:
        raise ValueError("TC001_ANDROID_REPORTS_BOTTOM_NAV_BOUNDS_MISSING")
    clip_bottom = min(web_bottom, min(nav_tops) - 16)
    header_bounds = [ui_node_bounds(node) for node in root.iter("node")
                     if "Latest recorded events" in
                     {node.get("text", "").strip(), node.get("content-desc", "").strip()}]
    visible_header_bottoms = [b[3] for b in header_bounds if b is not None and
                              web_top <= b[1] < clip_bottom]
    if visible_header_bottoms:
        clip_top = max(web_top + 24, max(visible_header_bottoms) + 16)
    else:
        # Once Reports has scrolled, the section heading may remain in the
        # accessibility tree with zero-height bounds while event details are
        # visible at the top of the WebView. Do not clip those real cards using
        # a guessed one-third offset.
        clip_top = web_top
    if clip_bottom - clip_top < 240:
        raise ValueError("TC001_ANDROID_REPORTS_SCROLL_VIEWPORT_TOO_SMALL")
    return web_left + 8, clip_top, web_right - 8, clip_bottom


def reports_page_fingerprint(root: ET.Element,
                             viewport: tuple[int, int, int, int]) -> tuple[tuple[str, str, tuple[int, int, int, int]], ...]:
    values = []
    for node in root.iter("node"):
        bounds = ui_node_bounds(node)
        if not bounds_intersect(bounds, viewport):
            continue
        text = node.get("text", "").strip() or node.get("content-desc", "").strip()
        if text and not text.startswith(("EventKey:", "Decision ID:")):
            values.append((node.get("class", ""), text, bounds))
    return tuple(values)


def scroll_reports(adb: Path, serial_number: str, root: ET.Element, *,
                   call=adb_call) -> tuple[int, int, int, int]:
    if "Reports" not in ui_texts(root):
        raise ValueError("TC001_ANDROID_REPORTS_VIEW_NOT_CONFIRMED_FOR_SCROLL")
    viewport = reports_scroll_region(root)
    left, top, right, bottom = viewport
    x = (left + right) // 2
    # Swipe within the WebView's event-list body; the bottom navigation is
    # excluded from the gesture region and never receives a tap.
    call(adb, serial_number, "shell", "input", "swipe", str(x), str(bottom - 32),
         str(x), str(top + max(48, (bottom - top) // 5)), "350", timeout_seconds=5)
    return viewport


def android_verify_event(config: dict, *, adb_locator=find_adb,
                         call=adb_call, sleep=time.sleep) -> dict:
    """Foreground the real app, refresh Reports, and match a Node key or Hub decision."""
    adb = adb_locator()
    ready = android_device_ready(config, adb_locator=lambda: adb, call=call)
    phone = config["phone"]
    serial_number = ready["device_serial"]
    package = ready["package"]
    home_id = config.get("home_id")
    expected_origin = config.get("backend_origin")
    expected_key = config.get("event_key")
    expected_decision = config.get("decision_id")
    decision_mode = isinstance(expected_decision, str)
    if (not isinstance(home_id, str) or
            (decision_mode and (not expected_decision.startswith("morning-complete:") or
                                len(expected_decision) > 256 or isinstance(expected_key, dict))) or
            (not decision_mode and not isinstance(expected_key, dict))):
        raise ValueError("TC001_ANDROID_OUTCOME_SCOPE_MISSING")
    call(adb, serial_number, "shell", "monkey", "-p", package,
         "-c", "android.intent.category.LAUNCHER", "1", timeout_seconds=12)
    foreground = call(adb, serial_number, "shell", "dumpsys", "activity", "activities",
                      timeout_seconds=12).decode("utf-8", "replace")
    resumed = next((line for line in foreground.splitlines()
                    if "mResumedActivity" in line or "topResumedActivity" in line), "")
    if package not in resumed:
        raise ValueError("TC001_APPROVED_ANDROID_APP_NOT_FOREGROUNDED")
    root = None
    raw = b""
    for _ in range(12):
        sleep(0.5)
        root, raw = ui_dump(adb, serial_number)
        if package in " ".join(ui_texts(root)) or "connected" in " ".join(ui_texts(root)).casefold():
            break
    if root is None:
        raise ValueError("TC001_ANDROID_APP_UI_NOT_AVAILABLE")
    # WebView accessibility can be empty briefly after the Activity is
    # foregrounded even though the page subsequently renders normally. Keep
    # polling the existing UI tree for a bounded interval before treating
    # Settings as unavailable; never infer a tap or relax the checks below.
    settings_reached = False
    for attempt in range(20):
        texts = ui_texts(root)
        if "App & connection" in " ".join(texts):
            settings_reached = True
            break
        if tap_text(adb, serial_number, root, "Settings", call=call):
            settings_reached = True
            break
        if attempt < 19:
            sleep(0.4)
            root, raw = ui_dump(adb, serial_number)
    if not settings_reached:
        raise ValueError("TC001_ANDROID_SETTINGS_NAVIGATION_NOT_FOUND")
    for _ in range(20):
        sleep(0.4)
        root, raw = ui_dump(adb, serial_number)
        texts = ui_texts(root)
        joined = "\n".join(texts)
        if "App & connection" in joined and home_id in joined:
            break
    joined = "\n".join(ui_texts(root))
    settings_origin = None
    for text in ui_texts(root):
        for match in re.finditer(r"https://[^\s<>]+", text):
            candidate = match.group(0).rstrip(".,;)")
            if canonical_https_origin(candidate) is not None:
                settings_origin = candidate
                break
        if settings_origin:
            break
    backend_status = next((text for text in ui_texts(root)
                           if "Backend API" in text), "")
    if ("Settings" not in joined or "App & connection" not in joined or home_id not in joined or
            not settings_origin or canonical_https_origin(settings_origin) !=
            canonical_https_origin(expected_origin) or "CONNECTED" not in backend_status):
        raise ValueError("TC001_ANDROID_BACKEND_ORIGIN_HOME_OR_AUTHENTICATED_SESSION_MISMATCH")
    root, raw = ui_dump(adb, serial_number)
    if not tap_text(adb, serial_number, root, "Reports", call=call):
        if "Latest recorded events" not in " ".join(texts):
            raise ValueError("TC001_ANDROID_REPORTS_NAVIGATION_NOT_FOUND")
    for _ in range(20):
        sleep(0.4)
        root, raw = ui_dump(adb, serial_number)
        texts = ui_texts(root)
        joined = "\n".join(texts)
        if "Latest recorded events" in joined and home_id in joined:
            break
    joined = "\n".join(ui_texts(root))
    if "Latest recorded events" not in joined or home_id not in joined:
        raise ValueError("TC001_ANDROID_REPORTS_HOME_NOT_VERIFIED")
    # The app already refreshes its visible view on document.visibilitychange.
    # Background and foreground the real app after opening Reports to invoke
    # that production refresh path rather than relying on the 15-second timer.
    call(adb, serial_number, "shell", "input", "keyevent", "KEYCODE_HOME",
         timeout_seconds=5)
    sleep(0.25)
    call(adb, serial_number, "shell", "monkey", "-p", package,
         "-c", "android.intent.category.LAUNCHER", "1", timeout_seconds=12)
    foreground = call(adb, serial_number, "shell", "dumpsys", "activity", "activities",
                      timeout_seconds=12).decode("utf-8", "replace")
    resumed = next((line for line in foreground.splitlines()
                    if "mResumedActivity" in line or "topResumedActivity" in line), "")
    if package not in resumed:
        raise ValueError("TC001_APPROVED_ANDROID_APP_NOT_FOREGROUNDED_AFTER_REFRESH")

    # Reports may contain more cards than fit on screen. Expand only visible
    # controls, then move through the verified WebView in bounded swipes. The
    # bottom tabs are excluded from the gesture region; off-screen controls
    # with clamped/zero-height bounds are never tapped.
    scrolls = 0
    stalled_swipes = 0
    while True:
        sleep(0.25)
        root, raw = ui_dump(adb, serial_number)
        joined = "\n".join(ui_texts(root))
        if "Latest recorded events" not in joined or home_id not in joined:
            raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_REFRESH")
        viewport = reports_scroll_region(root)
        visible_texts = [node.get("text", "").strip() or
                         node.get("content-desc", "").strip()
                         for node in root.iter("node")
                         if bounds_contained(ui_node_bounds(node), viewport)]
        visible_joined = "\n".join(visible_texts)
        exact_outcome = (exact_decision_in_ui(root, expected_decision,
                                              visible_bounds=viewport) if decision_mode
                         else exact_key_in_ui(root, expected_key,
                                              visible_bounds=viewport))
        if exact_outcome:
            screenshot = call(adb, serial_number, "exec-out", "screencap", "-p",
                              timeout_seconds=12)
            if (not screenshot.startswith(b"\x89PNG\r\n\x1a\n") or
                    len(screenshot) > 8 * 1024 * 1024):
                raise ValueError("TC001_ANDROID_SCREENSHOT_CAPTURE_INVALID")
            expected_label = ("Morning routine completed" if decision_mode else "Motion recorded")
            if expected_label.casefold() not in visible_joined.casefold():
                raise ValueError("TC001_ANDROID_EXACT_OUTCOME_LABEL_MISMATCH")
            if not decision_mode and "bedroom" not in visible_joined.casefold():
                raise ValueError("TC001_ANDROID_EXACT_KEY_NOT_ASSOCIATED_WITH_BEDROOM_MOTION")
            result = {"status": "PASS", "observation": "AUTOMATED_PASS",
                    "package": package, "device_serial": serial_number,
                    "version_name": ready["version_name"],
                    "signer_sha256": ready.get("signer_sha256"),
                    "home_id": home_id, "backend_origin": settings_origin,
                    "backend_status": backend_status,
                    "reports_view": "Latest recorded events",
                    "outcome_details_open": True,
                    "event_label": expected_label,
                    "reports_scrolls": scrolls,
                    "ui_dump_sha256": hashlib.sha256(raw).hexdigest(),
                    "ui_hierarchy_xml_b64": base64.b64encode(raw).decode("ascii"),
                    "screenshot_png_b64": base64.b64encode(screenshot).decode("ascii")}
            if decision_mode:
                result["decision_id"] = expected_decision
                result["decision_kind"] = "MORNING_ROUTINE_COMPLETED"
            else:
                result["event_key"] = expected_key
                result["event_details_open"] = True
                result["logical_node_id"] = "bedroom"
            return result

        details_label = "Decision details" if decision_mode else "Event details"
        identity_prefix = "Decision ID:" if decision_mode else "EventKey:"
        summaries = [node for node in root.iter("node")
                     if details_label in {node.get("text", "").strip(),
                                          node.get("content-desc", "").strip()} and
                     node.get("clickable") == "true" and
                     bounds_intersect(ui_node_bounds(node), viewport)]
        expanded = sum(1 for node in root.iter("node")
                       if (node.get("text", "").strip().startswith(identity_prefix) or
                           node.get("content-desc", "").strip().startswith(identity_prefix)) and
                       bounds_intersect(ui_node_bounds(node), viewport))
        if expanded < len(summaries):
            if not tap_text(adb, serial_number, root, details_label,
                            index=expanded, call=call, visible_bounds=viewport):
                raise ValueError("TC001_ANDROID_OUTCOME_DETAILS_CONTROL_UNAVAILABLE")
            sleep(0.25)
            continue

        if scrolls >= ANDROID_REPORTS_MAX_SCROLLS:
            raise ValueError("TC001_ANDROID_REPORTS_SCROLL_LIMIT_REACHED_BEFORE_EXACT_OUTCOME")
        before = reports_page_fingerprint(root, viewport)
        scroll_reports(adb, serial_number, root, call=call)
        scrolls += 1
        advanced = False
        for _ in range(ANDROID_REPORTS_SCROLL_POLL_ATTEMPTS):
            sleep(0.25)
            next_root, next_raw = ui_dump(adb, serial_number)
            next_joined = "\n".join(ui_texts(next_root))
            if ("Latest recorded events" not in next_joined or home_id not in next_joined):
                raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_SCROLL")
            next_viewport = reports_scroll_region(next_root)
            root, raw, viewport = next_root, next_raw, next_viewport
            if reports_page_fingerprint(root, viewport) != before:
                advanced = True
                stalled_swipes = 0
                break
        if not advanced:
            stalled_swipes += 1
            if stalled_swipes >= ANDROID_REPORTS_END_NO_PROGRESS:
                if decision_mode:
                    raise ValueError("TC001_EXACT_HUB_DECISION_NOT_VISIBLE_IN_ANDROID_REPORTS")
                raise ValueError("TC001_EXACT_EVENT_KEY_NOT_VISIBLE_IN_ANDROID_EVENT_DETAILS")


if __name__ == "__main__":
    try:
        config = json.loads(base64.b64decode(sys.argv[1], validate=True))
        action = config.get("action")
        if action == "List":
            value = ports()
        elif action == "ObserveNode":
            value = observe_node(config)
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
        elif action == "AndroidReady":
            value = android_device_ready(config)
        elif action == "AndroidVerify":
            value = android_verify_event(config)
        elif action == "AndroidVerifyDecision":
            value = android_verify_event(config)
        else:
            raise ValueError("TC001_SERIAL_ACTION_NOT_ALLOWED")
        print(json.dumps(value))
    except Exception as error:
        failure = {"error": str(error) if isinstance(error, ValueError) else type(error).__name__}
        if hasattr(error, "captured_observation"):
            failure["observation"] = error.captured_observation
        if hasattr(error, "bootstrap_timeline"):
            failure["bootstrap_timeline"] = error.bootstrap_timeline
        print(json.dumps(failure))
        raise SystemExit(2)
