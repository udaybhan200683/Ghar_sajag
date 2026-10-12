# Ghar Sajag Repository Operating Contract

This file is the always-on repository guidance for Codex. Keep it short. Longer requirements live in the canonical documents linked below.

## Permanent engineering Definition of Done — GS-116 / GS-130

Read the current GS-116 and GS-130 Jira policies and
`docs/validation/MASTER_VALIDATION.md` for every substantive feature/fix. Before
editing, record owning Jira, affected Node/Hub/application components and shared
interfaces, existing prior-feature suites, new positive/negative/recovery tests,
simulation/physical requirements and release impact. Follow the canonical source
and context rules below; historical validation-worktree instructions do not apply.

Permanently register new deterministic tests in the component registry. Run new
tests plus all prior affected-component regressions and impacted Node–Hub/API/PWA
contracts using `make validation-node`, `validation-hub`, `validation-contract`,
`validation-backend` and `validation-pwa`. Do not substitute focused PASS for these
suites. Node-only sleep changes require Node and relevant contract tests; GS-40
liveness changes also require Hub/backend/PWA coverage. Full browser validation
is required for affected browser behavior and every product release candidate,
not unconditionally for every isolated firmware developer loop.

Verify registration/execution and nonzero failure propagation. Run applicable
target builds/sanitizers. `make validation-fast` is the project deterministic gate;
every product release candidate must run actual `make release-gate-final`, which
includes all fast/component suites plus release builds, browser and quality gates.
Missing/zero tests, unexpected skips, stale artifacts, timeouts and incomplete
mandatory stages are failures. Record remaining failures honestly; never weaken
requirements or assertions to report PASS.

Software-delivered, physically qualified and release-approved are separate states.
Simulation/compilation does not prove GPIO/RF/current/storage/OTA behavior. Keep
required physical acceptance NOT_RUN/BLOCKED until real current-image evidence
passes or an explicit approved scope decision removes it. Hardware authorization
is still required. Record test commands/counts/exits/profile/source/evidence and
remaining gaps in canonical Markdown/Jira; GS-130 owns exhaustive feature mapping.
Commit validated changes, push normally, verify actual remote HEAD, preserve
unrelated assets and provide a precise next-task pause/resume handoff.

Development acceptance and release qualification are distinct (GS-116 comment10405).
For development, run affected Node/Hub suites, shared contracts, framework tests and
applicable builds/sanitizers. Do not unconditionally run validation-fast, complete
release-gate-final, unrelated backend or full browser suites. Verify release-stage
composition with lightweight framework tests. Execute complete product gates for a
genuine release candidate or explicit user request; otherwise record NOT_RUN,
deferred. Structural verification never establishes release PASS.

GS-130 keeps feature-level regressions and the portable C3/S3 board-stack E2E
simulation separate. Maintain `docs/validation/MASTER_TRACEABILITY.csv`, the
source inventory and physical catalogue when features change. Run affected
component suites and `make validation-board-e2e` for shared runtime/security/
durability/sleep changes; use verified receipts to avoid duplicate execution.
Run `make feature-coverage-test` for mapping integrity. A resolved source anchor
proves registration consistency, not exhaustive semantic coverage. Report feature
coverage, board-stack simulation, physical qualification and release approval
independently; keep explicit gaps and mandatory failing tests visible.
GS-130 physical-track comment10413 requires reuse/inventory of existing HIL,
not a second framework. Physical commands stay opt-in and outside software gates.
Legacy `hil-smoke`/regression campaigns build and flash; never invoke them as
non-destructive observation. Injected motion is not real AM312 optical evidence.
GS-108/114 require separately authorized, identified fixtures and image evidence.

GS-130 also owns the P0 product vertical target `make validation-p0-e2e`, which
joins the production C3/S3 host-stack event and CloudSync serializer to the real
local API/service and caregiver PWA where those contracts exist. This target is
registered through GS-116 for affected components and release composition; a
scenario assertion PASS with `product_status=PARTIAL` is still a gate FAIL.
The current local actor adapter is not OIDC and the unfinished GS-148 durable
Hub-commit API must remain an explicit product gap. `make validation-board-hil`
and `make validation-motion-hil` are separate opt-in physical commands. Their
default invocation records NOT_RUN without opening a port. Before any `--observe`
or `--run` use, obtain the user's explicit approval for the exact identified
fixture and test plan in the current task; the runner's typed phrase is a second
operator guard, not user approval. Do not treat a missing stimulus, image hash,
running-image identity or reset-safe serial path as PASS. Preserve existing
physical evidence and use unique evidence directories.

For every feature or product fix, require actually executed production-code unit/
component tests, deterministic production-code simulation, and focused trigger-
to-outcome E2E across affected components. Add permanent IDs and requirement,
source, gate and execution evidence to `MASTER_TRACEABILITY.csv`. Run the new
tests and all prior affected-component/contract regressions. If target behavior
requires hardware proof, classify it in `PHYSICAL_CLASS`, add/update its case in
`PHYSICAL_HIL_CATALOGUE.csv` and keep physical status NOT_RUN/BLOCKED until a
matched, authorized fixture run passes. Software gates never open ports or operate
boards. Full release validation must execute the release-only physical evidence
check; missing required evidence blocks release approval. Pure software features
remain SOFTWARE_ONLY and do not receive artificial HIL tests.

## Mandatory document precedence

The active source tree is organized under `code/` by product responsibility;
the former version-stamped source wrapper is historical and must not be used in
new paths. See [`docs/architecture/GS152_STABLE_REPOSITORY_LAYOUT.md`](docs/architecture/GS152_STABLE_REPOSITORY_LAYOUT.md)
for ownership boundaries and build-root conventions.

For substantive work, read these first:

1. `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md`
2. `docs/product/R1_RELEASE_CONTRACT.md`
3. `docs/product/R1_WORK_STATE.md`
4. `docs/product/CANONICAL_REQUIREMENTS_INDEX.md`

Then read only the domain documents relevant to the task. Trivial edits do not require the full reading sequence. Treat other `.md` files as supporting or historical unless the index marks them authoritative.

For substantive Ghar Sajag implementation, bug fixes, architecture/storage changes, PWA/backend behavior changes, or release qualification, **context preflight must PASS first**. Run `tools/context/ghar_sajag_context_preflight.sh` from the worktree. If it reports `STALE`, `INCOMPLETE`, or is absent, do not implement; report the mismatch and safe options. Never automatically reset, rebase, merge, stash, clean, or otherwise synchronize the worktree. Exempt only clearly safe trivial non-semantic edits such as spelling/comments.

When Ghar Sajag documents conflict, apply this exact authority order:

1. LOCKED decisions in `docs/product/DECISION_LOG.md`.
2. `docs/product/R1_RELEASE_CONTRACT.md`.
3. Current CANONICAL domain requirement/design documents identified by `docs/product/CANONICAL_REQUIREMENTS_INDEX.md`.
4. `docs/product/R1_WORK_STATE.md` for current implementation, qualification and blocker status.
5. SUPPORTING and IMPLEMENTATION_DESIGN documents.
6. TEST_PLAN and TEST_EVIDENCE, as validation/evidence rather than product-requirement authority.
7. HISTORICAL and SUPERSEDED documents.
8. Chat/session assumptions.

A lower-authority source never overrides a higher-authority requirement. Historical or implementation-design text can accurately describe current/old code without defining the current product requirement. Keep those statements distinct. For example, “the Hub currently has a 128-entry journal” can be a valid implementation fact; “R1 requires a fixed 128-event lifetime” is superseded by GS-D005 and GS-D016.

Supersede only the obsolete section/claim when the rest of a document remains useful. Record partial supersession in the canonical index with the valid uses, the no-longer-authoritative scope, replacement source and relevant decision IDs. Do not hide accurate implementation facts by classifying an entire design as obsolete.

If two current documents conflict and no higher-authority LOCKED decision resolves the conflict, classify it as `REQUIREMENT_CONFLICT`. Do not choose by timestamp, reading order, or intuition; do not invent product behavior. Stop product-semantic implementation, report the exact statements and sources, and request a product/user decision. Read-only investigation may continue if useful.

## R1 scope discipline

- R1 = commercially installable, stable fresh-install baseline.
- Preserve quality by reducing scope, not correctness, durability, security, or fail-closed behavior.
- Fix before R1 only for essential product failure, security/authentication failure, data loss/corruption, incorrect caregiver-visible behavior, inability to use fresh R1, or failure of a required release gate.
- Defer nonessential compatibility, polish, legacy migration, convenience tooling, and speculative future features.
- Never silently broaden R1.

## Do not deviate from R1

Before implementing any newly discovered issue outside the requested task:

Record this triage before implementation:

```text
BUG_CLASSIFICATION=R1_BLOCKER / R1_FIX / DEFER_POST_R1 / INVESTIGATE_ONLY / TEST_INFRA_ONLY
REQUIREMENT_SOURCE=<canonical path or REQUIREMENT_GAP>
DECISION_IDS=<GS-Dxxx IDs or NONE>
TASK_SCOPE=<requested and approved scope>
OUT_OF_SCOPE=<adjacent work explicitly excluded>
```

If product semantics are missing, classify `REQUIREMENT_GAP`; do not invent them. If `DEFER_POST_R1`, record it and do not implement during R1 work. If `R1_BLOCKER` or `R1_FIX`, explain the applicable release rule. Do not broaden scope merely because related code is nearby. Do not spend deep-model effort on non-R1 convenience problems while an R1 product blocker exists.

## Current hardware baseline

- GS-D030 selects ESP32-S3 N16R8 (16 MiB flash, 8 MiB PSRAM) for new R1 Hub development.
- Sensor Nodes remain ESP32-C3; preserve their protocol and BAT-C8 behavior.
- All new R1 target work, including ESP32-S3 Hub work, uses `/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`. Historical feature worktrees are provenance/evidence sources only; do not resume development there.
- Preserve the classic ESP32 target and evidence as historical sources; do not resume 4 MiB capacity optimization.
- Verify actual board flash, PSRAM and pinout before hardware bring-up; commercial partitions and capacity qualification remain open.

## Non-negotiable durability invariants

Do not weaken durable-before-ACK, authenticated ownership/domain checks, lost-ACK retry safety, duplicate suppression across reboot, Node retained-event retirement, current-format reboot recovery, fail-closed corruption handling, versioned storage/FOTA behavior, or bounded runtime behavior.

Do not erase/reset storage or use epoch reset to hide capacity defects.

## Data and cloud architecture

See `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`.

Key rule: when internet is available, the Hub synchronizes caregiver-relevant information to the backend continuously/near-real-time. It does not wait for local storage pressure and does not wait for the caregiver to open the PWA.

Local storage is primarily correctness-critical durability, offline buffering, short-term cache/history, and learned-state persistence. Long-term caregiver history belongs in the backend.

## Working-tree/evidence safety

- No destructive git operations (`reset --hard`, blind `clean`, blind stash/rebase).
- Preserve evidence.
- Do not rerun factory initialization unless specifically required.
- Do not fabricate hardware results.
- Do not repeat proven qualification steps unless a change invalidates them.

## Documentation maintenance

After substantial work that changes a requirement, design, architecture, release or validation status, blocker status, implementation scope, hardware decision, backend contract, or storage policy:

1. Update `docs/product/DECISION_LOG.md`.
2. Update `docs/product/R1_WORK_STATE.md`.
3. Update the relevant canonical requirement document.
4. Update `docs/product/CANONICAL_REQUIREMENTS_INDEX.md` if document authority changes.
5. Update other affected canonical domain documents.
6. For a newly approved LOCKED requirement/decision, increment `docs/product/CONTEXT_VERSION` and commit the canonical documentation before starting implementation that depends on it. Spelling-only and formatting-only changes do not increment the version.

Do not create another competing master requirements document.

## Canonical worktree source

The designated canonical R1 source is `/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`. The preflight script checks this source without modifying either worktree. If the canonical repository location or ref changes, update the script's two source constants and this paragraph; do not copy requirement text into worktree-specific configuration.

## Permanent single-worktree and pause/resume policy

R1 is developed sequentially in this one approved worktree and branch. Do not create another branch, worktree, clone or feature directory without explicit user approval. Keep one authoritative requirements index and `R1_WORK_STATE.md`; link topic designs and dated evidence instead of creating competing master documents.

Before substantive work, verify canonical path/branch/HEAD/status and remote, read applicable agent instructions, canonical requirements, current work state, latest Jira comments and the relevant handoff, then require context preflight PASS. Never infer that a newer branch contains all approved work; inspect commit ancestry and file-level differences before integration.

When work pauses, is interrupted or changes priority, update its existing canonical handoff and `R1_WORK_STATE.md`, and add a dated owning-Jira comment. Include current implementation/evidence, exact local and remote checkpoint, validation state, preserved uncommitted/untracked files, blockers, safety limits and the next exact action. Resume by reading the newest handoff and checking current source before continuing.

After validation, commit and push to `feature/r1-commercial-baseline`, verify `git ls-remote` equals local HEAD, and confirm tracked cleanliness while preserving generated/untracked files. Do not perform destructive Git or hardware operations without explicit authorization. Stop on unresolved product, security, protocol or storage-format conflicts; do not invent requirements.
