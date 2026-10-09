# S3 storage Phase 2 lifecycle progress — 2026-10-09

Starting revision: `479c6d0082890bc19b5c88e570fb0b176f5ff474`
Branch: `feature/r1-s3-hub-bringup`
Context: `2026-10-09.001` (unchanged)

This is an implementation checkpoint, not Phase 2 or storage closure. It connects
the existing segmented outbox, reducer checkpoint, runtime identity log,
authenticated backend completion path, and authenticated Node retirement report
to one guarded body-retirement transition.

## Lifecycle publication and recovery

The outbox now publishes a versioned HMAC-authenticated lifecycle root in
LittleFS. It binds the retired ordinal, reducer checkpoint boundary, selected
authenticated Node-report generation/digest, and the event-publication
ordinal/digest. The root is the authority to delete event segments. The adapter
first persists and verifies the Node retirement snapshot in its existing NVS
durability owner; only then can it present that snapshot reference to the outbox.
No atomic multi-partition operation is assumed. A reset between the NVS report
checkpoint and LittleFS root publication retains bodies. A reset after the root
is committed resumes the pending reclaim idempotently. Corrupt or contradictory
roots fail recovery rather than restoring a stale body range.

Reclamation currently operates on a complete published body prefix: every body
must have an exact authenticated backend COMMITTED receipt, the reducer
checkpoint must cover the high-water, the selected Node report must prove each
exact key retired under its enrollment slot/generation/session/high-water and
pending-key set, and the post-sync retention gate must be true. Completion
publication is reset and its log truncated only after the lifecycle root is
published; then segment files are removed and a final root is published. Recovery
can finish after a lifecycle-root write uncertainty, completion-log truncation,
or segment-removal interruption without deleting a pending body.

The S3 production configuration keeps body deletion disabled. No post-sync
retention duration or durable completion-time policy is approved or implemented,
and physical LittleFS power-cut/recovery qualification has not been run. The
Kconfig switch defaults off; the runtime authorization also deliberately leaves
the retention predicate false. Host fixtures may satisfy it only to test the
transaction.

## Results

- Three 100-event HubRuntime cycles pass through authenticated ingress, durable
  ACK, authenticated deterministic backend receipts, checkpoint and Node-retired
  proof. Segment removal is interrupted in cycle one; restart completes that
  reclaim, and later cycles reclaim and refill. A duplicate after retirement is
  acknowledged from the exact identity log without repeating reducer effects.
- A 3,278-event mixed semantic stream passes through the same HubRuntime path,
  backend completion, retirement authorization, segment reclaim and one-event
  refill. Host in-memory adapter measurements: 551,348 event bytes before
  reclaim, 307,025 completion bytes before reclaim, 366,141 identity-log bytes;
  body capacity returns to zero, then the refill charges 166 bytes. These are
  logical/host-adapter values, not LittleFS physical occupancy or a household
  workload guarantee.
- The existing 6,556-record outbox admission/recovery stress remains PASS
  (1,110,125 encoded frame bytes). Full 6,556-event retirement is not supported
  by this implementation: the bounded completion stream rejects after 5,472
  receipts / 524,205 bytes, before all records can be completed. Completion
  metadata compaction is presently whole-history only.
- Exact identity evidence remains conservative and is not compacted. The
  identity rows do not yet persist enrollment slot/generation, and the runtime
  admission path has no durable compacted-report stale-key barrier to replace
  those exact rows after deletion. Identity compaction must wait for that
  ownership-scoped stale-key mechanism; no time-based expiry is inferred.
- The authenticated retirement predicate has focused tests for exact pending
  keys, owner-generation mismatch, session bounds and admission high-water.
  Wrong backend key, unauthenticated/network failure, duplicate receipt,
  missing Node proof, disabled retention, outbox storage-full, lost-ACK retry,
  and duplicate-after-reboot paths are covered by the focused host targets.
- An interrupted identity-only preparation retry restores the original
  persisted local-minute context; its reducer checkpoint matches uninterrupted
  execution even when the retry arrives with a different local-minute value.

## Validation

PASS:

- `make hub-runtime-checkpoint-host-test` — three reuse cycles, interrupted
  lifecycle publication/truncation/removal recovery, 3,278-event lifecycle,
  independent-identity retry and refill.
- `make hub-retirement-snapshot-host-test` — authenticated report and exact
  retirement proof rules.
- `make s3-durable-outbox-host-test` — 6,556 exact event admission/recovery and
  bounded completion rejection.
- `make hub-segmented-outbox-runtime-host-test` — existing authenticated runtime
  outbox regression.
- The four targets above pass under ASan/UBSan (`-fsanitize=address,undefined`).
- The updated runtime checkpoint/retry equivalence target also passes under
  ASan/UBSan after adding the persisted local-time retry check.
- Isolated ESP-IDF v6.0.3 `build-outbox.sh` candidate-profile build PASS. The
  image is 1,843,728 bytes with 4 MiB OTA slots. Body retirement remained off;
  the build was not flashed. ESP-IDF emitted existing Kconfig notes for `0`
  boolean defaults and duplicate Bluetooth rename mappings, but no build error.
- `make hub-backend-commit-host-test` PASS.

Known pre-existing failure: `make hub-journal-migration-host-test` still fails at
`clean migration commits`, the development-format ownership-domain failure
already recorded in the Phase 1 handoff. This change does not modify that legacy
migration path; fresh-format lifecycle tests pass.

## Remaining Phase 2 blockers

1. Identity compaction needs per-row enrollment slot/generation plus a durable
   report-derived stale-key admission rule; exact identity evidence is retained
   today.
2. Completion compaction/reclaim is only whole-history. The 6,556 stress cannot
   complete under the current 512 KiB completion workspace, and mixed
   pending/completed partial-segment reclamation is not implemented.
3. Firmware deletion remains disabled pending a product-approved post-sync
   retention policy and its persistent time/clock semantics.
4. The S3 target has no production cloud transport caller. Backend success in
   this checkpoint is a deterministic authenticated host fixture.
5. Physical LittleFS power-cut, S3 memory/wear, and full 72-hour NORMAL/HIGH
   qualification remain outstanding. No S3 flash was written.

No production Node code, classic ESP32 target, partition CSV, C3 state, BAT-C8,
canonical worktree, product decision, or context version was changed.
