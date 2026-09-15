# 1.5.4 status addendum

## Phase 1 targeted implementation checkpoint — manual full gate pending

Home Details and Family Members now load, validate, mutate and reload through `/pwa/foundation/` and one SQLite `FoundationService`. Active OWNER authorizes mutations; last-owner removal, duplicate contact/ID and inactive-member edits are rejected. Devices and Manage Devices share `device_registry`; simulator registration, details, rename/room/enabled edits, confirmed unregistration, counts, online/offline and health history use the same application domain. Unregistration retains historical rows. Battery alert thresholds and routine policy are versioned in `application_policy`, survive restart and affect the existing host evaluation/configuration path. Migration 003 and `schema_migrations` preserve existing household data.

The 46/46 targeted Python suite, 92/92 functional catalog and focused Phase 1 Chromium desktop/mobile flows (12/12) pass. The Phase 0 v3.4.3 `make release-gate-final` result was manually PASS before this work. Inside-sandbox browser execution was ENVIRONMENT_BLOCKED by loopback EPERM; the focused 12-case file passed outside the sandbox. Complete manual WSL full-gate qualification remains pending. **Phase 1 is not yet full-gate validated.** The local lab uses a development actor header; production authentication, cloud deployment, physical pairing/Wi-Fi, battery/RF calibration and flash qualification remain open. Reports/production notifications are Phase 2; stress/endurance and final evidence are Phase 3.

Release-gate wiring: `make release-gate-final` runs `release-gate` first; its `make python-test` discovery includes `test_foundation.py` and `test_phase1_application.py`, while the existing HTTP, canonical functional, PWA bridge/API/frontend, sanitizer and trace stages remain in place. The mandatory Playwright runner executes every `tests/playwright/*.spec.ts` for both Chromium desktop and mobile projects, including `phase1_foundation.spec.ts`. No separate duplicate Phase 1 campaign or Phase 3 stress suite is added.

## Host/software status

The hardware-independent reference now has a formal regression/release framework. The canonical connected functional suite contains **92 scenarios** and is driven by synthetic node, clock, link, fault and caregiver inputs. The same catalog generates the manual validation plan.

Current verified host coverage:

- 4 JSON schemas + protocol/config/OpenAPI contract verification;
- 94 C++ checks;
- 31 Python backend/database/logging/validation-framework/battery-analytics tests;
- 11 JavaScript application tests;
- four feature-flag simulator variants;
- Base and AI product-profile tests;
- 5/5 dummy sensor stream replays;
- 92/92 connected functional scenarios;
- 16/16 HTTP integration tests;
- C++ AddressSanitizer/UBSan pass;
- trace-enabled C++ build/test pass.

The connected simulator now exercises quiet-hours, door-left-open and daytime-inactivity decisions from the C++ pure rule engine. It rejects impossible simulated sensor/event combinations and preserves rule-detection timestamps for deterministic chronology.

## Release process

`make release-gate-final` is the mandatory browser-qualified host/software release command: it runs the release gate, Playwright preflight and the desktop/mobile Chromium suite. `make release-gate` remains the non-browser host regression gate. The generated `tests/MANUAL_FUNCTIONAL_VALIDATION.md` is supplementary exploratory evidence, not a substitute for the final automated browser gate.

Every new feature should add positive, negative and relevant boundary/recovery cases to the canonical catalog or the appropriate unit/integration suite before release.

## Still pending physical integration

A host PASS must not be interpreted as hardware/pilot acceptance. Real-board PIR/reed/button behavior, ESP-NOW RF/RSSI and heartbeat timing, **battery current/ADC/capacity calibration**, charging/UPS, brown-out/reset/watchdog, flash persistence/wear, signed OTA/rollback, real notification-provider delivery and installed-home coverage remain pending. Software battery consumption analytics, usage-pattern learning, high-drain detection and remaining-life prediction are implemented in the host/backend reference.
