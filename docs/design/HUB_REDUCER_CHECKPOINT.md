# Hub reducer checkpoint: design audit

Status: **not ready for firmware implementation**. This document records the
recoverable boundary and the missing contracts found at base commit
`5d640901cee909b8024c899b7334a35e889d59de`. It does not authorize journal
reclamation or change the deployed journal format.

## Source and ownership inventory

Paths below are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

| State | Owner and mutation | Recovery classification |
| --- | --- | --- |
| Accepted events, exact EventKey dedupe, per-slot backend receipts | `HubJournal` in `firmware/hub/components/storage/journal.*`; encrypted slots and receipt blobs in `target/esp32/nvs_journal_slot_store.*` | Separate durable journal/completion authority; validate before reducer restore. Tail events replay after the checkpoint boundary. Future retirement also needs bounded dedupe and receipt ownership. |
| Required Nodes and assignments | `HubRuntime::authorize_node/revoke_node`, `CoverageTracker`; security registry in `HubSecurityLink` and `HubRegistryRepository` | Configuration source is the durable registry, but its current snapshot must be bound to the checkpoint; a changed required set is a reducer transition. Do not derive it from sensor events. |
| Coverage health | `CoverageTracker::observe/forget_node/set_sensor_fault/current` in `components/coverage/coverage.*` | Last event epoch/contact, battery and sensor fault affect coverage. Event-derived observations can replay from a tail only with the correct prior state. Sensor fault and required-set changes need durable source or checkpoint. Recompute current coverage only with a valid clock and restored eligibility. |
| Authenticated Node health, online lease and latest power telemetry | `HubRuntime::observe_authenticated_health/contact`, radio callbacks | Volatile. Monotonic contact time and session/health sequence must restart with authenticated rejoin. Power telemetry is diagnostic RAM state, not a durable event reducer input. |
| Active routine config and state | `RoutineService::start_window/set_mode/set_coverage/apply/deadline`; `shared/src/rules.cpp` | Must preserve active window ID, times, locations/policy version, activity/OK flags, mode, coverage eligibility and incident decision state, or replay durable transitions. `RoutineState::evidence_ids` grows on each qualifying event and has no bound. |
| Activity rule config and reducer | `HubRuntime::configure_activity_rules/start_activity_monitor/activity_timers/apply_committed_event`; `shared/src/rules.cpp` | Config is a durable configuration source; all `ActivityRuleState` anchors, counters, event IDs and alert flags are checkpoint state unless independently reconstructed from a complete ordered transition log. Current event journal lacks local minute, timer evaluations and monitor-start transitions. |
| Incident and emitted rule effects | `RoutineService::deadline`, `RulesCore`, `ProcessResult::rule_signals`; host simulator `pending_signals` | Durable pending effect identity and payload are required before a rule flag can suppress re-emission. Backend dedupe handles repeated delivery of a given identity, not a locally lost decision. Current pending-signal vector is RAM only. |
| Caregiver alerts, notification jobs, provider delivery | `backend/ghar_sajag/durable_commit.py`, database and notification components | Backend authoritative after durable backend commit. Never regenerate provider side effects from Hub state restore. Pending Hub delivery belongs to a separate durable outbox/receipt protocol. |
| Ingest queue, peer/session/radio/FOTA work | `HubRuntime`, `HubSecurityLink`, target adapter | Volatile; Nodes retry unacknowledged inputs and rejoin. Do not serialize session keys, uptime or transient queues. |

The target constructs `HubRuntime(32, 128)`, attaches the NVS journal and calls
`restore_from_journal` before admission (`target/esp32/hub_runtime_adapter.cpp`).
The target calls `run_state_once()` without a local minute and supplies
`hub_received_at=0`; it does not wire `start_window`, activity configuration,
monitor start, timer evaluations or deadline scheduling. Host simulation uses
more of the rule engine. These are distinct observable reducer scopes; a
checkpoint cannot claim equivalence to both by snapshotting only the current
production path. `restore_from_journal` uses `std::nullopt` local minute even
for events originally processed with a local minute.

## Proposed boundary and schema

The journal has one physical append order, slots 0 through 127. EventKey
sequences are per Node and cannot be a global watermark. For the legacy
append-only journal, `P` can be the validated contiguous committed slot count
(checkpoint covers slots `[0,P)`). A reusable future journal needs an
explicit, never ambiguous journal generation plus contiguous global ordinal;
physical slot numbers alone cease to be unique after reuse. Checkpoint `G`
means all **durable reducer transitions** through that boundary are applied
exactly once while the single state owner is quiescent. The proposed invariant
is:

`restore(checkpoint G) + replay(valid journal transitions after P)`
`= replay(the complete ordered transition history)`

The current journal contains only events, so this invariant cannot yet cover
configuration, authorization, window, monitor-start or timer transitions.
The checkpoint also must not skip a committed event whose reducer application
was interrupted; a snapshot is taken only after an atomic owner transition
and its effect intent are durable. The journal must retain every record
needed by either recoverable generation, including pending backend records and
their slot-bound receipts. No prefix reclamation is specified here.

Proposed versioned, canonical record (field sizes and maximum lengths are
deliberately **not** asserted yet):

* Header: magic, schema version, generation, Home/Hub identity binding,
  journal format/generation and covered ordinal `P`, reducer/rule version,
  configuration generation/hash, registry generation/hash, payload length.
* Product state: active routine window/config binding and bounded sufficient
  evidence, routine flags/mode/coverage eligibility, required-Node binding,
  coverage observations and sensor faults, all activity anchors/counters/flags
  and event IDs. Store epoch anchors, never monotonic uptime leases.
* Effect state: bounded pending rule/incident effect identities and canonical
  payloads, plus a compact acknowledged/suppressed state where backend state
  cannot prove completion. Backend completion receipts remain separate and
  bound to journal records; do not duplicate the full journal or alert table.
* Integrity: length and cryptographic authentication under the installation
  key, with generation/identity/boundary/config metadata authenticated.

`RoutineState::evidence_ids` is unbounded, as are several configuration
strings and the location set. The exact sufficient evidence representation,
identifier limits, maximum pending effects and serialization sizes must be
fixed before the schema or storage budget is final. No finite checkpoint byte
estimate follows from today's product structures.

## External effects and time

Separate state reconstruction from effect emission. Tail replay may update
reducer state, but must never directly send alerts or notifications. A new
rule decision must first persist a stable identity and payload in a local
effect intent, then deliver it with the same identity until the backend's
durable acceptance is known. The backend's EventKey/alert uniqueness and
notification outbox prevent duplicate backend business effects for repeated
requests. A rule flag such as `missing_incident_created` or
`door_left_open_alerted` cannot be committed independently of its effect
intent. Existing code mutates these flags before returning a decision and
does not persist the returned signal. Backend receipt alone cannot recover a
decision that never reached the backend.

`TrustedClock` ties epoch estimates to a monotonic anchor within one uptime.
After reboot, clock trust begins unknown until a new trusted source anchors
it. Persist only meaningful epoch event/window/deadline anchors with their
configuration and timezone version; do not carry uptime-based online leases
or a previous boot's trust. On restore, mark Node contact/coverage unknown
until fresh authenticated contact and trusted time establish eligibility.
Defer absence, inactivity, morning/night and scheduled evaluations while
time is untrusted; after trust returns, evaluate once under a defined missed-
deadline policy and persist any resulting effect intent. The missed-deadline
policy, handling of wall-clock correction and local-minute history remain
unspecified in current product wiring.

Configuration changes need a durable version and hash, including timezone,
schedule, mode, location mapping, required Nodes and rule policy. Apply a
change as an ordered reducer transition with a declared mid-window policy;
never load checkpoint state under a different configuration merely because
the latest config exists. The current `HomeConfig` version field is not a
production durable configuration history or an ordered journal transition.
Restore must fail closed on incompatible schema/configuration until a defined
migration exists.

## A/B persistence and crash recovery proposal

Keep the selected generation and all journal records it needs. Serialize an
inactive generation, write/commit it, read back and authenticate it, then
write/commit/read back a durable selector containing generation and digest.
Only after that selection may an older prefix be considered for a separately
designed reclamation protocol. Do not overwrite the sole recoverable copy.

* Partial/corrupt inactive write or selector write failure: use the old
  selected generation and its retained journal tail; fail the attempted
  checkpoint. A selector that is torn must itself have an atomic/redundant
  representation or be treated as invalid.
* Crash before selection: restore old selected generation and replay its tail.
  Crash after selection: restore new generation and replay its tail.
* Corrupt selected generation: fallback to the older authenticated generation
  **only** if every journal record from its boundary is still retained and
  configuration/effect state is compatible; otherwise fail closed.
* Both generations invalid, selector ambiguous, missing required tail, or
  identity/config mismatch: fail closed; do not silently replay a partial
  journal or admit new events.

This is a crash model, not a claim that current NVS APIs provide an atomic
selector or that `gs_journal` has reserved checkpoint capacity. Those storage
contracts need measurement and qualification.

## Migration, rollback and write budget

On first upgrade, validate the complete legacy 0–127 slot prefix and its
receipts, replay it, write/verify generation one, select it, and retain the
whole legacy journal. A reboot before selection repeats legacy replay; after
selection it may restore the checkpoint, with the full journal still present
as a fallback. An invalid/holey legacy journal fails closed. Full 128-slot
journal migration must be possible without first accepting another event.

This migration is exact only for state that legacy replay can actually
reconstruct. The journal lacks past local-minute/config/window/timer inputs,
so current rule state and already produced signals in richer deployments
cannot be recovered exactly. A product-approved reset/reconciliation policy
or an additional durable source for these facts is needed before migration
can be called lossless.

Rollback to journal-only firmware remains possible during initial migration
only while it can still read the complete append-only journal and the product
accepts its limited reducer semantics. It becomes unsafe at the first prefix
deletion/reuse or checkpoint-only state transition. Before that point, require
an upgrade compatibility gate and a policy that prevents installation of old
journal-only images; a normal OTA fallback must also be checkpoint-aware.

Current partition `gs_journal` is 0x20000 = 131,072 bytes, shared with 128
encrypted journal slots and receipt blobs. A two-generation budget is
`2 * bounded_serialized_checkpoint_max + selector/metadata + NVS overhead`.
The maximum and metadata overhead are **undetermined**, because evidence and
config cardinalities are unbounded and pending effect limits are absent.
After bounds are specified, a candidate policy is checkpoint every N
completed events and before an occupancy threshold, with an elapsed-time
trigger for quiet periods. Explicit clean shutdown cannot be the only
trigger. Non-event transitions that can suppress an effect need their own
durability before effect delivery; batching event checkpoints cannot replace
that guarantee. Do not checkpoint every sensor event.

## Deterministic host test plan

Use a persistent fault-injecting slot/selector store and a reference ordered
transition trace. Compare canonical reducer state after full-trace replay
with checkpoint plus tail across multiple interleaved Nodes and 512–1000
events. Include immediate restart, interrupted inactive write, crash before
and after select, corrupt newest/oldest generation, selector corruption,
missing tail, repeated generations, and identity/config mismatch. Exercise
config changes on either side of the boundary and timers/windows over reboot
with trusted and untrusted time. Assert that pending and completed backend
events keep the same identities and that no alert/provider effect is emitted
twice. Migrate partial and full 128-record legacy journals, including hole
and corruption cases. Compare storage bytes and write counts to the chosen
bounds. This is a test **plan**; no tests were run for this design audit.

## Blocking decisions before implementation

1. Define the product reducer scope and an ordered durable representation for
   every config, registry, mode, window, monitor and timer transition that can
   affect replay. Define local-minute/timezone history or an explicit
   reconciliation policy for legacy states that cannot be reconstructed.
2. Define an atomic persistent effect-intent/outbox protocol tied to reducer
   flags and backend completion, including fixed identity and payload limits.
3. Bound routine evidence and configuration strings/sets, pending effects and
   per-Node state; prove these bounds preserve rule behavior.
4. Specify legacy migration semantics for missing historical inputs and
   already emitted effects. A full journal alone is insufficient.
5. Fix the storage layout and selector durability contract, then calculate a
   measured two-generation byte budget and write/endurance policy within the
   131,072-byte partition or allocate an explicit separate partition.
6. Define trusted-time reacquisition, missed-deadline and wall-clock-change
   behavior before timer state can be restored safely.

Until these decisions are made, `DESIGN_READY_FOR_IMPLEMENTATION: NO`.

## Follow-up policy and storage decision

The [durable transition design](HUB_DURABLE_STATE_TRANSITIONS.md) now records
recommended time/coverage behavior, backend effect ownership, source-backed
bounds and a single-envelope transition model. It does **not** make the
checkpoint ready: historical coverage and legacy rule inputs remain
unreconstructable, several product bounds are undecided, and the registry /
transition cross-store commit protocol needs a crash proof. A checkpoint may
cover only a fully canonical transition generation and must retain legacy
evidence and receipts until the explicit safe condition in that design is met.
