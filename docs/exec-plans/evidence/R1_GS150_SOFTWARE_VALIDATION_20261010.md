# GS-150 C3 software implementation and validation — 2026-10-10

Classification: HOST_TESTED / SIMULATED / TARGET_COMPILED. PHYSICAL_TESTS=NOT_RUN.
This is dated evidence; the battery guide and R1_WORK_STATE remain the current
canonical design and handoff. No commercial or battery-life qualification.

## Provenance and scope

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`. Starting local/remote HEAD
`ff0f6f159890b86f26b998ca3d1218600ff34cc8`; prior firmware baseline `f245eeb`.
Global/repository AGENTS and mandatory preflight PASS, context 2026-10-09.001.
GS-150 latest Jira 10349 and GS-110/114/115/146/147 links/comments reconciled.
The subsequent user instruction explicitly authorizes safe best-effort missed
ACK handling or confirmed-outage-only sleep. Its approved scope resolves the
prior need for a guaranteed network ACK maximum. Source still supplies no such
maximum; no guarantee or arbitrary network expiry was introduced.

Only C3 sleep/receive ownership and its regression infrastructure changed.
Event admission, radio retry/rejoin timings, Hub durable processing, crypto,
wire frames, storage formats, 32-event limits and FOTA contracts are preserved.
S3 source/hardware, original paired C3 seven-record state and pre-existing
untracked S3 managed_components remain untouched.

## Alternatives and selection

| Alternative | Disposition | Safety, timing and cost |
|---|---|---|
| A: guaranteed ACK-arrival bound | Unsupported; unnecessary for selected policy | Source proves durable-before-ACK ordering, not bounded network delivery. 1 s local callback expiry never proves durable application acceptance. |
| B: general bounded listening | Rejected for connected/transient pending | An initial short-window model could repeatedly miss slow ACKs. Current reception stays continuous for connected pending and successful application MAC delivery. |
| C + narrow best-effort B in confirmed outage | IMPLEMENTED | Existing three-missed-attempt classification plus failed/ambiguous transport, 10 s receive budget, known future retry and all other safety predicates permit sleep with retained K. A late/missed response is recovered by the original scheduled same-key transmission. |

The application budget is `SessionRecoveryPolicy::active_contact_timeout_ms`
(10,000 ms, extracted without changing `active_expired` behavior). The current
negotiated protocol already permits replacing an unanswered application session
after three completed attempts and 10 s. Reusing that conservative budget is an
implementation receive opportunity, not a Hub timing SLA. MAC success holds
continuous pending reception beyond it; no repeated slow-ACK starvation on a
reachable peer. After timeout/failure with no usable response, retention and
scheduled replay remain mandatory. Eventual completion still needs eventual
usable authenticated communication; no guarantee under permanent RF or Hub
storage failure is claimed.

Auxiliary budget is 200 + maximum 100 ms existing retry jitter = 300 ms. Existing
retirement fragment callbacks inhibit, and unchanged 1 s/5 s retry deadlines
bound sleep. Security reception uses the full existing first rejoin retry
opportunity (1,500 ms + session jitter). Bootstrap remains awake. Active/idle
contact, fallback and ambiguity timers are now explicit sleep deadlines. The
10 s active session cutoff may invalidate old-session reception before a new
callback-relative budget expires, as it already did before this patch.

## Timeline and state ownership

| State/operation | Bound/transition | Sleep/retention |
|---|---|---|
| Admission K | Encrypted recovery commit before adapter can send | Failed/uncertain commit stops unsafe progress; no new write path |
| TX + callback | Local callback or existing 1,000 ms timeout | Awake; MAC success is never an app ACK |
| Application RX | Source-derived 10 s budget after completion; successful MAC retains continuous RX | ACK can be accepted at any awake time; budget does not expire K |
| Connected/transient pending | Existing continuous reception | Awake, original retry ladder |
| Confirmed-outage quiet | Budget ended, unsuccessful/ambiguous transport, future known retry | Pending and original timestamps persist; safe GPIO/timer sleep |
| Valid ACK | Current-session AEAD, correct ownership/direction/replay and exact key/class | Existing pending/retained mutation followed by durable retirement snapshot |
| Missed/late ACK | No Node completion | Same EventKey resealed under current session at unchanged retry; Hub durable dedupe returns another ACK |
| Rejoin | Original retry/fallback/ambiguity state machine | Protect initial receive opportunity; quiet backoff may sleep, no PIR needed |
| FOTA/control, persistence, critical work, unsafe GPIO/radio or expired/near deadline | Existing inhibitors | Fail awake; no energy-driven suppression |
| Light sleep | Earliest health/retry/retirement/episode/security deadline, 30 s cap, 500 ms margin/minimum | Existing radio stop/resume and powered GPIO4 path |
| Restore failure | Retry existing restoration; uncertain state inhibits TX/sleep | Continue PIR sampling and durable admission; no motion stall |

Same `gs_node_owner` owns the helper and authoritative `evaluate_light_sleep`.
Callbacks still only copy bounded queue work. Session/frame counters remain in
RAM across sleep. Partial ESP-NOW callback initialization is not advertised ready.
Offline C7 RAM summaries remain deferred, rather than being incorrectly marked
executable recovery work; actual gap/fault and unsettled persistence remain
inhibitors. No competing task/timer/power owner.

Source references (within product root):
- `firmware/node/components/power/power.hpp`: AckListeningWindow, sleep bounds,
  authoritative snapshot, RAM-only accumulated sleep residency.
- `firmware/node/components/power/power.cpp:107`: retained-delivery snapshot;
  `evaluate_light_sleep` includes retirement deadline and verified outage quiet.
- `firmware/node/components/power/session_recovery_policy.hpp:18`: unchanged
  active-contact timing made observable as a deadline.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp:695`: fail-awake sensing;
  1023/1063 local completion; 1110 session replacement; 1602/1609/1664 deadline
  and snapshot integration. Original ACK authentication/retirement path preserved.
- Existing `NodeRadio::record_transport_result`: 200/600/1800/10000/60000 ms
  with key jitter; existing `SessionRecoveryPolicy::retry_delay`: unchanged
  1500/3000/10000/20000/40000/60000 ms with session jitter.

## Regression coverage

New `tests/cpp/gs150_offline_sleep_validation.cpp` uses production power policy,
NodeRuntime/radio, QualifiedInput, encrypted NodeRecoveryRepository, mutual-proof
rejoin, runtime AEAD, and persistent HubRuntime/journal/reducer recovery.
Deterministic policy matrix covers active TX, pending counts 0/1/8/32, RX boundary,
successful-MAC continuous RX, due/near/unknown deadlines, retirement deadline,
security reception, FOTA/control/boot/persistence/runtime/queued work, held HIGH,
bounce, first/next motion and no power-replug requirement. ACK matrix checks
volatile/forged/wrong-owner/old-session/replayed ACKs; reboot retains exact K and
occurrence time; Hub reboot replay does not repeat reducer/evidence; only valid
ACK plus retirement commit empties pending state. Existing four priority slots,
DoorOpen/DoorClosed/CallFamily/OkPressed and full 32-record refusal are asserted.
There is no separate native SOS EventKind or new button GPIO in this C3 patch;
existing CallFamily/critical classification and full product gates cover current
resident-action semantics, without inventing a new sensor/protocol.

Two Python guards check target integration of the host-tested snapshot and
fail-awake/partial-init restoration behavior. Existing BAT-C8 assertions remain
intact: active pending/RX/recovery/outage still inhibit unless the new explicit
quiet state is established. Existing security/FOTA/Hub persistence tests supplement
the new focused seam. Physical SDK callback/radio faults are not host emulation
of real hardware and remain qualification cases.

## Identical-workload software model

`make gs150-host-test` produces `build/gs150_metrics.csv`; checked-in raw results:
[19 before/after workloads](R1_GS150_SOFTWARE_METRICS_20261010.csv).
Baseline branch in the same harness reproduces ff0f6f1's pending/retained/outage
inhibitors and 20 ms poll. It is not a historical checkout or physical run.
Both versions use the same actual NodeRadio and session retry functions.

Most workloads run 360,000 monotonic ms after ready; idle Hub reboot runs 720,000.
Model inputs: owner poll 20 ms, PIR debounce/retrigger 150/1000 ms from target,
GPIO pulses 2 s every 10 s from t=20 s in motion workloads, initial durable
records, Hub return at 130 s where specified, local callback after 20 ms or the
actual 1000 ms timeout, application ACK at 40/1000/12000 ms. Radio/flash/sleep
transition overhead is modeled as zero; all nonsleep model time is counted as
awake/listening. Handshake cryptography is real but message exchange synchronous
in the model; its RF/OS/commit duration is not modeled. Consequently measured
Hub-return numbers are scheduled opportunities, not a worst-case real handshake
SLA. Standalone health opportunities and event piggyback opportunities are
counted separately. Direct critical input uses an explicit model wake at 30 s,
not a claimed new door/button electrical wake source. Retirement workload models
one successful transport callback per report opportunity, not every fragment;
fragment ACK/security is covered by separate protocol tests.

| Scenario | Loops before → after | Awake/listen ms before → after | Sleeps before → after | TX before → after | Retired/effects after |
|---|---:|---:|---:|---:|---:|
| `connected_idle` | 95 → 125 | 1660 → 2260 | 12 → 12 | 0 → 0 | 0/0 |
| `offline_empty` | 95 → 125 | 1660 → 2260 | 12 → 12 | 0 → 0 | 0/0 |
| `offline_one` | 18000 → 3189 | 360000 → 63540 | 0 → 12 | 8 → 8 | 0/0 |
| `offline_many` | 18000 → 3171 | 360000 → 63180 | 0 → 12 | 8 → 8 | 0/0 |
| `hub_return` | 9087 → 1674 | 181620 → 33240 | 6 → 12 | 13 → 13 | 8/8 |
| `hub_return_v2` | 708 → 1213 | 13820 → 23940 | 16 → 15 | 11 → 11 | 8/8 |
| `frequent_pir` | 4257 → 4684 | 84340 → 92880 | 39 → 39 | 7 → 7 | 4/4 |
| `critical_outage` | 696 → 1214 | 13560 → 23940 | 17 → 16 | 5 → 5 | 2/2 |
| `lost_ack` | 87 → 117 | 1500 → 2100 | 12 → 12 | 2 → 2 | 1/1 |
| `delayed_ack` | 112 → 142 | 2000 → 2600 | 12 → 12 | 3 → 3 | 1/1 |
| `outage_late_ack` | 9136 → 1726 | 182600 → 34280 | 6 → 12 | 6 → 6 | 1/1 |
| `ack_after_budget` | 9686 → 2276 | 193600 → 45280 | 6 → 12 | 6 → 6 | 1/1 |
| `missed_ack_in_sleep` | 9686 → 2811 | 193600 → 55980 | 6 → 12 | 6 → 7 | 1/1 |
| `retirement_outage` | 9088 → 2465 | 181640 → 48740 | 6 → 28 | 13 → 13 | 8/8 |
| `missing_callback` | 742 → 1213 | 14500 → 23940 | 16 → 15 | 4 → 4 | 1/1 |
| `failed_callback` | 694 → 1213 | 13540 → 23940 | 16 → 15 | 4 → 4 | 1/1 |
| `failed_mac_delayed_ack` | 9136 → 1726 | 182600 → 34280 | 6 → 12 | 6 → 6 | 1/1 |
| `repeated_outage` | 4384 → 4885 | 86840 → 96880 | 41 → 40 | 7 → 7 | 4/4 |
| `idle_hub_reboot_return` | 184 → 335 | 3160 → 6180 | 25 → 25 | 0 → 0 | 0/0 |

Confirmed outage with one event: 82.28% fewer owner loops, 82.35% modeled sleep
residency, 12 capped timer sleeps, 8 TX/7 same-key retries, 1 durable admission
write, no retirement without an ACK. Eight pending: 82.38% fewer loops, 82.45%
sleep residency, 12 timer sleeps, same 8 TX opportunities and 8 admission writes.
Timer/GPIO wakes, retry counts, ACK misses, rejoin attempts, durable writes,
health/piggyback opportunities and latencies are all in the CSV. Sleeps are
modeled successful attempts; physical failures/costs are not assigned invented
values. Attempted = completed in these fault-free sleep workload metrics;
failure inhibition/restore is separately asserted at the software seam.

In `missed_ack_in_sleep`, one returned-Hub callback is lost; its delayed ACK is
missed in sleep. Before→after TX is 6→7, retries 5→6, effects remain 1, retirement
remains 1, and writes remain 2. First ACK latency is 193,100→254,128 ms (61,028 ms
extra, the existing 60 s opportunity plus model scheduling/listening). First
Hub contact opportunity remains 51,100→51,091 ms after return; completion/drain
63,100→124,128 ms. No new delivery SLA is claimed or retry delayed artificially.

For normal ACK loss/1 s delay, ACK completion is unchanged (300/1000 ms).
First qualified event-to-TX is 0 ms in the no-report workloads, 20 ms when a
retirement transport occupies the owner; actual GPIO electrical/restore latency
is unmeasured. Hub return with eight legacy pending records: contact opportunity
50,800→50,761 ms, drain 51,120→51,081 ms. V2 recovery: 7 rejoin attempts both,
contact 14,773→14,790 ms (17 ms model poll alignment), drain 15,093→15,110 ms.
Idle Hub reboot: automatic rejoin at the existing idle contact expiry,
300,000 ms after the modeled return, without new PIR. All workloads assert
admitted = retired + still pending, retained = pending, identical admissions,
retirements and logical effects across versions. No duplicate logical effect.

The current v2 path already sleeps in rejoin backoff, which the initial audit
had not quantified. Protecting its receive opportunities adds awake time:
13,820→23,940 ms in `hub_return_v2`; frequent PIR 84,340→92,880 ms; idle adds
600 ms across two health opportunities. These are disclosed safety costs,
not savings. Substantial reduction applies to previously polling authenticated
confirmed-outage retained periods. Permanent successful MAC with no app ACK,
held-HIGH PIR, active maintenance or repeated near 1 s fragment deadlines
intentionally stay awake where required. Physical battery benefit is UNMEASURED.

## Commands and actual outcomes

All Make commands run from `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.

| COMMAND | EXIT | PASS / FAIL / SKIPPED / BLOCKED |
|---|---:|---|
| `make gs150-host-test` | 0 | PASS: 1,481 checks, 19 paired workloads |
| `make -j2 battery-c8-host-test node-recovery-persistence-host-test node-retirement-protocol-host-test rejoin-host-test secure-fota-adapter-host-test` | 0 | PASS: BAT-C8 72 C++ / 11 Python; encrypted recovery, authenticated retirement, rejoin, secure FOTA/hash (other binaries do not print check counts) |
| `make cpp-test` | 0 | PASS: 1,479 checks |
| `make python-test` | 0 | PASS: 346 run, 345 passed / 1 existing historical classic-target skip; P2-D bridge PASS, 300 completed/0 pending |
| `make app-test contracts` | 0 | PASS: 17 frontend tests, 0 skipped; four schemas/protocol examples/OpenAPI |
| `python3 tests/pwa_bridge_test.py` | 0 | PASS: 12 tests |
| `python3 tests/pwa_68_api_test.py` | 0 | PASS: 1 harness test, all 92 current canonical scenarios |
| `python3 tests/pwa_68_frontend_test.py` | 0 | PASS: 1 harness test, all 92 current canonical scenarios evaluated/rendered |
| `make -j2 hub-journal-persistence-host-test hub-retirement-snapshot-host-test hub-fota-guard-host-test node-recovery-host-test commissioning-crypto-host-test` | 2 | FAIL initially: pre-existing Hub journal recipe omitted outbox source; other four targets passed |
| `make hub-journal-persistence-host-test` after recipe correction | 0 | PASS: capacity/full/replacement/dedupe/restart/tamper/write-fault/reducer-replay |
| ASan/UBSan command below | 0 | PASS: GS-150 1,481 and full C++ 1,479 checks; no sanitizer report |
| `make -j2 master-validation fota-host-test lab-build` | 2 | Initial master linker omission; lab build completed; FOTA not started |
| `make -j2 master-validation fota-host-test` after link correction | 2 | Initial C3-STRESS-001 stale sequence expectation: master 48/49, FOTA 34/34 |
| Same command after validated expectation correction | 0 | PASS: master 49/49 (all OR-001–035), FOTA 34/34 |
| Clean C3 build below | 0 | PASS: compile/link and configured partition capacity |
| `tools/context/ghar_sajag_context_preflight.sh` | 0 | PASS: 2026-10-09.001 unchanged |
| `git diff --check` | 0 | PASS |
| Inline Python Markdown path check below | 0 | PASS: GS-150 files' relative-path links; anchors not checked |
| Physical/HIL, battery current/endurance, protected storage/OTA operations | — | NOT_RUN: not authorized |

Adjacent linker correction classification before implementation:
`BUG_CLASSIFICATION=TEST_INFRA_ONLY; REQUIREMENT_SOURCE=R1_RELEASE_CONTRACT
required relevant regression validation; DECISION_IDS=GS-D020/027;
TASK_SCOPE=GS-150 Hub reboot/dedupe regression; OUT_OF_SCOPE=Hub product changes`.
At starting commit ff0f6f1, the unchanged recipe did not link
`firmware/hub/components/storage/durable_event_outbox.cpp`, required by
`HubRuntime::replay_fence_matches`. Actual exit 2 from Make / linker exit 1:
undefined `DurableEventOutbox::replay_fence_matches`. Read-only `git show`
proves the omission at baseline; no historical full test reproduction was run.
Correction adds that existing source to the journal, master and FOTA host
recipes. The broader master gate reproduced the same linker omission; its
shared HubRuntime object also requires the source in the FOTA recipe. No Hub
production source changed. GS-150 joins `validation-fast`.

Adjacent stress correction triage:
`BUG_CLASSIFICATION=TEST_INFRA_ONLY; REQUIREMENT_SOURCE=EVENT_DELIVERY_RETRY_AND_RECOVERY.md
and HUB_NODE_SECURE_COMMUNICATION.md admitted-prefix/retirement invariants;
DECISION_IDS=GS-D020/027; TASK_SCOPE=GS-150 existing outage/recovery regression;
OUT_OF_SCOPE=Node sequence/admission semantics changes`.
`C3-STRESS-001`, `tests/cpp/master_validation.cpp:305–309`, initially expected
`next_sequence()==5001` after 5,000 calls despite the ordinary-motion reserve
admitting only 28 and rejecting 4,972; actual next sequence is 29. The untouched
NodeRuntime allocates only after queue preflight/store append, preserving the
contiguous retirement high-water. The older assertion was introduced at
`df60ed5c8ae2000f2fcb293a549318a93ec10e79`; actual first historical failing
execution is unverified. Starting ff0f6f1 has the same test, NodeRuntime and
radio source, and the integration manifest already classifies this same
mistaken assumption in the full C++ suite. No older full build was run.
Classification: VALID_TEST_EXPECTATION_MISMATCH. Correction checks accepted+1,
all 5,000 outcomes, exactly 28 admitted/4,972 dropped, admitted high-water,
every retained sequence and original timestamp. This strengthens identity and
reserve coverage; production admission/sequence behavior is unchanged.
Exact failing-command exit 2 (master binary exit 1), final same command exit 0.
Regression risk: low, limited to the validated test expectation/link recipes.

Sanitizer command, with separate instrumented object output:

```sh
ASAN_OPTIONS=detect_leaks=0 make -j2 gs150-host-test cpp-test \
  CPP_OBJECT_DIR=/var/tmp/gs150-asan-objects \
  CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'
```

Leak detection follows the existing host sanitizer convention; address and
undefined-behavior checks were enabled. Instrumented simulation CSV equals the
normal run's checked-in CSV byte for byte.

Clean C3 command (fresh generated output at /var/tmp, existing board data untouched):

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py -C firmware/node/target/esp32c3/idf -B /var/tmp/gs150-c3-build \
  -D SDKCONFIG=/var/tmp/gs150-c3-sdkconfig fullclean
idf.py -C firmware/node/target/esp32c3/idf -B /var/tmp/gs150-c3-build \
  -D SDKCONFIG=/var/tmp/gs150-c3-sdkconfig -D IDF_TARGET=esp32c3 build
```

Final clean image `gs_hw_m1_node.bin`: **933,520 bytes (0xe3e90)**; each
configured OTA slot 1,966,080 bytes; **1,032,560 bytes / 53% free**. Increase
from prior image: 2,096 bytes. SHA-256
`c2e9b86facfc6e831835807645e103f0f19b7d4ddb4005757d12d8b2b91c2f14`.
No partition/configuration/source migration. Unsigned default development build;
not a signed/production/eFuse qualification claim. S3 not rebuilt or modified.
Logs: `/var/tmp/gs150-c3-build-final.log`, `gs150-focused.log`, `gs150-cpp.log`,
`gs150-python.log`, `gs150-app-contracts.log`, `gs150-extra.log`,
`gs150-hub-journal-rerun.log`, `gs150-host-final.log`, `gs150-asan.log`,
`gs150-runtime-gates.log`, `gs150-runtime-rerun.log`, `gs150-runtime-final.log`,
`gs150-pwa-bridge.log`, `gs150-pwa-api.log`, `gs150-pwa-frontend.log`.

Documentation validation uses mandatory context preflight, diff whitespace
checks and this scoped inline path check. The absent
`tools/context/check_markdown_links.py` was not recreated. An initial overly
broad untracked-file scan encountered an unrelated third-party LittleFS README
link; no managed component was changed. The actual GS-150 scope passes:

```sh
python3 - <<'PY'
from pathlib import Path
from urllib.parse import unquote
import re, subprocess
files=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
files.append('docs/exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md')
checked=0
for name in files:
    if not name.endswith('.md'):
        continue
    file=Path(name)
    for target in re.findall(r'\]\(([^)]+)\)',file.read_text()):
        target=target.strip().split(' "')[0].strip('<>')
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):
            continue
        target=unquote(target.split('#')[0])
        if target:
            checked+=1
            assert (file.parent / target).exists(), (name,target)
print(f'PASS: {checked} relative-path links in GS-150 Markdown; anchors not checked')
PY
```

## Remaining limits and next step

Software validation cannot establish real GPIO4 pulse retention, held-HIGH
power behavior, wake overhead within 500 ms margin, radio/session restoration
on board, sleep-entry FOTA races, physical callback scheduling, NVS power cuts,
signed OTA/rollback, current or lifetime. Existing Node telemetry wire has no
accumulated light-sleep field; RAM residency/awake diagnostics do not qualify
backend energy estimation. No new telemetry protocol was added.

Current 32-event retention remains bounded; no Hub-off duration/event guarantee,
72 h Node guarantee, GS-147 journal, new SOS input, C9–C12, TX power or deep sleep.
GS-114 image-matched P1–P9 is next, on a separately authorized safe fixture.
GS-149 remains quantitative P10; GS-146 requires both. S3/backend gates remain
independently open. Jira status/rank/dependencies are preserved. Final committed,
pushed and remote-verified provenance is recorded in R1_WORK_STATE and Jira.

## Verified implementation delivery

Commit `1262400408e780044d928d84286d9b6f392b9d5a` includes the validated code,
regressions and evidence. Normal push exit 0; actual remote branch HEAD equals
that local HEAD on 2026-10-10. Tracked status clean, original untracked S3
managed_components preserved. Mandatory preflight and staged diff check PASS;
15 explicitly reviewed files exclude generated binaries/SDK configuration,
credentials and unrelated work. The only generated artifact committed is the
requested reproducible software metrics CSV. This documentation-only closeout
records the delivery; final closeout HEAD and dated Jira comment IDs appear in
the session handoff/Jira. Physical qualification remains NOT_RUN.
