# Hub Storage, Cloud Sync, PWA Freshness, and Routine-Learning Contract

## Architectural intent

The Hub is not the long-term caregiver database.

Hub responsibilities:
- authenticated Node ingestion;
- local safety/routine decisions;
- durable processing before ACK;
- retry/dedupe/recovery state;
- short-term buffering/history;
- current learned routine/baseline/trend state;
- near-real-time backend synchronization when connected;
- outage buffering and backfill.

Backend responsibilities:
- long-term caregiver history;
- longer-term analytics/trends;
- prepared data for the PWA;
- serving PWA without waiting for Hub sync at dashboard open.

## Normal connected flow

1. Node sends event.
2. Hub authenticates and durably commits required state.
3. Hub updates local rules/routine learning.
4. Hub ACKs Node only after required local durability.
5. Hub immediately queues caregiver-relevant information for backend sync.
6. Backend durably stores/processes it and ACKs completion.
7. Hub later reclaims local payload/history when cloud and local correctness dependencies permit.
8. PWA reads already-synchronized backend state and receives subsequent updates from backend.

Dashboard-open must not trigger the primary Hub synchronization.

## Connectivity outage

If backend/internet is unavailable:
- local sensing/alerts continue;
- routine learning continues;
- unsynced data is buffered locally;
- PWA shows last-update/offline/stale status;
- Hub retries with bounded backoff.

When connectivity returns:
- backlog is backfilled;
- backend reconstructs missing timeline/aggregates;
- PWA becomes current;
- eligible local backlog is reclaimed.

## Storage classes

### Correctness-critical active durability state
For durable-before-ACK, lost ACK, duplicate suppression, crash recovery, authenticated ownership, and retirement semantics. Must be bounded without indefinite history.

### Backend outbox
Only data still required for backend delivery. Separate logical responsibility from durability journal. Needs explicit bounded outage/backlog policy.

### Short-term local event/history cache
Rolling/reclaimable recent data for short context, diagnostics, and outage buffering. Its retention limit must never stop live processing.

### Materialized reducer/routine state
Compact persistent state needed to recover current household state, baseline/trend statistics, and product logic without replaying indefinite raw history.

### Long-term history/analytics
Primarily backend storage.

## Event representation

Do not persist every electrical/sensor transition forever.

Repeated PIR activity should be coalesced where semantics allow:
- raw: many motion edges;
- semantic: activity session start/end/duration/count;
- aggregate: daily first activity, active duration, session count, deviation.

Preserve exact raw identity only where correctness, security, troubleshooting, or an approved retention requirement needs it.

## Storage-pressure behavior

Finite flash cannot preserve unlimited unsynced history.

Degrade in this order:
1. reclaim synced and locally-unneeded low-value history;
2. coalesce repetitive low-value detail;
3. preserve compact summaries/aggregates;
4. preserve correctness-critical retry/dedupe state;
5. reserve capacity for high-priority safety/security events;
6. continue sensing/local safety/routine learning even if historical detail is reduced.

Exact priority classes/thresholds remain open.

## Routine learning / Basic AI

Routine learning should use bounded statistics such as:
- usual first/last activity;
- per-zone activity counts/durations;
- time-of-day histograms;
- weekday/weekend baselines;
- rolling means/variance;
- recent trend/delta;
- sample/confidence counts;
- anomaly/deviation state.

Safety-relevant current learning runs locally. Backend can compute richer longer-term analytics from synchronized data.

All persistent learning structures must have explicit fixed bounds.

## Hardware constraint

R1 is constrained to the existing 4 MB Hub unless hardware migration is explicitly approved.

Therefore derive capacity from:
- actual partition table;
- dual OTA/FOTA needs;
- NVS/security/ownership;
- active durability;
- backend outbox;
- short history;
- materialized routine state;
- crash-safe cleanup reserve;
- measured record sizes;
- worst-case six-Node behavior.

Do not choose arbitrary event-count targets first.

## Numerical closure still required

The [R1 Hub storage/data-lifecycle ExecPlan](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
contains the 2026-10-07 source audit, derived workload scenarios, candidate byte
budgets/layouts and implementation STOP gates. It is a **proposal**, not an
approved retention/outage/priority or partition requirement. Its current-image,
protocol-progress, backend-contract, rollback and crash/wear limits remain
explicit. This canonical contract and LOCKED decisions retain authority.

Its efficiency section adds isolated host-only implementation/evidence and a
single-immutable-payload proposal. It does not authorize a new deployed format,
retention/overflow policy or partition size. Prove optimized fit in the existing
128 KiB durability area before treating enlargement as necessary; all canonical
durability, backend-first sync and independent lifecycle requirements remain.

Before final storage implementation, calculate and approve:
- worst-case six-Node semantic event rate;
- offline outage survival target;
- outbox/event record encoding and size;
- exact flash budget;
- active durability bound;
- cloud backlog bound;
- recent-history bound;
- routine-state size;
- cleanup/reclamation reserve;
- flash-wear estimate;
- OTA application headroom.

## Storage-first engineering and failure-aware routine requirements

GS-D021 requires the mandatory correctness/durability/security/recovery/stability/scalability/UX gate before optimization. Then prioritize useful information per flash byte, deterministic retrieval, bounded RAM and flash lifetime; CPU optimization is secondary. Preserve one immutable event body shared by lifecycle owners where safe. Larger records require measured realtime justification, not a host microbenchmark advantage.

GS-D022/023 require bounded current-day and daily routine state, coverage/confidence and recovery through Node/Hub/radio/cloud failures, reboot/rejoin, lost ACK, delayed events, midnight, multi-day backlog and pressure. NO_ACTIVITY requires adequate observation; NO_OBSERVATION, sensor/Hub unavailability and untrusted time must remain distinguishable locally and in backend/PWA effects. Missing observation cannot train an inactive baseline. Stable daily identity and durable finalization must prevent double baseline application and duplicate backend days. Exact coverage sufficiency, late revision policy, offline horizon and overflow semantics remain OPEN. The ExecPlan contains proposed formats and proof obligations, not additional locked numerical policy.
