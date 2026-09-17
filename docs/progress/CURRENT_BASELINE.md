# Ghar Sajag / Parivar Saathi - Current Baseline

**Document revision:** P3B-R3
**Product baseline:** Parivar Saathi v1.5.4
**PWA / BatteryAnalytics baseline:** v3.4.3
**Engineering baseline:** Phase 3A - COMPLETE / QUALIFIED
**Active engineering work:** Phase 3B - IN PROGRESS
**Qualified Phase 3A implementation anchor:** `4dcaf99`
**Qualified Phase 2D implementation anchor:** `9499381`
**Updated:** 2026-09-17

This document describes the current validated implementation baseline.

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

The P0 software-gap audit is complete: software is ready to start HW-M1. No
host/backend/PWA defect blocks the first physical vertical slice. F14 remains
an open software gap but does not block HW-M1; it remains a pilot/commercial
P0 blocker. Full audit: `docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md`.

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

## Next

1. Start Phase 3B load/scale qualification from the P3A-R1 qualified baseline
   anchored at `4dcaf99`.
2. Preserve the Phase 3A performance budgets and browser sequencing regressions
   as mandatory regression coverage during later stress/fault work.
3. Keep `4dcaf99` as the permanent Phase 3A implementation/qualification anchor;
   later documentation-only commits do not replace it.

NEXT = Phase 3B event/device/history/report/notification/API load qualification,
followed by Phase 3C fault/recovery/resource/endurance work.
