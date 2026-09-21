# HW-M1 Implementation Plan

## 1. Purpose and current state

This plan was established for the isolated `feature/hw-m1` branch. The current
HW-M1.4A closure is on `fix/hw-m1-4-node-offline-resilience`. It
uses `docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md` as the software-readiness
basis and the immutable evidence snapshots under `docs/hw/evidence/` as the
physical qualification record.

The original HW-M1 objective is one ESP32 DevKit hub, one ESP32-C3 node, and
one PIR proving:

`PIR -> ESP32-C3 sensing -> NodeMessage -> ESP-NOW -> ESP32 Hub -> ingest /
ACK / dedupe / rules / journal -> Hub Wi-Fi/backend transport -> backend
persistence/read models -> PWA`

The historical HW-M1.3 status was based on implementation commit `1d41864`
and pre-build documentation checkpoint `0546b28`. Current HW-M1.4A status is
on the qualification branch `fix/hw-m1-4-node-offline-resilience`, using
runtime implementation `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9` and
qualified paired artifact `bb34f5eb796d4975c7e8ab788ca638d9828a3996`:

- HW-M1.0 toolchain and board bring-up: **QUALIFIED / PASS**.
- HW-M1.1 real AM312 PIR sensing: **QUALIFIED / PASS**.
- HW-M1.2 real PIR-to-C3-to-ESP-NOW-to-Hub path: **QUALIFIED / PASS**.
- ESP-NOW dual-slot C3 FOTA qualification: **QUALIFIED / PASS**.
- HW-M1.3 Target Runtime Integration: **QUALIFIED / PASS**. Implementation,
  host validation, target build, automated release gate, positive HIL, FOTA
  HIL, negative HIL, clean-production artifact provenance, clean-production
  restore, and final normal PIR smoke all passed.

The status words have strict meanings in this plan:

- **IMPLEMENTED** — source code exists.
- **HOST VALIDATED** — host, simulation, or automated software validation
  passed.
- **HW VALIDATED** — behavior was physically exercised on target hardware.
- **QUALIFIED / PASS** — checkpoint exit criteria were physically
  demonstrated.

Documentation and source inspection do not upgrade a milestone to HW VALIDATED
or QUALIFIED.

## 2. Branch and software baseline

- Current HW-M1.4A qualification branch: `fix/hw-m1-4-node-offline-resilience`.
- Historical HW-M1.3 implementation branch: `feature/hw-m1-runtime-integration`.
- Current HW-M1.4 offline-resilience runtime implementation:
  `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9` (`Fix node operation during Hub outages`).
- Current HW-M1.4A qualified paired artifact:
  `bb34f5eb796d4975c7e8ab788ca638d9828a3996` (`Enforce Hub and C3 firmware pair integrity`).
- Last host-validated implementation commit: `1d41864` (`Implement HW-M1.3
  target runtime integration`).
- Pre-build documentation/resume checkpoint: `0546b28` (`Document HW-M1.3
  checkpoint and resume state`), pushed to
  `origin/feature/hw-m1-runtime-integration`.
- Qualified parent branch: `feature/hw-m1`.
- Implementation branch point: `4645098` (`Document complete HW-M1 resume
  state before runtime integration`).
- Previous fully qualified HW baseline: `50abdce` (`Qualify dual-slot
  ESP-NOW node FOTA`). HW-M1.3 physically qualified artifact provenance is
  `1dfa9c3`; the current documentation HEAD is the closure commit created
  after that provenance checkpoint.
- Earlier HW checkpoint: `3f02822` (`Qualify HW-M1.2 PIR to ESP-NOW hub
  path`).
- HW-M1 planning commit: `997f9ba` (`Initialize HW-M1 implementation plan`).
- Frozen software/PWA branch point: `9b391fa` (`Document Phase 3B pause for
  HW-M1`).
- Stable software/PWA reference: `feature/full-pwa-e2e`.
- Active product code directory:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.

HW-M1 documents the deltas from the frozen software/PWA branch point. It does
not replace the Phase 3A/3B host qualification anchors or duplicate the full
PWA implementation history. When HW-M1 changes are eventually reconciled, the
integrated branch must be compared with the historical qualified host
checkpoint `0d6a2fc` and applicable host/release gates must be rerun.

## 3. Hardware configuration and qualified facts

### Hub

- ESP32 DevKit / ESP-WROOM-32.
- ESP32-D0WD-V3 revision 3.1.
- 4 MB flash.
- STA MAC: `5C:01:3B:BE:B9:F8`.
- CP2102 USB interface during bring-up.
- Current ESP-NOW channel: **1**.

### Node

- ESP32-C3 small board / SuperMini-style.
- 4 MB flash.
- MAC: `14:63:93:C5:D1:58`.
- SmartElex AM312 PIR on **GPIO4**.
- Onboard LED on **GPIO8**, active-low.
- Current ESP-NOW channel: **1**.
- Current configured TX power: `esp_wifi_set_max_tx_power(40)` = **10 dBm**.

### Physical qualification

The AM312 was physically exercised at approximately 12 ft / 3.7 m in the
recorded test setup. The path `PIR -> C3 -> ESP-NOW -> Hub` is physically
qualified at the configuration recorded above. Hub RSSI logging was added and
the cleaned single-line receive logging removed the earlier serial-garbage
symptoms.

The qualification does not establish production range, multi-node RF
behavior, target-runtime integration, backend delivery, or PWA end-to-end
qualification.

## 4. RF findings and rationale

Initial operation used channel 6. The C3 showed instability at the
higher/default configured TX power. Reducing the configured maximum to 10 dBm
(`esp_wifi_set_max_tx_power(40)`) produced substantially more stable behavior,
so 10 dBm is the current qualified baseline. Any increase requires a new
controlled RF qualification.

Channel 6 -> channel 1 was tested because local Wi-Fi-channel congestion was
suspected. Channel 1 produced no meaningful room-to-room range improvement, so
channel congestion was not proven to be the dominant range limitation. Channel
1 remains the current baseline while RF optimization remains open. Do not
describe channel 1 as having solved the range issue.

Further RF work should use controlled placement, measured RSSI, packet-loss
and retry observations, and repeatable distance conditions.

## 5. FOTA qualification and boundary

Both Hub and C3 use 4 MB flash with the custom dual-OTA layout:

- `ota_0`: 1920 KB.
- `ota_1`: 1920 KB.
- Rollback enabled.

The C3 qualification sequence was:

1. USB bootstrap into `ota_0`.
2. FOTA #1: `ota_0 -> ota_1`, reboot, pending validation, mark VALID, PIR
   restored, post-update motion received by Hub — **PASS**.
3. FOTA #2: `ota_1 -> ota_0`, reboot, pending validation, mark VALID, PIR
   restored, post-update motion received by Hub — **PASS**.

Qualified FOTA behavior includes ESP-NOW transfer, application-level FOTA
ACKs, sequencing, retry, duplicate handling, per-chunk CRC32, full-image
CRC32, inactive-partition selection, boot-partition switching, rollback-enabled
boot, and post-boot validation. The full snapshot is
`docs/hw/evidence/HW_M1_FOTA/README.md`.

FOTA is **control-plane** traffic. Normal sensor and business events are
**data-plane** traffic. They must remain separate in implementation and
documentation.

FOTA is not production-secure yet: CRC32 detects corruption but does not prove
authenticity; ESP-NOW peer encryption/key management, signed firmware
authenticity, anti-rollback/version policy, backend firmware distribution, and
Hub self-OTA remain open. The embedded C3 image in the qualification Hub was a
bootstrap test arrangement, not the intended production distribution
architecture.

## 6. Portable architecture ownership boundary

The existing portable production code is the reference architecture for
HW-M1.3; it is not evidence that target integration is complete.

### Node ownership

`NodeRuntime` owns node identity, session identity, event sequence, retained
business events, retry scheduling through `NodeRadio`, `NodeMessage` creation,
transport-result handling, and application-level ACK handling. Its
`next_message()` method is the typed message boundary for a future physical
transport adapter. Its `transport_result()` method receives the physical
transport result, and `acknowledge()` applies application ACK policy.

`NodeRadio` owns pending work and retry timing, not physical RF. A transport
success is not a durable business ACK.

### Hub ownership

`HubRuntime::radio_message_callback(const NodeMessage&, EpochSeconds)` is the
typed ingress boundary. The Hub path validates, authorizes the node/session,
converts and admits the event, then the single owner calls
`HubRuntime::run_state_once()` for journal, coverage, routine/rules and related
processing. The Hub response must be a `NodeAckMessage` with the correct
application ACK semantics.

ESP-NOW callbacks must not mutate `HubRuntime` directly. The callback copies a
bounded frame into a bounded queue; the owner task performs decoding and
business processing. `firmware/hub/runtime/FREERTOS_BINDING.md` is the
authority for this callback/task ownership model. A transport-level ESP-NOW
success must never be documented as equivalent to a durable business ACK.

## 7. Checkpoint plan

### HW-M1.0 — Toolchain and board bring-up — QUALIFIED / PASS

ESP-IDF v6.0.3 build, flash, and serial bring-up were demonstrated for the
ESP32 Hub and ESP32-C3. Board variants, MACs, 4 MB flash and the CP2102
interface were recorded in the HW-M1.2 evidence snapshot.

### HW-M1.1 — Real PIR sensing on C3 — QUALIFIED / PASS

AM312 detection on GPIO4, onboard LED indication, motion qualification and the
approximately 12 ft / 3.7 m observation were physically demonstrated. Battery-
powered node operation was also observed.

### HW-M1.2 — Real ESP-NOW C3-to-Hub path — QUALIFIED / PASS

The real AM312 event path to the Hub was physically demonstrated. The evidence
also records the channel 6 -> 1 experiment, the 10 dBm stability decision,
RSSI logging, and cleaned single-line receive logging. This checkpoint does
not claim portable runtime integration, durable business ACK semantics,
backend/PWA delivery, or production RF optimization.

### Dual-slot ESP-NOW node FOTA — QUALIFIED / PASS

The C3 dual-slot rotation `ota_0 -> ota_1 -> ota_0` was physically
demonstrated through the Hub, with PIR restoration and post-update motion after
both boots. This is a qualified control-plane checkpoint separate from
HW-M1.3 data-plane runtime integration.

### HW-M1.3 — Target Runtime Integration — QUALIFIED / PASS

Source implementation, portable host validation, ESP-IDF target builds,
positive/FOTA HIL, temporary negative-HIL cases, and final clean-production
restore/smoke verification are complete. The final evidence is recorded in
`docs/hw/evidence/HW_M1_3_FINAL_SMOKE/README.md`; the temporary HIL harness
remains isolated on `test/hw-m1-3-negative-hil`.

Implemented scope:

A. **Common bounded wire codec**

- Encode/decode `NodeMessage`.
- Encode/decode `NodeAckMessage`.
- Include protocol magic/version/frame type.
- Use an explicit fixed-width, bounded representation.

B. **ESP32-C3 target integration**

- Bind AM312 GPIO4 using the existing sensing semantics.
- Drive `NodeRuntime` and `NodeRuntime::next_message()`.
- Add the ESP-NOW transport adapter.
- Feed physical send results to `NodeRuntime::transport_result()`.
- Feed application ACKs to `NodeRuntime::acknowledge()`.

C. **ESP32 Hub target integration**

- Receive ESP-NOW frames in the callback.
- Copy into a bounded queue and keep callback work bounded.
- Decode `NodeMessage` in the owner task.
- Call `HubRuntime::radio_message_callback()`.
- Run `HubRuntime::run_state_once()` from the single owner task.
- Encode and send `NodeAckMessage` back to the node.

D. **Plane separation**

Keep FOTA as control-plane traffic, separate from normal sensor/business
data-plane frames and ACK policy.

E. **Validation sequence**

Host codec/runtime tests passed before physical validation. Target logs,
queue/overflow observations, frame results, application ACKs, retained-event
retirement, PIR behavior and post-integration FOTA remain to be captured.

Implementation modules:

- `firmware/common/transport/data_plane_codec.{hpp,cpp}` — bounded portable
  codec and data/control frame classification.
- `firmware/common/transport/session_id.{hpp,cpp}` — fail-closed persistent
  boot-session policy.
- `firmware/node/target/esp32c3/` — qualified C3 constants, NVS session
  provider, static callback queues and sole NodeRuntime owner task.
- `firmware/hub/target/esp32/` — qualified Hub constants, static callback
  queues, session admission and sole HubRuntime owner task.
- `tests/cpp/test_main.cpp` — codec, malformed-frame, ACK/retry/session and
  FOTA separation regressions.

The target adapters remain excluded from the host Makefile, but are now
composed through isolated ESP-IDF product projects under each target's `idf/`
directory. Those projects compile the portable runtime dependencies directly
and preserve the portable business ownership model.

### HW-M1.3B — ESP-IDF target composition/build — TARGET BUILD VALIDATED

ESP-IDF v6.0.3 product compositions now build for the ESP32-C3 node and ESP32
Hub from the existing target adapters and portable dependencies. Both preserve
the qualified dual-slot layout and rollback. Wire-compatible FOTA worker tasks
consume the adapters' bounded control queues; maintenance pauses normal
data-plane work and never routes FOTA through business runtime processing.

HW-M1.3B acceptance criteria:

- **PASS:** C3 ESP-IDF target `esp32c3`; `0xC9430` (824,368 bytes),
  `0x116BD0` (1,141,712 bytes, 58%) OTA headroom.
- **PASS:** Hub ESP-IDF target `esp32`; `0x184E10` (1,592,848 bytes),
  `0x5B1F0` (373,232 bytes, 19%) OTA headroom.
- **PASS:** exact `ota_0`/`ota_1` 0x1E0000 layout, 4 MB flash and rollback
  configuration preserved in both projects.
- **PASS:** C3 AM312 GPIO4, channel 1 and TX API value 40 remain configured.
- **PASS:** `PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++` — 124 checks.
- No hardware qualification is claimed from target build success alone.

Target-build-only evidence is recorded in
`docs/hw/evidence/HW_M1_3_TARGET_BUILD/README.md`.

### HW firmware regression/release gate — IMPLEMENTED

The repeatable gate is invoked from the active product directory with
`make hw-release-gate`. `make hw-validation-fast` provides the host,
configuration, partition, rollback, and structural subset without rebuilding
ESP-IDF targets. The full gate reuses the existing 124 C++ checks, builds both
ESP-IDF targets, validates target metadata and binary presence, checks the
exact 4 MB dual-OTA layout, rollback, qualified C3/Hub settings, FOTA/data
plane separation artifacts, and hard-fails OTA overflow. A configurable
`HW_OTA_WARNING_PERCENT` threshold defaults to 15% and produces a warning
without failing an otherwise in-slot image.

If ESP-IDF v6.0.3 activation or `idf.py` is unavailable, target stages report
`BLOCKED / ENVIRONMENT_MISSING`; they are never silently skipped. The command
reports automated software/target results separately from physical evidence;
its HIL stages remain manual-evidence inputs, power/performance remains
`NOT_BASELINED`, and physical endurance is recorded separately as HW-M1.4A
PASS. The implementation is
`tools/validation/hw_release_gate.py`, with focused self-tests in
`tests/python/test_hw_release_gate.py`.

### HW-M1.3C — Physical target qualification — QUALIFIED / PASS

The negative-HIL portion is recorded in `docs/hw/evidence/HW_M1_3_HIL/README.md`
and the final clean-production restore/smoke is recorded in
`docs/hw/evidence/HW_M1_3_FINAL_SMOKE/README.md`. The required path,
callback/owner-task boundary, Durable ACK retirement, session/retry behavior,
RSSI visibility, and FOTA evidence are represented in the HIL matrix. The
temporary fault-injection harness remains isolated and is not production
runtime source.

### HW-M1.4A — Offline resilience / physical endurance — QUALIFIED / PASS

The physical endurance/resilience qualification is recorded in
`docs/hw/evidence/HW_M1_4A_ENDURANCE/README.md`. The exact qualified
Hub+C3 pair is artifact `bb34f5eb796d4975c7e8ab788ca638d9828a3996`
(`Enforce Hub and C3 firmware pair integrity`), whose runtime behavior is
unchanged from `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9` (`Fix node operation
during Hub outages`).

Decision: **HW-M1.4A physical endurance/resilience qualification PASS for the
bb34f5e paired artifact under the documented HIL workload.** The node was
confirmed continuously alive for at least 19 h 54 min, with a healthy final
firmware state, all accepted motions durably acknowledged, no motion drops,
no PIR rejection, no queue accumulation, no unexpected reset, no reported
runtime error, stable heap evidence, and operation continuing at weak measured
RSSI near the endpoint. This is not a commercial battery-life or production
battery qualification.

The run is useful input to HW-M1.4B but is not a controlled current or energy
baseline. The next milestone is **HW-M1.4B — Power Baseline
Characterization**, which must measure the current architecture before any
low-power redesign. The endurance node used one 18650 cell through the
Robocraze `TIFC00389` shield; product and wiring-boundary detail is in the
dedicated evidence record.

### HW-M1 continuation ordering

The approved order is:

`HW-M1.3B TARGET BUILD VALIDATED`
-> `HW firmware regression/release gate`
-> `HW-M1.3C PHYSICAL FUNCTIONAL QUALIFICATION — QUALIFIED / PASS`
-> `HW-M1.4A OFFLINE RESILIENCE / PHYSICAL ENDURANCE — QUALIFIED / PASS`
-> `HW-M1.4B POWER BASELINE CHARACTERIZATION`
-> repeat the full regression gate
-> future Hub -> backend -> existing PWA integration.

The gate framework does not implement HW-M1.4 power optimization, routine
learning, backend delivery, or PWA functionality.

## 8. HW-M1.3 acceptance and exit criteria

HW-M1.3 may not become QUALIFIED until all of the following are demonstrated
and evidence is captured.

### Host side

- **PASS:** bounded `NodeMessage` codec tests.
- **PASS:** bounded `NodeAckMessage` codec tests.
- **PASS:** malformed, truncated, wrong-magic, wrong-version, wrong-frame-type and
  out-of-range frames are rejected.
- **PASS:** ACK semantics, including durable versus volatile receipt, are preserved.
- **PASS:** retry identity (`node_id`, `session_id`, `sequence_number`) is preserved
  across retries and re-encoding.
- **PASS:** `make cpp-test` with 124 checks, plus the release-gate C++ unit,
  sanitizers, trace, Python, JavaScript, contracts, product/feature, simulator,
  dummy-stream and functional stages.
- **ENVIRONMENT BLOCKED:** complete `make release-gate-final`; localhost HTTP,
  PWA and browser stages cannot create/bind sockets in this sandbox. This is
  not recorded as PASS and must be rerun in the normal local terminal.

### Target composition/build (HW-M1.3B)

- **PASS:** C3 ESP-IDF composition/build with ESP-IDF v6.0.3.
- **PASS:** Hub ESP-IDF composition/build with ESP-IDF v6.0.3.
- **PASS:** OTA-slot fit, exact partition preservation and rollback
  configuration verified for both images.
- **PASS:** Separate FOTA control-plane sender/receiver workers composed with
  the target adapters through bounded queues.

### Target side (HW-M1.3C)

- Real AM312 GPIO4 input reaches the existing sensing semantics and
  `NodeRuntime`.
- A real typed `NodeMessage` crosses ESP-NOW.
- The Hub callback uses a bounded queue and does not mutate `HubRuntime`
  directly.
- The Hub owner task decodes and processes through `HubRuntime`.
- An application `NodeAckMessage` returns to the node.
- A retained event is retired only under the correct ACK policy; transport
  delivery success alone is insufficient.
- Post-integration FOTA still works as separate control-plane traffic.
- PIR functionality remains working after integration and reboot/update
  checks.
- Hardware observations, serial logs, configuration, failures, retries,
  duplicates and queue behavior are captured in durable evidence.

## 9. Open limitations and non-goals

The following remain open unless separately qualified: HW-M1.4B
power-baseline characterization, HW-M1.4C low-power architecture, longer-run
robustness beyond the documented HW-M1.4A run, post-integration
FOTA changes,
RF range optimization,
multi-node RF/concurrency behavior, ESP-NOW peer encryption/key management,
signed firmware authenticity, anti-rollback/version policy, backend firmware
distribution, Hub self-OTA, target Wi-Fi/backend transport, target journal and
power-loss recovery, battery calibration, production security, and the wider
HW-M1.4+ vertical slice. HW-M1.3 is complete and qualified by the combined
evidence record; these remaining items are outside its qualified exit criteria.

Later HW-M1 milestones remain planned for Hub Wi-Fi/backend transport, the
full PIR-to-PWA slice, resilience/recovery, and telemetry. The remaining Phase
3B host work is preserved for later reconciliation and must not be silently
marked complete by HW-M1 evidence.

## 10. Regression and checkpoint policy

Keep commits small and checkpoint-oriented. Do not modify the immutable
evidence snapshots under `docs/hw/evidence/HW_M1_2/` or
`docs/hw/evidence/HW_M1_FOTA/`. Do not redefine historical Phase 3 anchors.

Before integrating HW-M1 changes back toward the stable software/PWA line,
compare with `0d6a2fc`, run applicable host/release gates, document contract
changes, and perform deliberate reconciliation. Partially working HW-M1
changes must remain isolated on the HW branch.
