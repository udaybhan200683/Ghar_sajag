# GS-152 Stable Repository Layout

**Status:** integrated into canonical R1; source restructuring and clean-checkout acceptance complete.
**Baseline:** `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`.
**Canonical integration:** fast-forwarded through GS-152 `d802485ee04227b6e1ca16810768e01f0da94009` after preserving newer canonical GS-114 commits.

## Why the layout changed

The active application was nested under the release-stamped directory
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`. That made source
ownership, build roots, tests and documentation paths depend on a release label.
GS-152 relocates that source tree to stable responsibility-based paths under
`code/`. The old wrapper is absent from the active tree. Release notes,
source-package notes and source-tree documentation were moved to
`docs/archive/source-release-v1.5.4/` and `docs/archive/source-tree-docs/`;
these archives retain their historical contents and provenance.

The exact 499-file old-path/new-path map, with pre-move SHA-256 for each tracked
file, is [`GS152_SOURCE_MOVE_MAP_20261011.csv`](../exec-plans/evidence/GS152_SOURCE_MOVE_MAP_20261011.csv).

## Responsibility boundaries

| Responsibility | Active location | Boundary |
|---|---|---|
| C3 Node | `code/firmware/node/` | Runtime, sensing, power, radio communication, storage and lifecycle are grouped by responsibility. |
| S3 Hub | `code/firmware/hub/` | Runtime, commissioning/registry, event processing, storage, CloudSync, routines and lifecycle are grouped by responsibility. |
| Shared firmware | `code/firmware/common/` | Protocol/transport, security and shared types have one owner; Node and Hub do not duplicate them. |
| Backend/API | `code/backend/ghar_sajag/` | Existing Python package remains cohesive to preserve its import and service boundaries. |
| Caregiver frontend | `code/frontend/` | Existing static PWA modules and package/build metadata are grouped together; existing feature/platform modules remain. |
| Tests | `code/tests/` | Test cases stay distinct from their production owners. Host-only adapters are under `tests/support/host/`. |
| Validation | `code/validation/` | GS-116 registry and executors have one active owner. |
| Engineering tools | `code/tools/` and repository `tools/` | Product build/simulation/HIL tools live under code; repository context tools remain at the root. |

## Firmware and build compatibility

ESP-IDF target project roots, target-specific `main/`, component directories,
partition tables, SDK defaults and generated component discovery remain under
`code/firmware/node/target/` and `code/firmware/hub/target/`. Portable source
groups were moved without changing target project roots. Their CMake source and
include paths now point to the functional owners under `firmware/node`,
`firmware/hub` and `firmware/common`.

The repository root Makefile delegates to `code/Makefile`; relative host source,
validation registry and artifact paths remain relative to the product source
root. The frontend package and Playwright configuration move together, and
browser runners execute with `code/frontend/` as their working directory. The
backend Python package path remains `code/backend/`.

Build outputs are generated beneath `code/build`, `code/evidence` and
`code/logs`. Baseline outputs created before the move were retained separately
at `code/{build,evidence,logs}/gs152-baseline-09bc8cd8b7baab06/`; these are not
post-migration validation evidence and must not be reused as build proof.

## Dependency rules and preserved behavior

- Node and Hub target compositions depend on their local firmware responsibility
  groups plus shared common interfaces.
- Shared protocol/security/data definitions have one source owner in
  `firmware/common/`.
- Backend and frontend remain separate application layers; neither is imported
  into firmware.
- Tests may use host adapters but do not replace production policy or transport
  modules.
- Validation metadata refers to source-relative paths under `code/`.
- No wire contract, security policy, event identity, persistent layout, retry
  behavior or product behavior was intentionally changed by this relocation.
- No target CMake project root, flash partition or storage format was moved.

## Migration and recovery

Moves were performed in the isolated GS-152 worktree, reviewed against the
499-entry source map, then integrated by a history-preserving merge of the
latest canonical R1 branch followed by a canonical fast-forward. The move map
lets reviewers verify original bytes. The merge retained newer GS-114
fixture-compatible S3 diagnostics, commissioning configuration, RPF00–RPF08,
and candidate partition profiles. It did not change storage format, security,
protocol or firmware behavior.

The integration commit and clean-checkout validation evidence are recorded in
[`GS152_RESTRUCTURE_BASELINE_20261011.md`](../exec-plans/evidence/GS152_RESTRUCTURE_BASELINE_20261011.md).
GS-152 made no hardware or release qualification claim. The historical Hub
journal migration assertion and P0 `product_status=PARTIAL` remain visible as
independent acceptance gaps.

## Retained boundaries

The Python backend remains a cohesive package rather than being split into
multiple packages, because that split would change import/API ownership beyond a
mechanical source relocation. The PWA keeps its existing `src/features` and
`src/platform` grouping. ESP-IDF target trees retain their required discovery
layout. These choices provide functional ownership without imposing mirrored
folders or a broad architecture rewrite.
