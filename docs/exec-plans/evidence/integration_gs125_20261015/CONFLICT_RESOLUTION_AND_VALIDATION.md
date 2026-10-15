# Controlled Dashboard Integration Candidate — 2026-10-15

## Source checkpoints and safety

- Integration worktree: `/home/udaybhan/projects/Ghar_sajag_r1_integration`
- Integration branch: `integration/gs125-dashboard-r1-20261015`
- Canonical source when integration began: `c48e0d2fa8e0bc9c0d0a1f5eccdef789ff0b02df`
- Canonical tip at final recheck: `2c6797e36891303211262d43773920f531a3695c`
- The new canonical tip adds only
  `docs/exec-plans/evidence/STORAGE_BRANCH_RECONCILIATION_20261015.md`; that
  additive report was merged into the candidate without conflict. It does not
  overlap any of the 13 shared changed paths or alter test/code inputs.
- Dashboard source commit and verified remote HEAD: `d6ea59a2e10691e2cb09af80f0794ead272342ce`
- Merge base: `77e29d44c57f0851f78358049c288323c985d2e7`
- Integrated code/evidence commit: `4e6236810484e4ab9de2cc55934dc0d7e5ad4ea4`
- The post-validation documentation/evidence binding is a follow-up commit on this
  same isolated branch; it does not change production code or test inputs.
- The canonical documentation-only advancement is included in the candidate
  ancestry; both the canonical and isolated context preflights passed afterward.
- Canonical context preflight: PASS; integration worktree context preflight: PASS.
- Neither source worktree was modified. The canonical's untracked GS-114 evidence,
  managed components and historical PWA assets were not copied, cleaned or altered.
  Dashboard-only historical evidence was retained as received.
- No firmware, storage, CloudSync implementation, production routes or production
  authentication code was imported or activated by the reconciliation.

## Exact 13-path shared-source conflict matrix

The paths below are the complete intersection of canonical and Dashboard changes
since the merge base. Six had Git content conflicts; the other seven were reviewed
as overlapping edits. No canonical path was deleted. Canonical source was retained
where the Dashboard copy was a stale snapshot; additive dashboard test/mapping
changes were combined where safe.

| Shared path | Resolution | Preserved constraints / evidence |
|---|---|---|
| `code/scripts/check_feature_traceability.py` | Combined dashboard requirement/PWA registration checks with canonical stage mapping and source inventory logic. Narrowly corrected physical status consistency: sourced canonical PASS/PARTIAL/FAIL records are retained; a plan-only `NOT_RUN` row still cannot be promoted by a host run. | Does not claim physical PASS from host execution. Tests cover both preserved outcomes and rejection of an unsupported promotion. |
| `code/tests/python/test_component_gate.py` | Three-way merged dashboard PREVIEW_ONLY browser registration tests with canonical gate and failure-propagation tests. | Canonical stage selectors remain subject to exact baseline comparisons. |
| `code/tests/python/test_feature_traceability.py` | Merged tests for scoped dashboard requirements with canonical traceability integrity tests; added explicit physical-status retention/rejection cases. | GS-114 PARTIAL and C8-P8 PASS remain unchanged. |
| `code/validation/suites.json` | Preserved all 79 canonical stages and added only `diagnostic-foundation`; merged the Engineering preview cases into the existing browser stage. | Canonical browser command/selector retained; preview is `PREVIEW_ONLY`, PWA-selected, not fast-selected, and release-selected. Six canonical-only stages are byte-for-byte unchanged. |
| `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | Kept canonical current status; did not import stale Dashboard snapshot. | Existing CloudSync architecture/status is unchanged. |
| `docs/product/CANONICAL_REQUIREMENTS_INDEX.md` | Combined current canonical index with isolated dashboard-scoped approval entries. | `GS-DIAG-01/02` remain scoped approvals, not promoted to canonical requirement rows. |
| `docs/product/CONTEXT_VERSION` | Kept canonical value `2026-10-13.001`. | No new product decision was approved; no context-version increment. |
| `docs/product/DECISION_LOG.md` | Combined the dated no-new-decision/status additions and removed merge markers. | No new auth, production route or CloudSync decision. |
| `docs/product/R1_RELEASE_CONTRACT.md` | Retained canonical requirements and additive dashboard boundary references. | No change to canonical security, durability or release gates. |
| `docs/product/R1_WORK_STATE.md` | Kept canonical work state; integration evidence is appended as a dated status record. | Canonical GS-148, P0 PARTIAL, migration FAIL and physical NOT_RUN remain distinct. |
| `docs/validation/MASTER_TRACEABILITY.csv` | Three-way union of canonical and dashboard feature rows; canonical keyed rows win unless the Dashboard supplied a non-divergent additive mapping. | 198 rows; source anchors and gate membership checked by feature coverage. |
| `docs/validation/MASTER_VALIDATION.md` | Kept canonical validation policy; appended this candidate's actual execution record. | No release gate or historical failure assertion was removed or weakened. |
| `docs/validation/SOURCE_FEATURE_INVENTORY.csv` | Unioned dashboard auth-foundation mapping into the canonical identity module row while retaining canonical feature IDs. | 210 source modules; reciprocal feature mapping passes. |

## Registry preservation audit

At the canonical checkpoint the registry had 79 stages; the candidate has 80.
`diagnostic-foundation` is the only new stage. For every canonical stage, the
command, component set, fast/release selectors, run conditions, baseline inputs
and required-success markers were retained. The following canonical-only stages
are unchanged byte-for-byte, including command and failure semantics:

- `c8-ack-drop-gate`
- `storage-correctness`
- `first-event-reader-compatibility`
- `first-event-recovery-projection`
- `storage-correctness-sanitizers`
- `cloud-worker-backend-integration`

The existing browser stage keeps its command and browser selection; it adds the
PWA selector and 21 required preview markers (summary plus 20 named cases).
Missing markers and nonzero failures remain failures. The detailed six-stage
selectors are in [`preserved-stage-selectors.json`](preserved-stage-selectors.json).

## Validation record

Validation used the merged working source fingerprint
`dfae841074fa8a39c669ea66da68c2faef8fdbbdee4dcd103d8b0b6318ac27e3`; the
registered PWA receipt records its base `source_head` as the canonical starting
commit and `source_unchanged=true` through execution. All copied native receipts
and stage logs are retained beside this report. Recomputing that fingerprint
after commit `4e6236810484e4ab9de2cc55934dc0d7e5ad4ea4` produced the same value.
The Engineering host suite (98), framework/feature-coverage suites (44/22),
Python discovery rerun (465 with one approved skip), and all six canonical
stages were also executed against this unchanged committed code tree. Their
post-commit receipts and the evidence file hashes are included here.

| Area / command | Result | Details |
|---|---|---|
| Engineering Dashboard host suite | PASS | 98 tests. |
| GS-116 framework / failure propagation | PASS | 44 tests. |
| GS-130 feature mapping | PASS | 22 integrity tests; 198 feature rows, 210 modules, 15 physical cases. |
| GS-130 coverage command | PASS | `GS130 TRACEABILITY PASS`; consistency only, not semantic or physical qualification. |
| Caregiver JavaScript regressions | PASS | 23 tests. |
| Caregiver browser regressions | PASS | 86/86 in desktop/mobile Playwright projects; registered browser stage also PASS (877.698 s). |
| Engineering preview browser regression | PASS | 20/20 stable case IDs across seven screens at desktop/mobile; `PREVIEW_ONLY`. |
| PWA functional, dummy stream, HTTP, bridge, API, frontend stages | PASS | Counts 92, 5, 17, 13, 2 and 2 respectively. |
| Python unittest discovery, first PWA attempt | FAIL | 465 tests; one setup error because `build/hub_backend_commit_validation` had not been built. This failure remains in the native aggregate receipt. |
| Hub backend commit prerequisite + Python discovery rerun | PASS | `make hub-backend-commit-host-test`; then 465 tests PASS, one pre-existing approved skip. |
| `make validation-pwa` aggregate | FAIL | Native report `software_status=FAIL`, `physical_status=NOT_RUN`, `release_approved=false`. The first registered Python attempt lacked the Hub binary; the P0 stage also remains FAIL because `product_status=PARTIAL`. The later Python rerun does not rewrite the aggregate receipt. |
| P0 cross-component E2E | PARTIAL | All 26 scenario checks and its Chromium check passed, but `product_status=PARTIAL`; physical remains NOT_RUN. |
| C8 ACK-drop host gate | PASS | 16 checks. |
| Storage correctness host + sanitizer | PASS | Full `GS148_CASE=all`; fail-closed recovery cases remain explicit. Sanitizer execution passed. |
| First-event reader compatibility | PASS with retained known limitation | Command exit 0 and report produced; `OLD_READER_COMMERCIAL_ROLLBACK_AVAILABILITY=FAIL_KNOWN_FIRST_EVENT_LIMITATION` remains visible. |
| First-event recovery projection | PASS with product gap retained | Host/recovery assertions passed; `PRODUCTION_CLOUDSYNC=PENDING`, `PRODUCT_P0=PARTIAL`, `PHYSICAL=NOT_RUN`. |
| Cloud Worker backend integration | PASS | Same-event retry, durable effect and caregiver projection assertions passed. |
| Historical migration result | FAIL (preserved) | No migration assertion was changed or rerun to convert this status. |
| Physical qualification | NOT_RUN | No hardware, flashing, provisioning, eFuse or deployment operations. |
| `make release-gate-final` | NOT_RUN | Not authorized in this task. |

`git diff --check` reports trailing whitespace in imported historical Dashboard
stdout receipts. These are preserved native historical logs and were not edited;
the whitespace finding is documented rather than hidden by receipt rewriting.

## Delivery state and blockers

The candidate remains isolated on `integration/gs125-dashboard-r1-20261015`.
No merge into `feature/r1-commercial-baseline` is performed here. Production
OIDC/session enforcement, PostgreSQL persistence, CSRF and authenticated PWA
Service Desk routes remain BLOCKED; Engineering screens remain PREVIEW_ONLY.
GS-148 P0 remains PARTIAL, historical migration remains FAIL, and physical
qualification remains NOT_RUN. Owner review and coordination with GS-148 are
required before any separate canonical merge approval.

## Final pre-merge qualification follow-up — 2026-10-15

The first Python discovery failure was a clean-checkout dependency-order defect:
`test_hub_backend_commit_integration.py` launches
`build/hub_backend_commit_validation`, but the PWA suite selected `python` without
selecting the already registered `backend-receipts` build/test stage first. The
registry now supports additive stage `prerequisites`; Python declares
`backend-receipts`, and the existing stage order ensures that prerequisite runs
first. This leaves all original canonical stage commands, component ownership,
selectors and assertions intact. A framework regression checks inclusion and
ordering. The one added dashboard stage remains `diagnostic-foundation`.

On the final source tree, the registry has 80 stages: all 79 stages from canonical
checkpoint `2c6797e` are present, with no missing IDs, and the sole added ID is
`diagnostic-foundation`. `make feature-coverage-test` passed (198 feature rows,
210 source modules, 15 physical cases; 22 mapping tests). The GS-116 framework
passed 44/44; Engineering host foundation passed 98/98; Python discovery passed
465 tests with the single approved historical skip. The focused prerequisite
target built and ran `HUB-BACKEND-COMMIT HOST PASS`.
Final deterministic source fingerprint: `79fac128bb75351097c322ab96e05f2578d5bad892f8391ae0328e75735c96cd`.

The browser suite passed separately on its supported alternate local port 8767:
86/86 Caregiver browser cases and all 20 Engineering `PREVIEW_ONLY` cases across
seven screens and two viewports. The dedicated P0 stage ran 26/26 scenario checks
and its Chromium check, with `product_status=PARTIAL` and `physical=NOT_RUN`.
These results do not turn P0 into PASS.

`make validation-pwa` was attempted with fresh stages and no receipt reuse. Its
first invocation was blocked by sandbox socket restrictions. In an external
execution, the normal browser port 8766 was already held by an existing
`python3 tools/sim/local_lab.py --port 8766` process (PID 432418), which was left
untouched. Running the entire aggregate with `PLAYWRIGHT_PORT=8767` is not a valid
workaround because the Python runner tests intentionally assert the default port;
that attempt recorded two environment-override test failures and was stopped.
The browser stage itself passed on 8767, but there is no complete final
`validation-pwa` aggregate receipt. Therefore the PWA aggregate remains
**BLOCKED/NOT COMPLETE** pending an ordinary rerun after port 8766 is available;
the known P0 PARTIAL completeness assertion remains an expected independent gate
failure.

Fresh final-tree C8/storage/CloudSync checks:

- C8 ACK-drop: PASS, 16 checks.
- Storage correctness: PASS, complete `GS148_CASE=all` matrix; explicit
  `FIRST_ADMISSION_RECOVERY_BLOCKED` fail-closed cases remain in output.
- Storage sanitizer: PASS after an initial sandbox LeakSanitizer startup failure
  (`does not work under ptrace`) was confirmed environmental on external retry.
- First-event reader: PASS for the scoped checks, with
  `OLD_READER_COMMERCIAL_ROLLBACK_AVAILABILITY=FAIL_KNOWN_FIRST_EVENT_LIMITATION`
  retained.
- First-event recovery projection: PASS, with
  `PRODUCTION_CLOUDSYNC=PENDING / PRODUCT_P0=PARTIAL / PHYSICAL=NOT_RUN` retained.
- Cloud Worker backend API: PASS, one exact retry, durable effect and caregiver
  projection.

The historical migration result remains **FAIL**; no migration assertion was
changed. Physical qualification remains **NOT_RUN**. No release gate, hardware,
flash, production authentication or Jira workflow transition was performed.

The remote canonical branch advanced to `1eba6c561e8a908fc899219cb7098af30ddcff80`.
The fetched tree delta from the supplied canonical checkpoint `2c6797e` is only
the additive `docs/exec-plans/evidence/S3_BRANCH_RECONCILIATION_20261015.md`;
there are no changed code, registry, requirement or test files in that delta.
This source comparison found no new product-code conflict, but this candidate has
not been rebased/merged onto the newer canonical tip. Any eventual integration
review must use that latest checkpoint and retain the new report.

The imported historical native logs were not rewritten. The earlier report's
trailing-whitespace finding for historical Dashboard stdout receipt copies remains
documented; their original files and hashes are preserved. Current follow-up
`git diff --check` is clean.
