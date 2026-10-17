# GS-68 spare-S3 USB observer retest plan v1.0

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
Before a future session, revalidate the same PnP instance against that receipt
and verify that the selected COM port is owned by no other process. COM number
alone is insufficient.

## Transport prerequisite

Use one Windows-native session through the identity-pinned adapter. The
transport must verify the exact PnP instance, VID/PID and serial, check port
ownership, disable RTS/CTS and XON/XOFF, use bounded read/write timeouts, and
open at most once. It must not clear input buffers, reconnect, or request DTR or
RTS transitions. It must record observable line and port events.

The adapter fails closed unless a host provider proves that its Windows driver
does not pulse reset-related lines while opening the port. The current standard
pySerial/Windows behavior has not been qualified for that guarantee. Until a
provider supplies this evidence, the next physical observer session is
**BLOCKED**; no port may be opened by the test plan.

## Procedure after separate physical-access authorization

1. Capture host time, exact PnP identity receipt match, COM ownership result,
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

Stop immediately on PnP/COM mismatch, another process owning the port, reset
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
