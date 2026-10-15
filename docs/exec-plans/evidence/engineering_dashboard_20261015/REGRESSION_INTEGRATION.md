# Engineering and Caregiver Dashboard Regression Integration — 2026-10-15

## Result

The existing GS-116/GS-130 framework now selects both dashboard regression surfaces in its PWA/browser composition. `make validation-pwa` executed every registered PWA stage. The aggregate is **FAIL** because the mandatory P0 product stage reported `product_status=PARTIAL`; the product completeness assertion remains unchanged. The other 13 stages passed. Physical qualification is `NOT_RUN`, and release approval is false.

This work establishes regression coverage for the existing Caregiver Dashboard and a **PREVIEW_ONLY** browser smoke for the inactive seven-screen Engineering Dashboard design. It does not establish production Engineering Dashboard UI, authentication, routes, or service-desk workflow availability.

## Source and receipts

- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1_dashboard`
- Branch: `feature/gs124-125-engineering-dashboard`
- Source HEAD at test start: `d57867b36118b0999adb1d9f3d5d27cde1c6f2b2`
- PWA source fingerprint: `77df80dd53f94ff8e6594cf75399da2a199d1bcee86719c1d03e677906336c61`
- Framework reported `source_unchanged=true` throughout the run. `tracked_dirty=true` reflects the intended uncommitted implementation changes present during qualification.
- Native report and all stage logs: [`native-pwa-1792025377817945141`](native-pwa-1792025377817945141/)
- The committed log copies have only trailing line whitespace removed; the exact native stage files remain under ignored `code/evidence/validation_framework/pwa-1792025377817945141/`. Their original hashes are recorded in the native report. The committed copies have a separate [`SHA256SUMS`](native-pwa-1792025377817945141/SHA256SUMS).
- Dashboard coverage audit: [`DASHBOARD_COVERAGE_MATRIX.csv`](DASHBOARD_COVERAGE_MATRIX.csv)
- Separate prior attempts, including historical failures, remain preserved in the existing ignored native framework evidence directory.

## Full PWA execution

Command: `make validation-pwa` from `code/`, with the unmodified registered suite composition. The native aggregate report records `software_status=FAIL`, `physical_status=NOT_RUN`, `release_approved=false`, 14 stages, and 1036.846 seconds total.

| Stage | Result | Count | Exit | Notes |
|---|---:|---:|---:|---|
| `host-build` | PASS | 1 build | 0 | |
| `contracts` | PASS | 1 group | 0 | |
| `lab-build` | PASS | 1 build | 0 | |
| `python` | PASS | 452 tests | 0 | One pre-existing historical classic ESP32 reserve-model skip, explicitly approved by its test reason |
| `javascript` | PASS | 23 tests | 0 | Existing Caregiver PWA JavaScript suite |
| `functional` | PASS | 92 groups | 0 | |
| `dummy-streams` | PASS | 5 groups | 0 | |
| `http` | PASS | 17 groups | 0 | |
| `bridge` | PASS | 13 groups | 0 | |
| `api` | PASS | 2 groups | 0 | |
| `frontend` | PASS | 2 groups | 0 | |
| `browser` | PASS | 86 tests | 0 | Caregiver Playwright browser regressions plus required preview suite |
| `p0-full-product-e2e` | **FAIL** | 26 checks | 0 | Execution assertions passed, but the required full-product result is `product_status=PARTIAL` |
| `diagnostic-foundation` | PASS | 98 tests | 0 | Engineering Dashboard host authorization/diagnostic/service-access suite |

The framework marks the P0 stage FAIL on the product-status assertion even though the runner exits 0 and all 26 scenario checks pass. Consequently `make validation-pwa` returns failure (GNU Make error exit 2); it must not be represented as aggregate PASS.

## Engineering Dashboard coverage

The browser stage executes 20 stable cases across desktop (1440 px) and mobile (390 px): Installation Overview, Live Events, Event Trace, Device Diagnostics, Communication Health, Guided Installation Test and Advanced Diagnostics, plus trace `UNKNOWN`, event filtering/refresh, disabled privileged controls and layout behavior. Its mandatory success pattern requires every case ID and the final `PREVIEW_ONLY` scope marker. Browser errors and non-GET requests fail the preview runner. Screenshots and JSON are written only under ignored `code/build/engineering_dashboard_preview/`; source review fixtures remain read-only.

All seven surfaces remain `PREVIEW_ONLY`. The preview tests saved design navigation and rendering, not live Home data, trusted sessions, staff roles, real telemetry, device commands, or commercial authorization. Service-desk domain tests remain host SQLite/fixture tests. Real OIDC, production PostgreSQL, authenticated PWA service routes, CSRF, and browser workflow cases remain **BLOCKED** until their production sources exist.

The 98-test diagnostic foundation suite is selected by `validation-pwa`, `validation-fast`, `validation-backend`, and release composition. The complete browser stage is selected by `validation-pwa` and release composition, and is intentionally excluded from `validation-fast`.

## Caregiver Dashboard coverage

The existing caregiver source and tests were retained. The coverage matrix maps Home status, motion chronology, door state, morning/night status, I Am OK, Call Family incident projection, Hub/Node health, notifications, device settings, household access, backend outage/recovery, refresh/cache and responsive behavior to their existing API, JavaScript, Playwright and P0 tests. The PWA run executed 23 JavaScript tests and all 86 existing caregiver browser tests. The P0 runner executed all 26 product scenario checks and its dedicated Chromium test, while correctly reporting the incomplete product path as PARTIAL.

Coverage gaps remain visible in the matrix: production caregiver session expiry and cross-dashboard role isolation; external calling/provider delivery; installed-browser cache eviction and cache isolation across Home/session changes; real device stimulus and physical qualification. These remain gaps or blockers, not inferred passes.

## Focused and registry validation

| Command | Result |
|---|---|
| `PYTHONPATH=backend:. python3 -m unittest discover -s tests/engineering_dashboard -p 'test_*.py' -v` | PASS, 98/98 |
| `PYTHONPATH=backend:. python3 -m unittest tests.python.test_component_gate tests.python.test_feature_traceability -v` | PASS, 62/62 |
| `make feature-coverage-test` | PASS, 20 integrity tests; 165 feature rows, 209 source modules, 14 physical cases |
| `python3 scripts/playwright_preflight.py` | PASS |
| `NODE_PATH="$PWD/node_modules" npx playwright test --list` | PASS, 86 tests in seven spec files; P0 browser spec owned by its injected-stack stage |

Traceability registers the seven Engineering preview surface requirements and the 98-test host diagnostic suite. The PWA stage registration fingerprints the browser config, caregiver specs, review runner and immutable review inputs; the JavaScript stage registers each relevant production module and test input. The P0 owner includes its injected browser configuration and scenario/test sources. A marker omission or production-scope substitution is a framework meta-test failure.

## Changed validation behavior and remaining blockers

- `validation-pwa` now has an explicit PWA selector for the full browser stage and the diagnostic/service-access foundation suite.
- `validation-fast` includes lightweight PWA JavaScript and the existing diagnostic host tests but excludes the long Playwright campaign.
- `playwright-gate` includes caregiver desktop/mobile coverage and the repeatable seven-screen preview smoke; the P0 spec remains owned by the full-product runner with its injected local stack.
- A missing preview case ID or wrong qualification marker fails the browser stage. P0 remains governed by `require_complete_product`; its PARTIAL state continues to fail the aggregate.
- Real Engineering Dashboard UI/authentication/routes, OIDC identity, PostgreSQL integration, staff lifecycle, service-desk PWA flows/CSRF, cross-dashboard authenticated data isolation, and physical hardware qualification remain blockers.
- No release gate or physical HIL was run. GS-148 source and product completeness assertions were not changed.
