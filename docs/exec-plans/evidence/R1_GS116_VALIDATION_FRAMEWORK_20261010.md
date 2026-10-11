# GS-116 validation framework execution — 2026-10-10

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; actual starting local/remote HEAD
`7b93dea9561ec4f0301ecd77a7b578bee8a1c36a`. Preflight PASS2026-10-10.001;
tracked clean; original S3 managed_components and ignored assets preserved.
GS-116/130 latest approved descriptions/comments10364/10365 and GS-40/114/150
handoffs read. Historical alternate-worktree instructions are superseded.

## Migration diagnosis before implementation

`make hub-journal-migration-host-test`: exit2 (child1), rebuilt current executable,
assertion `clean migration commits`, tests/cpp/hub_journal_migration_validation.cpp:194.
Independent O0/debug rebuild reproduces. Temporary read-only `git archive` snapshot
of pre-GS-40 `913b1dedb483ca63aff7244dbbd224053206c7f2` compiled all production
sources and the unchanged fixture with OpenSSL: child exit1, same assertion,
49.36seconds including compile. No Git worktree/branch/checkout/synchronization.
Snapshot/logs: `/var/tmp/gs116-baseline-readonly-_dbmg4pw`,
`/var/tmp/gs116-migration-baseline.log`; current/debug/GDB logs share gs116 prefix.

GDB breakpoint durable_transition.cpp:743 confirms checkpoint generation2,
registry_owner_domain=false; candidate registry_owner_domain=true, enrollment
slot0/generation1. Legacy bootstrap initializes the old domain; current importer
durable_journal_slot_store.cpp:192–199 submits a registry-domain event. The guard
at durable_transition.cpp:741–743 correctly refuses that domain change, returns
NotCommitted, and the migration stops before erasing legacy source records.
No process order, filesystem fixture state or GS-40 policy dependency is required.

Classification **HISTORICAL_BASELINE_DEFECT**: incompatible legacy migration path,
not validation wiring or an accepted PASS. GS-D001 defers arbitrary development-era
migration; GS-D029 preserves fail-closed ownership/recovery. Existing storage owner
GS-148 (paused production lifecycle work) receives this technical handoff; no new
issue/status change. GS-126 is battery runtime control, not this storage owner.
Do not invent a registry migration contract or rewrite durability under GS-116.
The migration test remains mandatory and failing in Hub/fast/full release.

## Framework scope and triage

BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-116 approved engineering policy; R1_RELEASE_CONTRACT
DECISION_IDS=GS-D001,GS-D002,GS-D029,GS-D030,GS-D031
TASK_SCOPE=component/release execution, permanent registration/integrity and DoD
OUT_OF_SCOPE=production storage migration; GS-130 exhaustive feature audit; hardware

Before: validation-fast manually lists host prerequisites then calls a global
quick runner; release-gate-final does not dominate those prerequisites, builds
classic ESP32 HIL, accepts unaudited ALREADY_PASSED environment flags, and variant/
sanitizer paths call make clean. No independent Node/Hub developer gate exists.

Implementation/qualification records follow after actual execution. Product
requirements and context version remain unchanged; this implements the explicitly
approved permanent engineering process. No physical qualification is implied.


## Resume and integrity corrections — 2026-10-11

Read interrupted GS-116 comment10370 and current global/root instructions;
preflight PASS, actual local/remote remain7b93dea. Preserved complete WIP,
managed_components, ignored assets and historical logs. No source restart.

Review closed a fingerprint omission: partition/config CSVs and all registered
untracked test inputs now invalidate receipts consistently across components.
Compiler identity/Python version join environment build profiles. Target receipt
artifacts include the build report and generated firmware BIN hashes. BAT-C8
requires both C++72-check and positive Python execution records; a synthetic
partial compound stage fails. These are TEST_INFRA_ONLY within GS-116.

Framework timeout fixture originally allowed100ms for Python startup; concurrent
IDF load reproduced a missing pre-timeout print. TEST_BUG: allow2s startup against
10s child delay; assert child actually launched before checking owned process-group
termination. Retains real timeout/partial-output/nonzero and orphan prevention.
24 self-tests PASS after correction, /tmp/gs116-framework-final3.log.

Initial resumed backend discovery ran385 tests (one scoped classic skip) and
failed only test_phase1_gate_integration_has_one_authoritative_owner: obsolete
literal Make prerequisite/classic build expectation. TEST_BUG / VALIDATION_WIRING:
replace source-layout assumption with executable registry checks preserving HIL
host/tool ownership, fast⊆release, C3/S3 production build and separate authorized
physical qualification owner. Focused HIL fixture68 tests PASS;
/tmp/gs116-hil-regression.log. Full current-source results follow below.

Initial overlapping campaigns predate the final framework changes and cannot be
reused as current-source PASS. Their logs are retained. Final qualification reruns
with stable source; explicit verified receipts avoid repeated identical stages.
Fresh IDF builds default2 jobs (IDF_PY_BUILD_JOBS override) to bound host contention.
No production firmware, protocol, security, timing, persistence or hardware change.


Additional hardening: incomplete nightly reports are RUNNING, empty reports FAIL,
blocked stages are excluded from passed counts, cancellation reaps owned children,
and linker/include overrides join receipt profiles. Framework26 tests PASS before
final sanitizer/skip matrix expansion. Initial fast qualification correctly rejected
an incompletely declared supported-limit skip (P2-MN25 plus summary) and a provider
success-marker mismatch (actual lowercase passed versus registered uppercase PASS).
Both are TEST_INFRA_ONLY registry corrections; tests/assertions remain unchanged.
The same migration failure still returns child1/Make2 and subsequent stages run.
Jira interim GS-11610403 and storage handoff GS-14810404; final delivery IDs
are recorded after actual commit/push verification.


## Final correctness/performance hardening

The full expanded pre-cache campaign ran all50 stages in1145.435s, source stable:
47PASS, multinode/provider registration mismatches FAIL despite executable exit0,
and mandatory migration child1/Make2 FAIL. Python387 (one classic skip), CPP1479,
GS-1501481, GS-401320, master49 and FOTA34 passed. Report:
`evidence/validation_framework/fast-1791682745264680458/report.json`;
/tmp/gs116-fast-qualified.log. Earlier original graph baseline183.29s is NOT
scope/cache/load-equivalent, so no speedup claim is made against that shorter graph.

Registry now matches exact provider/migration final success messages and both
existing P2-MN25 skip lines, retaining supported cases and capacity-rejection proof.
No fixture/production assertion was weakened. Browser/TAP lowercase skipped/todo/
unexecuted summaries fail; sanitizer diagnostics fail even with exit0 and UBSan
halts on the first error. Synthetic negative cases prove these protections.
Cancellation reaps owned groups, including on KeyboardInterrupt.

Uniform compiler recipes now reuse production translation units under the existing
object/dependency mechanism. The object profile includes compiler/flags plus
production source/header/config content, so preserved old mtimes cannot satisfy
current-source object validity. Generated headers and .d dependencies remain;
special per-target defines (e.g. recovery scheduling) retain dedicated compilation.
Every test executable still relinks and runs. Production code/test scenario bodies
are unchanged. Final framework31 self-tests PASS before full qualification.


First cached full campaign443.768s executed50 stages, source stable;
48PASS, migrationFAIL and HTTPS compileFAIL. HTTPS requires
-Itests/cpp/p2d_idf_fake; the generic object rule omitted this dedicated include.
Classification VALIDATION_WIRING introduced by GS-116 optimization, repaired by
restoring its original dedicated compile recipe and adding a permanent guard test.
No crypto/transport source change; missing esp_http_client.h caused nonzero failure,
not a silent wrong-profile PASS. Report fast-1791684111398782309/report.json remains
retained. Component receipts attempted from that campaign correctly rerun failed
stages; those superseded results are not the final qualification.
Final full gate reruns after the fix; special includes/defines remain dedicated.


## Approved execution correction — 2026-10-11, GS-11610405

Development qualification now runs Node, Hub, affected shared contracts, framework
self-tests and focused sanitizer/target builds only. Full release-gate execution is
**NOT_RUN / deferred until a genuine release candidate**, not PASS. Before this
correction a release attempt was started, then interrupted during sanitizers; its
partial log /tmp/gs116-release-final.log is preserved and provides no release
qualification. Its four variant builds exposed an existing simulator link omission:
HubRuntime replay-fence binding required durable_event_outbox.cpp absent from the
simulator link recipe. Classification VALIDATION_WIRING; fixed by linking that
production implementation and shared correctly profiled objects. Added a direct
framework guard; no protocol or storage implementation change.

Final pre-correction fast campaign fast-1791684809083415394/report.json ran
50 stages in452.351s:49PASS, mandatory migrationFAIL (Make2), source unchanged.
Node15/15 and contract23/23 passed using verified same-source receipts; Hub27/28
with migration rerunFAIL. Backend/PWA stages ran before the correction and are
retained as historical evidence, not rerun for current component acceptance.
The new simulator wiring changes source fingerprint; final component qualification
runs again below. Final framework self-test command make validation-framework-test:
exit0,33tests,8.240s, /tmp/gs116-framework-final.log.

Observed same expanded graph elapsed1145.435s before shared-object caching versus
452.351s after caching (~60.5% lower); host/load/cache not controlled. The original
183.29s graph was shorter and is not comparable. Every fixture still relinks/runs;
no performance improvement is obtained by suppressing failed tests.


## Final component qualification and pause/resume

All final framework/component/build commands use source HEAD
7b93dea9561ec4f0301ecd77a7b578bee8a1c36a plus reviewed GS-116 working changes,
source fingerprint70db85e1dc729e53042f262b740ed4f818f26054469f6fafd7df59f3a1fcbc6b.
Final local/remote delivery commit is recorded in the owning Jira final comment;
resume at actual branch HEAD, never restore the source baseline.

`make validation-node`: exit0,15/15 registered stages,280.585s, source unchanged.
CPP1479checks, BAT-C8 72checks plus11Python tests, GS-1501481checks,
GS-401320checks, secure-FOTA, commissioning/rejoin/association, Node persistence/
retirement/recovery, FOTA34 assertion groups, master49 groups and health config15
tests pass. Report node-1791686305322700234/report.json; log
/tmp/gs116-node-delivery.log. Counts retain their individual units, not a combined
invented test count. Health/SAN/shared receipts will be recorded after completion.

Framework33tests pass; lightweight `python3 tools/validation/component_gate.py
--suite release --list` selects61stages, exit0. Full release NOT_RUN/deferred.
Existing pre-correction fullPython393tests with one exact historical classic-ESP32
skip is retained as earlier evidence; no unrelated backend/PWA or fullPython rerun
is required by comment10405. Supported1/4/10-node matrix remains asserted, historical
25-node stress explicitly scoped SKIPPED with ten-slot rejection checked.

GS-130 next action: read this evidence, GS-116/130 latest Jira and current AGENTS;
map every implemented feature/requirement to registered positive, negative, boundary,
reboot/fault and physical cases. Close missing deterministic simulations without
claiming the framework registry alone proves exhaustive feature coverage. Start with
the separately built TF-PSA factory-reset executable's registration/dependency gap.
Carry the mandatory migration failure and GS-14810404 storage ownership handoff;
do not alter registry/domain security solely to turn legacy migration green.
Extended MEDIUM/concurrency/100k/coverage and all physical qualification remain
NOT_RUN here. GS-148 production cloud/backend contract remains partially implemented,
not commercially qualified by host interface tests.

After GS-130, GS-114 P1–P9 requires separate board authorization, matching C3/S3
GS-40/150 images/configuration and protected retained-event preservation. Real PIR,
GPIO4 electrical/held-high wake, radio restoration, authenticated outage/rejoin,
NodeHealth/caregiver visibility, target storage interruption and signed-FOTA evidence
remain open. GS-149 power and GS-146 dependencies are unchanged. Hardware actionsNONE;
GS-128/147 scope remains gated. Preserve original managed_components and ignored assets.


Final Hub command `make validation-hub VALIDATION_REUSE_REPORTS=<absolute Node
report above>`: Make exit2 / runner1,374.234s,27/28 stages PASS, source unchanged.
Only migrationFAIL; report hub-1791686586810724018/report.json. Shared stages reuse
verified executed Node receipts; all other Hub stages actually execute, including
migration. /tmp/gs116-hub-delivery.log retains complete command/output.

Final contract command `make validation-contract VALIDATION_REUSE_REPORTS='<absolute
Node report> <absolute Hub report>'`: exit0,23/23 stages,0.844s, source unchanged;
report contract-1791686961620500431/report.json. Reuse is explicitly declared and
checks exact source/profile/log/binary hashes; previously failed migration is not
a contract-suite stage. /tmp/gs116-contract-delivery.log and
/tmp/gs116-final-components.json record fully expanded absolute commands and timing.

`make simulator` from the application directory: exit0,5.323s, actual production
simulator executes and reports activity_seen=true, offline_records_replayed=1.
This proves the repaired default replay-fence linkage; the four alternate profiles
are not re-executed after comment10405. /tmp/gs116-simulator-delivery.log.
All component reports use the same final fingerprint; framework delivery does not
establish aggregate Hub or complete product PASS. No migration skip/disable, no
firmware protocol/security/state-format changes and no physical operations.


`python3 scripts/build_validation_targets.py` (application directory): exit0,
clean production GS_HIL_BUILD=OFF ESP-IDF6.0.3 C3/S3 compile/link/size and JSON
packaging PASS. Test count not applicable; whole-command duration not instrumented.
Report build/validation_targets/gs116-_kuod5ma/report.json; complete per-board
commands/logs and package.log retained there; outer /tmp/gs116-builds-final.log.
C3 934,192bytes /1,966,080-byte OTA slot, SHA256
`dd0d8855df851dd2f9300bb3b6bc91d9e810e68572ed129ec19455136dfc8aca`.
S3 1,868,800bytes /4,194,304-byte OTA slot, SHA256
`d285359eb0828e603d7dd53e8e61045e3c896de066c75ba1edd3ba3b18d19e95`.
Version7b93dea-gs116-70db85e1 embeds the source fingerprint. Configuration hash
fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862,
300s heartbeat/910s offline timeout and exact C3 image embedding PASS. S3 uses
existing LittleFS1.20.4/IDF6.0.3 dependency; optional online dependency-change
checks unavailable in sandbox, existing locked dependency builds successfully.
Original ignored Node image is preserved using an external scratch asset. Target
compiled only; no flash, partition/state migration or physical qualification.


`make validation-sanitize` (application directory): exit0,345.479s; ASan/UBSan
CPP1479checks and GS-401320checks PASS. ASAN_OPTIONS=detect_leaks=0;
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1, -O1 -g1
-fsanitize=address,undefined -fno-omit-frame-pointer. LeakSanitizer is not qualified
by this focused gate. No sanitizer diagnostics; /tmp/gs116-sanitizers-delivery.log.

Final preflight PASS, context unchanged2026-10-10.001; git diff --check PASS.
Framework implementation delivered; software qualification PARTIAL because the
mandatory historical migration test remains FAIL. Complete release NOT_RUN/deferred
per10405; no release or commercial qualification claim. No physical actions.
