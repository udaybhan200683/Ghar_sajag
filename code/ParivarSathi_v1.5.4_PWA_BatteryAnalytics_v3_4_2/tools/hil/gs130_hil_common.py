"""Shared, read-only GS-130 HIL collection primitives; no command/injection API."""
from __future__ import annotations
import hashlib
import json
import csv
from pathlib import Path
import re
import threading
import time
from datetime import datetime, timezone
import subprocess

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
REPO = PRODUCT.parents[1]
PHYSICAL_CATALOGUE = REPO / "docs/validation/PHYSICAL_HIL_CATALOGUE.csv"
FIXTURE = json.loads((HERE / "gs130_fixture.json").read_text())
TOKEN = f"OBSERVE {FIXTURE['fixture_id']}"


def catalogue_test_ids():
    with PHYSICAL_CATALOGUE.open(newline="", encoding="utf-8") as stream:
        return {row["TEST_ID"] for row in csv.DictReader(stream)}


def report_exit_code(status):
    return 0 if status == "PASS" else (1 if status == "FAIL" else 3)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact(line: str) -> str:
    line = re.sub(r"(?i)(installer[_ -]?code|private[_ -]?key|identity[_ -]?scalar|session[_ -]?key|credential|secret)(\s*[:=]\s*)\S+", r"\1\2[REDACTED]", line)
    return line


def verify_preflight(c3_port, s3_port, c3_image, s3_image):
    failures = []
    for name, given_port, image in (("c3", c3_port, c3_image), ("s3", s3_port, s3_image)):
        expected = FIXTURE["boards"][name]
        if given_port != expected["by_id"]:
            failures.append(f"{name}: port must be the exact fixture by-id path")
        elif not Path(given_port).exists():
            failures.append(f"{name}: stable fixture interface is unavailable")
        else:
            try:
                enumerated = subprocess.run(
                    ["udevadm", "info", "--query=property", "--name", given_port],
                    capture_output=True, text=True, timeout=3, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                failures.append(f"{name}: read-only USB identity enumeration unavailable: {error}")
            else:
                properties = dict(
                    line.split("=", 1) for line in enumerated.stdout.splitlines() if "=" in line
                )
                actual_serial = properties.get("ID_SERIAL_SHORT")
                if enumerated.returncode != 0:
                    failures.append(f"{name}: udevadm could not identify the stable interface")
                elif actual_serial != expected["usb_serial_short"]:
                    failures.append(
                        f"{name}: USB serial mismatch (expected {expected['usb_serial_short']}, observed {actual_serial or 'missing'})"
                    )
        if image is None or not Path(image).is_file():
            failures.append(f"{name}: matching image artifact was not supplied")
        elif sha256(Path(image)) != expected["image_sha256"]:
            failures.append(f"{name}: image SHA-256 does not match attempt06 fixture evidence")
    return failures


def status_from_logs(case_id, c3_text, s3_text):
    all_text = c3_text + "\n" + s3_text
    if case_id == "HIL-A04":
        return "NOT_RUN", "Offline threshold requires outage stimulus, excluded from observational run."
    if case_id == "HIL-A08":
        return "NOT_RUN", "Loss/replay/offline negative stimulus is not permitted in this runner."
    if case_id == "HIL-A01":
        has_identity = all(token.lower() in all_text.lower() for token in (FIXTURE["boards"]["c3"]["mac"], FIXTURE["boards"]["s3"]["mac"]))
        has_version = FIXTURE["firmware_version"] in all_text
        if has_identity and has_version:
            return "BLOCKED", "Identity/version banner observed; running image hash and config fingerprint are not emitted by firmware."
        return "BLOCKED", "Exact board identity and firmware profile were not both observed in this UART capture."
    if case_id == "HIL-A02":
        c3_link = re.search(r"authenticated.*(?:rejoin|session|NodeHealth)", c3_text, re.I)
        s3_link = re.search(r"authenticated.*(?:Node|session|rejoin)|(?:Node|session|rejoin).*authenticated", s3_text, re.I)
        return ("PASS", "Authenticated link/session markers were observed independently at C3 and S3.") if c3_link and s3_link else ("NOT_RUN", "Both C3 and S3 authenticated-link markers are required.")
    if case_id == "HIL-A03":
        return ("PASS", "Hub accepted authenticated NodeHealth in the bounded observation.") if re.search(r"NodeHealth.*(?:accepted|authenticated)|authenticated.*NodeHealth", s3_text, re.I) else ("NOT_RUN", "No accepted authenticated NodeHealth evidence was observed.")
    if case_id == "HIL-A05":
        key = re.search(r"(?:EventKey|event_key)\s*[:=]\s*([A-Za-z0-9:._-]+)", all_text, re.I)
        if key is None:
            return "NOT_RUN", "No identifiable EventKey was observed."
        event_key = key.group(1)
        ack = any(event_key in line and re.search(r"authenticated", line, re.I) and
                  re.search(r"Durable ACK|durable_ack|ACK=Durable", line, re.I)
                  for line in s3_text.splitlines())
        retired = any(event_key in line and re.search(r"retired|pending=0", line, re.I)
                      for line in c3_text.splitlines())
        return ("PASS", "Same EventKey is present on authenticated Durable ACK and Node retirement evidence.") if ack and retired else ("NOT_RUN", "No correlated EventKey→authenticated Durable ACK→retirement transaction was observed.")
    if case_id == "HIL-A06":
        bad = re.search(r"unexpected reset|panic|abort|fatal error", all_text, re.I)
        if bad:
            return "FAIL", "Unexpected reset or fatal runtime marker observed."
        if c3_text.strip() and s3_text.strip():
            return "PARTIAL", "No fatal marker appeared, but this capture cannot establish reset-counter continuity, heap/resource trend or queue/in-flight stability."
        return "NOT_RUN", "Both serial observations must contain runtime output."
    if case_id == "HIL-A07":
        return ("PASS", "Timer/light-sleep telemetry observed; this does not prove GPIO wake.") if re.search(r"timer[_ -]?(?:wake|wakes)|sleep[_ -]?entries", all_text, re.I) else ("NOT_RUN", "No target sleep/timer telemetry was observed.")
    return "NOT_RUN", "No classifier exists for this case."


class ReadOnlyCapture:
    def __init__(self, ports, serial_module=None):
        self.ports = ports
        self.serial_module = serial_module
        self.devices = []
        self.lines = {name: [] for name in ports}
        self.stop = threading.Event()
        self.threads = []

    def open(self):
        if self.serial_module is None:
            import serial as serial_module
            self.serial_module = serial_module
        for name, port in self.ports.items():
            device = self.serial_module.Serial(port=None, baudrate=115200, timeout=0.2,
                                               dsrdtr=False, rtscts=False, write_timeout=0)
            device.dtr = False
            device.rts = False
            device.port = port
            device.open()
            self.devices.append((name, device))
        for name, device in self.devices:
            thread = threading.Thread(target=self._read, args=(name, device), daemon=True)
            thread.start()
            self.threads.append(thread)

    def _read(self, name, device):
        while not self.stop.is_set():
            data = device.readline()
            if data:
                self.lines[name].append(redact(data.decode("utf-8", errors="replace").rstrip()))

    def window(self, seconds):
        self.lines = {name: [] for name in self.ports}
        time.sleep(seconds)
        return {name: "\n".join(lines) for name, lines in self.lines.items()}

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=1)
        for _, device in self.devices:
            device.close()


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")


def create_evidence_dir(requested, label):
    """Create a new evidence directory; never overwrite a prior physical record."""
    if requested is not None:
        path = Path(requested)
        if path.exists():
            if not path.is_dir() or any(path.iterdir()):
                raise FileExistsError(f"refusing to overwrite existing HIL evidence: {path}")
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = PRODUCT / "build" / f"{label}_{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def current_source_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
