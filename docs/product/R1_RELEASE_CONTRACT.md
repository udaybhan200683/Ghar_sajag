# Ghar Sajag R1 Release Contract

## Objective

Ship a commercially installable, stable fresh-install R1 quickly without weakening security, durability, correctness, or caregiver-visible behavior.

> Preserve quality by reducing scope, not standards.

## Supported baseline

R1 supports freshly installed Hub/Nodes using the current approved persistent format.

Arbitrary migration from abandoned development-era formats is post-R1 unless it blocks the supported fresh-install path.

## Pre-R1 fix rule

A defect is an R1 blocker only if it causes:
1. essential product functionality failure;
2. security/authentication failure;
3. data loss/corruption;
4. incorrect/unsafe caregiver-visible behavior;
5. inability to use the supported fresh R1 system;
6. failure of a required R1 gate.

Everything else normally moves to backlog/post-R1.

## Bug and scope triage contract

Before acting on every newly discovered bug, classify it as exactly one of:

- `R1_BLOCKER` — prevents a supported fresh R1 installation or a required release gate, or causes essential product failure, security/authentication failure, data loss/corruption, invalid durability, unsafe/incorrect caregiver-visible behavior, or commercial instability.
- `R1_FIX` — within R1 scope and must be corrected before release, but does not meet the blocker threshold above.
- `DEFER_POST_R1` — legacy/dev-format migration only, convenience tooling, diagnostic polish, nonessential optimization, unsupported configuration, future/P1/P2 work, cosmetic cleanup, or speculative refactor.
- `INVESTIGATE_ONLY` — evidence is insufficient to classify implementation scope; investigate and report without changing product behavior.
- `TEST_INFRA_ONLY` — a validation/tooling defect that does not itself change product behavior; keep the change limited to test infrastructure.

State the classification before implementing a newly discovered adjacent bug when it would broaden the requested work. For `R1_BLOCKER` or `R1_FIX`, explain the applicable release rule. For `DEFER_POST_R1`, record it for later and do not implement it as part of the current task. Do not infer a product decision from an implementation convenience.

Before implementing an adjacent or unrequested issue, record:

```text
BUG_CLASSIFICATION=R1_BLOCKER / R1_FIX / DEFER_POST_R1 / INVESTIGATE_ONLY / TEST_INFRA_ONLY
REQUIREMENT_SOURCE=<canonical path or REQUIREMENT_GAP>
DECISION_IDS=<GS-Dxxx IDs or NONE>
TASK_SCOPE=<requested and approved scope>
OUT_OF_SCOPE=<adjacent work explicitly excluded>
```

If product semantics are missing, report `REQUIREMENT_GAP` and do not invent behavior. If two current requirements conflict without a resolving locked decision, report `REQUIREMENT_CONFLICT`, stop product-semantic implementation, and request a product decision. A test-plan title or pending test does not by itself establish product scope or a mandatory release gate; that gate must be identified by a locked decision or this contract.

## Non-negotiable invariants

Preserve:
- authenticated Node/Hub ownership;
- durable-before-ACK;
- retry/duplicate protection;
- lost-ACK safety;
- Node retirement of acknowledged retained events;
- reboot recovery of current-format state;
- fail-closed corruption handling;
- bounded CPU/memory/watchdog behavior;
- versioned storage/FOTA behavior;
- no silent erase/reset as recovery policy.

## Hardware scope

- Hub: existing 4 MB target.
- Nodes: ESP32-C3.
- ESP32-S3-N16R8 migration is not R1 unless explicitly approved.
- First prove whether approved R1 behavior fits safely on 4 MB.

## BAT-C8 required feature and qualification

BAT-C8 production-critical power behavior is an R1-required feature with physical qualification pending (GS-D020). Qualification must cover intended production sleep entry, required GPIO/timer wake, bounded wake/resume, sensing/runtime and radio restoration, safe fail-awake behavior, and required event-processing regressions. Final battery-life optimization and long-duration endurance are not R1 blockers unless the product makes an explicit battery-life claim. See the battery guide and BAT-C8 qualification plan for test details; do not infer product scope from test case labels.

## Current storage blocker

The historical shared Hub journal has a finite append-only lifetime. This is not commercially acceptable.

Do not fix it by simply increasing 128.

The design must separate/reconcile:
- correctness-critical durability/dedupe;
- materialized/recoverable reducer/routine state;
- backend-sync backlog;
- short-term event/history retention;
- safe reclamation.

## Cloud/backend scope

Cloud/backend sync is part of the product path because the caregiver PWA should see fresh information without waiting for dashboard-open synchronization.

But cloud availability must not be required for local sensing, alerts, or routine learning.

## Basic AI / routine learning

R1 may include bounded, transparent statistical routine learning/baseline/trend logic using fixed-size state and aggregates.

Do not introduce heavyweight ML infrastructure merely because the feature is called AI.

Current P0 behavior and implementation boundaries are summarized in `docs/product/P0_PRODUCT_REQUIREMENTS.md`. It distinguishes domain/application behavior from physical qualification and names unresolved semantics; domain guides retain detailed behavior.

## Approved storage and Node design direction — GS-D025–028

R1 targets 72 hours of internet-only outage resilience with powered Hub/Nodes
and functional local connectivity. Local monitoring and routine learning continue,
essential safety evidence and observation coverage stay durable, and pending
information synchronizes when the backend returns. This design target is not an
unconditional qualified capacity guarantee; supported volume and critical
saturation remain OPEN.

Eligible ordinary PIR history may be grouped without losing required routine,
inactivity or timely safety evidence. Important door transitions, user actions
and safety events remain exact; NO_OBSERVATION is never NO_ACTIVITY. Existing
durability/retry/deduplication/recovery and durable backend acceptance requirements
remain mandatory. Encoding, intervals, quiet gap, progress cadence and backend
summary contract remain unapproved.

ESP32-C3 Nodes are battery-operated. Prefer meaningful-observation processing
and avoid unnecessary wake-ups, Wi-Fi transmissions and flash writes. Do not add
40–120-second periodic wake-ups for activity consolidation. Sensor-specific
interpretation/episode tracking may be local; household/cross-sensor decisions
stay at Hub. Any new Node protocol must prove battery and correctness impact
before implementation. GS-D020 BAT-C8 requirements and pending qualification
status are unchanged; this does not establish a battery-life claim.

Door OPEN/CLOSE remain individually identifiable. Future bed occupancy sessions
may track START/END/duration at Node, but bed sensing is excluded from R1 and is
not proof of sleep or identity. Existing 4 MB Hub/ESP32-C3 hardware scope stays
in force. Final critical classes/reserves, NORMAL/HIGH/STRESS guaranteed bounds,
NVS partition and ESP32-S3 upgrade are not approved. Requirement approval does
not close technical proof gates or authorize production integration in this task.

## Release discipline

Do not rerun passed physical gates unless a later change can invalidate them.

Use host tests first for new storage/lifetime architecture, then target build/size checks, then physical qualification.
