# R1 storage encoding density — 2026-10-07

Initial context preflight **PASS**, local/canonical `2026-10-07.002`; starting HEAD `b833b3a1f9bfb951efc25c7d9e245ca42de94b82`. Branch `feature/r1-hub-storage-lifecycle`. This is host-only evidence and proposed architecture. It does not qualify production storage, radio, sensors, backend service, encrypted flash or hardware.

[ExecPlan section22](../active/R1_HUB_STORAGE_DATA_LIFECYCLE.md) contains the complete lifecycle, byte grammar, security, RAM, retirement, wear, FOTA and128 KiB reservation analysis. [Persistent inventory](R1_STORAGE_PERSISTENT_FIELD_INVENTORY_20261007.csv) has81 entries with bytes/format/copies/writer/reader/persistence rationale/reboot/dedupe/backend/routine/diagnostic/lifetime/classification. [Raw benchmark and cold output](R1_STORAGE_ENCODING_DENSITY_20261007.log), [sanitizer output](R1_STORAGE_ENCODING_DENSITY_SANITIZERS_20261007.log), and [regression output](R1_STORAGE_ENCODING_DENSITY_REGRESSIONS_20261007.log) are preserved.

## Reproduction

From `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`:

```sh
make storage-density-host-test storage-density-benchmark
python3 host/storage/cold_probe.py
make storage-efficiency-host-test hub-backend-commit-host-test hub-journal-persistence-host-test
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer -I. tests/cpp/storage_density_validation.cpp -lcrypto -o /tmp/gs-density-sanitized
ASAN_OPTIONS=detect_leaks=0 /tmp/gs-density-sanitized
```

The benchmark writes twelve bounded independent cold fixtures to `/tmp/gs-density-cold-blocks.trace`; the Python probe consumes them. No firmware compressor dependency. Leak detection is disabled for the existing environment ptrace restriction; **no LeakSanitizer result claimed**. Compiler flags and raw output are preserved. Host wall-clock nanoseconds are medians of9 runs after warmup; codec runs30,000 iterations, boot runs1,000. Timings exclude target AEAD/flash, interrupts/Wi-Fi and ESP32 cycles. OpenSSL allocations are outside portable codec allocation counting. The benchmark's actual current-code encoders use existing production implementations, not a guessed struct size.

## Results and limits

**PROVEN within host scope:** all six lossless numeric codec models roundtrip, full signed/unsigned extremes, canonical varint boundaries/rejection, summary extension, immutable context/dictionary boundary/restart, unsupported schema/context serial/epoch/domain rejection, random indexed read and index rebuild, 50,000 bounded negative-decode probes, CRC byte-tear/COW old-new selection models and synthetic host AES-GCM AAD/position/nonce/cipher/tag binding. Full fallback summary raw101 B/HOT124 B/WARM103 B is asserted. Prior exact-index collision/capacity/backshift/wrap/statistic tests remain passing. One million semantic inputs retain at most192 exact keys in explicitly owner-released fixed storage; no C++ new in that portable path.

```text
DENSITY_LONG_RUN events=1000000 peak_keys=192 fixed_pool_RAM=34080 index_RAM=12452 hot_new=0
STORAGE_DENSITY_HOST_PASS codec/context/random-access/AEAD-binding/byte-tears/COW-model/bounded-lifetime
HUB-BACKEND-COMMIT HOST PASS
P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128 full=129 replacement/dedupe/restart/tamper/write-fault/reducer-replay
```

ASan and UBSan PASS for new validation executable. Existing storage efficiency million-event regression also PASS. Native capacity128 /Full129 remains an implementation fact; this run does not resolve it in product firmware.

**PROTOTYPED:** fixed binary, canonical varints, signed time/sequence delta, per-sector immutable context, presence/dictionary selectors, exact unit/receive-offset relations. Raw bodies have no authentication. Mock sector CRC +commit proves accidental tear handling only; the separate host AES experiment proves binding requirements with a synthetic key. Externally selected extent/count/serial/epoch/domain are trusted model inputs. Neither root publication, nonce reservation nor erase/rollback inventory is implemented. A raw contextual decode under wrong context can produce different valid values; authenticate the selected context/envelope before decoding.

NORMAL distribution (384 source records/day; source summaries120, other source families24):

| Codec | Raw median /p95 /mean B | HOT median /mean B | WARM median /mean B | Encode /decode ns |
|---|---|---|---|---|
| Fixed |64 /84 /70.25 |84 /90.25 |66 /72.25 |364.33 /514.81 |
| Varint |27 /36 /29.8125 |52 /54.5 |29 /31.8125 |123.73 /363.50 |
| Delta |22 /31 /23.2135 |44 /46.6042 |24 /25.8490 |150.37 /360.51 |
| Immutable context |18 /27 /19.2161 |40 /42.6875 |20 /21.8490 |119.51 /329.06 |
| Presence/dictionary |15 /24 /16.0026 |40 /39.625 |17 /18.8750 |121.60 /298.36 |
| Recommended exact relations |12 /19 /12.5938 |36 /36.1354 |14 /15.53125 |135.17 /294.96 |

HOT/WARM values include candidate framing; per-sector context/auth footer and unused space are additionally charged in whole-sector capacity runs. WARM uses actual independently restarted boundaries, which differ from HOT. Recommended raw global max101 B, HOT124 B, WARM103 B; trace max is smaller. Six-row proposed authenticated context/header+footer404 B;4 KiB independently recoverable segment, no prior record dependency, max497 entries derived from minimum114-byte one-context header and8-byte entry. Source string dictionaries/security roots remain proposals, not covered by numeric roundtrip.

Deterministic fixtures represent six interleaved room/kitchen/bathroom sources, first motion/immutable repeat summaries, software-domain door/button/control/CallFamily and sequenced Heartbeat examples, origin/rejoin changes, delay and time-uncertainty changes. Repeated PIR edges are not persisted events. Battery0 matches no-ADC target behavior. Unsequenced periodic NodeHealth is excluded. Backend interruption does not create extra source activity; fixture commentary models Day1/Day2 unavailable and Day3 backfill, but the codec benchmark does not implement a backend outage scheduler or daily reducer. Derived Hub connectivity/device-transition/critical/daily envelopes still require APIs; exact normal ancillary rate is OPEN. Capacity runs add one300-byte daily plaintext object/day. Critical8 KiB is independent; ancillary normal events consume the remaining pool. The [three-day scenario annotations](R1_STORAGE_ENCODING_DENSITY_SCENARIO_20261007.csv) accompany the deterministic source fixture with explicit Node failure/rejoin/health, Hub connectivity, backend interruption/recovery, critical domain event, daily identity and duplicate/late/backfill steps. These are test-design annotations, not a newly executed backend/coverage model or encoded extra records. Derived effect rates/sizes must be added before a product outage guarantee. Current raw source preservation alone is insufficient to claim complete backend/coverage recovery.

**PROPOSED conditional budget:** fixed100 KiB +variable28 KiB =existing128 KiB. Fixed includes active28 KiB, retirement12 KiB, model/day/reducer three6,144-byte checkpoints20 KiB, roots8 KiB, segment/lifecycle/dictionary8 KiB, GC/COW12 KiB, critical8 KiB, engineering4 KiB. No RAM index counted as flash and no triple event payload copy. Active65-byte witnesses retain key21+HMAC32+assignment4+original receive8 after other body obligations clear; keep the smaller full compressed body instead where safe.434 rows fit7 independently authenticated witness sectors.416 capacity still depends on unimplemented384-key persisted retirement-credit invariant +32 COW margin. Existing target registry supports10; six-Node budgeting requires six-source admission or rederivation for10. Current native six-Node full report snapshot is measured3,485 B, not previous legacy/conservative bounds.

| Rate/day | Recommended pool source records | Hours /days | Fixed binary same pool records | Three days incl100 KiB fixed +daily |
|---|---:|---|---:|---:|
|384 |1,595 |99.6875 /4.153646 |383 |126,976 B |
|1,776 |1,476 |19.945946 /0.831081 |377 |208,896 B |
|23,232 |1,619 |1.672521 /0.069688 |365 |1,339,392 B |

72 h NORMAL1152 source+3 day entries uses6 sectors +fixed100 KiB =126,976 B,4,096 B spare. **Exact trace packing, conditional reservation; not a guaranteed outage horizon or approved72-hour requirement.** Root/dictionary/nonce/peak COW coexistence and ancillary effects could invalidate it. Worst103-byte WARM escape fits35 entries/404-header sector, not a1152-record guarantee. Same7-sector NORMAL pool retention improves1595/383=4.16449× vs fixed; full one-day fixed/recommended WARM sector bytes28,672/8,192=3.5×. Current native logical write ledger is664 B/event first cycle,1,408 at32nd cycle,1,036 average through128; physical NVS overhead/current occupied storage is unknown. Current native already uses one archive body across journal/outbox/history; do not falsely claim removal of two current full copies.

Routine candidate2,848 RAM /2,560 flash, current-day512, coverage208 included; daily300 plaintext/320 standalone authenticated. Thirty/ninety/365 daily bodies9,000/27,000/109,500 B; independently blocked allocation12,288/28,672/118,784 B. Daily-only7-sector ceiling91 days is **not authorized source-backlog substitution**. Missing observation remains distinct from inactivity under GS-D022/023; actual model/coverage/day/time recovery is not newly implemented.

Index12,452 B PROTOTYPED; complete retrieval directories/index22,161 B and39,017 B total engine+stack allowance PROPOSED. Boot O(partition bytes +bounded entries), scan<=128 KiB; no previous-record decode chain. Host exact lookup54.30 ns, random read317.42 ns,32-record rebuild23,586.71 ns; no target cycle/RAM qualification.

Optional Python zlib: twelve full-context32-source blocks9,570 ->4,233 B,4,473 with20 B/block auth/commit allowance. Encode/decode123,430.99 /7,517.80 ns/block; traced Python encode peak300,905 B/decode23,585 B. Target code/RAM unknown; no general compressor selected. Independent restart context included, not free.

**OPEN / STOP:** offline horizon and saturated critical behavior; semantic/daily substitutions and backend revisions; complete exact canonical witness and retirement-credit progress; string dictionary churn/lifetime; trusted time/late correction/coverage; authenticated append extent/root/nonce/GC/COW proof and flash encryption/program alignment; target wear/endurance/runtime RAM; enforced rollback/minimum reader and firmware growth reserve. No new format/storage API is production-ready.128 KiB CONDITIONAL; enlargement not proven necessary. Previous current image1,864,624 B has101,456 B margin in existing1,966,080-byte OTA slots; prior384 KiB lifecycle layout fails current image,256 KiB leaves35,920 B. Build evidence preserved in [prior refinement](R1_STORAGE_FIRST_REFINEMENT_20261007.md); no production source changed so no redundant build/hardware run.

Static checks PASS: reservation sums, witness packing, daily packing, maximum frame arithmetic, workload/72-hour calculations,81 inventory entries, evidence/document relative paths and `git diff --check`. Header audit removed16 redundant bytes/segment; final experimental context is36-byte prefix +6×58-byte rows +CRC4 =388 B; candidate authenticated overhead404 B. Prototype-only version2 rejects the earlier exploratory grammar. After all analysis/testing, canonical GS-D024/context update will be committed separately; final preflight is intentionally expected STALE at local.003 vs designated canonical.002. Stop at that result; no automatic promotion or guard override.


## Full-source sizing correction

[Additional raw packing output](R1_STORAGE_ENCODING_DENSITY_IDENTITIES_20261007.log) includes exact source-string cost, native config-version/hash36 B, and deterministic20 ms timing/receive jitter. The core numeric codec/sector roundtrips remain as above; full identity/configuration serialization is PROPOSED, not implemented. Recommend self-contained full source dictionary/config at each restart, encrypted under the existing-strength envelope. It costs728 B/header for the sample32/6/7 names and1,370 B at maximum64/24/64 lengths. No plaintext sensitive-header deployment is approved.

Under the same conditional fixed100 KiB and variable28 KiB: jittered sample names retain1,281 NORMAL (80.0625 h/3.335938 d),1,347 HIGH (18.202703 h/0.758446 d),1,457 STRESS (1.505165 h/0.062715 d). Same full-source fixed baseline350/343/336 records; NORMAL gain3.66×. Max names+jitter:1,056 /1,103 /1,181 records.72-hour NORMAL sample needs131,072 B (zero spare); max names135,168 B (4,096 deficit). Numeric uniform126,976 B result remains a narrower comparison and must not be used as a guaranteed production horizon. No72-hour product requirement, new partition or full-format compatibility is approved. Header/cipher/dictionary/config/replay/peak allocator and wear proofs remain OPEN. See ExecPlan22.10 for byte layout, confidentiality, root dependencies and corrected interpretations.

## Interruption recovery and final closeout

Resume inspection preserved every existing change. Initial preflight again
PASS at local/canonical2026-10-07.002, HEADb833b3a. Existing final host validation
and benchmark are preserved in the identities log; regression log contains
all three PASS gates. The final temporary sanitizer output is byte-identical
to the preserved sanitizer log (SHA256
`95d818150a263328a5a3016cdb93bf29675dc0fe1313f4745363805defd89a5e`).
It contains the million-event terminal PASS and no sanitizer diagnostic; the
original process/session exit-status handle was lost at interruption. No
expensive passed validation or sanitizer run was repeated. No LeakSanitizer
or physical qualification is claimed.

Only the missing one-day source-size comparison was completed using the
unchanged codec via `./build/storage_density_benchmark --closeout-sizing`.
This fast report roundtrips every input and skips CPU/lifetime benchmarks.
Full-name/config serializer remains PROPOSED; cost is accounted by restart
header size. Each WARM/HOT packing pass independently restarts contexts; this
changes the exact average/median even for identical logical source events.
Header/tail costs are additional to the entry sizes below.

| NORMAL variant | Header B | Raw median/mean B | HOT median/mean B | WARM median/mean B | Retained source records/hours including daily |72h total B |
|---|---:|---|---|---|---|---:|
|numeric uniform |404 |12/12.5938 |36/36.1354 |14/15.5312 |1595/99.6875 |126976 |
|numeric timing variation |404 |13/14.9453 |36/38.1458 |16/17.6823 |not independently recomputed; use full-source rows |not claimed |
|sample names uniform |728 |12/12.4661 |36/36.0208 |14/15.6979 |1469/91.8125 |126976 |
|max names uniform |1370 |12/12.1458 |36/35.5938 |14/15.2031 |1193/74.5625 |131072 |
|sample names timing variation |728 |13/14.8568 |36/38.0521 |15/17.5052 |1281/80.0625 |131072 |
|max names timing variation |1370 |13/14.5260 |36/37.7500 |15/17.2760 |1056/66 |135168 |

Conservative reporting: numeric body median13 B, HOT median36 B, WARM
median15–16 B (use16 for a typical-entry planning comparison), **plus shared
728–1370 B context and sector padding**. These are experimental trace sizes,
not production-qualified record sizes. Full fallback maxima remain raw101,
HOT124, WARM103 B; no median-based worst-case capacity claim. More frequent
restarts can reduce per-entry deltas while increasing total header cost; a
smaller mean in the maximum-name case does not mean better retention.

Headline the full-source timing-variation result, including the maximum-name
case:72h NORMAL is CONDITIONAL, sample has zero spare and maximum has4096 B
deficit. No72-hour production guarantee or partition change is approved.
Existing fixed100 KiB reservation, allocator peaks, source dictionary/config
recovery, authenticated root/nonce/reclaim proof, retirement progress, backend
daily/effect/substitution, coverage/time/late policy, rollback and target
RAM/wear remain OPEN.
