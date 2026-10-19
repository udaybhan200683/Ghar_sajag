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
UTC provider and the configured timezone. The current TEST_ONLY adapter accepts
`Etc/UTC` only; other timezone identifiers fail closed. Missing/invalid time,
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
