# Storage efficiency host evidence — 2026-10-07

Architecture checkpoint: `94fe1a8`; source base `cd8d126ab44689cc9c6ebbbe74e6dce058d4323b`.
Context preflight PASS, version `2026-10-07.001`. These results apply to the
isolated host primitives/tests in this worktree, **not production firmware**.
Compiler: g++ 15.2.0, C++17, O2, warnings-as-errors, trace disabled.
Host: Intel Core i5-3210M CPU @ 2.50GHz. Shared-host wall-clock results vary;
do not infer ESP32 cycles or physical flash performance.

Reproduce from `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`:

```sh
make storage-efficiency-host-test storage-efficiency-benchmark
make hub-backend-commit-host-test hub-journal-persistence-host-test
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer -I. \
  tests/cpp/storage_efficiency_validation.cpp -o /tmp/storage_efficiency_sanitized
ASAN_OPTIONS=detect_leaks=0 /tmp/storage_efficiency_sanitized
```

Warmup + median of 9 rounds. Lookup/primitives200,000 operations/round; insertion
and retirement128 batches/round at each capacity. Full output:
[raw host log](R1_STORAGE_EFFICIENCY_HOST_20261007.log).

| Capacity | Linear lookup ns | Sorted ns | Hash ns | Fingerprint+exact ns | Per-node sorted ns | Hash erase ns | Hash index bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 192 | 450.86 | 89.43 | 62.43 | 220.95 | 91.16 | 57.63 | 5,828 |
| 384 | 478.40 | 122.16 | 64.35 | 292.28 | 228.34 | 166.67 | 11,652 |
| 416 | 1,308.69 | 226.92 | 91.60 | 265.63 | 66.67 | 106.06 | 12,452 |

| Capacity | Actual volatile HubJournal new commit ns | CRC-frame+index new ns | Current key-only duplicate ns | Proposed key lookup ns | Current retained heap B | Proposed index+all frame fixture B |
|---:|---:|---:|---:|---:|---:|---:|
| 192 | 1,693.62 | 430.25 | 1,843.30 | 68.20 | 77,652 | 22,724 |
| 384 | 963.38 | 342.21 | 1,249.16 | 119.26 | 155,412 | 45,444 |
| 416 | 1,098.81 | 364.83 | 1,180.12 | 146.71 | 160,180 | 49,060 |

Current commit C++ new calls for192/384/416 retained events:969/1,930/2,090.
Current 1,000 duplicate commits:2,000 calls. Core CRC-frame/index fixture:0.
This measures only those volatile slices; current production persistent path
does additional allocations/crypto/recovery. Heap measurements exclude input
fixtures, security/framework queues and allocator headers. Current production
capacity remains128; larger current-reference capacities are volatile lab-only.

Primitive medians: CRC-event encode433.46 ns, decode418.01 ns; current payload
encode with reused vector332.98 ns. The CRC codec alone is **slower in this
comparison**; its reduced record bytes/allocation behavior does not prove an
end-to-end speedup. Earlier bitwise CRC was replaced by1 KiB read-only table.
Moments update2.89 ns; standalone stats encode132.70 ns, decode174.79 ns;
7,168 B checkpoint fixture encode56,241.60 ns, decode38,555.25 ns;
32-record cursor parse8,932.80 ns. Checkpoint fixture consists of256 independent
statistics frames; not a full production household checkpoint. Cursor parsing
does not benchmark erase/GC/root publication. All timings exclude AEAD/flash.

Current sample event:32-byte physical ID,6-byte logical ID,7-byte room,
101 B journal plaintext,129 B legacy AEAD envelope. Host DomainEvent 192 B,
EventKey 80 B, Moments 24 B. Compact plaintext 68 B ordinary/88 B summary;
prospective authenticated record108/128 B needs future envelope/commit integration.
Current durable transition writes more than legacy envelope size: its 72 B
header repeats identity/enrollment/digest in addition to causal payload;
archives/checkpoints/receipts add further traffic. No physical NVS byte/write
amplification number was measured.

For this sample, source-derived native event-transition size is **298 B**:
72 header + (2 string lengths+32 physical+6 logical+16 session/sequence)
+5 enrollment+32 digest+101 causal payload+4 slot decision+28 AEAD.
With maximum allowed strings, ordinary/summary transitions are **455/475 B**
for the current slot adapter with no added effects;1,332 B is the defensive
generic transition cap. These sizes exclude archive/root/evidence writes and
NVS entry overhead;129 B is the legacy envelope, not the current native write.

Tests PASS:

- Codec enum/numeric boundaries, negative timestamps, corruption/truncation,
  malformed frames with recomputed CRC, CRC golden vector and 50,000 fuzz inputs.
- Index capacity192/384/416, forced collisions/wraparound, exact enrollment
  separation, retirement/reuse and50,000-operation randomized churn.
- Statistics values/serialization and count/sum/square overflow refusal.
- **1,000,000 semantic events**, fixed 192-record six-node fixture, repeated
  reconstruction; record pool 17,088 B, index 12,452 B; hot C++ allocations0.
- AddressSanitizer/UndefinedBehaviorSanitizer PASS with leak detection disabled.
  LeakSanitizer cannot run under this environment's ptrace; no LSan PASS claimed.
- Existing `HUB-BACKEND-COMMIT HOST PASS` and
  `P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128 full=129` regressions.

The million-event fixture is bounded RAM/record reuse evidence, not a flash
crash simulator, production retirement certificate proof or backend outage
qualification. No hardware, partition, Node, backend/PWA, BAT-C8 or Jira changes.
