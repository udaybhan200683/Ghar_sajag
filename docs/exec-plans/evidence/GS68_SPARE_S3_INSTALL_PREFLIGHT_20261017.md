# GS-68 spare S3 install preflight — 2026-10-17

**Disposition: NO-GO for installation or target tests.** This is a read-only
source/build/runner review. No board, USB device, serial port, power, flash,
reset, network stimulus, key provisioning, eFuse, or security configuration
was accessed or changed.

## Checkpoint and preserved state

- Canonical path: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Local HEAD, origin tracking HEAD, and `git ls-remote` HEAD at start:
  `c4bc525e1fea8555ab30affc5b9e9926703c7f8e`
- Tracked worktree: clean. Existing untracked PWA, Android, managed component,
  C8/GS-114, and GS-40 evidence were left unchanged and unstaged.
- Existing worktrees were not changed. A prior backend process in the separate
  `Ghar_sajag_gs177` worktree was explicitly outside this task and not signaled
  or interrupted.
- Context preflight: PASS (reported in the preceding checkpoint; repository
  source and context version remain unchanged).

## Candidate identity and configuration

The ignored build artifact was found at:

`code/build/validation_targets/gs68_cloudsync_diag_20261017_usb_console/build/gs_r1_s3_hub.bin`

| Item | Verified value |
|---|---|
| Artifact size | 473,312 bytes |
| App SHA-256 | `c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65` |
| Build report | `code/build/validation_targets/gs68_cloudsync_diag_20261017_usb_console/gs68_build_report.json` |
| ESP-IDF / target | `v6.0.3` / ESP32-S3 |
| Profile | `GS68_CLOUDSYNC_DS_MTLS_HIL` (TEST_ONLY diagnostic) |
| Profile SHA-256 | `7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72` |
| Effective sdkconfig SHA-256 | `ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a` |
| Console | USB Serial/JTAG primary; UART0 primary unset; USB secondary unset; driver-backed blocking stdin |
| Build report source commit | `a5d2806b40023d0c42a90d082187398416fb956c` |
| Build report source `code/` tree OID | `c5dccea2fd0e1fd3f8d93e608502237f52019717` |

The binary, sdkconfig, and checked-in profile were rehashed during this
preflight and match the build receipt. The current HEAD's `code/` tree matches
the recorded source tree, and the diagnostic source/profile/build inputs have
no source diff since the build commit. The whole repository commit is now
`c4bc525e1fea8555ab30affc5b9e9926703c7f8e`, however, so this is code-tree
equivalence rather than an exact current-HEAD build.

The TEST_ONLY diagnostic keeps production composition unchanged and has no
provisioned DS/HMAC identity, production credential, production time anchor,
or commercial endpoint. A selected DS peripheral in compile configuration is
not silicon signing evidence. Physical state remains NOT_RUN.

## Installation blockers

1. **Fixture identity is incomplete.** The checked-in fixture template remains
   `GS68-SPARE-UNASSIGNED`, without MAC, USB serial, `/dev/serial/by-id` path,
   custodian, or physical approval. Historical notes report an S3 N16R8,
   BUSID `3-1`, COM10 / `/dev/ttyACM0`, and installed baseline digest
   `c905af73419c84af7a1d986dada3724da7e654b4d7eaa0235bd06e515902f8ef`; none
   of these were re-observed in this task.
2. **No verified recovery image is staged.** A targeted search of discovered
   named S3 app binaries under `code/build` found no binary matching the
   reported baseline digest. No independently verified rollback image was
   identified. Do not substitute the superseded `e8e0a623...` candidate or any
   unverified build artifact.
3. **Partition compatibility is unknown.** The candidate app is linked for
   `partitions.development.csv`: NVS at `0x9000`, OTA metadata at `0xf000`,
   `ota_0` at `0x20000` and `ota_1` at `0x420000`. Its partition table hash is
   `4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe`. The
   installed baseline's table was not verified. App-only installation is not
   approved until compatibility is established; full project flashing would
   also change bootloader, partition table, and OTA metadata and is not an
   acceptable fallback.
4. **Formal GS-68 runner source binding fails for this candidate at current
   HEAD.** The runner requires fixture `source_commit == git HEAD`; the image
   embeds `a5d2806...`, while current HEAD is `c4bc525...`. The equal `code/`
   tree OID does not satisfy that exact-commit rule. The fixture also has no
   source commit or approval, so the runner cannot execute.
5. **The registered runner does not implement this console diagnostic.** It
   sends `RUN_CASE` for official GS68-PHY-001..010 and requires signed backend
   receipts. `OBSERVE`, `LOAD_TIME_KEY`, `TIME_CHALLENGE`, and `TIME_PROOF` are
   auxiliary diagnostic events, not registered-case adjudication. The signed-
   time helper labels its command `GS68-PHY-003`, while catalogue PHY-003 is
   certificate validation. Do not report the auxiliary proof as PHY-003 PASS;
   case mapping/harness adjudication needs correction before formal evidence.
6. **Persistent TEST_ONLY state needs explicit scope.** A valid diagnostic
   signed-time proof commits a floor into NVS namespace `gs68time`. Any
   separately approved run must explicitly allow only this namespace write;
   no erase, factory initialization, or unrelated NVS mutation is in scope.
7. **The full negative proof matrix is not operator-ready.** The current
   ephemeral host helper creates one RSA-3072 key per process and signs one
   outstanding challenge. Wrong nonce and replay can be exercised with that
   challenge, but invalid-signature, expired-proof, and stale-generation cases
   need additional fixture support or separate authorized sessions. Do not
   claim them covered by the current one-proof helper.

## Safe, ordered test plan (not authorized to execute)

### P1 — Identify and bind the spare and image

1. Obtain separate approval for **read-only identity observation only**. Name
   the fixture owner/operator, purpose, time window, observer, and evidence
   destination. Do not infer current identity from the historical BUSID/COM10
   mapping.
2. With that approval, record board marking/revision, S3 MAC, USB serial,
   stable `/dev/serial/by-id` path, 16 MiB flash / 8 MiB PSRAM provenance, and
   compare all identifiers with the protected C8/GS-114 inventory. Stop on any
   collision or ambiguity.
3. Locate and hash-verify a restoration image and its matching partition table,
   or obtain an explicitly approved recovery method. Verify the installed
   partition layout without destructive reads. No recovery artifact currently
   satisfies this gate.
4. Resolve source binding for any future formal run: either build the exact
   source at the then-current approved commit, or obtain a reviewed change to
   the runner's binding policy. Do not edit the fixture to claim a false
   source match.
5. Select a unique evidence directory and record image/profile/sdkconfig,
   partition-table and build-report hashes. Confirm the candidate remains
   `c0fb82...` before any approval request; any source/config/build change
   invalidates this digest and requires a new review.

### P2 — Install and observe the USB command console

This phase requires a second, explicit installation authorization after P1 is
complete. It must name the exact fixture, image digest, flash utility and
arguments, operator, evidence destination, backup/recovery plan, stop rules,
and permitted actions. The candidate build helper's generated app-flash
address is `0x20000`; do not infer that app-only flashing is safe until the
installed partition table is proven compatible. Do not use a full project
flash as a shortcut.

If authorized, capture boot and diagnostic READY output; require the running
image identity to match the approved candidate before proceeding. Send the
bounded `OBSERVE` line after startup, split into delayed fragments with CRLF;
then malformed input followed by valid input; then two sequential valid
commands. Require corresponding responses, no unexpected app exit/reset, and
no network request. The parser's expected rejection of malformed/oversized
input is a subtest observation, not a firmware PASS by itself. Any identity,
reset, timeout, over-bound response, or unexpected network activity is STOP;
preserve evidence, quarantine the fixture, do not reset/reflash automatically,
and invoke recovery only under a separately approved recovery action.

The diagnostic command frame is bounded JSON terminated by CRLF. The
currently accepted harmless observation frame is:

```json
{"schema":"gs68.target.command.v1","case_id":"GS68-PHY-003","challenge_nonce":"0000000000000000000000000000000000000000000000000000000000000000","operation":"OBSERVE"}
```

`GS68-PHY-003` is currently the diagnostic's accepted envelope value but is
already assigned to certificate validation in the formal catalogue. This
example is for auxiliary console smoke only; it must not be recorded as
official PHY-003 execution. Before formal adjudication, give the diagnostic
its own approved case identifier and update the runner/schema mapping. The
current safe response is `event=command_result`,
`result=OBSERVED_NO_ACTION`, `physical=NOT_RUN`. For the fragmented-input
subcheck, split this exact line into two writes separated by a delay, append
CRLF only to the second write, and require exactly one response. Then send a
malformed line followed by the same valid line and require explicit rejection
plus one valid response. Finally send two valid frames in one write and
require two ordered responses. An oversized line (>1024 bytes) should be
rejected/drained before a subsequent valid frame is accepted. Do not turn an
expected parser rejection into case PASS if the following response is missing.

The checked-in formal runner uses `/dev/serial/by-id/...`, verifies exact USB
identity before opening the port, and sets DTR/RTS low. Its existing `RUN_CASE`
interface is not a harness for the auxiliary command smoke sequence. Until
that gap and the PHY-003 label collision are resolved, label these observations
**auxiliary TEST_ONLY diagnostic evidence**, not official GS-68 physical case
PASS.

### P3 — TEST_ONLY PSA RNG and signed-time checks

Only after P1/P2 pass and a separately approved scope includes diagnostic
commands and the `gs68time` NVS namespace:

1. Start an isolated host `gs68_signed_time_fixture.py` session; its ephemeral
   private key must remain in process memory and never be logged, written, or
   committed. Load only the emitted TEST_ONLY public key on target.
2. Request a fresh target challenge. Record nonce hash, nonzero boot
   generation, and `random_source=ESP32_S3_PSA`; this is the first silicon PSA
   RNG evidence, not a host simulation.
3. Sign the exact current challenge and verify the target reports
   `RSA3072_SHA256_VERIFIED`, TEST_ONLY, and physical diagnostic result. Record
   the NVS time-floor write and test-only key/authority identifiers.
4. With the same challenge, send a wrong outer nonce and require rejection,
   then the valid proof, then replay and require rejection. Additional bad
   signature, expiry, and stale-generation cases remain NOT_RUN until helper
   support/session plan is approved.
5. Any cloud/network request, production trust selection, unexpected identity
   readiness, or state write outside `gs68time` is STOP/FAIL. Do not exercise
   DS signing or mTLS under this diagnostic-only approval.

Every result is separately classified PASS, FAIL, BLOCKED, or NOT_RUN with
raw capture hash and fixture/image binding. Host tests and build output remain
software evidence and cannot satisfy these physical cases.

## Installation authorization packet (prepared, not approved)

**Current decision: NO-GO; there is not yet a safe installation packet to
sign.** After P1 prerequisites above are resolved, the owner approval must
explicitly state:

- spare fixture ID, board MAC/revision, USB serial and verified stable port;
- candidate source commit, app digest
  `c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65`, profile
  digest `7d13aa...`, sdkconfig digest `ff3150...`, partition table digest,
  and matching running-image verification method;
- exact install command/method, named operator, date window and no C8 fixture;
- evidence directory, capture/hash manifest, and named review owner;
- verified restore image and its hash, restore method/operator, quarantine
  owner, and explicit stop/recovery steps;
- initial allowed action list (install, boot, non-resetting capture, bounded
  console commands) and whether the `gs68time` NVS namespace write is allowed;
- explicit prohibitions on DS/HMAC/eFuse provisioning, Secure Boot, Flash
  Encryption, production credentials/endpoints, network stimuli, erase,
  factory initialization, and unrelated NVS writes;
- approved case IDs, plan digest, start/expiry, and a Jira approval comment.

The formal runner also requires an APPROVED fixture manifest bound to the
plan hash and selected case IDs, plus exact typed operator confirmation. Those
software guards do not replace owner authorization. Given missing identity,
recovery and case-binding items, requesting flash authorization now would be
premature.

## Historical results and remaining blockers

Prior successful software results remain as reported in
[`GS68_USB_COMMAND_CONSOLE_20261017.md`](GS68_USB_COMMAND_CONSOLE_20261017.md):
1,736 parser/framer assertions; cloud-trust provider 5 suites; mTLS 9/9;
backend security 14/14; GS-40 identity/time/caregiver 4/4; GS-168 registry
10/10; NodeHealth 5/5; GS-130 runner 72/72; validation framework 47/47;
traceability 208 features/220 modules/24 physical cases/22 mapping tests; and
non-flashing ESP-IDF 6.0.3 build PASS. They were not rerun for this read-only
preflight.

Still NOT_RUN: silicon PSA RNG, RSA proof verification, USB receive behavior,
DS signing, live mTLS, GS-68 physical acceptance, and GS-40 PHY acceptance.
Existing recorded blockers remain visible: Hub migration assertion
“clean migration commits”; Hub sanitizer timeout at 600 seconds; P0
`product_status=PARTIAL`; production CA/issuer and trust custody; protected DS
key/eFuse lifecycle; authenticated-time authority and rollback-resistant
storage; registry/certificate lifecycle; Secure Boot, Flash Encryption and
recovery policy; and separate real-target DS signing/mTLS qualification.

**Next exact step:** obtain owner approval for read-only identity observation
of the named spare. Then verify fixture/C8 exclusion and locate/approve a
compatible recovery image/partition plan. Reconcile runner source/case binding.
Only after those steps, submit a new digest-bound installation authorization;
do not execute installation on this receipt.
