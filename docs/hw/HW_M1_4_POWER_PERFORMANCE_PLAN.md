# HW-M1.4 Power and Performance Baseline Plan

Status: **NOT_BASELINED**

This document reserves measurements for the future HW-M1.4 phase. It does not
change firmware, enable sleep, optimize radio behavior, or claim any physical
measurement. Measurements must use the qualified hardware configuration and
must be repeated after any power/performance change.

## Node measurements

| Metric | Status | Required method/result |
|---|---|---|
| Average current | NOT_BASELINED | Measure over a representative idle/event workload. |
| Idle current | NOT_BASELINED | Measure with runtime active and no PIR event. |
| Sleep current | NOT_BASELINED | Measure only after sleep is implemented; currently not enabled. |
| Event-active current | NOT_BASELINED | Capture PIR processing and radio activity. |
| Event wake/processing duration | NOT_BASELINED | Timestamp PIR transition through send/ACK completion. |
| Radio TX time | NOT_BASELINED | Measure actual ESP-NOW transmission duration. |
| Radio RX/ACK wait time | NOT_BASELINED | Measure application-ACK wait separately from MAC result. |
| Retries per event | NOT_BASELINED | Count retry attempts under normal and controlled loss. |
| Energy per event | NOT_BASELINED | Derive from current/time measurements; do not estimate before measurement. |
| Estimated battery life | NOT_BASELINED | Derive from measured workload and the actual battery. |
| Minimum free heap | NOT_BASELINED | Capture the minimum during boot, PIR, retry, and FOTA. |
| Task stack high-water marks | NOT_BASELINED | Capture each target task under representative load. |
| Queue high-water marks | NOT_BASELINED | Capture ACK, data, control, and send queues. |
| Codec encode/decode time | NOT_BASELINED | Measure bounded NodeMessage and NodeAckMessage operations. |

## Hub measurements

| Metric | Status | Required method/result |
|---|---|---|
| CPU utilization | NOT_BASELINED | Measure owner-task and FOTA-worker load. |
| Minimum free heap | NOT_BASELINED | Capture during data traffic, retries, and FOTA. |
| Task stack high-water marks | NOT_BASELINED | Capture callback-owner and FOTA tasks. |
| Queue high-water marks | NOT_BASELINED | Capture bounded data/control queues. |
| Callback latency | NOT_BASELINED | Measure callback enqueue-to-return duration. |
| Event processing latency | NOT_BASELINED | Measure queue admission through `run_state_once()`. |
| ACK round-trip latency | NOT_BASELINED | Measure NodeMessage through matching NodeAckMessage. |
| Packet loss/retry rate | NOT_BASELINED | Measure under controlled and normal RF conditions. |
| FOTA throughput | NOT_BASELINED | Measure both OTA directions without changing protocol. |
| Long-run heap stability | NOT_BASELINED | Measure during a future endurance run. |

## System and future backend measurements

These are reserved for the later Hub -> backend -> PWA integration; they are
not part of HW-M1.3C:

- motion -> Hub processing latency: **NOT_BASELINED**
- motion -> backend latency: **NOT_BASELINED**
- motion -> PWA visible latency: **NOT_BASELINED**

## Future robustness gates

These are placeholders only and must not be represented as completed:

| Gate | Status |
|---|---|
| 1-hour smoke | NOT_RUN |
| 24-hour run | NOT_RUN |
| 72-hour run | NOT_RUN |
| Reboot/recovery | MANUAL_REQUIRED |
| Repeated FOTA cycles | MANUAL_REQUIRED |
| Event burst | MANUAL_REQUIRED |
| Queue pressure | MANUAL_REQUIRED |
| Intentional packet loss | MANUAL_REQUIRED |

The repeatable automated gate reports these as pending states. Physical
measurements and endurance runs begin only after HW-M1.3C functional
qualification and remain separate from the host/target build PASS.
