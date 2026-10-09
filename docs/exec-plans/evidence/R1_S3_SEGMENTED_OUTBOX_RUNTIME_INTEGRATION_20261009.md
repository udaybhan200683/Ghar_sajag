# S3 Segmented Outbox Runtime Integration — 2026-10-09

Starting revision: `f2be15029cf2f3f348d2784581fcd8a516c5a65a`
Context: `2026-10-09.001`
Target: ESP32-S3, ESP-IDF 6.0.3

## Integration result

The S3 Hub composition now constructs `HubRuntime(32, event_backend)`, where
`OutboxJournalBackend` adapts the existing Hub journal API to the encrypted
segmented outbox. It stores the existing versioned `DomainEvent` encoding and
canonical `EventKey` unchanged. Authentication and owner/session checks still
occur in the existing Hub security receive path before runtime admission.

An ordinary `Motion` or `MotionSummary` uses the outbox ordinary-admission
class; all other event kinds use protected admission. The existing `run_state_once()`
calls durable commit before it returns the existing Durable ACK result. The
outbox returns committed only after segment synchronization, record readback and
authenticated publication. Capacity/reserve rejection maps to `Rejected`; a
publication, integrity or storage failure maps to `StorageFault`. Neither
failure path produces a Durable ACK. A duplicate EventKey returns Durable
without applying reducer effects again.

On S3 startup, the target mounts the named outbox without formatting, recovers
the published root, and attaches the backend before opening event admission.
Recovery streams committed events through the existing reducer rather than
building `HubJournal::records()`. Failure to mount or recover keeps admission
closed. The classic ESP32 branch and its NVS slot implementation remain
unchanged; the S3 path no longer has the physical 128-slot journal limit. The
existing 32-event volatile ingest queue remains a separate bounded processing
queue.

Cloud batch selection now streams journal records and retains only the requested
priority-ordered batch, avoiding a temporary vector proportional to the full
outbox. Existing per-event retry/permanent-error tracking remains in CloudSync
and has not been stress-profiled under large backend failure storms.

## Focused validation

| Check | Result |
|---|---|
| `hub-segmented-outbox-runtime-host-test` | PASS; 2,048 records through authenticated HubRuntime, including events 129 and 385, unique observed AES-GCM nonces, restart replay, retry/deduplication, owner mismatch, failed publication, full-capacity rejection and a bounded seven-event cloud batch |
| `s3-durable-outbox-host-test` | PASS; 6,556 records, 1,110,125 frame bytes, five existing append/publication/recovery scenarios |
| `hub-journal-persistence-host-test` | PASS; legacy 128-slot provider regression remains intact |
| `hub-backend-commit-host-test` | PASS; backend completion/idempotency regression |
| Clean ESP-IDF S3 `ninja all` | PASS |
| `idf.py size` | PASS |
| Physical S3 test | NOT RUN; no flash or partition operation was performed |

The runtime integration test uses the existing outbox core with a host memory
SegmentStore and OpenSSL crypto. The existing outbox core’s earlier sanitizer
and 6,556-record evidence remains separate; this new runtime test was run with
the normal host build. These tests do not prove physical LittleFS power-loss or
flash behavior.

## S3 build measurements

The clean isolated build used the current development partition table: two
4 MiB OTA slots and a 2 MiB NVS partition named `gs_journal`. Its application
binary is **1,818,352 bytes** (`idf.py size` total image: 1,818,233 bytes), leaving
**2,375,952 bytes** in the smallest 4 MiB OTA slot. The size report measured:

- Flash code: 674,656 bytes; flash data: 1,045,916 bytes.
- DIRAM: 107,761 bytes, including 26,520 bytes BSS.
- IRAM: 16,384 bytes.
- PSRAM runtime peak, internal free heap and task-stack high-water marks: not
  measured on hardware. The outbox index allocator requests PSRAM on ESP32.

The runtime expects `gs_outbox` and `gs_state`, which are absent from the
development table used for this build and present only in the unflashed
candidate map. The current board layout therefore cannot initialize this S3
storage path and must fail closed. The build result is compile/size evidence,
not permission to flash or repartition the preserved board.

## Remaining lifecycle work

Backend completion and retirement are intentionally not implemented in this
slice. The S3 backend does not persist cloud-completion receipts;
`acknowledge_cloud()` returns false, event bodies are not retired, and segment
capacity is not reused. This integration does not qualify NORMAL/HIGH 72-hour
workloads or close the locked offline target. Also open are candidate partition
selection and preserved-data migration, physical LittleFS power-cut recovery,
large-backlog resource profiling, completion/identity separation, sustainable
reclamation, signed FOTA rollback and physical S3 validation.

No product requirement or context version changed. No physical board, C3 Node,
classic-ESP32 worktree, canonical governance or old storage worktree was
modified. No production partition file was changed.
