# 128 KiB NORMAL/HIGH 12h–24h capacity — 2026-10-09

**All four unchanged maximum-size mixed fixtures: FAIL_CAPACITY.** No complete
12h/24h protected offline duration is demonstrated. **RECOMMENDATION=
EVALUATE_8MB_CLASSIC_ESP32** as the previously identified candidate, not approval
or purchase. Shortening the horizon alone does not remove fixed recovery/COW
costs. No additional shorter tests, storage redesign or implementation follows.

Start `394050ddfea8ff1d1286ab8c1fac8064f95e33de`, expected storage branch,
context2026-10-08.002, preflight PASS; only protected `prompt.txt` initially.
It was not accessed; canonical and other worktrees untouched. GS-D025–029,
72-hour design target, event/security/Node/BAT-C8/FOTA contracts unchanged.
48h/72h, historical fuzzing/SDK matrices and optimization builds were not rerun.

## Actual shorter traces; no volume rescaling

Existing `offline_72h_model.py` mixed rules at NORMAL384/HIGH1776 semantic
sources/day, deterministic noon-start timeline. Select source timestamps before
noon+12h/24h and reapply the existing final-source anchor for each of six Nodes.
Local outcomes retain their original3h schedule; native MotionSummary keeps its
exact body. Existing one-hour loss-aware point grammar, max103-byte exact fallback,
ownership/context/clock/coverage and consumer-checkpoint eligibility unchanged.
No raw PIR pulses, invented lower rate or new event format. These engineering
workloads are not measured or approved household bounds.

Preserve the full fixed20-object budget63,857 B (all384 witness slots, six owners,
report/checkpoint/root/lifecycle and four320-byte daily slots), eight4096-byte
source/COW extents, four progress objects10,653 B,32 HOT tails and8,192 B critical
placeholder. That placeholder is not an approved critical reserve. No favorable
overlap, extra cloud receipt or staging release. 12h intersects one modeled date,
24h two, but all four daily slots stay charged. The previous36h origin change is
outside these windows; we do not move it earlier to manufacture reboot traffic.
Internet outage only; backend ACK count zero and every observation stays pending.

| Test | Duration/workload | Source +local observations | Exact /important subset | Native summaries within exact | Eligible ordinary points /history summaries | Event payload B | All logical objects B |
|---|---|---:|---:|---:|---:|---:|---:|
|T1|12h NORMAL|192+4|102 /48|55|94 /41|12,828|139,918|
|T2|24h NORMAL|384+8|247 /152|110|145 /65|29,086|168,590|
|T3|12h HIGH|888+4|459 /195|265|433 /63|53,442|205,454|
|T4|24h HIGH|1776+8|1099 /635|527|685 /98|122,890|316,046|

Remaining exact motion counts16/74/65/321 preserve important/unavailable/delayed
context or last-activity anchors; they are not automatically safe to aggregate.
The ordinary points above are separate observations, not continuous presence.
All source EventKeys appear exactly once across exact bodies and summaries;
all required important and native-summary keys remain exact in the semantic model.
Current routine/learning coverage budgets persist; no silence-to-inactivity inference.
Complete personalized/longitudinal learning and authenticated history serialization
remain future/unqualified implementation; allocating a budget doesn't implement them.

## Capacity and physical protected workspace

Required NVS bytes below are the **unchanged ledger's modeled physical peak**, not
a successful complete SDK measurement. It charges entry/page overhead plus its
own GC/engineering allowance. Do not add the separate compact certificate and
claim an integrated storage format. Actual SDK pressure is measured below.

| Test | Duration | Workload | Required NVS B (modeled); deficit vs131,072 | Protected next-operation certificate | Available certified workspace after SDK stop/restart | Result |
|---|---|---|---:|---:|---:|---|
|T1|12h|NORMAL|159,744;28,672 short|≥61,440 B /15 pages|0 B|FAIL_CAPACITY|
|T2|24h|NORMAL|188,416;57,344 short|≥61,440 B /15 pages|0 B|FAIL_CAPACITY|
|T3|12h|HIGH|225,280;94,208 short|≥61,440 B /15 pages|0 B|FAIL_CAPACITY|
|T4|24h|HIGH|339,968;208,896 short|≥61,440 B /15 pages|0 B|FAIL_CAPACITY|

Logical vectors alone exceed the partition by8,846/37,518/74,382/184,974 B,
before NVS overhead. Actual minima/margins cannot be inferred by dividing48h costs.
Even successful exact-source retirement would not discharge cloud-pending history.

Four new ESP-IDF6.0.3 Linux-emulator cases, current128KiB descriptor32pages,
unchanged SDK/native libraries. A small **temporary** diagnostic callback in copied
probe source verifies the retained prefix after load failure, remounts SDK NVS,
then invokes the real `compact_sdk::Store::prepare_publication`. It uses the same
optimistic15-page plan as the prior workspace counterexample; three requests
must return `InsufficientProtectedSpace` with zero new write/erase and no ACK
eligibility. No representation/codec/provider algorithm changed. Only evidence
is committed; the copied source, object/executable and fixtures remain in `/tmp`.

All cases stop at **zero-based object34**, attempting4096 B; committed objects0–33
hold121,201 logical B. Different tails have the same saturated prefix in the existing
object order. SDK returns `ESP_ERR_NVS_NOT_ENOUGH_SPACE`, process **EXIT=2**.
This is expected capacity failure, **not PASS** and not an injected power cut.
Before exit, all committed objects byte-verify before AND after restart.

Actual identical measurements for each failed prefix:

- Peak32 nonblank pages /131,072 B, peak4,006 live entries; final/restarted
  **31 occupied pages /126,976 B**,3,889 live entries /124,448 entry B,
  zero deleted entries and one wholly erased page /4,096 B.
- NVS entry overhead over committed logical prefix is3,247 B; page allocation
  slack/headers are separate. SDK stats_free143 entries are not erased workspace.
- One possible lazy active page is excluded: **zero certified pages**, deficit
  at least15 pages /61,440 B for that plan. Max384-row plan still needs25 certified
  pages /102,400 B; control/internal part36,864–49,152 B is not a critical reserve.
- Failed-load path performs3 GC sector erases, maximum2/sector; programmed139,584 B.
  Restart and three protected refusals do not change write/erase counts or retained
  prefix. No fully reclaimable occupied page is established; pinned prefixes have
  no cloud discharge and zero deleted entries. No purge/reclamation is attempted.

**EARLIEST_ADMISSION_FAILURE_TIME=NOT_ESTABLISHED.** Loading orders metadata/history/
COW objects rather than chronological events; object34 cannot be mapped to an
elapsed outage hour. This unguarded size fixture is a capacity probe, not the
authenticated event admission path. Its failed writes never issue radio ACKs.
The post-restart protected refusal is a real zero-write boundary, but cannot
retroactively turn the original load into protected admissions.

## Recovery scope, resource limits and commercial implication

Semantic identity preservation PASS; failed-prefix SDK readback/restart PASS;
guard rejection/no-false-ACK eligibility PASS in tested scope. **Complete event,
owner/credit, routine-root recovery and duplicate EventKey handling for these
four histories are NOT QUALIFIED**, because complete history never loads and
the fixture uses opaque length-matched bytes. Existing authenticated Gate C
duplicate/lost-ACK, corruption and hard-stop interruption tests remain supporting
evidence in their smaller scope, not a substitute for these missing full runs.
No new workload interruption test is performed after a failed complete load;
there is no legal complete-history next operation to interrupt. No failures
are suppressed. Subsequent Node retry/32-record queue pressure is unqualified.

SDK NVS estimate~2.75KiB for128KiB partition plus~5.5KiB/1000keys is not measured
target heap. Diagnostic buffers are bounded: existing4KiB certificate buffer,
one verify/put vector up to6,144 B and bounded object-size vectors (71/78/87/114
objects); the Python runner holds the original finite trace. Peak host allocation
was not measured. There is no added production buffering or flash/RAM cost.
The80KiB owner-stack concern, six-Node peak heap/stack, encrypted-target physical
power cuts/wear, signed FOTA/application rollback and storage-format compatibility,
production integration and BAT-C8 qualification remain pending.

**MAX_DEMONSTRATED_OFFLINE_DURATION=NONE** for these four complete protected
envelopes. This does not mean the deployed device stores zero events or prove
a universal minimum for every possible representation. It means128KiB doesn't
qualify even the tested NORMAL12h maximum-size map, so neither12h nor24h can be
advertised from this experiment. Do not silently lower the LOCKED72-hour target.

The user-provided existing DevKit-V1 cost₹395 is retained as a prototype input,
not a new supplier quote. Current two1,966,080-byte OTA slots leave176,624 B for
the1,789,456-byte `-Os` candidate; compiler/partition settings unchanged. Additional
flash doesn't add CPU speed or internal RAM. Reuse the [final4/8MiB comparison](R1_FINAL_4MIB_8MIB_FLASH_DECISION_20261009.md):
256KiB increases room but has no qualified protected mixed24h run, still fails
NORMAL48h workspace, and does not solve the LOCKED72h/HIGH capacity direction.
**Evaluate8MiB classic ESP32**, retaining NVS rather than starting another codec/
journal optimization. Exact landed board cost/compatibility and hardware approval
remain prerequisites; no purchase or further scenario is started.

**NEXT_ACTION:** resolve the existing8MiB candidate's compatible landed BOM and
seek explicit hardware-direction approval before NVS lifecycle/integration work.
Do not revise72h governance based on a shorter guarantee that has not passed.

Reproduction, fixture/hash/counts, SDK output and temporary instrumentation:
[measurement log](R1_128K_12H_24H_STORAGE_FEASIBILITY_20261009.log).
Four capacity failures with successful prefix-recovery/refusal assertions;
evidence consistency/preflight/whitespace PASS. Production, partitions, Node,
BAT-C8, requirements/context/canonical remain unchanged. No push.
