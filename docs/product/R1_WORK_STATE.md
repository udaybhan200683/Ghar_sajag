# R1 Current Work State

## GS-114 Part 2 physical preflight — 2026-10-11

Preflight at source checkpoint `02d7a12bd0f523a3acf7b80bfc06ac996fd14c76`
found no `/dev/serial/by-id` directory or `/dev/ttyACM*` interfaces in the
current WSL environment. No board was opened or otherwise interacted with. The
existing genuine-motion observer sets DTR/RTS low and sends no bytes, but its
own safety note says serial open may affect an unverified adapter; the S3
fixture is CH343 and a non-reset guarantee is not established. Real PIR
qualification is therefore **BLOCKED before stimulus**. Operator still needs
to confirm the exact disposable pair is attached, the AM312 is already safely
wired to C3 GPIO4, and they are available for prompted motion; a verified
no-reset observer or explicit approval for the bounded DTR/RTS-low serial open
is also required.

Part 1 hashes remain the recorded build artifacts from source
`73e1e842ff843a696d592bd7c2004b72a512082c` (C3
`b03b3b2ed7996b594f9fe7d59241f558a6af82774db07a661e5346731db83014`, S3
`f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1`), not
verified flash readbacks. C3 firmware sources are unchanged through this
checkpoint; the intervening S3 delta adds CloudSync generation provenance and
does not affect GS-114 local event/ACK/sleep behavior. This does not establish
which images currently run on the fixture. No motion, reset, outage, FOTA,
storage operation or physical measurement occurred. Exact case dispositions
and the next safe action are in
[`GS114_PART2_PREFLIGHT_20261011.md`](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2_PREFLIGHT_20261011.md).

**GS-114 remains In Progress and is not eligible for closure.** P1 is NOT_RUN;
P2–P9 remain NOT_RUN/BLOCKED as mapped in the preflight record; P10 belongs to
GS-149. The preserved Part 1 evidence remains limited to its recorded scopes.
Local/remote HEAD at preflight was `02d7a12bd0f523a3acf7b80bfc06ac996fd14c76`;
only this work-state/evidence documentation is intended to change. Untracked
S3 `managed_components/` and prior redacted Part 1 logs remain preserved.


## GS-130 P0 full-product E2E and HIL runner checkpoint — 2026-10-11

Current implementation adds `make validation-p0-e2e` to the existing GS-116
registry, joining the production C3/S3 host event path and S3 CloudSync serializer
to the actual local API/service and shipped caregiver PWA in one focused
Chromium scenario. The separate GS-116 opt-in `make validation-board-hil` and
`make validation-motion-hil` runners are implemented with no-run JSON evidence,
fixture/image/USB-serial preflight, operator confirmation, no UART writes and
unique evidence directories. Their unit tests exercise safe-block/NOT_RUN paths
only. **No physical ports were opened and no physical stimulus occurred.**

The initial product vertical test is PARTIAL. It proves C3/S3 host stack
EventKey retry/dedupe/Durable ACK, local API activity and incident processing,
Hub API lease projection, household isolation, configuration validation and
Chromium timeline/door/connectivity/alert rendering. The production-shaped Hub
CloudSync event-key request receives fail-closed 503
`durable_event_store_unavailable`; the local API test route is not the unfinished
GS-148 authenticated COMMITTED contract or production OIDC. The official
`make validation-p0-e2e` stage therefore reports FAIL when the harness's
`product_status=PARTIAL`. This is intentional release safety, not a failed
scenario assertion. No product feature coverage or release qualification is
claimed complete. Exact scenario/gap mapping, outputs, gate results and physical
limits are in [dated GS-130 P0 E2E/HIL evidence](../exec-plans/evidence/R1_GS130_P0_E2E_HIL_20261011.md).

Final focused checkpoint: the P0 stage executed 17/17 scenario markers and one
Chromium case, then correctly exited nonzero at the PARTIAL completeness check;
the existing board-stack suite reran PASS at 8 groups/325 checks. Runner
integrity is 15/15, component-gate integrity 39/39, feature mapping 19/19,
focused API/durable regressions 19/19 and app tests 23/23. No serial port or
board was accessed; physical status stays NOT_RUN.

Latest same-source verification after adding exact scenario selection: the
scoped `make p0-product-e2e P0_SCENARIOS=P0-E2E-002` passed its selected
assertion and selection tests (3/3), with browser tests correctly omitted. The
unfiltered registered `make validation-p0-e2e` then ran 17/17 assertions plus
one Chromium test; its component command exited 0 but completeness adjudication
returned FAIL / outer exit 2 because the product result is PARTIAL. Final
post-commit report at source HEAD
`5e785b49839fc2fa914a3baf8886f6e707a3de3d`:
`code/evidence/validation_framework/p0-e2e-1791729788813148262/report.json`,
source fingerprint `add14d809ae6ee942f0d282a668bbe72e7071b6d25efb6353d24027f11f85285`,
tracked source unchanged; stage 11.661 s, total 12.170 s. Board-stack rerun at
the same source/fingerprint passed at 8 groups/325 checks in 6.681 s.

Implementation commit `4fd36f31518cb5f7e3c33d0b62862d59813516ce` was pushed
normally and the actual origin branch was verified equal. GS-130 comment 10436
records implementation evidence without changing workflow fields. This work
state/evidence delivery closeout is a documentation-only follow-up. The final
task handoff records its resulting local/remote HEAD and Jira comment. Existing
untracked S3 `managed_components/` and redacted GS-114 evidence were preserved
and excluded from the GS-130 implementation commit.

GS-148 retains the CloudSync commit integration gap and historical journal
migration FAIL. GS-130 still has partial P0 use cases where production scheduler,
provider, persistent backend, OIDC, firmware lifecycle or physical acceptance is
not implemented/testable in this vertical. `make release-gate-final` and broad
unchanged suites remain NOT_RUN. No product requirement/context version, Jira
workflow/rank, firmware behavior or physical authorization changed. Next
software handoff remains GS-130 gap closure; next physical campaign remains
separately authorized GS-114.

## Permanent physical HIL catalogue audit — 2026-10-11

GS-114 coverage audit reuses GS-130's 149-row traceability matrix and 200-row
source inventory (the two GS-114 fixture commissioning-adapter modules are now
reciprocally mapped to secure commissioning). The matrix classifies implemented/partial features as 45
`PHYSICAL_REQUIRED`, 40 `PHYSICAL_CONDITIONAL`, and 57 `SOFTWARE_ONLY`; the
remaining seven are one `NOT_IMPLEMENTED` (FOTA-HUB-SELF-01), three `ON_HOLD`
(BAT-C9, GS128-RUNTIME-CONFIG, GS147-JOURNAL), and three `DEFERRED` (BAT-C11,
BAT-C12, P1-TEMP-CAMERA), not rows missing physical classification. Required and conditional
rows resolve to case IDs in `docs/validation/PHYSICAL_HIL_CATALOGUE.csv`.
Catalogue registration is separate from execution and physical acceptance.

The case catalogue preserves the existing HW-M1.4 supervisor/71 test IDs and
marks its classic ESP32 Hub campaign historical-only for current S3. It records
the actual bounded GS-114 Part 1 observations: A02/A03/A06 PASS, A01 PARTIAL,
A07 timer-counter-only PARTIAL, A04/A05 NOT_RUN, A08 BLOCKED. BAT-C8 C8-P1–P9
remain NOT_RUN. No boards/serial ports were accessed in this audit. No current
S3-compatible unattended or operator-prompting HIL runner existed at that audit
checkpoint; GS-130 later added separate opt-in observational and genuine-motion
runners, documented in the current section above. Legacy `hil-regression` is not
safe for this S3 fixture and can build/flash/reset/inject motion.

Added hardware-independent catalogue mapping tests to `hil-tooling-test` and a
release-only evidence checker in GS-116's registry. The release checker fails
when mandatory physical rows are partial, missing or historical; it never
operates hardware. See [dated HIL coverage evidence](../exec-plans/evidence/R1_HIL_COVERAGE_AUDIT_20261011.md)
for commands and exact evidence. The full software release gate was not run;
physical qualification and product release remain NOT_APPROVED. The existing
GS-148 journal migration failure remains visible and unchanged.

Next physical work remains **GS-114**, on the separately authorized matching
fixture: current-image P1–P9, actual optical PIR/GPIO4, timer/radio restoration,
event Durable ACK/EventKey, sleep/retry/rejoin, outage recovery and maintenance
inhibitors. GS-108 later owns broad stable-head HIL after S3 runner compatibility
work. No Jira workflow/rank/dependency changes are implied.

## GS-114 fixture commissioning and focused Part 1 result — 2026-10-11

User-approved, S3-only `GS_HIL_COMMISSIONING` adapter reuses the existing
HubSecurityLink commissioning owner and cryptographic protocol. It is opt-in
and disabled by default; broad S3 HIL-control rejection remains. The two
specifically authorized disposable boards were clean-installed after exact
C3/S3 identity checks. Fresh association, authenticated rejoin, C3
software-restart rejoin, and a subsequent authenticated NodeHealth from the
same Node after the S3 app restart were observed. The five-minute health
opportunity and timer-wake counters were captured without PIR stimulus.
Detailed image hashes, logs and limitations are in [GS-114 Part 1 fixture
evidence](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md).

`make validation-node` and `make validation-contract` PASS. `make validation-hub`
remains FAIL (exit 2) solely at the known GS-148 `hub-journal-migration-host-test`
assertion `clean migration commits`; all other registered Hub stages passed.
The test and ownership constraints remain unchanged. Focused adapter parser /
isolation tests and existing commissioning crypto, rejoin, association and
fresh-install checks pass. The ESP-IDF 6.0.3 production-profile C3/S3 builds
pass (C3 934,192 B; S3 1,868,880 B); fixture UART command strings are absent
from the production S3 image.

Physical outcomes are bounded: HIL-A01/A02/A03/A06 PASS within stated scope,
A07 PASS for timer-wake telemetry only, A04/A05 NOT_RUN, A08 BLOCKED. No genuine
PIR exercise, event Durable ACK, offline threshold, FOTA, RF fault, current
measurement, broad HIL or release gate was performed. GS-114 P1–P9 physical
qualification remains open; Part 2 PIR and battery qualification are not
started. The fixture adapter is not GS-109 product commissioning and uses
unprotected development identity material; never ship or use it on protected
or production devices.

Work remains on `/home/udaybhan/projects/Ghar_sajag_r1`,
`feature/r1-commercial-baseline`, starting at
`73e1e842ff843a696d592bd7c2004b72a512082c`; source, tests and documentation
passed focused validation. Commit `fee4b230ce954ea8b429390f1d89c44f105458f0`
was pushed normally and matched the actual origin branch at verification.
Existing untracked S3
`managed_components/` and prior redacted failed-attempt evidence are preserved.
Documentation closeout commit `ad93cea52f6bbf0e628fee5ed5fb24981dd877c6` is
also pushed and remote-verified. GS-114 comment 10428 records implementation,
test and bounded physical evidence. GS-109 comment 10429 explicitly states the
fixture adapter does not satisfy product Add Device authorization; GS-114 ↔
GS-109 is linked without changing either workflow status or rank. Next is the
separately authorized GS-114 Part 2 physical PIR work.

## GS-130 focused application lifecycle continuation — 2026-10-11

Starting local and GitHub HEAD: `17fb074cdb1caa5ff1a08135222b29ec502c1dda`,
branch `feature/r1-commercial-baseline`. Focused app lifecycle continuation
added six stable application regression cases and one Python claim-expiry case.
`make app-test` passes 23/23, notification backend regressions 8/8, related claim/
identity/activity backend tests 4/4, and settings persistence tests 2/2. Direct
service-worker script execution exposed and fixed unsafe rejected-cache behavior:
navigation now falls back to the cached shell and unavailable/corrupt resources
return explicit 503. Details and limitations are in the linked dated GS-130
evidence section below.

Gap disposition: worker navigation/recovery PASS in a deterministic VM harness;
claim expiry/reconnection PASS in UI-policy and API model tests. Onboarding,
offline settings and notification/activity browser lifecycle are PARTIAL because
the current app has no persisted onboarding transaction or durable offline settings
queue, and live browser storage/push subscription lifecycle remains untested. No
broader feature was invented. Full PWA/browser, full release and physical suites
remain NOT_RUN. Historical GS-148 Hub migration FAIL remains unchanged; no Node,
Hub, contract or 325-check board-stack suite was rerun. Jira status/rank/dependencies
and product requirements are unchanged.

Implementation commit `a0452084b50d2d720010719cbc3a5d18ccd71b8b` and evidence
commit `44f27ce1215dfdce7f51c576fd26cf457edb0ab8` are normally pushed; actual
remote HEAD matched. GS-130 Jira delivery comment10419 records the focused results.
This work remains PARTIAL pending the listed lifecycle gaps and historical
migration disposition. Separately authorized GS-114 P1–P9 remains the next
physical qualification.

## GS-130 feature regressions / board-stack checkpoint — 2026-10-11

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; starting local/remote
`d3857fd76aff71b58287bee72aaa3b36b6042d89`. The implementation is preserved
sequentially; no new branch/worktree or physical action. Resume at actual verified
branch HEAD, recorded in the final GS-130 Jira delivery comment.
Validated implementation checkpoint `9349ed33ba72b7cf80d35a87c4108d4a9b1bda66` is normally
pushed; actual local/remote HEAD matched. The subsequent Markdown closeout
revision is recorded in Jira. Tracked tree clean; original S3 untracked assets preserved.

[GS-130 evidence and exact resume](../exec-plans/evidence/R1_GS130_FEATURE_COVERAGE_20261011.md)
and [MASTER_VALIDATION](../validation/MASTER_VALIDATION.md) index the existing
feature matrix (149 behavior/validation rows), source inventory (198 files) and
14 physical campaigns. These counts do not prove 100% semantic coverage.

**A: feature/category coverage PARTIAL.** New production boundary regressions,
real portable TF-PSA reset execution, prior Node/Hub/contract regressions and
permanent mapping/integrity enforcement are delivered. Specific application
offline/cache/onboarding/config/claim/notification lifecycle gaps remain mapped
under GS-130; unchanged application execution is NOT_RUN by focused user policy.

**B: portable C3/S3 E2E executable PASS, eight groups/325 checks.** Real sensing,
runtime, crypto/session, encrypted Node recovery, S3 outbox/journal/reducers,
health/piggyback, outage/sleep/priority and FOTA interruption run through host
hardware boundaries. Complete target-stack acceptance remains PARTIAL: target
app_main/task/callback/radio suspension-restoration orchestration is not executed
by this driver. Do not equate policy/runtime simulation with every firmware entry
point. Target-only qualification belongs to GS-114/108; any future host seam must
exercise production orchestration. Physical proof remains separate.

Focused Node and contract gates PASS; Hub FAIL only for mandatory historical
`clean migration commits` (line194), owned by GS-148. GS-D001 deferred arbitrary
legacy migration and GS-D029 fail-closed ownership remain unchanged. Fresh current-
format/S3 recovery passes separately. The test is neither skipped nor weakened.
Evidence records exact final commands/counts/durations/exits/profile/fingerprint.
Framework/traceability and new focused ASan/UBSan checks pass. Firmware/config/
partition bodies unchanged; existing verified IDF6.0.3 GS-116 C3/S3 image/build
evidence still applies. Fresh target builds NOT_RUN; full fast/release/browser
NOT_RUN; product release NOT_APPROVED; physical qualification NOT_RUN.

**Next executable action: finish GS-130 coverage gaps**, starting with precise application lifecycle mappings
and tests when within the authorized validation scope. Target-only owner/radio
qualification remains with GS-114/108; do not create a second business algorithm. Do not rediscover/restart
the delivered boundary/board/PSA framework. Then **GS-114 P1–P9** requires separately
authorized fixtures and current matched GS-40/150 firmware/config. GS-40 actual
heartbeat/offline caregiver acceptance remains open; GS-149/146 retain their
existing dependencies. Preserve original S3 managed_components and ignored assets.
No requirement/context, Jira status/rank/dependency or production behavior change.

New GS-130 comments10411/10413 were reconciled during delivery: Track C is an
inventory/reuse handoff of existing canonical HIL, not greenfield implementation.
GS-108 owns broad stable-head HIL; GS-114 owns P1–P9. Existing supervisor motion
is synthetic INJECT_MOTION and campaign defaults flash. C1/C2 actual execution
NOT_RUN without approved safe fixture; genuine optical evidence and historical
image-matched traces remain distinct. No serial/USB/board command was invoked.

## GS-116 resumed framework delivery — 2026-10-11

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting/verified remote checkpoint
`7b93dea9561ec4f0301ecd77a7b578bee8a1c36a`. Resumed preserved uncommitted
framework from GS-116 comment10370; no new branch/worktree or hardware action.
GS-116 implementation/qualification checkpoint `c71bb9624e62f350fa22f9b19d8692615982f316` is normally
pushed and actual local/remote HEAD verified equal. Post-commit source fingerprint
matches every final component/build report. The following documentation closeout
revision is recorded in the final Jira handoff; resume at actual canonical branch HEAD.

See [GS-116 execution evidence](../exec-plans/evidence/R1_GS116_VALIDATION_FRAMEWORK_20261010.md)
and [permanent execution guide](../validation/MASTER_VALIDATION.md).

Node/Hub/contract/backend/PWA commands share one executable stage registry;
fast is their deterministic union; final release dominates fast and adds fresh
C3/S3 production builds, sanitizer/trace/product variants, browser and bounded
performance. AGENTS.md permanently enforces new plus prior-component regressions,
contract impact, registration and distinct software/physical/release evidence.
GS-130 owns exhaustive feature-to-test completeness, including the separately
built portable PSA factory-reset harness and physical evidence definitions.

**Migration diagnosis supersedes the GS-40 UNRESOLVED finding below:** current
and independently compiled pre-GS-40 `913b1ded` reproduce `clean migration commits`
at tests/cpp/hub_journal_migration_validation.cpp:194. Classification
HISTORICAL_BASELINE_DEFECT: legacy checkpoint owner domain versus current
registry-domain import; the durable-transition guard correctly rejects it before
legacy erasure. GS-D001 defers arbitrary legacy migration; GS-D029 ownership
safety is preserved. GS-148 receives the technical storage handoff; GS-126 is not
the storage owner. No production migration fix or assertion weakening in GS-116.
The test remains mandatory; aggregate Hub/fast/release cannot be PASS while it fails.

GS-11610405 permanently distinguishes component development from release acceptance.
Current work runs Node/Hub/shared security contracts, framework tests and relevant
builds/sanitizers. Full release execution is NOT_RUN/deferred until a genuine
release candidate; lightweight registration tests establish composition only.
The pre-correction interrupted release attempt remains disclosed in evidence.

Final component qualification: Node15/15PASS (280.585s), shared contracts23/23PASS
(0.844s verified receipt campaign), Hub27/28PASS (374.234s), aggregate HubFAIL only
for migration. Framework33testsPASS; simulator default link/runPASS. Sanitizer and
target-build final results PASS: ASan/UBSan CPP1479/GS-401320; clean IDF6.0.3
C3 934,192bytes and S3 1,868,800bytes, slots/config/exact embedding PASS. This is framework delivery
with a known software qualification failure, not complete product release acceptance.

Current qualification results and exact checkpoint are recorded in the linked
evidence and final owning Jira delivery comment. Physical remains NOT_RUN.
Next executable task **GS-130**, then separately authorized **GS-114 P1–P9**
with matching GS-40/150 C3/S3 images/configuration; GS-149 power and GS-146 retain
existing prerequisites. Preserve S3 managed_components and original ignored
assets. GS-40 real-target heartbeat/offline visibility, GPIO4/radio/power-cut/
signed-FOTA and endurance acceptance remain open. No workflow/rank/dependency change.


## GS-40 software delivery / physical handoff — 2026-10-10

GS-40 source implementation is complete: default 300 s, internally derived 910 s,
identical day/night authenticated-contact/piggyback cadence, validated schema 1
JSON embedded into C3/S3 startup policy, trusted physical identity mixed-profile
mapping, and per-device backend/PWA received-contact freshness. GS-D031/context
2026-10-10.001 record the approved policy; GS-128 remains OnHold. Actual preceding
production cadence was 120/310; historical 60/190 remains an explicit legacy profile.
No wire/storage migration, retry changes, GS-150 rewrite or hardware action.

Starting local/remote checkpoint `913b1dedb483ca63aff7244dbbd224053206c7f2`;
approved canonical policy commit `821da80b25dc11c8a01252333abc9734036fc66b`.
Implementation `e36bd88371449421420ec86995e82d3695a680d5` was normally pushed;
actual origin branch HEAD matched local HEAD with tracked cleanliness. GS-40
design/implementation comments10360/10363 and GS-114 candidate comment10368
record the milestones. Final documentation closeout HEAD is recorded in Jira
after its own normal push/verification. Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`. Original untracked S3 managed_components and
original ignored Node asset are preserved; bundle/build directories are generated.

Evidence: [GS-40 software validation](../exec-plans/evidence/R1_GS40_SOFTWARE_VALIDATION_20261010.md),
[paired software metrics](../exec-plans/evidence/R1_GS40_SOFTWARE_METRICS_20261010.csv),
[JSON/build/profile guide](../../code/config/README.md).
Host C++ 1,479, Python 361 with one historical skip, GS-40 model 1,320 / configuration 15,
GS-150 1,481, BAT-C8 72+11, PWA bridge 12 / API 92 / frontend 92 and security/FOTA passed.
ASan/UBSan CPP/model passed. Clean IDF 6.0.3 C3 app 934,192 bytes and S3 app 1,868,800 bytes
pass existing slots; exact paired C3 asset/config fingerprint packaging passes.
Quiet 30 minutes health 15→6, night 8 hours 240→96: 60% fewer standalone health transmissions versus
actual120 baseline. Event identities/effects/retry and recovery latencies unchanged;
physical current/endurance unmeasured. Quick release gate with mandatory Chromium
passes 17 stages (master 49/49, FOTA 34/34). Extended validation-fast exit2 is
retained below. Final `make playwright-gate` exit0: all86 desktop/mobile cases
PASS after exact received-contact boundary fixture correction; the earlier
failed/interrupted runs remain recorded in the evidence.

Expanded regression fixture corrections were TEST_INFRA_ONLY /
VALID_TEST_EXPECTATION_MISMATCH under R1 release gates and GS-D031: missing six
host linker dependencies, current snapshot cap 6,100, persistent journal requirement,
selected authenticated replay-fence/owner evidence and configured coverage timing (including browser boundary assertions).
No storage/security production behavior was changed for these corrections. Historical
25-Node stress is explicitly SKIPPED with ten-slot rejection verified; supported
1/4/10 cases remain checked. Baseline source provenance is in the evidence.

**Remaining software limitation:** extended `validation-fast` still fails historical
`hub-journal-migration-host-test`: `clean migration commits` (line 194), unchanged
storage path/fixture from starting HEAD; baseline execution unverified. Classification
UNRESOLVED / INVESTIGATE_ONLY under deferred legacy storage work. Do not suppress
this failure or change migration ownership/storage contracts under GS-40. Independent
fresh-install, current S3 durability/replay and GS-40 gates are recorded separately.
Secure target trusted-epoch and production cloud-contract limitations remain open;
host backend/PWA validation does not qualify real-target caregiver visibility.

**Next sequential task: GS-116, then GS-130, then GS-114 BAT-C8 P1–P9.** Latest
user GS-40 comment10366 supersedes the earlier immediate-GS-114 plan. GS-116
owns component/contract gates and permanent AGENTS/master validation policy;
GS-130 owns exhaustive feature/test/physical traceability. Their new policy
sections were read and this deliverable reviewed: GS-40 deterministic gates are
registered in validation-fast, but remaining migration failure, full inventory
and release-gate dominance gaps prevent an all-green product release claim.
Do not start those follow-on implementations automatically in this GS-40 task.
GS-114 remains conditional on those audits and separate authorization of
fixture/image preparation and hardware actions. Include matched GS-40/GS-150 images,
startup config SHA/profile map, actual GPIO4/held-HIGH, timer/radio restoration,
NodeHealth 300/910, Hub outage/rejoin without new motion and honest coverage cases.
GS-40 stays In Progress pending its own real-target heartbeat and caregiver offline
visibility acceptance; overlapping evidence may be reused only when traceable.
No protected board flash/reset/erase/re-enrollment is authorized here. GS-149 power
acceptance follows existing GS-144/GS-51 prerequisites; GS-146 full physical/HIL
closure retains all dependencies. GS-126/128 statuses/ranks/dependencies unchanged.

The final committed-source bundle records implementation HEAD `e36bd883`,
tracked_source_dirty=false; C3/S3 image Git metadata is `e36bd88`. Hashes and
package commands are in the evidence. It is a production software candidate,
not a signed/physical-wake-qualified image. Documentation-only closeout preserves
the validated firmware source and existing runtime/storage/wire contracts.

## GS-150 software implementation — 2026-10-10

The user clarified safe best-effort missed-ACK replay and confirmed-outage
alternatives, superseding the prior guaranteed-ACK-latency stop. Production C3
now permits safe light sleep with committed pending events in the existing
confirmed-outage profile after the existing 10 s active-contact receive budget.
A successful application MAC result keeps continuous reception while pending;
it never marks contact authenticated or retires work. Connected/transient
pending reception, original retry/rejoin timing, EventKeys/timestamps, queue
limits and ACK-driven durable retirement remain intact. Rejoin, retirement,
active/idle contact, fallback and ambiguity deadlines bound the same owner
sleep decision. Radio restore failure keeps PIR sensing running and fails awake.

Current implementation/evidence: [battery design](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md),
[GS-150 validation and scenario metrics](../exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md).
GS-150 is SOFTWARE_IMPLEMENTED / HOST_TESTED / SIMULATED / TARGET_COMPILED.
New deterministic gate PASS (1,481 checks / 19 paired workloads); BAT-C8 PASS
(72 C++ / 11 Python); full C++ PASS (1,479); full Python PASS (346 run, one
historical scoped skip); frontend 17/17 and contracts PASS; PWA bridge 12/12,
API/frontend 92 canonical scenarios each PASS. Master runtime 49/49 and FOTA
34/34 PASS after correcting its matching stale rejected-admission sequence
assumption and host-only outbox link recipes. No production sequence change.
Encrypted recovery,
authenticated retirement/rejoin, security/FOTA and Hub persistent dedupe gates
PASS. ASan/UBSan PASS for the new gate and full C++ suite. Clean C3 ESP-IDF
6.0.3 PASS: 933,520-byte image, 53% OTA-slot free. Evidence records all actual
commands and the corrected pre-existing Hub host-test link recipe. No physical
actions, physical current measurement or battery-life claims.

Identical six-minute outage workloads: one/eight pending records reduce owner
loops 18,000→3,189/3,171 and modeled awake time 360,000→63,540/63,180 ms, with
unchanged eight TX opportunities. One modeled sleeping ACK miss needs one
additional same-key replay and preserves one logical effect. Protected rejoin
and auxiliary receive windows add awake time in already sleeping paths; these
costs and model limitations are explicit in the evidence.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting local/remote
`ff0f6f159890b86f26b998ca3d1218600ff34cc8`; the pre-existing untracked S3
`managed_components/` remains preserved. This task is the narrow GS-150 exception
to GS-147; expanded journal/retirement/capacity, deep sleep and C9–C12 remain
excluded. No LOCKED decision/context revision change. Next sequential task is
GS-114 image-matched physical functional P1–P9, requiring separately authorized
fixture/board actions. GS-149 quantitative P10 and GS-146 closure remain open.

### Delivery and sequential handoff

Implementation commit `1262400408e780044d928d84286d9b6f392b9d5a`
was pushed normally to `origin/feature/r1-commercial-baseline` on 2026-10-10;
actual `git ls-remote --heads` equals local HEAD at that checkpoint. Tracked
tree was clean; only the original S3 `managed_components/` was untracked.
This subsequent documentation-only closeout records that verified delivery;
the final closeout HEAD is reported in GS-150 Jira and the session handoff.
No firmware source changed after the validated clean image.

No GS-150 software blocker remains. Read this section, the battery guide,
linked validation/CSV and latest GS-150/GS-114 comments before resuming.
The precise next action is GS-114 fixture/image preparation and separately
authorized P1–P9 qualification, including pending-event outage sleep,
missed-ACK replay, held-HIGH/overnight PIR, radio restore and FOTA/control
entry races. Rebuild the approved qualification profile from the final
checkpoint, record its hash and fixture readiness. Do not use protected
original paired boards or treat this handoff as hardware authorization.
GS-149 P10 current/residency and GS-146 final closure follow their existing
dependencies. GS-147 remains gated; no new scope or security decision needed
to resume GS-150 software.


## Historical GS-150 ACK-boundary blocker, 2026-10-10

Superseded by the current GS-150 software delivery above. The absence of a
guaranteed ACK-arrival maximum remains true; safe missed-ACK replay is now the
approved basis for a conservative implementation.

GS-150 is a user-approved narrow C3 software implementation exception to the
broader GS-147 hold. Source verification reached its explicit stop condition:
there is no source-defined maximum authenticated application Durable-ACK
arrival time. The Node's 1,000 ms timeout covers its local MAC send callback
only; after that callback, `NodeRadio` schedules the existing retry ladder. The
Hub authenticates/processes the Node event, completes the durable runtime step,
then submits the application ACK, but does not publish a maximum arrival bound.
The existing retry deadline cannot create a safe interval to sleep before the
same retry is due. Do not repurpose the MAC timeout or change retry/ACK policy.

**GS150_RESULT=BLOCKED** before production behavior changes. The needed product
input is an approved end-to-end application Durable-ACK listening maximum,
measured from Node MAC callback completion, with a source/build-supported Hub
commit/ACK path bound that leaves time to sleep before the unchanged retry. This
must preserve exact EventKey, authenticated Durable ACK retirement, first-event
and critical-event priority, health/freshness, FOTA/control, GPIO4 and radio
restoration. No firmware behavior changed; no GS-147 queue/journal, protocol,
retry or deep-sleep work was added.

Validation on canonical source HEAD `f245eebcd80c9e43a230ae0ee814f59a37adefd0`:
`make -j2 battery-c8-host-test node-recovery-persistence-host-test
node-retirement-protocol-host-test rejoin-host-test secure-fota-adapter-host-test`
PASS; `make cpp-test` PASS (1,479); `make python-test` PASS (344, one scoped
skip). No source changed, so existing clean C3 ESP-IDF 6.0.3 build evidence
remains applicable. GS-150-specific new behavior tests/simulation and final
candidate build are blocked; no hardware action. Exact source analysis and
validation are recorded in the [battery guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).

Starting local/remote checkpoint: `f245eebcd80c9e43a230ae0ee814f59a37adefd0`
on `feature/r1-commercial-baseline`; pre-existing untracked S3
`managed_components/` preserved. After documenting and commenting this stop,
commit/push the handoff. Next action: approve the ACK receive bound and validate
it against the Hub durable commit and Node existing retry schedule. GS-150
blocks final-candidate GS-114 physical qualification; GS-149 remains pending.

## C3 software-first battery audit — 2026-10-10

At canonical start HEAD `3279294e31345f0ff34d5d97ee456145375eb46a`, the
confirmed Hub-outage/backlog software gap remains: C3 light sleep is inhibited
by outage, every pending TX/ACK and retained event, so the single owner falls
back to a 20 ms poll while the existing retry/rejoin schedules remain much
slower. GS-D027 supports avoiding unnecessary Node wake-ups, but sleep with an
unacknowledged EventKey would stop authenticated ACK reception until radio
restore; the locked requirements do not define an ACK receive-window boundary
or a Hub-power-off recovery target. GS-D025 is only a powered Hub/local-radio
internet outage target. GS-147 remains design-only, blocked by GS-146, and its
expanded journal, offline envelope and ACK/retirement scope are not approved.
No firmware behavior or requirement changed pending that decision.

Read-only scope review and validation: `make battery-c8-host-test` PASS (72
C++ checks / 9 Python invariants); `make cpp-test` PASS (1,479); `make
python-test` PASS (344, one documented skip). Existing C3 ESP-IDF 6.0.3 clean
build evidence (931,424-byte image) remains applicable because no firmware
changed. No hardware actions. Diagnostics limitations, source references,
modeled wake frequency and C9–C12 disposition are in the existing
[battery/power guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).

The 2026-10-10 latest Jira decision splits functional BAT-C8 P1–P9 to GS-114
and quantitative P10 to GS-149; GS-146 requires both. BAT-C12 deep sleep is
explicitly deferred. Next software action is to obtain an approved ACK-window
and Hub-off recovery/service contract before changing offline sleep eligibility;
then add deterministic outage/backlog/rejoin tests and rebuild C3. Preserve the
existing untracked S3 `managed_components/` directory. No branch/worktree
change, hardware work or journal expansion.

## Integrated software regression closure — 2026-10-10

Starting at canonical HEAD `5648d90426fb12b584a009eac0a88e754ad909c6`, the
confirmed C++ and PWA failures are closed with test-only/host-simulator fixes;
no firmware behavior or product requirement changed. `make cpp-test` passes
1,479 checks. `make python-test` passes 344 discovered tests with one explicit
skip: the classic ESP32 NVS capacity/reserve model is historical under GS-D030,
and S3 commercial capacity/reserve remain open. Its current source-bound parser
and raw-profile test pass. The PWA bridge, API scenario catalogue and frontend
suite pass after the host lab drains all bounded CloudSync batches, keeping
later activity and door-close events visible to the backend fixture.

The individual root causes, exact pre/post-fix exits, classifications, source
locations and regression risks are recorded in the [dated integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md).
Focused BAT-C8 (72 C++ checks / 9 Python invariants), S3 durability/security,
replay/reclamation, P2-D HTTP/HTTPS, Node recovery/retirement and commissioning
crypto host gates pass. Firmware source is unchanged, so the existing clean
ESP-IDF 6.0.3 C3/S3 builds and selected ASan/UBSan evidence remain applicable;
no physical, production backend or OTA result is claimed. GitHub DNS was
unavailable at intake; the normal push then succeeded and actual remote HEAD
matched `dfc24d1db88fe6cd0fa7a51232a10f4152a4d5ae`.

**SOFTWARE_REGRESSION_STATUS=PASS_WITH_ONE_SCOPED_SKIP.** This does not close
S3 production backend authentication/receipt/connectivity, capacity/retention,
physical storage/FOTA qualification, or BAT-C8 physical P1–P10. No hardware was
touched. `READY_FOR_GS_114_PHYSICAL=YES`: software gates in this task
pass, but this work does not authorize or start physical qualification.
Jira comments for this closure were added to GS-110/10327, GS-114/10328,
GS-131/10329 and GS-148/10330; no status or rank changed.

## One-time source consolidation — snapshot at initial closeout, 2026-10-10

The user-approved destination is this canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`. Starting local and remote HEAD were `f6e949a79354ebd1a25c55a9b9a9b750bf387dac`; context preflight passed at `2026-10-09.001`. C3 BAT-C8 implementation is already in canonical history through ancestor `808080e`. Reviewed S3 target, P2-A/B/C and partial P2-D code/evidence were selectively cherry-picked with provenance; see [source integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). Integration source checkpoint before final handoff: `1febcf027baea892b95ed3a57615a4a562ee9b82`.

At initial consolidation closeout (the aggregate results are superseded by the regression-closure section above), BAT-C8 focused C++ (72 checks) and nine Python power-policy invariants passed; S3 outbox, segmented runtime, replay/checkpoint, identity, completion, mixed-body and P2-D HTTP/HTTPS suites passed. The P2-D SQLite bridge processed 300 events with no pending records; catch-up measured 26,458 ms in that host fixture. `make cpp-test` failed at `test_node_offline_resilience` expecting `next_sequence()==1001` after 1000 attempts; this same assertion is in the source P2-D evidence. `make python-test` ran 344 tests after the simulator link fix: 341 passed, one failed and two errored in G01/HIL checks (details in the integration manifest). Those historical results are not represented as passes. No Node/BAT-C8 production edit was made. Clean S3 and C3 ESP-IDF 6.0.3 builds passed in isolated `/tmp` build directories; sanitizer outcomes are recorded in the integration manifest. No hardware validation was performed.

**Active next product work remains BAT-C8 physical qualification** (GS-114), plus GS-144 target, GS-140/B0–B4 and matched AFTER measurements, GS-119 residual cases/12-hour soak, and GS-146 closure. No hardware action was taken. GS-115 C9–C12 remains conditional and measurement/decision-only; current boundaries are in [battery power management](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md). GS-147 remains a proposed sleep-first/offline-journal design only, not implementation approval; retain its Hub-off target, retirement/ACK interoperability and capacity requirements as unresolved until the issue contract is approved (audit findings: [C3/GS-147 section](../exec-plans/evidence/R1_CROSS_WORKTREE_REQUIREMENTS_CODE_AUDIT_20261010.md)). S3 GS-148 and parent GS-131 remain intentionally OnHold as a workstream; P2-D remains partial, production deletion disabled, and P2-E/F/Phase 3 gates open. The pre-integration cross-worktree audit is historical for source-absence claims; this manifest and checkpoint supersede those claims.

Cross-component follow-up remains open: production backend authentication/COMMITTED ownership and live Hub-to-backend-to-PWA flows (GS-117/121) are not proven; S3 storage/FOTA interruption and rollback compatibility (GS-118) remains unqualified. The activity/door assertion failures recorded at the initial integration snapshot are closed as a host fixture defect in the updated integration manifest. The P2-D handoff documents missing production contracts and the supported host fixture without representing it as live deployment evidence.

Untracked user files remain at their original worktrees: battery HIL scripts; S3 `sdkconfig` and `managed_components/`; storage `prompt.txt`; and Phase 2 generated build directories. No code from the unpublished 11-commit classic-storage range was merged.

## Initial integration delivery closeout — snapshot before regression follow-up

**CONSOLIDATION_STATUS=PARTIAL.** Commit `ed6cffcdbfcbd69118e41b436ef616a0bea927db` (`Record R1 source consolidation and validation handoff`) is pushed to `origin/feature/r1-commercial-baseline`; at verification, local HEAD and actual GitHub ref both equaled that hash. The tracked worktree is clean; generated untracked S3 `managed_components/` remains preserved.

At this initial integration snapshot, focused BAT-C8, S3 storage/security/recovery, P2-D HTTP/HTTPS and ASan/UBSan checks passed; clean isolated ESP-IDF 6.0.3 C3 and S3 builds passed. The aggregate failure details are historical and are superseded by the regression-closure section above. Production P2-D authentication/receipt/connectivity, canonical workload, live backend E2E, capacity/retention and physical qualification remain open. No hardware actions occurred; production destructive event/identity reclamation remains disabled.

Jira synchronization comments were added and read back successfully, without workflow or ranking changes: GS-110 comment 10321, GS-114 10322, GS-115 10323, GS-131 10324, GS-147 10325, and GS-148 10326. Evidence and source provenance are in the [dated integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). The six-worktree inventory and exact validation details are recorded there.

## Cross-worktree audit handoff — 2026-10-10

The active priority is BAT-C8 physical qualification (GS-114), with GS-144 target, GS-140/B0–B4 and matched AFTER power measurements, GS-119 remaining physical evidence/12-hour soak, and GS-146 C1–C8 closure. Reuse valid battery-branch physical PIR/GPIO4/ACK evidence only when image and setup provenance match. BAT-C8 software/host/build are complete; physical gate remains open. GS-115 stays conditional and To Do.

S3 GS-148/GS-131 are intentionally paused, not cancelled or complete. The reviewed source branch checkpoint is `e1941d7136c43fe6e21f4eff42527aa2d0de9a9a`; P2-D remains partial and production auth/receipt/connectivity/workload acceptance remains open. GS-148 is still In Progress in Jira while its description/comments document the pause; no workflow transition is made here. Production destructive reclamation remains disabled. The [cross-worktree audit](../exec-plans/evidence/R1_CROSS_WORKTREE_REQUIREMENTS_CODE_AUDIT_20261010.md) is preserved as historical triage; current source dispositions are in the [integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). No product decision or context-version change is made here.

**Updated:** 2026-10-10

## Authoritative work line
- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Current P0 product behavior and application-vs-physical evidence boundaries: `docs/product/P0_PRODUCT_REQUIREMENTS.md`.

## Closed / physically qualified

Fresh-install durability path physically proven:
- fresh native ownership/enrollment;
- Node empty-AEAD hardware-AES regression;
- Hub owner stack sizing;
- first durable event commit;
- Hub recovery without watchdog starvation;
- authenticated Node runtime/rejoin;
- Node→Hub transmission;
- ACK class 0 and retirement;
- duplicate ACK safe;
- lost-ACK/reboot/retry duplicate safety;
- final Node retained/in-flight queues empty in lost-ACK qualification.

Do not reopen unless later code/hardware changes can invalidate these gates.

## USB automation

Zero-touch USB automation is convenience tooling, not an R1 product requirement. Keep it out of the critical path while product blockers remain.

## Working-tree reconciliation — 2026-10-07

The previously uncommitted qualified Node empty-AEAD and Hub native durability,
first-commit, stack/recovery, and lost-ACK controls are now committed, along with
their focused tests and existing factory/USB tooling. The canonical storage
contract and GS-D020 Jira traceability are tracked. Existing physical evidence
is preserved unchanged; no hardware test, initialization or flash was repeated.
See [the reconciliation snapshot](../progress/R1_WORKTREE_RECONCILIATION_20261007.md)
for every initial file, commit units, validations and remaining metadata.

Seven focused C++ gates, the production PSA host regression, factory/dispatcher/
profile tests, real Hub ELF checks and USB offline mocks passed. Two optional
initializer-ELF tests were skipped because their artifact is absent. The legacy
`hub-journal-migration-host-test` fails at `clean migration commits` on both the
start commit and reconciled sources; this pre-existing legacy failure is
DEFER_POST_R1 under GS-D001, with no migration fix attempted. `validation-fast`
still includes that target and is not claimed green. Eleven Windows download
metadata streams remain untracked and untouched; no uncommitted implementation
remains. Requirements and context version `2026-10-07.001` are unchanged.

Final lost-ACK source: `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/status.json`.
Selected duplicate record growth is `79 - 78 - 1 independent event = 0`; selected
Node ACK is class=0 retired=1 and final retained=0/in_flight=0. This preserves the
previous physical PASS rather than claiming a new qualification run.

## Current R1 blocker

Hub storage lifetime/data-lifecycle architecture.

The previous fresh-install durability and lost-ACK qualification remains closed. This blocker concerns lifetime behavior after continued household activity; it does not invalidate the already-passed physical proof. Do not spend journal capacity or repeat HIL to investigate the design.

Known requirements:
- current finite append-only journal lifetime is unacceptable;
- reducer/routine state must be durably materialized/bounded;
- exact dedupe retained until retirement semantics safely cover it;
- backend outbox separated logically from local correctness;
- cloud-connected Hub pushes near-real-time;
- PWA reads already-current backend data;
- cloud outage does not stop local safety/routine learning;
- repetitive raw sensor detail can be coalesced;
- new Hub work targets ESP32-S3 N16R8 under GS-D030; preserve prior 4 MiB evidence;
- GS-D025 locks the 72-hour internet-only outage design target; exact retention, supported volume and guaranteed offline capacity remain open.

## Initial storage architecture checkpoint (historical proposal)

Architecture analysis at storage-worktree baseline
`cd8d126ab44689cc9c6ebbbe74e6dce058d4323b` is recorded in
[R1_HUB_STORAGE_DATA_LIFECYCLE.md](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md).
It recommends a **conditional** 384 KiB lifecycle allocation with dual OTA,
not an approved partition change. Those implementation observations describe
the historical classic ESP32 target at that checkpoint. The canonical branch
now includes the selected S3 segmented encrypted outbox, checkpoint/replay
recovery, completion/identity metadata, mixed-segment host reclamation and
partial P2-D HTTP/HTTPS adapters. The 192 simultaneous Node-pending-key bound
still does not by itself bound accumulated ACKed-but-unreported Hub evidence.

S3 production acceptance remains STOP pending product outage/overflow decisions,
bounded retirement progress, reducer/model limits, backend summary/effect
completion, safe rollback/format transition, commercial image/partition fit and
crash/wear proof. Historical classic-target build sizes do not establish the
current S3 commercial OTA margin.
Existing physical qualification and deferred legacy migration classification
are unchanged; no firmware, physical event or new qualification was performed.

Subsequent efficiency phase preserves that architecture as documentation commit
`94fe1a8` and implements **isolated host-only policy-neutral primitives** under
the code project's `host/storage/`, with dedicated tests and benchmarks. No
production target lists or ACK path are changed. The optimized candidate shares
one immutable event across lifecycle owners; existing 128 KiB feasibility is
**CONDITIONAL**, so partition enlargement remains UNDECIDED rather than assumed.
The 128-event production limit describes the historical classic target, not the
integrated S3 segmented outbox. S3 commercial capacity and lifetime guarantees
remain unqualified. One million simulated events
show fixed 192-record storage and allocation-free primitives; existing journal
and backend completion host regressions pass. These are host results, not
physical durability/GC/rollback qualification. See ExecPlan section 20 and its
host evidence for exact byte budgets, benchmark scope and remaining STOP gates.

Complete S3 production storage/data-lifecycle qualification for the GS-D030 Hub and six-Node worst case. The following accepted implementation areas are integrated, but remain subject to product acceptance and physical proof:

1. active correctness journal and dedupe state;
2. materialized routine/reducer state;
3. backend outbox and completion semantics;
4. short local history/cache and safe reclamation;
5. offline capacity and six-Node worst-case event rates;
6. flash wear, crash-safe cleanup reserve and OTA budget.

Do not implement a guessed retention policy or merely increase the 128-event constant. The 72-hour outage design target is LOCKED by GS-D025; exact retention, supported volume, guaranteed offline capacity and partition-layout changes remain open decisions. See `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` and `docs/product/DECISION_LOG.md`.

## BAT-C8

GS-D020 traceability: GS-114 — implementation/focused qualification; GS-146 — final R1 battery closure. Issue completion is not inferred from this mapping.

BAT-C8 is an R1-required feature with physical qualification pending (GS-D020). Physical cases P1–P10 remain NOT_RUN; these are test case IDs, not priority labels. Required production proof covers sleep entry, GPIO/timer wake, bounded resume, sensing/runtime and radio restoration, safe fail-awake behavior, and event-processing regression. Do not block on final battery-life optimization or long-duration endurance absent an explicit R1 battery-life claim. No BAT-C8 tests were run as part of the documentation decision.

## Stop rule

If work does not fix an R1 blocker or implement a locked R1 requirement, strongly consider backlog.

## Storage-first requirement checkpoint — 2026-10-07

Qualified isolated core checkpoint: `45f6b00`; million-event bounded fixture re-run PASS. GS-D021/022/023 now lock storage/retrieval-before-CPU priority and failure-aware routine/daily recovery with NO_ACTIVITY distinct from NO_OBSERVATION. Context revision advances from `2026-10-07.001` to `2026-10-07.002`. No production integration or partition approval. Existing primitive evidence does not prove daily finalization, retirement progress, AEAD GC or rollback. Current 128 KiB feasibility remains CONDITIONAL pending those proofs and product/backend limits.

At the GS-D021/022/023 checkpoint, the designated canonical branch still had `.001`; that storage-worktree requirement commit required review/promotion by an explicitly authorized canonical-source action. The density run subsequently started with local/canonical `.002` PASS. Do not silently synchronize worktrees or bypass the context guard. Next step: align approved canonical context, then implement policy-neutral failure models and close time/coverage, backend aggregate revisions, retirement-credit and COW recovery proofs before production work.

Refinement design is in ExecPlan section21: one shared immutable body, conditional derived-nonce84/104-byte records, coverage-aware320-byte daily aggregates,6,144-byte checkpoint candidate, exact128 KiB reservation arithmetic and Node/Hub/backend/day/reclaim failure matrices. No final record size or retention promise is approved. Conservative normal incremental detail capacity is76 records (4.75 hours at384/day);72-hour comparison needs249,856 bytes under the stated worst-record independent-reserve allocation, not a new requirement. Critical reserve8,192 protects one bounded32-record burst only; it does not solve indefinite critical saturation. The finite384 exact-key induction requires persisted admission credits/report progress; production bound remains unproven.

Unchanged core million-event and ASan/UBSan checks, journal/full129 recovery and backend completion regressions, and24 retirement-model tests pass; static byte arithmetic/relative paths and diff checks pass. New coverage/day/reclaim failure models are specified but not implemented: canonical requirement commit must precede dependent implementation, and the new local version must pass the context guard against the designated canonical source first. No hardware result, production integration, CSV change, BAT-C8 or Jira action.

Current no-HIL Hub target build now PASS after explicit C3 artifact build: actual Hub.bin1,864,624 B; current1,966,080-byte slots leave101,456 B. Static DRAM45,783 B/IRAM87,359 B are linker figures, not runtime heap margins. The old384 KiB candidate fails image fit by29,616 B;256 KiB leaves only35,920 B before future code/reserve. No partition resize approved. Build/test provenance: [refinement evidence](../exec-plans/evidence/R1_STORAGE_FIRST_REFINEMENT_20261007.md).

## Storage-density closeout — current handoff, 2026-10-07

Host-only codec/tests/benchmark/evidence commit: `74c4b99`. Initial resume
preflight PASS at local/canonical2026-10-07.002. Existing files and all evidence
were preserved; no expensive passed tests were repeated. Final density
million-event PASS (peak192 keys, fixed storage/RAM, portable hot new0),
ASan/UBSan terminal PASS and current storage/backend/journal regressions
are preserved. Sanitizer exit-status session handle was lost on interruption;
its completed temporary output is byte-identical to the tracked PASS log.
No LeakSanitizer or physical result is claimed.81-field inventory and
static budgets/links/diff checks passed; CSV cells were preserved during
line-ending normalization. Only the missing fast one-day size comparison
was completed with the unchanged codec.

[ExecPlan sections22.10/22.11](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
and [density evidence](https://github.com/udaybhan200683/Ghar_sajag/blob/2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8/docs/exec-plans/evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md)
supersede earlier density recommendations for current planning while
preserving historical/numeric-only comparisons. Full self-contained identity
and config context costs728 B sample /1370 B maximum per independently
restartable4 KiB sector; serializers/security integration are PROPOSED.
Timing-variation median body13/HOT36/WARM15–16 B excludes shared header/tail;
maxima raw101/HOT124/WARM103 B. Conditional fixed100 KiB +variable28 KiB
reservation fits the existing partition arithmetically, not by allocator proof.

Full-source timing-variation retention: NORMAL1281 sample /1056 max-name
records (80.0625/66 hours), HIGH1347/1103, STRESS1457/1181. Synthetic72h
NORMAL plus daily/fixed reserve requires131072 B sample (zero spare),
135168 B maximum (4096 deficit).128 KiB remains CONDITIONAL; no approved
72-hour guarantee or proven partition enlargement requirement. The conservative
prior76-record result and narrower uniform-numeric1595 result use different
representations/reservations and are not production guarantees. Current
1864624-byte image and101456-byte OTA margin remain prior build evidence.

GS-D024 now locks redundancy elimination and compact bounded context/restart
evaluation before storage enlargement. Context advances.002 ->.003, separately
from host work. Designated canonical remains.002; final preflight is expected
STALE and all substantive work must STOP then. No automatic synchronization
or promotion. Next step is explicitly authorized canonical review/promotion
and preflight PASS, followed by policy-neutral authenticated allocator/root/
nonce/reclaim and full dictionary/config recovery proofs. Also close retirement
credit/report bound, exact witness retry projection, offline/saturation policy,
backend daily/effect/revision/substitution, coverage/trusted-time/day recovery,
rollback and target RAM/wear/OTA growth before production integration.

Production integration NO; partition CSV/ACK/backend/PWA unchanged; hardware
unused; BAT-C8/Jira untouched. Existing physical fresh-install gates stay closed.

## Product governance preparation and canonical promotion — 2026-10-08

Storage-worktree preparation (historical checkpoint) at starting HEAD
`d8631e656bd37f05294853de40cec93d65f0cec6`, storage branch
`feature/r1-hub-storage-lifecycle`. Initial preflight PASS and context
`2026-10-07.003`; only user-owned untracked `prompt.txt` was present.

GS-D025–028 now LOCK the approved 72-hour internet-only outage design target,
loss-aware eligible ordinary-motion aggregation, battery-first ESP32-C3 Node
processing and PIR/door/future-bed boundaries. GS-D013/017 are only partially
superseded for these approved directions; their numerical/protocol decisions
remain OPEN. Context advances to `2026-10-08.001`. This preparation does not
authorize production integration or claim capacity/battery qualification.
Existing host evidence is preserved; simulations, hardware and release gates
were not repeated. No production, partition, BAT-C8 or hardware scope changes.

OPEN: critical-event classification/reserve, NORMAL/HIGH/STRESS guaranteed
volumes, critical saturation behavior, quiet gap, progress frequency, final
backend summary protocol and final NVS size. The 4 MB ESP32 Hub remains baseline.
New Node protocol work must prove battery and correctness impact before
implementation; no 40–120-second periodic consolidation wake-ups are approved.
BAT-C8 physical qualification remains pending, with its requirements unchanged.

**Authorized canonical promotion:** promote only the reviewed governance edits
from source commit `4732679aabbe354bb6c771a4b8ac81437d8c45c5` to
`/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`,
starting clean at `5dcd2f7c10682bd1f6801821deaff20ad4a803e4` and context
`2026-10-07.003`. Canonical context becomes `2026-10-08.001`, matching storage.
The promoted scope is exactly these eight governance files:

- `docs/product/DECISION_LOG.md`
- `docs/product/R1_RELEASE_CONTRACT.md`
- `docs/product/R1_WORK_STATE.md`
- `docs/product/P0_PRODUCT_REQUIREMENTS.md`
- `docs/product/CANONICAL_REQUIREMENTS_INDEX.md`
- `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md`
- `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`
- `docs/product/CONTEXT_VERSION`


Existing canonical content is preserved. Storage-only technical checkpoint
notes, ExecPlan section29, prototype code, tests and evidence files are excluded.
The source branch and user-owned untracked `prompt.txt` remain unchanged.
Validate both worktrees with the existing preflight, commit canonical governance,
and push only the canonical branch to the verified origin using a fast-forward
update. Do not weaken the guard. No capacity/battery/hardware qualification or
production implementation is implied; subsequent work requires a separate task.

## Current security-scope governance — GS-D029, 2026-10-08

Product-owner approval locks ordinary power-failure/interrupted-flash crash consistency,
detected-corruption/missing/inconsistent-state fail-closed recovery, and no silent
stale/uncertain routine state. Ownership, durable-before-ACK, retry/deduplication,
retirement credits and protected dependencies are preserved.

Deliberate restoration of an otherwise valid older flash image is outside R1's
data-freshness detection guarantee; AES-GCM is not malicious full-flash rollback
protection. Automatic signed FOTA APPLICATION rollback through ESP-IDF remains
MANDATORY, including firmware validation and compatibility with storage created
by an unsuccessful upgrade. Data rollback exclusion does not waive application
rollback or permit silent erase/reset/stale recovery.

Context advances2026-10-08.001 ->2026-10-08.002. This task explicitly authorizes
reviewed promotion of only these new governance edits into canonical; independent
worktree history is preserved. No storage experiment, code, test, evidence or
ExecPlan is promoted. Previous governance preparation/promotion notes above are
historical checkpoints. Both worktrees must PASS preflight at the new version
before implementation; no guard bypass or new qualification is claimed.

The deliberate older-image replay limitation no longer establishes an R1 requirement
for an independent malicious-data-rollback anchor. Stronger historical host-authority
assumptions remain valid in their stated proof scope. Ordinary power-failure/corruption
freshness, production mapping and FOTA/storage compatibility still require evidence;
this approval does not declare those implementation gates or Gate C passed.

**Next:** resume Gate C protected NVS admission and progress implementation, retaining
ordinary crash/corruption and dependency regressions. Protected reserve/progress,
supported event volumes, critical saturation and the 72-hour capacity guarantee
remain OPEN. No new security hardware, ESP32-S3 or partition change; existing 4 MB
Hub/ESP32-C3 baseline and BAT-C8 requirements/pending qualification remain unchanged.

## Current Hub development direction — GS-D030

Context2026-10-09.001 records the explicit S3 N16R8 selection. By the user-approved
one-time consolidation on 2026-10-10, reviewed S3 source/evidence is integrated
into this canonical worktree and `feature/r1-commercial-baseline`; see the
[source integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md).
The former S3 worktree and storage branch are preserved as provenance; do not
resume development there. No experimental storage lifecycle code or unapproved
capacity policy was promoted.

The 4 MiB classic Hub is retired from active development, not deleted. Existing
physical PASS results remain valid only for their original hardware/configuration.
S3 target/PSRAM/ESP-NOW/FOTA/heap-stack/recovery qualification is pending.
Initial bring-up must identify and preserve existing device firmware/data before
writing flash. Commercial partitions, sustainable storage reclamation, supported
72-hour volume, critical saturation and R1 end-to-end qualification remain open.
Do not resume classic-ESP32 footprint/capacity optimization or change C3/BAT-C8.

### S3 bring-up checkpoint — 2026-10-09

[S3 evidence](../exec-plans/evidence/R1_S3_HUB_BRINGUP_20261009.md) records
GS-D030 governance, direct reuse of the existing Hub composition and unchanged
C3 asset, successful ESP-IDF6.0.3 S3 builds and a physical diagnostic PASS at
that historical checkpoint. No physical tests were performed during the
2026-10-10 consolidation.
Actual board: ESP32-S3rev0.2,16 MiB flash,8 MiB Octal PSRAM40 MHz; startup/scratch
memory, Wi-Fi and ESP-NOW init and six10-second heartbeats pass. Full private
flash backup verified before writing; original NVS/VFS digests still match.
Final Hub composition1791792 B; development dual4 MiB OTA slots/2 MiB journal
leave2402512 B current unsigned-image margin per slot. The product image was
not flashed. Module/PCB GPIO mapping, provisioning/C3 application interchange,
storage/reclaim/72-hour volume, signed FOTA/rollback and full runtime remain
unqualified; diagnostic heap values do not qualify product peak memory.
Existing host1479 checks, fresh-install, FOTA guard and retirement pass.
Canonical receives governance only; storage worktree/history and C3/BAT-C8 remain
unchanged. No commercial partition/retention decision or new R1 qualification.
Next bring up one authenticated S3-Hub/C3 pair and prove durable ACK/retry/reboot.

## GS-114 Part 1 HIL source audit — 2026-10-11

Source/compatibility audit is complete at `6d0318f644a400caa1f35d9bd0eb4dc9fcb0830b`.
No serial port was opened and no board command was sent. Read-only USB
enumeration was unavailable (`lsusb` is not installed and
`/dev/serial/by-id` is absent), so connected hardware, ports, identities,
firmware, and image hashes are unverified. The existing HIL supervisor remains
incompatible with the selected S3 N16R8 target and has flash/reset/logical-state/
motion-injection paths; the S3 target explicitly rejects legacy HIL controls.
The detailed old-ESP32→S3 compatibility matrix and safe execution boundary are
in [GS-114 Part 1 audit](../hw/evidence/GS114_PART1_HIL_AUDIT_20261011.md),
with the historical HIL document applicability notice in
[HIL automation](../validation/HIL_AUTOMATION.md).

**Status: Part 1 hardware tests NOT_RUN / BLOCKED pending named fixture and
explicit approval.** Before any port open or device interaction, obtain the
five confirmations listed in the evidence record. No production source behavior
changed. Preserve paired-device data and existing authenticated state. After
approval, implement/verify a genuinely non-resetting observation path and an
S3-aware identity/evidence adapter before running only the approved
observational cases. GS-114 Part 2 physical PIR tests remain separate.

## GS-114 authorized clean-fixture checkpoint — 2026-10-11

After explicit user authorization, exact stable USB links and user-designated
ports were checked. esptool confirmed `/dev/ttyACM1` is the dedicated C3
(`14:63:93:c5:d1:58`, 4 MB) and `/dev/ttyACM0` is the dedicated S3
(`7c:4f:ad:b7:2a:20`, 16 MB, 8 MB PSRAM); Secure Boot and flash encryption are
disabled. Fresh matching ESP-IDF 6.0.3 C3/S3 production-profile images and GS-40
configuration bundle built and their image headers, hashes, and partition
tables were verified. No erase/write occurred. The setup stopped before erase
because current R1 commissioning requires an exact authorized `ExpectedNode`
and installer code, but kit provisioning/external authorization is incomplete
and the S3 target lacks the legacy HIL commissioning control. No credentials or
protocol were invented. Detailed source/image evidence, per-test status, RTS
reset disclosure, and the precise prerequisite are in [the clean-fixture
checkpoint](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md). Latest Jira
comment records this blocker and required resume action. GS-114 Part 1 A01 has
identity evidence only; A02–A08 remain blocked/not run as listed. No erase/write
occurred, but the dedicated Node's pending-event contents and post-probe runtime
state were not inspected. No Part 2 motion test.
## GS-114 fixture commissioning and focused Part 1 result — 2026-10-11

User-approved, S3-only `GS_HIL_COMMISSIONING` adapter reuses the existing
HubSecurityLink commissioning owner and cryptographic protocol. It is opt-in
and disabled by default; broad S3 HIL-control rejection remains. The disposable
pair was clean-installed after exact C3/S3 identity checks. Fresh association,
authenticated rejoin, C3 software-restart rejoin, and a subsequent authenticated
NodeHealth from the same Node after the S3 app restart were observed. The
five-minute authenticated health cadence and timer-wake counters were captured
without PIR stimulus. Detailed image hashes, logs, machine-readable outcomes,
limitations and validation reports are in
[GS-114 Part 1 fixture evidence](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md).

`make validation-node` and `make validation-contract` PASS. `make validation-hub`
remains FAIL (exit 2) solely at the known GS-148
`hub-journal-migration-host-test` assertion `clean migration commits`; all
other registered Hub stages passed. Do not suppress or relabel it. The focused
adapter parser/isolation tests and existing commissioning crypto, rejoin,
association and fresh-install checks pass. Production-profile C3/S3 target
build outcome is recorded in the evidence after completion.

Physical outcomes are bounded: HIL-A01/A02/A03/A06 PASS within the stated
scope, A07 PASS for reported timer wakes only, A04/A05 NOT_RUN, A08 BLOCKED.
No genuine PIR exercise, event Durable ACK, outage threshold, FOTA, RF fault,
current measurement, broad HIL or release gate was performed. GS-114 P1–P9
physical qualification remains open; Part 2 PIR and battery qualification are
not started. The fixture adapter is not GS-109 product commissioning and uses
unprotected development identity material; never ship or use it on protected
or production devices.

Current work remains on `feature/r1-commercial-baseline`, originally at
`73e1e842ff843a696d592bd7c2004b72a512082c`; source, tests and documentation
are pending focused final validation and commit. Existing untracked S3
`managed_components/` is preserved. Next: finish the ESP-IDF 6.0.3 production
profile builds, run preflight/diff checks, commit and push, verify remote HEAD,
then use the already installed disposable pair only for separately approved
GS-114 Part 2 physical PIR qualification.

## GS-148 P2-D CloudSync/API implementation checkpoint — 2026-10-11

**Scope:** User-approved P2-D only. GS-148 P2-E/P2-F, physical Phase 3, GS-114,
hardware, destructive event reclamation and release campaigns remain on hold.
Starting canonical local and origin HEAD: `2b1c15c97a917521c142db1b3973382274c306ff`.
Context preflight PASS (`2026-10-10.001`).

The original P0 failure was reproduced: an unchanged CloudSync EventKey request
reached `JsonApi` with `durable_events=None` and returned its intended
fail-closed `503 durable_event_store_unavailable`. The P0 harness had never
composed the existing file-backed `DurableEventCommit`; this was not a commit
transaction failure or an authorization rejection. The default `http_api.main`
remains the documented development adapter.

Added `backend/ghar_sajag/durable_api.py` as an explicit file-backed composition
of existing migrations, FULL-sync SQLite, `DurableEventCommit`, and
`SQLiteEventMap` caregiver event queries. It requires an externally supplied
authorizer and does not itself authenticate clients. P0 passes the exact
production-shaped CloudSync request through this real API/store, using only an
ephemeral loopback fixture authenticator. The committed exact EventKey is
queryable in Chromium after backend reopen. Positive/negative tests cover
commit-before-receipt, exact retry/restart, conflict, missing/wrong principal,
Home, fixture generation, physical/logical identity, storage failure, timestamp
and payload preservation. The P2-D bridge runs production C++ CloudSync/receipt
code against the real API transaction for 300 events.

**Validation:** latest `make validation-p0-e2e` ran 25/25 scenario assertions
and one Chromium test PASS; its stage command exited 0 but the complete-product
adjudicator and outer make gate FAIL because `product_status=PARTIAL`. P2-D
bridge: 300/300 committed/completed, 3 restarts, 0 pending. Focused API/P2-D
host regressions PASS. `make feature-coverage-test` PASS: 149 feature rows,
201 source modules, 14 physical cases and 19 framework integrity tests. See
[P2-D evidence](../exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md)
and report
`code/evidence/validation_framework/p0-e2e-1791733150540893734/report.json`.
No firmware changed; no target build/sanitizer was necessary. No hardware
operation occurred. The historical GS-148 journal-migration assertion FAIL is
preserved and was not rerun.

**Still blocked:** no production Hub credential provisioning/verification is
connected. Hub HTTPS verifies the server CA/hostname and sends an injected
`Authorization` value, while backend trusted middleware is absent. Current API
and schema do not provide the production Hub/Home/Node enrollment-generation
lookup or revocation lifecycle; the Hub request/receipt do not carry generation
fields. File-backed SQLite composition is host validation and not a deployed
PostgreSQL service or complete persistent backend. Do not invent a bearer
credential policy, auth principal contract, generation storage, or wire/schema
change. Exact next prerequisite: approve/document the trusted Hub principal
source, ownership and enrollment-generation binding/revocation source, and
production durable-store deployment adapter; then wire those existing approved
contracts and rerun the P0 E2E. P2-D remains PARTIAL; full P0 and release remain
NOT_APPROVED. Preserve any required GS-130 blocker disposition.

Uncommitted intended changes are limited to P2-D composition/tests, P0 scenario
registration and related validation evidence. Existing unrelated S3
`managed_components/`, GS-114 attempts and redacted logs remain untracked and
preserved. No branch/worktree/history operation or hardware access was made.

## GS-148 P2-D production trust contract checkpoint — 2026-10-11

Scope resumed under GS-148 comment 10444 / GS-109 comment 10445 only. Starting
local and origin HEAD: `18e542873ceec568f70a9358bae6845e39992a54`; preflight
PASS (`2026-10-10.001`). No production firmware/backend security behavior or
wire/storage format changed. Only P0/CloudSync regression tests, scenario
registration, validation traceability and documentation changed. Untracked S3
`managed_components/`, GS-114 attempt directories and redacted fixture logs are
preserved; no physical device was accessed.

The fail-closed API composition/transaction seam is testable and the previous
503 was a harness omission, but the requested production authorization is not
implementable under current approved contracts: no registered Hub principal
issuer/verification and Home ownership authority, no backend Node-generation /
revocation source, no defined retained-old-generation disposition, no approved
receipt-authentication semantics beyond exact EventKey over verified TLS, and
no deployed trusted middleware/database composition or active target CloudSync
caller. The local Hub's persisted commissioning generation is not carried in
the canonical CloudSync body. See the open security-contract entry in
`DECISION_LOG.md` and the 2026-10-11 section of the existing GS-148 P2-D
evidence. This is an explicit `REQUIREMENT_GAP`, not a production defect to
patch by inventing credentials or protocol fields.

Focused evidence: `make p2d-cloud-contract-host-test` PASS (15 invalid receipt
modes and two completion interruption modes); focused durable API/commit/P2-D
Python suite PASS (9 tests; 300/300 deterministic local fixture completions,
three restarts); P0 revocation seam scenario PASS (1/1); P0 scenario registry
integrity PASS (17 use cases/26 scenarios); HTTPS channel host test PASS (8
modes). `make validation-p0-e2e` ran 26/26 scenario assertions and one Chromium
test but exits 2 because complete-product status remains PARTIAL. Report:
`code/evidence/validation_framework/p0-e2e-1791734099302365499/report.json`;
source fingerprint `06487176039b60ddee4c368b72eea5b53c1616bfcd3987e285960c0ce94dd571`.
The historical `hub-journal-migration-host-test` failure remains separately
mandatory and unchanged; it was not rerun. Full P0/release is not approved;
physical HIL is NOT_RUN.

**Next action:** obtain one approved GS-109/GS-148 shared trust contract naming
the Hub credential authority and lifecycle, Hub↔Home registry, Node
generation/revocation source and pending-event behavior on replacement, exact
COMMITTED receipt trust semantics, and production middleware/durable-store
composition. Then implement only that approved slice and rerun focused P2-D/P0
tests. Do not start P2-E/P2-F, hardware/HIL or release-gate-final.

## GS-148 P2-D ownership registry and original-generation provenance — 2026-10-11

Implementation continuation from `ac70f82431c51cc9f7d2975cbc0d04dda4aecb1a`
adds a persistent backend Hub/Home ownership registry, installation-epoch
fencing, Node enrollment generation/revocation history, and a fail-closed
CloudSync authorization guard inside the same durable commit transaction.
Transfer start fences old epochs; transfer completion intentionally remains
blocked until old-Home journal disposition and secure local rebind/reset are
approved. Replaced-generation events cannot be newly admitted; only an exact
already-committed EventKey with matching payload and provenance may replay
under the same active Hub/Home epoch.

S3 CloudSync now has a version-2 host-tested request path that obtains the
original Node enrollment generation from persistent authenticated owner
evidence bound to the event. It reproduces the same request after restart and
fails closed when the evidence is absent. The version-1 compatibility path
remains. No active S3 CloudSync worker calls this path today.

Focused ownership/lifecycle tests pass (6/6), C++ runtime checkpoint and Hub
backend-commit tests pass, P0 scenario registration passes (17 use cases / 30
scenarios), and feature-mapping integrity passes (19 checks; 150 features,
204 source modules, 14 physical cases). `make validation-hub` is FAIL (exit 1,
403.934 s; 34/36 stages PASS) because the historical
`hub-journal-migration-host-test` fails at `clean migration commits` (exit 2)
and the required P0 product status is PARTIAL. `make validation-contract` is
FAIL (exit 1, 264.616 s) at that same P0 PARTIAL status. `make validation-backend`
with the registered command-line receipt reuse is FAIL (exit 1, 147.696 s):
439 Python tests completed with 1 allowed skip and the registered API/frontend
stages passed, but its required P0 product stage remains PARTIAL. After the
final backend-only single-active-Node uniqueness constraint, current
`make python-test` passed 440 tests with one allowed skip in 37.572 s and the
registered ownership stage passed 6/6. Failures remain visible and are not
treated as successful product qualification.
The official clean ESP-IDF 6.0.3 `GS_HIL_BUILD=OFF` C3/S3 target build and
image-capacity/package check passed: C3 934,192 bytes (1,966,080-byte OTA slot)
and S3 1,868,880 bytes (4,194,304-byte OTA slot). Image hashes and build report
are in the linked P2-D evidence record. The build fingerprint preceded the
final backend-only active-Node uniqueness index and test addition; no
Hub/C3/S3 firmware source changed after that build.

The focused Hub runtime checkpoint and backend-commit tests also passed under
ASan/UBSan using the documented `CXXFLAGS` sanitizer profile. After adding the
single-active-Node binding constraint, its conflict test, scenario registration
and GS-116 required marker, the ownership stage passed (6/6), and
`make validation-p0-e2e` reran against source fingerprint
`6af24081bcc769bd73c61cfb498dfa27e6308e63dbb47931ef207ad7cbc49729`. It
completed in 42.025 seconds, executed all 26 full-P0 scenario assertions and
one Chromium test, then exited 2 because product status remains PARTIAL. Current
report: `evidence/validation_framework/p0-e2e-1791742316138312319/report.json`.
The focused P0 registry checker reports 30 registered scenarios; three
ownership scenarios are separately executed by the registered component test.

The registry accepts verified-identity and authorized-operation capability
objects from its caller; this code does not itself verify credentials, issue
them, authenticate the caregiver/installer, or establish production
middleware/deployment. Those trust boundaries remain `BLOCKED` by the open
technical mechanism decisions in `DECISION_LOG.md`. SQLite and lifecycle
behavior are host-tested, not deployed/authenticated production trust. The
previously untracked S3 component directory and GS-114 evidence are preserved;
no hardware or stored device data was touched. Full release is
`NOT_APPROVED`; physical HIL is `NOT_RUN`.

See the implementation and validation record in
`docs/exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md`. After final
target-build and remote verification, the next prerequisite is one approved
GS-109/GS-148 technical trust contract for production Hub credential authority,
authorized claim middleware, enrollment/revocation provenance and retained
old-generation event disposition. Do not start P2-E/P2-F, HIL or release-gate.

### GS-148 P2-D final implementation checkpoint — 2026-10-11

This same-worktree continuation implements the approved Hub/Home ownership
policy and original Node-generation provenance at fail-closed backend/Hub
seams. Backend SQLite now records permanent Hub identity/key fingerprint,
one active Home binding, ownership epoch/history, globally monotonic Node
generation history and revocation. The authorization guard runs inside the
durable EventKey commit transaction and stores Hub/epoch/generation provenance.
Hub CloudSync has a host-tested v2 serializer that reads the original
generation from persisted authenticated per-event owner evidence; v1 remains
for compatibility. A single physical Node cannot have active enrollment rows
under two Hubs/Homes. Re-home after explicit revocation requires a strictly
higher generation; the old Home's event stays there and an old generation can
only retry its exact matching previously committed key.

The transition model safely starts and fences a transfer, but cannot complete
it while retained old-Home journal data disposition and local association/key
rebind remain undecided. Capability objects used by the policy are inputs from
a future trusted adapter; their type names do not prove identity or authorization.
No production issuer/verifier, caregiver/installer authorization, deployed
trusted API middleware/database, active S3 CloudSync worker or generation
allocation authority is configured. The existing protected local P256 key is
not asserted to be a cloud credential. TLS plus exact EventKey COMMITTED
remains the implementation's response check; whether production needs a
separately signed owner/generation-bound receipt remains open.

**Final focused evidence** (working-source fingerprint
`dc8e0f8bc91cfcaab9a600e9904e124e5cd64162843b15d29ca1eb9709e9e517`, base
HEAD `ac70f82431c51cc9f7d2975cbc0d04dda4aecb1a`): ownership lifecycle stage
6/6 PASS; full Python suite 440 PASS / 1 allowed skip; feature traceability
integrity 19/19 PASS (150 features, 204 modules, 14 physical cases); P0
registry 17 use cases / 30 scenarios / 30 executable mappings PASS. Latest
P0 run executes 26/26 assertions and one Chromium test successfully, but
`make validation-p0-e2e` exits 2 because product status is PARTIAL; report is
`p0-e2e-1791742681161360468/report.json`. Full Hub/contract/backend reports
remain as earlier recorded; the Hub report includes the mandatory historical
`hub-journal-migration-host-test` failure (`clean migration commits`). That
failure is still FAIL and was not suppressed. Clean ESP-IDF 6.0.3 C3/S3 builds
and targeted ASan/UBSan evidence remain applicable to unchanged firmware
sources, but their earlier aggregate source fingerprint predates the final
backend-only generation constraint.

P0/production trust remains PARTIAL/BLOCKED; product release is
`NOT_APPROVED`; physical HIL is `NOT_RUN`. No hardware, live cloud, production
credential or stored device data was used. No workflow/status/rank/dependency,
locked requirement, storage format or context version changed. Existing S3
`managed_components/` and GS-114 untracked/redacted evidence are preserved.

**Delivery verified:** implementation commit
`1860ebe5d675c8593290bef904a9409004c01681` was pushed to
`origin/feature/r1-commercial-baseline`; local and remote matched. Jira evidence
comments were added to GS-148/GS-109/GS-130 as 10453/10454/10455. This work-state
delivery pointer is included in the final closeout documentation commit.

**Next dependency:** before production trust can be completed, GS-109/GS-148
must identify the Hub credential issuer and key lifecycle, caregiver/installer
claim authority, trusted runtime middleware/database composition,
Node-generation allocation authority, exact COMMITTED receipt trust contract,
and pending old-Home event disposition. GS-109 still owns full Add Device;
GS-148 P2-E/P2-F and physical qualification remain on hold. Product P0 remains
PARTIAL/FAIL, the historical journal migration gate remains FAIL, physical HIL
is NOT_RUN, and release is NOT_APPROVED.

## GS-152 isolated repository restructuring — 2026-10-11

GS-152 is active only on the isolated worktree
`/home/udaybhan/projects/Ghar_sajag_r1_gs152`, branch
`feature/r1-gs152-repository-refactor`, based on canonical source HEAD
`09bc8cd8b7baab0674bbe03157b7b50bab28e51e`. No canonical files, GS-114
fixtures, boards, USB devices or serial ports were changed or accessed.

The active version-stamped source wrapper has been moved to the stable `code/`
layout. Node, Hub, common firmware, backend, frontend, tests, validation and tools
are grouped by responsibility; ESP-IDF target roots remain in place. See
[GS-152 repository layout](../architecture/GS152_STABLE_REPOSITORY_LAYOUT.md)
and [GS-152 baseline evidence](../exec-plans/evidence/GS152_RESTRUCTURE_BASELINE_20261011.md).
The 499-entry source move map records pre-move SHA-256 for tracked files.

Before/after results and baseline failures are recorded in the evidence document.
Baseline `validation-node`, `validation-hub` and `validation-contract` exited 2
before relocation due to four existing NodeHealth-config simulator setup errors
and a missing Playwright dependency; Hub also retained the known
`hub-journal-migration-host-test` assertion failure. The migration test remains
mandatory and must not be suppressed. Post-migration verification is in progress;
this isolated branch is not canonical delivery or release qualification.

### GS-152 resumption checkpoint — 2026-10-12

Post-migration verification is complete on the isolated worktree. The 499-entry
move map has 499/499 baseline hashes verified, 499/499 destinations present,
374 byte-identical files and 125 path/build/documentation adaptations. The
active version-named source wrapper is absent. The archived release manifest
matches its baseline SHA-256 exactly; the prior `UNCHANGED=0` diagnostic was
consistent with the successful `git diff --quiet` return code and did not
indicate an edit.

The corrected `python3 scripts/build_validation_targets.py` workflow passed
end-to-end under ESP-IDF 6.0.3 with `GS_HIL_BUILD=OFF`, building and packaging
the C3 and S3 images from one source fingerprint. The separate report and image
hashes are in [GS-152 migration evidence](../exec-plans/evidence/GS152_RESTRUCTURE_BASELINE_20261011.md).
`make validation-sanitize` passed the C++ 1,479-check and GS-40 1,320-check
ASan/UBSan runs. Host, app, configuration, traceability, board-stack, HIL
tooling and framework checks passed as itemized there.

The Node/Hub/contract/backend/PWA aggregate reports retain their correct FAIL
status because the production P0 product outcome is still `PARTIAL`; Hub also
retains the pre-existing GS-148 `clean migration commits` assertion failure.
No GS-152 regression was found. Release gate execution and physical HIL remain
NOT_RUN. No serial port or device was accessed. The canonical GS-114 worktree
and its fixture data remain unchanged; the pre-existing untracked S3
`managed_components/` and redacted evidence are preserved.

Source layout, reference migration and validation evidence are ready for
integration review only. This GS-152 worktree remains separate from canonical
R1; its final commit, isolated-branch push and exact remote HEAD are recorded
in the GS-152 Jira delivery comment after Git verification. GS-114 hardware
qualification remains untouched and must resume only when its operator
availability and fixture requirements are satisfied.
