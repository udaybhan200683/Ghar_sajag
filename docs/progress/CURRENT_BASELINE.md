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

Updated: 2026-09-15

## Git

- Branch: `feature/full-pwa-e2e`
- HEAD: `4d021cdd25024774375ccdbc8cef3de57a7ba420`

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
  - backend-derived "Last confirmed" elapsed timing
  - caregiver-facing "Routines & Activity Rules" display label
  - optional DEVICE_MAINTENANCE notifications
  - Home / Reports / Notifications classification consistency
- Targeted socket-free validation:
  - `test_phase2c_integration.py`: PASS
  - Phase 2B Notifications regression tests: PASS
  - Phase 2A Reports regression tests: PASS
  - affected Phase 1 application tests: PASS
- Browser validation:
  - `phase2c_integration.spec.ts`: implemented and discovered for desktop/mobile
  - affected `phase1_ui_contract.spec.ts`: included in focused qualification
  - focused desktop/mobile execution: PENDING

## Authoritative Validation Locations

- Phase 1 UI contract: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/validation/phase1_ui_contract.json`
- Python tests: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/python/test_*.py`
- Playwright specs: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/playwright/*.spec.ts`
- Release gate target: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/Makefile`

## Deferred Boundaries

- MANUAL_ONLY: real browser notification permission prompt.
- HW_REQUIRED: ESP32/RF/Wi-Fi provisioning, physical sensors, physical battery calibration.
- PRODUCTION_INTEGRATION_PENDING: SMS/email/push providers, production authentication/deployment, autonomous production scheduler.
- PHASE3_PENDING: stress, load, endurance, soak, fault injection.

## Next

- NEXT = Phase 2D
