# R1 retirement and reclamation proof checkpoint — 2026-10-07

Status: ANALYSIS + HOST-MODELED; production integration **NO**. Context preflight
PASS at `2026-10-07.003`; starting HEAD `1f44e78542b8d23ca7200f7d8dc928828019a82e`.
The worktree started clean. Density codec commit `74c4b99` is frozen; no codec,
partition, firmware, backend/PWA, hardware or BAT-C8 change. No new locked
requirement, context bump, canonical promotion or retention promise.

## Conclusion and evidence scope

**PROVEN from source:** six supported Nodes have at most 32 sequenced pending
messages each: 192 simultaneously retryable Node keys. This does **not** bound
unreported, previously ACKed Hub keys, backend-pending bodies, or historical
journal occupancy. Event/report ACKs are independent. Current production still
retains 128 archive events and rejects 129; that cap is an implementation
failure boundary, not a safe required-capacity bound.

**DERIVED:** a complete selected pending-set report safely replaces individual
retired keys with its authenticated covered-universe complement. Sequence gaps
need no additional retired-gap list. **No finite supported-lifetime bound is
proven for current Hub exact evidence** because arbitrarily many event ACKs can
succeed while reports fail. Finite integer exhaustion is a fail-closed stop,
not an indefinite-operating capacity guarantee.

**HOST-MODELED:** an explicitly hypothetical admission gate of at most 32 new
uncovered keys per Node yields 384 live exact entries. Its million-event fixed
ledger run and 4,325 byte-cut COW tests pass. Neither the admission gate nor its
flash persistence is production implemented/approved. Admission backpressure
alone cannot close product safety-under-pressure policy.

**OPEN:** full authenticated allocator/root/nonce/erase/rollback proof,
immutable-source retry digest projection, complete backend-derived completion,
critical saturation/offline policy and simultaneous peak capacity. Existing
128 KiB remains CONDITIONAL. No partition enlargement is proven necessary.

## Source map and actual facts

Paths below are relative to
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/` unless stated otherwise.

| Source | Relevant fact |
|---|---|
| `firmware/node/runtime/node_runtime.hpp` | Default journal and transmit capacities both32 |
| `firmware/node/runtime/node_runtime.cpp::record/acknowledge/restore_recovery` | Allocate sequence before admission (gaps possible); enqueue preflight; ACK removes exact pending key; boot restores old keys under fresh origin; counters fail closed before wrap |
| `firmware/node/components/storage/node_recovery_persistence.cpp` | `kMaximumEvents=32`; encrypted recovery validates pending/retained bounds and correspondence |
| `firmware/node/target/esp32c3/node_runtime_adapter.cpp` | Default NodeRuntime composition; verified recovery saved before transmit and after pending-set ACK changes; save failure stops owner; retirement fragments/retry use separate report ACK |
| `firmware/common/transport/node_retirement_protocol.hpp/.cpp` | Pending cap32; complete sorted key list; report30+16N<=542; authenticated fragments; epoch/generation/HMAC ACK |
| `firmware/hub/components/storage/node_retirement_snapshot.cpp` | Selected report validation, no resurrection of covered absent keys; exact key/digest classification; prune only covered absent keys |
| `firmware/hub/target/esp32/hub_runtime_adapter.cpp` | Authenticate/resolve real registry owner; prepare report bank, checkpoint-select/readback then report ACK |
| `firmware/hub/components/storage/durable_transition.cpp::commit/recover` | Exact digest evidence/tail and report references are recovered/validated; same-key changed digest conflicts at this component boundary |
| `firmware/hub/components/storage/durable_journal_slot_store.cpp` | Native event digest currently HMACs full HubJournal encoded payload, including Hub received_at; archives immutable; two checkpoint rotations preserve references |
| `firmware/hub/components/storage/journal.cpp::commit` | Early Duplicate is key-only (`ids_`); skips candidate payload comparison; attach restores all records and completion receipts |
| `firmware/hub/components/cloud/cloud_sync.cpp` | Only authenticated matching COMMITTED reply persists completion; transport ACK/timeouts not completion; no production target caller established |
| `backend/ghar_sajag/durable_commit.py` | Household+full EventKey idempotent transaction; canonical payload SHA256 conflict; event/incident/notification outbox committed before COMMITTED |
| `firmware/hub/target/esp32/nvs_durable_blob_store.cpp` | `gs_journal/events`, mapped short keys, nvs_set_blob/commit/readback, exact conditional scratch erase; no log-slot recycling |

The supporting [retirement protocol](../../design/NODE_RETIREMENT_REPORT_PROTOCOL.md)
is partly stale: its opening/closing statements that target report adapters are
not implemented conflict with actual target source; its128-global admission cap
is a current implementation fact, not a lifetime proof. Its complete-set logic
remains useful; do not infer a tighter per-Node historical Hub bound from queue
capacity alone. Actual snapshot schema2 has sparse registry coordinates and up
to10 slots; this analysis's six-owner future budget requires enforcement of six
active source admission or rederivation for ten. No old ownership generation is
silently discarded to fit that limit.

Adjacent issue triage (analysis only): `BUG_CLASSIFICATION=INVESTIGATE_ONLY`;
`REQUIREMENT_SOURCE=docs/design/NODE_RETIREMENT_REPORT_PROTOCOL.md` plus R1
non-negotiable conflict/dedupe requirements; `DECISION_IDS=GS-D016,GS-D024`;
`TASK_SCOPE=lifecycle proof, no integration`; `OUT_OF_SCOPE=production duplicate
path repair`. The source shows two different boundaries: durable component
compares digests, outer journal returns Duplicate by key before comparison.
Also the native digest includes mutable Hub receive time while the proposed
source digest must exclude it. Do not claim certificate compatibility or a
production same-key payload-conflict proof until ingest/retry normalization is
traced and qualified. No product change is made here.

## Lifecycle: order, ownership and retry

These states are independent flags/owners, not a single mandatory total order:
backend acceptance can precede Node ACK arrival; Node retirement can precede
backend completion. A selected durable event + unapplied effect tail may make
ACK eligible; the tail must guarantee exactly-once recovered local application.
If that guarantee is absent, checkpoint the effect before ACK.

| Transition | Preconditions and persistent evidence | Retry/duplicate, crash and recovery |
|---|---|---|
| NODE_CREATED→NODE_RETAINED | Fresh nonwrapping key; room in bounded queue; verified encrypted Node snapshot containing immutable message and report projection | Before save no send; failed/ambiguous save stops owner; recover old or complete new snapshot |
| NODE_RETAINED→HUB_RECEIVED | Authenticated current owner/epoch/transport; old origin permitted under valid ownership | Node retries same retained key; untrusted frame never changes Hub state |
| HUB_RECEIVED→HUB_DURABLE | Commit/readback body or complete lossless information, binding, retry digest and replay obligation under authoritative root/append inventory | Before commit no durable ACK; after commit/power cut Node retries and receives duplicate ACK without effects |
| HUB_DURABLE→NODE_ACKED | Application ACK authenticated for exact key; Node saves exact removal before absence report | Lost ACK leaves retained message; lost removal save restores retry; report cannot claim RAM-only removal |
| HUB_DURABLE→LOCAL_EFFECT_APPLIED | Deterministic reducer/routine input/config/time mapping; applied ordinal/materialized state atomically selected with residual replay tail | RAM-only apply is provisional; reboot replays only events beyond selected applied ordinal; no double effect |
| LOCAL_EFFECT_APPLIED→BACKEND_PENDING | Canonical body serves backend owner; no duplicate body required; durable pending inventory survives reboot | Upload near-real-time when connected; never wait for PWA or pressure |
| BACKEND_PENDING→BACKEND_DURABLY_ACCEPTED | Server authenticates client and commits exact source identity/payload and required effects | Timeout/response loss indistinguishable from no acceptance: retain original retry payload; retry same key and original Hub timestamps |
| Backend accepted→local completion known | Authenticated matching COMMITTED response plus durable local receipt selected/read back | Before local receipt, repeat submission; after receipt, recover completed; PUBACK or request-sent flag insufficient |
| NODE_ACKED→NODE_RETIREMENT_CONFIRMED | New verified complete report excludes key inside covered universe; snapshot+index selected, all recovery roots protected | Lost report/report ACK cannot authorize guessed retirement; listed holes still retryable; late covered absent frame is Stale, never applied |
| BODY_REPLACEABLE→CERTIFICATE_ONLY | No backend/detail/history/replay/config-dependent owner needs body; local effect materialized; full canonical source digest projection validated; certificate and required owner map committed before source release | New certificate+root validated first; power cut leaves old body or selected certificate; certificate retry uses full exact key and32-byte HMAC |
| CERTIFICATE_ONLY→RECLAIMABLE | Selected authenticated report proves covered absence, or durable revocation prevents old owner authentication; both recovery roots/rollback understand that proof | Remove exact witness only after proof selected; no highest-sequence-only rule; stale old frames cannot resurrect |
| RECLAIMABLE→ERASE_ALLOWED | All selected/recoverable roots and inventories no longer reference victim; all surviving child manifests validated; no backend/routine/history owner left | Erase only unreferenced victim; interruption invalidates free-page status; verify blank/re-erase before reuse with new unique generation/nonce |

NODE_ACK != BACKEND_ACK != REPORT_ACK. Deleting an exact witness on report
progress does not delete a body with a pending backend owner; deleting a body
on backend completion does not delete still-required retry evidence.

## Bounds: what is and is not finite

Let P_i be the latest durably reported pending set, |P_i|<=32. Let U_i be
committed keys outside that report's covered universe. Report coverage is all
older origins, plus sequence<=H in the current origin. It is **not** all
sequence<=highest received event.

Current protocol bounds instantaneous Node pending to6×32=192. Six full queues,
ACK loss, radio interruption, reboot/rejoin, out-of-order/duplicate retries and
session changes do not multiply pending keys: recovery preserves their original
identity and queue cap. At most32 older pending origins plus one current origin
per Node; a transport rejoin does not itself close an allocation origin.
Skipped sequences never transmitted need no exact key or gap ledger.

Counterexample: choose one Node with pending capacity1. For event k, durably
retain, send, Hub commit, Node receives ACK, saves removal. Drop every retirement
report. Repeat. Node pending<=1, Hub unresolved exact history=k. Events can be
cloud-complete and locally applied. Without report proof the Hub cannot assume
absence or distinguish a legitimate pending old retry from a revoked key.
Current128 cap merely stops the run; it does not prove128 correct capacity.
Host counterexample runs100,000 repetitions. Event ACK availability is not a
proof of report delivery.

Thus current **MAX_EXACT_KEYS_REQUIRED=NO_PROTOCOL_FINITE_LIFETIME_BOUND**;
**MAX_CERTIFICATES_REQUIRED=no finite safe bound**; full bodies needed by
unbounded unsynced backend detail likewise have no finite duration-independent
bound. Routine state being bounded does not prove outbox boundedness. Locked
bounded-backlog/local-safety requirements need the separately approved overflow
information contract; stop that branch at REQUIREMENT_GAP, not guessed loss.

Smallest conceptual finite rule modeled here:

1. Persist per-owner latest complete report and at most32 admissions outside its
   covered universe. Initial owner state requires authenticated baseline (model
   uses session1/highwater0). Charge each *new distinct* unreported key, never
   retries. Admission can continue for report-listed keys without new credits.
2. On selected newer report, remove covered absent exact keys; keep listed keys
   and uncovered admissions. Credits are32 minus surviving uncovered admissions,
   **not blindly32 after any report-generation change**.
3. Recover report, evidence and spent-credit invariant together. Reboot/rejoin,
   duplicate report, storage epoch or new transport session must not refill
   credits. Enrollment change needs separately proven durable revocation and
   source/outbox ownership. No counter wraps.

Then exact live keys E_i⊆P_i∪U_i, |E_i|<=64; six owners<=384. The witness
margin32 in earlier416 is a transient COW batch, **not32 additional live keys or
full bodies**. New+old physical copies coexist in GC reserve. This is a
conditional protocol invariant, not current product integration proof. A stalled
report channel eventually blocks new uncovered admissions: must establish
bounded/fair report progress, safe critical admission under failure, or explicit
approved fail-safe/pressure semantics before adopting it. Reserving credits for
critical classes is itself product policy, not resolved here.

Exception/gap entries: zero **additional** retired-gap entries under this
complete-set design; up to192 listed pending exceptions are already inside
reports, not an extra192-key flash allocation. Without complete reports, a
contiguous floor plus retired exceptions can grow indefinitely behind one
permanently missing key. A lost report preserves older complete evidence; a
superseding complete report is sufficient without receiving every generation.

Full active bodies are separate from these counts. Dedupe alone requires zero
full bodies once a safe witness/report is selected. Worst all192 new Node
messages during backend outage require192 source bodies until another lossless
owner representation exists. Total bodies = union(local replay, backend pending,
required history), not sum of three copies, and can exceed192 as ACKed events
accumulate. No unconditional192 maximum full-body requirement is proved.
Materialized-state replay-tail cadence32 is still proposed, not a proven global
body bound; the model does not implement reducer/coverage/day recovery.

## Exact certificate comparison

Proposed dedupe-only witness, within independently authenticated/versioned pages:

| Offset | Field | Bytes | Why |
|---:|---|---:|---|
|0|owner registry slot|1|Exact immutable selected owner map; not a device fingerprint|
|1|enrollment generation|4|Replacement isolation; nonwrapping|
|5|origin session|8|Old retained sessions preserved|
|13|sequence|8|Exact sparse identity|
|21|full canonical immutable-source HMAC-SHA256|32|Same key/different immutable payload conflict|
|**Total**|||**53**|

Epoch/key domain/schema/page generation/integrity are shared at authenticated
page/root level, not omitted globally. Retirement status is the selected
report predicate; no per-witness boolean required. Canonical projection must
bind physical/logical owner, event kind/location, immutable Node fields and
payload; excludes fresh Hub reception/radio/time reinterpretation. Registry
mapping must outlive every witness and pending body; reject reuse before durable
revocation. The model uses mock digests to test exact comparison, not cryptography.

The earlier65-byte witness added assignment4 and original received_at8 for
reconstructing retry/effects. Removing these12 is safe **only after all such body
owners finish**; a53-byte witness is not a backend retry payload. Current native
HMAC projection is not yet this source projection. No digest truncated.

Frozen entry estimates: raw body median13 B; HOT median36 B /max124 B; WARM
median15–16 B /max103 B, excluding independent full-source context728/1370 B.
53-byte certificate plus2 framing=55 B: saving vs124-byte worst HOT entry69 B;
vs36-byte typical HOT entry **−19 B**; vs103-byte worst WARM48 B; vs16-byte
WARM **−39 B**. Actual same-field source sample101/121 B payload and native
archive overhead are different representations. Prefer retaining the smaller
complete compressed entry while dedupe-only if its context is safely pinned;
certificate conversion is an ownership optimization, not universal compression.
No codec changes. No416-full-body reservation retained in the new sensitivity.

## Backend boundary

Existing source-event contract identity: household + physical ID + logical ID +
origin session + sequence; server commits immutable canonical-payload binding
and required event/incident/notification-outbox transaction. Local completion
requires authenticated matching COMMITTED and durable selected receipt. Server
acceptance plus response lost means Hub reuses original source information;
server idempotency returns prior result instead of duplicate caregiver history.
Reboot without receipt also retries. Partial backlog completion releases only
individually receipted information. Node duplicate never creates a new backend
identity. No exactly-once transport assumption.

`BACKEND_COMPLETION_PROOF=HOST_PROVEN_SOURCE_CONTRACT_ONLY`; production caller,
derived alerts/activity effects/daily aggregate revisions, replacement of
unsynced detail by aggregate and retry-time reconstruction remain OPEN.
`BACKEND_COMPLETION_BOUND=NO_FINITE_OUTAGE_INDEPENDENT_BODY_BOUND`. Never erase
backend-pending bodies solely because a Node report retires them. The53-byte
certificate proves no backend payload equivalence.

## COW/reclamation proof obligations and model

State machine: BODY_ACTIVE → LOCAL_APPLIED + BACKEND_PENDING →
BODY_BACKEND_COMPLETE → CERTIFICATE_ELIGIBLE → CERTIFICATE_COMMITTED →
ROOT_SELECTED → OLD_ROOTS_RELEASED → BODY_ERASE_ALLOWED. Certificate retirement
is a separate report-backed transaction followed by the same root-release and
erase procedure. If report retirement happens first, body may remain backend
pending without a certificate. A GC live copy preserves every logical owner.

| Cut | Required recovery |
|---|---|
|Candidate chosen, no write|Original root/body; candidate designation RAM-only|
|Destination/context/live copy torn|Unselected destination ignored; old source retained|
|Certificate prepared/committed, root not selected|Old source remains authority; verified certificate alone never authorizes erase|
|New root torn before complete validation|Old complete root; no externally claimed durability from torn root|
|New root complete/read back|New selected manifest validates all children and ownership; old references still pin victim|
|Old root retirement interrupted|New root remains authoritative; erase not started until every old recovery reference released|
|Victim erase interrupted|No root references victim; new complete state; victim unusable until verified blank|
|Reboot after erase before free metadata|Recover new root; reconcile/redo free-page erase, no source dereference|
|Backend completion marking interrupted|Old pending body or complete durable receipt; retries never infer completion from send|
|Selected child corrupt|Fail closed; NEVER silently fall back to old root that could omit ACKed events/effects|

The host fixture has two256-byte pages and two32-byte roots; model CRC/footer
acts as deterministic tear detection, **not AEAD or real ESP32 root format**.
It exhaustively cuts864 modeled byte erase/program operations at865 positions
for five transitions: local apply, cloud completion, body→certificate,
certificate→retirement and live-certificate GC copy. Total4,325 cuts. Each
recovers old complete state or new complete state; selected-child tampering and
premature certificate without backend completion fail closed. Model programming
requires1→0, erasure maps bytes to0xff. Root erasure occurs before body erasure.
Stable lifetime identities are assumed; copy generations are distinct.

Model limits: root slots are independent erase units abstracted as32 bytes;
real roots share4096-byte sectors and need journal rotation/scratch. No AEAD,
nonce allocator, word/program atomicity, hardware erase completion, full selected
inventory, root freshness/antirollback fence, interrupted recovery writes,
simultaneous multi-owner extent pins or round-trip flash allocator exists here.
Million-event ledger reboot uses an assumed atomic durable snapshot copy, not a
persistent codec. Backend lost-ACK fixture models ownership flags; real server
uniqueness is checked by existing backend regression. Passing this model closes
an abstract ordering lemma, **not production crash-reclamation proof**.

Required next proof: authenticated manifest/root generation + unique serial
reservation; selected-child inventory and rollback minimum; retire all roots
referencing victim before erase; recovery resumption idempotence; bounded number
of live victims/destinations/roots/report banks across repeated crashes; no GC
that requires unreserved free space; fairness/admission proof. A full-live
partition cannot reclaim useful bytes by copying; progress needs approved owner
retirement or semantic aging. Never reset epoch to hide fullness.

## Real NVS versus raw flash

Audited installed ESP-IDF6.0.3 source commit
`76f5dedd9950a3012fee8fb7d5586df21fc67802`, under
`/home/udaybhan/.espressif/v6.0.3/esp-idf/components/nvs_flash/`:
`private_include/nvs_constants.h`, `src/nvs_storage.cpp::writeMultiPageBlob`,
`src/nvs_page.hpp`, `src/nvs_pagemanager.cpp::requestNewPage`.

NVS sector4096 = page header32 + bitmap32 +126×32-byte entries. New-format
blob index consumes one entry, each BLOB_DATA chunk consumes one header plus
ceil(chunk_bytes/32) data entries; maximum chunk4000 B. Namespace creation costs
one entry; short key names live inside entry metadata, no extra name per data
entry. Required erased/free page supports internal copying; fully live pages
cannot create capacity. Replaced values coexist until obsolete entries/pages
are reclaimed. Extra fragmentation can create additional chunk headers/padding.
App AEAD is already included in logical blob length; NVS doesn't eliminate it.

| Logical value | Best fresh-layout entry bytes | Ratio (not erase/write WA) |
|---|---:|---:|
|32-byte completion receipt|96 (3 entries)|3.0000|
|36-byte HOT entry as separate blob|128|3.5556|
|16-byte WARM entry as separate blob|96|6.0000|
|53-byte witness as separate blob|128|2.4151|
|300-byte daily value|384|1.2800|
|3485-byte measured six-owner snapshot|3552|1.0192|
|4096-byte segment blob|4192 (128 data+2 chunk headers+1 index)|1.0234|
|6144-byte checkpoint blob|6240 (192+2+1 entries)|1.0156|

4096 blob actually needs two chunks; simply charging2+ceil(B/32) undercounts
one header. Seven such blobs need917 entries+one namespace: ceil(918/126)=8
allocated pages plus one free=9 sectors (36,864 B) for28,672 logical bytes,
**1.2857× allocated-window estimate**. Eight need1048+1 entries:9+1=10 pages
(40,960 B) for32,768 logical,1.25×. These are optimistic packing bounds, not
measured NVS allocator peaks. Internal GC scratch may share a separately reserved
free page if proven; do not charge it twice or assume it free. Eight dedicated
NVS sectors with one free and namespace support only six whole4096 blobs in
ideal packing. Tailroom, obsolete versions, headers and fragmentation worsen it.

Raw candidate sector costs already include full independent contexts, AEAD tag,
commit/framing/padding and whole-sector allocation in frozen sizing. Raw storage
has **no NVS entry tax**, but must implement all allocator/crash/nonce/security
responsibilities. Production remains NVS. Raw128 KiB arithmetic cannot be used
to approve an NVS-based128 KiB engine. `PHYSICAL_WRITE_AMPLIFICATION=UNPROVEN`:
entries/occupancy ratios above are not erased/write bytes; actual GC live-copy,
root/checkpoint/report churn, torn-space burn and repeated reboot can dominate.
At live fraction f, ideal copying amplification~1/(1−f); no finite claim without
victim-live/progress bound. Flash endurance and sector hotness remain target gates.

## Conditional rebudget, no finite-bound claim

This is a **DERIVED raw-partition sensitivity**, using the hypothetical credit
bound and safe53-byte dedupe-only projection. It removes the old416-body
reservation; it does not prove all simultaneous owners fit. Every event body
belongs to one shared pool; no separate duplicated backend/history payload.

| Category | Reserved physical bytes | Condition/purpose |
|---|---:|---|
|Full active bodies incremental separate reserve|0|Use shared body pool; NOT claim zero bodies needed|
|Exact certificates|24,576|Six sectors; candidate64-byte authenticated page header +55-byte framed witness:73/sector,438 physical slots;384 live, COW copies in GC reserve|
|Gap exceptions additional|0|Covered complement;192 listed holes already in reports|
|Retirement report generations|12,288|Three sector-sized six-owner snapshots; keep both selected refs +new candidate; actual owner/bank peak proof required|
|Routine/current-day/checkpoint child state|20,480|Previous conditional stateCOW allocation; routine2560/current-day512/coverage208 are inside, not added again|
|Root/checkpoint selectors|8,192|Two root sectors; erase rotation uses scratch, not per-event unbounded roots|
|Segment/lifecycle metadata|8,192|Selected context/extent/binding inventories and completion/report deltas; actual churn upper bound OPEN|
|GC/COW|12,288|Bounded victim/destination/root scratch; max32 extra witness copies staged here|
|Critical reserve|8,192|Prior placeholder, critical rate/overflow REQUIREMENT_GAP; do not assert guarantee|
|Engineering reserve|4,096|Not normal admission space|
|**Fixed**|**98,304**|24 sectors; conditional assumptions above|
|**Shared variable bodies/outbox/history/daily**|**32,768**|8 independent sectors, header/padding charged by sizing|
|**Total**|**131,072**|Exact existing partition|

No separate fixed backend-body bytes: `BACKEND_PENDING_BYTES=SHARED32768`,
not32768 extra. Certificates already in bodies need not be duplicated; the
24 KiB reservation conservatively supports the all-certificate state. Payload
binding can share the original body digest until conversion. A snapshot's
dictionary/registry binding remains pinned until every body/certificate releases
it. Six-entry dictionaries in each body sector are already charged to variable
pool, not also8192 metadata. Daily300+2 framing lives in variable pool;
current-day512 is inside state reserve; checkpoint6144 maximum candidate inside
stateCOW, not a second separate5120/6144 allocation.

Critical correction: full1370 context allows21 worst128-byte cells/sector,42
across8192 B before lifecycle deltas. No approved critical burst/rate determines
this reserve; its earlier32 placeholder is not a derived product guarantee.

Important adverse peak:192 maximal HOT124-byte entries with1370-byte contexts
fit21/sector, need10 sectors=40,960 B **before daily/backend older bodies**,
exceeding the8-sector shared pool by8192. With sample728 header,27/sector,
192 require8 sectors=32,768, no spare for daily or older outbox. These are
explicit supported-field adversarial bounds, not workload guarantees. On-line
completion/rapid local checkpoint could reduce peaks, but an outage cannot be
assumed away. Therefore this ledger is NOT a guaranteed192-body admission proof.
Different reusable raw arena/metadata sharing/reserve assignment needs measured
peak allocator proof, not merely an increased constant or favorable trace.

## Retention sensitivity with frozen codec

No new workload assumption: NORMAL384/day, HIGH1776/day, STRESS23232/day.
PIR coalesced episodes, not electrical edges. Same existing six-source traces,
20ms timing variation, exact sample/max names, and one300+2-byte daily entry per
elapsed day. Header728/1370; unchanged codec independent restarts. Current-day,
root/state/GC/critical costs are in fixed98,304 B above. No new ancillary events,
identity churn or critical bursts in this synthetic trace.

| Rate | Eight-sector raw sample: records /hours /days | Eight-sector raw max names: records /hours /days |
|---|---|---|
|NORMAL|1472 /92 /3.833333|1197 /74.8125 /3.117188|
|HIGH|1539 /20.797297 /0.866554|1261 /17.040541 /0.710023|
|STRESS|1667 /1.722107 /0.071754|1351 /1.395661 /0.058153|

These are **conditional FULL-detail body-pool capacities**, not new guarantees.
Both sample/max72h NORMAL now arithmetically fit raw:1152 sources +3daily objects,
sample7sectors+98304=126,976 B (4096 margin), max8sectors+98304=131,072 B (0).
That improvement comes from4KiB hypothetical witness reserve reduction, **not a
codec change or proved lifetime policy**. Native53-byte projection, credit gate,
peak allocation and backend-detail contracts must close before using it.

If the same complete sectors are instead stored as NVS4096-byte blobs, optimistic
isolated-pool allocation above gives7blobs9pages:98304+36864=135,168 (−4096),
8blobs10pages:98304+40960=139,264 (−8192). This holds raw fixed cost constant
only to show **additional NVS event-pool tax**. It is not an exact full NVS engine
budget: fixed objects and COW/free-page sharing must be remapped too. If an
8-sector dedicated NVS window admits only6whole blobs, sample retention becomes
1104 /69h /2.875d NORMAL,1154 /15.594595h /0.649775d HIGH,1247 /1.288223h /
0.053676d STRESS; max900 /56.25h /2.34375d,945 /12.770270h /0.532095d,
1012 /1.045455h /0.043561d. Thus `72H_*_FITS=RAW_CONDITIONAL_YES;
NVS_WINDOW_ESTIMATE_NO`, not production acceptance.

Semantic compaction horizon remains UNDEFINED: backend contract cannot yet
substitute aggregates for unsynced detail. Daily-only ceiling cannot authorize
loss. Infinite backend outage plus infinite critical arrivals cannot preserve
all details in any finite partition; the approved finite-buffer saturation
information/incident behavior is REQUIREMENT_GAP. No new duration/rate invented.

`CURRENT_128K_FEASIBILITY=CONDITIONAL`; minimum required partition UNDETERMINED;
partition increase necessity NOT PROVEN. The synthetic72h tax/peak deficit does
not itself justify192/256 KiB because72h and worst supported arrival/admission
policy are not locked. Per task, do not revisit384 KiB. Existing app/OTA evidence
1,864,624 /1,966,080 B,101,456 margin unchanged; no new build/partition/hardware.

## Validation and remaining STOP gates

New host artifacts: `host/storage/lifecycle_model.hpp`,
`tests/cpp/storage_lifecycle_validation.cpp`,
`tests/cpp/storage_lifecycle_sizing.cpp`; dedicated Make target only.
No firmware source lists or default behavior changed. Allocation is fixed
arrays; lifecycle model Ledger26,368 bytes,384 witnesses; million events peak89
under16-event report batches with six randomized interleaved Nodes. This RAM is
model size, not recommended target index or measured firmware footprint.

Commands/results are preserved in sibling `_REGRESSIONS_20261007.log`,
`_SANITIZERS_20261007.log`, `_SIZING_20261007.log` evidence. ASan/UBSan on new
model with `detect_leaks=0`, `halt_on_error=1`; no leak-check claim. Model flags
assume atomic snapshot restore; no real flash or physical qualification claim.
Final validation: lifecycle/fault tests PASS; sizing/static budget PASS; ASan/UBSan PASS (exit0); source backend completion PASS; journal persistence/recovery PASS; Node retirement protocol and Hub snapshot PASS; documentation links24 PASS; git diff --check PASS; final preflight PASS at.003.

Existing density regression still executes its separate million-event fixture;
backend completion, journal recovery and Node retirement/report snapshot tests
exercise actual components in addition to abstract tests.

Production integration stays **NO** until all relevant gates close:

- enforce/safely admit finite uncovered-key bound, fair persisted report progress,
  epoch/replacement/retirement root safety, six-owner bound;
- canonical immutable retry digest and same-key conflict verification end to end;
- backend derived/source completion and retained payload equivalence, explicit
  offline/critical saturation/substitution policy;
- actual full-body/config/routine/day/coverage/time recovery owner lifetime;
- AEAD append inventory/root freshness/nonce/erase/resume proof with bounded
  simultaneous metadata/COW/free-space peak;
- rollback/FOTA format safety; target RAM/OTA growth, raw versus NVS physical
  allocation, worst victim-live fraction and flash wear.

No new REQUIREMENT_CONFLICT established. New finding is a **protocol progress
proof gap**, plus an already-open product saturation REQUIREMENT_GAP. No locked
requirements changed; no CONTEXT_VERSION bump or automatic promotion.
