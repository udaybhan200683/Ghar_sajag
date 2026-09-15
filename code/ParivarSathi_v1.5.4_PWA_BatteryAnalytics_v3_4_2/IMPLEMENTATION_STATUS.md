# 1.5.4 status addendum

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
