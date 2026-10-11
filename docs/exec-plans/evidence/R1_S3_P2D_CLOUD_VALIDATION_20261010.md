# P2-D cloud implementation checkpoint — 2026-10-10

## Canonical source handoff — 2026-10-10

The reviewed P2-A/B/C and partial P2-D source/evidence are now selectively
integrated into `/home/udaybhan/projects/Ghar_sajag_r1` on
`feature/r1-commercial-baseline` (integration source checkpoint
`1febcf027baea892b95ed3a57615a4a562ee9b82`; final validation/delivery pending).
Continue future R1 work only in that canonical worktree. This P2-D handoff remains
the current technical source for GS-148; the separate S3 branch and generated
`sdkconfig`/`managed_components/` are preserved and must not be treated as the
development destination.

Status remains PARTIAL: production authentication/provisioning and
owner/enrollment-generation-bound durable COMMITTED contract, configured trusted
endpoint, active S3 connectivity worker and canonical 72-hour workload contract
are missing. Live production backend E2E, canonical 72-hour cases and physical S3
qualification are NOT_RUN. Production body/identity deletion is DISABLED. The
current integrated core test still reports the known Node sequence assertion as
FAIL; preserve that result without changing C3/BAT-C8 behavior to clear it.
Resume only after the BAT-C8 priority switch ends and the required backend and
workload contracts are supplied/approved.

Authority: IMPLEMENTATION_DESIGN / TEST_EVIDENCE; no new product decision.
START_HEAD=17c5cfded8d809535bc846fbf8108a9b8cca0e1a. Context preflight PASS at
2026-10-09.001. Actual origin feature/r1-s3-hub-bringup matched START_HEAD.
GS-148 description is historical for P2-C; latest comments 10289/10290 establish
P2-C closure and verified GitHub delivery. No newer comment was present at intake.

## Essential contract gaps

Backend DATA_MODEL.md defines POST /v1/homes/{home}/events and the file-backed
SQLite FULL-synchronous transaction. JsonApi requires trusted middleware to set
internal gs.verified_hub and an injected authorizer to bind Hub, home and EventKey.
It explicitly calls its X-Actor-Id adapter development-only. No production
middleware/credential mechanism, Hub principal provisioning, intended backend
origin/CA or deployment configuration is supplied. EventKey/COMMITTED/duplicate
responses do not carry home, owner/enrollment generation or a payload digest.
The existing TLS-authenticated exact-request boundary must not be described as
an independently signed owner/generation receipt. Production contract clarification
was requested before choosing a credential or owner-generation mechanism.

The dated offline_72h_model.py / R1_STORAGE_72H_SCENARIOS_20261008.csv mixed NORMAL
row has 728 exact records PLUS 197 candidate summaries; HIGH has 3278 exact PLUS
298 candidate summaries. STRESS mixed has 42679 exact plus 1682 summaries.
The requested 728/3278/6556 total-event matrix does not specify those complete
traces. No approved distribution or production summary-substitution protocol
resolves the mapping. Canonical GS-D025 locks the design target, not these volumes;
GS-D026 permits loss-aware aggregation but not arbitrary source deletion or a
new summary API. Distribution clarification was requested; do not silently
truncate the source model, map unspecified local_outcome records, or label a
synthetic fixture as this canonical matrix.

## Independent implementation scope

Within the established endpoint/CloudSync interface: bounded exact COMMITTED JSON
parsing, synchronous per-request HTTP binding, configured HTTPS channel with
mandatory CA/hostname verification, redirect refusal, bounded framing/writes/reads,
and no network-send completion. Credentials are opaque deployment inputs rather
than a new approved scheme. No endpoint, CA, credential or secret is compiled in.
This channel is not wired to the production owner task: authentication/provisioning,
STA/ESP-NOW channel coordination and a nonblocking owner/worker contract remain
essential gates. The S3 composition compiles the adapter; compilation is not an
active production caller or live service connection.

CloudSync scheduling is limited to 16 staged events and 64 transient retry/conflict
hints, without limiting durable event count. Eviction forgets only scheduling hints;
pending bodies remain authoritative and idempotent retry is safe. Caller-supplied
same-key content must match the original serialized journal record. Retry counters
and time arithmetic are capped. No new persistent delivery ledger is introduced.

BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D023,GS-D029
TASK_SCOPE=authorized P2-D delivery correctness/bounds and supported contract tests
OUT_OF_SCOPE=guessed production auth/owner-generation/workload contracts, retention approval, physical hardware, C3/BAT-C8, other worktrees

Supported-interface host/build validation is finished; the overall P2-D gate is
not complete. No live-backend, requested 72-hour matrix or physical qualification
is claimed. Production deletion remains DISABLED.

## Validated host scope and measured limits

The final measured SQLite bridge accepts 300 events through the six-Node
`HubRuntime` authenticated admission seam, verifies durable-before-ACK, reboots
with all original encrypted bodies, and catches up in three interrupted phases.
It invokes the actual Python JsonApi/DurableEventCommit using a deterministic
injected authorizer and stdio channel. Separate SQLite connections verify each
commit is visible before a reply; repeated submissions produce one logical event
and one set of critical-event effects. The fixture injects actor-header auth
failure, backend commit with lost reply, wrong-device receipt and truncated reply.
Three backend restarts and three Hub catch-up reconstructions preserve correctness.

Final measured run: 300 peak pending, 304 requests, 300 backend/local COMMITTED,
zero final pending, three duplicates, four injected failures; 30 critical-event
alerts/jobs/durable notification entries, with no duplicate logical effects.
`rejected=3` counts channel metadata failures only; the wrong-key reply is the
fourth fixture failure and is rejected by receipt decoding. Offline outbox logical
bytes=49,826; final/peak logical=77,452; peak POSIX allocated=90,112. Identity
logical bytes=44,046, held in a separate memory fixture rather than the same
POSIX partition. Configured reserve=524,288 bytes. This does not measure physical
critical reserve or qualify the combined 4 MiB LittleFS packing boundary.

Catch-up elapsed=138,863 ms; whole fixture elapsed=141.260 s under concurrent
host compiler/regression load. Time is deterministic accelerated scheduling with
real host processing, not Internet throughput or 72-hour endurance. Body snapshots
and original serialized requests are compared across retry/reboot. No bodies or
identities are deleted. No new persistent in-flight ledger is needed for supported
idempotent submission; uncertain replies leave durable pending state authoritative.

Protocol tests preserve 200 pending records across 14 invalid receipt modes and
reject every prefix truncation, modified original content/time, wrong event key,
wrong session/sequence, wrong logical/physical device, malformed/duplicate JSON,
HTTP 202/204, unverified channel and incomplete response. Unicode escaping is
covered. Both torn completion append and failed completion publication recover
and accept the exact durable receipt after reboot. HTTPS adapter tests run the
actual target source against a fake IDF client: eight failure/framing modes,
partial writes/fragmented reads, TLS/hostname configuration, no redirects, bounded
I/O and cleanup. They do not exercise real certificate/credential validation.

Measured queue count/capacity=16, retry-hint peak=64. Configured request/response
bounds=2048/1024 bytes; read staging=256 bytes; IDF RX/TX buffers=1024 each.
These are logical bounds, not a total heap/PSRAM measurement: TLS allocations,
string allocator overhead and target concurrency remain unqualified. Conflict
hint eviction permits idempotent resubmission without changing durable pending.
One blocking operation can overrun the 5-second soft transaction deadline by its
configured 3-second I/O timeout. An owner task must not call this synchronous
channel while responsible for Node ACKs; production worker ownership remains open.

## Unverified mandatory acceptance criteria

NORMAL_728/HIGH_3278/STRESS_6556 P2-D outage/catch-up matrix: NOT_RUN, awaiting
approved complete traces. Existing similarly sized storage regressions are not
substitutes. Active S3 transport/caller, credential provisioning, owner/generation
receipt binding and connectivity state machine: BLOCKED by essential contracts.
Live authenticated backend E2E, actual credential/cross-owner rejection and live
service durability: NOT_RUN. Target memory, physical 72-hour/power-cut/wear and
signed OTA rollback qualification: NOT_RUN. P2-D overall remains PARTIAL.
P2-E retention and Phase 3 remain open; production deletion remains DISABLED.

### Core-suite linker correction

The combined regression command exited 2 after all ten specialized targets ran
successfully: `cpp-test` omitted DurableEventOutbox/OpenSSL source and `-lcrypto`,
which the already implemented HubRuntime replay-fence method requires. The recipe
is corrected, with no production code change. The final core rerun uses
`make -o Makefile cpp-test`: only link inputs changed; existing objects retain
identical source and compiler flags, so treating the Makefile timestamp as old
avoids an unnecessary complete recompilation. Source dependencies remain active.

BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=required P2-D regression validation
DECISION_IDS=NONE
TASK_SCOPE=repair demonstrated core-suite link failure
OUT_OF_SCOPE=unrelated build recipes/product semantics

## Final gate results and reproducibility

| Gate / raw log | Actual exit | Result |
|---|---:|---|
| `focused-final-source.log` | 0 | Final protocol/bounds and two local completion cuts PASS |
| HTTPS portion of `focused-rerun.log` | 0 aggregate | Eight modes PASS; production sources unchanged afterward |
| `bridge-final.log` | 0 | Final measured 300-event real SQLite/Hub bridge PASS |
| `backend-unit.log` | 0 | Six durable backend tests PASS |
| `backend-integration.log` | 0 | Existing lost-response/duplicate/restart bridge PASS |
| `sanitizers.log` | 0 | Final source focused ASan/UBSan protocol, cuts and HTTPS PASS |
| `bridge-asan.log` | 0 | Final source instrumented SQLite/Hub bridge PASS |
| `regressions.log` | 2 | Ten specialized targets PASS; core link recipe failed |
| `core-final.log` | 2 | Link corrected; unchanged Node sequence assertion FAIL |
| `core-baseline.log` | 1 binary | Same assertion with starting CloudSync implementation |
| `s3-build.log` | 0 | Clean isolated IDF 6.0.3 ESP32-S3 build PASS |
| `context-final.log` | 0 | Context PASS at 2026-10-09.001 |

The ten specialized targets are mixed body, incremental completion, identity
compaction, runtime checkpoint, backend commit, durable outbox, segmented runtime,
commissioning crypto, Node persistence and Hub retirement snapshot. Combined make
reports only the core failure; each specialized target completes successfully.
Mixed recovery reproduces 84 interruption checks, 32 reuse windows/3232 admissions,
12 six-Node windows/1440 admissions and 32768 allocated bytes recovered. Checkpoint,
6556-record outbox and 12000-identity multiwindow regressions pass. These are
existing storage/security regressions, not requested P2-D outage matrix results.

Core failure is `test_node_offline_resilience` at the expectation that 1000 attempted
motions leave `next_sequence()==1001`. Neither its Node implementation nor test
was changed. Replacing only the CloudSync object with the START_HEAD implementation
reproduces the same failure. No BAT-C8/Node fix is made. This full-suite gate remains
FAIL; all P2-D delivery claims must retain that limitation. The linker repair is
validated to build/run the suite, not to make the assertion pass.

ASan bridge catch-up=27098 ms; whole fixture=28.441 s, with identical counts/storage
and less concurrent compiler load. Neither run is a target throughput guarantee.
Clean S3 image=1863536 bytes, SHA256
`f102703d1074119b45e29409879aade15e686c7dccad85da18444fc81c58cc85`.
Unused adapter code may be removed by the linker; unchanged image size is not
proof of runtime integration. Production deletion flags remain default n/undefined
and the default OutboxLimits gate remains false. No physical command was run.

Raw evidence: [raw/R1_S3_P2D_FINAL_20261010](raw/R1_S3_P2D_FINAL_20261010/commands.txt),
including exact commands, observed exits, source/executable hashes, log creation
and final-write UTC timestamps. Log intervals include compiler scheduling and
are not precise per-suite CPU times. Initial fixture/link failures are retained
as diagnostics, not PASS evidence. Whitespace checks pass after final staging.

Jira: source-gap comment 10293 and validated host milestone 10305 succeeded.
Final commit/push verification and a final dated Jira comment follow this evidence
checkpoint. GS-148/Phase 2 remain open; do not equate the pushed partial checkpoint
with P2-D delivery. The final Jira comment records the commit and actual remote
verification to avoid a self-referential commit hash in this document.

## GS-148 P2-D CloudSync/API integration checkpoint — 2026-10-11

Scope is limited to the user-approved P2-D durable CloudSync/API path. P2-E/F,
physical Phase 3, GS-114, hardware, destructive reclamation and release campaign
remain on hold. Starting canonical local/origin HEAD was
`2b1c15c97a917521c142db1b3973382274c306ff`; context preflight passed at
`2026-10-10.001`.

### Reproduction and classification

`make validation-p0-e2e` at the starting source reproduced the P0 failure:
`POST /v1/homes/home-p0-e2e/events` with the exact production-shaped S3
CloudSync EventKey body returned `503 durable_event_store_unavailable`. The
request was scenario `P0-GAP-001`; the durable body carried structured physical
device, logical Node, origin session and sequence identity. Reproduction report
source fingerprint was
`add14d809ae6ee942f0d282a668bbe72e7071b6d25efb6353d24027f11f85285`; its log
SHA-256 was
`dfaed9bd5b9049175b710753dec9ccea4e27094d25f4de32e6490aed589dabcb`.

Root cause: `JsonApi._dispatch` correctly fails closed for an EventKey request
when `durable_events` is unset. The P0 `LocalProductStack` constructed
`JsonApi(service, now=...)` without the existing `DurableEventCommit` adapter.
The default `http_api.main()` is explicitly the in-memory development adapter;
there is no configured production service composition. This 503 occurred before
Hub authorization or a SQLite transaction, so it was not an authentication
rejection or storage commit failure. Classification: **production composition
gap** (P2-D); no weak fallback to development event ingestion was made.

### Safe implemented portion

Added `backend/ghar_sajag/durable_api.py::open_durable_event_api`. It requires a
file-backed database and an explicit Hub-authorizer callback, runs the existing
migrations with foreign keys and SQLite FULL synchronous writes, composes the
real `DurableEventCommit`, and maps `SQLiteEventMap` onto the existing caregiver
query path. It does not authenticate a network request itself. Production
deployment must supply trusted server-side middleware/context and an
owner/enrollment authorizer. The normal development `JsonApi()` entry point was
not changed and remains fail-closed for EventKey requests.

The P0 harness now submits the generated CloudSync request unchanged to this
file-backed API composition. A temporary loopback-only test authenticator uses
random per-run tokens and an internal trusted context, then binds exact fixture
Home, Hub, enrollment generation, physical device and logical Node. No token is
printed or persisted. Tests observed the real API's `201 COMMITTED` only after
the SQLite transaction; after backend reopen, exact retry returned `200` with
`duplicate: true`. The committed event was read through `SQLiteEventMap` and
rendered once in the actual Chromium caregiver timeline. Exact original event
and Hub receipt timestamps, type, location and payload were asserted.

Negative tests returned 403 for absent Hub context, wrong Home, stale fixture
generation and wrong physical/logical identity; 409 for same EventKey with a
conflicting payload; and 503 without a COMMITTED receipt when the backing
connection was closed. Existing `tests/python/test_durable_event_commit.py`
still verifies transaction rollback, conflict handling, duplicate effect
suppression and restart. The integrated P2-D bridge used the production C++ Hub
CloudSync serializer/HTTP receipt parser and real `JsonApi`/`DurableEventCommit`:
300/300 events committed and completed, 304 requests, 3 Hub/backend restart
boundaries, 3 duplicate responses, 4 injected response/framing/auth failures,
0 pending after catch-up, 7.6 seconds measured catch-up in that host fixture.
This is deterministic host timing, not a deployment or throughput claim.

### Focused results and remaining boundary

Latest `make validation-p0-e2e` report:
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/evidence/validation_framework/p0-e2e-1791733150540893734/report.json`;
stage log SHA-256
`b6177937e8dc376e6efc7330c9d1e05e8be727b8b38ef628db82b312b0fdff97`.
The report records 121.558 seconds total (120.964-second stage), 25 scenario
checks, stage subprocess exit 0, `source_unchanged=true`, and final gate
`software_status=FAIL` because the complete-product result remains PARTIAL.
The production-shaped request/PWA journey ran 25/25 scenario assertions and one
Chromium reload PASS. The P2-D bridge committed 300/300 events, persisted across
three restarts, and retained zero pending after catch-up. `make feature-coverage-test`
passed: 149 features, 201 source modules, 14 physical cases, plus 19 framework
integrity tests. Focused API/P2-D host tests passed. No firmware source changed,
so no target build or sanitizer was rerun. The independent historical
`hub-journal-migration-host-test` FAIL remains unchanged and was not rerun or
hidden.

The complete-product stage command exited 0 with valid test output but was
adjudicated FAIL because the P0 report remains `PARTIAL`; the outer
`make validation-p0-e2e` gate therefore fails. The scenario run passed; production
trust/deployment and complete product qualification did not.

Production completion remains blocked by the exact unimplemented trust boundary:
the Hub HTTPS source verifies the server CA/hostname and sends an injected
`Authorization` string, but no production credential provisioning/verification
adapter is connected to the backend. No approved source of Hub/Home/Node
enrollment-generation binding or revocation lifecycle is wired to the API.
The CloudSync request and strict Hub receipt schema carry no generation claim,
and the current SQLite event store is a host contract rather than the deployed
PostgreSQL/service persistence. Do not add bearer-token semantics, new request or
receipt fields, storage migration, or production identity policy by assumption.
The remaining GS-148 decision must specify the trusted Hub principal source,
Home/Node enrollment-generation lookup and revocation semantics, and the
production durable-store deployment adapter before live production acceptance.

Physical HIL=`NOT_RUN`; release=`NOT_APPROVED`; production trust and credential
qualification=`NOT_RUN`. P0 local scenario execution PASS is not full P0 product
completion or production deployment proof. The GS-130 blocker handoff remains
PARTIAL. Historical migration-failure evidence, 300-event prior P2-D evidence,
and all raw logs are preserved; no secrets or physical boards were accessed.

## GS-148 P2-D Hub trust contract and focused test checkpoint — 2026-10-11

This checkpoint continues only GS-148 P2-D from canonical source/origin HEAD
`18e542873ceec568f70a9358bae6845e39992a54`; origin matched before edits and
context preflight PASS (`2026-10-10.001`). The only source changes are focused
host-test/P0 scenario registration changes. Production firmware, backend trust
behavior, wire formats, storage formats and physical devices were not changed.

### Trust-boundary result

The existing Hub identity owner is the right local source: S3
`HubSecurityLink` maintains the Hub/Home values and persistent Node registry;
`ExpectedNode` pins MAC, Device ID, public key, installer proof and logical
assignment, and the local enrollment record has a generation. However, the
Home value is generated locally, the Hub identifier is MAC-derived, and there
is no approved backend registration authority binding that local identity to a
commercial Home. Target P256 signing is gated on protected PSA key provisioning,
Secure Boot and flash encryption; manufacturing/installer issuance, key-to-Home
registration, rotation and revocation are not implemented. GS-109's authorized
installer/service Add Device path is still not implemented and is not included
in this task.

The ESP32-S3 `HttpsBackendChannel` verifies the configured server CA and host,
refuses redirects and accepts an injected opaque `Authorization` value. It does
not issue or validate that credential. No target caller/composition invokes the
channel or `CloudSync::drive_batch`; production connectivity ownership is
therefore also absent. The API (`backend/ghar_sajag/http_api.py`, EventKey branch)
accepts only an internal `gs.verified_hub` request context and an injected
`authorize_hub` callback before invoking the durable transaction. That context
must come from trusted server middleware, never a client header. The existing
file-backed SQLite `durable_api` is a host composition, not a deployed service
database or a source for ownership claims.

The canonical CloudSync body carries its immutable EventKey, but not Hub identity
or Node enrollment generation. The current strict Hub parser accepts only the
existing exact COMMITTED response shape over server-authenticated TLS; it does
not verify a separate signed receipt binding Home, Hub, generation and payload
digest. Local revocation/tombstones exist in Hub commissioning state, but there
is no backend revocation registry. Treatment of a retained old-generation event
after revocation/replacement (reject it, allow a bounded drain, or another
authorized disposition) is not specified. Changing request fields, credential
scheme, backend owner registry, revocation policy or receipt format would create
a security contract, so none was invented.

### Decision boundary and recommendation (not an approved decision)

The smallest coherent proposed path is to reuse the existing protected Hub P256
identity: GS-109's authorized onboarding authority would register its public-key
fingerprint to a Home and current Hub installation; an authenticated request
would prove possession and bind the canonical request and freshness data; the
backend would atomically resolve the Hub/Home and current Node identity,
enrollment generation and revocation state before committing the exact
EventKey. A narrowly defined old-generation pending-event disposition and
replay/retry window must be approved. The API would commit durably before
returning the existing exact EventKey receipt. If that receipt must carry
independent cryptographic proof beyond the existing verified TLS channel, its
signing authority, key lifecycle and canonical fields also need approval.

Alternative: an issuer-managed short-lived device token can authenticate a Hub,
but requires an approved issuer, audience/subject/Home claims, secure token
storage, expiry, rotation, revocation and replay rules; it still does not solve
Node enrollment authorization. Mutual TLS could reuse a protected identity key
only after a certificate authority, certificate enrollment and revocation
lifecycle are specified. Neither alternative is currently implemented or
selected. These are proposals for the product/security owner, not permission to
implement them.

Before production integration can continue, approve/identify: (1) the authority
that registers and revokes a Hub principal against a Home and the production
credential/proof lifecycle; (2) the authoritative Node/Home enrollment
generation and revocation source, including retained-event disposition across
replacement; (3) whether authenticated TLS plus exact EventKey COMMITTED is the
receipt contract or a separately signed owner/generation/payload-bound receipt
is required; and (4) the deployable durable-store and trusted middleware
composition. GS-109 retains ownership of its full Add Device workflow; this
checkpoint asks only for the shared identity/authority contract it must expose.

### Focused tests and result

Added `P0-P2D-009`: the production `JsonApi` and durable commit path receive a
fixture authorizer's revoked-Node decision, return 403, and create no durable
commit. This proves the existing fail-closed authorization seam, not a
production revocation registry. The C++ Hub receipt-parser test now rejects
unrecognized Home/generation/signature fields instead of accepting an expanded
receipt. It does not claim to verify a signature. Both tests are permanently
registered in the P0 scenario document / GS-116 stage. Existing valid exact
EventKey and lost-response retry tests remain unchanged.

Evidence at source HEAD `18e542873ceec568f70a9358bae6845e39992a54` plus working
tree (P0 source fingerprint
`06487176039b60ddee4c368b72eea5b53c1616bfcd3987e285960c0ce94dd571`):

| Command | Result |
|---|---|
| `make p2d-cloud-contract-host-test` | PASS; 15 invalid receipt modes, pending bound 200, batch peak 16, retry peak 64; completion interruption cuts PASS (2 modes) |
| `PYTHONPATH=backend:. python3 -m unittest tests.python.test_durable_api tests.python.test_durable_event_commit tests.python.test_p2d_cloud_contract -v` | PASS; 9 tests; local fixture bridge 300/300 durable completions, 304 requests, 3 restarts, 3 duplicate responses, 4 injected failures, zero pending |
| `python3 tests/python/run_full_product_p0_e2e.py --event build/p0_product_event.json --cloud-request build/p0_cloud_sync_request.json --report /tmp/ghar_sajag_p0_revocation_report.json --scenarios=P0-P2D-009` | PASS; focused revoked-Node scenario 1/1 |
| `python3 tools/validation/check_p0_e2e_scenarios.py` | PASS; 17 use cases, 26 scenarios, 26 executable source mappings |
| `make p2d-https-channel-host-test` | PASS; 8 target-channel failure/framing modes; existing fake-IDF channel harness |
| `make validation-p0-e2e` | **FAIL (exit 2)**; 26/26 scenario assertions and 1 Chromium test PASS, but `product_status=PARTIAL` is adjudicated as failure. Outer report total 50.729 s; P0 stage 49.117 s. Physical=`NOT_RUN`. |

Full P0 report: `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/evidence/validation_framework/p0-e2e-1791734099302365499/report.json`;
P0 stage log SHA-256
`fa9de98a04042edec6e44ed7053b44289b70fd226d1c8747abba688d1e735b99`.
Source stayed unchanged during that run. The 26 executed scenario assertions
and one Chromium assertion do not establish production Hub authentication,
owner-generation enforcement, signed receipts, production database deployment,
active target CloudSync or live service connectivity. The known historical
`hub-journal-migration-host-test` failure remains a separate mandatory FAIL and
was not rerun or suppressed. No production defect was demonstrated in this
checkpoint; classification is `REQUIREMENT_GAP` for missing authority/receipt
contracts and `TEST_INFRA_ONLY` for the added fixture coverage.

P2-D remains PARTIAL/BLOCKED at the production trust contract. Physical HIL is
`NOT_RUN`; full product/release qualification is `NOT_APPROVED`. P2-E/P2-F,
production deletion/reclamation, GS-114 and hardware remain out of scope.

### GS-148 P2-D ownership provenance implementation checkpoint — 2026-10-11

Starting checkpoint for this implementation continuation was
`ac70f82431c51cc9f7d2975cbc0d04dda4aecb1a` (local and origin agreed before
editing; context preflight PASS). The approved GS-D032 lifecycle behavior is
implemented at the trusted policy seams, without defining or fabricating a
credential issuer:

- Added SQLite Hub identity/Home ownership and Node enrollment-generation
  records with unique permanent Hub identity/key fingerprint, single active
  Home binding, monotonically increasing installation epochs, ownership audit
  rows, monotonic Node generation replacement and explicit revocation.
- Claims, transfer initiation, revocation and enrollment require explicit
  verified-identity / authorized-operation capability inputs. No HTTP header,
  QR, MAC, or serial is promoted to a verified identity. This module does not
  authenticate caregivers, verify cryptographic proof, issue credentials, or
  expose a claim endpoint; its direct test proofs are test inputs at the
  trusted boundary, not production credential evidence.
- Cloud event policy executes inside the same SQLite `BEGIN IMMEDIATE`
  transaction as durable EventKey commit. It checks current Hub key/Home/epoch
  and the original Node generation. New events from a replaced/revoked
  generation fail closed. An exact already committed EventKey may retry under
  the unchanged active Hub/Home epoch only when stored Hub/epoch/generation
  provenance matches; immutable payload/provenance conflict checks remain in
  the durable committer.
- The S3 `CloudSync(HubJournal&, HubRuntime&)` path serializes a version-2
  request with the generation read from persistent authenticated owner
  evidence bound to that exact original event. The compatibility serializer
  remains version 1. Restart/retry reproduces the same request; missing owner
  evidence fails closed. No packet format or storage layout was changed.
- Transfer can enter `TRANSFER_PENDING` and advances the authorization epoch,
  immediately fencing old credentials in the registry. Completion is
  deliberately blocked while retained old-Home data disposition and safe
  local Hub rebind/reset are undecided. No pending event is erased, reassigned
  or exported.

This is a persistent policy/data-model implementation and host validation, not
commercial production trust closure. The production Hub credential verifier,
credential issuer/rotation/revocation authority, caregiver/installer
authorization middleware, trusted runtime composition of this registry, and
deployment database remain absent. The serializer is not currently called by
an active S3 CloudSync worker. Exact COMMITTED over server-verified TLS remains
the implemented response check; whether production additionally requires a
separately signed receipt is unapproved. The actual S3 P256 key provisioning
and protection state has not been proven as a cloud credential. New migration
9/10 schemas are host-tested only; no deployed database was migrated.

Focused implementation validation (source HEAD below plus dirty worktree):

| Command | Result |
|---|---|
| `PYTHONPATH=backend:. python3 -m unittest tests.python.test_hub_ownership_registry -v` | PASS, 5 tests: unique permanent identity/Home claim, durable exact retry/reopen, wrong owner/epoch/context rejection, generation replacement/revocation, transfer-pending retention/block. |
| `make hub-ownership-lifecycle-host-test` | PASS, 5 tests; GS-116 ownership lifecycle stage registered. |
| `make feature-coverage-test` | PASS, 19 traceability-integrity checks; 150 features, 204 source modules, 14 physical cases. Registration integrity is not semantic coverage. |
| `python3 tools/validation/check_p0_e2e_scenarios.py` | PASS, 17 use cases / 29 scenarios / 29 source mappings. |
| `make -j2 hub-runtime-checkpoint-host-test hub-backend-commit-host-test` | PASS after adding the source dependency and recovery checkpoint fixture needed by the new exact-generation/restart assertion. |
| `make validation-hub` | FAIL (exit 1, 403.934 s). 34/36 stages passed; `hub-journal-migration-host-test` fails at `clean migration commits` (test exit 2), and P0 product status is PARTIAL (26 assertions + 1 Chromium test executed). |
| `make validation-contract` | FAIL (exit 1, 264.616 s) at full-product P0 status (`PARTIAL`); affected contract, runtime, security, ownership and board-stack stages passed. P0 substage: 26/26 assertions plus 1 Chromium test. |
| `make VALIDATION_RECEIPTS='--reuse-report evidence/validation_framework/contract-1791739183540743883/report.json' validation-backend` | FAIL (exit 1, 147.696 s) at required P0 status; backend Python 439 tests completed (1 allowed skip), and API/frontend/component stages passed. P0 stage reran (receipt reuse does not cover it): 26 assertions + 1 Chromium test, product PARTIAL. |
| `make validation-p0-e2e` | FAIL (exit 2, 48.941 s outer / 48.027 s stage) by product completeness adjudication; current test-source fingerprint `0a95002fe20e828be847fce7441f9e6b784144f3b752a189b1eb367e06e81b77`; 26/26 scenario assertions and 1 Chromium test passed, overall status remains PARTIAL. |
| `python3 scripts/build_validation_targets.py` | PASS; clean isolated ESP-IDF 6.0.3 production-profile C3/S3 builds and packaging; C3 934,192 / 1,966,080 slot bytes, S3 1,868,880 / 4,194,304 OTA slot bytes. `GS_HIL_BUILD=OFF`; target compiled only. |

Reports for Hub, contract, backend and P0 stages are under
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/evidence/validation_framework/`
with run IDs `hub-1791738758385199801`,
`contract-1791739183540743883`, `backend-1791739481827670450`, and
`p0-e2e-1791739635817423714`. Their source HEAD is the starting commit plus the
implementation worktree; the Hub report fingerprint is
`750bbea4115ec3a823fc04dca045b478581eca69989c69303f00d470e6345ab9`. The
historical migration assertion remains an independent required FAIL, owned by
GS-148; this task did not change or suppress it. Physical HIL is `NOT_RUN`;
full release remains `NOT_APPROVED`.

Official clean target build report (ignored build evidence, retained locally):
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/build/validation_targets/gs116-k8zn86n2/report.json`.
Both images have build version `ac70f82-gs116-750bbea4`; source fingerprint is
`750bbea4115ec3a823fc04dca045b478581eca69989c69303f00d470e6345ab9`.

| Target image | Size | OTA slot | SHA-256 |
|---|---:|---:|---|
| C3 `gs_hw_m1_node.bin` | 934,192 bytes | 1,966,080 bytes | `1454bf77c6fa8d2c821c2e738811074bcfacfeb021e74d91b54aa1f4eefda40b` |
| S3 `gs_r1_s3_hub.bin` | 1,868,880 bytes | 4,194,304 bytes | `f9bb33ed8551a1f8829ac6fcb1196d6bf21b64e74b8edcc85c86079498d56ef8` |

Post-build focused rerun after adding a conflicting second-Home claim assertion:
`make hub-ownership-lifecycle-host-test` PASS, 5 tests. The final P0 E2E
rerun on the strengthened test source completed in 48.027 seconds: 26/26
scenario checks plus 1 Chromium test passed; outer command exits 2 because
`product_status=PARTIAL`. Report:
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/evidence/validation_framework/p0-e2e-1791741994656470626/report.json`;
log SHA-256 `5d76c069413467db432418793d1e6567e8e79f9359ad9509dc2d5e2ce1571de4`.
The earlier Hub/contract/backend aggregate reports carry fingerprint
`750bbea4…`, before that assertion-only change; current P0 carries the exact
updated fingerprint above. No firmware source changed after the target build.

Focused sanitizers also pass:
`ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 make -j2 hub-runtime-checkpoint-host-test hub-backend-commit-host-test CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'`
— exit 0; both changed Hub runtime/CloudSync-related host executables completed.

### Final backend Node-binding fence — 2026-10-11

Final source review found the backend could hold the same permanent physical
Node identity as ACTIVE under two separate Hub/Home rows. Existing device
identity architecture binds a Node to one Hub/Home at a time, so migration
`009` now adds a partial unique index on `physical_node_id WHERE state='ACTIVE'`.
Enrollment translates that exact active-identity collision into a fail-closed
ownership conflict; unrelated schema-integrity errors are not mislabeled.
This does not implement Node transfer or authorization. The old binding must
be explicitly revoked by the trusted commissioning owner before any new
binding; old-Home events are untouched.

Final focused evidence on source fingerprint
`6af24081bcc769bd73c61cfb498dfa27e6308e63dbb47931ef207ad7cbc49729`:

| Command | Result |
|---|---|
| `make hub-ownership-lifecycle-host-test` | PASS, 6/6 tests including concurrent cross-Hub/Home enrollment rejection; P0-P2D-010/011/012/013 markers emitted. |
| `make python-test` | PASS, 440 tests in 37.572 s, 1 allowed skip. |
| `make feature-coverage-test` | PASS, 19/19 framework/traceability tests; 150 features, 204 modules, 14 physical cases. |
| `python3 tools/validation/check_p0_e2e_scenarios.py` | PASS, 17 use cases / 30 registered scenarios / 30 executable source mappings. |
| `make validation-p0-e2e` | FAIL as complete-product gate (exit 2; outer 42.025 s, P0 stage 41.312 s): all 26 executed scenario assertions and one Chromium test PASS; adjudicator retains `product_status=PARTIAL`. Report `p0-e2e-1791742316138312319/report.json`, log SHA-256 `868be9666881d0b55b491bab1f83276e150286e1df3436d8753d783857fad611`. |

The preceding complete Hub/contract/backend aggregates were run before this
last backend-only index/test addition; their earlier source fingerprint and
reports remain identified above. The current full Python backend suite, new
ownership stage, framework traceability checks and P0 E2E were rerun after the
addition. No Hub/C3/S3 firmware source changed after the clean ESP-IDF target
builds, so the built image hashes remain valid for the firmware source. The
build report's aggregate suite fingerprint predates the final backend-only
change and is not represented as a fingerprint of this final complete
worktree. The historical Hub journal migration failure remains FAIL from the
mandatory Hub gate run. No physical operation occurred; release remains
`NOT_APPROVED`.

### Final P2-D lifecycle/provenance checkpoint — 2026-10-11

The final focused policy change makes Node enrollment generation monotonic
across the permanent physical Node identity, including a re-home to a different
Hub/Home. A Node identity cannot be active under two Hub/Home bindings at once.
After the old binding is explicitly revoked, a new binding must use a higher
generation; the old generation cannot create a new event. Only its exact,
already-committed EventKey may receive an idempotent retry under the same
active Hub ownership epoch and matching stored payload/provenance. Old-Home
event rows remain attached to the old Home. This is fail-closed backend policy;
it does not provide the commercial enrollment authority or an automatic
transfer path.

Latest focused evidence uses dirty-source fingerprint
`dc8e0f8bc91cfcaab9a600e9904e124e5cd64162843b15d29ca1eb9709e9e517` over base
HEAD `ac70f82431c51cc9f7d2975cbc0d04dda4aecb1a`:

| Command | Result |
|---|---|
| `make hub-ownership-lifecycle-host-test` | PASS, 6/6 tests; claims, transaction guard, durable retry/reopen, revocation, transfer pending, cross-Hub/Home exclusion and globally increasing re-home generation. Markers P0-P2D-010/011/012/013 emitted. |
| `make python-test` | PASS, 440 tests, one allowed skip. |
| `make feature-coverage-test` | PASS, 19/19 traceability/framework checks; 150 features, 204 modules, 14 physical cases. |
| `python3 code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/validation/check_p0_e2e_scenarios.py` | PASS, 17 use cases / 30 registered scenarios / 30 executable source mappings. |
| `make validation-p0-e2e` | **FAIL as product gate, exit 2.** The production-shaped scenario stage exited 0 and executed 26/26 assertions plus one Chromium test, all PASS; the report adjudicates `product_status=PARTIAL`, so the outer validation gate correctly fails. Outer duration 41.893 s, stage 41.290 s. Physical=`NOT_RUN`. |

Latest P0 report:
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/evidence/validation_framework/p0-e2e-1791742681161360468/report.json`;
stage log SHA-256
`be2272f3301e8047b7f97d592eacfb626d2daf0c9806010df1ff9af67c7738eb`.
The 30-case registry includes four ownership IDs; the four ownership behavior
markers are executed in the separate required `hub-ownership-lifecycle`
component stage. P0's 26 assertions plus its one actual Chromium test do not
prove production credential issuance, trusted claim middleware, an active S3
CloudSync worker, a deployed durable service, or physical behavior.

The current full backend Python suite and ownership component test were rerun
after the global generation/index change. The complete Hub, contract and
backend aggregate reports recorded earlier in this evidence remain valid for
their then-current fingerprints but were not rerun after that backend-only
change. The Hub aggregate remains a recorded FAIL due to the unchanged
historical `hub-journal-migration-host-test` assertion `clean migration
commits`; it was not skipped, weakened or rerun in this focused continuation.
Firmware source was unchanged after the recorded clean ESP-IDF 6.0.3 C3/S3
builds, though those reports do not fingerprint the final backend-only tree.

Still open under GS-109/GS-148: production device identity verifier and
credential issuer/key lifecycle; trusted caregiver/installer claim authority;
deployment composition that supplies trusted Hub/Home/epoch context; the
production source/allocation authority for globally monotonic Node generations;
receipt trust semantics; and disposition of old-Home pending journal records
before transfer can complete. Existing P256 local commissioning identity is
not claimed as a cloud credential. No live credentials/service, physical
board, real transfer, data deletion, full release gate, P2-E or P2-F was used.
Production trust=`BLOCKED`; P2-D=`PARTIAL`; P0 gate=`FAIL/PARTIAL`;
physical HIL=`NOT_RUN`; product release=`NOT_APPROVED`.
