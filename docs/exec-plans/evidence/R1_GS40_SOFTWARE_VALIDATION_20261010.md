# GS-40 software implementation evidence — 2026-10-10

## Authority and provenance

GS-40 description/latest comment 10359 and user approval, LOCKED GS-D031.
Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; starting local/remote checkpoint
`913b1dedb483ca63aff7244dbbd224053206c7f2`. Approved policy documentation was
committed before implementation as `821da80b25dc11c8a01252333abc9734036fc66b`.
Context version 2026-10-10.001. GS-112/GS-150 historical evidence is preserved.
No hardware actions, physical current measurements or commercial qualification.

## Implementation and safety

Validated schema-1 JSON is the sole adjustable health timing input. Its generated
typed representation and fingerprint are embedded; the complete JSON is packaged
in the firmware bundle. Startup does not require a filesystem JSON file.
Default 300 seconds; internal new-policy lease 3 × interval + 10 = 910 seconds.
Range 15–3600 reuses lifecycle validation; not a physically qualified range.
The unchanged 430-second authenticated-contact recovery may precede long health
intervals. Strict build/service validation and generated constexpr startup policy
prevent invalid/missing JSON from producing health-disabled firmware. Both IDF
CMake projects and the host build consume the generated representation/config SHA.
No runtime flash configuration writes, partitions or storage migrations.

Authenticated event contact refreshes Hub monotonic liveness; matching validated
application ACK or NodeHealthAck refreshes the C3 cadence. MAC success does not.
Due event diagnostics reuse the existing optional power carrier; oversize telemetry
is omitted so event admission/delivery is not blocked. Full fault/health diagnostics
retain the existing standalone format. Standalone health is due only when needed;
pending recovery/application work has priority. Same day/night algorithm.

Trusted physical identity deployment profiles select configured policy, legacy60
(60/190), legacy120 (actual preceding 120/310), or unknown. New configured120
uses370, not legacy310. No unauthenticated packet field selects the lease. Profile
maps are RAM startup policy, reconstructed on authenticated authorization/rejoin;
checkpoint/wire schemas are unchanged. Unmapped Nodes cannot prove online coverage.
Hub-first mapped staged updates and final-image verification are prerequisites;
the known protected pair mapping is a candidate, not evidence of an upgrade.

Backend leases are selected per device from the same trusted configuration.
Actual received-contact evidence, never PWA rendering or retained occurrence time,
refreshes freshness. Unchanged renders do not write health records. Host PWA shows
unmapped availability as unknown. Hub cloud lease190, Internet state and resident
inactivity remain distinct. The secure target's documented trusted-epoch and
production backend authentication/completion limitations remain open; no wall clock
or production cloud contract is invented. Real-target caregiver visibility remains
GS-40 acceptance.

GS-150's confirmed-outage sleep, 10-second best-effort receive budget, retry/rejoin,
30-second sleep cap, GPIO4/held-HIGH safeguards, first-event and critical priority,
EventKeys/timestamps, durable replay/ACK retirement, 32-event limit and signed FOTA
remain unchanged. No C9–C12, journal expansion or GS-128 runtime framework.

## Test construction and discovered baseline issues

Focused matrix covers JSON types/duplicates/missing/version/range/overflow/profiles,
changed600 generation and compiled1810 policy, startup/build integration, packaging
fingerprint/C3-in-Hub equivalence, authenticated contact/deadline overlap, failed or
missing ACK, piggyback, reboots, mixed leases/unknowns, silent expiry910/911, Internet
loss, coverage faults, critical keys and durable duplicate replay. GS-150's existing
19 paired workloads and security/storage/FOTA suites supply unchanged behavior tests.

Initial commands/results were retained in `/var/tmp/gs40-*.log` during execution:

- BAT-C8 old target/source assertions: exit2; updated to generated300 production
  interval while retaining explicit raw-HIL60 and historical120 component fixtures.
- Expanded `validation-fast`: exit2 missing `DurableEventOutbox::replay_fence_matches`
  linkage. Six older host recipes lacked durable_event_outbox.cpp, present at starting
  HEAD (symbol introduced6462a83). TEST_INFRASTRUCTURE_DEFECT; explicit linkage only.
- Next run: exit2 unsupported25-Node fixture. Existing ten-slot enrollment protocol
  e1ef65e is present at start; release hardware scope retains six. VALID_TEST_EXPECTATION_MISMATCH:
  keep supported1/4/10 tests; explicitly SKIP25 stress with capacity rejection verified.
  No cap expansion or claimed25-Node PASS. Baseline execution unverified.
- Next run: exit2 fresh-install/recovery fixture omitted selected report replay-fence
  reconciliation and enrollment evidence now required by the existing security guard.
  Starting source contains both omission/guard. TEST_INFRASTRUCTURE_DEFECT: exercise
  actual authenticated fence codec with volatile host storage, bind before admission,
  preserve durable-before-ACK/reboot/dedup/fault assertions. No production guard change.
- PWA aggregate: exit2 inactivity fixture assumed silent coverage expired before300s.
  VALID_TEST_EXPECTATION_MISMATCH under GS-D031: inactivity due1200s, silent advance1211s
  exceeds910 lease; retain zero false-inactivity assertion. Silent910/911 independently
  checked. This changes fixture timing, not production inactivity policy.
- `validation-fast` exit2: `hub-durable-storage-host-test` hard codec cap still5777,
  actual snapshot6100 introduced6462a83 and present at start. TEST_INFRASTRUCTURE_DEFECT:
  retain exact current6100 cap assertion; label classic migration budget historical,
  not S3 capacity qualification. Baseline execution unverified; no storage source change.
- Provider host fixture expected Ready owner alone to permit ingress, without
  the required persistent journal. TEST_INFRASTRUCTURE_DEFECT: attach the real
  bounded128 journal adapter, keep unready/erase/corruption gates, and assert
  missing enrollment cannot yield Durable ACK. Corrected individual gate exit0.
- Extended host aggregate still fails legacy migration `clean migration commits`
  at tests/cpp/hub_journal_migration_validation.cpp:194. That test and production
  durable_journal_slot_store.cpp are unchanged from913b1de; baseline execution
  unverified. Classification UNRESOLVED / INVESTIGATE_ONLY under deferred legacy
  storage work. Expected historical migration commit, actual fail-closed false.
  No GS-40 change uses this migration path. Fixing storage ownership/migration
  without its approved contract would exceed this task. Preserve this failure;
  do not broadly skip it or claim `validation-fast` PASS. Recommend investigation
  “Reconcile legacy journal migration host gate with current ownership contract”,
  storage owner/GS-126 context; no new issue/status/dependency created.
- Packaging old embedded C3: exit1 intentional rejection; matched final C3 asset passes.

## Deterministic efficiency

Before = actual preceding120/310 policy with GS-150 already active. After =300/910.
Identical event/ACK/outage workloads. See [full CSV](R1_GS40_SOFTWARE_METRICS_20261010.csv).
20 ms owner poll, same authoritative sleep policy/30s cap, 40ms ordinary modeled ACK,
source retry/rejoin/receive deadlines; GPIO model uses existing debounce/aggregation.
Awake/listening counters are logical modeled active duration, not current or actual
radio residency. OS/RF/flash transition energy is not measured. TX latency is from
successful durable admission, excluding PIR debounce150ms/poll and physical RF time.

| Workload | Standalone health before→after | Owner loops before→after | Modeled awake/listen ms before→after | Event TX/retries (same) |
|---|---:|---:|---:|---:|
| Quiet30m |15→6|654→294|11880→4680|0/0|
| Night8h |240→96|10554→4794|191880→76680|0/0|
| Frequent day |12→0|19656→19496|389540→386340|11/0|
| Sporadic day |12→4|1100→765|20700→14000|4/0|
| Confirmed outage |0→0|3189→3189|63540→63540|8/7|
| Hub recovery |1→0|1213→1173|23940→23140|11/3|
| Lost ACK |2→1|117→67|2100→1100|2/1|
| Delayed ACK |2→1|142→102|2600→1800|3/2|

Quiet health transmissions reduce60%; timer wakes remain60/30m and960/8h because
30-second safeguards remain. Frequent event contacts11 and sporadic4 defer health.
Recovered backlog admits/retires/effects8/8/8, durable writes16 in both. Hub-return
contact14790ms/drain15110ms unchanged, no PIR required. Ordinary event ACK40ms,
lostACK300ms/delayedACK1000ms in both. Outage retains1 durable event; no retirement
or effect falsely claimed. Every paired scenario has equal event TX/retries,
admission/retirement/durable writes/logical effects and zero false-offline samples.
Configured silent Node is online through910s and offline after910s, sampled by the
existing owner; long detection delay is the approved policy, not resident inactivity.
Mixed-profile190/310/910/1810 boundaries are tested. No mA, mAh or endurance claim.

## Validation command record

Actual completed command records (application root unless noted):

| Command | Exit | Result / count |
|---|---:|---|
| `make cpp-test` |0|PASS 1,479 checks; repeated by release gate|
| `make gs40-host-test` |0|PASS 1,320 checks / eight paired workloads|
| `make gs40-config-test` |0|PASS 15 tests including compiled changed JSON and backend/PWA profiles|
| `make gs150-host-test` |0|PASS 1,481 checks / 19 paired workloads|
| `make -j2 python-test pwa-e2e-test app-test contracts` |0|PASS 361 Python run (one historical skip), bridge12, API92/frontend92 scenarios, JS17, contracts and P2-D bridge|
| `make -j2 hub-fresh-install-host-test hub-recovery-scheduling-host-test pwa-68-api-test manual-test-plan` |0|PASS authenticated genesis/report/reboot/dedup/fault;128 records/256 handoffs; regenerated plan/API cases|
| `make hub-durable-storage-host-test` |0|PASS exact codec bounds and historical budget fixture|
| `make hub-durable-provider-host-test` |0|PASS corrected persistent owner/journal gating and failure cases|
| `npm ci --ignore-scripts` |0|PASS locked developer test dependencies; package/lock unchanged|

Sanitizers: both commands exit0, no ASan/UBSan findings; leak detection disabled.

```sh
ASAN_OPTIONS=detect_leaks=0 make -j2 cpp-test \
 CPP_OBJECT_DIR=/var/tmp/gs40-asan-objects \
 CXXFLAGS='-std=c++17 -O1 -g1 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'
ASAN_OPTIONS=detect_leaks=0 make gs40-host-test \
 CPP_OBJECT_DIR=/var/tmp/gs40-asan-objects \
 CXXFLAGS='-std=c++17 -O1 -g1 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'
```

C++1,479 and GS-40 model1,320 checks passed under instrumentation. These do not
measure physical current or prove hardware timing.

Clean ESP-IDF6.0.3 builds (new task build directories), followed by final dependent
rebuilds after generated policy/paired asset stabilization: both commands exit0.

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py -C firmware/node/target/esp32c3/idf -B /var/tmp/gs40-c3-build \
 -D SDKCONFIG=/var/tmp/gs40-c3-sdkconfig -D IDF_TARGET=esp32c3 build size
idf.py -C firmware/hub/target/esp32s3/idf -B /var/tmp/gs40-s3-build \
 -D SDKCONFIG=/var/tmp/gs40-s3-sdkconfig -D IDF_TARGET=esp32s3 \
 -D GS_NODE_FIRMWARE_ASSET=/var/tmp/gs40-assets/node_firmware.bin build size
python3 scripts/package_node_health_firmware.py \
 --c3-build /var/tmp/gs40-c3-build --s3-build /var/tmp/gs40-s3-build
```

Packaging exit0; bundle `build/gs40_bundle` contains exact paired binaries, existing
flash offsets, JSON/schema and manifest. It never accesses boards. C3 app934,192
bytes, existing0x1e0000 slot,52% free; S3 app1,868,800 bytes, existing0x400000 slot,
55% free. No partition changes. Binary padding explains size-tool differences.

- Config SHA256: `fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862`.
- C3 SHA256: `86a8a4e201f4334709b5ae89bb6b2f294276bb0b76e6a9a2e68f147b7a296cdd`.
- S3 SHA256: `7e84902c419faf5e44ad6766f3638866b80145c2d86233e7be8ebae65a714204`.

Context preflight and `git diff --check` exit0. Documentation relative-link
validation reuses the scoped inline check in the GS-150 evidence (file selection
changed to GS-40 evidence/config README): exit0,44 links initially /56 after final work-state cross-links. Anchors not
checked. Missing `tools/context/check_markdown_links.py` was not recreated.

Final expanded/browser command records are appended after execution. Build artifacts were compiled
from the implementation source subsequently committed with this evidence, using
governance HEAD plus tracked implementation edits; binary application Git metadata
is not claimed to equal the later documentation delivery commit.

## Physical and delivery handoff

No board was flashed/reset/erased/re-enrolled; original authenticated pair and
historical pending records untouched. GS-40 remains In Progress for real-target
NodeHealth and caregiver offline-visibility acceptance. Earlier immediate GS-114
planning is superseded by user comment10366: next GS-116, then GS-130, then GS-114.
GS-114 P1–P9 requires separately authorized fixture preparation and matched GS-40/GS-150
candidate images/profile map; reuse traceable overlapping evidence only. GS-149
power measurement waits its dependencies (GS-144/GS-51); GS-146 full physical/HIL
closure retains its existing gates. GS-128/GS-126 OnHold unchanged.

### Expanded gate final outcome

- `make -k -j2 validation-fast`: exit2 / FAIL; only remaining actual target failure
  is `hub-journal-migration-host-test` (`clean migration commits`, child exit1).
  All other prerequisite targets executed and passed, with25 stress explicitly
  SKIPPED. The quick release recipe is not executed when this prerequisite fails;
  it is separately run and reported, never substituted for aggregate PASS.
- `make -k -j2 validation-fast hub-runtime-checkpoint-host-test
  s3-durable-outbox-host-test hub-segmented-outbox-runtime-host-test`: exit2 / FAIL
  during earlier provider fixture correction; current S3 extra gates themselves
  PASS. Outbox6,556 records/1,110,125 event bytes,5,472 completion records/524,205
  bytes/six scenarios; checkpoint replay/crash/identity and authenticated segmented
  Hub runtime/deduplication PASS. Provider individual/final prerequisite now PASS.
- `python3 tools/validation/release_gate.py --quick`: exit0 / PASS16 mandatory
  stages, master49/49, FOTA34/34. Initial browser MANUAL_REQUIRED (dependency
  unavailable); locked npm dependencies were then installed without changing
  package/lock files and browser gates run separately below.
- Historical Python skip: classic ESP32 G01 NVS reserve model under GS-D030;
  S3 commercial capacity/reserve physical acceptance remains open.

Software source is implemented; extended all-green closure remains partial due
the unchanged legacy migration assertion. This is not commercial release or
physical qualification. No migration fix, broad skip or relaxed assertion was
used to hide the failure.

### Browser availability resolution

`npm ci --ignore-scripts` exit0 installed the checked-in lockfile dependencies
into ignored node_modules; package.json/package-lock.json unchanged. Existing
cached Chromium matched the locked Playwright revision. No system package or
hardware operations were needed.

`python3 tools/validation/release_gate.py --quick --require-browser`: exit0 / PASS
17 stages, including the actual local Chromium smoke (sensor, caregiver lifecycle,
390px layout, visible validation suite, no page errors). No MANUAL_REQUIRED browser
stage remains in this final quick run. Separate desktop/mobile comprehensive
Playwright result is recorded below when complete. This is a quick software gate;
no physical or full commercial release acceptance is inferred.

Full Playwright initially also exposed the historical191-second lease fixture at
phase1_ui_contract.spec.ts:201 (desktop/mobile). Expected UNKNOWN at191, actual
correctly COVERED with configured910 lease. VALID_TEST_EXPECTATION_MISMATCH under
GS-D031. The fixture now reads the effective policy, asserts300/910, verifies
coverage at the inclusive910 boundary, then advances1 second and preserves every
Home concern, care-event, recovery and chronology assertion. Full suite is rerun;
individual success is not substituted for aggregate PASS.

Initial full `make playwright-gate`: exit2 / FAIL,84 passed/2 failed (desktop
and mobile lease fixture),86 executed. Corrected fixture strengthens inclusive
boundary coverage and keeps all concern/recovery assertions; corrected full
aggregate is executed again. Initial contexts/traces are preserved under
`/var/tmp/gs40-browser-lease-*-error.md` / `*-trace.zip` before runner output refresh.

The first strengthened browser rerun found fixture reset-to-PASS advances60s
after Kitchen contact. Adding910 to render time therefore overshot the contact
lease. Second attempt was deliberately interrupted after this proven fixture
failure: Make exit2 / child130,30 passed,1 failed,1 interrupted,54 not run. Correct
boundary now derives `last_seen_at + effective_timeout - simulation.now`; no
production change or weakened expectation. Focused desktop/mobile and then full
aggregate reruns follow. This also tests that rendering cannot renew contact.

Focused corrected boundary: existing `scripts/run_playwright_gate.py` readiness,
port ownership and process cleanup helpers start an isolated in-memory lab;
`npx playwright test tests/playwright/phase1_ui_contract.spec.ts --grep
'required-node lease expiry'` exit0,2/2 desktop/mobile PASS. No persistent helper
script or test suppression was added; final `make playwright-gate` runs all86
again.

Final `make playwright-gate`: **exit0 / PASS86 of86**, desktop/mobile,12.8 minutes.
No test skipped or removed. The correct last-received-contact boundary fixture
passed in both browser profiles. Final full aggregate success supersedes the
earlier browser failures; it does not substitute for the still-failing expanded
validation-fast aggregate or physical acceptance.

## Follow-on policy reconciliation and traceability

GS-40 comment10366 (2026-10-10), received during this execution, supersedes only
the earlier immediate-GS-114 planning phrase. The new approved order is **GS-116
→ GS-130 → GS-114**. The new top sections of GS-116/GS-130 were read. Their
permanent engineering policy starts with the next session; its repository
AGENTS/master-policy implementation belongs to GS-116, not this configuration
change. No Jira workflow/rank/dependency was edited.

Review against that policy: changed Node, Hub, Node↔Hub and backend/PWA contracts
received new tests plus the recorded prior regressions, sanitizer runs and target
builds. GS-40's cheap deterministic model/configuration gates are permanently
registered in `validation-fast`; the Python configuration cases also run in full
Python discovery. **All-green affected-component closure is not asserted**:
the migration prerequisite fails, exhaustive previous-feature inventory is not
yet audited, and existing `release-gate-final` does not automatically depend on
the expanded `validation-fast` prerequisites. Quick release/browser PASS is not
proof that the final release gate dominates those tests. GS-116 owns runner,
failure-propagation and component-suite registration; GS-130 owns exhaustive
feature/test/physical traceability. No third generic ticket was created.

This is scoped GS-40 evidence, not a replacement for the canonical master matrix:

| Requirement / owner | Executed test identity | Gate registration / current result | Remaining proof |
|---|---|---|---|
| GS-D031 JSON / NODE_HUB | `test_default_and_derived_examples`, `test_invalid_fields`, `test_corrupt_missing_duplicate_json`, `test_json_changes_compiled_startup_policy`, `test_build_and_startup_share_input`, packaging rejection | `gs40-config-test`, full Python; fast registered / PASS15 | GS-116 full-release registration; actual startup/image verification NOT_RUN |
| GS-D031 cadence/piggyback / NODE | `health_matrix`, quiet/night/frequent/sporadic paired workloads | `gs40-host-test`; fast registered / PASS1320 including contract matrix | Real 300-second quiet cadence and event suppression NOT_RUN |
| GS-D031 mixed leases / HUB, NODE_HUB | `health_matrix` 190/310/910/1810 and unknown identity | `gs40-host-test`; fast registered / PASS | Authenticated real mixed installation/profile proof NOT_RUN |
| GS-D031 received freshness / BACKEND,PWA | `test_backend_mixed_silent_nodes`, `test_received_contact_not_render_time_renews_freshness`, `test_silent_rf_expiry_boundary_and_automatic_health_return`, `test_internet_loss_does_not_expire_locally_healthy_nodes` | `gs40-config-test`, full Python / PASS; API/frontend scenarios and browser boundary separately executed | Production epoch/cloud integration and caregiver real-target visibility NOT_RUN |
| GS-150 / NODE,NODE_HUB | Existing 19 paired GS-150 workloads, BAT-C8, encrypted recovery/retirement/rejoin and secure-FOTA | Named host targets; fast registered / recorded PASS | Actual GPIO4/RF/radio restoration/long run/OTA physical proof NOT_RUN |
| Durable ownership/reboot / HUB | Fresh-install, recovery scheduling, journal persistence, retirement, checkpoint/outbox/segmented runtime gates | Named host gates / recorded PASS; registration completeness belongs GS-116/130 | Legacy migration assertion FAIL; physical storage/power-cut NOT_RUN |
| Caregiver coverage/chronology / BACKEND,PWA | API92/frontend92, bridge12, full desktop/mobile contract suite | Named API/PWA/Playwright and quick browser gates / recorded PASS | Real C3→S3→backend→PWA acceptance NOT_RUN |

Source implementation/profile: `e36bd88371449421420ec86995e82d3695a680d5`,
schema1/configured300/910, existing GS-150 10-second ACK policy. Physical status
for every row is NOT_RUN. Full inventory/gate architecture remains GS-116/130
work; product release approval is not claimed.

## Committed-source build and package refresh

After the implementation was committed, normally pushed and verified as
`e36bd88371449421420ec86995e82d3695a680d5`, the same clean task build directories
were reconfigured and rebuilt to refresh application Git metadata from that
committed source. Firmware modules did not change after the earlier clean builds.
Both commands exit0 / PASS:

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py -C firmware/node/target/esp32c3/idf -B /var/tmp/gs40-c3-build \
 -D SDKCONFIG=/var/tmp/gs40-c3-sdkconfig -D IDF_TARGET=esp32c3 reconfigure build size
cp /var/tmp/gs40-c3-build/gs_hw_m1_node.bin /var/tmp/gs40-assets/node_firmware.bin
idf.py -C firmware/hub/target/esp32s3/idf -B /var/tmp/gs40-s3-build \
 -D SDKCONFIG=/var/tmp/gs40-s3-sdkconfig -D IDF_TARGET=esp32s3 \
 -D GS_NODE_FIRMWARE_ASSET=/var/tmp/gs40-assets/node_firmware.bin reconfigure build size
python3 scripts/package_node_health_firmware.py \
 --c3-build /var/tmp/gs40-c3-build --s3-build /var/tmp/gs40-s3-build
```

Copy/package exit0. Both project metadata versions are `e36bd88`. Final package
was created before closeout Markdown edits: manifest source_head is full
implementation `e36bd88371449421420ec86995e82d3695a680d5`, tracked_source_dirty=false.
No later documentation-only commit is represented as the binary Git metadata.
Config fingerprint and exact C3-in-Hub membership validated again; partitions
and sizes unchanged. Final SHA256 values supersede the earlier metadata build:

| Artifact | Bytes | SHA256 |
|---|---:|---|
| C3 application |934192| `f7bae5675657411f524f50f1d8fc2235e222e7d12848f00983fd4b3ab2cb46bf` |
| S3 application |1868800| `3a43579ffe138ee2b7f08b2de42d3f60fba8821a2024da662c71d9f49c32073a` |
| Configuration |—| `fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862` |

Bundle remains ignored `build/gs40_bundle`, software-only unsigned development
packaging; no deployment/signature/physical qualification. Original ignored
Node asset is preserved. GS-114 qualification wake profile must be separately
built/hashed and authorized as documented in its test plan.

GS-40 design comment10360 and pushed-implementation comment10363 record their
actual milestones. GS-114 comment10368 records these final candidate artifacts
and the new GS-116→GS-130→GS-114 planning order without changing workflow, rank
or dependencies. Final GS-40 delivery comment follows documentation push and
remote verification. GS-40 stays In Progress.

Final closeout documentation validation: context preflight exit0/PASS,
`git diff --check` exit0/PASS after correcting one extra EOF blank line, and the
existing inline path check from the GS-150 evidence with GS-40 file selection
exit0/PASS21 relative-path links (anchors not checked). Final selection is
current `git diff --name-only` Markdown plus this evidence and config/README.md,
deduplicated before checking. No missing-script recreation or third-party
managed-components scan. Only work-state/evidence Markdown is staged for the
final closeout; source binaries and generated outputs remain excluded.
