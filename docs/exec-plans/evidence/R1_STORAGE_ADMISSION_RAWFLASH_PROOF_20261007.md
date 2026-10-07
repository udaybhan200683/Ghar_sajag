# Bounded admission and NVS/raw flash proof — 2026-10-07

Context preflight PASS at local/canonical `2026-10-07.003`; start HEAD
`347d5f4ae9a278433b3213fb57e851e56342cc41`, clean worktree. Codec frozen at
`74c4b99`: no density codec, production firmware, ACK, partition, backend/PWA,
BAT-C8, Jira or hardware change. No new LOCKED decision or context bump.
This document refines [the lifecycle evidence](R1_STORAGE_RETIREMENT_RECLAIM_PROOF_20261007.md)
and [ExecPlan section24](../active/R1_HUB_STORAGE_DATA_LIFECYCLE.md).

## Result and proof boundary

**DERIVED / HOST-MODELED:** persist a complete retirement report plus a bounded
uncovered-admission window W per Node. The exact-key bound is `6*(32+W)`;
W=32 gives384, but32 is a one-full-flight operating choice, not necessary for
correctness or an approved final policy. Critical credits are carved out of W,
not added without limit. Reports/control must progress independently of event
admission. Credit durability, critical classification and safe saturation remain
production STOP gates.

**SOURCE-DERIVED / FRESH-IMAGE TESTED:** remapping all fixed objects into NVS
entries changes the previous event-pool-only comparison. A conditional whole
NVS layout fits the synthetic72h NORMAL sample/max-name workload at
122,880/126,976 B. The official installed generator constructs these fresh
images with all stated logical objects and a free NVS page. This does **not**
prove the runtime allocator can maintain that occupancy after churn or preserve
all owners at peak.

**DERIVED correction:** three independently erasable6144-byte raw checkpoint
banks require3*8192=24,576 B. The prior20,480 B arena requires a sharing/release
proof and is not a sector-isolated allocation. With the conservative bank
mapping here, raw fixed102,400 +body pool28,672=131,072. Synthetic72h sample
fits exactly; maximum names need135,168 B.72h is NOT a locked requirement.

**DECISION:** backend UNDECIDED; first qualify efficient NVS runtime allocation
and write/reclaim behavior. A raw migration is not justified by the older
NVS-pool-only deficit. Current128 KiB remains CONDITIONAL; enlargement and a
hardware upgrade are NOT proven necessary. No finite partition can retain an
unlimited unsynced critical stream without an approved saturation information
contract. That product branch stops at REQUIREMENT_GAP.

## A. Evidence growth and minimal finite invariant

Source facts are unchanged: NodeRuntime/recovery pending32 per Node; six Nodes
=>192 instantaneous retryable keys. NodeRadio already reserves
`min(4,capacity/4)=4` slots against ordinary motion at capacity32. This is a
reserve for *all nonmotion priority traffic*, including door/buttons/privacy/
gap, not a critical-only guarantee. NodeStore/radio return failure when full;
existing diagnostics do not prove indefinite critical delivery.

Relevant production paths under the code project:

- `firmware/node/runtime/node_runtime.cpp::record/acknowledge/restore_recovery`:
  retained exact identities, gaps on refused admission, monotone generation and
  fresh boot origin; no queue multiplication at reboot/rejoin.
- `firmware/node/components/radio/node_radio.cpp::can_enqueue/next_due`: current
  priority reserve and outage scheduling; no new credit mechanism.
- `firmware/common/transport/node_retirement_protocol.hpp/.cpp`: complete sorted
  report, at most32 keys, logical30..542 B;170-byte fragment data,44-byte fragment
  header, at most4 fragments. No wire-format change in this run.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp`: independent report
  fragment/ACK retry and prepared generation; bounded progress is not guaranteed
  merely because this sender exists.
- `firmware/hub/components/storage/node_retirement_snapshot.cpp`:
  validate no resurrection; preserve covered listed holes; prune covered absent
  keys only. Current registry schema permits10 coordinates; enforce six live
  source owners and keep historical ownership pinned or rederive bounds.
- `firmware/hub/components/cloud/cloud_sync.cpp` and
  `docs/DURABLE_BACKEND_COMPLETION_CONTRACT.md`: matching authenticated COMMITTED
  plus local durable completion receipt, never radio/application ACK alone.

Counterexample remains: each event is retained, Hub commits/ACKs, Node saves
removal; all retirement reports are lost. Repeat k times. Pending peak1;
Hub historical unresolved exact evidence k. A completed body can become a
certificate, but its exact key/payload binding cannot be guessed retired.
The report's covered-universe complement is what permits rejecting old retries
as Stale without per-key evidence. Backend completion does not supply that proof.
No simple highest-received-sequence watermark is safe with gaps.

Let P_i be the latest selected authenticated complete pending report, |P_i|<=32.
Its covered universe is all older allocation origins plus sequence<=H in its
current origin, not the current transport session or highest received sequence.
Let U_i be committed distinct keys outside this universe. Let E_i be exact
witnesses still required by dedupe (backend bodies are a separate owner).

Required proposed rule:

1. A new uncovered admission requires `|U_i|<W` AND actual durable body/replay/
   backend space. Spend only on successful selected commit; failed writes must
   not produce ACK. Exact retry/conflict/Stale never spends or refills credit.
2. A new covered admission is allowed only if listed in P_i and actual required
   storage is available. A covered absent key is Stale, never a new effect.
3. Select only authenticated, newer, nonregressing complete reports. Prune
   covered absent keys; retain listed and still-uncovered keys. Recompute U_i
   from surviving evidence, **not** from generation increment or ACK count.
4. Report, source owner/epoch, exact evidence and class charges must have one
   selected durable generation. Recover these together; rebuild counts. Neither
   reboot, report replay, rejoin, new transport nor origin change refills credit.
   Counter wrap fails closed. Owner replacement/epoch transition requires an
   explicit durable revocation/progress proof, not a reset loophole.
5. Reserve report assembly/validation/selection COW workspace independently of
   normal data. Retry an immutable prepared complete report to selection;
   scheduling must not continuously supersede/starve it as new events arrive.
   Superseding valid complete reports remain safe. Control progress is allowed
   even with zero new-event credits; fairness assumes eventual working radio.

Induction: initially E empty. New covered keys belong to P; uncovered admissions
add one U within W. Retries add none. A selected monotone report removes covered
absent evidence and shrinks old U; its listed set is still<=32. Thus
`E_i subset P_i union U_i`, `|E_i|<=32+W`, total<=6*(32+W).
Session changes preserve older listed origins, not another ledger per session.
Long disconnect freezes evidence/credits; reconnect/repeated reboot does not
increase the bound. Out-of-order lower generations and report replay cannot
refund credits. Missing listed keys remain exact holes. Additional gap ledger0;
at most32 listed exceptions/Node (192 total) are already in the report banks.

This proves a safety bound conditional on the new rule. It does NOT prove
bounded wall-clock progress with infinitely lost reports, nor safety of blocked
new input under all product outages. Current production has no such finite
historical bound. Latest-report generations may skip safely if complete.

### Window derivation and alternatives

Any finite W yields a finite bound. With one selected report before every new
uncovered event W=1 yields33/Node,198 total. If only one complete report before
one full32-key Node retained flight is guaranteed, W>=32 permits that flight;
W=32 then64/Node,384 total. Faster report cadence can support smaller W, but the
required cadence under power/radio/critical failure has not been qualified.
With separate positive normal and critical credits, W must be at least2
(C=1 plus one normal credit); W=1/C=1 admits only new critical traffic.
W=0 would require every key be reported before ingestion (32/Node); viable only
with a changed report-before-event schedule, not the existing path.

| Alternative | Correctness / failure recovery | Node/radio | RAM/flash / complexity |
|---|---|---|---|
| A fixed admission credits | Finite only if selected durably and replenished by real coverage | Refusal/retry when depleted; no radio time bound | Small counters/rebuilt U; medium integration |
| B mandatory complete report to replenish | Provides safe gap-aware retirement; report-ACK loss harmless | Existing report fragments, up to542 logical bytes per report | Uses bounded report banks; moderate scheduling proof |
| C piggyback report/progress | Reduces separate control traffic; generation alone is insufficient | Full list still needed when holes; fragment/retry starvation must be controlled | Reuses report state; wire/scheduling changes |
| D ACK-issued credit token | Helpful Node hint, never sole authority; token replay/epoch must bind selected report | Additional authenticated control information | More counters/token recovery; unnecessary for Hub safety |
| E bounded origin ledger alone | Unsafe: one origin can produce unlimited ACKed-unreported keys | Easy reboot/rejoin | Does not solve growth; reject as standalone rule |
| F A+B, opportunistic C | Finite safety bound plus independently serviced complete reports | Existing report shape, no mandatory token redesign | Recommended conceptual minimum; liveness/policy conditional |

Recommend F, with W=32 as the **one-flight candidate**, not final approved
numerical policy. Do not introduce a new ACK token simply to prove the bound.
Logical report max542 plus four52-byte outer/fragment headers =750 before any
additional secure-link overhead/retries; not a physical airtime measurement.
No guaranteed report rate or overhead/event is invented.

### Critical admission and saturation

Parameter C satisfies0<=C<=W. For uncovered keys retain immutable admission
class; normal admissions require normal charges<W-C and total<W. Critical may
use free total credits; normal cannot use the C reserved credits. P-listed
retries consume no new credits. Do not give critical unlimited bypass: that
recreates the unbounded evidence problem. Persist/rebuild class association
alongside exact evidence. A384-bit classification bitmap48 B can live inside
reserved lifecycle metadata with stable authenticated page/row association;
its relocation/root update must preserve that association. The53-byte dedupe
witness is not on its own sufficient to reconstruct class charges.

C=4 is tested to reflect the existing Node four-slot *nonmotion* reserve, but
also C=1,2,16,32 are tested. None is a final critical burst/rate contract.
Both Node admission and Hub body allocation need aligned critical protection;
Hub credits cannot rescue a critical event refused earlier by a full Node.

Keep physical critical body capacity separate from normal body capacity,
checkpoint/root/control and GC scratch. Let Bc be approved maximal required
critical information, H its authenticated restart context, and Kc the required
simultaneous *still-owned* critical bodies. A conservative sector reserve is
`ceil(Kc/floor((4096-H)/Bc))*4096` (plus lifecycle/COW dependencies).
For source-like HOT124 with H1370,21 records/sector; illustrative8 KiB holds42,
so6*C new reserved arrivals fit only if C<=7 and reserve was actually free.
Critical-derived effects may differ in size. Critical arrivals beyond a Node's
reserved C may use normal free space, never other Nodes' guaranteed reservations.
A replenished report credit is NOT free flash: a backend-pending critical body
may remain pinned after report retirement. Track capacity separately.
The8 KiB allowance below is therefore a placeholder, not a derived product
critical guarantee. No unlimited critical history guarantee is possible.

At exhausted normal credits/space: no false ACK, keep Node retained exact event,
service report/control, continue independent sensing/local alerts, materialize
only inputs with proven replay/effect handling. Low-value detail may be coalesced
only before immutable identity or through approved lossless/semantic substitution;
do not mutate a previously ACKed immutable event. Missing/unavailable input
reduces coverage: NO_OBSERVATION, never invented NO_ACTIVITY. Surface degradation
through bounded reserved status state when available. If critical reserve also
fills, signal/report fault, preserve retained critical information and do not ACK
undurable input. That fail-closed refusal alone does not satisfy indefinite
local-safety operation: approved incident/aggregation/overflow behavior is required.

**REQUIREMENT_GAP:** final critical classes/C/Kc, saturation effects and Node
priority mapping; finite-outage/full-detail guarantee and allowed backend
substitution; safe local learning/alerts when new immutable input cannot be
admitted. This policy branch stops here. Larger flash postpones saturation but
cannot resolve an unlimited-stream contradiction.

## B. Representation by lifecycle owner

| State | Smallest safe candidate; no forced conversion |
|---|---|
| Local replay or backend pending | Complete lossless compressed body with original received time/config/source binding; one canonical body shared by owners |
| Dedupe still needed; backend/replay/history complete | Keep smaller context-pinned body or53-byte exact key+full HMAC certificate (55 framed), accounting for marginal context pin cost |
| Report proves covered absence but backend pending | Release exact dedupe row, retain complete backend body/reference |
| Backend accepted with durable matching local receipt | Release backend owner only; keep dedupe/replay/history owners independently |
| All body owners complete; report still pending | Exact key AND payload binding; key-only is insufficient for changed-payload conflict |
| Selected report proves absence; all owners complete | No per-event record; report covered-complement certificate suffices; erase only after all root references released |

Typical HOT36 and WARM15–16 are smaller than55 framed certificates; maximum
HOT124 saves69 with a certificate. Physical NVS separate blob HOT36=128 entry
bytes and certificate53=128, so no small-object entry saving there. HOT124=192
versus witness53=128 saves64 entry bytes. References do not replace source data
until corresponding owner/manifest lifetimes are proven. Backend reference
without authenticated durable COMMITTED is not permission to drop a body.
Original retry/conflict digest projection and outer journal key-only duplicate
boundary remain OPEN from the previous investigation; no adjacent product fix.

## C. Real NVS physical access pattern

Installed ESP-IDF6.0.3 at `/home/udaybhan/.espressif/v6.0.3/esp-idf`, source commit
`76f5dedd9950a3012fee8fb7d5586df21fc67802`. Audited:
`components/nvs_flash/private_include/nvs_constants.h`, `src/nvs_types.hpp`,
`src/nvs_storage.cpp::writeMultiPageBlob`, `src/nvs_page.cpp`, and
`src/nvs_pagemanager.cpp::requestNewPage`.

Sector4096 =header32 +entry-state bitmap32 +126 entries*32. Each entry header
contains namespace/type/span/chunk4, CRC4, key16, value/blob metadata8. Short
keys<=15 bytes live in that header, no separate string allocation per data entry.
BLOB_IDX one entry; each BLOB_DATA chunk one header and32-byte padded data;
chunk maximum4000. Namespace one entry. Best-layout entry count for nonempty
value B: `ceil(B/32)+ceil(B/4000)+1`. Tail fragmentation/splitting adds headers
and padding, plus obsolete/torn entry space. The runtime moves live items before
erasing and keeps a free page; fully live pages cannot produce free capacity.
NVS CRC is not authenticated application ownership/replay protection. Preserve
application AEAD; existing security/key provisioning is not removed.

| Object | Logical B | Minimum entries /entry bytes | Occupancy ratio |
|---|---:|---:|---:|
| Small WARM as standalone blob |16|3 /96|6.0000|
| Backend receipt |32|3 /96|3.0000|
| Typical HOT |36|4 /128|3.5556|
| Certificate |53|4 /128|2.4151|
| Maximum HOT |124|6 /192|1.5484|
| Numeric authenticated context |404|15 /480|1.1881|
| Candidate full-manifest root |512|18 /576|1.1250|
| Six-owner retirement bank |3485|111 /3552|1.0192|
| Certificate block64+73*55 |4079|131 /4192|1.0277|
| Whole independently restarted segment |4096|131 /4192|1.0234|
| Checkpoint bank |6144|195 /6240|1.0156|

These exact-derived entry minima exclude allocated-page slack/GC. Blob chunking
depends on write order; the official generator below measured three extra
entries for this complete image, not the theoretical lower bound exactly.
Keys/padding/namespace/page overhead are included in the generator binary.
It writes dummy length-matched values, not real source/crypto manifests.

### Whole128 KiB NVS mapping (conditional, global pooling)

Map immutable packed certificate/event segments as blobs. New durable HOT
records cannot wait for a batch: either separate small committed tail objects,
or a costly replacement of a packed blob. Batch COW promotion may temporarily
keep tail plus packed body, releasing old copies only after new root selection.
A sealed WARM segment may authenticate context+all records together; HOT
individual ACK-required commits still need durable independent evidence.
No production access-pattern change in this run.

| Fixed objects/reserve | Logical B /count | Minimum entries | Raw sector-isolated bytes |
|---|---:|---:|---:|
| Exact witnesses worst all-certificate |4079*6|786|24576 (438 slots for384 live) |
| Selected/previous/candidate report banks |3485*3|333|12288 |
| State/day/checkpoint banks, three COW images |6144*3|585|24576 |
| Two full-manifest root values |512*2|36|8192 |
| Lifecycle/extent/class/completion metadata |4096*2|262|8192 |
| Critical placeholder values/reserved space |4096*2|262|8192 |
| Namespace |one entry|1|shared authenticated ownership domain |
| GC/COW |three4096 pages|not occupied values|12288 |
| Engineering |one4096 page|not occupied values|4096 |

NVS fixed logical values70,769 B;2265 minimum entries=72,480 B. Minimum18
allocated pages plus four reserved pages =90,112 B. Those four comprise one
internal NVS free page, **two application COW/GC pages**, and one engineering
page; do not add another internal free page. Application coexistence (three
state/report banks, two roots) is already in fixed objects. Whether two extra
application pages suffice for all simultaneous promotions/torn tails is OPEN.
The separate8 KiB lifecycle metadata must also bound completion/class churn.

Shared event/backlog/history/daily pool has no second payload copy. Each complete
4096-byte segment costs at least131 entries. Up to nine segments fit the
optimistic whole partition: `ceil((2265+9*131)/126)+4=32` sectors. Ten need33.
Report `NVS_FIXED_BYTES=90112`, incremental physical variable allocation40960,
free0, total131072; nine logical4096 segments =36,864 B (NOT40,960 logical).
Global rounding means incremental allocation cannot be assigned as isolated
page windows. The four reserved pages are inside fixed90112, not event capacity.

Official `esp_idf_nvs_partition_gen` V2 in the installed IDF Python environment:

| Event segments | Minimum image sectors including one free | Written entries | Add application/engineering sectors | Total /margin |
|---:|---:|---:|---:|---:|
|7|27 (26 allocated)|3185 vs3182 lower bound|3|122880 /8192 |
|8|28 (27 allocated)|3316 vs3313 lower bound|3|126976 /4096 |
|9|29 (28 allocated)|3447 vs3444 lower bound|3|131072 /0 |

One smaller tested image fails capacity for each row. Full raw objects and
NVS objects are now compared, not raw fixed bytes plus isolated NVS event tax.
This supersedes that earlier tax-only estimate for **whole fresh layout**, while
preserving its isolated-window facts. Fresh packing is not dynamic allocator
proof: application HOT tails, replaced blob versions, dirty pages and shared
scratch may invalidate these margins. No lower bound proves runtime feasibility.

Whole fixed allocation ratio90112/70769=1.2733;4096 blob entry ratio1.0234;
whole fresh9-segment occupancy ratio131072/(70769+36864)=1.2178. These are
occupancy ratios, **not physical flash write amplification**. Per-event NVS
objects are poor density; full-blob rewrites per event are poor wear. Both need
measured tail/batch/GC policy before backend selection.

## D. Raw sector candidate and host proof

Raw fixed102400 +seven shared4096 sectors28672 =131072, free0. This conservative
mapping charges every checkpoint child an independently erasable8192-byte bank.
The previous five-sector18432-byte arena remains possible only with a proved
shared-extent release/GC schedule; do not count it as sector-isolated.
No separate full-body reservation: active/replay/outbox/history bodies share
seven sectors, not zero bodies required. Exact witnesses can share body binding
while the body remains; the all-certificate reserve is conservative. Allowing
bodies to borrow unused certificate/state reserve needs a peak allocator proof.

Each data sector has frozen independently restarted context. Numeric header/
auth envelope404; full-source sample/max728/1370 including dictionary/config
and envelope estimates. No NVS32-byte entry tax. HOT envelope is aligned
`plain+2 length+16 GCM tag+4 commit`,22..25 bytes overhead depending padding;
median36, max124. WARM length2 per entry and a sealed authenticated context/block
(the block cannot be acknowledged incrementally just because it is smaller).
Raw variable bytes28672; after seven sample/max contexts23,576/19,082 B remain
for framed entries/daily objects/padding. Sector headers already included in that
pool; don't add context again to fixed metadata. Source-string serialization is
still proposed, not qualified by the numeric fixture.

Host `rawflash_model.hpp` uses two full4096-byte data sectors and two full4096
root sectors, fixed media16,384 B. Frozen numeric context388 with16-byte GCM tag;
clear36-byte discovery prefix authenticated, encrypted352-byte rows/CRC. Derived
nonce synthetic64-bit external segment serial +32-bit position; header position
UINT32_MAX; distinct synthetic root key. Record AAD binds complete authenticated
context, physical offset, length; tag before4-byte commit, zero padding. Root
68 bytes:48-byte authenticated manifest fields +16 tag +4 commit; fields are
magic/schema/child, generation, segment serial, extent/count, epoch/domain.
The full partition budget provisions512-byte manifest roots, not this one-child
fixture size. No new codec or real key/nonce allocator.

Sequence: blank destination/root required ->live copy under new serial or
append beyond selected extent ->new authenticated root complete/readback ->
monotonically invalidate old root commit marker ->erase old root4096 ->erase
old child4096 if GC ->verify blank before reuse. Selected root is never mutated
in place. The old-root marker release is safe only after the new root is
validated; it prevents a partly erased old header looking committed/corrupt.

| Crash cut | Recovery |
|---|---|
| Destination erase/context/copy or append torn | Old complete selected extent; torn tail is never reused with the same nonce |
| New root partial | Old root; no new ACK eligibility |
| New root complete before old release | New complete child; old root still pins source until released |
| Old marker release/root erase partial | New complete child/root; do not erase selected child |
| Old child erase partial | New root only; no source references; blank-check/re-erase before reuse |
| Recovery cleanup crashes again | Re-select valid authority; repeat unselected root/child cleanup idempotently |
| Selected child/context/record tag corrupt | Fail closed; do not fall back to older state losing ACKed events |

4,197 append/root cuts +12,821 GC/root/sector-erase cuts =17,018; all old/new
selected identities and payloads correct. Another144 sampled second-crash
cleanup cuts (18 first-cut samples*8 cleanup cuts) preserve selected state and
finish with reusable unselected sectors. Sixty-four successful alternating GC
lifetimes reuse fixed media. Context/cipher/root-tag tampering and wrong serial
fail closed. Existing frozen density million/index regression remains separate.

**HOST-MODELED, not full crash proof:** deterministic prefix erase, not every
physical brownout bit pattern; external unique serial reservation; synthetic
keys; numeric source context only; single selected extent, no full multi-owner
manifest; whole-sector root rotation per model transaction is deliberately
inefficient; fixed model event arrays are not a target RAM budget. Recovery may
scan at most four sectors in this fixture (distinct address coverage16,384 B);
production32-sector boot inventory bounds distinct flash coverage131072 with
bounded record count, but target read-buffer/I/O counts remain to measure.
Common runtime retrieval can use the existing bounded exact index (384-row
packed key/handle index11,652 B), pending bitsets/segment queues and per-owner
report state; no normal full-partition scan.

Authentication alone cannot distinguish a fully valid old root replay from
rollback or loss of a newer committed root marker. Root freshness/replay fence,
nonce reservation across torn append/erase/reboot, real flash program alignment,
interrupt/resume, full allocator and FOTA/rollback compatibility remain OPEN.
Never reuse a torn append tail/serial just because the selected older root has a
shorter extent. The fixture cleanup frees unselected sectors; it does not supply
nonce freshness or validate every arbitrary corrupted root-loss case.

### NVS versus raw backend decision

| Dimension | NVS | Raw segment candidate |
|---|---|---|
| Fresh capacity in conditional map | Nine event segments via pooled entries | Seven with independently erased three-bank state; shared arena could improve |
| Writes | Small HOT blob overhead; batched COW; frequent whole-blob replacement costly | Sequential HOT append; sealed WARM; metadata/root journal still required |
| RAM/retrieval | NVS internal page/hash RAM plus same bounded application index; target peak unmeasured | Fixed sector/read/reclaim buffers plus same index; target peak unmeasured |
| Boot/recovery | Mature entry/CRC/GC recovery plus application auth roots; application rebuild bounded | Must own complete authenticated scan/root/erase/recovery; model incomplete |
| Security | Keep app AEAD/domain/version; NVS CRC/encryption alone insufficient | Every domain/context/position/nonce/freshness responsibility explicit |
| Wear | IDF GC moves live entries; hot application roots/checkpoints still matter | Can avoid NVS entry tax but bad root/GC design wears rapidly |
| FOTA/schema | App mixed-format/rollback barrier still required | Same, plus new raw driver/format migration; old firmware cannot read it |
| Diagnostics/maintenance | Existing adapter familiarity and SDK tooling | More custom recovery/inspection/support code and target qualification |

RECOMMENDED_STORAGE_BACKEND=UNDECIDED. Retain current production NVS; prototype
its **runtime** tail/sealed-segment access pattern next without integration.
Select raw only if measured occupancy/wear/peak bounds materially beat efficient
NVS and authenticated freshness/reclaim/rollback complexity is acceptable.
This run does not prove that threshold or authorize migration.

## E. Retention and72h comparison

Frozen synthetic scenarios384/1776/23232 source events/day; PIR episodes, not
raw edges. Sample/max full names,20ms timing variation, one300+2-byte daily
entry/day, independent restarts. Names/context/header/padding and fixed budgets
are charged. No new critical/ancillary effects, config churn or clinical guarantee.

| Rate | Raw seven-sector sample /max records and hours | Optimistic NVS nine-segment sample /max records and hours |
|---|---|---|
|NORMAL384|1281 /1056;80.0625 /66 h (3.335938 /2.75 d)|1649 /1353;103.0625 /84.5625 h (4.294271 /3.523438 d)|
|HIGH1776|1347 /1103;18.202703 /14.905405 h|1740 /1419;23.513514 /19.175676 h|
|STRESS23232|1457 /1181;1.505165 /1.220041 h|1877 /1520;1.939050 /1.570248 h|

NVS capacities above count sealed WARM values, not transient HOT/tail coexistence
or proved runtime retained-history capacity. Neither model supports a product
retention promise. Compacted retention remains UNDEFINED without backend summary/
daily substitution and offline/critical policy; finite bounded routine statistics
are not permission to discard unsynced meaningful information.

72h NORMAL =1152 sources +three daily entries:

| Names | Frozen required event sectors | NVS whole fresh total /margin | Raw sector-isolated total /margin |
|---|---:|---:|---:|
|Sample|7|122880 /+8192; conditional fits|131072 /0; conditional fits |
|Maximum|8|126976 /+4096; conditional fits|135168 /−4096; does not fit this map |

The official generator verifies NVS fresh allocation for these payload lengths.
Do not headline uniform/no-name traces or promise72h production behavior.
The raw max-name miss is not evidence R1 needs a larger partition:72h isn't a
locked requirement, NVS fresh map fits, and safe sharing/owner release is open.
Minimum partition UNDETERMINED; no enlargement proved necessary. Therefore no
192/256 KiB minimum is derived and no384 KiB layout revisited.

Worst simultaneous192 maximum124-byte HOT bodies with1370 context require
10 sectors40,960 B, beyond both conservative shared raw seven sectors and NVS
nine sealed-segment allowance before old outbox/days. Body/witness ownership
may free/borrow reserved sectors, but that must be proved. The key bound384
alone never proves full-body admission. Backend outage bodies have no finite
outage-independent required count without approved overflow/substitution.

## F. Pressure and flash wear

Use admission/ownership boundaries, not invented percentages:

| State /derived trigger | Behavior |
|---|---|
| NORMAL: new normal transaction plus all protected peaks fits | Commit before ACK; continuously upload; periodic bounded state checkpoint; diagnostic ring bounded |
| PRESSURE: next normal append needs owner release/GC or approaches W-C | Reclaim synced/unneeded history/debug; schedule report and cloud progress; only approved semantic aging; protect door/daily inputs until policy defines substitution |
| CRITICAL_PRESSURE: normal admission would consume reserved critical/control/GC space or credits | Refuse that new durable normal ACK; keep retained keys, service report/control and critical reservations; health/state bounded; daily/current learning obligations stay protected |
| SATURATED: even critical or mandatory state transaction cannot fit | No false ACK/overwrite; retain originals; surface fault/degraded observation; critical overflow/local safety behavior is REQUIREMENT_GAP, not an approved operating mode |

NodeHealth is unsequenced; current values/coverage transitions can use bounded
state, not append every health frame. Door/check-in meaningful events and daily
aggregates are not silently downgraded. Pending backend items survive timeout/
server durable acceptance with response lost, and report pruning cannot erase
that owner. No internet/cloud availability requirement for local operation.

No measured whole-engine write amplification or erase lifetime claim. NVS
entry occupancy is not WA. Illustrative typical36-byte HOT standalone blob
programs at least128 entry bytes, plus bitmap/page/churn; RAW HOT36 without roots
programs36 (including record tag/commit). NORMAL/HIGH/STRESS entry lower bounds
49,152/227,328/2,973,696 B/day; raw HOT36 examples13,824/63,936/836,352 B/day.
These use a typical record for sensitivity, not actual trace means or predictions.
NVS replacing a4096-byte segment each event writes>=4192 entry bytes per event:
1,609,728/7,444,992/97,388,544 B/day before GC; reject this access pattern absent
strong justification. Independently committed HOT tail +batch promotion avoids
that particular rewrite, but its coexistence peak is unproved.

Raw fixture adds68 root program bytes and one4096 root erase per append;
NORMAL/HIGH/STRESS would imply384/1776/23232 root erases/day, unacceptable as an
unqualified production strategy. It is a crash-ordering fixture, not recommended
engine. A bounded append-root journal/authoritative authenticated append inventory
must amortize root-sector erases; do not treat68 bytes as a qualified root budget.
Checkpoint/report writes occur on selected report/state cadence, not every
normal event; actual checkpoint replay-tail/day guarantees remain OPEN. Need
measure selected report frequency, checkpoint bytes/cadence, root rotations,
GC live fraction f and copied bytes. Ideal copy factor1/(1-f); no finite bound
as f approaches1. Infinite lost reports/full live victims cannot be fixed by GC.
No flash endurance rating is invented; target erase counters and wear distribution
must establish hot root/state/report sectors and actual write amplification.

## Validation, artifacts and next gate

Added only `host/storage/admission_model.hpp`, `host/storage/rawflash_model.hpp`,
`host/storage/nvs_physical_probe.py`, dedicated C++ admission/raw/sizing tests
and Make targets; no default firmware target change. Tests are bounded arrays,
no event-age growth. Admission model RAM37,384 B (copied ledger snapshots are
explicit atomic-model assumptions), not proposed target RAM. Million events
peak139;6-Node exact bound384 saturated separately. Raw fixed media16,384 B;
OpenSSL internal allocation outside target/portable hot-path guarantees.

Reproduction from code project:

```sh
make storage-admission-host-test storage-rawflash-host-test storage-physical-sizing
make storage-lifecycle-host-test storage-density-host-test hub-backend-commit-host-test hub-journal-persistence-host-test
python3 host/storage/nvs_physical_probe.py --idf-python /home/udaybhan/.espressif/python_env/idf6.0_py3.14_env/bin/python
```

Preserved [regressions](R1_STORAGE_ADMISSION_RAWFLASH_REGRESSIONS_20261007.log),
[final raw/sizing results](R1_STORAGE_ADMISSION_RAWFLASH_SIZING_20261007.log),
[NVS fresh-image probe](R1_STORAGE_ADMISSION_NVS_PHYSICAL_20261007.log), and
[sanitizers](R1_STORAGE_ADMISSION_RAWFLASH_SANITIZERS_20261007.log). All processes
exit0. ASan/UBSan cover new admission and raw fixtures; LeakSanitizer disabled
(`detect_leaks=0`), no physical qualification. Raw sanitizer repeated only after
adding interrupted-recovery cleanup tests; passed admission run preserved.
Existing lifecycle/density million fixtures, source-backend completion and
current journal reboot/tamper/writefault regressions PASS. Codecs unchanged.
Final static/path/diff/preflight validation is recorded in closeout.

Prior target evidence unchanged: app1,864,624 B, existing OTA slot1,966,080,
margin101,456. DRAM static45,783, linker remaining134,953; IRAM87,359 remaining
43,713. Runtime RAM/stack/Wi-Fi/crypto peak and new allocator code growth are
not measured; current4 MB storage CONDITIONAL, current image OTA fits, hardware
upgrade not proven required. No new target build in this host-only run.

Next focused technical step: efficient NVS **runtime** on an emulated flash
partition using actual IDF storage/GC, including HOT tails +sealed promotion,
checkpoint/report/root replacement peaks, repeated brownouts/recovery and
full-live progress. In parallel obtain explicit product critical/offline/
substitution decisions, then prove authenticated credit/root/nonce/freshness/
rollback integration before touching production.

Production readiness NO. STOP gates: final W/C/classification and report fairness;
six-owner/enrollment/epoch authority; immutable-source conflict/retry projection;
critical overflow/offline/backlog substitution; complete routine/day/coverage/time
recovery; actual NVS/runtime or raw full-owner allocator peak and forward
progress; root freshness/nonce/antirollback/FOTA and target RAM/code/wear.
No new LOCKED requirement or CONTEXT_VERSION change.

Final closeout: preflight PASS local/canonical2026-10-07.003; 33 documentation links and static byte sums PASS; tracked git diff --check and all11 new-file whitespace checks PASS. Frozen codec/fixture, production firmware/backend and CONTEXT_VERSION diffs empty.17 files changed/added (host model/tests/Make targets, documentation and logs only); work remains uncommitted for review. No user-authorized commit was requested in this run.
