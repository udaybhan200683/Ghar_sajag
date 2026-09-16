# Ghar Sajag / Parivar Saathi Engineering History

**Document revision:** P2D-R1
**History covered through:** Phase 2D
**Product baseline through:** Parivar Saathi v1.5.4
**PWA / BatteryAnalytics baseline through:** v3.4.3
**Latest implementation anchor covered:** `9499381`
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
