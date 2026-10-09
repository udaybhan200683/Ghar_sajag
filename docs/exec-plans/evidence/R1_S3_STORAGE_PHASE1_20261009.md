# S3 storage Phase 1 — checkpoints and exact identity persistence

Context preflight PASS: `2026-10-09.001`. Start: `51ca0addde6ada597f5f70448f5763b811190047`.
This is a source/host implementation slice. No physical flash, partition, C3,
canonical-source, product-policy or context-version change; no push. Phase 2
body retirement/reclamation and Phase 3 workload/hardware qualification were not run.

## Implemented transaction and recovery

`RuntimeStateStore` adds three bounded files to the existing serialized LittleFS
writer: `identity.log`, authenticated `identity.head`, and encrypted atomic
`application.head`. Version 1 AES-GCM envelopes authenticate type, version and
lifetime admission ordinal. A separately derived runtime key and fresh random
96-bit nonces reuse the approved crypto provider; randomness/physical entropy
qualification remains required. This is not malicious full-flash rollback detection.

For a new event: persist/read back the exact EventKey, HMAC of its unchanged
versioned payload and original optional local minute; publish the identity head;
commit/publish the event using the existing outbox; apply the reducer; atomically
replace/synchronize/read back the application checkpoint; only then return
Durable ACK. A prepared identity alone is not an accepted event. Exactly one
prepared identity ahead of the committed event head is permitted. An unresolved
prepared key cannot be replaced with another key to manufacture admission credit.

Recovery authenticates every identity record and its published head, verifies
identity and payload against streamed event bodies, restores the checkpoint and
applies only events after its authenticated boundary using their original local
minute. It emits no historical rule signals. A failed checkpoint publication
closes admission even if the filesystem persisted the replacement before the API
reported failure. On restart either the new checkpoint or the old checkpoint plus
committed tail recovers the same reducer state. Missing, malformed, unsupported
or corrupt published checkpoints/identities fail closed; there is no stale-root
fallback. A genesis head detects a missing checkpoint even before the first event.
Only an unpublished partial identity tail can be truncated; no accepted identity
or event body is deleted.

The portable explicit checkpoint schema covers the existing routine configuration,
window/evidence/latches/mode/coverage, every ActivityRuleConfig and ActivityRuleState
field, required-node contact/battery/fault state and cached power telemetry.
Monotonic boot leases and best-effort NodeHealth diagnostics are deliberately
invalidated on restart; trusted peer/session ownership is restored by the existing
security owner, never granted by the checkpoint. Clock trust remains an explicit
rule input. Future-dated coverage after a backwards clock correction is Unknown.
Current coverage is present-moment coverage; this does not invent historical
full-window coverage or a new longitudinal learning implementation.

Configuration/window/mode/monitor changes and timer/deadline alert latches also
checkpoint before decisions escape the runtime. Unchanged snapshots cause no
additional write. Tests demonstrate no repeated returned rule effects on replay
or duplicate ACK. This is not end-to-end external notification delivery
qualification: a crash between returning a decision and external delivery still
requires the existing notification pipeline's separate idempotency/delivery proof.

## Independent identity and finite resource limits

The encrypted ledger stores exact physical owner, logical source, origin session,
sequence and payload evidence independently of event-body files. It has no sequence
watermark, so gaps never imply acceptance. Host tests query/recover it without any
body-store IO. No identity expiration is invented: authenticated Node pending
reports prove pending/highwater state, while backend COMMITTED receipts prove
backend acceptance; the existing contract does not authorize forgetting every
completed EventKey. Identity expiration/compaction remains a Phase 2 contract issue.
Conservative retention is bounded by bytes; exhaustion rejects new admission.

The S3 writer's unchanged 4 MiB partition candidate now budgets 2 MiB event
segments (16 × 128 KiB), 1 MiB identities, 512 KiB completions, up to 128 KiB
checkpoint old/new coexistence, and approximately 384 KiB filesystem overhead.
These are logical engineering budgets, not verified physical LittleFS reserves.
Ordinary events still respect the existing 512 KiB protected event budget.
The application checkpoint has a 64 KiB plaintext limit; oversized snapshots fail
closed rather than truncate evidence. No in-memory identity array is added;
identity scans retain one frame (at most 336 B with the 256 B key bound), and
sequential replay uses a cursor. Snapshot/crypto temporaries are bounded by the
64 KiB schema limit, with several simultaneous buffers; physical peak heap/stack
and PSRAM placement remain unmeasured. Eager checkpoints add write amplification
that must be measured before deployment.

A pre-Phase-1 nonempty body-only installation lacks the new identity/context
publication evidence and is safely rejected rather than auto-migrated or erased.
Its original event encoding is unchanged and its bodies remain intact. Supported
fresh installs and Phase-1 restart recovery are tested. Development-format upgrade
and cross-version FOTA rollback/write compatibility are not qualified here.

## Migration regression classification

`make CPP_OBJECT_DIR=/tmp/gs-phase1-obj hub-journal-migration-host-test`
reproduces `Hub journal migration validation failed: clean migration commits`
(binary exit 1, make exit 2) before Phase 1 changes. The original assertions and
sources remain unchanged. A temporary instrumented copy, outside the repository,
traces the rejection to `DurableJournalSlotStore::append_event` at source line 205,
then `write` line 222 and the importer line 448. The importer sets
`transition.registry_owner_domain = true`, while the legacy epoch-one genesis
created by `initialize_epoch_one()` is not registry-owned. `DurableStore::commit`
rejects that domain mismatch. Relabeling the legacy root would weaken ownership;
a proper registry migration is required, not a relaxed assertion.

```text
BUG_CLASSIFICATION=DEFER_POST_R1
REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md (fresh-install scope, development-format migration exclusion)
DECISION_IDS=GS-D030; existing durability/ownership decisions preserved
TASK_SCOPE=Phase 1 checkpoint, coverage, identity and migration regression classification
OUT_OF_SCOPE=legacy registry migration, Phase 2 reclamation, Phase 3 qualification
```

This remains a visible FAIL, not a fabricated PASS or waived test. It is outside
the supported fresh S3 path; the fresh-install owner/domain regressions pass.

## Executed validation and measurements

- `hub-runtime-checkpoint-host-test`: PASS; original-context replay equivalence,
  failed/torn identity append, interrupted identity head, event publication failure,
  checkpoint failure before/after publication, lost ACK, duplicate/gap/owner/session,
  payload conflict, corrupt/missing/unsupported metadata, timer-latch recovery,
  clock reversal/staleness and 2,048 admissions plus restart.
- Same target with ASan + UBSan: PASS, no sanitizer finding.
- `hub-segmented-outbox-runtime-host-test`: PASS (existing 6,556-event integration,
  authenticated completion, duplicate and publication regressions).
- `hub-backend-commit-host-test`: PASS.
- `hub-journal-persistence-host-test`: PASS after adding the new runtime dependencies
  to its explicit source list; existing legacy journal assertions unchanged.
- `hub-retirement-snapshot-host-test`: PASS; Node report contract untouched.
- `hub-fresh-install-host-test`: PASS (normal and both existing fault modes).
- `cpp-test`: 1,479 checks PASS.
- Context preflight and `git diff --check`: PASS.

Measured four-event checkpoint: 529 encrypted bytes; identities: 438 bytes.
Measured 2,048-event case: 691 encrypted checkpoint bytes, 228,269 identity bytes;
host `sizeof(HubRuntime)`: 1,280 bytes (not target peak RAM).
Clean isolated ESP-IDF 6.0.3 S3 profile build: PASS, final `.bin` 1,839,392 B,
14,496 B larger than the previous 1,824,896 B image; each 4 MiB OTA slot has
2,354,912 B remaining. `idf.py size`: ELF image 1,839,273 B; flash code 695,344 B,
flash data 1,046,268 B; DIRAM 107,761 B (BSS 26,520 B), IRAM 16,384 B.
No compiler error/warning added; pre-existing ESP-IDF Kconfig default-value notes
remain. Build root: `/home/udaybhan/projects/.ghar_sajag_s3_phase1_build_20261009`.

Host adapters model atomic old/new replacement and stop all state-store IO after
injected power cuts until explicit restart. These are not real flash power-cut,
SDK filesystem fault-injection, 72-hour workload or physical RAM measurements.
No body reclamation, safe identity expiration, backend catch-up, physical FOTA or
commercial storage closure is claimed. Next: Phase 2 lifecycle, preserving the
checkpoint/identity dependencies and defining a safe identity-retention boundary.
