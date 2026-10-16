# GS-40 automated qualification framework — implementation scope

**Owning Jira:** GS-40, resumed from comments 11156, 11158 and 11162.

**Starting checkpoint:** canonical `feature/r1-commercial-baseline` HEAD
`d738dc51a25e72de570a11fc39f0e26522ead3d8`, matching `origin` when verified.
This work is isolated on `codex/gs40-qualification-20261016` because other
Codex processes are actively using the canonical worktree. No canonical
worktree files or pre-existing untracked evidence are edited.

**Affected components:** C3 Node cadence and sleep observation; S3 Hub
authenticated health/contact and per-Node lease; shared security/session and
event recovery; backend health freshness; caregiver PWA coverage visibility;
existing HIL/replay tooling and physical acceptance traceability.

**Existing implementation and suites to reuse:** `make gs40-host-test`,
`make gs40-config-test`, the Node/Hub/contract/backend/PWA component gates,
`code/tools/hil/phase1.py`, `code/tools/hil/core.py`, the GS-130 replay/HIL
helpers, and existing GS-40 physical catalogue entry. The GS-40 production
model already exercises 300/910 configuration, quiet cadence, contact
suppression, expiry boundaries, profile mapping, and retained-event recovery;
new automation must reference those assertions rather than duplicate firmware
behavior.

**New checks:** versioned TC01–TC07 case registry and deterministic host
observation contracts; immutable, source-hash-pinned replay of Jira 11158's
S3 boot transcript; fail-stop serial-observer fault classification; exact
zero-write/reopen/USB-reattach/reset audit; and a live-mode safety gate that
does not enumerate or open hardware.

**Positive/negative/recovery scope:** six quiet opportunities, authenticated
event piggyback, 910-second boundary and distinct Node/Hub/WAN status, exact
EventKey rejoin recovery, legacy/configured/untrusted profiles, online/offline/
unknown caregiver projection, and serial identity/owner/transport/log/reset/
timestamp faults. Physical real-target scenarios remain distinct and require
their own matched identity/image/config/session evidence.

**Physical/release scope:** no hardware access is authorized in this task.
Synthetic and historical input can produce `HOST_PASS` only; no physical case
may become `PHYSICAL_PASS`. The seven automated cases must be registered in the
existing component and physical catalogues. A real release gate is not
requested; only the affected component and framework regressions will run.

**No product change is planned.** Changes to firmware liveness semantics,
security, NVS, EventKeys, or production cloud contracts are out of scope unless
a genuine defect appears in the authorized host investigation. No requirement
or decision is changed.

## USB observation investigation

### C3 native USB Serial/JTAG disappearance

The production Node enters light sleep through
`code/firmware/node/target/esp32c3/node_runtime_adapter.cpp` at the
`esp_light_sleep_start()` call. The configured console is the native USB
Serial/JTAG endpoint. ESP-IDF light sleep gates clocks used by that peripheral,
so the host endpoint can disappear while the C3 remains powered and sleeps.
Jira comments 11164–11165 point to existing image-scoped GS-114 physical
evidence: C8-P1 recorded ten additional light-sleep/timer-wake cycles and an
authenticated post-wake NodeHealth received by the Hub while C3 native USB
Serial/JTAG could not be opened; C8-P2 recorded a real AM312 event, authenticated
EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1`, durable Hub ACK and Node
retirement. Their C3/S3 image hashes are respectively
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`.
These are reused only to confirm that C3 USB unavailability did not prevent
the ESP-NOW operational path on that exact GS-114 fixture; they are not GS-40
300/910, mixed-profile or caregiver acceptance and do not verify today's
installed image. The C3 USB interface and physical scenario were not repeated.

### S3 CH343 POWERON capture

The immutable historical input is Jira comment 11158's capture at
`/home/udaybhan/projects/Ghar_sajag_r1/docs/hw/evidence/GS40_S3_READONLY_UART_20261016T060458Z/s3_receive_only.jsonl`,
SHA-256 `2ff1dab2e452883af97a3eec649f5d0b7da6984dc333b692d6c17af957cc2bc6`.
It records `1a86:55d3`, serial `5CBC401023`, one exclusive pySerial 3.5 open at
115200 baud and zero bytes transmitted. The serial open succeeded at
06:04:58.972 UTC; the first received boot data arrived at 06:04:59.228 UTC,
256 ms later (the capture records 257 ms elapsed). The ESP
bootloader identified `rst:0x1 (POWERON)` and then emitted its boot/partition
table and image-segment output. The observer stopped immediately on the boot
marker. USB/IP still listed the same CH343 as Attached after close at
06:04:59.654 UTC. No Hub application startup, current NodeHealth, authenticated
session, or effective running JSON configuration appears in the capture.

The pySerial source checksum and transcript show why `dtr=False` and `rts=False`
before `open()` are not a no-transition guarantee. POSIX `Serial.open()` first
opens with `O_RDWR|O_NOCTTY|O_NONBLOCK`, configures the port, and then applies
the requested modem states using `TIOCMBIC` for DTR and RTS. The USB/IP snapshot
shows the Linux `cdc_acm` driver. If the CH343 control lines are connected to
the Hub's reset/boot network, open-time line initialization could have
triggered a reset. The actual board wiring has not been verified. Driver
initialization or USB/IP line-state behavior, a host-to-device line transition,
an independent power/brownout event, and an already-running reboot remain
plausible. `POWERON` and the 257 ms timing do not identify which occurred, and
the continued Attached state only argues against a complete USB/IP detach. The
UART was not observed before the open, so the boot could already have been in
progress when the receive stream began. The capture therefore records
`UNPROVEN_SERIAL_OPEN_CAUSALITY`; it does not prove that the serial open caused
the boot.

There was no second serial attempt in this task. No S3/C3 enumeration, handle
open, reattach, reset, power operation, flash, NVS change, motion, outage, or
physical GS-40 scenario was performed.

### Existing telemetry path

The S3 target logs authenticated NodeHealth after Hub acceptance in
`code/firmware/hub/target/esp32/hub_runtime_adapter.cpp`. Hub freshness is
maintained in runtime state. CloudSync submits durable caregiver events; it
does not submit a production NodeHealth heartbeat. The backend health service
has direct test/model entry points, and PWA tests use the backend snapshot
contract, but source inspection found no production Hub-to-backend read-only
NodeHealth route. Consequently those backend/PWA tests cannot serve as live
board observation. A trustworthy live path must correlate authenticated Hub
receipt and lease state with backend and caregiver timestamps before the
real-target cases can run.

## Automated execution results

### Per-case reports

The runner produced unique JSON and Markdown files for each case under
`docs/hw/evidence/GS40_AUTOMATED_QUALIFICATION_20261016/runs/`:

- Mock: `20261016T081451446674Z_mock` — all seven cases `HOST_PASS`, 26/26
  assertions, physical status counts 0 `PHYSICAL_PASS`, 3 `BLOCKED`, 4
  `NOT_RUN`.
- Replay: `20261016T081451841251Z_replay` — TC07 `HOST_PASS`, 6/6 checks on
  the actual Jira 11158 capture; historical input hash matches the recorded
  source hash. It reports the `POWERON` banner, one past open, zero past
  writes, USB/IP still Attached, no GS-40 application evidence, and
  `UNPROVEN_SERIAL_OPEN_CAUSALITY`.
- Live: `20261016T081452129398Z_live` — all seven `BLOCKED`; the runner has no
  verified approved non-resetting provider and refuses USB/serial/network
  access. All action counters are zero. No report has `PHYSICAL_PASS`.

Current repository config SHA-256 in all reports is
`2e42da92784c6eed807d8df240d1c33a178c1c088a568cbf9cb6d5d20817aadb`. The
running C3/S3 image hashes, effective on-device config hash, current board
identities and current authenticated session remain `UNVERIFIED`/unknown. The
historical capture's partition table is not current installation evidence.

### Commands and outcomes

| Command | Result |
|---|---|
| `make gs40-qualification-test` | PASS, exit 0, 12 tests; also passed as the registered `gs40-qualification-host` stage. |
| `make validation-tooling` | PASS, exit 0, including the registered GS-40 runner, 46 framework tests, traceability, HIL integrity and negative gate checks. |
| `make validation-framework-test` | PASS, exit 0, 46 tests. |
| `make feature-coverage-test physical-hil-catalogue-test` | PASS, exit 0; traceability tests 22/22, catalogue 107 cases, device access `NONE`. |
| `make validation-node` | Final run exit 1 only at mandatory P0 product status: board-stack E2E 10, C++ 1,483, `gs40` 1,320 and `health-config` 17 passed. P0 ran 26/26 but reported `product_status=PARTIAL`. An earlier pre-install run stopped at missing Playwright. |
| `make validation-hub` | Run exit 1: the unchanged Hub journal migration test reports `clean migration commits`; its initial P0 stage also lacked Playwright. Reported GS-40 (1,320), health-config (17), security, board-stack E2E (10), and sanitizer stages passed. Post-install P0 runs in other component gates completed 26/26 with `product_status=PARTIAL`. |
| `make validation-contract` | Final run exit 1 at P0 product status. GS-40 (1,320), health-config (17), board-stack (10), storage/recovery, compatibility and authenticated contract stages passed. P0 assertions were 26/26 but `product_status=PARTIAL`. |
| `make validation-backend` | Final run exit 1 at P0 product status. Backend Python 503, functional 92, HTTP 17, bridge 13, API 2 and diagnostic-foundation 98 passed; P0 assertions 26/26 but `product_status=PARTIAL`. |
| `make validation-pwa` | Final run exit 1 at P0 product status. Browser 86 passed; backend/PWA Python 503, JavaScript 23, functional 92, HTTP 17, API 2 and diagnostic-foundation 98 passed. P0 assertions were 26/26 but `product_status=PARTIAL`. |

The existing component framework marks P0 as FAIL when product status is
PARTIAL even if scenario assertions pass. This is the already-recorded GS-148
durable Hub-commit API gap, not a GS-40 test failure. The Hub migration failure
is also separate from GS-40 and was not modified. The framework registration
regression was updated to compare against the supplied active R1 checkpoint
`d738dc51a25e72de570a11fc39f0e26522ead3d8`; it now asserts that only the new
GS-40 tooling stage was added on this candidate while retaining the canonical
parent's no-loss checks. Its six tests pass.

No full release gate ran. No firmware behavior, board image, durable state,
security state, or backend product contract was changed.

## Physical disposition and next authorization

There are no physical PASS results. PHY-GS40-01 through PHY-GS40-06 remain
BLOCKED in the catalogues, and aggregate PHY-GS40 remains NOT_RUN. The current
hardware set is one C3 Node and one S3 Hub. The pair can support the single-Node
cadence, contact, timeout, recovery, and caregiver cases only after identity,
image/config/session, and a trustworthy observer are established. It cannot
complete mixed-profile physical acceptance: TC05 needs a second valid C3 Node
or an approved qualified profile fixture. No oscilloscope/current profiler is
required by these liveness/status cases, but a synchronized timestamped
authenticated observation chain is required.

The next owner authorization should be one consolidated, board-specific staged
plan covering: (1) the exact non-resetting observation method and read-only
preflight of C3/S3 identity, current image/config/session, and pending EventKeys;
(2) if no such method exists, whether to accept the residual reset risk of one
new, exact S3 CH343 receive-only open and which recovery steps are permitted;
(3) a real sensor stimulus for TC02; (4) the precise controlled 910-second
Node-silence and return/rejoin method for TC03/04; and (5) live backend/PWA
observation and a second Node or qualified fixture for TC05. Do not begin a
scenario if the preflight cannot prove exact image/config/session, safe capture,
and identity/EventKey-preserving recovery. The earlier single receive-only
approval is consumed.

Firmware installation is not established as necessary: running images and
effective on-device JSON are unknown. If the passive preflight identifies an
image/config mismatch, installation would require a separate exact flash
authorization; no installation is authorized by this work. GS-40 remains In
Progress and does not meet Done criteria until all six real-target cases and
caregiver visibility pass with matched current-image evidence.
