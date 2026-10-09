# Bounded circular flash sizing comparison — 2026-10-09

**RECOMMENDATION=INSUFFICIENT_EVIDENCE.** A circular journal could remove NVS
entry/allocator overhead, but no existing candidate establishes a safe 256 KiB
NORMAL/48h implementation. Stop at this comparison. The simplest engineering
direction is to evaluate additional capacity while retaining NVS, rather than
begin a custom journal for a narrow, conditional fit. No hardware purchase,
backend/format change or production implementation is selected.

Preflight PASS, branch `feature/r1-hub-storage-lifecycle`, start
`08c59073f5aebaac08ad491764b72d46b95e1fdd`, context `2026-10-08.002`.
Canonical/other worktrees untouched; protected `prompt.txt` not accessed.
72-hour design target stays LOCKED; 48h remains a test envelope; `-Os` unpromoted.
GS-D025/026/029 and signed FOTA/application rollback requirements are unchanged.
This is supporting arithmetic, not a change to design or qualification status.

## Reconcile the NVS quantities first

Reuse the [48h fixture/log](R1_4MIB_48H_STORAGE_FEASIBILITY_20261008.log),
[Gate C certificate](R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.md), and
[workspace counterexample](R1_256K_48H_WORKSPACE_QUALIFICATION_20261009.md).

- Event/summary payload: **58,020 B**, not total retained storage. NORMAL48h
  represents 768 source observations +16 local outcomes, 492 exact bodies
  (295 important; 226 native summaries within exact) and 131 history summaries.
- Entire frozen peak map: **89 objects /213,646 logical B**. This includes
  owner/credit witnesses, checkpoint/day/coverage state, 32 HOT tails,
  staging/COW, four temporary metadata values and the unapproved critical
  placeholder. Authentication/restart-context allowances in history extents
  are already charged. Do not charge their tags/context again per event.
- Actual NVS allocation: **56 pages /229,376 B**; initially 6,913 live entries
  /221,216 entry B. Eight raw erased pages become **seven certified pages
  /28,672 B** after the possible lazy active page exclusion.
- **61,440 B /15 certified pages** is the smallest conservative *complete
  next-operation* bound used in the workspace proof. It is not a payload
  size and not just the 36,864–49,152 B control/internal reserve.
- Current un-repacked coexistence needs `56+15+1=72` pages **294,912 B**.
  **282,624 B** is a different, favorable lower bound: after four temporary
  objects are discharged, 6,569 live entries need at least 53 perfectly packed
  pages, plus 15 certified and one lazy page. It is not `229376+61440`.
  The identical 282,624 B in the older NORMAL72h ledger is a separate result.

## Bounded arithmetic sensitivity, not a circular format

No codec, payload, identity, owner, timing/coverage or aggregation changes.
Keep every existing object. For an ideal stream spanning sectors, calculate
`sum(align16(object_length + F))`, then round up using `4096-H` usable bytes
per sector. F=16/64/128 B is **unproven supplemental record framing**;
H=64/128 B is **unproven physical-sector metadata**. These are sensitivity
inputs, not measured format sizes or certified authentication/commit overhead.
F=16 is deliberately optimistic and cannot hold a fresh full AEAD envelope.
The existing compact envelope is 12-byte nonce +16-byte GCM tag; a new journal
must reuse/bind existing authenticated objects correctly or charge that envelope
and record identification/commit/fragments explicitly. Larger overhead is possible.

Illustrative protected workspace: unchanged maximum compact operation lengths
`531+4124+16649+86` B, with the same F/alignment, needs six stream sectors;
add two independently erasable publication/anchor sectors and **one** live-copy/
erase sector: **nine sectors /36,864 B**. This is a budgeting scenario, not a
proven sufficient reserve. Existing temporary/COW values remain charged; this
deliberately independent workspace may overlap some future implementation's
budget. Conversely, relocation of multi-sector dependencies or a torn tail can
need more. It cannot be presented as a minimum or as NVS's reserve transferred
to raw flash. Publication authority, nonce lifetime and fragmentation remain open.

| Sector metadata H | Supplemental framing F | Aligned retained stream B | Retained sectors | Illustrative total incl.36,864 B workspace | 256 KiB margin |
|---:|---:|---:|---:|---:|---:|
|64|16|215,216|54|258,048|4,096|
|64|64|219,488|55|262,144|0|
|64|128|225,184|56|266,240|-4,096|
|128|16|215,216|55|262,144|0|
|128|64|219,488|56|266,240|-4,096|
|128|128|225,184|57|270,336|-8,192|

These assume tightly packed cross-sector objects, no additional torn-tail loss
and only the illustrated relocation reserve. Such packing is not implemented.
Giving each object exclusive whole sectors instead (H=64,F=64) costs **548,864 B
before workspace**; circular address reuse alone provides no packing gain.

Only if the same four temporary values are genuinely discharged, the 85-object
logical total becomes **202,993 B**. The same sensitivity gives **245,760–258,048 B**
including the illustrative workspace (4,096–16,384 B headroom). It neither releases
staging/history nor manufactures a backend receipt. Compare like sets:
89-object NVS un-repacked 294,912 B versus illustrative raw258,048–270,336 B
gives **24,576–36,864 B conditional savings**. After discharge, NVS ideal282,624 B
versus illustrative raw245,760–258,048 B gives the same conditional range.
Actual savings, required reserve and commercial capacity are **UNKNOWN**.

## Recovery, reclaim and costs

The earlier [raw model](R1_STORAGE_ADMISSION_RAWFLASH_PROOF_20261007.md)
has two data/two root sectors and a single selected extent, synthetic external
serial allocation and numeric context. Its successful cuts are evidence for
that scope, not this multi-owner/history/outbox journal. Its source-like HOT
envelope already costs 22–25 B beyond plaintext; full restart context can be
1,370 B per sector. We retain existing context inside the fixture and make no
claim that a 64-byte physical header replaces it. No old crash suite is rerun.

A candidate would still need versioned authenticated lengths/identity/ownership,
durable commit/publication evidence binding the full selected closure, unique
nonce/reuse handling and bounded recovery. Torn/unpublished writes cannot ACK;
corrupt/missing selected dependencies must fail closed, never silently select
stale routine state. Retire credits only after authenticated complete reports;
erase a sector only after **all** local/retry/backend dependencies are discharged
or durably relocated under a recoverable publication. EventKeys, exact important
bodies, motion point/gap evidence and NO_OBSERVATION remain intact. GS-D029 excludes
malicious full-image restoration, not these ordinary crash/corruption obligations.
FOTA's previous valid application must understand supported durable state.

Minimum reclaimable **event-history** space during the outage is zero: no cloud
ACKs exist. At most four obsolete metadata objects /10,653 logical B are modeled
as discharged; their sector co-residency is not known. This does not prove even
one whole sector becomes erasable. Keeping a circular pointer cannot change that.
A live 6,144-byte object already spans sectors; one copy sector is not a universal
GC bound. Repeated cuts consume space until safe cleanup or storage-full rejection.
No indefinite retry/GC loop or wraparound overwrite is permitted.

Sequential append could avoid NVS entry/index writes. Whole-sector relocation,
per-publication root rotation and hot control sectors can offset that benefit.
Erase/write amplification and lifetime are **UNMEASURED**; live-copy amplification
can become very high as reclaimable bytes shrink. No wear/battery percentage claim.
RAM could use bounded streaming buffers (illustratively one4KiB sector), but the
index, authenticated manifest (up to16,649 B), relocation/recovery scratch and
six-owner state remain necessary. Net RAM/stack savings are **UNKNOWN**.
CPU adds scans, authentication and copying; restart can scan up to64 sectors,
with ACK/recovery latency unmeasured. No physical measurements or extra allocations.

For NORMAL72h, the **existing** logical peak alone is258,702 B: only3,442 B remain
before additional journal framing/workspace. The same preserved map plus the
illustrative reserve cannot fit256 KiB. HIGH48h's existing logical peak512,654 B
already exceeds the partition by250,510 B; its prior NVS modeled shortfall282,624 B
is a different physical accounting. Neither implication is a new simulation or
a universal lower bound for every future representation.

Implementing a qualifying circular backend would be substantial: multi-sector
append/publication, indexing, recovery authority, authenticated nonce lifecycle,
safe live-copy GC, fault injection, SDK/physical wear/RAM/latency and FOTA-format
compatibility. Existing host transaction semantics can be reused, but do not
supply those physical primitives. Credible certification needs that implementation;
it exceeds this task, so **stop with INSUFFICIENT_EVIDENCE**. Additional flash with
NVS is the simpler direction to evaluate, subject to module/BOM/OTA approval and
sustainable reclamation qualification; no automatic MCU/partition change.

## Reproduction and validation

Only this calculation was run; no SDK load, HIGH workload, 72h generator or
historical capacity/crash/fuzz suite rerun:

```python
import json, math
from pathlib import Path
rows = [json.loads(x[6:]) for x in Path(
    'docs/exec-plans/evidence/R1_4MIB_48H_STORAGE_FEASIBILITY_20261008.log'
).read_text().splitlines() if x.startswith('MODEL=')]
r = next(x for x in rows if x['scenario']=='NORMAL' and x['hours']==48 and x['worst'])
s = [n for n,c in r['object_size_runs'] for _ in range(c)]
assert len(s)==89 and sum(s)==213646 and r['cloud_acknowledgments']==0
a = lambda n: (n+15)//16*16
for H in (64,128):
    for F in (16,64,128):
        b = sum(a(n+F) for n in s)
        p = math.ceil(b/(4096-H))
        w = math.ceil(sum(a(n+F) for n in (531,4124,16649,86))/(4096-H))+3
        assert w==9
        print(H,F,b,p,(p+w)*4096,262144-(p+w)*4096)
```

Arithmetic/table/link consistency and whitespace checks PASS. No executable
circular-journal test or measured savings claimed. Evidence-only local commit;
no production/partition/BAT-C8/context/governance/worktree synchronization or push.
