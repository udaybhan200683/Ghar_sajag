# GS-40 real-target readiness and production-path audit — 2026-10-16

## Latest follow-up — S3 runtime composition (2026-10-16)

This update follows the original audit and supersedes its claim that the S3
runtime has no publisher composition. At canonical checkpoint
`9d16556bbfe741bd4aa59c3df88a0ba0addca3c8`, the S3 Hub owner now refreshes
bounded NodeHealth snapshots from HubRuntime and a separate network worker
uses the existing CloudSync authority wrapper and HTTPS transport. The
commercial identity/current-ownership, trusted-time and TLS identity providers
are deliberately unprovisioned and fail closed; no live NodeHealth feed is
active. Durable events remain on their existing path with EventKey, ACK, retry,
replay and retirement semantics unchanged.

The HubRuntime-to-CloudSync publisher tests cover authenticated ONLINE and
OFFLINE transitions, strict lease expiry without another packet, the 300/910,
60/190 and 120/310 profiles, session/enrollment and ownership changes, WAN
outage/recovery, retry/backoff and unavailable identity/time. Backend NodeHealth
ingest/read model and caregiver PWA projection passed their focused suites;
the caregiver browser suite passed 86/86. Broader validation aggregates retain
the existing Hub journal migration failure and required P0 `PARTIAL` result.
The final Hub and contract reports are
`code/evidence/validation_framework/hub-1792177423393802158/report.json` and
`code/evidence/validation_framework/contract-1792177035924980667/report.json`;
both record `source_unchanged=true` and the same tracked-source fingerprint.
ESP-IDF 6.0.3 non-flashing S3 build passed at 2,166,688 bytes in its 4 MiB app
slot (image SHA-256
`e39dc13190b8f23d95a82f972ce9a896ce5c9f87a1ea33565ab31ff07e88e1d5`). No
physical operation or production credential/service action occurred.

**Next action:** complete approved D05/D12 Hub identity/key custody, verifier
and current ownership/revocation source; approve D06 trusted Hub time; validate
the deployed trust-provider and owner/network concurrency contract in software.
Only then prepare the exact fixture, board/current-image/config/session and
pending-EventKey provenance, verified non-resetting observer and per-case
approval for PHY-GS40. PHY-GS40-01..06 remain BLOCKED / NOT_RUN. The earlier
source-audit table below records the state before this follow-up; update its
composition-related findings only when a production source is actually
provisioned and tested.

## Disposition

The statements in this original disposition describe the source audit before
the runtime-composition follow-up above.

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
| Backend | `FoundationService.record_health()`, `expire_stale()`, `devices()` and `node_health_policy.py` provide host-side health storage, per-device policy and views. They are not reached from authenticated S3 CloudSync. `http_api.py` is a local WSGI host adapter; `durable_api.py` requires caller-provided trusted Hub authentication. The caregiver `queries.snapshot()` projects Hub event reachability, not per-Node NodeHealth. | Reusable host policy/model exists; production authenticated ingest and caregiver read projection are missing. |
| Caregiver PWA | `code/frontend/src/features/home/index.mjs` and `code/frontend/public/app.mjs` project Hub/events but no per-Node NodeHealth state. | No Node online/offline/unknown coverage projection from authenticated contact. |

The existing Foundation and PWA host suites do not close this path: they
exercise host/simulated state and cannot establish a running S3 publication,
production Hub authentication, or caregiver visibility. Jira GS-109 comment
11172 and GS-148 comment 11173 confirm that the approved production identity,
credential/verifier, and deployment contracts remain incomplete. GS-40 leaves
those decisions and implementations with their owners.

## Minimum authenticated publication and caregiver contract

This is a semantic integration acceptance contract derived from the existing
GS-40 300/910 policy, current coverage semantics, and GS-109/GS-148 ownership.
It does not prescribe a new wire format, cryptographic scheme, credential
lifecycle, or durable-event API.

| Information required end-to-end | Existing source / state | Missing owner or boundary |
|---|---|---|
| Trusted Node identity, authenticated Node transport session, health sequence or authenticated application-contact reference, and contact kind (NodeHealth or already-authenticated event contact) | C3 protocol and Hub ingress decode these; `HubRuntime::observe_authenticated_health/contact()` verifies Node/session binding, monotonic sequence/contact time and maintains per-Node volatile state. | S3 publication must preserve the Hub-accepted identity/session/contact without treating MAC TX success as receipt. GS-148 owns the export; no cloud publisher exists today. |
| Hub principal, Home binding and current ownership epoch, plus a verifier decision | Existing CloudSync authority interfaces model a binding, but the commercial S3 composition has no trusted authority source. A Home ID or HTTP header alone is not proof. | GS-109 D05/D12 owns the accepted Hub identity/key custody and verifier contract; GS-148 must consume that approved result. Candidate mTLS/DS work is not production approval. |
| Effective per-Node timing profile and source of trust for that assignment | C3 config uses the configured 300-second interval and derives 910 seconds; Hub has a per-Node offline-timeout setter; backend `node_health_policy.py` already maps configured, legacy 60/190 and legacy 120/310 policy. | Integrate one trusted identity-to-profile assignment across Hub/backend. Unknown or untrusted identity/profile must remain UNKNOWN. Do not let a Node self-assert a profile. |
| Hub receive timestamp and backend receive/snapshot timestamp, with session/sequence/contact correlation | Hub currently records monotonic receive time in volatile runtime state; backend host `record_health()` accepts a received-contact timestamp and prevents stale/out-of-order health from refreshing liveness. | GS-109 must settle any trusted-time basis needed by the cloud contract; GS-148 must preserve source receive time separately from server receive time and event occurrence time. Do not use send time, retained occurrence time, UI refresh time, or MAC success as a fresh Node contact. |
| Hub Node lease state and source connectivity (Hub, Internet, backend) | Hub runtime has the per-Node lease/profile state. Backend host helpers derive Node status; caregiver snapshot currently has only Hub event reachability. | GS-148 must publish/read a per-Node status and independent Hub/cloud source freshness. Apply configured 300/910 (offline only at strict `age > 910s`), legacy 60/190, and 120/310; keep the separate 190-second Hub/cloud freshness from Node lease policy. |
| Backend caregiver projection: Node ONLINE/OFFLINE/UNKNOWN, coverage COVERED/UNKNOWN, last authenticated contact, effective profile/lease, and freshness/source state | Backend host model has parts of the health policy/storage; `queries.snapshot()` does not return per-Node NodeHealth. | GS-148 owns authenticated health ingest, read model/API and caregiver projection. Health publication must be additive to CloudSync and must not create synthetic events, EventKeys, ACKs, or alter durable event commit/retirement. |
| PWA rendering of the same per-Node identity/contact/status plus a distinct resident-activity signal | Current Home PWA shows Hub/event-derived home state, not per-Node NodeHealth or monitoring coverage. | GS-148 owns the production response contract and PWA projection. No resident motion must remain distinct from missing sensor coverage; stale/untrusted source is never shown covered. |

The minimum end-to-end result is therefore: a currently authorized Hub
publishes a newly authenticated Node application contact for the registered
Node/profile; backend accepts it only under the approved Hub/Home/epoch
authority and retains correlated source and server times; backend derives the
per-Node lease and coverage without changing Node liveness policy; caregiver
snapshot and PWA display that same identity/contact/status with Hub/cloud
freshness independently visible. Event durability/ACK behavior remains on its
existing path.

### Existing seven-case runner compatibility

`assess_observation_bundle()` already consumes a normalized timing/status view
with `schema_version`, `captured_at_utc`, `node`, `hub`, `backend`, and `pwa`
layers. The contact carries Node identity, authenticated flag, session,
contact ID and Hub-received time; the downstream layers carry the matching
contact, liveness/coverage state, source reachability, cloud contact time and
PWA snapshot time. It applies the existing configured 300/910 and legacy
60/190, 120/310 profiles, plus independent 190-second source freshness; this
does not modify product policy.

The normalized view is sufficient for the existing seven cases' timing,
status, outage, recovery and UI assertions. Schema v1 was not the complete
trust evidence contract: it did not name/correlate the Hub principal, Home,
ownership epoch, trusted profile assignment, contact kind, or separate backend
receive timestamp. It was therefore superseded for correlated observations by
observation-bundle schema v2. The v2 validator requires Hub/Home/epoch binding
to match across Hub, backend and PWA; the trusted profile must be assigned by
the Hub and preserved downstream; contact must be authenticated NodeHealth or
authenticated event application traffic; and Hub receive time must remain
separate from backend receive and PWA snapshot time. Older v1 bundles are
BLOCKED, not silently accepted. This changes the evidence adapter only; it
does not change Node cadence, Hub lease, backend product policy, or CloudSync.

The schema remains a normalized assertion format, not an authenticator. A JSON
claim cannot establish that the GS-109 Hub verifier approved the authority.
`LIVE_CURRENT_TARGET` remains BLOCKED without an approved source provider, even
when every field is internally consistent. The Hub UTC receive-time mapping
also remains dependent on the unresolved D06 trusted-time contract; synthetic
HOST_PASS does not validate that mapping for production.

### Integration acceptance checks for GS-109/GS-148 delivery

1. Reject missing, untrusted, revoked or wrong-Home/epoch Hub authority; do not
   update Node health or show the Node healthy.
2. Bind every contact to the registered Node identity and authenticated
   session. Reject stale/replayed health sequence/contact; MAC-level success
   alone never refreshes the lease.
3. Carry Hub receive time, backend receive time, health sequence/contact ID,
   Node identity and effective trusted profile through backend and PWA. Keep
   these separate from Node occurrence/send time and UI fetch time.
4. Use configured 300/910, legacy 60/190 and legacy 120/310 per trusted Node;
   keep unknown identity/profile UNKNOWN. Verify 910 is ONLINE at the
   inclusive boundary and OFFLINE only after it.
5. Show ONLINE only for a current authenticated contact; after a silent Node
   lease expires, show Node OFFLINE while the Hub/cloud source remains
   reachable. Do not confuse that with resident inactivity.
6. Distinguish Hub unreachable from Internet/backend unreachable. When the
   caregiver cannot receive a fresh authoritative projection, coverage is
   UNKNOWN and must not remain falsely COVERED; preserve last-source ages.
7. Verify authenticated event contact piggyback/suppression without changing
   event priority, EventKey, durable-before-ACK, retry, replay, or retirement.
8. Rejoin the same Node/session policy without a new motion requirement;
   preserve pending EventKeys and chronological order, reject replay, and
   restore caregiver status only after fresh authenticated contact.
9. Verify backend's caregiver snapshot and actual PWA rendering for ONLINE,
   OFFLINE and UNKNOWN, with the exact same Node/contact/profile and
   timestamps. Prove resident inactivity does not change coverage.
10. Run these as production-code Hub-to-CloudSync-to-backend-to-PWA contract
    tests, including mixed profiles and missing/untrusted identity; synthetic
    runner HOST_PASS does not satisfy this acceptance.

### Existing evidence reuse and physical TC01–TC06 order

Reuse, without rerunning, the recorded GS-114 C8 evidence only for the claims it
actually establishes: C8-P1 is ten C3 timer sleep/wake cycles and authenticated
post-wake NodeHealth at the Hub; C8-P2 is real AM312 motion with one durable
EventKey admission, authenticated ACK and retirement over ESP-NOW while C3 USB
was unavailable. These results show that native C3 USB disappearance does not
mean Node/radio failure. They do not show six quiet opportunities, the 910-second
lease, event-health suppression at a due opportunity, current image/config,
mixed profiles, or caregiver visibility. Catalogue HIL-A03 additionally has
one recorded 300-second authenticated health opportunity for its own attempt06
fixture; it is at most one image-scoped sample, not a six-opportunity TC01
result. None of these records identifies the presently installed images.

After the GS-109/GS-148 contract tests pass, a non-resetting observer is
available, and the board/image/config/session/pending-event provenance is
verified, execute in this order. Capture one timestamped correlated evidence
bundle continuously; keep each case's verdict separate:

1. **TC01 / PHY-GS40-01:** baseline the enrolled C3/S3 identities, image
   hashes, effective config/profile, session and pending EventKeys. Observe six
   quiet 300-second opportunities (nominally 300 through 1800 seconds); record
   schedule, Hub-authenticated receipt and backend/PWA observation for every
   unique contact. Reject duplicate/missing/unauthenticated reports and false
   offline transitions. C8-P1/HIL-A03 can only support their recorded
   image-scoped subclaims.
2. **TC02 / PHY-GS40-02:** at a due health opportunity, use one explicitly
   approved real sensor motion and correlate the MAC result, authenticated Hub
   application acceptance, EventKey/durable ACK state and health scheduler.
   Prove only authenticated event contact suppresses the redundant standalone
   health report. Reuse C8-P2 for its event/durability subclaims; do not repeat
   that motion test merely to reprove EventKey ACK.
3. **TC03 / PHY-GS40-03 then TC04 / PHY-GS40-04:** first record a non-empty
   pending EventKey baseline if the case is to claim pending-event preservation.
   With the Node powered and using a specifically approved NVS-preserving
   silence method, retain the Hub and Internet as controls; observe immediately
   before, at 910 seconds, and just after strict `>910s`. Then restore the same
   Node through normal rejoin without new motion; correlate new authenticated
   contact and restored PWA coverage, compare pending EventKeys before/after,
   and verify chronology/replay rejection. If no pending key exists or the
   authorized silence/recovery method cannot preserve identity, that subclaim
   remains NOT_RUN; do not reset or clear storage.
4. **TC05 / PHY-GS40-05:** require at least two independently identified and
   enrolled C3 Nodes as the catalogue states, with trusted profile assignments
   and the Hub observing them concurrently. Exercise legacy 60/190,
   legacy 120/310 and configured 300/910 boundaries plus an unknown/untrusted
   identity. If all three profiles must be concurrent, provide three Nodes or
   an approved qualified fixture. Two Nodes cover all three across separate
   rounds only if owner-approved trusted profile reassignment is available;
   otherwise use three Nodes or the approved fixture.
5. **TC06 / PHY-GS40-06:** use the actual caregiver account/PWA and production
   API throughout TC01–TC05. Verify online, silent-Node offline, and unknown
   coverage for Hub disconnection and Internet/backend outage; correlate
   displayed status, identity, last authenticated contact and source ages to
   backend. Network changes/outages require explicit approval; do not infer a
   Node failure from an unreachable source.

Stop before any physical case if identities, effective profile, running image,
session, pending-event baseline or the trustworthy observer are unknown. The
current one-C3/one-S3 bench can support TC01–TC04 and TC06 after those gates;
it cannot meet TC05. The active Hub image must contain the GS-148 publication
path; because that path is absent from current S3 composition, a matching Hub
firmware installation is expected after implementation unless a future
verified image already contains it. Any flash/install requires its own exact
authorization. No hardware operation is authorized by this assessment.

## Reusable observation-bundle adapter

`code/tools/hil/gs40_qualification.py::assess_observation_bundle()` accepts
normalized, timestamped Node, Hub, backend and PWA observations. It is a pure
validator; it does not open a device or connect to a service. It checks:

- common Node identity and Hub-accepted contact/session correlation through
  backend and PWA snapshots;
- Hub, Home and ownership-epoch binding, Hub-assigned Node profile, and
  authenticated authority state carried consistently through the projection;
- explicit authenticated contact, so MAC send success cannot renew the lease;
- contact kind and Hub receive time, retained separately from backend receive
  time and caregiver snapshot time;
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

At the original readiness checkpoint: Python compilation PASS; 4 focused tests
PASS. Those results remain historical and were not rerun as a mock/replay
campaign.

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

## Additive CloudSync integration contract and focused adapter validation — 2026-10-16

**Scope classification:** `TEST_INFRA_ONLY`. Requirement sources are existing
GS-D031 and GS-40 acceptance/comments 11175/11176. This increment changes the
GS-40 observation evidence schema only. It does not add a CloudSync endpoint,
credential/verifier, backend storage/API, product liveness policy, event, or
PWA behavior.

The production owner map remains: GS-109 supplies the verified current Hub,
Home and ownership-epoch authority plus trusted identity/profile assignment;
GS-68 carries additive bounded status through its existing trusted CloudSync
channel; GS-148 owns production publication, backend ingest/read model and PWA
projection. Each publication is one bounded current-state record for one
registered Node; numeric payload and registry-member caps must follow GS-148's
accepted storage/resource limits. Status is not a business event and cannot
create an EventKey, durable ACK, replay entry, or event-retirement side effect.
The Hub must be able to publish the derived OFFLINE transition after lease
expiry without waiting for another NodeHealth report. No PWA/backend
implementation exists in current production source, so a production
end-to-end contract test is still blocked.

Observation-bundle schema v2 now requires: a common Hub/Home/ownership-epoch
binding across Hub/backend/PWA; the Hub-assigned profile to match the trusted
deployment profile and be preserved by backend/PWA; Node identity, authenticated
session, contact ID and contact kind (`NODE_HEALTH` or `AUTHENTICATED_EVENT`);
explicit Hub contact receive time; a separate backend receive time carried into
the PWA; and current source timestamps. Unverified authority/profile, MAC-only
contact, source-binding mismatch or stale source cannot yield healthy/covered
status. Configured 300/910, legacy 60/190 and 120/310 lease behavior and separate
190-second Hub/cloud freshness are unchanged. Schema-v1 correlated bundles are
BLOCKED rather than treated as sufficient. The adapter's UTC contact-age
calculation is usable for deterministic fixtures only; D06 time authority and
the production source attestation still block live evidence.

**Notification requirement check:** Jira search found no dedicated configurable
sensor-offline caregiver notification issue, and current `NotificationService`
only schedules incident/door notices and daily summaries. GS-40 requires visible
coverage state, not an implied push/SMS alert. If a configurable alert is wanted,
create a separate product-approved task linked to GS-40/GS-148 to define
recipient, delay, quiet hours, deduplication, recovery/clear and channel policy.
No new Jira issue was created because those semantics are not specified.

**Focused validation (canonical source commit `a110228b22ff35d53e3ab709364c0ce21977cd92`, branch `feature/r1-commercial-baseline`):**

```text
python3 -m py_compile tools/hil/gs40_qualification.py tests/python/test_gs40_qualification.py
python3 -m unittest -v \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_observation_adapter_correlates_300_910_status_and_separates_connectivity \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_observation_contract_binds_hub_home_epoch_node_profile_and_backend_time \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_observation_contract_rejects_contact_kind_and_receive_time_rewrite \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_observation_adapter_rejects_uncorrelated_or_live_unattested_status \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_source_audit_distinguishes_authenticated_radio_ingress_from_missing_cloud_path \
  tests.python.test_gs40_qualification.GS40QualificationRunnerTests.test_live_mode_blocks_without_any_device_access_or_physical_pass
```

Result: compile PASS; 6 focused test methods PASS. Feature-map integrity
also passed (207 features, 216 modules, 24 physical cases; 22/22 mapping
tests). The observation matrix covers
14 states, including configured 910 boundary, legacy 190/310, Hub disconnect,
Internet loss, stale Hub/backend/cloud/PWA sources, missing/untrusted identity,
unverified Hub/Home/epoch, missing application contact and recovery-safe
UNKNOWN. Negative checks reject mismatched Home, stale/untrusted profile,
MAC-only contact-kind substitution, backend-time omission and receive-time
rewriting. The live gate still reports BLOCKED with zero device actions. The
seven-case mock campaign, Jira 11158 replay, Node/Hub/backend/PWA product suites
and BAT-C8 physical results were not rerun or changed.

**Remaining blockers:** production D05/D12 Hub authority/verifier and D06 time
contract; GS-68 producer integration through the existing CloudSync transport;
GS-148 authenticated ingest, freshness read model and PWA projection; verified
current board image/config/session and safe observer; TC05 second trusted Node
or fixture. All PHY-GS40-01..06 remain BLOCKED/NOT_RUN and GS-40 remains In
Progress.

## Follow-up — provider seam and physical prerequisites — 2026-10-17

The later canonical integration now includes GS-68's bounded HubRuntime to
CloudSync NodeHealth publisher and the backend/PWA software projection. The
prior paragraph's GS-68 producer/GS-148 ingest/PWA items are superseded as
software implementation gaps; they remain TEST_ONLY/software evidence, not a
deployed commercial path. The S3 product is wired to one shared trust-provider
seam but uses `UnprovisionedS3CloudTrust`, so production NodeHealth cannot be
sent. The app lacks the provisioned CloudSync endpoint/trust root and approved
credential/authority/time providers.

Latest focused checks: D05/D12/D06/GS-40 provider integration passes under
TEST_ONLY fixtures; mTLS adapter 9/9, backend security 14/14, NodeHealth API
5/5, C++ 1,509 checks, durable EventKey contract, and local mTLS worker/API
bridge 1/1 pass. Validation framework is 47/47; traceability is 208 features,
220 modules, 24 physical cases and 22 mapping tests. The non-flashing ESP-IDF
6.0.3 S3 `GS_HIL_BUILD=OFF` production-profile image is 2,168,128 bytes, fits
the 4 MiB app slot and has SHA-256
`2052ba8d233b66bd753d5f6572c01acd4a4cd3daf6017dde70c27d628fde69b5`; its
sdkconfig SHA-256 is
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. It
embeds the unchanged previously validated C3 image (937,536 bytes, SHA-256
`d94e011abd0e28b31cadb4dee2ff6451b0f5311c2783cdcbb2a631c03e86f765`). The
build used project version `gs68-provider-20261017`; source commit
`42f74034d5f1f5acd2c605ffee37f540da42ef7e` was pushed to the canonical branch.
Jira evidence: GS-40 comment `11288`, GS-68 `11286`, GS-109 `11287`.
Managed-component file hashes were identical
before and after. Prior caregiver browser result remains 86/86; it was
not rerun because PWA code/contracts were not changed.

**Still BLOCKED:** GS-40 PHY-01..06 and GS-68-PHY remain NOT_RUN. S3/C3 fixture
identity/provenance, board revision and electrical/pinout verification, current
installed-image/config/session verification and a named safe reset-free
observer/recovery path need owner evidence and case-specific authorization.
GS40 TC05 still needs a second enrolled Node or an approved profile fixture.
Production prerequisites remain D05 CA/issuer and current Home/epoch/revocation
source; D12 actual protected DS/eFuse custody and TEST_ONLY credential fixture;
D06 approved signed bootstrap/verifier/CSPRNG nonce source, durable target
counter/floor and freshness/floor-checkpoint thresholds; deployed trust mapping
and live credentials/endpoints. No physical action occurred; no physical
approval is implied by this software update.


## GS-68 D05/D12/D06 provider software addendum — 2026-10-17

The existing GS-168 TEST_ONLY issuer now supplies certificate-fingerprint
registry lookup to backend TLS authorization; tests cover active, revoked,
unknown, expired and wrong-source credentials. The S3 provider validates
RSA-3072 ClientAuth certificate material and rechecks Home/epoch/credential
revision. D06's RSA-3072/SHA-256 proof verifier, PSA CSPRNG nonce, boot
binding and floor/reboot/rollback behavior pass focused host validation. The
issuer and time-authority keys are ephemeral TEST_ONLY fixtures. The product
still instantiates `UnprovisionedS3CloudTrust`; no production path is enabled.
See `GS68_D05_D12_D06_PROVIDER_E2E_20261017.md` for proof layout, test results,
production approvals and physical case criteria.

This does not change physical disposition: **NO-GO / NOT_RUN**. No board or
interface was accessed. The S3/C3 fixture IDs and provenance, installed-image
hash/runtime receipt, current enrollment/session/profile, reset-free observer,
recovery owner and fixture-specific written authorization remain missing.
GS-40 TC05 still requires a second independently enrolled Node or approved
profile fixture. GS-68 physical cases additionally require the approved D05,
D12 and D06 sources, and GS68-PHY-010 remains with GS-118/D15 signed-image and
rollback approvals. No physical result is inferred from host crypto or build
validation.

The 2026-10-17 paired non-flashing ESP-IDF 6.0.3 software build passed after a
Mbed TLS 4 PSA API compatibility correction. C3 app SHA-256 is
`b4e2b1c1d370fd2da2a30aae52cfbc2f85e91d0ff3b39da41eef23816829fedb`; S3 app
SHA-256 is `e09e9651160719673958fffdc5c06f7a1787eb31403384324fd421b8f15a3ea1`.
This is a candidate artifact receipt only; it does not establish that this
image is installed on a fixture. Provider tests, GS-40 backend/caregiver path,
local mTLS bridge, simulation, validation framework and feature mapping
results are documented in `GS68_D05_D12_D06_PROVIDER_E2E_20261017.md`.
