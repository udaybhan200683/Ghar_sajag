# GS-117 physical access recovery — 2026-10-25

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
