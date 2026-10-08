# R1 Node-local motion consolidation investigation — 2026-10-08

**Result: Nodes already consolidate PIR; a longer quiet timer is not a safe
standalone change.** Investigate a durable Node episode with timely, immutable
progress observations, keeping household decisions at the Hub. Reduced event
counts for that new protocol are **UNDETERMINED**, not a capacity fix proved here.
Production integration remains **STOP**.

Authority: TEST_EVIDENCE / IMPLEMENTATION_DESIGN / PROPOSED. This is neither a
new master requirement nor canonical promotion. GS-D011/021/022/023/024 apply;
GS-D013/014/015/017 remain formally OPEN. The previously user-approved 72-hour
internet-outage/loss-aware aggregation direction awaits the explicit governance
action below. No new LOCKED decision, CONTEXT_VERSION or canonical file changed.

## Safe resume and scope

Preflight PASS; branch `feature/r1-hub-storage-lifecycle`; start HEAD
`dc4eb0c61419cdf0e0e64074638fc1f43289cfa1`; local and canonical context
`2026-10-07.003`. The handoff's containing commit resolves to exactly this HEAD.
Tracked checkpoint files are unchanged, including the 72h model/probe/logs;
the old 14-test PASS and 54-case SDK capacity record remain preserved, not rerun.
Initial Git status is only `?? prompt.txt`. Its SHA256 before/after is
`c45a9db5f1c4e8252993b3df8bfa4639ec2517a16f3070d1ad105c409a285e69`.
`prompt.txt` was not read, modified or staged. No destructive Git operation,
hardware, factory initialization, Jira or BAT-C8 action occurred.

Read AGENTS and the mandatory context/release/work-state/index sequence, locked
decisions, storage architecture, active ExecPlan, 72h handoff and capacity evidence,
and relevant P0, routine, battery, delivery/backend and actual source contracts.
Historical context-sync statements describe prior checkpoints; current preflight
matches .003. Supporting guide claims that PIR episodes do not exist or the
morning sequence lacks a lower timestamp bound are stale implementation claims;
the current source below establishes the facts. No canonical requirement conflict
was resolved by inventing policy.

```text
BUG_CLASSIFICATION=INVESTIGATE_ONLY
REQUIREMENT_SOURCE=docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md; REQUIREMENT_GAP for episode eligibility/progress/quiet/loss semantics
DECISION_IDS=GS-D011,GS-D016,GS-D020,GS-D021,GS-D022,GS-D023,GS-D024
TASK_SCOPE=source audit, proposed state machines, focused host counterexamples/replays, inherited capacity comparison, evidence and ExecPlan
OUT_OF_SCOPE=production Node/Hub/backend/PWA integration, partition, canonical promotion, BAT-C8 changes, hardware, Jira, bed hardware
```

The existing storage lifetime blocker remains R1_BLOCKER under GS-D005/016 and
the release contract's essential-functionality/data-loss/durability rules. The
repeat-loss/summary-consumer/time/coverage questions below are INVESTIGATE_ONLY
within this requested audit; no adjacent fix or new release classification is
implemented. Bed sensing is FUTURE ONLY / DEFER_POST_R1.

## Actual implementation, with source references

Paths below use `P = code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.
Line references are to the unchanged start-HEAD production files.

| Area | Real source and finding |
|---|---|
| Electrical PIR | `P/firmware/node/target/esp32c3/node_target_config.hpp:23` gives GPIO4, 10s stabilization, 20ms polling, 150ms debounce and 1000ms minimum retrigger. `components/sensing/sensing.cpp:29` qualifies stable level transitions, initializes boot-high without Motion, and emits on a qualified rise. Falling PIR has no event. Sustained high does not periodically create Motion. A rise suppressed by retrigger changes stable state and does not emit later without a new transition. These are software limits, not a measured PIR's optical response. |
| Existing episode | `P/firmware/node/components/power/power.hpp:236` and `power.cpp:31` implement ActivityEpisode: first Motion, RAM repeats, connected quiet45s/max300s, radio-outage idle1800s. `needs_first` polls before deciding. At exactly quiet expiry the next detection starts a new episode. Max300s ends a software batch even during continuing activity; it is not a physical departure. |
| Target wiring | `P/firmware/node/target/esp32c3/node_runtime_adapter.cpp:1090` polls the episode before sensing. At1143 repeats call `note_repeat` rather than `runtime.record`; at1153 first Motion goes through runtime and at1167 encrypted recovery is saved before any send. At1213 the separate MotionSummary is admitted and persisted, then the RAM pending summary is cleared. Raw HIL (`GS_HIL_BUILD`) bypasses episode coalescing; do not infer commercial rates from raw HIL. |
| Summary meaning | `P/shared/include/gs/domain.hpp:88`: additional_count, first_ms, last_ms describe **additional observations**, not the first Motion. No episode-ID linkage or occupancy duration exists. `power.cpp:36` can merge a pending same-room summary across separate closed episodes; other-room detail may be omitted, with a RAM omitted counter. It cannot establish a single uninterrupted session. |
| Timestamps | Target first Motion uses monotonic `now`, occurred_at0, uncertainty86400s, battery0/RSSI0 (`node_runtime_adapter.cpp:1153`). Summary uses last-repeat monotonic and original millisecond endpoints. `shared/include/gs/protocol.hpp:259` preserves absent absolute time as0. Secure Hub target at941 uses hub_received_at0 and `run_state_once()` without local minute. No trusted absolute clock, day assignment or physically operating timed routine path is proved by these source fields. No new time conversion is invented here. |
| Queue/persistence | `P/firmware/node/runtime/node_runtime.hpp:50` defaults to32 retained/32 TX. `node_runtime.cpp:58` validates meaning, allocates origin/sequence, preflights radio, then retains/enqueues. `components/radio/node_radio.cpp:23` reserves4 slots from ordinary Motion/MotionSummary. `components/storage/node_recovery_persistence.cpp:72` serializes pending immutable events/retry/report metadata, **not ActivityEpisode**. Recovery repository at247 seals a generation/domain-bound snapshot; `common/security/nvs_association_blob_store.cpp:45` writes/commits the bounded blob. |
| Reboot/retry | `node_runtime.cpp:144` snapshots retained/pending/report state; at171 restores old origin keys under a newer boot session. `node_security_link.cpp:118` rejects corrupt/IO recovery. `node_runtime_adapter.cpp:913` handles matching authenticated application ACK and at931 persists changed retirement state. A MAC callback is not a durable ACK. Current unclosed repeats and pending uncommitted summary can disappear on reset, even if the first Motion is already Hub-ACKed. |
| Actual radio | `node_runtime_adapter.cpp:1438` encodes, application-AEAD seals and sends ESP-NOW on the Wi-Fi STA radio, not a separate TCP/cloud connection per PIR. Initialization at227 selects Wi-Fi RAM config/channel1/10dBm/WIFI_PS_NONE. Health, security/rejoin and retirement fragments also use RF. |
| Retry rate | `P/shared/include/gs/protocol.hpp:35` supplies200/600/1800/10000/60000ms plus sequence jitter0..100ms. `node_radio.cpp:100` retains identity, applies the global opportunity gate and periodic backoff; valid retirement opens drain. At45 priority unsent nonmotion bypasses ordinary outage probes. At65 new outage Motion gets a bounded recovery opportunity. `node_runtime_adapter.cpp:982` selects outage after repeated unacknowledged attempts. Internet-only outage does **not** select this local-radio profile. |
| Hub commit/duplicate | `P/firmware/hub/runtime/hub_runtime.cpp:177` commits journal before returning Durable ACK, returns Rejected on Full/fault, and skips repeated reducer effects for Duplicate. Target at945 runs that path before sending the ACK at966. `components/storage/journal.cpp:291` checks exact key first, then128 lifetime cap. Current key-only fast duplicate path versus immutable-payload digest verification remains an existing integration blocker; this audit does not claim adversarial same-key conflicts are solved. |
| Hub rules | `P/shared/src/rules.cpp:19` applies routine-window activity/OK with occurrence uncertainty, location, mode and test exclusion. At110 native MotionSummary is ignored for activity rules; `domain.hpp:192` also excludes it from is_activity. At132 Motion/door updates last-activity exact key/time; bedroom Motion restarts morning sequence at139, night visits use configurable spacing at165, Motion after door close sets post-door evidence at137. Timer eligibility at230 requires Home/Covered/trusted clock. `hub_runtime.cpp:155` without local minute restores only basic activity anchors. |
| Coverage vs liveness | `protocol.hpp:25` production health120s, authenticated liveness310s, separate event-time coverage190s. `hub_runtime.cpp:33` records authenticated health/contact separately; `components/coverage/coverage.cpp:48` is a current-contact coverage tracker, not recovered whole-window coverage. A heartbeat or a delayed positive observation does not certify past sensor observation. |
| Backend | `P/backend/ghar_sajag/durable_commit.py:74` and `ingest.py:42` validate existing native MotionSummary count/endpoints. Existing exact-event idempotent completion is described in `P/docs/DURABLE_BACKEND_COMPLETION_CONTRACT.md:3`. It is not an episode/progress/source-manifest or daily-revision API. |

Answers to the six audit questions:

1. Qualified electrical observations cannot emit faster than1/s/Node in this
   configuration, and require fresh qualified rises. Stable-room connected new
   **Motion** starts require quiet45s or max300s closure: a singleton may recur
   at45s; a continuously repeated episode produces a first plus summary around
   each300s boundary (next actual detection can occur later). There is no universal
   40/60/90/120s transmit cadence. Summary/control backlog, retry, binding change,
   reboot and transport gates give different packet timing. Pending drain can
   send faster than new activity creation. Hardware accepted rate is unmeasured.
2. Yes: repeats within an episode already avoid per-repeat full events, NVS saves
   and application transmissions. Max300s, quiet45s and pending-summary behavior
   bound this mechanism; local-radio outage has different behavior.
3. Yes: one person working for hours may produce many software episodes and many
   distinct immutable keys. PIR cannot prove one person, continuous presence or
   the boundary of a meaningful activity. At40s spacing it merges; at60–120s
   spacing it normally closes between detections. Native summaries can also span
   multiple activity intervals when summary admission is delayed.
4. Existing rules need original kind, zone, occurrence time, occurrence uncertainty,
   test flag and stable full source key, plus applied config, local minute, mode,
   clock trust and coverage. Morning-window interior evidence, bedroom restart
   times, night visit spacing and post-door chronology can require intermediate
   Motion points. First/last/count alone are insufficient. Monotonic provenance
   and receive/order/context are needed by time/recovery/coverage, even though the
   pure RulesCore does not read RF/RSSI/battery or native aggregate endpoints.
   Battery/RSSI are not blanket removable from canonical source/health contracts.
5. Repetitive **semantic** Motion is persisted when episodes close between
   detections; raw PIR edges and within-episode repeat updates are not each
   persisted. The first and summary have separate keys and meanings, not retry
   duplicates. Hub persists every admitted distinct key today, including native
   summaries ignored by routine rules, and neither cloud completion nor Node
   retirement frees the128 lifetime archive. Encoding/context duplication and
   history-level redundancy are distinct from valid exact retry witnesses.
6. Electrical qualification and permitted semantic classification can precede
   allocating a business-event identity; the current code already does this.
   There is no requirement to first create/persist an exact event for every raw
   pulse. Once an immutable business record is admitted/visible, its key/content
   must remain stable and must be committed before transmit. Required last-motion,
   point or gap state cannot live solely in volatile RAM just to claim fewer
   writes. A new compact durable observation journal can precede immutable
   progress publication, but its selected recovery/identity obligations need proof.

## Proposed PIR state machine — no production policy selected

Node owns sensor qualification and a bounded observation episode, **not household
routine learning**. Hub owns eligibility, cross-sensor dependencies and rules.

```text
IDLE --qualified first observation + durable START--> ACTIVE
ACTIVE --qualified repeat--> update recoverable observation state
ACTIVE --Hub-required progress boundary--> immutable durable PROGRESS + retry
ACTIVE --validated quiet with adequate observation--> immutable durable END -> IDLE
any state --fault/reboot/maintenance/observation loss--> UNCERTAIN metadata/gap
```

START/PROGRESS/END above are new proposed messages, not the existing enums and not
implemented. ACTIVE means recent positive observations; it is never a continuous
presence claim. Track episode origin/ID, assignment/config version, first actual
motion, first repeat, last actual motion, observation ordinals/quality, clock
basis/uncertainty, coverage generation and published progress cursor. END records
last observed motion separately from quiet-validation/emission time. Quiet waiting
does not add duration or activity. Bound counter/point overflow and make fidelity
loss explicit. A max-size/time continuation remains the same logical episode
with a new immutable revision, not an inferred departure/new person.

Default eligibility is exact fallback. Hub must establish any safe eligibility
contract; Node cannot know another Node's door close or an unresolved household
rule dependency. Configuration/room/owner/clock/coverage changes close or split
interpretation boundaries with explicit cause. Revocation, missing permission,
expired contract or uncertainty falls back to timely exact evidence. If required
cross-sensor state cannot reach the Node promptly, retain/send its Motion evidence
at the current safe cadence; do not guess that a common room is always ordinary.

Two potentially useful representations, both requiring later qualification:

- For ordinary history after necessary inputs are accounted for, use a linked
  episode's observed endpoints/count/quality as the displayed historical record.
  Multiple immutable progress revisions need not each become a separate caregiver
  activity row. Source/progress membership remains available for dedupe/recovery.
- Where rules or learning need intermediate times, retain bounded **separate
  observation points** in compact progress batches. Stable `(episode ID, observation
  ordinal)` identifies each point; an immutable batch key/revision/content commits
  before send. Hub applies each required observation once, under its original
  timing/config, and materializes consumer state before history compaction. Do not
  feed the new public episode to the existing ignored MotionSummary enum.

This can reduce repeated full-record context, ACK traffic and historical rows,
but does not prove fewer required durable point writes. Current RAM-only repeats
are already cheaper than a fully recoverable new episode. Unnecessary raw electrical
chatter remains filtered before semantic admission.

### Quiet and progress policy

**QUIET_GAP_RECOMMENDATION=UNDETERMINED.**45s is a source fact, not a validated
person/activity boundary. Do not choose40/60/90/120s or reuse the300s night merge
as a universal quiet gap. Validate actual PIR hold/retrigger/sustained-high behavior,
movement/task interruptions, zone semantics and caregiver fidelity. Expiry can
establish an observed quiet interval only while sensor/runtime observation is
available; a reboot, blocked loop, maintenance or radio silence is not validated
quiet and must not generate a fabricated normal END.

**HUB_PROGRESS_UPDATE_REQUIREMENT=YES for required suppressed Motion evidence.**
Derive allowable delay from applied Hub rule/deadline/window/coverage context and
an explicitly approved alert-latency contract, with scheduler/RF/clock uncertainty
margin. Deliver required observations before the earliest affected evaluation.
An already due dependency can require immediate exact fallback. START cannot be
held until END; END alone after hours of working is insufficient. PROGRESS must
carry actual last-motion time and any required interior points; a timer heartbeat
with no new motion may refresh authenticated contact, never last-activity time.
Current health120s/liveness310s do not establish a safe activity progress interval.
If no finite safe batch delay is established, retain the current exact input path.

### Recovery and invariant obligations

| Risk | Required design behavior / current proof boundary |
|---|---|
| Hidden activity / false presence | Preserve required points; label endpoint/count fidelity and gaps. Never draw an uninterrupted occupied bar from first/last. Host counterexamples prove endpoints alone differ for morning-window and night rules. No final learning sufficient statistics are approved. |
| False inactivity / late alert | First evidence promptly delivered; progress precedes relevant Hub evaluation; preserve original time rather than receipt time. No Hub lease extension from a motionless timer. Host test shows native-summary replacement raises inactivity at100s despite actual motion at80s. It is a counterexample, not proof of a deployed target alert. |
| Door/actions/safety | Door OPEN/CLOSE, Call Family and I Am OK are independent exact events. Positive motion after door close remains timely and exact where needed; grouping before a cross-sensor close cannot hide it. Gap/fault/important evidence bypasses ordinary grouping; saturation policy remains open. |
| First/last / reset | Durably select START and every required point/last-motion update, or an explicitly approved loss marker before a future complete-data claim. On Node reboot restore selected state and old immutable pending batches; mark downtime UNKNOWN and interrupted episode, never invent quiet/END or continue monotonic time across boot. Current snapshot omits ActivityEpisode, demonstrated by the host test. RAM/RTC retention across light sleep is not reset durability. |
| ACK / retry / duplicate | Keep application durable-before-ACK on each immutable START/PROGRESS/END or exact input; record and validate full membership/content, not only endpoints/highwater. Retry unchanged body/key across Node/Hub reboot, and advance the observation/application cursor only through selected durable state. Do not mutate an in-flight cumulative summary; emit a new revision. Existing valid retry path tested; full new persisted cursor/root/conflict path UNPROVEN. |
| Hub recovery | Persist complete rules/coverage/config/time checkpoint plus uncovered required inputs before body release. Separate point application from display-row grouping. Reset liveness/coverage to UNKNOWN until established; preserve pending alert/last-motion anchors. Current target replay without local minute is not the full proof. |
| Cloud recovery | Stable episode/revision and point-membership IDs, exclusive representation claims and durable matching completion. Do not resubmit an exact source as a different episode representation after possible acceptance. Lost backend ACK repeats identical immutable identity/content; Node retirement never stands for cloud receipt. Existing mock/SDK evidence is not a production atomic protocol. |
| Timing / sleep | Schedule quiet and progress with boot-scoped monotonic deadlines, keep original wall-clock mapping/version/uncertainty separate. Use earliest debounce/retry/health/progress/quiet/security/maintenance deadline and GPIO wake. Retain low/debounce qualification, fail-awake on unknown runtime/wake/persistence. Stuck-high/fault is uncertainty, not proof of continued motion. |
| Finite bounds | Protect exact safety, report/root/GC and ordinary credits separately. Bound points, pending batch size and source window; on overflow no unsafe ACK or silent overwriting of required state.32 pending event slots do not imply32 episodes with unlimited internal points. Extended unavailable radio is a coverage gap; internet-only outage does not alter local sensing/radio guarantee. |

Host tests do not prove a new design satisfying all these obligations. They prove
selected actual behavior and demonstrate why the simpler proposal is unsafe.
In particular, unbounded future late revisions or safety reclassification cannot
be reconstructed from a lossy endpoint-only history. Policy must define the
retained evidence/correction horizon before eligibility is frozen.

Existing queue preflight can reject motion at28 ordinary pending slots before
NodeStore's full-store gap flag is set (`node_runtime.cpp:74`, `node_store.cpp:32`).
Drop counters alone do not establish durable observation-gap history. Record this
as INVESTIGATE_ONLY under GS-D022/023, REQUIREMENT_GAP for the approved loss/coverage
contract; no queue/gap/BAT-C8 fix is made in this task.

## Bed state machine — future only

```text
VACANT --validated occupied observation--> OCCUPIED
OCCUPIED --validated vacant observation--> VACANT
either --unavailable/uncertain observation--> quality UNKNOWN, no invented transition
```

Track session ID/start, last valid occupied/vacant observation, observed duration,
validated end, sensor availability, time uncertainty and an interrupted-session
cause. Separate elapsed session envelope from adequately observed occupancy
duration; unobserved time is unknown. Restore committed session/progress after
reboot, keep a gap rather than assume either occupied or vacant. Intermediate
progress and end need immutable identities and the same durability/retry rules.
Bed occupancy is neither proof of sleep nor occupant identity. Node does sensor
qualification/session tracking; household routine/cross-sensor decisions remain
at Hub. No bed hardware, R1 enum, production protocol, battery dependency or test
fixture for an unselected future sensor is added.

## Source-derived workloads and storage comparison

New replay compiles unchanged QualifiedInput, ActivityEpisode, NodeRuntime,
NodeRadio, NodeStore and RulesCore. Generation enters at **qualified observation**,
not each raw edge; separate debounce tests establish that distinction. Prompt
successful admission/application ACK and uninterrupted local radio are assumed.
Owner timer closure precedes each observation, and final closure tail is charged
conservatively after the72h observation interval. No target NVS, RF or clock is
used. Health, report fragments, rejoin and lost-ACK retransmissions are excluded
from ideal application-transmission counts and must be added for physical energy.

The original ExecPlan NORMAL40/HIGH160 episodes/Node/day can be realized with
starts every2160/540s, repeats in half/three quarters of episodes. This replay
uses four qualified repeats at+1/+10/+20/+30s in each repeated episode; the exact
repeat count is a fixture input, not a measured household assumption or new rate
requirement. It affects raw observations, not one-summary-per-closed-episode count.
Other exact source events retain the original24/96/192 per household/day envelope.
Add24 local Hub outcomes in72h, as in the prior model; those are not Node events.

The literal STRESS1920 starts/Node/day at45s plus a repeat at+1s does **not**
create1920 separate two-record episodes: last-repeat quiet expiry is46s, so
subsequent45s detections extend activity until max closure. A paired46s sensitivity
can nearly realize the old rough2/45s envelope. The lower45s replay must **not**
replace the high-volume bound for a commercial promise. Earlier69,696-source
capacity results remain valid for their abstract semantic workload; this section
qualifies only its attribution to the literal45s paired PIR implementation.

|72h six-Node fixture|Qualified PIR observations|Motion|Native MotionSummary|Other exact Node|Total source events|Recovery save operations / ideal app sends|
|---|---:|---:|---:|---:|---:|---|
|NORMAL|2160|720|360|72|1152|2304 /1152|
|HIGH|11520|2880|2160|288|5328|10656 /5328|
|STRESS literal45s pairs|69120|4938|4938|576|10452|20904 /10452|
|PAIRED46 adverse sensitivity|67644|33810|33810|576|68196|136392 /68196|
|Working8h/day/Node,40s detections|12960|1620|1620|0|3240|6480 /3240|
|Working8h/day/Node,80s detections|6480|6480|0|0|6480|12960 /6480|
|Working8h/day/Node,120s detections|4320|4320|0|0|4320|8640 /4320|

Recovery operations count one saved admission and one saved retirement per
source event, excluding boot/epoch/gap changes. They are **logical save calls**,
not measured page programs/erases/bytes. Repeated RAM updates cause no such saves.
Exact distinct events are not duplicates merely because they belong to one human
task. Lost-ACK retries add transmissions while retaining the same source count.

A = actual source-derived events retained exactly in the inherited new-storage
ledger. B = proposed Node episodes: only the exact fallback is currently justified,
so its safe counts/ledger equal A. Reduced B would require approved eligibility,
required point fidelity, progress deadlines, durable Node schema and backend
meaning; do not claim a guessed E-fold or percentage reduction. For a later
START/PROGRESS/END protocol, event count depends on started/ended episodes plus
immutable progress batches and unchanged exact exceptions. Point-journal commits
are a separate count. None of these terms is bounded by a quiet-gap guess here.

C = the unchanged72h Hub loss-aware point-container model, fed source-derived
records. It preserves all native MotionSummary bodies exactly. Last **Motion**
anchors (not ignored summaries), local outcomes and other exact classes remain
exact. Ordinary/mixed eligibility here is a synthetic trusted-time/Covered case;
mixed also excludes the prior morning/night room/time regions. Unlike the old
random source-kind1/3 mixture, these native-summary counts come from real episode
replay. It does not claim a measured arrival/time/fault envelope. The actual target's
86400s uncertainty would exclude **all** Motion from this candidate compaction;
production trusted time/coverage is a prerequisite, not supplied by this script.

|Fixture/profile|A and B fallback exact Hub inputs / modeled peak KiB|C retained exact (native included)|C new point summaries / represented Motion points|C backend representations|C modeled protected peak KiB|
|---|---|---:|---|---:|---:|
|NORMAL ordinary|1176 /308|462 (360 native)|442 /714|904|244|
|NORMAL mixed|1176 /308|645 (360 native)|329 /531|974|272|
|HIGH ordinary|5352 /1004|2478 (2160 native)|640 /2874|3118|624|
|HIGH mixed|5352 /1004|3201 (2160 native)|482 /2151|3683|728|
|STRESS literal45s ordinary|10476 /1856|5544 (4938 native)|850 /4932|6394|1176|
|STRESS literal45s mixed|10476 /1856|6779 (4938 native)|636 /3697|7415|1352|
|PAIRED46 ordinary|68220 /11456|34416 (33810 native)|3572 /33804|37988|6548|
|Working40s ordinary|3264 /652|1650 (1620 native)|278 /1614|1928|448|
|Working80s ordinary|6504 /1196|30 (0 native)|438 /6474|468|264|
|Working120s ordinary|4344 /832|30 (0 native)|340 /4314|370|220|

Hub exact **ingestion** still has all A inputs before C compaction; retained-exact
counts above are after consumer checkpoint and selected summary. C does not
reduce Node persistence/transmissions or initial Hub durable commits; COW/summary
writes can add work while reducing retained bytes/cloud object multiplicity.
Backend point effects/claims still account for all represented input membership;
904 representations are not904 observed points. Four day states and all inherited
384 witnesses/report/COW/staging/critical/progress owners are charged, not magically
freed by fewer source records.103-byte exact fallback,1434-byte full context,
128-input staging,32-HOT serial admission and32 critical alternative are inherited
model parameters, not newly approved formats/quota. No reduction factor is chosen.

### 128 / 192 / 256 KiB

Only changed source-derived C fixtures use the existing SDK runner/binary.
15 capacity/update/reclaim/remount cases: **1 PASS,14 expected capacity stops**.
NORMAL ordinary passes256 KiB (27 history/8 staging extents,1176 arrivals), peak63
physical pages =258048 B, one erased page for internal GC. NORMAL mixed and
HIGH/STRESS stop at all three reviewed sizes. No new full72h schedule, fault/GC
campaign or target wear run is needed or claimed; previous fault evidence is
preserved but does not qualify new Node/progress transactions.

- 128 KiB: no changed worst-size C fixture fits; no Node reduction demonstrated.
- 192 KiB: no changed worst-size C fixture fits; old typical NORMAL passes remain
  valid only for their narrower original inputs.
- 256 KiB: source-derived ordinary NORMAL has a passing operation witness, mixed
  NORMAL/HIGH/STRESS do not. No supported-volume/physical admission guard or general
 72h guarantee is closed. A/B fallback worst-size NORMAL itself exceeds256 KiB.

Passing peak consumes all but internal free page; it is not application workspace
proof. Retain NVS candidate/raw fallback and4MB Hub. No layout selection is made.
Prior current-image OTA margins101456 B at128 KiB and35920 B limiting margin at
192/256 KiB are preserved build evidence, not new integration-growth measurements.

## Required changes, RAM and battery impact

Node later needs versioned linked episode/progress meaning, compact recoverable
point/last-motion state, immutable export cursor, bounded exact fallback and loss
markers, protected queue/admission/report handling, and progress/quiet deadlines
included in the existing sleep scheduler. Current event origin/retry/retirement
identity must survive. Hub later needs authenticated versioned decoding, point
dedupe/cursor, consumer/coverage/time checkpointing, eligibility contract and
display/history aggregation separate from live rule inputs. Retain household
learning at Hub; no competing per-Node model is proposed.

Backend later needs episode/revision/point membership, exact-submission fence,
exclusive representation claims, atomic history/derived-effect completion, gap/
fidelity/time flags and stable backfill/day revision receipts. Existing native
MotionSummary exact API is insufficient. PWA should display a meaningful episode
with observation fidelity/gaps and stale state; it must not show continuous
presence, sleep or a named person's identity from PIR/bed alone. No changes made.

RAM planning example, **not a codec or target allocation**: proposed104-byte
scalar owner state (IDs/version/time/cursors/quality),32 bounded16-byte points
(ordinal4,monotonic8,quality2,reserved2)=512 B, one512-byte immutable export work
buffer and644-byte authenticated snapshot encode workspace gives1772 B/Node,
before pending progress payloads, strings, NVS internals, crypto/task stacks and
alignment.32-point capacity is inherited as a sensitivity, not approved Node
episode policy. Snapshot bank flash, NVS page overhead, pending immutable payload
coexistence and no-heap hot path need measurement. New host ActivityEpisode sizeof
is152 B on this host ABI only; do not call it ESP32-C3 RAM usage. B exact fallback
changes no deployed RAM.

Hub existing candidate42749 B+NVS internals remains unmeasured. A proposed48-byte
episode/cursor/time/quality row×6=288 B plus one512-byte decoded-point workspace
adds800 B, yielding43549 B+internals **only as planning**. Shared existing workspace
reuse, strings, larger progress codec, runtime stacks and current heap headroom
are unresolved. No per72h-source RAM index or per-Node routine engine is added.

Battery: radio application sends/saves in the replay table establish opportunities,
not mAh or battery lifetime. Node grouping cannot remove the GPIO wake needed to
notice each valid detection. Longer ACTIVE must permit qualified low-input light
sleep; do not leave the radio awake until END. Current target at1535/1555/1599
uses episode next_deadline as maintenance wake, inhibits pending summary/recovery/
radio outage, and at411 enters IDF light sleep then restores Wi-Fi/ESP-NOW.
Production health remains120s with contact-based deferral. New progress adds
deadlines/RF/ACK and durable state writes; making today's RAM repeats recoverable
can **increase** energy. It might save full recovery saves/ACK work for frequent
separate ordinary events with a compact point journal, but no net physical saving
or acceptable maximum overhead is proved. Do not promise an improvement.

BAT-C8 impact: any later episode/state/progress/sleep integration can invalidate
the sensing/restoration/deadline/event-processing portion of GS-D020 and requires
focused host deadline/retry/corruption tests, target size/heap/wake budget and then
separately authorized physical sensing/GPIO/timer/radio/fail-awake qualification.
Keep existing BAT-C8 files/status unchanged; do not reopen unrelated passed
fresh-install gates without an actual invalidating change. No physical energy or
wake results are fabricated; final battery/endurance optimization remains separate.

## Governance action and open blockers

Required next **explicitly authorized canonical governance task**, on
`/home/udaybhan/projects/Ghar_sajag_r1@feature/r1-commercial-baseline`:

1. Review/promote the already approved72 elapsed-hour internet-only outage and
   loss-aware eligible ordinary-motion direction into a new LOCKED decision
   (next available ID, currently GS-D025), preserving exact important evidence,
   local monitoring/learning/coverage, backfill, near-real-time connected sync and
   durable-before-ACK. Do not equate this direction with unlimited arrivals.
2. Partially supersede only the now-approved horizon/direction statements in
   GS-D013/017; keep supported exact/critical volume, saturation, loss/fidelity,
   coverage/time/lateness/revisions, quota and partition decisions OPEN where
   unresolved. Record backend policy's actual approved scope without inventing an
   API or locking the candidate32/128/W/C values. Node proposal remains PROPOSED.
3. Update Decision Log, R1 Work State, relevant storage/P0 requirements, project
   orientation and canonical index authority/traceability; increment context
   from2026-10-07.003 through the approved version scheme. Commit canonical
   documentation **before** dependent production implementation.
4. Bring consuming worktrees to the approved context only through a separately
   authorized nondestructive workflow; require preflight PASS again. This run
   neither edits the canonical source nor silently advances the local context.

Open product decisions: supported72h event/class envelope and finite critical
saturation; ordinary episode definition and tolerated detail/loss; progress/alert
latency and eligibility boundaries; sufficient statistics for learning; coverage
qualification and fault/gap visibility; clock/day/late correction and summary
backend contract; partition/OTA growth reserve. No fixed quiet gap is recommended.

Open technical blockers: full durable Node episode/point/cursor schema and reset
gap handling; timely cross-sensor eligibility/progress; original retry digest/
conflict projection; authenticated Hub admission/report/root/nonce/reclaim and
protected next-operation NVS workspace; full reducer/time/coverage/day recovery;
backend exclusive membership/effect/revision completion;32-slot/point bounds;
target RAM/OTA/wear and relevant BAT-C8 physical qualification. No production
correctness or battery proof is closed by this investigation.

## Validation and reproducibility

New files are isolated under `P/host/storage/`; they are not added to target
sources or production build lists. Tests are focused behavioral counterexamples,
not a new implementation copied into tests. Logs retain exact commands/exits and
SHA256 for source, binary, replay CSV and derived cases:

- [Host compile, counterexamples, seven replays and ledgers](R1_NODE_MOTION_HOST_20261008.log): PASS.
- [Scoped ASan+UBSan](R1_NODE_MOTION_SANITIZERS_20261008.log): PASS, replay byte-identical; LeakSanitizer disabled.
- [New SDK NVS capacity fixtures](R1_NODE_MOTION_NVS_20261008.log): runner PASS;1 capacity witness/14 expected stops. No new SDK build or fault campaign.

Reproduce from `P/` using the compile command in the host log, then:

```sh
/tmp/gs-node-motion-audit /tmp/gs-node-motion-events.csv
python3 host/storage/node_motion_capacity.py --events /tmp/gs-node-motion-events.csv --cases /tmp/gs-node-motion-cases.json
LD_LIBRARY_PATH=/tmp/gs-ruby/usr/lib/x86_64-linux-gnu:/tmp/gs-libbsd-dev/usr/lib/x86_64-linux-gnu python3 host/storage/nvs_runtime_probe/run_offline.py --cases /tmp/gs-node-motion-cases.json --suite capacity
```

Reuse the probe README's prepared environment if staged paths differ. The CSV
is deterministic temporary input/output, not a hardware trace; its hash and all
counts are preserved in the log. SDK runner removes only its own completed
temporary emulator files. Do not rerun proven hardware/qualification or old broad
regressions for these isolated additions. After this focused host-only commit,
**STOP**. Recommended next action is governance and semantic decision review,
followed by a separately scoped persisted progress/equivalence proof; no production
integration, partition CSV, BAT-C8, backend/PWA or context version changes here.
