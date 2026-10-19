# GS-178 software vertical — execution record

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
