# GS-178 software vertical — execution record

## Current status update — 2026-10-19

The earlier target-gap statements in this historical execution record describe
the `ceeddc0` checkpoint and are superseded for current source by
[`GS178_S3_RULE_RUNTIME_20261019.md`](GS178_S3_RULE_RUNTIME_20261019.md).
Canonical `HubRuntime` now checkpoints pending Hub rule-decision publication
intent with rule state, the S3 adapter schedules rules using trusted local-time
input and current authority, and the existing CloudSync worker acknowledges
only backend `COMMITTED` decisions. Host E2E and both S3 build profiles have
been validated. This does not establish physical target execution; GS-40,
GS-117 and GS-121 physical acceptance remain NOT_RUN, P0 remains PARTIAL, and
the recorded migration assertion remains an open failure.

The TEST_ONLY product image hash was rechecked after resume. The currently
present artifact hash and image-validation digest are recorded in the new
evidence. The earlier build digest below is historical and must not be used to
identify that current artifact.

Owning Jira: GS-178; dependencies GS-40/59/148/177/109/168. Started on
`feature/r1-commercial-baseline` at `e74dc5190cccd2ebf4c4b37a54b73f7e95041c7a`,
equal to origin. Context preflight PASS. Tracked tree was clean; all untracked
assets and historical worktrees are preserved. Other long-lived Codex processes
had no active build/test/editor child; the remaining child is an idle clipboard
bridge. This session is the canonical implementation writer.

## Impact and validation contract recorded before implementation

Affected components: TEST_ONLY GS-40 host services, C3/S3 production-code host
simulation, durable backend projection/actions, GS-177 caregiver API/PWA.
Shared interfaces: G40E, GSTQ/GSTP, G40A, authenticated NodeMessage/ACK,
CloudSync v2 EventKey/COMMITTED and NodeHealth, current Home/epoch/enrollment,
authenticated caregiver session. Existing suite families: Node, Hub, contract,
backend, PWA, board-stack, cloud trust and GS-177. New checks cover complete
Node-originated traces, configuration/signatures/replay, authority transfer and
revocation, persistence, outage/retry, chronology and caregiver authorization.
Applicable builds: ESP-IDF 6.0.3 C3/S3 and Android; sanitizers and existing
GS-116/130 registration/failure propagation. Full release gate is NOT_RUN until
a frozen RC. Hardware and phone acceptance are NOT_RUN.

## Reuse inventory

Canonical already includes GS-177 Connected Lite. Reuse QualifiedInput,
NodeRuntime, NodeRecoveryRepository, authenticated_pair/board-stack AEAD and
rejoin, HubRuntime, RuntimeStateStore, segmented outbox, CloudSyncWorker,
HttpBackendTransport, HttpsBackendChannel, GS-168 TestOnlyIssuer, registered
ownership and durable SQLite API, canonical query/action services, Lite opaque
sessions and shared Android/PWA assets.

Read-only simulator inventory: branch `codex/gs-hub-test-simulator-20261018`
at `0ff9e3ba` differs from base `5848797` in 14 files (~1,425 insertions).
Its worktree retains Makefile/work-state edits and generated managed components.
Its bridge creates a Hub-only `hub-sim-test` System source and calls
`radio_callback`; it does not establish the requested C3/authenticated-radio
origin and cannot supply durable owner provenance for CloudSync v2. Preserve
that work; reuse canonical Node-side harness for this vertical rather than
importing a parallel injection bridge or disabling replay fences.

## Scope and safety

This task authorizes bounded TEST_ONLY engineering, including the matching
GS40T/1 services. Commercial approval of that proposal remains absent. No
locked product policy, production credential/endpoint, hardware, eFuse, FOTA
partition, or GS-104 learning algorithm is changed. Domain virtual time and
real signed cryptographic time are separate. TEST_ONLY fixture environment and
evidence identify software observations; they are not real sensor results.

Initial concrete integration defect: G40A nonce comparison used unsigned bytes
against signed `char`, rejecting valid high-bit nonce values. Classify as
R1_FIX under GS-D032 authentication correctness; correct exact byte comparison
and add a regression, without relaxing signature/binding validation.

Execution results and final handoff are appended after actual validation.

### Additional in-scope defect triage before correction

BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; canonical chronology/durable-event invariants
DECISION_IDS=NONE
TASK_SCOPE=GS-178 delayed-event chronology and retry correctness
OUT_OF_SCOPE=GS-104 learning and a general historical rule recomputation engine

The current live activity reducer assigns last_activity_at from every arriving
motion, including older backlogged evidence. That can move its timer anchor
backwards. Preserve the latest activity anchor and retain the old event in the
journal/backend chronology; do not replay old activity into current live-rule
state or invent a historical concern.


## Implemented software path and boundaries

`make -C code gs178-software-e2e` builds one host executable against production
QualifiedInput, NodeRuntime/recovery, authenticated rejoin/AEAD, HubRuntime,
identity/replay ledger, segmented outbox, CloudSync worker, HTTPS channel and
HTTP COMMITTED adapter. The SDK socket boundary is a bounded OpenSSL TLS 1.2
adapter; this does not execute ESP-IDF Wi-Fi, GPIO, radio or flash hardware.

The isolated stack uses the existing GS-168 issuer/registry and ownership DB,
RSA-3072 signed time, separate signed authority leases, SQLite durable ingest,
canonical query/incident policy and existing GS-177 app assets. Four synthetic
Nodes are independently enrolled in the test registry. No event is seeded into
the backend. Scenarios send sensor transitions to production Node processing.

Configuration uses the existing G40E ECDH/HKDF/AES-GCM/RSA envelope. Time uses
GSTQ/GSTP with nonce/boot binding. `/v1/test/authority/refresh` is mounted only in
the loopback test server, requires real TLS 1.2 client-certificate authentication,
and obtains Home/epoch/generation from current verified registries. An initial
certificate permits only this refresh; publication still needs its signed lease.
No public WSGI/commercial endpoint is activated. Ephemeral private authorities,
client credentials and passwords are never committed or installed in NVS.

Authority lease validity begins at the preceding completed UTC second and lasts
60 seconds, yielding at most 59 seconds of remaining server-clock validity. This
accounts conservatively for whole-second signed-time quantization; it does not
add future-time tolerance. Verification resamples authenticated time after the
bounded HTTPS round trip. A signed future authority lease is still rejected.
The server independently checks ownership/revocation for every submitted update.

The shared `Gs40TestOnlyCloudComposition` is instantiated by actual guarded S3
startup and the host vertical. It takes references from the material source
AFTER moving configuration, fixing the former moved-from endpoint/CA strings.
A TEST_ONLY Wi-Fi netif is created and time/authority refresh is paired; loss of
IP, time or authority fences publication. Normal composition remains
`UnprovisionedS3CloudTrust`; no software test key is selected commercially.

### Software faults corrected

- Byte-exact G40A nonce comparison now handles high-bit bytes.
- Trusted-time rollback detection observes actual platform clock rollback;
  nested reads no longer mistake an earlier caller reference for actual rollback.
- Authority response time is checked at receipt, with bounded round-trip age.
- Original durable Hub receipt metadata is retained on authenticated retries;
  changed Node contents still fail the original identity digest. No storage
  format or retirement proof is changed, and absent bodies are not invented.
- Backlogged activity remains in history without rewinding live rule anchors.
- Durable backend incidents/actions now use existing alerts/acknowledgements
  tables and canonical incident policy; failed actions roll back, and human ACK
  suppresses pending delivery. This is not evidence of actual notification reach.
- Caregiver product projections expose actual committed data and persistent
  actions, including structured EventKey provenance. Offline device/source state
  cannot claim COVERED monitoring.
- Existing test certificates now carry standard key identifiers/key usage needed
  by strict Python 3.14 TLS validation. Certificate checking was not disabled.
- GS-168 public metadata retains credential generations over renewal/reopen.

### Explicit limits

Accelerated time drives domain leases/rules only. Signed-time and certificate
verification use the real cryptographic clock. The host gives event admission a
controlled receipt timestamp; the current S3 radio adapter still records event
Hub UTC as unknown (0). NodeHealth timestamps use the existing trusted snapshot
adapter. The host event timestamp is not evidence of that S3 event-time seam.

Normal domain events use the ordinary event flag inside an isolated synthetic
Home so real incident/action policy runs. That differs from the `is_test` domain
flag, which intentionally suppresses business effects. Test-only identity,
loopback services, evidence and app banners keep these fixtures separate from
customer data. No notification provider is contacted.

Derived deterministic morning/night decisions are exercised in actual Hub rules,
but are not falsely promoted into caregiver concerns. Their durable Hub-owned
output stream, identity/receipt and timer-decision contract is still missing.
Node EventKey provenance cannot be reused for invented Hub-originated events.
Full P0 product_status remains PARTIAL. GS-104 learning stays on hold.

### Physical preparation

PHY-GS40-01..06 and GS-117/121 remain NOT_RUN. A future run requires separately
identified and authorized S3 PRODUCT and C3 images, matching radio enrollment,
sessions and configured 300/910 policy; an isolated reachable backend/time service
and a live owner-controlled TEST_ONLY envelope signing fixture are also required.
This loopback sender is software validation, not a ready LAN provisioning tool.
PHY-GS40-05 additionally needs a second independently enrolled trusted legacy
Node/profile fixture. C8, C3 and the GS-68 diagnostic spare were not accessed.
No USB/serial, reset, flash, eFuse or security provisioning occurred.


## Validated checkpoint 1 — raw events, status and caregiver actions

Actual commands / exits:

- `make -C code -j4 gs178-software-e2e`: PASS, 22 tests (116.863 s), exit 0;
  `/tmp/gs178_full_vertical_final.log` (local raw execution log).
- `make -C code -j4 gs178-software-e2e cloud-trust-provider-test gs40-test-only-bootstrap-test cpp-test`:
  PASS, 20-test earlier scenario set, cloud-trust 5 suites, bootstrap 33 checks,
  C++ 1,511 checks, exit 0; `/tmp/gs178_focus_freeze.log`.
- `make -C code validation-framework-test feature-coverage-test`: PASS, framework
  51 tests, traceability 214 features / 253 modules / 25 physical cases and
  mapping tests 22, exit 0; `/tmp/gs178_framework_final.log`.

Exploratory failures were corrected and rerun: immutable retry receipt mismatch;
SDK time/authority second-boundary race; legacy 120 profile incorrectly treated
by the new fixture as 120/370 instead of its trusted 120/310; bounded publication
expectation; night rule's strict greater-than configured threshold; and browser
selectors/offline transport routing. None was converted to a false PASS by
changing product acceptance rules. Raw exploratory logs remain local.

P0 A/E/F/G/H/I/J/K/L and existing Privacy drop/explicit assistance pass their
identified software assertions. Door OPEN/CLOSE ordering passes. Deterministic
morning/night rule outputs pass locally but cloud-derived concerns are still a
separate missing connection at this checkpoint. Required product P0 remains
PARTIAL. This checkpoint is not a release or physical acceptance claim.

## Pause / resume handoff — 2026-10-19

The owner paused GS-178 after the validated host vertical and requested a
detailed handoff. Canonical worktree:
`/home/udaybhan/projects/Ghar_sajag_r1`; branch:
`feature/r1-commercial-baseline`. The source checkpoint began at
`e74dc5190cccd2ebf4c4b37a54b73f7e95041c7a`, which matched origin at
preflight and again before closeout (`git fetch`, ahead/behind `0/0`). Context
preflight PASS. The 38 intended source/test/document changes were staged for a
single checkpoint commit; unrelated untracked PWA, Android, managed-component,
GS-114/C8 and GS-40 evidence was neither staged nor modified. Historical
worktrees, including the separate Hub simulator and GS-177 worktree, remain
untouched. The closing commit and remote SHA must be read from Git when resuming;
this handoff intentionally does not predict a commit ID.

The prior execution recorded 22/22 isolated host integration tests PASS, plus
the focused cloud trust, bootstrap, C++ and validation-framework counts above.
After this execution environment restarted, the `/tmp/gs178_*` raw logs were no
longer present. The command/results in this file are the retained contemporaneous
test record; a new session must not mistake the missing ephemeral logs for new
test execution or claim an independently rechecked receipt. No current-source
ESP-IDF C3/S3 image, Android APK, sanitizer result, complete affected-component
gate, board-stack gate or full browser gate was produced at this checkpoint.
Those stages are NOT_RUN for the new GS-178 source. The older GS-177 Android CI
artifact and older GS-40 firmware image are not source-bound GS-178 results.

Completed host software evidence: simulated PIR, door OPEN/CLOSE, I Am OK and
Call Family enter production Node processing, authenticated Node/Hub admission,
durable ACK and CloudSync; real loopback TLS 1.2/mTLS backend ingestion and
SQLite persistence feed the existing caregiver API/PWA. Host scenarios cover
lost ACK and COMMITTED receipt, Hub/backend restart, WAN recovery, exact-key
retry versus conflicting payload, authenticated NodeHealth online/offline and
stale-source UNKNOWN, current Home/epoch/revocation, mixed 300/910, 60/190 and
120/310 profiles, persistent authorized caregiver actions, and chronology.
These are HOST_SIM_PASS only. No real sensor, RF, target firmware or phone
operation occurred.

Unfinished product connection: existing deterministic Hub morning/night rule
decisions execute locally, but their Hub-owned durable identity, storage,
CloudSync submission, backend concern receipt and caregiver projection have not
been joined. Node EventKeys cannot be repurposed to manufacture Hub decisions.
Therefore the mandatory P0 software vertical and `product_status` remain
PARTIAL. The existing Hub migration assertion ("clean migration commits"),
Hub sanitizer 600-second timeout and other release gates remain independently
open; this checkpoint does not resolve or suppress them. GS-104 R01–R09
learning, commercial GS40T/1 approval and all physical GS-40/117/121 acceptance
remain outside this host result. PHY-GS40-05 still requires a second enrolled
legacy-profile Node or approved equivalent fixture.

Resume in this order: (1) verify canonical branch, commit, remote equality,
tracked/untracked status, latest GS-178 Jira and context preflight; (2) inspect
this handoff and source/tests before repeating any validated host scenario;
(3) implement the minimum Hub-owned durable rule-decision path using existing
journal/outbox/backend incident services, preserving Node EventKey, durable
ACK, replay and ownership invariants; (4) add complete-chain morning/night and
negative/recovery assertions; (5) run affected Node/Hub/contract/backend/PWA,
board-stack, browser, sanitizer, GS-116/130 and source-bound ESP-IDF 6.0.3 and
Android build checks; (6) update Jira/evidence, commit and push. Physical tests
need separately identified, image-verified, authorized fixtures. Do not access
the C8 Hub, C3 Node or GS-68 spare under this handoff.

## Resumed execution — 2026-10-19

Preflight PASS at `ceeddc0ff1f670d78414baddccdfcf9f9c89fcd0`, equal to
origin with a clean tracked tree; GS-178 remains In Progress. Owning Jira:
GS-178. Affected components: Hub deterministic rule output/checkpoint,
CloudSync, authenticated backend commit/incident projection, caregiver read
model and GS-116/130 host vertical. Prior Node/Hub/contract/backend/PWA,
board-stack and security suites remain the affected regressions. Required new
checks: source identity, current Hub/Home/epoch, exact retry/conflict,
revocation/transfer, WAN/restart and caregiver rule concern. Hardware remains
NOT_RUN; release gates remain deferred to a release candidate.

BUG_CLASSIFICATION=R1_BLOCKER
REQUIREMENT_SOURCE=docs/product/P0_PRODUCT_REQUIREMENTS.md; docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D007; GS-D009; GS-D010; GS-D022; GS-D023; GS-D032
TASK_SCOPE=GS-178 software Hub rule-decision to caregiver delivery
OUT_OF_SCOPE=GS-104 learning; production issuance; physical qualification; unapproved retention or partition changes

The current Node durable event stream cannot identify Hub-owned decisions:
Node EventKeys and enrollment provenance must remain attached to Node data.
The existing Hub checkpoint persists local rule latches but has no pending
derived-decision publication intent. Initial implementation will first establish
the independently authenticated backend receipt/read-model contract in the
isolated TEST_ONLY vertical, then attach a bounded Hub-owned durable sender.
No host receipt will be described as a qualified target storage format.

## GS-178 resumed implementation: separate Hub rule receipt (2026-10-19)

This checkpoint adds an isolated TEST_ONLY delivery path for deterministic Hub
rule decisions. It does not change the Node event wire identity. The production
`HubRuntime` still generates morning/night rule signals. The GS-178 host stack
serializes those signals as bounded Hub-owned decisions, stores them in a
separate protected `DurableEventOutbox`, and sends them after the ordinary
CloudSync event batch. The backend accepts a decision only over the existing
TLS 1.2 mTLS channel with a typed verified Hub context, trusted time, current
Hub/Home/epoch registry state, and (for event-derived decisions) a source Node
event already committed under that same owner. Exact retries return a duplicate
COMMITTED receipt; same-ID changed content is a conflict. Transfer or revocation
fences submission. The backend's rule endpoint is disabled by default and is
enabled only by the isolated TEST_ONLY durable API composition. It uses a
separate `hub_rule_decisions` table; concern decisions create one persistent
alert for the existing caregiver action workflow. The caregiver timeline and
browser display Hub decisions with their own decision ID and never show an
undefined or synthetic Node EventKey.
The existing long-open door rule has an explicit `:clear` Hub decision identity;
the close transition preserves the open/close history and resolves an earlier
door-left-open alert without recording a caregiver acknowledgement. A late
arrival of the warning is also marked resolved when its prior clear receipt
already exists.

The host outbox is durable once the decision intent is captured, and a lost
backend receipt is retried with the same bytes. **A crash between the existing
HubRuntime event checkpoint and capture of its rule signal can still lose the
derived decision**: the current target checkpoint persists rule latches but
does not atomically persist pending publication intent. The host outbox is not
composed into the S3 target scheduler. That scheduler currently calls
`run_state_once()` without a trusted local minute, so time-dependent target
rule execution also remains unqualified. These are explicit product gaps,
not qualifications conferred by host TLS/browser PASS. Full P0 product status
stays PARTIAL. GS-104 personalized learning remains on hold. No physical
operation or production endpoint was used.

New permanent cases cover morning decision, night concern, WAN/restart and lost
rule receipt, exact duplicate versus changed payload, wrong source, future
decision time, revoked credential, Home transfer, door warning clear and browser
identity display.
See `GS178-HUB-RULE-02` in GS-130 traceability. Exact final validation and
source checkpoint are recorded in the closeout below.

### Resumed execution closeout — 2026-10-19

Validated on the original canonical source checkpoint `ceeddc0` plus the
recorded working-tree changes. Local and `origin/feature/r1-commercial-baseline`
were equal before editing; no other worktree or hardware was used.

Implementation adds a TEST_ONLY Hub rule-decision transport and read model
separate from Node `DomainEvent`/EventKey. HubRuntime rule outputs are serialized
with stable decision IDs and a separate `:clear` identity for the door-close
resolution. The host simulator captures these into its bounded durable outbox;
CloudSync submits them after ordinary durable events through the existing
authenticated TLS/mTLS transport. Backend persistence is a separate table and
the handler is default-disabled outside explicit TEST_ONLY composition. It
requires verified Hub context, current Home/epoch, trusted time and, for
event-derived decisions, the already committed source event. Same-ID exact retry
is idempotent; changed content conflicts; revocation, transfer, wrong source,
and invalid chronology fail closed. The caregiver view renders the Hub decision
identity independently and retains original event history when the door alert
is cleared.

Executed validation on the changed source:

- `make -C code gs178-software-e2e`: PASS, 27/27. This includes normal
  Node-originated scenarios, morning/night deterministic Hub decisions, door
  alert clear, lost receipt/retry/restart/WAN recovery, ownership/revocation
  negatives, and browser caregiver rendering.
- `make -C code p2d-https-channel-host-test`: PASS; bounded real HTTPS channel
  host contract (`modes=8`, configured body/response/I/O limits and deadline).
- `make -C code cloudsync-security-ut`: PASS: mTLS 9 cases, TEST_ONLY adapter
  5, cloud trust 5 suites, CloudSync security 14, identity/time E2E 4, GS-168
  issuer/registry 10, NodeHealth 5.
- `make -C code validation-board-e2e`: PASS, 10 host-stack checks; physical
  stage NOT_RUN.
- `make -C code feature-coverage-test`: PASS at the working source checkpoint;
  215 features, 255 modules, 25 physical cases, mapping tests 22/22.
- `make validation-framework-test`: PASS, 51 tests.
- `make validation-hub` (reusing exact-source backend receipts): component
  stages include board-stack 10, C++ 1511, GS-40 1320, GS40 test bootstrap 33,
  storage sanitizer, CloudSync/mTLS and GS-130 HIL integrity 116, all PASS.
  Aggregate exits 2 because the existing Hub journal migration test fails
  `clean migration commits` and the mandatory P0 gate returns FAIL while
  `product_status=PARTIAL` (26/26 assertions themselves pass).
- `make validation-node`, `make validation-contract` and `make
  validation-backend` on the same source fingerprint: affected component
  stages pass; the required P0 stage preserves 26/26 assertion PASS but keeps
  aggregate FAIL at `product_status=PARTIAL`. Backend's Python stage is 528
  tests with 1 existing static PWA bundle-budget failure: total 117011 bytes
  versus 114688, CSS 21694 versus 18432.
- `make validation-pwa` reported 83 browser cases PASS and 3 unrelated settings
  locator timeouts (Family Members, Battery Alerts, Notifications). The legacy
  `pwa-68-browser-test` also exits 2 because Python module `websocket` is absent.
  All GS-178 browser integration assertions passed. The PWA aggregate therefore
  remains FAIL; these unrelated tests/assertions were not changed.
- Host compile/format checks and `git diff --check` passed. Full release gates
  were NOT_RUN. Android APK assembly and physical target execution were not
  performed; no browser/simulation or compile result is physical evidence.

Committed-source target build:

- Command: `python3 code/scripts/build_validation_targets.py`.
- Result: PASS, ESP-IDF 6.0.3, `GS_HIL_BUILD=OFF`, production target profile,
  target compile only; report
  `code/build/validation_targets/gs116-p0e50i_4/report.json`.
- Source HEAD: `2a389febe472c5e8a31da4a745dd8423a1087527`; source fingerprint:
  `475210604d053bed455fd237b6d299cb5e6e406fb66115727344e9498fd75ed0`.
- C3 image: 937,536 bytes, OTA slot 1,966,080 bytes, SHA-256
  `d9541f3947ca65df0a80a949912d7b05191c85aab51459815a37b595ba4804fe`;
  effective sdkconfig SHA-256
  `c8a7e0dcaaf7053acb1bc46db5cdb2fe1c567e5a02e9eb391d011b23a9789986`.
- S3 image: 2,168,368 bytes, OTA slot 4,194,304 bytes, SHA-256
  `310bafecbae5289fe4850edbb1d79c6f7714811fcce53df60f399fd0fd54ebe2`;
  effective sdkconfig SHA-256
  `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`.
- The builder emits no standalone profile-manifest file/hash; profile is the
  recorded `production GS_HIL_BUILD=OFF`, with effective sdkconfig hashes above.
  These images compile the canonical C3/S3 targets; this result does not show
  the TEST_ONLY startup selecting a credential-ready runtime, runtime NodeHealth
  delivery, or physical behavior. No image was flashed.

Android caregiver verification: `bash code/parivar_saathi_android_app/verify.sh`
passed 19 tests and XML structure
  validation. Android SDK, Java, Gradle and adb are absent in this environment
  (`ANDROID_HOME` unset), so no APK was assembled here. Existing connected-app
  API/browser software results are separate from a phone installation.

Jira evidence comments: GS-178 #11397, GS-59 #11398, GS-40 #11399, GS-148
#11400, GS-177 #11401, GS-116 #11402, GS-130 #11403. Ticket completion and
physical acceptance states were not advanced by host or compile-only evidence.

The implementation still has a real target gap: the S3 scheduler does not
atomically persist Hub-derived publication intent with the Hub checkpoint, and
the current target rule invocation lacks trusted local minute input. The new
outbox is composed in the host simulator only. Thus the tests establish a
software vertical for the simulated Hub runtime, not loss-safe target-side Hub
rule delivery. Keep the P0 release state PARTIAL and official GS-40/117/121
physical acceptance NOT_RUN. No board, production service, production identity,
or commercial trust setting was accessed.

### GS-40 TEST_ONLY product-build linker follow-up — 2026-10-19

Fixed deterministic naming for the external public config-root asset, rebuilt
the GS-40 TEST_ONLY S3 product profile from commit
`26e49162071975873881e88294216d08fe5e20c7`, and verified ESP image metadata,
partition fit, guarded TEST_ONLY symbols, and commercial-profile separation.
The artifact is build-only and not physically executed. Full hashes and
commands are in
[`GS40_TEST_ONLY_S3_LINKER_BUILD_20261019.md`](GS40_TEST_ONLY_S3_LINKER_BUILD_20261019.md).
GS-178 27/27 software E2E remains prior evidence and was not repeated because
this correction was confined to the build-time asset basename.

### Current-source five-run Bedroom Motion simulation — 2026-10-27

This is a later software-only rerun from canonical parent
`f6321597578bda69aa43056cbee70c863d5e625a`, after the latest GS-178 and GS-117
Jira instructions were read. Context preflight passed. The full release gate,
physical fixture and hardware acceptance were outside this run.

The first five exploratory repetitions had all used the host simulator's fixed
initial Node session `10`, so isolated databases still produced identical
synthetic EventKeys. To make this campaign independently traceable without
changing product behavior, the existing GS-178 host fixture now accepts an
optional TEST_ONLY initial Node session. Default remains `10`; NodeRuntime,
HubRuntime, security, persistence and CloudSync production sources are
unchanged. The integration report records UTC generation time and campaign ID.
The five campaign invocations assert the Bedroom EventKey matches that run's
session and sequence before saving its result.

Validation:

- `make -C code gs178-software-e2e`: **PASS, 33/33** (11 security and 22
  vertical integration tests; 227.076 seconds). This is the current-source
  GS-178 software suite.
- Five separately started `test_07_actual_shared_caregiver_browser_and_actions`
  runs: **5/5 PASS**, each in its own temporary TEST_ONLY backend database and
  TLS identities. Each passed all 17 existing Playwright caregiver assertions,
  authenticated Node/Hub admission, production NodeRuntime input/retention/ACK,
  Hub durable event handling, CloudSync, durable API `COMMITTED`, one durable
  business row per EventKey, and shared caregiver UI visibility. The scenario
  also sends one separate Call Family event to exercise the caregiver action
  view; both scenario events had one durable row. These results are
  `HOST_SIM_PASS`, not Android or physical acceptance.
- GS-117 console/ADB regression suite: **43/43 PASS**. Its exact-key Android
  observer positive and wrong-key negative tests pass; no serial adapter was
  opened by the tests.

| Campaign run | Bedroom EventKey (physical test identity, logical room, session, sequence) | Browser assertions | JSON report SHA-256 |
|---|---|---:|---|
| 01 | `test-c3-bedroom / bedroom / 42001 / 1` | 17 | `2002e262c70503eb594c20623404d0034b17b2a8e2b162f35b793307c74f5c7d` |
| 02 | `test-c3-bedroom / bedroom / 42002 / 1` | 17 | `7734f0ec21b75f55764dd425f0643d533a4e48f9470dc456179225aab5f689c9` |
| 03 | `test-c3-bedroom / bedroom / 42003 / 1` | 17 | `8cf0ff9945f12831c0e742e9b66d6048df18ea531768ff2a3e4313caa0ee0f97` |
| 04 | `test-c3-bedroom / bedroom / 42004 / 1` | 17 | `3e7bf0619118b48be17651b2831f62033838926dad5c01715fb16a4b053ffe48` |
| 05 | `test-c3-bedroom / bedroom / 42005 / 1` | 17 | `42e71393912d9ed1d525b8f619ac9320fea586799a7e66f2cd1a194b639a6ac9` |

Individual JSON, DOM and test-log artifacts remain in the ignored local
directory
`code/build/gs178_tc001_acceptance_20261027/verified-repeatability-final/`
with owner-only run directories. They are not fixture receipts and must not be
used as physical evidence. The full current-suite reports are in its
`full-suite/` subdirectory.

### Physical TC-001 readiness observed without opening board serial ports

ADB found the authorized Motorola Edge 60 Fusion (`ZA2237MRHN`). The installed
package `in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging` (versionCode 3), is installed and its MainActivity
was foreground. A read-only `adb pull` of the installed base APK matched the
preserved APK SHA-256 `0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`.
The preserved checkpoint records backend origin `https://192.168.1.10/` and Home
`gs177-test-product`; this check did not freshly authenticate the caregiver
session or verify the Home inside the app. A current read-only accessibility
dump of the foreground activity exposed no Home, Connected or Reports label,
so the authenticated app screen remains unverified. No local `apksigner`/Android SDK
build-tools were present. Android's `dumpsys package` exposes only an internal
signature token, not a certificate digest, so installed signer verification is
`NOT_VERIFIED` and the console-required fresh signer receipt is still absent.

The existing local backend health script passed PostgreSQL durability,
caregiver HTTPS and DNS/IP TLS identity checks at current Windows Wi-Fi address
`192.168.1.10`. It reported phone LAN reachability `NOT_VERIFIED`, Hub ingress
autostart disabled, and Hub ingress `NOT_CONFIGURED`. A direct socket check
found no current listener on port 8445; the saved ingress PID was no longer
running. Prior authenticated S3 ingress traces contain real physical EventKey
commits and authority-refresh HTTP 200 responses from 2026-10-26, but they are
historical and do not prove a live S3 CloudSync session on 2026-10-27.

The existing owner-only TC-001 `fixture.json` and
`five-run-campaign-approval.json` are absent. The last owner APK note contains
no exact EventKey/time. No Android signer receipt, current S3 mTLS receipt or
fresh C3/S3 runtime observation was created. The known synthetic/physical
NodeHealth freshness conflict was left untouched and is not a required event
delivery gate. Neither COM4 nor COM10 was opened; no board was reset or
stimulated, no credential/ownership/enrollment/database state was changed, and
no physical motion EventKey was generated. Thus the software milestone is
PASS, while the physical campaign remains **BLOCKED / NOT_RUN**. Do not request
the five-injection approval until the exact owner fixture, current signer and
ingress readiness receipts exist.

## 2026-10-27 — software use-case batch S1 audit (execution in progress)

Owning Jira GS-178; coverage GS-130; validation GS-116. Owner comments
11748/11750/11749 prioritize the existing one-command host campaign independently
of GS-117 (OnHold). Canonical baseline f7168825a4751330629bf285c3bad83c21a87b51;
preflight PASS; tracked clean, unrelated untracked assets preserved.

Existing implementation: production Node input qualification/retention/AEAD,
HubRuntime journal/coverage/deadline/rule checkpoint, CloudSync mTLS, durable
backend, authenticated caregiver API and shared browser. Existing tests 01–18
and security suite already cover event delivery, lost ACK/WAN/restart replay,
night and door concerns, privacy, caregiver actions and authority isolation.
Reused entry point: `make -C code gs178-software-e2e` (prior 33/33).

Classification: IMPLEMENTED_NOT_YET_VALIDATED for the full missing-morning
concern path and its never-seen/expired coverage, clock/mode suppression,
receipt-loss/restart and caregiver browser outcomes. TEST_INFRA_ONLY changes
extend existing integration tests, simulator observation and browser helper;
no product algorithm/wire/storage change is planned. GS-D021/022/023 and P0
requirements require missing observations not to imply inactivity. Current
CoverageTracker explicitly describes present coverage only; full-window gap
history, calendar/prompt orchestration and personalized learning remain
PARTIAL/ON_HOLD rather than accepted by this batch.

Affected test interfaces: deadline reason/identity reporting, existing NodeHealth
software input, Hub decision mTLS receipt and caregiver UI. Regression plan:
new cases, full existing GS-178 suite, relevant Hub checkpoint tests and
lightweight framework/traceability registration checks. Target builds and
hardware are not required for test-only changes. No release gate, alternate
framework, physical/ADB endpoint migration, or held feature implementation.

### Established gap before product edit

OWNING_JIRA=GS-178 (coverage/liveness feature GS-40)
BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=docs/product/P0_PRODUCT_REQUIREMENTS.md (coverage and inactivity)
DECISION_IDS=GS-D021;GS-D022;GS-D023
EXISTING_IMPLEMENTATION=HubRuntime authenticated health/contact and CoverageTracker
EXISTING_TEST_EVIDENCE=baseline GS178 33/33; new S1 focused run 1/5 PASS, four failures
VERIFIED_GAP=NodeHealth passes trusted_contact_at=0 to the existing contact API; backend can be COVERED while Hub deadline coverage remains UNKNOWN despite authenticated healthy Nodes
USER_USE_CASE_IMPACT=healthy silent household cannot produce the existing eligible missing-morning concern
MINIMUM_REQUIRED_CHANGE=carry optional caller-verified UTC through authenticated health to the existing coverage update; S3 uses the existing signed-time snapshot guard; preserve default zero/UNKNOWN
AFFECTED_COMPONENTS=Hub runtime and S3 adapter; host simulator adapter; existing NodeHealth-to-caregiver contract
SECURITY_AND_DURABILITY_IMPACT=no new trust/time source; identity/session/sequence validation still precedes coverage; health remains distinct from activity/EventKey; no persistent-format change
REGRESSION_REQUIREMENTS=runtime unit/checkpoint, GS40/cloud contracts, board E2E, full GS178/API/browser, registration, applicable S3 build
OUT_OF_SCOPE=historical interval coverage, new routine semantics, physical operations, held learning and release approval

The separate partial-coverage test also expected four changed snapshots for three
observed Nodes; actual three is correct and the test expectation is corrected.
Initial failed reports/log are preserved in `code/build/gs178_s1_20261027/focused/`
and `code/build/gs178_s1_focused.log`.

Second S1 run reproduced an independent caregiver defect: three healthy Nodes
made Home monitoring COVERED while the fourth active enrolled Node had never
been observed. `NodeHealthStatusStore.latest()` joined from observations and
omitted missing members of the current enrolled roster. Classification R1_FIX,
owner GS-40/GS-178; P0 coverage/UNKNOWN requirement and GS-D021 apply. Minimum
fix: query the authenticated active enrollment roster, left-join only matching
current authority observations, and return UNKNOWN/null contact metadata for
unobserved or invalidated records. Preserve cross-Home/epoch/key/generation
fences. Regression: NodeHealth API/read model, full backend tests, shared UI and
GS178 browser. No stored row or credential mutation. A prior fingerprint test
will assert UNKNOWN with no reused contact metadata instead of hiding the
still-enrolled device. The lost-receipt test also filtered only HTTP 200 and
missed the valid initial HTTP 201 commit; accept both committed statuses while
retaining exact identity/duplicate assertions. Failed reports remain preserved.

### 2026-10-27 — S1 missing-observation and inactivity batch results

Audit disposition: GS-178's Node → HubRuntime → CloudSync → authenticated
backend → caregiver path, production-code host simulation, and Playwright
observer already existed. GS-130/116 scenario inventories and gates were reused;
no second runner, event pipeline, database path or UI observer was added. The
verified gaps were limited to current authenticated contact time not reaching
the existing Hub coverage API, and the caregiver NodeHealth read model omitting
an active enrolled Node with no health row. Both are corrected without changing
wire/storage format, health-to-activity semantics or authority rules. Contact
can establish current observation coverage only; it never creates a motion
EventKey or counts as resident activity.

The existing `make -C code gs178-software-e2e` now executes 37 tests (15
security and 22 vertical cases). Run:

```sh
GS178_REPORT_DIR=build/gs178_s1_20261027/full-suite make -C code gs178-software-e2e
```

Result: **37/37 PASS**, 409.934 seconds. The four added vertical cases are:

| Case | Verified behavior | Result boundary |
|---|---|---|
| `test_19_covered_absence_boundary_receipt_loss_and_restart` | 119-before/120-grace boundary; a covered, silent morning creates one authenticated Hub missing-morning concern; 201 initial/200 duplicate receipt; WAN loss, lost receipt, Hub/backend reopen and same decision identity; caregiver browser sees the concern. | `HOST_SIM_PASS`; time-derived concern has no source Node EventKey by design. Browser report has 5 assertions. |
| `test_20_never_seen_node_is_missing_observation_not_inactivity` | An active enrolled Node with no observation remains `UNKNOWN`; no concern or fabricated event; caregiver browser shows four Nodes with unknown health and no false activity. | `HOST_SIM_PASS`; browser report has 8 assertions. |
| `test_21_expired_coverage_suppresses_absence_then_contact_recovers` | Expired health cannot satisfy the inactivity rule; a fresh authenticated Node contact restores coverage without inventing activity, an event or a concern. | `HOST_SIM_PASS`; API/software projection checked, no browser claim for this case. |
| `test_22_untrusted_rule_time_and_modes_suppress_until_eligible` | Untrusted time and Away/Paused/Privacy suppress the decision; trusted time in Home permits exactly one decision. | `HOST_SIM_PASS`; no physical or APK claim. |

The independent repeat of test 19 passed **1/1** using Node session `53001`
and decision identity `missing-morning:gs178-morning-53001`. All 22 vertical
case reports recorded `first_failed_stage=null`, physical status `NOT_RUN`,
and actual Android `APK_NOT_VERIFIED`. Prior focused iterations exposed the
missing trusted-UTC path and a backend roster omission; the initial assertions
also incorrectly counted a valid HTTP 201 as absent and expected four updates
for three observed Nodes. Those assertions were corrected to preserve, rather
than weaken, the expected status and identity checks. The early failure logs
remain in ignored `code/build/gs178_s1_20261027/` evidence. One manual repeat
first failed to import because its invocation omitted `tests/integration` from
`PYTHONPATH`; the corrected command passed and the normal one-command suite is
the authoritative repeatable entry point.

Additional validation on this source:

| Command | Result |
|---|---|
| `IDF_PY_BUILD_JOBS=2 python3 code/scripts/build_validation_targets.py` | C3 BUILD PASS, 944,272 bytes; S3 BUILD PASS, 2,197,568 bytes. ESP-IDF production profiles; no flashing. The modified Hub adapter compiled in S3. |
| `make -C code validation-sanitize` | PASS. ASan/UBSan C++ suite 1,516 checks; GS40 host suite 1,320 checks. |
| `make -C code hub-runtime-checkpoint-host-test p2d-cloud-contract-host-test` | PASS. Runtime checkpoint/replay/crash boundaries; CloudSync receipt modes, bounded batching/retry and completion persistence cuts. |
| `make -C code validation-board-e2e` | PASS, board-stack 10 scenarios; SOFTWARE PASS / physical NOT_RUN. |
| `make -C code validation-framework-test feature-coverage-test` | PASS after traceability correction: framework 51/51; feature map 226 features / 285 modules / 27 physical cases; registration unit tests 22/22. This validates consistency only, not exhaustive semantic or physical acceptance. |
| `make -C code python-test` | **FAIL**: 623 tests; 621 passed, one approved historical ESP32 NVS-reserve test skipped, one failure in existing `test_static_payload_and_collection_budgets`: CSS 29,576 bytes exceeds 18,432. This task did not modify caregiver CSS. Keep the failure visible and triage with existing GS-177 ownership. |

The focused Python NodeHealth suite contains six passing tests, including the
new never-seen → UNKNOWN → authenticated contact → revocation sequence. The
main E2E and repeat exercise production NodeRuntime/HubRuntime, actual local
TLS/mTLS and backend commit/read-model paths plus shared caregiver browser UI;
they are `HOST_SIM_PASS`, not target or phone tests. The changed firmware
adapter also compiled in both standard production target builds. No Android
device, COM port, physical sensor, production service or physical event was
used. The installed Android APK, caregiver login on a phone and physical
TC-001/AM312 remain unverified/NOT_RUN; GS-117 remains OnHold. All 17 P0 use
cases and R1 product status remain PARTIAL; full-window missing-observation
history and calendar/prompt orchestration remain incomplete, and GS-104
personalized learning remains on hold.

Registration validation was not treated as a cosmetic check: the first
`make -C code validation-framework-test feature-coverage-test` had framework
51/51 PASS but the mapper failed because the added C++ and Python unit-test
files were listed under GS-178 E2E without their existing `cpp`/`python`
owners. The traceability row now maps all four existing stages (`cpp`,
`checkpoint`, `python`, `gs178-node-caregiver-e2e`) and their exact registry
commands/gates. The corrected feature-coverage check passed; no case was left
unregistered to make the error disappear.

Offline GS-117 note: the prior private C3 JEDEC result is `0xffffff`, so the
actual capacity remains UNKNOWN and the capacity-first hardware guard remains
failed. Reviewing the preserved helper and installed esptool 5.4.0 source
offline showed the helper requested `flash_id()` before `run_stub()` but did
not call the existing ROM-loader `attach_flash()` step. The official esptool
`flash-id` CLI attaches/configures SPI flash before reading its JEDEC ID. This
makes a helper-ordering/tool-initialization issue plausible; it does not prove
the C3 flash is healthy or establish its capacity. No retry, port open, or
hardware access is included in this GS-178 task; GS-117 stays OnHold pending a
separate scoped approval and correctly initialized read-only procedure.

Evidence directory: `code/build/gs178_s1_20261027/`; repeat report:
`code/build/gs178_s1_20261027/repeat-53001/`; full-suite report:
`code/build/gs178_s1_20261027/full-suite/`; paired build report:
`code/build/validation_targets/gs116-llw2l7ga/report.json`. These are local
ignored software test/build artifacts, not physical fixture receipts. Validation
source is the GS-178 S1 diff based on canonical
`f7168825a4751330629bf285c3bad83c21a87b51`; its staged code subtree is
`052d1c2c9e2a59c052a76660b281a30f9f5414e7`. The full commit and remote
verification are recorded in the closeout Jira comment.

## 2026-10-27 S2 addendum — Hub-link versus WAN outage recovery

**Audit and gap:** GS-178 is the owner of this existing software vertical;
GS-130's P0-UC-09 and proposed R1AUTO-027/028 describe Hub/link versus
internet-only outage behavior; GS-116 requires the affected existing campaign
and registration checks. The C3 NodeRuntime, authenticated Hub admission,
durable Hub outbox, CloudSync, backend commit/read model and caregiver UI were
already implemented and exercised in separate paths. The missing item was a
joined caregiver-visible vertical for the two outage boundaries. This was
classified `IMPLEMENTED_NOT_YET_VALIDATED`; no production behavior was found
defective. The only code change is a bounded TEST_ONLY radio-response switch in
the existing GS-178 host simulator, used by the existing vertical/browser test.

The new `test_23_hub_link_and_wan_outage_recovery_exact_keys_and_caregiver_view`
asserts:

1. With the Node-to-Hub test link unavailable, the Node retains original
   `bedroom:10:1`, receives no ACK, and Hub storage/backend/API have no event.
2. After the existing source freshness window expires, caregiver API and the
   shared browser render stale/unknown coverage with no fabricated event.
3. Restoring the local link while WAN/CloudSync remains down lets the Hub
   authenticate the retry, durably store it before ACK, and retire the Node's
   retained event. A second event is likewise locally durable; the backend
   still has zero commits. The Hub is restarted while WAN remains unavailable,
   and both Hub outbox entries survive.
4. On WAN recovery, CloudSync commits both events. The API returns the exact
   physical/logical/session/sequence keys in correct chronology; the isolated
   backend SQLite store has one event and one durable commit per key; the
   caregiver browser observes the same ordered keys before and after reload.

Validation:

| Command | Result |
|---|---|
| `make -C code gs178-host-build` | PASS; TEST_ONLY existing production Node/Hub host stack rebuilt, no target or hardware access. |
| Focused `test_23_hub_link_and_wan_outage_recovery_exact_keys_and_caregiver_view` | PASS 1/1; two browser observations passed (stale/no event, 4 assertions; exact-key recovery before and after reload, 6 assertions). The browser helper's first full-suite run undercounted the latter by one in its report metadata; this was corrected and verified in the focused repeat. |
| `GS178_REPORT_DIR=build/gs178_s2_20261027/full-suite make -C code gs178-software-e2e` | PASS 38/38 in 273.500 seconds: 15 security + 23 vertical tests. All generated reports have `HOST_SIM_PASS`, null first-failing stage, physical `NOT_RUN`, and Android `APK_NOT_VERIFIED`. |
| `make -C code validation-framework-test feature-coverage-test` | Framework PASS 51/51. First mapping attempt failed because the traceability checker accepts one assertion anchor per feature row, not a semicolon list; corrected the row to the new test 23 anchor. Rerun `make -C code feature-coverage-test` PASS: 226 features / 285 modules / 27 physical cases and 22/22 traceability tests. |
| Post-commit focused test 23 on `bfbae7796df55a0db098ab7c6e13232d2f558808` | PASS 1/1 in 24.047 seconds; `source_revision` equals the full commit SHA; outage/recovery browser assertions 4/6; `HOST_SIM_PASS`, physical `NOT_RUN`, Android `APK_NOT_VERIFIED`. |

The report directory is ignored local evidence at
`code/build/gs178_s2_20261027/full-suite/`. Its new scenario report is
`P0-UC-09-HUB-WAN-CAREGIVER-RECOVERY.json`; the browser artifacts separately
show the stale outage view (4 browser assertions) and restored exact-key
timeline (6 browser assertions). The resulting API keys were
`test-c3-bedroom/bedroom/session 10/sequence 2` and the same identity at
sequence 1, in descending occurrence-time order. The test-source SHA-256 is
`8160cd3bf6c0643b0934518c51958cfb6b37dc1ecc85d8e49649fa22300a91b7`, simulator
source SHA-256 is
`7a6552782daf7643fb80a8f923f9e6859e5a68f6aec805de87058190b00e5b02`, browser
helper SHA-256 is
`18f759f4b66a1e85db74dd96a874b61364d1f12667c062f6ea627fec42b095d2`, and the
compiled host simulator SHA-256 is
`a7f57c3450949d6f54181070f7b1e5b87da1d57e7848ecd0af5c4a91054ebafd`. The test run
was performed on the S2 source diff based on `9e87c435db805f14be165286dc5cc9a5dd05a9ce`;
the harness's `source_revision` therefore records that base SHA while the
test-source SHA and built host simulator binary identify the modified inputs.
The commit-bound focused report is preserved at
`code/build/gs178_s2_20261027/commit-bfbae77/P0-UC-09-HUB-WAN-CAREGIVER-RECOVERY.json`;
it records exact source SHA `bfbae7796df55a0db098ab7c6e13232d2f558808`, API keys
for session 10 sequences 1 and 2, two durable backend events/commits, 4/6
browser assertions, and no first failed stage.

This is deterministic host simulation over the existing product stack. It is
not physical RF/flash qualification, an actual Android APK observation, or
proof of the production deployment/backend authorization path. P0-UC-09 and
all 17 P0 use cases remain `PARTIAL`; GS-117 physical TC-001 remains
`NOT_RUN`/OnHold. No hardware, ADB, COM port, production service, new runtime,
test framework, or duplicate Jira case was used.

### 2026-10-28 — persistent PostgreSQL software path to the installed APK

This run closes the prior `APK_NOT_VERIFIED` gap for the requested software
vertical. It reuses `ProductStack` from `code/tests/support/gs178_stack.py`, the
existing C++ `gs178_product_host`, the existing GS-179
`TestOnlyMtlsListener`, the existing persistent GS-148 PostgreSQL API, and the
installed Parivar Saathi APK. No source, runtime, event pipeline, framework,
credential or enrollment was changed, and no database event was inserted
directly. A single Node-boundary `motion` input created the business event.
The pre-existing host executable was not rebuilt for this checkpoint; its
SHA-256 was
`a7f57c3450949d6f54181070f7b1e5b87da1d57e7848ecd0af5c4a91054ebafd`.

The local backend health command passed PostgreSQL TLS `verify-full` and
durability (`fsync`, `synchronous_commit`, `full_page_writes`), caregiver HTTPS,
local backend and current `.6` endpoint TLS validation. The WSGI caregiver API
and the simulated Hub listener used the same existing PostgreSQL DSN. The
simulator used the seeded TEST_ONLY `test-hub-product` enrollment and the
existing `gs177-test-product` Home; it did not claim a Hub or enroll a Node.
The CloudSync request reached a bounded, loopback TEST_ONLY mTLS listener
running the existing GS-179 authenticated Hub/API code. This is a software
Hub/listener path, not physical S3 authentication.

One `input 0 motion ...` at the Node host input produced Node ACK `DURABLE` and
the original EventKey:

```text
physical_device_id=test-c3-bedroom
logical_node_id=bedroom
origin_session_id=2026102801
event_sequence=1
canonical=p15:test-c3-bedroomn7:bedrooms2026102801q1
```

The Hub submitted this key through authenticated TEST_ONLY CloudSync. The
backend returned HTTP 201 `COMMITTED` for the first commit; its receipt was
deliberately dropped after commit, so that CloudSync attempt completed 0. The
Hub retried the same queued EventKey. The backend returned HTTP 200 (the
existing API selects that status for `duplicate=true`), and the retry
completed 1. PostgreSQL then contained exactly one `durable_event_commits` row
and one joined business event for this key (`MOTION`, `bedroom`). No second
Node input was issued.

The actual laptop HTTPS API at `https://192.168.1.6/` passed trusted-CA TLS,
caregiver login and Home binding. Its authenticated
`AUTHENTICATED_GS148_TEST_ONLY` overview returned HTTP 200 and exactly one entry
for the same EventKey, kind `MOTION`, room `bedroom`, Home epoch 1. Occurrence
time is `2026-10-28T03:16:55Z` (`28/10/2026, 8:46:55 am` on the phone); backend
receive time is `03:16:59Z` (`8:46:59 am`). PostgreSQL and API exact-key counts
were both 1.

The authorized Motorola Edge 60 Fusion (`ZA2237MRHN`) ran the existing ADB
observer against the installed package
`in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging` / versionCode 3. The currently installed base
APK was pulled read-only and hashed at
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`, matching
the previously preserved install bytes. The embedded signer digest continues
to match the owner-only install receipt (`d336ae68479da03de932a44b16c8de730c86e3cf68aee52fe92261e74e596b85`);
formal `apksigner verify` was unavailable, so this is byte/package identity
plus receipt-backed signer corroboration, not a new formal signature-verifier
result.

After foregrounding the APK and forcing its normal visibility refresh, the
Reports/Event Details accessibility tree and screenshot showed the exact key,
`Motion recorded`, `bedroom`, `28/10/2026, 8:46:55 am`, and backend receive time
`8:46:59 am`. The app showed `CONNECTED`, Home `gs177-test-product`, origin
`https://192.168.1.6/`, and the durable history increased from 138 to 139
records. The same key remained present after the observer's refresh. Private
evidence (mode 0600) is in
`~/.local/state/ghar-sajag/gs178-android-check-20261028/`:

| Evidence | Result |
|---|---|
| `fresh-node-hub-postgres-event.json` | Node ACK `DURABLE`; first CloudSync response lost after HTTP 201 commit; exact-key retry HTTP 200; one PostgreSQL commit and business event. |
| `external-backend-api.json` | Trusted HTTPS to `.6`, authenticated caregiver API, same Home and exact-key count 1. |
| `android-fresh-event-verification.json` | Existing ADB observer PASS; actual installed APK, connected backend, Home, exact EventKey and post-refresh verification. |
| `fresh-event-android.png` / `fresh-event-android.xml` | Screenshot SHA-256 `e495cdf3ce11ee7df536feb0f25b2ccf61e4af36ff9a5c716e52dec9c5785940`; hierarchy SHA-256 `20bd1494bb63f88c65f99e9ae295096f2574a2824987e0da691449956296f265`. |

The observer's first invocation stopped at its Settings navigation guard while
the app was changing screens; the app was subsequently confirmed in Settings
and the existing observer passed. This was an observer starting-state issue,
not a failed event-processing stage. A separate browser run against the actual
`.6` service was not performed in this checkpoint. Prior 39/39 GS-178 browser
tests remain HOST_SIM evidence and are not substituted for this Android result.

Classification: `HOST_SIM_PASS` through the real installed APK for this one
TEST_ONLY software event; actual Android observation is verified. This does
not satisfy the separate real-board web-to-USB→C3→S3 acceptance recorded in
GS-178 Jira comment 11767. No C3/S3, sensor, COM port or physical ingress was
accessed. Physical TC-001 and AM312 remain NOT_RUN; GS-178 remains In Progress,
all 17 P0 groups and the complete product remain PARTIAL.
