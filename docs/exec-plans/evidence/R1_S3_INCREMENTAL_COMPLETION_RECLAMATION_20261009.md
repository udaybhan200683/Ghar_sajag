# S3 incremental completion reclamation — 2026-10-09

GS-148 focused implementation evidence. START_HEAD:
`5b473912d690d19b9b0d3aaecbdbabc1806775a6`; branch
`feature/r1-s3-hub-bringup`; context preflight PASS at `2026-10-09.001`.
No new product decision or context version change. Phase 2 remains IN_PROGRESS.

## Durable replacement predicate and publication

`DurableEventOutbox::reclaim_completion_metadata` uses the existing lifecycle
root, selected authenticated Node report and reducer checkpoint. It revalidates
persistent bodies, receipt frames and their publication heads before replacing
completion evidence. A staged/unpublished receipt or event cannot be compacted.
The checkpoint must cover the published event boundary and cannot move behind
the previous lifecycle checkpoint. Report generation cannot decrease; equal
generation requires an identical report digest. Every newly substituted
completion needs exact Node retirement proof for its key and payload. Missing,
stale-owner or incomplete proof preserves the receipt log without reclaiming it.
Previously substituted bits retain their durable original proof.

The version-2 authenticated lifecycle root retains a bitmap over immutable event
ordinals, an event-publication anchor, report generation/digest and checkpoint
boundary. A streaming HMAC chain binds every completed bit to its exact ordinal,
EventKey (including physical device/session ownership) and versioned effect
payload. Pending bits remain clear. Retained authenticated bodies are mandatory
recovery dependencies. This substitutes exact completion evidence; it does not
expire EventKeys or authorize body/identity deletion. All newly substituted
receipts must satisfy the predicate; a partially covered report conservatively
blocks that attempt, while pending and retention-gated bodies can coexist.

Publish and read back the pending snapshot root first. Then publish a
generation-bound empty completion head, truncate/sync the old receipt stream,
and publish/read back a finalized root. Recovery validates snapshot dependencies
before repeating interrupted cleanup. Any ambiguous publication faults the live
instance until recovery. Every subsequent completion head carries its lifecycle
generation, so a missing root/head fails closed even after fresh receipts append.
Version-1 full-history roots remain readable. Older firmware fails closed on
version-2 metadata; no development-format migration or rollback compatibility
qualification is claimed. Random AES-GCM nonces remain independent of reused
receipt ordinals; the host fixture observes nonce uniqueness across all windows.

The root is bounded to 8 KiB. It retains exact completion state rather than
moving the receipt stream to a second independent lifecycle system. The S3
adapter attempts reclamation on an authenticated report when the stream cannot
fit its maximum next receipt, using the existing selected report/checkpoint join.
Production body deletion stays disabled, including its retention gate.

## Focused results

Normal and fully instrumented ASan/UBSan runs PASS:

| Cumulative completions | Actual adapter receipt bytes before → after | Replacement root bytes | Retained body bytes | Retained identity bytes |
|---:|---:|---:|---:|---:|
| 5,589 | 524,262 → 0 | 883 | 926,999 | 625,085 |
| 6,089 | 47,000 → 0 | 946 | 1,009,833 | 680,973 |
| 6,556 | 43,898 → 0 | 1,004 | 1,087,355 | 733,277 |

The first window actually fills the 512 KiB stream: another receipt is refused
without append or fault, then reclamation restores writable capacity for later
windows. Bytes are measured from the host SegmentStore's stored byte vectors,
not only outbox accounting. Reboots reconstruct all completions. An early
pending event remains selectable; completed events never re-enter CloudSync
batches. ACK-loss duplicate replay preserves reducer state and identity count.
The different receipt limit from the prior 5,472-event fixture follows different
key sizes; the existing fixture still reports 5,472 receipts / 524,205 bytes.

Six deterministic cuts PASS: before and after pending-root publication, before
empty-head publication, interrupted truncation, and before and after finalized-
root publication. Each restores exact mixed completion state and accepts another
receipt. Additional checks PASS for wrong keys, wrong receipt owner generations,
stale/incomplete/missing Node proof, stale report generations, checkpoint lag,
missing roots/heads, detected receipt/root corruption, repeated compaction, and
host-only full-history retirement/segment reuse followed by a nonzero-prefix
completion snapshot. Body deletion is enabled only in that copied host fixture.

Commands (from the code directory):

```sh
TMPDIR=$PWD/build/incremental-tmp make hub-incremental-completion-host-test
TMPDIR=$PWD/build/incremental-tmp ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 make -j2 hub-incremental-completion-host-test CPP_OBJECT_DIR=build/obj/incremental-san CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -DGS_PRODUCT_AI=0 -fsanitize=address,undefined -fno-omit-frame-pointer'
TMPDIR=$PWD/build/incremental-tmp make s3-durable-outbox-host-test hub-runtime-checkpoint-host-test
TMPDIR=$PWD/build/incremental-tmp GS_S3_OUTBOX_BUILD_ROOT=$PWD/build/incremental-s3 firmware/hub/target/esp32s3/idf/build-outbox.sh
```

The final normal focused binary was compiled using the Make target's compile
recipe into `build/incremental_final_normal` to keep its output separate from
the concurrent sanitizer binary. The S3 source objects postdate final production
edits; ESP-IDF 6.0.3 build PASS: binary 1,849,056 bytes, OTA-slot free 2,345,248
bytes. No flash/erase/repartition/re-enrollment occurred. Preserved untracked
`sdkconfig` SHA-256 remains
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`.
`managed_components/` remains untracked. C3/BAT-C8/GS-147 were not changed.

Compiler scratch used the ignored workspace build directory because `/tmp` was
full; existing temporary evidence was preserved. LeakSanitizer alone is disabled
because this environment reports that it cannot run under ptrace. ASan and UBSan
remain enabled with halt-on-error; their final run passes.

## Remaining qualification

Host byte-vector measurements prove receipt-stream writable capacity recovery,
not physical LittleFS allocation, flash wear or power-cut qualification. Identity
ledger compaction and mixed-segment body compaction remain separate unfinished
work. Production cloud transport, retention policy, sustainable end-to-end
capacity and physical S3 qualification remain open. No Phase 3 work was started.
