# GS-68 spare-S3 USB observer retest plan v1.1

## Scope and fixture

This plan covers one auxiliary, read-only USB console observation on the
owner-designated spare ESP32-S3 N16R8. It excludes the protected C8 Hub and C3
Node. It is not an official GS68-PHY-001..010 case and cannot qualify DS
signing, mTLS, GS-68, or GS-40.

Installed TEST_ONLY image identity:

- Source commit: `cfc89a8e7bd6009eddde5790814e557357d8a032`.
- Full application artifact SHA-256: `855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`.
- ESP image-validation SHA-256 reported by READY: `d3d03609024b2b1ecf269150516bbfc08acd26f7caf9b220ab7f6a925b67e0b5`.
- Profile SHA-256: `7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72`.
- Effective sdkconfig SHA-256: `ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a`.

The artifact SHA protects the complete file. The READY digest is the ESP-IDF
appended image-validation hash over the image body. The observer now validates
the ESP32-S3 image structure, segments, checksum, appended hash, and source/build
provenance, then compares READY to the derived validation digest.

The board identity receipt and full PnP identifiers remain in private evidence.
The Windows provider resolves a COM name to a present PnP instance (instance
ID, VID, PID, device serial and driver version), then repeats the identity
comparison immediately before one native exclusive open. It does not use
pySerial, clear buffers, reconnect, or issue DTR/RTS calls. This is a
best-effort identity pin: COM enumeration and opening the COM name are separate
Windows operations, not an atomic device-instance-bound handle. Any PnP
removal, re-enumeration or substitution stops observation.

## Transport prerequisite

The provider uses bounded PowerShell PnP enumeration and a Win32 serial handle
opened with share mode zero, so another open handle is rejected by the one
actual exclusive open. A documented reliable PID lookup for an arbitrary COM
handle is not available here; pre-open owner status is **UNKNOWN**. A sharing
or access-denied result is `BUSY_OR_ACCESS_DENIED`, never retried. The provider
uses bounded read/write timeouts, disables hardware/software flow control and
refuses an inherited DCB that requests DTR/RTS control. It does not alter those
bits after open, clear input buffers, or reconnect.

Opening fails closed unless an external reset-safe policy callback binds
qualification evidence to the current PnP identity and driver version. No
qualified policy/evidence is present. The provider cannot observe DTR/RTS
transitions initiated internally by Windows/the driver; it records this
limitation. Microsoft documents that a serial resource inherits the previous
DCB at `CreateFile`; Espressif documents USB Serial/JTAG buffering and host-side
flush behavior and notes that the controller can enter download mode
automatically. Mock tests, DCB state after open, and duplicate startup
transcripts do not prove reset-free open or an actual reboot. COM10 remains
unopened and physical observation is **BLOCKED**. References:
[Microsoft serial resource settings](https://learn.microsoft.com/en-us/windows/win32/devio/modification-of-communications-resource-settings)
and [ESP-IDF 6.0.3 USB Serial/JTAG console](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32s3/api-guides/usb-serial-jtag-console.html).

Before a separately authorized physical observation, collect:

1. Windows build, active USB Serial/JTAG driver provider/version, exact PnP
   instance and COM mapping against the restricted spare receipt.
2. USB protocol capture (USBPcap/Wireshark or hardware USB analyzer) for the
   one authorized open, preserving CDC `SET_CONTROL_LINE_STATE` requests and
   timestamps. Correlate with Windows USB/driver ETW and visible reset/BOOT
   observation. Evidence applies only to that host/driver version.
3. Host monotonic timestamps, PnP remove/arrival, USB control transfers, reset
   reason, and a target boot-generation/uptime marker to distinguish buffered
   output from a new boot. The installed image lacks that marker; reset reason
   alone is insufficient. Identical startup bytes remain ambiguous.
4. Exact case/nonce/operation response correlation, bounded capture, and
   stop-on-reset/PnP substitution. Mocks do not satisfy this physical evidence.

## Procedure after separate physical-access authorization

1. Capture host time, exact PnP identity receipt match, owner status UNKNOWN,
   atomic exclusive-open result,
   reset-safe-open provider evidence, installed-image receipt, observer source
   commit, and candidate artifact hash. Abort on any mismatch, busy port, or
   failed driver policy.
2. Open the port once. Do not toggle DTR/RTS or clear buffers. Preserve every
   received byte, monotonic host timestamp, sequence number, and observable
   USB/control-line event in a private mode-0600 capture before parsing.
3. Drain at most 256 startup lines, each no larger than 16 KiB, within 30
   seconds and the 8 MiB / 8,192-line session caps. Retain ordinary ESP-IDF
   startup messages in order. Require one structured `GS68/1` READY frame with
   the expected source, profile, S3 capacity, spare identity and derived image
   validation digest.
4. Record READY reset reason and the observed startup transcript fingerprint.
   The installed image does not report boot generation or uptime. A repeated
   READY or repeated startup prefix is an unexpected observation and stops the
   test; classify the cause as **ambiguous replay/reset**, not as a confirmed
   reboot. Do not continue qualification after this event.
5. If startup is clean, send exactly one harmless `GS68-AUX-USB-001` OBSERVE
   command with a fresh 32-byte nonce. Allow one bounded response window of 10
   seconds. Require `event=command_result`, the exact case ID, exact nonce,
   `operation=OBSERVE`, and `result=OBSERVED_NO_ACTION`. Ordinary console logs
   may precede the response and remain in the private capture. Missing,
   malformed, mismatched, duplicate-READY, disconnected, or late responses are
   FAIL/BLOCKED and never PASS.
6. Close the single session once and hash the private raw capture, parsed event
   index, and observer report. Keep raw serial text and complete device
   identifiers outside Git/Jira; publish only redacted results and checksums.

## Stop conditions and exclusions

Stop immediately on PnP/COM mismatch, a busy/access-denied exclusive open, reset
line activity, unsafe/unknown driver-open behavior, USB removal, image mismatch,
unexpected READY/startup replay, malformed structured frame, timeout, or
response correlation failure. Do not retry, reconnect, reset, reflash, or
attempt rollback in this session.

This retest sends no signed-time proof, performs no `gs68time` NVS write, and
does not exercise PSA RNG, DS signing, mTLS, network access, production
credentials, or official physical cases. Any further physical USB access
requires separate explicit authorization for this exact fixture and plan.

## Expected outcome

The best possible outcome is **GS-68 auxiliary TEST_ONLY USB observation PASS**
for the single harmless OBSERVE command. Official GS-68/GS-40 physical
qualification remains NOT_RUN until its separately approved requirements and
cases pass on matched evidence. If future qualification needs decisive reset
attribution, add target boot-generation and monotonic uptime to a separately
source-bound firmware build; the current image cannot supply those fields.
