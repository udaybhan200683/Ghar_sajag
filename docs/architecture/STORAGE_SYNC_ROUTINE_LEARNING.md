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
approved retention, guaranteed outage capacity, priority or partition requirement.
GS-D025 separately locks the 72-hour design target; GS-D026–028 lock aggregation,
Node and sensor boundaries without approving these proposed mechanisms. Its current-image,
protocol-progress, backend-contract, rollback and crash/wear limits remain
explicit. This canonical contract and LOCKED decisions retain authority.

Its efficiency section adds isolated host-only implementation/evidence and a
single-immutable-payload proposal. It does not authorize a new deployed format,
retention/overflow policy or partition size. Prove optimized fit in the existing
128 KiB durability area before treating enlargement as necessary; all canonical
durability, backend-first sync and independent lifecycle requirements remain.

Before final storage implementation, calculate and approve:
- worst-case six-Node semantic event rate;
- supported volume and critical saturation behavior against the approved 72-hour internet-only outage design target;
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

GS-D022/023 require bounded current-day and daily routine state, coverage/confidence and recovery through Node/Hub/radio/cloud failures, reboot/rejoin, lost ACK, delayed events, midnight, multi-day backlog and pressure. NO_ACTIVITY requires adequate observation; NO_OBSERVATION, sensor/Hub unavailability and untrusted time must remain distinguishable locally and in backend/PWA effects. Missing observation cannot train an inactive baseline. Stable daily identity and durable finalization must prevent double baseline application and duplicate backend days. Exact coverage sufficiency, late revision policy, guaranteed offline capacity and overflow semantics remain OPEN; GS-D025 locks the 72-hour design target only. The ExecPlan contains proposed formats and proof obligations, not additional locked numerical policy.

## Information-density principle — GS-D024

**LOCKED:** Before increasing Hub storage allocation, storage design shall eliminate redundant persistent information and evaluate compact binary representation, shared bounded context, delta/change encoding, dictionary/reference encoding and safe semantic aggregation. Common context should be stored once where safe rather than repeated per record. Context-dependent formats must use bounded independently recoverable restart points. Storage optimization shall not weaken correctness, security, crash recovery, scalability, retrieval, routine learning or caregiver behavior.

The [storage ExecPlan](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
section22.10/22.11 and [density evidence](../exec-plans/evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md)
separate numeric host results from proposed complete source/security formats.
128 KiB remains CONDITIONAL. The72-hour NORMAL comparison with full name/config
context and timing variation has zero spare for sample names and a4096-byte
deficit at maximum names under the unproven fixed-reservation ledger. It is
not an approved outage guarantee or proof that partition enlargement is needed.
Exact offline/saturation policy, retirement credits, backend summary/day
completion, time/coverage/late recovery, authenticated nonce/root/reclaim,
rollback and target RAM/wear remain STOP gates. Keep near-real-time connected
sync, one shared event body where safe, bounded routine state and
NO_ACTIVITY distinct from NO_OBSERVATION under GS-D021/022/023.


## Lifecycle proof status at context2026-10-07.003

The [focused host lifecycle evidence](../exec-plans/evidence/R1_STORAGE_RETIREMENT_RECLAIM_PROOF_20261007.md)
proves the32-key Node pending bound, not a finite historical Hub evidence bound.
Report loss can coexist with continued event ACKs; complete-set retirement is
gap-safe but requires bounded admission/report progress for a finite Hub ledger.
A384-witness credit-gated model is proposed and host-tested only. Backend
completion and Node retirement remain independent owners. A dedupe-only53-byte
certificate cannot replace unsynced source/replay information. Root release
before erase is host-modeled; authenticated allocator/nonce/rollback/physical
peak proof remains open. Raw conditional128 KiB sizing does not include NVS
entry tax by implication; no production capacity/retention guarantee is closed.
No policy change or new requirement; use ExecPlan section23 for the next proof.

## Admission and physical backend proof status (technical findings only)

[Focused evidence](../exec-plans/evidence/R1_STORAGE_ADMISSION_RAWFLASH_PROOF_20261007.md)
and ExecPlan section24 derive a conditional complete-report plus finite uncovered
credit window:6*(32+W) exact witnesses; W32 tolerates one Node retained flight.
Report/control selection must progress independently of normal admission, and
critical reserves cannot be unlimited bypasses. Final critical/overflow policy
and durable credit/recovery remain OPEN. Credits do not free backend-pinned
bodies; NO_OBSERVATION remains distinct from inactivity.

Whole-object NVS fresh-image mapping fits synthetic72h NORMAL sample/max with
stated reserves, unlike an isolated event-pool tax estimate. This is not runtime
allocation/GC proof. Independently erased raw checkpoint banks need24 KiB for
three6144-byte images; shared20 KiB arena needs a release/allocator proof. Current
128 KiB remains CONDITIONAL and storage backend UNDECIDED. Do not infer a72h
product guarantee, partition enlargement or hardware migration. Next host step
is actual IDF NVS runtime tail/promotion/GC peak proof; no production integration
or new numerical requirement/context version.

## NVS runtime proof status at context2026-10-07.003 (technical findings only)

The [installed-IDF host runtime evidence](../exec-plans/evidence/R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md)
supersedes only the assumption that fresh-image NVS free pages remain reserved
under churn. Nine sealed segments can churn for10,000 modeled heavy cycles,
but the application COW/engineering reserve is consumed; at higher occupancy
retirement-report replacement returns not-enough-space with one NVS free page.
A 192 maximum-HOT standalone-tail coexistence fixture fails before complete
admission, and a sampled report-blob write cut remounts without that key.
Authenticated selected/previous report banks and durable root/credit selection
are still required. No full NVS workload/flash-life/RAM/rollback proof exists.
NVS is the preferred R1 backend candidate, raw is fallback; current128 KiB
and4 MB Hub viability remain conditional, and no numerical product policy or
partition/hardware change is approved.

## NVS diagnostic refinement (technical evidence, no requirement change)

[Cut1072 follow-up](../exec-plans/evidence/R1_STORAGE_NVS_BLOCKER_DIAGNOSIS_20261008.md)
corrects the prior power-loss interpretation: the emulator resumes writes after
one failure, permitting destructive error cleanup; a latched interruption
recovers complete old/new. An independent report/selection prototype passes
focused cuts, while authenticated credit/root persistence remains open. Existing
nine-segment128 KiB mapping fails maximum192-HOT+report/checkpoint progress;
tested152 KiB or fewer history segments can progress conditionally. No offline
horizon, saturation policy, partition/backend approval or target wear/RAM claim.
NVS remains the technical candidate; production implementation remains gated.

## Approved outage and sensor-processing requirements — GS-D025–028

**LOCKED design target (GS-D025):** R1 targets 72 hours of internet-only outage
resilience with Hub and Nodes powered and locally connected. Local monitoring
and routine learning continue without internet. Essential safety evidence and
observation coverage remain durable; pending information is synchronized when
the backend becomes available. This is not an unconditional capacity guarantee
or a promise covering power loss or local radio failure. Supported event volume
and critical saturation behavior require separate closure.

**LOCKED aggregation direction (GS-D026):** Eligible ordinary motion observations
may be grouped or summarized to avoid unnecessary repeated PIR history. Preserve
information needed for routine learning, inactivity evaluation and timely safety
decisions, including necessary observation timing and coverage. Preserve exact
important door transitions, user actions (Call Family and I Am OK) and safety
events. Never equate NO_ACTIVITY with NO_OBSERVATION or infer continuous presence
from an episode. Preserve authenticated ownership, durable-before-ACK, lost-ACK
retry safety, deduplication and reboot/recovery correctness. Backend delivery is
complete only for information durably accepted by the backend. Summary encoding,
intervals and the backend contract remain unapproved.

**LOCKED battery-first Nodes (GS-D027):** ESP32-C3 Nodes are battery-operated.
Avoid unnecessary wake-ups, Wi-Fi transmissions and flash writes; prefer
processing triggered by meaningful sensor observations. Do not introduce
40–120-second periodic wake-ups for activity consolidation. Nodes may perform
sensor-specific interpretation and episode tracking; household routine learning
and cross-sensor decisions remain at the Hub. Preserve BAT-C8 sleep/wake
requirements and necessary health, retry and recovery behavior. A new Node
protocol must prove battery and correctness impact before implementation. This
direction does not change BAT-C8 qualification status or override GS-D021's
mandatory correctness gate and storage/retrieval priority.

**LOCKED sensor boundaries (GS-D028):** Ordinary PIR motion may be consolidated
where safe. Door OPEN/CLOSE transitions remain individually identifiable. Future
bed sensors may track occupancy START/END sessions and duration at the Node,
with observation availability and uncertainty preserved. Bed sensing is excluded
from R1; occupancy establishes neither sleep nor occupant identity. No new
hardware or physical sensor qualification is implied.

Still **OPEN**: final critical-event classification and reserve size; guaranteed
NORMAL/HIGH/STRESS event-volume bounds; motion quiet gap; progress-update
frequency; final summary encoding/backend protocol; final NVS partition size.
The existing 4 MB ESP32 Hub remains the baseline pending technical qualification;
ESP32-S3 migration and any R1 hardware scope change are not approved. Existing
host models remain conditional evidence, not capacity or battery qualification.

## R1 storage-security scope and FOTA compatibility — GS-D029

**LOCKED:** durable storage must be crash-consistent under ordinary power failure
and interrupted flash operations. Detect corrupted, missing or inconsistent durable
state; recover trustworthy committed state or fail closed. Never silently expose
stale or uncertain routine state as current. Preserve authenticated ownership,
durable-before-ACK, exact retry/deduplication, persisted retirement-credit correctness
and all still-required recovery dependencies. Missing observation remains distinct
from no activity; this decision does not approve older-root fallback after data loss.

Deliberate restoration of an otherwise valid older flash image is outside the R1
stored-data freshness detection guarantee. Document that limitation explicitly.
AES-GCM/authentication alone does not detect malicious full-flash rollback. R1 does
not acquire a new independent monotonic security-hardware requirement for that
excluded threat. Ordinary crash consistency, detected-corruption handling and
trustworthy recovery remain required; a scope decision does not prove them implemented.

Automatic FOTA APPLICATION rollback remains MANDATORY. A failed update must normally
return to the previous valid firmware through ESP-IDF OTA rollback. Preserve signed
FOTA, firmware validation and compatibility with durable storage created by the
unsuccessful upgrade. Storage-format transitions must preserve a correct recovery
path for previous valid firmware, or fail closed if trustworthy recovery is impossible;
silent erase/reset and stale successful recovery are prohibited. Application rollback
is distinct from stored-data rollback. No particular migration mechanism is approved.

Gate C protected next-operation NVS capacity/progress and the 72-hour supported-volume/
capacity guarantee remain OPEN. No new security hardware, ESP32-S3 upgrade, partition
change or production integration is approved. Existing 4 MB Hub/ESP32-C3 and BAT-C8
scope/qualification remain unchanged. Historical stronger nonrollback host-authority
assumptions are evidence for their stated model, not additional R1 requirements.
