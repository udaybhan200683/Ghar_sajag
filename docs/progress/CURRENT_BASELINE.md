# Ghar Sajag / Parivar Saathi - Current Baseline

**Document revision:** HW-M1.3-TARGET-BUILD-R1
**Product baseline:** Parivar Saathi v1.5.4
**PWA / BatteryAnalytics baseline:** v3.4.3
**Engineering baseline:** Phase 3B paused; HW-M1.2 QUALIFIED / PASS
**Active engineering work:** HW-M1.3 IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / HARDWARE VALIDATION PENDING
**Qualified Phase 3A implementation anchor:** `4dcaf99`
**Qualified Phase 2D implementation anchor:** `9499381`
**Current qualified HW branch:** `feature/hw-m1`
**Current qualified HW commit:** `50abdce`
**Current implementation branch:** `feature/hw-m1-runtime-integration`
**Implementation branch point:** `4645098`
**Last host-validated implementation commit:** `1d41864dd3d0004ed4dbfa608bb85baf3e35a91f`
**Pre-build documentation/resume HEAD:** `0546b28`
**Remote development branch:** `origin/feature/hw-m1-runtime-integration`
**Updated:** 2026-09-19

This document is the definitive current “WHERE ARE WE NOW?” record. It
preserves the inherited PWA/software baseline and the HW-M1 deltas without
duplicating the full historical PWA implementation record below.

Phase 2 remains COMPLETE / QUALIFIED at `9499381`. Phase 3A is COMPLETE /
QUALIFIED after successful desktop/mobile browser validation and the authoritative
`make release-gate-final` PASS. The Phase 3A implementation/qualification anchor is
`4dcaf99` (`Complete Phase 3A performance and stress foundation`).

The qualified Phase 3B scale/read-path optimization checkpoint is `fee5854`.
It does not replace the permanent Phase 3A implementation/qualification anchor
`4dcaf99`, and it does not claim all of Phase 3B complete.

The qualified Phase 3B Reports scalability checkpoint is `0e5a9e3`. The earlier
qualified Phase 3B scale/read-path checkpoint remains `fee5854`; the permanent
Phase 3A implementation/qualification anchor remains `4dcaf99`.

The qualified Phase 3B concurrent API and household-isolation checkpoint is
`0d6a2fc`. Phase 3B remains IN PROGRESS; notification-provider storm/failure
qualification, restart/recovery, DB/resource fault injection,
EXTENDED/endurance and final Phase 3 qualification remain pending.

## Git Checkpoints

These commits have different meanings and must not be summarized as one
generic “stable” state:

| Purpose | Commit | Branch / relationship | Validation status |
|---|---|---|---|
| Last physically qualified HW baseline | `50abdce` | `feature/hw-m1` history | HW QUALIFIED / PASS; dual-slot FOTA and earlier HW-M1 milestones physically demonstrated. |
| Documentation / resume baseline | `4645098` | `feature/hw-m1`, parent of the implementation branch | Documentation-only checkpoint; no new physical firmware behavior qualified. |
| HW-M1.3 host-validated implementation | `1d41864` | `feature/hw-m1-runtime-integration`, also on `origin/feature/hw-m1-runtime-integration` | IMPLEMENTED / HOST VALIDATED. |
| Pre-build documentation/resume checkpoint | `0546b28` | `feature/hw-m1-runtime-integration`, also on the tracked remote before this work | Documentation checkpoint; no physical qualification. |
| Current HW-M1.3B source/build checkpoint | This document's commit | `feature/hw-m1-runtime-integration`; descendant of `0546b28` | IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / HARDWARE VALIDATION PENDING. |

The last host-validated implementation commit before target composition is
`1d41864`; `0546b28` is the documentation/resume checkpoint from which
HW-M1.3B started. The latest physically qualified checkpoint remains
`50abdce` until HW-M1.3 target hardware testing passes. Target build success
does not replace physical qualification.

The P0 software-gap audit approved HW-M1: no host/backend/PWA defect blocks the
first physical vertical slice. F14 remains an open software gap but does not
block HW-M1; it remains a pilot/commercial P0 blocker. Full audit:
`docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md`.

## Current HW-M1 state

### Repository and inherited software baseline

- Repository root: `/home/udaybhan/projects/Ghar_sajag`.
- Active product code directory:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.
- HW-M1 implementation branch: `feature/hw-m1-runtime-integration`.
- Qualified parent branch: `feature/hw-m1`.
- Implementation branch point: `4645098`.
- Frozen software/PWA branch point: `9b391fa` on `feature/full-pwa-e2e`.
- HW-M1 planning commit: `997f9ba`.
- Earlier qualified HW checkpoint: `3f02822`.
- Latest qualified HW commit: `50abdce`.

The HW branch documents hardware and target-integration deltas from the frozen
software/PWA branch point. The stable host/PWA reference remains
`feature/full-pwa-e2e`; the historical qualified Phase 3B host checkpoint is
`0d6a2fc`. These historical software anchors are not replaced by HW commits.

### Milestone status

| Milestone | Status | Evidence / meaning |
|---|---|---|
| HW-M1.0 toolchain and board bring-up | QUALIFIED / PASS | ESP-IDF v6.0.3 Hub/C3 build, flash and serial bring-up; board identity and 4 MB flash recorded. |
| HW-M1.1 real AM312 PIR sensing | QUALIFIED / PASS | GPIO4 sensing, LED indication, battery operation and approximately 12 ft / 3.7 m observation. |
| HW-M1.2 PIR -> C3 -> ESP-NOW -> Hub | QUALIFIED / PASS | Real motion events reached the Hub; channel/TX/RSSI findings recorded. |
| Dual-slot C3 FOTA | QUALIFIED / PASS | `ota_0 -> ota_1 -> ota_0`, validation, PIR restoration and post-update events. |
| HW-M1.3 Target Runtime Integration | IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / HARDWARE VALIDATION PENDING | Portable runtime/adapters are composed into ESP-IDF v6.0.3 C3 and Hub products; both fit the 1920 KB OTA slots; 124 focused C++ checks pass. No flashing or physical HW-M1.3 validation was performed. |

The terms are strict: IMPLEMENTED means source exists; HOST VALIDATED means
host/simulation validation passed; HW VALIDATED means target behavior was
physically exercised; QUALIFIED / PASS means checkpoint exit criteria were
physically demonstrated. Documentation or source inspection does not upgrade
a status.

### Qualified hardware configuration

| Item | Qualified configuration |
|---|---|
| Hub | ESP32 DevKit / ESP-WROOM-32; ESP32-D0WD-V3 rev 3.1; 4 MB flash; STA MAC `5C:01:3B:BE:B9:F8`; CP2102 USB interface. |
| Node | ESP32-C3 small board / SuperMini-style; 4 MB flash; MAC `14:63:93:C5:D1:58`. |
| PIR | SmartElex AM312 on node GPIO4; approximately 12 ft / 3.7 m observed in the test setup. |
| LED | Node onboard LED GPIO8, active-low. |
| ESP-NOW | Current channel 1 on Hub and node. |
| C3 TX power | `esp_wifi_set_max_tx_power(40)` = 10 dBm. |

The full HW-M1.2 snapshot is `docs/hw/evidence/HW_M1_2/README.md`. It also
records that initial operation used channel 6, the C3 was unstable at the
higher/default TX power, 10 dBm was substantially more stable, channel 6 -> 1
did not produce meaningful range improvement, and channel congestion was not
proven to be the dominant range limitation. RF optimization remains open;
channel 1 did not solve the range issue. Hub RSSI logging was added and
cleaned single-line logging removed the prior serial-garbage symptoms.

### FOTA state and security limitations

Hub and C3 use 4 MB flash with custom dual-OTA partitions: `ota_0 = 0x1E0000`
(1920 KB) and `ota_1 = 0x1E0000` (1920 KB), with rollback enabled. The
Hub -> C3 control-plane path completed the USB bootstrap to `ota_0`, FOTA #1
`ota_0 -> ota_1`,
and FOTA #2 `ota_1 -> ota_0`, including pending validation, VALID marking, PIR
restoration and post-update Hub events. The immutable record is
`docs/hw/evidence/HW_M1_FOTA/README.md`.

FOTA is CONTROL PLANE traffic. Normal sensor/business events are DATA PLANE
traffic. Qualified FOTA features include ESP-NOW transfer, application ACK,
sequence handling, retry, duplicate handling, per-chunk/full-image CRC32,
inactive partition selection, boot partition switching, rollback-enabled boot
and post-boot validation.

FOTA is not production-secure: CRC32 is corruption detection, not
authenticity; ESP-NOW peer encryption/key management, signed firmware
authenticity, anti-rollback/version policy and backend firmware distribution
remain open. The embedded C3 image in the qualification Hub was only for
bootstrap qualification, not the intended production distribution
architecture. Hub self-OTA is also open.

### Architecture boundaries to preserve

The portable code already defines `AckClass`, `EventKey`, `DomainEvent`,
`NodeMessage`, `NodeAckMessage`, `node_message_from_event()`,
`domain_event_from_node_message()` and `make_node_ack()`.

`NodeRuntime` owns node/session identity, event sequence, retained business
events, retry scheduling, typed `NodeMessage` creation, physical transport
result handling and application ACK semantics. `next_message()` is the typed
boundary for the future physical adapter; `transport_result()` accepts the
physical result; `acknowledge()` applies the application ACK. `NodeRadio` owns
retry timing/pending work, not physical RF. ESP-NOW delivery success is not a
durable business ACK.

`HubRuntime::radio_message_callback()` is the typed ingress boundary, followed
by validation, authorization/session checks, ingest, journal, coverage and
routine/rules processing through `run_state_once()`. The Hub runtime remains
single-owner. ESP-NOW callbacks must only perform bounded copy/admission into a
queue; they must not mutate `HubRuntime` directly. The owner-task model in
`firmware/hub/runtime/FREERTOS_BINDING.md` remains authoritative.

### HW-M1.3 implementation state

HW-M1.3 is **IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / HARDWARE
VALIDATION PENDING**. It is not HW VALIDATED or QUALIFIED.

1. Implemented and host-tested a common bounded codec for `NodeMessage` and
   `NodeAckMessage`, with protocol magic/version/frame type and fixed-width,
   bounded representation; reject malformed frames.
2. Added an isolated C3 AM312 GPIO4 adapter using existing sensing semantics,
   `NodeRuntime`, `next_message()`, an ESP-NOW adapter,
   `transport_result()`, and application ACK -> `acknowledge()`.
3. Added an isolated Hub ESP-NOW callback, bounded queue, owner task, decode,
   `radio_message_callback()`, `run_state_once()`, and `NodeAckMessage` return.
4. Kept FOTA separate as control-plane traffic through dedicated target queues.
5. Added an NVS-backed, fail-closed monotonically increasing boot-session
   provider so sequence restart after reboot does not reuse an EventKey.
6. Added real ESP-IDF v6.0.3 product compositions at
   `firmware/node/target/esp32c3/idf/` and
   `firmware/hub/target/esp32/idf/`, each using the portable runtime and
   existing adapter rather than a second prototype runtime.
7. Added a wire-compatible FOTA receiver/sender composition. The sole ESP-NOW
   callback in each adapter classifies and queues control traffic; FOTA worker
   tasks consume the bounded control queue, and normal data-plane work pauses
   during maintenance. FOTA never enters `NodeRuntime`, `HubRuntime`, journal,
   or rules.

Host result: `PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++` passed 124
checks. The release-gate C++ unit, sanitizers, trace, Python, JavaScript,
contracts, product/feature, simulator/lab, dummy-stream and functional stages
passed. Complete `make release-gate-final` is **ENVIRONMENT BLOCKED**, not PASS:
this sandbox prohibits localhost socket creation/binding, so HTTP/PWA/browser
stages cannot start. The exact record is
`docs/hw/evidence/HW_M1_3_HOST/README.md`.

Target builds used ESP-IDF v6.0.3. C3 target `esp32c3` produced
`gs_hw_m1_node.bin` at `0xC9430` (824,368 bytes), leaving `0x116BD0`
(1,141,712 bytes, 58%) in its `0x1E0000` slot. Hub target `esp32` produced
`gs_hw_m1_hub.bin` at `0x184E10` (1,592,848 bytes), leaving `0x5B1F0`
(373,232 bytes, 19%). Both builds used the exact custom 4 MB partition layout
and `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`. The Hub image embeds the exact
built C3 application binary for the temporary BOOT-button engineering FOTA
path; backend firmware distribution remains intentionally open.

Reproduction commands from the active product directory:

```sh
source ~/.espressif/tools/activate_idf_v6.0.3.sh
cd firmware/node/target/esp32c3/idf
idf.py set-target esp32c3
idf.py build
cd ../../../../hub/target/esp32
cp ../../../node/target/esp32c3/idf/build/gs_hw_m1_node.bin idf/main/node_firmware.bin
cd idf
idf.py set-target esp32
idf.py build
```

Then return to the active product directory and run
`PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++`.

No target was flashed. The immediate remaining task is HW-M1.3C physical
qualification: real AM312 -> NodeRuntime, typed NodeMessage over ESP-NOW,
bounded Hub callback queue, HubRuntime owner-task processing, application ACK
return, correct retained-event retirement, reboot/session behavior, and both
post-integration FOTA rotations with PIR restoration and retained evidence.

### Current open gaps

- HW-M1.3 physical validation and evidence (the exact next task, HW-M1.3C).
- Physical post-integration FOTA revalidation in both slot directions; target
  composition is build-validated but does not inherit a physical PASS merely
  from wire compatibility with the qualified control-plane protocol.
- Normal-terminal rerun of `make release-gate-final` because localhost stages
  are sandbox-blocked here.
- Target ESP-NOW peer encryption/key management and production authenticity.
- Anti-rollback/version policy and backend firmware distribution.
- RF range optimization and multi-node RF characterization.
- Target Wi-Fi/backend transport, target persistence/power-loss recovery,
  battery calibration and later HW-M1 vertical-slice milestones.
- Remaining Phase 3B host work: provider storm/failure, restart/recovery,
  DB/resource fault injection, EXTENDED/endurance and final reconciliation.

## Master implementation specification

Primary master plan:

`docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md`

### How to use these documents

Use `FULL_PWA_IMPLEMENTATION_TASK.md` for:
- intended product scope;
- original requirements;
- Phase 1 / Phase 2 / Phase 3 boundaries;
- overall implementation direction.

Use the following as the authority for what is actually implemented and
validated now:

1. Current code and automated tests
2. `docs/progress/CURRENT_BASELINE.md`
3. Machine-readable validation contracts
4. Current README / CHANGELOG / validation documentation
5. Historical DOCX/XLSX documents

If the master implementation specification differs from a later approved and
validated implementation refinement, do not automatically revert the current
implementation to the older master wording.

Instead:
- preserve the validated implementation;
- identify the difference;
- update the baseline/status documentation;
- reconcile the master specification during the appropriate documentation pass.

## Resume instructions for future ChatGPT / Codex sessions

Before implementing the next phase:

1. Read `docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md`.
2. Read `docs/progress/CURRENT_BASELINE.md`.
3. Inspect recent Git history.
4. Verify relevant current code/tests before deciding what remains.
5. Do not reimplement functionality already marked COMPLETE in this baseline.
6. Preserve validated behavior unless a new approved requirement explicitly changes it.

## Authoritative validation references

Phase 1 UI/behavior contract:

`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/validation/phase1_ui_contract.json`

Master qualification command:

`make release-gate-final`

Mandatory browser projects:
- `chromium-desktop`
- `chromium-mobile`

# Current Baseline

Updated: 2026-09-17

## Phase 3B qualified scale/read-path checkpoint; broader work in progress

- Added migration-managed indexes matching timeline/event-kind/latest-received
  hot query shapes; representative plans no longer use temporary sort/group
  B-trees.
- Replaced recursive conversion of the full incident population during every
  PWA poll with a distinct active-incident-kind read model.
- Preserved the public snapshot active-ID contract, durable event/incident
  history, report semantics and caregiver-visible Home behavior.
- Added bounded stderr stress progress and diagnostic-only per-stage timings in
  JSON while keeping stdout machine-readable.
- Focused tests, full Python discovery, JavaScript tests, performance/SMALL and
  MEDIUM stress pass on the implementation host.
- Qualified checkpoint: `fee5854`.
- LARGE correctness: PASS; runtime improved from approximately 461 s to
  approximately 72 s.
- PWA/read-path optimization: qualified.
- Playwright cleanup race: fixed.
- `make playwright-gate`: PASS, 86/86.
- `make release-gate-final`: PASS.
- At the `fee5854` checkpoint, remaining Phase 3B work included Reports
  scaling, controlled concurrent API load, household isolation, notification
  storm qualification, and restart/recovery.
- EXTENDED/endurance remains pending.

Focused evidence:
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3B_SCALE_OPTIMIZATION.md`

Phase 3B overall status remains IN PROGRESS. Phase 3A remains COMPLETE /
QUALIFIED. Permanent Phase 3A implementation/qualification anchor: `4dcaf99`.

## Phase 3B Reports scalability qualified checkpoint

- Root cause: each repeated report request selected and deserialized every
  reportable event in the window into a full `CloudEvent`, then repeated Python
  filtering and aggregation.
- Added SQL summary/trend aggregation using exact household-local bucket
  boundaries, grouped motion timestamps for timezone-aware night activity,
  bounded room totals, and six-row highlight materialization.
- Did not add report caching or a second history store; canonical durable events
  remain authoritative and the API schema is unchanged.
- Optimized-versus-reference tests preserve Today, Week, calendar Month,
  timezone, include/exclude-test, care/maintenance, reportability,
  removed-device history, deterministic ordering, and collection bounds.
- MEDIUM report stage improved from 675.680 ms to 106.244 ms on the same host.
- Qualified checkpoint: `0e5a9e3`.
- Manual LARGE qualification: correctness PASS; Reports stage improved from
  approximately 27.3 s to approximately 4.9 s and total runtime improved from
  approximately 72.2 s to approximately 47.6 s; request failures were zero.
- `make release-gate-final`: PASS, including `performance-test` and SMALL
  deterministic stress.
- MEDIUM and LARGE stress remain outside the normal final gate; LARGE remains an
  explicit/manual milestone qualification. EXTENDED/endurance remains outside
  the normal final gate and is endurance/soak only.

Focused evidence:
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3B_REPORT_SCALABILITY.md`

Phase 3B overall status remains IN PROGRESS. `0e5a9e3` is the qualified Reports
scalability checkpoint; `fee5854` remains the earlier qualified scale/read-path
checkpoint, and `4dcaf99` remains the permanent Phase 3A
implementation/qualification anchor. Remaining Phase 3B work includes
controlled concurrent API load, household isolation, notification storm
qualification, and restart/recovery. EXTENDED/endurance remains pending.

## Phase 3B controlled concurrent API load and household isolation

- Status: QUALIFIED (manual qualification complete).
- Added a fixed-seed, six-worker bounded concurrency harness using real WSGI,
  domain, SQLite event, report, device and notification paths.
- Corrected the durable event identity mismatch: canonical event IDs are now
  unique per household rather than accidentally global in SQLite.
- Made durable duplicate acceptance atomic and serialized complete core/local
  lab requests through the existing re-entrant application lock.
- Verified simultaneous two-household reads/writes with identical canonical
  event IDs and identical caregiver-facing device names.
- Verified snapshots, chronology, Today/Week/Month Reports, incidents,
  notifications, devices, preferences and raw database ownership remain
  household-local.
- Focused result: PASS (`9/9`); harness result: PASS with 12 accepted, 6
  duplicates and 2 rejected per household, zero unexpected failures, zero
  SQLite busy/lock failures and deterministic worker/simulator cleanup.
- Focused schema/migration suite: PASS (`9/9`), including an explicit 006→007
  existing-history upgrade fixture.
- Full Python: PASS (`107/107`); JavaScript: PASS (`3/3`);
  performance/SMALL: PASS; MEDIUM stress: PASS.
- Manual qualification: `make concurrency-test` PASS; `make release-gate-final`
  PASS; Playwright `86/86` PASS; SMALL, MEDIUM and LARGE PASS. LARGE recorded
  25,000 accepted, 2,500 duplicates, 250 rejected, zero request failures,
  `correctness_gate` PASS, a 20,828,160-byte database, approximately 64 MB
  maximum RSS and approximately 49.9 seconds wall time. Migration 006→007
  preservation regression: PASS.
- Timing remains diagnostic only; the focused host run was approximately
  147 ms. MEDIUM completed in approximately 3.946 s with a 111.019 ms report
  stage.
- `make concurrency-test` is explicit and is not added to
  `release-gate-final`; MEDIUM/LARGE/EXTENDED concurrency is not made a normal
  release gate.

Evidence:
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3B_CONCURRENT_API_ISOLATION.md`

Phase 3B overall remains IN PROGRESS. This checkpoint does not replace
qualified Reports checkpoint `0e5a9e3`, earlier scale/read-path checkpoint
`fee5854`, or permanent Phase 3A anchor `4dcaf99`. Remaining Phase 3B work
includes notification-provider storm/failure qualification, restart/recovery,
DB/resource fault injection, EXTENDED/endurance and final Phase 3
qualification.

## Git

- Branch: `feature/full-pwa-e2e`
- Phase 3A implementation and qualification commit:
  `4dcaf99` (`Complete Phase 3A performance and stress foundation`)
- Phase 3A status: COMPLETE / QUALIFIED.
- Authoritative Phase 3A qualification: `make release-gate-final` PASS.
- `4dcaf99` is the Phase 3A implementation/qualification anchor. Later
  documentation-only commits do not replace this implementation anchor.
- Phase 2D implementation and qualification commit:
  `9499381` (`Complete Phase 2D reconciliation and qualification`)
- Phase 2D status: COMPLETE / QUALIFIED.
- Final qualification: `make release-gate-final` PASS.
- Overall Phase 2 status: COMPLETE / QUALIFIED.
- `9499381` is the Phase 2D implementation/qualification anchor. A later
  documentation-only pointer commit does not replace this implementation anchor.

## Phase 3A - PWA Performance, Lightweight UX and Stress Foundation

- Status: COMPLETE / QUALIFIED
- Document revision: P3A-R1
- Product version remains Parivar Saathi v1.5.4 / PWA v3.4.3.
- Physical implementation directory remains `v3_4_2`.

Implemented:

- deterministic socket-free static/payload/profile measurement;
- structural performance budgets with documented headroom;
- initial Home no longer fetches the 28,770-byte validation catalog;
- Settings no longer hydrates full application state on entry;
- Reports remain lazy and use guarded bounded active refresh;
- state/report requests cannot form persistent overlapping poll loops;
- background state/report work pauses while browser notification checking stays
  available, and foreground return refreshes immediately;
- unchanged Home/Devices/Reports DOM is retained rather than rebuilt every poll;
- SQLite snapshot/timeline/report reads use indexed home/range/kind/limit queries;
- service-worker cache remains static-only and now includes imported modules;
- SMALL/MEDIUM/LARGE/EXTENDED deterministic stress profiles and isolated cleanup;
- `make performance-profile`, `make performance-test`, `make stress-test`, and
  `make endurance-test` targets;
- Python, JavaScript and Playwright Phase 3A regression coverage.

Measured evidence is in the active implementation documents:

- `docs/PHASE3A_PERFORMANCE.md`
- `docs/PHASE3_STRESS_FRAMEWORK.md`

Current focused evidence:

- structural profiler: PASS;
- final post-fix profiler run remains within the Phase 3A static budget
  (profiler-reported static total: 80,542 B);
- SMALL stress: PASS (120 accepted / 12 duplicate / 6 rejected);
- MEDIUM stress: PASS (2,500 accepted / 250 duplicate / 50 rejected);
- targeted Phase 1/2 Python regressions: PASS;
- full Python discovery: PASS (`96/96`);
- JavaScript tests: PASS (`3/3`);
- contracts and validation coverage: PASS (`24/24` mapped requirement IDs);
- focused desktop/mobile browser regressions: PASS;
- mandatory desktop/mobile Playwright suite: PASS;
- authoritative `make release-gate-final`: PASS.

Final browser qualification also found and corrected three sequencing defects
without weakening the Phase 3A performance strategy:

- Reports refresh scheduling could effectively exceed the intended refresh
  interval because the deadline was sampled only from the Home poll loop;
- an older Home poll snapshot could overwrite a newer explicit action result;
- simulator time can move backward across an explicit reset, so stale-response
  rejection now compares a reset epoch before comparing `simulation_now`.

Phase 3B/3C remains responsible for substantial LARGE/EXTENDED qualification,
accelerated multi-month soak, controlled concurrent API load, full database and
resource failure injection, restart checkpoints under stress, and physical
hardware resource qualification.

## Phase Status

### Phase 1 - Persistent Foundation, Devices and Validation Hardening

- Status: COMPLETE / qualified

- Commit anchors:
  - `9cb3f4a` - Implement Phase 1 persistent settings and device management
  - `959c854` - Fix caregiver UI presentation and regression coverage
  - `9757791` - Complete Phase 1 validation hardening

#### Purpose

Phase 1 established the persistent application foundation, authoritative device
management, caregiver-facing Home behavior, simulator integration, and the
validation framework required before adding Reports and Notifications.

Phase 1 was subsequently hardened after manual PWA testing exposed several
user-visible defects that the original positive-only validation had missed.

#### Persistent application foundation

Implemented durable SQLite-backed application state for:

- Home Details
- Family Members
- caregiver/admin roles
- authoritative device registry
- device room assignment
- device enable/disable/remove behavior
- Battery Alerts
- routine/activity policy
- device health state
- application settings required by the caregiver PWA

Normal product restart preserves persistent configuration.

Explicit automated test reset remains deterministic and isolated.

#### Family and role behavior

Implemented:

- family-member CRUD
- relationship/role/contact information
- active/inactive member handling
- owner/admin boundaries
- protection against removing/deactivating the final administrator

Production authentication remains outside the current local-development
authorization boundary.

#### Devices

Implemented one authoritative device registry shared between Devices and
Manage Devices.

Supported:

- simulated-device registration
- device details
- rename
- room assignment
- enable/disable
- remove/unregister
- online/offline/heartbeat state
- battery/device-health projection

Removing a device does not imply that its historical activity must be deleted.

#### Home caregiver behavior

Validated Home domains include:

- overall household status/banner
- Morning Routine
- I am OK
- Call Family
- Main Door
- Night Activity
- Device Health
- Recent Important Events

Important established semantics:

- Morning `NOT_STARTED` is neutral.
- Morning `IN_PROGRESS` is amber/orange and does not cause overall attention.
- Morning `COMPLETE` is success/green.
- Morning `MISSED` is a concern/red.
- Main Door open-too-long shows human-readable elapsed duration.
- Night Activity contains only night-domain information.
- Device Health shows caregiver-facing information rather than engineering
  diagnostics.
- ordinary battery telemetry is maintenance information, not a care/safety
  Recent Important Event.
- monitoring coverage loss is a care/safety concern.
- no global caregiver-visible Privacy ON/OFF control exists.

#### Care/safety versus maintenance classification

Care/safety activity includes applicable events such as:

- I-am-OK concerns/acknowledgement
- Call Family
- missed routine
- unusual night activity
- meaningful Main Door concerns
- post-door inactivity
- monitoring coverage loss

Maintenance/diagnostic activity such as battery calculations, confidence,
consumption-rate updates and raw telemetry does not become caregiver care/safety
activity by default.

#### Phase 1 Validation Hardening

Validation was strengthened after manual testing exposed issues including:

- cross-card message contamination
- battery maintenance appearing as important activity
- incorrect Morning `IN_PROGRESS` semantics
- weak Main Door duration presentation
- engineering battery information exposed in caregiver UI

The hardened validation model requires, where applicable:

- required-content assertions
- forbidden/unrelated-content assertions
- backend/UI consistency
- unaffected-component assertions
- desktop/mobile coverage
- persistence/reset isolation
- cross-feature pairwise/high-risk interaction coverage

Machine-readable Phase 1 UI contract:

`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/validation/phase1_ui_contract.json`

#### Release-gate architecture

`make release-gate-final` is the authoritative qualification command.

Validation ports are isolated:

- host `browser-e2e`: `127.0.0.1:8765`
- mandatory Playwright lab: `127.0.0.1:8766`

The mandatory Playwright stage executes the discovered browser specifications
for both:

- `chromium-desktop`
- `chromium-mobile`

#### Qualification

Phase 1 final qualification:

`make release-gate-final` - PASS

This included host validation and mandatory desktop/mobile browser validation.

#### Phase 1 invariants to preserve

Future phases must not regress:

- authoritative shared device registry
- persisted household/settings behavior
- deterministic test isolation
- last-admin protection
- established Home status/color semantics
- care/safety versus maintenance classification
- no cross-domain Home-card contamination
- consumer-facing Device Health presentation
- required + forbidden validation philosophy


### Phase 2A - Reports and Durable Event History

- Status: COMPLETE / committed
- Commit: `97f004fbd64b6dbdce9f163bdb017b7909f14da1`

#### Purpose

Phase 2A replaced the static Reports mock with backend-derived caregiver Reports
and added the durable canonical event-history foundation required for meaningful
Today/Week/Month reporting.

#### Reports implementation

Implemented backend-derived:

- Today
- Week
- This Month

The Reports tab no longer uses hard-coded browser values.

Report projection is performed by the backend from canonical historical activity
rather than by browser-side aggregation.

#### Report periods

Today:

- household-local current day
- inclusive start / exclusive end
- current-day caregiver summary/highlights

Week:

- seven household-local calendar days ending today
- daily trend buckets

Month:

- current household-local calendar month
- daily trend buckets
- no fabricated values when historical data is insufficient

`This Month` intentionally means the current calendar month rather than a
rolling 30-day period.

#### Reports API

Implemented a period-validated Reports API:

`GET /v1/homes/{home_id}/reports?period=TODAY|WEEK|MONTH`

Invalid periods are rejected rather than silently defaulted.

Reports distinguish:

- valid report data
- explicit `NO_DATA`
- backend/error state
- malformed response

No-data is not treated as an error.

#### Durable canonical CloudEvent history

Initial Phase 2A implementation exposed that canonical event history was still
process-memory only.

Phase 2A was therefore completed by adding durable SQLite-backed CloudEvent
storage while preserving the existing event-store contract used by
`IngestService` and `QueryService`.

Implemented:

- SQLite-backed canonical event history
- `(home_id, event_id)` identity semantics
- duplicate/replay idempotency
- event ordering
- restart durability
- report durability across backend restart

Reports remain projections over canonical events; no separate precomputed
Reports history model was created.

#### Database changes

Reused the existing `events` table.

Migration:

`backend/migrations/004_cloud_event_history.sql`

was added to persist `hub_received_at`, which was required for lossless
CloudEvent round-tripping.

#### Removed-device history

Removing/unregistering a device:

- does not reactivate the device
- does not destroy historical events
- does not remove valid historical report activity

Historical events remain reportable after backend restart.

#### Household timezone

Report windows use the persisted household timezone.

The backend Home timezone is synchronized from persisted Home Details rather
than using host-machine timezone or an independent hard-coded reporting
timezone.

Timezone configuration therefore survives restart and drives Today/Week/Month
boundaries consistently.

#### Report classification

Care/safety activity is reported according to the established event
classification.

Maintenance/diagnostic telemetry is not incorrectly promoted into caregiver
care/safety reporting.

Coverage loss/restoration remains care/safety relevant where appropriate.

#### UI behavior

Reports support:

- backend-derived loading
- Today/Week/Month switching
- populated state
- no-data state
- explicit error state
- refresh after new backend activity
- responsive desktop/mobile rendering

Technical/debug fields are not exposed to caregivers.

#### Validation

Primary backend validation:

`tests/python/test_phase2a_reports.py`

Coverage includes:

- Today/Week/Month backend-derived reports
- explicit no-data behavior
- invalid report requests
- duplicate/replayed event handling
- event durability across restart
- removed-device historical reporting
- explicit test-fixture clearing
- persisted household timezone boundaries
- care/safety versus maintenance separation

Targeted Python validation: PASS.

Browser validation:

`tests/playwright/phase2a_reports.spec.ts`

is discovered for both:

- `chromium-desktop`
- `chromium-mobile`

Current baseline records focused Reports browser validation as PASS.

#### Phase 2A invariants to preserve

Future work must not:

- replace durable canonical history with browser-local history
- create a second competing Reports event store
- load unlimited historical events into the browser
- fabricate report values when data is unavailable
- treat backend errors as zero activity
- delete historical activity when a device is removed
- use host timezone instead of persisted household timezone
- classify maintenance telemetry as caregiver care/safety activity

#### Deferred from Phase 2A

- PDF/export remains pending unless separately implemented later.
- Notifications were intentionally left for Phase 2B.
- large-data/load/endurance qualification remains Phase 3.


### Phase 2B - Caregiver Notifications

- Status: COMPLETE / committed
- Commit: `d43d999c7b84b107e63844d71144b6440e2bdd42`

#### Purpose

Phase 2B implemented persisted caregiver notification preferences, notification
state/history, deterministic policy/deduplication, resolution handling, and a
production-shaped delivery-adapter boundary.

Canonical care/safety events remain separate from notification delivery state.

#### Persisted notification preferences

Implemented persisted caregiver-facing preferences for applicable categories,
including:

- safety / urgent concerns
- routine concerns
- I-am-OK/check-in concerns
- monitoring coverage
- optional device maintenance
- browser alerts

Preferences survive normal restart.

Malformed settings are rejected server-side.

Settings support load/save/reload/cancel behavior.

#### Notification records

Added durable notification records separate from canonical event history.

Migration:

`backend/migrations/005_phase2b_notifications.sql`

Notification records preserve delivery/deduplication/resolution state while
canonical CloudEvents remain the underlying historical activity.

States include applicable:

- delivered/active
- `SUPPRESSED`
- `FAILED`
- `RESOLVED`

Delivery failure never deletes or hides the original care/safety event.

#### Notification-eligible care/safety concerns

Current notification policy supports applicable concerns such as:

- Call Family
- missed morning routine
- daytime inactivity
- Main Door left open
- post-door inactivity
- unusual night activity
- monitoring coverage loss
- I-am-OK overdue

Maintenance and diagnostic events are explicitly separated.

#### Explicit suppression

Normal care notifications are not generated from:

- raw telemetry
- battery runtime recalculation
- engineering diagnostics
- heartbeat/internal events
- disabled notification categories

Optional device-maintenance notification behavior remains a separate
maintenance category and must not become a care/safety concern.

#### Deduplication / idempotency

Notification correlation and database uniqueness prevent repeated delivery for
the same canonical event or unresolved correlated concern.

The design prevents notification creation merely because:

- the browser refreshes
- `/pwa/state` is polled
- an event is replayed
- an unresolved condition is repeatedly evaluated

Dedupe state survives backend restart.

#### I-am-OK overdue ownership

An architectural gap discovered during Phase 2B was corrected.

I-am-OK overdue notification creation is no longer owned by a PWA simulation
button/action.

The local backend/domain evaluation:

- opens a pending check-in deadline
- evaluates the overdue condition from backend time progression
- creates one persisted overdue notification
- does not require `/pwa/state`
- does not require Home rendering
- deduplicates repeated overdue evaluation

Accepted `OK_PRESSED` resolves the corresponding persisted I-am-OK notification
correlation.

The current local simulator `sync()/advance` represents this scheduler
behavior; autonomous production scheduling remains a production integration
boundary.

#### Coverage loss / restoration

Monitoring coverage loss can create an appropriate care notification.

Coverage restoration resolves the correlated notification while preserving
notification/event history.

#### Delivery adapter boundary

Implemented a deterministic local delivery boundary.

The architecture keeps core policy separate from delivery provider behavior so
future adapters can support:

- browser/PWA
- SMS
- email
- production push provider

Real SMS/email/production push providers are not implemented in Phase 2B.

#### Browser/PWA behavior

Settings > Notifications provides:

- persisted caregiver preferences
- browser permission/capability information
- recent notification status
- best-effort browser delivery when permission is granted and preference enabled

Browser permission denial/unavailability does not break the PWA.

The UI does not falsely claim successful delivery when delivery fails.

Technical implementation details such as raw event IDs, correlation keys,
provider credentials and retry internals are not exposed to caregivers.

#### Validation

Primary backend validation:

`tests/python/test_phase2b_notifications.py`

Coverage includes:

- preference persistence
- care/safety classification
- suppression
- failure state
- resolution
- deduplication/idempotency
- restart behavior
- I-am-OK overdue evaluation
- accepted acknowledgement resolution
- coverage loss/restoration

Targeted backend validation: PASS.

Browser validation:

`tests/playwright/phase2b_notifications.spec.ts`

Focused result:

- chromium-desktop: PASS
- chromium-mobile: PASS
- total: `6/6 PASS`

Browser coverage includes:

- load/save/reload/cancel notification preferences
- delivered/suppressed/failed/resolved states
- no technical leakage
- duplicate suppression
- maintenance activity not generating caregiver notification spam

#### Phase 2B invariants to preserve

Future changes must not:

1. make notification creation depend on the caregiver PWA being open;
2. duplicate notifications on refresh/polling/replay;
3. delete canonical event history when notification state resolves;
4. report failed delivery as successful;
5. classify maintenance diagnostics as care/safety alerts;
6. expose provider/internal notification details to caregivers;
7. allow notification preference suppression to erase the underlying
   care/safety concern.

#### Deferred boundaries

MANUAL_ONLY:
- real browser permission-prompt interaction

PRODUCTION_INTEGRATION_PENDING:
- production authentication/deployment
- real SMS provider
- real email provider
- production push provider/credentials
- autonomous production scheduler outside the deterministic local simulator

PHASE3_PENDING:
- notification storm/load testing
- high-volume delivery qualification
- long-running notification persistence/endurance

### Phase 2C - PWA Integration

- Status: COMPLETE / committed
- Commit: `4d021cdd25024774375ccdbc8cef3de57a7ba420`

#### Purpose

Phase 2C completed the remaining cross-feature PWA integration after
Phase 2A Reports and Phase 2B Notifications.

The work focused on Home, Settings, Notifications, Reports and Device Health
consistency rather than introducing another major product subsystem.

#### I-am-OK Home integration

Implemented:

- backend-owned I-am-OK overdue state reflected on Home;
- persisted active `CHECK_IN` notification state used by Home;
- accepted `OK_PRESSED` resolves the active overdue concern;
- backend-derived `last_ok_age_s`;
- caregiver-facing `Last confirmed X ago` timing;
- acknowledgement timing remains correct across browser refresh.

The underlying Home care concern remains visible even when notification
delivery for that category is suppressed.

#### Settings integration

The caregiver-visible settings label:

`Device Schedules`

was changed to:

`Routines & Activity Rules`

because the settings represent household routine/activity policy rather than
device power scheduling.

The existing internal selector:

`data-setting="Device Schedules"`

was intentionally preserved for Phase 1 compatibility.

#### Device-maintenance notification integration

Implemented a functional positive path for the existing
`device_maintenance` notification preference.

When enabled:

- qualifying maintenance conditions can create `DEVICE_MAINTENANCE`
  notification records;
- caregiver-facing device display names are used;
- maintenance remains separate from care/safety notification classification;
- maintenance does not cause the overall Home care banner to enter attention;
- maintenance is not counted as caregiver/safety activity in Reports.

#### Cross-feature consistency

Preserved the established semantics across Home, Reports and Notifications:

- canonical historical events remain the source of report activity;
- resolving notification state does not delete historical events;
- notification suppression/delivery state does not redefine event
  classification;
- device maintenance remains outside care/safety report activity;
- existing household-timezone and durable event-history behavior remains
  unchanged.

#### Important invariants

Future work must preserve:

1. I-am-OK overdue must not depend on the caregiver PWA being open.
2. Accepted I-am-OK acknowledgement clears the active concern and resolves the
   corresponding persisted notification.
3. I-am-OK elapsed confirmation timing remains backend-derived.
4. Notification suppression must not erase the underlying Home care concern.
5. Device maintenance remains separate from care/safety classification.
6. Device maintenance must not be counted as caregiver activity in Reports.
7. Existing Phase 1 Home state/color semantics remain unchanged.
8. `Routines & Activity Rules` remains the caregiver-facing name while stable
   internal compatibility identifiers may retain the previous identifier.

#### Validation

Primary backend validation:

`tests/python/test_phase2c_integration.py`

Targeted validation:

- Phase 2C integration tests: PASS
- Phase 2B Notifications regression tests: PASS
- Phase 2A Reports regression tests: PASS
- affected Phase 1 application tests: PASS

Browser validation:

`tests/playwright/phase2c_integration.spec.ts`

Validated on:

- `chromium-desktop`: PASS
- `chromium-mobile`: PASS

Phase 2C was also included successfully in the later Phase 2 focused browser
qualification and final `make release-gate-final` qualification.

### Phase 2D - Final Phase 2 Reconciliation, Performance Trim and Qualification

- Status: COMPLETE / QUALIFIED
- Implementation/qualification commit:
  `9499381` (`Complete Phase 2D reconciliation and qualification`)
- Final qualification: `make release-gate-final` PASS
- Phase 2 overall status: COMPLETE / QUALIFIED

#### Gap audit summary

No unresolved software-testable Phase 2 product requirement was found after
reconciling the master specification with current code and tests.

Classifications:

- COMPLETE: Home current-state integration, Devices/Manage Devices, Settings
  Home Details/Family Members/Battery/Routines/Notifications, Today/Week/Month
  Reports, durable canonical event history, persisted notification preferences
  and records, backend-owned I-am-OK overdue evaluation, care/safety versus
  maintenance classification, removed-device historical reporting, desktop and
  mobile Playwright coverage.
- MANUAL_ONLY: real browser notification permission prompt.
- HW_REQUIRED: ESP32/RF/Wi-Fi provisioning, physical sensors and physical
  battery calibration.
- PRODUCTION_INTEGRATION_PENDING: production authentication/deployment, SMS
  provider, email provider, production push provider and autonomous production
  scheduler.
- PHASE3_PENDING: stress/load/endurance/soak, event and notification storms,
  DB scale, resource leakage and fault injection.

#### Cross-feature consistency confirmed

Current automated coverage verifies the high-risk Phase 2 flows:

- I-am-OK overdue opens a Home concern and notification, accepted
  `OK_PRESSED` clears Home, resolves the notification and preserves historical
  activity.
- monitoring coverage loss opens Home attention and notification state;
  restoration resolves the correlated notification and preserves history.
- Main Door open-too-long, post-door inactivity and night unusual activity are
  Home care concerns, eligible for notifications, and remain consistently
  classified in Reports/history without Door/battery contamination.
- device maintenance and battery diagnostics remain Device Health/maintenance
  concerns, with optional `DEVICE_MAINTENANCE` notification behavior; they do
  not become care/safety Home events or Reports care activity.
- removed devices stay inactive/unregistered while historical report activity
  remains meaningful.

#### Performance and UX trim

Implemented Phase 2D performance trims:

- `GET /pwa/state?scope=home` returns a compact Home/current-state projection
  for normal Home polling.
- existing full `GET /pwa/state` remains available for validation and
  domain-specific hydration where required.
- Reports are no longer fetched during initial Home load; Reports fetch only
  when Reports is opened or the selected period changes.
- notification preference/history polling for browser delivery is throttled,
  preference-cached and bounded.
- repeated DOM rebuilds are reduced to the active tab where practical.
- full device state is fetched while Devices is the active tab or after
  device create/edit/remove actions.
- the lightweight no-framework HTML/CSS/JS architecture remains unchanged.

Existing bounds preserved:

- Home Recent Important Events: 20 rendered events.
- backend snapshot recent events: 6 domain events.
- canonical timeline projection: explicit limit, currently 40 for the PWA lab.
- notification records endpoint: limit bounded to 1..100, default 20.
- report windows: Today, seven-day Week and calendar Month windows; backend
  aggregation/highlights are bounded.

The service worker continues to cache only explicitly allowlisted static app
assets and does not cache dynamic caregiver-state endpoints.

#### Phase 2D qualification regressions and resolutions

##### Regression 1 - Device Health caregiver display name

After compact Home polling was introduced, the full `devices[]` metadata was
no longer present in `scope=home`.

Device Health still received offline device IDs such as:

`kitchen`

but could no longer resolve the caregiver-facing name:

`Kitchen Node`

This caused the UI to show the internal identifier rather than the configured
device display name.

Resolution:

- preserved the compact Home payload;
- added only the minimal caregiver-facing name mappings required by Device
  Health;
- added `offline_device_names`;
- added `high_drain_device_names`;
- did not restore the full device/settings payload.

Focused Phase 1 UI contract validation subsequently passed on desktop/mobile.

##### Regression 2 - Durable-history validation isolation

After Phase 2A made canonical CloudEvent history durable, validation runners
that reused one Lab and called plain `reset()` retained events from previous
scenarios.

Observed failure:

`stream-offline-replay` contained two `MOTION` events when the isolated fixture
expected one.

Root cause:

test/harness isolation, not replay/idempotency product behavior.

Resolution:

- dummy sensor stream validation uses `reset(test_fixture=True)` per stream;
- PWA frontend validation uses `reset(test_fixture=True)` per validation run;
- production event durability semantics remain unchanged.

Validation after the fix:

- dummy sensor streams: PASS `5/5`;
- Phase 2D reconciliation tests: PASS.

##### Regression 3 - Devices tab stale full-state data

The Phase 2D active-tab optimization initially kept normal polling on compact
Home state even while the Devices tab was active.

This caused:

- a newly registered device to exist in the backend but not appear in Devices;
- direct backend online/offline health changes to remain visually stale.

Resolution:

- device create/edit/remove performs a full state refresh;
- normal polling fetches full state while `currentTab === 'devices'`;
- Home polling remains compact;
- Reports remain on-demand;
- notification polling remains throttled/cached;
- active-tab rendering remains enabled.

The fix preserves the Phase 2D performance strategy while ensuring Devices
uses fresh authoritative device state.

#### Validation

Added:

`tests/python/test_phase2d_reconciliation.py`

Coverage includes:

- compact Home payload excludes on-demand Devices/Settings/Reports/Notifications
  payloads;
- compact Home events remain bounded;
- full `/pwa/state` compatibility remains available;
- invalid state scopes are rejected;
- compact Device Health retains caregiver-facing device identity;
- validation runners isolate durable history correctly.

Targeted socket-free validation:

- Phase 2A/2B/2C/2D focused Python tests: PASS
- affected Phase 1/foundation tests: PASS
- JavaScript tests: PASS
- JavaScript syntax validation: PASS
- dummy sensor stream validation: PASS `5/5`
- `git diff --check`: PASS

Manual browser qualification:

- Phase 1 UI contract:
  - `chromium-desktop`: PASS
  - `chromium-mobile`: PASS
  - focused result: `12/12 PASS`
- Phase 2 focused browser suite:
  - Phase 1 UI contract
  - Phase 2A Reports
  - Phase 2B Notifications
  - Phase 2C Integration
  - desktop/mobile result: `34/34 PASS`
- Phase 1 Foundation regressions after Devices refresh fix:
  - desktop/mobile: PASS

#### Final qualification

Authoritative command:

`make release-gate-final`

Result:

PASS

Host release gate passed, including:

- validation coverage
- contracts
- C++ unit tests
- Python/backend/database/logging
- JavaScript application tests
- product variants
- feature variants
- lab build
- dummy sensor streams
- functional catalog
- HTTP integration
- PWA bridge
- PWA 68 API
- PWA 68 frontend
- C++ sanitizers
- trace build
- browser E2E

Mandatory Playwright qualification also passed for:

- `chromium-desktop`
- `chromium-mobile`

Phase 2 is therefore COMPLETE / QUALIFIED.

## Authoritative Validation Locations

- Phase 1 UI contract:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/validation/phase1_ui_contract.json`
- Python tests:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/python/test_*.py`
- Playwright specs:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/playwright/*.spec.ts`
- Release gate target:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/Makefile`

## Deferred Boundaries

- MANUAL_ONLY:
  real browser notification permission prompt.
- HW_REQUIRED:
  ESP32/RF/Wi-Fi provisioning, physical sensors, physical battery calibration.
- PRODUCTION_INTEGRATION_PENDING:
  SMS/email/push providers, production authentication/deployment, autonomous
  production scheduler.
- PHASE3B_3C_PENDING:
  LARGE/EXTENDED qualification, accelerated long household soak, concurrent
  API load, notification-provider storm qualification, DB/resource failure
  injection and restart/recovery under substantial load.

## Phase 3B Pause / Resume Point for HW-M1

Phase 3B is intentionally paused while HW-M1 target integration remains the
active engineering line. HW-M1.2 and the separate C3 FOTA checkpoint are
qualified. HW-M1.3 target-runtime integration is IMPLEMENTED and HOST
VALIDATED; target build/composition is VALIDATED while physical hardware
validation remains pending, so HW-M1.3 is not QUALIFIED.
The stable qualified host/PWA branch is `feature/full-pwa-e2e`. The last
qualified Phase 3B implementation checkpoint before HW-M1 is `0d6a2fc`; the
current documented baseline before branching for HW-M1 is `c43c829`.

Qualified Phase 3B work already completed:

- scale/read-path optimization (`fee5854`);
- Reports scalability (`0e5a9e3`); and
- concurrent API / household isolation (`0d6a2fc`).

Remaining Phase 3 work is unchanged:

- notification-provider storm/failure qualification;
- restart/recovery qualification;
- DB/resource fault injection;
- EXTENDED/endurance / long-soak validation; and
- final Phase 3 reconciliation and qualification.

The P0 audit at `docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md` approved HW-M1:
software is ready, no unresolved host/backend/PWA defect blocks the milestone,
and F14 remains a software gap but does not block HW-M1. HW-M1 is one ESP32
DevKit hub, one ESP32-C3 node, and one PIR proving PIR → C3 sensing →
NodeMessage → ESP-NOW → hub ingest/ACK/dedupe/rules → hub Wi-Fi/backend
transport → backend persistence/read models → PWA. The currently qualified
scope is the HW-M1.2 PIR-to-Hub path plus separate C3 FOTA; target runtime
integration, backend transport and PWA delivery remain open.

When Phase 3 resumes, the first step is reconciliation, not immediate new
Phase 3 implementation:

1. Read `CURRENT_BASELINE.md`, `docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md`,
   `docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md`, the current Phase 3
   stress/qualification documents, and `docs/progress/PROJECT_HISTORY.md`.
2. Inspect Git history and all HW-M1 changes since the pre-HW-M1 baseline.
3. Compare the integrated code with qualified checkpoint `0d6a2fc`.
4. Identify HW-M1 effects on node and hub runtimes, radio/transport,
   persistence, configuration, backend interfaces, PWA contracts,
   concurrency assumptions, performance assumptions, and release tests.
5. Re-run and reconcile applicable existing release and Phase 3 gates on the
   integrated baseline.
6. Continue the remaining Phase 3 work only after reconciliation.

The intended branch strategy is `feature/hw-m1` for HW-M1 development while
`feature/full-pwa-e2e` remains the stable qualified host/PWA reference. Hardware
work may change shared portable code, backend interfaces, or tests when needed,
but those changes remain isolated on `feature/hw-m1` until reconciled and
qualified. Integration back to the main development line must be deliberate
and followed by regression/release qualification; partially working HW-M1
changes should not be continuously merged into the stable PWA branch.

`0d6a2fc` remains a historical qualified checkpoint even after HEAD advances.
Future HW-M1 commits do not replace or redefine historical Phase 3 anchors. Git
and code/tests remain exact implementation truth; `CURRENT_BASELINE.md` remains
the current operational and resume truth.

## HW-M1 working status

- Implementation branch: `feature/hw-m1-runtime-integration`
- Qualified parent branch: `feature/hw-m1`
- Implementation branch point: `4645098`
- Branch point: `9b391fa`
- Stable host/PWA reference: `feature/full-pwa-e2e`
- HW-M1 status: HW-M1.2 QUALIFIED / PASS; separate C3 FOTA QUALIFIED / PASS;
  HW-M1.3 IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED /
  HARDWARE VALIDATION PENDING
- Pre-build documentation/resume HEAD: `0546b28`
- Last host-validated implementation commit: `1d41864`
- Last physically qualified HW checkpoint: `50abdce`
- Previous documentation/resume checkpoint: `4645098`
- Current checkpoint: HW-M1.3B target composition/build validated; next sub-step is physical qualification
- HW-M1.3 status: IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED /
  HARDWARE VALIDATION PENDING
- Host regression status: focused C++ PASS (124 checks); most full-gate stages
  PASS; complete release gate ENVIRONMENT BLOCKED by sandbox localhost policy
- Target-build status: C3 and Hub ESP-IDF v6.0.3 builds PASS and fit their
  1920 KB OTA slots; physical HW-M1.3 evidence does not exist
- Plan: `docs/hw/HW_M1_IMPLEMENTATION_PLAN.md`
- Host-only evidence: `docs/hw/evidence/HW_M1_3_HOST/README.md`
- Target-build-only evidence:
  `docs/hw/evidence/HW_M1_3_TARGET_BUILD/README.md`

## Next

1. **HW-M1.3C — physical target qualification:** flash the build-validated C3
   and Hub compositions, run the manual sequence below, and retain
   serial/configuration evidence.
2. Rerun `make release-gate-final` in a normal local terminal where localhost
   sockets are permitted.
3. Keep HW-M1.3 at HARDWARE VALIDATION PENDING until every physical criterion
   passes; do not infer qualification from host or target-build success.

### Exact manual HW-M1.3 hardware validation

1. Flash the C3 build's bootloader, partition table, OTA data and
   `gs_hw_m1_node.bin` into the USB bootstrap `ota_0`; boot and capture serial.
2. Verify C3 MAC `14:63:93:C5:D1:58`, channel 1, TX API value 40
   (10 dBm), GPIO4 PIR and active-low GPIO8 LED.
3. Flash the Hub build's bootloader, partition table, OTA data and
   `gs_hw_m1_hub.bin`; boot and capture serial.
4. Verify Hub MAC `5C:01:3B:BE:B9:F8`, channel 1, bounded
   data/control queues and one HubRuntime owner task.
5. Allow the AM312 ten-second stabilization interval to finish without a
   fabricated boot-time motion event.
6. Trigger motion and capture C3 sensing -> `NodeRuntime::record()` with the
   complete node/session/sequence identity.
7. Capture bounded `NodeMessage` encoding/send and the separate ESP-NOW MAC
   result passed to `NodeRuntime::transport_result()`.
8. Capture Hub callback enqueue with source MAC/RSSI/channel, followed by
   owner-task decode rather than callback-side business processing.
9. Verify the Hub admits the mapped current session, calls
   `radio_message_callback()` and `run_state_once()`, and journals the event.
10. Verify a typed Durable `NodeAckMessage` returns and only the matching node
    event is retired.
11. Deliberately suppress/drop an application ACK where practical; verify MAC
    success alone does not retire evidence and retry preserves the EventKey.
12. Deliver the duplicate retry and verify journal identity remains
    duplicate-safe; record the existing duplicate-reducer gap if observable.
13. Reboot the C3; verify NVS session increment, sequence restart under the new
    session, and rejection of stale prior-session traffic.
14. Verify RSSI/channel diagnostics remain visible without overwriting
    semantic message RSSI.
15. Run both qualified FOTA rotations, verify PIR restoration, then repeat the
    business-message/ACK path after update.

## RESUME HERE

- Repository root: `/home/udaybhan/projects/Ghar_sajag`.
- Active branch: `feature/hw-m1-runtime-integration`; qualified parent is
  `feature/hw-m1`; frozen software/PWA reference is `feature/full-pwa-e2e`,
  with HW-M1 fork point `9b391fa`.
- Pre-build documentation/resume commit: `0546b28` (`Document HW-M1.3
  checkpoint and resume state`); the current development checkpoint is this
  document's target-build commit.
- Last host-validated implementation commit:
  `1d41864dd3d0004ed4dbfa608bb85baf3e35a91f`.
- Remote development branch: `origin/feature/hw-m1-runtime-integration`
  contains `0546b28`; this target-build checkpoint is local until explicitly
  pushed.
- Previous documentation/resume checkpoint: `4645098`; it was documentation
  only and did not qualify new physical firmware behavior.
- Active code directory:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.
- Latest qualified commit: `50abdce` (`Qualify dual-slot ESP-NOW node FOTA`).
- Expected working-tree state after handoff: clean.
- Current milestone: HW-M1.3 — Target Runtime Integration,
  **IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / HARDWARE
  VALIDATION PENDING**.
- Implemented modules: bounded data-plane codec; persistent boot-session
  policy; ESP32-C3 GPIO/ESP-NOW/NodeRuntime adapter; ESP32 Hub
  callback-queue/HubRuntime/ACK adapter; separate control-plane queue boundary;
  wire-compatible FOTA sender/receiver workers; C3 and Hub ESP-IDF product
  compositions; focused codec/ACK/retry/session tests.
- Target projects: C3
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/idf/`;
  Hub
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/idf/`.
- Target builds: ESP-IDF v6.0.3 C3 `esp32c3` PASS, 824,368 bytes with
  1,141,712 bytes OTA headroom; Hub `esp32` PASS, 1,592,848 bytes with
  373,232 bytes OTA headroom. Both preserve 4 MB flash, the exact dual
  `0x1E0000` OTA layout, and rollback.
- Hub configuration: ESP32 DevKit / ESP-WROOM-32, ESP32-D0WD-V3 rev 3.1,
  4 MB flash, STA MAC `5C:01:3B:BE:B9:F8`, CP2102 interface, ESP-NOW channel 1.
- Node configuration: ESP32-C3 SuperMini-style board, 4 MB flash, MAC
  `14:63:93:C5:D1:58`, AM312 GPIO4, active-low LED GPIO8, ESP-NOW channel 1,
  TX API value 40 = 10 dBm.
- Tests: focused `PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++` PASS with
  124 checks; `git diff --check` PASS at the target-build checkpoint. Full
  release gate did not pass because this sandbox blocks localhost socket creation/binding; all
  non-localhost stages listed in `HW_M1_3_HOST/README.md` passed. Rerun the
  complete gate in a normal local terminal.
- Last successful physical qualification: dual-slot C3 FOTA
  `ota_0 -> ota_1 -> ota_0`, after HW-M1.2 physically qualified
  `PIR -> C3 -> ESP-NOW -> Hub`. That qualification remains intact and the
  immutable HW-M1.2/FOTA evidence snapshots were not changed.
- Unresolved limitations: RF range optimization; channel 1 did not prove a
  range solution; 10 dBm remains the qualified C3 baseline; production
  ESP-NOW encryption/key management, signed authenticity, anti-rollback and
  backend firmware distribution are open; the Hub's embedded C3 image remains
  an engineering qualification mechanism rather than production distribution;
  physical HW-M1.3 validation, trusted Hub time, backend/PWA integration and later
  resilience/telemetry work remain open.
- Exact next engineering task: HW-M1.3C — physically flash and validate the
  build-validated C3 and Hub compositions using the exact sequence above.
- Read first: this `RESUME HERE` section; `docs/hw/HW_M1_IMPLEMENTATION_PLAN.md`;
  `docs/progress/PROJECT_HISTORY.md`; `docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md`;
  `docs/hw/evidence/HW_M1_2/README.md`; `docs/hw/evidence/HW_M1_FOTA/README.md`;
  `docs/hw/evidence/HW_M1_3_HOST/README.md`;
  `docs/hw/evidence/HW_M1_3_TARGET_BUILD/README.md`;
  and, under
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`,
  `shared/include/gs/domain.hpp`, `shared/include/gs/protocol.hpp`,
  `shared/include/gs/ports.hpp`, `firmware/node/runtime/node_runtime.hpp`,
  `firmware/node/runtime/node_runtime.cpp`,
  `firmware/node/components/radio/node_radio.hpp`,
  `firmware/node/components/radio/node_radio.cpp`,
  `firmware/common/transport/`, `firmware/node/components/sensing/`,
  `firmware/node/target/esp32c3/`,
  `firmware/hub/runtime/hub_runtime.hpp`,
  `firmware/hub/runtime/hub_runtime.cpp`,
  `firmware/hub/components/ingest/`, `firmware/hub/target/esp32/`, and
  `firmware/hub/runtime/FREERTOS_BINDING.md`, plus `Makefile`.
- Target ESP-IDF builds: PASS in this checkpoint; physical validation was not
  run. Use the exact sequence above and write a new immutable HW-M1.3 physical
  evidence snapshot only after executing it.
- Qualification reminder: HW-M1.3 is not physically qualified. Do not label it
  HW VALIDATED or QUALIFIED until the host and target exit criteria in the plan
  are demonstrated and captured as evidence.
- Expected next milestone after HW-M1.3 physical qualification: HW-M1.4 — Hub
  Wi-Fi/backend transport.
