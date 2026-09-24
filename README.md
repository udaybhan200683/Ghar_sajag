# Ghar Sajag / Parivar Saathi

Ghar Sajag is a home activity and routine monitoring system. Battery-operated
sensor Nodes (currently ESP32-C3 prototypes) report activity to an ESP32 Hub.
The product direction combines local event/rule handling, a backend/cloud
service, and a caregiver/family PWA. Current sensing includes PIR activity;
door/reed sensing is planned/available in the product roadmap.

## Architecture and present connectivity

```text
PIR / door sensor -> NodeRuntime -> authenticated local transport -> Hub
                                                       -> rules / journal / state
                                                       -> backend -> caregiver PWA
```

The Node/Hub target path has a qualified one-Hub/one-C3 physical smoke and
same-image C3 OTA recovery path. Host code also exercises independent logical
NodeRuntime instances. A production Hub-to-backend-to-PWA target bridge,
target commissioning/runtime-security wiring, target multi-Node scale, and
physical multi-C3 RF behavior are still open. Host simulations and backend
device records do not establish those target behaviors.

## Current project status

- **Phase 1:** CLOSED / qualified. The 71 real-hardware regression cases
  remain mandatory.
- **Phase 2:** ACTIVE / NOT COMPLETE. Host security, persistence, and
  multi-Node foundations exist; target integration and several qualification
  areas remain open.
- **Battery optimization:** PLANNED next major power track. No low-power
  optimization is claimed by this status.
- **P0 product vertical:** real-device-to-backend-to-caregiver-PWA work remains
  open.

## Qualification terms

- **HOST / SIMULATED:** host tests or logical Nodes using production components
  where stated; this is not physical RF evidence.
- **TARGET BUILD:** firmware compiles for a board/configuration; this does not
  prove the compiled path was exercised on hardware.
- **PHYSICAL HIL:** connected target evidence with recorded firmware identity
  and provenance. Current Phase-2 physical evidence is one Hub plus one C3.
- **PHYSICAL MULTI-C3:** real RF contention/fairness with multiple Nodes; not
  yet qualified.
- **BLOCKED_EXTRA_FIXTURE:** a test needs an electrical, optical, current, or
  RF fixture unavailable to that campaign. It is not a test failure.

## Validated code and latest evidence

- Last physically qualified firmware/code commit: `7bc2a33`
- Current repository/documentation commit at this checkpoint: `6f49d28`
- Latest physical evidence: [`evidence/hil/runs/20260924T094521.398370Z`](evidence/hil/runs/20260924T094521.398370Z)

The evidence records 17/17 smoke and 3/3 same-image FOTA cases passing,
20 PASS, 0 FAIL and six `BLOCKED_EXTRA_FIXTURE`. It proves the same-image OTA
and post-boot health/recovery success path, not a version upgrade, signature
enforcement, rollback, or multi-C3 RF qualification. A later documentation
commit does not change the firmware provenance recorded in the run.

## Repository map

| Area | Location |
|---|---|
| Node firmware | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/` |
| Hub firmware | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/` |
| Shared runtime, codecs and security | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/common/` and the Node/Hub firmware trees |
| Backend and PWA | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/backend/`, `app/`, and `shared/` |
| Simulation | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/`, `tools/`, and backend/PWA simulation code |
| HIL tooling | root WSL/USB helpers in `tools/hil/`; campaign supervisor and target test support in `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/` |
| Validation and tests | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/`, `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/validation/`, `docs/validation/` |
| Qualification evidence | `evidence/` |
| Project documentation | `docs/` |

## Documentation ownership and where to continue

- [Current status and roadmap](docs/progress/CURRENT_STATUS_AND_ROADMAP.md) —
  present truth and next work.
- [Project history](docs/progress/PROJECT_HISTORY.md) — chronological record.
- [Phase-2 architecture and gap analysis](docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md)
  — architecture decisions and detailed gaps.
- [Master traceability](docs/validation/MASTER_TRACEABILITY.csv) — requirement,
  test, evidence, and status mapping.
- [HW-M1.4 post-resilience roadmap](docs/hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md)
  — canonical battery/power and later routine-learning roadmap.
- [HW-M1.4B power baseline plan](docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md) —
  measurement procedure before low-power changes.
- [Master validation guide](docs/validation/MASTER_VALIDATION.md) — validation
  ownership and commands.
