# Ghar Sajag / Parivar Saathi Engineering History

**Document revision:** P3A-R1
**History covered through:** Phase 3A qualification
**Product baseline through:** Parivar Saathi v1.5.4
**PWA / BatteryAnalytics baseline through:** v3.4.3
**Latest implementation anchor covered:** `4dcaf99`
**Updated:** 2026-09-16

This file is an append-only chronological engineering history.

# Ghar Sajag / Parivar Saathi Engineering History

This file is an append-only chronological engineering history.

Do not delete or rewrite completed historical entries when later phases are
implemented. Corrections and refinements should be recorded as later entries.

For current implementation status, see:
`docs/progress/CURRENT_BASELINE.md`

For intended scope and phase boundaries, see:
`docs/plans/FULL_PWA_IMPLEMENTATION_TASK.md`

## Phase 1 - Persistent Foundation

Commit anchors:
- `9cb3f4a` - persistent settings and device management
- `959c854` - caregiver UI corrections and regression coverage
- `9757791` - Phase 1 validation hardening

Summary:
- persistent household/settings foundation
- Family Members and roles
- authoritative device registry
- Devices / Manage Devices
- battery/device health
- routine/activity configuration
- Home caregiver behavior
- deterministic simulator and validation framework

Important validation hardening:
- required + forbidden assertions
- cross-card contamination checks
- desktop/mobile browser coverage
- release-gate process/port isolation

Qualification:
- `make release-gate-final`: PASS


## Phase 2A - Reports and Durable Event History

Commit:
`97f004fbd64b6dbdce9f163bdb017b7909f14da1`

Summary:
- Today / Week / This Month reports
- backend-derived Reports API
- durable canonical CloudEvent history
- SQLite event persistence
- restart durability
- removed-device historical reporting
- persisted household-timezone report boundaries

Important architectural decision:
Canonical event history became durable and remained the source of truth for
report projections.

Validation:
- backend Reports suite: PASS
- desktop/mobile Reports Playwright: PASS


## Phase 2B - Notifications

Commit:
`d43d999c7b84b107e63844d71144b6440e2bdd42`

Summary:
- persisted notification preferences
- persisted notification records
- care/safety classification
- maintenance separation
- dedupe/idempotency
- FAILED / SUPPRESSED / RESOLVED states
- backend-owned I-am-OK overdue evaluation
- coverage-loss/restoration resolution
- delivery-adapter boundary

Validation:
- notification backend suite: PASS
- desktop/mobile notification Playwright: PASS


## Phase 2C - PWA Integration

Commit:
`4d021cdd25024774375ccdbc8cef3de57a7ba420`

Summary:
- backend-owned I-am-OK state reflected on Home
- backend-derived "Last confirmed" timing
- Routines & Activity Rules caregiver-facing label
- optional DEVICE_MAINTENANCE notifications
- Home / Reports / Notifications classification consistency

Validation:
- targeted backend regressions: PASS
- desktop/mobile Phase 2C Playwright: PASS


## 2026-09-16 - Phase 2D Reconciliation and Qualification

Purpose:
Final Phase 2 reconciliation, performance trimming, cross-feature validation,
and release qualification.

Performance / architecture improvements:
- compact `/pwa/state?scope=home`
- Reports loaded on demand
- notification polling throttled/cached
- active-tab rendering
- Phase 2D payload contract coverage
- full device state fetched only when Devices requires it

Regression 1 - Device Health display name:
Compact Home state removed full `devices[]`, causing Device Health to render
internal ID `kitchen` instead of caregiver-facing `Kitchen Node`.

Resolution:
- retained compact Home payload
- added minimal caregiver-facing device-name maps
- did not restore full devices/settings payload

Regression 2 - Durable-history validation isolation:
Dummy sensor/PWA validation scenarios reused durable canonical event history,
causing previous MOTION events to leak into later assertions.

Resolution:
- validation runners use `reset(test_fixture=True)`
- production durability behavior remains unchanged

Regression 3 - Devices tab stale state:
Phase 2D compact polling left `state.devices` stale while Devices was active.

Symptoms:
- newly registered device did not immediately appear
- backend offline transition remained visually Active

Resolution:
- device create/edit/remove explicitly refreshes full state
- polling uses full state only while Devices tab is active
- Home polling remains compact
- Reports/Notifications optimizations remain intact

Final qualification:
- focused Phase 1 UI contract: PASS
- focused Phase 2 browser suite: PASS
- host release gate: PASS
- mandatory desktop/mobile Playwright gate: PASS
- `make release-gate-final`: PASS

Phase 2 status:
COMPLETE / QUALIFIED

## 2026-09-16 - Phase 2D Commit Anchor Recorded

Implementation / qualification commit:
`9499381` - Complete Phase 2D reconciliation and qualification

Repository state at the Phase 2D implementation checkpoint:
- branch: `feature/full-pwa-e2e`
- implementation/qualification commit pushed to origin
- Phase 2: COMPLETE / QUALIFIED
- authoritative final qualification: `make release-gate-final` PASS

This commit is the Phase 2D implementation/qualification anchor. Later
documentation-only commits may become repository HEAD without changing this
qualified implementation anchor.

## 2026-09-16 - Phase 3A Performance and Stress-Foundation Checkpoint

Document revision:
`P3A-R1`

Historical qualified baseline retained:
`9499381` - Complete Phase 2D reconciliation and qualification

Summary:
- established deterministic static and API payload measurement with structural
  regression budgets;
- moved the engineering validation catalog off initial Home startup;
- removed unnecessary full-state Settings hydration;
- guarded and throttled polling without weakening backend-owned safety rules;
- added change-aware active-tab rendering and visibility recovery;
- changed durable history projections to indexed/range/limit-aware SQLite reads;
- completed the bounded static-only service-worker module allowlist;
- added isolated deterministic SMALL/MEDIUM/LARGE/EXTENDED stress profiles and
  performance/stress/endurance Make targets;
- added Python, JavaScript and desktop/mobile Playwright regression coverage.

Checkpoint evidence:
- profiler structural budgets: PASS;
- SMALL deterministic stress: PASS;
- MEDIUM deterministic stress: PASS;
- targeted Phase 1/2 Python regressions: PASS;
- full Python discovery: PASS (94/94);
- JavaScript tests: PASS (3/3);
- 20 socket-free/compiled release-gate stages: PASS;
- Playwright desktop/mobile discovery: PASS (86 instances);
- socket-bound HTTP/PWA/browser stages: ENVIRONMENT_BLOCKED by Codex loopback
  EPERM and therefore still require WSL execution.

Qualification status:
IMPLEMENTED / QUALIFICATION PENDING. This entry does not replace or weaken the
qualified Phase 2D anchor and does not claim Phase 3A QUALIFIED before the
mandatory browser/final release gate is executed successfully.

## 2026-09-16 - Phase 3A Final Qualification

Document revision:
`P3A-R1`

Qualification result:
COMPLETE / QUALIFIED

Authoritative final qualification:
- `make release-gate-final`: PASS;
- mandatory Chromium desktop browser suite: PASS;
- mandatory Chromium mobile browser suite: PASS;
- performance profile: PASS;
- SMALL deterministic stress: PASS;
- MEDIUM deterministic stress: PASS;
- Python regression suite: PASS (`96/96`);
- JavaScript regression suite: PASS (`3/3`);
- `git diff --check`: PASS.

Performance / UX result:
- the 28,770-byte engineering validation catalog remains removed from initial
  Home startup;
- compact Home state remains 1,216 B in the recorded deterministic baseline;
- the post-fix profiler reported 80,542 B static total and remained within the
  established Phase 3A structural budget;
- Reports, Settings and Devices retain the Phase 3A lazy/bounded hydration and
  active-domain refresh rules.

Browser qualification found and corrected three sequencing defects:
- Reports refresh used a deadline sampled from the Home poll loop, allowing an
  effective delay beyond the intended active refresh interval;
- an older Home poll response could overwrite a newer explicit action result;
- simulator `simulation_now` can legitimately move backward after reset, so the
  stale-response guard now uses a reset epoch before comparing simulator time.

The Phase 2D qualified implementation anchor `9499381` remains historical
evidence. The Phase 3A implementation/qualification commit anchor is pending
creation of the qualified commit and will be recorded in a later append-only
entry.

## 2026-09-16 - Phase 3A Commit Anchor Recorded

Implementation / qualification commit:

`4dcaf99` - Complete Phase 3A performance and stress foundation

Repository state at the Phase 3A implementation checkpoint:
- branch: `feature/full-pwa-e2e`
- implementation/qualification commit pushed to origin
- Phase 3A: COMPLETE / QUALIFIED
- authoritative final qualification: `make release-gate-final` PASS

This commit is the Phase 3A implementation/qualification anchor. Later
documentation-only commits may become repository HEAD without changing this
qualified implementation anchor.

## 2026-09-16 - Phase 3B Durable-History Read Optimization (In Progress)

Status:
IMPLEMENTED / MANUAL QUALIFICATION PENDING

Summary:
- confirmed temporary SQLite sort/group B-trees on representative hot event
  queries and added migration-managed indexes matching their filters/orders;
- replaced recursive per-poll conversion of the historical incident population
  with the bounded active incident categories required by caregiver Home;
- preserved public snapshot, durable history, Reports and caregiver-visible
  care semantics;
- added bounded stderr stage/milestone progress and diagnostic-only per-stage
  timings to the stress runner;
- added focused query-plan, ordering, projection-scale and JSON-stream tests.

Host evidence:
- focused Phase 3B tests: PASS (`5/5`);
- full Python discovery: PASS (`101/101`);
- JavaScript application tests: PASS (`3/3`);
- performance/SMALL and MEDIUM stress gates: PASS;
- explicit LARGE host diagnostic: PASS (25,000 accepted, 2,500 duplicates,
  250 rejected, 5,000 notifications, zero request failures, 75.14 s wall time);
- MEDIUM unprofiled diagnostic: 11.93 s before, 4.51 s after on the same host;
- MEDIUM profiled diagnostic: supplied ~17.45 s before, 6.94 s after.

This is not a Phase 3B completion or qualification entry. Manual acceptance and
mandatory desktop/mobile browser qualification remain pending. Phase 3A remains
COMPLETE / QUALIFIED at permanent implementation anchor `4dcaf99`.
