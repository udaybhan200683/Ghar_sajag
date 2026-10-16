# R1 flash/OTA engineering decision — 2026-10-08

**Engineering recommendation: EVALUATE_8MB_FOR_R1.** Evaluate a classic ESP32
module with 8 MiB physical flash, a 2 MiB journal and two 2.5 MiB OTA slots.
This is a qualification proposal, not an approved hardware/partition change or
a 72-hour guarantee. No hardware purchase is required now. The current 4 MiB
baseline remains authoritative until explicit product governance approves a change.

Start `17ebe081c90d586e70f8a904c20392bc77af604d`, storage branch,
context `2026-10-08.002` PASS. GS-D025–029 remain LOCKED and unchanged.
Canonical `f27d6ab0944bf3c1871d6185a7cd4ebef357a149` remains clean/unchanged.
Only pre-existing untracked `prompt.txt` was present; it was not read or modified.

```text
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md; R1_RELEASE_CONTRACT.md
DECISION_IDS=GS-D025,GS-D026,GS-D027,GS-D028,GS-D029
TASK_SCOPE=flash/OTA calculations, three frozen SDK capacity fixtures, reclamation counterexample
OUT_OF_SCOPE=production integration, partitions, Node/BAT-C8, backend, governance, hardware, push
```

## Evidence and boundaries

- **MEASURED artifact:** available canonical `firmware/hub/target/esp32/idf/build/
  gs_hw_m1_hub.bin` is **1,865,616 B**, SHA256
  `8a3a91baf00a2fb4480b5afae31e9cbc40bc253800d751abdb815d5046e787fe`.
  This is a file measurement, not a fresh target build or physical qualification.
  Earlier qualified 1,864,624 B remains historical evidence; do not substitute it.
- **SOURCE-DERIVED:** production CSV has 128 KiB `gs_journal`, two
  1,966,080 B slots, 4 MiB flash configuration and application rollback enabled.
  Available image margin is **100,464 B** per current slot.
- **SDK EMULATED:** ESP-IDF 6.0.3, commit
  `76f5dedd9950a3012fee8fb7d5586df21fc67802`; larger capacity objects are
  frozen length-matched ledger fixtures, not authenticated operational history.
  Reclamation counterexample uses actual compact transactions/authentication.
- **HOST-MODELED:** traffic composition, historical encoding, reserve placeholders,
  receipt/consumer completion and long-run workload counts; none are field measurements.
- **UNPROVEN:** production RAM/heap, integrated/signed image growth, power-cut
  behavior on chosen flash, sustained protected replenishment, workload guarantee,
  backend summary protocol, saturation policy and landed commercial BOM.

Prior sources: [compact feasibility](R1_STORAGE_COMPACT_NVS_FEASIBILITY_20261008.md),
[protected Gate C](R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.md),
[72-hour model](R1_STORAGE_72H_AGGREGATION_CAPACITY_20261008.md),
[actual Node counts](R1_NODE_MOTION_CONSOLIDATION_20261008.md).
No new Node consolidation/batching or reduced event rate is assumed.

## Supported workload is a separate product decision

Six powered, locally connected C3 Nodes; backend unavailable for 72 hours.
Existing semantic inputs, already accounting for current PIR consolidation:

| Engineering trace | Node + Hub inputs / 72h | Conditional modeled NVS peak |
|---|---:|---:|
| NORMAL, ordinary / mixed | 1,152 + 24 = 1,176 | 249,856 / 278,528 B |
| HIGH, ordinary / mixed | 5,328 + 24 = 5,352 | 638,976 / 745,472 B |
| HIGH, safety-heavy door/user profile | 5,328 + 24 = 5,352 | 913,408 B |
| Literal STRESS, ordinary / mixed | 10,452 + 24 = 10,476 | 1,204,224 / 1,384,448 B |
| Adverse repeated-motion trace (46s phase) | 68,196 + 24 = 68,220 | Not tested here |
| Earlier abstract STRESS, ordinary / mixed / door-user | 69,696 + 24 = 69,720 | 5,132,288 / 7,913,472 / 10,104,832 B |

The safety-heavy profile assigns 60% door/user traffic; it is a sizing assumption,
not a final critical-event classification. Literal STRESS is not the maximum
permitted household activity and does not supersede the adverse/abstract traces.
The two source ledgers differ in native MotionSummary/exact composition; their
peaks are tied to the specified profile/encoding, not interchangeable guarantees.

**No numeric guaranteed event volume is currently approved.** GS-D025 defines a
72-hour target, not unlimited capacity. Proposed release qualification floor:
NORMAL 1,176 and HIGH 5,352 original semantic inputs, including the defined
door/user-heavy composition, simultaneous six-Node backlog, reboots/lost ACK,
and reconnection/backfill. Seek explicit approval of supported compositions,
maximum exact-event volume, required safety reserve, saturation behavior and
firmware-growth allowance before treating any floor as a commercial guarantee.
Do not exclude all-critical or repeated-motion cases silently.

Keep five budgets distinct:

1. Unretired Node identities: conditional `6*(32+W)=384`, W=32, complete
   authenticated report/owner contracts. Missing reports stop admission safely.
2. Total outage records: 1,176/5,352/10,476+ accumulated semantic inputs;
   retirement does not mean the backend has accepted them.
3. Historical encoding: eligible ordinary observations only; preserve required
   observation points/times/gaps and exact important door/action/safety evidence.
4. Routine recovery: independently durable reducer/manifest/credit dependencies;
   silence after reboot is not fresh sensor coverage.
5. Backend backlog: keep pending information pinned until verified durable
   acceptance; receipt replay/retry must not duplicate business effects.

The present compact transaction also caps **all pinned body rows at 384**.
It cannot retain a full offline trace merely because flash is larger. Durable
history/outbox detachment from drained identity/reducer obligations remains
required. The existing history models are not that implemented protocol.

## Partition arithmetic and comparison

All capacities use binary bytes. Prefix budget 128 KiB covers bootloader at
0x1000 (0x7000 budget before table), table at0x8000 (4 KiB), system NVS24 KiB
at0x9000, OTA metadata8 KiB at0xf000, PHY4 KiB at0x11000, initial4 KiB and
0xe000 application-alignment gap. Both app offsets and sizes are64 KiB aligned;
data is4 KiB aligned. No factory app slot is needed in these two-OTA proposals.
ESP-IDF's installed generator validates all five temporary layouts including
`--secure v1` alignment. That option does not verify firmware signatures.
[ESP-IDF partition requirements](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-guides/partition-tables.html).

| Requested comparison | 4 MiB current | 8 MiB proposal | 16 MiB comparison |
|---|---|---|---|
| FLASH_SIZE | 4,194,304 B | 8,388,608 B | 16,777,216 B |
| NVS_PARTITION_SIZE | 131,072 B | 2,097,152 B | 8,388,608 B |
| OTA_SLOT_SIZE (each of two) | 1,966,080 B | 2,621,440 B | 3,145,728 B |
| CURRENT_IMAGE_MARGIN (each) | 100,464 B | 755,824 B | 1,280,112 B |
| SPARE outside partitions | 0 | 917,504 B | 1,966,080 B |
| PROTECTED_RESERVE | 36,864 /49,152 B conditional workspace in prior compact SDK scope; not critical reserve | Same conditional evidence; larger history mapping needs its own proof | Same limitation |
| NORMAL_72H_STATUS | Existing tested failures; unsuitable | 512 KiB length fixture passes; authenticated72h unqualified | Arithmetic room; unqualified |
| HIGH_72H_STATUS | Existing failures | 1 MiB safety-heavy length fixture passes;2 MiB engineering headroom | Arithmetic room; unqualified |
| SAFETY_HEAVY_STATUS | Unsupported tested volume | Defined5,352 fixture passes at1 MiB; other critical mixes open | Larger modeled room;10,104,832 B abstract door-user exceeds8 MiB journal |
| SUSTAINED_RECLAMATION_STATUS | Safe rejection demonstrated; replenishment missing | Bigger blank capacity postpones failure; not qualified | Same correctness blocker |
| RAM_RISK | NVS estimate~2.75 KiB +keys, plus transaction/runtime buffers | NVS~44 KiB +keys; target peak heap unknown | NVS~176 KiB +keys at8 MiB; significant classic ESP32 risk |
| FLASH_WEAR_RISK | Guard churn and limited space; lifetime unqualified | More distribution possible; actual GC/write amplification unqualified | More capacity does not prove endurance or bounded RAM |
| HARDWARE_COMPATIBILITY | Existing baseline; no new flash detection performed | Qualify ESP32-WROOM-32E-N8 and matching board | Qualify ESP32-WROOM-32E-N16 and matching board |
| BOM_IMPACT | Existing BOM | Physical higher-flash module/board and qualification; landed quote needed | Quote incremental cost versusN8; avoid unsupported price assumption |
| RECOMMENDATION | Do not retain for this commercial envelope | **EVALUATE_8MB_FOR_R1** | Conditional fallback if approved volume/growth needs more; not selected |

Addresses for8 MiB: ota0@0x20000/0x280000, ota1@0x2a0000/0x280000,
journal@0x520000/0x200000, end0x720000. For16 MiB: ota0@0x20000/0x300000,
ota1@0x320000/0x300000, journal@0x620000/0x800000, end0xe20000.
Spare is unallocated engineering space, not a proven runtime reserve.

4 MiB with512 KiB journal leaves two equally sized aligned slots of
1,769,472 B: the available image exceeds each by **96,144 B**. Even keeping
slots just large enough for this image (0x1d0000 each) leaves only262,144 B
journal and34,928 B image growth; prior max mixed NORMAL/HIGH fail there.
No partition-only 4 MiB solution supports the proposed envelope plus useful growth.

8 MiB could use1 MiB journal and two3 MiB slots, leaving1,280,112 B growth
per slot and917,504 B spare. Prefer2 MiB journal with2.5 MiB slots for the
demonstrated storage pressure: it doubles journal capacity while retaining
755,824 B (~40.5% of the available image) growth. This allowance is proposed,
not an approved minimum or forecast of integrated firmware size.
An8 MiB flash-only module does not increase SRAM. Espressif estimates22 KiB
NVS RAM perMiB and5.5 KiB per1,000 keys; transaction copies/buffers and Wi-Fi
add separate costs. 512 KiB/1 MiB/2 MiB/8 MiB NVS estimates are11/22/44/176 KiB,
before keys. [NVS documentation](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-reference/storage/nvs_flash.html).

## Focused SDK physical capacity and reclamation

Frozen object-size vectors preserve prior model SHA256 provenance. No matrix
or workload generator was rerun. Immutable dummy objects include identity,
report, reducer, root, history,8 COW extents,32 hot arrivals and a32-event critical
placeholder. That placeholder is not an approved critical reserve. The fixture
performs32 report/checkpoint/selector update cycles and byte-verifies baseline
objects after remount. It does not implement authenticated history selection or
a new backend protocol.

| NVS / fixture | Logical peak object bytes | Initial physical pages | Peak nonblank pages/bytes | Peak live entries | Free erased pages after churn | Churn GC erases |
|---|---:|---:|---:|---:|---:|---:|
| 512 KiB NORMAL mixed,1,176 |254,606|66|127 /520,192|8,222|1|22|
| 1 MiB HIGH door/user,5,352 |864,910|222|255 /1,044,480|27,742|1|50|
| 2 MiB literal STRESS mixed,10,476 |1,319,566|337|421 /1,724,416|42,283|91|0|

All three load/update/remount checks PASS. One remaining erased page at512 KiB
or1 MiB does **not** satisfy the compact guard's required workspace. These are
physical NVS capacity witnesses, not next-operation certificates or 72h runs.
The protected adapter still accepts only128–256 KiB configurations; larger
compact configurations return UnsupportedConfiguration. Extending its verified
envelope belongs with the replenishment proof, not these dummy size fixtures.
The2 MiB fixture leaves372,736 B of whole erased pages after tested churn,
but future fragmentation/control size is not bounded by that observation.
Earlier modeled peaks already contain COW/progress/reserve allowances; do not
blindly add/subtract the36,864/49,152 B compact workspace and call the combined
representations proven. No8 MiB NVS SDK test or new endurance estimate was run.

The first2 MiB test failed before data I/O because SDK6.0.3 derives its mmap
size from the small host partition table. Explicitly configuring the SDK's
private **host-only** mmap input to4 MiB fixes the harness boundary. The enlarged
synthetic NVS descriptor overlaps an unused dummy app area in this isolated file;
it does not alter or qualify a target layout. The initial failure is retained
in the raw log as an infrastructure counterexample, not a flash-capacity failure.

**Sustainable reclamation is not implemented.** A focused128 KiB real-SDK compact
fixture leaves one acknowledged backend-pinned body intact while26 other bodies
are admitted, recovered/retried after lost ACK, covered by authenticated drained
reports, marked locally complete/durably backend-accepted, and safely collected.
At the next admission: one live row,5,320 logical bytes,17 nonblank pages,
180 live entries and1,822 deleted entries. Only14 pages are certified after
excluding the possible lazy active page; the operation needs15. Three further
attempts write nothing, remount still rejects, current reducer/root/body survive.
No GC erases occur. Logical collection has not restored erased workspace.

The gate's bounded safe-rejection proof remains valid. It is not sustained
progress. Normal NVS dummy fixture GC above cannot be substituted for the guard's
missing replenishment proof. The smallest next correction is a bounded SDK-backed
reserve-restoration operation after authenticated dependency collection, preserving
the selected closure and credits through interruption, recertifying whole erased
workspace before admission. Define a NO-GO if the public SDK operation contract
cannot safely provide it; do not erase pages/reset storage or retry indefinitely.
Also qualify durable history/outbox transfer beyond384 retained body rows before
claiming offline capacity. Backend completion in this test is a trusted host
caller assertion, not qualification of production receipt authorization.

## Hardware, economics and FOTA acceptance

Classic ESP32-WROOM-32E-N8/N16 are manufacturer-listed8/16 MiB options in the
same module family; an ESP32-S3 upgrade is unnecessary to propose larger flash.
Flash-only variants add no PSRAM. Physical compatibility with the actual board,
antenna/straps/supply and provisioning still needs qualification. A partition
table cannot turn a4 MiB chip into8/16 MiB. Confirm markings and detected flash
capacity on the selected physical module before enabling a new build configuration.
[Espressif module datasheet](https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.html).

Indicative indexed distributor pricing at100 units isUS$4.26 forN8 andUS$4.56
forN16, an indicativeUS$0.30 module difference. These are cached listings, not
live quotes, landed India prices, a comparison with the current DevKit BOM or
purchase authorization. Product-page fetches were unavailable; obtain comparable
supplier quotes before choosing the economical commercial assembly.
[Mouser N8 listing](https://www.mouser.com/en/c/?q=ESP32WROOM32&sort=manufacturerpartnumber),
[Mouser N16 listing](https://www.mouser.com/es/ProductDetail/Espressif-Systems/ESP32-WROOM-32E-N16?qs=Li%252BoUPsLEnsC4cA%252BUYB2Bw%3D%3D).

Two OTA slots and OTA metadata are preserved in every proposed layout.
Signed firmware validation and automatic application rollback remain mandatory;
ESP-IDF pending-image validation must succeed or the previous valid application
must return. Layout fit alone proves neither signatures nor failed-boot rollback.
[ESP-IDF OTA contract](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-reference/system/ota.html).
Existing signed C3 FOTA evidence is not a new Hub self-update qualification.
Measure the final integrated/signed Hub image, including embedded C3 firmware
growth/signature overhead, rather than trusting the current artifact margin.

Before purchase: approve workload/critical/saturation and growth policies; close
replenishment and history/outbox correctness using SDK tests; measure target RAM
and image size; obtain comparable N8/N16 BOM quotes; then authorize a selected
module/board qualification. Physical acceptance must include reported flash size,
six-Node admission/outage/backfill, concentrated wear/write amplification, actual
power cuts during GC/publication, signed A/B update, rejected signature and failed
boot rollback with compatible durable state created by the unsuccessful update.
Old firmware must recover supported storage or fail closed, never erase/reset or
silently publish stale state. GS-D029's data rollback exclusion does not waive
application rollback. Node protocol/energy and BAT-C8 requirements remain unchanged.

## Validation and stop

[Raw logs](R1_FLASH_OTA_CAPACITY_DECISION_20261008.log) include5 generator checks,
3 focused capacity passes, the sustainable-progress counterexample and its safe
recovery assertions, unchanged native/compact host regressions, and ASan/UBSan
on the new compact fixture. SDK/OpenSSL archives are uninstrumented; LeakSanitizer
disabled. Context PASS and whitespace checks PASS; canonical unchanged.
Reproduce from the reference-code directory (supply the available canonical
artifact path; no build/flashing required):

```sh
python3 host/storage/nvs_runtime_probe/run_flash_review.py --idf /home/udaybhan/.espressif/v6.0.3/esp-idf --image /absolute/path/to/gs_hw_m1_hub.bin --output /tmp/gs-flash-review.log
python3 host/storage/nvs_runtime_probe/run_compact.py --case reclaim --output /tmp/gs-reclaim.log
make storage-native-transaction-host-test storage-compact-representation-host-test
```

No production/partition/BAT-C8/backend/governance/context changes or hardware use.
Local evidence checkpoint only; no push. Next implement/qualify protected
workspace replenishment under an explicitly approved workload/flash envelope;
production integration remains blocked.
