# GS-68 spare-S3 USB observer retest plan v1.3 execution update

## 2026-10-17 — Replacement image session result and next correction

After the source-bound TEST_ONLY stack-buffer build below was installed once
app-only at measured OTA0 `0x20000`, Windows esptool v5.4.0 exited 0 and
reported `Hash of data verified.` The exact image was 278,480 bytes, full
SHA-256 `9558665c928ea2ee2910b9297cba9feacebd00730410c1094137d57ff49b8c04`,
ESP image-validation digest
`fb24ca983b3e16fefc6b6d9c71a40ce9f0a6d894832e898c852584e66d74de65`, source
`f7278f9746e756214502ac270dc8db43e6ab0489`, profile hash
`7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72`.
Only the app's sector range `0x20000..0x64000` was written. Esptool then
reported its requested hard reset via RTS; it did not modify bootloader,
partition table, OTA metadata, NVS, OTA1, journal or eFuses.

The following single COM observation session again matched the private spare
PnP parent receipt and opened exclusively once. It captured two complete
ESP-IDF startup log lines and then an incomplete `GS68/1` READY frame ending
mid-profile digest. The observer marked it truncated and sent no command.
There is no direct running-image identity result, fresh OBSERVE, malformed or
oversized recovery, sequential-command result, PSA-RNG result, or signed-time
result from this session. The private result bundle SHA-256 is
`1eb39f84351907b9097f841dd7be9f9a4302bba2923a3d1dd3f0b39e8e9ea84c`; its raw
console digest is
`bc3a6ed7dab78b3e76068c478ba00639059f4222c1f1ace72656f871e68104be`. The
prior image session's complete stack-overflow panic remains an observed failure;
this second transcript does not contain a complete panic or prove its cause.

The latest source correction raises the isolated GS-68 profile's main-task
stack from 3,584 to 8,192 bytes, in addition to moving its bounded input state
to static storage. This directly addresses the long READY/crypto call-path
stack-pressure hypothesis, but is not yet built, installed or physically
verified. No more serial session is permitted until that source-bound build is
validated and a replacement candidate is installed within the existing
spare-only authorization. Reset-safe driver behavior remains unqualified.
Auxiliary physical USB remains **FAIL/incomplete**; TEST_ONLY PSA RNG and
signed time remain **NOT_RUN**; official GS-68 and GS-40 acceptance remain
**NOT_RUN**.

## v1.2 owner-authorized execution amendment — 2026-10-17

The latest owner instruction authorizes a single controlled Windows-native
observation session on fixture `GS68-SPARE-S3-OWNER-DESIGNATED` only. It permits
the initial COM open to reset the spare; this is **reset-tolerant**, not
reset-safe qualification. The provider must retain current PnP-parent identity
matching, exact COM binding, one exclusive open, bounded I/O, no reconnect and
control-line evidence. Other fixtures retain the default fail-closed
reset-safe-policy requirement. No C8/C3, flash, eFuse, credential, production
endpoint or unrelated NVS operation is in scope.

The session accepts either a READY frame received after opening or no READY at
all. A received READY is compared to the installed image-validation digest and
source/profile/board identity; it is recorded as directly reobserved in this
session, without claiming that it proves a reset or excludes buffered replay.
If no READY arrives, the previously verified installation receipt must bind
source commit, complete image SHA-256, ESP image-validation digest and profile,
and its cited evidence files must pass checksum/content checks. In both cases,
qualification proceeds only when a new exact-nonce `OBSERVE` response arrives.
The report distinguishes `DIRECT_READY_REOBSERVATION` from
`INHERITED_VERIFIED_INSTALLATION_RECEIPT`.

After that first delayed/fragmented OBSERVE passes, run malformed-input
rejection plus valid recovery, oversized-input rejection plus recovery, and two
sequential ordered OBSERVE responses. If all USB cases pass, the same open
session may continue with the process-local TEST_ONLY RSA signer: target PSA
RNG challenge, signed-time proof/replay and negative proofs. Only the dedicated
TEST_ONLY `gs68time` state is in scope; no production trust anchor or live
network is used. A repeated READY during a command, PnP event, line-control
failure, mismatch or timeout stops the session. Reset-versus-buffer-replay
remains ambiguous because this image lacks boot-generation/uptime evidence.

This amendment supersedes v1.1's separate-authorization/reset-safe-open gate,
single-OBSERVE-only procedure and exclusion of TEST_ONLY signed time for this
one owner-authorized task. It does not qualify reset-safe Windows behavior or
official GS-68/GS-40 acceptance.

## 2026-10-17 — Owner-authorized single-session observation result

The spare was reidentified immediately before opening by Windows PnP parent
chain; the interface VID/PID and parent receipt matched the designated spare.
The transport performed one exclusive COM open, recorded port ownership as
UNKNOWN before the share-mode-zero open, and did not reconnect. Reset-tolerant
opening was used as authorized; reset safety was not claimed. The driver did
not expose DTR/RTS transition telemetry.

The prior verified installation receipt was accepted as inherited image
identity; this session did not receive a new READY frame. The session capture
contains an ESP-IDF `stack overflow in task main` panic signature and no exact
nonce-correlated OBSERVE response. The observer therefore recorded the USB
probe as FAIL and did not run malformed, oversized, sequential, PSA-RNG or
signed-time commands. The startup bytes do not establish whether the port open
caused a reset or whether they were buffered/replayed. No reset was confirmed,
and no second port opening was attempted.

The restricted private bundle SHA-256 is
`d241a196e3d5abd50691bb2c61f7f9e10d3c5c7ed15d01e82489de0553feb8d8`; the raw
console-record digest inside it is
`092cf5ea5395cd68723cd743382ceb923a5f5ed071695ccf1676803b95752c56`. No raw
console or full hardware identity is included here. The host observer now
fails immediately on recognizable ESP-IDF panic/abort startup lines instead
of sending a command after that evidence. The TEST_ONLY diagnostic moves its
bounded line accumulator and command buffer out of the 3584-byte main-task
stack as a software mitigation; a new non-flashing build is required to
validate this source change. The existing installed image remains unchanged.

Auxiliary USB physical result: **FAIL / incomplete**. TEST_ONLY PSA RNG and
signed-time physical checks: **NOT_RUN**. Official GS68-PHY-001..010, GS-68
physical acceptance and GS-40 physical acceptance remain **NOT_RUN**. Do not
reopen the port or claim the mitigation is effective until a new source-bound
image is separately installed under its approved bounded recovery procedure.

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

## 2026-10-17 — 8192-byte-stack candidate and owner-authorized physical session

The new non-flashing ESP-IDF 6.0.3 build used source commit
f501d985c1ce5b8b89f0786b42af6e5a179469cb and code-tree OID
cca5d51036e7a7da59f1b18f4b80fee26d814cd0. The image is 278,480 bytes,
full artifact SHA-256
fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd, and
ESP image-validation SHA-256
d60b1c4730e86dc4f1d0d8f034b5e3e170c10c0df6abae0d2399113920686346.
Profile SHA-256 is
d3a57024ecd0c8e0fda08f841d9aab14ca67b769d48610531ae464d747e0fd7c;
effective sdkconfig SHA-256 is
223c23490ffdf0a11bf24cda1984b3192355441ed03ede458c540bec5ae0535e.
It selects USB Serial/JTAG primary console and an 8,192-byte main task stack;
the target remains diagnostic-only, unprovisioned and network-disabled.

Candidate provenance initially failed because the expected TEST_ONLY
configuration omitted the new stack value. The validator and a negative
configuration test now include it. Candidate binding and install gates then
passed with no errors. The host-only follow-up delta allowlist also had omitted
the changed cloudsync runner test file; that narrow host-only path was added
with regression coverage. Neither correction changes firmware bytes. Focused
tests passed: test_gs68_aux_runners.py 41/41 and
test_gs68_cloudsync_runners.py 35/35. Commits d8ddb3f and 329a32c were
pushed to canonical.

Immediately before the single app-only install, Windows PnP COM10 VID/PID and
the parent chain matched the private designated-spare receipt. The stored
read-only partition-table, OTA metadata and 1 MiB recovery-image checksums
still matched. Prior ROM inspection recorded Secure Boot disabled, Flash
Encryption disabled, normal USB ROM download available, 16 MiB flash, and
OTA0 selected at 0x20000; no security configuration changed. Windows esptool
v5.4.0 used one --no-stub --connect-attempts 1 application write at
0x20000, with no force option. It returned 0 and Hash of data verified.
The write covered 0x20000..0x64000 only. Bootloader, partition table,
otadata, NVS, OTA1, journal and eFuses were excluded. The installed-image
receipt binds the write to the exact candidate digest above and the original
recovery capture. The private installation log SHA-256 is
6a28a9b6d15587c5b0bf87e3a0bc24f002783e1873163385ee0926d8a2f0844b.

The first one-open observation used a 15-second READY wait and received two
complete ESP-IDF startup lines followed by a 148-byte unterminated READY
prefix. It sent no commands and failed as truncated. A second single-open
session used a 30-second bounded startup wait. No complete READY was observed;
the session therefore did not claim fresh runtime digest verification. It
used the source-bound installation receipt as inherited image identity, then
required new exact-nonce-correlated application responses. COM ownership was
reported UNKNOWN before the atomic exclusive open; open succeeded. The driver
did not expose DTR/RTS transition telemetry. Reset-safety remains unproven and
no reset was confirmed.

The second session's auxiliary checks were recorded PASS:

- Delayed fragmented CRLF OBSERVE returned a correlated OBSERVED_NO_ACTION.
- Malformed and oversized command lines were rejected; the receiver processed
  valid commands after each rejection.
- Two sequential OBSERVE responses returned in request order.
- The silicon PSA RNG returned a fresh challenge with nonzero boot generation.
- TEST_ONLY RSA-3072/SHA-256 signed time verified with challenge nonce and
  generation binding; replay was rejected.
- Wrong nonce, invalid signature, expired proof and stale-generation proof
  were each rejected. The ephemeral signing key stayed in host process memory;
  only its TEST_ONLY public key was sent to target runtime memory.
- No production network or credential path was requested. Signed-time floor
  testing exercised only the diagnostic's dedicated gs68time store; no NVS
  dump or unrelated namespace operation was performed.

Evidence reconciliation found that the private orchestration script had loaded
the prior authorized-usb-session-fixture.json despite preparing a new
stack-8192 fixture. Consequently its raw result bundle reports the older
855b586d... image metadata. That original private result is preserved; it is
not silently rewritten. A separate mode-0600 adjudication binds the session to
the immediately preceding WRITE_HASH_VERIFIED receipt for the exact
fd072a... candidate, and records the mismatch, the original bundle hash and
the raw console-record hash. This supports the command/proof results and
application responsiveness but does not create direct READY/runtime-digest
evidence. The corrected private adjudication SHA-256 is
57a79d386e5a23ccd29c0facb9bf1a3956105ec9f9e98af3e126539e7a286023;
original runner bundle SHA-256 is
921ca86ff99dbdfd8a1933d69c393be69c58a65ee608212c6b95ff96dcdbcc0f;
raw console-record SHA-256 is
860fff2bb6fea3b59b8fa9af22ea4316f67de6eef9b0a965d66af862b36981fe.
Private transcripts, fixture identities, recovery bytes and ephemeral key
material remain outside the repository and Jira.

Auxiliary USB command and TEST_ONLY PSA/RSA diagnostics: PASS with inherited
install identity and the explicit runner-metadata reconciliation above.
Direct READY image identity: NOT_OBSERVED. Windows reset-safe opening:
NOT_QUALIFIED. Silicon DS signing and live mTLS: NOT_RUN. Official
GS68-PHY-001..010, GS-68 acceptance and GS-40 acceptance: NOT_RUN. The
installed TEST_ONLY candidate remains suitable for this bounded diagnostic;
no further firmware build or flash is indicated for the completed auxiliary
checks. A later formal physical qualification still needs a correctly
image-bound capture, reset/event correlation where required, certificate/DS
provisioning decisions, and the official case evidence. No C8 or C3 access
occurred.

Post-session hardening: the restricted orchestration script now selects the
stack-8192 fixture and checks fixture/build-report/install-receipt equality,
including checksums for each installation evidence artifact, before any PnP
or serial access. Its syntax was checked with py_compile. This post-session
guard was not used for, and did not alter, the preserved physical result; no
additional device session was run.
