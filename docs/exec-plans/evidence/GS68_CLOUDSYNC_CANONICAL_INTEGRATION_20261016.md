# GS-68 CloudSync selective canonical integration — 2026-10-16

## Checkpoint and authority

The integration source is the immutable, pushed commit
44838da836d3014e606cfe2ee57ad624ee417240 on
feature/r1-gs68-gs109-mtls-feasibility. Live remote refs were checked before
work: CloudSync 44838da836d3014e606cfe2ee57ad624ee417240, canonical
d3a17df57e0cf82b598edbc862c7ef0bc0ed14b6. The common ancestor is
12eae946db1ce8c810c9cc7df8e2c17d27d30889; the branch counts were 25
canonical-only and 10 CloudSync-only commits.

GS-148 comment 11177 authorizes selective integration of the latest validated
software subset while preserving the separate development branch. It does not
authorize hardware access, production credentials, eFuse/HMAC provisioning,
production CloudSync activation, or Jira workflow changes. Repository context
preflight passed in both the source and integration worktrees with context
2026-10-13.001.

The integration worktree is
/home/udaybhan/projects/Ghar_sajag_r1_cloudsync_integration on
integration/gs68-cloudsync-into-r1, created from canonical remote HEAD
d3a17df57e0cf82b598edbc862c7ef0bc0ed14b6. Uncommitted files in the active
CloudSync worktree were excluded. In particular, the paired C3 diagnostic
follow-on visible only as uncommitted work was not copied.

## Integrated scope

The selected committed source adds:

- A restricted cloud-purpose RSA-3072 signer seam for ESP32-S3 DS, separate
  from commissioning P-256, plus TLS 1.2 mTLS configuration in the existing
  HTTPS backend channel.
- A backend certificate/fingerprint identity adapter that resolves current
  permanent Hub, Home and ownership epoch and rejects revoked, invalid,
  wrong-purpose, wrong-domain, stale-time and in-flight transfer cases.
- Production CloudSync worker/backend tests for authenticated Hub ingress,
  durable COMMITTED receipt, dropped response, reboot and exact EventKey retry,
  with one durable effect and caregiver projection.
- Security unit tests, simulated HIL, localhost mTLS integration, a standalone
  S3 diagnostic build profile, TEST_ONLY backend and runner-integrity tooling.
- GS-116 stages cloudsync-security-unit, cloudsync-security-sim-hil and
  cloudsync-mtls-integration, plus GS-130 source/feature traceability and
  physical catalogue registration.

The standalone diagnostic profile is not selected by the production build.
Commercial CloudSync remains disabled. No production CA, credentials or backend
route were introduced. The paired C3 observer/control work remains unintegrated
until it is committed and validated.

## Conflict reconciliation

- code/Makefile: preserved canonical C8, GS-40 and release targets; added
  CloudSync tests, isolated diagnostic build and default dry-run HIL targets.
- code/validation/suites.json: merged three CloudSync stages into canonical
  selectors; preserve existing stages and their dependencies. Physical runner
  remains outside software selectors.
- code/firmware/hub/target/esp32s3/idf/CMakeLists.txt: retained canonical
  components and added the CloudSync adapter/DS dependencies without selecting
  the diagnostic app for normal production builds.
- code/tests/engineering_dashboard/test_registration.py: extended the exact
  allowed registry delta to include the three CloudSync stages while asserting
  the canonical and active-baseline stages remain unchanged.
- docs/product/R1_WORK_STATE.md: retained current canonical GS-40/C8 state and
  added this CloudSync integration checkpoint.
- docs/validation/MASTER_TRACEABILITY.csv,
  SOURCE_FEATURE_INVENTORY.csv, PHYSICAL_QUALIFICATION.csv and
  PHYSICAL_HIL_CATALOGUE.csv: retained canonical rows and added the CloudSync
  software/physical mapping. Physical cases remain NOT_RUN.
- Existing canonical work-state, requirements and architecture statements
  remain intact; no product decision or context version changed.

## Validation record

Selected-source evidence at 44838da reports security UT 20/20, simulated HIL
18/18, localhost mTLS/durable-retry integration 1/1, GS-116 framework 47/47,
GS-130 traceability 22/22 and runner integrity 63/63. The S3 diagnostic
build-only image was 442,544 bytes (SHA-256
0e4fede23804199b98c246315e32c6468b49b0a23baaa7717932c2c3d146cb47).
These are provenance only; integrated-source reruns are recorded below.

Integrated-source validation on the isolated candidate (working tree based on
canonical d3a17df57e0cf82b598edbc862c7ef0bc0ed14b6):

- `make cloudsync-security-ut`: PASS, C++ adapter 8 cases and backend security
  unit tests 12/12 (20 total).
- `make cloudsync-security-sim-hil`: PASS, 18/18; physical NOT_RUN.
- `make cloudsync-mtls-integration-test`: PASS, 1/1; durable receipt retry
  completed with one durable effect in two attempts.
- `make validation-framework-test feature-coverage-test physical-hil-catalogue-test gs130-hil-runner-test`:
  PASS, framework 47/47, traceability 22/22, feature mapping 207 features /
  213 modules / 24 physical cases, runner integrity 63/63; physical catalogue
  108 cases and no device access.
- Engineering dashboard registration tests: PASS, 6/6.
- `make validation-node`: component stages PASS; the P0 stage reports
  `product_status=PARTIAL` despite its 26/26 scenarios and browser test passing.
- `make validation-hub`: CloudSync and affected Hub stages PASS; pre-existing
  Hub journal migration assertion `clean migration commits` FAIL and P0
  `product_status=PARTIAL` FAIL.
- `make validation-contract`: CloudSync and contract stages PASS; P0
  `product_status=PARTIAL` FAIL.
- `make validation-backend`: backend and CloudSync stages PASS; P0
  `product_status=PARTIAL` FAIL.
- `make validation-fast`: completed, exit 2. All its remaining stages passed,
  including storage correctness, first-event compatibility/recovery, storage
  sanitizers, compaction, CloudSync unit/simulated/localhost integration,
  HTTPS adapter, Python 507/507, JavaScript 23/23, functional 92/92, HTTP
  17/17, bridge 13/13, API 2/2, frontend 2/2, registration 24/24, HIL tooling
  145, HIL host, board E2E negative, GS-130 runner integrity 63/63 and
  diagnostic foundation 98/98. It remains failed for the known Hub journal
  migration assertion and P0 `product_status=PARTIAL`. P0 scenarios were 26/26
  and Chromium 1/1; the product completeness status remains PARTIAL. These two
  failures were already recorded as baseline blockers before this integration;
  no new CloudSync or build regression was observed.
- Documented `python3 code/scripts/build_validation_targets.py`: PASS with
  ESP-IDF 6.0.3, production `GS_HIL_BUILD=OFF`, physical NOT_RUN. C3 image
  937,536 bytes (SHA-256
  `003d6319a51e7bcc387d8c00f7b1a951676d248dd6491c347edf7550febeed0d`);
  S3 image 1,887,232 bytes (SHA-256
  `7e9088f0804c91de0530cb861a283e7c71b5cba2d41f27e562c98731754c5b77`),
  within its 4 MiB OTA slot.
- Isolated GS-68 S3 diagnostic profile: build completed with ESP-IDF 6.0.3,
  DS peripheral and TLS 1.2 enabled, TLS 1.3 disabled, image 442,512 bytes
  (SHA-256 `84df600e9a13886b6dcb02e0eec20a0ce8c3002bf9e81c118d8461677bd3206b`).
  This build used integration commit
  `3e4b163d8a0e7958e179686b3ea11a3d838488d1` as the source identity. It did
  not flash or access hardware.

The current aggregate has no stages left to run. Its P0 scenarios and browser
passed but `product_status=PARTIAL` remains a required gate failure. The
pre-existing Hub journal migration assertion remains a required failure. No
known newly introduced failing test remains.

Known independent gate failures remain visible: Hub historical journal
migration assertion clean migration commits and P0
product_status=PARTIAL. No result here may relabel them or imply full release
approval. Physical GS68 cases remain NOT_RUN and release-blocking. D05/D12
production custody/verifier, D06 time limits, D15 rollback and D16 numeric
limits remain pending.

## Delivery

The implementation commit is
3e4b163d8a0e7958e179686b3ea11a3d838488d1. The final validation evidence
commit 52fca1bc4166acb2765378e2e3e2a2fc95b750e1 was pushed to
integration/gs68-cloudsync-into-r1 and fast-forwarded to canonical after the
remote canonical ref was confirmed unchanged at the approved starting SHA.
GitHub then verified canonical and integration both at
52fca1bc4166acb2765378e2e3e2a2fc95b750e1. The separate CloudSync development
branch had advanced to
e740f99d094b4a0ef7397f0a506e8f089fb5d261 after the selected validated source
checkpoint. Commits after 44838da836d3014e606cfe2ee57ad624ee417240 remain
unintegrated for a later batch.

No physical devices, ports, production endpoints or customer data were accessed.
The active CloudSync and canonical/C8 worktrees were not edited or synchronized.


## Second incremental batch — GS-68 paired C3 observer (2026-10-16)

**Source checkpoint:** `e740f99d094b4a0ef7397f0a506e8f089fb5d261` on
`feature/r1-gs68-gs109-mtls-feasibility`. The previous integrated CloudSync
checkpoint is `44838da836d3014e606cfe2ee57ad624ee417240`. This batch was
applied selectively to canonical target `c0430b14bd0897de5d22f5ace073bf457302067c`;
no source development worktree files were copied.

Integrated functionality includes the default-off ESP32-C3 read-only PING /
OBSERVE diagnostic observer; shared bounded S3/C3 protocol; boot/reset, link,
retained-event and authenticated EventKey/ACK observations; C3 source/profile
metadata; TEST_ONLY backend signed readiness bound to source/image/profile/case
plan; related capture, dry-run, runner-integrity and negative tests; GS-116/130
registrations and S3-first qualification plan. The C3 observer excludes legacy
HIL injection/reset controls, production Node algorithms are unchanged, and
commercial CloudSync remains disabled. Physical cases remain NOT_RUN.

**High-risk conflict resolutions:**

- `code/Makefile`: kept canonical C8, GS-40, GS-114 and release targets; added
  the C3 protocol host test/build targets and made the runner target depend on
  the protocol test.
- C3 root and component CMake files: retained canonical HIL/C8 qualification
  options and compile definitions while adding the default-off observer, its
  isolated control guard, source metadata, and SPI flash dependency.
- `code/tests/engineering_dashboard/test_registration.py`: retained canonical
  registry assertions and expanded its baseline allowlist for five newer
  canonical stages; added CloudSync opt-in physical-suite checks.
- `docs/product/R1_WORK_STATE.md`: kept canonical GS-40/C8 history, prior
  CloudSync integration history, and the latest CloudSync readiness section.
- `MASTER_TRACEABILITY.csv` and `PHYSICAL_HIL_CATALOGUE.csv`: kept every
  canonical row and updated only the matching CloudSync feature/case rows.

**Focused checks:** `make -C code gs130-hil-runner-test` PASS (protocol 16/16;
Python runners 70/70; hardware actions 0; physical NOT_RUN);
`PYTHONPATH=code/tools/hil python3 code/tools/hil/gs68_test_backend.py
--self-test` PASS (TLS 1.2, RSA-3072, signed readiness, duplicate-safe durable
retry; no external network); GS-116 stage-selection tests PASS (2/2); dashboard
registration no-loss test PASS (1/1); `make -C code feature-coverage-test` PASS
(22/22, 207 features / 216 modules / 24 physical cases). These focused checks do
not rerun the unchanged CloudSync production security/mTLS suites or any broad
component/release campaign. Historical P0 `product_status=PARTIAL` and Hub
migration assertion FAIL remain existing release blockers.

**Historical evidence archive:** The old S3 build evidence is classified
`ARCHIVE_SAFE`. Its manifest and source/image/profile bindings verified before
movement. Four files retain their original hashes and restrictive modes under
`/home/udaybhan/projects/_artifacts/Ghar_sajag/GS68/20261016_M9cHfJ/`. The
old path
`/home/udaybhan/projects/gs68_hil_build_evidence_20261016_M9cHfJ` is a
compatibility symlink to that directory. The image is bound to old source
`c527f98c53916bfa6079a516b610f15fc83ffc1b` and remains historical evidence; it
was not superseded or deleted.

The existing integration worktree is retained. Its untracked
`managed_components/` and ignored generated/test artifacts were preserved. The
active CloudSync development worktree and canonical/C8 worktree were not
modified.
