# P2-C final safety validation — 2026-10-10

Classification: TEST_EVIDENCE / HOST-MEASURED / TARGET-BUILD. Jira: GS-148.

Implementation baseline and START_HEAD: `984913a7194439d628598b5d79adbb156ed9c25d`
on `feature/r1-s3-hub-bringup`, worktree `/home/udaybhan/projects/Ghar_sajag_r1_s3`.
The follow-up commit containing this evidence finalizes the existing implementation;
it does not restart P2-C or authorize production deletion. Context preflight passed
at `2026-10-09.001` before work and after validation. No new product decision.

## Final source and scope

The interrupted session left exactly three tracked modifications: the Makefile,
`durable_event_outbox.cpp`, and `hub_mixed_body_compaction_validation.cpp`.
All were preserved. The final reserve gate uses
`max(caller_reserve, limits.protected_capacity_bytes)`, so callers cannot reduce
the configured protected reserve. It checks actual free filesystem capacity before
candidate staging and publication. Existing partition-configuration validation is
kept separate from usable-space exhaustion. No architectural rewrite was required.

The focused test now separates simulated external filesystem occupancy from
partition capacity, measures event-body blocks separately from completion metadata,
checks original persisted local minute after pending retries, and reports host RSS.
Additional final boundary tests cover caller reserves 0, 4096 and 16384 bytes with
an 8192-byte configured reserve: one byte below required staging plus effective
reserve refuses; the exact boundary succeeds. Refusal leaves every fixture file
byte-for-byte unchanged and all original bodies recover after reboot. An invalid
partition returns UnsupportedConfiguration without modifying files. Corrupt or
missing selected candidate bodies fail closed; no obsolete bank substitutes for them.

BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D023,GS-D029
TASK_SCOPE=authorized P2-C reserve safety fix and final validation/commit
OUT_OF_SCOPE=P2-D, retention policy, physical flash, C3/BAT-C8, other worktrees

The reserve enforcement preserves required durability/recovery under storage
pressure. Fixture reserve values are test inputs, not approved product policy.

The [source manifest](raw/R1_S3_P2C_FINAL_20261010/source-sha256.txt) hashes all tracked
code inputs, including the final three modified files. Its SHA-256 is
`e7348c05e15e39fd041313594c9c5b681a66f2adf7df06082e7daeac0c9bf7ec`.
The manifest was rechecked after validation; code inputs were unchanged.

## Fresh final-source validation

Every batch below finished with an observed process exit code of 0.
[Exit codes](raw/R1_S3_P2C_FINAL_20261010/observed-exit-codes.json) and
[checksums](raw/R1_S3_P2C_FINAL_20261010/SHA256SUMS) accompany the full logs.
Commands ran from the versioned code directory. Host builds used `make -j2`.

| Batch / raw log | Targets and result |
|---|---|
| [Focused](raw/R1_S3_P2C_FINAL_20261010/focused.log) | `hub-mixed-body-compaction-host-test`; PASS |
| [Focused ASan/UBSan](raw/R1_S3_P2C_FINAL_20261010/focused-asan.log) | Same target with isolated instrumented objects and binary; PASS |
| [Regressions](raw/R1_S3_P2C_FINAL_20261010/regressions.log) | `hub-runtime-checkpoint-host-test`, `hub-incremental-completion-host-test`, `hub-identity-compaction-host-test`, `s3-durable-outbox-host-test`, `hub-segmented-outbox-runtime-host-test`; all PASS |
| [Additional ASan/UBSan](raw/R1_S3_P2C_FINAL_20261010/sanitizers.log) | Incremental completion, identity compaction, durable outbox and segmented runtime targets above; all PASS |
| [Clean S3 build](raw/R1_S3_P2C_FINAL_20261010/s3.log) | ESP-IDF v6.0.3, ESP32-S3, new `/tmp/p2c-closeout-20261010/s3-build` directory; PASS |
| [Context preflight](raw/R1_S3_P2C_FINAL_20261010/context-preflight.log) | Local/canonical `2026-10-09.001`; PASS |

Sanitizer flags: `-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic
-DGS_PRODUCT_AI=0 -fsanitize=address,undefined -fno-omit-frame-pointer`.
`ASAN_OPTIONS=detect_leaks=0`, `UBSAN_OPTIONS=halt_on_error=1`.
Objects: `/tmp/p2c-closeout-20261010/asan-objects`; focused binaries:
`/tmp/p2c-closeout-20261010/mixed` and `mixed-asan`, selected with
`MIXED_BODY_TEST_BINARY`. LeakSanitizer qualification is not claimed.

Clean build command after sourcing `/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh`:
`idf.py -C firmware/hub/target/esp32s3/idf -B /tmp/p2c-closeout-20261010/s3-build
-D SDKCONFIG=/tmp/p2c-closeout-20261010/sdkconfig build`.
The existing untracked sdkconfig was copied to that temporary path; source sdkconfig
and managed_components were preserved. Installed LittleFS 1.20.4 was used; registry
connectivity checks were skipped by the dependency manager, and the build completed.
Image size: 1,863,536 bytes (`0x1c6f70`), candidate OTA slot: 4,194,304 bytes,
remaining slot space: 2,330,768 bytes. Image SHA-256:
`7ee63db4c8baff157f30d2d01d739fd7302492a95bb8cf82f2cbf35823223dd0`.
Generated config does not enable body retirement or identity deletion; the runtime
retention-satisfied authorization remains false. No flash command was run.

## Results and measurements

- 42 mutation boundaries, 84 before/after publication/reclamation interruption checks.
- Six subsequent-admission interruption cuts; empty candidate generation, stale
  generation rejection and deletion-disabled recovery cleanup all PASS.
- Original ordinal and encrypted payload preservation, dense completion-bit mapping
  over sparse bodies, original event time/local minute, pending duplicate retries,
  durable-before-ACK and replay-fence consistency all PASS.
- 32 mixed reclaim/refill windows, 3,232 cumulative admissions; oldest pending event
  survives throughout. Maximum retained bodies 16; root 306 bytes; index 14,344 bytes.
- Six-Node authenticated runtime: 12 windows, 1,440 admissions, 31 pending bodies
  preserved per window through body/identity compaction and reboot. Retained identity
  window maximum: 22,346 bytes. Exact lost-ACK retry has no repeated reducer effect;
  conflicting retry is rejected and retired exact keys remain fenced.
- HIGH 3,278-event lifecycle, 6,556 cumulative incremental completions and
  two 6,000-identity windows (12,000 cumulative identities) PASS.
- Incremental completion storage falls from 524,262 bytes to zero in the first
  window with an 883-byte replacement root; all three windows and six crash cuts PASS.
- Measured POSIX allocated file blocks: 49,152 before, 16,384 after; **32,768 bytes
  recovered**. Event-body files independently fall from 28,672 to 4,096 allocated
  bytes; **24,576 event-body allocated bytes recovered**.
- Original body logical bytes 25,057; retained body logical bytes 3,268.
  Fixture total logical bytes before 32,120. Temporary peak: **35,694 logical bytes**
  and **57,344 allocated bytes** (3,574 logical / 8,192 allocated above baseline).
  Planned protected-copy workspace in this measurement: 20,480 bytes.
- Host process peak RSS: normal 10,344 KiB; ASan/UBSan 365,068 KiB. These are whole
  host process measurements, not target compaction RAM/PSRAM measurements.

## Prior logs and qualification limits

The five requested prior `/tmp/p2c-*-final.log` files were inspected. They contain
terminal success output, but no saved exit status; previous execution handles and
final-source provenance cannot be recovered from those logs. They were left intact
and are superseded for final-source qualification by the fresh runs above. The
[audit](raw/R1_S3_P2C_FINAL_20261010/prior-log-audit.json) records their exact hashes,
last lines and missing exit-code attribution. No PASS is inferred solely from them.

Production body deletion remains DISABLED; identity deletion is also disabled.
No physical S3/C3 flash, reset, erase, repartition or enrollment was performed.
The C3's previously observed seven pending events were not accessed or altered.
No other worktree or BAT-C8 source was modified. P2-D was not started.

Host allocation recovery is real POSIX file-block recovery, not physical LittleFS
flash-chip recovery. Physical power-cut/GC/wear, target RAM/PSRAM/stack, signed FOTA
application rollback compatibility, retention approval, production cloud transport,
commercial capacity and 72-hour workload guarantees remain open. A mostly pending,
near-full partition may lack staging workspace and must fail closed. Deliberate
valid-image flash rollback remains outside the GS-D029 freshness guarantee.
P2-C implementation and host/build validation are complete; Phase 2 and physical
qualification remain open. Next task: P2-D, without beginning it in this closeout.
