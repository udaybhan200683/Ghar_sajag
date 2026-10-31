## GS-117 — SDK-specific ESP-NOW transmit analysis — 2026-10-31 06:56 UTC

Context preflight PASS; starting local/remote HEAD `301f277a6401630cd443c2929342c17fddb006b2`, canonical worktree and branch, tracked clean. Owning Jira GS-117; BUG_CLASSIFICATION=INVESTIGATE_ONLY. Offline investigation only; no device access, firmware changes, policy activation or ledger changes.

The installed SDK is ESP-IDF 6.0.3 at `/home/udaybhan/.espressif/v6.0.3/esp-idf` (verified against the completed target build's project_description.json). Its esp_now.h specifies channel 0 as the current STA/AP channel, ESP_ERR_ESPNOW_IF/CHAN for peer interface/channel mismatch, and no caller-buffer lifetime requirement after send returns. Its bundled esp_now.rst warns that callbacks may be disordered when sends overlap and MAC delivery does not prove application acceptance.

Source/evidence inventory: HubSecurityLink validates the exact registry/MAC/Home/Hub/logical/session binding and installation-key HMAC before returning RejoinChallenge. The Hub adds absent peers on WIFI_IF_STA, channel 0, native encryption off because application authentication protects the handshake. Existing peers are reused without inspecting/updating metadata. Challenge bodies are 64 bytes (v1) or 68 bytes (v2), plus a 12-byte header: one 76/80-byte packet, below 250. The owner submits once per received hello and waits up to 1000ms for the send callback; C3 owns bounded hello retries and channel discovery. No extra Hub retry was added.

Both saved C3 sessions sweep channels 1 through 7 with matching delivery flags. Session 127 subsequently sends RejoinFinal on channel 7 at C3 uptime 38387ms, challenge_pinned=1; session 129 continues hello attempts on channel 8 at 45747ms and channel 9 at 65897ms, without a pinned challenge. Hub failures occur at its uptime 48736/48816/48926ms. C3 and Hub boot clocks must not be directly subtracted; saved output does not establish exact cross-device queue latency. The earliest proven divergence remains challenge delivery, not different initial C3 channel selection or a sensing failure.

Ranked unresolved hypotheses: (1) channel availability/hello processing timing or MAC delivery loss while C3 scans; (2) peer-add/ESP-NOW submit errors, including stale peer metadata; (3) callback attribution or late callbacks. The callback stores only a Boolean in one shared queue, and other ACK/FOTA/runtime sends use the same registration; it cannot prove which outstanding transmission completed. This is a source-supported diagnostic limitation, not a confirmed cause in session 129. Fragment size/buffer lifetime and backend time/authority gating are unsupported causes: the challenge is small, buffer ownership is permitted by this SDK, and HubSecurityLink's rejoin path has no trusted-time/lease dependency. Backend publication remains separately fenced by time/authority checks.

The existing 70d577e diagnostics uniquely distinguish peer_add, wire_fragment, esp_now_submit, callback timeout and callback failure and preserve ESP error names. Receive channel comes from rx_ctrl; it is not a measurement of the current transmit channel. Callback failure is an uncorrelated global callback result under the present implementation. Logs expose no keys, payloads or credentials and execute only on failure outside the Wi-Fi callback. Collector retention and compilation evidence remain applicable. No speculative transport change is justified before observing the failed stage.

Gate RCA: separate make processes share `build/obj/<product>/<profile>/tests/support/host/multinode/scheduled_harness.d.tmp` and `.o.tmp`; identical profiles do not isolate concurrent writers, and the Makefile has no cross-process lock. Serialize these gates. The modified IDF adapter is not linked into those host test binaries; the existing commissioning assertion, journal migration failure and sanitizer timeout remain unresolved gate failures rather than demonstrated regressions from diagnostic logging. The sanitizer timeout under contention is inconclusive and needs an isolated owning-gate rerun before release PASS; no full gate or sanitizer PASS is claimed here.

Authorization remains SAFETY_LATCHED. Generic ValueError classification preserves the failure conservatively; absence of authenticated rejoin is not enough to declare either successful readiness or a credential violation. The existing audited disposition only handles the exact pre-operation pin-mismatch case, not this post-operation readiness guard. No classifier/latch change or new authorization mechanism was made.

No new tests/builds were needed for this documentation-only investigation. Reused evidence: GS-117 136/136, framework 55/55, paired production-profile target compilation; incomplete Hub/contract results retained. Production-profile S3 artifact 56264ff1… is not a TEST_ONLY deployment candidate. Future diagnostic deployment requires a correctly profiled build of reviewed diagnostic source, exact artifact hash/pins, existing app-only flash/rollback safeguards and explicit successor scope after preserving the latch. One protected S3 runtime restore and one deliberate C3 restart with a 90-second observation should then collect the failing stage and actual authenticated final/rejoin/liveness, plus separate target time/authority proof. No campaign is authorized by this record. TC-001 0/5; historical 126/1 remains supplemental; 123/1 latency unresolved.

Jira comment 11867 was posted and read back; GS-117 remains In Progress. All pre-existing untracked files and private ledgers are preserved.

## GS-117 — Offline C3/S3 rejoin differential; target-send diagnostics added — 2026-10-31

OWNING_JIRA=GS-117; RELATED_JIRA=GS-179, GS-116, GS-130, GS-173
BUG_CLASSIFICATION=TEST_INFRA_ONLY
READINESS_OUTCOME=BLOCKED; TC-001=0/5; HARDWARE_ACCESS=PROHIBITED_WHILE_SAFETY_LATCHED
REQUIREMENT_SOURCE=GS-117 authenticated Node-to-Hub and physical acceptance criteria; no acceptance or security rule changed
DECISION_IDS=NONE
TASK_SCOPE=Compare preserved good/failed target observations offline and add bounded diagnostic detail to the existing S3 authenticated-control transmission failure log.
OUT_OF_SCOPE=COM access, reset/bootstrap/flash/readback, event injection, latch/ledger edits, security/protocol changes, campaign execution.

Existing functionality → actual gap → minimum change: the S3 already authenticates the C3 rejoin hello and constructs the challenge; existing generic send-failure logging did not identify which lower-level transmission step failed. The existing bounded serial collector already retains `Authenticated` lines. The S3 log now records the failure stage, message kind, received channel and ESP error/callback outcome for peer-add, wire-fragment, ESP-NOW submission and callback failure. The protocol, retries, authentication, and stop behavior are unchanged. A focused collector regression ensures this evidence survives capture.

Differential result from private session-127 success and session-129 failure: both show the expected C3 image/app, OTA slot, serial-open reset reason, and initial authenticated `RejoinHello` (`kind=6`). In session 127 the C3 later sent `RejoinFinal` (`kind=8`); the S3 recorded the authenticated Bedroom rejoin, then C3 runtime/sensing counters advanced. In session 129, no `RejoinFinal` appeared; S3 logged three authenticated-control reply delivery failures while attempting the challenge (`kind=7`). This is the earliest evidenced divergence. The exact lower-level send stage was not recorded by the old image and remains unknown until a future authorized run with the diagnostic log. No evidence supports a C3 sensing-loop defect.

Source confirms NodeRuntime waits for `security_link.ready()` before starting the normal runtime/sensing loop and updating those liveness counters. Therefore the zero counters in session 129 are a downstream consequence of rejoin not completing; they do not establish a runtime or PIR initialization failure. The 430-second timeout applies to already-associated idle recovery, not this initial rejoin. Session 127's successful sequence supports the existing rejoin mechanism; no new mechanism or timing relaxation is justified.

S3 authority/time evidence is kept separate: session-129 HTTP 200 authority-refresh replies and signed-time request counts establish service transport only, not target trusted-time acceptance or lease installation. The earlier `CloudSync Ready` observation is source-backed evidence that `current_binding()` succeeded in that earlier boot, but it is not a fresh structured receipt for session 129. Household-policy rejection is the known missing `activity_home_id` path; version-0/no-policy remains valid for basic motion TC-001 and is not the rejoin cause. NodeHealth 503 is a separate additive path with no evidence that it blocks this motion scenario. Zero CloudSync submissions with no queued event is not a failure.

The current successor remains `SAFETY_LATCHED` at `standing_readiness_authenticated_liveness_not_verified`. The console raises this known readiness guard as `ValueError` inside the reserved session; the session manager's generic exception path records it as `UNKNOWN_UNHANDLED`, increments the safety-failure count and latches the scope. That label is conservative bookkeeping, not evidence of a device identity/credential violation. The observed readiness failure remains preserved; this diagnostic change does not classify it as PASS or clear the latch. No existing audited disposition has been identified for this post-operation guard. No hardware operation is permitted until the latch is lawfully dispositioned and an applicable authorization is active. Historical predecessor ledgers remain untouched. Event 123/1's approximately 6h53m delivery delay remains unresolved. No new event was generated; TC-001 remains 0/5.

Validation: `python3 code/tests/python/test_gs117_tc001_console.py` **136/136 PASS**; `make -C code validation-framework-test` **55/55 PASS**; `git diff --check` **PASS**. Paired C3/S3 production-profile build completed (`TARGET_COMPILED_ONLY`, `physical_status=NOT_RUN`, `hardware_actions=NONE`; C3 artifact SHA-256 `45affeab2f3cff25594560eaff1cd94411dd327ab8d69dcb22ca9cd17dc2afdd`, S3 `56264ff117e7dd40062d98f87655448042079854b09537daf79b35e0203a691d`). It used production flags with GS_HIL and TEST_ONLY CloudSync disabled; it is not a TEST_ONLY deployment or installed-image proof. Hub and contract gates were started concurrently, causing a shared generated-artifact collision. Hub's board-stack stage failed on the colliding temporary artifact; the same contract stage passed. Hub's commissioning stage had 1 failure in 18 tests due to a stale assertion against the builder's explicit `GS_HIL_COMMISSIONING=OFF`; the Hub journal migration stage failed its clean-migration commit assertion; storage sanitizer timed out at 600s. Identity-compaction, incremental-completion and mixed-compaction passed; cloudsync-security-unit was interrupted. Contract stages passed cloudsync mTLS, cloud contract, worker/backend integration, HTTPS channel, health config (17 tests), contracts and GS-130 HIL runner integrity (116 tests); its first-event-reader stage timed out at 600s, while the Hub gate later passed the matching stage in 367.8s. The gates were stopped after about 45 minutes to avoid continuing unrelated release-scale stages; therefore neither is a complete-suite PASS. No physical test/build flash occurred.

Next: retain this offline diagnosis and seek only the existing audited latch disposition/authorization needed for a single observation using the reviewed diagnostic image; that observation must identify the actual S3 challenge-send failure and re-establish trusted-time/authority and authenticated C3 rejoin. Do not access hardware while the latch remains active.

Jira: GS-117 remains In Progress. Dated differential diagnosis and validation status were posted as comment 11866 and read back.

## GS-117 — approved provenance session stopped at authenticated rejoin guard — 2026-10-31

OWNING_JIRA=GS-117; RELATED_JIRA=GS-179, GS-116, GS-130, GS-173
OWNER_APPROVAL_REF=GS-117#11864
BUG_CLASSIFICATION=TEST_INFRA_ONLY
READINESS_OUTCOME=BLOCKED; TC-001=0/5
REQUIREMENT_SOURCE=GS-117 physical fixture and TC-001 acceptance; owner approval comment 11864
DECISION_IDS=NONE; no product acceptance or security rule changed
TASK_SCOPE=One approved current C3/S3 image provenance read, one protected S3 bootstrap/rejoin observation, and the conditional TC-001 campaign only if every gate passed.
OUT_OF_SCOPE=Firmware write/flash, erase, JEDEC, credentials, enrollment, ownership, unrelated DB changes, retries, or campaign after failed readiness.

Existing functionality → actual gap → minimum change: the existing reviewed readback helper verifies the selected app, partition table and OTA selector; the stale fixture receipts needed a current observation. The existing helper was used unchanged and genuine owner-only receipts were written from its actual output. No source implementation changed.

The single approved readback observation passed for both targets. C3 `c3-146393c5d158`/COM4 selected `ota_0` (seq 7, offset `0x20000`) and its 958,992-byte app matched `589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7`; partition table SHA-256 `219614d3586ae564ce51dfc462e6e7773b590abe41048a10bc513e1a7d799469`. S3 `hub-e072a1d38d34`/COM10 selected `ota_1` (seq 30, offset `0x420000`) and its 2,292,864-byte app matched `ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5`; partition table SHA-256 `338f4a83ba90609b4ed0a04514f6378dc90b5d21769e186f49dc3086fd9feabc`. No JEDEC/capacity query, NVS/key/trust read, write or erase occurred. The subsequent S3 bootstrap boot log independently reported 16 MiB flash and 8 MiB PSRAM; C3 boot log reported 4 MiB. Fixture image receipt checks now pass.

The one permitted protected bootstrap did **not** establish readiness. First failed guard: `standing_readiness_authenticated_liveness_not_verified`. C3 entered session 129; across nine `GET_STATE` observations both `runtime_live` and `sensing_live` remained 0, with retained/in-flight/pending injection all 0. C3 emitted bounded `GS117_DEV_REJOIN` attempts but no matching authenticated S3 rejoin was observed; S3 logged three `Authenticated control reply delivery failed` messages. Thus runtime liveness was not separately diagnosed as a firmware loop fault.

S3 boot identity and TLS-pair validation passed (`valid=1`). The authenticated TEST_ONLY ingress recorded five `/v1/test/authority/refresh` responses with HTTP 200, and the signed-time server counted six requests. These are transport/server observations only. The S3 logged household-policy rejection and deterministic activity rules disabled because signed Home config/current lease/trusted time was unavailable. Target trusted-time acceptance and authority-lease installation therefore remain **NOT VERIFIED**; an HTTP 200 is not target acceptance. No C3/S3 event was injected and no database event was created. The phone was connected and the existing APK/package readiness check passed, but no new event was presented in Android.

The successor authorization `gs117-provenance-20261031-3032726aa89e8077` is now safety-latched after 2 of 3 allowed procedure sessions (one successful observation, one failed bootstrap; one conditional campaign procedure remains unused but is unavailable while latched). Current status: `SAFETY_LATCHED`, one consecutive failure. All predecessor ledgers remain unchanged. Do not retry, clear the latch or start TC-001 under this policy. TC-001 remains **0/5**. Backend/PostgreSQL, caregiver HTTPS and LAN forwarding remain PASS. Temporary ingress/UDP listeners were stopped and absence verified.

Private evidence: `/home/udaybhan/.local/state/ghar-sajag/gs117-tc001/provenance-observation-20261031T051727Z/` (C3 readback SHA-256 `29c99ec5095c0889c68f4a928a382de7f0d64164eb30939b6e5e93365785a8b9`; S3 readback SHA-256 `8205d7e2b4c580c785c088e641c4cddeb38cbc8e1a339d1ff701076918050e4d`) and `/home/udaybhan/.local/state/ghar-sajag/gs117-tc001/standing-authorization/bootstrap-85fb8d482e17dc33ce4f8dca/`. Raw image bytes and sanitized target observations remain private.

No product source or firmware changed; broad regression suites were not rerun. Existing GS-117 135/135, framework 55/55 and mapping 22/22 evidence remains applicable to unchanged code. This session’s readback self-test, live fixture preflight, backend health, target identity, and service-stop checks passed; the physical readiness guard failed as above. Event 123/1’s approximately 6h53m delivery delay remains unresolved. GS-117 stays In Progress.

Next: offline-trace the exact S3 configuration/time/authority rejection and the C3↔S3 rejoin failure from existing source and preserved evidence. Only after a reviewed cause/correction should an audited successor/disposition be considered; this consumed, latched authorization cannot be reused. No immediate hardware retry is authorized by this record.

---

## GS-117 — successor readiness authorization implementation checkpoint — 2026-10-31

OWNING_JIRA=GS-117; RELATED_JIRA=GS-116, GS-130, GS-179, GS-173
OWNER_APPROVAL_REF=OWNER_CHAT_GS117_SUCCESSOR_20261031 (GS-117 comment 11859)
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-117 owner approval comment 11859; existing GS-117 DEV authorization and readiness contract
DECISION_IDS=NONE; product/security requirements and acceptance criteria unchanged
TASK_SCOPE=Enforce the one-bootstrap/one-campaign successor scope in the existing fail-closed authorization/session manager, preserve all predecessor ledgers, then activate and execute the approved readiness candidate only after exact preflight passes.
OUT_OF_SCOPE=Any flash/readback/JEDEC/erase, credential/enrollment/ownership change, non-test database mutation, safety-latch reset, or operation beyond the approved candidate/session limits.

Existing functionality → actual gap → minimum change: the existing GS-117 authorization loader already enforced exact fixture identity, source pins, an operation allowlist and a global session cap; the selected-operation successor path did not enforce a separate per-operation count, so two allowed sessions could both have been bootstrap sessions. The existing loader/session manager now requires a finite per-operation limit map for subset policies and checks that limit before reserving a session. For the approved successor the only valid map is `protected_gs40_bootstrap: 1` and `tc001_campaign: 1`, with `max_sessions: 2`; rejected operations do not consume a session. No second authorization framework was introduced.

Focused validation after the final source edits: `python3 code/tests/python/test_gs117_tc001_console.py` **135/135 PASS**; `make -C code validation-framework-test` **55/55 PASS**; `make -C code feature-coverage-test` **PASS**, 232 features / 287 modules / 27 physical cases and 22/22 mapping tests; Python compilation and `git diff --check` **PASS**. The new regression proves application flash is denied before reservation, a second bootstrap cannot reserve a session, the one campaign slot remains independently available, and malformed or inconsistent per-operation limits fail closed. No target build applies to this Python-only policy change.

The latest private active DEV manifest is still the previous authorization, owner approval ref `OWNER_CHAT_GS117_PERSISTENT_DEV_MODE_20261030`, SHA-256 `48e4f21064c705783230ce7937f7781c47416d0f70712ff9ce9d8f1ed41bda77`; its current scope remains `SAFETY_LATCHED` at 2 sessions / 1 safety failure. The immutable predecessor remains 29 sessions / 3 failures / blocked. Neither was edited or cleared. Jira comment 11859 independently records the owner's approval of an audit-linked successor and exact candidate SHA-256 `0429ee7f7293f319cd0538ca10d52c063613dd5b837116b63232491345a5ff55`. At this checkpoint the successor has not yet been activated, and no hardware operation has been performed.

The approval allows one protected S3 bootstrap, one bounded C3 restart, a 90-second observation, then one existing campaign of up to five events only if every mandatory gate passes. The readiness candidate can provide current boot/capacity, trusted-time/authority and rejoin observations only as emitted by the actual devices; it does not guarantee a current C3 installed-image provenance receipt or fixture acceptance. No values may be inferred or fabricated. TC-001 remains **0/5**; the prior missing fresh authenticated rejoin and `c3_current_installed_image_provenance_missing` remain open. Event `123/1`'s approximately 6h53m delivery delay remains an independent unresolved reliability finding.

Next: finish review/commit/push of the tested source and this evidence, then preserve the current manifest and both ledgers byte-for-byte while recording the separately approved, exact-hash successor activation through the existing audit format. Recheck all mandatory non-invasive pins and identities before using the candidate. Run at most one approved readiness session; start the campaign only if fresh target evidence and the complete fixture validate.

### 2026-10-31 04:40 UTC — image receipt expiry audit and diagnostic correction

The installed-image receipt's 24-hour `observed_at` limit is defined in the
existing GS-117 controller, not in the canonical requirements or Jira
acceptance. It is a development fixture observation-freshness policy, not a
firmware expiration rule. Exact current image identity remains mandatory. The
installed C3 HIL profile exposes no trusted full-image/partition digest, the S3
runtime only exposes a short image-hash prefix, and external/out-of-band
firmware changes are not reliably detectable from the local operation ledger.
Therefore the old receipts cannot be treated as current, and removing the age
gate would assume an integrity continuity that this fixture does not prove.
Production/release image requirements remain unchanged.

Existing functionality → actual gap → minimum change: `exact_fixture()` already
checks a fresh timestamp plus image digest, target, USB/device identity, active
OTA slot, partition digest and capacity. Gap: a stale observation and a
mismatched image were collapsed into the same provenance error. Minimum change:
retain the 24-hour check and all integrity checks, but report stale receipt and
invalid/future observation time separately from image/identity mismatch.
`IMAGE_RECEIPT_MAX_AGE_SECONDS` names the existing DEV bound; no TTL was
extended or removed.

Validation: Python compile and `python3
code/tests/python/test_gs117_tc001_console.py` **135/135 PASS**. Focused fixture
regressions confirm stale C3 and S3 receipts fail with a stale-specific reason,
future/naive observation times fail, and an otherwise fresh wrong image digest
still fails the provenance guard. Direct current-fixture preflight returns
`c3_installed_image_receipt_stale`. The controller source pin is now stale by
the intended edit and must be updated through the existing reviewed source-pin
process after commit; until then authorization status/preflight fails closed.
No physical access, receipt renewal, bootstrap, event injection or TC-001 run
occurred. TC-001 remains **0/5**. The remaining authorized campaign slot is
preserved, and the predecessor safety-latched ledgers remain unchanged.

#### 2026-10-31 04:40 UTC — source review completed

The existing owner-audited source-update procedure recorded the committed
controller change at `f79656236aaf110d8becdd0ec737c8da6b9e65e1`. Only the
controller pin changed; the scope hash, device identities, allowed operations,
session limit and historical ledgers were preserved. Review record SHA-256:
`77562044b1d89e8e26d26c5783732e2be589bf047f197f6917469e638840352e`; focused
test receipt SHA-256:
`410acc60a7268f58244eaf35a8e2ed22fe46dc6870899f0a219f22a45a451490`.
The recorded checks were GS-117 **135/135 PASS** and GS-130 consistency
**232 features / 287 modules / 27 physical cases; 22/22 mapping tests PASS**.
Authorization status is again `ACTIVE`, 1 of 2 sessions used, one campaign
session remaining and zero current safety failures. The predecessor's
29-session/3-failure latch remains preserved. The exact fixture still fails
closed at `c3_installed_image_receipt_stale`; the campaign slot was not used.

##### 2026-10-31 04:43 UTC — preserve integrity-failure precedence

Review tightened the check order: receipt identity/image/partition/capacity
integrity is evaluated before age classification. A stale receipt with a wrong
image digest therefore remains a provenance mismatch; only a matching receipt
with an old observation is labeled stale. The regression now explicitly covers
that combined case. The focused suite remains **135/135 PASS**. This follow-up
controller edit temporarily makes the reviewed source pin stale again; it will
be recorded by the same audited source-update path after this commit. No
hardware was accessed and the campaign slot remains unused.

##### 2026-10-31 04:43 UTC — follow-up source review completed

The source-review procedure recorded commit
`4dae4db2c8efec14030c193dd689445f7149cc5c`, changed only the controller pin,
and preserved policy/session state. Review record SHA-256:
`bf412de5a9ca82f90f7bab4ea771b2c24d0c57bab5cb45f6c94abbaf1a50c8f3`; test
receipt SHA-256:
`9e8decaf09e6784eedc697a05147f2d2141e8e8d5ce31b2238d06fc2c63252c0`.
The reviewed tests again report GS-117 **135/135 PASS** and feature mapping
**22/22 PASS** (232 features / 287 modules / 27 physical cases). Current
authorization is `ACTIVE`, 1/2 sessions used, one campaign slot remaining,
zero safety failures; all procedure pins match and the predecessor latch is
preserved. The exact fixture remains blocked at
`c3_installed_image_receipt_stale`. No physical operation occurred.

## GS-117 — Persistent TEST_ONLY development mode and physical E2E — 2026-10-30

OWNING_JIRA=GS-117; RELATED_JIRA=GS-116, GS-130, GS-179, GS-173
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-117 owner policy comment 11852 and current direct owner instruction; GS-116 comment 11853; GS-130 comment 11854
DECISION_IDS=NONE; commercial and release acceptance remain unchanged
TASK_SCOPE=Reuse the existing GS-117 authorization module to establish persistent, revocable default-permitted operations on the exact known GS117_DEV_TEST_ONLY fixture; preserve the prior 29-session/3-failure latch; run focused negative regressions and proceed to the existing campaign only when live technical gates pass.
OUT_OF_SCOPE=Production security activation, unknown/non-test devices, customer data, permanent eFuse/security changes, credential/ownership/enrollment bypass, unauthenticated device/backend paths, optical PIR qualification, and commercial release acceptance.

Existing functionality → actual gap → minimum change:

- Existing: `gs117_hil_authorization.py` owns the private policy, exact fixture identity, reviewed procedure pins, append-only ledger, bounded campaigns, and functional-versus-safety outcomes. Gap: the DEV policy is finite, its current source pins are stale, it has no explicit persistent-mode state, and a new consent reference must be traceably separated from the preserved old latch. Minimum change: add a fail-closed persistent mode contract and activation/revocation audit transition in that module, with no parallel service or ledger.
- Existing: the GS-117 controller runs the C3 HIL campaign and consumes `development_session('tc001_campaign')`; exact fixture, current device, ingress, API, and Android guards are already present. Gap: it cannot proceed until the persistent DEV policy validates. Minimum change: keep the existing controller path and update only its source pin after commit/review if required.
- Existing: the TEST_ONLY fixture and firmware receipts are preserved privately. Gap: current Android/device readiness is not yet rechecked in this task. Minimum change: run read-only live preflight after mode activation; never infer readiness from old receipts.
- Existing evidence: the prior owner-scoped audit contains 29 sessions, 3 consecutive failures, `blocked=true`; the prior manifest and all historical ledgers remain intact. The new mode must have a distinct direct-owner reference and activation event that links this predecessor snapshot; no hash rotation or counter reset may clear the old latch.

Validation after the latest source edit: `python3 -m py_compile code/tools/local/gs117_hil_authorization.py code/tools/local/gs117_tc001_console.py code/tests/python/test_gs117_tc001_console.py` PASS; `python3 code/tests/python/test_gs117_tc001_console.py` **124/124 PASS**; `make -C code validation-framework-test` **55/55 PASS**; `make -C code feature-coverage-test` PASS (232 features / 287 modules / 27 physical cases, 22/22 mapping tests); `git diff --check` PASS. These are Python tooling/policy tests; no target build is implicated. The prior `validation-tooling` failures recorded below remain unrelated and are not represented as passing.

Current execution status: source changes are implemented and focused validation passes; a current owner-only Development Mode activation event has not yet been written. No hardware/ADB action or fresh campaign has yet been performed in this task. Physical campaign remains formally 0/5 until a new run passes every C3/S3/backend/API/actual-APK stage. The 126/1 supplemental success and the 123/1 long-delay concern remain historical, unchanged evidence.

Next exact action: review and commit this tested policy/transition change, then create a byte-preserved backup and owner-audited activation record for the direct owner instruction. Preserve the old manifest and append-only predecessor ledger. Only after the activated policy validates should live readiness and the existing web campaign be attempted; the web campaign remains blocked on its existing fixture/ADB/target gates until live evidence says otherwise.

## GS-117 — Separate DEV functional outcomes from authorization-safety failures — 2026-10-30

OWNING_JIRA=GS-117; RELATED_JIRA=GS-179, GS-116, GS-130, GS-173
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-117 reusable TEST_ONLY authorization and stop-on-first-non-PASS campaign; GS-116 focused validation policy
DECISION_IDS=NONE
TASK_SCOPE=Classify existing DEV campaign results separately from authorization/safety faults so ordinary product or observer failures retain evidence and can be diagnosed/retried within valid consent; preserve the old latched scope and prepare the next approval boundary.
OUT_OF_SCOPE=No hardware/ADB/USB access, motion injection, policy/ledger edit, credential/enrollment change, database mutation, fixture fabrication or campaign execution.

The last three failed recorded sessions were reviewed against the existing append-only private audit and preserved run evidence:

1. `2026-10-30T01:42:11Z`, `tc001_campaign`: the controller's Android observer exited with `CalledProcessError` after the product path had otherwise completed. The exact same EventKey was later observed in the actual APK by the existing observer. Classify this as a recoverable tooling/observer failure. The original campaign run remains `BLOCKED`; it is not retroactively a PASS.
2. `2026-10-30T07:31:02Z`, `protected_gs40_bootstrap`: the protected procedure reported `REVIEWED_SERIAL_HELPER_CHANGED`. This is a reviewed-procedure fingerprint/authorization failure and correctly remains fail-closed; no retry occurred.
3. `2026-10-30T07:33:33Z`, `protected_gs40_bootstrap`: the child returned exit 0, but the captured S3 output reported desired-policy rejection, disabled routine rules and `CloudSync submitted=0`, while C3 liveness counters advanced. The parent did not persist a precise target failure code and no same-session authenticated rejoin was observed. Classify as UNKNOWN/unhandled target-readiness failure pending better preserved stage evidence; do not relabel it as a confirmed ordinary product defect or successful bootstrap.

The durable owner-scoped history remains **29 sessions** (10 bootstrap, 11 observe, 4 application-flash, 4 campaign), with **3 consecutive failures and `blocked=true`**. This task did not modify the owner-only manifest, any old hash-keyed ledger, the stable ledger or the append-only audit. The existing active consent pins the old controller and authorization-module SHA-256 values; both now differ from the reviewed working-tree files, so the standard loader fails closed before reserving a session. Other reviewed pins still match. The historical scope must remain latched; no hash rotation, new consent reference or counter reset was made.

The existing authorization module and TC-001 controller now keep two outcomes distinct. A completed campaign records `functional_outcome` (`PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, or `PARTIAL`) separately from `authorization_outcome`. A normal functional non-PASS stops the current campaign and preserves its evidence, but does not increment the authorization-safety failure counter. Explicit identity/scope/authority safety failures raise a typed guard and latch the scope. Unknown exceptions remain conservatively latched. Pre-session pin/consent denials do not reserve a session. No acceptance criteria were relaxed.

Focused validation after the final source edit: `python3 code/tests/python/test_gs117_tc001_console.py` **118/118 PASS**; `make -C code validation-framework-test` **55/55 PASS**; `python3 -m py_compile ...` and `git diff --check` **PASS**. `make -C code validation-tooling` did **not** pass: its Python stage reported two unrelated existing failures (static payload/CSS budget and the S3 fixture test's expectation that `GS_HIL_COMMISSIONING` is absent from the current build script). The report also records `source_unchanged=false`, so it is not a matched-source validation receipt. No target build applies to this Python-only controller/auth change. Traceability has been updated to map the new test anchor; its final mapping check is recorded in the associated evidence entry.

The physical campaign remains **0/5 accepted**; no new EventKey, hardware action or Android observation was produced. Event `126/1` remains supplemental real C3-HIL-to-APK evidence while its original controller run remains BLOCKED. Optical PIR qualification, recovery qualification and release acceptance remain separate.

**Next gate:** preserve the old latch and obtain one explicit successor DEV consent scope if continuing after review. The successor must pin the final committed controller and authorization-module hashes, retain the exact C3/S3/Home/backend identities and existing safety restrictions, and reference the preserved 29-session/3-failure scope without resetting it. Reconnect the authorized phone, verify the successor through the existing fail-closed loader and readiness path, then execute the existing campaign only under valid scope; stop on the first non-PASS. The unresolved `123/1` delivery latency (~6 h 53 min) remains a reliability investigation item, not a newly validated acceptance threshold.

Delivery: source/test/evidence commit `cc5b4ef3fee8594ff375727f01f733018488e4f0` was pushed normally to `feature/r1-commercial-baseline`; `git ls-remote` matched that commit. Tracked files were clean after the source delivery; all pre-existing untracked Android/build/hardware evidence was left untouched. GS-117 remains In Progress. Jira comment **11851** was added and read back successfully. Current successor pins to review: controller `12db4b3ce0d4d3a43d423dafa854d2e783086ce576d2993c0661525b8c5dc533`; authorization module `f77bfe0bc5043128d4e62cfe7d64903e0c991a48f20d49cb27732a95fbb2157c`. The older consent still pins controller `f5de2dfadc74533fd881a576bbc2e922a8fee2b5f913b2c9ba78daa7d4dec75e` and validator `91973a527d3518a90ca93e625fa0b7df0a14b77902fd883446e6f07acbb7277d`, and remains failure-latched. This delivery does not activate a successor or authorize a physical run.

## GS-117 — DEV authorization history continuity; campaign latch preserved — 2026-10-30

OWNING_JIRA=GS-117; RELATED_JIRA=GS-179, GS-116, GS-130
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=Current GS-117 DEV authorization procedure and owner direction; GS-116 focused validation policy
DECISION_IDS=NONE
TASK_SCOPE=Preserve cumulative DEV session, procedure and failure counts across reviewed manifest pin changes; validate the existing Android observer fix offline; do not start a physical campaign while the owner-scope failure latch is active.
OUT_OF_SCOPE=No ADB interaction while the phone is disconnected; no COM access, reset/bootstrap, motion injection, firmware operation, credentials, enrollment, database mutation, or failure-counter reset.

The authorization bug was confirmed: DEV ledgers were keyed by the manifest SHA-256, so each reviewed pin rotation could select a fresh zero-count ledger. The current manifest-specific ledger reported 2 sessions/2 consecutive failures, while the owner-scoped append-only audit contains **29 sessions**, including 10 protected bootstrap, 11 observe, 4 app-flash and 4 campaign sessions, with **3 consecutive failures** at the end. The audit, not the newest hash-specific ledger, is the cumulative source of usage.

Commit `b59a903dea5f0451bf963d3911cb12cdd6e56132` implements a stable owner-consent/fixture ledger identity, reconstructs cumulative counters from distinct audited session starts, preserves old hash ledgers, reconciles the stable ledger against the append-only audit on every use, and fails closed on missing/corrupt/inconsistent history. It also clears stale prior-run completion/failure fields when reserving a new session and derives the last outcome from the explicit blocked/completed state. New-consent scopes remain isolated; changing only procedure pins does not reset the existing scope.

Focused validation: `python3 code/tests/python/test_gs117_tc001_console.py` **114/114 PASS**. It covers hash rotation, procedure/session count preservation, failure-latch retention, missing history, stable-ledger/audit mismatch, stale completion markers, success after failure, and consent-scope isolation. `make -C code feature-coverage-test` **PASS**: 232 features, 287 modules, 27 physical cases and 22/22 registry tests. No target build applies to this Python-only tooling change.

The established owner-only atomic backup/repin procedure was used on the active `GS117_DEV_TEST_ONLY` manifest, with **only** `serial_helper.sha256` and `validator.sha256` changed. Byte-for-byte backup: `~/.config/ghar-sajag/gs117-tc001/development-authorization.json.before-ledger-history-repin-20261030T1635Z` (old manifest SHA-256 `fd6e54cda06a4a06b57c586ae7fcde184885b25e5c065df78fbf74f7f12761a6`). New serial helper SHA-256 is `fc2a30f5b0407d1f0f2300552476991575128cb2b66aa3cdd29a9533a608ceaa`; the validator SHA-256 is `91973a527d3518a90ca93e625fa0b7df0a14b77902fd883446e6f07acbb7277d`; new owner-only manifest SHA-256 is `b89b819497b1d7a93cd7e1e65220c44df53990543bd888e4b74e3ae2504c2aa6`. The existing approval reference, device/Home/backend scope, permissions, limits, revocation and all other pins were verified unchanged. `load_development()` now passes.

The standard campaign authorization check was then exercised offline. It reconstructed a private stable ledger at 29 sessions / 3 consecutive failures / blocked=true, preserved every historical hash-keyed ledger byte-for-byte, appended one migration audit note with no `started_at`, and **denied before reserving a session**. Audit session starts remain 29. No device, USB port, ADB, or event input was accessed. Therefore the 3-failure guard is active and cannot be bypassed by the now-valid source pins. The earlier Android correction remains covered by the same focused test suite; the phone is disconnected and no live APK observation occurred in this checkpoint.

The existing physical event `c3-146393c5d158 / bedroom / session 126 / sequence 1` remains one same-key C3-HIL-to-actual-APK supplemental evidence chain, but the original controller run remains BLOCKED and formal campaign accounting remains **0/5 accepted**. Event `123/1` later committed about 6 h 53 min after input; the scheduling/backoff cause remains unknown. Neither is promoted to this campaign.

**Next gate:** do not clear or rewrite the 29-session/3-failure history. The current DEV scope is latched. The owner must review the last three failed session records and, if continuing is desired, explicitly approve a successor DEV consent scope for the same exact TEST_ONLY devices/Home/backend after that review. Reconnect the authorized Android phone before any new run. Then verify standard non-hardware preflight and start the existing web campaign only under that successor consent; keep stop-on-first-failure. No optical PIR or commercial release qualification is inferred.

## GS-117 / GS-179 — Fresh C3 HIL event correlated through actual APK — 2026-10-30

OWNING_JIRA=GS-117; RELATED_JIRA=GS-179, GS-116, GS-130
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-117 exact original EventKey through C3/S3/backend/caregiver APK; GS-116 focused validation; GS-130 traceability
DECISION_IDS=NONE
TASK_SCOPE=Fix bounded Android Reports observer recovery, reconcile the same-key evidence for physical C3 HIL event 126/1, and update existing evidence/traceability.
OUT_OF_SCOPE=No further phone interaction after disconnect, COM access, reset/bootstrap, motion injection, firmware operation, policy/ledger edit, credential change, or database mutation.

One fresh C3 HIL event has a complete same-key evidence chain. EventKey: `c3-146393c5d158 / bedroom / session 126 / sequence 1`; provenance `C3_HIL_INJECTED`. The original controller record shows the physical C3 command and NodeRuntime event, matching authenticated class-0 S3 durable application ACK (`retired=1`), authenticated S3 CloudSync, one PostgreSQL durable record, zero duplicates and one caregiver API result for `gs177-test-product` / Hub `hub-e072a1d38d34` / epoch 1 / enrollment generation 1. The backend commit/receipt time is 2026-10-30 01:43:30 UTC; source C3 generation wall-clock time is unavailable.

The initial controller Android step exited `CalledProcessError`, so its immutable run remains `BLOCKED`, `passed_runs=0` and campaign accounting remains **0/5 accepted**. A later run of the existing ADB observer on the authorized phone independently found that same fresh exact key in the actual installed Parivar Saathi APK Reports/Event Details: package `in.gharsajag.caregiver.discoverytest`, version `0.4.0-connected-lite-staging`, Home `gs177-test-product`, origin `https://192.168.1.6/`, backend `CONNECTED`, Bedroom, Motion recorded. Screenshot and accessibility evidence are preserved privately; see `GS117_PHYSICAL_ACCESS.../EXECUTION.md` and private `android-stage-addendum.json`. The owner has since disconnected the phone for a call. It is needed for APK verification of any later campaign event, not for offline work. This HIL input does not qualify optical PIR.

The existing Android observer was minimally extended to recover from transient Reports-tab loss after scroll and transient Home/Reports accessibility gaps after refresh/capture, while keeping bounded retries and exact Home/package/origin/authenticated-session/EventKey checks. Persistent missing navigation, mismatched Home or absent EventKey still fails closed. `python3 code/tests/python/test_gs117_tc001_console.py`: **108/108 PASS**. `make -C code feature-coverage-test`: **PASS** (232 features, 287 modules, 27 physical cases; 22/22 registry tests). The existing GS-130 traceability row is updated; no new framework or test ID was added.

Other reconciled findings: EventKey session 123/1 eventually committed through authenticated ingress and caregiver API exactly once at 2026-10-30 01:22:10 UTC, about 6 h 53 min after the C3 input; the delay cause is not established. The current routine-config HTTP 403 is expected for the authenticated FAMILY/CAREGIVER account because the existing route requires OWNER/PRIMARY. The TEST_ONLY Home has no desired policy row; S3's version-0/no-policy form is supported and does not block motion event validation. The previous generic target “desired household policy rejected” remains unexplained because its actual config GET response was not captured.

**Next gate:** the active private DEV manifest pins `gs117_tc001_serial_windows.py` at SHA-256 `66afe888…`, but the reviewed helper after this observer change hashes to `fc2a30f5…`. The standard authorization path fails closed on this mismatch. The current owner-only ledger remains `sessions=2`, `consecutive_failures=2`, `blocked=true`; preserve it. Do not edit the private consent manifest, reset the ledger, or bypass the pin. A reviewed pin update through an established authorized mechanism is required before another campaign. Reconnect the phone before attempting additional exact-key APK stages. No second event was started after the original run stopped.

At resume the canonical local and origin branch were both `feature/r1-commercial-baseline`, HEAD `84d56bce0669886b28a30468afb25de9c46845a0`; context preflight PASS (`2026-10-28.001`). The observer/test patch, this handoff, the GS-117/GS-179 evidence addenda, and the existing traceability row were reviewed together and committed/pushed as `14b6c1e35297278e025dc1bbf7e4a8dfdf169f8d` (remote matched on verification). Unrelated untracked Android/build/hardware evidence was preserved. GS-117 and GS-179 remain In Progress; no ticket is closed.

## GS-117 — Session-118 32-event Android report reconciliation — 2026-10-29

OWNING_JIRA=GS-117; RELATED_JIRA=GS-179
BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=GS-117 event identity/time/chronology and caregiver-visible acceptance; GS-179 authenticated caregiver projection
DECISION_IDS=NONE
TASK_SCOPE=Read-only PostgreSQL, authenticated caregiver API, preserved physical ingress traces, and one existing ADB observer attempt.
OUT_OF_SCOPE=No COM/Hub access, reset, bootstrap, injection, firmware operation, database mutation, credential change, authorization-latch change, or API source modification.

The owner reports 32 Bedroom motion entries in the installed APK Reports view today (29 October), approximately 11:20–13:22 IST. Read-only PostgreSQL verification found exactly 32 unique durable event keys for Home `gs177-test-product`, C3 `c3-146393c5d158`, room `bedroom`, origin session 118, sequences 70–101. All 32 rows join to Hub `hub-e072a1d38d34`, installation epoch 1 and Node enrollment generation 1; all have `source_type=NODE` and `is_test=0`. Event types are 24 `MOTION` and 8 `MOTION_SUMMARY`. There is one durable row per key.

The two preserved physical mTLS ingress traces contain 59 event POSTs for those keys: 32 first commits returned HTTP 201 `COMMITTED`; 27 retries returned HTTP 200 duplicate-safe `COMMITTED` (seq73 once, seq81 23 times, seq101 three times). The 32 first commits reconcile with the previously confirmed 28 retained keys (seq74–101) plus four retained keys (seq70–73) from the earlier trace. These were retained-backlog deliveries during the report interval; no fresh NodeRuntime generation is evidenced in that interval, and the original stimulus/generation times are unavailable. The first and last PostgreSQL backend receive/commit timestamps are 11:25:50 and 13:22:26 IST; all 32 database receive/commit values match the physical ingress request time within 1.9 seconds. This confirms physical S3 CloudSync, authenticated backend admission and durable deduplication for the recorded keys. It does not by itself prove the C3 emitted each key over authenticated ESP-NOW or received an application ACK.

All 32 stored `events.occurred_at` and `hub_received_at` values are zero. The caregiver read model substitutes backend `received_at` for zero `occurred_at`, so displayed API chronology is backend arrival time, not C3 generation time or Hub receipt time. C3-origin and S3-receipt timestamps are unavailable for this batch. Thus the owner’s approximate 11:20 first display cannot be independently compared with source time; backend first receipt was 11:25:50 IST.

The current authenticated GS-148 caregiver Reports API returned 171 total Home event records and a 100-row recent-event window. It contained 31 of these 32 keys; seq100 was absent. Source inspection confirms the timeline query orders and limits on the stored `occurred_at` before `_row_to_event()` substitutes `received_at`. For the current data, all 32 raw occurrence times are zero and seq100 ranks 101 while seq101 ranks 100. This is a proven caregiver projection omission/order defect under GS-179; no source fix was made in this read-only validation task.

No record is marked HOST_SIM or `is_test`, and the requests arrived through the actual authenticated S3 ingress; no synthetic seed is indicated. However, these event types can also result from the USB HIL input, and no C3 source transcript for seq70–101 establishes whether the initiating stimulus was optical PIR, USB injection, or another prior physical stimulus. This batch is not REAL_SENSOR_PASS or TC-001 controlled-injection acceptance.

The authorized ADB device and installed APK were detected as `in.gharsajag.caregiver.discoverytest`, version `0.4.0-connected-lite-staging`. The existing exact-key observer for session118/seq101 stopped at `TC001_ANDROID_SETTINGS_NAVIGATION_NOT_FOUND`, before Reports/Event Details, and produced no new Android evidence. The owner-reported 32 count remains separate from independently verified APK evidence. The previous seq16 APK observation is historical and does not verify this batch.

Current gates remain: TC-001 0/5 NOT_RUN; physical optical PIR NOT_RUN; current C3↔S3 application ACK NOT_VERIFIED; owner-only `fixture.json` absent; five-run campaign approval absent. The last preserved physical S3 trace is from the 29 October bounded service window and is not a substitute for a fresh pre-campaign ingress/time receipt. Next, correct and regression-test the GS-179 effective-time ordering/projection omission, then independently expose all 32 exact keys in the caregiver API and installed APK. Only after current fixture/receipt checks and separate campaign authorization should any controlled physical input proceed. No source tests or hardware operations were run in this analysis.

Repository/code checkpoint analyzed: `512430a8472728e50c8d5d1330d19e83279534c7`, canonical branch `feature/r1-commercial-baseline`; context preflight PASS. Pre-existing untracked assets were preserved.

## Latest GS-117 offline S3 time/authority analysis — 2026-10-29

OWNING_JIRA=GS-117
BUG_CLASSIFICATION=INVESTIGATE_ONLY
REQUIREMENT_SOURCE=existing GS117-TC001-01 trusted-time, current-authority, authenticated rejoin and liveness gates
DECISION_IDS=NONE
TASK_SCOPE=Offline source and preserved-log analysis only; no device, service, database or authorization-state operation.
OUT_OF_SCOPE=No COM access, reset, bootstrap retry, latch/ledger change, injection, campaign, credential, firmware or database mutation.

The exact target line from the one-session successor remains `TEST_ONLY time/authority refresh failed; publication fenced` at S3 uptime 51.951 s. The existing observer would stop on earlier `signed-time bootstrap unavailable` or `authority bootstrap unavailable` markers; neither appears in the preserved S3 observation before this generic periodic-refresh failure. The first failure therefore occurred in the later combined refresh loop, not as an observed initial-bootstrap failure. That loop short-circuits `gs40_test_only_refresh_time()` and `gs40_test_only_refresh_authority()` and emits one shared error, so the saved evidence cannot identify which operation or substage failed.

The exact GSTQ/GSTP v1 wire layout, 45-byte challenge, 456-byte RSA-3072/SHA-256 proof, nonce/generation binding, validity interval, trusted-floor checks, and authority lease signature/binding checks align between the S3 implementation and existing host signer/verifier. Existing tests cover signed-time cryptography/replay, time-floor recovery/rollback/storage failure, and authority-lease validity/nonce/generation/expiry/binding; they do not exercise the target UDP refresh function or identify a runtime substage. No source defect was established.

Read-only review of the already-preserved physical ingress trace adds later recovery evidence. In the same bounded service window, actual S3 authority-refresh requests returned authenticated HTTP 200 94 times from 07:03:40.550Z through 07:58:32.450Z. More decisively, the S3 later submitted 55 physical CloudSync event requests from 07:04:24.948Z through 07:57:38.350Z: 28 new session-118 sequence 74–101 EventKeys received `COMMITTED` (HTTP 201), and 27 retries for already committed keys received duplicate-safe `COMMITTED` (HTTP 200). These are historical retained C3 events, not a new TC-001 input. The production S3 CloudSync path requires current trusted time and an installed current authority lease before the authenticated event POST; therefore this trace proves those prerequisites became valid after the initial refresh guard. It does not prove the specific failed substage or current session-120 C3 application ACK.

Conclusion: the first periodic time/authority refresh failed transiently and the existing S3 retry path later recovered without a new bootstrap or hardware intervention. There is no evidence of a persistent proof-format/key, envelope-expiry, authority-signature or service-availability defect. The exact first failed substage is **not established** because the current target firmware collapses both refresh results into one log line. No firmware correction or test change was made.

Current gates: S3 trusted-time/current authority and physical CloudSync are evidenced as recovered later in that service window; current C3 session-120 authenticated rejoin/application ACK remains NOT_VERIFIED. The owner-only `fixture.json` remains absent. TC-001 remains 0/5 NOT_RUN; campaign authorization remains separate. Next product validation requires a qualified current fixture and a separately authorized physical input/run, then exact C3 application-ACK-to-Android correlation. Any attempt to isolate the historical one-shot refresh error more finely would require a target observation that records separate non-secret stage outcomes; no such operation was performed or authorized here.

Repository checkpoint for this offline analysis: branch `feature/r1-commercial-baseline`, source HEAD `6943cf15c9f1155737b811430524c8b662c99ae6`, equal to origin before documentation edits. Pre-existing untracked files were preserved. No tests were run because no source/test code changed.

## Latest active checkpoint — GS-117 successor readiness stopped at S3 time/authority guard — 2026-10-29

OWNING_JIRA=GS-117
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=existing GS117-TC001-01 target trusted-time, authenticated C3↔S3 rejoin and liveness readiness contract
DECISION_IDS=NONE
TASK_SCOPE=Execute the explicitly approved one-session successor using the corrected protected-bootstrap evidence parent; verify and report genuine target readiness.
OUT_OF_SCOPE=No retry, injection/campaign, flash/erase/readback/JEDEC, credential/enrollment/ownership change, database edit, Android action or new authorization framework.

Owner-approved one-session successor was activated using the existing owner-only manifest/consent mechanism. Candidate parent SHA-256 `b674461a46a14a4a5e3fd56902ffee04c60aca99c036efa8a892cb23c0f5d454`; evidence helper SHA-256 `d3ab32c9217293ae54960ef11d03e6cd0237c74d2d779d0f070aed1116cc8f9d`. Successor policy hash `9ed966b535ed83ac5ac8d2f25f80af7231d90d56c71a427382fdcd9c836f94f9`, `max_sessions=1`, approved until `2026-11-05T00:00:00Z`. Original policy hash `90cbf044f525fb907a87376707ef64d9d5f254f47a555e31bb0a8b792937fdb9` was archived byte-for-byte; its session 1/10 failed ledger remains unchanged and latched. Successor now records its single session used and is failure-latched; no retry is permitted under this approval.

The trusted Private Wi-Fi, .6 endpoint/certificate SAN, backend HTTPS/PostgreSQL, current WSL `.10` ingress route/listener, Windows `.6:8445` mapping/listener, `.6:4468` signed-time listener, exact COM4/COM10 USB identities and pinned image receipts passed non-invasive preflight. The missing bounded ingress/signed-time processes were started once from the preserved scripts in owner-private run directory `~/.local/state/ghar-sajag/gs117-tc001/successor-readiness-20261029T065850Z/`; both run with a one-hour bound. The existing owner-only `fixture.json` is absent and was not fabricated.

Exactly one `python3 code/tools/local/gs117_tc001_console.py --hil-readiness` call ran. Child-result evidence is in `~/.local/state/ghar-sajag/gs117-tc001/standing-authorization/bootstrap-e8768f01e42e8f01a160e2dd/bootstrap-child-result.json` (owner-only). First failed target guard: S3 logged `TEST_ONLY time/authority refresh failed; publication fenced`; child error was `TC001_TARGET_READINESS_GUARD_FAILED`, exit 2, stage `encrypted_config_exchange`. The S3 TLS identity validation reported `valid=1`, expected Hub/Home and enrollment/epoch were observed. Real backend mTLS authority-refresh returned HTTP 200 at 07:03:40.550Z and 07:04:04.416Z; signed-time host request count reached four, but target trusted-time acceptance was not demonstrated. No authenticated C3 rejoin line was captured.

C3 NodeRuntime started. In session 120, five GET_STATE samples advanced both `runtime_live` and `sensing_live` from 204790 to 206807. A retained seq3 `NodeMessage sent` appeared, but no application ACK or controlled input was observed; this is not TC-001 evidence. Overall readiness **BLOCKED** at S3 time/authority refresh, with target trusted-time acceptance and C3↔S3 authenticated rejoin NOT_VERIFIED. TC-001 remains 0/5 NOT_RUN; no Android or Morning Routine outcome is claimed. No database was manually modified; no flash, erase, readback, JEDEC, credential, enrollment or ownership operation occurred. Existing normal service/CloudSync retries may continue until the bounded services expire.

Canonical source at this execution's start was branch `feature/r1-commercial-baseline`, local and remote HEAD `2bb45c0d9e2f89c85bddb4b9edeed4549daf2a85`; context preflight PASS. This checkpoint's evidence/work-state documentation is being closed from that source. Unrelated pre-existing untracked files remain preserved. Next action: offline diagnosis of the S3 time/authority refresh failure using current source and saved target evidence; request new hardware authorization before any further port/bootstrap observation. The campaign remains separately unauthorized.

## Previous checkpoint — GS-117 bootstrap failure evidence retention, offline only — 2026-10-29

OWNING_JIRA=GS-117
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=existing GS117-TC001-01 observation and failure-evidence contract
DECISION_IDS=NONE
TASK_SCOPE=Preserve the existing protected GS40 child result and failure observations in owner-only evidence before any parent error is raised.
OUT_OF_SCOPE=No device access, bootstrap retry, COM4/COM10, service restart, injection, campaign, credential/configuration change, or failure-latch change.

Existing functionality → actual gap → minimum change: the protected Windows serial helper already emits JSON with its error identity and captured C3/S3 observation; the private bootstrap parent checked the child's return code and raised before writing that response. The parent also discarded child output after a timeout/parent interruption. Added the small `code/tools/local/gs117_bootstrap_evidence.py` serializer/child waiter, which filters response fields, redacts credential-like and long-token values, retains stage/guard/exit code/timestamps and relevant C3/S3 observations, and durably writes one mode-0600 result into the already validated mode-0700 session directory before returning or raising. It records hashes/byte counts, never raw malformed output, has bounded sizes, uses exclusive creation/fsync, and kills/drains a child once on timeout/interruption. It does not read configuration or credentials and does not change the standing authorization/latch code.

The pinned active private script remains unchanged at SHA-256 `aca84ff3ebc4a507dcaca792a22167643cce32bd736fa3012e139af2c19d45ad`; active owner manifest remains unchanged at SHA-256 `90cbf044f525fb907a87376707ef64d9d5f254f47a555e31bb0a8b792937fdb9`. The prior failure latch remains set and the read-only launcher status still returns BLOCKED/exit 2. A distinct, owner-only, mode-0600 candidate script was prepared but not activated or executed: `~/.local/state/ghar-sajag/gs117-tc001/standing-readiness-prepared/gs117-protected-bootstrap-current-network-evidence-v5.py`, SHA-256 `b674461a46a14a4a5e3fd56902ffee04c60aca99c036efa8a892cb23c0f5d454`. It pins helper SHA-256 `d3ab32c9217293ae54960ef11d03e6cd0237c74d2d779d0f070aed1116cc8f9d` and keeps the existing serial-helper pin and Bootstrap guards. Earlier unactivated drafts v2–v4 are retained; the active pinned procedure was not edited.

Private-log reconciliation found no recoverable child serial observation from the first readiness attempt: its saved stdout contains only the generic parent guard, stderr is empty, and no child-result file exists. No target text is reconstructed. The separate session-120 C3 GET_STATE receipt shows zero runtime/sensing counters at its earlier observation; it is not evidence of this later bootstrap's exact fault or current C3↔S3 state. The current run's contemporaneous ingress logs do verify actual S3 authority-refresh HTTP 200 and CloudSync commits for retained C3 session-118 sequences 70–73; a PostgreSQL READ ONLY query found exactly one row each. Those are backlog replay, not TC-001 input. A signed-time service request count remains insufficient to prove S3 accepted signed time. C3 current runtime/liveness, S3-to-C3 authenticated rejoin, and target time acceptance remain NOT_VERIFIED.

Validation after the final helper edit: `python3 tests/python/test_gs117_tc001_console.py` **77/77 PASS**; `make validation-framework-test` **55/55 PASS**; `make feature-coverage-test` **traceability check PASS (226 features, 286 modules, 27 physical cases) and 22/22 tests PASS**. Focused failures during test development were in the new mock's drain behavior and the initial CSV anchor; both were corrected and the final commands above pass. Candidate bootstrap AST parse PASS; it was not executed. No hardware, ADB, service, database or authorization operation occurred. Broad `validation-tooling`, product suites and target builds were not run because only the local Python diagnostic serializer/tests/registry input changed.

The next physical observation requires explicit owner approval for a one-session successor authorization: retain the old failed ledger unchanged; approve the reviewed candidate path/hash and helper hash; set a new approval reference and maximum one session/one existing GS40 Bootstrap/zero retries, retaining exact devices/Home/endpoint/images, 150-second limit, 60-second observation and every existing technical preflight/stop guard. This does not clear the old latch or authorize motion injection/campaign. Once approved, activate that separate one-shot policy through the existing consent mechanism, then run one readiness observation and stop on the first technical guard. TC-001 remains 0/5 NOT_RUN; GS-117 remains OnHold; no Android or Morning Routine result is claimed.

Repository at task start was `feature/r1-commercial-baseline`, base HEAD `44a3d4ee93081e71833ebe3dea3613a1397e6967`, equal to origin; context preflight PASS. The changes are limited to the existing console regression file, a small local evidence helper, its registry input/traceability and this handoff. All unrelated untracked worktree assets remain untouched.

## Previous active checkpoint — GS-117 consolidated physical session stopped at C3 runtime liveness guard — 2026-10-29 04:42 UTC

Physical operations used source commit `ddf3ff4d866213716462f000db7534252f74e64c` on
`feature/r1-commercial-baseline`; origin matched and context preflight passed.
The owner approved one exact-device GS-117 TEST_ONLY readback, C3 return/GET_STATE,
conditional existing S3 GS40 config recovery, and up-to-five-run TC-001 session.
The authorization ends at the first failed physical readiness guard; the campaign
and recovery were not started.

Read-only USB enumeration matched C3 COM4 / `14:63:93:C5:D1:58` and S3 COM10 /
`E0:72:A1:D3:8D:34`, VID/PID `303A:1001`. The existing private image-readback
procedure passed its non-hardware artifact check. Its one-session variant omitted
flash-capacity/JEDEC queries and read only the partition table, `otadata`, and the
trusted-image-length bytes from the selected application slot. Both boards passed:
C3 MAC `146393c5d158`, selector `ota_0` at `0x20000`, image SHA-256
`591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea`; S3 MAC
`e072a1d38d34`, selector `ota_1` at `0x420000`, image SHA-256
`c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16`. Each
partition-table hash and selector CRC were verified. No JEDEC/capacity query,
flash write, erase, NVS/outbox read or credential-partition access occurred.
Private raw readback and logs are mode 0600 under
`~/.local/state/ghar-sajag/gs117-tc001/readback-approved-20261029T0435Z/`.

After readback, the approved C3 `read-mac` command exited 0, returned the expected
MAC and issued the RTS hard reset. The C3 application answered `GET_STATE` with
the expected `HIL_AWAKE_TEST_ONLY` profile and empty retained/in-flight/pending
state. However, a full 30-second bounded observation, with samples through
112.3 seconds after boot, kept `runtime_live=0` and `sensing_live=0`. The UART
control task acknowledged every `GET_STATE`, but the NodeRuntime liveness gate
failed. Source increments these counters inside the NodeRuntime owner loop
(`node_runtime_adapter.cpp`); the underlying startup stall is not yet identified.
This is the first failed guard. No S3 config reapplication, motion injection,
TC-001 campaign or further hardware operation followed. The S3 readback entered
the bootloader/stub path and may have cleared RAM-only TEST_ONLY configuration;
it was not restored after the stop.

Non-invasive service checks passed: local and LAN HTTPS `/readyz` returned HTTP
200 with certificate verification and reported PostgreSQL reachable; PostgreSQL
and the caregiver service remain active. Windows listeners are present at
`192.168.1.6:8445` and UDP `192.168.1.6:4468`; the WSL 8445 ingress listener is
active. These host/listener checks do not prove fresh S3 mTLS or signed-time
acceptance. The existing GS-117 page returned HTTP 200; `/api/status` did not
return within the attempted bounded request. Windows ADB currently lists no
device, so there is no fresh APK observation. Owner-only fixture and campaign
approval remain absent; no database event was written. TC-001 remains 0/5
NOT_RUN, Morning Routine completion and real PIR remain NOT_RUN, and GS-117
remains OnHold.

Next: investigate the C3 owner-loop startup failure from current source and
preserved image/build records without touching hardware. Further serial/runtime
diagnostics and physical continuation require a new bounded owner scope because
the approved session ended on this failed guard. Do not re-run JEDEC or resume
the campaign. Pre-change local and remote HEAD were both
`ddf3ff4d866213716462f000db7534252f74e64c`; unrelated untracked Android and
historical HIL evidence remains preserved.

## Prior checkpoint — GS-117 physical E2E, one consolidated hardware approval pending — 2026-10-29

Resume base: canonical `feature/r1-commercial-baseline` at
`8a8e0a082bb2556e3f19075ecc1e0476383046d2`; origin matched before this
checkpoint. Context preflight PASS (`2026-10-28.001`). Tracked files were clean
at the base; unrelated untracked Android, IDF and historical hardware evidence
remain preserved.

The owner-approved COM4 JEDEC/capacity query remains PASS: XMC 4 MB,
manufacturer `0x46`, device `0x4016`, combined ID `0x164046`. It is not repeated.
The command left C3 in ROM bootloader. C3 application execution and current
installed-image provenance are not verified.

At 2026-10-29 04:03Z the existing GS-117 console returned HTTP 200. PostgreSQL,
caregiver HTTPS, development endpoint, certificate-verified laptop HTTPS at
`192.168.1.6`, and the current Windows `192.168.1.6:8445` to WSL
`172.17.152.10:8445` route passed. The previous bounded services expired at
their one-hour limit. The first ingress restart exited before binding because
the launch omitted the existing GS-179 bundled `libpq` path; its log is
preserved. Reusing `gs179-laptop-server.sh`'s existing `PYTHONPATH` and
`LD_LIBRARY_PATH` restored the bounded TEST_ONLY ingress. The existing signed-time
launcher also restored UDP `192.168.1.6:4468`. No certificate, DB record, device
port or credential was changed.

These are host/listener results only. Current bounded ingress runtime reports
`trusted_time_ready=YES` from its host TEST_ONLY provider but
`real_hub_authenticated=NO`, `hub_connected=NO`, and
`monitoring_freshness=UNKNOWN`; the current physical ingress trace is absent.
The signed-time listener request count was zero after restart. No fresh S3
mTLS/identity/time receipt or physical CloudSync receipt exists. The route's
PASS is not a physical receipt.

The S3 installed-image receipt observed 2026-10-26 is older than the fixture's
24-hour limit. No fresh C3 image, active selector or partition-table receipt is
available. The owner-only fixture and five-run approval files are absent. The
current ADB list sees authorized phone `ZA2237MRHN`, but this pass made no new
APK event observation; console APK readiness remains `NOT_VERIFIED` because the
fixture is absent. TC-001 remains 0/5 NOT_RUN; physical PIR remains NOT_RUN.
GS-117 stays OnHold and GS-179 stays In Progress.

There is no tracked JEDEC helper in `code/tools/local` or `code/tests` to fix.
The old helper is a mode-0600 one-off under private local state, outside
supported source; it calls `flash_id()` before SPI attachment and is not reused.
Its offline inspection also found broader eFuse/Jedec operations than the
current scope. No code change or JEDEC test/query is warranted. Offline review
of installed esptool 5.4.0 identified the least-invasive ROM exit candidate:
`read-mac` with `--before no-reset --after hard-reset --no-stub` reads the
expected eFuse MAC without SPI attachment/JEDEC access; common teardown then
uses the RTS hard-reset path. This is a proposal only. It would need a single
COM4 authorization, followed by the existing `GET_STATE` check; stop if the
expected HIL application does not start.

**Single owner approval needed before any new physical operation:** one bounded
GS-117 TEST_ONLY session for the exact C3 `c3-146393c5d158` / COM4 /
`14:63:93:C5:D1:58`, Hub `hub-e072a1d38d34` / COM10 /
`E0:72:A1:D3:8D:34`, Home `gs177-test-product`, and the already authorized
Android phone `ZA2237MRHN`. Permit (1) targeted read-only reads of only each
board's partition table, OTA selector (`otadata`) and selected active app region
to establish current image receipts, starting with C3 while it remains in ROM;
(2) one reapplication, only if COM10 readback/reset clears RAM-only Hub
configuration, of the existing verified GS40 TEST_ONLY encrypted configuration
targeting `192.168.1.6`; (3) after readback, one C3 no-JEDEC `read-mac` plus
controlled hard reset to the existing app and `GET_STATE`; then (4) only after
all fixture, fresh physical ingress, identity and backend gates pass, run the
existing controller for at most five sequential C3
`INJECT_MOTION` inputs, with COM4-open reset risk accepted, COM10 unopened
during campaign runs, automatic exact-key verification through PostgreSQL/API
and the installed APK, and stop at the first failure. Use only the existing
one-use campaign approval guard after readiness passes.

Explicit exclusions: no standalone JEDEC/capacity query; no flash write, erase,
partition/NVS/outbox/credential read or mutation, credential issuance or
replacement, enrollment/ownership/database change, firmware/security change,
factory reset, additional reset/retry after failure, another Home, or PIR test.
Before each port open, revalidate exact USB identity. Any identity, image,
security, configuration or time mismatch stops the session. This single approval
is the next owner action; it is not granted by this checkpoint.

### Previous active checkpoint — GS-117 C3 JEDEC/capacity verified; fixture remains partial — 2026-10-29

Resume base: canonical `feature/r1-commercial-baseline` at
`6918ffcd4ba34bbcf082c9523720ff2df3385fdd`; origin matched. Context preflight
PASS (`2026-10-28.001`). The owner approved exactly one read-only COM4 C3
JEDEC/capacity query. Before open, Windows pySerial identified COM4 as
`14:63:93:C5:D1:58`, VID/PID `303A:1001`, location `1-1:x.0`.

The previous private readback helper still had the faulty call order
`flash_id()` before SPI attachment, so it was not used. Existing Windows
esptool 5.4.0 official `flash-id` CLI was checked offline: its callback calls
`prepare_esp_object -> attach_flash -> flash_id`, contains no flash
read/write/erase command, and accepts one connect attempt, no stub and no
post-command reset. Version/help and source-order checks passed. The single
command was `py -3 -m esptool --chip esp32c3 --port COM4 --baud 115200
--before default-reset --after no-reset --connect-attempts 1 --no-stub
flash-id`.

Hardware result PASS: expected ESP32-C3/MAC `14:63:93:c5:d1:58`, manufacturer
`0x46`, device `0x4016`, detected 4 MB XMC flash, exit 0. Esptool prints the
manufacturer/device fields; per its byte mapping, their combined 24-bit JEDEC
ID is `0x164046`. This resolves the previous all-ones result: the old helper
queried before `attach_flash()`; the official corrected sequence attached
first and returned recognized flash data.

The default-reset connection sequence entered ROM; output ended
`Staying in bootloader.` The no-reset-after option avoided another reset, and
no physical reset edge was separately instrumented. The C3 is left in ROM
bootloader. No flash write/erase, stub, firmware/partition read, COM10/S3
operation, event input, credential/config change or campaign occurred. The
one-query authorization is consumed; no retry or further hardware operation
was performed.

**Fixture result:** the C3 JEDEC/capacity gate passes; the full fixture remains
PARTIAL/BLOCKED. Current C3 app/partition provenance, S3 current-image and
Hub identity/time evidence, fresh S3 mTLS receipt and the owner-only fixture
remain outstanding. The C3 also needs an authorized return to application
state before a functional run. This approval did not cover those operations.
TC-001 remains 0/5 NOT_RUN; its separate campaign approval is absent. The
existing Settings 403 and lack of desired/applied Morning Routine policy
remain as in the preceding checkpoint. GS-117 remains OnHold; GS-179 remains
In Progress.

Private one-attempt evidence:
`~/.local/state/ghar-sajag/gs117-tc001/c3-jedec-once-20261029T034458Z/`
(`result.json` SHA-256
`9ba78a7789dae259b9adacdcaba23cbe7c3e8dd60fab8886158ce441a7c0edad`; log SHA-256
`998df36cc3b5ec73722e485c41ba4e8d2c5e706ff6de5436412456780bdffb03`, mode
0600). No source code changed; no product regression suite was rerun. Unrelated
untracked Android, IDF and historical evidence files remain preserved.

### Previous checkpoint — GS-117 ingress route restored; S3 and fixture still blocked — 2026-10-29

Resume base is canonical `feature/r1-commercial-baseline` at
`893a76f250fa8fb8dfce99fc7102e033682b1bcd`; origin matched before this
evidence-only closeout. Context preflight PASS (`2026-10-28.001`). The owner
completed the elevated action for the existing GS-179 physical-ingress route.
The live GS-117 `/` and `/api/status` return HTTP 200. Read-only status confirms
trusted Private Wi-Fi `.6`, current WSL `.10`, the exact owned `.6:8445 ->
.10:8445` mapping, one Windows listener and the WSL listener. Route status is
PASS. PostgreSQL, local caregiver HTTPS, LAN forwarding and certificate-verified
laptop HTTPS are PASS. No TLS/certificate work was repeated.

The route is not an authenticated Hub receipt: the bounded runtime trace remains
absent/zero, `authenticated_hub` and `fresh_physical_receipt` remain
`NOT_VERIFIED`, and no current physical Hub time proof exists. The previously
verified host-generated signed-time proof was host-only and expired. The
caregiver health script's `HUB_INGRESS_READY=NOT_CONFIGURED` describes its
separate default-disabled ingress composition, not the active bounded
TEST_ONLY listener. Evidence is private at
`~/.local/state/ghar-sajag/gs117-tc001/services-live-20261029T025923Z/console-ingress-readiness-20261029T033127Z.json`
(mode 0600; SHA-256
`72bcf73b862eebdbe69eba9bbb5d6b28c520808cd6a8a18709e6543517fa2be1`).

Settings remains BLOCKED with HTTP 403 because the configured observer account
has `CAREGIVER`/`FAMILY`, while existing policy requires `ADMIN` and durable
`OWNER`/`PRIMARY`. A qualifying account exists but its credentials are not
configured for this observer; the Home has no desired/applied policy row. No
account or configuration was changed. Use the existing authenticated Settings
flow with an authorized owner/primary administrator; do not bypass the guard or
share credentials in chat.

USB discovery confirms only the expected C3 COM4 and S3 COM10 descriptors; no
port was opened. The last authorized C3 flash-ID attempt returned JEDEC
`0xffffff`, capacity unknown, and read no app/partition bytes. That one-attempt
approval is consumed. The current owner-only fixture and independent run/five-
run approvals are absent. The first physical-fixture action is a new narrowly
scoped owner approval for one corrected read-only COM4 JEDEC/capacity attempt
using the existing reviewed procedure (attach SPI flash before `flash_id()`);
stop if the result remains unexpected. This does not authorize readback,
recovery, injection or a campaign. After JEDEC succeeds, separately authorize
any remaining targeted readback/recovery and then request the independent
five-run campaign approval only after all current fixture and S3-authentication
gates pass.

TC-001 remains 0/5 NOT_RUN. No physical event, Hub routine decision or current
Android business-outcome evidence was created. The last authorized Android
observer evidence remains a live phone-to-backend check of historical HOST_SIM
data, not a physical event. GS-117 remains OnHold; GS-179 remains In Progress.

### Previous checkpoint — GS-117 Android observation and ingress readiness — 2026-10-29

Resume base was canonical `feature/r1-commercial-baseline` at
`3ec7831450055bf4258e37b2759cfaaeadeaa6c9`; origin matched. Context preflight
PASS (`2026-10-28.001`). This checkpoint adds one focused change to the existing
GS-117 console: **existing WSL listener check → missing Windows LAN forwarding
check → require the existing read-only GS-179 `PhysicalHubIngress` audit to
confirm the current exact mapping, trusted Wi-Fi and live Windows listener.** It
does not add authentication or a service. It labels Hub authentication and
physical receipt separately `NOT_VERIFIED`.

The supplied Windows ADB executable observed the authorized Motorola Edge 60
Fusion `ZA2237MRHN`; installed package
`in.gharsajag.caregiver.discoverytest` is version
`0.4.0-connected-lite-staging`/versionCode 3. The existing Android observer
verified current API connectivity, Home `gs177-test-product`, Reports and the
historical HOST_SIM EventKey
`p15:test-c3-bedroomn7:bedrooms2026102801q1`. Backend logs showed current HTTP
200 authenticated login, `/me`, and Reports reads. The actual APK displayed
`Backend API · CONNECTED`, Bedroom `Motion recorded`, and TEST_ONLY / physical
origin not verified. The APK hash matches preserved bytes; formal apksigner
verification was not run. This is live phone-to-backend communication, not a
new physical event or Morning Routine result. Evidence remains private at
`~/.local/state/ghar-sajag/gs117-tc001/android-live-check-20261029T025526Z/`.

PostgreSQL, local TLS backend and certificate-verified LAN HTTPS on
`192.168.1.6:443` are PASS. Bounded trusted-time service on `.6:4468` returned a
fresh nonce/generation-matched RSA-3072 proof to a host challenge; physical S3
trusted-time acceptance is not verified. Current WSL ingress listener
`172.17.152.10:8445` and the owned `.6:8445 -> .10:8445` mapping exist, but the
read-only Windows audit reports **zero** `.6:8445` listeners. The console now
reports `hub_ingress=BLOCKED`, reason
`windows_physical_ingress_listener_missing`. Its live `/api/status` returned
HTTP 200 from the restarted existing launcher. The GS-179 bounded runtime has
no physical receipt (`real_hub_authenticated=NO`; trace count zero).

Current controller readiness also reports the exact COM4/COM10 USB descriptors
and historical device identities without opening either serial port. Board
qualification remains PARTIAL. The owner-only current-image/JEDEC fixture and
run/campaign approvals are absent; the authenticated Settings policy read
returned HTTP 403. Morning Routine and TC-001 remain NOT_RUN; no hardware,
ADB mutation, credentials, certificate, or database record was changed.

Focused validation after the source change: Python compilation PASS;
`python3 code/tests/python/test_gs117_tc001_console.py` **63/63 PASS**, including
active-route, WSL-only listener, wrong mapping and untrusted Wi-Fi cases. Live
read-only audit confirms the current block. The controller/test and three
scoped evidence/work-state files were committed as
`f9c997c0b572b48ad1bc164ece387e280220581f` and pushed to
`feature/r1-commercial-baseline`; origin matched that commit after the push.
Unrelated untracked Android, IDF, and historical hardware evidence remains
preserved. No such files were staged.

Next precise action: obtain one elevated run of the existing guarded helper for
`PhysicalHubIngress` on trusted Private Wi-Fi, re-audit the Windows listener,
and wait for a fresh actual S3 mTLS receipt. Independently resolve the controller's
Settings-route 403 and current C3 JEDEC/installed-image fixture evidence. Then
complete the owner-only fixture and obtain the distinct scoped physical-run
approval before any C3 COM4 input. No COM port was opened in this checkpoint.
GS-117 remains OnHold; TC-001 remains 0/5 NOT_RUN and real optical PIR remains
NOT_RUN.

## Latest active checkpoint — GS-117 Morning Routine Run controller — 2026-10-28

Resumed at verified canonical commit `74458e2df560752d41e93c442e05f710e9bd1584`
on `feature/r1-commercial-baseline`; context preflight PASS (`2026-10-28.001`).
The controller/observer follow-on is
`3854d661f731e996a0cc7f26f0a7800a49e3be78`; a read-only SQL guard regression
is `d6a37dc113ead8fe5559a990dcce2974d271e182`, the validated source checkpoint.
Those commits touch only four scoped GS-117 tool/test files. Existing unrelated
untracked Android, IDF and hardware-evidence assets remain untouched. The
previous checkpoint's TEST_ONLY desired/applied policy integration and DTP
register remain in the following historical section.

**Existing implementation → gap → minimum change.** The configurable
MorningRoutine RulesCore, TEST_ONLY desired/applied policy repository and S3
application path, GS-179 backend, GS-117 fixed Bedroom campaign/USB helper, and
the installed-APK ADB observer already exist. The Run panel previously persisted
BLOCKED readiness only, while its observer proved a Node motion EventKey rather
than the separate Hub-owned completion. Extended the same controller to perform
one Bedroom-only run only after current applied policy, enrolled-room mapping,
physical identity/image/JEDEC fixture, backend/Home, Android, fresh ingress and
one-use run approval all pass. It reuses the existing C3 COM4 helper and exact
Node-to-APK flow, then requires one PostgreSQL `MORNING_ROUTINE_COMPLETED` row
joined to the original EventKey, the same authenticated caregiver API decision,
and the exact Hub Decision ID in the actual APK Reports details with private
screenshot/accessibility evidence. The established fixed five-run TC-001 flow is
preserved. Additional enabled rooms without their own enrolled Node remain
BLOCKED; Bedroom cannot stand in for Kitchen or another location.

This is controller/observer integration, not a new backend or rule engine. The
separate one-use Morning Routine approval is not present or consumed. No COM,
USB, ADB, flash, reset, credential, enrollment, database mutation, or physical
input occurred. The mocked one-click test proves orchestration/fail-closed
contracts only; it is not a real-device Run or APK observation.

Focused validation on source commit `d6a37dc`:

- Python compilation of the three existing GS-117 tools and their regression:
  PASS.
- `python3 -m unittest tests.python.test_gs117_tc001_console -v`: **58/58
  PASS**, including exact decision identity, screenshot/accessibility digest,
  missing one-use approval, wrong decision, and un-enrolled extra-room guards.
- `PYTHONPATH=. python3 -m unittest tests.python.test_component_gate -v`:
  **55/55 PASS**.
- `make feature-coverage-test`: PASS; **226 features, 286 source modules, 27
  physical cases**, with **22/22** traceability registration tests. Mapping
  consistency is not physical or semantic qualification.
- `git diff --check`: PASS.
- No target build was needed for these Python-only controller and ADB-observer
  changes; existing firmware and configuration integration were not modified.

Read-only current host health: PostgreSQL TLS/durability and local caregiver
HTTPS on WSL `172.17.152.10:8444` PASS; phone-facing LAN HTTPS at
`192.168.1.6:443` FAIL/timeout. No physical ingress TCP `8445` or signed-time
UDP `4468` listener is active. The backend reports no authenticated Hub identity,
unknown monitoring freshness and no persistent ingress configuration. The
current owner-only fixture/current C3 JEDEC-image evidence, fresh physical S3
receipt and separate Morning Run authorization are not established. No current
APK decision observation was made. GS-117 remains OnHold; TC-001 is 0/5
NOT_RUN and real optical PIR is NOT_RUN.

The existing development-to-production register remains the single register:
`DTP-001..010` in `DEV_TO_PRODUCTION_REGISTER.md/.json`. Production identity,
issuer/key lifecycle, caregiver production issuer, middleware/deployment,
hosting, signed firmware/root-of-trust, external notifications and final
production Android qualification remain release-gated; none is substituted by
this DEV controller. DTP-001..009 remain open; DTP-010 only qualifies existing
TEST_ONLY build-profile isolation. No production endpoint or security control
was activated.

Next action: restore the already-owned laptop LAN HTTPS route only through its
approved UAC procedure; restore bounded 8445/4468 service under the existing
GS-179 procedure; then obtain current C3 JEDEC/image and S3 configuration/auth
receipts and validate the owner-only fixture. If every readiness gate passes,
obtain a separate one-use Bedroom Run approval, then exercise the existing
Morning Routine Run once and require actual S3 completion, PostgreSQL/API, and
APK decision evidence. Do not start another room or the five-run TC-001 campaign
without its applicable independent approval.

## Prior checkpoint — GS-117/GS-179 TEST_ONLY Morning Routine integration — 2026-10-28

Resumed from canonical commit `a92bd8214df67ae68ac5e902bf2b2f49367223ec` on
`feature/r1-commercial-baseline`; local and origin matched at resume. The
validated implementation is committed as
`732b848df157859cffaf813332d8ab1e0058ad7a`; the documentation checkpoint is
being finalized against that source. Context preflight passed on resume and
again during closeout (`2026-10-28.001`). Unrelated untracked Android, IDF and
hardware evidence is preserved. No hardware, COM/USB, ADB, credential, or
protected household-data operation was performed.

The approved DEV direction reuses the existing isolated GS-40/GS-179 TEST_ONLY
profile. Production issuer, credential lifecycle/provisioning, commercial
hosting and irreversible security activation remain release gates, not DEV
prerequisites. Reused the existing GS-76 caregiver session boundary, GS-109/
GS-148 Hub authority model, Home/Hub/epoch registry, PostgreSQL configuration
repository, GS-117 controller, RulesCore, CloudSync and Android observer.
Implemented only the missing integration in the existing TEST_ONLY composition:
authorized Settings writes versioned desired policy, the authenticated S3
configuration fetch validates and applies it, the Hub checkpoints the complete
policy and timezone before returning applied-version acknowledgement, and the
existing Settings/status view distinguishes desired from applied.

The applied policy now preserves its version and timezone in Hub checkpoint
schema v6; stale/conflicting versions fail closed and policy/timezone changes
reset routine progress. The existing Morning Routine web Run remains gated on
fixture, authorization, authenticated physical ingress and Android readiness;
no simulated event or decision can make it pass. The release-owned register is
`docs/product/DEV_TO_PRODUCTION_REGISTER.md` and `.json` (GS-173, enforced by
GS-116). It distinguishes implementation state from effective DEV state and
production readiness; production release remains NO-GO for unresolved mandatory
gates and pending scope.

Validation on implementation commit `732b848df157859cffaf813332d8ab1e0058ad7a`:

- Hub checkpoint host suite: PASS, including schema-v6 timezone restore,
  same-version conflict rejection and higher-version advancement.
- GS-179 runtime composition against isolated schema on existing TLS
  PostgreSQL: 5/5 PASS; no shared/public household rows changed.
- GS-179 PostgreSQL/security integration against isolated schema: 21/21 PASS.
- Backend Python tests: 24/24 PASS.
- Android server tests: 28/28 PASS.
- Caregiver JavaScript runtime: 11/11 PASS.
- GS-116 component-gate tests: 55/55 PASS, including the register status
  vocabulary and release-stage registration.
- CloudSync security, Hub checkpoint and P2D HTTPS host suites: PASS.
- Fresh paired C3/S3 production-profile build: PASS using the existing builder
  at `code/build/validation_targets/gs116-ktfj60_m/report.json`. C3 image
  944,272 bytes, SHA-256
  `6d65ce180a926b7e0388032ac65f9a40b8de6813a79396aa62b8e4c4d4d7c522`; S3
  image 2,201,168 bytes, SHA-256
  `9544d3afa20dc2b376ffa5af8e65c518776eb84456560372318448b04766f99c`.
  Cache guard verified TEST_ONLY CloudSync, HIL controls, commissioning and
  external TEST_ONLY root are disabled/absent. Report source head is 732b848.
  `TARGET_COMPILED_ONLY`; no image was installed.
- Isolated TEST_ONLY S3 target build: PASS after fixing an ESP-IDF 6.0.3
  dependency declaration in the existing TEST_ONLY composition. Reused the
  existing cached/pinned Espressif cJSON 1.7.19~2 package, declared only for
  ESP32-S3, and changed the conditional component from `json` to `cjson`.
  Image size 2,271,744 bytes; SHA-256
  `f1890698945acf502d43645faf5be7f0207cdc977f47d7bdfa644f636cb7e949`.
  `GS40_TEST_ONLY_CLOUDSYNC=ON` used an external TEST_ONLY public root;
  `GS_HIL_BUILD`, `GS_HIL_CONTROL` and `GS_HIL_COMMISSIONING` were OFF. The image
  was not installed. A fresh incremental production-profile S3 rebuild after
  this manifest/CMake change completed successfully: 2,201,049 bytes,
  SHA-256 `989d0a20d8f38487d86d6fb2e3f5d4379b844fd1e2c712c45ddceb519f00948d`.
  The S3 cache guard confirmed TEST_ONLY CloudSync, HIL build/control,
  commissioning OFF and an empty external TEST_ONLY root. The build emitted
  existing unused-variable and ESP-IDF Kconfig value warnings but exited 0.
  This is compile/profile evidence only; no image was installed.
- `make -C code validation-board-e2e`: PASS, 10 software checks; physical status
  NOT_RUN. This is not board acceptance.
- GS-117 focused console/ADB regression: 50/50 PASS after adding checks that
  readiness uses the authenticated existing Settings route and Morning Run
  remains physically blocked despite software policy acknowledgement.
- Read-only `code/tools/local/gs179-laptop-server.sh health`: local PostgreSQL
  TLS/durability and caregiver HTTPS on WSL port 8444 PASS; LAN HTTPS at
  `192.168.1.6:443` FAIL/timeout. Windows proxy audit found the existing owned
  `.6:443 -> 172.17.152.10:8444` and `.6:8445 -> 172.17.152.10:8445` mappings,
  but listener/firewall inspection is blocked without Windows administrator
  access. The existing `proxy-start` guard stopped with
  `administrator_token_required_for_scoped_portproxy_and_firewall_rule`
  before making changes. No Windows route was altered.
- WSL physical ingress TCP 8445 and signed-time UDP 4468 are not listening.
  Metadata-only checks confirm the owner-only TC-001 fixture and five-run
  approval files are absent; their contents were not read.
- `python3 code/validation/dev_to_production_gate.py` reports the expected
  release NO-GO with open mandatory/deferred gates; this is not a DEV test
  failure. Full release gate and unrelated GS-178 39-case suite were not rerun.
- Browser UI testing is NOT_RUN because Chrome/Chromium is unavailable. Actual
  Android APK/ADB observation is NOT_RUN in this session.

Physical/target acceptance remains blocked: C3 JEDEC identification is still
`0xffffff`/unknown capacity; current installed-image provenance and fresh
physical S3 authentication are absent; no actual S3 policy application or
`MORNING_ROUTINE_COMPLETED` decision has been observed; the owner-only fixture
and separate Run authorization are absent. Bedroom is the only established
physical Node room. GS-117 remains OnHold; TC-001 and optical PIR remain
NOT_RUN. No board or APK result is inferred from target compilation or tests.

Next action: commit/push this evidence and register update, then post concise
observed results to GS-116/117/148/173/179 without changing ticket statuses.
Restoring phone-facing HTTPS requires owner-provided Windows UAC elevation for
the existing scoped route helper. A first real Bedroom-only Run additionally
requires active bounded 8445/4468 services, current C3 JEDEC/image and S3
image/configuration evidence, an owner-only fixture, fresh physical S3 mTLS,
and separate scoped hardware Run authorization. No hardware action is
authorized by this development checkpoint.

## Prior checkpoint — GS-117 Morning Routine config repository and console gate — 2026-10-28

Resumed from canonical commit `5687854d700b4e97bd5f975c6b820c13dd3d365b` on
`feature/r1-commercial-baseline`; local and origin matched and context preflight
passed. Pre-existing unrelated untracked Android/IDF/physical evidence was
preserved. No hardware, ADB, protected database, credential or enrollment
operation was performed.

The validated implementation and evidence are committed as
`bb7fe430f4ce8447692025ca334d7349cca6e196`, pushed normally, and verified equal
to origin at this source checkpoint. All test results below apply to that
source commit.

Added `PostgresConfigurationRepository` over the existing versioned
`configurations` and `audit_log` schema. Desired publish requires a live
`ActorSession` and an injected current Home-settings authorization callback;
Hub read/apply requires a `VerifiedHubContext`, an injected trusted-Hub
authorization callback, and an in-transaction recheck of active Hub/Home/epoch
and ownership fingerprint. Config validation reuses `FleetService` policy
validation. Expected-version conflicts, stale acknowledgements, wrong/revoked
ownership and missing/denied authorization fail closed. Desired and latest
applied policy remain distinct. This class installs no API route and does not
provide the pending credential issuer, caregiver/Home membership authority,
trusted mTLS middleware, Hub fetch/apply transport, or S3 restart persistence.
Contract tests use the existing migrations under SQLite; live PostgreSQL
execution is NOT_RUN.

Extended the existing GS-117 loopback console with a Morning Routine panel,
read-only applied-version/room fields, bounded TEST_ONLY stimulus interval
(default 10 seconds), one Run action, persisted report history and explicit
stage states/first blocker. The fixed TC-001 Bedroom five-event campaign stays
in place. While auth/config/physical gates are unavailable, Run saves a
`BLOCKED` report with no event keys and no physical operations; the API route
does not invoke USB/ADB or claim physical success. The current report's first
blocked stage is `applied_household_policy`. Only Bedroom is an established
room fixture; no other room is mapped to it. No actual Hub policy was fetched
or applied and no scenario event/Android business decision was observed.

Added the decision-ready GS-68/GS-109/GS-148 RSA-3072 DS/mTLS and GS-76
caregiver-session approval delta to the existing GS-109/GS-148 package. The
four requested dispositions are Hub identity/issuer lifecycle, caregiver
issuer/revocable session and Home-settings authority, Home/epoch source and
manifest-vs-online binding, and trusted TLS middleware/deployment boundary.
All remain pending owner/security approval; no identity mechanism was selected
or activated. GS-117 remains OnHold at TC-001 0/5; GS-109/148/178/179 remain
In Progress; physical PIR and all real Morning Routine execution remain
NOT_RUN/BLOCKED.

Focused validation on this working tree: backend tests 20/20 PASS (including
five repository contract cases), GS-117 console tests 47/47 PASS, and
`make -C code feature-coverage-test` PASS (226 features, 286 source modules,
27 physical cases, mapping tests 22/22). JSON parse, Python compile, inline
console JavaScript syntax and `git diff --check` passed. Full Python/backend,
Hub/contract aggregates, live PostgreSQL, C3/S3 builds, browser, Android and
physical campaign were not run. Historical validation-hub migration/P0 and
validation-contract P0 failures remain unchanged and are not reclassified.

Next action: obtain the four owner/security dispositions and the exact config
fetch/apply contract before connecting production auth or transport; then
continue with the approved Settings → PostgreSQL → authenticated S3 persistence
path. Keep Morning Routine Run blocked until a current trusted applied policy,
separate enrolled input per required room, fresh physical S3 receipt, current
fixture and scoped hardware authorization exist.

## GS-178 software use-case batch S4 — 2026-10-27

Owning Jira GS-178; feature inventory GS-130; regression policy GS-116. Resume
checkpoint before this batch was `7e85b27b55556af23138c29cc46ed093c70568d3`
with local/origin equal and context preflight PASS. The worktree had preserved
untracked Android/PWA/IDF/physical evidence; only the intended GS-178 test and
this batch's documentation were changed.

Audit of GS-178/GS-130/GS-116 scope and the canonical identity rules found that
the existing production `HubOwnershipRegistry.authorize_cloud_event` guard
binds a CloudSync EventKey's physical ID, logical Node ID and active enrollment
generation. Existing security tests reject wrong Home, stale enrollment and
changed same-key content, but the existing multi-Node caregiver vertical did
not verify rejection of a new unregistered physical/logical pair while proving
the caregiver projection remains unpolluted. Classification:
`IMPLEMENTED_NOT_YET_VALIDATED`. No production defect or source behavior change
was found; the existing NodeRuntime, authenticated Hub, CloudSync, durable API,
caregiver API and browser were reused.

Extended `test_24_multinode_room_identity_and_door_chronology_in_caregiver_view`
with the R1AUTO-010 negative and recovery checks. After five properly enrolled
TEST_ONLY events were durably committed, a TLS-authenticated request pairing
physical `test-c3-bedroom` with logical `bathroom` returned
`403 hub_not_authorized`. Durable event and commit counts remained five. The
exact original bedroom EventKey then retried as `COMMITTED, duplicate=true`;
the caregiver API retained the five correct keys/rooms and Chromium verified
the exact chronology/labels before and after reload. Evidence is in
`code/build/gs178_s4_20261027/` under
`R1AUTO-010-WRONG-NODE-ROOM-PAIRING.json`.

Validation: focused test 1/1 before commit (20.793s); full existing
`GS178_REPORT_DIR=build/gs178_s4_20261027/full-suite make -C code
gs178-software-e2e` 39/39 PASS (15 security + 24 vertical, 582.279s); focused
test 1/1 on code commit `ee772be986ce401b130803b8a92f35e8bb5fcaf6` (15.790s). All results are
`HOST_SIM_PASS` on isolated SQLite/Chromium. Actual Android remains
`APK_NOT_VERIFIED`; physical qualification is `NOT_RUN`. No hardware, ADB or
COM was used. Five-run TC-001 remains 0/5 NOT_RUN and GS-117 OnHold.
The ephemeral GS-178 fixture is loopback-only and shuts down with the test, so
the installed Android APK cannot observe these specific EventKeys; browser
assertions are not APK evidence.

Code/test commit: `ee772be986ce401b130803b8a92f35e8bb5fcaf6`. After the
traceability row update, `make -C code validation-framework-test
feature-coverage-test` passed: framework 51/51; traceability 226 features,
285 modules, 27 physical cases and 22/22 mapping tests. Trace consistency does
not prove exhaustive semantic or physical coverage. The documentation
closeout/push and Jira comments follow this code-bound validation.

GS-178, GS-130 and GS-116 stay In Progress; all 17 P0 groups remain PARTIAL.
GS-130 catalogue comment 11728 makes R1AUTO-011 the next priority:
durable-before-ACK and immutable EventKey through Node, Hub, ingress,
PostgreSQL and caregiver. Audit existing GS-178 event/retry cases and GS-179
PostgreSQL coverage before adding any test; reuse existing paths and report
separately if the only missing evidence is the joined PostgreSQL projection.

## GS-178 software use-case batch S3 — 2026-10-27 (validated and published)

Owning Jira GS-178; coverage inventory GS-130; regression policy GS-116. This
batch resumed at canonical HEAD `b2aab27a049927718c21198bb5787adbf7c587b3`
after S2. Context preflight passed. No competing writer was present; tracked
files were clean at start and pre-existing untracked Android/PWA/IDF/physical
evidence remains preserved.

The audit mapped the next implemented-but-not-yet-joined slice to proposed
R1AUTO-009: separate first-sequence EventKeys from bedroom, bathroom, kitchen,
and door Nodes; preserve door OPEN/CLOSE meaning and order through the
caregiver timeline. Existing NodeRuntime, authenticated Hub admission,
CloudSync, durable API/read model, and caregiver browser were reused. S2's
`test_23` covers outage recovery; existing tests cover API door semantics and
the left-open rule. The missing assertion was the four-Node exact-key/room
projection plus door labels after caregiver reload. Classification:
`IMPLEMENTED_NOT_YET_VALIDATED`; no production defect or production code
change was made.

Added `test_24_multinode_room_identity_and_door_chronology_in_caregiver_view`
to the existing `gs178-node-caregiver-e2e` stage and extended its current
browser observer. The new trace case is
`GS178-DOOR-MULTINODE-01`. Focused test passed 1/1 in 23.683s; the existing
one-command `GS178_REPORT_DIR=build/gs178_s3_20261027/full-suite make -C code
gs178-software-e2e` passed **39/39** (15 security + 24 vertical, 473.805s).
The registered framework passed 51/51. Feature mapping passed 226 features,
285 modules, 27 physical cases and 22/22 mapping tests. `git diff --check`
passed.

The exact test report records five distinct Node EventKeys (three Nodes at
sequence 1; door sequence 1 and 2), five authenticated `COMMITTED` receipts,
one durable row for each key, and browser verification of all keys/labels/room
identities after reload (4 assertions). Observed newest-first keys were
`test-c3-door/door/session-10/sequence-2` (`DOOR_CLOSED`),
`test-c3-door/door/session-10/sequence-1` (`DOOR_OPEN`), then
`test-c3-kitchen/kitchen/session-10/sequence-1`,
`test-c3-bathroom/bathroom/session-10/sequence-1`, and
`test-c3-bedroom/bedroom/session-10/sequence-1` (`MOTION`). It is
`HOST_SIM_PASS`; its backend is
isolated SQLite, not PostgreSQL or a production deployment. Actual Android is
`APK_NOT_VERIFIED`, and physical qualification is `NOT_RUN`. No hardware,
ADB or COM was used.

The code/test commit is `a98c1830aa4309805e2d244fd88595d00fc45f0c`.
The focused test passed again on that exact commit (1/1 in 21.788s); its report
records the same five receipts/rows, browser 4/4, null first failure,
`HOST_SIM_PASS`, physical `NOT_RUN`, and `APK_NOT_VERIFIED`. The full 39/39 suite
ran on the identical code tree before commit. Its reports remain under
`code/build/gs178_s3_20261027/`. The code/test commit is `a98c1830aa4309805e2d244fd88595d00fc45f0c`;
evidence/traceability updates were committed and pushed normally. At the
publication checkpoint, local and origin matched at `a0a28fd4cba886068c6c620f5235737ae3bb9a6f`.
The final GS-178/GS-130/GS-116 Jira comments record the resulting source and
remote SHAs. GS-178 stays In Progress; all 17 P0 groups remain PARTIAL. GS-117 stays OnHold with
TC-001 0/5 NOT_RUN. The S3 checkpoint's next audit target was proposed
R1AUTO-010 invalid-input and wrong Node/room enrollment rejection. S4 above
completes that software check by reusing existing ownership and admission
guards; no new input path was added. Continue without physical access.

## GS-178 software use-case batch S2 — 2026-10-27 (validated and published)

Owning Jira GS-178; feature coverage GS-130; regression governance GS-116.
S1 was completed and pushed at `9e87c435db805f14be165286dc5cc9a5dd05a9ce`.
S2 started on the canonical `feature/r1-commercial-baseline` worktree at that
same local/remote SHA. Its code/test/evidence commit is
`bfbae7796df55a0db098ab7c6e13232d2f558808`; its evidence/source-bound closeout
commit is `392ec21b0965672ca981b6740e164078ef2f2ed2`. Both were pushed. At the
closeout verification checkpoint, local and origin both equaled
`392ec21b0965672ca981b6740e164078ef2f2ed2`; tracked files were clean and
pre-existing untracked Android/PWA/IDF/physical evidence remained untouched.
The S2 evidence now explicitly distinguishes the isolated SQLite vertical
backend from separate GS-179 PostgreSQL coverage.
Context preflight passed. Latest Jira decisions
11748/11749/11750 require the existing software E2E campaign, incremental
coverage, and no hardware prerequisite. The source, GS-178/130/116 scope,
P0-UC-09 requirement, suite registration, previous case 02, board-stack
outage cases and current evidence were audited before editing.

At the audit boundary, S2 classification was `IMPLEMENTED_NOT_YET_VALIDATED`.
The gap is now host-validated for this workflow. Existing NodeRuntime,
authenticated HubRuntime admission, durable outbox/ACK, CloudSync, backend
commit/read model and caregiver projection were reused. There was no production
product defect and no production behavior change. The smallest addition is a
bounded Hub-radio response control in the existing TEST_ONLY simulator, one
vertical test 23, and two assertion branches in the already-used browser helper.
It covers Node-to-Hub link loss and retained identity, stale/unknown caregiver
state without fabricated activity, local durable ACK while WAN is unavailable,
Hub restart, exact-once backend recovery, API chronology and exact browser keys
before/after reload.

Validation so far: `make -C code gs178-host-build` PASS; focused test 23 PASS
1/1; existing one-command `gs178-software-e2e` PASS 38/38 (15 security + 23
vertical, 273.500 seconds). The framework suite passed 51/51. The first
feature-mapping run failed because its assertion-anchor field accepts a single
source-resolving test, not a semicolon list; after pointing to test 23,
`feature-coverage-test` passed (226 features, 285 modules, 27 physical cases,
22/22 mapping tests). Generated reports under
`code/build/gs178_s2_20261027/full-suite/` show `HOST_SIM_PASS`, null first
failure, physical `NOT_RUN`, and Android `APK_NOT_VERIFIED`. Registration
integrity checks now pass. After commit
`bfbae7796df55a0db098ab7c6e13232d2f558808`, test 23 passed again 1/1 in
24.047 seconds; its separate report records that exact source SHA, null first
failure, `HOST_SIM_PASS`, physical `NOT_RUN`, and `APK_NOT_VERIFIED`. Browser means
the shared TEST_ONLY caregiver UI; no installed APK or device was used.

P0-UC-09 and all 17 P0 groups remain `PARTIAL`. Production deployment auth and
backend path, physical RF/storage behavior and actual Android APK remain
unverified. GS-117 remains OnHold; no hardware, ADB or COM access was used.
The full-window observation history/calendar prompt requirement remains open;
GS-104 learning remains on hold. The unrelated pre-existing CSS budget failure
(29,576 bytes vs 18,432) reported during S1 remains open with GS-177; S2 did not
modify CSS. No full release gate was run.

The S2 batch is complete. GS-178 remains In Progress because all 17 P0 use
cases and the R1 product gate remain PARTIAL. GS-117 remains OnHold with
physical TC-001 0/5 NOT_RUN; S2 used no hardware, ADB or COM access. Next
priority at S2 closeout was the next audit-selected, implemented-but-not-yet-
validated P0-A software case. S3 below records that follow-up and its result.
Do not start physical qualification or held GS-104/conditional behavior
without applicable approval.
Unrelated untracked Android/PWA files, generated IDF state and physical
evidence remain preserved.

## GS-178 software use-case batch S1 — 2026-10-27 (completed/pushed)

Owning ticket GS-178; coverage inventory GS-130; regression policy GS-116.
The owner directed that the existing `make -C code gs178-software-e2e` campaign
advance independently while GS-117 stays OnHold. Canonical branch is
`feature/r1-commercial-baseline`, based on commit
`f7168825a4751330629bf285c3bad83c21a87b51`; the S1 closeout was committed as
`9e87c435db805f14be165286dc5cc9a5dd05a9ce` and pushed with remote equality
verified. The canonical worktree and
context preflight passed. The tested code subtree is
`052d1c2c9e2a59c052a76660b281a30f9f5414e7`. The existing GS-178 implementation and current
Jira scope were audited before completing this batch. No hardware, serial port,
Android device, APK, physical sensor or service recovery was accessed.

The batch found and fixed two real coverage correctness gaps using existing
runtime paths: authenticated NodeHealth contact had no trusted UTC forwarded to
Hub coverage; and the caregiver NodeHealth projection omitted active enrolled
Nodes with no observation, allowing incomplete monitoring to look covered.
Contact freshness is not resident activity and cannot create an EventKey. The
backend now returns `UNKNOWN` with null contact metadata for a never-observed
active Node, joining only current authority. Four deterministic GS-178 vertical
cases (tests 19–22) exercise missing-morning decision boundaries, never-seen
and expired coverage, trusted-time and mode suppression, lost COMMITTED receipt,
restart/retry, browser-visible outcomes and recovery. Full-window observation
gap history/calendar prompts and GS-104 learning remain unimplemented/on hold;
they are not inferred from these tests.

Current validation: existing one-command suite 37/37 PASS; repeat of test 19
1/1 PASS with a fresh Node session; C3/S3 production target builds PASS without
flashing; ASan/UBSan target PASS (C++ 1,516 checks and GS40 1,320); Hub
checkpoint/replay and P2D CloudSync contract PASS; board-stack 10 scenarios
PASS; registry and focused result details are in the GS-178 execution record.
`make -C code python-test` ran 623 tests: 621 PASS, one approved historical
ESP32 reserve test skipped, and one existing PWA static CSS budget test failed
(29,576 bytes vs 18,432). The changed files do not include that CSS; retain the
failure for the existing caregiver-app owner rather than expanding this batch.
Final framework validation passed 51/51. The first traceability attempt exposed
three incorrect source/stage ownership mappings; after mapping the C++ and
Python regressions to their existing `cpp` and `python` stages,
`feature-coverage-test` passed 226 features / 285 modules / 27 physical cases
and its 22 registration tests. Documentation, commit, push and Jira comments
11752 through 11756 were verified. R1 `product_status` and all
17 P0 use cases remain PARTIAL. Actual Android APK and physical qualification
remain unverified/NOT_RUN. Full release gate was not run.

Next software-test priority: extend the existing GS-178 vertical around the
already registered R1AUTO-027/028 outage cases so one caregiver-visible test
distinguishes a Node-to-Hub outage from a WAN-only outage, then verifies
original EventKey retention, truthful stale/unknown state and exact-once
catch-up. GS-178 case 02 and the board-stack suite cover related pieces; audit
and reuse them rather than adding another runner. Full-window observation-gap
and calendar/prompt behavior is a separate requirements gap: coverage formulas
remain open, so do not invent that behavior. Actual APK observation requires
separately scoped ADB authorization; physical HIL, `validation-fast` and release
gates remain outside this batch.

At the S1 checkpoint, only its validated source/tests/traceability/evidence
were committed. Unrelated untracked PWA, Android, managed-component, sdkconfig
and historical physical evidence remained untouched. GS-177 was notified of
the separate CSS budget failure. GS-117 remains OnHold because the preserved
C3 raw JEDEC result was all ones; offline tool inspection suggests the prior
helper omitted esptool's existing flash-attach step, but current capacity is
still UNKNOWN and no hardware retry is authorized.

## GS-178 P0 software readiness and targeted regressions — 2026-10-19

Current source checkpoint before this evidence closeout: canonical branch
`feature/r1-commercial-baseline`, local HEAD
`cc7d6ab32c756219320777f8afe1592e5a962337`, source tree
`75d631cf1b1303dc6b773fe284888da4f42321f9`. The code changes are in
`94591ab51dd393af730c8edcc772838d171a2ff2` (TEST_ONLY India local-minute
adapter and caregiver bundle split) and `cc7d6ab32c756219320777f8afe1592e5a962337`
(service-worker v5 stale-cache purge and regression). This evidence/work-state
bundle was committed as `4d66110`, followed by closeout commit `d883c75`; both
were pushed normally with the preceding source commits. `git ls-remote` matched
local HEAD at `d883c75`. Context preflight passed (`2026-10-13.001`). No other
worktree, physical board or production service was used.

The source-linked matrix is
[`GS178_P0_SOFTWARE_READINESS_MATRIX_20261019.md`](../exec-plans/evidence/GS178_P0_SOFTWARE_READINESS_MATRIX_20261019.md);
all 17 registered P0 use cases remain `PARTIAL`. Deterministic approved rules
have a host path through production HubRuntime/checkpoint, CloudSync, local
authenticated backend and caregiver projection. TEST_ONLY target scheduling
now derives Asia/Kolkata local minute from authenticated UTC; missing time,
overflow or unsupported zone fails closed. The change does not approve a
commercial timezone policy or implement GS-104 learning.

Only affected regression checks were rerun after the user's direction to limit
validation scope: bootstrap 47 checks, GS-178 E2E 27/27, Hub checkpoint two
assertion groups, PWA startup profile 62,513/114,688 bytes, focused caregiver
browser 3 tests / 92 assertions, Phase 3A desktop/mobile 8/8, framework 51/51,
and traceability mapping 22/22. One `validation-hub` run already completed on
`94591ab` before that direction; component stages passed except the existing
`clean migration commits` assertion, and the aggregate also correctly failed
the mandatory P0 `product_status=PARTIAL` check (26/26 scenario assertions).
No additional broad component or release aggregate was run after the direction.

ESP-IDF 6.0.3 source-bound, non-flashing builds on `cc7d6ab` passed. Standard
production C3 is 937,536 bytes, SHA-256
`384eb4f5b194fb02d3d49044f952d3d7fbb2a01f14ca29d63ea17d06d3aea37d`; S3 is
2,184,704 bytes, SHA-256
`f10393df9bafb78bb419fc8d8be9fb564434e2f93fcfa7323414877bc7b7378c`. The
guarded GS40 TEST_ONLY S3 product image is 2,233,392 bytes, SHA-256
`da3b28c54dd9e06e88b25b12a96c0f9fa3f2d80c07c190b6a6fadfa41e2eb1c6`, ESP
validation hash
`294bd9e668ad71870c212a59b030267708d8238e43ed0a63133c3bfa8fde1761`,
effective sdkconfig SHA-256
`3750bc9360e4524d61d8209e2cbe7014f67be9ee55dcb553033bcc9858c83099`. Both
fit their slots. With `SOURCE_DATE_EPOCH=1792429200`, a clean same-directory
rebuild was byte-identical; separate absolute paths change the ELF digest
embedded in app metadata and the dependent image footer. The commercial
profile remains `GS40_TEST_ONLY_CLOUDSYNC=OFF`, DS peripheral enabled and
linked to fail-closed `UnprovisionedS3CloudTrust`. Neither image was flashed.

Open status is unchanged: R1 `product_status=PARTIAL`; 17/17 P0 matrix rows
PARTIAL; journal migration gate still fails `clean migration commits` and needs
GS-173 adjudication against the R1 release contract; GS-104 R01–R09 remains on
hold; current-image sensor, target runtime and all physical cases are NOT_RUN;
production identity/issuer, notification delivery and phone acceptance remain
unqualified. The Android APK was not assembled here. Full
`release-gate-final` was NOT_RUN. Untracked PWA, Android, managed components,
`sdkconfig`, GS-114/C8/GS-40 evidence and historical worktrees remain
preserved.

An unrelated tracked edit to `code/firmware/node/power/power.cpp` was present
during closeout. Its diff changes optional retry-state handling to avoid a GCC
`-Werror=maybe-uninitialized` false positive; it was not part of this evidence
work and is excluded from the documentation commit. It remains untouched and
uncommitted.

## GS-178 S3 deterministic rule-runtime integration — 2026-10-19

Implementation commit `487ffa03e2cc95d84a8eafa5a51016fe413cdce7` integrates
Hub-owned deterministic rule decisions into the S3 product source. HubRuntime
checkpoint v3 persists rule state and bounded decision-publication intents
together; v1/v2 decoding is preserved. Decisions use identities separate from
Node EventKey. Replayed admission reconstructs the same decision identity, and
the S3 adapter retires a publication intent only after its matching backend
`COMMITTED` receipt is checkpointed. Trusted time and current Hub/Home/epoch
authority gate target rule scheduling; unsupported TEST_ONLY timezone
configuration fails closed. The host GS-178 path uses the production HubRuntime
and existing CloudSync/backend/caregiver code.

`make -C code gs178-software-e2e` passed 27/27; the registered checkpoint stage
passed two assertion groups; board-stack simulation passed 10 scenarios. The
ESP-IDF 6.0.3 standard C3/S3 profile and explicit GS40 TEST_ONLY S3 product
profile both built without flashing. Detailed source, tests, exact artifact and
configuration hashes, and aggregate gate failures are in
[`GS178_S3_RULE_RUNTIME_20261019.md`](../exec-plans/evidence/GS178_S3_RULE_RUNTIME_20261019.md).

Validation is not release acceptance: `validation-hub` still has the existing
`clean migration commits` failure and required P0 `product_status=PARTIAL`;
`validation-contract` also correctly fails on P0 PARTIAL. No target or physical
execution is claimed. GS-40/GS-117/GS-121 remain NOT_RUN physically; GS-104
R01–R09 stays on hold. The implementation source commit was local one commit
ahead of origin when this update began. Commit and verified remote equality for
this evidence update are reported in the execution closeout.

## GS-178 Node-originated software vertical — 2026-10-19

Resumed from canonical HEAD `ceeddc0ff1f670d78414baddccdfcf9f9c89fcd0` on
`feature/r1-commercial-baseline`; the initial local and origin HEADs matched and
context preflight passed. The host vertical now carries Hub-owned deterministic
rule decisions through a separate TEST_ONLY receipt/outbox path, backend
storage and caregiver projection. It preserves Node EventKey and durable event
semantics. The expanded `make -C code gs178-software-e2e` passed 27/27.
Hub/CloudSync and backend trust regressions passed in the affected stages.

The latest registered component-gate executions have honest aggregate failures:
Hub fails the existing journal migration assertion (`clean migration commits`)
and required P0 composition because `product_status=PARTIAL`; backend and
contract gates likewise retain P0 PARTIAL, plus backend's existing static PWA
bundle budget failure (117011 bytes total vs 114688; CSS 21694 vs 18432). The
PWA gate ran 83 browser tests successfully and had three settings-page locator
timeouts; its legacy `pwa_68_browser_test.py` stage also lacks the Python
`websocket` module. These failures were not suppressed or reclassified. Board
stack simulation passed 10 checks. The non-flashing ESP-IDF 6.0.3 C3/S3 build
passed on source commit `2a389febe472c5e8a31da4a745dd8423a1087527`. S3 is
2,168,368 bytes (SHA-256
`310bafecbae5289fe4850edbb1d79c6f7714811fcce53df60f399fd0fd54ebe2`) and fits
its 4,194,304-byte OTA slot. This is a production-profile target compile, not
proof of TEST_ONLY runtime composition or physical behavior. Android local APK
build is unavailable in the current environment. The registered P0 scenario
reports 26/26 assertions and browser PASS but remains an aggregate gate failure
while required product status is PARTIAL.

Historical target gap at the earlier `ceeddc0` checkpoint: the host simulator
then used a separate rule outbox, while the S3 scheduler did not persist
publication intent with the Hub checkpoint and lacked trusted local-minute
input. Those source gaps are implemented at `487ffa03e2cc95d84a8eafa5a51016fe413cdce7`;
the detailed 2026-10-19 evidence is linked above. This remains host and
compile-only validation, not physical target acceptance. Full P0 remains
PARTIAL. Physical GS-40/117/121 and phone acceptance are NOT_RUN. GS-104
R01–R09 remains on hold. No hardware was accessed. Untracked
PWA/Android/managed-component/physical evidence and other worktrees remain
untouched.

Evidence and exact current results:
[GS178_SOFTWARE_VERTICAL_20261018.md](../exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md).
Jira comments: GS-178 #11397; GS-59 #11398; GS-40 #11399; GS-148 #11400;
GS-177 #11401; GS-116 #11402; GS-130 #11403.

# R1 Current Work State

## GS-177 canonical integration — 2026-10-18

The owner authorized integrating `feature/gs-177-caregiver-android` into this
canonical branch and safely retiring that branch after its deployment/build
dependencies move. The canonical Android source that was untracked before the
merge was preserved in commit `6cfba0dfad57a6279101591e16287dbd39c90652`;
the Connected Lite app is now the compiled Android entry point. Canonical-only
call/FCM classes remain under `code/parivar_saathi_android_app/prototype/` and
are not activated or qualified. The isolated Hub simulator branch and worktree
were excluded.

Canonical integration commit `4b8a1de569d33c2bff2366d9d9eeab9ea36720f2`
and its Android workflow are pushed. Focused local results: Connected Lite
API/storage/auth 13/13; caregiver runtime 7/7; host event/routine scenarios
3/3; voice-prototype contracts 19/19; component-gate framework 50/50;
dashboard registration 6/6; feature coverage 22/22; traceability 213 features
/ 249 source modules / 25 physical cases. Host `make lab-build` passed.
`parivar_saathi_android_app/verify.sh` passed 19/19 and XML structure checks.
GitHub Actions run [39143635257](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39143635257)
passed: browser regression 3/3 and catalogue assertions 92/92; Connected Lite
API 13/13; Android stage 6/6 (unit test, APK assemble, shared PWA bundle,
branding/origin checks and signature verification); voice prototype 19/19.
APK artifact ID `12142667693`, SHA-256
`fb79da133083a5ed761be32843a69035045b8682fd6da8e08c00c512fc6c8551`, package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`. Signing is
runner-generated debug-only; prior APK may need uninstalling. Local browser
validation was skipped because no browser binary was installed; CI browser
tests passed. This was not a release-gate run.

The Render Free service has not been migrated: no Render CLI/MCP or API
credential is available. `healthz` and `readyz` return 200, readiness reports
the database reachable, and anonymous `/lite/v1/me` returns 403. The last
recorded deployment revision is `47e8faaff093184d0bcbf1bb95dc9e79aba03090`;
the service still depends on the GS-177 source branch. `render.yaml` now points
to canonical, but the service linkage was not changed and no staging deploy was
attempted. Keep the remote GS-177 branch (and its worktree containing ignored
APK build artifacts) until Render is migrated. The GS-68 archive branch was
verified as an ancestor with zero unique commits and deleted locally/remotely;
its remote absence was verified, and no archive worktree existed. Hub simulator
commit `0ff9e3ba` remains untouched.
Physical phone, real Hub CloudSync and voice-call acceptance remain NOT_RUN.

## GS-68 / GS-172 stack-correction diagnostic update — 2026-10-17

The first spare session on the previously installed `855b586d...` image
captured an ESP-IDF main-task stack-overflow panic and no OBSERVE response. A
host-only build then used commit `f7278f9746e756214502ac270dc8db43e6ab0489`,
moving two bounded command buffers out of `app_main`'s stack. The 278,480-byte
TEST_ONLY app (`9558665c928ea2ee2910b9297cba9feacebd00730410c1094137d57ff49b8c04`)
was installed once at measured OTA0 offset `0x20000`; esptool v5.4.0 exited 0
and reported `Hash of data verified.` The only written sector window was
`0x20000..0x64000`; the command then performed its explicitly requested hard
reset via RTS. A restricted 1 MiB baseline capture covers that candidate
sector window. No NVS or other partition was written.

One subsequent bounded native USB session matched the spare PnP parent receipt
and opened exclusively once. It captured two startup lines, followed by a
truncated READY frame ending mid-profile digest. No exact image identity or
OBSERVE response was established, so no malformed/oversized/sequential commands
or TEST_ONLY PSA/signed-time operations were sent. This capture does not show a
complete panic and does not prove whether the serial open reset the device or
whether incomplete bytes arose from USB/target output interruption. Private
bundle SHA-256 `1eb39f84351907b9097f841dd7be9f9a4302bba2923a3d1dd3f0b39e8e9ea84c`;
console digest `bc3a6ed7dab78b3e76068c478ba00639059f4222c1f1ace72656f871e68104be`.

The isolated profile now sets `CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192`, leaving
the product defaults unchanged. This is the last targeted stack correction for
this execution. It is unbuilt and not installed yet. Run the focused GS-68
profile/runner tests, source-bound ESP-IDF 6.0.3 non-flashing build, validate
the new candidate, then use at most one bounded app-only OTA0 installation and
one final observation session if current identity/recovery gates still pass.
Stop after any further incomplete READY, panic, response timeout or PnP event.
Official GS-68/GS-40 physical acceptance and silicon DS/mTLS remain **NOT_RUN**.

## GS-68 / GS-172 authorized spare USB diagnostic execution — 2026-10-17 update

The first owner-authorized Windows-native session was executed after commit
`2b5a7388421c59abea23bc444b2f91b037117c72` and clean-source candidate-binding
validation. Immediate Windows PnP-parent verification matched the restricted
spare receipt; the COM interface was opened exclusively once in
`controlled_reset_tolerant` mode. The provider logged reset tolerance, not
reset safety, recorded process ownership as UNKNOWN before the atomic exclusive
open, and recorded the Windows driver's DTR/RTS state as unobservable.

This session inherited the previously verified installation identity because
it did not receive a new READY frame. Its private capture contains an ESP-IDF
`stack overflow in task main` panic signature and no fresh nonce-correlated
OBSERVE response. The auxiliary OBSERVE is **FAIL**; malformed, oversized,
sequential and all TEST_ONLY PSA-RNG/signed-time physical cases are **NOT_RUN**.
No reset was confirmed; reset versus buffered/replayed startup bytes remains
unknown. No further port opening, flash, NVS update or firmware build was done
at this point. Private result bundle SHA-256:
`d241a196e3d5abd50691bb2c61f7f9e10d3c5c7ed15d01e82489de0553feb8d8`; raw
console record digest:
`092cf5ea5395cd68723cd743382ceb923a5f5ed071695ccf1676803b95752c56`.

Follow-up software correction: startup observer classifies ESP-IDF panic/abort
signatures as a fail-fast condition and sends no command after one is seen.
The isolated TEST_ONLY diagnostic moves its line-framer state and command
buffer out of ESP-IDF's 3584-byte `main` task stack. This addresses a plausible
stack-pressure cause without claiming the capture proves where/when the panic
occurred. Run affected tests and a non-flashing source-bound S3 build. The
existing installed image is unchanged; any replacement installation must be
re-evaluated against the owner-authorized recovery/install scope. Keep official
GS-68 and GS-40 physical acceptance **NOT_RUN**.

```text
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-172 current execution instruction and GS-68 auxiliary diagnostic contract
DECISION_IDS=NONE
TASK_SCOPE=Spare-only GS-68 USB observer and isolated TEST_ONLY startup-stack correction
OUT_OF_SCOPE=Production Hub composition, C8/C3 fixtures, security eFuses, credentials, endpoints, and official GS-68/GS-40 acceptance
```

## GS-68 / GS-172 authorized spare USB retest — 2026-10-17

Started from canonical `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, HEAD `351683ab76ffeba0d7678a281ac94d5ca11f4caf`;
local and origin matched and context preflight PASS. Pre-existing untracked PWA,
Android, managed-component, GS-114/C8 and GS-40 evidence remain untouched. No
other worktree/process was interrupted.

Current host-only Windows PnP inspection found COM10 present, VID/PID
303a:1001, and verified its parent-device serial against the private spare
identity receipt; that parent identity is distinct from the protected C8
inventory. The COM interface's own PnP serial differs from the USB parent
serial; parent-chain verification resolved this without opening COM10. Windows
interoperability works (Windows 10.0.19045; PowerShell 5.1; Windows Python
3.12). No serial port has yet been opened in this task.

The owner has now authorized one controlled reset-tolerant open and diagnostic
session on the designated spare, including TEST_ONLY PSA RNG/signed-time tests.
This does not prove reset-safe opening. The implementation adds a spare-ID-only
opening mode and retains default fail-closed reset-safe behavior for all other
fixtures. It logs reset tolerance separately from observed reset evidence.
`execute_usb_if_ready()` can proceed without a new READY only when the prior
installed-image receipt and its cited evidence files validate, then requires a
fresh nonce-correlated OBSERVE. A new READY, if present, is directly checked
against the ESP-IDF image-validation digest; evidence states whether identity
was reobserved or inherited. The exact candidate binary is not present in the
current build directory; do not substitute the different `c0fb...` artifact.

Software changes in `gs68_capture.py`, `gs68_aux_diagnostic.py` and
`test_gs68_aux_runners.py` pass focused validation: auxiliary runner suite
40/40; GS-130 protocol assertions 1,738; GS-130 HIL runner regression 115/115;
feature traceability 208 features, 220 modules, 24 physical cases, 22/22
mappings and 22/22 tests; Python compile and `git diff --check` PASS. Expected
physical runner paths remained NOT_RUN/BLOCKED and opened no port. No firmware
build is needed. The private application install
and READY receipts remain the prior image evidence; full digest
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`, runtime
digest `d3d03609024b2b1ecf269150516bbfc08acd26f7caf9b220ab7f6a925b67e0b5`,
source `cfc89a8e7bd6009eddde5790814e557357d8a032`, profile
`7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72`.

Physical procedure amendment is recorded in
[`GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md`](../exec-plans/evidence/GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md)
v1.2. Next action after the software gates: commit/push the host-only observer
correction, validate the inherited image/installation receipt against the clean
committed source, then perform exactly one bounded Windows-native session
using current PnP-parent matching and exclusive COM open. Run the four USB
command cases; only if all pass, continue with the in-memory TEST_ONLY signer
and target PSA RNG/signed-time cases. Keep raw captures/private identifiers in
mode-restricted evidence outside Git/Jira. Official GS-68/GS-40 physical
acceptance, production DS signing and mTLS remain NOT_RUN.

## GS-68 / GS-172 Windows USB serial provider — 2026-10-17

Task classification: `TEST_INFRA_ONLY`; no product semantics changed. Started
from canonical `feature/r1-commercial-baseline` HEAD
`0deb657242bc0fec517d9554f49d09b2cf0f427a`; fetch confirmed local/origin equal,
context preflight PASS, and no competing source writer was observed. Existing
untracked PWA, Android, ESP-IDF managed components, GS-114/C8, GS-40 and other
evidence remain preserved and unstaged. No other worktree was accessed.

Implemented a Windows provider in `code/tools/hil/gs68_capture.py`: present
PnP COM mapping via bounded PowerShell enumeration, VID/PID/instance/serial and
driver-version extraction, immediate pre-open identity recheck, single native
Win32 exclusive open, bounded synchronous read/write, flow-control disablement,
no reconnect/buffer clearing, PnP presence polling and no explicit DTR/RTS
calls. The native provider returns owner PID as UNKNOWN; share-mode-zero
`CreateFileW` is its atomic exclusive-access check. It fails closed without an
external reset-safe policy bound to the active PnP identity/driver version.
No such policy is qualified. Windows COM handle opening cannot be atomically
bound to the preceding PnP instance query, and Windows/driver DTR/RTS activity
is not observable by this provider. Thus the software implementation is
mock-validated, not yet Windows-runtime qualified or reset-safe qualified.

Focused tests pass: `PYTHONPATH=tools/hil python3 -m unittest
test_gs68_aux_runners -v` (34/34 PASS). Registered
`make gs130-hil-runner-test` passed: 1,738 protocol assertions, 109 Python
runner tests, with physical cases correctly NOT_RUN/BLOCKED and no hardware
port opened. `make feature-coverage-test` passed: 208 features, 220 modules,
24 physical cases and 22/22 mapping tests. Python compile and `git diff --check`
passed. No firmware build, COM10 access, reset, flash, or other device action
occurred. The installed TEST_ONLY application remains unchanged; no new image
is necessary for a host-side observer update.

Reset-safe physical observation is **BLOCKED**. Microsoft documents inherited
serial DCB settings during `CreateFile`; ESP-IDF 6.0.3 documents USB
Serial/JTAG buffering/flush behavior and automatic download-mode capability.
Mock evidence cannot establish active Windows driver behavior. Before another
physical open, require a separately authorized observation with exact Windows
build/driver/PnP receipt, USB protocol capture of CDC
`SET_CONTROL_LINE_STATE` (USBPcap/Wireshark or hardware analyzer), Windows
USB/driver event trace, visible reset/BOOT observation, and target
boot-generation/uptime correlation. Current installed image lacks boot
generation/uptime. Duplicate startup output alone remains ambiguous replay vs
new boot. The retest plan is
[`GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md`](../exec-plans/evidence/GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md)
(content revision v1.1).

GS-68/GS-40 official physical qualification remains **NOT_RUN**. The
TEST_ONLY image is unchanged and remains installed; no new installation or
physical action is authorized by this software-only task. Next step: obtain a
reviewed reset-safe policy/evidence for the precise Windows USB Serial/JTAG
driver, then separately authorize the fixture-specific one-session USB
observation. No production credentials/endpoints, DS signing, signed-time NVS
write or hardware security setting is in scope.

## GS-172 / GS-68 spare-S3 conditional installation — 2026-10-17

Resumed on canonical `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, at `c896eabf982d787e0f83147b599388862a0f8397`;
local and origin matched, context preflight PASS, tracked state clean. Existing
untracked PWA, Android, managed-component, C8/GS-114 and GS-40 evidence was
preserved. No other worktree was touched.

Owner-authorized spare identity was reverified via the restricted USB receipt;
COM10 was present/OK and BUSID 3-1 remained Windows-side Shared. No C8/C3 was
accessed. The current no-reset security query again observed Secure Boot and
Flash Encryption disabled. The measured partition table and OTA metadata were
reread and hash-matched; OTA0 remained selected at `0x20000`. The private
1 MiB OTA0 recovery capture and manifest were rehashed, and the recovery image
format/one-slot restore syntax were checked offline. Restore remains
unexercised.

Installed the exact existing TEST_ONLY image only at OTA0: 278,944 bytes,
SHA-256 `855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`,
source `cfc89a8e7bd6009eddde5790814e557357d8a032`; esptool v5.4.0 returned
success and `Hash of data verified`, then performed one hard reset to boot.
No bootloader, partition table, OTA metadata, NVS, OTA1, journal, eFuse,
credential, endpoint or security setting was changed. First target READY
matched source/profile/version/chip/capacity and spare identity. Its runtime
hash `d3d03609024b2b1ecf269150516bbfc08acd26f7caf9b220ab7f6a925b67e0b5`
matched the candidate's valid image-info validation hash; this is the correct
ESP-IDF runtime measurement and differs from full artifact SHA-256.

Bounded USB command verification is **BLOCKED/INCOMPLETE**. One harmless
fragmented OBSERVE frame was sent, but a boot-log line preceded any correlated
response. A later observer open without input received the same byte-identical
startup transcript/READY again; this could be output replay or a reset on COM
open, and cannot safely be distinguished. No more device I/O occurred. No
malformed/oversized/sequential test was completed. Silicon PSA RNG/signed-time,
DS signing, mTLS, and official GS-68/GS-40 physical qualification remain
NOT_RUN. Do not reopen, reset, reflash or provision the spare at this checkpoint.
The next action is software-only: fix frame draining and runtime digest
comparison in the auxiliary observer, then propose a reviewed reset-safe
observation plan before additional board access. Exact redacted results and
private receipt hashes are in
[`GS68_SPARE_S3_AUX_DIAGNOSTIC_20261017.md`](../exec-plans/evidence/GS68_SPARE_S3_AUX_DIAGNOSTIC_20261017.md).

The redacted evidence commit `a0be5b9651092e2db600107091012efa7a07a415` was
pushed normally, and remote HEAD matched at that checkpoint. Jira updates: GS-172 comment `11345`; GS-68 comment
`11346`; both remain In Progress. The commit staged only the evidence and work
state files; existing untracked assets/evidence remain untouched.

## GS-172 / GS-68 software-only USB observer correction — 2026-10-17

Starting canonical HEAD was `dece06e8d06ba140f51362bd118fc3d5c28eb687` on
`feature/r1-commercial-baseline`, equal to origin; context preflight PASS. The
dedicated S3 remains installed with the TEST_ONLY image. This task performed
no hardware/serial access, reset, flash, erase, eFuse/security change, production
service access, or C8/C3 operation.

Investigation of the preserved private captures found an invalid digest
comparison in the first observer: READY's ESP image-validation digest was
compared against the complete artifact SHA-256. The candidate's validated
appended hash is `d3d03609024b2b1ecf269150516bbfc08acd26f7caf9b220ab7f6a925b67e0b5`;
the complete binary SHA-256 remains
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`. A later
observer retained 25 normal ESP-IDF lines plus READY, then saw another READY
before command execution and stopped. The earlier physical-session report
records a fragmented OBSERVE attempt without a correlated result, but the
surviving raw receipts do not fully attribute that write to either preserved
capture. The two captured 26-line streams are byte-identical (decoded transcript
SHA-256 `3dbbdc84265cf9045c2f269c5114cfdb4f6bb30ddaffe5b9d1f67375131603be`).
Available evidence does not
distinguish USB-driver replay/buffering from reset-on-open: the installed READY
does not contain boot generation or uptime, and host USB arrival/control-line
events were not correlated. Do not label the S3 as reset based on repeated
startup output alone.

Software changes add bounded startup draining and mixed console/frame sync,
raw line retention with monotonic timestamps/order, strict case/nonce/operation
correlation, timeout/malformed separation, duplicate READY/startup-prefix stop
conditions, ESP32-S3 image/footer validation and correct runtime digest
comparison, source-provenance allowlisting for only host observer/build tooling,
firmware-matched malformed/oversized response handling, and a mock-validated
Windows-native transport that rejects unverified PnP identity, COM substitution,
busy port, or a driver lacking a no-reset open guarantee. The builder emits both
artifact and image-validation digests. Firmware behavior and the installed
image are unchanged.

Validation: `PYTHONPATH=tools/hil python3 -m unittest test_gs68_aux_runners -v`
PASS, 26/26 tests; `make gs130-hil-runner-test` PASS, 1,738 C++ protocol
assertions and 101 Python runner tests; `make feature-coverage-test` PASS,
208 features / 220 modules / 24 physical cases with 22/22 mapping tests;
`py_compile` PASS for the changed Python files; `git diff --check` PASS.
No ESP-IDF rebuild was needed because no firmware code/configuration changed.
New observer plan:
[`GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md`](../exec-plans/evidence/GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md).
The next physical observation is BLOCKED until a Windows serial provider proves
reset-safe open behavior; any physical access additionally needs separate
explicit authorization for that exact plan. Official GS-68 and GS-40 physical
acceptance remain NOT_RUN.

Implementation commit `664e79c7ea7129746ec13a364ff01419742c830e` was pushed
normally to the canonical branch after reviewing only the ten intended staged
paths. Source-bound candidate validation against the current branch and local
ignored artifact passed with zero errors; full binary and runtime image hashes
remain as above. GS-68 comment `11351` and GS-172 comment `11350` record this
software result; both tickets remain In Progress. The final documentation
checkpoint, remote HEAD, and clean tracked state are recorded by the delivery
commit for this handoff. Existing untracked PWA, Android, managed-components,
GS-114/C8 and GS-40 evidence remained unstaged and untouched; no other worktree
was modified.

## GS-172 / GS-68 spare-S3 installation preflight — 2026-10-17

Resumed at canonical HEAD `c4bc525e1fea8555ab30affc5b9e9926703c7f8e` on
`feature/r1-commercial-baseline`; local, tracking and remote heads matched.
Tracked state was clean. Existing untracked PWA, Android, managed-component,
C8/GS-114 and GS-40 evidence was preserved. Context preflight was PASS. No
canonical writer was found; a prior process in the separate GS-177 worktree was
left untouched.

The ignored TEST_ONLY S3 candidate was found and its app digest reverified:
`c0fb82c69fe030f8b4358b7783e7c537156dfdb361b4df1a620831210d1bef65` (473,312
bytes). Profile digest is
`7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72` and
effective sdkconfig digest is
`ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a`; USB
Serial/JTAG is primary. Current `code/` tree equals the build source tree, but
the formal runner requires exact full-HEAD equality and the candidate embeds
source `a5d2806b40023d0c42a90d082187398416fb956c`, not current HEAD `c4bc525...`.

**Physical disposition is NO-GO.** The spare remains unassigned in the fixture
manifest; its historical BUSID/COM10/ttyACM0 and baseline-image digest were
not rechecked. No independently hash-verified baseline restore image was
found among discovered named S3 app artifacts, and installed partition-table
compatibility is unknown. The formal runner executes signed `RUN_CASE` cases,
not the auxiliary USB command/signed-time diagnostic; its time-fixture label
also collides with catalogue GS68-PHY-003 (certificate validation). Valid
time proof writes NVS namespace `gs68time`. No device/port was accessed and no
physical test was run.

Detailed source/image binding, stop/recovery procedure, P1–P3 plan, prepared
owner authorization packet, and all outstanding blockers are in
[`GS68_SPARE_S3_INSTALL_PREFLIGHT_20261017.md`](../exec-plans/evidence/GS68_SPARE_S3_INSTALL_PREFLIGHT_20261017.md).
Previously reported software validation was not rerun. Next action is owner
approval for read-only identity observation only; after that verify C8
exclusion and recovery/partition plan, resolve runner binding/case mapping,
then prepare a new digest-bound installation approval. Do not flash based on
this preflight. The evidence/checklist update was committed as
`1b37f40ddb21e154697cccd9709a798215b8b538` and pushed normally. Dated Jira
comments record this new NO-GO decision without workflow transitions: GS-172
`11328` and GS-68 `11329`. Final remote verification follows this handoff
update.

## GS-172 / GS-68 USB diagnostic command-console correction — 2026-10-17

Authority: GS-172 comment 11323 and GS-68 comment 11324. Context preflight
passed. Canonical worktree and branch are
`/home/udaybhan/projects/Ghar_sajag_r1` and
`feature/r1-commercial-baseline`; before edits, local and origin both matched
`3cb4146603594313c163d9b80483aa7c2fab88a1`. No writer was found in the
canonical worktree. During final delivery, a backend validation process was
observed in the separate `Ghar_sajag_gs177` worktree on
`feature/gs-177-caregiver-android`; it and its uncommitted files were left
untouched. The canonical remote still pointed to the expected base during the
check. Existing untracked PWA, managed-components and C8/GS-114/GS-40 evidence
remain untouched and unstaged.

Verified the previous candidate's effective console was UART0 primary with
USB Serial/JTAG secondary. ESP-IDF 6.0.3 documents that secondary input is not
available to stdin and its simplified USB VFS reads are nonblocking. The
isolated GS-68 diagnostic profile now makes USB Serial/JTAG primary, disables
UART0 and the secondary USB console, initializes the driver-backed blocking
VFS, and uses an incremental 1024-byte command framer. The command loop
survives delayed/partial input, malformed and oversized lines, transient EOF,
and sequential commands. Production sdkconfig defaults and product composition
were not changed; existing nonce binding, RSA-3072/SHA-256 proof validation,
fail-closed TLS/identity, and no-fake-verifier guards remain intact.

Validation: host protocol/framing `1,736` assertions PASS; provider tests 5
suites PASS; mTLS adapter 9/9; backend security 14/14; GS-40 identity/time/
caregiver 4/4; GS-168 issuer 10/10; NodeHealth 5/5; GS-130 runner suite 72/72.
ESP-IDF 6.0.3 non-flashing build PASS: 473,312 bytes, image SHA-256
`c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65`; source
commit `a5d2806b40023d0c42a90d082187398416fb956c`; profile SHA-256
`7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72`;
effective sdkconfig SHA-256
`ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a`.
The old build-only candidate `e8e0a6236817f857346aced735f94f412245c693733710f749d56a55b248ef34`
is superseded for future install; user-reported installed baseline
`c905af73419c84af7a1d986dada3724da7e654b4d7eaa0235bd06e515902f8ef` remains
unchanged. The /tmp tmpfs build attempt failed for lack of space; the preserved
build was resumed successfully under ignored `code/build/validation_targets`
with compiler TMPDIR on the root filesystem.

No board, serial/USB interface, power, flash, reset, provisioning, DS/HMAC,
eFuse, Secure Boot, Flash Encryption, production credential or endpoint was
accessed. The new image is ready for owner review and separately authorized
spare-S3 installation only. Installed-image match, USB console behavior on
silicon, PSA RNG, RSA verification, DS signing, mTLS, GS-68 PHY, and GS-40 PHY
remain NOT_RUN. Exact post-authorization harmless console smoke procedure and
the full receipt are in
[`GS68_USB_COMMAND_CONSOLE_20261017.md`](../exec-plans/evidence/GS68_USB_COMMAND_CONSOLE_20261017.md).
Source-fix commits are `b545fb7e71f1ecdcef33bef753623fc58a8debe6` and
`a5d2806b40023d0c42a90d082187398416fb956c`; the evidence packet was committed
as `f23bdfe83cadf490285fd547ab97e4d9ebc3ebe0` and pushed normally. The remote
read-back matched that commit. Dated Jira comments were added without workflow
changes: GS-172 `11326` and GS-68 `11327`. This work-state handoff records those
receipts; the final handoff commit is pushed and its local/remote equality was
verified at delivery. No physical operations or production-security activation
were authorized.

## GS-68 D05/D12/D06 provider seams and GS-40 integration — 2026-10-17

This is the latest canonical continuation of the GS-40/68/109/148 handoff.
The task resumed on the sole canonical worktree
`/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, at `cea35806b44ece7442a286606a7ec23bfe9ace87`;
the branch was fetched and equal to origin before edits. Context preflight
passed (`2026-10-13.001`). The previously untracked PWA BatteryAnalytics tree,
ESP-IDF managed components, GS-114 captures and GS-40 UART evidence remain
unstaged and preserved. No other worktree or branch was changed.

Added `cloud_trust_provider` contracts and TEST_ONLY host fixtures. They model
the permanent Hub identity, credential/certificate generation and cloud-only
RSA-3072 DS signer context, atomic current Home/epoch/revocation snapshot,
credential quarantine/revocation, and an authenticated-time startup/recovery
state machine with nonce-bound proof verification, freshness, durable boot
generation, monotonic rollback latching and policy-configured durable time-floor
checkpoints. Unconfigured freshness or floor-checkpoint thresholds remain
fail-closed. The production S3 owner still instantiates
`UnprovisionedS3CloudTrust`; no fake credential, time authority, trusted SNTP,
or production endpoint was introduced. The HTTPS channel requires authenticated
time/Hub/credential metadata, passes only the DS context and client certificate,
keeps TLS 1.2 and server certificate validation, has no bearer fallback, and
sets ESP system time only from the authenticated provider snapshot. Existing
backend mTLS verifier and NodeHealth model remain unchanged. The bounded GS-40
NodeHealth CloudSync path and durable EventKey/ACK/retirement path are unchanged.

Executed: `make cloudsync-security-ut` PASS (mTLS adapter 9/9; provider D05,
D12, D06 and GS-40 integration suites PASS; backend security 14/14; NodeHealth
API/model 5/5); `make cpp-test` PASS (1,509 checks); `make
p2d-cloud-contract-host-test` PASS (15 invalid receipt modes, pending bound
200, batch 16, retry 64, two persistence cuts); `make
cloudsync-mtls-integration-test` PASS (1/1 local real-mTLS worker/API bridge,
two attempts); `make validation-framework-test` PASS (47/47);
`make feature-coverage-test` PASS (208 features, 220 modules, 24 physical
cases, 22/22 mapping checks); suite JSON parsing and `git diff --check` PASS.
The non-flashing ESP-IDF 6.0.3 S3 `GS_HIL_BUILD=OFF` production-profile build
passed with `PROJECT_VER=gs68-provider-20261017`: 2,168,128-byte app image in
the 4 MiB slot, SHA-256
`2052ba8d233b66bd753d5f6572c01acd4a4cd3daf6017dde70c27d628fde69b5`, sdkconfig
SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`.
The paired C3 app was reused unchanged at 937,536 bytes, SHA-256
`d94e011abd0e28b31cadb4dee2ff6451b0f5311c2783cdcbb2a631c03e86f765`. Build
directory: `code/build/validation_targets/gs68-provider-KOykpg`. The initial
configure with `IDF_COMPONENT_MANAGER=0` correctly failed because it hid the
pinned LittleFS dependency; rerunning with the existing ESP-IDF lockfile and
manager enabled completed. Before/after managed-component file hashes matched,
and `dependencies.lock` stayed unchanged. The IDF build printed one
non-fatal `unused variable 'retirement_ack_sent'` warning in the Hub adapter.
The firmware build and size check returned success; an initial post-build hash
command used the wrong sdkconfig path and was corrected by hashing the actual
sibling sdkconfig. No flash command was run.

The durable floor/high-water checkpoint and nonce-reuse tests were added during
this continuation and are included in the final provider/security result above.
No Hub journal migration or release aggregate was edited to mask existing
failures: required `product_status=PARTIAL` and the known Hub migration
`clean migration commits` failure remain. No PWA browser suite was rerun because
no backend/PWA interface changed; the prior GS-40 PWA 86/86 and backend/API
software evidence remains historical and separate from physical qualification.

Affected component aggregates were executed sequentially after the focused
tests. `make validation-hub` completed **FAIL / exit 2**: 47/49 stages PASS;
the two failures are the unchanged `migration` assertion `clean migration
commits` (exit 2, count 0) and required P0 `product_status=PARTIAL` (26/26
assertions and its Chromium check pass, physical `NOT_RUN`). Report:
`code/evidence/validation_framework/hub-1792205386802576887/report.json`.
`make validation-contract` completed **FAIL / exit 2**: 40/41 stages PASS;
the sole failure is that same P0 `PARTIAL` gate. Report:
`code/evidence/validation_framework/contract-1792206089239429376/report.json`.
No expectation was weakened and neither pre-existing failure was hidden.

Production blockers: D05 needs the approved per-Hub CA/issuer, chain/trust-root
and authenticated active Hub/Home/ownership-epoch/revocation registry source;
D12 needs approved factory issuance/custody and actual ESP32-S3 DS/eFuse key
provisioning plus isolated TEST_ONLY identity; D06 needs an approved signed-time
bootstrap authority/protocol and nonce source, verifier trust anchor, durable
target boot counter/floor store, response freshness and wear-bounded floor
checkpoint/validity thresholds. All production provider implementations remain
absent and commercial transmission stays disabled. Physical readiness additionally
needs exact identified S3/C3 fixtures and verified current-image/config/session,
owner-authorized safe observation/recovery plans, identity/time test fixtures,
isolated backend trust mapping, and for GS-40 TC05 a second enrolled Node or an
approved profile fixture. Physical cases remain NOT_RUN; no hardware action was
performed. The exact image hashes and non-flashing build metadata are recorded
in the dated evidence addenda. Source commit
`42f74034d5f1f5acd2c605ffee37f540da42ef7e` was pushed normally to the
canonical branch and matched GitHub at source-checkpoint verification. Jira
comments were added without workflow transitions: GS-68 `11286`, GS-109
`11287`, GS-40 `11288`; GS-148 was not updated because its backend/PWA
implementation was not changed. This documentation receipt records those
results. The next owner action is to approve/supply the production D05/D12
identity and authority provider, then approve the D06 proof, storage and timing
contract before a production adapter is instantiated; physical fixture and
case-specific authorization are a separate prerequisite.

## GS-40 S3 NodeHealth runtime composition — 2026-10-16

The canonical task resumed on `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, at verified checkpoint
`9d16556bbfe741bd4aa59c3df88a0ba0addca3c8`; local and fetched origin were equal
before editing and the tracked tree was clean. Existing untracked PWA,
managed-component, GS-114 and GS-40 UART evidence was preserved and excluded
from the change.

The S3 Hub owner now refreshes bounded NodeHealth snapshots from authenticated
HubRuntime current-session contacts every five seconds. A separate five-second
network worker uses the existing CloudSync authority wrapper and HTTPS
transport; it publishes at most four current states per pass, checks the
current Hub/Home/ownership epoch, retries with bounded backoff, and waits for
WAN association plus IP. It does not process journal events or alter EventKey,
durable-before-ACK, retry, replay or Node retirement. The installed policy
mapping accepts configured 300/910 and trusted legacy 60/190 and 120/310
profiles. Lease expiry is computed by HubRuntime without requiring another
packet. Checkpoint restore, session changes and revocation clear/stop ephemeral
publication. Hub security fault state is atomic for the network-side revocation
check; registry/session tables remain owner-only.

Commercial sending remains fail-closed: the S3 permanent identity/current
ownership provider, D06 trusted-time source and TLS identity provider are
explicit unprovisioned stubs. The provider seam requires an immutable,
thread-safe current authority snapshot; untrusted SNTP, MAC-derived identity,
caller headers and generated production credentials are not used. No live
credential, backend service, board, serial port, eFuse, flash or reset was
accessed. This completes software runtime composition with TEST_ONLY host
fixtures, not commercial activation.

Validation: `make -C code cpp-test` PASS (1,509 checks); CloudSync adapter 8/8,
mTLS 13/13 and backend NodeHealth API/model 5/5 PASS; P2D durable EventKey and
receipt contract PASS (15 invalid receipt modes, pending bound 200, batch 16,
retry 64 and two persistence cuts); `make -C code app-test` PASS (24/24),
backend Python suite 523 PASS and caregiver desktop/mobile browser suite 86/86
PASS. `make -C code validation-hub` aggregate FAILs on the existing
`clean migration commits` assertion and required P0 `product_status=PARTIAL`.
Contract, backend and PWA aggregates also report the required P0
`product_status=PARTIAL` (26/26 assertions and its Chromium scenario passed);
the PWA browser suite itself passed 86/86. Final frozen-source aggregate
reports (`source_unchanged=true`) are
`code/evidence/validation_framework/hub-1792177423393802158/report.json` and
`code/evidence/validation_framework/contract-1792177035924980667/report.json`;
both used source fingerprint
`478ca9b8d83835ebf5ebe4a9d3c500e1fc2cd54946573ba3bc770e9bccd9822c`. The
first Hub aggregate attempt was discarded because its source changed during
execution and was rerun with tracked content frozen. No release campaign was
run. The
ESP-IDF 6.0.3 non-flashing S3 production-profile build passed with
`GS_HIL_BUILD=OFF`: 2,166,688 bytes in a 4 MiB app slot, image SHA-256
`e39dc13190b8f23d95a82f972ce9a896ce5c9f87a1ea33565ab31ff07e88e1d5`, sdkconfig
SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`.
The initial target build exposed an incorrect `CloudAuthoritySource` wrapper
argument; it was fixed and the subsequent S3 build passed. After adding the
atomic terminal-fault read, `make -C code cpp-test` and the S3 target build
passed again after the final bounded-map and revocation test updates. Feature
coverage integrity also passes: 208 features, 218 source modules, 24 physical
cases and 22 mapping tests. These results do not qualify credentials, time,
radio or board behavior.

The validated implementation and handoff changes are committed locally as
`65e6bb83b636e803ec647bbef40a03ce74cedfbe`. The validation campaign ran against
that code change on the working tree based on checkpoint `9d16556bbfe741bd4aa59c3df88a0ba0addca3c8`; its exact frozen-source fingerprint is
recorded above and in the traceability row. The origin branch was still at the
starting checkpoint when this implementation commit was created. The final
delivery comment records the documentation-receipt commit and verified remote
HEAD after the normal push.

Remaining prerequisites: approved D05/D12 permanent Hub identity issuance,
protected key custody, verifier, current Home/ownership-epoch and revocation
source; approved D06 trusted Hub time; deployment-bound software verification
using those providers; then exact physical fixture, board/image/config/session
and pending-EventKey provenance plus a verified non-resetting safe observer and
separate per-case authorization. PHY-GS40-01..06 remain NOT_RUN. P0 remains
PARTIAL and the Hub journal migration gate remains FAIL. Latest source commit
and actual origin HEAD are recorded in the dated Jira follow-up after delivery.

## GS-40 NodeHealth CloudSync evidence-contract increment — 2026-10-16

The canonical source checkpoint before this increment was
`ad6df017a7f7bf586a84beb5b54cea2ad74d5962` on
`feature/r1-commercial-baseline`, with `origin` at the same SHA. The focused
GS-40 evidence-contract change is source commit
`a110228b22ff35d53e3ab709364c0ce21977cd92`. The implementation and architecture
evidence follow-up records the resulting delivery checkpoint in its dated GS-40
Jira comment. The separate, active GS-68 worktree
`/home/udaybhan/projects/Ghar_sajag_r1_cloudsync_mtls` was not modified or
merged; existing untracked assets and BAT-C8/GS-114/GS-40 evidence remain
preserved.

The only code change extends the existing GS-40 pure observation validator to
schema v2. It now checks matching Hub/Home/ownership-epoch authority across
Hub/backend/PWA, Hub-owned trusted Node profile, authenticated NodeHealth or
event contact kind, Hub contact receive time carried separately from backend
receive and PWA snapshot time, and fail-closed stale/untrusted source handling.
This is `TEST_INFRA_ONLY`: no Node/Hub liveness algorithm, CloudSync endpoint,
credential, verifier, backend schema/API, event/EventKey/ACK path or PWA product
behavior changed. GS-148 architecture evidence now records the additive bounded
status contract under GS-109/GS-68/GS-148 ownership. Configurable sensor-offline
notification behavior is not found in current Jira/code; any alert is separate
product scope and needs a new linked requirement.

Focused validation at source commit `a110228b22ff35d53e3ab709364c0ce21977cd92`:

- Python compile: PASS.
- Six selected GS-40 adapter/source-audit/live-gate unit methods: PASS; 14
  observation states/subcases. No full mock/replay case campaign was rerun.
- `make feature-coverage-test`: PASS; 207 features, 216 modules, 24 physical
  cases; 22 mapping tests PASS.
- `git diff --check`: PASS.
- No Node/Hub/backend/PWA product component changed; their component gates were
  not rerun. No hardware, port, USB, power, stimulus or outage operation ran.
- All PHY-GS40-01..06 remain BLOCKED/NOT_RUN; no physical PASS. BAT-C8 results
  were not changed or repeated.

Production readiness is still blocked on GS-109 production Hub verifier/key
custody and D06 trusted-time decision; GS-68 additive status publication through
the existing CloudSync channel; GS-148 authenticated ingest, freshness read
model and caregiver PWA projection; and a verified safe observer plus current
board/image/config/session provenance. GS-40 remains In Progress. Next action is
owner delivery of those GS-109/GS-68/GS-148 contracts, then production source-to-
caregiver end-to-end tests before physical TC01–TC06.


## GS-68 second incremental CloudSync integration — 2026-10-16

The isolated integration candidate starts at canonical remote
`c0430b14bd0897de5d22f5ace073bf457302067c` and selectively integrates source
checkpoint `e740f99d094b4a0ef7397f0a506e8f089fb5d261` from
`feature/r1-gs68-gs109-mtls-feasibility`; prior integrated checkpoint:
`44838da836d3014e606cfe2ee57ad624ee417240`. GS-148 comment 11216 authorizes
this incremental software integration. The paired C3 read-only observer and
shared diagnostic protocol, TEST_ONLY backend readiness binding, runner tests,
registrations, traceability and qualification plan are integrated in the
existing candidate. Focused runner tests (16 C++ / 70 Python), backend self-test,
registration checks (2 component / 1 dashboard) and traceability (22) passed.
C3 and S3 non-flashing ESP-IDF 6.0.3 builds passed, source-bound to
implementation commit `ce6151fe1f387e867b1c6c17c0aa742550f3353a` (C3 948,112
bytes; S3 442,240 bytes). Reports and logs are in the dated integration
evidence and unique `/tmp` build directories. Physical cases remain NOT_RUN; commercial
CloudSync remains disabled. Existing P0 `PARTIAL` and Hub migration failures
remain blockers. See the dated canonical integration evidence for conflict
resolutions, test logs and build artifact metadata.

The older GS-68 S3 build evidence was verified and archived at
`/home/udaybhan/projects/_artifacts/Ghar_sajag/GS68/20261016_M9cHfJ/`; the old
path remains a compatibility symlink. The integration worktree is retained
with its pre-existing untracked/ignored artifacts. CloudSync development and
canonical/C8 worktrees remain untouched.
## GS-68 CloudSync physical-HIL readiness — 2026-10-16 (latest checkpoint)

Authority: GS-68 comment 11174. The isolated branch is
`feature/r1-gs68-gs109-mtls-feasibility`; implementation source commit is
`534701fe1ba873007468b6292a8229a92d87edb5`. The initial documentation
closeout `f51b094c9eeeb5188c61267490769206743c84aa` was pushed normally and
verified equal to origin. This final handoff receipt is a documentation-only
follow-up; the latest remote SHA is reverified and carried by Jira comments
11178/11179/11180. The canonical C8 worktree was not used. The pre-existing
untracked `code/firmware/hub/target/esp32s3/idf/managed_components/` was
preserved and excluded from staging.

The C3 diagnostic interface is implemented and default-off in normal product
builds. Its bounded case/nonce protocol supports only PING/OBSERVE, with
source/profile/image binding, boot/reset observations, link/outage and
retained-event counters, and authenticated Node/Hub EventKey/ACK trace. It has
no event injection, network/power toggle, or Node reset command; paired physical
stimulus needs an external fixture interface. The C3 profile compiled with ESP-IDF
6.0.3. No production sleep, ACK, retry, or security algorithm was changed.
The isolated TEST_ONLY backend readiness self-test passed with synthetic
credentials, local TLS 1.2 mTLS, RSA-3072 checks, certificate-to-Hub/Home/epoch
mapping, signed readiness, and duplicate-safe durable receipt retry. It did not
connect to a production endpoint or deploy a service. It does not implement the
unfinished GS-148 production durable Hub-commit API; P0 remains PARTIAL.

Build-only reports for the implementation source commit:

| Target | Result | Profile SHA-256 | sdkconfig SHA-256 | Image SHA-256 | Image bytes |
|---|---|---|---|---|---:|
| ESP32-S3 CloudSync diagnostic | BUILD_ONLY_PASS, ESP-IDF v6.0.3 | `00a8aefb20a6b67d34c6631128031d112ff091d3f255b21a7280db45a356b1d0` | `8e7b13e1989f4a102874370cb8d90ccb6716cb1df1f9316dbea0268e4916c6c8` | `f0eea28dfb50c6f6c896caa647d1da57ffc81bb7c8a3f8e5b5475d4964027e8a` | 442240 |
| ESP32-C3 read-only observer | BUILD_ONLY_PASS, ESP-IDF v6.0.3 | `81ddcd270c3a7b6a46e6b983df7daa6df28ab780acaf6c5e6ff1f5f6df7d24a2` | `6a932842c7478cc16289706cb8409d373033c27a0d48b66b66a227f2a3c07a06` | `25322db1a3a3052f6812630bf34578f2d1fe43a3558730fd908ec1ef4c607481` | 945568 |

Both reports bind source `534701fe1ba873007468b6292a8229a92d87edb5` and code-tree
OID `88f4fc0fcbb4890b942c5c55b48ef07ad9d89926`. S3 configuration selects the
ESP32-S3 diagnostic-only profile and TLS 1.2; GS HIL build/control,
commissioning, and C8 ACK-drop are disabled; the DS peripheral is selected but
unprovisioned. C3 enables only the observer in its separate ESP32-C3 profile;
GS HIL build/control and BAT-C8 physical wake are disabled. C3
`sdkconfig.defaults` and observer-overlay SHA-256 values are
`44bd471e07c2597873704c8427ef3e986c6a0b474cbabd5bab9e1a56925ad8fa` and
`0679dfa2078d757a3990f0766dea3c363c0a7e5ef5625d02994b13cf5575e664`.
S3 JSON report/log:
`/tmp/gs68_cloudsync_diag_9h385r_e/gs68_build_report.json` and `build.log`;
C3 JSON report/log: `/tmp/gs68_cloudsync_c3_bsyj9zbz/gs68_c3_build_report.json`
and `build.log`. The C3 profile selects `GS_GS68_NODE_OBSERVER=ON`, while
`GS_HIL_BUILD/CONTROL=OFF`. Compilation does not demonstrate a running image,
hardware RSA signing, target TLS, or physical qualification.

Validation on the isolated candidate:

- `make gs130-hil-runner-test`: PASS; C++ parser 16/16 and Python runner tests
  70/70. Safe dry-run: ten cases, `physical=NOT_RUN`, zero hardware actions.
- TEST_ONLY backend self-test: PASS; TLS 1.2, RSA-3072, signed readiness and
  duplicate-safe durable retry. `cloudsync-security-ut` 20/20,
  `cloudsync-security-sim-hil` 18/18, localhost mTLS integration 1/1.
- GS-116/GS-130 framework tests: 53/53; feature coverage mapping: 199 features,
  215 modules, 16 physical cases, 22 checks; physical catalogue: 100 cases.
- Component gates: Node 24 PASS / 1 FAIL (P0); Hub 44 PASS / 2 FAIL (migration
  and P0); Contract 38 PASS / 1 FAIL (P0); Backend 20 PASS / 1 FAIL (P0).
  The required P0 scenario executed 26 checks but retains
  `product_status=PARTIAL`, so its component stage remains FAIL. The Hub
  `clean migration commits` stage remains FAIL. Node/Hub/Contract component
  reports record HEAD `44838da836d3014e606cfe2ee57ad624ee417240` with
  `tracked_dirty=true`, before the final C3-only compile portability commits;
  Backend was run at source `534701fe1ba873007468b6292a8229a92d87edb5`. Neither
gate was weakened.
- Fast and full release gates were not executed; registration and release-stage
  selection were verified. `PHY-GS68-CLOUD-MTLS` remains release-blocking and
  `NOT_RUN`.

Compile/test defects resolved: C3 ESP-IDF `spi_flash` dependency, removal of an
S3-only PSRAM API on C3, portable `PRIu32` formatting, and a backend test setup
KeyError. No board, USB/serial, production network, secret, or hardware security
configuration was accessed. No flash, reset, eFuse/HMAC, Secure Boot, Flash
Encryption, production credential, or commercial CloudSync operation occurred.

The [S3-first qualification plan](GS68_S3_FIRST_PHYSICAL_QUALIFICATION_PLAN_20261016.md)
is **BLOCKED** and says `S3-FIRST-CONNECTION-APPROVAL-READY=NO`: the exact spare
board, revision, connector, power/adapter path, and stable USB identity have not
been identified or verified. S3-only identity observation, later S3 RSA/mTLS,
paired C3 cases, and GS-118/D15 OTA rollback have separate prerequisites.
D05/D12/D06/D16 remain unresolved; OTA remains separately gated by D15. This
entry records no product/security decision and does not increment
`CONTEXT_VERSION`.

## Prior GS-68 CloudSync integration — 2026-10-16

The isolated integration candidate was based on canonical remote
d3a17df57e0cf82b598edbc862c7ef0bc0ed14b6 and selectively ports the first-batch
validated committed CloudSync checkpoint
44838da836d3014e606cfe2ee57ad624ee417240. GS-148 comment 11177 authorizes
this software integration only. The first-batch integration commit was verified at
52fca1bc4166acb2765378e2e3e2a2fc95b750e1.
The separate CloudSync development branch and the active canonical/C8 worktree
remain untouched.

Integrated scope, conflict resolutions, focused rerun results, remaining
baseline failures, and delivery checkpoint are tracked in the dated
GS-68 CloudSync canonical integration evidence. The restricted S3 cloud
identity/mTLS seam remains separate from commissioning identity; the TEST_ONLY
diagnostic is opt-in and commercial CloudSync remains disabled. Physical cases
remain NOT_RUN. Production trust/key custody, trusted time, rollback, and
resource-limit decisions remain pending.


## GS-40 integration-readiness assessment — 2026-10-16 10:17 UTC

Resumed from GS-40 Jira comment 11175 on canonical
`feature/r1-commercial-baseline`, starting HEAD and verified remote HEAD
`09fcb9421fafb949bc14a2c295517942c00b1308`. The separate GS-109/GS-68
worktree remains unchanged. Existing untracked frontend assets, managed
components, and BAT-C8/GS-40 evidence were preserved.

Source review refined the backend finding: `FoundationService` already has
host-side per-Node health storage, policy, expiry and a device view; configured
300/910 and legacy 60/190, 120/310 profiles exist. This host model is not wired
to authenticated S3 CloudSync publication, and the caregiver API/PWA snapshot
still has no per-Node status/coverage projection. GS-109 owns the approved Hub
identity/verifier/ownership and trusted-time decisions; GS-148 owns production
CloudSync publication, backend ingest/read model, and PWA response integration.
No parallel transport, credential, or event storage was added.

The existing seven-case GS-40 runner accepts the normalized timing/status
bundle without changing the 300/910 liveness rule. Its schema does not validate
Hub principal/Home/ownership-epoch provenance; those fields and their
verification must be finalized by GS-109/GS-148. Its live mode remains
BLOCKED. No independent GS-40 product defect can be safely fixed until those
owner contracts exist; no code or tests were changed or rerun in this
assessment.

The evidence report now defines the minimum semantic publication/caregiver
contract, producer/consumer ownership, production integration checks, and exact
TC01–TC06 order. Existing C8-P1/P2 are reused only for their image-scoped
sleep/wake/ESP-NOW and real event durability subclaims; they do not satisfy
GS-40 cadence, offline, mixed-profile, or PWA cases. All physical cases remain
BLOCKED/NOT_RUN. Current bench is one C3 plus one S3; TC05 requires at least a
second trusted Node or approved fixture (three Nodes/fixture if three profiles
must run concurrently). A matched Hub image with the GS-148 path will be needed
after that path is implemented; any install needs separate exact approval.

No hardware, serial, USB, mock campaign, replay campaign, or code test was run.
This documentation-only change passed `git diff --check`; no component or
product test was applicable. The final commit and remote HEAD verification are
recorded in the dated GS-40 Jira follow-up. The next action is owner delivery
under GS-109/GS-148, not another independent GS-40 code change. Keep GS-40 In
Progress; do not claim physical PASS or Done.

## GS-40 production-path readiness follow-up — 2026-10-16 09:50 UTC

Resumed from GS-40 Jira comment 11170. The completed automation branch was
verified as a three-commit fast-forward from the starting canonical commit
`d738dc51a25e72de570a11fc39f0e26522ead3d8` to
`9453587383215e62628e436a20b10648a923410f` on
`feature/r1-commercial-baseline`. The existing GS-109/GS-68 branch/worktree at
`44838da836d3014e606cfe2ee57ad624ee417240` remains separate and untouched. The
canonical worktree contains preserved pre-existing untracked frontend assets,
managed components and GS-114/GS-40 hardware evidence; none were staged or
modified. At authoring, origin still pointed to the starting canonical commit;
the implementation delivery and its remote verification are recorded in the
resulting GS-40 Jira update.

**Production-path finding:** NodeHealth is decoded/authenticated at
`code/firmware/hub/target/esp32/hub_runtime_adapter.cpp` and enters volatile
HubRuntime lease/contact state. The active S3 entry point does not instantiate
CloudSync; existing CloudSync is durable-event synchronization only. There is
no production authenticated NodeHealth backend ingest/read-model projection or
caregiver PWA projection. The backend's local event API requires a caller-owned
Hub verifier and is not that provider. GS-109 D05/D12 owns trusted Hub identity
and verification; GS-148 owns the durable CloudSync/API integration. GS-40 did
not create a parallel credential, ingest route, event commit, or trust
contract. Source evidence and exact paths are in
`docs/exec-plans/evidence/GS40_REAL_TARGET_READINESS_20261016.md`.

**Reusable observation adapter:** `assess_observation_bundle()` validates
timestamped Node/Hub/backend/PWA snapshots, identity/session/contact
correlation, authenticated contact, configured 300/910 and legacy 60/190 and
120/310 boundaries, separate 190-second Hub/cloud freshness, stale PWA data,
and fail-closed unknown coverage. It does not connect to hardware or a network.
Synthetic valid bundles can only be `HOST_PASS`; untrusted/missing sources stay
unknown; mismatched claims are `FAIL`; a JSON claim of current hardware remains
`BLOCKED` because production provider attestation is not implemented. The
source-gated `live` runner remains no-I/O and BLOCKED.

**Focused validation:** Python syntax compilation passed. Four focused tests
passed, covering the production-source audit, adapter timing/connectivity
matrix (including 910 boundary and legacy 190/310), identity/contact mismatch,
live-provider refusal, and the existing live no-device gate. The command and
scope are recorded in the real-target evidence report. The completed mock and
replay campaigns were not repeated. No production Hub/backend/PWA end-to-end
test can pass against the current source because the path under test is absent;
the existing synthetic TC06 is not promoted to production evidence.

**Physical disposition:** No hardware operation was performed. All
PHY-GS40-01..06 remain BLOCKED/NOT_RUN, with no new physical PASS. Existing
BAT-C8 GS-114 physical evidence is unchanged. C3/S3 running image, effective
device JSON, live session and pending EventKey baselines remain unverified.
CH343 POWERON causality remains unproven; no serial interface was reopened.
Ordinary ESP-NOW Node liveness does not require opening C3 native USB. PHY-GS40-05
still requires a second identified C3 Node or approved fixture.

**Next action and ownership:** GS-109 and GS-148 must first provide the
approved authenticated Hub identity/publication path, backend projection and
caregiver PWA contract; then add real production cross-layer contract tests and
an approved non-resetting observer. Only after those prerequisites can a
single consolidated owner authorization stage PHY-GS40-01..06: one 30-minute
cadence observation, genuine authorized motion, a >910-second silent-Node
method, Node return/rejoin with before/after pending EventKeys, caregiver/API
evidence, and a second Node/qualified fixture for mixed profiles. Keep GS-40 In
Progress; software evidence does not meet its physical Done criteria.

## GS-40 automated qualification and physical handoff — 2026-10-16 08:34 UTC

Resumed from GS-40 Jira comments 11156, 11158 and 11162. The canonical R1
worktree was actively owned, so the approved isolated candidate is
`/tmp/ghar-sajag-gs40-qualification` on
`codex/gs40-qualification-20261016`. Implementation/evidence commit
`c32cf2fbe39011be5d6171e58243f666e5494626` was pushed to
`origin/codex/gs40-qualification-20261016`; `git ls-remote` matched that SHA.
The original handoff was pushed as `b943b061e410789ccd3127100a8e599b8fc03892`;
after reconciling Jira comments 11164–11165, the current candidate/remote
checkpoint is that same SHA and this evidence clarification is a follow-up
documentation commit.
The canonical `feature/r1-commercial-baseline` remains at
`d738dc51a25e72de570a11fc39f0e26522ead3d8`, matching its remote. No canonical
tracked files or pre-existing untracked assets/evidence were changed. This
follow-up does not modify product behavior.

Implemented the seven-case GS40 mock/replay/live framework and registered the
host stage. No firmware/product behavior was changed. The isolated test setup
installed the exact locked frontend dependencies with `npm ci`; generated
build/framework outputs and `frontend/node_modules` are ignored. At the
`c32cf2f` checkpoint the tracked worktree was clean.

**Physical diagnosis:** C3 light sleep gates the native USB Serial/JTAG clocks,
so the endpoint can disappear while the powered Node sleeps. This is observer
loss and does not prove Node outage. Historical S3 evidence SHA-256
`2ff1dab2e452883af97a3eec649f5d0b7da6984dc333b692d6c17af957cc2bc6` records
one 115200 receive-only CH343 open with zero transmitted bytes, followed by
`rst:0x1 (POWERON)` 257 ms into the captured receive interval. pySerial 3.5
opened the descriptor before applying DTR/RTS-low using `TIOCMBIC`; with
unverified CH343 reset wiring, line/driver/USB-IP initialization could explain
the reset. An independent or already-running power/reboot event also remains
possible. Because UART was not observed before open and USB/IP stayed Attached,
causation is unproven. No repeat open or hardware operation occurred here.
The capture has no current app/config/session/NodeHealth evidence. Hub-accepted
health is logged locally; source inspection found no production
Hub-to-backend NodeHealth view, so existing PWA models cannot prove live
caregiver coverage.

Jira comments 11164–11165 also preserve the existing GS-114 C8-P1/P2 physical
PASS: ten C3 timer sleep/wake cycles followed by authenticated Hub NodeHealth,
and one real AM312 motion EventKey durably admitted/ACKed/retired over ESP-NOW
while the native C3 USB console was unavailable. The recorded C3/S3 image hashes
are `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. These
image-scoped GS-114 results are reused only to disprove USB visibility as a
proxy for Node liveness; they do not satisfy GS-40's 300/910, mixed-profile or
caregiver criteria. They were not repeated.

**Automated evidence:** Mock: seven `HOST_PASS`, 26/26 assertions. Replay:
actual Jira 11158 source, six checks passed with historical provenance retained.
Live: seven `BLOCKED`, zero device actions. No physical PASS was generated.
The JSON and Markdown reports are under
`docs/hw/evidence/GS40_AUTOMATED_QUALIFICATION_20261016/runs/`; full diagnosis,
commands, counts and gate dispositions are in
`docs/exec-plans/evidence/GS40_AUTOMATED_QUALIFICATION_20261016.md`.

`make gs40-qualification-test` passed 12 tests; `make validation-tooling`
passed including the registered GS-40 stage; `make validation-framework-test`
passed 46; feature traceability passed 22 tests and the physical catalogue
passed 107 cases (`device_access=NONE`). Node and contract gates passed their
GS-40 1,320, health-config 17, security/storage/recovery and board-stack 10
stages. Backend Python 503, functional 92, and PWA browser 86 passed. Component
aggregates remain FAIL: mandatory P0 E2E has 26/26 assertions but
`product_status=PARTIAL` because GS-148's durable Hub-commit API is incomplete;
the Hub gate also reports the unchanged journal migration failure `clean
migration commits`. No release gate ran.

PHY-GS40-01 through PHY-GS40-06 remain BLOCKED; aggregate PHY-GS40 remains
NOT_RUN. The currently available one C3 plus one S3 can support single-Node
cases 01–04 and 06 only after exact identity/image/config/session, safe
timestamped observation and recovery are established. TC05 needs a second
valid C3 Node or approved qualified fixture. Liveness acceptance requires no
oscilloscope/current profiler, but does require authenticated cross-layer
timestamps. Installed firmware and effective device JSON remain unknown, so
installation is not yet established as necessary.

**Next action:** request one consolidated owner authorization naming the exact
non-resetting read-only observer and preflight for both board identities,
running images/effective configuration/session and pending EventKeys; if no
such observer exists, explicitly decide whether to accept one new CH343
receive-only open's reset risk and define permitted recovery. The same staged
authorization must name the TC02 real sensor stimulus, TC03 controlled
910-second silence method, TC04 return/rejoin procedure, caregiver/API
observation, and TC05 second Node or qualified fixture. Stop before any case if
image/config/session, identity-preserving recovery or the safe observation path
cannot be established. Earlier serial-open approval is consumed. Keep GS-40 In
Progress; Done criteria are unmet until all six real-target cases and caregiver
visibility pass on matched current images with timestamped evidence.

## GS-114 P9 physical-readiness handoff — 2026-10-16 04:43 UTC

Continued from GS-114 Jira comment 11150 in the canonical worktree
`/home/udaybhan/projects/Ghar_sajag_r1` on
`feature/r1-commercial-baseline`. Source code is committed at
`9b22c13689e819743e57e2a847a65f476b94331f`; origin was still
`f6a23ecd8419e987ef3eca578e061d3ec3185cf5` before this documentation delivery.
Source commit `9b22c13689e819743e57e2a847a65f476b94331f` and evidence/docs
commit `4fa3f3fa5e07986b00d300f791a411cee6caaeae` were pushed normally;
`git ls-remote origin refs/heads/feature/r1-commercial-baseline` matched the
evidence/docs commit. Jira GS-114 comment 11154 records the result. At handoff authoring, the only tracked diff was this final update. Existing
untracked PWA assets, managed components, logs and readbacks remain untouched.

The former broad C3 qualification profile was narrowed to
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`,
`GS_BAT_C8_PHYSICAL_WAKE=ON`, `GS_BAT_C8_ACK_TRACE=ON`, and
`GS_BAT_C8_FIXTURE_SECURITY=ON`. The narrow option reads existing R&D identity
state without NVS mutation; missing state fails closed. The profile keeps the
real GPIO4/timer light-sleep and production ACK/retry path, with no generic UART
HIL command plane. Commercial defaults remain OFF. The P9-A S3 Hub has only
the exact-key ACK-hold fixture enabled and embeds the exact signed C3 A image.

Host generation completed with exit 0 under ESP-IDF 6.0.3. Signed C3 A/B/N/R
are 987,136 bytes each and fit the 1,966,080-byte C3 OTA slot. A/B/R share
RSA-3072 signer fingerprint `60d83d7e7b00c3c80a883f43546cc33d3f7e76c5e83ab2467cbb425a83586ef6`; wrong-key N uses
`dfd5a8ab1168f86423d709406292f0c2178456b25aafcd3484ae053592b15843` and was
rejected against A's trusted key. S3 signed-FOTA N/B/R embed their exact C3
images and all fit 4 MiB app slots. The separate P9-A S3 ACK-hold image is
1,940,512 bytes, embeds C3 A exactly and has 2,253,792 bytes free in its
4,194,304-byte slot. All candidates remain host-only and NOT_INSTALLED. Hashes,
versions, profile checks, partition rows, keys' public fingerprints and
superseded artifacts are in the [P9 execution manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/P9_EXECUTION_MANIFEST_20261015.json).

Focused validation: S3 fixture plus signed-FOTA Python tests 40/40 PASS;
stable profile tests 4/4 PASS; Python syntax checks PASS; eight C3/S3 candidate
images compiled and profile/signature/embed/slot checks PASS; `git diff --check` PASS. The new test-plan section sets the independent observer minimum:
passive common-timebase C3 UART0/GPIO4/EN and S3 UART capture plus a
non-invasive C3 current channel, 1 MS/s digital at 115200 baud, 1 kS/s current,
cross-channel alignment within 10 ms, no target drive/power interruption, and
demonstrated awake/sleep current separation. `make feature-coverage-test
physical-hil-catalogue-test` passed: 22 traceability tests and 101 catalogue
cases; device_access=NONE. No observer equipment is currently identified or
qualified.

Stage 2 remains unauthorized. Stage 1 comment 11145 is read-only and does not
cover observer attachment, serial opening, app-only installation, expected
reboots, real AM312 stimulus, ACK-hold commands, signed-FOTA triggers or
recovery. Historical match criteria are C3 MAC `14:63:93:c5:d1:58` / USB-JTAG
serial `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` and S3
MAC `7c:4f:ad:b7:2a:20` / CH343 serial `5CBC401023`; current identities, ports,
images, slots, authenticated session, replay admission, pending EventKeys,
wiring and recovery are UNKNOWN. The S3 console is needed for
`ARM_C8_ACK_HOLD`, `RELEASE_C8_ACK_HOLD` and
`START_SIGNED_C3_FOTA`; its ownership and DTR/RTS reset behavior remain
unverified. The required staged package and exact image hashes are in the P9
manifest. No board interface or observer was connected and no hardware
operation occurred. P9-A/P9-B remain BLOCKED / NOT_RUN; GS-114 stays In
Progress. P1/P2/P6/P7 and controlled P4/P5/P8 dispositions are preserved;
P3 remains PARTIAL, P4 historical q10-q12 OPEN, P5 retry identity LIMITED, and
P10 remains GS-149. GS-118 rollback stack is still provisional at 12 KiB with
no measured high-water evidence.

**Next:** obtain the single consolidated Stage 2 owner authorization for the
exact identified pair and named observer/port/equipment scope in the manifest.
Before any install or P9 stimulus, Stage 2A must verify both identities, safe
exclusive no-reset observation, current image/slot/session/pending-key state,
and an identity/EventKey-preserving app-only recovery route. Stop if any check
remains unknown. No board or serial access is authorized meanwhile.

## GS-114 P9-A ACK-wait instrumentation and host validation — 2026-10-16 03:14 UTC

Resumed from GS-114 Jira comment 11149 on canonical branch
`feature/r1-commercial-baseline`, source HEAD
`d992eee9475239474aca48c4bf28c0ee824f5590`; context preflight PASS
(`2026-10-13.001`). Two other Codex CLI sessions had the canonical directory
as cwd but were idle: no active build/Git child, no repository file descriptor,
and their open files were terminal/pipes or Codex logs. Existing untracked
PWA assets, managed components and physical logs/readbacks remain preserved.

Implemented a bounded, RAM-only `C8AckWaitTraceRecorder` in
`code/firmware/node/power/power.hpp`, compiled into a C3 image only when
`GS_BAT_C8_ACK_TRACE=ON` with `GS_BAT_C8_PHYSICAL_WAKE=ON` and
`GS_HIL_BUILD=OFF`. It observes the existing Node send/ACK/sleep path without
changing retry, ACK, persistence, radio or sleep decisions. MAC success keeps
the current receive-wait interval open until the exact authenticated Durable
ACK retires that EventKey. Confirmed failed transport closes the bounded
receive interval and records sleep eligibility between retries. Wrong-key,
volatile, unauthenticated, late/missing, session-replaced, overflowed or
watchdog-expired traces cannot report complete.

The trace carries exact Node/session/sequence identity, MAC outcome,
boot-generation/reset reason, boot-relative ordered timestamps, sleep-inhibitor
reason masks, sleep entry/wake and radio-restore outcomes. It is emitted as
additive authenticated NodeHealth schema 4 on the existing health cadence;
legacy schemas remain unchanged, and the Hub records the trace without
replacing the last full operational NodeHealth snapshot. The fixed 16-event,
three-reason trace is 220 plaintext bytes at maximum Node ID size and fits the
secured frame. The trace is RAM-only, timestamps wrap after about 49.7 days,
and its scheduled report may lag until the normal health interval (up to the
existing 300-second cadence). A reset loses an open trace. This is retrospective
supporting evidence, not a continuous reset-safe physical observer.

Host-only matched C3/S3 candidates built with ESP-IDF 6.0.3. C3 app SHA-256
`57273e8203179d32c4075f75e906444e8a35d628f2caf71b89cba6ab8e83b354`
(945,760 bytes) is embedded byte-for-byte in S3 app SHA-256
`a4b3d7a3c27ac04c517967e9dde28c712f6febf21873c16809f89e32561a5146`
(1,899,136 bytes). C3 profile has HIL build OFF, HIL control ON, physical wake
ON and ACK trace ON. S3 has broad HIL controls OFF and only the C8 ACK-hold
fixture ON. The compiled S3 partition-table hash is
`bb0066feee7368e621c6f0f0d7bfdf47cbc5bbbf4cfdd9eccab9525ad683f82a` and
matches its CSV. The local build report is
`code/build/gs114_fixture_pair/build-aq8ooz92/fixture_pair_report.json`;
deployment is unauthorized and no image was installed.

Validation results:

- `make gs114-ack-wait-host-test`: exit 0, 36 checks PASS. Includes success-MAC
  wait beyond the 10-second bounded receive interval, exact Durable ACK
  retirement, failed-transport bounded listen and retry sleep, late ACK marked
  incomplete, wrong/foreign/unauthenticated/volatile/replayed ACK rejection,
  watchdog, session replacement, overflow, boot generation, secure-report
  tamper rejection and Hub health preservation.
- `ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
  make CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic
  -fsanitize=address,undefined -fno-omit-frame-pointer -DGS_PRODUCT_AI=0'
  gs114-ack-wait-host-test`: exit 0, 36 checks PASS under ASan/UBSan.
- `make gs114-ack-wait-host-test battery-c8-host-test gs150-host-test
  s3-fixture-commissioning-test`: exit 0; ACK trace 36, BAT-C8 72 C++ checks
  and 11 Python tests, GS-150 1,500 checks, and S3 fixture 15 tests PASS.
- `python3 -m unittest discover -s tests/python -p
  test_secure_signed_fota_fixture.py -v`: exit 0; 22 tests PASS, including
  the ACK-trace default-OFF and invalid-profile CMake guards.
- `make gs114-c3-s3-c8-p9-build`: exit 0; both target apps compile, exact
  embedded C3 hash/profile/partition checks pass. No hardware access.
- `make validation-board-e2e`: exit 0; board-stack simulation 10/10 scenario
  groups PASS. `make validation-framework-test`: 46/46 PASS.
- `make feature-coverage-test physical-hil-catalogue-test`: exit 0; 205
  features/211 modules/17 physical definitions, 22 mapping tests, and 101
  physical catalogue cases pass with `device_access=NONE`.
- `make validation-node`: exit 2; 26/27 stages PASS. The ACK trace stage passed
  at 34 checks before the final two late-ACK assertions were added; the current
  focused 36-check target and sanitizer both pass. Only the required P0 gate
  failed: all 26 scenario checks pass, but `product_status=PARTIAL` and
  `physical=NOT_RUN`.
- `make validation-hub`: exit 2; 43/45 stages PASS. The existing Hub journal
  C8 ACK-hold deduplication gate passed 34/34 and ACK-drop gate 16/16. The
  journal migration assertion `clean migration commits` failed (exit 2, zero
  matched assertion groups), and P0 failed on `product_status=PARTIAL` / physical
  NOT_RUN. The ACK trace stage passed at 34 checks before the final test-only
  assertions; current 36-check focused and sanitizer runs pass.
- `make validation-contract`: exit 2; 36/37 stages PASS. P0 alone failed on
  `product_status=PARTIAL` / physical NOT_RUN. The ACK trace stage passed at
  34 checks before the final test-only assertions; current 36-check focused
  and sanitizer runs pass.

`GS-114` P9-A remains **BLOCKED / NOT_RUN**; P9-B remains **BLOCKED / NOT_RUN**.
P1–P8 dispositions are unchanged. No board interface was opened, and there was
no USB/IP attach, flash, reset, wake, reconnect, erase, OTA, sensor stimulus,
recommissioning or security operation. Physical P9 still requires exact
Stage 2 authorization, verified present board/image/slot/session/pending-key
state, safe recovery, a qualified independent reset-safe continuous observer,
and the separate signed-FOTA trust/rollback prerequisites for P9-B. GS-114
stays In Progress; P10 remains GS-149. No product or security decision changed;
context version remains `2026-10-13.001`.

See the [GS-114 execution report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
and [P9 manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/P9_EXECUTION_MANIFEST_20261015.json)
for exact source/profile hashes, test receipts, preserved dispositions and
future physical prerequisites.

## GS-114 Stage 1 passive diagnostic follow-up — 2026-10-16 01:19 UTC

Follow-up was performed under read-only Stage 1 authorization in GS-114 comment
11145. It started from canonical `feature/r1-commercial-baseline` HEAD
`fb78d85ca6a6b1413b066842f47b0327441ac720`; origin matched and context
preflight passed. Existing untracked evidence/assets remain preserved.

Windows PnP history establishes a strong likely association between current
BUSID 3-3 and the historical C3 USB Serial/JTAG endpoint: both use root-hub
HSP3 / port 3, and the descriptor-failure node arrived two seconds after the
historical C3 instance was removed. Windows records problem 43 and
`USB_DEVICE_DESCRIPTOR_FAILURE`; the current descriptor gives no C3 serial or
MAC. The current C3 board identity therefore remains **UNVERIFIED**.

The S3 CH343 `5CBC401023` is now listed by `usbipd` as `Attached` to WSL, while
the earlier Stage 1 snapshot listed it as `Shared`; this follow-up did not
attach it. WSL sysfs sees the S3 adapter at `/dev/ttyACM0` and no process owns
that tty. Windows COM9 is non-present/phantom. `openfiles` cannot enumerate
local handles (tracking disabled/access denied), and no Sysinternals handle
tool is installed, so exact serial-handle ownership and DTR/RTS safety remain
unknown.

The C8 C3 source explicitly calls `esp_light_sleep_start()` and the HIL profile
selects the native USB Serial/JTAG console. ESP-IDF 6.0 documents that light
sleep gates the USB clocks, can make the device appear erroneous while still
connected, and may prevent re-enumeration after wake. Prior C3 diagnostic logs
showed USB silence while authenticated Hub traffic continued. This is a
plausible explanation for the same-port failure, not proof of the current
sleep cycle or current installed profile.

The existing authenticated NodeHealth/schema-3 path through the S3 can report
sleep/wake/event counters and post-rejoin status without opening C3 USB, as
shown by prior physical evidence. Its normal 300-second cadence makes it an
after-wake summary, not a continuous observer for a 12-second ACK hold. The
WSL fd scan found no current Hub tty reader, and the S3 serial path has not
been proven safe to open. A continuous reset-safe observer remains unqualified.

Historical evidence includes a C3 app-only install/readback at `ota_0` with a
known app hash and a prior S3 partition/selector readback. The C3 selector
procedure used a ROM reset/RTS; these records do not establish a presently
safe restore path. P9 signed test candidates and host checks exist but remain
uninstalled, and current target trust is unknown. GS-118 rollback has no
physical PASS or measured task-stack high-water result. Current image/slot,
authenticated session, pending EventKeys, and recovery readiness remain
**UNKNOWN**.

No board interface was opened or changed, and no hardware operation occurred.
P9-A/P9-B remain **BLOCKED / NOT_RUN**. Next eligible physical step requires a
separate Stage 2 authorization plus safe identity/port verification, a
no-reset current-state read path, a qualified observer, and a verified
identity/EventKey-preserving recovery route. Do not wake or reconnect the C3.
Detailed values and methods are in the [Stage 1 diagnostic addendum](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
and `stage1_additional_passive_diagnostics` in the P9 manifest.

## GS-114 P9 Stage 1 read-only inspection — 2026-10-16 01:06 UTC

Executed only the Stage 1 scope explicitly authorized in GS-114 Jira comment
11145. Canonical branch `feature/r1-commercial-baseline` was at local/remote
HEAD `1534b61fa3269bb0a3a01311906f040d41d4faa9`; context preflight PASS.
Existing untracked files and raw evidence remain preserved. Current GS-114
task is the sole active related Codex thread; an older related task is idle and
no Git index/HEAD lock was present.

**Result: BLOCKED after passive enumeration.** Windows reports S3 USB bridge
CH343 `COM9`, serial descriptor `5CBC401023`, PnP status OK; this matches the
historical S3 adapter but does not verify the S3 MAC or app. A second USB
device is reported as `VID_0000:PID_0002` with a device descriptor failure
and PnP status Error; it cannot be assigned to the C3, so C3 identity/port
cannot be verified. WSL shows only USB/IP virtual root hubs, no target USB or
serial nodes, and no serial fd owner. Windows COM9 process ownership and
DTR/RTS/open safety remain unknown. No target interface was opened or modified.

Current firmware hashes/slots, authenticated sessions/replay admission,
pending EventKeys, C3 sleep/reset state, continuous reset-safe observer, and
target-specific signed app-only recovery readiness remain UNKNOWN. Host P9
candidate images were rehashed and match the manifest, but are not installed
and do not prove the target trust or recovery path. Physical P9-A/B remain
BLOCKED / NOT_RUN; no case disposition changed.

**Next:** do not attach/open/restart the descriptor-failing C3 or open COM9.
Stage 2 requires safe re-identification and exclusive port ownership, an
independently proven no-reset read path, current target firmware/slot/session/
EventKey baseline, qualified continuous observer, verified app-only recovery
route, and a separate explicit Stage 2 owner authorization. Details and exact
commands are in the [Stage 1 report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
and the manifest's `stage1_inspection` object. The existing P1–P8 dispositions
and GS-114 In Progress state are unchanged.

## GS-114 resumed P9 host engineering checkpoint — 2026-10-15 19:31 UTC

Resumed the original GS-114 P1–P9 assignment from the 15:23 UTC quota pause.
Latest observed `/status` at 19:31 UTC was 80% of the five-hour limit remaining;
the requested three-minute monitor remains active and the requested pause
threshold is 12%. At the start of this final status refresh, local and remote
HEAD matched `7775f0b5f7dbe5198eb761b68358f1ffee8c7099` on
`feature/r1-commercial-baseline`; this refresh is being committed on that
checkpoint. Context preflight PASS (`2026-10-13.001`).
Tracked source is clean. Existing untracked PWA assets, Hub managed components,
raw physical logs and readbacks remain preserved.

Fixed the S3 signed-FOTA packager profile guard in `a5428cf`: it now accepts
only signed C3 `physical_wake=true` with generic C3 HIL controls OFF for the
S3-only fixture, while leaving the legacy classic-Hub profile rule unchanged.
P9-B host artifacts are complete in ignored
`code/build/gs114_p9_signed/20261015T185926Z/`: C3 signed A/B/N/R and matched
S3 N/B/R. A/B/R trust fingerprints match; wrong-key N was rejected by the A
trust key; all Hub variants contain the exact corresponding C3 bytes. Images
fit the historical OTA app slots and remain **NOT_INSTALLED**. The external
test keys remain outside the repository. The [fixture-specific manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/P9_EXECUTION_MANIFEST_20261015.json)
records hashes, profiles, board identity limits, physical scope and recovery.

Focused P9 Python suites ran 55 tests, PASS/exit 0; S3 fixture suite ran
15/15; `make validation-hub` ran 44 stages, 42 PASS and 2 FAIL (pre-existing
Hub journal migration assertion and required P0 `product_status=PARTIAL`).
The P9 ACK-hold, signed artifact, FOTA/security and storage/recovery stages
passed. `make feature-coverage-test` passed (204 features, 211 modules, 17
physical definitions, 22 tests); `make physical-hil-catalogue-test` passed 101
cases after fixing an evidence-field path separator caught by its first run.
JSON parsing, `git diff --check` and context preflight pass. This is
software/build evidence only. No hardware operation occurred.

C3 USB-power from the laptop and no WSL USB attachment do not block host
builds; no C3 flash was needed. The boards were not reidentified, no serial
port was opened, and current image hashes, active OTA slots, pending EventKeys
and continuous reset-safe sleep observation were not verified. GS-146 comment
10734 does not authorize P9 flashing/OTA/stimulus; the exact P9 scope approval
and observer/recovery prerequisites remain missing. P9-A and P9-B physical
remain BLOCKED / NOT_RUN. P3 provenance remains PARTIAL, P4 q10–q12 OPEN, P5
retry identity LIMITED. GS-114 remains In Progress; P10 remains GS-149.

Jira progress comments are GS-114 #11110, GS-110 #11111 and GS-118 #11112.
Commit `280fd44ce004b9ee68cc9f776c053ff3fcf6b9ff` includes the report, this
handoff, P9 manifest and qualification matrices; the canonical origin HEAD was
verified identical. Latest observed `/status` was 80% remaining at 19:31 UTC;
the requested monitor remains active with a 12% pause threshold.

**Resume boundary:** wait for the owner's explicit response to the one
consolidated P9 approval request. Before tests, verify board identity/port,
current image/slots, pending EventKeys, authenticated session, continuous
reset-safe Node observer and app-only restore route. Stop if any prerequisite
fails or requires erase, recommissioning, eFuse, Secure Boot or production
trust changes. C3 laptop USB power and no WSL attachment do not block host
builds, and no C3 flash is proposed for P9-A. Do not open ports or operate
boards before authorization. GS-114 remains In Progress; physical P9 remains
BLOCKED / NOT_RUN.

## GS-114 pause at five-hour limit threshold — 2026-10-15 15:23 UTC

Per owner instruction, `/status` reported 6% of the five-hour limit remaining
and GS-114 work paused. The [detailed execution handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
records completed P9-A fixture/build/tests, completed signed C3 A/B/N/R host
artifacts, the intentionally interrupted S3 N build and Hub aggregate gate,
all preserved files, physical blockers and exact resume commands. P9-A/B
physical remain BLOCKED / NOT_RUN; GS-114 remains In Progress. No hardware
operation occurred.


## GS-114 P9 fixture engineering — 2026-10-15

Starting canonical local/remote HEAD `d0869cd6c128a61aff7fbc58ca448ebf439c33a9`,
branch `feature/r1-commercial-baseline`, context preflight PASS. The exact-key
bounded S3 P9-A ACK-hold fixture is implemented and its 34-check host gate and
isolated S3 target build pass. A test-only S3 authenticated signed-C3 FOTA
trigger and external test-key A/B/N/recovery artifact workflow are implemented;
the first signed build uncovered and fixed an implicit wrong target selection.
Signed artifact generation and affected component regressions are underway.
The [current GS-114 execution handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
records candidate hashes, source changes, safety boundaries, validation and the
fixture-specific execution manifest. No hardware operation occurred. Physical
P9-A/B remain BLOCKED / NOT_RUN pending exact-operation approval, current
installed image/slot/pending-key evidence and reset-safe continuous C3
observation. P3 PARTIAL, historical P4 anomaly OPEN and P5 per-attempt identity
LIMITED are preserved; P1/P2/P6/P7 and controlled P4/P5/P8 physical PASS are
reused. P10 remains GS-149 and GS-114 stays In Progress. Existing untracked
evidence and unrelated files remain untouched.


## GS-144 minimal workload integration — 2026-10-15

Reconciled historical `gs144-workload-qualification` against the canonical Node
power, health, sleep, retry, ACK and recovery implementation. At start canonical
local/remote were `12eae946db1ce8c810c9cc7df8e2c17d27d30889`. Historical GitHub
tip was `ad7b9b7434246dd567ea0d800adccec65d724f00` (implementation
`9af8c4f97c3db2314075ce62be5b95cb34fab923`); the separate `/tmp` clone was
clean apart from ignored build/log/cache/evidence artifacts. Its preservation
and final retirement checks are recorded in the [GS-144 integration and
retirement report](../exec-plans/evidence/GS144_MINIMAL_INTEGRATION_AND_RETIREMENT_20261015.md).

Canonical now has one machine-readable workload specification and a registered
test contract; production runtime algorithms were not changed. Seven historical
candidate profiles remain explicitly `PROPOSED_NOT_APPROVED`; the accepted
profile, event schedule, outage/RF assumptions, commercial cell/capacity,
reserve, measurement boundary/uncertainty, service limits and endurance target
remain open. GS-D031's 300-second health and derived 910-second offline facts
are captured separately. The optional historical battery estimator was not
integrated: it is not required before the measured workflow and its flash-write
conversion divides mA·s by 3,600,000 rather than 3,600 (1,000× undercount).
No battery-life or commercial acceptance claim is made; GS-144 remains In
Progress and GS-149 stays blocked on accepted GS-144 and measurement inputs.

Focused validation passed: workload spec 4 tests; BAT-C8 72 C++ checks + 11
Python invariants; GS-40 1,320; GS-150 1,500; Node runtime, persistence and
retirement protocol host suites; feature traceability 199/210/15 with 22 tests;
validation framework 46/46. Full component/release gates and physical testing
were not run. Existing unrelated untracked PWA, managed-component and GS-114
evidence remains preserved. Next: obtain one product approval for workload,
battery/reserve, boundary/uncertainty, latency/reliability and endurance; then
proceed through GS-140/B0, GS-41/42/141/43 BEFORE, GS-44, matched GS-51 and
GS-149. Canonical integration commit `9393ac8335e84582361642e2134ae3dc41567a5c`
was pushed before cleanup. The complete standalone historical clone was
verified in the external backup at
`/home/udaybhan/projects/gs144_retirement_backup_20261015T130000Z`; its local
ref at `9af8c4f97c3db2314075ce62be5b95cb34fab923` and GitHub ref at
`ad7b9b7434246dd567ea0d800adccec65d724f00` were then retired. The temporary
directory and live branch refs are absent. See the linked report for backup
inventory verification and remaining worktrees.

## GS-114 BAT-C8 battery-first physical evidence handoff — 2026-10-15

Resumed from GS-114 comment 11029 and GS-110 comment 11030 on canonical branch
`feature/r1-commercial-baseline`. Start local HEAD and actual origin HEAD were
both `97eff6c2ed927d641cd3ee3b9854dd8c38cb176b`; context preflight PASS
(`2026-10-13.001`). Tracked files were clean at start. Pre-existing untracked
PWA assets, ESP-IDF managed components, and raw GS-114 logs/readbacks/manifests
were preserved and not staged.

The dated [GS-114 execution handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
reconciles the current TEST_PLAN with physical evidence: P1/P2/P4/P5/P6/P7/P8
PASS; P3 measured behavior PASS with the S3 running-image hash unverified, so
the case/catalogue remains PARTIAL; P9 ACK hold/release and signed-FOTA
sleep-inhibition remain BLOCKED / NOT_RUN; P10 remains GS-149. P4 q10–q12's
unexplained extra events and P5's unlogged per-attempt retry key remain explicit
limitations. No evidence was relabeled from software simulation.

No board, USB/serial interface, firmware, power, reset, storage, OTA,
commissioning or motion operation occurred. No tests, software gates or full
release gate were rerun. The existing report now contains the case closure
matrix, P3 provenance findings, P9 procedures/prerequisites, GS-40 acceptance
mapping, GS-144 open owner inputs and the next plan. The qualification plan's
stale all-NOT_RUN header and the aggregate/P8 status in `PHYSICAL_QUALIFICATION.csv`
were reconciled; detailed catalogue case statuses were already consistent.

**Next:** Keep GS-114 In Progress; close provenance only with truthful source
evidence; obtain the missing P9 fixtures/signing/rollback/observer prerequisites
before seeking exact-operation authorization. Coordinate matched real-target
GS-40 300/910-second and caregiver-visibility acceptance. Prepare one GS-144
owner decision for reproducible workload, selected battery/reserve, measurement
boundary, latency/reliability and endurance target before GS-140/B0–B4/GS-51/
GS-149 measurement. No hardware operation is authorized by this handoff.

## Git handoff checkpoint

The handoff's documentation changes are based on local/remote start checkpoint
`97eff6c2ed927d641cd3ee3b9854dd8c38cb176b`; the final documentation commit and
remote verification are recorded in the new GS-114/GS-110 Jira comments. The
pre-existing untracked artifacts above remain preserved.

## GS-109 / GS-148 CloudSync security decision package — 2026-10-15

Prepared [the consolidated implementation-ready decision package](../exec-plans/evidence/GS109_GS148_CLOUDSYNC_DECISION_PACKAGE_20261015.md)
from verified local/remote checkpoint
`bb2b77cb26ac88aaea244b7d1f73b124d18f6a3f` on
`feature/r1-commercial-baseline`; context preflight PASS
(`2026-10-13.001`). Reused GS-109 design review/register comments 10595/10601
and GS-148 comment 11007. The package covers D03/D05/D07/D11/D16 and
prerequisites D04/D06/D12/D15, distinguishing accepted GS-D032 invariants from
new decisions. It checks the recommendations against the current CloudSync
worker, backend ownership/durable-commit path and S3 single-radio/blocking HTTPS
limitations. GS-109 comment 11008 contains the consolidated recommendation and
approval request; GS-148 comment 11009 cross-references it.

This is a proposal only. No new contract is approved or implemented; commercial
target sending remains disabled. No tests or hardware operations were needed or
performed. No credentials, roots, workflow states or accepted contracts changed.
The previous GS-148 Hub gate status, historical journal migration assertion
FAIL, and P0 `product_status=PARTIAL` remain unchanged. The next action is owner
disposition of the nine decisions in the linked package; after approval, execute
its staged D12/D04 → D03/D05 → D07/D15 → D11 → D06/D16 implementation order.

## GS-148 Hub gate and GS-109 production CloudSync decision map — 2026-10-15

Resumed from canonical local/remote HEAD `6489b25670bade448e3fee4776a99ed804ca62d8`
on `feature/r1-commercial-baseline`. Context preflight PASS
(`2026-10-13.001`); tracked tree clean; existing untracked PWA assets,
managed components and GS-114 raw logs preserved. No active competing source,
build or serial-capture process was found. Read GS-148 comment 10974 and the
existing GS-109 audit/register in comments 10595/10601; the 2026-10-12 decision
register still marks D01–D16 open. No hardware operation or commercial sending
occurred.

The corrected current-source Hub gate ran as `make validation-hub` and exited 2
after 439.371 s. Its report is
`code/evidence/validation_framework/hub-1792022788167507214/report.json`;
source HEAD `6489b25670bade448e3fee4776a99ed804ca62d8`, source fingerprint
`505acbfc55d449dbc0b7a9f5720fb2acd09fd64e0223028dca93992a88ff24a0`,
`source_unchanged=true`, 42 stages total: 40 PASS, 2 FAIL. Cloud contract
passed with count 2; `cloud-worker-backend-integration` passed with count 1.
The direct `make -C code gs148-cloud-worker-api-integration-host-test` also
passed: protocol invalid-receipt modes 15, pending 200, peak batch 16, peak
retry entries 64, persistence cuts 2; lost-response retry used the same key,
with one durable effect and one caregiver projection. The lightweight
validation-framework test passed 41/41, including explicit failure-propagation
coverage. Contract/backend reports from the prior checkpoint remain separately
identified at fingerprint `a6987bd82c8ce32e41522e030fa31e7e9eca3bb7b3e62550e48d60738a3efc15`:
their worker/API stage passed count 1 and their only aggregate failure was P0
PARTIAL. They are not relabeled as current-fingerprint reports. The current
Hub run independently verified the cloud stages after the harness fixes.

The Hub aggregate failures are the unchanged historical migration assertion
`clean migration commits` (count 0) and required P0 full-product gate
(`product_status=PARTIAL`, despite 26 software scenarios plus one Chromium test
passing). No additional regression was found. Commercial sending remains
disabled; the host injected authority and target TLS channel do not provide a
production credential or authority source.

The remaining production contract is assigned to GS-109/GS-148 decisions
D03, D05, D07, D11 and D16, with supporting D04/D06/D12/D15 dependencies.
Recommendations and affected modules are recorded in the dated GS-148 evidence
handoff. No new product/security option was selected; owner approval remains
required before target activation. GS-148 remains In Progress; P0 PARTIAL and
the migration FAIL remain visible and independent.

## GS-148 P4/P5-B1 bounded CloudSync caller checkpoint — 2026-10-14

On canonical `feature/r1-commercial-baseline`, starting local/remote HEAD
`94c2c5e29838f05d37ac15ca4342e6784ae06d16`, context preflight PASS,
the CloudSync worker gained a test-injected current Home/Hub/epoch and original
event-owner authority gate. It preserves original EventKey and generation,
requires exact backend COMMITTED via existing strict receipt handling, and
refuses completion after authority transfer. It is not wired into the S3
runtime: GS-109 commercial credential issuance/verification and target
ownership/concurrency contracts remain open, so commercial sending stays
disabled. No hardware or backend production configuration changed.

[GS-148 execution and exact resume handoff](../exec-plans/evidence/R1_GS148_P4P5_B1_20261014.md)
records source scope, prior audit, original fixture/mapping test failures,
focused checkpoint PASS (`GS148-CLOUD-WORKER-001`), framework 41/41 and mapping
20/20. Full affected component gates, backend trigger-to-caregiver E2E,
sanitizer and S3 build remain NOT_RUN for this change; do not claim product
completion or release PASS. Historical Hub migration FAIL, P0 PARTIAL and C8
physical evidence remain unchanged. Untracked GS-114 logs, managed components
and PWA assets are preserved. The next action is the affected gates and a real
backend-path integration scenario, followed by sanitizer/target build where
applicable; GS-109 authority and concurrency decisions are prerequisites for
commercial target activation. Commit and remote checkpoint are recorded in
the dated Jira GS-148 comment and Git history after this report is delivered.

The owner-requested allowance guard triggered at 17:54:53 UTC with 4% left
(reset reported at 20:54:43 UTC). Engineering paused at pushed commit
`42a89c33c37cf7ba4681422c56294b98bdcba634`; the detailed handoff-only
follow-up is in the linked report. No affected aggregate gate or target build
may be inferred from the scoped PASS.

## GS-130 bounded risk-prioritized regression checkpoint — 2026-10-14

GS-130 comment 10932 was executed in the canonical worktree on
`feature/r1-commercial-baseline`, starting at local/remote
`ed1a7dfde0299e8c84e4f12a9f1dd48dd39836ed`; context preflight PASS,
version `2026-10-13.001`. There was no competing canonical source writer.
[Focused report and resume handoff](../exec-plans/evidence/GS130_RISK_REGRESSION_20261014.md)
records scope, six added scenarios, original failures, repaired source,
per-scenario assertions, registration, receipts and exact next action.

One actual R1 blocker was reproduced and repaired in FoundationService: cached
or old explicit received-contact telemetry could resurrect OFFLINE or clear a
newer DEGRADED state. Duplicate/older and already-expired online observations
are ignored; genuinely new, still-fresh contact recovers under the existing
Node/Hub leases. Authentication, transport, EventKey, storage and target firmware
are unchanged. No new product requirement or context version is introduced.

Six permanent production-code scenarios extend existing board/health/rules/API
harnesses. Board E2E is now 10 groups / 398 checks; feature boundaries 133;
health-config 17; focused backend/durable API 17; framework 41; mapping integrity
20, with 182 rows / 205 modules / 15 physical definitions. The 78-stage registry
and local/release membership remain. Omitted/failed new cases propagate failure.
Mandatory Python discovery found six legacy invalid coverage statuses; these
are corrected to PARTIAL with an added schema regression. Physical results and
implementation fields were preserved.

Final affected gates ran at fingerprint
`11b8ce399cce108c2dc2fedede0c54e31a31a6d45df05beef8539eba3d7fe574`,
all with source unchanged. Node 23/24, Hub 39/41, contract 33/34, backend
13/14 and PWA 11/12 stages passed. **Every aggregate remains FAIL** because
of mandatory P0 `product_status=PARTIAL`; Hub additionally retains migration
`clean migration commits` FAIL. Full Python discovery is OK, 459 tests with
one declared historical classic ESP32 skip; storage ASan/UBSan PASS. Existing
P0 26 assertions plus one targeted Chromium case pass without closing its
production trust gaps. No unexpected regression remains in these receipts.

No hardware, USB/IP, reset, flash, commissioning or motion occurred. Existing
untracked PWA assets, managed components and private GS-114 logs remain intact.
Prior C8 physical results are reused: P3 catalogue remains PARTIAL for S3 image
provenance; P9 ACK/FOTA physical BLOCKED; P10 GS-149. GS-104 R01–R09, GS-89,
GS-148 production credentials, historical interval coverage, unconnected generic
backend flags, human OIDC and external provider delivery remain genuine gaps.
`validation-fast`, full browser campaign and `release-gate-final` were NOT_RUN.
The implementation/closeout commit and verified remote are recorded in the
latest Jira delivery comments and the Git checkpoint below.

Git checkpoint: implementation/tests/evidence commit
`df31bbda9e34bbd8640e232ab37ee1fe317f71d3` was pushed to the canonical branch;
`git ls-remote origin refs/heads/feature/r1-commercial-baseline` matched local
HEAD. Tracked files were clean after that push; pre-existing untracked assets
and raw hardware evidence remained. The following documentation-only closeout
records this verification; its exact final HEAD is in GS-130/GS-116 delivery
comments. Resume from actual canonical HEAD, not an older prompt checkpoint.

**Next separate task:** GS-148 P4/P5-B1 CloudSync under comments 10810/10933.
Read its active lifecycle handoff, existing caller/worker, strict receipt parser
and backend trusted ownership before implementation. Preserve exact key/time,
Home/Hub/Node/enrollment binding and durable COMMITTED-before-completion. If
production issuer/verifier authority is undefined, keep commercial sending
not-ready and surface that precise security prerequisite. GS-148 implementation
has not started; do not automatically begin unrelated work from this checkpoint.

## GS-116 / GS-130 BAT-C8 coverage integration — 2026-10-14

Task-start canonical checkpoint was local/remote HEAD
`51ffc694308b16672c68e114c74deb8c96d36037` on
`feature/r1-commercial-baseline`; context preflight PASS. The board-stack
software suite and C8 P1–P10 test mapping were audited. Detailed matrix, actual
receipts, provenance and physical limitations are in
[GS-116/GS-130 C8 coverage audit](../exec-plans/evidence/GS116_GS130_C8_COVERAGE_AUDIT_20261014.md).
The validated implementation/evidence commit is
`ab72ac2f141f32c375d9f7fe7598ef7456ce1a87`; it was pushed and origin matched
at verification. The final closeout documentation commit and remote checkpoint
are recorded in the Jira delivery comments.

The 78-stage registry currently selects 68 fast and 78 release stages, with
Node/Hub/contract ownership counts 24/41/34. Added explicit production-code
board-stack case `BOARD-TC-130-009` for the first newly qualified PIR event
after Hub reboot; the existing board stage now requires all nine case markers.
This fills a software simulation gap only. No product firmware behavior or
requirement changed.

Validation: `make validation-board-e2e` PASS, 9 groups / 358 checks;
`make battery-c8-host-test` PASS, 72 C++ + 11 Python invariants;
`make validation-framework-test` PASS, 40/40;
`make feature-coverage-test` PASS, 176 rows / 205 modules / 15 physical cases
and 19/19 tests; `make physical-hil-catalogue-test` PASS, 99 cases. Full
`validation-fast` and `release-gate-final` were not run.

The physical catalogue now maps individual GS-114 evidence: P1/P2/P4/P5/P6/P7/P8
PASS, P3 physical behavior PASS but catalogue PARTIAL because the exact running
S3 image SHA is unavailable, P9 ACK/FOTA BLOCKED, and P10 remains GS-149.
Preserved P4 q10–q12 as an unresolved failed trial and P5's per-attempt retry
key observation limitation. The historical Hub journal migration assertion
`clean migration commits` still fails; P0 `product_status=PARTIAL` is a separate
open release blocker. GS-114 stays In Progress.

No hardware was accessed. At task start, tracked files were clean. Existing
untracked PWA assets, managed ESP-IDF components and GS-114 raw logs/install
evidence remain preserved. Work completed in this task touches the board-stack
test, the existing suite registration, traceability, physical catalogue, master
validation guide and this work-state handoff. Next GS-114 physical gaps are P3
image provenance, P9 ACK-hold/signed-FOTA fixtures, and separate GS-149 P10
measurement. Do not start another major implementation from this checkpoint.

## GS-114 P9 software validation complete; physical P9 fixtures outstanding — 2026-10-14 15:31 UTC

The P9 ACK and FOTA software coverage audit is complete. Source checkpoint at
task start was local/remote HEAD
`3c677f0b6fa2ed77405cd87905f9e80b71e89fbf` on
`feature/r1-commercial-baseline`; context preflight passed. The only source
change is a permanent GS-150 host regression plus its traceability mapping;
production firmware did not change, and no hardware/serial/image/commissioning
operation occurred.

`ack_wait_sleep_transition()` exercises production NodeRuntime/HubRuntime. It
proves an unresolved authenticated Durable ACK keeps the exact event pending
and inhibits sleep beyond the 10,000 ms receive budget, then an authenticated
exact-key ACK retires the event and restores normal idle sleep eligibility.
`make gs150-host-test` PASS 1,500 checks; the focused ASan/UBSan rerun PASS
1,500 checks. Reused tests also passed: BAT-C8 72 C++ + 11 Python,
secure-FOTA adapter 2 groups, FOTA host 34, board-stack E2E 8 groups/325,
signed-FOTA fixture orchestration 16/16, and feature coverage 175 features /
205 modules / 15 physical cases (19 framework tests).

P9 disposition: **ACK software PASS / physical BLOCKED, NOT_RUN** pending a
bounded long ACK-hold or qualified directional RF fixture, target no-sleep
observation and exact-key commit/ACK/retirement evidence. **FOTA software
state-machine/host fixture coverage PASS / signed-target physical BLOCKED,
NOT_RUN** pending matched signed test/recovery images, trusted signing
provenance, authenticated trigger, and safe rollback/recovery. Host fixture
orchestration does not prove ESP-IDF target signature acceptance. Prior RPF07
and C8 P1–P8 physical PASS evidence is preserved and reused. P10 remains
separate under GS-149.

`make validation-node` and `make validation-contract` reached their registered
P0 product E2E and returned gate FAIL because P0 reports
`product_status=PARTIAL` / `physical=NOT_RUN`; the 26 P0 scenario assertions
passed. This remains an independent release gap, not a P9 failure. The
historical Hub journal migration assertion failure remains recorded and was
not reclassified here. GS-114 remains In Progress.

Evidence: [P9 software validation](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run05_software_20261014/C8_P9_SOFTWARE_VALIDATION_20261014.md), [consolidated GS-114 report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).

**Next priorities after this safe GS-114 checkpoint:** follow the user-approved
sequence for GS-116/GS-130 comprehensive implemented-feature regression
coverage, then authorized GS-148 CloudSync work as product priority directs.
Do not begin either scope without its applicable explicit instruction.

## GS-114 C8-P8 physical lost-ACK PASS; S3 capture transport paused — 2026-10-14 12:12 UTC

The latest physical P8 run passed on the existing commissioned R&D pair. The
S3 app-only P8 image was installed and write-verified at the read-back active
`ota_0` slot, `0x20000`. Its app SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`; boot
reported `ce9c436f0e9a-gs114-c8p8-59b8341`. The image embeds the installed C3
app SHA-256 `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.

At 12:11:57 UTC the S3 armed one-shot postcommit ACK loss. At 12:12:11 UTC it
received real PIR EventKey `p15:c3-146393c5d158n8:gs114-c8s16q14`, found its
durable outbox key under RPF00 OPEN, committed one effect (`state_changed=1`,
`records=43`), and withheld the first application ACK. Same-key deliveries
reported `state_changed=0` with unchanged record count. Authenticated Durable
ACK sends returned `ESP_OK`; NodeHealth at 12:12:13 UTC showed
`retained=0`, `durable_ack=14` (+1), `retry=15` (+2), GPIO wake, radio restore
OK and owner resumed. **P8 physical PASS.** The operator said the physical
movement preceded the direct prompt; its exact timestamp is unknown. The
prompt is not attributed as the cause of q14, and no event latency is claimed.
Full evidence is in [P8 physical run](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_PHYSICAL_20261014.md)
and its captured UART log.

A separate later ACK-drop arm was captured at 12:14:59 UTC. The operator
completed that requested movement and replied DONE, but no event/health report
followed. WSL `vhci_hcd` logs show USB/IP URB errors `-104` from 12:12:37 UTC
and the monitor later timed out on writes. The stale monitor was gracefully
interrupted and no longer owns the serial device; it has no tty fd. No further
attach, reset, flash, power operation or serial command was made. The q14
evidence predates this transport gap and remains valid. Keep all untracked raw
logs and prior evidence intact.

P3 and prior RPF07/P1/P2/P4/P5/P6/P7 PASS evidence are reused; P4's earlier
multi-key observation and P5's retry-identity observability limitation remain
documented. P9 ACK is BLOCKED because no qualified prolonged ACK-hold fixture
is available. P9 signed FOTA is BLOCKED pending matched signed test/recovery
images, trusted provenance, authenticated trigger and safe recovery. P10 is
GS-149. GS-114 remains In Progress.

**Next action:** stop hardware work at this safe checkpoint after the USB/IP
observer loss. Resume only with a fresh identified S3 capture path; do not
repeat P1–P8. Keep P9 blockers explicit and report any fixture prerequisites.
The latest source/docs checkpoint at execution start was local/remote HEAD
`fd679334780f3bcbac3113554bd43d7e2916bdd8`, context preflight PASS.

## GS-114 C8-P8 S3 app write verified; runtime boot unresolved — 2026-10-14 11:32 UTC

The operator approved the bounded S3-only P8 installation procedure. Starting
source checkpoint was local/remote HEAD
`ead9a83b9df0a1cc928280760496747f1901e38e` on
`feature/r1-commercial-baseline`; context preflight PASS. Existing untracked
assets, managed components, and earlier raw C8 logs remain preserved.

Windows reported the identified S3 CH343 (`1a86:55d3`, serial `5CBC401023`,
COM9, BUSID `3-1`) Attached. Its WSL stable by-id path mapped to `/dev/ttyACM0`.
The C3 remains the separate `0000:0002` descriptor-error device; it was not
attached, opened, reset, flashed, or recommissioned. A stale capture had an
old `/dev/ttyACM1` fd; normal TERM moved it to uninterruptible USB/IP kernel
wait, so it was not force-killed. That stale process later disappeared. The
current S3 port is now unowned; the device remained Windows Attached at the
11:32 UTC final check.

One authorized S3 ROM entry verified ESP32-S3 rev 0.2 / MAC
`7c:4f:ad:b7:2a:20`, 16 MiB flash, 8 MiB PSRAM, Secure Boot/Secure Download
disabled, and `FLASH_CRYPT_CNT=0`; no eFuse was modified. The actual table
matches the candidate table payload and preserves `ota_0`, `ota_1`,
`gs_outbox`, and `gs_state`. The valid `otadata` record selects `ota_0` at
`0x20000` (sequence 1, state 2, CRC valid).

The current-source ACK-drop S3 app was written only to `0x20000` and esptool
reported `Hash of data verified`; candidate SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`.
The expected hard reset ran. An exclusive ESP-IDF monitor with `--no-reset`
then remained attached for at least 300 seconds while USB/IP stayed Attached,
but no S3 UART bytes arrived and two read-only `FIXTURE_STATUS` attempts had
no response. Monitor closed cleanly. **The flash write is verified; S3 app
boot/running identity, fresh authenticated C3 rejoin, schema-3 NodeHealth,
RPF00 OPEN, and Durable ACK are not verified.** The silence's cause is
unknown. No further reset, recovery flash, power action, or PIR stimulus was
performed. Evidence is in [P8 installation record](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_BUILD_VALIDATION_20261014.md)
and adjacent raw logs/readbacks.

**C8-P8: BLOCKED before stimulus / physical test NOT RUN.** Do not arm
`DROP_NEXT_DURABLE_ACK` or request motion until S3 runtime/status, authenticated
C3 rejoin, schema-3 trace, and RPF00 OPEN are positively observed. Any further
reset, firmware write, or power operation requires separate authorization.
P3 controlled physical PASS and RPF07/P1/P2/P4/P5/P6/P7 PASS results remain
preserved/reused without repetition. P9 ACK/FOTA remain BLOCKED on their own
fixtures; P10 is GS-149. GS-114 remains In Progress.

## GS-114 C8-P8 candidate build checkpoint — 2026-10-14 11:07 UTC

The operator explicitly approved Python 3 for the existing ESP-IDF 6.0.3
toolchain and approved offline build/software validation; this supersedes the
earlier Python 3 restriction for this GS-114 P8 task only. The existing
`gs114-s3-c8-p8-build` builder path reuses the exact installed C3 app and
skips C3 compilation. Builder/tooling commit
`ce9c436f0e9a8324c0785bad996ed9c4a421de3d` is pushed to the canonical branch.
Context preflight passed at task startup, and no firmware source was changed
by the builder extension.

ESP-IDF 6.0.3 built an S3-only candidate with
`GS_HIL_C8_ACK_DROP=ON`, broad Hub HIL control OFF, commissioning ON, and the
16 MiB/8 MiB PSRAM fixture profile. S3 app SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`;
candidate size is 1,894,496 bytes. Its embedded Node app SHA-256 exactly
matches the installed C3 value
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
The compiled table matches the existing `ota_0`/`ota_1`, `gs_outbox` and
`gs_state` layout; the complete build/profile and focused validation receipts
are in [P8 build evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_BUILD_VALIDATION_20261014.md).
At this 11:07 build checkpoint, the S3 binary was built but not yet installed;
the later installation attempt is recorded above.

Focused results: S3 fixture suite 14/14 PASS; ACK-drop host gate 16/16 PASS;
ASan/UBSan 16/16 PASS; TSan 16/16 PASS; image and compiled-partition
compatibility checks PASS. Existing wider suites and firmware-source
sanitizer evidence are reused because product/firmware source is unchanged.

At this build checkpoint, active-slot evidence was limited to the earlier
boot banner. The subsequent actual selector readback is recorded above. The
prior record stated: the last captured S3 boot banner reports app offset
`0x20000` (`ota_0`) at 03:34:27 UTC, but reports app version
`72a223fc3b29-gs114-rpfdiag-1eec`; the exact running S3 hash and a current
post-detach selector readback remain unverified. The install plan therefore
requires a fresh exact S3 identity/active-slot check before any write and stops
if `ota_0`/`0x20000` is not confirmed. A stable S3 capture must also be
restored before a P8 stimulus. No USB/IP reattachment, reset, firmware write,
commissioning change or physical stimulus has been authorized yet. The C3
descriptor-error device remains untouched.

P3 remains controlled physical PASS; reuse RPF07/P1/P2/P4/P5/P6/P7 evidence.
P8 remains physical NOT_RUN pending explicit approval of the S3-only observer
recovery/app install plan and then a real same-EventKey retry test. P9 ACK is
blocked on a validated long ACK-hold observation fixture; signed FOTA is
blocked on matched signed test/recovery images, trusted provenance, a
supported authenticated trigger and recovery procedure. P10 remains GS-149.
GS-114 stays In Progress. Existing raw logs, generated managed components,
untracked product asset directory and historical failure evidence remain
preserved.

Next action: obtain explicit approval for the exact bounded S3-only observer
recovery and app-only install plan in the linked P8 evidence. Do not attach,
reset, write or request physical P8 motion before that approval.

## GS-114 observer checkpoint — 2026-10-14 10:08 UTC

The S3 USB/IP observer failed again after the controlled P3 PASS. Last fresh
authenticated C3 session-16 health/schema-3 trace was sequence 25 at
`10:06:33Z`, showing GPIO4 LOW, retained zero and timer wake. Windows
`usbipd-win` recorded release of the exact S3 CH343 COM9 at `10:07:57Z`
and socket abort 10053 at `10:07:58Z`, alongside WSL virtual-switch NIC
reinitialization. At `10:13:13Z`, Windows listed S3 BUSID `3-1` as Shared;
C3 remained an unknown descriptor-error USB device. WSL's S3 by-id tty and
capture PID 324978 were stale. The cause of the host socket abort remains
unproven; no post-release Node/Hub application liveness inference is made.
No board, serial or USB recovery operation was attempted. Preserve the sole
capture and commissioned state. A working, operator-approved S3 observer is
required before physical P8; the existing Python 3 build clarification also
remains open. No additional PIR motion is needed now. See [transport
evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/S3_USBIP_CAPTURE_DIAGNOSIS_20261014.md).

## GS-114 controlled C8-P3 physical PASS — 2026-10-14 09:57 UTC

After the operator reattached the exact S3 CH343 `1a86:55d3` /
`5CBC401023`, the existing exclusive capture PID 324978 recovered on the new
WSL `/dev/ttyACM1`. No second reader, board reset or C3 USB operation was
needed. The post-gap stream at `09:49:04–09:49:06Z` showed OPEN RPF admission,
authenticated C3 session 16, health sequence 19 and schema-3 GPIO/sleep trace.
Hub uptime and C3 uptime/health progression through the gap show both target
applications continued operating. The earlier absent heartbeat and Hub
offline UART line were caused by the S3 USB/IP observation loss.

One operator-controlled real AM312 movement window was prompted at
`09:50:56.473Z`, DONE at `09:51:50.807Z`. The authenticated trace measured one
continuous GPIO4 HIGH episode of **28,518 ms**, 1,425 additional HIGH sleep
inhibitions, no sleep entry with GPIO4 HIGH, one additional GPIO wake and one
qualified PIR event. Hub EventKey
`p15:c3-146393c5d158n8:gs114-c8s16q2` produced one durable logical effect;
same-key retry produced none. Authenticated Durable ACK was sent, C3 durable
ACK count increased once and retained events stayed zero. The
`09:56:40.800–09:56:40.855Z` health/trace showed GPIO4 LOW, 11 additional
sleep entries and timer wakes, last wake TIMER, radio restore OK and owner
resumed. **C8-P3 physical behavior PASS.** Historical P3 windows remain
separate. See [case evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P3_CONTROLLED_20261014.md).

The exclusive capture later recorded separate q3 `MOTION`, q4
`MOTION_SUMMARY` and q5 `MOTION` keys at `09:58:48–10:01:33Z`, after the
controlled run and the `09:56:40Z` LOW/timer-recovery sample. Three additional
short GPIO4 HIGH episodes were authenticated. Each key produced one durable
effect and ACK; the physical cause of this later activity is unknown. It is
preserved separately from the q2 P3 stimulus, with no inferred false-alarm
finding.

The C3 installed app SHA-256 remains verified as
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
Exact *running* S3 app hash remains unverified; its source-matched candidate
hash must not be labeled as installed. This is a release-provenance gap. The
only active capture is S3 PID 324978 on the stable CH343 by-id path, currently
`/dev/ttyACM1`; its raw log remains untracked/preserved. The C3 USB descriptor
error is irrelevant to the observed authenticated ESP-NOW liveness and was
not probed. No image, commissioning, power or security state changed.

RPF07/P1/P2/controlled P4/P5/P6/P7 physical PASS evidence remains reused.
P8 physical lost-ACK is next: current S3 diagnostic build has
`GS_HIL_C8_ACK_DROP=OFF`; the existing older ON image is not source-matched.
Prepare a new exact image before requesting installation authorization. The
operator's earlier Python 3 restriction is being clarified before any
ESP-IDF rebuild. P9 ACK/FOTA remain independently BLOCKED on their fixtures;
P10 is GS-149. GS-114 stays In Progress. Current source branch
`feature/r1-commercial-baseline`; source at P3 test was
`d18ed3e52d61a4f0f33f563eceb84f1d2f2294fb` (local/remote matched at
start); context preflight PASS `2026-10-13.001`. Existing untracked files and
raw evidence remain preserved.

## GS-114 S3 USB/IP capture root-cause checkpoint — 2026-10-14 09:40 UTC

The apparent loss of C3 NodeHealth after `08:35:48Z` is an **observation
gap**, not evidence that either application stopped. Windows `usbipd-win`
recorded a transport socket abort (10053) and release of the exact S3 CH343
adapter `1a86:55d3` / `5CBC401023` at `08:37:43Z`, before the next C3
heartbeat was due. Windows now shows S3 BUSID `3-1` `Shared`; WSL retains a
stale `/dev/ttyACM0` and by-id link. The exclusive S3 capture PID 324978 has
received no bytes since `08:35:48Z`. One allowed `FIXTURE_STATUS` attempt
blocked while opening its stale fd and sent no command bytes; no further
serial request is safe on this attachment. Windows also shows C3 USB as
descriptor-error `0000:0002`; this does not prove C3 radio/app state.

The Hub's source checks liveness every 1000 ms against the authenticated
910-second lease. Its missing `online=0` UART line is explained by the broken
S3 observer. C3 health scheduling and sleep deadlines were inspected; no
firmware liveness defect is established. Nearby Windows WSL virtual-switch
events support a host transport disruption; its initiating cause remains
unproven. No firmware source/image, board power, commissioning or security
state changed. The prior one-time C3 reset authorization is exhausted.

Current safe action is S3-only observer recovery after explicit authorization:
account for the stale capture/writer, reverify the exact CH343 serial identity,
reattach only that identified S3 adapter to WSL, establish one fresh reader,
and verify authenticated C3 health/schema-3 trace and OPEN replay admission.
Do not request PIR motion or infer P3 readiness before those observations.
Do not attach the C3 descriptor-error device. P3 remains BLOCKED / NOT RUN;
P8 physical NOT_RUN; P9 ACK/FOTA BLOCKED. Prior RPF07/P1/P2/controlled
P4/P5/P6/P7 physical PASS evidence remains valid and is not being repeated.
P10 remains GS-149. See [diagnostic evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/S3_USBIP_CAPTURE_DIAGNOSIS_20261014.md).

Local and remote HEAD at investigation start were both
`cec251a96b30ca85ed1b256162b2a3f47317258b` on
`feature/r1-commercial-baseline`; context preflight PASS
`2026-10-13.001`. Untracked raw logs, generated components and unrelated
assets remain preserved. Exact running S3 binary hash remains unverified; the
previously verified installed C3 app SHA-256 remains
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.

## GS-114 P3 readiness recheck — 2026-10-14 08:59 UTC

The operator is available for the single controlled P3 movement episode, but
the physical fixture is not ready. Existing S3 capture PID 324978 remains the
sole reader/owner of `/dev/ttyACM0`, configured to append to the run04 log.
The process is alive, but the log has no bytes after the authenticated
session-16 health_seq-4 trace at `08:35:48.465006359Z`; current capture activity
is not proven.

Latest authenticated NodeHealth: session 16 / health_seq 4 at
`08:35:48.443225859Z`; its schema-3 trace reports GPIO4 LOW, no retained event,
timer wake, radio restoration OK, and owner resumed. Configured heartbeat is
300 s; a new report was due around 08:40:48 UTC. No later authenticated health,
trace, event or RPF00 OPEN line was captured. The 910 s lease elapsed at
`08:50:58.443225859Z`. No explicit `online=0` transition is present, so the
evidence does not identify whether the Node, Hub runtime or observation path
stopped. Authenticated liveness is stale and P3 must not start.

No movement prompt, port probe, fixture command, USB/IP attach, reset, flash,
erase, recommission or power change occurred. The one authorized C3 reset has
already been used. Keep the existing S3 reader and commissioned pair intact;
continue passive observation for fresh authenticated liveness, schema-3 trace
and OPEN replay admission. If none returns, identify a safe recovery action
before any further reset. P3 remains BLOCKED / NOT RUN. Preserve prior RPF07,
P1, P2, controlled P4/P5, P6 and P7 physical PASS evidence. P8 follows after
P3; P9 remains fixture-blocked; P10 belongs to GS-149.

Checkpoint: `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, local and remote HEAD
`e4e036a5d3c92bd7d53ce478a5d4e8099cc957b9`; context preflight PASS
`2026-10-13.001`. Existing untracked raw logs, readbacks, generated
components and unrelated assets remain preserved. No source/image changed.
The verified C3 app SHA remains
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; exact
active S3 app SHA remains unverified.

## GS-114 controlled C3 reset recovery — 2026-10-14 08:31 UTC

The operator authorized and completed one C3-only EN/RST reset after the
pre-reset S3 UART snapshot and log were preserved. No new `usbipd attach`, C3
USB serial probe, flash, erase, S3 reset, recommission, or security change was
performed. The user clarified that USB is currently only providing C3 power;
WSL attachment is unnecessary unless a flash is planned.

The existing exclusive S3 capture observed authenticated C3 rejoin as session
16 at `08:15:49.543439605Z`, online liveness at `08:15:50.028801212Z`, RPF00
`PREPARED admission=OPEN` at `08:15:59.778409608Z`, and an authenticated
retirement ACK send of `ESP_OK` at `08:15:59.786565707Z`. Authenticated
NodeHealth/schema-3 traces then arrived at `08:20:49.037–08:20:49.088Z`,
`08:25:48.751–08:25:48.806Z`, `08:30:48.571–08:30:48.626Z`, and
`08:35:48.410–08:35:48.465Z` (health_seq 1–4), matching the configured 300 s
heartbeat. Across these reports, retained
events stayed at zero, GPIO4 stayed LOW with no PIR edges or GPIO wakes, timer
sleep/wakes advanced 10→20→30→40, radio restoration was OK, owner resumed, and no
session-16 offline transition appeared by `08:36:11Z`. This verifies
post-reset application operation and sustained authenticated liveness. The
raw health `reset=1` is retained without using it alone to attribute reset
source: the same value was present before reset, and no C3 boot UART was
captured.

**P3 remains BLOCKED / NOT RUN.** The operator is currently away and no PIR
motion was performed; the quiet GPIO4 trace is only a baseline. When the
operator returns, preserve the current S3 capture and commissioned state,
recheck fresh health/admission, and request one 20–30 s real AM312 stimulus
only when ready. If continuous HIGH cannot be proved, retain BLOCKED. After
P3, P8 is next. P9 ACK/FOTA remain blocked on their fixture/signing
prerequisites; P10 remains separate under GS-149. Previously qualified RPF07,
P1, P2, P4, P5, P6 and P7 evidence remains reused.

Evidence: [C3 reset recovery and P3 handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C3_RESET_RECOVERY_AND_P3_HANDOFF_20261014.md)
and the live S3 capture
`docs/hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/s3_uart_timestamped.log`.
At this checkpoint canonical branch is `feature/r1-commercial-baseline`,
starting HEAD and remote both
`8f911ba502d44e84f9cf61cd9dca8ed9e02d1a4d`; context preflight PASS
`2026-10-13.001`. Existing untracked evidence and unrelated assets remain
preserved. The S3 capture remains the sole reader of `/dev/ttyACM0` (PID
324978); no port operation is required for this
observation-only work.

## GS-114 P3 readiness checkpoint — 2026-10-14 07:55 UTC

The requested P3 motion window was not performed, per operator confirmation;
it is not a physical test. No movement prompt was repeated. Read-only checks
showed local `HEAD` and `origin/feature/r1-commercial-baseline` both at
`27974e0759ac2aadf9886aaeb202d85dcd5998fe`, tracked worktree clean, and
context preflight PASS (`2026-10-13.001`). Existing unrelated untracked assets
and private/raw evidence remain untouched.

The active S3 capture is still PID 324978, the sole owner of `/dev/ttyACM0`
(stable S3 by-id path); its output is the run04 S3 log, whose last line is the
read-only `FIXTURE_STATUS state=idle` at `06:58:28.214244408Z`. No later S3
UART evidence has been captured. C3's stable by-id path resolves to
`/dev/ttyACM1`; sysfs still identifies USB `303a:1001`, serial
`14:63:93:C5:D1:58`, with runtime status `active`, and no process owns ACM1.
This confirms USB enumeration only, not a running or authenticated Node.

The newest authenticated C3 evidence remains session 15 / health_seq 1 at
`06:37:24.484466352Z`, with its schema-3 sleep trace at
`06:37:24.506002952Z`. The Hub marked session 15 offline at
`06:52:38.225783443Z`. The configured heartbeat is 300 seconds and offline
lease is 910 seconds; the lease has expired with no subsequent authenticated
NodeHealth, rejoin or event. Therefore **P3 remains BLOCKED / NOT RUN** and the
fixture is not ready for physical motion. No reset, port probe, flash, command
or commissioning operation was performed. The exact active S3 binary hash
also remains unverified; its candidate build hash must not be represented as
the installed hash.

Next action: recover C3 authenticated liveness through a separately authorized
safe action while preserving the commissioned state and exclusive S3 capture.
Only after fresh authenticated NodeHealth, current schema-3 trace decoding and
OPEN admission are observed should the single controlled 20–30 second P3
movement request be made. P8 remains the subsequent priority; P9 ACK/FOTA
remain blocked on their specific fixtures, and P10 remains GS-149.

## GS-114 C8 resume checkpoint — 2026-10-14 07:18 UTC

Canonical path `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; execution source is `c69960fb064a60c3e6dc52b27d90fbbbe30b560a`.
At the start of this checkpoint update, documentation/evidence commit
`81f4407afa824de8b63b3e5ba27bbf175ffa8604` matched `origin`; context preflight
PASS `2026-10-13.001`, and the tracked worktree was clean. Existing untracked
PWA assets, generated managed components, old failure reports, private logs
and run04 binary/log evidence remain preserved. No destructive Git operation
or firmware/source rebuild occurred.

Windows reports only the intended fixtures attached: C3 `BUSID 3-3`,
`303a:1001`, COM4; S3 `BUSID 3-1`, `1a86:55d3`, COM9. WSL stable links resolve
to C3 `/dev/ttyACM1` (USB serial `14:63:93:C5:D1:58`) and S3 `/dev/ttyACM0`
(USB serial `5CBC401023`). The exclusive S3 capture is PID 324978 and owns
ACM0; ACM1 was unowned. No `usbipd attach` or competing serial probe was used.

The already-built c699 ESP-IDF 6.0.3 pair was hash-verified. C3 application
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530` was
installed app-only at verified active `ota_0` offset `0x20000`; esptool
reported write verification success and partition/otadata reads confirmed
`ota_seq=1`. NVS, commission, event data, security state, partition table and
other OTA metadata were preserved. The C3 later authenticated under Hub session
15 and delivered NodeHealth schema 3 with the physical GPIO/sleep trace. The
S3 log proves trace decoding and a valid `FIXTURE_STATUS` response, but its
exact active binary hash was not read back; the built S3 candidate is
`ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`.

At 06:52:38Z the Hub marked Node session 15 offline after missed health. A
06:58:28Z `FIXTURE_STATUS` returned `idle`. No later authenticated NodeHealth,
GPIO trace or event was captured during the requested P3 movement window, and
operator completion was not confirmed. Do not count it as a controlled test or
PASS. No additional physical reset/reflash/recommission is justified yet.

Evidence reuse ledger: RPF07 PASS; P1 PASS; P2 PASS; P4 controlled q16 retest
PASS (retain the earlier q10–q12 multiplicity); P5 controlled outage/recovery
q24 PASS (retain retry-key observability limitation); P6 PASS; P7 q22 PASS.
The diagnostic change is bounded HIL telemetry, and these prior behaviors were
not repeated. P3 remains BLOCKED on controlled high/low evidence; P8 remains
physical NOT_RUN because the active c699 Hub profile has
`GS_HIL_C8_ACK_DROP=OFF` and the available ACK-drop image is from an older
source checkpoint; P9 ACK/FOTA remain BLOCKED on distinct fixture/signing
prerequisites. P10 remains under GS-149.

Next action: wait for the operator's completion of the already-requested P3
stimulus; no DONE confirmation has arrived. If the motion occurred, inspect
the existing S3 log before any new stimulus. If no authenticated data appeared
after confirmed movement, preserve that first failure and diagnose Node
wake/rejoin before asking for any reset or additional motion.

P8's current-source S3 image is not available: the c699 Hub build has
`GS_HIL_C8_ACK_DROP=OFF`, and the older ACK-drop artifact is not source-matched.
The registered `gs114-s3-rpf-diagnostic-build` Make target invokes
`python3 scripts/build_gs114_fixture_pair.py`; respecting the operator's
instruction not to use Python3, no rebuild or flash was attempted. P8 requires
a supported build path that avoids Python3 or a changed operator constraint,
then exact image/slot verification before any installation. P9 ACK/FOTA remain
blocked on their fixture/signing prerequisites. No P1/P2/P4/P5/P6/P7 retest,
broad suite rerun or FOTA operation is justified at this checkpoint.

Jira GS-114 comment 10873 records the install/trace milestone. The consolidated
documentation commit `81f4407afa824de8b63b3e5ba27bbf175ffa8604` was pushed and
remote-verified. GS-114 remains In Progress; do not start GS-116/GS-130.

## GS-114 C8 resumed execution checkpoint — 2026-10-14 05:20 UTC

Canonical path `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting HEAD `988fa44ee1207ed67a3a253a5eb2c9dc7813277b`;
context preflight PASS `2026-10-13.001`. The source/evidence modifications
listed by `git status` are uncommitted; prior untracked P5 evidence, private
historical logs, ignored target builds, PWA and generated managed components
remain preserved. No destructive Git or hardware operation occurred in this
checkpoint.

## GS-179 PostgreSQL and caregiver software checkpoint — 2026-10-19

On the existing canonical branch, GS-179 now has an opt-in TEST_ONLY host
composition that uses the application-controlled TLS listener, existing
verified Hub client-certificate and current-ownership checks, existing GS-148
COMMITTED API, and the production-model caregiver projection on isolated local
PostgreSQL. The final registered E2E run used the same per-test PostgreSQL
schema for caregiver accounts/sessions and Hub monitoring data. The shared
caregiver browser received the same authenticated event and Hub-decision rows.
Synthetic scenario-run records remain a separate source. The final registered
`gs179-postgres-e2e` stage passed 34/34. The focused SQLite GS-178 caregiver
browser scenario passed after the Home monitoring assertion was added; the
prior full SQLite regression passed 29/29. In the final PostgreSQL run, the
caregiver browser passed 17 assertions including Home `COVERED`, source
`CURRENT`, and explicit host-simulation provenance. The earlier standalone
PWA browser suite passed 3 tests / 92 assertions. Traceability passed 22/22
mapping checks (216 features, 257 source modules and 25 physical cases).
Detailed command, source fingerprint, test log hash, limitations, aggregate-gate
failures, and hosting recommendation are in
[`GS179_POSTGRES_CAREGIVER_E2E_20261019.md`](../exec-plans/evidence/GS179_POSTGRES_CAREGIVER_E2E_20261019.md).

This is host TEST_ONLY evidence. The public Render service was not modified and
still cannot provide a verified Hub TLS peer identity to WSGI; live deployment
and database networking remain blocked pending explicit host/account, DNS/TLS,
secret, fixed-egress allowlist, and deployment authorization. No actual Android
phone, firmware target, sensor, production credential, customer Home, physical
fixture, or commercial service was exercised. GS-179 remains In Progress;
GS-148 and GS-177 keep their current statuses; `product_status=PARTIAL` and
physical qualification stays NOT_RUN. The final source-bound rerun passed
34/34 in 202.324 seconds (202.999 seconds total gate runtime). Its ignored
local report is
`code/evidence/validation_framework/postgres-integration-1792435470522033688/report.json`;
it binds to source fingerprint
`366a503df78677b4ce3d6ff13981cfce822afce705f59c444b81ae8d1d54413e` with
`source_unchanged=true`, and the stage log SHA-256 is
`27af77200aa8fc841660aff65853ae27a83472c6ac368ed97226175083cec299`. The
same run also rejects a caregiver account absent from the durable Home roster
and keeps a roster `PRIMARY` account at caregiver privilege. The PostgreSQL
fixture was stopped after validation.

The existing GS-177 Android workflow completed successfully for this pushed
commit: GitHub Actions run `39305728185`; PWA browser 92/92; registered API
13/13, Android dashboard 6/6 and voice-prototype 19/19. The CI-built
`in.gharsajag.caregiver` v`0.4.0-connected-lite-staging` artifact (ID
`12213208184`) is 2,909,502 bytes with SHA-256
`1e2a862239d57ac70d71783b215dd358da80c71c87b9386daf3f1d595a33b7ea`. Its v2
signature is runner-debug-key signed, not pilot signed. This CI result does not
establish live Render monitoring, APK update continuity, or owner-phone use;
those remain unqualified. Render was not changed.

The physical pair remains commissioned on C3 app
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3 app
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. Stable
paths remain C3
`/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00`
and S3
`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00`. The sole S3
reader is PID 302734 and owns only S3; no C3 reader is open. USB-only power and
AM312 3.3 V/GND/GPIO4 remain the previously operator-confirmed arrangement.
No board has yet received the trace image.

P5 run03 now PASSes: during Hub-only USB outage the real AM312 event q24 was
retained, then admitted once after authenticated session-6 rejoin with RPF00
OPEN; Hub durable state changed once, Durable ACK send succeeded, and NodeHealth
confirmed reset unchanged, retained=0 and durable_ack +1. Retry identity is
inferred from the single new pending event because the C3 native USB console is
silent in light sleep; preserve that limitation and the earlier run02 capture
gap. P6/P7, P1/P2 and controlled P4 retest remain PASS on the installed pair;
P3 remains BLOCKED pending GPIO4 HIGH/sleep trace; P8 remains physical NOT_RUN;
P9 ACK/FOTA remain fixture-blocked; P10 remains separate under GS-149.

A TEST_INFRA_ONLY observer is implemented: C3's `GS_BAT_C8_PHYSICAL_WAKE`
profile records sampled GPIO4 HIGH episodes, sleep inhibition/race counts,
entry/wake GPIO levels, radio restore and owner resume in an optional bounded
authenticated NodeHealth schema-3 trace. The S3 commissioning fixture prints
the trace. Normal C3 builds exclude the recorder object and owner-resume call.
Node/Hub/contract registered component stages pass, including 1,483 C++ checks,
72 BAT-C8 checks and Hub storage ASan/UBSan. Aggregate gates exit 1: Node and
contract on P0 `product_status=PARTIAL`/physical `NOT_RUN`; Hub also retains the
known `hub-journal-migration-host-test` failure (`clean migration commits`).
None is described as a full-gate PASS.

Next exact action: commit and push only the scoped source, test mapping and
current GS-114 evidence updates; build the source-matched C3/S3 commissioning
pair with ESP-IDF 6.0.3 and verify the complete profile/hash manifest. Then
stop PID 302734 after preserving its final log, verify exact chips/MAC/flash and
ownerless stable ports, flash only the authorized two R&D fixtures, restart one
S3 capture, and run P1 then P3 with actual AM312 motion. Do not claim P3 until
authenticated trace shows HIGH/inhibition and LOW recovery without a HIGH sleep
entry, reset or wake storm. GS-114 stays In Progress.

## GS-114 resumed C8 execution checkpoint — 2026-10-14 03:58 UTC

Controlled P7 now PASSes. The operator performed one real AM312 movement
episode during the requested window after Hub-only reboot. Hub booted at
03:34:27.008Z, authenticated Node rejoin advanced to session 4, and RPF00
admission remained OPEN. First post-reboot key q22
`p15:c3-146393c5d158n8:gs114-c8s1q22` produced one durable logical effect;
two same-key retries were idempotent. Authenticated retirement ACK send
returned `ESP_OK`; NodeHealth at 03:57:15.413Z confirmed reset=11, retained=0,
durable_ack=22, pir_ok=27 and gpio_wakes=27. P6 also PASSes with the full S3
boot banner captured. See [GS-114 P6](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P6.md)
and [GS-114 P7](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P7.md).

P5 remains BLOCKED/inconclusive from its prior capture gap and is next for a
controlled retest using the existing reconnect-aware exclusive S3 reader.
P3 remains BLOCKED for direct GPIO4 HIGH/sleep-inhibition evidence; P4 passes
on its controlled retest while the earlier q10–q12 multi-key result remains
unexplained. P1/P2 PASS. P8 is still physical NOT_RUN pending installation of
the isolated ACK-loss image set after exact-device/profile verification; P9
ACK-window and signed FOTA subcases remain blocked by missing fixtures/images.
RPF07 physical retest remains PASS. No source/image change, reset, reflash or
recommission occurred in this checkpoint. GS-114 remains In Progress; GS-149
P10 current measurement and other GS-146 evidence remain separate.

## GS-114 resumed C8 execution checkpoint — 2026-10-14 03:25 UTC

The R&D pair remains on its existing commissioned images; no source/image
change, reset, reflash or recommission occurred. The operator completed another
continuous real-motion P3 attempt. Hub events q17–q20 were four distinct keys,
each durably accepted once, same-key deduplicated, and ACKed. Authenticated
NodeHealth at `2026-10-14T03:25:04.945156252Z` (session 3, health_seq 120)
reported reset=11, `pir_raw=0`, retained=0, durable_ack=20, pir_ok=25,
gpio_wakes=25, sleep_entries=1273 and timer_wakes=1248. Relative to health_seq
119 before the stimulus, GPIO wakes and accepted PIR events each increased by
four, while sleep entries increased by 14 and timer wakes by 10.

P3 remains BLOCKED for held-HIGH sleep-inhibition qualification: C3 native USB
UART/direct GPIO4 did not expose HIGH during movement, and aggregate counters
cannot identify sleep entries relative to the pin level. Post-stop LOW and
timer/sleep recovery are observed. Four distinct EventKeys during continuous
movement are preserved as unexplained physical event multiplicity, not
same-key duplicate effects. See [C8-P3 evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P3.md).

Current physical statuses: RPF07 PASS; P1/P2 PASS; P3 BLOCKED; P4 controlled
retest PASS with the original q10–q12 failure retained; P5 BLOCKED/inconclusive;
P6 PASS; P7 requires a new Hub-only reboot followed by a controlled first real
motion; P8 physical NOT_RUN; P9 ACK/FOTA BLOCKED. P5 requires a reconnect-capable
exclusive S3 log reader before Hub power removal; the existing reader does not
reopen after USB disconnect. Preserve installed image hashes C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. No C3
reader is active. Keep GS-114 In Progress; P10 remains separate under GS-149.
Next, repeat the Hub-only P6 reset needed to establish a fresh controlled P7
first-event window, then run P7 after authenticated rejoin. Before the later P5
Hub power-removal test, replace the S3 observer with a reconnect-capable single
reader and verify the replacement does not reset the Hub.

## GS-114 resumed C8 execution checkpoint — 2026-10-14 03:13 UTC

Canonical path `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; run03 code checkpoint
`72716c141a788b251e6b630f4684df12028ea847`. q15/q16 evidence and handoff
updates were committed and pushed as `610c3f3d754ef647d9b0ab0faa284b0465928470`,
`9664b4b9848a67f290dabfe2108c8dd06051675c`, and
`0ae61bd2234da0af8fb1a636cc58f4ef4380347d`; local and remote matched at the
last verified checkpoint. Context preflight passed `2026-10-13.001`. The
tracked tree was clean after those commits. Existing untracked PWA,
managed-component and historical physical-evidence paths remain preserved.
The untracked raw S3 capture was owned by reader PID 283926 at 03:06 UTC. No C3
reader was present at that check; do not open another S3 reader or stop the
active capture.

The installed C3/S3 pair remains unchanged and commissioned. Authenticated
NodeHealth at `2026-10-14T02:53:43.472786229Z` was Hub session 3 / health_seq
115, reset 11, retained 0, durable ACK 14, accepted PIR 19, GPIO wakes 19,
sleep entries 1212, timer wakes 1193, last wake TIMER. The first physical
GPIO/PIR-path event after the Hub reboot was q15
`p15:c3-146393c5d158n8:gs114-c8s1q15`; it was durably accepted once, same-key
deduplicated and ACKed. NodeHealth at `02:58:47.560721096Z` (health_seq 116)
confirmed retained=0 and durable_ack/pir_ok/gpio_wakes each incremented once.
The event's external physical trigger and GPIO assertion time are unknown, so
P7 remains BLOCKED for controlled stimulus attribution/timestamp evidence. To
run the controlled first-event P7 case requested by the owner, repeat Hub-only
P6 and then generate the first real PIR event after that reboot; q15 itself
already consumed the first-event position after the previous P6.

The operator performed one brief controlled movement for the P4 retest after
the q15 chain had completed. q16
`p15:c3-146393c5d158n8:gs114-c8s1q16` produced one authenticated Hub durable
effect, same-key duplicate suppression, successful Durable ACK and authenticated
Node retirement; NodeHealth at `03:05:23.259112457Z` (health_seq 117) confirmed
retained=0, durable_ack=16, `pir_ok=21`, `gpio_wakes=21`, reset=11. No extra key
appeared during the three-minute post-DONE quiet window. P4 controlled retest
PASS; retain the original q10–q12 multi-event FAIL and its unresolved cause.
No source/image change, reflash or reset occurred.

While waiting, ESP-IDF 6.0.3 built the matched P8 target pair offline under
`code/build/gs114_c8_p8_20261014/`. C3 app SHA-256 is
`5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`; S3 app
SHA-256 is `f94192a7c59fa1a7221a7dc4a8394c1bd8c448c2009553e35dfed2f074eccd08`.
The S3 profile uses `GS_HIL_CONTROL=OFF`, commissioning ON, isolated P8 ACK-drop
ON, 16-MiB flash, octal PSRAM configuration, and `ota_0`/`ota_1`/`gs_outbox`/
`gs_state`. Both builds exited 0; `make -C code c8-ack-drop-gate-host-test`
passed 16 checks. Neither image was flashed. Offline image-info checks matched
the C3/4-MiB and S3/16-MiB target types and verified checksums. The S3 fixture
profile suite passed 12/12; traceability passed for 175 features/205 modules/15
physical cases and its 19 tests passed; the physical catalogue check passed for
99 cases with no device access. An attempted `make -C code validation-hub` was
stopped before `host-build` could invoke Python per the user's instruction; its
16-check ACK-drop gate and 12-check S3 fixture-profile stage passed, but the
Hub validation target is incomplete (exit 130), not PASS. Full artifact/profile
hashes and commands are recorded in the [GS-114 P8 target evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P8.md).

Physical dispositions: RPF07 PASS, P1 PASS, P2 PASS, P3 BLOCKED, P4 PASS on
controlled retest (initial trial FAIL retained), P5 BLOCKED/inconclusive, P6
PASS, P7 BLOCKED for missing controlled stimulus attribution/timestamp after
q15's observed and retired first post-reboot event, P8 physical NOT_RUN, and P9
ACK/FOTA BLOCKED. P8 installation requires presenting the exact prepared
image/partition hashes for operator confirmation before flashing; no P8/P9
image has been installed. The next physical case is P3, which needs a real
sustained-HIGH stimulus and an authenticated NodeHealth sample during the
episode; the current P3 evidence remains blocked without a verified high-level
interval. Keep GS-114 In Progress; P10 remains separate under
GS-149. Jira GS-114 comment 10862 records q15 retirement, the q16 controlled P4
retest and both evidence commits. GS-114 remains In Progress; no issue workflow
status changed.

## GS-114 resumed software checkpoint — 2026-10-13 UTC

Jira GS-114 comment 10800 and the pause handoff were reconciled. Canonical
local and remote HEAD were both `93935e345a29e3b119f460fda5e9294477b6f798`
at resume, branch `feature/r1-commercial-baseline`; preflight PASS. All
uncommitted repair work and prior evidence were preserved. The old stuck S3
esptool process exited, but neither `/dev/ttyACM0` nor `/dev/ttyACM1` exists
in WSL. No port was reopened or hardware operation performed on resume.

All nine repair artifacts have matching byte size and SHA-256; the repair
manifest was corrected to reflect the actual 1,889,280-byte S3 app and its
embedded new C3 image. `make validation-hub` completed: 38/40 stages PASS;
the known journal migration test FAIL and product P0 `PARTIAL` classify the
gate FAIL (exit 2). Affected checkpoint, fresh-install, board-stack, storage
correctness and sanitizer stages PASS. `make validation-contract` completed
33/34 stages PASS; only product P0 `PARTIAL` makes that gate FAIL (exit 2),
while its contracts and affected component stages PASS. Both receipt reports
are identified in the execution handoff.
Physical repair retest and P1–P4 remain NOT_RUN/BLOCKED pending restored USB,
renewed exact-board identity/power/wiring checks and the operator's requested
pre-flash confirmation of the repaired image hashes. See the
[consolidated GS-114 execution handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).


## GS-114 paused at physical repair checkpoint — 2026-10-13 UTC

The operator requested a logical pause before the session limit. The canonical
worktree remains `/home/udaybhan/projects/Ghar_sajag_r1` on
`feature/r1-commercial-baseline`; starting local HEAD was
`93935e345a29e3b119f460fda5e9294477b6f798`, with no branch switch or
destructive Git operation. Context preflight PASS `2026-10-13.001`. The existing
nine unrelated untracked entries and prior failure evidence are preserved.

The exact authorized C3 (`14:63:93:c5:d1:58`, 4 MiB, COM4/ttyACM0) and S3
(`7c:4f:ad:b7:2a:20`, 16 MiB/8 MiB PSRAM, COM9/ttyACM1) were ROM-identified,
clean erased, flashed and verified with the original manifest. Both booted;
`GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` produced authenticated rejoin,
session 2. At 12:04:48.028 UTC the fresh S3 closed admission with `RPF07
SELECTED_CHECKPOINT_MISSING`. Phase A therefore FAIL; P1–P9 have no current
physical PASS. The [execution report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
contains redacted first-failure logs and the verified install receipts.

A scoped Hub owner-cache refresh fix and production-code regression are in the
canonical tree. Focused checkpoint and fresh-install host tests, feature
coverage, target C3/S3 fixture build and `git diff --check` PASS. The full
`validation-hub` run was stopped for this pause after reproducing the known
`hub-journal-migration-host-test` failure; it is not a gate PASS. Rebuilt repair
images (C3 `89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`,
S3 `c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`)
are hash-checked but **not installed**. No repair erase/write occurred.

At pause, a read-only S3 `flash-id` probe was hung in uninterruptible kernel
I/O after its parent was terminated. S3 runtime state must be treated as
unknown; do not infer stable serial observation or start qualification from
this point. Next action on resume: check that probe/USB state first, then
reidentify both exact chips/ports and image/profile hashes, perform the
authorized controlled repair installation if safe, recommission with the
supported fixture APIs, and physically retest healthy replay-fence admission
and reliable dual logs before P1–P4. Preserve separate P5–P9 operator
checkpoints. GS-114 stays In Progress; GS-149/GS-146/GS-115 remain dependent.

The older GS-114 sections below describe prior checkpoints; this section is
the current pause/resume state.

## GS-114 clean R&D execution — 2026-10-13

Active task: actual C8 P1–P9 on the existing commissioned R&D pair, under
GS-114 comment 10732 and the user's execution instruction. Old experimental
flash, enrollment and pending events may be deliberately erased/recommissioned.
Earlier preservation-first gates below are superseded for these two fixtures;
previous redacted failure evidence remains preserved. No spare pair is needed.

Startup canonical/local/GitHub HEAD `5ee96fd24b4a82b2a11b928cb40f2638eaee9616`,
branch `feature/r1-commercial-baseline`; tracked clean, original nine untracked
entries preserved; context PASS `2026-10-13.001`. GS-148 Option A and GS-150
source/artifacts reconciled without repeating their completed campaigns.
Current fingerprint `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`
matches the retained commissioning-compatible C3/S3 fixture build. Full
bootloader/partition/otadata/app hashes and fresh blank outbox are recorded in
[the execution report and preparation manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).
ESP-IDF 6.0.3/esptool 5.4.0 activated; offline image/profile/partition checks and
host mount of the component-pinned empty LittleFS image PASS. No runtime source
change, release/current campaign or repeated GS-148 fault injection.

After the operator reported "boards connectd", read-only OS inventory matched
C3 USB serial `14:63:93:C5:D1:58` at `/dev/ttyACM0` (COM4, BUSID 3-4) and
S3 UART serial `5CBC401023` at `/dev/ttyACM1` (COM9, BUSID 3-1), both attached
to WSL, with no other serial reader. Actual silicon/MAC/security, present safe
power and AM312 wiring still need confirmation. **No port opened, probe/reset,
erase/write, commissioning or physical test yet.** Exact Phase A confirmation
requested under user section 3.6 / GS-114 10732; P1 NOT_RUN, P2–P9 BLOCKED.

Next: confirm exact board/power/wiring/Phase A operation, probe identities and
security on the stable named interfaces, stop on mismatch; then supervised clean
erase/write/verification, boot and test-only secure commissioning. Establish
stable independent timestamped capture before actual P1–P4 motion. A documented
setup reset is permitted; unexpected measurement resets are failures. P5–P7
power/reboot, P8 postcommit ACK loss/per-key ledger and P9 signed FOTA require
their separate operator checkpoints. Prior USB reset/replay-fence faults remain
unresolved historical regressions; clean fresh-install evidence cannot prove
recovery of the discarded old state. GS-114 stays In Progress; GS-149/GS-146 and
measured GS-115 decisions remain separate, with no invented current/endurance.

## GS-114 C8 physical readiness — 2026-10-13

Historical offline checkpoint, superseded only where GS-114 10732 and the active
clean R&D execution above remove experimental-state preservation prerequisites.

Offline review at canonical/GitHub `ca87e2cd058586d9c7231df9ab313c4b237f8085`,
context preflight PASS, found current source-matched C3/S3 fixture binaries and
RPF00–RPF08 but no installed-image/storage provenance, verified non-resetting
C3 observer, safe state-preserving S3 app installation, or healthy physical
replay-fence admission. The saved run stopped on `USB_UART_CHIP_RESET` and
`admission closed`; no second spare pair is confirmed. [The dated readiness
report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_PHYSICAL_READINESS_20261013.md)
defines a preferred separately confirmed disposable-pair route and gated
fallback for the commissioned fixture. **NO-GO** for P1–P9 now; P1 NOT_RUN,
P2–P9 BLOCKED. Next action is separate approval for identified-fixture
power-off visual inventory; no physical action, software rebuild, flash or
serial access occurred here. GS-114 stays In Progress; P10 remains GS-149.

## GS-148 Option A software delivered — 2026-10-13

GS-148 10688/10690 and GS-145 10689 approve bounded native-v1 recovery and
software validation. GS-D033 locks corrected recovery in both supported S3
images; exact signed pair and physical OTA remain pending. Start baseline local
and actual GitHub `19ec67c365e1bdea8fce61fb46f481f407fa42b9`, canonical branch,
tracked clean, nine preserved untracked entries. Other observed session writes
only separate dashboard worktree; canonical writer is exclusive for GS-148.
Context updated to `2026-10-13.001` for the approved policy before source work.
[Implementation handoff](../exec-plans/evidence/R1_GS148_OPTION_A_20261013.md)
records exact source, 59 primary fault cuts, 24 authority negatives, 22 actual
old/corrected reader checks, real C3/S3/API projection, ASan/UBSan, framework
and source-traceability PASS. Frozen fingerprint
`c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`
has Hub 38/40, Node 23/24 and contract 33/34 PASS. Only historical journal
migration and product P0 PARTIAL stages fail. Board-stack E2E passed eight cases;
ESP-IDF 6.0.3 S3 production and GS-114 fixture profiles compiled. Old reader
availability on interrupted first events remains a known FAIL_CLOSED limitation;
both commercial supported images must include the corrected reader (GS-D033).
The concrete signed pair, physical reboot/OTA/rollback, lifetime storage capacity
and full release qualification remain NOT_RUN/BLOCKED. GS-148 In Progress;
GS-145 To Do; no status transition. Next action is separate image/physical and
remaining commercial lifecycle qualification under its own authorization.


## GS-148 / GS-145 first-event design review — 2026-10-13

**DESIGN_READY_FOR_APPROVAL**, documentation only. Reviewed actual canonical
local/GitHub HEAD `371a560f04b99bce8fd86e58739a75184b555b55`, clean tracked
tree, context PASS `2026-10-11.001`, current code and Jira 10678–10682.
[Focused decision report](../architecture/GS148_FIRST_EVENT_RECOVERY_DESIGN_20261013.md)
recommends Option A: the existing authenticated zero-boundary application checkpoint,
selected first identity/body and native owner/root/fence checks establish one
pending transaction. Original authenticated retry finishes ordinary v1
publication/checkpoint before Durable ACK. A narrowly proven interrupted empty
checkpoint may be completed using its current format. No new persistent bytes,
keys, partitions or installation manifest; all proposed logic remains unimplemented.

This replaces the earlier assumption that the 116-byte genesis candidate is
necessary for the demonstrated first event. It does not weaken current failure
checks: standalone missing-head, populated history, missing/corrupt checkpoint,
owner/epoch and inconsistent witness cases still fail closed. Native epoch-1
scope is explicit; future transfer/incarnation remains separate.

S3 uses the shared Hub-to-C3 FOTA sender, with rollback configured but no inspected
Hub self-OTA receiver or pending-image health confirmation. Signed S3 rollback
is not qualified. Recommend corrected v1 recovery in both supported R1 images;
old engineering readers retain their existing fail-closed initial-pending limit.
Image support approval and qualification cannot be inferred from unchanged bytes.

No production code or validation registry changed; no completed test campaign
repeated. New cases PROPOSED_NOT_EXECUTED; documentation checks only. Prior
P0/P1/P2 PARTIAL, historical migration FAIL and product P0 PARTIAL remain.
Physical NOT_RUN/BLOCKED; release NOT_RUN. GS-148 In Progress, GS-145 To Do;
GS-152 Done. No issue transition or hardware action. Final docs commit/actual
remote equality and Jira IDs are recorded in dated delivery comments.
Next action: approve the bounded design and supported image recommendation,
then separately authorize its ordered implementation package. Stop after review.

## GS-148 bounded P0/P1/P2 correctness checkpoint — 2026-10-13 (started 2026-10-12)

Delivery: architecture `2b17924be86c7ce78f8e1ec1c7c03b402fc48a6c`, tested source `23636a921409b52afe56823ca4302d5fb09683cb`; normal push and actual
GitHub/local HEAD equality verified, tracked tree clean before this final Markdown
handoff. The dated GS-148 delivery comment records the final handoff-only descendant
HEAD. Source fingerprint `7fd270f6cbd5f94f520945cd218d2bdddc7b4d77ab24c31a4936932ad4973250`
remains identical. Hub 36/38, contract 31/32 and Node 22/23 stages PASS; only
migration and/or product P0 PARTIAL fail. Board eight cases PASS; new normal /
ASan / UBSan fault tests, production and GS-114 target builds, framework and
traceability PASS. See the full receipt/count/hash table in the package handoff.

GS-152 is Done; bounded work resumes from canonical `77e29d4` on
`feature/r1-commercial-baseline`, context PASS `2026-10-11.001`. Start comment
10594 records the authorized software scope. The approved Sol direction is
integrated with its historical source audit; D-A–D-M remain OPEN and no new
LOCKED requirement/context version is introduced.

Implemented: exact next-reducer/identity/body immediate admission checks before
identity selection; active/fallback/witness report-bank protection; cross-epoch
witness refusal; equal-generation checkpoint conflict rejection, permitting
nonce-different identical authority. Permanent production tests cover 28 cuts,
two-boot exact retry/original context, conflicting payload/lost ACK, repeated
capacity refusal, all three bank pins and the existing 64-KiB reducer boundary.
Final component/build/fixture/sanitizer/framework results and delivery checkpoint
are in the [current package handoff](../exec-plans/evidence/R1_GS148_P0_P1_P2_20261012.md).

**PARTIAL:** complete first body without its first v1 event head remains fail
closed. The genesis/rollback format proposal is unimplemented pending approval.
Immediate checking does not qualify lifetime completion/metadata/COW/GC reserve.
Historical migration FAIL and product P0 PARTIAL remain visible. Physical
NOT_RUN/BLOCKED; release approval NOT_RUN. GS-148 stays In Progress; other
requested issue statuses are unchanged. Stop after this package. Next action:
review/approve genesis compatibility and owning commercial prerequisites, then
authorize a separate package. Do not resume the original audit or hardware.

## GS-114 Part 2D — fixture-compatible S3 RPF diagnostic build — 2026-10-12

At source HEAD `e31e8ef6314abcc777eb5979c3d33939cdb7b296` (source fingerprint
`f54e3162160d4f9e96a61ed60575f434c2a33c73a866b85789cd5bce610e0dce`), the
new explicit `make gs114-s3-rpf-diagnostic-build` target completed successfully
with ESP-IDF 6.0.3. The standalone local S3 app is
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/build/gs114_fixture_pair/build-kvi2pcxe/s3/gs_r1_s3_hub.bin`,
1,879,392 bytes, SHA-256
`48d08726d3acb686466fc8ef056609efe2b0148719ea89943bbe3e48a72c1f09`; it fits
the candidate 4 MiB OTA slot with 2,314,912 bytes free. The build checks the
Part 1 `GS_HIL_COMMISSIONING=ON`, broad S3 HIL-off, 16 MiB/Octal PSRAM and
`gs_outbox`/`gs_state` profile; all RPF00–RPF08 diagnostics and bounded fixture
commissioning strings are present. It decodes the compiled partition table and
confirms it matches the candidate CSV. The generated full-device flash bundle
is not authorized for deployment.

Focused validation: fixture/profile test 9/9 PASS; validation framework
39/39 PASS; seven focused Hub retirement/checkpoint/storage/fresh-install/
rejoin/association/protocol targets PASS. The historical GS-148 journal
migration failure remains an independent known FAIL and was not rerun or
changed. No production runtime/storage/security C++ source changed; no physical
device or data was accessed. The new S3 image is not installed. Actual fixture
image, active OTA slot, partition contents, eFuse state, retained events and
safe rollback remain unverified; first-boot replay-fence reconciliation can
write persistent state. Deployment and GS-114 physical qualification remain
**BLOCKED / NO-GO** pending separate preservation review and installation
authorization. The exact comparison, successful build JSON and caveats are in
[GS-114 Part 2D evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2D_FIXTURE_DIAGNOSTIC_BUILD_20261012.md).

The Part 1 provenance note below is corrected: its later retained local app
binaries match `physical_results.json`, while the `fixture_pair_report.json`
at the same paths records earlier different hashes and is stale relative to
those files. Neither source is physical flash readback. No previous physical
PASS is upgraded.

**Part 2D delivery checkpoint:** commit `2545e9a94e6fc87f43ec8a3b672e88dbb1fcbbae`
is pushed to `origin/feature/r1-commercial-baseline`. Local and remote HEAD
matched at verification. No fixture deployment or physical qualification was
performed. The pre-existing untracked S3 `managed_components/` and redacted
Part 1 evidence remain unmodified; the separate GS-152 worktree remains
isolated and unchanged.

## GS-114 Part 2C — supervised diagnostic deployment plan — 2026-10-12

Planning-only review was performed at canonical source/remote checkpoint
`cbbf12d1b4fba9cd1e38730685ccede32f23f558` on
`feature/r1-commercial-baseline`. Context preflight passed. No USB, serial,
target storage, build, or physical device was accessed. See the dated
[GS-114 Part 2C deployment plan](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2C_DIAGNOSTIC_DEPLOYMENT_PLAN_20261012.md).

The saved GS-148 diagnostic S3 image hash was verified locally and contains
RPF stage strings, but it is not suitable for the commissioned fixture:
`GS_HIL_COMMISSIONING=OFF` does not use the fixture's persisted development
identity, and its packaged partition table is the development `gs_journal`
map, not the fixture's `gs_outbox`/`gs_state` map. Its complete flash bundle
also rewrites bootloader, partition table and OTA metadata and resets the
target. The current source fingerprint differs from the report fingerprint.
There is no proven S3 app-only update path, storage backup/restore, or
reset-safe two-board observation route. Normal rejoin may attempt replay-fence
publication, which can write LittleFS; this diagnostic is not application-level
read-only. Therefore deployment, observation and real PIR qualification remain
**NO-GO**. The physical failure root cause remains unknown.

The saved Part 1 C3/S3 application artifacts are present in the ignored local
fixture-pair build directory. Their hashes match Part 1 `physical_results.json`,
but the colocated `fixture_pair_report.json` records earlier different hashes
for those same paths and is stale relative to the retained binaries. Neither is
flash readback; installed image, partition table, OTA slot and live persistent-
state provenance remain unknown.
The deployment plan records this distinction and the required separate
approval gates. GS-114 planning result is in Jira comment 10504; the diagnostic
profile incompatibility is cross-referenced to GS-148 in comment 10505. The
deployment plan is documentation-only and records the exact source checkpoint,
offline artifact checks and future approval gates.

Plan/documentation commit `c077bee73befac3afc9bbdb50f9234ac46fe2b18` was pushed
normally; local HEAD and `origin/feature/r1-commercial-baseline` matched at
that delivery checkpoint. Only the plan and this work-state file were staged.
The pre-existing untracked S3 `managed_components/` and redacted fixture
evidence remain untouched.

GS-114 remains In Progress; GS-148 remains OnHold; GS-145 remains a separate
fresh-format durability gate. Next action is user review of the state
preservation strategy, corrected fixture image profile, installation method
and reset-safe observation candidate. No hardware action is authorized by the
plan. Preserve the untracked S3 `managed_components/`, all redacted fixture
evidence, and the isolated GS-152 worktree.

## GS-148 narrow replay-fence diagnostic checkpoint — 2026-10-12

Authorized by GS-148 comment 10499. On the canonical
`feature/r1-commercial-baseline` branch, production Hub replay-fence failure
diagnostics now distinguish selected-state/checkpoint recovery, witness
prevalidation/publication/readback, and runtime binding stages with sanitized
stable codes. Production-code host fault tests cover valid Prepared/Duplicate
reports, failure boundaries and restart selection. The error remains fail
closed and does not send a retirement-report ACK. No storage format, ownership,
durable-before-ACK, event identity or recovery policy changed.

Focused Hub/Node retirement, outbox, checkpoint, rejoin, framework and
traceability tests passed; the checkpoint suite also passed ASan/UBSan. Clean
ESP-IDF 6.0.3 paired C3/S3 production-profile builds passed (C3 934,192 bytes;
S3 1,870,944 bytes) with matching embedded Node image provenance; no flash
target ran. See the dated [GS-148 replay-fence diagnostic evidence](../exec-plans/evidence/R1_GS148_REPLAY_FENCE_DIAGNOSTIC_20261012.md)
for image hashes and the exact target report. The historical Hub journal
migration assertion remains an independent FAIL. No physical devices, USB,
serial, storage or HIL interfaces were accessed. Physical root cause remains
unknown and GS-114 remains physical NO-GO.

The storage reconciliation confirms the old classic ESP32 fixed 128-slot
NVS journal is not the active S3 outbox implementation. S3 uses bounded
segmented LittleFS plus checkpointed identity/completion state; its current
candidate capacity, retention and physical endurance are not qualified. This
checkpoint does not start GS-148 P2-E/P2-F. After final validation and push,
GS-148 returns to OnHold. Preserve the untracked S3 `managed_components/` and
existing redacted GS-114 evidence. Next action: review this diagnostic and
authorize a separate, state-preserving physical diagnostic plan before any
GS-114 retest.

## GS-114 Part 2B — software-only root-cause investigation — 2026-10-12

Investigation source HEAD was `7c1fee29e17fc3fe12c840e0afef5fa6b7217b68`;
canonical local and origin refs matched before the tooling/documentation
checkpoint. No board, USB or serial interface was accessed. The saved C3
`USB_UART_CHIP_RESET` is most likely associated with opening its native USB
Serial/JTAG console: pySerial 3.5 applies DTR/RTS after `os.open()`, and prior
fixture notes document monitor-attachment resets. Exact causation/timing is
not proven by the captured logs. The HIL-A06 classifier was corrected and its
registered host test now fails on this marker.

The S3 replay-fence error occurs while handling an authenticated Node
retirement report after rejoin/epoch advertisement. The source emits this error
only after report application returned Duplicate or a Prepared snapshot passed
NVS checkpoint recovery/reference verification. The later selected-state or
reducer-checkpoint reload, LittleFS fence validation/publication/readback, or
runtime bind remains the unresolved step. Admission correctly fails closed
and the report ACK is not sent on this error path. A C3 reset/rejoin may have
triggered the report, but the report fragments are not directly observed. This
is not the separate historical GS-148 journal-migration assertion failure.

Host-only `make gs130-hil-runner-test` passed 17 tests, `make
validation-framework-test` passed 39 registration/failure-propagation tests,
and `make hub-runtime-checkpoint-host-test` passed its synthetic publication-
cut, recovery and mismatch checks. These tests do not reproduce the fixture's
persistent state. Production security/storage semantics and device data were
not changed. The physical retest is **NO-GO** until the S3
failure is localized without clearing storage and the capture path is
independently assessed for reset risk. Details and exact future gates are in
[GS-114 Part 2B evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2B_ROOT_CAUSE_20261012.md).

## GS-114 Part 2 — observer stopped on reset and Hub admission error — 2026-10-12

At canonical source `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`, read-only
USB/sysfs/udevadm preflight found the approved C3 USB identity on
`/dev/ttyACM0` and the approved S3 USB-UART identity on `/dev/ttyACM1`; neither
port was already open. The user authorized opening only their two stable by-id
interfaces for DTR/RTS-low receive-only capture. The existing observer verified
the by-id serials and Part 1 candidate artifact hashes, then captured 60 seconds
without sending serial bytes.

The capture reported C3 boot reason `USB_UART_CHIP_RESET` during the observation
window. The cause is consistent with opening the UART but cannot be proven. S3
reported `S3 replay-fence publication failed; admission closed`. Per operator
instruction, the physical campaign stopped immediately; no recovery or further
device access occurred and no real PIR movement was requested. Logs are retained
at [GS-114 Part 2 stopped baseline](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2_20261012T032500Z_baseline/STOP_REPORT.md).

Boot banners show the fixture's expected C3/S3 MACs, chip revisions, flash/PSRAM
profiles, ESP-IDF 6.0.3, and app version `73e1e842ff84-gs114-16fca85b`; installed
image hashes are not proven. Authenticated rejoin and online liveness appeared,
but no EventKey-to-durable-commit-to-application-ACK-to-retirement chain was
observed. The observer's aggregate `PARTIAL` is overridden by the explicit
stop-condition evidence; HIL-A06 is FAIL. GS-114 P1 is NOT_RUN, P2–P4 BLOCKED,
P5–P9 remain BLOCKED/NOT_RUN as detailed in the stop report, and P10 belongs to
GS-149. No PIR physical PASS is claimed. GS-114 remains In Progress.

Next action requires a verified non-resetting receive path and resolution of
the S3 replay-fence admission failure; do not reopen the ports, reset, reflash,
or modify stored state without a new explicit authorization. Isolated GS-152
and protected original boards were not accessed.

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
At the 2026-10-11 implementation checkpoint, baseline `validation-node`,
`validation-hub` and `validation-contract` exited 2 before relocation due to four
existing NodeHealth-config simulator setup errors and a missing Playwright
dependency; Hub also retained the known `hub-journal-migration-host-test`
assertion failure. The migration test remains mandatory and must not be
suppressed. Final post-migration and integration outcomes follow below.

### GS-152 final integration checkpoint — 2026-10-12

The 499-entry move map has 499/499 baseline hashes verified and 499/499
destinations present. It records the original 125 path/build/documentation
adaptations; 6 additional destinations include newer canonical GS-114 changes,
for 368 byte-identical destinations in the integrated source. The
active version-named source wrapper is absent. The archived release manifest
matches its baseline SHA-256 exactly; the prior `UNCHANGED=0` diagnostic was
consistent with the successful `git diff --quiet` return code and did not
indicate an edit.

History-preserving merge commit `0ab12c38b8115c211b66b203289d77f8a835ec00`
incorporated canonical GS-114 through `9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33`.
The branch then added clean-checkout GS-114 build-discovery and validation
runner fixes, ending at `d802485ee04227b6e1ca16810768e01f0da94009`. Canonical
integration used a fast-forward; exact GitHub and test evidence is in the linked
[GS-152 integration record](../exec-plans/evidence/GS152_RESTRUCTURE_BASELINE_20261011.md).

The clean-checkout C3/S3 target pair and GS-114 S3 RPF diagnostic build passed
under ESP-IDF 6.0.3; the diagnostic selected the fixture commissioning profile,
validated RPF00–RPF08 and matched the candidate partition CSV to the compiled
table. A later redundant rebuild attempt could not start to completion because
the temporary filesystem filled after the earlier verified artifacts had been
produced. No artifacts were deleted. Focused Node, Hub, backend, PWA and
contract regressions ran; ASan/UBSan passed C++ 1,479 and GS-40 1,320 checks,
and board-stack E2E passed all 8 groups.

The aggregate Node/Hub/contract/backend/PWA gates correctly retain FAIL because
P0 reports `product_status=PARTIAL`; all 26 P0 scenario checks and its Chromium
case pass. Hub also retains the pre-existing `clean migration commits`
assertion failure. Both failures remain mandatory and visible, and were present
before this restructuring. No new regression was found. Release qualification
and physical HIL remain NOT_RUN. No serial port or device was accessed.

Canonical source integration is complete. GS-114 hardware qualification was
not changed, and the pre-existing untracked S3 `managed_components/` and
redacted physical evidence were preserved. GS-144 and GS-148 work/statuses were
not changed by GS-152.

## GS-114 repaired C8 physical checkpoint — 2026-10-13

Canonical branch `feature/r1-commercial-baseline` at initial local/remote HEAD
`72a223fc3b290c01c9f93fbb90db83d87601ad54`; context preflight PASS
`2026-10-13.001`. The authorized C3/S3 R&D pair was independently reidentified,
and the RPF07 repair images were clean-installed and flash-verified. Fresh
test-only commissioning and authenticated rejoin succeeded. A real AM312 motion
produced EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1`, authenticated Hub
Durable ACK and one GPIO wake in post-event authenticated NodeHealth. Hub
admission was operational; no RPF07 was logged. The exact successful `RPF00`
reconciliation, C3 application-ACK retirement trace and per-key one-effect
ledger remain unproved because the built-in C3 USB Serial/JTAG console stopped
emitting after light sleep. P1/P2 have partial physical evidence, no PASS;
P3–P9 remain pending or blocked by their specific fixtures. The complete
timestamped redacted logs, hashes and dispositions are in the [GS-114 execution
report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md),
and GS-114 Jira comment 10818 records the same checkpoint. Prior migration FAIL
and product P0 PARTIAL remain separate.

A scoped `GS_HIL_COMMISSIONING` S3 diagnostic now builds under ESP-IDF 6.0.3,
logging authenticated NodeHealth detail, successful replay-fence reconciliation,
retirement-ACK send result and per-key durable outbox lookup. The paired build
and focused replay/checkpoint host regression passed; exact image hashes and
partition profile are in the [diagnostic manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/diagnostic_manifest.json).
Both new diagnostic images were then clean installed and flash verified on the
same identified R&D pair. A C3 read-only probe initially stopped at a WSL USB
RTS ioctl timeout before C3 erase; operator C3-only reconnect and an exact
Windows USBIP attach restored the interface, after which the C3-only guarded
install passed. Fresh test-only commissioning succeeded. The first authenticated
Node retirement report physically logged `RPF00 path=PREPARED admission=OPEN`
and authenticated retirement ACK at 16:52:50 UTC: **RPF07 repair physical
retest PASS**. The owner requested pause before the five-minute P1 health
baseline and before any run-02 PIR stimulus. Capture was closed, both serial
ports are unowned, and the installed images/commissioning remain on the boards.
The latest full [pause handoff and results](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
preserve all redacted run-02 evidence and the exact resume action. Source/evidence
commit `b3217b977b6bf77070bc1a52c0c6706eb9cf7a29` matched GitHub before
the pause update; the handoff changes require their own commit/push verification.
Jira GS-114 comment 10819 records the direct RPF00 milestone. The USB console
observer may still require an independent 3.3 V UART/GPIO probe for literal C3
UART and held-HIGH acceptance. GS-114 P1–P9 and GS-146 remain open; GS-149
current/P10 measurements were not made. No CloudSync or C9–C11 implementation
was started. At resume, recheck by-id ports/identity/power/wiring and capture
with a live control channel; reuse installed images, wait for authenticated
timer-wake health and then prompt for real P2 motion. Do not erase first.

## GS-114 C8 physical execution update — 2026-10-14 02:14 UTC

The run03 campaign continued on the existing commissioned boards and diagnostic
images without erase, reflash or recommission. Canonical branch
`feature/r1-commercial-baseline` is at `ec469303d17ea2037019a5bb18d29ce070c249e2`,
matching `origin` at this checkpoint. The P8 fixture, test registration and
evidence updates are now tracked-file modifications in the working tree and
remain unstaged/uncommitted. Existing unrelated untracked PWA/build/evidence
directories are preserved. The new run03 raw capture is also untracked and
active. Context preflight PASS `2026-10-13.001` was verified at resume.

Physical dispositions: Phase A/RPF07 repair PASS; P1 PASS; P2 PASS; P3 BLOCKED
because no GPIO4 level trace proves held-HIGH sleep inhibition; P4 FAIL because
three distinct qualified EventKeys followed one requested motion episode; P5
BLOCKED/inconclusive because first outage-recovery key traffic fell in the S3
capture gap and another distinct durable event appeared; P6 PASS because the
Hub-only restart led to authenticated session 3, RPF00 admission OPEN, and no
Node reset/pending event. Detailed timestamped records are in the
[GS-114 execution report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
and run03 per-case notes. No source/image change is justified by the observed
P4/P5 anomalies; exact GPIO/event causation remains unproven.

The one-owner S3 capture remains active at the stable by-id path. The Node's
native USB console is silent during light sleep; authenticated NodeHealth over
ESP-NOW is the deferred wake/sleep observer. P7 is ready for a physical
post-reboot event but the operator instructed that motion prompts wait until
they send `available`. The active S3 capture recorded stable session-3 health
through 02:18:45 UTC: reset 11, retained 0, durable ACK 14, GPIO wakes 19 and 40
additional timer wakes since 01:58:46, with no new event or pending work. Do not
reset/reflash/recommission.

While waiting for P7 motion, the separate S3 commissioning-profile-only
`GS_HIL_C8_ACK_DROP` path was implemented in the working tree, default OFF and
separate from broad `GS_HIL_CONTROL`. It requires an authenticated Durable ACK,
new state effect, successful exact-key outbox lookup and OPEN admission before
suppressing one ACK; the same-key duplicate remains on the normal ACK path. The
registered C++ gate test passed 16 checks in ordinary, ASan/UBSan and TSan
builds. The target P8 image has not been built or installed, and no P8 physical
stimulus occurred. P7 still takes priority after the operator sends
`available`. Current installed app hashes remain C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`.

At this checkpoint local and remote HEAD are both
`ec469303d17ea2037019a5bb18d29ce070c249e2`; source and documentation changes
are uncommitted and unstaged. The active raw S3 capture and pre-existing PWA,
managed-component and historical evidence paths remain untracked and preserved.
Context preflight PASS `2026-10-13.001`. P9's ACK hold still needs a longer
controlled window; no matched signed C3 test/recovery image or trigger was found
for FOTA. GS-114 stays In Progress; P10 is separate under GS-149.
Jira GS-114 comment 10860 records this host-validation milestone and P7 wait.

## GS-148 P4/P5-B1 CloudSync caller — resumed validation checkpoint, 2026-10-14

Resumed at base HEAD `bac66ad3a2fb05307c5200fafd34925a04203d42`, with local
and `origin/feature/r1-commercial-baseline` matching and context preflight PASS
`2026-10-13.001`. Added a registered host production-path scenario joining the
bounded C++ CloudSync worker and HTTP transport to the real local durable API,
SQLite commit, ownership policy and caregiver projection. It covers wrong-Home
and stale-epoch denial before writes, exact original EventKey/timestamps, loss
of the first response after durable commit, backend reopen, byte-identical
retry, duplicate COMMITTED, one durable logical effect and one caregiver
projection. Registration is in the existing local/release stage for Hub,
contract and backend. Full details, commands, source fingerprint, build hashes
and component reports are in the [GS-148 resume execution
record](../exec-plans/evidence/R1_GS148_P4P5_B1_20261014.md).

The new worker/API stage passed in contract and backend component runs at source
fingerprint `a6987bd82c8ce32e41522e030fa31e7e9eca3bb7b3e62550e48d60738a3efc15`.
Framework tests passed 41/41 and feature mapping passed for 184 features, 205
source modules and 15 physical cases. The legacy first-event reader
compatibility test initially exposed a test-only compile dependency on new
worker APIs; a `GS148_OLD_READER` guard fixed it and the focused compatibility
retest passed 11 states for two readers. The new stage's initial matcher also
missed its `unittest`-prefixed PASS line; the registry matcher was corrected and
both affected gates then counted the stage as PASS. Hub storage ASan/UBSan
passed. An initial framework check also caught guessed migration input
filenames; the stage was corrected to reference existing repository migrations
before the passing contract/backend runs. Only the traceability result field and
Markdown evidence changed after those component reports; their original source
fingerprints remain recorded in the handoff, and framework, feature-mapping and
worker/API checks were rerun on the final metadata tree.

`validation-hub` aggregate remains FAIL: its first resumed run also reproduced
the known `clean migration commits` assertion and P0 `product_status=PARTIAL`.
The later contract/backend aggregates remain FAIL only because P0 remains
PARTIAL; the registered worker/API stage and other selected software stages
passed. The full Hub aggregate was not rerun after the two focused test-harness
corrections. P0's 26 scenario checks and Chromium test pass but do not close the
product gap. The Hub migration assertion remains mandatory and unchanged.

An offline ESP-IDF 6.0.3 S3 RPF diagnostic build passed at that same source
fingerprint. Candidate S3 app SHA-256 is
`380790d92bb4ced76c716939d3789157c27ebe8ca1643057d066afa0ef1b5b11`; paired
C3 build SHA-256 is
`c46ceda27adac2175c041a6b0850fddd6d216a2745bb57bd381008e744fb2998`. This is
not a P8 ACK-drop image (`GS_HIL_C8_ACK_DROP=OFF`), neither image was installed,
and no running-image identity or physical CloudSync result is claimed.

Commercial target sending remains disabled pending GS-109 decisions on
credential issuance/verification, trusted Home/Hub/epoch authority and safe
coordination between CloudSync networking and the ESP-NOW admission owner.
P0 is PARTIAL, Hub journal migration is FAIL and release is not approved. No
hardware or `release-gate-final` operation was run. The validated checkpoint is
committed as `3bf08d187e7be24e2cbbc83c3998ec31ee2de962` and pushed with local and
remote HEAD matching. Keep GS-148 In Progress and carry the unresolved
trust/runtime contracts to GS-109 before enabling target sending. GS-148 Jira
comment 10974 records the resumed validation checkpoint.

## GS-109 / GS-148 CloudSync security-contract addendum — 2026-10-15

Resumed from canonical local/origin HEAD
`3ddfabdb6d5ce1d33ea20dfc60714e8722a29493` on
`feature/r1-commercial-baseline`; context preflight PASS
`2026-10-13.001`. Jira work orders GS-68 comment 11014, GS-109 comment 11015
and GS-148 comment 11016 were read. There is no competing canonical source
writer. A pre-existing `validation-pwa` run is active in the surrounding
workspace; it was left untouched and no source work was performed concurrently.

The [CloudSync contract addendum](../exec-plans/evidence/GS109_CLOUDSYNC_CONTRACT_ADDENDUM_20261015.md)
adds a source-grounded key-custody matrix, D12/D05 recommendation, exact
proposed D03/D04/D07/D11 contracts, D06 expiry/time values, D15 rollback
dependencies and measurable D16 runtime/memory/SLO bounds. It explicitly marks
new values/fields unapproved and records actual S3 hardware/fuse state as
unverified. The previous conditional recommendation to consider existing
P-256 first is superseded: current HIL source exports P-256 into NVS, the
production PSA path does not reject export usage or establish hardware
backing, and the examined diagnostic build has Secure Boot, Flash Encryption
and NVS Encryption disabled. ESP-IDF 6.0 S3 does document RSA DS/eFuse HMAC
signing and DS data support in ESP-TLS, but the production client signer and
factory provisioning path do not exist in the current CloudSync integration.

Work remains documentation/decision preparation only. No source implementation,
tests, hardware/eFuse changes, credentials, roots, trust settings, deployments or
Jira workflow changes occurred. GS-148's validated host worker/API receipts are
reused because source behavior is unchanged. Commercial S3 CloudSync remains
disabled. Product P0 `PARTIAL`, Hub migration `FAIL`, GS-114 evidence and
GS-146/GS-149 ownership remain unchanged. Existing untracked PWA assets,
managed components and GS-114 raw/private evidence are preserved.

**Next action:** route the addendum for owner disposition in GS-68/GS-109/GS-148.
Resolve D12 before D05; then D03/D04/D06/D07/D11/D15/D16 and GS-76/GS-137
dependencies. Do not implement or issue credentials until those approvals are
recorded. After the documentation push, the exact delivered local/origin SHA
and new Jira comment IDs are the resume checkpoint; verify both the branch head
and those comments before beginning any implementation.

## GS-125 isolated Dashboard integration candidate — 2026-10-15

An isolated candidate was prepared from canonical source
`c48e0d2fa8e0bc9c0d0a1f5eccdef789ff0b02df`; the Dashboard source checkpoint was
`d6ea59a2e10691e2cb09af80f0794ead272342ce`. The candidate worktree is
`/home/udaybhan/projects/Ghar_sajag_r1_integration` on
`integration/gs125-dashboard-r1-20261015`. Neither source worktree was modified.
Integrated source/evidence commit at validation was
`4e6236810484e4ab9de2cc55934dc0d7e5ad4ea4`; the follow-up commit only binds the
validation report, native receipts and this work-state update.
At final source recheck canonical had advanced to
`2c6797e36891303211262d43773920f531a3695c` through one storage-history
documentation file. That file was added to the isolated candidate without source
overlap. Canonical and integration context preflights both passed after this
documentation-only advancement.
The [conflict-resolution and validation report](../exec-plans/evidence/integration_gs125_20261015/CONFLICT_RESOLUTION_AND_VALIDATION.md)
records the 13 shared paths, all six preserved canonical-only registry stages,
native receipts and actual results.

Engineering host tests (98), GS-116 framework tests (44), GS-130 mapping tests
(22), Caregiver JavaScript tests (23), Caregiver browser tests (86), Engineering
PREVIEW_ONLY browser cases (20), and the focused canonical C8/storage/Cloud
Worker stages passed. Storage sanitizers passed. P0 scenario assertions passed
with `product_status=PARTIAL`; the PWA aggregate remains FAIL, the historical
Hub migration remains FAIL, and physical qualification remains NOT_RUN. One
native PWA aggregate Python attempt recorded a missing Hub test-binary setup
error; after building its existing prerequisite, the full 465-test Python
discovery passed with one approved skip. The original aggregate receipt is
preserved and was not rewritten. No release-gate-final or hardware operation
was run. Commercial auth, production Engineering routes and CloudSync remain
disabled; GS-148 remains owner-controlled and In Progress. No canonical merge
is authorized by this status entry.

Final pre-merge follow-up on 2026-10-15: the Python test stage now has an
explicit `backend-receipts` prerequisite, so a clean PWA validation builds
`hub_backend_commit_validation` before Python discovery. The original 79
canonical registry stages remain present with their commands, components,
selectors and assertions preserved; the only additive change is Python's
`backend-receipts` prerequisite. The candidate has 80 stages with only
`diagnostic-foundation` added. Framework 44/44, engineering host 98/98,
traceability 22/22, Python 465/465 with one approved skip, Caregiver browser
86/86, and Engineering PREVIEW_ONLY 20/20 passed in fresh/focused executions.
The final `make validation-pwa` aggregate could not complete because its default
localhost port 8766 is held by an unrelated existing lab process; its browser
stage passed separately on supported port 8767. The P0 stage remains PARTIAL,
historical migration remains FAIL, first-event old-reader limitation remains
known, and physical remains NOT_RUN. Canonical remote advanced to
`1eba6c561e8a908fc899219cb7098af30ddcff80`; its tree delta from `2c6797e` is
one additive storage reconciliation report only. Full details and receipts are
in the linked integration report above. Merge recommendation remains BLOCKED
until a complete normal-port PWA aggregate is captured and the owner reviews the
candidate against the latest canonical tip.


## GS-125 port-coexistence final qualification — 2026-10-15

Validation correction commit `63cf8d605db08ff5c9cec8e62729a437e234fd4d` is pushed on `integration/gs125-dashboard-r1-20261015`; it includes canonical tip `1eba6c561e8a908fc899219cb7098af30ddcff80` as a merge parent. Context preflight PASS (`2026-10-13.001`); local and remote canonical HEAD matched. The integration tracked tree was clean at validation and its branch remote equaled local HEAD. Detailed receipts and merge review are appended to the [GS-125 integration report](../exec-plans/evidence/integration_gs125_20261015/CONFLICT_RESOLUTION_AND_VALIDATION.md).

Root cause: the component gate inherited global `PLAYWRIGHT_PORT`/`PWA_BASE_URL` into Python tests, changing tests' expected default port. Browser-only variables are now scoped to the registered browser stage. With no explicit override, the runner prefers 8766 and selects an OS-assigned alternate if occupied; a per-user startup lock coordinates concurrent worktrees. The existing listener (PID 432418) was not terminated. Regression tests cover default behavior, alternate port use, concurrency serialization and stage environment isolation.

Source fingerprint `a468c9311fa3c9942c0485b52138574c1641026fc797400cc27ca6850bf949c9`. Fresh `make validation-pwa`: **14/15 stages PASS**, aggregate **FAIL / exit 2 / physical NOT_RUN**, solely because P0 completeness remains PARTIAL after 26/26 assertions and its Chromium check pass. Python 470 tests (one approved historical skip), Caregiver JS 23, browser 86, Engineering preview 20, Engineering host 98 all pass. Six final-source canonical stages passed: C8 ACK-drop 16, storage correctness, storage ASan/UBSan, reader compatibility (known rollback limitation retained), recovery projection (CloudSync PENDING/P0 PARTIAL/physical NOT_RUN retained), and Cloud Worker/backend integration. GS-130 traceability is 198 features/210 modules/15 physical cases, 22/22 mapping tests. GS-116 framework is 46/46.

Keep visible: **P0 PARTIAL** due unconfigured production Hub TLS/credential authenticator and enrollment-generation registry binding; **historical migration FAIL** (not rerun); `OLD_READER_COMMERCIAL_ROLLBACK_AVAILABILITY=FAIL_KNOWN_FIRST_EVENT_LIMITATION`; and **physical qualification NOT_RUN**. Commercial CloudSync remains PENDING, Engineering screens remain PREVIEW_ONLY, and no release gate or hardware/authentication action was run. Failed historical receipts and whitespace findings are preserved.

Registry comparison: 79/79 canonical stages preserved, 80 total with only `diagnostic-foundation` added; no release/security requirements weakened. Latest canonical report is incorporated and no candidate tracked path collides with the canonical worktree's 272 untouched untracked evidence/artifact paths. **Source merge recommendation: GO** when separately authorized; commercial release remains blocked by the product and qualification gaps above. Do not merge canonical in this task. Next action is separate owner-approved source integration; retain the physical evidence and do not change Jira workflow statuses.

## GS-125 Dashboard source integration completed — 2026-10-15

Executed the owner-authorized source integration from GS-125 comment 11058. Canonical `feature/r1-commercial-baseline` was fast-forwarded from `570758dccf7b2d23154696b3a4c4989a02932ded` to integration commit `5f58333548739a31c388a359f4a122dad20d2ed7`; no merge commit was created. At this checkpoint canonical local and GitHub refs matched. The integration branch also pointed to that commit, and the original Dashboard branch remained at `d6ea59a2e10691e2cb09af80f0794ead272342ce` on local and remote. The canonical task process was idle at its terminal with no child commands, no Git operations or locks were present, tracked status was clean, and the protected 272-path untracked inventory hash stayed `c82d021fd13f46ec58b397f43be00c557262e0508d7d7da276d7849451127d7c`.

Canonical had advanced after candidate approval. Its single new commit `570758dccf7b2d23154696b3a4c4989a02932ded` added existing Hub journal and Node recovery host assertions plus the Hub test target's codec link input and a diagnostic branch reconciliation report. This test-only delta was reconciled into the integration branch and both new host targets passed before the canonical fast-forward.

Post-merge checks on the integrated tree: context preflight PASS; GS-116 framework 46/46; GS-130 traceability 22/22 (198 features, 210 modules, 15 physical cases); Engineering Dashboard host 98/98; Node recovery persistence host PASS; Hub journal persistence host PASS. The registry contains 80 stages, all 79 stages from canonical `570758d` remain, and all six C8/storage/CloudSync stage commands are unchanged. The Python stage retains its `backend-receipts` prerequisite. Browser/Python execution settings remain scoped; no release/security requirement was weakened.

The native PWA aggregate is preserved at the exact approved candidate source `3b69336d1a661bf91a0d57dda56695764a16003d`, fingerprint `a468c9311fa3c9942c0485b52138574c1641026fc797400cc27ca6850bf949c9`: 14/15 PASS, with the sole failure P0 `product_status=PARTIAL`. Its byte-exact report/log copies and six canonical regression logs are in [the committed evidence archive](../exec-plans/evidence/integration_gs125_20261015/native_final_candidate_3b69336/); archive manifest SHA-256 is `906fc0164fb176e7065fe9f96e8c4c9416af9fadb486d345382ff4aa3ecafccf`. The canonical test reconciliation changes the current source fingerprint to `036f4f910c0f7cb050fbbd89e6e5c40f2f6a737aa9167ddf0063a20a4d3fdbfd`; the archived PWA report is not relabeled as running at that later source. The test-only delta has focused post-merge coverage as listed above.

Product/release status is unchanged: P0 PARTIAL; historical migration FAIL; known old-reader rollback limitation; production CloudSync PENDING; Engineering production UI/authentication BLOCKED; physical qualification NOT_RUN. Remaining Stage 2B production work includes production Hub TLS/credential trust and enrollment-generation binding for P0, production CloudSync credentials/worker deployment and durable COMMITTED receipt path, and production Engineering identity/authenticated routes. No production authentication or CloudSync was activated, no hardware operation or full release gate was run, and no Jira workflow status was changed.

Detailed source/evidence results are in [the integration qualification report](../exec-plans/evidence/integration_gs125_20261015/CONFLICT_RESOLUTION_AND_VALIDATION.md). Context version and locked product decisions are unchanged.

## GS-118 Phase-2 rollback remediation handoff — 2026-10-15

The owner clarified that the ESP32-C3 Node is still the 4 MiB target; only the
Hub is now ESP32-S3 N16R8 with 16 MiB flash and 8 MiB PSRAM. The C3 OTA
partition geometry and rollback memory budget remain unchanged by the Hub
upgrade. The historical Phase-2 audit identified a 3 KiB C3 rollback-task
stack fault. Canonical now configures `gs_ota_validate` with a provisional
12 KiB stack and includes guarded, opt-in signed-HIL failed-health injection
plus rollback-evidence regression checks. This source change addresses the
confirmed historical configuration gap; physical stack margin and rollback
qualification remain open.

The detailed reconciliation, historical commit dispositions, stack analysis,
validation receipts, fixture limitation, and backup verification are in
[`GS118_PHASE2_ROLLBACK_RECONCILIATION_20261015.md`](../exec-plans/evidence/GS118_PHASE2_ROLLBACK_RECONCILIATION_20261015.md).
The complete Phase-2 worktree and commit history are preserved in the verified
restricted backup at
`/home/udaybhan/projects/phase2_evidence_backup_20261015T101912Z`. The Phase-2
worktree and branch were not modified or removed. Existing untracked PWA
assets, S3 `managed_components`, and GS-114 raw evidence in canonical remain
untouched and must not be swept into this delivery.

Canonical is `feature/r1-commercial-baseline`. Remediation commit
`aab00e895e9a130c6c9b31b07e6ece11815f4f6c` was pushed normally and local
HEAD matched GitHub at final verification. GS-118 handoff comment 11070 was
posted with no workflow status change. A documentation-only follow-up records
the exact isolated build commands and this final delivery checkpoint.

Focused software results: signed-FOTA fixture tests 20/20 PASS; C3 production
and explicit HIL-injection ESP-IDF 6.0.3 builds PASS; board-stack E2E 10 groups
PASS; validation framework 46/46 PASS; traceability 22/22 PASS (202 features,
210 modules, 15 physical cases). The signed-profile build is BLOCKED by absent
local signed configuration and test signing credentials. `validation-node`
and `validation-contract` aggregates remain FAIL because P0 is
`product_status=PARTIAL`; `validation-hub` remains FAIL because the existing
Hub journal migration stage fails, in addition to P0 PARTIAL. Those failures
remain visible and are not GS-118 acceptance. Physical signed rollback is
NOT_RUN. The current FOTA supervisor still targets a classic ESP32 Hub while
the S3 Hub rejects legacy broad HIL controls, so S3-compatible fixture control
or an approved alternate fixture is required before current-pair physical
qualification. A first mistaken build invocation regenerated the ignored C3
target-root `sdkconfig`; its current bytes are preserved externally, but its
prior bytes were not captured and cannot be certified unchanged.

**Exact next action:** owner/fixture authority must resolve an S3-compatible
HIL control/profile or approve an alternate supported Hub fixture, then provide
safe signed test artifacts and a disposable C3 for the bounded physical
rollback test. That run must capture restored slot, fresh authenticated
session, retained EventKey/Durable ACK, panic/reset evidence, rollback-task
stack high-water and free heap. Keep physical status NOT_RUN until then. Track
source-consolidation and historical-ref retirement decisions under GS-95;
do not retire Phase-2 in this task. P0 PARTIAL and the existing Hub migration
failure remain with their owning work.

## GS-95 Phase-2 source retirement handoff — 2026-10-15

All 11 historical `feature/hw-m1-4-hil-phase2` commits are reconciled in
[`GS95_PHASE2_SOURCE_RETIREMENT_20261015.md`](../exec-plans/evidence/GS95_PHASE2_SOURCE_RETIREMENT_20261015.md).
No required production source or regression remains exclusively historical.
The C3 rollback-task stack remediation and guarded failed-health test path are
already in canonical; physical stack margin and rollback remain NOT_QUALIFIED.
The C3 still has 4 MiB flash; only the Hub baseline is S3 N16R8. Historical
classic-Hub HIL results do not qualify current S3 hardware.

The owner-authorized historical Phase-2 worktree and its local/GitHub branch
were removed after full file-hash, inventory and Git-bundle verification.
The deleted branch tip was `8f053b45b1c6b8ec772565336582c7e63a68a6a6`.
Its complete source, ignored artifacts, logs, firmware images, historical
commits and misleading September 27 rollback PASS record remain in the
restricted backup at
`/home/udaybhan/projects/phase2_evidence_backup_20261015T101912Z`.
The original pre-regeneration C3 sdkconfig bytes were unavailable, as already
documented under GS-118; the current file was preserved. No protected
hardware was accessed.

The initial GS-95 report was pushed at
`05ccb298d9de889a17da9310abdf8e6d71c1ef03`; this handoff and final
deletion receipts are a subsequent documentation-only update. The canonical
tracked tree was clean before the handoff edit; pre-existing untracked PWA,
S3 managed components and GS-114 raw evidence are untouched. After worktree
removal, signed-FOTA fixture tests passed 20/20 and feature coverage passed
22/22. No target build or full release gate was rerun. Existing P0 PARTIAL and
Hub migration FAIL statuses remain, separate from GS-95 source retirement.

**Next:** continue ordinary feature work in canonical without Phase-2 branch,
worktree, signing credentials or HIL fixture. GS-118/67 need approved signed
test images and a disposable current-pair fixture for clean failed-health,
interruption/corruption and stack high-water qualification. GS-108 and GS-96
retain broad and multi-node physical HIL. GS-148 and P0/migration remain with
their own owners. Verify canonical local/GitHub HEAD equality after this
documentation commit and record the GS-95 Jira handoff.

GS-95 handoff comment `11104` was posted and its source-consolidation issue
transitioned to Done after these gates passed. GS-118, GS-108 and GS-96 remain
To Do for their distinct physical acceptance work. Their test results and
workflow statuses were not changed by branch retirement.


## GS-40 source-to-caregiver software integration checkpoint — 2026-10-16

The canonical branch now contains additive GS-109/GS-68/GS-148 software for
verified Hub/Home/epoch/time context, current per-Node health publication over
the existing CloudSync path, authenticated SQLite latest-state ingest, and
caregiver projection. The backend read model keeps Hub contact, backend receipt
and PWA snapshot times distinct; lease expiry or stale Hub/cloud source cannot
render a healthy Node. EventKey durability and ACK/retry behavior are unchanged.

**Production integration remains incomplete:** the S3 product application does
not yet instantiate the worker with the approved permanent Hub identity, trusted
time and current authenticated NodeHealth authority source. GS-40 cannot resume
physical acceptance until that source-to-caregiver path is composed and its
prerequisites are qualified. D05/D12 production Hub certificate/key custody and
verifier, D06 trusted Hub time, plus the S3 owner/worker composition contract
remain open. P0 stays PARTIAL; Hub journal migration stays FAIL; `PHY-GS40` and
`PHY-GS68-CLOUD-MTLS` remain release-blocking / NOT_RUN. No workflow state,
production credentials, production endpoint, hardware, flash, reset or physical
case was changed or accessed.

ESP-IDF 6.0.3 compile-only builds pass: C3 937,536 bytes, SHA-256
`d94e011abd0e28b31cadb4dee2ff6451b0f5311c2783cdcbb2a631c03e86f765`; S3
1,887,200 bytes, SHA-256
`507df1e2a26707bc7c5267b98c369dd00e5141a29c6ccf687b5a06908d4480ed`. Their
source baseline is `76516b963055977eab7cb2d2d084c69692d8690e` with working
source fingerprint `ba043ee9da757a1cf0285223b94e145a4ed4478b06d07e74ad03bff2708ae913`.
Focused mTLS 8 adapter cases + 13 certificate tests, NodeHealth 5 tests, C++
1,488 checks, CloudSync contract, PWA JavaScript 24/24, GS-40 qualification
17/17, GS-116 framework 47/47, GS-130 runner 70/70, traceability 22/22, and
GS-130 mapping consistency 208 features / 218 modules / 24 physical cases pass.
Backend component Python passed 513/513; PWA browser passed 86/86. Hub,
contract, backend and PWA aggregate gates remain FAIL only at their preserved
release conditions: P0 product_status=PARTIAL, and for Hub the historical
journal migration validation (`clean migration commits`). Parallel component
runs initially collided on shared binaries (`Text file busy`); affected
feature-boundary (133 checks), board-stack (10 cases / 398 checks) and storage
sanitizer targets were rerun sequentially and passed. Full exact results and
limits are in the [dated evidence report](../exec-plans/evidence/GS40_GS109_GS68_GS148_SOFTWARE_INTEGRATION_20261016.md).

This checkpoint is on the canonical `feature/r1-commercial-baseline` worktree;
initial local and origin HEAD were both
`76516b963055977eab7cb2d2d084c69692d8690e`. Implementation commit
`37556707cd03b84327e9a25b98a4c9e43f374abf` was pushed normally;
`git ls-remote origin refs/heads/feature/r1-commercial-baseline` matched local
HEAD at that checkpoint. Jira comments were added without workflow changes:
GS-109 comment 11242, GS-68 comment 11239, GS-148 comment 11240 and GS-40
comment 11241. A final documentation checkpoint records these delivery facts.
The pre-existing untracked PWA asset bundle, managed components, GS-114/C8
evidence and GS-40 UART evidence remain preserved and unstaged. No new
product/security decision is made; CONTEXT_VERSION is unchanged.

**Next action:** resolve D05/D12 and D06, then compose the S3 runtime's approved
identity/time/current-NodeHealth source into the existing CloudSync worker and
rerun focused source-to-caregiver gates. Keep production feed and physical
qualification disabled until their separate prerequisites and approvals are met.


## GS-172 first-device S3 security qualification package — 2026-10-17

GS-172 comment 11296 is addressed with four versioned records:
`GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md`,
`GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md`,
`GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md`, and
`GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md`. They follow GS-165–GS-171
pilot scope/contracts and reuse the implemented GS-168 TEST_ONLY issuer,
GS-109 Home/epoch authority seam, GS-68 D05/D12/D06 provider seam and existing
GS-68/GS-40 physical cases. GS-167/GS-169–GS-171 remain planned/integration
scope and are not represented as completed station software. No replacement
PKI, backend authority model, transport, or validation infrastructure was
introduced.

The proposed pilot is one disposable non-customer S3 fixture, one isolated
TEST_ONLY issuer/time/backend, one operator and one independent evidence
reviewer for 50–100 Hubs. The decision matrix separates owner-ready scope/model
decisions from Security review of issuer custody, RSA-3072 DS key generation
and eFuse/HMAC handling, D06 authority/rollback limits, production registry
lifecycle, and Secure Boot/Flash Encryption/anti-rollback/recovery order. The
SOP is non-executable. Secure Boot/Flash Encryption sequencing is tied to the
pinned ESP-IDF 6.0.3 workflow and requires a source-pinned reviewed procedure;
the current S3 product lacks a production signed OTA/recovery path, so
irreversible commercial lock-down is NO-GO.

Current fixture readiness is NO-GO: board/revision, installed image,
source/config/session, target DS signer, physical test-only credential/time
fixtures, safe reset-free observer, recovery owner and fixture authorization
are not established. The S3 app still composes `UnprovisionedS3CloudTrust`;
the production providers and key/counter hardware are not instantiated or
qualified. Existing GS-68 TEST_ONLY host evidence is retained as software
evidence only. GS68-PHY-001..010 and PHY-GS40-01..06 remain NOT_RUN; TC05 needs
another independently enrolled Node or approved profile fixture. BAT-C8
evidence remains untouched. P0 `product_status=PARTIAL` and the existing Hub
journal migration FAIL are preserved.

This package makes no product/security decision, does not increment
`CONTEXT_VERSION`, and does not authorize hardware or production operations.
The starting canonical checkpoint was `71f7dc0518fc4705d2467bc70f772d861b02750e`
on `feature/r1-commercial-baseline`, synchronized with origin with a clean
tracked tree; all existing untracked PWA assets, IDF managed components,
CloudSync architecture notes, GS-114/C8 and GS-40 evidence remain preserved
and unstaged. The other historical worktrees were not modified, and no active
writer was detected at the pre-edit check. Final delivery SHA and remote
equality are recorded in the GS-172 Jira closeout. Next action: review and
approve the owner scope rows, route P2–P8 to Security, implement and validate
the target DS/time composition behind TEST_ONLY fixtures, then prepare exact
fixture/image/observer/recovery records and request separate physical
authorization.


## GS-68 D05/D12/D06 signed-time and registry follow-up — 2026-10-17

Resumed on canonical `feature/r1-commercial-baseline` at local/origin
`29890b36a753ffdc46d7be9399a4a6cbed97d727`; pre-edit tracked status was clean,
and the context preflight passed (`2026-10-13.001`). Existing historical
worktrees and all untracked PWA, ESP-IDF managed components, GS-114/C8 and
GS-40 UART evidence remain untouched. No competing writer was active at the
start of this change.

Implemented and TEST_ONLY validated: the existing GS-168 pilot issuer now
implements the backend credential-registry lookup by certificate fingerprint,
including active/revoked/unknown state and Hub/source identity. Its localhost
mTLS harness accepts the issuer's separate TEST_ONLY client root while
preserving server-name and TLS validation. The S3 trust seam parses an RSA-3072
ClientAuth certificate and checks the exact SHA-256 fingerprint, composes one
immutable current Home/epoch/credential snapshot, and rechecks it after trusted
time acquisition before returning identity. Credential changes, transfer,
revocation, quarantine and unavailable sources fail closed.

D06 now has a bounded fixed-format RSA-3072/SHA-256/PKCS#1-v1.5 signed proof
verifier, PSA CSPRNG challenge source on ESP-IDF, one-use nonce and boot
generation binding, signed validity interval/floor checks and reboot/rollback
state-machine coverage. The target NVS floor adapter is only a durability
seam: it has no anti-rollback protection and is not composed into product
runtime. The test authority and all issued identities/certificates are
ephemeral TEST_ONLY. Product `app_main` still uses
`UnprovisionedS3CloudTrust`, keeping commercial CloudSync fail closed. No new
security decision or production anchor was added; CONTEXT_VERSION remains
unchanged.

Focused execution on the 2026-10-17 working source: `make
cloud-trust-provider-test` PASS (5 suites); `make cloudsync-security-ut` PASS
(mTLS adapter 9/9, backend security 14/14, identity/time/NodeHealth/caregiver
4/4, GS-168 issuer/registry 10/10, NodeHealth model 5/5);
`make cloudsync-security-sim-hil` PASS (18/18); `make
cloudsync-mtls-integration-test` PASS (1/1, durable worker/API bridge);
framework 47/47; feature map 208 features / 220 source modules / 24 physical
cases / 22 mapping checks PASS. The direct caregiver API/read-model projection
passed; PWA source was unchanged, and historical browser 86/86 was not rerun.
Paired non-flashing ESP-IDF 6.0.3 target build passed after switching the
Mbed TLS 4 key-capability check to its PSA API. C3 app is 937,536 bytes,
SHA-256 `b4e2b1c1d370fd2da2a30aae52cfbc2f85e91d0ff3b39da41eef23816829fedb`;
S3 app is 2,168,128 bytes, SHA-256
`e09e9651160719673958fffdc5c06f7a1787eb31403384324fd421b8f15a3ea1`, with
2,023,104 bytes free in the 4 MiB slot. S3 sdkconfig SHA-256 is
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b` and
runtime config SHA-256 is
`fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862`.
Source fingerprint is
`0944b96d91b13be9d0a8de1d9f83961e4cf38c8d05195972d27f84c50070134a`.
Build produced existing Kconfig notes and an unrelated unused-variable
warning in `hub_runtime_adapter.cpp`, no remaining build errors.
Existing required `product_status=PARTIAL`, Hub journal-migration failure and
unexecuted physical acceptance remain visible and unchanged.

**Production status:** D05/D12/D06 and current Home/epoch/revocation remain
PARTIAL/BLOCKED pending the five approval groups in
[`GS68_D05_D12_D06_PROVIDER_E2E_20261017.md`](../exec-plans/evidence/GS68_D05_D12_D06_PROVIDER_E2E_20261017.md): pilot CA/root and issuer custody; S3 DS/eFuse key custody/build/debug policy; authenticated-time authority and protected floor/boot counter; production registry and certificate lifecycle; pilot operations and fixture-specific physical authorization. Physical readiness remains NO-GO: exact S3/C3 fixture provenance, installed-image receipt, enrolled session/profile, safe reset-free observer, recovery owner and TC05's second Node/approved profile fixture are missing.

**Delivery:** implementation/evidence commit
`443f272e0277439ea932d3c7990db80d1672dd91` was pushed normally to
`origin/feature/r1-commercial-baseline`, with local/origin equality confirmed
at that checkpoint. Dated Jira comments were added without workflow changes:
GS-68 `11294`, GS-109 `11292`, GS-40 `11293`. A documentation-only receipt
commit follows this implementation commit on the same branch. The final local
and remote HEAD equality is checked after that receipt push. No hardware, real
credential, eFuse, production endpoint or commercial activation action was
authorized or performed.

## GS-172 #11316 / GS-68 #11317 — isolated signed-time diagnostic follow-up — 2026-10-17

On the canonical `feature/r1-commercial-baseline` branch, the task safely
fast-forwarded to the requested `6a0e482727c64cf5a34cb43e353bdc94b814aca1`
checkpoint, then added the TEST_ONLY S3 diagnostic integration and a response
field-layout compatibility fix. The implementation commits are
`b2decb25bbc3ebdd5413613f5f290f4f5587458b`,
`3d01bd92c80f0356d9686a9f3e3feebe7e7a2c18`, and
`d75f6b730c0b4ddc1861f2f30bf9d3fa4f381f5a`. The target-build/source test
checkpoint was d75f6b7. The validation/evidence commit
`ccc903f07fc960bef1536d1a7e727ca6362bd4fd` was pushed normally after fetch
confirmed origin remained at `6a0e482727c64cf5a34cb43e353bdc94b814aca1` and
that origin was an ancestor. `git ls-remote` then matched local HEAD at ccc903f.
No branch/worktree switch was made. All pre-existing untracked PWA/Android
assets, IDF managed components, CloudSync notes and GS-114/C8/GS-40 evidence
remain untouched.

The isolated diagnostic target links the existing `cloud_trust_provider.cpp`
and exercises runtime-injected TEST_ONLY public RSA-3072 key, S3 PSA RNG
challenge and signed-time proof interfaces. The fake host verifier macro is a
target compile error. Production `app_main` still composes
`UnprovisionedS3CloudTrust`; no private key or production anchor is included.
Missing identity/time/authority, bad/replayed proof, revoked credential,
incomplete TLS identity and unexpected network response remain fail-closed.

Validation passed on the source at d75f6b7: 27 diagnostic protocol assertions;
5 cloud-trust provider suites; mTLS adapter 9/9; backend security 14/14; GS-40
identity/time/NodeHealth/caregiver 4/4; GS-168 issuer/registry 10/10;
NodeHealth model 5/5; security simulation 18/18; local TLS-to-durable-API
integration 1/1; runner Python 72/72; validation framework 47/47; and feature
coverage 208 features / 220 modules / 24 physical cases / 22 mapping checks.
After correcting a source-compatible `BackendHttpResponse` aggregate field
order found by the integration compile, that integration passed. ESP-IDF 6.0.3
non-flashing diagnostic build passed: 468,240-byte image SHA-256
`e8e0a6236817f857346aced735f94f412245c693733710f749d56a55b248ef34`; source
tree OID `a94fd18c6cd398b70bf067e6b207a0a66f6d0682`; profile SHA-256
`00a8aefb20a6b67d34c6631128031d112ff091d3f255b21a7280db45a356b1d0`;
sdkconfig SHA-256 `f120945dd0f4ccbeee29eff5f1514ea5f0533856b27eb5207435d464a5231741`.
The prior installed spare-S3 image hash reported by the user is
`c905af73419c84af7a1d986dada3724da7e654b4d7eaa0235bd06e515902f8ef`; the
candidate was not flashed. Silicon PSA RNG, signature verification, DS signing,
live mTLS, image match and all physical acceptance remain NOT_RUN.

The candidate is build-ready for separately authorized physical validation of
PSA RNG, signed-time proof and fail-closed diagnostics after explicit image
installation and image matching; it does not qualify DS signing or mTLS because
no device DS key is provisioned. Production CA/issuer and trust custody, S3 DS
key lifecycle/eFuse authorization, authenticated-time authority and trust
anchor, rollback-resistant boot/floor storage and thresholds, production
ownership/revocation registry, Secure Boot/Flash Encryption and recovery order,
and fixture-specific physical authorization remain unresolved. Existing P0
`product_status=PARTIAL` and Hub journal migration failure are preserved.

This handoff records no new locked decision; `CONTEXT_VERSION` remains
`2026-10-13.001`. No hardware, serial/USB, flash, credentials, eFuses, Secure
Boot/Flash Encryption, or production endpoints were accessed.

Affected component gates completed: `make validation-hub` returned FAIL because
the unchanged migration test reported `clean migration commits`, the registered
ASan/UBSan storage stage timed out at 600 seconds, and P0 retained
`product_status=PARTIAL`; the P0 scenario itself had 26/26 checks and one
browser test pass. `make validation-contract` returned FAIL only because P0
retained `product_status=PARTIAL`; its security, cloud-contract, HTTPS, worker,
runner, and sanitizer stages passed. The focused target/host tests, non-flashing
S3 build, feature traceability, and exact candidate image hashes are recorded
above and in the paired evidence file. No gate failure was suppressed.

Delivery comments were added without workflow changes: GS-172 `11321` and GS-68
`11322`. The evidence commit ccc903f and its remote equality were confirmed
before those comments. This status receipt is the final handoff update on the
same branch; its normal push and HEAD equality are verified after commit.

Next action: obtain the open production security approvals and separate
fixture-specific authorization before installing the candidate or opening a
physical observer. A target test must verify the candidate's image hash before
running the PSA RNG, signed-time proof and fail-closed diagnostic cases. DS
signing/mTLS still require approved DS key provisioning, so this image does not
qualify those paths.

## 2026-10-17 — GS-172 / GS-68 spare-S3 auxiliary execution checkpoint

Canonical source on `feature/r1-commercial-baseline` was advanced by four
implementation commits ending at `cfc89a8e7bd6009eddde5790814e557357d8a032`.
The final TEST_ONLY S3 diagnostic candidate is source-bound to that commit and
builds with ESP-IDF 6.0.3. Image size/hash: 278,944 bytes /
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`;
profile/sdkconfig SHA-256 are `7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72` /
`ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a`.
The former c0fb82c candidate is superseded. Source/build runner checks now
preserve immutable artifact provenance across documentation-only commits while
rejecting code/build-input changes; auxiliary case IDs do not redefine official
GS-68 cases.

Validation: `make -C code gs130-hil-runner-test` PASS (1,738 protocol
assertions, 84 Python tests; no port opened); focused auxiliary/source-binding/
signed-time tests PASS (13); `make -C code gs68-node-diag-protocol-host-test`
PASS (1,738); non-flashing ESP-IDF 6.0.3 S3 build PASS. Context preflight
PASS. Full release validation was not run.

Owner-designated spare identity is consistent with host-only USB/PnP evidence
and distinct from protected C8 inventory. One documented read-only security
inspection with reset-capable `--before default-reset --after hard-reset`
transport options returned no security data and blocked. No retry/device I/O,
flash readback/backup, candidate install, USB diagnostic or physical crypto
operation followed. Secure Boot, Flash Encryption, ROM restrictions, installed
partition/OTA state and recovery readiness remain UNKNOWN; install is NO-GO.
Candidate not installed; running image not verified; USB/PSA/RSA tests and
official GS-68/GS-40 physical acceptance remain NOT_RUN. Restricted private
host evidence is under `~/.local/share/ghar-sajag/GS68-20261017`; public
report redacts device identifiers.

Local implementation HEAD was four commits ahead of origin at last check;
fetch/push equality must be verified after documentation/Jira completion.
Existing unrelated untracked artifacts remain unstaged. GS-172 and GS-68 are
In Progress. The Hub migration `clean migration commits` assertion, 600-second
sanitizer timeout, required P0 `product_status=PARTIAL`, production CA/DS/time/
registry/recovery approvals and physical acceptance remain open. Precise
candidate and next steps are in
`docs/exec-plans/evidence/GS68_SPARE_S3_AUX_DIAGNOSTIC_20261017.md`.

Next action: re-establish stable USB and complete only read-only security,
partition/slot and restorable-baseline recovery preflight. Do not install unless
security state and app-only compatibility are known and offline recovery is
validated. No protected C8 access, flash/erase, eFuse/security writes,
production credentials or endpoints were used.

### Delivery receipt — GS-172 / GS-68 — 2026-10-17

The auxiliary diagnostic NO-GO evidence is in delivery commit
`1f7016d0e1482d6d541d541d97665e7aca9c9059`; it was pushed normally, and
`origin/feature/r1-commercial-baseline` matched that commit. GS-172 and GS-68
remain In Progress; dated Jira comments `11333` and `11334` respectively record
the source-bound candidate, software results, blocked physical gates and
redacted spare identity. The 35 pre-existing untracked paths were left
unstaged. The separate GS-177 PWA validation process remained in its own
worktree and was not interrupted. No hardware installation or diagnostic was
performed. The next action is read-only protection/partition inspection plus
validated recovery preparation after stable USB transport is restored.
### Windows-native spare-S3 transport update — 2026-10-17

At canonical `e81272909d803a311f9e6a08bf85eeba29b97d3f` (equal to origin),
host-only checks matched Windows USB parent metadata to the restricted receipt
for the owner-designated spare. Windows lists BUSID 3-1, COM10, VID:PID
303a:1001 as Shared and not attached to WSL; WSL has no serial device node. The
prior esptool D-state/stuck process is no longer present. The separate GS-177
validation remains active and was not interrupted.

One Windows esptool v5.4.0 read-only `get-security-info` attempt used explicit
`--before no-reset --after no-reset --no-stub --connect-attempts 1`. ROM sync
ended in pySerial Write timeout; no security report was returned. No retry,
reset, USB/IP detach, flash access, or security write followed. Secure Boot,
Flash Encryption, ROM restrictions, installed partitions, OTA slot and recovery
state remain UNKNOWN. The current TEST_ONLY candidate hash is verified as
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`; it is not
installed. Physical installation remains NO-GO until an approved ROM-entry or
qualified debug route enables read-only protection inspection, then actual
partition/slot compatibility and an offline-validated restorable baseline are
established. Full redacted findings are in
`docs/exec-plans/evidence/GS68_SPARE_S3_AUX_DIAGNOSTIC_20261017.md`.

### Controlled spare-S3 ROM inspection checkpoint — 2026-10-17

At canonical `ac42690c7c75b686aec27f5a0e61f1ced1dad40c` (local and origin
equal), context preflight passed and the candidate still hashes to
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`. Windows
interop failed with `UtilAcceptVsock:273: accept4 failed 110` before current
COM10/BUSID identity and competing-port checks returned. WSL has no serial
device. Therefore the authorized automatic ROM-entry sequence was NOT_RUN; no
device I/O, reset, USB/IP operation, flash read/write or security operation
occurred. Security state, installed partition/OTA state and recovery capability
remain UNKNOWN; candidate installation is NO-GO. After Windows interop is
restored, verify the current device identity and port ownership before a single
bounded `usb-reset`/ROM security query. Full evidence and the private receipt
hash are in the linked GS-68 evidence record.

### GS-172 / GS-68 controlled read-only ROM inspection — 2026-10-17

Windows interop recovered. Current COM10/BUSID 3-1 metadata matched the
restricted spare receipt; C8 was not accessed. One authorized esptool v5.4.0
`usb-reset` entry succeeded. `get-security-info` and filtered read-only eFuse
inspection observed Secure Boot disabled, Flash Encryption disabled, normal
USB ROM download not fuse-disabled, and no secure-download mode. Flash ID
reported 16 MiB. Read-only flash access succeeded.

Installed table at measured offset 0x8000 has a valid MD5 and entries matching
the candidate layout; OTA metadata at 0xF000 selects valid OTA0 at 0x20000.
Bootloader image and app image validate as ESP-IDF v6.0.3. A 1 MiB private
OTA0 capture fully contains the installed app image and covers the candidate's
278,944-byte app write range. A full 4 MiB backup attempt timed out without a
file; the smaller validated recovery range succeeded. Private artifacts and
hashes are documented in the GS-68 evidence file; private backups remain
outside Git. Restore was not tested because it would modify flash.

Partition compatibility and an app-only recovery method are now prepared, but
no candidate installation or write was performed under this task. Candidate
remains uninstalled; running image differs from the candidate. Official GS-68
and GS-40 physical acceptance, silicon DS signing and mTLS remain NOT_RUN. A
separate installation authorization/task is required to act on the candidate.

### GS-68 / GS-172 8192-byte-stack spare diagnostic execution — 2026-10-17

Canonical branch feature/r1-commercial-baseline now contains provenance
corrections in commits d8ddb3f51e239ba839ef193b21dc60753de79044 and
329a32c3da1425148edce1c5db71e08e3222bc3f; both were pushed. The new
non-flashing ESP-IDF 6.0.3 TEST_ONLY candidate was built from
f501d985c1ce5b8b89f0786b42af6e5a179469cb (code-tree OID
cca5d51036e7a7da59f1b18f4b80fee26d814cd0): 278,480 bytes,
SHA-256 fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd,
runtime image-validation digest
d60b1c4730e86dc4f1d0d8f034b5e3e170c10c0df6abae0d2399113920686346.
Profile hash is d3a57024ecd0c8e0fda08f841d9aab14ca67b769d48610531ae464d747e0fd7c;
effective sdkconfig hash is
223c23490ffdf0a11bf24cda1984b3192355441ed03ede458c540bec5ae0535e.
The provenance validator now accepts the actual 8,192-byte main-task setting
and the explicit host-only test delta while rejecting changed build
configuration. Focused runner tests passed 41/41 and 35/35.

The designated spare was reidentified from Windows PnP immediately before
installation. Stored security/partition/OTA/recovery receipts rehashed; Secure
Boot and Flash Encryption were observed disabled, and OTA0 remained selected
at 0x20000. One Windows esptool v5.4.0 application-only write at that offset
returned exit 0 and Hash of data verified; only sectors
0x20000..0x64000 were written. No bootloader, partition table, OTA metadata,
OTA1, journal, eFuse, C8 or C3 was operated on.

One 15-second console observation failed on an incomplete READY frame before
sending commands. In the following single-open session, no full READY was
observed, so direct runtime digest verification is NOT_OBSERVED. The session
inherited the exact install identity receipt and obtained fresh
nonce-correlated responses. Auxiliary tests passed for fragmented OBSERVE,
malformed/oversized rejection and recovery, sequential ordering, PSA RNG,
valid RSA-3072/SHA-256 signed-time verification, replay rejection, mismatched
nonce, invalid signature, expired proof and stale generation.

A private orchestration-script fixture-path error caused its raw session bundle
to label the prior 855b586d... image. The original is preserved. A separate
private reconciliation record binds the session to the immediately preceding
verified write receipt for fd072a..., and states the limitation that no target
READY digest was observed. It does not fabricate fresh image verification.
Its hash and the original result/raw-record hashes are recorded in
GS68_USB_OBSERVER_RETEST_PLAN_v1.0_20261017.md.

Auxiliary TEST_ONLY USB + PSA/RSA diagnostic: PASS with inherited
source-bound install receipt and disclosed runner metadata reconciliation.
Reset-safe COM opening: NOT_QUALIFIED; COM owner attribution remains UNKNOWN,
driver DTR/RTS transitions are unobservable, and reset-versus-buffer behavior
is unresolved. Official GS-68/GS-40 physical acceptance, silicon DS signing
and live mTLS remain NOT_RUN. No production network/credentials, security
eFuse or protected C8/C3 access occurred. Full redacted evidence is in the
linked retest plan; restricted raw artifacts remain in the private local
evidence directory. Next: correct the orchestration fixture binding for any
future session; do not repeat the completed diagnostic. For formal GS-68/GS-40
physical acceptance, obtain the required security-provisioning approvals and
run the official cases on exact-image-bound evidence.

After recording the result, the restricted auxiliary-session orchestration
script was corrected to use the stack-8192 fixture and to reject mismatched
build/install receipts before PnP or serial access. Its syntax check passed;
this guard was not used for the already completed session and was not followed
by another device access. See the dated evidence addendum for the distinction.

### GS-40 real-target qualification resume — 2026-10-18

Resumed on canonical `feature/r1-commercial-baseline` from local/origin
`65caf93df0011e6de29fb3d0e6310334b4e09036`; context preflight passed. The
unrelated GS-177 validation remained active in its separate worktree and was
not interrupted. All pre-existing untracked PWA/Android, managed components,
GS-114/C8 and GS-40 evidence were preserved.

Source audit confirms configured C3 heartbeat 300 s / strict offline after
910 s, trusted legacy 60/190 and 120/310 support, HubRuntime authenticated
contact and silent lease-expiry publication through the bounded CloudSync
worker, authenticated backend NodeHealth ingest/read model, and caregiver
ONLINE/OFFLINE/UNKNOWN projection. Test-only identity/time, local TLS,
backend and caregiver path tests pass. Product S3 `app_main` still instantiates
`UnprovisionedS3CloudTrust`; commercial CloudSync stays fail closed. The
2026-10-17 C3/S3 app hashes (C3
`b4e2b1c1d370fd2da2a30aae52cfbc2f85e91d0ff3b39da41eef23816829fedb`, S3
`e09e9651160719673958fffdc5c06f7a1787eb31403384324fd421b8f15a3ea1`) are
build candidates, not verified current installed images. Canonical config raw
SHA-256 is `2e42da92784c6eed807d8df240d1c33a178c1c088a568cbf9cb6d5d20817aadb`;
generated effective-config SHA-256 is
`fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862`.

Focused results: GS-40 C++ 1,320 checks; config/simulation 17 tests;
qualification runner 17 tests; mTLS adapter 9/9; cloud trust 5 suites;
identity/time/NodeHealth/caregiver local TLS 4/4; GS-168 issuer 10/10;
NodeHealth backend 5/5; caregiver JS 25/25; board-stack E2E 10 cases / 398
checks; CloudSync security simulation 18/18; local TLS worker/API bridge 1/1;
traceability 22/22 and physical catalogue 108 cases PASS. Full details and the
new caregiver status assertion are in
[`GS40_REAL_TARGET_EXECUTION_20261018.md`](../exec-plans/evidence/GS40_REAL_TARGET_EXECUTION_20261018.md).
The existing aggregate P0 `product_status=PARTIAL` and Hub `clean migration
commits` assertion failure remain unchanged.

The only source edit adds test coverage for caregiver ONLINE/OFFLINE/UNKNOWN,
coverage-UNKNOWN on offline or stale source, and the distinction between no
activity and no sensor coverage; the existing GS-130 traceability row was
updated. No product behavior or firmware changed. No target build was needed.
`git diff --check`, focused JS, traceability and physical-catalogue checks
passed.

No PHY-GS40-01..06 case was run. Historical GS-114 C8-P1/P2 and HIL-A03 remain
reusable only for their recorded image-scoped timer wake, authenticated Hub
contact, real event/durable ACK, and one 300-second opportunity; they do not
establish current image, six-opportunity cadence, 910-second offline, mixed
profile or caregiver physical acceptance. C8 and C3 were not accessed. TC05
requires a second independently enrolled C3 or approved profile fixture.

Minimum isolated TEST_ONLY physical path gap is distinct from commercial D05/
D12/D06 approval: the current product S3 composition still selects the
unprovisioned provider, so a reviewed TEST_ONLY-only runtime composition,
isolated local endpoint/issuer/time authority and test credential source are
needed before a physical end-to-caregiver run. No production DS/eFuse/CA is
required for that isolated test, but exact C3/S3 fixture, image/config/session,
observer/recovery method and fixture-specific operation authorization remain
required. Physical work was not authorized for the protected C8/C3 in this
execution. GS-40 and relevant dependency Jira comments record this boundary.

Next action: implement/review the TEST_ONLY-only S3 product-runtime composition
and source-bound build for the existing GS-168 issuer and signed-time contract;
then obtain a specific isolated C3/S3 fixture and operation authorization,
with a second enrolled Node/profile fixture for PHY-GS40-05. Do not activate
commercial trust or reinterpret GS-68 spare diagnostic results as GS-40.

Delivery receipt: source/evidence commit
`2a7c2f3a5371118524df25058f6e04c72f5b7b2a` was pushed normally to
`origin/feature/r1-commercial-baseline`. Jira comments were added to GS-40
`11360`, GS-109 `11361`, and GS-148 `11362`; no workflow status changed.

### GS-40 TEST_ONLY software-key transport continuation — 2026-10-18

Canonical source began at `eef0152e5844eeb548a3b8d44d3cb8a05d06bf02`, local
and origin equal; context preflight PASS. The full product S3 runtime still
constructs `UnprovisionedS3CloudTrust`. Added an explicit build-guarded
TEST_ONLY RSA-3072 software-key path to the existing trust/HTTPS abstractions;
it verifies certificate/key match and requires current authenticated Home/
epoch, active credential, and trusted time. The full product runtime is not
yet wired to a target-side GS-168/ownership/time material source, so this is a
transport/provider capability, not a credential-ready image or completed
runtime composition.

Current focused validation: `cloud-trust-provider-test` and
`cloudsync-security-ut` PASS (provider 5 suites, production DS adapter 9/9,
TEST_ONLY adapter 5 assertions, local security 14/14, GS-40 TLS end-to-end
4/4, GS-168 10/10, NodeHealth 5/5); GS-40 Hub 1,320 checks, profile/simulation
17/17, qualification 17/17, board E2E 10 cases/398 checks, caregiver JS
25/25; CloudSync security simulation 18/18 and local worker/HTTPS bridge 1/1;
traceability 22/22 and physical catalogue 108 cases. All physical status is
NOT_RUN. No physical fixture was accessed, and no production
credential/endpoint was used. A non-flashing ESP-IDF 6.0.3 S3 full-product
profile build with `GS40_TEST_ONLY_CLOUDSYNC=ON` then passed at commit
`2427622b44796779b3c0730d4da6baeebcde7835`: 2,164,512-byte app,
SHA-256 `9444365b32aab0a78a357f94fcdcd5538bb977eea52b5ff63fbcfc8f8c78f2bb`;
effective sdkconfig SHA-256
`8bff1b0e2cb4ff7f109e22a4962ef9d6e79ba50da42e44e9316bf14093b8f9fa`.
It is compile-only transport capability: the selected product runtime remains
`UnprovisionedS3CloudTrust`, and no test credentials, binding or endpoint were
supplied. Thus runtime startup composition and target publication remain
unimplemented and unclaimed. P0 remains PARTIAL and the existing Hub
`clean migration commits` failure is unchanged.

Full evidence and exact remaining source/configuration requirements:
[`GS40_TEST_ONLY_TLS_PROVIDER_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_TLS_PROVIDER_20261018.md).
The next step is the TEST_ONLY target material/runtime source plus isolated
test-network configuration, then a source-bound S3 product build. Physical
PHY-GS40-01..06 requires explicit fixture-specific authorization; TC05 also
requires a second enrolled C3 with a trusted legacy profile or approved
profile fixture. The C8/C3 and GS-68 spare remain untouched.

Delivery checkpoint: provider code commit `2427622b44796779b3c0730d4da6baeebcde7835`
and build-evidence commit `dc7c93760ec35853f0fb0e569f60341f7e76ba0b` are on
`feature/r1-commercial-baseline`; origin matched dc7c937 after push. Jira
comments: GS-40 `11366` plus compile-evidence correction `11369`, GS-109
`11367`, GS-148 `11368`. Tracked files are clean; pre-existing untracked PWA,
Android, managed-component, GS-114/C8 and GS-40 physical evidence remain
untouched. No board, serial port, production endpoint or credential was used.

## GS-40 TEST_ONLY product-runtime integration resumption — 2026-10-18

Canonical source was `58487978988b609917f4d021d01480ab87bc220a`, branch
`feature/r1-commercial-baseline`, local and origin equal before work. Context
preflight PASS. Existing untracked PWA, Android, ESP-IDF managed components,
GS-114/C8 and GS-40 evidence were preserved; the active GS-177 C3 build in its
separate worktree was left untouched.

The product S3 startup remains on `UnprovisionedS3CloudTrust`. The bounded
NodeHealth scheduler/CloudSync worker, `ProvisionedS3CloudTrust`, signed-time
verifier/state machine, GS-168 TEST_ONLY issuer/registry, backend model/API and
caregiver projection are present, but the full target composition is missing
an authenticated target material/ownership refresh source, signed-time proof
bootstrap transport/configuration, and isolated Wi-Fi/config source. GS-D032
leaves those mechanisms open; the latest GS-40/109/148 comments
11369/11367/11368 confirm the target-side source gap. No insecure authority or
time fallback was added. Detailed disposition and required contract inputs:
[`GS40_TEST_ONLY_RUNTIME_COMPOSITION_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_RUNTIME_COMPOSITION_20261018.md).

Validation executed: provider 5 suites; mTLS adapters 9/9 and TEST_ONLY 5
assertions; backend security 14/14; GS-68/GS-40 issued-identity NodeHealth and
caregiver TLS E2E 4/4; GS-168 issuer 10/10; NodeHealth 5/5; GS-40 liveness
1,320; timing/configuration 17/17; qualification runner 17/17; board-stack
simulation 10 cases / 398 checks; caregiver JS 25/25. The combined command
found a stale duplicate traceability command for GS40-NODEHEALTH-CLOUD-001;
after correcting the row, `make -C code feature-coverage-test` passed with 208
features, 220 modules, 24 physical cases and 22/22 mapping tests. No target
source changed and no new image was built. Prior image
`9444365b32aab0a78a357f94fcdcd5538bb977eea52b5ff63fbcfc8f8c78f2bb` is still
compile-only transport capability, not an integrated candidate.

GS-40 remains In Progress; PHY-GS40-01..06 remain NOT_RUN, and PHY-05 still
requires a second independently enrolled Node/profile fixture. P0 remains
PARTIAL and the existing Hub `clean migration commits` failure is unchanged.
No physical, serial, production endpoint, credential, eFuse or security
operation occurred. The next action is to supply/approve the target TEST_ONLY
provisioning, current Home/epoch refresh, signed-time bootstrap and network
configuration contracts; then wire the existing providers and build a new
source-bound S3 product image.

## GS-40 TEST_ONLY bootstrap decision boundary — 2026-10-18

At canonical checkpoint `f8dc5ca44cdf4fabf85f481fa269d1c14112a62e`, branch
`feature/r1-commercial-baseline`, local and origin matched and context preflight
passed. Tracked state was clean before this documentation update. Existing
untracked PWA, Android, ESP-IDF managed components, GS-114/C8 and GS-40
evidence were preserved. The concurrently running Hub validation/sanitizer job
was identified in `/home/udaybhan/projects/Ghar_sajag_hub_sim_gs177` and left
untouched.

No code or interface implementation can safely compose the product runtime
until the three target inputs are selected: isolated runtime configuration,
pre-TLS authenticated-time bootstrap, and fresh GS-168/current Home+epoch
credential authority. GS-D032 leaves their mechanisms open. A bounded
`GS40T/1` proposal was recorded as PROPOSED (not approved/LOCKED) in
[`GS40_TEST_ONLY_BOOTSTRAP_DECISION_PROPOSAL_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_BOOTSTRAP_DECISION_PROPOSAL_20261018.md)
and the Decision Log. It reuses existing issuer/ownership/time/CloudSync seams,
defines its trust roots, signed encrypted lab configuration, UDP signed-time
bootstrap, mTLS current-authority refresh, freshness limits, threats, failure
behavior and acceptance tests. It explicitly does not claim production key
custody, device attestation, or malicious flash rollback resistance.

Validation for this documentation-only decision proposal: `git diff --check`
PASS. No source, tests, image, target, physical fixture, serial port, production
credential or endpoint was changed or accessed. Prior host integration results
remain as documented in the runtime-composition evidence; they do not verify
S3 product runtime. No tests or firmware build were repeated. GS-40 stays In
Progress; physical PHY-GS40-01..06 remain NOT_RUN; P0 remains PARTIAL and the
Hub `clean migration commits` failure remains open. Next action: approve or
replace the complete `GS40T/1` interface contract; after that, implement the
target adapters/composition and run the registered focused integration gates.
Proposal comments are GS-40 `11374`, GS-109 `11375`, and GS-148 `11376`;
the three Jira issues remain In Progress / unchanged.

## GS-40 TEST_ONLY S3 runtime composition checkpoint — 2026-10-18

After task-specific authorization for bounded TEST_ONLY engineering, canonical
source commit `8bd9cf3` adds the guarded target path: authenticated bounded
`G40E` USB fixture envelope, isolated Wi-Fi/backend material, existing signed
time proof verifier over an untrusted UDP carrier, a TEST_ONLY mTLS bootstrap
identity, signed current-authority lease validation, and S3 owner-task
composition with `ProvisionedS3CloudTrust` and the existing CloudSync worker.
Commercial builds remain on `UnprovisionedS3CloudTrust`. The GS40T/1 decision
proposal remains PROPOSED/not LOCKED; no commercial security mechanism was
approved. A GS-116 registry correction is commit `0d7a5f0`.

The TEST_ONLY ESP-IDF 6.0.3 S3 product-profile build passed from source commit
`8bd9cf3`: image 2,187,584 bytes, ESP-IDF image validation hash
`a4ac8be74997e0b5b1e1f993eb7707e757adaf2fd2d838fcf8ccceed0894ebc6`, artifact
SHA-256 `d8df7d807059d65f37e5cf1b4df687234126418239f110cbaccb71f98305ded7`,
effective sdkconfig hash `3750bc9360e4524d61d8209e2cbe7014f67be9ee55dcb553033bcc9858c83099`,
and TEST_ONLY defaults hash
`7339aa689a054a849ac14d29c0eb79de543d966a6440c18c8467ead4756cd073`. It fits
the existing 0x400000 app partition. These are build facts, not installed or
physical results. A clean non-TEST_ONLY S3 profile build also passed with
`GS40_TEST_ONLY_CLOUDSYNC=OFF`, empty TEST_ONLY root configuration, and
`GS40_TEST_ONLY_CLOUDSYNC_BUILD=0`: image 2,168,160 bytes, full artifact SHA-256
`c2c886ddee480b2363a7b50b7bdd58f45c3e19bc212ba8bd3a170de046e494bb`, image
validation hash
`9642656a2d35d17774b9f9e90b0f418b3ca956f5af787a241a5149b25d45617f`, ELF SHA
`57850c4ed02a35179b7db3557a1df9b60f5128e90fc54e043a3ff712b45c033a`, and
effective sdkconfig SHA `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`.
The commercial branch retains `UnprovisionedS3CloudTrust` and DS peripheral
support in its build config; this is not eFuse/device evidence. Build metadata
is app version `0d7a5f0-dirty`, with tracked dirt limited to documentation; the
firmware source inputs match the cited implementation/registry commits. Results
and full hashes are in
[`GS40_TEST_ONLY_RUNTIME_CHECKPOINT_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_RUNTIME_CHECKPOINT_20261018.md).

New TEST_ONLY bootstrap tests pass 29 checks. The focused suite passed cloud
trust 5 suites; mTLS 9/9 and TEST_ONLY 5 assertions; backend security 14/14;
existing identity/time/caregiver host integration 4/4; GS-168 issuer 10/10;
NodeHealth 5/5; GS-40 liveness 1,320; configuration 17/17; qualification
17/17; and feature coverage 208 features/224 modules/24 physical cases with
22/22 mapping tests. `make validation-framework-test feature-coverage-test`
passed 47/47 framework tests after the registered stage ownership was
corrected. Existing board-stack simulation 10 cases / 398 checks remains prior
evidence and was not repeated.

This does not yet demonstrate a composed S3-to-caregiver software E2E. No
fixture envelope sender, signed-time service, or backend
`/v1/test/authority/refresh` handler exists in the exercised local service; the
new S3 runtime was built, not executed. Existing localhost E2E tests exercise
the host identity/backend/caregiver path only. Product status remains PARTIAL;
the Hub `clean migration commits` assertion remains FAIL; physical PHY-GS40-01
through 06 remain NOT_RUN, and PHY-GS40-05 still needs a second independently
enrolled legacy-profile C3 or approved equivalent. No hardware, production
endpoint, credential, eFuse, DS key or security setting was accessed. GS-40
stays In Progress.

### Canonical writer handoff

After the evidence/doc commit and verified push, this GS-40 software checkpoint
is ready for a separate GS-177 integration session. The isolated
`Ghar_sajag_hub_sim_gs177` worktree and its branch were not read or modified and
remain unintegrated. The next session must inventory its tracked/untracked
changes against base `58487978988b609917f4d021d01480ab87bc220a`, exclude generated
`managed_components` and sensitive evidence, and reuse canonical HubRuntime,
replay/security, journal, NodeHealth and CloudSync code. Do not begin GS-104
R01–R09; keep GS40T/1 PROPOSED and unapproved for production. Pre-existing
untracked PWA, Android, managed-component and physical evidence in the canonical
worktree remains preserved.

Jira evidence comments for this checkpoint: GS-40 `11379`, GS-109 `11380`,
GS-148 `11381`; all remain In Progress.

## GS-178 / GS-40 TEST_ONLY S3 linker fix — 2026-10-19

At canonical source HEAD `50fbb6886af07cb7412ec3dbe3531e6692b7c542`, the
isolated S3 TEST_ONLY image failed to link because ESP-IDF's embedded asset
symbols were derived from the external DER filename (`config-root.der`) while
the guarded runtime referenced fixed `gs40_test_config_root.der` symbols.
Commit `26e49162071975873881e88294216d08fe5e20c7` copies only the externally
supplied public TEST_ONLY DER into the build-local stable basename before
embedding. The TEST_ONLY S3 product profile now builds and passes ESP image
validation; image SHA-256 is
`1f247cbcdbe1bbc326b5224abf18c2fdb377a9005c37724b4f48e08be50430d8`, image
validation hash
`1e9cf8c57ab03ee3a5f6415f58b3749b4be8e619aa1637822d5136924cd406d5`, size
2,211,104 bytes, and app descriptor `26e4916-gs40t1`. Effective sdkconfig SHA-256
is `e18bccdaf876c0442ff6119d9d8dac49ed67cde964cf4f8c9281edb9eeb7f065`; the
4 MiB OTA application partition has 1,983,200 bytes free. The exact external
root/embedded bytes match. Build evidence and validation commands:
[`GS40_TEST_ONLY_S3_LINKER_BUILD_20261019.md`](../exec-plans/evidence/GS40_TEST_ONLY_S3_LINKER_BUILD_20261019.md).

Focused validation: `make -C code gs40-test-only-bootstrap-test` PASS 33;
`make -C code cloudsync-security-ut` PASS (mTLS 9, TEST_ONLY mTLS 5, Cloud
Trust 5 suites, backend security 14, identity/time 4, GS-168 issuer 10,
NodeHealth 5); ESP-IDF 6.0.3 `reconfigure build size` PASS; esptool image-info
PASS. The existing GS-178 27/27 software E2E remains valid and was not rerun.
The existing production-profile build uses TEST_ONLY OFF/macro 0 and
`UnprovisionedS3CloudTrust`; no production composition change is made.

This is target build evidence only, not S3 execution or physical acceptance.
The previously reported GS-178 host-simulator target-side atomic rule-decision
checkpoint and trusted-minute gaps remain. Existing Hub migration failure,
P0 `product_status=PARTIAL`, PWA failures/budget, Android APK NOT_RUN and
GS-40/GS-117/GS-121 physical acceptance NOT_RUN remain unchanged. No board,
serial interface, production service, credential or eFuse was accessed.

## GS-179 live Cloud-to-Android integration checkpoint — 2026-10-19

Canonical `feature/r1-commercial-baseline` was at
`3c0fec898d5cb2caae662f3dcc6324faaabf6b30`, equal to origin, with context
preflight PASS. GS-179 was moved to In Progress. The current public Render
staging service is still on the canonical commit with auto-deploy disabled. Its
WSGI composition serves synthetic `/lite/v1` only; a deployed
`GET /v1/homes/gs179-test-probe/snapshot` returned 404 and unauthenticated
`/lite/v1/me` returned 403. The current app does not mount the GS-148 durable
API or a genuine Hub-event caregiver projection.

Render's public web-service ingress terminates HTTPS before the application and
forwards HTTP to Gunicorn. The existing GS-148 identity verifier requires an
actual verified TLS 1.2 client peer socket to construct `VerifiedHubContext`; no
such peer reaches the WSGI app, and caller-controlled identity headers cannot
substitute. Secure live Hub ingestion is blocked on this deployment boundary.
Do not mount the durable API there until a trusted mTLS ingress is supplied or
a new signed-request security contract is reviewed and approved. The smallest
safe alternative and actual observations are recorded in
[`GS-179 Render ingress evidence`](../exec-plans/evidence/GS179_RENDER_INGRESS_BLOCKER_20261019.md).

The Render PostgreSQL service reports available, but the read-only SQL connector
cannot reach it because its external IP allowlist is empty; no DB setting was
changed, and no schema/persistence result is claimed. A first `/readyz` client
request timed out, but subsequent Render logs report 200 responses; treat that
timeout as inconclusive. Existing GS-178 host E2E 27/27 and GS-177 Android CI
success are prior evidence only. No source-linked Node event, live PostgreSQL
COMMITTED receipt or caregiver-visible real monitoring record was executed.
GS-179 stays In Progress; GS-177, GS-148, GS-59 and GS-40 remain in their
current statuses. `LIVE_STAGING_SOFTWARE_E2E_PASS=NO`; phone real-data and all
physical acceptance remain NOT_RUN. The next action is to provide an
already-authorized direct mTLS-capable isolated backend ingress and database
network path, or approve a new request-authentication contract for review. No
source/API/database/service/deployment change or hardware action occurred in
this checkpoint.

## GS-179 local WSL2 caregiver validation host — 2026-10-20

Following GS-179 owner decision comment 11452, the existing Windows 10/WSL2
laptop is configured as the no-cost, same-trusted-Wi-Fi validation host. The
canonical GS-148 caregiver HTTPS API and PostgreSQL run through an enabled WSL
user systemd service. PostgreSQL listens only on WSL loopback with TLS
`verify-full`, SCRAM app credentials, `fsync=on`, `synchronous_commit=on`, and
`full_page_writes=on`. Windows forwards only the current private Wi-Fi address
TCP 443 to the active WSL address TCP 8444. The Windows firewall allow rule is
restricted to the Wi-Fi interface, exact local address and current Wi-Fi
subnet. No router port-forward, public service, Render change, production
credential, hardware or physical operation was used. Operational evidence and
phone checklist are in
[`GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md`](../exec-plans/evidence/GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md).

The current LAN Android profile is opt-in and debug-only. It embeds only the
public TEST_ONLY CA (`CA:TRUE,pathlen:0`, `keyCertSign,cRLSign`), uses a
runner-generated debug key, and limits Android network trust to the exact
configured LAN IP. The build runner checks the CA constraints and the exact
origin-to-domain trust binding. Ordinary debug and release profiles keep the
public-DNS origin policy and do not load this CA. The local
server leaf was rotated after finding its previous CN-only certificate lacked
an IP SAN; the replacement has the exact IP SAN and passed OpenSSL IP/chain
verification and live HTTPS readiness. CA and private keys remain outside Git.

The local source-linked host path has one authenticated GS-178 Node motion
EventKey admitted through the existing TEST_ONLY mTLS listener, a matching
GS-148 `COMMITTED` receipt, exactly one durable PostgreSQL row and the same
caregiver timeline record. Service restart preserved it. Stale source was
projected as UNKNOWN and a later authenticated NodeHealth refresh restored
ONLINE/COVERED. The live canonical PWA browser check passed against laptop
HTTPS, including exact EventKey, room, current source, Node status and reload
without duplication. Focused connected-Lite API tests passed 15/15 and PWA
runtime tests passed 8/8. `pwa-68-browser-test` was 0 run / 1 skipped because
system Chromium is absent; the dedicated cached Playwright executable did run
the focused laptop browser scenario successfully. The explicit local-LAN
Android workflow passed as run 39326071201 on source commit
`b8af8b37f3de4334a672588e5f5c8fad0dd855d4`. It ran the PWA browser/offline
stage, registered API 15/15, Android dashboard 7/7, voice prototype 21/21,
`:app:testDebugUnitTest`, `:app:assembleDebug` and APK v2 signature
verification. The 2,913,584-byte local-LAN debug APK SHA-256 is
`6935f71d06c38087f09b2bf95c6a216e4dae30836449e367c773e7afa65eab42`;
artifact ID `12222706843`. Build metadata pins origin `https://192.168.1.6`
and local TEST_ONLY profile, and reports CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
The CI build uses a runner-generated debug key. APK build/signature and
software tests are not phone acceptance.

Current state remains software-only: phone acceptance and C3/S3 target/physical
acceptance are NOT_RUN; mobile-data/VPN use is unconfigured; Render remains
untouched and `LIVE_STAGING_SOFTWARE_E2E_PASS=NO`. The continuous WSL service is
HTTPS caregiver API plus PostgreSQL; existing host simulation invokes the
application-terminated TEST_ONLY Hub mTLS listener with ephemeral credentials,
not a persistent physical-Hub ingress. GS-179 remains In Progress. Existing P0,
migration, product PARTIAL and release blockers remain unchanged.

### Caregiver login self-service — 2026-10-20

Added `code/tools/local/gs179-laptop-server.sh change-login` for the existing
laptop TEST_ONLY caregiver account. It verifies the private credential file,
current database password, active account, and matching TEST_ONLY Home
membership/epoch; uses the existing Scrypt hash; atomically changes the same
PostgreSQL account and revokes its active sessions; and atomically refreshes
the existing private login JSON. A private pending envelope enables fail-closed
reconciliation if the process stops between database commit and file promotion.
No live caregiver account, event, Home membership, role, or monitoring data was
modified during implementation.

Focused login-change tests passed 5/5 in SQLite and 5/5 against isolated schemas
on the existing TLS PostgreSQL service. The registered connected-caregiver gate
passed: 20 API tests, 8 browser-runtime tests, lab build, and three host
scenarios. Exact commands and limits are recorded in
[`GS-179 caregiver login change evidence`](../exec-plans/evidence/GS179_CAREGIVER_LOGIN_CHANGE_20261020.md).
GS-179 remains In Progress; phone acceptance and physical C3/S3 acceptance
remain NOT_RUN.

### GS-177 / GS-179 authenticated Home event visibility — 2026-10-20

At canonical source commit `45efec6a051cda87732888ba88097b381ceeb57d`, the
Connected Lite Home was changed to use the established Parivar Saathi PWA
hero/cards/timeline against the current authenticated GS-148 caregiver
projection. Devices, Reports, Settings and other existing tabs remain. The
floating bottom pill is now an accessible full-width strip directly below the
app header. Source provenance and stale freshness remain visible; stale or
unrecognized source data fails closed to UNKNOWN/unavailable, with no
simulator fallback.

The live WSL laptop browser observed the already committed
`test-c3-bedroom` HOST_SIM event exactly once, with its EventKey, room and source
time. It was labelled `HOST_SIM · TEST_ONLY`; Hub/source freshness was stale and
monitoring/Node state were UNKNOWN. No event or health record was inserted by
this work. The existing caregiver account has CAREGIVER role; its direct
Engineering request returned 403 and the tab stayed hidden because the existing
route requires ADMIN plus TEST_ONLY. No role was elevated. A decision to grant
that account the existing TEST_ONLY Engineering permission remains for the
owner.

Focused validation: caregiver runtime 8/8; registered browser stage 4/4 with
92/92 catalogue assertions; registered component adjudication PASS; PWA
frontend 1/1; feature coverage 217 features / 257 modules / 25 physical cases
with 22/22 mapping tests; live laptop read-only browser `HOST_SIM_PASS`;
`git diff --check` PASS. Android local assembly reached the build step after
PWA runtime 8/8 and stopped with exit 127 because Gradle is absent from WSL.
The existing Actions workflow succeeded as run 39371372388 and assembled a
2,914,926-byte signed debug APK (SHA-256
`d36eab8982a655fbb6678eb7124c46c3e289b8681beb4b0452ead1809c14eab1`, artifact
12241890946). It used the default Render origin with
`GS177_LOCAL_LAN_TEST_ONLY=0`, so this build is not the laptop-connected APK and
must not be installed to test the current laptop event. Physical phone, Node
sensor, Hub publication and GS-117 E2E acceptance remain NOT_RUN. Exact
evidence and dependency boundaries are in
[`GS177_GS179_HOME_EVENT_VISIBILITY_20261020.md`](../exec-plans/evidence/GS177_GS179_HOME_EVENT_VISIBILITY_20261020.md).

The WSL-bound HTTPS listener passed certificate-verified `/readyz`; the
existing Windows Wi-Fi forwarding endpoint on TCP 443 currently refuses the
connection. No forwarding/firewall rule was changed. A LAN-configured APK can
be built from the existing workflow, but the phone cannot reach this laptop
until the already-approved scoped forwarding is restored and health-checked.

This does not close GS-40/58/68/109/148/117. Actual C3 authenticated motion,
current S3 Hub health/authority, and a persistent application-terminated mTLS
ingress to laptop PostgreSQL have not been observed. Production identity,
credential and eFuse approvals remain separate. GS-177 and GS-179 stay In
Progress; GS-117 physical acceptance stays NOT_RUN. No phone, board, serial
port, production endpoint, database row, login, or device state was modified.

### GS-58 / GS-165 canonical integration and regression closeout — 2026-10-20

GS-58 and GS-165 source histories are integrated into canonical through merge
commits `de1ec0a4c1cec3907e04efd2fc91cd0b43f7aad8` and
`c60828b264bdb8d4d562a614b2126c7d211a8037`. GS-177 source is already an
ancestor; no duplicate merge was performed. A source-level feature audit
confirmed one shared `IndiaWifiProfileV1` for C3/Hub, reuse of the existing
authenticated C3 rejoin and GS-168 TEST_ONLY issuer, and preservation of the
current GS-177 authenticated Home, docked navigation, other tabs, caregiver
role, and freshness behavior. The narrow Home correction distinguishes Hub
decision IDs from Node EventKeys.

Focused current-source results: GS-58 Wi-Fi 77 checks; GS-165/GS-168 24 tests;
GS-178 29/29; connected caregiver API/runtime 20 API + 8 runtime; browser 4/4
with 92/92 catalogue assertions; PWA frontend 1/1; framework 51/51 and feature
mapping 22/22. Non-flashing ESP-IDF 6.0.3 production C3/S3 builds passed at
940,608 and 2,193,248 bytes, respectively. Image and sdkconfig hashes and the
full validation record are in
[`CANONICAL_GS58_GS165_GS177_INTEGRATION_20261020.md`](../exec-plans/evidence/CANONICAL_GS58_GS165_GS177_INTEGRATION_20261020.md).

The requested `make -C code validation-fast` completed with 79/83 stages PASS
and exit 2. Its four failures were: the existing Hub migration assertion
`clean migration commits`; an incomplete zero-byte sanitizer object that
caused unresolved `RuntimeStateStore` symbols; a registry expectation missing
the integrated `gs58-wifi` and `pilot-factory` stages; and P0 `product_status=PARTIAL`
despite 26/26 scenario checks. The host object build now atomically promotes
completed objects and selectively rebuilds zero-byte objects; the sanitizer
target passes. The diagnostic registry assertion now expects the two
additional stages and passes 6/6. The full fast gate was not repeated after
these focused corrections. Thus Hub migration and P0 PARTIAL remain blockers,
and the recorded aggregate fast run remains FAIL. No release gate was run.

At final integration checkpoint canonical local and remote HEAD is
`bbf073f775aca138d84092b916d005653eab8ae3`; the tracked worktree is clean.
PR #1 and #2 are closed/merged at the existing GS-58 and GS-165 merge commits.
Jira comments 11474–11478 record GS-58, GS-165, GS-177, GS-116 and GS-130
integration/validation outcomes. The inactive GS-58 and GS-165 worktrees were
fast-forwarded locally to canonical after dirty/process checks; their feature
refs were not pushed. GS-58's untracked `managed_components/` and all canonical
untracked app assets, IDF files and physical evidence remain preserved.

The validation-fast report remains 79/83 PASS, exit 2; no full rerun followed
the focused repairs. The sanitizer link issue and missing integrated-stage
registry expectation passed focused revalidation. Hub migration
`clean migration commits` and required P0 `product_status=PARTIAL` remain
unresolved. GS-58 D1/D2, commissioning/channel qualification, GS-165
production/physical QA, GS-177 phone acceptance, GS-40/117 physical cases and
other release/security gates remain incomplete. No commercial readiness or
physical acceptance is claimed.

## GS-179 / GS-59 bounded mTLS ingress hardening — 2026-10-20

At source checkpoint `29cdc43f569a9a512e68e073cb85aa3ebc0eebbd`, the existing
application-terminated `TestOnlyMtlsListener` was hardened without composing
or starting it in the persistent laptop caregiver unit. Listener construction
now requires backend-readiness and aware trusted-time providers that pass
before socket creation; both are rechecked per request. Default bind remains
loopback, private IPv4 requires explicit TEST_ONLY opt-in, wildcard/public
bindings fail, TLS handshakes run in bounded connection workers (8 default,
32 maximum) with socket timeouts, and close has a bounded drain with no restart
after close. Certificate-derived Hub identity, current ownership/epoch
authorization, GS-148 PostgreSQL commit and caregiver projection code remain the
existing implementations.

The registered isolated PostgreSQL integration passed 40/40 using GS-178's
production-code host stack and ephemeral TEST_ONLY credentials. Listener
regressions cover saturation/recovery/drain, startup and per-request readiness,
time failure, bind bounds and closed-instance behavior. Validation framework
passed 51/51; feature traceability passed at 221 features, 263 modules, 26
physical cases, with 22/22 mapping tests. Python compilation and `git diff
--check` passed. This is HOST_SIM/TEST_ONLY software evidence, not a persistent
live service or physical Hub result. Exact details are in
[`GS-179 continuous-ingress audit`](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md).

The current laptop systemd unit remains stopped/failed because its Windows
forwarding `ExecStartPost` failed; its `ExecStopPost` stopped PostgreSQL. It
was not restarted, and no forwarding, firewall, address, account, credential or
database state was changed. Continuous live ingress remains BLOCKED pending an
authorized/recovered network route, ingress server/client trust material,
current enrolled TEST_ONLY Hub authority and a trusted-time source. GS-59 and
GS-179 remain In Progress. Physical cases and production credential/security
qualification remain NOT_RUN; Hub migration `clean migration commits` and P0
`product_status=PARTIAL` remain open.

## GS-179 laptop service recovery and read-only Windows diagnostics — 2026-10-20

The prior laptop-service failure is resolved on the Linux/WSL side. Root cause
was systemd `ExecStartPost=proxy-start`: the Windows portproxy/firewall action
correctly refused the non-administrator token, causing systemd to terminate
the caregiver service. Its unconditional `ExecStopPost` then stopped the
persistent PostgreSQL server, making later worker database/TLS errors
secondary. The corrected user unit has no automatic Windows network hooks;
failed application startup preserves PostgreSQL, while intentional clean stop
stops only the local database. Start/restart load the existing private
configuration and wait up to 30 seconds for verified local DB and HTTPS
readiness.

The existing PostgreSQL cluster started cleanly, with 13/13 migration records
present. A read-only TLS query after the isolated E2E run reported 6 households,
7 caregiver accounts, 1 existing event, 1 COMMITTED receipt, 1 NodeHealth row,
and no Hub decisions. E2E used temporary isolated schemas. No caregiver
account, session, Home, event, or private credential was altered. Local
PostgreSQL and caregiver HTTPS both pass readiness; repeated start and restart
also pass. This does not establish Hub ingress readiness.

Windows read-only audit observed Wi-Fi `192.168.1.3/24`, WSL NAT
`172.17.152.10`, and the existing mapping `192.168.1.6:443` to WSL TCP 8444.
There is no Windows TCP 443 listener. The server certificate and existing
LAN-origin configuration remain bound to `.6`; the expected address is not the
current Wi-Fi address. Firewall details were blocked by non-admin read
permissions, and router DHCP reservation/lease evidence was unavailable, so
`.6` availability is UNCONFIRMED. No Windows address, portproxy, firewall,
certificate, WSL networking or Android artifact was changed. Windows-to-WSL
TCP connected, but Windows Schannel reported unknown certificate revocation
status for the diagnostic HTTPS request; validation was not bypassed. Phone
LAN remains BLOCKED, Hub ingress remains NOT_CONFIGURED, and GS-117 phone/
physical acceptance remains NOT_RUN.

Focused results: registered local GS-179 PostgreSQL E2E 46/46; affected browser
scenarios 3/3; GS-179 lifecycle/security 14/14; validation framework 51/51;
traceability 221 features / 263 modules / 26 physical cases and mapping tests
22/22. `validation-fast` and `release-gate-final` were not run. Detailed commands,
readiness output, Windows limitations and the safe next address decision are in
[`GS-179 laptop service recovery evidence`](../exec-plans/evidence/GS179_LAPTOP_SERVICE_RECOVERY_20261020.md).
GS-179 remains In Progress; GS-59's event contract is unchanged. GS-117 phone
and physical acceptance remain NOT_RUN. The next step is confirmation from the
network owner that `.6` is reserved/available, followed by separate
authorization for any Windows networking update.

## GS-58 / GS-177 customer Wi-Fi onboarding software checkpoint — 2026-10-20

Canonical source adds a bounded S3 Hub Wi-Fi scanner and a guarded setup policy requiring current installer authority generation, a recent Hub-observed supported 2.4 GHz network and a verified protected atomic credential commit before reconnect. Android Settings now opens a native, bounded BLE discovery screen; device names are labelled unverified. No password collection or credential-bearing BLE session is enabled. The commercial target still has no approved D1 device-specific installer/Hub proof or D2 encrypted-NVS key/partition provider, and current Home/epoch cloud claim remains a separate GS-109/68/148 gate. Accordingly first-time setup, change-Wi-Fi, real S3/phone acceptance and commercial readiness remain BLOCKED/NOT_RUN. Existing GS-58 India profile, C3 rejoin and station retry semantics are unchanged. Exact code, tests, build status and handoff: [GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md](../exec-plans/evidence/GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md). No physical board, phone, Windows networking, PostgreSQL or production service was operated.

Implementation commit `1043827858609a1212e403ddf4d4494e90c6165e` and evidence checkpoint `ea94240c52a80d88709620a88248127bdb17250c` are pushed. Rechecked canonical branch and local/remote equality at `ea94240`; context preflight PASS, filesystem writable, `git fsck --no-reflogs` exit 0 with only dangling-object notices, tracked worktree clean before this documentation checkpoint. Host reconnect 77/77, onboarding 30/30 (normal and ASAN/UBSAN), caregiver runtime 9/9, app 34/34, validation framework 51/51 and mapping 22/22 passed. Android workflow `39437956269` SUCCESS after a single failed-job rerun: browser 4/4, catalogue 92/92, caregiver API 20, Android dashboard 9, voice prototype 26; downloaded debug APK 2,923,446 bytes, SHA-256 `6c12a4439636b0ea9f9a762cdf4f99d41b16fc4dc8f4c9fbb6674d7a9c83a757`, Render origin, not installed. No-flash ESP-IDF 6.0.3 S3 `idf.py build` verification exit 0; 2,191,664-byte image, full SHA-256 `5416a715fc3862977aed9584534c53c3b6726fa888599ee973930df67dee75c3`, image validation digest `d47429105d7b2499ffbb00963372a8408d2c0adfdb546e299ce59ba54affc38f`, effective sdkconfig SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`, standard profile `GS40_TEST_ONLY_CLOUDSYNC=OFF`, app version `ea94240`, source code tree `19f705568942d7e1e800fb67cc3b5ee30dd2992e`. Build verification reused the existing build tree and passed size checks; it did not access hardware. Local browser remains NOT_RUN because Chrome/Chromium is absent in WSL. Evidence and exact security/physical gates are in [`GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md`](../exec-plans/evidence/GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md). GS-58 and GS-177 remain In Progress; D1, D2, authenticated Home/epoch claim, actual BLE credential submission, S3/phone and commercial acceptance remain blocked/NOT_RUN.


## GS-58 Phase 2 D1/D2 secure onboarding decision checkpoint — 2026-10-20

At canonical source `e7f8a88631aab0f88686ee44bf9b5c4b2da67a1d`, context
preflight PASS and local/origin equal, the focused command
`make -C code gs58-onboarding-host-test` passed 30/30. No
source/provider/configuration was changed: current production source still has only the fail-closed authority
and protected-store seams, the bounded S3 scanner, and Android BLE discovery.
No live Security 2 session, per-device verifier, signed Home/epoch permit,
encrypted NVS provider/key partition or native credential-transfer adapter is
activated. Existing untracked assets and hardware evidence remain untouched.

The implementation-ready but unapproved proposal recommends Security 2 only,
per-Hub factory proof plus GS-109 one-use current-owner permit, and encrypted
NVS protected by the approved per-device Flash Encryption lifecycle with
two-slot/selector recovery. Exact alternatives, security assumptions, approval
matrix and target/host/Android acceptance plan are in
[`GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md`](../exec-plans/evidence/GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md#gs-58-phase-2-d1d2-implementation-decision-packet--2026-10-20).
No context version, product decision, commercial configuration or physical
acceptance status changed. GS-58/GS-177 remain In Progress; first-time setup,
change-Wi-Fi and real S3/phone qualification remain SECURITY_BLOCKED/NOT_RUN.

Next action: obtain the D1 Security 2 proof/factory delivery and GS-109 signed
permit/transfer-revocation decisions, plus the D2 Flash Encryption/NVS key
custody, partition and record-recovery decisions. Only then pin/add the ESP-IDF
6 managed provisioning component and Android library, implement target session
and encrypted-store adapters, and run the listed regressions/builds before any
separately authorized fixture test. The current untracked development
`sdkconfig` and partition configuration were not altered. No Windows/network,
production, eFuse, board or phone operation was performed.

## GS-58 Phase 3 secure onboarding software checkpoint — 2026-10-20

Added host-testable, fail-closed D1/D2 adapters in canonical source commit
`99142b8c3a939ff5a8875fe8c850d97eb7a66fa2` (`feature/r1-commercial-baseline`,
pushed). The two-slot credential backend verifies the inactive record before
selector commit and resolves ambiguous commit results only by reread. The
ESP-IDF encrypted-NVS adapter requires already-enabled Secure Boot and Flash
Encryption, the expected encrypted key/data partitions, and an injected
device-key fingerprint verifier; it creates no keys, erases no partition, and
is not initialized by S3 product startup. The one-use setup-permit gate binds
the injected GS-109 verifier result to the exact Security 2 session, Hub,
Home/epoch, operation, nonce, boot generation and bounded monotonic lease.
Credential reconnect notification is after protected commit and permit
completion. Android adds a unit-tested fail-closed native policy predicate;
existing Add Hub remains discovery-only, with no Security 2 transport, Hub scan
display, password entry or credential submission.

Focused validation on the implementation commit: credential-slot tests 18/18
normal and ASAN/UBSAN; setup-permit tests 30/30 normal and ASAN/UBSAN; existing
onboarding 30/30 normal and ASAN/UBSAN; reconnect 77/77; validation framework
51/51; traceability 222 features / 275 modules / 26 physical cases, mapping
tests 22/22. Paired ESP-IDF 6.0.3 C3/S3 builds completed without flashing. S3
profile is `GS40_TEST_ONLY_CLOUDSYNC=OFF`, 16 MiB flash, and 4 MiB app slot; the
2,193,248-byte image SHA-256 is
`79449e37837591c26ed1a05711a7b0c0fff24d5b24bf1236aff9b276dd19d138`, with
valid ESP image digest
`67664f95c2f06de2cbac603c89b08bb304a8a4df977eaf25fd9bdcd691ee70f3`. Effective
S3 sdkconfig SHA-256 is
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`; profile
cache SHA-256 is
`52219cd12310b54fbd3213748693fab754c0945575892058ef8ef34c4d599d9d`. The
paired C3 image is 940,608 bytes, SHA-256
`2401c650fc58e517bfdbcbc91950a4bbde72a94444c92928dd590eb1f545e0ec8`, and was
byte-compared to the embedded S3 asset. Build provenance, generated config
fingerprint and partition hash are in the linked evidence.

D1/D2 remain PROPOSED. The standard S3 profile leaves Secure Boot and Flash
Encryption disabled, so the new encrypted-NVS adapter cannot initialize. No
GS-109 signature verifier, device proof/key delivery, Security 2 target
transport, protected partition/key custody or Android credential path is
composed. No physical setup, phone test, eFuse/security operation or production
credential activity occurred. `PHY-GS58-WIFI-01` remains NOT_RUN; GS-58 and
GS-177 remain In Progress. Android Actions run `39479165553` completed SUCCESS
on the source commit, including registered Android unit tests, `assembleDebug`
and PWA browser 92/92. Its runner-generated Render-origin debug APK is
2,925,210 bytes, SHA-256
`a3dbd873a08936e120c388cce9a30f2e68f5810a09c641cf98fdaf62a91ac493`; it was
not installed on a phone and is not a laptop-LAN package.
The latest Phase 3 results and constraints are maintained in
[`GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md`](../exec-plans/evidence/GS58_CUSTOMER_WIFI_ONBOARDING_20261020.md).

## GS-58 Commercial integration hardening — 2026-10-21

Task branch `feature/gs58-integration-hardening-20261021` is isolated from the
canonical writer and is based on canonical `2b8dee5dc0494a06bcc34210cd08bdc63e6339b0`.
Implementation commit `47be1e3abcac54af37c4b5ea4407c9420b82372b` adds
idempotent recovery of an exact already-committed first Hub claim and stages a
Wi-Fi credential candidate without switching the active selector or starting
reconnect. The previous active credential remains selected through staging and
restart; explicit activation is a separate primitive and has no product-flow
caller. Transfer completion and initial-claim permit reservation remain
fail-closed because their GS-109 authority/data-disposition semantics are not
approved. D1/D2 stay PROPOSED; no Android, physical, key/eFuse, production
credential or network operation occurred.

Focused host validation recorded in the hardening evidence: onboarding 41
checks, credential slots 48, setup permit 33, reconnect 77, ownership lifecycle
8/8; the four C++ suites also passed ASAN/UBSAN. Framework 51/51 and traceability
222 features / 275 modules / 26 physical cases / mapping 22/22 passed. A paired
ESP-IDF 6.0.3 non-flashing C3/S3 build passed on committed source `47be1e3`.
The S3 image is 2,193,264 bytes, full SHA-256
`1cbda4501ac41bda39e0a47af3db75777f4bdaa4947bcddcaf24b6b4ad611b3e`, ESP
validation hash `200ac124511950950055512a1f99bcd3b21adf8ca7924e80f5b1ba0b48048f02`,
and effective sdkconfig hash
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. The
paired C3 image (940,608 bytes) and embedded C3 asset match at SHA-256
`38e12e4f730a5afabf017d4b6ba094b32afd54dd09515ebd396ade2251c8d610`. This
development profile has `GS40_TEST_ONLY_CLOUDSYNC=OFF`; Secure Boot, Flash
Encryption and NVS encryption are disabled, and the build is compile evidence
only. See
[`GS58_COMMERCIAL_INTEGRATION_HARDENING_20261021.md`](../exec-plans/evidence/GS58_COMMERCIAL_INTEGRATION_HARDENING_20261021.md)
for exact provenance and remaining gates. Jira comments: GS-58 `11499`, GS-109
`11500`. Evidence/work-state commit `600ffe8f9040fdf5b2594079f7e1782972e8a883`
was pushed to the authorized task branch and `git ls-remote` matched local at
that checkpoint. Delivery-note commit `ce751b8e261d1b0ef2344272ca15e9b5c86d2b5f`
was also pushed. Final local/remote task-branch equality is recorded in GS-58
comment `11499` and the execution handoff. Do not merge into canonical
automatically. GS-58 remains In Progress and physical qualification is NOT_RUN.

## GS-75 notification worker hardening checkpoint — 2026-10-21

The authorized GS-75 worktree is on
`feature/gs75-autonomous-notifications-20261020`. It was reconciled by normal
merge with canonical remote `5fd6fe0cb5e161f6e8d8e14e00f2d5f21c20747f`
(merge commit `fbf50fd8f2c2d3714cf5c468baaa7d1140b41aad`). Source/test and
GS-116/130 registry corrections are committed at `94b6167`; the detailed
source-linked evidence is in
[`GS75_AUTONOMOUS_NOTIFICATION_WORKER_20261020.md`](../exec-plans/evidence/GS75_AUTONOMOUS_NOTIFICATION_WORKER_20261020.md).

The worker now claims jobs just before processing, bounded to one row per
claim, and calculates retry deadlines from the actual provider failure
completion time. SQLite and PostgreSQL lease/retry tests, current authorization
checks, restart recovery and provider-boundary behavior passed. The registered
worker stage and traceability mapping are present. Focused backend regression
passed 50/50, isolated PostgreSQL integration 1/1, validation framework and
traceability checks 73/73, and feature mapping checks 22/22. Exact commands and
the initial missing-generated-binary setup error followed by its successful
recovery are documented in the evidence file.

GS-75 remains In Progress. PR #4 remains OPEN/DRAFT and is not merged. No
production provider, FCM credentials, Android notification delivery, phone
acceptance or commercial activation was executed. GS-74 owns the FCM provider
and authorized destination resolution; GS-177 owns native registration,
permissions and phone receipt qualification. Keep the worker disabled by
default and preserve provider acceptance as distinct from device delivery or
human acknowledgement. The GS-75 worktree and ignored build/cache artifacts
remain preserved.

### GS-75 PR #4 merge clarification — 2026-10-21

The preceding GS-75 checkpoint records the state before canonical integration.
PR #4 was subsequently merged into the canonical branch; the merge is present
at `ef352611528ea8ddd302229ef8371bd7528a8c61` (`feat(GS-75): integrate durable
autonomous notification worker (#4)`). The historical `OPEN/DRAFT` sentence
above is retained as an accurate checkpoint-time statement and is no longer the
current canonical PR status. This clarification does not reopen GS-75 work.

### GS-179 resumed software integration checkpoint — 2026-10-21

GS-179 remains In Progress and at its existing Jira Rank; GS-114 remains ahead
of GS-117 and GS-179. The authorized canonical fast-forward advanced
`feature/r1-commercial-baseline` from `2b8dee5dc0494a06bcc34210cd08bdc63e6339b0`
to `ef352611528ea8ddd302229ef8371bd7528a8c61`, exactly matching the verified
remote. The 25 incoming paths had no collision with pre-existing untracked or
ignored paths. The preserved counts were 301 untracked and 174,433 ignored
before and after synchronization. Context preflight passed before and after.

No new backend, listener, identity path, data model, caregiver view or Android
UI was needed or added. The TLS 1.2 TEST_ONLY listener, GS-148 durable
PostgreSQL API/COMMITTED behavior, and GS-179 Home-authorized caregiver
projection remain implemented and were reused. The remaining operational gap
is still `HUB_INGRESS_READY=NOT_CONFIGURED`: the laptop service does not compose
the listener and has no approved TEST_ONLY Hub credential/issuer artifacts,
trusted-time provider, current Hub/Home/epoch binding, or authorized Hub route.
The minimum safe runtime change cannot be completed without those approved
inputs; synthetic/persistent credentials, inferred time/authority, and network
activation were not introduced.

Focused validation on canonical source `ef352611528ea8ddd302229ef8371bd7528a8c61`:
`make -C code gs179-postgres-e2e` passed 47/47 after using the laptop's existing
private Python and libpq dependency paths (two earlier environment-only
attempts exited 2 at import/collection, 34 errors each). The suite included
production Node/Hub host simulation, authenticated TEST_ONLY ingress, durable
PostgreSQL commit/retry, restart, Home isolation, security negatives and
NodeHealth stale/UNKNOWN/recovery cases. The same source EventKey
`test-c3-bedroom / bedroom / session 10 / sequence 1` returned `COMMITTED`,
then an idempotent duplicate receipt; one logical row was asserted and the
event was read from its authorized TEST_ONLY caregiver Home.
`validation-framework-test` passed 51/51; `feature-coverage-test` passed with
223 features, 277 modules, 26 physical cases and mapping 22/22; laptop script
`bash -n` and `git diff --check` passed. Tests used host simulation and isolated
TEST_ONLY software, not target or physical hardware. The existing read-only
health probe reported local PostgreSQL, caregiver HTTPS and backend ready;
phone LAN reachability was `BLOCKED_CONFIG_MISMATCH`; Hub ingress remained
`NOT_CONFIGURED`.

Evidence and exact commands/correlation are in
[`GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md`](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md#canonical-fast-forward-and-resumed-gs-179-checkpoint--2026-10-21).
No product decision, release gate, source code, test registry, or physical
acceptance state changed. No real S3 authentication, real C3 sensor event,
Android handset observation, persistent ingress activation, firewall/route
change, or production trust operation occurred. GS-117 remains unaccepted;
GS-74 FCM is not a prerequisite for ordinary authenticated monitoring display.

Next action: supply/approve the existing TEST_ONLY credential registry and
client artifacts, trusted-time provider, current Hub/Home/epoch authority, and
authorized private route needed to compose and start the laptop listener. Then
validate authenticated Hub-to-caregiver flow in that runtime. Separately,
complete the GS-117 fixture/image/authority/network/reset-safe handoff before
any real PIR qualification. Do not infer physical or commercial readiness from
the host-simulation PASS.

### GS-179 default-disabled runtime implementation — 2026-10-22

This checkpoint supersedes the preceding GS-179 conclusion only for safe
software implementation. Live credentials, trusted-time configuration and
network route remain separate activation gates; they were not prerequisites to
implementing and testing an injected, default-disabled composition.

At task start, the canonical worktree and live `origin/feature/r1-commercial-baseline`
both pointed to `b7ef58a4cf595f35f692e7a1986aace2e3331580`, tracked files were
clean, and `tools/context/ghar_sajag_context_preflight.sh` passed at context
version `2026-10-13.001`. GS-179 remains In Progress at its existing Rank; GS-114
remains ahead of GS-117 and GS-179. No branch/worktree synchronization, cleanup,
credential activation, network mutation or physical operation was performed.

Reused the existing bounded application-terminated TLS 1.2 TEST_ONLY listener,
verified peer/GS-168 registry and current ownership checks, GS-40 authority
refresh, GS-148 PostgreSQL commit/NodeHealth/decision/read APIs, and the existing
Home-authorized caregiver projection. The minimum runtime composition is now
[`gs179_hub_ingress_runtime.py`](../../code/backend/ghar_sajag/gs179_hub_ingress_runtime.py).
It requires explicit TEST_ONLY configuration and injected credential registry,
trusted-time source and authority refresh; checks the registry CA fingerprint,
current configured Hub/Home/epoch and active Node enrollment, and verifies
loopback PostgreSQL with `sslmode=verify-full` and durable settings before
binding. It scopes ingress to one configured TEST_ONLY Hub, loops back only,
remains disabled by default, and is never started in WSGI/Gunicorn. The existing
laptop health command now reports runtime implemented, autostart disabled,
real Hub authentication `NO`, monitoring freshness `UNKNOWN`, and persistent
ingress `NOT_CONFIGURED` while retaining `HUB_INGRESS_READY=NOT_CONFIGURED`.

The registered [`test_gs179_runtime_composition.py`](../../code/tests/integration/test_gs179_runtime_composition.py)
executes the actual entry point in a separate process. Production-code HOST_SIM
Node input and CloudSync reached the listener over loopback TLS. Original
EventKey `{physical_device_id: test-c3-bedroom, logical_node_id: bedroom,
origin_session_id: 10, event_sequence: 1}`, source occurrence time, `MOTION`
type, bedroom, configured Hub/Home/epoch and one durable PostgreSQL row were
correlated. The first COMMITTED response was lost; after listener process
restart the exact retry returned duplicate COMMITTED without another row. The
authenticated caregiver Home read the same event before and after caregiver
API connection restart. New fail-closed cases cover disabled/incomplete config,
missing authority/time/TLS material, CA mismatch, stale epoch and unavailable
PostgreSQL; wrong Home is rejected. Existing GS-178/179 security tests retain
revocation, expiry, forged-header, body conflict, bounds, cross-Home,
NodeHealth freshness/UNKNOWN and recovery coverage.

Validation: `make -C code gs179-postgres-e2e` **50/50 PASS** (15 security, 18
Node-origin vertical, 14 PostgreSQL/security, 3 runtime composition); focused
runtime rerun **3/3 PASS** after the exact EventKey assertion;
`make -C code validation-framework-test` **51/51 PASS**;
`make -C code feature-coverage-test` **223 features, 278 modules, 26 physical
cases, mapping 22/22 PASS**. The full gate built and executed the production
HOST_SIM path against isolated schemas. The first feature-map attempt identified
that test/tool files were outside configured source inventory roots; the new
backend runtime is inventoried and test fixtures remain in the registry/trace.
The initial runtime subprocess attempt correctly exposed the missing GS-40
authority-refresh callback; it is now explicitly required and supplied through
the existing TEST_ONLY fixture. The detailed command/results and no-live-
activation limits are in
[`GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md`](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md#default-disabled-runtime-composition-implementation--2026-10-22).

Status: runtime implementation, isolated software integration, durable
COMMITTED, retry/restart and caregiver API readback are **PASS**. Persistent
laptop ingress remains **NOT_CONFIGURED**. Real S3 authentication, C3 sensor
input, Android handset visibility, GS-117 physical E2E and commercial release
remain **NOT_RUN**. Runtime source and validation were committed as
`acde2183c74351db403b49b441deea67a3474142` and pushed normally; the live
canonical remote matched that commit. Jira comment 11526 records the delivery.
GS-179 remains In Progress because persistent configuration and its broader
staging/phone acceptance remain incomplete. Next customer milestone is the
separate GS-117 physical qualification after owner-approved security,
authority, endpoint, network, fixture/image and recovery inputs. Do not claim
HOST_SIM as physical acceptance.

### GS-117 Android physical vertical readiness — 2026-10-22

GS-117 was moved from To Do to In Progress for the owner-directed first
real-sensor-to-Android milestone; its Rank was not changed (Rank 52, below
GS-114 Rank 31). The Jira inventory contains 173 issues. GS-60 remains To Do,
GS-121 remains downstream, and no physical acceptance state changed.

The current canonical checkout was `ec9076aa1326999de32d5ecc1e8ceb055cdff96e`,
equal to origin, with tracked files clean and context preflight PASS at
`2026-10-13.001`. The 301 existing untracked and 174,518 ignored assets were
preserved. A focused GS-179 runtime/test change now allows a private bind only
when `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1`, a specific RFC1918 IPv4
address, and a fixed port are explicitly supplied. The default remains
loopback and disabled; no listener or network was activated. The GS-130
`PHY-GS117` catalogue entry now names the Parivar Saathi Android APK as the
physical caregiver endpoint in accordance with GS-117/GS-177 owner direction;
browser checks remain supporting shared-UI evidence. The row remains
`NOT_RUN`.

Read-only WSL health reports local PostgreSQL and caregiver HTTPS ready, but
phone LAN reachability blocked: configured certificate/forwarding address
`192.168.1.6` differs from current Windows Wi-Fi `192.168.1.10`. The GS-179
Hub runtime is implemented and default-disabled, with loopback as default and
an explicit RFC1918 private-bind opt-in;
`HUB_IDENTITY_AUTHENTICATED=NO`, monitoring freshness is `UNKNOWN`, and
`PERSISTENT_HUB_INGRESS=NOT_CONFIGURED`. Render remains on
`3c0fec898d5cb2caae662f3dcc6324faaabf6b30` and cannot provide an application-
verified Hub TLS peer through its TLS-terminating proxy. The latest identified
Android APK is a debug TESTING artifact from source `acde2183c74351db403b49b441deea67a3474142`
targeting Render, not the laptop PostgreSQL backend; its APK SHA-256 is
`fa0a53b7f9cff822e27409701d7b60d78f142f08989d8362e672594d1f5e8c72`. The
owner-reported installation was not independently inspected on the phone.

Current physical C3/S3 identity and image, effective configuration, session,
Home/epoch/enrollment, pending EventKey state, trusted time, actual PIR wiring,
approved no-reset observer and current operator remain unverified. The only
inspected S3 receive-only capture is historical (2026-10-16, source
`d738dc51a25e72de570a11fc39f0e26522ead3d8`). Production S3 source composition
still defaults to `UnprovisionedS3CloudTrust`; GS-D032's production identity,
registry and receipt mechanisms remain open. No board/serial operation,
listener activation, network change, credential operation, Render change,
customer data mutation or physical stimulus occurred. No physical EventKey or
Android-visible event exists from this checkpoint.

The registered `make -C code gs179-postgres-e2e` rerun passed **51/51** against
the existing isolated local TLS PostgreSQL fixture (`physical=NOT_RUN`),
including source-linked HOST_SIM, security/lifecycle and runtime composition.
The new private-bind policy test validates explicit RFC1918/fixed-port
configuration and rejects unsafe/missing opt-ins; the full runtime process E2E
continues to bind loopback and no private socket was opened. The initial command
without `GS179_TEST_POSTGRES_DSN` exited 2 at the target's fail-fast guard. Also
`make -C code validation-framework-test` passed **51/51**, and
`make -C code feature-coverage-test` passed at 223 features, 278 modules, 26
physical cases, mapping **22/22**. `git diff --check` and the physical-case CSV
schema/status assertion passed. These are software/configuration results, not
physical proof. The focused current command `code/tools/local/gs179-laptop-server.sh
health` returned local PostgreSQL/caregiver readiness PASS, phone route
`BLOCKED_CONFIG_MISMATCH`, and Hub ingress `NOT_CONFIGURED`. The full findings
and exact next gates are in
[`GS-117 Android vertical readiness`](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md).

The runtime/test/catalogue/work-state implementation was committed and pushed
normally as `32460ef93dac3695a84467e8a6d84efcfef080e4`; origin matched at push.
GS-117 comment 11528 and GS-179 comment 11529 record the code/test result and
remaining gates. Jira Rank was unchanged.

Next action: fixture owner identifies the current C3/S3 and image/state and
approves a named reset-safe passive observer plus the genuine PIR stimulus;
security/authority owner supplies the current authorized Hub trust, Home/epoch,
Node enrollment/revocation and trusted-time inputs; network owner selects the
current laptop origin and separately authorizes any route, private-bind
configuration/listener activation and certificate changes. Then reuse the
existing GS-179 runtime and build the
existing CA-pinned GS-177 LAN TEST_ONLY APK only after its origin/SAN/route
match. Do not change live credentials, networking or hardware, and do not
replace the real sensor path with HOST_SIM. GS-117 remains open; GS-60 and
physical/commercial qualification remain NOT_RUN.

## 2026-10-22 — GS-177 approved Android UI regression correction

The latest owner direction is GS-177 comment 11534; the prior regression diagnosis is
comment 11530. The shared caregiver PWA now renders the sign-in form synchronously
before starting asynchronous `/lite/v1/me` session restoration. A single-flight
restore is cancelled when credential entry begins; generation checks prevent a
late response from changing the form. Successful login verifies `/me` before
showing Home and opens Home by default. The startup diagnostic reports only the
form-visible duration, with no credentials or tokens.

The connected caregiver Home now follows the approved 22 October hierarchy using
the existing authorized GS-148 projection: brand/header/date/Away, monitoring
hero, routine/activity/device summary, I am OK/Main door/Night activity/Device
health cards and recent-event timeline. Unknown, stale, unavailable and
unrecognized sources remain truthful; HOST_SIM/TEST_ONLY provenance remains
visible and is not presented as physical monitoring. Bottom navigation is the
four text-only Home/Devices/Reports/Settings labels in a flat, full-width,
56-pixel fixed ribbon; the header-reparenting helper and sticky-under-header
rules were removed. The Android WebView uses `adjustResize` and applies system
bar/cutout/IME insets so the app viewport and ribbon reflow around system UI.

Local production-code JS/runtime and validation framework checks passed. GS-130
traceability passes at 224 features / 278 modules / 26 physical cases, mapping
22/22. The registered Chromium browser test could not execute on this host because Chrome /
Chromium is absent; it is included in the Android Actions workflow. `adb` is also
absent, so no physical-phone login timing, 3-button/gesture navigation, keyboard,
font-scaling or screenshot comparison is claimed. Initial GitHub Actions run
39721098614 passed the new browser cases but failed a stale offline-login copy
assertion; the failure is preserved in the evidence. Follow-up run 39721322469
passed browser 4/4 with 92/92 assertions, GS-116 caregiver/API and Android stages,
APK build/signature and artifact upload. The runner-debug APK is source `2a1b5ffa`,
package `in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`,
configured for Render staging (not WSL2 HOST_SIM), 2,927,482 bytes, SHA-256
`c42fd1817f85eae52f9e7df3cb016a173ff0275b20307a2274b48a07042bab64`. The owner
phone was unavailable; installation, real startup timing and Android system
navigation/keyboard behavior remain NOT_RUN. This runner signing certificate
differs from immediately previous CI run 39716865657; if that is the installed
APK, Android will require uninstall/reinstall, which may clear local app state. Test evidence, files, IDs and
remaining device/backend boundaries are in
[`GS177_ANDROID_UI_REGRESSION_FIX_20261022.md`](../exec-plans/evidence/GS177_ANDROID_UI_REGRESSION_FIX_20261022.md).
GS-177 remains In Progress; GS-179 and physical Android/real Hub acceptance are
unchanged.

## 2026-10-22 — GS-179 customer cloud architecture checkpoint

Owner directions GS-179 comment 11532 and GS-117 comment 11533 select an
outbound customer Hub-to-cloud path; the laptop is not the product architecture.
The Jira inventory was refreshed (173 issues; Rank unchanged): GS-114 Rank 31,
GS-117 Rank 52, GS-60 Rank 60, and GS-179 Rank 173. GS-179 remains In Progress;
GS-117 remains In Progress; GS-60 remains To Do.

At checkpoint start, `/home/udaybhan/projects/Ghar_sajag_r1` on
`feature/r1-commercial-baseline` was at `1f6b72b3fac0a4ddf5b58a78d42ed430ffb124e4`,
equal to the live origin. Tracked files were clean; the 301 pre-existing
untracked items and 174,520 ignored paths were preserved. Context preflight
passed at `2026-10-13.001`.

The current Render caregiver service is still the Free staging deployment at
`3c0fec898d5cb2caae662f3dcc6324faaabf6b30`. Its TLS-terminating edge does not
provide the WSGI process with the verified Hub peer socket. The current WSGI
app does not mount the commercial GS-148 durable API/read model, and the
production S3 source still uses `UnprovisionedS3CloudTrust`. The existing
GS-179 runtime and same-PostgreSQL caregiver projection are implemented and
validated only in isolated TEST_ONLY/HOST_SIM mode.

An engineering topology recommendation is recorded in
[`GS-179 commercial cloud vertical evidence`](../exec-plans/evidence/GS179_COMMERCIAL_CLOUD_VERTICAL_20261022.md): a small Mumbai cloud host with
application-terminated Hub TLS and caregiver HTTPS routed by SNI to distinct
processes, both using one private managed PostgreSQL database. Indicative
baseline is about USD 42/month before domain, tax, snapshots and overage. This
is not provisioned, not a locked product/security decision, and not approval to
spend or change DNS. It avoids accepting caller-supplied identity headers and
does not rely on Render's TLS-terminating ingress for Hub authentication.

No source or tests changed in this checkpoint. The latest registered GS-179
PostgreSQL/runtime result remains 51/51 PASS with framework 51/51 and feature
mapping 22/22; these are existing TEST_ONLY/HOST_SIM evidence, not a cloud or
physical result. No production Hub identity, caregiver OIDC/Home authorization,
same-event Android read, actual S3 authentication or physical PIR event is
verified.

GS-D032 continues to leave production credential/proof, verifier, trust
registry, trusted-time/authority and deployment middleware/database composition
open. GS-68/109/172 must approve the production Hub trust contract; GS-76/143
must qualify caregiver authentication and Home membership; the owner must
approve the paid host/database/domain before provisioning. The next Jira action
is the production Hub identity/authority contract decision under GS-172/68/109.
GS-179 remains In Progress and GS-117/GS-60 remain open.

## GS-68 security correction and GS-179 laptop amendment — 2026-10-22

The owner amended the near-term deployment/validation direction in GS-179
comment 11538 and GS-117 comment 11539: use the existing Windows 10/WSL2 laptop
for initial same-Wi-Fi physical testing; no paid cloud hosting now. This
supersedes the immediate cloud-host recommendation above, not the commercial
requirement that customer operation work without a laptop. Jira Rank and
acceptance remain unchanged: GS-114 R31, GS-117 R52, GS-179 R173; GS-68,
GS-179 and GS-117 In Progress; GS-60 remains open.

Implemented one approved fail-closed correction in
`ProvisionedS3CloudTrust`: it now checks the S3 Hub client certificate's
`notBefore` and `notAfter` against the already authenticated trusted-time
snapshot before returning the TLS identity. It preserves existing
fingerprint/material-generation, revocation, purpose, trusted-time and backend
authority checks. Deterministic expired and not-yet-valid certificate
regressions are registered as `GS68-D05-CERT-VALIDITY-001` in the existing
GS-116/130 path. No production issuer, key, trust registry, time source, Home
claim, caregiver provider, or parallel backend was introduced.

The first target report exposed a defect in the existing ESP image checker for
segment streams ending on a 16-byte boundary; the image itself passed
`esptool image-info`. The validator was corrected and its aligned-boundary test
added. The diagnostic runner's pre-existing untracked-file guard was also
narrowed so the preserved IDF-generated sdkconfig and the already excluded,
non-input Android workspace do not block a source-bound S3 build; tracked
source changes remain rejected. Details and failed-attempt history are in
[`GS68 D05/D12/D06 provider evidence`](../exec-plans/evidence/GS68_D05_D12_D06_PROVIDER_E2E_20261017.md#2026-10-22--authenticated-hub-certificate-validity-and-laptop-check).

Validation: `make cloudsync-security-ut` PASS (mTLS 9/9; TEST_ONLY adapter 5
cases; provider 5 suites; backend security 14/14; GS-68/GS-40 identity/time
4/4; GS-168 registry 10/10; NodeHealth 5/5). `make gs130-hil-runner-test` PASS
(protocol 1,738 assertions, 116 Python tests); physical board/motion cases
remained NOT_RUN/BLOCKED without port access. ESP-IDF 6.0.3 S3 diagnostic
`BUILD_ONLY_PASS`, source commit `2f94d0a38250826f833cb8c82db3c386e1f094eb`,
image SHA-256
`f98e8617284cb56f3f5253b9383e8e92980c69f15091b6705d12a2574fe82bac`, no
flash/serial. Existing focused results also include 18/18 security simulation,
1/1 local mTLS integration, validation framework 51/51 and feature mapping
22/22. These are software evidence; no commercial key or silicon behavior is
qualified.

Read-only laptop status: PostgreSQL `verify-full` and caregiver HTTPS CA/IP-SAN
both PASS; WSL2 caregiver service and PostgreSQL remain running. The existing
Hub ingress runtime is implemented but `AUTOSTART=DISABLED`, Hub identity is
unauthenticated, freshness `UNKNOWN` and persistent ingress
`NOT_CONFIGURED`. Current Windows Wi-Fi is `192.168.1.10`, while configured
endpoint/Android profile expects `192.168.1.6`; existing forwarding still
targets `.6:443 → 172.17.152.10:8444`, and firewall inspection requires
administrator access. No endpoint, certificate, forwarding, firewall, network,
service, credential, customer data, or hardware change was made. The current
Render-targeted APK is not aligned with this laptop; no local-LAN APK was
built or installed.

Production D05/D12 issuer and DS-key custody; D06 authenticated-time authority
and rollback-resistant storage; GS-109 epoch-0 Home claim/transfer; GS-76/143
production caregiver issuer/session/membership; exact laptop endpoint/cert
and network authorization; and current physical fixture/image/observer
approval remain open. No original physical EventKey or caregiver-visible
physical event exists. GS-117 and GS-60 remain incomplete.

Implementation commits are `cf5def1` (Hub certificate validity), `19afb18`
and `7ca1889` (source-bound diagnostic guard for preserved artifacts), and
`2f94d0a` (aligned ESP image validation). Evidence/traceability and source
commits were pushed at `c3b024488fe0a123087517152d5caa08800eaf28`. Factual
updates were added without workflow changes: GS-68 comment 11542, GS-179
comment 11543 and GS-117 comment 11544. This work-state closeout records those
comments; its final documentation-only delivery and remote equality are
verified by the follow-up Git/Jira handoff. The next executable action is owner
resolution of the exact current laptop endpoint/certificate/route and approved
D05/D12/D06 test identity/time inputs; then prepare the matching existing
local-LAN Android build and, only after fixture/image/observer approval, run
one real PIR test. Starting local/remote HEAD was
`f65c503baa538b232162a61228a70c9d585313f6`; the initial 301 untracked items
were preserved. Two untracked Python bytecode files from the explicit compile
check are also preserved; no cleanup was run. The diagnostic artifacts remain
in `/tmp/gs68_cloudsync_diag_e1pbdu7c` (initial failed report generation) and
`/tmp/gs68_cloudsync_diag_retry_20261022` (passing report).

## GS-179 owner-approved laptop LAN readiness — 2026-10-22

Owner approval in GS-179 comment 11546 and GS-117 comment 11547 permits reversible, private TEST_ONLY LAN setup. This records the resulting state and supersedes the preceding paragraph's statement that laptop endpoint/forwarding work was still pending. It does not authorize phone, Hub, board, credential, customer-data, or PIR operations.

Current Windows Wi-Fi is SSID Yogi at `192.168.1.6/24` (Public profile); WSL2 is `172.17.152.10`. The existing server certificate already covers `192.168.1.6` and uses the same CA fingerprint pinned in the existing Android local-LAN profile, so no certificate/key or Android trust change was needed. Windows forwards `192.168.1.6:443` to caregiver HTTPS at `172.17.152.10:8444`; the narrowly scoped firewall rule permits TCP 443 only from `192.168.1.0/24` on Wi-Fi. The DHCP lease expires 2026-10-23 15:36 local; no router reservation or static IP was configured. Private rollback state is preserved at `/home/udaybhan/.local/state/ghar-sajag/gs179-laptop/lan-rollback-20261022T103148Z`.

Caregiver HTTPS and Hub ingress configuration point to the same local PostgreSQL database (`gs179_monitoring`, `gs179_app`, TLS verify-full and durable server settings). Live health reports PostgreSQL, caregiver HTTPS and the WSL-to-Windows TLS endpoint ready. It reports phone reachability NOT_VERIFIED and Hub ingress NOT_CONFIGURED/default-disabled; no actual Hub identity or fresh physical source is present.

Validation on the implementation source: registered GS-179 PostgreSQL/source-linked integration **52/52 PASS**; the two repaired browser regressions **2/2 PASS**; focused GS-179 security/lifecycle **15/15 PASS**; laptop HTTPS browser returned HOST_SIM_PASS with one committed test event visible after reload and stale/UNKNOWN monitoring. The existing Python/PostgreSQL security cases verify Home isolation, forged-header rejection, retries and restart behavior. This does not establish phone reachability or physical acceptance. The approved local-LAN APK workflow completed PASS at run 39766494060 on source 8c134487a4afdde0869aad0e0c5b9c9b19f1b544. Artifact ID 12420842385 is linked in the evidence; APK SHA-256 is ab61481bbdaf9b8d98b86b0c67ef8b7bdfb10be0605dc4a425f6343de03754f9, package in.gharsajag.caregiver version 0.4.0-connected-lite-staging, origin https://192.168.1.6, and runner-generated debug signer certificate SHA-256 58f9d58042af12a1eca6b4fadd8bb836e3b04220995fb710ad3eac0d1b1972ac. CI software gates passed; physical status NOT_RUN and the app was not installed.

Evidence and rollback details are in [GS-179 laptop LAN / Android host evidence](../exec-plans/evidence/GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md#2026-10-22--owner-approved-windowswsl2-lan-configuration). Starting source HEAD was `ad170206152714bcfbedaa0e3a26108f03cb638e` and matched the remote. Five tracked helper/test files and this evidence/work-state are the only intended source/documentation changes; all pre-existing untracked and ignored files remain preserved. Implementation commit 8c134487a4afdde0869aad0e0c5b9c9b19f1b544 is pushed and equals the verified remote. The APK artifact provenance is included in the linked evidence. Phone verification, real S3 authentication, Hub-ingress activation, and genuine PIR remain the next separate authorized stages.

## GS-177/GS-179 router-independent TEST_ONLY reconnect — 2026-10-22

The Wi-Fi roaming source change is implemented and its focused host/API/security
regressions pass. The local TEST_ONLY Android build now supports a persisted
paired `.local` HTTPS origin and an explicit private-address reconnect fallback
without bypassing certificate hostname validation. The backend allows that
origin only in the isolated local-LAN profile. Windows tooling derives current
Wi-Fi/WSL addresses and contains an opt-in, narrowly scoped forwarding refresh
watcher; it is not registered because the current Windows token is not
elevated.

Current read-only laptop state is Agrim `192.168.1.8/24`, WSL2
`172.17.152.10`. PostgreSQL and caregiver HTTPS are healthy, but existing
portproxy still targets historical `.6`; therefore current LAN HTTPS readiness
is FAIL and phone reachability is NOT_VERIFIED. No route refresh, firewall
change, watcher registration, phone action, or live server restart was made.
The source change is not physical Wi-Fi-switch acceptance: Yogi → Agrim → Yogi
on the same installed phone APK remains NOT_RUN. The combined Wi-Fi and approved
UX APK is deferred until after the Wi-Fi source checkpoint is committed.

Validation: PWA runtime 10/10; caregiver API 22/22; GS-179 security 18/18;
GS-179 PostgreSQL E2E 55/55; GS-177 connected-lite/API runner 22 API, 10 JS,
3 scenarios and 10 runtime checks; framework 51/51; feature/traceability
integrity PASS; isolated PWA browser 4/4 and 92/92 rendered checks; GS-178
caregiver integration 33/33; syntax and `git diff --check` PASS. The broad
backend/PWA aggregates still report the existing mandatory P0 `PARTIAL` and
stale diagnostic-foundation registration expectation; an initial aggregate
also lacked `websocket`, after which its focused browser stage passed using a
temporary external dependency. Android Gradle/APK and handset validation were
not available in this environment. Detailed commands and the exact current
route state are in [the dated GS-179 evidence](../exec-plans/evidence/GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md#2026-10-22--router-independent-test_only-reconnect-implementation).

The Wi-Fi changes are not yet committed at this checkpoint. Starting local and
remote HEAD is `aeb2ab52a4f1c0e286817b77026d4fe13f03580b`; pre-existing
untracked and ignored files are preserved. GS-177, GS-179, GS-117 and GS-60
remain open/In Progress or otherwise at their existing Jira states. After this
Wi-Fi-only source checkpoint is validated and pushed, continue the owner-
authorized GS-177 UX integration in this same worktree.

## GS-177 UX integrated after Wi-Fi checkpoint — 2026-10-22

The requested implementation order was followed. Router-independent TEST_ONLY
Wi-Fi source is first checkpointed at `fd6437eee69ca6cfabd78ab3fc3b9f38801444db`.
The owner-approved GS-177 UX implementation and APK evidence were then
integrated sequentially on the same canonical branch at
`608c5ba40453f3eead9b5e831fe22dbbe68efed5` and
`794b355364471c89bf0ec30006e77e5e64e15735`. Shared Settings and traceability
conflicts preserve the approved UX and guarded reconnect/reset behavior.

The combined GS-179 PostgreSQL vertical passes 55/55, the shared PWA browser
stage passes 4/4 with 92/92 catalog assertions, caregiver API 22/22, runtime JS
10/10, GS-179 security 18/18, validation framework 51/51, and feature coverage
and traceability pass (225 features, 278 modules, 26 physical cases; framework
22/22). Existing browser assertions now check incident-driven Home status, the
current authenticated watermark, and semantic incident state after UX changes.
These are HOST_SIM and TEST_ONLY software results.

No phone test has been performed. Current read-only Agrim evidence still shows
Windows `192.168.1.8/24`, WSL2 `172.17.152.10`, and an existing portproxy target
of `192.168.1.6`; caregiver HTTPS/PostgreSQL are healthy locally but current
LAN route is not verified. The optional address-refresh watcher is not registered
because the available Windows token is not elevated. The combined local-LAN APK
build is pending the established Android CI workflow from final pushed source.
No app was installed, cleared or removed. Real Hub authentication, physical
Yogi → Agrim → Yogi reconnection, real PIR, and GS-117/GS-60 acceptance remain
NOT_RUN.

### Combined local-LAN APK workflow result — 2026-10-22

The combined source build completed its sole Android workflow job successfully:
[run 39797650882](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39797650882), source `ed99dbe1d73286110670c0128e2476415e387d2a`, artifact ID `12434502262`. APK `in.gharsajag.caregiver` version `0.4.0-connected-lite-staging` targets `https://desktop-3qqu64b.local` with local-LAN TEST_ONLY enabled and CA SHA-256 `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`. APK SHA-256 is `5aaea3c6f71e1d60b401436d987fb50633c4766ba4e7318384e077ad7f0bd02f`; v2 signature validation passed. Signer is a runner-generated debug key with certificate SHA-256 `141f15cdaec4645094cb0657956f8b82110f2f4eccfda61a9b5260052e111392`, different from the prior recorded LAN and staging artifacts. Installed-phone signer was not queried, so update eligibility is unknown; no installation/uninstallation/clear was performed. A signer mismatch requires uninstall/reinstall and therefore remains behind owner approval.

CI passed PWA browser 4/4 / rendered checks 92/92, caregiver API 22/22, Android dashboard 12 checks, voice prototype 28 checks, APK v2 signature and artifact upload. GitHub reports the single job complete/success while aggregate run remains `in_progress`. The push-triggered default-origin run 39797636040 failed once at Chrome DevTools startup for the first catalog test; the other three browser tests passed, and the later complete manually configured local-LAN run passed. The physical phone, local network transition, current portproxy correction, real Hub and PIR remain NOT_RUN.

The GitHub run aggregate later finalized `completed / success` at 2026-10-22
14:50:44 UTC; the earlier in-progress status reflected delayed aggregation.

## GS-179/GS-177 owner-reported Android Wi-Fi regression — 2026-10-22

The owner installed combined TEST_ONLY APK workflow 39797650882 and reports
login `Failed to fetch` on both Yogi and Agrim; the previous IP-origin APK had
connected on Yogi. This is a phone-connectivity FAIL, not an authentication
result or Hub/sensor acceptance.

Current read-only state: Windows Wi-Fi profile Airtel_Agrim, `192.168.1.8/24`,
Public profile; WSL2 `172.17.152.10`; stale portproxy
`192.168.1.6:443 -> 172.17.152.10:8444`. WSL PostgreSQL and caregiver HTTPS
are healthy. The caregiver TLS certificate has a valid `desktop-3qqu64b.local`
DNS SAN and the APK-pinned CA, but its only IPv4 SAN is old `.6`; no current
`.8` SAN exists. Correct-host TLS verification passes from WSL, wrong-host TLS
is rejected, and current `.8` Windows-LAN HTTPS times out.

Windows DNS returns both WSL virtual gateway `172.17.144.1` and Wi-Fi address
`.8` for `desktop-3qqu64b.local`; WSL's ordinary resolver returns no `.local`
answer. Android source loads the `.local` origin in WebView and delegates name
resolution to the platform; there is no app-level NSD/DNS-SD resolver. The
Android-selected address is still unknown. A read-only direct-to-WSL
authenticated caregiver probe passed with the existing TEST_ONLY login, read
the one pre-existing PostgreSQL EventKey from the authorized Home, denied a
foreign Home, and returned STALE/UNKNOWN. This record is HOST_SIM/TEST_ONLY.
Existing caregiver regression suite `test_connected_lite.py`: 22/22 PASS.

No Windows changes were made: current token is non-administrator and firewall
readback is blocked. The automatic watcher remains unregistered; its current
generic network-event task would run HighestAvailable and can enable the scoped
listener on any RFC1918 Wi-Fi because it has no owner-trusted network allowlist.
Do not register it until that trust gate is resolved. Next action: run
`code/tools/local/gs179-laptop-server.sh network-refresh` from the canonical
WSL distro launched by an elevated Windows Terminal while on a specifically
owner-approved Wi-Fi; repeat for each Wi-Fi transition until a safely scoped
watcher is approved. Require the LAN TLS probe to pass, then use phone Chrome
`https://desktop-3qqu64b.local/readyz` to separate DNS/TLS/route failures before
retrying APK login. If `.local` fails, use the app's reconnect action with the
current private IPv4 only after the server leaf includes that IP SAN. No APK
rebuild/reinstall, Home data mutation, physical Hub operation, or sensor test
was performed in this checkpoint.

## GS-177 / GS-179 owner phone result and secure DNS-SD follow-up — 2026-10-22

Owner correction in GS-177 comment 11583: the installed local-LAN TEST_ONLY
APK successfully logged in and loaded its authorized Home on Agrim after
selecting `https://192.168.1.8` through the existing reconnect flow. This is
physical phone PASS for the IP fallback and caregiver API/Home path. The
hostname-based `.local` route failed; automatic DNS-SD and Yogi → Agrim → Yogi
on the same APK remain unverified. No physical sensor provenance is implied.

Implemented source adds a TEST_ONLY Windows DNS-SD locator and foreground
Android NSD client. Discovery metadata never authenticates the service. The
Android client requires platform CA and IP-hostname verification, exact
`desktop-3qqu64b.local` DNS SAN, persisted SPKI continuity after the first
verified connection, healthy PostgreSQL `/readyz`, bounded probes, and current
network-generation checks before saving the discovered private IP. The test
profile alone adds Wi-Fi multicast/network-state permissions and the local CA;
the commercial/release origin and UI remain unchanged. The Windows advertiser
only runs from the explicit TEST_ONLY server path and is restricted to RFC1918
Wi-Fi that Windows classifies Private or DomainAuthenticated.

Current read-only checks: Windows is `Airtel_Agrim`, `192.168.1.8/24`, profile
Public; WSL2 is `172.17.152.10`; both `.8:443` (active) and historical `.6:443`
portproxy mappings/listeners exist to the same WSL service. PostgreSQL,
caregiver HTTPS and WSL-originated TLS health pass. Because Windows classifies
Agrim Public, the new advertiser intentionally will not publish there until
the owner marks that trusted network Private. The privileged Wi-Fi watcher
remains unregistered pending its trusted-network approval; it is still needed
to refresh current-IP certificate SAN, firewall and forwarding across a router
change. Stale `.6` cleanup remains a separate issue.

Validation on this source: PWA JS runtime 10/10; `GS177-LAN-NSD-001` source
marker PASS; Windows PowerShell TEST_ONLY DNS-SD policy/record-construction
validation 13 policy cases PASS with no registration/socket; feature coverage
and traceability 22/22 PASS (225 features, 280 modules, 26 physical cases);
shell syntax, Python compilation, registry JSON, and `git diff --check` PASS.
The local Android runner exits 127 after source and PWA tests because WSL lacks
Gradle/Android SDK. Android JUnit, APK build, automatic phone discovery and
router-switch acceptance are pending the registered CI build and owner phone
test. No portproxy/firewall mutation, network-profile change, watcher
registration, APK installation, Hub operation or PIR stimulus was performed.

Detailed implementation and read-only laptop evidence:
[`GS-179 local WSL2 host — DNS-SD follow-up`](../exec-plans/evidence/GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md#2026-10-22--test_only-dns-sd-discovery-and-android-secure-reconnect).

The Android route-recovery correction now tracks default Wi-Fi network and
link-address/route changes. After a verified NSD/TLS candidate, the app reloads
the caregiver WebView on either a changed endpoint or a changed route, including
the case where a router transition retains the same private IP. It does not
reload solely on foregrounding an unchanged network. A JUnit regression covers
same-origin route recovery; it is registered but still requires CI's Android
Gradle stage for execution. Post-correction source validation re-ran PWA 10/10,
static `GS177-LAN-NSD-001`, Windows DNS-SD validation 13 policy cases, traceability
22/22, syntax/JSON and `git diff --check`. The local Android runner again exits
127 because Gradle/Android SDK are not installed in WSL. No APK or Android JUnit
result is claimed from this local environment.


### GS-177 / GS-179 Android discovery CI and APK — 2026-10-22

Commit `8ca19768ea3da392d2badbb8b9e9077702bc54dc` is pushed and remote-verified.
Push workflow 39821567855 passed. Local-LAN workflow 39822389037 used
`https://desktop-3qqu64b.local` and GS179 TEST_ONLY. Attempt 1 had two existing
PWA browser tests fail because Chromium DevTools did not start; retry attempt 2
passed all stages. PWA: 4 tests, 92/92 rendered cases. Registered caregiver-app
stages: connected-lite API 22, Android dashboard 17, voice prototype 28, all
PASS. Android unit tests and assembleDebug passed, APK signature verified.

The 14-day artifact is
[workflow 39822389037](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39822389037),
APK SHA-256
`b54d0ebd45653d2e085be1deaaf5686c5d73802f05fbaaeb7338e1315f8084c3`, package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, source
`8ca19768ea3da392d2badbb8b9e9077702bc54dc`, origin
`https://desktop-3qqu64b.local`, CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
The generated debug signer SHA-256 is
`8caa922ccf7efae2337ba8d63780d12a0d2935bba3f10872b0466f51330eed11`, which
differs from installed workflow 39797650882 signer
`141f15cdaec4645094cb0657956f8b82110f2f4eccfda61a9b5260052e111392`.
Therefore it is not an in-place update. It was not installed and no existing
phone app data was cleared.

While synchronizing the latest CI evidence, `make -C code feature-coverage-test` first rejected a mismatched command and test anchor in GS179-LAN-01. The traceability row was corrected to the commands in `suites.json` and the JUnit marker; rerun passed with 225 feature rows, 280 modules, 26 physical cases and 22/22 framework tests. The initial failure is recorded in the evidence file.

The owner's physical phone report still proves only Agrim login/Home through
manual HTTPS IP fallback `192.168.1.8`. New automatic DNS-SD and Yogi → Agrim
→ Yogi behavior remain NOT_RUN. No laptop network/IP/portproxy/firewall changes
were made. Windows currently categorizes Agrim as Public, so the TEST_ONLY
advertiser remains fail-closed; the privileged network watcher is unregistered.
Stale .6 portproxy cleanup remains separate. No real Hub/PIR event or physical
sensor provenance is implied.

Detailed evidence is in
[GS-179 laptop/Android evidence](../exec-plans/evidence/GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md#ciapk-and-owner-verification-addendum--2026-10-22).

#### GS-179 reconnect guard follow-up — 2026-10-22

The optional Windows network watcher now fails closed unless the current Wi-Fi
profile is Private or DomainAuthenticated and has a bounded RFC1918 address.
The profile check runs before watcher registration and before forwarding or
firewall mutation. The watcher remains unregistered; no live laptop network
state was changed. The WSL target-recording command and explicit DNS-SD
advertiser-start command are now separate, with the watcher invoking them in
sequence after refreshing forwarding.

Validation: `LaptopServiceLifecycleBoundary` 11/11 PASS; feature traceability
22/22 PASS (225 features, 280 modules, 26 physical cases); Bash syntax,
PowerShell parse, and `git diff --check` PASS. The preceding full GS-179 suite
ran 55 tests with one lifecycle-fixture failure because the test did not create
the private config now required by the DNS-SD side effect. That side effect was
removed from the target-recording command and the lifecycle class passed after
the correction; the full suite was not rerun. Physical phone automatic DNS-SD
and router-switch validation remain NOT_RUN. See the dated GS-179 execution
evidence for exact artifact, current Windows profile, signing mismatch and
owner-reported IP-fallback result.

## GS-177 + GS-179 canonical integration — 2026-10-23

GS-179 source ownership was explicitly handed off before this integration. The
incremental GS-177 UI correction from feature HEAD
`a0f49c5bb855a716647521ad3bd1f7a487394816` was integrated into canonical starting
at `b4eaa05f999680d3dfe0f8c3d9e553a19941c032`, preserving commit history and
avoiding replay of earlier UI work already present in canonical. Current local
HEAD is `563691589e72b09f7b5ef2564e6c4464cd2512b4`; canonical remote was still at
the starting SHA at the last check. Three local commits are pending normal push.

The final isolated GS-179 PostgreSQL/security run passed all 55 tests in
491.530 seconds using a temporary database/TLS environment. The GS-177
connected-lite suite passed 22 API tests, 10 runtime tests and 3 scenarios;
standalone caregiver runtime passed 10/10; feature coverage passed at 225 rows,
280 modules, 26 physical cases and 22/22 framework tests. Caregiver-app gate
API (22) and voice prototype (28) stages passed. Its Android stage reached the
source, branding and runtime checks, then stopped because local Gradle is not
installed. The local PWA browser gate skipped all tests because no Chromium or
Chrome executable is installed. Hosted Android workflow and full browser stage
are still required for the final APK artifact.

Visual evidence is the existing five-screen 390×844 mock-authenticated browser
capture set linked in `GS177_ANDROID_UX_IMPLEMENTATION_20261022.md`; these are
not phone/WebView acceptance. Physical Android login, discovery, Yogi → Agrim →
Yogi roaming, offline recovery, untrusted-network guard, and sensor/Hub tests
remain NOT_RUN. The owner services were intentionally left running. All
pre-existing untracked files and reference images were preserved. Next steps:
review and commit the evidence plus the narrow Playwright teardown fix, push the
three integration commits and evidence commit to the canonical branch, verify
remote HEAD, then dispatch the combined TEST_ONLY Android workflow and record
artifact/source/signature evidence. Do not install the APK or claim phone
acceptance.

### GS-177 + GS-179 final software artifact checkpoint — 2026-10-23

The TEST_ONLY Android workflow completed successfully: [run 39885083296](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39885083296), source `f023319ec1e49bf69e27e314a964b1ab43812367`, artifact ID `12472705475`. Hosted browser checks passed 92/92 rendered assertions; registered stages passed API 22, Android 17 and voice prototype 28. The final integrated GS-179 isolated PostgreSQL/security suite passed 55/55. See the dated GS-177 evidence for APK SHA-256, TEST_ONLY origin/CA, source asset parity, package/version and signer certificate. APK signature passed, but installed phone signer continuity and update compatibility are unverified.

Canonical was pushed and verified at `f023319ec1e49bf69e27e314a964b1ab43812367`; this evidence addendum is being committed separately. GS-177 and GS-179 remain In Progress. Physical phone login and visual comparison, automatic discovery, Yogi → Agrim → Yogi switching, offline/recovery behavior, unauthorized TLS rejection, and untrusted-network watcher behavior remain NOT_RUN. Do not uninstall, replace or clear the current phone app without separate approval. Real C3/PIR/Hub acceptance remains outside this software integration.

## GS-179 DNS-SD diagnosis and combined APK — 2026-10-23

Owning Jira GS-179 remains In Progress. Canonical code source is on
`feature/r1-commercial-baseline` at `dce8a52e6a294c40d6f8fe949430418c54042a3c`;
`origin/feature/r1-commercial-baseline` matched at the code checkpoint. The
documentation checkpoint is being committed and pushed after this status
update. Preserve pre-existing untracked work and evidence.

Root cause of the reported paired-laptop `Failed to fetch`: the action erased
the working manual-IP origin and saved SPKI pin, then immediately loaded the
unresolved `.local` hostname before asynchronous Android NSD and secure
readiness validation completed. The app now keeps the current working endpoint
and pin, restarts foreground discovery, and switches only after platform CA/IP
hostname validation, expected laptop DNS SAN, SPKI continuity and `/readyz`
pass. TEST_ONLY logs now show browse/start/timeout, filtering/TXT rejection,
resolve, IPv4 selection, TLS/SAN/SPKI/readiness, persistence and delivery
failures. Manual-IP TLS and certificate verification remain intact.

The Windows worker reports actual registration status: PID 4280, API result
9506 (`DNS_REQUEST_PENDING`), callback 0, service
`GharSajag-GS179-desktop-3qqu64b._https._tcp.local`, `192.168.1.8:443`,
interface 18, Private profile. This confirms Windows DNS-SD registration but
not phone discovery. The Android phone has not been observed; mDNS
browse/resolve and Yogi → Agrim → Yogi remain NOT_RUN. `adb` is unavailable in
the build environment.

Combined regressions passed in [Local-LAN workflow
39887837848](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39887837848)
on source `dce8a52e`: PWA browser 92/92; registered API/Android/voice 22/19/28;
Android unit tests, APK assembly, APK v2 signature and upload. Earlier in this
task, GS-179 PostgreSQL E2E passed 55/55, connected-lite API/runtime passed
22/10 plus three scenarios, Windows policy validation passed 14/14, and
feature coverage passed 225 features, 280 modules, 26 physical cases and
22/22 mapping checks.

The single Local-LAN TEST_ONLY APK is
[`parivar-saathi-caregiver-debug.apk`](../exec-plans/evidence/GS179_DNSSD_AUTODISCOVERY_20261023/apk/parivar-saathi-caregiver-debug.apk),
2,962,184 bytes, artifact `12473876313`, APK SHA-256
`0ae141221233ba39a997396bb496a818250668ccf1b4d354372dad5add630c80`, origin
`https://desktop-3qqu64b.local`, CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`, signer
certificate SHA-256
`61710682d9c43052a1e1f07dbe6fef7ae7671391d82335d91b61bd0cf3a564cf`.
Update compatibility with the currently installed phone package is unverified;
previous installed-build records show a different signer. No install,
uninstall, app-data clear, watcher activation, firewall/forwarding change, or
production-security change occurred.

Next action: owner confirms a signer-compatible path that preserves the
working app. Then capture `ParivarSaathiLan` logs while exercising Android
discovery, secure endpoint verification and Yogi → Agrim → Yogi. Record handset
visibility separately from Windows callback/CI results. Physical acceptance,
release approval and Hub/PIR qualification remain NOT_RUN.

## GS-179 / GS-177 side-by-side discovery build — 2026-10-23

The owner requested a separate physical-discovery APK while preserving the
installed commercial application. Canonical GS-75 UI and corrected GS-179
discovery sources are reused as-is; no old UI branch was merged. The explicit
GS-179 debug TEST_ONLY profile now produces package
`in.gharsajag.caregiver.discoverytest` with a visible TEST_ONLY label. Normal
debug/release IDs and production behavior remain unchanged. A separate
persistent TEST_ONLY PKCS#12 identity is stored outside Git at the owner-only
path documented in the GS-179 evidence and in GitHub Actions encrypted
secrets; source contains only its public SHA-256 fingerprint. TLS CA/IP SAN,
laptop DNS SAN, SPKI continuity, authentication/Home authorization and manual
IP fallback are unchanged.

Before push, `make -C code feature-coverage-test` passed with 225 features,
280 modules, 26 physical cases and 22/22 checks. Python compilation, registry
JSON parsing, workflow YAML parsing and `git diff --check` passed. Source
`7f1626428e5a45f27ab07f6094977e05fb20ad38` is pushed and remote-verified.
Standard workflow 39905741965 passed. TEST_ONLY workflow 39905750839 passed
PWA browser 92/92, registered API 22, Android dashboard 19, voice 28, Android
unit tests/build, package/label assertions, pinned signer verification, APK
SHA verification and upload. It reports SOFTWARE PASS / PHYSICAL NOT_RUN.
APK SHA-256 is
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`, signer
SHA-256 is `d336ae68479da03de932a44b16c8de730c86e3cf68aee52fe92261e74e596b85`,
artifact ID is `12480713458`; see linked evidence for the APK file path.

ADB/Android SDK are unavailable locally. Physical Agrim discovery remains
NOT_RUN, no APK was installed, and the existing app/data/settings are
untouched. Do not infer phone multicast reception from Windows registration or
CI. Next action: on Agrim, install the separate TEST_ONLY package, capture
`ParivarSaathiLan` logs, select “Use paired laptop” without first entering the
laptop IP, and report DNS-SD receive/resolve separately from HTTPS/TLS,
readiness, endpoint persistence and authorized Home. Only after Agrim passes,
run Yogi → Agrim → Yogi using the TEST_ONLY app. Preserve the original package
and its data. The privileged network watcher remains unregistered and requires
separate explicit approval; do not operate the Hub or PIR. See [GS-179
discovery acceptance evidence](../exec-plans/evidence/GS179_DNSSD_AUTODISCOVERY_20261023.md#side-by-side-discovery-acceptance-apk-preparation--2026-10-23).

### GS-117 TC-001 physical-C3/S3 injected-motion console — 2026-10-23

The canonical branch began this work at
`f5b2042bf36ebd01da85dc147ae2ae3e873c9c2f`, matching origin; context
preflight passed. The existing C3 HIL command, production NodeRuntime,
physical S3 product composition, GS-179 mTLS/PostgreSQL/API runtime and
GS-177 APK UI were audited and reused. A loopback-only Windows-launchable
TC-001 console and exact-COM helper now provide a guarded path for repeatable
`C3_HIL_INJECTED` events. The existing GS-179 browser probe also resolves the
WSL `.local` routing problem through a current IP and certificate-verified
endpoint. The live browser result is `HOST_SIM_PASS` on the old one-time event;
it is not physical or APK acceptance. See the [GS-117 TC-001 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-23--tc-001-injected-motion-console-checkpoint).

At this checkpoint Windows exposes only one COM interface, there are no
current C3/S3 installed-image/reset-safe/fixture approval receipts, the
existing Hub ingress remains `NOT_CONFIGURED`, and no ADB executable is
available. The localhost console's guarded smoke run reports `BLOCKED`
before serial access. No new EventKey, physical S3 admission, mTLS COMMITTED
receipt, fresh caregiver event or APK display was observed. `PHY-GS117-TC001`
and optical `PHY-GS117` both remain `NOT_RUN`; GS-117/179 remain In Progress.
The latest handoff lists exact prerequisites, validation and next action.

Focused TC-001 orchestration tests passed **15/15** and certificate-verified
endpoint tests **2/2**; the read-only live caregiver browser probe passed on
the preserved HOST_SIM seed only. GS-130 traceability passed (226 rows,
280 modules, 27 physical cases) and the framework passed 51/51. The PWA
Chromium stage passed 86/86 while the aggregate PWA/backend/tooling gates
remain **FAIL** for the recorded CSS budget, partial P0 physical status and
the PWA offline browser's missing local `websocket` dependency. No TC-001
physical acceptance or release gate was executed.
The isolated GS-179 PostgreSQL regression passed **55/55**, with physical
`NOT_RUN`. A live read-only authority lookup verified only the existing
HOST_SIM seed's active test Hub/Node registry; the console uses that lookup
to block injection if the selected fixture's current Home, epoch or
enrollment has changed.

## GS-117 C3 HIL awake profile audit — 2026-10-24

The observed loss of C3 USB serial during light sleep is addressed for TC-001
by reusing the existing test-only profile `GS_HIL_BUILD=OFF`,
`GS_HIL_CONTROL=ON`, `GS_BAT_C8_PHYSICAL_WAKE=OFF` (default remains OFF). The
physical-wake eligibility gate already inhibits light sleep in that profile;
the regular 20 ms PIR poll delay avoids a busy-loop. The build reports its
active power/HIL mode, and the serial helper must see the expected `GET_STATE`
profile before it can send `INJECT_MOTION`. Production sleep and GS-114
qualification policy remain unchanged; no firmware has been installed.

ESP-IDF 6.0.3 non-flashing profile builds both passed from the current
`ad717c715bf8399546632c954bc45ed60f104be1` source HEAD plus the tracked working
diff. HIL-awake candidate: 950,032 bytes, SHA-256
`2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f`, flags
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`. Normal sleep-enabled candidate: 940,608 bytes,
SHA-256 `eec59be390315bad53e05bb7c3c60e0fd3311ec16a11d19040d3ad36ef4c733b`,
all three flags OFF. Both fit the 1,966,080-byte smallest app partition.
Focused results: TC-001 17/17, endpoint 2/2, C3 profile 4/4, BAT-C8 invariants
11/11, validation framework 51/51, feature traceability 22/22, physical
catalogue 111 cases PASS with `device_access=NONE`. Build output remains in
ignored `code/build/gs117-c3-*` directories; not staged or installed.

Fresh read-only enumeration found two native Espressif USB Serial/JTAG
interfaces attached to WSL: Windows USB/IP COM4 / WSL `/dev/ttyACM0` with
historical C3 serial `14:63:93:C5:D1:58`, and COM10 / `/dev/ttyACM1` with serial
`E0:72:A1:D3:8D:34`, which is not yet matched to the expected S3 fixture. No
serial port was opened, so current firmware/profile/OTA state is `NOT_VERIFIED`.
GS-114's documented approval is passive-only and prohibits uncertain serial
opens; the fixture's exact current-image receipts and approval are absent.

Laptop PostgreSQL, caregiver HTTPS and local backend health are `PASS`. Owner
reports the existing single APK showed Connected, but no phone-side observation
was available; phone reachability remains `NOT_VERIFIED`. Hub ingress is not
configured or identity-authenticated, so real S3 CloudSync remains
`NOT_VERIFIED`. No new event, EventKey or physical APK presentation exists.

Next action: after separately approved exact-fixture non-reset serial/image
inspection, verify the installed C3 profile. If it is not HIL-awake, approve an
app-only deployment of the built candidate with an identified recovery path;
do not touch NVS, credentials, partition table, Home or enrollment. Then verify
the running profile, build fresh receipts and continue the existing TC-001
console against the same Home and backend. Preserve GS-114 physical status and
the independent genuine-PIR qualification.

### Delivery checkpoint — 2026-10-24

Implementation source commit `15b983ef604cd9fc6ba2ab9f8865d64f0f5bec84` was
pushed to canonical branch `feature/r1-commercial-baseline`; remote HEAD was
verified equal. Context preflight passed. Jira comments 11602 (GS-117) and
11603 (GS-114) record the exact builds, tests and physical limitations. The
implementation source/test commit is on the remote; this document-only
checkpoint records the remaining state. Pre-existing untracked Android assets,
S3 managed components and `sdkconfig`, historical
hardware evidence, and ignored target build outputs were preserved.

Remaining gates: exact fixture-specific authorization and verified no-reset
serial path for current C3/S3 image inspection; installed C3 HIL profile and
current OTA identity; safe repeated idle/injection serial behavior; authenticated
persistent Hub-ingress identity/readiness; phone-side current APK/backend/Home
receipt and explicit display confirmation. No C3 injection or device update has
been performed. Continue from the existing TC-001 console only after those
receipts are obtained; retain the same Home, backend and APK.

### GS-117 fresh physical/backend recheck — 2026-10-24

At canonical HEAD `44f384afaa3d3efd1c7fb48d220cf3d6f6e1dcf8`, remote matched
local and context preflight passed. Read-only USB metadata maps COM4 / BUSID
`3-1` / `ttyACM0` / `14:63:93:C5:D1:58` to the documented C3 USB identity.
COM10 / BUSID `3-2` / `ttyACM1` / `E0:72:A1:D3:8D:34` is a second native
Espressif interface but does not match the historical S3 CH343 identity
`5CBC401023`; do not infer S3 identity from COM number. No TTY was open under a
WSL process at the snapshot, but the ports remain attached through USB/IP and
reset-safe open behavior is unverified.

Jira GS-114 comment 11145 is still the controlling physical authorization:
passive enumeration is allowed; active open/read is permitted only if exact
adapter/endpoint reset safety is independently proven, otherwise stop. The
TC-001 fixture and phone receipts are absent. Existing C3 serial observation
has prior `USB_UART_CHIP_RESET` evidence. `HIL_READY`/`GET_STATE` contain the
needed build/profile status, but no safe current query path is established. The
candidate HIL-awake image is available and rehashed at
`2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f`; installed
profile, active slot, whether an update is required, and exact prior-app
rollback image are all `NOT_VERIFIED`. No board update/reset was performed.

Current laptop service health: PostgreSQL, caregiver HTTPS, backend and
certificate-verified LAN endpoint `PASS`. Existing Hub-ingress implementation
is present, but its listener/autostart is disabled, authenticated physical Hub
identity is `NO`, freshness is `UNKNOWN`, and persistent ingress is
`NOT_CONFIGURED`; no S3 CloudSync receipt exists. The actual S3's running image,
trust/time, ownership epoch and Node enrollment are not safely observable. The
owner-reported APK Connected state does not identify its backend/Home; phone
reachability is `NOT_VERIFIED` and `adb` is unavailable. No event/EventKey was
created and no APK PASS is claimed. Detailed stage evidence and safe next
prerequisites are in
[`GS117_ANDROID_VERTICAL_READINESS_20261022.md`](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-fresh-physicalbackend-recheck--read-only).

### GS-117 / GS-179 receipt reconciliation — 2026-10-24, HEAD 063007d

Fresh read-only `usbipd` and sysfs checks map COM4 / `ttyACM0` /
`14:63:93:C5:D1:58` to the documented C3 identity and COM10 / `ttyACM1` /
`E0:72:A1:D3:8D:34` to the separate owner-designated GS68 spare ESP32-S3. The
exact COM10/USB-identity/board match is recorded in the owner-local
`GS68-20261017/stack8192-authorized-usb-fixture.json`; this corrects the prior
statement that COM10 was unmatched. The historical GS-114 S3 adapter identity
`5CBC401023` belongs to a different fixture. Neither serial port was opened.

The latest COM10 install receipt records an app-only diagnostic image from
2026-10-17 (`GS68_CLOUDSYNC_DS_MTLS_HIL`, SHA-256
`fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd`, source
`f501d985c1ce5b8b89f0786b42af6e5a179469cb`). The DS peripheral was selected
but not provisioned. This receipt is not current-image readback and does not
prove full product HubRuntime/CloudSync is running.

Live laptop health remains PASS for TLS-verified PostgreSQL, caregiver HTTPS,
local backend and certificate-verified LAN endpoint; phone reachability is
NOT_VERIFIED. The existing GS-179 ingress source is implemented but the
caregiver WSGI service does not mount/start it. Autostart is disabled, Hub
identity is unauthenticated, freshness is unknown and persistent ingress is
not configured. Current operator configuration has no Hub credential registry,
trusted-time/authority source or physical Hub/Home/epoch/Node enrollment
binding. Synthetic integration-test fixtures are not a safe physical Hub
configuration. No listener, credential, ownership, route or board settings
were changed.

Focused `test_gs179_runtime_composition` and `test_gs179_postgres_security`
regressions passed **21 tests**, with the registered runtime-process/mTLS/
PostgreSQL integration case skipped because no separate isolated
`GS179_TEST_POSTGRES_DSN` was configured. The caregiver database was not used
as a test database. This is software configuration/TLS-boundary evidence only;
it is not a physical Hub mTLS or CloudSync result.

Owner-reported APK Connected remains unverified on the phone; its backend
origin, authenticated Home and identity with this laptop database are unknown.
TC-001 remains NOT_RUN: no EventKey was created, and no HOST_SIM seed is
counted. Detailed stage results, limits and consolidated physical plan are in
[`GS117_ANDROID_VERTICAL_READINESS_20261022.md`](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-receipt-reconciliation-at-canonical-head-063007d).

Next action: obtain fixture-specific approval for a reset-safe read-only image
and configuration observation path. If the current S3 image is unsuitable,
separately approve an exact app-only image, measured slot, reboot behavior and
verified app-only recovery image. Provisioning remains separately gated on an
approved TEST_ONLY Hub identity, trusted-time/authority source, backend trust
registry and existing Home/Hub/epoch/Node binding. Verify APK origin/Home on the
existing phone before executing the existing TC-001 console. Preserve the
current Home, database, credentials, event history, device NVS and GS-114
qualification status.

### GS-117 physical execution audit — 2026-10-24, HEAD 5328c31

Read-only USB identity still matches COM4 to the documented C3 and COM10 to
the owner-designated spare S3. Both devices are attached to WSL; the Windows
TC-001 serial helper's `List` action returns no COM ports. Neither WSL TTY was
opened, and USB/IP ownership was not changed. ADB is absent on the host.

The existing 950,032-byte C3 HIL-awake artifact rehashes to
`2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f` with
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`; the normal sleep image rehashes to
`eec59be390315bad53e05bb7c3c60e0fd3311ec16a11d19040d3ad36ef4c733b`. Neither
is evidenced as installed. Historical Oct 9 full-flash backups are not valid
app-only rollback proof; the C3 snapshot contains seven retained pending
records and a different Hub pairing. The latest Oct 17 S3 record remains
diagnostic GS68 mTLS HIL with DS unprovisioned, not current full product image.

Read-only local database checks show TEST_ONLY `gs177-test-product` is enrolled
to synthetic `test-hub-product` / `test-c3-bedroom` and contains the preserved
single historical seed row. That is not a binding for the physical C3/S3.
Backend and caregiver service health remain PASS; physical Hub ingress is
unconfigured. Owner-reported APK Connected is not verified as using this
backend/Home; package, origin and actual event display remain NOT_VERIFIED.

Current focused software results: TC-001 console 17/17, C3 profile 4/4,
GS-179 verified endpoint 2/2; GS-179 configuration/TLS boundary 21 passed and
one isolated PostgreSQL mTLS runtime test skipped without a dedicated test
DSN. Physical TC-001 is NOT_RUN: no board access, EventKey, event commit or APK
observation. See the [dated execution audit](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-full-physical-e2e-readiness-audit--head-5328c31).

No safe current-image observer, reset-safe COM handoff, app-only rollback
package, physical Hub identity/trusted-time/ownership binding or phone receipt
is available. No flash, reset, USB detach, enrollment, credential or listener
change was performed. Keep all existing data and release/GS-114 statuses.

### GS-117 owner-authorized inspection — 2026-10-24, HEAD 44f53a1

Owner authorization was recorded in GS-117 comment 11618 for exact COM4 C3
`14:63:93:C5:D1:58` and COM10 spare S3 `E0:72:A1:D3:8D:34`: Windows port
discovery, reset-aware serial inspection and existing status queries; one
`INJECT_MOTION` only after current C3 mode and security/delivery prerequisites
are verified. Flash, eFuse, NVS, credential and ownership changes remain out of
scope absent compatibility, preservation and verified recovery evidence.

Fresh Windows PnP and the TC-001 helper matched both exact serial interfaces.
COM4 returned `GET_STATE`, with session 20, retained/in-flight 0, but
`sensing_live=0`, `runtime_live=0`; the response did not establish the running
firmware version or HIL-awake/build/physical-wake flags. COM10 opened once, but
no allow-listed startup/status line or HIL acknowledgement was captured. The
latest recorded S3 image is still diagnostic-only, not full product HubRuntime
+ CloudSync. No S3 retry/reopen followed the missing response, consistent with
the bounded one-open observer stop rule.

Laptop PostgreSQL/caregiver HTTPS/LAN TLS remain PASS. Physical Hub ingress is
still `NOT_CONFIGURED`; real Hub certificate/trusted-time/ownership/enrollment
binding and phone package/origin/Home evidence remain absent. Therefore no
injection was issued. TC-001 remains `BLOCKED` / `NOT_RUN`, with no EventKey,
new database record or APK observation. The full stage evidence and stop
reason are in the [dated GS-117 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-owner-authorized-physical-inspection--head-44f53a1).
No flash, reset command, USB/IP detach, credential, ownership or database
change occurred; serial-open reset effects are not qualified. Existing
untracked/ignored files, all stored data and GS-114 status remain preserved.

### GS-117 current-source C3 HIL-awake deployment — 2026-10-24, HEAD 60574c4

Owner-authorized COM4 app-only deployment used the ESP-IDF 6.0.3 C3 product
build from canonical HEAD `60574c4d3b98ded68bd18df611335afea48862fc`. Candidate
version `60574c4-gs117-hilawake-20261024`, SHA-256
`d1e7f89d473d3443b4b0380a53764f7521e88df2a452251f8a326656a8d74136`, with
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`. It was installed to the verified blank
`ota_1` app partition only; full-slot readback matched. COM4 identity and
installed `HIL_AWAKE_TEST_ONLY` state were verified; 27 status queries were
responsive with stable later heap. The untouched prior `ota_0` app is retained
as manual recovery. Automatic rollback is not claimed for the host selector
method. The separate normal sleep-enabled C3 build succeeded and was not
flashed. GS-114 physical-wake/battery qualification is unchanged.

C3 state remained `sensing_live=0`, `runtime_live=0`; therefore the physical
NodeRuntime is not ready and `INJECT_MOTION` was not issued. COM10 is verified
as ESP32-S3 rev 0.2, 16 MiB flash / 8 MiB PSRAM, but its current product image
and Hub credentials/ownership/trusted time are not verified. Existing TC-001
fixture receipt is absent; current laptop readiness is PostgreSQL, caregiver
HTTPS, backend and LAN TLS `PASS`, with `HUB_INGRESS_READY=NOT_CONFIGURED`.
TC-001 remains BLOCKED/NOT_RUN with no new EventKey, database event or APK
observation. See the [deployment evidence](../hw/evidence/GS117_C3_HIL_AWAKE_FLASH_20261024/README.md)
and [dated handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-current-source-c3-hil-awake-deployment--head-60574c4).

C3 USB profile regression **4/4 PASS**; TC-001 console regression **17/17
PASS**; normal sleep-enabled firmware build **PASS**. `make -C code
validation-node` completed with exit **2**, `software_status=FAIL`,
`physical_status=NOT_RUN`, and source unchanged. The registered C3 HIL profile
stage passed **4/4**; 29 other stages passed. `p0-full-product-e2e` is a gate
FAIL because `product_status=PARTIAL` while physical qualification is
`NOT_RUN` (all 26 scenario assertions passed). `gs178-node-caregiver-e2e` ran
33 tests and failed the existing browser assertion `[data-event-key]` expected
2, received 0, in `test_07_actual_shared_caregiver_browser_and_actions`; product
source was unchanged. Host board-stack simulation passed 10 groups and is not
physical evidence. No source implementation changed; only scoped
status/evidence documentation is intended for commit. Untracked and ignored
owner assets and all existing application/device data remain preserved.

Next action: complete the existing Hub identity/trusted-time/mTLS/ownership and Android APK/Home receipts
before attempting the existing TC-001 console. Require C3 `runtime_live`
to advance before injection; do not treat HIL UART acknowledgement alone as a
NodeRuntime event or claim physical end-to-end success.

### GS-117 S3 authenticated-session dependency and infrastructure policy — 2026-10-24, source HEAD afc2486

At source HEAD `afc248610f897882482bad0d2eb830bd37b61a3b`, read-only COM10
flash inspection matched USB identity `E0:72:A1:D3:8D:34` to the owner-
designated ESP32-S3 rev 0.2 / 16 MiB flash / 8 MiB PSRAM. Its partition table
selects `ota_0` (two 4 MiB app slots and the existing journal partition). The
active app readback is 278,480 bytes, SHA-256
`fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd`, and
matches the saved GS-68 receipt for the diagnostic-only
`GS68_CLOUDSYNC_DS_MTLS_HIL` profile. The DS identity was recorded as selected
but not provisioned. This is not the complete `gs_r1_s3_hub` product
composition. No S3 flash, eFuse, NVS, journal, credential or ownership write
occurred.

The C3 HIL-awake image remains unchanged from its authorized deployment. Its
most recent state was `sensing_live=0`, `runtime_live=0`; source confirms
NodeRuntime admission begins after its authenticated Hub security link is
ready. Thus `runtime_live=0` without a session does not demonstrate a C3
firmware regression. A live matching Node enrollment/Home/Hub/epoch binding
has not been established. The local TEST_ONLY Home still names synthetic
`test-hub-product` / `test-c3-bedroom`, and laptop Hub ingress is
disabled/unconfigured. PostgreSQL and caregiver HTTPS health pass, but no
physical Hub mTLS/CloudSync receipt exists. The owner's reported APK Connected
state does not verify its backend origin or Home.

Reuse audit: the full S3 product HubRuntime and CloudSync composition already
exists; `GS40_TEST_ONLY_CLOUDSYNC` is its explicit default-OFF isolated profile
and uses the guarded one-session bootstrap. The separate GS-68 diagnostic
composition cannot substitute for it. Existing JSON inputs are narrow, not a
general infrastructure feature map; no new flag system, runtime or backend was
added. The GS40 bootstrap regression passed 47 checks and existing security,
rejoin and CloudSync regressions passed as recorded in the handoff. TC-001 was
not run: no new EventKey, S3 admission, database event, caregiver presentation
or APK observation exists. The historical HOST_SIM event remains excluded.

Additional source/fixture compatibility check: the live table matches the
development `partitions.development.csv`: `gs_journal` is a 2 MiB NVS partition
at `0x820000`. Product `LittleFsSegmentStore` requires a `gs_outbox` LittleFS
partition with formatting disabled on mount failure. The separate product
candidate table allocates 4 MiB `gs_outbox` at `0x820000` plus 256 KiB `gs_state`
at `0xC20000`; it overlaps/reinterprets the current journal bytes. Therefore an
app-only product image against the current table is incompatible and cannot
admit durable events. Changing the table is a storage-layout migration, not an
app-only update. The current journal partition was not read or written. No
migration/recovery evidence exists, and no repartition was attempted.

One earlier `gs179-laptop-server.sh health-source` invocation was not
read-only: it ran the existing HOST_SIM health scenario and accepted a
synthetic `test-c3-bedroom` NodeHealth update (source revision 8). It did not
create or alter a business-event row; the backend still has only the preserved
historical HOST_SIM seed. The command was not repeated and no rollback was
attempted. This is recorded for traceability, not physical evidence.

Owner-directed engineering policy for future work: keep optional provisioning
automation, credential-lifecycle management, fleet management and nonessential
operations OFF by default in product-development profiles; enable a supporting
capability only in its explicit implementation/validation profile. Retain all
foundational security and durability checks. Reuse existing JSON/profile/build
mechanisms and do not add a second feature-flag system. Release gates remain
responsible for required commercial capabilities even when development defaults
are OFF. For TC-001, do not require commercial commissioning or fleet services;
use the existing product/TEST_ONLY path with only its authorized identity and
authority prerequisites, and a product-compatible durable outbox layout.
Existing GS40 test secrets remain ephemeral under their security contract. Full
policy: [CloudSync and configuration
architecture](../architecture/STORAGE_SYNC_ROUTINE_LEARNING.md#configurable-supporting-infrastructure-policy-2026-10-24).

Validation on this source: `make -C code gs40-test-only-bootstrap-test
gs40-config-test cloudsync-security-ut rejoin-host-test
p2d-https-channel-host-test p2d-cloud-contract-host-test` exited 0. It passed
the envelope suite 47 checks; NodeHealth JSON/config suite 17 tests; CloudSync
mTLS adapter 9, TEST_ONLY adapter 5, trust-provider 5 suites; backend CloudSync
security 14, identity/time integration 4, issuer 10, NodeHealth API 5; secure
rejoin; HTTPS transport 8 modes; and cloud receipt/recovery checks (15 invalid
receipt modes and 2 persistence-cut modes). These are software regressions,
not physical Hub, backend-ingress or APK evidence. See the
[GS-117 dated handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-s3-authenticated-session-and-configurable-infrastructure-policy).

## GS-117 / GS-68 development S3 storage deployment and network recheck — 2026-10-24, source HEAD e9e610b

The owner approved the existing product ESP32-S3 storage layout for the
development COM10 board after preservation and recovery checks. Current
identity is USB serial/MAC E0:72:A1:D3:8D:34, ESP32-S3 rev 0.2, 16 MiB flash
and 8 MiB PSRAM. The existing product candidate table now supplies 4 MiB
LittleFS gs_outbox at 0x820000 and 256 KiB NVS gs_state at 0xC20000 while
preserving two 4 MiB OTA slots. The former 2 MiB gs_journal readback contained
no allocated records. The outbox filesystem was explicitly initialized;
mount-on-failure formatting remains disabled. OTA0, bootloader, base-NVS keys,
credentials and C3 were preserved. Recovery is manual via backed-up OTA0 and
saved table/selector; no automatic rollback is claimed.

The complete gs_r1_s3_hub product app was installed app-only to selected OTA1.
After the first product build used UART0 and yielded no COM10 startup lines, a
second app-only build changed only the debug console to native USB
Serial/JTAG. Its 2,194,768-byte readback matches SHA-256
a46c843ef66f4a0862668304b27f6cf6079ee70c0e2e48a3acbaa6e307462fa7. The
selected product app is verified installed. Runtime startup and LittleFS mount
remain NOT_VERIFIED because the existing identity-pinned observer captured no
startup lines and then hit a PnP query timeout before opening COM10. The
product build has GS40_TEST_ONLY_CLOUDSYNC=OFF. No physical Hub identity,
current Node enrollment, time authority or GS-179 mTLS ingress configuration
is present, so authenticated event admission and CloudSync remain blocked.

The Agrim recheck reports Airtel_Agrim / Private / 192.168.1.10/24; WSL NAT is
172.17.152.10. PostgreSQL durability/TLS and local caregiver HTTPS pass.
LAN HTTPS fails because Windows still forwards stale 192.168.1.7:443 to the
current WSL listener at 172.17.152.10:8444. The existing scoped proxy start
requires a Windows administrator token, which is not available; no firewall
or forwarding rule was changed during this recheck. Phone-side APK origin,
Home and event presentation remain NOT_VERIFIED.

C3 was not reflashed, no serial injection occurred, and no new EventKey,
database business event or Android observation exists. Latest C3 state remains
runtime_live=0 and sensing_live=0 pending authenticated Hub readiness.
TC-001 remains NOT_RUN/BLOCKED, the HOST_SIM seed remains excluded, and
GS-114 physical-wake/battery qualification is unchanged. See the [dated
GS-117 execution evidence](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-owner-approved-s3-product-storage-deployment-and-agrim-network-recheck).

### GS-117 fresh Agrim and C3↔S3 identity recheck — 2026-10-24, HEAD 94be192

Fresh authorized COM4 `GET_STATE` still reports `HIL_AWAKE_TEST_ONLY`,
`hil_control=1`, `runtime_live=0`, and `sensing_live=0`; C3 was not reflashed
and no motion was injected. Read-only source-derived identity comparison
shows current COM10 MAC `e0:72:a1:d3:8d:34` maps to Hub ID
`hub-e072a1d38d34`, while the COM4 NVS health-ACK pin names a different
historical Hub. The encrypted C3 association binding was not decoded or
changed. COM10 `gs_state` readback is all-erased; base NVS was not dumped, so
this does not establish whether identity metadata exists outside `gs_state`.
Current ownership and Node enrollment remain unverified. The installed product app
readback is verified, but S3 runtime mount/startup is NOT_VERIFIED and
TEST_ONLY CloudSync remains OFF.

Agrim is `192.168.1.10/24`; local PostgreSQL durability/TLS and caregiver
HTTPS pass. Existing Windows LAN portproxy remains bound to stale
`192.168.1.7`; refreshing it requires the unavailable administrator token.
Phone reachability and actual APK backend/Home/event remain NOT_VERIFIED.
No new EventKey or backend row exists, and the HOST_SIM seed remains excluded.
TC-001 is BLOCKED/NOT_RUN pending the existing authorized matching
TEST_ONLY Home/Hub/Node ownership, time and mTLS fixture; no identity,
credential, NVS or ownership changes were performed in this recheck. Full
stage evidence and private-readback hashes are in the
[GS-117 dated handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-agrim-recheck-and-c3s3-identity-evidence--source-head-94be192).

### GS-117 physical identity/TEST_ONLY contract compatibility — 2026-10-24

An additional source audit established that the current physical C3/S3
identities are MAC-derived (`c3-<MAC>` and `hub-<MAC>`), while the existing
GS40 TEST_ONLY bootstrap, GS-179 Hub ingress, TC-001 fixture and backend
helper accept only synthetic `test-c3-*` / `test-hub-*` identities. They
cannot safely identify this physical pair under the existing TEST_ONLY Home
without an approved identity binding; no alias or guard bypass was introduced.
GS-D032's proof-of-possession/Home-epoch behavior is LOCKED, while the target
`GS40T/1` bootstrap details remain PROPOSED. No issuer, matching Node
enrollment, trusted-time or mTLS fixture is present. TC-001 remains
BLOCKED/NOT_RUN. Required next input is an approved minimal TEST_ONLY
identity/ownership and trust contract for the existing Home and these exact
physical IDs; this is a security/product decision, not a routine serial or
network step. The existing Agrim proxy also needs a scoped Windows-admin
refresh. See the [GS-117 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-physical-identity-compatibilitysecurity-contract-boundary).

### GS-117 physical MAC-identity syntax integration — 2026-10-24

The source-level syntax mismatch is now corrected in the existing isolated
TEST_ONLY path: strict MAC-derived C3/S3 IDs are accepted by GS40 bootstrap,
GS-179 ingress and TC-001 checks, while the Hub runtime exact-MAC binding,
verified certificate fingerprint, active Home/epoch ownership and Node
enrollment guards remain mandatory. Existing HOST_SIM IDs remain supported;
production validation is unchanged. This does not provision or enroll the
physical pair. Focused GS40 bootstrap, TC-001 console and isolated
GS-179/PostgreSQL runtime tests pass. The full product S3 TEST_ONLY build
completed successfully as build-only; the installed application was not
changed.

Current physical status remains: COM4 has the already-installed HIL-awake C3
app (945,584 bytes, SHA-256
`d1e7f89d473d3443b4b0380a53764f7521e88df2a452251f8a326656a8d74136`), with
HIL build off/control on/physical wake off; it was not rebuilt or reflashed.
C3 `runtime_live=0`, `sensing_live=0`; its readable health-ACK pin names
`hub-7c4fadb72a20`, not current COM10's
MAC-derived `hub-e072a1d38d34`; S3 startup/mount is NOT_VERIFIED and installed
TEST_ONLY CloudSync is OFF; there is no verified physical Home/epoch/Node
enrollment, trusted-time or mTLS package. No HIL event was sent. The Agrim
portproxy remains stale at `192.168.1.7`, and refresh requires Windows admin.
No ADB evidence is available for the existing APK, so phone origin/Home/event
remain NOT_VERIFIED. TC-001 is NOT_RUN; the HOST_SIM seed is excluded. Exact
tests, stage evidence and required external fixture are in the
[dated GS-117 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-strict-physical-identity-compatibility-implementation).

The full S3 `gs_r1_s3_hub` product TEST_ONLY build passed from current source
(2,243,408-byte build-only image, SHA-256
`3add51b98fa21192b42ae07b75eba31985e19c82dc46f6e2036ae4ce094b34ed`,
47% application-slot headroom). It uses an ephemeral public root build input
and was not flashed. The Hub component gate passed the board-stack simulation
(10 groups) and most security/storage regressions. The full Hub gate ran 55
stages: 49 PASS and 6 FAIL. Failures were three cold-build timeouts, the known
legacy journal migration assertion (`clean migration commits`, returning
`NotCommitted` while the checkpoint is in `migration_view`), P0 vertical
`product_status=PARTIAL`, and one GS-178 browser-helper timeout. Warmed direct
retries then passed `validation-build`, the GS148 reader-compatibility target
and the full storage sanitizer suite; the GS-178 retry is recorded in the
dated handoff. The existing GS148 architecture review requires preserving
this owner-domain guard pending the GS-D001/GS-116 scope decision; no storage
fix was attempted. A live Windows query now reports Wi-Fi profile `Yogi` as
Public at `192.168.1.6/24`, not the earlier owner-reported Agrim `.10`; the
portproxy still listens on stale `.7`. The repository proxy script is blocked
by PowerShell execution policy in this session, and it refuses mutation on a
Public profile. Full gate stages and exact results are in the
[GS-117 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-strict-physical-identity-compatibility-implementation).

Follow-on affected-suite results: backend gate 23/26 stages PASS (TC-001
console 19/19, verified endpoint 2/2, GS-178 33/33); its remaining failures
are the existing CSS budget, diagnostic-stage registry expectation and P0
`PARTIAL` result. Contract gate 47/48 stages PASS; its only failure is P0
`PARTIAL`. `make feature-coverage-test` passes for 226 features/281 modules/27
physical cases. No TC-001 EventKey exists and the physical stages remain
BLOCKED/NOT_RUN; the Android APK remains NOT_VERIFIED. The newer live Windows
profile/route result and all stage-level counts are in the dated handoff.
The existing GS-168 software-only credential issuer intentionally remains
synthetic-ID-only and host-keyed; it is not an authorized physical Hub issuer.
No physical key/CSR-backed TEST_ONLY certificate registry or matching
Home/epoch/Node binding is available, so the syntax change does not enroll or
authenticate the boards.

## 2026-10-24 latest GS-117 live recheck

From source `3cf644b928cb1c573ce80c0d4887e0e984964627`, live COM discovery
again matches COM4 to C3 USB serial `14:63:93:C5:D1:58` and COM10 to S3
`E0:72:A1:D3:8D:34`. Reset-aware C3 `GET_STATE` confirms the HIL-awake profile
and `runtime_live=0`, `sensing_live=0`, `retained=0`, `in_flight=0`; no
injection was sent. S3 passive UART observation produced no startup markers,
so its HubRuntime and storage startup remain NOT_VERIFIED.

The live Yogi Wi-Fi is now Private at `192.168.1.8/24`; the existing GS-179
portproxy is still stale at `.7:443 -> 172.17.152.10:8444`, and the current
Windows token is not elevated. The existing caregiver/PostgreSQL service is
healthy. A local CA- and hostname-verified API check confirmed the existing
Home `gs177-test-product` and authenticated GS-148 projection, with stale
monitoring. Read-only registry inspection found no ownership/enrollment for
the historical or current physical Hub and no physical C3 commits. Hub ingress
is still disabled and lacks physical client identity/trusted-time authority;
the S3 CloudSync build remains OFF. ADB is unavailable, so APK verification is
NOT_VERIFIED and TC-001 remains BLOCKED/NOT_RUN with no EventKey. Exact stage
evidence, focused regressions, and the one consolidated authority/network gate
are in the [GS-117 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-live-c3s3-backend-and-route-recheck).

### 2026-10-24 GS-117 fixture integration implementation

Current source adds recoverable same-Home C3 reassociation through the existing
commissioning proof/Offer/ACK path, with a guarded HIL-awake-only request for
the exact `hub-e072a1d38d34` fixture. Old association and encrypted retained
EventKey/retry state are copied to bounded NVS backup stores and verified
before a binding change. The existing GS40 TEST_ONLY host config accepts that
exact Hub only for `gs177-test-product`; this does not grant authority or
provide credentials. The TC-001 local API helper now routes through the
current WSL listener while retaining HTTPS hostname/SNI/CA verification.

Validation: C3 HIL-awake and normal sleep-enabled builds and full S3 product
build passed (hashes and flags in the linked handoff); association and recovery
host tests, GS40 fixture bootstrap (59), identity/time fixture (6), TC-001
console (19), verified endpoint (4), USB stable profile (4), battery invariants
(11), signed FOTA fixture (23), GS-178 isolated software E2E (33), board-stack
simulation (10 groups) and feature mapping (226 features) passed. The broader
Node gate remains FAIL on P0 `product_status=PARTIAL` and one cold GS-178 timeout;
the isolated 33-test rerun passed.

Physical acceptance remains BLOCKED/NOT_RUN: C3 reports HIL-awake but
`runtime_live=0`, `sensing_live=0`; S3 identity is observed by USB but product
startup/storage/CloudSync are not verified; the authenticated physical Hub
certificate, trusted time and current Home/epoch/Node enrollment are absent;
the Windows Yogi Wi-Fi is Public and its existing portproxy targets stale
`.7`; Android diagnostics are unavailable. No firmware, credentials,
ownership, data or event history changed; no motion was injected and no new
EventKey exists. Exact live evidence and candidate hashes are in the
[GS-117 execution handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-fixture-integration-implementation-and-executable-validation).

### 2026-10-24 GS-117 C3 app-only install and live association result

The authorized current C3 HIL-awake application was installed app-only on the
identified COM4 device. The new app readback exactly matches SHA-256
`86bb487dfbc41d3e781d115cc014144202a424b714185ca1ee95fec517098fdd` and
boots from inactive `ota_1`; the prior `ota_0` app readback and the full
inactive slot were preserved before write. Only the `ota_1` application range
and OTA selector metadata were written. NVS, partition table, bootloader,
credentials, association and retained-event state were not written. The
installed image reports `HIL_AWAKE_TEST_ONLY`, HIL control enabled, physical
wake disabled; serial status requests remain responsive. A normal
sleep-enabled C3 build also passes, with no change to GS-114 qualification.

One authorized authenticated reassociation request was attempted through the
existing commissioning path. Firmware rejected it with `home_mismatch` and
preserved the current binding/recovery snapshot. This is the verified blocker,
not a reason to bypass Home ownership. C3 remains `runtime_live=0`,
`sensing_live=0`; no motion was injected and no new EventKey exists.

COM10 identifies the physical S3 and its active full-product `gs_r1_s3_hub`
image and product partition table were read back. The table already includes
`gs_outbox`/`gs_state`; the S3 was not flashed. No HubRuntime, storage-mount
or CloudSync startup markers were observed, so runtime status remains
`NOT_VERIFIED`. A physical Hub client credential, trusted-time authority and
authorized Home/epoch/Node binding are not configured in GS-179. The existing
caregiver backend Home and database do not prove physical Hub identity. Phone
side APK event visibility remains `NOT_VERIFIED`.

**TC-001 is `BLOCKED / NOT_RUN`.** There is no fresh C3 EventKey, S3 receipt,
CloudSync acknowledgement, physical PostgreSQL commit or Android APK event
observation. The historical HOST_SIM seed remains excluded. Full source,
installation, recovery and stage evidence is in the [GS-117 dated
handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-c3-app-only-deployment-and-reassociation-result).

Current-source validation: the Node gate ran 30/31 stages PASS; the only
failure is P0 reporting `product_status=PARTIAL` because physical qualification
is `NOT_RUN`. The contract gate ran 47/48 stages PASS; its only failure is the
same P0 physical status. The CloudSync security stage itself passes after its
registered expected identity/time suite count was corrected to 6; its full
security target passed, and the validation framework tests passed 51/51.
Focused C3 association/recovery, GS40 fixture and BAT-C8 checks passed. These
software results do not alter the physical TC-001 status.

### 2026-10-24 resumed GS-117 S3 commissioning/CloudSync profile

From canonical source/remote HEAD `eea7e176d94a74638d7b17b894266ba1d4b6638c`,
the full-product S3 TEST_ONLY build guard now permits the existing
`GS_HIL_COMMISSIONING` fixture adapter together with
`GS40_TEST_ONLY_CLOUDSYNC`; both are default-OFF and all legacy HIL/fault/FOTA
controls remain rejected. The isolated ESP-IDF 6.0.3 build passed at 2,253,664
bytes (SHA-256 `692aa9df6cc9b3f6d04d427a01ed98b4072417a63b64ce7de96e37551a50553a`)
with 46% headroom in the 4 MiB app slot. It used a disposable config-root
public key and was not flashed or provisioned. The exact implementation,
build fingerprints, live fixture evidence and gate reports are in the
[GS-117 handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-24-resumed-gs-117-s3-profile-integration).

Focused fixture coverage passes 17/17. `validation-hub` is 53/55 with the
existing reproducible `hub_journal_migration_validation` failure and required
P0 `product_status=PARTIAL`; `validation-contract` is 47/48 with the same P0
partial result. Fresh USB evidence again maps COM4 to the approved C3 and
COM10 to the approved S3; C3 is HIL-awake but `runtime_live=0` and
`sensing_live=0`; S3 runtime/storage/CloudSync startup is still
`NOT_VERIFIED`. The reassociation guard returned `home_mismatch` earlier and
has not been bypassed. The live Windows Wi-Fi is Public with no IPv4 address,
ADB is absent, and no authenticated physical Hub certificate/trusted-time/
Home-epoch registration is configured. No motion event, database mutation or
firmware update occurred. TC-001 stays BLOCKED/NOT_RUN; Android stays
NOT_VERIFIED.

### 2026-10-25 GS-117 fixture integration checkpoint

Current canonical branch is `feature/r1-commercial-baseline`; local and remote
source baseline is `1e08b32397dbc0a98dbe23b17ec089e589bf0d55`. Context preflight
passed. The scoped working-tree integration adds exact-fixture C3 fresh
commissioning with a verified encrypted-association/recovery backup and
monotonic retirement limited to owner-approved disposable TEST_ONLY motion
records; physical S3/Home namespace compatibility at GS-179; and composition
of the existing fixture UART path with the full-product S3 TEST_ONLY CloudSync
profile. Existing commissioning proof, HubRuntime, security and event handling
are reused. No new event pipeline or Home/backend/APK was created.

Focused checks after traceability corrections: `make feature-coverage-test`
PASS (226 features, 285 modules, 27 physical cases; 22/22 tests), engineering
stage registration 6/6 PASS, TC-001 console 21/21 PASS, fixture commissioning
18/18 PASS, GS40 bootstrap 82 checks PASS, GS178 Node/caregiver E2E 33/33
PASS, GS-179 runtime composition 4 PASS/1 isolated-PostgreSQL skip, JSON parse
and `git diff --check` PASS. Node/Hub/contract component reports remain gated
by required P0 `product_status=PARTIAL` because physical acceptance is
`NOT_RUN`; Hub also has the known clean-journal migration failure. The previous
backend suite had one unrelated PWA CSS-budget failure and was not rerun after
the traceability fixes.

Physical status: COM4 still identifies C3 `14:63:93:C5:D1:58`, installed
`HIL_AWAKE_TEST_ONLY`, with `runtime_live=0` and `sensing_live=0`; no
commissioning or motion command was sent. COM10 identifies S3
`E0:72:A1:D3:8D:34`; the full-product TEST_ONLY CloudSync candidate
(`21e78b2882f180e917c2d6dd5599d5a1f0fbfa1c9b7d18a782e8ef5f49ea05c6`,
2,267,584 bytes) builds and fits the 4 MiB app slot, but has no active
authenticated Hub credential/time/ownership envelope and was not flashed.
S3 boot, storage and CloudSync remain `NOT_VERIFIED`.

The latest-source C3 HIL-awake profile also compiles under ESP-IDF 6.0.3 to
958,368 bytes (SHA-256
`183417fdd840ed9cce333e7b276beeaba83d085173f9cbe28589d617d874739f`), with
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`, and light-sleep PM disabled by the TEST_ONLY
profile. `INJECT_MOTION` and the guarded fresh-commissioning command are in the
binary, which fits the 1,920 KiB OTA app slot. This compile-only image is
unsigned; the current trusted signing key and recovery compatibility were not
verified, so it was not flashed.

Existing PostgreSQL/caregiver backend and the authorized
`gs177-test-product` API login are ready, but source freshness is `STALE` and
there is no physical event. Wi-Fi is `Airtel_Agrim`, Private,
`192.168.1.6/24`; the existing scoped proxy still targets `.7`, and this
process is not elevated. Android ADB/phone observation is unavailable. TC-001
therefore remains `BLOCKED / NOT_RUN`: no new EventKey, physical S3 receipt,
CloudSync commit or actual APK presentation exists; the historical HOST_SIM
seed is excluded. No hardware flash, protected-storage update, credential or
ownership change, DB mutation, or event-history change occurred. Detailed
stage evidence is in the [2026-10-25 GS-117
handoff](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-25-resumed-gs-117-fixture-integration-and-validation).

### 2026-10-25 C3 inactive-slot deployment update

Current source is commit `b629b3e04a7b5ca63d23238a37e3f72a5a8cb63b` on
`feature/r1-commercial-baseline`, pushed and verified at origin. Under the
owner's existing C3 app-only deployment authorization, the latest-source
HIL-awake app (`183417fdd840ed9cce333e7b276beeaba83d085173f9cbe28589d617d874739f`,
958,368 bytes) was written to the verified inactive `ota_1` only. Full slot
readback matched the candidate prefix exactly; official ESP-IDF OTA selector
update to slot 1 passed its write-hash verification. The prior app remains in
`ota_0`; NVS and retained state were not written. Secure Boot and Flash
Encryption are confirmed disabled by read-only device security query.

The expected reset occurred, but post-boot COM observation is now
`NOT_VERIFIED` because Windows interop from WSL fails with
`UtilAcceptVsock: accept4 failed 110`. Thus the C3 app/selector deployment is
verified at flash readback, while installed-image startup, HIL state and
NodeRuntime readiness are not yet verified. No association or motion command
was sent. The S3's live readback confirms the approved `gs_outbox` and
`gs_state` product partition layout; S3 runtime/mount/CloudSync startup is
still `NOT_VERIFIED`. TC-001 remains `BLOCKED / NOT_RUN` with no new EventKey,
backend commit, or Android APK event. See the [dated GS-117 deployment
evidence](../exec-plans/evidence/GS117_ANDROID_VERTICAL_READINESS_20261022.md#2026-10-25-authorized-c3-inactive-slot-deployment).

## 2026-10-25 GS-117 native physical access recovered

Canonical entry HEAD `30af100d2d5c84b56c7bd7abc99be031cd075cc6`, context PASS.
Windows execution and the existing native serial helper work again, without a
WSL restart or bridge configuration change. COM4 and COM10 match the expected
USB identities. Repeated C3 status samples establish active `ota_1`, session 99,
`HIL_AWAKE_TEST_ONLY`, HIL build/control/physical-wake flags 0/1/0, stable heap,
and empty event queues. No C3 write/reset, commissioning or motion was issued.
The prior verified candidate write plus current running-slot evidence clears
the C3 post-boot-observation blocker; runtime/sensing remain 0 pending Hub auth.

One authorized same-stream S3 boot observation now proves the full product
`gs_r1_s3_hub` version `e9e610b` starts from OTA1 and then reports `Hub security
bootstrap failed closed`. The installed non-fixture identity profile reaches
the protected production checks on this development board; no security check
was removed. Storage mounts, HubRuntime and CloudSync remain unverified.

Implementation delivered/prepared in this continuation: existing native helper
retains full HIL and boot/error lines, supports an explicit S3 status/reset and
bounded encrypted GS40 config carrier; existing GS40 profile installs its native
USB driver/VFS; existing GS168 issuer gains owner-only persistent exact-fixture
CA support; existing GS68 time carrier accepts a supplied signing key and an
explicit private bind. Default synthetic and production behavior stay guarded.
Fixture CA/client/time/lease material is prepared outside Git but not installed
or registered as backend ownership. Corrected full S3 product build passes and
fits its existing slot. Tooling issued no S3 firmware, partition or credential update.

Focused console/issuer/security/UDP/target tests pass. The existing ingress
process test now passes all five cases using isolated PostgreSQL schemas rather
than skipping its database case. Existing Home remains `gs177-test-product`,
with one preserved historical business event and no physical Hub/Node registry
rows. Current authenticated caregiver API is ready but stale/monitoring UNKNOWN.
The existing endpoint refresh preserves its trust root/login and follows the
current Wi-Fi IP; LAN portproxy remains stale and needs Windows elevation.

TC-001 is still `BLOCKED / NOT_RUN`; no new EventKey or APK acceptance exists.
The exact next deployment prerequisite is the owner-approved protected
`Airtel_Agrim` Wi-Fi config (the saved Windows secret was not extracted), plus
approved elevated scoped networking. Then complete the prepared signed config,
verified inactive-slot S3 update, existing authenticated fresh commissioning and
physical ingress ownership; inject only after those pass. Android diagnostics
are unavailable; actual phone observation remains required. Detailed evidence,
validation limits and precise resume steps are in the
[GS-117 native-access record](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md).

### GS-117 final paired build and delivery source

Implementation commit `0af99da0451a1c4eb8cc8d5ea034efc51f3893b6` is pushed and
remote-verified. The clean-source S3-only rebuild replaces the older embedded
Node asset with the exact installed C3 binary, without rebuilding/flashing C3.
Current prepared S3 image is version `0af99da0451a-gs117-test`, 2,270,336 bytes,
SHA-256 `59f9ffb80ce7f7d7af94af691f7dc7cdfe11fb39737835d08c29e44893bf1047`.
Its embedded C3/root and partition-reference checks PASS; image-info validates
ESP32-S3/16MB/DIO/40MHz. The initial `1290e680` candidate is superseded and
preserved. The new app is backed up under the owner-only
`~/.local/state/ghar-sajag/gs117-tc001/s3-ready-0af99da0451a/` directory.
No S3 flash/credential update occurred; protected Wi-Fi input and scoped
Windows elevation remain the immediate external prerequisites. Exact matched
software gate outcomes and artifact provenance are in the native-access record.
TC-001 and actual APK acceptance remain NOT_RUN/NOT_VERIFIED, respectively.


## 2026-10-25 GS-117 S3 app-only deployment, precise TLS rejection and requested pause

Entry71ebd920b6e49cd3cf0eda2cb02dff7f9e1564bf; scoped owner Wi-Fi reuse approval recordedGS117/11671. Fresh live S3 backup/partition/identity/recovery checks passed. Existing full-product commissioning+CloudSync app installed/read back inOTA0; protected NVS/table/oldOTA1/outbox/state byte-preserved. Actual boot proven. Existing signed encrypted GS40 transport succeeds through signature/decryption, but target policy reports fields=1/time_key=1/authority_key=1/tls_identity=0. Added only fixed-name nonsecret diagnostics; no security check relaxed. Final instrumented candidate fdb1555a795214dea12aece2a822d56cd6985ec571d990972c5060d3fe1052d6 preserved. At owner-requested8% usage pause, official selector returned to retainedOTA1 recovery to avoid config-rejection reboot looping; current recovery observation/evidence in dated record. C3 unchanged, session99/awake, runtime/sensing0; no commissioning/injection/EventKey.35 focused tests and82 bootstrap checks PASS, target build/write/boot PASS; broader gates not rerun for diagnostics; prior failures unchanged. Existing caregiver/PG/Home preserved. UAC request canceled, scoped LAN proxy unchanged. No physical ingress or APK acceptance. Exact next action is diagnose the target TLS identity subcheck, fix compatibility without weakening checks, then resume existing secure fixture pipeline.

Detailed deployment/backup/recovery paths, software delta, evidence and resume sequence: [GS117 native-access execution record](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md#2026-10-25-scoped-wi-fi-authorization-physical-s3-deployment-and-rate-limit-checkpoint). TC001 BLOCKED/NOT_RUN, APK NOT_VERIFIED.

### 2026-10-25 GS-117 authenticated-envelope transport retry

At source HEAD `d0e5f84ed5c56142452fc0ccec42bf4543e6aedb` on the canonical branch,
the S3 TLS target validator still has no new subcheck result. Comparing the
known successful OTA0 envelope delivery with the failed d0 candidate attempts
found a host transport regression: the existing helper had changed the proven
single `write(frame)` to a split, paced length/body transfer. The target saw
zero RX bytes with that split framing. Restored the one-write challenge-bound
frame, retained bounded host-write timing, and updated the existing helper
regression. TC-001 console tests passed 26/26; `make -C code
gs40-test-only-bootstrap-test` passed 84/84. No TLS checks were weakened.

Fresh COM enumeration still matches COM4 `14:63:93:C5:D1:58` and COM10
`E0:72:A1:D3:8D:34`; read-only C3 GET_STATE remains session99, HIL-awake,
runtime/sensing0. A new current `otadata` readback was saved mode0600 and
confirmed selector copies11/12 select OTA1 before the retry. The official
ESP-IDF `otatool.py switch_ota_partition --slot 0` then changed only otadata
and verified its write hash; OTA0 still contains the preserved d0 diagnostic
candidate and OTA1 remains the verified recovery app. The protected bootstrap
runner subsequently could not start the Windows port enumerator due
`UtilAcceptVsock: accept4 failed 110`; a second attempt failed at its
Windows-backed network preflight. No envelope reached COM10 and no target TLS
subcheck was produced. Do not claim current OTA0 startup or rollback until a
fresh observation; the next action is restore WSL-to-Windows interop, observe
COM10, then either send one full-frame protected bootstrap with the existing
helper or use the official selector to return to OTA1.

The local tracked delta is confined to `gs117_tc001_serial_windows.py` and its
existing Python tests; canonical documentation is being updated in the same
delivery. Existing unrelated untracked firmware/assets/evidence remain
untouched. No C3 write/injection, event insert, ownership change, TLS bypass,
or Android acceptance occurred. TC-001 remains BLOCKED/NOT_RUN; actual APK
event remains NOT_VERIFIED.

### 2026-10-25 GS-117 resumed S3 receive diagnosis

Source HEAD at resume was `d0e5f84ed5c56142452fc0ccec42bf4543e6aedb`; context
preflight PASS. Existing Windows serial identities remain COM4/C3
`14:63:93:C5:D1:58` and COM10/S3 `E0:72:A1:D3:8D:34`. Reused the existing
TC-001 serial helper and GS40 envelope protocol. Its bounded reset-aware path
now retains the S3 challenge, verifies the same COM identity after
re-enumeration, and reopens before TX; it restores the historical paced
256-byte whole-frame transfer. No security or ownership check changed.

The exact OTA0 candidate
`d4517c92a6ce5f8c2ce3aae1cbe98a984f886b9c7149b83e5ba47a5007669ade`
still reports `GS40T/1 RX status=timeout stage=length bytes=0` after a
7,323-byte host write. This blocks all later envelope/TLS checks; the previous
`tls_identity=0` remains undiagnosed. Official ESP-IDF `otatool.py` restored
OTA1 with a verified selector write. Reset-aware observation then confirmed
OTA1 (`0x420000`, version `e9e610b`) and its existing fail-closed Hub security
bootstrap. OTA0 and the protected recovery/backups remain preserved.

Current physical state: C3 COM4 HIL-awake, session99, retained/in-flight0,
`runtime_live=0`, `sensing_live=0`; S3 COM10 selected OTA1 recovery. No motion
injection, fresh EventKey, S3 admission, backend COMMITTED, caregiver event or
APK observation. Existing PostgreSQL/Home/history unchanged. TC-001 remains
BLOCKED/NOT_RUN; Android event visibility NOT_VERIFIED.

Checks: TC-001 helper 26/26 PASS; GS40 bootstrap host checks 85/85 PASS;
`git diff --check` PASS. Five-hour status tool returned null for goal and
remaining budget, so the percentage is unavailable. Detailed exact retries
and artifacts are in the [GS-117 physical access record](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md#2026-10-25-resumed-physical-s3-receive-diagnosis).

### 2026-10-25 — latest GS-117 S3 receive-path evidence

Fresh native Windows COM evidence identifies COM10 (`303A:1001`, serial
`E0:72:A1:D3:8D:34`) as the S3 USB Serial/JTAG endpoint, not a CH343 UART. The
active diagnostic attempt used the existing native-USB path; the S3 emitted a
GS40 challenge and reported its driver connected. Windows pyserial accepted a
single 7,323-byte encrypted frame in 1,610 ms, but the target logged
`GS40T/1 RX status=timeout stage=length bytes=0`. The envelope did not reach
TLS parsing, so the historical `tls_identity=0` has not been diagnosed. The
helper source comment now distinguishes host write acceptance from target
receipt. The source RX ring is back at the bounded 4 KiB setting; the
preserved inactive OTA0 image still has its prior 32 KiB setting. OTA1 remains
the selected recovery app and failed closed at Hub-security startup. No flash,
reset, injection, persistent-data change or backend/Home mutation occurred in
this latest diagnosis.

Focused results after the ring change: `PYTHONPATH=code python3 -m unittest
tests.python.test_gs117_tc001_console` PASS, 26/26; `make -C code
gs40-test-only-bootstrap-test` PASS, 85/85; `git diff --check` PASS. C3
`runtime_live=0` and `sensing_live=0`; no fresh EventKey, physical S3
admission, PostgreSQL commit, caregiver API event or Android observation.
TC-001 remains BLOCKED/NOT_RUN and APK event visibility remains
NOT_VERIFIED. Preserve OTA0 candidate and owner-only S3 backups; next actionable
step is to resolve why the native USB Serial/JTAG RX path receives zero bytes
before attempting further TLS diagnostics. Five-hour status returned no budget
value; remaining percentage is unavailable.

### 2026-10-26 — S3 encrypted receive and TLS identity physically resolved

Entry HEAD local/remote `8cbda4b742e9c216bb667fe5fdf710326915ecca`, context PASS.
Exact deployed-image symbolization proved the reported zero-byte RX timeout was
a subsequent boot: the first boot had received/authenticated/decrypted the
7,323-byte envelope and asserted inside `valid_tls_identity()` RSA signing.
The old 3,584-byte main task could not contain the observed >3,824-byte call
stack. The existing GS-68 8,192-byte RSA budget is now reused in the isolated
GS40 TEST_ONLY profile, guarded at build time. A single authorized app-only
OTA0 update/readback installed image `b92e85440430608d3190d0a22cb7d65cc2156210fa6b7878129edb614294a728`
(version `8cbda4b-dirty`, ELF `eed78cac476c2f7dfd14356373510561de268959b1323cf33dc38124e016350c`).
Full before/after readback verified table, NVS, OTA1 recovery, outbox and state
unchanged. Physical TLS validation now PASS (`valid=1`, RSA signature pair proof
with `raw_pair_equal=0`, 3,024 bytes stack headroom). S3 authenticated Hub owner
started for `hub-e072a1d38d34` / `gs177-test-product`, storage_epoch=1. Later
serial observation proved stable runtime and an idle commissioning interface.
Signed-time/authority refresh is still unavailable; CloudSync remains fenced.

The approved exact-fixture commissioning attempt queued at S3 but C3 rejected
`association_backup_failed` before retirement. Source inspection identifies a
first-use ordering defect: it requires the previous-association backup to
exist before invoking the routine that creates it. A scoped correction using
the existing encrypted repository is being tested; C3 firmware remains
unchanged at this checkpoint. No injection, EventKey, backend insert or actual
APK event observation. Detailed public stack diagnosis is in
`GS117_PHYSICAL_ACCESS_20261025T112221Z/usb-receive-diagnosis-20261026.json`;
owner-only full device/readback evidence is in
`~/.local/state/ghar-sajag/gs117-tc001/s3-usb-timeline-20261026/`.


### 2026-10-26 — Actual S3 TLS and C3/S3 authenticated runtime PASS

Supersedes earlier C3-inactive/USB-zero-byte blockers. Exact-image symbolization
identified S3 RSA stack exhaustion, followed by a new boot's receive timeout.
Existing GS68 8192-byte stack budget physically fixes GS40 TLS validation with
3024-byte headroom. Installed S3 OTA0 SHA256
`b92e85440430608d3190d0a22cb7d65cc2156210fa6b7878129edb614294a728` starts the
full product Hub for the correct Home. Scoped first-use encrypted backup ordering
fix installed on C3 OTA0 SHA256
`591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea`.
Both retain verified prior OTA1 recovery images; protected state preservation
is recorded in the existing handoff. No additional flash is needed.

Real exact-fixture PoP/commissioning/rejoin PASS; C3 session107 runtime/sensing
counters131 then22090, HIL_AWAKE_TEST_ONLY. The owner-approved disposable old
association was backed up before scoped retirement; permanent keys/counters kept.
Actual public-key proof is `physical-pair-20261026.json` in the existing evidence
directory. Existing PostgreSQL ownership now registers physical Hub/Node in
`gs177-test-product`, epoch1/gen1; event count stayed1. No fake event insertion.
Bounded existing mTLS listener trial was ready but no real Hub peer connected;
persistent ingress lifecycle remains NOT_CONFIGURED. Signed-time UDP requests
were observed, target acceptance NOT_VERIFIED. Trials stopped at checkpoint.

TC001 NOT_RUN: no INJECT_MOTION issued. Incidental sensor107/1 is not acceptance.
Physical CloudSync/COMMITTED/API fresh-event and actual APK remain NOT_VERIFIED.
Backend authenticated Home/API readiness PASS; phone-side evidence unavailable.
One consolidated protected action remains: normal UAC with process-only
RemoteSigned permission for reviewed hash-verified existing proxy; repair owned
443 route and explicitly add restricted Private-Wi-Fi8445 mTLS route. Windows
Restricted policy rejected normal script execution; no bypass or firewall change.
Then restart existing time/ingress, refresh expired encrypted S3 config, ordinary
C3 rejoin, and execute one new controlled console event plus actual APK evidence.

Focused console28, GS40 checks85, production association/recovery, proxy security19,
both target builds and board E2E10 PASS. Actually executed Node/Hub/contracts
remain FAIL at existing P0 PARTIAL, plus Hub migration; no release gate claimed.
See `docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`
and `physical-activation-20261026.json` for preservation, exact results, next action
and final Git/Jira receipt. Canonical branch unchanged; unrelated assets preserved.


Final current-source GS179 PostgreSQL E2E PASS57/57 with isolated schemas and no
skips; feature-coverage consistency PASS226 features/285 modules/27 cases plus
22 tests. No physical Hub commit or phone event inferred from those results.
Bounded ingress trial stopped; no8445 listener remains. The final scoped commit
and verified remote are recorded in GS117/GS68/GS179 delivery comments.


### 2026-10-26 04:48 UTC — OWNER PAUSED after verified inactive S3 update

Approved normal-UAC process-RemoteSigned proxy operation PASS: current trusted
Private Airtel_Agrim192.168.1.7/24,443->existing8444 and8445->existing8445,
restricted subnet192.168.1.0/24. Same CA/private key retained during existing
network certificate SAN refresh; caregiver/PG/LAN HTTPS health PASS. No global
policy change or persistent elevated task. Physical S3 mTLS authority-refresh
requests returned200 to existing GS179 runtime, but no event COMMITTED.

Found CloudTrust's duplicate raw key-pair comparison still rejecting the actual
PSA format. Reused existing secure bootstrap validator; new production CloudTrust
PKCS1/PKCS8/wrong-key regression PASS. Full-product S3 build PASS. New app
SHA256404dd1ec32ec3f66585f3a8c54e1ee94e8e068b5ff619f9e6369df154a6d51bf
is written/readback verified in inactive OTA1(0x420000), **NOT SELECTED/BOOTED**.
OTA0 b92e8544 remains selected, valid sequence27, preserved recovery. Table,
otadata,NVS,OTA0,outbox,state byte-identical. S3 left in ROM/stub, handle closed.
C3 untouched; do not reflash or repeat successful commissioning.

Temporary time/ingress stopped; existing caregiver service and approved scoped
routes remain. Source parent9bbc6d0 plus delivered scoped fix; exact final commit
in Jira/delivery. Focused security groups14/9/13/5, adapters9/5, provider suites5,
simulation18, bootstrap85 PASS. Affected full campaign for this change deferred
at explicit owner pause; prior P0/migration failures not resolved. TC001 NOT_RUN;
no injection or actual Android observation. Current console fixture/phone receipts
still absent; do not fabricate them.

Resume: existing services, verify current route/metadata, official selector-only
activation of already-written OTA1, encrypted config refresh expected offset
0x420000/version9bbc6d0-dirty/ELF c40486743, real CloudTrust/CloudSync and ordinary
C3 rejoin, then genuine console/phone acceptance. Full preservation and exact
commands/prerequisites in existing GS117 physical-access EXECUTION.md latest pause.

Pause mapping/preflight checks PASS (traceability22 tests,226 features/285 modules/
27 physical cases); exact candidate and source-provenance manifest preserved
owner-only in current session s3-cloudtrust-ready/. No further hardware operation
was performed after the verified readback checkpoint.


Final pause review preserved the original8192-byte private-key limit in the shared
API and added oversize rejection. This supersedes selector-only resume: written
inactive404dd1ec is an earlier candidate, NOT_SELECTED; do not activate it.
Latest bounded full-product candidate BUILT_NOT_WRITTEN, bytes2272880,
SHA256ce33f40aefee2ad9009c5c88a518dd83b5bb02186d204788d510a10dac945e65, ELF1140ce12cc8b0b0240e0836fb4f26fb71c54e4c1f42e98f7edda3a03f2d3523e. Exact owner-only manifest in
current session s3-cloudtrust-bounded-ready/. After resume verify preservation,
write latest bounded candidate to inactive OTA1, verify, then select/bootstrap.
No additional physical action after owner pause. OTA0 recovery remains intact.


### 2026-10-26 resume — ce33 product app physically running; bounded proof cache prepared

ce33f40a candidate now installed/readback and boot-verified on S3 OTA1, recovery
OTA0b92e8544 protected. Ordinary C3 rejoin109/110, real original107/41..52 durable
S3 admissions/ACKs and duplicate-safe retained recovery observed. C3 firmware,
identity and commissioning unchanged. Private Airtel_Agrim192.168.1.7 scoped
443/8445 routes and existing caregiver Home/API ready at stable .local origin.

Repeated private RSA proof validation starves both S3 cores (exact ce33 ELF
watchdog symbolization) and accompanies refresh/HTTP completion failures. Shared
validator now has one-entry RAM/digest cache of immutable crypto proof; live
ownership/epoch/revocation/time checks retained. Bootstrap85/provider/cache
regressions and target build PASS. New imagec26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16
is BUILT_TESTED_NOT_WRITTEN, pending specific owner approval because resume
named onlyce33. ce33 restored/running while waiting; fresh preservation checks
required before new write. Exact plan and artifacts in existing execution record
and owner-only resume-20261026T062943Z/proof-cache-ready/.

No controlled injection; TC001 NOT_RUN; no physical event COMMITTED/API/actual
APK acceptance. Phone current Home/origin/version and genuine install/ingress
receipts remain pending. Existing localhost console is present but guarded;
no receipts fabricated. Affected component campaigns running with native strict
PASS-receipt verification; mandatory failures remain visible. Final validated
Git/Jira receipt follows delivery. No new provisioning platform or product scope.


Current bounded time/physical-ingress trial has been shut down cleanly; existing
caregiver service/PG and approved Windows forwarding remain. No8445 listener is
active now; previous READY receipts are historical. New-image approval and phone
evidence have not arrived. ce33 remains last boot-verified image; c26 remains
BUILT_TESTED_NOT_WRITTEN. Exact new image approval is the next physical gate;
restart existing services with a fresh window and fresh preservation backup
before an approved operation. TC001 remains NOT_RUN, actual APK NOT_VERIFIED.


### Power-outage interruption — summary checkpoint, 2026-10-26

Owner reports power outage and requests execution summary, not further hardware
operations. Post-outage context preflight PASS; actual local/remote remain
9bbc6d0c89f5a8dcad575e3f4f8a4f5aafc8c117. All intended source changes are still
UNCOMMITTED. Candidate c26b6241 BIN/ELF/config/metadata hashes and saved source-file
hashes all match. Existing caregiver user service is active. No board was opened,
reset, flashed or commissioned during this post-outage reconciliation.

Last physical observation before outage: ce33 running OTA1; OTA0 recovery b92e8544
preserved; C3 ordinary rejoin110/runtime/sensing verified. Current post-outage
board startup, network address/routing and transient protected S3 configuration
are NOT_RECHECKED. Do not infer current CloudSync readiness from old receipts.
Bounded ingress/time services were already stopped cleanly before interruption.

Completed software receipts: initial Hub52/55 stages PASS (overall FAIL),
Contract47/48 (FAIL existing P0 PARTIAL), Backend24/26 (FAIL existing P0 and CSS
budget). Initial GS178 browser timeout then focused case PASS and full33/33 PASS.
Registered board-stack-e2e10/10 PASS in the Hub report. PWA final report is absent;
its process was interrupted, so PWA remains INCOMPLETE/FAIL, not PASS. The separate
queued board-e2e target never started. Keep the existing executed board10 receipt.
No validation campaign remains running. Full campaign summary JSON was not written.

Next exact action: obtain/check specific new c26 image-write authorization, then
refresh current fixture/network/protected-state backups; use official app-only
OTA1 procedure preserving OTA0 recovery, readback, selector/boot and same protected
configuration. Do not write ce33 again, do not activate superseded404dd1ec, and do
not touch C3 commissioning/firmware. Verify real CloudSync before any controlled
injection. Finish interrupted PWA/mapping/final review, then commit/push scoped
changes and verify remote. Actual phone evidence remains missing. TC001 NOT_RUN;
no controlled EventKey, physical backend COMMITTED or actual APK PASS exists.


### 2026-10-26 approved c26 deployment — actual physical boot PASS

Owner specifically approved c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16.
Post-outage context PASS, actual local/remote9bbc6d0, preserved source/artifact
hashes match. Live COM4/C3 and COM10/S3 USB identities match; actual prior ce33
boot confirmed. Fresh eight-region owner-only backup includes bootloader, table,
otadata, NVS, both full4MiB apps, outbox and state. Official partition decoder
confirms product layout and valid seq27/28 selectors. OTA0 recovery b92e8544 and
prior ce33 app hashes match. Official esptool confirms S3 revision0.2,16MiB flash,
embedded8MiB PSRAM. Initial uninitialized raw-ROM flash-ID assertion stopped before
any write; using official stub/SPI attachment confirmed capacity without relaxing
the check. Aborted inspection log preserved.

Official otatool selected recovery OTA0 before app-only OTA1 write. Full post-write
readback exactly matches candidate2273344 bytes plus erased tail; bootloader,
table,NVS,OTA0,outbox,state byte-identical; otadata exactly matches intended
recovery-selector snapshot. Official selector then selected OTA1. Actual protected
bootstrap verifies offset0x420000/version9bbc6d0-dirty/ELF c77483102. Encrypted
7323-byte frame accepted; exchange1640ms, generation265ms, hostwrite31ms.
TLS signature proof valid1, raw_pair_equal0 is correctly handled. Full product
owner starts enrolled1/storage_epoch1. No C3 write/reset/commissioning performed.
First two capture windows show no watchdog/backtrace. Sustained capture ongoing;
CloudSync remains fenced without a reachable authority endpoint.

Network changed to trusted Private Airtel_Agrim192.168.1.6/24. Existing server's
network-refresh-config safely refreshed leaf IP SAN/origin using the existing
CA/key and saved rollback files. Existing signed-time and physical GS179 ingress
started with fresh bounded3600s window; actual S3 time requests observed. Existing
caregiver authenticated Home/API and PG readiness PASS. Physical Hub/Node owner
and enrollment1 verified; physical durable backend baseline count0. No historical
HOST_SIM seed is counted. Actual Android diagnostic interface absent; phone
Home/origin/version requested, no response yet.

Approved existing Windows proxy source exactly matched canonical reviewed HEAD.
Normal-UAC process-only RemoteSigned invocation did not complete within its wait;
no status/log/elevated process receipt exists and routes remain old.7. No UAC
bypass, global policy change, firewall broadening or persistent task. Specific
normal-dialog result requested. Complete scoped443/8445 repair before claiming
physical mTLS. Independent firmware work proceeded.

C3 latest initial capture remains session111/runtime0/sensing0 while Hub recovers;
existing max60s backoff and13-channel sweep may take~13min after long outage.
Read-only bounded observations are running; do not reflash/recommission/reset C3
or call this a new firmware failure without evidence. Existing PWA gate resumed
using only native reverified PASS receipts from completed unaffected stages;
failures still rerun/propagate. TC001 NOT_RUN, actual APK NOT_VERIFIED.

Current owner-only evidence: /home/udaybhan/.local/state/ghar-sajag/gs117-tc001/cache-deploy-20261026T082637Z.


Ordinary C3 authenticated rejoin has now recovered without intervention:
actual HIL_STATE session111 runtime_live5338/sensing_live5338, retained0/inflight0,
HIL_AWAKE_TEST_ONLY. NodeRuntime cannot become active before security_link.ready
and authenticated channel completion; no firmware/association/reset change was
used. S3 sustained capture still has no watchdog/backtrace. Public current
cache-deployment receipt updated; time/authority remains fenced by stale route.


### FINAL RESUME HANDOFF — owner-requested quota pause, 2026-10-26

**Current hardware checkpoint:** corrected full-product S3 c26b6241 is installed,
fully readback-verified, selected OTA1 and physically boot/config verified. Do NOT
flash it again. OTA0 recovery b92e8544 preserved. C3 firmware591e9016 unchanged;
ordinary authenticated rejoin session111 recovered without reset/commissioning.
Runtime/sensing grew5338->39236, retained0/inflight0, HIL_AWAKE_TEST_ONLY.
Captured S3 windows through uptime972071ms have no watchdog/backtrace. This proves
local product/crypto recovery only, not successful CloudSync or TC001 acceptance.

**Actual remaining gates:** approved scoped Windows443/8445 routes still target
old192.168.1.7, while verified trusted Private Airtel_Agrim is192.168.1.6/24.
Logged normal-UAC retry returned "operation was canceled by the user"; no elevated
completion receipt, no route/firewall change and no bypass. Need normal Windows
UAC completion for the exact reviewed existing script, not new firmware approval.
Actual installed Android origin/Home/signer evidence and final event visibility
remain missing; no diagnostic interface or owner confirmation arrived. Existing
backend Home gs177-test-product and ownership epoch1/enrollment1 verified; physical
backend baseline0. No controlled INJECT_MOTION has been issued.

**Software delivery:** source parent9bbc6d0 plus preserved shared TLS validator and
bounded successful immutable-proof cache; original8192-byte bounds, PKCS1/8 and
wrong-key rejection, current authority/Home/epoch/revocation/time checks retained.
Bootstrap85/provider/cache checks and full target build PASS. Latest registered
Hub53/55 stages PASS (gate FAIL migration/P0 PARTIAL); contract47/48 (FAIL P0);
backend24/26 (FAIL CSS/P0); PWA17/19 (FAIL CSS/P0). Browser86 PASS, GS177 real
Chromium4 tests/92 catalogue assertions PASS; initial post-outage missing websocket/
Chrome process paths repaired using existing cached dependencies, no new framework.
Board target1/1 stage with10 cases PASS. Mandatory nonzero failures preserved.
Prior GS178 transient browser timeout subsequently passed focused and full33.
Feature mapping22 tests/226features/285modules/27physical cases PASS. After executable
campaigns only documentary mapping/status CSVs changed; actual tested firmware/
unit-source hashes still match candidate manifest. No release-gate-final,
commercial release or optical qualification is claimed.

**Pause safety:** current allowance read through official account/rateLimits/read
is92% used in300min window =8% remaining, reset 2026-10-26T11:29:17+00:00. Owner's below9%
pause condition triggered. Bounded ingress PID3000 stopped cleanly (explicit
GS117_BOUNDED_INGRESS_STOPPED); exact Windows signed-time PID5984 stopped after
command identity check. No8445 fixture listener should be treated as active;
old READY receipts are historical. Caregiver service/PG and loopback console
http://127.0.0.1:18791 remain. All serial observation/write handles are closed.
No more elevation or physical action after pause. Existing network leaf/config
rollback backups and all old/new hardware backups preserved owner-only.

**Exact next action after resume:** run context/status preflight, verify current
trusted Wi-Fi/IP and actual existing route state. Use the existing reviewed scoped
proxy with process RemoteSigned and normal UAC (no global policy, task or broad
firewall change). If same approved script is copied locally, verify hash against
canonical source before elevation. Restart the preserved existing time/ingress
operators with a fresh bounded window, current endpoint certificate/IP and existing
trust. Reuse running S3 config if still valid; otherwise refresh only the existing
encrypted config through approved S3 reset-aware bootstrap, expecting OTA1@0x420000,
version9bbc6d0-dirty/ELFc77483102. No S3 reflash, no C3 reflash/reset/commissioning.
Verify physical mTLS authority and actual event CloudSync; let any old retained
records recover and capture a new baseline. Obtain genuine phone/ingress/image
receipts for existing console fixture guard; never fabricate or weaken them.
Then invoke ONE existing console Run Test, original EventKey exactly once through
physical Hub/PG/API and actual APK, manual evidence USER_CONFIRMED when applicable.

**Artifacts and reports:** owner-only /home/udaybhan/.local/state/ghar-sajag/gs117-tc001/cache-deploy-20261026T082637Z; prior proof-cache-ready manifest/BIN/ELF
in resume-20261026T062943Z. All source hashes/candidate checks match. Full source,
public cache-deployment JSON and existing handoff/work-state/validation mappings
are the intended Git delivery; untracked/ignored unrelated assets are preserved.
Final integrated commit/verified remote is supplied by the delivery/Jira receipt;
parent9bbc6d0 is not a claim that these uncommitted fixes were already pushed.

### GS-117 current physical integration — 2026-10-26

Context preflight PASS; canonical local/remote HEAD `8303a3293af8cfcce1e56063434e8d625f9c93b8`.
The owner-approved, reviewed Windows proxy repair completed through one visible
normal UAC run. Current trusted Wi-Fi is `Airtel_Agrim` Private
`192.168.1.10/24`; only `.10:443→WSL:8444` and `.10:8445→WSL:8445` remain. The
exact stale `.7` mappings were removed. Netsh confirms the two GS-owned inbound
rules are Private-only and limited to local `.10/32`, remote subnet
`192.168.1.0/24`, and their respective TCP ports. Caregiver TLS and PostgreSQL
health pass.

Existing signed time and the bounded TEST_ONLY GS-179 ingress are active. The
physical S3 has returned HTTP 200 authority refreshes; 66 distinct physical C3
EventKeys across sessions 107 and 111 received HTTP 201 `COMMITTED`,
`duplicate=false`. These unrequested/replayed records are not TC-001 evidence.
The listener's autostart remains disabled and permanent service status remains
`NOT_CONFIGURED`; no persistent service was fabricated. The existing caregiver
Home/API reports `gs177-test-product` and `https://desktop-3qqu64b.local` ready,
with monitoring `UNKNOWN` and source freshness `STALE`.

C3 is unchanged; its latest read-only observation is authenticated session 111,
`HIL_AWAKE_TEST_ONLY`, `runtime_live=39236`, `sensing_live=39236`. No board was
reset, reflashed or recommissioned during this continuation. TC-001 remains
`NOT_RUN`: the existing console sees COM4/COM10 but has no owner-only current
fixture/Android installation receipt. No Android device/ADB evidence is
available, so installed APK identity, backend/Home and event display remain
`NOT_VERIFIED`. The owner was asked for USB-debuggable phone access or a genuine
phone-side installation receipt. Next: verify the existing APK and assemble the
console fixture from genuine receipts, then run one controlled injection and
correlate the original EventKey through physical S3, PostgreSQL, caregiver API
and actual APK. Full details are in the dated GS-117 execution evidence above.

### GS-117 resumed Android/network checkpoint — 2026-10-26

Current canonical local and remote HEAD is `6abc9b43f3d1216f66cb2c4d871523ed33445ccd`;
context preflight PASS. No tracked source changes were made; pre-existing
untracked/ignored assets are preserved.

Owner confirmed the C3 is unplugged to connect the phone. After revalidating the
canonical proxy script hash, the existing physical-Hub `Start` path completed
once through normal Windows UAC under process-only `RemoteSigned`. Wi-Fi is
`Airtel_Agrim` Private `192.168.1.10/24`, WSL NAT `172.17.152.10`; current routes
are `.10:443 -> WSL:8444` and `.10:8445 -> WSL:8445`. Windows TCP probes pass for
both ports. Existing bounded signed-time and mTLS ingress processes are active.
No unrelated Windows network state changed.

The authenticated caregiver API helper passes login and retrieves historical
physical EventKey `(c3-146393c5d158, bedroom, session 111, sequence 8)` exactly
once (`durable_count=1`, `caregiver_count=1`, `MOTION`, `Bedroom`) for
`gs177-test-product`. The physical baseline remains 66, all historical and not
TC-001. Freshness remains `STALE` and monitoring `UNKNOWN` because no
`node_health_latest` row exists; prior NodeHealth requests returned 503, and
motion event commits alone do not update source-health freshness.

Windows native enumeration sees S3 COM10 / identity `E0:72:A1:D3:8D:34`, expected
while C3 is unplugged. A subsequent PnP query identified the connected phone as
`motorola edge 60 fusion`, USB VID/PID `22B8:2E81`, service `WinUSB`. No `adb.exe`
is installed in checked SDK locations, so no current APK package/signer/origin/
Home receipt can be produced. The official Android SDK Platform-Tools download
page requires acceptance of its SDK license; that acceptance has not been made.
Existing TC-001 console remains blocked because the owner-only
fixture/approval/identity file is absent and the genuine phone receipt is
unavailable. No injection occurred; TC-001 remains `NOT_RUN`.

Next: obtain owner acceptance of the Android SDK Platform-Tools license (or use
an existing approved `adb.exe`), record the installed APK/signer/origin/Home via
read-only device diagnostics, then ask the owner to reconnect C3 and discover its
live COM port before one controlled console event. Detailed evidence is in
`docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`.

### GS-117 current physical checkpoint — 2026-10-26 15:47 UTC

The owner reports C3, S3 and Android are connected. Fresh Windows serial-helper
enumeration and PnP evidence show only the S3 on COM10
(`E0:72:A1:D3:8D:34`); no C3 COM interface enumerates. ADB sees the authorized
Motorola Edge 60 Fusion and the existing foreground Parivar Saathi app, version
`0.4.0-connected-lite-staging`. Prior read-only APK evidence confirms the
existing Home and motion history; this is not a fresh TC-001 event. No serial
port was opened, avoiding the documented USB-UART reset risk.

The protected physical-session record binds the intended C3/S3 pair to
`gs177-test-product`, epoch 1, but the console-required owner-only `fixture.json`
is absent and current C3 port/image/reset-safety receipts cannot be reconstructed
truthfully from the old session record. Historical ingress evidence contains 66
commits, which remain excluded from TC-001. The existing one-hour bounded
GS-179 ingress was restarted on `172.17.152.10:8445`; listener, PostgreSQL and
signed-time are ready, while current Hub authentication/connection remain NO
and persistent ingress remains NOT_CONFIGURED.

No reset, flash, recommission or motion injection occurred. TC-001 remains
`BLOCKED / NOT_RUN` with no new EventKey. Resume by restoring C3 Windows USB
serial enumeration, then verify the live device pair and current S3 mTLS session;
assemble the owner-only fixture only from those current receipts. Run one
controlled injection after all gates pass and require owner confirmation of the
event in the actual APK before marking PASS. Full checkpoint:
`docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`.

### GS-117 refreshed device enumeration — 2026-10-26 16:02 UTC

Following the owner's updated USB inventory, Windows serial enumeration now
independently confirms COM4 is the expected C3 identity
`14:63:93:C5:D1:58` and COM10 is the expected S3 identity
`E0:72:A1:D3:8D:34`. The unrelated `0000:0002` descriptor-failure device is
not a board. No serial port was opened: canonical validation documents prior
`USB_UART_CHIP_RESET` on C3 serial access and does not qualify the current port
open as reset-safe. A current C3 installed-image receipt and reset-safe UART
receipt are absent, so the owner-only console fixture cannot be truthfully
reconstructed from stable identities alone.

Windows ADB was restarted but reports no attached device; prior app/Home
evidence is retained, though current phone observation needs ADB enumeration.
The existing bounded GS-179 listener is active on `172.17.152.10:8445`; its
PostgreSQL and signed-time checks pass, but the physical S3 has not authenticated
after listener restart and persistent ingress is not configured. Historical 66
commits remain excluded. No event was injected; TC-001 is still
`BLOCKED / NOT_RUN` with no new EventKey.

Next: obtain a verified reset-isolated UART path or owner decision covering the
documented COM4 reset risk; restore ADB enumeration for the phone; then collect
current receipts, verify live C3/S3 session and ingress, execute one controlled
injection, and require owner confirmation in the actual APK. Evidence is in
`docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`.

### GS-117 USB identities refreshed — 2026-10-26 16:03 UTC

The existing Windows serial helper now independently enumerates COM4 as C3
`14:63:93:C5:D1:58` and COM10 as S3 `E0:72:A1:D3:8D:34`; the separate unknown
USB descriptor-failure device is neither board. The active Private Wi-Fi and
existing 443/8445 proxy mappings remain correct and were not changed. No serial
port was opened because canonical evidence records a prior `USB_UART_CHIP_RESET`
on COM4 observation and the existing open path is not reset-safe. The protected
physical-session record is present, but current C3 image and reset-safe receipts
needed by the console fixture are not; no fixture was synthesized.

The one-hour existing GS-179 ingress remains actively listening, with PostgreSQL
and signed-time ready, but current Hub authentication/connection remain NO and
persistent ingress remains NOT_CONFIGURED. ADB currently lists no device after
the official server was restarted; prior app/Home evidence remains historical,
not a new event observation. The 66 previous commits remain excluded. TC-001 is
still `BLOCKED / NOT_RUN`, with no new EventKey. The next gate is a verified
reset-isolated serial observation/injection path (or an explicit owner decision
covering COM4's documented reset risk), current Hub mTLS authentication, and
phone-side confirmation in the existing APK. Details are in the dated GS-117
execution evidence above.

### GS-117 USB-port return and Android refresh — 2026-10-26 16:26 UTC

After the owner returned the devices to their original USB ports, fresh
Windows-native enumeration confirms COM4 is C3 `14:63:93:C5:D1:58` and COM10 is
S3 `E0:72:A1:D3:8D:34`; both PnP entries are OK. The Motorola is again
authorized in ADB, with the existing caregiver package
`in.gharsajag.caregiver.discoverytest` version `0.4.0-connected-lite-staging`
foreground. Its live screen displays `CONNECTED`, Home `gs177-test-product`,
and monitoring `UNKNOWN` / source `STALE`; this is not TC-001 event evidence.
The saved endpoint is `https://192.168.1.10/`. TLS remains enforced by the APK;
the server certificate at the IP has an IP SAN and the `.local` DNS SAN, but
the app has no stored SPKI pin. The current console accepts only `.local` and
exact-origin equality, so it does not accept this phone endpoint as presently
configured.

Historical C3 evidence at 08:51 UTC showed active `ota_0`,
`HIL_AWAKE_TEST_ONLY`, session 111 and live runtime/sensing counters. It does
not prove the post-disconnect boot. Port `List` was read-only; no serial port,
reset, flash, commissioning or motion command was used. A USB cable removal can
explain temporary enumeration loss and, if USB is the sole supply, a normal
power cycle. It is distinct from the separately documented
`USB_UART_CHIP_RESET` on serial open. Windows pySerial opens the COM handle
before applying DTR/RTS, so the present path remains unqualified as reset-safe.

The existing ingress listener, PostgreSQL and signed-time checks are ready,
but current S3 authentication is `NO`, persistent ingress is not configured,
and the trace has no entries after 13:27 UTC. CloudSync may remain silent when
there are no pending journal events or current NodeHealth publications; the
current evidence cannot distinguish this idle case from an S3 connectivity
failure. No fresh EventKey exists; TC-001 remains `BLOCKED / NOT_RUN` pending a
single explicitly authorized reset-aware observation. Exact supporting
evidence and its recovery boundaries are in the linked GS-117 execution record.

### GS-117 one-use physical observation — 2026-10-26 16:39 UTC

After the USB devices returned to stable ports, the existing Windows helper
identified COM4 as the physical C3 and COM10 as the physical S3; Windows PnP
reports both OK. ADB now sees the authorized Motorola Edge 60 Fusion, and the
existing caregiver APK package/version is installed and foreground. This is
not a current event-display confirmation.

The owner authorized one reset-risk-accepted, read-only serial observation.
C3 `GET_STATE` returned OTA0 / `HIL_AWAKE_TEST_ONLY`, session 118, with
`runtime_live=0` and `sensing_live=0`. S3 booted the product composition from
`0x420000`, but the observed `FIXTURE_STATUS` text was sent while its GS40
receiver was waiting for encrypted configuration. The GS40 startup path parses
that envelope before HubRuntime commands; the four-byte `FIXT` prefix exceeds
its accepted length. The subsequent `ESP_ERR_INVALID_SIZE` and abort are
consistent with that parser receiving the status text; S3 then reported
`RTC_SW_CPU_RST`. This is an observer sequencing defect, not proof of a USB
power-cycle reset cause. The
existing serial helper now requires the S3 to advertise `FIXTURE_STATUS`
readiness before sending it and skips the command during a configuration
challenge. Regression `GS117-S3-STATUS-GATE-001` and the registered console
suite pass: 32 tests. No motion, reconfiguration, commissioning or firmware
operation was performed.

Current S3 HubRuntime, mounted product storage, authenticated C3 rejoin, mTLS
CloudSync and new-event API/APK visibility remain unverified. The one-use
observation approval is consumed; the normal owner fixture is still absent.
TC-001 remains `BLOCKED / NOT_RUN`, with no new EventKey. See the linked
GS-117 execution record and sanitized serial observation JSON for evidence.

The focused tests passed and implementation/evidence were pushed on
`feature/r1-commercial-baseline` as
`b04d700ed91a59e9426ec76d7cb0471be012fd3e`; the remote matched at verification.
Only the eight scoped implementation and evidence files were committed.
Existing untracked and ignored firmware, Android, hardware evidence and
owner-local credentials were preserved. The latest GS-117 Jira comment records
the final HEAD including the handoff closeout.

### GS-117 S3 runtime recovery prepared — 2026-10-26

The existing protected GS40 bootstrap and c26 OTA1 boot evidence were reviewed.
All 16 saved pre/post-deployment backup regions verify. Existing fixture
keys/certificate match their backup; the current RSA-3072 ClientAuth pair and
exact ACTIVE Hub generation 1 registry entry verify. No credential issuance,
Wi-Fi secret retrieval or board serial open occurred during preparation.

The existing Private Airtel_Agrim address is dynamically confirmed as
192.168.1.10/24, with correct existing 443/8445 forwarding. Existing bounded
signed-time and physical ingress services are running again for 3600 seconds;
ingress reports listener/PostgreSQL/time ready but no actual Hub authentication.
The initial ingress dependency-path error was fixed by reusing the GS179
dependency environment. No service replacement or network-policy change.

The actual existing Android APK now visibly shows CONNECTED and Home
gs177-test-product; monitoring remains UNKNOWN/source STALE. The saved
CA-verified IP origin is unchanged. No fresh motion display is claimed.

A single-attempt protected recovery invocation is prepared in the owner-local
`s3-runtime-recovery-20261026T170152Z` state directory. It requires explicit
approval for serial-open/close risks on both boards, one S3 application reset,
one encrypted GS40 configuration delivery, and bounded read-only status
sampling. The existing serial helper's optional default-OFF GET_STATE polling
permits increasing C3 counters to be checked without reopening S3. The S3
FIXTURE_STATUS query is disabled throughout recovery. No motion/flash/enrollment
change is included. Exact bounds, script hash, risks and stop/recovery conditions
are in the existing GS117 EXECUTION.md. Physical recovery is APPROVAL_PENDING;
TC-001 remains NOT_RUN and the normal console fixture/origin gates remain.

### GS-117 approved S3 configuration recovery — 2026-10-26 17:11 UTC

The owner approved the exact prepared attempt. It executed once and exited 0:
expected c26 OTA1 boot metadata verified, one encrypted GS40 frame accepted,
TLS identity valid=1, no FIXTURE_STATUS sent. Product owner started with one
enrolled Node and storage epoch 1 after guarded persistent outbox recovery.
No captured abort/watchdog/backtrace; no flash, OTA selection, C3 reset command,
commissioning or motion injection. Existing protected state/backups preserved.

Physical S3 mTLS/CloudSync now has fresh evidence: repeated authority HTTP 200
and two retained physical session112 events COMMITTED. Both have exactly one
PostgreSQL record and one caregiver projection; duplicate retry is suppressed.
The existing 66 records remain, total 68. These are recovery events, excluded
from controlled TC-001 acceptance. The runtime status fields for authentication
and connection are hardcoded NO and must not override actual mTLS receipts.

S3 recorded authenticated ordinary C3 rejoin/session118 and Node liveness
online at uptime69 seconds. The six zero-counter GET_STATE samples ended
before rejoin, so increasing runtime/sensing counters remain NOT_VERIFIED.
No extra serial open was performed after the approved capture.

NodeHealth 503/STALE is traced to the unique Home/logical-node constraint:
historical HOST_SIM bedroom health/enrollment and the physical bedroom
enrollment are both ACTIVE in gs177-test-product. Read-only diagnosis only;
both enrollments, credentials and all history were preserved. Resolve through
the existing fixture lifecycle before claiming monitoring freshness. Console
fixture/reset-risk and verified IP-versus-DNS origin gates also remain.

Actual Android readiness is CONNECTED/Home gs177-test-product, with monitoring
UNKNOWN/source STALE; no new controlled event is displayed or confirmed.
TC-001 remains NOT_RUN. Existing bounded ingress/time services remain running.
See the existing execution handoff and recovery_20261026T1711Z.json for exact
physical evidence, source checkpoint and next actions.

### GS-117 working pipeline preservation — 2026-10-26

Owner personally observed new Bedroom Motion in the actual existing APK after
physical recovery. Record USER_CONFIRMED application visibility separately:
no exact phone observation time/EventKey was supplied. Most recent correlated
backend candidates are retained physical session112/1 and112/2, each exactly
once in PostgreSQL/caregiver API. This is a working recovery pipeline with
owner phone acceptance, not a controlled TC-001 injection; TC-001 remains NOT_RUN.

The existing execution handoff now contains the permanent startup/recovery
runbook (top quick link), exact existing script references, commands, guarded
S3 recovery and automatic/manual/missing restart behavior. Private checkpoint
working-pipeline-checkpoint-20261026T173535Z contains 1008 verified files,
including existing trust/config/issuer backup, runtime dependencies, actual APK,
firmware/recovery assets and a consistent standard PostgreSQL archive. Archive
listing/full decode PASS; live restore NOT_RUN. Private assets remain outside
Git in owner-only storage; no saved Wi-Fi secret exported. Saved firmware
metadata was inspected offline with existing esptool; no board port opened.

Console IP/.local mismatch corrected using the existing verified endpoint
helper: phone IP must equal current measured Wi-Fi IP, both DNS/IP TLS identities
must validate through the existing CA, and both must serve the exact installed
leaf. Actual laptop proof PASS; wrong CA/SAN/leaf/address and unsafe URL tests
reject. No phone configuration, trust policy or other fixture guard changed.
Endpoint 8/console 32 focused tests PASS; existing serial timing guard retained.

NodeHealth collision remains preserved and read-only: both synthetic/physical
bedroom enrollments ACTIVE, stale synthetic latest row conflicts. Existing
authenticated REVOKE_NODE lifecycle is reusable but needs explicit authority;
current code also needs an authority-checked latest-projection handover. No
enrollment, credential or history mutation was performed.

Restart limits remain explicit: existing backend unit enabled/on-failure but
WSL Linger=no; physical ingress/time are bounded one-hour manual processes;
S3 TEST_ONLY startup is RAM-only with one-hour configuration expiry. Persistent
services, auto-launch, protected credential changes, hardware and injection were
not performed. Keep the working Hub untouched; use actual mTLS receipts rather
than hardcoded NO status fields. Remaining controlled TC-001 prerequisites:
truthful fixture/reset-risk control, later live counters, one approved fresh
injection and exact-key APK confirmation. See preservation_20261026.json.

### GS-117 five-run console and automated APK verification — 2026-10-26

The existing TC-001 console/Windows helper now supports the requested five-run
campaign: one lock, five sequential fresh C3 HIL events with separate
timestamped reports, and stop-on-first-non-PASS. It opens only C3 COM for the
authorized injection, records possible COM4-open reboot risk (never claims
reset-safe DTR/RTS), and never opens S3 COM10. The helper validates active
HIL-awake mode, positive runtime/sensing counters and empty pending queues before
each injection; it requires the matching authenticated class-0 Node ACK, exact
physical CloudSync provenance, one PostgreSQL row, caregiver projection and
exact-key APK observation. Duplicate row counts are retained on failures.

Per controlled event, ADB foregrounds the existing Parivar Saathi APK, verifies
its receipt-bound backend origin/Home/CONNECTED status in Settings, opens
Reports, triggers the APK's own visibility-change refresh, expands Latest
recorded events/Event details and compares the exact EventKey. The APK already
exposes the key, so no APK feature change was needed. Actual screenshot and
accessibility-tree evidence are stored privately with 0600 permissions. The
signer digest is sourced from the owner-only install receipt and matched to the
installed package/version; it was not independently extracted from the installed
APK in this software pass.

Software checks: TC-001 console/ADB automation 43/43 PASS; GS-179 verified
endpoint 8/8 PASS; Python compilation PASS; feature coverage PASS (226 feature
rows, 285 source modules, 27 physical cases, 22 registry tests). These checks
do not establish actual phone automation or hardware results. No ADB command,
serial-port open, injection, firmware operation or database mutation occurred.
Physical TC-001 is still NOT_RUN. It requires a current exact owner-only fixture
receipt and a separate one-use owner approval explicitly accepting exactly five
COM4 C3 injections and possible serial-open reboot, while excluding COM10 UART,
flash/reset command/recommission, credentials/ownership/enrollment/database
changes. The campaign approval is not present in this execution and was not
fabricated. Existing S3/CloudSync recovery events and owner APK observation
remain historical, not TC-001. NodeHealth UNKNOWN/STALE is preserved and is not
an event-delivery gate. Full evidence is in the existing GS117 EXECUTION.md.

### 2026-10-27 GS-178 software acceptance and GS-117 physical preparation

Starting canonical commit `f6321597578bda69aa43056cbee70c863d5e625a`; context
preflight PASS. Current-source `make -C code gs178-software-e2e` passed 33/33.
Five isolated Bedroom Motion software E2Es passed with unique synthetic Node
sessions 42001–42005, exactly one durable row for each original EventKey and 17
Playwright assertions per run. Physical status remains NOT_RUN; browser results
are not Android observations. The existing GS-117 console/ADB suite passed
43/43, including exact-key APK observer success/rejection paths. Test-only
session seeding changed no product runtime.

ADB currently sees the authorized Motorola Edge 60 Fusion and the existing
Parivar Saathi TEST_ONLY package, version 0.4.0. The installed APK bytes match
the protected preservation SHA; preserved metadata records its IP origin and
`gs177-test-product` Home, but this check did not freshly verify app
authentication/Home. The current accessibility dump exposed no Home,
Connected or Reports label. It could not derive a signer certificate fingerprint.
PostgreSQL, caregiver HTTPS and current endpoint TLS health pass. Physical mTLS
ingress autostart is disabled, port 8445 is not listening, and the saved ingress
process is stopped. Last physical S3 COMMITTED and authority-refresh evidence
is from 2026-10-26 and is historical.

Owner-only TC-001 `fixture.json`, current phone signer/install receipt and
`five-run-campaign-approval.json` are absent. Neither COM4 nor COM10 was opened;
no motion injection or physical/configuration mutation occurred. Thus software
simulation is PASS and physical TC-001 remains BLOCKED / NOT_RUN. Do not request
the five-run injection authorization until current ingress, signer and exact
fixture evidence are ready. Detailed results, EventKeys and hashes are in the
[GS-178 software evidence](../exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md#current-source-five-run-bedroom-motion-simulation--2026-10-27)
and the [GS-117 execution handoff](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md#2026-10-27--current-source-gs-178-and-non-disruptive-tc-001-readiness).

### GS-117 / GS-179 non-disruptive readiness closeout — 2026-10-27

Owning Jira is GS-117 (In Progress); GS-179 remains In Progress. This resumed
closeout preserved and completed the interrupted additions to the existing
[GS-117 execution handoff](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md)
and [GS-179 ingress audit](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md).
At evidence-capture entry, canonical branch was
`feature/r1-commercial-baseline`, local and remote HEAD both
`cac55b92a00fe6fe807787ce9faa55ba42df5305`, and context preflight passed. The
interrupted two-document diff was retained; all unrelated untracked/ignored
files remain untouched. This closeout adds only those two evidence documents
and this work-state handoff.

At 04:30Z the existing host health check passed PostgreSQL TLS/durability,
caregiver HTTPS, local backend and endpoint TLS identity. Windows/WSL private
network identity and existing scoped forwarding were rechecked; TCP 8445
forwarding reached the listener. Its no-client-certificate TLS probe did not
authenticate. Bounded ingress status showed listener/backend/trusted-time ready
but `real_hub_authenticated=NO`, `hub_connected=NO`, no current event receipt,
persistent ingress NOT_CONFIGURED and autostart disabled. UDP 4468 host-generated
RSA-3072/SHA-256 challenge proof passed nonce/generation and validity checks at
04:22Z only; this is not S3 traffic and its validity window had elapsed by the
later check.

The actual installed Android observation remains the timestamped 02:59Z
receipt: existing TEST_ONLY app, Home `gs177-test-product`, backend CONNECTED,
Reports → Latest recorded events, and historical exact-key observer match for
`{physical_device_id: c3-146393c5d158, logical_node_id: bedroom,
origin_session_id: 112, event_sequence: 2}`. Home monitoring remains
UNKNOWN/source STALE. No fresh TC-001 key was observed. Installed APK bytes
matched the preserved SHA-256. Its embedded v2 signer-certificate fingerprint
matched preserved trust digests; `apksigner verify` was unavailable, so
signature verification is incomplete. The loopback console endpoint returned
HTTP 200 from a process predating current console source; it is stale and not
used for readiness. Current guarded code regression passed 43/43.

Fixture status is **BLOCKED**: the owner-only `fixture.json` is absent, current
C3/S3 running-image evidence and image hashes are unavailable without board
access, no fresh authenticated S3 mTLS/CloudSync receipt establishes the
current Hub/Home/epoch/enrollment binding, and historical image metadata is not
substituted. The separate `five-run-campaign-approval.json` is absent. TC-001
remains **0/5 BLOCKED / NOT_RUN**. No COM4/COM10 access, reset, injection,
firmware operation, credential or lifecycle change, or protected database
mutation occurred. The bounded service session expires around 05:19Z.

Validation for this documentation/readiness closeout:
`python3 code/tests/python/test_gs117_tc001_console.py` — **43/43 PASS**, exit
0. GS-178 software acceptance was not rerun; no release-wide gate was run.
Sanitized private readiness evidence (mode 0600) is at
`~/.local/state/ghar-sajag/gs117-tc001/fixture-session-20261027T041925Z/readiness-observation-20261027T0430Z.json`.

**Next physical prerequisite:** if fresh S3 readiness is still required, obtain
new scoped owner approval for the existing one-attempt encrypted-configuration
recovery through COM10, explicitly accepting its USB-UART reset risk and
possible loss of RAM-only Wi-Fi/GS40 configuration. Do not create the fixture
until the current installed-image receipts, identity/epoch/enrollment, current
authenticated ingress and app evidence validate. The later five-injection
campaign remains a separate approval and is not authorized by this closeout.
After this handoff, GS-178 comment 11729 names the next software deliverable:
deduplicate current scenario/test coverage into its proposed-case gap table and
prioritize Wave S1. This is a next-task pointer only; GS-130/GS-178
implementation did not begin here. GS-173 scope decisions gate conditional
cases. Delivery commit and remote verification are recorded in the owning Jira
closeout comment.

### GS-117 / GS-179 pause checkpoint — 2026-10-27 05:12Z

The current audit-first TC-001 readiness recheck is documented in the existing
[GS-117 execution handoff](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md)
and [GS-179 ingress audit](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md).
The local and origin branch were both at
`77b1927dc4043308078f0b3d2afa496aeead4555` before this checkpoint. The latest
Jira history was reconciled before changes; GS-117 and GS-179 remain open.
Only these three canonical evidence/work-state documents are intended for the
checkpoint commit. Untracked and ignored user assets are preserved and
unstaged.

Existing C3 EventKey/retention, S3 authentication/durable-before-ACK,
CloudSync, PostgreSQL deduplication/caregiver projection and Android exact-key
observer were audited and reused; no approved product defect or missing code
capability was established. The host health, Windows forwarding/TCP 8445 and
bounded listener were ready. Host signed-time proof passed its nonce,
generation and signature checks inside its validity window, then expired; it
does not establish physical S3 authentication. No fresh authenticated S3
receipt, current image attestation or fixture is available. The APK evidence is
historical observer readiness only; APK bytes and embedded signer digest
matched preserved values, but formal APK signature verification is incomplete.

No board port was opened and no reset, flash, config recovery, injection,
credential/lifecycle/database mutation or APK rebuild occurred. TC-001 remains
0/5 BLOCKED/NOT_RUN; target injection, optical PIR and full Android acceptance
are not established. The separate five-run approval remains absent. The
current-source console is running and reports readiness BLOCKED. The existing
GS-117 regression source is unchanged; no test suite was rerun for this
documentation-only checkpoint. `git diff --check` is the applicable local
validation.

**Pause boundary / next exact action:** obtain one new, scoped owner approval
for the existing one-attempt protected S3 configuration recovery via COM10
(reset and RAM-only Wi-Fi/GS40 loss risk) and COM4 (serial-open reboot risk),
then execute only that procedure and re-evaluate fresh image, identity,
authenticated-ingress, Android and fixture gates. Do not create the fixture or
five-run approval until those gates pass. The five sequential injections and
real AM312 optical qualification require their own applicable approval/action.
No approval is implied by this checkpoint. Once recovery is separately
authorized, resume GS-117 In Progress and continue with the existing controller.
Jira state at pause: GS-117 **OnHold** (comment 11737); GS-179 **In Progress**
(comment 11738). The Git checkpoint is `ea481a753ef39b30c5d4571c98c6f186cf32bafb`.

### GS-117 one-attempt S3 recovery and readiness checkpoint — 2026-10-27 05:57Z

Resumed from canonical `feature/r1-commercial-baseline` at local/origin
`ae44b6584ad9eb69b61ca87a2c6affa7ffd5029e`; context preflight PASS. The old
Codex process was parked with no repository file handles, no competing writer
was found, and all pre-existing untracked/ignored assets remain preserved.
Latest GS-117/179 Jira comments and the GS-116/130/121/148/173 acceptance
history were reconciled before the recovery closeout. The existing C3
EventKey/retention, authenticated S3/durable event pipeline, CloudSync,
PostgreSQL/caregiver projection and Android observer were reused. No code
defect was established and no product code or test framework was changed.

Owner approval authorized one invocation of the existing protected S3 recovery
procedure only; its one-attempt marker is consumed. S3 reset/configuration
recovery succeeded once, and the approved C3 action was `GET_STATE` only. No
injection, flash, erase, storage/database mutation, credential or ownership
change occurred. Fresh physical S3 mTLS authority refreshes continued through
05:57:02Z. Sixteen distinct physical C3 EventKeys were accepted by CloudSync
and the backend as COMMITTED; the read-only backend/API evidence shows one
durable record and one caregiver projection per EventKey, with correct Home,
Hub, epoch, enrollment and Bedroom. Eighteen repeated event submissions were
idempotent `duplicate=true` receipts. Monitoring remains UNKNOWN/STALE from the
known GS-148 ownership/NodeHealth projection conflict. A later observed C3
sequence 122 lacks an exact backend record and is not counted as delivered.

Current non-invasive checks: PostgreSQL TLS/durability, caregiver HTTPS/local
backend, Windows Private `Airtel_Agrim` address `192.168.1.10`, TCP 8445
forwarding, and UDP 4468 binding passed. The host RSA-3072 signed-time proof
passed nonce/generation/signature validation at 05:38:38Z and expired at
05:40:38Z; the service remained bound and the physical Hub continued
authority-refresh HTTP 200. The one-hour ingress/time processes remain
bounded; persistent ingress/autostart remains disabled. Current-source console
regression `python3 code/tests/python/test_gs117_tc001_console.py` passed
43/43. Current loopback readiness reports backend/Home and USB descriptor
readiness, but fixture/campaign/Android observation are BLOCKED or
NOT_VERIFIED.

Android read-only `AndroidReady` passed for authorized device
`ZA2237MRHN`, installed package/version and package path. Its signer value is
receipt-derived, not formal signature verification. Exact-key Android
observation did not pass: the app did not foreground and device state showed
the lockscreen. No unlock bypass or APK rebuild occurred. `apksigner verify`
remains unperformed. Owner-only `fixture.json` and campaign approval remain
absent because full current C3/S3 running-image/partition receipts and fresh
APK UI observation are missing; historical image metadata was not substituted.

**Disposition:** GS-117 is **In Progress**, not Done. Physical five-run TC-001
is **0/5 BLOCKED/NOT_RUN**, `TARGET_TEST_INPUT_PASS=NOT_RUN`, optical PIR
`REAL_SENSOR_PASS=NOT_RUN`, actual Android exact-key observation
NOT_VERIFIED, and full acceptance BLOCKED. GS-179 remains **In Progress**:
fresh bounded real S3 authentication is now observed, but persistent ingress
and broader staging/phone acceptance remain open. Do not execute another
physical operation under the consumed recovery approval. Next, obtain fresh
full-current-image receipts through an independently approved safe method and
unlock the authorized phone so Codex can capture current UI evidence. Only when
all exact fixture gates pass request the separate one-use five-run campaign
approval; do not begin it under recovery approval.

Documentation closeout covers this work-state entry and the existing GS-117
and GS-179 evidence documents. Base HEAD and origin before delivery were both
`ae44b6584ad9eb69b61ca87a2c6affa7ffd5029e`; validated evidence commit and
final remote equality are recorded in the follow-up Jira closeout comments.

### 2026-10-27 11:11 UTC — GS-117 resumed product verification checkpoint

Canonical branch and source remain `feature/r1-commercial-baseline` at
`c7eceedd44a37cf1ed049b4b7fba008d89ddcc3b` before this handoff. Context
preflight passes. No product source changed. The phone is now ADB-visible and
the installed package/path readiness check passes, but the existing exact-key
observer for C3 session 118 sequence 16 stops because the APK displays “Sign in
required / No current authorized session was restored.” Do not call this an
Android event observation; no credentials were sent. The exact EventKey is
present once in the durable backend and caregiver API. Sequence 122 remains
unmatched and has three C3 sends without a captured application ACK; the saved
S3 boot trace shows trusted-time/authority refresh failure and CloudSync fenced.
First failing delivery boundary is not proven beyond the missing C3 ACK and
absence of an S3/backend receipt.

The host's local PostgreSQL, caregiver HTTPS and backend are ready, but bounded
TCP 8445 / UDP 4468 services have expired. Windows Wi-Fi is `192.168.1.6`; the
phone and last verified encrypted Hub configuration target `192.168.1.10`, whose
current neighbor is not the laptop. The old portproxy remains on `.10`; no
forwarding/network change was made and no credentials were sent to the current
`.10` host. The saved S3
installed-image receipt is 26.5 hours old; no current C3 installed-image
receipt exists. The owner-only fixture and five-run approval remain absent.
Current S3 authentication, exact-key Android observation and fixture are
BLOCKED/NOT_VERIFIED; TC-001 remains 0/5 NOT_RUN and optical PIR remains
NOT_RUN. Existing console/ADB regression remains 43/43 PASS at its previously
verified source commit; no tests were rerun because no code changed.

The minimum product-readiness sequence is: restore the owner-approved `.10`
endpoint (or approve one coordinated new endpoint), restore only the existing
bounded services, confirm fresh physical S3 authentication, obtain newly scoped
current C3/S3 image and partition receipts using targeted read-only app-slot
readback (COM4/COM10 opening can reset devices; S3 RAM-only configuration can
be lost), establish an authenticated app session over verified TLS, then repeat
the existing observer for exact sequence 16. The prior one-attempt S3 recovery
approval is consumed. Do not create the fixture or run injections until all
current gates pass; request the five-run authorization separately at that
point. See the dated updates in the GS-117 and GS-179 evidence documents.

### 2026-10-27 12:16 UTC — laptop route restored; TC-001 stopped at new hardware approval boundary

**Checkpoint:** canonical repository `/home/udaybhan/projects/Ghar_sajag_r1`,
branch `feature/r1-commercial-baseline`, baseline HEAD and origin both
`40f18f0e5a122773faf20c1e8f0365f9c582e657` before this documentation update;
context preflight PASS. Tracked source was clean at entry. Existing untracked
user evidence/build assets were preserved. A long-lived Codex CLI process was
present but idle in epoll/futex wait; no concurrent tracked-file writer was
observed.

The owner confirmed a router DHCP reservation of `192.168.1.6` to laptop Wi-Fi
MAC `C0:18:85:B9:4F:C3`; Windows DHCP is enabled and profile `Airtel_Agrim` is
Private. WSL is `172.17.152.10`. Existing scoped Windows routes now forward
`.6:443` to WSL `:8444` and `.6:8445` to WSL `:8445`; old `.10` routes are
absent. The current TLS leaf validates the existing DNS name and `.6`; current
PostgreSQL TLS/durability, caregiver HTTPS and backend readiness pass. The
stable-address mechanism is the router's DHCP reservation; no extra network
infrastructure is needed.

The actual Motorola APK (`ZA2237MRHN`, package
`in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging`, versionCode 3) reports backend CONNECTED, Home
`gs177-test-product`, origin `https://192.168.1.6/`, and Reports access. Existing
ADB observer helpers located the exact historical physical key C3
`c3-146393c5d158`, bedroom, session 118, sequence 16 in Event Details with
Motion recorded, Bedroom and the matching timestamp. Evidence is preserved at
`~/.local/state/ghar-sajag/gs117-tc001/android-session118-seq16-exact-20261027T120515Z/`.
Backend exact-key correlation remains one durable record plus one caregiver
projection. This is not a fresh TC-001 input. The signer digest is
receipt-derived; formal APK signature verification remains incomplete.

Existing bounded ingress/time services are active; backend and TCP 8445 route
checks pass. The host-generated RSA-3072 signed-time challenge verified its
nonce/generation/signature at 12:11:28Z for 120 seconds, then expired. At
12:16:32Z the actual ingress runtime still reported no authenticated Hub and
no Hub connection; monitoring freshness is UNKNOWN and persistent ingress is
NOT_CONFIGURED. Thus fresh physical S3 authentication is NOT_VERIFIED. C3
sequence 122 remains unmatched and is not counted. No credentials went to the
old `.10` address.

The current-source guarded loopback console GET `/api/status` returned HTTP
200. PostgreSQL/HTTPS/backend/Home and descriptor-only COM4/COM10 checks pass;
no serial ports were opened. The bounded listener is active but its status is
not persistent S3 authentication. Fixture/campaign readiness is BLOCKED and
the console's APK fixture gate remains NOT_VERIFIED, separate from the
successful actual APK historical exact-key observation.

The owner-only fixture and five-run approval remain absent. S3 current-image
receipt is older than 24 hours and C3 image/partition attestation is incomplete.
The existing least-data option is targeted read-only active-app-slot and
partition-table readback; the broader script that reads NVS/outbox/state is not
needed. Opening COM4/COM10 can reset the device; COM10 can lose RAM-only
Wi-Fi/GS40 configuration. The previously approved one-shot recovery was
consumed. **Next action:** obtain one new, bounded owner authorization for those
targeted read-only image receipts and one existing-procedure encrypted S3
endpoint recovery to `.6`; stop on identity/provenance/configuration mismatch
or any failure. After safe verification, re-evaluate the fixture, then request
the independent five-injection campaign approval. No physical ports were
opened and no reset, config update, injection, flash/erase, credential,
ownership/enrollment or protected data operation occurred in this checkpoint.

GS-117 is **OnHold** pending the new scoped physical approval, with TC-001
**0/5 NOT_RUN**, target test input **NOT_RUN**, and real optical PIR
**NOT_RUN**. Resume In Progress when authorized execution begins. GS-179 remains
**In Progress**.
No product source changed. The existing console/ADB regression result of
43/43 PASS remains historical evidence at its verified source; no test was
rerun for this documentation/network/Android verification checkpoint. Latest
Jira comments before this closeout were GS-117 `11741` and GS-179 `11742`;
dated evidence comments will record the delivery commit. Delivery SHA and
remote comparison are available in the next Git/Jira closeout entry.

### 2026-10-27 13:21 UTC — GS-117 stopped at C3 readback capacity guard

At canonical HEAD 1fe7e3777dbe542c05b3fd134fe5f22f90ce3459 (remote matched),
the owner authorized targeted C3/S3 current app/table readback followed by one
existing S3 encrypted configuration recovery to .6. Context preflight passed;
GS-117 moved from OnHold to In Progress. The C3 COM4 connection verified the
approved USB serial, ESP32-C3/MAC and read-only security state. Preserved
C3/S3 artifacts and metadata passed offline hash/provenance checks. The
installed esptool 5.4.0 returned unknown flash capacity (detect_flash_size()
== None); the guard stopped before any flash region read (flash_reads=[]). No
current C3 image/table/capacity receipt exists. This is an unknown-capacity/tool
identification result, not an observed firmware image mismatch.

No COM10 access, S3 recovery invocation, configuration operation, injection,
firmware write/erase, protected data read/mutation, or database/lifecycle change
occurred. COM4 was opened once under the accepted reset-risk scope; app-run
state after serial close is unverified and was not probed again. Private
evidence: ~/.local/state/ghar-sajag/gs117-tc001/current-image-readback-20261027T131908Z/.
The offline parser/artifact self-test passed; the actual C3 readback failed
closed before partition-table, selector or app reads. No product code changed
and no product regression suite was rerun.

The owner's explicit stop-on-any-failed-guard instruction ends this hardware
session. GS-117 is OnHold pending fresh scoped owner authorization for one
corrected read-only C3 capture that records/validates raw flash ID and capacity;
only after it passes may targeted S3 readback and one existing recovery
invocation proceed under that new authorization. TC-001 remains 0/5 NOT_RUN,
fixture BLOCKED/absent, five-run approval absent, and optical PIR NOT_RUN.
Preserve the prior actual APK observation for session 118/sequence 16 as
historical observer evidence only. Detailed results and exact next action are
in the [GS-117 execution handoff](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md#2026-10-27-1321-utc--approved-current-image-readback-stopped-at-c3-capacity-guard).


### 2026-10-27 14:11 UTC — revised readiness session stopped at invalid C3 JEDEC ID

The owner approved one revised GS-117 readiness session: validate the C3 raw
flash ID and actual capacity first; only on success continue with targeted C3
image/partition evidence, targeted S3 readback, then one existing S3 encrypted
configuration recovery to `192.168.1.6`. Context preflight passed at
`5c6e180c517a99f829dc3fef3b7895705d71609c`; local and origin HEAD matched and
tracked files were clean. Existing untracked user assets remain preserved.

The private run is
`~/.local/state/ghar-sajag/gs117-tc001/capacity-first-readback-20261027T141042Z/`.
The preserved artifact/hash self-test and Windows Python 3.12 / esptool 5.4.0
helper preflight passed without opening a port. One COM4 connection attempt
verified the expected USB serial `14:63:93:C5:D1:58`, ESP32-C3 MAC
`14:63:93:C5:D1:58`, and read-only security flags (Secure Boot off, encryption
count zero, Secure Download off). The JEDEC read returned `0xffffff`
(manufacturer `0xff`, device `0xffff`); esptool reported capacity `Unknown`
and both official capacity decoders returned null. The raw ID/capacity guard
failed closed. `flash_reads=[]`: no C3 partition table, OTA selector or app
region was read.

The explicit stop condition was applied. COM10 was not opened, S3 readback was
not run, and the existing S3 recovery procedure was not invoked. No flash write,
erase, NVS/outbox read, configuration change, injection or campaign action
occurred. COM4 post-close runtime state was not probed. The S3 remains without a
fresh authenticated receipt; the owner-only fixture remains blocked/absent;
TC-001 remains 0/5 NOT_RUN and real optical PIR remains NOT_RUN.

Next action: investigate the all-ones C3 JEDEC response using existing offline
tool/provenance evidence and prepare a minimal diagnosis. Any further COM4
access requires a new scoped owner approval. Do not proceed to S3 readback or
recovery until C3 capacity is genuinely identified and validated.

### 2026-10-28 — GS-117/178 configurable Morning Routine source slice

At start, canonical `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, local and origin HEAD were both
`7fcb2cd35d3f0b17bbd68da794e4955e259bd125`; context preflight passed. Existing
tracked edits from the interrupted session and unrelated untracked/private
evidence remain preserved. No competing product writer or active test process
was present at closeout. Latest owner corrections were read from GS-117
comment 11773, GS-178 comment 11775, GS-130 comment 11774, GS-116 comment
11769 and GS-121 comment 11770.

Implemented and host-validated the generic required/optional Morning Routine
rule shape in the existing shared rule/config path, including strict and
unordered ordering, legacy compatibility, bounded input validation, checkpoint
v4 progress preservation and TEST_ONLY AR2 bootstrap decoding. Added a
fail-closed guard so an empty strict policy cannot invoke the legacy Bedroom
sequence. Updated the existing GS-130 feature row and `PHY-GS117` case; no new
test framework or physical case was created.

The real-device utility is not complete. Backend desired configuration is
versioned, but production S3 has no authenticated fetch plus durable apply
consumer; the frontend serializer is not connected to a visible Settings
editor; and GS-117's existing local console still runs only its fixed
five-event Bedroom Motion campaign. The known fixture has only a Bedroom C3.
Do not use it to impersonate another location. No hardware or Android operation
was performed for this rule slice; no fresh sequence event or APK completion
was observed. Existing historical HOST_SIM-to-APK evidence is unchanged.

Validation: `make -C code cpp-test` 1,529 checks PASS; `make -C code app-test`
36/36 PASS; `make -C code gs178-software-e2e` 39/39 PASS (HOST_SIM);
`make -C code feature-coverage-test` 226 features / 285 modules / 27 physical
cases plus 22/22 mapping tests PASS. The full `validation-hub` gate failed on
the known migration case and P0 `product_status=PARTIAL`; the full
`validation-contract` gate failed on P0 `product_status=PARTIAL`. Both gates'
registered GS-178 39/39 passed; contract GS-117 console 43/43 passed. The
paired ESP-IDF build was interrupted and its attempted resume hit a malformed
generated archive before any S3 build; no target build result is claimed.
Detailed commands/results and acceptance limits are in the
[GS-178 evidence note](../exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md#2026-10-28--configurable-morning-routine-rule-slice-and-real-target-audit).

Validated implementation and evidence were committed as
`5cbbc732019ad8c32b9ee06766d92090b45eb3ab`, pushed normally, and verified equal
to origin at closeout. Tracked files were clean at that checkpoint; unrelated
untracked evidence/build assets remain preserved. GS-117 stays OnHold at
physical TC-001 0/5 and real PIR NOT_RUN; GS-178/179 remain In Progress. No
five-run approval is present or implied.

Next exact product action: audit and implement the missing authenticated,
versioned S3 desired-config fetch/persistence/application path using existing
Hub identity/storage contracts, then wire the current authorized Settings
publish path and existing GS-117 controller to genuine enrolled Nodes. Keep
multi-room scenarios BLOCKED until each configured required room has its own
current enrolled physical input. Resume target builds from fresh isolated
outputs; request hardware authorization only for an operation actually
required after software readiness is established.
## GS-178 P0 software readiness and targeted regressions — 2026-10-19

### 2026-10-28 — GS-178 HOST_SIM event observed in the installed Android APK

At starting canonical commit `b34736da3d44885d0bad95e3b8a6784ef4e36d3e`,
`feature/r1-commercial-baseline` matched `origin`; context preflight passed.
Tracked files were clean before this evidence update. Existing unrelated
untracked assets/evidence were preserved. No production or test source changed.

Reused the existing GS-178 `ProductStack`/C++ Node host, GS-179 TEST_ONLY mTLS
listener, GS-148 durable PostgreSQL API and the installed caregiver APK. One
synthetic Node-boundary Bedroom Motion input received Node ACK `DURABLE` and
original EventKey
`p15:test-c3-bedroomn7:bedrooms2026102801q1` (Hub `test-hub-product`, Home
`gs177-test-product`, session 2026102801, sequence 1). The first backend
response was HTTP 201 COMMITTED and deliberately lost after commit. An exact
CloudSync replay returned HTTP 200, the existing API duplicate status. The
backend held exactly one durable row and one business event. The authenticated
external caregiver API at `https://192.168.1.6/` returned the same exact key
once, with `MOTION`, bedroom, and occurrence time `2026-10-28T03:16:55Z`.

The authorized Motorola phone's actual installed
`in.gharsajag.caregiver.discoverytest` APK (0.4.0-connected-lite-staging,
versionCode 3) was connected to the backend/Home. Existing ADB automation
foregrounded the app, refreshed Reports, opened Event Details, and matched the
exact key. The screen showed `Motion recorded`, bedroom, phone-local time
`28/10/2026, 8:46:55 am`, backend receive time `8:46:59 am`, and Home
`gs177-test-product`; the app showed 139 durable records. Installed APK bytes
SHA-256 `0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`
match the preserved copy. Preserved install signer digest matches the
embedded-certificate digest, but formal `apksigner verify` was unavailable.
Private evidence and screenshot/accessibility hashes are recorded in
[`GS-178 software vertical evidence`](../exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md#2026-10-28--persistent-postgresql-software-path-to-the-installed-apk)
and `~/.local/state/ghar-sajag/gs178-android-check-20261028/`.

This is one `HOST_SIM_PASS` software event with actual Android observation. It
does not prove physical C3/S3 input or fresh physical S3 authentication. The
most recent GS-178 Jira comment 11767 requests separate real-board USB-trigger
acceptance; no hardware authorization was used here. The actual `.6` API
passed independently; a browser run against that service was NOT_RUN. The
existing 39/39 GS-178 suite remains prior HOST_SIM/browser evidence and was not
rerun because this checkpoint changed no source. No full release gate or
firmware build was run.

GS-117 remains OnHold at 0/5 physical TC-001; current physical fixture and
five-run approval remain blocked/absent, and real AM312 optical qualification
remains NOT_RUN. GS-179 remains In Progress: its health check still reports
physical Hub authentication NO, monitoring freshness UNKNOWN and persistent
ingress NOT_CONFIGURED. GS-178 remains In Progress; its separate real-target
USB→C3→S3 acceptance and remaining scenario/use-case coverage are outstanding.

### 2026-10-28 — GS-117 production config boundary and paired target build

Resumed at canonical `238bf5dfc84b973a511b9874b982060ded591bbd`; branch and
origin matched and context preflight passed. No competing writer or hardware
operation was active. No source behavior changed in this checkpoint.

The targeted GS-109/GS-148/GS-179 audit establishes a security decision
boundary before implementing the desired/applied-config product path. GS-D032
does not approve a production Hub credential issuer, proof-of-possession or
freshness contract, trusted mTLS middleware/deployment, or caregiver auth
adapter. `HumanAuthenticationBoundary` and `VerifiedHubContext` are unconnected
seams. The local Hub ingress is TEST_ONLY. The development `JsonApi` config
route reads/writes `InMemoryStore`; despite the existing schema table,
PostgreSQL has no wired versioned config repository/route. The frontend routine
serializer is not connected to a caregiver Settings page. S3's production
HTTP channel is POST-only and has no desired-config fetch/apply consumer.

I did not select an mTLS issuer, trust an actor header, introduce credentials,
or bypass current authorization. The requested Settings → PostgreSQL →
authenticated S3 → persisted applied policy path therefore remains BLOCKED at
the existing GS-109/GS-148 security contract. The GS-117 console has no Morning
Routine button; its fixed Bedroom campaign cannot run a multi-room scenario.
Only a Bedroom physical Node is established, so any required other room remains
BLOCKED rather than mapped to that Node. No COM, device, Android, credential,
enrollment or protected database access occurred.

Current-source paired ESP-IDF 6.0.3 production builds completed from fresh
ignored output `code/build/validation_targets/gs116-rclvmmof/` at source HEAD
`238bf5dfc84b973a511b9874b982060ded591bbd` (fingerprint
`07d98b97cf40f24e2c44f2bc45b42f90f41ad0766e290957cf25a5243786fa23`). C3:
944,272/1,966,080 bytes, SHA-256
`cd8f0a2d11c6ee4f97f3d34ed0e6ffefe7535989a18685d0a28b1a2be4b365a6`; S3:
2,200,480/4,194,304 bytes, SHA-256
`91113e128a3bf1298de5adef0dd4d98285109eebec6fcd4655394329d0fa4c02`.
Both compiled and passed slot/package checks. Qualification is
`TARGET_COMPILED_ONLY`; physical status NOT_RUN and hardware actions NONE. This
replaces the earlier incomplete-build checkpoint for this source, without
claiming installed-image or runtime acceptance. Existing focused tests from
`5cbbc73` remain unchanged; no source suites were rerun.

Next required owner decision: GS-109/GS-148 must provide or approve the
production authenticated caregiver/Hub identity and trusted-context contract
that the existing config path can use. Once that boundary is resolved, persist
desired/applied versions through the existing database schema, wire Hub fetch
and durable apply, then connect the authorized Settings UI and GS-117 console.
Do not start the real multi-room scenario until each required location has a
genuinely enrolled C3 and the ordinary GS-117 fixture/campaign gates pass.

### 2026-10-28 — development endpoint recovery checkpoint

Recovery code commit: `c6efa7b4f347be408449fee56c7f8fb67b5d0842` on
`feature/r1-commercial-baseline`; origin matched after push. Local backend
recovery was verified after a controlled existing systemd service
restart, but Windows LAN and WSL-restart recovery are not fully qualified.

The confirmed LAN root cause is an absent GS-179 scheduled recovery task and
owned Windows portproxy rows without a listening socket. Current Windows Wi-Fi
is trusted Private `.6/24`; WSL is `.10`; existing HTTPS CA/SAN identity is
valid. Code now makes overall readiness fail when LAN HTTPS fails, uses the
existing watcher with bounded minute-level WSL-address reconciliation, keeps
healthy backend starts idempotent, and routes the GS-117 launcher through the
existing readiness/report path. The local persistent service, PostgreSQL and
loopback GS-117 utility are up; the Windows loopback page and readiness API
return HTTP 200. Durable event and commit counts remain 139 each.

The watcher registration requires an elevated Windows token. The task remains
ABSENT because this run has no administrator token; no UAC bypass or network
mutation was performed. Thus LAN HTTPS `.6:443` still times out and automatic
recovery after WSL/IP change is not yet proven. The exact next operation is one
elevated invocation of the existing Windows PowerShell script, followed by
verification of the task and a controlled recovery cycle:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\code\tools\local\gs179-windows-lan-proxy.ps1' -Action RegisterWatch -LinuxScriptPath '/home/udaybhan/projects/Ghar_sajag_r1/code/tools/local/gs179-laptop-server.sh'
```

A WSL shutdown was not run while this active execution was using the distro.

The existing Android observer plus Windows ADB still reports
`TC001_APPROVED_ANDROID_DEVICE_NOT_AUTHORIZED_OR_CONNECTED` after one bounded
ADB server start; PnP has no Android/ADB device. The current app endpoint/login
cannot be freshly checked. The utility's read-only status endpoint returns 200
and safely reports LAN readiness FAIL, fixture BLOCKED, and Hub ingress
NOT_LISTENING. Expected C3 COM4/S3 COM10 USB descriptors were enumerated only;
no serial port was opened. TCP 8445, UDP 4468, current S3 authentication and
physical image/fixture readiness remain BLOCKED. TC-001 and Morning Routine
physical acceptance remain NOT_RUN.

Focused results: GS-179 PostgreSQL/security 23/23; isolated live PostgreSQL
runtime composition 6/6; GS-117 controller 60/60; connected-lite 23/23;
shell/Python syntax, context preflight, TLS CA/SAN verification and diff check
PASS. See the existing
[`GS-179 ingress/recovery evidence`](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md#2026-10-28--recovery-watcher-and-end-to-end-readiness-correction)
for commands, root cause and limitations. Jira GS-179 remains In Progress;
GS-117 remains OnHold for physical qualification.

### 2026-10-29 — GS-179 scheduled recovery bug fixed

Source `7604f5562fb506b520141626cf77de543f1cfa17` fixes the validation-order
bug in the already registered elevated Windows watcher. It now recomputes the
WSL RFC1918 validation after Watch discovers the current address and before
Start validation; existing admin, trusted-network and owned-rule guards are
unchanged. The focused regression is in the existing GS-179 security test
module (24/24 PASS).

The existing task was run without re-registering: manual run and a natural
scheduled reconciliation after a controlled backend service restart both
returned `0x0`. Windows reports one listener on `.6:443`; CA/SAN-verified
HTTPS through `192.168.1.6` and the complete PostgreSQL/local/LAN health check
PASS. Restarted backend retained `events=139` and `durable_event_commits=139`.
No WSL shutdown was attempted.

Android remains NOT_VERIFIED: the current ADB observer sees no authorized
device, and the preserved install receipt has stale origin `.10`; no credentials
were sent to that address. The current app/login cannot be checked until the
phone enumerates in ADB with its approved current endpoint. Physical S3 ingress
TCP 8445 and signed time UDP 4468 remain absent, so physical E2E, current S3
authentication and Morning Routine remain NOT_RUN. GS-179 remains In Progress;
GS-117 remains OnHold. See the dated GS-179 evidence section for exact live
checks and limitations.

### 2026-10-29 03:04 UTC — live Android connectivity and bounded ingress checkpoint

At source HEAD `3ec7831450055bf4258e37b2759cfaaeadeaa6c9` (remote matched before
this evidence-only update), the owner-authorized Motorola phone was detected
with the exact supplied Windows ADB binary. The installed
`in.gharsajag.caregiver.discoverytest` APK, version `0.4.0-connected-lite-staging`
versionCode 3, passed the existing observer. Its current Settings page showed
Home `gs177-test-product`, origin `https://192.168.1.6/`, and `Backend API ·
CONNECTED`. Backend logs show HTTP 200 for caregiver login, `/me`, and Reports
at 02:57:03 UTC and successful authenticated refreshes afterward. Reports
showed historical HOST_SIM EventKey
`p15:test-c3-bedroomn7:bedrooms2026102801q1`, Bedroom, `Motion recorded`, and
the original 28 October timestamp. The screenshot visibly labels it
`TEST_ONLY` / `physical origin not verified`. Installed APK bytes match the
preserved artifact hash `0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`;
formal APK signature verification remains NOT_PERFORMED. Evidence is private
under `~/.local/state/ghar-sajag/gs117-tc001/android-live-check-20261029T025526Z/`.
This is a fresh APK-to-backend read, not a new physical event. The old `.10`
receipt was not modified and no request was sent to `.10`.

The bounded GS68 signed-time service listens on current Windows Wi-Fi
`192.168.1.6:4468`. A new host-generated proof matched challenge nonce and
generation, verified under the preserved RSA-3072 key, and was current. That
is not physical Hub evidence. The GS-179 TEST_ONLY ingress runtime listens on
WSL `172.17.152.10:8445` with PostgreSQL and trusted-time ready, but its trace
has zero requests and `real_hub_authenticated=NO`. The `.6:8445 -> .10:8445`
portproxy row exists; Windows shows no active `.6:8445` listener. The read-only
firewall audit requires Administrator. The existing elevated Wi-Fi recovery
task handles caregiver 443 only, not physical ingress 8445. One elevated
existing-helper action is required:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\code\tools\local\gs179-windows-lan-proxy.ps1' -Action Start -EndpointKind PhysicalHubIngress -WslAddress 172.17.152.10
```

The helper must retain its existing trusted Private Wi-Fi, port-ownership,
firewall-scope and admin guards. Do not use an alternate task or widen the
firewall. Until this succeeds and an actual authenticated Hub receipt appears,
GS-179 current S3 authentication remains NOT_VERIFIED.

GS-117 `/` and `/api/status` returned HTTP 200. The controller still reports
the owner-only current fixture absent/BLOCKED and no approved physical Run;
USB discovery remained descriptor-only. No COM4/COM10 access, device reset,
flash, event injection, database mutation or credential change occurred.
Focused regression `python3 code/tests/python/test_gs117_tc001_console.py`:
60/60 PASS. TC-001 remains 0/5 NOT_RUN; Morning Routine Hub decision and APK
outcome remain NOT_RUN; real AM312 PIR remains NOT_RUN. GS-117 remains OnHold
and GS-179 remains In Progress. Detailed command results and private evidence
are in the existing
[`GS-117 execution handoff`](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md#2026-10-29--authorized-android-live-check-and-bounded-service-recovery)
and [`GS-179 ingress audit`](../exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md#2026-10-29--current-android-connectivity-and-test_only-ingress-state).

### 2026-10-29 05:16 UTC — C3 auth gate and S3 volatile-config diagnosis

Offline source/log analysis only; no hardware or COM operation occurred. C3
`owner_task()` waits for `NodeSecurityLink::ready()` before constructing and
running normal NodeRuntime work. Rejoin retries continue at the security gate;
an explicit fault exits with a fail-closed log. The HIL `GET_STATE` handler is
separate, and runtime/sensing counters are incremented only after authenticated
session establishment. Thus session 120's zero counters are consistent with
an unestablished C3↔S3 association and do not establish a C3 sensing defect.
Because the preserved GET_STATE JSON filters out full boot/security logs, it
cannot distinguish a still-waiting owner task from a prior logged owner-task
exit. Historical 26 October S3 logs do show an authenticated C3 rejoin and
online liveness in session 118, but that is not current-session proof.

The GS40 TEST_ONLY config receiver is entered during S3 app startup, emits a
boot-scoped challenge, accepts the existing challenge-bound encrypted
configuration for 60 seconds, and keeps accepted Wi-Fi/Hub/TLS material in
RAM. The 29 October COM10 readback reset the S3; this config was not reapplied
and S3 app startup was not observed afterward. A prior S3 bootstrap trace
shows the Hub owner and enrolled peer working but signed-time/authority
refresh failures kept rules/CloudSync fenced. C3↔S3 ESP-NOW authentication and
S3↔backend mTLS/signed-time are separate gates. Latest saved host ingress state
(05:03 UTC) has host services ready but no authenticated real Hub, connection,
or fresh monitoring evidence.

Next: request one new, readiness-only authorization for the existing protected
GS40 Bootstrap on the exact S3/COM10 and an exact-identity-checked C3/COM4
GET_STATE/log observation in the same bounded session. Its scope must allow
the existing S3 rearm/reset and acknowledge COM4 serial-open reset risk; it
must use only preserved config/trust material for Home `gs177-test-product`
and endpoint `192.168.1.6`, stop at any image/identity/security/config/time
mismatch, and exclude all motion injection. The previous session ended at its
first failed readiness guard. No new code or tests were needed for this
offline finding. TC-001 remains 0/5 NOT_RUN and GS-117 remains OnHold. See the
[`offline authentication-gate investigation`](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md#2026-10-29-0516-utc--offline-c3-authentication-gate-diagnosis) for evidence and exact bounds.


### 2026-10-29 — standing GS117 readiness consent implemented, activation pending

Reused the GS117 console/launcher, exact fixture and serial helper, existing
protected GS40 Bootstrap, and current image receipts. Added an owner-only standing
consent reader and bounded session ledger; no new service, credentials, firmware,
or product rule. The launcher supports `--hil-policy-status` / `--hil-readiness`.
The reviewed draft is inactive: ten readiness sessions maximum, expires
2026-11-05 00:00 UTC, one preserved-config Bootstrap per session, zero retries,
exact COM4/COM10 devices/Home/endpoint/image pair; expected serial resets allowed.
No motion injection or campaign is included. Missing/expired/revoked/inconsistent
consent denies access. Procedure/receipt hashes, USB identity, backend/forwarding,
rejoin, advancing liveness and independent fresh physical time/mTLS/fixture checks
remain required. Failures/crashes latch further standing execution pending review.

Console/ADB regression 72/72 PASS; framework 55/55 PASS; Python/shell syntax PASS.
Inactive launcher status/readiness each return BLOCKED/exit 2 before hardware.
The prepared private procedure copy and tracked patch preserve the historical
original. No active owner manifest, hardware access, bootstrap, reset or input was
performed. C3/S3 runtime authentication remains NOT_VERIFIED; TC-001 0/5 NOT_RUN.
GS-117 remains OnHold pending one consolidated approval activating the exact draft
and the first single readiness session. Motion campaign approval remains separate.
Details, consent-versus-technical-guard audit, activation/revocation and limits:
`docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`.


Broader affected tooling gate: `make -C code validation-tooling` exited 2 /
SOFTWARE FAIL. Its Python stage ran 666 tests: 2 failures and 1 documented
historical ESP32 layout skip. Failures in unchanged sources:
`test_phase3a_performance.test_static_payload_and_collection_budgets`
(static total 118556 > 114688 bytes; CSS 29576 > 18432), and
`test_s3_fixture_commissioning.test_s3_option_is_opt_in_and_legacy_broad_hil_stays_rejected`
(the unchanged target-build script contains the GS_HIL_COMMISSIONING string
that the test forbids). These are retained as unresolved gate failures, not
suppressed or repaired in this consent-only change. The registered GS117 stage
passed 72/72, GS117 profile 4/4, GS179 endpoint 8/8 and framework 55/55; the
final focused console run also passed 72/72 after source completion. Tooling
report: `code/evidence/validation_framework/tooling-1793251941535021580/report.json`.
No product/firmware sources changed, so target builds and physical gates were
not invoked. Full tooling acceptance is not claimed.

Feature-coverage registry regression: 22/22 PASS. The prepared procedure also
requires observed Wi-Fi address exactly `192.168.1.6` before loading existing
credentials; a changed address fails closed even if another SAN is present.


### 2026-10-29 05:58 UTC — standing policy activated; first session stopped at target guard

The owner explicitly activated the exact reviewed policy from source commit
`9020204b430dcc037135a933ff0e24da70b24d94`, including the first readiness
session. The owner-only active manifest records
`owner-chat-2026-10-29-standing-dev-readiness-9020204`; identities, Home `.6`
endpoint, image/procedure pins, ten-session limit, one Bootstrap/session, zero
retries and expiration `2026-11-05T00:00:00+00:00` are unchanged. No campaign
consent was created. Context preflight and all policy/receipt hashes passed.

Before serial access, PostgreSQL durability and verified local/LAN HTTPS passed;
COM4 and COM10 descriptors matched exactly. Expired bounded host services were
restored once using their existing provenance-verified scripts and preserved
trust/configuration. Prior fixed-path logs were archived before restarting.
WSL `172.17.152.10:8445`, the existing Windows `.6:8445` route/listener and
UDP `.6:4468` passed; no elevation, certificate, credential, network rule or
persistent startup change was required.

The standard existing launcher `--hil-readiness` was executed once with a
150-second outer timeout. Session 1 ran from 05:53:22.897Z to 05:54:34.358Z
(about 71.5 seconds), with exactly one protected Bootstrap invocation and no
retry. It exited 2 and latched on `TC001_TARGET_READINESS_GUARD_FAILED`:
`BOOTSTRAP_FAILED_STAGE=encrypted_config_exchange TYPE=ValueError
CODE=BOOTSTRAP_CHILD_TC001_TARGET_READINESS_GUARD_FAILED`. No motion input,
campaign, readback, JEDEC, flash/erase or ownership/enrollment operation occurred.

Evidence limitation / exact next software fix: the approved private protected
parent parses the child's failure JSON and raises at lines 83–84, before writing
`bootstrap-observation.json` at lines 85–86. Consequently the child target
failure marker and C3/S3 transcript were discarded, although the serial helper
attached its captured observation. There is no trustworthy way to reconstruct
that lost target line from the surviving summary. Current C3↔S3 rejoin and
runtime/sensing counter progression therefore remain NOT_VERIFIED, rather
than proven failures or sensing defects. Do not reopen serial ports to recover
logs. Preserve the running Hub and the failure latch. The minimal next fix is
to preserve child output/observation before checking its return code, review the
pinned-procedure implications, then determine the appropriate next observation;
do not silently change the active pins or retry this session.

Independent positive evidence did arrive after reconfiguration: the real mTLS
listener received physical Hub `/v1/test/authority/refresh` HTTP 200 at
05:54:26.618Z and later refreshes. This route requires CERT_REQUIRED and current
certificate/Hub/Home/epoch authority verification. CloudSync then returned
201 COMMITTED for retained original C3 session-118 sequences 70–73. A separate
PostgreSQL READ ONLY query confirmed each has exactly one durable row, Hub
`hub-e072a1d38d34`, ownership epoch 1. These are retained backlog replay, not
new controlled inputs or TC-001 acceptance. Signed-time service request counts
advanced, but the target's own time-acceptance transcript was lost; do not
substitute a request counter for that proof. No fresh NodeHealth receipt was
present in the preserved trace snapshot. `runtime.status()` still emits
hardcoded `real_hub_authenticated=NO` / `hub_connected=NO`; those placeholders
must not override the authenticated request/COMMITTED evidence. They are not
live counters (see `gs179_hub_ingress_runtime.py` status implementation).

Private evidence: `~/.local/state/ghar-sajag/gs117-tc001/standing-activation-20261029T055250Z/`
and `standing-authorization/bootstrap-5099032e07c23efc9f89430e/` under the same
private base. The ledger records one of ten sessions used and a failure latch;
policy-status correctly returns BLOCKED/exit 2 afterward. No second hardware
attempt was made. The policy remains activated, subject to that latch and its
original expiry. No additional owner permission is requested for offline
investigation. TC-001 remains 0/5 NOT_RUN; fixture/physical readiness remain
BLOCKED; GS-117 remains OnHold. No APK observation or Morning Routine outcome
is claimed. No source code changed and no regressions were rerun: the prior
72/72 focused result remains historical source evidence, while this session's
actual validations are policy/preflight, host connectivity, one failed hardware
readiness attempt and read-only durable replay verification.


### 2026-10-29 12:08 UTC — GS-179 Reports window corrected; Android verification still pending

The capped caregiver Reports timeline previously ordered on raw zero
`occurred_at`, which excluded session-118 sequence 100 before the 100-row
limit. Commit `36922a05aa1326a0e798f116f1866ab03172dced` orders by effective
event time (`occurred_at`, falling back to `received_at`) before LIMIT, adds a
matching bounded functional index, aligns the in-memory fallback and registers
focused regressions.

After one controlled restart of the existing GS-179 service, PostgreSQL
TLS/durability, caregiver HTTPS and LAN forwarding passed; migration 015 was
applied. An authenticated TEST_ONLY Reports API read and independent
PostgreSQL READ ONLY query both returned all 32 unique C3 session-118 keys,
sequences 70–101, once each (24 MOTION, 8 MOTION_SUMMARY). Preserved physical
S3 ingress traces correlate all 32 HTTP 201 commits and 27 HTTP 200 duplicate
retries to the same original keys. No rows or event timestamps were mutated.

All raw C3 `occurred_at` and database `hub_received_at` values are zero.
The API's displayed `occurred_at` is therefore the backend receipt-time
fallback, not original motion-generation time. This is retained physical
backlog evidence with unknown original stimulus; it is neither PIR qualification
nor controlled TC-001 acceptance.

Android observer now reads `content-desc` and waits a bounded additional
interval for a temporarily empty WebView accessibility tree. The saved failed
observer run has no hierarchy dump; a separate diagnostic supports, but does
not prove, that transient cause. The authorized ADB path currently lists no
device, so the owner's 32-entry Reports view is not independently reverified
and no new exact-key screenshot is claimed.

Validation: GS-179 PostgreSQL E2E 70/70; isolated PostgreSQL timeline
regression 1/1; effective-time projection 8/8; GS-117 observer/controller
79/79; validation framework 55/55; traceability 226 features / 287 modules /
27 physical cases and 22/22 tests. Full release gates were not run. See
`docs/exec-plans/evidence/GS179_CONTINUOUS_INGRESS_AUDIT_20261020.md` and
`docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`.

GS-179 remains In Progress; GS-117 remains OnHold and TC-001 0/5 NOT_RUN.
Next: reconnect the authorized Android device for exact-key Reports/Event
Details observation. The physical TC-001 run still requires current qualified
target/fixture evidence, current S3 authentication/time readiness, the
owner-only fixture, and separate campaign authorization.

### 2026-10-29 12:55 UTC — Android exact-key backlog observation; TC-001 gates remain closed

The authorized phone is connected to ADB as `ZA2237MRHN`; the installed
`in.gharsajag.caregiver.discoverytest` APK remains version
`0.4.0-connected-lite-staging` (versionCode 3), with no reinstall. In the real
APK, Reports → Event Details shows exact C3 session-118 sequence 100 and 101
for Bedroom/Home `gs177-test-product`; Settings reported backend origin
`https://192.168.1.6/` and `CONNECTED`. Private screenshots and accessibility
XML with hashes are preserved under
`~/.local/state/ghar-sajag/gs117-tc001/android-session118-seq100-reverify-20261029T123356Z-cf60bf/`.
The bounded automated exact-key scan still fails to find seq100 because it
does not scroll the long Reports list; existing ADB UI helpers were used to
scroll and independently confirm the actual record. The app labels these
TEST_ONLY entries “physical origin not verified.” This confirms display of
historical retained backlog only; displayed times are backend receipt-time
fallbacks, not C3 generation times. It is not a fresh injection or optical
PIR pass. The full 32-key authenticated API/PostgreSQL result remains the
previously verified 12:08 UTC evidence; it was not repeated in this session.

The owner-only fixture and five-run campaign approval are both absent. The
current exact-fixture guard needs current per-board image receipts, including
S3 16 MiB flash/8 MiB PSRAM, a current APK install receipt bound to Home/origin
and trusted signer digest, and a structured fresh ingress receipt with
authenticated Hub identity, trusted-time readiness and certificate digests.
Reuse same-day C3/S3 app/partition readbacks and the prior JEDEC PASS; do not
repeat them. Current raw ingress proves physical CloudSync receipts but lacks
the complete structured trust/time fields. `--hil-policy-status` is BLOCKED
on a standing-policy serial-helper fingerprint mismatch; its one-session
failure ledger remains consumed and latched. The local GS-117 `/api/status`
timed out after five seconds, and bounded 8445/4468 listeners were not active
at observation. No COM, hardware, service restart or data mutation occurred.

GS-117 remains OnHold, TC-001 0/5 NOT_RUN; GS-179 remains In Progress. The
next action is to resolve the existing policy fingerprint/latch through its
reviewed successor procedure, obtain only the genuinely missing current
receipts and live readiness evidence, validate the owner-only fixture, then
request separate campaign authorization. See the dated GS-117/GS-179 evidence
sections for hashes, constraints and stage details.


### 2026-10-29 — GS-117 Reports observer and readiness preparation checkpoint

The existing GS-117 ADB observer now performs a bounded exact-key scan through the Reports WebView and handles the actual preserved layout where the section header collapses to zero height. It retains Home/package/origin/authentication checks, visible exact-key matching, explicit absent/end-of-list failures, and a hard 55-swipe limit. The saved real session-118 sequence-100 accessibility tree passes the new viewport replay; this is historical evidence, not a new Android event observation. Focused suite: 86/86 PASS; helper/test compilation and `git diff --check` PASS.

ADB read-only install evidence at 13:52Z confirms the authorized phone, package/version and current installed APK bytes exactly match the trusted SHA-256. Embedded signer certificate digest corroborates both owner trust digests; formal `apksigner verify` was not run. No live Settings/Home/origin/Reports check was made because the phone was foregrounding YouTube UploadActivity. The current receipt leaves Home/origin unobserved; prior same-day Settings and exact session-118 observations remain separate historical evidence.

Fixture `fixture.json` and five-run approval remain absent. Reuse the Oct 29 C3/S3 partition/active-app/OTA readbacks and prior C3 XMC 4 MiB result. The current S3 readback did not query capacity; Oct 26 capacity evidence is stale. Existing physical S3 mTLS/CloudSync replay demonstrates recovery after the earlier transient, but its trace lacks certificate digests and an explicit target trusted-time-ready field. The preserved 07:03Z session-120 transcript shows C3 runtime/sensing counters advancing 204790→206807, but the S3 time/authority guard failed before an authenticated rejoin line or application ACK was observed. Do not repeat liveness-only checks; target trusted-time acceptance, authenticated rejoin, current structured ingress certificate evidence, and an EventKey-correlated application ACK remain unverified.

An **inactive** one-session readiness proposal and private v6 protected-bootstrap candidate are prepared, with pinned hashes in the existing GS-117 execution evidence. The candidate adds a fail-closed startup-memory profile check; it was syntax-checked only. The existing readiness flow does not create a structured ingress receipt or owner fixture, and its final fixture guard may still block after the one observation. No successor policy activation, COM access, reset, bootstrap, injection or campaign occurred. The consumed policy/latches and all old evidence remain unchanged. GS-117 stays OnHold, TC-001 0/5 NOT_RUN. Next owner action: explicitly approve at most this one readiness observation, with the possibility of a post-observation fixture block; only after genuine current receipts validate the fixture should a separate campaign approval be requested.


### 2026-10-29 — GS-117 target observation retained independently of fixture

Existing standing readiness now durably saves TARGET_OBSERVATION_PASS inside its session, then checks the unchanged owner fixture outside it. FIXTURE_PENDING no longer failure-latches a successful target observation. Real target/authentication/identity/capacity/security failures still latch. Transient time/authority warnings can be collected in the revised bounded procedure but require current target-bound authenticated recovery evidence; HTTP 200 alone cannot clear them. There is no automatic positive target-time/structured-ingress receipt generator, so missing evidence remains pending and an unresolved actual refresh failure still latches. Old approvals/ledgers/private parents are preserved; r2 one-session proposal and v7 parent are inactive. Exact pins and caveats are in the GS-117 execution handoff.

Focused 89/89 and framework 13/13 PASS. Actual Android Settings at 16:28:48Z shows gs177-test-product, .6 HTTPS, CONNECTED; current APK bytes match trusted artifact. Formal apksigner verification unavailable. Private observation path android-readiness-20261029T162816Z. No COM/bootstrap/injection or DB mutation. GS-117 remains OnHold; TC-001 0/5 NOT_RUN. Next: owner approval of r2 readiness-only proposal, then genuine receipt/fixture completion and separate campaign approval.


### 2026-10-29 17:06 UTC — GS117 live web acceptance preflight

Current-source idle console refreshed; web/status HTTP200. PostgreSQL, local/LAN caregiver HTTPS and Windows routing PASS. Expired existing bounded .6:8445 ingress and .6:4468 signed-time services restored with preserved trust and the existing backend dependency environment; host signed challenge signature/nonce/generation/window PASS. Fresh physical S3 mTLS/target-time acceptance NOT_VERIFIED. USB descriptors match COM4/COM10; no port opened. ADB currently no phone. Fixture/campaign approval absent, r2 inactive with all pins matching; no authorization consumed or latch changed. Jira current GS117 In Progress, GS179 In Progress; prior OnHold wording is historical. No source changes or fresh EventKey; TC001 0/5 NOT_RUN. Existing 89/89+13/13+22/22 receipts reused. Private preflight evidence directory preflight-20261029T170425Z; services bounded 3600s. Next owner actions: reconnect authorized phone and approve existing r2 readiness-only session; campaign approval remains separate after fixture validation. See GS117 EXECUTION.md for live checks, initial dependency-launch failures and exact scope.


### 2026-10-29 17:23 UTC — r2 readiness executed once; capacity evidence guard failed

Explicit owner-approved r2 activated after pins/USB/backend/ingress preflight. Previous manifest archived and earlier ledger hashes verified unchanged. One approved standard invocation, no retry, within150s. Child17:20:53–17:22:08Z stopped TC001_S3_MEMORY_PROFILE_NOT_VERIFIED: actual PSRAM8MiB, flash-size evidence absent (INCOMPLETE, not proven wrong hardware). C3 session120 runtime/sensing advanced2058881→2061403, retained3, no captured authenticated rejoin/app ACK. S3 TLS/Home/Hub/epoch observed; time/authority refresh warning at58.851s, target acceptance not verified. Later authenticated S3 authority200 and duplicate-safe COMMITTED replay118/101 establish backend recovery, not new input/TC001 PASS. Child evidence retained under standing-authorization/bootstrap-56551ab3816f16d00e646592; r2 ledger3357bc9e… consumed1/1 and latched. No TARGET_OBSERVATION_PASS/TC001_READY; positive partial evidence retained. ADB phone absent, fixture/campaign approval absent, TC0010/5 NOT_RUN. Next: offline investigate missing flash-capacity capture and receipt/rejoin observation gaps; no hardware retry without fresh scoped consent. No source edits or new regression run; no manual DB change/injection.


### 2026-10-29 — reusable DEV integration ready for controlled input

Owner-approved isolated DEV consent now extends existing authorization/controller; legacy/production paths and old failed ledgers preserved. Revocation is checked before each DEV event, failure loops bounded, erase/reprovision require recovery artifacts. Explicit DEV_INPUT_TRIAL uses real current image/USB/Home/enrollment/TLS/APK prerequisites while prior event delivery proof is obtained by the run itself; no TC001_READY or sensor/release qualification is claimed. S3 capacity16/8MiB observed after collector fix. App-only C3 diagnostic flash589dc9f9… at0x20000 succeeded; unchanged partitions/NVS, no full erase, session122 counters250→1257. APK Home/.6/CONNECTED/bytes reverified. Focused96/96, framework13/13, traceability22/22 and C3 target build PASS. Node component gate FAIL29/31 stages, historical S3 source-string and P0 PARTIAL failures retained; source changed during gate. Existing console/live DEV prerequisites pass; first controlled web input next, no new injected event yet. DTP008/009 updated for current DEV scope without release promotion.


### 2026-10-30 01:20 UTC — GS-117/179 DEV checkpoint: TLS cause established

Current branch `feature/r1-commercial-baseline`, committed/pushed HEAD `8acab96d5a7532417f98a3e10b36099f6ea975ac`; focused source/evidence changes uncommitted at this active checkpoint. Reusable DEV consent remains active; historical one-use ledgers untouched. Actual web `123/1` received authenticated class-0 ACK `retired=1` but failed backend wait; both attempted campaigns 0/5, no fresh APK PASS. RSA software TLS exceeded client3s/server5s, producing AuthorityUnavailable. TEST_ONLY client/server15s and client total30s now retain actual6281ms authenticated complete response; production3s/5s preserved. Actual S3 backlog publication advancing, latest118/123. Three app-only S3 writes, latestff111634…, no erase/credential/enrollment changes. C3 app589dc9f9… unchanged; post-Hub rejoin pending completion. ADB phone authorized. Existing expired services restored; ingress alone restarted for correction.

Focused 98/98, C++ TLS cases and two real isolated PostgreSQL delay/concurrency cases PASS; S3 build completed. Full PostgreSQL suite running. Actual prior affected gates FAIL: Hub 52/55, contract 46/48, backend 24/27 stages PASS; commissioning source assertion, migration, P0 PARTIAL, Python static budgets and diagnostic registry expected-set failures retained, see GS117 EXECUTION.md. No blanket regressionPASS. SDK prefix and parent-budget preparation mistakes corrected offline; failed attempts preserved. Minimum next action: C3 rejoin, wait old backlog through controlled123/1, existing web Run fresh five events with exact-key actual Android observation; no new approval within active DEV scope.


### 2026-10-30 02:13 UTC — owner quota pause; resume existing GS117 physical campaign

Paused at reported11% five-hour allowance, below owner12% threshold. **0/5 campaign acceptance**; no physical operation or test left running. Real126/1 passed C3→authenticated durable S3ACK→physical CloudSync→one PostgreSQL/API record. APK XML matched but PNG review showed collapsed details; complete Android acceptance NOT_VERIFIED. Original evidence preserved with capture-review.json. GS177 shared UI now preserves same-Home event disclosures across refresh; observer enforces bounded stable navigation and before/after PNG exact-key checks. Actual APK reload/reverification is pending, no reinstall/data clearing.

Validated:GS117104/104; PostgreSQL71/71 before new UI case; new production-path Reports browser1/1(6 assertions); completed target builds; framework13/13 and traceability22/22 before final metadata additions. Full browser interrupted at owner pause:41PASS,1interrupted, never fullPASS. Prior full component failures remain. Firmware latest C3 589dc9f9…, S3 ff111634…; app-only writes, no erase/credential/enrollment/partition changes. NodeHealth503/UNKNOWN/STALE and slow DEV delivery remain separate gaps; no optical/release qualification.

Active reusable DEV consent remains but latest observer edit invalidates its procedure fingerprint until reviewed repinning on resume. Preserve all old policies/latches. Existing bounded service/GS40 windows may expire; check actual state before restoration. Next: full browser/new PG regression, served UI reload and read-only126/1 screenshot consistency, reviewed active DEV pins/current fixture, restore only expired existing services/GS40 if needed, then new web five-run campaign. Detailed exact paths, identities, commands, guard state and failed campaign IDs are in the latest GS117 EXECUTION.md section. No additional owner hardware approval inside existing DEV scope; no new physical run started at pause.


### 2026-10-30 07:19 UTC — GS-117 resumed checkpoint

Canonical branch `feature/r1-commercial-baseline`, commit `e52f4c84edbebe789c757589593326ea3e754d7c`, origin equal; tracked worktree clean and preflight PASS. No hardware operation or new event occurred. Active DEV consent was preserved and its sole stale serial-helper fingerprint was updated through an owner-only atomic backup/repin; no permission scope or old approval/ledger changed.

The resumed PostgreSQL suite passed72/72; Playwright passed86/86 and dashboard preview20/20. Local PostgreSQL durability/TLS, caregiver HTTPS and LAN TLS at192.168.1.6 pass. GS-117 console remains active on127.0.0.1:18791 but is an older process; physical ingress is not configured. ADB enumeration returned no connected device.

The installed Android app serves shared PWA assets bundled in its APK. The Reports-details fix therefore requires a newly built signed TEST_ONLY APK; a foreground refresh cannot update the existing binary. CI run40990890768 failed before APK build because the registered required `sdkconfig.gs40_test_only_uart.defaults` was absent from the GitHub checkout; its existing local file is now tracked in the reviewed source checkpoint. The focused profile regression file reported17/18, with one known false-positive string assertion retained. Rerun the existing TEST_ONLY APK workflow. Local Android SDK/Gradle/signing material are absent. Existing campaign remains0/5; physical126/1 passed through DB/API but Android screenshot acceptance remains unverified. Next: connect phone/ADB, run existing TEST_ONLY APK workflow and data-preserving update, verify126/1 screenshot and XML on device, restart console, restore only expired bounded S3 services/config, then resume the existing campaign under active DEV consent. Full browser/API passes are not APK or physical qualification.


### 2026-10-30 07:44 UTC — GS-117 resumed: services restored; first live target blocker retained

At canonical `feature/r1-commercial-baseline` source HEAD `2743c92966e8d832db81203db62d0bf6f7164373` (origin equal before this evidence update), context preflight PASS and tracked files clean. Existing untracked assets preserved. PostgreSQL verify-full/durability, caregiver HTTPS, LAN TLS at `192.168.1.6`, current forwarding and loopback console HTTP 200 pass. Bounded existing GS-179 8445 ingress and 4468 signed-time services restored from preserved scripts for 3600 seconds; no persistent startup was added.

Corrected the protected-bootstrap stale nested helper pin privately: v18 changes only the serial-helper digest; DEV policy scope and prior failure history were preserved. One corrected protected bootstrap completed encrypted GS40 exchange and rearmed/reset the S3 as scoped; no C3 reset command or motion input was issued. Current physical S3 boot reported 16 MiB flash/8 MiB PSRAM and TLS `valid=1`. C3 session-126 GET_STATE succeeded and runtime/sensing counters advanced `1060267→1064317`; retained/in-flight/pending input are zero. Target readiness did not pass: no same-session authenticated S3 rejoin line was captured, desired household config was rejected, deterministic rules remained disabled, and CloudSync reported zero submitted events. Current mTLS authority-refresh routes did return 17 HTTP 200 responses after the S3 boot; the existing listener validates the mTLS/Hub authority before issuing a signed response, but target lease installation/config acceptance is still NOT_VERIFIED. Host signed-time request count is not source-correlated.

A read-only PostgreSQL check shows no desired configuration row for `gs177-test-product`; no protected data changed. ADB currently reports no device and Windows present Android/ADB device count is zero. The existing signed APK artifact is ready but not installed/observed. Focused console tests passed 104/104. TC-001 remains **0/5**, no new input was sent, and historical `126/1` was not recounted. Details and evidence locations are in `docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md`.

The private DEV failure ledger now retains two readiness attempts after the stale pin correction and the subsequent missing-rejoin result; do not clear it or retry bootstrap until the desired-config/rejoin cause is identified. Next: restore ADB visibility; diagnose the saved config-fetch rejection and missing authenticated rejoin without weakening guards; then use the existing web Run only after backend, Hub and actual APK readiness gates pass. No full physical acceptance, optical-PIR result, flashing, erase or database mutation is claimed.

### 2026-10-30 07:49 UTC — GS-117 current status reconciliation

Canonical source/evidence HEAD is `f3e909aefabead856ceeaa7662ac0903a6b5eb98`, with matching origin and clean tracked files; existing unrelated untracked assets remain preserved. Context preflight PASS. PostgreSQL, caregiver HTTPS, `.6` LAN TLS and forwarding pass. The GS-117 controller is responsive when queried with its required loopback Host/Origin and is idle; its physical USB inventory is descriptor-only (`PARTIAL`). Scoped ingress listener/forwarding and signed-time helper are active, but fresh authenticated S3 receipt, target trusted-time/lease installation and current C3 rejoin are NOT_VERIFIED. Do not confuse the general caregiver server's `HUB_INGRESS_READY=NOT_CONFIGURED` with the separate active bounded listener or with target authentication.

Current authorized ADB enumeration is empty; actual APK verification is BLOCKED. Settings reports HTTP 403; no applied household/Morning Routine policy or desired PostgreSQL row is present. Existing S3 source uses authenticated desired-config fetch and fails closed. Captured ingress records show authority-refresh HTTP 200 only, no desired-config response, so the target rejection's exact cause remains unknown. The private DEV readiness ledger retains two failures and must not be cleared or retried before offline cause analysis. No hardware operation, injection, new event or DB mutation occurred in this checkpoint. TC-001 remains **0/5 accepted**; previous partial physical events remain separate historical evidence. Exact current evidence and next actions are recorded in the GS-117 execution handoff.

### 2026-10-30 19:30 UTC — persistent DEV-mode authorization pin recovery

The current canonical branch is `feature/r1-commercial-baseline` at
`173b307ff56cb0d022652b3e531ad6bef57986fa` before this checkpoint's commit;
origin matched. Context preflight PASS. Only the GS-117 authorization module
and its existing registered Python test file were modified by implementation;
untracked Android, firmware and historical evidence assets were preserved.

The owner-directed persistent TEST_ONLY mode is recorded enabled and unrevoked
in the owner-only manifest. The previous authorization scope (29 sessions,
three failures, failure-latched) remains a separate immutable historical
scope. The current mode's first reserved session at 18:50 UTC failed before
device access because the protected bootstrap still embedded an obsolete
serial-helper fingerprint. The failure evidence is retained; no COM/USB,
reset, bootstrap, injection or database operation occurred. The current
manifest therefore does not yet load through the standard entry point because
the reviewed validator source pin changed.

The existing authorization module now supports a chained, commit/test-bound
source-fingerprint review that preserves the previous private manifest and
authorization scope; it does not grant sessions or clear counts. Its bootstrap
path accepts only the exact one-string stale-helper correction from the
verified private backup. The exact pre-operation failure disposition retains
the original failed session and appends a linked record; other unknown,
identity or security failures remain latched. No new authorization framework
was introduced.

Focused results after final edits: GS-117 suite **133/133 PASS**;
validation framework **55/55 PASS**; feature traceability **232 features,
287 modules, 27 physical cases; 22/22 mapping tests PASS**; Python compile and
`git diff --check` PASS. These are software authorization/controller results,
not physical qualification. `GS117_DEV_TEST_ONLY` routine use remains blocked
until the reviewed source/bootstrap fingerprint update and exact pre-I/O
failure disposition complete.

The Windows ADB executable sees `ZA2237MRHN` as `device`; the handset is
Dozing with keyguard active, so no app foreground/navigation or event
observation was attempted. No fresh physical event was generated. Formal
campaign remains **0/5**; the historical `126/1` event and ~6h53m delay for
`123/1` retain their prior classifications.

**Next:** commit/push only reviewed GS-117 source/tests and evidence; verify
and update private source pins using the existing audit path and a byte-exact
manifest/bootstrap backup; disposition only the matching pre-I/O pin failure;
then inspect live readiness. Keep the existing campaign stop-on-first-failure
logic and do not start a campaign until actual APK observation is possible.

### 2026-10-30 19:39 UTC — persistent DEV mode active; APK receipt blocks campaign

Commit `a5b3e79dc15d4e68690f34afb232b73201c99282` is pushed and matched
origin. The reviewed source update chained exact current private fingerprints
for the existing bootstrap and authorization validator after the focused test
receipt; it did not change device/Home/backend scope or procedure allowlist.
The prior manifest was byte-preserved in the owner-only audit directory. The
single reserved session failed before Windows helper invocation because of
the stale nested serial hash; an exact, evidence-linked disposition leaves
that original failure intact as `NOT_RUN`, preserves session count 1, and
returns persistent DEV status to `ACTIVE` with 0 consecutive safety failures.
The predecessor 60-entry audit prefix and 29-session/3-failure ledger still
match their activation hashes exactly. No authorization history was deleted,
rewritten or reset.

Current health: PostgreSQL durability/TLS, local caregiver HTTPS, laptop LAN
TLS/forwarding at `192.168.1.6`, Windows portproxy route audit, caregiver Home
and the exact COM4/COM10 USB descriptors pass. The existing 8445 listener and
Windows route are ready; this is not a current S3 mTLS/time proof. The
existing console's current readiness response blocks at the owner-only fixture
because its Android install receipt is 25.7 hours old; the fixture-derived
campaign and enrollment checks are consequently blocked. The authorized ADB
serial is currently online, but Android is Dozing behind keyguard; no APK
foreground or current authenticated Home/origin observation was attempted.

Validation: GS-117 focused suite **133/133 PASS**; validation framework
**55/55 PASS**; feature traceability **232/287/27 with 22/22 tests PASS**,
including a rerun after updating the existing GS-130 row to this commit and
pin-review regression. Python compile and diff-check PASS. No hardware session,
serial open, reset, bootstrap, injection or database write occurred. TC-001
remains **0/5**, and previous EventKey `126/1` remains supplemental historical
evidence. Event `123/1`'s ~6h53m delay remains unresolved.

**Next exact owner action:** unlock authorized phone `ZA2237MRHN` and leave it
available to the existing ADB observer so current APK, Home, backend origin
and authenticated UI evidence can be refreshed. Then rerun the existing
fixture/readiness gate and, only if it passes, start the already existing
bounded five-run campaign under active DEV Mode. No separate routine campaign
consent is needed while Development Mode is active; real security, fixture,
authentication and event-stage guards remain mandatory.

### 2026-10-31 02:28 UTC — latest GS-117 readiness disposition

The previous handoff's `ACTIVE` Development Mode state is superseded by one
authorized readiness session on 31 October. It stopped at
`standing_readiness_authenticated_liveness_not_verified`; current DEV status is
`SAFETY_LATCHED` (2 sessions, 1 consecutive safety failure, blocked=true).
Historical predecessor scope remains 29 sessions / 3 failures / blocked and
was not changed. No motion input or TC-001 run occurred; formal campaign stays
**0/5 NOT_RUN**.

The phone is now online and unlocked. The installed Parivar Saathi APK was
observed against Home `gs177-test-product`, origin `https://192.168.1.6/` and
backend CONNECTED; its fresh owner-only receipt records installed APK bytes
matching the trusted artifact. The signer digest was corroborated, but formal
`apksigner verify` was not run. Historical EventKey 126/1 was seen again and
does not count as a fresh campaign event.

The single protected S3 bootstrap reported 16 MiB flash, 8 MiB PSRAM and TLS
pair validation `valid=1`. Target authority/config startup logs establish
trusted time and a current authority lease by control flow: the target reached
the `current_binding()` branch, whose implementation requires an unexpired
lease and trusted time from the same boot generation. This is not a separate
serialized target receipt. The exact household-config rejection remains
unresolved because target evidence did not capture a fetch status/body. C3
GET_STATE liveness advanced `4,432,374→4,436,416` in session 126, but no fresh
authenticated rejoin line was captured. Source shows that a running C3 does
not immediately rejoin solely because S3 rebooted: its idle-contact recovery
timeout is 430 seconds when negotiated, and the observation was about 81
seconds; the existing HIL reassociation request is only consumed before the
security link becomes ready. This absence is not proof of a C3 security defect.

The existing fixture remains blocked at
`c3_current_installed_image_provenance_missing`. No current installed-image
receipt was fabricated. Bounded 8445 and 4468 readiness services were stopped
and their listeners verified absent; backend/PostgreSQL and the loopback GS-117
console remain available. Source was unchanged, so prior focused tests were
reused; only documentation diff validation is applicable. Evidence and exact
source analysis are in the GS-117 execution handoff section dated
2026-10-31 02:28 UTC.

**Next:** preserve the safety latch and failure evidence. Use the existing
audited review/disposition path before any new hardware session; then review
the minimal readiness sequencing change and config-rejection evidence gap.
Re-evaluate the current-image fixture and campaign gates before injecting.
Event 123/1's ~6h53m delay remains unresolved; real PIR and release acceptance
remain separate.

### 2026-10-31 02:56 UTC — GS-117 offline RCA; hardware remains stopped

Canonical source remains `e69ee50e25b5cf5b570b2fdc8f44ef40e54bb91d`; no source
change or hardware operation was made. The active DEV authorization is enabled
and unrevoked but **SAFETY_LATCHED** (2 sessions, 1 consecutive safety failure).
The current failure is `standing_readiness_authenticated_liveness_not_verified`.
The only existing reviewed disposition accepts the exact earlier pre-operation
serial-helper pin mismatch; it cannot disposition this post-operation missing
rejoin. Keep the latch and both historical ledgers unchanged. No hardware may
be operated until a valid explicit audited successor/disposition exists.

The previous C3 observation showed increasing runtime/sensing counters, not a
fresh authenticated rejoin. S3 was restarted while C3 remained link-ready; the
negotiated C3 idle recovery timeout is 430 seconds, versus the ~81-second
observation. The HIL reassociation request only acts before the C3 security link
first becomes ready. This is an insufficient readiness sequence, not proof of
authentication failure. A useful next bounded observation must restart C3
after S3 bootstrap and observe the real S3 authenticated rejoin plus advancing
counters.

The S3 `desired household policy rejected` message is a local source-level
precondition: the signed GS40 bootstrap has `fixture_home_id` but no
`activity_home_id` (fields 17–20); the fetch routine rejects empty activity
Home before HTTP. The ingress trace has no `/config/desired` request, only
authority-refresh responses. TLS pair validation was `valid=1`; this message
does not prove backend rejection. No desired routine policy row exists, but
supported version-0/no-policy is sufficient for motion TC-001. Morning Routine
configuration application remains a separate gap; no policy was seeded.

The last C3 installed-image receipt (2026-10-30 01:40:47 UTC) and S3 receipt
(01:38:46 UTC) are stale. Their recorded application hashes matched the
approved images; the later S3 boot freshly reported 16 MiB flash, 8 MiB PSRAM
and expected S3 image identity, but C3's current image was not freshly proven.
The inactive owner-only readiness candidate is
`~/.local/state/ghar-sajag/gs117-tc001/readiness-proposal-20261031/gs117-protected-bootstrap-development-v19-rejoin-candidate.py`,
mode 0600, SHA-256
`0429ee7f7293f319cd0538ca10d52c063613dd5b837116b63232491345a5ff55`. It
refreshes helper pins, uses the observed S3 image, enables the existing bounded
C3 restart after S3 bootstrap and observes for 90 seconds. Syntax check passed;
not activated or executed. Active manifest remains pinned to the v18 parent
`7cd38e60b291e12ee51572b30f55a83fc8fb393ca188328c06f8e3541eff7ccb`; pin
maintenance does not clear the latch. No fresh receipt was fabricated.

Event `123/1` still has an unresolved ~6h53m delivery delay: C3 injection and
S3 class-0 admission passed; the original backend wait timed out after ~61
seconds, and later PostgreSQL/API commit is confirmed. The retained ingress log
does not include that EventKey, so retry/backlog root cause remains unknown.
No timeout change or reliability PASS is claimed. TC-001 remains **0/5**;
historical EventKey `126/1` is supplemental only. Details and evidence limits
are in the dated GS-117 execution handoff section above.

**Next action:** obtain one explicit owner approval for an audit-linked
successor authorization with a new approval reference, preserving the present
latched scope, its original failure record and all predecessor ledgers/counters
unchanged. Do not clear/relabel the latch or reset counters. The existing code
has no disposition for this post-operation guard (only the earlier exact
pre-operation pin mismatch). The approval should cover at most two bounded
operations on this exact TEST_ONLY fixture: one readiness session using the
inactive reviewed candidate (one S3 bootstrap/reset, one C3 restart/GET_STATE
and rejoin observation); then, only if readiness and fixture gates pass, one
existing campaign of up to five fresh events, stopping at the first non-PASS.
No flash, erase, credential, enrollment or ownership change is needed or
included. No hardware action has been authorized/executed in this checkpoint.
GS-117 remains In Progress.

### 2026-10-31 — owner-approved successor readiness result

Owner approval is recorded at GS-117 comment 11859 (`OWNER_CHAT_GS117_SUCCESSOR_20261031`). The one audit-linked successor is active and its single readiness session is consumed: the scope records one successful protected bootstrap/target observation, zero new safety failures, and one conditional campaign session remains. All predecessor ledgers and failure latches remain intact; the original 67-record audit prefix hash is unchanged. Exact activation, ledger hashes and evidence path are recorded in the GS-117 execution handoff.

Result: `TARGET_OBSERVATION_PASS / FIXTURE_PENDING`, not `TC001_READY`. Actual S3 reported 16 MiB flash/8 MiB PSRAM, post-reset app at `0x420000`, version `8acab96-dirty`, ELF prefix `7584a1f80`, and TLS pair `valid=1`. C3 session 127 runtime/sensing counters advanced `1347→1852`, and S3 logged authenticated Bedroom rejoin for the expected C3. This is current runtime/rejoin evidence, not a full installed-image hash receipt.

Target time/authority acceptance remains unverified: the target produced authenticated TEST_ONLY HTTP 200 authority-refresh requests, but its log also reports deterministic rules disabled because signed Home config/current lease/trusted time was unavailable and records a household-policy rejection. Host signed-time request count was 28 but no target-bound acceptance receipt exists. NodeHealth returned 503; CloudSync submitted/completed zero events; structured ingress evidence is missing. The exact fixture still fails at `c3_current_installed_image_provenance_missing` because its installed-image receipt is over 24 hours old; the S3 receipt is also stale. The Android phone was not present in ADB at campaign preflight. It is not required for readiness observation, but actual Android observation is required for campaign acceptance.

No event was injected; TC-001 remains **0/5**. Bounded 8445/4468 services were stopped and both ports verified closed; the existing local console was preserved. The readiness CLI exited 1 only after saving the target result, when it tried to bind a second listener to the already-running `127.0.0.1:18791`; no pinned source was changed. Event 123/1's ~6h53m delivery delay remains unresolved. GS-117 remains In Progress.

**Next:** offline-trace target signed-time/current-lease state and determine whether genuine current image/structured-ingress receipts can be collected within existing non-destructive authority. Reattach the authorized Android phone for its current APK receipt. Do not consume the remaining conditional campaign authorization unless all target trust, fixture, backend, and APK gates pass.

### 2026-10-31 04:14 UTC — Android reconnected; readiness reconciled

The authorized ADB phone is online, awake and unlocked. The existing observer
reverified historical EventKey `c3-146393c5d158 / bedroom / 126 / 1` in the
actual installed APK with Home `gs177-test-product`, origin
`https://192.168.1.6/` and Backend API CONNECTED. Current installed APK bytes
match the preserved trusted SHA-256
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`;
signer-digest corroboration is retained, formal `apksigner verify` was not run.
Private screenshot, accessibility and APK identity evidence are under
`~/.local/state/ghar-sajag/gs117-tc001/android-attached-refresh-20261031T041212Z/`.
This is historical-key Android evidence only. The app displays monitoring and
source UNKNOWN / physical origin not verified.

Correction to the preceding readiness interpretation: target CloudSync
`state=3` maps to `CloudWorkerState::Ready`; the worker sets it only after a
route and current Home/Hub/epoch binding are available. The S3 trust source
requires an accepted signed-time proof/floor and an unexpired signed authority
lease matching the same boot generation and credential binding. This proves
time/authority acceptance during those target polls, not from HTTP 200 alone,
and is not a standalone signed receipt or current campaign-time proof.
`submitted=0` was expected because no event was queued. The generic activity
rules warning does not identify the failed prerequisite. Household-config
rejection can occur before HTTP; the trace has no `/config/desired` GET, and
the exact clause was not recorded. The DEV version-0 motion path needs no
Morning Routine policy. NodeHealth 503 is a separate additive status path with
no preserved response body; it is consistent with the APK's UNKNOWN monitoring
status but does not establish event CloudSync failure.

Current C3/S3 image receipts are respectively 26.56h/26.60h old; the fixture
allows 24h. Source inspection found the installed HIL `GET_STATE` reports the
active OTA slot but not an image digest or partition-table digest. The C3
GS-68 image-hash observer is an isolated profile that the build explicitly
forbids composing with HIL controls. S3 boot evidence supplies a version and
short ELF-hash prefix, not the full app/partition hashes required by the
fixture. `exact_fixture()` therefore remains BLOCKED at
`c3_current_installed_image_provenance_missing`. The readiness session is
consumed; the active successor has one conditional campaign slot. TC-001 stays
**0/5**; no C3/S3 operation or physical motion event occurred in this turn.

**Next exact action:** owner authorization is needed for one targeted,
read-only current-image/partition/OTA-selector observation on the identified
C3/S3 because no existing non-destructive runtime path emits the required full
receipts. Include any expected serial-reset effects and one existing S3
protected bootstrap/C3 rejoin to restore and verify RAM-only configuration;
only after that fixture passes may the remaining conditional five-run campaign
be used. No C3/S3 operation or physical motion event occurred in this turn;
the Android ADB observation was read-only. GS-117 remains In Progress.

### 2026-10-31 07:44 UTC — GS-177 caregiver login network and visibility checkpoint

At source checkpoint `3033ce3576662e97a4a881785b37c9c96a8db3df` (branch
`feature/r1-commercial-baseline`; origin matched before edits), local PostgreSQL
and caregiver HTTPS pass with verified TLS, while the Windows LAN endpoint
probe fails. The approved `Yogi` Wi-Fi is categorized Public. The existing
trusted-network task exits 1 on its intended
`active_wifi_must_be_owner_trusted_private_or_domain_authenticated` guard
before network mutation. The phone is ADB-online but on `Airtel_Agrim`, not
Yogi; no phone Login request was observed. Exact APK `Failed to fetch` cause
cannot be stated until the phone is on the intended network and the real
request is captured. No firewall, proxy, account, session or app state changed.

Implemented the shared PWA login Show/Hide control (hidden by default, value
and selection preserved, accessible labels, re-hidden after login failure),
registered its asset/dependencies and added unit/browser assertions. Node
focused tests passed 12/12, GS-177 connected-lite API passed 23/23 plus three
host scenarios, component-gate tests passed 55/55, and feature traceability passed 22/22
(232 features / 288 modules / 27 physical cases). The browser command was attempted but ran zero tests because Chromium/Chrome is absent;
actual Android UI/login remains NOT_VERIFIED and the APK was not installed or
updated. No four-digit PIN was added: the existing account verifier requires
16–256-character passwords and its bounded email/IP lockout is not a suitable
4-digit PIN defense; no per-account TEST_ONLY PIN provisioning contract exists.
No production auth policy or credentials changed.

GS-117 remains 0/5 and hardware `SAFETY_LATCHED`. S3 challenge diagnostics were
not deployed; no correct full TEST_ONLY diagnostic image was built because the
exact paired C3 asset needed by the existing builder was absent from checked
build paths. Historical session 127/129, EventKey 123/1 latency, EventKey
126/1 and physical acceptance statuses are unchanged. Exact evidence is in
[`GS-117 execution handoff`](../exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/EXECUTION.md).

**Next:** restore the owner-approved Yogi network to the existing required
Private profile through Windows' normal administrator UI, then run the
existing scoped recovery and observe a real Login from the attached phone on
that LAN. Continue offline preparation while awaiting that network change.

### 2026-10-31 07:51 UTC — asset-route and performance-budget result

Added the missing exact `/password_visibility.mjs` route to the existing local
lab allowlist and covered it in the HTTP asset test. The focused route test
passed; component-registry tests passed 55/55. The PWA startup-size profile
now counts the imported visibility helper. Its focused budget test failed at
`static.total_bytes=120819` (limit 114688) and `static.css_bytes=29576` (limit
18432). CSS was unchanged by this task and budget values were not relaxed; the
profile failure remains visible. Feature traceability passed 22/22 with 232
features, 288 modules and 27 physical cases.

No actual installed-APK Login request/result is available yet. The laptop
HTTPS/PostgreSQL checks pass locally, but the Windows trusted-network watcher
is stopped by the current Public classification of approved SSID `Yogi`, and
the attached phone is on `Airtel_Agrim`. No firewall/profile mutation was
performed. GS-117 remains safety-latched and TC-001 remains 0/5; no hardware
was accessed. Detailed network and Show/Hide evidence remains in the linked
GS-117 execution record. Jira comments 11868 (GS-177), 11869 (GS-179) and
11870 (GS-117) were posted and read back; all three remain In Progress.

### 2026-10-31 07:59 UTC — CI APK package verified; physical Login pending

Commit `6813bee1978589f09029397e277d24bd2ed5d9e2` is pushed and matches
origin. Existing GitHub workflow `41182431768` completed successfully:
Chromium browser/offline-startup regression passed; registered caregiver/API,
Android-dashboard and voice-prototype stages passed with 23, 19 and 29 checks;
the report explicitly says physical `NOT_RUN`. The signed APK artifact
`13035483200` targets the staging Render origin and uses the workflow-generated
debug signer. Its SHA-256 is
`870e4fc91a1f4b9b420f9229657c95c5059e6804c10275c2596abe1267bdda86`; bundled
Show/Hide helper bytes match the source. It was not installed on the physical
phone, so actual local-backend Login and handset UI remain unverified.

The approved Yogi network remains Public, and ADB reports the phone on
`Airtel_Agrim`; the existing guard prevents LAN forwarding recovery until the
owner restores Yogi to Private through Windows' normal admin UI and joins the
phone to that LAN. No firewall/proxy/network or app data changed. GS-117
authorization is still safety-latched and TC-001 remains 0/5. CI follow-up
comments 11871 (GS-177) and 11872 (GS-117) were posted/read back; GS-179
comment 11869 retains the exact trusted-Wi-Fi guard result.

### 2026-10-31 08:23 UTC — fixture network and TEST_ONLY S3 candidate build

Live read-only checks show Windows Wi-Fi `Yogi|Public` and the authorized
ADB-online phone `ZA2237MRHN` on `Airtel_Agrim` (`192.168.1.5`). The existing
trusted-network recovery guard correctly does not mutate a Public network.
Local HTTPS/PostgreSQL PASS does not establish laptop LAN reachability; the
installed APK's Login request remains uncaptured and actual login is
NOT_VERIFIED. Next network prerequisite is restoring the approved Yogi profile
to Private through Windows' standard administrator UI and joining the phone to
that network before using the existing scoped recovery.

The paired C3 build asset is present and its SHA-256 matches the previously
verified image. A correct clean ESP-IDF 6.0.3 S3 TEST_ONLY configuration exposed
an incomplete existing UART fixture profile: the protected RSA bootstrap
requires an 8192-byte main-task stack, and the profile needed to explicitly
select UART0 rather than USB Serial/JTAG. The opt-in
`sdkconfig.gs40_test_only_uart.defaults` now declares those two existing
requirements; production defaults and firmware runtime are unchanged. Focused
profile regression passed 1/1. The full 18-check fixture module is 17/18 due to
the pre-existing brittle production-builder string assertion recorded in the
execution handoff.

The final clean TEST_ONLY S3 build passed compile, image generation and size
checks: app 2,303,136 bytes in the 4 MiB slot (45% free), ESP32-S3/16 MiB,
UART0, 8 KiB bootstrap stack. App SHA-256:
`d1e15266b89bfd14ea17d92d3616d2d2bb334d024693ccb0be00232aa23a8d10`; ELF:
`224fbc4f15c9653da80591c62cbdffb84dfdbfe6d8740dc1dbf540f4d9c59ccb`.
This is build-only; no hardware was accessed and authorization remains
SAFETY_LATCHED. Read-only authorization status reports 2 sessions, 1
consecutive safety failure and 0 reviewed dispositions. GS-117 remains 0/5.
Earlier valid software/physical evidence is reused as recorded; no broad
regression suite was rerun. Show/Hide remains
unverified on the installed APK; the four-digit PIN remains deferred pending a
secure TEST_ONLY credential contract. Event 123/1 latency remains unresolved.
