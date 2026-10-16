# GS-144 R1 battery workload and endurance model — 2026-10-12

## Status and source boundary

**Software checkpoint: PROPOSED, not product accepted.** GS-144 remains In
Progress. Jira comment 10511 records the authorized scope. This independent
branch starts at requested source commit
`9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33` (`feature/r1-commercial-baseline`)
in `/tmp/gs144_battery_workload`, branch
`gs144-workload-qualification`. The canonical GS-148 worktree, its untracked
managed components, and physical evidence were not changed. No board, USB,
UART, flash, current meter, or battery was accessed.

Implementation checkpoint commit
`9af8c4f97c3db2314075ce62be5b95cb34fab923` was pushed to the actual GitHub
branch `gs144-workload-qualification`; `git ls-remote` matched that commit at
verification. The shared source clone initially inherited a local filesystem
`origin`; the first push created a local branch ref in the canonical
repository's Git metadata. That ref points to this commit and did not move the
active `feature/r1-commercial-baseline` branch or alter working files. I left
the ref intact. The GitHub remote was added explicitly and is the delivery
target. The canonical active HEAD remained
`9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33`; its pre-existing untracked GS-114
evidence and S3 managed components remain present.

The isolation branch is based on the last reported checkpoint. It must be
reviewed against the then-current canonical branch before integration because
canonical work continued concurrently. No merge or canonical update is implied.

## Current Node behavior audited

Audited production paths in
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/` and
`shared/include/gs/protocol.hpp`:

* ESP32-C3 samples AM312 GPIO4 from the single Node owner at a 20 ms awake
  polling interval. Startup settling is 10 seconds; qualified input uses
  150 ms debounce and a 1 second minimum retrigger interval. The first
  qualified observation enters the event path immediately.
* Ordinary motion episodes preserve a separate first event. Repeats are
  summarized after 45 seconds quiet, capped at 300 seconds connected; outage
  coalescing waits for 1,800 seconds idle. Only ordinary motion compacts.
  New critical event kinds retain priority and do not use motion compaction.
* Production NodeHealth uses the validated `config/node_health.json` interval
  of 300 seconds, with event piggyback enabled. The current offline threshold
  is `3 × 300 + 10 = 910 seconds`; do not substitute historical BAT-C5
  120/310-second assumptions. Due application work wins; pending work, outage
  and maintenance suppress routine health.
* `NodeRadio` retries at 200/600/1,800/10,000/60,000 ms with deterministic
  EventKey jitter up to 100 ms. Confirmed outage uses the existing 60-second
  rung and one global radio opportunity gate. Hub return makes retained events
  eligible without changing EventKey or original occurrence time. Durable ACK
  is required to retire an event; MAC success and volatile receipt do not.
* `gs_node_owner` calls `evaluate_light_sleep`; `PowerPolicy::evaluate` is not
  the authoritative sleep decision. Light sleep caps each interval at 30 s,
  observes the earliest health/retry/security/maintenance deadline, keeps
  GPIO4 armed and fails awake on unknown state, unsafe PIR, pending work,
  FOTA/control, unsettled persistence, active connected ACK reception, or
  other inhibitors. Wi-Fi/ESP-NOW are stopped and restored around sleep.
* GS-150's source-derived best-effort application receive opportunity is 10 s
  after local callback completion or its existing timeout for the eligible
  confirmed-outage case; a successful application MAC callback with a pending
  event keeps RX available. This is not an ACK-validity expiry, delivery SLA,
  or retirement signal. Exact-key retry and authenticated Hub dedupe remain
  the recovery path. Health/retirement exchanges use the existing 300 ms
  receive envelope. Session recovery remains on its existing policy.
* Low-battery voltage classification code exists, but no calibrated battery
  sample is wired into the C3 runtime. Unknown/uncalibrated input cannot be
  treated as a power-saving mode. OTA/control/boot-health maintenance remains
  a sleep inhibitor.
* The target now derives `awake_ms` from monotonic uptime minus accumulated
  light-sleep residence. It still has no production updates to `radio_tx_ms`
  or `radio_rx_ms`, and recovery-write diagnostics do not represent a complete
  flash write/erase count. These software counters do not establish current,
  energy, RF airtime, or lifetime.

The production behavior above is the starting point, not an accepted workload
specification. Historical values in older power-plan sections do not override
the current JSON policy or GS-D031.

## Reproducible proposed workload inputs

Machine-readable inputs are in
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/data/gs144_workloads.json`.
The scenario schedule values below are assumptions for product review, not
claims about household behavior. Each profile represents one device. One
episode emits one immediate first-motion event; if repeats occur, this source's
current episode policy emits one coalesced MotionSummary after closure. Event
durability and ACK semantics remain those of production code.

| Scenario | Proposed schedule | Coalescing / traffic assumptions | Offline, queue and freshness assumptions |
|---|---|---|---|
| Quiet household, 24 h | 12 episodes/day; 3 PIR observations/episode | 24 business events/day; 276 standalone health and 12 events suppressing an otherwise due health; 300 total TX windows in supplied model | Online, pending peak 1; ordinary event remains on current prompt-send policy |
| Typical household, 24 h | 72 episodes/day; 4 observations/episode | 144 business events/day; 30 retry attempts; 216 standalone health; current episode summary behavior applied | Online; assumed peak pending 3; original event/ACK behavior unchanged |
| Active household, 24 h | 216 episodes/day; 6 observations/episode | 432 business events/day; 108 retry attempts; 72 standalone health; supplied TX count includes these health frames | Online; assumed peak pending 8 |
| Nighttime quiet, 8 h | 0 PIR episodes for a continuous 8-hour segment | 96 health opportunities at 300 seconds; no event piggyback | No sleep behavior is inferred beyond source eligibility; proposed freshness remains governed by the 910-second derived offline threshold |
| Short Hub absence, 15 min plus 90 s recovery tail | 1 outage episode, 12 observations | 1 immediate first event remains pending during outage; after 45 s connected quiet it emits one summary; 15 outage/recovery retry attempts total; 8 estimated rejoin procedures after the 430 s contact timeout | Peak pending 1; this span ends before the 910 s offline threshold by 10 s; no new caregiver recovery SLA |
| Extended Hub outage, 8 h | 4 episodes spaced 2 h apart, 16 observations | 8 first/summary events; 480 event/health transmission opportunities (8 initial plus 472 retry attempts at the global 60 s outage gate); about 477 rejoin procedures after 430 s contact expiry using the current retry ramp to 60 s | Peak pending 8, below the current 32-record limit; 8 admission writes within the outage, eventual ACK retirements are outside the 8 h outage window; not an approved retention target |
| Intermittent poor RF, 24 h | Typical household event schedule | 144 business events; 150 assumed retries; six assumed rejoin attempts; 216 standalone health | Assumed peak pending 4. RF loss fractions and windows require fixture measurement and product review |
| Battery-low operation, 24 h | Typical schedule under an uncalibrated/unknown reading | Same event, health and retry assumptions as typical; **no** reduced service or altered retries are assumed | Exercises unknown battery state without suppressing first motion, critical events, ACK, recovery, or caregiver truth |
| OTA/control readiness, 24 h | Quiet household plus two control/maintenance exchanges | 24 business events; 276 standalone health; 2 additional TX/RX exchanges; 50 assumed flash writes | Maintenance and active FOTA/control inhibit sleep; 1 pending peak; ready-to-start does not assert OTA is applied |

The JSON's `radio_tx_attempts`, weighted `rx_window_ms`, `awake_seconds`,
retry/rejoin counts, pending peaks, flash writes and current values are explicit
proposed inputs. Event/health TX counts do not include the multiple wire
frames that may occur inside a rejoin procedure; rejoin procedure count is a
separate counter. The extended-outage estimate follows the 430-second
no-contact timeout and bounded ramp to a 60-second retry, but the exact count
is schedule-dependent and still needs source-integrated simulation. They are
not generated by the C++ test for every household
profile. Business-event counts and outage retry/ACK invariants are separately
exercised against production `ActivityEpisode`, `NodeHealthCadence`, and
`NodeRadio` classes. Radio durations, health counts, 24-hour scheduling, FOTA,
PIR electrical behavior, and physical queue persistence remain model
assumptions or existing focused-test coverage; the model does not reproduce
ESP-NOW or the ESP-IDF task scheduler. The current model's 10-second receive
budget is deliberately visible as workload input, not a measured radio-on
duration.

## Capacity and average-current envelope

For nominal capacity `C`, usable fraction `u`, reserve fraction `r`, and target
days `d`:

```text
usable budget (mAh) = C × u × (1 − r)
required whole-device average current (mA) = usable budget / (24 × d)
estimated days = usable budget / (measured average current × 24)
```

With the user-stated nominal 2,900 mAh reference, full nominal capacity and no
reserve require at most **0.806 mA for 150 days** or **0.671 mA for 180 days**.
At 80% usable with no reserve, the envelope is **0.644 mA / 0.537 mA**. At the
model's illustrative 80% usable and 10% reserve, the envelope is **0.580 mA /
0.483 mA**. A 70% usable, 10% reserve case gives **0.508 mA / 0.423 mA**;
90% usable, 5% reserve gives **0.689 mA / 0.574 mA**. Capacity, reserve,
temperature, age and cutoff remain unverified inputs.

The configurable model separates battery-side light-sleep base current,
awake base current, continuous PIR current, regulator/board leakage, TX and RX
increments, and flash-write charge. Awake time includes CPU active work; TX/RX
increments are layered on the awake base; PIR and leakage apply continuously.
The illustrative values in the JSON (including 0.12 mA sleep, 35 mA awake,
80/55 mA TX/RX increments and flash pulse charge) are **not measured or
selected device values**. Replace them with same-boundary instrument results.
The sample per-profile lifetime output is sensitivity arithmetic only and
must not be quoted as a product estimate. A software transmission counter or
modeled radio duty fraction cannot replace whole-device current integration.

At the example 2,088 mAh usable budget, current sensitivity is:

| Whole-device average current | Arithmetic runtime |
|---:|---:|
| 0.25 mA | 348 days |
| 0.50 mA | 174 days |
| 0.58 mA | 150 days |
| 0.75 mA | 116 days |
| 1.00 mA | 87 days |

These figures are direct capacity/current arithmetic, not predicted Node
performance. At 2,900 mAh, varying usable fraction 70–90% and reserve 5–15% moves the
required 150-day whole-device current from **0.479 to 0.689 mA** and the
180-day current from **0.399 to 0.574 mA**. This range alone is wide enough
that cell, cutoff and power-path verification are material to the result.
The measurement report should use lower-confidence usable capacity and
upper-confidence average current; combine instrument, run-to-run and capacity
uncertainty before comparing to the target. Product must approve the actual
reserve/uncertainty policy.

## Deterministic software simulation and outputs

New runner and registrations:

```text
make gs144-workload-host-test
python3 tools/validation/component_gate.py --suite node --list
```

Final focused run: exit 0. The command passed the C++ production-component
workload checks (quiet/typical/active episode compaction, business-event first
transmissions, retained outage EventKey retry, MAC/volatile ACK
non-retirement, durable ACK retirement, 300-second health piggyback and due
work/outage/maintenance suppression):

```text
GS144 WORKLOAD SIM PASS scenarios=5 checks=2431
Ran 4 tests ... OK
```

The Python runner emits nine workload summaries, sleep/awake residence,
business/health counts, assumed TX/RX/retry/rejoin/flash counts, modeled
average current and runtime sensitivity. All output is labeled
`PROPOSED_ENGINEERING_MODEL_NOT_MEASURED`; output does not claim production RF,
physical mA or battery-life evidence. Final exact test commands and exits are
recorded in the delivery comment/evidence update.

The component stage `gs144-workloads` is permanently registered in
`tools/validation/suites.json` under Node and lists the scenario inputs and
runner source. The regression also remains separately invocable. No component
production policy or event semantics changed.

Validation executed (all final listed commands exited 0):

| Command | Result |
|---|---|
| `make gs144-workload-host-test` | C++ 2,425 checks across 5 grouped scenarios; Python model 4/4; JSON model report emitted |
| `make battery-c8-host-test` | BAT-C8 C++ 72 checks; Python battery invariants 11/11 |
| `make gs150-host-test` | 1,481 checks; 19 paired software workload cases printed |
| `make gs40-host-test` | 1,320 checks; quiet/night/normal/outage/recovery cases printed |
| `make lab-build` then `make gs40-config-test` | Simulator dependency built; NodeHealth configuration/backend/PWA suite 15/15 |
| `make rejoin-host-test` | `P2-REJOIN-HOST PASS` |
| `make node-recovery-host-test` | `P2-NODE-RECOVERY HOST PASS` |
| `make node-recovery-persistence-host-test` | `P2-PERSIST-NODE-RECOVERY HOST PASS` |
| `make node-retirement-protocol-host-test` | `NODE RETIREMENT PROTOCOL HOST PASS` |
| `make secure-fota-adapter-host-test` | Secure FOTA S3 adapter and hash checks PASS |
| `make fota-host-test` | 34/34 checks PASS |
| `make validation-framework-test` | 39/39 framework checks; nonzero failure propagation and test registration coverage PASS |
| `make feature-coverage-test` | Traceability consistency 152 features / 204 source modules / 14 physical cases; 19/19 traceability tests PASS |
| `python3 tools/validation/component_gate.py --suite node --list` | New `gs144-workloads` stage is selected in Node and therefore fast/release compositions; full Node aggregate deliberately not run |
| `git diff --check` and JSON parsing of both new configs | PASS |

Resolved validation setup issues: the initial C++
compile exposed a GCC `-Wmaybe-uninitialized` false positive for the optional
episode summary with the test TU optimized at O2, so only this harness TU now
uses O0 while production objects keep O2. The first GS-40 config run lacked the
interactive simulator executable expected by its tests; `make lab-build` then
enabled a clean 15/15 rerun. A first traceability check also caught an invalid
requirement reference and test-source prefix in the new matrix row; those were
corrected and final traceability passed. A new outage-sleep case also exposed
stale owner-loop fields in the test fixture; rebuilding the observation
between simulated owner iterations made the harness follow the actual
single-owner snapshot contract, and the final workload rerun passed. No test
assertion was weakened.

No full `validation-node`, `validation-fast`, product release gate, target
build, physical run, or current measurement was performed. The first attempt
at the aggregate command chain stopped on the missing simulator executable;
the final isolated relevant Node regressions above passed after building that
required local harness.

## Proposed acceptance for product review

* Preferred objective: **180 days** at the product-approved representative
  household/RF workload. Keep 150–180 days an aspirational product goal until
  actual cell/power path and matched BAT-C8 data support a claim.
* Proposed minimum for review: **150 days** using an approved representative
  workload, measured at the whole Node battery boundary and evaluated with
  approved capacity, reserve and uncertainty. This is not user-approved and
  must not be treated as an acceptance threshold yet.
* No allowed compromise to first real PIR observation, critical-event
  priority/delivery, immutable EventKey/original time, authenticated durable
  ACK, retry/rejoin, FOTA recovery, truthful coverage or caregiver freshness.
  Numeric application latency/reliability SLAs are not present in the sources
  reviewed; compare against the frozen current behavior and obtain a product
  decision before setting numeric limits.
* For BAT-C8 comparison, recommend paired active/C8 runs on the same board,
  battery/power path, Hub, channel, TX setting, PIR and workload. P10 must show
  a current/energy reduction greater than combined uncertainty without
  reliability or latency regression. GS-149 owns that conclusion after GS-51.
* A measured multi-day average supports an endurance estimate; it does not
  prove a full 150–180-day discharge result. Report estimate, uncertainty,
  full-cycle status and product approval separately.

### Measurement prerequisites and ticket mapping

| Work | GS-144 relationship / required evidence |
|---|---|
| GS-110 / GS-115 | Parent optimization epic; C9–C11 decisions remain measurement-led; BAT-C12 deep sleep remains explicitly deferred. Do not implement from this estimate. |
| GS-114 | Owns BAT-C8 physical functional P1–P9. Current work-state blocks fixture retest due to reset-safe observation and Hub replay-fence issues. This software workload does not satisfy it. |
| GS-40 | 300 s NodeHealth / 910 s offline semantics are the current policy input. Physical quiet-node visibility remains open. |
| GS-150 | Supplies the bounded outage receive/retry/rejoin software behavior to represent. Does not set a new product outage SLA. |
| GS-140 | Must freeze safe current instrument, measurement boundary, sample method, burden and uncertainty before battery measurement. |
| GS-41, GS-42, GS-141, GS-43 | Own B1 idle, B2 NodeHealth, B3 real PIR, and B4 Hub outage/recovery BEFORE baselines. Keep exact workload/image/setup provenance. |
| GS-51 | Owns matched AFTER measurements with the same boundary, configurations and workload as BEFORE. |
| GS-149 | Owns C8-specific P10 average-current assessment; blocked on approved GS-144 target/workload plus GS-140/B0–B4 and GS-51. It must use measured values, not these model counters. |
| GS-116 / GS-130 | New deterministic test is Node-registered here. Software simulation does not clear physical-class work or release status. |

For physical capture: verify the actual selected 18650 make/model, measured
usable capacity at the Node's real cutoff, charger/protection/regulator path,
board/PIR rail boundary and fixture identity. Use a power analyzer/current
logger with documented sample rate/bandwidth for short ESP-NOW pulses; record
burden/shunt and calibration. Integrate battery-side current and voltage over
the same schedules in the paired BEFORE/AFTER arms. Capture real AM312 motion,
Node/Hub timestamps, durable ACKs, EventKeys, RSSI, retries, radio/session
recovery and pending counts. Repeat runs, retain raw traces and compute
uncertainty. Reuse the existing GS-140/41/42/43/141/51/114/149 procedures and
qualified fixtures; do not create a second HIL framework.

No hardware measurement, fixture approval, selected production cell, reserve
decision, accepted workload, approved minimum duration, numeric event SLA, or
GS-149 pass is present in this checkpoint. Software optimization is sufficient
to proceed to instrument/workload review and then authorized baseline
measurement; further C9–C12 software work is not justified by this model.

## Validation and limits

Relevant validation commands are recorded after closeout in this file and
Jira. Scope excludes full release, Hub/backend/PWA, new storage/cloud work,
production sleep-policy changes and all physical access. This evidence does not
change GS-148, GS-114 or GS-152 workflow state, does not approve the workload,
and does not close GS-144. The next product decision is acceptance of the
representative scenario, usable-capacity/reserve assumptions, preferred target,
proposed 150-day minimum, and any numeric caregiver latency/reliability bound.
