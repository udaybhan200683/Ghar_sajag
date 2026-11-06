# GS-117 no-flash USB-to-Android E2E audit — 2026-11-06

## Decision and boundary

This is an offline source/evidence review and future execution-plan only. It
does not authorize USB/ADB/COM access, reset, receipt capture, bootstrap,
firmware installation, event injection, network-session activation, or a
physical test. No source or authorization record was changed.

**Physical execution: NO-GO under current authority and evidence.** The shortest
future route reuses the existing C3 HIL input and event pipeline after current
receipt, source-pin, and one-use authorization guards are legitimately
refreshed. It does not require a new firmware image if fresh evidence confirms
the same installed HIL-capable C3 and product S3 images.

Preflight passed at canonical branch/HEAD `feature/r1-commercial-baseline` /
`10119d3eeef2b8aa10fdfd668a5134593fdb6c43`; remote matched. Tracked files were
clean before this documentation update. The 79 pre-existing untracked entries
were preserved.

## Existing product proof and limits

GS-117#11929 and GS-179#11849 record session 126, sequence 1: the real C3
accepted `INJECT_MOTION`; the real S3 admitted the authenticated event and
CloudSync committed the same EventKey once to PostgreSQL; the caregiver API
returned one record; and that exact EventKey was observed in the installed
Android APK's Reports/Event Details view. This proves the existing vertical
path worked on that date. It is supplemental HIL-injected evidence, not optical
PIR activation and not a newly accepted TC-001 case. Session 127 separately
proved a successful authenticated rejoin with advancing C3 runtime/sensing
counters.

Session 134 later failed once during rejoin. It is not evidence of a persistent
defect: the exact radio send stage and S3 receive readiness were not recorded,
while the session-134 RCA retains same-image success in session 127. Firmware
has not changed since those observations. Current readiness still cannot be
inferred from that history.

## Existing no-flash path

The existing C3 target dispatches `INJECT_MOTION` to
`hil_inject_motion()` only in the TEST_ONLY runtime-control profile
(`GS_HIL_CONTROL=1`, `GS_HIL_BUILD=0`, `GS_BAT_C8_PHYSICAL_WAKE=0`). The source
path is `code/firmware/node/target/esp32c3/idf/main/hil_control.cpp` and the
runtime is `node_runtime_adapter.cpp`. This is the simulated sensor stimulus;
the subsequent radio, Hub, CloudSync, API and Android path is the real
implementation.

`gs117_tc001_serial_windows.py::run()` enumerates both exact C3/S3 USB identities
but opens only C3 COM4. Before injection it requires the expected HIL profile,
positive `runtime_live` and `sensing_live`, and zero pending/retained/in-flight
records. It sends one `INJECT_MOTION`, waits at most 35 seconds for the new
NodeRuntime session/sequence and matching authenticated class-0 Application
ACK, and never opens S3 UART. The ACK is the current path's evidence of
authenticated durable Hub admission. No separate S3 serial observation is
required for this event path.

`gs117_tc001_console.py::execute()` then checks a new EventKey against the
backend baseline, requires exactly one durable PostgreSQL row with the
expected Hub/Home/epoch/enrollment provenance, requires one caregiver API
record with the expected Bedroom/MOTION identity, and has the installed APK
display that same EventKey with the authenticated backend connected. It saves
bounded screenshot and accessibility evidence. Development input results are
not release-latency qualification.

The normal `/api/start` path is a five-run campaign and must not be used for
this one-event step. The existing one-run entry point is
`start_morning_routine()`: it calls the same one-event `execute()` path, then
also requires an already-applied Bedroom-only Morning Routine policy and
verifies its resulting Hub decision/API/Android presentation. Use it only if
that existing scenario's extra semantics and prerequisites are acceptable. If
the requested operation must be a generic motion-only one-run without those
Morning Routine checks, the current controller exposes no such one-run route;
do not run the five-run campaign as a substitute. That would require a separate
small offline controller/authorization review before any hardware approval.

There is also a fail-closed readiness-report mismatch in the five-run path:
`campaign_approval()` checks the DEV fixture identity but does not check that
`tc001_campaign` is in the manifest's allowed procedures; the subsequent
`development_session('tc001_campaign')` does check and rejects the current
bootstrap-only scope before hardware access. Thus a refreshed manifest could
make the UI report campaign approval PASS while execution correctly blocks.
This is not authorization and does not affect the separately approved one-run
Morning Routine validator; it should be corrected before the five-run button is
used, not by broadening the policy.

## Mandatory current gates and observed blockers

The source's exact fixture guard requires current C3/S3 installed-image
receipts no older than 24 hours, matching image hashes, target and USB identity,
source identity, active OTA slot, partition-table digest, and board capacity.
It also requires an installed Android receipt no older than 24 hours, bound to
package, signer, Home/backend origin, and ADB identity. The fixture additionally
requires the C3 HIL-control profile and full-product S3 profile. In the DEV
input-trial profile only, the stored authenticated-ingress receipt may be
unverified; the current trusted-network/8445 listener gate remains, and the
event itself must produce the authenticated durable ACK and backend evidence.

The owner-local C3/S3 receipt files currently match the expected application
hashes but were observed over 24 hours ago (about 146 hours at audit time); both
are **STALE**. The saved Android install receipt is also over 24 hours old.
`exact_fixture()` therefore fails before serial access. The current
`readback_receipt` authorization file is absent. The existing collector may be
used only after a distinct one-use grant; its reviewed fixed scope enters ROM
once per target, captures the allowed ranges, then issues one USB-aware EN
restore reset per target. It performs no flash write/erase and has no retry.

The current private DEV manifest is bound to GS-117#11897, lists only
`protected_gs40_bootstrap` (one session), and says motion injection is false.
Its source pins no longer validate: read-only `development_status()` returned
`development_reviewed_procedure_changed`. The one-run Morning Routine and
five-run campaign approval files are absent. The standing hardware authorization
read-only status is BLOCKED; Jira/session evidence records the existing
consumed/safety-latched state. The five-day GS-179
grant is still within its fixed time window, but its recorded
`hardware_operations_authorized` value is false. None of these may be reused to
authorize a new motion event or receipt capture.

The existing `exact_fixture()` guard does not require bootloader rollback proof.
GS-D029 makes automatic application rollback mandatory for firmware updates;
this proposed run makes no firmware change, so GS-D029 rollback qualification
is not a prerequisite to exercising the existing installed images. The fixed
receipt collector does also capture the S3 32-KiB bootloader region, but that
hash is evidence of bytes, not rollback provenance. The app/partition/selector
freshness and identity checks remain mandatory for the fixture.

## Reuse plan for one fresh event

After separately authorized work becomes available:

1. Use the existing one-use receipt collector only if the installed-image
   receipts remain stale. Recheck exact fixture, source/tool pins and
   authorization before reservation. Preserve its per-target ROM-entry and
   one-time application-restore-reset limits. Do not treat a bootloader hash as
   GS-D029 proof or install any image.
2. Through the existing source-review process, restore valid pins for the
   changed controller/authorization source; do not edit/reissue the historical
   manifest or ledger ad hoc. Refresh the owner-only Android install receipt
   with the existing observer as part of the separately authorized operation.
3. Before the one event, verify current exact USB descriptors, Home/enrollment,
   PostgreSQL/caregiver HTTPS, installed APK package/signer, and the current
   trusted ingress route. Reuse the prior GS-179 network qualification; do not
   repeat its broad tests. A listener alone is not proof of authenticated S3
   readiness.
4. Obtain a new, explicit, one-use owner scope independent of #11897 and #11886.
   Prefer the existing `start_morning_routine()` one-run route only if its
   Bedroom policy/decision checks are in scope. It checks C3 liveness before
   the single injection and the resulting authenticated ACK/backend/API/APK
   path. Do not activate or run this scope as part of this audit.
5. Stop after one result or the first failed stage. Preserve C3 output, original
   EventKey, ACK, backend row/duplicate counts, API projection, APK UI evidence,
   source/commit timestamps, chronology and cleanup. The current report also
   records source freshness and monitoring state, but explicitly does not
   qualify release latency. Do not retry or continue into the five-run campaign.
   A missing post-injection ACK is failure at the authenticated-admission
   boundary, not proof of a particular radio defect. A HIL-input pass remains
   distinct from optical PIR acceptance and from TC-001 case acceptance.

The current helper checks C3 runtime/sensing before injection and authenticates
durable admission through the post-event ACK; it does not prove a separate
pre-injection S3 rejoin. The one event itself is the shortest meaningful
rejoin/data-path observation. If a separate S3 rejoin observation is required,
it is an additional authorized operation with its own reset/open risks and
should not be silently bundled into this event run.

## Consolidated owner decision package — proposal only

The minimum future package contains separate, non-overlapping one-use scopes:

**A. Fresh installed-image receipt**, only if still required: exact Home
`gs177-test-product`; C3 `c3-146393c5d158`, COM4, USB
`14:63:93:C5:D1:58`; S3 `hub-e072a1d38d34`, COM10, USB
`E0:72:A1:D3:8D:34`. Pin the current collector, authorization module,
controller, serial helper and runtime dependencies. Allow only its seven fixed
read ranges (C3 partition table, both OTA selector copies and selected app;
S3 32-KiB bootloader region, partition table, both OTA selector copies and
selected app). Permit one ROM-loader connection and one application-restore
reset per target; one connection attempt; no retry. Prohibit writes, erase,
NVS, keys/credentials, eFuses, other flash, bootstrap, motion, network changes
and radio observation. Preserve partial private evidence and stop on the first
identity, tool, layout, selector, auth or restore mismatch.

**B. One USB-triggered event**, after A and every current readiness guard pass:
same C3/S3/Home fixture; one C3 COM4 `INJECT_MOTION` invocation through the
existing one-run procedure; accept documented incidental COM-open reset risk;
S3 USB identity enumeration only, no S3 UART. Allow no explicit reset,
bootstrap, retry, firmware operation, credential/enrollment change, database
mutation or second input. Verify one fresh EventKey from C3 through durable
class-0 ACK, exact one-row PostgreSQL commit, authenticated caregiver API and
that exact EventKey in the actual installed APK. Include Android ADB readiness
and bounded screenshot/UI evidence. Stop on any identity, authentication,
duplicate, chronology, latency or cleanup guard failure. Keep this separate
from the five real optical-PIR TC-001 cases.

The current GS-117#11897 latch and historical #11886 must remain unchanged.
The five-day network grant confers no hardware scope. No authority is requested
or activated in this report; an owner decision and existing audited
authorization activation are required before either operation.

## Artifact/source pins and validation

| Existing component | SHA-256 at reviewed HEAD |
|---|---|
| `gs117_tc001_console.py` | `d641e76ab241a04df4756783e2e836638a0614da90aa1fa5d20d560a8aa511e5` |
| `gs117_tc001_serial_windows.py` | `44a2669593ff367fcb9d0a59d4c2d289070906fbb0270b9f1f3929c183f5b8dd` |
| `gs117_tc001_backend.py` | `46e830bb3b8c4a5049f63235616a1d8ccbc84ff24e6a3c8840c75441630c4cce` |
| `gs117-tc001-backend.sh` | `222d845231ba4f5a70925de71594cf12ae8f23b4eb301f558e4476f28a4487b6` |
| `gs179-laptop-server.sh` | `687f5561e950a5e864dba267dc47901eadf72873871cf0cf4ece0c36307a73cf` |
| `gs117_tc001_readback.py` | `87373b43cbce3036c427fe90723b3edfddc269bbd3d92ca3b63f0f6a688ce312` |
| `gs117_hil_authorization.py` | `1afd803d34ff59a29aae6be8b8068d9bb09b8ed04bef2437e4a972cec883c70c` |
| C3 `hil_control.cpp` | `943d057a16ffe642763d623f6eb7f18173161d9135bef5bfe42037af10147130` |

Expected previously captured apps are C3
`589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7`
(`gs117-dev-rejoin-20261029`) and S3
`ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5`
(`8acab96-dirty`). These are historical expectations, not current receipts.
Android install/signing remains bound to its current owner-only receipt.

Checks performed for this review: canonical context preflight PASS; exact local
and remote HEAD matched; source/policy state checks were read-only; hashes above
were recomputed. No test suite was run because no source changed. No ADB,
serial, network readiness command, hardware, firmware, or authorization
operation was executed. The existing receipt and event-path test results remain
historical and are not repeated here.

Current state remains firmware unchanged; receipts STALE; session-134 cause
unproven; #11897 SAFETY_LATCHED 1/1; #11886 preserved; `TC001_READY=NO`; TC-001
0/5. The earliest executable blocker is stale C3 image receipt; the next
pre-event software-policy blocker is the invalidated DEV source pin. Independent
owner authorization for receipt and one event is also absent. The physical
event route is not authorized. Previously recorded Node/Hub/Contract aggregate
gate failures remain FAIL and unchanged; this development E2E review neither
requalified nor waived them.
