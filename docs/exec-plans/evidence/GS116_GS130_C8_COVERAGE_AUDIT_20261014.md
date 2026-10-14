# GS-116 / GS-130 BAT-C8 coverage integration — 2026-10-14

## Scope and checkpoint

This audit reconciles BAT-C8 P1–P10 with the production code, permanent test
IDs, executable Make targets, local component gates, release registration and
the latest executed software/physical evidence. It reuses the GS-114 reports
and P9 software report; it does not repeat physical tests or run the full
release gate.

- Repository: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Starting HEAD and origin HEAD: `51ffc694308b16672c68e114c74deb8c96d36037`
- Context preflight: PASS, context version `2026-10-13.001`.
- Hardware: not accessed; no serial/USB/IP, reset, flash, motion or commissioning
  operation occurred.
- At audit start, tracked files were clean. Existing untracked PWA assets,
  ESP-IDF managed components, and private GS-114 raw captures/install logs were
  left untouched.

## Findings and correction

The registry has 78 permanent software stages. Effective component selections
are Node 24, Hub 41 and contract 34; the union of fast stages is 68 and the
release selection is 78. Stage fields default to fast unless explicitly
disabled, so counting only explicit `fast: true` flags understates the gates.
The two physical runners are separate opt-in suites and are excluded from all
software gates.

The board-stack E2E suite had a specific C8-P7 simulation gap. Its
`restarts_without_pir` scenario exercised Hub restart and recovery of a
previously pending event, but did not exercise the first newly qualified PIR
event after the Hub reboot. A production-code scenario was added as
`BOARD-TC-130-009` (`first_pir_after_hub_reboot`). It requires an empty event
baseline, Hub restart, a newer authenticated link session, GPIO4-equivalent
`QualifiedInput` admission, exact durable Node retention, one Hub logical
effect, authenticated Durable ACK and Node retirement. The registered board
stage now requires the ninth case marker; it still runs the complete suite.
This is software simulation evidence and does not replace physical C8-P7.

## P1–P10 requirement-to-evidence matrix

| Case / requirement | Production source and automated test IDs | Executable target; local gates | Release gate membership | Latest software result | Physical result and evidence |
|---|---|---|---|---|---|
| **P1 Timer sleep/wake** — actual eligible light sleep, timer wake, radio/owner restoration, no false event. | `firmware/node/power/power.cpp`, `power.hpp`, `node_runtime.cpp`, C3 target adapter. `BAT-C8::light` / `BAT-C8::c8_physical_trace`: `test_physical_wake_profile`, `test_pir_wake_handoff_and_timer_wake`, `test_qualification_diagnostics`. Board case `BOARD-TC-130-004` also covers timer-bounded outage sleep. | `make battery-c8-host-test`; `make validation-node`; relevant board simulation `make validation-board-e2e` → Node/Hub/contract. | `battery-c8` and `board-stack-e2e` are selected by release. | **PASS:** battery-C8 72 C++ checks + 11 Python invariants; board E2E 9 groups / 358 checks. Exact current board receipt below. | **PASS.** 10 real timer sleep/wake cycles, 2026-10-14 00:42:16–00:47:15 UTC. C3 SHA `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814`; S3 SHA `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`; test checkpoint `9674075f1911dbad076fdcdb1c541a283dfbb748`; firmware build source `72a223fc3b290c01c9f93fbb90db83d87601ad54`. [C8-P1](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P1.md). |
| **P2 Real AM312 GPIO4 wake** — real sensor wake, qualified event, durable ACK and retirement. | C3 `sensing.cpp`, `node_runtime.cpp`, C3 target GPIO/wake adapter; `BAT-C8::light`; `BOARD-TC-130-001` (`motion_to_ack`). | `make battery-c8-host-test`; `make validation-board-e2e` → Node/Hub/contract. | `battery-c8` and `board-stack-e2e` are selected by release. | **PASS:** 72 + 11 BAT-C8 checks; `BOARD-TC-130-001` PASS in 9/358 board E2E. | **PASS.** Real AM312 EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1`, event at 00:49:04.638 UTC; one logical effect, Durable ACK and retirement. Same original image pair and run03 campaign provenance as P1. [C8-P2](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P2.md). |
| **P3 Held-HIGH inhibition** — no sleep re-entry/storm during verified HIGH, qualified event once, normal LOW recovery. | C3 `sensing.cpp`, `power.cpp`, `node_runtime.cpp`; `test_sleep_eligibility_and_inhibitors` and `test_pir_wake_handoff_and_timer_wake`; `BOARD-TC-130-004`. | `make battery-c8-host-test`; `make validation-board-e2e` → Node/Hub/contract. | `battery-c8` and `board-stack-e2e` are selected by release. | **PASS:** 72 + 11 BAT-C8 checks; `BOARD-TC-130-004` PASS in 9/358 board E2E. | **Behavior PASS; catalogue PARTIAL for provenance.** Controlled q2 measured GPIO4 HIGH for 28,518 ms, +1,425 sleep-inhibit observations, zero sleep entries with GPIO4 HIGH, one durable event/ACK/retirement, followed by LOW and 11 timer sleep/wake cycles. C3 SHA `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; exact running S3 SHA was not read back. Candidate `ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379` is explicitly not asserted as running. [P3 controlled report](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P3_CONTROLLED_20261014.md). |
| **P4 Motion → authenticated Durable ACK** — restore radio, stable key, one durable Hub effect, authenticated ACK, durable Node retirement. | C3 sensing/PowerPolicy/NodeRuntime; shared frame security/transport; HubRuntime/durable outbox. `BOARD-TC-130-001`, `BOARD-TC-130-002`; `BAT-C8::light`. | `make validation-board-e2e`; `make battery-c8-host-test`; Node/Hub/contract local gates. | Board E2E and BAT-C8 stages are release members. | **PASS:** board suite 9/358; BAT-C8 72 + 11. | **Controlled retest PASS**, EventKey `p15:c3-146393c5d158n8:gs114-c8s1q16` at 03:00:23.713 UTC; one durable effect, idempotent same-key repeat, ACK and retirement. Original q10–q12 three-event observation remains an unresolved separate FAIL. C3/S3 hashes are the P1 pair; controlled retest checkpoint `72716c141a788b251e6b630f4684df12028ea847`. [C8-P4](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P4.md). |
| **P5 Hub outage/recovery** — pending key survives, bounded outage policy, authenticated rejoin, one durable effect and retirement. | NodeRuntime/NodeRecoveryPersistence/PowerPolicy; rejoin/frame security; HubRuntime/outbox. `BOARD-TC-130-002`, `BOARD-TC-130-004`; GS-150 offline sleep matrix; `rejoin` stage. | `make validation-board-e2e`; `make gs150-host-test`; `make rejoin-host-test`; Node/Hub/contract local gates. | All referenced stages are release members. | **PASS:** board suite 9/358; GS-150 1,500 checks (standard and ASan/UBSan) and rejoin coverage reused from the 2026-10-14 P9 evidence. | **Controlled run03 PASS**, q24 `p15:c3-146393c5d158n8:gs114-c8s1q24`, Hub recovery at 04:17:53 UTC, RPF00 OPEN, one durable effect and ACK; post-ACK health had retained 0 and unchanged Node reset counter. Same C3/S3 pair as P1; checkpoint `988fa44ee1207ed67a3a253a5eb2c9dc7813277b`. Limitation: failed-radio-attempt key identity was not directly logged on C3. [C8-P5](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P5.md). |
| **P6 Hub-only reboot/rejoin** — Hub restores identity, stale session rejected, newer authenticated session; Node does not reset. | HubRuntime/journal/outbox, shared rejoin/session/frame security, NodeRuntime. `BOARD-TC-130-003` (`restarts_without_pir`); `rejoin` stage. | `make validation-board-e2e`; `make rejoin-host-test`; Node/Hub/contract local gates. | All referenced stages are release members. | **PASS:** board suite 9/358; rejoin stage result reused from existing 2026-10-14 component validation. | **PASS**, controlled run02: Hub reboot boot log captured, Node rejoined session 4 at 03:41:27.932 UTC; RPF00 OPEN; reset counter stayed 11. C3/S3 hashes are the P1 pair; test checkpoint `1e433477f67cbc01dad8cffa0655e2eec257d409`. [C8-P6](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P6.md). |
| **P7 First motion after Hub reboot** — after fresh authenticated rejoin, first qualified motion under current link state is durably ACKed once. | Shared rejoin/frame security; C3 sensing/NodeRuntime; HubRuntime/outbox. **New** `BOARD-TC-130-009` (`first_pir_after_hub_reboot`); `BOARD-TC-130-003` covers pending-event reboot recovery. | `make board-stack-e2e-host-test`; registered `make validation-board-e2e` → Node/Hub/contract local gates. | `board-stack-e2e` is included in fast and release selection. | **PASS, newly added:** explicit event-free baseline → Hub restart → newer authenticated link session → first qualified Motion → one durable effect → ACK/retirement. Full board suite 9/358. | **PASS**, controlled physical q22 `p15:c3-146393c5d158n8:gs114-c8s1q22` at 03:52:15.856 UTC, under Hub session 4 after P6. One durable effect, authenticated ACK and Node retirement; reset counter unchanged. Same C3/S3 pair; checkpoint `1e433477f67cbc01dad8cffa0655e2eec257d409`. [C8-P7](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P7.md). |
| **P8 Lost application ACK** — suppress one ACK only after durable commit; retry same exact key; one logical effect; duplicate Durable ACK retires Node. | Hub ACK-drop gate/HubRuntime/outbox; authenticated frame security and NodeRuntime retry. `C8-P8-ACK-DROP-GATE::one-shot`; `BOARD-TC-130-002` (`lossy_channel`). | `make c8-ack-drop-gate-host-test`; `make validation-board-e2e`; Hub and Node/Hub/contract local gates. | ACK-drop and board E2E stages are release members; the hardware fixture itself remains opt-in. | **PASS:** ACK-drop host gate 16 checks, ASan/UBSan 16, TSan 16; board suite 9/358. P8 build/profile/embedded-C3 compatibility checks passed. | **PASS**, q14 `p15:c3-146393c5d158n8:gs114-c8s16q14` at 12:12:11 UTC. S3 app SHA `f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`, build source `ce9c436f0e9a8324c0785bad996ed9c4a421de3d`, ACK-drop ON; embedded/installed C3 SHA `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`. First ACK withheld after one durable commit; same key retried; duplicates had `state_changed=0`; authenticated Durable ACK and retirement observed. Stimulus onset was not timestamped; no latency claim. [C8-P8 physical](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_PHYSICAL_20261014.md). |
| **P9 ACK/FOTA sleep inhibition** — pending ACK keeps Node awake through required wait; valid ACK restores sleep. FOTA maintenance/signature/hash/failure/recovery paths. | C3 `power.cpp`, `node_runtime.cpp`; FOTA receiver/secure adapter/boot-health gate; Hub guard/runtime. `GS150-SLEEP::ack_pending_to_idle`; `BAT-C8::light`; `FOTA-HOST-001..034`; `P2-FOTA-S2-GUARD`, `P2-FOTA-S3-ADAPTER`, `P2-FOTA-S4-HASH`; `BOARD-TC-130-008`; signed-FOTA fixture orchestration tests. | `make gs150-host-test`; `make battery-c8-host-test`; `make fota-host-test`; `make secure-fota-adapter-host-test`; `make hub-fota-guard-host-test`; `make validation-board-e2e`; registered local gates Node/Hub/contract. | All cited software stages are release members; physical release evidence remains a separate release-only check. | **Software PASS, host/production-state only:** GS-150 1,500 standard + 1,500 ASan/UBSan; BAT-C8 72 + 11; FOTA host 34; secure adapter 2 groups; board E2E 9/358; signed-FOTA fixture runner 16/16. No target signature/bootloader result is inferred. | **Physical BLOCKED / NOT_RUN for both subcases.** ACK requires bounded long ACK hold or qualified directional RF attenuation plus authenticated target awake trace. Signed FOTA requires matched signed test/recovery images, trusted signing provenance/config, authenticated trigger, verified OTA slots and safe recovery/rollback procedure. [P9 software and prerequisites](../../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run05_software_20261014/C8_P9_SOFTWARE_VALIDATION_20261014.md). |
| **P10 Quantitative current/power** — measured active/light-sleep energy under representative matched workload. | No software result can substitute for current/energy instrumentation; policy counters are not mA or battery-life data. Physical owner/test: `GS-149` / `PHY-GS149`. | No local software acceptance target. Physical measurement procedure and instrument belong to GS-149. | Included only through the release-only physical evidence check when GS-149 marks its required evidence complete. | **N/A / NOT_RUN:** no quantitative current measurement was made or simulated. | **NOT_RUN**, GS-149 owner. Needs a suitable calibrated current/power instrument, representative workload decisions and matched active/sleep capture; report actual values only after measurement. `PHY-GS149` remains NOT_RUN. |

## Gate composition, evidence reuse and limitations

- The `board-stack-e2e` registry stage is required to emit all nine markers
  `BOARD-TC-130-001..009`; it belongs to Node, Hub and contract, and therefore
  flows into fast/release. It is also runnable directly with
  `make validation-board-e2e`.
- BAT-C8 is Node-owned; GS-150 is Node/contract-owned; rejoin and FOTA stages
  are Node/Hub/contract-owned; ACK-drop gate is Hub-owned. The matrix lists the
  stage and local gate for each case. Registry audit found all selected case
  stages reachable from the documented component/fast/release selectors.
- `make validation-framework-test`: **40/40 PASS**, including nonzero failure
  propagation, zero/missing execution rejection, stale source/log/binary receipt
  rejection, all component→fast→release reachability, physical opt-in exclusion,
  P0 PARTIAL rejection and incomplete-stage checks.
- `make feature-coverage-test`: **176 mapped feature rows / 205 source modules /
  15 physical cases; 19/19 framework tests PASS**. This proves mapping and
  registration consistency, not exhaustive semantic coverage.
- `make physical-hil-catalogue-test`: **99 catalogue cases PASS**, no device
  access. The GS-114 case rows now reflect their latest individual reports.
- The board E2E run was source HEAD `51ffc694308b16672c68e114c74deb8c96d36037`
  plus the audited test/registry changes, source fingerprint
  `7e190c8791d6409263ac55d5434947ada4a7e177869b65312d797cd847ed6aaa`,
  `source_unchanged=true`. It reported `cases=9 checks=358 failed=0
  physical=NOT_RUN`, exit 0. The exact report and raw stage log are copied beside
  this file as `board-stack-e2e-report.json` and `board-stack-e2e.log`.
- BAT-C8 current rerun: **72 C++ checks + 11 Python invariants PASS**, recorded
  in `battery-c8-host-test.log`.
- The P9 software report is reused for unchanged GS-150/FOTA stages. It records
  `make validation-node` and `make validation-contract` returning FAIL because
  the complete-product stage emits `product_status=PARTIAL` / `physical=NOT_RUN`;
  its 26 scenario assertions themselves passed. The known Hub journal migration
  assertion `clean migration commits` remains a separate required FAIL. Neither
  result was suppressed or relabeled. `make validation-fast` and
  `make release-gate-final` were not run for this coverage task.
- Physical HIL software gates remain device-free. P3 has measured behavioral
  PASS evidence but its catalogue row is PARTIAL until the running S3 image hash
  is established. P4’s original q10–q12 multiple-event observation and P5’s
  missing per-attempt retry-key observation remain visible. P9 is physically
  blocked; P10 belongs to GS-149.

## Changed files and next owner

- Added production-code regression `BOARD-TC-130-009` and made its marker
  mandatory in the existing board-stack registry stage.
- Updated `MASTER_TRACEABILITY.csv` with the new case and current GS-114
  physical-evidence statuses for BAT-C8, GS-150 and the P8 fixture row.
- Reconciled C8-P1..P9 and aggregate `PHY-GS114` entries in
  `PHYSICAL_HIL_CATALOGUE.csv` with their per-case reports; `PHY-GS149` remains
  separate and NOT_RUN.
- Updated `MASTER_VALIDATION.md` and `R1_WORK_STATE.md`; no product/security
  requirement or firmware behavior changed.

Next: retain GS-114 In Progress until the P3 image-provenance gap and P9 physical
fixtures are resolved; P10 remains GS-149. After this integration checkpoint,
GS-116/GS-130 still owns broader implemented-feature simulation gaps, and the
separately authorized GS-148 CloudSync scope remains distinct.
