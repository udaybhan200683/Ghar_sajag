# Phase 3B Reports scalability - IN PROGRESS

- Replaced repeated full report-history `CloudEvent`/JSON materialization with
  report-specific SQL aggregation and bounded detail reads.
- Preserved household-local Today/Week/calendar-Month semantics, reportable
  event filtering, room/highlight bounds, removed-device history, and the
  existing API schema through optimized-versus-reference payload tests.
- Added diagnostic-only Today/Week/Month stress timings.
- MEDIUM report cycles improved from 675.680 ms to 106.244 ms; explicit LARGE
  report cycles improved from approximately 27.3 s to 5.320 s with correctness
  PASS and zero request failures.
- Host validation passes; manual/browser qualification remains pending.
- `fee5854` remains the previous qualified Phase 3B checkpoint, and Phase 3A
  remains qualified at `4dcaf99`.

# Phase 3B durable-history read optimization - qualified at `fee5854`

- Added migration-managed event indexes confirmed by representative SQLite
  query plans for bounded timeline, event-kind, latest-received and count reads.
- Replaced per-poll recursive incident-history conversion with the bounded
  active incident categories required by caregiver Home while keeping the
  public snapshot contract and historical/report semantics intact.
- Added stderr stress stages/milestones and diagnostic-only per-stage JSON
  timings without making wall time a gate or corrupting stdout JSON.
- Added focused query-plan, ordering, projection-scale and CLI stream tests.
- An explicit post-change LARGE host run passed all correctness checks; this
  focused checkpoint was subsequently qualified at `fee5854`.
- Phase 3A remains qualified at `4dcaf99`.

# Phase 3A PWA performance and stress foundation — COMPLETE / QUALIFIED

- Added deterministic static/payload/resource measurement and structural byte
  budgets without introducing a bundler or wall-clock release limits.
- Removed the 28,770-byte engineering validation catalog from initial Home;
  it now loads only when validation is requested.
- Removed the full application-state fetch from Settings navigation; Settings
  domains continue to hydrate from their authoritative bounded APIs.
- Added polling overlap guards, bounded active Reports refresh, visibility-aware
  state polling with immediate foreground refresh, and change-aware active-tab
  DOM rendering.
- Added indexed/range/limit-aware SQLite event reads for snapshot, timeline and
  Reports instead of materializing all durable history for routine projections.
- Completed the static-only service-worker allowlist for imported PWA modules;
  dynamic caregiver APIs remain excluded.
- Added configurable deterministic SMALL/MEDIUM/LARGE/EXTENDED stress profiles,
  machine-readable counts/storage/resource diagnostics, `make stress-test` and
  `make endurance-test`.
- Added Python/JavaScript/Playwright Phase 3A coverage for budgets, stress smoke,
  repeated navigation, lazy loading, request-overlap protection, bounded
  cache/DOM behavior and temporary API-failure recovery.
- Corrected Reports refresh scheduling so the active Reports refresh owns its
  self-scheduling timer instead of depending on Home-poll timer alignment.
- Corrected PWA state sequencing so stale Home poll responses cannot overwrite a
  newer explicit action result.
- Added simulator reset-epoch handling so a valid post-reset state is accepted
  even when `simulation_now` moves backward.
- Final qualification: mandatory Chromium desktop/mobile browser validation PASS
  and authoritative `make release-gate-final` PASS.
- Final Python regression discovery: `96/96` PASS; JavaScript test files: `3/3`
  PASS; SMALL and MEDIUM deterministic stress profiles: PASS.

# Phase 2D reconciliation checkpoint — final qualification preparation

- Reconciled Phase 2 behavior against the master PWA specification without
  starting Phase 3 or reworking completed Phase 2A-C functionality.
- Added a compact `GET /pwa/state?scope=home` projection for routine Home
  polling while preserving the existing full `/pwa/state` contract for
  validation and on-demand Devices/Settings hydration.
- Stopped eager Reports loading at initial app startup; Reports now fetch from
  the backend when the Reports tab/period is opened.
- Reduced browser-notification polling by caching preferences, bounding
  delivered-record tracking, and keeping notification history/detail fetches on
  the Settings > Notifications path where practical.
- Added `tests/python/test_phase2d_reconciliation.py` so the payload contract is
  automatically discovered by `make python-test` and therefore by
  `make release-gate-final`.
- Targeted validation passed for Phase 2A/B/C regressions, the new Phase 2D
  contract, affected Phase 1 application/foundation tests, Playwright-runner
  discovery tests, and JavaScript unit tests.

# Phase 1 Validation Hardening — final qualification PASS

- Added the machine-readable Phase 1 UI contract at `tests/validation/phase1_ui_contract.json`, covering required caregiver-visible content and forbidden unrelated UI assertions.
- Hardened browser validation for cross-feature contamination, state-matrix coverage, event classification, persistence/test isolation and backend/UI consistency.
- Expanded Settings validation across save, rejection, cancel and reload behavior.
- Covered coverage-loss and I am OK acknowledgement flows, plus consumer-facing Device Health and battery presentation.
- Hardened release-gate process and port lifecycle ownership: `browser-e2e` uses `8765`, Playwright uses `8766`, and `make release-gate-final` requires mandatory desktop/mobile browser validation.
- Validation hardening found and corrected real Phase 1 defects; the final documented baseline is qualified by `make release-gate-final` PASS.

# Phase 1 implementation checkpoint — complete

- Added one versioned SQLite application store for Home Details, family members, registered devices, device health/history and battery/routine policy without resetting existing household data.
- Added server-validated owner-only Home/family/device/policy APIs; simulator registration, edit and unregister use the same registry as Devices and Manage Devices, preserving historical rows.
- Made the PWA Devices view/counts, Device Details, Home Details, Family Members, Battery Alerts and Manage Devices backend-driven; saved policy changes feed existing host rules and battery evaluation.
- Added focused migration, domain, WSGI API and desktop/mobile Playwright tests; final release qualification is `make release-gate-final` PASS.
- Kept physical provisioning and network setup as adapter/HW_REQUIRED boundaries. The physical source directory remains `v3_4_2`, with effective prior browser baseline v3.4.3.

# Parivar Sathi v3.4.3 — checked-in effective browser baseline

- Integrated the legacy engineering-lab browser assertion alignment (`/No (?:open )?incidents/i`).
- `make release-gate-final` is the browser-qualified release command and runs Playwright preflight plus desktop/mobile PWA validation.
- The physical source directory deliberately retains the historical `v3_4_2` name.

# Parivar Sathi v3.4.0 — battery analytics and remaining-life prediction

- Added backend `BatteryAnalyticsService` with non-linear Li-ion voltage→SOC estimation, calibrated energy accounting, usage-history smoothing, confidence levels and remaining-days prediction.
- Added cumulative node power telemetry contract fields for sleep/awake/sensor/RF time, wakeups, retries, packets, boots and brown-outs.
- Added per-device power calibration profiles; capacity/current calibration is configuration and is not a family hardcoded constant.
- Added high-drain detection using recent-vs-baseline consumption and usage-pattern diagnostics.
- Added configurable household low-battery alert threshold under Settings → Device Schedules.
- Updated Home Device Health and Devices views with battery %, mV, estimated time left, mAh/day, confidence, drain state, wakes/day and RF retries/day.
- Battery/health warnings remain isolated from the household care banner.
- Expanded the canonical functional catalog to **92 scenarios** and regenerated the 92-case manual plan.
- Current focused host verification: 94 C++ checks, 31 Python tests, 11 JavaScript tests, 8 PWA bridge tests, 92/92 functional scenarios, 16/16 HTTP integration tests and 5/5 dummy sensor streams.
- Physical current draw, ADC accuracy and usable-capacity calibration on the final hardware remain a hardware acceptance step; software never assumes the ESP32 can measure its own full supply current.

# 1.5.4 — release-gate validation framework

- Added a canonical **68-scenario declarative functional suite** spanning expected activity, morning routine, door concerns, daytime inactivity, transport/replay, caregiver workflow, settings/invalid input, and simulated node/hub diagnostics.
- Added five replayable **dummy sensor stream** fixtures and a dedicated runner.
- Added a generated **68-case manual functional validation plan** from the same catalog.
- Added `make validation-fast`, `make release-gate`, `make release-gate-browser`, `make functional-test`, `make dummy-sensor-test` and `make manual-test-plan`.
- Added validation traceability for all P0 IDs F01–F14 and E01–E10; physical-only criteria are explicitly marked pending.
- Routed quiet-hour and door-left-open connected simulation through the C++ pure rule engine rather than duplicate Python timing logic.
- Added connected daytime-inactivity event/incident/routing behavior and tests.
- Added simulated-device capability checks so impossible sensor/event combinations are rejected.
- Added actual rule detection timestamps so warning/close chronology remains deterministic.
- Expanded regression evidence to 80 C++ checks, 24 Python tests, 10 JavaScript tests, 68 connected functional scenarios, 5 dummy sensor streams and 16 HTTP integration tests.
- Superseded by the final gate above: Playwright browser automation is mandatory for pilot/release qualification through `make release-gate-final`; the manual browser checklist remains supplementary.

# 1.5.3 — configurable household policy settings

- Promoted quiet hours, door-left-open timeout, daytime monitoring window and inactivity threshold from fallback defaults to **versioned per-household settings**.
- Added a Settings panel to the simulation web app with validation and a clear config-version indicator.
- Added `GET/POST /v1/homes/{homeId}/config` and OpenAPI coverage for desired household configuration.
- Wired Settings → backend desired config → simulator hub activity-rule configuration; changing the door timeout changes simulator behavior.
- Added `activity_rules` as a required section of the household configuration contract and stored backend-generated `home_id`/`version` canonically.
- Kept Privacy out of ordinary user-selectable modes; consent withdrawal may still force privacy internally.
- Kept transport reliability parameters (ACK/retry/heartbeat/offline threshold) engineering-controlled rather than exposing them to family Settings.
- Retained the v1.5.2 hardware-independent rule engine, typed node↔hub protocol and relational P0 database schema.

# 1.5.1 — P0 simulation closure and caregiver clarity

- Added exact caregiver activity presentation: green **I am OK** with age, explicit motion/door labels and newest-first household history.
- Preserved unresolved **Call Family** and **Missing morning activity** incidents while showing later reassuring activity chronologically.
- Removed the user-facing privacy ON/OFF simulation control; privacy/consent enforcement remains an internal product requirement.
- Added normal vs quiet-hours door classification, five-minute door-left-open warning, close duration and warning-clear evidence.
- Added hub/node status with location, diagnostic fault codes, troubleshooting and bounded reboot behavior.
- Expanded connected host suite from 13 to 20 scenarios and HTTP checks from 9 to 13.
- The same authorised dashboard can represent a family member or caregiver; no separate professional-caregiver page is required for P0.
- Hardware telemetry, real RF/battery/temperature diagnosis, persistence across restart and real notification providers remain pending.

# 1.5.0 — local simulation integration

Added interactive C++ host adapter, Python lab API, connected dashboard, 13 scenario assertions, 9 HTTP checks and optional browser script. Existing domain algorithms unchanged; product version metadata updated. Documentation v2.0 remains the design baseline with a new simulation LLD/guide.

# 1.4.2 documentation and traceability patch

Added canonical module/requirement responsibility comments and critical API intent. Product version metadata updated. Runtime algorithms unchanged. Documentation edition 2.0 supersedes earlier design/status summaries.

# Release 1.4.1

Documentation/status synchronization and Product::version metadata patch. No core algorithm or interaction API change. Fresh product tests are recorded in PATCH_VERIFICATION.txt.

# Release 1.4.0

- Added Parivar Saathi and Sarthi-AI product selection to the host build.
- Added allocation-free interaction lifecycle with an asynchronous provider port.
- Added per-product regression tests and a two-product verification target.
- Added product-family HLD, interaction LLD, architecture and sequence diagrams.
- Added current progress summary with explicit remaining integration gates.

Migration: extract this release alongside v1.3; preserve local changes before
merging. From this directory in Ubuntu, run `make verify-products`. Do not copy
generated build or log output to the firmware source tree in Git.

This is a new release snapshot based on the available prior reference source.
It does not modify a remote Git repository or replace historical documents.
Product names affect the new C++ profile; public website and old document titles
are not renamed. AI conversation/audio and flashable ESP-IDF projects remain
future integration work.
