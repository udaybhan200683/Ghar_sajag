# GS-117 — One-event USB-to-Android readiness — 2026-11-06

## Scope and result

Offline source, authorization, and test work only, within the GS-117 one-event
execution-path request. The existing product path is reused. No device, COM, ADB,
network, or authorization activation occurred. No historical policy, receipt,
or hardware ledger was edited.

Historical session 126/sequence 1 (GS-117#11929; GS-179#11849) is the evidence
that the real C3 HIL-injected motion path previously reached authenticated S3
admission, one PostgreSQL row, the caregiver API, and the same EventKey in the
installed Android APK. It is not fresh acceptance. Session 127 is historical
rejoin/liveness evidence. Current readiness still requires fresh fixture and
Android receipts and a separately authorized run.

## Minimal controller correction

The regular controller action runs a five-event campaign. The existing
single-run entry applies Bedroom Morning Routine configuration and Hub-decision
semantics. The controller now accepts the exact request
`{"operation":"motion_event_once"}` on its existing loopback `/api/run`
route and invokes the existing `execute()` pipeline exactly once. It adds no
new network endpoint, serial path, event pipeline, or backend verifier. The
five-event campaign and Morning Routine remain separately gated and unchanged.

The one-event action requires an exact isolated development scope:
`procedures=["motion_event_once"]`, the same singleton allowed-operation list,
one session, a per-procedure limit of one, and motion injection explicitly
authorized. It rechecks the fresh fixture before reservation and compares
device, image, partition, phone, and identity fields after reservation. A
post-reservation change consumes the one-use session and fails closed. There
is no retry, second injection, or fallback to the campaign. Existing
`execute()` checks remain in force: fixture/image freshness, C3/S3 identity,
current runtime/liveness and HIL profile, one fresh EventKey, authenticated
class-0 durable ACK, exactly one persistent PostgreSQL row, authenticated API
projection, and the same EventKey in the actual installed APK. This is a
development USB-input observation, not optical-PIR TC-001 acceptance.

The authorization module accepts `motion_event_once` only as a distinct
single-use operation. Attempting to use that grant for `tc001_campaign` is
rejected. Source-pin review for this operation records a dedicated marker and
requires all operation-specific negative tests in addition to the existing
authorization-negative set. The reviewed source-pin updater was not run
against the old private manifest.

## Source and tool fingerprints

SHA-256 values for the reviewed working-tree sources at this checkpoint:

| File | SHA-256 |
|---|---|
| `code/tools/local/gs117_tc001_console.py` | `e00f6605b41ec6242e7ffa5708cb3abfd9c76d3488d942b4aa5c2aef9a3004d0` |
| `code/tools/local/gs117_hil_authorization.py` | `08051089379fd5f9593be5caf1dcec4d7262de546c25f995d5f53f2cdec53dc9` |
| `code/tools/local/gs117_tc001_serial_windows.py` | `44a2669593ff367fcb9d0a59d4c2d289070906fbb0270b9f1f3929c183f5b8dd` |
| `code/tools/local/gs117_bootstrap_evidence.py` | `21967680bde4f052d3c697ccac43ea334eff5e04fa82cb428b5f91c9257479f3` |
| `code/tools/local/gs117_tc001_readback.py` | `87373b43cbce3036c427fe90723b3edfddc269bbd3d92ca3b63f0f6a688ce312` |
| `code/tools/local/gs117-tc001-backend.sh` | `222d845231ba4f5a70925de71594cf12ae8f23b4eb301f558e4476f28a4487b6` |
| `code/tools/local/gs179-laptop-server.sh` | `687f5561e950a5e864dba267dc47901eadf72873871cf0cf4ece0c36307a73cf` |
| `code/tools/local/gs179_verified_endpoint.py` | `b8372309b6167f16e38f2c9245cc5d866fbe8ce330b9dfe33c282d94febe3ebc` |
| `code/tests/python/test_gs117_tc001_console.py` | `50050cd4e49e8ea5def851a7cfb81c5f2bf472a77017dcd1d6380ef117464ab4` |

The existing v18 bootstrap fingerprint remains `7cd38e60b291e12ee51572b30f55a83fc8fb393ca188328c06f8e3541eff7ccb`; this one-event path does not run it. Current source pins are not authorization: the existing private DEV manifest is bootstrap-only, one-use already consumed, and source-pin-invalid. Read-only reconciliation found these old-pin → current-source values:

- `serial_helper`: `fc2a30f5b0407d1f0f2300552476991575128cb2b66aa3cdd29a9533a608ceaa` → `44a2669593ff367fcb9d0a59d4c2d289070906fbb0270b9f1f3929c183f5b8dd`.
- `bootstrap_evidence_helper`: `cdcfd90ebbeb3ce270578d0e589aeb88db84ae98778872ddfb36a367e442e929` → `21967680bde4f052d3c697ccac43ea334eff5e04fa82cb428b5f91c9257479f3`.
- `controller`: `bbeb90f1c4e1692ef4d5eac7ccaa6dbb2ee5c37aab03d9d491176d286c958e18` → `e00f6605b41ec6242e7ffa5708cb3abfd9c76d3488d942b4aa5c2aef9a3004d0`.
- `validator`: `34c6ca7cbe2c312c9dcc46ea3fdd8ccc3f3c454e0311b8b67c3d5c32ce3143f7` → `08051089379fd5f9593be5caf1dcec4d7262de546c25f995d5f53f2cdec53dc9`.
- `bootstrap_script`: unchanged at `7cd38e60b291e12ee51572b30f55a83fc8fb393ca188328c06f8e3541eff7ccb`.

The old manifest lists only `protected_gs40_bootstrap` and has `max_sessions=1`; it cannot authorize the motion event. Do not repair or reuse that grant. A future one-event authorization must be provisioned through the existing audited owner process, with the current reviewed source pins and source-review receipt; no grant was created or activated here.

## Future approval package — proposal only

The current receipt mechanism is reused. It already verifies fixture identity,
active application, partition table, OTA metadata, private evidence integrity,
and bounded device operations. The newly added S3 bootloader region is relevant
to the separate receipt task; a bootloader hash alone does not prove rollback.
GS-D029 automatic rollback qualification is not required for the no-flash
one-event run. Fresh C3/S3 application, partition/selector, fixture, and
Android-installation receipts remain required. The stale receipts are not
waived.

### Scope A — one-use installed-device receipt capture

- Home `gs177-test-product`.
- C3 `c3-146393c5d158`, COM4, USB `14:63:93:C5:D1:58`.
- S3 `hub-e072a1d38d34`, COM10, USB `E0:72:A1:D3:8D:34`.
- Existing receipt operation `readback_receipt`; exact existing collector,
  authorization source, and tool hashes must be bound in its separately audited
  one-use record.
- Exact seven ranges: C3 partition table `(0x8000, 0x1000)`, C3 OTA data
  `(0xF000, 0x2000)`, C3 active application `(0x20000, 958992)`, S3 bootloader
  `(0x000000, 0x008000)`, S3 partition table `(0x8000, 0x1000)`, S3 OTA data
  `(0xF000, 0x2000)`, S3 active application `(0x420000, 2292864)`.
- One attempt per target: at most one ROM-loader entry, one USB-aware
  application-restore reset, and one connection, with no retry. These resets
  are part of the capture procedure and must be explicitly accepted. No flash
  writes/erase, NVS, credentials, keys, unrelated ranges, bootstrap, or event.
- Stop on any identity, range, tool-hash, authorization, or capture-integrity
  mismatch; retain partial evidence and cleanup outcome.

### Scope B — one fresh USB-triggered E2E event

- A separate, independent one-use `motion_event_once` grant, usable only after
  Scope A produces fresh matching receipts and all readiness guards pass.
- Same Home and fixture identities as Scope A; verify Android USB identity,
  package, signer, backend origin, and fresh installation receipt through the
  existing `AndroidReady` path. Verify backend/PostgreSQL, authenticated
  caregiver API, Hub ingress, and current C3/S3 readiness using existing checks.
- Enumerate S3 identity without opening its UART. Open C3 COM4 through the
  existing helper, acknowledging the documented incidental COM-open reset
  risk. Send exactly one existing `INJECT_MOTION` command. Require the matching
  class-0 durable ACK, exactly one PostgreSQL EventKey, the authenticated API
  projection, and that same EventKey in the actual APK. Preserve event
  chronology, Home/room/type identity, delivery evidence, and latency data.
- Stop on the first failure. No event retry, second event, explicit reset,
  bootstrap, firmware operation, network change, five-event campaign, or claim
  of optical-PIR acceptance. Close the one-use session and preserve evidence.

Scopes A and B must have independent immutable authorization/session records.
Scope B must not activate until receipt scope has completed and been reviewed.
This package is not an approval or activation; both operations remain NOT_RUN.

## Validation and status

Newly executed offline checks:

- `python3 -m py_compile ...` — PASS.
- `python3 code/tests/python/test_gs117_tc001_console.py` — **180/180 PASS**.
  Includes one-event isolation, stale/missing readiness, reservation count,
  post-reservation fixture mutation, source-pin negative requirements, and no
  campaign fallback. Existing execute-path tests cover ACK, duplicate database
  event, API and APK failures. The exact named source-pin negatives are required
  before future source-pin update:
  `test_motion_event_once_authority_is_an_isolated_one_use_operation`,
  `test_motion_event_readiness_requires_fresh_one_use_fixture_authority`,
  `test_motion_event_source_pin_review_requires_and_records_single_use_negatives`,
  `test_single_event_controller_reserves_once_and_never_falls_back_to_campaign`,
  `test_single_event_fixture_change_after_reservation_consumes_scope_without_execute`,
  and `test_single_event_missing_or_stale_preflight_never_invokes_execute`.
- `make -C code validation-framework-test` — **55/55 PASS**.
- `make -C code feature-coverage-test` — **22/22 PASS**; registry traceability
  reports 237 features, 288 modules, and 28 physical cases.
- Inline controller JavaScript syntax (`node --check`) — PASS.
- `git diff --check` — PASS.

An initial test run exposed five old pin-review mock cases that lacked the new
operation-specific test names; the fixtures were updated to supply the
registered negative-test list and the full final suite then passed. These are
host tests only. No firmware build or device operation was run.

Current state: hardware grant #11897 remains `SAFETY_LATCHED`, 1/1 consumed;
#11886 and all historical records remain unchanged. Firmware is unchanged;
image receipts are STALE; `TC001_READY=NO`; physical TC-001 accepted cases 0/5.
There are 79 pre-existing untracked entries; they remain untouched. The current
worktree source changes are pending review/commit at starting HEAD
`2111511e9a12d9120f9b8c2a7973ed4ea78bc582`.

**Next action:** obtain one consolidated owner decision for the separate Scope
A and Scope B grants; only after Scope A is approved and captured should Scope
B be provisioned and considered for execution.
