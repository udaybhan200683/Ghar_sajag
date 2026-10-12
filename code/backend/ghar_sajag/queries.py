# Ghar Sajag traceability edition 2.0 | source release 1.5.1
# @module B07 Read models/API
# @requirements F05, F06, F07, F09, F11, F12, F14, E04

from __future__ import annotations

from .logging_config import traced
from collections import Counter
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .identity import IdentityService
from .model import IncidentState, CloudEvent
from .store import InMemoryStore


_ACTIVITY_KINDS = {"MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED"}
_MEANINGFUL_KINDS = _ACTIVITY_KINDS | {"CALL_FAMILY", "MISSING_MORNING_ACTIVITY", "DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY",
    "MORNING_ROUTINE_COMPLETED", "UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY", "POST_DOOR_INACTIVITY"}
_REPORT_KINDS = _MEANINGFUL_KINDS | {"COVERAGE_CHANGED"}
_CONCERN_KINDS = {
    "CALL_FAMILY", "MISSING_MORNING_ACTIVITY", "DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY",
    "UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY", "POST_DOOR_INACTIVITY",
}
_SAFE_PAYLOAD_KEYS = {
    "quiet_hours", "unexpected", "open_duration_s", "was_left_open", "resolved_left_open",
    "opened_at", "duration_s", "source_event_id", "window_id", "left_open_timeout_s", "reason",
}


class QueryService:
    def __init__(self, store: InMemoryStore, identity: IdentityService, hub_lease_seconds: int = 190) -> None:
        self.store = store
        self.identity = identity
        self.hub_lease_seconds = hub_lease_seconds

    def _event_view(self, item) -> dict[str, Any]:
        payload = {k: v for k, v in item.payload.items() if k in _SAFE_PAYLOAD_KEYS}
        if item.kind in {"MISSING_MORNING_ACTIVITY", "DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY",
                          "UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY", "POST_DOOR_INACTIVITY"}:
            tone = "danger"
        elif item.kind == "DOOR_OPEN" and payload.get("unexpected"):
            tone = "danger"
        elif item.kind == "COVERAGE_CHANGED" and payload.get("reason") == "coverage_lost":
            tone = "danger"
        elif item.kind in {"OK_PRESSED", "DOOR_CLOSED", "MORNING_ROUTINE_COMPLETED"} or (item.kind == "COVERAGE_CHANGED" and payload.get("reason") == "coverage_restored"):
            tone = "positive"
        elif item.kind in {"MOTION", "DOOR_OPEN"}:
            tone = "positive"
        elif item.kind == "CALL_FAMILY":
            tone = "warning"
        else:
            tone = "neutral"
        return {
            "event_id": item.event_id,
            "kind": item.kind,
            "location": item.location,
            "occurred_at": item.occurred_at,
            "received_at": item.server_received_at,
            "uncertainty_s": item.uncertainty_s,
            "delayed": item.server_received_at - item.occurred_at > 60,
            "tone": tone,
            "details": payload,
        }

    def _events(self, home_id: str, *, kinds=None, start=None, end=None,
                include_test=True, newest_first=False, limit=None, payload_reasons=None) -> list[CloudEvent]:
        durable_query = getattr(self.store.events, "home_events", None)
        if durable_query is not None:
            return durable_query(
                home_id, kinds=kinds, start=start, end=end, include_test=include_test,
                newest_first=newest_first, limit=limit, payload_reasons=payload_reasons,
            )
        events = [
            event for (candidate, _), event in self.store.events.items()
            if candidate == home_id
            and (include_test or not event.is_test)
            and (start is None or event.occurred_at >= start)
            and (end is None or event.occurred_at < end)
            and (not kinds or event.kind in kinds)
            and (not payload_reasons or event.payload.get("reason") in payload_reasons)
        ]
        events.sort(key=lambda item: (item.occurred_at, item.event_id), reverse=newest_first)
        return events if limit is None else events[:max(0, int(limit))]

    @traced("B07")
    def snapshot(
        self,
        home_id: str,
        actor_id: str,
        at: int,
        *,
        include_active_incident_ids: bool = True,
    ) -> dict[str, Any]:
        self.identity.require(home_id, actor_id, "read", at)
        home = self.store.homes[home_id]
        if hasattr(self.store.events, "latest_home_received"):
            last_hub_event = self.store.events.latest_home_received(home_id, "HUB_HEARTBEAT")
        else:
            hub_beats = self._events(home_id, kinds={"HUB_HEARTBEAT"})
            last_hub_event = max(hub_beats, key=lambda item: item.server_received_at, default=None)
        last_hub = last_hub_event.server_received_at if last_hub_event else None
        hub_reachable = last_hub is not None and at - last_hub <= self.hub_lease_seconds
        active_incident_ids = (
            [
                item.incident_id for item in self.store.incidents.values()
                if item.home_id == home_id and item.state != IncidentState.RESOLVED
            ]
            if include_active_incident_ids else []
        )
        activity = self._events(home_id, kinds=_ACTIVITY_KINDS, newest_first=True, limit=1)
        latest_activity = activity[0] if activity else None
        meaningful = self._events(home_id, kinds=_MEANINGFUL_KINDS, newest_first=True, limit=6)
        coverage = self._events(
            home_id, kinds={"COVERAGE_CHANGED"}, payload_reasons={"coverage_lost", "coverage_restored"},
            newest_first=True, limit=6,
        )
        recent_events = sorted(meaningful + coverage, key=lambda item: (item.occurred_at, item.event_id), reverse=True)[:6]
        recent = [self._event_view(item) for item in recent_events]

        door_events = self._events(home_id, kinds={"DOOR_OPEN", "DOOR_CLOSED"}, newest_first=True, limit=1)
        latest_door = door_events[0] if door_events else None
        door_status = None
        if latest_door is not None:
            details = self._event_view(latest_door)["details"]
            door_status = {
                "state": "OPEN" if latest_door.kind == "DOOR_OPEN" else "CLOSED",
                "since": latest_door.occurred_at,
                "location": latest_door.location,
                "unexpected": bool(details.get("unexpected", False)),
                "open_duration_s": details.get("open_duration_s"),
                "left_open": latest_door.kind == "DOOR_OPEN" and at - latest_door.occurred_at >= int(details.get("left_open_timeout_s", 300)),
            }

        return {
            "home_id": home_id,
            "mode": home.mode.value,
            "home_version": home.version,
            "hub_reachable": hub_reachable,
            "last_hub_at": last_hub,
            "latest_activity": None if latest_activity is None else self._event_view(latest_activity),
            "recent_events": recent,
            "door_status": door_status,
            "active_incidents": active_incident_ids,
            "event_counts": (self.store.events.home_event_counts(home_id)
                             if hasattr(self.store.events, "home_event_counts")
                             else dict(Counter(item.kind for item in self._events(home_id)))),
            "fetched_at": at,
        }

    @traced("B07")
    def timeline(self, home_id: str, actor_id: str, at: int, limit: int = 100) -> list[dict[str, Any]]:
        self.identity.require(home_id, actor_id, "read", at)
        events = self._events(home_id, include_test=False, newest_first=True, limit=limit)
        return [self._event_view(item) for item in events]

    @traced("B07")
    def report(self, home_id: str, actor_id: str, at: int, period: str) -> dict[str, Any]:
        self.identity.require(home_id, actor_id, "read", at)
        period = period.upper()
        if period not in {"TODAY", "WEEK", "MONTH"}:
            raise ValueError("invalid_report_period")
        home = self.store.homes[home_id]
        tz = ZoneInfo(home.timezone)
        start, end = self._report_window(at, period, tz)
        buckets = self._report_buckets(start, end, period, tz)
        bucket_map = {item["key"]: item for item in buckets}
        summary = Counter()
        location_counts: Counter[str] = Counter()
        room_first_order: dict[str, tuple[int, str]] = {}
        durable_reports = getattr(self.store.events, "report_event_groups", None)
        if durable_reports is not None:
            bucket_ranges = [(item["start_at"], item["end_at"]) for item in buckets]
            total = 0
            for group in durable_reports(home_id, kinds=_REPORT_KINDS, buckets=bucket_ranges):
                count = int(group["event_count"])
                total += count
                event = CloudEvent(
                    home_id, "", group["event_type"], "", 0, 0, 0,
                    payload={
                        "reason": group["payload_reason"],
                        "unexpected": group["payload_unexpected"],
                    },
                )
                self._count_report_event(event, summary, amount=count, include_motion_night=False)
                self._count_report_event(
                    event, buckets[int(group["bucket_index"])],
                    amount=count, include_motion_night=False,
                )
            for occurred_at, count in self.store.events.report_motion_times(home_id, start, end):
                if not self._is_night_timestamp(home_id, occurred_at):
                    continue
                summary["night_activity"] += count
                key = self._bucket_key(occurred_at, period, tz)
                if key in bucket_map:
                    bucket_map[key]["night_activity"] += count
            for group in self.store.events.report_room_groups(home_id, start, end):
                location = self._label_location(group["location"])
                location_counts[location] += int(group["event_count"])
                first_order = (int(group["first_occurred_at"]), group["first_event_id"])
                room_first_order[location] = min(room_first_order.get(location, first_order), first_order)
            highlight_events = self.store.events.report_highlights(
                home_id, kinds=_REPORT_KINDS, start=start, end=end, limit=6,
            )
        else:
            all_events = self._events(
                home_id, kinds=_REPORT_KINDS, start=start, end=end, include_test=False,
            )
            all_events = [item for item in all_events if self._is_reportable_event(item)]
            for event in all_events:
                self._count_report_event(event, summary)
                if event.location and event.kind in {"MOTION", "DOOR_OPEN", "DOOR_CLOSED"}:
                    location = self._label_location(event.location)
                    location_counts[location] += 1
                    room_first_order.setdefault(location, (event.occurred_at, event.event_id))
                key = self._bucket_key(event.occurred_at, period, tz)
                if key in bucket_map:
                    self._count_report_event(event, bucket_map[key])
            total = len(all_events)
            highlight_events = sorted(
                all_events, key=lambda event: (event.occurred_at, event.event_id), reverse=True
            )[:6]

        incidents = [
            item for item in self.store.incidents.values()
            if item.home_id == home_id and start <= item.created_at < end
        ]
        open_concerns = sum(1 for item in incidents if item.state is not IncidentState.RESOLVED)
        resolved_concerns = sum(1 for item in incidents if item.state is IncidentState.RESOLVED)
        summary_view = {
            "event_count": total,
            "activity_events": int(summary["activity_events"]),
            "check_ins": int(summary["check_ins"]),
            "morning_completed": int(summary["morning_completed"]),
            "morning_concerns": int(summary["morning_concerns"]),
            "door_openings": int(summary["door_openings"]),
            "night_activity": int(summary["night_activity"]),
            "care_concerns": int(summary["care_concerns"]),
            "call_family": int(summary["call_family"]),
            "coverage_lost": int(summary["coverage_lost"]),
            "coverage_restored": int(summary["coverage_restored"]),
            "open_concerns": open_concerns,
            "resolved_concerns": resolved_concerns,
        }
        return {
            "schema_version": 1,
            "home_id": home_id,
            "period": period,
            "label": {"TODAY": "Today", "WEEK": "This Week", "MONTH": "This Month"}[period],
            "timezone": home.timezone,
            "window": {
                "start_at": start,
                "end_at": end,
                "start_local": datetime.fromtimestamp(start, tz).date().isoformat(),
                "end_local": (datetime.fromtimestamp(end, tz) - timedelta(seconds=1)).date().isoformat(),
                "boundary": "start_inclusive_end_exclusive",
            },
            "status": "NO_DATA" if total == 0 else "DATA",
            "partial_data": total > 0 and min(summary_view["check_ins"], summary_view["morning_completed"], summary_view["door_openings"], summary_view["night_activity"]) == 0,
            "summary": summary_view,
            "trend": [{k: item[k] for k in ("key", "label", "start_at", "end_at", "activity_events", "check_ins", "morning_completed", "care_concerns", "door_openings", "night_activity")} for item in buckets],
            "room_activity": [
                {"location": location, "count": count}
                for location, count in sorted(
                    location_counts.items(),
                    key=lambda item: (-item[1], room_first_order[item[0]]),
                )[:5]
            ],
            "highlights": [self._report_highlight(item, tz) for item in highlight_events],
            "insights": self._report_insights(period, summary_view, buckets, total),
            "fetched_at": at,
        }

    def _report_window(self, at: int, period: str, tz: ZoneInfo) -> tuple[int, int]:
        local_now = datetime.fromtimestamp(at, tz)
        today = local_now.date()
        if period == "TODAY":
            start_local = datetime(today.year, today.month, today.day, tzinfo=tz)
            end_local = start_local + timedelta(days=1)
        elif period == "WEEK":
            start_day = today - timedelta(days=6)
            start_local = datetime(start_day.year, start_day.month, start_day.day, tzinfo=tz)
            end_local = datetime(today.year, today.month, today.day, tzinfo=tz) + timedelta(days=1)
        else:
            start_local = datetime(today.year, today.month, 1, tzinfo=tz)
            next_month = datetime(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1, tzinfo=tz)
            end_local = next_month
        return int(start_local.timestamp()), int(end_local.timestamp())

    def _report_buckets(self, start: int, end: int, period: str, tz: ZoneInfo) -> list[dict[str, Any]]:
        buckets = []
        current = datetime.fromtimestamp(start, tz)
        end_local = datetime.fromtimestamp(end, tz)
        while current < end_local:
            next_day = current + timedelta(days=1)
            buckets.append({
                "key": current.date().isoformat(),
                "label": current.strftime("%d %b") if period == "MONTH" else current.strftime("%a"),
                "start_at": int(current.timestamp()),
                "end_at": int(next_day.timestamp()),
                "activity_events": 0,
                "check_ins": 0,
                "morning_completed": 0,
                "care_concerns": 0,
                "door_openings": 0,
                "night_activity": 0,
            })
            current = next_day
        return buckets

    def _bucket_key(self, occurred_at: int, period: str, tz: ZoneInfo) -> str:
        del period
        return datetime.fromtimestamp(occurred_at, tz).date().isoformat()

    def _is_reportable_event(self, event: CloudEvent) -> bool:
        if event.kind == "COVERAGE_CHANGED":
            return event.payload.get("reason") in {"coverage_lost", "coverage_restored"}
        return event.kind in _REPORT_KINDS

    def _count_report_event(self, event: CloudEvent, counter: Counter | dict[str, Any],
                            *, amount: int = 1, include_motion_night: bool = True) -> None:
        def add(key: str, amount: int = 1) -> None:
            counter[key] = int(counter.get(key, 0)) + amount

        if event.kind in _ACTIVITY_KINDS:
            add("activity_events", amount)
        if event.kind == "OK_PRESSED":
            add("check_ins", amount)
        elif event.kind == "MORNING_ROUTINE_COMPLETED":
            add("morning_completed", amount)
        elif event.kind == "MISSING_MORNING_ACTIVITY":
            add("morning_concerns", amount)
            add("care_concerns", amount)
        elif event.kind == "DOOR_OPEN":
            add("door_openings", amount)
            if event.payload.get("unexpected"):
                add("care_concerns", amount)
        elif event.kind == "CALL_FAMILY":
            add("call_family", amount)
            add("care_concerns", amount)
        elif event.kind in {"UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY"}:
            add("night_activity", amount)
            add("care_concerns", amount)
        elif event.kind in {"DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY", "POST_DOOR_INACTIVITY"}:
            add("care_concerns", amount)
        elif event.kind == "COVERAGE_CHANGED":
            reason = event.payload.get("reason")
            if reason == "coverage_lost":
                add("coverage_lost", amount)
                add("care_concerns", amount)
            elif reason == "coverage_restored":
                add("coverage_restored", amount)
        if include_motion_night and event.kind == "MOTION" and self._is_night_activity(event):
            add("night_activity", amount)

    def _is_night_activity(self, event: CloudEvent) -> bool:
        return self._is_night_timestamp(event.home_id, event.occurred_at)

    def _is_night_timestamp(self, home_id: str, occurred_at: int) -> bool:
        desired = self.store.configs.get(home_id)
        rules = desired.body.get("activity_rules", {}) if desired else {}
        if rules.get("night_activity_enabled", True) is False:
            return False
        home = self.store.homes[home_id]
        local_event = datetime.fromtimestamp(occurred_at, ZoneInfo(home.timezone))
        minute = local_event.hour * 60 + local_event.minute
        start = int(rules.get("night_start_minute", 22 * 60))
        end = int(rules.get("night_end_minute", 6 * 60))
        if start <= end:
            return start <= minute < end
        return minute >= start or minute < end

    def _report_highlight(self, event: CloudEvent, tz: ZoneInfo) -> dict[str, Any]:
        title, detail, tone = self._report_event_text(event)
        return {
            "at": event.occurred_at,
            "time": datetime.fromtimestamp(event.occurred_at, tz).strftime("%I:%M %p").lstrip("0"),
            "title": title,
            "detail": detail,
            "tone": tone,
        }

    def _report_event_text(self, event: CloudEvent) -> tuple[str, str, str]:
        location = self._label_location(event.location)
        if event.kind == "OK_PRESSED":
            return "I am OK confirmed", "Resident pressed the check-in button.", "positive"
        if event.kind == "CALL_FAMILY":
            return "Call Family requested", "Family assistance was requested.", "warning"
        if event.kind == "MORNING_ROUTINE_COMPLETED":
            return "Morning routine completed", "Expected morning activity was completed.", "positive"
        if event.kind == "MISSING_MORNING_ACTIVITY":
            return "Morning routine concern", "Expected morning activity was not completed.", "danger"
        if event.kind == "DOOR_LEFT_OPEN":
            seconds = int(event.payload.get("open_duration_s") or event.payload.get("duration_s") or 0)
            detail = f"Main door stayed open for {self._duration_label(seconds)}." if seconds else "Main door stayed open longer than configured."
            return "Main door left open", detail, "danger"
        if event.kind == "DOOR_OPEN" and event.payload.get("unexpected"):
            return "Main door opened during quiet hours", "Door activity occurred during a configured quiet period.", "danger"
        if event.kind == "DOOR_OPEN":
            return "Main door opened", "Door activity was recorded.", "positive"
        if event.kind == "DOOR_CLOSED":
            return "Main door closed", "Door closure was recorded.", "positive"
        if event.kind == "DAYTIME_INACTIVITY":
            return "Daytime inactivity concern", "Expected daytime activity was not observed.", "danger"
        if event.kind == "POST_DOOR_INACTIVITY":
            return "No indoor activity after door closed", "Indoor activity did not follow the door event.", "danger"
        if event.kind in {"UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY"}:
            return "Unusual night activity", "Night activity was outside configured household limits.", "danger"
        if event.kind == "COVERAGE_CHANGED":
            if event.payload.get("reason") == "coverage_lost":
                return "Monitoring coverage lost", "A monitoring device was unavailable.", "danger"
            return "Monitoring coverage restored", "Monitoring coverage returned.", "positive"
        if event.kind == "MOTION":
            return f"Activity in {location}" if location else "Activity recorded", "Household motion activity was recorded.", "positive"
        return "Care activity recorded", "Household activity was recorded.", "neutral"

    def _report_insights(self, period: str, summary: dict[str, int], buckets: list[dict[str, Any]], total: int) -> list[dict[str, str]]:
        if total == 0:
            return []
        insights: list[dict[str, str]] = []
        if summary["morning_completed"]:
            insights.append({"title": "Morning routine was recorded", "detail": f"{summary['morning_completed']} completion{'' if summary['morning_completed'] == 1 else 's'} in this period."})
        elif period != "TODAY":
            insights.append({"title": "No morning completions recorded", "detail": "There is not enough recorded morning routine history for this period."})
        if summary["check_ins"]:
            insights.append({"title": "I am OK check-ins recorded", "detail": f"{summary['check_ins']} check-in{'' if summary['check_ins'] == 1 else 's'} from persisted history."})
        if summary["care_concerns"]:
            insights.append({"title": "Care concerns need review", "detail": f"{summary['care_concerns']} concern event{'' if summary['care_concerns'] == 1 else 's'} recorded in this period."})
        else:
            insights.append({"title": "No care concerns recorded", "detail": "Persisted history has no caregiver concern events for this period."})
        active_days = sum(1 for item in buckets if int(item["activity_events"]) > 0)
        if len(buckets) > 1 and active_days:
            insights.append({"title": "Activity appeared on multiple days", "detail": f"Activity was recorded on {active_days} of {len(buckets)} days."})
        return insights[:4]

    @staticmethod
    def _label_location(location: str) -> str:
        labels = {"room1": "Bedroom", "entry": "Main door", "common": "Common room"}
        return labels.get(location, location.replace("_", " ").replace("-", " ").title())

    @staticmethod
    def _duration_label(seconds: int) -> str:
        seconds = max(0, seconds)
        minutes = seconds // 60
        hours = minutes // 60
        if hours and minutes % 60:
            return f"{hours} hr {minutes % 60} min"
        if hours:
            return f"{hours} hr"
        if minutes:
            return f"{minutes} min"
        return f"{seconds} sec"
