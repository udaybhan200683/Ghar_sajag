# GS-117 bounded installed-image receipt correction — 2026-11-06

## Scope and decision

`OWNING_JIRA=GS-117`; offline software/tooling correction approved in GS-117
#11928. `BUG_CLASSIFICATION=TEST_INFRA_ONLY` (it enables trustworthy fixture
evidence but does not change product behavior). No product requirement,
physical acceptance criterion, or security decision changed.

This work reuses the preserved v3 receipt collector rather than creating a
second readback framework. The historical candidate remains unchanged at
`~/.local/state/ghar-sajag/gs117-tc001/provenance-refresh-20261101/candidate/readback_once_v3.py`
(SHA-256 `d1895a348612ae93395fb03ceb69517619c85ecde8fb8a7b9ea89af0d0064ca4`).
The existing 22-case private mock suite is preserved unchanged (SHA-256
`b68756da8cc47fcf989bfa41cb0b52e09074754a6e67546acdf76a91eb3cbede`).

## Implementation

The reviewable collector is `code/tools/local/gs117_tc001_readback.py`. Its
only new flash range is the fixed S3 bootloader region `0x000000..0x008000`
(32 KiB). It keeps the v3 fixture, USB, MAC, chip, security, partition,
selector, active-application and pinned-artifact checks. The exact allowlist
rejects all other ranges and malformed/overflowing values before the target
read call. Evidence creation is exclusive, private (`0600` files / `0700`
directories), hashed and fsynced. The collector contains no write, erase,
NVS, credential, key or eFuse read path.

The existing `code/tools/local/gs117_hil_authorization.py` now recognizes a
separate `readback_receipt` operation. It binds the exact fixture, seven
permitted ranges, reset budget, source/tool/runtime hashes and versions to a
one-use, nonrenewable scope; validates a hash-chained activation/revocation/
reservation/completion audit; prevents replay and concurrent use; and records
partial evidence on failure. It neither changes the existing `readback`
prohibition nor modifies the consumed GS-117 hardware authorization or its
historical ledger. No receipt grant was created or activated in this task.

The existing GS-117 console has a one-use controller entry point that validates
tool pins and Windows/WSL path dependencies before reservation, then invokes
the pinned collector for each role with the same session identity. It is not
safe to use until a new exact-scope owner authorization is separately
approved and activated through the trusted owner process.

The preserved v3 procedure is not passive: for each device it makes one
default-reset ROM-loader connection and, once ROM entry was attempted, one
USB-aware EN hard reset to restore application mode and verify exact USB
re-enumeration. It allows one connect attempt and no retry. These runtime
effects must appear in any later physical approval. This task did not perform
them.

## Exact permitted future evidence scope (proposal only)

Fixture: Home `gs177-test-product`; C3 `c3-146393c5d158`, COM4, USB
`14:63:93:C5:D1:58`; S3 `hub-e072a1d38d34`, COM10, USB
`E0:72:A1:D3:8D:34`.

| Target | Region | Offset | Size |
|---|---|---:|---:|
| C3 | partition table | `0x008000` | `0x001000` |
| C3 | both OTA selector copies | `0x00f000` | `0x002000` |
| C3 | pinned selected application bytes | `0x020000` | 958,992 bytes |
| S3 | bootloader region | `0x000000` | `0x008000` |
| S3 | partition table | `0x008000` | `0x001000` |
| S3 | both OTA selector copies | `0x00f000` | `0x002000` |
| S3 | pinned selected application bytes | `0x420000` | 2,292,864 bytes |

The fixture's hardware identity, active application identity/digest, selector
state, partition entries and bounded bootloader digest are recorded. No NVS,
credentials, keys, eFuses, unrelated flash, general dump, firmware write,
erase, bootloader/partition/selector modification, bootstrap, event injection
or radio observation is included. Stop on identity, security, tool-pin,
partition, selector, authorization or restoration mismatch. Preserve partial
private evidence; no retry. The collector's restore reset is inside the future
approved operation and is not currently authorized.

## Artifact and rollback provenance

The pinned app artifacts used by the existing v3 procedure are C3
`589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7`
(`gs117-dev-rejoin-20261029`, 958,992 bytes; ELF SHA-256
`043ba7db4a89197e608971a590476ea77807e3abbf58f93e050d3a018dd2f234`) and
S3 `ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5`
(`8acab96-dirty`, 2,292,864 bytes; ELF SHA-256
`7584a1f80c1a59dc55e7fed9ae3092618cde7c8be8c8ccca6b041e302bf52ed1`). The
tool also pins the partition-table digests and exact expected layouts. These
are the collector's historical expected artifacts; fresh device capture was
not performed, so installed receipts remain STALE.

The previously observed S3 bootloader digest
`ae304441aaaad2b52765d48f4b37752f2ab26a65a480f5f1f9586cd54ebe1580` still has
no trusted matching build/configuration provenance. A new hash over the
32-KiB region will identify bytes only; it cannot establish automatic rollback.
GS-D029 application rollback remains mandatory. Candidate installation remains
NO-GO until trusted rollback-capable bootloader provenance and all applicable
deployment/recovery evidence are established.

## Offline validation

New focused tests:

- `python3 code/tests/python/test_gs117_readback_receipt.py`: 37/37 PASS.
- `python3 code/tests/python/test_gs117_tc001_console.py`: 173/173 PASS.
- `make -C code validation-framework-test`: 55/55 PASS.
- `make -C code feature-coverage-test`: PASS; 237 features, 288 modules,
  28 physical cases; mapping tests 22/22 PASS.
- Preserved v3 mock suite adapted to load the reviewable collector: 21 PASS,
  1 historical wrapper check skipped because its legacy live-table checker is
  deliberately disabled for offline review; 0 failures. This is not a physical
  result and does not replace the 37 newly registered cases.

The broader tooling gate completed with unrelated failures. Two additional
whole-component gates were started concurrently by mistake; because the
repository requires shared gates to be serialized, their incomplete output is
not treated as a valid suite result. They were interrupted during unrelated
long `gs178-software-e2e` stages to avoid continuing the out-of-scope run. No
failure was weakened or silently waived:

- `validation-tooling`: FAIL. Its 828-test Python stage had 3 failures:
  `test_static_payload_and_collection_budgets`,
  `test_catalogue_maps_every_required_implemented_feature` (catalogue evidence
  path `PHY-GS117-DIAG` is prose rather than an existing path), and
  `test_s3_option_is_opt_in_and_legacy_broad_hil_stays_rejected` (builder text
  assertion). Its HIL-tooling stage also failed that same catalogue evidence
  path. The registered GS-117 console stage itself passed 173/173.
- `validation-contract`: INCOMPLETE/INTERRUPTED during `gs178-software-e2e`;
  an earlier S3 fixture commissioning stage reported 1 failure in 18 tests.
  The concurrent run is not a trustworthy full-gate result.
- `validation-backend`: INCOMPLETE/INTERRUPTED during `gs178-software-e2e`;
  an earlier 828-test Python stage reported 3 failures (same unrelated tooling
  failures above). The concurrent run is not a trustworthy full-gate result.

These failures do not point to the receipt-correction source; the GS-117
focused and registered console tests pass. The whole validation-tooling gate
still remains FAIL. No firmware target build was needed because firmware
source was unchanged. No Windows live qualification, serial access or physical
device operation occurred.

## Source and test identities

At the reviewed source checkpoint before documentation finalization:

- Collector SHA-256: `87373b43cbce3036c427fe90723b3edfddc269bbd3d92ca3b63f0f6a688ce312`.
- Authorization module SHA-256: `1afd803d34ff59a29aae6be8b8068d9bb09b8ed04bef2437e4a972cec883c70c`.
- Console SHA-256: `d641e76ab241a04df4756783e2e836638a0614da90aa1fa5d20d560a8aa511e5`.
- Focused test SHA-256: `888e488a2f81cbcef273e1cdbd60cac93d8c431a3c95473d0f361443a0e0ef71`.
- Console suite SHA-256: `bc2fafc4c98f81fac72bed754ef918f84fc2b86fd94631178cb9fd898edc9157`.
- Suite registry SHA-256: `fb979f9b68f4df58035f6bb85631382a7a32fddd9db4d1bf44abeab770589e7d`.

Recalculate these after any source/test change and pin the exact final
collector, controller, authorization module, Python/esptool/pyserial/partition
parser identities in any future one-use authorization. A suitable runtime
identity is not activated or approved by this offline change.

## Status and next decision

- Hardware/COM/ROM/reset/readback operations: **NONE**.
- Receipt authorization created/activated: **NO**.
- Existing #11897 latch: unchanged, `SAFETY_LATCHED`, 1/1 consumed; #11886
  unchanged.
- Installed firmware: unchanged; receipts STALE; `TC001_READY=NO`; TC-001 0/5.
- S3 rollback provenance: UNVERIFIED; diagnostic installation remains NO-GO.

Future owner approval must authorize exactly one use of the reviewed collector
and controller hashes for the fixture and read ranges above, including the
specified ROM-entry and USB-aware application-restore resets, with no retries
or other device operations. It must be separately activated and audited; this
offline approval #11928 does not grant it. After receipts are captured, compare
the installed bootloader bytes against trusted build/configuration provenance
and GS-D029 rollback behavior before deciding whether any diagnostic install
is safe. This is a readiness proposal, not physical authorization.
