# Canonical GS-58 / GS-165 / GS-177 Integration — 2026-10-20

## Scope and checkpoint

Owning work: canonical R1 source integration on `feature/r1-commercial-baseline`.
This record covers source integration and software validation only. It does not
claim physical qualification, commercial provisioning, release acceptance, or
Android phone acceptance.

- Pre-integration canonical parent: `5e8cec135e3f72fd14c9818e67bb6e138899077c`.
- GS-58 merge: `de1ec0a4c1cec3907e04efd2fc91cd0b43f7aad8`, parents canonical
  parent and `ece901ecc29aea4cc9650bfd44ca3cf288794ce2`.
- GS-165 merge: `c60828b264bdb8d4d562a614b2126c7d211a8037`, parents GS-58 merge
  and `19034e0a20c3a53b1ddf4f2530243ef0bceb8e0f`.
- GS-177 tip `0120f6f2f57a2568700b5933bcab8eb4ddf18edc` and Home implementation
  commit `45efec6a051cda87732888ba88097b381ceeb57d` are ancestors of canonical.
  GS-177 was already integrated; no second merge was performed.
- The original GS-177 Home delivery evidence commits remain ancestors of
  canonical. The Home design, full-width docked navigation, other tabs, role
  filter, authenticated GS-148 API and freshness behavior were preserved.

The repository remote was verified as
`https://github.com/udaybhan200683/Ghar_sajag`. Final canonical local and remote
HEAD is `bbf073f775aca138d84092b916d005653eab8ae3`. GitHub reports draft PR #1
closed/merged at the GS-58 merge `de1ec0a4c1cec3907e04efd2fc91cd0b43f7aad8`
and PR #2 closed/merged at the GS-165 merge
`c60828b264bdb8d4d562a614b2126c7d211a8037`. These are the existing canonical
merge commits, not duplicate integrations. Jira comments added: GS-58 #11474,
GS-165 #11475, GS-177 #11476, GS-116 #11477 and GS-130 #11478. Tickets remain
In Progress where acceptance is incomplete.

## Duplicate and obsolete functionality audit

- **India Wi-Fi policy:** source search found one `IndiaWifiProfileV1`, in
  `code/firmware/common/connectivity/india_wifi_profile.hpp`. C3 and Hub target
  adapters use that shared profile. The GS-58 reconnect path retains the
  established authenticated rejoin contract; it does not introduce a second
  enrollment/session protocol.
- **Pilot Station and issuer:** the single CLI/registry implementation is
  `code/tools/factory/pilot_station.py`. Its TEST_ONLY adapter
  `pilot_test_issuer.py` reuses the GS-168 issuer; no second PKI or issuer was
  added. The registry is local SQLite and simulated QA remains distinct from
  real device qualification.
- **Caregiver application:** GS-177 was already an ancestor of canonical. No
  second Android/PWA UI or Home data path was imported. The current caregiver
  account remains CAREGIVER; Engineering remains restricted to its existing
  ADMIN + TEST_ONLY authorization and no privilege was changed.
- One narrow caregiver rendering correction ensures Hub-owned decision IDs
  are displayed as decision identity and never as a Node EventKey. This
  preserves the existing independent identity contract; it is not a duplicate
  event or a replacement UI.

## Merge conflict disposition

GS-58 conflicted in `docs/product/R1_WORK_STATE.md` and
`docs/validation/MASTER_TRACEABILITY.csv`. The canonical living work-state was
kept; GS-58 traceability rows were added without dropping canonical mappings.
GS-165 conflicted in traceability only; canonical and GS-58 rows were retained
and GS-165 rows added. No Android/PWA UI file was replaced by an older branch
version.

## Integration validation

Commands and outcomes on/against the integrated source:

| Command | Result |
|---|---|
| `make -C code gs58-wifi-host-test` | PASS, 77 checks |
| GS-58 host test with AddressSanitizer/UBSan and strict warnings | PASS, 77 checks (recorded before merge; GS-58 stage also passed in `validation-fast`) |
| `python3 -m unittest discover -s tests/python -p 'test_gs16*_pilot*.py' -v` | PASS, 24 GS-165/GS-168 tests (also passed as `pilot-factory` in `validation-fast`) |
| `make -C code validation-framework-test feature-coverage-test` | PASS, 51/51 framework tests and 22/22 mapping tests; registry reports 221 features, 263 modules, 26 physical cases |
| `make -C code gs178-software-e2e` | PASS, 29/29 |
| `PATH="$PWD/build/gs177-pwa-test-bin:$PATH" PYTHONPATH="$PWD/build/gs177-pwa-test-deps${PYTHONPATH:+:$PYTHONPATH}" python3 tests/pwa_68_browser_test.py` | PASS, 4/4 browser cases and 92/92 rendered catalogue assertions |
| `python3 validation/run_gs177_connected_lite.py` | PASS, 20 API tests and 8 caregiver runtime tests |
| `make -C code pwa-68-frontend-test` | PASS, 1/1 |
| `make -C code physical-hil-catalogue-test` | PASS, 110 catalog assertions; software catalogue validation only |
| `make -C code validation-fast` | FAIL, exit 2; 79/83 registered stages passed, 4 failed in the report described below |

The current-source browser run verified authenticated Home API binding,
committed HOST_SIM EventKey/room/time display, stale UNKNOWN handling, stale
Node ONLINE downgraded to UNKNOWN, docked full-width navigation, existing tabs,
offline/login behavior and caregiver Engineering denial. It issued no
simulator data request. This is software/browser evidence, not physical Node or
Hub evidence.

## Validation-fast failures and follow-up

Report: `code/evidence/validation_framework/fast-1792477301080677543/report.json`.
The report is immutable evidence of the run at source HEAD
`c60828b264bdb8d4d562a614b2126c7d211a8037`, source fingerprint
`0e65fdf64d580bbc50d8358e9be9b6740b84205570b281afbe80fdf27ecf92f2`, and
elapsed time 1,462.678 seconds. It recorded:

1. **Hub migration:** `clean migration commits` remains a source/acceptance
   failure. No assertion or expected result was changed.
2. **Sanitizer build:** link errors named `RuntimeStateStore` methods. Inspection
   found that the source was already in the host link command, but the
   sanitizer-profile cached object was zero bytes. The host Makefile wrote
   compiler output directly to the final object path and did not detect that
   interrupted artifact. The object rule now writes temporary object/dependency
   files and atomically renames completed outputs; zero-byte cached objects are
   selectively forced through the compiler. The exact target
   `make hub-storage-correctness-sanitize` now passes all registered GS-148
   fault/recovery/capacity cases and prints `GS148 STORAGE SANITIZERS PASS`.
3. **P0 full product E2E:** all 26 scenario checks and the Chromium check passed,
   but the gate correctly reports FAIL while `product_status=PARTIAL`. This
   status is unchanged and must not be waived.
4. **Diagnostic foundation:** the registry delta assertion expected the prior
   stage set and omitted the two integrated stages `gs58-wifi` and
   `pilot-factory`. The assertion now explicitly expects both additions while
   preserving exact comparisons for inherited stages and protected canonical
   registrations. `python3 -m unittest discover -s tests/engineering_dashboard
   -p 'test_registration.py' -v` passes 6/6.

`validation-fast` was not rerun after these two focused repairs. Consequently
the recorded aggregate remains FAIL; current focused evidence shows the
sanitizer and registry failures are corrected. The Hub migration failure and
P0 PARTIAL failure remain unresolved and visible. No release gate was run.

## Paired non-flashing target builds

Command from repository root:

```bash
source "$HOME/.espressif/v6.0.3/esp-idf/export.sh" && \
python3 code/scripts/build_validation_targets.py
```

Result: PASS, ESP-IDF v6.0.3, production profile `GS_HIL_BUILD=OFF`,
`TARGET_COMPILED_ONLY`, hardware actions NONE, physical NOT_RUN. The builder
created fresh ignored directory `code/build/validation_targets/gs116-xk36sdpt/`
and packaged the exact C3 image as the S3 paired Node firmware asset.

| Artifact | Size / OTA slot | SHA-256 |
|---|---:|---|
| C3 `gs_hw_m1_node.bin` | 940,608 / 1,966,080 bytes | `b81bfdc09a04397862faf8dec61e254d6f07d6384342cfdc7b1816e07ac19f6f` |
| S3 `gs_r1_s3_hub.bin` | 2,193,248 / 4,194,304 bytes | `dedaa5f0081bbb88045b22d11228466fe284641373d31aa9ff5913aca3dccca4` |

Build profile/source fingerprint:
`74268f9ebe3286236388c3a5689e3d1b07d0d942631c51460c6f57ac7be40ed5`.
Effective sdkconfig hashes: C3
`c8a7e0dcaaf7053acb1bc46db5cdb2fe1c567e5a02e9eb391d011b23a9789986`; S3
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. The
builder report is
`code/build/validation_targets/gs116-xk36sdpt/report.json`; build outputs are
ignored local artifacts, not Git evidence. The S3 image is not an integrated
GS40 TEST_ONLY provisioning candidate and no image was installed.

## Change classification and limits

```text
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=code/tests/pwa_68_browser_test.py registered PWA browser suite
DECISION_IDS=NONE
TASK_SCOPE=canonical branch integration and affected regressions
OUT_OF_SCOPE=product security policy, production provisioning, hardware qualification
```

The separate Hub decision ID display correction is an R1 correctness fix for
the existing independent Hub-decision identity contract (it must not be
presented as a Node EventKey); it changes no decision semantics.

Open items remain: GS-58 installer authorization D1 and protected
credential/NVS provider D2, first-time commissioning and physical channel
qualification; GS-165 uses TEST_ONLY ephemeral issuer material and has no
production issue/physical QA; GS-177 current-source phone APK installation and
physical caregiver acceptance; GS-40/GS-117 physical Node-to-Hub path; required
P0 `product_status=PARTIAL`; the Hub `clean migration commits` assertion; and
the laptop LAN address/forwarding mismatch already recorded in work-state.
Production CA/DS/eFuse/secure-boot approvals, production endpoints, notifications
and calling qualification are separate gates. Protected C8/C3/GS-68 spare,
serial ports, eFuses, production services and databases were not accessed.

## Final canonical and worktree disposition

The final integration/validation commit is
`bbf073f775aca138d84092b916d005653eab8ae3`; local `HEAD` and
`origin/feature/r1-commercial-baseline` were verified equal. Tracked canonical
files are clean. Pre-existing untracked files, including PWA/Android assets,
ESP-IDF managed components/configuration, and physical evidence, were preserved.

Inactive feature worktrees were fast-forwarded locally to the canonical commit
without pushing their feature refs: `Ghar_sajag_gs58` remains on
`feature/gs-58-hub-wifi` and retains its untracked `managed_components/`;
`Ghar_sajag_gs177` is the GS-165 worktree on
`feature/gs-165-pilot-station`. No separate GS-177 worktree was found. The
detached historical repository, Hub simulator worktree and `/tmp` qualification
worktree were untouched.

The recorded validation-fast run remains FAIL at 79/83 stages; it was not
rerun after focused fixes. The zero-byte sanitizer-object issue and integrated
stage registry expectation were corrected and their focused tests passed.
The Hub migration assertion and required P0 `product_status=PARTIAL` remain
open. D1/D2, physical qualification, production provisioning, and phone
acceptance remain separate incomplete gates.
