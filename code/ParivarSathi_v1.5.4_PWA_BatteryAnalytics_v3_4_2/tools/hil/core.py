"""Fail-closed, dependency-injectable primitives for the Hub+C3 HIL fixture."""
from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

PRODUCT = Path(__file__).resolve().parents[2]
REPO = PRODUCT.parents[1]
EXPECTED_HUB_MAC = "5c013bbeb9f8"
EXPECTED_C3_MAC = "146393c5d158"


def normalize_mac(value: str) -> str:
    return re.sub(r"[^0-9a-f]", "", value.lower())


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def source_fingerprint() -> str:
    tracked = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=REPO,
                             check=True, stdout=subprocess.PIPE).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                               cwd=REPO, check=True, text=True,
                               stdout=subprocess.PIPE).stdout.splitlines()
    digest = hashlib.sha256(tracked)
    for name in sorted(untracked):
        path = REPO / name
        digest.update(name.encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


@dataclasses.dataclass(frozen=True)
class Device:
    port: str
    mac: str
    chip: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    location: str | None = None
    stable_path: str | None = None


def assign_devices(devices: Iterable[Device], hub_mac: str, c3_mac: str) -> dict[str, Device]:
    rows = list(devices)
    expected = {"hub": normalize_mac(hub_mac), "c3": normalize_mac(c3_mac)}
    result: dict[str, Device] = {}
    for role, mac in expected.items():
        matches = [item for item in rows if normalize_mac(item.mac) == mac]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one {role} MAC {mac}; found {len(matches)}")
        result[role] = matches[0]
    if result["hub"].port == result["c3"].port:
        raise RuntimeError("Hub and C3 resolved to the same port")
    if "esp32-c3" in result["hub"].chip.lower() or "esp32-c3" not in result["c3"].chip.lower():
        raise RuntimeError(f"board type mismatch: hub={result['hub'].chip} c3={result['c3'].chip}")
    return result


class FixtureLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.seek(0)
            owner = self.handle.read().strip() or "unknown"
            self.handle.close()
            raise RuntimeError(f"HIL fixture is already locked by {owner}") from exc
        self.handle.seek(0); self.handle.truncate()
        self.handle.write(json.dumps({"pid": os.getpid(), "started": dt.datetime.now(dt.timezone.utc).isoformat()}))
        self.handle.flush()
        return self

    def __exit__(self, *_):
        if self.handle:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


class SerialCapture:
    """Timestamped duplex capture with bounded waits and clean cancellation."""
    def __init__(self, role: str, port: str, path: Path, serial_factory=None,
                 port_resolver: Callable[[], str] | None = None):
        import serial
        self.role, self.port, self.path = role, port, path
        self.serial_factory = serial_factory or serial.Serial
        self.port_resolver = port_resolver
        self.stream = None
        self.stream_lock = threading.RLock()
        self.stop_event = threading.Event()
        self.condition = threading.Condition()
        self.lines: list[str] = []
        self.thread: threading.Thread | None = None
        self.error = ""

    def start(self):
        if self.thread and self.thread.is_alive():
            raise RuntimeError(f"{self.role} serial capture is already running")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._open_stream(self.port)
        self.thread = threading.Thread(target=self._run, name=f"hil-{self.role}", daemon=True)
        self.thread.start()

    def _open_stream(self, port: str):
        """Replace the FD only after the old reader-side FD is closed."""
        candidate = self.serial_factory(port, 115200, timeout=.2, write_timeout=2,
                                        exclusive=True)
        with self.stream_lock:
            old = self.stream
            self.stream = candidate
            self.port = port
        if old and old is not candidate:
            with contextlib.suppress(Exception):
                old.close()

    def _run(self):
        pending = bytearray()
        while not self.stop_event.is_set():
            try:
                # Do not use readline(): pyserial returns a timeout fragment when
                # a target line is split across USB/UART reads.  Treating each
                # fragment as a line corrupts evidence and makes wait_for()
                # miss control acknowledgements.  Keep bytes until LF instead.
                with self.stream_lock:
                    stream = self.stream
                if not stream or not stream.is_open:
                    raise OSError("serial stream is closed")
                raw = stream.read(256)
                if not raw:
                    continue
                pending.extend(raw)
                while b"\n" in pending:
                    line_raw, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    self._record_line(line_raw)
            except Exception as exc:
                if pending:
                    self._record_line(bytes(pending))
                    pending.clear()
                if not self.port_resolver:
                    self.error = f"{type(exc).__name__}: {exc}"
                    with self.condition: self.condition.notify_all()
                    return
                with self.stream_lock:
                    failed_stream = self.stream
                with contextlib.suppress(Exception):
                    if failed_stream: failed_stream.close()
                deadline = time.monotonic() + 20
                while not self.stop_event.is_set() and time.monotonic() < deadline:
                    try:
                        # Always resolve and identity-verify again, even if the
                        # kernel reused the same tty name after a native-USB reset.
                        fresh_port = self.port_resolver()
                        self._open_stream(fresh_port)
                        self._record_line(f"SERIAL_RECONNECTED port={self.port}".encode())
                        break
                    except Exception:
                        time.sleep(.25)
                else:
                    self.error = f"USB reconnect failed after {type(exc).__name__}: {exc}"
                    with self.condition: self.condition.notify_all()
                    return

        if pending:
            self._record_line(bytes(pending))

    def _record_line(self, raw: bytes):
        message = raw.decode("utf-8", errors="replace").rstrip("\r")
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
        line = f"{stamp} [{self.role}] {message}"
        with self.condition:
            self.lines.append(line)
            with self.path.open("a", encoding="utf-8") as output:
                output.write(line + "\n")
            self.condition.notify_all()

    def send(self, command: str):
        with self.stream_lock:
            stream = self.stream
        if not stream or not stream.is_open:
            raise RuntimeError(f"{self.role} serial is not open")
        stream.write((command + "\n").encode())
        stream.flush()

    def wait_for(self, pattern: str, timeout: float, start: int = 0) -> str:
        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                for line in self.lines[start:]:
                    if compiled.search(line): return line
                if self.error: raise RuntimeError(f"{self.role} serial stopped: {self.error}")
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError(f"{self.role}: timeout waiting for {pattern}")
                self.condition.wait(min(remaining, 0.25))

    def wait_for_predicate(self, predicate: Callable[[str], bool], description: str,
                           timeout: float, start: int = 0) -> str:
        """Wait for a classified fresh line without reducing it to a regex-only contract."""
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                for line in self.lines[start:]:
                    if predicate(line):
                        return line
                if self.error:
                    raise RuntimeError(f"{self.role} serial stopped: {self.error}")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{self.role}: timeout waiting for {description}")
                self.condition.wait(min(remaining, 0.25))

    def wait_count(self, pattern: str, count: int, timeout: float, start: int = 0) -> list[str]:
        compiled = re.compile(pattern); deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                matches = [line for line in self.lines[start:] if compiled.search(line)]
                if len(matches) >= count: return matches
                if self.error: raise RuntimeError(f"{self.role} serial stopped: {self.error}")
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError(
                    f"{self.role}: got {len(matches)}/{count} lines matching {pattern}")
                self.condition.wait(min(remaining, .25))

    def cursor(self) -> int: return len(self.lines)

    def close(self):
        self.stop_event.set()
        with self.stream_lock:
            stream = self.stream
        # Closing first unblocks a reader held in a USB read promptly; join
        # then guarantees exactly one reader has finished before teardown.
        if stream:
            with contextlib.suppress(Exception): stream.close()
        if self.thread: self.thread.join(timeout=2)
        with self.stream_lock:
            self.stream = None
        self.thread = None


class Results:
    def __init__(self): self.rows: list[dict[str, str]] = []
    def add(self, tc: str, status: str, detail: str):
        self.rows.append({"id": tc, "status": status, "detail": detail})
    def counts(self):
        return {name: sum(row["status"] == name for row in self.rows)
                for name in ("PASS", "FAIL", "BLOCKED_EXTRA_FIXTURE", "BLOCKED_BY_FIXTURE_STATE")}
    def mandatory_pass(self):
        return all(row["status"] in ("PASS", "BLOCKED_EXTRA_FIXTURE") for row in self.rows)


def write_report(run_dir: Path, metadata: dict, results: Results):
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {**metadata, "tests": results.rows, "counts": results.counts(),
               "overall": "PASS" if results.mandatory_pass() else "FAIL"}
    (run_dir / "test_results.json").write_text(json.dumps(results.rows, indent=2) + "\n")
    (run_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    lines = [f"# HIL Phase 1 — {payload['overall']}", "", f"Commit: `{metadata.get('commit','unknown')}`", "",
             "| Test | Result | Detail |", "|---|---|---|"]
    lines += [f"| {r['id']} | {r['status']} | {r['detail'].replace('|','/')} |" for r in results.rows]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    return payload


def host_metadata() -> dict[str, str]:
    return {"platform": platform.platform(), "python": platform.python_version(),
            "hostname": platform.node()}
