# HW-M1.4A Offline Resilience / Physical Endurance Closure

**Status:** QUALIFIED / PASS

**Decision:** HW-M1.4A physical endurance/resilience qualification PASS for
the `bb34f5e` paired artifact under the documented HIL workload.

**Date:** 2026-09-21

This record closes the physical endurance/resilience portion of HW-M1.4A. It
does not modify the qualified firmware, runtime source, tests, build scripts,
or earlier historical evidence. The exact physical firmware pair was:

- `bb34f5eb796d4975c7e8ab788ca638d9828a3996` — `Enforce Hub and C3 firmware pair integrity`;
- runtime implementation: `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9` — `Fix node operation during Hub outages`.

There was no runtime logic change between `cfcee97` and `bb34f5e`. The
physically qualified artifact is the `bb34f5e` Hub+C3 pair.

## Test configuration and scope

- Hub: ESP32 DevKit, continuously USB powered, ESP-NOW channel 1.
- Node: ESP32-C3 with AM312 PIR on GPIO4, PIR continuously powered from 3V3,
  one 18650 Li-ion cell through a Robocraze 18650 Lithium Battery Holder
  Shield Module Micro USB (SKU `TIFC00389`), and no USB attached to the node
  during the endurance run.
- Firmware: ESP-IDF v6.0.3, exact `bb34f5e` paired artifact.

Product URL: <https://robocraze.com/products/18650-lithium-battery-holder-shield-module-micro-usb>

The seller specification identifies this as a single-18650 holder with
built-in overcharge and over-discharge protection, advertised charging current
of 0.5 A, and advertised outputs of 3 V @ 1 A and 5 V @ 2 A. The available
project evidence does not unambiguously identify which advertised shield
output powered the C3; this record therefore states only that the C3 was
powered through the shield's output/power path. Exact shield-output wiring is
carried into HW-M1.4B verification.

This is an endurance/resilience test of the current unoptimized runtime. It is
not a commercial battery-life or production battery qualification.

## Battery and endurance checkpoints

| Elapsed time | Cell terminal |
|---|---:|
| Start | approximately 4.11 V |
| approximately 8 h 30 min | approximately 3.80 V |
| approximately 10 h | approximately 3.71 V |
| 12 h | 3.64 V — 12-hour endurance PASS |
| 14 h 30 min | approximately 3.57 V |
| 18 h | approximately 3.40 V |

The final confirmed alive timestamp was `2026-09-21 20:01:20 +05:30`, with
`uptime_ms = 71640009`, approximately 19 h 54 min. Therefore:

> The node was confirmed alive for at least 19 h 54 min.

This does not assert an exactly timestamped shutdown at 19 h 54 min; the node
stopped shortly afterward and the exact shutdown time was not recorded.

Approximately 15 minutes after the node stopped operating, the cell terminal
was approximately 2.80 V, the C3 3V3 rail was approximately 0 V, and AM312
VCC was approximately 0 V. The battery/power supply was subsequently
disconnected from the C3.

The node was powered through a Robocraze 18650 battery shield whose seller
specification advertises over-discharge protection. The observed loss of the
node power domain near the low-battery endpoint is therefore consistent with
activation of the shield's over-discharge protection. However, the exact
cutoff mechanism and threshold were not independently verified; do not
describe this as a confirmed protection cutoff at 2.8 V.

## Final health evidence

Timestamp: `2026-09-21T20:01:20+05:30`

```text
NodeHealth:
schema=1
session=26
health_seq=1194
uptime_ms=71640009
reset=1
pir_raw=0
pir_edges=3090
pir_ok=1545
pir_rejected=0
store_full=0
motion_drop=0
priority_rejected=0
sensing_live=3581492
runtime_live=3581492
retained=0
oldest_seq=0
in_flight=0
tx=2746
mac_ok=2741
mac_fail=5
durable_ack=1545
volatile_ack=0
retry=5
backoff=0
breadcrumb=3
error=0
heap=212956
min_heap=205356
maintenance=0
RSSI=-85
CH=1
```

Immediately preceding successful motion event: `2026-09-21T20:00:43+05:30`;
`session=26`, `seq=1545`, `app_ack=0`, `ack_send=ESP_OK`, `RSSI=-89`, `CH=1`.

## Evidence-backed conclusions

- `session` remained 26 and `reset` remained 1. No unexpected runtime reboot
  occurred during the endurance run.
- `pir_edges=3090`, `pir_ok=1545`, and `pir_rejected=0`; no qualified PIR
  motion was rejected. The approximately 2:1 edge/event ratio is only noted
  as consistent with the observed qualified PIR high/low transition behavior.
- `pir_ok=1545` equals `durable_ack=1545`; all accepted PIR motion events were
  durably acknowledged. `retained=0`, `in_flight=0`, `motion_drop=0`,
  `store_full=0`, and `priority_rejected=0` show no final event backlog.
- `tx=2746`, `mac_ok=2741`, `mac_fail=5`, and `retry=5` show five MAC
  failures matched by five retries. Operation continued at approximately
  -85 to -89 dBm near the endpoint; this is not an RF range-limit
  qualification.
- Final `heap=212956` and `min_heap=205356` remained stable against earlier
  checkpoints. No evidence of progressive heap/resource leakage was observed
  during the endurance run; this is not proof that no leak can ever exist.
- `sensing_live=3581492` and `runtime_live=3581492` over approximately
  71640 seconds indicate approximately 50 runtime/sensing iterations per
  second, or approximately 20 ms per iteration. The approximately 10-second
  HIL motion spacing was operator pacing, not the firmware sensing interval.

## Qualification boundary and next work

The result records: confirmed alive for at least 19 h 54 min; natural
low-voltage electrical endpoint afterward; healthy final firmware state; all
accepted motions durably acknowledged; no motion drops or PIR rejection; no
queue accumulation; no unexpected reset; no reported runtime error; stable
heap evidence; and operation at weak measured RSSI near the endpoint.

The run used the current unoptimized architecture: an essentially continuous
runtime/sensing loop, continuously powered PIR, regular NodeHealth traffic,
frequent deliberate motion, ESP-NOW traffic/ACKs, debug/HIL instrumentation,
and no production sleep strategy. Thus “approximately 19 h 54 min confirmed
operation under this HIL workload” is not expected product battery life.

Next milestone: **HW-M1.4B — Power Baseline Characterization**. Measure before
changing architecture: battery cell voltage/current; shield battery-side/input
voltage; the shield output actually used for C3; C3 supply rail; AM312 VCC;
load current; C3 idle and PIR-only current; one PIR event; ESP-NOW transmit
plus ACK cost; repeated motion; NodeHealth cost; Hub-online and Hub-offline
retry behavior; RSSI/TX-power relationship; shield quiescent current;
conversion efficiency versus cell voltage/load; shield over-discharge cutoff
voltage and repeatability; recovery/restart threshold; whether charger
insertion resets protection; and behavior near cutoff.

Open electrical question:

> Did the battery shield's advertised over-discharge protection cause the
> node power-domain shutdown when the cell terminal measured approximately
> 2.8 V about 15 minutes after node shutdown?

This is a HW-M1.4B test hypothesis, not a qualified fact. The exact cutoff
threshold and mechanism remain open.

Do not answer this question in HW-M1.4A.
