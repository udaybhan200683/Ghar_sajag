#!/usr/bin/env python3
"""Focused physical qualification of authenticated signed C3 FOTA.

This campaign deliberately uses the existing Phase-1 USB/serial fixture and
report primitives. It is separate from the legacy raw-v1 ``hil-fota`` path.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[2]
REPO = PRODUCT.parents[1]
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))

from tools.hil import phase1
from tools.hil.core import (FixtureLock, Results, SerialCapture, host_metadata,
                            write_report)

RUNS = REPO / "evidence/hil/runs"
NODE_PROJECT = PRODUCT / "firmware/node/target/esp32c3/idf"
HUB_PROJECT = PRODUCT / "firmware/hub/target/esp32/idf"
ARTIFACTS = PRODUCT / "build/secure_signed_fota"
LOCK = phase1.LOCK
SIGNING_ENV = "GS_HIL_SIGNED_FOTA_KEY"
NEGATIVE_ENV = "GS_HIL_SIGNED_FOTA_NEGATIVE_KEY"
EXPECTED = ("SIGNED_FOTA_NEGATIVE", "SIGNED_FOTA_A_TO_B", "POST_UPDATE_RECOVERY")
OTA_DATA_OFFSET = 0xF000
OTA_DATA_SIZE = 0x2000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def activated_python_command(script: str, *args: str) -> list[str]:
    """Use the interpreter selected by the ESP-IDF activation script's PATH."""
    return ["python", script, *args]


def command(args: list[str], *, cwd: Path, config: dict[str, str], timeout: int = 3600) -> str:
    shell = f"source {shlex.quote(str(phase1.activation(config)))}; {shlex.join(args)}"
    completed = subprocess.run(["bash", "-lc", shell], cwd=cwd, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {args[0]}\n"
                           f"{completed.stdout[-4000:]}")
    return completed.stdout


def validate_signing_inputs(config: dict[str, str]) -> tuple[Path, Path]:
    signing = Path(os.environ.get(SIGNING_ENV, "")).expanduser().resolve()
    negative = Path(os.environ.get(NEGATIVE_ENV, "")).expanduser().resolve()
    if not signing.is_file() or not negative.is_file():
        raise RuntimeError(f"set {SIGNING_ENV} and {NEGATIVE_ENV} to external RSA-3072 test keys")
    if signing == negative:
        raise RuntimeError("distinct signing keys are required")
    activation = phase1.activation(config)
    if not activation.is_file():
        raise RuntimeError(f"ESP-IDF activation script is unavailable: {activation}")
    return signing, negative


def build_images(run_dir: Path, config: dict[str, str]) -> dict[str, dict]:
    signing, negative = validate_signing_inputs(config)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%y%m%d%H%M%S")
    versions = {"A": f"sfA-{stamp}", "B": f"sfB-{stamp}", "NEG": f"sfN-{stamp}"}
    out_dir = ARTIFACTS / stamp
    out_dir.mkdir(parents=True, exist_ok=False)
    records: dict[str, dict] = {}
    for label, key in (("A", signing), ("B", signing), ("NEG", negative)):
        image = out_dir / f"c3-{label.lower()}.signed.bin"
        build_dir = f"build_secure_signed_fota_{stamp}"
        args = activated_python_command("scripts/build_signed_c3.py", "--signing-key", str(key),
                "--version", versions[label], "--output", str(image), "--hil-control",
                "--build-dir", build_dir)
        if label == "NEG":
            args += ["--trusted-key", str(signing)]
        log = command(args, cwd=PRODUCT, config=config)
        for private_path in (str(signing), str(negative)):
            log = log.replace(private_path, "<external-test-key>")
        (run_dir / f"build_c3_{label.lower()}.log").write_text(log, encoding="utf-8")
        record = json.loads(image.with_suffix(image.suffix + ".json").read_text(encoding="utf-8"))
        if record["version"] != versions[label] or record["hil_control"] is not True or record["gs_hil_build"] is not False:
            raise RuntimeError(f"C3 {label} artifact profile/version mismatch")
        if label in ("A", "B") and record["signing_public_key_fingerprint_sha256"] != records.get("A", record)["signing_public_key_fingerprint_sha256"]:
            raise RuntimeError("signed A/B public key fingerprints differ")
        if label == "NEG" and record["signing_public_key_fingerprint_sha256"] == records["A"]["signing_public_key_fingerprint_sha256"]:
            raise RuntimeError("negative candidate unexpectedly uses A signing key")
        records[label] = {**record, "path": str(image)}
    if versions["A"] == versions["B"] or records["A"]["size"] > 0x1E0000 or records["B"]["size"] > 0x1E0000:
        raise RuntimeError("A/B versions or OTA slot sizes are invalid")
    records["versions"] = versions
    return records


def build_hubs(images: dict[str, dict], run_dir: Path, config: dict[str, str]) -> dict[str, dict]:
    built: dict[str, dict] = {}
    embed = HUB_PROJECT / "main/node_firmware.bin"
    previous = embed.read_bytes() if embed.is_file() else None
    try:
        for candidate in ("NEG", "B"):
            label = f"sfota-{candidate.lower()}-{images['versions'][candidate]}"
            output = ARTIFACTS / f"hub-{label}.bin"
            log = command(activated_python_command("scripts/build_secure_fota_hub.py", "--node-image",
                           images[candidate]["path"], "--output", str(output), "--label", label,
                           "--build-dir", f"secure_fota_hub_{images['versions']['A']}"),
                          cwd=PRODUCT, config=config)
            (run_dir / f"build_hub_{candidate.lower()}.log").write_text(log, encoding="utf-8")
            sidecar = json.loads(output.with_suffix(output.suffix + ".json").read_text(encoding="utf-8"))
            if sidecar["embedded_c3_sha256"] != images[candidate]["sha256"] or sidecar["legacy_raw_fota"]:
                raise RuntimeError(f"Hub {candidate} embedding provenance mismatch")
            built[candidate] = sidecar
    finally:
        if previous is None:
            embed.unlink(missing_ok=True)
        else:
            embed.write_bytes(previous)
    return built


def hub_flash_command(record: dict, port: str) -> str:
    build_dir = Path(record["build_dir"])
    image = Path(record.get("hub_image", ""))
    otadata = build_dir / "ota_data_initial.bin"
    if (record.get("profile") != "secure-signed-fota-hil-control" or
            record.get("legacy_raw_fota") is not False or not image.is_file() or
            not otadata.is_file() or record.get("hub_sha256") != sha256(image)):
        raise RuntimeError("Hub artifact/profile/hash is not the prepared secure candidate")
    if image.stat().st_size == 0 or image.stat().st_size > 0x1E0000:
        raise RuntimeError("Hub artifact is empty or does not fit the OTA slot")
    # Flash the exact sidecar-verified Hub candidate. Running `idf.py flash`
    # here can rebuild a shared build directory for the other candidate and
    # silently replace the selected NEG/B image. Reset only OTA selection and
    # ota_0 app bytes; leave Hub NVS (identity/registry) intact.
    command = (
        f"python -m esptool --chip esp32 -b 460800 --port {phase1.shlex.quote(port)} "
        f"--before default-reset --after hard-reset write-flash --flash-mode dio "
        f"--flash-size 4MB --flash-freq 40m 0x{OTA_DATA_OFFSET:x} "
        f"{phase1.shlex.quote(str(otadata))} 0x20000 {phase1.shlex.quote(str(image))}")
    return command


def flash_hub(config: dict[str, str], port: str, record: dict, run_dir: Path, label: str) -> None:
    command = hub_flash_command(record, port)
    output = phase1.idf_command(config, command, HUB_PROJECT, 900)
    (run_dir / f"flash_hub_{label}.log").write_text(output.stdout or "", encoding="utf-8")
    if output.returncode:
        raise RuntimeError(f"Hub {label} firmware flash failed")
    phase1.runtime_port(config, "hub", timeout=25)


def flash_signed_a(config: dict[str, str], port: str, record: dict, run_dir: Path) -> None:
    build_dir = Path(record["build_dir"])
    signed = Path(record["path"])
    app = build_dir / "gs_hw_m1_node.bin"
    if not app.is_file() or not signed.is_file():
        raise RuntimeError("signed A flash inputs are missing")
    backup = app.with_suffix(".unsigned-for-restore")
    shutil.copy2(app, backup)
    try:
        # Reset only OTA selection metadata. Keep the C3's NVS device identity
        # and installer credential intact for exact authenticated enrollment.
        erased = phase1.idf_command(config,
            f"esptool --chip esp32c3 --port {phase1.shlex.quote(port)} erase-region "
            f"0x{OTA_DATA_OFFSET:x} 0x{OTA_DATA_SIZE:x}", NODE_PROJECT, 120)
        (run_dir / "erase_c3_otadata.log").write_text(erased.stdout or "", encoding="utf-8")
        if erased.returncode:
            raise RuntimeError("could not safely reset C3 OTA selection metadata")
        shutil.copy2(signed, app)
        flashed = phase1.idf_command(config,
            f"idf.py -B {phase1.shlex.quote(str(build_dir))} -p {phase1.shlex.quote(port)} flash",
            NODE_PROJECT, 900)
        (run_dir / "flash_c3_signed_a.log").write_text(flashed.stdout or "", encoding="utf-8")
        if flashed.returncode:
            raise RuntimeError("signed A flash failed")
        phase1.runtime_port(config, "c3", timeout=25)
    finally:
        shutil.copy2(backup, app)
        backup.unlink(missing_ok=True)


def redact_test_code(path: Path) -> None:
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"installer_code=[0-9a-fA-F]+", "installer_code=<redacted>", text)
        path.write_text(text, encoding="utf-8")


def send_commissioning_control(capture: SerialCapture, command_text: str) -> None:
    """Pace the long test commissioning line below the Hub UART RX ring size."""
    payload = (command_text + "\n").encode("utf-8")
    with capture.stream_lock:
        stream = capture.stream
        if stream is None or not stream.is_open:
            raise RuntimeError(f"{capture.role} serial is not open")
        for offset in range(0, len(payload), 32):
            stream.write(payload[offset:offset + 32])
            stream.flush()
            if offset + 32 < len(payload):
                time.sleep(0.01)


class SecureCampaign:
    def __init__(self, config: dict[str, str], devices: dict, run_dir: Path):
        self.config, self.devices, self.run_dir = config, devices, run_dir
        self.hub = self.c3 = None
        self.results = Results()
        self.images: dict[str, dict] = {}
        self.hubs: dict[str, dict] = {}
        self.node_id = ""
        self.before_slot = ""
        self.before_session = ""
        self.active_case = "SIGNED_FOTA_SETUP"
        self.transfer_ids: dict[str, str] = {}

    def open(self) -> None:
        ports = phase1.cached_campaign_ports(self.config, self.devices)
        self.hub = SerialCapture("hub", ports["hub"], self.run_dir / "hub_serial.log",
            port_resolver=lambda: phase1.runtime_port(self.config, "hub"))
        self.c3 = SerialCapture("c3", ports["c3"], self.run_dir / "c3_serial.log",
            port_resolver=lambda: phase1.runtime_port(self.config, "c3"))
        self.hub.start(); self.c3.start()

    def close(self) -> None:
        for capture in (self.hub, self.c3):
            if capture:
                capture.close()
        redact_test_code(self.run_dir / "hub_serial.log")
        redact_test_code(self.run_dir / "c3_serial.log")

    @staticmethod
    def send(capture: SerialCapture, command_text: str, pattern: str,
             timeout: float = 10) -> str:
        cursor = capture.cursor()
        capture.send(command_text)
        return capture.wait_for(pattern, timeout, cursor)

    def restart_and_ready(self, capture: SerialCapture, role: str, version: str,
                          *, wait_for_sensing: bool = True) -> None:
        cursor = capture.cursor()
        capture.send("SOFTWARE_RESTART")
        capture.wait_for_predicate(lambda line: phase1.normalize_rom_reset_class(line) ==
            phase1.SOFTWARE_RESET_EVIDENCE, "fresh normalized software reset", 8, cursor)
        capture.wait_for(rf"HIL_READY role={role} protocol=1 version={re.escape(version)}", 35, cursor)
        if role == "c3" and wait_for_sensing:
            capture.wait_for(r"PIR ready on GPIO", 45, cursor)

    def motion(self) -> None:
        c3_cursor, hub_cursor = self.c3.cursor(), self.hub.cursor()
        self.send(self.c3, "INJECT_MOTION", r"HIL_OK command=INJECT_MOTION")
        event = self.c3.wait_for(
            r"PIR -> NodeRuntime session=(\d+) seq=(\d+)", 10, c3_cursor)
        identity = re.search(r"session=(\d+) seq=(\d+)", event)
        if not identity:
            raise RuntimeError("C3 motion event omitted authenticated session/sequence")
        session, sequence = identity.groups()
        self.c3.wait_for(
            rf"NodeMessage sent session={session} seq={sequence} bytes=\d+", 12, c3_cursor)
        self.hub.wait_for(
            rf"Authenticated event logical=hil-signed-fota seq={sequence} ack=\d+ send=ESP_OK",
            20, hub_cursor)
        self.c3.wait_for(
            rf"Application ACK session={session} seq={sequence} class=\d+ retired=1",
            20, c3_cursor)

    def exact_identity_and_session(self, rejoin_cursor: int,
                                   c3_ready_cursor: int) -> None:
        qr_cursor = self.c3.cursor()
        self.send(self.c3, "GET_TEST_QR", r"HIL_OK command=GET_TEST_QR")
        qr = self.c3.wait_for(r"HIL_TEST_QR profile=TEST_ONLY device_id=([^ ]+) public_key=([0-9a-f]+)",
                              8, qr_cursor)
        code = self.c3.wait_for(r"HIL_TEST_CODE profile=TEST_ONLY device_id=([^ ]+) installer_code=([0-9a-f]+)",
                                8, qr_cursor)
        identity = re.search(r"device_id=([^ ]+) public_key=([0-9a-f]+)", qr)
        secret = re.search(r"device_id=([^ ]+) installer_code=([0-9a-f]+)", code)
        if not identity or not secret or identity.group(1) != secret.group(1):
            raise RuntimeError("C3 test identity output was incomplete or inconsistent")
        self.node_id = identity.group(1)
        mac_hex = self.node_id.removeprefix("c3-")
        if len(mac_hex) != 12:
            raise RuntimeError("C3 identity does not encode the expected radio address")
        rejoin_pattern = rf"Authenticated rejoin device={re.escape(self.node_id)} .*session=(\d+)"
        try:
            joined = self.hub.wait_for(rejoin_pattern, 8, rejoin_cursor)
        except TimeoutError:
            command = (f"COMMISSION_TEST_NODE {self.node_id} {mac_hex} {identity.group(2)} "
                       f"{secret.group(2)} hil-signed-fota test pir")
            send_commissioning_control(self.hub, command)
            self.hub.wait_for(r"HIL_OK command=COMMISSION_TEST_NODE", 10, rejoin_cursor)
            joined = self.hub.wait_for(rejoin_pattern, 30, rejoin_cursor)
        self.before_session = re.search(r"session=(\d+)", joined).group(1)
        # Sensing is deliberately unavailable until authenticated commissioning
        # or rejoin has completed. Prove readiness from after the fresh C3 boot.
        self.c3.wait_for(r"PIR ready on GPIO", 45, c3_ready_cursor)

    def establish_fresh_node_session(self) -> None:
        """Restart Hub first, then Node, so rejoin belongs to the current Hub boot."""
        self.restart_and_ready(self.hub, "hub", self.hubs["NEG"]["hub_app_version"])
        rejoin_cursor = self.hub.cursor()
        c3_ready_cursor = self.c3.cursor()
        self.restart_and_ready(self.c3, "c3", self.images["A"]["version"],
                               wait_for_sensing=False)
        self.exact_identity_and_session(rejoin_cursor, c3_ready_cursor)

    def state(self, expected: str | None = None) -> str:
        pattern = r"HIL_STATE role=c3 .*ota_slot=ota_[01]"
        if expected:
            pattern = expected
        return self.send(self.c3, "GET_STATE", pattern, 10)

    def secure_transfer(self, version: str, *, expect_signature_reject: bool) -> str:
        cursor_hub, cursor_c3 = self.hub.cursor(), self.c3.cursor()
        command = f"START_AUTHENTICATED_SIGNED_C3_FOTA {self.node_id} esp32c3 {version}"
        self.send(self.hub, command, r"HIL_OK command=START_AUTHENTICATED_SIGNED_C3_FOTA", 10)
        begin = self.hub.wait_for(r"SECURE_FOTA_BEGIN transfer=(\d+) node=([^ ]+) board=([^ ]+) version=([^ ]+) bytes=(\d+)",
                                  30, cursor_hub)
        match = re.search(r"transfer=(\d+) node=([^ ]+) board=([^ ]+) version=([^ ]+) bytes=(\d+)", begin)
        if not match or match.group(2) != self.node_id or match.group(4) != version:
            raise RuntimeError("secure FOTA did not bind expected Node and candidate version")
        transfer_id = match.group(1)
        pinned = self.hub.wait_for(
            rf"SECURE_FOTA_SESSION_PINNED transfer={transfer_id} session=(\d+)", 10, cursor_hub)
        pinned_session = re.search(r"session=(\d+)", pinned).group(1)
        if pinned_session != self.before_session:
            raise RuntimeError("FOTA sender pinned a session other than the enrolled Node's current session")
        self.transfer_ids[version] = transfer_id
        self.c3.wait_for(rf"SECURE_FOTA_IMAGE_SHA256_VERIFIED transfer={transfer_id}",
                         1800, cursor_c3)
        if expect_signature_reject:
            rejected = self.c3.wait_for(r"SECURE_FOTA_IMAGE_SIGNATURE_REJECTED error=ESP_ERR_OTA_VALIDATE_FAILED",
                                        1800, cursor_c3)
            self.hub.wait_for(rf"SECURE_FOTA_TRANSFER_FAILED transfer={transfer_id} phase=end", 30, cursor_hub)
            return rejected
        self.c3.wait_for(r"FOTA COMPLETE; next boot partition=ota_[01]", 1800, cursor_c3)
        self.hub.wait_for(rf"SECURE_FOTA_TRANSFER_COMPLETE transfer={transfer_id} chunks=\d+", 30, cursor_hub)
        self.c3.wait_for(r"SECURE_FOTA_IMAGE_SIGNATURE_ACCEPTED", 30, cursor_c3)
        return transfer_id

    def run(self) -> dict:
        if self.config.get("HIL_IDF_ACTIVATE"):
            os.environ.setdefault("HW_IDF_ACTIVATE", self.config["HIL_IDF_ACTIVATE"])
        self.images = build_images(self.run_dir, self.config)
        self.hubs = build_hubs(self.images, self.run_dir, self.config)
        (self.run_dir / "signed_fota_artifacts.json").write_text(
            json.dumps({"images": self.images, "hubs": self.hubs}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        flash_signed_a(self.config, self.devices["c3"].port, self.images["A"], self.run_dir)
        flash_hub(self.config, self.devices["hub"].port, self.hubs["NEG"], self.run_dir, "negative")
        self.open()
        self.establish_fresh_node_session()
        state = self.state()
        self.before_slot = re.search(r"ota_slot=(ota_[01])", state).group(1)
        self.motion()

        self.active_case = EXPECTED[0]
        negative_cursor = self.c3.cursor()
        rejected = self.secure_transfer(self.images["NEG"]["version"],
                                        expect_signature_reject=True)
        after_negative = self.state()
        after_slot = re.search(r"ota_slot=(ota_[01])", after_negative).group(1)
        if after_slot != self.before_slot:
            raise RuntimeError(f"bad signature changed active slot {self.before_slot}->{after_slot}")
        if any(phase1.normalize_rom_reset_class(line) == phase1.SOFTWARE_RESET_EVIDENCE
               for line in self.c3.lines[negative_cursor:]):
            raise RuntimeError("C3 reset during bad-signature rejection")
        ready = re.search(r"HIL_READY role=c3 protocol=1 version=([^ ]+)", "\n".join(self.c3.lines))
        if not ready or ready.group(1) != self.images["A"]["version"]:
            raise RuntimeError("known-good signed A did not remain active after signature rejection")
        self.motion()
        self.results.add(EXPECTED[0], "PASS", "authenticated transfer reached ESP-IDF signature verifier; A stayed active and application ACK recovered")

        self.active_case = EXPECTED[1]
        self.close()
        self.c3 = self.hub = None
        flash_hub(self.config, phase1.runtime_port(self.config, "hub"), self.hubs["B"], self.run_dir, "positive")
        self.open()
        rejoin_cursor = self.hub.cursor()
        self.restart_and_ready(self.hub, "hub", self.hubs["B"]["hub_app_version"])
        old_session = self.before_session
        # The Node re-establishes its authenticated session after Hub reboot.
        joined = self.hub.wait_for(rf"Authenticated rejoin device={re.escape(self.node_id)} .*session=(\d+)",
                                   30, rejoin_cursor)
        self.before_session = re.search(r"session=(\d+)", joined).group(1)
        if self.before_session == old_session:
            raise RuntimeError("Hub restart did not establish a fresh authenticated session")
        self.before_slot = re.search(r"ota_slot=(ota_[01])", self.state()).group(1)
        session_after_hub_restart = self.before_session
        postboot_rejoin_cursor = self.hub.cursor()
        fota_session = self.before_session
        transfer = self.secure_transfer(self.images["B"]["version"], expect_signature_reject=False)
        self.results.add(EXPECTED[1], "PASS", f"authenticated signed B transfer completed transfer={transfer}")

        self.active_case = EXPECTED[2]
        c3_cursor = self.c3.cursor()
        self.c3.wait_for_predicate(lambda line: phase1.normalize_rom_reset_class(line) ==
            phase1.SOFTWARE_RESET_EVIDENCE, "fresh post-update C3 software reset", 30, c3_cursor)
        self.c3.wait_for(rf"HIL_READY role=c3 protocol=1 version={re.escape(self.images['B']['version'])}",
                         40, c3_cursor)
        self.c3.wait_for(r"PIR ready on GPIO", 50, c3_cursor)
        self.c3.wait_for(r"OTA image marked VALID after sensing/runtime/radio health", 100, c3_cursor)
        slot_state = self.state()
        final_slot = re.search(r"ota_slot=(ota_[01])", slot_state).group(1)
        if final_slot == self.before_slot:
            raise RuntimeError(f"valid B did not activate alternate slot {self.before_slot}")
        rejoined = self.hub.wait_for(
            rf"Authenticated rejoin device={re.escape(self.node_id)} .*session=(\d+)",
            40, postboot_rejoin_cursor)
        final_session = re.search(r"session=(\d+)", rejoined).group(1)
        if final_session == fota_session:
            raise RuntimeError("C3 did not establish a fresh authenticated session after FOTA reboot")
        self.motion()
        final_state = self.state(r"HIL_STATE role=c3 .*retained=0 in_flight=0 .*ota_slot=ota_[01]")
        self.results.add(EXPECTED[2], "PASS", f"B boot-health, alternate slot={final_slot}, authenticated rejoin and application ACK; {final_state.strip()}")
        self.results.add("SIGNED_FOTA_DIGEST", "PASS", "secure sender/receiver transfer completed with embedded image SHA-256 verification")
        return {"node_id": self.node_id, "a_slot_before": self.before_slot,
                "slot_after_negative": after_slot, "slot_after_b": final_slot,
                "signature_rejection_evidence": rejected, "transfer_id_b": transfer,
                "transfer_id_negative": self.transfer_ids[self.images["NEG"]["version"]],
                "session_before": old_session, "session_after_hub_restart": session_after_hub_restart,
                "session_after_c3_update": final_session,
                "artifacts": self.run_dir / "signed_fota_artifacts.json"}


def main() -> int:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = RUNS / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)
    campaign = None
    failure = None
    metadata: dict = {"commit": phase1.git("rev-parse", "HEAD"),
                      "branch": phase1.git("branch", "--show-current"),
                      "mode": "authenticated-signed-c3-fota", **host_metadata()}
    try:
        with FixtureLock(LOCK):
            devices, info = phase1.preflight(quiet=True)
            campaign = SecureCampaign(info["config"], devices, run_dir)
            metadata["fixture"] = {role: {"chip": device.chip, "mac": device.mac,
                                          "stable_path": device.stable_path}
                                   for role, device in devices.items()}
            result = campaign.run()
            metadata["secure_fota"] = result
            metadata["images"] = campaign.images
            metadata["hub_images"] = campaign.hubs
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        (run_dir / "failures").mkdir(exist_ok=True)
        (run_dir / "failures" / "secure_signed_fota.txt").write_text(failure + "\n", encoding="utf-8")
    finally:
        if campaign:
            campaign.close()
    results = campaign.results if campaign else Results()
    if failure:
        results.add(campaign.active_case if campaign else "SIGNED_FOTA_SETUP", "FAIL", failure)
        recorded = {row["id"] for row in results.rows}
        for tc in EXPECTED:
            if tc not in recorded:
                results.add(tc, "BLOCKED_BY_FIXTURE_STATE", "prerequisite campaign stage failed")
    counts = results.counts()
    payload = write_report(run_dir, metadata, results)
    (RUNS.parent / "latest.txt").write_text(str(run_dir) + "\n", encoding="utf-8")
    print(f"AUTHENTICATED SIGNED FOTA: {payload['overall']}")
    print(f"PASS={counts['PASS']} FAIL={counts['FAIL']} BLOCKED={counts['BLOCKED_BY_FIXTURE_STATE']}")
    print(f"report={run_dir}")
    return 0 if payload["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
