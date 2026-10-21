"""Bounded, restart-safe delivery worker for the existing durable notification outbox.

The provider is injected. This module does not create provider credentials,
resolve destinations, or claim that provider acceptance means phone delivery.
"""
from __future__ import annotations

import json
import importlib
import logging
import os
import random
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Protocol


LOG = logging.getLogger("ghar_sajag.notification_worker")


@dataclass(frozen=True)
class Delivery:
    outbox_id: str
    home_id: str
    recipient_id: str
    stage: int
    event_type: str
    severity: str


@dataclass(frozen=True)
class ProviderResult:
    accepted: bool
    reference: str | None = None
    retryable: bool = True


class NotificationProvider(Protocol):
    """GS-74 adapter boundary; send must enforce its declared network timeout."""

    max_send_seconds: int
    def ready(self) -> bool: ...
    def send(self, delivery: Delivery, *, idempotency_key: str) -> ProviderResult: ...


class NotificationWorker:
    def __init__(self, db, provider: NotificationProvider, *, now=None, random_value=None,
                 batch_size: int = 10, lease_seconds: int = 60, max_attempts: int = 5,
                 base_retry_seconds: int = 10, max_retry_seconds: int = 900,
                 jitter_fraction: float = 0.2):
        if not callable(getattr(provider, "send", None)) or not callable(getattr(provider, "ready", None)):
            raise ValueError("trusted_notification_provider_required")
        if not 1 <= batch_size <= 100 or not 1 <= lease_seconds <= 3600:
            raise ValueError("invalid_worker_bounds")
        send_bound = getattr(provider, "max_send_seconds", None)
        if type(send_bound) is not int or not 1 <= send_bound <= 30 or lease_seconds < send_bound + 5:
            raise ValueError("provider_timeout_must_fit_inside_lease")
        if not 1 <= max_attempts <= 20 or not 1 <= base_retry_seconds <= max_retry_seconds <= 86400:
            raise ValueError("invalid_retry_bounds")
        if not 0 <= jitter_fraction <= 0.5:
            raise ValueError("invalid_jitter_fraction")
        self.db = db
        self.provider = provider
        self.now = now or (lambda: int(time.time()))
        self.random_value = random_value or random.random
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        self.max_retry_seconds = max_retry_seconds
        self.jitter_fraction = jitter_fraction

    def ready(self) -> bool:
        try:
            self.db.execute("SELECT 1").fetchone()
            return self.provider.ready() is True
        except Exception:
            return False

    def run_once(self) -> dict[str, int]:
        """Process a bounded batch while claiming each row immediately before use."""
        if not self.ready():
            raise RuntimeError("notification_worker_not_ready")
        metrics = {"claimed": 0, "accepted": 0, "retry_scheduled": 0,
                   "failed": 0, "expired_leases": 0, "cancelled": 0}
        for _ in range(self.batch_size):
            claims = self._claim(int(self.now()), metrics, limit=1)
            if not claims:
                break
            metrics["claimed"] += 1
            # If the lease was replaced or expired while processing, stop this
            # cycle. A later poll can safely reclaim it without starving other
            # rows in this batch or sending under an expired lease.
            if not self._process_claim(claims[0], metrics):
                break
        return metrics

    def _process_claim(self, row: dict, metrics: dict[str, int]) -> bool:
        if not self._authorized(row):
            reason = "INCIDENT_NOT_ACTIVE" if row.get("alert_id") and row.get("alert_state") not in ("OPEN", "CLAIMED") else "AUTHORIZATION_DENIED"
            finished = self._finish(row, state="FAILED", reason=reason)
            if finished:
                metrics["cancelled" if reason == "INCIDENT_NOT_ACTIVE" else "failed"] += 1
            return finished
        delivery = Delivery(row["outbox_id"], row["home_id"], row["recipient_id"],
                            row["stage"], row["event_type"],
                            "URGENT" if row["event_type"] == "CALL_FAMILY" else "CONCERN")
        try:
            result = self.provider.send(delivery, idempotency_key=row["outbox_id"])
            if not isinstance(result, ProviderResult):
                raise TypeError("invalid_provider_result")
        except TimeoutError:
            result = ProviderResult(False, retryable=True)
            error_class = "TIMEOUT"
        except (ConnectionError, OSError):
            result = ProviderResult(False, retryable=True)
            error_class = "NETWORK"
        except Exception:
            result = ProviderResult(False, retryable=True)
            error_class = "PROVIDER_ERROR"
        else:
            error_class = "PROVIDER_REJECTED"
        if result.accepted:
            finished = self._finish(row, state="DELIVERED", provider_reference=result.reference)
            if finished:
                metrics["accepted"] += 1
            return finished
        if not result.retryable:
            finished = self._finish(row, state="FAILED", reason="PROVIDER_PERMANENT",
                                    error_class="PROVIDER_PERMANENT")
            if finished:
                metrics["failed"] += 1
            return finished
        attempts = row["attempts"]
        if attempts >= self.max_attempts:
            finished = self._finish(row, state="FAILED", reason="RETRY_LIMIT", error_class=error_class)
            if finished:
                metrics["failed"] += 1
            return finished
        # Provider calls may consume most of the lease. Schedule from the
        # observed failure/completion time, not the cycle's initial timestamp.
        retry_at = int(self.now()) + self._retry_delay(attempts)
        finished = self._finish(row, state="PENDING", retry_at=retry_at, error_class=error_class)
        if finished:
            metrics["retry_scheduled"] += 1
        return finished

    def _claim(self, now: int, metrics: dict[str, int], *, limit: int | None = None) -> list[dict]:
        metrics.setdefault("failed", 0)
        claim_limit = self.batch_size if limit is None else max(1, min(self.batch_size, int(limit)))
        postgres = getattr(self.db, "dialect", "sqlite") == "postgres"
        self.db.execute("BEGIN" if postgres else "BEGIN IMMEDIATE")
        try:
            # Only committed PENDING rows can be claimed. A PostgreSQL row lock
            # with SKIP LOCKED makes competing workers independent; SQLite's
            # BEGIN IMMEDIATE serializes writers without pretending its lock is PG.
            lock = " FOR UPDATE SKIP LOCKED" if postgres else ""
            exhausted = self.db.execute(
                """UPDATE durable_notification_outbox
                   SET state='FAILED',terminal_reason='RETRY_LIMIT',lease_token=NULL,lease_until=NULL
                   WHERE state='PENDING' AND attempts>=? AND lease_until IS NOT NULL AND lease_until<=?""",
                (self.max_attempts, now),
            )
            exhausted_count = max(0, getattr(exhausted, "rowcount", 0))
            metrics["failed"] += exhausted_count
            metrics["expired_leases"] += exhausted_count
            if exhausted_count:
                self.db.execute(
                    """UPDATE notification_jobs SET state='FAILED',
                           attempts=(SELECT o.attempts FROM durable_notification_outbox o JOIN alerts a
                             ON a.home_id=o.home_id AND a.stable_key=o.effect_key
                             WHERE o.home_id=notification_jobs.home_id AND o.recipient_id=notification_jobs.recipient_id
                               AND o.stage=notification_jobs.stage AND a.alert_id=notification_jobs.alert_id
                               AND o.state='FAILED' AND o.terminal_reason='RETRY_LIMIT' LIMIT 1),
                           last_attempt_at=(SELECT o.last_attempt_at FROM durable_notification_outbox o JOIN alerts a
                             ON a.home_id=o.home_id AND a.stable_key=o.effect_key
                             WHERE o.home_id=notification_jobs.home_id AND o.recipient_id=notification_jobs.recipient_id
                               AND o.stage=notification_jobs.stage AND a.alert_id=notification_jobs.alert_id
                               AND o.state='FAILED' AND o.terminal_reason='RETRY_LIMIT' LIMIT 1)
                       WHERE state='CREATED' AND EXISTS (SELECT 1 FROM durable_notification_outbox o JOIN alerts a
                         ON a.home_id=o.home_id AND a.stable_key=o.effect_key
                         WHERE o.home_id=notification_jobs.home_id AND o.recipient_id=notification_jobs.recipient_id
                           AND o.stage=notification_jobs.stage AND a.alert_id=notification_jobs.alert_id
                           AND o.state='FAILED' AND o.terminal_reason='RETRY_LIMIT')"""
                )
            candidates = self.db.execute(
                """SELECT outbox_id,lease_until FROM durable_notification_outbox
                   WHERE state='PENDING' AND due_at<=? AND (lease_until IS NULL OR lease_until<=?)
                     AND attempts<? ORDER BY due_at,outbox_id LIMIT ?""" + lock,
                (now, now, self.max_attempts, claim_limit),
            ).fetchall()
            rows = []
            for candidate in candidates:
                old_until = candidate[1]
                if old_until is not None and old_until <= now:
                    metrics["expired_leases"] += 1
                token = uuid.uuid4().hex
                cur = self.db.execute(
                    """UPDATE durable_notification_outbox
                       SET lease_token=?,lease_generation=lease_generation+1,lease_until=?,
                           attempts=attempts+1,last_attempt_at=?,last_error_class=NULL,
                           stage=COALESCE(stage,
                             (SELECT nj.stage FROM notification_jobs nj JOIN alerts a ON a.alert_id=nj.alert_id
                              WHERE a.home_id=durable_notification_outbox.home_id
                                AND a.stable_key=durable_notification_outbox.effect_key
                                AND nj.home_id=durable_notification_outbox.home_id
                                AND nj.recipient_id=durable_notification_outbox.recipient_id LIMIT 1),
                             (SELECT CASE hc.role WHEN 'PRIMARY' THEN 1 WHEN 'BACKUP' THEN 2 ELSE NULL END
                              FROM household_caregivers hc WHERE hc.home_id=durable_notification_outbox.home_id
                                AND hc.caregiver_id=durable_notification_outbox.recipient_id))
                       WHERE outbox_id=? AND state='PENDING'
                         AND (lease_until IS NULL OR lease_until<=?)""",
                    (token, now + self.lease_seconds, now, candidate[0], now),
                )
                if getattr(cur, "rowcount", 1) != 1:
                    continue
                row = self.db.execute(
                """SELECT o.outbox_id,o.home_id,o.event_id,o.effect_key,o.recipient_id,o.payload_json,
                              o.stage,o.attempts,o.lease_token,o.lease_generation,
                              e.event_type,e.is_test,a.alert_id,a.state AS alert_state,
                              h.consent_state, hc.role, hc.active,
                              np.preferences_json
                       FROM durable_notification_outbox o
                       JOIN events e ON e.event_id=o.event_id AND e.home_id=o.home_id
                       JOIN households h ON h.home_id=o.home_id
                       LEFT JOIN alerts a ON a.home_id=o.home_id AND a.stable_key=o.effect_key
                       LEFT JOIN household_caregivers hc ON hc.home_id=o.home_id AND hc.caregiver_id=o.recipient_id
                       LEFT JOIN notification_preferences np ON np.home_id=o.home_id
                       WHERE o.outbox_id=?""", (candidate[0],)
                ).fetchone()
                if row is None:
                    cur = self.db.execute(
                        """UPDATE durable_notification_outbox SET state='FAILED',terminal_reason='CORRUPT_OUTBOX',
                           lease_token=NULL,lease_until=NULL WHERE outbox_id=? AND lease_token=?""",
                        (candidate[0], token),
                    )
                    metrics["failed"] += max(0, getattr(cur, "rowcount", 0))
                    self._mark_related_job_failed(candidate[0])
                    continue
                item = dict(row) if hasattr(row, "keys") else dict(zip(
                    ("outbox_id","home_id","event_id","effect_key","recipient_id","payload_json","stage",
                     "attempts","lease_token","lease_generation","event_type","is_test",
                     "alert_id","alert_state","consent_state","role","active","preferences_json"), row))
                try:
                    payload = json.loads(item["payload_json"])
                    if not isinstance(payload, dict) or payload.get("kind") != item["event_type"]:
                        raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    cur = self.db.execute(
                        """UPDATE durable_notification_outbox SET state='FAILED',terminal_reason='CORRUPT_OUTBOX',
                           lease_token=NULL,lease_until=NULL WHERE outbox_id=? AND lease_token=?""",
                        (candidate[0], token),
                    )
                    metrics["failed"] += max(0, getattr(cur, "rowcount", 0))
                    self._mark_related_job_failed(candidate[0])
                    continue
                item["event_type"] = item["event_type"]
                rows.append(item)
            self.db.commit()
            return rows
        except BaseException:
            self.db.rollback()
            raise

    def _authorized(self, row: dict) -> bool:
        # Re-read live authorization after claim and directly before provider I/O.
        live = self.db.execute(
            """SELECT o.effect_key,e.is_test,a.alert_id,a.state AS alert_state,h.consent_state,
                      hc.role,hc.active,np.preferences_json
               FROM durable_notification_outbox o
               JOIN events e ON e.event_id=o.event_id AND e.home_id=o.home_id
               JOIN households h ON h.home_id=o.home_id
               LEFT JOIN alerts a ON a.home_id=o.home_id AND a.stable_key=o.effect_key
               LEFT JOIN household_caregivers hc ON hc.home_id=o.home_id AND hc.caregiver_id=o.recipient_id
               LEFT JOIN notification_preferences np ON np.home_id=o.home_id
               WHERE o.outbox_id=? AND o.lease_token=? AND o.lease_generation=?
                 AND o.state='PENDING' AND o.lease_until>?""",
            (row["outbox_id"], row["lease_token"], row["lease_generation"], int(self.now())),
        ).fetchone()
        if live is None:
            return False
        if hasattr(live, "keys"):
            for name in live.keys():
                row[name] = live[name]
        else:
            for name, value in zip(("effect_key","is_test","alert_id","alert_state","consent_state","role","active","preferences_json"), live):
                row[name] = value
        if row["is_test"] or row["consent_state"] != "ACTIVE" or row["active"] != 1:
            return False
        if row["stage"] is None:
            row["stage"] = 1 if row["role"] == "PRIMARY" else 2 if row["role"] == "BACKUP" else None
        if row["stage"] == 1 and row["role"] != "PRIMARY":
            return False
        if row["stage"] == 2 and row["role"] != "BACKUP":
            return False
        if row["stage"] not in (1, 2):
            return False
        if row["alert_id"] is not None and row["alert_state"] not in ("OPEN", "CLAIMED"):
            return False
        if row["alert_id"] is None and not str(row["effect_key"]).startswith("door-quiet:"):
            return False
        try:
            preferences = json.loads(row["preferences_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return isinstance(preferences, dict) and preferences.get("safety_alerts") is True

    def _mark_related_job_failed(self, outbox_id: str) -> None:
        identity = self.db.execute(
            "SELECT home_id,recipient_id,stage,effect_key FROM durable_notification_outbox WHERE outbox_id=?",
            (outbox_id,),
        ).fetchone()
        if identity is None:
            return
        home_id, recipient_id, stage, effect_key = identity
        self.db.execute(
            """UPDATE notification_jobs SET state='FAILED',
                   attempts=(SELECT attempts FROM durable_notification_outbox WHERE outbox_id=?),
                   last_attempt_at=(SELECT last_attempt_at FROM durable_notification_outbox WHERE outbox_id=?)
               WHERE home_id=? AND recipient_id=? AND stage=? AND state='CREATED'
                 AND alert_id=(SELECT alert_id FROM alerts WHERE home_id=? AND stable_key=?)""",
            (outbox_id, outbox_id, home_id, recipient_id, stage, home_id, effect_key),
        )

    def _finish(self, row: dict, *, state: str, provider_reference=None,
                retry_at=None, reason=None, error_class=None) -> bool:
        return self._finish_raw(row["outbox_id"], row["lease_token"], state,
                                reason, error_class, provider_reference,
                                retry_at, row["lease_generation"])

    def _finish_raw(self, outbox_id, token, state, reason, error_class,
                    provider_reference=None, retry_at=None, generation=None) -> bool:
        accepted_at = int(self.now()) if state == "DELIVERED" else None
        postgres = getattr(self.db, "dialect", "sqlite") == "postgres"
        self.db.execute("BEGIN" if postgres else "BEGIN IMMEDIATE")
        try:
            identity = self.db.execute(
                """SELECT home_id,recipient_id,stage,effect_key FROM durable_notification_outbox
                   WHERE outbox_id=? AND lease_token=? AND state='PENDING'""", (outbox_id, token)
            ).fetchone()
            if identity is None:
                self.db.rollback()
                return False
            home_id, recipient_id, stage, effect_key = identity
            sql = """UPDATE durable_notification_outbox
                     SET state=?,due_at=COALESCE(?,due_at),provider_reference=COALESCE(?,provider_reference),
                         provider_accepted_at=COALESCE(?,provider_accepted_at),
                         terminal_reason=?,last_error_class=?,lease_token=NULL,lease_until=NULL
                     WHERE outbox_id=? AND state='PENDING' AND lease_token=? AND lease_until>?"""
            params = [state, retry_at, provider_reference, accepted_at, reason, error_class,
                      outbox_id, token, int(self.now())]
            if generation is not None:
                sql += " AND lease_generation=?"
                params.append(generation)
            cur = self.db.execute(sql, tuple(params))
            if getattr(cur, "rowcount", 0) != 1:
                self.db.rollback()
                return False
            incident_state = None
            if state == "DELIVERED":
                incident_state = "PROVIDER_ACCEPTED"
            elif state == "FAILED" and reason not in {"AUTHORIZATION_DENIED", "INCIDENT_NOT_ACTIVE"}:
                incident_state = "FAILED"
            elif state == "FAILED" and reason in {"AUTHORIZATION_DENIED", "INCIDENT_NOT_ACTIVE"}:
                incident_state = "CANCELLED"
            # Keep the existing durable notification_jobs model in step with
            # provider outcomes. A human acknowledgement state is never
            # overwritten by late provider completion.
            self.db.execute(
                """UPDATE notification_jobs SET state=COALESCE(?,state),
                       attempts=(SELECT attempts FROM durable_notification_outbox WHERE outbox_id=?),
                       last_attempt_at=(SELECT last_attempt_at FROM durable_notification_outbox WHERE outbox_id=?),
                       provider_reference=COALESCE(?,provider_reference)
                   WHERE home_id=? AND recipient_id=? AND stage=? AND state='CREATED'
                     AND alert_id=(SELECT alert_id FROM alerts WHERE home_id=? AND stable_key=?)""",
                (incident_state, outbox_id, outbox_id, provider_reference,
                 home_id, recipient_id, stage, home_id, effect_key),
            )
            self.db.commit()
            return True
        except BaseException:
            self.db.rollback()
            raise

    def _retry_delay(self, attempts: int) -> int:
        raw = min(self.max_retry_seconds, self.base_retry_seconds * (2 ** max(0, attempts - 1)))
        sample = min(1.0, max(0.0, float(self.random_value())))
        factor = 1 - self.jitter_fraction + 2 * self.jitter_fraction * sample
        return max(1, min(self.max_retry_seconds, round(raw * factor)))

    def metrics_snapshot(self) -> dict[str, int]:
        """Return aggregate operational counts without exposing identities."""
        now = int(self.now())
        row = self.db.execute(
            """SELECT
                 SUM(CASE WHEN state='PENDING' AND attempts=0 THEN 1 ELSE 0 END),
                 SUM(CASE WHEN state='PENDING' AND attempts>0 THEN 1 ELSE 0 END),
                 SUM(CASE WHEN state='PENDING' AND lease_until IS NOT NULL AND lease_until<=? THEN 1 ELSE 0 END),
                 SUM(CASE WHEN state='DELIVERED' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN state='FAILED' THEN 1 ELSE 0 END)
               FROM durable_notification_outbox""", (now,),
        ).fetchone()
        values = tuple(int(value or 0) for value in row)
        return dict(zip(("pending", "retry", "expired_lease", "provider_accepted", "failed"), values))


class NotificationWorkerProcess:
    """Small bounded polling loop suitable for a separately managed worker process."""

    def __init__(self, worker: NotificationWorker, *, poll_seconds: float = 2.0,
                 stop_event=None):
        if not 0.25 <= poll_seconds <= 60:
            raise ValueError("invalid_worker_poll_bounds")
        self.worker = worker
        self.poll_seconds = poll_seconds
        self.stop_event = stop_event or threading.Event()

    def run(self, max_cycles: int | None = None) -> None:
        cycles = 0
        if not self.worker.ready():
            raise RuntimeError("notification_worker_not_ready")
        while not self.stop_event.is_set() and (max_cycles is None or cycles < max_cycles):
            try:
                self.worker.run_once()
            except RuntimeError as error:
                if str(error) == "notification_worker_not_ready":
                    raise
                LOG.error("notification_worker_cycle_failed")
            except Exception:
                LOG.error("notification_worker_cycle_failed")
            cycles += 1
            if self.stop_event.wait(self.poll_seconds):
                break
        # No unbounded in-memory work exists. Returning finishes the current
        # batch; any unprocessed rows remain durable for the next process.


def run_notification_worker(db, provider: NotificationProvider, *, stop_event=None,
                            poll_seconds: float = 2.0) -> None:
    """Deployment composition entry point; caller must inject approved DB/provider."""
    NotificationWorkerProcess(
        NotificationWorker(db, provider), poll_seconds=poll_seconds, stop_event=stop_event,
    ).run()


def main() -> int:
    """Standalone process entry point; remains disabled without explicit activation."""
    if os.environ.get("GS_NOTIFICATION_WORKER_ENABLED") != "1":
        print("notification worker disabled", file=sys.stderr)
        return 78
    dsn = os.environ.get("DATABASE_URL")
    factory_path = os.environ.get("GS_NOTIFICATION_PROVIDER_FACTORY", "")
    if not dsn or ":" not in factory_path:
        print("notification worker configuration incomplete", file=sys.stderr)
        return 78
    module_name, attribute = factory_path.split(":", 1)
    if (not module_name or not attribute or
            any(not part.isidentifier() for part in module_name.split(".")) or
            not attribute.isidentifier()):
        print("notification worker provider configuration invalid", file=sys.stderr)
        return 78
    db = None
    try:
        from .postgres_database import connect_postgres, initialize_postgres
        db = connect_postgres(dsn)
        initialize_postgres(db)
        provider = getattr(importlib.import_module(module_name), attribute)()
        worker = NotificationWorker(db, provider)
        stop_event = threading.Event()
        signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_event.set())
        signal.signal(signal.SIGINT, lambda _signum, _frame: stop_event.set())
        NotificationWorkerProcess(worker, stop_event=stop_event).run()
        return 0
    except Exception:
        LOG.error("notification worker startup or cycle failed")
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":  # pragma: no cover - exercised by deployment smoke test
    raise SystemExit(main())
