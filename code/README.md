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

## Fresh-checkout target builds

Install and activate ESP-IDF **6.0.3** with Espressif's supported setup for the
host platform. The paired target builder expects the activation script at
`$HOME/.espressif/v6.0.3/esp-idf/export.sh` by default; set `GS_IDF_EXPORT` if
the installation is elsewhere. From the repository root, run:

```bash
source "$HOME/.espressif/v6.0.3/esp-idf/export.sh"
python3 code/scripts/build_validation_targets.py
make gs114-s3-rpf-diagnostic-build
```

The paired builder creates fresh ignored output directories under
`code/build/validation_targets/` and compiles the C3 and S3 production
profiles. The GS-114 command creates a separate unique directory under
`code/build/gs114_fixture_pair/`, builds its paired C3 asset and fixture-profile
S3 diagnostic, and verifies the `gs_outbox`/`gs_state` partition profile plus
RPF00–RPF08 markers. ESP-IDF Component Manager resolves dependencies from the
tracked manifests and lockfile; generated `managed_components/` content stays
local. These commands compile and package only; they do not flash or access a
device.

For a P8 ACK-loss image that must embed the exact already-installed C3 app,
use the same builder in S3-only mode. It verifies the supplied Node image's
SHA-256, stages it under ESP-IDF's required `node_firmware.bin` name, skips the
C3 build, and checks the isolated ACK-drop profile and compiled S3 partition
table:

```bash
make -C code gs114-s3-c8-p8-build \
  GS114_C3_APP=build/gs114_fixture_pair/build-8rqa0oi5/c3/gs_hw_m1_node.bin \
  GS114_C3_SHA256=70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530
```

The P8 build produces only an S3 candidate app for later, separately authorized
installation; it does not open serial ports or flash hardware.
