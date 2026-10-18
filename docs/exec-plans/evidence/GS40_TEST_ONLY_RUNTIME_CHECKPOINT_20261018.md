# GS-40 TEST_ONLY S3 runtime checkpoint — 2026-10-18

**Status:** Partial software integration; not source-to-caregiver E2E and not
physical qualification.

## Repository and authorization boundary

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`. Starting HEAD and remote were both
`0f7780a955939799043fc832a431ee618db30571`; context preflight passed. The
implementation commit is `8bd9cf3` and the GS-116 registry correction is
`0d7a5f0`. The build artifact reports firmware source version `8bd9cf3`; the
follow-up commit changes only validation component ownership and does not
change firmware sources or build inputs.

This implementation is bounded to the explicitly enabled TEST_ONLY S3 product
profile under the task-specific engineering delegation. The GS40T/1 proposal
remains PROPOSED, not approved or LOCKED. No commercial CA, credential,
endpoint, eFuse, DS/HMAC key, Secure Boot/Flash Encryption change or production
activation was used. No hardware, serial port, C8, C3 or GS-68 spare was
accessed.

## Implemented composition

- New `gs40_test_only_bootstrap` code accepts a bounded one-session `G40E`
  signed/encrypted fixture envelope. Target PSA P-256 ECDH, HKDF-SHA-256 and
  AES-256-GCM protect the session; an external TEST_ONLY public RSA root
  verifies the envelope. Private signing material is not embedded in firmware
  or repository source.
- The envelope carries disposable isolated-network inputs, the backend CA and
  hostname, TEST_ONLY client identity material, and separate time/authority
  verification keys. Certificate/private-key correspondence, RSA-3072,
  ClientAuth, fingerprint, profile fields and bounds are checked.
- After Wi-Fi connection, the target sends a fresh nonce/boot-generation
  challenge over UDP and accepts only the existing RSA-3072/SHA-256 signed-time
  proof through `AuthenticatedHubTimeProvider`. Unsigned network time is not
  accepted. TLS uses the resulting trusted time and server CA/hostname checks.
- The target implements a signed, nonce/boot-generation-bound current-authority
  lease verifier, rejects stale/revoked/mismatched material, and fences the
  CloudSync trust source on refresh failure. The TEST_ONLY build composes
  `ProvisionedS3CloudTrust` with the existing HTTPS channel and NodeHealth
  CloudSync worker. Normal composition still instantiates
  `UnprovisionedS3CloudTrust` and the HTTPS adapter rejects the TEST_ONLY
  software key outside the explicit build guard.
- Durable event/EventKey, ACK, retry, priority and retirement paths are not
  changed. No test endpoint or time authority was added to the backend in this
  change.

## Validation

Executed focused command from `code/`:

```text
make gs40-test-only-bootstrap-test cloud-trust-provider-test cloudsync-security-ut gs40-host-test gs40-config-test gs40-qualification-test feature-coverage-test
```

Results:

- New bootstrap envelope/lease validation: 29 checks PASS.
- Cloud-trust provider: 5 suites PASS; production mTLS adapter 9/9 PASS;
  TEST_ONLY mTLS adapter 5 assertions PASS.
- Backend security negative/positive cases: 14/14 PASS.
- Existing issued-identity/mTLS/NodeHealth/caregiver E2E: 4/4 PASS (host
  integration; it does not invoke this new S3 product startup path).
- GS-168 TEST_ONLY issuer/registry: 10/10 PASS; NodeHealth backend model: 5/5
  PASS.
- GS-40 liveness: 1,320 checks PASS; configuration/simulation: 17/17 PASS;
  qualification runner: 17/17 PASS. Its expected live-operation cases remain
  BLOCKED/NOT_RUN without hardware access.
- Traceability: 208 features, 224 modules, 24 physical cases; mapping tests
  22/22 PASS.
- GS-116 framework first failed because the new stage used a component label
  (`security`) outside the registered ownership set. The registry was corrected
  to `hub` and `contract`; rerun `make validation-framework-test
  feature-coverage-test` passed: 47/47 framework tests, 208/224/24 trace counts,
  and 22/22 mapping tests.
- Previously accepted board-stack result 10 cases / 398 checks remains valid;
  it was not repeated because this addition does not change the simulated
  Node/Hub protocol or durability implementation.

### ESP-IDF builds

TEST_ONLY S3 product-profile command (non-flashing):

```text
idf.py -C firmware/hub/target/esp32s3/idf -B /tmp/gs40_test_only_build/build \
  -D IDF_TARGET=esp32s3 -D GS40_TEST_ONLY_CLOUDSYNC=ON \
  -D GS40_TEST_ONLY_CONFIG_ROOT_DER=/tmp/gs40_test_only_build/gs40_test_config_root.der build size
```

ESP-IDF 6.0.3 / esptool 5.4.0 PASS. Image metadata: `gs_r1_s3_hub`, version
`8bd9cf3`, ESP32-S3, 16 MiB flash profile, DIO/40 MHz; binary size 2,187,584
bytes, fitting the 0x400000-byte smallest app slot (48% free). The image
validation digest is distinct from the complete artifact-file digest.

```text
TEST_ONLY application SHA-256: d8df7d807059d65f37e5cf1b4df687234126418239f110cbaccb71f98305ded7
ESP image validation hash:     a4ac8be74997e0b5b1e1f993eb7707e757adaf2fd2d838fcf8ccceed0894ebc6
ELF SHA-256:                   bc42b00774333a62a1a90774ff7194f33232456a038cb83b400da83094dcd117
Effective sdkconfig SHA-256:   3750bc9360e4524d61d8209e2cbe7014f67be9ee55dcb553033bcc9858c83099
Product defaults SHA-256:      be0624e0d4efb47d6e3868a42c7a5925c5be1dea8520df644271ad2e66a4c024
TEST_ONLY profile SHA-256:     7339aa689a054a849ac14d29c0eb79de543d966a6440c18c8467ead4756cd073
Node-health config SHA-256:    2e42da92784c6eed807d8df240d1c33a178c1c088a568cbf9cb6d5d20817aadb
Generated GS40 config hash:   fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862
Config public-root DER SHA:   9018f58d50dc8ea180087af935130de540ef454976711af6f5335cc9caf9ec90
```

Effective settings verified: S3 target; USB Serial/JTAG primary console;
ESP-TLS DS peripheral disabled for TEST_ONLY software-key use; Secure Boot
disabled; Flash Encryption disabled. These are build configuration facts, not
device/eFuse evidence. The build also emitted an ESP-IDF component include-path
warning for the guarded USB Serial/JTAG header; build completed successfully.

The clean commercial-profile build used only `sdkconfig.defaults` and a fresh
isolated sdkconfig under `/tmp/gs40_commercial_build`; it completed with ESP-IDF
6.0.3 / esptool 5.4.0. CMake cache records
`GS40_TEST_ONLY_CLOUDSYNC=OFF`, empty `GS40_TEST_ONLY_CONFIG_ROOT_DER`, and
the target compile definition is `GS40_TEST_ONLY_CLOUDSYNC_BUILD=0`. The
commercial S3 runtime branch therefore retains `UnprovisionedS3CloudTrust`;
the TEST_ONLY startup composition is not selected. ESP-TLS DS peripheral is
enabled in the effective config. This confirms build-profile separation only;
it does not prove device eFuse or silicon state.

```text
Commercial application SHA-256: c2c886ddee480b2363a7b50b7bdd58f45c3e19bc212ba8bd3a170de046e494bb
ESP image validation hash:      9642656a2d35d17774b9f9e90b0f418b3ca956f5af787a241a5149b25d45617f
ELF SHA-256:                    57850c4ed02a35179b7db3557a1df9b60f5128e90fc54e043a3ff712b45c033a
Effective commercial sdkconfig: 79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b
Product defaults SHA-256:       be0624e0d4efb47d6e3868a42c7a5925c5be1dea8520df644271ad2e66a4c024
Image size:                     2,168,160 bytes (0x211560)
Partition table SHA-256:        4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe
```

The image metadata reports app version `0d7a5f0-dirty`. At build time the
only tracked differences from that commit were documentation files; firmware
source and build inputs were unchanged from commit `8bd9cf3` plus the
validation-registry-only correction `0d7a5f0`. The image was built from the
canonical worktree and is not a release or installed image. Its 0x400000-byte
application slot has 48% free. TEST_ONLY image hashes above remain the earlier
independent build; the commercial artifact is not interchangeable with it.

## Limits and remaining blockers

This is **not** a complete composed S3-to-caregiver E2E. The target expects a
fresh signed configuration envelope on USB at startup, but there is no fixture
sender in this change. The repository backend also has no `/v1/test/authority/refresh`
handler or signed-time proof service matching the target requests. Therefore
there is no valid end-to-end authority lease, no runtime proof that product
startup reaches CloudSync-ready, and no NodeHealth request from this target to
backend/PWA. The existing 4/4 localhost E2E exercises the existing host
identity/backend/caregiver path, not this new target adapter. Do not claim
GS-40 software integration complete from host tests or compilation.

No target was flashed or run. Physical GS-40 PHY-01..06 and GS-68 acceptance
remain NOT_RUN; PHY-05 still needs a second independently enrolled legacy
profile Node or approved equivalent. Existing P0 `product_status=PARTIAL` and
Hub `clean migration commits` assertion failure remain open. Commercial D05,
D12, D06, registry/certificate lifecycle, rollback-resistant time-floor and
physical security decisions remain outside this TEST_ONLY implementation.

The canonical GS-177 simulator worktree/branch was not read or modified and
has not been integrated. Its future integration is a separate next session;
first inventory its uncommitted files against canonical, preserve its evidence,
reuse canonical HubRuntime/CloudSync/security/event code, and resolve replay
fencing without bypassing the production fence. Do not begin GS-104 R01–R09.
This checkpoint is ready for an explicit writer handoff to that separate
session after the documentation and Jira updates are committed and pushed.

Jira evidence comments: GS-40 `11379`, GS-109 `11380`, and GS-148 `11381`.
All remain In Progress; no issue was marked complete.
