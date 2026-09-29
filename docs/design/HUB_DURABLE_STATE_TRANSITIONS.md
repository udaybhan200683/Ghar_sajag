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
