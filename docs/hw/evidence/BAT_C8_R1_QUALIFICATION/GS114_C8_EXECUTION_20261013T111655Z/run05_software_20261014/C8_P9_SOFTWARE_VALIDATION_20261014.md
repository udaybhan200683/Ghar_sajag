# GS-114 C8-P9 software validation — 2026-10-14

## Scope and provenance

- Repository: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Source checkpoint at task start: `3c677f0b6fa2ed77405cd87905f9e80b71e89fbf` (same as `origin`)
- Code under test: production C3 power/runtime policy, production C3/Hub protocol and runtime, production FOTA state/adapter code. The only source-tree change for this P9 task adds a permanent host regression and traceability entry; no production firmware source changed.
- Hardware, serial, USB/IP, firmware build/write, reset, commissioning and physical motion: **not used**.
- Installed C3/S3 images and commissioning state were not inspected or changed during this software-only task.

## Results

### ACK-window sleep policy

Added `ack_wait_sleep_transition()` to `code/tests/cpp/gs150_offline_sleep_validation.cpp` and mapped it as `GS150-SLEEP::ack_pending_to_idle` in `docs/validation/MASTER_TRACEABILITY.csv`.

The scenario uses the production NodeRuntime/HubRuntime pair. It creates a real authenticated durable event, leaves the application ACK unresolved beyond the 10,000 ms receive budget, and proves that the exact EventKey remains pending while both pending-TX and ACK-wait inhibitors prevent sleep. It then delivers the authenticated Durable ACK, verifies exact-key retirement and persisted removal, and checks that normal idle sleep eligibility returns. `make gs150-host-test` passed with **1,500 checks**; the AddressSanitizer/UndefinedBehaviorSanitizer run also passed with **1,500 checks**.

The existing GS-150 outage/retry matrix was reused: its paired production-code workloads cover delayed/late/missed ACK, bounded listening, offline sleep, Hub outage and recovery. No physical timing or power claim follows from these host scenarios.

### FOTA software behavior

Existing production-code checks were reused without changing FOTA implementation:

- `make battery-c8-host-test`: **72 C++ checks** and **11 Python invariants** passed.
- `make secure-fota-adapter-host-test`: **2 focused groups** passed for authenticated adapter/session and image-hash behavior.
- `make fota-host-test`: **34 checks** passed, including malformed/bounds/session rejection, hash match/mismatch, abort/timeout and boot-health wait/validate/rollback decisions.
- `make board-stack-e2e-host-test`: **8 scenario groups / 325 checks** passed. Production-code simulation covers authenticated FOTA maintenance sleep inhibition, interrupted/expired transfer cleanup, retained-event preservation and post-update boot-health rollback decision/recovery flow.
- `PYTHONPATH=tests/python python3 -m unittest test_secure_signed_fota_fixture -v`: **16/16** orchestration/manifest/profile guard checks passed. This validates the host fixture runner and artifact guards; it does **not** establish ESP-IDF target cryptographic signature acceptance.
- `make feature-coverage-test`: mapping integrity passed for **175 features, 205 modules and 15 physical cases**; the framework's **19 tests** passed. Traceability consistency is not physical evidence.

No signed image was installed or verified on an ESP32. The target receiver's ESP-IDF `esp_ota_end()` path is present in source, but no target-signed test/recovery pair or trusted signing provenance was available for physical validation.

## Validation commands and gate results

Validation ran on 2026-10-14 UTC against the task-start source checkpoint plus the test/traceability working-tree change:

```text
make -j2 gs150-host-test battery-c8-host-test secure-fota-adapter-host-test fota-host-test board-stack-e2e-host-test  PASS
PYTHONPATH=tests/python python3 -m unittest test_secure_signed_fota_fixture -v  PASS (16/16)
make gs150-host-test  PASS (1,500 checks)
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 make gs150-host-test CXXFLAGS='-std=c++17 -O1 -g1 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'  PASS (1,500 checks)
make feature-coverage-test  PASS (175 features / 205 modules / 15 physical cases; 19 tests)
make validation-node  FAIL at registered P0 full-product stage: scenario assertions pass, but product_status=PARTIAL; physical=NOT_RUN
make validation-contract  FAIL at registered P0 full-product stage: scenario assertions pass, but product_status=PARTIAL; physical=NOT_RUN
```

The Node and contract runs completed their prior registered component/contract stages, including GS-150 at 1,500 checks and FOTA host at 34 checks, before the known P0 release-status failure. This is an independent product/release gate failure, not a P9 assertion failure. The historical Hub journal migration assertion failure remains recorded elsewhere and was not hidden or reclassified by this work. No broad release gate was run.

## Disposition

| Subcase | Software result | Physical result |
|---|---|---|
| P9 ACK sleep inhibition and recovery after authenticated retirement | **PASS — host production-code regression** | **BLOCKED / NOT_RUN** |
| P9 signed FOTA maintenance, validation and rollback paths | **PASS — existing host/board-stack coverage reused** | **BLOCKED / NOT_RUN** |

P9 as a whole is **not physically qualified**. Prior RPF07 and C8 P1–P8 physical PASS evidence, including P3, remains preserved and reused; no physical case was repeated here. GS-114 remains In Progress. P10 current/energy measurement remains separate under GS-149.

## Minimum remaining physical fixtures

### P9 ACK

Provide a source-matched commissioned C3/S3 pair and a stable exclusive S3 observation path capable of correlating authenticated C3 schema-3 health with Hub evidence. Provide either:

1. An isolated, bounded fixture that holds a selected postcommit application ACK outstanding for the acceptance observation window, then releases the valid ACK; or
2. A qualified directional RF attenuator/shield arrangement that can reliably delay/block only the application-ACK path for the required interval.

The run must capture the exact EventKey, durable Hub commit before ACK release, Node awake/listening evidence throughout the required window, no premature sleep, valid ACK and Node retirement, followed by later normal sleep eligibility. A one-shot P8 ACK drop alone does not hold the window open long enough to establish this case.

### P9 signed FOTA

Provide a matched signed C3 test image and known-good recovery image, a manifest binding image hashes/profile/slots, trusted signing-key provenance and the target trust configuration that accepts that signer. Also provide a supported authenticated Hub trigger/transfer path, verified OTA slot selection, a safe recovery/rollback procedure, and target logs for signature acceptance/rejection, transfer completion, boot-health validation and rollback/recovery. No signature bypass, invented signing authority, eFuse change or arbitrary OTA image is permitted.
