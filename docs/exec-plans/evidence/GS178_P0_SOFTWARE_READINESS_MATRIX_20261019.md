# GS-178 R1 P0 software readiness matrix — 2026-10-19

## Authority and interpretation

This matrix audits the 17 use cases in
[`docs/validation/P0_E2E_SCENARIOS.json`](../../validation/P0_E2E_SCENARIOS.json)
against the current software and evidence. Requirement authority remains
[`P0_PRODUCT_REQUIREMENTS.md`](../../product/P0_PRODUCT_REQUIREMENTS.md), the
R1 release contract, and LOCKED decisions. The JSON registry remains the
machine-readable status source. Its 17 classifications are all `PARTIAL`; this
document does not promote any use case or change `product_status=PARTIAL`.

`PASS` below refers only to the explicitly named host/software assertion. It
does not imply that a whole P0 use case, target runtime, real sensor, production
service, Android phone, notification delivery, or physical case passed. The
registered P0 aggregate records 26/26 scenario assertions but fails its product
gate while mandatory functionality remains partial.

## Source-linked use-case matrix

| ID / approved use case | Implementation path and input | Software evidence | Status and remaining gap |
|---|---|---|---|
| P0-UC-01 Household creation, caregiver roles and authorization | `backend/ghar_sajag/{identity,homes,foundation}.py`; `tools/sim/pwa/connected_lite.mjs`; local caregiver API | P0-E2E-001/009/014; GS-178 `test_04`, `test_07`; cross-Home access denied in the isolated host E2E | **PARTIAL** — the local actor/session adapter is not production OIDC; invitations and production role lifecycle are not qualified. |
| P0-UC-02 Device onboarding, pairing, identity and lifecycle | `firmware/hub/commissioning/registry/`; `firmware/hub/event_processing/ingest/`; `frontend/src/features/onboarding/`; GS-109 interfaces | Existing ownership lifecycle and commissioning host checks; P0-P2D-010/012/013 registry cases | **PARTIAL** — secure owner commissioning has software/fixture evidence, but caregiver onboarding/claim is absent from the current PWA product flow and physical enrollment is not run here. |
| P0-UC-03 PIR, door and room activity | C3 `firmware/node/sensing/sensing.cpp`, `firmware/node/runtime/node_runtime.cpp`; Hub `firmware/hub/runtime/hub_runtime.cpp`, `firmware/common/shared/src/rules.cpp`; caregiver activity projection | P0-E2E-002/004/017; GS-178 `test_01`, `test_15`, `test_16`; simulated PIR and distinct OPEN/CLOSE/clear chronology | **PARTIAL** — host input exercises production event processing; real PIR/Reed sensing, room mapping and target trigger-to-caregiver are not qualified. |
| P0-UC-04 Event identity, durable journal, delivery and ACK | C3 `firmware/node/storage/node_store.cpp`; Hub `firmware/hub/runtime/`, `firmware/hub/storage/`, `firmware/hub/cloud_sync/`; backend event ingest/commit | P0-E2E-002/003; GS-178 `test_02`, `test_09`; checkpoint recovery tests; Node EventKey stays distinct from Hub decision ID | **PARTIAL** — same-key retry, replay, durable host ACK and COMMITTED path are tested; production credentials/deployment and real target storage remain open. The separate legacy migration stage still fails; see blockers. |
| P0-UC-05 Routine learning and baseline behavior | Deterministic Hub rules: `firmware/hub/routines/routine_service.cpp`, `firmware/common/shared/src/rules.cpp`, `firmware/hub/runtime/`; backend Hub-rule read model | GS-178 `test_06`, `test_10`, `test_13`–`test_16`; morning, night, coverage/clock suppression, door clear and caregiver projection exercised in host software | **PARTIAL** — deterministic rules work in the validated software path. Personalized baselines/longitudinal learning remain on GS-104 R01–R09 approval hold; do not infer a learned baseline. S3 scheduler remains unqualified on hardware. |
| P0-UC-06 Activity coverage, inactivity thresholds and configuration | Hub `firmware/hub/event_processing/coverage/`, `firmware/hub/runtime/time/`, shared rule scheduler; GS-40 test-only local-time adapter | P0-E2E-005/011–016; GS-178 `test_03`, `test_06`, `test_08`, `test_10`; GS-40 bootstrap 47 checks includes trusted-UTC to `Asia/Kolkata` boundary tests | **PARTIAL** — software requires trusted time and covered observations; the scenario backend accepts concern events and does not prove all secure target timers/coverage signals generated them. |
| P0-UC-07 Expected/unexpected activity classification | `firmware/common/shared/src/rules.cpp`; `firmware/hub/runtime/hub_runtime.cpp`; `backend/ghar_sajag/incidents.py`; caregiver UI | P0-E2E-004/005; GS-178 `test_06`, `test_10`, `test_15`, `test_16` | **PARTIAL** — deterministic host rules and presentation are covered; target rule scheduling and physical door semantics remain unqualified. |
| P0-UC-08 NodeHealth, offline/online transitions and recovery | C3 NodeRuntime/contact; S3 HubRuntime/CloudSync; backend `node_health_status.py`, `queries.py`; caregiver Devices view | P0-E2E-011–013; GS-178 `test_03`, `test_08`; 300/910 and trusted legacy-profile boundaries exercised in software | **PARTIAL** — current API/host lease and UI semantics pass; target C3→S3 publication and deployed backend session are not physically or commercially qualified. |
| P0-UC-09 Hub outage versus Internet-only outage | Node retained events, Hub `firmware/hub/cloud_sync/`, backend source freshness and caregiver status | P0-GAP-001; GS-178 `test_02`, `test_03` exercise WAN loss, restart, replay, stale/UNKNOWN and recovery | **PARTIAL** — host durability and recovery path pass; target/local-storage operation and production deployment authentication/recovery remain open. |
| P0-UC-10 Buffering, retry, deduplication and rejoin | C3 `firmware/node/storage/node_store.cpp`, `firmware/node/runtime/node_runtime.cpp`; Hub dedupe/outbox; backend idempotency | P0-E2E-003; GS-178 `test_02`, `test_09`, checkpoint replay; exact retry and conflicting same-key payload behavior | **PARTIAL** — production-code host stack proves Node same-key retry; app-route dedupe and target persistence are separate boundaries. |
| P0-UC-11 Caregiver alerts, notifications and alert recovery | `backend/ghar_sajag/incidents.py`, `notifications.py`; PWA incident/action UI | P0-E2E-005/006/008/017; GS-178 `test_01`, `test_07`, `test_11`, `test_12`, `test_16` | **PARTIAL** — concern creation, claim/acknowledge/resolve and history are exercised; external provider delivery and actual caregiver receipt are not implemented/proven. No call completion is claimed. |
| P0-UC-12 Activity history, chronology, status and dashboard | `backend/ghar_sajag/ingest.py`, `sqlite_events.py`, `queries.py`; caregiver Home/Reports | P0-E2E-007/008/017; GS-178 `test_01`, `test_02`, `test_07`, `test_15`; delayed event chronology asserted | **PARTIAL** — the local API/browser projection displays source event and Hub decisions separately; the connected local lab's service models do not establish production long-term/restart-durable history. |
| P0-UC-13 Caregiver settings and household policy persistence | `backend/ghar_sajag/fleet.py`; PWA routine/settings modules | P0-E2E-015/016 and existing API validation/version checks | **PARTIAL** — input validation/version behavior is covered; durable production configuration, accepted-configuration acknowledgement and complete settings workflow remain open. |
| P0-UC-14 Battery/device health and sleep policy | C3 `firmware/node/power/power.cpp`, `firmware/node/runtime/node_runtime.cpp`; BAT-C8 power path | Existing battery/power host suites and preserved GS-114 BAT-C8 image-scoped evidence | **PARTIAL** — software policy/previous image-scoped behavior are not a current-image power qualification; calibrated battery telemetry, current/RF measurements and caregiver battery projection are unqualified. |
| P0-UC-15 Security, authorization, replay and invalid identities | `firmware/common/security/`, Hub ingest/ownership, backend `identity.py`; GS-168 isolated registry | GS-178 security tests (10), `test_04`, `test_05`, `test_09`, `test_13`, `test_14`; wrong Home, revoked/replaced authority, replay and conflict denied | **PARTIAL** — isolated TEST_ONLY trust and host authentication pass; production OIDC→Hub identity issuance/registry and live deployed security remain open. |
| P0-UC-16 FOTA/control and recovery | C3 `firmware/node/lifecycle/fota/`; Hub target FOTA sender; current host FOTA suites | Existing registered host FOTA/state/artifact checks (see GS-116 reports) | **PARTIAL** — source/host protocol checks are not signed current-image target installation, rollback, bootloader or caregiver FOTA status qualification. |
| P0-UC-17 Multiple devices/households, isolation and bounded operation | Hub `firmware/hub/event_processing/ingest/`; `tests/cpp/multinode_host_validation.cpp`; backend household authorization | P0-E2E-014; GS-178 `test_04`, `test_14`; two-Home denial and old-authority fencing | **PARTIAL** — isolated host authorization is covered; independently enrolled multiple target Nodes, production load and physical room attribution remain open. |

## Current-source changes and focused results

Source commit `94591ab` adds two bounded changes:

1. Under the explicit GS-40 TEST_ONLY S3 build guard, household timezone config
   accepts only `Etc/UTC` and `Asia/Kolkata`. The local-minute helper derives
   from positive authenticated trusted UTC; India is fixed UTC+05:30, which has
   no DST. Unsupported zones, missing time and overflow fail closed. It does not
   use host wall time, mutate process TZ, or establish cryptographic trust.
2. Caregiver startup selects a small dedicated stylesheet and its Connected
   Lite dependency graph before loading the caregiver runtime. The development
   simulator retains its own full stylesheet/app/service-worker cache. The PWA
   profile counts the actual caregiver startup request graph with the existing
   byte budgets, rather than treating development-only simulator assets as
   caregiver startup downloads.

Results on the source commit:

| Command | Result |
|---|---|
| `make -C code gs40-test-only-bootstrap-test` | PASS, 47 checks. Includes signed-zone acceptance/rejection, trusted UTC boundary at India 23:59→00:00, morning local minute, night-window minute, UTC unchanged, invalid/missing time and overflow. |
| `make -C code gs178-software-e2e` | PASS, 27/27; host production-code Node→Hub→backend→caregiver software path. |
| `make -C code hub-runtime-checkpoint-host-test` | PASS, 2 assertion groups, including decision/checkpoint replay and crash-boundary coverage. |
| `python3 code/tools/performance/profile_pwa.py` | PASS; caregiver startup 62,513 bytes (budget 114,688), CSS 6,052 bytes (budget 18,432), JS 29,371 bytes (budget 69,632); no threshold change. |
| `PATH=/tmp/ghar-sajag-gs178-browser-bin:$PATH PYTHONPATH=/tmp/ghar-sajag-gs178-testdeps make -C code pwa-68-browser-test` | PASS, 3 browser tests and 92/92 rendered assertions; offline/unknown caregiver startup and Connected Lite navigation/restrictions. Uses the already-installed pinned `websocket-client` test dependency and Playwright Chromium wrapper. |
| Previous full `make validation-pwa` | PWA component stages included Python 528, JavaScript 32, functional 92, HTTP 17, bridge 13, API 2, frontend 2 and GS-178 27 all PASS. Its browser stage recorded 84 PASS and 2 failures from the old local-simulator service-worker expectation; the assertion was corrected and the affected browser suite now passes. The overall gate still returns FAIL for `product_status=PARTIAL`. |

After the service-worker cache was advanced to v5, the affected checks were
rerun without repeating the PWA aggregate: `python3
code/tools/performance/profile_pwa.py` passed with the same 62,513-byte startup
request graph (CSS 6,052; JavaScript 29,371; manifest/icon 24,958; nine cached
entries). The focused `pwa-68-browser-test` remained PASS at 3 tests / 92
assertions, and the Phase 3A desktop/mobile Playwright regression passed 8/8,
including removal of a stale v4 cache. These results supersede the old
service-worker browser assertion failure for the affected paths; they do not
change the P0 aggregate's PARTIAL status.

The targeted `make validation-hub` execution completed once on source commit
`94591ab51dd393af730c8edcc772838d171a2ff2` (source fingerprint
`d6b52563f59640496ec888a64377f2b24a82bd4dd3fc92421732d3971b7dda6c`, report
`code/evidence/validation_framework/hub-1792421022541396885/report.json`,
833.586 seconds). Its affected implementation and regression stages passed;
the aggregate remains FAIL for the unchanged `clean migration commits`
assertion and mandatory P0 `product_status=PARTIAL` gate. The P0 scenario
assertions themselves were 26/26. No migration assertion or P0 expectation was
changed.

### Source-bound target builds and image provenance

On canonical source commit `cc7d6ab32c756219320777f8afe1592e5a962337`
(`git tree` `75d631cf1b1303dc6b773fe284888da4f42321f9`), ESP-IDF 6.0.3
paired production builds completed without flashing. The C3 image is 937,536
bytes (SHA-256
`384eb4f5b194fb02d3d49044f952d3d7fbb2a01f14ca29d63ea17d06d3aea37d`, slot
1,966,080 bytes). The S3 image is 2,184,704 bytes (SHA-256
`f10393df9bafb78bb419fc8d8be9fb564434e2f93fcfa7323414877bc7b7378c`, slot
4,194,304 bytes); its effective sdkconfig SHA-256 is
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. Build
fingerprint: `7119c9504628631407040f89a0812a0dd86ee8882ad6f4075d8e261a34279afe`.
The report is `code/build/validation_targets/gs116-a1ppl5pl/report.json`.
Both profiles set `GS_HIL_BUILD=OFF`; the standard S3 profile has
`GS40_TEST_ONLY_CLOUDSYNC=OFF` and links `UnprovisionedS3CloudTrust`, which
remains fail-closed.

The isolated GS40 TEST_ONLY S3 product profile also built successfully from
the same source and paired C3 image. Its selected artifact is
`code/build/validation_targets/gs178-p0-cc7d6ab/a/build/gs_r1_s3_hub.bin`,
2,233,392 bytes, full-file SHA-256
`da3b28c54dd9e06e88b25b12a96c0f9fa3f2d80c07c190b6a6fadfa41e2eb1c6`, and
ESP image-validation digest
`294bd9e668ad71870c212a59b030267708d8238e43ed0a63133c3bfa8fde1761` (valid).
It fits the 4,194,304-byte OTA slot. Effective sdkconfig SHA-256 is
`3750bc9360e4524d61d8209e2cbe7014f67be9ee55dcb553033bcc9858c83099`; profile
settings are `GS40_TEST_ONLY_CLOUDSYNC=ON`, `GS_HIL_BUILD=OFF`, and DS
peripheral disabled. Its external TEST_ONLY public config root is 1,097 bytes,
SHA-256 `fe7d71fbe68797fe6fcd28e4364e9cd161005f15befeef4be78b19e0ce355fb0`,
and the paired C3 asset has SHA-256
`384eb4f5b194fb02d3d49044f952d3d7fbb2a01f14ca29d63ea17d06d3aea37d`. The
TEST_ONLY binary contains the exact public root bytes. No private key or
credential was embedded.

With `SOURCE_DATE_EPOCH=1792429200`, the selected TEST_ONLY image and ELF were
reproduced byte-for-byte by a clean rebuild in the same build directory (image
SHA above; ELF SHA-256
`1d07ef7be54055fdf86b015132a0ebd22224f0db7da758e39945b56dedb848ed`). Two
otherwise identical builds in separate absolute build directories produced
different ELF hashes, and the ESP images differed only in the 32-byte embedded
ELF hash and 33-byte image footer. Their code/loadable content was therefore
stable across those builds, but bit-identical output across build paths is not
claimed. Earlier reported TEST_ONLY hashes came from earlier source/profile
inputs: the 2,238,400-byte artifact at source `487ffa03` is not the same source
or effective configuration as this `cc7d6ab` build. This resolves the earlier
unexplained digest difference as distinct source/configuration and path-bound
ELF metadata, rather than an untracked substitution. The image was not
installed or executed on hardware.

The built TEST_ONLY ELF contains `ProvisionedS3CloudTrust` and the guarded
GS40 TEST_ONLY runtime/provider symbols. The standard commercial S3 ELF sets
the TEST_ONLY guard OFF, links `UnprovisionedS3CloudTrust`, and excludes the
TEST_ONLY bootstrap/runtime symbols. This verifies profile separation at
compile/link time only.

Current affected regression results after the PWA cache correction are the
profile and focused browser results above. `make -C code
validation-framework-test` and `make -C code feature-coverage-test` are run
after this matrix/traceability update to verify registration integrity. No
broad aggregate, release gate, phone test or physical case was rerun.

The 3 mobile settings locator timeouts were caused by the development
stylesheet's `.bottom-nav { display: grid }` overriding the HTML `hidden`
attribute before app handlers were attached. `.bottom-nav[hidden] { display:
none }` restores the intended authentication gate. The corrected focused
desktop/mobile phase-3A suite passed 8/8 in the preceding validation run. No
browser output is classified as physical evidence.

## Blockers kept open

- The R1 product gate remains `PARTIAL`: see the JSON gaps above and GS-173
  scope adjudication, especially production caregiver identity/onboarding,
  production registry/deployment, sensor-to-current-target qualification,
  storage/API durability boundaries, notifications and other incomplete P0
  product paths.
- GS-104 R01–R09 personalized learning remains on approval hold. Deterministic
  rules do not satisfy that learning scope.
- `make validation-hub` has a previously recorded failure in the old legacy
  `migrate_legacy_journal` test at `clean migration commits`. The tested input is
  an abandoned legacy journal format, not the R1 fresh-install format. The R1
  contract says arbitrary development-era migration is post-R1, while the
  release validation registry currently requires the migration stage to pass;
  retain the failure and obtain GS-173 adjudication instead of weakening the
  assertion or silently skipping the stage.
- Full browser/Android phone qualification, provider notifications/calling,
  current-image C3/S3 execution and all official physical cases remain separate
  from these host results. GS-40/GS-117/GS-121 physical acceptance is NOT_RUN.
- Production TLS/identity/credential authorities, Secure Boot/Flash Encryption,
  real-target durable behavior and commercial activation remain open; no
  production service or hardware was accessed.

This is a traceable software-readiness matrix, not a release approval. The
executable registry remains authoritative for future status updates.
