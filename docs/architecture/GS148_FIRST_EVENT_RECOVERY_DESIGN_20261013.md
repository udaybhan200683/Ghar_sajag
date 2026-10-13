# GS-148 / GS-145 — first-event recovery decision review

Date: 2026-10-13 UTC. Source and actual GitHub baseline:
`371a560f04b99bce8fd86e58739a75184b555b55`, canonical
`/home/udaybhan/projects/Ghar_sajag_r1`, `feature/r1-commercial-baseline`.
Context preflight PASS, `2026-10-11.001`; tracked tree initially clean.

**DESIGN_READY_FOR_APPROVAL. PROPOSED IMPLEMENTATION; NOT IMPLEMENTED OR TESTED.**
This supporting design does not change LOCKED requirements, approve its own
implementation, establish an OTA support matrix, or qualify a release.
The owner's approved design guidance is simplicity, reliability, affordability,
maintainability and proportional security (GS-148 10681; GS-145 10682).
The recovery algorithm below remains a proposal requiring separate authorization.

## A. Executive recommendation

Choose **Option A: reuse the authenticated v1 application checkpoint and selected
identity to recognize one interrupted first admission as pending**. Retain its
encrypted body and exact identity; let the existing authenticated Node retry
finish ordinary v1 event-head publication, reducer checkpointing and ACK.
Do not publish an event merely because boot found it.

This needs a narrow coordinated recovery check, not a new genesis file, format,
key, installation manifest or cloud call. The existing zero-boundary application
checkpoint is the initial authority. Its relationship to ACK ordering, selected
identity and body must be checked together. Outbox-only missing-head recovery
must continue failing closed.

Also cover interruption between the existing zero identity-head write and initial
application checkpoint. Repair that initial checkpoint only when the complete
selected inventory proves empty, as specified below. Do not treat a corrupt
checkpoint as an absent initial checkpoint.

The earlier 116-byte v2 genesis proposal in the P0/P1/P2 handoff was a candidate.
Its assumption that a new record was necessary is superseded **for this bounded
current-format problem** by this review's source-derived alternative. It is not
an approved or activated format. General installation/transfer and lifetime
storage packages remain independent.

## B. Root cause and the authority proof

Current production sequence:

1. `HubRuntime::restore_from_journal()` creates an authenticated application
   checkpoint at event boundary 0 before the target accepts events.
2. Admission selects `identity.head` at ordinal 1, binding an authenticated row
   with exact EventKey, HMAC of the serialized payload, original local minute
   and enrollment owner evidence.
3. The outbox writes and verifies the encrypted first body.
4. It replaces and reads back the authenticated event publication head.
5. Runtime confirms publication, applies the event and durably saves the
   application checkpoint at boundary 1.
6. Only then can the normal target send an authenticated Durable ACK.

`GSHD` v1 has no valid ordinal-zero representation. Its encoder and decoder
reject zero. `DurableEventOutbox::recover()` consequently rejects a complete body
when the event head is absent, before the target can consult `RuntimeStateStore`.
The existing scanner remembers an unpublished body's digest only when a prior
publication head exists. All three demonstrated first-admission failures thus
stop at IntegrityFailure, even with a valid selected identity and checkpoint 0.

**Why existing authority can be sufficient:** under the current single-writer,
atomic replacement and persistence-barrier contract, every first Durable ACK
requires a successfully persisted application checkpoint at boundary at least 1.
Normal code cannot subsequently reduce that boundary to 0. A valid, selected
checkpoint 0 therefore proves that the selected application state has not
durably accepted/applied a journaled event, provided all other selected stores
are consistent. Policy-discard ACKs and pre-event configuration/health activity
are distinct from Durable journal admission; they must not cover the candidate
key through an authenticated retirement fence.
The identity head authenticates the chosen row; the row authenticates the exact
body payload and original context. This proves ownership of an interrupted
transaction, not that an event publication previously succeeded.

Treat it as unpublished, with high-water 0, and complete it only on exact retry.
Even if a head once reached disk and subsequently disappeared before checkpoint
1, the proposed classification never claims prior success or skips the pending
effect. Previously ACKed state with a missing head has checkpoint >=1 and is
refused. No fallback application checkpoint, temporary `.new` file, prepared
identity alone or body alone can supply this proof.

Two existing guards make this reuse practical: `contains` returns `Staged`,
rather than `Found`, for an indexed body above public high-water; the journal
backend recognizes only `Found` as a committed duplicate. `for_each` stops at
public high-water. Retaining the first index entry at high-water 0 therefore
neither ACKs it through the duplicate shortcut nor replays it as committed.

This reasoning depends on the same barrier guarantees already required for
durable-before-ACK. It is a source-derived crash-consistency argument, **not new
physical proof** of LittleFS/NVS behavior. Deliberate restoration of an otherwise
valid older flash image remains outside GS-D029's freshness guarantee. No new
anti-rollback threat model is adopted to solve this admission problem.

## C. Existing mechanisms and source anchors

All paths below are relative to repository root; old version-wrapper paths are
historical. The delivered P0/P1/P2 fixes and their comprehensive campaign are
preserved.

| Mechanism | Current source | Reuse and limit |
|---|---|---|
| Authorized local Home/Hub and registry | `code/firmware/hub/target/esp32/hub_security_link.cpp`: `initialize`, `event_journal_key`, `resolve_enrollment_binding` | Journal key derives from existing wrapping key and Home/Hub salt. Resolve original physical Node, logical ID, slot, generation and binding digest; no MAC-only authorization. |
| NVS owner and epoch | `code/firmware/hub/storage/hub_durability_owner.cpp`: `recover`, `initialize_epoch_one` | Existing authenticated native checkpoint/selectors, freshness/inventory checks, epoch 1 bootstrap; no owner recreation on missing evidence. |
| Selected identity and empty state | `code/firmware/hub/storage/runtime_state_store.cpp`: `save_checkpoint`, `recover`, `record_at`, `lookup_identity` | Existing GSR1 type-2 zero identity head and type-3 checkpoint, with authenticated ordinal in AAD. Selected row HMAC includes the complete encoded payload. |
| Segmented body and publication | `code/firmware/hub/storage/durable_event_outbox.cpp`: `recover`, `decode_record`, `publish_through`, `append`, `admission_ready` | Existing GSOX v1 AEAD/CRC and GSHD v1 HMAC. Existing exact staged-body retry already publishes without rewriting the body. |
| Event payload semantics | `code/firmware/hub/storage/journal.cpp`: `encode_event_payload`, `decode_event_payload`; `outbox_journal_backend.cpp` | Canonical key must match decoded EventKey; compare full versioned bytes, not an invented subset. |
| Reducer restore and ACK barrier | `code/firmware/hub/runtime/hub_runtime.cpp`: `restore_from_journal`, `run_state_once`, `checkpoint_state`; `hub_checkpoint_codec.cpp` | Restore checkpoint 0; pending body is excluded from replay. Retry uses original minute; publication and checkpoint precede Durable. |
| Root/report/witness protection | `durable_transition.cpp`, `node_retirement_snapshot.cpp`, runtime replay-fence reconciliation | Retain active/fallback bank pins, equal-generation conflict rejection, epoch/generation checks and RPF00–RPF08. Check all recovery-eligible roots before admitting the special case. |
| Target owner sequencing and writes | `code/firmware/hub/target/esp32/hub_runtime_adapter.cpp`; `target/esp32s3/littlefs_segment_store.cpp` | S3 uses this shared owner. Target mounts without formatting; replacement uses temp write, flush/fsync, rename, post-rename fsync and exact core readback. |

The current target initializes the native epoch at 1. There is no production
caller of `commit_candidate_epoch` in `code/firmware`; it is a library seam.
Neither GSR1 nor GSOX v1 independently stores the NVS epoch. Do not claim they
do. Restrict the missing-head exception to the currently demonstrated native
fresh-install epoch-1 domain. Other epochs with ordinary valid publication heads
retain ordinary recovery; a missing head in another epoch stays fail closed.
Adding/recommissioning a future epoch is GS-132 work, not an implicit assumption
of this fix.

## D. Alternatives

| Parameter | A — existing authority, pending retry (recommended) | B — minimal authenticated empty head | C — extensive versioned authority |
|---|---|---|---|
| Correctness | Safe for the exact native tuple below. Does not claim missing publication succeeded. Reuses pending retry and preserves ACK barrier. | An authenticated empty marker before bodies provides a zero publication boundary, but still requires exact identity/body joins and empty initialization checks. A stale zero marker alone cannot justify losing a later head. | Can explicitly bind epoch/incarnation, but authority issuance and safe initialization still require proof; more metadata does not automatically establish correctness. |
| Complexity | Outbox scanner validation hook, initial-state inspection/repair, owner wiring; one existing pending classification, no persistent state machine. | Extend zero-head codec semantics, bootstrap write/readback and readers. No need for a new manifest/key hierarchy for this candidate. | Versioned codecs, identity binding/issuer, activation and compatible readers/writers; multiple extra modules/interfaces. |
| Compatibility | Every written byte already belongs to the existing v1 contract. Old readers keep their existing fail-closed behavior for interrupted first admission; see G. | Old v1 decoder rejects ordinal 0. Same-size/same-version bytes do **not** mean compatible semantics. Needs reader adoption or a new version. | Old readers reject v2; explicit rollout and rollback support required. |
| Essential security | Existing Home/Hub key domain, Node ownership, GCM/HMAC, root consistency and exact payload. No new key. | Reuse existing publication HMAC key for a minimal design; owner/epoch limits remain those of current v1 unless separately changed. | Explicit epoch/incarnation may help independently required future lifecycle work; no demonstrated additional requirement for this fixed native first event. |
| Performance | Zero additional persistent bytes and normal writes; bounded extra reads/authentication only in initial recovery. | Candidate 80 bytes, one additional atomic replacement/readback before first body, plus its filesystem allocation. | Earlier candidate 116 bytes plus any authority metadata and activation writes; overhead depends on an unapproved design. |
| Maintenance | One narrow predicate with diagnostic reason and permanent cut matrix; existing retry path. | Another initialization/compatibility boundary to debug and preserve. | More issuer, format, activation and migration interactions to support. |
| Validation | Exact tuple positives/negatives, two reboots, capacity and existing v1 reader matrix. | All A joins plus zero marker cuts, missing/corrupt marker and incompatible old readers. | All B plus issuer/domain changes, migration and activation/rollback cuts. |
| Durability risk | Accidentally broadening missing-head acceptance; prevent with default strict reader and complete conjunction below. | Creating the marker over populated/ambiguous state or leaving an incompatible rollback reader. | Cross-store activation, stale authority and partial deployment failures. |

Minimal B, if ever needed: retain 80-byte GSHD layout and current publication key;
propose ordinal 0 and zero frame digest, authenticate the first 48 bytes as today.
Offsets: magic 0–3; version 4; reserved 5–7; big-endian ordinal 8–15;
digest 16–47; HMAC 48–79. Permitting zero changes the supported reader contract
even without increasing record size. **B is rejected for this package:** A has
an authenticated zero-boundary authority already, so its extra persistent write
and compatibility obligation are unnecessary.

B's 80 bytes would be present during empty initialization; an ordinary 80-byte
head would replace them later. It therefore adds no steady-state head bytes
after the first publication, but still adds an initialization write and reader
contract. The proposed 116-byte head would add 36 bytes over today's head,
before any separately proposed manifest metadata.

The 116-byte v2/manifest/extra-key candidate is also rejected for this problem.
Do not implement C merely to anticipate owner transfer, factory erase, arbitrary
historical migration or a future incarnation platform.

## E. Minimum proposed implementation

### E1. Complete missing-head predicate

Accept a first body as pending **only when every condition holds**:

1. Existing security owner and durability owner are Ready in the expected
   Home/Hub key domain; native fresh-registry state, epoch 1, no migration or
   ambiguous installation. Existing NVS inventory/selector/checkpoint checks
   pass, including conflicting authority rejection. No NVS selected event/effect
   history contradicts a zero event boundary.
2. The event publication object is truly absent. A present empty, malformed,
   unauthenticated or wrong-version head is an error, never this exception.
3. The selected `application.head` exists, authenticates as GSR1 type 3 with
   boundary exactly 0, and its plaintext passes the complete current checkpoint
   decoder and bounds. It is not a guessed default or fallback.
4. The selected identity head is ordinary GSR1 type 2 at ordinal exactly 1;
   its authenticated tail digest selects exactly one valid identity row at
   ordinal 1. The ordinary identity log ends at that selected row; no extra
   identity tail, compacted generation or other selected identities is allowed
   in this exception.
5. Exactly one complete body exists, ordinary GSOX v1 ordinal 1. Decode and
   authenticate it, verify CRC and canonical key/payload encoding, then compare
   the exact key and full payload HMAC against the selected identity. A second
   complete body, unexplained gap or extra transaction tail is inconsistent.
6. The identity carries authenticated original enrollment owner evidence.
   Resolve the decoded physical/logical Node against the existing authenticated
   registry and compare slot, enrollment generation and binding digest. Reject
   foreign, revoked or replaced ownership; do not rewrite it to current ownership.
7. No retired body boundary, completion record/publication, body compaction or
   identity compaction authority implies prior event history. A zero-event replay
   witness is allowed only if its epoch/reference/generation/digest is compatible
   with the existing selected NVS report and fallback protections. No authenticated
   retirement fence may cover the candidate key. Preserve ordinary reconciliation
   when NVS is legitimately ahead; never bypass a witness mismatch.
8. All remaining scanner, file-size, capacity/configuration and crypto checks
   pass. I/O error, missing readback and an incomplete proof close admission.

The coordinator must validate the selected tuple under the same serialized
writer. Retain the full original frame in place; never regenerate its identity,
minute or payload from boot time. Store its verified frame digest in the existing
`staged_frame_digest_`; retain its index entry at ordinal 1. Set public event
high-water to 0 and next physical ordinal to 2, exactly like an existing staged
next body behind a valid nonzero head. It is invisible to journal replay,
completion transmission and committed-duplicate ACK lookup.

### E2. Initial empty-state creation and repair

Reuse the existing startup order: authenticated NVS owner, genuinely empty
outbox, zero identity head, zero application checkpoint, exact readback, then
open admission. Retain existing NVS bootstrap recovery; do not infer a fresh
installation from an empty partition when its owner reports Existing/Ambiguous.

The interrupted-write subcase needing attention is a valid selected zero
identity head with an absent application checkpoint: current `recover(0)` rejects
it because a head exists. Permit completing the normal initial checkpoint only
after the native owner and all selected stores prove empty: no identities,
bodies, event/completion head, prior event/effect/reducer history, compaction or
contradicting report/witness. A type-2 zero identity head must have the exact
existing zero digest. Reuse the ordinary configured initial checkpoint encoder,
replacement and readback; do not recreate owner keys or epochs.

An incomplete `.new` file is never selected authority. A valid selected checkpoint
0 already present needs no rewrite. A present corrupt application checkpoint,
identity head or NVS authority fails closed. A missing checkpoint with identity
1 or any complete body also fails closed: the initial checkpoint cannot be
proved. Owner bootstrap failure before any authentic NVS root remains an owner
initialization failure; do not invent recovery authority for it. This design
does not solve arbitrary interruption of initial key/claim provisioning.

### E3. Interfaces and affected modules

- Extend `DurableEventOutbox` recovery with an optional bounded **validator of
  the exact initial candidate**, invoked only for the specific absent-head,
  one-body case. The default outbox-only reader remains strict. Do not add an
  `ignore_integrity_failure` or caller-supplied `allow_missing_head` boolean.
- Add read-only selected-initial-state inspection to `RuntimeStateStore`, reusing
  its codecs and payload HMAC. Separate proof inspection from truncation/cleanup;
  no authoritative write or healthy publication before the complete join.
  Add the narrowly proven empty-checkpoint completion path to ordinary recovery.
- Reuse `HubCheckpointCodec` decoding/bounds for the checkpoint-0 proof. Factor
  validation from restore if necessary; use the actual runtime's bounded storage,
  rather than constructing another full runtime merely to inspect a checkpoint.
- Coordinate the proof in the existing Hub runtime/target owner. Supply existing
  enrollment resolver and selected NVS/report context. Construct dependencies
  before opening admission; check the complete outbox scan including completion
  and lifecycle metadata before returning healthy. Re-read selected authority
  if any recovery operation could have changed it.
- Reuse `HubRuntime::run_state_once` and `OutboxJournalBackend` for exact retry.
  Do not add a second commit implementation. When necessary, make the pending
  admission guard explicit so a different key rejects without selecting another
  identity or faulting away the valid pending transaction.

Proposed scanner hook contract: a function taking the existing owner context,
candidate ordinal, canonical key and exact versioned payload, returning true
only after read-only validation of E1. It is optional and null for every existing
standalone caller. Invoke it for ordinal 1 only, never for a present invalid head
or general IntegrityFailure; do not return healthy until the rest of the scan
passes. The owner context contains references to existing dependencies, not new
persistent authority. Initial-state inspection returns selected checkpoint/head
kind/count and exact row evidence through bounded existing buffers; it performs
no repair itself. These are proposed source interfaces, not wire/schema changes.

No persistent interfaces change: GSR1, GSOX v1, GSHD v1, lifecycle/completion
formats, NVS keys, storage keys, partitions, Node wire and backend wire remain
unchanged. Publication still uses nonzero ordinal 1. No genesis activation,
prepared abort or destructive reclamation is included.

## F. Essential security assessment

The demonstrated risks are corrupt/foreign body admission, payload substitution,
incorrectly treating ACKed history as empty, stale owner/epoch/fence selection and
premature ACK. Existing AEAD/HMAC, exact selected identity, checkpoint barrier,
authenticated registry and root/witness checks address them when joined correctly.

The proposal preserves all of these checks. It adds no unauthenticated success
path, extra event exchange or independent authority. Persisting a first body
means the original authenticated ingress already selected its identity; boot must
still verify that selected owner, not merely trust ciphertext structure. Exact
retry requires an authenticated current Node session and normal enrollment/fence
validation. A conflicting payload remains Rejected and leaves original bytes intact.

GS-D032 permanent Hub identity and authorized Home ownership are unchanged.
GS-109's trusted Add Device workflow remains incomplete independently; no new
claim/recommission API is needed to read this same local authorized domain.
GS-132 future erase/replacement/incarnation behavior is not implemented here.
No HSM, secure element, eFuse change, certificate platform, new encryption layer,
universal credential or cloud dependency is justified by this first-event fix.

Signed firmware and automatic application rollback remain mandatory under
GS-D029/030. Their current S3 integration gap below is not waived by using v1.

## G. Installation, S3 OTA and rollback compatibility

### Source findings

- S3 `idf/CMakeLists.txt` reuses `target/esp32/idf/main`. Its candidate partition
  CSV contains two 4-MiB app slots and `otadata`, 4-MiB LittleFS and 256-KiB state.
  No partition change is proposed. Defaults still select the separate development
  map; correct outbox profile selection remains required.
- S3 defaults and retained production `s3-sdkconfig` set
  `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`. The retained config does **not**
  enable `CONFIG_SECURE_SIGNED_APPS_NO_SECURE_BOOT` or hardware Secure Boot.
  This is compile evidence, not a commercial signed-image qualification.
- Shared `app_main.cpp` starts the runtime adapter and `fota_sender`. The sender
  updates enrolled **C3 Nodes**. There are no `esp_ota_*` calls, Hub self-update
  receiver or pending-image health confirmation in the inspected Hub production
  source. Starting a task is not proof that its storage recovery succeeded.
- ESP-IDF's pending OTA image must confirm successful diagnostics with
  `esp_ota_mark_app_valid_cancel_rollback`; otherwise a reset can cause rollback.
  See [ESP-IDF 6.0.3 S3 OTA documentation](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32s3/api-reference/system/ota.html#app-rollback).
  The config flag alone does not complete that product integration.
- GS-118/C3 signed-FOTA host/build/physical evidence cannot qualify S3 self-OTA
  or S3 failed-boot rollback. Existing S3 saved images are engineering artifacts;
  this review found no qualified commercial S3 A/B image pair.

### Reader matrix (source-derived expectation; proposed tests NOT_EXECUTED)

Define OLD as baseline 371a560 v1 reader; FIX as the proposed corrected v1 reader.
These are behavior labels, not a new persistent schema or approved release list.

| Persistent state | OLD behavior | FIX behavior |
|---|---|---|
| Existing valid populated v1, valid head | Ordinary exact recovery | Same ordinary recovery; no migration/rewrite |
| Authorized empty v1, valid checkpoint 0 | Ordinary empty recovery | Same; no additional initial record |
| Native zero identity head, initial checkpoint write interrupted | Fail closed if checkpoint absent | Complete checkpoint only with proven empty tuple |
| Original first body + selected identity 1 + checkpoint 0 + no head | Existing IntegrityFailure | Verified pending 1, public boundary 0; exact retry completes |
| First body/head 1, checkpoint 0 | Existing replay then checkpoint 1 | Same; no artificial ACK on boot |
| Head/checkpoint 1, lost ACK | Exact duplicate ACK after recovery | Same; one logical reducer effect |
| Missing head with checkpoint >=1, multiple bodies or corrupt/foreign evidence | Fail closed | Fail closed; no attempt to synthesize a head |
| FIX has completed ordinary head/checkpoint 1 | Reads normal v1 | Reads normal v1 |

**No new incompatible state is written by A.** Its recovery semantics improve
existing interrupted states that OLD already creates and refuses. An upgrade
interrupted before slot selection leaves the previous app and same v1 stores.
A FIX boot cut before exact retry leaves that same old pending state; OLD will
still fail closed. A cut after head 1 is durable leaves an existing recoverable
head/tail combination; a cut after checkpoint 1 leaves ordinary duplicate-safe v1.

Do not claim that format compatibility repairs an OLD reader's existing
availability bug. For reliable R1 rollback at every first-event cut, recommend
that **both supported S3 application images contain this bounded recovery fix**
and retain current v1 codecs/keys. Establish the fixed reader as the commercial
R1 baseline, or backport the fix to any previous image that must remain supported.
This is an image support/qualification choice requiring owner approval; it is
not a v2 reader-first writer activation or migration platform.

If an OLD engineering image is retained for rollback, record its fail-closed
pending-first-event limitation explicitly. GS-D029 permits fail-closed handling
of unsupported/incompatible state, but that does not establish GS-145 reliable
fresh-install acceptance. Do not silently downgrade the latter requirement.

Subsequent S3 OTA work must implement signed candidate verification, inactive
slot finalization and owner-reported boot health using the existing ESP-IDF
mechanism. Health may accept a fully verified pending initial transaction;
it must not wait for cloud or a Node retry just to confirm a healthy boot.
Unknown/corrupt authority must not report storage healthy. Image hashes, signed
publisher identity, actual profile and rollback state must be qualified separately.
No OTA implementation or physical execution occurs in this package.

## H. Recovery flow and cases A–I

Use existing conceptual states: CLOSED during inspection; READY with zero or
published boundary; READY with one exact PENDING transaction; FAIL_CLOSED on
uncertainty. PENDING is existing prepared ownership, not a new on-disk state.
READY/PENDING permits authenticated rejoin and the original event only;
it does not expose the pending body as committed history.

```text
recover existing security owner, native NVS roots and inventory
if authority is unknown/corrupt/conflicting: FAIL_CLOSED
inspect selected identity/application and ordinary outbox evidence
if all selected stores prove empty:
    complete ordinary checkpoint 0 if genuinely absent; verify readback
elif event head is valid:
    ordinary outbox + identity + fence recovery and checkpoint replay
elif head is absent AND the complete E1 conjunction holds:
    retain original body/index/digest as pending ordinal 1
    published high-water = 0; restore checkpoint 0; reconcile compatible fence
else:
    FAIL_CLOSED
after the complete scan/reconciliation: READY or READY/PENDING

on authenticated exact retry of pending key:
    verify original full payload and owner; reuse original minute
    reserve remaining head/checkpoint workspace
    if body exists: sync/read back the original body before publication
    else: ordinary original-payload append + sync/readback
    publish ordinary nonzero v1 head; verify exact durable readback
    confirm identity; apply once; persist checkpoint 1; verify readback
    only now return Durable for the requested EventKey
on another key or conflicting same-key contents: reject without mutation
```

The explicit resync/readback before publishing a recovered staged body covers an
earlier body write/sync that persisted despite reporting failure. Implement it in
the existing staged publication path, preserving its frame bytes and digest; it
is one extra barrier on that recovery path, never re-encryption. A failed barrier
or readback requires restart and no Durable ACK.

| Case | Authoritative persistent state | Recovery / admission / ACK | Original event and next stable state |
|---|---|---|---|
| A. Genuinely fresh authorized empty storage | Existing trusted owner/native NVS; no event history; selected zero identity/checkpoint or proven interrupted empty initialization | Finish normal empty checkpoint and readback. Admit only after all initialization checks. No event ACK on boot. | No pending event; READY boundary 0. No reset/format to establish emptiness. |
| B. First body successfully published | Valid head 1 and exact identity 1; checkpoint 0 or 1 | If checkpoint 0, replay the published body once and save checkpoint 1; restore checkpoint 1 otherwise. Admission after recovery. ACK only on a valid later request. | Event published and backend pending unless existing completion proves otherwise; READY 1. Historical notifications remain suppressed as in current replay. |
| C. Body persisted, publication interrupted | E1 tuple: selected checkpoint 0, identity 1, exact body 1, absent head | Restore pending, not committed. Allow rejoin and exact retry only; other event admissions reject. No boot ACK. Retry follows all normal durable barriers. | Original bytes/minute pending; stable PENDING 1 until ordinary commit, then READY 1. |
| D. Identity prepared, body absent/prefix only | Valid checkpoint 0 and selected identity 1; no complete body or head | Existing prepared recovery, authenticated exact retry; ordinary torn-tail accounting retained. No fabricated payload from its HMAC. Reject a different key without creating a new identity. | Original key/hash/minute pending; Node retained payload supplies exact original on retry; READY 1 only after real commit. |
| E. Initial checkpoint/authority corrupt | Present invalid checkpoint/head, missing checkpoint with selected identity 1/body, corrupt or conflicting owner/NVS/witness | FAIL_CLOSED; no new event admission or Durable ACK. Preserve evidence. Missing initial checkpoint is repairable only under E2's empty conjunction. | Pending/accepted evidence remains protected; diagnostic/operator scope required for uncertainty. |
| F. Same EventKey retried after reboot | Pending tuple or ordinary committed identity/checkpoint | Pending: resume original transaction. Committed: authenticated exact duplicate ACK without applying again. Conflicting payload/owner rejects in either case. | One publication, original payload/context and one logical effect. |
| G. Different EventKey during incomplete recovery | Original prepared/pending ordinal remains selected | Rejected, no identity append/head overwrite or ACK for the new key; maintain ability to service original retry. No new priority/overflow policy. | Same pending event; no second ordinal occupant. After its commit, fresh admission proceeds normally. |
| H. Reboot again before recovery/retry finishes | Same selected tuple, or normal v1 head/checkpoint reached by partial completion | Repeat read-only classification; unselected temp files never count. After a head is genuinely selected, ordinary recovery applies. ACK withheld until actual durable conditions hold. | Stable pending survives indefinitely many read-only boots; one selected prepared owner, no bootstrap write per boot. |
| I. Previous image restored | Same unchanged v1 bytes | Corrected supported reader resumes pending. OLD handles normal head/checkpoint states but fails closed on the known pending-first or interrupted-empty case. No erase or invented successful boot. | Exact data retained; availability requires the corrected supported pair specified in G. |

Application checkpoint authority determines local effect replay. Backend delivery
continues to use the original EventKey and existing idempotence contract. Exactly
one logical caregiver effect must be tested through the existing board/serializer
and local API adapter; the unfinished production CloudSync/trust worker and product
P0 PARTIAL remain independent. This proposal does not promise exactly-once external
notification delivery or activate an unfinished backend receipt contract.

## I. Proposed validation and acceptance matrix

**All new positive recovery cases below are PROPOSED_NOT_EXECUTED.** Existing
P0/P1/P2 execution is in its dated handoff; it was not repeated. Keep its default
standalone missing-head failures and all populated/corrupt missing-authority
negatives. Add positives through the production coordinator with authenticated
owner fixtures; the original ownerless outbox fixture is not such a proof.

Reuse `code/tests/cpp/hub_storage_correctness_validation.cpp`,
`hub_runtime_checkpoint_validation.cpp`, `hub_segmented_outbox_runtime_validation.cpp`,
`hub_durable_provider_validation.cpp` and `board_stack_e2e_validation.cpp`, plus
existing authenticated pair/file-flash support. Use actual production codecs,
runtime, owner and scanner. Scripted adapters inject faults; they do not replace
the state machine with a model. Permanently extend current registered
`storage-correctness`/sanitizer/component stages and GS-130 traceability in the
implementation package. Add OTA reader scenarios to existing fixtures/stages,
not a duplicate framework. Registration of a proposal is never recovery PASS.

| Required case | Existing acceptance IDs to extend | Oracle and level |
|---|---|---|
| Empty initialization and interrupted zero identity/application writes | GS148-ARCH-001, 003, 006 | Owner-backed fixture: before write, prefix temp, barrier, rename and readback cuts. Authenticated empty tuple repairs; selected corrupt checkpoint fails; no events ACKed. |
| NVS initial root selection interrupted/corrupt/missing | 001, 012–016, 048 | Reuse provider/root fixtures. Existing valid selected genesis recovery only; no-root or uncertain owner remains fail closed, never auto-claim. |
| First identity persist failure | 002, 003 | Old-or-new selected row; unselected prefixes never identity authority; at most one prepared owner; exact retry. |
| First body persist failure/prefix and sync interruption | 004, 005 | No ACK or effect before ordinary publication/checkpoint; charge partial tail; complete selected body can qualify only with full proof. |
| First head persist failure; write succeeded but API reports failure | 005, 006 | Absent head => verified pending; actually valid head => ordinary replay. Presence/authentication dominates API return guesses. |
| Crash before/after every readback/barrier | 003–006 | Halt I/O immediately at cut, reconstruct production objects, boot twice, inspect exact selected key/boundaries, then retry/fresh admission. |
| Lost first ACK; two consecutive boots; same key | 007, 009 | Node retains original; one published identity/body/logical effect; committed duplicate gets authenticated ACK only after restore. |
| Same key conflicting payload/time/owner | 008, 040, 048 | Reject; original bytes, local minute, reducer and ownership unchanged. |
| Different key before original retry | 002, 003, 010 | Reject without selecting identity 2, poisoning original retry, publishing head or admitting another occupant. |
| Corrupt auth metadata/unknown version/mismatched key or epoch | 016, 040, 048 | Fail closed; exception requires native epoch 1 and original enrollment; no key recreation or reset. |
| Existing populated state missing authority | 005, 006, 048 | Checkpoint >=1, two bodies, completion/compaction history, retired boundary or conflicting fence => fail closed; no synthesis. |
| Valid zero-event NVS report/witness and fallback roots | 012–016 | Report-before-first-event positive; mismatched/stale/conflicting witness negative; fallback report banks stay pinned; RPF diagnostics unchanged. |
| Valid recovery then new event | 001, 006, 007 | Commit original once, checkpoint 1, admit new key at 2, two boots; exact pending/retired sets. |
| Full and low capacity | 010, existing admission/workspace cases | Refusal before irreversible work, one owned pending event after uncertain I/O, safe refusal of head/checkpoint completion without space; no deletion or numerical new guarantee. |
| OLD/FIX same v1 store reads and simulated application rollback cuts | GS148-ARCH-049 | Cross-reader fixture uses the actual baseline reader and corrected reader against one retained byte store. Test every state in G. Expected OLD limitation is explicit, not silently counted as availability PASS. |
| Trigger-to-outcome caregiver projection | 007, 051 | Existing production C3/S3 board-stack/serializer to real local API fixture: original key, one logical projection, fresh second event. Product COMPLETE cannot be claimed while P0 remains PARTIAL. |
| Registration/failure propagation and target profiles | 053–055 | Nonzero counts, negative exit adjudication, permanent source/requirement/stage mapping, S3 and GS-114 build profiles. |
| Real S3 first-event cuts/duplicate recovery | 056 and existing PHY-GS148/PHY-GS145 | Later separately authorized expendable fixture; current image/profile/partition provenance, actual write barriers and exact ACK/outcome. NOT_RUN. |
| Signed S3 A/B boot success, failed boot and pending-first rollback | 063 | Later S3 OTA implementation plus host/inactive-slot tests and authorized matched physical image pair. C3 evidence insufficient. NOT_RUN. |
| Physical controlled corruption | 066 | Existing catalogue, expendable storage and explicit plan; fail closed with originals preserved. NOT_RUN. |

For each cut assert selected authority, original exact key/payload/minute, no
premature Durable ACK, no duplicate logical effect, pending ordinal exclusion
from replay/cloud delivery, no identity 2 before resolution, no root/fence
regression and bounded indexes/quarantine. For resync failures include missing
and corrupt readback; do not publish from a digest that was merely remembered.

Subsequent implementation validation: affected Hub/Node/contract regressions,
board E2E, new fault cases, ASan/UBSan, framework/feature mapping, ESP-IDF 6.0.3
S3 production and affected GS-114 fixture/profile builds. Backend/PWA tests only
for affected contracts or the focused existing projection test. No automatic
full release gate. Historical migration FAIL and product P0 PARTIAL must remain
visible. Physical and actual signed S3 rollback require their own acceptance.

## J. Engineering and resource impact

These are structural estimates, not measurements or a firmware-size budget.

| Resource | Increment under A |
|---|---|
| Persistent bytes | **0** additional steady-state bytes, no new NVS keys/records. Ordinary v1 head remains 80 bytes; existing GSR envelope overhead remains 41 bytes. |
| Typical admission writes | **0** additional writes compared with current successful admission. No per-event genesis or new encryption pass. |
| Recovery writes | Complete-body pending classification: **0** authoritative writes. Exact retry: existing head replacement + application checkpoint replacement; add a body resync/readback before head publication. Proven interrupted empty initialization: one existing checkpoint replacement, plus zero identity head only if genuinely absent. |
| Worst-case retries | One attempt per actual retry; errors stop success. Read-only reboots add no pending publication writes. Arbitrarily many failing physical writes have no finite lifetime/wear bound; do not invent one. Existing partial-tail/capacity limits still apply. |
| RAM/PSRAM | Small validator context/digests; reuse one identity row (bounded at 516 encoded bytes), one body buffer (configured payload <=1024 plus key <=256 and frame overhead), existing 32-byte staged digest/index. Retaining the pending entry uses existing index allocation granularity (outbox blocks of 256 entries), not an invented one-entry allocation. Decode checkpoint within existing 64-KiB limit; reuse current buffers and avoid a second runtime/recovery copy. Exact allocator peak to measure after implementation. |
| CPU/restart latency | One bounded first-candidate payload authentication/owner lookup and checkpoint decode; ordinary scan complexity unchanged. No cloud wait or additional runtime Node exchange. No measured timing claim. |
| Flash wear/firmware | No new normal-path persistent write. Several small validation/recovery methods and regression cases; link-size delta unknown until target build, not forecast as a measured value. |
| Engineering scope | Existing outbox/state store/checkpoint/runtime/target owner and current tests/docs/registry; no new storage subsystem, issuer or generalized migration. |

The delivered S3 compile artifact was 1,875,216 bytes, with 2,319,088 bytes free
in its candidate 4-MiB OTA slot; static DIRAM accounting was 107,761 bytes used.
Those are prior P0/P1/P2 build results, not a build of this design. Runtime heap,
PSRAM peaks, ESP-NOW responsiveness, ACK latency, actual flash wear and power-cut
atomicity remain PHYSICAL_QUALIFICATION_PENDING. `/tmp` is full; future builds
must use existing supported ignored temp/build locations on the main filesystem
(about 911 GiB available at review), preserving all generated assets/evidence.

## K. Genuine approval gates

1. **Authorize the bounded A implementation**, including the exact joined
   pending predicate and proven-empty checkpoint completion. Recommendation:
   approve A; retain all formats/keys and ordinary ACK/fence behavior. Risk is
   an overbroad exception, addressed by the explicit negative matrix. This
   report itself is not implementation permission.
2. **Approve the supported S3 image baseline/pair for reliable first-event
   rollback.** Recommendation: corrected v1 recovery in both supported R1
   images; backport to any previous image designated supported. OLD engineering
   images keep their documented fail-closed limitation. Product owner approval
   is required before excluding an otherwise supported previous image or claiming
   a commercial image matrix. This choice gates deployment/rollback acceptance,
   not implementation of the byte-compatible local correction. Current S3
   self-OTA/signed-image integration and physical proof remain separate work,
   not solved by this approval.

No new persistent-format, key hierarchy, retention, overflow, commercial
incarnation issuer, owner-transfer or CloudSync decision is needed to implement
this fixed local native-epoch-1 recovery slice. Existing locked ownership and
rollback requirements stay in force. Broader supported epochs/transfer/migration
must not be inferred from this limited predicate. Unrelated D-A–D-M decisions
remain OPEN; physical fixture approval is required only for a later physical task.

## L. Ordered bounded subsequent implementation package

1. Recheck canonical branch/HEAD/remote, preflight and writers; record separate
   owner authorization of A. Carry the supported-image recommendation into later
   qualification; unresolved commercial image designation does not require a
   format decision or block this local byte-compatible software package.
2. Add production-backed **authenticated** failing first-body/no-head recovery
   positives and interrupted-empty checkpoint tests. Preserve standalone and
   populated missing-head negatives. Capture baseline failures without repeating
   the entire delivered P0/P1/P2 campaign merely to rediscover the blocker.
3. Implement read-only selected-initial-state proof and the narrowly gated
   scanner path; retain staged frame/digest at public boundary 0. Complete the
   proven-empty checkpoint using the existing encoder/write/readback path.
4. Wire existing NVS/enrollment/fence context in the single target owner; restore
   state before any ACK-capable ingress. Make different-key refusal non-mutating
   and recoverable for the original pending key. Resync/read back original staged
   body before the existing retry publication path.
5. Run the fault/negative/two-boot/capacity and actual baseline/corrected reader
   matrix, focused board-to-API projection and appropriate sanitizer/component
   regressions; keep migration/P0 failures visible.
6. Register cases/IDs/source/gate evidence permanently in current GS-116/130
   registries, then run applicable source-traceability/framework checks and
   production S3 plus affected GS-114 builds using adequate temp space.
7. Document exact implementation/validation and limitations; coherent commits,
   normal push and actual remote equality; GS-148 evidence and GS-145 qualification
   handoff. Stop. No production GC, future epoch/owner transfer, signed S3 OTA
   implementation or physical qualification automatically follows this package.

## M. Jira and document mapping

| Owner/input | Review disposition |
|---|---|
| GS-148, In Progress | Owner of local first-event correction; 10678 delivered P0/P1/P2, 10679 next gate, 10681 simplicity guidance. Publish this proposal, no status transition. |
| GS-145, To Do | Current-format first-event/reboot/dedupe acceptance; 10680/10682. New positives and later physical evidence required; no Done or host-only qualification. |
| GS-132, OnHold | V1 reader compatibility input and future incarnation/migration ownership. No new identity platform required for this fixed native domain; supported image matrix remains explicit. |
| GS-109, To Do | Reuse authenticated local registry/ownership; trusted Add Device/production issuance remains independently incomplete. No new commissioning implementation. |
| GS-139, existing qualification scope | Actual S3 signed OTA/rollback and physical power cuts are pending. No ticket transition or new generic framework. |
| GS-116 / GS-130 | Existing stages/traceability, board/physical separation; proposed cases require later permanent registration and actual execution. |
| GS-152 / GS-114 / GS-144 | Restructuring remains Done; diagnostic/profile evidence and physical NO-GO preserved; battery work untouched. |

Inputs read: live GS-148/145 latest issues/comments; original GS-148 10513–10523
architecture and open decisions; GS-132/109 and GS-116/130 policies; canonical
AGENTS/context/release/decisions/work-state/index; current storage/OTA documents;
[delivered P0/P1/P2 handoff](../exec-plans/evidence/R1_GS148_P0_P1_P2_20261012.md)
and current production sources/registered fixtures. No original architecture
review or comprehensive implementation test campaign was restarted.

## N. Verdict and handoff

**DESIGN_READY_FOR_APPROVAL.** A supplies an implementation-ready minimal
authority proof for the demonstrated current-format first event, writes only
existing v1 records, and preserves prior missing-authority security tests.
It deliberately resumes a transaction rather than inventing a completed commit.
Approve the bounded implementation and corrected supported-image baseline
separately before production work.

Implementation/test status: NOT_IMPLEMENTED / proposed cases NOT_EXECUTED.
Documentation checks passed: all 14 A–N sections, eight Markdown-only files,
10 new relative links, `git diff --check`, unchanged production/registry/context
files, and context preflight PASS. No software regression/build was repeated.
Previous bounded package remains
PARTIAL; historical migration FAIL and product P0 PARTIAL unchanged. S3 self-OTA,
signed A/B rollback and physical current-image durability are unqualified.
Physical NOT_RUN/BLOCKED; release NOT_RUN. No production source, formats, keys,
partitions, GC, hardware or issue workflow changed by this design delivery.

Canonical tracked Markdown may be committed only after a fresh writer/status
check. At review, the other active CLI session's observed edits target the
separate dashboard worktree; canonical tracked mtimes/status remained unchanged.
Its work is not modified. Preserve all canonical untracked components, generated
assets and GS-114 evidence. Final documentation commit/actual GitHub equality
and dated Jira comment IDs are recorded in the delivery comments, avoiding a
self-referential commit hash here. Next action: user approval and separate
authorization of L; stop after this design.
