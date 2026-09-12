# Parivar Sathi Battery Analytics — Software Design and Validation

## Purpose

Battery analytics estimates **battery percentage, usage rate, remaining runtime, confidence, and abnormal drain** for each hub/node without pretending that the ESP32 can directly measure its own complete supply current.

The C++ semantic `NodeMessage` also carries the optional cumulative power telemetry, and the hub runtime retains the latest accepted telemetry per authenticated node for the future physical/cloud adapter.

The software consumes two kinds of evidence:

1. **Battery voltage** (`battery_mv`) from calibrated ADC/fuel-gauge telemetry.
2. **Cumulative activity counters** from node firmware:
   - deep-sleep time
   - awake time
   - sensor-active time
   - radio TX/RX time
   - TX packets / retries
   - wake count / heartbeat count
   - boot / brownout count

The conversion from time to mAh uses a **per-device power calibration profile**. Those currents must eventually come from bench measurements on the exact board, regulator, sensor, and battery. They are not family/person routine constants.

## Estimation flow

```text
battery_mv + cumulative usage counters
              ↓
per-device measured current profile
              ↓
modeled mAh consumed
              ↓
historical mAh/day + recent mAh/day
              ↓
non-linear Li-ion voltage → state of charge
              ↓
remaining usable mAh (reserve protected)
              ↓
estimated days/hours remaining + confidence
              ↓
normal / learning / high-drain status
              ↓
Devices + Device Health dashboard
```

## State of charge

The host reference uses a conservative piecewise 1S Li-ion voltage curve. It is intentionally **not linear**. Production should replace/tune the curve after real-cell/board characterization or use a proper fuel gauge when required.

## Usage-rate calculation

The firmware counters partition base elapsed time into deep sleep and awake time. Sensor and radio counters are modeled as incremental current above the awake base. This prevents counting a full second of awake current twice simply because radio TX occurred during that second.

For each interval:

```text
mAh = Σ(current_mA × duration_ms / 3,600,000)
rate_mAh_per_day = interval_mAh × 86,400 / interval_seconds
```

The normal prediction uses a median of recent valid interval rates to reduce noise. A sustained recent rate above the calibrated high-drain ratio is flagged as `HIGH`; in that case the remaining-life prediction intentionally uses the higher recent rate so the app does not over-promise runtime.

## Counter reset / reboot handling

Cumulative counters can reset after reboot. If any counter decreases between two samples, that interval is ignored for delta-rate calculation. The new boot segment can still produce a valid low-confidence estimate from its own uptime counters.

## Confidence

Reference policy:

- `LOW`: insufficient observation history
- `MEDIUM`: at least 24 h and at least 3 samples
- `HIGH`: at least 72 h and at least 8 samples

Confidence is shown in the UI alongside the estimate.

## Configurable values

The household low-battery alert threshold is stored in versioned household configuration (`battery_alert_percent`) and is editable under **Settings → Device Schedules → Device power & battery**.

Hardware calibration values (usable capacity and state currents) are device/profile configuration, not household routine settings. The host simulator supports `battery_profile_patch` for validation.

## Dashboard behavior

Device Health and Devices show:

- percentage
- battery voltage
- estimated time remaining
- modeled mAh/day
- confidence
- drain status
- recent wakes/day
- RF retries/day

Battery-only problems **never change the family care banner**. They remain Device Health concerns.

## Current host limitation

The estimator code is real and automated, but the host lab uses synthetic power counters and unverified current calibration. Before pilot/commercial release, measure:

- deep-sleep current
- awake base current
- sensor incremental current
- radio TX/RX incremental current
- ADC/fuel-gauge accuracy
- usable battery capacity across temperature/aging
- charging/UPS behavior
- brownout thresholds

Those measurements replace the simulator calibration profiles; the analytics algorithm and tests remain the same.
