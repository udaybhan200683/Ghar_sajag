# Hub + ESP32-C3 unattended HIL automation — Phase 1

Status: implemented on `feature/hw-m1-4-hil-automation`. This phase is the
bounded core regression; FOTA matrices, long stress/soak, advanced performance
qualification and dashboard history are expressly out of scope.

## Commands

The authoritative complete Phase-1 command is run from normal WSL Ubuntu:

```sh
cd ~/projects/Ghar_sajag
make hil-qualify
```

It synchronously runs `validation-fast`, `release-gate-final`, WSL fixture
identity/readiness, `hil-setup`, `hil-preflight`, `hil-smoke`, and
`hil-regression`. It fails fast, marks every later mandatory stage `BLOCKED`,
always prints the final summary, and exits zero only after all seven summary
rows pass. It requires no manual port, BUSID, flash, ESP-IDF activation,
motion, BOOT or RESET action.

The individual commands remain available for focused diagnostics:

```sh
make hil-setup       # one time, discovers identities; never flashes
make hil-preflight   # read-only fail-closed fixture/readiness check
make hil-smoke       # fast boot/health/one real ESP-NOW event/ACK check
make hil-regression  # smoke + radio + outage + restart + short health campaign
```

### WSL-first architecture and Windows USB boundary

The original implementation made PowerShell the master: it attached USB,
converted repository paths, launched WSL stage children, monitored them and
collected the result. Real Windows PowerShell 5.1/WSL runs exposed repeated
encoding, quoting, stderr, wait, provider-path and UNC/current-directory
conversion failures. That history is retained here, but that architecture is
superseded because it added risk without testing the product.

WSL now owns repository location, stage order, `make`, ESP-IDF, serial paths,
identity, recovery, evidence and verdicts. It first asks pyserial/esptool to
verify both boards. If both are visible, Windows is not called. If either is
missing, WSL passes the ASCII source of
`tools/hil/ensure-usb-attached.ps1` to Windows PowerShell on standard input.
No repository, Linux or UNC path crosses that boundary.

The helper only queries usbipd and attaches unique live Hub `10c4:ea60` and C3
`303a:1001` matches. It supports parsable output with plain-list fallback,
ignores Persisted rows, accepts informational stderr when exit status is zero,
refuses `Not shared` as `BLOCKED_NEEDS_USBIPD_BIND`, rediscovers changed
BUSIDs, and requires live `Attached` state within a bounded timeout. It never
runs WSL, make, ESP-IDF or HIL.

During HIL, serial recovery is also WSL-owned. When a tty disappears, WSL
tries bounded rediscovery, calls the USB helper only if attachment is needed,
then dynamically finds the tty and re-verifies the ESP chip/MAC before capture
resumes. PowerShell never monitors the HIL process.

The former `tools/hil/run-hil.ps1` is now an explicit deprecation notice and
has no orchestration behavior. `tools/hil/run-wsl-stage.sh` is retained only as
a historical compatibility artifact and is not used by qualification.

Hardware-independent orchestration coverage runs through:

```sh
make hil-supervisor-test
make hil-tooling-test
```

The USB helper supports direct `-ParserCheck` and `-SelfTest` Windows
PowerShell modes. Its self-test uses fake native results and does not attach
hardware or execute HIL.

No command prompts after launch. `hil-setup` writes the ignored
`config/hil.local.env`; the committed `config/hil.example.env` documents its
schema. Rerun setup after deliberately changing branch, commit, source, USB
adapters or boards. `HIL_FLASH=auto` avoids reflashing when the exact Hub/C3
image hashes were already flashed by this fixture. Delete the ignored
`config/hil.flash-state.json` to force a bootstrap flash.

## Validation-gate ownership

`make hil-regression` is the single authoritative owner of all 71 real-target
Phase-1 IDs. `make validation-fast` invokes only `hil-tooling-test` and the
hardware-independent HIL host/isolation check. `make release-gate-final` adds
the HIL target compile/provenance check, including required HIL markers and
pair matching; it does not require attached boards. `make validation-nightly`
is hardware-free by default and includes those infrastructure checks. Setting
`HIL=1` invokes the WSL-first `hil-qualify` path and blocks when the fixture is
unavailable.
`make hw-release-gate HIL=1` similarly requests connected qualification;
without `HIL=1` it reports `BLOCKED_HIL_FIXTURE_UNAVAILABLE` rather than
claiming physical PASS. No top-level gate duplicates the Phase-1 scenarios.

After `make hil-qualify` passes on the real fixture: review the reports, make the
deliberate checkpoint commit, verify a clean tree, then run `make hw-pair-build`,
`make hw-release-gate`, and `make validation-nightly`. Optionally run
`make validation-nightly HIL=1` for a connected-HW nightly. The supervisor does
not perform the commit or push.

## Architecture and safety boundary

The controller discovers every candidate using esptool and assigns roles only
when exactly one device matches each qualified station MAC:

- Hub `5C:01:3B:BE:B9:F8`, ESP32 (not C3)
- C3 `14:63:93:C5:D1:58`, ESP32-C3

It records `/dev/serial/by-id` when available, plus VID/PID, USB serial and the
observed tty. Runtime reconnect first uses by-id, then USB serial, then a unique
role-specific VID/PID. COM/tty numbers are never permanent identity. Unknown,
duplicate, wrong-chip or ambiguous ESP devices fail closed and are never
flashed.

The HIL firmware uses a narrow UART command shim compiled only when
`GS_HIL_BUILD=ON`. `INJECT_MOTION` replaces the PIR electrical/optical
observation at the sensing boundary. The event then uses the real production
`NodeRuntime`, bounded store, retry/session logic, ESP-NOW, Hub adapter,
`HubRuntime`, journal decision, application ACK and C3 retirement. It does not
claim AM312 optical sensitivity.

Supported controls are:

- C3: `INJECT_MOTION`, `GET_HEALTH`, `GET_STATE`, `SOFTWARE_RESTART`
- Hub: `SET_HUB_LOGICAL_ONLINE`, `SET_HUB_LOGICAL_OFFLINE`, `GET_HEALTH`,
  `GET_STATE`, `SOFTWARE_RESTART`

Normal project configuration defaults `GS_HIL_BUILD` to OFF and does not add
`hil_control.cpp` to either component. The production pair builder scans both
release images and fails if a HIL marker is present. The HIL pair builder does
the inverse check. Thus the test interface is absent—not merely disabled—in a
normal image. It does not change production authorization or radio security.
The C3 HIL build additionally generates an ignored sdkconfig from production
defaults plus `sdkconfig.hil.defaults`, selecting native USB Serial/JTAG as
the primary bidirectional console. The tracked production sdkconfig remains
UART-primary and is not rewritten.

## Preflight and fixture ownership

Preflight checks local config completeness, configured branch/commit/source
fingerprint, requested clean-tree policy, ESP-IDF activation, `idf.py`,
esptool, pyserial, 2 GiB free disk, exact MACs, chip families and exclusive
serial access. It warns about WSL/sleep/AC risk but never changes laptop power
settings. Probing uses supported esptool DTR/RTS reset sequencing and performs
no flash.

Smoke/regression take a nonblocking `flock` fixture lock. A second runner fails
immediately with owner PID/time. Context-managed cleanup covers success,
failure, exception and Ctrl-C: capture threads and ports close, child commands
are bounded, and the lock is released. Scenario waits have explicit timeouts;
stopped serial, lost health/liveness, disappearance and reconnect failure are
failures rather than infinite waits.

The pair build reuses `scripts/build_hw_pair.py` hashing, metadata, embedding
and pair-validation functions. HIL images have a deterministic
`<commit>-hil-<source-fingerprint>` version with no `-dirty` suffix. Provenance
still records the real branch, full commit, clean/dirty state, source
fingerprint, ESP-IDF version, image hashes/sizes and byte-identical embedded
C3. HIL images are explicitly marked non-release qualification artifacts.

Flashing is per-role, per-project, through `idf.py -p ... flash`, only after
identity validation. After each flash the fixture is rediscovered and MAC is
rechecked. ESP-IDF/esptool owns automatic boot/reset sequencing. Software
restart is labelled `SOFTWARE_RESET`; it is never described as a power cycle.

## Phase-1 matrix

| Suite | IDs | Real-target behavior |
|---|---:|---|
| Smoke | HIL-SMOKE-001..017 | discovery, identity, pair, boot, health/liveness, one motion, ESP-NOW, Hub process, durable ACK, retirement, idle, reset/resource checks |
| Radio | HIL-RADIO-001..010 | baseline, repeated/sequential/idle event, app ACK, health, Hub/C3 recovery coverage, short nine-event qualified burst, final health |
| Offline resilience | HIL-OR-001..020 | logical Hub outage, live C3, offline motions, retained/retry/backoff, recovery/drain, event during drain, two cycles, final state/resources |
| Hub restart | HIL-HUB-RST-001..010 | idle, pending/backlog, repeated software restart, autonomous recovery, post-restart event/ACK/state |
| C3 restart | HIL-C3-RST-001..008 | software reset, NVS session advance, Hub reauthorization, health, post-reset event/ACK, repeated reset |
| Both restart | HIL-BOTH-RST-001..006 | Hub→C3, C3→Hub, near-simultaneous software reset, rediscovery, communication and event/ACK |

Offline traceability maps to the production-runtime host cases as follows:

| HIL | Host OR evidence |
|---|---|
| 001–005 | OR-001..005 |
| 006–008 | OR-006..012 |
| 009–013 | OR-013..020, OR-027..029 |
| 014–017 | OR-021..026, OR-030..035 |
| 018–020 | OR-018, OR-033..035 and stability cases |

The runner records TX attempts, MAC success/failure, durable ACK, retry,
backoff, session, sequence, reset reason, sensing/runtime liveness, retained,
in-flight, motion/store/priority counters, errors/breadcrumb, heap/minimum heap,
RSSI and channel when firmware exposes them. RSSI is diagnostic only—there is
no fragile pass threshold. Watchdog or brownout indications fail the campaign.
Phase 1 checks basic heap/liveness/final-state invariants, not trends.

The current product has no persistent retained-event store across C3 reset.
The restart suite therefore checks session/rejoin/new traffic; it does not
invent retained-event persistence. This remains a named product gap.

## Evidence and recovery

Each invocation creates `evidence/hil/runs/<UTC timestamp>/` containing:

- `summary.md`, `summary.json`, `test_results.json`, `provenance.json`
- `hub_serial.log`, `c3_serial.log` with UTC timestamps and source labels
- pair/flash logs and `failures/` diagnostics when applicable

`evidence/hil/latest.txt` points to the most recent local run. Generated HIL
evidence is ignored and is not qualification history until deliberately
reviewed. Exit status is zero only when all configured Phase-1 IDs pass;
physical-only rows may remain `BLOCKED_EXTRA_FIXTURE`.

After a scenario failure the runner attempts safe recovery: serial remains
owned/reconnectable, both targets receive software restart, HIL-ready and
NodeHealth must return, then one smoke motion must receive a durable ACK. It
prints `RECOVERED` or `RECOVERY_FAILED`. After failed recovery, dependent cases
are `BLOCKED_BY_FIXTURE_STATE`, preventing cascaded false failures.

## Failure triage

1. Read console overall/counts/report path, then `summary.md`.
2. For identity or port errors, rerun `make hil-setup`; never override a MAC.
3. For a busy port, stop the named external serial monitor and rerun preflight.
4. For flash/boot failure, inspect the role flash log and serial log. The tool
   uses automatic DTR/RTS; needing BOOT/RESET is a fixture/hardware fault.
5. For radio/outage failures, correlate session/sequence across C3 send, Hub
   process/ACK and C3 retirement. RSSI alone is not a verdict.
6. Do not promote a run with unexpected watchdog/brownout, version/hash
   mismatch, recovery failure or missing final idle state.

## Physical-only boundary and Phase 2

The current USB fixture cannot create a true electrical Hub/C3 power cut,
controlled brownout/battery cutoff, current measurement, battery endurance,
PIR optical stimulus, house-range RF path or thermal environment. These are
reported `BLOCKED_EXTRA_FIXTURE`/`PHYSICAL_ONLY`, with the exact missing
fixture. USB/software reset tests are not power-cycle tests.

Phase 2 owns FOTA fault matrices, extended stress/soak, advanced performance
qualification and dashboard history. No scheduler, cron entry or Windows Task
Scheduler configuration is installed by Phase 1.
