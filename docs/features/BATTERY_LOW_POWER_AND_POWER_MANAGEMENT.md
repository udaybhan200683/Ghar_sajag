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
uses bounded retries. The low-power policy and battery estimator are present
as portable code, but target sleep and measurement integration is incomplete.

## Easy mental model

```text
PIR / sensor
      |
      v
Node samples input (current target: active polling)
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
active wait for next input (sleep is planned, not wired in)
```

The final low-power state in this diagram is a future target integration. No
current target call enters ESP light sleep or deep sleep.

## Current sensing and radio behavior

On the C3, `NodeRuntimeAdapter` configures GPIO4 as a pulled-down input and
samples it from the runtime task. There is no GPIO interrupt or sleep wake
source configured. The task uses a 20 ms poll interval; PIR startup
stabilization is 10 seconds, and input debounce is 150 ms with a 1 second
minimum retrigger interval. These are firmware values, not the historical
HIL fixture's generated-motion pacing.

When qualified motion arrives, the runtime maps the input to a motion event.
The target LED on GPIO8 is active-low and blinks for about 200 ms after the
qualified PIR signal. That blink shows local sensing, not that the event was
persisted, transmitted, or accepted by the Hub. The target currently logs
radio and sensor activity; reducing production debug output is planned.

Wi-Fi is configured in station mode with `WIFI_PS_NONE`, a fixed ESP-NOW
channel, and configured maximum TX power of 40 API units (10 dBm in the code
comment). Thus current firmware does not save energy by radio sleep or dynamic
TX power. NodeHealth is attempted every 60 seconds when the radio owner is
available; application traffic also refreshes Hub liveness.

## Low-power modes

| MODE | CURRENT STATUS | WAKE SOURCES | STATE RETAINED | RADIO CONSEQUENCES | LIMITATIONS |
|---|---|---|---|---|---|
| Active | Implemented target behavior | Task scheduling and GPIO polling | RAM state; durable events/association are separately saved | Wi-Fi station and ESP-NOW active; `WIFI_PS_NONE` | Continuous CPU sampling and radio availability cost power |
| Light sleep | Policy concept only; no target sleep call | None configured | Not applicable to current target | No current sleep/wake cycle | Automatic light sleep is planned first, subject to measurement and qualification |
| Deep sleep | Deferred; no target deep-sleep path | None configured | Existing NVS records survive reset; RAM session/task state does not | Radio stops and must be initialized/rejoined after wake | RTC-retained state and event/session reconstruction are not implemented as a deep-sleep design |
| GPIO wake | Not configured | GPIO4 is sampled, not a wake source | No sleep state | Not applicable | Roadmap intends GPIO4 wake after light-sleep baseline |
| Timer wake | Not configured | No timer wake call | No sleep state | Not applicable | A portable `SleepPlan` is not target timer programming |

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
policy is bounded in storage and rate, but fixed retry timing is not yet an
adaptive low-power outage strategy.

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
energy and can disturb residents. Current LED activity is brief on qualified
motion, while target diagnostic logs remain present. Production indication
and log levels need an explicit power policy and measured qualification.

## Failure and recovery matrix

| CONDITION | EXPECTED BEHAVIOR | IMPLEMENTATION STATUS | ENGINEER DIAGNOSTIC |
|---|---|---|---|
| Repeated PIR activity | Separate events are admitted until bounded capacity; no coalescing today | Implemented active sensing; aggregation planned | GPIO4 transitions, debounce/retrigger, motion sequence, queue occupancy |
| ACK loss | Same event is retried on bounded schedule | Implemented; host retry coverage; physical power cost not qualified | Event key, retry count/next due time, session, ACK status |
| Hub offline | Sense locally, retain admitted events, retry with backoff | Implemented bounded recovery path; endurance/power profile not current-head qualified | Hub reachability, queue counts, retry schedule, RSSI, reset reason |
| Node reboot | Restore association and pending records, rejoin with a new session | Host recovery and target build; physical restart qualification incomplete | Reset reason, recovery generation, event keys, rejoin/session logs |
| Low battery | No target low-battery action exists | Portable policy/simulator only | Raw externally supplied voltage, calibration flag, backend battery profile |
| Critical battery | No target sleep/notification behavior exists | Portable policy/simulator only | Same as above; do not infer a hardware reading from modeled state |
| Invalid ADC reading | No ADC reader; absent/zero portable sample is Unknown | No target ADC implementation | ADC path is absent; inspect telemetry producer/configuration |
| Full event queue | Reject latest motion, count rejection, preserve reserved capacity | Implemented bounded admission behavior | Store/radio counts, rejected-motion and gap counters |
| Persistence failure | Admission must not be treated as safely recoverable before durable save; report failure/gap according to path | Implemented guarded write path; target power-loss qualification incomplete | NVS return/readback, recovery generation, gap marker, error logs |
| Rejoin failure | Keep association and pending events; retry/recovery owner controls next attempt | Implemented protocol recovery; target outage endurance incomplete | Association load, proof result, session changes, retry state |
| Sleep/wake failure | Not applicable in present target; no target sleep entry exists | Planned | Verify actual firmware revision and absence/presence of sleep calls |
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

- `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/app/node_runtime_adapter.cpp` — target task, PIR polling, health cadence and radio initialization.
- `.../firmware/node/app/node_target_config.hpp` — GPIOs, poll/debounce/stabilization, channel and TX power.
- `.../firmware/node/components/power/power.hpp` and `power.cpp` — portable battery classification, percent estimate, sleep plan and energy model.
- `.../firmware/node/components/runtime/node_runtime.cpp` — event generation and runtime flow.
- `.../firmware/node/components/radio/node_radio.cpp` and `.../shared/include/gs/protocol.hpp` — bounded send queue and retry policy.
- `.../firmware/node/components/persistence/node_recovery_persistence.cpp` — encrypted pending-event recovery record.
- `.../backend/ghar_sajag/battery.py`, `.../tools/sim/local_lab.py` — supplied-sample energy analytics and simulator thresholds.
- `.../tests/cpp/test_main.cpp` and `.../tests/python/test_battery_analytics.py` — host policy and analytics tests.

| EVIDENCE CLASS | CURRENT BOUNDARY |
|---|---|
| IMPLEMENTED | Active PIR polling, bounded event/retry behavior, encrypted recovery persistence, 60-second best-effort health, portable power policy, host-side supplied-data analytics |
| HOST_VERIFIED | Portable policy and battery analytics tests; event/recovery host tests are separate from measuring energy |
| TARGET_BUILD_VERIFIED | Current status records C3 non-HIL/HIL builds for recovery changes; a build proves compilation, not sleep or battery performance |
| HISTORICALLY_PHYSICALLY_VERIFIED | Historical HW-M1.4A resilience/endurance run for its recorded pair/workload only |
| CURRENT_HEAD_PHYSICALLY_VERIFIED | No current-HEAD physical battery/low-power qualification evidence is claimed |
| NOT_YET_PHYSICALLY_QUALIFIED | Current-HEAD battery life, sleep modes, ADC/SOC, brownout recovery, flash wear and production power architecture |
| PLANNED / INCOMPLETE | Light sleep and measurement baseline; GPIO wake/adaptive aggregation and health/retry policy; deep sleep/retained state; calibrated battery telemetry; TX power optimization and long endurance soak |

## Engineer diagnostics

When consumption or reporting changes, correlate reset and wake reason (if
available), boot/session/rejoin, NodeHealth cadence, event cadence, retry
count and due time, pending/in-flight counts, queue rejection, NVS generation
and write errors, heap, logs, RSSI/TX power, and externally measured current.
For battery state, inspect the raw sample and calibration/profile metadata;
the current target has no ADC value to inspect. A frequent radio retry loop
usually points to ACK/session/Hub reachability, while a steadily active CPU is
expected with the present 20 ms poll design.
