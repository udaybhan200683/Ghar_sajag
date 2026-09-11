# Ghar Sajag patch notes — v1.5.4

This release is focused on **regression safety before hardware arrival**.

## New validation framework

- `tests/functional/scenario_catalog.json` — 68 canonical host-functional cases.
- `tools/validation/functional_scenarios.py` — safe declarative scenario executor.
- `tools/validation/run_functional_suite.py` — CLI report generator.
- `tests/fixtures/sensor_streams/` — five realistic dummy event streams.
- `tools/validation/run_dummy_sensor_streams.py` — stream replay runner.
- `tools/validation/generate_manual_plan.py` — generates the manual checklist from the same catalog.
- `tests/MANUAL_FUNCTIONAL_VALIDATION.md` — 68 manual cases plus visual/accessibility and physical-hardware checks.
- `tests/validation_coverage.json` + `scripts/check_validation_coverage.py` — F01–F14/E01–E10 coverage contract.
- `tools/validation/release_gate.py` — fail-closed host/software release orchestration.
- `docs/VALIDATION_FRAMEWORK.md` — framework policy and commands.

## Functional corrections found by the new tests

- Quiet-hours and door-left-open connected simulation now consumes C++ `RulesCore` decisions instead of reproducing policy in Python.
- Daytime inactivity now reaches backend/read-model/incident routing in the connected simulator.
- Invalid sensor/event combinations are rejected according to simulated node capabilities.
- Rule signals include the actual detection time, preventing a left-open warning from sorting after a later close.

## Release rule

For future features, add positive, negative and boundary/recovery coverage before release. A new version is not host-release-ready until `make release-gate` passes. If Playwright is part of the release environment, use `make release-gate-browser` so actual-browser automation is mandatory.

Physical ESP32/RF/power/flash/OTA/provider validation remains pending until those integrations exist.
