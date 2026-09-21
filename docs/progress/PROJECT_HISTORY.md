# Ghar Sajag / Parivar Saathi Engineering History

**Document revision:** HW-M1.4-MASTER-ROADMAP
**History covered through:** HW-M1.4 master forward-roadmap planning
**Product baseline through:** Parivar Saathi v1.5.4
**PWA / BatteryAnalytics baseline through:** v3.4.3
**Latest qualified Phase 3B checkpoint covered:** `0d6a2fc`
**Previous qualified Phase 3B scale/read-path checkpoint:** `fee5854`
**Permanent Phase 3A implementation/qualification anchor:** `4dcaf99`
**Latest qualified HW branch:** `fix/hw-m1-4-node-offline-resilience`
**Latest physically qualified firmware/artifact provenance:** `bb34f5e`
**Current implementation branch:** `fix/hw-m1-4-node-offline-resilience`
**Updated:** 2026-09-21

This file is an append-only chronological engineering history.

# Ghar Sajag / Parivar Saathi Engineering History

This file is an append-only chronological engineering history.

Do not delete or rewrite completed historical entries when later phases are
implemented. Corrections and refinements should be recorded as later entries.

For current implementation status, see:
`docs/progress/CURRENT_BASELINE.md`

For intended scope and phase boundaries, see:
`docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md`

## Phase 1 - Persistent Foundation

Commit anchors:
- `9cb3f4a` - persistent settings and device management
- `959c854` - caregiver UI corrections and regression coverage
- `9757791` - Phase 1 validation hardening

Summary:
- persistent household/settings foundation
- Family Members and roles
- authoritative device registry
- Devices / Manage Devices
- battery/device health
- routine/activity configuration
- Home caregiver behavior
- deterministic simulator and validation framework

Important validation hardening:
- required + forbidden assertions
- cross-card contamination checks
- desktop/mobile browser coverage
- release-gate process/port isolation

Qualification:
- `make release-gate-final`: PASS


## Phase 2A - Reports and Durable Event History

Commit:
`97f004fbd64b6dbdce9f163bdb017b7909f14da1`

Summary:
- Today / Week / This Month reports
- backend-derived Reports API
- durable canonical CloudEvent history
- SQLite event persistence
- restart durability
- removed-device historical reporting
- persisted household-timezone report boundaries

Important architectural decision:
Canonical event history became durable and remained the source of truth for
report projections.

Validation:
- backend Reports suite: PASS
- desktop/mobile Reports Playwright: PASS


## Phase 2B - Notifications

Commit:
`d43d999c7b84b107e63844d71144b6440e2bdd42`

Summary:
- persisted notification preferences
- persisted notification records
- care/safety classification
- maintenance separation
- dedupe/idempotency
- FAILED / SUPPRESSED / RESOLVED states
- backend-owned I-am-OK overdue evaluation
- coverage-loss/restoration resolution
- delivery-adapter boundary

Validation:
- notification backend suite: PASS
- desktop/mobile notification Playwright: PASS


## Phase 2C - PWA Integration

Commit:
`4d021cdd25024774375ccdbc8cef3de57a7ba420`

Summary:
- backend-owned I-am-OK state reflected on Home
- backend-derived "Last confirmed" timing
- Routines & Activity Rules caregiver-facing label
- optional DEVICE_MAINTENANCE notifications
- Home / Reports / Notifications classification consistency

Validation:
- targeted backend regressions: PASS
- desktop/mobile Phase 2C Playwright: PASS


## 2026-09-16 - Phase 2D Reconciliation and Qualification

Purpose:
Final Phase 2 reconciliation, performance trimming, cross-feature validation,
and release qualification.

Performance / architecture improvements:
- compact `/pwa/state?scope=home`
- Reports loaded on demand
- notification polling throttled/cached
- active-tab rendering
- Phase 2D payload contract coverage
- full device state fetched only when Devices requires it

Regression 1 - Device Health display name:
Compact Home state removed full `devices[]`, causing Device Health to render
internal ID `kitchen` instead of caregiver-facing `Kitchen Node`.

Resolution:
- retained compact Home payload
- added minimal caregiver-facing device-name maps
- did not restore full devices/settings payload

Regression 2 - Durable-history validation isolation:
Dummy sensor/PWA validation scenarios reused durable canonical event history,
causing previous MOTION events to leak into later assertions.

Resolution:
- validation runners use `reset(test_fixture=True)`
- production durability behavior remains unchanged

Regression 3 - Devices tab stale state:
Phase 2D compact polling left `state.devices` stale while Devices was active.

Symptoms:
- newly registered device did not immediately appear
- backend offline transition remained visually Active

Resolution:
- device create/edit/remove explicitly refreshes full state
- polling uses full state only while Devices tab is active
- Home polling remains compact
- Reports/Notifications optimizations remain intact

Final qualification:
- focused Phase 1 UI contract: PASS
- focused Phase 2 browser suite: PASS
- host release gate: PASS
- mandatory desktop/mobile Playwright gate: PASS
- `make release-gate-final`: PASS

Phase 2 status:
COMPLETE / QUALIFIED

## 2026-09-16 - Phase 2D Commit Anchor Recorded

Implementation / qualification commit:
`9499381` - Complete Phase 2D reconciliation and qualification

Repository state at the Phase 2D implementation checkpoint:
- branch: `feature/full-pwa-e2e`
- implementation/qualification commit pushed to origin
- Phase 2: COMPLETE / QUALIFIED
- authoritative final qualification: `make release-gate-final` PASS

This commit is the Phase 2D implementation/qualification anchor. Later
documentation-only commits may become repository HEAD without changing this
qualified implementation anchor.

## 2026-09-16 - Phase 3A Performance and Stress-Foundation Checkpoint

Document revision:
`P3A-R1`

Historical qualified baseline retained:
`9499381` - Complete Phase 2D reconciliation and qualification

Summary:
- established deterministic static and API payload measurement with structural
  regression budgets;
- moved the engineering validation catalog off initial Home startup;
- removed unnecessary full-state Settings hydration;
- guarded and throttled polling without weakening backend-owned safety rules;
- added change-aware active-tab rendering and visibility recovery;
- changed durable history projections to indexed/range/limit-aware SQLite reads;
- completed the bounded static-only service-worker module allowlist;
- added isolated deterministic SMALL/MEDIUM/LARGE/EXTENDED stress profiles and
  performance/stress/endurance Make targets;
- added Python, JavaScript and desktop/mobile Playwright regression coverage.

Checkpoint evidence:
- profiler structural budgets: PASS;
- SMALL deterministic stress: PASS;
- MEDIUM deterministic stress: PASS;
- targeted Phase 1/2 Python regressions: PASS;
- full Python discovery: PASS (94/94);
- JavaScript tests: PASS (3/3);
- 20 socket-free/compiled release-gate stages: PASS;
- Playwright desktop/mobile discovery: PASS (86 instances);
- socket-bound HTTP/PWA/browser stages: ENVIRONMENT_BLOCKED by Codex loopback
  EPERM and therefore still require WSL execution.

Qualification status:
IMPLEMENTED / QUALIFICATION PENDING. This entry does not replace or weaken the
qualified Phase 2D anchor and does not claim Phase 3A QUALIFIED before the
mandatory browser/final release gate is executed successfully.

## 2026-09-16 - Phase 3A Final Qualification

Document revision:
`P3A-R1`

Qualification result:
COMPLETE / QUALIFIED

Authoritative final qualification:
- `make release-gate-final`: PASS;
- mandatory Chromium desktop browser suite: PASS;
- mandatory Chromium mobile browser suite: PASS;
- performance profile: PASS;
- SMALL deterministic stress: PASS;
- MEDIUM deterministic stress: PASS;
- Python regression suite: PASS (`96/96`);
- JavaScript regression suite: PASS (`3/3`);
- `git diff --check`: PASS.

Performance / UX result:
- the 28,770-byte engineering validation catalog remains removed from initial
  Home startup;
- compact Home state remains 1,216 B in the recorded deterministic baseline;
- the post-fix profiler reported 80,542 B static total and remained within the
  established Phase 3A structural budget;
- Reports, Settings and Devices retain the Phase 3A lazy/bounded hydration and
  active-domain refresh rules.

Browser qualification found and corrected three sequencing defects:
- Reports refresh used a deadline sampled from the Home poll loop, allowing an
  effective delay beyond the intended active refresh interval;
- an older Home poll response could overwrite a newer explicit action result;
- simulator `simulation_now` can legitimately move backward after reset, so the
  stale-response guard now uses a reset epoch before comparing simulator time.

The Phase 2D qualified implementation anchor `9499381` remains historical
evidence. The Phase 3A implementation/qualification commit anchor is pending
creation of the qualified commit and will be recorded in a later append-only
entry.

## 2026-09-16 - Phase 3A Commit Anchor Recorded

Implementation / qualification commit:

`4dcaf99` - Complete Phase 3A performance and stress foundation

Repository state at the Phase 3A implementation checkpoint:
- branch: `feature/full-pwa-e2e`
- implementation/qualification commit pushed to origin
- Phase 3A: COMPLETE / QUALIFIED
- authoritative final qualification: `make release-gate-final` PASS

This commit is the Phase 3A implementation/qualification anchor. Later
documentation-only commits may become repository HEAD without changing this
qualified implementation anchor.

## 2026-09-16 - Phase 3B Durable-History Read Optimization (In Progress)

Status:
IMPLEMENTED / MANUAL QUALIFICATION PENDING

Summary:
- confirmed temporary SQLite sort/group B-trees on representative hot event
  queries and added migration-managed indexes matching their filters/orders;
- replaced recursive per-poll conversion of the historical incident population
  with the bounded active incident categories required by caregiver Home;
- preserved public snapshot, durable history, Reports and caregiver-visible
  care semantics;
- added bounded stderr stage/milestone progress and diagnostic-only per-stage
  timings to the stress runner;
- added focused query-plan, ordering, projection-scale and JSON-stream tests.

Host evidence:
- focused Phase 3B tests: PASS (`5/5`);
- full Python discovery: PASS (`101/101`);
- JavaScript application tests: PASS (`3/3`);
- performance/SMALL and MEDIUM stress gates: PASS;
- explicit LARGE host diagnostic: PASS (25,000 accepted, 2,500 duplicates,
  250 rejected, 5,000 notifications, zero request failures, 75.14 s wall time);
- MEDIUM unprofiled diagnostic: 11.93 s before, 4.51 s after on the same host;
- MEDIUM profiled diagnostic: supplied ~17.45 s before, 6.94 s after.

This is not a Phase 3B completion or qualification entry. Manual acceptance and
mandatory desktop/mobile browser qualification remain pending. Phase 3A remains
COMPLETE / QUALIFIED at permanent implementation anchor `4dcaf99`.

## 2026-09-17 - Phase 3B Scale/Read-Path Optimization Qualified Checkpoint

Qualified checkpoint: `fee5854`.

Phase 3B overall status remains IN PROGRESS. This checkpoint qualified the
PWA/read-path optimization while preserving Phase 3A as COMPLETE / QUALIFIED at
the permanent implementation/qualification anchor `4dcaf99`.

Qualification evidence:
- LARGE correctness: PASS;
- LARGE runtime improved from approximately 461 s to approximately 72 s;
- Playwright cleanup race fixed;
- `make playwright-gate`: PASS, 86/86;
- `make release-gate-final`: PASS.

Remaining Phase 3B work includes Reports scaling, controlled concurrent API
load, household isolation, notification storm qualification, and
restart/recovery. EXTENDED/endurance remains pending.

## 2026-09-17 - Phase 3B Reports Scalability (In Progress)

Status:
IMPLEMENTED / HOST VALIDATED / MANUAL QUALIFICATION PENDING

Root cause and implementation:
- repeated Today/Week/Month generation selected full durable event rows,
  parsed every JSON payload, and materialized every matching `CloudEvent` before
  Python filtering and aggregation;
- the existing range query was indexed, so no new index was added;
- report-specific SQLite reads now aggregate summary/trend facts, return
  grouped motion timestamps for timezone-aware night classification, aggregate
  bounded room activity, and materialize only six highlights;
- no cache, second report store, migration, or API/schema change was introduced;
- stress diagnostics now include non-gating Today/Week/Month subtotals.

Host evidence:
- optimized-versus-reference Today/Week/Month payload comparison: PASS;
- focused report/Phase 2/Phase 3 regressions: PASS (`21/21`);
- full Python discovery: PASS (`105/105`);
- JavaScript application tests: PASS (`3/3`);
- performance/SMALL and MEDIUM stress gates: PASS;
- MEDIUM report stage: 675.680 ms before, 106.244 ms after;
- explicit LARGE: PASS, 52.290 s total and 5.320 s Reports versus the qualified
  baseline of approximately 72.2 s total and 27.3 s Reports;
- LARGE retained 25,000 accepted, 2,500 duplicate, 250 malformed rejected,
  zero request failures, and a 16,424,960-byte database.

This entry does not qualify or complete Phase 3B. Manual/browser qualification
and a committed checkpoint remain pending. `fee5854` remains the previous
qualified Phase 3B checkpoint. Phase 3A remains COMPLETE / QUALIFIED at
permanent anchor `4dcaf99`. Remaining Phase 3B scope is controlled concurrent
API load, household isolation, notification-provider storm qualification, and
restart/recovery; EXTENDED/endurance remains pending.

## 2026-09-17 - Phase 3B Reports Scalability Qualified Checkpoint

Qualified checkpoint: `0e5a9e3`.

Phase 3B overall status remains IN PROGRESS. This checkpoint qualifies the
Reports scalability work; it does not complete the broader Phase 3B scope.
`fee5854` remains the earlier qualified Phase 3B scale/read-path checkpoint,
and `4dcaf99` remains the permanent Phase 3A implementation/qualification
anchor with Phase 3A COMPLETE / QUALIFIED.

Manual LARGE qualification:
- correctness: PASS;
- Reports stage improved from approximately 27.3 s to approximately 4.9 s;
- total LARGE runtime improved from approximately 72.2 s to approximately
  47.6 s;
- request failures: zero;
- `make release-gate-final`: PASS.

The final release gate now includes `performance-test` and its SMALL
deterministic stress smoke. MEDIUM and LARGE remain outside the normal final
gate, with LARGE reserved for explicit/manual milestone qualification.
EXTENDED/endurance remains outside the normal final gate as endurance/soak
work only.

Remaining Phase 3B work is controlled concurrent API load, household
isolation, notification storm qualification, and restart/recovery;
EXTENDED/endurance remains pending.

## 2026-09-17 - Phase 3B Controlled Concurrent API Load and Household Isolation

Status:
IMPLEMENTED / HOST VALIDATED / MANUAL QUALIFICATION PENDING

Summary:
- found that the Python event identity contract was household-local while the
  SQLite `event_id` primary key was still global;
- added migration-managed household-local canonical event identity without
  rewriting existing relational foreign-key identifiers;
- made durable event acceptance/duplicate detection atomic;
- serialized complete core/local-lab requests through the existing shared
  re-entrant lock while retaining threaded request dispatch;
- added a fixed-seed, six-worker two-household WSGI/store harness covering
  simultaneous event writes/replays, compact/full reads, snapshots,
  Today/Week/Month Reports, device health, notifications/preferences and
  caregiver acknowledgement;
- deliberately reused canonical event IDs and caregiver-facing device names
  across households and verified no cross-household event, snapshot, report,
  incident, notification, device, preference or database-row leakage;
- kept the explicit concurrency target outside `release-gate-final`.

Focused host evidence:
- concurrency plus Phase 3B projection/report regressions: PASS (`9/9`);
- focused schema/migration suite: PASS (`9/9`), including explicit 006→007
  preservation of history, reports, ordering and historical references;
- full Python: PASS (`107/107`); JavaScript: PASS (`3/3`);
- performance/SMALL and MEDIUM stress: PASS;
- 12 accepted, 6 duplicate and 2 rejected requests per household;
- 3 incidents and 3 persisted notifications per household;
- zero unexpected failures and zero SQLite busy/lock failures;
- no worker-thread leak; simulator process cleaned up;
- 147.446 ms focused harness duration and 3,945.727 ms MEDIUM duration
  (diagnostic only).

This entry does not qualify or complete Phase 3B. Qualified Reports checkpoint
`0e5a9e3`, earlier scale/read-path checkpoint `fee5854`, and permanent Phase 3A
anchor `4dcaf99` remain unchanged. Notification-provider storm qualification,
restart/recovery, later database/resource failure injection and
EXTENDED/endurance remain pending.

## 2026-09-17 - Phase 3B Concurrent API Load and Household Isolation Qualified

Manual qualification is complete for the concurrent API and household-isolation
checkpoint. `make concurrency-test`, `make release-gate-final`, Playwright
(`86/86`), SMALL, MEDIUM and LARGE passed. LARGE recorded 25,000 accepted,
2,500 duplicates, 250 rejected, zero request failures, `correctness_gate`
PASS, a 20,828,160-byte database, approximately 64 MB maximum RSS and
approximately 49.9 seconds wall time. The migration 006→007 preservation
regression also passed.

Phase 3B remains IN PROGRESS. The new checkpoint commit hash is intentionally
not recorded yet; `0e5a9e3` and permanent Phase 3A anchor `4dcaf99` remain
unchanged. Notification-provider storm qualification, restart/recovery, later
database/resource failure injection and EXTENDED/endurance remain pending.

## 2026-09-17 - Phase 3B Concurrent API Load and Household Isolation Pointer

Qualified checkpoint: `0d6a2fc`.

This documentation-only pointer records the completed concurrent API and
household-isolation qualification. Phase 3B remains IN PROGRESS. `0e5a9e3`
remains the qualified Reports scalability checkpoint, `fee5854` remains the
earlier Phase 3B scale/read-path checkpoint, and `4dcaf99` remains the permanent
Phase 3A anchor.

Remaining Phase 3B work is unchanged: notification-provider storm/failure
qualification, restart/recovery, DB/resource fault injection,
EXTENDED/endurance and final Phase 3 qualification.

## 2026-09-17 - P0 Software-Gap Audit and HW-M1 Transition

The complete P0 software-gap audit is recorded in
`docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md`. The audit found no unresolved
host/backend/PWA blocker, so HW-M1 is approved to start with one ESP32 DevKit
hub, one ESP32-C3 node, and one PIR. F14 remains the open software gap and is
not an HW-M1 blocker, but remains a pilot/commercial P0 blocker. Target ESP32
adapters and HIL evidence are the next work. Phase 3B remains IN PROGRESS and
its remaining work is unchanged.

## 2026-09-17 - Phase 3B Paused for HW-M1 Integration

Phase 3B is intentionally paused after qualified concurrent API and
household-isolation checkpoint `0d6a2fc`. The completed P0 software-gap audit
approved transition to HW-M1: no unresolved host/backend/PWA blocker was found;
F14 remains an open software gap but does not block HW-M1. The stable qualified
host/PWA baseline is retained on `feature/full-pwa-e2e`, with documented
baseline `c43c829`; HW-M1 will use the intended `feature/hw-m1` branch.

Target ESP32 adapters and HIL evidence are next. The remaining Phase 3 work is
preserved for later reconciliation and resumption: notification-provider
storm/failure qualification, restart/recovery qualification, DB/resource fault
injection, EXTENDED/endurance / long-soak validation, and final Phase 3
reconciliation and qualification. Resumption must first inspect HW-M1 history
and changes, compare the integrated code with `0d6a2fc`, and rerun applicable
release and Phase 3 gates before any new Phase 3 implementation.

## 2026-09-17 - HW-M1 Working Branch Initialized

The isolated `feature/hw-m1` branch was created from documented branch point
`9b391fa`; stable host/PWA reference `feature/full-pwa-e2e` remains preserved.
HW-M1 scope is frozen as one ESP32 DevKit hub, one ESP32-C3 node, and one PIR.
The checkpoint breakdown, acceptance evidence, regression policy, and exit
strategy are recorded in `docs/hw/HW_M1_IMPLEMENTATION_PLAN.md`.

No target firmware implementation has started yet. Phase 3 historical anchors
remain unchanged, and later Phase 3 work is preserved for reconciliation after
the single-node hardware slice.

## 2026-09-18 - HW-M1.0 and HW-M1.1 Physical Qualification

The first physical HW-M1 slice was brought up on ESP-IDF v6.0.3 with one ESP32
DevKit / ESP-WROOM-32 Hub and one ESP32-C3 node, both with 4 MB flash. The
qualified board identities, Hub CP2102 interface, MAC addresses, node GPIO
mapping and power baseline were recorded in the HW-M1.2 evidence snapshot.

The SmartElex AM312 PIR was connected to C3 GPIO4 and the onboard active-low
LED was used for indication on GPIO8. PIR sensing was physically demonstrated,
including an observed approximately 12 ft / 3.7 m detection distance in the
recorded test setup and battery-powered node operation. These results closed
the bring-up and standalone sensing checkpoints because target electrical and
sensor behavior had to be observed before qualifying the radio path.

Evidence: `docs/hw/evidence/HW_M1_2/README.md`.

## 2026-09-18 - HW-M1.2 ESP-NOW Path and RF Baseline Qualified

Commit `3f02822` recorded the physically qualified path:

`AM312 PIR -> ESP32-C3 -> ESP-NOW -> ESP32 Hub`

The Hub received real PIR-generated motion events and the recorded C3 send
callback reported successful delivery. The qualification baseline moved from
initial channel 6 operation to channel 1 on both devices. This was tested
because local Wi-Fi-channel congestion was suspected, but channel 1 produced
no meaningful room-to-room range improvement. Therefore congestion was not
established as the dominant range limitation and RF optimization remains open.

The C3 was unstable at the higher/default configured TX power. Reducing the
configured maximum to `esp_wifi_set_max_tx_power(40)` (10 dBm) produced much
more stable behavior, so 10 dBm became the current qualified baseline. Any
future increase requires controlled RF requalification. Hub RSSI and channel
metadata logging was added to make later range work measurable, and cleaned
single-line logging removed the earlier serial-garbage symptoms.

This checkpoint qualified the physical link and logging behavior only. It did
not qualify the portable runtime codec, durable business ACK semantics,
backend/Wi-Fi delivery, PWA delivery or production RF optimization.

## 2026-09-18 - HW-M1 Dual-Slot ESP-NOW Node FOTA Qualified

Commit `50abdce` qualified the C3 control-plane FOTA path through the ESP32
Hub. Both devices used 4 MB flash with custom dual-OTA partitions: `ota_0`
and `ota_1` were each 1920 KB and rollback was enabled.

The qualification started with a USB bootstrap into `ota_0`. FOTA #1 rotated
`ota_0 -> ota_1`; the node rebooted into pending validation, was marked VALID,
restored PIR operation and generated post-update motion received by the Hub.
FOTA #2 rotated `ota_1 -> ota_0` and demonstrated the same validation, PIR
restoration and post-update event behavior. The sequence therefore qualified
dual-slot rotation in both directions.

The demonstrated FOTA features were ESP-NOW transfer, application-level ACK,
sequence handling, retry, duplicate handling, per-chunk CRC32, whole-image
CRC32, inactive OTA partition selection, boot-partition switching,
rollback-enabled boot and post-boot validation. FOTA is control-plane traffic;
normal sensor/business events remain data-plane traffic and are not equivalent
to FOTA acknowledgements.

The qualification intentionally leaves production-security and distribution
work open: CRC32 is corruption detection rather than authenticity, ESP-NOW
peer encryption/key management is pending, signed firmware authenticity and
anti-rollback/version policy are pending, backend firmware distribution is
pending, and the C3 image embedded in the qualification Hub was only a
bootstrap arrangement rather than the intended production architecture.

Evidence: `docs/hw/evidence/HW_M1_FOTA/README.md`.

## 2026-09-18 - Transition to Planned HW-M1.3 Runtime Integration

After the HW-M1.2 link and separate FOTA qualification, the next milestone was
defined as **HW-M1.3 — Target Runtime Integration**. It remains
**PLANNED / NOT STARTED**. The purpose is to connect the proven hardware path
to the existing portable `NodeRuntime` and `HubRuntime` architecture without
redesigning ownership boundaries.

The planned work is a common bounded `NodeMessage`/`NodeAckMessage` codec with
magic, version and frame type; C3 AM312 GPIO4 -> sensing -> `NodeRuntime` ->
`next_message()` -> ESP-NOW transport -> `transport_result()` and application
ACK -> `acknowledge()`; and Hub callback -> bounded queue -> owner task ->
decode -> `radio_message_callback()` -> `run_state_once()` -> application ACK
back to the node. Host codec and regression tests must pass before target
validation. FOTA remains separate control-plane traffic.

HW-M1.3 cannot become HW VALIDATED or QUALIFIED from source inspection or the
existing standalone evidence. Its physical exit criteria require real typed
messages, bounded callback ownership, HubRuntime processing, application ACK,
correct retained-event retirement, post-integration FOTA/PIR behavior and
captured hardware evidence.

## 2026-09-19 - HW-M1.3 Target Runtime Integration Implemented and Host Validated

Status: **IMPLEMENTED / HOST VALIDATED / HARDWARE VALIDATION PENDING**.

A bounded binary codec was introduced because C++ `std::string`,
`std::optional` and object layouts cannot be copied safely or deterministically
onto RF. The codec uses explicit big-endian fixed-width integers, bounded
strings, magic, version, frame type, presence flags and exact payload length.
It preserves every current `NodeMessage` field, including optional power
telemetry and bounded `payload_json`, while keeping the maximum normal frame
below the ESP-NOW v1 payload limit. `NodeAckMessage` uses the same data-plane
envelope. Existing FOTA magic is recognized as control-plane traffic and is
never decoded as a business message.

Target code was isolated under `firmware/node/target/esp32c3/` and
`firmware/hub/target/esp32/` so ESP-IDF headers and callback concerns do not
enter the portable host build or redefine runtime ownership. C3 constants
preserve GPIO4 PIR, active-low GPIO8 LED, channel 1, TX API value 40 (10 dBm)
and both qualified MACs. The C3 owner task alone calls `NodeRuntime`; ESP-NOW
callbacks only copy ACK/control frames or enqueue MAC results. The Hub callback
only bounds/checks/copies bytes and transport metadata; one owner task decodes,
admits through `radio_message_callback()`, processes through
`run_state_once()`, creates `NodeAckMessage`, and transmits it.

The ACK distinction remains explicit: ESP-NOW MAC success only enters
`NodeRuntime::transport_result()` and cannot retire retained evidence. Only a
matching application ACK enters `NodeRuntime::acknowledge()`;
`ReceivedVolatile` does not retire business evidence and Durable may retire
the exact EventKey. Transport RSSI/channel stay diagnostic and do not overwrite
semantic RSSI.

Reboot identity uses a portable fail-closed boot-session policy backed by an
ESP32-C3 NVS counter. The counter is durably incremented before the runtime
starts; failure prevents startup rather than knowingly reusing an EventKey.
The Hub admits a newer monotonically increasing session from the qualified MAC
and rejects stale prior sessions. NVS erase/reset behavior and secure
provisioning remain future operational/security policy.

Created target/portable files include:

- `firmware/common/transport/data_plane_codec.{hpp,cpp}`;
- `firmware/common/transport/session_id.{hpp,cpp}`;
- `firmware/node/target/esp32c3/` configuration, session provider and adapter;
- `firmware/hub/target/esp32/` configuration and adapter; and
- `docs/hw/evidence/HW_M1_3_HOST/README.md`.

Host test result: `make cpp-test` PASS with 124 checks using the system host
compiler/linker. Codec round trips, malformed input, ACK policy, retry identity,
session identity, stale-session rejection and FOTA separation are covered.
The release-gate C++ unit, sanitizers, trace, Python, JavaScript, contracts,
product/feature, simulator/lab, dummy-stream and functional stages passed.
Complete `make release-gate-final` did not pass because the sandbox forbids
localhost socket creation/binding; HTTP/PWA/browser stages could not start.
This is recorded as ENVIRONMENT BLOCKED and must be rerun in a normal terminal.

The repository has no unified ESP-IDF product project/CMake composition, so
target-only adapter code was not target-built, flashed or physically exercised.
The separate control-plane queues still need composition with the existing
qualified FOTA maintenance implementation. HW-M1.3 therefore remains hardware
validation pending and is not QUALIFIED.

## 2026-09-19 - HW-M1.3 Checkpoint and Resume Taxonomy

The repository checkpoint meanings were made explicit for future sessions.
`4645098` is the documentation/resume baseline: it consolidated the HW-M1
context but did not qualify new physical firmware behavior. The latest commit
associated with physically demonstrated hardware remains `50abdce`, which
qualified the dual-slot FOTA baseline and therefore remains the last physically
qualified HW checkpoint.

Commit `1d41864dd3d0004ed4dbfa608bb85baf3e35a91f` on
`feature/hw-m1-runtime-integration` is the current HW-M1.3 implementation and
host-validation checkpoint. It was pushed to
`origin/feature/hw-m1-runtime-integration`. Its exact status is IMPLEMENTED /
HOST VALIDATED / TARGET BUILD PENDING / HARDWARE VALIDATION PENDING. The
focused host command passed 124 C++ checks and `git diff --check` passed; the
complete release gate remained incomplete because localhost HTTP/PWA/browser
stages were blocked by the sandbox socket policy.

The immediate next task is HW-M1.3B — ESP-IDF target composition/build for the
real C3 and Hub images, preserving the qualified 1920 KB dual-OTA layout,
rollback and separate FOTA control plane. HW-M1.3C is the subsequent physical
qualification step. No target build or HW-M1.3 physical validation is claimed
by this checkpoint, and the immutable HW-M1.2/FOTA evidence snapshots remain
unchanged.

## 2026-09-19 - HW-M1.3B ESP-IDF Target Composition and Build Validated

Status: **IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / HARDWARE
VALIDATION PENDING**.

Starting from documentation/resume checkpoint `0546b28`, real ESP-IDF v6.0.3
product projects were added under `firmware/node/target/esp32c3/idf/` and
`firmware/hub/target/esp32/idf/`. They compile the already host-validated
adapters and portable NodeRuntime/HubRuntime dependencies; they do not create
a second target-only business runtime. This isolation keeps ESP-IDF headers
out of the host build and preserves callback -> bounded queue -> sole owner
task ownership.

The target compositions added a wire-compatible form of the qualified FOTA
protocol under `firmware/common/transport/fota_protocol.hpp`, a C3 receiver,
and a Hub sender with the temporary BOOT-button engineering trigger. The sole
ESP-NOW callback on each target classifies and enqueues control frames. FOTA
workers consume only the bounded control queues while normal data-plane work
pauses, so FOTA cannot enter NodeRuntime, HubRuntime, journal, or rules. The Hub
embeds the exact C3 application build artifact for engineering qualification;
this is not backend firmware distribution or production authenticity.

Both projects preserve the 4 MB partition map (`nvs` at `0x9000`, `otadata`
at `0xF000`, `phy_init` at `0x11000`, `ota_0` at `0x20000`, and `ota_1` at
`0x200000`), with each OTA slot `0x1E0000` and rollback enabled. Build results:

- C3 target `esp32c3`: PASS; `gs_hw_m1_node.bin` = `0xC9430` (824,368
  bytes), leaving `0x116BD0` (1,141,712 bytes, 58%).
- Hub target `esp32`: PASS; `gs_hw_m1_hub.bin` = `0x184E10` (1,592,848
  bytes), leaving `0x5B1F0` (373,232 bytes, 19%).
- Host regression: `PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++` PASS,
  124 checks under strict warnings.
- `git diff --check`: PASS before checkpoint commit.

No device was flashed. No target behavior or post-integration FOTA rotation
was physically exercised. The last physically qualified commit therefore
remains `50abdce`; the exact next task is HW-M1.3C physical target
qualification with serial/configuration evidence.

## 2026-09-19 - HW Firmware Regression and Release Gate Added

The HW-M1.3B target-build checkpoint now has a repeatable gate invoked from the
active product directory with `make hw-release-gate`; the fast subset is
`make hw-validation-fast`. The gate reuses the existing 124 C++ checks and
adds C3/Hub ESP-IDF build verification, target metadata and binary checks,
exact 4 MB dual-OTA partition validation, rollback validation, qualified
channel/GPIO/TX invariants, lightweight structural checks, and hard OTA image
size limits. Hub headroom warning threshold defaults to 15% and is configurable
without changing firmware behavior.

The gate is fail-closed for missing ESP-IDF: target stages report
`BLOCKED / ENVIRONMENT_MISSING` rather than being silently skipped. It reports
functional and FOTA HIL as `MANUAL_REQUIRED`, power/performance as
`NOT_BASELINED`, and endurance as `NOT_RUN`. It explicitly prints
`SOFTWARE/TARGET GATE: PASS` separately from `PHYSICAL QUALIFICATION: PENDING`;
it never prints HW QUALIFIED.

Focused gate self-tests cover in-slot images, OTA overflow, warning thresholds,
malformed partitions, wrong invariants, and missing ESP-IDF. The full gate was
run successfully: host regression, C3 target build, Hub target build,
partition layout, rollback, configuration invariants, static structure, and
image size all passed. No board was flashed. The HIL matrix is
`docs/hw/HW_M1_3_HIL_TEST_MATRIX.json` with the readable checklist in
`docs/hw/HW_M1_3_HIL_VALIDATION.md`. Future power/performance measurements are
reserved as NOT_BASELINED in `docs/hw/HW_M1_4_POWER_PERFORMANCE_PLAN.md`.

## 2026-09-19 - HW-M1.3 Negative HIL Physically Exercised

The temporary branch `test/hw-m1-3-negative-hil` physically exercised the
remaining negative-HIL cases using the temporary compile-time harness. The
drop-ACK retry path, same EventKey retry identity, wrong EventKey ACK, durable
versus `ReceivedVolatile` retirement, duplicate current behavior, NVS session
lifecycle, stale-session rejection, and separate semantic/transport RSSI
diagnostics all passed. Exact artifacts, hashes, board identities, and
observations are recorded in `docs/hw/evidence/HW_M1_3_HIL/README.md`.

The tested binaries were built before the harness commit and therefore report
`efbeaf9-dirty`; their recorded SHA-256 values are authoritative. Native USB
monitor reconnects caused expected `USB_UART_CHIP_RESET` resets and new NVS
sessions; this was not a firmware crash. The harness is temporary and must not
be merged into the production runtime branch.

HW-M1.3 now has implementation, host, target-build, automated-gate,
positive-HIL, FOTA-HIL, and negative-HIL PASS evidence. Final clean-production
restore/smoke verification remains pending, so final QUALIFIED status remains
pending. HW-M1.4 power/performance remains separate.

## 2026-09-19 - HW-M1.3 Clean-Production Restore Checkpoint

The evidence-only negative-HIL qualification record was preserved on the
production-development branch as `5aad7e6`,
`Document HW-M1.3 negative HIL qualification`. The temporary HIL harness
remains isolated on `test/hw-m1-3-negative-hil`; it is not present in the
current production source.

The repeatable `make hw-release-gate` result is **PASS** for host regression,
partition layout, rollback configuration, HW invariants, target structure, C3
and Hub builds, and image size. The clean production artifacts prepared for
the next hardware session are:

- C3 `gs_hw_m1_node.bin`: 824,368 bytes,
  SHA-256 `20fbb95e118e8d5f3b0b2f350ee1ae066333a690fe3c1e7c304109c00cf91ec9`.
- Hub embedded `node_firmware.bin`: 824,368 bytes, with the exact same
  SHA-256 as the standalone C3 image.
- Hub `gs_hw_m1_hub.bin`: 1,592,848 bytes,
  SHA-256 `35cee47bb906e1c559c7f66a72e83d3b0682be2caf21302c44283f6e6a1c8f57`.

All three production artifacts report embedded version `5aad7e6` where
applicable. The production source contains no `GS_HW_M1_3_NEGATIVE_HIL` compile
hook, and binary scans found no negative-HIL runtime strings. Hardware was
disconnected after this provenance verification. No clean-production restore
flash or final normal PIR smoke test has yet been performed.

The exact resume sequence is recorded in `docs/progress/CURRENT_BASELINE.md`:
reconnect the Hub and C3, attach USB devices if needed, detect actual serial
ports, flash the verified artifacts without erasing, avoid Hub BOOT, open the
correct monitors, verify version `5aad7e6` with no HIL logs, perform one
controlled PIR event, verify the normal NodeRuntime/NodeMessage/Hub processing/
Durable ACK/retirement/MAC path, and record Hub RSSI/channel. A
`USB_UART_CHIP_RESET` and NVS session increment from opening the C3 native USB
monitor is expected and is not by itself a smoke failure.

Status remains: implementation PASS; host validation PASS; target build
validation PASS; automated gate PASS; positive HIL PASS; FOTA HIL PASS;
negative HIL PASS; clean-production artifact preparation/provenance PASS;
clean-production hardware restore PENDING; final normal PIR smoke PENDING; and
final HW-M1.3 QUALIFIED status PENDING. HW-M1.4 power/performance remains
separate.

## 2026-09-19 - HW-M1.3 Final Clean-Production Qualification

The exact clean-production artifacts were rebuilt at documentation/provenance
version `1dfa9c3` and physically qualified after the earlier checkpoint. The
standalone C3 and Hub-embedded C3 images are each 824,368 bytes with SHA-256
`f2c81ad8794fe766664ce253f588124665bb7c3e91da3b2b2ab4dc3b5c9104b2`; the Hub
image is 1,592,848 bytes with SHA-256
`f48a455658cf59d4f3e6a857bac36360ca045da2fd890d9b23ce7438e779a7f1`.
The embedded C3 image exactly matched the standalone image. Production source
contains no temporary negative-HIL implementation, and binary scans found no
negative-HIL runtime strings.

WSL plus USB-IP Hub flashing was unstable for sustained writes on this
workstation (`urb->status -104` and serial drops). Native Windows serial access
recovered the activity: Python 3.12.10, esptool 5.4.0, Hub COM3 and C3 COM4
for this session. Both native flashes passed hash verification and hard reset;
no erase-flash was used. The port names are historical and must be re-detected.

The Hub clean boot physically reported version `1dfa9c3`, initialized ESP-NOW,
started the `HubRuntime` owner on channel 1, and reported the embedded C3 image
size of 824368 bytes. A clean C3 startup banner was not retained because
native USB Serial/JTAG monitor/reset can reset or re-enumerate; its image
provenance and esptool hash verification were captured instead. No
negative-HIL logs were observed.

The decisive matched normal event was C3 `session=17 seq=3`: PIR reached
NodeRuntime, a 63-byte NodeMessage was sent, the Hub processed the matching
event and returned `ack_send=ESP_OK` at RSSI `-69` on channel `1`, and the C3
received Durable ACK class `0`, retired exactly once (`retired=1`), with MAC
delivery `accepted=1`. Final evidence is
`docs/hw/evidence/HW_M1_3_FINAL_SMOKE/README.md`.

Qualification decision: **HW-M1.3 TARGET RUNTIME INTEGRATION: QUALIFIED / PASS**.
HW-M1.0, HW-M1.1, HW-M1.2, and dual-slot C3 FOTA remain QUALIFIED / PASS.
The temporary negative-HIL branch remains isolated and the PWA branch remains
frozen at `9b391fa` on `feature/full-pwa-e2e`. Next engineering work is
HW-M1.4 power/performance characterization; its measurements remain
`NOT_BASELINED`.

## 2026-09-21 - HW-M1.4A Offline Resilience / Physical Endurance Closure

HW-M1.4A physical endurance/resilience qualification is **QUALIFIED / PASS**
for the exact `bb34f5eb796d4975c7e8ab788ca638d9828a3996` Hub+C3 pair
(`Enforce Hub and C3 firmware pair integrity`). Its runtime implementation is
`cfcee972dab6045bbb8f7fbfeb51bf66097cfae9` (`Fix node operation during Hub
outages`); no runtime logic changed between those commits.

Under the documented HIL workload, the node was confirmed alive for at least
19 h 54 min. The final health sample retained session 26, reset 1,
`pir_ok=1545`, `pir_rejected=0`, `durable_ack=1545`, zero retained/in-flight
backlog, zero motion drops, five matched MAC-failure retries, `error=0`, and
stable heap evidence. The final successful motion was at
`2026-09-21T20:00:43+05:30`; the final health sample was at
`2026-09-21T20:01:20+05:30`.

Approximately 15 minutes after operation stopped, the cell measured about
2.80 V while the C3 3V3 and AM312 VCC were approximately 0 V. The exact
cutoff component/path is intentionally unresolved and is carried to HW-M1.4B;
this is not recorded as a battery-protection cutoff claim. Earlier 12-hour,
14.5-hour, and 18-hour checkpoints remain historically valid. The dedicated record is
`docs/hw/evidence/HW_M1_4A_ENDURANCE/README.md`.

The run is not a commercial battery-life qualification or controlled
power-consumption baseline. Next milestone: **HW-M1.4B — Power Baseline
Characterization**. The planned HW-M1.4C low-power architecture and HW-M1.4D
battery telemetry/energy model roadmap is recorded in
`docs/hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md`.

The node used one 18650 cell through the Robocraze `TIFC00389` shield; the
authoritative product and wiring-boundary detail is recorded in the dedicated
HW-M1.4A evidence README. The seller-advertised over-discharge protection is
consistent with the observed endpoint but the actual cutoff mechanism and
threshold remain unverified.

## 2026-09-21 - HW-M1.4B Minimal Power Baseline Planned

HW-M1.4B is **PLANNED / READY TO START**. The authoritative plan is
`docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md`. It establishes a minimal repeatable
BEFORE baseline for the current `bb34f5e` software using the Robocraze
`TIFC00389` fixture only as prototype test hardware: B0 measurement-path
verification, B1 idle, B2 NodeHealth-inclusive normal activity, B3 controlled
PIR workload, and B4 short Hub-offline/recovery behavior.

No HW-M1.4B physical measurement has been performed or claimed by this
planning checkpoint. After B0 measurement-path verification plus minimal B1–B4
capture, HW-M1.4C1 Low-Power Software V1 may start immediately; full
prototype-shield characterization is not a software start gate. HW-M1.4C2 remains deep-sleep/retained-state work and
HW-M1.4D remains future battery telemetry and energy-model work.

Detailed prototype hardware characterization is separate HW-PWR-PROT work.
Future commercial battery/power-path selection and qualification is
HW-PWR-COMM; the Robocraze fixture is not a frozen product architecture.

## 2026-09-21 - HW-M1.4 Master Forward Roadmap Planning Pass

The forward roadmap was expanded so a future session can resume from
repository documentation alone. The authoritative current-state entry is
`docs/progress/CURRENT_BASELINE.md`; the authoritative forward roadmap is
`docs/hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md`; and the active milestone detail
is `docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md`.

The roadmap preserves HW-M1.4A **QUALIFIED / PASS**, sets the immediate action
to B0 measurement-path verification followed by repeatable B1–B4 BEFORE
measurements, and permits HW-M1.4C1 Low-Power Software V1 after that minimal
baseline. It explicitly keeps Robocraze prototype characterization separate
as HW-PWR-PROT and defers commercial hardware selection/qualification to
HW-PWR-COMM.

It also records planned activity-episode semantics, P0-SW-R0 event chronology
dependencies for routine learning, C2 retained-state/recovery work, D battery
telemetry, E installer observability, F RF/Wi-Fi/backend coexistence, G
FOTA/maintenance/security closure, the BLE feasibility experiment, H extended
reliability/soak, and explicit acceptance/evidence boundaries for each.
