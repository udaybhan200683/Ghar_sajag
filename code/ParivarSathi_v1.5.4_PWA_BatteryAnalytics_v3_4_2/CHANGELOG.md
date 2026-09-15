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
- Playwright browser automation remains optional unless `make release-gate-browser` is used; the manual browser checklist is mandatory when browser automation is unavailable.

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
