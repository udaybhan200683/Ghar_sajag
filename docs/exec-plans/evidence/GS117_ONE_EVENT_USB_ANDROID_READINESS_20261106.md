## Existing ingress authority check — 2026-11-08

Starting local/origin 531e69cb4813aaa1522746fb8057bb730369b47a; context PASS,
tracked clean. No hardware or network mutation. Existing launcher identified as
services-AB-20261105T041014Z/gs117-active-ingress.py with its signed-time companion,
launch-manifest and fixed 3600-second lifetime. Its retained log ends
GS117_BOUNDED_INGRESS_STOPPED; current socket check confirms no8445 listener.
Generic caregiver health's NOT_CONFIGURED label is static, not the session check.

The existing five-day network authority validated at current UTC2026-11-08:
activation2026-11-05T03:08:32.809579Z, expiry2026-11-10T03:08:32.809579Z,
SHA256 a4cda9fad33fc13d91d449e41ccdcc51b95335e3b7bb7d49dac9870dd576b4e8,
hardware_operations_authorized=false; no DEV sublease record found. Source DEV
branch uses independent network authority and existing process/service guards;
it does not require reviving the consumed hardware grant. Historical A/B closed.
The reviewed handoff leaves live DEV privileged activation NOT_ENABLED and not
qualified; five-day software authority is not blanket privileged deployment
approval. No service, sublease or Windows task was started.

Required owner decision: approve ONE bounded DEV network activation for this
passive observation, using existing ingress/signed-time launchers, maximum3600s
clamped to outer expiry,1800s inactivity closure, exact .6:8445-to-verified-WSL
route, existing temporary Highest/SYSTEM tasks, normal UAC and cleanup; no firewall
expansion, hardware operation or permanent task. #11941 alone does not cover it.
Hub authentication UNKNOWN, no PIR request/stimulus/EventKey; all event boundaries
NOT_RUN, TC001_READY NO, TC0010/5. Firmware/latches/evidence unchanged. No tests
rerun because no source change; read-only authority/listener/log checks executed.

# GS-117 — One-event USB-to-Android readiness — 2026-11-06

## Approved passive optical-PIR preflight — 2026-11-08

Owner chat approval recorded in GS-117 #11941 permits one manual AM312 stimulus
on gs177-test-product / c3-146393c5d158 / hub-e072a1d38d34 with existing passive
monitoring only. It is not independently signed issuer evidence. The USB issuer
was not consulted as a prerequisite to this separate observation.

Context preflight PASS; starting local/origin 73b7577a0022cbcbafe6a357ece4507f05070ef7,
tracked clean. Existing read-only gs179-laptop-server.sh health returned PostgreSQL
TLS/durability PASS, local caregiver HTTPS PASS, and LAN HTTPS PASS at 192.168.1.6.
However HUB_INGRESS_READY=NOT_CONFIGURED, HUB_IDENTITY_AUTHENTICATED=NO,
HUB_MONITORING_FRESHNESS=UNKNOWN; socket inventory showed caregiver 8444 and
PostgreSQL 55432 but no 8445 listener. Thus existing monitoring/delivery facilities
were insufficient before stimulus. No motion was requested or claimed. No fresh
EventKey; C3/S3/event/PostgreSQL/API/APK correlation NOT_RUN. No USB/COM/ADB,
reset, readback, injection, service start or network change occurred.

Observation BLOCKED before stimulus by unavailable existing Hub ingress. No
source changes or automated tests; current host health checks are not target
readiness. Firmware and historical latches unchanged, receipts STALE,
TC001_READY NO, TC-001 0/5. Next action: restore the existing bounded Hub ingress
through its established authorized service/session workflow, then recheck passive
readiness before requesting the single manual motion. No new infrastructure or
issuer-trust investigation is needed for this passive observation.


## Direct optical-PIR route review — 2026-11-07

Offline review only; no USB, COM, ADB, board, network, database or event
operation was performed. The canonical worktree is `feature/r1-commercial-baseline`
at `efc41a4823bcfc992ac4f14123745434f042075b`, equal to origin; tracked files
were clean and existing untracked assets were preserved. Context preflight PASS.

The existing GS-117 `Controller.observe_once()` is a bounded read-only status
observer, not the product E2E observer: it consumes a one-use local approval,
opens both serial interfaces, asks C3 `GET_STATE`, and may ask S3
`FIXTURE_STATUS` when the existing readiness conditions permit. It reports that
reset-free UART behavior is unverified. The expected approval file is absent.
Its historical approval was already consumed by
`OBSERVE-20261026T163858-8f80b4a9`; that observation was PARTIAL (C3 status only,
zero runtime/sensing liveness, no S3 fixture status, CloudSync NOT_VERIFIED).
It did not capture or correlate a fresh EventKey through PostgreSQL/API/Android.

The available genuine-AM312 runner, `code/tools/hil/gs130_motion_hil.py`, is
pinned to `GS114-DISPOSABLE-C3-S3`, its own image hashes and sleep-wake cases; it
does not match the GS-117 product S3 `hub-e072a1d38d34` or its approved scope.
The GS-117 `motion_event_once` controller instead sends USB `INJECT_MOTION` and
is explicitly not optical-PIR evidence. The physical catalogue retains that
distinction. Therefore no existing tool/approval pair can currently execute
and prove the requested real-PIR-to-Android case on the GS-117 fixture.

Read-only authorization status: `readback_receipt` BLOCKED
(`readback_receipt_policy_not_private`); `motion_event_once` BLOCKED because its
policy is absent. Jira #11933 remains conditional approval for receipt capture
and one USB-injected event only; it is not optical-PIR authority. #11897 remains
SAFETY_LATCHED, 1/1 consumed; #11886 is preserved. The five-day network grant
does not grant hardware access. Receipts remain STALE and TC-001 remains 0/5.

No code or tests changed. Existing 53/53 receipt/issuer, 180/180 console,
55/55 framework and 22/22 mapping results remain historical offline results.
The source/tool hashes listed below remain unchanged. The issuer trust blocker
from #11936/#11939 remains: an agent-authored Jira comment or caller-supplied
owner fields cannot issue grants. The one owner action already recorded in
#11939 remains necessary: establish owner-only Jira write/review control outside
Codex access and read-only authenticated verification, then personally review
the exact source/test digest. This does not reapprove #11933; any optical-PIR
operation must also be covered by its own exact fixture-bound scope. No physical
operation was authorized or attempted in this checkpoint.

## Solo-developer reconciliation — 2026-11-07 — owner clarification #11938

No second-developer or two-human-review requirement was found in the applicable
canonical development contracts/LOCKED decisions. The same sole owner may review
and authorize. Any previous wording implying another person or Jira account is
necessary is superseded by #11938. The separation required here is owner approval
from automated execution; the #11936 caller-provenance defect remains unresolved.
Scope #11933 and all product/security/fixture limits are unchanged.

Bounded read-only availability checks: GPG/gpgv and ssh-keygen installed; no local
GPG private-key directory, SSH directory or configured SSH agent in the checked
Linux account; no ykman/fido2-token executable. Windows CurrentUser My certificate
store reported zero certificates with private keys. UAC and secure-desktop policy
are enabled. This does not exhaustively establish absence of Windows Hello or a
hardware token; neither is qualified as an exact-manifest approval signer here.
No signing operation, key generation, elevation prompt or device access occurred.
Existing UAC asks for elevation and has no reviewed binding to the issuer commit,
test digest, scope, identity and expiry. A same-user file or locally accessible
key cannot supply that missing owner boundary.

**One minimum owner-operated setup action:** establish the existing Jira account
as an owner-only write channel, with automation limited to authenticated read
access. Keep the owner login/write credential in a session outside Codex access
(for example, owner-operated phone/browser); remove automation's write capability
as that account, including the present write-capable connector, and provide only
read-scoped Jira API access for the eventual local verifier. The same owner then
personally records review of the final issuer commit, fingerprints, test-report
digest and unchanged #11933 boundaries. This is one separated read/write setup,
not a request to approve Scope A/B again, a second developer, or a new account.
No access settings or credentials were changed by this task. Exact read scopes
and enforcement must be verified during owner setup; a broadly writable token
labelled read-only is insufficient. This proposal is not an activated trust source.

Once that setup is confirmed, a narrow authenticated read adapter in the existing
issuer and its forgery/replay/activation-crash tests can be prepared. The owner
must review the final changed source/test digest before grants. The current MCP
read-write identity alone and agent-posted Jira comments cannot attest that review.
The receipt collector, single-event controller and full C3/S3/backend/APK product
path remain reusable unchanged. No firmware deployment is justified by this audit.

Context preflight PASS; starting local/origin `15bbf70a5e50879bad713990ae7529df0cb50f43`.
Issuer SHA-256 remains `ee60a55851535ed0ed39695f70d2744721c8b9e994f4b469c832a0f112d06c4e`;
collector remains `87373b43cbce3036c427fe90723b3edfddc269bbd3d92ca3b63f0f6a688ce312`.
No source change or tests rerun; prior 53/180/55/22 are historical offline results.
Issuer BLOCKED; grants absent; Scope A/B NOT_RUN; no COM/ADB/reset/readback/injection;
firmware unchanged, receipts STALE, historical #11897 SAFETY_LATCHED 1/1/#11886
preserved, TC001_READY NO, optical-PIR TC-001 0/5. Stop at owner setup, per step 2.

## Trust-source availability and minimal external prerequisite — 2026-11-06

Result: **BLOCKED; no existing independently consumable trust mechanism found**.
The authenticated Atlassian connector successfully returned the owner account
`712020:d1785a8a-5bf2-4556-a451-0805ddb6af74`, the actual #11933 approval,
and #11936 review finding. Resource discovery reports Jira **read-write** access.
This is a usable interactive source for investigation, but the local Python
issuer has no authenticated Jira client/credential interface or verifiable
connector attestation. A copied connector response would again be caller JSON.
Moreover, Codex can add comments through this same owner account: author ID
alone cannot distinguish an independent owner review from an agent-written
comment. This task's Jira result comment must never serve as source approval.

Targeted availability checks found no `acli`/`jira` executable, no Jira/Atlassian
environment variable names, and no standard local acli/Jira/Atlassian config
directory. Relevant canonical tool source has no Jira REST/authentication client.
No credential values or connector credential stores were inspected or exported.
These observations establish no configured local verifier in the examined
interfaces; they do not claim no credential exists anywhere on the laptop.

**One proposed owner-controlled setup decision:** use the existing Jira Cloud
service with separated review-write and verifier-read authority. The owner
selects a review account whose write credentials are unavailable to Codex
(or removes Codex write access as that reviewer), and provisions read-only Jira
API access for the local verifier through an owner-controlled credential store.
The owner independently records a source review in Jira identifying the exact
issuer commit, source/tool fingerprints, reviewed test outputs and report digest.
The existing test runner may produce those outputs; an independently authored
review must endorse their source binding and digest. The issuer must fetch the
actual approval and review directly over authenticated HTTPS, validate authors,
current content and scope, and match the local test report to the reviewed digest.
No new approval of unchanged #11933 hardware scope is requested.

This is a proposed setup, not an implemented or activated trust source. Credential
provisioning, separated reviewer control and genuine source review require owner
participation; Codex cannot create those independently by copying JSON or posting
as the owner. After setup, only the existing issuer verification inputs need a
narrow adapter and focused forgery/replay/crash tests, followed by source review.
Product pipeline, receipt collector, controller, scope limits and historical
ledgers can remain unchanged. No identity framework was implemented.

Current preflight PASS at starting local/origin `bbe094f9117b88fea79ce09bb46ced56b221d504`.
No source changed and no tests were rerun: prior 53/53 receipt/issuer, 180/180
console, 55/55 framework and 22/22 mapping remain historical results, not trust
qualification. Scope A/B remain absent and NOT_RUN; no hardware/grant/network
operation occurred. Firmware unchanged; receipts STALE; #11897 SAFETY_LATCHED
1/1 and #11886 preserved; TC001_READY NO; formal TC-001 0/5.

## Independent issuer security review — BLOCKED — 2026-11-06

The scoped issue/activate implementation is **not approved for use**. Jira
#11933 is a genuine owner-authored approval (verified through the authenticated
Atlassian connection), but the local issuer does not retrieve that record. At
`gs117_hil_authorization.py:981-997`, it accepts a caller-provided dictionary
when its fields and body digest match constants. This pins the approved
contents and prevents scope substitution; it does not authenticate the
snapshot's provenance at invocation.

The source-review boundary has the same material gap. At
`gs117_hil_authorization.py:1000-1090`, `reviewer` is accepted when its string
equals the owner account ID; source/test hashes and test counts are checked,
but the reviewer and test receipt have no authenticated producer or
attestation. The caller can construct those fields. Owner-only file permissions
do not distinguish the local Codex process from the owner when both run as the
same Unix account. The current repository/local authorization mechanisms
provide no authenticated Jira snapshot or independently authenticated source
review interface that this issuer can consume. Do not issue or activate grants
through these APIs until that trust boundary is supplied by an existing
approved mechanism.

Other reviewed properties: the code binds the clean canonical commit, seven
source/tool/test fingerprints, fixture and exact operation scopes; issue and
activate are separate, one-use and time-bounded; Scope B checks passing fresh
Scope A evidence at issue, activation and policy load; policy loaders also
require the linked issuance and activation audit records. Interruption before
the final audit binding leaves a policy unusable (though an orphan pending
record can block reissue). Existing tests cover interrupted pending issuance,
but do not inject every crash point between activation-audit, policy write and
issuance-audit. No evidence shows a partially written policy can become usable;
this crash-window coverage remains a follow-up to any corrected issuer.

Newly run during this review: receipt/issuer **53/53 PASS** and console
**180/180 PASS**. Previously recorded at the same source checkpoint:
framework **55/55 PASS** and feature mapping **22/22 PASS**. These host tests do
not close the approval/reviewer authenticity gap. `issue_gs117_scope_grant()`
and `activate_gs117_scope_grant()` were not called. The issuance state,
readback policy, and motion-event policy remain absent. No device or USB/COM/
ADB, ROM, reset, readback, network, or event operation occurred. #11897 remains
SAFETY_LATCHED 1/1; #11886 is unchanged; firmware is unchanged; receipts are
STALE; `TC001_READY=NO`; TC-001 remains 0/5.

No code change was made: the missing authenticated authority provider is not
present in the existing mechanism, and substituting a caller field, local
confirmation or new identity workflow would not satisfy the review requirement.
The exact next gate is to use an already trusted authenticated approval/source
review mechanism, if one exists, and bind this issuer to its evidence. Otherwise
the owner/security decision is how to supply that trust without expanding the
approved physical scope. Do not run Scope A or Scope B before then.

## Authorization issuance correction — offline only — 2026-11-06

The #11933 approval is unchanged. Audit confirmed there was no trusted physical
grant issuer in the existing module: receipt authorization could validate and
reserve a provisioned policy, while the GS-179 recorder is limited to network
authority. The existing readback and one-event validators are reused.

`gs117_hil_authorization.py` now has a narrow issue-then-activate API for the
two approved operation names only. It verifies the pinned issue/comment/owner
and comment-body digest, an owner-identified source review for the exact clean
canonical commit and source fingerprints, exact tool paths/hashes, and fixed
operation scope. The source review must list the 21 registered negative/guard
tests across the receipt and console suites; the private test receipt pins
their exact commands and zero skips. It creates a private immutable pending
record and hash-chained audit entry; activation is separate, one-use,
nonrenewable, time-bounded and
creates only the operation-specific policy. Scope B rechecks the fresh passing
Scope A evidence before issue, activation and each motion-policy load. The
one-event controller now selects that isolated policy, never the consumed
broad DEV manifest. Shared HIL locks serialize the new scopes with existing
hardware operations. Generic readback, flash and erase remain prohibited; the
old #11897/#11886 ledgers are not edited.

Exact source-review pins at this checkpoint:

| Source/tool/test | SHA-256 |
|---|---|
| `code/tools/local/gs117_hil_authorization.py` | `ee60a55851535ed0ed39695f70d2744721c8b9e994f4b469c832a0f112d06c4e` |
| `code/tools/local/gs117_tc001_console.py` | `bd664cc89e09837744393f0c20c356638f015c591513c43c46f344b1c57fb318` |
| `code/tools/local/gs117_tc001_readback.py` | `87373b43cbce3036c427fe90723b3edfddc269bbd3d92ca3b63f0f6a688ce312` |
| `code/tools/local/gs117_tc001_serial_windows.py` | `44a2669593ff367fcb9d0a59d4c2d289070906fbb0270b9f1f3929c183f5b8dd` |
| `code/tests/python/test_gs117_readback_receipt.py` | `141b5af937c5bb84975014a1036c6fc7fbeeba1b3e3a3f7fa3efe8f6beba673c` |
| `code/tests/python/test_gs117_tc001_console.py` | `6609c2f4dfb3aade90ae5adbd9929c65b88a00eef8b216098b36e460db93a767` |
| `code/validation/suites.json` | `ef9f5812aeaa8c10e8413de111d0b94bc3b8948298553a0103230d294e8673ee` |

The new `gs117-scope-authorization-issuance` stage registers and executes the
receipt/issuer suite as a tooling/contract/backend host test; it never opens a
device. The exact code, operational tools, tests, and registry above must be
reviewed together. These hashes do not authorize or activate a grant.

New offline checks: receipt/issuer **53/53 PASS**, console **180/180 PASS**,
framework **55/55 PASS**, feature mapping **22/22 PASS**; Python compilation
passed. The first receipt run exposed double acquisition of the receipt lock;
the lock order was corrected and the final run passed. No target build was
needed. These are host/offline results.

No source-review package has yet been accepted for the changed issuer hashes.
No actual grant was issued, activated or reserved: both #11933 policies remain
ABSENT; Scope A is NOT_RUN and Scope B is NOT_RUN. No device, COM, ADB, ROM,
reset, flash/readback, network or event operation occurred. The current
firmware and receipts are unchanged/stale; #11897 remains SAFETY_LATCHED 1/1,
#11886 is preserved, `TC001_READY=NO`, and TC-001 remains 0/5. The next gate is
independent review of the changed issuer source and its exact source/tool/test
fingerprints. This checkpoint does not approve or activate hardware access.

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

## Execution attempt after owner approval #11933 — BLOCKED before reservation

The canonical worktree and branch were rechecked at commit
`861daf5a2aaf3989b76d88c0fd5393f568f741af`; origin matched. Context preflight
passed. Tracked files were clean before this status update; the 79 existing
untracked entries were preserved. No competing Codex or hardware process was
visible. Read-only source/tool hashes for the collector, authorization module,
controller, serial helper, bootstrap evidence helper, backend verifier, health
helper, and endpoint verifier still match the fingerprints in this record.

Jira #11933 was read and matches the proposed fixture, exact seven ranges,
per-target ROM/restore-reset limits, conditional Scope B and exclusions. The
comment explicitly says it records owner intent and is not a completed
technical authorization, receipt, or PASS.

- **Scope A: BLOCKED / NOT_RESERVED.** Read-only
  `readback_receipt_status()` returned
  `BLOCKED: readback_receipt_policy_not_private`; the expected
  `readback-receipt-authorization.json` and its state directory do not exist.
  The existing authorization source validates and reserves a previously
  issued grant, but provides no grant creation/activation operation or local
  issuer command. No session or device operation was started.
- **Scope B: BLOCKED / NOT_RUN.** Read-only `development_status()` returned
  `BLOCKED: development_reviewed_procedure_changed`. The existing private DEV
  manifest is bootstrap-only and consumed, and its controller, authorization,
  serial-helper, and bootstrap-evidence-helper pins are stale. It was not
  modified. The implementation's source-review path does not issue a new
  operation grant. No session was reserved.

Because Scope A did not produce a verified PASS, Scope B was not considered for
activation. No USB enumeration, COM/ADB open, ROM entry, reset, flash read,
bootstrap, network operation, or event injection occurred. Firmware and
installed-image evidence are unchanged; application receipts remain STALE.
GS-117 #11897 remains SAFETY_LATCHED 1/1 and #11886 remains preserved;
`TC001_READY=NO`, TC-001 remains 0/5.

The remaining blocker is completion of the existing trusted/audited grant
issuance path for two separate one-use records bound to the reviewed hashes and
#11933 scope. Do not manually create policy/audit records or reuse the consumed
DEV manifest. After those records are legitimately provisioned, rerun status
and source-pin checks before Scope A; Scope B remains conditional on a verified
Scope A PASS and fresh Android/readiness evidence.
