# Ghar Sajag R1 source tree

This directory is the active, stable source root for the Ghar Sajag R1 Node,
Hub, shared firmware, backend, caregiver frontend, tests, validation and
engineering tools. The former version-stamped source wrapper is no longer an
active source location; its release notes and source-tree documentation are
preserved under `docs/archive/`.

## Ownership map

| Responsibility | Location |
|---|---|
| ESP32-C3 Node | `firmware/node/` |
| ESP32-S3 Hub | `firmware/hub/` |
| Shared protocol, security and data types | `firmware/common/` |
| Backend/API | `backend/ghar_sajag/` |
| Caregiver PWA | `frontend/` |
| C++/Python/JavaScript and Playwright tests | `tests/` |
| Host and board-stack validation | `validation/` |
| HIL, simulation, factory and build tools | `tools/` |
| Host build outputs | `build/`, `evidence/`, `logs/` (generated/ignored) |

Firmware functional directories express ownership while target-specific ESP-IDF
project roots, `main/`, `components/`, partition tables and CMake discovery
boundaries remain in `firmware/node/target/` and `firmware/hub/target/`.

## Development commands

Run commands from the repository root; the root Makefile delegates to this
source root:

```bash
make validation-node
make validation-hub
make validation-contract
make validation-board-e2e
make p0-product-e2e
```

The component registry lives at `validation/suites.json`. Physical HIL targets
remain opt-in and are not part of host component validation. Use the current
canonical instructions in `AGENTS.md` and `docs/validation/MASTER_VALIDATION.md`
before selecting a gate. Target firmware projects are built from their retained
ESP-IDF roots under `firmware/*/target/`; see the build scripts in `scripts/`.

The source ownership and relocation rationale are recorded in
[`docs/architecture/GS152_STABLE_REPOSITORY_LAYOUT.md`](../docs/architecture/GS152_STABLE_REPOSITORY_LAYOUT.md).
