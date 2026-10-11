# R1 Physical HIL coverage audit — 2026-10-11

## Scope and provenance

Owning work: GS-114 HIL coverage catalogue integration, with framework ownership
cross-referenced to GS-116 and inventory ownership to GS-130. Source checkpoint
before edits: `622bdd87608081f802a7f36a1029f9559777ed6a`, branch
`feature/r1-commercial-baseline`. No board, serial device, firmware or storage
was accessed in this audit. The dedicated C3/S3 fixture evidence cited below
was completed earlier under separate authorization; this audit did not rerun it.

The current source of feature rows is `docs/validation/MASTER_TRACEABILITY.csv`
(149 rows), backed by `SOURCE_FEATURE_INVENTORY.csv` (200 module records after
adding the two GS-114 fixture-commissioning adapter modules). The
physical class was explicitly assessed per trace row. Of 142 implemented or
partially implemented rows, 45 are `PHYSICAL_REQUIRED`, 40 are
`PHYSICAL_CONDITIONAL`, and 57 are `SOFTWARE_ONLY`. The remaining seven rows
are three ON_HOLD, three DEFERRED, and one NOT_IMPLEMENTED. These classes are
engineering dispositions, not semantic branch coverage or a qualification
percentage. For required and conditional rows, every listed HIL test ID must
resolve in the case catalogue.

## Existing HIL assets and compatibility

The reused implementation is under
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/`, principally
`phase1.py`, `qualify.py`, `core.py`, `identity_probe.py`,
`esp_idf_adapter.py`, `secure_signed_fota.py`, and the associated USB and build
helpers. Hardware-independent regression is in `tests/python/test_hil_*`.
`make hil-regression` owns the legacy 71-case connected Phase-1 campaign:
17 smoke, 10 radio, 20 outage, 10 Hub restart, 8 Node restart and 6 combined
restart cases. The exact old IDs and behavior remain documented in
`HIL_AUTOMATION.md` and `HW_M1_3_HIL_TEST_MATRIX.json`.

That connected runner remains for the historical classic ESP32 4 MiB Hub plus
C3 profile. It is not compatible with the current ESP32-S3 N16R8 target and is
unsafe for passive use: discovery can reset via DTR/RTS, campaigns can build,
flash, restart, alter logical connectivity and issue `INJECT_MOTION`. Injection
does not prove AM312 optical/GPIO4 behavior. No S3-compatible unattended board
runner or operator-prompting optical-motion suite exists today. GS-108 owns the
later broad stable-head HIL rework; GS-114 owns BAT-C8 P1–P9. This audit does
not create a second HIL supervisor.

The old-to-S3 compatibility audit remains in
`docs/hw/evidence/GS114_PART1_HIL_AUDIT_20261011.md`. Later, separately approved
fixture work installed development images on the disposable C3 and S3 pair,
used the S3-only `GS_HIL_COMMISSIONING` adapter through the existing secure
commissioning owner, and ran bounded Part 1 observations. That adapter does not
provide general HIL controls, does not satisfy GS-109 product authorization,
and ran with Secure Boot/flash encryption disabled. Do not use its security
profile for production qualification.

## Permanent catalogue and gate enforcement

`PHYSICAL_HIL_CATALOGUE.csv` now has 99 entries: 71 individual legacy Phase-1
case IDs, 27 current/owner physical cases, and one legacy suite summary. It links cases to feature
and requirement IDs, owner Jira, board/sensor profile, safe prerequisites,
destructive classification, procedure/command, expected observable, failure
conditions, run status, source/image provenance, evidence, release-blocking
classification and limitations. The 71 classic-ESP32 runner cases are
individually marked `HISTORICAL_EVIDENCE_ONLY`, with source/image hashes
explicitly unverified where old records do not preserve them. Old physical
evidence is never upgraded to the S3 N16R8 profile.

The `PHYSICAL_QUALIFICATION.csv` owner-level plan is preserved. The case-level
catalogue complements it. `make physical-hil-catalogue-test` validates unique
IDs, enumerated results, evidence paths and mappings from every required or
conditional implemented trace row. The same test is part of `make hil-tooling-test`
and therefore runs as hardware-independent tooling validation. It does not open
ports or execute physical scenarios.

The GS-116 registry has a release-only `physical-hil-release-evidence` stage.
It requires every `RELEASE_BLOCKING=YES` case to be a current PASS with exact
source SHA, image SHA-256 and evidence file. It never runs hardware tests. It is
excluded from fast and component development suites. Missing physical proof
causes the eventual complete release gate to fail visibly.

## Existing current-image physical evidence

Machine-readable results and detailed report:

`docs/hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011/attempt06/physical_results.json`

The two disposable fixture identities and app hashes are recorded there. The
run reported HIL-A02 authenticated link/rejoin PASS, HIL-A03 one authenticated
300-second health opportunity PASS, HIL-A06 bounded stability PASS, HIL-A07
timer counters PARTIAL, and HIL-A01 PARTIAL due to the missing S3 post-update
boot banner. HIL-A04 910-second offline detection and HIL-A05 actual Durable
ACK/EventKey transaction were NOT_RUN; HIL-A08 negative cases were BLOCKED.
No genuine PIR event was generated. Full BAT-C8 C8-P1–P9 remain NOT_RUN.
The case register retains image/source and fixture provenance, but does not
claim flash readback hash verification or production security qualification.

Historical HW-M1.4/GS-32–37/GS-118/GS-119 results retain their original board,
image and setup scope. They do not count as current S3 evidence. GS-148 physical
storage/cloud proof remains open and its mandatory host journal-migration
failure remains FAIL under GS-148; no migration assertion was removed or changed.

## Focused validation

| Command | Expected/observed | Status |
|---|---|---|
| `make physical-hil-catalogue-test` | 99 entries; 45 required and 40 conditional implemented features mapped; no device access | PASS, exit 0 |
| `make hil-tooling-test` | Existing supervisor/security-tool/phase1/replay tests plus catalogue integrity; 138 unittest checks passed | PASS, exit 0; Windows PowerShell interop explicitly skipped because unavailable |
| `make validation-framework-test` | GS-116 registry/failure-propagation self-tests | PASS, 36 tests, exit 0 |
| `make feature-coverage-test` | 149 feature rows, 200 source modules, 14 owner-level physical definitions plus 19 integrity tests | PASS, exit 0 |
| Release registry metadata | 59 fast stages; 69 release stages; physical evidence stage is release-only | PASS, metadata only |
| `python3 tools/validation/physical_hil_catalogue.py --release` | Fails while mandatory cases are PARTIAL/NOT_RUN/BLOCKED; 3 of 27 blocker records are currently PASS | EXPECTED FAIL / RELEASE NOT APPROVED |
| Synthetic complete-provenance release-check fixture | Checker accepts complete synthetic fields in unit test | PASS, test fixture only; no physical evidence |
| Physical tests / serial access | Not executed by this audit | NOT_RUN |

The full `make validation-fast`, `make release-gate-final`, Node/Hub/contract
regressions, broad GS-108 HIL, browser suites and hardware actions were not run.
The historical Hub journal migration assertion remains a mandatory Hub gate
failure as previously evidenced; this documentation/catalogue task does not
rerun or change it.

## Current gap and next owner

The catalogue documents present coverage; it does not create an S3 HIL runner.
The immediate physical next task remains **GS-114**, after this audit delivery,
for remaining current-image BAT-C8 P1–P9 and the real AM312/GPIO4, timer/radio
restore, Durable ACK/EventKey, outage/recovery and sleep-inhibitor cases. Use a
case-specific approved fixture and record exact current source/image hashes.
Part 2 real motion remains separate. GS-108 resumes its existing broad HIL
supervisor only after S3 compatibility and safe fixture execution are addressed.
Product release remains NOT_APPROVED until mandatory software gates and physical
evidence pass.
