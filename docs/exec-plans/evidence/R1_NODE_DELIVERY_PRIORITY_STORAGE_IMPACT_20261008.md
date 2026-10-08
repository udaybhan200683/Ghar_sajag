# R1 Node delivery priority and storage impact — 2026-10-08

**Classification:** SUPPORTING INVESTIGATION / HOST TEST_EVIDENCE; no new product
requirement, production implementation, battery qualification or storage guarantee.
**Recommendation:** `RETAIN_CURRENT_DELIVERY` for the Hub storage project. Reuse
existing ACK-driven pending drain, episode coalescing and health suppression after
authenticated contact. Do not introduce a new delay window, batch wire format or
Node protocol dependency into Hub storage. Delivery batching alone offers **zero
demonstrated durable-record savings**. Future battery optimization belongs to the
separate Node/BAT-C8 work, subject to timing/coverage and measured power proof.

## Checkpoint, authority and bounded scope

- Worktree `/home/udaybhan/projects/Ghar_sajag_r1_storage`, branch
  `feature/r1-hub-storage-lifecycle`, start `4732679aabbe354bb6c771a4b8ac81437d8c45c5`.
- Preflight PASS, local/canonical context `2026-10-08.001`; GS-D025–028 active.
  Canonical promotion `3b72892` is already complete. Earlier storage documents'
  pending-promotion statements describe their historical checkpoints.
- Only existing untracked `prompt.txt` at start; SHA-256
  `c45a9db5f1c4e8252993b3df8bfa4639ec2517a16f3070d1ad105c409a285e69`, preserved.
- Read AGENTS, project context, release contract, work state, canonical index,
  Decision Log, storage/sync contract, active storage ExecPlan, prior Node motion
  audit and 72-hour checkpoint, battery guide and BAT-C8 qualification plan.
- GS-D025 is a 72-hour internet-only target, with powered/local-connected Hub/Nodes,
  not an unconditional capacity guarantee. Local-radio outage is a different case.
  GS-D026 preserves eligible ordinary-motion meaning and exact important evidence;
  GS-D027 requires battery/correctness proof before a new Node protocol;
  GS-D028 excludes bed hardware and preserves the 4 MB Hub/ESP32-C3 baseline.
- User's delivery-priority direction is evaluated below; latency numbers and final
  classes are not locked here. Safety, durability, authenticated ownership,
  recovery and routine correctness remain mandatory together under GS-D021–028;
  a battery priority list cannot license weakening any of them.

```text
BUG_CLASSIFICATION=INVESTIGATE_ONLY
REQUIREMENT_SOURCE=docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md; GS-D025–028
DECISION_IDS=GS-D020/021/022/023/025/026/027/028
TASK_SCOPE=bounded Node delivery/priority audit and material Hub storage implications
OUT_OF_SCOPE=production firmware, backend/PWA, partition, BAT-C8 changes, canonical governance, Jira, hardware, full storage simulations, push
```

The host counterexamples identify limits of a *new deferred-delivery proposal*,
not authorization to fix adjacent firmware issues. No master requirements file
or competing Node routine-learning engine is introduced.

## Actual source audit and reusable mechanisms

`P = code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`. References are to the
unchanged production source at start HEAD; numbers are implementation facts.

| Area | Real source and result |
|---|---|
| PIR | `P/firmware/node/target/esp32c3/node_target_config.hpp:15–24`, `components/sensing/sensing.cpp:27–60`: GPIO4, 10s stabilization, awake poll20ms, debounce150ms, min retrigger1s; qualify rises, not every pulse/high sample. Boot-high is not new motion; low has no PIR event. |
| Existing coalescing | `P/firmware/node/components/power/power.hpp:233–240`, `power.cpp:31–92`, `node_runtime_adapter.cpp:1090–1228`: first Motion durably admitted; repeats RAM-only; connected quiet45s/max300s, outage idle1800s; separate immutable MotionSummary on admission. Current values are not newly approved episode semantics. Uncommitted repeats/summary can disappear on reboot; prior audit already records this limit. |
| Event queue | `P/firmware/node/runtime/node_runtime.hpp:50`, `node_runtime.cpp:54–98`, `components/radio/node_radio.cpp:23–41`:32 retained/32 TX; Motion/MotionSummary limited to28 pending, four slots available to non-motion. No four-class scheduler; reserve is not a guaranteed critical-storage budget. At32 even CallFamily is rejected; no safe automatic eviction. |
| Transport | `P/firmware/node/target/esp32c3/node_runtime_adapter.cpp:227–274,1431–1465`: initialize Wi-Fi STA RAM config, channel1,10dBm,WIFI_PS_NONE, ESP-NOW with application AEAD. **No AP association, TCP connection or cloud upload per event.** No `esp_wifi_connect` in this Node target path. One NodeMessage is one event; no multi-event packet/ACK format. |
| Radio wake/restore | `node_runtime_adapter.cpp:306–346,359–430`: stop ESP-NOW/Wi-Fi for explicit light sleep; restore both and Hub peer after timer/GPIO return, even if no event will be transmitted. Holding an event alone does not remove these radio restarts. Security rejoin is authenticated session negotiation, not Wi-Fi AP reassociation. |
| Existing pending drain | `P/firmware/node/components/radio/node_radio.cpp:216–236`: durable/policy ACK retirement opens next radio opportunity immediately; callback/in-flight gates still serialize adapter sends. Several exact records can share an already-active radio period without a new wire batch. MAC result alone does not retire a business event. |
| Existing piggyback | `node_runtime.cpp:143–149` and `shared/include/gs/protocol.hpp:194–210`: optional power telemetry can accompany a single event; inspected target does not call `set_power_telemetry`. Owner NodeHealth already carries diagnostics. `power.cpp:27–28,101–104` and adapter913–941: matching authenticated ACK defers redundant health, pending work suppresses routine health. No explicit policy to hold new ordinary business events for a later session. |
| Priority limits | `node_radio.cpp:46–95,102–147`: connected mode round-robin/global gate, not strict urgent-first. In outage, newly unsent non-motion bypasses the gate; subsequent retries share the gate with non-motion chosen first at an available opportunity. An in-flight data/health/retirement frame and maintenance/rejoin can still block selection. Non-motion includes door/privacy/gap/OK, not just critical. |
| Retry/rejoin | `P/shared/include/gs/protocol.hpp:25–36`:200/600/1800/10000/60000ms plus deterministic0..100ms jitter; last delay repeats, no new PIR needed. Adapter973–1085 switches to outage after3 unacknowledged attempts, handles1s callback timeout and authenticated-contact expiry/rejoin. NodeRadio uses one shared opportunity, not32 simultaneous retry bursts. These are implementation intervals, not alert-latency guarantees. |
| Persistence/reboot | Adapter1165–1172,1217–1223 persists encrypted recovery before send; ACK retirement913–941 persists changed state. `components/storage/node_recovery_persistence.cpp:72,247` saves immutable pending/retry/report metadata; `node_runtime.cpp:171–215` restores old origin identities under a new boot session. Retry deadlines become due in the new monotonic domain; arbitrary new deferral eligibility/deadlines are not persisted today. Corrupt/IO recovery fails closed in `node_security_link.cpp:118`. |
| Sleep | `power.hpp:85–151`, `power.cpp:107–160`, adapter1528–1626: max30s opportunistic sleep,500ms deadline margin/min window; pending TX, ACK wait, retained/recovery work, outage, held-high/unsafe debounce, unknown state, FOTA and owner/callback work inhibit. No deep sleep. Safe low input and armed GPIO/timer required; fail-awake on errors. Active fallback polls20ms. |
| Health/coverage | Normal quiet health120s, authenticated monotonic Hub liveness310s, separate event-time coverage190s (`protocol.hpp:25–33`, `hub_runtime.cpp:36–77`, `coverage/coverage.cpp:48–59`). Delayed activity or heartbeat contact does not prove historical observation completeness or that all observed events were delivered. |
| Hub exact durability | `P/firmware/hub/runtime/hub_runtime.cpp:177–198`, `components/storage/journal.cpp:291–338`: commit/readback before Durable ACK; Duplicate skips reducer; Full/fault rejects. Current target128 lifetime archive is unchanged. No batch transaction or bulk ACK replaces each original event's durable acceptance. |
| Hub burst bounds | `P/firmware/hub/target/esp32/hub_runtime_adapter.cpp:43–46,553,941–966`: callback data queue16, runtime ingest32, journal128; one event processed/ACKed through owner. `components/ingest/ingest.cpp:64–90` bounded admission refuses overload. MAC completion is earlier than durable Hub ACK: one-in-flight MAC per Node does **not** prove only one aggregate uncommitted event across six Nodes. |

```text
CURRENT_WIFI_CONNECTION_TRIGGERS=No AP association; radio initialization at startup, restore after each light-sleep return, recovery/rejoin traffic on ESP-NOW
CURRENT_EVENT_BATCHING=Existing PIR semantic coalescing and ACK-driven separate-frame drain; no multi-event wire batch or deliberate defer-to-session queue
CURRENT_PIGGYBACK_SUPPORT=Authenticated application contact avoids redundant health; optional power field exists; pending drain shares active radio
CURRENT_PRIORITY_SUPPORT=Four non-motion admission slots; outage unsent non-motion bypass; connected strict P0/P1 preemption absent
CURRENT_RETRY_POLICY=Identity-stable global gate/backoff plus authenticated-session recovery; periodic retry until ACK/policy result, no finite success promise
CURRENT_SLEEP_POLICY=BAT-C8A guarded light sleep <=30s; pending/ACK/recovery/outage inhibit; active fallback20ms; physical BAT-C8B pending
CURRENT_NODE_QUEUE_CAPACITY=32 pending and retained; ordinary-motion admission stops at28
```

### Event origins and detection ownership

`P/shared/include/gs/domain.hpp:23–34` has CallFamily/OkPressed/door, **no SOS kind**.
The actual C3 composition (`idf/main/app_main.cpp:16–27`, adapter608,1096–1162)
is PIR-focused: no production resident button or Reed GPIO producer was found.
`QualifiedInput` can model Reed active/inactive transitions when configured; its
presence is not physical installation or qualification.

`P/firmware/hub/components/ui/resident_ui.cpp:18–26` creates Hub-origin
CallFamily/OK (`source_id=hub_id`, location=hub); references found are host tests,
not a proven production Hub button adapter. Simulator/backend injection also
supports these events. [Caregiver guide](../../features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md)
confirms no production SOS dispatch/provider or physical resident control proof;
OK after CallFamily is new chronological evidence and does not resolve that call.
`P/firmware/hub/components/cloud/cloud_sync.cpp:99–121` already prioritizes
CallFamily in backend batches; this is Hub→backend scheduling, not Node radio QoS.

**NODE_DETECTABLE_EXCEPTIONS:** qualified local electrical motion; sensor
stuck-high/noise diagnostics; admission/retention failure; link/ACK/rejoin failure;
a physically implemented explicit button/locally defined critical predicate in
a future supported configuration. Current battery ADC/SOC classification is not
established. A Node cannot identify emergency, identity, wellbeing or unexpected
household motion from PIR alone.

**HUB_DETECTABLE_EXCEPTIONS:** configured quiet-hours door, night visit thresholds,
missing morning evidence, morning cross-room sequence, inactivity and post-door
activity; household learned deviations conceptually. Hub owns modes/config/time,
coverage, incidents and cross-sensor state. Current deterministic RulesCore is
not a qualified learned baseline engine. With no proven Node eligibility/context
contract, first Motion and important exact observations must stay promptly
eligible: the Hub may need them to discover the exception.

## Candidate priorities and three alternatives

Transmission priority and persistent storage priority are separate. Deferring
an immutable exact event need not lose identity, but may lose timely decisions.
These are candidate boundaries, **not a final critical classification/latency SLA**.

| Class | Candidate handling and evidence | Current limitation / prerequisite |
|---|---|---|
| P0 | At a supported producer, durable admission then immediate transmission attempt; never wait for an ordinary batch. Stable retry until durable ACK or explicit approved failure result; expose pending/unavailable without claiming caregiver delivery. | SOS not implemented. CallFamily producer may be Hub-local. Node has no general urgent preemption or unlimited critical capacity; offline link/maintenance cannot promise instantaneous delivery. Define safe reservation/saturation and urgent indication separately. |
| P1 | Prompt exact door/user/safety evidence and motion needed for Hub exception/decision detection. Prioritize above ordinary traffic; preserve original times and chronological reducer meaning. | Numeric latency absent. Node lacks household unexpectedness, trusted wall time and incident context; treat unknown eligibility as prompt, not P2. |
| P2 | Only positively approved ordinary observations may defer to an existing justified opportunity **before** all applicable decision/coverage/capacity deadlines. Preserve door OPEN/CLOSE identity/order if a future door policy permits deferral. | No approved ordinary-door deferral or Node eligibility/deadline protocol. First Motion can be P1 evidence. A recent heartbeat cannot certify no pending activity. Native summary ignored by rules is not blanket permission to discard/delay required history. |
| P3 | Optional nonurgent diagnostics/telemetry piggyback on existing health/event/report opportunities. | Required health/liveness, fault/coverage and retirement progress are not dispensable background data. Promote work needed for a correctness deadline; do not defer gaps that affect a decision. |

| Alternative | Implementation evaluation | Bounded decision |
|---|---|---|
| A Current | Uses semantic coalescing, bounded retry, ACK drain, guarded sleep and quiet health. Existing timing/power/coverage limits remain explicit. | **RETAIN_CURRENT_DELIVERY** for storage; no production change required. |
| B Existing opportunities | Prefer reuse of ACK drain, existing urgent/retry/health/rejoin/maintenance-end radio periods and existing telemetry fields. No new periodic timer. | Already-active drain reuse exists. A new holding policy is unsafe as a standalone change: pending suppresses health/sleep; an otherwise quiet Node may never flush, and records may miss Hub decisions. Not selected. |
| C Deadline-aware | B plus earliest proven decision/coverage/queue deadline; add a communication opportunity only when the current justified opportunities cannot meet it. | Necessary if later positive batching approval cannot prove B suffices. Requires bounded holding expiry, capacity headroom, sleep-safe deferred state, urgent-first selection and Hub knowledge of delivery completeness. No invented flush timer or latencies; defer to separate Node/BAT-C8 task. |

**Smallest safe change now:** none to production delivery. Reuse A's existing
mechanisms; keep Hub storage independent. If later urgent selection is required,
consider a narrowly scoped non-motion/approved-urgent selection before ordinary
queue drain with existing identity/ACK/wire protocol; do not introduce a new
learning engine or batch protocol. It needs admission/control-plane blocking and
ordering tests, explicit priority policy and BAT-C8 qualification. It improves
urgency rather than proving energy/storage savings.

For later B/C, a PIR CPU wake must be separable from radio restoration *only after*
BAT-C8 proof. Simply delaying `next_message` still restores Wi-Fi after each wake
and can keep the owner awake. Retaining exact records in a sleep-safe deferred
queue needs eligibility/expiry persisted or conservatively flushed after reboot;
no RAM-only pending identity, indefinitely postponed quiet Node or false ACK.
A new health/event opportunity must not be suppressed merely because deferred
records exist. Queue-pressure flushing alone is insufficient for a quiet Node;
mandatory deadline/health/recovery opportunities are unavoidable.

## Eighteen required scenarios

`GAP` below means no approved end-to-end numeric delivery latency; configured
rule thresholds are not permitted transport delays. All rows are source/design
review; only the disputed component behaviors listed in validation are host-run.
No physical alert, network outage or battery campaign is claimed.

| Case | Detecting component / required evidence | Deferral, radio necessity and latency | Correct Hub behavior / battery consequence |
|---|---|---|---|
| 1 SOS with queued PIR | No current SOS producer/kind; future local explicit request plus stable identity | P0 immediate attempt after durable admission if Node-origin; never wait for PIR; latency GAP | Urgent selection/reserve must be proved; current limited bypass insufficient. Radio cost justified; no invented dispatch. |
| 2 CallFamily during interrupted connectivity | Actual host Hub UI/application producer; Node-origin only hypothetical. Exact action plus unavailable/pending status | Hub-origin needs no C3 RF. Future Node-origin P0 stable retry/rejoin; physical no-link delivery impossible; latency GAP | Save locally, expose pending/unavailable, prioritize backend when available; never claim family received it. Retry energy unavoidable/bounded; canonical overflow remains open. |
| 3 OK after CallFamily | Hub/application producer and active incident context; separate OK identity/time | Prompt requested-check-in evidence; current Node cannot know incident relationship. If Node-origin treat conservatively prompt; latency GAP | OK does not resolve CallFamily. Matching morning evidence follows its own rule. No redundant Node RF for Hub-local action. |
| 4 Unexpected night door | Qualified door producer (not installed C3), Hub quiet-hours/time/mode | Important OPEN/CLOSE exact/prompt; Node cannot classify learned unexpectedness; latency GAP | Hub emits quiet-hours concern when event applied; retain close/order. Radio necessary if remote producer, justified safety cost. |
| 5 Unexpected night movement | PIR observation; Hub location/night spacing/count/config | First/relevant motion stays prompt; no safe global P2 label; event-driven night decision latency GAP | Delay postpones threshold detection; use occurrence local minute, not current receive minute. RF justified for required evidence. |
| 6 Morning motion before deadline delivered later | Node original time/key/uncertainty; Hub window and grace | Arrive and durably apply before evaluation at `grace_end_at` when relied upon. This is an existing rule deadline, not a fixed radio SLA | Late evidence may leave an already-created false concern. B not equivalent; C would need clock/error/processing allowance. Necessary deadline session can cost RF. |
| 7 Missing morning, fresh valid coverage | Hub requires sufficient observation **and delivery completeness**, trusted window/mode | Fresh contact alone cannot justify holding observed motion across grace; no new radio if already complete | Evaluate absence only with sufficient evidence. Current contact tracker is not whole-window coverage; no batching-based false negative evidence. Health costs retained. |
| 8 Missing morning, stale coverage | Hub lease/coverage/time/gap inputs | Required health/recovery timely; no activity-only flush strategy | Suppress unjustified inactivity/missing inference; show uncertainty/offline. Radio for liveness required; silence is not normal or inactivity proof. |
| 9 Prolonged inactivity | Hub last original activity, applied inactivity threshold, time/coverage | Needed motion applied before absence evaluation; no fixed batching delay approved | Hidden recent motion can trigger false alert. Threshold is anchored at Hub's last known evidence, not Node's assumed quietness. RF may be necessary despite ordinary-looking PIR. |
| 10 Repeated ongoing room motion | Existing ActivityEpisode first/repeat/summary | Current RAM repeat coalescing reused; no extra periodic40–120s wakes. New summaries/semantics need equivalence proof | ACTIVE not continuous presence; native summary ignored by current activity rules. Same current records/saves; no new reduction assumed. |
| 11 Quiet Node with unsent records | Node persisted pending age, health/retry/deadline state | A retries without new motion. B-only waiting for another PIR/urgent event is unbounded and unacceptable | Keep retries/quiet health/recovery opportunities; held pending currently inhibits sleep. Requires a bounded deadline opportunity before any future deferral. |
| 12 Near-full queue | Node pending/store counts, admission failures | Motion limited28 of32; important work may use remaining4, not infinite. Capacity can force justified early flush; important event may not wait for large routine drain | Backpressure/gap/failure visible; do not erase or allocate new identity to retry. Overflow/critical saturation policy open. Burst and energy can increase. |
| 13 Node reboot with deferred records | Encrypted recovery, origin keys and time uncertainty | Restore current pending as due; any new deferred metadata needs compatible durable recovery or fail-safe immediate flush | Recovered keys retain time; old monotonic deadline cannot be reused as new-boot absolute. Repeat RAM is not covered by pending snapshot. Boot/rejoin/write cost unavoidable. |
| 14 Hub reboot during bulk | Node exact pending/ACK/report state; Hub committed keys/root | No collective retirement; each durable ACK governs exact key; unACKed retry/rejoin | Already committed duplicates skip reducer; not-yet-durable originals retry. Any future delivery holding cannot corrupt retirement proof. Recovery RF/flash overhead remains. |
| 15 Lost ACK, batch retransmit | Original immutable key/content, authenticated ACK | Retry exact frames; MAC success never delivery. Retry bound is current backoff, not successful-delivery SLA | One logical effect for duplicate; no fresh identities or ACK-all shortcut. Retries add RF but not new semantic records. |
| 16 Cross-sensor out-of-order | Hub occurrence/context, coverage, source identities | Per-Node order does not ensure cross-sensor equivalence. No blanket delayed delivery | Current reducer can regress last activity/miscount post-door motion. Needs late-data/order/closure contract before C; buffering would add RAM/latency, not assumed here. |
| 17 Battery low | Current battery0/unknown, no calibrated target ADC policy; local health faults distinct | Optional telemetry P3; never suppress important sensing/ACK/recovery to claim savings. Latency GAP | No trustworthy SOC/remaining-life inference. Measure supply/current, calibration, brownout handling in separate battery task; no extra sampling/RF specified here. |
| 18 Future bed threshold | Future Node occupancy session start/last observation/end/uncertainty; Hub applied household threshold | START/END alone may notify too late while still occupied; necessary threshold-crossing evidence requires a proven deadline opportunity | Occupancy not sleep/identity. Hub makes routine/alert decision; sensor-specific local tracking only. Bed hardware excluded R1; no session RF/energy estimate. |

## Routine-deadline equivalence and time limits

`P/shared/src/rules.cpp:19–83` accepts occurrence-window activity/OK but evaluates
missing morning at grace; late apply does not clear `missing_incident_created`.
At102–219, bedroom starts/restarts sequence, bathroom/kitchen complete it, night
visits count with configured spacing, door OPEN emits quiet-hours concern,
CLOSE ends open state, Motion after close changes post-door evidence. At223–271,
inactivity/door timers require Home/Covered/trusted clock and depend on current
anchors. Native MotionSummary is excluded at110. The caller must also supply
valid time/context for event-driven night rules; that function is not itself a
complete uncertainty/clock gating service.

A/B/C are not equivalent merely because eventual original timestamps match:

- B can withhold evidence while fresh health misleads a timer; late arrival cannot
  undo notification/history already emitted by the current morning path.
- Cross-sensor deferred ordering can regress last-activity time and make old motion
  count after a later door close. Per-Node sequential frames do not solve it.
- C requires delivery plus Hub commit/reducer time before the earliest relevant
  decision, **including clock/uncertainty and processing allowances**; the Node
  does not possess the Hub's current cross-sensor inactivity anchor or all rules.
  An eligibility/deadline contract or conservative prompt fallback is necessary.
- Corrected time must retain original provenance and mapping uncertainty; do not
  rewrite immutable retry bodies or silently reclassify old observations as now.
- Daily/learned state needs coverage, day identity, late revisions and idempotent
  baseline contribution. Existing deterministic core is not full learned-state
  recovery. Batching does not supply GS-D022/023 implementations.

The secure target explicitly creates Node `occurred_at=0`, uncertainty86400s
(adapter1160–1162); Hub `received_at=0` and `run_state_once()` without local minute
(`hub_runtime_adapter.cpp:941–946`). No physically qualified trusted-time/timer
path is established. Host tests use synthetic trusted time, not production
alert qualification. Clock absence is a prerequisite gap, not proof that event
latency no longer matters. See [routine guide](../../features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md).

A minimum transport-latency SLA for P0/P1/P2, eligibility for ordinary door/motion,
late correction/retraction behavior and delivery-complete coverage are product
**decision gaps**. No 40/60/90/120s batch window is chosen here. If new priority or
latency semantics are approved, a separate canonical Decision Log/domain/work
state/index update and context increment/commit/promotion is required before
implementation. GS-D025–028 remain unchanged in this investigation.

## Battery and storage accounting without another 72-hour simulation

Labels: **SOURCE-DERIVED** = actual code behavior; **HOST-MODELED** = prior
qualified-observation replay or this component fixture; **UNPROVEN** = real
currents/wakes/RF/runtime/flash physics; **MEASURED** battery values = none here.

Prior source-derived six-Node counts are reused from
[R1_NODE_MOTION_CONSOLIDATION_20261008.md](R1_NODE_MOTION_CONSOLIDATION_20261008.md),
not rerun and not raw electrical pulse counts. Six Nodes over72h =18 Node-days;
other exact events are the inherited scenario, not proof of installed buttons.

| Fixture | Original semantic Node events/72h | Ideal app packets/72h A/B/C with current one-event wire | Logical Node recovery saves/72h | Average per Node/day events / saves |
|---|---:|---:|---:|---:|
| NORMAL |1152|1152|2304|64 /128|
| HIGH |5328|5328|10656|296 /592|
| STRESS literal45s pairs |10452|10452|20904|580.67 /1161.33|
| PAIRED46 adverse sensitivity |68196|68196|136392|3788.67 /7577.33|

Ideal prompt durable ACK assumptions exclude retries, report fragments, health,
security/FOTA and boot/epoch/gap work. Save counts are one admission and one
retirement each, **not measured flash writes/erases**. An urgent/frame grouping
schedule does not automatically combine snapshot commits. Real network counts
are E + event retries + health + security + retirement + FOTA traffic, plus Hub
ACKs; all terms have current independent meanings. New multi-event packets would
require an unapproved wire/partial-ACK/recovery contract and are out of scope.

| Metric, per Node/day unless stated | A actual baseline | B additional holding/piggyback | C deadline-aware holding |
|---|---|---|---|
| CPU wakes / sensing | Actual count UNPROVEN. Awake loop20ms corresponds to4,320,000 delay cycles/day if awake throughout (ideal reference, not measured sensor/CPU wakes). Light-sleep returns use GPIO/deadline timers, max30s. | Same sensing needed. No new periodic consolidation wake allowed; merely holding queue can increase awake poll cycles. | Same observation work; necessary deadline wakes may add overhead but must serve correctness, never convenience. |
| Quiet timer/reference | In an ideal120s health interval, about four30s-bounded sleep windows, or roughly2880 returns/day before margin/owner-work overhead; not a measured total/bound. Held-high/outage/callback work alter this substantially. | Cannot assume fewer returns; current radio restored after each. | Must measure earliest actual deadlines against existing cap/margin, not invent cadence. |
| Wi-Fi AP associations |0 in inspected ESP-NOW path. Radio initialization plus restore after successful sleep returns; counts UNPROVEN. |0 AP associations; startup/restore unchanged without BAT-C8 path changes. |0 AP associations; additional necessary opportunities can add radio-active periods. |
| Application transmissions |64 NORMAL/296 HIGH mean per Node/day,580.67 literal STRESS; source-derived HOST-MODELED ideal sends. |Same E; sharing periods is not fewer packets. Retries may increase or decrease, UNPROVEN. |Same E; retry/control counts unproved. No promised packet ratio. |
| Health RF | Quiet authenticated no-event reference720 attempts/day at120s; successful application contact postpones it. Actual H schedule is conditional, not720 added blindly to every workload. |Required H preserved; current pending suppression must be changed/proved for holding, otherwise no safe health opportunity. |H cannot slip beyond coverage/liveness correctness; no unapproved cadence change. |
| Radio-active time |UNPROVEN. Radio starts on wake even for local maintenance; WIFI_PS_NONE while active. |Could fall with genuinely shared sessions, or rise through longer ACK/drain/hold time. Current queue-only holding inhibits sleep. |Adds necessary opportunities; energy comparison needs matched traces, duty cycle and current. |
| Node flash/NVS |2E logical saves ideal; boot/session/report/gap metadata add work. Real programs/erases/amplification UNPROVEN. |Same events imply same existing saves. Durable eligibility/expiry metadata can add saves; no coalesced commits assumed. |Same plus possible deadline/recovery state; no percentage saving. |
| Pending peak |Ideal prompt admission/ACK replay usually one business event outstanding; actual cap32, motion stops28; current MAC send is not durable ACK, so target peak UNPROVEN. |Can accumulate to28 ordinary plus4 non-motion; pressure/expiry must force progress. |Explicit bound must include burst during flush and urgent headroom; below32, not unlimited. |
| CPU active/sleep residency |UNPROVEN target. Coalescing/retry/gates already bounded; pending/outage keeps awake. |Keeping deferred state through sleep requires a proven power-owner change; otherwise residency worsens. |Deadline/context bookkeeping plus bounded drain; measure, do not infer energy from packet count. |
| Extra Node RAM |0 added by recommendation; current queue/recovery allocations unchanged. |Unapproved metadata; budget as O(32) fixed slots, no second payload queue. Illustrative32*(8-byte deadline+1-byte class)=288 B before padding/context, NOT a target/final allocation. |At least B metadata plus bounded applied-context/expiry state; allocation unproved. |

**Estimated battery impact:** A retains the existing unqualified baseline; no
new battery saving is claimed. B/C may save radio-active transitions only with
proven eligibility and sleep/radio integration. Current deferral can consume
more energy by staying awake, retrying or persisting metadata. Board regulator,
battery capacity/chemistry, currents, voltage, RF link quality, PIR workload,
latency and ACK/rejoin distribution are required for a life/percentage estimate.
BAT-C8 plan P1–P10 remains NOT_RUN; its existing host tests/target-build evidence
is preserved, not rerun. Retain required production sleep/wake/fail-awake/restore
behavior and later relevant physical qualification; no sleep is claimed physically
qualified merely because fresh-install ACK gates passed.

### Material Hub storage conclusion

For exact batching alone A/B/C: **original identities E unchanged, ideal separate
packets E unchanged, Hub exact ingestion E unchanged**. Hub retained history and
backend representations change only through the *separate* approved-direction
loss-aware compaction proof, not radio-session grouping. Add the inherited24
Hub-local outcomes over72h: current modeled Hub inputs1176 NORMAL,5352 HIGH,
10476 literal STRESS (adverse sensitivity68220). Actual production128 lifetime
journal can refuse later inputs; these are offered/model inputs, not claims that
all fit today. Current Hub writes/verifies each novel admitted event before ACK
(journal327); exact logical admission count remains E+L, physical NVS programs,
COW generations, report updates and erases are implementation-dependent.

Prior conditional Hub compaction counts are unchanged:

| Prior trusted-time model | Retained exact / new point summaries | Backend representations | Protected peak bytes |
|---|---:|---:|---:|
| NORMAL ordinary |462 /442|904|249856|
| NORMAL mixed |645 /329|974|278528|
| HIGH ordinary |2478 /640|3118|638976|
| HIGH mixed |3201 /482|3683|745472|
| STRESS literal45s ordinary |5544 /850|6394|1204224|
| STRESS literal45s mixed |6779 /636|7415|1384448|

These preserve native summaries exactly and all modeled point membership; summary
count is not observed-point count. Current target time uncertainty makes
eligibility unproved. Earlier abstract STRESS69696 and typical-profile checkpoint
results retain their original assumptions and must not be replaced by the lower
literal45s trace. No capacity matrix, wear campaign or compression work rerun.

**72-hour adjustment:** none to totals, sizes or backend object counts for selected
A. Existing128/192/256 KiB failures/conditional witnesses remain; batching is not
a capacity fix. Do not credit fewer Node snapshots, Hub writes, dedupe witnesses,
retirement state or backend backlog from fewer RF periods.

**Peak admission/COW/GC caveat if B/C is later selected:** simultaneous deferred
release can bunch up to32 pending/Node,192 total across six Nodes. This is a
possible retained-record envelope, not a proven192-at-once RX burst bound or
final critical reserve. Current callback16/ingest32 must reject/backpressure
safely, not ACK dropped frames; urgent traffic must not be hidden behind a routine
burst. Preserve current one-frame/owner serialization and consider bounded drain
only after proof. Exact per-event journal work remains; report/COW/checkpoint
interleaving and unsynced staging peaks can worsen despite identical totals.
GS-D016's existing192 pending-key and unreported-credit proof remains necessary.
No new admission experiment is required for **A unchanged**. Before adopting B/C,
run focused burst/partial-ACK/Hub-reboot/admission-next-operation checks against
the actual protected allocator/GC guard then available; do not assume a wire batch
is one atomic NVS transaction. Existing full192-HOT capacity failures remain open.

Connected backend synchronization must remain near-real-time after Hub durable
acceptance; Node delay changes caregiver freshness before that stage. Internet-only
outage has locally powered/connected Nodes and normal local ACK behavior, so it
is not justification for applying the local-radio outage/backoff/coalescing profile.

## Engineering recommendation and separate work

| Proposed scope | Eventually affected production modules (all under P) | Effort / prerequisites / risks | Hub storage dependency |
|---|---|---|---|
| A selected |None; reuse current components|0 implementation days in this investigation. Known delivery/time/power limits remain recorded; no new protocol or qualification claim.|**NO** new Node blocker. Proceed on existing event stream. |
| Optional narrow urgent-first selection |`firmware/node/components/radio/node_radio.cpp/.hpp`; `firmware/node/target/esp32c3/node_runtime_adapter.cpp`|Planning estimate2–4 engineer-days for bounded selection/host-target checks after priority approval, excluding hardware qualification. Prove connected/outage first/retry gates, in-flight/health/report/FOTA blocking, starvation, queue reserve and door/order behavior. Current C3 critical producer is unestablished; do not ship speculative SOS. Separate Node task.|NO; no claimed storage savings. |
| B holding at existing opportunities |Same radio/adapter; `firmware/node/runtime/node_runtime.cpp/.hpp`; `firmware/node/components/power/power.cpp/.hpp`; `firmware/node/components/storage/node_recovery_persistence.cpp/.hpp`; review `node_security_link.cpp` integration|Planning estimate1–2 engineer-weeks for a bounded prototype and host/target integration *after* eligibility/time/health contract, excluding product decisions and physical measurement. Preserve32 cap, durable identity, required health and sleep inhibition correctness. No extra payload queue/wire batch.|NO; separate BAT-C8/Node power work. |
| C necessary deadline extension |B modules; Hub `runtime/hub_runtime.cpp/.hpp`, rules/coverage interfaces only if an approved applied deadline/complete-observation contract requires them; existing secure transport boundaries then reviewed|Estimate exceeds B; not speculatively scoped/implemented here. Prerequisites: maximum latency, applied context, clock uncertainty, late/order/recovery and partial completion contracts. Prove no periodic convenience wakes and uncertainty fallback. Backend/PWA changes only under separately approved need.|NO; never prerequisite for storage fit. |

Separate battery work: BAT-C8B wake/radio/current matched-load qualification;
measure actual timer/GPIO wake/restores, sleep residency, held-high/outage costs,
health/retirement/in-flight blocking and retries; calibrate voltage/SOC only under
approved hardware. Any future holding optimization must compare total energy and
latency, not packets alone, and preserve existing durable/reboot/ACK behavior.

Open product decisions: P0/P1 mapping and supported physical action producer,
bounded urgent/unavailable indication and critical saturation policy; P2
eligibility/door policy; end-to-end latency/decision margins; delivery-complete
coverage; late corrections/order/day closure and time trust; summary/backend
contract. Critical storage reserve/final NVS allocation remain separately OPEN.
No canonical files or CONTEXT_VERSION are changed here.

Open technical blockers: current target trusted time/timers and coverage recovery,
strict urgent selection/in-flight bounds, sleep-safe held state/health integration,
32-slot recovery/expiry, proven applied-context deadlines, late/order idempotence,
protected Hub admission/root/report/next-operation/GC and target RAM/OTA/wear.
Keep the Node enhancement questions off the Hub storage critical path.

**Next Hub storage task:** bounded proof of authenticated persisted
admission/retirement-credit/report/root selection and protected next-operation
COW/GC forward progress using the unchanged source-derived semantic event stream,
with essential/gap evidence preserved. Critical classification/reserve/saturation
and backend representation completion decisions remain prerequisites to
production policy. Do not repeat the full72h matrix or begin implementation here.

## Focused validation and reproducibility

Only disputed cases were run; previous coalescing/recovery/physical/storage
qualification logs remain untouched. New HOST-ONLY program:
`P/host/storage/node_delivery_audit.cpp`. It calls unchanged NodeRadio,
NodeRuntime, PowerPolicy sleep/health helpers and RulesCore; synthetic fixture
thresholds/times do not establish product latencies. It neither models RF/current
nor proves target NVS/encrypted recovery/power-failure behavior.

From product root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -DGS_ENABLE_TRACE=0 \
  -I. -Ishared/include -Ifirmware/node/components \
  host/storage/node_delivery_audit.cpp \
  firmware/node/runtime/node_runtime.cpp \
  firmware/node/components/radio/node_radio.cpp \
  firmware/node/components/storage/node_store.cpp \
  firmware/node/components/power/power.cpp shared/src/rules.cpp \
  shared/src/logging.cpp -o /tmp/ghar_node_delivery_audit
/tmp/ghar_node_delivery_audit
```

Observed exit0,10 groups:

```text
PASS connected_call_waits_for_global_gate
PASS outage_nonmotion_first_attempt_bypass_not_unlimited_priority
PASS 28_motion_plus_4_nonmotion_reserve_no_unbounded_urgent_admission
PASS reboot_preserves_origin_time_and_durable_ack_opens_drain
PASS held_pending_suppresses_health_and_sleep
PASS late_morning_evidence_does_not_undo_created_incident
PASS deferred_motion_false_absence_unknown_coverage_or_time_suppresses
PASS out_of_order_motion_regresses_anchor_and_postdoor_chronology
PASS night_decision_requires_occurrence_minute_and_prompt_evidence
PASS exact_door_records_still_require_ordered_reducer_application
RESULT=PASS groups=10; component counterexamples only; no RF/NVS/battery/target qualification
```

Pass means the recorded limitations are reproducible, **not** that deferred
ordinary delivery/P0 immediate service is implemented or safe. Documentation
checks cover changed-file scope, whitespace, relative links/source anchors,
unchanged context/production/BAT-C8/partition and prompt checksum. No full release,
storage simulation, target build or hardware gate is run. Commit explicitly only
this evidence, the focused host program and the material ExecPlan finding.
