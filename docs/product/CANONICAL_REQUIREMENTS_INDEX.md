# Canonical Requirements and Documentation Index

This is the authority map for Ghar Sajag documentation. For substantive Codex work, start with [project context](GHAR_SAJAG_PROJECT_CONTEXT.md), [R1 release contract](R1_RELEASE_CONTRACT.md), [current work state](R1_WORK_STATE.md), then this index. Read only relevant domain sources after that.

## Mandatory document precedence

For conflicting Ghar Sajag documentation, use this exact order:

1. LOCKED decisions in `docs/product/DECISION_LOG.md`.
2. `docs/product/R1_RELEASE_CONTRACT.md`.
3. Current CANONICAL domain requirement/design documents identified by this index.
4. `docs/product/R1_WORK_STATE.md` for current implementation, qualification and blocker status.
5. SUPPORTING and IMPLEMENTATION_DESIGN documents.
6. TEST_PLAN and TEST_EVIDENCE, as validation/evidence rather than product-requirement authority.
7. HISTORICAL and SUPERSEDED documents.
8. Chat/session assumptions.

A lower-authority document never overrides a higher-authority requirement. Implementation facts and product requirements are different claims: an older design may accurately describe current code, but cannot set current product scope. For example, the Hub's current 128-entry journal is an implementation fact; a fixed 128-event R1 product lifetime conflicts with GS-D005 and GS-D016.

If two current documents conflict and no higher-authority LOCKED decision resolves the conflict, classify it as `REQUIREMENT_CONFLICT`. Do not choose by timestamp, reading order, or intuition. Stop product-semantic implementation, state the exact conflicting text and sources, and request a product/user decision. Read-only investigation may continue.

## Canonical documents

| Path | Classification | Purpose | Read when |
|---|---|---|---|
| `AGENTS.md` | CANONICAL | Codex source order, triage and closeout rules | Every substantive task |
| `docs/product/CANONICAL_REQUIREMENTS_INDEX.md` | CANONICAL | Authority map, requirement register and document navigation | Every substantive task; use to choose domain sources |
| `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md` | CANONICAL | Concise product, architecture, status and priority orientation | Every substantive task |
| `docs/product/P0_PRODUCT_REQUIREMENTS.md` | CANONICAL | Current P0 household, sensor/event, caregiver, privacy and implementation boundaries | P0/product behavior work |
| `docs/product/R1_RELEASE_CONTRACT.md` | CANONICAL | Release scope, invariants, bug/scope classification | Any product, code, or validation task |
| `docs/product/R1_WORK_STATE.md` | CANONICAL-LIVING | Current closed gates, blocker and next task | Resuming or changing R1 work |
| `docs/product/DECISION_LOG.md` | CANONICAL | Locked/provisional/open decisions | A decision could be affected |
| `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | CANONICAL | Hub storage classes, sync, offline, PWA freshness and local learning | Storage, cloud, PWA, or routine work |
| `docs/product/CONTEXT_VERSION` | CANONICAL | Machine-readable canonical context revision | Worktree preflight/version governance |

## Document map

Each canonical file is listed once in the canonical table above. The domain sections below map the supporting source documents.

### PRODUCT

| Path | Classification | Use | Read when |
|---|---|---|---|
| `README.md` | SUPPORTING | Repository/product entry point | First repo orientation or setup |
| `docs/product/P0_PRODUCT_REQUIREMENTS.md` | CANONICAL | Supported P0 product behavior and explicit gaps | P0/product behavior changes |
| `docs/progress/P0_SOFTWARE_GAP_AUDIT_HW_M1.md` | HISTORICAL | P0 software gap audit and transition | Trace original P0 gap closure |
| `docs/progress/Phase_0_Current_Baseline_Reconciliation_v1.5.4.md` | HISTORICAL | Version-specific baseline reconciliation | Understand that release-era snapshot |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/backend/DATA_MODEL.md` | SUPPORTING | Backend data model from v1.5.4 | Backend schema work; check canonical contract first |

### R1

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/product/R1_WORK_STATE.md` | CANONICAL-LIVING | Current gates, blocker, next design work | R1 execution/handoff |
| `docs/progress/R1_WORKTREE_RECONCILIATION_20261007.md` | TEST_EVIDENCE | Reconciled source/tool/evidence attribution and focused validation snapshot | Audit the committed qualification baseline and known deferred test failure |
| `docs/progress/CURRENT_STATUS_AND_ROADMAP.md` | HISTORICAL | Earlier roadmap snapshot | Trace earlier status; do not use as current status |
| `docs/progress/FEATURE_IMPLEMENTATION_STATUS_AND_REMAINING_GAPS_AT_0608e2a.md` | HISTORICAL | Commit-specific implementation gap snapshot | Inspect that historical baseline |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/IMPLEMENTATION_STATUS.md` | SUPPORTING | Release-code implementation notes | Investigate reference implementation; verify against R1 state |
| `docs/progress/PROJECT_HISTORY.md` | HISTORICAL | Engineering chronology | Trace why an approach changed |

### ARCHITECTURE

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md` | HISTORICAL | Phase 2 architecture/gap analysis | Trace prior phase; canonical R1 decisions win |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PRODUCT_ARCHITECTURE_v1.4.md` | SUPERSEDED | v1.4 product architecture/status snapshot | Historical only; use current product context and domain contracts |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/README.md` | SUPPORTING | Reference implementation structure and commands | Working in embedded code project |
| `WHATS_CHANGED.md` | HISTORICAL | Documentation-edition change note | Documentation provenance |

### HUB

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/HUB_PERSISTENCE_AND_RECOVERY.md` | IMPLEMENTATION_DESIGN | Hub persistence/recovery behavior | Hub journal/recovery changes |
| `docs/design/HUB_DURABLE_STATE_TRANSITIONS.md` | IMPLEMENTATION_DESIGN | Durable transitions/effect intent | Durable transition or recovery changes |
| `docs/design/HUB_REDUCER_CHECKPOINT.md` | IMPLEMENTATION_DESIGN | Reducer checkpoint audit/design | Materialized state/checkpoint work |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/runtime/FREERTOS_BINDING.md` | IMPLEMENTATION_DESIGN | Hub runtime/FreeRTOS binding | Hub task and scheduling work |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/README.md` | SUPPORTING | Hub target adapter notes | Hub target build/configuration |

### NODE

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/EVENT_DELIVERY_RETRY_AND_RECOVERY.md` | IMPLEMENTATION_DESIGN | Retry, ACK and recovery protocol detail | Event delivery/retirement work |
| `docs/design/NODE_RETIREMENT_REPORT_PROTOCOL.md` | IMPLEMENTATION_DESIGN | Authenticated retirement reports and dedupe horizon | Retirement/reclamation design |
| `docs/features/DEVICE_IDENTITY_REGISTRATION_AND_LIFECYCLE.md` | IMPLEMENTATION_DESIGN | Device enrollment and identity lifecycle | Ownership/rejoin work |
| `docs/features/DEVICE_HEALTH_LIVENESS_AND_OFFLINE_DETECTION.md` | SUPPORTING | Health and offline semantics | Liveness or caregiver status |
| `docs/features/HUB_NODE_SECURE_COMMUNICATION.md` | IMPLEMENTATION_DESIGN | Hub/Node secure communication | Transport/authentication changes |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/contracts/NODE_TO_HUB_PROTOCOL.md` | SUPPORTING | Earlier P0 protocol contract | Protocol details; verify against current implementation/design |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/README.md` | SUPPORTING | ESP32-C3 target adapter notes | Node target build/configuration |

### STORAGE

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md` | IMPLEMENTATION_DESIGN / PROPOSED ExecPlan | Baseline-specific storage audit, candidate 4 MB budgets and lifecycle/proof plan; numerical policies remain unapproved | Review storage decisions and STOP gates before later implementation |
| `docs/DURABLE_STORAGE_EPIC_PAUSE_HANDOFF.md` | HANDOFF/WORK_STATE | Paused durable-storage work context | Resume that historical workstream; reconcile with current state |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/DURABILITY_ARCHITECTURE_CLOSURE_AUDIT.md` | SUPPORTING | Detailed durability audit and evidence | Audit current-format implementation |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/DURABLE_BACKEND_COMPLETION_CONTRACT.md` | IMPLEMENTATION_DESIGN | Backend completion receipt contract | Outbox completion/reclamation work |
| `docs/features/HUB_PERSISTENCE_AND_RECOVERY.md` | IMPLEMENTATION_DESIGN | Hub storage/recovery detail | Persistence implementation |

### CLOUD/PWA

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md` | SUPPORTING | Caregiver actions and notification intent | Caregiver-facing behavior |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/contracts/PHASE1_APPLICATION_API.md` | SUPPORTING | Earlier local integrated-lab API | API compatibility/implementation work |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3B_CONCURRENT_API_ISOLATION.md` | IMPLEMENTATION_DESIGN | Phase 3B API concurrency/isolation | Backend scalability work; not an R1 scope authority |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3B_REPORT_SCALABILITY.md` | IMPLEMENTATION_DESIGN | Phase 3B report scalability | Report query work |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3B_SCALE_OPTIMIZATION.md` | IMPLEMENTATION_DESIGN | Durable history read optimization | Backend query work |
| `docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md` | HISTORICAL | Large prototype implementation plan | Historical PWA scope only; not current R1 contract |
| `ParivarSathi_PWA_Prototype_v6/README.md` | HISTORICAL | Standalone PWA prototype | Prototype provenance |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/sim/pwa/README.md` | SUPPORTING | Integrated PWA simulator | PWA simulator use |

### ROUTINE LEARNING

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md` | IMPLEMENTATION_DESIGN | Routine and incident rule details | Routine logic work |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/BATTERY_ANALYTICS_DESIGN.md` | SUPPORTING | Battery analytics implementation design | Battery analytics only; not R1 scope authority |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/PATCH_NOTES_v3.3_ROUTINE_RULES.md` | HISTORICAL | Routine rule expansion note | Change provenance |

### POWER/BATTERY

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md` | IMPLEMENTATION_DESIGN | Battery/power feature design | Power policy or battery behavior |
| `docs/hw/HW_M1_4B_POWER_BASELINE_PLAN.md` | TEST_PLAN | Pre-optimization power baseline | Resume/run that measurement plan |
| `docs/hw/HW_M1_4_POWER_PERFORMANCE_PLAN.md` | TEST_PLAN | HW-M1.4 power/performance plan | Power/performance qualification |
| `docs/hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md` | BACKLOG/FUTURE | Post-resilience roadmap, including future work | Future planning; filter against R1 scope |
| `docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md` | TEST_PLAN | BAT-C8 R1 physical qualification procedure (P1–P10 are test case labels) | For the required production-critical qualification in GS-D020 |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/PATCH_NOTES_v3.4.0_BATTERY_ANALYTICS.md` | HISTORICAL | Battery analytics patch note | Release history |

### FOTA

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/FOTA_ENGINEERING_FLASHING_SECURITY_AND_RECOVERY_GUIDE.md` | IMPLEMENTATION_DESIGN | FOTA security, flashing and recovery | FOTA implementation/operations |
| `docs/validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md` | TEST_PLAN | Signed FOTA physical qualification | FOTA qualification |
| `docs/hw/evidence/HW_M1_FOTA/README.md` | TEST_EVIDENCE | HW-M1 FOTA qualification evidence | Verify historical FOTA gate |

### SECURITY

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/features/HUB_NODE_SECURE_COMMUNICATION.md` | IMPLEMENTATION_DESIGN | Secure transport and identity detail | Hub/Node security changes |
| `docs/features/DEVICE_IDENTITY_REGISTRATION_AND_LIFECYCLE.md` | IMPLEMENTATION_DESIGN | Identity ownership/lifecycle | Enrollment/rejoin changes |
| `docs/hw/PHASE2_DEVICE_IDENTITY_PROVISIONING.md` | IMPLEMENTATION_DESIGN | Phase 2 provisioning design | Provisioning work; validate R1 scope |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/G01_ENROLLMENT_OWNERSHIP_MIGRATION_CONTRACT.md` | SUPPORTING | Detailed enrollment/ownership contract and migration history | Ownership migration audit; fresh-install contract wins for scope |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/SESSION_RECOVERY_PROTOCOL.md` | IMPLEMENTATION_DESIGN | Authenticated session recovery detail | Session/rejoin work |

### VALIDATION

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/validation/MASTER_VALIDATION.md` | TEST_PLAN | Host/simulation/validation framework | Choose validation gates |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/VALIDATION_FRAMEWORK.md` | TEST_PLAN | Reference-code validation framework | Reference application tests |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/SIMULATION_START_HERE.md` | TEST_PLAN | Hardware-independent verification entry | Host simulation workflow |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/SIMULATION_LLD_v1.0.md` | IMPLEMENTATION_DESIGN | Simulation adapter low-level design | Simulator implementation |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/FEATURE_FLAGS.md` | SUPPORTING | Build/runtime simulation flags | Configure supported simulation |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3_STRESS_FRAMEWORK.md` | TEST_PLAN | Phase 3 stress framework | Stress qualification; check scope first |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3A_PERFORMANCE.md` | TEST_PLAN | Phase 3A performance budgets | Performance qualification; check R1 priority |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/MANUAL_FUNCTIONAL_VALIDATION.md` | TEST_PLAN | Manual app validation scenarios | Manual PWA/product validation |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/PWA_E2E_68_VALIDATION_REPORT.md` | TEST_EVIDENCE | PWA end-to-end report (title says 92 scenarios) | Historical browser proof; reconcile report details before citing |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/VERIFICATION_REPORT.md` | TEST_EVIDENCE | Reference-code verification report | Reference code only |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/RESULTS.md` | TEST_EVIDENCE | Fresh R1 runtime host gate | Verify this host gate |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/MANUAL_FUNCTIONAL_VALIDATION.md` | TEST_PLAN | Manual functional validation | PWA validation |

### HIL

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/validation/HIL_AUTOMATION.md` | TEST_PLAN | HIL automation procedure | HIL orchestration changes |
| `docs/hw/HW_M1_3_HIL_VALIDATION.md` | TEST_PLAN | HW-M1.3 HIL plan | That hardware gate |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/installation_checklist.md` | TEST_PLAN | Installation preflight checklist | Physical installation |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/README.md` | SUPPORTING | Development bench initialization commands | Factory bench operation; never infer product behavior |
| `tools/usb/README_ZERO_TOUCH.md` | BACKLOG/FUTURE | Optional USB automation setup | Only when explicitly working on USB convenience tooling |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/MANUAL_FUNCTIONAL_VALIDATION.md` | TEST_PLAN | Product functional scenarios | Manual validation, not hardware HIL |

### HARDWARE

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/hw/HW_M1_IMPLEMENTATION_PLAN.md` | HISTORICAL | HW-M1 implementation plan | Trace hardware plan history |
| `docs/hw/evidence/HW_M1_2/README.md` | TEST_EVIDENCE | ESP-NOW qualification evidence | Verify historical radio gate |
| `docs/hw/evidence/HW_M1_3_TARGET_BUILD/README.md` | TEST_EVIDENCE | Target build evidence | Verify historical target build |
| `docs/hw/evidence/HW_M1_3_HOST/README.md` | TEST_EVIDENCE | Host validation evidence | Verify historical host gate |
| `docs/hw/evidence/HW_M1_3_HIL/README.md` | TEST_EVIDENCE | Negative HIL physical evidence | Verify historical negative HIL |
| `docs/hw/evidence/HW_M1_3_FINAL_SMOKE/README.md` | TEST_EVIDENCE | Clean production smoke evidence | Verify historical smoke gate |
| `docs/hw/evidence/HW_M1_4A_ENDURANCE/README.md` | TEST_EVIDENCE | Offline resilience/endurance closure | Verify historical endurance gate |
| `docs/hw/evidence/HW_M1_4_NODE_OFFLINE_RESILIENCE/README.md` | TEST_EVIDENCE | Node offline resilience evidence | Verify Node outage behavior |

### BACKLOG/FUTURE

| Path | Classification | Use | Read when |
|---|---|---|---|
| `docs/hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md` | BACKLOG/FUTURE | Forward roadmap | Future planning only |
| `docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md` | HISTORICAL | Prototype-era broad PWA task | Historical context only |
| `docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md` | TEST_PLAN | Pending BAT-C8 production qualification; no battery-life/endurance claim | Schedule required R1 gate without expanding it into deferred optimization |
| `tools/context/ghar_sajag_context_preflight.sh` | SUPPORTING | Read-only canonical context/version guard | Before substantive work in any Ghar Sajag worktree |
| `tools/usb/README_ZERO_TOUCH.md` | BACKLOG/FUTURE | Optional USB automation | Explicit tooling task only |

### HISTORICAL

| Path family | Classification | Use | Read when |
|---|---|---|---|
| `docs/progress/PROJECT_HISTORY.md`, `docs/progress/CURRENT_BASELINE.md`, `docs/progress/CURRENT_STATUS_AND_ROADMAP.md`, `docs/progress/Phase_0_Current_Baseline_Reconciliation_v1.5.4.md` | HISTORICAL | Earlier snapshots and chronology | Understand provenance; do not treat as current state |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/PATCH_NOTES*.md`, `CHANGELOG.md`, `VERIFICATION_REPORT.md`, `PWA_E2E_68_VALIDATION_REPORT.md` | HISTORICAL / TEST_EVIDENCE | Versioned application changes and reported checks | Investigate the named app version only |
| `docs/hw/evidence/**`, `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/**` | TEST_EVIDENCE | Preserved physical/host results | Cite only for the exact gate, build and date recorded |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/PHASE3*.md` | IMPLEMENTATION_DESIGN / TEST_PLAN | Later-phase backend scalability/performance work | Explicit future/backend task only |

The complete per-file scan, including title, purpose, area, era, relevance, authority class, duplicate and conflict notes, is in [DOCUMENTATION_INVENTORY.md](DOCUMENTATION_INVENTORY.md). No historical document or evidence should be deleted or silently promoted.

## Document conflicts and historical precedence

| DOCUMENT_A | DOCUMENT_B | CONFLICT / OVERLAP | MOST_RECENT_DECISION | RECOMMENDED_AUTHORITY | USER_DECISION_REQUIRED |
|---|---|---|---|---|---|
| `docs/DURABLE_STORAGE_EPIC_PAUSE_HANDOFF.md` | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/product/R1_WORK_STATE.md` | The handoff calls removal of the 128-event limit deferred in its earlier scope; current R1 status makes bounded lifetime storage the active product blocker. | Current R1 blocker and lifetime ceiling decision in the 2026-10-07 canonical work state/log | `R1_RELEASE_CONTRACT.md`, `R1_WORK_STATE.md`, `DECISION_LOG.md` | NO; preserve handoff as history |
| `docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md` | Same document; `CHANGELOG.md`; caregiver and routine guides | The historical plan contradicts itself about a global user-facing Privacy ON/OFF control. Later release notes and current guides agree the generic control is absent and consent enforcement remains internal. | GS-D018, now stated canonically in `P0_PRODUCT_REQUIREMENTS.md` | `DECISION_LOG.md`, `P0_PRODUCT_REQUIREMENTS.md` | NO for existing behavior; new privacy behavior requires an explicit decision |
| `docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md`, `ParivarSathi_PWA_Prototype_v6/README.md` | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | Prototype-era local/demo state and dashboard integration assumptions overlap with the current backend-first, continuously synchronized product contract. | Current backend-first contract and GS-D007/008 | `STORAGE_SYNC_ROUTINE_LEARNING.md` | NO for R1 source precedence; prototype remains historical |
| `docs/progress/CURRENT_BASELINE.md`, `docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md`, phase plans | `docs/product/DECISION_LOG.md` | Older release snapshots and proposals can describe phase scope, capacities or hardware options that are not current R1 commitments. No specific contrary approved hardware decision was found in the inspected excerpts. | Locked 4 MB Hub / ESP32-C3 decision; future hardware is not an R1 dependency | `DECISION_LOG.md`, `R1_RELEASE_CONTRACT.md` | NO unless proposing a hardware change; then approval is required |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/G01_ENROLLMENT_OWNERSHIP_MIGRATION_CONTRACT.md`, `docs/DURABLE_STORAGE_EPIC_PAUSE_HANDOFF.md` | `R1_RELEASE_CONTRACT.md` | Older migration design/material includes compatibility work beyond supported fresh-install R1. Migration remains post-R1 unless it blocks fresh install. | Fresh-install boundary in R1 release contract | `R1_RELEASE_CONTRACT.md` | NO for current scope; YES to expand R1 migration support |
| `docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md` | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/product/DECISION_LOG.md` GS-D020, battery guide | The plan's physical qualification scope is required for production-critical sleep/wake behavior; final battery-life optimization and endurance remain outside absent an explicit claim. | GS-D020 resolves/supersedes GS-D019 | `DECISION_LOG.md`, `R1_RELEASE_CONTRACT.md`, `P0_PRODUCT_REQUIREMENTS.md` | NO; classification resolved |

## Partial supersession and 128-entry journal references

Supersession is section-specific. The following documents retain useful implementation facts while no longer defining the R1 product lifetime or reclamation requirement.

| PATH | CLASSIFICATION | STILL_VALID_FOR | NO_LONGER_AUTHORITATIVE_FOR | SUPERSEDED_BY | DECISION_IDS |
|---|---|---|---|---|---|
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/DURABLE_BACKEND_COMPLETION_CONTRACT.md` | IMPLEMENTATION_DESIGN (partial supersession) | Current append-only slot mapping 0..127, completion receipt behavior, and current admission limit | Desired commercial capacity, retention/lifetime, future reclamation | Current storage architecture contract and approved lifecycle design | GS-D005, GS-D006, GS-D016 |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/DURABILITY_ARCHITECTURE_CLOSURE_AUDIT.md` | SUPPORTING (partial supersession; audit snapshot) | Code-path findings and “not implemented/untested” observations, subject to rechecking current code | Product acceptance of 128-event lifetime | `R1_RELEASE_CONTRACT.md`, `R1_WORK_STATE.md`, storage architecture contract | GS-D005, GS-D016 |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/G01_ENROLLMENT_OWNERSHIP_MIGRATION_CONTRACT.md` | IMPLEMENTATION_DESIGN (partial supersession) | Ownership/migration implementation detail and historical 128-bound assumptions | R1 requirement for a fixed 128-entry lifetime | `R1_RELEASE_CONTRACT.md`, current storage architecture contract | GS-D001, GS-D005, GS-D016 |
| `docs/DURABLE_STORAGE_EPIC_PAUSE_HANDOFF.md` | HANDOFF/WORK_STATE (partial supersession) | Historical pause, migration scope and test state at handoff | Its statement that removing the 128-event limit is post-R1 | `R1_RELEASE_CONTRACT.md`, `R1_WORK_STATE.md`, `DECISION_LOG.md` | GS-D001, GS-D005, GS-D016 |
| `docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md` | HISTORICAL (partial supersession) | Phase-2 architecture and old target sizing facts | Current R1 capacity/retention requirement | `DECISION_LOG.md`, storage architecture contract | GS-D003, GS-D005, GS-D016 |
| `docs/design/NODE_RETIREMENT_REPORT_PROTOCOL.md` | IMPLEMENTATION_DESIGN (partial supersession) | Retirement proof mechanics and implementation-era ledger bound | Overall Hub capacity/lifetime requirement | Current storage architecture contract and approved lifecycle design | GS-D005, GS-D016 |
| `docs/design/HUB_DURABLE_STATE_TRANSITIONS.md` | IMPLEMENTATION_DESIGN (partial supersession) | Transition/checkpoint detail and explicitly proposed bound | Approved commercial lifetime/capacity/reclamation policy | Current storage architecture contract and approved lifecycle design | GS-D005, GS-D016 |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/SIMULATION_LLD_v1.0.md` | HISTORICAL | Simulator-only Hub journal capacity 4096 and old simulator constraints | Physical Hub capacity or product retention | Current R1 contract and storage architecture contract | GS-D005, GS-D016 |

The production 0..127 slot range and event-129 admission failure are `CURRENT_IMPLEMENTATION_FACT` / `STILL_VALID_IMPLEMENTATION_DETAIL`. Acceptance of a 128-entry commercial lifetime is a `SUPERSEDED_PRODUCT_REQUIREMENT`; phase proposals are `HISTORICAL_DESIGN`. The simulator's 4096 capacity is a lab-only implementation detail. Current product requirement: finite 128-event lifetime is unacceptable; increasing only the constant is not an architecture fix; replacement capacity and retention remain OPEN pending the 4 MB/six-Node design.

## Locked-decision traceability

Decision text remains authoritative in `DECISION_LOG.md`; this table points to the canonical destination for details. Domain implementation and validation documents are mapped in sections above.

| DECISION_ID | CANONICAL_DESTINATION |
|---|---|
| GS-D001, GS-D002 | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md` |
| GS-D003, GS-D004 | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D005 | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`, `docs/product/R1_WORK_STATE.md` |
| GS-D006 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D007 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D008 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D009 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D010 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D011 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D012 | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` |
| GS-D016 | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`, `docs/product/R1_WORK_STATE.md` |
| GS-D018 | `docs/product/P0_PRODUCT_REQUIREMENTS.md`, `docs/features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md` |
| GS-D020 | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/product/P0_PRODUCT_REQUIREMENTS.md`, `docs/product/R1_WORK_STATE.md`, battery feature guide; GS-114 implementation/focused qualification, GS-146 final R1 battery closure |

## Context version and canonical worktree

`docs/product/CONTEXT_VERSION` is the comparable revision for project context. The canonical source is `/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`; this location/ref is configured in `tools/context/ghar_sajag_context_preflight.sh`. Update the script constants and this statement if the canonical source moves. Increment the version when a LOCKED decision or canonical requirement materially changes, not for spelling/formatting. Commit canonical documentation before implementation depends on a newly approved decision. A worktree whose version differs or whose required context files are missing must stop before substantive implementation.

## Classification totals and review flags

The full inventory includes 104 Markdown files. Classes describe document use, not truth of every statement. Several old release notes are grouped in the inventory as historical or evidence; no historical result was edited. No inventory entry is currently classified `UNKNOWN_REQUIRES_REVIEW`; re-evaluate classification before promoting a source. Do not treat similar titles or repeated plans as proof that one document is a duplicate requirement.

## Current requirement register

This register records requirements explicitly present in canonical sources. `UNKNOWN` means the cited docs do not establish implementation/validation status; it is not a claim of failure. Detailed feature requirements remain in their linked source documents.

| REQ_ID | Domain / requirement | Source | Status; priority; decision | Implementation / validation | Notes |
|---|---|---|---|---|---|
| GS-PROD-01 | Commercially installable fresh baseline; reduce scope, not quality | `docs/product/R1_RELEASE_CONTRACT.md` | LOCKED; P0/R1 | PARTIAL; fresh-install durability gates passed | R1 release objective |
| GS-P0-01 | P0 household, Hub/Node, event, caregiver, privacy, offline and deferral behavior plus evidence boundaries | `docs/product/P0_PRODUCT_REQUIREMENTS.md` | LOCKED where marked; OPEN items remain explicit; P0/R1 | PARTIAL; physical/app paths have separate evidence status | Canonical summary; domain details stay in guides |
| GS-R1-01 | Support current approved fresh-install persistent format; arbitrary abandoned-format migration deferred | `docs/product/R1_RELEASE_CONTRACT.md` | LOCKED; R1 | IMPLEMENTED for qualified path; gate passed | Migration-only work post-R1 absent fresh-path impact |
| GS-HW-01 | Existing 4 MB Hub and ESP32-C3 Node baseline; S3-N16R8 not dependency | `docs/product/DECISION_LOG.md` | LOCKED; R1 | UNKNOWN; not requalified here | Six Nodes share Hub resources |
| GS-HUB-01 | Hub owns authenticated ingestion, local safety/routine decisions, durable processing and ACK | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`, `docs/product/R1_RELEASE_CONTRACT.md` | LOCKED; R1 | PARTIAL; selected gates passed | See Hub and protocol designs |
| GS-NODE-01 | Node senses, retains/retries, and retires only on valid application ACK | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/product/R1_WORK_STATE.md` | LOCKED; R1 | IMPLEMENTED; physical gate passed | Do not repeat absent invalidation |
| GS-EVENT-01 | Repeated raw PIR/sensor chatter coalesced where semantics permit | `docs/product/DECISION_LOG.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | LOCKED; R1 | UNKNOWN; validation not recorded | Preserve safety-relevant identity/meaning |
| GS-SENSOR-01 | PIR is the established physical Node sensor; Reed/button categories in software are not proof of installed/qualified physical sources | `docs/product/P0_PRODUCT_REQUIREMENTS.md`, `docs/features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md` | LOCKED distinction; P0/R1 | PIR physical path exercised; Reed/button end-to-end support OPEN | Keep product vocabulary distinct from target hardware evidence |
| GS-CARE-01 | I Am OK and Call Family remain distinct app events; no emergency dispatch or production provider is implied | `docs/product/P0_PRODUCT_REQUIREMENTS.md`, `docs/features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md` | LOCKED boundary; P0 | Application model present; physical controls/live provider unproven | Caregiver claim/acknowledge/resolve are separate |
| GS-STORE-01 | Durable-before-ACK, duplicate/lost-ACK safety, reboot recovery, fail closed | `docs/product/R1_RELEASE_CONTRACT.md` | LOCKED; R1 | IMPLEMENTED; physical durability/lost-ACK gate passed | Current-format path |
| GS-STORE-02 | Shared 128-event lifetime ceiling unacceptable; simply raising it is not a fix | `docs/product/DECISION_LOG.md`, `docs/product/R1_WORK_STATE.md` | LOCKED; R1 | UNIMPLEMENTED; blocker open | Current top product blocker |
| GS-STORE-03 | Separate correctness state, reducer state, backend backlog, short history; safe reclamation | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | PROVISIONAL/OPEN details; R1 | UNIMPLEMENTED; design open | Exact bytes/retention not locked |
| GS-SEC-01 | Authenticated ownership/domain validation and versioned storage/FOTA behavior | `docs/product/R1_RELEASE_CONTRACT.md` | LOCKED; R1 | PARTIAL; ownership qualification passed | No weakened fallback |
| GS-PRIV-01 | No generic ordinary PWA Privacy ON/OFF control; consent withdrawal may enforce internal privacy state that suppresses passive routine evidence | `docs/product/P0_PRODUCT_REQUIREMENTS.md`, `docs/product/DECISION_LOG.md` (GS-D018) | LOCKED; P0/R1 | PWA/current guide behavior documented; no new UX implementation | Privacy and notification preferences remain separate |
| GS-FOTA-01 | Preserve signed/versioned FOTA and recovery semantics | `docs/product/R1_RELEASE_CONTRACT.md`, `docs/features/FOTA_ENGINEERING_FLASHING_SECURITY_AND_RECOVERY_GUIDE.md` | LOCKED; R1 | UNKNOWN here; consult FOTA evidence | No new qualification claimed |
| GS-POWER-01 | Production-critical BAT-C8 sleep/wake behavior, with physical qualification pending | `docs/product/DECISION_LOG.md` GS-D020, `docs/product/R1_RELEASE_CONTRACT.md`, `docs/features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md` | LOCKED; R1_REQUIRED_FEATURE_WITH_PENDING_QUALIFICATION | C8A software policy implemented; C8B physical qualification pending | Final battery-life optimization/endurance excluded absent an explicit R1 claim |
| GS-PWA-01 | Backend-first PWA shows already-current caregiver data | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | LOCKED; R1 | UNKNOWN against current backend contract | Dashboard-open is not primary sync |
| GS-CLOUD-01 | Connected Hub sync near-real-time, independent of storage pressure/PWA open | `docs/product/DECISION_LOG.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | LOCKED; R1 | PARTIAL/UNKNOWN; production contract details open | Exact protocol/backlog policy open |
| GS-CLOUD-02 | Cloud outage leaves local sensing/safety/learning active; show stale/offline; backfill on return | `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | LOCKED; R1 | UNKNOWN; validation not recorded | Offline capacity target open |
| GS-AI-01 | Basic routine/baseline/trend learning local and bounded; richer analytics may be backend | `docs/product/DECISION_LOG.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | LOCKED; R1 | PARTIAL/UNKNOWN; bounded persistence design open | No heavyweight ML requirement |
| GS-OFF-01 | Storage pressure may reduce low-value history but cannot stop core safety operation | `docs/product/DECISION_LOG.md`, `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | LOCKED; R1 | UNIMPLEMENTED design details; open | Priority thresholds open |
| GS-VAL-01 | Host tests first, then target size/build, then relevant physical gates | `docs/product/R1_RELEASE_CONTRACT.md` | LOCKED; R1 | IMPLEMENTED as process; per-change | Do not repeat passed hardware gate without invalidation |
| GS-HIL-01 | Fresh-install/lost-ACK physical qualification closed | `docs/product/R1_WORK_STATE.md` | LOCKED status; R1 | IMPLEMENTED; physical PASS | Existing evidence preserved; BAT-C8 remains pending |
| GS-TOOL-01 | USB zero-touch setup is convenience tooling, not R1 blocker | `docs/product/R1_WORK_STATE.md` | LOCKED; post-R1 | Not required for product release | Avoid critical-path investment |
| GS-FUTURE-03 | Feature flags mark temperature context and external camera as P1 experiments | `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/FEATURE_FLAGS.md` | DEFERRED; P1 | Disabled; not an R1 requirement | Preserve flag defaults; new acceptance review required |

## Open decisions

See `DECISION_LOG.md`: exact local retention, offline duration, outbox policy, record encoding, active durability capacity, pressure thresholds, and partition-layout acceptability are not locked. Do not copy candidate numbers from historical plans into requirements without a decision.

## Storage-first requirement additions — 2026-10-07

GS-D021 (storage/retrieval priority; CPU secondary), GS-D022 (missing observation is not inactivity) and GS-D023 (current/daily routine failure recovery) are LOCKED in the decision log, with domain requirements in STORAGE_SYNC_ROUTINE_LEARNING and P0_PRODUCT_REQUIREMENTS. The storage ExecPlan remains IMPLEMENTATION_DESIGN / PROPOSED: byte budgets, retention and new storage/backend formats are not locked. Prior host evidence remains TEST_EVIDENCE for primitives only. Checkpoint context revision: `2026-10-07.002` (advanced by GS-D024 below).

## Storage-density requirement and evidence — GS-D024

GS-D024 is LOCKED in [DECISION_LOG.md](DECISION_LOG.md), with canonical
domain requirements in [STORAGE_SYNC_ROUTINE_LEARNING.md](../architecture/STORAGE_SYNC_ROUTINE_LEARNING.md)
and [P0_PRODUCT_REQUIREMENTS.md](P0_PRODUCT_REQUIREMENTS.md). Eliminate
persistent redundancy and evaluate compact binary, bounded shared context,
delta/change, dictionary/reference and safe semantic aggregation before
increasing storage allocation. Independently recoverable restart points
are mandatory; all quality/retrieval/routine/caregiver invariants remain.
Context revision: `2026-10-07.003`. No exact record/outage/partition policy locked.

| Path | Classification | Valid scope / limits |
|---|---|---|
| `docs/exec-plans/evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md` and linked raw logs/CSV | TEST_EVIDENCE | Host numeric codec, synthetic binding/restart/byte-cut models, million-event bounded fixture, preserved sanitizer/regression and conditional trace accounting; no product retention or physical proof |
| `docs/exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md` sections22.10/22.11 | IMPLEMENTATION_DESIGN / PROPOSED | Corrects earlier numeric-only density planning with full-source/config/name/timing costs; full serializers/root/crypto/allocator/retirement/backend/rollback remain open |

Earlier density/retention figures remain valid for their stated uniform
numeric/historical budget comparisons, and cannot establish full-source
production retention. Sample/max-name timing scenarios and current blocker
status are recorded in [R1_WORK_STATE.md](R1_WORK_STATE.md). No competing
master requirements source or production format is introduced.


### Lifecycle-bound/reclamation evidence checkpoint

| Document | Authority | Valid use / limitations |
|---|---|---|
| `docs/exec-plans/evidence/R1_STORAGE_RETIREMENT_RECLAIM_PROOF_20261007.md` | TEST_EVIDENCE / DERIVED / HOST-MODELED | Source pending192 bound, unreported-history counterexample, proposed384-credit lemma, abstract COW cuts and NVS/raw capacity sensitivity; no product retention/partition/production proof authority |
| `docs/exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md` section23 | IMPLEMENTATION_DESIGN / PROPOSED | Qualifies old416-body/100KiB fixed ledger with conditional dedupe-only witnesses; progress/admission, allocator/crypto/rollback, backend and saturation remain open |

### Admission / physical storage evidence checkpoint

| Path | Classification | Authority boundary |
|---|---|---|
| `docs/exec-plans/evidence/R1_STORAGE_ADMISSION_RAWFLASH_PROOF_20261007.md` and linked logs | TEST_EVIDENCE / DERIVED / HOST-MODELED | Conditional6*(32+W) credit lemma, full-sector AES host crash models, installed SDK NVS fresh-image occupancy and raw physical accounting; no product W/C/overflow/offline/partition/backend approval or target qualification |

ExecPlan section24 refines section23's event-pool-only NVS sensitivity and
conservative independent raw bank allocation. Preserve prior source/codec facts;
whole fresh NVS packing does not establish runtime GC/peak progress. Context
revision remains2026-10-07.003; no new LOCKED decision or authority promotion.

### NVS runtime/saturation evidence checkpoint

| Path | Classification | Authority boundary |
|---|---|---|
| `docs/exec-plans/evidence/R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md` and linked raw logs | TEST_EVIDENCE / HOST-MEASURED | Installed-IDF Linux 128 KiB NVS churn, saturation, tail coexistence, selected fault cuts and write/erase counters for dummy length-matched objects; no product retention, authenticated whole-transaction, target RAM/wear or hardware claim |
| `docs/exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md` section25 | IMPLEMENTATION_DESIGN / PROPOSED | Replaces the fresh-image reserve assumption with a conditional physical admission/progress obligation; does not approve W/C, partition, backend or production integration |

GS-D013/014/015/017 remain OPEN and GS-D016/021/024 unchanged. The new
evidence does not alter canonical requirement authority or context version
`2026-10-07.003`; NVS is a candidate rather than an approved backend.
