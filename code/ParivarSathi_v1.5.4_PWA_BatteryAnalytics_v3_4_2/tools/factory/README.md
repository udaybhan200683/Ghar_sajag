# Explicit development bench fresh initialization

**Current status (2026-10-07):** the supported fresh-install durability and
lost-ACK physical gates are closed in `docs/product/R1_WORK_STATE.md` at the
repository root. The initialization/retry instructions below preserve the
earlier bench procedure and its archived 28-event state; do not rerun them to
reconcile source changes or repeat a passed gate. BAT-C8 physical qualification
remains pending. The final lost-ACK capture is in
`docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/` at the repository root.

This tool is for the preserved development bench, not a field reset or legacy
migration. No board was operated while preparing it. The commands below execute
only when the operator runs them. Stop if a device, partition, OTA state, or
retained-record check fails. Do not use erase-flash or automatic NVS recovery.

## Changes and preservation

The standalone initializer waits for a MAC-bound `DEV_FRESH_RESET` confirmation.
It does not run normal radio/admission. Hub initialization replaces only
`gs_journal`, `gs_security/wrap_key`, `gs_home/id`, and `gs_registry/snapshot`.
It creates authenticated native epoch-1 genesis and an empty native registry
using production codecs, then verifies normal recovery. No migration metadata.
Node initialization explicitly disposes of the archived 28 development records
in `gs_node_rec/snapshot`, then writes a generation-advanced Unpaired association.
It preserves signing identity, installer code, wrapping key and boot/session
counter. Disposal is not a Durable ACK. Normal firmware subsequently advances
its session normally. In-flight RAM disappears when the initializer boots.

Both preserve bootloader, partition table, otadata, factory material and unrelated
NVS. The controller reads/hashes NVS (plus Hub journal), partition table and OTA
metadata before writing any app. Evidence has restricted permissions; do not
publish raw NVS. Existing October-5 forensic dumps are never opened for writing.
The controller uses official IDF partition/OTA parsing and refuses pending OTA
rollback states. Only the confirmed active app slot is flashed, then restored.

Initializer failure can leave a partial fresh installation. Admission remains
off; preserve its transcript and investigate. No automatic repair or rollback.
The reset is intentionally not a power-cut-atomic field provisioning protocol.

## Build only (no port access)

```bash
cd /home/udaybhan/projects/Ghar_sajag_r1/code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
python tools/factory/bench.py build --role hub --build /tmp/gs_r1_factory_hub
python tools/factory/bench.py build --role node --build /tmp/gs_r1_factory_node_hardware_aead
python tools/factory/bench.py build --role hub --normal-hub --build /tmp/gs_r1_normal_hub
```

Normal Hub uses the real production runtime with `GS_HIL_BUILD=OFF`, existing
bench `GS_HIL_CONTROL=ON` development provisioning and size optimization `-Os`.
It has no former security-only/inspection flags. This is a qualification image,
not a production protected-identity release. Embedded Node image is unchanged.
Restore the already built C8 USB qualification Node image below; no Node source
or FOTA signing changes are needed.

## Guarded Node retry after zero-input GCM correction

The production PSA adapter now supplies non-null addresses for zero-length input
and output, while preserving zero authenticated payload length and the existing
record schema. Hardware AES remains enabled in the corrected initializer and
normal Node image. No software-backend workaround is required.

Both images include a memory-only regression executing the real ESP-IDF PSA
hardware driver. It checks the empty 28-byte-AAD case against an independent
known-answer tag, rejects tampering, and exercises association reset, reload and
re-enrollment. The initializer runs this gate **before FACTORY_READY**, so a
failed gate cannot receive reset confirmation or change installation state.
Normal qualification firmware runs the same gate before starting admission.

Target execution has NOT been performed during offline preparation. Require
`NODE_EMPTY_AEAD_TARGET result=PASS backend=ESP_IDF_PSA_HARDWARE_AES checks=13
stage=complete` in initializer and normal boot evidence. Build/host PASS must not
be recorded as a physical target PASS.

The Hub has already passed initialization: **do not rerun any Hub reset command**.
For the current partial Node state, use only this guarded retry after operator
approval and port verification (new evidence directory required):

```bash
python tools/factory/bench.py reset --role node --port "$GS_NODE_PORT" --device node-146393c5d158 --build /tmp/gs_r1_factory_node_hardware_aead --normal-app /tmp/gs_r1_node_normal_empty_aead/gs_hw_m1_node.bin --evidence /home/udaybhan/ghar_sajag_forensics/fresh_bench_node_retry_empty_aead_20261006 --confirm-development-disposal
```

The old 28 events are already archived/disposed. Rerun accepts their missing
snapshot, reports `development_events_discarded=0`, and advances the existing
Paired generation-1 association to authenticated Unpaired generation 2. It does
not invent ACKs or repeat event delivery. Normal boot must then load Unpaired
successfully and permit new Home enrollment. No manual NVS repair is needed.

## Operator-executed reset and re-enrollment

Check port names and physical MACs before running. Each evidence directory must
be new; old dumps/logs are never overwritten. Commands capture additional evidence
before explicit destructive DEVELOPMENT disposal.

```bash
python tools/factory/bench.py reset --role hub --port /dev/ttyUSB1 --device hub-5c013bbeb9f8 --build /tmp/gs_r1_factory_hub --normal-app /tmp/gs_r1_normal_hub/gs_hw_m1_hub.bin --evidence /home/udaybhan/ghar_sajag_forensics/fresh_bench_hub --confirm-development-disposal
python tools/factory/bench.py reset --role node --port /dev/ttyACM0 --device node-146393c5d158 --build /tmp/gs_r1_factory_node_hardware_aead --normal-app /tmp/ghar_sajag_r1_bat_c8_usb_console_qual/gs_hw_m1_node.bin --evidence /home/udaybhan/ghar_sajag_forensics/fresh_bench_node --confirm-development-disposal
python tools/factory/bench.py commission --hub-port /dev/ttyUSB1 --node-port /dev/ttyACM0 --device c3-146393c5d158 --evidence /home/udaybhan/ghar_sajag_forensics/fresh_bench_enrollment
```

Commissioning opens Node then Hub and waits for Node `HIL_READY` before requesting
the test QR/code. It sends one `COMMISSION_TEST_NODE` only after Hub `HIL_READY`,
native `HIL_DURABILITY owner=Ready`, and `Authenticated Hub owner started` have
been observed with matching storage epochs. It consumes startup output before
TX, records the command with the installer code redacted, checks every write,
and never automatically resends the command. RX evidence identifies `PRE_TX`
and `POST_TX`; panic, watchdog, storage failure or post-TX rejection stops it.
This is passive readiness observation: missing startup markers cause a timeout
without commissioning TX; the controller does not reboot either board to obtain
them. Use a new evidence directory for each operator-approved attempt.
Fresh Node automatically opens its commissioning window. Enrollment must show
`Authenticated rejoin device=c3-146393c5d158` and new Home binding.
If initializer readiness was missed, the tool times out without confirmation;
do not repeat destructive commands without reviewing the transcript.

## Original physical procedure (gate now closed)

Keep PIR LOW/quiet through enrollment. Use separate terminals for Hub and Node
capture; only one process owns each port. Retain all raw transcripts.

`bench.py command` runs serial I/O in a child and enforces `--seconds` from
the foreground parent. It creates a new evidence directory for each call under
`~/.local/state/ghar-sajag/factory-command/` (or under `--evidence-dir`).
`output.log` retains received lines; `status.json` reports classification,
elapsed time, port and worker PID. The parent returns even when USB teardown
leaves the child stuck in kernel D-state. A stuck child keeps a per-port lock,
so subsequent commands to the same alias fail without sending another command.
`SERIAL_WORKER_STUCK` requires transport release before retry; this tool never
detaches or reattaches a device. `USB_DEVICE_DISAPPEARED` is a transport result,
not evidence that the firmware rejected the command. The foreground exit code
is zero only for `NORMAL_COMMAND_COMPLETE`.

```bash
python tools/factory/bench.py command --port /dev/ttyUSB1 --seconds 120 GET_STATE | tee /home/udaybhan/ghar_sajag_forensics/fresh_bench_enrollment/hub-first-event.log
python tools/factory/bench.py command --port /dev/ttyACM0 --seconds 120 GET_STATE | tee /home/udaybhan/ghar_sajag_forensics/fresh_bench_enrollment/node-first-event.log
```

Before motion: initializer Hub evidence `owner=Ready epoch=1 generation=2
registry=native-empty records=4 migration=NONE`; normal boot `HIL_DURABILITY
owner=Ready ... native=1 migration=NONE`, `HIL_JOURNAL_RECOVERED records=0`.
Node `HIL_STATE ... retained=0 in_flight=0`. Trigger exactly one real PIR event.
Require Hub `HIL_EVENT_RESULT ... ack=0 state_changed=1 records=1` and
`Authenticated event ... ack=0 send=ESP_OK`; Node same key
`Application ACK ... class=0 retired=1`. Stop capture after convergence.

For deterministic physical lost-ACK replay, use the supervised operator flow
from the project directory. Close other serial readers first and keep PIR quiet:

```bash
python3 tools/factory/bench.py lost-ack-test --node-port /dev/ghar-sajag-node --hub-port /dev/ghar-sajag-hub --evidence-dir ../../docs/hw/evidence/R1_LOST_ACK_FINAL
```

The same isolated worker opens Node once, captures `NodeRuntime owner started`
and `PIR ready on GPIO4`, then opens Hub once. It additionally requires a live,
empty Node GET_STATE, Hub `HIL_READY`, and a captured journal record baseline.
Startup records must be observed in this invocation: an already-running board
may not repeat them. Missing records cause FAIL without an operator cue; the
tool does not reset a board to obtain them. It uses 115200 baud, 8N1, no flow
control, DTR/RTS false, advisory exclusive serial access, and shared supervisor
locks keyed by resolved device path to prevent factory-tool alias collisions.

Only an exact `HIL_OK command=REBOOT_AFTER_NEXT_DURABLE_COMMIT` prints the bell
and the large motion cue. Trigger one real motion then move away. The command
captures both streams and verifies one selected EventKey: unique durable commit,
ACK deliberately unsent, Hub journal recovery and HIL readiness after reboot,
Node retransmission, same-key durable duplicate without another record, and
Node `Application ACK ... class=0 retired=1`. It polls final GET_STATE after
retirement until queues are empty or the time budget expires. It never injects
PIR, commissions, flashes, erases, or issues a software reset command.

Each run creates a new `lost-ack-*` directory with raw `node.log`, raw `hub.log`,
operator `output.log`, and `status.json`. The status includes selected key,
before/unique/duplicate record counts, retirement, final state, additional events,
and partial proof checkpoints even if the parent stops a blocked child.
With no unrelated commits, duplicate records must equal unique records. If a
separate event legitimately commits between them, the raw global counts are
preserved and its independently proven one-record growth is reported separately;
the selected duplicate must itself add zero records. Garbled or incomplete
lines are retained but never treated as proof.

Defaults are 300 seconds overall (parent allowance of one second plus bounded
termination), 60 seconds per startup stage, 10 seconds for arm confirmation,
and 120 seconds from cue through convergence. Options `--seconds`,
`--ready-timeout`, `--arm-timeout`, and `--event-timeout` can bound an attempt.
Transport loss, a hung read/write/close, missing proof, or a failed invariant
returns nonzero with `LOST_ACK_TEST=FAIL` and a specific reason. A stuck worker
continues holding both factory locks until it exits. If a run fails after
arming but before the lost-ACK marker, the Hub one-shot may remain armed; the
tool reports this and does not reset or disarm it automatically.

The previous garbled Hub transcript contains NULs and missing log characters.
The checked Hub sdkconfig and host opener both specify 115200; the opener's
existing pyserial defaults were already 8N1 with flow control off. No physical
corruption cause is established by these artifacts. The old generic command
worker classified any nonempty arm-command output as completion; this flow
instead requires the exact arm confirmation before cueing the operator.

Focused offline validation:

```bash
python3 -m unittest tests.test_factory_lost_ack tests.test_factory_command_supervisor
```

PASS requires retained=0 and in_flight=0, all preceding markers, stable replay
key, no storage faults, migration, panic or synthetic ACK. Missing evidence is
NOT_RUN/PARTIAL, never PASS. Only then resume C8. The independent 128-slot lifetime
exhaustion bug remains open and must be fixed separately before R1 release.
