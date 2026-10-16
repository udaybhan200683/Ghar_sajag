# R1 256 KiB / NORMAL 48-hour workspace qualification — 2026-10-09

**QUALIFICATION_RESULT=FAIL_CAPACITY**, specifically for the frozen retained
object map and the existing protected certificate. **Production readiness: NO.**
4 MiB /256 KiB cannot qualify this tested configuration without further changes.
This is not a universal lower bound for every possible future representation.
No new codec, reclamation engine, production firmware or partition change.

Start `92e4e1c926b11cb4e17c1afb0c6fad1fec17501e`, storage branch, context
`2026-10-08.002`, preflight PASS. User-owned `prompt.txt` never read/changed/staged;
canonical untouched. GS-D025–029, LOCKED 72-hour design target, BAT-C8 and signed
FOTA/application rollback remain unchanged. `-Os` remains an unpromoted candidate.

```text
BUG_CLASSIFICATION=INVESTIGATE_ONLY
REQUIREMENT_SOURCE=docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D025,GS-D026,GS-D029
TASK_SCOPE=existing NORMAL48h retained-map / real SDK workspace counterexample
OUT_OF_SCOPE=production integration, new history format, partitions, HIGH/72h comparisons
```

## Executable boundary

Added only a `workspace48` mode to the existing Linux SDK probe. It reconstructs
the **unchanged** maximum-size NORMAL mixed /48h vector from the committed
[feasibility log](R1_4MIB_48H_STORAGE_FEASIBILITY_20261008.log), SHA256
`1f9da309e5099f87a8197f1294c3021994d771d075966bb926dfaa7041a5d9fa`:
89 objects, 213,646 logical bytes, 23 history extents, eight COW/source staging
extents, existing control/daily/credit budgets and 32 HOT tails. No workload
generator, HIGH case, 72-hour simulation or capacity matrix rerun.

The same **real** `compact_sdk::Store::prepare_publication` reads fully erased
pages and rejects effect-free. An optimistic unchanged-reducer plan needs at
least 15 certified pages: at least two page activations each for event, bank and
head; eight for protected control; one for NVS. The one-row control bound is
4,010 B. The test uses the lowest bank activation class, not an invented smaller
codec. Larger actual manifests or a changed reducer can only increase the bound.
The 384-row maximal operation requires 25 certified pages; its protected
control/internal workspace is 12 pages /49,152 B. One possible lazy active page
is excluded from certification. No free-entry or nominal-byte admission promise.

The four unselected temporary metadata objects are the **same favorable
discharge assumption as the prior size fixture**, not proof of an authenticated
history selection protocol. All other 85 objects stay pinned. This includes all
history, staging, HOT, ownership/credit, reducer/coverage/day and critical-placeholder
objects. We deliberately do not release staging or witnesses on guessed semantic
completion and do not synthesize backend acknowledgments. Even the favorable
temporary deletion cannot restore enough workspace.

## Physical SDK measurements

ESP-IDF 6.0.3, source `76f5dedd9950a3012fee8fb7d5586df21fc67802`; existing flash
emulator and copied 256 KiB descriptor. This is a host SDK test, not a physical
Hub layout or hardware result.

| Phase | Nonblank pages /bytes | Erased pages | Live entries /entry bytes | Deleted entries | Certified pages | Minimum next admission |
|---|---:|---:|---:|---:|---:|---|
| Frozen load |56 /229,376|8|6,913 /221,216|0|7|REJECT, needs15 |
| Four temporaries removed |56 /229,376|8|6,569 /210,208|344|7|REJECT, needs15 |
| SDK purge of deleted metadata |56 /229,376|8|6,569 /210,208|344|7|REJECT, needs15 |
| Remount/restart |56 /229,376|8|6,569 /210,208|344|7|REJECT, needs15 |

Removal writes 116 bytes; purge writes another 11,008 bytes. **Neither performs
a sector erase nor restores any erased page.** Installed SDK `nvs_purge_all`
calls `Page::purgeEntryRange`, programming zeros into deleted data. It is not
compaction and is not recommended as a production workspace fix. The SDK page
manager's allocation-triggered GC normally runs at the last-free-page boundary;
ordinary protected publication intentionally refuses to reach that condition.
No private GC method, direct sector erase, reset or unbounded scratch-write loop
was introduced.

Actual certified workspace is **28,672 B**, versus **61,440 B** for the most
optimistic next ordinary operation: eight pages /32,768 B short today. Removing
all four temporaries still leaves 6,569 live entries. At 126 entries/page, even
perfect repacking requires at least **53 live pages**. Thus:

```text
53 live +15 certified next-operation +1 possible lazy page =69 pages
69*4096 =282,624 B; current partition262,144 B
Ideal-packed lower deficit =5 pages =20,480 B
Actual un-repacked minimum =56+15+1 =72 pages =294,912 B
```

At the 384-row maximum certificate, the analogous ideal-packed bound is 79 pages
/323,584 B, and current un-repacked coexistence is 82 pages /335,872 B. These
are certificate/map arithmetic, **not qualification of a larger partition**.
No scalar free-byte estimate or deletion of required evidence can close this
existing-map deficit. Source/COW dependencies might be discharged only through
a validated selected representation; that bridge is not implemented and cannot
be assumed to make this test pass.

## Focused validation and limitations

- New workspace test: **five cases PASS as negative proofs**, including no-cut,
  cuts0/1/8 and completed child reclaim. Each rejects the lower and maximal
  admission plans before writes, with three bounded retries at each phase.
  No event is newly admitted after loading; repeated forward progress **FAILS**.
- On injected failure the child immediately `_exit(77)`s; no cleanup or later
  writes continue on the failed device. All 85 pinned blobs byte-verify after
  interruption and restart. The test has no cloud receipt/backfill operation.
- Five existing **authenticated subset** checks at 256 KiB PASS: typed I/O/slot
  refusal, collection cuts1/2, publication cut1360 and no-cut publication.
  These preserve selected state/credits, durable publication and lost-ACK retry
  identity. They are small native transactions, **not an authenticated 48h run**.
  Collection uses its existing independently completed dependency fixture;
  that completion is not credited to the internet-outage history test.
- Native Gate A/B and compact host regressions PASS in their documented report/
  authority scope. The provider-free host summary retains `gate_C=OPEN`.
- ASan/UBSan: five new workspace cases PASS. Probe/adapter, native transaction and
  compact codec instrumented; SDK/OpenSSL archives uninstrumented, LeakSanitizer
  disabled. Final SDK executable hash matches the recorded tests. Build PASS.
- The retained size objects are opaque dummy values. Their exact byte preservation
  complements the previous semantic-model evidence; it does not establish full
  physical routine learning, clock/coverage or a new backend protocol. The compact
  384-row transaction still has no authenticated transfer to 492 exact bodies plus
  131 history summaries representing 784 retained observations (768 source plus
  16 local outcomes). Critical-placeholder size and saturation policy remain OPEN.
- There is no new production heap/stack/flash allocation. New test metadata is
  bounded (89 sizes, three/four plan lengths, existing 4 KiB certificate buffer,
  at most one 6,144-byte verify buffer); no growing retry list/loop. Physical
  six-Node heap/stack, ACK/recovery latency, encrypted flash/power-cut/endurance,
  signed update/storage compatibility and BAT-C8 qualification remain pending.

The raw log's `EXIT=0` / `COUNTEREXAMPLE_PASS` means the asserted refusal and
preservation behavior passed. It does **not** turn the qualification into PASS.
No existing assertion was weakened. No corrective lifecycle change is made:
the guard is acting correctly, while safe reserve restoration and the selected
history mapping remain missing contracts/engineering work.

## Stop and commercial next action

Additional journal capacity is the simpler way to let this retained map coexist
with the conservative guard, rather than weakening it or introducing a new
compression/allocator design in this task. Larger blank capacity still does not
prove sustainable reclamation or the LOCKED 72-hour supported-volume guarantee.

For 4 MiB, keeping both OTA slots at least 1,900,544 B leaves at most 256 KiB
for this journal. More journal forces a limiting slot down to 1,835,008 B or
below, leaving **45,552 B** against the measured 1,789,456-byte `-Os` candidate.
That tight margin excludes unmeasured integration growth and is not qualified.
No partition, hardware or commercial guarantee is selected here.

**NEXT_ACTION:** resolve the journal/OTA capacity envelope with the product owner;
evaluate additional flash capacity as the simpler option before production
integration. Reuse existing larger-flash evidence; no new MCU, hardware purchase,
capacity matrix, or implementation begins automatically. Keep 48h as a test
envelope and 72h LOCKED. Pricing and physical qualification remain separate.

Reproduction and exact outputs: [focused log](R1_256K_48H_WORKSPACE_QUALIFICATION_20261009.log).
Only host probe/test code, this evidence and a short ExecPlan entry are changed.
No push, canonical/context/requirement changes, Node/BAT-C8/backend/Jira work.
