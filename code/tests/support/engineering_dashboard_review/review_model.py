"""Inactive GS-120 design exercise. NOT a production diagnostics implementation.

No HTTP routes, production callers, firmware observers or device operations.
Policies supplied explicitly by isolated tests are not approved product contracts.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import json

from ghar_sajag.durable_commit import DurableEventCommit
from ghar_sajag.node_health_policy import NodeHealthPolicy

STAGES = (
    "sensor", "node_created", "radio_tx", "hub_rx", "hub_validated",
    "hub_persisted", "rules_processed", "backend_queued",
    "backend_committed", "dashboard_received",
)
RESULTS = {"PASS", "WARNING", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}
ENVIRONMENTS = {"HOST_SIMULATION", "BACKEND_FIXTURE", "BROWSER_FIXTURE"}


def canonical_key(key: dict) -> str:
    # Exercise the actual existing backend identity contract; never replicate it.
    return DurableEventCommit._identity({"event_key": key})[1]


def diagnostic_key(key: dict) -> dict:
    canonical_key(key)
    return {name: str(value) if type(value) is int else value
            for name, value in key.items()}


@dataclass(frozen=True)
class FixtureGrant:
    """Only an isolated policy input. This class does NOT verify credentials."""
    actor: str
    home: str
    expires_at: int
    permissions: frozenset[str]
    active: bool = True

    def require(self, home: str, permission: str, now: int) -> None:
        if (not self.actor or not self.active or self.home != home or
                now >= self.expires_at or permission not in self.permissions):
            raise PermissionError("fixture_diagnostic_denied")


@dataclass(frozen=True)
class Observation:
    schema_version: int
    home: str
    key: str
    stage: str
    result: str
    producer: str
    evidence: str
    environment: str
    cursor: int
    clock_domain: str
    observed_ms: int
    reason_code: str

    def __post_init__(self):
        if (type(self.schema_version) is not int or self.schema_version != 1 or
                self.stage not in STAGES or self.result not in RESULTS or
                self.environment not in ENVIRONMENTS or
                type(self.cursor) is not int or self.cursor <= 0 or
                type(self.observed_ms) is not int or self.observed_ms < 0):
            raise ValueError("invalid_review_observation")
        for value in (self.home, self.key, self.producer, self.evidence,
                      self.clock_domain, self.reason_code):
            if not isinstance(value, str) or len(value.encode()) > 256:
                raise ValueError("unbounded_review_field")
        if not self.home or not self.key or not self.producer or not self.clock_domain:
            raise ValueError("missing_review_provenance")
        if self.result in {"PASS", "FAIL", "WARNING"} and not self.evidence:
            raise ValueError("missing_review_evidence")
        # Reasons are codes, never arbitrary exception/raw packet strings.
        if not self.reason_code or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in self.reason_code):
            raise ValueError("invalid_review_reason_code")


def trace(home: str, key: dict, observations, grant: FixtureGrant, now: int) -> dict:
    grant.require(home, "READ_DIAGNOSTICS", now)
    canonical = canonical_key(key)
    selected = [o for o in observations if o.home == home and o.key == canonical]
    stages = []
    for name in STAGES:
        rows = [o for o in selected if o.stage == name]
        outcomes = {o.result for o in rows}
        conflict = len(outcomes) > 1
        stages.append({
            "stage": name,
            "result": "WARNING" if conflict else next(iter(outcomes), "UNKNOWN"),
            "reason_code": "CONFLICTING_OBSERVATIONS" if conflict else
                (rows[0].reason_code if rows else "EVIDENCE_UNAVAILABLE"),
            "observations": [asdict(o) for o in sorted(rows, key=lambda o: (o.producer, o.cursor))],
        })
    return {"schema_version": 1, "home_id": home,
            "event_key": diagnostic_key(key), "canonical_event_id": canonical,
            "scope": "INACTIVE_REVIEW_PROTOTYPE", "stages": stages}


def contact_health(last_ms, now_ms, policy: NodeHealthPolicy | None,
                   same_clock=True, authenticated=True):
    if (policy is None or type(last_ms) is not int or type(now_ms) is not int or
            last_ms <= 0 or now_ms < last_ms or not same_clock or not authenticated):
        return "UNKNOWN"
    return "HEALTHY" if now_ms - last_ms <= policy.offline_seconds * 1000 else "OFFLINE"


def ack_meaning(value):
    # Descriptions only. No pending state, ACK transport or retirement mutation.
    return {
        "MAC_SUCCESS": "RADIO_RESULT_ONLY",
        "HUB_ACK_SENT": "NODE_RECEIPT_UNKNOWN",
        "DURABLE": "DURABLE_CLASS_REPORTED",
        "RECEIVED_VOLATILE": "RETAINED_PENDING",
        "DISCARDED_POLICY": "POLICY_DISCARD_REPORTED",
        "REJECTED": "REJECTED_REPORTED",
    }.get(value, "UNKNOWN")


class ReviewWindow:
    """Explicit fixture count AND encoded-byte limits; gap is never silent."""
    def __init__(self, max_count, max_bytes):
        if type(max_count) is not int or type(max_bytes) is not int or min(max_count, max_bytes) <= 0:
            raise ValueError("invalid_review_window")
        self.max_count, self.max_bytes = max_count, max_bytes
        self.rows = deque()
        self.bytes = 0
        self.dropped = 0

    def append(self, row: Observation):
        encoded = json.dumps(asdict(row), ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > self.max_bytes:
            self.dropped += 1
            return False
        while self.rows and (len(self.rows) >= self.max_count or self.bytes + len(encoded) > self.max_bytes):
            _, size = self.rows.popleft()
            self.bytes -= size
            self.dropped += 1
        self.rows.append((row, len(encoded)))
        self.bytes += len(encoded)
        return True

    def observations(self):
        return [row for row, _ in self.rows]


@dataclass(frozen=True)
class ExpectedDevice:
    physical: str
    logical: str
    generation: int
    room: str
    kind: str
    required_stages: frozenset[str]
    supported: bool = True


class InstallationReview:
    """Ephemeral fixture-only state exercise, NOT a physical install certificate."""
    def __init__(self, home: str, devices: tuple[ExpectedDevice, ...], timeout_ms: int):
        if (not home or not devices or type(timeout_ms) is not int or timeout_ms <= 0 or
                len({(d.physical, d.logical, d.generation) for d in devices}) != len(devices)):
            raise ValueError("invalid_review_manifest")
        for d in devices:
            if (type(d.generation) is not int or d.generation <= 0 or
                    not d.required_stages or not d.required_stages <= set(STAGES)):
                raise ValueError("invalid_review_stage_policy")
        self.home, self.devices, self.timeout_ms = home, devices, timeout_ms
        self.states = ["NOT_TESTED"] * len(devices)
        self.evidence = [set() for _ in devices]
        self.candidates = [None for _ in devices]
        self.attempts = [[] for _ in devices]
        self.active = None
        self.arm_ms = self.deadline = self.cursor = 0
        self.domain = ""

    def arm(self, index, now_ms, cursor, domain):
        if (type(index) is not int or not 0 <= index < len(self.devices) or
                type(now_ms) is not int or now_ms < 0 or type(cursor) is not int or cursor < 0 or
                not domain or self.active is not None or self.states[index] == "PASS"):
            raise ValueError("invalid_review_arm")
        d = self.devices[index]
        if not d.supported:
            self.states[index] = "UNSUPPORTED"
            return
        self.active = index
        self.states[index] = "ARMED"
        self.arm_ms, self.deadline, self.cursor, self.domain = now_ms, now_ms + self.timeout_ms, cursor, domain
        self.evidence[index] = set()
        self.candidates[index] = None
        self.attempts[index].append({"armed_ms": now_ms, "cursor": cursor, "result": "ARMED"})

    def tick(self, now_ms):
        if self.active is not None and now_ms >= self.deadline:
            i = self.active
            self.states[i] = "TIMEOUT"
            self.attempts[i][-1]["result"] = "TIMEOUT"
            self.active = None

    def observe(self, key, generation, room, kind, observation: Observation, now_ms):
        self.tick(now_ms)
        if self.active is None:
            return "NO_ARMED_STEP"
        i = self.active
        expected = self.devices[i]
        canonical = canonical_key(key)
        if (observation.home != self.home or observation.key != canonical or
                (key["physical_device_id"], key["logical_node_id"], generation, room, kind) !=
                (expected.physical, expected.logical, expected.generation, expected.room, expected.kind)):
            return "WRONG_DEVICE_OR_CONTEXT"
        if (observation.clock_domain != self.domain or observation.cursor <= self.cursor or
                observation.observed_ms < self.arm_ms or observation.observed_ms > now_ms or now_ms < self.arm_ms):
            return "NOT_FRESH_STIMULUS"
        if self.candidates[i] is None:
            if observation.stage != "node_created" or observation.result != "PASS":
                return "CREATION_EVIDENCE_REQUIRED"
            self.candidates[i] = canonical
        elif self.candidates[i] != canonical:
            return "DIFFERENT_CANDIDATE"
        if observation.result != "PASS":
            return "NON_PASS_EVIDENCE"
        self.evidence[i].add(observation.stage)
        self.states[i] = "LOCAL_OBSERVED"
        if expected.required_stages <= self.evidence[i]:
            self.states[i] = "PASS"
            self.attempts[i][-1].update(result="PASS", key=canonical)
            self.active = None
        return self.states[i]

    def result(self):
        return "PASS" if all(s == "PASS" for s in self.states) else "PARTIAL"
