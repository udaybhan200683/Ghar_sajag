# GS-117 physical access recovery — 2026-10-25

Current reference: [working pipeline preservation and startup runbook](#working-pipeline-preservation-and-startup-runbook--2026-10-26).
Earlier entries are dated historical checkpoints, not current blockers.

Source HEAD: `30af100d2d5c84b56c7bd7abc99be031cd075cc6`. Canonical branch and context preflight PASS; no tracked changes on entry.

Owning Jira: GS-117, with GS-68/GS-179 dependencies.
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=AGENTS.md physical evidence accuracy; existing GS117-TC001-01
DECISION_IDS=NONE (no product semantics change)
TASK_SCOPE=Recover existing native Windows serial observation; retain complete profile/boot/error evidence and allow an explicit fixed read-only S3 FIXTURE_STATUS query.
OUT_OF_SCOPE=Firmware writes, resets solely to regain WSL access, credential/ownership changes, event injection before readiness.

Affected component: existing TC-001 Windows helper and its already registered tests (GS117-TC001-SW-001, gs117-tc001-console). No Node/Hub/API protocol or firmware changes. New regressions cover complete long HIL profile lines, boot/error messages, secret redaction and explicit Boolean S3 status query. Existing console guards, wrong USB identity, CSRF, single-run, EventKey and APK-evidence checks remain included. Physical evidence uses existing owner authorization for exact COM4/COM10 reset-aware read-only queries, with DTR/RTS low. No release qualification claimed.

Windows interop and native helper List recovered without modifying services, sockets or OS configuration. Both expected VID:PID 303A:1001 USB serial identities match. First Observe returned C3 GET_STATE/HIL_OK from ota_1 in HIL_AWAKE_TEST_ONLY; runtime_live=0, sensing_live=0, retained=0, in_flight=0. S3 returned no matching lines. The original collector truncated the last power/profile fields and excluded product boot/error markers, which is the demonstrated tooling defect corrected here.

## Physical findings and demonstrated S3 gap

The helper captured the selected C3 ota_1 application repeatedly at session 99 with complete HIL_AWAKE_TEST_ONLY flags, physical_wake=0, stable free/min heap 197292/179820, and no retained/in-flight events. Startup image provenance is the prior byte-verified ota_1 write plus current running-slot evidence; no C3 write/restart was performed. Fresh command code is present in that verified candidate; it was not executed as a capability probe.

After silent S3 observations and a no-reset/no-stub ROM query that ended in USB write timeout, one owner-authorized reset-aware S3 boot was captured by the existing helper with Espressif HardReset, same open native USB stream, and no flash operation. It reported USB_UART_CHIP_RESET, loaded app offset 0x420000, project gs_r1_s3_hub version e9e610b, full product partition layout, then Hub security bootstrap failed closed. Startup is now proven, but HubRuntime/storage initialization is not. The source production identity branch requires protected production provisioning and returns false on an unprotected development board when all fixture flags are OFF; the installed image has commissioning/CloudSync OFF. The existing GS_HIL_COMMISSIONING TEST_ONLY profile is the supported development identity mechanism; production checks must stay intact.

Saved NVS metadata lists only gs68time, misc, nvs.net80211 and phy; no identity/Home/registry namespace was present in that backup. Values and protected keys were not printed.

BUG_CLASSIFICATION=TEST_INFRA_ONLY
TASK_SCOPE=Reuse the existing S3 full-product GS40 CloudSync+commissioning profile; initialize its native USB driver/VFS before its existing authenticated config receiver (the analogous GS-68 setup already exists). Reuse GS-168 issuer and GS-68 signed time; add only explicit exact-fixture authority persistence/identity support needed for this approved physical session. Default synthetic fixtures and production identity guards remain unchanged.
VALIDATION_PLAN=Existing registered TC001/GS168/GS40 security and fixture tests, affected Hub/contracts, target S3 build, physical signed-config/commissioning when preservation/security/network gates pass. No new runtime, database, issuer framework, Home or APK.

## Software/bootstrap preparation

Fixed the existing GS40 native USB receiver to install the interrupt driver and connect its VFS, reusing GS68 setup. Existing full product S3 build with GS40_TEST_ONLY_CLOUDSYNC=ON and GS_HIL_COMMISSIONING=ON completed: 2,274,768 bytes, SHA-256 1290e680f458882bbb82c9f8bc73d3cb1280b14b345df26cb25bb72c82793c9f. The root DER references the persistent owner-only GS117 config signer; native USB console selected. This candidate is not flashed.

Extended existing GS168 issuer with an explicit exact-fixture persistent authority. Default synthetic issuer rejects physical identities; physical fixture authority rejects synthetic and neighboring physical IDs. Protected CA bundle is no-follow, owner-only POSIX storage with explicit initialization, immutable existing CA reuse, certificate/key matching, validity/signature/CA checks and fail-closed partial-file recovery. Separate TLS, signed-time, authority-lease and envelope-signing keys were prepared in the existing owner-only ~/.config/ghar-sajag/gs117-tc001 directory. The TLS key is newly host-generated TEST_ONLY material for the existing encrypted RAM-import path, not an extracted/protected hardware DS key or production provisioning. No device credential was installed and no backend ownership was asserted.

Persistent client certificate SHA-256 aa0b1eff16547ad67a790d122bae1d88fd0e8040a50901ed841464d77a7f2732, client CA SHA-256 42d36b8e8a3bb60705d81a6987994e7e763c430dbd75868cd6f239101e7f47ea, generation 1. Public preparation status PREPARED_NOT_INSTALLED. No secrets in evidence.

The existing GS68 proof signer now accepts an injected RSA3072 fixture key, and the existing signed-time UDP carrier accepts an explicit fixed-port RFC1918 bind while remaining loopback by default and refusing wildcard/public addresses. Focused tests: TC001 23/23; GS168 13/13; identity/time mTLS/ownership/revocation and signed UDP 9/9; native S3 target build PASS. Existing GS179 runtime process test now ran against its random isolated PostgreSQL schemas: 5/5 PASS (previous skip resolved), including source-linked host event commit/retry, separate from physical acceptance.

Live Windows network: Airtel_Agrim, Private, 192.168.1.4/24, channel 6; old portproxy remains 192.168.1.7:443 -> 172.17.152.10:8444. Administrator token not elevated; no existing GS179 elevated watcher is registered. No firewall/route mutation performed. The fixture has no supplied Wi-Fi secret; the saved Windows credential was not extracted. Requested only the protected config file path asynchronously while independent work continues.

## Executable use and external prerequisites

Reuse `code/tools/local/GS117-TC001-Console.cmd`, localhost `http://127.0.0.1:18791`. Its physical readiness guards must remain blocked until the installed S3/current authenticated Home/epoch/Node/time/ingress and APK receipts are real. No second launcher, console, backend or APK was created.

The existing Windows helper supports `List` and `Observe` as before; `Observe` may explicitly request `query_s3_status: true`, `s3_boot_reset: true` (only under fixture reset authorization), and integer `observation_seconds` 10..60. `Bootstrap` reuses the same identified stream and existing GS40 crypto: read its public CONFIG_CHALLENGE JSON, call existing encode_config in the protected host parent, then write one stdin JSON with only encrypted_envelope_b64. The child enforces target nonce, wire framing, bounded sizes and 20-second challenge/response waits. Use a 45-second observation for Wi-Fi/time startup. Bootstrap was software-tested only and was not invoked on the old physical S3 profile. A regular Run does not reset or commission a board.

Protected material API: TestOnlyAuthority.for_gs117_fixture(path, initialize=True) creates only a missing owner-only CA bundle; later use omits initialize. An existing/partial/invalid root is never overwritten. TestOnlyIssuer receives that authority and the persistent physical registry. new_test_csr(..., gs117_fixture=True) accepts only the designated Hub. Synthetic defaults are unchanged. The SignedTimeService accepts the existing TestOnlySignedTimeFixture with an explicitly injected separate RSA3072 key. Its default bind remains loopback; a private fixed port requires explicit opt-in and approved networking.

The owner-only bootstrap-materials.json is public preparation metadata and explicitly says PREPARED_NOT_INSTALLED, wifi_secret_configured=false and backend_ownership_registered=false. No protected key contents belong in Git, browser output or logs. The new host-generated TLS credential is a TEST_ONLY RAM-import credential, not a hardware-protected DS claim. The physical TLS/commissioning proof and exact backend authority must be verified before real event admission.

Precise external input requested: only the path to the approved owner-only Airtel_Agrim Wi-Fi configuration (never its password in chat). No such input was found in the fixture package. Earlier owner instructions prohibit credential extraction, so the saved Windows profile secret was not retrieved. If the owner instead authorizes that narrowly scoped use explicitly, it must stay in protected memory/encrypted GS40 transport and never be logged.

Precise Windows action: an elevated invocation of the existing gs179-windows-lan-proxy.ps1 -Action Watch -LinuxScriptPath /home/udaybhan/projects/Ghar_sajag_r1/code/tools/local/gs179-laptop-server.sh, which re-detects trusted Private/Domain Wi-Fi and updates only GS179-owned forwarding/rules. The current Windows token is not elevated and the expected elevated watcher is absent. No UAC/security policy bypass or firewall mutation was performed in this continuation. Current read-only observation confirms Private Airtel_Agrim 192.168.1.8/24; the script must re-detect it at execution time. Physical Hub ingress/time endpoints must also be explicitly configured through the existing runtime after verified device enrollment, with narrowly scoped networking and no exposure of TC001 control.

No additional C3 flash approval or commercial Home-transfer implementation is a prerequisite. Finish only the config-dependent S3 deployment/PoP association/real backend registration after those inputs and preservation checks; do not fabricate ownership records or use historical HOST_SIM data.

## Final source validation and preservation

Current matched-source reports use fingerprint aa64feefcb9712c280217dce4bd795267fdf0ac0fec82a2545376f1bce9e5041, entry HEAD 30af100d2d5c84b56c7bd7abc99be031cd075cc6 plus scoped working changes:

| Command | Result | Evidence |
|---|---|---|
| make validation-contract | FAIL: 47/48 stages PASS; required p0-full-product-e2e reports product_status=PARTIAL / physical=NOT_RUN | code/evidence/validation_framework/contract-1792931298186042738/report.json; source_unchanged=true |
| make validation-hub with verified contract receipts | FAIL: 53/55 stages PASS; existing clean journal migration failure and required P0 PARTIAL | code/evidence/validation_framework/hub-1792932147864292809/report.json; source_unchanged=true |
| make validation-backend with verified contract/Hub receipts | FAIL: 24/26 stages PASS; existing static.css_bytes 29576 >18432 in Python suite, plus required P0 PARTIAL | code/evidence/validation_framework/backend-1792932369202313930/report.json; source_unchanged=true |
| make validation-tooling | FAIL: general Python CSS budget failure; the later registry-count/traceability changes were revalidated in the matched-source gates | code/evidence/validation_framework/tooling-1792929325619605638/report.json |
| python -m unittest tests.python.test_gs117_tc001_console | 26/26 PASS, no hardware | registered gs117-tc001-console; matched-source contract/backend reports |
| GS168 persistent fixture issuer | 13/13 PASS | registered cloudsync-security-unit; 14/9/13/5 Python sub-suite counts |
| GS68/GS40 identity/time E2E | 9/9 PASS, real loopback TLS/UDP only | registered cloudsync-security-unit |
| GS179 runtime composition with protected local DSN and isolated schemas | 5/5 PASS, no skipped PostgreSQL runtime case | /tmp/gs117-runtime-isolated-postgres.log |
| GS116 framework | 51/51 PASS, old reduced suite counts rejected | /tmp/gs117-registry-correction.log |
| make feature-coverage-test | consistency PASS: 226 features, 285 modules, 27 physical cases; 22/22 tests | /tmp/gs117-recovery-feature-coverage.log |

The Python suite's one skip is the explicitly historical classic-ESP32 NVS reserve model under GS-D030; it is not a skipped S3 physical qualification. No complete product/release PASS is claimed. Initial Hub registration failed because old fixed counts expected 6 and 10 instead of the expanded 9 and 13; registration and its negative framework fixture were corrected, and current security stages PASS. Initial stale-source Hub and cancelled pre-correction contract runs are not acceptance receipts; matched-source reruns above supersede them. Physical TC001 remains NOT_RUN. No full release-gate-final was run for this development correction.

Ten fixture trust/config files were copied into the owner-only state backup directory ~/.local/state/ghar-sajag/gs117-tc001/fixture-trust-backup-20261025, verified byte-for-byte and mode 0600, and the CA reloaded from the backup with matching public fingerprint. No device private key was extracted. The initial 1290e680 S3 candidate was preserved there. Build review found its embedded Node asset SHA256 ff2f1ab29d032dc5649150e6dd2a7c820d0ec3f5be44639c21e3d84c262ead26 differs from the already-installed C3's 183417fd image. The exact installed C3 binary is staged at /tmp/gs117-s3-installed-c3-asset-mhw5hrnb/node_firmware.bin via the existing GS_NODE_FIRMWARE_ASSET mechanism. Rebuild S3 only from the committed source using that asset; do not deploy the initial 1290e680 candidate. No C3 rebuild/reflash is needed.

All local firmware assets, public/private historical backups, existing active caregiver services and unrelated untracked files are preserved. No destructive Git operation, whole-flash erase, partition rewrite, eFuse/security change, protected device-key extraction, Home/account recreation, historical event deletion or fake event insertion occurred. Git delivery uses the same canonical worktree and branch, normal commit/push and actual ls-remote verification. The exact delivery commit is recorded in the subsequent GS117 Jira comment and final task result.

## Committed-source final paired S3 candidate — supersedes initial 1290e680 build

Implementation commit 0af99da0451a1c4eb8cc8d5ea034efc51f3893b6 was pushed normally and matched actual origin/feature/r1-commercial-baseline. A clean tracked-source S3-only build from that commit now embeds the exact already-installed C3 image. No C3 source build or flash occurred.

- Project/version: gs_r1_s3_hub / 0af99da0451a-gs117-test; ESP-IDF 6.0.3.
- App: 2,270,336 bytes; full-file SHA256 59f9ffb80ce7f7d7af94af691f7dc7cdfe11fb39737835d08c29e44893bf1047.
- ELF SHA256: 1bb7879185c2a859c93ebdddf2f9a7134c9a11522fd9e1d79a2221e7155428f6. Espressif image-info reports valid image digest, ESP32-S3 chip ID9, 16MB/DIO/40MHz, revision range covering the known v0.2 board.
- Existing product partition bytes match the saved live readback prefix exactly; generated table SHA256 bb0066feee7368e621c6f0f0d7bfdf47cbc5bbbf4cfdd9eccab9525ad683f82a. Both 4MiB OTA slots, gs_outbox and gs_state remain unchanged. No partition write is required.
- Exact C3 app SHA256 183417fdd840ed9cce333e7b276beeaba83d085173f9cbe28589d617d874739f occurs once in the S3 image. The persistent fixture config-root public DER is also embedded.
- Profile: full product; commissioning and GS40 TEST_ONLY CloudSync ON; legacy HIL/control/diagnostic/fault/FOTA triggers OFF; native USB console; DS peripheral OFF only in the existing isolated software-key test profile. Production identity and transport guards are unchanged.
- Preserved ready app and reproducibility metadata: ~/.local/state/ghar-sajag/gs117-tc001/s3-ready-0af99da0451a/gs_r1_s3_hub.bin, sdkconfig, project_description.json, manifest.json and partition-layout-reference.bin, owner-only. The reference partition image is evidence, not permission to rewrite it.

The successful build uses the existing GS_NODE_FIRMWARE_ASSET environment override (needed during ESP-IDF's early component-requirement scan), not a second Node build. The earlier attempt with only -D encountered the existing missing-asset guard, was corrected using that supported override, and then reconfigured/built successfully. The initial candidate and older Node asset remain preserved. Only the 59f9ffb8 candidate is the current prepared artifact; the earlier public candidate JSON is historical build-step evidence.

This is BUILT/IMAGE_VERIFIED, not FLASHED/PHYSICALLY_ACCEPTED. The live S3 is still the previously observed e9e610b app failing security initialization. No firmware or credential installation was attempted with missing Wi-Fi input. Existing authorizations still apply; before any app write, recheck the exact current S3 identity, active/inactive slot, preserved protected state and recoverable app/selector backups using the existing approved mechanism. Never invoke the build output's full-flash recipe.

The follow-up commit changes only build/evidence/traceability metadata; production code is identical to the tested implementation commit. Final traceability check and context preflight PASS are required for delivery. Actual remote HEAD and Jira comment IDs are reported at completion.


## 2026-10-25 scoped Wi-Fi authorization, physical S3 deployment and rate-limit checkpoint

Entry HEAD/local/remote: `71ebd920b6e49cd3cf0eda2cb02dff7f9e1564bf`, canonical branch, preflight PASS, tracked tree clean on entry. All unrelated untracked/ignored assets remain preserved. No new worktree or branch. Owning Jira GS-117/GS-68; GS-179 remains dependency. This continuation adds fixed-name TEST_ONLY rejection diagnostics to the existing GS40 receiver only; authentication/policy decisions are unchanged. BUG_CLASSIFICATION=TEST_INFRA_ONLY; requirement source is existing physical TC001 diagnostic/acceptance evidence. No commercial onboarding, identity aliases, new issuer/backend/Home/APK or commissioning protocol.

Owner explicitly authorized narrowly reusing saved Windows Airtel_Agrim Wi-Fi credentials for encrypted commissioning of the exact physical S3. The secret was retrieved into a private captured process pipe and passed in memory to existing `encode_config`, then sent only in target-challenge-bound, signed AES-GCM GS40 envelopes through existing native helper Bootstrap. No Wi-Fi secret or plaintext configuration was printed, logged, committed, uploaded or written to a file. Existing protected fixture key files were reused; no device private key was extracted. Approval recorded GS-117 comment11671. The temporary orchestration source `/tmp/gs117-protected-bootstrap-session.py` contains paths/logic only, no secret, and is not a second protocol or framework.

Live native Windows enumeration again matched COM4 / 14:63:93:C5:D1:58 and COM10 / E0:72:A1:D3:8D:34. Espressif ROM inspection additionally proved ESP32-S3 rev0.2 / e072a1d38d34, embedded8MB PSRAM. Existing Secure Boot/flash encryption flags are disabled; they were not changed. Product table unchanged: ota0 0x20000/4MiB, ota1 0x420000/4MiB, outbox0x820000/4MiB, state0xc20000/256KiB. Active pre-update OTA1 selector seq2; inactive OTA0 seq1. Fresh complete app/table/selector/NVS/outbox/state backups are in owner-only `~/.local/state/ghar-sajag/gs117-tc001/s3-predeploy-current/`; each read length/hash was verified. Old app slots/outbox/state/table matched prior saved copies. No storage retirement, format or partition change was required.

Under the existing conditionally approved S3 app-only deployment/recovery authority, official ESP-IDF parttool erased/wrote ONLY ota0 (0x20000..0x41ffff), initially installing the 2,270,336-byte 59f9ffb80ce7f7d7af94af691f7dc7cdfe11fb39737835d08c29e44893bf1047 candidate. Full4MiB readback SHA87f5e0b78595265e7315a47e526317338da59bc0e98103b6862f0636ac619418 matched candidate prefix and erased tail. Byte comparisons verified NVS, partition table, selector, old OTA1, outbox and state unchanged after that write. Recovery app OTA1 remained intact. Official otatool then selected OTA0 with verified selector write. The Windows IDF_PATH import initially failed before any selector write; explicit Python import paths corrected it, without replacing Espressif tooling.

Actual boot proved full gs_r1_s3_hub from0x20000, version0af99da0451a-gs117-test and expected ELF prefix1bb787918. Its target-bound signed encrypted config was rejected with ESP_ERR_INVALID_ARG before Wi-Fi/security/HubRuntime startup. Never treated transport completion as provisioning PASS. An initial observation requested FIXTURE_STATUS after the rejection/reboot; that text reached the next boot's binary config receiver and caused INVALID_SIZE. Later bootstrap observations set query_s3_status=false until startup succeeds; no arbitrary commands or state edits were used.

To isolate the genuine target-only defect, the existing receiver now logs only fixed rejection-stage names and boolean policy results, behind its already isolated TEST_ONLY composition. No credentials, envelope/plaintext bytes or parsed secret values are logged. Two minimal incremental S3 product diagnostic builds were installed app-only into OTA0, preserving retained OTA1 recovery. Final diagnostic image is2,270,704 bytes, SHA fdb1555a795214dea12aece2a822d56cd6985ec571d990972c5060d3fe1052d6, version71ebd92-gs117-test. Official esptool write-hash checks passed; actual boot version/offset/ELF recorded. It is a full-product profile, not diagnostic-only firmware. Its binary/config/project metadata are preserved owner-only in `~/.local/state/ghar-sajag/gs117-tc001/s3-policy-rejection-candidate/`. Source is entry71eb plus the scoped fixed-name diagnostics diff, delivered in the subsequent commit.

**Physical root-cause boundary now established:** `GS40T/1 POLICY fields=1 material=0 time_key=1 authority_key=1 tls_identity=0`; reject stage=payload_policy. Therefore target config signature, ECDH/HKDF/AES-GCM decryption and required-field parsing passed; both signed-time and authority RSA public keys pass target validation. Remaining software defect is specifically the target `valid_tls_identity` result, not Wi-Fi retrieval, USB envelope transport, signature authority or C3 firmware. Host checks confirm actual certificate/private key match, both RSA3072, exact prepared leaf fingerprint aa0b1eff16547ad67a790d122bae1d88fd0e8040a50901ed841464d77a7f2732. Config private/public root match and exact public root is present in flashed binary. Do not weaken or bypass the TLS identity check. Next diagnosis must distinguish target certificate parse, private-key parse/policy, key-pair check, EKU and fingerprint stages using safe status codes, then correct the demonstrated incompatibility and run affected security regressions.

At14:18 UTC allowance was9%; at14:21 UTC8%. Owner requested status every2minutes and a logical pause below9%. No further integration attempts after that threshold. To avoid leaving the S3 in a configuration-rejection reboot loop, official otatool restored selector OTA1 (old e9e610b app) successfully; its app bytes were never overwritten. Final recovery observation is recorded separately. OTA0 retains the instrumented full-product image; no application recovery erase needed. Do not blindly full-flash or reflash C3. Before resuming OTA0 activation, preserve/verify current selector and relevant state, fix TLS identity validation, then use approved app-only/recovery safeguards. Automatic bootloader rollback is not claimed; manual official slot selection is the verified recovery method.

C3 was never rebuilt, flashed, reset, freshly commissioned or injected in this continuation. Repeated GET_STATE stayed session99, ota1, HIL_AWAKE_TEST_ONLY flags0/1/0, heap197292/min179820, retained0/inflight0, runtime_live0/sensing_live0. Existing physical secure association is still NOT_READY, not a C3 image failure. No new EventKey exists.

Network remained Airtel_Agrim Private, dynamically observed192.168.1.8. Existing proxy still stale192.168.1.7:443->172.17.152.10:8444. Requested normal `Start-Process -Verb RunAs` for existing gs179-windows-lan-proxy.ps1 ActionWatch; Windows returned operation canceled by user. No elevation/policy bypass, forwarding/firewall mutation or repeated UAC request. This single canceled dialog remains the network external prerequisite. Actual ingress8445/signed-time4468 endpoints in the encrypted preparation are not operational routes/listeners; do not claim CloudSync readiness from merely configured addresses.

Existing gs179-laptop.service and PostgreSQL remained active; no ownership/Node rows, event insert/delete, Home/account/backend replacement or historical HOST_SIM mutation was performed. Physical ingress/ownership/credential possession/CloudSync remain NOT_CONFIGURED/NOT_VERIFIED. Existing Home gs177-test-product preserved. Actual Android diagnostics/event visibility remains NOT_VERIFIED; no ADB or phone confirmation obtained.

Validation executed: TC001 helper26 + GS68/GS40 identity/time9 =35/35 PASS (22.785s); registered GS40 production-code host bootstrap82 checks PASS before and after target diagnostics; ESP-IDF6.0.3 incremental full-product S3 builds PASS; official write-hash checks and actual matched boot evidence PASS. An initial unittest invocation from repo root used the wrong module path and failed import; corrected execution from code/ ran all35 successfully. No assertion weakened. Context preflight/diff checks PASS. Broad Hub/contracts/backend gates were NOT_RERUN for this diagnostic-only delta; prior known migration/CSS/P0 PARTIAL failures remain as documented above and release approval is not claimed.

Resume exactly: inspect current handoff/HEAD/preflight and rate status; diagnose target TLS identity subcheck against the existing real fixture material without printing/exporting keys; correct minimal compatibility defect; rebuild/revalidate only S3 if required; activate/configure safely via existing encrypted bootstrap; verify mounts/HubRuntime; then use approved existing C3 fresh commissioning/PoP with protected test installer input. Verify both actual runtime states before any motion. Complete legitimate trusted-time/mTLS/Home/epoch ingress and scoped network route after UAC. Only then use existing console for one fresh original C3 EventKey, durable S3/backend exactly-once record and actual APK USER_CONFIRMED or authorized automated observation. TC001 remains BLOCKED/NOT_RUN; commercial release remains unqualified.

Final physical recovery observation PASS: boot loaded0x420000, versione9e610b, then its previously known fail-closed security bootstrap (no abort/reboot loop observed). C3 session99/heap unchanged, runtime/sensing0. Public evidence `s3-recovery-ota1-observation.json`. All serial processes closed; no new listener/time service/background deployment was left running.

## 2026-10-25 resumed target-TLS diagnosis and transport correction

Resumed with local/remote `d0e5f84ed5c56142452fc0ccec42bf4543e6aedb` on
`feature/r1-commercial-baseline`; context preflight PASS. Latest Jira checkpoint
comments before this continuation were GS-117/11672, GS-68/11673 and
GS-179/11674. The S3 target-only TLS details remain pending because the d0
physical attempt stopped before parsing the envelope.

Compared the last successful physical config exchange (which reached target
policy and reported `tls_identity=0`) with the latest d0 `RX stage=length
bytes=0` observation. Source history showed the sender had changed after the
successful run from one `stream.write(frame)` to prefix-first chunked writes.
Restored the original single full-frame write while retaining host-write
length/timing evidence. This is the smallest reuse-compatible correction; it
does not change GS40 wire bytes, signature, encryption, target trust policy or
the mbedTLS validator. Regression results: TC-001 console 26/26 PASS and
`make -C code gs40-test-only-bootstrap-test` 84/84 PASS; `git diff --check`
PASS.

Physical recovery/checkpoint: native Windows port enumeration again matched
COM4 `14:63:93:C5:D1:58` and COM10 `E0:72:A1:D3:8D:34`; C3 read-only state
remained session99, `HIL_AWAKE_TEST_ONLY`, empty retained/in-flight queues,
`runtime_live=0`, `sensing_live=0`. The S3 OTA0 candidate SHA-256 remains
`9cd0b99e52837248ef24e9fbbf61c8326389986b4a326fd56c3ef32c4115509f`; verified
OTA1 recovery backup remains
`3767e80d33f11748642d1174c55a76e4a61d2ceae5f9699b7f7fabafb3b86b71`.
Partition table and app fit are unchanged. Before selecting OTA0, a fresh
official read-only otadata backup was saved mode0600 and validated: sequences
11 and 12 select OTA1. The existing ESP-IDF `otatool.py` then selected OTA0;
its log confirms COM10 MAC `e0:72:a1:d3:8d:34` and a hash-verified write of
only the otadata region at `0xF000..0x10FFF`.

The subsequent protected bootstrap attempt did not enumerate COM ports or
open serial. It exited at `verified_port_enumeration` after the Windows Python
launch failed with `UtilAcceptVsock: accept4 failed 110`. That attempt had
passed its private-network checks and handled the previously authorized
Wi-Fi credential only in process memory; it did not pass a config envelope.
A second attempt exited at `network_preflight` with the same transient WSL
interop failure before credential retrieval. A direct PowerShell probe also
returned the vsock timeout. Therefore no new S3 `RX`, TLS, HubRuntime, storage,
or CloudSync result exists. OTA0 is selected after the official tool reset;
do not claim its current boot or assume automatic rollback. The immediate
next action is regain the existing WSL-to-Windows process bridge, observe the
exact running slot over COM10, then either send one protected full-frame GS40
envelope and capture the target subchecks or use the official selector to
restore OTA1 if the candidate remains fail-closed. Do not reset WSL or disrupt
the existing backend service as a workaround.

Worktree delta at this checkpoint: changes to the existing serial helper and
its existing tests, plus this execution record and R1 work state. Numerous
untracked/ignored owner assets remain preserved and unstaged. No application
flash, partition-table/NVS/key/ownership changes, C3 injection, PostgreSQL
mutation, or APK event verification occurred during this retry. TC-001 remains BLOCKED/NOT_RUN;
actual Android event visibility remains NOT_VERIFIED.

## 2026-10-25 resumed physical S3 receive diagnosis

Resumed from local/remote `d0e5f84ed5c56142452fc0ccec42bf4543e6aedb` on the
canonical branch. Context preflight PASS. Latest Jira evidence read before
work: GS-117/11672, GS-68/11673, GS-179/11674. COM4 remains the C3
`14:63:93:C5:D1:58`; COM10 remains the S3 `E0:72:A1:D3:8D:34`.

The target's detailed TLS validator is still present and unchanged; it reports
fixed booleans and fixed integer statuses only. It cannot run until the S3
receives and accepts a complete envelope. A prior attempt ended before target
parsing. Candidate app in OTA0 is
`d4517c92a6ce5f8c2ce3aae1cbe98a984f886b9c7149b83e5ba47a5007669ade`
(2,272,576 bytes, full product, GS40 TEST_ONLY/CloudSync enabled, USB
Serial/JTAG profile, 32 KiB requested RX ring); the readback artifact hash
matches the candidate. OTA1 recovery image remains
`3767e80d33f11748642d1174c55a76e4a61d2ceae5f9699b7f7fabafb3b86b71`.
No partition table, NVS, outbox, or state partition was written.

The existing Windows helper now reads the target challenge first, obtains the
same signed/encrypted response, and can reopen only the exact verified COM
identity before TX after USB re-enumeration. Re-enumeration is bounded to five
seconds; the challenge wait remains explicitly bounded (20–75 seconds). Tests
cover the port disappearing/reappearing and invalid timeout values. Historical
successful S3 policy evidence used whole-frame, paced 256-byte writes; this
existing transfer was restored rather than the later prefix-only delay variant.

Controlled physical retries all reached the host-side envelope write
(7,323 bytes), but the current OTA0 receiver continued to report
`GS40T/1 RX status=timeout stage=length bytes=0`, including with the requested
32 KiB ring and with the exact COM identity reopened immediately before TX.
The last attempt observed a fresh challenge and took 55,485 ms from bootstrap
start to completed host write; the S3 still reported zero length bytes after
its 60-second receiver deadline. This establishes a current Windows-native-USB
TX-to-target-RX transport failure. It does **not** reach signature, decryption,
TLS PEM parsing, key-pair, EKU, fingerprint, trusted-time, ownership,
HubRuntime, storage-mount, or CloudSync validation. Therefore the historical
`tls_identity=0` remains unresolved; no target TLS subcheck result is claimed
for this resumed attempt.

After the retries, the official ESP-IDF `otatool.py` selected OTA1 again and
verified the otadata write hash. A reset-aware native observer then proved the
physical S3 booted from `0x420000`, version `e9e610b`, and retained its known
fail-closed `Hub security bootstrap failed closed` behavior. The inactive OTA0
diagnostic candidate remains available for a later controlled retry. C3
read-only state remained `ota_1`, `HIL_AWAKE_TEST_ONLY`, session 99, retained 0,
in-flight 0, `runtime_live=0`, `sensing_live=0`.

Validation after the helper change: `PYTHONPATH=code python3 -m unittest
tests.python.test_gs117_tc001_console` — 26/26 PASS;
`make -C code gs40-test-only-bootstrap-test` — 85/85 PASS;
`git diff --check` PASS. No C3 injection/commissioning, event, database
mutation, credential/ownership update, Windows proxy/firewall update, or APK
observation occurred. TC-001 is BLOCKED/NOT_RUN; actual APK event visibility
is NOT_VERIFIED. Existing Home and all historical records remain preserved.

Precise next action: diagnose why Windows COM10 host writes are accepted by
pyserial but the identified S3 USB Serial/JTAG receive driver sees no first
byte. Keep the supported full-product application and protected TLS/ownership
checks intact. Do not claim the TLS fix until a new target envelope reaches the
fixed TLS-subcheck log. OTA1 is currently the selected recovery app; OTA0 and
all owner-only backups remain preserved. The five-hour status tool still
returns no usage/remaining-budget value, so no percentage is inferable.

## 2026-10-25 latest receive-path correction

Fresh Windows-native enumeration continues to identify COM10 as the physical
S3 (`VID:PID=303A:1001`, serial `E0:72:A1:D3:8D:34`), the Espressif native
USB Serial/JTAG interface. It is not a CH343 UART; the UART profile is not
applicable. The fixture's current S3 image emitted the GS40 challenge and
reported the USB Serial/JTAG driver installed and connected. The existing
Windows helper accepted a single 7,323-byte length-prefixed encrypted frame
(write duration 1,610 ms), but the S3 then reported
`GS40T/1 RX status=timeout stage=length bytes=0`. This means the envelope did
not reach the target parser; no TLS credential subcheck ran. The historical
`tls_identity=0` therefore remains unresolved.

The helper's source comment was corrected: host-side `pyserial.write()`
acceptance does not prove target receipt. The helper remains a single bounded
write with an independent target-log check. The receive ring source was
restored to the existing bounded 4 KiB setting; the inactive OTA0 image still
contains the prior 32 KiB build and was not changed. No additional reset or
flash was performed for this diagnosis.

The official OTA selector remains on the backed-up OTA1 recovery image
(`0x420000`, version `e9e610b`), whose observed startup fails closed because
Hub security bootstrap is not configured. The preserved OTA0 product candidate
hash remains
`d4517c92a6ce5f8c2ce3aae1cbe98a984f886b9c7149b83e5ba47a5007669ade`.
The fresh readback/backup remains under the owner-only directory
`~/.local/state/ghar-sajag/gs117-tc001/s3-pre-bootstrap-20261025T2112Z/`.

Latest source checks after the bounded-ring change: TC-001 Windows-helper
unit tests 26/26 PASS; GS40 TEST_ONLY bootstrap checks 85/85 PASS; working
tree whitespace check PASS. C3 remains unchanged (`runtime_live=0`,
`sensing_live=0`); no event was injected. No backend record or caregiver
history was mutated. TC-001 remains BLOCKED/NOT_RUN and actual APK event
visibility remains NOT_VERIFIED.

A previous note in this record said the full-frame write had already been
proven on the target and described a COM re-open before transmission. That
claim is superseded: host write acceptance is the only evidence for this
attempt, the target reported zero received bytes, and the current helper does
not re-open the port. Do not report target receipt or TLS diagnosis until a
subsequent S3 receive log demonstrates bytes reached the parser.

Five-hour usage status was queried; the available status tool returned no goal
or remaining-budget values, so a remaining percentage cannot be computed.

## 2026-10-26 — reset/challenge timeline investigation

Owning Jira GS-117 / GS-68; scope is the existing Windows serial helper and
its registered TC-001 tests. Classification TEST_INFRA_ONLY. GS40 envelope
bytes, cryptography, Node/Hub semantics and credentials are unchanged. Existing
requirements: original EventKey, authenticated enrollment/ownership and secure
TEST_ONLY bootstrap. Positive/negative/recovery validation remains in the
existing `gs117-tc001-console` stage; real matched COM10 receipt is mandatory.
No release qualification is claimed.

Entry local/remote HEAD `8cbda4b742e9c216bb667fe5fdf710326915ecca`, canonical
branch/worktree and context preflight PASS. Fresh native Windows List matches
COM4/C3 and COM10/S3 serials. A fresh owner-only readback is preserved at
`~/.local/state/ghar-sajag/gs117-tc001/s3-usb-timeline-20261026/`. Table, NVS,
both application slots, outbox and state match the prior backup byte-for-byte;
otadata reflects the previously selected OTA1. OTA0 image prefix matches
`d4517c92a6ce5f8c2ce3aae1cbe98a984f886b9c7149b83e5ba47a5007669ade`,
2,272,576 bytes; remaining app tail is erased. Archived image-info and exact
build config SHA `44ee7d9514441f30ed520a0af9cfef6f30eeee685719ab91bfd45d4862164dc9`
prove this deployed candidate requests 32 KiB USB RX, primary USB Serial/JTAG,
UART_NUM=-1, and PM disabled. This is distinct from current source's 4 KiB ring.

Comparison of raw observations reveals the failed run records a new boot and
challenge *after* host TX, then the 60-second timeout. The helper previously
accepted any buffered challenge immediately following HardReset. Hypothesis:
a previous-boot challenge was consumed, so TX raced the next boot/driver setup.
The helper now purges input before the approved reset, requires new boot/app
metadata before selecting a challenge, rejects an unexpected image/port, and
refuses response generation beyond a 25-second target budget or an intervening
reset. It records separate challenge/parent/TX timing and actual DTR/RTS state.
Focused 27-test regression PASS; exact physical verification is in progress.
The official OTA selector selected preserved OTA0; no application image write
or partition/NVS/outbox/state change was made for this test.


## 2026-10-26 — Physical encrypted provisioning and C3/S3 session operational

This checkpoint supersedes the earlier zero-byte-receive and C3-inactive blockers.
Owning issues GS-117 / GS-68 / GS-179 / GS-114. Entry canonical local/remote
HEAD `8cbda4b742e9c216bb667fe5fdf710326915ecca`; context preflight PASS.
Implementation classification TEST_INFRA_ONLY / R1_FIX for the demonstrated
fixture activation defects; no protocol, production identity, durability or
commercial transfer policy changed. All work remains in the canonical worktree
and branch. The earlier stale-challenge hypothesis was tested and not reproduced.

### Root cause and smallest fixes

The exact installed S3 OTA0 image/ELF/config were matched to readback, rather
than inferred from current source. Fresh challenge timing was 1,328 ms, response
generation 281 ms and host write 31 ms with DTR/RTS false. The target received,
authenticated and decrypted the complete 7,323-byte frame, then crashed during
PSA RSA private signing in TLS key-pair validation. Symbolized stack evidence
shows at least 3,824 bytes in a 3,584-byte main task. The apparent zero-byte
60-second timeout was emitted by the subsequent boot, not the receiving boot.
No USB transport downgrade, chunking workaround or authentication relaxation
was needed. Existing Windows helper evidence now retains fixed assertion headings,
fences challenges on fresh boot/image/port evidence, and records bounded timing.
Raw memory dumps and secrets remain excluded.

The isolated GS40 profile now reuses the existing GS68 main-task budget of
8,192 bytes, with a compile-time guard and four bounded stack diagnostics.
After one verified app-only S3 OTA0 update, physical TLS parsing, RSA3072,
PSA sign/verify, key-pair proof, client EKU and fingerprint validation PASS:
`valid=1`, `pair_check=psa_signature`, `raw_pair_equal=0`, minimum headroom
3,024 bytes. Existing cryptographic pair-proof fallback is retained. The S3
started its authenticated product Hub owner for the actual physical identity
and existing Home, storage_epoch=1. The saved Wi-Fi secret was used only in the
approved encrypted commissioning path and never written to logs or Git.

First physical C3 commissioning correctly failed closed at
`association_backup_failed`. The demonstrated first-use bug required the saved
association before invoking its creation. The correction prepares and verifies
the existing encrypted backup before requiring it and before the monotonic
unpaired tombstone. It verifies all binding fields, generation, both public keys
and installation key; it rejects conflicting/corrupt backups. Existing recovery,
identity and same-Home production checks are unchanged. The existing native helper
now has a restricted exact-fixture setup action using existing QR/PoP and
commissioning commands; the installer code stays in RAM. This is not a web
endpoint or new commissioning protocol. Do not run this action again on the
now-commissioned fixture.

### Installed images and preservation

| Board | Current app / physical result | Preserved recovery |
|---|---|---|
| C3 COM4 / 14:63:93:C5:D1:58 | OTA0, 958,832 bytes, SHA256 `591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea`, version `8cbda4b-dirty`, ELF `990fe1f2e4033780035777d044f57f3b0acf5849ffcdff65fcf30f60386d8e47` | Prior OTA1 image `183417fdd840ed9cce333e7b276beeaba83d085173f9cbe28589d617d874739f` preserved and readback verified |
| S3 COM10 / E0:72:A1:D3:8D:34 | OTA0, 2,272,944 bytes, SHA256 `b92e85440430608d3190d0a22cb7d65cc2156210fa6b7878129edb614294a728`, version `8cbda4b-dirty`, ELF `eed78cac476c2f7dfd14356373510561de268959b1323cf33dc38124e016350c` | OTA1 recovery `3767e80d33f11748642d1174c55a76e4a61d2ceae5f9699b7f7fabafb3b86b71` preserved |

Official ESP-IDF otatool app-partition API was reused after exact identity,
layout, backup and recovery checks under existing conditional owner authorization.
The upstream write CLI failed before any app write because of its argument
adapter; the existing API performed the scoped app-only update. Only the app
partition was erased/programmed; no whole-chip erase, table/bootloader write,
eFuse operation or protected-key extraction occurred. S3 table/NVS/OTA1/outbox/
state readbacks were byte-identical after installation. C3 bootloader/table/OTA1
were byte-identical; raw NVS comparison initially differed and was classified
before commissioning: only the legitimate boot_session counter advanced, while
32 other active records were unchanged. Boot-session monotonicity was preserved.
Full opaque backups, selectors and manifests remain owner-only under
`~/.local/state/ghar-sajag/gs117-tc001/s3-usb-timeline-20261026/`.

C3 is `HIL_AWAKE_TEST_ONLY`, GS_HIL_BUILD=OFF, GS_HIL_CONTROL=ON,
GS_BAT_C8_PHYSICAL_WAKE=OFF. No production sleep/physical-wake changes.
The S3 full-product image has commissioning and TEST_ONLY CloudSync enabled;
its embedded older C3 FOTA asset is not the new C3 app. No FOTA was invoked and
this is not a release-qualified paired artifact. Neither board needs another
flash for the next network/configuration step.

### Actual authenticated fixture and existing backend

The owner-approved disposable previous C3 binding belonged to
`home-37e0751595a51eb3994dfe4c93c480a5` / `hub-7c4fadb72a20`, generation1.
Encrypted association/recovery backup was verified; retained/pending counts were
zero. The scoped retirement committed monotonic generation2 without deleting
factory identity or security counters. Existing commissioning/PoP/rejoin then
established the real pair `c3-146393c5d158` -> `hub-e072a1d38d34` in
`gs177-test-product`. Both sides reported authenticated rejoin, C3 session107.
The same permanent Node public key was verified before/after. Public Hub key was
observed only after authenticated rejoin. Runtime/sensing counters rose from131
to22090 in later independent observation; these are counters, not Boolean flags.
Serial remained accessible with no further reset.

Public proof: `physical-pair-20261026.json` (proof SHA256
`9eae1b774125ac04c9bdfc7195f2879ce98e8e247ee675fff1af289e92464ee4`),
plus `physical-activation-20261026.json` and the exact crash diagnosis JSON.
The existing PostgreSQL ownership registry now contains the verified physical
Hub/Home epoch1 and Node/bedroom enrollment generation1, using explicit owner
fixture authorization. Generation1 follows the first committed NodeRegistry
enrollment contract; no unsupported generation query is claimed. Event count
remained exactly1 before/after registry configuration: no fake event insertion,
new Home, account, database, credential issuance or historical seed deletion.

Existing GS179 strict-mTLS listener composition ran a bounded private-interface
trial on WSL172.17.152.10:8445: listener/PostgreSQL/TEST_ONLY trusted-time readiness
PASS. Real Hub authentication remained NO; trace contained no requests. This
trial is not persistent autostart deployment. Existing Windows signed-time
service received eight UDP requests using the persistent approved time key;
requests alone do not prove physical trusted-time acceptance. No UDP firewall
change was needed. Bounded trial services are stopped at the handoff; caregiver
HTTPS/PostgreSQL remain in place. The one-hour encrypted S3 config has expired
and must be refreshed after the route is operational, using the same protected
bootstrap. C3 must then rejoin normally; do not retire/commission it again.

### TC-001 acceptance status

| Stage | Result / evidence |
|---|---|
| Exact boards, active apps, HIL profile | PASS; current readbacks and startup/status |
| Encrypted target receipt and TLS material validation | PASS; physical GS40 validation and 3,024-byte headroom |
| Product Hub startup, authenticated C3 enrollment | PASS; real Hub owner and authenticated rejoin |
| C3 runtime/sensing and stable serial | PASS; positive increasing counters and later status |
| Backend ownership/Home/Node enrollment | PASS; existing registry, event count unchanged |
| Physical S3 signed-time/authority acceptance | NOT_VERIFIED; CloudSync remains fenced |
| Physical S3 mTLS/CloudSync delivery | BLOCKED; no Windows8445 route; no authenticated Hub trace |
| Controlled C3 INJECT_MOTION | NOT_RUN; no injection command issued |
| Same fresh EventKey exactly-once PostgreSQL/API | NOT_VERIFIED |
| Actual Android event display | NOT_VERIFIED; no approved ADB device access available |

A buffered `PIR -> NodeRuntime session=107 seq=1` line appeared during idle
observation. It is uncontrolled sensor input, not TC001, not C3_HIL_INJECTED and
not genuine optical qualification. Preserve it; use a new later EventKey for
the controlled test after CloudSync readiness. Do not count the historical
HOST_SIM seed or this incidental line as acceptance.

Authenticated caregiver backend readiness PASS at
`https://desktop-3qqu64b.local`, existing Home `gs177-test-product`; returned
monitoring UNKNOWN/freshness STALE. This is backend/API evidence, not proof of the
installed APK origin, Home or fresh presentation. No APK was rebuilt/reinstalled.

### Focused and component verification

- Existing TC001 suite: 28/28 PASS, including stale challenge/image/port/reboot/
  deadline rejection, private QR handling, commissioning failure and real counter
  semantics. GS40 bootstrap85 checks PASS; association/recovery production tests
  PASS including GS117-FRESH-BACKUP-001 first-use/I/O/conflict/recovery cases.
- Full C3 and S3 target builds PASS. Existing production battery/wake and optical
  qualification status unchanged. Power profile source was not redesigned.
- Proxy extension: existing Windows script AST parse PASS; focused PostgreSQL
  security suite19 PASS, including fixed endpoint/default-off and existing guards.
- Affected campaign actually ran: Node30/31 stages PASS, Hub53/55 PASS,
  contract47/48 PASS. Campaign FAIL remains explicit: required P0 test has
  product_status=PARTIAL despite scenario exit0; Hub migration exits2/count0.
  Board-stack E2E PASS, 10 cases. These known failures are not weakened.
- Campaign logs/builds are in
  `code/build/validation_targets/gs117-s3-stack8192-20261026/`; component reports
  node-1792983455848551833, hub-1792983941705998306,
  contract-1792984889884005184, board-e2e-1792985557310432517.
- Initial additional GS179 command lacked opt-in DSN, then lacked local libpq;
  both were harness environment failures, corrected using existing isolated-schema
  helper, protected local DSN and service library path. Final result recorded below.
- Release-gate-final/full release, physical lost-receipt recovery, optical PIR
  and Android acceptance NOT_RUN. No commercial/release PASS.

### One consolidated external operation and exact resume action

Live read-only Windows evidence: Airtel_Agrim Private192.168.1.4/24; S3 neighbor
192.168.1.10 MAC matches. Stale owned proxy192.168.1.7:443->WSL172.17.152.10:8444;
no8445 proxy. Normal existing-script invocation was rejected by Windows Restricted
execution policy (all scopes Undefined). No policy/elevation bypass or firewall
change was performed.

The existing proxy now supports one explicit `-EndpointKind PhysicalHubIngress`
fixed8445->8445 route, distinct named rule `GS117-Physical-Hub-mTLS`, default OFF.
Only Audit/Start/Stop are enabled for it. Original dynamic Wi-Fi, Private/Domain,
subnet, administrator, ownership and rollback guards are reused. Caregiver default
443->8444 is unchanged; console18791 remains localhost-only.

Required owner approval is one scoped normal-UAC Windows operation: execute a
hash-verified local copy of the reviewed existing script with process-scoped
RemoteSigned permission (no persistent/global/organization policy change), repair
owned caregiver443 forwarding and add only physical-Hub8445 forwarding/rule on
the dynamically detected trusted Private Wi-Fi subnet. Rollback is existing Stop
for each exact endpoint and recorded WSL target. No UDP rule or broad port opening.

After approval, agent performs the operation; owner need not run terminal commands.
Restart existing signed-time and GS179 listener components, refresh encrypted S3
configuration, verify target time/authority and real Hub mTLS, observe ordinary
C3 authenticated rejoin, baseline all events, then use existing console to inject
one NEW event and correlate durable backend/API and actual APK. If ADB remains
unavailable, require genuine phone-side USER_CONFIRMED evidence for that EventKey.

Source checkpoint is entry HEAD plus scoped changes; final commit/verified remote
SHA and Jira comment IDs are in delivery below. All unrelated untracked/ignored
assets, credentials and historical backups are preserved. No new branch/worktree.
Available status telemetry returned no five-hour quota values; percentage is unknown.


### Final validation and delivery preparation — 2026-10-26

Corrected-environment `make -C code gs179-postgres-e2e` PASS, 57/57 tests,
no skips, isolated random schemas only; historical fixture data untouched.
Log: `code/build/validation_targets/gs117-s3-stack8192-20261026/gs179-current-regression-isolated.log`.
The initial unconfigured DSN/libpq attempts are superseded by this actual run.
`make -C code feature-coverage-test` PASS: 226 features, 285 modules,
27 physical cases; 22 consistency/framework tests. Adding the existing opt-in
PostgreSQL stage to this feature's mapping required correcting its derived
command/gate/fast/release columns; the opt-in stage remains outside ordinary
fast/release composition. No suite was disabled. Context preflight PASS at
04:04 UTC and whitespace checks PASS. Bounded owned ingress process215181
stopped cleanly; no8445 listener remains. Signed-time service was a15-minute
window and has ended. Caregiver/backend services are preserved.

Final scoped implementation is nine existing code/test/config files, canonical
handoff/work-state/validation updates, three public evidence JSON receipts and
one existing traceability/catalogue row each. Unrelated untracked and ignored
firmware/Android/evidence assets remain untouched. Installed images were built
from parent8cbda4b plus the committed implementation changes; version strings
retain8cbda4b-dirty, exact SHA256 above is authoritative. Final commit/remote
and Jira receipt are supplied in the delivery response. Next operation remains
the single reviewed Windows policy/UAC scoped route operation, not another flash.


## 2026-10-26 — Approved network activation and demonstrated CloudTrust gap

Entry local/remote9bbc6d0c89f5a8dcad575e3f4f8a4f5aafc8c117, preflight PASS.
Owner approved process-only RemoteSigned/normal UAC for existing proxy443/8445.
Canonical/local copy SHA25601a8778b552e698deb3f80021c043a323e2410b822fda4af71d9ce36b80e2b26
matched. Normal UAC exited0. Current Airtel_Agrim Private192.168.1.7/24;
both exact owned routes/listeners PASS, subnet192.168.1.0/24. No global/user
execution policy change, elevated task or unrelated firewall mutation. Existing
network-refresh-config reused to update server IP SAN with SAME CA/private key,
backup prior leaf/config, restart existing caregiver service. Health PASS.

Actual S3 refreshed encrypted config, TLS valid1, Hub starts enrolled1/storage_epoch1.
Authenticated physical /v1/test/authority/refresh requests return200 over mTLS.
However current_binding remains unavailable. Source reveals second TEST_ONLY
key-pair validation in cloud_trust_provider.cpp still requires the raw
mbedtls_pk_check_pair that already physically failed for this exact RSA material;
bootstrap's verified PSA signature pair-proof fallback is not reused there.

BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=Existing GS117 TC001 authenticated CloudSync and GS68 TLS identity
DECISION_IDS=NONE
TASK_SCOPE=Reuse existing TLS identity validation for TEST_ONLY CloudTrust software key; no new credential/protocol, no production relaxation.
OUT_OF_SCOPE=Commercial onboarding, new issuer/runtime/backend, C3 firmware changes.
VALIDATION_PLAN=Existing GS40 bootstrap and production CloudTrust positive/wrong-key/fingerprint tests plus PKCS1/PKCS8 key serialization regression; full product S3 incremental build; app-only deployment only after current-image/layout/backups/recovery checks; actual physical CloudSync evidence. Existing affected-suite receipts remain separate; rerun relevant security/contracts for changed source.


## OWNER-REQUESTED PAUSE — 2026-10-26 04:48 UTC

This is the latest resume checkpoint and supersedes the earlier Windows approval
blocker. The owner requested a logical pause during corrected S3 app deployment.
Physical operations and temporary services are now stopped. No motion was injected.

### Completed during this continuation

- Normal UAC completed the explicitly approved existing proxy operation, exit0.
  Hash-verified script SHA256
  `01a8778b552e698deb3f80021c043a323e2410b822fda4af71d9ce36b80e2b26`.
  Current trusted Private Airtel_Agrim192.168.1.7/24 detected dynamically;
  Windows443->WSL172.17.152.10:8444 and8445->WSL:8445 listeners PASS.
  Rules remain scoped to192.168.1.0/24, Private, Wi-Fi. No global/user execution
  policy change, unrelated rule/proxy mutation or persistent elevated task.
- Existing network-refresh-config reused SAME server CA/private key to refresh
  leaf IP SAN for192.168.1.7, backing up old leaf/config and restarting existing
  caregiver service. PostgreSQL, caregiver HTTPS and LAN certificate-verified
  health PASS. Existing credentials/Home/history preserved.
- Existing approved time/ingress components started temporarily. Physical S3
  encrypted configuration/TLS validation PASS on b92e8544 OTA0, stack headroom
  2976 bytes; product Hub starts enrolled1/storage_epoch1. Physical mTLS
  authority-refresh POSTs actually reached existing backend and returned200.
  This proves the operational signed-time/TLS bootstrap prerequisite; it does
  not prove target lease acceptance or event CloudSync COMMITTED.
- Found second TEST_ONLY key validation in CloudTrust still using the rejected
  raw mbedtls_pk_check_pair format. The existing bootstrap's PSA signature
  key-pair proof is now reused through one exported validator. All parsing,
  RSA3072, PSA, client-EKU, fingerprint and key-pair checks remain; production
  DS/identity code is unchanged. No second verifier, CA, protocol or backend.
- Registered existing CloudTrust test source now contains permanent
  GS117-CLOUD-PAIR-001: PKCS1/PKCS8 valid same-key acceptance and unrelated valid
  RSA3072 key rejection. Existing wrong Home/epoch/certificate/revocation cases
  remain. Host link dependency/stub follows the existing bootstrap unit pattern;
  physical validation never uses that closed HTTP stub.

### Exact device and deployment state — no activation during pause

C3 COM4 /14:63:93:C5:D1:58 was NOT changed this continuation. It remains the
verified591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea
HIL-awake OTA0 image. Prior fresh commissioning has already succeeded for the
correct Home/pair; do not retire data or commission again. Latest observed
session107 runtime/sensing counters293852; incidental sensor events are not TC001.
Current radio connectivity is not claimed while S3 is paused in ROM.

S3 COM10 /E0:72:A1:D3:8D:34 new full-product candidate:

- Version9bbc6d0-dirty, bytes2272848.
- SHA256 `404dd1ec32ec3f66585f3a8c54e1ee94e8e068b5ff619f9e6369df154a6d51bf`.
- ELF SHA256 `c404867432239b103690f14bc5fc31e8261897413c5be25ed5ab0a6b5221a8ae`.
- Profile GS40_TEST_ONLY_CLOUDSYNC=ON, GS_HIL_COMMISSIONING=ON,
  GS_HIL_BUILD=OFF, GS_HIL_CONTROL=OFF, diagnostic OFF; main stack8192.
- Official existing OtatoolTarget.write_ota_partition(1, image) wrote ONLY
  inactive OTA1 at0x420000/4MiB; no selector change. Readback PASS for full app
  and erased remaining tail. No partition/NVS/bootloader/eFuse write.
- Protected-region before/after byte equality PASS: partition table, otadata,
  NVS, OTA0, gs_outbox and gs_state. Full opaque backups/manifests retained.
- OTA0 still selected: selector sector0 sequence27/stateVALID(2), sector1
  sequence26/stateUNDEFINED(0xffffffff), CRCs valid, unchanged byte-for-byte.
- Proven OTA0 recovery app b92e85440430608d3190d0a22cb7d65cc2156210fa6b7878129edb614294a728
  remains intact. Historical replaced OTA1 app also remains in the pre-update
  backup. Do not blindly restore a whole-flash image.
- At pause: S3 is in ROM/stub after readback, serial handle closed.
  **New OTA1 is WRITTEN_AND_READBACK_VERIFIED, NOT_SELECTED, NOT_BOOT_VERIFIED.**
  No claim that corrected CloudTrust or event CloudSync has passed hardware.

Owner-only current session evidence:
`~/.local/state/ghar-sajag/gs117-tc001/network-activation-20261026/`.
Contains Windows UAC audit/results, network-refresh/health, actual mTLS trace,
protected before/after S3 backups, plan, app-only log and
app-only-write-verification.json. Public no-secret summary:
`network-pause-20261026.json` beside this handoff.

### Services and accepted limitations at pause

Temporary Linux ingress PID218238 gracefully stopped; listener8445 absent.
Owned Windows signed-time PID12512 stopped. Existing caregiver service remains
ACTIVE. Approved restricted Windows443/8445 forwarding remains configured;
8445 has no backend listener until resumed. No new elevated task. The existing
server.env, TLS trust, private fixture keys and physical PostgreSQL registry are
preserved. No new Home/account/database/APK and no backend event insert.

No new controlled EventKey; TC001 NOT_RUN, actual Android NOT_VERIFIED.
Existing console fixture.json is absent. It still requires actual phone
installation/backend/Home evidence and authenticated ingress/current-image
receipts before Run. Do not fabricate these or weaken the guards. A text-only
phone Home/origin check was requested asynchronously; no reply had arrived at
pause. No connected Android ADB interface was found. Manual final evidence must
be USER_CONFIRMED, never automated PASS.

### Actually executed validation

Full S3 product target build PASS. GS40 bootstrap85 checks PASS; CloudTrust
provider PASS including new pair-format/wrong-key production-code regression.
`make cloudsync-security-ut cloudsync-security-sim-hil` PASS: adapters9 and5,
provider suites5, Python groups14/9/13/5, simulation18. Initial provider link
failure from the new shared bootstrap dependency was corrected with the existing
closed unit HTTP adapter pattern; final build/test passed. Superseded initial
compile run cancelled when adding the regression, not used as evidence.

No full affected component campaign was rerun after this fix because of the
explicit owner pause. Prior campaign failures (required P0 PARTIAL and Hub
migration) remain unresolved. Full release/optical/PIR/physical CloudSync event
qualification NOT_RUN. Mapping/preflight/whitespace checks recorded at delivery.

### Precise next action after owner resumes

1. Read this checkpoint, verify actual canonical local/remote HEAD and context
   PASS, confirm no later writer/device changes. Preserve all assets/backups.
2. Confirm current Private Airtel_Agrim dynamic IP and approved owned routes.
   Restart existing protected time and GS179 ingress composition using preserved
   CA/registry/Home/epoch; no new issuer or ownership mutation. Refresh endpoint
   leaf through existing network-refresh-config only if dynamic SAN changes.
3. Verify preserved new OTA1 readback manifest and current OTA metadata match.
   Use existing official OTA selector switch to slot1 (selector-only, not flash).
   Retain verified OTA0 as recovery. Expected app offset0x420000,
   version9bbc6d0-dirty, ELF prefixc40486743.
4. Refresh encrypted S3 GS40 config with existing protected orchestration,
   adapting expected boot metadata to OTA1. Script
   /tmp/gs117-protected-bootstrap-current-network.py currently expects OLD OTA0;
   change those expected fields, not credentials/protocol. Do not run an old
   challenge/frame or reissue fixture credentials. Bootstrap reboot is already
   within recorded fixture authorization.
5. Capture actual corrected S3 startup, persistent mounts/enrolled1, trusted time,
   authority/current CloudTrust and real event delivery; observe ordinary C3
   authenticated rejoin. Do not fresh-commission or reflash C3.
6. Obtain honest current phone/backend/Home and installed-image/ingress receipts,
   prepare existing fixture.json, then existing localhost console Run Test once.
   Trace a NEW original C3 EventKey through S3/COMMITTED/unique PostgreSQL/API
   and actual APK. Historical HOST_SIM and incidental sensor events are not TC001.
7. Run pending affected-component regressions for the new shared verifier,
   record actual hardware/Android results, update existing Jira and commit/push.

Canonical branch remains feature/r1-commercial-baseline; source parent
9bbc6d0c89f5a8dcad575e3f4f8a4f5aafc8c117 plus scoped tested changes delivered
in the subsequent checkpoint commit/Jira receipt. All unrelated untracked/ignored
assets preserved. This pause is the owner's request, not a new approval blocker.


Pause delivery checks: context preflight PASS; feature-coverage consistency
PASS226 features/285 modules/27 cases and22 tests; git diff whitespace PASS.
Ready candidate BIN/ELF/sdkconfig/project metadata and exact firmware-source patch
are preserved owner-only in the current session's `s3-cloudtrust-ready/` with
verified manifest. That earlier candidate is superseded by the final bounded candidate noted below. Existing .tmp operator orchestration paths are convenience only;
canonical APIs and source remain the authority. Final commit and actual remote
HEAD are recorded in dated Jira pause comments and this session's final handoff.


### Final pause review correction — supersedes immediate selector-only resume

Final diff review caught that the original8192-byte private-key bound needed to
remain explicit at the shared verifier API, even though the physical encrypted
config path already enforces bounded material. The bound was restored, with an
oversized-but-valid-PEM rejection regression, before committing. No further
physical write/reset/selection was performed after the owner pause checkpoint.

Consequently the already-written inactive404dd1ec image remains unselected and
is **SUPERSEDED**, not the final source build. Do not activate it on resume.
Latest full-product bounded candidate version9bbc6d0-dirty:
bytes2272880, SHA256 `ce33f40aefee2ad9009c5c88a518dd83b5bb02186d204788d510a10dac945e65`, ELF SHA256 `1140ce12cc8b0b0240e0836fb4f26fb71c54e4c1f42e98f7edda3a03f2d3523e`.
Its full target build PASS; candidate is BUILT_NOT_WRITTEN/NOT_BOOT_VERIFIED.
Owner-only BIN/ELF/config/source-patch provenance manifest is under current session
`s3-cloudtrust-bounded-ready/`; the earlier written candidate remains preserved
separately in `s3-cloudtrust-ready/`. Scratch operator sources are backed up under
`operator-session-sources/` and contain paths/logic only, no plaintext secrets.

**First physical action after resume:** verify existing OTA0 recovery/current
protected data and latest candidate provenance; use the already-authorized existing
app-only mechanism to replace inactive OTA1 with latest bounded candidate, read
back/verify protected regions, then official selector slot1 and protected config.
Expected boot offset0x420000/version9bbc6d0-dirty/ELF prefix1140ce12c.
Do not rebuild unless source changes; do not reflash C3 or recommission. The earlier
selector-only instructions above apply only AFTER this final candidate is written.


## 2026-10-26 resume — corrected image installed; measured repeated proof cost

Entry canonical local/remote9bbc6d0, context PASS; preserved ce33f40a candidate
and exact firmware-source patch matched. Fresh COM4/COM10 identities and all S3
regions matched paused backup. Official app-only OTA1 write/readback PASS;
table/otadata/NVS/OTA0/outbox/state byte-identical; official selector then boot
OTA1 at0x420000/version9bbc6d0-dirty/ELF1140ce12c verified. C3 ordinary authenticated
rejoin session109 PASS; S3 durably admits retained original107/41..52 and sends
ACKs without recommissioning. These are not controlled TC001 injections.

Physical target repeatedly performs ~2-second RSA pair signatures during trust
lookups. A real authority request returned200 but subsequent TLS write saw EOF,
and target reports time/authority refresh failure/publication fenced. Existing
HTTPS deadline begins before identity lookup and is5 seconds; repeated unchanged
private signing consumes that budget. No timeout/trust requirement is relaxed.

BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=GS117/GS68 bounded authenticated CloudSync integration
DECISION_IDS=NONE
TASK_SCOPE=One-entry RAM cache of successful immutable credential proof, bound by
length-prefixed SHA256 to full certificate/private-key/fingerprint bytes; reuse
existing verifier for both config and CloudTrust. No plaintext cache/key export.
Live Home/epoch/authority/revocation/certificate-time checks remain on every use.
OUT_OF_SCOPE=Production credential lifecycle, alternate transports/frameworks.
VALIDATION_PLAN=Existing bootstrap/provider/security tests plus permanent
GS117-CLOUD-PAIR-CACHE-001 cache-hit count and live revocation/time/fingerprint
rejection tests; target build, preserved-state app-only update if needed, real
CloudSync proof. No physical injection yet.


### 2026-10-26 — current resume runtime and precise next physical gate

The earlier paused-state note is superseded: ce33f40a was app-only deployed,
full readback/erased tail verified, selected and physically boot-verified at
OTA1@0x420000/version9bbc6d0-dirty/ELF1140ce12c. Protected table, NVS,
OTA0 recovery, outbox/state were byte-identical before first boot; otadata was
unchanged by the app write, then intentionally updated by the official selector.
Actual C3 ordinary rejoin109 and durable S3 original107/41..52 admissions/ACKs
were observed; duplicate retries kept record count52. C3 not reflashed or
recommissioned. This is real local-radio/recovery evidence, not TC001 injection.

A subsequent ce33 restart reproduced task-watchdog backtraces on both cores.
Exact preserved ELF1140ce12c symbolization places CPU0 in private RSA signing
through ProvisionedS3CloudTrust/current_binding/CloudSync health refresh, and
CPU1 in the same private signing through config.valid_material_shape and the
existing authority-refresh task. Real authority HTTP200 and SSL EOF/target
publication fences accompany the repeat work; no completed event receipt exists.
Do not treat an HTTP200 authority request as CloudSync event acceptance.

The new isolated one-entry proof cache hashes length-prefixed full certificate,
private-key bytes and fingerprint, keeps only a32-byte digest in RAM under a
mutex, and memoizes only successful cryptographic proof. No secret is logged,
no plaintext proof cache persists, and normal production DS validation is
unchanged. Authority/Home/epoch/revocation, time and certificate validity are
still checked on every provider use. New GS117-CLOUD-PAIR-CACHE-001 proves16
repeat reads do not re-sign and cached proof cannot bypass revocation, missing
time or changed fingerprint. Bootstrap85/provider tests and full target build
PASS. Existing HTTPS/watchdog deadlines and security checks were not relaxed.

Prepared full-product image2273344 bytes:
SHA256 c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16;
ELF c77483102425bcb77b95df4570b09168f64cd290522705d92241dc766da39e0c.
Owner-only manifest/BIN/ELF/sdkconfig/source patch:
current session proof-cache-ready/. BUILT_TESTED_NOT_WRITTEN.
The current resume explicitly names ce33, so a precise new-image authorization
was requested asynchronously before any further write. No reply means no
permission. Proposed scope: COM10 official selector0 for interrupted-write
safety, app-only OTA1 replacement/readback, then selector1/expected reboot and
same protected encrypted config. OTA0 b92e8544 and both current apps/protected
data are backed up; no eFuse, partition, NVS, identity, ownership or outbox erase.
Current ce33 was restored with its approved encrypted bootstrap while waiting;
ordinary rejoin110 and HIL-awake C3 counters713592 were captured. Refresh current
preservation evidence before a later new-image operation, because legitimate
runtime counters/storage can now advance.

Private Airtel_Agrim192.168.1.7/24 and existing scoped443/8445 routes verified.
Existing caregiver/API authenticates Home gs177-test-product at stable
https://desktop-3qqu64b.local; monitoringUNKNOWN/freshnessSTALE. Console already
listens only localhost18791, no active run; actual fixture/phone/ingress receipts
remain missing. No ADB interface found. Phone current Home/origin/version was
requested; no evidence is invented. No controlled INJECT_MOTION issued.

Affected Hub/contracts/backend/PWA and board E2E regression campaign is running.
After the full Hub campaign, remaining suites reuse only original PASS rows
reverified with existing verify_receipt (source/profile/log/artifact hashes);
stale artifacts and mandatory failures are rerun by the registered gates.
The original make coordinator is held between components only for that reuse;
no mandatory stage is skipped. Final stage/count/failure receipts follow below.
Source code remains stable during the campaign; Markdown/public evidence updates
do not alter firmware or executable tests. GS117 Jira11684 records actual
ce33 deployment and new-image gate. TC001 NOT_RUN; physical CloudSync and actual
Android acceptance remain unverified. No new Home/account/backend/issuer exists.


### Current bounded-service and approval checkpoint

The one-hour signed-time and physical-ingress trial was stopped cleanly before
its window expired. Exact owned ingress PID222363 and Windows signed-time
PID11820 were checked before shutdown. Existing caregiver service remains active;
PostgreSQL, the Home, credentials and scoped Windows forwarding remain untouched.
There is currently no physical-ingress8445 listener. Restart the same existing
components with a fresh bounded window before further target verification; stale
READY files are historical receipts, not proof of a running service.

No c26 image write occurred. The specific new-image approval and current phone
Home/origin/version question remain unanswered. Do not infer permission from
elapsed time. ce33 remains the last physically boot-verified app. Preserve OTA0
recovery and refresh the complete current protected-data backup before any later
approved write, since ce33 legitimately advances runtime/storage counters.

Software gates are not acceptance: initial Hub52/55 stages PASS (FAIL overall:
existing migration, P0 PARTIAL, and one GS178 browser timeout). Without changing
assertions, the exact timed-out browser case passed on a focused diagnostic
rerun, then the full registered GS17833/33 passed in the Contract campaign.
Contract47/48 PASS (FAIL overall: P0 PARTIAL); Backend24/26 PASS (FAIL overall:
P0 PARTIAL and existing Python static.css budget). All mandatory failures retain
nonzero gate exit. PWA/browser and board campaign final receipts follow below.


Current physical acceptance ledger (2026-10-26 resume):

| Stage | Status | Observed evidence / limitation |
| --- | --- | --- |
| Exact COM4/C3 and COM10/S3 identity | PASS | Live Windows USB metadata and ROM S3 MAC match approved fixture. |
| ce33 app-only install / recovery preservation | PASS | Full OTA1 readback plus protected-region equality before boot; OTA0 b92e8544 retained. |
| Running S3 product / storage / ordinary C3 rejoin | PASS | OTA1 offset/ELF matched; enrolled1/storage epoch1; rejoin109/110 and durable retained admissions. |
| C3 HIL-awake runtime/sensing | PASS | Unchanged OTA0 image591e9016; increasing runtime/sensing counters; no C3 flash/commissioning. |
| Existing trusted Private LAN443/8445 routes | PASS | Airtel_Agrim dynamic192.168.1.7/24; scoped existing rules preserved. |
| Real S3 client-authenticated authority endpoint | PASS | GS179 records actual physical S3 authority HTTP200; not an event receipt. |
| S3 sustained time/authority/CloudTrust refresh | FAIL | ce33 repeated private signing on both cores, watchdog and publication fence; c26 fix is not installed. |
| Physical S3 CloudSync event COMMITTED | NOT_VERIFIED | No completed physical event commit receipt. |
| Existing authenticated caregiver Home / PostgreSQL readiness | PASS | Existing gs177-test-product and certificate-verified origin ready; monitoring UNKNOWN/STALE remains visible. |
| Controlled C3 injection / new TC001 EventKey | NOT_VERIFIED | NOT_RUN; no INJECT_MOTION issued. Retained107/41..52 are not this test. |
| Same fresh EventKey exactly once in PG and caregiver API | NOT_VERIFIED | No controlled source event exists yet. |
| Actual Android event display | NOT_VERIFIED | No connected Android diagnostics or phone-side confirmation; browser results cannot substitute. |
| Overall TC001 | BLOCKED | New c26 image write awaiting specific approval, then actual physical CloudSync and phone acceptance required. |

Existing Windows launcher remains `code/tools/local/GS117-TC001-Console.cmd`;
console http://127.0.0.1:18791. Do not click Run until genuine installed-image,
active ingress/Home/epoch and phone receipts satisfy the existing owner-only
fixture guard. Keep provenance C3_HIL_INJECTED for the eventual controlled run.


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

### 2026-10-26 resumed execution — LAN proxy and physical CloudSync

Context preflight PASS at source `8303a3293af8cfcce1e56063434e8d625f9c93b8`;
local and remote canonical branch HEAD matched, tracked tree clean. Existing
untracked/ignored owner assets were preserved.

The active Windows Wi-Fi was re-read as `Airtel_Agrim`, Private,
`192.168.1.10/24`; WSL NAT address was `172.17.152.10`. The reviewed canonical
proxy script hash `01a8778b552e698deb3f80021c043a323e2410b822fda4af71d9ce36b80e2b26`
matched the reviewed copy. One visible normal-UAC run completed with exit 0. Only
the stale exact `.7` mappings were removed. Current mappings are `.10:443 →
172.17.152.10:8444` and `.10:8445 → 172.17.152.10:8445`. Netsh confirms both
GS-owned inbound rules are enabled for Private only, local `.10/32`, remote
`192.168.1.0/24`, TCP 443 and TCP 8445 respectively. No unrelated portproxy or
firewall settings were changed. Windows TCP probes to both ports passed;
certificate-verified caregiver HTTPS and PostgreSQL health passed.

The existing bounded signed-time process is active and S3 authority refreshes
returned HTTP 200. The existing GS-179 ingress process is listening on WSL
`172.17.152.10:8445`; the corrected Windows forwarding is carrying physical S3
CloudSync requests. In the owner-only ingress trace, 42 authority refreshes and
66 distinct physical C3 EventKeys (sessions 107 and 111) received HTTP 201,
`COMMITTED`, `duplicate=false`. These ambient/replayed device events are not the
controlled TC-001 event and are not acceptance evidence. The runtime remains
TEST_ONLY and foreground/bounded; `gs179-laptop-server.sh health` truthfully
continues to report Hub-ingress autostart/persistent service as
`NOT_CONFIGURED`. No caregiver backend, Home, database or event history was
replaced.

The existing Home `gs177-test-product` and caregiver origin
`https://desktop-3qqu64b.local` pass backend readiness. Monitoring is still
`UNKNOWN` and source freshness `STALE`. The C3 remains unchanged; the latest
read-only HIL observation recorded authenticated session 111 with
`runtime_live=39236`, `sensing_live=39236`, `HIL_AWAKE_TEST_ONLY`, no retained or
in-flight events. No C3 reset/reflash/recommission or S3 reflash occurred in
this continuation.

**TC-001 remains NOT_RUN.** The loopback console lists COM4 and COM10 but its
readiness is BLOCKED because the current owner-only fixture file and genuine
Android installation receipt are absent. Windows has no attached Android/ADB
device evidence, and no ADB executable was found in the checked SDK locations.
The actual APK package/version/signer/origin and event presentation therefore
remain `NOT_VERIFIED`. The owner was asked to connect the existing phone over
USB and accept its normal USB-debugging prompt, or provide a genuine phone-side
installation receipt. No HIL injection was issued, no new TC-001 EventKey was
created, and none of the session-107/111 commits is counted as TC-001.

**Next action:** after real phone installation evidence is available, assemble
the existing console's owner-only fixture from verified current device, ingress,
Home and phone receipts; run exactly one controlled C3 `INJECT_MOTION`; correlate
that original EventKey through the physical Hub, PostgreSQL and caregiver API;
then require actual APK observation (`USER_CONFIRMED` when manual). Do not reflash
or recommission either board.

### 2026-10-26 resumed Android/network checkpoint

Current canonical local/remote HEAD is `6abc9b43f3d1216f66cb2c4d871523ed33445ccd`;
context preflight PASS. Tracked worktree remains clean and all pre-existing
untracked/ignored firmware, Android and evidence assets are preserved.

The owner clarified the C3 was unplugged to connect the Android phone. The
existing proxy script was copied to Windows temporary storage only after its
SHA-256 matched canonical source (`01a8778b552e698deb3f80021c043a323e2410b822fda4af71d9ce36b80e2b26`).
The existing `PhysicalHubIngress` Start action ran once under process-only
`RemoteSigned` using the normal Windows `RunAs` elevation flow; elevated process
exit was 0. Current
Windows state is still trusted `Airtel_Agrim` Private `192.168.1.10/24` and WSL
NAT `172.17.152.10`. Portproxy rows are exactly `.10:443 -> 172.17.152.10:8444`
and `.10:8445 -> 172.17.152.10:8445`; Windows TCP probes to both ports pass.
The scoped Start path was used only for physical Hub ingress. No unrelated
mapping/firewall rule was changed.

The existing bounded signed-time operator and bounded mTLS ingress are running;
the ingress listener binds WSL `.10` NAT address on 8445, with PostgreSQL and
trusted-time readiness. The runtime's `status()` deliberately does not attest
Hub authentication and currently reports `real_hub_authenticated=NO` and
`persistent_hub_ingress=NOT_CONFIGURED`. The persisted physical trace still has
66 unique event commits, 63 authority refreshes and 8 NodeHealth requests ending
in 503; no new ingress request has been observed in the restarted listener yet.
Prior physical CloudSync commits remain valid historical evidence, but are not a
new delivery in this resumed window.

The protected read-only backend helper verified caregiver API login and Home
`gs177-test-product`, origin `https://desktop-3qqu64b.local`, and retrieved
historical physical EventKey `(c3-146393c5d158, bedroom, session 111, sequence 8)`
exactly once (`durable_count=1`, `caregiver_count=1`, kind `MOTION`, location
`Bedroom`, Hub `hub-e072a1d38d34`, epoch 1, enrollment generation 1). The total
physical baseline remains 66; none counts as TC-001. Freshness remains `STALE`
and monitoring `UNKNOWN`: no row exists in `node_health_latest`; historical
NodeHealth requests returned 503, and event commits do not refresh NodeHealth.

Windows native enumeration through the existing serial helper returns only
COM10, USB VID/PID `303A:1001`, serial `E0:72:A1:D3:8D:34` (the S3), expected
while the C3 is unplugged. After the owner connected the Motorola phone, PnP
identified `motorola edge 60 fusion`, USB VID/PID `22B8:2E81`, service `WinUSB`.
No `adb.exe` is installed in checked SDK locations, so package/signer/backend/
Home and app-screen evidence remain unavailable. The official Android SDK
Platform-Tools download page requires acceptance of its SDK license; do not
accept it on the owner's behalf.
The existing TC-001 console is blocked because its owner-only current
fixture/approval/identity file is absent; genuine phone receipt is also
unavailable. No UART injection was issued;
no new EventKey was generated; TC-001 remains `NOT_RUN`.

**Next action:** obtain the owner's acceptance of the Android SDK Platform-Tools
license or an existing approved `adb.exe` path. Then use read-only ADB commands
to record the real package/signer/backend/Home receipt and app visibility. After
those checks pass, ask the owner to reconnect C3, discover its live COM port and
identity, then perform exactly one console-controlled injection. Do not fake
receipts, count historical events, reflash or recommission either board.

### 2026-10-26 Android verified; live C3 enumeration and ingress checkpoint

Current source remains canonical `feature/r1-commercial-baseline` at
`6e7c303da38b4130b007a90248db2510af038fa0`; local and remote matched and
context preflight passed. Tracked worktree was clean before this checkpoint;
existing untracked/ignored Android, PWA, firmware, managed-component and
hardware evidence assets remain untouched.

The owner reports all three devices connected. Fresh Windows Platform-Tools
enumeration and ADB show the authorized Motorola Edge 60 Fusion as
`ZA2237MRHN`, model `motorola_edge_60_fusion`, state `device`. The existing
Parivar Saathi package is foreground, version `0.4.0-connected-lite-staging`.
Prior read-only APK evidence matches its existing artifact and records the
authenticated Home `gs177-test-product`; the app showed existing motion history.
No APK was modified or reinstalled. This is readiness/history evidence, not a
new TC-001 event.

Fresh Windows native enumeration through the existing serial helper `List`
action returned only COM10, USB VID/PID `303A:1001`, serial
`E0:72:A1:D3:8D:34` (physical S3). A Windows PnP inventory also showed only
that Espressif USB device; no C3 COM interface is present in this observation,
despite the owner's report of reconnection. Neither board serial port was opened
in this checkpoint, avoiding the documented USB-UART reset risk. C3 current
port/identity/runtime and ordinary rejoin are therefore not re-verified. No
flash, reset, recommission or injection was performed.

The owner-only `~/.config/ghar-sajag/gs117-tc001/physical-session.json` exists
with the intended physical Node/Hub, Home `gs177-test-product`, and installation
epoch 1. The console-required `fixture.json` is absent. It was not synthesized
from stale or partial records: current live C3 port/image evidence and the
required serial reset-safety receipt are not available.

The caregiver/PostgreSQL service is healthy. Historical bounded-ingress trace
contains 66 `COMMITTED` responses; these ambient/replayed physical events remain
excluded from TC-001. At checkpoint entry there was no listener/process on
TCP 8445. The existing owner-only exact-fixture GS-179 ingress launcher was
started with its protected credentials, existing PostgreSQL settings, signed-
time authority, S3 identity, Home and epoch. Process PID 26481 reports listener,
PostgreSQL and signed-time ready and binds to `172.17.152.10:8445`. It currently
reports `real_hub_authenticated=NO`, `hub_connected=NO`, and
`persistent_hub_ingress=NOT_CONFIGURED`; prior commits do not prove a current
Hub session. The launcher is bounded to one hour and remains attached to the
active execution session. No credential, backend ownership or persistent
service configuration was changed.

**Result:** TC-001 remains `BLOCKED / NOT_RUN`; no new EventKey exists. The hard
blockers are absent Windows enumeration for the C3, no current S3 authentication
to the restarted ingress, and missing current receipts needed to truthfully
create the owner-only fixture. Next, restore C3 USB enumeration and verify its
exact identity; then use the existing approved observation path and verify
live C3/S3 session plus ingress before creating the fixture and running exactly
one injection. Require the owner's actual APK visibility confirmation before
marking TC-001 PASS.

### 2026-10-26 refreshed USB enumeration checkpoint

After the owner supplied a fresh `usbipd`/PnP inventory and confirmed all
devices were cabled, the existing Windows serial helper independently listed
COM4 as USB VID/PID `303A:1001`, serial `14:63:93:C5:D1:58` (the expected C3),
and COM10 as USB VID/PID `303A:1001`, serial `E0:72:A1:D3:8D:34` (the expected
S3). The unrelated `0000:0002` descriptor-failure device is not either board.
This confirms the two USB identities without opening serial ports.

The owner-provided physical-session record and recent S3 installed-image receipt
remain available; only an S3 image receipt exists in the current fixture cache.
No current C3 installed-image receipt or reset-safe UART receipt exists. The
canonical physical validation record documents a prior C3 `USB_UART_CHIP_RESET`
on serial observation and does not qualify the existing open path as reset-safe.
Because the current request says to avoid board resets and the existing console
requires a verified reset-safe receipt, neither COM port was opened and no
`GET_STATE`, `FIXTURE_STATUS`, rejoin, or injection command was sent. The exact
owner-only console fixture remains absent and cannot be truthfully assembled
from identity metadata alone.

The official Windows ADB server was restarted and `adb devices -l` still reports
no attached Android device. Prior APK installation/Home/history evidence is
preserved, but current ADB observation is unavailable until Windows enumerates
the phone as an authorized device.

The bounded GS-179 ingress process remains active at `172.17.152.10:8445` with
PostgreSQL and signed-time ready. Current status remains
`real_hub_authenticated=NO`, `hub_connected=NO`,
`persistent_hub_ingress=NOT_CONFIGURED`; no request arrived after its restart.
The 66 historical commit responses remain excluded. No protected record,
credential, backend configuration, USB/IP attachment, firmware, or event data
was changed. TC-001 remains `BLOCKED / NOT_RUN` with no new EventKey.

**Exact next action:** obtain a physically verified reset-isolated serial
observation/control path for the C3 (the documented COM4 open can reset it), or
an explicit owner decision that accepts this known reset risk for the necessary
read-only status and single injection workflow. Also restore Windows ADB device
enumeration for actual APK confirmation. Then produce fresh current-image and
reset-safety receipts, verify live C3/S3 authentication and ingress, and only
then create the owner-only fixture and run the single controlled injection.

### 2026-10-26 owner-reported all devices connected; identity refresh

Following the owner-provided `usbipd` and PnP information, the existing native
Windows serial helper independently lists COM4 as USB VID/PID `303A:1001`,
serial `14:63:93:C5:D1:58` (C3), and COM10 as `303A:1001`, serial
`E0:72:A1:D3:8D:34` (S3). The separate unknown `0000:0002` descriptor-failure
device does not appear as either COM identity. The currently active network is
still `Airtel_Agrim` / Private / `192.168.1.10`; the existing scoped mappings
remain `.10:443 -> 172.17.152.10:8444` and `.10:8445 -> 172.17.152.10:8445`.
No network settings were changed.

No serial port was opened. The canonical GS-114/GS-117 evidence records a prior
`USB_UART_CHIP_RESET` on COM4 observation and explicitly says the existing
serial-open path is not qualified reset-safe. The fixture requires a current
C3 installed-image receipt and `reset_safe_uart_verified=true`; the protected
physical session alone and USB descriptors do not establish those facts. The
current cache has a recent S3 image receipt but no C3 running-image receipt.
Therefore no `fixture.json`, `GET_STATE`, `FIXTURE_STATUS`, rejoin or injection
was manufactured or attempted.

ADB was restarted using the existing official Platform-Tools binary, but the
current Windows ADB server lists no device. Prior installed-app and Home
evidence remains valid as historical readiness evidence; no current phone-side
event observation exists.

The existing bounded GS-179 ingress remains active on `172.17.152.10:8445`;
PostgreSQL and signed-time are ready. It has not received a current physical S3
authentication or event after restart (`real_hub_authenticated=NO`,
`hub_connected=NO`, persistent configuration `NOT_CONFIGURED`). The existing
66 committed event responses predate this runtime and are excluded from
TC-001. TC-001 remains `BLOCKED / NOT_RUN` with no new EventKey.

**Next exact gate:** use an independently qualified reset-isolated UART path for
the live C3/S3 status query and eventual injection. If none exists, the owner
must explicitly decide whether to accept the documented COM4 open/reset risk;
the existing fixture safety guard remains in force until a genuine receipt is
available. Restore ADB enumeration or be ready to confirm the event on the phone
screen after backend/API verification. Only after current C3/S3 rejoin and Hub
mTLS readiness pass may the existing console fixture be completed and exactly
one controlled event injected.

### 2026-10-26 USB-port return, ADB and serial-safety refresh — 16:26 UTC

After the owner returned the C3, phone and S3 to their original USB ports, a
fresh Windows-native `List` (enumeration only; no serial handle opened) again
maps COM4 `303A:1001` / `14:63:93:C5:D1:58` to the C3 and COM10 `303A:1001` /
`E0:72:A1:D3:8D:34` to the S3. Windows PnP reports both serial devices `OK`.
The Motorola Edge 60 Fusion is again authorized in ADB. Its installed package
is `in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging`; the saved app origin is
`https://192.168.1.10/`. The app was foregrounded without changing its data.
An owner-local screenshot at
`~/.local/state/ghar-sajag/gs117-tc001/android-readiness-20261026/apk-home-screen.png`
(SHA-256 `bf78b26f43a93fe95e90d9d5b12ea9139f1f5254912865abe8fb0ef4661112f0`)
shows `CONNECTED`, the TEST_ONLY Home `gs177-test-product`, and monitoring
`UNKNOWN` / source `STALE`. It is readiness evidence, not a new-event receipt.
The latest displayed authenticated Hub contact is still 24 October.

The Android TEST_ONLY origin parser accepts a private IPv4 endpoint, and the
server certificate presented at `192.168.1.10` includes both that IP and
`desktop-3qqu64b.local` in its SAN. The APK source keeps cleartext disabled and
cancels WebView SSL errors; no TLS bypass was found. The app currently has no
stored SPKI pin, so pin continuity is not established. The console still
requires a literal `.local` origin and exact equality with the caregiver API
origin; the current APK IP origin does not satisfy that controller check. Do
not fabricate an origin receipt or relax certificate/identity validation.

The laptop backend readiness and existing Home API remain PASS. At 16:20 UTC
the bounded ingress status was listener/PostgreSQL/signed-time ready, but
`real_hub_authenticated=NO`, `hub_connected=NO`, and
`persistent_hub_ingress=NOT_CONFIGURED`. Its trace has 137 historical rows and
ends at 13:27 UTC, before the current listener start. The source CloudSync
worker submits outstanding journal entries and, when available, the current
authenticated NodeHealth snapshot; it need not issue an ingress request when
both are empty. Thus an idle Hub is plausible, but the absence of post-restart
traffic does not prove that the S3 is healthy or broken. Current S3 runtime,
outbox and authenticated session remain unobserved.

The best saved C3 physical evidence is a readback image captured at 08:44 UTC
(app SHA-256 `591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea`)
followed at 08:51 UTC by `GET_STATE`: active `ota_0`,
`HIL_AWAKE_TEST_ONLY`, `hil_build=0`, `hil_control=1`, `physical_wake=0`,
session 111, and `runtime_live=sensing_live=39236`. This is pre-port-swap
evidence; current running slot/session after cable disconnection is not
verified. No reflashing is indicated.

USB removal explains disappearance from Windows COM/ADB enumeration. If USB
was a board's sole supply it may also cause a normal power cycle, but no reset
reason was captured for this latest reconnect. This is distinct from the
historical C3 `USB_UART_CHIP_RESET` reported during serial observation. Windows
pySerial opens with `CreateFile` before applying DTR/RTS through its subsequent
serial reconfiguration, so setting DTR/RTS low before `.open()` is not a
reset-safety qualification. The existing console still lacks its owner-only
`fixture.json` and will not run with a fabricated `reset_safe_uart_verified`
receipt. No serial port was opened, no board state was changed, and no motion
was injected.

**TC-001 remains `BLOCKED / NOT_RUN`; there is no new EventKey.** No qualified
reset-isolated observation path is attached. If the owner accepts the reset
risk, the next action is to add an explicit, owner-only risk-acceptance gate to
the existing console/helper path (leaving `reset_safe_uart_verified` false),
then perform one bounded read-only `Observe`: require the exact COM identities,
set DTR/RTS low, query C3 `GET_STATE` and S3 `FIXTURE_STATUS`, and send no motion
command. Either board may reboot on open; leave both powered, allow their
existing images to boot and allow the C3 to rejoin. If either fails to recover,
stop without flashing, erasing, recommissioning or injecting. After live
C3/S3, storage and CloudSync readiness evidence, the already scoped one-event
test can proceed; the exact fresh EventKey must still be confirmed in the
physical APK.

Implementation triage for the newly approved observation gate:
`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=AGENTS.md physical
HIL authorization and existing GS117-TC001-01`; `DECISION_IDS=NONE`;
`TASK_SCOPE=one owner-approved, one-use, read-only C3/S3 observation through
the existing TC-001 console/helper`; `OUT_OF_SCOPE=motion injection, reset
commands, firmware/credential/storage changes, or any assertion that the UART
path is reset-safe`.

### 2026-10-26 16:39 UTC — returned USB devices and one-use observation

The owner returned the C3, S3 and phone to their stable USB connections. A fresh
Windows-native enumeration through the existing helper identifies COM4 as C3
`14:63:93:C5:D1:58` and COM10 as S3 `E0:72:A1:D3:8D:34`; Windows PnP reports
both serial interfaces `OK`. The unrelated descriptor-failure device is not in
the serial-port list. The official `adb.exe` was found recursively under
Downloads; the authorized Motorola Edge 60 Fusion is online. Package
`in.gharsajag.caregiver.discoverytest`, version `0.4.0-connected-lite-staging`,
is installed with `MainActivity` foreground. This confirms ADB/app presence, not
a fresh event display or a newly verified backend/Home session.

After the owner authorized one read-only observation, the existing native
helper opened only COM10 and COM4 with DTR/RTS low, queried S3 `FIXTURE_STATUS`
and C3 `GET_STATE`, and closed both ports. The one-use owner-only approval was
consumed. Sanitized captured evidence is
[`observe_20261026T163858Z.json`](observe_20261026T163858Z.json), SHA-256
`654240822971719bc1999f561ac604c0ec438f941238f75972423aa02d1a6880`.

C3 answered `GET_STATE` from OTA0 in `HIL_AWAKE_TEST_ONLY` (`hil_build=0`,
`hil_control=1`, `physical_wake=0`), session 118, but `runtime_live=0` and
`sensing_live=0`. No C3 reset transcript appeared in this capture. S3 booted
the product composition from partition `0x420000` (observed version
`9bbc6d0-dirty`, ELF SHA prefix `c77483102`), but did not report
`HIL_FIXTURE_STATUS`, HubRuntime, mounted product storage or CloudSync. Instead
it logged `TEST_ONLY authenticated configuration unavailable` with
`ESP_ERR_INVALID_SIZE`, called `abort()`, then logged
`rst:0xc (RTC_SW_CPU_RST)`. This reset transcript follows the S3 startup abort;
it is not evidence of a USB power-cycle reset reason. The cause of the initial
boot seen in this 10-second capture cannot be distinguished from a prior cable
power cycle or serial-open reset.

Source correlation identifies a test-tool sequencing defect: the S3 startup
path receives its GS40 configuration before HubRuntime command parsing. The
observer sent plain-text `FIXTURE_STATUS` before seeing a command-ready marker;
the first four bytes (`FIXT`) exceed the receiver's accepted envelope-length
range. The following `ESP_ERR_INVALID_SIZE` and startup abort are consistent
with those bytes being consumed as the frame length. No encrypted configuration
envelope, explicit NVS/partition write, firmware write, commissioning or motion
command was sent. The abort means current NVS contents were not freshly
verified.

The existing helper now sends `FIXTURE_STATUS` only after the S3 advertises
`HIL_FIXTURE_READY` with that command, and skips it while a GS40 configuration
challenge is pending. Regression `GS117-S3-STATUS-GATE-001` and the existing
registered console suite pass (32 tests). The helper does not assert reset
safety. The TC-001 console's normal owner fixture remains absent; its Run path
is still blocked. Current C3/S3 authentication, HubRuntime, storage and
CloudSync are not verified. No event/EventKey was generated, and TC-001 remains
`NOT_RUN`; Android ADB is online but no fresh motion was observed in the APK.

Implementation triage:
`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=existing GS117
serial-observer contract and GS40T/1 frame parser`; `DECISION_IDS=NONE`;
`TASK_SCOPE=gate the existing S3 status query on explicit runtime command
readiness and cover its secure-config-wait negative case`;
`OUT_OF_SCOPE=any second serial observation, S3 bootstrap/write, firmware
change, C3 injection, reset/recommission, or reset-safe claim`.

Delivery checkpoint: canonical branch `feature/r1-commercial-baseline`;
implementation commit `b04d700ed91a59e9426ec76d7cb0471be012fd3e` was pushed and
matched the remote. Focused console tests (32) and feature traceability tests
(22) pass; context preflight passes. Only the intended eight implementation and
evidence files were committed. Existing untracked firmware, Android, hardware
evidence and owner-local credentials were preserved and not staged. The final
HEAD including this handoff closeout is recorded in the latest GS-117 Jira
comment.

### 2026-10-26 — S3 configuration recovery preparation (physical approval pending)

Owning Jira: GS-117, with GS-68/GS-179 integration evidence. Reuse the existing
protected bootstrap/operator scripts, installed OTA1 c26 application, fixture
CA/Hub credential, signed-time service and PostgreSQL ingress. No issuance,
enrollment, firmware or storage-layout change is planned.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=GS117 bounded physical
recovery and live C3 counter verification`; `DECISION_IDS=NONE`;
`TASK_SCOPE=optional bounded GET_STATE polling inside the existing open serial
observation, so recovery can verify increasing counters without reopening S3`;
`OUT_OF_SCOPE=firmware/security/protocol changes, motion injection and physical
execution before the owner approves the exact recovery attempt`.

The existing registered GS117 console/helper suite owns positive, invalid-option
and no-command-during-GS40-receive regressions. Host-only tests cannot establish
physical recovery or TC-001 acceptance; no commercial release gate is claimed.

Preparation results (no board port opened): exact Windows USB metadata still
matches COM4/C3 `14:63:93:C5:D1:58` and COM10/S3 `E0:72:A1:D3:8D:34`.
`Airtel_Agrim` is Private at dynamically observed `192.168.1.10/24`; existing
443/8445 routes match that address. Caregiver TLS validates through the existing
CA for both the IP and `desktop-3qqu64b.local`. Backend authority remains the
same Home/epoch/enrollment; the existing 66 events remain historical.

All 16 saved pre/post-deployment region backups match their manifests. The
saved installed OTA1 prefix matches c26 SHA-256, and its embedded configuration
root matches the existing protected root key/public DER. The existing Hub
certificate is current, RSA-3072, ClientAuth, paired with its private key and
registered ACTIVE for exact Hub generation 1. Existing key/certificate files
match the protected trust backup and are owner-only. No new credential was
issued, and no saved Wi-Fi secret was fetched during preparation.

Existing bounded host services were restarted from the prior operator scripts
in owner-only runtime directory
`~/.local/state/ghar-sajag/gs117-tc001/s3-runtime-recovery-20261026T170152Z/`.
The initial ingress start lacked the existing Python dependency environment;
it failed before listening. Reusing the established GS179 Python/LD paths
corrected startup. Ingress now reports listener/PostgreSQL/trusted-time ready
on WSL `172.17.152.10:8445`; Windows signed-time is ready on
`192.168.1.10:4468`. Both are bounded to 3600 seconds, without autostart or
firewall changes. A TCP route check used no client certificate and is not Hub
authentication. `real_hub_authenticated=NO` / `hub_connected=NO` remain honest.

The existing Motorola is authorized in ADB. The existing app was opened without
changing its data; the actual screen shows CONNECTED, Home
`gs177-test-product`, monitoring UNKNOWN/source STALE. Its saved origin is
`https://192.168.1.10/`, without a stored SPKI pin. Owner-only screenshot
`android-caregiver-screen.png` is readiness evidence only. Remaining console
gates include the missing full fixture receipt, reset-risk handling for an
event run, and its strict `.local`/exact-origin check against the phone's
CA-verified IP origin. None was bypassed or represented as PASS.

**Prepared physical operation — explicit approval pending:**

1. Recheck the exact USB identities, Private network, unchanged helper and live
   services. Open COM10 and COM4 once, DTR/RTS low. Either native-USB serial open
   or close may reboot a board; this remains unqualified as reset-safe.
2. Use the existing S3 native-USB `HardReset(uses_usb=True)` once to obtain a
   fresh boot/challenge. Require OTA1 offset `0x420000`, version
   `9bbc6d0-dirty`, ELF prefix `c77483102` before sending anything confidential.
   This is an application reboot, with no ROM flash write or OTA selection.
3. Use the same approved saved Windows Wi-Fi profile and existing protected
   fixture keys to generate one challenge-bound encrypted/signed GS40 frame.
   Keep plaintext only in memory. Send it once; send no `FIXTURE_STATUS` at any
   point in this attempt. Do not issue or replace credentials or enrollment.
4. Observe up to 60 seconds, polling only C3 GET_STATE every 10 seconds on the
   same handle. Record actual S3 acceptance/startup/storage/time/CloudTrust,
   ordinary C3 rejoin and counter progression, and actual backend mTLS traffic.
   No INJECT_MOTION is part of this approval request.
5. Close both handles and stop on mismatch, rejection, timeout or crash, with
   no retry, flash, erase, selector change or commissioning fallback. A failed
   bootstrap may leave S3 waiting for configuration/restarting; preserve power
   and report the exact evidence. Existing recovery image/backups are retained
   but this operation does not authorize their deployment.

Configuration/Wi-Fi credential material is RAM-only (`WIFI_STORAGE_RAM`).
Successful normal runtime may advance authenticated time/security counters,
journal acknowledgements and ordinary durable state; it does not promise
byte-identical live NVS. No raw persistent-region write or deletion is planned.

The prepared operator script reuses the successful bootstrap, pins the reviewed
helper hash, refuses execution without the exact owner approval marker and
creates an exclusive one-attempt marker before launching the child. Challenge
wait is capped at 30 seconds and subsequent completion at 85 seconds; there is
no automatic retry. Host preflight plus the physical attempt are bounded to
approximately three minutes. Current script SHA-256:
`e760c04dd312b3b1078862cd1973496e42e2f1f9e3eed595f25963c2c76c0278`.
Running it with approval absent was verified to stop before device access;
`recovery-attempt.started.json` does not exist. Its owner-local path is
`s3-runtime-recovery-20261026T170152Z/gs117-protected-bootstrap-current-network.py`.

Validation: existing console/helper suite 32/32 PASS (including default one-query
behavior, bounded polling, invalid intervals, challenge-only, stale READY plus
challenge, and absent READY exclusion); feature mapping/framework 22/22 PASS;
Python compilation, diff whitespace and context preflight PASS. Firmware,
board-stack and release suites are NOT_RUN for this host-only preparation.
Preparation base is canonical local/remote
`940256596d73e7beff4877f42dc048932df8983a`; final scoped delivery SHA is recorded
in GS-117 Jira. Owner-local runtime files, credentials, screenshots and existing
untracked/ignored assets remain outside the commit. No board serial handle was
opened in this preparation task.

### 2026-10-26 17:11 UTC — approved recovery executed, product Hub/CloudSync PASS

Owner approved the exact prepared attempt. Canonical context PASS at local and
remote `8b936b167d30850761e8882d6193e133ce89c7f2`; prepared script and helper
hashes unchanged, attempt marker absent, exact COM4/COM10 USB identities,
Private Airtel_Agrim/.10, existing routes, ingress and signed-time reverified.
The approval was recorded owner-only, then the prepared script ran once and
exited 0. No retry, firmware write, OTA selection, C3 reset command, enrollment
change or motion command was performed.

Physical evidence is in
[`recovery_20261026T1711Z.json`](recovery_20261026T1711Z.json); complete sanitized
capture and operator logs remain in the protected preparation directory.
The explicit S3 application reset produced the expected OTA1 boot at
`0x420000`, version `9bbc6d0-dirty`, ELF prefix `c77483102`. The existing
encrypted configuration frame (7326 host bytes) was accepted, with target TLS
identity validation `valid=1`, PSA pair proof and 2960 bytes minimum free stack.
Host exchange took 1750 ms. `FIXTURE_STATUS` sent count was zero.

The product Hub reached `Authenticated Hub owner started enrolled=1
storage_epoch=1` and the correct Hub/Home binding. Source guards require a
successful gs_outbox LittleFS mount, authenticated native outbox recovery and
persistent journal before that log; restored outbox events also reached the
backend. No abort/watchdog/backtrace appeared during this roughly 70-second
capture. An initial time/authority refresh failure was logged; later signed
time requests and repeated authenticated authority HTTP 200 responses recovered
without intervention.

S3 logged ordinary authenticated C3 rejoin at uptime 69241 ms, logical bedroom,
session 118, then Node liveness online. Six GET_STATE samples, ending before
that rejoin, all showed zero runtime/sensing counters. Therefore authenticated
rejoin is PASS but increasing counters are NOT_VERIFIED, not a demonstrated C3
firmware failure. No second port open was used to obtain a later sample.

Actual physical S3 mTLS/CloudSync is PASS for recovered retained EventKeys
`(c3-146393c5d158, bedroom, 112, 1)` and `(…,112,2)`: HTTP 201 COMMITTED for
both, plus one duplicate=true HTTP 200 retry for key112/1. Read-only PostgreSQL
and authenticated caregiver API checks find exactly one durable record and one
projection per key, committing Hub `hub-e072a1d38d34`, Home
`gs177-test-product`, ownership epoch/enrollment generation 1. The prior 66
records remain and the count is now 68. These are retained recovery events,
not a fresh controlled TC-001 event or REAL_PIR qualification.

Current runtime `status()` returns literal NO for its Hub-authentication and
connection fields; those values are placeholders, not measurements. The
authenticated listener trace establishes actual mTLS success despite them.
Do not reinstate a false authentication blocker from those static fields.

NodeHealth HTTP 503 is a separate demonstrated fixture-data collision:
PostgreSQL reports duplicate unique key
`node_health_latest_home_id_logical_node_id_key`. Read-only inspection finds
the stale latest-health bedroom row belongs to `test-c3-bedroom` /
`test-hub-product`, while both that synthetic enrollment and the physical
C3/Hub bedroom enrollment remain ACTIVE in the same Home. No row, enrollment,
credential or historical event was removed/changed to conceal this conflict.
Monitoring remains UNKNOWN/source STALE. Classification is INVESTIGATE_ONLY for
an existing TEST_ONLY fixture lifecycle/configuration conflict; no commercial
transfer implementation or ownership mutation was undertaken.

The existing APK/CA-verified IP origin and actual CONNECTED/Home readiness from
preparation remain the available phone evidence; no controlled event was sent
or confirmed in the APK. TC-001 remains NOT_RUN. Bounded ingress/signed-time
services remain running for their original one-hour windows; no persistent task
was added. Firmware, protected backups, owner-local secrets and unrelated assets
are preserved.

Next exact work: resolve the live synthetic/physical fixture conflict using the
existing authorized lifecycle while preserving historical events; obtain later
C3 status samples without reopening/resetting the now-running S3; reconcile the
existing console's truthful fixture/reset-risk and verified IP/DNS-origin gates.
Only then may a separately scoped controlled injection be executed and the
original EventKey confirmed on the actual APK. This recovery approval included
no injection or further port operation. Host suite receipts from unchanged
8b936b1 (32 console/helper tests and 22 mapping tests) are reused; no release,
new firmware build or optical acceptance is claimed.

### 2026-10-26 — working pipeline preservation and verified-origin correction

Owner personally confirmed new Bedroom Motion events visible in the actual APK
after recovery. Classification: USER_CONFIRMED recovery/application visibility;
no exact EventKey or observation timestamp supplied, and not a controlled
TC-001 injection. Preserve candidate-key correlation separately from this
statement. Owning Jira GS-117/GS-179; no physical control or injection in scope.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=existing GS117 console
origin gate and GS179 CA/hostname-verified endpoint selection`;
`DECISION_IDS=NONE`; `TASK_SCOPE=allow the actual APK's current private-IP HTTPS
origin only after both IP and canonical DNS TLS identities verify against the
existing CA and exact installed server leaf certificate`;
`OUT_OF_SCOPE=TLS bypass, trust/certificate changes, enrollment mutation,
hardware access, persistent-service enablement or motion injection`.

Affected components: existing endpoint helper and TC001 console fixture gate.
Reuse registered endpoint/console suites; add actual loopback TLS positive and
wrong-CA/SAN/leaf/address cases and fixture integration rejection tests. Existing
serial timing/security/receipt gates remain intact. This is host tooling only;
no firmware build or physical qualification is implied.

## Working pipeline preservation and startup runbook — 2026-10-26

This is the maintained reference for the existing single TEST_ONLY fixture,
owned by GS-117/GS-179/GS-68. GS-148 owns the health/ownership collision.
Preservation baseline local/remote: `8003b7024df928f2b1922831d9194b83c64b0563`.
No hardware control, injection, enrollment mutation, credential issuance,
service-persistence or network-policy change occurred in this checkpoint.
Final delivery SHA is recorded in the GS-117 Jira comment.

### Verified working state

| Component | Preserved state and evidence |
| --- | --- |
| C3 | COM4, `c3-146393c5d158`, USB `14:63:93:C5:D1:58`, OTA0, HIL_AWAKE_TEST_ONLY; HIL_BUILD=0/HIL_CONTROL=1/PHYSICAL_WAKE=0. Saved readback SHA `591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea`; official offline descriptor `gs_hw_m1_node`, `8cbda4b-dirty`, IDF v6.0.3. No readback repeated. |
| S3 | COM10, `hub-e072a1d38d34`, USB `E0:72:A1:D3:8D:34`, product OTA1 `0x420000`; SHA `c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16`, `gs_r1_s3_hub`, `9bbc6d0-dirty`, ELF `c77483102425bcb77b95df4570b09168f64cd290522705d92241dc766da39e0c`, IDF v6.0.3. Recovery OTA0 preserved. |
| Radio/ownership/storage | Existing Home `gs177-test-product`, epoch1, physical Node enrollment generation1. Authenticated ordinary session118 rejoin and Node liveness online. Guarded product gs_outbox mount/native recovery and owner-start enrolled1/storage_epoch1. Counter samples preceded rejoin; increasing counters not claimed. |
| Backend | Existing PG/caregiver HTTPS, physical mTLS8445, signed-time4468. Sustained actual authority HTTP200, retained physical keys112/1 and112/2 COMMITTED, one row/API projection each, duplicate retry suppressed. Original66 records retained, total68 at checkpoint. |
| Android | Existing `in.gharsajag.caregiver.discoverytest`, v0.4.0-connected-lite-staging, saved `https://192.168.1.10/`, Home correct. Actual installed APK SHA `0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76` preserved; no reinstall. |

Owner personally confirmed new Bedroom Motion visible after recovery:
**USER_CONFIRMED** recovery/application visibility. No exact EventKey or phone
observation time was supplied. The most recent correlated candidates are
physical session112 sequence1 (delivery17:11:53 UTC) and sequence2
(17:12:25 UTC). Their API chronology/counts and the separate owner statement
are in [preservation_20261026.json](preservation_20261026.json). Do not claim
that the owner individually identified either key, or fabricate an APK capture.
**TC-001 remains NOT_RUN**: no controlled C3_HIL_INJECTED event was generated.
Optical PIR acceptance remains separate.

### Git and protected preservation inventory

Git contains the production firmware/security/storage/API implementations,
serial helper, GS40 envelope and signed-time code, issuer contracts, GS179
listener/PG composition, LAN proxy, APK source, console, tests and sanitized
reports. Private credentials/configuration, binaries and raw backups stay out.

Owner-only verified checkpoint directory:
`~/.local/state/ghar-sajag/gs117-tc001/working-pipeline-checkpoint-20261026T173535Z/`.
`MANIFEST.json` records relative paths, sizes, modes and hashes; every recorded
file was read back and verified. It contains existing fixture trust/keys and
consistent issuer SQLite backup; backend TLS/server.env/login/user unit;
C3/S3 binaries and official image metadata; dated verified S3 deployment
snapshots; runtime PG/Python dependencies; actual installed APK; protected
operator scripts; origin proof, original evidence and owner confirmation.

A standard consistent `pg_dump` custom archive is included. Matching-major18
Ubuntu client tools were downloaded/extracted locally, without installing a
service. Archive listing and full `pg_restore --file=/dev/null` decode PASS;
a live restore/fault restart was NOT_RUN. Global DB roles/system OS state are
not a full-machine backup. Do not copy the running PG data directory or
restore over the live database. Any restoration needs an approved clean-target
plan. Raw NVS/outbox/state snapshots are dated deployment evidence, not current
security-counter state or authority for blind rollback.

No saved Wi-Fi secret was exported/stored. The protected bootstrap retrieves
the approved Windows profile into memory only during an authorized operation.
Do not run `provision` to restore working identities/credentials.

### Safe initial checks and backend startup

```bash
cd /home/udaybhan/projects/Ghar_sajag_r1
tools/context/ghar_sajag_context_preflight.sh
git branch --show-current
git rev-parse HEAD
git ls-remote origin refs/heads/feature/r1-commercial-baseline
ip -4 -o addr show dev eth0
systemctl --user is-active gs179-laptop.service
bash code/tools/local/gs179-laptop-server.sh health
```

If endpoint bindings/certificates are unchanged and the existing unit is
inactive, use `systemctl --user start gs179-laptop.service`. That existing unit
starts PG and caregiver HTTPS. It is already enabled with Restart=on-failure;
Linger=no, so an active WSL user manager/session is required. Do not enable
linger/tasks here. Windows boot is not qualified unattended WSL startup.
`gs179-laptop-server.sh start/restart/network-refresh` also refreshes endpoint
configuration/restarts/proxies; it is not a read-only health check.

Serial List action reads Windows metadata only. Do not open either COM port to
check health: native USB open/close can reset a board. Observe running S3 via
actual authority/event receipts. Current ingress status() hardcodes auth and
connection NO; these placeholders do not override actual authenticated traces.

### Trusted Windows forwarding after address changes

Use only existing `code/tools/local/gs179-windows-lan-proxy.ps1`, reviewed
against canonical source/hash before elevation. In Windows PowerShell:

```powershell
$script = '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\code\tools\local\gs179-windows-lan-proxy.ps1'
$p = Get-NetConnectionProfile -InterfaceAlias 'Wi-Fi'
if ($p.Name -ne 'Airtel_Agrim' -or $p.NetworkCategory -ne 'Private') { throw 'Trusted Private Wi-Fi required' }
$line = wsl.exe -d Ubuntu -- ip -4 -o addr show dev eth0
if ($line -notmatch '\binet\s+([0-9.]+)/') { throw 'Current WSL IPv4 missing' }
$wslAddress = $Matches[1]
foreach ($endpoint in @('Caregiver','PhysicalHubIngress')) {
  powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File $script -Action Audit -EndpointKind $endpoint -WslAddress $wslAddress
}
```

Repair only if needed: use the same script/arguments with Action Start through
normal UAC (`Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList ...`),
process-only RemoteSigned. Supply PreviousWslAddress only from the preserved
GS179 target record if replacing a stale owned target. The script discovers
Wi-Fi IP/subnet and limits the exact named rules:443→8444 and8445→8445.
Action Stop for the exact endpoint is the existing rollback. Never guess/delete
unknown entries, allow Public networks, use unrestricted rules or RegisterWatch.
If a new IP is absent from TLS SANs, the existing network-refresh-config /
approved leaf refresh is a protected configuration write; do not silently
reissue certificates. No such change was needed/performed here.

### Fresh bounded host services using the existing protected scripts

Do not overwrite historical logs or reuse a consumed attempt marker. Prepare
fresh code copies/evidence only (this snippet does no device I/O):

```bash
umask 077
python3 - <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import ast
backup = Path.home()/'.local/state/ghar-sajag/gs117-tc001/working-pipeline-checkpoint-20261026T173535Z'
run = backup.parent/('fixture-session-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
run.mkdir(mode=0o700)
for source in (backup/'operator-scripts').glob('*.py'):
    tree = ast.parse(source.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'state' for t in node.targets):
            node.value = ast.parse('Path('+repr(str(run))+')', mode='eval').body
    target = run/source.name
    target.write_text(ast.unparse(tree)+'\n')
    target.chmod(0o600)
print(run)
PY
```

Verify protected-template manifest hashes first. Set GS117_SESSION_DIR to the
printed directory; do not start duplicates if8445/4468 already have a listener.
The existing scripts require these established dependency paths:

```bash
export PYTHONPATH="$HOME/.local/share/ghar-sajag/gs179-laptop/python-deps${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$HOME/.local/share/ghar-sajag/gs179-laptop/postgres-root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
nohup python3 -u "$GS117_SESSION_DIR/gs117-active-ingress.py" >"$GS117_SESSION_DIR/ingress-service.log" 2>&1 &
printf '%s\n' "$!" >"$GS117_SESSION_DIR/ingress-operator.pid"
nohup python3 -u "$GS117_SESSION_DIR/gs117-start-existing-signed-time.py" >"$GS117_SESSION_DIR/signed-time-operator.log" 2>&1 &
printf '%s\n' "$!" >"$GS117_SESSION_DIR/signed-time-operator.pid"
```

Both stop after3600s; no persistent task/autostart. Ingress uses measured WSL
private bind; signed-time uses verified current Windows Private address. Check
READY, listener/PG/time status, then genuine S3 authority/event receipts. Stop
only session-recorded PIDs; SIGNED_TIME_READY records the exact Windows child
PID for ordinary Stop-Process if needed. Existing Home/issuer/epoch are reused.

### S3 encrypted startup and C3 rejoin

Do not reset/bootstrap a healthy S3 following only a host-service restart.
Existing15-second station/time/authority refresh can recover while its RAM
configuration remains valid. A real S3 reboot loses TEST_ONLY RAM configuration
and Wi-Fi credentials. Its existing GS40 receiver then requires a fresh
challenge-bound encrypted frame; never replay cached ciphertext. The fixture
script sets a one-hour envelope expiry; expiry fences time/authority refresh.
Host restart alone does not extend the envelope.

Only after explicit current approval for exact serial/reset/config risks,
use the copied, reviewed existing bootstrap once:

```bash
env GS117_APPROVED_RECOVERY=GS117-S3-RUNTIME-RECOVERY-ONE-ATTEMPT \
  python3 "$GS117_SESSION_DIR/gs117-protected-bootstrap-current-network.py"
```

It opens exact COM10/S3 and COM4/C3, resets S3 once, checks OTA1/version/ELF,
sends one encrypted frame from existing protected material and observes bounded
status. The environment marker does not substitute for owner approval; do not
set it globally. Its pinned helper hash must not be altered after a source
upgrade without review. No plaintext secret is logged/saved. Stop on rejection
or mismatch; no retry/flash/recommission fallback. FIXTURE_STATUS stays disabled
throughout bootstrap. The preserved helper independently requires explicit
HIL_FIXTURE_READY and no pending GS40 challenge before sending that text.

C3 keeps identity/association/events and rejoins normally. Long-outage
channel/backoff recovery may take about13 minutes; no reset/flash/commissioning
is needed. Do not reopen S3 to poll C3 and lose restored RAM configuration.
Samples taken before rejoin do not establish a runtime failure.

### Verify delivery and APK without generating events

Existing read-only helper example for retained recovery data (not TC-001):

```bash
printf '%s' '{"action":"event","home_id":"gs177-test-product","physical_device_id":"c3-146393c5d158","logical_node_id":"bedroom","origin_session_id":112,"event_sequence":1}' \
  | bash code/tools/local/gs117-tc001-backend.sh
```

Require durable_count=1, caregiver_count=1, original EventKey, correct physical
Hub/Home/epoch/enrollment and real mTLS COMMITTED trace. Duplicate receipt does
not mean duplicate business event. Never use seed/event/health-source generation
as a health probe. Open the existing APK with saved login; verify Home, HTTPS
origin and chronology. ADB is optional; reuse existing official Platform-Tools.
The console now accepts the current private IP alias only after live CA and
hostname verification for both names and exact installed leaf equality.
No APK origin, pin, credential or trust-policy change is needed.

### Restart reliability and remaining work

| Trigger | Existing behavior | Qualification/remaining gap |
| --- | --- | --- |
| Caregiver process crash | Existing enabled user-unit Restart=on-failure; preserved PG/config | Automated within active WSL user manager; no disruptive restart tested here. |
| Laptop/WSL reboot | Database/keys/unit persist | Manual WSL/user service and endpoint audit; Linger=no; no new auto-launch. |
| Ingress/time stop | Restart existing bounded scripts and same credentials | Manual one-hour windows, not persistent service configuration. |
| Wi-Fi/WSL IP change | Scoped proxy audit/normal-UAC repair and approved SAN refresh | Manual; no Public exposure, watch task or certificate change here. |
| Backend outage, S3 powered | Durable outbox and authenticated retry/refresh | Implemented; duplicate recovery receipt observed, no outage campaign repeated. |
| S3 reboot/envelope expiry | Fresh approved encrypted configuration | Manual TEST_ONLY recovery. RAM profile is not commercial unattended startup. |
| C3 restart/outage | Retained association/events, ordinary authenticated rejoin | Physically observed; no new restart test. |
| APK restart | Saved origin/login and reconnect logic | Working app/owner visibility confirmed; IP-change phone recovery not qualified here. |

Smallest next development improvement: explicit opt-in lifecycle composition of
the existing ingress/time processes in the existing launcher/service, with
truthful health and session bounds. Keep it disabled until authorized; do not
create another framework. Commercial release must use the existing persistent
credential/time architecture and separately qualify restart/backup restore;
this checkpoint enables neither persistence nor new provisioning infrastructure.

The NodeHealth collision is preserved: two ACTIVE synthetic/physical bedroom
enrollments and the synthetic latest-health row occupy the same Home/room.
Existing HubOwnershipRegistry.revoke_node supports scoped authenticated
retirement while retaining event history; invoking it needs explicit authority.
Revocation alone does not reclaim the latest-health unique row in current
source, so a tested authority-checked projection handover is also needed.
Do not delete rows, weaken uniqueness or silently revoke either fixture.
Track this in existing GS-179/GS-148 work; no commercial transfer implementation.

Minimum TC-001 prerequisites remain: truthful current fixture and approved
serial/reset-risk control that preserves the running S3; fresh C3 runtime/
sensing proof; one separately authorized INJECT_MOTION, original-key durable
correlation, and actual APK confirmation of that controlled event. This task
performs no hardware operation or motion injection.

Preservation validation: endpoint8 real-TLS tests PASS; existing console32
PASS (including serial timing, no-approval/wrong-fixture and alias integration
rejection); feature mapping/framework22 PASS; Python compilation, JSON parsing,
context preflight and whitespace checks PASS. Actual DNS/IP proof validates
through the same CA and installed leaf, with canonical Home readiness PASS.
The idle local console was restarted through the existing launcher to load the
fix; its missing full fixture gate remains BLOCKED, and no Run/serial action
was invoked. PostgreSQL/caregiver service and physical S3 were not restarted.
Sustained actual authority HTTP200 and ready signed-time/listener evidence were
rechecked after preservation; exact final timestamp is in preservation JSON.
Unrelated untracked/ignored assets remain intact. No full release, disruptive
restart, database restoration or new physical acceptance test was performed.

## 2026-10-26 18:31 UTC — repeatable campaign and automated Android evidence

Entry source was `b85a4dbb2de9afd666fa0cc0f1c763eafb5be0d7` on
`feature/r1-commercial-baseline`; local and remote matched and context preflight
passed. The existing code changes in progress were preserved. Existing firmware,
physical credentials, owner-only backups, APK artifacts and unrelated
untracked/ignored files were not modified. Latest Jira context read: GS-117
comment 11714, GS-179 comment 11715, GS-148 comment 11716, and GS-130 comment
11718 (five independently traceable TC-001 runs with automated APK observation).

BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-117 TC-001; latest GS-130 owner acceptance comment 11718
DECISION_IDS=NONE (existing physical test procedure only)
TASK_SCOPE=Improve the existing TC-001 console/Windows ADB helper for one-use,
five-run physical campaign reporting and exact-event observation in the actual
installed APK.
OUT_OF_SCOPE=Physical injection in this software checkpoint; C3/S3 firmware,
security, credential, ownership, enrollment, NodeHealth, database and network
changes; new test framework or APK build.

The existing console now models one five-run campaign under its existing
single-run lock. It validates a one-use owner-only approval bound to the exact
physical C3/S3, Home and run count before any C3 serial operation; approval
records acceptance that opening COM4 may reboot the C3. Each sequential run has
its own report, stage statuses/timestamps, original EventKey and saved result.
The campaign stops on its first non-PASS. COM10 is only enumerated and is never
opened. Serial status must report the expected HIL-awake flags, positive
runtime/sensing counters, and empty pending/retained/in-flight state before the
single injection command. A matching authenticated class-0 Node ACK establishes
S3 durable admission without an S3 UART open. Duplicate PostgreSQL counts are
retained in the failure report instead of being hidden by an early return.

The existing Windows helper now reuses the approved ADB device identity and
installed package/version receipt. Per run it foregrounds Parivar Saathi,
checks Settings for the receipt-bound HTTPS backend origin, existing Home and
`Backend API · CONNECTED`, navigates to Reports, and backgrounds/foregrounds the
same app to trigger the APK's existing visibility-change refresh. It then polls
`Latest recorded events`, expands Event details and compares the exact original
EventKey. The existing caregiver UI exposes this key, so no APK source change
was needed. A screenshot and the matching accessibility XML are retained with
0600 mode under the existing private TC-001 state directory; only screenshot
preview is served by the loopback console. GET status/evidence requests reject
foreign Origin and cross-site/same-site browser fetches; POST retains exact
Origin plus CSRF checks. The signer fingerprint is carried
from the current owner-only APK install receipt and matched to the installed
package/version; this pass did not independently re-extract a signer from the
installed APK binary.

Focused validation on the modified source: Python compilation PASS;
`python3 code/tests/python/test_gs117_tc001_console.py` PASS, 43 tests; GS-179
verified endpoint PASS, 8 tests; `make -C code feature-coverage-test` PASS,
226 feature rows / 285 source modules / 27 physical cases and 22 framework
tests. These are software/registry checks only. No ADB phone command, COM-port
open, board operation, motion injection or TC-001 event was performed here.
No actual device run of the new Android automation has yet been observed.

TC-001 remains NOT_RUN. The older physical recovery events and owner-reported
APK visibility are not campaign results. The synthetic/physical NodeHealth
collision remains unchanged, monitoring may still show UNKNOWN/STALE, and it is
not used to block event-delivery acceptance. Before campaign execution, a fresh
exact owner-only fixture/install receipt and a separate one-use approval for
exactly five consecutive C3 injections are required. The approval must accept
possible C3 reboot on COM4 open, no S3 UART open, stop-on-first-failure, and no
flash/reset command/recommission/credential/ownership/database changes. On
unexpected C3 reboot or failed rejoin, the campaign stops and existing
authenticated rejoin recovery is required; it does not flash or recommission.
The bounded listener, current phone session, COM enumeration and board runtime
were not refreshed in this software-only pass. The exact delivery commit and
remote verification are recorded in the follow-up GS-117 Jira comment.

### 2026-10-27 — current-source GS-178 and non-disruptive TC-001 readiness

At canonical starting HEAD `f6321597578bda69aa43056cbee70c863d5e625a`, context
preflight passed and local/remote HEAD matched. Read latest GS-178 and GS-117
Jira instructions and reused their existing host vertical, console, ADB
observer and ingress. No physical recovery work was repeated.

`make -C code gs178-software-e2e` passed **33/33** on current source. Five
separately isolated Bedroom Motion software E2Es each passed the production
NodeRuntime/HubRuntime/CloudSync/authenticated backend/caregiver browser path
and 17 Playwright assertions. A small test-support-only initial-session option
was added because the earlier repeated runs reused session 10 and therefore
repeated the same synthetic key. The five new synthetic EventKeys now use
sessions 42001–42005, sequence 1, with one durable database row per key; details
and individual report hashes are in
[`GS178_SOFTWARE_VERTICAL_20261018.md`](../GS178_SOFTWARE_VERTICAL_20261018.md#current-source-five-run-bedroom-motion-simulation--2026-10-27).
The existing TC-001 console/ADB tests passed **43/43**, including exact APK
EventKey positive and wrong-key rejection cases. These are all software/HOST_SIM
results, not physical or Android event observations.

Fresh non-disruptive Android evidence: the official existing Windows ADB
reported authorized device `ZA2237MRHN`, Motorola Edge 60 Fusion. Package
`in.gharsajag.caregiver.discoverytest`, versionCode 3,
`0.4.0-connected-lite-staging`, was installed; its MainActivity was foreground.
A read-only pull produced the same APK SHA-256 as the saved preservation record:
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`. The prior
checkpoint associates these APK bytes with origin `https://192.168.1.10/` and
Home `gs177-test-product`; this execution did not freshly authenticate or
inspect the Home session in the APK. A read-only accessibility dump of the
foreground activity exposed no Home, Connected or Reports label. No
`apksigner`/SDK build-tools are installed, and Android's package dump does not
provide a certificate digest.
Thus signer fingerprint is **NOT_VERIFIED**, not a pass.

The existing GS-179 health check passed PostgreSQL durability, caregiver HTTPS
and current DNS/IP TLS checks at Windows Wi-Fi `192.168.1.10`. It reported
phone LAN reachability `NOT_VERIFIED` and Hub ingress `NOT_CONFIGURED` with
autostart disabled. Port 8445 had no listener and the saved ingress PID was not
alive. A real authenticated S3 event/authority trace exists through 2026-10-26
(last event receipt `2026-10-26T17:12:25Z`, physical C3 session 112 sequence
2, COMMITTED; authority refresh at 17:47:33Z returned 200); it is historical,
not current CloudSync proof.

The owner-only console fixture
`~/.config/ghar-sajag/gs117-tc001/fixture.json` and
`five-run-campaign-approval.json` are absent. The available APK preservation
record has no exact owner phone EventKey/time confirmation. I did not create
fixture or signer receipts from historical records. Synthetic/physical
NodeHealth conflict remains unchanged and is not an event-delivery gate.
Neither COM4 nor COM10 was opened; no reset, injection, credential/ownership/
enrollment/database change occurred. TC-001 remains **BLOCKED / NOT_RUN**.

No five-injection approval is requested at this checkpoint because current
physical campaign readiness is incomplete: the mTLS service is stopped, a
fresh exact fixture/phone signer receipt is absent, and no current authenticated
S3 session was observed. Once those existing components and receipts are
current, request one approval for exactly five sequential physical C3
`INJECT_MOTION` actions through the existing console, with possible C3 reboot
on COM4 open accepted, COM10 never opened, automated APK exact-key observation,
and stop on the first failure. No firmware, reset command, re-commissioning,
credential, ownership, enrollment or database changes are in scope.

### 2026-10-27 — bounded services and current Android readiness

At source HEAD `cac55b92a00fe6fe807787ce9faa55ba42df5305`, mandatory context
preflight passed and local/remote canonical HEAD matched. No GS-178 software
suite was rerun. The existing bounded GS-179 TEST_ONLY ingress and signed-time
processes were restarted from hash-matched protected operator scripts with the
preserved fixture CA, Hub certificate, issuer registry, and time/authority
signers. The listener remains bounded to its one-hour window; ingress autostart
and persistent service configuration remain disabled.

The active Wi-Fi profile was dynamically rechecked as Private
`Airtel_Agrim`, IPv4 `192.168.1.10`. Existing scoped forwarding remained
`192.168.1.10:443 -> 172.17.152.10:8444` and
`192.168.1.10:8445 -> 172.17.152.10:8445`; Windows TCP probing of the 8445
route passed. PostgreSQL durability/TLS, caregiver HTTPS, local backend, and
endpoint certificate/DNS-SAN health passed. A fresh host-generated signed-time
challenge was verified against the preserved RSA-3072 public key (nonce and
generation bound, signature and current validity interval passed). This proves
the service endpoint, not a request from the S3. During this observation window
the ingress had zero authenticated Hub/event receipts; runtime status remained
`listener_ready=YES`, PostgreSQL/time ready, `real_hub_authenticated=NO`,
`hub_connected=NO`. The signed-time datagram counter is unattributed and is not
counted as authenticated S3 communication. Prior S3 authority/CloudSync
receipts are historical.

The authorized ADB device was `ZA2237MRHN`, Motorola Edge 60 Fusion. The
installed package is `in.gharsajag.caregiver.discoverytest`, versionCode 3,
`0.4.0-connected-lite-staging`. A fresh installed base APK pull matched the
preserved APK SHA-256 `0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`.
The certificate embedded in its APK v2 signer block had SHA-256
`d336ae68479da03de932a44b16c8de730c86e3cf68aee52fe92261e74e596b85`, matching
both preserved trusted signer digest files; its DER parsed successfully with
Python `cryptography`. Google `apksigner` was unavailable, so evidence is the
independent signer-certificate extraction/digest comparison plus exact APK-byte
match to the trusted preserved installation, not a fresh `apksigner verify`
execution.

The initial ADB UI dump was empty while the app was not top-resumed and its
WebView had not rendered. A normal explicit launch of the existing
`MainActivity` followed by readiness polling exposed the accessibility tree;
no APK reinstall, authentication bypass, or credential entry occurred. Current
Settings reported origin `https://192.168.1.10/`, Home
`gs177-test-product`, and `Backend API · CONNECTED`. Home showed caregiver API
CONNECTED with monitoring UNKNOWN/source STALE. Reports showed `Latest recorded
events` for the same Home. The real ADB observer automatically opened Event
details and matched existing physical event key
`{physical_device_id: c3-146393c5d158, logical_node_id: bedroom,
origin_session_id: 112, event_sequence: 2}`. This is explicitly
`HISTORICAL_READINESS_ONLY_NOT_TC001`; it is not a new controlled event. Private
readiness screenshots/XML and the historical observer receipt are retained
mode 0600 outside Git under
`~/.local/state/ghar-sajag/gs117-tc001/android-observe-20261027T0230Z/`.
An owner-only current Android installation receipt was created at
`~/.config/ghar-sajag/gs117-tc001/android-install-receipt-20261027.json`
(mode 0600). No TC-001 fixture or campaign approval was created.

The existing console at `http://127.0.0.1:18791/` remains blocked at its
environment gate with
`owner_only_fixture_approval_and_identity_file_missing`; its latest run
`TC001-20261027T024327-bdbb3321` injected nothing. The exact fixture was not
fabricated because there is no current authenticated physical S3 ingress
receipt or fresh S3 runtime proof. Home/API readiness and APK readiness do not
establish Hub connectivity. The known NodeHealth uniqueness conflict remains
separate (`UNKNOWN`/`STALE`) and unchanged; no enrollment or database state was
modified.

No COM4 or COM10 port was opened. No device reset, injection, flash,
recommissioning, credential/ownership change, or database mutation occurred.
The last successful physical S3 ingress/configuration evidence is historical;
the product's encrypted Wi-Fi/GS40 session is RAM-only and bounded. If it has
expired, the existing recovery procedure is the one-attempt protected
`gs117-protected-bootstrap-current-network.py` through COM10 with a fresh
challenge-bound encrypted configuration. Opening COM10 can trigger
`USB_UART_CHIP_RESET`, reboot the S3 and lose its RAM-only Wi-Fi/GS40 session;
the procedure does not flash firmware or overwrite NVS/partition/outbox/state.
The previously recorded recovery approval covered one attempt and is consumed.
This task explicitly prohibited COM10 access, so recovery was not attempted.

Focused console/ADB regression `python3 code/tests/python/test_gs117_tc001_console.py`
is 43/43 PASS for the current implementation. TC-001 remains
`BLOCKED / NOT_RUN`; five-run physical authorization was neither present nor
created. Do not request the five-injection campaign approval until a fresh
authenticated S3 receipt and exact fixture are current. The next action is one
explicit approval for the reset-aware COM10 encrypted-configuration recovery
if required, followed by fresh S3 mTLS evidence and fixture validation; the
five-injection approval remains a separate later gate. Sanitized current
readiness evidence is retained mode 0600 at
`~/.local/state/ghar-sajag/gs117-tc001/services-20261027T0230Z/readiness-observation-20261027T0255Z.json`.

### 2026-10-27 — resumed non-disruptive readiness recheck (04:30Z)

The interrupted documentation edits were preserved. Canonical context
preflight passed; at recheck entry local and origin HEAD were both
`cac55b92a00fe6fe807787ce9faa55ba42df5305`. The current Windows network was
Private `Airtel_Agrim`, `192.168.1.10/24`; WSL was `172.17.152.10/20`. Existing
443→8444 and 8445→8445 portproxy entries were present. The Windows 8445 TCP
probe passed. A TLS probe without the existing CA and without a client
certificate received the expected server certificate subject and then a TLS
handshake-failure alert. This confirms the forwarded path reaches the listener;
it is not an authenticated Hub session.

At 04:30Z, the existing laptop health command passed PostgreSQL TLS/durability,
caregiver HTTPS, local backend, and endpoint CA/DNS-SAN checks. It reported
`PHONE_LAN_REACHABLE=NOT_VERIFIED`, Hub identity unauthenticated, freshness
UNKNOWN, and persistent ingress NOT_CONFIGURED. The bounded TEST_ONLY ingress
and signed-time operator were alive; ingress status at 04:30:07Z was listener,
PostgreSQL and trusted-time ready, but `real_hub_authenticated=NO` and
`hub_connected=NO`. No current physical receipt or ingress trace row was
created. Windows UDP 4468 was bound. The separately saved host-generated
RSA-3072/SHA-256 challenge at 04:22:20Z passed nonce and generation matching
and was valid at that observation through 04:24:20Z; it is host-only evidence,
not S3 traffic or a current proof beyond its validity window. The one-hour
bounded processes expire around 05:19Z; no persistent startup was enabled.

The private Android receipt is timestamped `2026-10-27T02:59:52Z` for ADB
device `ZA2237MRHN`, Motorola Edge 60 Fusion, package
`in.gharsajag.caregiver.discoverytest` version
`0.4.0-connected-lite-staging` / versionCode 3. It recorded Settings Home
`gs177-test-product`, origin `https://192.168.1.10/`, Backend API CONNECTED,
Reports → Latest recorded events and observer match for historical key
`{c3-146393c5d158, bedroom, session 112, sequence 2}`. The receipt explicitly
has `tc001_fresh_event_observed=false`; this proves observer readiness only.
Installed APK bytes match the preserved SHA-256
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`. The
embedded APK v2 signer-certificate digest
`d336ae68479da03de932a44b16c8de730c86e3cf68aee52fe92261e74e596b85` matches
the preserved trust digest files and its DER parsed with Python `cryptography`.
`apksigner verify` was not available or run; this is certificate-fingerprint
corroboration and APK-byte identity, not completed APK signature verification.
No rebuild or reinstall was performed.

The loopback `/api/status` returned HTTP 200, but its process (PID 39775,
started 2026-10-26 17:52Z) predates console source commit
`f6321597578bda69aa43056cbee70c863d5e625a` and omits current readiness fields;
its output is not treated as current-source readiness. Current-source guarded
readiness remains covered by
`python3 code/tests/python/test_gs117_tc001_console.py`: **43/43 PASS**, exit 0,
on this source HEAD. Owner-only `fixture.json` and
`five-run-campaign-approval.json` are both absent. The fixture remains BLOCKED:
fresh C3/S3 running-image receipts and exact image provenance, current
Hub/Home/epoch/enrollment binding and a fresh authenticated S3 ingress receipt
are unavailable without hardware access. Historical firmware hashes and
physical events were not substituted.

No COM4 or COM10 was opened; no reset, injection, flash, commissioning,
credential/ownership/enrollment change, or protected database mutation
occurred. TC-001 remains **0/5 BLOCKED / NOT_RUN**. A new scoped owner approval
is required before any reset-aware use of the existing
`gs117-protected-bootstrap-current-network.py` through COM10; opening that port
can reset the S3 and clear its RAM-only Wi-Fi/GS40 configuration. The prior
one-attempt recovery approval is consumed. Any later five-run C3 campaign needs
its own separate approval and must wait for a current fixture and authenticated
S3 receipt. Sanitized evidence is retained mode 0600 outside Git at
`~/.local/state/ghar-sajag/gs117-tc001/fixture-session-20261027T041925Z/readiness-observation-20261027T0430Z.json`.

### 2026-10-27 — audit-first TC-001 current-source readiness (05:07 UTC)

Resumed on canonical `feature/r1-commercial-baseline` at
`77b1927dc4043308078f0b3d2afa496aeead4555`; remote matched at entry and
`tools/context/ghar_sajag_context_preflight.sh` passed. The root `AGENTS.md`
is the only repository AGENTS file. Current release/product/validation
requirements, architecture/decisions, existing GS-117/GS-179 evidence and Jira
history were reconciled before considering changes. Latest reviewed comments:
GS-117 11735/11731/11727/11720; GS-179 11736/11724/11715; GS-178 11729/11726;
GS-116 11730/11717; GS-130 11728; GS-121 11732; GS-148 11725/11716; GS-173
11733.

#### Existing implementation audit

| Stage | Classification | Finding |
|---|---|---|
| C3 EventKey, retained Node event and existing HIL input | `IMPLEMENTED_AND_VALIDATED` | Existing NodeRuntime/TC-001 helper reused. No current injection was run. |
| Authenticated C3→S3, durable-before-ACK and replay handling | `IMPLEMENTED_AND_VALIDATED` (historical evidence) | Existing HubRuntime/journal/typed class-0 ACK path reused; historical physical evidence is not fresh TC-001 acceptance. |
| S3 CloudSync, mTLS ingress, PostgreSQL exactly-once and caregiver API | `IMPLEMENTED_AND_VALIDATED` (software/history); current runtime `CONFIGURATION_OR_RUNTIME_BLOCKER` | Existing GS-179 listener, DurableEventCommit and caregiver projection reused. No current S3 receipt exists in this readiness session. |
| Installed Android exact-key event details/ADB observer | `IMPLEMENTED_AND_VALIDATED` (historical observer readiness) | Existing APK and helper reused; only historical session112/sequence2 was matched. |
| Current fixture and authenticated S3 configuration | `CONFIGURATION_OR_RUNTIME_BLOCKER` / `PHYSICAL_APPROVAL_REQUIRED` | Fixture, current running-image receipts and fresh authenticated S3 ingress receipt are absent. |
| AM312 optical sensing | `PHYSICAL_APPROVAL_REQUIRED` / `NOT_RUN` | `INJECT_MOTION` cannot qualify optical sensing. |

No approved product capability was found missing or defective. No product
source, test framework, firmware, backend, database or APK changes were made.
Existing GS-178 results (33/33 and five HOST_SIM runs) remain software-only
historical evidence and were not rerun.

#### Current non-invasive readiness

`code/tools/local/gs179-laptop-server.sh health` passed PostgreSQL TLS and
durability, caregiver HTTPS and local backend health. Windows currently reports
Private `Airtel_Agrim` at `192.168.1.10`; existing forwarding remains
443→8444 and 8445→8445, and the Windows TCP 8445 probe passed. The bounded
listener is active at `172.17.152.10:8445`; persistent Hub ingress remains
NOT_CONFIGURED and autostart remains disabled.

At 05:01:54Z the existing Windows UDP `192.168.1.10:4468` signed-time service
returned a 456-byte RSA-3072/SHA-256 proof bound to a fresh nonce and
generation, valid through 05:03:54Z. This was a host-generated GS-68 TEST_ONLY
proof only (`s3_authenticated=false`, `physical_cloudsync_receipt=false`);
its validity interval had expired by the 05:07Z observation. Signed-time
request counters have no authenticated source attribution.

The ingress status observed at 05:07:36Z showed listener/PostgreSQL/time
dependencies ready. Its `real_hub_authenticated`/`hub_connected` values are
fixed conservative values in `Gs179TestOnlyHubIngressRuntime.status()`, not
live measurements. No current-session `real-hub-ingress-trace.jsonl` was
created and the ingress operator log remained empty; no fresh authenticated
physical CloudSync event receipt was observed. Listener readiness and TCP
forwarding do not prove S3 authentication.

The old loopback server was idle (`running=false`) and predated current console
source. It was replaced with the existing `bash
code/tools/local/gs117-tc001-launch.sh` launcher. Current-source `/api/status`
reported PostgreSQL/HTTPS/local backend PASS and authenticated TEST_ONLY Home
`gs177-test-product`; Home monitoring remains `UNKNOWN` / freshness `STALE`.
The existing PowerShell `List` action confirmed these USB descriptors without
opening either serial port:

| Board | Port | USB serial |
|---|---|---|
| C3 `c3-146393c5d158` | COM4 | `14:63:93:C5:D1:58` |
| S3 `hub-e072a1d38d34` | COM10 | `E0:72:A1:D3:8D:34` |

Current console readiness is PARTIAL: listener active; fixture BLOCKED;
Android NOT_VERIFIED because fixture is absent; campaign approval BLOCKED;
`running=false`. Enumeration is not an installed-image receipt or serial
observation.

The actual Android receipt remains 02:59:52Z: package
`in.gharsajag.caregiver.discoverytest` v0.4.0-connected-lite-staging,
versionCode 3, Home `gs177-test-product`, backend CONNECTED, Reports visible,
and historical session112/sequence2 exact-key match only. The preserved APK
snapshot SHA-256 is
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`; embedded
v2 signer-certificate digest
`d336ae68479da03de932a44b16c8de730c86e3cf68aee52fe92261e74e596b85` matches
the trusted digest. No existing WSL/Windows SDK or Downloads path contained
ADB or `apksigner`; formal APK signature verification remains incomplete. No
rebuild, reinstall or fresh event navigation was performed.

#### Fixture and bounded recovery approval boundary

Owner-only `fixture.json` and `five-run-campaign-approval.json` remain absent.
Missing fixture evidence is: current C3/S3 running-image receipts and artifact
hashes; fresh authenticated Hub/Home/epoch/enrollment and ingress receipt;
and current Android installation/signer verification. Preserved S3 image
SHA-256
`c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16`
(`9bbc6d0-dirty`, ELF prefix `c77483102`) is historical recovery evidence,
not current running-image attestation. Bootstrap metadata still says
`PREPARED_NOT_INSTALLED` and is not substituted for device evidence.

The previous one-hour RAM-only configuration/authority envelope has expired;
the new bounded host endpoints have no current physical receipt. No
non-invasive host operation renews that device configuration. The existing
protected template
`gs117-protected-bootstrap-current-network.py` matched its owner-only manifest.
Its run-local copy had a stale serial-helper SHA pin (`55da2f8f…`) while the
current helper is
`1849695926cf95d8c84a3d8b8c04c1091a970a6d41eba9e13b354ab202816b6c`.
History review confirmed `ports`, `collect`, `bootstrap_config` and `observe`
were unchanged; the later commit added separate campaign/Android paths. Only
the session-local pin was updated; the protected template and helper are
unchanged. Updated script SHA-256 is
`4ec5b057b942770bea2828801778ab05fc4d6ec5d845c816080c12a3f61d5dbb`, mode
0600. Syntax/hash checks passed. With the owner-approval environment guard
absent, the script returned its expected explicit-approval block before any
network or serial operation. No recovery marker or approval file was created.

One new scoped owner approval is needed before this recovery. The exact
procedure opens COM10/S3 and COM4/C3 (DTR/RTS low does not prove reset safety),
explicitly calls Espressif `HardReset` once on S3, and reads C3 `GET_STATE`
only. COM10 reset clears RAM-only Wi-Fi/GS40 config; COM4 open may reboot C3.
It reads the existing saved Airtel_Agrim passphrase into process memory and
sends it only in a fresh challenge-bound encrypted TEST_ONLY config; it does
not print or persist the passphrase, but Python memory zeroization is not
guaranteed. Existing TEST_ONLY keys, Hub/Home/epoch and TLS material are
reused. No flash, erase, partition/NVS/outbox/state mutation, commissioning,
ownership/enrollment change, database mutation or motion injection occurs.
Stop on network/identity/image mismatch, missing challenge, timeout or target
rejection; maximum one attempt and no retry without new approval. This is
recovery authorization only, not five-run injection or optical PIR approval.

The unchanged GS-117 source/test files last passed
`python3 code/tests/python/test_gs117_tc001_console.py` 43/43 at
`f6321597578bda69aa43056cbee70c863d5e625a`; source comparison confirms they
are unchanged through audit entry. No full release gate or unrelated suite was
run. TC-001 remains **0/5 BLOCKED / NOT_RUN**; real optical PIR is NOT_RUN;
fresh S3 authentication is NOT_VERIFIED; fixture is BLOCKED. Next step is the
single scoped recovery approval, followed by a new readiness/fixture
evaluation. Five-run approval remains separate.

Jira pause state: GS-117 was moved to **OnHold** after comment 11737; GS-179
remains **In Progress** after comment 11738. Resume GS-117 In Progress only
when separately authorized recovery is ready to proceed.

### 2026-10-27 — owner-authorized one-attempt S3 recovery and live ingress verification (05:57Z)

Owner approval in this Codex task authorized exactly one invocation of the
existing protected `gs117-protected-bootstrap-current-network.py` procedure:
S3 `hub-e072a1d38d34` on COM10 reset plus existing encrypted TEST_ONLY
configuration, and C3 `c3-146393c5d158` on COM4 `GET_STATE` observation only.
The approved run-local script SHA-256 was
`4ec5b057b942770bea2828801778ab05fc4d6ec5d845c816080c12a3f61d5dbb`; its
pinned serial helper SHA-256 was
`1849695926cf95d8c84a3d8b8c04c1091a970a6d41eba9e13b354ab202816b6c`. The
one-attempt marker was consumed at 05:39:03Z. The recovery completed once;
there was no retry. COM10 reset and loss of RAM-only Wi-Fi/GS40 state were
within the stated approval. COM4 was used only for `GET_STATE`; no injection
was issued. No firmware write, erase, partition/NVS/outbox mutation,
recommissioning, credential or enrollment change, or database mutation took
place.

The fresh S3 boot reported OTA offset `0x420000`, application version
`9bbc6d0-dirty`, ELF SHA-256 prefix `c77483102`, `post_reset_boot_verified=true`,
Hub `hub-e072a1d38d34`, Home `gs177-test-product`, `enrolled=1`, and
`storage_epoch=1`. GS40 encrypted configuration was accepted and
`HIL_FIXTURE_READY` was observed. The observed ELF prefix is not a complete
running-image hash or current installed-image receipt. C3 `GET_STATE` reported
the expected TEST_ONLY identity/profile/session; it did not provide the full
current C3 image and partition receipts required by the campaign fixture.

#### Fresh physical ingress and backend correlation

The existing hash-verified bounded ingress and signed-time procedures were
started with their existing one-hour limits; no persistent service or
autostart was enabled. At the recheck, Windows still reported Private
`Airtel_Agrim` / `192.168.1.10`; TCP 8445 forwarding succeeded and UDP 4468
was bound. `gs179-laptop-server.sh health` passed PostgreSQL TLS/durability,
caregiver HTTPS and local backend checks. The host-generated signed-time proof
was cryptographically verified against the existing RSA-3072 trust key and
matched its nonce/generation at 05:38:38Z, with validity through 05:40:38Z; it
was expired at this 05:57Z closeout. The bound host service remained available.

The private physical ingress trace contains 32 authenticated
`/v1/test/authority/refresh` HTTP 200 receipts, latest at 05:57:02Z. It also
contains 16 distinct physical C3 EventKeys (Node `bedroom`, session 118,
sequences 1–16), each initially acknowledged by ingress as HTTP 201
`COMMITTED`, `duplicate=false`. Repeated physical retries returned 18 HTTP 200
`COMMITTED`, `duplicate=true` receipts. The saved read-only backend/API
correlation reports exactly one durable event and one caregiver projection per
key, correct physical Hub/Home/epoch/enrollment, and bedroom location. Sequence
14 is `MOTION_SUMMARY`; the other 15 are `MOTION`, which explains the audit
summary's `all_motion_bedroom=false` check without indicating a missing
delivery. Monitoring remains `UNKNOWN` / `STALE` because of the previously
documented GS-148 synthetic/physical Bedroom NodeHealth projection conflict;
no health/enrollment/history row was changed.

The C3 observer also logged a later NodeRuntime PIR/transmit sequence 122, but
the contemporaneous exact-key backend lookup had no matching durable event.
That observation is not counted as delivered or accepted. The observed
session-118 traffic was not produced by the five-run controlled campaign, and
does not establish the required per-run Node durable ACK/retirement evidence
or optical PIR qualification.

#### Current-source console and Android gates

The focused current-source regression
`python3 code/tests/python/test_gs117_tc001_console.py` passed **43/43**, exit
0. The current loopback `/api/status` returned `running=false`, backend and
authenticated TEST_ONLY Home ready, exact USB descriptors visible without
opening the ports, listener active, fixture BLOCKED, campaign approval
BLOCKED, and Android event observation NOT_VERIFIED. The listener readiness
field describes a bound listener; physical authentication is established by
the separate mTLS trace above. Persistent `HUB_INGRESS_READY` remains
NOT_CONFIGURED by design.

The existing read-only `AndroidReady` helper passed: authorized Motorola Edge
60 Fusion `ZA2237MRHN`, installed package
`in.gharsajag.caregiver.discoverytest` version
`0.4.0-connected-lite-staging` / versionCode 3 and installed package path
verified. The returned signer digest is read from the owner-only installation
receipt; it is not a fresh cryptographic package-signature verification. The
earlier APK pull matched the preserved SHA-256; this readiness check did not
repull or hash the installed APK. Formal `apksigner verify` remains
unperformed. The exact-key Android observer was attempted twice for
the current C3 sequence 122 and both attempts stopped with
`TC001_APPROVED_ANDROID_APP_NOT_FOREGROUNDED`; read-only device state showed a
locked lockscreen. No unlock bypass was attempted; observer retries stopped
after the two identical foreground failures. Thus app installation readiness
passes, while fresh Home/Reports/Event Details observation remains NOT_VERIFIED.

The owner-only `fixture.json` and independent
`five-run-campaign-approval.json` are both absent. Fixture creation remains
BLOCKED on complete current C3/S3 running-image and partition receipts, a
fresh current phone UI observation, and validated exact identity/trust fields;
historical image hashes and receipt signer values were not promoted. No five
injections were run and no approval was created. TC-001 remains **0/5
BLOCKED/NOT_RUN**; `TARGET_TEST_INPUT_PASS` and `REAL_SENSOR_PASS` are both
NOT_RUN. Do not execute another serial operation or recovery under the consumed
one-attempt approval. After the app is unlocked and missing full-current-image
receipts are obtained through a separately approved safe procedure, re-evaluate
the fixture; only then request the independent bounded five-run authorization.

### 2026-10-27 11:11 UTC — resumed exact-key and readiness recheck

The canonical source remains `c7eceedd44a37cf1ed049b4b7fba008d89ddcc3b`.
The owner reconnected and authorized the Motorola phone. Current `AndroidReady`
passed for serial `ZA2237MRHN`, package
`in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging` / versionCode 3, and the installed package path.
The returned signer is still receipt-derived; no formal `apksigner verify` tool
was present in the checked Linux/Windows SDK paths.

The existing Android observer was run for the original physical EventKey
`c3-146393c5d158 / bedroom / session 118 / sequence 16`. It stopped at
`TC001_ANDROID_SETTINGS_NAVIGATION_NOT_FOUND`. A read-only screen capture and
accessibility dump showed the installed app in its sign-in screen with “No
current authorized session was restored.” No credentials were submitted. The
phone is ADB-ready, but no exact EventKey was observed in the APK. Private
Android evidence is under
`~/.local/state/ghar-sajag/gs117-tc001/android-session118-seq16-result-20261027T110634Z/`
and `android-ui-diagnostic-20261027T110708Z/`.

The existing read-only backend observer reconfirmed sequence 16 as one durable
`MOTION` row and one caregiver projection in `Bedroom`, committed by
`hub-e072a1d38d34` at ownership epoch 1 / enrollment generation 1. Its
freshness is `STALE` and Home monitoring is `UNKNOWN`; this is backend evidence,
not Android evidence or TC-001 campaign acceptance. Sequence 122 remains
unmatched: the preserved C3 trace has `PIR -> NodeRuntime` and three
`NodeMessage sent` attempts, with no application ACK; the exact backend query
returns zero durable rows/projections and the bounded ingress trace has no
sequence-122 receipt. The saved S3 boot observation reports failed
time/authority refresh and fenced CloudSync publication. These traces do not
prove whether the ESP-NOW packet reached the Hub. The exact-key query is saved
privately at
`~/.local/state/ghar-sajag/gs117-tc001/backend-session118-exact-keys-20261027T111134Z.json`.

The phone app and last verified encrypted Hub configuration target
`https://192.168.1.10/`, but Windows Wi-Fi is now `192.168.1.6`; the existing
Windows portproxy rows still listen on `.10` and target WSL
`172.17.152.10`. The current `.10` neighbor is not the laptop Wi-Fi adapter.
Do not send caregiver credentials to that address, claim its TLS identity, or
rebind the address while another device owns it. PostgreSQL TLS/durability,
caregiver HTTPS and the local backend remain ready; bounded TCP 8445 ingress
and UDP 4468 signed-time listeners are absent. No current S3 authentication is
verified.

The fixture remains absent, as does the separate campaign approval. The S3
installed-image receipt was observed at `2026-10-26T08:36:03Z` and is now older
than the fixture's 24-hour limit. Its complete app hash matches the preserved
binary, while the later S3 boot supplied only version `9bbc6d0-dirty` and ELF
SHA prefix `c77483102`. The C3 artifact and image-info exist, but there is no
current installed-image receipt or full running-image digest. The fixture
requires both boards' local image/artifact hash match, current installed-image
receipt, target/USB/serial/source identity, active slot, partition-table hash,
and capacity evidence (including S3 PSRAM). Neither a version string nor an ELF
prefix can replace those fields. The existing S3 full-flash readback script
also reads NVS, outbox and state; it is broader than needed. The least-data
attestation is a targeted read-only readback of each active app slot and the
partition-table region using the existing esptool package. Opening COM4/COM10
can reboot a board; COM10 reset can clear RAM-only Wi-Fi/GS40 configuration.
The previous one-attempt recovery approval is consumed, so this readback and
any necessary encrypted S3 reconfiguration require a new explicitly scoped
owner approval. No serial operation was performed in this recheck.

Disposition remains GS-117 **In Progress**, physical TC-001 **0/5
BLOCKED/NOT_RUN**, `TARGET_TEST_INPUT_PASS=NOT_RUN`, `REAL_SENSOR_PASS=NOT_RUN`,
and actual Android EventKey observation **NOT_VERIFIED**. GS-179 remains In
Progress. Restore a stable owner-approved route for the existing `.10` endpoint
first; then restore bounded services and verify fresh S3 authentication,
obtain the scoped current-image evidence, restore an authenticated app session,
and re-evaluate every fixture gate. Request the separate five-run authorization
only after those gates pass. No product source or tests changed; the previously
recorded current-source console regression remains 43/43 PASS at its source
commit.

### 2026-10-27 12:16 UTC — router-reserved endpoint and actual APK event observation

The owner confirmed the Wi-Fi router reserves `192.168.1.6` to the laptop Wi-Fi
MAC `C0:18:85:B9:4F:C3`. Windows DHCP remains enabled and the trusted
`Airtel_Agrim` profile is Private. Current Windows Wi-Fi is `.6/24`; WSL is
`172.17.152.10`. The existing GS-179 scoped routes now bind `.6:443` to WSL
`:8444` and `.6:8445` to WSL `:8445`; no route points at old `.10`. The active
TLS certificate checks the existing `desktop-3qqu64b.local` identity and the
current `.6` address. Backend health passes PostgreSQL TLS/durability,
caregiver HTTPS and local service checks. The laptop IP stability is provided
by the router reservation; no Windows static address or additional service was
configured.

The installed Motorola Edge 60 Fusion (`ZA2237MRHN`) is using the existing
Parivar Saathi package `in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging` / versionCode 3, with backend API `CONNECTED`,
Home `gs177-test-product`, origin `https://192.168.1.6/`, and Reports available.
Using existing observer helpers with normal UI scrolling, Event Details showed
the exact historical physical EventKey
`c3-146393c5d158 / bedroom / session 118 / sequence 16`: “Motion recorded”,
Bedroom, timestamp `2026-10-27T05:45:19Z` (shown in the app as 27/10/2026,
11:15:19 am local). The backend exact-key query showed one durable MOTION row
and one caregiver projection for the same Home/Hub/epoch/enrollment. Private
ADB evidence is under
`~/.local/state/ghar-sajag/gs117-tc001/android-session118-seq16-exact-20261027T120515Z/`.
This proves observation of an existing physical event in the actual APK. It is
not a new campaign input, per-run ACK evidence, or a real-PIR acceptance result.
The app signer value remains receipt-derived; formal `apksigner verify` was
not performed.

The bounded GS-179 ingress and signed-time services are currently active. At
12:16:32Z the live ingress status showed listener/PostgreSQL/trusted-time ready,
but `real_hub_authenticated=NO`, `hub_connected=NO`, monitoring freshness
`UNKNOWN`, and persistent ingress `NOT_CONFIGURED`. TCP forwarding to the
listener is reachable. The RSA-3072 proof at 12:11:28Z verified its
nonce/generation binding and signature and was host-generated TEST_ONLY proof
valid for 120 seconds; it expired before this checkpoint and is not a physical
S3 receipt. No new authenticated physical S3 receipt is available. No
credentials were sent to `.10`.

The existing current-source loopback console at `127.0.0.1:18791` returned
HTTP 200 from its guarded `/api/status` GET. PostgreSQL, HTTPS, local backend,
Home and descriptor-only COM4/COM10 identity checks passed; no serial port was
opened. The runtime reports `running=false`, the bounded ingress listener
active, and its own ingress gate PASS, while persistent service configuration
is NOT_CONFIGURED. The owner fixture/campaign remain BLOCKED and the console's
APK fixture gate is NOT_VERIFIED; these console gate states do not invalidate
the separate actual-APK exact-key evidence above.

Sequence 122 remains unmatched: the preserved C3 trace has three NodeMessage
sends without a captured application ACK, and the exact backend query has no
durable event or caregiver projection. It remains excluded from delivered-event
counts. The owner-only fixture and five-run approval files remain absent. The
S3 full-image receipt is older than the fixture's 24-hour window; the C3
running-image/partition-table receipt is incomplete. The fixture requires
matching current image digests, exact target/USB/serial/source identity, active
slot, partition-table digest and memory evidence for both boards. The
least-data existing method is to read only each active app slot and partition
table using the protected esptool tooling, avoiding the broader readback that
includes NVS/outbox/state. ROM access/opening COM4 or COM10 can reset a board;
COM10 reset can clear its RAM-only Wi-Fi/GS40 configuration. A new scoped
owner approval is required both for those current-image reads and for one use
of the existing encrypted S3 configuration recovery procedure with the
confirmed `.6` endpoint. The previous single recovery attempt was consumed.

No serial port, reset, configuration write, injection, APK rebuild, firmware
write, protected data mutation, or enrollment/ownership change occurred in
this checkpoint. TC-001 remains **0/5 NOT_RUN**, `TARGET_TEST_INPUT_PASS` and
`REAL_SENSOR_PASS` remain **NOT_RUN**, and GS-117/GS-179 remain **In Progress**.
After the scoped current-image/readiness operation is authorized and passes,
revalidate the guarded fixture and request the separate five-injection
authorization; do not create either owner-only file before its required
authorization. GS-117 is now being placed OnHold while this new scoped
authorization is pending; resume In Progress when authorized execution starts.

### 2026-10-27 13:21 UTC — approved current-image readback stopped at C3 capacity guard

The owner approved one bounded readiness session for targeted C3/S3 app-slot
and partition-table evidence, followed by exactly one existing S3 encrypted
configuration recovery to 192.168.1.6. GS-117 was moved to In Progress for
this authorized session. The canonical branch was
feature/r1-commercial-baseline at
1fe7e3777dbe542c05b3fd134fe5f22f90ce3459; origin matched, context preflight
passed, and tracked files were clean before this evidence update. Existing
untracked user assets were preserved.

The approved C3 COM4 operation opened the exact enumerated USB device
14:63:93:C5:D1:58; esptool identified ESP32-C3 MAC 14:63:93:C5:D1:58.
Read-only security metadata reported Secure Boot off, flash-encryption count
zero and Secure Download off. The preserved C3 image artifact hash and its
version/ELF metadata matched the private checkpoint manifest in an offline
preflight. The targeted readback stopped before reading any flash region
because esptool 5.4.0 returned no recognized flash capacity
(detect_flash_size() == None). The private result records flash_reads=[]; no
partition table, OTA selector or app bytes were read, and no current C3 image
or capacity receipt was produced. This is an unknown-capacity/tool-
identification result, not an observed image mismatch.

The private run evidence is under
~/.local/state/ghar-sajag/gs117-tc001/current-image-readback-20261027T131908Z/
(c3-readback.json, c3-esptool.log, and the reviewed one-use helper). The
offline helper self-test passed for the installed ESP-IDF 6.0.3 partition
parser and preserved C3/S3 artifacts without opening a port. COM4 was opened
once; the app-run state after closing the serial connection was not rechecked,
to honor the stop condition. No retry or further device observation was made.

COM10 was not opened. The S3 readback and approved recovery procedure were not
invoked. No S3 reset/configuration change, firmware write, erase, NVS/outbox/
credential read, motion injection, ownership/enrollment change, or protected
database mutation occurred. The existing owner-only fixture and separate
five-run approval remain absent. TC-001 remains 0/5 NOT_RUN; target test input
and optical PIR remain NOT_RUN. The historical session-118 sequence-16 APK
observation remains evidence of observer readiness only.

The failed capacity guard triggers the owner's explicit stop rule. Do not
reopen COM4, proceed to COM10, or invoke the S3 recovery under the prior
session approval. The exact next step requires a fresh scoped owner approval
for one corrected read-only C3 app/table/selector capture that records and
validates the raw flash-ID/capacity result; only if that passes may the
remaining S3 readback and one recovery be considered within that new
authorization. Stop on any further mismatch. Then revalidate fresh physical
mTLS and fixture gates before requesting the separate five-run campaign
approval.

No product source changed. python3 -m py_compile passed for the private
one-use helper; its Windows Python 3.12 / esptool 5.4.0 offline self-test
passed. The actual C3 hardware readback stage FAILED/BLOCKED at capacity
detection before flash-region reads. No product regression suite was rerun
because no product code changed. GS-117 is placed OnHold pending fresh
authorization; GS-179 remains In Progress.


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

### 2026-10-27 — offline interpretation of the C3 JEDEC capacity stop

No device or serial port was accessed for this diagnosis. Inspection of the
preserved private helper
`~/.local/state/ghar-sajag/gs117-tc001/capacity-first-readback-20261027T141042Z/`
and the installed Windows esptool 5.4.0 source shows that the helper issued
`flash_id()` after `detect_chip()` but did not use the existing `attach_flash()`
ROM-loader initialization. The official esptool `flash-id` command performs
`attach_flash()` before the JEDEC read. This is a plausible explanation for an
all-ones `0xffffff` response, not proof that the C3 flash is good or that its
capacity is known. The preserved result still has `flash_reads=[]`; no
partition, selector or application region was inspected. Capacity remains
UNKNOWN and the existing stop condition remains active.

No retry, COM4/COM10 access, S3 readback or recovery is authorized by this
offline review. Any further hardware attempt requires a new explicit scoped
owner approval for an audited, identity-checked, read-only initialized flash-ID
procedure. Only a genuine recognized capacity can permit the separately scoped
readback/recovery sequence to be considered. TC-001 remains 0/5 NOT_RUN.

### 2026-10-28 — configuration repository and fail-closed Morning Routine console

At canonical `5687854d700b4e97bd5f975c6b820c13dd3d365b`, implemented a reusable
versioned desired/applied household configuration repository against the
existing `configurations` table. It has no HTTP route. Caregiver publish
requires a current `ActorSession` plus an injected current Home-settings
authorizer. Hub read/apply requires `VerifiedHubContext`, an injected trusted
Hub authorizer, and a transaction-scoped check that the existing ownership
registry still maps the Hub, key fingerprint, Home and installation epoch.
The repository rejects stale expected versions and stale Hub acknowledgements,
validates through the existing household policy validator, records an audit
entry, preserves the last applied version while a newer desired version waits
for acknowledgement, and accepts an exact apply acknowledgement idempotently.
Contract tests exercised the migrations on SQLite. No live PostgreSQL instance
was used; the PG adapter's TLS/durable runtime is not verified by these tests.

Extended the existing loopback TC-001 console with an additive Morning Routine
panel and route. It displays desired/applied version and included/required/
optional room fields when a trusted source is available, retains the separate
10-second-default TEST_ONLY stimulus cadence, exposes a Run action, and saves
stage-by-stage reports with first blocker and private report history. The
existing fixed Bedroom five-event TC-001 campaign is unchanged. Current Run
fails closed at `applied_household_policy`: production caregiver/Hub authority
and config delivery are unavailable; there is only an established Bedroom
Node fixture; no separate Morning Routine hardware authorization or fresh
physical S3 receipt exists. A blocked attempt saves no EventKeys, performs no
USB/ADB action and remains `acceptance=NOT_RUN`.

Focused results: backend test file 20/20 PASS; GS-117 controller/ADB test file
47/47 PASS; feature coverage consistency 226 features, 286 modules, 27
physical cases, mapping regressions 22/22 PASS. Python compile, JSON parsing,
inline JavaScript syntax and `git diff --check` pass. No live PostgreSQL,
Hub/S3, browser, Android, COM or firmware build was run. The four owner/security
decisions are summarized in the existing GS-109/GS-148 decision package. No
production endpoint, identity provider, credential, Home authority or device
configuration was activated. TC-001 remains 0/5 NOT_RUN; actual S3 rule
application, Morning Routine decision and Android completion remain NOT_RUN.

### 2026-10-28 — Bedroom-only policy and live PostgreSQL repository verification

Resumed from canonical `f3223a1a687c9c3729a3ad3b5960e620b9039622` with
context preflight PASS and local/origin HEAD equal. Existing configurable
`RulesCore`, PostgreSQL desired/applied repository and GS-117 controller were
reused. The owner approval record in the existing GS-109/GS-148 decision
package is a request only: RSA-3072 DS/mTLS Hub identity, GS-76 caregiver
authority, backend Home/Hub/epoch source and trusted TLS middleware remain
pending product-security disposition. Credential provisioning and any
physical Run require separate scoped approvals.

The general configured-step implementation now has a regression for a policy
whose sole enabled required location is Bedroom. It ignores an event from a
location outside the configured list, emits `MORNING_ROUTINE_COMPLETED` once
on Bedroom activity, and does not emit a duplicate on replay. This is generic
required-step evaluation, not a Bedroom-only shortcut. The repository also
round-trips this policy through desired/fetched/applied states, first through
the SQLite contract suite and then through the existing isolated live
PostgreSQL test facility.

Focused results on the working tree: C++ test harness 1,532 checks PASS;
backend Python file 21/21 PASS; GS-117 console/controller 47/47 PASS; GS-179
PostgreSQL/security integration module 20/20 PASS; Node USB stable-profile
regression 4/4 PASS; feature-traceability tests 22/22 PASS and validation
framework 51/51 PASS. The PostgreSQL run used TLS to the existing
`gs179_monitoring` service and a disposable isolated schema, dropped at
teardown; it did not modify shared/public household records.

Aggregate checks are not all green: `validation-hub` reports the existing
migration clean-commit failure and P0 `product_status=PARTIAL` (GS-178 remains
39/39 PASS). `validation-backend` reports P0 partial and CSS budget 29,576 B
against 18,432 B; its earlier traceability assertion issue was corrected and
the focused mapping tests now pass, but the aggregate was not rerun.
`validation-tooling` reports the CSS budget issue plus an outdated assertion
about stream closure; that assertion now matches the existing reverse-order
cleanup and its focused test passes 4/4, but the aggregate was not rerun. No
release gate was run.

No physical readiness was promoted. Bedroom remains the only established
physical room fixture. Production configuration is not delivered/applied to an
actual S3; fresh authenticated physical ingress and a current approved fixture
are absent. The unresolved C3 JEDEC result is still `0xffffff` with unknown
capacity. No COM port, hardware, USB input, reset, Android session or credential
was accessed in this checkpoint. Run remains BLOCKED at `applied_household_policy`;
there is no real Hub completion decision or corresponding Android result.
TC-001 and optical PIR remain NOT_RUN. Next: obtain the scoped architecture
disposition, then address separately authorized credential and physical gates
without weakening the existing JEDEC, image, ingress or campaign controls.

#### First Bedroom-only real-device Run — prepared, not authorized/executed

The bounded scenario is one configured Bedroom motion observation, not the
five-run TC-001 campaign:

1. Approve and implement the production identity/configuration contracts; use
   authorized Settings to publish a schema-valid policy with Bedroom as the
   sole enabled required activity. Confirm desired version in PostgreSQL and
   exact Hub/Home/epoch apply acknowledgement only after S3 durably persists
   that version.
2. Requalify current C3/S3 identities, app-slot/partition provenance, JEDEC
   capacity, enrollment/epoch, fresh authenticated S3 ingress, backend/API and
   Android observer. A failed/missing gate keeps Run blocked.
3. Obtain a separate bounded approval for the existing C3 USB
   `INJECT_MOTION` operation, including COM4 open/reset risk and exact stop
   conditions. COM10 remains unopened unless an independent configuration or
   recovery operation is separately authorized.
4. Use the existing GS-117 Morning Routine Run path once. Capture the original
   Node EventKey and NodeRuntime state; require authenticated ESP-NOW delivery,
   durable S3 admission/ACK, and the actual S3 rule engine's
   `MORNING_ROUTINE_COMPLETED` decision. Stop on the first failure.
5. Correlate that decision through authenticated CloudSync, one PostgreSQL
   business record, caregiver API and the installed Android APK's routine
   result. Event-row visibility alone does not satisfy the run.

The current implementation intentionally cannot pass step 1 because the
production authority/delivery boundary is pending approval and is not
installed. This plan grants no hardware, credential or configuration-change
authority. After this single-room vertical passes, additional rooms require
their own enrolled physical Nodes; Bedroom is never relabeled as another room.

### 2026-10-28 — DEV-first Morning Routine integration update

This is an implementation/status amendment to the earlier readiness notes;
those notes remain historical evidence of the state at their recorded times.
The architecture direction was approved in GS-109 comment 11797 and GS-148
comment 11798. Production issuer/key custody, credential issuance, production
deployment/activation and any physical operation remain separately gated.

Reused the existing GS-40/GS-179 isolated TEST_ONLY profile, authenticated
caregiver Settings boundary, versioned PostgreSQL desired/applied repository,
configurable RulesCore, existing Hub checkpoint, GS-117 controller and Android
observer. The S3 TEST_ONLY composition now fetches policy over its existing
authenticated backend channel, validates Home/Hub/epoch and policy version,
applies it to the existing rule engine, checkpoints policy/timezone, and
acknowledges only after durable save. The caregiver Settings/status view
distinguishes desired from acknowledged-applied versions. No production route
was made anonymously writable and no production credential was issued.

The existing controller reads its configuration from the authenticated
Settings route and derives desired/applied status from that response. It
continues to fail closed on physical Run: no device has been operated and no
real S3 policy application, `MORNING_ROUTINE_COMPLETED` decision, or APK
business-outcome observation is claimed. Only Bedroom is an established
physical room; additional required rooms block until independently enrolled
Nodes and fixture evidence exist.

Focused results on the current working tree: GS-117 controller/ADB 50/50 PASS;
GS-116 component-gate 55/55 PASS; caregiver JavaScript 11/11 PASS;
`make -C code validation-board-e2e` 10 checks PASS (software only, physical
NOT_RUN); isolated PostgreSQL repository/security 21/21 and runtime
composition 5/5 PASS in disposable schema. The existing TEST_ONLY S3 target
compiled with cJSON 1.7.19~2 and external TEST_ONLY public root; it was not
installed. The incremental production-profile S3 rebuild following the
conditional CMake dependency change completed PASS: 2,201,049 bytes,
SHA-256 `989d0a20d8f38487d86d6fb2e3f5d4379b844fd1e2c712c45ddceb519f00948d`.
The CMake cache verifies `GS40_TEST_ONLY_CLOUDSYNC`, `GS_HIL_BUILD`,
`GS_HIL_CONTROL`, and `GS_HIL_COMMISSIONING` OFF and an empty external TEST_ONLY
root. Build output included unused-variable and ESP-IDF Kconfig warnings but
returned success. Neither the TEST_ONLY nor production image was installed.

Current physical gates remain unchanged: C3 JEDEC `0xffffff`/capacity unknown,
current installed-image provenance incomplete, fresh physical S3 mTLS receipt
unverified, owner-only fixture absent, and no scoped Morning Routine Run
authorization. GS-117 TC-001 and optical PIR remain NOT_RUN. No COM/USB, ADB,
credential, reset, flash or physical input was used.

### 2026-10-28 — committed DEV integration and clean paired target build

The integrated implementation is committed as
`732b848df157859cffaf813332d8ab1e0058ad7a`. The clean existing C3/S3 builder
passed from this source and wrote
`code/build/validation_targets/gs116-ktfj60_m/report.json`: C3 image 944,272
bytes, SHA-256
`6d65ce180a926b7e0388032ac65f9a40b8de6813a79396aa62b8e4c4d4d7c522`; S3
image 2,201,168 bytes, SHA-256
`9544d3afa20dc2b376ffa5af8e65c518776eb84456560372318448b04766f99c`.
Both fit their configured app slots. The production S3 cache confirms
`GS40_TEST_ONLY_CLOUDSYNC`, `GS_HIL_BUILD`, `GS_HIL_CONTROL`, and
`GS_HIL_COMMISSIONING` OFF and an empty TEST_ONLY root. Qualification is
`TARGET_COMPILED_ONLY`; no board operation or image installation occurred.

The read-only local service check reports PostgreSQL TLS/durability and
caregiver HTTPS on WSL port 8444 PASS, but Windows LAN HTTPS at
`192.168.1.6:443` times out. Existing `.6` forwarding entries point to the
current WSL address, but Windows listener/firewall inspection and repair
require UAC. The existing proxy helper stopped at its administrator guard
before changing route state. No 8445 ingress or 4468 signed-time service is
listening. The current owner-only fixture and TC-001 approval files are absent.

Focused software results: GS-117 controller 50/50, GS-116 gate tests 55/55,
caregiver JavaScript 11/11 and board-stack E2E 10/10 PASS (software only).
Isolated TLS PostgreSQL repository/security tests passed 21/21 and runtime
composition 5/5 using a disposable schema. These do not establish physical
S3 configuration application or a Morning Routine decision. GS-117 remains
OnHold; TC-001, real optical PIR and Android routine outcome remain NOT_RUN.

## 2026-10-28 — guarded Bedroom Morning Routine Run integration

Resumed from pushed closeout `74458e2df560752d41e93c442e05f710e9bd1584`.
The controller/observer source is `3854d661f731e996a0cc7f26f0a7800a49e3be78`;
the final read-only decision-query regression commit is
`d6a37dc113ead8fe5559a990dcce2974d271e182`.
Existing configurable RulesCore, authenticated desired/applied policy,
GS-117 C3 USB path, PostgreSQL/caregiver API and ADB observer were reused. The
minimum integration now extends the existing Run panel from readiness reporting
to a one-use, Bedroom-only sequence that requires an actual Hub-owned
`MORNING_ROUTINE_COMPLETED` row joined to the original Node EventKey, the
matching authorized caregiver decision and the exact decision ID in the
installed APK Reports detail view. It captures screenshot and accessibility
evidence privately. The fixed TC-001 five-injection campaign remains unchanged.

The Run path checks the applied household version, actual enrolled room mapping,
current exact fixture/image/JEDEC receipts, backend/Home, Android readiness,
fresh authenticated physical ingress and a separate one-use Run approval before
consuming approval or opening C3 COM4. S3 COM10 remains unopened. Configured
rooms without their own enrolled physical Node report BLOCKED. The Run approval
was not present or consumed; no hardware or Android operation occurred.

Validation: Python compilation PASS; GS-117 controller/ADB suite **58/58 PASS**;
GS-116 component-gate suite **55/55 PASS**; `make feature-coverage-test` PASS
(226 features, 286 source modules, 27 physical cases; 22/22 mapping tests);
`git diff --check` PASS. The successful one-click orchestration and APK
exact-decision tests use mocks; they are not a real board run or an Android
observation. No target build was needed because firmware/configuration sources
were unchanged.

Read-only current service status: PostgreSQL TLS/durability and local caregiver
HTTPS at WSL `172.17.152.10:8444` PASS; LAN HTTPS `192.168.1.6:443` times out;
TCP `8445` and UDP `4468` listeners absent. Backend reports no authenticated
Hub identity, monitoring freshness UNKNOWN and ingress NOT_CONFIGURED. The
current C3 JEDEC/image receipts, owner-only fixture, fresh physical S3 mTLS
receipt and separate Morning Routine approval are not established. No physical
S3 completion decision or APK business outcome is claimed. GS-117 remains
OnHold; TC-001 is 0/5 NOT_RUN and optical PIR is NOT_RUN.

### 2026-10-29 — authorized Android live check and bounded service recovery

At source commit `3ec7831450055bf4258e37b2759cfaaeadeaa6c9`, the owner-provided
Windows ADB executable was used directly:
`C:\Users\DELL\Downloads\platform-tools-latest-windows\platform-tools\adb.exe`.
The authorized phone `ZA2237MRHN` was present and authorized. Existing
`AndroidReady` passed for installed package
`in.gharsajag.caregiver.discoverytest`, version
`0.4.0-connected-lite-staging` / versionCode 3. A read-only ADB pull verified
the installed `base.apk` SHA-256
`0b240966255618ad3466e17e8dcca40d71efbe84b0096cb1063ba9f4855e2d76`, matching
the preserved APK. The signer digest remains receipt-backed corroboration;
formal `apksigner verify` was not run.

The existing `AndroidVerify` observer passed against the in-memory current
origin `https://192.168.1.6/` and Home `gs177-test-product`. The actual APK
Settings showed `Backend API · CONNECTED`; Reports refreshed and showed the
exact historical HOST_SIM EventKey
`p15:test-c3-bedroomn7:bedrooms2026102801q1`, `Motion recorded`, bedroom and
the original `28/10/2026, 8:46:55 am` timestamp. The refreshed screen reports
139 durable event records and labels that event `TEST_ONLY` / `physical origin
not verified`. Current backend logs at 02:57:03 UTC show HTTP 200 for the
existing caregiver login, `/me` and Reports requests, with authenticated
`/me` and Reports reads continuing on later refreshes. This is a live
APK-to-backend check of an old software event, not a new physical event. The
stale `.10` owner install receipt was not changed; `.10` received no request.
Screenshot, accessibility tree, pulled APK and observation manifest are
private under
`~/.local/state/ghar-sajag/gs117-tc001/android-live-check-20261029T025526Z/`.

The existing bounded GS-179 procedures were reused. Signed-time now listens on
Windows `192.168.1.6:4468`; a host-generated GS68 TEST_ONLY proof matched its
nonce and generation, its RSA-3072 signature verified, and the interval was
valid. This is host proof only. The existing GS-179 runtime is active on WSL
`172.17.152.10:8445` with PostgreSQL and its explicit TEST_ONLY trusted-time
provider ready, but it reports `real_hub_authenticated=NO`; the ingress trace
has zero receipts. The existing Windows `.6:8445 -> 172.17.152.10:8445` row is
present, but Windows has no active `.6:8445` listener. The read-only proxy
audit cannot read the firewall rule without Administrator. The registered
`Ghar Sajag GS-179 Trusted Wi-Fi Reconnect` task covers caregiver port 443
only. No alternate task can perform the physical-ingress action.

`ADMIN_APPROVAL_REQUIRED`: run the existing
`gs179-windows-lan-proxy.ps1 -Action Start -EndpointKind PhysicalHubIngress
-WslAddress 172.17.152.10` once in an elevated PowerShell on the current
trusted Private Wi-Fi. Its existing guards scope the rule to that Wi-Fi
subnet, verify port ownership and fail closed on a conflicting firewall rule.
No certificate, credential, endpoint identity, database record or hardware
state was changed. The private bounded-service evidence is under
`~/.local/state/ghar-sajag/gs117-tc001/services-live-20261029T025923Z/`.

The existing GS-117 console page and `/api/status` return HTTP 200. Readiness
still marks the owner-only fixture BLOCKED because its approved current
identity/image fixture is absent; physical Run, TC-001, fresh S3 mTLS, Hub
Morning Routine completion and APK decision observation remain NOT_RUN. No
COM4/COM10 open, injection, reset, flash or enrollment operation occurred.
Focused regression: `python3 code/tests/python/test_gs117_tc001_console.py`,
60/60 PASS. Physical TC-001 stays 0/5 NOT_RUN; GS-117 remains OnHold.

### 2026-10-29 03:09 UTC — live Android, TEST_ONLY ingress, and console route guard

The live Android check above is current for this session: the authorized
`ZA2237MRHN` APK authenticated to `https://192.168.1.6/`, reached
`gs177-test-product`, and refreshed Reports. The exact displayed event is the
historical HOST_SIM EventKey recorded above; it is not physical TC-001 evidence.
The actual app showed backend CONNECTED and marked the event TEST_ONLY / physical
origin not verified. APK bytes match the preserved hash; formal apksigner
verification was not performed.

**Existing implementation → gap → minimum change.** The GS-117 console already
checked the WSL 8445 listen table and GS-179 already provided a read-only Windows
proxy audit. The console treated a WSL-only socket as physical ingress readiness,
even when Windows had no LAN listener. Changed only the existing readiness helper
to require the current WSL listener, the exact `.6:8445 → current-WSL:8445`
mapping, trusted Private/Domain Wi-Fi and a live Windows listener from that
existing audit. It explicitly leaves Hub authentication and a fresh physical
receipt `NOT_VERIFIED`. Classification: `TEST_INFRA_ONLY`; the change prevents
misleading readiness, adds no transport or trust mechanism, and does not alter
Run authorization.

Live audit: WSL `172.17.152.10:8445` is listening; Windows Wi-Fi is trusted
Private `Airtel_Agrim` at `192.168.1.6`, and the expected portproxy row exists,
but the Windows listener count is zero. The console now reports
`hub_ingress=BLOCKED`, `listener=WSL_ONLY`, reason
`windows_physical_ingress_listener_missing`. Firewall-rule details remain
unreadable without Administrator, and no S3 request/receipt exists. Signed-time
UDP 4468 and a valid host-generated RSA-3072 proof were observed; this is not a
physical Hub signed-time or CloudSync receipt. PostgreSQL/local HTTPS/LAN HTTPS
and the live Android login/Home/Reports read passed in the checks above.

The restarted console uses the existing `gs117-tc001-launch.sh`; `/api/status`
returned HTTP 200 and reported the WSL-only 8445 route as BLOCKED. Current
readiness reports USB descriptors for COM4/COM10 matching the recorded C3/S3
identities without opening either port; board qualification remains PARTIAL.
The owner-only fixture is absent, the authenticated Settings route returned
403 to the controller, and the physical Run/TC-001 authorizations are absent.
No physical event was generated.

Focused validation after the readiness change: Python compilation PASS and
`python3 code/tests/python/test_gs117_tc001_console.py` **63/63 PASS**, including
active matching route, WSL-only/no-Windows-listener, untrusted-network and wrong
mapping cases. A direct live invocation of the existing Windows Audit helper
reported listener count zero and the expected BLOCKED result. No certificate,
backend data, firmware, device state or credential changed.
The private route observation is
`~/.local/state/ghar-sajag/gs117-tc001/services-live-20261029T025923Z/readiness-console-ingress-20261029T0311Z.json`
(mode 0600, SHA-256
`2e079c03520b3fd80612c0803f4128a57a7d2414bfdf06c61e3d737fb928e63e`).

Exact next action to make the LAN ingress route live: one elevated invocation of
the existing guarded helper on the current trusted Private Wi-Fi:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\code\tools\local\gs179-windows-lan-proxy.ps1' -Action Start -EndpointKind PhysicalHubIngress -WslAddress 172.17.152.10
```

Its existing Administrator, trusted-network, owned-port and firewall-scope
guards must pass. Afterward, recheck the Windows listener and only regard a
fresh authenticated receipt from the physical S3 as Hub authentication. The
owner-only current-image fixture and independent one-run/five-run approvals
remain required; TC-001 is **0/5 NOT_RUN**, Morning Routine decision is
**NOT_RUN**, and optical PIR is **NOT_RUN**. GS-117 remains OnHold.

### 2026-10-29 03:31 UTC — owner-restored physical-ingress route rechecked

The owner completed the elevated Windows action for the existing
`PhysicalHubIngress` forwarding rule. The current GS-117 console page and
`/api/status` return HTTP 200. Its live read-only audit confirms trusted Private
Wi-Fi `Airtel_Agrim` at `192.168.1.6`, current WSL `172.17.152.10`, the exact
`.6:8445 -> .10:8445` mapping, one active Windows listener and the WSL listener.
Console ingress route status is **PASS**. PostgreSQL, local caregiver HTTPS,
LAN forwarding and certificate-verified laptop HTTPS also report PASS. No
certificate work was repeated.

Route readiness does not establish an S3 handshake. Current status still has
`authenticated_hub=NOT_VERIFIED` and `fresh_physical_receipt=NOT_VERIFIED`;
the bounded ingress trace is absent (zero receipts in the preserved
post-restoration observation). No fresh physical Hub identity or signed-time
proof is available. The earlier nonce/generation-bound host proof was a
host-only test and is expired. The caregiver service's aggregate health field
`HUB_INGRESS_READY=NOT_CONFIGURED` is its separate default-disabled ingress
composition; it is not evidence that the active bounded TCP 8445 listener
authenticated a Hub.

The Settings 403 is the expected existing authorization result for the
currently configured `CAREGIVER` / `FAMILY` account. Household Settings require
the existing `ADMIN` plus durable `OWNER` or `PRIMARY` authority. An eligible
account exists but no owner/primary credentials are configured for this
observer; the Home has no desired/applied configuration row. No role, account,
credential or household data was changed. Use the existing authenticated
Settings flow with an authorized owner/primary administrator; do not bypass the
guard or put credentials in this evidence.

Current USB discovery reports the expected C3 COM4 and S3 COM10 descriptors
only; neither port was opened. The last authorized C3 raw flash-ID attempt
returned JEDEC `0xffffff`, manufacturer/device `0xff/0xffff`, with capacity
unknown. It did not read app bytes, the partition table or selector. That
one-attempt hardware approval is consumed. The owner-only fixture is absent;
the separate physical-run/campaign approvals are absent. No injection, reset,
flash or physical event occurred. TC-001 remains **0/5 NOT_RUN**; Morning
Routine completion and physical APK observation remain NOT_RUN; optical PIR
remains NOT_RUN.

The first physical-fixture gate is a new, narrowly scoped owner authorization
for one corrected, read-only COM4 JEDEC/capacity diagnostic using the existing
reviewed procedure, with SPI flash attach performed before `flash_id()`. It
must stop if identity/capacity is still unexpected; this approval would not
permit firmware/partition reads, reset, injection or the campaign. After a
valid JEDEC result, obtain separate current authorization for any remaining
targeted readback/recovery. Only after all fixture, fresh-S3-authentication and
identity gates pass should the independent five-run approval be requested.

The current sanitized console observation is private at
`~/.local/state/ghar-sajag/gs117-tc001/services-live-20261029T025923Z/console-ingress-readiness-20261029T033127Z.json`
(mode 0600, SHA-256
`72bcf73b862eebdbe69eba9bbb5d6b28c520808cd6a8a18709e6543517fa2be1`).

### 2026-10-29 03:44 UTC — one authorized C3 JEDEC/capacity query

The owner authorized exactly one read-only COM4 identification/capacity query.
Before opening the port, Windows pySerial enumeration matched COM4 to USB serial
`14:63:93:C5:D1:58`, VID/PID `303A:1001`, location `1-1:x.0`. The previous
private readback helper was confirmed to call `flash_id()` before SPI flash
attachment, so it was not reused. The existing Windows esptool 5.4.0 `flash-id`
CLI was used instead. Its source callback and non-hardware checks verified the
order `prepare_esp_object -> attach_flash -> flash_id`, no flash read/write/
erase operation in the callback, version/help availability, and an explicit
single connection attempt with no post-command reset. The complete attempt
used `--chip esp32c3 --port COM4 --baud 115200 --before default-reset --after
no-reset --connect-attempts 1 --no-stub flash-id`.

Result: esptool connected to the expected ESP32-C3/MAC
`14:63:93:c5:d1:58`; manufacturer `0x46`, device `0x4016`, detected capacity
`4MB (XMC)`. Esptool reports those JEDEC components rather than the combined
24-bit value; using esptool's `_get_flash_info()` byte-order mapping, the
corresponding combined ID is `0x164046`. Exit code 0. This clears the C3 JEDEC
and capacity sub-gate and explains the earlier all-ones result: the prior
helper queried before `attach_flash()`, while the corrected official CLI
attaches first and returned a recognized ID/capacity.

The command's `default-reset` entry sequence connected to ROM; its output ended
`Staying in bootloader.` `--after no-reset` intentionally performed no
post-query reset, and no separate reset edge was instrumented. The C3 is
therefore recorded as left in ROM bootloader. No stub, flash write/erase,
partition/image read, other COM port, S3, credential, configuration, event
input or campaign operation was used. The one-query authorization is consumed;
no retry was attempted.

The existing fixture can proceed past the JEDEC/capacity gate, but is **not
fully qualified**: current C3 app/partition provenance and S3 current-image,
identity/time and fresh mTLS evidence remain missing, and the C3 must be
returned to its application state before a functional test. Any such further
hardware operation is outside this one-query authorization. TC-001 remains
0/5 NOT_RUN and its separate campaign approval remains absent.

Non-hardware checks: `py -3 -m esptool version` and
`py -3 -m esptool flash-id --help` report 5.4.0/PASS; AST inspection of the
installed CLI confirmed corrected attachment order and no flash read/write/
erase calls; current COM4 pySerial identity matched before open. No code tests
were rerun because no source code changed.

Private evidence is at
`~/.local/state/ghar-sajag/gs117-tc001/c3-jedec-once-20261029T034458Z/`:
`result.json` SHA-256
`9ba78a7789dae259b9adacdcaba23cbe7c3e8dd60fab8886158ce441a7c0edad`, esptool
log SHA-256
`998df36cc3b5ec73722e485c41ba4e8d2c5e706ff6de5436412456780bdffb03`; files
are mode 0600.

### 2026-10-29 04:03 UTC — bounded service recheck; physical authorization package

The current canonical head before this evidence update was
`8a8e0a082bb2556e3f19075ecc1e0476383046d2` (origin equal; preflight PASS).
No source/helper fix was needed: `git grep` finds no supported JEDEC helper in
`code/tools/local` or `code/tests`. The private mode-0600 readback script is
outside supported source, calls `flash_id()` before attach, and includes other
eFuse/JEDEC reads, so it was neither changed nor run. Installed esptool 5.4.0
source review found that `read-mac` does not attach SPI flash or query JEDEC;
its `--after hard-reset` teardown uses RTS. This is the proposed one-shot path
from ROM to the existing app, not an executed operation. Verify app startup with
the existing `GET_STATE` helper and stop on failure.

At 04:03 UTC, the existing GS-117 `/api/status` returned HTTP 200 and reported
PostgreSQL, caregiver HTTPS, laptop LAN TLS, development endpoint and current
Windows `.6:8445` to WSL `.10:8445` forwarding PASS. The bounded service window
had expired; one launch attempt first exited before binding because the
existing bundled libpq `LD_LIBRARY_PATH` was omitted. Its log is preserved. The
second launch reused the paths from `gs179-laptop-server.sh` and restored the
existing bounded GS179 TEST_ONLY listener on `172.17.152.10:8445`. The existing
signed-time launcher restored UDP `192.168.1.6:4468`; Windows reports the
listener bound. Runtime status still says `real_hub_authenticated=NO`,
`hub_connected=NO`, `monitoring_freshness=UNKNOWN`; the trace file is absent and
the restarted signed-time request count was zero. The runtime's
`trusted_time_ready=YES` is host-generated readiness only. No physical S3
identity, trusted-time or CloudSync receipt is established.

The actual S3 installed-image receipt is from 2026-10-26 and is stale for the
24-hour fixture gate. Current C3 app/partition evidence is also absent; C3 was
last observed in ROM after the approved capacity query. The expected C3/S3 USB
descriptors match without opening either port. Phone `ZA2237MRHN` appears as an
authorized ADB device, but the current APK event was not re-observed. The
owner-only fixture and campaign approval are absent; TC-001 remains 0/5
NOT_RUN. No hardware or database operation occurred in this recheck.

One consolidated approval is requested for a single bounded GS-117 TEST_ONLY
session on exact C3 `c3-146393c5d158` / COM4 / serial
`14:63:93:C5:D1:58`, S3 `hub-e072a1d38d34` / COM10 / serial
`E0:72:A1:D3:8D:34`, Home `gs177-test-product`, and phone `ZA2237MRHN`:

1. Targeted read-only current-image provenance: partition table, OTA selector,
   selected active app region only on C3 and S3, starting with the C3 already in
   ROM. No NVS, outbox, credentials or unrelated region access; no writes/erase
   and no standalone JEDEC query.
2. If COM10 readback/reset clears RAM-only connectivity, one use of the existing
   GS40 encrypted TEST_ONLY configuration recovery to endpoint `192.168.1.6`,
   using the preserved verified artifacts only.
3. After readback, one read-only `read-mac` plus RTS hard reset to return the
   existing C3 app; confirm expected app and HIL state with existing `GET_STATE`.
4. After current fixture and fresh S3 mTLS/time/backend gates pass, run the
   existing five-run controller once: at most five sequential C3
   `INJECT_MOTION` inputs, accept COM4 serial-open reset risk, do not open COM10
   during campaign runs, automatically verify each original EventKey through
   authenticated S3 durable ACK, CloudSync, PostgreSQL, caregiver API and actual
   installed APK, and stop on the first failure. The first successful run is
   the end-to-end smoke result; remaining runs proceed only if it passes.

No credential replacement, enrollment/ownership/database mutation, flashing,
erase, firmware/security change, partition modification, factory reset, retry
after a failed guard, PIR stimulus or additional hardware operation is included.
Recheck USB identities immediately before every port open. The existing
one-use campaign approval file is created only after genuine readiness passes.
This approval request does not authorize execution. The 24-hour S3 receipt,
current C3/S3 readbacks, fresh physical Hub receipt and owner-only fixture remain
the exact gates before the first event.

### 2026-10-29 04:42 UTC — approved readbacks passed; session stopped at C3 liveness guard

The owner approved one exact-device GS-117 TEST_ONLY session covering targeted
read-only C3/S3 partition-table, OTA-selector and selected-app readback; the
existing no-JEDEC C3 `read-mac`/RTS hard reset and `GET_STATE`; conditional reuse
of the existing encrypted GS40 configuration to `192.168.1.6`; then at most one
five-run TC-001 campaign, stopping at the first failed guard/run.

Preflight was PASS at source `ddf3ff4d866213716462f000db7534252f74e64c`; the
origin matched. The existing private readback script passed its non-hardware
artifact self-check. Because its normal read path re-queries JEDEC, a private
one-session copy retained its USB/MAC/chip/security, partition-layout, OTA
selector CRC/state, trusted artifact/version/ELF, and byte-match guards while
removing `detect_flash_size()` and the wrapper that invokes it. It read only
partition table at `0x8000`/`0x1000`, `otadata` at `0xF000`/`0x2000`, and the
expected image byte length at the selected app offset. It did not query JEDEC,
write/erase flash, access NVS/outbox or read unrelated partitions. Its artifact
self-check and static no-write/no-JEDEC checks passed.

Both current readbacks passed against their preserved trusted artifacts:

| Target | USB identity / MAC | OTA selector | Active app evidence |
| --- | --- | --- | --- |
| C3 | COM4 / `14:63:93:C5:D1:58` / `146393c5d158` | valid selector copy 0, sequence 7; `ota_0`, offset `0x20000` | `8cbda4b-dirty`, 958,832 bytes; SHA-256 `591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea`, byte-for-byte match |
| S3 | COM10 / `E0:72:A1:D3:8D:34` / `e072a1d38d34` | valid selector copy 1, sequence 30; `ota_1`, offset `0x420000` | `9bbc6d0-dirty`, 2,273,344 bytes; SHA-256 `c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16`, byte-for-byte match |

Partition-table SHA-256: C3 `219614d3586ae564ce51dfc462e6e7773b590abe41048a10bc513e1a7d799469`; S3 `338f4a83ba90609b4ed0a04514f6378dc90b5d21769e186f49dc3086fd9feabc`.
Both selectors had a valid CRC. Security status from esptool's target detection
was read-only and reported secure boot off, flash encryption counter 0, and
secure-download off. Flash capacity was not re-queried; the prior C3 XMC 4 MB
JEDEC result stands and was not repeated.

After both readbacks, the authorized Windows esptool 5.4.0 command
`--chip esp32c3 --port COM4 --baud 115200 --before no-reset --after hard-reset
--connect-attempts 1 --no-stub read-mac` exited 0, returned
`14:63:93:c5:d1:58`, and issued “Hard resetting via RTS pin.” A subsequent C3
read-only `GET_STATE` returned the expected `HIL_AWAKE_TEST_ONLY` profile,
`hil_build=0`, `hil_control=1`, `physical_wake=0`, and empty retained,
in-flight, and pending state. The complete existing liveness predicate did not
pass: after repeated GET_STATE ACKs over 30 seconds and a final boot uptime of
112,302 ms, `runtime_live=0` and `sensing_live=0`. Current source increments
these values only inside the NodeRuntime owner loop. The HIL UART-control task
works; why the owner loop did not advance remains undiagnosed. The initial
short sample was not treated as the final result; the full bounded poll is the
failed guard.

The approved scope requires stopping at that guard. No S3 configuration
reapplication, C3 motion injection, event DB write, five-run campaign, Android
event observation or PIR test occurred. The COM10 readback used default-reset
bootloader entry and the volatile stub path; S3 RAM-only TEST_ONLY configuration
may have been cleared and was not restored. The S3 was not observed booting its
application after readback. The current owner-only fixture and campaign
approval remain absent; TC-001 remains 0/5 NOT_RUN.

Current non-invasive environment evidence: local WSL TLS and LAN HTTPS at
`https://192.168.1.6/readyz` both returned HTTP 200 with the preserved CA and
reported PostgreSQL reachable. Existing Windows TCP 8445 and UDP 4468 listeners
and the WSL TCP 8445 listener were present. These are route/service checks only;
no fresh physical S3 mTLS, identity, signed-time, or CloudSync receipt was
observed. GS-117 console root returned HTTP 200; its `/api/status` request did
not complete within the bounded request. The supplied Windows ADB executable
now lists no attached device, so no current APK observation was possible.

Private evidence (owner-only, mode 0600) is at
`~/.local/state/ghar-sajag/gs117-tc001/readback-approved-20261029T0435Z/`;
the C3/S3 JSON manifests, binary readbacks, esptool logs and GET_STATE captures
are retained there. No repository firmware/source changes occurred and no
regression tests were rerun. Focused non-hardware checks passed: context
preflight; existing readback artifact self-check; private helper syntax/static
scope check; TLS-verified local/LAN readiness; PostgreSQL readiness. No new
software PASS is claimed. The current session ended at the C3 liveness failure;
further COM/Hub recovery or event injection needs a fresh bounded owner scope.

### 2026-10-29 05:16 UTC — offline C3 authentication-gate diagnosis

No COM port, device, credential, service, or database was accessed in this
investigation. The source confirms that `owner_task()` initializes
`NodeSecurityLink`, sends its initial rejoin, and stays in
`while (!security_link.ready())` while processing authenticated rejoin frames
and paced retries. It can remain there indefinitely if no acceptable S3
response arrives. `sensing_liveness` and `runtime_liveness` are incremented
only after that gate and the authenticated-channel check. Therefore the
session-120 `GET_STATE` values of zero do not diagnose a sensing-loop defect.
The task exits with explicit fail-closed log messages on initialization,
security fault, failed channel retention, or session-allocation errors.

The preserved 29 October C3 captures contain only `HIL_STATE` and
`HIL_OK command=GET_STATE` lines, not the full boot/rejoin log. The HIL control
task is started separately from the owner task, so its acknowledgements prove
the HIL UART path is alive but cannot distinguish an owner still waiting for
authentication from an owner that exited on one of those fail-closed paths.
The current best diagnosis is an unestablished C3↔S3 authenticated association;
the exact owner-task state remains unproven offline. No error log was present
in the filtered capture, which is not evidence that no error was emitted.

The existing 26 October GS40 bootstrap trace is useful historical evidence:
for the then-running S3 app, it records `Authenticated Hub owner started
enrolled=1`, followed by `Authenticated rejoin device=c3-146393c5d158
logical=bedroom session=118` and Node liveness `online=1`. This proves that the
existing C3↔S3 security path worked in that earlier session. The same trace
records signed-time and authority-refresh failures with CloudSync/rules fenced;
it does not prove S3↔backend mTLS. After the 29 October COM10 readback reset,
the RAM-only GS40 config was not reapplied and no S3 application startup was
observed. The latest saved ingress status (05:03 UTC) reports host listener,
PostgreSQL and host trusted-time service ready, but
`real_hub_authenticated=NO`, `hub_connected=NO`, and freshness `UNKNOWN`.
Host readiness is not physical Hub authentication.

The trusted recovery sequence is the existing guarded GS40 `Bootstrap`
procedure: recheck exact USB identities and the expected active image; rearm
the S3's existing TEST_ONLY app/config receiver; accept its live one-use
challenge; construct and send the envelope using the preserved signing root
and ephemeral key agreement/encryption; then observe the target's policy/TLS
validation and startup. The receiver's challenge is boot-scoped and its input
window is 60 seconds; the accepted Wi-Fi/GS40 material is held in RAM. Normal
S3 startup then attempts the independent signed-time bootstrap before it
allows CloudSync publication. C3↔S3 ESP-NOW rejoin is a separate security
exchange and can be observed in the Hub log even when backend time/CloudSync
is fenced. Fresh S3↔backend proof separately requires the target's current
signed-time/authority state and an authenticated physical ingress receipt.

**Next authorization boundary — one readiness-only session, not the campaign:**
authorize one invocation of the existing reviewed protected-bootstrap
procedure for `hub-e072a1d38d34` / COM10, using the preserved GS40 TEST_ONLY
artifacts to rearm the current `9bbc6d0-dirty` app for
`gs177-test-product` and endpoint `192.168.1.6`; in that same bounded session,
allow exact-identity-checked COM4 `GET_STATE` plus existing serial-log
observation long enough to classify the C3 owner gate and observe authenticated
rejoin/liveness. A COM10 reset/reopen can clear RAM config; COM4 open can reset
the C3. Stop on any identity, active-image, config-signature/policy/TLS,
trusted-time, Hub-authentication, or communication mismatch, and do not inject
motion. No readback, JEDEC query, flash/erase, credential/enrollment change,
or database mutation is included. The prior one-use session stopped at its
failed readiness guard, so this is a new authorization. The five-run campaign
remains separately unauthorized until readiness is established.


### 2026-10-29 — proposed standing readiness authorization (inactive)

OWNING_JIRA=GS-117. Affected components: local GS117 controller/launcher,
Windows serial collector, registered controller tests; no firmware, backend API,
rule, credential, or durability contract changed. Existing functionality → gap
→ minimum change: exact fixture/USB/image checks, one-use observation/campaign
consent, protected GS40 challenge bootstrap and Android observer already exist;
consent is tied to historical one-use references; add a local owner-only consent
reader and bounded session ledger around the existing procedure. Classification:
TEST_INFRA_ONLY, authorized by the current standing-HIL implementation request.
Existing one-use campaign/fixture/CSRF/authentication checks remain mandatory.

Authorization audit: owner consent is distinct from technical USB, image,
Home/epoch, TLS, time, rejoin, liveness and ingress guards. Old consumed approval
files are not renewed. Windows elevation/serial exclusivity remain OS controls.
The old bootstrap helper hash and consumed run-directory marker are historical
execution restrictions, not device-security requirements. A prepared private
copy reuses that procedure with the current reviewed helper hash, a private
per-session output directory and an opt-in immediate target-failure stop check.
The historical script is unchanged. `protected-bootstrap-standing-session.patch`
records the small extension without committing protected configuration or keys.

Implementation: `code/tools/local/gs117_hil_authorization.py` validates exact
C3/S3/COM identities, Home `.6` environment, known installed-image receipts,
reviewed procedure hashes, explicit owner reference, activation/expiry/revocation,
operation lists and limits. It serializes standing sessions, reserves before
hardware access and latches failure/interruption before a further attempt can
occur. The durable private ledger and append audit are under
`~/.local/state/ghar-sajag/gs117-tc001/standing-authorization/`; Bootstrap logs
are retained in separate owner-only session directories. Approval is local
operator trust, not cryptographic proof of owner consent: JSON alone does not
grant permission and no browser/remote activation endpoint exists.

The existing launcher accepts `--hil-policy-status` and `--hil-readiness`.
Readiness checks backend HTTPS/PostgreSQL, actual physical-ingress forwarding,
USB descriptors and pinned receipts before invoking only the existing protected
Bootstrap once. It requires advancing C3 runtime/sensing counters in the same
session and an S3 authenticated rejoin for that session, then reuses the existing
exact fixture and fresh physical ingress/time/mTLS checks. A serial response or
host listener cannot establish READY. Missing final fixture/receipt remains a
failed guard; it is never synthesized. This is not a replacement for the existing
five-event Run controller.

`standing-authorization.proposed.json` is a reviewable INACTIVE proposal, not
consent. Proposed scope: at most ten readiness sessions through 5 November 2026
00:00 UTC; one bootstrap per session, zero retries, only the listed devices,
Home, endpoint and image pair. It permits the expected COM10 app reset/encrypted
config restoration and COM4 open/GET_STATE/log collection, including expected
serial-open resets. No injection or campaign is authorized. Flash/erase,
readback/JEDEC, credentials, enrollment/ownership, database mutations, security
bypasses, new identities/environments and unreviewed recovery stay prohibited.
Future motion campaigns require a separately approved scope; their current
one-use controller guard is unchanged.

Activation after explicit owner approval only: install the reviewed proposal as
`~/.config/ghar-sajag/gs117-tc001/standing-authorization.json` mode 0600, set
`active` and `owner_approved` true, record the exact real approval reference and
activation time within the approved validity window. Do not change the approved
scope, hashes or limits. Revocation: set `revoked` true, set `active` false or
remove the active manifest. Expiration or any scope/hash/receipt mismatch denies
access. A failed/crashed session stays latched; investigate and obtain applicable
owner authorization before replacing its activation record. Do not delete the
ledger to retry. Changed firmware, procedures or Home/endpoint require review
and fresh applicable approval. Scope does not authorize security bypasses.

Non-hardware results: console/ADB regression 72/72 PASS; framework 55/55 PASS;
Python compilation and launcher shell syntax PASS. Both standard launcher policy
status and readiness commands return exit 2/BLOCKED with the active manifest
absent, before any serial operation. No active manifest was created, no bootstrap
was invoked and no COM/ADB operation, reset, readback or injection occurred.
Standing policy is implemented, activation awaits one consolidated owner consent.
C3 current runtime/sensing and S3 current boot/rejoin/mTLS remain unverified.
TC-001 remains 0/5 NOT_RUN; GS-117 remains OnHold at the hardware boundary.


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
