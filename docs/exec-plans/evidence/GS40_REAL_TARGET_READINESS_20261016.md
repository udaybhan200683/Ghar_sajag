# GS-40 real-target readiness and production-path audit — 2026-10-16

## Disposition

**Software:** The completed GS-40 automation branch is reconciled into the
canonical R1 branch. A reusable, pure observation-bundle validator and focused
tests are added. The live runner remains fail-closed and does not access
hardware or the network.

**Production path:** NOT READY. Authenticated NodeHealth currently stops at the
S3 Hub's local volatile lease/contact state and logs. There is no active
production Hub-to-backend NodeHealth publication, backend freshness read model,
or caregiver PWA NodeHealth projection. GS-109 owns the trusted Hub identity
and verifier decisions; GS-148 owns the CloudSync/backend integration. Adding a
second credential, verifier, durable API, or event commit under GS-40 would
cross those ownership boundaries and is not safe.

**Physical acceptance:** No GS-40 physical test ran. No `PHYSICAL_PASS` was
created. GS-40 remains In Progress. Existing BAT-C8 GS-114 evidence was
preserved without rerun or modification.

## Branch and worktree reconciliation

- Canonical path: `/home/udaybhan/projects/Ghar_sajag_r1`
- Canonical branch: `feature/r1-commercial-baseline`
- Starting HEAD: `d738dc51a25e72de570a11fc39f0e26522ead3d8`
- Completed automation branch: `codex/gs40-qualification-20261016`
- Reconciled commit: `9453587383215e62628e436a20b10648a923410f`
- Relationship: exactly three commits ahead; canonical had no unique commit;
  fast-forward only.
- The separate GS-109/GS-68 worktree at
  `44838da836d3014e606cfe2ee57ad624ee417240` was not changed or merged.
- Existing untracked PWA assets, managed components, GS-114 evidence, and the
  historical GS-40 S3 UART capture were preserved. No cleanup or evidence
  replacement occurred.

## Source audit: NodeHealth to caregiver

| Layer | Source finding | Result |
|---|---|---|
| C3 Node | Configured profile is 300-second NodeHealth with event piggyback. Authenticated Hub receipt, not MAC TX success, is the relevant contact. Current board image/effective JSON/session are not verified. | Source policy exists; target identity/config remains unknown. |
| S3 Hub ingress | `code/firmware/hub/target/esp32/hub_runtime_adapter.cpp` decodes NodeHealth and calls authenticated HubRuntime ingress after transport/session checks. | Present. |
| Hub lease | `code/firmware/hub/runtime/hub_runtime.cpp` tracks NodeHealth and authenticated contact in volatile maps; target logs are local. | Present locally; restart persistence/cloud export are not established. |
| CloudSync | `code/firmware/hub/cloud_sync/cloud_sync.*` implements durable event synchronization. `code/firmware/hub/target/esp32/idf/main/app_main.cpp` does not instantiate `CloudSyncWorker` or a trusted cloud authority source. No NodeHealth publisher exists. | Missing in production target. |
| Backend | `code/backend/ghar_sajag/http_api.py` is a local WSGI host adapter. `durable_api.py` requires caller-provided trusted Hub authentication and does not implement it. `queries.py` has no NodeHealth projection. `DATA_MODEL.md` describes tables/target direction, not active S3 deployment composition. | No production authenticated health ingest or freshness read model. |
| Caregiver PWA | `code/frontend/src/features/home/index.mjs` and `code/frontend/public/app.mjs` project Hub/events but no per-Node NodeHealth state. | No Node online/offline/unknown coverage projection from authenticated contact. |

The existing Foundation and PWA host suites do not close this path: they
exercise host/simulated state and cannot establish a running S3 publication,
production Hub authentication, or caregiver visibility. Jira GS-109 comments
11172 and GS-148 comment 11173 confirm the relevant identity/API ownership and
that the related source remains incomplete. GS-40 leaves those decisions with
their owners.

## Reusable observation-bundle adapter

`code/tools/hil/gs40_qualification.py::assess_observation_bundle()` accepts
normalized, timestamped Node, Hub, backend and PWA observations. It is a pure
validator; it does not open a device or connect to a service. It checks:

- common Node identity and Hub-accepted contact/session correlation through
  backend and PWA snapshots;
- explicit authenticated contact, so MAC send success cannot renew the lease;
- configured `>910s` offline boundary and legacy `>190s` / `>310s` boundaries;
- the independent 190-second Hub/cloud freshness limit;
- Hub disconnection, Internet outage, stale PWA data, unknown profile, missing
  contact, and untrusted identity remain UNKNOWN/coverage UNKNOWN;
- online/covered claims fail if the correlated source is stale, mismatched,
  untrusted or unauthenticated.

Synthetic input may produce only `HOST_PASS`. A JSON claim of
`LIVE_CURRENT_TARGET` remains `BLOCKED` because no production provider
attestation is available. Assertion mismatches are `FAIL`. This adapter does
not claim physical verification. The existing `live` execution mode still
stops before device/network access when the source audit finds the missing
CloudSync/backend/PWA path.

## Focused validation performed

From `code/`:

```text
python3 -m py_compile tools/hil/gs40_qualification.py tests/python/test_gs40_qualification.py
python3 -m unittest \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_source_audit_distinguishes_authenticated_radio_ingress_from_missing_cloud_path \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_observation_adapter_correlates_300_910_status_and_separates_connectivity \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_observation_adapter_rejects_uncorrelated_or_live_unattested_status \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_live_mode_blocks_without_any_device_access_or_physical_pass
```

Result: Python compilation PASS; 4 focused tests PASS. The adapter truth table
includes 10 states/subcases, including configured 910 boundary, silent Node,
legacy 190/310 expiries, Hub disconnected, Internet outage, unknown profile,
untrusted identity, missing authentication, stale PWA, and source/session
mismatch. The live-mode unit test mocks Git identity reads and uses a temporary
output directory; it records zero device actions. No full mock/replay campaign,
backend suite, PWA browser suite, or hardware operation was repeated.

The qualification source fingerprint for this validated working tree is
`599baba2e682d65f4b21790e5f06b0dfd5b7f9e403d3c202c28d85ae37cbb97e`.

Prior completed automation-branch results remain as recorded in
`GS40_AUTOMATED_QUALIFICATION_20261016.md`: seven mock cases HOST_PASS (26/26
assertions), Jira 11158 historical replay (6 checks), live cases BLOCKED with
zero device actions, and its previously recorded affected validation stages.
Those prior results were not rerun or promoted by this follow-up.

## Historical CH343 observation and BAT-C8 preservation

The existing Jira 11158 capture records one receive-only 115200 CH343 open,
zero application transmit bytes, then a `rst:0x1 (POWERON)` banner 257 ms into
the captured interval. pySerial 3.5 requested DTR/RTS low after opening the
descriptor. The board's reset wiring and CH343/USB-IP/driver control-line
transitions were not measured. No pre-open UART stream establishes whether a
reboot was already underway; USB/IP remained Attached afterward. The open may
have contributed, but causation is unproven. No second open was attempted.

C3 native USB Serial/JTAG can disappear when the C3 enters light sleep. That is
observer loss, not Node outage. Ordinary Node-to-Hub ESP-NOW observation does
not require opening C3 USB. S3 UART is not a proven safe live observer, so the
future plan must rely on an approved read-only telemetry provider that does not
toggle reset/boot control. No C3 USB open, S3 serial open, USB/IP reattach,
reset, flash, power change, motion stimulus or induced outage occurred here.

Existing GS-114 BAT-C8 C8-P1/C8-P2 evidence remains unchanged: ten C3 timer
sleep/wake cycles followed by authenticated Hub NodeHealth, and one real AM312
motion EventKey durably admitted/ACKed/retired over ESP-NOW while C3 USB was
unavailable. Its existing image hashes and evidence are not GS-40 qualification
and were not repeated.

## Physical case plan after blockers are cleared

| Case | Physical observation plan | Current disposition / prerequisite |
|---|---|---|
| PHY-GS40-01 | With a verified current C3/S3 image, effective 300/910 config, trusted identity and session, observe six quiet opportunities at 300-second intervals (30 minutes). Correlate six unique authenticated Hub contacts through backend and caregiver PWA. | BLOCKED: no production source-to-PWA path or safe live source; running image/config/session unverified. |
| PHY-GS40-02 | Use one explicitly authorized genuine sensor motion. Correlate authenticated event acceptance and verify event contact suppresses the redundant standalone health report. Do not count MAC success alone. | BLOCKED: motion stimulus approval, live path and safe observer required. |
| PHY-GS40-03 | Keep the Node powered and silent by an explicitly authorized, NVS-preserving method; record just before, at 910 seconds and after the strict `>910s` boundary. Independently record Hub reachability and Internet state. | BLOCKED: approved silence method and observer needed; do not improvise a power interruption. |
| PHY-GS40-04 | Restore Node contact through its normal rejoin path. Capture authenticated session/contact recovery and compare pending EventKeys before/after to prove no loss, replay or reordering. | BLOCKED: authorized return/rejoin plan and pending-event baseline needed; no reset/NVS action. |
| PHY-GS40-05 | Run concurrently with separately trusted Node identities for explicit legacy 60/190, legacy 120/310 and configured 300/910 profiles. | BLOCKED: current equipment has one C3. Requires a second valid C3 Node or approved qualified fixture. |
| PHY-GS40-06 | Capture actual backend API and caregiver PWA online, offline and unknown states with the same identity/session/contact and timestamps. Repeat for Hub disconnected and Internet unavailable. | BLOCKED: production backend/PWA projection is absent. |
| GS40-TC07 | Keep host/replay-only; validate reset, USB identity, busy port, transport loss, truncation and timestamp-gap stop behavior. | Host/replay validation only; not physical acceptance. |

Before executing any physical case, close GS-109 identity/verifier and GS-148
publication/read-model ownership, register a trustworthy non-resetting
observer, and verify exact board/image/config/session/pending-event provenance.
Then obtain one consolidated authorization for the specified real motion,
silent interval and recovery procedure. No board operation is authorized by
this readiness work. GS-40 remains In Progress and Done criteria are unmet.
