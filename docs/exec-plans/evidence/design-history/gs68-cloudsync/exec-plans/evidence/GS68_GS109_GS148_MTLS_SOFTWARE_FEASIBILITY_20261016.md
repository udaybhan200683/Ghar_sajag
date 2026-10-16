# GS-68 / GS-109 / GS-148 CloudSync RSA-3072 mTLS software feasibility

Date: 2026-10-16 UTC
Status: **software feasibility implemented; focused tests and paired targets pass; production and physical acceptance remain open**

## Scope and source

This work used the owner-approved isolated branch `feature/r1-gs68-gs109-mtls-feasibility`, rooted at pinned baseline `12eae946db1ce8c810c9cc7df8e2c17d27d30889`. The checkpoint under test was `65556078202b26a521a0f61d675dd5774779cd66`; resumed changes are recorded in the delivery commit that links this report. Context preflight passed for context version `2026-10-13.001`.

The moving canonical C8 worktree was not edited, synchronized, or merged. No board, USB/serial port, eFuse, production credential, customer endpoint, or live CloudSync channel was accessed. The candidate does not install a production provider or enable commercial CloudSync.

Jira authorization is limited to software design and non-destructive feasibility. GS-68 comment 11026 and GS-109 comment 11027 leave D05/D12 production authority and key custody pending; D06/D15/D16 numeric and compatibility decisions remain pending. GS-148 commercial sending remains disabled. The latest pause handoffs were GS-68 comment 11152, GS-109 comment 11151, and GS-148 comment 11153.

## Design and implementation

| Area | Implementation | Boundary |
|---|---|---|
| Hub TLS identity | `firmware/hub/target/esp32s3/https_backend_channel.hpp/.cpp`: `CloudTlsIdentity` and `CloudTlsIdentityProvider` expose a certificate, opaque DS context, RSA bit count, and an explicit cloud-client purpose. The adapter rejects wrong purpose, missing context, or non-3072-bit identity. It does not expose a general signing API or reuse commissioning P-256 identity. | Interface only; no provider is wired into product composition and no credential is provisioned. |
| TLS profile | The DS-backed `HttpsBackendChannel::post` path explicitly selects TLS 1.2 and uses ESP-IDF's client certificate and opaque DS context fields. Server verification remains enabled. | Candidate profile only. IDF compilation is not proof of DS/eFuse signing on hardware. TLS 1.3 was not selected or validated. |
| Backend peer authorization | `backend/ghar_sajag/cloud_client_identity.py`: `authorize_cloud_tls_peer` requires server-side, certificate-required TLS 1.2, a trusted time, RSA-3072 ClientAuth certificate, active cloud-purpose fingerprint mapping, and a current ownership row. It returns permanent Hub identity/current Home epoch context for the existing transactional authorization guard. The `CloudCredentialRegistry` protocol leaves the future GS-165/GS-172 factory registry behind an injected interface. | No production route or credential registry is installed. Synthetic certificate records are test-only. |
| Synthetic credentials and TLS | `tests/support/cloudsync_mtls_certs.py` and `cloudsync_mtls_local.py` create disposable RSA certificates and run real localhost OpenSSL TLS 1.2 client authentication. | Temporary test keys are generated outside the source tree and discarded by fixtures. No key material is committed. |
| Simulated HIL | `tests/support/cloudsync_mtls_sim_hil.py` exercises authentication, ownership, retry, restart, and failure cases. The new `test_018_home_transfer_during_authenticated_request_fails_closed` transfers ownership after TLS peer authentication but before API dispatch. | Host simulation; reports `physical=NOT_RUN`. |
| Production worker integration | `tests/cpp/p2d_cloud_contract_validation.cpp` now admits through `HubRuntime.authenticated_radio_message_callback`, persists to the production segmented outbox, runs the existing `CloudSyncWorker`, reconstructs the outbox/runtime after restart, and retries the byte-identical EventKey/body through the real TLS/backend fixture. The backend confirms one durable effect and one caregiver projection. | Authenticated ingress is the integration boundary; the separate board-stack E2E validates Node/Hub runtime and authenticated frame behavior. The integration is not physical or commercial qualification. |
| Gate and traceability | Three mandatory registered stages cover unit, simulated HIL, and mTLS integration. GS-130 feature, source, and physical traceability keeps physical status `NOT_RUN`. | The physical release-evidence stage remains separate and cannot be satisfied by simulated HIL. |

The in-flight Home-transfer case verifies that authorization is rechecked at durable dispatch time: the old Home request receives 403 and produces zero durable effects. The real worker integration simulates a lost backend response, reconstructs Hub state from the same test flash/state store, retries the exact request, and observes one backend/caregiver effect.

## ESP-IDF 6.0.3 crypto/TLS compatibility findings

The installed v6.0.3 source was inspected at `components/esp-tls/esp_tls_mbedtls.c`:

- The DS TLS adapter imports an opaque `ESP_RSA_DS` PSA key with
  `PSA_KEY_TYPE_RSA_KEY_PAIR`, the DS-reported modulus size, and
  `PSA_KEY_USAGE_SIGN_HASH`; it injects the public key parsed from the supplied
  certificate rather than exporting private key material.
- For the current TLS 1.2 profile, IDF sets
  `PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_ANY_HASH)` for the DS key. If TLS 1.3 is
  compiled, this source also enrolls `PSA_ALG_RSA_PSS(PSA_ALG_ANY_HASH)`.
  ESP-IDF's `esp_ds.h` declares an `ESP_DS_RSA_3072` size and the target build
  has `CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y`.
- The candidate explicitly pins the mTLS path to TLS 1.2. Its S3 sdkconfig has
  TLS 1.2 enabled and TLS 1.3 disabled; host OpenSSL integration uses TLS 1.2
  with an RSA-3072 client certificate. We did not exercise a TLS 1.3/PSS
  handshake, nor a hardware DS-generated CertificateVerify signature.
- This confirms a plausible IDF 6.0.3 software adapter path and exact profile
  assumptions for PKCS#1 v1.5 TLS 1.2 signatures. It does not confirm that a
  provisioned S3 DS context, HMAC/eFuse key, certificate issuer, chain policy,
  live trusted-time source, or target memory/timing behavior works on a board.

No certificate-profile, root, cipher-suite, time, resource, or key-custody
production values were approved by this finding.

## Permanent test cases

| Suite | Stable coverage | Result |
|---|---|---|
| C++ adapter unit | `GS-CLOUD-MTLS-UT-001..008`: restricted identity purpose/algorithm/size, DS-context presence, verified server TLS, and refusal paths. | PASS, 8/8 |
| Backend identity unit | `test_001..012`: current RSA-3072 mapping, clone/unknown and revoked identities, purpose/algorithm, expiration and trusted time, malformed cert, EKU, ownership transfer, repeat lookup. | PASS, 12/12 |
| Simulated HIL | `test_001..018`: valid and invalid client/server trust, server name, revocation, expiry, missing signer context, wrong purpose, clone, unsupported TLS, wrong Home/epoch, in-flight transfer, unavailable time, exact retry, backend restart, network recovery, malformed event. | PASS, 18/18; `physical=NOT_RUN` |
| Worker/mTLS integration | `test_019_production_worker_real_mtls_durable_retry`: production CloudSync worker, real TLS client authentication, durable backend commit, lost receipt, Hub restart, exact retry, one caregiver projection. | PASS, 1/1; `physical=NOT_RUN` |

The adapter unit suite runs the C++ cases plus the 12 Python cases through `make cloudsync-security-ut` (20 assertions/cases total). Simulated HIL and integration targets are `make cloudsync-security-sim-hil` and `make cloudsync-mtls-integration-test`.

## Validation registry and traceability

Registered stages are:

- `cloudsync-security-unit`
- `cloudsync-security-sim-hil` (prerequisite: unit)
- `cloudsync-mtls-integration` (prerequisites: simulated HIL and cloud contract)

All three explicitly set `fast=true` and `release=true`, associate with Hub/contract/backend, require nonzero success markers, and declare their source/test dependencies. Selection checks confirmed all three are present in `fast`, `release`, `hub`, `contract`, and `backend`. The existing release-only `physical-hil-release-evidence` stage remains separate. `release-gate-final` was not run.

The GS-116 framework suite passed 47/47. The engineering dashboard/registration meta suite passed 98/98 after its registry-delta expectation was extended to allow exactly these three new CloudSync stages in addition to the pre-existing `diagnostic-foundation` stage. This test-infrastructure-only correction preserves rejection of any other unexpected registry addition.

Traceability integrity passed: 199 feature records, 211 source modules, 16 physical cases, and 22 mapping checks. Feature coverage was also exercised in the fast gate.

## Focused commands and aggregate gate outcomes

The resumed work ran the three dedicated Make targets and then the affected suites. The CloudSync unit, 18-case simulated-HIL, and one-case integration stages passed in the final `validation-fast` run. Additional focused results:

| Command | Result |
|---|---|
| `make p2d-cloud-contract-host-test` | PASS; 15 invalid receipt modes rejected, 200 pending events bounded, two completion-persistence cuts recovered. |
| `make gs148-cloud-worker-api-integration-host-test` | PASS; exact retry after lost receipt, one durable effect and one caregiver projection. |
| `make p2d-https-channel-host-test` | PASS; 8 channel modes and bounded body/response/I/O sizes. |
| `PYTHONPATH=backend:. python3 -m unittest discover -s tests/python -p test_component_gate.py -v` | PASS, 47/47. |
| `PYTHONPATH=backend:. python3 -m unittest discover -s tests/engineering_dashboard -p 'test_registration.py' -v` | PASS, 6/6 after the exact-stage whitelist correction. |
| `make validation-node` | Aggregate FAIL only at required P0 completion stage: all 26 scenario checks and the Chromium test passed, but `product_status=PARTIAL`. Node/FOTA/board-stack stages passed. |
| `make validation-contract` | Aggregate FAIL only at required P0 completion stage: 26 scenario checks and Chromium passed, `product_status=PARTIAL`. Contract, board-stack, storage sanitizer, and new CloudSync stages passed. |
| `make validation-backend` (final run) | Aggregate FAIL only at required P0 completion stage: 26 scenario checks and Chromium passed, `product_status=PARTIAL`. New CloudSync, backend receipt, 471 Python tests, and corrected 98-case diagnostic-foundation stage passed. |
| `make validation-hub` | The initial run passed CloudSync and Hub durability stages but failed the existing journal-migration assertion `clean migration commits`; its first P0 attempt also lacked the local Playwright package. The dependency was restored from `frontend/package-lock.json`; P0 then ran successfully at scenario level in later gates, while gate adjudication correctly remains FAIL for `product_status=PARTIAL`. |
| `make validation-fast` | Aggregate FAIL, 71/73 stages PASS. Only failures: existing `migration` (`Hub journal migration validation failed: clean migration commits`) and required `p0-full-product-e2e` (26/26 scenario checks and Chromium pass, but `product_status=PARTIAL`). All three new CloudSync stages passed. |
| `make p0-product-e2e P0_SCENARIOS=` | PASS at scenario level: 26/26 checks, one Chromium browser test, `product_status=PARTIAL`, `physical=NOT_RUN`. This does not satisfy product completion. |

The P0 and Hub-migration states predate this branch and are retained without changes. `npm ci --ignore-scripts --no-audit --no-fund` restored the lockfile-defined Playwright dependency; `package.json` and `package-lock.json` were not changed. The complete release gate was not run.

The final fast/backend/node validation receipts used source fingerprint
`509962afddcc64a3dbf373a24b7f7809050e904c51f625db39df724233e371ec` and
reported `source_unchanged=true`. The initial Hub/contract runs used the
pre-fixture-correction fingerprint
`7064f0d0a62552e9ad4f5e9865d70fb3116f068631b9370fbdaf0aed892a9d12`.

## ESP-IDF 6.0.3 paired target and resource check

Command: `python3 scripts/build_validation_targets.py` from `code/`. The paired C3/S3 production-style profile compiled with `GS_HIL_BUILD=OFF`; no hardware actions occurred. The build receipt is preserved at `code/build/validation_targets/gs116-64ep7xle/report.json` (ignored generated evidence).

| Target | Image size | OTA slot | SHA-256 | Result |
|---|---:|---:|---|---|
| ESP32-C3 Node | 934,992 bytes | 1,966,080 bytes | `cc4cbab67923eb9166da8b72e38d5c591dc236d4a80923616c8ffe41ceafecf5` | PASS |
| ESP32-S3 Hub | 1,882,096 bytes | 4,194,304 bytes | `c217190bfa69618b93d5ec26270dea4ab4a8c7b3398ac90cf29c0c2c296e979d` | PASS |

Both used project version `6555607-gs116-509962af`; report source fingerprint is `509962afddcc64a3dbf373a24b7f7809050e904c51f625db39df724233e371ec`. S3 sdkconfig enables `CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y` and `CONFIG_MBEDTLS_SSL_PROTO_TLS1_2=y`; TLS 1.3 is not enabled in this candidate profile. This is a compile and slot-size check, not runtime memory, cryptographic timing, signer high-water, or hardware proof. The build log contains one unrelated non-fatal warning in the classic ESP32 adapter (`retirement_ack_sent` unused); the S3 image linked and passed the configured slot bound.

The signed C3 profile was not built: this checkout has no `sdkconfig.signed` and no approved disposable test signing key/profile was supplied. No credentials were fabricated or security settings bypassed. Signed-profile build status is therefore `NOT_RUN/BLOCKED` on safe test signing inputs.

## Read-only comparison with moving canonical

The latest fetched canonical branch was
`feature/r1-commercial-baseline` at
`d738dc51a25e72de570a11fc39f0e26522ead3d8`; its merge base with this isolated
branch is the pinned baseline
`12eae946db1ce8c810c9cc7df8e2c17d27d30889`. At comparison time canonical had
20 commits after that base and this branch had one task checkpoint commit.
There were seven overlapping changed paths: `code/Makefile`,
`code/validation/suites.json`, `docs/product/R1_WORK_STATE.md`, and the four
GS-130 traceability/inventory/physical-catalogue files. The CloudSync
production adapter/backend identity files did not overlap canonical changes
since the baseline. The overlap is registry/documentation composition rather
than a production-code conflict, but the registry and work-state have advanced
on canonical; integrate later by manually applying the reviewed additions to
the current files and rerunning framework/traceability checks. Do not
cherry-pick or merge this pinned branch wholesale into the moving canonical
branch.

## Bugs and test-infrastructure issues found during resume

1. The stronger integration test initially attempted direct `EventKey` equality, which the type does not define; it now compares the canonical `.str()` representation.
2. The real worker/backend bridge requires persisted Node enrollment provenance; the test now establishes the owner-bound runtime-state record before sending.
3. The integration fixture was strengthened from a manually staged event to authenticated Hub ingress, segmented outbox persistence, Hub reconstruction, and exact retry.
4. Adding the three registered stages exposed a stale test assertion that allowed only the diagnostic dashboard stage; its exact allowed set now names the three CloudSync stage IDs. No production dashboard behavior changed.
5. Initial P0 execution could not find the Playwright binary. Restoring the exact package-lock dependency resolved the environment failure; later P0 scenario runs completed, with only the pre-existing product-partial adjudication remaining.

## Open approval and qualification boundaries

- No live ESP32-S3 DS key operation, eFuse/HMAC key provisioning, private-key non-exportability proof, Secure Boot/Flash Encryption, production credential issuance, CA/HSM, rotation/revocation service, or trusted-time source was exercised.
- No commercial CloudSync provider is installed or activated. The backend identity adapter is not mounted as a production route; credential/ownership registry interfaces remain synthetic.
- Physical DS/eFuse signer proof, certificate-chain acceptance on target, target TLS handshake, resource/runtime and interruption behavior remain `NOT_RUN` and require a separately approved fixture/procedure.
- D05/D12 production sign-off, D06 time/lifetime values, D15 rollback matrix, D16 numeric resource/network limits, and GS-165/GS-172 factory interfaces remain pending.
- P0 `product_status=PARTIAL` and the Hub journal migration failure remain independent repository blockers. Their statuses were not weakened or changed.

## Delivery and next plan

The software implementation was committed and pushed on
`feature/r1-gs68-gs109-mtls-feasibility` at
`9c50443a28c1e6d237860488f965f14183cfe166`. Subsequent documentation-only
commits record Jira receipts and handoff checkpoints; at task close, local and
GitHub branch refs were verified equal (the live ref is authoritative on
resume). No merge to canonical occurred. Status-neutral Jira
handoffs were posted: GS-68 comment 11159, GS-109 comment 11160, and GS-148
comment 11161. The read-only comparison used canonical local/remote HEAD
`d738dc51a25e72de570a11fc39f0e26522ead3d8` and recommends later manual
integration after reconciling the seven shared registry/documentation paths.
The isolated worktree's downloaded ESP-IDF managed components, ignored
build/evidence/logs, and frontend `node_modules` remain preserved and were not
staged.

Next owner actions are review of the isolated software candidate, approval of
the remaining security/credential/time/rollback/network contracts, and a
separately authorized hardware qualification plan. Software feasibility
evidence must not be described as commercial activation or physical
qualification.
