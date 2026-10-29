"""Bounded, redacted evidence retention for the existing GS-117 bootstrap child.

This module is used only by the owner-authorized private readiness procedure.
It never reads configuration or credentials and never writes raw child output.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any


EVIDENCE_NAME = "bootstrap-child-result.json"
MAX_CHILD_OUTPUT_BYTES = 1_000_000
MAX_LINE_CHARS = 1024
MAX_LINES_PER_DEVICE = 300
MAX_STDERR_LINES = 20

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passphrase|psk|private[_ -]?key|public[_ -]?key|"
    r"key[_ -]?material|credential|secret|token|nonce|encrypted[_ -]?(?:envelope|config))"
    r"\b\s*[:=]\s*)([^\s,;]+)"
)
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9+/=_-]{48,}\b")
_SAFE_CODE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_RESPONSE_FIELDS = frozenset({
    "stage", "error", "status", "reason", "proof", "c3", "s3",
    "c3_status_queries", "s3_config_receive_pending", "s3_status_command_ready",
    "s3_status_command_sent", "bootstrap_host_write_bytes", "bootstrap_exchange_ms",
    "bootstrap_timeline", "observation", "node_id", "hub_id", "home_id", "liveness",
    "status", "flash_size_bytes", "psram_size_bytes", "evidence_lines",
})
_TIMELINE_FIELDS = frozenset({
    "stage", "status", "reason", "elapsed_ms", "bytes", "response_bytes",
    "device", "port", "challenge_stage", "observed", "attempt", "s3_memory_capacity",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: str) -> str:
    value = value[:MAX_LINE_CHARS]
    value = _SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", value)
    return _LONG_TOKEN.sub("[REDACTED_TOKEN]", value)


def _safe_value(value: Any, *, timeline: bool = False, depth: int = 0) -> Any:
    if depth > 5:
        return "[TRUNCATED]"
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, list):
        limit = MAX_LINES_PER_DEVICE if all(isinstance(item, str) for item in value) else 100
        return [_safe_value(item, timeline=timeline, depth=depth + 1)
                for item in value[:limit]]
    if isinstance(value, dict):
        allowed = _TIMELINE_FIELDS if timeline else _RESPONSE_FIELDS
        return {str(key): _safe_value(item, timeline=(key == "bootstrap_timeline"),
                                      depth=depth + 1)
                for key, item in list(value.items()) if key in allowed}
    return "[UNSUPPORTED_VALUE]"


def _safe_response(raw: str) -> dict[str, Any] | None:
    if len(raw.encode("utf-8", "replace")) > MAX_CHILD_OUTPUT_BYTES:
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    return _safe_value(value)


def _private_directory(directory: str | os.PathLike[str]) -> Path:
    path = Path(directory)
    try:
        info = path.lstat()
    except OSError:
        raise ValueError("PRIVATE_BOOTSTRAP_EVIDENCE_DIRECTORY_REQUIRED") from None
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or
            info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise ValueError("PRIVATE_BOOTSTRAP_EVIDENCE_DIRECTORY_REQUIRED")
    return path


def _digest(text: str) -> dict[str, int | str]:
    encoded = text.encode("utf-8", "replace")
    return {"bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}


def _challenge_summary(line: str | None) -> dict[str, Any] | None:
    if not line:
        return None
    try:
        value = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return {"status": "MALFORMED", **_digest(line)}
    if not isinstance(value, dict):
        return {"status": "MALFORMED", **_digest(line)}
    stage = value.get("stage")
    error = value.get("error")
    return {
        "status": "VALID",
        "stage": stage if isinstance(stage, str) and _SAFE_CODE.fullmatch(stage) else None,
        "error": error if isinstance(error, str) and _SAFE_CODE.fullmatch(error) else None,
        **_digest(line),
    }


def _stderr_summary(stderr: str) -> list[str]:
    return [_text(line) for line in stderr.splitlines()[:MAX_STDERR_LINES]
            if line.strip()][:MAX_STDERR_LINES]


def _persist(directory: str | os.PathLike[str], payload: dict[str, Any]) -> Path:
    root = _private_directory(directory)
    target = root / EVIDENCE_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError:
        raise ValueError("BOOTSTRAP_CHILD_EVIDENCE_ALREADY_EXISTS") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return target


def _record(directory: str | os.PathLike[str], *, stage: str, started_at: str,
            challenge_received_at: str | None, stdout: str, stderr: str,
            exit_code: int | None, interruption: str | None = None,
            failure_code: str | None = None, finished_at: str | None = None,
            elapsed_ms: int | None = None,
            challenge_line: str | None = None) -> dict[str, Any]:
    response = _safe_response(stdout)
    response_status = ("OVERSIZE" if len(stdout.encode("utf-8", "replace")) > MAX_CHILD_OUTPUT_BYTES
                       else "VALID" if response is not None else "MALFORMED")
    child_error = response.get("error") if response else None
    if not isinstance(child_error, str) or not _SAFE_CODE.fullmatch(child_error):
        child_error = "CHILD_ERROR_UNAVAILABLE" if child_error is not None else None
    finished = finished_at or _utc_now()
    if elapsed_ms is None:
        try:
            elapsed_ms = max(0, int((datetime.fromisoformat(finished) -
                                     datetime.fromisoformat(started_at)).total_seconds() * 1000))
        except (TypeError, ValueError):
            elapsed_ms = None
    record = {
        "schema_version": 1,
        "parent_stage": _text(stage),
        "started_at": started_at,
        "challenge_received_at": challenge_received_at,
        "challenge": _challenge_summary(challenge_line),
        "finished_at": finished,
        "elapsed_ms": elapsed_ms,
        "child_exit_code": exit_code,
        "child_outcome": "INTERRUPTED" if interruption else "EXITED",
        "interruption": interruption,
        "parent_failure_code": (failure_code if isinstance(failure_code, str) and
                                 _SAFE_CODE.fullmatch(failure_code) else None),
        "response_status": response_status,
        "child_error": child_error,
        "stdout": _digest(stdout),
        "stderr": _digest(stderr),
        "stderr_safe_summary": _stderr_summary(stderr),
        "response": response,
    }
    _persist(directory, record)
    return record


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def wait_and_record_child(proc: Any, directory: str | os.PathLike[str], *,
                          stage: str, started_at: str,
                          challenge_received_at: str | None,
                          timeout_seconds: int = 85,
                          challenge_line: str | None = None) -> dict[str, Any]:
    """Wait once for the child, persist a redacted result, then evaluate success.

    A timeout/interruption kills and drains this one child, records its exit and
    any valid observations, then propagates the original interruption. It never
    starts or retries a hardware operation.
    """
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise ValueError("BOOTSTRAP_CHILD_TIMEOUT_OUT_OF_RANGE")
    interruption: str | None = None
    failure_code: str | None = None
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except BaseException as error:
        interruption = ("timeout" if isinstance(error, subprocess.TimeoutExpired)
                        else type(error).__name__)
        failure_code = "BOOTSTRAP_CHILD_TIMEOUT" if interruption == "timeout" else "BOOTSTRAP_CHILD_INTERRUPTED"
        try:
            if proc.poll() is None:
                proc.kill()
            stdout, stderr = proc.communicate()
        except BaseException:
            stdout = getattr(error, "output", None)
            stderr = getattr(error, "stderr", None)
        _record(directory, stage=stage, started_at=started_at,
                challenge_received_at=challenge_received_at,
                stdout=_as_text(stdout), stderr=_as_text(stderr),
                exit_code=proc.returncode, interruption=interruption,
                failure_code=failure_code,
                challenge_line=challenge_line)
        if isinstance(error, subprocess.TimeoutExpired):
            raise ValueError("BOOTSTRAP_CHILD_TIMEOUT") from None
        raise

    stdout_text, stderr_text = _as_text(stdout), _as_text(stderr)
    record = _record(directory, stage=stage, started_at=started_at,
                     challenge_received_at=challenge_received_at,
                     stdout=stdout_text, stderr=stderr_text,
                     exit_code=proc.returncode,
                     challenge_line=challenge_line)
    if record["response_status"] != "VALID":
        raise ValueError("BOOTSTRAP_CHILD_RESPONSE_MALFORMED")
    if proc.returncode:
        raise ValueError("BOOTSTRAP_CHILD_" + (record["child_error"] or "FAILED"))
    return record["response"]


def record_interrupted_child(proc: Any, directory: str | os.PathLike[str], *,
                             stage: str, started_at: str,
                             challenge_received_at: str | None,
                             parent_error: BaseException,
                             challenge_line: str | None = None) -> Path:
    """Stop a child when the parent fails before its normal result wait."""
    try:
        if proc.poll() is None:
            proc.kill()
        stdout, stderr = proc.communicate()
    except BaseException:
        stdout = getattr(parent_error, "output", None)
        stderr = getattr(parent_error, "stderr", None)
    interruption = type(parent_error).__name__
    parent_code = str(parent_error)
    if not _SAFE_CODE.fullmatch(parent_code):
        parent_code = "BOOTSTRAP_PARENT_INTERRUPTED"
    return _persist_record_path(directory, stage=stage, started_at=started_at,
                                challenge_received_at=challenge_received_at,
                                stdout=_as_text(stdout), stderr=_as_text(stderr),
                                exit_code=proc.returncode, interruption=interruption,
                                failure_code=parent_code,
                                challenge_line=challenge_line)


def _persist_record_path(directory: str | os.PathLike[str], **kwargs: Any) -> Path:
    # _record intentionally exposes the record only after its durable write.
    _record(directory, **kwargs)
    return Path(directory) / EVIDENCE_NAME
