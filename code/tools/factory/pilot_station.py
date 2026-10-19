"""GS-165 Pilot Provisioning Station v1 (host-only simulation).

This station cannot discover or provision boards. All credentials come from the
GS-168 TEST_ONLY issuer; simulated QA is never physical or delivery readiness.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import secrets
import sqlite3
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pilot_test_issuer import (  # noqa: E402
    TEST_ONLY, TestIssuerRejected, TestOnlyIssuer, new_test_csr,
)

STATES = {"NEW", "RESERVED", "TEST_CREDENTIAL_ISSUED", "SIMULATED_QA_PASS", "QUARANTINED"}
_HUB_ID = re.compile(r"test-hub-[a-z0-9][a-z0-9-]{0,31}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PROVENANCE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}\Z")
_TRANSITIONS = {
    "NEW": {"RESERVED", "QUARANTINED"},
    "RESERVED": {"TEST_CREDENTIAL_ISSUED", "QUARANTINED"},
    "TEST_CREDENTIAL_ISSUED": {"SIMULATED_QA_PASS", "QUARANTINED"},
    "SIMULATED_QA_PASS": {"QUARANTINED"},
    "QUARANTINED": {"RESERVED"},
}
_QUARANTINE_REASONS = {
    "identity_or_provenance_conflict", "credential_issuer_mismatch",
    "operator_review_retryable", "interrupted_registry_transaction", "test_failure",
}
_SENSITIVE_NAMES = {"private_key", "private_key_pem", "csr", "csr_pem", "password", "token", "secret", "home_id", "home_epoch", "node_credential"}


class StationError(ValueError):
    """A safe station refusal with no credential material in the message."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if str(k).lower() not in _SENSITIVE_NAMES}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, bytes):
        return "[excluded]"
    return value


@dataclass(frozen=True)
class Provenance:
    source_version: str
    firmware_version: str
    firmware_sha256: str
    source_head: str
    artifact_sha256: str

    def validate(self) -> None:
        if not all(isinstance(value, str) and _PROVENANCE_TOKEN.fullmatch(value) for value in
                   (self.source_version, self.firmware_version, self.source_head)):
            raise StationError("safe_provenance_token_required")
        for value in (self.firmware_sha256, self.artifact_sha256):
            if not _SHA256.fullmatch(value):
                raise StationError("sha256_provenance_required")


class ManufacturingRegistry:
    """Single-operator transactional SQLite identity and simulated-QA ledger."""

    def __init__(self, path: str | Path, issuer_fingerprint: str):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS station_meta (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                schema_version INTEGER NOT NULL CHECK(schema_version=1),
                environment TEXT NOT NULL CHECK(environment='TEST_ONLY'),
                issuer_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS devices (
                hub_id TEXT PRIMARY KEY,
                certificate_fingerprint TEXT UNIQUE,
                issuer_reference TEXT,
                source_version TEXT NOT NULL,
                firmware_version TEXT NOT NULL,
                firmware_sha256 TEXT NOT NULL,
                source_head TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                provisioning_state TEXT NOT NULL CHECK(provisioning_state IN
                    ('NEW','RESERVED','TEST_CREDENTIAL_ISSUED','SIMULATED_QA_PASS','QUARANTINED')),
                qa_result TEXT NOT NULL CHECK(qa_result IN ('NOT_RUN','SIMULATED_PASS','SIMULATED_FAIL')),
                qa_report_json TEXT NOT NULL,
                qr_handle TEXT NOT NULL UNIQUE,
                quarantine_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS station_audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                hub_id TEXT NOT NULL,
                action TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS station_audit_hub ON station_audit(hub_id,sequence);
        """)
        row = self.db.execute("SELECT environment,issuer_fingerprint FROM station_meta WHERE singleton=1").fetchone()
        if row is None:
            with self.transaction():
                self.db.execute("INSERT INTO station_meta VALUES (1,1,?,?)", (TEST_ONLY, issuer_fingerprint))
        elif tuple(row) != (TEST_ONLY, issuer_fingerprint):
            self.db.close()
            raise StationError("NOT_READY_TEST_ISSUER_MISMATCH")

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def get(self, hub_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM devices WHERE hub_id=?", (hub_id,)).fetchone()
        return dict(row) if row else None

    def all(self) -> list[dict]:
        return [dict(row) for row in self.db.execute("SELECT * FROM devices ORDER BY hub_id")]

    def _audit(self, hub_id: str, action: str, reason: str) -> None:
        self.db.execute("INSERT INTO station_audit(hub_id,action,reason_code,recorded_at) VALUES (?,?,?,?)",
                        (hub_id, action, reason, _now()))

    def reserve(self, hub_id: str, provenance: Provenance) -> dict:
        if not _HUB_ID.fullmatch(hub_id):
            raise StationError("invalid_test_hub_id")
        provenance.validate()
        current = self.get(hub_id)
        if current:
            same = all(current[k] == v for k, v in {
                "source_version": provenance.source_version,
                "firmware_version": provenance.firmware_version,
                "firmware_sha256": provenance.firmware_sha256,
                "source_head": provenance.source_head,
                "artifact_sha256": provenance.artifact_sha256,
            }.items())
            if same and current["provisioning_state"] == "SIMULATED_QA_PASS":
                return current
            if same and current["provisioning_state"] in {"RESERVED", "TEST_CREDENTIAL_ISSUED"}:
                return current
            if current["provisioning_state"] == "QUARANTINED":
                raise StationError("quarantined_record_requires_explicit_recovery")
            self.quarantine(hub_id, "identity_or_provenance_conflict")
            raise StationError("identity_or_provenance_conflict_quarantined")
        now = _now()
        qr = "gs://hub/v1/" + secrets.token_urlsafe(18)
        with self.transaction():
            self.db.execute("""INSERT INTO devices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (hub_id, None, None, provenance.source_version, provenance.firmware_version,
                 provenance.firmware_sha256, provenance.source_head, provenance.artifact_sha256,
                 "RESERVED", "NOT_RUN", "{}", qr, None, now, now))
            self._audit(hub_id, "RESERVED", "new_synthetic_identity")
        return self.get(hub_id)  # type: ignore[return-value]

    def transition(self, hub_id: str, new_state: str, *, certificate_fingerprint: str | None = None,
                  issuer_reference: str | None = None, qa_report: dict | None = None,
                  qa_result: str | None = None) -> dict:
        row = self.get(hub_id)
        if row is None:
            raise StationError("unknown_hub_id")
        old = row["provisioning_state"]
        if new_state not in _TRANSITIONS.get(old, set()):
            raise StationError("invalid_state_transition")
        if new_state == "SIMULATED_QA_PASS" and qa_result != "SIMULATED_PASS":
            raise StationError("simulated_pass_evidence_required")
        if new_state == "TEST_CREDENTIAL_ISSUED" and not (certificate_fingerprint and issuer_reference):
            raise StationError("verified_test_credential_reference_required")
        if new_state == "SIMULATED_QA_PASS" and not row["certificate_fingerprint"]:
            raise StationError("test_credential_required_for_simulated_qa")
        values = {
            "provisioning_state": new_state,
            "certificate_fingerprint": certificate_fingerprint or row["certificate_fingerprint"],
            "issuer_reference": issuer_reference or row["issuer_reference"],
            "qa_result": qa_result or row["qa_result"],
            "qa_report_json": json.dumps(_safe(qa_report or json.loads(row["qa_report_json"])), sort_keys=True),
            "updated_at": _now(),
        }
        with self.transaction():
            self.db.execute("""UPDATE devices SET certificate_fingerprint=?,issuer_reference=?,
                provisioning_state=?,qa_result=?,qa_report_json=?,updated_at=? WHERE hub_id=?""",
                (values["certificate_fingerprint"], values["issuer_reference"], values["provisioning_state"],
                 values["qa_result"], values["qa_report_json"], values["updated_at"], hub_id))
            self._audit(hub_id, new_state, "state_transition")
        return self.get(hub_id)  # type: ignore[return-value]

    def quarantine(self, hub_id: str, reason: str) -> dict:
        row = self.get(hub_id)
        if row is None:
            raise StationError("unknown_hub_id")
        if reason not in _QUARANTINE_REASONS:
            raise StationError("quarantine_reason_code_required")
        if row["provisioning_state"] == "QUARANTINED":
            if row["quarantine_reason"] == reason:
                return row
            raise StationError("quarantine_reason_is_immutable")
        if "QUARANTINED" not in _TRANSITIONS[row["provisioning_state"]]:
            raise StationError("invalid_state_transition")
        with self.transaction():
            self.db.execute("UPDATE devices SET provisioning_state='QUARANTINED',qa_result='SIMULATED_FAIL',quarantine_reason=?,updated_at=? WHERE hub_id=?",
                            (reason, _now(), hub_id))
            self._audit(hub_id, "QUARANTINED", reason)
        return self.get(hub_id)  # type: ignore[return-value]

    def recover(self, hub_id: str, confirmation: str) -> dict:
        row = self.get(hub_id)
        if row is None or row["provisioning_state"] != "QUARANTINED":
            raise StationError("quarantined_record_required")
        if confirmation != f"RECOVER {hub_id}":
            raise StationError("recovery_confirmation_mismatch")
        reason = row["quarantine_reason"] or "unknown"
        if reason not in _QUARANTINE_REASONS:
            raise StationError("unknown_quarantine_reason_fails_closed")
        # Identity and provenance conflicts need a separately allocated Hub ID.
        if reason == "identity_or_provenance_conflict":
            raise StationError("conflicting_identity_requires_new_hub_id")
        with self.transaction():
            self.db.execute("UPDATE devices SET provisioning_state='RESERVED',qa_result='NOT_RUN',quarantine_reason=NULL,updated_at=? WHERE hub_id=?",
                            (_now(), hub_id))
            self._audit(hub_id, "RESERVED", "operator_recovery:" + reason)
        return self.get(hub_id)  # type: ignore[return-value]

    def report(self, hub_id: str) -> dict:
        row = self.get(hub_id)
        if row is None:
            raise StationError("unknown_hub_id")
        return _report_row(row)


def _report_row(row: dict, *, credential_verification: str | None = None) -> dict:
    qa = _safe(json.loads(row["qa_report_json"]))
    report = {
            "report_version": 1,
            "label": "SIMULATED",
            "permanent_hub_id": row["hub_id"],
            "certificate_fingerprint_sha256": row["certificate_fingerprint"],
            "issuer_reference": row["issuer_reference"],
            "source_version": row["source_version"],
            "firmware_version": row["firmware_version"],
            "firmware_sha256": row["firmware_sha256"],
            "source_head": row["source_head"],
            "artifact_sha256": row["artifact_sha256"],
            "provisioning_state": row["provisioning_state"],
            "qa_result": row["qa_result"],
            "qa_checks": qa,
            "public_qr": "gs://hub/v1/" + row["qr_handle"].removeprefix("gs://hub/v1/"),
            "physical_qa": "NOT_RUN",
            "delivery_readiness": "NOT_READY_SIMULATION_ONLY",
            "quarantine_reason": row["quarantine_reason"],
            "updated_at": row["updated_at"],
        }
    if credential_verification:
        report["credential_verification"] = credential_verification
    return report


def _read_registry_reports(path: str | Path, hub_id: str | None = None) -> list[dict]:
    uri = "file:" + str(Path(path).resolve()) + "?mode=ro"
    try:
        db = sqlite3.connect(uri, uri=True)
        db.row_factory = sqlite3.Row
        meta = db.execute("SELECT environment FROM station_meta WHERE singleton=1").fetchone()
        if not meta or meta["environment"] != TEST_ONLY:
            raise StationError("NOT_READY_SECURITY_APPROVAL")
        if hub_id is None:
            rows = db.execute("SELECT * FROM devices ORDER BY hub_id").fetchall()
        else:
            rows = db.execute("SELECT * FROM devices WHERE hub_id=?", (hub_id,)).fetchall()
        if hub_id is not None and not rows:
            raise StationError("unknown_hub_id")
        return [_report_row(dict(row), credential_verification="NOT_REPEATED_AUTHORITY_KEY_EPHEMERAL") for row in rows]
    except sqlite3.Error as error:
        raise StationError("registry_read_failed") from error
    finally:
        if "db" in locals():
            db.close()


class PilotStation:
    def __init__(self, registry: ManufacturingRegistry, issuer: TestOnlyIssuer):
        self.registry = registry
        self.issuer = issuer
        if getattr(issuer, "environment", TEST_ONLY) != TEST_ONLY:
            raise StationError("NOT_READY_SECURITY_APPROVAL")
        if issuer.authority.fingerprint != self.registry_issuer_fingerprint:
            raise StationError("NOT_READY_TEST_ISSUER_MISMATCH")

    @property
    def registry_issuer_fingerprint(self) -> str:
        row = self.registry.db.execute("SELECT issuer_fingerprint FROM station_meta WHERE singleton=1").fetchone()
        return row[0]

    def simulate_one(self, hub_id: str, provenance: Provenance, *, interrupt_at: str | None = None) -> dict:
        record = self.registry.reserve(hub_id, provenance)
        if record["provisioning_state"] == "SIMULATED_QA_PASS":
            return self.registry.report(hub_id)
        if record["provisioning_state"] == "RESERVED":
            # A resumed record can reuse an already issued public test cert when
            # the same TEST_ONLY authority and issuer DB survive the interruption.
            active = self.issuer.active_credential_for_hub(hub_id)
            if active is None:
                _, csr = new_test_csr(hub_id)
                credential = self.issuer.issue(hub_id, csr)
            else:
                credential = active
            verified = self.issuer.verify(credential.certificate_pem, hub_id)
            self.registry.transition(hub_id, "TEST_CREDENTIAL_ISSUED",
                                     certificate_fingerprint=verified.fingerprint,
                                     issuer_reference=verified.issuer_fingerprint)
            if interrupt_at == "after_credential":
                raise InterruptedError("simulated_interruption_after_credential")
        record = self.registry.get(hub_id)
        if record["provisioning_state"] == "TEST_CREDENTIAL_ISSUED":
            active = self.issuer.active_credential_for_hub(hub_id)
            if (not active or active.fingerprint != record["certificate_fingerprint"] or
                    active.issuer_fingerprint != record["issuer_reference"]):
                self.registry.quarantine(hub_id, "credential_issuer_mismatch")
                raise StationError("credential_issuer_mismatch_quarantined")
            self.issuer.verify(active.certificate_pem, hub_id)
        checks = {"test_issuer_signature": "PASS", "hub_binding": "PASS",
                  "provenance_present": "PASS", "qr_public_only": "PASS",
                  "physical_hardware_test": "NOT_RUN"}
        if interrupt_at == "before_qa_commit":
            # The registry transaction is rolled back; the already issued
            # TEST_ONLY credential remains discoverable for an idempotent retry.
            self.registry.db.execute("BEGIN IMMEDIATE")
            try:
                self.registry.db.execute("UPDATE devices SET provisioning_state='SIMULATED_QA_PASS',qa_result='SIMULATED_PASS',qa_report_json=?,updated_at=? WHERE hub_id=?",
                                         (json.dumps(checks, sort_keys=True), _now(), hub_id))
                self.registry._audit(hub_id, "SIMULATED_QA_PASS", "state_transition")
                raise InterruptedError("simulated_interruption_during_registry_transaction")
            except InterruptedError:
                self.registry.db.rollback()
                raise
        self.registry.transition(hub_id, "SIMULATED_QA_PASS", qa_report=checks, qa_result="SIMULATED_PASS")
        return self.registry.report(hub_id)

    def simulate_batch(self, count: int, provenance: Provenance, *, prefix: str = "test-hub") -> list[dict]:
        if type(count) is not int or not 1 <= count <= 100:
            raise StationError("batch_size_must_be_1_to_100")
        return [self.simulate_one(f"{prefix}-{n:03d}", provenance) for n in range(1, count + 1)]

    def verify(self, hub_id: str) -> dict:
        row = self.registry.get(hub_id)
        if not row or not row["certificate_fingerprint"]:
            raise StationError("credential_not_registered")
        credential = self.issuer.active_credential_for_hub(hub_id)
        if not credential or credential.fingerprint != row["certificate_fingerprint"]:
            self.registry.quarantine(hub_id, "credential_issuer_mismatch")
            raise StationError("credential_issuer_mismatch_quarantined")
        verified = self.issuer.verify(credential.certificate_pem, hub_id)
        if verified.issuer_fingerprint != row["issuer_reference"]:
            self.registry.quarantine(hub_id, "credential_issuer_mismatch")
            raise StationError("credential_issuer_mismatch_quarantined")
        return self.registry.report(hub_id)

    def resume(self, hub_id: str, provenance: Provenance) -> dict:
        row = self.registry.get(hub_id)
        if row and row["provisioning_state"] == "QUARANTINED":
            raise StationError("quarantined_record_requires_explicit_recovery")
        return self.simulate_one(hub_id, provenance)

    def export(self) -> list[dict]:
        return [_safe(self.registry.report(row["hub_id"])) for row in self.registry.all()]


def _provenance(args) -> Provenance:
    return Provenance(args.source_version, args.firmware_version, args.firmware_sha256,
                      args.source_head, args.artifact_sha256)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GS-165 TEST_ONLY pilot station; no hardware access")
    parser.add_argument("--registry", default="pilot-station.sqlite3")
    parser.add_argument("--issuer-db", default=None, help="TEST_ONLY issuer metadata DB")
    parser.add_argument("--environment", default=TEST_ONLY, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    def provenance_options(command):
        command.add_argument("--source-version", required=True)
        command.add_argument("--firmware-version", required=True)
        command.add_argument("--firmware-sha256", required=True)
        command.add_argument("--source-head", required=True)
        command.add_argument("--artifact-sha256", required=True)
    one = sub.add_parser("simulate-one"); one.add_argument("hub_id"); provenance_options(one)
    batch = sub.add_parser("simulate-batch"); batch.add_argument("--count", type=int, required=True); batch.add_argument("--prefix", default="test-hub"); provenance_options(batch)
    for name in ("verify", "resume", "quarantine", "recover"):
        command = sub.add_parser(name); command.add_argument("hub_id")
        if name in {"resume", "recover"}: provenance_options(command)
        if name == "quarantine": command.add_argument("--reason", required=True, choices=sorted(_QUARANTINE_REASONS - {"identity_or_provenance_conflict", "credential_issuer_mismatch"}))
        if name == "recover": command.add_argument("--confirm", required=True)
    sub.add_parser("export-public")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.environment != TEST_ONLY:
        print("NOT_READY_SECURITY_APPROVAL"); return 2
    if args.command in {"verify", "export-public"}:
        try:
            value = (_read_registry_reports(args.registry, args.hub_id)[0]
                     if args.command == "verify" else _read_registry_reports(args.registry))
            print(json.dumps(_safe(value), sort_keys=True, indent=2)); return 0
        except StationError as error:
            print(json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True)); return 2
    if args.command == "resume":
        try:
            row = _read_registry_reports(args.registry, args.hub_id)[0]
            expected = _provenance(args)
            expected.validate()
            if row["provisioning_state"] == "SIMULATED_QA_PASS" and all(row[k] == v for k, v in {
                    "source_version": expected.source_version, "firmware_version": expected.firmware_version,
                    "firmware_sha256": expected.firmware_sha256, "source_head": expected.source_head,
                    "artifact_sha256": expected.artifact_sha256}.items()):
                print(json.dumps(row, sort_keys=True, indent=2)); return 0
            raise StationError("NOT_READY_TEST_ISSUER_AUTHORITY_LOST")
        except StationError as error:
            print(json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True)); return 2
    issuer_path = args.issuer_db or (args.registry + ".gs168-test-only.sqlite3")
    issuer = registry = None
    try:
        issuer = TestOnlyIssuer(issuer_path, environment=TEST_ONLY)
        registry = ManufacturingRegistry(args.registry, issuer.authority.fingerprint)
        station = PilotStation(registry, issuer)
        if args.command in {"simulate-one", "simulate-batch", "resume"}:
            provenance = _provenance(args)
            value = (station.simulate_one(args.hub_id, provenance) if args.command == "simulate-one"
                     else station.simulate_batch(args.count, provenance, prefix=args.prefix) if args.command == "simulate-batch"
                     else station.resume(args.hub_id, provenance))
        elif args.command == "verify": value = station.verify(args.hub_id)
        elif args.command == "quarantine": value = registry.quarantine(args.hub_id, args.reason)
        elif args.command == "recover":
            registry.recover(args.hub_id, args.confirm)
            value = station.resume(args.hub_id, _provenance(args))
        else: value = station.export()
        print(json.dumps(_safe(value), sort_keys=True, indent=2))
        return 0
    except (StationError, TestIssuerRejected) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True)); return 2
    except InterruptedError as error:
        print(json.dumps({"status": "INTERRUPTED", "reason": str(error)})); return 3
    finally:
        if registry:
            registry.close()
        if issuer:
            issuer.close()


if __name__ == "__main__":
    raise SystemExit(main())
