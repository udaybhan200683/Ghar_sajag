# Reference code 1.5.4 verification

## Result

**PASS for mandatory host/software checks executed in this environment.** Actual Playwright/Chromium automation is **not recorded as passed** because Playwright is not installed; the generated manual browser/PWA plan is provided instead.

| Verification layer | Result |
|---|---:|
| P0 validation coverage map | PASS — 24/24 requirement IDs mapped |
| Contract verifier | PASS — 4 schemas + protocol examples + config + OpenAPI |
| C++ unit/component | PASS — 80 checks |
| Python backend/database/logging/framework | PASS — 24 tests |
| JavaScript app | PASS — 10 tests |
| Base product profile | PASS |
| AI product profile compatibility | PASS |
| Feature-flag matrix | PASS — 4/4 variants |
| Dummy sensor streams | PASS — 5/5 |
| Declarative connected functional suite | PASS — 68/68 |
| HTTP integration | PASS — 16/16 |
| AddressSanitizer/UBSan | PASS — 80 C++ checks |
| Trace-enabled C++ build/test | PASS — 80 checks |
| Playwright browser automation | MANUAL_REQUIRED — dependency not installed |

## Functional coverage added in v1.5.4

Expected motion/check-in/call behavior; morning positive/negative evidence; coverage and clock suppression; normal/quiet-hours/left-open door behavior; configurable thresholds; daytime inactivity and re-arming; Away/Paused/Visitor suppression; WAN and node replay; duplicate suppression; provider-vs-human acknowledgement; caregiver claim/ack/resolve; invalid sensor/event/config inputs; all simulated node/hub diagnostic fault codes; and realistic multi-event dummy streams.

## Evidence

- `evidence/release_gate_v1.5.4/` — per-stage logs.
- `logs/functional_report.json` / `.txt` — 68-case functional result.
- `logs/dummy_sensor_stream_report.json` — five stream replays.
- `tests/MANUAL_FUNCTIONAL_VALIDATION.md` — generated manual suite.
- `tests/validation_coverage.json` — P0 requirement mapping.

## Boundary

The simulator uses synthetic sensor/RF/time/fault/provider inputs and in-memory runtime stores. The SQL schema is a validated persistence contract, not yet the connected runtime store. Physical ESP32/RF/flash/power/OTA/provider acceptance therefore remains pending.
