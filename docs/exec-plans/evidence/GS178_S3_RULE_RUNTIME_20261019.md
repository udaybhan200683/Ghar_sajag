# GS-178 S3 rule-runtime integration — 2026-10-19

## Outcome

The deterministic Hub rule-decision path is now part of the S3 product runtime
source. `HubRuntime` owns bounded pending rule-decision publication intents;
their identity is independent of Node `EventKey`. Checkpoint v3 persists rule
state and publication intents together while preserving v1/v2 decode. Replayed
admitted events reconstruct the same decision identity across the checkpoint
cut. The S3 adapter feeds the existing CloudSync worker from this runtime state
and retires a local intent only after the matching backend `COMMITTED` receipt
has been checkpointed. No synthetic Node event or changed Node ACK/retirement
rule was introduced.

The target rule scheduler is gated by authenticated current Hub/Home/epoch
authority and trusted time. It derives the local-minute input from the trusted
UTC provider and the authenticated configured timezone. The TEST_ONLY adapter
accepts `Etc/UTC` and `Asia/Kolkata` (fixed UTC+05:30, no DST); other timezone
identifiers fail closed. Missing/invalid time,
authority, or observation coverage suppresses time-dependent inactivity/night
conclusions. This is deterministic existing R1 rule behavior; GS-104 R01–R09
personalized learning remains on hold.

The GS-178 host scenario now uses the production `HubRuntime` checkpoint and
decision/outbox path with the existing CloudSync worker and backend projection.
The S3 source composition also builds under the explicit GS-40 TEST_ONLY profile.
This proves source composition and compilation, not execution on an ESP32-S3.

## Source and artifact binding

- Branch: `feature/r1-commercial-baseline`.
- Runtime implementation commit: `487ffa03e2cc95d84a8eafa5a51016fe413cdce7`.
- Repository tree: `85d876f270511f97609087795113014472617fb0`.
- `code/` source subtree: `d81f65099f469eb7c7f32a32a24bc9dfa6dad8d8`.
- Validation source fingerprint: `8ff6341d2481f3ea7bf59de7f0d1f2256a9cad3cd73ccbd35996f7b63f96fb97`.
- ESP-IDF: v6.0.3; esptool: v5.4.0.

The source-bound TEST_ONLY S3 product image is at
`code/build/validation_targets/gs178-testonly-487ffa0-ds-off/s3/gs_r1_s3_hub.bin`.
The currently present artifact is 2,238,400 bytes, full-file SHA-256
`54f8fcda7b28cf59cdefa085182755023ea919995007ddeb095fe914d17bb3d5`, and ESP
image validation hash
`c848184ffaede7087af04924a48003837079c6c77af0435561305205669b69ee`.
`esptool image-info` reports ESP32-S3, 16 MiB flash, valid checksum and valid
image hash. App version is `487ffa0-gs178-testonly`.

The effective SDK configuration SHA-256 is
`8bff1b0e2cb4ff7f109e22a4962ef9d6e79ba50da42e44e9316bf14093b8f9fa`; the
build-local defaults SHA-256 is
`170810126035e042107c83f11a1df6ff9bd76affed030339b705d591a9d38648`. The
build cache selects `GS40_TEST_ONLY_CLOUDSYNC=ON`; compile commands define
`GS40_TEST_ONLY_CLOUDSYNC_BUILD=1`, and the effective config leaves the DS
peripheral unset. The isolated profile's recorded profile digest is
`a43fd105784a9c8f6e6f822137ea226bbeb65459b0f980806572e5d1bebbdb6b`.

The external public config-root DER is 1,097 bytes, SHA-256
`fe7d71fbe68797fe6fcd28e4364e9cd161005f15befeef4be78b19e0ce355fb0`. The
same bytes were found in the image, and the linked ELF contains the expected
`_binary_gs40_test_config_root_der_start/end` symbols. The associated ephemeral
private key was not embedded or committed. This is TEST_ONLY public trust
material, not a production root or credential.

The image fits the configured 4 MiB OTA application slot. The generated
partition table is 3,072 bytes (SHA-256
`4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe`); the
source table is `partitions.development.csv`, SHA-256
`9da4b591a461c8b251e3ced8107d3ff3bc4a5fe4fd8844670ba4d90163d3ea29`.
Its paired embedded C3 asset is 937,536 bytes, SHA-256
`6d50849ae9238f34bbafe8b92b1a5de252692ae0eb1a0639b8e89c5eab9f17f7`.

An earlier execution note recorded a different full-file digest for this
build directory. On resume, the on-disk binary was rehashed and its ESP image
metadata revalidated. The value above supersedes the earlier full-file digest;
the reason for the byte-level difference was not established. Use only the
digest of the exact artifact captured for a future installation. No board was
accessed and no image was installed.

The paired standard production C3/S3 non-flashing build also passed on this
source. The S3 application is 2,184,704 bytes, SHA-256
`b29979ac979bc97040c3f941957fc052e17fb4322c3733e9cb36e9ccb3fd09bf`; its OTA
slot is 4,194,304 bytes. Its image-validation hash is
`93bbbb16b244966c2b8119ba46ca7ec18cea8d04981db55b17388a612daa8039`; its
effective SDK configuration SHA-256 is
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. It has
build guard `GS40_TEST_ONLY_CLOUDSYNC_BUILD=0`, DS peripheral enabled, and the
linked ELF selects `UnprovisionedS3CloudTrust` without TEST_ONLY runtime,
bootstrap or root symbols. It remains fail-closed/unprovisioned; this compile
result does not establish commercial credential readiness.

## Validation record

| Command / stage | Result |
|---|---|
| `make -C code gs178-software-e2e` | PASS, 27/27 software E2E tests. |
| `make hub-runtime-checkpoint-host-test` (registered Hub checkpoint stage) | PASS, 2 assertion groups, including decision-intent crash replay and configured activity checkpoint extension. |
| `make -C code validation-hub` | Aggregate FAIL: checkpoint passed; existing journal migration assertion `clean migration commits` failed (exit 2, count 0); required P0 gate failed with `product_status=PARTIAL` (26 scenario checks recorded). |
| `make -C code validation-contract` | Aggregate FAIL because the required P0 product status remains PARTIAL (26 scenario checks recorded). |
| Registered board-stack E2E stage | PASS, 10 scenarios. |
| Registered CloudSync/mTLS, backend worker integration, storage correctness and storage sanitizers | PASS in the Hub/contract executions. |
| `make -C code validation-framework-test` | PASS, 51/51 framework assertions. |
| `make -C code feature-coverage-test` | PASS, 22/22 mapping tests; consistency reports 215 features, 255 source modules and 25 physical cases. |
| ESP-IDF 6.0.3 paired C3/S3 production build (`python3 code/scripts/build_validation_targets.py`) | PASS, no flashing. |
| ESP-IDF 6.0.3 S3 TEST_ONLY product profile (`idf.py ... build size`) | PASS, no flashing; app image fits 4 MiB OTA slot. |
| `git diff --check` | PASS after the documentation and registry edits. |

The Hub and contract aggregate failures remain visible. Scenario assertions do
not convert `product_status=PARTIAL` to PASS, and the historical migration
failure was not suppressed or rewritten. Report JSON is retained at
`code/evidence/validation_framework/hub-1792411484051464659/report.json` and
`code/evidence/validation_framework/contract-1792412698542485199/report.json`.
Those reports bind the executed stages to source fingerprint
`8ff6341d2481f3ea7bf59de7f0d1f2256a9cad3cd73ccbd35996f7b63f96fb97` and the
pre-commit source HEAD they recorded; the equivalent code is now committed in
`487ffa03e2cc95d84a8eafa5a51016fe413cdce7`.

The first combined framework/mapping command reported all 51 framework tests
passing but exited 2 when the new trace row's exact command and component gate
fields disagreed with the registry. The row was corrected to match the
registered `checkpoint` and `gs178-node-caregiver-e2e` stages; the standalone
feature-coverage rerun then passed 22/22. The initial mismatch was not hidden.

## Status and remaining qualification

- S3 rule/checkpoint/scheduling source integration: implemented and host-tested;
  TEST_ONLY and commercial target profiles compile.
- Hub rule decision to backend/caregiver software path: PASS in the registered
  host E2E; no target network execution is claimed.
- Physical S3 rule scheduler, checkpoint persistence, flash/OTA behavior and
  caregiver end-to-end on current installed images: NOT_RUN.
- GS-40/GS-117/GS-121 physical acceptance: NOT_RUN; exact separately authorized
  matched fixtures and source/image/session evidence are still required.
- Release approval: NOT granted. P0 status remains PARTIAL.
- GS-104 R01–R09 remains on approval hold.
- Hub journal migration assertion remains an open failure.
- Physical hardware, production credentials/endpoints and eFuses were not
  accessed or changed.

## Current P0 readiness and build provenance — 2026-10-19

This section supersedes the earlier note above that called the image digest
change unexplained. The source-bound checkpoint is commit
`cc7d6ab32c756219320777f8afe1592e5a962337`, tree
`75d631cf1b1303dc6b773fe284888da4f42321f9`. Earlier `2,238,400`-byte image
`54f8fcda...` was built from source `487ffa03` with a different effective
configuration; it is not the artifact for this checkpoint.

The current guarded TEST_ONLY S3 product image is 2,233,392 bytes, full binary
SHA-256
`da3b28c54dd9e06e88b25b12a96c0f9fa3f2d80c07c190b6a6fadfa41e2eb1c6`, ESP
validation digest
`294bd9e668ad71870c212a59b030267708d8238e43ed0a63133c3bfa8fde1761`, and
effective sdkconfig SHA-256
`3750bc9360e4524d61d8209e2cbe7014f67be9ee55dcb553033bcc9858c83099`. It fits
the 4 MiB OTA slot. The profile has
`GS40_TEST_ONLY_CLOUDSYNC=ON`, `GS_HIL_BUILD=OFF`, DS peripheral disabled, and
build-time secure boot/flash-encryption options unset. Its 1,097-byte external
TEST_ONLY public config root is SHA-256
`fe7d71fbe68797fe6fcd28e4364e9cd161005f15befeef4be78b19e0ce355fb0`; the
binary contains those exact bytes once. The paired C3 asset is SHA-256
`384eb4f5b194fb02d3d49044f952d3d7fbb2a01f14ca29d63ea17d06d3aea37d`. The
artifact was built with ESP-IDF 6.0.3 and was not installed or run on a board.

The paired standard production C3/S3 build on the same source passed with
`GS_HIL_BUILD=OFF`; the S3 has `GS40_TEST_ONLY_CLOUDSYNC=OFF`, DS peripheral
enabled and only `UnprovisionedS3CloudTrust` linked. Its report is
`code/build/validation_targets/gs116-a1ppl5pl/report.json`; S3 is 2,184,704
bytes, SHA-256
`f10393df9bafb78bb419fc8d8be9fb564434e2f93fcfa7323414877bc7b7378c`, in the
4 MiB slot. The paired production C3 image is 937,536 bytes, SHA-256
`384eb4f5b194fb02d3d49044f952d3d7fbb2a01f14ca29d63ea17d06d3aea37d`.

For the TEST_ONLY target, `SOURCE_DATE_EPOCH=1792429200` fixed the app compile
date. A clean rebuild in the same absolute build directory reproduced both
the full BIN and ELF byte-for-byte (ELF SHA-256
`1d07ef7be54055fdf86b015132a0ebd22224f0db7da758e39945b56dedb848ed`). Builds
from separate absolute paths differed only in the app descriptor's embedded
ELF SHA-256 (32 bytes) and dependent image footer (33 bytes). This is
path-sensitive ELF metadata; no content variation was observed in the other
image bytes. Reproducibility is confirmed for a stable path and pinned date,
not across arbitrary build paths.

Focused current-source evidence: `make -C code gs40-test-only-bootstrap-test`
passed 47 checks on `94591ab` (the later `cc7d6ab` commit changes only the PWA
cache profile); `make -C code gs178-software-e2e` passed 27/27 and
`make -C code hub-runtime-checkpoint-host-test` passed two assertion groups on
the rule/time source. After the cache-v5 correction,
`python3 code/tools/performance/profile_pwa.py` passed at 62,513 bytes,
`pwa-68-browser-test` passed 3 tests / 92 assertions, and the Phase 3A
desktop/mobile regression passed 8/8 including stale-cache eviction.
`make -C code validation-framework-test` passed 51/51 and the corrected
`make -C code feature-coverage-test` passed 22/22 mapping tests, reporting 215
features, 255 modules and 25 physical cases.

The single `make -C code validation-hub` execution on `94591ab` completed in
833.586 seconds. Its affected implementation stages passed, while the
aggregate remains FAIL on the existing `clean migration commits` assertion
and required P0 gate (`product_status=PARTIAL`; scenario assertions 26/26).
The P0 matrix at
[`GS178_P0_SOFTWARE_READINESS_MATRIX_20261019.md`](GS178_P0_SOFTWARE_READINESS_MATRIX_20261019.md)
classifies all 17 use cases PARTIAL and links implementation, evidence and
gaps. No release gate, physical case, phone, production service or hardware
operation was run in this follow-up.
