# HW-M1.4B — Minimal Pre-Optimization Power Baseline

**Status:** PLANNED / READY TO START

**Purpose:** Establish a repeatable BEFORE measurement for the current
`bb34f5e` software architecture so future low-power software changes can be
compared quantitatively.

This is a documentation and controlled physical measurement plan. It does not
change firmware, runtime architecture, radio settings, NodeHealth cadence, or
power behavior. Use the existing qualified `bb34f5e` Hub+C3 pair and the
HW-M1.4 runtime implementation `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9`
unless a separate measurement-only artifact is explicitly approved later.
Do not rebuild or modify the qualified artifact as part of this plan.

The Robocraze TIFC00389 fixture used during HW-M1.4A is a repeatable prototype
test fixture for these measurements, not a selected or frozen commercial Ghar
Sajag power architecture. Absolute current and battery-duration results are
not commercial product specifications.

## 1. Prototype fixture boundary

The HW-M1.4A endurance node used one 18650 cell through the Robocraze
**18650 Lithium Battery Holder Shield Module Micro USB**, SKU `TIFC00389`.
The seller advertises overcharge/over-discharge protection, a 0.5-A charging
current, and 3-V @ 1-A and 5-V @ 2-A outputs. The historical HW-M1.4A record
is authoritative for what was used in that run.

This fixture is not:

- a frozen commercial hardware choice;
- a required future power module;
- a software architecture dependency;
- the basis for hard-coded battery thresholds; or
- a prerequisite for implementing low-power firmware.

The final product may use a different battery, protection circuit, charger,
regulator/buck-boost, PMIC, or power-path architecture. The exact fixture
output/wiring may be recorded when easily and safely observed, but full
Robocraze topology or cutoff characterization is not an HW-M1.4B
software-baseline blocker.

## 2. B0 — Measurement-path verification

Perform B0 before current measurements. Its purpose is to verify enough of
the physical wiring to insert the current meter safely and identify the
measurement boundary.

Record:

- where current is measured and whether the boundary is cell-side,
  shield-input-side, shield-output-side, or C3-supply-side;
- supply voltage at that boundary;
- C3 supply voltage;
- C3 3V3;
- PIR/AM312 supply voltage; and
- polarity and any intermediate regulator, adapter, jumper, or rail visible
  in the path.

If easy and non-destructive, record which advertised shield output is being
used. Do not infer it from the product page. Do not open, desolder, puncture,
or modify the fixture merely to complete B0. If output identity is not
visible, record it as unknown and proceed with the defined measurement
boundary rather than making it a full topology investigation.

## 3. Minimal BEFORE measurement set

Use the same fixture, board placement, battery identity, Hub state, channel,
configured TX power, instrument setup, and test duration when repeating these
tests after HW-M1.4C1. Record a defined interval and raw logs for every test.

| Test | Controlled workload | Required record |
|---|---|---|
| **B0** | Measurement-path verification | Measurement boundary, supply voltage, C3 supply, C3 3V3, PIR VCC, polarity, and optional easy/non-destructive shield-output identity. |
| **B1** | C3 + PIR operating normally; Hub online; no intentional motion; current `bb34f5e` behavior | Average node current over a defined interval, boundary voltage, C3 supply, C3 3V3, PIR VCC, duration, and instrument limits. |
| **B2** | Normal operation long enough to include existing periodic NodeHealth behavior; cadence unchanged | Average current and correlated NodeHealth/log activity over the defined interval. |
| **B3** | Defined, repeatable number of PIR events at recorded pacing with Hub online | Accepted PIR events, TX, ACK, MAC failures, retries, average current, and correlated logs/RSSI. |
| **B4** | Hub OFF for a controlled short interval, then restored | Average node current, retry/backoff, retained/in-flight behavior, outage/recovery time, and normal recovery after Hub restoration. |

B1–B4 are the mandatory minimal baseline and must be reusable as BEFORE/AFTER
comparisons against HW-M1.4C1. The approximately 10-second motion spacing
used during HW-M1.4A was operator pacing, not the firmware sensing interval;
choose and record a repeatable B3 pacing interval.

Do not reduce TX power, enable sleep, stop continuous sensing, change
NodeHealth cadence, change retry/backoff, coalesce events, or add runtime
measurement hooks in this plan. The goal is to measure existing behavior,
not to create a measurement-specific architecture.

## 4. Instrumentation and safety

A standard DMM is suitable for steady voltage and slower average-current
measurements when its range, burden voltage, and sampling behavior are
appropriate. It must not be treated as an accurate measurement of short
ESP-NOW current transients unless its capabilities demonstrate that.

For ordinary DMM current measurement:

- connect the meter in series with the load;
- verify the correct current jack and range before connecting;
- start at the highest safe current range;
- account for DMM burden voltage and its effect on the supply;
- never place a meter in current mode directly across the 18650; and
- never allow meter leads to short the cell.

For radio transients, use a suitable power analyzer, current logger, or
shunt/differential measurement with known bandwidth and sampling rate when
available. Record instrument model, range, burden/shunt, sample rate,
bandwidth, and whether each value is instantaneous, peak, average, or
integrated.

Do not deliberately over-discharge the prototype 18650. Stop if the cell or
fixture shows swelling, heating, odor, unstable voltage, abnormal current,
or other unsafe behavior.

## 5. Standard test record and later calculations

Use one row per run and retain raw serial/log captures separately:

| Field | Required value |
|---|---|
| Test ID | B0–B4 |
| Date/time | ISO 8601 with timezone |
| Firmware artifact | Exact Hub+C3 pair and provenance |
| Battery identity | Cell make/model/capacity/condition if known |
| Measurement boundary | Exact insertion point and instrument |
| Voltage | Boundary supply, C3 supply, C3 3V3, PIR VCC |
| Current | Idle/average; peak only if instrument supports it |
| Test duration | Start/end and elapsed interval |
| PIR events | Accepted count and pacing |
| TX/ACK/retry | Counts from logs |
| Retained/in-flight | Counts during B4 and recovery |
| RSSI/Hub state | As applicable |
| Notes/result | Anomalies, safety, limitations |

For later comparison, at one defined power boundary:

```text
P(t) = V(t) × I(t)
average power = (1 / duration) × integral(P(t) dt)
energy = integral(P(t) dt)
Wh ≈ average power (W) × duration (h)
mAh ≈ integral(I(t) dt) when I is in mA and time is in hours
```

State the sampling/approximation method. Do not convert these baseline values
into commercial battery life, remaining percentage, or a 2.8-V software
threshold.

## 6. Minimal HW-M1.4B exit gate

HW-M1.4B is sufficient to start software optimization when:

- the measurement boundary is known and safe;
- baseline idle/no-motion current is recorded;
- baseline normal/NodeHealth workload is recorded;
- baseline controlled PIR workload is recorded;
- baseline Hub-offline/recovery workload is recorded;
- instrumentation limits and uncertainty are documented; and
- B1–B4 are repeatable for future BEFORE/AFTER comparison.

The following are explicitly not required before HW-M1.4C1:

- full shield cutoff characterization;
- exact over-discharge threshold or hysteresis;
- shield recovery or charger-reset testing;
- repeated full-discharge testing;
- final commercial power-path selection;
- final regulator-efficiency qualification; or
- final battery-life qualification.

HW-M1.4B remains **PLANNED / READY TO START** until the minimal dataset is
captured. It must not be marked RUNNING or PASS from documentation alone.

## 7. HW-M1.4C1 — Low-Power Software V1 start gate and scope

After B0 measurement-path verification and the B1–B4 baseline are captured,
HW-M1.4C1 low-power software implementation may start immediately. Measurements quantify improvement,
detect regressions, and help tune parameters; they do not determine whether
low-power work is necessary. The core direction is already established by
the current architecture and HW-M1.4A evidence.

The intended first increment is:

1. Replace continuous approximately 20-ms PIR polling with an event/wake-
   oriented design where technically feasible.
2. Keep PIR sensing available while reducing MCU active time.
3. Implement LIGHT SLEEP first.
4. Investigate/implement GPIO4 PIR wake.
5. Keep the first meaningful motion event immediate.
6. Suppress/coalesce repeated PIR activity locally instead of generating
   unnecessary ESP-NOW transactions.
7. Keep PIR retrigger/debounce semantics distinct from the longer
   activity-aggregation window.
8. Reduce production NodeHealth radio traffic and/or piggyback health on
   ordinary events where safe.
9. Add adaptive Hub-offline retry/backoff.
10. Reduce unnecessary production LED/debug activity.

These changes are not implemented by this documentation task.

## 8. HW-M1.4C2 — Deep Sleep / Retained-State Optimization

Deep sleep is a later iteration. Before implementation, design session
semantics, sequence continuity, pending critical events, activity aggregation
state, configuration/FOTA state, offline state, and retained/persistent state.
Do not treat every deep-sleep wake as a normal reboot without designing these
semantics.

## 9. HW-M1.4D — Battery Telemetry + Energy Model

HW-M1.4D remains future battery telemetry and energy-model work. Generic
software concepts may eventually include `battery_mv`, `battery_state`,
`low_battery`, and `power_good` / charging state only if supported by the
selected hardware. Do not hard-code Robocraze-specific behavior or a 2.8-V
threshold. Final SOC and remaining-life modeling must be calibrated to the
selected commercial battery and power path.

## 10. Parallel hardware milestones

### HW-PWR-PROT — Prototype Power-Path Characterization

This separate, optional hardware activity may characterize the current
Robocraze prototype fixture: shield quiescent current, conversion efficiency,
3-V/5-V output behavior, over-discharge cutoff behavior, recovery behavior,
and charger-reset behavior. It is useful prototype knowledge, but it is not a
blocker for HW-M1.4C1 and does not select the commercial product hardware.

### HW-PWR-COMM — Commercial Power Architecture Qualification

After commercial hardware is selected, qualify the production battery,
protection, charging, low-Iq regulator/buck-boost/PMIC, efficiency, quiescent
current, cutoff/recovery, thermal behavior, lifecycle, safety, and enclosure
integration. This task does not select final commercial hardware.
