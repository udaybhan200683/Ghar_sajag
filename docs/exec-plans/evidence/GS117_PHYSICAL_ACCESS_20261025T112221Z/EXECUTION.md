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
