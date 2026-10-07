# R1 worktree reconciliation — 2026-10-07

This is a reconciliation/validation snapshot, not product-requirement authority.
Canonical scope remains in the release contract and locked decision log.

## Starting state and scope

- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`.
- Branch: `feature/r1-commercial-baseline`.
- Start HEAD: `4026e10e314b00903e0f8acf9854c794e69e5f4b`.
- Context preflight: PASS, version `2026-10-07.001`.
- Initial changes: 17 modified tracked files and 57 untracked files (74 total);
  no staged changes or deletions. Three additional deliberate historical host
  evidence files were found behind the code-level `evidence/` ignore rule and
  explicitly tracked unchanged so the canonical reference survives worktrees.
  Total reviewed project files: 77, including these ignored evidence files.
  Governance entry files were already committed
  in `4026e10`; the canonical storage contract was still untracked.
- Ignored build products remain ignored; no generated binaries are committed.
- No new worktree, hardware operation, initialization, flash, Jira modification,
  destructive Git operation, or new storage architecture work occurred.

## Logical commit plan and origin

| Unit | Purpose / likely prior task | Requirement / decision | Validation | Commit |
|---|---|---|---|---|
| governance | Finish tracking the existing canonical storage contract and add BAT-C8 Jira mapping | GS-D003–GS-D012, GS-D016; GS-D020 → GS-114 implementation/focused qualification, GS-146 final R1 battery closure | Preflight, canonical paths/links, locked-decision traceability, shell syntax, whitespace | `3961993` |
| empty_aead | Close the previously qualified Node zero-payload accelerated-AES boundary fix and shared target/host regression | Supported fresh-install authentication and existing persistence format | Production PSA host runner with exact IDF pointer guard; 13 shared checks; existing Node target PASS in preserved logs | `22682af` |
| hub_durability | Close native registry/checkpoint ownership, pending-key first admission, owner stack, cooperative recovery, and lost-ACK HIL controls | Durable-before-ACK, authenticated ownership, retry/dedupe, fail-closed recovery; GS-D001/GS-D016 | Seven focused C++ gates, dispatcher test, three real Xtensa ELF checks | `ea9d4ba` |
| factory_tools | Preserve explicit development initializer, readiness-gated commissioning, supervised delayed GET_STATE, and selected-event lost-ACK operator flow | Existing physical qualification procedure; no synthetic PIR | 44 factory tests pass; 2 optional initializer-ELF cases skipped; 4 USB-stable profile tests pass | `d443998` |
| usb_tools | Preserve existing downloaded zero-touch convenience tooling as a separate unit | GS-D015; DEFER_POST_R1 for further convenience work | 7 Python tests, 41 mocked Windows PowerShell checks, shell syntax | `cd8fccf` |
| physical_evidence | Preserve old state/garbled attempts and final physically qualified lost-ACK capture; record reconciliation | Existing closed physical gate in R1_WORK_STATE | Raw/status inspection and byte/hash preservation, not a new hardware run | Evidence/closeout commit containing this report |

The firmware origin is supported by the matching source paths, focused tests,
canonical closed-gate list and preserved physical markers. The earlier host audit
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/RESULTS.md`
explicitly documents the native-registry/checkpoint correction, Makefile fix,
and pre-existing legacy migration failure. Exact historical task
IDs/authorship for these uncommitted source changes are not available in Git;
Jira attribution is UNKNOWN except the user-provided GS-D020 mapping. These are
completed fresh-install qualification changes, not a partially started lifetime
storage redesign or a BAT-C8 implementation extension. Relative to the start
HEAD, they add the already-qualified semantics described above; this reconciliation
added no new product behavior.

Changes made during reconciliation were limited to BAT-C8 traceability, an optional
original-ELF path/explicit missing-artifact skips in the stack test, whitespace in
the offline runner, a current-status note in the historical factory procedure,
raw-evidence Git attributes, and this closeout. No locked requirement changed;
CONTEXT_VERSION remains unchanged.

## Focused validation and known failure

- PASS: `hub-fresh-install-host-test`, `hub-recovery-scheduling-host-test`,
  `registry-persistence-host-test`, `hub-durable-storage-host-test`,
  `hub-durable-provider-host-test`, `hub-retirement-snapshot-host-test`,
  `hub-journal-persistence-host-test`.
- Recovery simulation: 128 records, 256 cooperative handoffs; old uninterrupted
  interval 6690 ms, longest independent segment 29 ms. This injected-latency host
  result is not a physical timing qualification.
- Real existing Hub ELF: nested frame sum 51680 bytes, allocation 81920 bytes,
  reserve 30240 bytes; compiled hook calls `vTaskDelay(1)`.
- Factory suite: 46 cases, 44 passed and 2 skipped because the optional original
  Hub-initializer ELF is absent. Dispatcher/profile suite: 5 passed. Hub ELF suite:
  3 passed using the archived original-frame input. USB suite: 7 Python tests and
  41 mocked PowerShell checks passed; no actual installation/USB action ran.
- Production PSA offline regression: PASS, including 13 shared empty-AEAD checks,
  known answer, tamper, generation/reboot, write fault and idempotency cases.
  Portable software PSA with the exact IDF pointer guard proves the host boundary;
  real accelerated-AES execution is evidenced by the existing target log only.
- FAIL: `hub-journal-migration-host-test` at `clean migration commits`.
  The same gate fails at the same assertion using an untouched `git archive` of
  start HEAD `4026e10`. This is a pre-existing deferred legacy-migration failure,
  not a regression introduced by these uncommitted changes. Classification:
  DEFER_POST_R1 under GS-D001/release fresh-install scope. No migration code/test
  assertions were changed or skipped. `validation-fast` was not run; it still
  includes this failing migration target and cannot be claimed green.
- Preflight, canonical path/link checks, duplicate canonical-source check,
  all 15 locked decisions' destination checks, shell syntax and staged whitespace
  checks passed. Raw CRLF Node/Hub captures have scoped binary Git attributes.

## Existing physical evidence

Earlier Node captures with zero live counters and the garbled two-terminal Hub
attempt remain historical evidence; their generic NORMAL_COMMAND_COMPLETE does
not establish the final lost-ACK invariants. The final capture is authoritative
for this completed gate:
`docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/status.json`.
Selected EventKey: `p15:c3-146393c5d158n15:hil-signed-fotas1530q1`.
Records before/unique/duplicate: 77/78/79, with one independently committed event.
Selected duplicate growth: `79 - 78 - 1 = 0`. Node selected ACK class=0 retired=1;
final retained=0, in_flight=0. No physical gate was repeated.

## Per-file classification

Every initial changed file is listed below. Origin, requirement, Jira attribution
and validation apply by the unit table above. All source/document/test/evidence
units are complete and safe to commit after their stated checks; download streams
are generated OS metadata, not project content. No file has UNKNOWN semantics.

| PATH | CATEGORY | UNIT | COMPLETE | SAFE_TO_COMMIT |
|---|---|---|---|---|
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/Makefile` | TEST_AUTOMATION | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/common/security/psa_commissioning_crypto.cpp` | R1_PRODUCT_CODE | empty_aead | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/registry/registry_persistence.cpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/registry/registry_persistence.hpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/durable_transition.cpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/durable_transition.hpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/hub_durability_owner.cpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/hub_durability_owner.hpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/journal.cpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/components/storage/journal.hpp` | DURABILITY_STORAGE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_runtime_adapter.cpp` | R1_PRODUCT_CODE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_runtime_adapter.hpp` | R1_PRODUCT_CODE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_security_link.cpp` | R1_PRODUCT_CODE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/hub_security_link.hpp` | R1_PRODUCT_CODE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/idf/main/hil_control.cpp` | R1_PRODUCT_CODE | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/idf/main/CMakeLists.txt` | R1_PRODUCT_CODE | empty_aead | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/idf/main/app_main.cpp` | R1_PRODUCT_CODE | empty_aead | YES | YES |
| `AGENTS.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/zero_length_aead_qualification.cpp` | R1_PRODUCT_CODE | empty_aead | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/zero_length_aead_qualification.hpp` | R1_PRODUCT_CODE | empty_aead | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/factory_node_reset_validation.cpp` | TEST_AUTOMATION | empty_aead | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/hub_fresh_install_validation.cpp` | TEST_AUTOMATION | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/cpp/node_empty_aead_checks.hpp` | TEST_AUTOMATION | empty_aead | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_factory_bench.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_factory_command_supervisor.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_factory_commission.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_factory_initializer_stack.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_factory_lost_ack.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_hub_hil_control.py` | TEST_AUTOMATION | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_hub_runtime_stack.py` | TEST_AUTOMATION | hub_durability | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/test_node_usb_stable_profile.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/README.md` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/bench.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/esp32_init/CMakeLists.txt` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/esp32_init/main/CMakeLists.txt` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/esp32_init/main/app_main.cpp` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/esp32_init/sdkconfig.defaults` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/esp32_init/sdkconfig.node.defaults` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/lost_ack.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/sdkconfig.size.defaults` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/serial_command.py` | TEST_AUTOMATION | factory_tools | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/factory/validate_node_reset.py` | TEST_AUTOMATION | empty_aead | YES | YES |
| `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` | CANONICAL_GOVERNANCE | governance | YES | YES |
| `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `docs/hw/evidence/NODE_FINAL_STATE/command-_3jqv2ms/output.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/NODE_FINAL_STATE/command-_3jqv2ms/status.json` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/NODE_FINAL_STATE_WITH_HUB/command-wy56436k/output.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/NODE_FINAL_STATE_WITH_HUB/command-wy56436k/status.json` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_20261007_HUB/command-q233fi2s/output.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_20261007_HUB/command-q233fi2s/status.json` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_20261007_NODE/command-gg2_q21h/output.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_20261007_NODE/command-gg2_q21h/status.json` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/hub.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/node.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/output.log` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/status.json` | HIL_EVIDENCE | physical_evidence | YES | YES |
| `docs/product/CANONICAL_REQUIREMENTS_INDEX.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `docs/product/DECISION_LOG.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `docs/product/R1_RELEASE_CONTRACT.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `docs/product/R1_WORK_STATE.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `tools/usb/README_ZERO_TOUCH.md` | DOCUMENTATION | usb_tools | YES | YES |
| `tools/usb/README_ZERO_TOUCH.md:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `tools/usb/gs-usb-autowatch.ps1` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/gs-usb-autowatch.ps1:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `tools/usb/gs-usb-common.ps1` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/gs-usb-wsl-config.py` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/install-gs-usb-zero-touch.ps1` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/install-gs-usb-zero-touch.ps1:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `tools/usb/install-gs-wsl-usb.sh` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/install-gs-wsl-usb.sh:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `tools/usb/tests/test-usb-automation.ps1` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/tests/test_wsl_config.py` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/uninstall-gs-usb-zero-touch.ps1` | TEST_AUTOMATION | usb_tools | YES | YES |
| `tools/usb/uninstall-gs-usb-zero-touch.ps1:Zone.Identifier` | BUILD_GENERATED | preserved_metadata | NOT_APPLICABLE | NO |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/RESULTS.md` | HIL_EVIDENCE | historical_host_evidence | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/baseline_migration.log` | HIL_EVIDENCE | historical_host_evidence | YES | YES |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/host_validation.log` | HIL_EVIDENCE | historical_host_evidence | YES | YES |

The additional historical host-evidence unit is TEST_INFRA_ONLY, complete and
safe to commit unchanged after read-only review. Its Jira ID is UNKNOWN; origin
is the 2026-10-05 fresh-native host audit, governed by GS-D001 and durability
invariants. It does not claim physical qualification.

## Preserved uncommitted metadata and safe next action

The eleven `:Zone.Identifier` paths in the table are unchanged Windows
ZoneTransfer streams. Their contents identify either the context-pack ZIP or
`ghar_sajag_usb_zero_touch_v3.zip`; they define no product behavior. They remain
untracked and untouched. Classification: DEFER_POST_R1; no product decision is
needed. Disposition (keep/archive/remove metadata) is left to a separately
authorized cleanup; do not discard them merely to obtain a clean status.

All implementation changes are committed. The current R1 product blocker is
still bounded Hub storage/data lifecycle; BAT-C8 production-critical physical
qualification remains pending. Storage design investigation can begin from this
reconciled commit line after a fresh context preflight. Do not begin implementation
from an invented retention/capacity policy. The known deferred migration gate
failure remains explicit and must be considered when interpreting broader test
results.

## Evidence byte hashes

Git must retain these original bytes, including raw CRLF and the old garbled text.

| PATH | SHA256 |
|---|---|
| `docs/hw/evidence/NODE_FINAL_STATE/command-_3jqv2ms/output.log` | `27784e15295afef3c4f434c149da63327e5f5d5c62f14b1d89ef23c9964fc678` |
| `docs/hw/evidence/NODE_FINAL_STATE/command-_3jqv2ms/status.json` | `0d7ebb47144187ab941a5237f50b0842b924e669b8ded27aa10497952aef90cc` |
| `docs/hw/evidence/NODE_FINAL_STATE_WITH_HUB/command-wy56436k/output.log` | `813520260149e14a9f463421784c9beab1b3bacac91915c307e8378f64fad325` |
| `docs/hw/evidence/NODE_FINAL_STATE_WITH_HUB/command-wy56436k/status.json` | `79bd6d9f1be01dc8005225b06f8585edfe913fbacc4e3f4c71db80e52036289a` |
| `docs/hw/evidence/R1_LOST_ACK_20261007_HUB/command-q233fi2s/output.log` | `f71f2741de6a58336618f5dfb30acb11ea06e93392901f5bfc1a07795fc254fe` |
| `docs/hw/evidence/R1_LOST_ACK_20261007_HUB/command-q233fi2s/status.json` | `a0e496120e9ca5d8e9a7e9dd468be6cf4d24a3c4833eb7debd9f441e48c8c68f` |
| `docs/hw/evidence/R1_LOST_ACK_20261007_NODE/command-gg2_q21h/output.log` | `42cacd82194e2fca7cd216c87732ee83a190b02d1706031a4948abecbc10cd59` |
| `docs/hw/evidence/R1_LOST_ACK_20261007_NODE/command-gg2_q21h/status.json` | `a50669ac9d5b0a3ef8b586b0630bbceb874e76083e177ed4fa05e2414d6bf998` |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/hub.log` | `ace53b401d4ad735821e81d5d7222658a75aa1c27dfcbb1dc970d552e1e13e3f` |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/node.log` | `74445742fb3e3fbde9fbfdce8f0a5cd218362f7bd84b6cabf2b2af7235031c4e` |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/output.log` | `b22354869dfed95e3961e2321579f1bd1d2c305e54557a31b49678a037fb1848` |
| `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/status.json` | `00c602f02347e2b9a51c9eeecb1c4b1851834f66bacedc034a601bd4c0613e3c` |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/RESULTS.md` | `f4461477b93699175dc93dd850ab69c974875cfcc8e4883faaf1440bb986d760` |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/baseline_migration.log` | `449eb614bba72e44638517aa8f5bdf8ca036b7a20afd99532c8c6752becf8911` |
| `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/docs/hw/evidence/FRESH_R1_HOST_20261005/host_validation.log` | `4ef72bc33c56dde6e7eea26d9c8e8ea8a18180a2b9a66b02da754daeb9960670` |
