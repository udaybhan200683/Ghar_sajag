# Full verification aggregate — Ghar Sajag v1.5.4

**Result: PASS for mandatory host/software stages; browser manual review required in this environment.**

| Layer | Result | Evidence |
|---|---:|---|
| validation coverage | PASS | 24/24 P0 IDs mapped |
| contracts | PASS | 4 schemas + protocol examples + config + OpenAPI |
| C++ unit/component | PASS | 80 checks |
| Python backend/database/logging/framework | PASS | 24 tests |
| JavaScript app | PASS | 10 tests |
| Base product profile | PASS | passed |
| AI product profile | PASS | passed |
| feature flag matrix | PASS | 4/4 variants |
| dummy sensor streams | PASS | 5/5 streams |
| connected functional catalog | PASS | 68/68 scenarios |
| HTTP integration | PASS | 16/16 tests |
| ASan/UBSan | PASS | 80 C++ checks |
| trace-enabled C++ | PASS | 80 checks |
| Playwright browser | MANUAL_REQUIRED | Playwright not installed; generated manual plan provided |

The long compile stages were executed individually because the hosted command runner limits one long command invocation. `make release-gate` still contains those stages and is the release command for the local/CI environment.

Physical ESP32/RF/power/flash/OTA/provider acceptance remains pending.

