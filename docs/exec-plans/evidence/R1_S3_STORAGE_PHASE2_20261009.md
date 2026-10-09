# S3 storage Phase 2 — lifecycle progress and blockers

Context preflight PASS at `2026-10-09.001`. Start HEAD:
`eb94524f71fc25cd95f54e0bedf9368d28a33fa8`. This is a local S3 source/test
checkpoint. No physical flash, C3, canonical worktree, product policy or context
version changed; no push. Phase 2 is **incomplete** and Phase 3 was not started.

## Implemented vertical slice

`JournalEventBackend` now offers immutable-ordinal streaming, and the segmented
outbox adapter preserves each original publication ordinal. `HubRuntime` recovery
validates ordered ordinals, replays only the uncovered tail, and requires every
ordinal after the authenticated reducer checkpoint to be present. A missing body
inside the checkpoint-covered prefix is tolerated; a missing body in the
uncheckpointed tail fails closed. `RuntimeStateStore::recover` now names its
argument as the published event high-water mark rather than a physical body
count. This prepares safe replay after a future retirement implementation; it
does not delete bodies or authorize an identity to expire.

The current outbox still stores body records and completion receipts in separate
append-only LittleFS files. Its backend-completion API is connected through the
host-tested `CloudSync` contract: upload/network failure does not complete an
event, an authenticated exact-key COMMITTED reply publishes completion, a
duplicate receipt is idempotent, and that completion survives outbox restart.
This remains host transport-fixture evidence. The S3 target has no
`CloudBackendTransport` implementation or `CloudSync::drive_batch` call site, so
production backend completion is not integrated.

## Identity and storage measurements

The exact EventKey/payload/context ledger is `identity.log` on the same LittleFS
`gs_outbox` partition as event bodies and completion metadata. It is not stored
in the 256 KiB `gs_state` NVS partition. NVS owner and authenticated Node
retirement snapshots remain in that separate state provider. The identity file
is scanned in bounded frames; the 6,556-record outbox index uses a measured
372,992 allocated bytes in the host build and maps to PSRAM allocation on S3.
Physical S3 heap behavior is unmeasured.

The integrated runtime checkpoint test measured 366,029 identity bytes at 3,278
records and 733,165 bytes at 6,556 records (about 111.5 bytes per exact
identity for this fixed-length key fixture). The current 1 MiB identity budget
therefore contains the requested stress fixture but is finite. Identity records
remain conservative; authenticated retirement snapshots are not yet joined to
this ledger, and no expiry is applied.

The host outbox fixture appended 6,556 bodies (1,110,125 logical frame bytes),
then published 5,472 completion records using 524,205 logical bytes of the
configured 524,288-byte completion budget. The next completion was rejected
before append; repeated rejection added no bytes, the outbox remained healthy,
and the published completion prefix recovered after restart while the next
event remained pending. These are host logical bytes, not physical LittleFS
block occupancy. They expose the current non-reclaimable completion-stream
limit; they do not demonstrate reusable capacity.

## Backend, retirement and migration findings

- The source contains `CloudSync` and an abstract `CloudBackendTransport`, but
  repository search finds no target transport subclass or S3 production caller.
  Live endpoint, TLS/authentication setup and response parser cannot be inferred
  from the host fixture. Host completion behavior passes; production completion
  is not connected.
- The authenticated Node retirement report persists owner, enrollment
  generation, origin session, high-water and up to 32 pending keys through the
  NVS durability owner. The existing bounded `ExactEventKeyLedger` has a
  retirement-eligibility helper, but that report authority is not connected to
  the S3 LittleFS identity ledger. Until a durable join rejects late stale keys
  after identity compaction, identities remain retained.
- No event-body or completion-stream retirement/compaction is implemented.
  Current outbox recovery assumes a complete ordinal body history, and there is
  no segment-generation manifest or reusable segment publication protocol.
  Completion-log capacity rejects safely but cannot be restored. No fill/retire/
  refill cycle is proven.
- Exact minimum local body retention after authenticated backend completion is
  not specified by current product policy (GS-D013/GS-D017 remain open). The
  backend receipt alone does not authorize deletion. A safe lifecycle must also
  preserve the reducer checkpoint boundary and independent replay/deduplication
  evidence, then apply an approved local-retention rule.
- The previously traced `hub-journal-migration-host-test` still fails at
  “clean migration commits” (program exit 1, Make exit 2) because the legacy
  epoch-one genesis registry-owner domain does not match the importer’s registry
  domain. This predates Phase 1 and remains fail-closed. It affects abandoned
  body-only/development migration, not the supported fresh-install format under
  the R1 release contract. No assertion was weakened.

## Validation

- `hub-runtime-checkpoint-host-test`: PASS, including 3,278/6,556 identity
  growth, exact restart lookups, checkpoint-plus-sparse-tail equivalence,
  uncheckpointed-gap fail-closed, and host backend receipt/reboot behavior.
- `s3-durable-outbox-host-test`: PASS, 6,556 exact event bodies and the
  5,472-receipt safe capacity-rejection/restart case above.
- `hub-segmented-outbox-runtime-host-test`: PASS.
- `hub-backend-commit-host-test`: PASS.
- `hub-retirement-snapshot-host-test`: PASS.
- `node-retirement-protocol-host-test`: PASS.
- `hub-journal-migration-host-test`: FAIL, known domain mismatch described above.
- ASan/UBSan: PASS for `hub-runtime-checkpoint-host-test` using a separate
  instrumented object directory. The 6,556-record checkpoint/replay executable
  completed without sanitizer findings.
- Clean ESP-IDF 6.0.3 S3 build: PASS using an isolated output directory and the
  `gs_outbox`/`gs_state` profile. The `.bin` is 1,839,504 bytes; the 4 MiB OTA
  slot has 2,354,800 bytes of build-time headroom. `idf.py size` reports 695,460
  bytes Flash Code, 1,046,268 bytes Flash Data, 107,761 bytes DIRAM (including
  26,520 BSS and 21,074 initialized data), and 16,384 bytes IRAM. This is a
  build-time section report, not runtime internal-heap or PSRAM qualification.
  ESP-IDF emitted non-fatal Kconfig notices for boolean defaults, duplicate BT
  rename mappings, and the configured 800 ms interrupt-watchdog timeout versus
  the Kconfig default of 300 ms. No source compilation errors occurred.
- `git diff --check` and context preflight: PASS at final review.
- No physical storage/power-cut, network backend, S3 runtime heap, or C3 test was
  run. No hardware data was touched.

Phase 2 cannot close until production receipt transport is connected, identity
retirement authority and stale-key rejection are joined durably, completion/body
metadata compaction can restore capacity crash-safely, and multiple refill cycles
pass. The next implementation step is to add a versioned S3 lifecycle root that
binds retained segment ordinals, completion compaction and checkpoint/identity
high-waters before exposing any body deletion operation.
