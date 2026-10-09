# R1 S3 segmented outbox — first implementation slice

**Date:** 2026-10-09
**Start revision:** `271a2fe24e407c9a1a2860910d50afde737e731a`
**Context:** `2026-10-09.001` (unchanged)
**Scope:** source-level backend, isolated candidate partition geometry and focused host/S3 build checks. No board was flashed.

## Historical 4 MiB constraint audit

| Finding | Evidence and original cause | S3 disposition |
|---|---|---|
| Classic Hub has two `0x1E0000` OTA slots and a `0x20000` (`128 KiB`) `gs_journal` at `0x3E0000`. | `firmware/hub/target/esp32/idf/partitions.csv`; introduced with bounded persistence in commit `7bffce5` (`Add bounded Hub journal persistence foundation`). The commit does not state that 4 MiB was the reason for the 128 KiB allocation, so that specific motivation remains **UNKNOWN**. | Preserve classic target and history; do not carry its partition map into S3. |
| S3 Hub runtime still constructs `HubRuntime(32, 128)`. `HubJournal::attach_persistence` also rejects any persistent capacity other than 128. The NVS adapter addresses per-slot event blobs and separate completion receipts. | `firmware/hub/target/esp32/hub_runtime_adapter.cpp`, `firmware/hub/runtime/hub_runtime.cpp`, `firmware/hub/components/storage/journal.cpp`, `firmware/hub/target/esp32/nvs_journal_slot_store.cpp`. The slot value is coupled to event bodies, identity and completion position. | This restriction remains behaviorally active on the S3 shared application path. It is **not removed by this slice**; replace the runtime persistence call path before claiming scalable Hub admission. |
| A 384-row compact implementation exists in the historical host work. | Historical host evidence describes rows coupling event bodies and identity; it is not in the S3 target component list and has no production call site. | Do not treat 384 as an S3 product limit or copy that layout unchanged. |
| S3 uses `CONFIG_COMPILER_OPTIMIZATION_SIZE`, Octal PSRAM and a 16 MiB flash setting. | `target/esp32s3/idf/sdkconfig.defaults`; the size setting remains a candidate and was not changed here. | Retain pending S3 runtime/performance qualification. PSRAM is volatile and does not replace durable flash. |
| Hub embeds `node_firmware.bin`. | `target/esp32/idf/main/CMakeLists.txt` requires and embeds the C3 image for the existing Node update path. | Retain; it is a required update asset, not an accidental host/PWA payload. |
| PIR episode coalescing and summaries reduce repeated sensor activity. | Existing Node source/evidence and GS-D026. This is semantic and battery behavior, not merely a 4 MiB workaround. | Retain unchanged. No Node or event-protocol code changed. |
| Camera, audio and AI components are not added by the S3 Hub target component list. | S3 target component composition and this build; no broad linker inventory was repeated. | Keep deferred; camera use is not an R1 requirement. |
| Reducer/checkpoint limits, Hub internal-RAM/task-stack bounds and historic retention caps appear in separate designs. | Existing architecture/ExecPlan evidence. Their causes are mixed or not proven to be flash-only. | Do not lift them based on flash size; internal RAM, timing, privacy, protocol and product-policy constraints need their own evidence. |

The S3 target uses a development map with two 4 MiB OTA slots and a 2 MiB NVS journal. That map is unchanged. A separate candidate CSV is validated below; it does not overlap the active CSV in code and was not applied to the preserved board.

## Implemented backend slice

Added `DurableEventOutbox` with a `SegmentStore` interface and an ESP-IDF LittleFS 1.20.4 adapter, pinned in `s3_storage/idf_component.yml` and the generated target `dependencies.lock`. The adapter mounts `gs_outbox` with `format_if_mount_failed=false`, uses bounded segment files, appends frames, synchronizes them through the LittleFS VFS `fsync` implementation, and publishes a fixed-size `head` marker through a synced temporary file plus LittleFS rename and readback.

Each immutable frame contains the canonical EventKey string and caller-versioned payload, with versioned framing, AES-256-GCM confidentiality/integrity, CRC for early corruption detection, and a domain-separated HMAC identity index. A separate HKDF-derived publication key authenticates the 80-byte publication marker, which binds the published ordinal to the exact encrypted frame digest. Recovery rejects a missing/corrupt/contradictory marker, frame gap, duplicate identity or authenticated-frame error. One complete record beyond the published root is retained as an unacknowledged staged record; only its exact EventKey/payload retry may publish it. Replay exposes only published records. The reconstructible HMAC identity index is allocated in 256-entry PSRAM blocks on ESP32, avoiding whole-index reallocations; event payloads are streamed. This index still retains one identity for every stored body and is not the separate post-retirement identity ledger required for safe reclamation.

Candidate `OutboxLimits` reserve 16 × 240 KiB for logical record frames (3.75 MiB), leave 256 KiB of the 4 MiB partition for filesystem/control workspace, and protect a candidate 512 KiB from ordinary admission. These are initial engineering parameters, not measured physical LittleFS occupancy, a certified GC reserve, a critical-event guarantee, or approved product policy. An adapter write/sync/publication error rejects the operation and does not return `Committed`; actual runtime ACK routing is not connected to this class.

Candidate partition geometry was accepted by ESP-IDF `gen_esp32part.py` for 16 MiB flash:

| Partition | Offset | Size |
|---|---:|---:|
| NVS | `0x9000` | `0x6000` |
| OTA metadata | `0xF000` | `0x2000` |
| PHY init | `0x11000` | `0x1000` |
| OTA A | `0x20000` | `0x400000` |
| OTA B | `0x420000` | `0x400000` |
| LittleFS outbox | `0x820000` | `0x400000` |
| State NVS | `0xC20000` | `0x20000` |
| Unallocated system/assets/reserve | `0xC40000` | `0x3C0000` |

This table is an isolated feasibility candidate only. It does not qualify dual-OTA signing/rollback or provide a safe migration from the board’s existing NVS/VFS contents.

## Validation and limits

- `s3-durable-outbox-host-test`: PASS, 6,556 sequential encoded events; 1,110,125 frame bytes in the synthetic six-source mixed sequence; restart, exact duplicate retry, payload conflict, reserve/full distinction, partial append, failed sync, failed publication/retry, missing/corrupt root, earlier torn segment and streaming-order cases.
- Existing `hub-journal-persistence-host-test`: PASS; explicitly still reports old persistent capacity 128 and its 129th-record rejection.
- Existing `hub-backend-commit-host-test`: PASS.
- Existing `hub-durable-provider-host-test`: PASS.
- AddressSanitizer + UndefinedBehaviorSanitizer outbox executable: PASS.
- Full ESP-IDF 6.0.3 `esp32s3` target build: PASS. The app image is 1,791,792 bytes under the active development table. The new object files compile; because no runtime calls them yet, this does not establish that application image size or runtime behavior has changed.
- ESP-IDF partition generator: candidate table PASS.
- `git diff --check`: PASS.

The 6,556-event sequence is a host-generated exact payload stress test, not the existing NORMAL/HIGH workload fixture, 72-hour qualification or physical flash test. Host `SegmentStore` fault cases do not emulate LittleFS flash power cuts. No ESP32-S3 physical storage, erase, wear, latency, internal-heap/stack, FOTA rollback or six-Node behavior was tested.

**Not completed:** S3 Hub runtime/ACK integration; authenticated owner binding at the outbox call boundary; backend transport/replay and durable completion; separate post-body-reclamation identity lifecycle; segment retirement/reuse and sustained reclamation; reducer/routine checkpoint separation; measured physical LittleFS capacity/GC reserve; actual 728 NORMAL, 3,278 HIGH and 6,556 2×HIGH fixture runs; critical-saturation policy; safe storage-format/FOTA migration. Accordingly the old runtime 128-slot limit remains, and neither storage closure nor a 72-hour capacity guarantee is claimed.

## Next implementation boundary

Integrate the outbox behind the existing Hub durability-owner boundary in a separate vertical slice: carry authenticated Node owner and EventKey through admission; adapt `HubRuntime` replay/iteration without materializing an unbounded `HubJournal`; route ACK only from the durable publication result; and add end-to-end lost-ACK/reboot tests. Before connecting backend retirement, specify a durable completion ledger and prove idempotent completion, body reclamation and bounded identity retention together. Measure physical LittleFS capacity/GC and interruption recovery before enabling the candidate partition on hardware.
