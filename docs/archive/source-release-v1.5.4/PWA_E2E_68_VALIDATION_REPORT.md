# Parivar Sathi PWA — 92-Scenario End-to-End Validation

## Scope
This update connects the canonical Ghar Sajag v1.5.4 functional catalog to the Parivar Sathi PWA verification UI and automated frontend validation.

## Automated data flow
Canonical scenario -> C++ node/hub simulation -> Python backend/read models -> local HTTP validation bridge -> PWA JavaScript validation engine -> rendered PASS/FAIL model.

## Added automation
- `tests/pwa_68_api_test.py`: executes all 92 scenarios through HTTP validation endpoints.
- `tests/pwa_68_frontend_test.py` + `tests/pwa_68_frontend_runner.mjs`: executes all 92 live HTTP scenarios and validates expected state using the exact JavaScript assertion/render module used by the PWA.
- `tools/sim/pwa/validation_engine.mjs`: shared frontend assertion and validation-row renderer.
- `tools/validation/pwa_frontend_validation.py`: exposes raw scenario state and canonical assertions to the frontend without reusing backend PASS/FAIL results.
- Mandatory PWA stages added to the release gate.

## Manual verification
The Home page has a temporary left-side **92-case PWA validation** panel:
- Run all 92 automatically
- Select and run one scenario manually
- Inspect step results and assertion details
- See per-case PASS/FAIL rows

This panel is verification-only and can be hidden/removed for production.

## Verification executed in authoring environment
- Canonical functional suite: PASS 92/92
- Existing PWA bridge tests: PASS 5/5
- PWA 92-case HTTP bridge: PASS
- PWA 92-case frontend JavaScript end-to-end: PASS 92/92
- Quick release gate: PASS
- Existing actual-browser Playwright stage: MANUAL_REQUIRED because Playwright is not installed in the authoring environment. This does not block the new unattended frontend-JavaScript end-to-end gate.

## Commands
```bash
make pwa-e2e-test
python3 tools/validation/run_functional_suite.py
python3 tools/validation/release_gate.py --quick
```

For the local PWA:
```bash
make lab
```
Open `http://localhost:8765/`, then use the left-side validation panel.

> Filename retained for backward compatibility; the canonical catalog now contains 92 cases.
