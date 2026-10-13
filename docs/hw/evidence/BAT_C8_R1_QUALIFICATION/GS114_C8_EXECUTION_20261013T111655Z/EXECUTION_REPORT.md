# GS-114 C8 physical execution

2026-10-13 UTC. Current checkpoint: safe software preparation PASS; Phase A operator confirmation pending. P1–P9 NOT_RUN/BLOCKED. No serial device has been opened or reset/erased/flashed.

Source: `5ee96fd24b4a82b2a11b928cb40f2638eaee9616`, canonical `feature/r1-commercial-baseline`; actual GitHub HEAD matched at startup. Context preflight PASS `2026-10-13.001`.

This execution follows GS-114 10732, which supersedes old experimental-state preservation for the identified disposable R&D C3/S3 pair. Prior failure logs and STOP reports are preserved.

Verified current-source fingerprint: `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`; build receipt records `774da5c2ee8073c535df2fe56ecdbf548c16ebf0` with the Option A working-source implementation. Both current app hashes match that receipt. ESP-IDF 6.0.3 and esptool 5.4.0 activated. No source changes or repeat GS-148 fault campaign.

See [preparation manifest](preparation_manifest.json) for all bootloader/table/otadata/app/outbox hashes, offsets, profiles and exact planned command argument arrays, and [current USB inventory](usb_inventory.txt). Artifact verification and compiled partition decode PASS. Fresh 4 MiB empty LittleFS generated with the component-pinned littlefs-python 0.15.0; host mount with target read/program/cache configuration and empty directory check PASS. This is host evidence, not actual target mount. A preliminary host validation invocation used an incorrect UserContext constructor and failed; corrected API invocation passed without changing the generated image.

Prior `USB_UART_CHIP_RESET` and replay-fence admission closure remain UNRESOLVED HISTORICAL REGRESSIONS. Clean installation cannot qualify recovery of that discarded old state.

## Execution scope

Owning Jira GS-114; affected C3/S3 fixture setup, USB capture, authenticated commissioning, GPIO4 light sleep, EventKey/ACK/durability contracts. Existing GS-150 and GS-148 software receipts are reused after exact source/artifact checks. No runtime, protocol, security, persistent format or app/backend change. Physical tests require actual operator stimuli. Full release/current/GS-148 fault campaigns NOT_RUN; prior mandatory migration FAIL and product P0 PARTIAL remain.

## Case results

| Case | Disposition | Evidence / blocker |
|---|---|---|
| Phase A | BLOCKED | Exact operator board/power/wiring/operation confirmation pending; USB interfaces enumerated only |
| P1 | NOT_RUN | Requires installed/commissioned pair and trustworthy continuous timer/wake logs |
| P2 | BLOCKED | Requires P1 and real AM312 GPIO4 motion |
| P3 | BLOCKED | Requires real held-HIGH/LOW episode and continuous level/sleep evidence |
| P4 | BLOCKED | Requires exact EventKey, authenticated durable commit, ACK class and retirement |
| P5 | BLOCKED | Requires separate Hub-only outage/return approval and operator stimulus |
| P6 | BLOCKED | Requires separate Hub-only reboot approval |
| P7 | BLOCKED | Requires P6 then first real post-reboot motion |
| P8 | BLOCKED | Controlled postcommit ACK-loss fixture and authoritative per-key ledger unavailable/unproven |
| P9 ACK | BLOCKED | Requires P8 link fixture and observed continuous receive during successful MAC/pending ACK |
| P9 FOTA | BLOCKED | Current S3 broad HIL control OFF; matched signed C3 test/recovery images and supported trigger/recovery plan unproven |
| P10 | NOT_RUN | GS-149 owns quantitative acceptance; no instrument/current measurements |

Next action: operator confirmation for exact connected pair; identity/security probes first, stop on mismatch; then supervised clean install and fresh test-only commissioning. No GS-114 Done transition or physical PASS.

## Validation and precise operator checkpoint

- `tools/context/ghar_sajag_context_preflight.sh`: PASS, exit 0, context `2026-10-13.001`, at startup and after documentation edits.
- Retained fixture app hash/size, exact embedded C3, current source fingerprint and S3 profile verification: PASS, exit 0. Both compiled partition tables decoded with IDF's `gen_esp32part.py`; OTA fit and outbox offsets checked. Build reuse only; target compilation was not repeated.
- `idf.py --version`: ESP-IDF v6.0.3, exit 0. Offline C3 `esptool image-info`: valid checksum/hash, C3/4 MB/DIO/80 MHz, ESP-IDF 6.0.3, exit 0. S3 independent image-info is retained in the matching build receipt.
- `littlefs-python create ... --fs-size=4194304 --block-size=4096 --name-max=64`: exit 0. Corrected host read-only image mount with target geometry: empty root directory, exit 0. S3 actual mount NOT_RUN.
- `make physical-hil-catalogue-test`: PASS, exit 0; 99 cases, 68 required and 40 conditional feature mappings checked, `device_access=NONE`.
- `python3 -m py_compile code/build/gs114_clean_install/prepare-20261013T111214Z/live_capture.py`: exit 0. This is an ignored session wrapper around existing `tools.hil.core.SerialCapture` and `FixtureLock`, not a new HIL framework or an executed capture. It requests DTR/RTS low before opening, keeps one reader per port, never automatically reopens a disconnected port, and stores credential-bearing raw commissioning output only under ignored private storage. Syntax check does not prove observation reliability.
- `git diff --check`: exit 0. No firmware/backend/PWA changes, so no new component or release campaign. Prior GS-148 migration FAIL and product P0 PARTIAL remain independently recorded.

Operator confirmation is pending for the live stable identities listed in `usb_inventory.txt`, present safe power, AM312 wiring and scoped Phase A. "boards connectd" established availability; it does not establish electrical facts or authorize an ambiguous erase. Execute the manifest's identity/security argument arrays first, require exact chip/MAC/capacity/security match, then only the confirmed erase/write/verify operations. Commands are prepared, not executed. Boot/capture and test-only `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` must use fresh fixture credentials in private RAM/logs. Do not use the incompatible generic factory `COMMISSION_TEST_NODE` driver.

The S3 commissioning-only image accepts `FIXTURE_STATUS`, **not** `GET_STATE`, broad HIL, ACK-drop or FOTA controls. Canonical P1/P4 Hub-counter snapshots therefore require a verified compatible read-only observation path before complete acceptance; do not label unsupported commands or counter-only reasoning PASS. The current RPF diagnostic emits failure stages only; absence of RPF errors alone is not an observed `RPF00` success. Confirm healthy admission through authenticated durable transactions and capture the required fence proof before qualification. These instrumentation limits remain explicit; no acceptance criterion is waived.

## Subsequent measured work

GS-144 still needs owner acceptance of representative event/outage workload rates, selected battery/power-path usable capacity and reserve, minimum endurance and caregiver latency/reliability bounds. The 150–180 day goal remains aspirational; no measured battery-life claim. Its separate historical workload branch is a read-only provenance source and was not integrated or recreated.

GS-140/B0 requires a real identified instrument, range/burden/sample rate/uncertainty, voltage and measurement boundary. GS-41/42/141/43/44 own comparable B1–B4 BEFORE and GS-51 owns AFTER; current C3/S3 images are not interchangeable with the old `bb34f5e` baseline without a matched-profile decision. None was physically measured here. GS-149 P10 remains blocked by those inputs and GS-114 acceptance; GS-146 also needs GS-119, GS-46 and GS-69 accepted evidence. GS-115 decisions remain C9 REQUIRES_MEASUREMENT/product semantics, C10 MEASURE_ACTUAL_WRITES_FIRST, C11 POST_R1, C12 DEFERRED. No subsequent firmware implementation is approved by these statuses.
