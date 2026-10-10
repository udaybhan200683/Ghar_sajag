Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current project status:
docs/progress/CURRENT_STATUS_AND_ROADMAP.md

For implementation/evidence traceability:
docs/validation/MASTER_TRACEABILITY.csv

For formal qualification:
docs/validation/ and evidence/hil/runs/

# Battery, Low-Power and Power Management

## Purpose

A battery Node cannot keep its CPU and radio active like the Hub. It still has
to notice household events, deliver them promptly, retain them during an
outage, and contact the Hub often enough that the Hub can tell whether it is
alive. The engineering problem is to do that with less radio airtime, awake
time, flash writing, LED activity, and logging. Battery life depends on the
whole board and firmware workload; this repository does not establish a
production battery-life number.

The current target favors correctness and observability: it polls the sensor
while awake, keeps Wi-Fi power save disabled, sends health periodically, and
uses bounded retries. BAT-C1/C2 added a passive owner-held PowerPolicy and
RAM-only activity counters. BAT-C3/C4 added bounded PIR noise diagnostics,
nonblocking production indication, quieter routine logs and a confirmed-outage
retry profile. BAT-C5 coordinates a quieter NodeHealth schedule with the Hub
lease. BAT-C6/C7 preserve first-motion durability and compact compatible
repeats. BAT-C8A adds owner-controlled opportunistic light sleep with GPIO4
and timer wake in software; physical wake, radio continuity and energy results
remain for BAT-C8B. Calibrated battery measurement remains incomplete, and no
battery-life improvement is claimed.

## Easy mental model

```text
PIR / sensor
      |
      v
Node samples input (20 ms while awake; bounded sleep when safe)
      |
      v
NodeRuntime creates an event
      |
      v
bounded queue and encrypted recovery record
      |
      v
authenticated send -> ACK or bounded retry/backoff
      |
      v
opportunistic light sleep after GPIO4 and deadline setup
```

Deep sleep remains out of scope. GPIO4 is level-wake configured during
BAT-C8A, but real GPIO/PIR wake is not claimed until BAT-C8B.

## Current sensing and radio behavior

On the C3, `NodeRuntimeAdapter` configures GPIO4 as a pulled-down input and
samples it from the runtime task. While awake there is no GPIO interrupt; the
owner configures a level wake source only for a qualified light-sleep interval.
The task uses a 20 ms poll interval; PIR startup
stabilization is 10 seconds, and input debounce is 150 ms with a 1 second
minimum retrigger interval. These are firmware values, not the historical
HIL fixture's generated-motion pacing.

When qualified motion arrives, the runtime maps the input to a motion event.
The target LED on GPIO8 is active-low. Production now indicates readiness,
durable application ACK and bounded sensor fault status from the owner loop;
qualified PIR alone does not blink. Legacy raw HIL retains its 200 ms PIR
indicator for existing fixture assertions. Routine PIR/send/MAC/ACK messages
are DEBUG in production and INFO in HIL control builds; warnings and errors
remain visible.

Wi-Fi is configured in station mode with `WIFI_PS_NONE`, a fixed ESP-NOW
channel, and configured maximum TX power of 40 API units (10 dBm in the code
comment). Before explicit light sleep the owner deinitializes ESP-NOW and stops
Wi-Fi, then restarts Wi-Fi/ESP-NOW and restores the Hub peer before resuming
the owner path. Normal production NodeHealth is attempted after at most 120 seconds
of quiet authenticated operation; the legacy raw HIL image keeps its 60-second
cadence. Application contact can defer a redundant health attempt.

## BAT-C5 health cadence and Hub lease

The existing C3 owner holds a RAM-only `NodeHealthCadence`. It schedules the
existing authenticated NodeHealth frame 120 seconds after rejoin, a matching
authenticated application ACK, or the previous health attempt. A MAC send
callback alone does not count as authenticated application contact. Due
application work goes first. Pending events, confirmed outage and maintenance
suppress routine health; event retry timing remains owned by `NodeRadio`.
The existing HIL `GET_HEALTH` control can still request a diagnostic frame.

The Hub's authenticated monotonic lease is 310 seconds: two 120-second quiet
health opportunities plus 70 seconds of margin for a 60-second outage probe
and scheduling delay. Current-session authenticated rejoin, accepted runtime
health, admitted application events and verified FOTA ACK progress refresh the
lease. Unknown, revoked, stale-session and unauthenticated traffic cannot.
The existing Hub owner checks this lease once per second and logs only online
state changes. This is distinct from the event-time `CoverageTracker`, whose
historical 190-second coverage expiry remains unchanged and still needs
trusted absolute time for routine coverage decisions.

Pending OTA image validation keeps its immediate post-sensing health probe and
60-second retry opportunity until radio delivery is observed. No new task,
packet type or routine NVS write was added. These timings are a bounded
software policy; quiet-node RF and current reduction remain physically
unmeasured.

## Low-power modes

| MODE | CURRENT STATUS | WAKE SOURCES | STATE RETAINED | RADIO CONSEQUENCES | LIMITATIONS |
|---|---|---|---|---|---|
| Active | Implemented target behavior | Task scheduling and GPIO polling | RAM state; durable events/association are separately saved | Wi-Fi station and ESP-NOW active; `WIFI_PS_NONE` | Continuous CPU sampling and radio availability cost power |
| Light sleep | BAT-C8A software implementation; target build and physical qualification reported separately | GPIO4 high-level plus bounded timer wake | CPU/task/session RAM resumes at the call site | Wi-Fi/ESP-NOW are stopped before sleep and reinitialized after wake; authenticated session continuity is unproven | Only idle, durable, stable-low state; real wake and current measurement deferred to BAT-C8B |
| Deep sleep | Deferred; no target deep-sleep path | None configured | Existing NVS records survive reset; RAM session/task state does not | Radio stops and must be initialized/rejoined after wake | RTC-retained state and event/session reconstruction are not implemented as a deep-sleep design |
| GPIO wake | Configured for BAT-C8A light sleep | GPIO4 high level; timer remains enabled | Wake-causing level is read by the same `QualifiedInput` path | Radio restoration precedes normal transmission | Software compile/test does not prove electrical behavior or first-motion reception on a board |
| Timer wake | Configured on every BAT-C8A sleep attempt | Bounded monotonic deadline interval | The timer wake does not synthesize a sensor event | Owner services the due health/retry work after radio restoration | Target timing and radio behavior remain for BAT-C8B |

## BAT-C8A software light sleep

For the BAT-C8 physical qualification image, build the C3 with
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`, and
`GS_BAT_C8_PHYSICAL_WAKE=ON` in an isolated generated build configuration.
The last option is deliberately explicit: existing HIL-control/FOTA images
remain awake, while the qualification image may use the same real GPIO4 and
timer wake setup as production. The owner still requires initialized sensing,
a supported GPIO wake configuration, and all BAT-C8 policy conditions before
it calls the real ESP-IDF light-sleep API. HIL security controls alone never
make a wake source ready. `INJECT_MOTION` is rejected in this profile, so
physical qualification must use the AM312/GPIO4 path. The profile also uses
the ordinary 120-second initial and repeated NodeHealth cadence and rejects
`GET_HEALTH`, which otherwise forces a fixture health event. Ordinary
HIL-control images retain their early first health record for FOTA testing.
This configuration does not qualify production Secure Boot, eFuse, or key
provisioning.

BAT-C8B qualification firmware emits compact INFO records at eligible sleep
decisions (`BAT_SLEEP_DECISION`), immediately before entry (`BAT_SLEEP_ENTER`),
immediately after return (`BAT_SLEEP_WAKE`), and after radio restoration
(`BAT_SLEEP_RESTORE`). Decision records include policy state, deadline source,
inhibitor mask, GPIO4 stability and pending work. Wake records include the API
result, GPIO/TIMER/OTHER cause, armed interval, measured elapsed milliseconds
and immediate GPIO4 level. These records occur only on eligible sleep attempts;
there is no per-loop ineligibility trace or new telemetry. BAT-C8C formal
current measurement may reduce these qualification logs if their overhead
affects measurement, while BAT-C8B retains them for behavior evidence.

### Pre-C8 idle behavior

Before BAT-C8A, the `gs_node_owner` task ran continuously after session
authentication and recovery restore. It sampled GPIO4 every 20 ms, passed each
level through `QualifiedInput`, drained the existing callback queues, advanced
NodeRuntime/NodeRadio retries, checked the owner-held NodeHealth cadence, and
serviced maintenance state. No sleep API or GPIO wake source was configured.
The owner remained the single writer for event identity, recovery persistence,
radio/session state and sensing. FOTA used its existing worker and validation
tasks.

### Ownership and eligibility

Only `gs_node_owner` evaluates a `LightSleepObservation` and can request sleep.
The portable policy returns eligibility, inhibitor bits, the earliest
monotonic deadline and a bounded interval. The ESP-IDF adapter configures
wake sources, stops the radio, enters light sleep, restores the radio and
returns to the same owner stack. No power-management task, FreeRTOS timer,
radio message or persistence path was added.

Sleep is fail-awake. It is inhibited until authentication, sensing readiness,
radio/session state and wake configuration are known; during rejoin,
transmission, in-flight event or health send, ACK wait, executable pending or retained
recovery work, due retry/health/security work, FOTA or boot-health validation,
maintenance, persistence uncertainty, callback queue work, unsafe outage reception, active
status indication, unexpected runtime state, PIR HIGH, unstable LOW, unsafe
debounce/retrigger state, missing deadline, or a window too short for the
configured margin.

GPIO4 is the AM312 input (expected idle LOW and active HIGH). IDF 6.0.3
provides light-sleep level wake using `gpio_wakeup_enable(GPIO_NUM_4,
GPIO_INTR_HIGH_LEVEL)` followed by `esp_sleep_enable_gpio_wakeup()`. C3 GPIO4 is
among GPIO0–5, which the local SoC headers identify as RTC-function pads; the
selected generic GPIO wake API supports digital GPIOs for light sleep. The
firmware keeps the existing 150 ms debounce as the LOW-stability interval and
also requires `QualifiedInput` to be stable LOW with its existing 1 s minimum
retrigger window elapsed. GPIO4 is re-read after radio shutdown and directly
before sleep. A held HIGH inhibits another attempt, preventing a
sleep/wake loop.

On GPIO wake, the CPU resumes at the sleep call site, restores Wi-Fi/ESP-NOW,
then immediately starts the next owner iteration without the regular 20 ms
delay. The actual GPIO4 level enters the established `QualifiedInput` and
`NodeRuntime::record` path. Its existing debounce runs and the triggering
activity can become the first event; no second edge or HIL injection is used
by this software seam. Timer-only wake samples the actual LOW level and does
not synthesize Motion.

### Deadlines and radio/session behavior

The timer deadline is the earliest available NodeHealth, event retry, security,
maintenance, retirement-report or activity-episode deadline. Sleep subtracts a 500 ms execution
margin, requires at least 500 ms remaining, and caps each request at 30 s so
the existing owner rechecks runtime state regularly. The 30 s cap and margins
are centralized in `power.hpp`. The owner does not use the Hub liveness lease
or coverage expiry as a generic sleep deadline. NodeHealth remains at its
existing 120 s opportunity; authenticated Hub liveness remains 310 s; event
coverage remains independently 190 s.

ESP-IDF 6.0.3 states that Wi-Fi is powered down during explicit light sleep and
connections are not maintained. The owner therefore calls `esp_now_deinit()`
and `esp_wifi_stop()` before sleep, then starts Wi-Fi, restores channel and TX
configuration, reinitializes ESP-NOW callbacks and restores the Hub peer after
wake. The NodeSecurityLink and its frame sequence remain in C3 RAM across
light sleep; no liveness refresh is fabricated and the code does not force a
rejoin solely because it slept. Hub-side session acceptance and radio
continuity still require BAT-C8B physical qualification. A radio restore
failure stays awake and is retried by the existing owner loop.

### Tests and evidence boundary

`make battery-c8-host-test` covers clean idle eligibility, each fail-awake
inhibitor, deadline ordering/margins/cap, wake-causing HIGH handoff, timer wake
without fabricated Motion, lingering HIGH, first Motion/MotionSummary identity,
NodeHealth contact suppression and the 120/310/190-second policy boundaries.
It also runs the battery source invariants for no new task, NVS path, message
type or periodic telemetry. The target is a prerequisite of
`make validation-fast`, with ordinary make failure propagation.

The target-specific adapter uses `esp_sleep_enable_timer_wakeup()` and
`esp_light_sleep_start()`, reads `esp_sleep_get_wakeup_causes()`, and clears
GPIO and sleep wake configuration after every return. The installed ESP-IDF
6.0.3 headers and sources were checked locally. GPIO wake is level-based and
only supports HIGH/LOW modes; if peripheral power-down mode is configured,
the generic GPIO wake API fails closed. ESP-IDF 6.0.3 production and HIL-config
builds both pass: images are 0xdf0d0 bytes (913,616 bytes) and 0xd0850 bytes
(854,096 bytes), respectively, within the 0x1e0000-byte app slot. No physical
HIL, GPIO4 or PIR wake, current measurement, radio/session continuity, or
battery-life claim is part of BAT-C8A. Those remain BAT-C8B work.

`make validation-fast` reaches the C8 host checks, which pass (46 C++ checks
and four Python invariants). The complete target did not pass: its nested quick
release gate timed out compiling `lab-build` (240 seconds) on the first run and
`fota-host-test` (300 seconds) on the permitted retry; the timeout handler then
raised a `bytes`/`str` formatting error. The focused `make lab-build` rerun
passed. This validation-gate result is not a BAT-C8 behavioral qualification.

PIR sensor hardware is an external AM312 module connected to GPIO4. Evidence
for the prototype records the sensor powered at about 3.3 V during operation;
the intention to keep it powered while the C3 sleeps is documented as a
hardware/roadmap requirement, not current sleep behavior. The commercial
power source, regulator, charger and protection topology are not frozen. A
prototype Robocraze TIFC00389 shield was used for a prior fixture run; it is
not a selected product BOM.

## Event aggregation and critical events

Current target behavior creates an event for each qualifying PIR activity;
there is no implemented motion episode/coalescing layer. The runtime and
radio/recovery queues are bounded. Current queue defaults are 32 entries with
four reserved for non-motion events; when full, a new motion admission is
rejected and counted rather than replacing an older event. The reserve is a
capacity policy, not a full priority scheduler.

The documented product direction is to send the first meaningful motion
promptly, then aggregate ordinary repeated PIR motion over a measured window
(initially 30–60 seconds is a proposal), recording first time, last time and
count. No such aggregate event is emitted by current target code. Door state
changes and Call Family/safety events are intended to remain individually
visible and immediate; this is roadmap intent, not a currently implemented
general critical-event scheduler.

Coalescing repeated PIR observations can reduce CPU wakeups, radio packets,
ACKs, retry opportunities and queue pressure. It must preserve event identity
and chronology and must not delay a first event or merge distinct door or
safety semantics. The required episode/chronology foundation remains planned.

## Events, persistence and outage power cost

Each event receives a stable source/session/sequence identity. Retrying sends
the same logical event identity; it does not allocate a new event. Session
identity authenticates the current connection, while event identity supports
deduplication across retry and recovery.

Before an event is exposed to target radio send, the C3 authenticated owner
writes its bounded encrypted recovery record to NVS. The record holds pending
event/retry information, a generation and boot/session recovery metadata. ACK
retirement and a first storage-gap marker also cause persistence updates.
PIR samples and every retry are not individually written. This bounds writes
relative to the event lifecycle, but there is no physical flash-wear or
power-cut qualification claim. On restore, the device obtains a fresh
authenticated runtime session and retransmits the original pending event
identity. Association persistence is separate from volatile session keys.

```text
Hub unavailable
     |
local sensing continues
     |
bounded pending-event storage
     |
retry schedule: 200, 600, 1,800, 10,000, 60,000 ms + deterministic 0–100 ms jitter
     |           (the 60-second interval repeats)
Hub returns -> authenticated rejoin -> same event identity is resent
```

The retry policy waits for application ACK even if the ESP-NOW send callback
reports link-layer success. The target send callback wait is 1 second. This
policy is bounded in storage and rate. After three unacknowledged event send
attempts, the owner selects the existing 60-second periodic retry interval.
A newly admitted non-motion event gets one prompt first opportunity, while
subsequent retries remain gated. A matching authenticated application ACK
clears the outage profile and makes retained work due. This is an active-mode
radio-opportunity policy, not a sleep or measured-power result.

The authenticated association survives reboot in encrypted NVS; the runtime
session does not. A Node reboot loads its association and pending recovery
record, rejoins with fresh session material and resumes delivery. A Hub reboot
restores identity/registry/journal where target wiring supports it; Nodes must
rejoin and replace the prior runtime session. These are active-mode recovery
paths and do not imply deep-sleep retention.

## Battery measurement and policy code

### Target measurement

No ADC sampling path, divider scaling, calibration acquisition, filtering, or
state-of-charge read is wired into the C3 runtime. `NodeHealth` does not carry
measured battery data. Shared protocol structs contain power counters and
telemetry fields, but the target does not populate them from measured current
or sleep accounting. Invalid/missing hardware measurements therefore remain
unknown; they are not treated as zero-percent readings.

### Portable policy and host-side analytics

`PowerPolicy::classify` is host-testable policy code: an uncalibrated or zero
reading is Unknown; calibrated voltage at or below 3300 mV is Critical, at or
below 3550 mV is Low, otherwise Normal. A portable percent estimator uses a
piecewise-linear voltage curve from 3300 mV (0%) to 4200 mV (100%). This is
not a measured C3 ADC conversion or a target battery percentage.

The same policy class contains a `SleepPlan`: default wait is the configured
heartbeat period, pending retry selects 10 seconds, and Critical selects 300
seconds, overriding the pending-retry interval; PIR/reed wake flags follow
NodeConfig. No target runtime calls this planner or programs those wake
sources. The portable energy estimator
requires calibrated current and usable-capacity inputs and at least one hour
of elapsed awake-plus-deep-sleep counters. It integrates modeled sleep, awake,
sensor and radio current; it is only as accurate as those supplied
measurements.

The Python battery analytics path smooths supplied voltage with a median of
up to three samples, applies the voltage curve, and learns energy rates from
reported counters and a per-device calibration profile. It marks drain
abnormal after at least four intervals when recent rate is at least the
configured baseline ratio (default 1.75). It needs eight samples and 72 hours
for HIGH confidence; three samples and 24 hours gives MEDIUM confidence.
These are backend analytics over input data, not C3 ADC behavior.

The local simulator seeds configurable warning/critical values at 20% and 5%.
Those thresholds and derived warning states are simulator/PWA behavior; no
target firmware low-battery notification, 10% threshold, hysteresis, charging
recovery rule, or repeated-warning suppression is implemented. Older battery
design documents describe candidate thresholds and ADC/fuel-gauge plans; they
do not supersede the current target source boundary.

## Hardware and indication considerations

Battery runtime depends on usable cell capacity, temperature and aging,
regulator quiescent current and conversion efficiency, sensor current,
ESP32-C3 awake/sleep current, radio duty cycle, and charger/protection leakage.
The repository has no production measurements supporting a battery-life
claim. The prototype fixture is not the selected product battery system.

For a battery product, unnecessary always-on LEDs and verbose logs consume
energy and can disturb residents. BAT-C3 removes the qualified-motion LED
blink from production and keeps routine success logs at DEBUG. The bounded
owner-loop LED patterns and diagnostic warnings still need measured power and
physical UX qualification.

## Failure and recovery matrix

| CONDITION | EXPECTED BEHAVIOR | IMPLEMENTATION STATUS | ENGINEER DIAGNOSTIC |
|---|---|---|---|
| Repeated PIR activity | First event is durable; compatible repeats are coalesced under BAT-C6/C7 | Implemented in owner/runtime; host and target compilation evidence applies | GPIO4 transitions, debounce/retrigger, motion sequence, summary identity |
| ACK loss | Same event is retried on bounded schedule | Implemented; host retry coverage; physical power cost not qualified | Event key, retry count/next due time, session, ACK status |
| Hub offline | Sense locally, retain admitted events, retry with backoff | Implemented bounded recovery path; endurance/power profile not current-head qualified | Hub reachability, queue counts, retry schedule, RSSI, reset reason |
| Node reboot | Restore association and pending records, rejoin with a new session | Host recovery and target build; physical restart qualification incomplete | Reset reason, recovery generation, event keys, rejoin/session logs |
| Low battery | No target low-battery action exists | Portable policy/simulator only | Raw externally supplied voltage, calibration flag, backend battery profile |
| Critical battery | No target sleep/notification behavior exists | Portable policy/simulator only | Same as above; do not infer a hardware reading from modeled state |
| Invalid ADC reading | No ADC reader; absent/zero portable sample is Unknown | No target ADC implementation | ADC path is absent; inspect telemetry producer/configuration |
| Full event queue | Reject latest motion, count rejection, preserve reserved capacity | Implemented bounded admission behavior | Store/radio counts, rejected-motion and gap counters |
| Persistence failure | Admission must not be treated as safely recoverable before durable save; report failure/gap according to path | Implemented guarded write path; target power-loss qualification incomplete | NVS return/readback, recovery generation, gap marker, error logs |
| Rejoin failure | Keep association and pending events; retry/recovery owner controls next attempt | Implemented protocol recovery; target outage endurance incomplete | Association load, proof result, session changes, retry state |
| Sleep/wake failure | Fail awake; clear wake sources and restore radio after any unsuccessful entry | BAT-C8A software path; target build and GPIO/radio behavior require separate evidence | Adapter result, wake cause, radio restore result, owner state |
| Brownout | NVS recovery is intended to recover valid committed records | Physical brownout/power-cut atomicity not qualified | Reset cause, valid generation, record decode, flash errors |

## Performance and resource observations

Power diagnosis should correlate wake/event frequency, task awake duration,
radio TX/RX airtime, retry count, queue and retained/in-flight occupancy,
heap readings, NVS writes, log volume and configured TX power. Current target
reports health/resource information but does not provide calibrated energy
counters or measured battery voltage. Do not calculate runtime from logs
without a validated current measurement boundary and calibration.

## Historical long-duration report

The HW-M1.4 offline resilience evidence describes an earlier run where the
motion LED stopped blinking after roughly 32 generated motions; separate Hub
outage runs had lasted about seven hours and about one hour. Investigation
found the C3 remained alive, the PIR/GPIO path still worked, and the bounded
radio queue had filled while the Hub was unavailable. Events could then be
accepted by a separate store until that filled, leaving records stranded.
The fix aligned the bounded queue capacities, preflighted admission, reserved
four slots for non-motion events, and made the PIR indication independent of
queue admission. Current code reflects bounded rejection and reports counts;
it does not add motion coalescing. The cited HW-M1.4A PASS is historical
qualification of a specific firmware pair and workload, not current-HEAD
battery/endurance qualification. See
`docs/hw/evidence/HW_M1_4A_ENDURANCE/README.md` and
`docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md`.

## Source map and verification boundaries

Key implementation locations:

- `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/node_runtime_adapter.cpp` — target task, PIR polling, health cadence and radio initialization.
- `.../firmware/node/target/esp32c3/node_target_config.hpp` — GPIOs, poll/debounce/stabilization, channel and TX power.
- `.../firmware/node/components/power/power.hpp` and `power.cpp` — portable battery classification, percent estimate, sleep plan and energy model.
- `.../firmware/node/runtime/node_runtime.cpp` — event generation and runtime flow.
- `.../firmware/node/components/radio/node_radio.cpp` and `.../shared/include/gs/protocol.hpp` — bounded send queue and retry policy.
- `.../firmware/node/components/storage/node_recovery_persistence.cpp` — encrypted pending-event recovery record.
- `.../backend/ghar_sajag/battery.py`, `.../tools/sim/local_lab.py` — supplied-sample energy analytics and simulator thresholds.
- `.../tests/cpp/battery_c8_validation.cpp`, `.../tests/cpp/test_main.cpp` and `.../tests/python/test_battery_power_invariants.py` — BAT-C8, host policy and source invariants.

| EVIDENCE CLASS | CURRENT BOUNDARY |
|---|---|
| IMPLEMENTED | Active PIR polling while awake, bounded event/retry behavior with confirmed-outage profile, encrypted recovery persistence, BAT-C5 adaptive 120-second production health and 310-second Hub lease, BAT-C6/C7 event aggregation, BAT-C8A owner-held light-sleep policy and radio stop/restore adapter, RAM-only diagnostics |
| HOST_VERIFIED | BAT-C8 deterministic eligibility, inhibitor, deadline, first-motion, timer-wake and existing policy regression tests; battery invariant test. No physical or energy result follows from host tests |
| TARGET_BUILD_VERIFIED | BAT-C1–C7 target-build evidence plus BAT-C8A ESP-IDF 6.0.3 production and HIL-config builds (0xdf0d0 and 0xd0850 bytes in a 0x1e0000-byte app slot); build proves compilation only |
| HISTORICALLY_PHYSICALLY_VERIFIED | Historical HW-M1.4A resilience/endurance run for its recorded pair/workload only |
| CURRENT_HEAD_PHYSICALLY_VERIFIED | No current-HEAD physical battery/low-power qualification evidence is claimed |
| NOT_YET_PHYSICALLY_QUALIFIED | BAT-C8 actual light sleep, GPIO4/PIR wake handoff, ESP-NOW/session continuity, current measurement, battery life, ADC/SOC, brownout recovery, flash wear and production power architecture |
| PLANNED / INCOMPLETE | BAT-C8B physical qualification; BAT-C9 battery QoS; BAT-C10 flash coalescing; BAT-C11 adaptive TX power; BAT-C12 deep sleep/RTC retention; calibrated battery telemetry and endurance; physical quiet-node BAT-C5 verification |

## BAT-C1–C12 architecture freeze at `a991c88` (historical design)

This section is a design for later implementation. It changes no firmware and
claims no current-HEAD power or sleep qualification. The historical 19 h 54 min
alive observation belongs to the `bb34f5e` battery fixture, not this revision.
The earlier motion-stall defect was traced to bounded queue admission during
Hub outage and corrected; all future power states must preserve sensing and
bounded, explicit rejection without needing a re-plug or restart.

Historical implementation boundary after BAT-C1 through BAT-C4: the owner calls a passive
policy evaluator and collects uptime, sensing, PIR, send, retry, rejoin,
recovery-commit and queue-high-water counters in RAM. PIR noise counters and
bounded LED patterns are owner-local. Confirmed outage changes retry timing
to the existing 60-second cap; normal initial retries and event identities
remain unchanged. There is no sleep entry, new radio frame or per-retry NVS
write. The existing `NodePowerTelemetry` wire shape remains unchanged; these
diagnostics are not calibrated energy or a battery-life claim. The BAT-C5
implementation above supersedes this historical health timing; BAT-C6 through
BAT-C12 remain future work.

### Current ownership and power baseline

| Responsibility | Current owner/context | State, clock, queue, persistence |
|---|---|---|
| Boot identity and authenticated rejoin | `gs_node_owner` in `node_runtime_adapter.cpp`, `NodeSecurityLink` | Boot session allocated and committed to NVS before radio start; security RX queue and 100 ms commissioning/rejoin poll; association restored before sensing; session keys in RAM |
| PIR sensing and event admission | Same owner; `QualifiedInput` | GPIO4 sampled each 20 ms after 10 s stabilization; 150 ms debounce and 1 s minimum retrigger; `NodeRuntime::record` admits to 32-entry store and 32-entry radio queue with four slots reserved from motion |
| Business retry and ACK retirement | Same owner; `NodeRuntime`/`NodeRadio` | Monotonic `esp_timer_get_time`; 200/600/1800/10000/60000 ms ladder plus sequence-derived 0–100 ms jitter; MAC callback and authenticated application ACK are distinct; only qualifying ACK retires retained business event |
| Radio callbacks | ESP-NOW callback context | Nonblocking copies into static ACK (8), control (8), security (8) and send-result (4) queues; drop counters are atomic; callbacks do not mutate `NodeRuntime` |
| Recovery persistence | Same owner; `NodeSecurityLink`/`NodeRecoveryRepository` | Encrypted bounded NVS snapshot saved before first event send, after ACK retirement and first gap marker; restore only after authenticated session; boot session and association have separate commits |
| Health and liveness | Node owner; `HubRuntime` | BAT-C5 normal production health is due after 120 s without matching authenticated application contact; Hub lease is 310 s and counts rejoin, accepted health/application traffic and verified FOTA ACKs; raw HIL remains at 60 s |
| FOTA and post-boot validity | `gs_node_fota` task and validation task; security owner mediates packets | Control queue, maintenance atomic flag and authenticated ACK handoff; maintenance pauses ordinary sends; boot-health gate depends on owner, sensing and radio evidence |
| LED, logs and power estimates | Node owner/portable `PowerPolicy` | Production GPIO8 indicates ready, durable delivery or bounded fault without blocking; routine success logs are DEBUG; HIL retains PIR indicator; owner RAM counters are diagnostic, not measured energy, and target never enters sleep |

The target uses `WIFI_PS_NONE`, ESP-NOW on channel 1 and fixed 40 quarter-dBm
(10 dBm) maximum power. `CONFIG_PM_ENABLE` is off in the checked-in C3
`sdkconfig`. No target sleep, GPIO wake, ADC, adaptive TX, health piggyback,
motion aggregation or battery QoS path exists. The 20 ms loop, not the
historical approximately 10 s generated-motion spacing, explains about 3000
`sensing_live` increments per minute. Current `PowerPolicy::plan` is not a
safe sleep arbiter: its critical-battery 300 s wait can override a pending
10 s retry. It must be replaced or extended before target use.

### Ownership decision and interface

Keep one authoritative power state machine as a **passive, fixed-size
component invoked only by `gs_node_owner`**. It is event-driven in behavior,
but creates no extra FreeRTOS task. Option A, a separate task, adds stack,
wakeups, shared-session locks and sleep-entry races. A stateless helper alone
(option B) cannot own deadlines and burst state. Option C, owner-task state
machine with portable policy logic, preserves the current single writer and
supports deterministic host tests. FOTA stays in its existing worker and
reports maintenance state to the owner; it cannot call sleep directly.

The proposed narrow contract uses current `Milliseconds` monotonic time and
small value types; names are illustrative until the first code slice:

```text
PowerPolicy.observe(InputObservation)       // qualified motion, level, wake cause
PowerPolicy.observe(DeliveryObservation)    // admitted key, MAC result, app ACK
PowerPolicy.observe(LinkObservation)        // auth/rejoin/contact/outage
PowerPolicy.observe(SystemObservation)      // queue, NVS, FOTA, battery, faults
PowerDecision PowerPolicy.evaluate(now_ms)  // episode action, health due,
                                            // retry profile, TX/LED/log advice,
                                            // next required deadline, sleep
```

`NodeRadio` continues to own each event's retry deadline and stable identity;
PowerPolicy chooses an outage/recovery *profile* and wake opportunity, not a
second retry queue. The owner executes decisions and reports results back.
`PowerDecision` must carry an explicit inhibitor bit mask and a bounded
`next_required_deadline_ms`. No sensing, radio, FOTA or diagnostic module may
independently enter sleep. Security admission and application ACK policy remain
owned by their existing components. Failed observation/unknown state defaults
to awake, normal radio power and conservative delivery.

### State machine and transition contract

Use five mutually exclusive operating states plus two orthogonal flags:
`BOOT_AUTH`, `READY_IDLE`, `ACTIVITY_EPISODE`, `OUTAGE`, `MAINTENANCE`;
`battery_band` and `sleep_mode` are attributes, not duplicated states.

| State | Entry and exit | Allowed work, timer and persistence | Radio/health/retry/sleep |
|---|---|---|---|
| BOOT_AUTH | Enter at reset or session invalidation; exit only after association/commissioning or rejoin and recovery restore | Security exchange, durable boot-session allocation, sensor stabilization and pending recovery; retry security messages on owner deadline | Conservative TX, no sleep, no ordinary event admission before recovery is safe; health after ready |
| READY_IDLE | Enter once authenticated, no active episode or outage; leave on PIR, maintenance, lost contact or invalid session | Sample/wake sensor, service ACK/retry/health and pending queue; no new NVS write without event transition | Normal retry ladder; sleep only with all inhibitors clear and proven wake path |
| ACTIVITY_EPISODE | First qualified ordinary PIR; exit after quiet timeout/max duration or outage/maintenance | First event admitted, committed and sent promptly; update bounded episode counts/timestamps; finalize summary if supported | Keep critical path immediate; sleep between work only when GPIO and timer deadlines are safe |
| OUTAGE | Enter on repeated unacknowledged delivery/contact failure, not a single lost MAC callback; exit on authenticated contact/rejoin | Continue sensing, retain important event identity, compact only eligible repeated PIR, schedule probe; persist admission/gap | Existing ladder reaches 60 s periodic ceiling; no burst retry storm; timer wake required; sleep only between probes with radio lifecycle proven |
| MAINTENANCE | Enter before FOTA/control flash operation; exit on verified worker completion or safe abort | Worker owns image; owner handles secure ACK and restores ordinary traffic afterward | Sleep inhibited, conservative TX, FOTA health/rollback deadlines take priority; local sensor observations must be explicit, not silently lost |

Any state goes to `BOOT_AUTH` if session/security validity is lost. Any state
goes to `MAINTENANCE` before accepted FOTA control starts. `MAINTENANCE` exits
to the state derived from real pending work and contact, never an assumed
empty `READY_IDLE`. Queue/NVS failure is a fault annotation plus fail-closed
admission, not a state that hides PIR sensing. `battery_band` cannot suppress
security, first motion, critical events or required fault notice.

| State | Blocked actions | Sleep eligibility |
|---|---|---|
| BOOT_AUTH | Ordinary runtime transmit/admission before binding, recovery and session are valid; coalescing before identity exists | Never |
| READY_IDLE | Unauthenticated controls and transmission before durable admission | Eligible only after all inhibitors and wake sources are checked |
| ACTIVITY_EPISODE | Deferring the first event, merging critical events, replacing committed evidence with RAM-only count | Possible only between secured work and with a safe episode/timer deadline |
| OUTAGE | Unbounded retries, discarding retained identity, suppressing sensing | Possible between bounded probes after committed recovery state |
| MAINTENANCE | New ordinary radio send, sleep, ambiguous candidate activation | Never while FOTA/control or boot-health work remains |

### Deadlines and sleep decision

All within-boot event deadlines use `esp_timer_get_time()` milliseconds, not
wall-clock time. The owner takes the minimum of next retry, short ACK/MAC
wait, health lease deadline, episode quiet/max deadline, outage probe,
diagnostic/FOTA deadline and later battery sample/checkpoint deadline. An
overdue item executes before another sleep decision; equal deadlines get
priority: security/FOTA, critical event, ACK/retry, sensing, health, optional
diagnostic. Use saturating arithmetic for timer microsecond conversion and
bounded sleep duration; never sleep on an absent or overflowed deadline.
Light sleep must preserve the monotonic clock's elapsed-time behavior in a
target experiment. On deep sleep, RAM clock/session do not survive: RTC time
is only a candidate elapsed-time hint; durable event identities and a fresh
boot session/rejoin remain authoritative.

`SleepDecision` is `{eligible, mode, deadline, inhibitor_bits}`. Mandatory
inhibitors: boot/commission/rejoin/session transition; no reliable GPIO wake;
PIR high or unstable/stuck high; uncommitted recovery/association/session
state; critical event requiring immediate work; queued due event; active TX
or MAC callback; short application ACK window; imminent retry/health/probe;
FOTA/maintenance/flash write/boot-health validation; callback queues not
drained; explicit service diagnostic; unknown clock or driver state. A pending
business event whose next retry is safely in the future may sleep **only**
after it has been durably recorded and the radio/wake lifecycle is proven.
Sleep decision is re-evaluated after arming wake sources and immediately before
entry; a new queue item or GPIO high cancels entry.

### Light sleep, sensing and wake-storm design (BAT-C3/C8)

The AM312 remains powered continuously. ESP-IDF 6.0.3 documents
`gpio_wakeup_enable(GPIO4, GPIO_INTR_HIGH_LEVEL)` followed by
`esp_sleep_enable_gpio_wakeup()` for light sleep with GPIO peripheral powered,
plus `esp_sleep_enable_timer_wakeup()` for the next required deadline. This is
**level** wake, not edge capture: sample GPIO before entry and immediately on
wake, and let `QualifiedInput` confirm a stable transition. A high PIR level
inhibits re-entry until low and stable; stuck high becomes a rate-limited
sensor fault, not repeated zero-time sleep/wake. The GPIO API is unavailable
if `CONFIG_PM_POWER_DOWN_PERIPHERAL_IN_LIGHT_SLEEP` is enabled; a different
RTC-domain API then requires a verified GPIO4 pin/board capability.

ESP-IDF also states explicit light sleep powers wireless peripherals down,
whereas Wi-Fi modem sleep plus automatic light sleep can preserve Wi-Fi driver
operation. ESP-NOW peer/session behavior under either mode is **not proven**
for this target. Therefore BAT-C8 must first measure automatic PM/tickless
behavior with the existing security owner and ESP-NOW callback path, or use
explicit owner-controlled Wi-Fi stop/start with authenticated recovery if
that proves necessary. Do not put the target to sleep on a guess about radio
receive, pending callbacks or cryptographic session continuity. Validate
GPIO4 polarity/pulse width, wake latency, timer wake, FreeRTOS tick accounting,
MAC callback ordering, peer availability, rejoin and FOTA inhibition on the
actual board. The 20 ms busy poll may only be removed after GPIO wake detects
first motion reliably through long idle and noisy conditions.

Preserve the existing debounce/retrigger constants until measurements justify
change. Count raw transitions, qualified PIR, wake cause, high dwell and
wakeups per interval. Continuous high, rapid edges or abnormal wake rate
report a sensor/wake fault and temporarily remain awake or use a bounded timer
check; never disable PIR indefinitely. The previous motion-stall invariant is
an endurance acceptance gate after every sleep change.

### Activity episode and offline compaction (BAT-C6/C7)

BAT-C6/C7 now use the existing C3 owner task and `NodeRuntime`. A first
qualified PIR motion in a new episode is recorded and committed to Node
recovery before radio transmission. Only after that succeeds does the owner
start the episode. Compatible repeats update a bounded RAM count and first/
last repeat times; they do not allocate event IDs, enqueue radio work or
write NVS. A connected episode closes after **45 seconds quiet** or **5
minutes maximum**. Its repeats become one `MotionSummary` business event
with a new immutable event key, typed `additional_count`, `first_ms` and
`last_ms`, and the same room. The summary is committed before transmission
and ACKed through the ordinary durable path. The first event's payload and
identity never change. The schema-3 wire codec accepts prior schema-2
ordinary events; Node recovery and Hub journal readers accept their prior
record versions. Summary frames remain within the protected ESP-NOW bound.

BAT-C7 uses one rolling episode during an outage. A new motion after **30
minutes without qualified PIR activity** starts a fresh durable first event;
continued repeats remain compacted in RAM. On authenticated recovery, the
owner closes the rolling aggregate and commits a summary when queue capacity
permits, with failed admission retried no more often than once per minute.
One pending summary is bounded; if another room's summary arrives while that
slot is occupied, only its nonessential repeat detail may be omitted and
the omitted count is kept in RAM diagnostics. Every room's first meaningful
event still follows the durable path. Ordinary motion and summaries share
the existing four-slot priority reserve, so door/button/critical events are
never coalesced into PIR summaries. `MotionSummary` does not retrigger routine
 activity or caregiver incidents and remains subject to Hub Privacy mode;
 backend ingestion validates and stores it idempotently.
The C3 door sensor itself is still not wired by this change.

The RAM aggregate count is best effort across sudden power loss. A reboot
before summary commit can lose repeat detail, but the first committed motion
and any previously committed summary retain their identities and ACK state.
No NVS write occurs for each repeat, retry or aggregate increment. The
45-second, 5-minute and 30-minute limits are software policy values, not
measured battery thresholds. Host tests establish reduced event/radio
opportunities (for example, 101 close observations become one first event
and one summary); no physical current or battery-life gain is claimed.

### Health, retry and radio opportunity (BAT-C4/C5)

Health policy must be versioned on both Node and Hub before changing cadence.
Define `MAX_HEALTH_INTERVAL`, `MISSED_COUNT`, `GRACE` such that Hub offline
lease equals at least `MAX_HEALTH_INTERVAL × MISSED_COUNT + GRACE`, with a
bounded allowance for wake/radio jitter. Accepted authenticated application
traffic and authenticated health both refresh `last_authenticated_contact`;
MAC success alone does not. Piggyback counters on an app frame when the codec
fits, and schedule standalone health only when no qualifying app contact has
occurred by the policy deadline. Fault, boot, low battery, commissioning and
recovery may temporarily use shorter health intervals. Do not change Node's
60 s cadence alone while Hub still uses its 190 s lease. Preserve an explicit
maximum silent interval so a quiet sleeping Node cannot appear healthy forever.
Health remains best-effort and does not substitute for a durable business ACK.

Retain `NodeRadio`'s per-event identity, existing initial delays and
sequence-derived jitter. Its global next-opportunity gate already prevents an
N-event retry burst. PowerPolicy observes authenticated contact and selects
`NORMAL`, `SUSPECT`, `CONFIRMED_OUTAGE`, `RECOVERY` modes; the radio component
owns due times. Confirm outage only after repeated missed application ACKs or
Hub contact deadline, never a single MAC failure. Once confirmed, cap probes
at the existing 60 s periodic interval initially, with no unbounded
exponential delay. Critical events get the next bounded opportunity without
discarding ordinary event identities; successful authenticated contact
immediately resets to normal and drains pending work fairly. Any change to
priority scheduling must preserve the current four-slot motion reserve and
test noisy-node fairness. A session invalidation invokes authenticated rejoin,
not a raw radio probe.

### Indication, battery and flash policies (BAT-C3/C9/C10/C11)

BAT-C3 now uses a nonblocking owner-loop GPIO8 pattern for readiness,
successful application delivery and a bounded PIR fault indication. Production
does not blink merely because PIR went high; legacy raw HIL retains its PIR
indicator. Routine PIR/send/MAC/ACK progress logs are DEBUG in production and
INFO in HIL control. Security, storage, OTA and fatal logs remain at their
existing levels. The three-long-blink completed-FOTA indication, a configurable
routine-data LED switch and measured LED power savings remain future work.
No log or LED callback may block owner progress.

Until calibrated target ADC hardware exists, battery state is `UNKNOWN` and
must not suppress any service. Later ADC sampling needs settling,
approximately 10–16 filtered samples, board calibration and Li-ion discharge
mapping, with hysteresis between `NORMAL`, `LOW`, `CRITICAL`. Optional health,
LED, logs, repeated ordinary motion and noncritical retry effort may be
reduced in low battery. First significant activity, SOS/critical action,
authenticated rejoin, required recovery and fault reporting are never
suppressed. Keep last-node-contact separate from last-battery-update.

Flash classification:

| Class | State and rule |
|---|---|
| MUST_BE_DURABLE_IMMEDIATELY | Boot session progression before radio, association/key/revocation transitions, admitted business event and its retry identity before send, ACK retirement, first gap marker, critical episode summary before it replaces individual evidence |
| MAY_BE_CHECKPOINTED | Episode counters only while first event and later summary semantics remain explicit; calibrated battery sample, aggregate resource counters and nonsecurity diagnostic breadcrumbs |
| RAM_ONLY | Raw PIR levels/edges, current wake cause, rate-limit counters, policy residence times and rolling RF-quality window |

Do not defer security/session writes or add a per-edge NVS commit. Measure NVS
write count and wear under a busy PIR workload before relying on aggregation
for flash life. On any required commit failure, preserve the current
fail-closed owner behavior; never transmit an event whose recovery identity
was not committed.

Adaptive TX power is deferred until RF measurement. PowerPolicy alone chooses
from a small board-qualified ladder, using authenticated ACK outcomes, retries,
latency and trusted RSSI over a rolling window; changes require hysteresis and
minimum dwell. Commissioning, rejoin, FOTA, critical delivery or link recovery
force conservative/high power. Historical laboratory RSSI near -40 to -60 dBm
does not justify a hard-coded reduction. Record per-step reachability and
energy under obstruction, distance and interference before enabling.

### Deep sleep, telemetry, concurrency and resource budget

Deep sleep is optional after measured light-sleep gains. It destroys the RAM
session, `NodeRuntime` instance, ESP-NOW peer state, callback queues and
ordinary timers. A future deep-sleep boot must allocate a fresh durable boot
session, restore association and event identity, authenticate rejoin, then
restore pending work. Candidate RTC-retained state is episode times/count,
next wake deadline, battery/filter state and diagnostics; security and durable
business identities remain in protected persistent storage. Do not write NVS
on each PIR trigger. Pending FOTA, uncommitted events and active ACK waits
inhibit deep sleep. `DEEP_SLEEP_NOT_NEEDED` is an allowed outcome if measured
light-sleep endurance meets product goals.

Extend existing `EnergyCounters`/`NodePowerTelemetry` rather than creating a
second telemetry channel. Owner accumulates active/light-sleep residence,
qualified PIR, wake reason/count, TX attempts/retries, health sends, rejoin,
NVS commits and queue high-water; existing retained and heap counters remain
available. Current telemetry lacks a light-sleep field, so add a versioned
bounded extension only when the target can measure it. Counter updates are
RAM-only and are emitted with existing authenticated health/event traffic or
on explicit diagnostic request; no per-transition flash write or extra
periodic radio packet. Current mAh model cannot turn these counters into
measured energy without HW-M1.4B current/voltage calibration.

Only `gs_node_owner` mutates policy, episode, `NodeRuntime` and session
security. ESP-NOW callbacks copy into existing bounded queues without
blocking, allocating, flashing or calling policy. FOTA worker publishes
maintenance and typed results through existing atomic/queue handoffs; it
does not borrow policy or session locks. A timer/ISR, if later introduced,
only signals owner; no policy mutation in ISR. Recheck queue and GPIO before
sleep and after wake. Never hold a mutex around `esp_now_send`, NVS commit or
sleep entry. A FOTA begin racing sleep sets the inhibitor before sender work;
if the owner is already asleep, a proven wake signal or bounded timer must
bring it back. Failure to prove that wake path blocks sleep integration.

Initial fixed-size budget *estimate*, not a measured target result: policy
state 96–192 B, one episode 96–160 B plus bounded room identifier, counters
128–256 B, rolling RF window 32–64 B, battery filter 32–64 B; approximately
0.5–1 KiB static/RAM total, no new task, queue or per-event allocation.
Actual `std::string`/alignment costs, code size, owner stack high-water and
20 ms loop CPU cost require target measurement. Keep the policy update O(1)
per observation, not a scan of all pending events every poll.

### Failure review

| Failure | Detection | Safe behavior and recovery | Focused test |
|---|---|---|---|
| PIR changes during sleep entry | GPIO re-read or immediate wake | Cancel entry/process first qualified event; never lose level | Boundary race on board |
| PIR high/stuck high or noisy wake storm | Level/dwell/wake-rate counters | Stay awake or bounded timer check; fault health; continue sensing | High/edge burst endurance |
| Hub disappears or returns | Authenticated contact/ACK deadlines | Retain IDs, bounded 60 s probes, then authenticated progress and fair drain | Outage/reconnect |
| Session invalid or rejoin fails | Security owner phase/proof | Inhibit sleep during recovery, reject stale ACK, retain events | Rejoin loss/stale session |
| Pending ACK at sleep decision | In-flight flags/short deadline | Keep awake until callback/ACK window closes; retry later | Delayed ACK |
| NVS commit fails or reboot during episode | Commit result/recovery decode | Stop unsafe send; restore committed first event and gap/summary contract | Inject write failure/reset |
| FOTA begins near sleep | Maintenance flag/queue | Inhibit sleep and preserve boot-health path; abort safely on conflict | FOTA/sleep race |
| Low battery during outage | Calibrated band/hysteresis | Preserve first/critical event and bounded authenticated probe | Low-voltage outage |
| Timer overdue after wake | Monotonic deadline comparison | Execute due work once in priority order, then recalculate | Oversleep/deadline |
| Unexpected reset or replayed event | Reset cause, boot session, Hub dedupe | Restore old event key only under fresh authenticated session; reject stale packet | Reset/replay |

### Implementation waves and decision register

| Wave | Modules/behavior | Dependency and focused proof | Rollback point |
|---|---|---|---|
| 1: BAT-C1/C2 | Add low-overhead owner telemetry and passive policy observations/deadlines; no sleep | Current active-mode behavior, host policy tests, C3 build, HW-M1.4B before/after measurement path | Policy disabled: existing 20 ms loop |
| 1B: BAT-C3/C4 | Implemented nonblocking production LED/log policy, bounded PIR diagnostics and confirmed-outage profile around existing `NodeRadio`; no sleep | Host owner/queue tests and C3 target build; physical power and motion-continuity measurement remains pending | Existing normal retry ladder and legacy raw HIL indication |
| 2: BAT-C5 | Implemented owner-local health deferment and coordinated 120 s/310 s lease; no new wire schema | Shared protocol/Hub tests and both target builds; quiet-node physical liveness remains pending | Historical 60 s/190 s contract |
| 3: BAT-C6/C7 | Bounded episode and versioned summary schema; safe offline compaction | Target codec/Hub consumer and NVS crash tests, outage chronology | One-event-per-qualified-PIR |
| 4: BAT-C8 | GPIO4/timer light sleep only after radio/wake experiment | C3 build, wake/ACK/rejoin/FOTA race and overnight sensing; measured power | Active polling mode |
| Conditional: BAT-C9/C10/C11/C12 | ADC QoS, write checkpointing, adaptive TX, optional deep sleep | Calibrated hardware, wear/RF/endurance evidence | Last measured safe policy |

Frozen for implementation: single Node owner; passive deterministic policy;
current security and radio ownership; minimum-deadline scheduler; explicit
sleep inhibitors; first event prompt; critical-event isolation; protected
event/ACK/session persistence; authenticated liveness; no per-edge flash
write; no extra periodic telemetry packet; FOTA inhibits sleep; deep sleep
optional. Needs experiment before freeze: exact GPIO4 wake/electrical pulse
and board pull behavior; automatic versus explicit light-sleep ESP-NOW
continuity; sleep current and wake latency; health interval/Hub lease values;
episode quiet/max duration and schema; battery thresholds/calibration; TX
ladder; deep-sleep value. This historical design table does not itself provide
qualification; current BAT-C1–C5 implementation is described above.

| Decision | Status | Boundary |
|---|---|---|
| PowerPolicy owner | FROZEN_FOR_IMPLEMENTATION | Passive component, single `gs_node_owner` writer |
| Runtime/task ownership | FROZEN_FOR_IMPLEMENTATION | Reuse owner, callbacks and FOTA worker; no new policy task |
| State machine | FROZEN_FOR_IMPLEMENTATION | Five operating states; battery and sleep are attributes |
| Deadline ownership | FROZEN_FOR_IMPLEMENTATION | Owner takes earliest required monotonic deadline; NodeRadio retains per-event retry due time |
| Sleep inhibitors | FROZEN_FOR_IMPLEMENTATION | Explicit mask, fail awake on unknown or incomplete work |
| NodeHealth/liveness contract | IMPLEMENTED_PROVISIONAL | BAT-C5 120 s production health and 310 s Hub lease are host tested; physical quiet-node timing remains to be measured |
| Retry/backoff ownership | FROZEN_FOR_IMPLEMENTATION | NodeRadio owns retry queue; policy chooses outage profile and radio opportunity |
| Activity episode ownership | FROZEN_FOR_IMPLEMENTATION | One owner-held bounded PIR episode; duration and wire schema still need experiments |
| Critical-event classification | FROZEN_FOR_IMPLEMENTATION | Only ordinary PIR motion coalesces; new kinds default critical |
| Persistence boundary | FROZEN_FOR_IMPLEMENTATION | Security and admitted business identities commit before exposure; no per-edge write |
| Telemetry ownership | FROZEN_FOR_IMPLEMENTATION | Owner accumulates counters, existing authenticated traffic carries them |
| Battery QoS boundary | FROZEN_FOR_IMPLEMENTATION | Unknown means no suppression; thresholds require measured calibration |
| TX-power ownership | FROZEN_FOR_IMPLEMENTATION | Policy chooses conservative ladder; RF thresholds require physical measurement |
| FOTA/maintenance interaction | FROZEN_FOR_IMPLEMENTATION | Existing worker owns OTA; owner inhibits sleep and normal TX |
| Light-sleep integration | NEEDS_EXPERIMENT_BEFORE_FREEZE | GPIO4 electrical wake and ESP-NOW/PM continuity on actual IDF 6.0.3 board |
| Deep-sleep future boundary | FROZEN_FOR_IMPLEMENTATION | Optional after measurements, always fresh boot session/rejoin |

ESP-IDF API reference for the proposed wake boundary: [ESP32-C3 sleep modes,
ESP-IDF 6.0.3](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32c3/api-reference/system/sleep_modes.html).

## Engineer diagnostics

When consumption or reporting changes, correlate reset and wake reason (if
available), boot/session/rejoin, NodeHealth cadence, event cadence, retry
count and due time, pending/in-flight counts, queue rejection, NVS generation
and write errors, heap, logs, RSSI/TX power, and externally measured current.
For battery state, inspect the raw sample and calibration/profile metadata;
the current target has no ADC value to inspect. A frequent radio retry loop
usually points to ACK/session/Hub reachability, while a steadily active CPU is
expected with the present 20 ms poll design.

## Historical canonical R1 C3 offline-idle audit — 2026-10-10

This audit describes the pre-GS-150 source and authorization checkpoint. Read
the delivered GS-150 section below for current behavior.

This is a current-source audit, not approval of the separate GS-147 sleep-first
and expanded-journal design. On the current canonical branch, a ready Node with
an admitted event in confirmed outage cannot light-sleep between retries:
`node_runtime_adapter.cpp` sets `pending_tx` and `ack_wait` whenever
`runtime.pending() != 0` (around lines 1559–1562), sets `recovery_work` while
`runtime.persisted() != 0` (1564–1569), and sets `outage_active` from the
outage profile (1599). `power.cpp` maps each condition to an inhibitor
(107–134). When no sleep is entered, the owner uses the 20 ms PIR poll delay
(1626). Thus the confirmed-offline backlog path performs about 50 owner/PIR
poll iterations per second while the existing outage retry opportunity remains
about 60 seconds apart. Retry time is still owned by `NodeRadio`; its current
ladder and deterministic jitter are in `components/radio/node_radio.cpp`
(102–133). The session-recovery ladder remains owned by
`SessionRecoveryPolicy` and the existing owner loop.

`PowerPolicy::evaluate()` (power.cpp 239–269) computes a passive diagnostic
decision that the adapter explicitly discards (node_runtime_adapter.cpp 1519–1520).
The active sleep decision is `evaluate_light_sleep()` (1528–1600), still called
by the same `gs_node_owner`; there is no second power task, but the diagnostic
policy result is not the eligibility authority.

This behavior is directly covered by the current BAT-C8 focused test:
`battery_c8_validation.cpp` asserts pending transmission, application ACK wait,
retained recovery work and outage each inhibit sleep (113–130). The current
runtime also stops Wi-Fi/ESP-NOW for light sleep and restores them before the
owner loop resumes. GPIO4 HIGH wake feeds the existing qualified PIR path; a
held HIGH remains sleep-ineligible. Timer wake is bounded by the earliest
health/retry/maintenance/security deadline and the existing 30-second cap.
Unauthenticated rejoin backoff can already sleep to its scheduled security
retry; active security exchange remains inhibited.

The relevant locked sources are GS-D020 (safe production light-sleep/wake and
event-processing behavior) and GS-D027 (avoid unnecessary Node wake-ups while
preserving required retry/recovery work). GS-D025 covers a powered, locally
connected Hub during an internet-only outage; it does not define a Hub-power-off
Node retention or recovery target. GS-147 records that target, event workload,
recovery latency and retirement/ACK interoperability as open, and remains a
proposed design blocked by GS-146. In addition, current code has no separate
application-ACK receive-window deadline: a pending EventKey remains eligible
for authenticated ACK while the radio is on, until its retry becomes due. Going
to light sleep during that interval would stop RX and could defer receipt until
the next exact-key retry. The retry/duplicate and durable-before-ACK invariants
remain intact, but whether that receive deferral is allowed is not defined by a
locked requirement.

**Disposition:** SOFTWARE_GAP_CONFIRMED=YES for awake polling between recovery
opportunities. SLEEP_FIRST_CHANGE_AUTHORIZED=NO while the ACK receive window and
Hub-off recovery/service expectations remain undefined. `BUG_CLASSIFICATION=INVESTIGATE_ONLY`;
`REQUIREMENT_SOURCE=GS-D020, GS-D027; REQUIREMENT_GAP=ACK receive-window and
Hub-power-off recovery contract`; `DECISION_IDS=GS-D020, GS-D027`;
`TASK_SCOPE=C3 software audit and safe, bounded battery improvement`;
`OUT_OF_SCOPE=GS-147 journal expansion/protocol changes, retry interval changes,
deep sleep and physical actions`. No production behavior was changed. The exact
product decision needed before a future behavior patch is whether the existing
retry deadline is an approved end of the ACK receive window (with retransmission
of the same EventKey/original timestamp after wake), and which existing
authenticated recovery deadline governs Hub return without a new PIR. The
approved GS-147 Hub-off duration/event envelope remains a separate open decision.

The current software-only model is limited to logical scheduler behavior: while
this path stays awake it polls at 20 ms (3,000 nominal poll intervals per
minute), while the outage radio gate allows roughly one scheduled retry
opportunity per 60 seconds. After the ACK-window decision, the existing 30 s
sleep cap would imply at most two timer-bounded waits per 60-second interval,
plus GPIO/event and required control/security work; this is a schedule estimate,
not measured active time or current. No validated battery-life gain is claimed.

Existing counters are not sufficient for physical-energy or full write-rate
claims. `awake_ms` is assigned monotonic uptime in `node_runtime_adapter.cpp`
(779), not accumulated awake residency; light-sleep telemetry stores entry/wake
counts and only the last requested/elapsed duration; ineligible decisions are
not counted; `radio_tx_ms`/`radio_rx_ms` have no target updates. The RAM
`recovery_nvs_commits` counter records event admission, ACK retirement, gap and
summary sites, but misses the boot-generation and Hub-epoch recovery writes.
These counters do not add persistent writes and are not current measurement.
Do not optimize NVS until target write frequency/erase behavior is measured.

BAT-C9 is `PRODUCT_DECISION_REQUIRED` (calibrated voltage hardware is absent;
define warning/QoS behavior without suppressing critical PIR/ACK/rejoin).
BAT-C10 is `MEASUREMENT_REQUIRED` (complete target NVS-write frequency and
erase-amplification evidence before selecting a safe reduction).
BAT-C11 is `POST_R1` by default (retain fixed 10 dBm until RF margin, retries,
latency and energy have been measured and a scoped need is approved).
BAT-C12 deep sleep is `POST_R1` / explicitly deferred by the user in latest
GS-115/GS-110/GS-146 comments; do not implement it under this task.

Validation on the unchanged firmware source at canonical start HEAD
`3279294e31345f0ff34d5d97ee456145375eb46a`: `make battery-c8-host-test`
PASS (72 C++ checks and 9 Python invariants); `make cpp-test` PASS (1,479
checks); `make python-test` PASS (344 tests, one documented skip). Existing
ESP-IDF 6.0.3 C3 build evidence remains applicable because no firmware source
changed; the recorded image is 931,424 bytes. No hardware was touched. The
latest Jira-approved BAT-C8 split assigns functional non-power P1–P9 to GS-114
and quantitative P10 power acceptance to GS-149; GS-146 still requires both.

## Historical GS-150 ACK-boundary stop — 2026-10-10

The source observations below remain valid. Its requirement for a guaranteed
Hub ACK-arrival maximum is superseded by the subsequent user clarification and
the conservative implementation described in the GS-150 section below.

GS-150 Option A is approved as a narrow implementation exception, but its
explicit Phase 1 stop condition applies: do not choose an arbitrary ACK timeout.
Current source does not provide a finite authenticated application-ACK receive
window that leaves a safe interval to sleep before the existing retry.

Evidence:

- The Node adapter's `kSendCallbackTimeoutMs` is 1,000 ms
  (`firmware/node/target/esp32c3/node_runtime_adapter.cpp:55`). It bounds only
  the Node's local ESP-NOW send callback while an attempt is `in_flight`
  (1015–1031). Once that callback is processed, `runtime.transport_result()` is
  called and `in_flight` is cleared (973–993). This timeout does not bound the
  Hub's authenticated application Durable ACK.
- `NodeRadio::record_transport_result()` establishes the existing next retry
  at 200/600/1,800/10,000/60,000 ms, with deterministic EventKey jitter up to
  100 ms; confirmed outage uses the existing 60,000 ms rung (node_radio.cpp:
  102–133; `shared/include/gs/protocol.hpp:34–36`). No separate ACK expiry is
  stored. `next_due_at()` is the retry deadline, not an application-ACK
  timeout.
- The Hub authenticates and accepts the Node message, calls
  `runtime.run_state_once()` (which returns after the durable transition), then
  seals and submits the Node ACK using `esp_now_send()`
  (`firmware/hub/target/esp32/hub_runtime_adapter.cpp:1141–1179`). The Hub path
  specifies ordering, but no maximum time from Node MAC completion to durable
  ACK arrival at the Node. `esp_now_send()` submission success is not an
  application delivery receipt.
- The Node's event is retired only by the matching application ACK, and the
  ACK-driven pending/recovery persistence remains in the existing owner
  (`node_runtime_adapter.cpp:895–947`; `node_runtime.cpp:110–140`). Existing
  sleep policy treats every pending event as `ack_wait` and blocks sleep.

Therefore the 1,000 ms callback timeout cannot be reused as an application-ACK
window. Using `next_retry_deadline()` as the window end also does not create a
safe sleep interval: at that boundary the unchanged retry is due and must be
offered; sleeping earlier would stop receiving an ACK still accepted by the
current behavior. Making the Hub promise and meet a new maximum Durable-ACK
arrival time would add a timing contract that neither source nor a LOCKED
decision currently supplies.

**GS-150 disposition: BLOCKED before production behavior changes.** Required
product input: approve a maximum end-to-end interval, measured from Node MAC
callback completion, in which the Node must listen for a matching authenticated
application Durable ACK; the Hub implementation must demonstrate its durable
commit and ACK submission/arrival fit that interval under supported runtime
conditions. The bound must end early enough to provide a nonzero sleep window
before the existing retry deadline, while preserving retry timing. Until that
contract is approved and supportable, keep the current behavior. No timer,
radio, event, ACK, queue or security code changed; no GS-147 journal feature
was implemented.

Validation at the unchanged firmware source HEAD `f245eebcd80c9e43a230ae0ee814f59a37adefd0`:

| COMMAND | EXIT | RESULT |
|---|---:|---|
| `make -j2 battery-c8-host-test node-recovery-persistence-host-test node-retirement-protocol-host-test rejoin-host-test secure-fota-adapter-host-test` | 0 | PASS: BAT-C8 72 C++ / 9 Python; encrypted Node recovery; authenticated retirement; session rejoin; secure FOTA adapter/hash |
| `make cpp-test` | 0 | PASS: 1,479 checks |
| `make python-test` | 0 | PASS: 344 tests, one scoped skip |

Firmware was unchanged, so a C3 rebuild was not required; the clean IDF 6.0.3
build evidence above remains applicable. GS-150 scenario-specific new tests,
before/after activity simulation and final-candidate physical qualification
were not run because no safe ACK boundary exists yet. The previous 20 ms versus
60 s logical-poll comparison remains a baseline; no post-change metric or
physical battery benefit is claimed. GS-150 blocks final-candidate GS-114
physical tests; GS-149 remains a later quantitative gate. Original paired
hardware and its pending events were not touched.


## GS-150 delivered software design — 2026-10-10

The user clarified that approved Option A permits best-effort ACK reception
with exact-key replay, and explicitly authorized a conservative confirmed-outage
implementation. A guaranteed network ACK latency is not required to preserve
retention. No LOCKED decision, wire/storage schema, retry interval, capacity or
context revision changes. GS-D020/027 and the existing authenticated
lost-ACK/deduplication contract remain authoritative. Detailed reproducible
results are in [GS-150 software evidence](../exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md).

### Selected policy and source-derived receive opportunities

Select C plus a narrow B: connected/transient-failure pending events keep
continuous reception. Only the existing three-unacknowledged-attempt outage
profile may sleep with durably pending records after completed transport and a
best-effort application receive opportunity. This opportunity is **10,000 ms
from local callback completion or its existing 1,000 ms timeout**, taken from
`SessionRecoveryPolicy::active_contact_timeout_ms`: the negotiated current
protocol already permits replacement of an unanswered session after three
completed attempts and 10 seconds. This is a conservative receive budget,
not a guaranteed Hub completion time, ACK-validity expiry or retirement signal.
The actual session-recovery deadline may preempt it, exactly as before.

A successful application MAC callback additionally keeps continuous reception
while pending: the peer may be reachable with slow durable processing. This
inhibitor is not authenticated contact, does not clear outage or retire an
event. It prevents periodically missing every delayed ACK from an otherwise
reachable Hub. A valid matching ACK still works after the budget whenever RX
is available. After a failed/ambiguous transport and sleeping, the original
scheduled retry reseals the original event under the current session. The Hub
commits/dedupes that identity and sends another authenticated response.

Auxiliary health/retirement completion holds reception for **300 ms**, the
whole earliest existing event-retry envelope (200 ms + maximum 100 ms jitter).
Outstanding fragments also inhibit sleep until their callback/timeout. Their
existing 1 s failure and 5 s report retries remain unchanged and are included
as timer deadlines; a near 1 s retry may leave no profitable safe sleep.
In-service rejoin stays awake for its existing first retry opportunity
(1,500 ms + session jitter) after each submission. Bootstrap/provisioning stays
awake. Existing 30 s fallback, ambiguity windows, active 10 s and idle 430 s
contact deadlines are respected. Rejoin/session replacement abandons reception
of old-session application frames, preserves every retained event and protects
its new handshake reception. No faster/slower rejoin or new Hub-return SLA.

Alternative A (guaranteed arrival bound) is unsupported by source and unnecessary
for this design. General connected-mode B was rejected: deterministic slow-ACK
simulation exposed repeated missed-ACK starvation. A first 300 ms application
candidate was tightened to the existing 10 s recovery budget and successful-MAC
receive inhibitor. Connected-mode reception therefore remains conservative.

### One owner, retention and wake

The same owner holds `AckListeningWindow`, builds its snapshot with
`observe_retained_delivery`, and calls authoritative `evaluate_light_sleep`.
Durably retained backlog is separate from executable recovery/persistence
work. Offline RAM motion summaries remain deferred as in C7, and are not an
executable sleep blocker until connected; gap/fault work remains an inhibitor.
FOTA, boot-health, control, active TX, queued callbacks, unsettled persistence,
unsafe runtime/radio state and due/near deadlines still inhibit sleep.

The earliest health, event retry, retirement retry, episode, active/idle contact,
rejoin/fallback/ambiguity deadline owns timer wake. The 30 s cap, 500 ms margin,
500 ms minimum, powered GPIO4 HIGH wake, LOW stability and debounce/retrigger
safeguards remain. PIR is rechecked around entry. Held HIGH stays awake and is
sampled without duplicate admission. Important events retain their existing
immediate admission/TX rules and queue reserve; no new door/button/SOS GPIO
integration or event type was introduced.

ESP-NOW/Wi-Fi stop and restore through the existing adapter, retaining RAM AEAD
counters/session. Partial callback initialization cannot mark ESP-NOW ready;
restore errors fail awake, retry restoration and keep sensing/durable admission
running rather than skipping PIR. Original timestamps and EventKeys remain
untouched. Only the existing verified application ACK handler retires records
and persists the retirement; missed responses never fabricate completion.

`LightSleepTelemetry` now accumulates successful monotonic sleep residence in
RAM. `EnergyCounters.awake_ms` subtracts that residence from uptime instead of
calling uptime awake duration. No new telemetry packet, wire field or NVS write.
These counters do not measure physical radio energy or battery life.

### Qualification boundary

Host policy/security/persistence/replay/simulation and target compilation are
software evidence. GPIO4 electrical pulses, wake/resume latency, session/RF
continuity, failed restore on board, overnight motion and real current remain
GS-114 P1–P9 and GS-149 P10 work. No protected board was accessed. The 32-event
pending limit remains; GS-147 journal/capacity/retention decisions remain gated.
No deep sleep or C9–C12 work. See the evidence record for exact metrics and
command exits, including modest added receive cost in already sleeping paths.
