# HW-M1 Implementation Plan

## 1. Purpose

This document initializes the isolated `feature/hw-m1` working branch for the
first real target-hardware vertical slice. It uses
`docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md` as the requirement and readiness
basis.

The objective is one ESP32 DevKit hub, one ESP32-C3 node, and one PIR proving:

`PIR -> ESP32-C3 sensing -> NodeMessage -> ESP-NOW -> ESP32 Hub -> ingest /
ACK / dedupe / rules / journal -> Hub Wi-Fi/backend transport -> backend
persistence/read models -> PWA`

## 2. Branch and baseline

- Working branch: `feature/hw-m1`.
- Branch point: `9b391fa`.
- Stable host/PWA reference: `feature/full-pwa-e2e`.
- Historical Phase 3A anchor: `4dcaf99`.
- Qualified Phase 3B checkpoints: `fee5854`, `0e5a9e3`, and `0d6a2fc`.
- `9b391fa` is the documented Phase 3B pause / HW-M1 branch point.

HW-M1 changes may touch shared portable code, backend interfaces, PWA code, or
tests when target integration genuinely requires it, but remain isolated here
until reconciliation and qualification.

## 3. Hardware scope

- One ESP32 DevKit hub.
- One ESP32-C3 node.
- One PIR sensor.
- Defined wiring, power source, board variants, ESP-NOW channel, and security
  configuration recorded as part of bring-up evidence.

## 4. Software architecture boundary

Portable node and hub runtimes, NodeMessage identity, retry/ACK policy, ingest,
dedupe, rules, journal/outbox, backend persistence/read models, and PWA
presentation are the reference software boundary. Physical GPIO, ESP-NOW,
Wi-Fi, target flash, power, watchdog, and board lifecycle are target adapters
and must be proven on hardware rather than inferred from host tests.

## 5. HW-M1 checkpoint breakdown

### HW-M1.0 — Toolchain and board bring-up

- Freeze ESP-IDF/toolchain.
- Build, flash, and capture serial logs for hub and C3.
- Record exact board variants.
- Record wiring and power baseline.

### HW-M1.1 — Real PIR sensing on C3

- Bind GPIO.
- Verify PIR electrical behavior.
- Implement debounce/filtering.
- Create the NodeRuntime event.
- Verify node, session, and sequence fields.

### HW-M1.2 — Real ESP-NOW C3-to-Hub transport

- Set up peer and channel.
- Encode/decode frames.
- Bind send/receive callbacks.
- Demonstrate ACK, retry, duplicate replay, and basic RF behavior.

### HW-M1.3 — Hub target runtime integration

- Integrate ESP-NOW ingress and frame validation.
- Convert NodeMessage and authorize the node.
- Exercise ACK/dedupe, rules, and journal/outbox integration.

### HW-M1.4 — Hub Wi-Fi/backend transport

- Configure development Wi-Fi provisioning and reconnect.
- Use a real backend endpoint.
- Verify backend ingestion/idempotency.
- Establish basic target persistence.

### HW-M1.5 — Full PIR-to-PWA vertical slice

Prove real PIR activity, C3 event, NodeMessage, hub receive/ACK, backend
commit, persistence/read model, and correct PWA presentation.

### HW-M1.6 — Basic resilience

Exercise a deliberately lost ACK, duplicate transmission, WAN unavailable and
reconnect, C3 reboot, hub reboot, offline/online transitions, and absence of
duplicate backend activity.

### HW-M1.7 — Device telemetry

Capture heartbeat, RSSI, real battery/raw-voltage input, and health/offline
state through the existing backend/PWA interfaces.

## 6. Acceptance evidence

Correlate logs and timestamps for each accepted event:

- PIR edge;
- node/session/sequence identity;
- hub receive;
- ACK;
- backend commit;
- persisted event;
- PWA presentation.

Also retain board and wiring notes, toolchain/build identity, serial logs,
RF/channel configuration, reboot/WAN-loss results, telemetry readings, and
duplicate/retry results.

## 7. HW-M1 exit criteria

HW-M1 is complete only when:

- one physical PIR is connected to one C3;
- real PIR activity creates the expected typed NodeMessage;
- real ESP-NOW transports it C3 to hub and the hub returns the correct ACK;
- lost-ACK retry is physically demonstrated;
- duplicate retransmission creates no duplicate domain activity;
- the hub processes the event through normal ingest/rules and real
  Wi-Fi/backend transport;
- the backend persists the event exactly once and the correct PWA state appears;
- heartbeat, offline/online behavior, RSSI, and real battery/raw-voltage
  telemetry are captured;
- C3 reboot, hub reboot/recovery, and WAN loss/reconnect/replay are demonstrated;
- correlated end-to-end evidence is retained; and
- applicable host regression/release gates pass after shared changes, with no
  unresolved defect preventing deterministic repetition of the slice.

## 8. Explicit non-goals

The following are later scope, not HW-M1 blockers: all four nodes, multi-node
RF/concurrency qualification, door/reed sensor, resident physical buttons,
final battery-life calibration, commercial power optimization, long
soak/endurance, full flash wear/retention qualification, production OIDC/TLS/
device PKI, real SMS/push/voice deployment, F14 completion, production
OTA/secure-boot/rollback qualification, enclosure/field installation, and
remaining Phase 3 work.

## 9. Regression policy

`feature/hw-m1` may change shared portable code, backend interfaces, PWA code,
or tests when target integration exposes a genuine requirement. Such changes
remain isolated on this branch; partially working hardware changes are not to
be continuously merged into `feature/full-pwa-e2e`. Existing host behavior
must not be silently broken. Rerun applicable host tests and release gates at
meaningful checkpoints, document intentional contract changes, and require
deliberate integration followed by regression/release qualification.

## 10. Commit/checkpoint policy

Keep commits small and checkpoint-oriented, with board/toolchain and evidence
references in commit messages or accompanying notes. Do not redefine
`4dcaf99`, `fee5854`, `0e5a9e3`, or `0d6a2fc`. A later integration commit must
identify HW-M1 changes and the gates rerun against the integrated baseline.

## 11. Known risks/unknowns

- ESP-NOW channel coexistence, range, loss, and callback timing are unproven.
- PIR voltage behavior, false triggers, wake behavior, and placement are
  unproven.
- Board-specific ADC, power, flash, watchdog, and reset behavior are unproven.
- Target Wi-Fi provisioning, reconnect, backend reachability, and WAN replay
  are unproven.
- Target storage capacity, interruption points, and journal recovery are
  unproven.
- F14, provider delivery, production security, OTA, and later Phase 3 campaigns
  remain outside this milestone.

## 12. Post-HW-M1 next steps

After exit, reconcile all HW-M1 changes against `0d6a2fc`, rerun applicable
host/release and Phase 3 gates, and only then resume notification-provider
storm/failure qualification, restart/recovery, DB/resource fault injection,
EXTENDED/endurance / long-soak validation, and final Phase 3 reconciliation.
