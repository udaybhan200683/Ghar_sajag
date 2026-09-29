# Durable Hub state transitions and effect intent

Status: **design incomplete for implementation**. Base:
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

### Bounds supported by current source

| Quantity | Bound | Basis/classification |
| --- | --- | --- |
| Enrolled Nodes | 10 | SOURCE_DEFINED: `HubSecurityLink::kInstalledCapacity`. |
| Required Nodes | At most 10 if drawn from enrolled Nodes | DERIVED_SAFE_BOUND; enforce registry membership. |
| Instrumented rooms | At most 10 distinct currently assigned Node rooms, but arbitrary configured room labels/other rooms are unbounded | DERIVED_SAFE_BOUND for observed Node rooms; full `MAX_ROOMS` is PRODUCT_DECISION_REQUIRED. |
| Active routine | One `RoutineService` and one `HomeConfig::morning` | SOURCE_DEFINED for current implementation; future `MAX_ROUTINES` is PRODUCT_DECISION_REQUIRED. |
| Activity signal kinds | Eight `RuleSignalKind` values | SOURCE_DEFINED kinds, not a bound on all future rules or emitted instances; `MAX_ACTIVITY_RULES` is PRODUCT_DECISION_REQUIRED. |
| Backend-pending Node events | 128 current journal slots | SOURCE_DEFINED current maximum; effect intents can exceed this due to timers. |
| Pending effects; effect payload; config snapshot; transition payload | No enforced finite product bound | PRODUCT_DECISION_REQUIRED. Existing routine evidence IDs and config strings/sets are unbounded. |

The registry wrapped blob has an 8192-byte maximum, but that is **not** a
bound for HomeConfig or effect intents. `journal.cpp` limits encoded event
plaintext to 256 bytes; each sealed event adds nonce/tag and store overhead.
Neither number can be repurposed as a checkpoint or transition cap without
changing and validating product semantics. Pending-effect capacity must be
fixed before admission: when full, refuse an event whose decision might need
another intent (without durable ACK), or stop timer progression and expose a
fault. Never silently drop or reprioritize safety effects. Exact capacity and
operational recovery are PRODUCT_DECISION_REQUIRED.

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
bytes `gs_journal`; both already carry other state. Known maximum event
plaintext is 256 bytes, and current journal holds 128 event slots. Required
budget remains a formula:

`transition_record_max = envelope_header + event(<=256) + context + delta + bounded_intents + authentication`

`total = transition_tail + 2*checkpoint_max + pending_effects + retained_config_versions + receipts + selectors + NVS overhead`

`checkpoint_max`, intent count/payload, config count/payload, tail capacity,
and NVS effective available bytes are unspecified. Therefore
`STORAGE_BUDGET_FITS: UNKNOWN`; an invented numeric maximum would conceal
the unbounded current structs. The design remains **not ready** for durable
transition or checkpoint firmware until product bounds, cross-store commit
and legacy reset policy are resolved.
