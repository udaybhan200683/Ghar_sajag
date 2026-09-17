# 1.5.4 status addendum

## Phase 3B durable-history read optimization - IN PROGRESS

The first focused Phase 3B task aligns SQLite indexes with the actual bounded
snapshot/timeline query order, replaces recursive all-incident PWA conversion
with a bounded active-kind read model, and adds stderr stage/milestone progress
plus per-stage JSON diagnostics to the deterministic stress runner.

Focused, Python, JavaScript, performance/SMALL, MEDIUM and an explicit LARGE
host diagnostic pass. Desktop/mobile browser validation, manual acceptance and
the remaining Phase 3B load scope are not yet qualified. See
`docs/PHASE3B_SCALE_OPTIMIZATION.md`.

Phase 3A remains COMPLETE / QUALIFIED at permanent implementation anchor
`4dcaf99`; this in-progress work does not replace that anchor.

## Phase 3A performance / lightweight UX / stress foundation — COMPLETE / QUALIFIED

Document revision: `P3A-R1`.

Implemented deterministic profiling/budgets, indexed bounded event-history
reads, lazy validation/Settings hydration, guarded visibility-aware polling,
change-aware active-tab rendering, a bounded static-only service-worker cache,
and isolated stress profiles. SMALL and MEDIUM host runs pass. The product
version remains 1.5.4.

Phase 3A implementation/qualification anchor:
`4dcaf99` (`Complete Phase 3A performance and stress foundation`).

Phase 2D anchor `9499381` remains the historical Phase 2 qualified baseline.

Final Phase 3A qualification passed in WSL:
- mandatory Chromium desktop browser suite: PASS;
- mandatory Chromium mobile browser suite: PASS;
- authoritative `make release-gate-final`: PASS;
- final Python regression discovery: `96/96` PASS;
- JavaScript test files: `3/3` PASS;
- performance profile: PASS;
- SMALL and MEDIUM deterministic stress profiles: PASS.

Browser qualification also found and corrected Reports refresh scheduling,
stale Home-poll/action sequencing, and simulator reset-epoch handling. These
fixes preserve the Phase 3A lightweight runtime strategy while making reset and
explicit-action boundaries deterministic.

LARGE/EXTENDED, long soak, controlled concurrent API load, comprehensive
failure injection and physical hardware resource qualification remain Phase
3B/3C or HW_REQUIRED.

## Phase 2D reconciliation checkpoint — COMPLETE / QUALIFIED

Phase 2A Reports, Phase 2B Notifications and Phase 2C PWA integration are
implemented and committed. Phase 2D performed a narrow reconciliation against
the master PWA specification and found no unresolved software-testable Phase 2
feature gap requiring new product behavior. Deferred boundaries remain real
browser permission-prompt interaction, physical ESP32/RF/Wi-Fi/sensor/battery
qualification, production auth/deployment and production SMS/email/push
providers, plus Phase 3 stress/load/endurance/fault-injection work.

The PWA now uses a compact `GET /pwa/state?scope=home` payload for normal Home
polling. Full `/pwa/state` is preserved for validation and on-demand
Devices/Settings hydration. Reports no longer fetch during initial Home load;
they load from `GET /v1/homes/{home_id}/reports?period=...` only when Reports is
opened or the period changes. Notification history remains backend-limited and
is loaded through Settings > Notifications; browser-delivery polling caches
preferences and is throttled.

Validation discovery remains unchanged: `make python-test` discovers
`tests/python/test_*.py`, including `test_phase2a_reports.py`,
`test_phase2b_notifications.py`, `test_phase2c_integration.py` and
`test_phase2d_reconciliation.py`; Playwright discovers every
`tests/playwright/*.spec.ts` for both `chromium-desktop` and
`chromium-mobile`. Do not run `make release-gate-final` inside restricted
Codex; run it manually in the normal local terminal for final qualification.

## Phase 1 targeted implementation checkpoint — subsequently qualified

Home Details and Family Members now load, validate, mutate and reload through `/pwa/foundation/` and one SQLite `FoundationService`. Active OWNER authorizes mutations; last-owner removal, duplicate contact/ID and inactive-member edits are rejected. Devices and Manage Devices share `device_registry`; simulator registration, details, rename/room/enabled edits, confirmed unregistration, counts, online/offline and health history use the same application domain. Unregistration retains historical rows. Battery alert thresholds and routine policy are versioned in `application_policy`, survive restart and affect the existing host evaluation/configuration path. Migration 003 and `schema_migrations` preserve existing household data.

At this historical checkpoint, the 46/46 targeted Python suite, 92/92
functional catalog and focused Phase 1 Chromium desktop/mobile flows (12/12)
passed, while the restricted Codex sandbox could not execute the complete
socket-bound gate. Phase 1 was subsequently fully qualified by the mandatory
desktop/mobile `make release-gate-final` process and remains COMPLETE /
QUALIFIED. The local lab still uses a development actor header; production
authentication, cloud deployment, physical pairing/Wi-Fi, battery/RF
calibration and flash qualification remain open.

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
