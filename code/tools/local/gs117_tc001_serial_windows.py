"""Windows COM helper for the exact, fixture-authorized TC-001 pair."""
from __future__ import annotations

import base64
import binascii
import contextlib
from datetime import datetime, timezone
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

S3_UPDATE_TARGET = {
    "device_id": "hub-e072a1d38d34",
    "port": "COM10",
    "serial_number": "E0:72:A1:D3:8D:34",
    "home_id": "gs177-test-product",
    "usb_vid": 0x303A,
    "usb_pid": 0x1001,
}
S3_UPDATE_PARTITION_CONTRACT = "S3_R1_OUTBOX_4M_STATE_256K_OTA_4M"
S3_UPDATE_LAYOUT = {
    "nvs": (0x9000, 0x6000), "otadata": (0xF000, 0x2000),
    "phy_init": (0x11000, 0x1000), "ota_0": (0x20000, 0x400000),
    "ota_1": (0x420000, 0x400000), "gs_outbox": (0x820000, 0x400000),
    "gs_state": (0xC20000, 0x40000),
}
S3_UPDATE_WRITE_BOUNDARIES = frozenset({
    "application_erase", "application_write", "selector_update", "selector_recovery",
})
S3_UPDATE_IDF_SOURCE_HASHES = {
    "app_update/otatool.py":
        "da713515caf674b4169c764ffb1e4dd068637bab8db26e6f48b7f09ceebdcb85",
    "partition_table/parttool.py":
        "a2e3eb680b44807cdcb19c8ef784d32251530caa8453d37ab3f218eb4dee7af3",
}


def ports() -> list[dict[str, str]]:
    return [{"port": item.device, "usb_hwid": item.hwid or "",
             "serial_number": item.serial_number or ""}
            for item in list_ports.comports() if re.fullmatch(r"COM[0-9]+", item.device)]


MAX_CAPTURE_LINES = 300
MAX_CAPTURE_CHARS = 1024
MAX_SERIAL_CHUNK = 4096
MAX_PENDING_CHARS = 2048
OBSERVATION_IO_MARGIN_SECONDS = 0.005
GET_STATE_QUERY_INTERVAL_SECONDS = 10
_DISCARD_PARTIAL = "\x00GS117_DISCARD_PARTIAL"


def capture_state():
    # Line text stays in the existing ordered list. Metadata refers to its index;
    # do not duplicate UART text or retain an unbounded raw stream.
    return {"records": [], "boot_markers": [], "boot_epoch": 0,
            "bytes_read": 0, "filtered_lines": 0, "dropped_lines": 0,
            "truncated_chars": 0, "pending_truncated_chars": 0,
            "late_read_bytes": 0, "deadline_overruns": 0, "boot_markers_dropped": 0,
            "unterminated_tail_chars": 0}


def collect(stream, pending: str, lines: list[str], *, capture=None,
            deadline=None, clock=None, wall_clock=None) -> str:
    clock = time.monotonic if clock is None else clock
    if deadline is not None:
        remaining = deadline - clock()
        if remaining <= OBSERVATION_IO_MARGIN_SECONDS:
            return pending
        # Windows pySerial read uses this bounded timeout; no new reader thread
        # or cancellation mechanism owns the COM handle.
        read_timeout = min(0.1, remaining - OBSERVATION_IO_MARGIN_SECONDS)
        # pySerial 3.5 on Windows reapplies the entire COM configuration,
        # including DTR/RTS control, whenever timeout is assigned. Preserve
        # the open port's configuration during ordinary reads; adjust only
        # when the remaining deadline actually requires another timeout.
        if getattr(stream, "timeout", None) != read_timeout:
            stream.timeout = read_timeout
    size = min(MAX_SERIAL_CHUNK, max(1, stream.in_waiting))
    if deadline is not None and clock() >= deadline:
        return pending
    data = stream.read(size)
    received = clock() if capture is not None or deadline is not None else None
    if capture is not None:
        capture["bytes_read"] += len(data)
    if deadline is not None and received > deadline:
        if capture is not None:
            capture["late_read_bytes"] += len(data)
            capture["deadline_overruns"] += 1  # Empty late reads also violate the budget.
        return pending  # A driver overrun is reported, never accepted as in-budget evidence.
    decoded = data.decode("utf-8", "replace")
    if pending == _DISCARD_PARTIAL:
        # Drop an entire overlong partial line, not just its credential label.
        # Otherwise the next chunk could expose a secret suffix as a new line.
        if capture is not None:
            first_terminator = re.search(r"\r\n|\r|\n", decoded)
            capture["pending_truncated_chars"] += (
                len(decoded) if first_terminator is None else first_terminator.start())
        first_terminator = re.search(r"\r\n|\r|\n", decoded)
        if first_terminator is None:
            return _DISCARD_PARTIAL
        pending = ""
        decoded = decoded[first_terminator.end():]
    combined = pending + decoded
    # UART loggers may terminate with LF, CRLF, or CR. Preserve a trailing CR
    # across non-empty chunks so a CRLF split at the read boundary is one line
    # ending; an empty timed read proves it is a standalone CR terminator.
    hold_trailing_cr = bool(data) and combined.endswith("\r")
    parseable = combined[:-1] if hold_trailing_cr else combined
    normalized = re.sub(r"\r\n|\r|\n", "\n", parseable)
    fragments = normalized.split("\n")
    tail = fragments[-1] + ("\r" if hold_trailing_cr else "")
    host_time = (datetime.fromtimestamp((time.time if wall_clock is None else wall_clock)(),
                                      timezone.utc).isoformat()
                 if capture is not None else None)
    complete_lines = fragments[:-1] if len(fragments) > 1 else []
    for line in complete_lines:
        safe = "".join(c for c in line if 32 <= ord(c) < 127).strip()
        if re.search(r"HIL_(?:READY|STATE|OK|ERROR|FIXTURE)|GS117_TEST_ONLY|GS117_DEV_(?:REJOIN|TX|CALLBACK|RADIO|RX)|GS40T/1|PIR -> NodeRuntime|NodeMessage sent|Application ACK|authenticated|durable|CloudSync|COMMITTED|HubRuntime|HubSecurity|gs_hub_product|gs_hub_runtime|ESP-NOW|outbox|storage|mount|Wi-Fi|STA_START|firmware|image|boot:|ESP-ROM|rst:|panic|abort\(\)|Backtrace|app_init:|SPI\s+Flash(?:\s+Size)?\s*[:=]|esp_psram|octal_psram|spiram|assert failed:|Guru Meditation Error|Stack canary|stack overflow|\btask_wdt\b|Task watchdog|Tasks currently running|CPU\s+[0-9]+:|Power counters|BAT_SLEEP_(?:DECISION|ENTER|WAKE|RESTORE)|Light sleep stayed awake|^\s*(?:0x[0-9a-f]+[: ]+){2,}", safe, re.I):
            # Keep challenge nonce/public-key parsing compatible with bootstrap.
            # The existing bootstrap-evidence redactor removes those fields before persistence.
            safe = re.sub(r"(?i)(\b(?:credential|secret|private[_. -]?key|session[_. -]?key|installer[_. -]?code|wifi_psk|psk|password|token|authorization|ssid|certificate|payload|authentication|encrypted[_ -]?(?:envelope|config))\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)",
                          r"\1[REDACTED]", safe)
            if capture is not None:
                # Marker epochs are serial evidence boundaries, NOT a physical reset count.
                # Never infer a reset by comparing two boards' uptime clocks.
                if re.search(r"ESP-ROM:|rst:0x|boot: ESP-IDF", safe):
                    capture["boot_epoch"] += 1
                    if len(capture["boot_markers"]) < 16:
                        capture["boot_markers"].append({"boot_epoch": capture["boot_epoch"],
                            "host_received_at": host_time, "host_monotonic": received})
                    else:
                        capture["boot_markers_dropped"] += 1
                capture["truncated_chars"] += max(0, len(safe) - MAX_CAPTURE_CHARS)
            if len(lines) < MAX_CAPTURE_LINES:
                if capture is not None:
                    uptime = re.search(r"^[IWEVD]\s*\(([0-9]+)\)", safe)
                    capture["records"].append({"line_index": len(lines),
                        "host_received_at": host_time, "host_monotonic": received,
                        "target_uptime_ms": int(uptime[1]) if uptime else None,
                        "boot_epoch": capture["boot_epoch"]})
                lines.append(safe[:MAX_CAPTURE_CHARS])
            elif capture is not None:
                capture["dropped_lines"] += 1
        elif capture is not None:
            capture["filtered_lines"] += 1
    if capture is not None:
        capture["pending_truncated_chars"] += max(0, len(tail) - MAX_PENDING_CHARS)
    if len(tail) > MAX_PENDING_CHARS:
        return _DISCARD_PARTIAL
    return tail


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


def classify_radio_observation(c3_lines: list[str], s3_lines: list[str]) -> dict:
    """Classify only source-backed radio stages; never infer RF delivery from silence."""
    c3_hello_attempts = []
    c3_peer_ids = set()
    c3_local_send_stages = []
    for line in c3_lines:
        if "GS117_DEV_TX" not in line or not re.search(r"\bkind=6\b", line):
            continue
        stage_match = re.search(r"\bstage=([A-Za-z0-9_]+)", line)
        if stage_match and stage_match[1] not in {
                "callback_positive", "submitted_only"}:
            error = re.search(r"\berror=([A-Za-z0-9_]+)", line)
            c3_local_send_stages.append({
                "stage": stage_match[1], "error": error[1] if error else None})
        if re.search(r"\bsubmitted=1\b", line):
            actual = re.search(r"\bactual_ch=([0-9]+)\b", line)
            read = re.search(r"\bchannel_read=([A-Za-z0-9_]+)", line)
            peer = re.search(r"\bpeer=([0-9a-fA-F]{12})\b", line)
            channel = int(actual[1]) if actual and read and read[1] == "ESP_OK" else None
            c3_hello_attempts.append(channel)
            if peer:
                c3_peer_ids.add(peer[1].lower())

    s3_channels = set()
    s3_hub_ids = set()
    callback_hello = []
    queue_drop_hello = []
    queue_unavailable_hello = []
    owner_dequeued = set()
    s3_invalid_callback_count = 0
    s3_diagnostic_loss = 0
    owner_results = {}
    authenticated_rejoin = False
    for line in s3_lines:
        owner_ready = re.search(
            r"GS117_DEV_RADIO role=s3 state=owner_ready .*?hub_mac=([0-9a-fA-F]{12}) .*?channel=([0-9]+) read=ESP_OK",
            line)
        if owner_ready:
            s3_hub_ids.add(owner_ready[1].lower())
            s3_channels.add(int(owner_ready[2]))
        station_channel = re.search(r"WIFI_RADIO_CHANNEL channel=([0-9]+)", line)
        if station_channel:
            s3_channels.add(int(station_channel[1]))
        rx = re.search(
            r"GS117_DEV_RX role=s3 .*?boot_id=([0-9a-fA-F]+).*?rx_seq=([0-9]+).*?stage=([a-z_]+).*?rx_ch=([0-9]+).*?wire_kind=([0-9]+)",
            line)
        if rx and int(rx[5]) == 6:
            event = {"boot_id": rx[1].lower(), "rx_seq": int(rx[2]),
                     "stage": rx[3], "channel": int(rx[4])}
            if rx[3] == "callback_arrival":
                callback_hello.append(event)
            elif rx[3] == "security_queue_drop":
                queue_drop_hello.append(event)
            elif rx[3] == "security_queue_unavailable":
                queue_unavailable_hello.append(event)
        dequeued = re.search(
            r"GS117_DEV_RADIO role=s3 state=security_owner_dequeued .*?boot_id=([0-9a-fA-F]+).*?rx_seq=([0-9]+).*?wire_kind=([0-9]+)",
            line)
        if dequeued and int(dequeued[3]) == 6:
            owner_dequeued.add((dequeued[1].lower(), int(dequeued[2])))
        if "GS117_DEV_RX role=s3 state=diagnostic_loss" in line:
            lost = re.search(r"\bdropped=([0-9]+)", line)
            s3_diagnostic_loss += int(lost[1]) if lost else 1
        elif "GS117_DEV_RX role=s3" in line and any(
                f"stage={stage}" in line for stage in
                ("invalid_callback_input", "source_rejected", "unclassified_frame")):
            s3_invalid_callback_count += 1
        processed = re.search(
            r"GS117_DEV_RADIO role=s3 state=security_owner_processed .*?boot_id=([0-9a-fA-F]+).*?rx_seq=([0-9]+).*?wire_kind=([0-9]+).*?validation=([a-z_]+)",
            line)
        if processed and int(processed[3]) == 6:
            owner_results[(processed[1].lower(), int(processed[2]))] = processed[4]
        if "Authenticated rejoin device=" in line:
            authenticated_rejoin = True

    for event in callback_hello:
        key = (event["boot_id"], event["rx_seq"])
        event["owner_dequeued"] = key in owner_dequeued
        event["owner_result"] = owner_results.get((event["boot_id"], event["rx_seq"]))

    valid_c3_channels = {channel for channel in c3_hello_attempts if channel is not None}
    identity_match = bool(c3_peer_ids & s3_hub_ids)
    if authenticated_rejoin:
        status = "AUTHENTICATED_REJOIN"
    elif any(event["owner_result"] == "hello_authenticated_challenge_ready"
             for event in callback_hello):
        status = "S3_AUTHENTICATED_HELLO_CHALLENGE_READY"
    elif any(event["owner_result"] == "no_response_unclassified"
             for event in callback_hello):
        status = "INCONCLUSIVE_S3_OWNER_PROCESSED_NO_RESPONSE"
    elif queue_drop_hello:
        status = "S3_SECURITY_CALLBACK_QUEUE_DROP_OBSERVED"
    elif queue_unavailable_hello:
        status = "S3_SECURITY_QUEUE_UNAVAILABLE_OBSERVED"
    elif any(event["owner_dequeued"] and event["owner_result"] is None
             for event in callback_hello):
        status = "INCONCLUSIVE_S3_OWNER_DEQUEUED_PROCESSING_RESULT_NOT_OBSERVED"
    elif any(not event["owner_dequeued"] and event["owner_result"] is None
             for event in callback_hello):
        status = "INCONCLUSIVE_S3_CALLBACK_OWNER_DEQUEUE_NOT_OBSERVED"
    elif callback_hello:
        status = "INCONCLUSIVE_S3_HELLO_CALLBACK_OWNER_RESULT_NOT_OBSERVED"
    elif any(item["stage"] in {"peer_add", "esp_now_submit", "channel_set"}
             for item in c3_local_send_stages):
        status = "C3_LOCAL_RADIO_OPERATION_FAILURE_OBSERVED"
    elif s3_diagnostic_loss:
        status = "INCONCLUSIVE_S3_DIAGNOSTIC_TELEMETRY_LOSS"
    elif not c3_hello_attempts:
        status = "INCONCLUSIVE_NO_C3_HELLO_SUBMISSION_OBSERVED"
    elif not valid_c3_channels:
        status = "INCONCLUSIVE_C3_CHANNEL_READBACK_UNAVAILABLE"
    elif not s3_channels:
        status = "INCONCLUSIVE_S3_CHANNEL_UNVERIFIED"
    elif not (valid_c3_channels & s3_channels):
        status = "INCONCLUSIVE_NO_CONFIRMED_CHANNEL_OVERLAP"
    else:
        status = "INCONCLUSIVE_CHANNEL_MATCH_NOT_TIME_CORRELATED"

    return {
        "status": status,
        "c3_rejoin_hello_submissions": len(c3_hello_attempts),
        "c3_local_send_stages": c3_local_send_stages[:32],
        "c3_actual_channels": sorted(valid_c3_channels),
        "s3_observed_channels": sorted(s3_channels),
        "c3_peer_matches_s3_hub": identity_match,
        "s3_hello_callback_count": len(callback_hello),
        "s3_hello_queue_drop_count": len(queue_drop_hello),
        "s3_hello_queue_unavailable_count": len(queue_unavailable_hello),
        "s3_hello_owner_dequeued_count": sum(
            1 for event in callback_hello if event["owner_dequeued"]),
        "s3_invalid_or_unclassified_callback_count": s3_invalid_callback_count,
        "s3_diagnostic_loss_count": s3_diagnostic_loss,
        "s3_owner_results": [event["owner_result"] for event in callback_hello],
        "s3_owner_dequeued": [event["owner_dequeued"] for event in callback_hello],
        "cross_device_time_correlation": "not_available",
        "radio_failure_inferred": False if status.startswith("INCONCLUSIVE") else None,
    }


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
            fixture_exchange=None, wall_clock=None) -> dict:
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
    observation_limit = 90 if config.get("profile") == "GS117_DEV_TEST_ONLY" else 60
    if type(observation_seconds) is not int or not 10 <= observation_seconds <= observation_limit:
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
    c3_lines, s3_lines = [], []
    captures = {"c3": capture_state(), "s3": capture_state()}
    c3_tail = s3_tail = ""
    timing = {"observation_budget_ms": observation_seconds * 1000,
              "clock": "host_monotonic", "termination_reason": "not_started"}
    observation_started = None
    deadline = None
    bootstrap_evidence = {}
    bootstrap_exchange_ms = None
    bootstrap_tx_bytes = None
    c3_status_queries = 0
    s3_config_receive_pending = s3_status_command_ready = s3_status_command_sent = False

    def snapshot():
        # Finalize already-read buffers without further UART sampling. Do not
        # retain an incomplete credential-bearing line or hide its omission.
        for board, tail in (("c3", c3_tail), ("s3", s3_tail)):
            captures[board]["unterminated_tail_chars"] = (
                0 if tail == _DISCARD_PARTIAL else len(tail))
        return {"c3": c3_lines, "s3": s3_lines, "serial_capture": captures,
                "phase_timing": timing, "c3_status_queries": c3_status_queries,
                "radio_diagnostic": classify_radio_observation(c3_lines, s3_lines),
                "s3_config_receive_pending": s3_config_receive_pending,
                "s3_status_command_ready": s3_status_command_ready,
                "s3_status_command_sent": s3_status_command_sent}

    try:
        for board in (s3, c3):
            stream = serial_factory()
            stream.port = board["port"]
            stream.baudrate = 115200
            stream.timeout = 0.1
            stream.write_timeout = 1
            stream.dtr = False
            stream.rts = False
            streams.append(stream)
            stream.open()
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
        # The approved observation starts here, AFTER separately permitted reset
        # and bootstrap. Every read/query/drain shares this one absolute budget.
        observation_started = clock()
        deadline = observation_started + observation_seconds
        timing.update({"bootstrap_elapsed_ms": bootstrap_exchange_ms or 0,
                       "observation_start_monotonic": observation_started,
                       "observation_deadline_monotonic": deadline,
                       "termination_reason": "running"})
        c3_tail = s3_tail = ""

        def sample_pair():
            nonlocal c3_tail, s3_tail
            c3_tail = collect(c3_stream, c3_tail, c3_lines, capture=captures["c3"],
                              deadline=deadline, clock=clock, wall_clock=wall_clock)
            s3_tail = collect(s3_stream, s3_tail, s3_lines, capture=captures["s3"],
                              deadline=deadline, clock=clock, wall_clock=wall_clock)
            if any(value["deadline_overruns"] for value in captures.values()):
                raise ValueError("TC001_SERIAL_READ_EXCEEDED_OBSERVATION_DEADLINE")
            readiness_guard(config, c3_lines, s3_lines)

        def query(stream, command):
            remaining = deadline - clock()
            if remaining <= OBSERVATION_IO_MARGIN_SECONDS:
                return False
            stream.write_timeout = min(1.0, remaining - OBSERVATION_IO_MARGIN_SECONDS)
            written = stream.write(command)
            # write_timeout bounds this operation. flush() can wait indefinitely
            # on a Windows driver and is not part of a bounded observation.
            if written is not None and written != len(command):
                raise ValueError("TC001_STATUS_WRITE_INCOMPLETE")
            if clock() > deadline:
                raise ValueError("TC001_SERIAL_WRITE_EXCEEDED_OBSERVATION_DEADLINE")
            return True

        warmup_deadline = min(deadline, observation_started + 4)
        while clock() < warmup_deadline:
            sample_pair()
            sleep(max(0, min(0.02, warmup_deadline - clock())))
        if query(c3_stream, b"GET_STATE\n"):
            c3_status_queries += 1
        s3_config_receive_pending = any("GS40T/1 CHALLENGE" in line for line in s3_lines)
        s3_status_command_ready = any(
            "HIL_FIXTURE_READY" in line and "FIXTURE_STATUS" in line for line in s3_lines)
        if query_s3_status and s3_status_command_ready and not s3_config_receive_pending:
            s3_status_command_sent = query(s3_stream, b"FIXTURE_STATUS\n")
        next_c3_status = (clock() + c3_status_interval_seconds
                          if c3_status_interval_seconds else None)
        while clock() < deadline:
            sample_pair()
            if next_c3_status is not None and clock() >= next_c3_status:
                if query(c3_stream, b"GET_STATE\n"):
                    c3_status_queries += 1
                next_c3_status = clock() + c3_status_interval_seconds
            sleep(max(0, min(0.02, deadline - clock())))
        timing.update({"observation_end_monotonic": clock(),
                       "observation_elapsed_ms": (clock() - observation_started) * 1000,
                       "remaining_ms": max(0, (deadline - clock()) * 1000),
                       "termination_reason": "deadline"})
        result = snapshot()
        if not any("HIL_STATE role=c3" in line for line in c3_lines):
            raise ValueError("TC001_INSTALLED_C3_HIL_STATUS_NOT_OBSERVED")
        if any(value[key] for value in captures.values() for key in (
                "dropped_lines", "truncated_chars", "pending_truncated_chars",
                "boot_markers_dropped", "unterminated_tail_chars")):
            # A bounded capture is allowed to lose data, but never to masquerade
            # as complete readiness evidence. Preserve its counters/partial data.
            raise ValueError("TC001_DIAGNOSTIC_CAPTURE_INCOMPLETE")
        if any("GS117_DEV_RX role=s3 state=diagnostic_loss" in line for line in s3_lines):
            error = ValueError("TC001_S3_DIAGNOSTIC_CAPTURE_INCOMPLETE")
            error.captured_observation = snapshot()
            raise error
        if fixture_exchange is not None:
            # Legacy explicit commissioning is a distinct separately approved
            # phase, never used by the GS117 Bootstrap readiness procedure.
            result["commissioning"] = fixture_exchange(c3_stream, s3_stream,
                c3_lines, s3_lines, clock=clock, sleep=sleep,
                expected_public_key=config.get("expected_node_public_key"))
        if bootstrap_tx_bytes is not None:
            result["bootstrap_host_write_bytes"] = bootstrap_tx_bytes
            result["bootstrap_exchange_ms"] = bootstrap_exchange_ms
            result["bootstrap_timeline"] = bootstrap_evidence
        # No further serial collection after the observation deadline, including
        # bootstrap's former unconditional ten-second drain.
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
    except BaseException as error:
        if observation_started is not None:
            timing.update({"observation_end_monotonic": clock(),
                           "observation_elapsed_ms": (clock() - observation_started) * 1000,
                           "remaining_ms": max(0, (deadline - clock()) * 1000),
                           "termination_reason": (str(error) if isinstance(error, ValueError) and
                               re.fullmatch(r"[A-Z0-9_]{1,160}", str(error)) else
                               type(error).__name__)})
        partial = getattr(error, "captured_observation", {})
        error.captured_observation = {**snapshot(), **partial}
        raise
    finally:
        cleanup_start = clock()
        errors = 0
        original_error = sys.exc_info()[1]
        for stream in reversed(streams):
            try:
                if stream.is_open:
                    stream.close()
            except BaseException:
                errors += 1  # Close the other handle even if one driver fails.
        timing["cleanup_elapsed_ms"] = (clock() - cleanup_start) * 1000
        timing["cleanup_errors"] = errors
        if errors and original_error is None:
            error = ValueError("TC001_SERIAL_CLEANUP_FAILED")
            error.captured_observation = snapshot()
            raise error



def bootstrap_s3(config, *, serial_factory=None, port_finder=None,
                 exchange=None, clock=None, boot_reset=None):
    """One S3-only GS40 exchange; no reset, commissioning or C3 access."""
    if (config.get("profile") != "GS117_DEV_TEST_ONLY" or
            config.get("home_id") != "gs177-test-product" or
            config.get("hub_id") != "hub-e072a1d38d34" or
            config.get("s3_boot_reset", False) is not False or
            config.get("c3_boot_reset", False) is not False or "c3" in config):
        raise ValueError("TC001_S3_ONLY_BOOTSTRAP_SCOPE_INVALID")
    board = config.get("s3", {})
    finder = ports if port_finder is None else port_finder
    if (board.get("port") != "COM10" or
            board.get("serial_number") != "E0:72:A1:D3:8D:34" or
            not exact_port(board, finder())):
        raise ValueError("TC001_VERIFIED_USB_INTERFACE_MISMATCH")
    duration = config.get("observation_seconds", 90)
    if type(duration) is not int or not 10 <= duration <= 90:
        raise ValueError("TC001_OBSERVATION_SECONDS_OUT_OF_RANGE")
    factory = serial.Serial if serial_factory is None else serial_factory
    clock = time.monotonic if clock is None else clock
    stream = factory()
    stream.port = "COM10"; stream.baudrate = 115200
    stream.timeout = .1; stream.write_timeout = 1
    stream.dtr = False; stream.rts = False
    evidence = {}; lines = []; capture = capture_state(); pending = ""
    try:
        stream.open()
        if boot_reset is not None:
            stream.reset_input_buffer()
            boot_reset(stream)
        # Existing primitive verifies nonce, framing, expiry/restart and identity
        # immediately before its single configuration write.
        written = (bootstrap_config if exchange is None else exchange)(
            stream, require_boot=boot_reset is not None, challenge_timeout_seconds=75,
            evidence=evidence, identity_check=lambda: exact_port(board, finder()))
        deadline = clock() + duration
        while clock() < deadline:
            pending = collect(stream, pending, lines, capture=capture,
                              deadline=deadline, clock=clock)
        return {"stage": "OBSERVATION", "s3": lines, "c3": [],
                "bootstrap_host_write_bytes": written,
                "bootstrap_timeline": evidence, "serial_capture": {"s3": capture},
                "c3_opened": False, "intentional_reset": boot_reset is not None}
    except BaseException as error:
        error.captured_observation = {"s3": lines, "c3": [],
            "bootstrap_timeline": evidence, "serial_capture": {"s3": capture}}
        raise
    finally:
        if stream.is_open: stream.close()


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
    lines=[];pending='';capture=capture_state();writes=[]
    try:
        stream.open();deadline=time.monotonic()+duration;query=0
        while time.monotonic()<deadline:
            pending=collect(stream,pending,lines,capture=capture,deadline=deadline)
            readiness_guard({'stop_on_readiness_error':True},lines,[])
            if time.monotonic()>=query:
                command=b'GET_STATE\n'
                write_started_at=datetime.now(timezone.utc).isoformat()
                written=stream.write(command)
                stream.flush()
                write_completed_at=datetime.now(timezone.utc).isoformat()
                writes.append({'command':'GET_STATE','requested_bytes':len(command),
                               'host_accepted_bytes':written,
                               'host_write_started_at':write_started_at,
                               'host_write_completed_at':write_completed_at,
                               'host_write_completed_monotonic':time.monotonic()})
                if written != len(command):
                    raise ValueError('TC001_GET_STATE_HOST_WRITE_INCOMPLETE')
                query=time.monotonic()+GET_STATE_QUERY_INTERVAL_SECONDS
            time.sleep(.02)
        capture['unterminated_tail_chars']=(0 if pending==_DISCARD_PARTIAL else len(pending))
        return {'c3':lines,'serial_capture':{'c3':capture},
                'host_write_receipts':writes,
                'get_state_ack_count':sum('HIL_OK command=GET_STATE' in line for line in lines),
                's3_serial_opened':False,'motion_injection':False}
    except BaseException as error:
        capture['unterminated_tail_chars']=(0 if pending==_DISCARD_PARTIAL else len(pending))
        error.captured_observation={'c3':lines,'serial_capture':{'c3':capture},
                                    'host_write_receipts':writes,
                                    's3_serial_opened':False,'motion_injection':False}
        raise
    finally:
        if stream.is_open:stream.close()


def c3_hil_readiness_evidence(lines: list[str], *, get_state_commands_sent: int,
                              observation_elapsed_ms: int, capture: dict,
                              guard_ready: bool, get_state_ack_received: bool,
                              host_write_receipts: list[dict] | None = None,
                              host_write_status: str = "COMPLETE") -> dict:
    """Return a small, credential-free explanation of the existing C3 guard."""
    state_lines = [line for line in lines if "HIL_STATE role=c3" in line]
    state_line = state_lines[-1] if state_lines else ""
    field_types = {
        "power_mode": "word", "hil_build": "flag", "hil_control": "flag",
        "physical_wake": "flag", "runtime_live": "counter",
        "sensing_live": "counter", "pending_inject": "counter",
        "retained": "counter", "in_flight": "counter",
    }
    values: dict[str, object] = {}
    missing_fields: list[str] = []
    malformed_fields: list[str] = []
    for name, value_type in field_types.items():
        match = re.search(rf"(?:^|\s){re.escape(name)}=([^\s]*)", state_line)
        if not match:
            if state_line and re.search(rf"\b{re.escape(name)}\s*=", state_line):
                malformed_fields.append(name)
                values[name] = "MALFORMED"
            else:
                missing_fields.append(name)
                values[name] = None
            continue
        raw = match[1]
        if value_type == "word" and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", raw):
            values[name] = raw
        elif value_type == "flag" and raw in {"0", "1"}:
            values[name] = int(raw)
        elif value_type == "counter" and re.fullmatch(r"[0-9]{1,20}", raw):
            values[name] = int(raw)
        else:
            malformed_fields.append(name)
            values[name] = "MALFORMED"

    ack_count = sum("HIL_OK command=GET_STATE" in line for line in lines)
    runtime_live = re.search(r"\bruntime_live=([0-9]+)\b", state_line)
    sensing_live = re.search(r"\bsensing_live=([0-9]+)\b", state_line)
    pending_inject = re.search(r"\bpending_inject=([0-9]+)\b", state_line)
    retained = re.search(r"\bretained=([0-9]+)\b", state_line)
    in_flight = re.search(r"\bin_flight=([0-9]+)\b", state_line)
    predicates = {
        "c3_state_received": bool(state_line),
        # Keep these textual checks identical to the production guard.
        "power_mode_is_HIL_AWAKE_TEST_ONLY": "power_mode=HIL_AWAKE_TEST_ONLY" in state_line,
        "hil_build_is_0": "hil_build=0" in state_line,
        "hil_control_is_1": "hil_control=1" in state_line,
        "physical_wake_is_0": "physical_wake=0" in state_line,
        "runtime_live_gt_0": bool(runtime_live) and int(runtime_live[1]) > 0,
        "sensing_live_gt_0": bool(sensing_live) and int(sensing_live[1]) > 0,
        "pending_inject_is_0": bool(pending_inject) and int(pending_inject[1]) == 0,
        "retained_is_0": bool(retained) and int(retained[1]) == 0,
        "in_flight_is_0": bool(in_flight) and int(in_flight[1]) == 0,
        "get_state_ack_received": get_state_ack_received,
    }
    failed = [name for name, passed in predicates.items() if not passed]
    if not state_line:
        response_status = "STATE_ABSENT"
    elif malformed_fields:
        response_status = "STATE_MALFORMED"
    elif missing_fields:
        response_status = "STATE_INCOMPLETE"
    elif not guard_ready:
        response_status = "STATE_REPORTED_NOT_READY"
    elif not get_state_ack_received:
        response_status = "GET_STATE_ACK_MISSING"
    else:
        response_status = "READY"

    startup_markers = (
        "ESP-ROM:", "rst:", "boot: ESP-IDF", "boot: Loaded app from partition",
        "app_init: App version:", "app_init: ELF file SHA256:",
        "Guru Meditation Error", "Task watchdog", "abort() was called",
        "assert failed:", "Stack canary", "Stack overflow",
    )
    startup = [line[:512] for line in lines
               if any(marker.casefold() in line.casefold() for marker in startup_markers)]
    record_by_line = {row.get("line_index"): row for row in capture.get("records", [])
                       if isinstance(row, dict)}
    response_pattern = re.compile(
        r"HIL_(?:STATE|OK|ERROR)|Power counters|BAT_SLEEP_(?:DECISION|ENTER|WAKE|RESTORE)|"
        r"Light sleep stayed awake|ESP-ROM:|rst:|boot: ESP-IDF|app_init: App version:|"
        r"app_init: ELF file SHA256:", re.I)
    candidates = [(index, line) for index, line in enumerate(lines)
                  if response_pattern.search(line)]
    selected_indices = []
    priority_patterns = (
        re.compile(r"ESP-ROM:|rst:|boot: ESP-IDF|app_init: App version:|app_init: ELF file SHA256:", re.I),
        re.compile(r"Power counters", re.I),
        re.compile(r"BAT_SLEEP_(?:DECISION|ENTER|WAKE|RESTORE)|Light sleep stayed awake", re.I),
        re.compile(r"HIL_ERROR", re.I),
        re.compile(r"HIL_STATE", re.I),
        re.compile(r"HIL_OK command=GET_STATE", re.I),
    )
    for pattern in priority_patterns:
        matching = [index for index, line in candidates if pattern.search(line)]
        for index in (matching[:1] + matching[-1:]):
            if index not in selected_indices:
                selected_indices.append(index)
    for index, _line in reversed(candidates):
        if len(selected_indices) >= 16:
            break
        if index not in selected_indices:
            selected_indices.append(index)
    selected_indices = selected_indices[:16]
    response_evidence = []
    for index in selected_indices:
        line = lines[index]
        response_evidence.append({
            **{key: record_by_line[index].get(key) for key in (
                "host_received_at", "host_monotonic", "target_uptime_ms", "boot_epoch")
               if index in record_by_line},
            "line": line[:384],
        })
    return {
        "schema": "GS117_C3_HIL_READINESS_V1",
        "response_status": response_status,
        "state_line_count": len(state_lines),
        "state_received": bool(state_line),
        "values": values,
        "missing_fields": missing_fields,
        "malformed_fields": malformed_fields,
        "get_state_commands_sent": get_state_commands_sent,
        "get_state_ack_count": ack_count,
        "get_state_ack_received": get_state_ack_received,
        "host_write_status": host_write_status,
        "host_write_receipts": (host_write_receipts or [])[-15:],
        "response_evidence": response_evidence,
        "response_evidence_omitted": max(0, len(candidates) - len(response_evidence)),
        "existing_guard_ready": guard_ready,
        "guard_predicates": predicates,
        "failed_predicates": failed,
        "observation_budget_ms": 30000,
        "observation_elapsed_ms": observation_elapsed_ms,
        "collection_respected_deadline": capture["deadline_overruns"] == 0,
        "capture": {key: capture[key] for key in (
            "bytes_read", "filtered_lines", "dropped_lines", "truncated_chars",
            "pending_truncated_chars", "late_read_bytes", "deadline_overruns",
            "unterminated_tail_chars")},
        "captured_line_count": min(len(lines), MAX_CAPTURE_LINES),
        "line_limit_reached": len(lines) >= MAX_CAPTURE_LINES,
        "startup_evidence": startup[-8:],
        "startup_evidence_omitted": max(0, len(startup) - 8),
        "raw_state_line_retained": False,
    }


def run(config: dict, *, monotonic=None) -> dict:
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
    readiness_capture = capture_state()
    host_write_receipts: list[dict] = []
    get_state_commands_sent = 0
    clock = time.monotonic if monotonic is None else monotonic
    try:
        c3_stream.open()
        readiness_started = clock()
        deadline = readiness_started + 30
        next_query = readiness_started + GET_STATE_QUERY_INTERVAL_SECONDS
        mode_line = ""
        ready = False
        get_state_ack_received = False

        def send_get_state(host_write_started_monotonic: float) -> None:
            nonlocal get_state_commands_sent
            command = b"GET_STATE\n"
            receipt = {
                "command": "GET_STATE", "requested_bytes": len(command),
                "host_write_started_at": datetime.now(timezone.utc).isoformat(),
                "host_write_started_monotonic": host_write_started_monotonic,
            }
            written = None
            try:
                written = c3_stream.write(command)
                c3_stream.flush()
            except BaseException as error:
                receipt.update({"host_accepted_bytes": written,
                                "status": "HOST_WRITE_ERROR",
                                "error_type": type(error).__name__,
                                "host_write_completed_at": datetime.now(timezone.utc).isoformat()})
                host_write_receipts.append(receipt)
                elapsed = max(0, int((host_write_started_monotonic - readiness_started) * 1000))
                evidence = c3_hil_readiness_evidence(
                    c3_lines, get_state_commands_sent=get_state_commands_sent,
                    observation_elapsed_ms=elapsed, capture=readiness_capture,
                    guard_ready=False, get_state_ack_received=False,
                    host_write_receipts=host_write_receipts,
                    host_write_status="HOST_WRITE_ERROR")
                failure = ValueError("TC001_GET_STATE_HOST_WRITE_FAILED")
                failure.captured_observation = evidence
                raise failure from None
            receipt.update({"host_accepted_bytes": written,
                            "host_write_completed_at": datetime.now(timezone.utc).isoformat(),
                            "status": "COMPLETE" if written == len(command) else "SHORT_WRITE"})
            host_write_receipts.append(receipt)
            if written != len(command):
                elapsed = max(0, int((host_write_started_monotonic - readiness_started) * 1000))
                evidence = c3_hil_readiness_evidence(
                    c3_lines, get_state_commands_sent=get_state_commands_sent,
                    observation_elapsed_ms=elapsed, capture=readiness_capture,
                    guard_ready=False, get_state_ack_received=False,
                    host_write_receipts=host_write_receipts,
                    host_write_status="SHORT_WRITE")
                failure = ValueError("TC001_GET_STATE_HOST_WRITE_INCOMPLETE")
                failure.captured_observation = evidence
                raise failure
            get_state_commands_sent += 1

        # COM4 can expose a partial console frame immediately after open. Drain
        # bounded startup output until the line has been quiet before sending
        # the first command; never send motion while startup output is arriving.
        preflight_started = clock()
        quiet_since = preflight_started
        preflight_limit = min(deadline, preflight_started + 2.0)
        while clock() < preflight_limit:
            bytes_before = readiness_capture["bytes_read"]
            c3_tail = collect(
                c3_stream, c3_tail, c3_lines,
                capture=readiness_capture, deadline=deadline, clock=clock)
            if readiness_capture["bytes_read"] > bytes_before:
                quiet_since = clock()
            elif clock() - quiet_since >= 0.25:
                break
            if any("HIL_OK command=INJECT_MOTION" in line or
                   "PIR -> NodeRuntime" in line for line in c3_lines):
                failure = ValueError("TC001_UNSOLICITED_C3_EVENT_BEFORE_INJECTION")
                failure.captured_observation = c3_hil_readiness_evidence(
                    c3_lines, get_state_commands_sent=get_state_commands_sent,
                    observation_elapsed_ms=max(0, int((clock() - readiness_started) * 1000)),
                    capture=readiness_capture, guard_ready=False,
                    get_state_ack_received=False, host_write_receipts=host_write_receipts,
                    host_write_status="UNSOLICITED_EVENT_BEFORE_READINESS")
                raise failure
            if clock() < preflight_limit:
                time.sleep(min(0.02, preflight_limit - clock()))
        if clock() - quiet_since < 0.25:
            failure = ValueError("TC001_C3_SERIAL_STARTUP_NOT_QUIET")
            failure.captured_observation = c3_hil_readiness_evidence(
                c3_lines, get_state_commands_sent=get_state_commands_sent,
                observation_elapsed_ms=max(0, int((clock() - readiness_started) * 1000)),
                capture=readiness_capture, guard_ready=False,
                get_state_ack_received=False, host_write_receipts=host_write_receipts,
                host_write_status="SERIAL_STARTUP_NOT_QUIET")
            raise failure
        send_get_state(clock())
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines,
                              capture=readiness_capture, deadline=deadline, clock=clock)
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
            get_state_ack_received = any(
                "HIL_OK command=GET_STATE" in line for line in c3_lines)
            if ready and get_state_ack_received:
                break
            now = clock()
            if now >= deadline:
                break
            if now >= next_query:
                send_get_state(now)
                next_query = clock() + GET_STATE_QUERY_INTERVAL_SECONDS
        observation_elapsed_ms = max(0, int((clock() - readiness_started) * 1000))
        readiness_evidence = c3_hil_readiness_evidence(
            c3_lines, get_state_commands_sent=get_state_commands_sent,
            observation_elapsed_ms=observation_elapsed_ms,
            capture=readiness_capture, guard_ready=bool(ready),
            get_state_ack_received=get_state_ack_received,
            host_write_receipts=host_write_receipts)
        if not (ready and get_state_ack_received):
            error = ValueError("TC001_INSTALLED_C3_HIL_MODE_UNVERIFIED")
            error.captured_observation = readiness_evidence
            raise error
        c3_state = mode_line
        runtime_value, sensing_value = int(live[1]), int(sensing[1])
        # Drain already buffered runtime diagnostics before the single HIL
        # trigger so pre-existing or ambient events cannot be correlated as
        # this run's stimulus.
        drain_deadline = clock() + 0.3
        while clock() < drain_deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines, clock=clock)
        c3_lines = []
        c3_tail = ""
        c3_stream.write(b"INJECT_MOTION\n")
        c3_stream.flush()
        command_sent_at = clock()
        deadline = clock() + 35
        while clock() < deadline:
            c3_tail = collect(c3_stream, c3_tail, c3_lines, clock=clock)
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
                "event_wait_ms": int((clock() - command_sent_at) * 1000),
                "c3_readiness": readiness_evidence}
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
    capture_retries = 0
    while True:
        for navigation_attempt in range(4):
            sleep(0.25)
            root, raw = ui_dump(adb, serial_number)
            joined = "\n".join(ui_texts(root))
            trusted_home_markers = [text for text in ui_texts(root)
                                    if "AUTHENTICATED_GS148_TEST_ONLY" in text]
            marker_homes = {match for text in trusted_home_markers
                            for match in re.findall(r"\bgs177-test-[a-z0-9-]+\b", text)}
            if marker_homes and home_id not in marker_homes:
                raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_REFRESH")
            if "Latest recorded events" not in joined or home_id not in joined:
                if navigation_attempt == 3:
                    raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_REFRESH")
                # The foreground refresh can briefly expose a stale/empty
                # WebView tree. Wait within the existing bounded navigation
                # window; a positively identified different Home still fails
                # immediately above.
                continue
            try:
                viewport = reports_scroll_region(root)
                break
            except ValueError as error:
                # Visibility refresh may expose the Reports body before its
                # tab becomes interactive. Wait for the same strict guard;
                # never swipe or accept a key using an unverified viewport.
                if (str(error) != "TC001_ANDROID_REPORTS_TAB_NOT_CONFIRMED_FOR_SCROLL" or
                        navigation_attempt == 3):
                    raise
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
            before_capture_sha256 = hashlib.sha256(raw).hexdigest()
            screenshot = call(adb, serial_number, "exec-out", "screencap", "-p",
                              timeout_seconds=12)
            if (not screenshot.startswith(b"\x89PNG\r\n\x1a\n") or
                    len(screenshot) > 8 * 1024 * 1024):
                raise ValueError("TC001_ANDROID_SCREENSHOT_CAPTURE_INVALID")
            confirmed_root, confirmed_raw = ui_dump(adb, serial_number)
            confirmed_text = "\n".join(ui_texts(confirmed_root))
            if "Latest recorded events" not in confirmed_text or home_id not in confirmed_text:
                trusted_home_markers = [text for text in ui_texts(confirmed_root)
                                        if "AUTHENTICATED_GS148_TEST_ONLY" in text]
                marker_homes = {match for text in trusted_home_markers
                                for match in re.findall(r"\bgs177-test-[a-z0-9-]+\b", text)}
                if marker_homes and home_id not in marker_homes:
                    raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_CAPTURE")
                capture_retries += 1
                if capture_retries >= 3:
                    raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_CAPTURE")
                # Do not accept a transient refresh tree as evidence. Re-find
                # the exact record and capture it again within the existing
                # three-attempt evidence bound.
                continue
            confirmed_viewport = reports_scroll_region(confirmed_root)
            still_visible = (exact_decision_in_ui(confirmed_root, expected_decision,
                                visible_bounds=confirmed_viewport) if decision_mode else
                             exact_key_in_ui(confirmed_root, expected_key,
                                visible_bounds=confirmed_viewport))
            if not still_visible:
                capture_retries += 1
                if capture_retries >= 3:
                    raise ValueError("TC001_ANDROID_OUTCOME_CHANGED_DURING_EVIDENCE_CAPTURE")
                continue
            raw = confirmed_raw
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
                    "capture_retries": capture_retries,
                    "ui_before_capture_sha256": before_capture_sha256,
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
        reports_navigation_confirmed = False
        for poll_attempt in range(ANDROID_REPORTS_SCROLL_POLL_ATTEMPTS):
            sleep(0.25)
            next_root, next_raw = ui_dump(adb, serial_number)
            next_joined = "\n".join(ui_texts(next_root))
            if ("Latest recorded events" not in next_joined or home_id not in next_joined):
                raise ValueError("TC001_ANDROID_REPORTS_HOME_CHANGED_DURING_SCROLL")
            try:
                next_viewport = reports_scroll_region(next_root)
            except ValueError as error:
                if (str(error) != "TC001_ANDROID_REPORTS_TAB_NOT_CONFIRMED_FOR_SCROLL" or
                        poll_attempt + 1 >= ANDROID_REPORTS_SCROLL_POLL_ATTEMPTS):
                    raise
                # A real WebView can publish its scrolled body before the
                # fixed navigation buttons reappear in the accessibility tree.
                # Keep polling within the existing bound; never inspect or
                # accept a key until the strict Reports viewport is present.
                root, raw = next_root, next_raw
                continue
            reports_navigation_confirmed = True
            root, raw, viewport = next_root, next_raw, next_viewport
            if reports_page_fingerprint(root, viewport) != before:
                advanced = True
                stalled_swipes = 0
                break
        if not reports_navigation_confirmed:
            raise ValueError("TC001_ANDROID_REPORTS_TAB_NOT_CONFIRMED_FOR_SCROLL")
        if not advanced:
            stalled_swipes += 1
            if stalled_swipes >= ANDROID_REPORTS_END_NO_PROGRESS:
                if decision_mode:
                    raise ValueError("TC001_EXACT_HUB_DECISION_NOT_VISIBLE_IN_ANDROID_REPORTS")
                raise ValueError("TC001_EXACT_EVENT_KEY_NOT_VISIBLE_IN_ANDROID_EVENT_DETAILS")


def bind_s3_update_artifact(artifact, expected_sha256, evidence_parent, session_id,
                           target=None, partition_contract=None):
    """Bind an explicit reviewed image to fresh, private session evidence.

    This is preparation only: admission, live-device validation, and all write
    guards remain the responsibility of the existing update operation.
    """
    artifact = Path(artifact)
    parent = Path(evidence_parent)
    if (not artifact.is_absolute() or artifact.is_symlink() or not artifact.is_file() or
            not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or "")):
        raise ValueError('s3_update_artifact_binding_invalid')
    if (not parent.is_absolute() or parent.is_symlink() or not parent.is_dir() or
            not re.fullmatch(r"[0-9a-f]{32}", session_id or "")):
        raise ValueError('s3_update_evidence_binding_invalid')
    target = dict(S3_UPDATE_TARGET if target is None else target)
    if (target != S3_UPDATE_TARGET or
            partition_contract not in (None, S3_UPDATE_PARTITION_CONTRACT)):
        raise ValueError('s3_update_registered_target_or_partition_contract_invalid')
    image = artifact.read_bytes()
    if hashlib.sha256(image).hexdigest() != expected_sha256:
        raise ValueError('s3_update_artifact_digest_mismatch')
    if (len(image) < 256 or len(image) > 0x400000 or image[0] != 0xe9 or
            int.from_bytes(image[12:14], 'little') != 9 or
            int.from_bytes(image[32:36], 'little') != 0xabcd5432):
        raise ValueError('s3_update_application_image_incompatible')
    evidence = parent / ('s3-app-update-' + session_id)
    evidence.mkdir(mode=0o700, exist_ok=False)
    # Snapshot the exact selected bytes so subsequent path replacement cannot
    # change which image the session writes. Historical evidence is untouched.
    snapshot = evidence / 'application.bin'
    with snapshot.open('xb') as stream:
        stream.write(image)
    manifest = {'session_id': session_id, 'source_path': str(artifact.resolve()),
                'application_sha256': expected_sha256, 'size': len(image),
                'target': target, 'partition_contract': S3_UPDATE_PARTITION_CONTRACT}
    with (evidence / 'artifact-binding.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, sort_keys=True)
    return evidence, snapshot, manifest


def verify_s3_update_binding(evidence, session_id, expected_sha256, target=None,
                             partition_contract=None):
    """Revalidate the writer's session-bound snapshot before a hardware write."""
    evidence = Path(evidence)
    if (evidence.is_symlink() or not evidence.is_dir() or
            not re.fullmatch(r'[0-9a-f]{32}', session_id or '') or
            evidence.name != 's3-app-update-' + session_id):
        raise ValueError('s3_update_evidence_binding_invalid')
    manifest_path = evidence / 'artifact-binding.json'
    snapshot = evidence / 'application.bin'
    if manifest_path.is_symlink() or snapshot.is_symlink():
        raise ValueError('s3_update_evidence_binding_invalid')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        image = snapshot.read_bytes()
    except (OSError, ValueError) as error:
        raise ValueError('s3_update_evidence_binding_invalid') from error
    expected_target = dict(S3_UPDATE_TARGET if target is None else target)
    expected_contract = partition_contract or S3_UPDATE_PARTITION_CONTRACT
    expected = {'session_id': session_id, 'application_sha256': expected_sha256,
                'target': expected_target, 'partition_contract': expected_contract}
    if (any(manifest.get(k) != v for k, v in expected.items()) or
            expected_target != S3_UPDATE_TARGET or
            expected_contract != S3_UPDATE_PARTITION_CONTRACT or
            not re.fullmatch(r'[0-9a-f]{64}', expected_sha256 or '') or
            manifest.get('size') != len(image) or
            hashlib.sha256(image).hexdigest() != expected_sha256):
        raise ValueError('s3_update_evidence_binding_mismatch')
    return snapshot, image, manifest


def validate_s3_application_update(image, expected_sha256, baseline, observed,
                                    partitions, write_ranges=None):
    """Technical guard for the existing official S3 app-only tool invocation.

    Baseline/observed are installed-device evidence, never generated bootloader
    artifacts. This does not grant hardware access or qualify automatic FOTA.
    The existing development_session still owns admission, locks and audit.
    """
    expected_layout = S3_UPDATE_LAYOUT
    if any(observed.get(k) != v for k, v in
           {'device_id': 'hub-e072a1d38d34', 'port': 'COM10',
            'serial_number': 'E0:72:A1:D3:8D:34',
            'home_id': 'gs177-test-product'}.items()):
        raise ValueError('s3_update_device_identity_mismatch')
    for field in ('device_id', 'port', 'serial_number', 'home_id', 'bootloader_sha256',
                  'partition_table_sha256', 'ota_contract'):
        if not baseline.get(field) or baseline[field] != observed.get(field):
            raise ValueError('s3_update_installed_contract_requires_revalidation')
    for field in ('bootloader_sha256', 'partition_table_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', baseline[field]):
            raise ValueError('s3_update_baseline_digest_invalid')
    if {k: tuple(v) for k, v in partitions.items()} != expected_layout:
        raise ValueError('s3_update_partition_layout_incompatible')
    if (not isinstance(image, bytes) or len(image) < 256 or image[0] != 0xe9 or
            int.from_bytes(image[12:14], 'little') != 9 or
            int.from_bytes(image[32:36], 'little') != 0xabcd5432 or
            not re.fullmatch('[0-9a-f]{64}', expected_sha256 or '') or
            hashlib.sha256(image).hexdigest() != expected_sha256):
        raise ValueError('s3_update_application_image_incompatible')
    active = observed.get('active_slot')
    if type(active) is not int or active not in (0, 1):
        raise ValueError('s3_update_active_slot_unverified')
    target = 1-active
    offset, capacity = expected_layout['ota_'+str(target)]
    erase_size = (len(image)+0xfff) & ~0xfff
    if erase_size > capacity:
        raise ValueError('s3_update_application_exceeds_slot')
    # IDF ParttoolTarget erases the complete inactive application partition.
    # This region contains no selected recovery image or protected data.
    erase_size = capacity
    allowed = [('application', offset, erase_size)]
    if write_ranges is not None:
        requested = [tuple(row) for row in write_ranges]
        # OTA selection is a distinct supported operation, never ota_data_initial.
        permitted = allowed + [('ota_selection', 0xF000, 0x2000)]
        if not requested or len(requested) != len(set(requested)) or any(
                row not in permitted for row in requested):
            raise ValueError('s3_update_protected_write_rejected')
    return {'target_slot': target, 'application_offset': offset,
            'application_size': len(image), 'application_erase_size': erase_size,
            'application_sha256': expected_sha256, 'baseline_reused': True,
            'automatic_fota_qualification': 'NOT_ESTABLISHED_BY_THIS_GUARD'}


def validate_s3_update_tool_command(arguments, plan, application_path,
                                   original_otadata, *, application_verified=False):
    """Constrain commands emitted by the existing IDF ParttoolTarget instance."""
    import binascii
    args = list(arguments)
    if not args or len(args) != (4 if args[0] == 'read-flash' else 3):
        raise ValueError('s3_update_tool_command_rejected')
    action = args[0]
    try:
        offset = int(str(args[1]), 0)
    except ValueError as error:
        raise ValueError('s3_update_tool_offset_invalid') from error
    app_range = (plan['application_offset'], plan['application_erase_size'])
    if action == 'read-flash':
        size = int(str(args[2]), 0)
        if offset < 0 or size <= 0 or offset+size > 0x1000000:
            raise ValueError('s3_update_read_out_of_bounds')
        return
    if action == 'erase-region':
        region = (offset, int(str(args[2]), 0))
        if region == app_range:
            return
        # Parttool's whole-otadata erase destroys both selector copies before
        # its subsequent write. A reset or interrupted parent in that window
        # would leave no valid selector for the retained recovery image.
        if region == (0xF000, 0x2000):
            raise ValueError('s3_update_selector_erase_not_interruption_safe')
        raise ValueError('s3_update_protected_write_rejected')
    if action != 'write-flash':
        raise ValueError('s3_update_tool_command_rejected')
    path = Path(args[2])
    if path.is_symlink() or not path.is_file():
        raise ValueError('s3_update_write_input_invalid')
    data = path.read_bytes()
    if offset == app_range[0]:
        if (path.resolve() != Path(application_path).resolve() or
                len(data) != plan['application_size'] or
                hashlib.sha256(data).hexdigest() != plan['application_sha256']):
            raise ValueError('s3_update_application_changed')
        return
    if (not application_verified or len(original_otadata) != 0x2000 or
            len(data) != 0x1000 or offset not in (0xF000, 0x10000)):
        raise ValueError('s3_update_protected_write_rejected')

    def record(raw, copy):
        at = copy*0x1000
        seq = int.from_bytes(raw[at:at+4], 'little')
        state = int.from_bytes(raw[at+24:at+28], 'little')
        crc = int.from_bytes(raw[at+28:at+32], 'little')
        valid = seq != 0xffffffff and state in (2, 0xffffffff) and crc == (binascii.crc32(raw[at:at+4],0xffffffff)&0xffffffff)
        return seq, valid
    old = [record(original_otadata,i) for i in range(2)]
    valid = [i for i in range(2) if old[i][1]]
    if not valid:
        raise ValueError('s3_update_selector_unverified')
    active = max(valid,key=lambda i:old[i][0]); other = 1-active
    if len(valid)==2 and old[0][0]==old[1][0]:
        raise ValueError('s3_update_selector_ambiguous')
    if offset != 0xF000 + other*0x1000:
        raise ValueError('s3_update_selector_active_copy_write_rejected')
    original_sector = original_otadata[other*0x1000:(other+1)*0x1000]
    if data == original_sector:
        return  # Restore only the inactive selector copy; the active copy remains valid.
    new_seq, new_valid = record(data,0)
    allowed = set(range(4)) | set(range(28,32))
    if (not new_valid or new_seq <= old[active][0] or
            (new_seq-1)%2 != plan['target_slot'] or
            any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(data,original_sector)))):
        raise ValueError('s3_update_selector_change_rejected')


def s3_official_application_target(table_path, live_otadata, *,
                                   port, parttool_module=None, otatool_module=None):
    """Compose the pinned IDF APIs without their obsolete positional constructor.

    IDF6.0.3 ParttoolTarget gained primary/recovery bootloader offsets before
    partition_table_file. OtatoolTarget still passes its inputs positionally.
    Preserve official methods and initialize their three documented fields from
    the already verified live snapshot; never launch an implicit serial query.
    """
    if len(live_otadata) != 0x2000 or not Path(table_path).is_file():
        raise ValueError('s3_update_live_partition_inputs_required')
    if port != S3_UPDATE_TARGET["port"]:
        raise ValueError('s3_update_registered_target_mismatch')
    if parttool_module is None:
        import parttool as parttool_module
    if otatool_module is None:
        import otatool as otatool_module
    target = object.__new__(otatool_module.OtatoolTarget)
    target.target = parttool_module.ParttoolTarget(
        port=port, baud=460800, partition_table_file=str(table_path),
        esptool_args=['chip=esp32s3', 'before=no-reset', 'after=no-reset'])
    target.spi_flash_sec_size = 0x2000
    target.otadata = bytes(live_otadata)
    return target


class S3UpdateAuthorizationLost(ValueError):
    pass


def _selector_copy(raw, copy):
    at = copy * 0x1000
    seq = int.from_bytes(raw[at:at + 4], "little")
    state = int.from_bytes(raw[at + 24:at + 28], "little")
    crc = int.from_bytes(raw[at + 28:at + 32], "little")
    valid = (seq != 0xffffffff and state in (2, 0xffffffff) and
             crc == (binascii.crc32(raw[at:at + 4], 0xffffffff) & 0xffffffff))
    return {"copy": copy, "seq": seq, "valid": valid,
            "slot": (seq - 1) % 2 if valid else None}


def _selected_ota_copy(raw):
    if len(raw) != 0x2000:
        raise ValueError("s3_update_selector_size_invalid")
    copies = [_selector_copy(raw, i) for i in range(2)]
    valid = [copy for copy in copies if copy["valid"]]
    if not valid:
        raise ValueError("s3_update_selector_unverified")
    if len(valid) == 2 and valid[0]["seq"] == valid[1]["seq"]:
        raise ValueError("s3_update_selector_ambiguous")
    return max(valid, key=lambda copy: copy["seq"]), copies


class _S3IDFUpdateDriver:
    def __init__(self, config, authorize):
        self.config = config
        self.authorize = authorize
        self.evidence = Path(config["evidence_dir"])
        components = Path(config["idf_components"])
        if (components.is_symlink() or not components.is_dir() or
                not (components / "app_update" / "otatool.py").is_file() or
                not (components / "partition_table" / "parttool.py").is_file()):
            raise ValueError("s3_update_idf_components_unavailable")
        if any(hashlib.sha256((components / relative).read_bytes()).hexdigest() != digest
               for relative, digest in S3_UPDATE_IDF_SOURCE_HASHES.items()):
            raise ValueError("s3_update_official_idf_source_changed")
        sys.path[:0] = [str(components / "partition_table"), str(components / "app_update")]
        import esptool
        import esptool.cmds
        import gen_esp32part
        import otatool
        import parttool
        from esptool.targets.esp32s3 import ESP32S3ROM
        if esptool.__version__ != "5.4.0":
            raise ValueError("s3_update_esptool_version_mismatch")
        self.esptool = esptool
        self.esptool_cmds = esptool.cmds
        self.gen_esp32part = gen_esp32part
        self.otatool = otatool
        self.parttool = parttool
        self.ESP32S3ROM = ESP32S3ROM
        self.esp = None
        self.tool = None
        self.log = None
        self.original_otadata = None
        self.plan = None
        self.snapshot = None
        self.application_verified = False
        self.protected = {}

    def _save(self, name, data):
        path = self.evidence / name
        with path.open("xb") as stream:
            stream.write(data)
        return path

    def _read_flash(self, name, offset, size):
        data = self.esp.read_flash(offset, size)
        if not isinstance(data, bytes) or len(data) != size:
            raise ValueError("s3_update_flash_read_incomplete_" + name)
        return data

    def inspect(self, target):
        discovered = list(list_ports.comports())
        matches = [item for item in discovered
                   if item.serial_number == target["serial_number"] and
                   item.vid == target["usb_vid"] and item.pid == target["usb_pid"]]
        same_port = [item for item in discovered if item.device == target["port"]]
        if (len(matches) != 1 or matches[0].device != target["port"] or
                len(same_port) != 1):
            raise ValueError("s3_update_registered_usb_target_not_unique")
        item = matches[0]
        if not (item.hwid or "").startswith(
                "USB VID:PID=303A:1001 SER=" + target["serial_number"]):
            raise ValueError("s3_update_registered_usb_hwid_mismatch")

        self.esp = self.ESP32S3ROM(target["port"], baud=115200)
        self.esp.connect(mode="default-reset", attempts=1)
        if bytes(self.esp.read_mac()).hex() != target["serial_number"].replace(":", "").lower():
            raise ValueError("s3_update_physical_mac_mismatch")
        security = self.esp.get_security_info(cache=True)
        flags = security.get("parsed_flags", {})
        if (flags.get("SECURE_BOOT_EN") or security.get("flash_crypt_cnt") or
                flags.get("SECURE_DOWNLOAD_ENABLE")):
            raise ValueError("s3_update_unexpected_flash_security_state")
        self.esp = self.esptool_cmds.run_stub(self.esp)
        self.esp.change_baud(460800)

        boot = self._read_flash("bootloader", 0, 0x8000)
        table = self._read_flash("partition-table", 0x8000, 0x1000)
        otadata = self._read_flash("otadata-before", 0xF000, 0x2000)
        self._save("partition-table.bin", table)
        entries = self.gen_esp32part.PartitionTable.from_binary(table)
        partitions = {partition.name: (partition.offset, partition.size)
                      for partition in entries}
        if len(entries) != len(S3_UPDATE_LAYOUT) or partitions != S3_UPDATE_LAYOUT:
            raise ValueError("s3_update_partition_layout_incompatible")
        active, copies = _selected_ota_copy(otadata)
        active_offset, active_size = partitions["ota_" + str(active["slot"])]
        recovery = self._read_flash("recovery-application", active_offset, active_size)
        if (len(recovery) < 256 or recovery[0] != 0xe9 or
                int.from_bytes(recovery[12:14], "little") != 9 or
                int.from_bytes(recovery[32:36], "little") != 0xabcd5432):
            raise ValueError("s3_update_active_recovery_application_invalid")

        protected = {"bootloader": boot, "partition_table": table}
        for name in ("nvs", "gs_outbox", "gs_state"):
            offset, size = partitions[name]
            protected[name] = self._read_flash(name, offset, size)
        observed = {
            "device_id": target["device_id"], "port": target["port"],
            "serial_number": target["serial_number"], "home_id": target["home_id"],
            "bootloader_sha256": hashlib.sha256(boot).hexdigest(),
            "partition_table_sha256": hashlib.sha256(table).hexdigest(),
            "ota_contract": "IDF6.0.3_ENGINEERING_APP_ONLY",
            "active_slot": active["slot"],
        }
        self.original_otadata = otadata
        self.protected = protected
        self.active_recovery = recovery
        self.active_selector = active
        self.partitions = partitions
        self.device = {"port": target["port"], "usb_serial": target["serial_number"],
                       "usb_vid": target["usb_vid"], "usb_pid": target["usb_pid"],
                       "usb_hwid": item.hwid or "", "flash_size": "16MB"}
        return {"baseline": dict(observed), "observed": observed,
                "partitions": partitions, "active_selector": active,
                "otadata": otadata,
                "selector_copies": copies}

    def write_application(self, plan, snapshot, plan_sha256, original_otadata):
        self.plan = plan
        self.snapshot = Path(snapshot)
        self.log = (self.evidence / "official-tool.log").open("x", encoding="utf-8")
        if self.esp._port.is_open:
            self.esp._port.close()
        self.tool = s3_official_application_target(
            self.evidence / "partition-table.bin", original_otadata,
            port=self.config["target"]["port"], parttool_module=self.parttool,
            otatool_module=self.otatool)
        original_call = self.tool.target._call_esptool

        def checked_call(args, out=None):
            args = list(args)
            if args and args[0] in ("erase-region", "write-flash"):
                validate_s3_update_tool_command(
                    args, plan, snapshot, original_otadata,
                    application_verified=self.application_verified)
                offset = int(str(args[1]), 0)
                if offset == plan["application_offset"]:
                    boundary = ("application_erase" if args[0] == "erase-region"
                                else "application_write")
                elif offset in (0xF000, 0x10000):
                    boundary = self.selector_boundary
                    if boundary not in ("selector_update", "selector_recovery"):
                        raise ValueError("s3_update_selector_boundary_missing")
                else:
                    raise ValueError("s3_update_protected_write_rejected")
                self.authorize(boundary, plan_sha256)
            if args and args[0] in ("erase-region", "write-flash"):
                return original_call(args, out=self.log)
            return original_call(args, out=out)

        self.selector_boundary = None
        self.tool.target._call_esptool = checked_call
        self.tool.write_ota_partition(plan["target_slot"], str(snapshot))

    def verify_application(self, plan, image):
        path = self.evidence / "application-readback.bin"
        self.tool.read_ota_partition(plan["target_slot"], str(path))
        raw = path.read_bytes()
        if raw[:len(image)] != image or any(value != 0xff for value in raw[len(image):]):
            raise ValueError("s3_update_application_readback_mismatch")
        self.application_verified = True
        return hashlib.sha256(raw[:len(image)]).hexdigest()

    def verify_protected(self):
        hashes = {}
        for name, expected in self.protected.items():
            path = self.evidence / (name + "-after.bin")
            if name in ("bootloader", "partition_table"):
                offset, size = ((0, 0x8000) if name == "bootloader" else (0x8000, 0x1000))
            try:
                if name in ("bootloader", "partition_table"):
                    self.tool.target._call_esptool(
                        ["read-flash", str(offset), str(size), str(path)], out=self.log)
                else:
                    self.tool.target.read_partition(
                        self.parttool.PartitionName(name), str(path))
                actual = path.read_bytes()
                if actual != expected:
                    raise ValueError("s3_update_protected_region_changed_" + name)
                hashes[name] = hashlib.sha256(actual).hexdigest()
            finally:
                path.unlink(missing_ok=True)
        path = self.evidence / "recovery-application-after.bin"
        try:
            self.tool.read_ota_partition(self.active_selector["slot"], str(path))
            actual = path.read_bytes()
            if actual != self.active_recovery:
                raise ValueError("s3_update_recovery_application_changed")
            hashes["recovery_application"] = hashlib.sha256(actual).hexdigest()
        finally:
            path.unlink(missing_ok=True)
        return hashes

    def _write_selector_sector(self, sector, boundary, plan_sha256):
        active, _ = _selected_ota_copy(self.original_otadata)
        other = 1 - active["copy"]
        offset = 0xF000 + other * 0x1000
        path = self.evidence / ("selector-" + boundary + ".bin")
        with path.open("xb") as stream:
            stream.write(sector)
        args = ["write-flash", hex(offset), str(path)]
        validate_s3_update_tool_command(
            args, self.plan, self.snapshot, self.original_otadata,
            application_verified=self.application_verified)
        self.selector_boundary = boundary
        try:
            self.tool.target._call_esptool(args, out=self.log)
        finally:
            self.selector_boundary = None

    def select(self, target_slot, plan_sha256):
        original_write = self.tool.target.write_partition

        def interruption_safe_partition_write(partition_id, input_path, ignore_readonly=False):
            is_otadata = (getattr(partition_id, "name", None) == "otadata" or
                          (getattr(partition_id, "type", None) == "data" and
                           getattr(partition_id, "subtype", None) == "ota"))
            if not is_otadata:
                return original_write(partition_id, input_path, ignore_readonly)
            candidate = Path(input_path).read_bytes()
            if len(candidate) != 0x2000:
                raise ValueError("s3_update_selector_size_invalid")
            active, _ = _selected_ota_copy(self.original_otadata)
            other = 1 - active["copy"]
            sector = candidate[other * 0x1000:(other + 1) * 0x1000]
            self._write_selector_sector(sector, "selector_update", plan_sha256)

        self.tool.target.write_partition = interruption_safe_partition_write
        self.tool.switch_ota_partition(target_slot)
        selected_path = self.evidence / "otadata-after.bin"
        self.tool.target.read_partition(self.otatool.OtatoolTarget.OTADATA_PARTITION,
                                        str(selected_path))
        selected, _ = _selected_ota_copy(selected_path.read_bytes())
        if selected["slot"] != target_slot:
            raise ValueError("s3_update_selected_slot_mismatch")
        return selected

    def recover_selector(self, plan_sha256):
        active, _ = _selected_ota_copy(self.original_otadata)
        other = 1 - active["copy"]
        sector = self.original_otadata[other * 0x1000:(other + 1) * 0x1000]
        self._write_selector_sector(sector, "selector_recovery", plan_sha256)
        path = self.evidence / "selector-recovery-readback.bin"
        self.tool.target.read_partition(self.otatool.OtatoolTarget.OTADATA_PARTITION,
                                        str(path))
        if path.read_bytes() != self.original_otadata:
            raise ValueError("s3_update_selector_recovery_readback_mismatch")

    def restore_application(self):
        if self.esp is None:
            return
        from gs117_tc001_readback import restore_application_once
        restore_application_once(self.esp, self.device)

    def close(self):
        if self.log is not None:
            self.log.close()
        if self.esp is not None and self.esp._port.is_open:
            self.esp._port.close()


def run_s3_application_update(config, authorize, driver=None):
    """Run the maintained IDF app-only writer using a live parent authorization callback."""
    required = ("session_id", "expected_sha256", "binding_dir", "binding_sha256",
                "evidence_dir", "idf_components", "target", "writer_sha256")
    if any(key not in config for key in required):
        raise ValueError("s3_update_writer_configuration_invalid")
    session_id = config["session_id"]
    expected_sha256 = config["expected_sha256"]
    if (not re.fullmatch(r"[0-9a-f]{32}", str(session_id)) or
            not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha256)) or
            not re.fullmatch(r"[0-9a-f]{64}", str(config["binding_sha256"])) or
            not re.fullmatch(r"[0-9a-f]{64}", str(config["writer_sha256"])) or
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != config["writer_sha256"]):
        raise ValueError("s3_update_writer_configuration_invalid")
    snapshot, image, manifest = verify_s3_update_binding(
        config["binding_dir"], session_id, expected_sha256, config["target"],
        S3_UPDATE_PARTITION_CONTRACT)
    binding_path = Path(config["binding_dir"]) / "artifact-binding.json"
    if hashlib.sha256(binding_path.read_bytes()).hexdigest() != config["binding_sha256"]:
        raise ValueError("s3_update_binding_manifest_changed")
    evidence = Path(config["evidence_dir"])
    if evidence != Path(config["binding_dir"]) or evidence.is_symlink():
        raise ValueError("s3_update_evidence_binding_invalid")
    lock_path = evidence / "writer.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("s3_update_duplicate_writer_rejected") from error
    os.close(descriptor)

    driver = driver
    plan = None
    selector_write_started = False
    result = {"status": "STARTED", "session_id": session_id,
              "application_sha256": expected_sha256, "target": manifest["target"],
              "partition_contract": manifest["partition_contract"],
              "protected_regions_unchanged": False,
              "selector_recovery": "NOT_REQUIRED"}
    try:
        if driver is None:
            driver = _S3IDFUpdateDriver(config, authorize)
        inspection = driver.inspect(manifest["target"])
        plan = validate_s3_application_update(
            image, expected_sha256, inspection["baseline"], inspection["observed"],
            inspection["partitions"])
        plan_data = {"plan": plan, "active_selector": inspection["active_selector"],
                     "baseline": inspection["baseline"], "target": manifest["target"]}
        plan_sha256 = hashlib.sha256(json.dumps(
            plan_data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        driver.write_application(plan, snapshot, plan_sha256, inspection["otadata"])
        result["application_readback_sha256"] = driver.verify_application(plan, image)
        result["protected_region_sha256"] = driver.verify_protected()
        result["protected_regions_unchanged"] = True
        selector_write_started = True
        result["selector_after"] = driver.select(plan["target_slot"], plan_sha256)
        result["selector_recovery"] = "NOT_REQUIRED"
        result["status"] = "WRITTEN_READBACK_VERIFIED_SELECTED"
        driver.restore_application()
        result["normal_boot_restoration"] = "USB_IDENTITY_REENUMERATED"
        return result
    except S3UpdateAuthorizationLost as error:
        result.update(status="FAIL", failure=str(error)[:240])
        raise
    except Exception as error:
        result.update(status="FAIL", failure=str(error)[:240])
        if selector_write_started and plan is not None:
            try:
                driver.recover_selector(plan_sha256)
                result["selector_recovery"] = "VERIFIED_ORIGINAL_RESTORED"
            except S3UpdateAuthorizationLost:
                result["selector_recovery"] = "NOT_ATTEMPTED_PARENT_OWNERSHIP_LOST"
            except Exception as recovery_error:
                result["selector_recovery"] = "FAIL:" + str(recovery_error)[:180]
                raise RuntimeError("s3_update_selector_recovery_failed") from recovery_error
        if driver is not None and not isinstance(error, S3UpdateAuthorizationLost):
            try:
                driver.restore_application()
                result["normal_boot_restoration"] = "USB_IDENTITY_REENUMERATED"
            except Exception as restore_error:
                result["normal_boot_restoration"] = "FAIL:" + str(restore_error)[:180]
                raise RuntimeError("s3_update_normal_boot_restoration_failed") from restore_error
        raise
    finally:
        try:
            if driver is not None:
                driver.close()
        except Exception as close_error:
            result["cleanup_error"] = str(close_error)[:180]
        report_path = evidence / "update-result.json"
        with report_path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())


def _s3_update_dedicated_protocol_stream():
    sys.stdout.flush()
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1, encoding="utf-8")
    try:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    except OSError:
        protocol.close()
        raise
    return protocol


def _s3_update_stdio_authorizer(config, protocol_stream=None):
    sequence = 0

    def authorize(boundary, plan_sha256):
        nonlocal sequence
        if boundary not in S3_UPDATE_WRITE_BOUNDARIES or not re.fullmatch(
                r"[0-9a-f]{64}", str(plan_sha256)):
            raise S3UpdateAuthorizationLost("s3_update_parent_ownership_invalid")
        sequence += 1
        request = {"kind": "s3_update_write_authorization", "sequence": sequence,
                   "session_id": config["session_id"],
                   "binding_sha256": config["binding_sha256"],
                   "application_sha256": config["expected_sha256"],
                   "boundary": boundary, "plan_sha256": plan_sha256}
        stream = protocol_stream if protocol_stream is not None else sys.__stdout__
        stream.write(json.dumps(request, sort_keys=True) + "\n")
        stream.flush()
        response_line = sys.__stdin__.readline()
        if not response_line:
            raise S3UpdateAuthorizationLost("s3_update_parent_interrupted")
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as error:
            raise S3UpdateAuthorizationLost("s3_update_parent_response_invalid") from error
        if (response.get("kind") != "s3_update_write_authorization" or
                response.get("sequence") != sequence or
                response.get("session_id") != config["session_id"] or
                response.get("allowed") is not True):
            raise S3UpdateAuthorizationLost("s3_update_parent_ownership_invalid")
    return authorize


def _run_s3_application_update_cli(config):
    protocol_stream = _s3_update_dedicated_protocol_stream()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = run_s3_application_update(
                config, _s3_update_stdio_authorizer(config, protocol_stream))
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
    finally:
        protocol_stream.close()


if __name__ == "__main__":
    try:
        config = json.loads(base64.b64decode(sys.argv[1], validate=True))
        action = config.get("action")
        if action == "S3ApplicationUpdate":
            _run_s3_application_update_cli(config)
            raise SystemExit(0)
        elif action == "List":
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
        elif action == "BootstrapS3Reboot11983":
            from esptool.reset import HardReset
            value = bootstrap_s3(config, boot_reset=lambda stream: HardReset(stream, uses_usb=True).reset())
        elif action == "BootstrapS3":
            value = bootstrap_s3(config)
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
        if locals().get("action") == "S3ApplicationUpdate":
            print(json.dumps(failure), file=sys.stderr)
        else:
            print(json.dumps(failure))
        raise SystemExit(2)
