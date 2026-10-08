# R1 Hub firmware footprint audit — 2026-10-08

The fresh production-profile build is **1,864,624 bytes**, leaving **101,456 bytes**
per existing OTA slot. The first optimization to measure is `-Os` instead of
`-Og`. No optimization was implemented and **measured savings are zero**.
No heavy ML, audio, Boost, iostream, simulation or host-storage prototype was
found in the linked application. Efficient C++ and native ESP-IDF APIs remain
appropriate; a general C rewrite is unsupported by this evidence.

## Baseline and reproducibility

Storage branch `feature/r1-hub-storage-lifecycle`, starting HEAD
`1c3727db2f15122f02e3cf1db7f31b53add5876f` (the preceding capacity evidence
commit, newer than the supplied last-known `17ebe08`). Context preflight PASS
at `2026-10-08.002`. GS-D025–029 remain unchanged. Canonical HEAD
`f27d6ab0944bf3c1871d6185a7cd4ebef357a149` remains clean. The only initial
untracked file was user-owned `prompt.txt`; it was not read or modified.

**MEASURED:** isolated Xtensa target build, linker/ELF attribution and target
`sizeof` results. **SOURCE-DERIVED:** configuration, capacities and execution
paths. **HISTORICAL HARDWARE:** existing single-Node stack logs only.
**UNPROVEN:** optimization deltas, current peak heap/stack, timing/energy effects,
integrated commercial image size, signed Hub update/rollback qualification and
72-hour workload readiness. This audit makes no new release qualification claim.

The snapshot was extracted from committed source into `/tmp/gs-hub-footprint-1c3727d`.
The actual storage-worktree ignored Node-image input and the available canonical
target sdkconfig were copied there; no tracked source/configuration was changed.
Production source is identical to canonical for the Hub and shared paths.
ESP-IDF **v6.0.3**, SDK commit `76f5dedd9950a3012fee8fb7d5586df21fc67802`,
Xtensa GCC **15.2.0**, `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`, project version
`1c3727d-footprint`. The 1,055-step build and partition-fit check PASS.

Inputs/artifacts, SHA256, all retained archives, top objects, exact symbol names,
compiled source list and measured types are in the companion
[JSON](R1_HUB_FIRMWARE_FOOTPRINT_AUDIT_20261008.json). Reproduction commands,
target-size probe, build result and the unmodified stack-test result are in the
[measurement log](R1_HUB_FIRMWARE_FOOTPRINT_AUDIT_20261008.log).
Large temporary ELF/map files are retained in `/tmp`, not committed.

| Measurement | Bytes | Meaning |
|---|---:|---|
| Application `.bin` | 1,864,624 | Actual flashed image, excludes bootloader/data partitions |
| ELF file | 18,451,228 | Includes debugging/symbol information; not OTA payload |
| Flash IROM / code | 717,098 | `.flash.text` |
| Flash DROM / data | 1,042,312 | rodata 1,042,040 + app description 256 + TLS data 16 |
| Static DRAM | 45,783 | initialized data 17,703 + BSS 28,080; an additional 1-byte `.noinit` is outside size-tool total |
| Static IRAM | 87,359 | text 86,331 + vectors 1,028 |
| RTC slow | 64 | initialized 40 + reserved NOBITS 24 |
| Bootloader `.bin` | 26,304 | Separate 28,672-byte pre-table budget; margin 2,368 |
| Embedded C3 image | 931,408 | One FOTA payload, about 49.95% of application image |
| Journal partition | 131,072 | Physical allocation, not application image or measured runtime occupancy |

Size-tool image attribution is 1,864,512 B; the 112-byte difference from `.bin`
is image packaging/padding. Linker DRAM/IRAM unused windows are **not free-heap
measurements**. Wi-Fi `.flash.rodata_noload` debug strings (13,965 B, NOBITS)
are already excluded from the flashed image.

The available canonical old artifact is 1,865,616 B, with a different embedded
Node input (932,928 B versus this worktree's 931,408 B) and project version.
The fresh build reproduces the earlier 1,864,624-byte figure. Its 992-byte
difference from that artifact is **not measured optimization savings**. The
embedded input's version/provenance also needs checking during release packaging;
an audit build is not a signed commercial release candidate.

## Top 20 components by attributable flash

Flash includes retained flash code/data, IRAM initial image and initialized
DRAM/RTC. RAM includes static DRAM + IRAM, excluding dynamic heap/stacks.
These are map attributions, not independent removable savings.

| Component | Attributed flash B | Static DRAM+IRAM B | Classification / why retained |
|---|---:|---:|---|
| main | 1,097,855 | 9,933 | Required R1 code + Node FOTA asset |
| esp_wifi | 225,773 | 41,528 | Required ESP-NOW/station; optional AP subset needs validation |
| mbedtls | 115,162 | 337 | Required PSA/encryption/identity/FOTA support |
| wpa_supplicant | 78,553 | 1,371 | Required secure Wi-Fi; AP/enterprise subsets need validation |
| lwip | 76,260 | 2,482 | Required network framework; IPv6 policy unresolved |
| esp_phy | 47,373 | 11,144 | Required radio/PHY |
| esp_stdio | 46,885 | 16 | Required diagnostics; pooled-string attribution caveat |
| freertos | 20,862 | 9,371 | Required scheduling/queues |
| spi_flash | 18,572 | 16,141 | Required NVS/OTA/flash-safe operations |
| nvs_flash | 15,717 | 24 | Required durable persistence |
| esp_hw_support | 15,239 | 7,498 | Required hardware runtime |
| esp_system | 13,268 | 4,691 | Required system/panic support |
| heap | 12,307 | 7,511 | Required bounded allocation support |
| libc.a | 10,630 | 388 | Required Picolibc formatting/runtime |
| esp_rom | 8,549 | 245 | Required ROM adapters |
| libstdc++.a | 5,627 | 57 | Required C++ helpers; no heavy stream framework |
| esp_mm | 4,046 | 1,082 | Required memory/cache support |
| xtensa | 3,892 | 3,707 | Required CPU/port runtime |
| vfs | 3,734 | 236 | Required console/I/O framework |
| esp_driver_uart | 3,448 | 360 | Required serial diagnostics |

**Merged-string caveat:** IDF assigns 46,345 B of shared pooled strings to
`stdio_vfs.c.obj`'s `console_open.str1.4` input (original input string 12 B).
Other merged string inputs have zero output attribution. Consequently the
46,885-byte `esp_stdio` row does **not** establish a 46 KiB removable console
implementation. Deleting that component would not delete other components' strings.

Largest main objects: embedded image 931,412 B including length word;
`durable_transition.cpp` 31,686; runtime adapter 19,912; security link 18,282;
registry persistence 11,878; Node registry 10,315; durable slot store 9,049;
durability owner 6,485; Hub runtime 6,428; data-plane codec 5,875.
These preserve required functionality; none is approved for removal.

## Top 30 individual flash functions/objects

Sizes exclude unnamed literals/alignment. Aliases with the same address/size
are counted once. Embedded-image size uses end-minus-start symbols because ELF
gives its assembly label a zero `st_size`. This list cannot sum to full image size.
R = required R1 behavior; F = required framework/runtime; P = possibly unnecessary
capability pending policy and differential build validation.

| # | Function / object (namespace shortened) | Flash B | Class |
|---:|---|---:|---|
| 1 | `node_firmware_bin` | 931,408 | R |
| 2 | `secure_owner_task(...)` | 6,808 | R |
| 3 | `esp_internal_sha1_parallel_engine_process$isra$0` | 4,820 | F |
| 4 | `hostap_recv_mgmt` | 4,434 | P |
| 5 | `DurableStore::checkpoint(...)` | 3,579 | R |
| 6 | `ieee80211_sta_new_state` | 3,524 | F |
| 7 | `scan_parse_beacon` | 3,456 | F |
| 8 | `nd6_input` | 3,391 | F |
| 9 | `tcp_receive` | 3,294 | F |
| 10 | `DurableStore::recover(...)` | 3,184 | R |
| 11 | `port_IntStack` | 3,072 | F |
| 12 | `wifi_nvs_cfg_init` | 3,064 | F |
| 13 | `esp_sha512_software_process` | 2,940 | F |
| 14 | `DurableStore::compound_root_digest(...)` | 2,847 | R |
| 15 | `vfprintf` | 2,825 | F |
| 16 | `wifi_softap_set_config` | 2,786 | P |
| 17 | `sta_recv_mgmt` | 2,671 | F |
| 18 | `ieee80211_parse_rsn` | 2,550 | F |
| 19 | `HubSecurityLink::accept(...)` | 2,367 | R |
| 20 | `scan_profile_check` | 2,344 | F |
| 21 | `DurableStore::commit(...)` | 2,314 | R |
| 22 | `tcp_input` | 2,199 | F |
| 23 | `mbedtls_internal_sha256_process$isra$0` | 2,167 | F |
| 24 | `esp_sha256_software_process` | 2,159 | F |
| 25 | `sswu` | 1,973 | F |
| 26 | `hostap_input` | 1,948 | P |
| 27 | `ip6_input` | 1,844 | F |
| 28 | `psa_key_derivation_output_bytes` | 1,830 | F |
| 29 | `psa_key_derivation_input_internal` | 1,740 | F |
| 30 | `esp_err_msg_table` | 1,736 | F |

Software/hardware SHA implementations are selected by PSA/WPA and fallback
paths; similar names do not establish safe duplication to remove. SoftAP code
is genuinely retained through Wi-Fi configuration/dispatch even though this
target initializes station mode. Installer/onboarding/network policy must be
validated before treating it as unnecessary. IPv6 is indirectly pulled in by
lwIP/netif; lack of a direct product call is not proof of redundancy.

## Compiled dependencies, configuration and C++ findings

- The build describes 138 components; 45 retained component/archive groups
  contribute to the application. Compiled-only SDK drivers, Unity/CMock and
  discarded objects do not constitute image overhead. The production source
  list contains 34 product C++ units and one generated Node-image assembly unit.
- No heavy ML/AI inference, audio, bed/camera/fall hardware, Arduino, Boost,
  iostream/stringstream, OpenSSL host fixture, simulation or compact experimental
  storage implementation is linked. R1 bounded routine/rule code stays included.
  Future temperature/camera/fall/pro-response flags default off; flags alone
  are not used as evidence of link exclusion.
- `-Og`, `-ffunction-sections`, `-fdata-sections`, `--gc-sections` are effective.
  Debug DWARF lives in ELF, so stripping it saves **0 application bytes**.
  Global link flags explicitly use `-fno-lto`; no supported global compiler-LTO
  option was found in the installed SDK configuration/CMake path. Latest SDK
  documentation is not proof of pinned v6.0.3 LTO support. Defer manual global LTO.
- CMake requests at least C++17; effective compiler mode is `gnu++26`.
  Exceptions and RTTI are already disabled (`-fno-exceptions`, `-fno-rtti`).
  A wrapped throw trap survives; full exception unwinding/RTTI is not an
  opportunity established here. Picolibc is already selected. A proposed
  Newlib-to-Picolibc saving would double-count an existing configuration.
- `libstdc++.a` contributes 5,627 flash / 57 static RAM bytes. Separately,
  standard-library template symbols compiled into callers total **54,863 B**
  (named retained code/data, not a removable budget): vector-associated 18,911,
  string-associated 15,857, tree-associated 18,170, map-associated 1,252,
  deque-associated 2,260. Categories overlap; do not add them or claim a C
  rewrite saves their total. `std::unique_ptr`/RAII protects ownership; most
  smart-pointer syntax itself is inlined, with allocation costs at runtime.
- `std::map`/`set`, vectors, deque and string are actually used for authenticated
  ownership, retirement assembly, journal identities, causal evidence and rule
  state. Prefer measured, bounded efficient C++ substitutions on individual hot
  paths. Existing radio/NVS/task operations already use native ESP-IDF/FreeRTOS;
  no unused high-level replacement framework was found.
- INFO is both default and maximum compiled log level. HIL/control and product
  trace logging are off. Assertion level 2, diagnostics and panic behavior are
  retained. Dynamic per-tag logging remains enabled with a 31-entry cache;
  no `esp_log_level_set` call was found in product Hub source. SDK/internal and
  field-diagnostic needs still require validation before disabling that facility.
- Full certificate-bundle generation is configured, but its object is discarded
  and bundle symbols are absent from ELF. HTTP client/HTTPS-OTA/cloud transport
  units are also absent from the current linked application. Their eventual R1
  integration can **increase** footprint; zero current linkage does not waive
  backend synchronization or signed automatic Hub application rollback.

Section GC, map interpretation, `-Os` and conditional log-control savings are
supported by [ESP-IDF v6.0.3 size guidance](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-guides/performance/size.html).

## RAM and peak-memory risks

| Source / allocation | Target/source-derived cost | Assessment |
|---|---:|---|
| Secure owner task | 81,920-byte dynamic stack | Largest explicit task allocation; cannot shrink from current evidence |
| Recovery frames | owner 23,584 + owner recovery 6,688 + initialization 512 + checkpoint 14,688 + durable recovery 7,168 = 52,640 B conservative sum | Leaves 29,280 B in allocated stack for remaining callees/interrupt effects; not worst-path hardware proof |
| `InventorySnapshot` | 6,160 B, bounded 384-row inventory | Nested inventory/checkpoint temporaries explain substantial stack cost; lifetime/reuse candidate |
| Four receive queue payloads | data 16×260=4,160; control 8×260=2,080; security 8×260=2,080; health 1×260=260: total 8,580 B BSS | Preserve required isolation/backpressure; capacity cuts can harm admission, latency and Node retries |
| Static queue controls | 11×84=924 B | Native static FreeRTOS queues already avoid their own runtime control allocation |
| Production runtime | `HubRuntime(32,128)`; object 848 B excluding container contents | Legacy HIL `32,1024` instance is excluded |
| Journal records | `DomainEvent` 168 B; 128 inline values =21,504 B + string payload/allocation overhead | Heap vector capacity/reallocation plus separate ID/completion sets; logical duplicates need exact identity preserved |
| Transient ingest queue | up to32 inline events =5,376 B + deque blocks/strings | Moving to a fully preallocated ring could increase idle RAM; preserve overflow behavior |
| Recovery / security objects | RecoveryState256 B, security-link680 B plus dynamic contents | Durable tail/cause bytes, slot-row maps and live journal may coexist during decode/recovery |
| Retirement reassembly | 744 B per reassembler + transport session/map overhead | Up to6 live reassemblers imply4,464 B payload alone; necessary report evidence, not disposable duplication |
| FOTA worker / queue values | worker6,144 B stack; command368 B, ACK328 B; small bounded chunks | No full931,408-byte image heap copy. HIL trigger's3,072-byte task is excluded |
| SDK task stacks | main3,584; event2,304; timer3,584; TCP/IP3,072; IPC1,024 per configured task | Task lifetimes/counts and Wi-Fi internal task allocations need runtime measurement; do not sum as simultaneous peak |
| Wi-Fi buffers | 10 static RX,32 dynamic RX maximum,32 dynamic TX maximum | Nominal static RX~16 KiB; dynamic bounds are not occupancy measurements. Do not reduce blindly during six-Node traffic/OTA |

`std::string` is 24 B before separately allocated contents. Owner authorization,
epoch-confirmation, liveness and retirement maps overlap with security-session
and runtime health/contact maps. Some store different lifetimes/trust domains;
merging them requires correctness evidence. Repeated map node/string/vector
allocation and full `EventKey::str()` construction are fragmentation/CPU risks,
not measured memory leaks. No avoidable second embedded image was found.

Repeated inventory/recovery scans and temporary authenticated blob/row maps can
produce substantial heap pressure while a retained recovery tail and journal
records coexist. Avoid decoding/copying entire sets merely for convenience, but
do not cache away required authenticity/freshness checks. Backend `next_batch`
source can copy events; its transport is not linked here, so its future staging
cost is not included as measured current heap usage.

Historical physical evidence at
`docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/hub.log:104,202`
reports owner startup minimum-free-stack 42,596 /42,660 B for that HIL scenario.
It does not establish six-Node/recovery/compaction/FOTA worst-case headroom.
No new hardware, heap telemetry, battery measurement or allocation trace was run.
Profile minimum free heap, largest free block, allocation failures and stack
high-water marks during six-Node recovery, report/rejoin bursts, FOTA and eventual
backend backlog/GC before reducing stacks, network buffers or queues.
[ESP-IDF RAM measurement guidance](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-guides/performance/ram-usage.html).

## Prioritized opportunities

Estimates below are **unmeasured**, nonadditive, and not approved changes. Unknown
means a numeric saving cannot responsibly be assigned before differential builds
or profiling. A means small configuration work; B means selective code work;
C means high risk, defer. Effort includes implementation only; release checks are
additional.

| Group / component | Current flash / RAM B; why included | Candidate | Estimated flash / RAM saving | CPU/performance; risk | Effort / recommendation |
|---|---|---|---|---|---|
| A1 compiler | Whole image1,864,624 / static45,783+87,359; all product/SDK code | Production-profile `-Os` comparison, same input assets/features | Unknown / unknown until measured; embedded931,408 B remains | Usually less code; optimization exposes UB, timing/stack changes; low code-change risk, full regression needed | Small config experiment; **first** |
| A2 logging control | Shared strings/console attribution46,885 is not removable cost; dynamic tag cache enabled | Disable dynamic tag control only if SDK/field requirements permit; retain INFO and safety errors/assertions | SDK estimate~1 KiB flash /264 DRAM+260 IRAM; not measured here | Less runtime tag overhead; loses per-tag runtime control | Small, conditional second experiment |
| A3 C++ cold helpers | Named STL54,863 + archive5,627; bounds/allocation support | Compare supported `CONFIG_COMPILER_CXX_GLIBCXX_CONSTEXPR_COLD*` options individually | Unknown / unknown; no guarantee all template code shrinks | Smaller helpers may be slower on hot paths; low/moderate configuration risk | Small, selective third experiment; efficient C++ preserved |
| B1 recovery scratch | durable TU31,686 + owner6,485; InventorySnapshot6,160 per value; nested stack52,640 | Reduce redundant inventory copies/lifetimes or share a bounded owner scratch buffer | Unknown / one removed simultaneous snapshot6,160 B potential stack, **not guaranteed total RAM saving** | Fewer copies; reentrancy/lifetime, fail-closed validation risks | Medium; profile first, never simply shift stack to heap and count a saving |
| B2 peer containers | map/tree named code overlaps18,170/1,252; per-peer reassembly744 plus node/key overhead | One validated bounded peer table/native IDs for selected owner maps | Unknown flash; allocation/header/key savings unknown; report payload remains | Linear lookup at≤6 owners may be cheap; revocation/retirement/auth lifetime risks | Medium; optimize one measured hot map, preserve all contracts |
| B3 event copying | journal/event168 each,128 values21,504 before strings; vectors/string helpers shared | Remove redundant ephemeral key strings/copies, use views/moves where lifetime proven; reserve only known needed recovery length | Unknown flash/heap; cannot claim21,504 B eliminated | Fewer allocations/copies; dangling views and retry-identity risks | Medium; measure allocation count/largest block, no storage-format change |
| B4 SoftAP capability | known named hostap/SoftAP functions9,168 B lower attribution; within Wi-Fi225,773 | Station-only SDK build if installation requirements exclude AP | Unknown differential saving;9,168 is **not** a guaranteed removal delta | No station benefit assumed; onboarding/ESP-NOW/network compatibility risk | Small config + meaningful qualification; policy prerequisite, not immediate removal |
| C runtime redesign | Required routines/security/radio/FOTA; libstdc++ only5,627 | Wholesale C rewrite, custom network/crypto/storage, global unsupported LTO | No proven saving | Large safety, durability, portability and timing risk | **Defer/avoid** |

The9,168 B SoftAP attribution is hostap_recv_mgmt4,434 +hostap_input1,948
+wifi_softap_set_config2,786; retained shared helpers and proprietary library
selection prevent translating that sum into a promised saving.
No summed quick-win/moderate saving or optimized image forecast is justified.
The only quantified quick-win estimate is conditional SDK log control~1 KiB;
`-Os` is likely the higher-value test but its saving remains unknown.

Avoid removing signed FOTA/rollback, the embedded update payload, AES-GCM/PSA,
ownership/dedupe/recovery evidence, routine learning, coverage, safety/user/door
features or backend sync. Avoid disabling WPA3, assertions, panic/error diagnostics,
flash-safe IRAM behavior or 64-bit formatting. Shrinking the80 KiB owner stack or
radio queues without peak tests is unsafe. Reducing future IPv6/enterprise support
requires explicit supported-network policy; no such reduction is recommended here.

## OTA and storage consequences

Existing production partition CSV is unchanged. Arithmetic uses the fresh image,
64 KiB application alignment and two equal OTA slots. The8 MiB example is the
prior engineering proposal, not an approved physical module/partition migration.

| Layout | Journal B | Each OTA slot B | Current margin B | Margin after validated savings S |
|---|---:|---:|---:|---|
| Current4 MiB |131,072|1,966,080|101,456|101,456+S |
| Candidate4 MiB /256 KiB journal |262,144|1,900,544|35,920|35,920+S |
| Proposed8 MiB |2,097,152|2,621,440|756,816|756,816+S |

**S=0 in this audit.** Expected optimized image is unknown until an isolated
comparison validates a real reduction. Firmware optimizations free app bytes;
they do not automatically expand durable storage or close capacity/reclamation
proofs. A4 MiB/512 KiB journal layout leaves1,769,472-byte slots: current image
exceeds them by95,152 B. Do not promise`-Os` can make this fit with useful growth.
The256 KiB option fits this existing application but leaves little integration
margin and still fails previously tested supported-volume candidates. It is not
a solution to the72-hour target.

Use [prior capacity evidence](R1_FLASH_OTA_CAPACITY_DECISION_20261008.md) for
physical NVS pressure, conditional36,864/49,152-byte workspace,384-body limit and
unimplemented sustained workspace restoration. No storage suites were repeated.
The current linked application lacks several forthcoming storage/cloud/Hub-FOTA
integration costs, so present OTA margins cannot qualify the completed R1 image.
Preserve two slots, signed firmware validation, automatic application rollback
and storage-schema compatibility across unsuccessful updates (GS-D029).

Evaluating an8 MiB classic ESP32 module is more economical engineering than
large, risky refactoring solely to force the completed system into4 MiB; a
landed module quote and integrated measurements are needed to establish BOM
economics. No MCU migration/purchase is authorized. Flash-only expansion adds
no SRAM; larger NVS caches and authenticated history still need peak RAM tests.

## Validation and next step

- Fresh isolated target build / partition-fit / ELF-size / target sizeof: PASS.
- Existing `test_hub_runtime_stack.py`: **1 PASS,1 FAIL,1 SKIP**. Frame-budget
  test passes (52,640/81,920 B); original-old-ELF test skips because that artifact
  was not provided. Recovery-hook test incorrectly requires `movi.n a10,1`;
  GCC emits equivalent `movi a10,1`. Disassembly verifies an indirect call to
  `vTaskDelay` with argument1. A separate read-only instruction check PASS does
  not erase the original failure. Preserve test; a focused TEST_INFRA_ONLY
  encoding-portability correction belongs in a later authorized test task.
- No source/test assertions weakened; no hardware/optimization variants or
  unrelated storage/release suites run. Context/whitespace checks required
  before evidence commit. Canonical and production paths remain unchanged.

First authorize and measure the`-Os` candidate with identical input asset,
source/config/SDK provenance. Compare `.bin`, per-component sections, stack
frames and timing; run affected ownership/durable-ACK/retry/recovery/routine/FOTA
regressions before accepting it. Then consider dynamic log control and C++ cold
helpers; only undertake container/scratch changes with measured payoff.
Stop at this audit. No optimization or production integration starts here.
