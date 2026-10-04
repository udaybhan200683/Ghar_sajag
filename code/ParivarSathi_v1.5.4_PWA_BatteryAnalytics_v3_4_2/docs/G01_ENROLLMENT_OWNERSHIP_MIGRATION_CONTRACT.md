# G01 enrollment ownership and migration contract

Status: production implementation PARTIAL. Sections 18–19 settle the bounded architecture; section 20 closes coordinator details against the dirty implementation at committed base 072316a5b376acc16860ee58a2d351a1dce46f6e. Section 20 supersedes conflicting recovery details and estimates, while preserving every hard limit. Earlier sections retain historical reasoning and models.
Scope: G01 only. No G03, reclamation, slot reuse implementation, or retirement-protocol redesign.
The request ended within section 6; this document covers the complete objective stated before it.

## 1. Source constraints and decision

NodeRegistry::EnrolledNode and CommissioningBinding contain no durable enrollment
coordinate. HubRegistryRepository serializes GSRG v1; its generation is the entire
snapshot write counter. It changes on rejoin and cannot identify an enrollment.
HubSecurityLink authenticates a real binding/session, but retirement_enrollment_binding
and DurableJournalSlotStore::append_event independently hash logical_id into slot/gen.
RetirementSnapshot uses a dense index with node_count, and rejects index gaps and
owner changes. Exact evidence contains slot/gen/session/sequence/digest, not device ID.
Existing association revocation is permanent and registry persistence forbids changing
logical ID, MAC, public key, or active installation keys except narrowly unactivated retry.

SELECTED_ENROLLMENT_SLOT_MODEL = ten fixed persisted descriptors, one enrollment
per descriptor; retired ownership remains pinned while referenced. No global monotonic ID.
MAX_ENROLLMENT_SLOTS = 10, matching current Hub capacity.
SLOT_ASSIGNMENT_RULE = lowest NeverOwned or safely Released descriptor; persist
registry authorization and coordinate atomically before enabling transport/admission.
SLOT_RELEASE_RULE = disable active authorization immediately on durable revocation;
release descriptor occupancy only after every recoverable evidence root excludes that
owner. Revoked device IDs remain in the existing revocation list. No release is
implemented or authorized by this contract.
SLOT_REUSE_RULE = increment descriptor generation and atomically install the new
owner only after the above proof. Until future ownership/reclamation support exists,
use NeverOwned slots only; reject replacement/enrollment when all ten are pinned.
This is safe bounded backpressure, not a claim of indefinite replacement capacity.

The slots bound simultaneously retained enrollment owners, not merely active radios.
A replacement can take a different free slot while the old slot remains pinned.
It must not overwrite old retirement evidence to preserve the ten-active-node count.
No inference from logical ID, sorted map order, snapshot generation, or array position.

## 2. Generation and owner identity

GENERATION_TYPE = uint32_t per descriptor, matching current durable coordinate width.
INITIAL_GENERATION = 1; zero denotes NeverOwned only.
GENERATION_INCREMENT_RULE = Released -> Active increments prior generation; never
increment in place while evidence for the old generation remains referenced.
GENERATION_PRESERVATION_RULE = reboot, report changes, ordinary rejoin, transport
session rotation, and authenticated maintenance of the same ownership preserve it.
GENERATION_OVERFLOW_RULE = UINT32_MAX cannot be reused; permanently exhausted slot.
Never wrap or reset generation after ordinary reboot or revocation.

Owner tuple = home/hub relationship + slot + generation + exact device_id/public key
and logical_id. Descriptor pins exact device_id and a 32-byte digest of canonical
identity fields. Full active record remains the authoritative registry relationship.
Digest is consistency/authentication metadata, never a slot allocator. Specify a NEW,
versioned local owner-digest HMAC domain over length-prefixed home, hub, device ID,
public key, logical ID, slot and generation. Existing report HMAC domains are unchanged.
Historical retired descriptors retain the digest and exact device ID; report snapshots
carry the digest. Session counters and transport MAC are not enrollment generations.
Installation-key refresh must not rewrite historical report verification evidence.

G04 lifetime incarnation across total erase is explicitly unresolved. This contract
provides continuity within preserved installation state, not lifetime EventKey uniqueness.

## 3. Authorization lifecycle

| Operation | Required behavior |
|---|---|
| First enrollment | Commissioning proof plus authorized intent; allocate free descriptor, gen1; one authenticated registry write, load/readback verify, then enable session |
| Ordinary reboot/rejoin | Restore exactly persisted coordinates; authenticated fresh session updates last_session only |
| Revoked, not replaced | Commit revocation and Retired state together; remove live session/reassembly; retain all old evidence and descriptor |
| Different device, same logical ID | Commit old revocation and new owner atomically; allocate another free descriptor if old evidence remains; never inherit its generation/report floor |
| Same physical device re-enrolled | Currently revoked IDs forbid this. Keep rejecting; no revocation bypass in G01. A future authorized reset/re-enrollment policy needs a separate incarnation/key/revocation design |
| Same slot, different device | Permitted only after Released proof; generation increments; otherwise reject |
| Logical ID change | Ownership change, not maintenance; old owner retired, new coordinate assigned; current persistence API requires explicit versioned operation |
| Device public key changes | Cryptographic identity changes: require authorized proof/handover and new ownership. A mere session/key refresh is not that operation |
| Session key refresh | Same proven identity/ownership retains coordinate; fresh session and old-session rejection |
| Installation key rotates | Existing activated-key mutation is forbidden. G01 does not introduce rotation; future authenticated maintenance must preserve old evidence verification and invalidate old live sessions |
| MAC changes, same authenticated device | Existing registry forbids mutation. Reject in this BAT; future authorized MAC maintenance can preserve ownership after signed proof, durable update and old-MAC session invalidation |
| Packet after replacement | Reject before journal lookup if its live session does not resolve to current Active descriptor and exact registry identity |

Old evidence is forever labelled its original (slot, generation) while retained.
New owner cannot use old report generation, completion identity, or covered-session floor.
Revocation itself does not assert that old pending events drained or backend effects completed.

## 4. Production boundary contract

Authenticate frame -> resolve session to device/key/MAC -> resolve durable Active
record/descriptor -> validate logical ID and currently authorized descriptor generation
-> validate/inject physical EventKey owner -> admit journal/report.
The journal adapter receives this immutable validated owner context; it never derives it
from event.source_id. Migration uses a separate validated historical-owner context and
cannot impersonate current transport admission. Duplicate lookup must not precede
ownership validation; exact duplicate policy is the separate G03 scope.

Report wire format need not contain generation: installation relationship/session
selects the descriptor on the Hub. Fragment state is keyed by descriptor generation
AND authenticated transport session, reset on owner change. Report ACK remains existing
epoch/report-generation/HMAC. Old sessions and installation keys cannot inject new-owner
reports. No Node EventKey/report/ESP-NOW format change is proposed here.
Completion receipts remain exact EventKey + journal slot HMAC; neither archive nor
receipt is rewritten or deleted by enrollment migration.

## 5. Proposed versioned persistence layout

GSRG v2 keeps existing AEAD header/nonce/wrapping-key/key-name mechanism and existing
record fields. Header version byte becomes 2; decoder accepts v1 read-only and v2.
Append one slot byte to each active record and the following canonical extension:

- extension magic (4 bytes), descriptor count=10 (1), flags (1);
- ten descriptors: state u8 (NeverOwned/Active/Retired/Released), generation u32 BE,
  device_id length u8 plus <=64 bytes, owner_digest[32];
- migration phase u8, Hub epoch u32, base checkpoint generation u64,
  target checkpoint digest[32].

Empty descriptor requires generation0/empty ID/zero digest; Released retains its
nonzero counter and old identity until replacement publication. Active descriptors
must bijectively match active records; no duplicate IDs/coordinates; Retired identities
must be revoked. Released is invalid unless independently proven no root references it.
G01 implementation must reject Released state until the future release mechanism exists.
All invalid or inconsistent authenticated states fail closed; never fallback to hash mapping.

Maximum EXTRA registry bytes: 10 active slot bytes + 10*(1+4+1+64+32) + 6 +45
= 1,081 bytes. Maximum modeled blob-entry delta <=ceil(1081/32)=34 entries under
2+ceil(blob/32). No new registry NVS key is proposed. Existing registry blob cap8192
remains a hard cap; current maximum encoded v1 PLUS1081 must be calculated/tested before
implementation. This is a bound on the proposal, not physical allocator qualification.
Registry lives outside the journal budget; account it in its actual partition, including
NVS replacement/GC scratch. Do not subtract this blindly from journal headroom427.

Persistent retirement snapshots need a v2 representation because sparse registry slots
are not dense report arrival order. Encode count of records, then explicit slot byte
plus existing record; records canonical ascending slot, at most ten Active/Retired owner
records total. An absent slot has no retirement evidence. Same slot/different generation
cannot replace a pinned record. Explicit slots add10 raw bytes per full bank; the domain adds1 (three banks<=33);
the existing exact maximum is6096, so v2 requires a declared6107-byte cap including the new domain byte. This proposal is not permission to change that cap in production. Worst entry delta <=1 per bank.

Transitions/evidence/checkpoints need an explicit versioned coordinate-domain discriminator
(LegacyLogicalHash vs RegistryOwnerV2); reject mixed interpretation. Reserve one byte in
the NEXT schema of each independently decoded such object, not an undocumented spare
field. An individual evidence chunk cannot mix domains. A v2 checkpoint also records the
registry ownership-table digest (32 bytes). Upper modeled increases: <=1 byte/transition,
<=1 byte/evidence chunk, <=33 bytes/checkpoint. Exact schema numbers, maxima and selector
compatibility must be assigned from current codecs in the implementation design review.
No partition resizing/key remapping is proposed. No feature is enabled until the codec
and phase budget tests demonstrate these extensions fit existing caps or an explicit
cap change is reviewed. These are declared format changes, not claimed current support.

## 6. Legacy ownership migration

Do NOT assign existing compressed evidence to whichever current logical-ID owner exists.
Hash collisions, past replacements and revoked devices make that unsafe. Preserve exact
legacy bytes and legacy domain until ownership is positively recoverable.

1. Freeze event admission, reports, ACKs and enrollment changes; no backend requests
   during conversion. Authenticate registry v1, all legal journal roots and snapshots;
   retain archives/receipts. Existing completed receipts must still verify.
2. Build deterministic candidate table: sorted exact active device IDs, then uniquely
   attributable historical owners; allocate lowest slots, generation1. More than ten
   retained owners => migration blocked, no deletion to force fit. Persist candidate
   GSRG v2 phase Prepared with base root identity; it does not enable runtime.
3. Attribute a retained event only from full authenticated archive EventKey and preserved
   registry/revocation history. If the only available information is a revoked device ID
   without authenticated enrollment binding/history, do not invent its public key or
   logical relationship: keep Legacy and stop automatic promotion for that owner.
4. Link legacy exact evidence to one retained authenticated event using session/sequence,
   legacy coordinate AND canonical event digest. Require exactly one match and recovered
   owner proof. Rewrite only a copied evidence object with v2 coordinates; zero/multiple
   matches blocks conversion. Never resolve ambiguity by active logical ID.
5. Reconstruct the complete logical report and verify stored report HMAC under the exact
   preserved enrollment installation key. Match its old digest/coordinate, epoch,
   session and generation. Unique proven owner permits copying the report to explicit
   v2 slot and owner digest without changing report contents or Node report HMAC. Missing
   old key, conflicting candidates or unprovable owner => preserve original snapshot,
   block automatic migration; a fresh current-owner report cannot replace old evidence.
6. Prepare bounded new evidence/snapshot/checkpoint objects without overwriting ANY
   source reachable by any recoverable root. Publish target root and verify selection,
   contents and registry-table digest. Change registry phase to Activated only after
   verification. Runtime requires matching Activated table and target coordinate domain. Subsequent same-table v2 checkpoints may supersede the initial target; the activation digest is provenance, not a requirement to keep selecting that original root forever.
7. Retain legacy evidence after activation until a separately authorized root-release
   contract proves removal safe. No source cleanup or effect/event retirement in G01.

Registry Prepared + legacy root => resume conversion or remain fail closed. Prepared +
verified target root => finish activation. Activated + missing/mismatched target table
or legacy fallback root => fail closed, never admit under the wrong coordinate domain.
Every retry deterministically uses the same candidate table; ordinary reboot must not
reallocate or increment it. No partial conversion success ACKs.

IMPORTANT: safe multi-root preparation capacity and staged-object recovery are open G02/G05
issues. G01 design does not silently solve them. Implementation may support v2 fresh
installations and detection/fail-closed migration first, but must report legacy migration
PARTIAL until actual safe publication is proven. If staging cannot fit fixed pools or
recovery rejects prepared objects, STOP rather than overwrite legacy roots. Registry-only
migration must not claim end-to-end G01 closure for populated legacy installations.

This is backward-compatible READING/migration, not downgrade-write compatibility.
Old firmware rejects GSRG v2; firmware rollback across activation must be prevented or
explicitly routed to compatible firmware. Never restore a stale v1 blob to clear the barrier.

## 7. Required deterministic implementation tests

- Ten arbitrary logical IDs/arrival orders; no hash collision ownership transfer.
- Persist/recreate provider: same slots/gens after reboot and ordinary rejoin.
- Unknown, quarantined, revoked and wrong-logical sender rejected before journal.
- Replacement publishes revocation/new coordinate together; old live session rejected.
- Old archive/receipt/report belongs only to old coordinate after replacement.
- Pinning/capacity and overflow fail closed; no release/reuse implemented by this BAT.
- GSRG v1 empty migration; active v1 with exact retained events and verifiable reports.
- Legacy hash collisions, missing historical keys, ambiguous compressed evidence,
  more than ten retained owners: preserve source and refuse automatic promotion.
- Cuts before/after Prepared write, each copied object, target-root publication,
  activation write; new provider reconstructs phase or fails closed without success ACK.
- Snapshot gaps and out-of-order reports handled via explicit slot; revoked report cannot
  modify new owner; duplicate/lost ACK and existing report format unchanged.
- Legacy/v2 mixed domains and corrupt table digest rejected; completion survives every cut.
- Exact maximum bytes/entries in every preparation/recovery phase; no orphan ownership
  acceptance without the separately reviewed G02/G05 contract.

Host tests prove deterministic authorization, codecs and restart model. Physical NVS
atomicity/GC, power cuts and ESP-NOW replacement remain HIL obligations. No production tests or target builds were run. The embedded design model below is executed separately.

## 8. Implementation decision

Contract is ready for review and codec/budget planning. Full populated-install migration
is explicitly gated on G02/G05 safe preparation/root ownership; ambiguous historical
ownership requires a reviewed service migration, not evidence reassignment or reset.
No production behavior, persistent format, test, retention ceiling, or receipt changed.
G03 and every reclamation scope remain untouched. The continuation requests a commit only for a sufficiently closed design. G02/G05 staging and capacity remain substantial enablement blockers; this document stays provisional and uncommitted.


## 9. Continuation: slot pinning and product capacity

This section completes the truncated request; earlier sections are preserved and
refinements below supersede estimates or unspecified details above.

SLOT_PINNING_MODEL = single retained ownership generation per descriptor.
MAX_SIMULTANEOUS_ACTIVE_ENROLLMENTS = 10, but actual available active capacity is
10 minus retained retired descriptors; Active + Retired + exhausted descriptors <=10.
MAX_RETAINED_OLD_GENERATIONS = 10 absolute; <=10-Active-Exhausted at any instant.
Total concurrently represented generations <=10. An enrollment may own many events,
but their archive/evidence remains bounded by the existing128-event ceiling.

A pinned slot CANNOT host a second generation in this model. Supporting two generations
would require another bounded owner/snapshot representation; that is not this selection.
Ten active owners leave no spare replacement slot. Revoking one changes it to Retired,
not Free: nine Active + one Retired is still full. Reject replacement before mutating
registry if a free descriptor is unavailable; preserve the original active owner unless
an independently authorized revocation is explicitly requested. Repeated replacements
can exhaust slots with fewer than ten active devices. This fail-closed tradeoff is
intentional for the interim design, but requires product review; it does not meet a
requirement for ten active Nodes PLUS seamless retained-history replacement headroom.
If that product requirement exists, reopen the bounded descriptor/snapshot capacity
contract BEFORE implementation, rather than quietly evicting an old generation.

PIN_RELEASE_CONDITION = committed proof that every recoverable root, journal tail,
archive/dedupe/report/legacy migration reference, and authorized retry path excludes
that ownership, with historical records independently attributable if retained. Also
invalidate volatile sessions/reassembly and preserve revocation. Merely receiving a
report, ACK, or backend completion is NOT this proof. Current event retention means
that proof is generally unavailable; this BAT authorizes no release.
REPLACEMENT_WHEN_ALL_SLOTS_PINNED = reject without partial replacement publication.
SLOT_EXHAUSTION_FAIL_CLOSED = YES. No aging, timeouts, generation overwrite or GC.

## 10. Complete ownership-bearing object audit

Paths abbreviated S=firmware/hub/components/storage,
R=firmware/hub/components/registry, T=firmware/hub/target/esp32,
C=firmware/common/transport. Names identify exact source files, not inferred owners.

| Structure | Source path | Current coordinate/encoding | Legacy hash? | Migration required / new coordinate / method | Crash commit boundary |
|---|---|---|---|---|---|
| Registry and bindings | R/registry_persistence.cpp; R/node_registry.hpp | GSRG v1; full device identity but no slot/gen | No explicit coordinate | GSRG v2 table; preserve keys/revocations/sessions; deterministic physical-owner assignment | Verified Prepared blob, then verified Activated blob |
| Durable event transitions | S/durable_transition.cpp; S/durable_journal_slot_store.cpp | GDT1 schema2 (schema1 readable), exact EventIdentity plus pseudo slot/u32gen and content digest | Yes | Proposed schema3, explicit domain byte RegistryOwnerV2; copy/revalidate exact owner; legacy remains schema1/2 | Target checkpoint/covered tail plus Activated registry barrier |
| Exact dedupe chunks | S/durable_transition.cpp | GDE1 schema1; slot/gen/session/seq/digest, no physical ID | Yes | Proposed schema2 + domain byte; translate only through unique matching retained event and proven historical owner | New chunk digest referenced by verified target root |
| Checkpoint references | S/durable_transition.cpp | GCP1 schema2, old schema1 frontiers readable; evidence refs and report ref; reducer opaque | Transitively, and legacy schema1 frontiers | Proposed schema3 + domain byte + ownership-table digest32; all references/domain consistent; unverified schema1 frontier cannot establish ownership | Verified checkpoint selection; all legal fallback roots must respect migration barrier |
| Pending effect/archive chunks | S/durable_transition.cpp; S/durable_journal_slot_store.cpp | GEC1 schema1; event archive payload + stable journal slot in effect ID; legacy kind1 completion | No explicit enrollment coordinate | Keep exact payload/kind/slot; target root associates full EventKey with proven registry table owner; never alter history to make attribution possible | Root references unchanged authenticated archive; owner context activation |
| Independent completion receipts | S/journal.cpp; S/durable_journal_slot_store.cpp | c000–c127; exact slot/EventKey HMAC32 | No | No rewrite; verify against same archived EventKey and slot before/after conversion | Existing immutable receipt commit/readback; no deletion |
| Legacy event slots and completion markers | S/journal.cpp; S/durable_journal_slot_store.cpp::migrate_legacy_journal | AEAD event blob plus kind1 archive marker/legacy receipt | Not directly | Existing journal migration separate; preserve exact event/completion, resolve historical owner or block | Existing legacy migration verification; NOT a G01 ownership inference |
| Retirement snapshot banks | S/node_retirement_snapshot.cpp | GRS1 schema1, dense index implicit slot, pseudo binding digest/gen | Yes | Proposed schema2 + domain byte + explicit slot per record; sparse canonical order; verify original report HMAC and exact owner before copy | Prepared/readback bank, verified target root, registry activation |
| Retirement report and report ACK | C/node_retirement_protocol.cpp; Node recovery repository | Wire epoch/report generation/pending keys/HMAC; no enrollment coordinates | No | No wire change. Authenticated Hub registry context selects owner; preserved report content/HMAC | Existing report snapshot durable selection before authenticated ACK |
| Selector records | S/durable_transition.cpp | Authenticated root selection/generation/epoch; indirect ownership through selected checkpoint | Transitively | Existing selector format can select new codec root; validate registry barrier/domain/table digest before Ready; fallback mismatch fails closed | Existing selector commit + verified target-root recovery |
| Epoch/owner inventory | S/hub_durability_owner.cpp; provider inventory | Epoch and physical object classification, not enrollment coordinate | No direct hash | Preserve epoch; recognize staged domain objects only under G05 commit-owned inventory; reject orphan objects | Owner recovery must prove barrier and object ownership before Ready |
| Completion bitmap | S/durable_transition.cpp | GBM1 schema1; mapping digest/bits; no production effect mapping | No direct hash | No migration/reinterpretation; any generic mapping reliant on legacy root stays legacy | Existing bitmap/root association; never a substitute for c receipts |
| Migration metadata | Existing journal migration; proposed registry phase/base root digest | Legacy journal source/phase; no enrollment table today | May reference legacy objects indirectly | GSRG extension holds ownership migration phase; separate old/new domains; never reuse unrelated legacy migration marker | Registry Prepared/Activated writes plus exact target-root selection |
| Backend durable event identity | S/journal.cpp; CloudSync; server durable_event_commits | Full EventKey; completion and server idempotency, no pseudo coordinate | No | No EventKey/backend PK change; preserve exact operation identity | Existing server transaction/local receipt; not proof of enrollment incarnation |
| Persisted Node recovery | firmware/node/components/storage/node_recovery_persistence.cpp | Recovery v3 pending EventKeys, Hub epoch, report gen, association-scoped state | No | No change in G01; authenticate relationship; G04 reset-incarnation remains open | Existing recovery save/readback |

No caller may assign a RegistryOwnerV2 coordinate by invoking the old derivation.
Legacy derivation is permitted ONLY in the read-only migration verifier, never creation
of new admission/report evidence. Hash-derived legacy bindings are domain0; authoritative
registry bindings are domain1. Old record versions imply domain0. New versions encode
u8 domain=1 and reject0 for new writes. RegistryOwnerV2 root cannot reference domain0
compressed evidence or snapshot. Archives/c receipts are coordinate-neutral and may be
shared if their exact historical-owner attribution is proven. Unsupported schema/domain
or unavailable attribution closes admission; no defaulting to domain1.

The migration source is durable_journal_slot_store.cpp::migrate_legacy_journal. Inventory is T/nvs_store_inventory.cpp; selectors/checkpoint recovery are in S/durable_transition.cpp. This table distinguishes generic unused primitives from production.

## 11. Exact registry encoding and corrected storage arithmetic

All integer fields BE. GSRG v2 AEAD header is exactly28 bytes:
magic GSRG[4], version=2[u8], reserved=0[u8], snapshot_generation[u64], nonce[12],
ciphertext_length[u16]; entire header is AAD. Ciphertext is encoded plaintext, followed
by16-byte GCM tag. Wrapping key and gs_registry/snapshot key unchanged; no plaintext
secret storage. Old v1 decoder authenticates the same header and validates full record.
V2 decoder rejects unknown states/flags/trailing bytes and validates the entire table.
Snapshot generation remains a monotonically increasing write counter, NOT enrollment gen.

V2 plaintext = v1 fields in their existing order, with slot[u8] immediately after each
active-record installation key; then extension magic GOWN[4], descriptor_count=10[u8],
flags=0[u8], ten descriptors indexed by their encoded order (stable physical descriptors,
NOT runtime owner inference), then phase[u8], source_epoch[u32], source_checkpoint_gen[u64],
target_checkpoint_digest[32]. Phase codes:1 Prepared,2 Activated;0 only for freshly
constructed candidate before persistence, never a persisted Ready state. Prepared target
digest is zero until target bytes exist; root publication is detected through schema3
and matching table digest, then its exact authenticated checkpoint digest is recorded
in Activated state. Registry updates after activation retain this migration provenance;
future ownership changes require a fresh consistent table/root update barrier, not an
uncoordinated table-digest mutation. That runtime transaction is also a G02/G05 dependency.

Descriptor state codes0 NeverOwned,1 Active,2 Retired,3 Released; layout exactly
state[u8], gen[u32], ID_length[u8], ID bytes[<=64], owner_digest[32]. Lowest slot is
selected from validated state, not ID hashes. Descriptor index itself is its stable slot.
Retired descriptor must retain nonzero gen and exact identity/digest. Revocation IDs
remain in the v1-format list; do not drop them. The already-declared new owner-digest
HMAC uses domain ASCII gs-enrollment-owner-v2 followed by canonical length-prefixed
home/hub/device/logical IDs, fixed public key65, slot[u8], gen[u32]. This changes ONLY
local owner binding semantics, not existing event receipt/report HMAC domains. Archived
logical relationship needs proven historical record to reconstruct this digest.

OLD_REGISTRY_MAX_BYTES (target ten active + ten revoked) =
44 AEAD +132 installation/counts +10*317 active +10*65 revoked =3996.
Active max317 =65 device string +3*25 strings +65 device key +6 MAC +8 session
+1 quarantine +65 Hub key +32 installation key. Two home/Hub strings max130;
counts2. Revoked ID max65. These are codec maxima, not current allocated bytes.
NEW_REGISTRY_MAX_BYTES =3996 +1081 =5077 (<8192 unchanged cap).
ADDITIONAL_BYTES_PER_ENTRY =1 active slot byte; separate descriptor maximum102.
TOTAL_ADDITIONAL_REGISTRY_BYTES =10 +10*102 +6 +45 =1081.
Modeled e(blob)=2+ceil(blob/32): old127, new161, delta34; namespace separate.
Registry default nvs partition is24576 bytes (Hub partitions.csv), distinct gs_journal.
Full partition budget must include other security keys; this task does not certify it.

REGISTRY_STEADY_STATE_ADDITIONAL_BYTES =1081 maximum versus maximum v1.
REGISTRY_MIGRATION_PEAK_ADDITIONAL_BYTES =5077 modeled old/new blob coexistence
versus old3996; peak9073, entries288 versus127, extra161. This is NVS replacement
space, not a proposed second registry key. GC/page reserve and repeated failed writes
are NOT bounded by summing live blob sizes; physical peak requires G09/G12 verification.
If implementation adds a backup registry key, recalculate it explicitly; none approved.

Retirement max verified from source:18 header +10*(93+32*16) +28 AEAD =6096.
Earlier explicit-slot delta10 omitted a domain byte; corrected v2 max6107 =6096+10+1.
Evidence chunk max321 (old320+1); transition max1333 (old1332+1);
checkpoint max4547 (old4514+1 domain+32 table digest). These are proposed envelopes,
NOT changed production constants. They require explicit reviewed codec-cap updates.
Archive1260, receipt32, report wire542, bitmap384, epoch and key mapping unchanged.

For the audit's retained-root inventory A32/E33/C128/R3/K2/T4, proposed steady raw
delta =33 +33*1 +3*11 +4*1 =136 bytes; checkpoint delta33 each =>66, so total
33+33+66+4 =136. Entry delta =33 evidence chunks (320->321 crosses32 boundary)
+2 checkpoints (4514->4547 crosses32 boundary) =35. Snapshot6096->6107 still193
entries; transition1332->1333 still44. No registry bytes charged to gs_journal.
GS_JOURNAL_STEADY_STATE_ADDITIONAL_BYTES =136 in this retained-root model.
Reconciled proposal model =89630 bytes/3275 entries; free41442 bytes/757 entries,
byte margin31.6177%, entry margin18.7748%. This is already below20% entry margin;
DO NOT authorize production migration from these figures.
Historical87314/3605 plus this delta gives87450/3640, free43622/392,
byte margin33.281%, entry margin9.7222%; mixing those families is only an illustration,
not a new certified production total. The prior baseline is not20% after receipts.

Migration peak formula (source objects cannot be destroyed):
DeltaB =136 +321*E_stage +6107*R_stage +4547*K_stage +1333*T_stage +manifest_bytes.
DeltaEntries =35 +13*E_stage +193*R_stage +145*K_stage +44*T_stage +manifest_entries.
E_stage<=32, R_stage<=1 target snapshot, K_stage<=2 destination roots,
T_stage<=4 translated tail transitions; plus a still-unspecified bounded staged-object
manifest under G05. Illustrative all-destination coexistence adds30805 bytes/1075 entries before the136-byte/35-entry steady delta and manifest. Reconciled live baseline plus these proposed allocations is120435 bytes/4350 modeled entries: entry capacity4032 is exceeded by318 even BEFORE manifest/GC. This all-copy plan cannot be enabled. A safely bounded incremental/root-rotation plan must be specified under G02/G05/G09; exact safe key pool/publication order is NOT defined in current provider. No cap may
be silently multiplied. Some old/new cp/tail slots physically alias, making such a
copy impossible without staged keys and ownership support; that is an enablement blocker.
Cleanup steady state is the above live model only AFTER root exclusion permits release;
this task permits no cleanup and therefore no production peak certification.
GS_JOURNAL_MIGRATION_PEAK_ADDITIONAL_BYTES = formula above; NOT_CERTIFIED.
GS_JOURNAL_TOTAL_MAX_BYTES / margins / NVS maxima are planning models, NOT approved
new production constants. Exact phase budgets, manifest/key inventory and GC reserve
must close under G05/G09 before enabling populated migration. No partition resize.

## 12. Crash/state machine and precise dependencies

Registry Prepared preserves all original active identities/keys/revocations and source
root identity. Table digest hashes canonical descriptor/active-owner association only;
exclude snapshot generation, last_session, migration phase and target-root digest to
avoid circular hashes. Enrollment changes freeze during conversion. Future changes
must publish matching root/table as one recoverable authorization transaction.

| Boundary / persisted state | Authoritative source | Admission/reports | Recovery/resume and rollback | Deletion |
|---|---|---|---|---|
| Before candidate | V1 registry + legacy roots | Closed once migration begins; v1 firmware remains baseline before upgrade | Authenticate source; regenerate deterministic candidate | None |
| Prepared candidate before translation | Preserved v1 fields/legacy roots; candidate NOT live | Closed | Reload candidate; verify source identity; resume; logical cancellation only if no target published | None |
| During any copy, including partial copies | Legacy roots, staged copies not authoritative | Closed | Verify exact staged contents/ownership; reuse identical copies; conflict/corrupt copy fails closed | None |
| All copies complete, before target checkpoint | Legacy roots | Closed | Resume root publication only after inventory/source/destination checks | None |
| Target root selected, before registry Activated | Target is prepared migration evidence, registry barrier not passed | Closed | Verify matching table digest and every reference; finalize Activated registry; no rollback to legacy Ready | None |
| Registry Activated verified | Matching v2 table/root only | Open ONLY after fresh runtime authorization/recovery validation | Reconstruct v2; never reinterpret legacy coordinate | None in G01 |
| After Activated, legacy artifacts remain | Matching v2 table/root | Open if all inventory ownership verified by G05 | Legacy objects are pinned migration sources, not competing active owners | None until separate release contract |
| Persisted but write returned failure | Read/authenticate actual persisted phase/root | Closed until exact status resolved | Old valid state or verified new valid state; no reliance on return value alone | None |
| Reboot with both domains | Phase+schema+table digest, not highest number alone | Closed unless Activated + fully matching v2 root | Resume deterministic work; v1 fallback cannot create v2 Ready | None |
| Corrupt candidate | No safe candidate authority | Closed | Service recovery from verified preserved source ONLY before any target activation; no guessed repair | None |
| Corrupt source/target root | No unverified proof allowed | Closed | Valid allowed root only if matching barrier/evidence; after activation legacy fallback is fail closed | None |

MIGRATION_PHASES = VerifiedLegacy -> Prepared -> Copying -> TargetVerified -> Activated;
Copying/TargetVerified are derived from durable object/root facts; registry phase is
Prepared until final verified switch. Ready is derived, never a standalone volatile flag.
MIGRATION_AUTHORITY_SWITCH_POINT = Activated registry readback AND exact authenticated
selected v2 root with matching ownership-table digest and complete ownership inventory.
MIGRATION_RESTART_RULE = authenticate persisted state and resume same table/coordinates;
never increment enrollment gen or allocate different slots on restart.
MIGRATION_ROLLBACK_RULE = no old-firmware downgrade; logical cancellation only before
publication, with all preserved legacy sources verified and staged ownership understood.
If G05 cannot account for staged objects, stay closed instead of rolling back Ready.
MIGRATION_CLEANUP_RULE = none in G01; no deletion until separate root-release proof.
MIGRATION_CRASH_MODEL_READY = PARTIAL; required outcomes specified, actual publication
and staged-key inventory under G02/G05 are not closed. No hardware atomicity claim.

G02 = protect ALL legal checkpoint/report roots and prevent fallback regression of
acknowledged evidence. G01 depends on G02 when preparing target ret bank/checkpoint,
when publishing matching table/root, and when selecting fallback after registry activation.
Current adapter protects selected report bank only; old fallback may lose its snapshot.
A migration cannot overwrite that source bank or enable a root with regressed proof.
G05 = prepared-object ownership and physical release recoverable under durable owner.
G01 depends on G05 immediately upon writing copied ev chunks/staged roots or retaining
legacy sources after target publication. Current inventory_chunks_owned only accepts
selected/alternate root refs plus a narrow prospective ef exception; an unreferenced
prepared ev can make restart fail. Migration registry phase is NOT currently consulted.

G01_IMPLEMENTABLE_BEFORE_G02 = PARTIAL: registry codecs, fresh-install allocation and
fail-closed detection can be developed/tested; no populated production migration.
G01_IMPLEMENTABLE_BEFORE_G05 = PARTIAL: same; no production evidence staging.
Registry-format implementation can be separate from evidence conversion, but must
report PARTIAL and reject existing populated v1 startup, not discard its evidence.
G01_MIGRATION_ENABLEMENT_BLOCKED_BY = G02 root/barrier + G05 staged ownership + G09
phase budget + exact historical attribution + product approval of pinned-slot capacity.
Production migration MAY NOT be enabled before those prerequisites close.

## 13. Replacement isolation and wire contract

Given old owner(3,7), retain its archive, exact ledger and report with old owner tuple.
New device at free(5,1) gets only evidence admitted through its own current authenticated
binding. Reusing logical ID does not change either tuple. The table maps old device ID
to Retired(3,7), new device ID to Active(5,1). Report payload contains no slot/gen; Hub
context selects(5,1) before reassembly and installation. Old session/key resolves no
Active registry owner and is rejected before duplicate/report logic. New physical
EventKey cannot claim old device ID: Hub validates/injects authenticated physical ID.

If future proven release permits(3,8), NO live/recoverable old(3,7) owner references may
remain in this selected single-generation model. A delayed old packet cannot use new
key/session; gen7 does not equal8. No old report floor is copied to8. Reboot reconstructs
the same authenticated descriptors/root barrier; it does not assign by report arrival.
REPLACEMENT_ISOLATION_INVARIANT = (domain,slot,gen,exact physical/logical relationship)
is immutable for every retained evidence item; owner changes cannot relabel it.

AUTHORITATIVE_RUNTIME_BINDING = authenticated transport device/key/session -> exact
Active registry record -> persisted descriptor -> nonzero gen -> validated evidence context.
PAYLOAD_COORDINATES_TRUSTED = NO; existing Node report carries no ownership coordinates.
NODE_REQUIRES_SLOT = NO. NODE_REQUIRES_GENERATION = NO.
PROTOCOL_FORMAT_CHANGE_REQUIRED = NO for existing event/report wire. Persistent-format
changes ARE required on Hub. Hub validates logical claims; source physical identity is
validated/injected from authentication; no payload-only owner or second authentication.

G03_ASSUMPTIONS_CHANGED_BY_G01 = NO to exact immutable event-content rule. Registry
owner context validates admission FIRST and is stored as durable evidence ownership;
it is not a new mutable field added to EventKey or a substitute for canonical content.
Duplicate from wrong owner rejects before comparison. Same full EventKey+same immutable
content stays duplicate; same key+different content stays conflict. G03 implementation
must not compare session/retry/ACK/report/processing fields as new immutable content.

## 14. Readiness and review decision

EVIDENCE_MIGRATION_TABLE_COMPLETE = YES for inspected ownership-bearing families;
proposed migration machinery is not present in code.
G01_ARCHITECTURE_READY = NO for full populated-install closure.
READY_FOR_G01_IMPLEMENTATION = PARTIAL for codecs/model/fresh-install-only preparation;
NO for populated production migration or claiming G01 closed.
OPEN_TECHNICAL_GAPS = G02 root/barrier, G05 staged inventory/transaction, G09 peak/GC
capacity, historical ownership ambiguity, pinned-slot product capacity approval.
NEXT_RECOMMENDED_SCOPE = close G02/G05 migration preparation/root contract and bounded
phase budget BEFORE enabling ownership migration; independent codecs may be a narrow
non-production preparation BAT. Do not implement G03 or expand reclamation here.

Document remains PROVISIONAL: substantial G02/G05 ambiguity concerns exact staged keys,
publication and capacity. Per continuation commit policy, do not commit/push merely to
produce a checkpoint. All source and production tests are untouched.


## 15. Executable host architecture model (embedded, not production)

The code below is a deliberately small abstract contract model. Its serialized state
represents durable facts; each test/restart reconstructs a new object from serialization.
It does NOT implement GSRG codecs, cryptographic authentication, real selectors,
flash staging or garbage collection. G02/G05/budget flags are explicit assumed
prerequisites, not conclusions proved by this model. A successful model Ready state
therefore does NOT imply production readiness.

Run by extracting this fenced Python block and executing it in memory; no extra file
or production test change is needed. Cases1–15 correspond to the continuation request.

```python
import json
import unittest

MAX_GEN = (1 << 32) - 1

class Contract:
    def __init__(self, image=None):
        self.state = json.loads(image) if image else {
            'owners': [], 'phase': 'legacy', 'copies': 0,
            'root': 'legacy', 'proofs': False, 'sound': True}
    def image(self):
        return json.dumps(self.state, sort_keys=True)
    def reboot(self):
        return Contract(self.image())
    def allocate(self, device, logical):
        if len(self.state['owners']) >= 10:
            raise ValueError('pinned capacity')
        if any(o['state'] == 'active' and (o['device'] == device or
               o['logical'] == logical) for o in self.state['owners']):
            raise ValueError('duplicate active owner')
        self.state['owners'].append({'device': device, 'logical': logical,
            'slot': len(self.state['owners']), 'gen': 1, 'state': 'active'})
    def migrate_registry(self, entries):
        for device, logical in sorted(entries):
            self.allocate(device, logical)
        self.state['phase'] = 'prepared'
    def revoke(self, device):
        next(o for o in self.state['owners'] if o['device'] == device)['state'] = 'retired'
    def accepts(self, device, slot, gen):
        return any(o['state'] == 'active' and (o['device'],o['slot'],o['gen']) ==
                   (device,slot,gen) for o in self.state['owners'])
    def advance(self, boundary):
        if boundary == 'partial': self.state['copies'] = 1
        elif boundary == 'copied': self.state['copies'] = 2
        elif boundary == 'root':
            if self.state['copies'] != 2: raise ValueError('incomplete')
            self.state['root'] = 'v2'
        elif boundary == 'activated':
            if self.state['root'] != 'v2' or not self.state['proofs']:
                raise ValueError('unproven publication')
            self.state['phase'] = 'activated'
    def ready(self):
        return self.state['phase'] == 'activated' and self.state['root'] == 'v2' and \
            self.state['copies'] == 2 and self.state['proofs'] and self.state['sound']

def unique_owner(candidates):
    if len(candidates) != 1: raise ValueError('ambiguous legacy owner')
    return candidates[0]

def next_generation(gen):
    if gen == MAX_GEN: raise ValueError('exhausted')
    return gen + 1

class ModelTests(unittest.TestCase):
    def one(self):
        m=Contract(); m.migrate_registry([('A','room')]); return m
    def test_01_single_v1(self):
        self.assertEqual(self.one().state['owners'][0]['slot'],0)
    def test_02_unique_deterministic(self):
        a=Contract(); b=Contract()
        a.migrate_registry([('B','b'),('A','a')]); b.migrate_registry([('A','a'),('B','b')])
        self.assertEqual(a.image(),b.image())
        self.assertEqual([o['slot'] for o in a.state['owners']],[0,1])
    def test_03_reboot(self):
        m=self.one(); self.assertEqual(m.image(),m.reboot().image())
    def test_04_rejoin_preserves(self):
        m=self.one(); old=m.image(); self.assertTrue(m.accepts('A',0,1))
        self.assertEqual(old,m.image())  # auth/session refresh does not mutate ownership
    def test_05_revocation_preserves(self):
        m=self.one(); m.revoke('A'); o=m.reboot().state['owners'][0]
        self.assertEqual((o['slot'],o['gen'],o['state']),(0,1,'retired'))
    def test_06_replacement_isolation(self):
        m=self.one(); evidence=('A',0,1); m.revoke('A'); m.allocate('B','room')
        self.assertFalse(m.accepts(*evidence)); self.assertTrue(m.accepts('B',1,1))
        self.assertEqual(evidence,('A',0,1))
    def test_07_stale_generation(self):
        m=self.one(); self.assertFalse(m.accepts('A',0,0))
        m.state['owners'][0]['gen']=8
        self.assertFalse(m.reboot().accepts('A',0,7))
        self.assertTrue(m.reboot().accepts('A',0,8))
        m.revoke('A'); self.assertFalse(m.reboot().accepts('A',0,1))
    def test_08_logical_reuse(self):
        m=self.one(); m.revoke('A'); m.allocate('B','room')
        self.assertEqual([o['slot'] for o in m.state['owners']],[0,1])
    def test_09_pinned_exhaustion(self):
        m=Contract()
        for i in range(10): m.allocate(str(i),str(i)); m.revoke(str(i))
        before=m.image()
        with self.assertRaises(ValueError): m.allocate('new','new')
        self.assertEqual(before,m.image())
    def test_10_overflow(self):
        self.assertEqual(next_generation(1),2)
        with self.assertRaises(ValueError): next_generation(MAX_GEN)
    def test_11_crash_phases(self):
        m=Contract(); self.assertFalse(m.reboot().ready())
        m.migrate_registry([('A','a')]); m.state['proofs']=True
        for boundary in ['prepared','partial','copied','root','activated']:
            if boundary!='prepared': m.advance(boundary)
            m=m.reboot()
            self.assertEqual(m.ready(),boundary=='activated')
        # persisted-but-returned-failure reads actual durable activated image
        self.assertTrue(m.reboot().ready())
        m.state['sound']=False; self.assertFalse(m.reboot().ready())
    def test_12_ambiguous(self):
        with self.assertRaises(ValueError): unique_owner([])
    def test_13_collision(self):
        with self.assertRaises(ValueError): unique_owner(['A','B'])
    def test_14_registry_only_not_ready(self):
        m=self.one(); self.assertFalse(m.reboot().ready())
        m.advance('partial'); m.advance('copied'); m.advance('root')
        with self.assertRaises(ValueError): m.advance('activated')
    def test_15_complete_conditionally_ready(self):
        m=self.one(); m.state['proofs']=True
        for b in ['partial','copied','root','activated']: m.advance(b)
        self.assertTrue(m.reboot().ready())
        self.assertEqual(unique_owner(['A']),'A')

unittest.main(argv=['embedded-g01-model'], exit=False)
```

HOST_MODEL_RESULT = PASS: 15 abstract model tests executed on 2026-10-03. This is architecture-model evidence
only; no production migration/authentication or HIL qualification is asserted.


### Final planning values (not certified production limits)

GS_JOURNAL_TOTAL_MAX_BYTES =89630 retained-root model; full migration peak NOT_CERTIFIED.
GS_JOURNAL_MARGIN_BYTES =41442, MARGIN_PERCENT =31.6177% for that model.
GS_JOURNAL_NVS_USED_ENTRIES_MAX =3275 retained-root model, not physical maximum.
GS_JOURNAL_NVS_FREE_ENTRIES_MIN =757 modeled, ENTRY_MARGIN_PERCENT =18.7748%.
The illustrative all-copy migration reaches4350 entries (>4032), so NO existing20%
safety margin is claimed or silently spent. Manifest and GC remain unbudgeted.
Proposed non-migration staging variant: previous95972 plus136 live delta plus34
(cp/evidence staging envelope growth) =96142 bytes; entries3452+35+2=3489,
free34930 bytes/543 entries (26.6495% byte,13.4673% entry margin). It is not a
populated-migration peak or release approval. Physical allocation still requires HIL.

No production implementation, G03, report-wire redesign, retirement, reclamation,
receipt deletion or slot reuse was performed. The existing audit document is unchanged.


## 16. G02/G05 bounded publication continuation (supersedes full-copy proposal)

Status: concrete candidate contract with quantified blockers; NOT implementation-ready.
Existing sections remain as design history. The rules below replace full-copy staging,
extra per-object domain bytes, and the6107-byte snapshot proposal. No production changes.

### Exact invariants and authority

G02_EXACT_INVARIANT: a migration root may become selected only after every referenced
object is authenticated/read back, and every acknowledged retirement floor of any legal
fallback is retained. Before a batch publishes, source roots and their report banks
remain immutable. After publication, fallback may select only a root with at least the
published migration frontier and all prior acknowledged floors; otherwise fail closed.
A valid root is not enough: it must be authorized by the publication barrier.
G02_SOURCE_PATHS: S/durable_transition.cpp::DurableStore::recover/checkpoint;
S/node_retirement_snapshot.cpp::prepare_bank/load; T/hub_runtime_adapter.cpp report
referenced-bank mask; S/hub_durability_owner.cpp::recover/inventory_chunks_owned.
G02_FAILURE_MODE: current recover can select highest valid cp without a valid selector;
current report preparation protects only selected bank, not every fallback reference.
These permit candidate selection or fallback proof loss if migration uses current code.

G05_EXACT_INVARIANT: every stored staged object has a bounded authenticated intent
naming its exact key, identity, source root, target digest and phase BEFORE creation;
recovery recognizes only those intents or published-root references. Release occurs
only after all authorized roots exclude the exact source and the publication floor is
persistent. Presence alone never grants ownership; unknown/conflicting objects fail closed.
G05_SOURCE_PATHS: S/durable_transition.cpp::checkpoint (ev write before cp/selector);
S/hub_durability_owner.cpp::inventory_chunks_owned; T/nvs_store_inventory.cpp;
T/nvs_durable_key_codec.cpp; T/nvs_durable_blob_store.cpp.
G05_FAILURE_MODE: an ev copied before root publication is currently unowned at reboot;
reference removal leaves stored objects that inventory rejects. The provider lacks a
commit-owned erase interface and no third cp key is currently mapped. These are required
versioned changes, not capabilities this proposal claims already exist.

LEGACY_AUTHORITY_ROOT = authenticated registry v1 fields + selected legacy checkpoint
and all protected fallback/report refs, subject to migration frontier barrier.
CANDIDATE_AUTHORITY_ROOT = candidate registry table + dual-readable migration checkpoint
with typed legacy/v2 refs + exact source/target equivalence checks; never Ready mid-migration.
PUBLICATION_SELECTOR = migration manifest's authenticated batch publication barrier,
then final Activated table/root barrier. Existing sel0/sel1 remain root selectors but
must be filtered by this barrier; no highest-valid-candidate fallback.
AUTHORITY_SWITCH_CONDITION = final manifest Activated + verified registry table digest
+ selected authoritative-domain root covering ALL batches and no unconverted ownership.
At a batch publication, only storage representation changes; the global ownership
DOMAIN stays Legacy until final activation. A mixed encoded root is allowed ONLY as a
closed migration view, never a runtime Ready state. Converted records can be projected
back through their proven bijective mapping while this view remains Legacy-authoritative.
Missing/inconsistent mapping closes recovery; it cannot be supplied from a logical hash.

FALLBACK_RULE = pre-final only published migration views at/after the verified frontier,
with every acknowledged report floor; post-final authoritative v2 only. If the sole
allowed root is corrupt, fail closed rather than resurrect released/legacy evidence.
PRE_PUBLICATION_ROOT_RULE = protect source roots and their referenced objects; candidate
has only staging ownership. POST_PUBLICATION_ROOT_RULE = protect published root; old
sources remain protected until BOTH legal cp roots adopt the same-or-newer frontier.
ROLLBACK_ALLOWED = logical cancellation before any batch publication only, with source
intact and staged objects recoverably accounted for. No rollback after first published
batch cleanup; no old-firmware downgrade after Prepared. Failure closes service.

### Selected bounded batch plan

SELECTED_STAGING_MODEL = frozen admission, one typed evidence-family batch at a time,
copy/verify, publish an equivalent closed migration view, shadow the authorized fallback,
then release only superseded coordinate-bearing objects. Archives/EventKeys/receipts
are shared and NEVER deleted. This metadata migration is not event/effect reclamation.
STAGING_BATCH_UNIT = one <=4-entry ev chunk; optional <=4-event ef tail materialization;
or one complete retirement snapshot bank (<=10 owner records). Single outstanding batch.
MAX_BATCH_RECORDS =4 event/evidence entries, or10 retirement-owner records.
MAX_BATCH_BYTES =5777 for snapshot batch; evidence+optional archive<=1580.
MAX_BATCH_NVS_ENTRIES =183 for snapshot blob; evidence+optional archive<=54.
One scratch checkpoint (4546 bytes/145 entries) is additional, not hidden in batch count.
At most one source/target evidence overlap; three existing ret banks suffice only when
the union of source/fallback bank refs leaves a free bank. Otherwise remain closed.

1. Freeze traffic and verify attribution for the ENTIRE installation before converting.
   Do not publish a prefix then discover an unresolvable suffix; no destructive rollback.
2. Persist Prepared registry and authenticated manifest intent before writing target.
3. For each batch, deterministic source keys/digests and candidate coordinates; copy
   once, read back exact bytes/authentication and content equivalence. Existing source
   remains protected. A partial/incorrect target is staging-only, never proof.
4. Write/readback scratch candidate checkpoint, then publish manifest BatchPublished
   naming its digest/frontier. It is a closed Legacy-domain migration view. Next publish
   both normal cp roots with that frontier and verify selectors/fallback policy.
5. Only after both authorized roots exclude source coordinate object, mark Cleanup
   and idempotently erase that exact old object through G05; preserve event archives,
   receipts and report contents. Candidate digest must match before erasing anything.
6. Mark BatchDone, reuse bounded scratch, advance to next batch. Persisted frontier
   replaces unbounded per-event manifest. Never allocate a new scratch key per attempt.
7. Once all references/tail converted, verify final root and table; publish Activated.
   Reconstruct fresh runtime before admitting or ACKing anything. Source cleanup can
   never delete event history; leftover retained archives remain normally owned.

The scratch checkpoint requires a reviewed third key/cap and inventory rule (e.g. cp2);
current mapping accepts only cp0/cp1. This is an explicit format/provider extension,
not an silently usable existing slot. Registry Prepared records provide candidate table;
no per-event map is stored: attribution must be deterministically reconstructable from
retained exact archives and verified table. Any mapping not provable this way blocks.
This batch plan specifies required actions but key/root/shadow publication semantics
still require the G02/G05 implementation contract and budget approval below.

### Bounded manifest and staged recovery

MIGRATION_MANIFEST_REQUIRED = YES; two A/B copies in existing mig0/mig1 maximum512.
They cannot overwrite an unrelated unfinished legacy-journal migration marker. First
finish/verify that separate migration or fail closed. No key-meaning reinterpretation.
MIGRATION_MANIFEST_FIELDS (BE, AEAD header/body format newly versioned): magic4,
version1, flags1, epoch4, migration_id16, phase1, two source(root_gen8,digest32),
registry_table_digest32, batch_family1, source_key_id8/source_digest32,
target_key_id8/target_digest32, verified_frontier2,
target_root_gen8/target_root_digest32, nonce12/tag16.
Total290 bytes; magic/version/context are authenticated; actual framing must bind
all fields. Phase ordinal/frontier and table/source identity forbid old intent revival.
MIGRATION_MANIFEST_BYTES =290 per bank (580 two-bank), <=512 existing envelope.
MIGRATION_MANIFEST_NVS_ENTRIES =12 per bank,24 total under current modeled formula.
Bank choice uses authenticated monotonically advanced frontier/phase; conflicting same
migration step fails closed. Any present corrupt publication record prevents falling back
to earlier authority unless a separate nonregressing proof exists. Availability loss is
acceptable; silently reverting an irreversible cleanup is not.

STAGING_PHASE_ENCODING = enum NotStarted, Prepared, Copying, TargetVerified,
BatchPublished, Cleanup, BatchDone, Activated in authenticated manifest.
RECOVERY_PHASE_RECONSTRUCTION = authenticated manifest + exact root/object digests;
write return values/presence alone are insufficient. PARTIAL_COPY_RULE = intent-owned
partial object cannot publish; verify/rewrite only the fixed staging key while closed.
VERIFIED_BUT_UNPUBLISHED_RULE = source authoritative; finish publication or remain closed.
PUBLISHED_BUT_NOT_CLEANED_RULE = selected batch view authoritative; keep sources until
all roots verified; duplicate cleanup intent harmless, never erase a newer key occupant.
PersistThenFail is resolved by authenticating actual object/manifest; no success ACK
until final readiness. Root/table digest excludes volatile sessions and phase fields.

### Snapshot fit without per-owner binding digests

SELECTED_RETIREMENT_SNAPSHOT_ENCODING = version2; u16 occupancy mask whose bit positions
encode PERSISTED registry slots; records emitted in ascending set-bit order. No runtime
array position allocates ownership. Remove per-record binding_digest32 because the
checkpoint already authenticates the exact registry-table digest, and loader resolves
slot/gen against that table. Every report record remains gen-bound; unknown/retired owner
cannot authorize incoming traffic. Reader requires matching table; snapshot alone is
not standalone retirement authority. Header schema byte defines coordinate domain,
so no extra domain byte. Old schema remains explicit Legacy-only. At activation no
v2 root can reference a legacy snapshot as current ownership without verified migration.

Current18-byte header becomes19 (mask2 replaces count1); record93 becomes61 by removing
32-byte redundant binding digest; preserve report HMAC32 and all report fields/keys.
RETIREMENT_SNAPSHOT_MAX_BYTES =19 +10*(61+32*16)+28 =5777.
EXTRA_BYTES_VS_CURRENT =-319 per maximum bank. SNAPSHOT_CAP_CHANGE_REQUIRED =NO;
existing6096 cap remains. Encryption/report MAC domains unchanged; codec schema changes.
Alternatives: explicit slots add10 bytes; implicit sparse array without mask cannot
represent holes; random field truncation weakens safety. A registry-owned mask is
encoding authority, not deriving authority from transient array position.

GDT schema3/GDE schema2 use their EXISTING version byte as coordinate-domain discriminator;
no extra domain byte/padding growth. GCP schema3 adds table digest32, envelope4546;
declare/check that cap change (4514->4546), not a snapshot cap increase. Mixed-domain
refs legal only in closed migration-view root; final authoritative root requires v2.

### Entry growth and planning capacity (not certification)

The54 =3275-3221 is NOT54 new ownership entries from a common production inventory.
Historical3221 is migration model3160 +27 checkpoint growth +34 retirement allowance.
Independent c receipts later add384 ->3605. Reconciled3240 instead enumerates
archive1344, ev396, c384, ret579, cp288, selectors8, transitions176, bitmap28,
mig allowance36, namespace1. The net19 (3240-3221) is a different family mix, NOT a
certified increment. Prior ownership-domain proposal then added33 ev alignment entries
+2 cp entries =35; total apparent54. Registry34 entries are in default nvs, NOT journal.
Snapshot6107 did not cross an entry boundary; migration overlap not in that steady figure.
This corrects the requested comparison without treating3221 as the current production baseline.

Selected planning model: remove separate domain bytes (save35 proposed growth); compact
three ret banks (579->549, save30); cp table digest adds2; manifest actual580 replaces
1024 allowance (36->24, save12). Reconciled3240-30+2-12 =3200.
STEADY_STATE_USED_ENTRIES =3200; FREE=832; MARGIN=20.6349%.
SAFETY_TARGET_MET =YES for this retained-root planning model ONLY; no physical guarantee.
GS_JOURNAL_STEADY_STATE_BYTES =89494-3*319+2*32-(1024-580)=88157.
Registry remains5077 steady /9073 old+new modeled replacement peak, separate nvs.

Conservative batch overlap: two source ret banks still at6096 rather than5777 add638
bytes/20 entries; one scratch cp4546/145; one ev320/12 beyond the33-root allowance;
optional archive1260/42. Extra6764 bytes/219 entries; manifest already counted.
MIGRATION_PEAK_USED_ENTRIES =3419; FREE=613; MARGIN=15.2034%.
GS_JOURNAL_MIGRATION_PEAK_BYTES =94921; free36151 bytes, peak margin27.5807%.
This is88157+638+4546+320+1260, a planning bound without physical GC certification.
NVS_GC_RESERVE_ENTRIES =128 (one page's modeled entries), provisionally kept WITHIN
free reserve, not a physical GC proof. Required20% reserve=ceil(.20*4032)=807,
including that GC allowance. Peak free613 falls short by194. Do NOT relax20% silently.
MIGRATION_PEAK_FITS =NO against selected reserve policy, despite physical-entry sum<4032.
A batch plan solves full-copy overflow but not the required reserve. Default NVS GC,
abandoned writes and physical page allocation need separate evidence; not magically128.

Root union/retirement floor and scratch envelope may be reducible, but no unsupported
assumption about shrinking these objects is permitted. Future solution must either prove
an actually smaller live/root bound, reduce specific redundant storage with proof, or
seek an explicit reserve-policy decision. Receipt packing, event deletion or partition
resizing is outside this task; no such change is smuggled into the budget.

### Enrollment-capacity alternatives

A: preserve10 total Active+Retired descriptors. Fits current model, zero replacement
headroom when full; deterministic failure and no ownership eviction. Selected interim
model. Active capacity UP TO10, not guaranteed after retained historical replacements.
B:10 active +2 extra pinned descriptors: registry additional204 descriptor bytes;
active slot bytes unchanged. Max12 snapshot owners =>19+12*573+28=6923 bytes,
which breaks6096 cap; +1146/bank versus selected10-owner encoding, +36 entries/bank
(108 total), before other identity metadata. Four extras add408 registry bytes and
snapshot8069 (+2292/bank, +72 entries/bank). This violates current margin/encoding budget.
C:ten slots with2 historical generations elsewhere: same extra owner/report data asB,
plus history indirection and explicit(slot,gen) lookup; cannot use a single mask slot
for two generations. No storage advantage proven, greater migration complexity.

SELECTED_ENROLLMENT_CAPACITY_MODEL =A, preserve10 bounded owners; explicitly reject
replacement when pinned. ACTIVE_NODE_CAPACITY =up to10. REPLACEMENT_HEADROOM =number
of unused descriptors, zero at full occupancy. TOTAL_DESCRIPTOR_COUNT =10.
CAPACITY_STORAGE_IMPACT_BYTES/ENTRIES =0 beyond current10-descriptor proposal.
ALL_REPLACEMENT_CAPACITY_EXHAUSTED_RULE =reject before partial replacement/revocation;
independent authorized revocation may proceed but does not create free capacity.
Product acceptance remains a blocker if seamless replacement at10 active is required;
this document does not invent that approval. Recommend preserving A until a separately
budgeted replacement-reserve requirement is approved.

### Attribution and migration traffic

A provable: authenticated exact archive + matching digest/evidence + preserved complete
physical enrollment binding; report additionally verifies exact original installation-key
HMAC. Translate and verify; global service remains paused until final activation.
B ambiguous: keep legacy-only, no translation/activation; admission/reports stay closed;
operator must supply authenticated historical mapping/proof, not pick a current owner.
C impossible/corrupt: preserve forensic objects, fail closed; reviewed service recovery
needed; never clear completed receipts or falsely mark work pending.
D hash collision: a full event uniquely matching a digest can still be attributable,
but ANY compressed record/report with >1 viable owner blocks activation. No hash-slot tie
breaker. Preflight every batch before first publication to avoid irreversible dead end.
UNMIGRATABLE_INSTALLATION_RULE =closed legacy service-recovery path; no automatic factory
reset/erase or history discard. Operator reset is not an ownership proof and must address
pending/external-effect responsibilities in its separately authorized scope.

EVENT_ADMISSION_DURING_MIGRATION =paused; no new durable event ACKs/duplicate ACKs.
RETIREMENT_REPORT_PROCESSING_DURING_MIGRATION =paused; no snapshot install/success ACK.
Incoming retries are discarded safely; Node retains durable keys and retries after service.
REJOIN_DURING_MIGRATION =paused; no registry/session mutation. After activation, require
fresh authenticated rejoin; drop old volatile sessions/reassembly. Freeze commissioning,
replacement and backend sends too. Downtime policy chosen as simplest safe behavior.

### Crash matrix (all migration phases are not Ready)

| Cut | Authoritative root | Recovery action | Admission/reports | Cleanup |
|---|---|---|---|---|
| Before manifest | Preserved legacy registry/root | Verify source; begin deterministic preflight | Closed after entering migration | No |
| After manifest | Legacy + Prepared barrier | Resume named batch; candidate not selectable | Closed | No |
| Candidate registry written | Legacy; candidate table pinned | Verify table equals intent | Closed | No |
| Evidence written | Legacy; target staging only | Read/authenticate target; partial target never Ready | Closed | No |
| Readback verified | Legacy | Resume candidate root publication | Closed | No |
| Candidate root written | Legacy | Verify scratch digest; highest cp cannot win | Closed | No |
| Before publication selector | Legacy | Resume atomic batch publication | Closed | No |
| Selector persisted, API failed | Published equivalent migration view | Read authenticated manifest; never assume old authority | Closed | Only after shadow roots verified |
| Published, source remains | Published view | Shadow all legal roots; then Cleanup | Closed | G05 exact-source release only |
| Mid cleanup | Published view, floor pinned | Resume exact deletes, no newer occupant erased | Closed | Idempotent pending cleanup |
| Cleanup done, manifest remains | Published view | Verify BatchDone/frontier, advance fixed staging | Closed | No extra source deletion |
| Next batch interruption | Prior published view | Resume only new intent; prior frontier cannot regress | Closed | Current batch publication required |

Final Activated manifest + matching final table/root is the ONLY transition to Ready.
A valid corrupted/lower fallback must not silently select an earlier frontier. Corrupt
publication state closes service. Persisted source and target digests, not presence alone,
resolve phase. This matrix is required behavior, not evidence current code does it.

MIGRATION_CRASH_MODEL_READY =PARTIAL: exact requirements and abstract phases defined;
provider key/cap, shadow-root publication and corruption/nonregression implementation
contract plus reserve approval remain blockers. G02/G05 are no longer vague labels,
but are NOT claimed closed merely by this matrix.
G01_ARCHITECTURE_READY =NO. READY_FOR_G01_IMPLEMENTATION =NO for end-to-end production.
OPEN_TECHNICAL_GAPS =peak20% reserve shortfall, cp scratch/provider mapping and root
publication semantics, G05 release inventory, physical GC reserve qualification,
positive historical attribution, full-capacity replacement product decision.
NEXT_RECOMMENDED_SCOPE =prove phase-specific root/scratch bounds and provider-compatible
G02/G05 publication contract; resolve reserve/capacity decisions before production G01.
No commit/push while these important blockers remain. No production work started.


## 17. Extended executable staged-publication model

Separate from production. JSON serialization below stands for durable model facts;
reconstruct after each step. Atomic publication is an ASSUMPTION being specified, not
proof of NVS atomicity. Cleanup deletes only simulated obsolete coordinate metadata,
not an EventKey, archive or completion. Fixed scratch key/provider support is also an
assumption; this model cannot close those blockers. The safety policy test explicitly
records migration reserve failure instead of weakening the requested20% target.

```python
import json
import math
import unittest

class StagedModel:
    def __init__(self, image=None):
        self.s=json.loads(image) if image else dict(phase='NotStarted', frontier=0,
            source='L0', candidate=None, published=None, shadow=False,
            source_live=True, owner_domain='Legacy', ambiguous=False)
    def reboot(self): return StagedModel(json.dumps(self.s,sort_keys=True))
    def prepare(self):
        if self.s['ambiguous']: raise ValueError('owner proof missing')
        if self.s['phase'] not in ['NotStarted','BatchDone']: raise ValueError('phase')
        self.s.update(phase='Prepared',candidate=None,published=None,
                      shadow=False,source_live=True)
    def copy(self):
        if self.s['phase']!='Prepared': raise ValueError('intent first')
        self.s.update(phase='Copying',candidate='V'+str(self.s['frontier']+1))
    def verify(self):
        if self.s['phase']!='Copying': raise ValueError('copy first')
        self.s['phase']='TargetVerified'
    def candidate_root(self):
        if self.s['phase']!='TargetVerified': raise ValueError('verify first')
        self.s['phase']='RootWritten'
    def publish(self):
        if self.s['phase']!='RootWritten': raise ValueError('root first')
        self.s.update(phase='BatchPublished',published=self.s['candidate'])
    def shadow_roots(self):
        if self.s['phase']!='BatchPublished': raise ValueError('publish first')
        self.s.update(phase='Cleanup',shadow=True)
    def cleanup(self):
        if self.s['phase']!='Cleanup' or not self.s['shadow']: raise ValueError('roots')
        self.s['source_live']=False  # obsolete coordinate metadata ONLY
    def done(self):
        if self.s['phase']!='Cleanup' or self.s['source_live']: raise ValueError('cleanup')
        self.s.update(phase='BatchDone',source=self.s['published'],
                      frontier=self.s['frontier']+1)
    def authority(self):
        if self.s['phase'] in ['BatchPublished','Cleanup']:
            return self.s['published']
        return self.s['source']
    def traffic(self): return False  # no Ready while global domain is Legacy
    def peak_used(self): return 3419
    def reserve_met(self): return 4032-self.peak_used() >= math.ceil(.2*4032)

class PublicationTests(unittest.TestCase):
    def cycle(self,m):
        for method in ['prepare','copy','verify','candidate_root','publish',
                       'shadow_roots','cleanup','done']:
            getattr(m,method)(); m=m.reboot()
        return m
    def test_01_multiple_batches(self):
        m=StagedModel()
        for _ in range(32): m=self.cycle(m)
        self.assertEqual(m.s['frontier'],32)
    def test_02_reboot_every_phase(self):
        m=StagedModel()
        for method in ['prepare','copy','verify','candidate_root','publish',
                       'shadow_roots','cleanup','done']:
            getattr(m,method)(); old=json.dumps(m.s,sort_keys=True); m=m.reboot()
            self.assertEqual(old,json.dumps(m.s,sort_keys=True))
    def test_03_source_protected(self):
        m=StagedModel(); m.prepare(); m.copy(); m.verify(); m.candidate_root()
        self.assertEqual(m.authority(),'L0'); self.assertTrue(m.s['source_live'])
    def test_04_candidate_cannot_win(self):
        m=StagedModel(); m.prepare(); m.copy()
        self.assertNotEqual(m.authority(),m.s['candidate'])
        with self.assertRaises(ValueError): m.publish()
    def test_05_atomic_publication_model(self):
        m=StagedModel(); m.prepare(); m.copy(); m.verify(); m.candidate_root()
        before=m.reboot(); m.publish(); after=m.reboot()
        self.assertEqual(before.authority(),'L0'); self.assertEqual(after.authority(),'V1')
    def test_06_cleanup_order(self):
        m=StagedModel(); m.prepare(); m.copy(); m.verify(); m.candidate_root(); m.publish()
        with self.assertRaises(ValueError): m.cleanup()
        m.shadow_roots(); m.cleanup(); self.assertFalse(m.s['source_live'])
    def test_07_cleanup_restart(self):
        m=StagedModel(); m.prepare(); m.copy(); m.verify(); m.candidate_root(); m.publish()
        m.shadow_roots(); m.cleanup(); m=m.reboot(); m.cleanup(); m.done()
        self.assertEqual(m.s['frontier'],1)
    def test_08_bound_and_gc(self):
        m=StagedModel()
        for _ in range(32):
            m=self.cycle(m); self.assertLessEqual(m.peak_used(),4032-128)
    def test_09_safety_target_blocker(self):
        self.assertGreaterEqual(4032-3200,math.ceil(.2*4032))
        self.assertFalse(StagedModel().reserve_met()) # explicit unresolved requirement
    def test_10_ambiguous_activation_blocked(self):
        m=StagedModel(); m.s['ambiguous']=True
        with self.assertRaises(ValueError): m.prepare()
        self.assertFalse(m.traffic())
    def test_11_pinned_exhaustion(self):
        occupied=[('retired',i) for i in range(10)]
        self.assertEqual(10-len(occupied),0)
    def test_12_replacement_headroom(self):
        self.assertEqual(10-10,0); self.assertEqual(10-8,2)
        # twelve owner records would exceed existing snapshot cap
        self.assertGreater(19+12*(61+512)+28,6096)
    def test_13_snapshot_max(self):
        self.assertEqual(19+10*(61+512)+28,5777)
        self.assertLessEqual(5777,6096)
    def test_14_live_report_policy(self):
        m=StagedModel()
        for method in ['prepare','copy','verify','candidate_root','publish',
                       'shadow_roots','cleanup','done']:
            getattr(m,method)(); self.assertFalse(m.reboot().traffic())
    def test_15_repeated_restart(self):
        m=self.cycle(StagedModel()); original=json.dumps(m.s,sort_keys=True)
        for _ in range(10): m=m.reboot()
        self.assertEqual(original,json.dumps(m.s,sort_keys=True))
    def test_16_budget_arithmetic(self):
        self.assertEqual(3240-30+2-12,3200)
        self.assertEqual(88157+638+4546+320+1260,94921)
        self.assertEqual(3200+20+145+12+42,3419)
        fields=[4,1,1,4,16,1,80,32,1,40,40,2,40,28]
        self.assertEqual(sum(fields),290)

result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicationTests))
assert result.wasSuccessful() and result.testsRun==16
```

HOST_MODEL_RESULT = PASS: original15 + extended16 =31 abstract tests executed on2026-10-03. Tests specify abstract batch isolation,
restart and ordering; they do not prove encryption, actual allocator peaks, root semantics
in production, or final activation under a satisfied reserve. Test09 intentionally
asserts the reserve blocker remains. Successful tests do NOT imply architecture READY.


### Exit clarifications

Manifest comparison orders(migration identity, verified frontier, phase rank) explicitly;
phase codes are not compared as arbitrary numeric insertion order. Conflicting matching
steps fail closed. Migration ID identifies one locked source/table; a different ID cannot
supersede an incomplete run. Never remove the final activation manifest just because
cleanup finished: move its nonregressing authority barrier into authenticated registry
and every legal normal checkpoint first, or retain the bounded two-bank manifest.
This proposal retains both banks in steady-state budgets. Batch source digests become
provenance after verified publication, not a requirement to keep obsolete source objects
forever; current live root references and published barrier define remaining ownership.
The permanent normal-operation barrier and third scratch-root provider mapping are
still explicit G02/G05 review blockers, not implemented assumptions.

Candidate physical-entry sum3419 leaves613 entries (15.2034%);128 provisional GC
entries fit inside those613, but selected total20% reserve needs807. Therefore
MIGRATION_PEAK_FITS=NO under the selected policy. Raw bytes94921 leave36151 bytes
(27.5807%). Registry5077/9073 maxima are modeled blob/replacement space in default nvs;
other security state, flash page GC and write interruption remain unqualified.

Document-only whitespace and git diff checks run. Because this is still the existing
untracked file, git diff --stat reports no tracked changes; that does not mean the
contract was discarded. No unrelated file is modified/untracked, no production tests
or builds were changed/run, no physical test was run, no commit/push is authorized by
the prompt's readiness condition while the listed blockers remain.


## 18. Final optimized architecture contract — authoritative design revision

This section supersedes the provisional readiness, scratch/capacity and290-byte manifest
answers in sections1–17. Earlier sections remain rationale/history, not simultaneous
requirements. No production implementation or physical qualification is claimed.

### Provider objects and guarded source profile

Existing provider mapping: cp0/cp1 (two), sel0/sel1 (two), tr0..tr3 (four),
ret0..ret2 (three), bm0/bm1 (two), mig0/mig1 (two,512 cap), c000..c127 (128),
legacy e000..e127 (128), and base36-mapped ef/ev u64 identities, max15-character
physical keys. Namespace gs_durable in gs_journal; registry gs_registry/snapshot
in default nvs. Provider maxima are cp4514/sel64/tr1332/ef1260/ev320/bm384/ret6096/
mig512/c32/e284. Keys permit candidate ev/ef identity; inventory currently rejects
unreferenced candidates and provider exposes no general durable erase. Future G05
release API is required, with exact-key/generation/source-content guards; not generic GC.

PROVIDER_EXISTING_SCRATCH_CAPABILITIES = inactive checkpoint bank, one report bank
not referenced by authorized root, one evidence overlap, two existing manifest keys.
NEW_SCRATCH_KEYS_REQUIRED =NO; NEW_SCRATCH_KEYS_COUNT =0. No cp2 or new namespace.
SCRATCH_ROOT_MAX_BYTES =4549; MAX_ENTRIES =145. Explicit cp cap change4514->4549
is required for v3 table digest32 + frontier u16 + domain/phase u8. Existing version
byte distinguishes schemas; no extra byte in ev/GDT. Transition domain comes from
new schema; checkpoint migration-view flag distinguishes closed mixed encoding from Ready.
This changes schema/cap, NOT physical key mapping. All decoder/provider/inventory caps
must be updated consistently in implementation. Other selected maxima unchanged.
Registry format5077 max and snapshot5777 proposal stand.

Before any writes, authenticate the whole source and attribution; verify selected root
retains ALL floors of other valid roots, full event history and completion evidence.
If it does not, stop rather than discard stronger proof. Root selection must reject
corrupt/ambiguous publication metadata, not silently choose highest valid cp.
Inventory must prove bounded profile: <=32 archives, <=32 selected evidence chunks
plus ONE candidate/alternate overlap,128 receipts,3 ret banks,2 cp,4 tr,2 bm,2 mig.
The union of roots/objects, not separate per-root maxima, is counted. More than33 ev
objects or unexplained history is NOT silently dropped to fit; preserve and refuse
automatic migration. Existing multi-root references can exceed this profile: those
installations have a defined non-destructive capacity failure, not a universal-fit claim.
Do not treat historical migration-test arithmetic as a universal physical inventory bound.

Normalize live tail before coordinate conversion, still closed and under G05 intent.
For <=128 retained events, a final <=4-event tail leaves <=31 full four-event archives;
its new archive makes <=32, not33. Its evidence similarly uses the reserved overlap.
If actual fragmentation/root union disproves that profile, refuse normalization/migration.
Never add an extra copied ef archive merely for ownership conversion; immutable archive
and c receipts are shared. Old tr records covered by final root stay old-schema,
coordinate-neutral history; only unarchived live transitions require conversion.

### Safe inactive-bank use and publication floor

SCRATCH_CHECKPOINT_MODEL = replace only the bank NOT named by the durable source barrier.
Prepared manifest pins the exact selected source root bank/gen/compound digest. It
revokes weaker alternate fallback only after proving that source contains its complete
history and acknowledged floors. Loss of that sole source fails closed; availability
is not purchased by regressing floors. Therefore the inactive bank is no longer a legal
last recovery copy and may be erased/replaced without a third cp. This is not overwriting
the authoritative source. Current greatest-generation overwrite logic is NOT adequate;
implementation must choose the bank opposite the pinned source, regardless of apparent gen.
SCRATCH_CHECKPOINT_KEY = cp(1-pinned_source_bank).

A compound source digest binds cp bytes AND referenced immutable objects/live tail,
using canonical logical key ordering; epoch, key kind/id and content are included.
Expected candidate contents are derived from this locked source/table. Exact source
child digest stays in the manifest for cleanup after source-root shadowing. If an ev/reference digest is missing,
verify exact full archive content and authenticated source; otherwise fail attribution.
Source mutation/nonce replacement while frozen is forbidden. Retired report owners
must resolve through authenticated candidate table; no current logical-owner reassignment.

MIGRATION_MANIFEST is the publication barrier, not sel alone. Ordering:
1 Prepared intent durably verified (source pinned; candidate keys/family/gens known).
2 Create candidate child blobs; verify authentication, canonical transformation and
   preserved event/report/completion semantics. Expected target contents are reconstructed from the pinned source/table; valid
   re-encryption retries need not reproduce ciphertext nonce. Source child digest
   is fixed and retained for conditional release.
3 Write inactive candidate cp with frontier N+1 and table digest; readback all refs.
4 Store TargetVerified manifest with exact candidate compound-root digest; verify it.
5 Write normal sel to candidate; verify it. While manifest still TargetVerified,
   recovery MUST continue source, even if sel points at candidate.
6 Write/readback Published manifest with exact candidate root/frontier. THIS publishes
   batch N+1. PersistThenFail resolves by authenticated reread, not API success.
7 Old cp may now be overwritten as a shadow at frontier N+1. Verify shadow has identical
   semantic floors/content and same table; fail closed if selected root is lost during this.
8 Cleanup obsolete source coordinate metadata only after every LEGAL root excludes it.
   Then BatchDone. Advance one batch; never accumulate another overlap.
Final Activated manifest + verified registry activation and final v3 root is required
for Ready. Registry activation alone is insufficient. Final manifest may remain at its
fixed size. Subsequent normal metadata publication updates the same floor BEFORE ACK;
root recovery cannot revert to pre-ACK evidence. Normal root frontier preserves the
completed migration frontier/table, even as checkpoint generation advances.

PUBLICATION_BARRIER_VERIFY_ORDER = authenticate intent/source -> candidate children ->
candidate cp/all refs -> sel exact target -> Published manifest -> shadow -> cleanup.
PUBLICATION_BARRIER_OBJECT = authenticated mig A/B record with committed frontier/root.

FALLBACK_ROOT_SELECTION_RULE = first authenticate manifest state, then apply its
allowed root/frontier, then validate normal selectors/root. Prepared/Copying/Verified
can recover ONLY pinned source; candidate never wins highest-generation fallback.
Published permits selected target or authenticated shadow ONLY if frontier>=floor,
same table/domain and semantic floor-equivalent. After Activated, legacy roots forbidden.
PUBLISHED_FRONTIER_FLOOR_RULE = authenticated Published/Activated manifest is minimum;
never select root below it, including when API reported failure. If a present manifest
bank is corrupt or same-step contradictory, fail closed rather than assuming old step.
OLD_ROOT_REJECTION_RULE = root below floor or unselected candidate cannot grant authority.
A shadow at newer checkpoint generation with identical floors is acceptable. Missing
sole target before verified shadow => fail closed. No rollback after first publication.
G02_ARCHITECTURE_READY =YES for this explicit migration/normal-publication contract;
implementation and deterministic production tests remain necessary.

### Compact manifest and G05 ownership

Keep two full AEAD banks, not a single fragile record or unauthenticated checksum.
From290 remove obsolete alternate-source(root_gen8,digest32)=40 bytes, and redundant target-canonical digest32 (recomputed from pinned source/table before
verification; the verified target-root digest binds it after publication). Total218.
The source-child digest32 is RETAINED so exact-source cleanup remains verifiable after
the old checkpoint is overwritten as shadow.
Exact fields: magic4,version1,flags1 (source bank encoded),epoch4,migration_id16,
phase1,source_generation8/source_compound_digest32,registry_table_digest32,
batch_family1,source_key_id8,target_key_id8,source_child_digest32,
frontier2,target_root_generation8/target_compound_digest32,nonce12/tag16.
MANIFEST_TOTAL_BYTES =436 (218 each), TOTAL_ENTRIES =18 (9 each), cap512 unchanged.
AEAD authenticates context/header/fields; use new migration-specific version/domain.
Order record progress by locked migration ID, frontier and specified phase rank;
contradictory or corrupt competing banks fail closed. Reserved fields zero; frontier
max bounded number of source families (<=128-event installation, no wrap). Readback
and actual persisted state resolve failure. Retain both banks at final activation.

Before Copying, source/table identity and deterministic target keys/gen are durable.
Batch kinds name one ev, one ret bank or tail-normalization pair ef/ev whose IDs derive
from target checkpoint generation exactly as existing generation-derived formulas.
For the pair, the intent names the deterministic keyed set and validates its full
canonical contents against the pinned source/table. No source archive/receipt is erased.
No arbitrary key becomes staging-owned. The family classifier/caps and event/report
transformation must validate every object, including a target whose write tore.
Target root digest remains zero until candidate cp exists and all references verify;
pre-verification candidate authorization is structural+semantic intent, not presence.
After TargetVerified, exact compound root digest is required. Re-encrypted incomplete
candidate rewrite can occur only before Published, while source remains pinned;
update verified digest before publication. After Published no rewrite may change meaning.

STAGED_OBJECT_OWNERSHIP_RULE = exact intent family/key/gen + source root/table + phase
owns candidate before publication; referenced roots own published objects. Partial
candidate is a recognizable intent-owned failure, not proof and not an orphan.
STAGED_OBJECT_DISCOVERY_RULE = inventory checks normal roots plus authenticated current
intent; exact matching stale prior candidate can be released ONLY after durable current
frontier excludes it. Unrecognized key/generation, valid-MAC wrong semantic contents or
corrupt authority => fail closed. Inventory does not blindly ignore extra ev keys.
STAGED_OBJECT_GC_RULE = no generic scan/delete. One bounded named batch at a time;
reuse available budget only after verified release; no unlimited failed-attempt IDs.
STAGED_OBJECT_RELEASE_RULE = Published/BatchDone floor plus all legal roots exclude the
exact source; durable Cleanup intent names conditional deletion; reread before erase
and reject identity/content mismatch. Repeated missing-key cleanup is safe. Never erase
archive EventKey or completion receipt to make migration fit. G05 API must expose
commit/readback for erase and fail closed on PersistThenFail ambiguity until reread.
G05_ARCHITECTURE_READY =YES for this bounded intent/release model; provider lacks it
currently, so this is a mandatory implementation component, not a current PASS claim.

### Phase-specific capacity certificate for admitted profile

No third cp(+145), no additional archive(+42), no second ev overlap(+12): save199.
Compact manifests save6 more versus prior290 banks. Initial all-three legacy snapshot
banks, rather than two, add10 versus previous modeled peak. Net reduction195:
3419-145-42-12-6+10 =3224. This removes the194 shortfall without lowering reserve.
Retained-root steady baseline =3200-6=3194; raw baseline88157-144=88013, includes
both4549 cp caps (extra3 each versus4546 adds6 raw bytes; final correct totals below).
Legacy snapshot banks add10 modeled entries /319 raw bytes each above compact v2.
No ev alignment growth: old/new chunk cap320/schema byte selects coordinate semantics.
All candidate data is inside the reserved family counts:2cp,3ret,33ev,32ef, not added
again as a scratch family. Each phase budgets BOTH manifests, including Prepared.

| Phase | Source/live root-family entries | Candidate included in family | Manifest | Total used | Free | Margin | Safe deletion |
|---|---:|---|---:|---:|---:|---:|---|
| 0 legacy steady/start |3206|none extra;3 legacy ret|18|3224|808|20.0397%|none until intent |
| 1 Prepared |3206|inactive cp is reserved, not selected|18|3224|808|20.0397%|weaker excluded cp; unreferenced bank only |
| 2 Copy |<=3206|one ev overlap or free ret bank, within counts|18|<=3224|>=808|>=20.0397%|no authoritative source |
| 3 Verify |<=3206|inactive cp within two-bank count|18|<=3224|>=808|>=20.0397%|no source |
| 4 Publish |<=3206|candidate becomes selected; old root retained until shadow|18|<=3224|>=808|>=20.0397%|after exact floor and shadow |
| 5 Cleanup |<=3206|no next candidate allocated|18|<=3224|>=808|>=20.0397%|exact excluded ev/obsolete ret, not events/c |
| 6 Next batch |<=3206|one overlap reused after release|18|<=3224|>=808|>=20.0397%|prior named batch only |
| Final Activated |3176|all3 ret compact, no extra scratch|18|3194|838|20.7837%|keep activation floor/normal owned objects |

These are conservative phase upper bounds, not assertions every counted family is
fully allocated together. Peak drops ten entries for each old ret bank safely replaced:
3224 ->3214 ->3204 ->3194. Evidence-only phases can retain3224 ceiling until snapshots
convert. During report staging source remains protected; target uses unreferenced third
bank, and source cleanup occurs after root exclusion, never before readback publication.

GC_RESERVE_POLICY =20% operational free-entry reserve INCLUDES GC and replacement
scratch; do not charge128 again outside20%. Current tests assert free>=20% without a
separate GC term; this preserves their policy. GC_RESERVE_ENTRIES =128 provisional
planning slice inside807, not a physical measured guarantee. Other reserve covers
same-key NVS replacement dead entries, page overhead and failure/GC scratch. A checkpoint
replacement temporarily leaves dead old data, not an additional live cp/root family;
these transient flash costs consume operational reserve and require allocator HIL.
No claim that instantaneous physical nvs_get_stats must always show20% while a write
is in flight. The certified metric is modeled LIVE+STAGING object budget with807 held
for operations; physical allocation must be qualified before release.
SAFETY_MARGIN_POLICY =ceil(.20*4032)=807 unallocated modeled entries, INCLUDING128.
REQUIRED_MIN_FREE_ENTRIES =807. Peak808 leaves one-entry slack over target, so maxima
are hard caps. Codec/key/frame growth or another key REQUIRES rebudgeting. Per-write
allocator admission must have capacity for the bounded write/commit/GC; allocation
failure keeps source and service closed. Arbitrary accumulated failed-write garbage
must be collected within provider reserve or cause safe refusal, never extra keys.

MIGRATION_PEAK_USED_ENTRIES =3224; FREE=808; MARGIN=20.0397%; FITS=YES for this
admitted-profile planning contract. Not a guarantee all existing inventories migrate.
Byte corrections for cp4549 instead of4546: steady88019; peak88019+957=88976;
free42096, peak margin32.1167%. Manifest436; candidate checkpoint<=4549 and child
<=5777 (or ef1260+ev320) are ALREADY inside family totals, not extra raw bytes.
Default registry remains5077 max, modeled old/new replacement peak9073; account in
its separate24576 partition and fail allocation closed. Not charged to journal.
RETIREMENT_SNAPSHOT_STAGING_FITS =YES (5777, third unreferenced existing ret bank).

### Final crash matrix and readiness

| Cut | Authority/recovery | Ready/traffic | Release |
|---|---|---|---|
| Before manifest | Legacy source; verify entire attribution/profile first |closed once migration begins|none |
| Prepared persisted |pinned source only; ignore candidate/high-gen sel|closed|only excluded obsolete inactive objects |
| Mid copy/write |source; intent owns partial target; retry fixed family|closed|no source |
| Candidate fully written |source; verify canonical transform/all refs|closed|no source |
| Readback verified/candidate cp written |source until Published, even if normal sel changed|closed|no source |
| Before barrier |source; resume verified publication|closed|no source |
| Published persisted but API failed |authenticated reread chooses actual new floor; never assume rollback|closed|only after shadow exclusion |
| Selector/frontier updated |Published candidate; alternate only at/above floor|closed|none before shadow |
| Before/mid cleanup |new floor; idempotent exact-key cleanup|closed|named excluded coordinate objects only |
| After cleanup/before next batch |BatchDone new floor; one available overlap|closed|no new unrelated delete |
| Repeated next batch restart |same migration ID/frontier; no reallocation/gen increment|closed|current bounded intent |
| Final registry activation before final manifest |root may be verified, but barrier not Activated|closed|no event/c cleanup |
| Final Activated persist/API failure |reread root/table/barrier; exact new-domain Ready only|fresh authenticated rejoin|normal bounded source-release contract |
| Corrupt authority bank or required selected root |fail closed, not lower-frontier fallback|closed|none based on corrupt proof |

HISTORICAL_ATTRIBUTION_ARCHITECTURE_COMPLETE =YES: provable converts; ambiguous/collision
has no tie-breaker and stays non-destructively closed; corruption fails closed. Those
are legitimate runtime/service outcomes, not an invented proof or global design gap.
TEN_DESCRIPTOR_MODEL_ARCHITECTURALLY_VALID =YES;10 active implies no immediate spare.
REPLACEMENT_HEADROOM_PRODUCT_LIMITATION =YES, explicit safe reject; not readiness blocker.
PHYSICAL_GC_REQUIRED_BEFORE_ARCHITECTURE_READY =NO.
PHYSICAL_GC_REQUIRED_BEFORE_PRODUCTION_RELEASE =YES.
MIGRATION_CRASH_MODEL_READY =YES at abstract contract level; all cuts choose one allowed
floor or fail closed. No physical atomicity/power-cut claim.
G01_ARCHITECTURE_READY =YES for the guarded bounded migration/registry contract.
READY_FOR_G01_IMPLEMENTATION =YES; no production feature started in this task.
Future BAT must implement schema3 checkpoint/cap4549, registryv2, snapshotv2, manifest
codec/intent-aware owner recovery, explicit root selection/floor, exact release API,
and production fault-injection tests as ONE reviewed migration implementation scope.
G03 remains separate. G04 reset-lifetime identity and reclamation remain open.


### Exact manifest framing and progress

GMM2 blob layout: clear authenticated header magic GMM2[4], version2[u8], flags[u8],
nonce[12]; encrypted184-byte canonical body; GCM tag16. Total218. AAD is ASCII
hub-enrollment-migration-v2 followed by the18-byte header. Body fields are the above
BE epoch/id/phase/source/table/family/key IDs/source-child digest/frontier/target root.
No undocumented padding or CRC replaces authentication. Migration ID16 is generated
once and reused from persisted Prepared; compare current migration ID/source/table,
not arbitrary greater random ID. Source bank is encoded in flags, other bits reserved.
Phase rank0 NotStarted,1 Prepared,2 Copying,3 TargetVerified,4 Published,5 Cleanup,
6 BatchDone,7 Activated. Next batch increments frontier, then starts Prepared; final
activation is a zero-data final batch with a new frontier and v3 RegistryReady flag.
Before it publishes, candidate RegistryReady root still cannot grant Ready. Registry
activation commits/readbacks before final Activated manifest. All counters fail closed
before wrap. Digest fields mean HMAC-SHA256 over canonical keyed contents with epoch
and kind/identity, except registry table digest uses its specified canonical table;
manifest AEAD binds them. Both same-step conflicting manifests and any corrupt present
bank close service; recovery never guesses the lower barrier was last committed.

Input budget gate sums EVERY physical logical object recognized by inventory, including
obsolete/alternate allocations, before Prepared. Each planned write/delete also checks
family-count and LIVE+STAGING bound<=3225, leaving807 modeled entries. Unexplained objects
cannot be counted away. A populated installation outside the admitted profile is preserved
and migration refused; reviewed service recovery is required. No historical source-model assumption authorizes deletion of evidence. Physical NVS reserve/GC behavior is a
later qualification gate and allocation errors preserve source/close traffic.

Not all retained old cp objects remain legal fallback after Prepared. Dropping a weaker
fallback is an authenticated authority decision, not deletion of its archive/EventKeys.
Selected source must contain all of its history/floors; otherwise migration cannot start.
The excluded bank is then storage space for candidate. All source children remain
pinned until batch publication. This explains why no extra checkpoint family is needed
without weakening replay prevention. Cleanup removes only excluded ev/obsolete report
representations, never event records, receipts or old owner descriptors.


## 19. Final executable abstract model and validation

This model replaces earlier provisional budget answers. It tests the explicit contract,
not production codecs/ESP-NOW/NVS or cryptographic implementations. Serialized model
facts are reloaded at every tested boundary. Atomic record replacement is an assumption
that production host fault injection and HIL must validate; corrupt records fail closed.
The20% reserve metric is live+staging planning entries, not an instantaneous flash-stat
claim. Inventory beyond the bounded source profile is a defined safe refusal.

```python
import json
import math
import unittest

class FinalMigration:
    def __init__(self, image=None):
        self.s=json.loads(image) if image else dict(
            phase='Idle',frontier=0,source=0,candidate=1,published=False,
            registry='Prepared',manifest_bad=False,ambiguous=False,
            intent=False,copied=False,verified=False,shadowed=False,
            cleanup=False,legacy_banks=3,admitted=True,
            roots=[{'floor':0,'good':True},{'floor':-1,'good':True}],
            events=['A','B'],receipts={'A':'immutable'},stage_key=None)
    def reboot(self): return FinalMigration(json.dumps(self.s,sort_keys=True))
    def used(self): return 3194+10*self.s['legacy_banks']
    def prepare(self):
        if self.s['ambiguous'] or not self.s['admitted']: raise ValueError('preflight')
        if self.s['phase'] not in ['Idle','Done']: raise ValueError('phase')
        self.s.update(phase='Prepared',intent=True,copied=False,verified=False,
                      published=False,shadowed=False,cleanup=False,
                      candidate=1-self.s['source'],stage_key='ev-fixed')
    def copy(self):
        if not self.s['intent']: raise ValueError('orphan')
        self.s.update(phase='Copying',copied=True)
    def candidate_root(self):
        if not self.s['copied']: raise ValueError('copy first')
        self.s['roots'][self.s['candidate']]={'floor':self.s['frontier']+1,'good':True}
        self.s.update(phase='Verified',verified=True)
    def authority(self):
        if self.s['manifest_bad']: raise ValueError('corrupt barrier')
        if not self.s['published']:
            r=self.s['roots'][self.s['source']]
            if not r['good'] or r['floor']<self.s['frontier']: raise ValueError('source corrupt/regressed')
            return self.s['source']
        floor=self.s['frontier']+1
        c=self.s['candidate']; r=self.s['roots'][c]
        if r['good'] and r['floor']>=floor: return c
        a=1-c; r=self.s['roots'][a]
        if self.s['shadowed'] and r['good'] and r['floor']>=floor: return a
        raise ValueError('no permitted root')
    def publish(self):
        if not self.s['verified'] or not self.s['roots'][self.s['candidate']]['good']:
            raise ValueError('not verified')
        self.s.update(published=True,phase='Published')
    def shadow(self):
        if not self.s['published']: raise ValueError('not published')
        self.s['roots'][self.s['source']]=dict(self.s['roots'][self.s['candidate']])
        self.s.update(shadowed=True,phase='Cleanup')
    def release(self):
        if not self.s['shadowed']: raise ValueError('source still legal')
        self.s.update(cleanup=True,stage_key=None) # obsolete coord state ONLY
    def done(self,snapshot=False):
        if not self.s['cleanup']: raise ValueError('not released')
        if snapshot and self.s['legacy_banks']:
            self.s['legacy_banks']-=1
        self.s.update(source=self.s['candidate'],frontier=self.s['frontier']+1,
                      published=False,phase='Done',intent=False)
    def staged_owned(self): return self.s['intent'] and self.s['stage_key']=='ev-fixed'
    def cycle(self,snapshot=False):
        m=self
        for method in ['prepare','copy','candidate_root','publish','shadow','release']:
            getattr(m,method)(); m=m.reboot()
        m.done(snapshot); return m.reboot()

class FinalTests(unittest.TestCase):
    def test_01_every_phase_entries(self):
        m=FinalMigration()
        for method in ['prepare','copy','candidate_root','publish','shadow','release']:
            getattr(m,method)(); m=m.reboot()
            self.assertEqual(m.used(),3224)
            self.assertGreaterEqual(4032-m.used(),math.ceil(.2*4032))
    def test_02_reduction(self):
        self.assertEqual(3419-3224,195); self.assertGreaterEqual(195,194)
    def test_03_reserve_all_batches(self):
        m=FinalMigration()
        for i in range(35):
            m=m.cycle(snapshot=i<3)
            self.assertGreaterEqual(4032-m.used(),807)
        self.assertEqual(m.used(),3194)
    def test_04_intent_protects(self):
        m=FinalMigration(); m.prepare(); m.copy()
        self.assertTrue(m.staged_owned()); self.assertEqual(m.authority(),0)
    def test_05_stage_reboot(self):
        m=FinalMigration(); m.prepare(); m.copy(); m=m.reboot()
        self.assertTrue(m.staged_owned())
    def test_06_source_before_publish(self):
        m=FinalMigration(); m.prepare(); m.copy(); m.candidate_root()
        self.assertEqual(m.authority(),m.s['source'])
    def test_07_floor_rejects_old(self):
        m=FinalMigration(); m.prepare(); m.copy(); m.candidate_root(); m.publish()
        self.assertEqual(m.authority(),m.s['candidate'])
        m.s['roots'][m.s['candidate']]['good']=False
        with self.assertRaises(ValueError): m.authority()
    def test_08_persist_then_api_failure(self):
        m=FinalMigration(); m.prepare(); m.copy(); m.candidate_root(); m.publish()
        m=m.reboot(); self.assertEqual(m.authority(),m.s['candidate'])
    def test_09_bad_manifest(self):
        m=FinalMigration(); m.prepare(); m.s['manifest_bad']=True
        with self.assertRaises(ValueError): m.reboot().authority()
    def test_10_bad_candidate(self):
        m=FinalMigration(); m.prepare(); m.copy(); m.candidate_root()
        m.s['roots'][m.s['candidate']]['good']=False
        self.assertEqual(m.authority(),m.s['source'])
        with self.assertRaises(ValueError): m.publish()
    def test_11_cleanup_crash(self):
        m=FinalMigration(); m.prepare(); m.copy(); m.candidate_root(); m.publish()
        with self.assertRaises(ValueError): m.release()
        m.shadow(); m.release(); m=m.reboot(); m.release(); m.done()
        self.assertEqual(m.s['events'],['A','B']); self.assertEqual(m.s['receipts'],{'A':'immutable'})
    def test_12_repeated_batches(self):
        m=FinalMigration()
        for i in range(32): m=m.cycle()
        self.assertEqual(m.s['frontier'],32)
    def test_13_snapshot_stage(self):
        self.assertEqual(19+10*(61+512)+28,5777)
        m=FinalMigration().cycle(snapshot=True); self.assertEqual(m.used(),3214)
    def test_14_bad_attribution(self):
        m=FinalMigration(); m.s['ambiguous']=True
        with self.assertRaises(ValueError): m.prepare()
        self.assertFalse(m.s['intent'])
    def test_15_descriptor_exhaustion(self):
        occupied=10; self.assertEqual(10-occupied,0) # reject; no evidence reassignment
    def test_16_full_profile_guard(self):
        m=FinalMigration(); m.s['admitted']=False
        with self.assertRaises(ValueError): m.prepare()
    def test_17_manifest_layout(self):
        self.assertEqual(sum([4,1,1,4,16,1,40,32,1,8,8,32,2,40,28]),218)
        self.assertEqual(2*(2+math.ceil(218/32)),18)
    def test_18_tail_archive_bound(self):
        for tail in range(1,5):
            self.assertLessEqual(math.ceil((128-tail)/4)+1,33)
        # admitted normalized profile requires full previous groups; no arbitrary fragmentation
        self.assertEqual(31+1,32)
    def test_19_final_activation_barrier(self):
        m=FinalMigration().cycle(); m.s['registry']='Activated'
        self.assertNotEqual(m.s['phase'],'Activated') # registry alone cannot grant Ready
        m.s['phase']='Activated'; self.assertEqual(m.reboot().s['phase'],'Activated')
    def test_20_byte_bound(self):
        self.assertEqual(88019+3*319,88976)
        self.assertEqual(131072-88976,42096)

result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(FinalTests))
assert result.wasSuccessful() and result.testsRun==20
```

Final host model execution is recorded below. These tests cannot substitute for actual
production adapters/provider fault tests. Previous provisional tests intentionally
asserted their THEN-budget blocker; they remain historical models, not final answers.


### Tail clarification: no forced archive copy

The optional normalization operation is NOT required to enable migration. A partial
legacy archive plus live tail might require33 archives despite128 logical events;
that is a concrete reason NOT to assume all old groups are full. Prefer leaving existing
immutable archive AND authenticated GDT schema1/2 tail bytes intact. Final GCP schema3
flags include AllowLegacyEventTail (within the specified flag byte). In that mode the
recovery projection derives owner ONLY from full authenticated physical/logical
EventIdentity and pinned table, ignoring old hash coordinates for ownership. Unique
historical attribution and exact causal-content validation are mandatory. A root-owned
legacy tail is readable representation, not legacy ownership authority. New transitions
MUST be GDT schema3 with registry coordinates. The compatibility flag persists until
all such old tail records are covered/overwritten by existing ordinary lifecycle; no
archive/event deletion or rewrite is authorized. Source records remain owned by selected
root plus ordinary four-key transition inventory; G05 does not classify them as scratch.

No per-event mapping is needed because same-device re-enrollment is forbidden and table
contains at most one retained generation per exact physical owner. If that uniqueness
or canonical identity/content proof is absent, reject migration rather than relabel.
The projected tail uses the authoritative root's table digest and full EventIdentity;
it can never select a descriptor by source_id hash. This completes exact legacy-tail
compatibility without forcing an extra ef allocation. Partial archive is retained as is.
The final RegistryReady root may therefore retain explicitly typed, validated legacy
EVENT representation only; it may NOT leave legacy compressed GDE/report coordinates
unconverted. Registry ownership remains the single authority; no mixed Ready domain.
A later G04 re-enrollment policy would require a new compatible identity review.

### Validation result and exit

HOST_MODEL_RESULT =PASS:15 original +16 provisional +20 final =51 abstract tests.
Final20 cases include all required reserve/publication/staging/crash/refusal checks.
MIGRATION_CRASH_MODEL_READY =YES at specified architecture-model level.
G02_ARCHITECTURE_READY =YES. G05_ARCHITECTURE_READY =YES.
MIGRATION_PEAK_FITS =YES in the guarded LIVE+STAGING planning model,20.0397% margin.
G01_ARCHITECTURE_READY =YES. READY_FOR_G01_IMPLEMENTATION =YES.
Input attribution/capacity refusal and ten-owner replacement rejection are specified
safe outcomes, not unresolved architecture decisions. Physical allocator/HIL remains
release work; this checkpoint makes no measured flash or real-radio claim.

OPEN_TECHNICAL_GAPS (implementation/release, not undefined design fields): production
GSRGv2/GCPv3/GDEv2/GRSv2/GMM2 codecs and caps, intent-aware owner/inventory recovery,
manifest-governed selector/fallback, exact conditional release API, adapter binding,
production fault-injection/regression/target builds, allocator/power-cut/radio HIL.
G03, G04 and reclamation remain separate unresolved scopes in the main audit.
NEXT_RECOMMENDED_SCOPE =implement this reviewed G01+required G02/G05 migration contract
with production host fault injection and target builds; no automatic implementation here.


Checked key-ID arithmetic is required before preparation: generation-derived ev IDs
must satisfy checkpoint_generation<=UINT64_MAX>>8, ef high-bit encoding must not
alias an existing ID, and source/target IDs must be distinct while source pinned.
Overflow/collision fails closed; no accidental wrap reuses a previously owned object.
All post-BatchDone root selection also checks root frontier>=manifest frontier, not
just root authentication. Current provider/schema/key functions are not presumed to
already implement these rules.

## 20. Coordinator closure against the partial production implementation (2026-10-04)

This is an implementation handoff, not production completion or storage certification.
The 23-file implementation diff at base `072316a` is preserved. The reported migration
failure at `clean migration commits` is valid: `append_event()` creates registry-domain
GDT3 against a legacy root. Keep `DurableStore::commit()`'s domain rejection. Migration
constructs and publishes roots through a separate closed coordinator; it does not replay
historical Events through ordinary admission.

The refinements below supersede: section 18's namespace name (`events` is the actual
namespace), its permissive newer-generation shadow, its 3,225-entry per-write allowance,
and section 19's model as sufficient coverage of these details. The ceiling is **3,224**,
free entries **808**, not merely the rounded 807 reserve. No persistent field grows.

### 20.1 Durable vocabulary and exact encodings

Let S be the frozen selected source view, C the candidate, T the prepared ownership
table digest, N the next batch frontier, and G the source checkpoint generation.
C has generation G+1 and occupies cp(1-source_bank). Prepublication floor is N-1;
publication commits N. All increments, shifts, bank masks and IDs are checked before
intent. No wrap. At most 32 evidence conversions, three selected/obsolete report-bank
conversions/releases and one final batch are needed; conservatively allow 39 batches,
well below the existing 128 frontier guard. Retry uses the persisted generation/IDs.

GCP1 schema 3 keeps the current 35-byte extension (digest32, frontier2, flags1).
Assign the existing flag byte as follows; no additional byte is introduced:

| Bits | Meaning |
|---|---|
| 0 | RegistryOwnerV2 interpretation |
| 1 | closed MigrationView; never Ready |
| 2 | AllowLegacyEventTail, inspection of exact GDT1/2 event representation |
| 3 | AllowLegacyEventSlots, inspection of retained e000..e127 representation |
| 4..6 | protected live-tail prefix count, 0..4; 5..7 invalid |
| 7 | reserved, zero |

The protected prefix starts at covered_ordinal+1. It is immutable until a later barrier
covers it. Additional ordinary GDT3 tail records may append beyond that prefix, within
four tr keys, with authenticated consecutive ordinals; they cannot replace the prefix.
Archive handoff/checkpoint changes use a new publication transaction before overwriting
any tail needed by a legal root. Covered stale tr records are not digest dependencies.
Legacy-tail inspection flags authorize no new legacy write.

GMM2 remains header18 + encrypted body184 + tag16 =218 bytes per bank. Keep all existing
body fields. Refine the existing authenticated flags byte: bit0 source bank; bits1..3
frozen source live-tail count 0..4; bit4 NormalPublication; bit5 VirtualLegacySource;
bit6 CancelledNormalPublication; bit7 zero. Cancellation requires NormalPublication.
VirtualLegacySource is legal only for the initial raw e/c or proven-fresh empty profile with
both cp banks absent, source generation 1, frontier 1, NormalPublication clear. It is
not an authorization to ignore a missing real checkpoint. FinalActivation remains the
zero-child family; a NormalPublication with this family is a metadata-only transaction.
TailPair remains available only when the complete union and capacity proof admits it;
ownership conversion itself never requires it.
For TailPair, `source_key_id` names the staged ef identity `0x8000000000000000 | (G+1)`
and `target_key_id` names staged ev `((G+1)<<8)|1`; its source_child_digest authenticates
the canonical ordered frozen source tail. This family-specific interpretation owns BOTH
children before either write. Source tr records are covered after publication, not erased;
Cleanup has no source-child delete for TailPair. Require G+1 below the archive prefix and
within the ev shift bound, no existing-ID alias and the full union count before intent.

All root digests use a new explicit local compound-root HMAC domain. Canonical entries
are length-prefixed (kind, logical ID, payload length, exact payload), sorted by kind/ID,
with epoch and domain context. The checkpoint entry's logical identity is
`checkpoint/<generation>`: physical bank is authenticated separately by manifest and
selector. Include exact checkpoint bytes, every referenced ef/ev/ret blob, and the exact
protected tail prefix. Source digest instead uses the full frozen tail count authenticated
in GMM2. Include all retained e blobs when the legacy-slot flag/profile applies. Do not
include unreferenced overlap children, covered tr records or selectors.

Independent c receipts do not enter the fixed compound digest. They remain immutable,
individually authenticated to exact EventKey AND stable journal slot under the existing
journal key. Verify every present receipt and preserve its event in every legal view.
Their independent commit/readback permits later completion without invalidating an
activation root digest. No c deletion or rewrite is allowed. During frozen migration,
compare the complete existing receipt set before/after every batch. bm values remain
unchanged, authenticated and budgeted; any unsupported live bitmap mapping blocks this
coordinator rather than being reinterpreted as a receipt. Their generic mutation is not
introduced here.
An existing authenticated ef archive's kind=1 completion marker remains readable exact
completion evidence for that same EventKey/slot. Preserve its bytes and meaning during
conversion. After activation, an independent c receipt may be published from that exact
legacy proof within the already reserved receipt family. Disable the existing
`replace_completion()` archive kind rewrite in the migration path: it would invalidate the fixed root
digest and is unnecessary. Retaining the marker is not completed-effect retirement.

A VirtualLegacySource digest covers a canonical logical genesis descriptor (epoch,
generation1, empty durable tail/references) plus authenticated raw e objects and their
stable slot association. It has no physical cp0 blob. Receipts are checked independently
as above. Source recovery derives this view from the authenticated legacy journal and
registry, with both cp keys absent. Intent precedes writing the first candidate cp1;
after publication, its exact shadow is written to cp0. No bootstrap scratch/root key.

T is HMAC-SHA256 over a versioned canonical ten-slot ownership table: occupied marker,
slot, uint32 generation, length-prefixed device ID and owner_digest for each descriptor;
NeverOwned has canonical zeros. Active and Retired both mean occupied for this identity
digest. Authorization state, active records, revocations and keys remain authenticated
by GSRG and checked independently. Thus revocation does not change historical ownership
binding; a new owner changes T. Owner digest already binds home/hub/public key/logical
ID/slot/generation. Exclude snapshot generation, session, migration phase and activation
digest. This specifies the earlier "descriptor/active-owner association" as immutable
identity association, not mutable live authorization status. A root never grants radio
authorization merely because an occupied descriptor exists.

### 20.2 Preflight and GSRG v1 -> v2 preparation

One owner task holds the mutation lease throughout a bounded step. Enter closed mode
before inspection: block event and duplicate success ACKs, reports/success ACKs, rejoin,
commissioning/replacement, reducer/config changes and backend sends/receipt writes.
Do not retain an unbounded queue. Existing bounded queues may discard traffic; Nodes
keep their durable retries. Reject any independent writer that can mutate pinned data.

1. Authenticate registry, selectors, source roots and their transitive child inventory.
   For cp-backed sources require an authenticated selector naming an exact valid root;
   absent/corrupt/conflicting selection fails closed. Do not pick a higher cp generation.
   For raw e/c-only sources use the virtual-source rule. Authenticate every event,
   completion and report, including weaker fallback report floors. An unexplained object,
   unsupported schema-1 dedupe frontier, unreadable key or unowned allocation blocks.
2. Verify S includes the union of retained event/effect/completion history and ALL
   acknowledged retirement rejection predicates of previously legal roots. Report pending
   keys are exceptions: highwater alone is insufficient. If S cannot dominate the full
   union, preserve it and refuse migration; do not merge by dropping exceptions/floors.
3. Inspect all legacy owners before any publication. Sort exact active device IDs by byte
   order; assign lowest descriptors, generation1. Then sort any historical owners for
   which complete authenticated enrollment identity is actually retained and assign the
   remaining descriptors. Ten descriptors total. A bare revocation tombstone does not
   reconstruct public key/logical identity/installation key; evidence needing that owner
   blocks. An unused tombstone is preserved and needs no fabricated descriptor. More
   than ten evidence owners blocks. Same physical device with multiple incarnations
   blocks this single-generation model. Released is invalid; no slot reuse in G01.
4. For compressed GDE1 match full retained EventIdentity, canonical immutable digest,
   session/sequence and old coordinate to exactly one proven owner. Recompute legacy
   binding only as a read-only consistency check. A collision/ambiguous association has
   no tie-breaker. Reports additionally require the exact original installation key and
   reconstruction/verification of their original report HMAC; missing keys or uncertain
   historical logical relationship block. Verify the entire proposed conversion plan
   now, so a later batch cannot discover an attribution gap after irreversible release.
5. Compute T, deterministic bounded batch keys, source digest and source-child digest
   in memory. Reserve all future live/staged counts. Write/readback first GMM2 Prepared
   BEFORE creating the candidate GSRG snapshot. Intent owns the Prepared table through
   T and source epoch/generation, even if the table is still derivable from GSRG v1.
6. Replace the SAME `gs_registry/snapshot` value with GSRG2 Prepared. Preserve every
   original base identity, installation binding, revoked ID and session field. Sort
   canonically for comparison; no security mutation is bundled with initial preparation.
   Exact readback/decode verifies all fields, descriptors/T and source provenance.
   Prepared's target digest is zero. It is not live v2 authorization.

Boot with Prepared GMM + v1 registry regenerates the same T and retries preparation.
Boot with GSRG2 Prepared retains a legacy projection of its unchanged base fields for
prepublication source recovery. This is semantic v1 recovery, not an extra backup key
or downgrade to old firmware. Missing/corrupt registry cannot be repaired by guessing
from payloads; leave journal sources intact and close service. A torn single registry
replacement may therefore require service recovery. PersistThenFail succeeds only when
exact authenticated reread proves the requested Prepared state. Boot never reallocates
slots or changes enrollment generation.

### 20.3 Candidate construction and equivalence

Choose one legacy ev chunk, one selected ret snapshot, or one obsolete ret representation
per batch, in canonical key order. Prefer retaining exact legacy event tails/slots, so
no ef copy is needed. Copy S's checkpoint configuration/reducer/effect references,
covered ordinal, full event history and report state. Set schema3, RegistryOwnerV2,
MigrationView, T, frontier N, generation G+1, inspection flags and protected-tail count.
Replace only the current batch's ev or ret reference with its verified new-domain
reference. Mixed GDE/GRS encodings are permitted only inside this closed MigrationView:
validate each object's actual schema and project legacy ownership through the locked
proof table. This is not permission for legacy coordinates to become current authority.
An ev chunk is entirely one domain. Ret v2 occupancy bit positions are persisted slots.
Final candidate clears MigrationView only after ALL compressed GDE and referenced GRS
objects are current-domain; legacy full-identity event representations may remain typed.

For e-only migration, preserve e/c bytes and journal slots. AllowLegacyEventSlots makes
those exact authenticated events readable under the table; it does not create new
Events, ef copies or receipts. They occupy the same 128-event retention pool as archived
and tail events. Existing multiple representations require exact same content AND slot;
any conflicting representation is a migration validation failure. This does not change
G03 ordinary duplicate handling. Remove the old copy/delete helper from the activation
path; tests asserting e/c cleanup must become preservation/typed-read assertions.

Translate each compressed coordinate through the unique proof found in preflight;
preserve EventKey, canonical digest, session, sequence, effect ID/payload, completion
identity and all report fields/HMAC/pending keys. Primary report conversion is exact
logical equality. Obsolete report cleanup requires dominance of its rejection predicate
by the selected report, not an invented equality of obsolete pending lists.

Write only the inactive cp bank under the current intent. Ordinary `checkpoint()` and
`commit(Event)` cannot construct this migration candidate. Read back checkpoint and ALL
children/tail/events/receipts, authenticate them, verify exact references and compare
complete projected semantic state against S. Compare reducer/config bytes, all retained
history, stable slots/effects/completions and rejection predicates including exceptions.
Store the exact compound target digest in TargetVerified only after this succeeds.
A canonical semantically identical preverification retry may use a fresh nonce; after
TargetVerified reuse exact bytes or step back only through an explicit closed reverify
transaction. The simplest implementation freezes verified bytes and fails closed if
lost until a source-based service retry; no Published object may be re-encrypted.

`DurableStore::commit()` may first admit new registry-domain Events only after FINAL
Activated is verified jointly with GSRG2 and a non-MigrationView selected root, then fresh
authenticated rejoin. A published intermediate root is never sufficient. Fresh empty
installations use this same zero-data activation path; no legacy-domain Ready genesis
followed by a registry Event is allowed.

### 20.4 Every durable phase

Codes are the existing GMM2 phase values. For initial migration candidate gen/digest
fields are zero in Prepared/Copying and exact in TargetVerified and later; G+1 is
already derivable. For NormalPublication the early fields instead carry G+1 and the
canonical intended child/projection digest specified below; size remains unchanged.
"Blocked" means all traffic listed in 20.2, including success ACKs and rejoin.

| Durable phase | Root/domain, selector and frontier authority | Legal fallback, staging and writes | Reboot / next transition / failure |
|---|---|---|---|
| No intent | authenticated legacy S or virtual source; no v2 authority | only originally authorized roots; no staging write | preflight, then Prepared; missing source, bad selector, attribution or capacity proof => closed |
| Prepared (1) | exact S; legacy initial domain or prior closed view, floor N-1; selector cannot promote C | S only after weaker fallback domination/exclusion; intent owns T, fixed child keys and inactive cp | finish GSRG Prepared, authenticate S/T, advance Copying; mismatched T/source or occupied unowned target => closed |
| Copying (2) | same pinned S and floor; candidate/selector higher generation ignored | S only; create/retry one named ev or ret; optional admitted ef/ev pair; then inactive C | classify every stage, rebuild/verify children and C; valid-MAC wrong content or lost S => closed |
| TargetVerified (3) | S remains authoritative, floor N-1, even if sel names C | S only; verified C exact digest; write/readback candidate selector | verify C/selector again and write Published; mismatched C/source/digest => closed |
| Published (4) | exact C, RegistryOwnerV2 closed view, floor N; GMM is authority, sel confirms target | ONLY C; old S excluded but source child retained; copy exact C bytes to old cp bank | verify/write shadow, then Cleanup; missing C before shadow proof => closed, never old S |
| Cleanup (5) | C or byte-identical shadow, same generation/T/frontier/digest | both exact roots legal; named source child must be excluded by BOTH; exact erase only | retry/verify absence then BatchDone; mismatch/reachable source or corrupt proof => closed |
| BatchDone (6) | same committed C/shadow and floor N; both manifests retained | no new stage until previous release is verified; all history/floors retained | next Prepared at N+1, or final activation transaction; unexplained leftover overlap => closed |
| Activated (7) | non-MigrationView current-domain C/shadow, GSRG2 Activated matching T/provenance, floor N | exact roots only; typed legacy events retained; ordinary authenticated operations after fresh rejoin | Ready jointly derived; unmatched registry/root, legacy compressed ref, missing/corrupt barrier => closed |

All failures preserve evidence. No transition to legacy Ready is legal after first
Published. NormalPublication reuses these states at SAME completed migration frontier,
with a newer source generation; it freezes traffic until Activated again. Initial
migration never sets that bit. In a normal transaction the prepublication floor is N,
not N-1. This prevents report/config/archive publication from reviving pre-ACK metadata.

### 20.5 G05 object ownership and exact release

| Existing physical family | Durable owner / expected identity | Boot validation and release |
|---|---|---|
| gs_registry/snapshot | Prepared intent T/source provenance, then activated joint authority | v1 or exact canonical Prepared identity; retain base projection; corruption closes; no erase |
| inactive cp0/cp1 | Prepared source_bank implies opposite bank, generation G+1/T/N | before verified, validate canonical candidate from S; torn owned candidate is repairable only while S remains exact; after verification require exact target digest; never delete legal cp |
| ev mapped u64 | EvidenceChunk source/target IDs, source-child HMAC, deterministic `(target_gen<<8)|1` target; full contents from S/T | absent retry; exact canonical staged object reusable; partial owned bytes may be conditionally replaced preverification; wrong authenticated content closes; old ev exact release in Cleanup |
| ret0..ret2 | RetirementSnapshot source/target bank IDs, source-child HMAC; target snapshot generation derived/locked by S and batch | target must be excluded by every legal root after Prepared and preserve all floors; schema1 read supports 6096, new encode <=5777; old ret exact release in Cleanup |
| ef mapped u64 + paired ev | TailPair names deterministic set derived from G+1 using existing key formulas; source-child digest covers canonical frozen tail | optional only if union<=32 ef/33 ev; intent precedes BOTH children; first-child-only reboot resumes second; no ef archive deletion |
| tr0..tr3 | existing S/C prefix or causal GDT3 extension, never unowned staging | four slots, consecutive ordinals/epoch; no migration tail rewrite; covered records cannot become authority |
| e000..e127 | virtual source or typed legacy-slot root closure + authenticated full event/slot | exact original bytes retained; new e writes forbidden; no migration deletion |
| c000..c127 | exact EventKey/slot HMAC independent receipt + event retained by every legal root | verify all receipts; persisted receipt failure resolved by exact reread; no erase/rewrite |
| bm0/bm1 | authenticated existing mapping, unchanged | preserve/read-validate; unsupported live use closes; no migration scratch |
| sel0/sel1 | authenticated exact root generation/bank; current intent owns bounded selector publication/repair | stale authenticated selector is filtered by GMM; it cannot select another generation; corrupt selector repair only from independently exact GMM authority |
| mig0/mig1 | authenticated same transaction, legal predecessor/successor relation | fixed A/B writes only; partial/corrupt/conflicting bank closes; no migration metadata erase |

A ret target may contain an authenticated obsolete legacy value before staging. Reuse
requires independently proving its bank is excluded and S dominates every floor/history
it could preserve. Compare the exact currently read bytes under the single mutation
lease before replacement. A valid old excluded value is distinguishable from an existing
candidate by its locked snapshot generation/schema. Unknown value, unsupported report
or unexpected valid candidate closes. The intent authorizes this specific bank reuse;
object presence alone does not. If two legal report banks leave no target, Prepared may
exclude the dominated fallback; it may not destroy the sole selected report.

Source release algorithm: authenticated Cleanup with exact target digest; authenticate
both legal cp closures and prove source key is excluded from both; read named source;
compute the keyed source-child digest over epoch/kind/ID/exact bytes and compare intent;
call erase_if_equals(key, those bytes) under the same mutation lease; reopen/read absent.
API failure plus proven absence completes release; API success without absence does not.
Different occupant, corrupt source, or digest mismatch closes WITHOUT erase. Missing source
is idempotent only in Cleanup/BatchDone, never before publication. No family scan/delete.

After converting the selected report, a formerly fallback/unreferenced ret value can be
released in a separate RetirementSnapshot batch: name that obsolete bank as source,
name the verified selected v2 bank as target, prove selected rejection-set dominance,
publish an unchanged-semantic new cp and exact shadow, then erase only that named source.
Thus no abandoned historical bank needs an extra digest, mask or key. Never erase ef,
e/c or pinned descriptors. A missing/corrupt unowned stage is not forgiven as garbage.
No next batch starts until one-overlap inventory is restored.

### 20.6 Publication, A/B, fallback and normal-operation proof

The driver orders: Prepared -> Copying -> children -> candidate cp -> equivalence
readback -> TargetVerified -> selector readback -> Published -> EXACT shadow readback ->
Cleanup -> exact source release/absence -> BatchDone. Manifest writes alternate banks
and must be exact authenticated readbacks; write return values are not phase evidence.
Final batch additionally performs registry activation and then Activated (20.7).

Both manifest banks must authenticate and either be byte/field-equivalent or be the
specified adjacent predecessor/successor. Within a batch all source/T/IDs/frontier
fields are fixed. Target generation/digest become fixed at TargetVerified. BatchDone ->
Prepared increments frontier by exactly one and pins the previous exact candidate as
source (bank may be either authorized identical copy). No arbitrary migration ID order.
A single initial Prepared frontier1 bank can be accepted with independently verified
original source and absence of any evidence of publication. Every later step requires
both banks. Missing one later bank closes: an old TargetVerified bank cannot prove that
a lost Published bank never existed. Missing both with GSRG2 or any GCP3 migration root
closes. Present corruption always closes; no older-bank rescue based on phase guessing.

**FALLBACK_ROOT_SELECTION_RULE:** authenticate GMM first. Before Published select only
its pinned source digest/generation/bank, with frozen source tail. Published selects only
the exact candidate. Cleanup and later additionally authorize the source bank ONLY when
it contains the BYTE-IDENTICAL candidate checkpoint and its independently verified exact
compound digest. Same generation/nonce/ciphertext/references are intentional; normalize
only the physical cp bank label in compound hashing. No semantic-only or newer-generation
shadow is allowed. Prefer the selector's exact allowed copy; if selector absent/corrupt,
GMM's exact candidate then authorized shadow is deterministic authority and traffic stays
closed during repair. A valid selector naming an unexplained higher root is a conflict.
An authenticated stale selector whose target was replaced is stale, not a fallback grant.

**PUBLISHED_FRONTIER_FLOOR_RULE:** actual authenticated Published/Cleanup/BatchDone/
Activated frontier is minimum. A later Prepared pins precisely that committed view, so
it retains the floor while another batch is unpublished. Root digest/T/domain and the
full acknowledged rejection predicates must also match; a large numeric frontier alone
is never proof. **OLD_ROOT_REJECTION_RULE:** any otherwise valid lower root is illegal,
including on selector failure, and cannot grant Ready or justify release.

Proof by transition: Prepared excludes only dominated fallback; C is semantically equal
except verified coordinates; Published commits its exact bytes/floors; Cleanup grants
only an identical shadow; release cannot remove any reachable child. The next Prepared
pins that view. Induction therefore preserves retained history, completion associations
and acknowledged rejection sets for every frontier. Candidate loss before Cleanup closes;
authorized shadow loss leaves exact C; both lost closes. Selector failure changes no
minimum floor. Corruption does not authorize a destructive fallback.

After Activated, ordinary new GDT3 append and independent c commit are allowed without
changing the fixed digest: new tail is an authenticated causal extension, new receipts
verify independently. At tail capacity, archive/checkpoint/report/config publication uses
NormalPublication through the same driver. Freeze the full tail in intent before stage,
prove all legal roots/history/report rejection sets, publish generation G+1 at the SAME
migration frontier, shadow and release only eligible coordinate metadata, then Activated.
For normal report ACK, Published readback and shadow/Activated joint recovery are required
before ACK. Refresh the GSRG activation digest to the new exact root through the verified
coordinator save operation before GMM Activated; keep source provenance and all identity
fields. This applies also to metadata-only transactions and uses the existing single
registry key (the v2->v2 replacement bound below). No direct selector-only `checkpoint()`
fast path bypasses this barrier. A general caller cannot change the activation digest.

Unlike migration conversion, a NEW retirement report/config update is not reconstructable
from S alone. NormalPublication Prepared/Copying therefore use their existing target
generation/digest fields to authenticate G+1 and a HMAC of the canonical intended
operation: operation kind, T, exact target child keys, decoded child semantics and the
candidate's normalized semantic projection. Exclude encryption nonces/raw reference
digests in this EARLY planned digest, include original Node report HMAC and all fields.
Prepare this digest before staging; read/authenticate the new child, reconstruct C and
check its planned projection against that digest. At TargetVerified replace it with
the exact compound ciphertext digest. The adjacent Copying bank still carries the early
digest; verify this transition against both records and actual candidate. Later phases
keep the exact digest. No extra target-digest field or entry is needed.

Boot after intent but before a NEW operation's child persisted cannot reconstruct the
requested payload. If child absent/partial, cancel that UNPUBLISHED normal operation
without ACK: rebuild unchanged-semantic C from exact S at G+1 and SAME frontier; write
C, then TargetVerified with CancelledNormalPublication set and its exact digest. For a
present partial stage, this special adjacent successor names the former target as the
source-to-release, the original selected child as retained target, and pins the exact
partial bytes in source_child_digest. If no stage exists, use FinalActivation's zero
child IDs/digest for the cancelled metadata-only batch. The original root digest/T,
generation, frontier and source tail remain fixed. The predecessor intent must own the
abandoned key; candidate must preserve S exactly and exclude that key. This is the ONLY
permitted change of family/key/digest fields within a batch, and only NormalPublication
Copying -> TargetVerified may set cancellation. A valid authenticated stage with wrong
planned contents is a conflict, not cancellable. Before TargetVerified an incomplete
candidate bank may be rebuilt under its existing intent; verified/published bytes stay
fixed. Publish the unchanged view, write exact shadow, Cleanup, conditionally release
the now-named partial stage, BatchDone, GSRG digest refresh and Activated. No report
success ACK; require fresh rejoin after reboot and retry the report as a new transaction.
This bounds recovery without persisting a queued wire payload or accumulating stages.
Initial migration has deterministic source-derived children and never uses cancellation.

NormalPublication starts only from Activated; its Prepared source is the prior exact
committed cp plus independently authenticated bounded tail extension. Compare the old
protected-prefix digest first, then pin the full frozen source-tail digest. Those two
digests need not be equal when new events appended. A/B validates this linked successor,
using source_generation to distinguish same-frontier transactions; `(frontier, phase)`
alone is insufficient. Within the transaction advance adjacent phase codes; terminal
Activated -> Prepared requires increasing source generation linked to previous target,
NormalPublication set and retained frontier. This is lineage validation, not highest cp
wins. Do not use phase 7 to outrank a legitimate newer Prepared at the same frontier.

Registry rejoin/session refresh leaves T unchanged. Revocation changes authenticated
active authorization and retains identity descriptors, so T remains unchanged. Adding
an enrollment/replacement adds exactly one lowest NeverOwned descriptor. Freeze first;
compute Tnew and persist linked NormalPublication Prepared before GSRG2 Prepared extension.
Existing descriptor identity tuples never change. Recover Told by the unique authenticated
old occupied-prefix projection of the extended table (never infer owner from hash); validate
old root under Told and candidate under Tnew. All descriptors allocate lowest NeverOwned,
so old occupied count is candidate occupied count minus one. Failed/unsupported extension
closes; no transport grants under the partially prepared table. Publish matching Tnew root,
activate registry, then Activated. Registry phase regression is legal ONLY inside this
verified coordinator-owned table-extension transaction; current general save guards must
be refined for that operation, not removed. Report/receipt ownership for retired owners
remains their original tuple. Ten occupied/pinned descriptors rejects before any mutation.

There is one additional normal cancellation case: intent Tnew persisted but the new
GSRG Prepared table did not persist, leaving an authenticated GSRG Activated Told.
No new-owner transport ACK may have been sent. Boot can cancel that unpublished extension
using an unchanged-semantic C with Told, through the same cancelled normal barrier above.
The special Copying -> TargetVerified successor may replace intent Tnew with Told ONLY
when exact S and the existing Activated registry authenticate Told, no prepared extension
exists, no legal root granted Tnew, and all named stages are accounted for/excluded. It
cannot discard a persisted Prepared descriptor: if GSRG Prepared Tnew exists, recover
its full candidate identity and finish the extension instead. Missing/corrupt registry
still closes. Thus an intent alone does not require storing a second registry or the
commissioning request. Initial GSRG-v1 preparation remains source-derived, never cancelled.

### 20.7 Final activation and fresh installations

The final batch has family FinalActivation, source/target child IDs zero, unchanged
semantic history, next frontier and candidate MigrationView=false. No legacy compressed
ev or selected report reference may remain. Complete normal publication, exact shadow,
Cleanup(no child erase) and BatchDone. Write/readback GSRG2 Activated with T, preserved
source provenance and exact final target compound digest. Then write/readback GMM2
Activated, retaining both manifest banks. Verify registry/table, allowed root, every
child/legacy representation, independent receipt and floor jointly. Only then construct
Ready runtime, discard all old sessions/reassembly/queued stale traffic, and require a
fresh authenticated rejoin before accepting any Node operation. Rejoin preserves slot/gen.

GSRG Activated with GMM BatchDone is still CLOSED; finish the final manifest after exact
joint verification. GMM Activated with missing/Prepared/mismatched registry is CLOSED;
that is an invalid ordering, not permission to promote registry by inference. Published
final root with GSRG Prepared is a closed historical projection only. At no boot does
live authorization use one ownership domain while evidence uses another. Literal
Prepared-v2 bytes alongside a legacy source are expected staging, not v2 authority.
No old registry/root may be restored to clear the activation barrier. Retain migration
manifests; retain typed legacy full events. There is no blanket legacy purge.

Fresh installation also prepares T and a logical empty source, publishes/activates a
matching GCP3 before first registry Event; use the virtual-source prelude with proven
freshness and empty inventory. No physical legacy genesis has to be created before
intent. Initial zero-owner T is valid; first commissioning then extends it through the
same table transaction. Authenticated contradictory freshness/evidence closes service.

### 20.8 Crash matrix (each row reloads persisted bytes)

| Power loss boundary | Boot selection | Retry/release and traffic |
|---|---|---|
| Before intent | authenticated original/virtual S | preflight again; no deletion, traffic closed |
| After intent, before/after GSRG Prepared | pinned S; v1 or unchanged Prepared base projection | regenerate/verify T; finish registry preparation; corrupt registry closes |
| After Copying / each staged child (including first TailPair member) | S only | authenticate intent, classify named children, retry missing/partial preverification child; wrong MAC-valid content closes |
| After candidate root | S only even if C generation higher | authenticate all C refs, equivalence and exact digest; repair incomplete owned C only before verification |
| After candidate verification, before manifest | S only | repeat verification; no inferred progress or erase |
| After TargetVerified manifest | S only | reuse exact C; write/readback candidate selector |
| After selector/publication barrier write | S while GMM TargetVerified | selector alone publishes nothing; verify C and commit Published |
| After Published, including PersistThenFail | exact C at N | reread both manifests; resume exact shadow; no old-root fallback/release |
| During shadow update | exact C; old bank not fallback yet | finish exact byte copy/readback; loss of C closes until Cleanup proof exists |
| After shadow, before/during Cleanup manifest | Published C, or Cleanup C/exact shadow | complete durable Cleanup proof before source erase; partial GMM closes |
| During exact cleanup | Cleanup C/exact shadow | exact source present => guarded erase; absent => verify completion; mismatch => close without delete |
| Before final activation | last published closed view or final BatchDone root | no Node ACK/rejoin; prepare final zero-data batch or activate registry |
| During final GSRG activation | final root; no Ready unless joint Activated | Prepared/Activated readback determines retry; torn registry closes, no rollback |
| During final GMM activation | final root; BatchDone remains closed or Activated jointly verified | PersistThenFail resolved by exact readback; corrupt/missing later bank closes |
| After activation before traffic resumes | exact final current-domain root/table | rebuild empty session maps; require fresh rejoin, then allow traffic |
| Repeated reboot between batches | prior exact published frontier, then current pinned S | reuse named IDs/gens; no accumulation of overlaps or enrollment reassignment |
| Later normal report/checkpoint transaction | prior current root before Published, new exact root after | same-frontier generation lineage enforced; no success ACK until joint recovery |

### 20.9 Actual object ledger and admission certificate

Derived from current codec/provider layouts, not `3206 + 18` alone. Formula for a live
blob is `2 + ceil(payload/32)`; namespace is one entry. Partition modeled capacity is
4032 entries/131072 bytes. Canonical selector bytes are 4 magic +8 generation +1 bank
+28 AEAD =41 (provider permits 64; canonical decode must reject trailing/noncanonical
values). Retirement legacy READ cap remains6096; current WRITE cap is5777. Both banks'
GMM framing is fixed218, and all proposed flags fit existing bytes.

| Key/family in gs_journal/events | Values at bounding peak | Max payload/value | Entries/value | Total entries | Payload total | Simultaneous source/candidate reason |
|---|---:|---:|---:|---:|---:|---|
| namespace events | 1 | 0 | 1 | 1 | 0 | existing namespace, counted once |
| cp0/cp1 | 2 | 4549 | 145 | 290 | 9098 | pinned source/inactive candidate; later exact shadow |
| sel0/sel1 | 2 | 41 | 4 | 8 | 82 | old selector and candidate publication |
| tr0..tr3 | 4 | 1332 | 44 | 176 | 5328 | protected/live tail, shared unchanged |
| ef mapped u64 | 32 | 1260 | 42 | 1344 | 40320 | retained event/effect archives shared, no conversion copies |
| ev mapped u64 | 33 | 320 | 12 | 396 | 10560 | <=32 retained + ONE named overlap, never a second batch |
| ret0..ret2 | 3 | 6096 legacy read | 193 | 579 | 18288 | selected, excluded prior bank, reserved target; all old maxima conservatively counted |
| bm0/bm1 | 2 | 384 | 14 | 28 | 768 | existing immutable-for-migration mapping values |
| c000..c127 | 128 | 32 | 3 | 384 | 4096 | independent receipts shared without copies |
| mig0/mig1 | 2 | 218 | 9 | 18 | 436 | authenticated adjacent intent/publication records |
| e000..e127 | 0 in THIS full-archive peak | 284 | 11 | 0 | 0 | raw-event profiles use the weighted alternative below, not uncounted objects |
| **Total** | | | | **3224** | **88976** | every candidate already inside its family bound |

`PEAK_FREE_ENTRIES=4032-3224=808`; `PEAK_MARGIN_PERCENT=100*808/4032=20.0396825397`;
`PEAK_FREE_BYTES=131072-88976=42096`. Once all three ret values are compact the same
upper ledger is3194 entries/88019 bytes. Namespace is included in entry totals; raw
payload bytes exclude physical NVS headers/page/GC cost, covered by operational reserve
and later physical qualification. Same-key flash replacement dead entries are not an
extra LIVE object; do not claim instantaneous nvs_get_stats meets this modeled margin.

Raw e values MUST be charged: replace `42*n_ef +12*n_ev` by actual union counts and add
`11*n_e` (and exact actual bytes). The all-raw profile with128 e, zero ef/ev and remaining
family maxima uses2892 entries/74448 bytes, leaving1140 entries/56624 bytes. Mixed
profiles pass only if the actual live union plus the complete reserved candidate plan
fits BOTH 3224 entries and88976 payload bytes, family limits and128 logical events.
A single extra e at the full-archive peak means3235 entries/797 free: REFUSE that source
profile without writes. A one-entry excess likewise stops. Objects are never omitted
because obsolete/unselected; admission charges every physical value until exact release.
Reserve cp/ret/mig maxima and future ordinary growth of retained typed events as well as
the one ev overlap; recheck before every mutation. Full legacy e/c duplication into
archives is not this design and is not budgeted. Provider cap64 selectors would produce
89022 raw bytes at full maxima; canonical41 admission is required for the stated bound.

Registry uses SAME default-nvs `gs_registry/snapshot` key, max5077. v1 max3996 plus v2
replacement9073 bytes/288 modeled blob entries (+existing namespace). A later v2->v2
replacement bounds10154 bytes/322 blob entries, not9073. Default partition24576 also
contains other security state; inspect/admit that union and provider allocation separately.
No new registry key is approved. This journal certificate does not certify that partition,
physical allocator/GC or power cuts. It must be rederived from finished production output
before commit; current tests' hard-coded source_family_entries=3206 are insufficient.

ACTUAL_MANIFEST_TOTAL_BYTES=436; ACTUAL_MANIFEST_TOTAL_ENTRIES=18;
ACTUAL_RETIREMENT_CURRENT_ENCODE_MAX_BYTES=19+10*(61+32*16)+28=5777;
ACTUAL_CANDIDATE_CHECKPOINT_CAP_BYTES=4549; NEW_PERSISTENT_KEY_FAMILIES=0;
NEW_SCRATCH_KEYS=0. No persistent scratch counter, shadow digest or registry backup.
All flags/refinements stay within current envelopes. Any implementation growth requires
STOP/rebudget, not use of the one-entry rounding slack or partition enlargement.

The checkpoint cap is attainable from actual codec fields: fixed header63 + count bytes4
+16*10 effect refs +32*8 chunk refs +32*40 evidence refs +35 extension +28 AEAD =1826;
reducer2723 gives4549 without report, or report reference41 + reducer2682 gives4549.
Candidate construction checks the WHOLE encoding cap, not independent reducer/reference
maxima. The protected count/legacy-slot flag replaces no byte and adds no encoded byte.

### 20.10 Resume review, abstract validation and production handoff

RESUME_DIFF_REVIEW=PARTIAL. Reusable: ten pinned descriptors/initial generation1,
registry owner-digest/resolver work, GSRG2 framing scaffolding, compact snapshot mask,
conditional erase, authenticated GMM2 framing/A-B scaffolding, GCP3 cap/domain gate.
Incomplete: manifest-aware inventory, candidate construction, publication driver,
GSRG preparation/activation and post-activation normal publication. Specific corrections:

- `compound_root_digest()` currently includes physical cp bank, ALL tr and c values;
  implement the specified stable closure and independent receipt verification.
- `recover()` currently rejects all mixed-domain references even in MigrationView and
  ignores typed legacy-tail/slot projection; add a CLOSED inspection context, preserve
  the ordinary new-Event domain gate.
- Activated recovery currently accepts a selected newer root without exact manifest
  lineage/digest; remove this selector-only authority path.
- `inventory_chunks_owned()` must recognize exact current intent stages/source release,
  while accounting every physical object and rejecting unexpected keys/content.
- Snapshot `decode()` currently applies5777 to schema1 input and `load()` rejects legacy;
  separate authenticated inspection6096 from current encode/load5777.
- `HubSecurityLink::persist_candidate()` attempts restore into an already populated
  candidate; verify into a fresh instance and replace only after durable joint checks.
  Fresh commissioning also lacks initialized registry/root provenance.
- Existing GMM successor guards hard-code target/source-bank alternation and frontier/phase
  ordering; allow independently exact shadow source and specified same-frontier lineage.
- Existing raw-journal migration tests require deleting e/c and synthesize registry Events
  against legacy root; replace that fixture contract with typed retained-event activation.
  Do not "fix" the failure by removing the domain check or changing Node wire fields.

Implementation order for Luna High (existing paths, new portable functions are proposed):

1. `storage/durable_transition.{hpp,cpp}`: checkpoint/manifest flags; canonical digest
   helper with explicit source/target tail scope; exact `legal_manifest_successor()` and
   `MigrationManifestRepository::load()/advance()` for two-bank and normal lineage.
   Add production codec/phase/corruption tests in `tests/cpp/hub_durable_storage_validation.cpp`.
2. `registry/registry_persistence.{hpp,cpp}`: explicit `prepare_v2()`/`activate_v2()` and
   canonical table/projection APIs, coordinator-only table-extension save guard; retain
   all security fields/readback. `registry/node_registry.{hpp,cpp}`: immutable owner
   context lookup, pinned historical view and deterministic preparation. Add v1 fixtures
   and boundary tests in registry validation files before proceeding.
3. `storage/node_retirement_snapshot.{hpp,cpp}`: authenticated legacy inspection6096,
   table-bound current read5777, deterministic conversion/full rejection-set equivalence,
   explicit intent-selected bank write (not selected-bank-only `prepare_bank()`).
4. `storage/hub_durability_owner.{hpp,cpp}`: manifest-first `inspect_checkpoint_set()`,
   `inventory_chunks_owned()`, virtual source, weighted admission ledger and joint Ready
   derivation; CLOSED historical resolver distinct from active transport resolver.
5. `storage/durable_transition.{hpp,cpp}`: proposed `stage_candidate_checkpoint()`,
   `verify_candidate_projection()`, `publish_candidate()`, exact shadow copy/readback,
   `release_named_source()` and bounded `resume_migration_step()` coordinator owned by
   HubDurabilityOwner. Reuse same driver for NormalPublication; ordinary `checkpoint()`
   delegates instead of selector-only publication. No ordinary historical Event commits.
6. `target/esp32/nvs_durable_blob_store.{hpp,cpp}` and `nvs_store_inventory.cpp`: exact
   lease/conditional replacement and release/readback integration, legacy/current caps,
   complete inventory/reservation checks; retain key mapping/no automatic broad erase.
7. `storage/durable_journal_slot_store.{hpp,cpp}`: `rows()/read()` typed e/tail reads,
   shared c receipt authentication, coordinator replacement of `migrate_legacy_journal()`;
   `read_completion()/publish_completion()` retain archive bytes while validating/publishing c;
   remove migration calls to `import_completion()/replace_completion()` that rewrite ef;
   `append_event()` accepts only verified current authenticated owner after activation.
8. `target/esp32/hub_security_link.{hpp,cpp}`: `initialize()`, `persist_candidate()`,
   `resolve_enrollment_binding()`, `accept()` freeze/joint activation/table transaction;
   resolver must receive authenticated session/device context, not payload-only identity.
   `target/esp32/hub_runtime_adapter.cpp::secure_owner_task()`: bounded resume before
   runtime attach, block all migration traffic/ACK paths, final rejoin reset and retirement
   report publication through common barrier. No Node protocol changes.
9. `tests/cpp/hub_journal_migration_validation.cpp`, provider/owner/security/retirement
   tests: actual byte/provider cuts after EACH write/readback, repeated batches, virtual
   source, same-frontier report floors, owner injection, typed legacy preservation,
   mismatch cleanup and all budget/layout assertions. Then all requested broad gates,
   Hub/required Node target builds and final actual implementation budget audit.

The standalone `tests/python/test_g01_coordinator_crash_model.py` is the architecture
model for these decisions; it cannot certify production codecs/provider behavior. No
production tests/builds are rerun or claimed fixed in this architecture-only turn.
G03/completed-effect retirement/reclamation remain unimplemented;128-event limit remains.
PHYSICAL_GC_QUALIFICATION=NOT_RUN; POWER_CUT_QUALIFICATION=NOT_RUN; RADIO_HIL=NOT_RUN.

Architecture-only validation on2026-10-04:
`python3 -B tests/python/test_g01_coordinator_crash_model.py` -> PASS,37 tests.
The model includes120 boundary/failure-mode scenarios across ordinary migration/final
activation and virtual-source activation, serialized restart, intent/candidate ownership,
exact shadow, two-bank loss/conflict, receipt independence, repeated normal batches,
planned normal report/cancellation, table extension, attribution refusal and a ledger
computed from provider caps. NormalOperand is focused planned-operand coverage, not a
complete normal-operation firmware simulator. Cryptographic/provider/target fault tests
remain required; these results grant no production or physical qualification.

G01_COORDINATOR_ARCHITECTURE_READY=YES
G02_PUBLICATION_ARCHITECTURE_READY=YES
G05_STAGING_ARCHITECTURE_READY=YES
V1_TO_V2_MIGRATION_READY=YES (guarded attributed/admitted source profiles)
CRASH_RECOVERY_MODEL_READY=YES (abstract contract level)
ACTUAL_PEAK_USED_ENTRIES=3224 (specified live+staging ledger, not physical measurement)
ACTUAL_PEAK_FREE_ENTRIES=808
ACTUAL_PEAK_MARGIN_PERCENT=20.0396825397
PEAK_USED_BYTES=88976
PEAK_FREE_BYTES=42096
NEW_SCRATCH_KEYS=0
READY_TO_RESUME_PRODUCTION_IMPLEMENTATION=YES
G01_PRODUCTION_IMPLEMENTATION_COMPLETE=NO

All changes from this architecture turn are uncommitted: this contract and the new
standalone abstract model only. The original23-file diff is checked separately for exact
preservation. No production coordinator, release gate, target build, commit or push is
performed here. Continue implementation in the existing worktree; do not restart it.
