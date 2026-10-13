# GS-114 C8 physical execution

## Repaired-image physical run 01 — 2026-10-13 16:17–16:32 UTC

The canonical local and remote HEAD matched `72a223fc3b290c01c9f93fbb90db83d87601ad54`; context preflight passed. Stable by-id ports had exchanged ttyACM numbers. Direct ROM probes verified the authorized C3 (`14:63:93:c5:d1:58`, 4 MiB) and S3 (`7c:4f:ad:b7:2a:20`, 16 MiB; 8 MiB PSRAM profile). The operator's USB-only supply and AM312 3.3 V/GND/GPIO4 arrangement remained the authorized setup. No other serial owner was present. The ignored installer guard was corrected to resolve stable by-id targets and reject occupied or non-ttyACM links; it no longer assumes fixed ttyACM numbering. All nine repair-manifest hashes and partition/profile bounds were rechecked before writing.

Using the already authorized disposable R&D scope, the S3 was erased, written and `verify-flash` checked at 16:17:42–16:18:59 UTC; the C3 followed at 16:19:00–16:19:08 UTC. Both installer runs exited zero. The installed C3 application SHA-256 was `89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`; S3 was `c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`. The S3 commissioning-only profile retained two 4 MiB OTA slots, `gs_outbox`, `gs_state`, and 16 MiB flash/8 MiB PSRAM. Installer transcripts and credential-bearing raw captures remain ignored under `code/build/gs114_clean_install/`; [C3 redacted log](repair_run01_c3_redacted.log) and [S3 redacted log](repair_run01_s3_redacted.log) are preserved here. Opening the capture caused setup resets before measurement; there was no observed reset afterward. Neither eFuses nor security settings were changed.

Both devices booted. The supported `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` flow freshly commissioned exact device `c3-146393c5d158` as logical `gs114-c8`; the Hub logged authenticated rejoin session 1 at 16:19:26.333 UTC. The Node logged PIR ready at 16:19:36, then `BAT_SLEEP_DECISION eligible=1` and `BAT_SLEEP_ENTER gpio4=1 timer=1`. The authenticated Hub NodeHealth at 16:24:25 reported 10 light-sleep entries and 10 timer wakes, zero GPIO wakes, no retained event. This proves the Node remained operational and could restore its radio to transmit authenticated health.

The operator performed one real AM312 motion episode for P2 and replied DONE. At 16:26:55.880 and 16:26:56.081 UTC, the Hub accepted the **same** exact EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1` twice, both `ack=0` (`AckClass::Durable`) with `ESP_OK` send. At 16:31:55, authenticated NodeHealth showed `gpio_wakes=1`, `sleep_entries=26`, `timer_wakes=25`, `retained=0`. This is positive physical GPIO wake, authenticated PIR transport and durable ACK evidence. It does not alone prove the exact C3 ACK retirement or one authoritative logical effect. No RPF error appeared, and the successful event confirms admission was open, but this image emits no `RPF00` success record, so the exact first-retirement-report reconciliation remains unproven directly.

The C3 native USB Serial/JTAG reader emitted no bytes after its first light-sleep entry, including after a queued `GET_STATE`, while authenticated radio health/events continued. ESP-IDF 6.0.3's USB Serial/JTAG documentation warns that light sleep can interrupt host enumeration. The continuous Node UART ordering and Hub counter snapshots required by the test plan therefore are unavailable. **P1/P2 remain BLOCKED on observer completeness, P3–P9 remain NOT_RUN/BLOCKED; no physical PASS is claimed.** Capture was closed at 16:32:21 without reopening either port. This is an observation failure; the live C3 did not show a runtime stall.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md`; `DECISION_IDS=GS-D020`; `TASK_SCOPE=GS-114 physical observer and RPF07 retest`; `OUT_OF_SCOPE=CloudSync, storage redesign, C9–C11`. A commissioning-profile-only read-only S3 diagnostic was added to log authenticated NodeHealth detail, successful `RPF00`, retirement ACK send result, and authoritative per-key outbox lookup. It changes no protocol, eFuse, durable admission or production profile. Retest requires source-matched target build/hash/verify and a justified fresh R&D installation. If post-sleep Node UART is still required literally, an independent GPIO/UART measurement interface is an external fixture prerequisite.

The paired diagnostic build subsequently passed with source fingerprint `1eec58fa1f77902c589e416db661b793d842320e33b1acc8073d677c460d1879`, ESP-IDF 6.0.3, C3 app SHA-256 `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3 app SHA-256 `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. All nine exact artifacts passed independent manifest hash checks; S3 remains commissioning ON, broad HIL OFF, two 4 MiB OTA slots, `gs_outbox`/`gs_state` and 16 MiB/8 MiB PSRAM. Focused Hub replay/checkpoint host regression, 19 traceability framework tests and `git diff --check` passed. This new pair has **not** yet been installed; the boards still carry the run-01 repair images at this checkpoint.

## Resume checkpoint — 2026-10-13 UTC

GS-114 Jira comment 10800 and the pause handoff were reconciled against the
canonical branch. Local and remote HEAD remained
`93935e345a29e3b119f460fda5e9294477b6f798` at resume; all scoped dirty
source/evidence and pre-existing untracked data were preserved. Context
preflight PASS. The old S3 esptool process is gone and no serial reader owns a
port, but **neither authorized `/dev/ttyACM0` nor `/dev/ttyACM1` currently
exists in WSL**. No serial port was opened and no repair erase, write, reset,
recommissioning or P1–P4 stimulus was attempted on resume. Operator USB
reattachment and renewed power/wiring confirmation are pending.

All nine selected repair artifacts exist and their byte lengths and SHA-256
match [the corrected repair manifest](repair_manifest.json) and actual build
receipt. The manifest's previously copied S3 profile fields were updated to
the verified repair receipt: S3 app 1,889,280 bytes and embedded C3 SHA-256
`89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`.
The fixture remains the commissioning-enabled 16 MiB/8 MiB PSRAM profile with
`gs_outbox`/`gs_state`. `GS114_REPAIR_MANIFEST_CHECK=PASS`. This is offline
artifact evidence; installed boards still run the first failed image.

Focused `hub-runtime-checkpoint-host-test`, `hub-fresh-install-host-test`,
`feature-coverage-test` and the paired target build PASS. The completed
`make validation-hub` receipt at
`code/evidence/validation_framework/hub-1791904599768894359/report.json`
records 38/40 stages PASS, source unchanged, exit 2: known journal migration
failure (`clean migration commits`) and product P0 `PARTIAL`; checkpoint,
fresh-install, board-stack, storage correctness and sanitizers PASS. The
completed `make validation-contract` receipt at
`code/evidence/validation_framework/contract-1791905308298399721/report.json`
records 33/34 stages PASS, source unchanged, exit 2: only product P0 `PARTIAL`;
the contracts, board-stack, fresh-install and affected Hub cases PASS. Both
receipts use source fingerprint
`51484c36451d1502c75e4f4ba2a101b1144b416407bfbe6adbc79695e391f3bc`
and classify physical evidence NOT_RUN. These known broader gates are not
reported as PASS. The initial interrupted Hub invocation remains recorded
as interrupted in the pause checkpoint below; this completed rerun supersedes
its incomplete gate status.

## Pause/resume handoff — 2026-10-13 UTC

The operator requested a pause before the session limit. Physical execution is
stopped at the first-failure repair checkpoint: original clean images are still
on the C3/S3 boards; repaired images are built and hash-verified but **have not
been flashed**. Phase A is FAIL at fresh-install S3 `RPF07`; P1–P9 have no
physical PASS. No repeat erase or flash for the repair was attempted.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, pre-handoff local HEAD
`93935e345a29e3b119f460fda5e9294477b6f798`; remote matched at task
startup. Context preflight PASS `2026-10-13.001`. This report, the four scoped
Hub source/test files, and the validation traceability CSV were modified for
this checkpoint; new redacted logs, verification logs and repair manifest are
being committed. Nine pre-existing unrelated untracked entries and ignored
private raw logs/builds remain untouched. No reset/rebase/merge/stash/clean.

Repair target build: ESP-IDF 6.0.3, C3 app SHA-256
`89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`,
S3 app SHA-256
`c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`.
[Repair manifest](repair_manifest.json) records bootloader, partition, OTA,
outbox, image and build-receipt hashes. The S3 build uses its 16 MiB
commissioning profile with `gs_outbox`/`gs_state`, 4 MiB OTA slots and 8 MiB
PSRAM; C3 is 4 MiB. At-build source fingerprint
`ee9fe393cfed897ef392547dc92cc3b5bd85d9e8e7f78f124505d5a80ab2a249`;
the only later source-fingerprint input change was registering the new test in
`MASTER_TRACEABILITY.csv`, not a firmware source edit.

`make hub-runtime-checkpoint-host-test`, `make hub-fresh-install-host-test`,
`make feature-coverage-test`, target paired fixture build and `git diff --check`
PASS. `make validation-hub` was interrupted for this requested pause after the
known `hub-journal-migration-host-test` failure was reproduced; no full gate
PASS is claimed. Contract and physical repair retest NOT_RUN. The attempted
read-only S3 `flash-id` re-probe hung in uninterruptible kernel I/O before an
identity result; its parent and the validation gate were terminated. The C3
re-probe was not reached. S3 boot/serial state is therefore unknown at pause.

Resume at USB/process inspection, then independently reidentify both exact
authorized chips/ports and verify repair image/profile hashes before any
further erase/write. If safe, perform one controlled clean repair installation,
verify flash, recommission via `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE`,
capture independent timestamped logs, and physically retest admission/RPF00
and durable authenticated transaction. Start P1–P4 only after stable Phase A;
retain the test plan's separate P5–P9 operator actions and prerequisites.
Never infer a physical PASS from these software results.

2026-10-13 UTC. Current checkpoint: Phase A clean installation and authenticated commissioning were executed; first Hub replay-fence reconciliation **FAILED**, and admission closed. A targeted source repair passed focused host validation; rebuilt target images and physical retest are pending. P1–P9 are not qualified.

## Phase A first physical attempt, 11:58–12:05 UTC

The operator confirmed USB-only power, no competing supply, and AM312 VCC at 3.3 V/GND shared/OUT to C3 GPIO4. Stable USB interfaces matched COM4 (`/dev/ttyACM0`) and COM9 (`/dev/ttyACM1`). Direct ROM probes before the first erase identified C3 revision 0.4, MAC `14:63:93:c5:d1:58`, embedded 4 MiB XMC flash; S3 revision 0.2, MAC `7c:4f:ad:b7:2a:20`, 16 MiB flash and reported 8 MiB PSRAM. Both reported Secure Boot and flash encryption disabled. No eFuse operation occurred. Probe outputs are retained in private ignored storage.

The first, hash-checked manifest was installed only on those identified boards. Both complete flashes were erased, written and `esptool verify-flash`-verified, including S3's empty 4 MiB `gs_outbox` image. C3 app SHA-256 `ad173384e827614bcbb62c0deac60b5d866dd144088528523c5711e5c2409e43`; S3 app SHA-256 `8c53b999c001095030c7f150854b9637404b666364470131f1511cffdc34a4f7`. [C3 verification](install_c3_verify.log) and [S3 verification](install_s3_verify.log) are retained. Setup resets on opening the UARTs occurred before any qualification measurement; they are not claimed as stable observation.

Both images booted. The first host bridge sent LF-only S3 commands that produced no usable fixture response; a bounded `FIXTURE_STATUS` probe with CR framing returned `state=idle`. The bridge was corrected in private ignored test tooling to pace S3 UART bytes and terminate with CR. No reflash was used for this fixture-side correction. The corrected setup accepted `GET_TEST_QR` on C3 and `COMMISSION_EXPECTED_NODE` on S3, then the Hub logged exact authenticated rejoin of `c3-146393c5d158`, logical `gs114-c8`, session 2 at 12:04:37.803 UTC. S3 `FIXTURE_STATUS` returned `authenticated_rejoin`; C3 started its runtime and reported PIR ready on GPIO4. Credentials remain only in ignored private raw logs; the [C3](setup02_first_rpf07_c3_redacted.log) and [S3](setup02_first_rpf07_s3_redacted.log) evidence copies redact them.

At 12:04:48.028 UTC, before any qualified PIR event, the S3 logged `RPF07 SELECTED_CHECKPOINT_MISSING path=PREPARED admission=CLOSED report_ack=withheld`. Capture stopped immediately. The authenticated report had advanced the NVS selected checkpoint, while `HubDurabilityOwner::recovery_state()` still held the initial boot snapshot with no report reference. `HubRuntime::reconcile_replay_fence()` reloaded the new selection for publication but its binding check compared the old owner cache. This is a fresh-install runtime defect, not a residual from erased experimental state. No EventKey-to-Durable-ACK physical PASS exists.

`BUG_CLASSIFICATION=R1_BLOCKER`; `REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/product/CANONICAL_REQUIREMENTS_INDEX.md (durable-before-ACK and replay-fence invariants)`; `DECISION_IDS=GS-D020; GS-D030`; `TASK_SCOPE=GS-114 Phase A targeted durability repair`; `OUT_OF_SCOPE=storage redesign, CloudSync, C9-C11`.

The scoped repair refreshes the owner cache from the authenticated selected durable store during runtime fence reconciliation, checks the store/epoch binding, and closes admission if refresh fails. A new production-code host regression reproduces fresh genesis → first authenticated retirement report → selected checkpoint advance → fence bind, plus a failed-refresh negative case. `make hub-runtime-checkpoint-host-test` and `make hub-fresh-install-host-test` passed with `TMPDIR=code/build/gs114_tmp` after the default 1.9 GiB `/tmp` tmpfs proved full. This is software evidence only; the physical retest is pending.

Historical preparation source: `5ee96fd24b4a82b2a11b928cb40f2638eaee9616`, canonical `feature/r1-commercial-baseline`; actual GitHub HEAD matched at that preparation startup. Context preflight PASS `2026-10-13.001`.

This execution follows GS-114 10732, which supersedes old experimental-state preservation for the identified disposable R&D C3/S3 pair. Prior failure logs and STOP reports are preserved.

Verified current-source fingerprint: `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`; build receipt records `774da5c2ee8073c535df2fe56ecdbf548c16ebf0` with the Option A working-source implementation. Both current app hashes match that receipt. ESP-IDF 6.0.3 and esptool 5.4.0 activated. No source changes or repeat GS-148 fault campaign.

See [preparation manifest](preparation_manifest.json) for first-install bootloader/table/otadata/app/outbox hashes, offsets, profiles and exact command argument arrays, and [USB inventory](usb_inventory.txt). Artifact verification and compiled partition decode PASS. Fresh 4 MiB empty LittleFS generated with the component-pinned littlefs-python 0.15.0; host mount with target read/program/cache configuration and empty directory check PASS. A preliminary host validation invocation used an incorrect UserContext constructor and failed; corrected API invocation passed without changing the generated image.

Prior `USB_UART_CHIP_RESET` and replay-fence admission closure remain UNRESOLVED HISTORICAL REGRESSIONS. Clean installation cannot qualify recovery of that discarded old state.

## Execution scope

Owning Jira GS-114; affected C3/S3 fixture setup, USB capture, authenticated commissioning, Hub replay-fence runtime, GPIO4 light sleep, EventKey/ACK/durability contracts. Existing GS-150 and GS-148 software receipts are reused after exact source/artifact checks. The scoped Hub runtime owner-cache repair changes no protocol, security, persistent format or app/backend behavior. Physical tests require actual operator stimuli. Full release/current/GS-148 fault campaigns NOT_RUN; prior mandatory migration FAIL and product P0 PARTIAL remain.

## Case results

| Case | Disposition | Evidence / blocker |
|---|---|---|
| Phase A | PARTIAL; repaired run 01 durable admission observed | Clean repair install/verify and fresh authenticated commissioning passed; direct `RPF00` first-report and complete observer proof pending |
| P1 | BLOCKED; physical partial evidence | C3 sleep entry and authenticated health proved 10/10 timer wakes, then 25 more; post-sleep C3 USB UART and Hub state snapshots unavailable |
| P2 | BLOCKED; physical partial evidence | Operator real motion, one authenticated GPIO wake and exact PIR EventKey with Durable ACK observed; direct C3 retirement and one-effect ledger pending |
| P3 | BLOCKED | Requires real held-HIGH/LOW episode and continuous level/sleep evidence |
| P4 | BLOCKED | Requires exact EventKey, authenticated durable commit, ACK class and retirement |
| P5 | BLOCKED | Requires separate Hub-only outage/return approval and operator stimulus |
| P6 | BLOCKED | Requires separate Hub-only reboot approval |
| P7 | BLOCKED | Requires P6 then first real post-reboot motion |
| P8 | BLOCKED | Controlled postcommit ACK-loss fixture and authoritative per-key ledger unavailable/unproven |
| P9 ACK | BLOCKED | Requires P8 link fixture and observed continuous receive during successful MAC/pending ACK |
| P9 FOTA | BLOCKED | Current S3 broad HIL control OFF; matched signed C3 test/recovery images and supported trigger/recovery plan unproven |
| P10 | NOT_RUN | GS-149 owns quantitative acceptance; no instrument/current measurements |

Next action: install the hash-verified [commissioning-profile diagnostic pair](diagnostic_manifest.json) on the same reidentified and unoccupied R&D boards, recommission, observe direct `RPF00` and per-key evidence, then resume real P1–P9 actions. No GS-114 Done transition or C8 physical PASS.

## Validation and precise operator checkpoint

- `tools/context/ghar_sajag_context_preflight.sh`: PASS, exit 0, context `2026-10-13.001`, at startup and after documentation edits.
- Retained fixture app hash/size, exact embedded C3, current source fingerprint and S3 profile verification: PASS, exit 0. Both compiled partition tables decoded with IDF's `gen_esp32part.py`; OTA fit and outbox offsets checked. Build reuse only; target compilation was not repeated.
- `idf.py --version`: ESP-IDF v6.0.3, exit 0. Offline C3 `esptool image-info`: valid checksum/hash, C3/4 MB/DIO/80 MHz, ESP-IDF 6.0.3, exit 0. S3 independent image-info is retained in the matching build receipt.
- `littlefs-python create ... --fs-size=4194304 --block-size=4096 --name-max=64`: exit 0. Corrected host read-only image mount with target geometry: empty root directory, exit 0. S3 actual mount NOT_RUN.
- `make physical-hil-catalogue-test`: PASS, exit 0; 99 cases, 68 required and 40 conditional feature mappings checked, `device_access=NONE`.
- `python3 -m py_compile code/build/gs114_clean_install/prepare-20261013T111214Z/live_capture.py`: exit 0. This is an ignored session wrapper around existing `tools.hil.core.SerialCapture` and `FixtureLock`, not a new HIL framework or an executed capture. It requests DTR/RTS low before opening, keeps one reader per port, never automatically reopens a disconnected port, and stores credential-bearing raw commissioning output only under ignored private storage. Syntax check does not prove observation reliability.
- `git diff --check`: exit 0. The later scoped Hub firmware repair and its focused tests are recorded in the pause handoff above. Backend/PWA and release campaigns were not run. Prior GS-148 migration FAIL and product P0 PARTIAL remain independently recorded.

The owner subsequently supplied the exact board, power, wiring and Phase A erase/flash authorization. The first manifest's operations above were executed and verified. A repair retest must reidentify both exact chips/ports and verify new image hashes before another clean installation. Use only fresh private test credentials and `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE`, never the incompatible generic factory driver.

The S3 commissioning-only image accepts `FIXTURE_STATUS`, **not** `GET_STATE`, broad HIL, ACK-drop or FOTA controls. Canonical P1/P4 Hub-counter snapshots therefore require a verified compatible read-only observation path before complete acceptance; do not label unsupported commands or counter-only reasoning PASS. The current RPF diagnostic emits failure stages only; absence of RPF errors alone is not an observed `RPF00` success. Confirm healthy admission through authenticated durable transactions and capture the required fence proof before qualification. These instrumentation limits remain explicit; no acceptance criterion is waived.

## Subsequent measured work

GS-144 still needs owner acceptance of representative event/outage workload rates, selected battery/power-path usable capacity and reserve, minimum endurance and caregiver latency/reliability bounds. The 150–180 day goal remains aspirational; no measured battery-life claim. Its separate historical workload branch is a read-only provenance source and was not integrated or recreated.

GS-140/B0 requires a real identified instrument, range/burden/sample rate/uncertainty, voltage and measurement boundary. GS-41/42/141/43/44 own comparable B1–B4 BEFORE and GS-51 owns AFTER; current C3/S3 images are not interchangeable with the old `bb34f5e` baseline without a matched-profile decision. None was physically measured here. GS-149 P10 remains blocked by those inputs and GS-114 acceptance; GS-146 also needs GS-119, GS-46 and GS-69 accepted evidence. GS-115 decisions remain C9 REQUIRES_MEASUREMENT/product semantics, C10 MEASURE_ACTUAL_WRITES_FIRST, C11 POST_R1, C12 DEFERRED. No subsequent firmware implementation is approved by these statuses.
