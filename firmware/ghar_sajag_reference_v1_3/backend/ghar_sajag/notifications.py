from __future__ import annotations

from .logging_config import traced
import uuid

from .model import AdvisoryNotice, DailySummary, DeliveryState, IncidentState, NotificationJob
from .store import InMemoryStore


class NotificationService:
    def __init__(self, store: InMemoryStore, backup_delay_seconds: int = 300) -> None:
        self.store = store
        self.backup_delay_seconds = backup_delay_seconds

    @traced("B05")

    def schedule_for_incident(self, incident_id: str) -> list[NotificationJob]:
        incident = self.store.incidents[incident_id]
        home = self.store.homes[incident.home_id]
        jobs: list[NotificationJob] = []
        if home.primary_caregiver_id:
            jobs.append(self._ensure(incident_id, home.primary_caregiver_id, 1, incident.created_at))
        if home.backup_caregiver_id:
            jobs.append(self._ensure(incident_id, home.backup_caregiver_id, 2, incident.created_at + self.backup_delay_seconds))
        return jobs

    @traced("B05")

    def due(self, at: int) -> list[NotificationJob]:
        result: list[NotificationJob] = []
        for job in self.store.notification_jobs.values():
            incident = self.store.incidents[job.incident_id]
            if incident.state in {IncidentState.ACKNOWLEDGED, IncidentState.RESOLVED}:
                if job.state == DeliveryState.CREATED:
                    job.state = DeliveryState.CANCELLED
                continue
            if job.state == DeliveryState.CREATED and job.due_at <= at:
                result.append(job)
        return sorted(result, key=lambda item: (item.due_at, item.stage, item.job_id))

    @traced("B05")

    def provider_result(self, job_id: str, accepted: bool, reference: str | None = None) -> NotificationJob:
        job = self.store.notification_jobs[job_id]
        job.attempts += 1
        job.state = DeliveryState.PROVIDER_ACCEPTED if accepted else DeliveryState.FAILED
        job.provider_reference = reference
        return job

    @traced("B05")

    def human_acknowledged(self, incident_id: str) -> None:
        for job in self.store.notification_jobs.values():
            if job.incident_id != incident_id:
                continue
            if job.state == DeliveryState.PROVIDER_ACCEPTED:
                job.state = DeliveryState.HUMAN_ACKED
            elif job.state == DeliveryState.CREATED:
                job.state = DeliveryState.CANCELLED

    @traced("B05")

    def create_door_notice(self, home_id: str, event_id: str, at: int, within_quiet_hours: bool, is_test: bool = False) -> AdvisoryNotice | None:
        """Create a low-priority notice only when the configured quiet policy matches."""
        if not within_quiet_hours or is_test:
            return None
        home = self.store.homes[home_id]
        recipient = home.primary_caregiver_id
        if not recipient:
            return None
        key = (home_id, event_id, "DOOR_QUIET_NOTICE")
        existing_id = self.store.advisory_keys.get(key)
        if existing_id:
            return self.store.advisory_notices[existing_id]
        notice_id = f"notice_{uuid.uuid4().hex[:16]}"
        notice = AdvisoryNotice(notice_id, home_id, event_id, "DOOR_QUIET_NOTICE", at, recipient, is_test)
        self.store.advisory_notices[notice_id] = notice
        self.store.advisory_keys[key] = notice_id
        return notice

    @traced("B05")

    def build_daily_summary(
        self,
        home_id: str,
        local_date: str,
        policy_version: int,
        at: int,
        summaries_enabled: bool,
        window_complete: bool,
        coverage_complete: bool,
    ) -> DailySummary | None:
        if not summaries_enabled:
            return None
        key = (home_id, local_date, policy_version)
        if key in self.store.daily_summaries:
            return self.store.daily_summaries[key]
        events = [event for (candidate, _), event in self.store.events.items() if candidate == home_id and not event.is_test]
        activity = [event for event in events if event.kind in {"MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED"}]
        unresolved = [
            incident.incident_id for incident in self.store.incidents.values()
            if incident.home_id == home_id and incident.state not in {IncidentState.RESOLVED}
        ]
        if not window_complete:
            observation = "window_not_finalized"
        elif not coverage_complete:
            observation = "observation_incomplete"
        elif activity:
            observation = "activity_observed"
        else:
            observation = "no_activity_evidence"
        summary = DailySummary(home_id, local_date, policy_version, at, {
            "observation": observation,
            "activity_event_count": len(activity),
            "unresolved_incident_ids": unresolved,
            "coverage_complete": coverage_complete,
        })
        self.store.daily_summaries[key] = summary
        return summary

    @traced("B05")

    def _ensure(self, incident_id: str, recipient_id: str, stage: int, due_at: int) -> NotificationJob:
        key = (incident_id, recipient_id, stage)
        existing_id = self.store.notification_keys.get(key)
        if existing_id:
            return self.store.notification_jobs[existing_id]
        incident = self.store.incidents[incident_id]
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        job = NotificationJob(job_id, incident_id, incident.home_id, recipient_id, stage, due_at)
        self.store.notification_jobs[job_id] = job
        self.store.notification_keys[key] = job_id
        return job
