# Ghar Sajag Product / Architecture Decision Log

Use:
- LOCKED = approved; changing requires explicit approval.
- PROVISIONAL = working direction.
- OPEN = unresolved.
- SUPERSEDED = replaced but retained for history.

### GS-D001 — R1 fresh-install scope
**Status:** LOCKED  
R1 is a commercially installable fresh baseline. Arbitrary dev-era persistence migration is post-R1 unless it blocks the fresh-install path.

### GS-D002 — R1 quality rule
**Status:** LOCKED  
Reduce scope, not correctness/security/durability standards.

### GS-D003 — Hub hardware baseline
**Status:** LOCKED  
Design R1 for the existing 4 MB Hub first. ESP32-S3-N16R8 remains future/optional unless explicitly approved.

### GS-D004 — Six Nodes share Hub storage
**Status:** LOCKED  
Storage is shared across Nodes; it is not a full independent journal per Node.

### GS-D005 — 128-event lifetime is unacceptable
**Status:** LOCKED  
Product lifetime must not be capped by a finite event count. Increasing 128 alone is not a correct fix.

### GS-D006 — Hub is not long-term caregiver database
**Status:** LOCKED  
Long-term history/analytics are backend responsibilities. Hub local storage is durability, outage buffering, current learned state, and short-term cache/history.

### GS-D007 — Connected sync is near-real-time
**Status:** LOCKED  
When connected, caregiver-relevant information is synchronized continuously/near-real-time. Do not wait for storage pressure or PWA open.

### GS-D008 — PWA is backend-first
**Status:** LOCKED  
Caregiver opens already-synchronized backend data; dashboard-open sync with Hub is not the main freshness mechanism.

### GS-D009 — Cloud outage does not disable local safety
**Status:** LOCKED  
Local sensing, alerts, durability, and routine learning continue during backend outage. PWA shows stale/offline state.

### GS-D010 — Basic AI is local + bounded
**Status:** LOCKED  
Current safety-relevant routine/baseline/trend logic runs locally using bounded state/aggregates. Backend may add richer analytics.

### GS-D011 — Raw sensor chatter is not permanent history
**Status:** LOCKED  
Repeated low-value raw transitions may be coalesced when correctness allows.

### GS-D012 — Storage pressure degrades history, not safety
**Status:** LOCKED  
Prefer reclaim/compress lower-value history while preserving correctness-critical state and continuing operation.

### GS-D013 — Exact retention values
**Status:** OPEN  
Previously discussed 72 h / 90 d / 5k / 50k / 100k values are not locked. Derive them from actual 4 MB budget, six-Node worst case, outage target, OTA needs, and crash-safety reserve.

### GS-D014 — Backend outbox policy
**Status:** OPEN  
Define bounded offline backlog and behavior for extremely long backend outages without permanent local safety failure.

### GS-D015 — Partition-layout change
**Status:** OPEN  
Do not alter partitions until byte budget and OTA impact are reviewed.

### GS-D016 — Storage/data-lifecycle design is the next R1 product blocker
**Status:** LOCKED (priority); policy details OPEN  
The shared 128-event lifetime ceiling is commercially unacceptable. The next design must derive active correctness/dedupe state, materialized reducer state, backend outbox, short history/cache, safe reclamation, offline capacity, flash wear, and OTA fit for the existing 4 MB Hub and six shared Nodes. Do not increase the event constant as the fix or repeat the already-passed fresh-install/lost-ACK physical qualification absent an invalidating change.

### GS-D017 — Storage retention and outage limits remain undecided
**Status:** OPEN  
No exact retention duration, offline guarantee, per-class byte budget, outbox overflow policy, or history-pressure threshold is approved. Derive options from the actual six-Node workload and 4 MB partition/OTA budget, then record the product decision before implementing policy.

### GS-D018 — Ordinary PWA privacy toggle is not supported
**Status:** LOCKED  
The ordinary household PWA mode selector does not expose a generic Privacy ON/OFF control. Consent withdrawal may enforce an internal privacy state, and routine rules suppress passive evidence while that state applies. Privacy enforcement and notification preferences remain separate. Sources: current [P0 product requirements](P0_PRODUCT_REQUIREMENTS.md), [caregiver guide](../features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md), and [routine rules](../features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md); later application release notes and validation checklist record removal of the ordinary control.

### GS-D019 — BAT-C8 R1 release classification
**Status:** SUPERSEDED by GS-D020  
This prior open classification is closed by the explicit production requirement in GS-D020. It must not be treated as an outstanding scope conflict.

### GS-D020 — BAT-C8 production-critical power behavior is R1-required
**Status:** LOCKED  
BAT-C8 is an `R1_REQUIRED_FEATURE_WITH_PENDING_QUALIFICATION`. Before R1 production release, physical qualification must prove the intended production sleep entry; required GPIO/timer wake; bounded wake/resume; sensing/runtime restoration; required radio restoration; fail-awake/safe failure behavior; and no regression of required event processing. This requirement does not make final battery-life optimization or long-duration endurance characterization an R1 blocker unless R1 makes an explicit battery-life claim. BAT-C8 test cases P1–P10 remain NOT_RUN until separately authorized; those labels are test IDs, not priority levels.

**Jira traceability:** GS-114 covers implementation/focused qualification; GS-146 covers final R1 battery closure. These links do not assert either issue or the physical qualification is complete.

## Reconciliation status — 2026-10-07

The already-qualified native fresh-install and empty-AEAD/recovery changes are
committed; no new product decision was made. The legacy journal migration host
gate also fails on the untouched starting commit and remains DEFER_POST_R1 under
GS-D001. See `docs/progress/R1_WORKTREE_RECONCILIATION_20261007.md` for attribution,
validation limits and preserved files. GS-D016's storage blocker and GS-D020's
pending physical qualification remain open work; CONTEXT_VERSION is unchanged.

## Storage architecture analysis — 2026-10-07

The proposed [R1 Hub storage/data-lifecycle ExecPlan](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
audits baseline `cd8d126ab44689cc9c6ebbbe74e6dce058d4323b` and proposes
a conditional 4 MB dual-OTA layout. **No new LOCKED decision is made.**
GS-D013/014/015/017 remain OPEN: outage/full-detail guarantees, critical overflow
and summary priorities, partition acceptability and exact numerical policy need
review. Retirement report progress/admission bounds, complete reducer limits,
new backend effect/summary completion semantics, rollback compatibility,
current signed image fit and crash/wear proofs also block implementation.
The candidate figures are analysis, not product requirements; context version
is unchanged. No firmware, partition, backend/PWA or hardware action occurred.

## Storage efficiency host core — 2026-10-07

User-authorized policy-neutral primitives are implemented outside production:
compact lossless experimental Node-event frames, bounded exact-key index,
integer statistics, record cursor and host tests/benchmarks. Documentation-only
architecture checkpoint: `94fe1a8`. The ExecPlan efficiency section challenges
the earlier budgets and prioritizes proving the existing 128 KiB partition.
Candidate108/128-byte authenticated envelopes,25 KiB engine RAM and smaller
routine/state models remain proposals. No new LOCKED policy, format activation,
partition approval or context-version change occurs. Million-event bounded host
fixtures and sanitizer/regression checks do not close production retirement,
backend, critical-overflow, crash/reclaim, image-size, wear or rollback gates.

## Maintenance

Append a new GS-Dxxx entry when a new product/architecture decision must survive future sessions. Never silently rewrite a LOCKED decision; supersede it explicitly.
