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
**Status:** OPEN; partially superseded by GS-D025 for the internet-only outage design target

GS-D025 locks the 72-hour design target, not a guaranteed capacity or exact local
retention policy. Other durations/counts (including 90 d / 5k / 50k / 100k),
supported event volumes and per-class retention remain OPEN. Derive them from
the actual 4 MB budget, six-Node workload, OTA needs and crash-safety reserve.

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
**Status:** OPEN; partially superseded by GS-D025/026 for approved direction

The 72-hour internet-only outage design target and eligible loss-aware ordinary
motion aggregation are now LOCKED by GS-D025/026. An unconditional offline
capacity guarantee, exact retention duration, supported event-volume envelope,
critical classification/reserve/saturation behavior, per-class byte budget,
outbox overflow policy and history-pressure threshold remain OPEN. Derive these
from the actual six-Node workload and 4 MB partition/OTA budget and record the
decision before implementing policy. Summary encoding/interval/backend contract,
motion quiet gap and progress-update frequency are not approved.

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

### GS-D021 — Storage and retrieval take priority over CPU optimization
**Status:** LOCKED

First satisfy correctness, durability, security/authentication, crash recovery, product stability, scalability and caregiver/user experience. Among qualifying designs prioritize useful information retained per flash byte, efficient deterministic retrieval, bounded RAM, and low flash write amplification/long flash lifetime, in that order. CPU-cycle efficiency is secondary. A faster host benchmark alone does not justify larger persistent records, less offline retention, weaker retrieval, durability, recovery, routine learning or caregiver behavior, or added complexity. A larger/faster representation needs strong justification and measurements showing the smaller design cannot meet realtime requirements. No product behavior, stability, scalability or UX degradation is authorized.

### GS-D022 — Missing observation is not resident inactivity
**Status:** LOCKED

The Hub routine learner and caregiver PWA must distinguish NO_ACTIVITY during adequately observed intervals from NO_OBSERVATION / SENSOR_UNAVAILABLE / HUB_UNAVAILABLE. Failed/offline sensors must not cause an inactivity conclusion. Coverage, confidence, time trust and data quality are part of current and daily routine state; positive delayed activity does not prove continuous sensor availability. Existing privacy/mode exclusions remain in force. Coverage thresholds/formulas and exact encodings remain OPEN.

### GS-D023 — Routine and daily-state failure recovery
**Status:** LOCKED

Bounded local routine learning must maintain correct current state, daily conclusions, coverage/confidence and recovery through Node power failure/reboot/rejoin, Hub power failure/reboot, radio interruption, internet/backend outages, lost backend ACK, backlog re-sync, multi-day outage, local-day rollover, delayed events, partial coverage and storage pressure. Recovery must not double-apply a logical event/baseline contribution, fabricate activity, duplicate caregiver history/daily conclusions, or lose ACK-required input. Backend retries use stable logical identities; exactly-once transport is not assumed. Daily time assignment must not fabricate trusted time. Exact retention, lateness, critical-overflow, backend effect/revision and rollback contracts remain OPEN; these decisions do not approve a partition change or production integration.

### GS-D024 — Eliminate persistent redundancy before increasing Hub storage
**Status:** LOCKED

Before increasing Hub storage allocation, storage design shall eliminate redundant persistent information and evaluate compact binary representation, shared bounded context, delta/change encoding, dictionary/reference encoding and safe semantic aggregation. Common context should be stored once where safe rather than repeated per record. Context-dependent formats must use bounded independently recoverable restart points. Storage optimization shall not weaken correctness, security, crash recovery, scalability, retrieval, routine learning or caregiver behavior.

This locks the approved design principle, not a record format, partition size,
retention horizon or backend substitution policy. GS-D021's mandatory quality
gate and CPU-secondary priority remain in force. Source strings, config/time
bindings, exact dedupe evidence and security metadata may be shared only when
their bounded lifetime and authenticated recovery are proven. The host-only
checkpoint `74c4b99` provides evidence for numeric codec/restart behavior and
conditional density; full-source serialization, target crypto/allocator,
retirement progress, derived backend effects, rollback and wear remain OPEN.
No production integration or partition change is authorized by this decision.

### GS-D025 — 72-hour internet-only outage design target
**Status:** LOCKED (design target); capacity guarantee and volume policy OPEN

**Approved:** 2026-10-08

R1 targets 72 elapsed hours of internet-only outage resilience with Hub and Nodes
powered and locally connected for the baseline scenario. Local monitoring and
routine learning continue without internet; essential safety evidence and
observation coverage remain durable. Pending information is synchronized when
the backend becomes available. This is a design target, not yet an unconditional
capacity guarantee. Supported event volume and critical saturation behavior
remain OPEN. It does not promise monitoring through power/sensor/local-radio
failure or approve a partition change. GS-D003/004/007/009/022/023 remain in force.
Only the previously undecided outage-target scope of GS-D013/017 is superseded.

### GS-D026 — Loss-aware ordinary motion aggregation
**Status:** LOCKED (product direction); representation and protocol OPEN

**Approved:** 2026-10-08

Eligible ordinary motion observations may be grouped or summarized; do not store
unnecessary repeated ordinary PIR history. Preserve information required for
routine learning, inactivity monitoring and timely safety decisions. Preserve
exact important door transitions, user actions (including Call Family and I Am
OK) and safety events. Never confuse NO_ACTIVITY with NO_OBSERVATION. Maintain
authenticated ownership, durable-before-ACK, retry, deduplication and recovery
correctness. Do not claim successful backend synchronization for data not
durably accepted by the backend. Specific summary encoding, interval, eligibility
details and backend contract remain unapproved. This refines GS-D011/024 without
approving endpoint-only substitution or weakening GS-D021/022/023.

### GS-D027 — Battery-first intelligent ESP32-C3 Nodes
**Status:** LOCKED (design requirement); new protocol and measured impact OPEN

**Approved:** 2026-10-08

R1 ESP32-C3 Nodes are battery-operated. Avoid unnecessary wake-ups, Wi-Fi
transmissions and flash writes; prefer processing triggered by meaningful sensor
observations. Do not introduce 40–120-second periodic wake-ups for activity
consolidation. Nodes may perform sensor-specific interpretation and episode
tracking; the Hub remains responsible for cross-sensor routine learning and
household decisions. Preserve GS-D020 BAT-C8 sleep/wake requirements and all
correctness/durability invariants. Any new Node protocol must prove its battery
and correctness impact before implementation. Required GPIO/timer wake,
health/retry/recovery work remains required; no new fixed progress frequency,
quiet gap, battery-life claim or qualified energy saving is established here.
Battery-first Node processing does not override GS-D021's mandatory quality gate
or authorize a competing routine-learning engine at every Node.

### GS-D028 — Sensor-specific motion, door and future bed semantics
**Status:** LOCKED (semantic boundaries); bed sensing excluded from R1

**Approved:** 2026-10-08

Ordinary PIR motion may be consolidated where safe under GS-D026. Door OPEN/CLOSE
transitions remain individually identifiable. Future bed sensors may support
occupancy START/END and duration tracking at the Node. Bed sensing is NOT being
added to R1; occupancy is not automatically equivalent to sleep or occupant
identity. This does not add bed hardware/protocol or claim that currently
unqualified door/button hardware has been installed or qualified. R1 retains
the existing 4 MB ESP32 Hub and ESP32-C3 Nodes; ESP32-S3 upgrade, final NVS size
and any hardware-scope change remain unapproved.

### GS-D029 — R1 durable-storage security scope and mandatory application rollback
**Status:** LOCKED

**Approved:** 2026-10-08, explicitly by the product owner

R1 must provide crash-consistent durable storage through ordinary power failures
and interrupted flash operations. Detect corrupted, missing or inconsistent durable
state and fail closed when trustworthy recovery is impossible. The Hub must never
silently present stale or uncertain routine state as current. Preserve authenticated
Node ownership/domain checks, durable-before-ACK, lost-ACK retry and exact deduplication,
retirement-credit correctness and every protected recovery dependency.

Deliberate restoration of an older, otherwise valid flash image is outside the R1
stored-data freshness detection guarantee. Document this limitation explicitly;
AES-GCM authenticates data but must not be represented as malicious full-flash
rollback protection. This exclusion does not permit stale fallback after ordinary
power interruption or detected corruption, or bypass uncertainty handling.

Automatic FOTA APPLICATION rollback remains MANDATORY: a failed firmware update
must normally return to the previous valid firmware through ESP-IDF OTA rollback.
Preserve signed FOTA, firmware validation and compatibility with durable storage
created by an unsuccessful upgrade. Previous valid firmware must be able to recover
that supported state correctly or fail closed; silent erase/reset or stale state
is not a compatibility solution. Application rollback and stored-data rollback
are separate concepts; the data-freshness exclusion does not waive firmware rollback.

No new security hardware, ESP32-S3 migration or flash partition change is authorized.
The existing 4 MB ESP32 Hub and ESP32-C3 Node baseline, BAT-C8 requirements and
qualification status remain unchanged. Gate C protected NVS capacity/progress,
supported event volumes and the 72-hour capacity guarantee remain unresolved.
This locks product/security scope, not a storage format, reserve, implementation
readiness or new qualification result. It resolves the previously OPEN security/
rollback scope in GS-D023/024 only to this extent; remaining technical recovery,
storage-format/FOTA compatibility, capacity and qualification gates stay open.

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

## Storage-first refinement status — 2026-10-07

GS-D021/022/023 are the only new LOCKED decisions in this checkpoint. Proposed84/104-byte authenticated records and128 KiB budgets remain gated; no72-hour guarantee, critical overflow policy or partition change is approved. Current reproduced Hub image1,864,624 B fits existing slots with101,456 B margin; the old384 KiB candidate does not fit. Retirement credit/progress, coverage/time/day finalization, derived backend completion, authenticated GC and rollback remain open. Existing host regressions pass; new failure models are specified but not implemented.


### 2026-10-07 lifecycle investigation status (no new decision)

GS-D016/021/024 remain unchanged. [Lifecycle proof evidence](../exec-plans/evidence/R1_STORAGE_RETIREMENT_RECLAIM_PROOF_20261007.md)
separates the source-proven192 Node pending keys from unbounded historical Hub
evidence under lost retirement reports.384 witnesses is conditional on a new
persisted admission/progress invariant, not an approved product policy. Host
COW/million-event tests pass within explicit model assumptions; physical
allocator/crypto/rollback and saturation/backend gates stay open.128 KiB remains
conditional; no partition decision,72h guarantee or new LOCKED requirement.

### 2026-10-07 admission and physical storage findings (no new decision)

GS-D016/021/024 unchanged. [Admission/NVS/raw host evidence](../exec-plans/evidence/R1_STORAGE_ADMISSION_RAWFLASH_PROOF_20261007.md)
derives conditional6*(32+W) exact-key bound; W32/C split is not approved numerical
policy. Critical/normal saturation still requires a product decision. Whole NVS
fresh-image packing can fit synthetic72h sample/max at122880/126976 B; actual
runtime/GC peaks remain unproved. Conservative independent raw state banks
correct the old20 KiB reservation to24 KiB; raw sample/max comparison
131072/135168 B.128 KiB remains conditional; no partition/hardware migration or
storage backend selection approved. No new LOCKED requirement/CONTEXT_VERSION.

### 2026-10-08 NVS runtime/saturation evidence (no new decision)

GS-D013/014/015/017 and GS-D016/021/024 keep their status. The
[installed-IDF NVS runtime probe](../exec-plans/evidence/R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md)
completes 10,000 heavy replacement cycles with nine sealed segments but uses
all previously counted application COW/engineering pages as allocator churn.
At higher live occupancy, a retirement-report replacement fails even while
NVS retains one erased page; a tested write cut also leaves the replaced
report key absent after remount. A 192-maximum-HOT coexistence fixture fails
before all 192 can be admitted. These are technical counterexamples to the
current fresh-image reserve proof, not a new product capacity policy or a
general rejection of NVS/128 KiB. NVS stays the preferred candidate; raw is
fallback only. Exact offline/critical/saturation/backend policy and technical
credit/root/physical guard/wear/RAM closure remain OPEN. No partition,
hardware, production implementation or CONTEXT_VERSION decision is made.

### 2026-10-08 NVS blocker diagnosis (technical findings, no new decision)

[Follow-up evidence](../exec-plans/evidence/R1_STORAGE_NVS_BLOCKER_DIAGNOSIS_20261008.md)
classifies cut1072 as FAULT_INJECTION_MODEL_DEFECT; corrected power-off latching
and independent report/selector host transactions recover old/new across2702
checks. The capacity failures remain: nine segments+192 maximal HOT+report/
checkpoint progress first completes in the152 KiB fixture; a three-segment
fixture also completes at128 KiB. No product horizon/overflow policy or universal
minimum is inferred. NVS remains the technical candidate; raw fallback and4 MB
Hub remain.192/256 KiB review layouts/current-image fit do not approve partition
changes or future firmware growth. GS-D013/014/015/017 remain OPEN; GS-D016/021/
024 and other LOCKED decisions remain unchanged. Production readiness remains
NO pending policy, authenticated persisted admission/root/physical guard, target
RAM/OTA/wear and rollback. CONTEXT_VERSION remains2026-10-07.003.
