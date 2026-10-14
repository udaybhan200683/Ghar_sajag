# GS-130 bounded implemented-feature regression pass — 2026-10-14

## Scope recorded before implementation

Owning Jira: GS-130 comment 10932; GS-116 owns gate registration/integrity.
Canonical branch `feature/r1-commercial-baseline`, starting local/origin HEAD
`ed1a7dfde0299e8c84e4f12a9f1dd48dd39836ed`; context preflight PASS,
version `2026-10-13.001`. Tracked worktree was clean. Existing untracked assets,
managed components and private/raw GS-114 evidence remain protected.
Prior canonical CLI has no active child task; a separate dashboard CLI uses its
own historical worktree. No competing canonical build/test/write was observed.
No hardware operation is permitted in this task.

BUG_CLASSIFICATION=TEST_INFRA_ONLY (coverage additions; classify any reproduced
product defect separately before repair).
REQUIREMENT_SOURCE=R1_RELEASE_CONTRACT.md; P0_PRODUCT_REQUIREMENTS.md;
DEVICE_HEALTH_LIVENESS_AND_OFFLINE_DETECTION.md; MASTER_VALIDATION.md.
DECISION_IDS=GS-D018/022/029/031/032; no new product decision.
TASK_SCOPE=bounded production-code regression gaps for health/coverage,
immutable durable events/caregiver projection, settings and implemented rules.
OUT_OF_SCOPE=GS-104 learning, GS-89 driver, production credential design,
GS-148 P4/P5-B1 implementation, physical operations and complete release gate.

Affected components: production Node/Hub simulation and shared rules; backend
health, durable API/query and configuration paths; existing local PWA projection
contracts. No commercial credentials or target wall-clock behavior are inferred.
Prior suites: GS-40/GS-150, BAT-C8/P9, 9-group board stack, feature boundaries,
backend Python, durable API/commit, ownership/P0, contracts and gate meta-tests.
New tests will use these existing harnesses/stages, stable IDs and mandatory
case markers. Positive, negative, exact-boundary, timeout and recovery oracles
are selected below; release registration remains permanent and device-free.

## Read-only gap audit

| Priority | Existing implemented coverage reused | Missing combination selected |
|---|---|---|
| Health | GS-40 300/910 policy; test_main direct identity/session/sequence rejection; BOARD-005 WAN-only; NodeHealth lab silent lease and recovery | Authenticated fresh-envelope replay at lease expiry followed by same-session and new-session recovery without an event; invalid health must not poison freshness |
| Health | Foundation received-contact test prevents render-time timestamp renewal while still online | Cached health after offline expiry must not resurrect online state; older contact must not clear a newer fault |
| Health | Separate WAN-only and silent-Node lab tests | Simultaneous WAN loss and silent Node; local Node recovery restores coverage while WAN stays down |
| Durability | Backend exact retry/reopen, atomic effects/fault cuts, original timestamps; P0 exact serialized EventKey and ownership negatives | Late backlog versus newer activity, fresh process/query composition, notification delivery followed by restart/retry, privacy-safe projection and one durable effect |
| Settings | Backend positive desired/applied version test; P0 one malformed policy; Foundation settings persistence/type rejection | Real JSON API typed/range rejection preserving entire desired/applied snapshot and audit, authorization failure, valid boundary recovery |
| Rules | Morning deadline mode/coverage tests; night >threshold; minute helper; ordinary inactivity | Implemented rule toggles, exact merge/day/night boundaries and rearming; suppression must not consume the one-shot timer latch |

Backend `feature_flags.py` has no production consumer in this checkout: helper
values are not proof that those broad feature switches enforce product behavior.
Tests will cover implemented ActivityRuleConfig switches instead. Complete
historical interval coverage, secure-target epoch scheduling, production Hub
credentials, external provider delivery and caregiver OIDC remain PARTIAL or
NOT_IMPLEMENTED with their existing owners. GS-104/GS-89 boundaries are retained.

## Added scenarios and permanent registration

| Stable scenario | P0 use case | Production path / asserted outcome | Existing executable stage |
|---|---|---|---|
| BOARD-TC-130-010 | UC-08/09 | NodeHealth codec + AEAD + HubRuntime: authenticated replay does not refresh 910-second lease; wrong identity/backwards time/old session do not poison state; fresh health and new-session sequence restart recover without resident event | `make board-stack-e2e-host-test`; `board-stack-e2e` → Node/Hub/contract/fast/release |
| GS130-HEALTH-001 | UC-06/08/09 | C++ local lab + Foundation projection: simultaneous WAN/Node loss, inclusive lease, truthful local coverage, Node return while WAN remains down, no fabricated Motion | `make gs40-config-test`; `health-config` and `python` → Node/Hub/contract/backend/PWA/fast/release |
| GS130-HEALTH-002 | UC-08/09 | Foundation received-contact consumer: cached/old/expired reports cannot revive OFFLINE or clear DEGRADED; future time/unregistered rejection; genuine recovery and Node 910/Hub 190 boundaries | Same existing health-config/Python stages |
| GS130-DURABLE-001 | UC-04/10/11/12/17 | File-backed JsonApi/SQLiteEventMap/DurableEventCommit: original structured key/time, late backlog does not displace newer activity, delivered outbox survives new process + duplicate receipt, one alert/job/effect, payload redaction and actor/Home isolation | Registered Python discovery → backend/PWA/fast/release |
| GS130-CONFIG-001 | UC-13/15/17 | JsonApi/FleetService/IdentityService: malformed/missing/typed/range-invalid JSON or non-managing caregiver preserves desired/applied snapshot and audit; valid lower/upper limits publish new unapplied version then target confirmation applies | Registered Python discovery → backend/PWA/fast/release |
| HUB-TC-130-006 | UC-06/07/13/15/17 | RulesCore: actual inactivity/night/quiet toggles, unavailable/fault coverage, untrusted time and mode suppression; exact threshold/day/night/merge boundaries; timer latch not consumed during suppression, new Motion/next night recovery | `make feature-boundary-host-test`; `feature-boundaries` → Node/Hub/contract/fast/release |

Python discovery command is the existing stage command
`python3 -m unittest discover -s tests/python -p test_*.py -v`.
The 78-stage registry is retained. Added mandatory markers for the sixth Hub
boundary case, tenth board case and all four new Python cases. The new meta-test
proves omission/nonzero exit fails even when other cases and total-count output
look successful. Existing stale-receipt/zero/skip/source/profile checks remain.
Traceability has 182 rows; source inventory has the same 205 modules; 15 legacy
physical definitions and the separately reconciled physical catalogue remain.

## Implemented behavior and genuine remaining gaps

| Area | Outcome of this bounded pass | Remaining owner / limitation |
|---|---|---|
| Authenticated C3 health, lease, retry and new-session recovery | PASS in executed production-code host paths; new replay/expiry/recovery combination added | GS-114/GS-40: real target scheduling/RF and trusted epoch integration are separate; no new HIL result |
| Cached backend health truth | Original FAIL reproduced; small consumer fix and positive/negative/recovery regression PASS | Caller must supply trusted received-contact time; no authenticator is invented |
| C3 versus locally available Hub versus WAN loss | Existing single-outage cases reused; combined local projection PASS | Local lab supplies explicit network state; absent remote Hub contact alone cannot locate the physical outage cause |
| No observation versus inactivity | Existing coverage/mode/time unit tests reused; new switch/latch boundaries PASS | Full historical interval coverage is PARTIAL, not proven by present lease; GS-104/GS-148 |
| Original EventKey/Node retention/Hub durable ACK | Existing board/recovery/security suites reused and executed under current candidate | Target physical evidence reused with its recorded limitations |
| Backend durable COMMITTED + retry + caregiver query | Existing P0/ownership tests plus new late-backlog/new-process/delivered-outbox/privacy PASS | GS-148: active caller/production issuer/verifier, trusted enrollment and deployment still PARTIAL; injected auth is explicitly a fixture |
| Current deterministic rule toggles/day/night | PASS for the typed implemented rule paths; no learned model introduced | Secure target wall-clock timer input/complete rollout remain PARTIAL |
| Valid/invalid settings and actor isolation | PASS for implemented JSON API/threshold/version guard and existing Foundation schema tests | Full runtime policy deployment/human OIDC remain separate; GS-76/GS-143 |
| Generic backend feature switches | NOT_IMPLEMENTED as enforced product behavior: helper has no consumers | GS-130; do not claim toggling unused helper proves feature suppression |
| Personalized routine learning | NOT_IMPLEMENTED / ON HOLD | GS-104 R01–R09 approval boundary preserved |
| Real main-door reed sensing | Physical NOT_RUN / driver boundary preserved | GS-89; virtual domain transitions cannot qualify its hardware |
| External provider/human receipt | BLOCKED / not claimed | Provider deployment and human identity owners; fixture delivery state is persistence only |
| Current component/release aggregate | Independent mandatory FAIL/PARTIAL retained | Hub migration assertion; product P0 trust gap; full release NOT_RUN |

## Execution and closeout

### Demonstrated health defect, classified before repair

BUG_CLASSIFICATION=R1_BLOCKER (incorrect caregiver-visible online/health state).
REQUIREMENT_SOURCE=P0_PRODUCT_REQUIREMENTS.md "Device offline and battery health";
DEVICE_HEALTH_LIVENESS_AND_OFFLINE_DETECTION.md; GS-D022/031.
TASK_SCOPE=small correction to existing FoundationService received-contact path.
OUT_OF_SCOPE=authentication, transport, Node/Hub firmware and new health policy.

`GS130-HEALTH-002` failed on the original source: after 910-second lease expiry,
the same cached contact changed OFFLINE to ONLINE. `record_health` clamps an older
timestamp but still overwrites online/health fields. It can also replace newer
DEGRADED telemetry with stale ACTIVE telemetry. The first failure is preserved in
`GS130_RISK_REGRESSION_20261014/health_first_failure.log`. Repair must reject
duplicate/older explicit online observations and observations already outside
the existing selected Node/Hub lease. Genuine newer, still-fresh contact must
recover online; implicit local offline transitions must remain supported.

Focused results: board E2E PASS 10 groups/398 checks; feature-boundary PASS 133
checks; health/config PASS 17 tests; durable API/backend PASS 17 tests;
feature mapping PASS 182/205/15 plus 20 integrity tests; gate framework PASS
41 tests. New fixture errors (unsupported UTC household value, desired new
version correctly being unapplied, event-table column name and unregister
method name) were corrected to match existing supported interfaces; no product
assertion or security guard was weakened. The first health-config fixture error
log is retained beside its successful retest and the original product failure.

### Traceability metadata defect found by mandatory component discovery

BUG_CLASSIFICATION=TEST_INFRA_ONLY.
REQUIREMENT_SOURCE=MASTER_VALIDATION.md; existing traceability schema.
TASK_SCOPE=repair invalid coverage-status values and prevent recurrence.
OUT_OF_SCOPE=product implementation and physical acceptance status.

The first backend/PWA Python discovery run exposed six pre-existing invalid
`status` values at the starting commit. Five GS148-ARCH rows used the coverage
class `AUTOMATED_WITH_PHYSICAL_GAP`, and C8-P8-ACK-DROP-GATE used implementation
state `IMPLEMENTED` in the coverage-status column. The existing framework test
correctly failed. These six coverage statuses are now `PARTIAL`; their separate
implementation/physical fields and open limitations remain explicit. The P8
gap text now reflects the existing accepted physical run and its timestamp
limitations. No physical result is newly claimed.

The feature mapper now checks the existing coverage-status vocabulary, and a
permanent negative/positive test rejects those two misplaced values. This
changes the framework's global source fingerprint. The initial component
receipts remain retained; final affected suites run at the corrected fingerprint
with verified reuse of matching stages across suites. This is the reason for
the additional component execution, rather than a repeated unchanged campaign.

Final component receipts are recorded below after current-source execution.
Source fingerprint for the frozen candidate is
`11b8ce399cce108c2dc2fedede0c54e31a31a6d45df05beef8539eba3d7fe574`.
Receipts may be reused only after source/profile/log/binary verification. No
firmware production source changed; no target rebuild/flash is required for
this Python consumer fix. Existing native storage/FOTA sanitizer evidence is
retained; registered applicable component sanitizer stages remain mandatory.

### Final affected-component results

| Existing command | PASS stages / total | Actual aggregate result | Remaining failing stage(s) |
|---|---:|---|---|
| `make validation-node` | 23/24 | FAIL; Make exit 2 | p0-full-product-e2e |
| `make validation-hub` | 39/41 | FAIL; Make exit 2 | migration; p0-full-product-e2e |
| `make validation-contract` | 33/34 | FAIL; Make exit 2 | p0-full-product-e2e |
| `make validation-backend` | 13/14 | FAIL; Make exit 2 | p0-full-product-e2e |
| `make validation-pwa` | 11/12 | FAIL; Make exit 2 | p0-full-product-e2e |

All five reports have `source_unchanged=true` and the same frozen fingerprint.
Cross-suite verified reuse selected 15 stages for Hub and 32 for contract;
backend/PWA also reused only matching successful receipts. Failed mandatory
P0 stages were executed and adjudicated as failures, rather than reused as PASS.

Actual Python discovery: **459 tests, OK with one declared historical classic
ESP32 target skip**; no unexpected skips. The six misplaced status values are
fixed, so the earlier Python metadata failure no longer occurs. Existing P0
executes 26 assertions and one targeted Chromium case successfully, but its
`product_status=PARTIAL` causes the registered stage to FAIL. The migration
`clean migration commits` assertion remains an actual independent FAIL.

Focused framework checks: 41 PASS; mapping integrity: 20 PASS, 182 rows /
205 modules / 15 physical definitions. Storage ASan/UBSan ran and PASSED.
BAT-C8 72 C++ + 11 Python, GS-150 1500, GS-40 1320, general C++ 1483,
FOTA 34 and board 10 groups / 398 checks remain PASS in current receipts.
No production C++/target firmware changed. ESP-IDF target rebuild, full browser
campaign, `validation-fast` and `release-gate-final` were NOT_RUN for this task.

Exact invoked commands, original paths, Make exits, counts, profile and global
fingerprint are in [final_component_manifest.json](GS130_RISK_REGRESSION_20261014/final_component_manifest.json).
Portable report/log copies are under `final_receipts/<suite>/`; each stage log
was checked against its report SHA-256 before archiving. The original report
paths are retained as provenance; the corresponding archived log uses its stage
ID as filename. [sha256_manifest.json](GS130_RISK_REGRESSION_20261014/sha256_manifest.json)
covers the archived files. Initial receipts and the first metadata failure are
retained under `initial_component_receipts/`. Generated original reports/binaries
also remain in ignored `code/evidence/` and `code/build/`; none were removed.
Source/document whitespace checks pass. Archived raw logs intentionally retain
their original trailing spaces/tabs so their receipt hashes remain verifiable;
the raw-log whitespace warnings are not edited away.

Hardware/commissioning and private GS-114 raw logs remain untouched. Prior C8
physical PASS evidence is reused; P3 catalogue provenance remains PARTIAL,
P9 physical ACK/FOTA BLOCKED, P10 GS-149. This is a bounded software checkpoint,
not exhaustive product/release qualification. GS-104 approvals, GS-89 hardware
and GS-148 commercial trust/provider gaps remain open.

## Exact next GS-148 handoff

After this bounded GS-130 checkpoint, read GS-148 comments 10810/10933,
`docs/exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md` and
`docs/exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md` from the verified
canonical branch. Inspect the existing Hub CloudSync worker/caller, strict
receipt parser, backend durable API and trusted ownership hooks. The next
separate task is P4/P5-B1 bounded CloudSync caller/COMMITTED integration.

Reuse exact-key retry/reboot/backend/projection tests from this checkpoint;
preserve original occurrence time, Hub/Home/Node/enrollment-generation binding,
one durable backend/caregiver effect and no completion on transport success.
If issuer/verifier or trusted ownership epoch/signer policy remains undefined,
leave commercial sending disabled/not-ready and report the exact missing
authority. Do not create universal credentials or use local fixture auth in
commercial mode. No new endpoint/storage codec/GC/migration/security downgrade
or hardware operation is implied. GS-148 implementation has not begun here.
