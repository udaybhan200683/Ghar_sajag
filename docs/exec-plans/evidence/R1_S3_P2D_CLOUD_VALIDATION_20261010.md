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
