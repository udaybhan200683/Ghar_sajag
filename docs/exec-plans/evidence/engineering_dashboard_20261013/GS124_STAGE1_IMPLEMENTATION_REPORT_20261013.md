# GS-122 / GS-124 / GS-125 Stage 1 implementation — 2026-10-13

## Authorized scope and recovery

Owning Jira: GS-122/124/125; permanent registration: GS-116/130.
The user's explicit Stage 1 authorization permits this existing isolated dashboard
worktree and branch despite the normal single-worktree policy. Source approval is
GS-122/10705; resume sources are GS-122/10727, GS-124/10725 and GS-125/10726.
Those comments and current GS-116/130 policies were read before implementation.

```text
BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=GS-122/10705; dashboard GS-DIAG-01/03; ED-D01/02/03-MIN
DECISION_IDS=NONE (no new LOCKED decision)
TASK_SCOPE=authorized software-only host service desk and caregiver consent
OUT_OF_SCOPE=production authentication/deployment; GS-148; firmware/HIL/OTA; release gate
```

Affected components: backend SQLite domain, diagnostic authorization/read
projection, GS-116 registration and GS-130 traceability. Shared interfaces are
the existing Home/Hub/Node ownership registry, an injected trusted actor/staff
authority, and the existing diagnostic read policy. Node/Hub firmware and the
caregiver PWA/HTTP composition are unchanged. This feature is SOFTWARE_ONLY.

At resume, local and actual GitHub remote HEAD both equalled
`a7b7470752a8470e73eb19806799989928556430` on
`feature/gs124-125-engineering-dashboard`. The pending source, tests, configuration,
migration and documentation were intact and were continued, not reconstructed.
No reset, clean, stash, rebase, merge or new worktree was used. Context preflight
PASS: local/canonical `2026-10-13.001`, including a repeat after source review.
The earlier interrupted implementation had 73 passing dashboard cases.

The canonical GS-148 worktree was inspected read-only. At the resumed snapshot
its HEAD was `93935e345a29e3b119f460fda5e9294477b6f798`; its tracked storage/runtime
edits and untracked historical/evidence/managed-component assets were preserved.
An independently running canonical `make validation-hub` process was observed
and was not interrupted. No file in that worktree was written by this task.

## Delivered behavior and modules

| Module | Implemented behavior |
|---|---|
| `code/backend/ghar_sajag/service_access.py` | Caregiver Home ticket; company admin queue; bounded pages/details; manual or atomic round-robin assignment; assigned-only technician Start; caregiver Approve/Deny/Revoke; close/unassign; minimal action audit; per-request consent checks |
| `code/backend/migrations/011_service_access.sql` | Host SQLite tickets, one live access request per ticket, persistent dispatch cursor and minimal audit; existing ownership tables reused |
| `code/config/service_access.json` | Strict versioned JSON contract with the approved 1800-second default; bounded integer validation |
| `code/backend/ghar_sajag/database.py` | Registers the four service tables in the existing host persistence convention |
| `code/backend/ghar_sajag/diagnostic_authorization.py` | Ticket-bound staff membership composed with the existing read-only grant policy |
| `code/backend/ghar_sajag/diagnostics.py` | Service Class A projection rejects unapproved device IDs and absent/stale Node enrollment generations; existing privacy and before-return authorization retained |
| `code/tests/engineering_dashboard/test_service_access.py` | 30 permanent production-domain host cases with explicitly injected identity/staff/technical fixtures |
| `code/tests/engineering_dashboard/test_registration.py`, `code/validation/suites.json` | Existing backend/fast/release stage preserved; new inputs registered; nonzero/zero/missing execution checks retained |
| `docs/validation/MASTER_TRACEABILITY.csv`, `SOURCE_FEATURE_INVENTORY.csv` | Two service features, source modules and GS125-SERVICE-S01..S30 registered under GS-116/130; production gaps and SOFTWARE_ONLY classification explicit |

`BEGIN IMMEDIATE` serializes assignment, approval, revoke, close and lazy expiry
with their audit writes. Time is read after the writer lock. Consent binds the
verified actor and staff role, ticket assignment version, Home, Hub, ownership
epoch and exact current physical/logical Node IDs plus enrollment generations.
The adapter returns the same principal checked with the consent transaction.
Expiry is non-sliding, and the persisted duration must match configuration.
Expiry needs a new Start and explicit caregiver approval. Revoke, reassignment,
offboarding, closure, company rebinding, Node re-enrollment and epoch change deny
subsequent requests. Write failure rolls back the cursor/request/audit together.

The diagnostic stage timeout was raised from 180 to 600 seconds because the
83-case exploratory disk-backed run took 231.714 seconds with synchronous SQLite
writes. This matches existing backend-stage bounds; assertions and mandatory
stage selection were preserved.

## Permanent cases and demonstrated outcomes

| IDs | Assertions |
|---|---|
| S01–S05 | Config validation; missing/forged principal; Home/company derivation; unassigned/role isolation; round-robin/no eligible staff |
| S06–S10 | Start grants nothing; one-time Home consent; Deny/new Start; exact expiry and restart/reapproval; revoke/reassign/unassign/close/offboard |
| S11–S15 | Current Node/epoch; wrong company and expired session; concurrent single approval; admin real-Home consent; existing diagnostic guard composition |
| S16–S19 | Concurrent dispatch cursor; concurrent close/approval; company rebinding; bounded role-scoped queue/details |
| S20–S24 | Same-device re-enrollment; role change; atomic principal snapshot; real SQLite lock-wait clock boundary; audit-write failure rollback |
| S25–S30 | Restart pending/revoked/cursor persistence; concurrent revoke/read; invalid persisted scope; absent HTTP routes with forged actor headers; consent-to-read E2E with privacy/device/generation/in-flight revoke checks; invalid extended persisted expiry |

This executes production domain/policy/projection code through deterministic
host simulation and a focused consent-to-read outcome. Fixtures establish no
credential verification, live technical provenance, PostgreSQL qualification or
commercial browser acceptance. The 48 original foundation methods are unchanged;
the six existing registry cases remain, preserving all 54 completed cases.

## Executed validation

The user requested a pause at 2026-10-13 12:29 UTC as the usage limit approached.
The backend gate had just completed, giving a validated source checkpoint.
PWA aggregate execution and the final completion handoff remain for resume.
Commands run from `code/`, with
`TMPDIR=$PWD/build/gs124_stage1_resume_tmp`; standalone dashboard discovery also
sets `PYTHONPATH=backend:.`.

| Command | Result |
|---|---|
| `python3 -m unittest discover -s tests/engineering_dashboard -p test_service_access.py -v` (exploratory) | PASS 27, exit 0, 128.891 s |
| `python3 -m unittest discover -s tests/engineering_dashboard -p test_*.py -v` (exploratory, before S30) | PASS 83 = 54 + 29, exit 0, 231.714 s |
| `make validation-framework-test` | PASS 39, exit 0 |
| `make feature-coverage-test` | PASS 157 features / 208 modules / 14 physical catalogue cases and 20 meta-tests, exit 0; mapping consistency only |
| `make validation-backend` | FAIL, make exit 2 / component runner exit 1; dashboard PASS 84 = 54 + 30, stage exit 0; Python FAIL 449 with one failure/one allowed historical skip; P0 FAIL exit 2 before scenarios |
| `make validation-pwa VALIDATION_REUSE_REPORTS=<final-backend-report>` | NOT_RUN: explicitly paused by user; remaining resume action |
| `git diff --check`, source/registration integrity and context preflight | PASS at review; repeated at delivery |

Exact backend receipt:
`code/evidence/validation_framework/backend-1791894195720046816/report.json`,
archived with all 15 stage logs [here](stage1_resume/backend/report.json).
It records source HEAD `a7b7470752a8470e73eb19806799989928556430`, fingerprint
`195c3a82e7ceaf075d9edc4f8b087bc69f0be6c508476babc7f2130522d97965`,
`source_unchanged=true`, tracked dirty, elapsed 303.170 seconds. Profile: Python
3.14.4, host compiler `d3c02c2eb999e2ce`, portable crypto sources
`ad5008d86e3a337d12bed44ce4e8d983db842db83ef0f245d6db69fb8b74bbd0`.
The final dashboard stage took 55.344 seconds. Changed source hashes are in
[source_sha256.json](stage1_resume/source_sha256.json).

| Backend stage | Status | Exit | Count |
|---|---|---:|---:|
| host-build | PASS | 0 | 1 build |
| backend-receipts | PASS | 0 | 1 assertion group |
| hub-ownership-lifecycle | PASS | 0 | 6 |
| health-config | PASS | 0 | 15 |
| contracts | PASS | 0 | 1 |
| lab-build | PASS | 0 | 1 build |
| python | FAIL | 1 | 449 tests; one failure, one allowed historical skip |
| functional | PASS | 0 | 92 |
| dummy-streams | PASS | 0 | 5 |
| http | PASS | 0 | 17 |
| bridge | PASS | 0 | 13 |
| api | PASS | 0 | 2 |
| frontend | PASS | 0 | 2 |
| p0-full-product-e2e | FAIL | 2 | 0 scenarios |
| diagnostic-foundation | PASS | 0 | 84 tests |

No Node/Hub firmware, shared runtime/durability contract or browser behavior was
changed. Unrelated Node/Hub aggregates, board simulation, target/sanitizer builds,
full browser release validation and full release gate were not invoked. The
registered backend/PWA gates include their existing shared contracts and P0
stage. Physical HIL, flashing, OTA and production activation are NOT_RUN.

## Existing broader failures and temporary storage diagnosis

```text
BUG_CLASSIFICATION=INVESTIGATE_ONLY
REQUIREMENT_SOURCE=existing CloudSync/P0 registered durability assertions
DECISION_IDS=GS-D029; GS-D033 (unchanged)
TASK_SCOPE=read-only diagnosis and host test observations
OUT_OF_SCOPE=GS-148 or firmware fixes; unrelated /tmp cleanup; gate weakening
```

`/tmp` is a 1.9 GiB tmpfs with zero available blocks, while inode usage is only
3%. The largest existing directories were two GS-152 clean checkouts (~1004 MiB
and ~775 MiB), GS-148 architecture evidence (~97 MiB), and a GS-144 workload
(~58 MiB). None was deleted. The main filesystem has ample space, so the new
scratch directory is under ignored `code/build/gs124_stage1_resume_tmp`.

A uniquely owned one-byte `/tmp` write failed with errno 28 (`ENOSPC`), recorded
in [tmp_capacity_probe.log](stage1_resume/tmp_capacity_probe.log). A diagnostic
libc observation library, whose source is retained in
[temporary_write_probe.c](stage1_resume/temporary_write_probe.c), observed:

| Original fixture | Observation (exit 1 for both) |
|---|---|
| `p2d_cloud_contract_validation --bridge` | `fclose errno=28`, followed by the original `FAIL bridge durable-before-ACK` |
| `p0_board_stack_e2e_validation --emit-p0-event ...` | `write errno=28`, followed by the original `FAIL initial file-backed Node recovery` |

See [CloudSync probe](stage1_resume/cloudsync_write_probe.log) and
[P0 probe](stage1_resume/p0_write_probe.log). Both fixtures hard-code `/tmp` and
ignore Python's `TMPDIR`. The probes observe errors without redirecting files,
changing assertions or modifying firmware. They identify an environmental write
failure at these failing boundaries; they do not prove the complete product
would pass with more space. The official uninstrumented gate failures remain
FAIL. No physical or production durability is inferred.

To reproduce observation from repository root:

```bash
mkdir -p code/build/gs124_stage1_resume_tmp
TMPDIR="$PWD/code/build/gs124_stage1_resume_tmp" cc -shared -fPIC \
  docs/exec-plans/evidence/engineering_dashboard_20261013/stage1_resume/temporary_write_probe.c \
  -ldl -o code/build/gs124_stage1_resume_tmp/temporary_write_probe.so
LD_PRELOAD="$PWD/code/build/gs124_stage1_resume_tmp/temporary_write_probe.so" \
  code/build/p2d_cloud_contract_validation --bridge < /dev/null
LD_PRELOAD="$PWD/code/build/gs124_stage1_resume_tmp/temporary_write_probe.so" \
  code/build/p0_board_stack_e2e_validation --emit-p0-event \
  code/build/gs124_stage1_resume_tmp/probe_event.json \
  code/build/gs124_stage1_resume_tmp/probe_request.json
```

The first probe compilation without `TMPDIR` also failed closing its compiler
temporary assembly file with ENOSPC; rebuilding with the owned scratch directory
passed. No probe environment is used for the official component gates.

Ignored `code/build/append_service_trace.py` and `fix_service_mapping.py` were
reviewed and preserved. They are historical, one-time append/repair helpers and
are not idempotent generators. They were not run on resume. Registration and
validation use the tracked CSV/JSON/source files directly and do not depend on
these ignored scripts.

## Remaining production blockers and next action

See the [Stage 1 interface boundary](../../../architecture/GS124_STAGE1_SERVICE_ACCESS_BOUNDARY_20261013.md).
GS-76/143 must provide the real verified issuer/session and current staff/Home
authority with a transaction-consistent offboarding/version fence. The backend
owner must review the actual production database for a PostgreSQL adapter and
migration, recovery/concurrency/idempotency compatibility and retention policy.
The PWA owner must compose verified sessions, CSRF, verified staff names, role
views, expiry/revoke/cache behavior and browser tests. GS-65/109 must qualify the
technical source and current event/Node resolver. Class B is disabled.

Production service/diagnostic routes remain absent. No `X-Actor-Id` bypass,
production principal/grant issuer, second device registry, persistent diagnostic
event pipeline or service-email OTP is added. Stage 1 does not wait for Stage 2
deployment infrastructure; GS-122/124/125 remain partial and are not moved to Done.

The pause checkpoint commits/pushes validated source and this evidence; it is
not a declaration that the complete Stage 1 task or aggregate gates passed.
Delivery SHA, remote equality and owning Jira comment IDs are recorded in the
pause delivery receipt/Jira handoff. The exact next step is startup status and
preflight, then the PWA aggregate with the native backend receipt above (only
same-source/profile PASS prerequisites are reusable). If receipt validation
rejects the current source/profile, rerun the affected stages normally. Preserve
both existing failures and all ignored evidence/helper files. Finish review,
source integrity, final commit/push equality and GS-122/124/125 completion comments
after remaining validation. No Stage 2 infrastructure is needed to finish that
bounded work.
