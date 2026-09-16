# Ghar Sajag reference code 1.5.4

## Phase 1 + Phase 2 implementation status

The effective PWA/BatteryAnalytics baseline is v3.4.3 in the historical `v3_4_2` directory. Phase 1 now stores Home Details, family membership, registered devices, device health and household battery/routine policy in one versioned SQLite application store (`backend/ghar_sajag/foundation.py`, migration `003_phase1_application.sql`). Devices and Settings → Manage Devices use the same registry and API. Registration is simulator-only; the physical provisioning adapter remains a hardware qualification boundary. Existing C++ care rules, Home presentation and canonical scenarios remain in place.

`make lab` uses `logs/application.sqlite` for durable interactive application settings and registry data. Set `GS_APP_DB` to another SQLite path for an isolated lab, or `GS_APP_DB=:memory:` for disposable host sessions. Automated browser tests force isolated in-memory application databases where intended to keep qualification deterministic. Local PWA APIs under `/pwa/foundation/` accept a development `X-Actor-Id` and enforce active OWNER for mutations; this local identity is not production authentication. Real ESP32 pairing/network provisioning, production identity, deployed database integration and flash durability remain pending.

Phase 2 adds backend-derived Reports, durable canonical CloudEvent history,
persisted notification preferences/records, backend-owned I-am-OK overdue
evaluation and Home/Reports/Notifications classification consistency. Phase 2D
keeps the PWA lightweight by polling a compact Home payload, loading Reports
only when the Reports tab is opened/changed, and loading detailed
Notifications/Settings state on demand.

Phase 3A adds deterministic static/payload budgets, indexed bounded history
reads, change-aware active-tab rendering, guarded/throttled polling, lazy
engineering validation data, and isolated SMALL/MEDIUM/LARGE/EXTENDED stress
profiles. It does not change the product version or the historical directory
name. See `docs/PHASE3A_PERFORMANCE.md` and
`docs/PHASE3_STRESS_FRAMEWORK.md`.

Final qualification command: `make release-gate-final`. This is the
authoritative release qualification command for the validated baseline. It
includes the host validation gate plus mandatory Playwright browser validation
for all mandatory specs across `chromium-desktop` and `chromium-mobile`. The
host `browser-e2e` lab owns port `8765`; Playwright owns port `8766`.

Start with [SIMULATION_START_HERE.md](SIMULATION_START_HERE.md). Version **1.5.4** adds a release-gate validation framework around the existing Base / Parivar Saathi P0 host implementation. It remains hardware-independent reference code, not a flashable ESP-IDF application.

## What v1.5.4 adds

- A **declarative 92-scenario functional regression catalog** covering expected, unexpected, boundary, failure/recovery, configuration, transport and diagnostic paths.
- A **generated 92-case manual validation plan** sourced from the same catalog, so manual and automated tests do not drift.
- Five realistic **dummy sensor stream fixtures** for normal morning, missing-then-later-activity, late-night door, daytime inactivity and offline replay.
- A **fail-closed host release gate** combining contracts, C++ rules/protocol, Python backend/database, JavaScript app, product profiles, feature variants, dummy streams, functional scenarios, HTTP integration, sanitizers and trace build.
- A **P0 validation coverage map** for F01–F14 and E01–E10, with physical-only gates explicitly marked pending rather than falsely passed.
- Sensor-capability validation: invalid combinations such as a Kitchen PIR generating `DOOR_OPEN` are rejected.
- Daytime inactivity is now exercised end-to-end through the **C++ pure rule engine → backend event → incident → caregiver routing** path.
- Rule-generated events carry their actual detection timestamp, preserving intuitive chronology.
- **Battery analytics** estimates non-linear SOC, calibrated mAh/day, remaining days, confidence and abnormal drain from voltage plus cumulative sleep/awake/sensor/RF counters. The low-battery alert threshold is household-configurable; hardware current/ADC/capacity calibration remains a physical acceptance gate.

## Main commands

```bash
make validation-fast        # normal development regression
make release-gate           # full host/software release gate
make release-gate-browser   # release-gate --require-browser for the engineering lab
make release-gate-final     # mandatory Playwright preflight + desktop/mobile PWA gate
make manual-test-plan       # regenerate manual cases from canonical catalog
make performance-profile    # deterministic static/payload measurements
make performance-test       # budgets + SMALL stress smoke
make stress-test            # MEDIUM deterministic workload by default
make endurance-test         # explicit EXTENDED workload; not a normal gate
make lab PRODUCT=base       # interactive browser simulator
```

The canonical functional catalog is `tests/functional/scenario_catalog.json`. The generated manual checklist is `tests/MANUAL_FUNCTIONAL_VALIDATION.md`. Validation architecture is documented in `docs/VALIDATION_FRAMEWORK.md`.

The same authorised dashboard is intended for family or caregiver use; role/authorization controls actions. Household behaviour policy remains configurable per home. Transport ACK/retry/heartbeat/offline parameters remain engineering-controlled.

A host release-gate PASS does **not** certify physical hardware. Real ESP32 GPIO/debounce, ESP-NOW RF/RSSI, battery current/ADC/capacity calibration and UPS behavior, brown-out/reset/watchdog, flash durability, OTA and real notification delivery remain physical acceptance gates.

## Parivar Sathi PWA bridge (integrated verification build)

This package adds the approved Parivar Sathi PWA to the existing v1.5.4 local lab **without changing the deterministic C++ rules core**.

Run:

```bash
make lab
```

Open:

- `http://localhost:8765/` — Parivar Sathi PWA, driven by backend state.
- `http://localhost:8765/lab` — original engineering simulation lab.

The PWA polls `GET /pwa/state?scope=home` for normal Home/current-state updates.
The full `GET /pwa/state` projection remains available for validation and
on-demand Devices/Settings hydration. Verification buttons call
`POST /pwa/action`.
The bridge translates supported controls into the existing v1.5.4 C++/Python simulation path. The PWA battery percentage/runtime is now produced by the software battery-analytics pipeline. In the host lab the voltage, usage counters and current profiles are synthetic; field accuracy still depends on connecting real node telemetry and calibrating the exact hardware.

Useful verification:

```bash
make http-e2e-test
make pwa-bridge-test
```

Production path remains:

`ESP32-C3 nodes -> Hub -> HTTPS/MQTT -> cloud backend -> PWA`

The local bridge validates the backend/PWA contract. It does **not** claim that a public cloud, MQTT subscriber, physical ESP32 radio, or production authentication has been deployed yet.

## Parivar Sathi PWA: all 92 canonical scenarios
Run `make pwa-e2e-test` to validate the complete canonical scenario catalog through backend HTTP and the PWA frontend validator. The temporary left-side validation panel supports manual per-scenario execution and a dynamic Run all action.


## Mandatory Playwright / Chromium final release gate

The final PWA release gate now includes a real Chromium-rendered DOM validation layer.

Install once:

```bash
make playwright-install
```

Run the complete mandatory final gate:

```bash
make release-gate-final
```

This runs the existing v1.5.4 release gate and then launches the local lab, opens the actual PWA in Chromium, and validates the rendered page.
The host `browser-e2e` lab and the mandatory Playwright lab use isolated ports (`8765` and `8766` respectively); the runner propagates its `8766` URL through `PWA_BASE_URL`.
The Phase 1 UI coverage matrix is the machine-readable contract at `tests/validation/phase1_ui_contract.json`.

The browser gate checks:
- PWA can load and the primary tabs are visible.
- Low-battery scenario changes Device Health while the top family-care banner remains positive.
- Calibrated battery prediction fields are backend-driven; sustained high drain is flagged without changing the care banner.
- Device Schedules saves the household-specific low-battery warning threshold.
- Recent Important Events are visibly ordered newest first after scenario transitions.
- The PWA's **Run all automatically** flow completes with a visible **N/N PASS** result for the current canonical catalog.
- A visible FAIL result causes the browser gate to fail.

Two Chromium profiles are exercised:
- desktop Chrome
- Android-sized Pixel 7 viewport

Artifacts on failures:
- `evidence/playwright-results.json`
- `evidence/playwright-report/`
- screenshots/traces/videos retained by Playwright
- `evidence/playwright-lab.log`

For day-to-day development you may still use `make release-gate`. For any pilot/release candidate, use **`make release-gate-final`**; Playwright is mandatory in that target and a missing browser dependency fails the command rather than falling back to manual review.

## v2 browser-gate routing correction

The integrated server serves:
- `/` — Parivar Sathi PWA
- `/lab` — original v1.5.4 engineering simulator

The legacy `browser-e2e` test now explicitly opens `/lab`. The mandatory Playwright PWA gate continues to open `/`.
This prevents the legacy browser test from waiting for engineering-lab DOM IDs on the new PWA page.


## v3 Playwright startup correction

`make release-gate` runs sanitizer and trace stages that can clean/rebuild the C++ output.
On WSL the interactive lab build can take roughly 40–60 seconds. The previous Playwright
runner started `make lab` and simultaneously used a 40-second HTTP readiness timeout,
so the timeout could expire while C++ compilation was still in progress.

The browser runner now:
1. runs `make lab-build` synchronously;
2. starts `python3 tools/sim/local_lab.py` only after the binary is ready;
3. starts the HTTP readiness timer after compilation;
4. detects early server exit and records the real startup output in
   `evidence/playwright-lab.log`.

No product/rule logic changed in this correction.
