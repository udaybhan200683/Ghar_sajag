# Durable backend completion contract

## Production audit and identity

Production currently has exactly one backend application commit effect per
retained DomainEvent. Its identity is the installation-scoped journal key plus
exact EventKey (physical device, logical source, origin session, sequence), in the
existing GharSajag/HubCompletion/v1 domain. This scope does not add multi-effect
execution. A future second operation needs a separate effect-kind contract.

HubJournal::commit assigns an append-only slot 0..127. DurableJournalSlotStore
persists that slot in Transition::decision, then in the first four bytes of the
archive Effect::id. rows() reconstructs it after reboot. It is not a process-local
vector position: archive slots are immutable and are never reclaimed or reused.
EventKey::str and receipt encoding remain unchanged.

append_event persists causal event bytes in a transition; flush checkpoints event
archives inside PendingEffectChunk. Those archive effects are retained events,
not separately executable backend payloads. HubJournal::pending_cloud selects
records without recovered completion receipts. CloudSync::handle_backend_reply
accepts only an authenticated matching backend COMMITTED response before calling
HubJournal::acknowledge_cloud. Its receipt readback is required before cloud_acked
is updated. A transport acknowledgement alone does not complete the effect.

## Independent completion representation

Use existing immutable c000..c127 records in gs_journal/events. Each is the
existing 32-byte receipt: HKDF-derived completion key, HMAC over GSC1, durable
slot (u64), and exact EventKey::str. The installation journal key scopes the
receipt to the authenticated relationship. No payload, new schema, namespace,
key mapping, enrollment, epoch, or report format is introduced.

write_completion publishes the independent receipt and verifies exact durable
readback. Duplicate identical receipts cause no write; conflicts fail closed.
read_completion authenticates the receipt against the exact recovered slot/key
before returning it. HubJournal reconstructs cloud_acked from those receipts;
CloudSync never emits a completed event again after a valid completion receipt
has durably committed. Before receipt commit, backend retry remains possible;
the backend's existing exact-event idempotency contract handles the external
commit/local-receipt interruption window. No local protocol can atomically commit
an external backend operation and flash evidence.

The receipt bytes do not depend on retaining a separate effect payload. Exact
identity is recovered from retained event history; event archive bytes remain
unchanged by new completion commits. Epoch transitions already prohibit
transferring nonempty retained history through the empty-history epoch helper.
No slot reuse or completion-evidence deletion is authorized by this contract.

CompletionBitmap is unsuitable here: GBM1 contains 16 committed bits and only
bm0/bm1 banks, with no production stable 128-event mapping. Padding must remain
zero in schema 1. It is not repurposed. PendingEffectChunk, DedupeEvidenceChunk,
checkpoint selectors, HMAC domains and their ownership rules remain unchanged.
Report checkpoint selection preserves the existing covered-event boundary rather
than covering the unarchived tail. DurableStore::checkpoint permits metadata-only
checkpoints at that unchanged boundary and adds exact dedupe entries only for
covered transitions. Recovery retains uncovered transitions. Full-tail archive
checkpoint behavior is unchanged. This keeps retained event identities available
to authenticate independent receipts without consuming a chunk on every report.
No archive record is deleted; normal bounded four-event batching remains intact.

## Compatibility and recovery ordering

Legacy archive kind=1 remains authenticated completion evidence. On journal
attachment after owner Ready, read_completion publishes and verifies a matching
independent receipt if absent. The legacy marker and archive are preserved.
Failure to publish stops attachment; restart retries from the retained marker.
If a c record exists it must validate exactly, even if kind=1 also exists; a
conflict cannot be masked by the legacy marker. kind=0 with no receipt remains
incomplete. Publication is idempotent and can resume across partially migrated
sets of records.

Older e/c source migration remains unchanged. During MigrationRequired the old
archive-marker completion path is used. Independent publication waits until
source cleanup has completed, because legacy cleanup deletes c keys. Durable
kind=1 preserves completion throughout that migration. With durable checkpoints
and no e source records, c records are current receipts rather than evidence
that e/c migration is required. Completion authentication occurs at journal
attachment before the runtime opens event admission; owner recovery supplies
the authoritative epoch and durable archive. Corrupt/partial/conflicting receipts
stop journal attachment, preserving both the receipt and history for diagnosis.

## Report and recovery separation

Node report generation is owned by NodeRuntime recovery-v3: durable pending
EventKeys, durable_admission_highwater and report_generation. Authenticated event
ACK retirement advances that state; periodic NodeHealth is excluded. The codec
and fragmenter transport it, and RetirementSnapshotRepository binds and validates
it. The Hub target selects and verifies a checkpoint-owned report bank before
sending a report ACK. Node validates epoch/generation/HMAC. These proofs describe
Node pending state, not backend application completion; c receipts do not change
report state or authorize dedupe/event reclamation. DurableStore::checkpoint keeps
exact DedupeEvidenceChunk ownership and report references; recover validates both.
HubDurabilityOwner recovers epoch/selectors and checks chunk inventory ownership.

## Bounds and excluded behavior

128 immutable receipts add at most 4096 raw bytes and 384 modeled NVS entries
(three per 32-byte blob). Conservatively adding all receipts to the previous
migration peak, even where old/new c keys overlap, gives 87314 bytes of 131072:
43758 bytes free (33.38%). NVS model: 3605 of 4032 entries, 427 free (10.59%).
Normal modeled peak becomes 81218 bytes and 2936 entries. No partition resize or
storage-limit increase is made. Physical allocator qualification remains pending.

No event history, effect payload, legacy marker, dedupe proof, or retirement
snapshot is deleted. No completed-effect retirement occurs. All 128 retained
events can be complete, but admission of event 129 still fails as Full. Node's
32-key pending contract and 542-byte reports remain unchanged.

Focused host coverage uses actual CloudSync, HubJournal, DurableJournalSlotStore,
HubDurabilityOwner and freshly constructed providers: pending/completed selection,
duplicate commit, exact identity binding, failure before write, partial write,
persistence with failed API, reboot, legacy marker publication/retry, archive
byte preservation, and the 128-event boundary. Existing migration tests retain
legacy source interruption coverage. Target builds prove compilation only;
physical NVS atomicity, power-cut and ESP-NOW validation remain HIL work.
