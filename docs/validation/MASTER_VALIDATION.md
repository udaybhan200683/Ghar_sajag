# Master automated validation and regression framework

**Baseline inspected:** `0eb1324c27ce3d6a2464627c6057b0cc68943c60`
**Validation branch:** `feature/hw-m1-4-regression-framework`
**Product tree:** `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`
**Scope:** current implemented behavior only; no HW-M1.4C low-power, future
aggregation, chronology redesign, retry redesign, deep sleep, BLE, or routine
learning was implemented by this framework.

This is the authoritative validation entry point. The machine-readable feature
mapping is [MASTER_TRACEABILITY.csv](MASTER_TRACEABILITY.csv). Historical
qualification evidence remains historical; automated regression does not
rewrite or upgrade physical qualification.

## Completion rule

**NO FUTURE FEATURE IS COMPLETE UNTIL ITS POSITIVE, NEGATIVE, BOUNDARY,
FAULT/RECOVERY AND APPLICABLE PERFORMANCE/REGRESSION TESTS ARE ADDED AND ALL
MANDATORY GATES PASS.**

Feature work must add or update a traceability row in the same change. A row
may be `COVERED`, `PARTIAL`, `MISSING_PRODUCT_FEATURE`, or
`HIL_ONLY_PHYSICAL`. Every `PARTIAL` row names its exact residue;
`MISSING_PRODUCT_FEATURE` is behavior that does not exist and must not be
faked by validation. None of the latter three statuses is a release claim.

## Architecture and layers

The host runtime harness compiles the production `QualifiedInput`,
`NodeRuntime`, `NodeRadio`, `NodeStore`, data-plane codecs, `HubRuntime`,
`IngestQueue`, `HubJournal`, coverage/rules, and security policy. Its
`VirtualClock` and `RuntimePair` substitute only time and transport. There is
no second node/hub algorithm. Exact retry time, identity, queue admission,
dedupe, ACK class, retirement, and state changes are decisions of production
code.

| Layer | Repository realization | Hardware |
|---|---|---:|
| L0 pure unit | C++ checks, Python `unittest`, Node test runner | No |
| L1 component/state machine | sensing, storage, radio, rules, codec tests | No |
| L2 Node+Hub simulation | `master_validation` production-runtime harness | No |
| L3 functional system simulation | canonical 92-scenario catalog, dummy streams, HTTP lab | No |
| L4 backend/API/PWA integration | Python API/application/bridge suites | No |
| L5 browser | every Playwright spec, desktop and Pixel 7 projects | No |
| L6 quality gates | ASan/UBSan, trace build, contracts, coverage manifest | No |
| L7 stress/stability | master stress/soak and existing stress profiles | No |
| L8 target HIL | fail-closed `tools/hil/nightly.py` adapter entry point | Yes |
| L9 physical qualification | immutable milestone evidence: RF, PIR optics, power/electrical | Yes |

Virtual time is an explicit monotonic millisecond value. The master cases jump
through 200 ms, retry boundaries, 60 seconds, 5 minutes, and six logical hours
without sleeping. Synthetic LOW/HIGH/LOW input uses production
`QualifiedInput`; accepted events enter production `NodeRuntime`.

`RuntimePair::attempt` supports exact-attempt MAC success/failure, packet loss,
Hub unavailable, ACK loss, duplicate packet and duplicate ACK. Hub restart is
performed by constructing a new production `HubRuntime` and re-establishing
the explicitly configured peer. The seed for compound deterministic work is
`23063` and is present in JSON and console results.

## Existing-suite inventory at the inspected baseline

Counts below were discovered from the current branch, not copied from old
evidence. “Release” describes the pre-framework `release-gate-final` behavior.

| Suite | Exact command | Framework/layer | Current count | Deterministic | HW | Isolation/reset | Result format | Release | Nightly/stress, overlap and important gap |
|---|---|---|---:|---:|---:|---|---|---:|---|
| Contracts | `python3 scripts/verify_contracts.py` | Python/L6 | contract assertions | Yes | No | read-only files | console/exit | Yes | overlaps API schema; no target wire proof |
| C++ host | `make cpp-test` | C++17/L0-L2 | 245 checks reported by HW gate | Yes | No | new process/objects | console/exit, log | Yes | broad firmware policies; old checks not individually selectable |
| Simulator | `make simulator` | C++17/L2 | one composed run | Yes | No | new process | console/exit | feature variants | overlaps C++ runtime |
| Scenario matrix | `make simulate-matrix` | Python/L3 | canonical transformations | Yes | No | fresh process | console/exit | via `verify` only | overlaps functional catalog |
| Python | `make python-test` | `unittest`/L0-L4 | 121 test methods | Yes except bounded perf budgets | No | temp/in-memory DB by suite | verbose console/exit | Yes | backend, pair/gate, logging, Playwright runner; coverage is assertion-oriented |
| JavaScript | `make app-test` | `node --test`/L0-L4 | 17 tests | Yes | No | new Node process | TAP/exit | Yes | PWA logic; not browser rendering |
| Product variants | `make product-test PRODUCT=base`; `... PRODUCT=ai` | C++17/L0 | one executable each | Yes | No | rebuild/process | console/exit | Yes | build flags only |
| Feature variants | four `make simulator TRACE_FLAGS=...` invocations in `release_gate.py` | C++17/L2 | 4 builds/runs | Yes | No | `make clean` each | per-stage logs | Yes | compile-time combinations |
| Dummy streams | `python3 tools/validation/run_dummy_sensor_streams.py` | Python/L3 | 5 JSON streams | Yes | No | lab build/new process | console/exit | Yes | downstream behavior, not radio |
| Functional catalog | `python3 tools/validation/run_functional_suite.py` | Python/L3 | 92 scenarios | Yes | No | scenario fixture reset | JSON/console | Yes | canonical catalog; metadata was not rich enough for firmware OR IDs |
| HTTP integration | `python3 tests/simulation_http_test.py` | Python/HTTP/L4 | script assertions | Yes | No | owned lab/in-memory state | console/exit | Yes | overlaps API and PWA bridge |
| PWA bridge/API/frontend | `python3 tests/pwa_bridge_test.py`; `pwa_68_api_test.py`; `pwa_68_frontend_test.py` | Python+Node/L4 | script assertions | Yes | No | owned process/temp state | console/exit | Yes | broad application bridge |
| Legacy browser simulation | `node tests/simulation_browser_test.cjs` | Playwright/L5 | one legacy flow | Yes | No | owned port 8765, memory DB | stage log | Yes | overlaps mandatory Playwright specs |
| Playwright | `python3 scripts/run_playwright_gate.py` | Playwright/L5 | 43 specs × 2 projects = 86 runs | Yes | No | owned port 8766/server/process group, memory DB | list+HTML+JSON, trace/screenshot/video on failure | Yes | desktop/mobile; workers=1, each spec independently runnable |
| Sanitizers | `make verify-sanitize` | ASan+UBSan/L6 | C++ host suite | Yes | No | clean rebuild | console/stage log | Yes | leak detector disabled for platform stability |
| Trace build | `make cpp-test TRACE_FLAGS=-DGS_ENABLE_TRACE=1` | C++/L6 | C++ host suite | Yes | No | rebuild/process | console/stage log | Yes | trace compile/runtime path |
| Performance small | `make performance-test` | Python/L7 | local PWA profile + SMALL stress | bounded/local | No | lab build/fresh state | JSON/console | Yes | stable local budgets only |
| Stress/concurrency/endurance | `make stress-test STRESS_PROFILE=MEDIUM`; `make concurrency-test`; `make endurance-test` | Python/L7 | profile-driven | seeded/bounded | No | fresh DB/process | JSON/console | No | MEDIUM/EXTENDED were not in final gate |
| HW fast/full gate | `make hw-validation-fast`; `make hw-release-gate` | Python+ESP-IDF/L6/L8 | staged checks | Yes | full build needs toolchain, not boards | build dirs/logs | No | full builds pair; physical stages manual |
| Pair build | `make hw-pair-build` | Python+ESP-IDF/L8-prep | one pair | Yes | no boards; ESP-IDF required | deletes generated build dirs; requires clean git | manifest/logs | No | hashes/version/dirty/embed checks |

### Exact `make release-gate-final` expansion

`release-gate-final` invokes `release-gate-browser-mandatory` then
`performance-test`. The former invokes `release-gate` and `playwright-gate`.
`release-gate.py` runs, in order: validation coverage, contracts, C++ unit,
all Python discovery, JavaScript, base product, AI product, four clean feature
variants, lab build, dummy streams, functional catalog, HTTP integration, PWA
bridge, PWA-68 API, PWA-68 frontend, sanitizers, trace build, and the legacy
browser flow. `playwright-gate` runs preflight and all 43 specs in both desktop
and mobile projects. Finally `performance-test` runs the local PWA profiler
and SMALL stress. Any mandatory command failure is non-zero.

## Implemented-function inventory

### C3/node

Implemented: debounced/retriggered `QualifiedInput`; NodeRuntime event
construction; boot session provider; monotonically allocated sequence;
bounded retained store and retry queue; four-slot non-motion reserve; explicit
`motion_drop`, `store_full`, and `priority_rejected`; one in-flight owner in the
target adapter; ESP-NOW encode/send and MAC callback accounting; durable versus
volatile application ACK; deterministic retry stages and 60-second terminal
backoff; NodeHealth codec/counters/liveness/breadcrumb/error/heap fields;
versioned configuration and service window; C3 FOTA begin/data/end/abort,
chunk/image CRC, sequence/session checks, OTA write/finalize/boot partition,
30-second maintenance timeout, pending-image validation, and restart.

Not implemented: persistent NodeRuntime retained/in-flight state across real
restart, deep-sleep retained state, signed-image verification in the wire FOTA
receiver, or target software motion-control endpoint. These are explicit gaps,
not simulated features. Receiver protocol and policy now live in the production
`fota_receiver::Receiver`; its `IOtaWriter` is implemented by ESP-IDF on target
and by a deterministic failure-injectable writer in host validation.

### Hub

Implemented: ESP-NOW receive queue; frame classification/decode/validation;
authorized node/session checks; owner-task event processing; HubJournal
same-identity dedupe; durable/rejected/discarded ACK generation; NodeHealth
receive/logging; C3 embedded-image FOTA sender with retry/ACK matching;
configuration; host cloud journal/outbox and backend/application bridge;
rules, coverage, activity and resident actions.

Not implemented in the target composition: Hub self-FOTA, durable target
journal/outbox across power loss, target Wi-Fi/backend vertical bridge, or
cross-Hub-restart persistent dedupe. Host/backend components exist separately;
the repository explicitly does not claim the target vertical slice complete.

### Paired build

Implemented by `scripts/build_hw_pair.py`: clean-tree refusal, fresh C3 and Hub
builds, embedded-node synchronization, byte/SHA/size equality, image-info
version checks, `-dirty` rejection, build-order freshness, pair manifest and
provenance. Wrong/stale pairs fail validation. ESP-IDF is required; hardware is
not.

### Backend/application/PWA

Implemented and tested: event/history API and persistence, household identity
and isolation, activity/event details, I am OK, Call Family, expected and
unexpected activity rules, missing morning/activity flows, door presentation,
settings/configuration, currently shipped battery analytics, notifications and
reports, PWA bridge, local/offline service-worker behavior, desktop/mobile
browser flows, performance budgets and concurrency/scale checkpoints. Future
chronology/episode redesign and personalized routine learning are not included.

## Offline resilience matrix

All `OR-001` through `OR-035` are L2 release-blocking master cases. Run one
with `./build/master_validation --id OR-011` or
`python3 tools/validation/master_validation.py --id OR-011`. They cover, in
the requested numeric order: online delivery; Hub loss; offline acceptance;
multiple events; retention; coherent store/retry state; first/subsequent/
periodic retry; MAC failure; ACK loss; MAC-success/no-ACK; duplicate packet;
duplicate ACK; same-session replay; Hub restart; restoration; no-node-reboot
recovery; backlog; durable retirement; final drain; prolonged outage; new
motion during drain; repeated cycles; six-hour virtual outage; deterministic
jitter; session; sequence; no simulated reset; qualified zero drop/full/
priority rejection; NodeHealth; resource-bounded recovery cycles; and the
physically qualified 28-motion/reserve/drain invariants.

The host suite does not claim RF propagation, target heap stability, actual
reset reason, or power behavior.

## FOTA and maintenance matrix

| Area | Simulation | Pair/build | Target HIL | Status/reason |
|---|---|---|---|---|
| packet/chunk size and CRC | `FOTA-PROTOCOL-001` | compile/static assertions | physical transfer | COVERED for shared protocol |
| target/version/signature policy component | `FOTA-POLICY-001` | image version checks | target image observation | COVERED component; receiver does not consume manifest policy |
| standalone/embedded equality, size, SHA, version, dirty/stale | Python pair tests | `make hw-pair-build` | hashes recorded by adapter | COVERED |
| begin/data/end sequence, duplicate/out-of-order chunk, bad session/CRC/size | `FOTA-HOST-001..010` executes production receiver | target build | connected transfer | COVERED software policy |
| writer begin/write/end/set-boot failures and false-success prevention | `FOTA-HOST-014..019` | ESP-IDF adapter compile | physical flash faults | COVERED decisions; actual flash is target-specific |
| inactivity / Hub disappearance / recovery / maintenance exit | `FOTA-HOST-011..013`, `018` | target build | connected timing | COVERED software lease; target scheduling remains PARTIAL |
| pending validation, actual reboot/new version and bootloader rollback | restart request only | paired version | connected target | HIL_ONLY_PHYSICAL/target-specific |
| Hub self-update | none | none | none | MISSING_PRODUCT_FEATURE: future Hub update milestone |
| repeated valid receiver cycles | `FOTA-HOST-020` models reboot-created receiver cycles | pair artifacts | connected A→B→C | COVERED policy; real cycles remain target-specific |
| retained event and pending ACK around maintenance | `FOTA-HOST-021..022` with production `NodeRuntime` | target build | connected target | COVERED for current in-memory semantics; target scheduling remains PARTIAL |

The host suite does not reproduce the algorithm: host and target compile the
same production receiver source. Only `IOtaWriter` and callbacks differ.
ESP-IDF owns partitions, writes, boot selection, ACK delivery and restart; the
host fake records calls and injects deterministic failures.

## Restart, storage, protocol, smoke, stress and stability

| Matrix | Automated evidence | Remaining boundary |
|---|---|---|
| C3 smoke | `C3-SMOKE-001` | target boot/radio/heap HIL |
| Hub smoke | `HUB-SMOKE-001` | target Wi-Fi/backend absent |
| System smoke | `SYSTEM-SMOKE-001` | real RF/PIR L9 |
| Hub restart with in-flight node event | `OR-016`, `RESTART-001` | target reset HIL |
| C3 restart/no pending | session-provider legacy tests | target boot HIL |
| C3 restart with retained/in-flight | none | MISSING_PRODUCT_FEATURE: NodeRuntime store is in-memory; future persistence milestone |
| both restart / restart during FOTA | receiver failure/recovery covered | actual target reset/flash remains target-specific |
| queue empty/1/near-full/full/overflow/drain/refill | legacy C++ plus `QUEUE-BOUNDARY-001`, OR cases | target NVS persistence absent |
| codec min/max/truncated/version/type/value/flags/trailing/ACK/health | legacy C++ plus `PROTO-ROBUST-001` | fuzzing PARTIAL; no new platform introduced |
| C3 stress | `C3-STRESS-001` | target heap/task metrics HIL |
| Hub stress | `HUB-STRESS-001` | target radio/backend concurrency HIL |
| deterministic chaos | `SYSTEM-STRESS-001`, seed 23063 | target FOTA leg remains connected-target work |
| stability/soak | `C3-STABILITY-001`, `HUB-STABILITY-001`, `SYSTEM-SOAK-001` | host-visible state only; target duration configurable |

Host resource assertions cover queue/journal cardinality, store/retry equality,
identity, retirement, eventual drain, and progressive retained growth. They do
not convert a heap low-watermark into a leak claim. Host throughput/performance
remains in the existing controlled profiler/stress tools; no C3 CPU, battery,
RF, or electrical inference is made.

`make validation-coverage` uses GCC `--coverage` and the installed LCOV tools.
It runs the legacy C++ suite, all 49 master runtime cases, and all 22 production
FOTA receiver cases, then restricts results to `firmware/` and `shared/`.
Artifacts are `evidence/coverage/coverage.info`, `summary.json`, `summary.txt`,
and `html/index.html`. Line and branch coverage are visible without a global
threshold. The summary names uncovered locations in NodeRuntime, retry,
sensing, codec, HubRuntime and FOTA policy, plus target-only exclusions.

## Manual/HIL to automated regression mapping

| Historical action | Automated simulation | Automated target HIL | Physical-only residue |
|---|---|---|---|
| move in front of PIR | `QualifiedInput` LOW/HIGH/debounce → NodeRuntime | future adapter software-visible motion | PIR optical/thermal sensitivity and GPIO waveform |
| unplug Hub | `set_hub_online(false)` | logical radio suppression via adapter | real power switching requires safe controller |
| restore Hub | `set_hub_online(true)` / new HubRuntime | adapter recovery | electrical boot transient |
| TX/MAC failure | exact `DeliveryFault.mac_success=false` | target radio fault seam | RF propagation |
| missing application ACK | `ack_lost=true` | target ACK suppression | RF cause |
| wait 60 seconds / long outage | VirtualClock advance | wall time or target control | none for policy; oscillator behavior remains physical |
| repeat/duplicate packet | `duplicate_packet=true` | target replay injection | RF collision behavior |
| Hub reboot while C3 alive | reconstruct production HubRuntime | target restart command | uncontrolled mains switching excluded |
| FOTA transfer/reboot/post-motion | protocol/policy plus normal runtime tests | connected target adapter | flash/boot/rollback is target-only |
| 19 h 54 min endurance invariants | OR-034/035 and virtual soak | configurable `HIL_SOAK_MINUTES` | battery discharge/current remains L9 |

## Commands and independence

From the product directory:

```sh
make master-validation
make fota-host-test
make validation-coverage
./build/master_validation --id OR-011
./build/master_validation --suite OFFLINE_RESILIENCE
make master-validation-self-test
make validation-nightly
make validation-nightly HIL=1 HIL_SOAK_MINUTES=480
```

For MAC-based HIL discovery, set `HIL_AUTO_DISCOVER=1` and supply the qualified
Hub/C3 station MACs in `HIL_EXPECTED_HUB_ID` and `HIL_EXPECTED_C3_ID`.

Every C++ master TC constructs fresh runtime/storage/clock/transport fixtures.
It has no wall-clock or previous-test dependency. Existing backend/browser
suites retain their in-memory/temp database and owned-server isolation.
Playwright specs can be run by title/project with normal Playwright CLI; the
gate owns its server lifecycle and records traces/screenshots/video only on
failure.

`validation-nightly` is the complete hardware-free overnight gate. It is
fail-fast in this order: all 49 master cases (including OR-001..035 and the
three stability/soak cases), the 22-case FOTA host suite, negative self-test,
MEDIUM stress, concurrency/isolation, authoritative `release-gate-final`,
EXTENDED 100,000-event endurance, and host line/branch coverage. The parent
marks master/FOTA already passed inside the release gate and suppresses its
superseded SMALL stress, so expensive suites have one campaign owner. Coverage
necessarily replays instrumented C++ cases as measurement. Use
`--continue-on-failure` only for diagnostics.

HIL is disabled by default. With `HIL=1`, `HIL_EXPECTED_HUB_ID` and
`HIL_EXPECTED_C3_ID` are qualified station MACs. Configure
`HIL_HUB_PORT`/`HIL_C3_PORT`, or set `HIL_AUTO_DISCOVER=1`. The repository
ESP-IDF adapter performs MAC discovery, clean paired build, commit/version/SHA
provenance, explicit-port flash, serial capture, readiness detection and
NodeHealth collection. `HIL_ADAPTER_COMMAND` may override it. Missing hardware,
configuration or control seams produce `BLOCKED` and non-zero. Exact remaining
seams are logical Hub receive disable, synthetic motion, deterministic
transport fault, software FOTA trigger, deterministic software restart/state
query, and final target-state query. The framework never erases NVS,
discharges a battery, or performs uncontrolled physical power switching.

Execution modes are distinct: simulation nightly needs no hardware; HIL
nightly requires configured connected Hub+C3 and blocks when absent; milestone
physical qualification owns RF/electrical/PIR/battery/brownout and electrical
power-interruption evidence. A relay is not required by this framework.

## Reports and triage

Master results: `evidence/master_validation/results.json`, `junit.xml`, and
`runner.log`. Nightly results: `evidence/validation_nightly/summary.json`,
`summary.md`, and numbered stage logs. Browser HTML/JSON and failure media stay
under `evidence/`. Pair builds emit `build/hw_pair/provenance.json`. HIL emits
`evidence/hil_nightly/summary.json` plus adapter log.

For a failure: identify the TC and feature row; rerun the exact ID; inspect its
stage/runner log; reproduce without failure injection; decide whether the
failure is product, test, environment, or explicit HIL block; fix without
weakening the assertion; rerun the TC, parent suite, master, and the applicable
gate. Preserve material target evidence under the existing evidence policy.

The negative self-test sets `GS_VALIDATION_INJECT_FAILURE=OR-001` only in a
child process and proves that the specific TC and parent command are non-zero.
It then exits PASS only when detection worked. No source is modified and the
normal suite is rerun green.

## Adding validation

Add an ID-addressable case to the narrowest existing framework, map it in
`MASTER_TRACEABILITY.csv`, include positive/negative/boundary/fault/recovery
and stable performance cases that apply, and assign release/nightly/HIL
membership. Reuse the canonical scenario catalog for product scenarios. Add a
new framework only when the existing production seam cannot express the case.
If hardware or unimplemented persistence prevents automation, record the exact
gap and reason; never mark it PASS or implement a future feature to fill it.

## Clean post-commit pair qualification

Do not bypass the pair builder's clean-tree safeguard. This closure pass is
intentionally uncommitted, so neither command below is claimed here. After the
validation-framework change is reviewed and committed, with no tracked or
untracked source changes remaining, run from the product directory:

```sh
git status --short
make hw-pair-build
make hw-release-gate
```

The first command must print nothing. `hw-pair-build` then performs fresh C3
and Hub builds, synchronizes the embedded C3 image, validates commit versions,
byte equality and SHA-256 values, and writes pair provenance. Only after that
PASS should `hw-release-gate` consume the clean pair and run its full static,
target-build, size and integrity checks. Connected HIL remains a separate gate.

## Physical-only boundary

L9 retains actual RF range/RSSI accuracy, current, battery discharge,
brownout voltage, PIR optical/thermal sensitivity, converter/cutoff/thermal
behavior, and GPIO electrical waveform. Target flash, boot, ESP-IDF restart,
FOTA and radio behavior belong in L8 whenever configured connected hardware
and a safe adapter are available.
