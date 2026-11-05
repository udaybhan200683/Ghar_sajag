# GS-117 session 134 — offline root-cause investigation

2026-11-05. Owning Jira GS-117, Highest / In Progress. Classification:
`INVESTIGATE_ONLY`; no product, transport, authentication or authorization change.
Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting local/remote
`6fe356754d84eb53f4eaca83f4a6d17d84b07a35`; context preflight PASS.
Tracked tree initially clean; 79 existing untracked status entries preserved.
No competing hardware execution identified. No hardware/network operation,
production-code change, firmware build, authorization mutation or retry performed.

## Result

**The radio root cause remains NOT_PROVEN.** The earliest retained failure is
C3's post-channel-set security-send aggregate returning false on channels 3/4.
It does not identify the ESP-NOW API/callback error. The zero liveness values
are consistent with the initial authentication gate, not proof of failed sensing
hardware. The S3 watchdog is real, but its causal relationship to failed rejoin
is unproven. Network qualification remains separate and PASS.

## Evidence identity and limits

Original private target directory:
`~/.local/state/ghar-sajag/gs117-tc001/standing-authorization/bootstrap-14abbf25667808dd0d099113/`.

| File | Bytes | UTC modification time | SHA-256 |
|---|---:|---|---|
| stdout.json | 6422 | 2026-11-05T04:28:39.206308Z | 28963e6a03a590b0fca75e72a5c3bb2b04354ddbe35f73e3e60f8a4d34cbe1d5 |
| bootstrap-child-result.json | 7809 | 2026-11-05T04:28:39.150316Z | 9cf2cbf8e4a168cb94fea8befec91ad5bef23c1997e98a13212955e1b0fb3ae8 |
| stderr.log | 0 | 2026-11-05T04:28:39.206308Z | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| recovery-attempt.started.json | 87 | 2026-11-05T04:26:55.436408Z | 3ad019a4e91e007195f1424a48ae2c2be4ae9dc002db9ab286b531797986635a |

The child receipt records start04:26:55.436462Z, challenge receipt04:26:58.239469Z,
finish04:28:39.149272Z, elapsed103712ms, child exit0, valid response. Its raw-output
digest is6594 bytes/SHA02f82497f57e292e0e1ba9e45cbc6fc73cd4b8990e9115768fbdba925671e1f7;
the retained response is redacted, not original unfiltered UART bytes.

Network/decoded-trace provenance is preserved in
`~/.local/state/ghar-sajag/gs179-approved-AB-20261105T040835Z/`.
New private analysis directory
`~/.local/state/ghar-sajag/gs117-session134-offline-rca-20261105/` contains a
51-file original-evidence manifest (paths, sizes, timestamps, hashes), probe
sources/results, test receipts and limitations. Originals were read only;
the four target hashes were rechecked unchanged.

**Correction to the earlier handoff:** both saved lists contain20 lines, but
there is no configured20-line tail limit. `gs117_tc001_serial_windows.py:34–44`
filters lines, keeps the first300 accepted lines and truncates each to1024
characters; `gs117_bootstrap_evidence.py:55–76` retains up to300 string entries.
Bootstrap boot/challenge collection also consumes earlier serial data separately.
No full raw UART capture or host arrival timestamp per line survives. The
watchdog overdue-task list/current-task names are excluded by the collector
allowlist; offline replay confirms this. Missing filtered lines cannot be recovered.

## C3: last proven state and first uncertain transition

The installed-image receipt records app SHA
`589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7`.
The preserved `code/build/gs117_dev_rejoin_20261029/c3/gs_hw_m1_node.bin` matches;
paired ELF SHA is043ba7db4a89197e608971a590476ea77807e3abbf58f93e050d3a018dd2f234.
Current `node_runtime_adapter.cpp` SHA
`863e726af2f7f9ad5d06ad62355b66ef7d288f3077f3181d36161ac7846fee3a`
matches the installation receipt's source pin. This is historical build/source
provenance, not a fresh device readback.

Source chain (all under `code/firmware/`):

| Stage | Exact implementation / session134 conclusion |
|---|---|
| Initialization | `node/target/esp32c3/node_runtime_adapter.cpp:2154–2220`: durable session allocation, static queues, GPIO, STA/MAC guard, ESP-NOW and owner task. Continued owner send logs and independent GET_STATE replies prove execution, not authenticated readiness. |
| Binding/Hello | `node_security_link.cpp:110–137,551–564,589–605`: validate stored association, derive destination from Hub ID, build authenticated Hello, encode, then send. The current destination/peer metadata are not logged, so expected fixture identity is not substituted for an observed TX destination. |
| Channel | `node_runtime_adapter.cpp:138–145,536–560`: permitted channel is set before the aggregate log; failure here returns without that log. Thus the logged attempts reached `send_security_message` after a successful set call. Actual PHY read-back/channel at send time is not recorded. |
| Send | `node_runtime_adapter.cpp:495–533`: false can mean fragmentation rejection, peer-add error, immediate `esp_now_send` error, callback timeout1000ms or negative callback. Initial boot calls wait for callbacks; in-service recovery has a separate nonwaiting submission-only path. |
| Callback | `node_runtime_adapter.cpp:206–226`: security-phase callback overwrites a one-entry Boolean queue, without MAC/transaction correlation. A returned false is not an application authentication rejection. |
| Challenge/Final | receive callback copies source/channel into depth8 queue; `node_security_link.cpp:594–605,666–719` validates source/transcript before Final, then authenticates ACK before Ready. Discovery pins only after an authenticated challenge. No such transition is established here. |

Complete current Hello logs are C3 uptime76327030ms/ch3 and76387190ms/ch4:
delivered0/challenge_pinned0,60160ms apart on the **same device clock**. The
initial concatenated channel11 fragment is older incomplete data, not a fresh
third observation. No subtraction of C3 and S3 boot clocks is used.

`common/connectivity/india_wifi_profile.hpp:49–112` scans channels1–13 once per
scheduled Hello and retains a channel only after an authenticated challenge.
`node/power/session_recovery_policy.hpp:77–81` saturates retries at60000ms plus
0–100ms jitter; a full saturated sweep can therefore take about13 minutes.
No Final means the ambiguity rule does not allocate a new candidate merely
because time passes. Channels3/4 are valid scan steps, not a proven channel bug.

Ranked hypotheses, none established as the unique cause:

1. Channel/receiver availability during the two scan opportunities: strongest
   contextual hypothesis, moderate plausibility but low causal confidence.
   Current S3 channel and receive readiness at those sends are absent.
2. Local peer/ESP-NOW submission or MAC failure: directly compatible with the
   aggregate; peer metadata and exact error are absent. Existing peers are reused
   without inspection. There is no evidence of a wrong MAC or stale peer.
3. Callback loss/late attribution: supported by the uncorrelated Boolean queue,
   but no session-specific timeout/status/queue evidence proves it.
4. S3 flash/scheduling pressure affecting radio service: plausible indirect
   contributor, not demonstrated by the watchdog alone.

The actual fixture Hello's valid wire encoding is121 body bytes/133 packet bytes
in the host probe. Successfully encoded Hello, nonzero transaction and existing
fragment bounds make size/fragmentation a weak explanation absent corruption.
No local challenge rejection is shown; `challenge_pinned=0` means no pin, not
proof that no packet arrived. No firmware or sensing fault is established.

## Liveness semantics

Globals at `node_runtime_adapter.cpp:128–129` start at zero. Initial owner waits
at613–729 for `security_link.ready()` before constructing NodeRuntime, restoring
retained state and starting PIR stabilization/normal sampling. Local counters
start at806–807, increment once per main owner-loop pass at984–985, and are
published at1799–1800 for GET_STATE at2081–2086. They are loop-progress counts,
not PIR-edge counts, time-window flags or direct task-existence measurements.
Once the normal owner loop has started, its in-service rejoin path still samples
and advances counters; it does not use the initial blocking gate.

All nine session134 values are zero, while GET_STATE and retry logs continue.
This strongly supports remaining in the initial rejoin gate, with zero counters
a **consequence of uncompleted authentication**, not its proven cause. No raw
PIR/task failure can be diagnosed from these values. Do not bypass the gate.

Comparable preserved session127 (`bootstrap-3e1d1732f282d938502bc282`) uses the
same S3 boot ELF prefix and C3 diagnostic context: counters initially0, Final
kind8/channel7 at38387ms, accepted rejoin, then334→838→1347→1852. Session129
(`bootstrap-85fb8d482e17dc33ce4f8dca`) also has early MAC-delivered Hellos and
three S3 control-reply failures, without Final. Session134 does **not** establish
that same later boundary: its retained Hellos themselves report false.

## S3 watchdog and configuration: separate findings

Preserved S3 ELF full SHA
`7584a1f80c1a59dc55e7fed9ae3092618cde7c8be8c8ccca6b041e302bf52ed1`
matches the boot prefix. Paired saved app SHA is
`ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5`.
Existing addr2line re-symbolized all29 frames successfully, without a build.
The interrupted CPU1 application context is `cloud_node_health_task` →
`CloudSyncWorker::run_once` → `CloudSync::next_batch` → journal/outbox iteration
→ LittleFS `fread/fstat` → `esp_flash_read` → flash/cache IPC coordination;
the top crosscore ISR prints the backtrace.

Same-S3-clock evidence: first run_once ends70806ms/elapsed13170ms; second ends
89126ms/elapsed13306ms, implying start75820ms. Watchdog85936ms is inside the
second iteration. Both report state3/Ready, submitted0/completed0/refused0.
There is no event HTTP submission in these iterations; authority checks,
scan/decode and scheduling can still take time. Later logs continue, so permanent
deadlock or another S3 reboot is not established.

`cloud_sync.cpp:375–413` scans the whole journal to choose globally ordered
bounded output. `durable_event_outbox.cpp:2367–2425` reads prefix and full body;
`backend_completed():1552–1579` authenticates another body read per visited key.
An existing MemorySegments fixture with100 records required300 segment reads
for batch limits1,4 and16. This proves scan work is not limited by batch size,
not a target timing or watchdog reproduction. LittleFS opens/seeks/reads/closes
per call (`littlefs_segment_store.cpp:70–86`). There is no explicit yield inside
this scan; the priority3 unpinned cloud task delays only after its worker calls.
The priority8 Hub owner and high-priority Wi-Fi callback path are separate.

The preserved generated SDK config requests a5s, nonpanic TWDT with both idle
tasks checked; Wi-Fi is pinned CPU0. ESP-IDF6.0.3
`components/esp_system/task_wdt/task_wdt.c:408–445,475–509` prints overdue tasks
and samples the affected core; those task-identification lines did not survive
filtering. `components/spi_flash/cache_utils.c:125–193` coordinates both cores
and temporarily suppresses scheduling/non-IRAM interrupts. Consequently CPU1
idle starvation/flash pressure is a supported watchdog hypothesis; no5s lock
hold, culprit task, cache deadlock, queue loss or radio causality is proven.
The host memory store cannot reproduce ESP cache/IPC/Wi-Fi scheduling.
Session127 already had8–10s CloudSync calls **and successful rejoin**, so slow
CloudSync alone is not sufficient evidence of the rejoin cause.

The desired-policy rejection has a separate deterministic explanation: approved
v18 supplies TLV21 (fixture Home), but omits TLV17 (activity Home). The parser
at `gs40_test_only_bootstrap.cpp:522,532` leaves `activity_home_id` empty;
`gs40_test_only_runtime.cpp:527–550` rejects before requesting desired policy.
The shared disabled-rules warning is not proof that time/lease also failed.
This same rejection appears in successful session127. HubSecurityLink's rejoin
path has no activity-policy/cloud-time gate. Do not weaken config validation or
claim target time acceptance from an HTTP200. This omission is not shown to
cause either watchdog or radio failure.

## Proven offline defects, minimal future corrections — NOT implemented

1. Existing collector lacks watchdog task identification and a common host
   arrival timeline. Preserve bounded/redacted watchdog headers, overdue/current
   task names, drop counts and channel/peer/send-stage evidence. No secrets or
   callback-time blocking logs. C3 lower-stage evidence is not recoverable from
   its existing aggregate; propose bounded diagnostics in existing functions
   only, with no transport/authentication/retry behavior change or deployment.
2. Existing helper has a90s requested phase **plus an unconditional10s drain**
   at `gs117_tc001_serial_windows.py:429–469`. Actual child103712ms is consistent
   with this; earlier text treating the entire collection as only90s was too
   strong. Fake-clock execution measured90.02s without bootstrap versus100.04s
   with it (nine queries each). Before another procedure is proposed, enforce
   one absolute approved observation deadline across collection/drain, then
   test exact bound, error cleanup and evidence retention. Do not silently
   amend pins, approvals, ledgers or the90s limit.
3. Current **uninstalled** diagnostic source introduced a return-type defect in
   commit70d577ead4d19b72691adc71097bb7a0f73fb903: `add_runtime_peer` now returns
   `esp_err_t`, but `hub_runtime_adapter.cpp:844` still uses `if (!add_runtime_peer(mac))`.
   Existing/new peer success0 is rejected; nonzero error is accepted by this
   caller. Three mocked production-function cases reproduce the inversion.
   Minimal proposed correction: compare `!= ESP_OK`; registered tests must
   exercise existing peer, successful add and failed add at the **owner caller**.
   Saved installed ELF disassembly proves the older helper returns Boolean
   true on success. Thus this defect is not session134's cause and does not
   justify replacing installed firmware. Do not deploy the unqualified image.

For a future diagnostic proposal, decisive evidence is C3 immediate ESP error,
actual destination/peer/channel, transaction-correlated callback result/timeout;
S3 actual STA channel, ESP-NOW-ready timestamp, Hello reception/validation and
reply stage; complete TWDT overdue-task/CPU records plus bounded scan timing.
Preserve source/session identities and host arrival times. Do not request
another physical attempt merely to repeat the aggregate observation.

## Newly executed validation and final boundary

Existing registered host targets, all exit0: `make -C code gs58-wifi-host-test`
(77 checks), `rejoin-host-test` (mutual proof/Home/session/replay PASS),
`hub-segmented-outbox-runtime-host-test` (durability/recovery/deduplication/
admission PASS), `gs40-test-only-bootstrap-test` (91 checks). These compile host
binaries only. Private analysis probes:17 production send-branch checks PASS;
collector/clock/filter probe PASS;100-record scan/corruption probe PASS;
three-case current-source peer-predicate defect reproduced; exact ELF29-frame
decode PASS. Probes are analysis experiments, not permanent regression gates
or RF/RTOS/physical qualification. Preliminary probe expectation/launcher
failures and corrections are recorded in `analysis-attempts.json`; no production
assertion was weakened. Broad release gates/target builds/HIL NOT_RUN.

No installed runtime root-cause fix is justified yet. Next engineering action:
review the smallest existing-collector/diagnostic correction with registered
tests for the proven timing/retention issues and precise send-stage evidence,
before any separately reviewed physical plan. No network redesign.

GS117#11897 remains SAFETY_LATCHED,1/1 consumed; historical#11886 and original
captures untouched. Firmware unchanged; receipts STALE; TC001_READY NO;
TC0010/5. Real optical PIR, authenticated recovery, EventKey/durable-before-ACK,
CloudSync/PostgreSQL, chronology/latency/deduplication and real Android acceptance
remain open. Event123/1's approximately6h53m delay remains unresolved.

Delivery: GS-117 comment11922 posted and independently read back. Canonical
execution/work-state and GS179 cross-reference synchronized. Documentation-only
commit follows validated diff/context checks; no permanent source/test changes.
