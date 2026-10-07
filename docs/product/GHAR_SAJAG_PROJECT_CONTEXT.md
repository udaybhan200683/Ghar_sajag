# Ghar Sajag Project Context

Read this as the orientation for a fresh Codex session. Detailed requirements and designs remain in the documents linked by the [canonical index](CANONICAL_REQUIREMENTS_INDEX.md).

Before substantive implementation in any worktree, run `tools/context/ghar_sajag_context_preflight.sh` and require `PASS`. The canonical source is `/home/udaybhan/projects/Ghar_sajag_r1` at `feature/r1-commercial-baseline`; the machine-readable revision is in `CONTEXT_VERSION`. See `AGENTS.md` for version update and worktree safety rules.

## Product and release

Ghar Sajag is a home safety and wellbeing system for caregivers, with room sensor Nodes, a household Hub, a backend, and a caregiver PWA. The P0 concept is to detect relevant household activity and device health, support local routine/incident logic, and give caregivers useful, timely information.

R1 means a commercially installable, stable **fresh-install baseline**. Preserve quality by reducing scope, not correctness, security, or durability. Arbitrary migration from abandoned development formats is deferred unless it breaks the supported fresh-install path.

Current P0 household, sensor/event, caregiver, privacy and implementation boundaries are summarized in [P0_PRODUCT_REQUIREMENTS.md](P0_PRODUCT_REQUIREMENTS.md). It distinguishes application/domain behavior from physically established hardware behavior and marks unresolved semantics.

## Supported hardware and architecture

- R1 Hub baseline: existing 4 MB ESP32 Hub. ESP32-S3-N16R8 is not an R1 dependency unless explicitly approved.
- R1 Nodes: ESP32-C3. Six Nodes share Hub storage/resources.
- Nodes sense locally, retain/retry events, and retire them only after a valid application ACK.
- Hub authenticates/owns Nodes, processes events, runs local safety and bounded routine logic, commits before ACK, and buffers/synchronizes caregiver-relevant data.
- Backend owns long-term caregiver history and richer long-range analytics. The PWA is backend-first and should open on current backend data.

## Storage, connectivity, and learning

The Hub is not the long-term caregiver database. When internet is available it syncs continuously/near-real-time; upload does not wait for storage pressure or PWA open. During backend outage, local sensing, alerts, event durability, and routine learning continue. The PWA must show stale/offline status; backlog is uploaded after connectivity returns.

Separate correctness-critical journal/dedupe, materialized reducer/routine state, backend outbox, and short local history/cache. Reclaim or coalesce low-value history under pressure without stopping safety operation. Basic AI/routine learning runs locally using bounded state/aggregates; richer long-term analytics may run in the backend. Coalesce repeated PIR/raw chatter where semantics allow. Exact retention durations, offline guarantee, byte budgets, and pressure thresholds remain open.

Preserve authenticated ownership, durable-before-ACK, lost-ACK retry safety, duplicate suppression across reboot, Node retirement, current-format recovery, fail-closed corruption behavior, and versioned storage/FOTA behavior.

## Current state

Closed physical fresh-install durability gates include ownership/enrollment, Node runtime/rejoin, first durable commit, Hub reboot recovery, ACK class 0 and retirement, duplicate ACK safety, and lost-ACK/retry/duplicate qualification with empty final Node queues. Do not repeat those gates unless a later change can invalidate them. See [R1 work state](R1_WORK_STATE.md) for the latest record.

The current R1 product blocker is Hub storage/data-lifecycle architecture. A shared 128-event lifetime ceiling is unacceptable; merely increasing 128 is not a fix. Next design the lifecycle against the actual 4 MB Hub and six-Node case: active correctness journal/dedupe, materialized state, backend outbox, short history/cache, safe reclamation, offline capacity, flash wear, and OTA limits. Do not implement a guessed capacity or retention policy.

BAT-C8 is an R1-required feature with physical qualification pending (GS-D020). Qualification must prove required production sleep/wake/resume, sensing/runtime and radio restoration, safe fail-awake behavior, and event-processing regression safety. Final battery-life optimization and long-duration endurance are not blockers absent an explicit R1 battery-life claim. USB zero-touch automation is convenience tooling, not an R1 product blocker. See the index for other deferred work and qualification evidence.

## Scope rules

Before addressing an adjacent bug, classify it under `R1_RELEASE_CONTRACT.md`. Fix R1 blockers and required R1 fixes; document/defer post-R1 work; investigate uncertain product questions without silently choosing policy. Do not broaden scope because nearby code is convenient to change. Do not reopen completed gates without a reason tied to a later change.

## Read the detailed source

Start from [CANONICAL_REQUIREMENTS_INDEX.md](CANONICAL_REQUIREMENTS_INDEX.md) to find product/P0 requirements, R1 release rules, Hub/Node contracts, storage and security designs, cloud/PWA behavior, routine learning, battery, FOTA, hardware decisions, validation plans, and physical evidence. [DECISION_LOG.md](DECISION_LOG.md) holds locked/open decisions; [R1_WORK_STATE.md](R1_WORK_STATE.md) is the current execution handoff.

## Do not reopen without reason

- Passed fresh-install durability, lost-ACK, retry, duplicate, ACK-retirement, and reboot-recovery qualification.
- R1 hardware baseline (4 MB Hub and ESP32-C3 Nodes) or approved ownership/security invariants.
- The decision that 128 events is not an acceptable lifetime and cannot be fixed by increasing the constant alone.
- USB automation as a product requirement, development-era migration as an R1 requirement, or completed historical evidence.

## Next engineering priority

Close the storage/data-lifecycle design and its explicit product decisions before implementation. The exact retention and backend-outage policies remain open; derive a bounded design and byte/wear/OTA budget from actual hardware and six-Node behavior. Then host-test the design, build/measure the Hub target, and qualify only the changes that can invalidate existing physical gates.
