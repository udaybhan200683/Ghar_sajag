# Ghar Sajag / Parivar Saathi Engineering History

**Document revision:** HW-M1-R1
**History covered through:** HW-M1 dual-slot C3 FOTA qualification
**Product baseline through:** Parivar Saathi v1.5.4
**PWA / BatteryAnalytics baseline through:** v3.4.3
**Latest qualified Phase 3B checkpoint covered:** `0d6a2fc`
**Previous qualified Phase 3B scale/read-path checkpoint:** `fee5854`
**Permanent Phase 3A implementation/qualification anchor:** `4dcaf99`
**Latest qualified HW branch:** `feature/hw-m1`
**Latest qualified HW commit:** `50abdce`
**Updated:** 2026-09-18

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
