
# Master automated validation and regression framework

## GS-40 mock/replay qualification runner — 2026-10-16

The versioned case registry is `code/tools/hil/gs40_cases.json`; it registers
GS40-TC01 through GS40-TC07 and links TC01–TC06 to six separate physical cases
in both physical catalogues. Run `make gs40-qualification-test` from `code/` to
exercise the runner, mock acceptance contracts, immutable report writer,
Jira-11158 replay fixture, observer fault classifier and no-device live-mode
gate. `python3 tools/hil/gs40_qualification.py` defaults to `mock`, which uses
deterministic input only and creates unique per-case JSON and Markdown output
under `docs/hw/evidence/GS40_AUTOMATED_QUALIFICATION_20261016/runs/`.

Use `--mode replay --case GS40-TC07 --capture <existing-jsonl>` to analyze a
preserved capture. Replay is read-only and reports `HOST_PASS` only when the
capture is parsed as expected; it retains the source checksum and historical
timestamp/provenance. Use `--mode live` only after a separately approved,
verified, non-resetting telemetry provider exists. The current implementation
does not enumerate USB, import/open serial, send network requests, or operate a
board in live mode; it writes `BLOCKED` reports until that source is registered.
Every report has a separate physical status. Mock/replay `HOST_PASS` never
becomes `PHYSICAL_PASS`, and no real-target acceptance is implied by this
runner.

The C3 USB Serial/JTAG endpoint can disappear while the device remains USB
connected: ESP-IDF light sleep gates the USB clocks, and existing C3 records
show the native endpoint unavailable while authenticated Hub telemetry
continued. Jira comments 11164–11165 preserve GS-114 C8-P1/P2 physical PASS on
their recorded image pair: post-wake authenticated NodeHealth and a real
authenticated AM312 event continued over ESP-NOW while native USB observation
was unavailable. Those image-scoped results are not GS-40 cadence/offline/PWA
acceptance and are not repeated here. This is observer loss, not evidence that
the Node is offline. The
single historical S3 receive-only capture is pinned by SHA-256 and stops at
`rst:0x1 (POWERON)`. pySerial 3.5 opens the POSIX descriptor before applying
requested DTR/RTS-low states (`TIOCMBIC`); a CH343/board reset path or driver
line transition is therefore plausible. The capture does not show which cause
occurred, and post-capture USB/IP remained attached. Its bytes stop before Hub
application startup, so they contain no current GS-40 image/config/session or
authenticated NodeHealth evidence. Hub NodeHealth is presently available in
target logs; Hub CloudSync sends durable events and no verified read-only live
Hub-to-backend health observation path is established.

Existing production host assertions remain the behavior authority:
`make gs40-host-test`, `make gs40-config-test`, and the registered
Node/Hub/contract/backend/PWA component suites. The new case runner checks
observation contracts and provenance rather than recreating firmware cadence,
authentication, event durability, lease, or PWA product algorithms. The six
physical rows remain `BLOCKED`/`NOT_RUN`; TC05 additionally needs a second valid
Node or approved qualified fixture.

Execution on 2026-10-16 is recorded in
[`GS40_AUTOMATED_QUALIFICATION_20261016.md`](../exec-plans/evidence/GS40_AUTOMATED_QUALIFICATION_20261016.md)
and the per-case JSON/Markdown run artifacts. Mock passed 7/7 host cases (26
assertions); the historical Jira 11158 replay passed 6/6 host checks; live mode
blocked all seven cases without device access. The tooling aggregate and
46-test framework suite passed. Affected Node, Hub, contract, backend and PWA
gates retain the known Hub migration and GS-148 P0 `product_status=PARTIAL`
failures; the PWA browser suite passed 86 checks. No physical acceptance or
release approval is inferred from these results.

## GS-130 bounded risk-regression integration — 2026-10-14

The [focused report](../exec-plans/evidence/GS130_RISK_REGRESSION_20261014.md)
records six audited missing scenarios and the reproduced backend cached-health
defect. `BOARD-TC-130-010`, `HUB-TC-130-006`, `GS130-HEALTH-001/002`,
`GS130-DURABLE-001` and `GS130-CONFIG-001` execute in the existing board,
feature-boundary, health-config and Python stages. Mandatory success markers
reject omission or failure of these cases. No extra simulator or stage is added.
The board stage now requires ten case markers, and traceability maps 182 rows /
205 modules / 15 existing physical definitions. These are accounting counts,
not a claim of 182 commercial features or complete product qualification.

The only production correction is the Foundation received-contact consumer;
Node/Hub firmware, wire formats, EventKey/ACK semantics and target images are
unchanged. Component/contract/backend/PWA outcomes and preserved mandatory
migration/P0 failures are in the report. Physical C8 evidence remains reused;
P3 provenance, P9 fixtures and separate GS-149 P10 stay open. Full release is
deferred; next separate task is GS-148 P4/P5-B1 under comments 10810/10933.

## GS-114 C8 coverage reconciliation — 2026-10-14

The GS-116/GS-130 C8 audit maps P1–P10 to production sources, automated test
IDs, executable targets, local gates, release membership and the latest actual
result in the [dated coverage audit](../exec-plans/evidence/GS116_GS130_C8_COVERAGE_AUDIT_20261014.md).
The 78-stage registry selects 68 fast stages and all 78 for release; the Node,
Hub and contract component selectors contain 24, 41 and 34 stages respectively.
Physical runners remain opt-in and outside software gates.

The board-stack E2E suite has nine required case markers. `BOARD-TC-130-009`
explicitly covers an event-free baseline, Hub restart, fresh authenticated link
session, first qualified PIR event, one durable effect and authenticated
retirement. This closes the automated first-event-after-reboot scenario gap
without changing product code. Its physical counterpart remains the separately
evidenced C8-P7 case.

The physical catalogue now recognizes the latest C8 P1/P2/P4/P5/P6/P7/P8 PASS
reports; P3 measured behavior PASS is catalogued PARTIAL because its running S3
image hash is unavailable; P9 ACK/FOTA remain BLOCKED; P10 remains under
GS-149. The GS-114 aggregate is PARTIAL. The Hub journal migration assertion
failure and P0 `product_status=PARTIAL` remain independent release blockers.
Neither `validation-fast` nor `release-gate-final` was run for this scoped audit.

## GS-148 / GS-145 first-event software registration — 2026-10-13

[Approved design](../architecture/GS148_FIRST_EVENT_RECOVERY_DESIGN_20261013.md)
E1/E2 is implemented in the existing v1 readers and registered as scoped
GS148-ARCH assertions. `storage-correctness` and its ASan/UBSan twin require
every native-owner fault, negative, capacity, report, privacy and repeated-prefix
marker. `first-event-reader-compatibility` compiles the actual old reader and
corrected reader against identical hashed v1 states, including mandatory output
for the old reader's known first-event availability limitation.
`first-event-recovery-projection` exercises the production C3 retained-event,
Hub ACK/reboot, CloudSync serializer and real local API/caregiver projection.
The stage registry, failure-propagation meta tests and source/physical traceability
are checked by the existing GS-116/130 tools. Standalone missing-head and
populated/corrupt-authority negatives remain mandatory. The
[dated evidence](../exec-plans/evidence/R1_GS148_OPTION_A_20261013.md)
records frozen source, actual receipts and remaining aggregate FAILs. Physical
and full release qualification remain NOT_RUN.

## GS-148 bounded correctness registration — 2026-10-12

`storage-correctness` and `storage-correctness-sanitizers` are permanent Hub and
contract stages. Required markers prove execution of refusal/reducer boundaries,
prepared exact-context retries, checkpoint/report cuts, all-root pinning and
conflicting authority checks; incomplete/filtered execution fails adjudication.
New scoped GS148-ARCH rows are in MASTER_TRACEABILITY and reciprocal source
inventory. PHY-GS148 retains current-image cuts/allocator qualification NOT_RUN.
The first-admission compatibility blocker is explicitly tested as fail closed,
not labeled implemented recovery PASS. The historical 72-case architecture
matrix remains proposed; focused assertions do not exhaust that specification.
Use the [dated evidence](../exec-plans/evidence/R1_GS148_P0_P1_P2_20261012.md) for
actual execution and failures. Historical migration FAIL and product P0 PARTIAL
remain mandatory visible results; this package does not run the full release gate.

## Active source root and GS-152 layout

The active product source root is `code/`; the repository root Makefile delegates
to that directory. Stable ownership is grouped under `code/firmware/node/`,
`code/firmware/hub/`, `code/firmware/common/`, `code/backend/`,
`code/frontend/`, `code/tests/`, `code/validation/` and `code/tools/`. ESP-IDF
target project roots remain under `code/firmware/*/target/`; physical suites
remain opt-in. The old version-stamped active source wrapper is not a supported
build root. See [GS-152 layout and migration rationale](../architecture/GS152_STABLE_REPOSITORY_LAYOUT.md).

## Physical HIL inventory and release evidence — 2026-10-11

`PHYSICAL_HIL_CATALOGUE.csv` is the case-level physical checklist linked to
`MASTER_TRACEABILITY.csv`; `PHYSICAL_QUALIFICATION.csv` retains the owner-level
qualification campaigns and their Jira ownership. The traceability matrix now
classifies implemented rows as `PHYSICAL_REQUIRED`, `PHYSICAL_CONDITIONAL` or
`SOFTWARE_ONLY` (non-implemented/deferred/on-hold rows retain their implementation
classification). The lightweight `make physical-hil-catalogue-test` checks IDs,
evidence paths and every required/conditional feature mapping without accessing
devices. The same checker runs under hardware-independent `hil-tooling-test`.
The catalogue has 99 entries: 71 individually listed historical classic-target
test IDs, 27 current/owner physical cases and one legacy suite summary.

The GS-116 registry includes `physical-hil-release-evidence` as a release-only
stage. It requires every `RELEASE_BLOCKING=YES` catalogue case to have actual
PASS, exact source SHA, image SHA-256 and an evidence file. It never runs physical
tests. `make release-gate-final` will therefore remain blocked while required
physical cases are PARTIAL, NOT_RUN, BLOCKED or historical-only. This check is
not proof of physical qualification by itself; review image/fixture compatibility
and evidence before release approval. At the time of this 2026-10-11 inventory
snapshot, GS-114 Part 1 HIL-A02/A03/A06 were bounded physical PASS, HIL-A01 was
PARTIAL, A07 was timer-only PARTIAL, A04/A05 were NOT_RUN and A08 was BLOCKED;
BAT-C8 C8-P1..P9 were then NOT_RUN. The newer 2026-10-14 case reconciliation
above supersedes those C8 catalogue dispositions without deleting the dated
historical snapshot.
GS-148 migration remains a mandatory software failure and is separate from this
physical checklist.

Reuse the HW-M1.4 `tools/hil/phase1.py` supervisor and existing test IDs; do not
invoke the connected classic-ESP32 `hil-smoke`/`hil-regression` against the S3
fixture. They probe/reset boards, can build/flash and use `INJECT_MOTION`. The
S3 commissioning-only adapter used for the dedicated fixture is not a general
HIL control API; it uses the existing secure commissioning owner. Current
observation evidence is recorded in
[`GS114_PART1_CLEAN_FIXTURE_20261011.md`](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md).
No physical tests were run for this catalogue integration task.

At the time of the original catalogue audit there was no S3-compatible
unattended board-HIL runner or safe operator-prompting motion runner. GS-130 has
since added `make validation-board-hil` and `make validation-motion-hil`; see
the dated P0 E2E/HIL evidence below. Their default invocation writes a
machine-readable NOT_RUN report without opening a port. The automated runner
uses exact fixture by-id paths, read-only udev USB-serial matching and supplied
image SHA-256 checks; current firmware does not expose a verifiable running-image
hash/config fingerprint, so HIL-A01 cannot pass from this harness. The motion
runner requires operator-confirmed genuine AM312 movement and rejects
`INJECT_MOTION`. Neither runner was used on a board for this software task.
`make hil-regression` remains the historical destructive classic-target command.
GS-114 owns BAT-C8 P1–P9; GS-108 owns later broad stable-head HIL. Both remain
opt-in and separately authorized. Registration, command availability, simulation
and historical PASS are distinct from executed current-image physical PASS.

For every new feature, use three executed software layers as applicable:
production unit/component tests, deterministic production-code simulation, and
focused end-to-end trigger-to-outcome verification across affected components.
Add/update permanent feature and physical traceability in the same change. Pure
software behavior stays software-only; physical-dependent acceptance receives a
catalogue test and retains NOT_RUN until actually qualified.

## Current canonical execution guide — GS-116, 2026-10-10

Approved GS-116/130 engineering policies (comments10364/10365) are enforced by
repository AGENTS.md. Use only the canonical R1 worktree/branch. Historical
alternate-worktree instructions below are superseded.

### GS-130 feature coverage and separate board stack — 2026-10-11

Two independent assessments are required (GS-130 comment10409): **A**, feature
regression/category coverage; **B**, portable C3/S3 production application E2E.
Neither test registration nor the board simulation establishes exhaustive feature
coverage. The authoritative files are:

- [Feature/test matrix](MASTER_TRACEABILITY.csv): stable feature IDs, requirements,
  implementation status, actual assertion anchors, commands, category scope,
  registration, execution provenance and explicit gaps.
- [Owned source inventory](SOURCE_FEATURE_INVENTORY.csv): reciprocal feature links
  for production and reference modules. Accounting for a file does not prove all
  its branches or hidden feature semantics were tested.
- [Physical qualification catalogue](PHYSICAL_QUALIFICATION.csv): existing Jira
  owners, preconditions, procedures, failure criteria, required logs/image hashes.
- [Case-level physical HIL catalogue](PHYSICAL_HIL_CATALOGUE.csv): permanent test
  IDs, current/historical fixture compatibility, execution class and actual result.
- [GS-130 evidence and resume](../exec-plans/evidence/R1_GS130_FEATURE_COVERAGE_20261011.md):
  executed results and unresolved semantic/application/target limitations.

`make feature-coverage-test` verifies matrix/registry/source consistency and its
negative self-tests. `make validation-board-e2e` uses the **same** GS-116 registry
and receipt executor. The board stage also belongs to Node, Hub, contract, fast
and release metadata. It compiles the real sensing/runtime/power/rejoin/AEAD,
encrypted Node recovery, S3 outbox/journal/reducer and FOTA policies; adapters
replace clocks, GPIO, ESP-NOW delivery, byte storage and OTA writer. It does not
execute ESP-IDF task startup/interrupts, flash electrical barriers, RF, bootloader
or production cloud credentials. Inspect those boundaries and physical cases
before claiming target acceptance. New tests must exercise production code and
meaningful assertions; no independent protocol/policy replica is acceptable.

### GS-130 P0 full-product E2E — 2026-10-11

`docs/validation/P0_E2E_SCENARIOS.json` maps the canonical 17 P0 use-case groups
to stable scenario IDs, requirements, traceability feature IDs, production
sources and executable test sources. `make p0-product-e2e` runs the focused
end-to-end chain: production C3/S3 host runtime with virtual GPIO/time/ESP-NOW
and file-backed storage → production Hub journal/outbox/CloudSync request → the
real local JsonApi/service → the shipped static PWA in Chromium. This is distinct
from the current nine-group board-stack suite (latest check count is in the dated
C8 coverage audit). `make validation-p0-e2e`
uses the single GS-116 registry and requires every scenario marker. A passing
scenario harness with `product_status=PARTIAL` is deliberately adjudicated as a
failed complete-product stage. It must not be reported as full P0 completion.

For focused local iteration, `make p0-product-e2e
P0_SCENARIOS=P0-E2E-002,P0-E2E-017` selects scenario assertions; Chromium runs only
when P0-E2E-017 is selected. Fixture preparation still exercises the isolated
real service flow. Unknown, duplicate and empty selections fail. The registered
complete stage sets `P0_SCENARIOS=` explicitly, so developer filters cannot
reduce mandatory coverage in `validation-p0-e2e`, fast or release composition.

The CloudSync request generated by the production C3/S3 host stack now reaches
the existing `DurableEventCommit` transaction through
`backend/ghar_sajag/durable_api.py`, a file-backed SQLite composition. Its
`SQLiteEventMap` exposes the committed exact EventKey to the existing caregiver
query projection and Chromium timeline. The P0 runner also executes the real
Hub HTTP receipt parser/CloudSync bridge against the real API transaction for
300 events, including lost replies, retries, duplicate suppression and three
backend/Hub restart boundaries. Focused negatives cover absent trusted Hub
context, wrong Home, stale fixture generation, wrong physical/logical Node,
conflicting payload and closed storage. Original occurrence/Hub timestamps and
event payload are checked.

The test middleware uses random per-run loopback fixture tokens and injects an
internal trusted context; it does not implement or prove production Hub
credential verification, enrollment-generation storage/revocation, caregiver
OIDC, PostgreSQL deployment, or the production event/alert query service. The
P2-D revocation scenario invokes this existing authorizer seam with fixture
revocation state; it is not evidence of a production registry. The Hub parser
test rejects unknown Home/generation/signature response fields, but does not
verify a cryptographic receipt signature. The
normal `JsonApi()` entry point remains the documented development adapter and
continues to fail closed for EventKey requests without configured durable store
and trusted authorizer. No fake COMMITTED response is used. The P0 report remains
`PARTIAL`, so `make validation-p0-e2e` correctly returns nonzero. The local
service's other simulated event/configuration state remains in-memory; no
autonomous production inactivity scheduler or resume-within-window suppression
is claimed. Remaining use-case gaps stay in the machine-readable registry.

The new P0 stage is owned by Node/Hub/contract/backend/PWA and joins the existing
fast and release metadata. It is a focused development target; do not run the
entire release gate merely to execute it. Full product release remains a separate
candidate gate and physical qualification remains separate.

Latest execution: 26/26 scenario assertions and one focused Chromium test passed;
the P2-D bridge committed 300/300 events, persisted across three restarts, and
retained zero pending after catch-up. The complete-product stage command exited
0 with valid test output but was adjudicated FAIL because `product_status=PARTIAL`;
`make validation-p0-e2e` therefore exits nonzero. Scenario execution passed;
production trust/deployment and complete product qualification did not. This
remains the required gate result until GS-148 supplies and deploys trusted Hub,
enrollment and durable-backend composition. The 2026-10-11 report is
`code/evidence/validation_framework/p0-e2e-1791734099302365499/report.json`
(source fingerprint `06487176039b60ddee4c368b72eea5b53c1616bfcd3987e285960c0ce94dd571`);
the stage took 49.117 seconds and the outer command took 50.729 seconds. The
new P0-P2D-009 assertion proves only rejection through a fixture-supplied
revocation decision before SQLite commit. Production Hub principal issuance,
Home ownership, enrollment-generation/revocation authority, receipt binding and
deployed store remain unresolved under GS-148. The separate historical Hub
journal migration failure remains a mandatory FAIL.
The board runner integrity target has 15 hardware-free checks. Automated and
manual HIL commands are opt-in and were NOT_RUN on hardware. Exact counts,
registered report/log path, source fingerprint, limitations and inventory
reconciliation are in
[`R1_GS130_P0_E2E_HIL_20261011.md`](../exec-plans/evidence/R1_GS130_P0_E2E_HIL_20261011.md).

The portable factory-reset stage now reproducibly builds installed TF-PSA Crypto
and executes production PSA/reset code plus the actual IDF null-pointer guard.
Compatibility headers expose upstream declarations only. Missing dependencies
fail visibly. External crypto/guard content participates in receipt provenance;
cached PASS cannot survive source changes. The distinct board stage requires all
nine case markers: selecting one passing case cannot satisfy the complete gate.

### Physical Track C inventory — GS-130 comments10411/10413

Comment10413 supersedes greenfield HIL creation: reuse the canonical
`tools/hil/phase1.py` Campaign/SerialCapture/FixtureLock/Results supervisor,
`usb_attach.py`, `identity_probe.py`, `runner.py`/`core.py`, signed-FOTA tooling
and existing physical case/evidence records. These files are already in this
branch, not available only in historical worktrees. GS-108 owns broad stable-HEAD
HIL; GS-114 owns BAT-C8 P1–P9. The GS-130 evidence inventories actual commands,
case families, provenance and unsafe defaults.

C1 board-automated and C2 genuine manual AM312 motion remain NOT_RUN: no fixture
authorization. `Campaign.motion()` sends `INJECT_MOTION`; it cannot prove optical
PIR. `hil-smoke`/regression invoke paired build and flash, and signed-FOTA tooling
includes resets/erase/flash; do not invoke them under a non-destructive scope.
Reuse the supervisor later with an explicitly authorized current-S3 fixture,
safe observation mode and genuine operator motion steps. Historical classic-ESP32
images/60s health evidence are not GS-40/150 qualification. Physical campaigns
never run implicitly in Node/Hub/contract/fast/release software gates.

### Development versus release acceptance — GS-116 comment10405

Development runs new and all prior affected Node/Hub regressions, affected shared
contracts, framework integrity tests and relevant builds/sanitizers. Application
suites run when their contracts change. Do not launch global validation-fast,
release-gate-final or full browsers unconditionally for firmware/framework work.
Verify release composition with deterministic registration and injected-failure
self-tests; this proves wiring, not release acceptance. Full product gate execution
is NOT_RUN/deferred until a genuine release candidate or explicit request. A release
candidate must execute the complete gates, including backend and browsers.

### Component ownership

The single maintained executable registry is
[suites.json](../../code/validation/suites.json).
From repository root:

| Command | Ownership and regression coverage |
|---|---|
| `make validation-node` | C3: sensing/runtime/event identity, battery/PowerPolicy/BAT-C8, GS-150/40, encrypted pending/recovery/retirement, security/rejoin and FOTA |
| `make validation-hub` | S3: authenticated ingest/registry/journal/ACK/dedupe/reboot, liveness, storage/checkpoint/reclamation and implemented CloudSync/HTTP/HTTPS contracts |
| `make validation-contract` | Node↔Hub/backend: authenticated ACK versus MAC, exact keys/replay, outage/rejoin/session/persistence, mixed health policy, FOTA and receipt parsing |
| `make validation-board-e2e` | Separate portable C3+S3 production application stack, nine scenario groups; hardware boundaries simulated, physical NOT_RUN |
| `make feature-coverage-test` | Matrix/source/registry integrity and controlled missing-mapping/physical-claim failures; semantic coverage remains an engineering assessment |
| `make validation-backend` | Python discovery, configuration, API/HTTP/functional/bridge/frontend contracts |
| `make validation-pwa` | JavaScript and backend-derived coverage/chronology/notification scenarios; browser separately when rendering is affected |
| `make validation-tooling` | Framework self-tests, master negative injection, coverage registration and existing hardware-independent HIL tooling |
| `make validation-android` | Explicit GS-177 JDK/Gradle/Android SDK build, HTTPS-origin unit tests, signed debug APK and SHA-256; excluded from generic fast/release suites |
| `make validation-caregiver-app` | GS-177 Android stage plus isolated call-signaling/provider prototype tests and JS/XML checks; excluded from generic fast/release suites |
| `make validation-fast` | Union of all registered fast component stages, preserving earlier API/PWA/security/FOTA/tool coverage |
| `make release-gate-final` | All fast stages + product/feature/trace profiles, sanitizers, fresh C3/S3 production builds/config packaging, full desktop/mobile browser and bounded performance/SMALL stress |
| `make validation-nightly` | Existing MEDIUM/concurrency/extended/coverage; explicit separate hardware authorization for physical mode |

List actual selected stages from the application directory with
`python3 validation/component_gate.py --suite node --list`
(or hub/contract/backend/pwa/fast/release). Registry selection deduplicates shared
stages within each campaign. The real production runtime/codec harnesses are
reused; there is no parallel protocol implementation. GS-148 host interfaces do
not qualify unfinished production backend authentication/completion.

The GS-177 Android dashboard stage is selected separately with
`python3 validation/component_gate.py --suite caregiver-app`. It runs both the
registered Android build and the isolated voice-contract prototype checks. It
is not included in generic component, fast, or full release gates. Its APK is
dashboard-only: successful assembly does not qualify a live backend, caregiver
authentication, push, voice, or the owner's phone.

### Gate graph and integrity

```text
root Makefile → product Makefile → registered runner
  component = stages selected by ownership
  fast      = union of every registered fast component stage
  release   = fast ∪ mandatory release-only stages
```

Registration validates unique IDs, ownership, commands, required files, success
records and timeouts. C++ main harnesses must be registered or have a specific
separate-harness reason. Python discovery automatically includes new application
tests; Node/Hub Python tests also need explicit component registration. New fast
component registrations automatically join fast and release. GS-130 owns exhaustive
feature→requirement→test mapping in [MASTER_TRACEABILITY.csv](MASTER_TRACEABILITY.csv);
registration does not prove exhaustive feature coverage.

Every stage must actually execute and report a positive count or explicit successful
assertion group. Sanitizer diagnostics fail even with zero process exit; UBSan halts on errors. Lowercase browser/TAP skip, todo and unexecuted summaries also fail. Nonzero exit, zero/missing tests, unexpected skip/manual/already-
passed markers, missing dependencies and timeout fail. Timeout kills only the owned
subprocess group. Remaining stages continue to expose incomplete mandatory coverage.
Source changes during a campaign invalidate its result, including partition/config CSV inputs. Cancellation kills owned children. Incomplete nightly reports use RUNNING and cannot claim PASS.

Host object profiles include compiler identity, all product/trace/compiler flags and production source/header content (independent of mtimes);
headers use generated dependencies. Shared production translation units are cached under that profile; phony test targets still relink and execute. Special compile definitions retain their dedicated recipes. Release
variants/sanitizers use separate profiles without cleaning existing assets. Target
builds create fresh owned directories and build C3/S3 IDF6.0.3, replacing the retired
classic-ESP32 HIL prerequisite in final release. Historical HIL preparation remains
available separately and does not imply hardware permission.

No receipt reuse by default. Explicit example:
`make validation-fast VALIDATION_REUSE_REPORTS='/absolute/report1.json /absolute/report2.json'`.
Executed PASS receipts require identical source/build profile, positive valid evidence,
intact log SHA and matching compiled artifact SHA (including target build reports/BIN images). Linker-guard/include overrides are part of the receipt profile. Missing/changed receipts fail;
previously failed stages execute again. Reuse provenance is recorded, never labeled
fresh execution. Environment-only mandatory-stage bypasses are rejected. Legacy
`release_gate.py --quick` remains diagnostic, not final release readiness.

Known scoped skips remain visible: historical classic-ESP32 reserve model under
GS-D030 and unsupported25 stress with existing ten-slot rejection verified;
supported1/4/10 stress remains asserted. **No migration skip:** its current mandatory
failure prevents aggregate software PASS. Portable production-PSA reset is now
an executable Node/contract/fast/release stage; see the GS-130 evidence for its
dependency provenance and host-only limits.

### Permanent Definition of Done and impact examples

Before implementation record owning Jira, affected components/interfaces, previous
regressions, new positive/negative/boundary/fault/reboot tests, simulation/physical
requirements, profile and release impact.

- Node PowerPolicy: Node plus relevant recovery contracts; no unconditional browser.
- GS-40 liveness: Node + Hub + contract + backend/PWA; browser for UI changes.
- Product candidate: actual complete `make release-gate-final`.

After implementation: new + prior affected-component/contract tests PASS, permanent
registration verified, applicable builds/sanitizers PASS, traceability/evidence updated,
normal commit/push/actual remote verified and precise handoff. Focused PASS is
insufficient. Mandatory failures remain FAIL/PARTIAL/BLOCKED.

Reports under ignored `evidence/validation_framework/<suite>-<campaign>` record source
HEAD/fingerprint/dirty state, commands/durations/exits/count kinds, logs/artifact hashes,
reuse provenance and software status. Physical is NOT_RUN; physically_qualified and
release_approved are false. Do not log secrets or operate boards.

Host simulation/compilation does not prove real PIR/GPIO4/RF/current, power-cut NVS,
signed OTA/rollback, long sensing reliability or actual C3→S3→backend→PWA acceptance.
Required physical rows stay open until authorized current-image/fixture evidence passes.
Software PASS does not grant commercial release approval.

[GS-116 evidence](../exec-plans/evidence/R1_GS116_VALIDATION_FRAMEWORK_20261010.md)
records actual outcomes/remaining gaps. [R1 work state](../product/R1_WORK_STATE.md)
is the handoff. Next: **GS-130**, then separately authorized GS-114.

---

## Historical framework at 0eb1324 — retained provenance

Counts/branch/graphs below describe that checkpoint. Current guide above supersedes
its execution claims; physical evidence is never upgraded to current-image PASS.

**Baseline inspected:** `0eb1324c27ce3d6a2464627c6057b0cc68943c60`
**Validation branch:** `feature/hw-m1-4-regression-framework`
**Product tree:** `code`
**Scope:** current implemented behavior only; no HW-M1.4C low-power, future
aggregation, chronology redesign, retry redesign, deep sleep, BLE, or routine
learning was implemented by this framework.

This is the authoritative validation entry point. The machine-readable feature
mapping is [MASTER_TRACEABILITY.csv](MASTER_TRACEABILITY.csv). Historical
qualification evidence remains historical; automated regression does not
rewrite or upgrade physical qualification.

## Completion rule

**NO FUTURE FEATURE IS COMPLETE UNTIL ITS POSITIVE, NEGATIVE, BOUNDARY,
FAULT/RECOVERY AND APPLICABLE PERFORMANCE/REGRESSION TESTS ARE ADDED AND ALL
MANDATORY GATES PASS.**

Feature work must add or update a traceability row in the same change. A row
may be `COVERED`, `PARTIAL`, `MISSING_PRODUCT_FEATURE`, or
`HIL_ONLY_PHYSICAL`. Every `PARTIAL` row names its exact residue;
`MISSING_PRODUCT_FEATURE` is behavior that does not exist and must not be
faked by validation. None of the latter three statuses is a release claim.

## Architecture and layers

The host runtime harness compiles the production `QualifiedInput`,
`NodeRuntime`, `NodeRadio`, `NodeStore`, data-plane codecs, `HubRuntime`,
`IngestQueue`, `HubJournal`, coverage/rules, and security policy. Its
`VirtualClock` and `RuntimePair` substitute only time and transport. There is
no second node/hub algorithm. Exact retry time, identity, queue admission,
dedupe, ACK class, retirement, and state changes are decisions of production
code.

| Layer | Repository realization | Hardware |
|---|---|---:|
| L0 pure unit | C++ checks, Python `unittest`, Node test runner | No |
| L1 component/state machine | sensing, storage, radio, rules, codec tests | No |
| L2 Node+Hub simulation | `master_validation` production-runtime harness | No |
| L3 functional system simulation | canonical 92-scenario catalog, dummy streams, HTTP lab | No |
| L4 backend/API/PWA integration | Python API/application/bridge suites | No |
| L5 browser | every Playwright spec, desktop and Pixel 7 projects | No |
| L6 quality gates | ASan/UBSan, trace build, contracts, coverage manifest | No |
| L7 stress/stability | master stress/soak and existing stress profiles | No |
| L8 target HIL | fail-closed `tools/hil/nightly.py` adapter entry point | Yes |
| L9 physical qualification | immutable milestone evidence: RF, PIR optics, power/electrical | Yes |

Virtual time is an explicit monotonic millisecond value. The master cases jump
through 200 ms, retry boundaries, 60 seconds, 5 minutes, and six logical hours
without sleeping. Synthetic LOW/HIGH/LOW input uses production
`QualifiedInput`; accepted events enter production `NodeRuntime`.

`RuntimePair::attempt` supports exact-attempt MAC success/failure, packet loss,
Hub unavailable, ACK loss, duplicate packet and duplicate ACK. Hub restart is
performed by constructing a new production `HubRuntime` and re-establishing
the explicitly configured peer. The seed for compound deterministic work is
`23063` and is present in JSON and console results.

## Existing-suite inventory at the inspected baseline

Counts below were discovered from the current branch, not copied from old
evidence. “Release” describes the pre-framework `release-gate-final` behavior.

| Suite | Exact command | Framework/layer | Current count | Deterministic | HW | Isolation/reset | Result format | Release | Nightly/stress, overlap and important gap |
|---|---|---|---:|---:|---:|---|---|---:|---|
| Contracts | `python3 scripts/verify_contracts.py` | Python/L6 | contract assertions | Yes | No | read-only files | console/exit | Yes | overlaps API schema; no target wire proof |
| C++ host | `make cpp-test` | C++17/L0-L2 | 245 checks reported by HW gate | Yes | No | new process/objects | console/exit, log | Yes | broad firmware policies; old checks not individually selectable |
| Simulator | `make simulator` | C++17/L2 | one composed run | Yes | No | new process | console/exit | feature variants | overlaps C++ runtime |
| Scenario matrix | `make simulate-matrix` | Python/L3 | canonical transformations | Yes | No | fresh process | console/exit | via `verify` only | overlaps functional catalog |
| Python | `make python-test` | `unittest`/L0-L4 | 121 test methods | Yes except bounded perf budgets | No | temp/in-memory DB by suite | verbose console/exit | Yes | backend, pair/gate, logging, Playwright runner; coverage is assertion-oriented |
| JavaScript | `make app-test` | `node --test`/L0-L4 | 17 tests | Yes | No | new Node process | TAP/exit | Yes | PWA logic; not browser rendering |
| Product variants | `make product-test PRODUCT=base`; `... PRODUCT=ai` | C++17/L0 | one executable each | Yes | No | rebuild/process | console/exit | Yes | build flags only |
| Feature variants | four `make simulator TRACE_FLAGS=...` invocations in `release_gate.py` | C++17/L2 | 4 builds/runs | Yes | No | `make clean` each | per-stage logs | Yes | compile-time combinations |
| Dummy streams | `python3 validation/run_dummy_sensor_streams.py` | Python/L3 | 5 JSON streams | Yes | No | lab build/new process | console/exit | Yes | downstream behavior, not radio |
| Functional catalog | `python3 validation/run_functional_suite.py` | Python/L3 | 92 scenarios | Yes | No | scenario fixture reset | JSON/console | Yes | canonical catalog; metadata was not rich enough for firmware OR IDs |
| HTTP integration | `python3 tests/simulation_http_test.py` | Python/HTTP/L4 | script assertions | Yes | No | owned lab/in-memory state | console/exit | Yes | overlaps API and PWA bridge |
| PWA bridge/API/frontend | `python3 tests/pwa_bridge_test.py`; `pwa_68_api_test.py`; `pwa_68_frontend_test.py` | Python+Node/L4 | script assertions | Yes | No | owned process/temp state | console/exit | Yes | broad application bridge |
| Legacy browser simulation | `node tests/simulation_browser_test.cjs` | Playwright/L5 | one legacy flow | Yes | No | owned port 8765, memory DB | stage log | Yes | overlaps mandatory Playwright specs |
| Playwright | `python3 scripts/run_playwright_gate.py` | Playwright/L5 | 43 specs × 2 projects = 86 runs | Yes | No | owned port 8766/server/process group, memory DB | list+HTML+JSON, trace/screenshot/video on failure | Yes | desktop/mobile; workers=1, each spec independently runnable |
| Sanitizers | `make verify-sanitize` | ASan+UBSan/L6 | C++ host suite | Yes | No | clean rebuild | console/stage log | Yes | leak detector disabled for platform stability |
| Trace build | `make cpp-test TRACE_FLAGS=-DGS_ENABLE_TRACE=1` | C++/L6 | C++ host suite | Yes | No | rebuild/process | console/stage log | Yes | trace compile/runtime path |
| Performance small | `make performance-test` | Python/L7 | local PWA profile + SMALL stress | bounded/local | No | lab build/fresh state | JSON/console | Yes | stable local budgets only |
| Stress/concurrency/endurance | `make stress-test STRESS_PROFILE=MEDIUM`; `make concurrency-test`; `make endurance-test` | Python/L7 | profile-driven | seeded/bounded | No | fresh DB/process | JSON/console | No | MEDIUM/EXTENDED were not in final gate |
| HW fast/full gate | `make hw-validation-fast`; `make hw-release-gate` | Python+ESP-IDF/L6/L8 | staged checks | Yes | full build needs toolchain, not boards | build dirs/logs | No | full builds pair; physical stages manual |
| Pair build | `make hw-pair-build` | Python+ESP-IDF/L8-prep | one pair | Yes | no boards; ESP-IDF required | deletes generated build dirs; requires clean git | manifest/logs | No | hashes/version/dirty/embed checks |

### Exact `make release-gate-final` expansion

`release-gate-final` invokes `release-gate-browser-mandatory` then
`performance-test`. The former invokes `release-gate` and `playwright-gate`.
`release-gate.py` runs, in order: validation coverage, contracts, C++ unit,
all Python discovery, JavaScript, base product, AI product, four clean feature
variants, lab build, dummy streams, functional catalog, HTTP integration, PWA
bridge, PWA-68 API, PWA-68 frontend, sanitizers, trace build, and the legacy
browser flow. `playwright-gate` runs preflight and all 43 specs in both desktop
and mobile projects. Finally `performance-test` runs the local PWA profiler
and SMALL stress. Any mandatory command failure is non-zero.

## Implemented-function inventory

### C3/node

Implemented: debounced/retriggered `QualifiedInput`; NodeRuntime event
construction; boot session provider; monotonically allocated sequence;
bounded retained store and retry queue; four-slot non-motion reserve; explicit
`motion_drop`, `store_full`, and `priority_rejected`; one in-flight owner in the
target adapter; ESP-NOW encode/send and MAC callback accounting; durable versus
volatile application ACK; deterministic retry stages and 60-second terminal
backoff; NodeHealth codec/counters/liveness/breadcrumb/error/heap fields;
versioned configuration and service window; C3 FOTA begin/data/end/abort,
chunk/image CRC, sequence/session checks, OTA write/finalize/boot partition,
30-second maintenance timeout, pending-image validation, and restart.

Not implemented: persistent NodeRuntime retained/in-flight state across real
restart, deep-sleep retained state, signed-image verification in the wire FOTA
receiver, or target software motion-control endpoint. These are explicit gaps,
not simulated features. Receiver protocol and policy now live in the production
`fota_receiver::Receiver`; its `IOtaWriter` is implemented by ESP-IDF on target
and by a deterministic failure-injectable writer in host validation.

### Hub

Implemented: ESP-NOW receive queue; frame classification/decode/validation;
authorized node/session checks; owner-task event processing; HubJournal
same-identity dedupe; durable/rejected/discarded ACK generation; NodeHealth
receive/logging; C3 embedded-image FOTA sender with retry/ACK matching;
configuration; host cloud journal/outbox and backend/application bridge;
rules, coverage, activity and resident actions.

Not implemented in the target composition: Hub self-FOTA, durable target
journal/outbox across power loss, target Wi-Fi/backend vertical bridge, or
cross-Hub-restart persistent dedupe. Host/backend components exist separately;
the repository explicitly does not claim the target vertical slice complete.

The `checkpoint` host stage also exercises GS-148 replay-fence reconciliation
diagnostics through production HubRuntime/outbox code. Its 21 explicit
diagnostic assertions distinguish selected-state/checkpoint loading, witness
validation/publication/readback and runtime binding outcomes under injected
host storage faults. The stage is registered in `validation-hub`; target build
fingerprints include the changed Hub adapter/runtime/outbox sources. Passing
host fault tests do not identify the saved physical S3 failure or qualify
LittleFS hardware behavior. See the [GS-148 diagnostic evidence](../exec-plans/evidence/R1_GS148_REPLAY_FENCE_DIAGNOSTIC_20261012.md).

### Paired build

Implemented by `scripts/build_hw_pair.py`: clean-tree refusal, fresh C3 and Hub
builds, embedded-node synchronization, byte/SHA/size equality, image-info
version checks, `-dirty` rejection, build-order freshness, pair manifest and
provenance. Wrong/stale pairs fail validation. ESP-IDF is required; hardware is
not.

### Backend/application/PWA

Implemented and tested: event/history API and persistence, household identity
and isolation, activity/event details, I am OK, Call Family, expected and
unexpected activity rules, missing morning/activity flows, door presentation,
settings/configuration, currently shipped battery analytics, notifications and
reports, PWA bridge, local/offline service-worker behavior, desktop/mobile
browser flows, performance budgets and concurrency/scale checkpoints. Future
chronology/episode redesign and personalized routine learning are not included.

## Offline resilience matrix

All `OR-001` through `OR-035` are L2 release-blocking master cases. Run one
with `./build/master_validation --id OR-011` or
`python3 validation/master_validation.py --id OR-011`. They cover, in
the requested numeric order: online delivery; Hub loss; offline acceptance;
multiple events; retention; coherent store/retry state; first/subsequent/
periodic retry; MAC failure; ACK loss; MAC-success/no-ACK; duplicate packet;
duplicate ACK; same-session replay; Hub restart; restoration; no-node-reboot
recovery; backlog; durable retirement; final drain; prolonged outage; new
motion during drain; repeated cycles; six-hour virtual outage; deterministic
jitter; session; sequence; no simulated reset; qualified zero drop/full/
priority rejection; NodeHealth; resource-bounded recovery cycles; and the
physically qualified 28-motion/reserve/drain invariants.

The host suite does not claim RF propagation, target heap stability, actual
reset reason, or power behavior.

## FOTA and maintenance matrix

| Area | Simulation | Pair/build | Target HIL | Status/reason |
|---|---|---|---|---|
| packet/chunk size and CRC | `FOTA-PROTOCOL-001` | compile/static assertions | physical transfer | COVERED for shared protocol |
| target/version/signature policy component | `FOTA-POLICY-001` | image version checks | target image observation | COVERED component; receiver does not consume manifest policy |
| standalone/embedded equality, size, SHA, version, dirty/stale | Python pair tests | `make hw-pair-build` | hashes recorded by adapter | COVERED |
| begin/data/end sequence, duplicate/out-of-order chunk, bad session/CRC/size | `FOTA-HOST-001..010` executes production receiver | target build | connected transfer | COVERED software policy |
| writer begin/write/end/set-boot failures and false-success prevention | `FOTA-HOST-014..019` | ESP-IDF adapter compile | physical flash faults | COVERED decisions; actual flash is target-specific |
| inactivity / Hub disappearance / recovery / maintenance exit | `FOTA-HOST-011..013`, `018` | target build | connected timing | COVERED software lease; target scheduling remains PARTIAL |
| pending validation, actual reboot/new version and bootloader rollback | restart request only | paired version | connected target | HIL_ONLY_PHYSICAL/target-specific |
| Hub self-update | none | none | none | MISSING_PRODUCT_FEATURE: future Hub update milestone |
| repeated valid receiver cycles | `FOTA-HOST-020` models reboot-created receiver cycles | pair artifacts | connected A→B→C | COVERED policy; real cycles remain target-specific |
| retained event and pending ACK around maintenance | `FOTA-HOST-021..022` with production `NodeRuntime` | target build | connected target | COVERED for current in-memory semantics; target scheduling remains PARTIAL |

The host suite does not reproduce the algorithm: host and target compile the
same production receiver source. Only `IOtaWriter` and callbacks differ.
ESP-IDF owns partitions, writes, boot selection, ACK delivery and restart; the
host fake records calls and injects deterministic failures.

## Restart, storage, protocol, smoke, stress and stability

| Matrix | Automated evidence | Remaining boundary |
|---|---|---|
| C3 smoke | `C3-SMOKE-001` | target boot/radio/heap HIL |
| Hub smoke | `HUB-SMOKE-001` | target Wi-Fi/backend absent |
| System smoke | `SYSTEM-SMOKE-001` | real RF/PIR L9 |
| Hub restart with in-flight node event | `OR-016`, `RESTART-001` | target reset HIL |
| C3 restart/no pending | session-provider legacy tests | target boot HIL |
| C3 restart with retained/in-flight | none | MISSING_PRODUCT_FEATURE: NodeRuntime store is in-memory; future persistence milestone |
| both restart / restart during FOTA | receiver failure/recovery covered | actual target reset/flash remains target-specific |
| queue empty/1/near-full/full/overflow/drain/refill | legacy C++ plus `QUEUE-BOUNDARY-001`, OR cases | target NVS persistence absent |
| codec min/max/truncated/version/type/value/flags/trailing/ACK/health | legacy C++ plus `PROTO-ROBUST-001` | fuzzing PARTIAL; no new platform introduced |
| C3 stress | `C3-STRESS-001` | target heap/task metrics HIL |
| Hub stress | `HUB-STRESS-001` | target radio/backend concurrency HIL |
| deterministic chaos | `SYSTEM-STRESS-001`, seed 23063 | target FOTA leg remains connected-target work |
| stability/soak | `C3-STABILITY-001`, `HUB-STABILITY-001`, `SYSTEM-SOAK-001` | host-visible state only; target duration configurable |

Host resource assertions cover queue/journal cardinality, store/retry equality,
identity, retirement, eventual drain, and progressive retained growth. They do
not convert a heap low-watermark into a leak claim. Host throughput/performance
remains in the existing controlled profiler/stress tools; no C3 CPU, battery,
RF, or electrical inference is made.

`make validation-coverage` uses GCC `--coverage` and the installed LCOV tools.
It runs the legacy C++ suite, all 49 master runtime cases, and all 22 production
FOTA receiver cases, then restricts results to `firmware/` and `shared/`.
Artifacts are `evidence/coverage/coverage.info`, `summary.json`, `summary.txt`,
and `html/index.html`. Line and branch coverage are visible without a global
threshold. The summary names uncovered locations in NodeRuntime, retry,
sensing, codec, HubRuntime and FOTA policy, plus target-only exclusions.

## Manual/HIL to automated regression mapping

| Historical action | Automated simulation | Automated target HIL | Physical-only residue |
|---|---|---|---|
| move in front of PIR | `QualifiedInput` LOW/HIGH/debounce → NodeRuntime | future adapter software-visible motion | PIR optical/thermal sensitivity and GPIO waveform |
| unplug Hub | `set_hub_online(false)` | logical radio suppression via adapter | real power switching requires safe controller |
| restore Hub | `set_hub_online(true)` / new HubRuntime | adapter recovery | electrical boot transient |
| TX/MAC failure | exact `DeliveryFault.mac_success=false` | target radio fault seam | RF propagation |
| missing application ACK | `ack_lost=true` | target ACK suppression | RF cause |
| wait 60 seconds / long outage | VirtualClock advance | wall time or target control | none for policy; oscillator behavior remains physical |
| repeat/duplicate packet | `duplicate_packet=true` | target replay injection | RF collision behavior |
| Hub reboot while C3 alive | reconstruct production HubRuntime | target restart command | uncontrolled mains switching excluded |
| FOTA transfer/reboot/post-motion | protocol/policy plus normal runtime tests | connected target adapter | flash/boot/rollback is target-only |
| 19 h 54 min endurance invariants | OR-034/035 and virtual soak | configurable `HIL_SOAK_MINUTES` | battery discharge/current remains L9 |

## Commands and independence

From the product directory:

```sh
make master-validation
make fota-host-test
make validation-coverage
./build/master_validation --id OR-011
./build/master_validation --suite OFFLINE_RESILIENCE
make master-validation-self-test
make validation-nightly
make validation-nightly HIL=1 HIL_SOAK_MINUTES=480
```

For MAC-based HIL discovery, set `HIL_AUTO_DISCOVER=1` and supply the qualified
Hub/C3 station MACs in `HIL_EXPECTED_HUB_ID` and `HIL_EXPECTED_C3_ID`.

Every C++ master TC constructs fresh runtime/storage/clock/transport fixtures.
It has no wall-clock or previous-test dependency. Existing backend/browser
suites retain their in-memory/temp database and owned-server isolation.
Playwright specs can be run by title/project with normal Playwright CLI; the
gate owns its server lifecycle and records traces/screenshots/video only on
failure.

`validation-nightly` is the complete hardware-free overnight gate. It is
fail-fast in this order: all 49 master cases (including OR-001..035 and the
three stability/soak cases), the 22-case FOTA host suite, negative self-test,
MEDIUM stress, concurrency/isolation, authoritative `release-gate-final`,
EXTENDED 100,000-event endurance, and host line/branch coverage. The parent
marks master/FOTA already passed inside the release gate and suppresses its
superseded SMALL stress, so expensive suites have one campaign owner. Coverage
necessarily replays instrumented C++ cases as measurement. Use
`--continue-on-failure` only for diagnostics.

HIL is disabled by default. `validation-fast` runs the hardware-independent
HIL tooling/isolation checks, while `release-gate-final` additionally runs the
HIL target compile/provenance check; neither requires attached boards.
The authoritative connected Phase-1 suite is exactly `make hil-regression`.
The complete connected qualification is `make hil-qualify` from normal WSL;
it owns software-gate ordering and calls `hil-regression` rather than copying
its 71 cases. It invokes the minimal Windows usbipd helper only if WSL cannot
already verify both targets. Missing hardware is reported as BLOCKED, never as
physical PASS.

`make validation-nightly` remains hardware-free by default and includes the
HIL tooling, isolation and target-build checks. `make validation-nightly HIL=1`
adds `make hil-qualify`, the only orchestration path. No Phase-2 soak or FOTA
matrix is started by these integrations.

## Fast-gate coverage map

This map describes the current `make validation-fast` execution path. A
registered test is covered only when its owning command is reached and returns
nonzero on failure. Physical proof remains separate.

| Feature / invariant | Test | Fast-gate execution path | Physical qualification needed? | Status |
|---|---|---|---|---|
| Phase-1 Node/Hub runtime, events, ACK/retry, outage/recovery and baseline persistence | `tests/cpp/test_main.cpp`, `tests/cpp/master_validation.cpp` | `release_gate.py --quick` → `cpp-unit` and `master-production-runtime`; prerequisite HIL host/replay gates | For target behavior | Executed; host failures fail the gate |
| Phase-1 HIL parser/supervisor real-evidence replay and production/HIL isolation | `test_hil_supervisor`, `test_hil_phase1`, `test_hil_real_replay`, `hil_host_gate.py` | `validation-fast` → `hil-tooling-test` and `hil-host-check` | Yes for connected hardware claims | Executed; host failures fail the gate |
| Phase-2 commissioning, identity, authenticated runtime/rejoin and replay protection | commissioning, rejoin, and runtime AEAD C++ validations | `validation-fast` prerequisites → commissioning/rejoin targets; quick release gate → master runtime | Target/physical claims remain distinct | Executed; host failures fail the gate |
| Registry admission/revocation, association and Node/Hub persistence | registry, association, recovery and journal C++ validations | `validation-fast` prerequisites → registry/persistence targets | Power-loss claims need target evidence | Executed; host failures fail the gate |
| 1/4/10/25 logical-node behavior, pressure, fairness and outage recovery | Multi-node host validation and summary checker | `validation-fast` prerequisite → `multinode-host-test` | Physical RF scale claims need physical Nodes | Executed; host failures fail the gate |
| FOTA codec/state machine and boot-health policy | `fota_host_validation.cpp` | quick release gate → `fota-host-state-machine` | Physical update/rollback claims require HIL | Executed; host failures fail the gate |
| Authenticated FOTA sender guard, secure receiver adapter and digest checks | `hub_fota_guard_validation.cpp`, `secure_fota_adapter_validation.cpp` | `validation-fast` prerequisites → `hub-fota-guard-host-test`, `secure-fota-adapter-host-test` | Physical signed-FOTA claims require the dedicated campaign | Executed; host failures fail the gate |
| BAT-C1–C5 policy, queue/retry invariants, NodeHealth cadence and Hub lease | C++ BAT-C5 checks and `test_battery_power_invariants.py` | quick release gate → `cpp-unit` and full `python-backend-db-logging` discovery | Quiet-node timing and energy require measurement | Executed; host failures fail the gate |
| Backend/API, event chronology, dedupe, offline/online state, caregiver actions and PWA | Python discovery, functional catalog, HTTP, bridge, PWA API/frontend and browser smoke | quick release gate named stages | Real deployment and physical vertical path remain separate | Executed; host failures fail the gate |

The focused secure FOTA host targets run once as `validation-fast`
prerequisites; their results are not repeated inside `release_gate.py`. The
quick gate shares product/trace-specific object files across its C++ host
binaries, so `cpp-unit`, `master-production-runtime`, `fota-host-state-machine`,
`lab-build`, and the multi-node prerequisite do not recompile their common
production sources. The Python discovery stage follows one `lab-build`; the
browser stage reuses that binary before launching its isolated local server.
The Python test stage itself does not trigger another build through the
`python-test` Make dependency. The fast gate excludes physical signed-FOTA, current/endurance/sleep HIL,
`release-gate-final`, nightly endurance, and full PWAE2E campaigns.

Execution modes are distinct: simulation nightly needs no hardware; HIL
nightly requires configured connected Hub+C3 and blocks when absent; milestone
physical qualification owns RF/electrical/PIR/battery/brownout and electrical
power-interruption evidence. A relay is not required by this framework.

## Reports and triage

Master results: `evidence/master_validation/results.json`, `junit.xml`, and
`runner.log`. Nightly results: `evidence/validation_nightly/summary.json`,
`summary.md`, and numbered stage logs. Browser HTML/JSON and failure media stay
under `evidence/`. Pair builds emit `build/hw_pair/provenance.json`. HIL emits
`evidence/hil_nightly/summary.json` plus adapter log.

For a failure: identify the TC and feature row; rerun the exact ID; inspect its
stage/runner log; reproduce without failure injection; decide whether the
failure is product, test, environment, or explicit HIL block; fix without
weakening the assertion; rerun the TC, parent suite, master, and the applicable
gate. Preserve material target evidence under the existing evidence policy.

The negative self-test sets `GS_VALIDATION_INJECT_FAILURE=OR-001` only in a
child process and proves that the specific TC and parent command are non-zero.
It then exits PASS only when detection worked. No source is modified and the
normal suite is rerun green.

## Adding validation

Add an ID-addressable case to the narrowest existing framework, map it in
`MASTER_TRACEABILITY.csv`, include positive/negative/boundary/fault/recovery
and stable performance cases that apply, and assign release/nightly/HIL
membership. Reuse the canonical scenario catalog for product scenarios. Add a
new framework only when the existing production seam cannot express the case.
If hardware or unimplemented persistence prevents automation, record the exact
gap and reason; never mark it PASS or implement a future feature to fill it.

## Clean post-commit pair qualification

The intended Phase-1 qualification order is:

```text
make validation-fast
make release-gate-final
make hil-qualify                         # pre-commit software + connected fixture
git commit                                 # deliberate human checkpoint
make hw-pair-build
make hw-release-gate
make validation-nightly
make validation-nightly HIL=1              # optional connected nightly
```

The real-target IDs have one owner (`make hil-regression`); top-level gates
invoke that owner rather than copying its scenarios.

Do not bypass the pair builder's clean-tree safeguard. This closure pass is
intentionally uncommitted, so neither command below is claimed here. After the
validation-framework change is reviewed and committed, with no tracked or
untracked source changes remaining, run from the product directory:

```sh
git status --short
make hw-pair-build
make hw-release-gate
```

The first command must print nothing. `hw-pair-build` then performs fresh C3
and Hub builds, synchronizes the embedded C3 image, validates commit versions,
byte equality and SHA-256 values, and writes pair provenance. Only after that
PASS should `hw-release-gate` consume the clean pair and run its full static,
target-build, size and integrity checks. Connected HIL remains a separate gate.

## Physical-only boundary

L9 retains actual RF range/RSSI accuracy, current, battery discharge,
brownout voltage, PIR optical/thermal sensitivity, converter/cutoff/thermal
behavior, and GPIO electrical waveform. Target flash, boot, ESP-IDF restart,
FOTA and radio behavior belong in L8 whenever configured connected hardware
and a safe adapter are available.
# Phase-1 unattended Hub+C3 HIL checkpoint

The connected-target core gate is documented in
`docs/validation/HIL_AUTOMATION.md` and invoked from repository root with
`make hil-setup`, `make hil-preflight`, `make hil-smoke`, and
`make hil-regression`. It adds HIL-SMOKE-001..017, HIL-RADIO-001..010,
HIL-OR-001..020, HIL-HUB-RST-001..010, HIL-C3-RST-001..008 and
HIL-BOTH-RST-001..006 (71 automated real-target cases). Six electrical,
optical, RF/current/battery/thermal boundaries remain explicit extra-fixture
rows. FOTA and extended stress/soak remain Phase 2.

## GS-130 application lifecycle regressions

The PWA feature rows `PWA-ONBOARD`, `PWA-SCHEDULE`, `PWA-CLAIM`, `PWA-NOTIFY`,
`PWA-ACTIVITY` and `PWA-CACHE` in `MASTER_TRACEABILITY.csv` map focused assertions
to the existing `javascript` and, where applicable, `python` stages. The JavaScript
suite registers `tests/js/application_lifecycle.test.mjs` through the existing
`make app-test` glob and stage input; backend tests remain under normal Python
discovery. For focused app changes use `node --test tests/js/application_lifecycle.test.mjs`
and only directly affected Python unittest methods/modules. This does not require
Node/Hub/contract or release gates unless a shared contract changes.

The service-worker harness executes the production worker source with controlled
worker globals/cache/fetch, covering activation, offline shell fallback, missing
assets, recovery and cache-read failure. It does not prove browser cache eviction,
quota or installed-device lifecycle. The current lightweight PWA feature modules
do not implement durable interrupted-onboarding recovery or an offline settings
queue; notification subscription and activity persistence across a real browser
restart remain partial and explicitly tracked rather than inferred from helper
tests. Full browser validation remains a release/affected-browser gate and was not
executed by the focused GS-130 continuation.

## GS-114 fixture-compatible RPF diagnostic build — 2026-10-12

make gs114-s3-rpf-diagnostic-build
is an explicit build-only target. It uses the existing S3 fixture commissioning
test stage, whose ten tests are registered for Node, Hub and contract gates.
The target builds the C3 embedded asset and S3 product composition, validates
the commissioned candidate gs_outbox/gs_state partition profile and a
standalone S3 app, and writes artifact provenance under the ignored unique
build/gs114_fixture_pair/build-* directory. It is not part of routine component
gates and never invokes a flash or device command. ESP-IDF's generated full
bundle remains NOT_AUTHORIZED_FOR_DEPLOYMENT; physical installation, state
preservation and rollback are separate approval/qualification gates.

## GS-125 isolated Dashboard integration candidate — 2026-10-15

The isolated Dashboard integration validation and exact 13-path conflict matrix
are recorded in
[`CONFLICT_RESOLUTION_AND_VALIDATION.md`](../exec-plans/evidence/integration_gs125_20261015/CONFLICT_RESOLUTION_AND_VALIDATION.md).
The candidate used the latest reviewed canonical and Dashboard checkpoints and
did not modify either source worktree. Engineering host (98), framework (44),
traceability (22), Caregiver JavaScript (23), Caregiver browser (86),
Engineering PREVIEW_ONLY browser (20), and the focused canonical C8/storage/
Cloud Worker checks are recorded with their native receipts. This candidate's
PWA aggregate remains FAIL: P0 product status is PARTIAL, and its initial Python
attempt records a missing Hub test-binary prerequisite even though a subsequent
full Python discovery passed after building that prerequisite. The original
aggregate is preserved. Historical migration remains FAIL, physical qualification
remains NOT_RUN, release approval remains false, and release-gate-final was not
run. These results are integration-candidate evidence only; they do not change
canonical release status or authorize a merge.

## GS-177/GS-179 local-LAN reconnect test registration — 2026-10-22

Router-independent local TEST_ONLY reconnection uses the existing GS-177 and
GS-179 registered suites. Added required markers are `GS177-API-LAN-ORIGIN-001`
and `GS177-API-LAN-ORIGIN-002` in the caregiver API suite,
`GS177-PWA-LAN-RECONNECT-001` and `GS177-ANDROID-LAN-RECONNECT-001` in the
Android dashboard suite, and `GS179-LAN-AUTO-001` / `GS179-LAN-RECOVERY-001`
in the PostgreSQL E2E suite. The updated feature row is `GS-PWA-01` in
`MASTER_TRACEABILITY.csv`; Android phone/network acceptance remains
`PHY-GS177-ANDROID-01` and NOT_RUN.

On 2026-10-22, focused source-linked host/API/security and browser tests passed
as recorded in
[`GS-179 laptop LAN evidence`](../exec-plans/evidence/GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md#2026-10-22--router-independent-test_only-reconnect-implementation).
The phone transition across Yogi → Agrim → Yogi was not executed. Current
Agrim readback found that the Windows portproxy still targeted the prior
address; therefore current laptop LAN reachability is FAIL, despite healthy
local PostgreSQL and caregiver HTTPS. The optional elevated Windows refresh
watcher was not registered. These software results do not promote the physical
case or real Hub/PIR status.

## GS-177 UX integration after the Wi-Fi checkpoint — 2026-10-22

The router-independent TEST_ONLY source checkpoint was committed first at
`fd6437eee69ca6cfabd78ab3fc3b9f38801444db`; the approved UX commits were then
integrated on the canonical branch at `608c5ba40453f3eead9b5e831fe22dbbe68efed5`
and `794b355364471c89bf0ec30006e77e5e64e15735`. Existing source-linked browser
assertions were corrected for the approved incident-driven Home heading,
authenticated watermark and semantic incident-state attribute.

Integrated-source validation: `make -C code gs179-postgres-e2e` 55/55 PASS;
`make -C code pwa-68-browser-test` 4/4 PASS and 92/92 catalog assertions;
caregiver API 22/22 PASS; runtime JavaScript 10/10 PASS; GS-179 security 18/18
PASS; validation framework 51/51 PASS; feature coverage/traceability PASS
(225 features, 278 source modules, 26 physical cases; 22/22 framework checks).
These are HOST_SIM/TEST_ONLY and browser/API software results. The actual
Android phone and Yogi → Agrim → Yogi sequence remain NOT_RUN. Current Agrim
portproxy still points to the historical Windows address, so phone LAN route is
not verified. The Android CI APK build remains pending on final integrated source.

### Combined local-LAN APK build result — 2026-10-22

Workflow [39797650882](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39797650882)
built source `ed99dbe1d73286110670c0128e2476415e387d2a` with origin
`https://desktop-3qqu64b.local` and `GS177_LOCAL_LAN_TEST_ONLY=1`. Its sole
Android job completed SUCCESS: PWA browser 4/4 and 92/92 rendered checks,
caregiver API 22/22, Android dashboard 12 checks, voice prototype 28 checks,
APK v2 signature and upload passed. Artifact ID `12434502262`, APK SHA-256
`5aaea3c6f71e1d60b401436d987fb50633c4766ba4e7318384e077ad7f0bd02f`; signer
certificate SHA-256 `141f15cdaec4645094cb0657956f8b82110f2f4eccfda61a9b5260052e111392`.
The runner-generated debug signer differs from previously recorded APKs, so
installation as an in-place update is not established. The installed phone
signer was not inspected and no install/uninstall occurred. The artifact build
and simulated tests do not establish phone network, WebView, or physical-sensor
acceptance. The overall GitHub run remained `in_progress` after its sole job
reported success. Preserve the separate default-origin push run failure
39797636040: Chrome DevTools did not start for the first catalog case; later
correctly configured local-LAN workflow passed the full browser stage.

Final status refresh: workflow run 39797650882 finalized `completed / success`
at 2026-10-22 14:50:44 UTC; the prior in-progress aggregate state was delayed
status propagation.

## GS-179 Android discovery diagnostics and endpoint retention — 2026-10-23

The explicit “Use paired laptop” action previously cleared the working saved
endpoint and immediately loaded the stable `.local` origin before foreground
NSD had resolved and verified a candidate. It now retains the existing working
origin and its server SPKI pin while restarting discovery; only a candidate
that passes platform TLS trust/IP hostname validation, expected laptop DNS SAN,
saved-key continuity and `/readyz` replaces it. The GS-75 caregiver UI
refinements already integrated on the canonical branch are preserved.

The TEST_ONLY Android diagnostics now expose browse/no-service timeout, service
and TXT filtering, resolve failures, IPv4 selection, TLS/SAN/SPKI/readiness,
endpoint persistence and handler delivery. The Windows advertiser now records
the `DnsServiceRegister` return and completion callback status in a read-only
status file. At this checkpoint, Windows reports status 9506
(`DNS_REQUEST_PENDING`) followed by callback status 0 for
`GharSajag-GS179-desktop-3qqu64b._https._tcp.local` at `192.168.1.8`. This is
Windows registration evidence only; handset discoverability remains NOT_RUN.
The initial byte-order hypothesis was rejected against Microsoft's
`IP4_ADDRESS` documentation: the API expects host byte order, and the original
conversion was retained.

Software validation: GS-179 PostgreSQL E2E 55/55 PASS; connected-lite API
22/22, three scenarios and shared runtime 10/10 PASS; Android runner source and
branding checks PASS; shared PWA runtime 10/10 PASS; feature coverage 225 rows,
280 modules, 26 physical cases and 22/22 mapping checks PASS; Windows policy
validation 14/14 plus record construction PASS. The local Android runner stopped
at its missing-Gradle dependency after source/runtime checks, so hosted browser,
Android unit tests, APK build and artifact/signature verification remain
pending. Physical phone DNS-SD and Yogi → Agrim → Yogi remain NOT_RUN; no app
installation, data clear, hardware access or privileged watcher activation was
performed.
