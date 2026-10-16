# Final bounded 4 MiB versus 8 MiB comparison — 2026-10-09

**RECOMMENDATION=EVALUATE_8MB_CLASSIC_ESP32**, preferably option D below.
Retain NVS. The tested 4 MiB/256 KiB history-plus-workspace configuration fails;
384 KiB leaves only45,552 B unsigned OTA growth and still fails HIGH volume.
Additional classic ESP32 flash offers materially more storage and firmware margin
without a new journal/codec or MCU architecture. This is an evaluation recommendation,
not hardware/partition approval, purchase authorization or production readiness.

Preflight PASS at context2026-10-08.002, storage branch, start
`a0d7ee328af9d80c8f935fad9c65b9eda2c5e09f`. Protected `prompt.txt` not accessed;
canonical and other worktrees unchanged. GS-D025–029 and the LOCKED72-hour target
remain intact; `-Os` stays ADOPT_CANDIDATE pending physical qualification.

## One comparison table

Reverified archived `os/gs_hw_m1_hub.bin`: **1,789,456 B**, SHA256
`129ef8e0ba72e3fb7d9d8618cfda92bb16cec19b1c4d684084db8fb90f368b0d`.
All app/data sizes below are bytes; `@` gives hexadecimal offsets.
Common prefix: bootloader@0x1000 with0x7000 pre-table budget, partition
table@0x8000/0x1000, system NVS@0x9000/0x6000 (24,576 B), OTA metadata
@0xf000/0x2000 (8,192 B), PHY@0x11000/0x1000 (4,096 B), alignment
gap@0x12000/0xe000 (57,344 B); apps begin@0x20000. Bootloader budget is
not a newly measured signed bootloader. No factory app or filesystem is assumed.

| Option | Exact OTA layout: two equal slots | Journal offset /size; end; unallocated spare | Unsigned OTA headroom | Sign-only V2 budget headroom, then integration | Existing NORMAL/HIGH48h and72h evidence | NVS partition RAM estimate, before keys |
|---|---|---|---:|---|---|---|
| A:4 MiB /256 KiB |ota0@0x20000; ota1@0x1f0000; each1,900,544 (0x1d0000)|@0x3c0000 /262,144; end0x400000; spare0|111,088|106,496 minus G; G UNKNOWN|NORMAL48h protected FAIL_CAPACITY; NORMAL72h prior capacity FAIL; HIGH48/72h modeled FAIL|~5.5 KiB|
| B:4 MiB /384 KiB |ota0@0x20000; ota1@0x1e0000; each1,835,008 (0x1c0000)|@0x3a0000 /393,216; end0x400000; spare0|45,552|40,960 minus G; G UNKNOWN|NORMAL48/72h older byte ledgers fit arithmetically, protected run UNQUALIFIED; HIGH48/72h modeled FAIL|~8.25 KiB|
| C:8 MiB /1 MiB |ota0@0x20000; ota1@0x320000; each3,145,728 (0x300000)|@0x620000 /1,048,576; end0x720000; spare917,504 (0xe0000)|1,356,272|1,351,680 minus G; G UNKNOWN|NORMAL/HIGH mixed byte ledgers fit; separate1 MiB HIGH safety-heavy SDK fixture reaches255 pages/one erased page after churn; protected48/72h UNQUALIFIED|~22 KiB|
| D:8 MiB /2 MiB |ota0@0x20000; ota1@0x2a0000; each2,621,440 (0x280000)|@0x520000 /2,097,152; end0x720000; spare917,504 (0xe0000)|831,984|827,392 minus G; G UNKNOWN|NORMAL/HIGH mixed byte ledgers fit; prior larger2 MiB SDK fixture leaves91 erased pages after churn; protected48/72h UNQUALIFIED|~44 KiB|

Installed ESP-IDF6.0.3 `gen_esp32part.py` validates each temporary CSV with
its4MB/8MB limit and normal, secure-v1 and secure-v2 checks: **12 PASS**.
Equal slots/app offsets are64KiB aligned, all data4KiB aligned, no overlaps,
and ends are within actual candidate flash capacities. Validation establishes
partition geometry only, not image authentication or hardware compatibility.
Temporary candidates are under `/tmp/gs-final-flash-layouts`; production CSV
SHA256 remains `561887825ed56c079d10c6c8f7a1b79687dfeba86120a17dc1a89bf19c486e03`.
Reproduce: `python3 <IDF>/components/partition_table/gen_esp32part.py
--flash-size 4MB|8MB [--secure v1|v2] candidate.csv candidate.bin`.
CSV contents are the common NVS/OTA/PHY prefix plus the table's OTA/journal rows.
The spare is unallocated future-layout flexibility, not certified NVS workspace.

## Image growth and signing

G is net production storage/cloud/Hub-self-FOTA integration growth. **UNKNOWN**:
the candidate is host-native and the audit did not measure integrated target code.
No defensible byte forecast exists; assigning zero or a guessed per-library saving
would misrepresent the remaining headroom. Current measurement includes the embedded
Node asset, but is not a finalized signed commercial Hub image.

Installed `espsecure` sign-data V2 normally rounds to4KiB and appends a4KiB
signature sector: the present image would budget **1,794,048 B** (4,592 B extra).
This is arithmetic, not a signed artifact or an approved Hub signing profile.
If the eventual build includes secure-boot-V2 64KiB image padding, budget
**1,839,104 B**, leaving A61,440; B**-4,096**; C1,306,624; D782,336 B before G.
We do not authorize secure boot or any new security framework; this conditional
SDK padding case simply prevents an unjustified signed-fit claim. Actual finalized
signed size and signed bootloader fit must be measured in the approved release path.
Automatic application rollback, validation and storage compatibility with the
previous valid application remain mandatory; two slots alone do not prove them.

Thus256 KiB is the **largest reviewed practical4 MiB candidate with ~111 KiB
unsigned growth**, not a universal mathematical maximum or approved minimum margin.
384 KiB trades away another65,536 B per slot. It is not credible to qualify completed
commercial R1 on40,960 B sign-only growth with unknown G. Even unsigned current
firmware cannot fit a4 MiB/512 KiB equal-slot layout (1,769,472 B slots).

## Storage evidence, workspace and RAM boundaries

Reuse [48h comparison](R1_4MIB_48H_STORAGE_FEASIBILITY_20261008.md),
[workspace proof](R1_256K_48H_WORKSPACE_QUALIFICATION_20261009.md),
[Gate C](R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.md),
[prior larger-flash evidence](R1_FLASH_OTA_CAPACITY_DECISION_20261008.md), and
[measured optimization](R1_HUB_OS_OPTIMIZATION_20261008.md); no suites rerun.
Mixed NORMAL48/72h older modeled physical peaks are233,472/282,624 B;
HIGH48/72h544,768/745,472 B. At384 KiB HIGH shortfalls are151,552/352,256 B.
Those ledgers already include their own COW/progress allowances; don't add the
compact workspace and call the resulting format qualified. NORMAL48h's later
282,624 B ideal protected minimum is a **different** retained-map/certificate
calculation, despite equaling the old NORMAL72h ledger.

Protected compact control/internal reserve is36,864–49,152 B; complete next
ordinary operation needs at least61,440 B, maximal384-row plan102,400 B, plus
the separately excluded possible lazy active page. These sufficient bounds were
proved only within128–256 KiB SDK scope. **B/C/D currently return unsupported
configuration through that adapter**. The guard must be extended and revalidated
for the selected size; larger physical space doesn't authorize weakening it.

Larger prior SDK fixtures used length-matched opaque blobs, not authenticated
NORMAL/HIGH48/72h admission/history runs. The1 MiB safety-heavy and2 MiB larger
fixtures are different traces; their page counts are not a duration guarantee.
Sustainable workspace replenishment remains unimplemented; logical deletion/purge
doesn't certify erased pages. The384 active identity rows remain distinct from
total outage backlog. Authenticated history/outbox transfer, complete coverage/
routine recovery, backend completion and safe saturated operation remain unqualified.
No cloud-dependent reclamation is credited during an internet outage.

NVS RAM figures follow Espressif's approximate22KB/MiB partition and5.5KB/1,000
keys estimates, not measurements. Key caches, transaction copies, Wi-Fi/FOTA
peaks and the previously audited ~80KiB owner stack add costs. Flash-only N8
adds no internal SRAM or PSRAM. Actual six-Node minimum/largest heap and stack
high-water measurements remain release-critical; additional flash doesn't fix RAM.
[ESP-IDF NVS sizing](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-reference/storage/nvs_flash.html).

## Hardware and price snapshot — not a landed BOM or approval

Classic **ESP32-WROOM-32E-N8** is an8MiB flash/no-PSRAM manufacturer variant;
the actual module must physically contain that flash. Reconfiguring a4MiB DevKit
cannot enlarge its chip. Board pinout, antenna, supply, straps, flash detection,
flash-mode/configuration and signed OTA/rollback must match the chosen hardware.
No ESP32-S3 is proposed. [Manufacturer module comparison](https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.html).

Web snapshot checked2026-10-09; quantities/prices are listings, not reserved stock:

- **Bare modules:** DigiKey N8 cut tape ₹550.37 at1, ₹415.21250 at100,893 listed
  in stock; N4 ₹476.79 at1, ₹359.12470 at100,4,139 listed. Like-package delta
  is ₹73.58 at1 /₹56.09 at100 before landed costs. PCB, regulator, USB/programming,
  assembly/test, shipping/taxes and support are extra; not a ready-made board price.
  [N8 listing](https://www.digikey.in/en/products/detail/espressif-systems/ESP32-WROOM-32E-N8/13159522),
  [N4 listing](https://www.digikey.in/en/products/detail/espressif-systems/ESP32-WROOM-32E-N4/11613125).
- **Ready-made classic board:** 7Semi DC-10115 /ESP32-DEVKIT-IE advertises8MiB
  WROVER-IE, ₹1,034.88,52 in stock, Mumbai dispatch. Tax/shipping/antenna inclusion
  and exact module/pinout require confirmation. Its external IPEX antenna is a
  separate compatibility/BOM consideration. [Manufacturer board listing](https://7semi.com/esp32-devkit-ie-esp32-wifi-ble-development-board-8mb-ipex/?setCurrencyId=1).
- Espressif ESP32-DEVKITC-VE at DigiKey lists ₹1,051.05 but **zero stock**;
  therefore not an immediate available-board quote.
  [Distributor board listing](https://www.digikey.in/en/products/detail/espressif-systems/ESP32-DEVKITC-VE/12091812).
- A ₹944 ex-GST DevKitC-VE listing claims5 available but mixes classic LX6
  and ESP32-S3/LX7 features: **do not use as verified compatible supply**.
  [Conflicting listing](https://www.electropi.in/espressif-esp32-devkitc-ve-development-board).

WROVER boards reserve GPIO16/17 internally; they are not assumed drop-in DevKit-V1
replacements. PSRAM is not an R1 dependency or credited RAM fix.
[Official DevKitC pin restrictions](https://documentation.espressif.com/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html).
Current DevKit-V1 commercial price, repeatable landed8MiB board supply, volume BOM
and peripheral/enclosure compatibility are **UNKNOWN**. Obtain an exact-SKU quote
and compatibility confirmation before requesting hardware approval or purchasing.

## Decision and stop

Evaluate D:8MiB classic ESP32,2MiB NVS, two2.5MiB slots,896KiB unallocated.
C reduces NVS RAM/space and maximizes app growth; D better accommodates the
already demonstrated safety-heavy storage pressure while retaining substantial
firmware allowance. Neither qualifies72h automatically. Final supported event
volume, critical reserve/saturation and actual integration growth remain open.

**NEXT_ACTION:** obtain one written landed quote and pinout/module confirmation
for a classic8MiB candidate, then seek explicit hardware-direction approval.
After approval, resume the existing bounded NVS replenishment/history mapping
and integrated signed-image/peak-RAM qualification; no redesign or new automatic
investigation is started here. No requirement, production source/configuration,
partition, BAT-C8, hardware purchase, canonical edit, push or merge.
