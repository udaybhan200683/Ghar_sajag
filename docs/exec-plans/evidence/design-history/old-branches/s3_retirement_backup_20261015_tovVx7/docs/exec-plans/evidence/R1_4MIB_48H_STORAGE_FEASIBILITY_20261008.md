# R1 4 MiB / 48-hour storage feasibility — 2026-10-08

**RECOMMENDATION=INSUFFICIENT_EVIDENCE** for a commercial retention guarantee.
Keep the existing 4 MiB baseline. NORMAL mixed / 48 hours is a **256 KiB
byte-fit candidate** worth the previously defined bounded workspace-restoration
proof. It is not a protected, sustainable, production-qualified configuration.
HIGH maximum-size traffic fails at both durations. No hardware purchase or
requirement/partition change follows from this experiment; GS-D025's 72-hour
design target remains LOCKED.

Preflight PASS at context `2026-10-08.002`, branch
`feature/r1-hub-storage-lifecycle`, start
`e548fedb7ecf59a4e2d0b201a3100c07eb6b35df`. Only untracked `prompt.txt` initially;
never read/changed/staged. Canonical remains unchanged. No production, Node,
BAT-C8, firmware optimization, codec, reclamation or governance implementation.

## Inputs and comparison

Reuse unchanged `host/storage/offline_72h_model.py`: six interleaved Nodes,
NORMAL 384 and HIGH 1,776 semantic source records/day, mixed profile, existing
kind/safety/routine exclusions, native MotionSummary and clock/delay treatment.
These are existing engineering fixtures, not measured or approved volume bounds.
No raw-PIR pulse assumption or speculative Node event reduction.

48 hours is a strict prefix of the existing noon-start 72-hour trace, with the
same six final-source anchors reapplied using the generator's existing rule.
Do not scale fixed storage by 2/3: all 384 witness slots, report/checkpoint/owner
metadata, four daily-state slots, 128-input staging, 32 HOT tails and the existing
32-event **unapproved** critical placeholder remain charged. Existing one-hour
loss-aware containers preserve individual eligible motion points; no new codec.
48 hours includes three local dates, 72 includes four; retaining all four slots
is conservative. The existing 36-hour origin change remains in both traces.

Backend acknowledgments are **zero** throughout the retention calculation and
SDK checks. Every generated source remains represented in exact bodies or an
immutable proposed summary. Neither backend completion nor Node retirement is
used to remove pending history. Initial pre-outage backlog/ambiguous submissions
are not added by these existing fresh fixtures; they can only worsen a guarantee.

`REQUIRED_STORAGE` below is the existing **maximum-size whole-object modeled
physical peak**, including entry/page tax, staging/COW/progress/critical allowances,
one GC page and one engineering page. It is not plain event payload.
`USABLE_CAPACITY` is only the geometric NVS entry upper bound after page metadata
and one GC page: `(pages-1)*126*32`. Blob indexes/chunk overhead and application
metadata consume that budget; fragmented free entries are not certified workspace.
There is no universal usable-payload constant. Compare modeled peak with the
physical journal size, rather than comparing these different byte categories.

| Configuration | Hours | Workload | Journal B | Required storage B | Usable entry bound B | Protected control workspace B | `-Os` OTA margin B | Capacity result / reason |
|---|---:|---|---:|---:|---:|---:|---:|---|
| A |72|NORMAL mixed|131,072|282,624|≤124,992|36,864–49,152|176,624|FAIL: prior SDK load failure; modeled shortfall 151,552 B |
| A |72|HIGH mixed|131,072|745,472|≤124,992|36,864–49,152|176,624|FAIL: prior SDK load failure; modeled shortfall 614,400 B |
| B |48|NORMAL mixed|131,072|233,472|≤124,992|36,864–49,152|176,624|FAIL: new SDK load failure; modeled shortfall 102,400 B |
| B |48|HIGH mixed|131,072|544,768|≤124,992|36,864–49,152|176,624|FAIL: new SDK load failure; modeled shortfall 413,696 B |
| C |72|NORMAL mixed|262,144|282,624|≤254,016|36,864–49,152|111,088|FAIL: prior SDK load failure; modeled shortfall 20,480 B |
| C |72|HIGH mixed|262,144|745,472|≤254,016|36,864–49,152|111,088|FAIL: prior SDK load failure; modeled shortfall 483,328 B |
| D |48|NORMAL mixed|262,144|233,472|≤254,016|36,864–49,152|111,088|UNQUALIFIED: SDK byte-fit PASS; protected workspace/progress not established |
| D |48|HIGH mixed|262,144|544,768|≤254,016|36,864–49,152|111,088|FAIL: new SDK load failure; modeled shortfall 282,624 B |

The workspace column is the **separate compact Gate C certificate**, not a new
amount added to the older peak ledger. At the 384-row control maximum it is
49,152 B; the full worst next-operation certificate can require 25 erased pages
(102,400 B), with the possible lazy active page additionally excluded. The two
representations are not yet integrated; adding/subtracting these budgets would
not prove a combined format.

Sensitivity only: the old 16-byte typical-exact assumption gives NORMAL peaks
147,456/139,264 B at 72/48 hours and HIGH 225,280/188,416 B. Those are planning
inputs, not actual maximum sizes. Favorable typical or mostly-ordinary passes
cannot qualify the maximum mixed fixture or a whole-household guarantee.

## Retained information and actual SDK pressure

| Workload / duration | Source + local outcomes | Exact bodies | Important subset | Native summaries, within exact | New history summaries | Event payload B | All logical objects B | Modeled live entry B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NORMAL /72 h |1,152 +24|728|433|338|197|86,108|258,702|267,168|
| NORMAL /48 h |768 +16|492|295|226|131|58,020|213,646|221,056|
| HIGH /72 h |5,328 +24|3,278|1,921|1,538|298|367,028|705,166|724,096|
| HIGH /48 h |3,552 +16|2,197|1,290|1,030|199|245,794|512,654|527,072|

The 384 unretired identity bound is distinct from the totals above. Semantic
checks preserve all source keys exactly once, exact important doors/user/safety
events and native MotionSummary bodies. Summary points retain occurrence times,
monotonic provenance and gaps; they do not assert continuous presence. Existing
coverage/reducer/day budgets remain, with NO_OBSERVATION distinct from NO_ACTIVITY.
Complete authenticated history/longitudinal-state serialization remains unqualified.

Run only **four new SDK cases**, maximum-size mixed NORMAL/HIGH at 48 hours on
32/64 pages. Reuse prior 72-hour results, with regenerated fixture hashes matching
their original logs exactly. Installed ESP-IDF 6.0.3 NVS / existing flash emulator;
unchanged executable, dummy length-matched bodies, no physical Hub result.

- Three expected stops return `ESP_ERR_NVS_NOT_ENOUGH_SPACE` during load.
  128 KiB stops at object 34; HIGH /256 KiB stops at object 64. These are capacity
  counterexamples, not completed monitoring runs or authenticated admissions.
- NORMAL /256 KiB loads all 89 objects: **56 nonblank pages, eight erased pages,
  6,913 live entries =221,216 entry B**, zero GC erases initially. Actual entry
  overhead slightly exceeds the ledger estimate; logical objects total 213,646 B.
- Its 32 metadata update cycles and remount byte-verification PASS while retaining
  every history object. **Peak 63 pages =258,048 B**, 76 GC erases, maximum eight
  erases/sector; final 6,569 live and 1,236 deleted entries, only **one erased page**.
  Removed objects are superseded candidate/temporary metadata, not cloud-pending
  history. No backfill, cloud receipt or cloud-dependent history reclaim runs.
- Eight raw erased pages after loading are already below the separate compact
  certificate's tested nine-page control workspace. Excluding the possible lazy
  page would leave seven, a two-page (8,192 B) deficit for that tested control budget, or five
  pages (20,480 B) for the 384-row control bound. After churn the certificate has
  no such clean workspace. This is a warning against combining the formats,
  **not** a test of an authenticated integrated history adapter.

## Boundary and next action

`48H_256K_FEASIBLE=BYTE_FIT_NORMAL_ONLY; protected commercial guarantee UNQUALIFIED`.
`72H_256K_FEASIBLE=FAIL maximum mixed NORMAL/HIGH fixtures`.
Important-event preservation is asserted in the semantic model and retained
dummy blobs; actual protected history/outbox integration is still missing.
Sustainable reclamation is unqualified and cloud-dependent reclamation is
unavailable during either outage. Compact Gate C still safely rejects before
writes/ACKs, preserves selected dependencies and uses bounded attempts; saturation
does not guarantee that the next important event will fit. Critical reserve and
full-storage product behavior are OPEN, not replaced by the dummy placeholder.

**Stop point:** existing fixtures do not provide a closed-loop, authenticated
48-hour compact NVS history/outbox run with protected workspace restoration.
The compact candidate's 384-row transaction limit cannot stand in for the total
offline backlog. Building that integration would exceed this measurement task.

**Next recommended action:** the previously defined bounded SDK
workspace-restoration/reclamation proof, using **4 MiB /256 KiB NORMAL /48-hour
as a candidate envelope**, without changing partitions or the 72-hour requirement.
That proof must replenish certified erased pages without deleting unsynchronized
history. Do not qualify HIGH or commercial retention until supported volume,
critical reserve/saturation and the authenticated history/outbox mapping are closed.
No automatic implementation or hardware upgrade is started here.

The 111,088-byte candidate OTA margin is tight: compact storage integration,
signed Hub FOTA/rollback/format compatibility and future growth are unfinished.
`-Os` runtime, six-Node peak heap/stack, physical power-cut/GC/endurance and BAT-C8
qualification remain pending. More flash is not approved or purchased.

Evidence: [bounded measurements/reproduction log](R1_4MIB_48H_STORAGE_FEASIBILITY_20261008.log),
[prior 72-hour model/SDK evidence](R1_STORAGE_72H_AGGREGATION_CAPACITY_20261008.md),
[protected Gate C scope](R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.md),
[measured `-Os` image/OTA sizes](R1_HUB_OS_OPTIMIZATION_20261008.md).
