# S3 outbox completion and partition profile — 2026-10-09

This implementation slice adds a durable backend-completion stream to the
already integrated S3 Hub outbox and a reproducible, explicitly selected
partition profile. It does **not** complete body retirement or storage closure.
Start HEAD: `928a252f7e8269da915a4e1941cdfef44a8b8284`.

## Completion behavior

`CloudSync::handle_backend_reply` remains the authority for receipt validation:
only an authenticated `COMMITTED` response matching the requested `EventKey`
reaches `HubJournal::acknowledge_cloud`. The outbox records the exact event
ordinal and key in a separately encrypted append-only completion stream, then
publishes and reads back an authenticated completion marker before reporting
completion. Repeated receipts are idempotent. An unpublished or torn completion
tail remains pending and can only be published after the backend re-verifies
the exact receipt. AES-GCM completion nonces are freshly generated and tested
for uniqueness in the exercised stream.

Host tests completed authenticated completion for 3,278 of 6,556 admitted
records. Restart and failure injection covered partial completion append,
failed publication, a retry after reboot, duplicate receipt, uncommitted
receipt recovery, and preservation of the previous published completion head.
An intentionally undersized completion budget returns `StorageFault` while the
event body remains present and eligible for retry.
Completed bodies remain in the outbox and remain available for reducer replay;
completion removes them from backend replay only. It is not a retirement marker.

No independent post-retirement identity ledger exists. Current dedupe evidence
is the exact retained event body plus its authenticated identity index. The
runtime also replays the retained bodies to reconstruct reducer/routine state;
there is no durable reducer checkpoint boundary that permits deleting those
bodies without losing recoverable state. The completion contract also provides
no identity-expiration/floor rule. Therefore bodies and their dedupe evidence
are not reclaimed, no segment is reused, and repeated capacity-reuse cycles
are not qualified. Completion-log capacity is bounded at 512 KiB and safely
rejects another receipt when full; no completion compaction has been added.

## Candidate partition and build

The new `build-outbox.sh` selects `sdkconfig.defaults.outbox` in an isolated
build directory. ESP-IDF 6.0.3 generated and accepted this 16 MiB layout:

| Label | Offset | Size | Type |
|---|---:|---:|---|
| `nvs` | `0x9000` | 24 KiB | NVS |
| `otadata` | `0xF000` | 8 KiB | OTA metadata |
| `phy_init` | `0x11000` | 4 KiB | PHY data |
| `ota_0` | `0x20000` | 4 MiB | OTA application |
| `ota_1` | `0x420000` | 4 MiB | OTA application |
| `gs_outbox` | `0x820000` | 4 MiB | LittleFS |
| `gs_state` | `0xC20000` | 256 KiB | NVS |
| unallocated | `0xC60000` | 3.625 MiB | candidate reserve/assets |

The target adapter looks up `gs_outbox` and mounts with formatting disabled;
the S3 persistent-state adapter looks up `gs_state`. A full ESP-IDF build using
this profile passed. The application `.bin` is 1,824,896 bytes, leaving
2,369,408 bytes in either 4 MiB OTA slot. `idf.py size` reports 1,824,773 bytes
total ELF image, 107,761 bytes DIRAM usage (including 26,520 B BSS), and 16,384
bytes IRAM. These are build measurements, not physical runtime heap/stack or
flash-operation measurements.

The profile does not change the connected board. No partition was flashed,
mounted, formatted or erased. The host fault-injection adapter is not a real
LittleFS/flash power-cut test; actual S3 filesystem recovery, wear, peak RAM,
signed FOTA, 72-hour NORMAL/HIGH capacity and backend network transport remain
unqualified. The product backend transport binding is not present in the S3
runtime, so completion was driven by host-controlled authenticated receipts.

## Validation

- `hub-segmented-outbox-runtime-host-test`: PASS; 6,556 exact admissions and
  restart replay; events 129, 385 and 3,278 admitted; 3,278 authenticated
  completion receipts persisted; no body retirement.
- `s3-durable-outbox-host-test`: PASS; 6,556 records, 1,110,125 encoded event
  frame bytes, existing interruption/dedupe scenarios.
- `hub-backend-commit-host-test`: PASS.
- AddressSanitizer + UndefinedBehaviorSanitizer outbox-core and integrated-runtime
  targets: PASS.
- ESP-IDF 6.0.3 clean S3 build with the outbox profile: PASS; `.bin` is
  1,824,896 bytes, with 2,369,408 bytes remaining in the smallest OTA slot.
  IDF emitted its existing Kconfig bool-default and duplicate rename-map
  notices; there were no application compilation or link errors.
- `hub-journal-migration-host-test`: FAIL at existing clean migration commit
  assertion; this change does not modify the migration source or test path.
- No LittleFS SDK/flash-emulator fault-injection test or physical flash test was
  run; the production adapter was compiled by the ESP-IDF build only.

No product policy, context version, production board contents or C3 state was
changed. GS-D025's 72-hour target remains a design target, not a capacity
guarantee. GS-D026 aggregation semantics, GS-D029 data-security scope, and
GS-D030 S3 direction are unchanged.

The next storage slice must first persist the complete materialized
routine/coverage reducer state at an authenticated, replay-safe checkpoint,
then add exact identity retention independent of event bodies. A safe identity
expiration/floor contract is still needed before old identities can be
discarded. Only after those dependencies are durable can completed bodies be
retired and segments reclaimed safely.
