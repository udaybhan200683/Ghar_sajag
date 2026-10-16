# NVS runtime/saturation checkpoint — 2026-10-08

Preflight PASS at context `2026-10-07.003`, clean starting HEAD `a3e9da9` on
`feature/r1-hub-storage-lifecycle`. This is host-only technical evidence. The
frozen codec, production firmware, partition CSV, BAT-C8 and hardware are
unchanged. ESP-IDF 6.0.3 installed source commit
`76f5dedd9950a3012fee8fb7d5586df21fc67802` supplies actual NVS and its
Linux emulated flash driver. The isolated probe is
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/`.

## Result

**FINAL PRE-PRODUCTION PROOF: NO.** NVS remains the preferred *candidate* and
raw flash remains fallback only. The prior 9-segment fresh image is physically
packable. It is not a safe runtime capacity guarantee: churn uses the three
pages previously labelled application COW/engineering reserve, a 12-segment
live condition blocks retirement-report replacement, and the full 192
maximum-HOT flight cannot be committed as standalone blobs alongside 192
remaining witnesses. One injected report-blob replacement cut remounts with
`ret0` absent. A selected report therefore needs an independently authenticated
old bank and root protocol; in-place NVS key replacement is insufficient.
These observations do not prove that the partition must grow. A bounded
tail/segment schedule, earlier lawful owner release, admission cap, or different
placement may fit, but none has an end-to-end proof or approved saturation
policy. NVS's tested 10,000-cycle progress is conditional on its specific
live set and does not prove progress for every permitted state.

## Workload and physical measurement

The probe writes six 4,079-byte witness blocks, three 3,485-byte report banks,
three 6,144-byte state/checkpoint banks, two 512-byte roots, two 4,096-byte
metadata values, two 4,096-byte critical placeholders and 7/8/9 4,096-byte
sealed segments. These are the prior length-matched candidate objects, not
actual serializers or product-approved retention. A churn cycle writes a
124-byte HOT tail, replaces one 4,096-byte segment, deletes the tail, then
replaces one report, state, metadata and root value. This is an intentionally
heavy *sensitivity* cycle, not a measured NORMAL/HIGH/STRESS event schedule.
It does use the real ESP-IDF NVS allocator, blob chunking, page compaction,
replacement, and Linux flash write/erase counters.

| Initial sealed segments | Fresh nonblank pages / live entries | After 1,000 cycles | 32 maximum HOT tails then segment replacement |
|---|---:|---:|---|
| 7 | 26 / 3,185 | 31 nonblank + 1 erased; 3,186 live entries | PASS in this fixture |
| 8 | 27 / 3,316 | 31 + 1; 3,319 live | PASS in this fixture |
| 9 | 28 / 3,447 | 31 + 1; 3,450 live | PASS; peak 3,643 live entries |

At 9 segments, 10,000 cycles completed. Final counters: 31 nonblank pages,
one erased page, 3,450 live entries, 297,789,032 bytes programmed since a
112,616-byte fresh setup, 69,755 page erases, and maximum 2,961 erases on one
sector (some fixed-data sectors remained at zero). NVS `PageManager::requestNewPage`
requires a free page, activates it during GC, copies the victim's live entries,
and erases the victim. Thus the application sees one erased page at stable
boundaries, while all 32 physical pages can be occupied transiently during GC.
The previously assumed two application COW pages plus one engineering page are
not reserved by NVS: **12,288 bytes of that candidate reserve are consumed at
steady churn**. Even when `nvs_get_stats` reports hundreds of free entries,
those are not a guaranteed contiguous blob-replacement reserve.

After 1,000 cycles with nine segments, adding segments 9, 10 and 11 succeeds;
adding segment 12 returns `ESP_ERR_NVS_NOT_ENOUGH_SPACE`. At 12 live segments,
3,844 live entries remain (123,008 entry bytes), one erased page remains, and
**replacing report bank `ret0` fails with the same error**. Directly deleting
old segment `seg0` and retrying an append succeeds. At 11 segments, a report
and root replacement succeed in this run (3,713 live entries, 118,816 entry
bytes), but this is no universal safe threshold. A system that needs a new
complete report to release exact evidence cannot assume that NVS has saved
space for that operation. Normal admission needs an enforced physical guard
before it consumes report/root/GC workspace.

For a separate maximum-HOT coexistence witness, the probe deletes three
64-key witness blocks (192 certificates) before committing 192 separate
124-byte HOT blobs, leaving 192 exact certificates and all other objects.
With nine initial segments, NVS accepts 138 HOT blobs and rejects the next
with `ESP_ERR_NVS_NOT_ENOUGH_SPACE`; no sealed promotion can begin from that
state. Seven/eight-segment fixtures accept 182/158. This is a counterexample
to treating the 384-key bound as a 192-full-body guarantee for standalone
NVS tails. It does not rule out staged promotion or lower admission with
protected space. The source-proven Node pending bound remains 192; Hub credit
and body admission remain conditional, with ACK refusal required on failure.

## Fault and durability boundary

At nine segments after 50 churn cycles, the probe replaces `ret0` while the
Linux flash emulator cuts writes/erases after selected operation counts,
deinitializes NVS, remounts, and reads the key. Tested cuts:
`0, 64, 128, 256, 512, 768, 1024, 1071, 1072, 1073, 1080, 1081, 2048`.
Cuts through 1071 recover the old 3,485-byte value; 1073/1080 report
`ESP_ERR_NVS_REMOVE_FAILED` yet recover the new value; 1081/2048 succeed and
recover new. At **cut 1072**, `nvs_set_blob` returns `ESP_ERR_FLASH_OP_FAIL`,
NVS remount succeeds, and `nvs_get_blob(ret0)` returns `ESP_ERR_NVS_NOT_FOUND`.
This is reproducible three times with this installed emulator and workload.
The test models one key only; it neither establishes a general SDK defect on
hardware nor proves a whole authenticated report/root transaction. It does
show why a selected bank must never be updated in place and why report/root
selection, old-bank retention, recovery and fault cuts need application proof.
No Node/Hub credit state is persisted by the existing host admission model;
it uses copied atomic ledger snapshots. The conditional `6*(32+32)=384`
induction is therefore **not** an end-to-end reboot/lost-report/replay proof.
The candidate class bitmap is 48 bytes for 384 rows, but authenticated slot
association, owner/report generation, root and recovery overhead are not sized.
Three 3,485-byte report banks are 10,455 logical bytes and at least 10,656 NVS
entry bytes before page/GC overhead.

## Write, wear and RAM boundary

The 10,000 heavy churn cycles program 29,767.64 bytes and erase 6.9755 pages
per cycle on average after setup. Nominal changed-value payload is 18,457
bytes/cycle, so measured **programmed-byte/payload ratio is 1.613** for this
specific all-owner replacement cycle; it is not final application write
amplification. Applying that *rejected* per-event schedule to the earlier
synthetic NORMAL/HIGH/STRESS rates (384/1,776/23,232 events/day) would imply
about 2,679/12,388/162,055 NVS page erases per day, respectively. These are
exposure calculations, not observed daily workloads or flash-life claims.
One 32-HOT promotion run adds 17,988 programmed bytes for
3,968 HOT bytes plus a 4,096-byte segment replacement (2.23 ratio, excluding
other owners). The per-event all-owner replacement schedule would produce
unacceptable erase rates at the synthetic NORMAL/HIGH/STRESS event rates;
it is rejected as a production schedule. Actual checkpoint/report cadence,
full owner release, hot-sector distribution, flash endurance and NORMAL/HIGH/
STRESS amplification have not been specified or measured. No lifetime claim
is made.

The prior raw-sector engine candidate was 39,017 bytes including stack; the
current admission fixture itself uses 37,384 host bytes. Neither is an NVS
target engine measurement. NVS metadata, network/crypto/task peaks, stack and
new firmware growth remain unmeasured. Existing Hub app 1,864,624 bytes and
101,456-byte OTA margin are preserved prior-build facts, not integration fit.

## Decision boundary and next work

`CURRENT_128K_FEASIBILITY=CONDITIONAL` for R1 overall, and **FAIL** for the
unrestricted nine-segment mapping with protected report/COW reserve assumed
by the fresh-image ledger. `PARTITION_CHANGE_REQUIRED=UNPROVEN`; the reserve
deficit is at least 12,288 bytes for *that mapping*, not a justified new
partition minimum. `CURRENT_4MB_HUB_STORAGE_VIABLE=CONDITIONAL`;
`CURRENT_4MB_HUB_OTA_VIABLE=YES_FOR_EXISTING_IMAGE_ONLY`;
`HARDWARE_UPGRADE_REQUIRED_FOR_R1=NO_EVIDENCE`.

Technical closure needs authenticated persisted report/credit/class/root
selection across crash and replay, a physical admission guard protecting
report/GC/COW and 192-body peak, a bounded NVS operation schedule with
NORMAL/HIGH/STRESS wear, an NVS-specific target RAM budget and rollback proof.
Product decisions still required: critical class/C and Node reserve alignment,
full-detail/offline horizon, saturation effect/alert behavior, and backend
derived-effect/revision/substitution semantics. No unlimited unsynced stream
can fit a finite partition. No production implementation or partition change
is authorized by this evidence.

Raw outputs: [10,000-cycle/saturation](R1_STORAGE_NVS_RUNTIME_CHURN_20261008.log),
[7-segment run](R1_STORAGE_NVS_RUNTIME_7SEG_20261008.log),
[8-segment run](R1_STORAGE_NVS_RUNTIME_8SEG_20261008.log),
[7-segment full-HOT attempt](R1_STORAGE_NVS_RUNTIME_7SEG_192HOT_20261008.log),
[8-segment full-HOT attempt](R1_STORAGE_NVS_RUNTIME_8SEG_192HOT_20261008.log),
[11-segment report progress](R1_STORAGE_NVS_RUNTIME_REPORT_PROGRESS_20261008.log),
[32 HOT promotion](R1_STORAGE_NVS_RUNTIME_32HOT_20261008.log),
[192 HOT attempt](R1_STORAGE_NVS_RUNTIME_192HOT_20261008.log), and
[selected flash cuts](R1_STORAGE_NVS_RUNTIME_FAULT_20261008.log).

## Root-cause correction — 2026-10-08

The [focused follow-up](R1_STORAGE_NVS_BLOCKER_DIAGNOSIS_20261008.md) supersedes
only the inference that cut1072 demonstrates single-key power-loss recovery
insufficiency. The original failure/logs remain accurate for a one-shot I/O
error: the emulator resumes writes after failing the index bitmap write, NVS
cleanup erases a new chunk, and recovery discards both indexes. A power-off
latch prevents those cleanup writes and recovers complete generation127 at the
same cut. Classification: FAULT_INJECTION_MODEL_DEFECT.2702 focused corrected
cut/selection/remount checks pass. Independent selected/old authority is still
required for the application multi-key/ambiguous-error transaction; this is not
a whole authenticated NVS credit/root proof.

Capacity failures remain real. Nine segments+192 maximum HOT+next report/state/
roots need a modeled155648 B and pass the tested152 KiB fixture, while128 KiB
passes a three-segment version. Neither is a product capacity guarantee.
Connected32-event checkpoint sensitivities produce90/461/6089 erases at the
three engineering rates; full production wear/RAM/admission remain UNPROVEN.
Original297789032 write counter includes112616 setup bytes; post-setup traffic
is297676416, preserving rounded ratio1.613. Keep both3844 (1000-cycle) and3848
(10000-cycle)12-segment observations. No evidence is overwritten or hardware/
partition/backend/production integration decision made.
