# GS-40 TEST_ONLY S3 TLS provider continuation — 2026-10-18

## Scope and disposition

Owning work: GS-40; affected dependencies GS-109, GS-148, GS-168 and GS-116/
GS-130. Components: S3 Hub HTTPS identity/provider, CloudSync, local backend
NodeHealth and caregiver projection. This is a TEST_ONLY software change; it
does not change production credentials, TLS policy, NodeHealth semantics,
durable events or physical acceptance.

```text
BUG_CLASSIFICATION=R1_BLOCKER
REQUIREMENT_SOURCE=docs/product/DECISION_LOG.md (GS-40 S3 runtime composition follow-up); GS-D032
DECISION_IDS=GS-D032; GS-D031
TASK_SCOPE=Add a build-guarded TEST_ONLY RSA software-key path to the existing S3 cloud trust and HTTPS interfaces; validate existing GS-40 host/backend/PWA path
OUT_OF_SCOPE=Production identity/key custody, production time authority, C8/C3/spare access, flash, provisioning, production endpoints, EventKey/ACK changes
```

## Implementation

The shared `S3CloudTrustMaterial` and `CloudTlsIdentity` expose a TEST_ONLY
software client key only when `GS40_TEST_ONLY_CLOUDSYNC_BUILD=1` is defined.
`ProvisionedS3CloudTrust` accepts that branch only for TEST_ONLY material,
requires an RSA-3072 private key matching the ClientAuth certificate, and
continues to require active authenticated authority, current Home/epoch,
credential generation and trusted time. Other builds reject TEST_ONLY material
and still require the verified DS context and key-custody flag.

`HttpsBackendChannel` uses ESP-TLS `client_key_pem` only in the explicit
TEST_ONLY build, only for a TEST_ONLY software identity, and refuses a mixed
DS/software identity. The isolated profile rejects a build if DS mode remains
enabled. Server CA and hostname verification, TLS 1.2, identity/time gates and
no-bearer behavior are unchanged. Commercial composition defaults remain
unchanged.

The profile switch currently compiles this guarded transport capability. It
does **not** replace the product runtime's `UnprovisionedS3CloudTrust`; no
target-side GS-168/ownership/time material source or runtime provisioning
channel is present in the current source. Therefore no image from this change
is represented as an integrated, credential-ready GS-40 image.

## Validation

Commands/results on canonical source before documentation closeout:

| Command | Result |
|---|---|
| `make -C code cloud-trust-provider-test cloudsync-security-ut` | PASS: trust provider 5 suites; DS mTLS adapter 9/9; TEST_ONLY software mTLS adapter 5 assertions; security checks 14/14; local TLS GS-40 identity/NodeHealth/caregiver 4/4; GS-168 issuer 10/10; NodeHealth model 5/5 |
| `make -C code gs40-host-test gs40-config-test gs40-qualification-test board-stack-e2e-host-test app-test` | PASS: Hub liveness 1,320 assertions; profile/simulation 17 tests; qualification runner 17 tests; board E2E 10 cases / 398 checks; caregiver JS 25/25 |
| `make -C code cloudsync-security-sim-hil cloudsync-mtls-integration-test feature-coverage-test physical-hil-catalogue-test` | PASS: CloudSync security 18/18; production worker/local HTTPS bridge 1/1; traceability 22/22; physical catalogue 108 cases |

All physical entries remained NOT_RUN and no serial/USB, board, endpoint or
production credential was used. The local TLS tests use the existing GS-168
TEST_ONLY issuer and ephemeral credentials; they are software integration,
not silicon or source-to-caregiver physical evidence.

## Target build

After commit `2427622b44796779b3c0730d4da6baeebcde7835`, a non-flashing
ESP-IDF 6.0.3 full S3 product-profile build passed with
`GS40_TEST_ONLY_CLOUDSYNC=ON`, `sdkconfig.defaults` plus
`sdkconfig.gs40_test_only.defaults`, and the existing paired C3 asset. Build
root: `/home/udaybhan/projects/.gs40_testonly_product_build_20261018`.

- S3 application: 2,164,512 bytes; SHA-256
  `9444365b32aab0a78a357f94fcdcd5538bb977eea52b5ff63fbcfc8f8c78f2bb`.
- Effective sdkconfig SHA-256:
  `8bff1b0e2cb4ff7f109e22a4962ef9d6e79ba50da42e44e9316bf14093b8f9fa`.
- TEST_ONLY defaults SHA-256:
  `8060129280e93ce0f18c2ffc74198e25b7783c9b963d735e6bb511d1ee9a0f94`.
- Paired C3 input SHA-256:
  `b4e2b1c1d370fd2da2a30aae52cfbc2f85e91d0ff3b39da41eef23816829fedb`.
- CMake option is ON; effective config disables ESP-TLS DS, Secure Boot and
  Flash Encryption. Development partition table is
  `partitions.development.csv`; smallest OTA slot is 4 MiB.
- ESP-IDF reports 1,998,560 bytes available in the smallest application slot.

This is a source-bound TEST_ONLY **transport-capability product build**, not a
credential-ready or integrated GS-40 image. Inspection of the selected
`hub_runtime_adapter.cpp` source and compiled startup log confirms the runtime
still constructs `UnprovisionedS3CloudTrust` and logs identity/time as
unprovisioned. No test private key, registry binding or endpoint was supplied
to the build. It proves the guarded target code compiles; it does not prove
runtime provider composition, startup publication, TLS exchange, or any target
behavior. The prior statement that no S3 image had been built is superseded
only for this compile-only profile; no integrated image is claimed.

## Remaining GS-40 requirements

1. Implement the target-side TEST_ONLY material source that consumes a
   GS-168-issued identity, current Home/epoch authority and authenticated D06
   time through existing interfaces; it must reject stale/revoked inputs and
   remain absent from normal commercial builds.
2. Provide a bounded test-only runtime configuration path for that source and
   the isolated local HTTPS endpoint without embedding private material in the
   source tree. The existing Hub starts Wi-Fi STA without a test-network
   configuration, so a complete target path also needs explicit test fixture
   network configuration.
3. Build and hash the complete S3 product profile against the exact paired C3
   asset, then run local/backend/caregiver contracts on the source-bound build.
4. Run physical PHY-GS40-01..06 only on an explicitly authorized, identified
   C3/S3 pair. No current fixture authorization was established in this task.
   PHY-GS40-05 additionally requires a second independently enrolled C3 with a
   trusted legacy profile or an approved qualified profile fixture.

The protected C8 and C3, the GS-68 spare diagnostic image, and all unrelated
worktrees/evidence were left untouched. Official GS-68 and GS-40 physical
acceptance remains NOT_RUN.
