# Durable Hub state transitions and effect intent

Status: **broader reducer/runtime design remains incomplete**. The Node
retirement report, report snapshot, exact EventKey digest and checkpoint
ownership components are implemented and host tested in the durable-storage
worktree. Base:
`cad13231d9e6a5b43268d3fa7d658fe504289e6e`. This document addresses the
missing ordered inputs identified by [HUB_REDUCER_CHECKPOINT.md](HUB_REDUCER_CHECKPOINT.md).
It specifies a candidate durability contract and records product policies that
must be settled before firmware is written. It does not design reclamation.

## Actual mutation inventory

Code paths are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.
"Ordered" below means ordered with respect to *all* other Hub product
transitions, not merely ordered within one store.

| Mutation / trigger | Owner and function | Current durability and ordering | Replay now? | External effect? | Proposed class |
| --- | --- | --- | --- | --- | --- |
| Accepted motion, door, heartbeat, OK and privacy events; routine observations; event-derived coverage and activity | `HubRuntime::run_state_once/apply_committed_event`, `RoutineService::apply`, `RulesCore::apply_event/apply_activity_event`, `CoverageTracker::observe` | Event is an authenticated journal slot before reducer apply, in slot order. Replay uses `nullopt` local minute, while host live path can use one. | Partial | Rule signals can result | Durable transition required: event plus every nondeterministic reducer input and effect intent. |
| Node admission, required set and removal | `HubRuntime::authorize_node/revoke_node`, `CoverageTracker::require_node/forget_node`; security registry | Registry is separately durable, but its saves are not globally ordered with journal events. Runtime required-set state is RAM. | No | Indirect absence effect | Durable configuration/authorization transition required. |
| Sensor fault and coverage eligibility | `CoverageTracker::set_sensor_fault/current`; `RoutineService::set_coverage` | Fault and sampled coverage are RAM; `current` is a query over Node health and time. No interval history. | No | Indirect absence effect | Fault change is durable if it changes rule eligibility; coverage calculation is recomputable from durable inputs only after its time/lease semantics are fixed. |
| Routine window start, mode and missing incident decision | `HubRuntime::start_window/set_mode/deadline`, `RoutineService`, `RulesCore::evaluate_deadline` | RAM only; `missing_incident_created` mutates before decision return. | No | Yes for deadline | Window/mode transition and positive deadline decision required. Pure unsuccessful polls need no write. |
| Activity config, monitor start and rule timer decisions | `HubRuntime::configure_activity_rules/start_activity_monitor/activity_timers`, `RulesCore::start_activity_monitor/evaluate_activity_timers` | RAM only; alert flags mutate before signals return. | No | Yes when signal created | Config/monitor transition and each decision that changes state or emits an effect required. No per-tick write. |
| Morning/night state changes and door resolution | `RulesCore::apply_activity_event` | Derived from event but also needs local minute, config, mode and coverage context absent from journal. | No in full rule path | Morning completion, unusual night activity, door open/close signals | Journal event transition must carry the decision context or a canonical reducer delta and effect intent. |
| Trusted-time anchor and correction | `TrustedClock::anchor/estimate` | Uptime anchor in RAM, no target time source; rule calls receive time/trust externally. | No | Indirect | Clock trust for an uptime is volatile; a rule decision based on a trusted estimate must record its logical epoch, uncertainty/source and config context. Meaningful clock-acquisition/correction transitions are required when they change schedules/eligibility. |
| Node online lease, authenticated health, session and power telemetry | `HubRuntime::observe_authenticated_contact/health`, radio callbacks; security link | RAM monotonic time; registry maintains separate session floor. | Intentionally no | None directly | Volatile by design; rejoin/reobserve. Epoch coverage history is a separate product question. |
| Backend event completion | `CloudSync::handle_backend_reply`, `HubJournal::acknowledge_cloud` | Write-once slot-bound HMAC receipt after authenticated matching COMMITTED reply. Separately durable, not globally ordered with reducer state. | Yes for existing event slot | Backend commit has already happened | Backend authoritative plus durable Hub receipt; do not replay as a reducer event unless business state depends on it. |
| Incident alert, notification, escalation, cancellation and resolution | Hub rule decision; `backend/ghar_sajag/durable_commit.py`, `notifications.py`, `incidents.py` | Hub rule signals are RAM; backend event/alert/outbox commits are durable after receipt. Escalation and human resolution are backend-owned. | Hub intent: no; backend: yes | Yes | Hub effect intent required for rule output. Backend is authoritative for notification lifecycle; no mirrored Hub timer transitions for backend-owned escalation. |
| Ingest queue, radio/Wi-Fi/FOTA state, retry timers | `HubRuntime`, target adapter, `CloudSync` | RAM, local queue order only | Recreated/retried | No direct business effect | Volatile by design. Repeated packets and retries cannot create new logical transitions. |

The production target calls `run_state_once()` without local minute, passes
`hub_received_at=0`, and does not wire the richer routine/timer/config path.
Thus the existing journal-only production replay matches only a restricted
event-derived path; host simulation does not have that limitation. Backend
escalation is not a Hub timer in the current source.

## One durable order and minimum records

Use one Hub-owned, serialized **logical commit sequencer**. Every accepted
product transition receives `(log_epoch, hub_transition_ordinal)` in one
committed record; ordinals increase across Nodes, timer decisions and config
changes, independent of wall time. The next ordinal is derived from the last
validated record at boot. There is no separate NVS counter write. A duplicate
Node EventKey maps to its already committed transition, receives its previous
ACK and produces no new ordinal. Failed/rejected inputs also produce none.

The minimum architecture change is a **unified logical replay stream** backed
by the existing Node event journal for event payloads plus a small sidecar for
non-event transitions and atomic effect envelopes. Each committed record must
carry the global ordinal, a journal generation, type, source/reason, schema
version, config version/hash, and authenticated payload. Event records need
to carry the same ordinal and the local-minute/clock/coverage decision
context if that context cannot be derived from other ordered records. The
sidecar alone cannot assign a durable order to old event slots. Legacy records
retain implicit physical slot order only during migration. A common logical
stream index merges event and sidecar records by ordinal; there must be no
ambiguous gaps or duplicate ordinal with different bytes. This requires a
journal format/store change, though no checkpoint or reclamation is built here.

Candidate sidecar types, emitted only on actual logical change:

* `CONFIG_APPLIED`: immutable canonical HomeConfig snapshot or content-addressed
  reference, plus version/hash; includes timezone, schedule, thresholds, room
  mapping and mode. `REQUIRED_SET_CHANGED` binds a registry generation/hash and
  explicit required-node assignment. A registry save and its logical config
  transition need one ordered commit protocol; independent NVS saves are not
  enough.
* `WINDOW_STARTED` or `WINDOW_CLOSED`: window ID, config version, epoch
  boundaries and reset policy. `MONITOR_STARTED`: epoch anchor and reason.
  `MODE_CHANGED`: mode and source. Privacy events remain event transitions.
* `SENSOR_FAULT_CHANGED`: Node identity and fault/clear source. Lease expiry
  may be recomputed at evaluation time; if it changes a persistent coverage
  decision, record that decision and its trusted-time context.
* `CLOCK_CONTEXT_CHANGED`: source, estimate interval, uncertainty, trust and
  timezone/config version, only when acquisition/correction changes logical
  scheduling or eligibility. Never serialize raw uptime as a future deadline.
* `RULE_DECIDED`: trigger identity (event ordinal or scheduled window/deadline
  ID), logical evaluation epoch, config version, resulting bounded state delta
  and zero or more canonical effect intents. A positive timer/deadline
  transition belongs here; unsuccessful polls and unchanged timer ticks do not.

Pure event-derived state need not be copied into each record if replay under
the recorded config and decision context is deterministic. Canonical rule
version is pinned; upgrading incompatible reducer logic requires a migration
or a checkpoint made with a declared new reducer version. Checkpoint-only
state is the bounded reducer accumulator at a selected boundary; it cannot
hide an unlogged transition that occurred before a crash.

## Effect atomicity and crash contract

For the source's `IncidentDecision` and `RuleSignalDecision`, derive a stable
effect ID from `(Home ID, trigger identity, effect kind, stable_key)` and store
the exact backend request payload. The existing stable keys include
`missing-morning:<window_id>` and rule keys based on event ID or monitor/door
anchor. The key must not change on retry or reducer replay. Any conflict
between same ID and differing payload fails closed.

Evaluate against a candidate reducer state. Persist **one** authenticated
transition envelope containing trigger/decision context, reducer delta and
all resulting effect intents. Verify commit before publishing the new RAM
state, sending a durable Node ACK for a newly accepted event, or delivering
any effect. The event evidence and its decision envelope must share one
recoverable commit boundary: either a single atomic record, or a validated
prepare/commit pairing that makes an orphan event deterministically
re-evaluable and forbids acknowledging a half-pair. Current
`HubRuntime::run_state_once` journals the event before applying the reducer,
so this contract is not implemented.

**Effect decision safe point:** verified durable envelope with state delta
and intent. **Effect delivery safe point:** backend's authenticated matching
COMMITTED response, followed by a durable Hub completion receipt. Until then
the intent remains pending. Lost ACK causes resend with the same effect ID;
backend idempotency absorbs it. Never send directly during replay. Backend
notification outbox remains authoritative for provider retries and human
resolution. The existing slot receipt covers Node events only; effect-intent
receipts need their own binding or a shared transaction status. An effect
outbox must have a bounded capacity and fail closed before producing a
decision it cannot durably retain.

Crash cases:

| Cut | Recovery |
| --- | --- |
| Before/during transition persistence | Reject/treat as absent unless a complete authenticated record validates; reprocess a retried input once. No external delivery. |
| After persistence, before/after RAM reducer apply | Replay the committed envelope exactly once by ordinal; RAM was never authoritative. |
| During effect-intent creation | Intent is part of the same envelope, so incomplete envelope is absent; complete envelope contains both state and intent. |
| After intent, before backend delivery | Retry pending intent with unchanged ID and payload. |
| After backend commit, before Hub receipt | Retry; backend returns the same committed result, then persist completion. |
| During config/registry save or trusted-time transition | Restore last fully bound config/transition pair. If registry snapshot and logical record disagree, fail closed; never apply new config to old reducer state silently. |
| Between Nodes | Last valid ordinal is the boundary; each Node's later retry retains its EventKey and gets one subsequent ordinal. |

This proves no *locally lost persisted decision* and no duplicate backend
business effect, contingent on atomic record validation, durable backend
idempotency and stable payloads. It does not prove exactly-once external
provider delivery; that is a backend/provider contract.

## Configuration and time policy

Use immutable bounded configuration snapshots with a monotonic version and
content hash, plus globally ordered `CONFIG_APPLIED` records naming the
snapshot. Every event/decision records the applied version/hash. A saved
snapshot is not considered applied until its ordered transition commits.
Retain every config version needed by a checkpoint tail; reject stale or
incompatible versions. Registry membership and required-node mapping must be
bound to the same order despite currently separate registry persistence.

Clock trust after reboot is untrusted. Current `TrustedClock` computes from a
same-boot monotonic anchor and expires after 72 hours; that anchor must not
survive reboot as an active clock. Durable epoch observations remain evidence
with their uncertainty. Before trusted time, do not infer absence or process
calendar deadlines. When trusted time arrives or is corrected, serialize a
logical clock-context change before evaluating due transitions. Record each
resulting positive decision with evaluation epoch and configuration version.
Backward corrections must never erase an already committed effect; duplicate
decision IDs suppress re-emission. Timezone/DST changes are ordered config
changes and cannot reinterpret previous event context retroactively.

Current code does not specify whether a routine deadline missed while the
Hub was offline should create a late incident, be suppressed, or be reported
as uncertain; nor whether a large forward correction should trigger all
intervening windows. Those choices affect state and caregiver effects and
cannot be inferred from `RulesCore::evaluate_deadline`. The meaning of a
required Node lease across reboot and the historical coverage interval is
also undefined. These are blocking product-policy questions.

## Checkpoint equation and cost

Once each transition is committed in the unified order, a checkpoint covering
ordinal `P` contains the canonical reducer accumulator, config/registry
bindings and pending effect statuses. Replaying every authenticated logical
record with ordinal `>P`, without external delivery during replay, yields the
same logical state. Backend-completion receipts are joined by stable effect or
event identity after replay. The existing Node journal remains the durable
event payload store, but its records participate in the unified **logical**
replay stream. Legacy event slots without global ordinals can only be mapped
in their physical order; missing historical non-event inputs prevent exact
full-state migration, as the checkpoint audit explains.

Write count model: one durable transition per new accepted sensor event;
zero for duplicate packets/retries; one per actual config/required-set/window/
monitor/fault/clock-context change; one positive timer/decision envelope;
one completion receipt per backend-accepted event or effect. No write for
polling, an unchanged timer tick or transport retry. Event decision and intent
must share a commit, not add an independent counter write. Existing target
accepts at most 128 Node journal events in a 131,072-byte NVS partition.
There is no defensible absolute writes/day or byte budget yet: sensor rate,
schedule/window rate, bounded config lengths, effect fanout, intent capacity,
and available NVS overhead are unspecified. At 1000 logical transitions the
new stream needs at least 1000 ordered records or a prior checkpoint and a
bounded tail; no reclamation policy is part of this design.

## Host test plan

Use a fault-injecting persistent store and a reference single-thread
transition interpreter. Exercise event→timer and timer→event ordering, config
change between events and reboot after config, multi-Node interleaving,
decision crash before commit and after intent, duplicate EventKeys/effect IDs,
backend ACK loss, and receipt failure. Boot without trusted time, acquire it
later, correct forward/backward, change timezone across a window, and compare
replay with uninterrupted execution. Inject a crash at each persistence and
delivery cut above, including registry/config pair mismatch. Compare
checkpoint plus tail with full logical-stream replay for 512–1000 transitions
and assert exact reducer state, pending effects and backend request IDs. No
tests were run for this design task.

## Decisions required before implementation

1. Product policy for late/missed routine windows, large clock corrections,
   DST/timezone changes, and uncertainty after reboot; define whether
   historical coverage gaps prohibit absence claims.
2. Bound configuration snapshots, rule evidence and effect fanout; choose
   outbox capacity and fail-closed behavior at capacity.
3. Specify an atomic on-disk event-plus-decision envelope (or paired commit),
   the global ordinal format, config/registry cross-store commit, and the
   authenticated selector/record guarantees of the actual NVS layout.
4. Define legacy migration when prior config, local-minute and timer decisions
   are unavailable. An exact reconstruction claim is currently impossible.
5. Decide whether any Hub-generated escalation/cancellation is planned;
   current escalation/resolution is backend-owned and should stay there
   unless product requirements change.

Therefore `DESIGN_READY_FOR_IMPLEMENTATION: NO`. Firmware implementation of
this mechanism would otherwise encode unresolved product behavior.

## Policy and storage-contract closure audit

This section refines the choices above using
`docs/features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md`,
`docs/features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md`, source and the current
host behavior. A recommendation is not a shipped behavior.

### Effect ownership

**Safe engineering default:** Hub owns authenticated sensor interpretation,
local rule decisions and a durable, stable incident/alert intent. Backend owns
the committed caregiver timeline/incident, notification jobs and provider
outbox, escalation schedule, human acknowledgement, cancellation of unsent
jobs, and resolution/audit history. `NotificationService` already creates
primary/backup jobs and cancels unsent work on human acknowledgement;
`durable_commit.py` commits event, alert and notification outbox in a backend
transaction. The Hub must not mirror the backend escalation timer or treat an
I Am OK event as caregiver acknowledgement. A door-close rule signal may
request resolution of its matching concern, but backend incident lifecycle
and caregiver-visible state remain authoritative. Whether any future Hub-side
escalation is desired is a product decision; none is required by current code.

### Time and coverage decisions

| Situation | Recommended behavior | Status |
| --- | --- | --- |
| Boot without trusted clock | Restore durable evidence and pending intents; mark time and current coverage unknown; make no absence inference. Acquire a fresh same-boot clock anchor. | SAFE_ENGINEERING_DEFAULT, consistent with rule trust gates. |
| Time arrives after boot; window started during outage | Resume only the current eligible window using stable `(routine_id, schedule_version, window_instance_id)` identity and verified evidence/coverage. Do not replay historical timer ticks. | SAFE_ENGINEERING_DEFAULT for dedupe; exact window-instance construction is PRODUCT_DECISION_REQUIRED. |
| Whole window missed in outage | Do not assert “no activity.” Record a separate availability/verification gap if the product wants a caregiver-visible concern; never backfill a missing-activity alert from unknown coverage. | Suppression is SAFE_ENGINEERING_DEFAULT; caregiver presentation/severity is PRODUCT_DECISION_REQUIRED. |
| Inactivity threshold passed during reboot | After trust returns, alert only if the entire required interval has provable coverage and no activity; otherwise classify unknown coverage. No burst for every elapsed threshold. | SAFE_ENGINEERING_DEFAULT; historical coverage proof is not implemented. |
| Large forward correction | Commit clock-context change; evaluate the currently relevant window once, with stable instance identity. Do not emit a backlog of historical alerts. Flag skipped intervals as unknown coverage if surfaced. | SAFE_ENGINEERING_DEFAULT for no burst; definition of “current” and gap presentation is PRODUCT_DECISION_REQUIRED. |
| Backward correction | Never undo committed intent or regenerate its stable identity. Re-evaluate only future eligible transitions after time progresses again. | SAFE_ENGINEERING_DEFAULT. |
| Timezone or DST change | Order new timezone as config transition; prior decisions keep original version. Use a stable local-date/window instance disambiguated by schedule version and offset/fold, so repeated local clock hour cannot duplicate an alert. | SAFE_ENGINEERING_DEFAULT for versioning; skipped/repeated window policy is PRODUCT_DECISION_REQUIRED. |

`KNOWN_ACTIVITY` requires authenticated evidence. `KNOWN_INACTIVITY`
requires trusted time, a declared observation interval and complete required
sensor coverage throughout that interval. An outage or unprovable coverage
interval is `UNKNOWN_COVERAGE`, never known inactivity. Current
`CoverageTracker::current` is point-in-time, so it cannot prove historical
coverage; interval evidence or a conservative unknown result is required.
Backend/UI should distinguish “no activity detected” from “activity could
not be verified.” The exact caregiver wording, severity and notification
policy for the latter need product approval.

### Bound classification

The exact source-enforced and proposed prototype bounds, including their
rationale and serialized consequences, are listed in the numeric sizing
section below. Current code enforces ten enrolled Nodes, seven backend room
labels at that API, 128 journal slots, an 8,192-byte registry blob maximum,
and a 256-byte codec plaintext ceiling (the actual largest field-bounded
event is 228 bytes). It does not enforce finite HomeConfig/evidence/effect
limits. Proposed limits must be wired into validators before implementation.

### Selected atomic persistence model

Select **A: one authenticated, immutable transition envelope** for each new
logical input and its reducer decision/effect intents. The envelope contains
the full causal Node event (or a cryptographically bound immutable event
reference already durable), global ordinal, config/time context, reducer
decision delta and bounded effect payloads. Prefer embedding the event: a
separate event slot plus decision slot cannot be made atomic by ordinary
independent NVS commits. The existing journal's one-slot write, commit,
readback and authentication pattern is a useful primitive, but its current
format has no decision envelope, global ordinal or effect outbox. Do not
claim the format change is already supported or that NVS power-cut behavior
is physically qualified.

Sequence: serialize from a candidate state under the sole owner; check
capacity and expected next ordinal; write the *one* immutable slot; commit;
read back and authenticate its complete contents, slot binding, ordinal and
causal event; only then publish candidate RAM state, send durable Node ACK
and expose intents to delivery. On boot, scan the contiguous authenticated
prefix, reject holes/ordinal conflicts, rebuild state and pending intents;
an interrupted invalid tail is either safely absent by a proven slot-store
contract or a storage fault requiring fail-closed recovery. A failed write
may leave an ambiguous occupied slot; it must not be retried under a new
ordinal until the slot is inspected. No separate ordinal counter write.
Use a 64-bit unsigned ordinal with a fixed nonzero initial value; refuse new
transitions at maximum, never wrap. Concurrent Nodes serialize at the Hub
owner; duplicates reuse their original EventKey/ordinal.

Configuration/registry cross-store atomicity is **not resolved** by a single
transition envelope if the registry remains an independently committed NVS
snapshot. A safe option is immutable prepare snapshot → verified transition
referencing its exact hash/generation → publish it as active; orphan prepared
snapshots are ignored. The current registry repository does not expose this
transaction protocol, and security authorization may already change before
the logical record is committed. This needs an exact API and crash proof.
Backend completion remains a separate write-once receipt after backend
`COMMITTED`; lost receipt leads to same-ID retry. Provider exactly-once is
outside the Hub's guarantee.

### Migration, failures and budget

Legacy journal replay recovers only the state its source actually records.
Start a new transition generation with explicit unknown time/coverage and a
product-approved reset of unrecoverable rule latches; preserve legacy event
IDs, pending backend events and receipts. Do not create a checkpoint claiming
old rich rule state was reconstructed. A first new-generation checkpoint is
eligible only after all active state has a declared canonical reset or
durable origin. Old slots become reclaimable only when a validated checkpoint
and bounded dedupe state cover their effects, all backend-pending events and
receipts are safely transferred/settled, no active rule depends on their
evidence, and rollback to journal-only firmware is barred. Reclamation is
not designed here.

Event/envelope/intent/ordinal failure: no durable ACK and no external
delivery; inspect ambiguous slot and fail closed if it cannot be classified.
Backend unavailable: retain bounded intent and retry; at capacity apply
admission control/fault, never discard. Clock unavailable: suppress absence
decisions. Config crash: restore last matching snapshot/transition pair or
fail closed. Two Nodes: owner serialization fixes the order. These outcomes
depend on the storage validation contract above; current separate journal
and registry stores do not yet provide the full proof.

The target partition table provides 24,576 bytes ordinary `nvs` and 131,072
bytes `gs_journal`; both already carry other state. See the numeric sizing
section below. These are proposed caps and formulas, not source-enforced
limits; target fit remains unqualified.

## Superseded numeric prototype (rejected)

The following prototype documents the rejected 160-record/full-payload
design. Its `STORAGE_FITS: NO` conclusion applies only to that prototype. The
selected storage contract and authoritative budget follow it.

## Numeric prototype bounds and fit calculation

Only values labeled SOURCE_DEFINED are enforced at the cited boundary.

| Bound | Value | Classification and rationale |
| --- | ---: | --- |
| Enrolled Nodes | 10 | SOURCE_DEFINED (`HubSecurityLink::kInstalledCapacity`). |
| Required Nodes | 10 | DERIVED_FROM_EXISTING_LIMIT; must be enrolled. |
| Rooms | 7 | SOURCE_DEFINED backend allowlist. Hub registry accepts arbitrary room labels up to 24 bytes, so this is not end-to-end enforcement. |
| Routines | 5 | PROPOSED_ENGINEERING_BOUND, one of each existing backend routine type. Firmware currently has one active routine. |
| Activity rules | 8 | PROPOSED_ENGINEERING_BOUND matching current eight `RuleSignalKind` values. Future kinds require schema/version update. |
| Evidence ID samples | 16 per active routine | PROPOSED_ENGINEERING_BOUND; 32-byte hashes retained for bounded local explanation. Exact evidence count is a separate 64-bit accumulator. Backend/event history remains authoritative for full evidence. |
| Pending effects | 16 total | PROPOSED_ENGINEERING_BOUND. On full, apply admission control and expose fault; never discard. |
| Effect payload | 256 bytes | PROPOSED_ENGINEERING_BOUND canonical binary body; reject larger payload. |
| Effects per transition | 3 | DERIVED_FROM_EXISTING_LIMIT: current timer evaluator can emit door-left-open, daytime-inactivity and post-door inactivity together. |
| Config snapshot | 2048 bytes | PROPOSED_ENGINEERING_BOUND; estimated serialized HomeConfig with capped identifiers is below 1 KiB, leaving room for schema/auth metadata. |
| Config versions | 3 | PROPOSED_ENGINEERING_BOUND: two checkpoint generations plus staged next config during apply. Select a checkpoint before another config transition. |
| Transition envelope | 1332 bytes | PROPOSED_ENGINEERING_BOUND from explicit binary model below; supports three simultaneous rule effects. |
| Transition tail | 160 records | PROPOSED_ENGINEERING_BOUND: 128 event positions plus 32 non-event positions before compaction/backpressure. |
| Effect receipts for tail | 480 | DERIVED_FROM_PROPOSED_BOUND: at most three effects per transition record; completion receipt storage must be bounded. |
| Backend-pending events | 128 | SOURCE_DEFINED current append-only event journal capacity. |
| MAX_BACKEND_PENDING_EVENTS | 128 | PROPOSED_ENGINEERING_BOUND equal to current source capacity; full means Node admission backpressure. |

These limits are small for one home with ten Nodes. Serialized RAM equivalents
are about 4,672 bytes for 16 pending effects, 512 bytes for 16 routine
evidence hashes, and 113 bytes for ten coverage entries, excluding C++
container/allocator overhead. Raising limits changes the schema and requires
recalculation and migration.

### Transition serialization arithmetic

Actual `encode_event` field limits yield 228 bytes plaintext at maximum:
version/length-prefixed strings for physical ID 64, source ID 24 and location
64 (156 bytes), fixed fields (52 bytes), and optional motion aggregate (20
bytes). AES-GCM adds nonce 12 + tag 16, so the encoded store blob is 256 bytes.
The NVS adapter allows 284, but current event codec cannot produce it. EventKey
fields occupy 106 bytes maximum in this encoding (length-prefixed physical ID
64 and source ID 24, session8 and sequence8) and are already included in the
event payload; do not add them a second time.

Proposed binary transition header: 72 bytes (magic4, version2, type1, flags1,
ordinal8, config version4, config hash32, event length2, delta length2,
effect count1, reserved/source binding15). Reducer delta cap 128 bytes. One
effect is 292 bytes (identity32 + kind/status/length4 + payload256). Timer
evaluation can emit three signals at once; authentication adds nonce/tag28.
Thus worst transition envelope is
`72 + 228 + 128 + 3*292 + 28 = 1332` bytes; the causal event is plaintext
inside the single authenticated envelope, so its standalone nonce/tag is not
counted twice. Representative ordinary event: 80-byte event plaintext +
32-byte delta and no effect = **212 bytes**. With one effect it is 504 bytes.
These transition sizes are proposed, not measured current serialization.

### Checkpoint serialized maximum

| Component | Worst bytes | Model |
| --- | ---: | --- |
| Header, identity, generation, config/reducer refs | 96 | Proposed fixed header |
| Coverage | 113 | required mask/count 3 + 10×(epoch8+battery2+fault1) |
| Routine | 560 | window ID32 + length1 + flags/enums5 + evidence count8 + sample count1 + 16 hashes512 + reserved1 |
| Activity rules | 134 | seven optional epoch anchors63 + two event hashes64 + flags/counters/reserved7 |
| Pending effects | 4672 | 16×(identity32 + metadata/length4 + payload256) |
| Config ref | 36 | version4 + hash32; snapshot stored once separately |
| Authentication | 28 | nonce12 + tag16 |
| **One checkpoint** | **5639** | Sum |

Typical empty effect queue and three evidence hashes: **551 bytes**. Two
maximum checkpoint generations: **11,278 bytes**; selectors/metadata add
128, for **11,406 bytes** raw. This model requires fixed-width schema
serialization; current C++ structs do not implement it.

### Configuration and partition accounting

`NvsRegistryBlobStore` has one live `gs_registry/snapshot` key with maximum
8,192 bytes (not two application-level snapshots). `NvsAssociationBlobStore`
allows one 1,024-byte binding. The Hub also stores small Home ID/wrapping and
development identity material, modeled conservatively as 160 bytes. Proposed
three config versions are 3×2,048 = 6,144 bytes; checkpoint references do
not duplicate snapshots. Config storage total including registry,
association, identity and three config versions is **15,520 bytes** raw.
Three versions cover two valid A/B generations and a staged new snapshot.
Finish and select a checkpoint for each config transition before accepting
another; retain every snapshot still referenced by a selectable generation.

| Partition | Start–exclusive end | Total | Known/proposed raw occupants | Raw margin |
| --- | --- | ---: | --- | ---: |
| `nvs` | `0x9000–0xF000` | 24,576 | Existing current max estimate: registry8,192 + association1,024 + identity160 = 9,376. Proposed config adds 6,144; new typical/worst raw total 15,520. | Nominal margin 9,056 (36.8%). If reserving 20% for NVS internals, only 4,141 remains for unmeasured entry/GC overhead; actual fit UNKNOWN. |
| `gs_journal` | `0x3E0000–0x400000` | 131,072 | Existing conservative max: events36,352 + Node receipts4,096 = 40,448 (actual event codec max gives 36,864 total). New typical 49,422; new worst 243,982 including up to 480 rule-effect receipts. | Typical margin 81,650 (62.3%); worst margin -112,910 (-86.2%). |

Conservative current journal raw use: 128×284-byte adapter max + 128×32-byte
completion receipts = **40,448 bytes**; actual encoder's maximum event blob
is 256 bytes. Proposed typical new total: 160×212 + 4,096 Node receipts +
11,278 checkpoints + 128 selectors = **49,422 bytes**; nominal margin
**81,650 bytes (62.3%)**. Proposed worst new total: 160×1,332 + (128+480)×32
receipts + 11,278 + 128 = **243,982 bytes**, exceeding the partition by
**112,910 bytes (86.2%)**.
Therefore `STORAGE_FITS: NO` for the chosen worst-case bounds. Raw byte totals
exclude NVS entry/page/GC overhead, so target space is less favorable. The
NVS partition's 9,056-byte raw remainder is likewise not an actual free-space
measurement; NVS metadata and temporary copy-on-write/GC needs are not
available from static source. No partition size is changed.

With a 20% nominal reserve policy, the journal reserve is 26,214 bytes. The
typical case retains 55,436 bytes beyond that reserve; the worst case is
139,124 bytes short even before NVS overhead. The ordinary NVS partition has
4,141 bytes above the same 20% reserve in the raw model, but actual NVS
metadata, page rounding, old/new blob overlap during update, and garbage
collection reserve are not statically known. Thus the ordinary NVS fit is
UNKNOWN; overall worst-case storage fit is NO due to `gs_journal`.

### Write-demand scenarios

Illustrative future steady-state software writes/day (not flash endurance):

| Scenario | Events | Non-event transitions | Event + effect receipts | Checkpoint storage writes | Config snapshot writes | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Typical assumption | 100 | 4 | 104 (100 event + 4 effect) | 8 periodic + 0.28 config-triggered | 0.14 (weekly) | **216.42/day** |
| High activity assumption | 500 | 20 | 520 (500 event + 20 effect) | 32 periodic + 2 config-triggered | 1 | **1,075/day** |

Each checkpoint uses two writes (inactive blob then selector); a config change
also writes one immutable snapshot and triggers a checkpoint. Event envelope
includes any effect intent; polling and retries add no write.
These rates assume future compaction/reuse. Current append-only 128-slot
journal cannot sustain these daily rates beyond its lifetime capacity.

## Selected bounded storage contract

This section supersedes the prototype above. It is a proposed on-disk schema,
not implemented firmware. All byte caps are *serialized blob* caps; encoders
must reject overflow before writing. A change to any cap requires a versioned
schema and a new peak-space calculation.

### Duplicate-field audit

| Field | Required owner | Old duplication removed |
| --- | --- | --- |
| EventKey, causal event fields and local observation time | MUST_EXIST_IN_LOG until a selected checkpoint; pending backend events then have one immutable payload chunk | Existing event blob plus full transition event |
| Global ordinal, reducer decision, config/registry delta, effect ID and effect payload | MUST_EXIST_IN_LOG at commit | Separate decision, registry write and pending-effect queue |
| Current reducer and security registry state, rule anchors, coverage, exact EventKey digest chunk references, selected retirement snapshot | MUST_EXIST_IN_CHECKPOINT | Replaying all historical events; sequence-only dedupe frontier |
| Pending event/effect IDs, chunk IDs and completion bits | REFERENCE_ONLY in checkpoint | Full pending payloads in checkpoint |
| Config version/hash | REFERENCE_ONLY in transition and checkpoint | Config bytes in every transition |
| Config bytes | One immutable ordinary-NVS version; referenced by ordered APPLY | Repeated config in checkpoint |
| Backend receipt | DERIVABLE from authenticated active-generation completion bitmap | Per-slot lifetime receipt and separate effect receipt |
| Routine evidence samples | DUPLICATED_UNNECESSARILY; backend/event history owns samples | Sixteen 32-byte hashes in checkpoint; retain count/flags |

The maximum transition is still
`72 header + 228 event + 128 decision/delta + 3*(32 identity + 4 metadata
+ 256 canonical payload) + 28 AEAD = 1,332 bytes`. A typical ordinary
event remains 212 bytes. The 106-byte EventKey is *inside* the 228-byte
event, not an additional field. Config/registry transitions use the same
cap; a delta that cannot fit must be split into an ordered sequence that
does not publish a partial security change, or rejected before admission.

### Model comparison and selection

| Model | Maximum bytes and writes per logical transition | Recovery, receipts, migration and occupancy |
| --- | --- | --- |
| A: unified log alone | 1,332; one write | One commit is simple, but 128 backend-pending events pin 128 records (170,496 bytes) before checkpoints/legacy state. Incompatible with bounded reuse. |
| B: old event plus referencing decision | 284 event + up to 1,072 decision + 64 commit marker = 1,420; three writes | Marker selects the pair, but partial pairs and slot-generation binding complicate restore. Old c-slot receipts can serve legacy only. More migration space than D. |
| C: write-ahead full envelope plus old event | 1,332 + 284 = 1,616; two writes | Envelope is authority and event is a cache. Removing the second write reduces this to A; retaining it duplicates the event. |
| D: unified log with checkpoint handoff | 1,332 at commit; one write, then amortized chunk/checkpoint writes | Single authoritative commit; pending payload migrates from log to immutable chunks before its log slot is reusable. Generation-bound bitmap replaces lifetime slot receipts. Fits the peak below. |

Select **D**. A log record is the only atomic authority for an accepted event,
its reducer decision, security/config delta and every effect intent. The
checkpoint stores current state and references, not historical payloads.
The backend owns external effect idempotency by stable request/effect ID.

### Exact commit and restore order

1. **BUILD:** under one serialized state-machine lock, derive the complete
   deterministic transition from the last committed state. Allocate ordinal
   `last+1`; bind EventKey, storage epoch, reducer/config schema and all
   effect identities. A repeat EventKey resolves to the prior ordinal and
   returns its prior result.
2. **WRITE:** write the complete authenticated blob to a free
   generation-tagged log slot. There is no separate accepted-event write.
   For CONFIG_APPLY, first write/readback an immutable config version in
   ordinary NVS. For registry changes, include the authoritative delta in
   the log; `gs_registry/snapshot` is only a rebuildable cache.
3. **VERIFY:** read back exact bytes, epoch, ordinal, EventKey, digest,
   authentication and contiguous predecessor. On an ambiguous NVS result,
   perform this same readback. Exact valid record means committed; missing
   or corrupt record means no ACK and no new ordinal. A corrupt committed
   prefix blocks admission rather than being skipped.
4. **COMMIT/PUBLISH:** after verification, apply the record once to RAM,
   publish its pending effects and refresh derived registry cache if useful.
   A cache-write failure never rolls back the committed transition.
5. **ACK NODE:** only after durable verification and RAM publication. A
   crash after the record and before publication/ACK replays it once; a
   crash just after ACK finds the same committed record. A retry uses the
   same EventKey and effect IDs, never a second ordinal.
6. **RECOVERY:** choose the highest valid selected checkpoint generation,
   verify its config version/hash and all referenced chunks, then replay
   the contiguous authenticated log prefix. Apply registry deltas before
   enabling secure peer admission. Ignore orphan config snapshots and
   cache versions that disagree with the recovered ordinal. Restore the
   latest valid completion bitmap; retry uncertain external deliveries with
   their original stable IDs. Missing selected data is a fail-closed fault.

A valid log blob is the commit point. No state can contain an accepted event
without its decision or an effect intent without its cause. An NVS failure
may have persisted the blob; readback, rather than the return code alone,
classifies it. A partial/corrupt blob cannot be a commit. Firmware rollback
to a reader unaware of the new epoch is prohibited.

### Tail, payload ownership and completion

Checkpoint every **two** committed logical transitions, counting events and
non-event transitions. A checkpoint may be triggered earlier for occupancy
or a config change. No elapsed time or graceful shutdown is required.
Keep the two valid A/B checkpoint generations and every log record required
to replay from either; thus the active replay tail is at most **four** records
(two since each boundary). Before accepting a fifth record, finish a
checkpoint or backpressure Node admission. Timer decisions that cannot be
persisted enter an explicit fault state; they are never silently dropped.

The product cap remains **16 pending rule/incident effects**, with up to
three generated by one timer evaluation. The source-defined **128 pending
Node events** is retained in normal operation. While all legacy slots
remain, allow only **64 additional new-epoch pending Node events**; this is
a migration admission cap, not a reduced normal product bound. Full queues
backpressure Node acknowledgements and surface a storage fault for local
timers. The log owns each pending payload until checkpoint handoff. Copy
up to four pending event payloads into one immutable 1,004-byte chunk, and
up to four effect payloads into one immutable 1,260-byte chunk; read back
and authenticate all chunks before writing/selecting the new checkpoint.
The checkpoint holds chunk IDs and item indexes. Old log slots remain until
*both* selectable checkpoint generations no longer need them. Overlap
during handoff is the necessary crash-safe temporary duplicate.

Completion uses two alternating authenticated 384-byte bitmap/state blobs.
Each bit is bound to storage epoch, ordinal or chunk ID, item index and
stable backend request ID, so slot reuse cannot inherit a stale receipt.
On backend COMMITTED, write/readback the next generation of bitmap before
reporting durable completion. A failed/ambiguous write is inspected like a
log write. A prior valid bitmap means retry using the same backend ID; the
backend's durable idempotency prevents a duplicate business effect.
Bitmap statuses only advance. Completion after checkpoint updates the
bitmap, not the checkpoint or payload. Legacy c000–c127 receipts remain
valid only for legacy slots until migration retirement.

Checkpoint selection is: copy/verify pending chunks; write/readback inactive
checkpoint; write/readback redundant generation-tagged selector; retire
unreferenced records/chunks only after both valid generations release them.
Before selector commit, restore the older checkpoint and its retained tail.
After selector commit, restore the new checkpoint and its verified chunks.
Invalid selector copies are resolved by authenticated generation and complete
references; if neither candidate is complete, fail closed.

### Checkpoint serialized cap and placement

| Checkpoint component | Maximum bytes |
| --- | ---: |
| Fixed header, identity, auth, config refs, rule state, common Hub key | 494 |
| Ten active Nodes: coverage 11 + registry record 252 each | 2,630 |
| Ten tombstones: length + ID 64 each | 650 |
| One active routine: window/flags/evidence count, no sample hashes | 47 |
| Sixteen pending-effect references, 10 each | 160 |
| Thirty-two event-chunk references, 8 each, plus 16-byte pending map | 272 |
| Exact EventKey evidence references (32 × 40 B) and report snapshot reference (41 B), replacing the old 1,060-byte frontier set | 1,321 |
| **One checkpoint maximum** | **4,514** |
| **Two checkpoint generations** | **9,028** |

The 252-byte registry entry excludes its repeated 65-byte Hub public key:
the current registry encoder can reach 3,952 plaintext bytes for ten Nodes
and ten tombstones, but the common key is stored once in the checkpoint.
The fixed 494 includes the config version/hash. The routine count and flags
are sufficient for reducer continuation; evidence samples stay with the
event/backend history. Each byte cap is a schema requirement, to be
enforced by serialization before firmware implementation.

| Partition | Objects and maximum raw bytes |
| --- | --- |
| Ordinary `nvs` | Derived `gs_registry` cache 8,192; association 1,024; identity/wrapping material 160; three immutable config versions 6,144. **15,520 total**, 9,056 nominal free (36.8%). |
| `gs_journal` | Four transition slots; A/B checkpoints; pending event/effect chunks; A/B completion bitmaps; selectors, epoch and migration metadata. Legacy 128 event/receipt slots retained during migration. |

At most three config versions coexist: versions referenced by the two
selectable checkpoints plus one staged next version. Select a checkpoint
after each CONFIG_APPLY before staging another version. Orphans may be
removed only after neither checkpoint/tail references them. A config
snapshot is verified before APPLY, and APPLY is the only activation point.

### Worst-case migration and steady-state budget

| `gs_journal` component | Migration maximum bytes | Normal maximum bytes |
| --- | ---: | ---: |
| Four 1,332-byte transition records | 5,328 | 5,328 |
| Checkpoint A | 4,514 | 4,514 |
| Checkpoint B | 4,514 | 4,514 |
| Pending event chunks (16 migration / 32 normal, four events each) | 16,064 | 32,128 |
| Four pending-effect chunks | 5,040 | 5,040 |
| Two completion bitmaps | 768 | 768 |
| Selectors, epoch and migration metadata | 512 | 512 |
| One extra checkpoint, bitmap, metadata and event scratch chunk in flight | 6,030 | 6,030 |
| Existing event/receipt slots untouched | 40,448 | 0 |
| Three report snapshot banks (normal operation) | 0 | 18,288 |
| **Total** | **83,218** | **77,122** |

Migration nominal free space is **47,854 bytes (36.51%)**. Ordinary NVS
remains at 15,520 raw bytes with no retirement keys added. Conservatively
allowing an NVS blob index, chunk metadata and 32-byte data entries, the
32-page journal offers about 4,032 usable entries. The corrected migration
peak is **3,221 used / 811 free (20.11%)**. This entry estimate does not prove
allocability under every page-fragmentation/GC state; target NVS allocation
and power-cut validation remain required before firmware rollout. See
[Espressif NVS storage format and error semantics](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/storage/nvs_flash.html).

Migration restores/authenticates all legacy events and c-receipts, builds
the new epoch's initial checkpoint from reconstructable state, verifies it,
then durably selects NEW_STORAGE_EPOCH before admitting new transitions.
Unknown historical time/rule state stays explicitly unknown. Old data is
never overwritten in this step. Future retirement requires backend-pending
legacy work to be settled or transferred, bounded dedupe and rule
dependencies to be covered, and rollback to legacy firmware barred.
Reclamation is outside this task.

### Hub storage epoch and production provider contract

**Authority and scope.** `storage_epoch` and the Hub retirement epoch are the
same nonzero `u32`: the generation of one Hub durable history **within one
authenticated Home/Hub installation**. The authenticated installation binding
plus this number is the retirement namespace. It is neither wall-clock time,
firmware version, boot count, enrollment generation nor checkpoint generation.
Use a monotonic counter within an installation: the first durable history is
epoch 1; a controlled replacement of that history uses the previous epoch
+ 1. Refuse replacement at `UINT32_MAX`. A restart, firmware update,
checkpoint, report, Node rejoin, or ordinary migration batch does not change
it. Migration from the legacy journal creates epoch 1 once, then preserves it.

The authoritative epoch record is the **selected durable checkpoint**, not a
new NVS key. `Codec::encode_checkpoint` already puts magic `GCP1`, schema,
nonzero `storage_epoch` (`4` bytes), checkpoint generation (`8` bytes) and
state in an AES-GCM protected blob; `Codec::encode_selector` protects the
generation and A/B bank choice. Both checkpoint banks must contain valid,
matching epoch values before that epoch can be advertised or accept reports.
The selected checkpoint and its referenced report bank/evidence chunks must
verify under the same epoch. A single corrupt checkpoint can be recovered
from the other valid bank **only if no valid bank or selector indicates a
different epoch**; ambiguous mixed epochs, invalid selectors that could
choose another epoch, or two corrupt banks stop admission. The boot service
must inspect both banks and both selectors *before* constructing
`DurableStore(epoch)`. It must not use `DurableStore::recover` alone as an
epoch discovery mechanism: that method receives an epoch and can ignore a
checkpoint from another epoch. After choosing the epoch, call `recover` and
require its selected checkpoint, chunks, tail and report references to verify.
An empty `recover` result is not a genesis checkpoint.

**Creation and invalidation.** Create a genesis checkpoint only after the
provider has initialized, a complete partition inventory proves it empty,
and the security bootstrap proves this is a freshly created installation.
Reading only the known `cp`/`sel` keys is insufficient because orphan
dynamic chunk keys may survive. If the Home identity or wrapping material
already exists but `gs_journal` is empty, fail closed; do not create epoch 1
under the old trust domain. For legacy migration, first authenticate legacy
events and receipts and stage the reconstructable initial state; build a
complete new-epoch checkpoint without erasing the legacy source. Write/read
back the first checkpoint, then the second matching checkpoint,
then select and verify the new generation. No epoch offer, report acceptance,
new transition admission or legacy-slot erasure occurs before this barrier.
The second valid checkpoint plus verified selector is the epoch commit point.
If power fails before it, resume staging or recover the intact legacy state;
if a persisted-but-failed write completed the barrier, readback resolves it
as committed. Once committed, bar rollback to legacy firmware and preserve
the epoch through all staged batches. Legacy physical slots may be retired
only after their authenticated EventKeys, payloads, receipts and pending work
have been transferred in the already specified two-checkpoint order. Enable
retirement reports only after that transfer and the three report banks can be
allocated; moving bytes alone never proves an EventKey retired.

Controlled invalidation **within the same installation** requires a complete
new checkpoint from the retained evidence, an incremented epoch, both A/B
banks verified under it, and a selected new generation before old history is
discarded. If that complete transfer cannot be proved, refuse invalidation
and keep report acceptance disabled. A bare erase of `gs_journal` while
ordinary NVS still holds the Home identity, wrapping key or enrolled Nodes is
corruption, not a fresh store: fail closed and require recovery or a full
factory reset. Full factory reset erases the durable journal **and** the Home
identity, wrapping key and enrolled bindings as one operator-controlled
operation. Quiesce radio admission before either erase and keep it disabled
through reboot; a power failure between erases leaves mismatched identity
or journal inventory and must resume reset or fail closed. No old Node can
authenticate afterward. A new installation starts
at epoch 1 in its new binding namespace; numeric equality with an old,
unrelated installation is harmless because old reports and ACKs fail the
binding authentication. Reusing old installation keys after full erase is
forbidden. This scoped rule is necessary because no finite on-device epoch
counter can prove a globally new value after every copy of its state is
erased. Recommissioned Nodes must send a complete authenticated report under
the new binding before any retirement proof exists, even if the new
installation's numeric epoch is also 1.

**Node transition.** After receiving a different nonzero epoch through an
authenticated Hub session, the Node preserves all pending EventKeys and
their origin sessions. It updates the epoch and increments its existing
persisted report generation; it does not reset that generation. The epoch,
generation and complete pending set must be committed together in Node
recovery v3 before the first new-epoch report. The Hub accepts a new-epoch
report only under its recovered epoch and authenticated enrollment binding;
an old-epoch report is rejected, never translated into retirement evidence.
The Node ignores an old-epoch report ACK, and accepts only an ACK matching
the current epoch, generation and report HMAC under the current authenticated
relationship. Existing old-origin pending keys remain in the first report
under the new epoch. If the Hub lacks transferable evidence for their old
history, it retains exact dedupe records or backpressures; it does not infer
that missing historical keys were retired.

**Provider composition and startup.** The planned target class
`NvsDurableBlobStore` implements the existing `durable::BlobStore` methods
`read`, `write_immutable` and `replace` over the existing `gs_journal` NVS
partition, reusing the existing `events` namespace with disjoint keys from
legacy `e000`/`c000` slots.
The existing `BlobStore` read/write/replace interface is sufficient for all
current codecs and repositories: a failed or ambiguous write is resolved by
exact readback, while a read error is distinct from a missing key. Bootstrap
additionally needs a read-only `StoreInventory` interface with one bounded
`scan(InventorySummary&)` operation. It enumerates at most **384** key names,
NVS types and namespaces across the whole `gs_journal` partition; `events`
is the only owned application namespace. It returns
`Empty`, `KnownLegacyOnly`, `DurablePresent`, `UnknownOrCorrupt`, or `IoFault`.
Known legacy names are bounded `e000`–`e127` and `c000`–`c127`; known durable
names are the fixed checkpoint, selector, transition, bitmap and report banks
plus canonical base-36 `ef`/`ev` chunk IDs. The summary contains only
bounded counts and presence masks, not a generic key list or mutable handle.
The 384-name limit covers the 256 legacy event/receipt names, 32 pending
event chunks, 32 exact-evidence chunks, four effect chunks, three report
banks, four transition slots, two checkpoints, two selectors, two bitmaps
and one scratch key, with headroom; exceeding it is a storage fault.
Unknown namespaces/names/types, duplicate physical mappings, invalid syntax,
too many keys, incomplete NVS iteration or unreadable entries fail closed. `Empty`
requires a completed scan with no application keys and no prior `events`
namespace marker. `KnownLegacyOnly` still requires
authenticated legacy restore; `DurablePresent` requires checkpoint/selector
and reference validation and cannot authorize fresh epoch creation. Validly
named but unreferenced durable chunks are not empty; a partially staged
genesis may resume only when its authenticated checkpoint and installation
state prove that stage. The scan never erases, rewrites or accepts retirement
evidence. The target security bootstrap
must also expose whether the Home identity and wrapping material were
newly created together; the current `load_or_create_home_id` does not expose
that fact. Neither addition changes `BlobStore` or writes provider metadata.
The provider must never erase/reformat on NVS error and must preserve
the bounded key/value sizes and copy-on-write behavior. NVS keys are limited
to 15 characters: fixed `cp`, `sel`, `tr`, `bm` and `ret` keys fit directly;
logical `ef`/`ev` plus decimal `u64` chunk IDs may not. The provider must
parse their canonical decimal ID and map it injectively to the same two-letter
prefix plus at most 13 base-36 digits (all `u64` values fit). It rejects
unknown, malformed or noncanonical keys; it never hashes or truncates keys.
Chunk-ID construction must check overflow before shifting checkpoint
generation. The provider owns **all**
durable keys for checkpoint A/B, selector A/B, transition slots, pending
effect/event and exact-evidence chunks, completion bitmaps, and the three
retirement snapshot banks. No object is split into ordinary NVS. The
existing `NvsJournalSlotStore` remains the legacy `events` reader during
migration; the ordinary-NVS `NvsRegistryBlobStore` remains registry storage,
not a retirement `BlobStore`.

The source boundaries are `firmware/hub/target/esp32/idf/partitions.csv`
(`gs_journal` at `0x3E0000`, size `0x20000`, ordinary `nvs` at `0x9000`, size
`0x6000`); `NvsJournalSlotStore` initialization and slot/receipt read/write
methods in `firmware/hub/target/esp32/nvs_journal_slot_store.cpp`
(legacy `events` keys); `HubSecurityLink::initialize` and
`attach_event_journal` in `firmware/hub/target/esp32/hub_security_link.cpp`
(Home ID, wrapping-derived journal key and enrolled registry);
`secure_owner_task` and `start_runtime_adapter` in
`firmware/hub/target/esp32/hub_runtime_adapter.cpp` (current initialization
and `HubRuntime(32, 128)` construction); `NvsRegistryBlobStore` in
`firmware/common/security/nvs_association_blob_store.cpp` (ordinary NVS);
and `durable::BlobStore`, `DurableStore`, `Codec` and
`RetirementSnapshotRepository` in `firmware/hub/components/storage/`.

A portable Hub durability owner (composed above `BlobStore`,
`DurableStore` and `RetirementSnapshotRepository`) discovers and validates
the epoch, owns checkpoint/report selection and gates report ACKs on durable
selection. The ESP32 target owns the NVS provider and derives a durable key
from the existing Home wrapping material with a distinct HKDF context; the
owner receives the key and `BlobStore&`, not NVS handles. `HubRuntime` gets
the recovered owner through a constructor/injection boundary; it does not
call ESP-IDF NVS APIs. This boundary is specified here, not implemented.
Target boot order is: initialize ordinary NVS and identity/security keys,
retaining the fresh/existing installation result; initialize `gs_journal`
without formatting; construct provider and scan its inventory; inspect both
checkpoint banks/selectors and legacy state; finish or resume migration;
recover the chosen durable epoch, checkpoint, tail, evidence and report
references; construct the durability owner and Hub runtime; only then
establish authenticated Node sessions, advertise the epoch and accept reports.
If any storage step is unavailable or ambiguous, do not advertise an epoch,
accept reports, send report ACKs or admit events that require durable state.

**Crash cases.** Fresh storage creates two verified epoch-1 checkpoints and
one selected generation before activation. A crash before either write leaves
an uninitialized store; a crash after only one verified bank resumes genesis
without advertising. A partial checkpoint or selector write is rejected by
AEAD/readback; a returned failure whose exact bytes persisted is resolved by
recovery. One corrupted bank is recoverable only under the same-epoch rule
above; two corrupted banks or conflicting valid epochs stop admission. Normal
reboot and firmware update read the same selected epoch. During migration,
legacy state stays intact until the two-bank epoch commit; after commit,
rollback is forbidden and incomplete later batches resume from verified
new-epoch checkpoints. Selectors or checkpoint generation at `UINT64_MAX`
stop further writes rather than wrap. No epoch is advertised while recovery
or migration is incomplete.

**Budget and qualification.** No standalone epoch or provider metadata key
is added: additional epoch metadata = **0 bytes / 0 NVS entries** and
additional provider metadata = **0 bytes / 0 NVS entries**. The two existing
checkpoint fields already include the two four-byte epoch values within
their 4,514-byte per-bank caps; existing selectors and migration metadata
remain inside the 512-byte `gs_journal` allowance. Reusing `events` avoids a
new namespace entry. Migration peak remains
**83,218 / 131,072 bytes**, leaving **47,854 bytes (36.51%)**. The modeled
NVS allocator peak remains **3,221 / 4,032 entries**, leaving **811 entries
(20.11%)**. Those entry figures model the NVS-formatted **`gs_journal`**
partition, not ordinary NVS. Ordinary NVS remains at the separate modeled
15,520 raw bytes with no added keys; its entry count was not established by
this model. Host proof can cover codec validity, same-epoch bank selection,
persist-then-fail recovery, stale report/ACK rejection and migration ordering.
ESP-IDF NVS allocation/GC behavior and power-cut qualification remain target
work; `idf.py` and `IDF_PATH` were unavailable during this contract update.

The deterministic contract cases for the later portable owner are:

| Case | Required result |
| --- | --- |
| Fresh empty installation | Require empty journal inventory and newly created Home identity/keys; create epoch 1 and activate only after both checkpoints and selector verify. |
| Normal reboot or volatile runtime restart | Recover the same selected epoch; make no epoch write. |
| Firmware-only update | Recover the same epoch; schema migration is a separate, explicit operation. |
| Controlled same-installation history replacement | Transfer evidence, increment epoch once, and verify both banks before activation. |
| Old-epoch report or ACK | Reject report; Node ignores ACK. Neither changes retirement evidence. |
| Node epoch transition | Save new epoch, incremented report generation and full old/new-origin pending set atomically before reporting. |
| Persisted write with a returned failure | Read back both banks and selector; recognize the committed result only if exact bytes and references verify. |
| Partial write or one corrupt bank | Reject invalid bytes; use the remaining bank only under the same-epoch rule. |
| Both banks corrupt or ambiguous epochs | Fail closed; do not recreate epoch 1 under existing installation keys. |
| Migration before epoch commit | Resume staging or use untouched legacy state; do not advertise. |
| Migration after epoch commit | Resume verified new-epoch batches; never roll back to legacy. |
| Epoch or checkpoint-generation overflow | Refuse the transition before writing. |

At 100 Node events and four non-event transitions/day, there are **104
logical transitions** and 104 log writes. Assuming 104 backend completions,
52 every-two-transition checkpoints (104 writes), online backend and one
weekly config snapshot (0.14/day), typical persistence demand is
**312.14 writes/day**, or **3.00 writes/logical transition** excluding the
weekly fraction. If a delayed backend forces one chunk handoff per
checkpoint, add at most 52 writes/day in this scenario. At 500 events,
20 non-event transitions, 520 completions, 260 checkpoints (520 writes),
one config snapshot and up to 260 chunk handoffs, the high activity
bound is **1,821 writes/day** (1,561 with no handoff). Retries, polling
and unchanged state write nothing. These are operation counts, not flash
endurance claims.

**Design fit:** yes for the modeled caps and migration peak. The epoch and
provider contract is ready to implement. Production deployment still requires
the ESP32 provider, target NVS page allocation/GC and power-cut validation,
and the later HubRuntime integration. No production firmware or reclamation
is changed here.
