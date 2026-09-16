# Ghar Sajag Validation Framework — v1.5.4

## Goal

Prevent a new release from silently breaking already implemented P0 behaviour. The framework separates **host/software regression** from **physical hardware acceptance** and uses synthetic sensor data until the ESP32 hardware is available.

## Validation layers

1. **Contract checks** — JSON schemas, node↔hub golden payloads, OpenAPI and configuration contracts.
2. **C++ unit tests** — pure rules, protocol/ACK/retry/dedup, hub/node adapters, security/update policy and feature flags.
3. **Python backend/database tests** — tenant scope, incidents, routing, idempotency, SQL schema, logging.
4. **JavaScript tests** — dashboard semantics, exact event presentation, configuration validation and app state handling.
5. **Dummy sensor streams** — realistic multi-event sequences replayed through the connected host lab.
6. **Declarative functional catalog** — 92 positive, negative, boundary, fault and recovery scenarios. This is the canonical functional-regression catalog.
7. **HTTP integration tests** — real local WSGI boundary, access checks, invalid requests, config changes and end-to-end event flow.
8. **Feature/product matrix** — feature-flag variants plus Base and AI product profiles.
9. **Sanitizers/trace build** — AddressSanitizer/UBSan and development tracing.
10. **Browser/PWA validation** — mandatory Playwright desktop/mobile validation in `make release-gate-final`, plus a generated manual checklist using the same functional catalog.
11. **Phase 1 UI contract** — `tests/validation/phase1_ui_contract.json` is the authoritative machine-readable Phase 1 UI contract and coverage matrix.
12. **Phase 2 deterministic suites** — `tests/python/test_phase2a_reports.py`, `test_phase2b_notifications.py`, `test_phase2c_integration.py` and `test_phase2d_reconciliation.py` cover Reports, Notifications, cross-feature integration and the compact Home payload contract. Matching browser specs under `tests/playwright/*.spec.ts` are discovered for both mandatory Chromium projects.

## Single source of truth

`tests/functional/scenario_catalog.json` is the canonical host functional scenario list. `tools/validation/generate_manual_plan.py` generates `tests/MANUAL_FUNCTIONAL_VALIDATION.md` from that catalog, so manual and automated cases stay aligned.

`tests/validation/phase1_ui_contract.json` is the authoritative machine-readable Phase 1 UI contract/coverage matrix. Important caregiver-visible behavior should verify required content/state, forbidden unrelated content, backend/UI consistency, unaffected components where relevant, and desktop/mobile rendering.

New product behaviour is not release-complete until its positive path, negative/failure path and relevant boundary/recovery path are added to this catalog (or to the appropriate lower-level suite) and `tests/validation_coverage.json` is updated if the requirement mapping changes.

Phase 2 browser validation is discovered by filename rather than a separate
qualification command: the Playwright runner executes every
`tests/playwright/*.spec.ts` for `chromium-desktop` and `chromium-mobile`.
Python Phase 2 reconciliation tests use the normal `tests/python/test_*.py`
discovery path.

## Commands

```bash
make validation-fast        # normal development regression
make release-gate           # full host/software release gate
make release-gate-browser   # full gate; browser automation is required
make release-gate-final     # authoritative final gate; host + mandatory Playwright desktop/mobile
make manual-test-plan       # regenerate manual checklist from canonical catalog
```

## Release interpretation

`make release-gate-final` is the authoritative final qualification command. It includes the mandatory host/software stages and Playwright validation for `chromium-desktop` and `chromium-mobile`. The host `browser-e2e` lab owns port `8765`; the Playwright lab owns port `8766`; automated browser tests use isolated in-memory application databases where intended.

A host PASS does not replace real-board testing. Physical PIR/reed/button debounce, RF/RSSI, battery/UPS, brown-out, reset reasons, flash durability, OTA and real notification-provider tests remain separate hardware/pilot gates.

## PWA end-to-end 92-scenario validation

The Home page contains a temporary engineering validation panel. **Run all 92 automatically** executes every canonical case from `tests/functional/scenario_catalog.json` through the connected C++/hub and Python backend path. The backend returns the raw snapshot plus the assertion specification; the same JavaScript validation engine used by the PWA independently evaluates those assertions and renders one PASS/FAIL row per scenario.

Automated layers (no manual intervention):

- `make pwa-68-api-test` — all 92 cases execute through the PWA HTTP bridge.
- `make pwa-68-frontend-test` — Node executes the exact PWA JavaScript assertion/render module against all 92 live HTTP results and requires 92/92 PASS. This validates C++/hub → backend → HTTP → frontend JS interpretation/rendering without a person clicking anything.
- `make pwa-e2e-test` — existing PWA bridge + 92-case API + 92-case frontend JavaScript validation.
- `release-gate` includes all three as mandatory stages.

Manual verification is also retained: choose any scenario in the left-side validation panel and run it individually, or run all 92 and inspect each step/assertion. This panel is verification-only and should be hidden/removed in production.

Actual-browser validation is mandatory in `make release-gate-final`; the generated manual plan remains supplementary and does not replace the final gate.
