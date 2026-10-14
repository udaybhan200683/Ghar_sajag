# GS-114 S3 capture and liveness diagnosis — 2026-10-14

## Scope and preserved evidence

`BUG_CLASSIFICATION=TEST_INFRA_ONLY` for the demonstrated serial observation
failure. Product firmware liveness is still unverified after the observation
gap. No firmware, image, partition, commissioning, persistent data, security
setting, board power or reset was changed in this investigation. The only
serial request attempted was one non-destructive `FIXTURE_STATUS`; it blocked
before opening the stale descriptor and did not reach the Hub.

Canonical source and remote HEAD at investigation start were both
`cec251a96b30ca85ed1b256162b2a3f47317258b` on
`feature/r1-commercial-baseline`; context preflight passed at
`2026-10-13.001`. Existing untracked raw logs and unrelated files were
preserved. The installed C3 application remains the previously verified
SHA-256 `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
The exact *running* S3 application hash remains unverified.

## Timeline (UTC)

| Time | Direct observation |
|---|---|
| 08:35:48.443–08:35:48.465 | Last captured authenticated session-16 NodeHealth sequence 4 and schema-3 trace. The run04 S3 UART log stops at 20,354 bytes. |
| 08:37:40–08:37:43 | Windows System records WSL virtual-switch NIC disconnect/reconnect events. Windows `usbipd-win` Application event 3 records a transport socket abort (10053). Event 2 at 08:37:43 records client `172.17.152.10` releasing S3 USB `VID_1A86&PID_55D3`, serial `5CBC401023`, BUSID `3-1`. |
| ~08:40:48 | Next C3 300-second NodeHealth was due, but no S3 serial evidence was captured. |
| ~08:50:58 | The 910-second lease from the last authenticated health expired. No explicit Hub `online=0` line was captured. |
| 09:32:58 | One `FIXTURE_STATUS` attempt through the sole S3 reader's existing fd3 was logged. The writer blocked in kernel `usb_kill_urb` while opening `/proc/324978/fd/3`; it had no fd4 and sent no command bytes. No response or new capture bytes appeared. Signals were sent to prevent a delayed write; the process remained in uninterruptible D state at the last check. Do not repeat the request. |
| 09:33–09:36 | Read-only Windows `usbipd list` showed the exact S3 CH343 COM9 at BUSID `3-1` as **Shared**, no longer Attached to WSL. The C3 USB enumeration showed `0000:0002` descriptor error; that does not establish its radio/application state. WSL still exposed a stale S3 by-id link and `/dev/ttyACM0`, held by capture PID 324978. |

Raw process, descriptor, capture-hash, Windows state and WSL log snapshot:
`s3_status_probe_failure_20261014T0932Z.log` (local untracked evidence).
The original S3 UART log, `observer_commands.log`, reset recovery report and
earlier physical test reports remain preserved.

## What the evidence establishes

The immediate cause of **missing S3 UART evidence** is the Windows↔WSL USB/IP
transport release at 08:37:43 UTC. The capture shell was alive and still owned
a stale tty descriptor, so PID/port ownership alone was an invalid capture
health check. The socket abort occurred before the next expected C3 heartbeat.
The nearby WSL virtual-switch events support a host transport disruption, but
the initiating cause of the socket abort is not established.

Hub source checks show the owner loop evaluates authorized-node liveness every
1000 ms and logs a change; `HubRuntime::node_online` uses the authenticated
contact timestamp and configured 910-second lease. C3 source checks show the
300-second NodeHealth cadence, authenticated send, callback timeout and sleep
deadline handling. Existing focused host regressions cover cadence and lease
boundaries. No source finding or target evidence currently proves a C3 crash,
Hub deadlock, or firmware liveness defect. The missing `online=0` line is
expected from a broken observer even if the Hub remained active.

## Safe next action and acceptance

Do not request PIR motion while the S3 observation path is broken. Do not
reattach the C3 descriptor-error device, reset either board or flash firmware.
The old S3 capture and blocked writer must be accounted for before opening a
new serial reader. With operator authorization for the potentially disruptive
S3 serial operation, preserve/stop the stale S3 capture, verify the live Windows
identity and `Shared` state, reattach **only** identified S3 `1a86:55d3` / serial
`5CBC401023` to WSL, then establish one exclusive capture. Stop if identity,
port ownership or transport state differs or a serial open resets the Hub.

After transport recovery, require fresh `FIXTURE_STATUS`, authenticated C3
rejoin/NodeHealth schema 3 and trace, OPEN RPF admission and subsequent
heartbeat liveness before a controlled P3 stimulus. If C3 is genuinely silent
after restored Hub observation, investigate the Node from new evidence; no
second C3 reset is authorized. P3 remains BLOCKED / NOT RUN. P8 remains physical
NOT_RUN; P9 ACK/FOTA remain fixture-blocked. Prior RPF07/P1/P2/controlled
P4/P5/P6/P7 PASS evidence is preserved.
