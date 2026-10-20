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

Implementation commit `1043827858609a1212e403ddf4d4494e90c6165e` is pushed and source-tree matched. Host reconnect 77/77, onboarding 30/30 (normal and ASAN/UBSAN), caregiver runtime 9/9, app 34/34, validation framework 51/51 and mapping 22/22 passed. Final S3 rebuild and Android workflow `39437956269` rerun were pending at the quota-warning checkpoint; local browser was NOT_RUN for missing Chrome/Chromium, while CI's first attempt passed 3/4 browser tests and failed first-case DevTools startup. The linked handoff records exact recovery steps. GS-58 and GS-177 remain In Progress.
