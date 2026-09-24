# HW-M1.4 Post-Resilience Master Forward Roadmap

This is the authoritative forward roadmap after HW-M1.4A. A future engineer
or Codex session should read this file together with
`docs/progress/CURRENT_BASELINE.md` and the current milestone plan without
requiring prior chat history.

For the current Phase-2 branch status and priorities, use
`docs/progress/CURRENT_STATUS_AND_ROADMAP.md`. The older resume branch, commit
and physically qualified pair in the historical resume contract below describe
the 2026-09-21 HW-M1.4 planning checkpoint; they are not the current Phase-2
repository or firmware provenance.

## Resume contract

- **Resume branch:** `fix/hw-m1-4-node-offline-resilience`
- **Master-roadmap planning parent commit:**
  `aef3f63b4d99257c98810e5f8297e4cd630124c1`
- **Physically qualified Hub+C3 pair:**
  `bb34f5eb796d4975c7e8ab788ca638d9828a3996`
- **HW-M1.4 offline-resilience runtime implementation:**
  `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9`
- **Current milestone:** HW-M1.4B — Minimal Pre-Optimization Power Baseline,
  **PLANNED / READY TO START**.
- **Immediate action:** perform B0 measurement-path verification, then the
  repeatable B1–B4 BEFORE workload baseline.
- **C1 start condition:** after B0 and B1–B4 are captured, HW-M1.4C1 may
  start immediately. Full prototype-shield characterization is not a C1
  software start gate.

The Robocraze TIFC00389 shield was the prototype/test-fixture power source
used for HW-M1.4A. It is not selected or frozen commercial Ghar Sajag power
hardware, a software dependency, or the basis for hard-coded thresholds. The
commercial product may use a different battery, protection, charger,
regulator/PMIC, or power-path architecture.

## Roadmap revision history

- **2026-09-21 — HW-M1.4A closure roadmap established:** the initial
  post-resilience roadmap recorded HW-M1.4A as QUALIFIED / PASS, carried the
  Robocraze TIFC00389 prototype-fixture boundary and unresolved low-voltage
  endpoint question forward, and identified broad HW-M1.4B, C, and D follow-up
  work.
- **2026-09-21 — HW-M1.4B planning refined:** the broad characterization intent
  was narrowed to the minimal B0 measurement-path verification plus B1–B4
  repeatable BEFORE baseline required before C1 software work. Full prototype
  shield cutoff, efficiency, and commercial power characterization were
  separated from the C1 start dependency as HW-PWR-PROT and HW-PWR-COMM work.
- **2026-09-21 — Master roadmap expanded:** C1/C2/D/E/F/G/H sequencing,
  BLE feasibility, event chronology and routine-learning dependencies,
  retained-state requirements, acceptance boundaries, and evidence locations
  were added while preserving the earlier A/B/C/D decisions.

## Master milestone matrix

| ID / title | Status | Dependency / sequence | Purpose and implementation intent | Acceptance criterion | Evidence location |
|---|---|---|---|---|---|
| **HW-M1.4A — Physical resilience/endurance** | QUALIFIED / PASS | Complete | Confirm offline operation and physical endurance of the qualified pair. | Final health is healthy; accepted motion is durably acknowledged; no qualified drops/rejections/backlog/unexpected reset; endpoint is documented with bounded claims. | `docs/hw/evidence/HW_M1_4A_ENDURANCE/README.md` |
| **HW-M1.4B — Minimal pre-optimization power baseline** | READY TO START | After A; before C1 | Capture repeatable software BEFORE values using prototype hardware as a fixture. | B0 plus repeatable B1–B4 current/workload records and instrumentation limits. | `docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md`; future B0–B4 evidence under `docs/hw/evidence/` |
| **HW-M1.4C1 — Automatic light sleep** | PLANNED | After B0 + B1–B4; no HW-PWR-PROT dependency | Replace continuous active polling with automatic light sleep while keeping the AM312 powered and event semantics safe. | Same B1–B4 workloads show measured improvement without critical-event loss, unacceptable latency, chronology errors, or resilience regression. | Future `docs/hw/evidence/HW_M1_4C1_*` record and implementation history |
| **HW-M1.4C2 — GPIO4 event wake and adaptive policy** | PLANNED | After C1 and measurement | Wake on GPIO4 PIR event; transmit first motion immediately; coalesce ordinary repeats; adapt health and Hub-offline backoff. | Wake/event behavior, chronology, critical-event priority, outage retry and power improvement are measured and qualified. | Future `docs/hw/evidence/HW_M1_4C2_*` record |
| **HW-M1.4C3 — Deep sleep / RTC retained state** | DEFERRED | After C1/C2 semantics and retained-state design | Reduce sleep energy while preserving identity, sequence, pending-event, configuration, FOTA, and offline semantics. | Recovery tests preserve state and critical events across reset/brownout/power interruption as specified. | Future C3 design and target-recovery evidence under `docs/hw/evidence/` |
| **HW-M1.4D — Battery telemetry + energy model** | PLANNED | After suitable battery/power-path measurement; can overlap later firmware work | Expose generic battery/power state and calibrated activity-aware energy estimates. | Calibrated raw battery measurement and model validation across representative discharge/workloads; no voltage-only SOC claim. | Future HW-M1.4D telemetry/calibration evidence |
| **HW-M1.4E — Engineering / installer observability** | PLANNED | Requires diagnostic contracts and transport/backend path | Provide structured commissioning and engineering diagnostics separate from caregiver UX. | Installer can inspect live flow, identity, RF, ACK/retry, queue, health, power, and routine-learning state from structured diagnostics. | Future engineering diagnostic contract/UI evidence |
| **HW-M1.4F — RF / Wi-Fi / backend coexistence** | PLANNED | Requires Hub Wi-Fi/transport composition and controlled RF setup | Validate ESP-NOW with Wi-Fi STA, WAN outage/reconnect, replay, idempotency, and later multi-node behavior. | Controlled channel/provisioning/reconnect/RF/cloud tests preserve event identity, durable ACK, journal/outbox, replay, and idempotency. | Future coexistence/HIL and Hub-backend evidence |
| **HW-M1.4G — FOTA / maintenance / security closure** | PLANNED | After C1/C2 changes; security architecture review | Requalify maintenance and update behavior across low-power/offline states and close production security gaps. | FOTA regression, interruption, restart, rollback, recovery, post-update event processing, authenticated/signed policy as applicable. | Existing FOTA evidence plus future `HW_M1_4G` evidence |
| **HW-M1.4H — Extended reliability / soak** | PLANNED | After optimized firmware stabilizes | Run long, realistic workload, outage, restart, resource, battery, wake, and maintenance campaigns. | Explicit duration/workload/resource/recovery criteria pass for 12 h, 24 h, 72 h, and applicable long-soak runs. | Future `docs/hw/evidence/HW_M1_4H_*` records |
| **HW-PWR-PROT — Prototype power-path characterization** | DEFERRED / PARALLEL | Optional; independent of C1 start | Characterize Robocraze fixture behavior: quiescent current, efficiency, outputs, cutoff/recovery, charger reset. | Repeatable prototype measurements with safety and wiring limits documented. | Future prototype hardware evidence; not an HW-M1.4B/C1 gate |
| **HW-PWR-COMM — Commercial power architecture qualification** | DEFERRED | After production hardware selection | Qualify battery, charging, protection, PMIC/regulator, efficiency, thermal, lifecycle, safety, enclosure, supply. | Selected production architecture passes electrical, thermal, safety, lifecycle, and supplier/availability criteria. | Future commercial hardware qualification record |
| **P0-SW-R0 — Event chronology & episode semantics** | PLANNED / REQUIRED FOUNDATION | Before routine-learning implementation depends on it; informs C1 | Define identity, occurrence chronology, aggregation, duplicate/replay, ordering, conflicts, and reset boundaries. | Deterministic tests and HIL/replay evidence prove correct chronology and episode aggregation under duplicate/out-of-order/restart cases. | Future software contract/tests and chronology evidence |
| **P0-SW-R1 — Activity episodes / chronology foundation** | PLANNED | After R0; can align with C1 | Implement stable episode representation and occurrence-time projections. | Episode first/last/count and event identity remain correct across arrival order, replay, and session boundaries. | Future software contract/test evidence |
| **P0-SW-R2 — Personalized routine baseline** | PLANNED | After R1 and sufficient trusted history | Build a transparent per-node/zone activity baseline. | Baseline uses occurrence chronology, excludes invalid/replayed data, and has explicit cold-start/coverage rules. | Future routine-learning evidence |
| **P0-SW-R3 — Short-term deviation detection** | PLANNED | After R2 | Detect explainable short-term deviations without treating missing data as behavior. | Deterministic windows, confidence/coverage rules, and false-positive/unknown outcomes are evidenced. | Future detection tests/evidence |
| **P0-SW-R4 — Longitudinal trend detection** | PLANNED | After R3 and longer qualified history | Detect longer-term changes with explainable data sufficiency. | Trend result is reproducible, chronology-correct, confidence-qualified, and does not make medical claims. | Future trend evidence |
| **P0-SW-R5 — Explainable caregiver insights** | PLANNED | After R4, UX/safety review | Present evidence-backed insights through approved caregiver semantics. | Every insight links to source evidence/time window/confidence and preserves care/safety boundaries. | Future product/UX qualification evidence |
| **HW-EXP-BLE — BLE transport feasibility** | EXPERIMENT | After optimized ESP-NOW baseline exists | Compare BLE transport feasibility without replacing NodeRuntime/ACK/dedupe semantics prematurely. | Measured comparison covers idle/sleep, wake/event energy, latency, loss, range, reconnect, coexistence, OTA, multi-node, and complexity. | Future experiment record; no BLE selection implied |

## HW-M1.4B minimal BEFORE baseline

The authoritative detailed plan is
`docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md`. The mandatory sequence is:

- **B0 — measurement-path verification:** identify a safe current-measurement
  boundary and record boundary supply, C3 supply, C3 3V3, PIR VCC, polarity,
  and any easily visible shield output. Full Robocraze topology is optional.
- **B1 — idle/no intentional motion:** C3 and PIR operating normally, Hub
  online, current `bb34f5e` behavior, defined average-current interval.
- **B2 — normal/health activity:** include existing periodic NodeHealth
  behavior without changing its cadence and correlate current with logs.
- **B3 — controlled PIR workload:** defined event count and pacing; record
  accepted events, TX, ACK, failures, retries, average current, and RSSI/logs.
- **B4 — Hub offline/recovery:** short controlled outage, current,
  retry/backoff, retained/in-flight behavior, restoration, and recovery.

The purpose is BEFORE/AFTER comparison, regression detection, and quantitative
improvement measurement. After **B0 measurement-path verification and the B1–B4
baseline are captured**, HW-M1.4C1 may start immediately. Full shield cutoff,
recovery, efficiency, commercial selection, and battery-life qualification are
not required before C1. No software task is blocked by unavailable prototype
shield specifications; only direct hardware-interface work is conditional when
the required electrical signal does not yet exist.

## HW-M1.4C1 automatic light-sleep contract

The first software increment should reduce unnecessary active/radio time while
preserving local sensing and event semantics:

- replace continuous approximately 20-ms sensing/runtime polling as the
  normal operating model where technically feasible;
- keep the AM312 powered and sensing while the C3 sleeps, where the selected
  hardware power path permits it;
- implement automatic LIGHT SLEEP first, preserving AM312 sensing;
- keep local sensing independent of Hub availability;
- defer GPIO4 wake, aggregation, health and outage retry refinements to C2;
- reduce unnecessary production LED/debug activity.

Do not lower ESP-NOW TX power during C1 without RF-margin validation.

## HW-M1.4C2 GPIO4 event-wake and adaptive-policy contract

GPIO4 is the intended PIR event/wake source. Keep the AM312 continuously
powered while the C3 CPU/radio sleep when idle. A PIR event wakes the C3 for
processing and required communication; do not wake every ten seconds just to
poll PIR. The first meaningful motion is sent immediately. Then aggregate
ordinary PIR repeats over an initially measured 30–60 second window, tracking
`first_time`, `last_time`, and `count` per Node/room. Keep PIR debounce and
retrigger semantics separate from the longer aggregation window.

The 60-second NodeHealth interval is HIL/debug-oriented, not production power
policy. Healthy Nodes should report less often and piggyback health where
practical; report faster temporarily for faults, low battery, commissioning,
recovery or diagnostics. Hub-offline retry uses bounded short attempts,
progressive backoff and low-frequency probes during long outages, while local
sensing continues and ordinary PIR repeats coalesce. Evaluate dynamic ESP-NOW
TX power using measured RSSI, ACK/loss and retry margin; do not hard-code a
lower value before RF qualification.

### Motion activity-episode semantics

Do not delay the first normal motion event for batching. The planned contract
is:

1. report the first meaningful event promptly;
2. open a candidate activity window, initially perhaps 30–60 seconds;
3. during the window, update local `first_time`, `last_time`, `count`, and
   zone/node identity rather than sending a packet for every ordinary motion;
4. keep the exact window tunable from measurement, not permanently fixed by
   this roadmap.

**COALESCIBLE:** ordinary PIR room activity.

**NON-COALESCIBLE / IMMEDIATE:** emergency/Call Family, safety/tamper,
critical alerts, door state changes where individual open/close chronology
matters, and any explicitly loss-intolerant event. Different semantic events
must not be merged merely to save radio energy.

Acceptance requires prompt first activity, reduced repeated-PIR radio traffic,
correct episode first/last/count, and no delay or loss of critical events.

This remains a product/energy roadmap decision, not current runtime behavior.
Represent the proposed episode with `first_time`, `last_time`, and `count`;
preserve Node/zone identity. Emergency/SOS, security-relevant door chronology,
tamper, serious fault and other designated critical events are never batched.

### P0-SW-R0 — Event Chronology & Episode Semantics

Backlog recovery can deliver packets in an order different from occurrence
order. Hub, backend, and routine learning must not assume
`receive_order == occurrence_order`. Each event or aggregate must preserve
`node_id`, boot/session identity, sequence number, and local occurrence time;
receive time remains diagnostic metadata.

R0 must define duplicate detection, replay, out-of-order arrival,
occurrence-time ordering, receive-time storage, aggregation, conflict
handling, reset/session boundaries, and events that remain individually
persistent. Routine learning must use occurrence/event chronology, not blindly
Hub arrival order. R0 is required before routine-learning implementation
depends on these semantics. Acceptance is deterministic replay/HIL coverage
for duplicate, out-of-order, replayed, conflicting, session-reset, and
individually persistent events.

## HW-M1.4C3 retained-state and recovery requirements

Before deep sleep, explicitly design session semantics, sequence continuity,
pending critical events, first/last activity timestamps, activity count,
aggregation-window state, health/error breadcrumbs, Hub-offline state,
configuration, FOTA/maintenance state, and retained/persistent state. Avoid
NVS writes for every PIR trigger. Do not treat each deep-sleep wake as a
normal reboot without these semantics.

Deferred target-recovery qualification must cover reset, brownout, watchdog,
interrupted power, flash/NVS persistence, journal recovery, and pending
critical-event recovery. None of this is implemented or qualified now.

## HW-M1.4D battery telemetry and energy model

When hardware supports it, measure raw cell voltage from an appropriate point
before the node regulator/power converter. Use a suitably low-leakage
divider/switchable path so the measurement circuit does not materially waste
the battery.

Keep software hardware-independent with concepts such as `battery_mv`,
`battery_state`, `low_battery`, and `power_good` / `charging_state` only when
supported by selected hardware. Do not estimate SOC or lifetime from voltage
alone. A calibrated model may use voltage, awake/sleep duration, PIR count,
TX, retries, Hub-offline duration, NodeHealth, FOTA/maintenance, and runtime
states. A fuel gauge/coulomb counter remains an option if voltage/energy
calibration is inadequate.

Acceptance requires calibrated raw measurements, documented workload/model
inputs, discharge-curve calibration, error bounds, and validation against
observed operation across representative activity. Evidence must identify
the selected commercial/prototype power path and must not encode Robocraze-
specific behavior as universal firmware semantics.

## Engineering and system integration roadmap

### HW-M1.4E — Engineering / Installer Observability

Provide a commissioning view separate from the caregiver dashboard. Structured
diagnostics should expose live event flow, node ID, session, sequence,
occurrence and receive timestamps, RSSI, channel, ACK/retries/drops,
retained/in-flight queue, NodeHealth, uptime, reset reason, heap/min-heap and
resource health, battery voltage/SOC/lifetime when implemented, routine
baseline-learning state, and installation/RF quality.

Prefer structured backend diagnostic events with WebSocket/SSE-style live
delivery to an engineering UI rather than parsing ESP_LOG serial text as the
product interface. Acceptance requires an installer to commission a node,
inspect RF/power/event health, and distinguish occurrence from receive time
without exposing engineering noise as caregiver activity. Dependencies are
diagnostic contracts, backend transport, and access-control/privacy review.

### HW-M1.4F — RF / Wi-Fi / Backend Coexistence

Cover ESP-NOW plus Hub Wi-Fi STA channel coexistence, AP-channel effects,
Wi-Fi provisioning/reconnect, ESP-NOW range/loss, callback timing, WAN
outage/reconnect, backend replay/idempotency, journal/outbox behavior, and
multi-node behavior later. The fixed channel-1 lab configuration is not an
installed-product assumption.

Acceptance requires controlled channel/provisioning/reconnect/RF/cloud tests
that preserve event identity, durable ACK semantics, journal/outbox recovery,
replay correctness, idempotency, and bounded callback behavior. Dependencies
are Hub Wi-Fi/backend composition and controlled RF fixtures.

### HW-M1.4G — FOTA / Maintenance / Security Closure

After C1/C2 changes, revalidate FOTA regression, sensing during maintenance,
interrupted update, restart during update, recovery, rollback, post-update
event processing, and low-power-state interaction. Production follow-up must
retain authenticated updates, signed OTA where required, rollback
protection/recovery, peer/security limitations, and production credential/key
handling. Acceptance requires these tests plus an explicit security review;
production security is not qualified now.

### HW-EXP-BLE — BLE Transport Feasibility

Only after the optimized ESP-NOW low-power baseline exists, compare BLE with
optimized ESP-NOW while preserving NodeRuntime and higher-level ACK/dedupe/
backend semantics. Measure idle/sleep power, wake energy, event TX energy,
latency, loss, range, reconnection, Hub coexistence, OTA implications,
multi-node behavior, and implementation complexity. This is an experiment,
not a redesign commitment or BLE selection.

### HW-M1.4H — Extended Reliability / Soak

After optimized firmware stabilizes, run 12-hour, 24-hour, and 72-hour
campaigns plus long no-motion, realistic/burst motion, Hub outage/recovery,
node/Hub restart, packet loss, queue/resource, heap stability, battery
discharge, low-power wake-cycle, and applicable FOTA interaction tests.

Acceptance must specify duration, workload, event loss/ordering, recovery,
resource stability, safety, and evidence for each campaign. Evidence belongs
under `docs/hw/evidence/HW_M1_4H_*` or the repository-approved equivalent.

## Commercial power hardware

`HW-PWR-PROT` remains prototype/test-fixture characterization. It may cover
the Robocraze shield's quiescent current, efficiency, 3-V/5-V behavior,
cutoff/recovery, and charger reset, but it is not a C1 blocker.

`HW-PWR-COMM` is later commercial power architecture qualification. Its scope
is battery selection, charging, protection, load sharing/power path,
regulator/buck-boost/PMIC, low quiescent current, conversion efficiency,
brownout, cutoff/recovery, thermal behavior, lifecycle, safety, enclosure,
and component availability/supplier choices. Do not select final hardware in
this roadmap pass.

## Routine-learning dependency chain

Correct chronology and episode semantics are prerequisites for later learning:

`P0-SW-R0` Event Chronology & Episode Semantics
-> `P0-SW-R1` Activity Episodes / Chronology Foundation
-> `P0-SW-R2` Personalized Routine Baseline
-> `P0-SW-R3` Short-Term Deviation Detection
-> `P0-SW-R4` Longitudinal Trend Detection
-> `P0-SW-R5` Explainable Caregiver Insights

No routine-learning implementation may depend on raw Hub receive order as a
substitute for occurrence chronology.

## Forward sequence

`HW-M1.4A QUALIFIED / PASS`
-> `HW-M1.4B B0 + B1–B4 minimal BEFORE baseline`
-> `HW-M1.4C1 Automatic Light Sleep`
-> `repeat identical B1–B4 BEFORE/AFTER`
-> `HW-M1.4C2 GPIO4 PIR Event Wake + Adaptive Activity/Health/Retry`
-> `HW-M1.4C3 Deep Sleep / RTC Retained State`
-> `HW-M1.4D Battery Telemetry + Energy Model`
-> `HW-M1.4E/F/G/H as dependencies mature`.

In parallel: `HW-PWR-PROT` prototype characterization, then later
`HW-PWR-COMM` after commercial hardware selection; and `HW-EXP-BLE` only
after the optimized ESP-NOW baseline exists.

## Additional approved battery and UX details (planned, not implemented)

### Battery-state reporting policy candidate

Keep `last_node_seen` separate from `last_battery_update`. After measurement
hardware and calibration exist, sample at boot and initially about every four
hours, piggyback where practical, and increase sampling/reporting near a
threshold or on abnormal behavior. A candidate warning policy is 20% warning,
10% critical, and 5% urgent, with hysteresis; these are product-policy
candidates, not implemented thresholds. Estimate state of charge using a
calibrated Li-ion discharge mapping and measured energy/activity/retry history,
not a simplistic linear voltage conversion.

Where ADC measurement is supported, allow settling and average/filter roughly
10–16 samples, calibrate against the actual measurement path, and validate a
measured Li-ion discharge curve. Do not write NVS for every PIR event. Use RTC
retention for appropriate transient state (session/sequence as designed,
activity first/last/count, pending aggregate, battery state and recovery
breadcrumbs); reserve flash writes for state that truly requires power-loss
durability.

### Priority and status-indicator direction

Power work priority is: (1) event-driven sleep and ending continuous CPU/radio
wakefulness, with a suitably low-quiescent-current regulator/power path; (2)
first-event delivery plus ordinary PIR burst coalescing; (3) adaptive health
and outage retry; (4) measured ESP-NOW TX-power adjustment; then production
LED reduction and debug-log reduction. Historical lab RSSI is often around
−40 to −60 dBm, so TX-power savings merit measurement, but do not hard-code a
lower setting before link-margin qualification.

The later LED UX should use one centralized non-blocking status manager and a
small vocabulary: one short blink for successful normal application-data
exchange; two medium blinks for ready/registration/authenticated rejoin; three
long blinks for successfully completed and operational FOTA; fast repeated
blinks for generic attention/error. PIR detection alone should not blink.
Current Node blue LED is GPIO8 active-low; routine exchange blinking should be
configurable or disabled in battery mode. Detailed causes belong in
diagnostics/PWA rather than a growing set of LED patterns. This is design
guidance only, not implemented behavior.

### Historical apparent offline-motion failure

In the battery-operated Hub-offline exercise, the Node's usual GPIO8 motion
indication stopped after repeated activity and a complete power cycle appeared
to restore it. Forensic evidence showed the C3 and GPIO4/AM312 path remained
alive; the actual defect was bounded retained/retry queue exhaustion without
ACKs, which made new event admission fail and the indicator appear dead. The
fix and evidence are in
`docs/hw/evidence/HW_M1_4_NODE_OFFLINE_RESILIENCE/README.md`. Preserve this as
a recovery/endurance regression scenario; do not misstate it as a proven PIR
sensor failure. The separate HW-M1.4A run confirmed approximately 19 h 54 min
under its unoptimized HIL workload and did not qualify commercial battery
life.
