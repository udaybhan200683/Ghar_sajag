#!/usr/bin/env python3
"""HOST-ONLY semantic/transaction model and derived 72h candidate ledger.
No production codec, backend contract, reducer or physical reserve implementation.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import struct

RATES = {'NORMAL': 384, 'HIGH': 1776, 'STRESS': 23232}
PROFILES = {
    'ordinary': (2, False, False),
    'mixed': (15, True, False),
    'door_user': (60, True, False),
    'node_loss': (15, True, True),
    'simultaneous': (2, False, False),
    'saturation': (15, True, False),
    'reboot': (15, True, False),
}
HEADER_TYPICAL = 728 + 64
HEADER_MAX = 1370 + 64  # charged summary-context extension, not codec modification
PAYLOAD_MAX = 4096 - HEADER_MAX

@dataclass(frozen=True)
class Event:
    node: int
    origin: int
    seq: int
    at: int
    kind: str = 'motion'
    end: int = 0
    repeats: int = 1
    safety: bool = False
    coverage: str = 'covered'
    clock_revision: int = 0
    uncertainty: int = 2
    delayed: bool = False
    owner: int = 1
    meaning: int = 1
    checkpoint: int = 0
    ever_submitted: bool = False
    monotonic_ms: int = 0
    received_s: int = 0

    @property
    def key(self):
        return (self.owner, self.node, self.origin, self.seq)

    @property
    def digest(self):
        # Host content binding only; target requires immutable-source HMAC domain.
        source = (self.key, self.at, self.kind, self.end, self.repeats, self.meaning, self.uncertainty, self.monotonic_ms)
        return hashlib.sha256(repr(source).encode()).hexdigest()

    @property
    def eligible(self):
        return (self.kind == 'motion' and not self.safety
                and self.coverage == 'covered' and self.uncertainty <= 2
                and not self.delayed and not self.ever_submitted and self.checkpoint > 0
                and -32768 <= ((self.received_s or self.at+2)-self.at) <= 32767
                and 0 < self.checkpoint <= 0xffffffff)

@dataclass(frozen=True)
class Summary:
    events: tuple[Event, ...]
    bucket_seconds: int

    def __post_init__(self):
        assert 1 <= len(self.events) <= 32
        assert all(e.eligible for e in self.events)
        first = self.events[0]
        assert all(group_key(e, self.bucket_seconds) == group_key(first, self.bucket_seconds)
                   for e in self.events)
        seqs = [e.seq for e in self.events]
        assert len(set(seqs)) == len(seqs) and max(seqs) - min(seqs) < 64
        # Source summaries that cross a bucket are excluded rather than clipped.
        assert all(e.kind != 'source_summary' or e.end // self.bucket_seconds == e.at // self.bucket_seconds
                   for e in self.events)

    def encode(self):
        e = self.events[0]
        bucket = e.at // self.bucket_seconds
        seq_base = min(x.seq for x in self.events)
        mask = sum(1 << (x.seq - seq_base) for x in self.events)
        # 34 B: version, fidelity, node/context row, meaning, local-day ordinal,
        # minute bucket, clock revision, checkpoint, 64-bit source seq base, membership,
        # tuple count, common uncertainty, coverage-record reference.
        header = struct.pack('<BBBBBHHIQQBHH', 1, 1, e.node, e.meaning,
                             (e.at // 86400) % 256, (bucket * self.bucket_seconds % 86400) // 60,
                             e.clock_revision, e.checkpoint, seq_base, mask,
                             len(self.events), e.uncertainty, 0)
        assert len(header) == 34
        out = bytearray(header)
        for x in sorted(self.events, key=lambda x: x.seq):
            slot = x.seq - seq_base
            # Keep exact point time, original monotonic clock delta and original
            # Hub receive lag. Context supplies the trusted clock mapping/basis.
            # No duration or continuous presence is inferred. Native MotionSummary
            # is excluded because its original millisecond endpoints/count remain
            # in the frozen exact body, not this candidate scalar point grammar.
            mono = (x.monotonic_ms or x.at*1000) - bucket*self.bucket_seconds*1000
            received = (x.received_s or x.at+2)-x.at
            assert 0 <= mono <= 0xffffffff
            out += struct.pack('<BHIh', slot, x.at-bucket*self.bucket_seconds, mono, received)
        return bytes(out)

    @property
    def identity(self):
        # Stable for this immutable representation. Target also binds installation,
        # segment serial and ordinal; identical content cannot change identity.
        e = self.events[0]
        return hashlib.sha256(repr((e.owner, e.node, e.origin, self.bucket_seconds,
                                     e.at // self.bucket_seconds, e.clock_revision)).encode()
                              + self.encode()).hexdigest()

    @property
    def sources(self):
        return {e.key for e in self.events}


def group_key(e, seconds):
    return (e.owner, e.node, e.origin, e.meaning, e.at // seconds,
            e.clock_revision, e.checkpoint, e.uncertainty, e.coverage)


def summarize(events, seconds=3600):
    assert seconds in (300, 900, 1800, 3600)
    groups = defaultdict(list)
    exact = []
    for e in events:
        if (not e.eligible or (e.kind == 'source_summary' and
                              e.at // seconds != e.end // seconds)):
            exact.append(e)
        else:
            groups[group_key(e, seconds)].append(e)
    summaries = []
    for group in groups.values():
        chunk = []
        for e in sorted(group, key=lambda x: x.seq):
            if chunk and (len(chunk) == 32 or e.seq - chunk[0].seq >= 64):
                summaries.append(Summary(tuple(chunk), seconds))
                chunk = []
            chunk.append(e)
        if chunk:
            summaries.append(Summary(tuple(chunk), seconds))
    assert len(exact) + sum(len(s.events) for s in summaries) == len(events)
    return exact, summaries


def workload(rate, profile, checkpoint_records=128):
    exact_percent, windows, node_loss = PROFILES[profile]
    rng = random.Random(720008 + rate)
    seqs = [0] * 6
    events = []
    # Start at local noon: 72 h intersects four local dates. No target TZ claim.
    start = 12 * 3600
    for i in range(rate * 3):
        node = i % 6
        at = start + i * 86400 // rate + rng.randrange(0, 3)
        if profile == 'simultaneous':
            at = start + (i // 192) * 192 * 86400 // rate + (i % 32)
        seqs[node] += 1
        origin = 1 if at < start + 36 * 3600 else 2
        safety = rng.randrange(100) < exact_percent
        kind = ('door_open', 'door_closed', 'call_family', 'i_am_ok')[i % 4] if safety else (
            'source_summary' if i % 3 == 0 else 'motion')
        hour = at // 3600 % 24
        if windows and kind in ('motion', 'source_summary'):
            safety |= (node in (0, 1, 2) and 5 <= hour < 11) or (
                node in (1, 4) and (hour >= 21 or hour < 7))
        coverage = 'unknown' if node_loss and node == 1 and 30 <= (at-start)//3600 < 38 else 'covered'
        delayed = i % 211 == 0
        # Full checkpoint materializes prior safety/routine consumers. Changed
        # anchors remain exact. Four 6h periods/day OR 128 arrivals, whichever
        # occurs first, are conservatively split by both coordinates here.
        cp = 1 + (i // checkpoint_records) * 100 + (at-start) // (6 * 3600)
        e = Event(node, origin, seqs[node], at, kind,
                  at + (15 if kind == 'source_summary' else 0),
                  4 if kind == 'source_summary' else 1, bool(safety), coverage,
                  int(at >= start + 48*3600), 3600 if i % 997 == 0 else 2,
                  delayed, checkpoint=cp, monotonic_ms=at*1000+rng.randrange(0,21), received_s=at+2)
        events.append(e)
    # Current last-activity anchors are retained individually, regardless of rate.
    for node in range(6):
        j = max(i for i, e in enumerate(events) if e.node == node)
        events[j] = replace(events[j], safety=True)
    if node_loss:
        for n, t in enumerate((start+30*3600, start+38*3600)):
            events.append(Event(1, 3, n+1, t, 'observation_fault', safety=True, checkpoint=1))
    # Additional exact local outcomes/health/clock/reboot evidence are charged,
    # not inferred to be included in the source-rate scenario.
    for i in range(24):
        events.append(Event(i % 6, 4, i+1, start+i*10800, 'local_outcome', safety=True, checkpoint=1))
    return events


def entries(size):
    return math.ceil(size / 32) + math.ceil(size / 4000) + 1


def pack(sizes, header):
    chunks, used = [], header
    for size in sizes:
        assert size + header <= 4096
        if used + size > 4096:
            chunks.append(4096)
            used = header
        used += size
    if used > header:
        chunks.append(4096)  # full sealed extent, including worst padding
    return chunks


def ledger(events, option='bucket', seconds=3600, worst=True, reserve=32,
           checkpoint_records=128, hot=32):
    if option == 'exact':
        exact, summaries = list(events), []
    else:
        exact, summaries = summarize(events, seconds)
    # Typical 16 B is a DERIVED planning input from prior frozen trace, not a new
    # measurement. Only 103 B frozen WARM fallback supports worst-size arithmetic.
    sizes = [103 if worst else 16 for _ in exact]
    sizes += [len(s.encode()) + 2 for s in summaries]
    header = HEADER_MAX if worst else HEADER_TYPICAL
    chunks = pack(sizes, header)
    # All 384 witnesses charged even when tails overlap. This intentionally does
    # not depend on the prior unproved certificate-release optimization.
    fixed = [4079]*6 + [3485]*3 + [6144]*3 + [512]*2 + [4096]*2 + [320]*4
    # Alternatives, not an approved critical promise. Protected preallocated
    # placeholders cost 2/4/8 extents for 32/64/128 separately admitted max HOTs.
    critical = [4096] * (2 * reserve // 32)
    # Full source staging until a selected consumer checkpoint. Each immutable
    # 32-source promotion needs TWO extents at the frozen 103 B fallback + max
    # context, ONE at typical 16 B. Charge all inputs, including exact sources,
    # because repacking must coexist; no favorable overlap/release assumption.
    stage_extents = math.ceil(checkpoint_records / 32) * (2 if worst else 1)
    cow_chunks = [4096] * ((2 if worst else 1) if option == 'exact' else stage_extents)
    # Candidate report/checkpoint/selection retains all steady old banks. This is
    # conservative extra independent COW, not assuming set_blob multi-key atomicity.
    progress = [3485, 6144, 512, 512]
    burst = [124 if worst else 36] * hot
    object_sizes = fixed + critical + chunks + cow_chunks + progress + burst
    n = 1 + sum(entries(b) for b in object_sizes)
    min_pages = math.ceil(n / 126) + 1
    # One additional engineering page; allocator fragmentation is still unproved.
    protected_peak = (min_pages + 1) * 4096
    return dict(exact=len(exact), essential_exact=sum(e.safety or e.kind not in ('motion','source_summary') for e in exact),
                source_summary_exact=sum(e.kind == 'source_summary' for e in exact), summaries=len(summaries), summarized_sources=sum(len(s.events) for s in summaries),
                payload_bytes=sum(sizes), summary_plain_bytes=sum(len(s.encode()) for s in summaries),
                summary_min=min((len(s.encode()) for s in summaries), default=0),
                summary_max=max((len(s.encode()) for s in summaries), default=0),
                history_segments=len(chunks), cow_segments=len(cow_chunks), reserve_events=reserve,
                object_sizes=object_sizes, live_entry_bytes=n*32, nvs_lower_bound=min_pages*4096,
                protected_peak_bytes=protected_peak, fixed_logical_bytes=sum(fixed),
                critical_logical_bytes=sum(critical), cow_logical_bytes=sum(cow_chunks),
                hot_entry_bytes=sum(entries(b)*32 for b in burst),
                progress_entry_bytes=sum(entries(b)*32 for b in progress),
                boundary='CAPACITY MODELED; SDK runtime test separate; reserve/eligibility/volume not approved')

class Backend:
    """Proposed atomic representation+source claims+derived effects contract."""
    def __init__(self):
        self.claims = {}
        self.identities = {}
        self.effects = set()

    def accept(self, identity, sources, digest):
        if identity in self.identities:
            assert self.identities[identity] == digest
            return 'committed'
        # Exclusive source representation claim: an exact request which may
        # have reached the server must remain exact. No silent shape replacement.
        assert all(key not in self.claims for key in sources), 'overlapping representation'
        for key in sources:
            self.effects.add(key)
            self.claims.setdefault(key, identity)
        self.identities[identity] = digest
        return 'committed'

class Store:
    """Atomic immutable-object publications, explicit selected root; no SDK claim."""
    def __init__(self, normal_limit=10000, critical_limit=32):
        self.bodies, self.witnesses, self.summaries = {}, {}, {}
        self.selected, self.checkpoint, self.acked, self.complete = set(), set(), set(), set()
        self.normal_limit, self.critical_limit = normal_limit, critical_limit
        self.reported = set()
        self.completed_sources = set()

    def ingest(self, event, committed=True, authenticated=True):
        if not authenticated or event.owner != 1 or not 0 <= event.node < 6:
            return 'unauthorized'
        if event.key in self.reported:
            return 'stale'
        if event.key in self.witnesses:
            assert self.witnesses[event.key] == event.digest, 'conflict'
            self.acked.add(event.key)
            return 'duplicate'
        normal = sum(not e.safety for e in self.bodies.values())
        critical = sum(e.safety for e in self.bodies.values())
        if (event.safety and critical >= self.critical_limit) or (
                not event.safety and normal >= self.normal_limit):
            return 'full'
        if not committed:
            return 'failed'
        self.bodies[event.key] = event
        self.witnesses[event.key] = event.digest
        self.acked.add(event.key)  # only after required immutable publication
        return 'accepted'

    def begin_exact_submit(self, key, committed=True):
        # Required durable BEFORE network send. Ambiguous publication cannot
        # authorize a send; future compaction must preserve this exact shape.
        if not committed:
            return False
        self.bodies[key] = replace(self.bodies[key], ever_submitted=True)
        return True

    def compact(self, summary, cut=None):
        assert all(k in self.bodies and not self.bodies[k].ever_submitted for k in summary.sources)
        if cut == 'before_checkpoint':
            return
        self.checkpoint |= summary.sources  # materialized consumer state abstraction
        if cut == 'before_summary':
            return
        self.summaries[summary.identity] = summary
        if cut == 'before_select':
            return
        self.selected.add(summary.identity)
        if cut == 'before_reclaim':
            return
        for key in summary.sources:
            del self.bodies[key]
        # Witness deliberately survives until a selected complete report.

    def recover(self):
        recovered = deepcopy(self)
        recovered.summaries = {i:s for i,s in self.summaries.items() if i in self.selected}
        assert all(s.sources <= self.checkpoint for s in recovered.summaries.values())
        represented = set(self.bodies) | set().union(*(s.sources for s in recovered.summaries.values()))
        assert self.acked <= represented | self.completed_sources
        return recovered

    def publish(self, backend, identity, lost_ack=False, receipt_commit=True):
        summary = self.summaries[identity]
        assert identity in self.selected
        assert backend.accept(identity, summary.sources, hashlib.sha256(summary.encode()).hexdigest()) == 'committed'
        if not lost_ack and receipt_commit:
            self.complete.add(identity)
            self.completed_sources |= summary.sources

    def reclaim_completed(self, identity):
        assert identity in self.complete
        summary = self.summaries[identity]
        assert summary.sources <= self.checkpoint
        del self.summaries[identity]
        self.selected.remove(identity)
        # Source witnesses remain; completion is not Node retirement proof.

    def retire(self, covered_absent):
        # This input stands for a validated selected complete report, never guessed
        # highest sequence; real source validation/admission bound remains separate.
        for key in covered_absent:
            self.witnesses.pop(key, None)
        self.reported |= set(covered_absent)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for scenario, rate in RATES.items():
        for profile in PROFILES:
            events = workload(rate, profile)
            for worst in (False, True):
                row = ledger(events, worst=worst)
                row.update(scenario=scenario, profile=profile, worst=worst, inputs=len(events), option='bucket',
                           checkpoint_records=128, bucket_seconds=3600, hot_count=32)
                rows.append(row)
        for option in ('exact', 'bucket'):
            for duration in ((3600,) if option == 'exact' else (300, 900, 1800, 3600)):
                row = ledger(workload(rate, 'ordinary'), option=option, seconds=duration)
                row.update(scenario=scenario, profile='comparison', worst=True, option=option,
                           checkpoint_records=128, bucket_seconds=duration, hot_count=32)
                rows.append(row)
        for reserve in (64, 128):
            row = ledger(workload(rate, 'ordinary'), reserve=reserve)
            row.update(scenario=scenario, profile=f'reserve_{reserve}', worst=True, option='bucket',
                       checkpoint_records=128, bucket_seconds=3600, hot_count=32)
            rows.append(row)
    args.output.write_text(json.dumps(rows, indent=2) + '\n')
    for row in rows:
        small = {k:v for k,v in row.items() if k not in ('object_sizes','boundary')}
        print('CAPACITY_MODELED ' + json.dumps(small, sort_keys=True))
    print('MODEL_EXIT=0; TARGET_HARDWARE=UNPROVEN')

if __name__ == '__main__':
    main()
