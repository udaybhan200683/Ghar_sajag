# Feature Implementation Status and Remaining Gaps at `0608e2a`

> **Point-in-time audit snapshot at `0608e2a` (`0608e2ad009c73b0edd6b35e11abdb98e6e8299b`).** This document does not automatically describe later commits. **IMPLEMENTED != PHYSICALLY QUALIFIED. TARGET BUILD PASS != PHYSICAL HIL PASS. HISTORICAL PASS != CURRENT HEAD QUALIFICATION.**

## 1. Executive Summary

The repository contains substantial product design, backend/PWA functionality, a working one-C3-to-Hub physical activity path, extensive host multi-Node/security tests, and newly added target code for authenticated commissioning and runtime traffic. These parts do not yet form a production-ready, end-to-end home product.

At this snapshot, `0608e2a` adds Hub/C3 production owner-task routing for commissioning, authenticated rejoin, and application-layer AEAD traffic. The new paths have target-build evidence, not physical qualification. Production credential provisioning and an installer-to-Hub commissioning entry point are incomplete; the default HIL image still uses the earlier Phase-1 transport path.

The main product gaps are production-usable identity provisioning and Add Device integration; restart-correct event persistence on the live Node/Hub paths; physical verification of authenticated target traffic and representative multi-C3 behavior; safe, authorized versioned FOTA; and the real Hub-to-backend-to-caregiver-PWA connection. Battery sleep/wake optimization is a separate next major track.

## 2. Current Provenance

| Field | Value |
|---|---|
| Branch | `feature/hw-m1-4-hil-phase2` |
| HEAD | `0608e2ad009c73b0edd6b35e11abdb98e6e8299b` — `Wire authenticated Hub and C3 target runtime paths` |
| Last physically qualified firmware | `7bc2a33` |
| Latest physical evidence | `evidence/hil/runs/20260924T094521.398370Z` |

The `0608e2a` authenticated target path must not be described as physically qualified. The latest physical evidence records firmware provenance from `7bc2a33`.

## 3. Implemented Features

| Feature | Implementation status | How it works; important source | Important commits | Verification level and limitations |
|---|---|---|---|---|
| One-C3 PIR activity to Hub | **PARTIAL_TARGET_INTEGRATED** | C3 polls PIR on GPIO4, creates a NodeRuntime event and sends it over ESP-NOW; Hub ingests and acknowledges it. Fixed prototype identity/configuration remains in `firmware/node/target/esp32c3/node_target_config.hpp` and the Node/Hub target runtime adapters. | `3f02822`, `1d41864`, `cfcee97` | The one-Hub/one-C3 path was **PHYSICAL_HIL_VERIFIED** at `7bc2a33`. The new authenticated production path at `0608e2a` is only target-built. |
| Node event queue, retry and ACK matching | **PARTIAL_TARGET_INTEGRATED** | `firmware/node/runtime/node_runtime.*` holds bounded event state and retries until ACK. Hub ingest/journal handles admission and duplicate event identity in `firmware/hub/components/ingest/` and `firmware/hub/components/storage/journal.*`. | `fc0776b`, `613dd45`, `e9bee1a` | Host recovery is **HOST_VERIFIED**; one-pair event/ACK behavior is physically exercised. Active target retained/in-flight state is not restored from the Node recovery record. |
| Hub local runtime and journal | **PARTIAL_TARGET_INTEGRATED** | `firmware/hub/runtime/hub_runtime.*` connects ingest, rules/state and bounded journal. Target constructs a runtime with bounded ingress/journal capacities. A journal NVS slot adapter exists, but the active target journal is volatile and does not attach that persistence. | `7bffce5` and earlier Hub runtime work | Target build and one-pair functional path exist. Power-loss journal/dedupe durability is **NOT_VERIFIED**. A target ACK currently reflects in-memory journal acceptance, not power-loss durability. |
| Commissioning cryptography and transcript | **PARTIAL_TARGET_INTEGRATED** | `firmware/common/security/commissioning_protocol.*`, `commissioning_wire.*` implement P-256 signing/ECDH, HKDF-SHA256, HMAC-SHA256 and AES-256-GCM. Transcript binds exact Node identity, Home/Hub and logical assignment. | `8d1ea28`, `af9fe2d`, `5b71c3a`, `7a962a3` | Protocol and tamper/replay cases are **HOST_VERIFIED**. ESP-IDF crypto adapters and target owners compile. Actual target pairing is **NOT_YET_PHYSICAL**. |
| Hub/C3 authenticated target owner paths | **PARTIAL_TARGET_INTEGRATED** | `firmware/hub/target/esp32/hub_security_link.*`, `hub_runtime_adapter.cpp`, and `firmware/node/target/esp32c3/node_security_link.*`, `node_runtime_adapter.cpp` route commissioning, rejoin and runtime frames through application security in the non-HIL production owner path. | `0608e2a` | **TARGET_BUILD_VERIFIED**, not physically exercised. Installer caller, usable provisioned production identities, target rejoin, and target multi-Node proof remain open. HIL continues to use the Phase-1 path. |
| Runtime AEAD and replay protection | **PARTIAL_TARGET_INTEGRATED** | `firmware/common/security/runtime_frame_security.*` protects event, health and ACK frames with application-layer AES-GCM, session/sequence metadata and replay checks. ESP-NOW peer encryption is disabled; the application layer supplies frame protection. | `d09071b`, `0608e2a` | Host multi-Node frames are **HOST_VERIFIED**; target path is **TARGET_BUILD_VERIFIED** only. No physical authenticated runtime proof at this HEAD. |
| Bounded Node registry and revocation | **PARTIAL_TARGET_INTEGRATED** | `firmware/hub/components/registry/node_registry.*` supports enrollment, lookup, rejoin, remove/replace, revocation and quarantine. Registry persistence is in `registry_persistence.*`; target Hub security link restores/saves a bounded snapshot. Capacity pressure preserves revocation state and fails closed. | `097f74c`, `18d66b3`, `3e87e90`, `842deb8`, `0608e2a` | Host lifecycle/capacity tests are **HOST_VERIFIED**; target repository path is **TARGET_BUILD_VERIFIED**. Target persistence and physical admission are not qualified. |
| Association persistence and boot-time rejoin | **PARTIAL_TARGET_INTEGRATED** | `firmware/common/security/association_persistence.*`, `nvs_association_blob_store.*` and Node/Hub security links load/save bindings and start authenticated rejoin. | `79b3393`, `dd7d5c5`, `0608e2a` | Host recovery is **HOST_VERIFIED**; target code is **TARGET_BUILD_VERIFIED**. Protected production key provisioning, power-loss behavior and physical rejoin are **NOT_VERIFIED**. |
| Host logical multi-Node qualification | **HOST_ONLY** | `host/multinode/scheduled_harness.cpp` and `tests/cpp/multinode_host_validation.cpp` exercise independent NodeRuntime contexts over scheduled transport through Hub ingest/runtime, journal and matching ACK. 1/4/10/25 Nodes, pressure, fairness and per-Node evidence are represented. | `fc0776b`, `81a3c04` | **HOST_VERIFIED** only. Ten Nodes are logical host Nodes; 25 Nodes are architectural simulation, not physical ESP-NOW peers. |
| C3 OTA transfer and boot health | **PARTIAL_TARGET_INTEGRATED** | `firmware/node/fota/fota_receiver.*`, `boot_health_gate.*`, target `fota_receiver.cpp`, and Hub `fota_sender.cpp` implement chunked transfer, CRC checks, alternate OTA slot and post-boot health gate. | `9633951`, `0b4bef4`, `7bc2a33` | Protocol negatives have host tests. Same-image alternate-slot update and success health gate are **PHYSICAL_HIL_VERIFIED** at `7bc2a33`. Version upgrade, authenticity, failed-boot rollback and broad interruption cases remain unqualified. |
| Backend household, event and routine functions | **PARTIAL_TARGET_INTEGRATED** | `backend/ghar_sajag/` includes homes, identity, ingestion, rules/service, incidents, notifications, fleet/device state, queries, SQLite and battery analytics. Local API/reference integration supports these software functions. | `9cb3f4a`, `97f004f`, `d43d999`, `4d021cd` | Backend/local scenarios are **HOST_VERIFIED**. The physical Hub does not feed a deployed backend. |
| Caregiver/family PWA | **PARTIAL_TARGET_INTEGRATED** | PWA features under `app/src/features/{home,onboarding,routines,incidents}/` and `app/public/` provide local views and workflows. | `4d021cd` and subsequent PWA work | Local/browser paths are host-tested. Production cloud deployment and physical-device-to-PWA presentation are **NOT_VERIFIED**. |

## 4. Partially Implemented Features

- **Secure installation:** Exact-identity authentication and target protocol routing exist. There is no complete installer/app/service caller that supplies the scanned identity and authorization to the Hub. The target Device ID is derived from radio MAC, rather than a separately provisioned immutable manufacturing identity.
- **Production credentials:** Production signer/wrapping-key interfaces expect provisioned PSA material and security configuration. HIL identity material is test-only and stored in ordinary NVS. Manufacturing provisioning and protected production key sourcing are absent; target compilation does not prove a provisioned production trust root.
- **Home/Hub binding:** Home and Hub identities participate in the protocol and persistence. There is no completed claim/activation path that binds a household installation and gives the Hub the installer-authorized candidate.
- **Authenticated rejoin:** Target boot-time rejoin code exists. Physical restart/outage recovery is unqualified; target runtime event state is not yet demonstrably restored across restart.
- **Remove/replace/reset:** Registry primitives are host-tested. Installer/service workflow, user-visible audit, factory reset and Hub replacement procedures are incomplete.
- **Hub durable event history:** Bounded journal and NVS slot persistence components exist, but the live target path uses a volatile journal. Do not describe its ACK as power-loss durable.
- **Node retained-event persistence:** Encrypted recovery-record components and target NVS adapter exist; live target startup/runtime restoration is not integrated/qualified.
- **ESP-NOW multi-Node:** The Hub registry is bounded for ten installed Nodes. ESP-IDF v6.0.3 headers specify 20 total ESP-NOW peers and 6 native encrypted peers. Current target peers use application AEAD with native peer encryption off. Ten-peer runtime/RF/resource feasibility remains unmeasured on target.
- **FOTA:** Same-image update and successful boot-health gate are physical facts. Image signature/authenticity and product/board/version authorization are absent; production FOTA control is disabled. Failed boot and rollback are not demonstrated.
- **Target sensing:** PIR is connected. Reed/door, resident I Am OK, Call Family/SOS buttons, speaker/buzzer, and installer controls are not connected to the active target runtime.
- **Target time and policy:** Host/backend rules and versioned policy exist, but trusted absolute time, Node-origin wall-clock timestamps, and durable target policy application are not integrated.
- **Battery sensing:** Analytics/model code exists in host/backend. There is no target ADC measurement/calibrated battery telemetry path; target battery health is not backed by real sampling.

## 5. Host / Simulation-Only Capabilities

- Independent 1/4/10/25 NodeRuntime scenarios, ten-Node pressure/fairness, bounded queue/journal full behavior, retries, per-Node reporting and recovery are host/logical evidence only.
- Commissioning cryptographic handshakes, assignment binding, replay/tamper rejection, authenticated runtime frames and rejoin have host coverage; they are not physical proof of the `0608e2a` target path.
- Registry snapshots, encrypted associations and recovery records have host reopen/failure tests; these do not prove target NVS atomicity under power loss.
- Local backend/PWA and simulator flows exercise home/device records, routines, incidents, reports and event presentation. They do not establish a deployed cloud or physical target bridge.
- Battery/power model and battery analytics are not target current/voltage measurements.
- FOTA CRC/chunk/timeout receiver tests are host evidence, not physical corruption/interruption/rollback qualification.

## 6. Designed but Not Implemented Features

- Manufacturing/service flow for immutable Device ID, unique protected private key, certificate/QR issuance, recovery and debug access.
- Complete starter-kit activation and assisted home-installation workflow.
- Production Hub-to-cloud/PWA path with authentication, retry/outbox, offline sync and operational deployment.
- Persistent target Hub event history/dedupe and Node retained/in-flight recovery across restart/power loss.
- Trusted absolute event time and chronology from Node through backend.
- Door/reed, resident buttons, SOS/Call Family and speaker/buzzer target integration.
- Automatic light/deep sleep, GPIO4 event wake, event aggregation, adaptive health and outage backoff.
- Production placement/delivery diagnostics and centralized LED status manager. Current GPIO8 motion indication is not the proposed installer/status UX.
- Routine learning, longitudinal baseline, multi-day trends, mmWave, bed/mattress sensing, fall detection, medicine monitoring, environmental sensors, camera linkage, emergency-response integration and Sarthi AI.

## 7. Device Provisioning / Add Device Lifecycle

The repository’s earlier assisted-installation design and later secure-commissioning design describe different lifecycle layers. They should be read together as follows; this is the reconciled product flow, not a claim that all steps are implemented:

```text
factory/service provisioning
  = permanent physical device identity

starter-kit pre-bonding
  = packaged Hub/Nodes already authorized together

home installation
  = claim Home + assign room/function + placement/delivery checks

later add-on/replacement Node
  = bounded authorized commissioning
    -> exact Node identity
    -> asymmetric identity proof
    -> Hub/Home authentication
    -> ECDH/HKDF
    -> persistent association
    -> room/function
    -> placement/delivery check
    -> READY

ordinary reboot/outage
  = restore association + authenticated rejoin
  = NO re-registration

factory/ownership reset
  = explicit reset + recommissioning
```

A QR is an identity/claim aid, not the permanent secret. It may identify/pin the expected public identity and support an authorized claim; it must not contain a reusable private credential. The current target has protocol/owner code for exact candidate commissioning and rejoin, but no complete installer flow, manufacturing provisioning, physical lifecycle qualification or finished replacement/reset UX.

## 8. Physical Qualification Truth

### Current code versus physically qualified firmware

- **CURRENT_HEAD = `0608e2a`**: authenticated Hub/C3 owner paths are present and target-built. They are **not physically qualified**. The default HIL build remains on the Phase-1 transport path.
- **LAST_PHYSICALLY_QUALIFIED_FIRMWARE = `7bc2a33`**: the latest known physical run used Hub/C3 firmware version `7bc2a33-hil-e3b0c44`.

### Latest physical run

Evidence: `evidence/hil/runs/20260924T094521.398370Z`.

It records fixture/setup/preflight PASS; 17/17 smoke cases; 3/3 same-image FOTA cases; 20 PASS, 0 FAIL, and six `BLOCKED_EXTRA_FIXTURE`. The C3 changed from `ota_0` to `ota_1`, produced fresh software-reset evidence, reached PIR/sensing readiness, passed the configured post-boot health gate, then sent a motion event acknowledged by the Hub. Unexpected resets were zero; final retained and in-flight counts were zero.

It proves the one-Hub/one-C3 same-image OTA and successful post-boot recovery path. It does **not** prove a version A-to-B upgrade, firmware authenticity/signature enforcement, rollback or failed-boot recovery, every corruption/interruption scenario, multi-C3 RF behavior, or electrical/current/PIR-fixture behavior. The six blocked fixture cases are Hub power, C3 power, brownout, current, optical PIR, and physical RF. Radio/offline/restart suites were outside this focused campaign, not reported as blocked or passed.

The separate historical HW-M1.4A evidence recorded at least 19 h 54 min alive under its workload on another historical code pair. It is not current-HEAD qualification or proof of acceptable battery life. Earlier apparent failures after roughly seven hours and one hour were investigated as a full NodeRadio retry queue and stranded retained events, not evidence that PIR itself had stopped working.

## 9. Stale / Superseded Documentation Findings

Some status text predates `0608e2a`. At this snapshot:

1. Statements that target commissioning/runtime authentication is wholly unwired are superseded. `HubSecurityLink`, `NodeSecurityLink` and production owner-task routing exist and build. Accurate status: **target wiring added; installer entry, production provisioning and physical qualification remain open**.
2. Statements that target rejoin exists only on host are superseded by target boot-time association load and rejoin code. Physical target restart/outage recovery remains unverified.
3. Statements that no target identity/wrapping-key source exists are stale: source abstractions exist and compile; provisioned protected production keys do not.
4. Statements that target Hub registry persistence is wholly absent are stale: the secure Hub link loads/saves an NVS-backed registry repository. This does not mean live Hub event journal persistence is integrated.
5. Statements that multi-Node work has not been done are stale if referring to logical host qualification: 1/4/10/25 host coverage and ten-Node pressure/fairness evidence exist. Physical target multi-Node scale remains open.
6. Older current-status fields naming `6f49d28` as repository HEAD are superseded by this snapshot’s `0608e2a` HEAD.

`CURRENT_STATUS_AND_ROADMAP.md` includes an older fast-closure table saying target commissioning is absent, followed by a newer note acknowledging target owner routing. Some `MASTER_TRACEABILITY.csv` recovery descriptions likewise predate the target integration. Those older documents are not modified by this task; use the source at `0608e2a` as implementation truth and preserve the distinction between code, build and physical evidence.

## 10. Remaining Product Implementation

### Phase 2

- Make the authenticated target path usable with explicitly test-only development identities and a real installer-controlled commissioning entry.
- Physically verify exact-node enrollment, authenticated event/health/ACK traffic, unknown-node rejection and rejoin.
- Connect target Node retained/in-flight recovery and Hub event/dedupe persistence, or strictly constrain the semantics claimed for ACK and restart behavior.
- Prove target outage/restart recovery and representative physical multi-C3 isolation/contention.
- Before enabling deployable FOTA, establish real version upgrade, authorized-image rejection and interrupted/failed-update recovery.
- Measure enough target heap, queue, latency and retry behavior to establish practical feasibility.

### Battery / low power

The current C3 polls GPIO4 every 20 ms and stays awake; there is no automatic sleep or event-driven wake. Follow the existing HW-M1.4 sequence: B0–B4 current baseline; C1 automatic light sleep; measure; C2 GPIO4 wake, immediate first motion, measured 30–60 second aggregation of ordinary repeats, adaptive NodeHealth/offline backoff and TX-power evaluation; C3 deep sleep/RTC retained-state design; then overnight/endurance qualification. Preserve critical-event immediacy and investigate the historical multi-hour event/retry failure.

### P0 product vertical/features

Backend/PWA rules and workflows exist in software, but the real target path remains open. Build the authenticated Hub-to-backend/cloud connection with offline/idempotent delivery and trusted timestamps; then connect correct household/device attribution and caregiver presentation. Integrate and physically verify door/reed, I Am OK and Call Family/SOS controls, target policy application, notification-provider delivery and complete summary consent/date-window semantics.

### Productization

Unique manufacturing identities and protected keys; firmware signing and controlled secure-boot/flash-encryption policy; installer, replacement, factory-reset and Hub-replacement procedures; watchdog/reset/brownout diagnostics; final PCB/BOM/enclosure/power architecture; certification, field support and deployment operations.

### P1 / later

Person-specific routine learning, longitudinal baselines, daily deviation and multi-day trend detection, explainable caregiver insights, mmWave, optional bed/mattress sensing, fall detection, medicine monitoring, environmental sensors, camera linkage, emergency-response service and Sarthi AI.

## 11. Recommended Next Product Implementation

1. **Product integration:** make the `0608e2a` authenticated target path operable on development hardware with test-only credentials and an actual authorized Add Device caller.
2. **Stability and recovery:** connect target persistence for Node pending events and Hub accepted-event/dedupe state; prove restart/rejoin semantics and accurately define ACK durability.
3. **Performance/resource feasibility:** measure target heap, queue pressure, retries, ACK latency and representative multi-C3 behavior; do not substitute host scale for radio evidence.
4. **Focused verification:** build and run only the tests/physical checkpoint needed to establish each product behavior; inspect generated evidence rather than broadening the harness preemptively.
5. **Validation tooling:** change it only when a specific product implementation or qualification is blocked. Do not prioritize general HIL/reporting expansion over product work.

## 12. Remaining Phase-2 Items

| Item | Classification | Snapshot assessment |
|---|---|---|
| Target authenticated commissioning/runtime | **REQUIRED_NOW** | Target owner routing exists and builds, but installer entry/provisioned development identity and physical proof are missing. |
| Production manufacturing credentials, secure boot/flash encryption and irreversible eFuse policy | **DEFER_TO_PRODUCT_TRACK** | Not a development-fixture task; no irreversible programming is implied. |
| Hub/Home association and automatic authenticated rejoin | **REQUIRED_NOW** | Target boot-time code exists; target restart/outage restoration is not physically qualified. |
| Node remove/replace/factory reset workflow | **PARTIAL_BUT_SUFFICIENT** | Registry primitives and host coverage exist; service UX/audit can be finished with productization before field deployment. |
| Hub persistent event history and dedupe | **REQUIRED_NOW** | Live target journal is volatile; durable semantics must be implemented or explicitly constrained before relying on restart-safe delivery. |
| Node retained/in-flight persistence on target | **REQUIRED_NOW** | Recovery record/adapters exist, but active target runtime restoration is not integrated/qualified. |
| Registry revocation/tombstone capacity | **ALREADY_COMPLETE** | Host fail-closed capacity behavior is committed and tested; do not silently evict revocation state. |
| 1/4/10/25 logical Node qualification | **ALREADY_COMPLETE** | Host scheduled transport and ten-Node pressure/fairness/per-Node evidence are complete at logical scale only. |
| Representative physical multi-C3 qualification | **REQUIRED_NOW** | Needed to validate the new target path’s real peer isolation, contention, ACK and reconnect behavior; does not require ten physical Nodes. |
| 25 physical ESP-NOW Nodes | **DEFER_TO_PRODUCT_TRACK** | 25-node scope is simulated architectural stress, not a physical-peer claim. |
| ESP-NOW peer/security capacity | **PARTIAL_BUT_SUFFICIENT** | SDK declares 20 total and 6 native encrypted peers; application AEAD avoids requiring ten native encrypted peers. Target resource and RF behavior still needs representative measurement. |
| Same-image OTA and successful boot-health path | **ALREADY_COMPLETE** | Physically qualified for one Hub/C3 at `7bc2a33`; do not repeat without relevant target changes. |
| FOTA version upgrade and image authenticity/authorization | **REQUIRED_NOW** | Same-image CRC transfer is not an authorized version update; production FOTA remains disabled until safe authorization exists. |
| FOTA corruption/interruption/failed-boot recovery | **REQUIRED_NOW** | Host protocol cases exist; target failed-update safety and rollback are not demonstrated. |
| Bootloader rollback configuration | **PARTIAL_BUT_SUFFICIENT** | Configuration and successful health-gate path exist; failed-boot rollback behavior is not physically demonstrated. |
| Broad reusable generic fault-injection matrix | **VALIDATION_TECH_DEBT** | Verify critical product failures through focused existing seams; comprehensive framework expansion is not a prerequisite. |
| Target outage/restart recovery | **REQUIRED_NOW** | Host scenarios pass; target Hub/Node restart and recovery are not yet physically qualified. |
| Target performance/resource feasibility | **REQUIRED_NOW** | Obtain enough target heap, queue, latency, retry and recovery measurements to rule out serious product feasibility issues. |
| Production Hub-to-backend-to-PWA bridge | **DEFER_TO_PRODUCT_TRACK** | This is P0 vertical work and must precede a real-home product claim, but is not an existing Phase-2 target feature. |
| Long soak and battery endurance after low-power work | **DEFER_TO_BATTERY_TRACK** | Bounded stability checks may support Phase 2; extended energy/endurance belongs to the battery track. |
| `hil-full` / `release-qualify` general orchestration | **VALIDATION_TECH_DEBT** | Do not expand the validation platform unless a concrete release/product gate requires it. |
| Phase-1 71-case regression | **ALREADY_COMPLETE** | Mandatory historical Phase-1 coverage remains; it does not qualify the new `0608e2a` target security path. |
