# GS-95 Phase-2 source consolidation and retirement

Date: 2026-10-15

Canonical: `/home/udaybhan/projects/Ghar_sajag_r1`, `feature/r1-commercial-baseline`
Historical: `/home/udaybhan/projects/Ghar_sajag_phase2`, `feature/hw-m1-4-hil-phase2`

## Decision and scope

The 11 Phase-2-only commits were reconciled against current canonical source. No
required production implementation or regression remains exclusively in the
historical worktree. The one credible source defect, the C3 rollback validator's
3,072-byte task stack, was addressed provisionally in canonical commit
`aab00e895e9a130c6c9b31b07e6ece11815f4f6c`; the GS-118 evidence and
handoff followed in `78c2ded81acc465c9bf5e561b0f2d4e2843c293f`.
The 12,288-byte stack is **not a physically measured minimum**. No Phase-2
history-only merge, cherry-pick, production change, firmware installation or
physical test was performed for this GS-95 retirement.

The ESP32-C3 Node remains a 4 MiB flash target. Only the Hub development
baseline moved to ESP32-S3 N16R8, with 16 MiB flash and 8 MiB PSRAM (GS-D030).
The classic ESP32 Hub HIL results and 128-entry journal are historical, not
current S3 qualification or storage policy. GS-D029 still requires automatic
signed-FOTA application rollback and safe storage recovery.

At the pre-retirement check, canonical local and actual GitHub HEAD both equal
`78c2ded81acc465c9bf5e561b0f2d4e2843c293f`. Phase-2 local and GitHub
HEAD both equal `8f053b45b1c6b8ec772565336582c7e63a68a6a6`; merge base is
`a991c8820c3abd1e79cd9549bd1385daa8124b30`. There are 11 Phase-2-only
and 228 canonical-only commits. The historical tracked tree is clean; its
untracked and ignored generated files are covered by the full backup below.
Canonical tracked files were clean before this document was created. Existing
untracked PWA assets, S3 managed components and GS-114 evidence are unrelated
and preserved.

## Eleven-commit disposition

`COVERED` means equivalent current source and regression protection, not Git
ancestry or physical qualification. Every historical SHA remains recoverable
from the bundle below.

| Historical commit | Jira / historical purpose | Canonical counterpart and regression | Disposition / remaining qualification |
|---|---|---|---|
| `480ec95a781b89f5139de9bd39bd9b4b0e0174ee` | GS-118/67; signed C3 failed-health rollback and fixture | `code/firmware/node/target/esp32c3/idf/main/fota_receiver.cpp`, `code/tools/hil/secure_signed_fota.py`, `code/tests/python/test_secure_signed_fota_fixture.py`; current signed-FOTA image, session, EventKey, ACK and panic assertions | PARTIAL physical evidence: source/test gap remediated; 2026-09-27 rollback was a stack panic and its initial PASS was invalid. Current S3+C3 physical rollback remains NOT_QUALIFIED. |
| `b6d04ad1ee1de0735554dae879dd607d6d8253b7` | GS-118; authenticated FOTA progress with interleaved application ACK | Existing authenticated ACK handling and `test_interleaved_begin_line_uses_authenticated_begin_ack_fallback` in signed-FOTA fixture tests | COVERED; no parallel protocol path. |
| `10f6af7c708c1506580118203fa8c348b849289b` | GS-118; enlarge rollback validator stack after panic | `kImageValidationTaskStackBytes = 12U * 1024U` and `test_rollback_stack_stays_at_conservative_bytes_value` | COVERED provisionally in `aab00e8`; high-water and heap margin remain physical GS-118 work. |
| `97b3546f18b150007af7ae706634b14749f1ba4a` | GS-118; correct misleading old rollback qualification record | Raw backup logs/results plus [GS-118 reconciliation](GS118_PHASE2_ROLLBACK_RECONCILIATION_20261015.md) | EVIDENCE_ONLY; old rollback PASS is invalid. |
| `08b698bc203293d7e7e548df91192cf738fb42c3` | GS-108/148; classic ESP32 fixed-journal restart HIL | S3 durable outbox/checkpoint/replay source, `code/tests/cpp/board_stack_e2e_validation.cpp` and Hub persistence/outbox tests | OBSOLETE implementation; historical classic-board evidence retained, current S3 physical durability open. |
| `8f9de2ab01b67a4b2acdd86dd331845ddfc96111` | GS-118; tolerate truncated UART reset line | Current signed-FOTA fixture checks fresh boot/session and fails closed without recovery proof; fixture tests cover stale-session rejection | COVERED by stricter current evidence rules; no broad acceptance of truncated lines. |
| `79d53107467460f0598b98170b4a7711b2a81aa7` | GS-108/118; live C3 pre-restart probe in old fixture | Current `code/tools/hil/phase1.py`, `qualify.py`, `secure_signed_fota.py`; historical probe kept in bundle | DEFERRED tooling convenience; not an R1 source or mandatory regression gap. Physical fixture plan must approve current-board controls. |
| `441643f8274d6287bfe01d5ff3bb889e9b099f1c` | GS-96/150; authenticated rejoin after Hub outage | `code/firmware/node/target/esp32c3/node_runtime_adapter.cpp`, Node session recovery and `code/tests/cpp/board_stack_e2e_validation.cpp`, `multinode_host_validation.cpp` | COVERED; current rejoin preserves retained EventKey while rejecting stale transport sessions. |
| `b131894bb15ab5ac1321ce050d1679b14af23458` | GS-108; verified identity reuse in HIL preflight | Existing `code/tools/hil/phase1.py`, `qualify.py` and supervisor tests; no second HIL framework | COVERED for historical fixture; current S3-compatible physical preflight still requires approval. |
| `9bd131ebcc9bd7d1c625c7f910f6221616987f65` | GS-108; verified identity reuse during supervised campaign | Same canonical HIL supervisor and identity/rejoin fixture tests | COVERED for historical workflow; not current S3 physical qualification. |
| `8f053b45b1c6b8ec772565336582c7e63a68a6a6` | GS-108/148; classic Hub journal restart qualification report | Preserved document and raw backup; modern S3 persistence, outbox and board-stack validation are separate | EVIDENCE_ONLY; classic result does not qualify S3. |

Current canonical security/identity, signed C3 image validation, boot-health,
authenticated rejoin, exact EventKey retry/ACK retirement, S3 durable outbox,
replay, and fault rejection are already owned by their current modules. Neither
the old fixed journal, 60-second health default, old power/retry workaround nor
versioned source wrapper is imported. Git ancestry remains intentionally
different; the owner authorized deletion of historical refs with a recoverable
bundle.

## Backup and recoverability gate

The complete historical worktree, excluding only its `.git` administrative
pointer, and a complete Git bundle are retained at
`/home/udaybhan/projects/phase2_evidence_backup_20261015T101912Z`.
The 2026-10-15 full recheck compared **57,145 entries** (36,903 files and
20,242 directories) against both source and manifest, including every file
SHA-256 and all relative paths. Manifest file bytes total **5,578,823,672**.
No missing, extra or changed file content was found. Source and backup file
modes matched except one intentional security tightening:
`config/hil.local.env` is mode 0644 at the source and mode 0600 in the backup;
its 838 bytes and SHA-256 match the manifest. The backup root is mode 0700.
There were no symlink mismatches. This restriction preserves the sensitive
configuration without widening access. No credentials or signing-key contents
are printed or committed.

The manifest SHA-256 is
`a6efe6e11631eff1a53a8849172f38d4745ffd7e375ba6aa6b15143412f91295`.
`phase2-history.bundle` SHA-256 is
`e30814f73a9932846f16805ff0efa8b52c4e964cfb4b716ce1e08f743d0c9712`.
`git bundle verify` reports a complete history and
`refs/heads/feature/hw-m1-4-hil-phase2` at `8f053b45b1c6b8ec772565336582c7e63a68a6a6`.
Recovery can use this bundle as a Git source after verifying its hash; restore
files from `worktree/` using the manifest to check content. The raw September 27
`c3_serial.log` retains the stack-protection panic while the original
`summary.md` and `test_results.json` retain the misleading PASS for provenance.
The corrected fixture, reports, image artifacts, build outputs and ignored
local configuration are also preserved.

An earlier GS-118 tool invocation regenerated an ignored C3 target-root
`sdkconfig`. Its prior bytes were not captured and cannot be certified backed
up. The current regenerated version is retained separately under
`/home/udaybhan/projects/gs118_config_backup_20261015T103900Z/` and the
current historical worktree contents match the full backup. Do not describe
the unavailable older `sdkconfig` as recovered.

## Validation and development independence

Current-source focused checks on 2026-10-15:

| Command/check | Result | Limit |
|---|---|---|
| `python3 -m unittest discover -s tests/python -p test_secure_signed_fota_fixture.py -v` in `code/` | PASS 20/20 | Fixture assertions only. |
| `make feature-coverage-test` in `code/` | PASS 22/22; 202 features, 210 modules, 15 physical cases | Mapping integrity only. |
| `make -n fota-host-test hub-fota-guard-host-test node-recovery-host-test validation-framework-test` | PASS; targets available | Dry run, not execution. |
| Search of executable `code/` source, build, validation, tooling and app paths for `Ghar_sajag_phase2` or the old branch | No executable dependency found | Historical documents remain provenance. |
| `git bundle verify`; full path/content/metadata comparison | PASS with documented one-file permission tightening | Backup validation, no physical claim. |

The current GS-118 source is unchanged since `aab00e8`; the intervening commit
only changed documentation. Prior GS-118 receipts at that source show C3
production and explicit HIL injection target builds PASS with ESP-IDF 6.0.3,
board-stack E2E 10 groups PASS, framework 46/46 PASS and physical-catalogue
structure 99 PASS. A signed-profile build remains BLOCKED for lack of approved
test signing configuration/material. No target build or physical operation was
repeated for this documentation-only task.

Normal Node/Hub development targets, backend/PWA paths and release registrations
remain in canonical `code/`, independent of the Phase-2 directory. The forced
boot-health failure option remains OFF by default and CMake rejects production
combinations; ordinary builds do not require this injection or signing material.
The signed HIL supervisor still uses the old classic-ESP32 Hub, so a current
S3+C3 physical rollback campaign needs an approved S3-compatible control/profile
or alternate fixture. This gap does not stop unrelated canonical development.

The prior aggregate `validation-node`/`validation-contract` failures from P0
`product_status=PARTIAL`, and `validation-hub` failure from Hub journal
migration plus P0 PARTIAL, remain open. They are release failures, not new
GS-95 regressions. `release-gate-final` and physical HIL were not run.
GS-118 signed rollback, GS-108 broad S3 HIL and GS-96 multi-node physical
qualification remain **NOT_QUALIFIED**; GS-67 FOTA requalification remains open.

## Pre-retirement gate and next action

No open GitHub PR references the Phase-2 branch. At this check no active
Git/IDF/HIL process or process with its current directory in the historical
worktree was found. Other Codex processes alone were not treated as writers;
tracked canonical content, active Git operations and remote refs were checked.
The required source and tests are canonical, the bundle is recoverable, and
the full backup covers local evidence. Recheck refs, source inventory and
process use immediately before removal. Then remove only the registered
Phase-2 worktree, delete only its local and guarded remote branch, and append
the exact receipts below. Stop if any gate changes.

## Final retirement receipts

PENDING — this report is prepared before any destructive operation. The final
receipt is appended only after each operation and post-removal checks succeed.
