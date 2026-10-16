# GS-68 CloudSync Physical-HIL Automation — 2026-10-16

## Current disposition

**Status: PARTIAL.** The software-side diagnostic image, controlled host capture adapter, TEST_ONLY mutual-TLS backend, case plan, evidence verification, dry-run, registry and negative tests are implemented and focused checks pass. A built image is preserved outside the worktree with checksums.

**CONNECT-SPARE-S3-READY=NO.** GS-68 owner comment 11169 explicitly says no spare connection is needed or authorized yet. The fixture template remains unassigned; no target identity, spare-board image, DS identity provider, test-backend deployment receipt or paired C3 controller is present. All ten physical cases remain NOT_RUN. No USB/serial/board access or physical operation occurred.

The report replaces older sections in this file that said the capture adapter and target build did not exist. Those statements described earlier checkpoints and are no longer current.

## Authorization and boundaries

GS-68 comment 11169 authorizes this software-only automation phase in the isolated branch. It explicitly prohibits USB/serial access, board attachment/operation, flashing/reset, DS/eFuse/HMAC provisioning, production credential issuance, Secure Boot/Flash Encryption changes, live CloudSync and production service use. A separate, fixture-specific written approval is required before connecting the spare S3 or C3.

The implementation remains in /home/udaybhan/projects/Ghar_sajag_r1_cloudsync_mtls on feature/r1-gs68-gs109-mtls-feasibility. It is not merged into canonical. The GS-114 C8 fixture/worktree was not used or modified. Production CloudSync stays disabled, Jira statuses remain unchanged, and the existing P0 PARTIAL and Hub migration FAIL states were not changed. No full release gate was run.

Context preflight: PASS, version 2026-10-13.001.

## Implemented software

### Diagnostic firmware and build-only path

- The diagnostic component in code/firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic implements a separately selected command interface. It returns bounded, non-secret observations: chip/revision/MAC, detected flash and PSRAM, reset reason, IDF version, free heap/largest block, compiled source/profile binding and image identity.
- sdkconfig.gs68_cloudsync_hil.defaults is a separate diagnostic profile enabling the candidate DS/TLS 1.2 build path. It is not included by normal product profiles and contains no provisioned identity or production credential.
- code/scripts/build_gs68_cloudsync_diagnostic.py checks the committed source/profile and builds the ESP32-S3 image and size report only. It does not open serial, flash or reset a device.
- There is deliberately no installed DS identity provider, HMAC/eFuse context, certificate issuance, or physical TLS authorization. Until approved provisioning and provider inputs exist, firmware returns a fail-closed blocked state and makes no network request. The successful compilation is not evidence that hardware RSA signing or mTLS works.

A first build attempt failed because the ESP-IDF 6.0.3 environment did not provide the json component used by the initial parser. The parser was replaced with a bounded, dependency-free command parser. The clean committed-source build then passed.

### Capture, backend, and evidence

- code/tools/hil/gs68_cloudsync_hil.py reuses the GS-130 runner conventions. Default operation is offline dry-run. A future physical invocation requires a complete spare fixture manifest, exact case-scoped authorization, source/profile/image matches and explicit confirmation. It rejects the protected C8 fixture and blocks missing or mismatched prerequisites.
- code/tools/hil/gs68_capture.py implements bounded frames, an explicit stable by-id serial adapter for a separately authorized future run, incomplete-capture rejection, atomic restricted evidence writes and a hash-chained record stream.
- code/tools/hil/gs68_test_backend.py implements a manually started TEST_ONLY TLS 1.2 mTLS service for isolated testing. It requires RSA-3072 client credentials, maps certificate fingerprints to explicit Hub/Home/epoch tuples, uses transactional duplicate-safe durable receipts and signs readiness/commit receipts. The template is unconfigured; this task did not start the service or make a physical or network connection.
- Receipt verification binds case, nonce, observation digest, source commit, image/profile, certificate fingerprints, fixture and ownership context. The signature proves the TEST_ONLY backend issued a receipt for the submitted observations; it does not constitute cryptographic hardware attestation. The hash chain is tamper-evident, not protection against an administrator who can replace the entire bundle and its trust roots.
- gs68_spare_fixture.template.json and gs68_test_backend.template.json contain no assigned identities or secret values.

The capture and adjudication software can validate protocol behavior and fail closed. With no physical fixture evidence or DS provider, it cannot produce a physical PASS.

## Case plan and current disposition

All ten stable cases map through PHY-GS68-CLOUD-MTLS; release blocking remains YES and physical status remains NOT_RUN.

| Case | Planned physical assertion | Current disposition / missing prerequisites |
|---|---|---|
| GS68-PHY-001 | RSA-3072 DS signature from the S3 identity | NOT_RUN — D12 key custody/provisioning approval and target DS provider/context absent |
| GS68-PHY-002 | TLS 1.2 mTLS using the hardware signer | NOT_RUN — case 001, approved D05 trust profile and isolated backend readiness absent |
| GS68-PHY-003 | Client/server chain and server-name validation | NOT_RUN — approved roots, trusted time (D06) and target handshake evidence absent |
| GS68-PHY-004 | Unknown, revoked, expired, malformed and wrong-purpose credential rejection | NOT_RUN — isolated physical identities and approved credential lifecycle absent |
| GS68-PHY-005 | Wrong Hub/Home/installation epoch rejection | NOT_RUN — approved ownership fixture and backend authorization evidence absent |
| GS68-PHY-006 | Bounded outage and secure reconnect | NOT_RUN — D16 bounds, outage controller and paired C3 capture/control path absent |
| GS68-PHY-007 | Restart retries the exact EventKey/body | NOT_RUN — approved restart method, paired C3 control path and physical event ledger absent |
| GS68-PHY-008 | Duplicate suppression and exact durable backend completion | NOT_RUN — approved GS-148 receipt contract and physical event chain absent |
| GS68-PHY-009 | Heap, handshake timing and runtime stability | NOT_RUN — D16 limits and source-matched physical instrumentation absent |
| GS68-PHY-010 | Signed-image compatibility and failed-health rollback | NOT_RUN — separate GS-118/D15 approval, signed image pair and recovery plan absent |

The paired C3 observation/control interface is not implemented in this phase; cases 006–010 need it. Existing host and simulated-HIL results are not physical case evidence.

## Build and artifact provenance

Build command:

GS68_DIAGNOSTIC_BUILD_ROOT=/tmp/gs68_cloudsync_diag_20261016_c527f98 python3 scripts/build_gs68_cloudsync_diagnostic.py

Run from code/ with ESP-IDF v6.0.3.

| Property | Result |
|---|---|
| Build status | BUILD_ONLY_PASS |
| Target profile | ESP32-S3 N16R8 candidate, 16 MiB flash / 8 MiB PSRAM |
| Source commit | c527f98c53916bfa6079a516b610f15fc83ffc1b |
| Git code subtree OID | 6411f59f1d0c66a24ac8a5aee28a0715d0f1c8ea |
| ESP-IDF | v6.0.3 |
| Diagnostic profile SHA-256 | 00a8aefb20a6b67d34c6631128031d112ff091d3f255b21a7280db45a356b1d0 |
| Image bytes | 442,544 |
| Image SHA-256 | 0e4fede23804199b98c246315e32c6468b49b0a23baaa7717932c2c3d146cb47 |
| Hardware actions | none; flash_or_serial_used=false |

External restricted artifact directory:
 /home/udaybhan/projects/gs68_hil_build_evidence_20261016_M9cHfJ

It contains the image, JSON build report, build log and exact profile defaults. Directory mode is 0700; files are 0600. The checksum manifest verified all four copied artifacts. Manifest SHA-256:
baedf50bb53d239002765ccdc225cd4f2dd8e702c52a777f49ce7d937194c055.

The image and build report are external evidence only; no firmware binary or credentials are committed.

## Focused validation

Commands run against the isolated branch:

| Command | Result |
|---|---|
| tools/context/ghar_sajag_context_preflight.sh | PASS, context 2026-10-13.001 |
| make gs130-hil-runner-test | PASS, 63/63 combined GS-130 and GS-68 runner/capture/backend tests |
| make validation-cloudsync-hil | PASS safe offline dry-run; 10 cases shown, execution BLOCKED, physical=NOT_RUN, hardware_actions=0 |
| make cloudsync-security-ut | PASS, 20 cases: 8 C++ adapter and 12 backend |
| make cloudsync-security-sim-hil | PASS, 18/18; physical=NOT_RUN |
| make cloudsync-mtls-integration-test | PASS, 1/1 real localhost TLS 1.2 mTLS with the production worker and durable backend; two attempts, one completion |
| make physical-hil-catalogue-test | PASS, 100 catalogue cases; no device access |
| make feature-coverage-test | PASS, 199 feature rows, 212 modules, 16 physical cases; 22/22 Python traceability tests |
| python3 -m unittest discover -s tests/python -p test_component_gate.py -v | PASS, 47/47 GS-116 framework tests |
| component_gate.py --suite suite --list for fast/release/hub/contract/backend/tooling | PASS for all six; each includes gs130-hil-runner-integrity, none runs physical execution |
| git diff --check | PASS before this report update; rerun after documentation edit |

validation-fast, release-gate-final, board-stack E2E and physical HIL were not run. The framework proves stage selection and fail propagation; that is not a release campaign result.

## Spare-fixture connection readiness

**CONNECT-SPARE-S3-READY=NO.** Do not connect the S3 or C3 under the current authorization.

Before a later connection/execution checkpoint, all of the following must be true:

1. A new written approval names the exact spare S3 and C3 identities, connection permission, case IDs, permitted operations, expiry, case-plan digest and recovery/preservation procedure. The existing approval explicitly says no device connection yet.
2. The owner-approved D12 threat model, key custody and provisioning controls and D05 verifier/issuer/trust/rotation/revocation contracts are resolved. No eFuse/HMAC action is inferred from this software task.
3. D06 trusted-time/validity behavior and D16 outage/resource/timing limits are approved.
4. A paired C3 controller/capture interface and its fail-safe recovery checks are implemented and validated.
5. A dedicated TEST_ONLY backend is configured under the approved trust profile, with readiness receipt and secret-store references only (no secrets in manifests).
6. The actual spare fixture identity receipt, S3/C3 image hashes and source/profile/build reports are verified; C8 identity/port exclusion is confirmed.
7. A separate GS-118/D15 authorization and signed-image recovery plan exists before case 010.

No board operation is authorized by this report. Even after those prerequisites, each operation must remain within the new written fixture-specific approval. Production roots, commercial sending and production credentials stay excluded.

## Current Git state and next action

At the pre-documentation closeout checkpoint, local HEAD was c527f98c53916bfa6079a516b610f15fc83ffc1b and origin was 3634ae5aeea0eedabfe80f54c7323986edf69cae; the two implementation commits had not yet been pushed. The pre-existing untracked code/firmware/hub/target/esp32s3/idf/managed_components/ directory is preserved and excluded from staging. The report, resume handoff and work-state note record this checkpoint; the final push receipt is included in the status-neutral Jira handoffs and task closeout. No merge into canonical or hardware connection is authorized.
