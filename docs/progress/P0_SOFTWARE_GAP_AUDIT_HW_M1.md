# P0 Software-Gap Audit and HW-M1 Transition

**Audit status:** COMPLETE
**Decision:** SOFTWARE READY TO START HW-M1
**Branch:** `feature/full-pwa-e2e`
**Current checkpoints:** `8e570b5` documentation pointer, `0d6a2fc` concurrent
API/household isolation, `0e5a9e3` Reports scalability, `fee5854`
scale/read-path optimization, and permanent Phase 3A anchor `4dcaf99`.

## 1. Executive conclusion

Software is ready to start HW-M1: **YES**. No unresolved host, backend, or PWA
defect blocks starting the first physical vertical slice. Host/reference logic
is substantially implemented and validated, but that evidence does not mean
that ESP32 target adapters, real RF/GPIO/power/flash behavior, provider
integration, or HIL evidence are complete.

The one true remaining software gap is F14, opt-in daily morning summary. It is
not an HW-M1 blocker, but it remains a pilot/commercial P0 blocker because
complete local-date filtering, direct consent enforcement, and finalized
same-day policy-version semantics are still open.

## 2. HW-M1 definition

HW-M1 is one ESP32 DevKit hub, one ESP32-C3 node, and one PIR proving:

`PIR -> C3 sensing firmware -> NodeMessage -> ESP-NOW -> Hub ingest / ACK /
dedupe / rules -> Hub Wi-Fi/backend transport -> backend persistence/read models
-> PWA`

## 3. F01-F14 audit table

| Requirement | Current status | Evidence | HW-M1 blocker | Pilot/commercial blocker |
|---|---|---|---|---|
| F01 — Household profile and caregiver roles | PROVIDER / DEPLOYMENT PENDING | Host CRUD, membership, and tenant-scope tests pass; production OIDC/session/database deployment is absent. | NO | YES |
| F02 — Resident consent and privacy controls | HARDWARE / HIL PENDING | Host consent withdrawal and privacy gating pass; sensor-side collection stop and retention/deletion are not physically proven. | NO | YES |
| F03 — Kit provisioning and installation verification | HARDWARE / HIL PENDING | Host onboarding, capability, duplicate-ID, and installation gates pass; physical board identity, GPIO, RF placement, and installed-home verification remain. | YES | YES |
| F04 — Configurable morning routine | HARDWARE / HIL PENDING | Versioned policy and host rules pass; target atomic configuration application is not evidenced. | NO | YES |
| F05 — Morning activity evidence | HARDWARE / HIL PENDING | Simulator/backend event path and projections pass; real PIR, debounce, placement, and RF delivery remain. | YES | YES |
| F06 — Explicit “I’m OK” check-in | HARDWARE / HIL PENDING | Host event and feedback logic pass; physical button input, latency, and usability remain. | NO | YES |
| F07 — Call family request | PROVIDER / DEPLOYMENT PENDING | Durable incident, routing, offline replay, and host cancellation pass; real push/SMS/voice delivery remains. | NO | YES |
| F08 — Missing morning activity workflow | HARDWARE / HIL PENDING | C++ rules and connected scenarios pass; real sensor coverage/history and target restart behavior remain. | NO | YES |
| F09 — Main-door history and quiet notice | HARDWARE / HIL PENDING | Host rules and connected tests pass; physical reed installation and field timing remain. | NO | YES |
| F10 — Away, pause, and visitor modes | HARDWARE / HIL PENDING | Host mode semantics pass; persistent target control and production authorization remain. | NO | YES |
| F11 — Caregiver dashboard and timeline | COMPLETE + VERIFIED | Backend/read models, PWA/API/frontend tests, Playwright 86/86, and Phase 3B isolation qualification pass. | NO | NO |
| F12 — Acknowledgement and resolution | PROVIDER / DEPLOYMENT PENDING | Claim/ack/resolve and host conflict behavior pass; production roles, transactional CAS, and concurrency deployment remain. | NO | YES |
| F13 — Backup routing and delivery visibility | PROVIDER / DEPLOYMENT PENDING | Host routing/status model passes; real workers, retry leases, provider ambiguity, and phone receipt remain. | NO | YES |
| F14 — Opt-in daily morning summary | SOFTWARE GAP | Host helper is opt-in/idempotent but lacks complete local-date filtering, direct consent enforcement, and finalized same-day policy-version semantics. | NO | YES |

Host mappings and validation coverage do not equal physical or commercial
completion.

## 4. E01-E10 audit table

| Requirement | Current status | Evidence | HW-M1 blocker | Pilot/commercial blocker |
|---|---|---|---|---|
| E01 — Node health, battery, and coverage | HARDWARE / HIL PENDING | Host health states, heartbeat thresholds, coverage, and synthetic telemetry are tested; real ADC/battery/RSSI/thermal evidence is absent. | YES | YES |
| E02 — Reliable transport and duplicate handling | HARDWARE / HIL PENDING | NodeMessage identity, retry, ACK classes, durable retirement, hub dedupe, and backend idempotency are host-tested; real ESP-NOW transport is absent. | YES | YES |
| E03 — Local operation during internet failure | HARDWARE / HIL PENDING | Host offline/replay logic exists; router/WAN separation, RF coexistence, target flash, and reboot evidence are absent. | YES | YES |
| E04 — Hub/cloud/app connectivity and freshness | PROVIDER / DEPLOYMENT PENDING | Host freshness/read models exist; production broker/stream, deployment, and phone reachability remain. | NO | YES |
| E05 — Persistence, recovery, and bounded storage | HARDWARE / HIL PENDING | Relational schema and host migration/restart tests pass; target journal, compaction, refill, and power-loss recovery remain. | YES | YES |
| E06 — Trusted time and boundary handling | HARDWARE / HIL PENDING | Trusted/untrusted clock and boundary rules pass; authenticated target time and reboot/DST evidence remain. | NO | YES |
| E07 — Versioned configuration and atomic application | HARDWARE / HIL PENDING | Host schema/version/stale-version checks pass; authenticated command envelopes and crash-safe target apply remain. | NO | YES |
| E08 — Security, privacy, and tenant isolation | PROVIDER / DEPLOYMENT PENDING | Host cross-tenant and unauthorized mutation tests pass; production TLS/OIDC, key management, secure boot, rotation, and deployment remain. | NO | YES |
| E09 — Signed firmware update and recovery | HARDWARE / HIL PENDING | Host manifest/board/rollback policy seams are tested; actual OTA, partitions, bootloader rollback, watchdog, and interrupted-update recovery remain. | NO | YES |
| E10 — Verification, observability, and release evidence | HARDWARE / HIL PENDING | Host contracts, tests, Playwright, sanitizers, and release-gate evidence are strong; physical diagnostics and pilot evidence remain. | NO | YES |

## 5. Node firmware readiness

Portable sensing, `NodeRuntime`, NodeMessage identity, retry timing, ACK
classes, node-store policy, heartbeat/battery fields, battery classification,
configuration validation, and radio/storage seams exist and are host-tested.

Target work remains: ESP32-C3 GPIO/PIR implementation and debounce; PIR
electrical behavior, wake behavior, and placement; ADC/battery measurement and
calibration; ESP-NOW send/receive callbacks; peer/channel/security
configuration; target flash/NVS persistence; board identity/provisioning; and
watchdog/reset/power evidence.

## 6. Hub firmware readiness

Peer/session authorization, NodeMessage conversion, ingest admission, ACK and
dedupe policy, journal/cloud outbox policy, coverage, rules, versioned config,
trusted-time model, resident semantic events, and cloud-sync retry semantics
exist as portable logic and host tests.

Target work remains: ESP-NOW receive/frame/ACK adapter; radio/channel/security
initialization; ESP32 Wi-Fi provisioning and reconnect; HTTPS/MQTT/backend
transport; target journal/flash/compaction/power-loss recovery; physical
resident controls/feedback where applicable; task/queue/watchdog binding; and
hub board identity/lifecycle.

## 7. End-to-end vertical-slice readiness

| Link | Status | Finding |
|---|---|---|
| PIR -> C3 | TARGET ADAPTER NEEDED | Portable sensing exists; ESP32-C3 GPIO/PIR implementation and HIL evidence do not. |
| C3 -> ESP-NOW | TARGET ADAPTER NEEDED | NodeMessage/session/sequence/retry/ACK contracts exist; physical ESP-NOW adapter does not. |
| ESP-NOW -> Hub | TARGET ADAPTER NEEDED | Hub ingest/authorization/dedupe/ACK logic exists; physical receive/frame adapter does not. |
| Hub -> backend | TARGET ADAPTER NEEDED | Cloud outbox/backend ingest exist; real Wi-Fi and transport adapters do not. |
| Backend -> PWA | READY | Persistence/read models, HTTP API, PWA, and browser validation are implemented and tested. |

## 8. Tasks required BEFORE HW-M1

No product-code blocker must be completed before HW-M1 starts. Before setup:

- Freeze board, PIR, GPIO, and power choices.
- Freeze the first-slice ESP-NOW channel/security approach.
- Define wiring and node/hub identity provisioning.
- Define minimum evidence: PIR edge, C3 event, NodeMessage identity, hub
  receive/ACK, backend commit, persisted event, and PWA display.
- Select target ESP-IDF/toolchain versions.
- Prepare the test household/device configuration and backend endpoint.

## 9. Tasks to implement DURING HW-M1

- Implement C3 PIR/GPIO sensing and debounce.
- Implement node ESP-NOW transport, retry, and ACK.
- Implement hub ESP-NOW RX, frame validation, and ACK.
- Wire real heartbeat, battery, and RSSI telemetry.
- Wire hub Wi-Fi/backend transport and target persistence/journal.
- Prove duplicate and lost-ACK retry behavior over RF.
- Prove one real PIR event reaches the PWA.
- Exercise WAN loss and reboot.
- Capture logs, toolchain, board, channel, and wiring evidence.

## 10. Tasks that can wait until AFTER HW-M1

- Production OIDC/TLS/device identity/security deployment.
- Push/SMS/voice workers and delivery ambiguity handling.
- Production claim/ack/resolve concurrency/CAS.
- F14 completion.
- Deeper flash retention and power-loss recovery.
- Multi-node RF qualification.
- OTA signature, rollback, watchdog, and interrupted-update recovery.
- Battery, thermal, coverage, field-installation, and accessibility qualification.
- Remaining Phase 3 notification storm/failure, restart/recovery, DB/resource
  fault injection, EXTENDED/endurance, and final Phase 3 qualification.

## 11. Documentation interpretation / overstatement corrections

“24/24 P0 mapped” means traceability coverage, not 24/24 fully implemented.
“Host implemented/validated” describes host/reference seams and tests; it does
not mean physical ESP32/HIL completion. Target firmware, provider integration,
OTA, physical RF, flash, power, and field qualification must not be inferred
from host mappings or module presence.

## 12. Audit decision / next milestone

**Decision: HW-M1 may start.** The next milestone is the single real-device
vertical slice defined above. Phase 3B remains IN PROGRESS; its remaining
notification-provider storm/failure qualification, restart/recovery, DB/resource
fault injection, EXTENDED/endurance, and final Phase 3 qualification remain
unchanged.
