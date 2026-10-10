# Ghar Sajag Repository Operating Contract

This file is the always-on repository guidance for Codex. Keep it short. Longer requirements live in the canonical documents linked below.

## Mandatory document precedence

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
