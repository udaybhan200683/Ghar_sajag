# HW-M1.4 Post-Resilience Roadmap

HW-M1.4A physical endurance/resilience is **QUALIFIED / PASS** for the exact
`bb34f5e` Hub+C3 pair under the documented HIL workload. The result is useful
input, not a controlled power baseline and not a commercial battery-life claim.

The endurance node used one 18650 cell through the Robocraze shield
(`TIFC00389`); authoritative hardware detail is recorded in the HW-M1.4A
evidence README.

## HW-M1.4B — Power Baseline Characterization

Measure the current architecture before changing it. For the Robocraze shield,
also identify the actual output/wiring used for the C3; the existing evidence
does not establish whether its advertised 3-V or 5-V output was used. At
minimum, record:

- battery voltage/current;
- shield battery-side/input voltage;
- shield output actually used for C3;
- C3 supply rail and AM312 VCC;
- load current and shield quiescent current;
- C3 idle current and PIR-only contribution;
- one PIR event and repeated motion workload;
- ESP-NOW transmit plus ACK cost;
- NodeHealth transmission cost;
- Hub-online and Hub-offline retry behavior;
- RSSI/TX-power relationship;
- regulator/power-path efficiency;
- C3 3V3 rail versus battery voltage;
- shield over-discharge cutoff voltage and repeatability;
- recovery/restart threshold;
- whether charger insertion resets the protection state; and
- conversion efficiency and behavior near cutoff.

Carry forward the open question: what component/path caused the 3.3-V domain
to disappear when the cell terminal measured approximately 2.8 V about 15
minutes after node shutdown? The primary test hypothesis is that the shield's
advertised over-discharge protection activated; this remains a hypothesis,
not a qualified fact. Do not presume the cutoff threshold or mechanism before
measurement.

## HW-M1.4C — Low-power sensing/radio architecture

After HW-M1.4B, investigate event-driven PIR wake instead of continuous
approximately 20-ms polling; AM312 powered while the C3 sleeps; GPIO4 wake;
light sleep first; wake/reconnect latency and consumption; immediate first
important-event transmission; local repeated-motion coalescing; a candidate
30–60-second activity aggregation window; duplicate/retrigger suppression;
reduced production NodeHealth cadence or piggybacking; adaptive Hub-offline
retry/backoff; production LED/log reduction; and adaptive ESP-NOW TX power
only after RF-margin measurement.

Only after light-sleep/state behavior is understood, investigate a deep-sleep
extension covering retained node identity, session semantics, sequence
continuity, pending important events, motion episode state, first/last
timestamps, motion count, Hub-offline state, and FOTA/configuration state.

No HW-M1.4C behavior is implemented or qualified by this document.

## HW-M1.4D — Battery telemetry + energy model

Later work should cover battery ADC hardware, calibrated raw battery mV, SOC
estimation, an activity-aware energy model, remaining-hours/days estimation,
calibration across the cell discharge curve, and a fuel gauge/coulomb counter
if ADC/model accuracy is insufficient. Do not estimate remaining battery
percentage from voltage alone.
