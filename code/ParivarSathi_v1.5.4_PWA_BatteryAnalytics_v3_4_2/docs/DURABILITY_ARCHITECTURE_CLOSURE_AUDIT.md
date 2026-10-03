# Durability architecture closure audit

Audit date: 2026-10-03. Code checkpoint: 3b02657165cce7684a14a794bdd8d9829ea3cbf3,
feature/hub-durable-storage-primitives. Authoritative worktree:
/home/udaybhan/projects/Ghar_sajag_durable_storage_impl.
Preflight matched HEAD and origin, and the worktree was clean. This document is
the only modification. No production source, test, schema, partition, or key
mapping was changed; no regression suite or hardware test was run for this audit.

## 1. Decision and limits of the verified baseline

The components support bounded admission, independent completion receipts, and
retirement reports. They are not yet a closed production reclamation architecture.
There are 16 finite closure items: eight P0, six P1, two P2. Do not start with
completed-effect retirement. Close authenticated enrollment/admission integration,
then durable-root/staged-object recovery, then incarnation/version contracts.

The current formats cannot support safe indefinite reuse merely by adding erase
calls. They lack a persisted sparse live-slot ownership map, reuse generations,
reclamation commit state, and production reducer ownership independent of all
retained events. A compatible, explicitly versioned extension is required.
This is a structural extension of the storage/recovery model, not a need to
replace authenticated transport, Node pending semantics, or backend transaction
idempotency. Its budget and migration must be approved before destructive work.

Claims here distinguish code trace, existing host tests, and physical evidence.
The previous PASS results are baseline evidence, not new executions. Target
CMakeCache files have GS_HIL_BUILD=OFF and GS_HIL_CONTROL=OFF for both targets;
previous ESP-IDF v6.0.3 compilation is useful but does not execute adapters.
No physical ESP-NOW, allocator, power-cut, or reboot qualification is established.

### New cross-layer findings

1. Enrollment binding is not a registry allocation. derive_retirement_enrollment_binding
   computes HMAC(journal_key, logical_id), slot=digest[0]%10, and a pseudo-generation
   from digest[1..4]. apply_authenticated_report requires slot <= node_count and
   dense append at node_count. A first report assigned slot 9 is rejected with
   node_count=0; slot collisions fail closed. For the existing fixture key bytes
   9..40, room-1 maps to 0, node-1 to 9, node-2 to 1, node-3 to 7, node-4 to 5
   (read-only standard HMAC calculation). Host integration uses room-1 and hides
   this general deployment problem. Replacing hardware at the same logical ID
   leaves binding/generation unchanged, even though EventKey includes hardware ID.
   Compressed retirement/dedupe evidence can consequently conflate incarnations.
2. HubJournal::commit returns Duplicate from its ids_ set before comparing payloads.
   DurableStore's exact digest conflict check is bypassed for retained duplicates.
   Authenticated changed-payload duplicates can therefore receive a Durable ACK.
3. Report installation protects only the selected report bank before prepare_bank,
   not the union referenced by both recoverable checkpoints. Three banks exist,
   but the target generally alternates two. An older recovery root can lose its
   snapshot before its checkpoint is replaced. Currently this chiefly reduces
   recovery availability; after reclamation, regressing an acknowledged retirement
   floor would become a replay/data-loss risk. No deletion may rely on that floor
   until fallback-root protection and nonregression are closed.
4. Checkpoint preparation writes ev objects before publishing the checkpoint.
   inventory_chunks_owned accepts ef/ev only from selected or alternate roots,
   plus a narrow prospective ef archive exception. It has no corresponding ev
   preparation exception. A cut after ev preparation can strand unowned evidence
   and fail owner recovery. Dropping checkpoint evidence references after report
   coverage also leaves physical ev keys; once both roots omit them, owner recovery
   rejects them. Root release and physical release are not yet one recovery protocol.
5. Production Hub target has no CloudSync/backend HTTP/TLS caller. The authenticated
   backend completion boundary is typed and host-proven, but target delivery is
   absent. PRODUCT_ARCHITECTURE_v1.4.md explicitly documents this limitation.
6. HubRuntime::restore_from_journal rebuilds coverage/routine/activity state from
   every retained event. Production checkpoints do not own a serialized equivalent
   reducer state. Removing events can alter recovered business decisions even if
   backend completion and Node retirement proofs are valid.
7. EventKey lifetime uniqueness is only conditional on preserved boot counter and
   identity state. Full erase/new installation can repeat MAC-based physical ID,
   logical ID, session and sequence. Neither storage epoch nor enrollment generation
   is included in EventKey, receipt MAC input, or backend durable_event_commits PK.
   Node recovery AAD binds home/hub/logical IDs, not a new enrollment incarnation.
8. The asserted 87,314-byte/3,605-entry model is arithmetic, not a complete physical
   allocator proof. Its base includes four generic effect chunks and modeled Node
   work, whereas production retains up to 32 archive chunks plus exact evidence.
   It is not a reconciled inventory/transaction bound for all live/migration states.

## 2. Source map and persistent object ledger

Primary paths below are relative to the product directory.

- shared/include/gs/domain.hpp: EventKey and its canonical str().
- firmware/node/runtime/node_runtime.cpp: record, acknowledge, recovery snapshot,
  set_retirement_epoch, restore_recovery; NodeRadio/NodeStore own pending/retained RAM.
- firmware/node/components/storage/node_recovery_persistence.cpp: recovery-v3 codec,
  association-scoped AAD, generation/readback, 8,192-byte bound and 32 keys.
- firmware/node/target/esp32c3/node_runtime_adapter.cpp: persist before TX, ACK
  persistence, authenticated epoch/ACK handling, deterministic report retry.
- firmware/node/target/esp32c3/nvs_session_provider.cpp and common/transport/session_id.cpp:
  persisted gs_node/boot_session allocation before session use.
- firmware/common/security/association_persistence.cpp, registry/registry_persistence.cpp,
  and target security links: authentication, association, revocation and sessions.
- firmware/hub/components/storage/journal.cpp: attach_persistence, commit,
  pending_cloud, acknowledge_cloud; durable slot receipts use completion_mac.
- storage/durable_journal_slot_store.cpp: append_event, rows, flush, write/read_completion,
  publish_completion, replace_completion and legacy migration.
- storage/durable_transition.cpp/.hpp: transition/chunk/bitmap/checkpoint/evidence codecs,
  commit/recover/checkpoint, handoff_effects, commit/read_bitmap and BlobStore contract.
- storage/node_retirement_snapshot.cpp/.hpp and common/transport/node_retirement_protocol.cpp:
  reports, HMAC/fragments, snapshots, exact ledger and retirement coverage.
- storage/hub_durability_owner.cpp: epoch authority, inventory/root selection and ownership.
- target/esp32/hub_runtime_adapter.cpp: authenticated admission, report installation/ACK.
- target/esp32/nvs_durable_blob_store.cpp, nvs_store_inventory.cpp, nvs_durable_key_codec.cpp:
  gs_journal/events namespace, physical base36 ef/ev keys, immutable/replace/readback.
- firmware/hub/components/cloud/cloud_sync.cpp: backend transaction request/reply boundary.
- backend/ghar_sajag/durable_commit.py and migrations/008_durable_event_commit.sql:
  SQLite identity/fingerprint transaction, incidents, per-recipient notification outbox.

Each ledger entry specifies owner, identity, create/mutate/commit, recovery/replay,
eligibility/migration, bound, failure policy and proof boundary.

| Object | Owner and stable identity | Creation/mutation and durable commit | Recovery and replay | Release/migration | Bound and failure/proof |
|---|---|---|---|---|---|
| Node boot session | Session provider; gs_node/boot_session | Increment and nvs_commit before use; no wrap | Load previous counter then increment; failed save stops boot | Preserve across association reset; full erase needs new incarnation | u64; host counter tests, target build; flash HIL needed |
| Node pending recovery | Node owner/repository; home/hub/logical AAD, recovery generation, origin session/sequence | record/ACK mutate RAM; save/readback before TX or report; epoch change saved | Fresh runtime restores complete pending set; reboot advances report generation; old origin keys remain | Event ACK removes pending key durably; factory/recommission handover unresolved | 32 keys, blob <=8192; auth/IO failure stops owner; host recovery tests |
| Hub event transition | Durable owner/store; epoch/ordinal and exact EventKey/digest | append_event writes tr[(ordinal-1)%4], exact readback before event Durable ACK | Consecutive tail above checkpoint boundary; same digest retry idempotent | Reuse tr only after BOTH checkpoint boundaries cover old ordinal; archive first | Four tr, <=1332 each; malformed transition fails closed; host faults plus HIL |
| Retained event archive | Journal adapter under owner; durable slot in transition decision then archive Effect.id[0..3] | flush writes immutable ef ID based on checkpoint generation, then checkpoint and shadow root | rows decodes DomainEvent payload and slot; journal currently requires dense 0..n-1 | No event deletion/reuse today; legacy e slots copy/verify before source cleanup | 32 checkpoint chunk refs, <=4 events/1260-byte chunk; crypto/duplicates fail closed |
| Backend effect identity | CloudSync: one application commit per installation-scoped EventKey; backend key additionally home_id | Deterministic request derived from retained event | Exact origin session preserved, not transport session | No payload distinct from retained archive; extra Hub operation would need EffectId | Host boundary only; target client absent |
| Independent completion receipt | Journal adapter; cNNN HMAC(HKDF(journal key), GSC1 + u64 slot + EventKey.str) | Authenticated matching COMMITTED reply; immutable write/exact readback | Verify against exact recovered slot/key; rebuild cloud_acked_, suppress request | Immutable while event owned; kind=1 publishes after e/c migration; legacy marker kept | 128 x32 bytes; conflicts/partial/orphans fail attachment closed; host faults |
| Legacy kind=1 marker | Authenticated event archive entry | Legacy import/replace_completion; new Ready completions use c only | read_completion publishes independent proof before opening runtime | Redundant only after c verified; payload/event MUST remain | No separate effect payload; clearing marker needs safe whole-chunk update; no bytes saved |
| Retirement report | Node recovery state owns content; epoch/generation/current session/high-water/pending keys; installation-key HMAC | Construct/fragment after durable changes; retry volatile TX cursor | Regenerate same logical state; rejoin/reboot safe resend | TX/report ACK RAM may discard; Node durable pending state survives | <=32 keys, 542 logical bytes, <=4 fragments; epoch 0 rejected; host codec proof |
| Hub fragment accumulator | Hub security owner; authenticated MAC/transport session/report generation/HMAC | Bounded RAM reassembly only after AEAD authentication | Incomplete sets cannot install; generation/session mixing resets/rejects | Volatile, safe to lose; retries restore fragments | Per authenticated relationship; host component proof, adapter target-build only |
| Retirement snapshot | Owner/repository; epoch, snapshot generation, authenticated enrollment binding and report HMAC | Prepare ret bank/readback, checkpoint selection/recover/load, then ACK | Duplicate same generation/content safe; stale/conflict rejected at component boundary | New report supersedes old snapshot; retain every recoverable-root reference | Three ret banks <=6096 each; wrong binding/corrupt selected bank fails closed; target mask gap |
| Event ACK / report ACK | Hub/Node runtime security context | Event ACK after journal commit; Node persists removal. Report ACK after selected snapshot verification | Lost ACK yields safe resend; Node report ACK acceptance matches epoch/generation/HMAC | Report ACK receipt is RAM only, not an additional durable reclamation proof | AEAD/session replay protection; adapter execution not host-proven end-to-end |
| Exact dedupe evidence | Durable store/checkpoint; enrollment slot/generation + session/sequence + digest | Fold only covered tail into ev chunks; verify and checkpoint reference | Admission reads exact evidence and report coverage | Logical ref removal may be report-covered; physical deletion missing; orphan gap | 32 refs, 4 entries/chunk, <=320 each; ExactEventKeyLedger capacity128; host component proof |
| Checkpoints/selectors | Owner/store; epoch, monotone root generation, covered ordinal | cp0/cp1 replace/readback then sel0/sel1 authenticated publication | Selected root + tail; metadata-only checkpoint preserves event boundary; valid fallback possible | Cannot free anything still needed by ANY legal root; selector/snapshot floor gap | cp<=4514, selector actual41/max64; codec schemas exist; host A/B faults |
| Completion bitmap / generic handoff | DurableStore primitives, not production completion owner | bm0/bm1, generation/checkpoint_generation/mapping_digest and 16 bits; ef handoff | Match digest/epoch; no stable production 128-effect mapping | Do not reinterpret padding or use as receipt replacement | bm<=384, pending effects16; host primitive tests only |
| Installation/enrollment security | Registry/association repositories; device keys, association generation, last_session, revoked IDs | Authenticated commissioning/rejoin and persisted registry candidate | AEAD key/salt/session binding; monotonically preserved session/revocation state | Full replacement/reset handover not coordinated with EventKey/recovery/floors | Ten active/tombstone capacity on target; finite replacement budget; host primitives + HIL |
| Backend commit/outbox | SQLite backend; home + physical/logical/origin/sequence/fingerprint; outbox effect_key/recipient | BEGIN IMMEDIATE, event/receipt/jobs/outbox transaction, COMMITTED after commit | Lost response yields exact duplicate; conflict differs fingerprint; provider uses outbox_id | No safe DB identity-receipt purge contract found; preserve until sender namespace revoked/floored | Host SQLite fault/restart tests; authenticated target client/provider delivery missing |
| Free/reclaimed storage | No production owner today | BlobStore has no erase/release operation for durable ef/ev/c; legacy erase is migration-only | No durable free-slot map to recover | Needs commit-owned release inventory, conditional deletion and fixed pools | NVS keys are physical objects, not logical slot generations; reclamation untested |

## 3. Lifecycle arrows and interruption semantics

All current durability proofs are readback/codec/identity checks; NVS physical
commit semantics require HIL. P0 gap IDs below explain incomplete arrows.

| Arrow | Durable proof and identity | Cut before / cut after | Replay, stale-state guard and retained/releasable state |
|---|---|---|---|
| Node create -> persist | Recovery save of exact session/sequence; high-water only admitted messages | Before: old pending snapshot. After: key must recover | No TX before save; retain full pending until authenticated event ACK saved |
| Persist -> authenticated TX | Saved recovery + installation/session AEAD | Before/after: pending remains until ACK | Resend under fresh transport session keeps origin identity; volatile TX cursor releasable |
| TX -> Hub admission | AEAD/authenticated enrolled identity; target source/device injection | Before: Node retries. After admission RAM alone is not Durable | Reject stale session; exact duplicate path needs G03; retain Node event until durable response |
| Admission -> Hub journal | Transition and full event readback | Before: no Durable ACK. After: Hub responsibility survives reset | Exact identity links journal/backend; retain tail until archive ownership committed |
| Journal -> backend pending | Valid event with no valid independent receipt | Before/after: reconstruct pending from archive/tail | Stable request; retain event and absent-completion meaning |
| Pending -> backend execution | Target client absent; host CloudSync boundary + SQLite transaction | Before: retry; after server commit/before local proof: exact retry | Requires authenticated client G08 and backend durable identity receipt; no notification send inside DB transaction |
| Backend success -> c receipt | Authenticated COMMITTED exact key; MAC/readback | Before: retry under backend idempotency. After: no request after recovery | Preserve c and event binding; corrupt receipt stops attachment |
| Receipt -> reboot suppression | Journal verifies c against recovered exact slot/key | Before/after: durable c reconstructs completion | RAM cloud_acked_ is a cache; not a new proof |
| Node ACK retirement -> report | Saved pending removal and incremented generation; sequenced Heartbeat included | Before save: previous complete pending set; after: new complete set | Old-session key remains while pending; NodeHealth excluded; no backend completion assertion |
| Report -> fragments -> reassembly | Existing logical report HMAC + AEAD relationship | Cuts lose only RAM accumulators/cursors | Complete bounded set needed; duplicate/reordered safe; enrollment allocation gap G01 |
| Reassembly -> snapshot selection | Semantic/epoch/generation validation, ret readback, cp selection/load | Before root: prior snapshot; after root: new snapshot | No success ACK on failure. Guard every root and staged key: G02/G05 |
| Snapshot -> Hub ACK -> Node ACK | Authenticated ACK epoch/generation/HMAC | Lost send/receive: same report repeats; after receive: RAM retry stops | ACK reception is not persisted; reboot resends. Snapshot coverage, not ACK delivery, is the durable fact |
| Completion -> redundant effect retirement | Proposed receipt plus recoverable whole-chunk transaction | Old marker or new marker-free archive; both retain c/event | No separate payload currently exists; G15 optional; never delete event as effect retirement |
| Joint evidence -> event reclamation | Proposed D + N + F + R + policy + ownership transaction | Old live event or committed retired map; never half-deleted identity | G04/G06/G07; retain anti-admission floor after archive release |
| Reclamation -> c deletion | Committed event exclusion from ALL roots plus surviving replay guard | Before: retain c; after: event cannot be executed/admitted again | Conditional delete exact old slot generation/identity; G06; lost report ACK harmless |
| c deletion -> slot reuse -> NVS reuse | New occupancy generation/full identity; free pool published durably | Empty/reserved slot or complete new event; no old c binds new occupant | Current dense vector/immutable keys cannot do this; G06/G09/G11 |
| Reuse -> >128 -> indefinite bounded operation | Finite pools and durable monotone floors with authenticated revoked incarnations | Any interruption recovers old/new valid ownership or explicit failed-closed state | Progress conditional on backend/report availability and remaining numeric lifetime; G10/G11 + HIL |

## 4. Proposed exact contracts (design only)

Let e be a full effect identity in an installation/enrollment incarnation, not
merely a logical room/session pair. Define:

- H(e): authenticated immutable event identity/content is recovered consistently.
- D(e): independent completion receipt for the exact effect/slot incarnation is
  authenticated, durably installed/read back, and recoverable. Backend COMMITTED
  means durable application transaction, not MQTT PUBACK, notification delivery,
  or a human acknowledgement.
- N(e): a complete authenticated report, bound to the exact enrolled incarnation,
  current nonzero storage epoch and accepted monotone report generation, is owned
  by a verified durable root. The key is absent AND covered: origin is older than
  current origin session, or same origin and sequence <= durable admission high-water.
  Mere absence of a future/never-covered key is insufficient. Old sessions with any
  pending key remain open. An offline Node without such evidence is not assumed drained.
- F(e): monotone durable rejection evidence prohibits re-admission/execution of e,
  including delayed packets, across EVERY permitted fallback root and restart.
  It is bound to the same installation/enrollment incarnation. Revoked old transport
  relationships cannot be reactivated with reused event identities. A latest report
  can compress this evidence only if its floor cannot roll back during recovery.
- R(e): a verified durable reducer/history checkpoint contains every contribution
  needed for future decisions/recovery; all downstream effect ownership is transferred.
- P(e): explicit local history policy permits deleting this record. Do not silently
  equate cloud completion with authority to delete product/audit history.
- T(plan): restart-safe authenticated ownership transaction has verified inputs,
  bounded staging capacity and precise identities; physical deletion occurs only
  after publication excludes the objects from all recoverable roots.

### Completed effect

COMPLETED_EFFECT_RETIREABLE(e,q) IFF H(e) AND D(e) AND q is redundant
effect-specific state AND every required identity, replay guard, retry/report,
completion proof and retained event payload survives removing q AND T(remove q)
is valid. Actual removal follows the verified transaction commit.

Today q can be an old kind=1 marker; it is not the archived DomainEvent payload.
CloudSync retry/backoff entries are RAM and already clear on completion. cNNN is
not redundant while journal recovery relies on it. Clearing a marker changes a
whole authenticated shared chunk, so preserve every other event/effect and use
recoverable replacement ownership. Marker clearing saves no blob bytes/entries.

Recommend this least complex contract. Alternative D(e) AND N(e) for marker-only
cleanup is conservative but needlessly delays it; Node coverage adds no backend
completion proof. Requiring proof of Node report-ACK receipt would need a new
ACK-of-ACK contract and is unnecessary. No separate durable backend-effect payload
exists to delete today. Future independent Hub sinks require EffectId, not marker
reinterpretation.

### Logical event

EVENT_RECLAIMABLE(e) IFF H(e) AND D(e) AND N(e) AND F(e) AND R(e) AND P(e)
AND T(reclaim e, completion lifetime, slot ownership) is valid.

Actual bytes may be released only after event ownership exclusion is committed
for every legal recovery root. Keep siblings of a shared four-event chunk intact.
Retain pending/retry effects, exact identity proof/floors, necessary reducer state,
and the selected retirement snapshot. Backend completion and Node coverage are
jointly necessary here; neither alone is sufficient. Report ACK send/receipt is
not an additional predicate because lost ACK must not revoke already durable N(e).
The current code does not yet implement F/R/P/T for event deletion.

### Independent completion receipt

COMPLETION_RECEIPT_CAN_BE_DELETED(e) IFF D(e) was verified AND e is durably
excluded from all live/recovery/retry ownership AND F(e) survives deletion AND
all legacy-marker migration obligations are satisfied AND a committed transaction
binds the deletion to the exact old slot generation/full identity AND no legal
fallback root can resurrect e.

Effect-marker retirement alone does not permit receipt deletion. A report ACK
alone does not change receipt lifetime. Keep the receipt while the retained event
would become pending if recovery did not see it. If an event remains as historical
only state, a new persistent non-executable state must replace that dependency
before c can be removed; current HubJournal has no such state.

### Anti-ABA and installation identity

For reused slot n, accept completion only when its authenticated full effect ID
AND slot ownership generation equal the currently committed map entry. Publication
must never mix A's receipt with B's event; deleting A must never delete B's receipt.
Delayed cleanup must be conditional on old generation/identity and unreferenced
status. Every legal recovery root observes either the complete A-era state or the
complete B-era state, or an explicitly reserved/free state that cannot execute B.
An ever-increasing epoch alone does not replace slot/event identity.

Current MAC(n, EventKey A) cannot authenticate different EventKey B under standard
HMAC assumptions. A stale c for a genuinely different B causes failure closed,
not false completion. HOWEVER if EventKey A repeats with the same receipt key and
slot, the MAC input is identical; current code cannot distinguish incarnations.
This disproves an unconditional lifetime anti-ABA claim. Receipt key rotation
alone also does not prevent collision in the backend identity primary key.

Required installation invariant: no reset, erase, Hub/Node replacement or
recommission can reuse an event-producing namespace while any old receipt,
backend idempotency record, pending message or authenticated replay capability
can survive. Preserve monotone counters within an incarnation; changing domain
requires a durably unique incarnation reflected in Node recovery, authenticated
enrollment, Hub evidence and backend EventKey/authorization. Epoch monotonicity
is within that domain, not a way to compare unrelated fresh epoch-1 installations.
A reset/handover must drain or explicitly transfer pending old-incarnation keys,
not relabel them under a new enrollment.

## 5. Reset, replacement and identity boundary table

| Boundary | Existing behavior | Required closure |
|---|---|---|
| Fresh security + empty journal | Owner bootstraps epoch1; preserved registry plus erased journal fails closed | New installation identity must be distinguished at Node/backend as well as local keys |
| Normal Node/Hub reboot | Persisted boot session increases; registry last_session and recovery survive | Host-proven primitives; target physical reboot HIL |
| AssociationRepository factory_reset | Writes unpaired record with higher association generation; does NOT erase boot_session | Preserve counter and pending responsibility; define coordinated reset API, not blanket erase |
| Full flash/namespace erase | Session can restart1; physical MAC identity can be the same; key creation may renew secrets | New durable incarnation + backend identity separation; never silently reuse old EventKey |
| Node replacement | Registry revokes old hardware/binding and persists new one; EventKey hardware ID differs | Actual enrollment generation/slot binding must differ too; old pending evidence preserved/revoked safely |
| Same hardware recommission | Activation/rejoin controls may reject stale state, protecting current installation by failing closed | Explicit supported handover; recovered Node state currently binds home/hub/logical, not enrollment incarnation |
| Hub replacement / new Hub at same logical IDs | Key/home/hub bindings differ; existing storage cannot simply be adopted | Authenticate domain handover and transfer/drain Node pending plus completion state; do not reset epoch silently |
| Enrollment change | Registry session/key state changes; retirement pseudo-generation does not track replacement | G01/G04: persisted real incarnation; old snapshot cannot classify new hardware keys |
| Storage-only erase | Existing owner fails closed, never reformats automatically | Preserve diagnostics/recover backup or authorized new domain; no invisible receipt loss |
| Legacy partial migration | Reverse bounded batches copy/verify then source receipt/event erase; kind=1 preserves proof | Existing host coverage; staged-object gaps and future slot-map migration remain |

Ten-entry revocation/tombstone capacity also bounds replacement history. Unlimited
recommission cannot mean storing all old identities forever in a fixed vector.
Close bounded revocation/authorization generations with a durable namespace
boundary; do not drop old tombstones while their credentials can still act.

## 6. Capacity audit and indefinite operation

128 currently combines: HubJournal capacity_/records_.size; numbered slot bound
0..127; c000..c127; 32 archive references x4 events; 128 exact-ledger entries.
It is NOT the 16-bit CompletionBitmap width (that primitive is unused for production
completion), nor the ten-node report snapshot limit. Because there is no release,
128 simultaneously retained events is also an effective lifetime admission ceiling
until installation history is replaced. Completing all 128 does not permit 129.
HubJournal attach rejects holes and commit chooses records_.size as slot: erase or
vector erase is not a compatible sparse-slot allocator.

Current reports are <=542 bytes and four fragments in RAM/transport. Hub ret banks,
not those wire frames, consume gs_journal flash. Node recovery is a separate
8,192-byte bounded object in Node NVS; do not count Node RAM/report bytes as actual
Hub gs_journal allocation.

Historical budget assertions (tests/cpp/hub_durable_storage_validation.cpp
modeled_migration_budget and test_node_retirement_protocol_model.py test_22):
87,314 = 83,218 + 128*32; 3,605 = 3,221 + 128*(2+ceil(32/32)). Headroom 43,758 raw
bytes / 427 modeled entries of 4,032. These are reproducible model numbers. The
base includes four effect chunks, generic pending-work allocations, and metadata
allowances; it does not enumerate current production's 32 retained archive chunks
and exact-evidence lifetime or prove NVS page GC. Do not present it as a measured
peak or a certified worst case. Provider selector maximum is64, codec actual41.

Reconciled component ceiling for an operating retained-root set (not a proof that
all maxima coexist, not a physical flash peak):

| Family | Count x maximum bytes | Raw bytes | Entries using 2+ceil(bytes/32) |
|---|---:|---:|---:|
| ef event archives | 32 x1260 | 40,320 | 1,344 |
| ev exact evidence incl one alternate/prepared ref | 33 x320 | 10,560 | 396 |
| c independent receipts | 128 x32 | 4,096 | 384 |
| ret snapshot banks | 3 x6096 | 18,288 | 579 |
| cp banks | 2 x4514 | 9,028 | 288 |
| selectors (actual codec bound) | 2 x41 | 82 | 8 |
| transition ring | 4 x1332 | 5,328 | 176 |
| completion bitmap banks | 2 x384 | 768 | 28 |
| migration marker allowance | 2 x512 | 1,024 | 36 |
| Namespace entry allowance | 1 entry | 0 | 1 |
| TOTAL | | 89,494 | 3,240 |

Use 64 rather than41 for provider-only selector bounding: add46 bytes, no entry
change. Bitmap/migration allocations are allowances, not all current production
creations. A conservative additional modeled staging allowance of one checkpoint,
archive, evidence chunk and bitmap is 6,478 bytes /212 entries. That gives 95,972
bytes /3,452 entries, leaving 35,100 bytes /580 modeled entries; provider-max
selector variant is96,018 bytes. Existing legacy source e/c keys must additionally
be budgeted per migration phase; source/destination sharing and release order must
be explicitly modeled rather than summing mutually exclusive maxima or ignoring
source receipts. Reverse migration shrinks legacy slots as archive batches grow.

CURRENT_WORST_CASE_BYTES / ENTRIES are therefore NOT CERTIFIED: the historical
model, retained-root ceiling and candidate staging model above are distinct. G09
must close actual per-phase maxima, abandoned objects, duplicate bank ownership,
NVS replacement garbage and GC scratch. Arbitrary failure/staging residue is not
covered by the live-root table. Physical storage cannot exceed the partition but
admission/recovery may fail before the advertised event bound.

Entry capacity is the tighter model margin: historical free10.59% vs raw33.38%;
reconciled staging free14.38% vs raw26.78%. 427 entries allow only 35 additional
320-byte blobs or10 additional1260-byte blobs under that model. Generation-derived
ef/ev IDs cannot grow indefinitely, and unreferenced ev objects already cause
recovery failure even before capacity exhaustion. Physical deleted entries are
not automatically reusable space until NVS page GC; raw bytes are not enough.

Let A be fixed archive-pool occupancy, E evidence-pool occupancy, C live receipts,
R=3 report banks, K=2 checkpoint banks, T=4 transition slots, X versioned map,
incarnation/floor/reducer metadata, S bounded staging, L remaining legacy sources,
and G allocator/GC reserve. Future bounds must certify:

    B <= 1260*A + 320*E + 32*C + 6096*R + 4514*K + 1332*T
         + selectors + optional bitmap/migration + X_bytes + S_bytes + L_bytes
    Entries <= 42*A + 12*E + 3*C + 193*R + 144*K + 44*T
               + fixed overhead + X_entries + S_entries + L_entries + G_entries

A/E/C limits are union-of-all-roots/pools, not just selected-root counts. New receipt
formats change the32-byte term explicitly. Slot generations, digests, occupancy
map, reducer state and floors must actually fit codec/reference caps or be bounded
in versioned metadata chunks. Do not assume they fit the existing4514-byte codec.

AFTER_COMPLETED_EFFECT_RETIREMENT: no guaranteed raw/entry reduction for kind-marker
clearing; COW temporarily increases S. AFTER_LOGICAL_RECLAMATION: remove only
commit-unreferenced objects; a four-event archive cannot free one quarter of an
NVS blob, so mixed chunks need bounded COW/repacking. STEADY_STATE_AFTER_SLOT_REUSE:
the formula above with fixed A/E/C/X/S/G and L=0, independent of lifetime event count.
Exact values require G06/G09 design; no approved new constant is implied here.

For events129,256,1000 and sustained operation: commit evidence-backed retirement
and reducer state, publish sparse ownership, conditionally release old receipts/
chunks, then reuse fixed physical pool slots with new generations. No ever-growing
ef/ev key family or tombstone list. Safety under permanent offline/backend outage
requires finite backpressure, not time-based deletion. Progress is conditional on
service/report availability and authenticated revocation/handover. Numeric counters
must fail closed before wrap; backend SQLite INTEGER is signed64 while protocol
counters are u64, so supported product-lifetime ranges must be reconciled. Literal
infinite operation with finite counter namespaces is not a mathematical promise.
Backend database history may grow under its retention policy; target-flash boundedness
does not prove the entire cloud database is bounded. Backend dedupe receipts must
not be purged while any authorized sender can retry their identities.

## 7. Crash/power-cut matrix

Host fault injection proves modeled ordering, not actual NVS flash atomicity.
All rows require physical HIL for a production physical-power-cut claim; rows13-17
are proposed and UNTESTED until implemented. Corruption may require failed-closed
service rather than silent old-state selection.

| Boundary | Required recovery / retry | Authoritative retained state | Current host proof / HIL obligation |
|---|---|---|---|
| 1 Before event archive write | Recover committed tail, retry archive; no lost Durable-ACK event | Transition + old cp | Archive/migration host coverage; board cuts before nvs_commit |
| 2 During archive write | Prior valid root+tail, or explicit failed-closed corruption; do not delete source | Old cp/tr and verified source | Partial-write tests; physical torn-write/GC validation |
| 3 After archive commit, before cp | Recover/retry prepared archive ownership; do not call orphan disposable | Old root+tail and exact prospective archive | Narrow ef exception exists; G05 general staged-state proof needed |
| 4 Before backend request | Pending event survives | Event and absent c | Journal/CloudSync host tests; target client G08 then HIL |
| 5 Backend success before c | Exact backend retry must produce duplicate COMMITTED, not redo jobs | Backend transaction identity receipt/outbox | SQLite lost-response tests; trusted network interruption needed |
| 6 During c write | Missing c leaves retryable event; corrupt c fails attachment; never false completion | Event + verified c only | Before/partial/persisted-API-failure host tests; NVS cuts/GC |
| 7 After c commit | Fresh runtime suppresses request; preserve history | c exact binding + event | Fresh-owner/provider completion tests; board reboot |
| 8 Before report TX | Rebuild full pending report; no report with epoch0 | Node recovery generation/pending/epoch | Node recovery/codec host tests; radio reboot |
| 9 During snapshot install | Prior/new valid root; no ACK without verified selected snapshot; staged residue recoverable | Old cp/snapshot and authenticated staged objects | Component bank faults; target bank-mask/staging G02/G05 unproven |
| 10 Snapshot selected before ACK | Retry identical report idempotently; floor may not regress | Selected snapshot/checkpoint and durable floor | Component duplicate/recovery proof; target HIL and floor closure |
| 11 ACK sent but lost | Node resends; Hub re-verifies same durable state and ACKs | Node pending/report state and Hub snapshot | Component/model lost-ACK tests; live adapter host harness + ESP-NOW HIL |
| 12 Node processes report ACK | Reboot resends safely; ACK RAM loss cannot change reclaim eligibility | Node recovery; report ACK flag is volatile | ACK codec/binding logic reviewed, target-built; full adapter host execution absent |
| 13 During marker/effect retirement | Old marker or new marker-free chunk; c/event/siblings survive | Versioned COW root + c | UNTESTED; implement G15 after G05; cuts at every COW boundary |
| 14 During event reclamation | Old live or new retired ownership, never completion-free executable old event | Reclamation transaction, floor, reducer checkpoint | UNTESTED G06/G07; physical cuts both cp/selector/erase boundaries |
| 15 During receipt deletion | Event cannot reappear pending via fallback; conditional identity delete restart-safe | Committed event exclusion + F + old-slot generation | UNTESTED G06; cuts before/after c erase |
| 16 During reuse publication | Old/free/reserved/new ownership is unambiguous; no ABA | Durable slot generation + full identity + root | UNTESTED G04/G06; reused-slot stale flash tests + HIL |
| 17 New event in reused slot | Recover complete B or no B; A receipt never suppresses B | New occupancy/root + exact B event/receipt | UNTESTED G06/G11; delayed A traffic/cleanup combined with physical cuts |

## 8. Migration/versioning and corruption policy

Explicit object schemas EXIST: GDT1 transitions emit schema2/read1 or2; GCP1
checkpoints emit2/read1 or2; GEC1 archives, GDE1 evidence, GBM1 bitmaps and GRS1
snapshots use schema1; selectors GSS1; completion MAC domain GSC1; Node recovery
reads prior versions and writes v3; registry/association codecs carry versions and
generations. Schema1 checkpoint frontiers without exact digest are marked
legacy_dedupe_unverified and cannot authorize normal recovery/admission.

The gap is an installation-wide compatible feature/migration ownership contract,
not absence of all version bytes. Recommend a new authenticated root/manifest
version declaring sparse live-map, slot incarnation, replay-floor and reducer
ownership. Dispatch legacy dense state explicitly; unknown versions fail closed.
Migrate e/c -> authenticated archives as today, then kind1 -> independent receipts,
then new map without deleting evidence. Verify both recovery roots and migration
progress before source release. Never infer the new layout from missing keys or
reuse zero bitmap padding (current decoders require it to be zero). New Node/backend
incarnation identity may require protocol/API schema migration; decide it explicitly.
Avoid publishing a slot-generation map without the corresponding identity/receipt
interpretation and replay-rejection floor.

| Object | Current corruption policy | Required future policy |
|---|---|---|
| Event archive/tail | Bad auth/codec/identity or duplicate slots fails closed; no silent skipping | Alternate owned valid copy may recover only if ownership/freshness proven; never drop retained event silently |
| Completion receipt | Wrong EventKey/slot, short/torn/MAC mismatch or orphan fails journal attach | Preserve evidence; recover authenticated replica if provided; never turn corrupt completed proof into an executable pending event |
| Exact dedupe evidence | Missing/digest mismatch selected chunk fails closed | No obsolete physical object removal until floor/ownership transaction proves it; no stale-floor fallback |
| Retirement snapshot | Selected reference requires digest/auth/epoch/generation; failure stops recovery | Protect all root banks; reconstruct only from authenticated Node resend without weakening previously ACKed floor |
| Checkpoint | Valid selector/root with older fallback may recover; both unusable fails closed | Fallback may not regress retired ownership/replay floor; committed delete boundary dominates old cp |
| Selector | Authenticated valid selector wins; store can fall back to valid cp if none usable; owner additionally gates selectors | One uniform documented selection/commit/floor rule; no disagreement between direct store and owner |
| Report/slot/recovery generation | Reject malformed/zero/overflow in relevant components | Persist real incarnation/reuse generations; reject unsupported wrap/ranges |
| Epoch/security metadata | Existing installation + empty storage/ambiguous freshness fails closed | Coordinated authorized new-domain reset/handover; epoch0 never valid; no old-domain adoption |

No reviewed corruption path authorizes automatic factory reset or storage erase.
An unrecoverable fault needs explicit service/operator recovery; reset is a new
installation transition, not a repair that silently loses accepted responsibilities.

## 9. Test coverage classification

HOST_PROVEN means existing focused tests execute that component/production portable
path. It does not mean the whole ESP32 adapter was executed on host. Prior gate PASS
is retained evidence; these suites were inspected, not rerun for documentation.

| Invariant | Evidence | Classification / missing closure |
|---|---|---|
| Independent completion, exact c binding, A cannot complete B, duplicate c, fresh reboot | hub_journal_migration_validation::completion_contract; hub-backend-completion-host-test alias | HOST_PROVEN; allocator/physical reboot HIL_REQUIRED |
| kind1 migration, before/after publication and legacy e/c cleanup cuts, mixed state | Same test plus run() reverse migration faults | HOST_PROVEN modeled; HIL_REQUIRED flash behavior |
| Backend lost response/transaction rollback/duplicate fingerprint and outbox ownership | test_durable_event_commit.py; hub_backend_commit_validation | HOST_PROVEN boundary; TARGET client UNIMPLEMENTED |
| Fragment duplicate/reorder/missing/auth/tamper/generation mixing and 32/542 bounds | node_retirement_protocol_validation::fragments_and_mac | HOST_PROVEN component; full adapter integration TARGET_BUILD_ONLY |
| Sequenced Heartbeat pending/high-water/old session; NodeHealth exclusion | node_retirement_protocol_validation + heartbeat_keeps_prior_session_open | HOST_PROVEN |
| Epoch persistence/reboot and high-water admission failure | node_recovery_persistence_validation; NodeRuntime tests | HOST_PROVEN; actual secured advertisement/receipt TARGET_BUILD_ONLY |
| Report stale epoch/generation/conflict/duplicate/durable bank readback | hub_retirement_snapshot_validation; hub_durable_storage_validation | HOST_PROVEN with explicit fixture bindings; general target enrollment G01 UNTESTED |
| Lost report ACK/reboot/rejoin | Python retirement model, codec/recovery/rejoin_host_validation; target retry logic | HOST_PROVEN components/model; complete production adapter ordering TARGET_BUILD_ONLY/HIL_REQUIRED |
| Metadata-only cp preserves tail, report after every event,128 completions,129 Full | completion_contract; metadata_checkpoint_faults | HOST_PROVEN; not a live report RX enrollment test |
| Full queue/storage and failure/corruption | journal capacity/provider/MemoryBlobStore fault suites | HOST_PROVEN simulated; target allocator exhaustion HIL_REQUIRED |
| Stale/wrong-slot/wrong-event c against unreused slot | completion_contract negative cases | HOST_PROVEN; namespace-repeat/ABA reuse UNTESTED |
| Actual enrollment slots/replacement generation; top-level changed-payload duplicate ACK | G01/G03 code-path contradiction | UNTESTED as deployment invariants, despite component PASS |
| Snapshot fallback-floor preservation and all staged ev ownership | G02/G05 missing protocol | UNTESTED full boundary; isolated A/B tests are insufficient |
| Sparse event deletion, receipt cleanup, slot/chunk reuse, >128 sustained operation | No production implementation | UNTESTED; generic1000-transition test is not production128-event rollover |
| Real NVS allocation, power cut, ESP-NOW physical reset/rejoin | No evidence found | HIL_REQUIRED, NOT_QUALIFIED |

Relevant Makefile targets: hub-durable-storage-host-test, hub-durable-provider-host-test,
hub-journal-migration-host-test, hub-journal-persistence-host-test,
hub-backend-commit-host-test, node-retirement-protocol-host-test,
node-recovery-persistence-host-test, hub-retirement-snapshot-host-test,
registry-persistence-host-test, association-host-test, rejoin-host-test,
cpp-test and validation-fast. Browser E2E absence remains MANUAL_REQUIRED and
is unrelated to claiming physical durability. No release-gate-final was run.

## 10. Finite prioritized architecture gap register

Severity: P0 correctness/data loss/replay, P1 endurance/reliability, P2 optimization/
maintainability. BLOCKS_PRODUCTION refers to the requested indefinitely operating,
reclaiming durability release, not whether a limited host demo can run.

### G01 — Real authenticated enrollment ownership (P0)
WHY_IT_MATTERS: hash slots/dense insertion and logical-only pseudo-generation can
reject normal reports or conflate replacement evidence.
CURRENT_STATE: authenticated input exists; allocation/incarnation is not registry-owned.
REQUIRED_INVARIANT: collision-free persisted registry slot and real enrollment
incarnation bind physical identity, journal digest evidence and report snapshots.
DEPENDENCIES: G04 for final lifetime domain; a non-destructive interim binding fix can proceed.
HOST_PROOF_REQUIRED: first Node at arbitrary logical ID; ten Nodes every insertion
order; forced hash collision; replacement low-session pending keys; wrong physical/generation.
HIL_PROOF_REQUIRED: authenticated multi-Node/replacement behavior in G14.
IMPLEMENTATION_SCOPE: BAT1 binding allocation and adapter identity enforcement.
BLOCKS_PRODUCTION: YES.

### G02 — Recovery roots and acknowledged-floor nonregression (P0)
WHY_IT_MATTERS: reclaim cannot trust a latest report that legal recovery can forget.
CURRENT_STATE: target protects selected bank only; store/owner fallback policies differ;
no persisted irreversible deletion floor yet.
REQUIRED_INVARIANT: prepare protects union of recoverable report refs; every legal
root preserves any retirement floor used for destructive actions/ACK responsibility.
DEPENDENCIES: G01; final irreversible floor representation with G06.
HOST_PROOF_REQUIRED: ret banks3 rotating with cp roots2; cut each bank/cp/selector
write; corrupt newest root after ACK; stale report never weakens a committed floor.
HIL_PROOF_REQUIRED: same boundaries in G13.
IMPLEMENTATION_SCOPE: BAT2 non-destructive root selection/ownership closure.
BLOCKS_PRODUCTION: YES.

### G03 — Exact duplicate admission at the journal boundary (P0)
WHY_IT_MATTERS: ids_ early-return bypasses changed-payload conflict checks before ACK.
CURRENT_STATE: exact durable ledger exists, but top-level duplicate fast path bypasses it.
REQUIRED_INVARIANT: same full EventKey plus different canonical content fails closed
through actual production admission; exact duplicate safely ACKs without reducer replay.
DEPENDENCIES: G01 for incarnation binding; G04 lifetime domain.
HOST_PROOF_REQUIRED: HubRuntime/journal changed type/time/payload duplicates before
and after archive/reboot; correct ACK classification, no backend completion confusion.
HIL_PROOF_REQUIRED: delayed conflicting authenticated packet path in G14.
IMPLEMENTATION_SCOPE: BAT1, jointly with binding/admission closure.
BLOCKS_PRODUCTION: YES.

### G04 — Installation/enrollment lifetime identity and versioned handover (P0)
WHY_IT_MATTERS: counter erasure can repeat backend identity and local receipt MAC input;
new epoch1 can also be rejected by old Node recovery domain.
CURRENT_STATE: reboot monotonicity is supported; whole-domain reset/recommission
uniqueness, pending transfer and backend namespace separation are not specified.
REQUIRED_INVARIANT: full effect/EventKey identity has a durable incarnation shared
by Node pending state, authentication, Hub evidence and backend; no relabeling old work.
DEPENDENCIES: G01/G02/G03; G09 budget/design before publishing new metadata.
HOST_PROOF_REQUIRED: erase/recommission same MAC/logical/session/sequence; Hub replacement;
old/new keys and epoch1; pending old keys; backend duplicate/conflict across incarnations;
legacy-to-new migration restart at every publication boundary.
HIL_PROOF_REQUIRED: authorized reset/replacement/handover in G14/G13.
IMPLEMENTATION_SCOPE: BAT3 explicit schema/identity rollout without reclamation.
BLOCKS_PRODUCTION: YES.

### G05 — Commit-owned preparation and physical object release (P0)
WHY_IT_MATTERS: prepared ev objects or released references become boot-blocking orphans.
CURRENT_STATE: ef preparation has narrow recovery allowance; ev and general release
lack bounded authenticated staging ownership and deletion lifecycle.
REQUIRED_INVARIANT: every created object is owned by a root or bounded authenticated
transaction intent; release is conditional and cannot remove any legal root's proof.
DEPENDENCIES: G02; future transaction schema aligns with G04/G06.
HOST_PROOF_REQUIRED: stop after ev/ef creation before cp; fail cp/selector; retry/reboot;
release evidence refs in both roots; shared refs; forged orphan vs legitimate staging.
HIL_PROOF_REQUIRED: G13 creation/commit/deletion boundaries.
IMPLEMENTATION_SCOPE: BAT2 staged recovery contract, with release implementation in BAT5.
BLOCKS_PRODUCTION: YES.

### G06 — Atomic reclaim/receipt lifetime/slot and chunk ownership (P0)
WHY_IT_MATTERS: dense journal and immutable c/ef IDs have no safe delete/reuse semantics.
CURRENT_STATE: no live map, erase API, reuse generation or retirement transaction.
REQUIRED_INVARIANT: H/D/N/F/R/P/T predicates, anti-ABA current-owner match, irreversible
floor, union-root release, fixed pools, restart-idempotent conditional cleanup.
DEPENDENCIES: G01–G05, G07, G09 and G10; G08 for actual target progress.
HOST_PROOF_REQUIRED: each transaction boundary; mixed chunks; lost report/event ACK;
new B vs stale A receipt/cleanup/packet; generations and identity cycles; old format
migration; event map holes; exact state restoration by new provider.
HIL_PROOF_REQUIRED: destructive matrix rows13–17 in G13/G14.
IMPLEMENTATION_SCOPE: BAT5 combine logical release, c deletion and reuse ownership;
never split them into independent erase-only BATs. Chunk ref freshness/digest must
be persisted: current pending ChunkReference.digest is not serialized by checkpoint.
BLOCKS_PRODUCTION: YES.

### G07 — Reducer/history and downstream-effect ownership before event deletion (P0)
WHY_IT_MATTERS: deleting replay inputs can change recovered routine/coverage decisions.
CURRENT_STATE: restore_from_journal reapplies all retained records; opaque reducer_state
exists but production journal flush does not serialize/recover equivalent business state.
REQUIRED_INVARIANT: compact durable reducer/config/history checkpoint and any downstream
outbox ownership are sufficient before reclaiming inputs; no duplicate decision/effect.
DEPENDENCIES: G02/G04/G09; contract must settle history policy P(e).
HOST_PROOF_REQUIRED: current full history vs compacted history equivalent decisions
across reboots/config/old-session events; no replayed alert or lost deadlines.
HIL_PROOF_REQUIRED: root publication/recovery in G13.
IMPLEMENTATION_SCOPE: BAT4 reducer and history ownership, without event deletion.
BLOCKS_PRODUCTION: YES.

### G08 — Authenticated production backend delivery boundary (P0)
WHY_IT_MATTERS: target cannot complete backend work or progress reclaim indefinitely.
CURRENT_STATE: CloudSync + SQLite/outbox host contract exists; ESP32 caller/trusted client absent.
REQUIRED_INVARIANT: only authenticated exact transaction COMMITTED creates c; request
retry uses stable origin identity; server identity proof survives reconnect, no PUBACK shortcut.
DEPENDENCIES: G03/G04/G16; can be a separate parallel implementation scope before BAT8.
HOST_PROOF_REQUIRED: actual client adapter fake server cases, auth failure, lost response,
conflict, backoff/fairness, reconnect, durable c fault after committed response.
HIL_PROOF_REQUIRED: target network/TLS reset path alongside G13; does not certify provider delivery.
IMPLEMENTATION_SCOPE: BAT6 separately authorized backend transport/auth integration.
BLOCKS_PRODUCTION: YES.

### G09 — Reconciled per-phase byte/entry and scratch bound (P1)
WHY_IT_MATTERS: 427 modeled entry headroom is not allocator qualification or transaction capacity.
CURRENT_STATE: mixed historical model and current component ceilings; no certified pool/staging/GC union.
REQUIRED_INVARIANT: actual sizes/keys/versions fit fixed partition through peak migration,
COW and cleanup; reserve preflight forbids beginning an unfinishable transaction.
DEPENDENCIES: BAT3/BAT5 design variables; start budget closure before their implementation.
HOST_PROOF_REQUIRED: trace actual key/object allocation by phase/failure/retry; assert fixed
pool maxima, no lifetime growth, exact new format bounds and forced reserve exhaustion.
HIL_PROOF_REQUIRED: G12 actual allocator/GC entries.
IMPLEMENTATION_SCOPE: BAT0 design-budget contract; BAT7 final executable accounting.
BLOCKS_PRODUCTION: YES.

### G10 — Offline pressure, revoked-domain and numeric-lifetime policy (P1)
WHY_IT_MATTERS: missing coverage/backend success cannot be aged away safely; revocation
lists and signed64 backend counters are also finite.
CURRENT_STATE: bounded Node/Hub admission rejects full queues; no indefinite offline
fairness/handover/revocation compaction or cross-layer counter-range contract.
REQUIRED_INVARIANT: safety under outage with explicit backpressure; conditional progress
when dependencies recover; bounded authenticated retired-domain state; no counter wrap.
DEPENDENCIES: G01/G04/G06/G08/G09.
HOST_PROOF_REQUIRED: ten Nodes, one permanently offline, backend outage, important-event
pressure, repeated replacements, session/report/ordinal range endpoints, restored capacity.
HIL_PROOF_REQUIRED: outage/rejoin fairness and recovery timing in G14.
IMPLEMENTATION_SCOPE: BAT0 policy decisions, BAT7 implementation/integration.
BLOCKS_PRODUCTION: YES.

### G11 — Production rollover and bounded endurance closure (P1)
WHY_IT_MATTERS: generic1000-transition stress does not prove production event reuse.
CURRENT_STATE: all128 completed events remain retained,129 rejected; no release/reuse path.
REQUIRED_INVARIANT:129/256/1000+ events use a fixed key/pool bound; no replay or stranded
responsibility across reused slots and reports after every event.
DEPENDENCIES: G01–G10; hardware stages after host proof.
HOST_PROOF_REQUIRED: actual production runtime/provider repeated reuse, delayed packets,
lost ACK, mixed partial chunks, multi-Node/offline episodes, failure injection and key-count plateau.
HIL_PROOF_REQUIRED: target soak and counter/allocator sampling in G12/G14.
IMPLEMENTATION_SCOPE: BAT8 no constant increase or bypass of retained-history policy.
BLOCKS_PRODUCTION: YES.

### G12 — Physical NVS allocator and GC qualification (P1)
WHY_IT_MATTERS: modeled raw/entry space cannot guarantee writes while flash GC runs.
CURRENT_STATE: target build only, no allocator measurements.
REQUIRED_INVARIANT: worst-phase writes/cleanup complete with measured free-entry/page
reserve; NO_FREE_PAGES/commit errors never erase history or create false completion.
DEPENDENCIES: G09/G11; board/partition available.
HOST_PROOF_REQUIRED: failing allocator adapter and reserve checks; cannot replace hardware proof.
HIL_PROOF_REQUIRED: actual NVS stats/pages at max payload/full/migration/COW/reuse, sustained
replacement GC, abort/reboot, partition bounds and no-free-pages failure behavior.
IMPLEMENTATION_SCOPE: BAT9 physical allocator campaign.
BLOCKS_PRODUCTION: YES.

### G13 — Physical interruption and recovery qualification (P1)
WHY_IT_MATTERS: simulated write faults cannot establish flash power-loss behavior.
CURRENT_STATE: host faults only.
REQUIRED_INVARIANT: every matrix boundary recovers old/new valid ownership or explicit
fail-closed corruption, never false completion/replay/accepted-event loss.
DEPENDENCIES: G01–G12 implementation and board-controlled cuts.
HOST_PROOF_REQUIRED: deterministic cut points persisted in fresh-process fixtures.
HIL_PROOF_REQUIRED: controlled cuts/brownouts around each commit/selector/erase/GC step,
repeated reboot and backend exact-effect counts checked externally.
IMPLEMENTATION_SCOPE: BAT10 exhaustive physical cut matrix.
BLOCKS_PRODUCTION: YES.

### G14 — Physical authenticated ESP-NOW/reboot/handover qualification (P1)
WHY_IT_MATTERS: adapter build and isolated codecs do not prove actual loss/rejoin ordering.
CURRENT_STATE: no live physical packet evidence.
REQUIRED_INVARIANT: enrolled devices advertise/receive epochs, fragment/retry/ACK correctly,
reject stale/spoofed relationships, preserve origins and completion across physical reset.
DEPENDENCIES: G01/G04/G06/G08/G10, G12/G13; hardware available.
HOST_PROOF_REQUIRED: portable adapter harness or fake authenticated radio event-loop tests
for complete install-before-ACK path, not just source-text assertions.
HIL_PROOF_REQUIRED: multi-Node reordered/missing fragments, lost ACK, stale old enrollment,
Node/Hub reset/rejoin/replacement, and post-reuse delayed packets.
IMPLEMENTATION_SCOPE: BAT11 physical protocol/reboot qualification.
BLOCKS_PRODUCTION: YES.

### G15 — Optional redundant legacy-marker retirement (P2)
WHY_IT_MATTERS: clarify effect retirement without deleting event archives or completion proof.
CURRENT_STATE: kind=1 retained safely; no separate effect payload; no capacity benefit to clearing byte.
REQUIRED_INVARIANT: completed-effect predicate and whole-chunk COW preserve c, events/siblings,
all recovery roots and migration compatibility; marker may remain forever safely.
DEPENDENCIES: G05/G06 transaction machinery; G09 staging bound.
HOST_PROOF_REQUIRED: marker clear with incomplete sibling, missing/corrupt c, restart/COW cuts,
report regeneration, unchanged event capacity and no backend retry.
HIL_PROOF_REQUIRED: only if cleanup deployed; add corresponding cuts to G13.
IMPLEMENTATION_SCOPE: optional BAT12 after core closure, not a prerequisite to rollover.
BLOCKS_PRODUCTION: NO.

### G16 — Enforce Hub operation boundary / future EffectId contract (P2)
WHY_IT_MATTERS: c completion cannot stand for provider delivery or a second independent Hub sink.
CURRENT_STATE: one Hub application transaction; backend legitimately creates multiple
per-recipient jobs with its own effect_key/recipient identity and outbox state.
REQUIRED_INVARIANT: c means backend transaction commit only. Additional independently
retryable Hub operation uses EffectId=(full event incarnation, operation kind, destination,
stable instance), separately completed; never infer multi-sink success from one c.
DEPENDENCIES: product/backend boundary and G04; complete documentation/enforcement before G08.
HOST_PROOF_REQUIRED: contract tests distinguish COMMITTED from delivery/PUBACK/human ACK;
reject any future sink reuse without independent identity/completion.
HIL_PROOF_REQUIRED: none for documentation/typed boundary; actual extra sink needs own qualification.
IMPLEMENTATION_SCOPE: BAT0 scope contract and optional BAT13 typed guard, no invented feature.
BLOCKS_PRODUCTION: NO for current one-operation Hub design.

## 11. Dependency graph and recommended BAT order

    BAT0: G09/G10/G16 policy, budget variables, one-Hub-operation boundary
      -> BAT1: G01 + G03 authenticated enrollment and exact duplicate admission
      -> BAT2: G02 + G05 roots, report banks, staged-object recovery
      -> BAT3: G04 versioned incarnation/manifest migration (non-destructive)
      -> BAT4: G07 reducer/history/outbox ownership (non-destructive)
      -> BAT5: G06 logical release + receipt lifetime + anti-ABA pool/slot reuse
      -> BAT7: G09/G10 final capacity/backpressure integration
      -> BAT8: G11 production129/256/1000/endurance
      -> BAT9: G12 physical allocator
      -> BAT10: G13 physical cuts
      -> BAT11: G14 physical protocol/reboot/handover

    BAT1/BAT3 + G16 -> BAT6: G08 authenticated target backend delivery -> BAT8
    BAT2/BAT5 + capacity approval -> optional BAT12: G15 legacy marker retirement
    BAT0 -> optional BAT13: G16 future-sink type guard (no second operation added)

BAT0 is design closure, not permission to implement destructive behavior. BAT3 must
settle format compatibility before BAT5. BAT5 combines event ownership retirement,
receipt release and reuse metadata because independently shipping those deletes
would create ABA or recovery gaps. Physical erases may be resumable later phases
of that same committed transaction; they are not independent eligibility policies.
Keep HIL BAT9/10/11 separate campaigns with one shared evidence ledger. Run each
scope's focused portable tests and required existing gates/target builds; do not
call host simulations physical qualification. No increase of128 is the solution.

NEXT_IMPLEMENTATION_SCOPE: BAT1, after BAT0 decisions are recorded.
SECOND_IMPLEMENTATION_SCOPE: BAT2.
THIRD_IMPLEMENTATION_SCOPE: BAT3; seek explicit schema/identity design approval.
Completed-effect marker cleanup is optional and comes after those safety foundations.

## 12. Readiness definition and audit exit

HOST-READY for bounded current components: existing portable completion, codecs,
recovery and capacity tests pass at the checkpoint. Full durability HOST-READY is
NO until G01–G11 required host invariants are proven through actual production paths,
including bounded reuse and migration. Local externally committed but unreceipted
work may retry only under backend idempotency; no local exactly-once atomic flash/
remote-server transaction is claimed.

TARGET-COMPILE-READY: YES for current ESP-IDF v6.0.3 Node/Hub code; no new build was
needed for documentation. Compile-ready is not delivery integration or physical proof.

HIL-QUALIFIED: NO until G12–G14 campaigns certify actual allocator, every significant
power-cut boundary, physical reboot and authenticated ESP-NOW/rejoin behavior.

PRODUCTION-READY: NO. Require authenticated actual backend delivery, no completed
operation replay after durable receipt, exact duplicate/conflict handling, reset-safe
full identity, bounded pools/counters, safe late/duplicate traffic, reducer/history
ownership, old-install migration, no lifetime key growth, anti-ABA slot/receipt reuse,
safety under outage/backpressure and conditional sustained progress, plus physical
qualification. Backend provider delivery remains its separate idempotent outbox
contract; c receipt is not proof that caregivers received notifications.

Indefinite bounded target operation is attainable with the finite scopes above,
conditional on availability and configured numeric product lifetime. It is not
attainable with the current append-only dense slot/schema model or by removing the
capacity check. No production implementation was started during this audit.
