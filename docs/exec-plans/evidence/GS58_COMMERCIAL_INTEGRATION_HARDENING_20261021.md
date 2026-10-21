# GS-58 Commercial Integration Hardening — 2026-10-21

**Disposition:** implementation hardening on isolated task branch; production
onboarding and physical qualification remain blocked/not run. This report records
source behavior and test evidence; it does not approve D1/D2 commercial policy.

## Scope and source state

```text
BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=GS-D032/GS-109 + GS-58 protected credential-store integration; no new locked decision
DECISION_IDS=GS-D032
TASK_SCOPE=initial claim retry safety, Wi-Fi candidate staging/rollback, transfer-state verification, runtime wiring audit
OUT_OF_SCOPE=Security 2 activation, production key/eFuse lifecycle, physical onboarding, Home transfer disposition policy
```

Canonical base was `2b8dee5dc0494a06bcc34210cd08bdc63e6339b0` on
`feature/r1-commercial-baseline`. Because another canonical writer was active,
the owner-authorized task branch is
`feature/gs58-integration-hardening-20261021`, in
`/home/udaybhan/projects/Ghar_sajag_gs58_integration_hardening`. Canonical was
not modified. Final task-branch commit and remote verification are recorded
below after delivery.

## A. EXISTING_IMPLEMENTATION_REUSED

The changes reuse the existing `HubOwnershipRegistry`, `WifiSetupPermitGate`,
`WifiOnboarding`, `WifiCredentialStore`, encrypted-NVS slot adapter, bounded
S3 scanner, reconnect policy, and existing GS-109/GS-168 ownership and identity
contracts. No second ownership registry, credential manager, Wi-Fi manager,
commissioning protocol, issuer, Android flow, or CloudSync implementation was
added. Android remains discovery-only and unchanged.

## B. REPRODUCED_DEFECTS

1. **Initial claim lost response:** `claim_home()` committed epoch 1 but an exact
   retry after the client lost the response was rejected as already claimed.
   Exact immutable operation/history matching was absent.
2. **Wi-Fi candidate activation:** onboarding's commit path changed the active
   credential selector immediately after storage, before association, Internet,
   cloud authentication or current Home readiness had been established. That
   could select a bad candidate and strand the existing station configuration.
3. **Transfer:** transfer completion remains an intentional fail-closed block;
   this is not treated as an implementation defect because data disposition and
   rebind policy are not approved.

## C. FALSE_POSITIVES_OR_INTENTIONAL_GATES

- A newly registered unclaimed Hub is at epoch 0. The setup-permit gate rejects
  epoch 0 and accepts only a nonzero target epoch. This guard is retained. The
  missing contract is a GS-109 reservation/finalization transaction that can
  authorize an offline initial-claim setup permit before the Hub becomes ACTIVE.
- `complete_transfer()` raises
  `pending_old_home_data_disposition_and_local_rebind_unapproved`. Both Home
  bindings are fenced while pending; old local history is preserved. This is a
  deliberate policy/data-safety gate, not a defect to bypass.
- Commercial encrypted storage is unavailable unless existing security flags,
  encrypted key/data partitions and an approved device-key custody verifier
  are present. The current development profile does not establish those facts.

## D. SOURCE_FIXES_IMPLEMENTED

- **Initial claim retry:** `claim_home()` now returns the already committed
  epoch-1 result only for the exact original claim whose Hub proof fingerprint,
  Home, actor, authorization reference and proof reference match the immutable
  CLAIMED history row. Different actor/Home/proof, revocation, later epoch or
  transfer remain conflicts. This is receipt recovery, not a second claim.
- **Credential candidate staging:** the existing two-slot backend now exposes
  stage/load/activate/discard operations. Staging verifies the inactive record
  and leaves the selector unchanged. Activation is a distinct exact-generation
  selector transaction; ambiguous results require verified reread. Initial
  staging writes a nonselecting tombstone so reboot can distinguish a staged
  candidate from uninitialized/corrupt bytes. Sensitive record buffers are
  cleared as before. No plaintext fallback, key generation, NVS formatting or
  erase path was added.
- **Onboarding policy:** the previous commit-and-reconnect path now stages the
  candidate, rechecks the authority generation and setup operation, and
  attempts candidate cleanup if authority changes. It never flips the active
  selector or triggers reconnect. Its result means `CredentialStaged`, not
  setup success or usable connectivity.
- **Coverage:** host tests now exercise power-loss boundaries, restart recovery,
  replacement retaining the old selector, activation/discard generation
  checks, ambiguous storage results, permit epoch 0/1 behavior, competing
  claims, and pending-transfer isolation. Registry, inventory and traceability
  entries were updated to describe staging rather than immediate activation.

## E. FIRST_CLAIM_CONTRACT_STATUS

The existing ownership registry's first committed claim is atomic and uses
epoch 1. Exact lost-response retry is now idempotent. The offline provisioning
permit still cannot be safely issued for a not-yet-active Hub because GS-109
does not specify a reservation lifecycle. Recommended missing semantics
(`PROPOSED`, not implemented or approved): transactionally reserve Hub/Home/
installer/op-ref and target epoch 1 with one-use nonce and bounded TTL; issue a
permit bound to that reservation, fresh Hub nonce/boot/session, signer
generation and expiry; finalize only if reservation, revocation generation and
proof remain current; exact finalized retry returns the same result; expiration
or revocation cancels the reservation without activating a Home. Competing
reservations must have a single winner.

## F. WIFI_ROLLBACK_STATUS

Candidate staging and old-active preservation are implemented and host tested.
No product runtime currently verifies a candidate's association, Internet,
backend authentication and current Home/epoch before calling explicit
activation. The old active slot remains selected during staging and can be
loaded after restart. An interrupted selector update is only accepted after
readback resolves the active generation; otherwise it reports outcome unknown.

**Activation remains disabled in product flow.** The exact activation
qualification sequence and the authority/permit needed to remain valid from
staging through verification require a product/security decision. In
particular, the current one-use permit completion happens after staging, so it
cannot by itself authorize a later activation. Retention/purge timing for the
old slot, retries, and recovery after a candidate was network-tested but not
activated also need an approved contract. No password or network readiness is
claimed by staging.

## G. OWNERSHIP_TRANSFER_STATUS

Transfer remains fail-closed. Tests demonstrate competing transfer rejection,
old- and new-Home admission denial while pending, denial of a new claim during
pending transfer, denial of stale exact event retry, restart persistence of
pending state, and preservation of old Home data. The historical Node
enrollment record is retained; backend admission is fenced while its Hub is not
ACTIVE. Completion still requires approved old-Home journal/outbox disposition,
Node credential revocation, new-Home proof/rebind, offline-Hub recovery and
outstanding COMMITTED-receipt behavior. No resident data is erased or silently
transferred.

## H. PRODUCTION_RUNTIME_WIRING

The S3 target build compiles the scanner, onboarding policy, permit gate,
two-slot backend and encrypted-NVS adapter. The actual runtime currently
initializes station mode with RAM Wi-Fi storage; no live credential source calls
`esp_wifi_set_config`. No Security 2 session, live GS-109 permit verifier,
protected-device-key verifier, production Wi-Fi credential provider, or
commercial CloudSync/trusted-time provider is instantiated by `app_main()`.
GS-40 bootstrap remains TEST_ONLY. These are activation gaps, not reasons to
substitute test trust in the commercial build.

## I. TEST_RESULTS

Focused results on this task source (host/software only):

| Command | Result |
|---|---|
| `make gs58-onboarding-host-test gs58-credential-slots-host-test gs58-setup-permit-host-test gs58-wifi-host-test hub-ownership-lifecycle-host-test` (from `code/`) | PASS: onboarding 41 checks; credential slots 48; permit 33; reconnect 77; ownership lifecycle 8/8 |
| Same four C++ suites with `-fsanitize=address,undefined` (`ASAN_OPTIONS=detect_leaks=0`, `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`) | PASS: same check counts |
| `make validation-framework-test feature-coverage-test` (from `code/`) | PASS: framework 51/51; traceability 222 features, 275 source modules, 26 physical cases; mappings 22/22 |
| `python3 code/scripts/build_validation_targets.py` | PASS: paired ESP-IDF 6.0.3 C3/S3, no flash. A committed-source incremental rebuild then passed on `47be1e3`; artifact report under ignored `code/build/validation_targets/gs116-k2q9tp5x/final-report.json`. |
| Android CI | NOT_RUN in this task; no Android source changed. Prior source-matched run remains evidence only. |
| Physical qualification | NOT_RUN; no board or phone accessed. |

`validation-fast` and `release-gate-final` were not run. Existing aggregate
failures and P0 status are not altered by this focused task.

Committed-source target provenance:

- Source commit: `47be1e3abcac54af37c4b5ea4407c9420b82372b`
- Source fingerprint: `b29f06c602a804c47e53e7aaabf986cd94431ddb4d415def1c9331e0df60382a`
- Project version: `47be1e3-gs116-b29f06c6`; ESP-IDF 6.0.3; profile
  `GS_HIL_BUILD=OFF`, `GS40_TEST_ONLY_CLOUDSYNC=OFF`,
  `GS_S3_DIAGNOSTIC_ONLY=OFF`.
- C3 application: 940,608 bytes; SHA-256
  `38e12e4f730a5afabf017d4b6ba094b32afd54dd09515ebd396ade2251c8d610`.
- S3 application: 2,193,264 bytes in a 4,194,304-byte OTA slot; full-file
  SHA-256 `1cbda4501ac41bda39e0a47af3db75777f4bdaa4947bcddcaf24b6b4ad611b3e`;
  ESP image validation hash
  `200ac124511950950055512a1f99bcd3b21adf8ca7924e80f5b1ba0b48048f02`.
- The S3 embedded C3 image is byte-identical to the paired C3 artifact (both
  940,608 bytes and SHA-256 above).
- Effective generated S3 sdkconfig SHA-256:
  `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`.
  It uses the development partition table; Secure Boot, Flash Encryption and
  NVS encryption are disabled in this non-flashing development profile. This
  does not qualify or activate a commercial security image.
- `esptool.py --chip esp32s3 image_info` reported a valid checksum and
  validation hash. Target builds compile the storage/onboarding code; they do
  not prove runtime composition or hardware behavior.

## J. REMAINING_SECURITY_DECISIONS

1. D1: approved per-device Security 2 secret generation, station custody and
   delivery; exact GS-109 initial-claim reservation/finalization, permit
   renewal, transfer/revocation race and recovery semantics.
2. D2: approved device-key custody and provisioning lifecycle for Secure Boot,
   Flash Encryption, encrypted NVS key/data partitions and recovery. No eFuse
   or key operation was performed.
3. Credential activation: exact network/cloud/Home acceptance conditions,
   permit lifetime/re-authorization, previous-slot retention and cleanup after
   ambiguous tests.
4. Transfer: old-Hub local data/outbox disposition and Node re-enrollment
   behavior before a new Home can become active.

These implementation findings do not change the owner-selected architecture
from “under review” to an approved commercial decision. `GS-D031`, `GS-D032` and
`CONTEXT_VERSION` are unchanged.

## K. COMMERCIAL_ACTIVATION_BLOCKERS

- No live Security 2 provisioning transport or unique production proof.
- No approved GS-109 permit issuer/reservation contract for initial claim.
- No production encrypted-NVS key custody and qualified protected partition
  layout.
- No runtime network verification + authorized explicit credential activation
  flow.
- Commercial CloudSync identity and trusted-time providers remain
  fail-closed/unavailable.
- Android stays BLE discovery-only; no password entry/submission is exposed.
- Real S3, phone, physical Wi-Fi and commercial acceptance remain NOT_RUN.

## L. FILES_CHANGED

Source and registered validation:

- `code/backend/ghar_sajag/ownership_registry.py`
- `code/firmware/hub/connectivity/wifi_credential_store.hpp`
- `code/firmware/hub/connectivity/wifi_credential_slots.hpp`
- `code/firmware/hub/connectivity/wifi_credential_slots.cpp`
- `code/firmware/hub/connectivity/wifi_onboarding.hpp`
- `code/firmware/hub/connectivity/wifi_onboarding.cpp`
- `code/tests/cpp/gs58_wifi_credential_slots_validation.cpp`
- `code/tests/cpp/gs58_wifi_onboarding_validation.cpp`
- `code/tests/cpp/gs58_wifi_reconnect_validation.cpp`
- `code/tests/cpp/gs58_wifi_setup_permit_validation.cpp`
- `code/tests/python/test_hub_ownership_registry.py`
- `code/Makefile`, `code/validation/suites.json`
- `docs/validation/MASTER_TRACEABILITY.csv`
- `docs/validation/SOURCE_FEATURE_INVENTORY.csv`

Evidence and canonical work-state records:

- `docs/exec-plans/evidence/GS58_COMMERCIAL_INTEGRATION_HARDENING_20261021.md`
- `docs/product/DECISION_LOG.md`
- `docs/product/R1_WORK_STATE.md`

Generated ESP-IDF `code/firmware/hub/target/esp32s3/idf/managed_components/`
is preserved as untracked data and excluded from the commits.

## M. COMMIT_SHA_AND_REMOTE_VERIFICATION

Implementation commit: `47be1e3abcac54af37c4b5ea4407c9420b82372b`.
The evidence/work-state closeout is delivered on the same authorized task branch.
After push, `git ls-remote` must match the final local task-branch HEAD; the
exact resulting delivery SHA is included in the execution handoff and the GS-58
Jira comment. Canonical remains at the separate base and is not merged by this
task.

## N. JIRA_UPDATES

GS-58 comment `11499` records candidate staging, focused tests, committed-source
build hashes and the D1/D2 blockers. GS-109 comment `11500` records exact
epoch-1 claim retry behavior and the missing initial-claim reservation
contract. Both tickets remain In Progress.

## O. EXACT_NEXT_ACTION

The next product action is to settle GS-109 initial-claim reservation/finalizing
semantics, the Wi-Fi verification/activation and permit-renewal contract, D2
device-key/partition custody, and transfer data disposition. Only after those
contracts are approved can the Security 2, encrypted NVS, network verification,
and authenticated Home-claim providers be composed. Keep credential activation,
commercial provisioning and physical tests blocked until then.
