# R1 72-hour offline aggregation and capacity analysis — 2026-10-08

Initial preflight **PASS**, branch `feature/r1-hub-storage-lifecycle`, context
`2026-10-07.003`, HEAD `29fca17f9407706d901ebbeaecf7f70773f8eb1c`.
Only user-owned `prompt.txt` was untracked; it was never read, changed or staged.
The user-directed checkpoint defers product-decision/context governance recording.
No GS-D025 or context update has been committed; no canonical worktree is modified.
Approved direction, open bounds and resume instructions are preserved in the
[checkpoint handoff](R1_STORAGE_72H_CHECKPOINT_HANDOFF_20261008.md). Work is paused.

## Decision and limits

**Keep NVS as the preferred technical candidate and the current 4 MiB ESP32 as
the baseline. Do not freeze or production-integrate storage yet.** The proposed
256 KiB option is materially safer than 192 KiB at the same limiting OTA image
size, but it is **not an approved partition or a general 72-hour guarantee**.
The conservative mostly-ordinary NORMAL fixture needs a modeled237,568 B peak
and passes the installed-SDK256 KiB capacity/reclaim test. Mixed NORMAL needs
282,624 B and fails256 KiB. HIGH worst-size mostly ordinary needs536,576 B;
STRESS needs5,132,288 B. Stop those unsupported guarantee branches; do not
choose a new MCU, raw engine, larger unrequested layout or unsafe summary.

The next decision is an explicit supported information/volume envelope, including
native Node aggregates and exact safety/coverage traffic. More exact per-kind
bounds and lawful source/checkpoint ownership reuse may improve these conservative
figures; they are unproved here. Global103-byte WARM fallback is deliberately
used for every retained exact body in the adverse-size comparison. Typical16 B
comes from the previous frozen trace, **not a measurement or maximum for this mix**.
No universal minimum partition size is established.

Approved direction: target72 elapsed hours of internet-only outage, preserve
local monitoring and necessary learning/coverage state, allow eligible ordinary
motion aggregation, preserve important evidence exactly, backfill on return,
and durable-before-ACK. Final exact/critical classes, event envelope, summary
and fault bounds, full behavior and partition remain unapproved.

## 72-hour contract being refined

Assume powered Hub/Nodes and functional local radio; the internet/backend is
unavailable. Local rules continue without waiting for cloud. Accepted observations
have a durable body/replay obligation before Node ACK. Important events, local
alert outcomes/actions, availability gaps and recovery information remain
individually identifiable. Eligible ordinary history may use the declared summary
fidelity. A rolling72 hours includes parts of **four** local dates. Current and
closed-day state must recover, with a stable day/revision identity preventing
repeat baseline application and cloud effects. No observed activity is not proof
of adequate observation. The model assumes coverage for the internet-only case;
it does not qualify the sensor-health thresholds that establish coverage.

Power outage is an observation gap, not72 hours of monitoring; persisted state
survives only through the applicable recovery guarantees. Node outage is a
per-sensor unknown/fault interval with no invented inactivity. Hub reboot
recovers the selected checkpoint and residual immutable inputs before monitoring
resumes; it does not reset credit, ownership, dedupe or the outage horizon.
Hardware/time acquisition and the complete routine/learning reducer remain
unqualified. Existing32-pending queues do not promise unlimited event creation.

**Candidate**, not a product promise:72h at NORMAL only for a declared composition,
record bound, additional local-outcome/gap budget and reserve. HIGH requires a
separate bound; the max-size profile below fails every reviewed partition.
STRESS requires explicit backpressure/degraded operation and finite critical
saturation behavior. A time target alone cannot specify finite storage.

## Classification and eligibility

| Class | Candidate representation and exclusions | Approval boundary |
|---|---|---|
| A exact essential | Call Family, I Am OK separately; important door transitions; alert creation/acknowledgement and dependencies; unexpected activity; missing-routine conclusions and supporting anchors; offline/recovery/observation/security/storage faults and user/mode actions | Existing required semantics preserved; exhaustive critical mapping and quotas OPEN |
| B ordinary history | Only a `Motion` point whose safety/routine consumers have been durably materialized; source identity/timing retained in a bounded loss-aware bucket | Ordinary aggregation direction approved; eligibility implementation and closing/late horizons proposed |
| B native Node `MotionSummary` | Keep its frozen exact body, including count and millisecond `first_ms/last_ms`; it already has limited repeat fidelity | This run does not substitute seconds endpoints for native millisecond semantics |
| C routine/coverage | Durable current reducer, last-activity/door/morning/night anchors, sensor coverage intervals, four day identities/revisions, learned state and exactly-once application cursor; exact active dependencies, compact persistent statistics when sufficient | Coverage sufficiency, late/day revision and learning formulas not newly invented |
| D diagnostics | Optional verbose logs; battery/RSSI can be dropped from ordinary *history* only after required health/fault state is incorporated | Never drop security/support evidence or a material fault |

Do not merge owners, enrollment/origin, Nodes, sensor meaning, applied configuration,
clock revision, coverage context, checkpoint dependency or calendar bucket.
Exclude unresolved alerts/anchors/window evidence, delayed or uncertain time,
unknown coverage, tests, incompatible context, unmaterialized consumers and any
source whose exact backend submission **may have begun**. If promotion to important
status occurs before finalization, retain its original body. An unbounded future
late correction cannot be promised from a finite summary: finalization/revision
policy is OPEN and blocks an unconditional eligibility guarantee.

Actual `shared/src/rules.cpp` uses exact EventKeys and seconds for inactivity,
configured morning sequence and night visit spacing (default300 s). It **ignores
EventKind::MotionSummary** in activity rules. Never feed the new public history
summary to that existing enum as a replacement input. Safety rules run on original
inputs; selected consumer state is the compaction dependency. The supporting
routine guide's old no-lower-time-bound/no-PIR-aggregation statements conflict
with current rule/Node source and are not used as requirement authority.
Learning is still a requirement/implementation gap; these tests do not implement
or prove a new personalized anomaly algorithm.

## Minimal candidate summary, frozen codec unchanged

Host scalar grammar:34-byte header +9 bytes per separate `Motion` point, at most
32 points and a64-sequence membership span. Header: version/fidelity, context-row
and meaning, relative local date/bucket, clock revision, checkpoint reference,
64-bit source sequence base, explicit64-bit membership, count, common uncertainty,
coverage reference. A point stores source membership slot, occurrence offset,
original monotonic millisecond delta and original Hub receive lag. Source origin,
full owner/Node/configuration identity, clock mapping/basis, absolute calendar
basis and durable generation live in independently authenticated restart context.

The membership mask preserves holes; a first/last sequence interval alone is
unsafe. Points preserve their separate times and gaps. Count of raw Motion is
implicit one; first/last derive from points. No duration, occupancy or continuous
presence is asserted. A source MotionSummary remains an original encoded body;
its repeated observations were already reduced upstream, and no continuous
presence is inferred there either. Context/date references and full-source
serialization are **proposed**, not production-qualified by the scalar encoder.
All field-range/context mismatches must retain exact bodies or fail closed.

NORMAL mostly ordinary:43..61 B/plain summary, mean57.3125 B; framed mean59.3125 B.
Global32-point maximum322 B/plain,324 B with two-byte framing. Shared restart
cost is792 B/sample or1434 B/max: previous728/1370 plus64 B charged for summary
context extensions. Previous authenticated extent overhead remains included in
that inherited context budget; standalone encryption would additionally need
its own existing-strength envelope. Headers/tails and NVS entries are not free.

Candidate encryption/authentication uses the existing strength and binds format,
installation/household/source ownership, context/configuration, clock basis,
checkpoint, immutable segment generation/position and payload. Fresh nonce/root
freshness/rollback and complete serialization remain OPEN. Host SHA256 identities
are content bindings, **not an authentication substitute**.

5/15/30/60-minute containers preserve the same individual point timing. The60-minute
candidate reduces header multiplicity; it does not lower activity resolution to
an hour or permit a continuous-presence claim. This choice is not locked. Connected
sync remains near-real-time exact delivery, independent of container closure.
Original inputs remain durable until consumer state and immutable replacement
are selected, even when a bucket closes earlier.

## Durable dependencies and backend contract

1. Node durably retains its immutable event before transmit.
2. Hub validates current authenticated ownership/domain; retries compare immutable
   source key/digest, not a new receive timestamp. New admission spends durable
   bounded credit and checks protected physical workspace. Failure yields no ACK.
3. Hub publishes/readbacks original body plus recoverable local effect/input obligation;
   only then Node ACK is legal. Lost ACK reuses identity, without a new effect/credit.
4. Run existing safety/routine consumers. Persist required alert outcomes exactly.
   Persist/select processed-state checkpoint/cursor before eligible input retirement.
5. Commit immutable new summary and its complete source/context/dependency manifest;
   independently commit/select the new root. Keep the old root, bodies and state
   until complete new selection is validated. `nvs_commit()` is not multi-key atomicity.
6. Reclaim original *body* only after selected replacement and all consumers permit it.
   Exact retry key/digest witnesses survive independently until a selected authenticated
   complete retirement report proves covered absence. Cloud completion is not that proof.
7. Before exact network submission, durably fence its representation as ever-submitted.
   Such events remain exact even after timeout/lost ACK. A summary is immutable once
   selected/submitted. The backend atomically claims its **explicit** source membership,
   stable representation ID+content digest and required history/derived effects.
   Retry of the same ID/content returns COMMITTED; a different overlapping representation
   conflicts/fails closed. Summary completion never ACKs unrelated originals.
8. After authenticated matching backend COMMITTED, select/readback durable completion
   and owner release before reclaim. Until that receipt, resend the same representation.
   Reboot and another interruption retain old bodies or complete selected replacement.

The production backend currently accepts **one exact DomainEvent application effect**
under household+EventKey and canonical payload digest. It has no qualified summary,
covered-source claim, coverage/day revision or manifest-level completion API. Required
changes: authenticated versioned summary/coverage acceptance; exclusive source claims;
atomic retained representation plus required derived effects/outbox; stable receipt;
PWA fidelity/gap rendering; day/revision idempotency and corrections. Hub exact submission
fence and summary ownership are also new. No API/backend/PWA change is made here.
A summary cannot be silently sent to the current exact-event endpoint.

The host backend rejects raw/summary overlap and changed content, and repeats a
lost summary ACK without duplicate effects. Atomic server behavior and checkpoint
publication are **model assumptions**, not a cross-system atomic commit proof.

## Workload and options

Engineering inputs384/1776/23232 source semantic records/day =>1152/5328/69696 in72h.
Six interleaved Nodes, deterministic seed720008+rate,0..2 s timestamp jitter,
0..20 ms monotonic jitter, source kind1/3 native MotionSummary among non-action
traffic,24 additional exact local outcomes/health/fault records in72h, source
origin change36h, clock revision48h, delayed every211th and uncertain every997th
source. This mixture is a test input, not a measured Node arrival guarantee.

Profiles:2% requested actions for mostly ordinary;15% plus room morning/night
exclusions for mixed;60% actions plus those exclusions for door/user-heavy;
mixed plus bathroom coverage unknown30..38h and two exact fault intervals;
192-record simultaneous bursts; mixed near saturation; mixed reboot during phases.
Last activity per Node is exact in every profile. All traces cross four dates.

The Node's actual episode policy uses45 s quiet closure and300 s connected maximum;
radio-outage idle behavior is separate from an internet-only outage. Continuous
six-Node motion with first Motion+one native summary per300 s episode illustrates
3456 records/day, not HIGH1776. Short/single-point episodes and door/user traffic
change the mix. These facts do not establish a universal rate/endurance guarantee.

Option A retains every unsynced exact frozen record. Option B retains exact classes
and native source summaries while grouping eligible separate Motion points.
Option C (adaptive) cannot discard points/gaps, reclassify fidelity or rewrite
inflight backend sources safely without another transition/manifest/COW. Changing
containers saves only headers; choose fixed B for the conditional candidate.
No adaptive algorithm or new compression is implemented.

Worst-size mostly ordinary comparison; exact includes24 local outcomes:

| Option/container | NORMAL payload B | NORMAL modeled protected peak B |
|---|---:|---:|
| A exact |121128 |315392 |
| B5 min |77860 |266240 |
| B15 min |77860 |266240 |
| B30 min |71452 |258048 |
| B60 min |61372 |237568 |

B reduces this NORMAL payload49.3%, but safety/metadata/peak costs prevent treating
that ratio as physical capacity gain. Typical exact16-byte input can be denser
than34-byte summary headers plus sparse points. CPU advantage is not used to
justify information loss. Source replay and targeted lookup use bounded object
cursors, not a RAM index for every72-hour source.

## Whole-object peak ledger

All384 conditional witnesses charged in six4079-byte banks, even when overlapping
HOT bodies. Three3485 report banks, three6144 reducer/checkpoint banks, two512
roots, two4096 owner/context/backend metadata objects, four320 daily states.
Fixed logical total63,857 B, fixed NVS entry total65,600 B (plus32 B namespace). These inherited sizes
remain candidate budgets, not serializers or final learning bounds.

Protected critical alternatives32/64/128 maximum HOT admissions charge2/4/8 full
4096-byte placeholders (logical8192/16384/32768; NVS entry8384/16768/33536 B).
They are alternatives for approval, not an unlimited guarantee. Normal traffic
must not consume them. Final classification and replenishment are not implemented.

Candidate: maximum32 unpacked Hub HOT tails (6144 entry B at124 B each), serially
seal Node flights;128-input checkpoint staging comprises **eight**4096-byte
extents at max103-byte WARM+1434 header.32 sources do not fit one extent. Typical
16-byte stage needs four extents. Full source staging remains through processed
checkpoint and summary selection; no favorable exact-body overlap is subtracted.
Additional independent report3485/checkpoint6144/two512 selectors cost10,944
NVS entry bytes. This deliberately retains all old banks while next owners commit.
Node192 pending does not require192 *simultaneous standalone Hub HOT* blobs.

NVS blob lower bound: `ceil(B/32)+ceil(B/4000)+1` entries;126 entries and64 page
metadata bytes per4096 page. Round live entries to pages; add one GC page and one
engineering page. Fragmentation/selected-root layout can exceed this lower bound;
actual SDK tests follow. The critical dummy values protect live capacity; an
application physical guard and their safe utilization still require integration
proof. Free-entry statistics are not an allocation guarantee.

Largest original flight still exists logically through staging. The proposed
serial32-body path needs persisted inventory/source digest/report credit together;
existing384-key lemma remains conditional. With192 simultaneous standalone HOT,
add at least160*192=30,720 entry B and page rounding. The favorable32-tail result
cannot qualify that different allocator state. Current production still has no
new bound and rejects its129th immutable archive event.

## Scenario results — CAPACITY MODELED

Counts include24 additional local outcomes (26 for Node-loss). `Exact` is all
retained original bodies; `essential` is the candidate A subset, which overlaps
some native source aggregates/anchors. Do not add those subsets together.
Typical/max columns are different record-size assumptions on the same timeline.

| Rate | Profile | Exact | Essential | Native source-summary exact | New summaries | Typical peak B | Max peak B |
|---|---|---:|---:|---:|---:|---:|---:|
|NORMAL|ordinary|430|53|374|288|151552|237568|
|NORMAL|mixed|728|433|338|197|147456|282624|
|NORMAL|door_user|959|809|174|146|147456|315392|
|NORMAL|node_loss|737|435|338|194|147456|282624|
|NORMAL|simultaneous|430|53|374|48|139264|225280|
|NORMAL|saturation|728|433|338|197|147456|282624|
|NORMAL|reboot|728|433|338|197|147456|282624|
|HIGH|ordinary|1899|129|1751|439|221184|536576|
|HIGH|mixed|3278|1921|1538|298|225280|745472|
|HIGH|door_user|4366|3723|731|273|233472|913408|
|HIGH|node_loss|3309|1923|1538|293|225280|749568|
|HIGH|simultaneous|1899|129|1751|224|212992|528384|
|HIGH|saturation|3278|1921|1538|298|225280|745472|
|HIGH|reboot|3278|1921|1538|298|225280|745472|
|STRESS|ordinary|24423|1373|22789|2448|1286144|5132288|
|STRESS|mixed|42679|25230|19779|1682|1404928|7913472|
|STRESS|door_user|56838|48561|9387|1656|1527808|10104832|
|STRESS|node_loss|43069|25232|19779|1657|1409024|7970816|
|STRESS|simultaneous|24423|1373|22789|2336|1286144|5132288|
|STRESS|saturation|42679|25230|19779|1682|1404928|7913472|
|STRESS|reboot|42679|25230|19779|1682|1404928|7913472|

The [scenario CSV](R1_STORAGE_72H_SCENARIOS_20261008.csv) and [model log](R1_STORAGE_72H_MODEL_20261008.log) preserve every option/bucket/reserve parameter. No simulated distribution is a supported product bound.

## Runtime validation — SDK NVS EMULATED

ESP-IDF6.0.3 source commit `76f5dedd9950a3012fee8fb7d5586df21fc67802`, same
Linux partition driver as prior diagnosis. No fresh-image generator is used to
claim forward progress. Values are length-matched dummy bodies/selectors. Each
fixture loads all steady owners, staging, candidate report/checkpoint/roots,
protected placeholders and32 HOTs; it then releases the candidate workspace,
executes32 independent new report/state/selector readback+reclaim cycles and
remounts/checks every retained original fixture value. Capacity stops are expected
counterexamples, not suppressed failures. Synthetic descriptors48/64 pages do
not alter the production partition CSV or qualify device flash.

| Partition | Tested72h support | Physical peak/free | Forward progress / reserve boundary |
|---|---|---|---|
|128 KiB |All final full fixtures fail, including typical NORMAL |Failure-path allocation can consume all32 pages; see raw counters |NO for this owner/staging map; previous narrow3-segment result remains valid, overall optimized128 KiB UNPROVEN |
|192 KiB |Typical NORMAL passes; max NORMAL and all tested HIGH fail |Passing churn peak47 pages=192512 B,4096 B erased |32 updates pass only for typical fixtures; no worst-size admission guarantee |
|256 KiB |Max mostly ordinary/simultaneous NORMAL and typical NORMAL/HIGH pass; max mixed NORMAL/HIGH fail |Passing churn peak63 pages=258048 B,4096 B erased |32 updates+remount pass in supported fixture; arbitrary fragmentation and physical admission guard UNPROVEN |

Allocation peaks include reusable deleted entries. One erased page is **internal
GC**, not4096 B guaranteed application admission. NVS churn can use physically
nonblank pages despite substantial reclaimable entry capacity. Protected critical
placeholders are live and normal traffic cannot overwrite them; safe use of that
reservation and a universal next-operation guard remain OPEN. Do not substitute
nonblank-page count for live entry bytes or claim an unallocated engineering page
at every runtime instant. Selected fixture margin is demonstrated by completing
the actual next operations, not free-entry statistics alone.

For max ordinary NORMAL, modeled protected237568 leaves24576 B against256 KiB;
measured peak live7043 entries=225376 B. For max mixed NORMAL, modeled282624 has
20480 B deficit even against256 KiB and actual loading fails at the candidate
checkpoint. Max ordinary HIGH536576 has274432 B deficit against256 KiB. STRESS
ordinary5132288 has4870144 B deficit. Typical HIGH221184 fits256 in the fixture;
that cannot become a worst-supported guarantee.

Pure-exact theoretical planning ceilings with the same32 HOT/report/reserve but
a two-extent next promotion (no128-input aggregation staging):125/500/875 global
max103-byte bodies for128/192/256 KiB. With the full eight-extent B staging, ceilings
are0/350/725 **if no ordinary summary/source-aggregate body consumes history**.
These are entry/page arithmetic, not SDK-qualified supported essential counts.
For the actual NORMAL ordinary composition, at256 KiB five extra history extents
could budget at most125 more max exact bodies under this arithmetic. Final exact
class/volume quotas and physical-layout qualification remain UNPROVEN.

Critical alternatives at NORMAL ordinary max:32=>237568 B;64=>245760 B;
128=>266240 B. This exposes the reserve tradeoff without approving32/64/128.
Report/COW/GC space is separate from those critical bodies.

Fault model retains the corrected power-off latch until remount:4-byte program
cut units/whole-sector erase model, not arbitrary hardware brownout.40 temporary
4096-byte churn operations prime GC; immutable summary4096, processed-state6144
and selector512 commit before original124-byte body retirement. Sampled cuts
include1071/1072/1073, publication/cleanup and GC; old/new bytes are fully checked.
The host semantic model also tests a second reboot at every compaction phase.
These are independent new-summary checks, not a reclassification of the prior
fault1072 (which remains FAULT_INJECTION_MODEL_DEFECT). Neither authenticated root
contents nor real target interrupted erase/encryption is qualified.

## Write schedule, wear and RAM

Candidate schedule commits each original124-byte HOT before ACK; every32 inputs
seals **two** maximum-size source extents and commits3485 report+512 selection;
checkpoint6144+512 selection every128 inputs or next32-input flush after6 hours;
append only newly required4096 history extents, then release superseded source
staging. Four320-byte day writes are charged. No full witness/metadata/all-owner
rewrite occurs per event. This length-matched schedule covers uniformly paced
source arrivals plus24 local outcomes; its exact placement is not the semantic
serializer/reducer implementation. Reports assume working local radio; rejoin
keeps credit/root generations and drains retained keys without resetting them.

NORMAL72h (1176 total durable inputs):logical changed-value816209 B, programmed
970944 B, WA1.189578,28656 entry spans written,185 page erases, maximum7 on one
sector;18 checkpoints,37 reports,24 history extents. Average/day:logical272069.667 B,
programmed323648 B,9552 entries,61.667 erases. Denominator includes full stage,
checkpoint, report and padded extent bytes; programmed/source-HOT-input ratio is
6.658328, so the1.19 ratio alone does not establish economical per-event wear.
Backfill24 proposed manifests adds24020 programmed B and5 erases, including96-byte
submission fence,96-byte completion and512-byte selector per manifest. Current
backend has no such completion contract; physical effect/receipt schedule remains
conditional. Setup writes are excluded from these counters.

HIGH/STRESS72h and per-day wear are **UNPROVEN**: at256 KiB this max-size retained
schedule stops at2048 inputs (HIGH second source seal; STRESS report). Partial
counters are preserved, never extrapolated as complete/day. Prior connected
checkpoint-every32 sensitivity remains1.641702/1.728766/1.745295 and90/461/6089
erases for NORMAL/HIGH/STRESS; it is not this72h guarantee. Prior10,000 heavy
synthetic cycles retain1.612810 WA,69755 erases total,6.9755/cycle, maximum2961
on one sector. Do not rerun that already-qualified sensitivity campaign.

Erase concentration arises from fixed live certificate/context/state ownership
and the smaller dynamic NVS allocation/GC working set, with report/checkpoint/root
churn. No per-event all-owner rewrite is required. NORMAL max7/185 across64
sectors is about2.42 times whole-partition mean; this is a single bounded trace,
not steady lifetime. Endurance specification, target flash-encryption writes,
long-running connected/outage/backfill distribution and target concentration are
UNPROVEN. No physical lifetime is claimed.

Bounded application RAM proposal (bytes):exact384 index12452; credit/class432;
report assembly3485; full context1536; six322-byte point accumulators plus64-byte
working metadata each2316;64 pending-object descriptors2048; cursors512;
active routine/four-date reducer6144; recovery checkpoint6144; flash/read/encode
workspace4096; receive1024; selector512; storage stack2048. Total**42749 B plus
NVS internal allocations**, not a target measurement. Backlog retrieval streams
at most partition bytes; no RAM array for all source IDs or every historical
summary. The Python fixture's full collections and stale-key oracle are test
memory, not a proposed target ledger. Bounded retirement correctness uses the
existing conditional384-admission proof, not that Python oracle.

SDK internal page hash/cache, object buffers and live key count must be measured
on target. Prior current-image static DRAM45783/linker remaining134953 is not heap
headroom after runtime allocation; **target RAM headroom UNPROVEN**. MCU/RAM
unsuitability is not demonstrated. No MCU upgrade is justified by these findings.

## OTA and platform

The [partition review log](R1_STORAGE_72H_PARTITIONS_20261008.log) runs the installed
SDK generator on temporary legal4 MiB layouts. Existing supporting partitions
remain unchanged. App offsets are64 KiB aligned; sizes/overlap/end are checked
by the installed generator. Both slots must accept the image.

| Storage | OTA0 offset/size | OTA1 offset/size | Lifecycle offset | Limiting current-image margin |
|---|---|---|---|---:|
|128 KiB |0x20000 /1966080 |0x200000 /1966080 |0x3e0000 |101456 B |
|192 KiB asymmetric |0x20000 /1966080 |0x200000 /1900544 |0x3d0000 |35920 B |
|256 KiB symmetric |0x20000 /1900544 |0x1f0000 /1900544 |0x3c0000 |35920 B |

A symmetric192 KiB option with two1900544-byte slots wastes an additional65536 B
alignment/tail gap; larger equal slots cannot both fit once the next app offset
is aligned.192 KiB therefore offers **no better limiting dual-OTA image margin**
than256 KiB here. The current app1864624 B is previously measured and unchanged;
production storage/summary/API integration growth is not measured. At192/256,
16 KiB added image leaves19536 B,32 KiB leaves3152 B,48 KiB exceeds by13232 B.
Current image fit is not integrated OTA approval or a rollback-compatibility proof.

Keep4 MiB ESP32 baseline. Extra flash need is conditional on supported information
volume; MCU performance and RAM needs are unproved separately. No hardware upgrade
is approved/required by current evidence. Choosing256 over192 is a technical
candidate recommendation; final partition is **UNDECIDED** until the volume/reserve
and firmware-growth gates close. Raw is fallback only: no new raw design or
matched-workload evidence demonstrates an advantage.

## Pressure policy and remaining decisions

Proposed order:reclaim completed and locally-unneeded data; aggregate only eligible
unsubmitted ordinary motion; reduce optional diagnostics; enforce ordinary quota
before protected critical/report/recovery space; backpressure new ordinary
admissions while reports and safe reclamation continue; persist/signify degraded
coverage/history status before exhausting its metadata allocation. Authentication,
exact retry/stale/conflict and durable-before-ACK survive pressure. Node retained
retries do not create new credits. No report/epoch reset hides fullness.

Ordinary saturation, exact critical saturation and physical flash failure are
separate. A finite critical allowance can fill; no silent ACK/loss or fabricated
normal routine is permitted. Node retry/gap handling and caregiver degraded/fidelity
messaging need explicit supported behavior; internet outage itself cannot provide
immediate remote notice. When the last essential representation cannot commit,
return no durable ACK and retain/report the known degraded state through available
paths. Full Node queues/indefinite critical input need a product decision, not a
storage eviction trick. Software cannot durably write to failed flash.

Open product decisions:exhaustive important/critical classification; per72h exact
and native-summary/ordinary volume and maximum sizes; gap/fault/reboot envelope;
critical32/64/128 choice; saturation/backpressure/degraded UX; coverage sufficiency
and late/day/clock correction horizon; new summary/coverage/effect backend contract;
partition approval and minimum firmware/OTA growth allowance. Approved direction
alone closes neither those bounds nor physical qualification.

Open technical blockers:complete source/context authentication+immutable digest
projection and persisted384 credit/report/root; universal physical next-operation
allocator guard; selected summary/checkpoint/manifests+completion serialization;
full routine/learning/time/day reconstruction; Node flight/report fairness;
backend summary/claim/revision implementation; encryption/brownout/GC hardware,
nonce/freshness/FOTA rollback, target heap/stack and integrated signed image;
real connected/backfill wear/endurance. Production readiness and architecture
freeze are **NO**. Stop further exploration in this run; resolve those explicit
policy/implementation gates in separate authorized tasks after canonical promotion.

## Focused validation and reproduction

**HOST PROVEN within model assumptions:**14 Python tests:separate ordinary points;
exact safety/actions/doors; native source summary exclusion; holes/64-bit source
sequences/32-point bound; ownership/authentication precondition rejection;
checkpoint/summary/select/reclaim cuts and second reboot; lost Node ACK/retry/
digest conflict; exact ever-submitted fence; backend lost ACK/receipt and overlap;
completion-before-release with witness survival; Node report cannot replace
pending cloud history; serial32 inputs for192 pending keys; coverage distinction;
72h all rates/seven profiles/four dates, day/epoch/clock split and delayed exact.
These tests use atomic immutable objects, a materialized-checkpoint abstraction,
and an atomic mock server. Full native routine/day revisions are UNPROVEN.

**Actual rule source HOST PROVEN:**focused C++ test compiles unchanged RulesCore:
unknown vs covered missing-morning, sparse points/night visit spacing and stable
keys, native MotionSummary ignored, exact inactivity anchor and door chronology
through copied checkpoints. Copied state is not flash serialization proof.

**SDK NVS EMULATED:**54 capacity fixtures:15 pass;39 expected capacity stops.
60 sampled latched summary/checkpoint/selection cuts after GC priming:60 pass
OLD_VALID or NEW_VALID, including cut1072/neighbors and transaction erases.
NORMAL full72h length-matched schedule/backfill passes; HIGH/STRESS stop at2048.
Passing API update/reclaim witnesses do not qualify authenticated application
selection/credit, all possible fragmentation or physical target power loss.

**Sanitizers:**actual-rule test ASan+UBSan PASS;60 SDK fault cases PASS with probe
main/header instrumented, SDK archives uninstrumented; LeakSanitizer disabled.
Existing lifecycle/density/admission and actual backend-completion regressions
PASS, exit0. Their unchanged built-in long fixtures are reused regressions;
no new generic million-event/full-repository/hardware campaign was added.

Artifacts: [host tests](R1_STORAGE_72H_HOST_TESTS_20261008.log),
[actual rules and sanitizer](R1_STORAGE_72H_RULES_20261008.log),
[SDK capacity](R1_STORAGE_72H_NVS_CAPACITY_20261008.log),
[SDK fault/GC](R1_STORAGE_72H_NVS_FAULT_20261008.log),
[SDK schedule/backfill](R1_STORAGE_72H_NVS_SCHEDULE_20261008.log),
[build](R1_STORAGE_72H_BUILD_20261008.log),
[SDK sanitizer compile/link/run](R1_STORAGE_72H_SANITIZERS_20261008.log),
[regressions](R1_STORAGE_72H_REGRESSIONS_20261008.log).
Raw run commands, binary/fixture hashes and child exit statuses are retained.

Field/staging audit corrected preliminary fixtures before the decision:32 max
source records require two extents; full source clock provenance needs9-byte
Motion points; native MotionSummary millisecond endpoints cannot use a seconds-only
9-byte shape. Earlier SDK counters remain preserved in the explicitly
[SUPERSEDED development log](R1_STORAGE_72H_PRE_STAGE_AUDIT_20261008.log).
No favorable preliminary HIGH pass is used as final safe retention evidence.

From repository root (reuse README's existing staged SDK environment):

```sh
base=code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2
probe=$base/host/storage/nvs_runtime_probe
python3 "$base/host/storage/offline_72h_model.py" --output /tmp/gs-72h-cases.json
python3 "$base/host/storage/test_offline_72h_model.py"
cmake --build "$probe/build"
python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite capacity
python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite schedule
python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite fault
python3 "$probe/build_host_sanitizer.py" --output /tmp/gs-72h-san
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
 python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite fault \
 --binary /tmp/gs-72h-san/probe.elf
python3 "$probe/review_budget.py"
"$base/build/storage_lifecycle_validation"
"$base/build/storage_density_validation"
"$base/build/storage_admission_validation"
"$base/build/hub_backend_commit_validation"
```

Actual-rule compile/run commands are in the rules log. All scripted expected
capacity stops are checked, not called a successful capacity guarantee. Runners
unlink only each completed child's explicitly emitted temporary emulator file.
No production code, frozen codec, production/test partition CSV, ACK behavior,
backend/PWA, BAT-C8, Jira or hardware changes. Final technical checks precede the
approved direction/context documentation commit; canonical promotion is required
before further substantive work. The current canonical branch is not updated.
