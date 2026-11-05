# GS-117 diagnostic corrections — offline implementation

Starting canonical local/remote `113d45d09f7ae258a88bcdd3a14b1272fbb4dd62`,
`feature/r1-commercial-baseline`; context preflight PASS, tracked clean,
79 pre-existing untracked entries preserved. Owning Jira GS-117, Highest /
In Progress; source-backed investigation and limitations in
[session134 RCA](GS117_SESSION134_OFFLINE_RCA_20261105.md), Jira11921/11922.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY` for collection/diagnostic evidence;
`R1_FIX` for the proven uninstalled S3 owner peer-result comparison.
Requirement source: owner's current offline correction scope, AGENTS.md,
R1_RELEASE_CONTRACT.md bounded behavior/security/durability invariants.
No new LOCKED decision, requirement waiver or context-version change.

Affected components: existing Windows serial collector and bootstrap-evidence
redactor; C3 target security-send/callback instrumentation; S3 target owner
peer-success check and TEST_ONLY channel/readiness evidence. Shared wire,
authentication, channel/retry, storage, event/ACK and cloud contracts unchanged.
No GS179 networking implementation/configuration work.

Minimal design: a single monotonic observation deadline starts after separately
permitted bootstrap/reset, includes all collection/query phases, and permits
only cleanup/evidence finalization afterward. Bounded collector metadata labels
host receipt versus target uptime/boot and exposes loss/truncation. TEST_ONLY
C3 evidence records send stages/API results and bounded callback metadata outside
the Wi-Fi callback; same-peer callbacks are not claimed transaction-correlated.
Keep existing queue consumption/overwrite and transport return decisions.
Fix the S3 caller's `esp_err_t` comparison, preserving peer-management behavior.

Validation plan: registered production-function radio mocks, fake-clock and
TWDT/redaction/boot/exception tests; existing GS117 authorization/collector,
Wi-Fi/rejoin/GS40 bootstrap, affected Node/Hub/contract and framework/mapping
regressions, applicable C3/S3 compile-only builds. Physical-specific behavior
remains unqualified; target compilation and host simulation cannot prove RF.
Preserve known incomplete P0/migration/quality gates; no release candidate claim.

Strict boundary: no ports/devices/reset/bootstrap/deployment/readback/erase,
motion/campaign, network windows/configuration, authorization activation or latch
change. #11897 remains SAFETY_LATCHED1/1 and #11886 remains intact. Original v18
and historical helper pins/approvals/evidence remain immutable. Changed helper
and artifact identities will be proposed only, never silently activated.

## Implemented corrections and limits

* `gs117_tc001_serial_windows.observe`: one absolute monotonic deadline after
  the separately permitted bootstrap/reset; four-second initial collection,
  GET_STATE and remaining collection all use that deadline. No extra ten-second
  drain. DEV readiness is capped at90seconds. Each read/write gets a remaining-
  budget timeout; no observation `flush()` can block beyond it. Cleanup performs
  no additional reads and records its separate duration. A broken driver that
  ignores its timeout is detected on return and its late bytes are not admitted;
  Python cannot guarantee OS-driver cancellation. No new worker or port owner.
* Collector keeps at most300 lines/board,1024characters/line,4096bytes/read,
  2048characters pending,300 timestamp records and16 boot markers. Whole
  overlong partial lines are discarded through newline so secret suffixes cannot
  lose their redaction label. Loss/truncation, including an unterminated final line, is counted and prevents a complete
  observation result. TWDT headings, overdue-task/CPU lines and backtraces survive
  filtering in original board-local order. UTC host arrival is batch receive
  time, not target event time; parsed target uptime is separate. Boot-marker
  epochs are transcript boundaries, not a claimed reset count or synchronization.
  The parent evidence writer preserves only the explicit bounded metadata schema.
  Previously filtered session134 task headings cannot be recovered by this
  change; no historical missing line is synthesized.
* Cooperative exceptions/timeouts/cancellation retain partial evidence and close
  both handles, including when one close fails. Abrupt process termination can
  still lose in-memory evidence; no crash-persistent UART stream is claimed.
  Legacy explicit commissioning is a separate operation and is not enabled by
  the Bootstrap readiness path or this task.
* C3 target instrumentation is compiled only for existing
  `GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE` TEST_ONLY profile.
  One bounded owner-side record reports local wire transaction/kind/session,
  destination, requested/actual channel and read result, peer/add/read metadata,
  immediate submission, callback status/peer/sequence/time, pending-queue count,
  final stage/error and elapsed monotonic time. Callback work is bounded metadata
  copying/atomic increment/unchanged queue overwrite, with no logging or parsing.
  SendResult size is statically capped at32bytes. Production profile retains the
  original Boolean-only SendResult. No keys, payload, authentication tokens or
  credentials are logged. MAC/session evidence requires existing private logs.
  C3 channel readback is a local pre-send snapshot, not an RF measurement or
  proof that a receiver was available; an intervening channel change remains
  distinguishable only with the corresponding channel/receive evidence.
* ESP-IDF does not return the application transaction in its send callback.
  Therefore same-peer/time-window evidence is explicitly `same_peer_window_no_txid`,
  not transaction proof. Wrong/unknown peer, pre-submit callback, prior timeout
  ambiguity and queue leftovers are visible. These labels do not change the
  existing success Boolean, timeout, retry, fragmentation, channel decisions or
  queue behavior. A late same-peer callback can remain ambiguous; no diagnostic
  claim silently repairs or proves callback attribution.
* S3 TEST_ONLY logs record ESP-NOW-ready/owner-ready actual STA channel and
  channel readback status. Owner-side RejoinHello/Final receive evidence records
  RX/current channel and the actual authenticated response returned by
  `HubSecurityLink::accept`. Raw wire kind/source remain untrusted; `no_outbound`
  is not an authentication rejection (fragmentation can be incomplete).
  No logging was added to the Wi-Fi receive callback.
* The newer S3 `esp_err_t` owner-call inversion was verified against commit
  `70d577ead4d19b72691adc71097bb7a0f73fb903` and corrected to `!= ESP_OK`.
  Existing-peer, successful-add and failed-add assertions execute the extracted
  production owner loop. A negative-control copy with the original predicate
  fails at that caller. The installed matching session134 ELF had the earlier
  Boolean implementation: this is not its observed radio failure cause.

## Registered validation

`gs117-diagnostic-collection` and `gs117-diagnostic-radio` are registered in the
existing component registry, with strict nonzero success/failure propagation.
The latter compiles actual target function bodies and the real wire serializer
against bounded ESP/queue boundaries for SDK6, SDK5 and diagnostic-disabled
profiles, not a rewritten transport model. New tests are mapped in the existing
traceability/source inventory. `PHY-GS117-DIAG` is proposed NOT_RUN evidence,
not permission, new product acceptance or a release waiver.

Final collector16 tests PASS; radio3 tests PASS with87 radio/caller assertions;
framework55 tests PASS. Fake clocks prove nine GET_STATE queries only when they fit, slow
responses reduce the count, no additional drain, deadline overrun failure,
exception/cancellation/cleanup handling, bounded/redacted metadata and TWDT
ordering. Initial test-adapter clock/queue mock failures remain preserved in
private evidence; the obsolete expectation of an additional ten-second drain
was replaced by the actual corrected90-second requirement. No product assertion
was weakened. Final component and target-build outcomes are recorded below;
partial component success is not full gate PASS.

The same production-function host probe also passed AddressSanitizer and
UndefinedBehaviorSanitizer (87 assertions, compile/run exit0, leak detection on).
This is memory/undefined-behavior validation of host boundaries, not RTOS/RF
qualification. The pre-existing USB-profile test's exact multiline cleanup
literal failed when exception-safe cleanup changed; it now checks the actual
`finally` AST for reversed-handle close and rejects cleanup reads/writes/flush.
Its4 tests PASS; registered behavioral tests additionally prove both handles
close after one close fails. The original failing output is preserved.

## Future diagnostic proposal — not activated or approved for execution

Retain fixture `gs177-test-product`, C3 `c3-146393c5d158` COM4/USB
`14:63:93:C5:D1:58`, S3 `hub-e072a1d38d34` COM10/USB
`E0:72:A1:D3:8D:34`. Installed images and historical pins remain unchanged.
Any deployment of the newly compiled instrumentation requires separate reviewed
artifact/procedure/rollback authorization and fresh installed-image receipts;
this document authorizes neither deployment nor another observation. The old
v18 checksum checks must reject the changed helpers. Do not amend its private
pins or consumed entitlement to make it run.

After those prerequisites and explicit new hardware scope, propose one bounded
90-second observation with approximately10-second GET_STATE, separately permitted
bootstrap and cleanup, no injected events. Capture C3 stage/error/callback labels
and actual/peer channels; capture S3 ESP-NOW/owner-ready channels and authenticated
response receive stage; preserve bounded TWDT overdue tasks/CPU/backtraces with
boot-local uptime plus host arrival labels. Confirm proposed source/ELF/image and
helper identities before any operation, with independent authorization guards.
The existing slow scan can miss the Hub channel during90seconds; any deliberate
C3 restart or different opportunity/timing plan is a separate owner decision,
not an implied extra reset/retry or change made here.

Decisive distinctions: peer-add versus immediate ESP error versus negative or
absent callback; actual C3/S3 channel overlap versus no observed overlap; S3
receipt/challenge generation versus no observed reception; callback ambiguity
versus authenticated challenge/Final acceptance; complete TWDT task/CPU evidence
versus a stack snapshot alone. Host arrival clocks do not establish RF latency
or causal ordering across independently buffered devices. TEST_ONLY logging
overhead and actual RF/RTOS behavior remain physically unqualified.

Session134 radio root cause and watchdog causal relationship remain NOT_PROVEN.
Liveness zero remains consistent with initial authentication gating. No channel,
retry, authentication, storage/durability, protocol, networking or watchdog
runtime fix has been inferred or implemented. TC001_READY NO, TC0010/5,
receipts STALE, installed firmware UNCHANGED. Real optical PIR through authenticated
durable Hub/CloudSync/PostgreSQL/caregiver API/actual Android, chronology, latency,
deduplication and recovery remain required; historical123/1 and126/1 are not fresh
acceptance, and123/1's approximately6h53m delay remains unresolved.


## Exact source and build identities

Private new evidence: `~/.local/state/ghar-sajag/gs117-diagnostic-corrections-20261105T153600Z/`.
`source-freeze.json`, `target-final-report.json`, `artifact-profile-checks.json` and
`artifact-final-source-reconciliation.json` retain commands/configurations/logs
and hash-identified copied BIN/ELF outputs. No private authorization or credentials
are committed. All following artifacts are BUILT_ONLY, never installed.

| Source | SHA-256 |
|---|---|
| `code/tools/local/gs117_tc001_serial_windows.py` | `d821b2f92858bc7d106fed7ced8c50fe82529bb5fb1b12ea9902b38b4095573b` |
| `code/tools/local/gs117_bootstrap_evidence.py` | `396c0843330559ac14d3e8efe85360a8d4161130c427f1058f16154b8eb82c29` |
| `code/firmware/node/target/esp32c3/node_runtime_adapter.cpp` | `68d5bc72d7ee1f2cd14ac3c1913677656118f1af44d649def37fe5f2ba169036` |
| `code/firmware/hub/target/esp32/hub_runtime_adapter.cpp` | `011843d7de063cc9de60a9dd4d7ff887c729cef570d96660292e2084fe93c9be` |

| Profile/target | Bytes / slot | BIN SHA-256 | ELF SHA-256 |
|---|---|---|---|
| production/c3 | 944272 / 1966080 | `7968668328b1900c05439a47cd20ef1b96449e0d12a0d99229622d7a9c5e7c28` | `53556766ae4e690d51b8db8c0f7129eabb618a59b1b2f8680e04cff2adc3f446` |
| production/s3 | 2201536 / 4194304 | `e70eee864dd985d30c9cc997de223e6b361077c071a3ac6df605a7ed225e400d` | `dd9f8211eb18c39b5bb47efce5dc7054fda441a08311b3ae292edbbd2c12c30a` |
| diagnostic/c3 | 966832 / 1966080 | `8cca8460fe5fab1fed547026023cee7f6038b6c150ec522969be2336d1f24b38` | `a11eef6637cdd592fb4dcf5c63db4f70e5b86cca7861826b18d995d06d0173cb` |
| diagnostic/s3 | 2311904 / 4194304 | `d08f70081b750b6cc1bfbd1bf95d09da8d3741f3238629dcb7949b78a572c679` | `b08ef2ea3ba633a2ed000b31c328c30e8013abefa04eb6c53394b4593fc704f0` |

ESP-IDF6.0.3 paired builds PASS/exit0 for production and diagnostic profiles.
Versions are `113d45d-gs117p-bf0ea8a3` and `113d45d-gs117d-bf0ea8a3`.
The target stamp records the build-start repository fingerprint; subsequent
collector-only empty-read/partial-line accounting changes do not change target
C++ inputs. Final runtime-adapter hashes match the compiled inputs exactly;
final host-validation fingerprint is `7e77cc8bf7edd96f910944685e06ddae952188c948300ba0c29dd7b26f51a183`.
These are pre-commit build identities tied to explicit file hashes, not a claim
that the final commit string is embedded or that an installed device was read.

Production C3 HIL_BUILD/CONTROL/PHYSICAL_WAKE are OFF. Production S3
TEST_ONLY_CLOUDSYNC/HIL_BUILD/CONTROL/COMMISSIONING are OFF with no TEST_ONLY
root. Diagnostic C3 uses the existing awake HIL_CONTROL profile (HIL_BUILD and
PHYSICAL_WAKE OFF). Diagnostic S3 reuses the preserved GS40 TEST_ONLY UART,
software-TLS and8KiB-main-stack defaults/profile with the existing PUBLIC root
DER, HIL_COMMISSIONING ON, HIL_BUILD/CONTROL OFF. No new key/certificate/profile
policy or device configuration was created. Both images fit their existing
OTA application slots. Local image-info verifies the embedded ELF identities.
Paired packaging verifies C3 is actually embedded in S3. Marker checks prove
new radio diagnostics are present in TEST_ONLY images and absent in production.

Retained build failures: the first cold S3 production build timed out at1800s
near final main objects; its same-directory incremental final-source build
passed. The first diagnostic S3 configure correctly rejected the incompatible
production DS-peripheral SDKCONFIG; reuse of the already reviewed TEST_ONLY
SDKCONFIG/defaults then passed. Original logs remain intact. No guard was
removed or production configuration relaxed. Build rollback configuration
does not prove installed bootloader rollback; GS-D029/030/173 are unchanged.

Future review must pin these NEW artifacts/helpers and a separately reviewed
procedure. If the proposed S3 diagnostic image is ever separately authorized
and installed, its expected app version is `113d45d-gs117d-bf0ea8a3` and ELF
prefix `b08ef2ea3`; this is not the presently installed `8acab96-dirty`/
`7584a1f80` identity. Original v18 remains exactly
`7cd38e60b291e12ee51572b30f55a83fc8fb393ca188328c06f8e3541eff7ccb`
and its historical helper/boot pins are not changed or treated as approval for
these images. No successor, deployment or physical scope is requested here.


## Final validation and handoff — 2026-11-05 UTC

| Gate/check | Actual result |
|---|---|
| Registered collector |16 tests PASS, fake clocks/UART only|
| Registered target-function radio/owner |3 tests PASS;87 SDK6 assertions; SDK5/production variants and original-predicate negative control|
| GS117 console/authorization |136 tests PASS|
| USB awake profile |4 tests PASS|
| Framework |55 tests PASS|
| Traceability/mapping |236 feature rows/288 modules/28 physical cases consistent;22 mapping tests PASS; not exhaustive coverage or physical PASS|
| ASan/UBSan radio/owner probe |87 assertions PASS, compile/run0, leak detection on|
| C3/S3 production and TEST_ONLY builds |4/4 PASS, IDF6.0.3; compiled/packaged only|
| `validation-hub` | **FAIL**: 53/56 stages PASS; 0 verified same-source receipts reused |
| `validation-contract` | **FAIL**: 48/50 stages PASS; 40 verified same-source receipts reused |
| `validation-node` | **FAIL**: 30/32 stages PASS; 25 verified same-source receipts reused |

All three final component reports confirm `source_unchanged=true` and final
fingerprint `7e77cc8bf7edd96f910944685e06ddae952188c948300ba0c29dd7b26f51a183`.
Hub stages were executed; contract/Node reuse explicitly verifies the actual
logs/artifacts/profile before accepting prior passed stages. Receipt reuse is
not another execution or new unique assertion count. Final report paths:
* `code/evidence/validation_framework/hub-1793899788696985569/report.json`
* `code/evidence/validation_framework/contract-1793900925874034015/report.json`
* `code/evidence/validation_framework/node-1793900989025184169/report.json`

Remaining mandatory failures are retained, not waived: fixture suite17/18 fails
its stale `assertNotIn('GS_HIL_COMMISSIONING', build_script)` even though the
unchanged builder explicitly forces it OFF; Hub migration fails `clean migration
commits`; P0's26 scenario assertions/real Chromium check complete but required
`product_status=PARTIAL` makes the gate FAIL despite subprocess exit0. These
unchanged-source/previously documented failures are outside this diagnostic
correction; no full software/product/release PASS is asserted.

Final affected checks also PASS: board-stack E2E10 cases, feature boundaries133,
C++1532, GS114 ACK trace36, GS1501500, GS401320, Wi-Fi77, GS40 bootstrap91,
rejoin proof/replay, segmented outbox runtime, storage correctness and its
sanitizer, recovery projections, CloudSync security/unit9/simulation18/mTLS,
backend/HTTPS contracts and GS178 Node-to-caregiver41 checks. These are host
software tests, not physical sensing/RF/Android-phone qualification. Full release
gates/extended qualification are NOT_RUN, deferred for an actual release scope.

Initial provisional Node campaign was source-changed and therefore FAIL/stale;
its fixture failure, ACK/GS150/HIL-integrity/P0/GS178 timeouts and obsolete
USB-cleanup literal failure remain preserved. A partial Hub campaign was stopped
at the test-source correction checkpoint, with its logs retained. Final frozen
campaigns contain no timeouts; the ACK/GS150/integrity/GS178 checks passed without
product-semantic changes. No provisional report is reused as final PASS.

Integrity verification:97 historical authorization/audit files and51 original
session134 evidence files retain their exact hashes; original v18 retains its
7cd38e60... identity; all79 pre-existing untracked status entries are preserved.
No COM/USB/device operation, bootstrap, reset, firmware deployment/readback/erase,
network window/configuration, authorization activation/disposition or motion
injection occurred. #11897 remains SAFETY_LATCHED1/1; #11886 unchanged.

Canonical worktree/branch unchanged, starting local/remote
`113d45d09f7ae258a88bcdd3a14b1272fbb4dd62`; preflight PASS/context2026-10-28.001.
Only the listed diagnostic source/tests/registry/traceability and canonical
evidence/status documents are included in delivery. Normal commit/push and
actual origin equality are verified separately after the commit; no historical
worktree, private authorization, key or fixture receipt is committed.

Next exact engineering action: review the pinned future diagnostic proposal
and its source/artifact/procedure/receipt prerequisites. No new hardware
entitlement is requested or created in this task. Radio root cause and watchdog
causality remain NOT_PROVEN; installed firmware unchanged, receipts STALE,
TC001_READY NO, TC0010/5. GS117 remains Highest/In Progress.
