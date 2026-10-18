# GS-40 TEST_ONLY S3 runtime composition checkpoint — 2026-10-18

## Disposition

The requested credential-ready S3 TEST_ONLY runtime composition is **not
implemented** at this checkpoint. The product startup still constructs
`UnprovisionedS3CloudTrust`. I did not replace it with synthetic authority or
time claims. The existing host provider, GS-168 issuer, NodeHealth backend and
caregiver path pass, but these results do not establish that the S3 product
runtime can acquire or refresh its inputs.

```text
BUG_CLASSIFICATION=R1_BLOCKER
REQUIREMENT_SOURCE=docs/product/DECISION_LOG.md (GS-D031, GS-D032); docs/product/R1_RELEASE_CONTRACT.md
DECISION_IDS=GS-D031; GS-D032
TASK_SCOPE=GS-40 TEST_ONLY runtime composition and source-to-caregiver integration
OUT_OF_SCOPE=Production credential issuance, DS/eFuse provisioning, commercial endpoint activation, physical fixture access, and changes to NodeHealth/EventKey/ACK semantics
```

## Exact source and authority gap

- `hub_runtime_adapter.cpp` already schedules the bounded CloudSync NodeHealth
  worker and refreshes its snapshot. It still constructs
  `UnprovisionedS3CloudTrust` at product startup.
- `ProvisionedS3CloudTrust` already validates a typed material snapshot and
  authenticated time, and the TEST_ONLY path checks RSA-3072 certificate/key
  correspondence. `S3CloudTrustMaterialSource` and
  `S3TrustedHubTimeSource` are interfaces; the full product target has no
  implementation connected to a target-side enrollment/material source.
- GS-168's existing TEST_ONLY issuer and registry are Python host components.
  The target has no credential delivery/refresh adapter that maps the current
  registry state to an S3 material snapshot.
- GS-D032 locks current Home/epoch and revocation behavior but leaves the
  authentication and delivery mechanisms open. Current GS-109 comment 11367
  and GS-148 comment 11368 likewise record that target-side material and
  runtime provisioning are absent.
- The signed-time verifier/provider accepts an injected pinned key and a
  nonce/boot-generation-bound proof. No product TEST_ONLY transport or
  configuration supplies the proof/key to the running product. The current
  `HttpsBackendChannel` requires trusted time before it starts HTTPS, so it
  cannot itself bootstrap that time through its existing CloudSync request.
- S3 Wi-Fi initialization starts STA mode but does not configure or connect a
  TEST_ONLY network. No bounded configuration source for isolated Wi-Fi,
  endpoint and trust material is connected to product startup.

Adding an unauthenticated local Home/epoch claim, treating an NVS string as
authenticated authority, using host wall-clock/SNTP as trusted time, or
creating an unreviewed bootstrap wire protocol would contradict the current
fail-closed GS-D032 boundary. No such code was added. No new product protocol
or trust decision was inferred.

## Validation executed on canonical HEAD `58487978988b609917f4d021d01480ab87bc220a`

Command:

```sh
make -C code cloud-trust-provider-test cloudsync-security-ut gs40-host-test gs40-config-test gs40-qualification-test board-stack-e2e-host-test app-test feature-coverage-test
```

The command reached `feature-coverage-test` and exited 2 because its registry
consistency check found one duplicated `make cloudsync-security-ut` entry in
the GS-40 traceability row. All preceding stages in the command passed. After
correcting the row, the standalone `feature-coverage-test` rerun passed.

Results before the traceability correction:

- Cloud-trust provider: PASS, 5 suites, including TEST_ONLY provider-to-NodeHealth
  CloudSync path and signed-time/ownership fail-closed cases.
- mTLS adapters: PASS, production 9/9 and TEST_ONLY 5 assertions.
- Backend security: PASS, 14/14.
- GS-168 issuer/registry: PASS, 10/10.
- GS-68/GS-40 issued-identity NodeHealth/caregiver localhost TLS E2E: PASS, 4/4.
- NodeHealth read model: PASS, 5/5.
- GS-40 liveness: PASS, 1,320 checks; configuration/simulation 17/17; qualification
  runner 17/17.
- Board-stack host simulation: PASS, 10 cases / 398 checks; no physical actions.
- Caregiver JS: PASS, 25/25.
- Feature traceability initially found a stale duplicate command in the
  `GS40-NODEHEALTH-CLOUD-001` row. The row now exactly matches its five
  registered stages. `make -C code feature-coverage-test` rerun: PASS, 208
  features, 220 modules, 24 physical cases; mapping tests 22/22.

These run actual existing host production-code paths and an ephemeral GS-168
issuer plus localhost TLS/backend/PWA fixture. They do not execute the target
S3 application. No new target image was built because no firmware source
changed; the previously recorded 2,164,512-byte image at SHA-256
`9444365b32aab0a78a357f94fcdcd5538bb977eea52b5ff63fbcfc8f8c78f2bb` remains a
compile-only transport-capability image and is not an integrated candidate.

## Remaining action

GS-40 remains In Progress and the integrated S3 runtime milestone remains
PARTIAL. Before target source integration can proceed, the test-only authority
and provisioning boundary must supply a reviewed contract for (1) how the
target obtains/revalidates active GS-168 test credential and current Home/epoch
state, (2) how the signed-time proof and pinned time-authority key reach the
target before TLS certificate-time validation, and (3) how isolated network
credentials/origin/CA are provided without committing secrets or changing
production composition. Once that interface is approved/provided, connect it
to the existing provider and startup path, rerun focused tests, build a new
source-bound ESP-IDF 6.0.3 image, and run the local/physical qualification
steps separately. GS-40 PHY-01..06 remain NOT_RUN; PHY-05 still needs a second
independently enrolled Node with an accepted legacy profile or an approved
equivalent fixture.

No board, serial port, production endpoint, credential, eFuse, or security
setting was accessed or changed. Existing migration failure and P0
`product_status=PARTIAL` remain unchanged.
