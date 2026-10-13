# GS-114 C8 physical readiness — offline decision

## Superseding execution authority

GS-114 comment 10732 and the later user execution instruction authorize deliberate
clean reinstallation/recommissioning of the **existing** disposable R&D pair.
No different spare pair or restore-capable preservation of temporary experimental
state is required. This supersedes the preservation-first/preferred-spare
preconditions below for that fixture. Existing failure evidence and physical
acceptance remain valid records; exact target/port, electrical and operator
operation checks still apply. Follow the active [consolidated execution report](GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
and [TEST_PLAN](TEST_PLAN.md). The rest of this file preserves the earlier offline
decision and its historical evidence; it is not the current execution blocker.

**Date:** 2026-10-13 UTC

**Verdict:** **NO-GO for P1–P9 now; CONDITIONAL GO for a separately approved fixture-preparation task.**

**Scope:** offline review only. No board, USB/serial, power, flash, PIR or physical HIL operation occurred. P1 is **NOT_RUN**; P2–P9 are **BLOCKED**. P10 current measurement belongs to GS-149.

## Confirmed baseline

- Canonical `feature/r1-commercial-baseline` local and GitHub HEAD were `ca87e2cd058586d9c7231df9ab313c4b237f8085` at review start; tracked tree was clean. Context preflight **PASS** (`2026-10-13.001`). The other active Codex process is in the separate dashboard worktree. Existing untracked build/evidence assets were preserved.
- The GS-148 [Option A handoff](../../../exec-plans/evidence/R1_GS148_OPTION_A_20261013.md) records source fingerprint `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`, host and target software validation, and **no physical qualification**. The current `code/build/gs114_fixture_pair/build-jz5absi6/fixture_pair_report.json` has that same fingerprint, ESP-IDF 6.0.3, commissioning-compatible S3 profile, and `physical_status=NOT_RUN`. The retained local C3 app is 939,024 bytes, SHA-256 `ad173384e827614bcbb62c0deac60b5d866dd144088528523c5711e5c2409e43`; S3 app is 1,887,440 bytes, SHA-256 `8c53b999c001095030c7f150854b9637404b666364470131f1511cffdc34a4f7`. These were verified against the actual local binaries. Its embedded C3 asset matches the C3 app. RPF00–RPF08 strings are present in the S3 app; broad S3 HIL-control markers are absent. The separate production-profile build receipt records C3 934,192 bytes, SHA-256 `854c0e6d4e3f5fe9f97fe8e44dda9e4574fb224d04fd4e2924767dc83e48d490`, and S3 1,878,944 bytes, SHA-256 `0affd8c386b9e76aa8a5543f6b0e218466011faecbffd1134a08038db30016e3`; neither receipt is an installed-image hash.
- The fixture S3 build checks 16 MiB flash/8 MiB PSRAM profile, 4 MiB `ota_0` and `ota_1`, 4 MiB `gs_outbox`, 256 KiB `gs_state`, commissioning ON, compiled partition table equal to the candidate CSV, and OTA rollback configuration. This is an engineering fixture profile, not an on-board partition/eFuse/slot readback or commercial signed-image pair. The older Part 2D app hash `48d08726…` is a historical build, not the current app. The earlier GS-148 diagnostic with commissioning OFF/development journal layout remains incompatible with the commissioned pair.
- The saved [stopped run](GS114_PART2_20261012T032500Z_baseline/STOP_REPORT.md) names `GS114-DISPOSABLE-C3-S3`, but that is the **already commissioned pair**, not evidence of a second spare pair. Its boot banners identify an earlier app version and expected MACs, not complete installed hashes or current storage state. The C3 capture began with `USB_UART_CHIP_RESET`; the S3 reported `S3 replay-fence publication failed; admission closed`. No real PIR event or durable EventKey→ACK transaction was qualified. No evidence shows that the GS-148 software correction cleared this physical fault.

## Shortest safe fixture route and gates

**Preferred if confirmed:** a *different*, genuinely spare and disposable C3/S3 pair with AM312. The current record does not establish whether a second pair is available. If an operator confirms one, record its board/serial IDs and wiring, then seek a separately approved clean engineering-image installation and safe observation plan. This avoids modifying the commissioned pair's unknown NVS/LittleFS/OTA state, but does not remove the observer, profile, enrollment or physical-test prerequisites.

**Fallback:** use the existing commissioned `GS114-DISPOSABLE-C3-S3` only after these gates are closed in order:

1. **Provenance/preservation:** identify actual running C3/S3 application hashes, active OTA slots, partition layout, eFuse/security configuration, enrolled identities, pending Node events, and S3 default NVS/`gs_state`/`gs_outbox` contents through a reviewed non-destructive method. Document a state-preserving recovery route and stop conditions. An app-only rollback does not reverse NVS/LittleFS writes; a full-device bundle, factory reset or storage erase is not a recovery plan.
2. **Installability:** verify the exact candidate pair against the actual table and commissioning state. Specify an app-only inactive-slot installation and rollback method that preserves data, with explicit approval before use. No S3 self-OTA receiver or safe app-only updater has been demonstrated. Do not deploy the generated bootloader/partition/OTA full-device package.
3. **Observation:** prove a non-resetting, independent, timestamped C3 and S3 capture route *before* opening either interface. The current pySerial path applies requested DTR/RTS after `os.open()` and coincided with a C3 USB-UART reset; a passive S3 UART TX tap is only a candidate, and C3 native USB Serial/JTAG does not imply an accessible TX-only pin. Review the actual board/electrical routing and verify observer effects on a disposable setup first. One reader per port, no command or reset during baseline capture.
4. **Separate operator authorization:** approve the named boards, exact image hashes, state-preservation/install procedure, observation wiring, stop/recovery steps, and each disruptive case. P1 starts only after a safe image/observer baseline and an enrolled, healthy pair.
5. **Hub admission checkpoint:** under that later approval, capture boot and RPF stage once. Require RPF00/healthy authenticated admission, intact owner and pending-event reconciliation. RPF01–RPF08, unknown authority, C3 reset, or admission closure stop the run; no automatic repair, replay-fence reset, recommissioning or clearing storage. RPF00 alone does not qualify the whole flash lifecycle.

The **first proposed physical action**, after an explicit fixture-specific approval, is a visual inventory of an *already powered-off* candidate second spare pair and its AM312/console connections, recording board labels and connector photographs **without connecting USB, changing power or touching the commissioned pair**. If no second pair exists, the next task is a reviewed provenance/preservation and reset-safe observation method for the commissioned pair; do not begin with its serial port or firmware install.

## P1–P9 supervised sequence and required evidence

Use the [authoritative P1–P9 procedure](TEST_PLAN.md) unchanged. For every executed case keep a unique dated manifest with operator, board/sensor IDs, installed image hashes and slots, source/profile/partition hashes, wiring and supply, UTC times, continuous unfiltered independent C3/S3 logs, before/after `GET_STATE`, real stimulus record, anomalies and exact Node identity/session/sequence EventKey correlation. A MAC send/acceptance or Hub counter alone is not a Durable ACK or single logical effect. Never substitute `INJECT_MOTION` for AM312 optical motion.

| Order | Physical case and evidence required | Present state / extra gate |
|---|---|---|
| 1 | **P1** idle GPIO4 LOW, timer sleep/wake, radio restore; Hub event/ACK count unchanged | NOT_RUN; fixture-specific provenance, installation, observer and healthy-admission gates first |
| 2 | **P2** real AM312 GPIO4 wake, one original EventKey, Hub durable commit/application ACK | BLOCKED; P1 and real PIR/level trace |
| 3 | **P3** real held-HIGH PIR: one event, no sleep loop, resume after LOW | BLOCKED; observe GPIO4 high/low and duplicate absence |
| 4 | **P4** GPIO wake → radio restore → same-key durable Hub ACK → Node retirement | BLOCKED; exact ordered C3/S3 ledger and timing |
| 5 | **P5** Hub-only outage while Node sleeps, real PIR retained, restore with one logical effect | BLOCKED; separate Hub power-operation approval and preserved pending state |
| 6–7 | **P6–P7** Hub-only reboot, stale session rejection/authenticated rejoin, then first real PIR/ACK | BLOCKED; separate reboot approval, new Hub counter baseline, no Node reset |
| 8 | **P8** suppress *one postcommit application ACK* while preserving uplink; same EventKey retry and one authoritative ledger effect | BLOCKED; approved directional ACK-loss fixture **and** read-only per-EventKey durable ledger method; `GET_STATE` counters cannot prove it |
| 9 | **P9** separately observe ACK-in-flight and signed C3 FOTA sleep inhibition/recovery | BLOCKED; P8 fixture for ACK subcase; signed test/recovery images, compatible Hub HIL-control image, validated rollback route and separate physical FOTA approval for FOTA subcase. Current S3 fixture app has broad HIL control OFF. |

**Approval boundary:** This report authorizes no hardware action. Obtain explicit approval for (a) the identified fixture and power-off visual inventory; (b) any observer connection or port opening with reset-safe proof; (c) exact state-preserving installation/rollback, or clean disposable-pair installation; (d) P1–P4 real motion; (e) P5 Hub power-off, P6 reboot and P7 motion; (f) P8 RF/ACK suppression and ledger access; and (g) P9 signed FOTA. P10 and GS-149 are separate. Keep GS-114 In Progress and physical/release acceptance open.
