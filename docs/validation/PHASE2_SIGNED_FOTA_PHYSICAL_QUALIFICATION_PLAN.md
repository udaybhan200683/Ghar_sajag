# Phase-2 Signed FOTA Physical Qualification Plan

**Prepared against repository HEAD:** `51e99e1f415af9cc896085b322d461b4720322aa`  
**Branch:** `feature/hw-m1-4-hil-phase2`  
**Status:** **PLAN — NOT YET PHYSICALLY EXECUTED**  
**Last physically qualified firmware:** `7bc2a33`  
**Latest historical physical evidence:** `evidence/hil/runs/20260924T094521.398370Z`

> Authenticated transport is not firmware publisher authenticity. SHA-256 integrity is not signature authenticity. A target build is not physical qualification. Offline signature verification is not physical OTA verification. This plan does not cover Secure Boot, eFuse programming, or production PKI.

## 1. Purpose and scope

This document defines a focused physical qualification of the authenticated,
signed C3 FOTA path on the existing one-Hub/one-C3 fixture. It specifies the
images, initial state, physical sequence, evidence, and pass conditions. It is
a reusable procedure; it records no completed physical campaign.

## 2. Feature state before physical qualification

The implementation checkpoint includes secure FOTA v2 wire framing with a
192-byte data-chunk bound, the Hub authenticated FOTA route, C3 authenticated
admission, authenticated ACK routing, streamed SHA-256 integrity, a fail-closed
signed-image gate, a signed-app-on-update profile, external test-key signing,
offline signature verification, and offline tamper rejection.

These implementation and offline results do not establish physical transfer,
signature enforcement on target, or boot recovery. Refer to the architecture
and traceability documents for implementation ownership and current status.

## 3. Existing fixture limitation

The existing command:

```bash
make -C code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2 hil-checkpoint-fota
```

refreshes the fixture setup and preflight, then runs the Phase-1 smoke and the
legacy raw Phase-1 FOTA path. It does **not** qualify the authenticated secure
signed-FOTA implementation.

## 4. Minimum fixture adaptation

Reuse the existing USB, serial, fixture setup, preflight, provenance, and
evidence supervisor. Do not create a general-purpose HIL framework. The
focused campaign needs a test build that keeps HIL control available while
routing FOTA through the secure owner-task path. It must establish or verify
an exact authenticated Hub/C3 association, then trigger
`request_authenticated_fota()` for that exact enrolled Node. It must build
signed A/B artifacts, embed the selected signed artifact in the Hub image,
and retain production fail-closed behavior and production/HIL isolation.

The ordinary HIL profile currently routes to raw FOTA. The production profile
has no external FOTA trigger. A focused secure-FOTA fixture profile and
checkpoint command are therefore prerequisites; neither is claimed to exist
in this plan.

## 5. A image requirements

- Built for the signed-app-on-update C3 profile.
- Signed with the same trusted test key used for valid B.
- Has a distinct, recorded app version; preserve its signature block.
- Record signed artifact SHA-256, size, effective config/profile, and signing
  public-key fingerprint.
- Record which OTA partition is active after installing A.

## 6. B image requirements

- Built for the same ESP32-C3 target and compatible signed-app test profile.
- Signed with the same key as A and a different app version.
- The exact signed artifact transferred must be embedded byte-for-byte in the
  Hub image.
- Record B's signed artifact SHA-256 and size, the Hub embedded-image SHA-256,
  and the Hub image provenance.
- Confirm the signed image fits the C3 OTA slot and the final Hub image fits
  its OTA slot. The current partitions are `0x1e0000` bytes per OTA slot; size
  checks must use the final campaign builds.

## 7. Negative image requirements

Use an image whose transfer remains valid: Hub/C3 authenticated transport must
accept it and the declared SHA-256 must match its transferred bytes. Its app
signature must be invalid for the public key trusted by running A. Prefer a
same-target image signed by a different disposable test key, or a valid signed
image altered after signing with the updated transfer digest.

The test must reach ESP-IDF's app-signature verifier. A transport rejection,
AEAD failure, digest mismatch, or timeout alone does not prove signature
rejection.

## 8. Signing-key policy for qualification

- Use a disposable RSA-3072 test key stored outside the repository.
- Never include private-key contents in logs or evidence; record only the
  public-key fingerprint.
- Do not describe a test key as a production publisher key.
- Do not program eFuses.

## 9. Build and artifact provenance

For A, valid B, wrong-signature image, and each Hub image, record:

- Source repository HEAD and dirty state.
- App version and build profile/configuration.
- Signed artifact SHA-256 and byte size.
- Signing public-key fingerprint, where applicable.
- Hub embedded-image SHA-256, matched against the selected C3 artifact.
- Applicable partition size and fit result.

Use the signed-app build/sign flow with an external key. Build versions must
be distinct for A and B. Do not rely on temporary or ignored build paths as
artifact identity; record hashes and provenance in the campaign evidence.

## 10. Required initial hardware state

- Signed A is installed and running on the C3, with its trusted key intact.
- Hub and C3 have the exact enrolled association and an active authenticated
  session.
- Hub identity, Node physical identity, logical attribution, and current
  session are recorded.
- Active C3 OTA slot is known.
- C3 sensing is ready.
- A baseline application event is received and acknowledged before FOTA.

## 11. Physical qualification sequence

### A. Establish identity, session, and baseline

Run the fixture setup and preflight. Record Hub/C3 identity, image provenance,
active slot, A version, and authenticated session. Confirm sensing readiness
and a baseline application event/ACK.

### B. Wrong-signature attempt first

1. Use a Hub image embedding the wrong-signature C3 artifact.
2. Start FOTA through the authenticated secure path for the exact Node.
3. Confirm the transfer reaches ESP-IDF signature verification and is rejected.
4. Confirm boot selection remains on A and A remains operational.
5. Confirm an application event still receives an ACK after rejection.

### C. Valid signed B update

1. Use a Hub image embedding the valid B artifact, signed by A's trusted key.
2. Start the authenticated transfer and verify the streamed SHA-256 result.
3. Confirm signature acceptance and alternate-slot activation.
4. Observe the fresh reboot, boot-health gate, and B app version.

### D. Post-upgrade recovery

Confirm authenticated rejoin with a fresh session, sensing readiness, and a
post-upgrade application event/ACK. Record final retained/in-flight state,
unexpected resets, and relevant resource/heap evidence.

## 12. Evidence requirements

Capture:

- Hub/C3 versions, source commit, dirty state, and build provenance.
- A, B, and negative image hashes/sizes; public-key fingerprint; signed-app
  config symbols; Hub embedded-image hash.
- Exact Node identity and authenticated session before and after reboot.
- Transfer ID and authenticated ACK progress.
- Digest and signature verification outcomes, including evidence that the
  negative image reached signature verification.
- OTA partition before each attempt and after rejection/activation.
- Fresh reset/boot evidence, boot-health decision, B version, and sensing
  readiness.
- Post-rejection and post-upgrade application event/ACK evidence.
- Unexpected reset count, retained/in-flight counts, and relevant heap or
  resource observations.
- Campaign evidence directory and per-case PASS/FAIL results.

## 13. PASS criteria

These are planned criteria and are **not yet passed**.

### `SIGNED_FOTA_NEGATIVE`

PASS only if authenticated transport and the declared image digest succeed,
ESP-IDF signature verification rejects the image, the boot selection remains
on A, and A continues to operate with an acknowledged application event.

### `SIGNED_FOTA_A_TO_B`

PASS only if the correctly signed B image transfers through the authenticated
path, passes digest and signature verification, activates the alternate slot,
reboots, and reports the expected distinct B version after the boot-health
gate.

### `POST_UPDATE_RECOVERY`

PASS only if B re-establishes an authenticated session, reaches sensing-ready,
and produces an application event acknowledged by the Hub, with final
retained/in-flight counts and unexpected resets reported and within campaign
acceptance.

Overall signed-FOTA qualification requires all three results with fresh,
matching provenance and complete evidence.

## 14. Failure and stop conditions

Stop and report FAIL or BLOCKED, as appropriate, on any of the following:

- Provenance or device identity mismatch.
- A is not actually signed, or A/B do not share the intended trusted key.
- A and B versions are not distinct.
- Signed artifact does not fit its OTA slot, or Hub embeds a different image.
- The wrong-signature test fails before reaching the signature verifier.
- Boot selection changes after the negative attempt.
- B fails to boot, pass its health gate, rejoin, reach sensing-ready, or
  deliver an acknowledged application event.
- Unexpected reset or recovery evidence is ambiguous.
- Required per-case evidence is absent or stale.

Do not convert a blocked prerequisite or missing fixture into PASS.

## 15. What this qualification proves

If all planned cases pass, this bounded campaign proves on the tested
one-Hub/one-C3 fixture that the authenticated physical FOTA path transfers a
signed image, accepts a valid signature, rejects a wrong signature before
activation while preserving A, activates a valid B in the alternate slot,
passes the configured boot-health gate, performs authenticated rejoin, and
supports a working application event after upgrade.

## 16. What this qualification does not prove

It does not prove:

- Hardware Secure Boot, eFuse protection, or resistance to physical flash
  rewriting.
- Production signing-key custody, manufacturing PKI, or production publisher
  identity governance.
- A complete anti-rollback policy or complete board/version authorization.
- Multi-C3 RF behavior, ten-node physical operation, or broad/full HIL
  regression.
- Electrical power-cut, brownout, current, battery endurance, optical PIR,
  or house-range RF qualification.

## 17. Execution Results

Status: **NOT YET EXECUTED**

Future runs should add:

- Execution date.
- Repository HEAD.
- A/B versions.
- Evidence directory.
- PASS/FAIL result for each planned case.
- Any limitations or blocked prerequisites.

## 18. Related references

- `docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md` — Phase-2 security and FOTA
  architecture and known gaps.
- `docs/validation/MASTER_TRACEABILITY.csv` — FOTA implementation and
  qualification status.
- `firmware/common/transport/fota_secure_wire.*` — secure FOTA v2 framing.
- `firmware/hub/components/fota/hub_fota_guard.*` and
  `firmware/hub/target/esp32/idf/main/fota_sender.cpp` — Hub authorization,
  sender, and secure routing.
- `firmware/node/fota/secure_fota_adapter.*` and
  `firmware/node/target/esp32c3/idf/main/fota_receiver.cpp` — C3 admission,
  integrity, and OTA receiver path.
- `firmware/node/target/esp32c3/idf/sdkconfig.signed.defaults` and
  `scripts/build_signed_c3.py` — software-signed profile and external-key
  image build/sign verification.
- `tools/hil/qualify.py`, `tools/hil/phase1.py`, and the product `Makefile` —
  existing fixture supervisor and legacy raw FOTA checkpoint ownership.
- `evidence/hil/runs/20260924T094521.398370Z` — historical same-image raw
  FOTA evidence; it is not evidence for this planned secure signed-FOTA run.
