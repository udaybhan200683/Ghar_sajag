# GS-117 diagnostic deployment readiness review — 2026-11-05

## Decision

**Recommendation: CONDITIONAL GO to prepare a new, separately authorized diagnostic scope. NO-GO for image installation or physical execution now.**

The diagnostic source and copied artifacts are internally consistent and compile-only validation passed. A future operation is not ready: the only hardware entitlement, GS-117#11897, is `SAFETY_LATCHED` at 1/1; the installed-image receipts are stale; candidate-specific deployment and rollback qualification are absent; and the proposed 90-second window cannot guarantee C3/S3 channel overlap. A negative S3 observation would also remain ambiguous without receive-callback/queue-drop evidence.

No approval or entitlement is requested or activated by this review.

## Baseline and scope

- GS-117 remains **Highest / In Progress**. TC-001 is **0/5** and `TC001_READY=NO`.
- Canonical worktree: `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`.
- HEAD and `origin/feature/r1-commercial-baseline`: `f0842403188c26ae980a92309aa7d04f718add65`.
- Context preflight at the reviewed implementation checkpoint: PASS, context `2026-10-28.001`.
- Current tracked worktree is clean. All 79 pre-existing untracked status entries match the saved pre-delivery inventory and remain untouched.
- #11897 is `SAFETY_LATCHED`, 1/1 used; #11886 and all historical authorization/evidence ledgers remain preserved. No hardware, serial, reset, bootstrap, flash, readback, network, or authorization operation occurred in this review.

## Diagnostic implementation review

Reviewed committed source, registered tests, and the private final build/report files identified in [GS117 diagnostic corrections](GS117_DIAGNOSTIC_CORRECTIONS_20261105.md).

| Capability | Review result | Limit |
|---|---|---|
| 90-second observation | One monotonic deadline begins after the separately permitted bootstrap and bounds collection, GET_STATE, and final sampling. The unconditional extra 10-second drain is removed. Cleanup/evidence finalization is separate and does no further reads. | A broken OS serial driver that ignores its timeout cannot be forcibly interrupted by Python; late data is rejected and reported on return. |
| C3 send stage | TEST_ONLY owner-side record distinguishes fragmentation/local error, peer-add, immediate `esp_now_send`, positive/negative callback, timeout, channel readback, numeric error and elapsed time. | ESP-NOW callback has no application transaction ID. Same-peer callback evidence is explicitly best-effort and can remain ambiguous after a timeout. No callback logging was added. |
| S3 channel/readiness | TEST_ONLY startup records ESP-NOW readiness and owner-ready STA channel/readback. A dequeued and authenticated RejoinHello records RX channel and the `HubSecurityLink::accept` result. | No receive log is emitted inside the S3 Wi-Fi callback. If no owner record follows, the evidence cannot distinguish no RF receive from callback rejection, queue loss, or loss before owner processing. |
| Watchdog evidence | Bounded filter retains TWDT headings, overdue task/CPU/current-task and backtrace lines, plus separate host-arrival and target-uptime/boot markers, redaction and truncation/drop counts. | Previously filtered session-134 lines cannot be recovered; host arrival time does not synchronize device clocks. |
| S3 peer result | The uninstalled-source `esp_err_t` owner comparison now uses `!= ESP_OK`; caller-level existing-peer/success/failure tests include an original-predicate negative control. | This was not present in the session-134 installed ELF and is not its cause. |
| Production isolation | C3 send instrumentation is gated to the existing diagnostic `GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE` profile. Marker checks found diagnostics in TEST_ONLY images and absent in production images. Production S3 effective cache checks all restricted options OFF and no TEST_ONLY root. | This review did not build, install, or physically qualify either profile. |

Historical offline validation remains: collector 16 PASS; radio 3 tests/87 assertions PASS; GS-117 console/authorization 136 PASS; USB profile 4 PASS; framework 55 PASS; mapping 22 PASS; ASan/UBSan 87 assertions PASS; paired target builds 4/4 PASS. These are prior results, not tests newly run for this review. Session-134 radio root cause and watchdog causality remain **NOT_PROVEN**.

## Artifact identity and build evidence

Private retained directory: `~/.local/state/ghar-sajag/gs117-diagnostic-corrections-20261105T153600Z/`. Recomputed SHA-256 for each retained BIN/ELF matched `target-final-report.json`. The S3 package checks report that the paired C3 image is embedded; image-info checks exit 0, and both BINs fit the generated build's application slots.

| Profile / target | Version | BIN bytes / generated slot | BIN SHA-256 | ELF SHA-256 |
|---|---|---:|---|---|
| Diagnostic C3 | `113d45d-gs117d-bf0ea8a3` | 966,832 / 1,966,080 | `8cca8460fe5fab1fed547026023cee7f6038b6c150ec522969be2336d1f24b38` | `a11eef6637cdd592fb4dcf5c63db4f70e5b86cca7861826b18d995d06d0173cb` |
| Diagnostic S3 | `113d45d-gs117d-bf0ea8a3` | 2,311,904 / 4,194,304 | `d08f70081b750b6cc1bfbd1bf95d09da8d3741f3238629dcb7949b78a572c679` | `b08ef2ea3ba633a2ed000b31c328c30e8013abefa04eb6c53394b4593fc704f0` |
| Production C3 comparison | `113d45d-gs117p-bf0ea8a3` | 944,272 / 1,966,080 | `7968668328b1900c05439a47cd20ef1b96449e0d12a0d99229622d7a9c5e7c28` | `53556766ae4e690d51b8db8c0f7129eabb618a59b1b2f8680e04cff2adc3f446` |
| Production S3 comparison | `113d45d-gs117p-bf0ea8a3` | 2,201,536 / 4,194,304 | `e70eee864dd985d30c9cc997de223e6b361077c071a3ac6df605a7ed225e400d` | `dd9f8211eb18c39b5bb47efce5dc7054fda441a08311b3ae292edbbd2c12c30a` |

ESP-IDF 6.0.3 builds report source HEAD `113d45d09f7ae258a88bcdd3a14b1272fbb4dd62` and build-start fingerprint `bf0ea8a367681f99646b69e5640476b4ab6961d4a84414763abc3ac4151cb0a2`. The final-source reconciliation confirms both target adapter hashes equal the source at `f0842403188c26ae980a92309aa7d04f718add65`; only host collector accounting changed after target compilation. Thus target inputs reconcile by exact source and image hashes, but the build version string is not the final commit and must not be represented as such.

The diagnostic C3 uses `GS_HIL_CONTROL=ON`, with HIL build and physical wake OFF. Diagnostic S3 uses the existing TEST_ONLY CloudSync/UART profile, `GS_HIL_COMMISSIONING=ON`, HIL build/control OFF, and the existing public trust-root DER. This is a TEST_ONLY candidate, not a production image. The production comparison profile has TEST_ONLY/HIL/commissioning options OFF and no test trust root.

## Deployment, image receipts, and rollback gates

The currently installed S3 remains the older `8acab96-dirty`, ELF prefix `7584a1f80`; its receipts are **STALE**. Historical records include bootloader SHA-256 `ae304441aaaad2b52765d48f4b37752f2ab26a65a480f5f1f9586cd54ebe1580`, but installed automatic application rollback capability is **not proven**. The new candidate's generated sdkconfig requests application rollback; that does not prove the installed bootloader implements it.

Before any future write, the separately authorized process must use the existing trusted receipt/readback mechanism to establish, for the exact fixture, current C3/S3 identity and running images, bootloader identity, partition-table/OTA slot layout, active selector and preserved state. Current build slot sizes do not prove compatibility with the installed partition map or identify a safe inactive slot.

The previous v18 procedure/hash/helper and #11897 consent pin different files/images and are consumed/latched; they cannot authorize these candidates. The new procedure must pin the exact diagnostic BIN/ELF hashes, source/configuration, current helper and deployment tool, fixture, slot/offset, operation limits, evidence capture and cleanup. No candidate-specific install-and-restore receipt exists. Historical application-only installation/manual restoration does not prove this image's compatibility or automatic rollback. GS-D029's automatic FOTA application rollback requirement remains unchanged; no development-only manual-recovery exception is approved. Prove the installed bootloader's rollback compatibility and candidate restore behavior under an approved plan before deployment; do not update a bootloader or OTA selector under this review.

## Observation effectiveness

`IndiaWifiChannelDiscovery` scans channels 1–13 and advances when the existing rejoin scheduler sends a Hello. The existing retry policy reaches approximately 60 seconds between saturated attempts. Session 134 itself observed channels 3 and 4 about 60.16 seconds apart. Therefore a steady-state 90-second observation may see only one or two arbitrary channels; it cannot guarantee that C3's actual channel overlaps the independently observed S3 channel.

The new C3 record can classify its local failure stage even without overlap. A useful receiver-side conclusion requires a same-channel send opportunity and positive S3 owner-side receive/authentication evidence. If no overlap occurs, the result must be `INCONCLUSIVE_NO_OVERLAP`, not a radio root cause. Even with overlap, absence of S3 owner evidence remains ambiguous because the TEST_ONLY callback has no explicit arrival/queue-drop counters. For the stated goal of distinguishing an S3 receive-path failure, this is a remaining diagnostic-readiness gate: add bounded S3 callback arrival/channel/source and queue-enqueue/drop counters, emitted later by the owner task (never logged inside the callback), and offline-test them; or explicitly scope the future observation so that missing owner evidence is reported as inconclusive and does not claim a root cause. Any added instrumentation creates new artifact hashes.

Do not change channel selection, retry timing, authentication or reset behavior implicitly. A longer observation, explicit C3 restart, altered channel opportunity, or added callback counters changes the proposed procedure/artifact and requires a reviewed scope and approval before execution.

## Remaining aggregate validation gates

Final reports are source-unchanged and remain FAIL: Node 30/32, Hub 53/56, Contract 48/50.

| Failure | Evidence and classification | Blocks isolated diagnostic? | Release/product effect and next owner action |
|---|---|---|---|
| Fixture assertion | `test_s3_option_is_opt_in_and_legacy_broad_hil_stays_rejected` asserts the string `GS_HIL_COMMISSIONING` is absent from the production builder, while the builder explicitly passes it as OFF and `verify_s3_production_profile()` checks the effective CMake cache and empty TEST_ONLY root. Effective production outputs report restricted markers absent. **TEST_INFRA_ONLY**; preserve and correct the assertion to test explicit OFF/effective profile, not remove the guard. | No. Candidate profile is separately TEST_ONLY and independently pinned. | Keeps all three current aggregate reports FAIL. GS-116/GS-130 own focused test correction and rerun before a green aggregate release result. |
| Hub clean migration | `make hub-journal-migration-host-test` fails `clean migration commits` in `hub_journal_migration_validation.cpp`. R1 supports fresh install on the current format; arbitrary migration from abandoned development-era formats is post-R1 unless it blocks supported fresh install (`R1_RELEASE_CONTRACT.md`). No evidence here shows fresh install is blocked. **DEFER_POST_R1** for product behavior; do not silently waive the still-registered failing gate. | No. | Current `validation-hub` remains FAIL. GS-116/GS-173 must explicitly reconcile the mandatory registered stage with the release contract, or retain/fix it if they establish it is in-scope. |
| P0 product status PARTIAL | All 26 scenario checks and the browser check pass, but `product_vertical_status=PARTIAL`, physical qualification `NOT_RUN`, and report gap `GS-148: production Hub TLS/credential authenticator and enrollment-generation registry binding are not configured; local test credential only`. The fixture credential is translated by test middleware; production Hub trust and caregiver OIDC are not claimed. **R1_BLOCKER** for full product/release acceptance under the required P0 gate; owners GS-148/GS-76 with GS-130/GS-116/GS-173 gate tracking. | No for an isolated authorized radio diagnostic; yes for claiming full TC-001/product or release acceptance. | Complete the production identity/authentication binding and real physical caregiver-application acceptance. Subprocess exit 0 does not override `PARTIAL`. |

The aggregate gate counts and failure logs are retained at `code/evidence/validation_framework/{node-1793900989025184169,hub-1793899788696985569,contract-1793900925874034015}/`. These current failures remain visible; no gate was rerun or waived here.

## Authorization and exact next gates

No physical operation may proceed under #11897: it is latched at 1/1. A future operation requires a new, separately owner-approved hardware entitlement and immutable procedure scope covering the exact diagnostic C3/S3 images and profile, fixture, current serial helper/tool hashes, fresh pre-install receipt process, application-only installation/slot, proven recovery/rollback, bounded observation and cleanup. Any longer timing, explicit C3 reset or altered channel strategy must be explicit in that scope. Do not change #11886/#11897 or rely on the five-day network authorization for hardware rights.

Before execution, close these conditions in order:

1. Resolve the S3 negative-receive ambiguity: add/test bounded callback/queue outcome evidence for a decisive RCA, or explicitly accept an inconclusive negative result in the future scope.
2. Define an observation outcome that requires same-channel overlap for radio conclusions and records no-overlap as inconclusive; obtain approval for any needed timing/reset change.
3. Pin a candidate-specific deployment/restore procedure and resolve installed bootloader rollback compatibility under GS-D029.
4. Obtain fresh authorized C3/S3, bootloader, partition, selector and image receipts before selecting/writing an application slot.
5. Obtain new owner authorization for the exact artifact/procedure/observation and one bounded hardware attempt.

The fixture-test, migration and P0 aggregate gates remain separately tracked; none is silently promoted to PASS. The P0 production-authentication and physical-acceptance gaps still block product acceptance.

## Review execution record

Read-only inspection and local SHA-256 recomputation of the retained artifacts and committed source were performed. Existing source/build/test reports were reviewed; no tests, build, readback or hardware operation were run for this review. No source, test, authorization, firmware or private evidence was changed. GS-117 remains Highest / In Progress; installed firmware is unchanged, receipts STALE, `TC001_READY=NO`, TC-001 0/5. Session-134 radio root cause and watchdog causality remain **NOT_PROVEN**.
