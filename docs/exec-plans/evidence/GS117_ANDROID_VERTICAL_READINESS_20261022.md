# GS-117 Android sensor vertical readiness — 2026-10-22

## 2026-10-24 owner-authorized physical inspection — HEAD 44f53a1

The owner authorized this identified TEST_ONLY fixture session in GS-117
comment **11618**: Windows COM discovery, reset-aware serial inspection and
existing firmware/HIL queries for COM4 C3 (`14:63:93:C5:D1:58`) and COM10
owner-designated spare S3 (`E0:72:A1:D3:8D:34`). One C3 `INJECT_MOTION` is
authorized only after firmware eligibility and Home/Node/Hub security and
delivery prerequisites verify. Flash, eFuse, NVS, credential and ownership
changes are explicitly excluded without separate compatibility/state/recovery
proof.

Immediately before inspection, local and remote canonical HEAD were
`44f53a1d0026ef61a6bdc84416050044809fc4bd`; context preflight passed. Windows
PnP found COM4 and COM10 present with status OK. `usbipd` showed both native
Espressif USB Serial/JTAG interfaces as Shared; no ownership handoff or detach
was needed. The existing Windows helper's read-only `List` matched each exact
COM number, USB hardware ID and USB serial. Both single-port serial opens
succeeded, which is evidence that no conflicting exclusive open blocked them
at those instants. DTR/RTS were requested low before open; no control-line
telemetry was available, so this does not qualify reset-safe behavior.

The COM4 C3 returned `HIL_OK command=GET_STATE` and
`HIL_STATE role=c3 session=20 retained=0 in_flight=0 sensing_live=0
runtime_live=0 pending_inject=0 heap=197956 min_heap=189708 ota_slot=ota_0`.
The observed HIL state did not include the required power-mode/build/control/
physical-wake flags, and no current firmware version or startup receipt was
captured. This proves the query interface answered, but does not prove
`HIL_AWAKE_TEST_ONLY` or injection eligibility. The runtime/sensing readiness
values are both false (`sensing_live=0`, `runtime_live=0`), a further stop
condition for motion injection.

The existing C3 HIL-awake build artifact remains SHA-256
`2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f` with
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`, and
`GS_BAT_C8_PHYSICAL_WAKE=OFF`; this artifact is not evidence of the installed
image.

The COM10 S3 opened once and received a `GET_STATE` request, but the bounded
redacted observer captured no allow-listed startup/status line and no HIL
acknowledgement. This is not a current firmware identity or S3 product-runtime
receipt. The latest recorded install evidence remains the spare's TEST_ONLY
GS-68 diagnostic image, which is not full HubRuntime + CloudSync and has no
provisioned DS identity. The S3 query was attempted once. No retry/reopen
followed the missing response, consistent with the existing bounded one-open
observer stop rule.

The laptop backend health was checked again: PostgreSQL, caregiver HTTPS and
LAN TLS passed, but physical Hub ingress remains `NOT_CONFIGURED`, Hub identity
is unauthenticated and monitoring freshness is unknown. The existing local
Home/Hub/Node enrollment is synthetic. No Android Debug Bridge or current
phone-install receipt is available. Thus the authenticated S3-to-backend path,
physical ownership/enrollment, same-Home APK connection and APK event view
remain unverified.

| Stage | Result | Evidence |
|---|---|---|
| Exact Windows COM/USB identity | `PASS` | COM4 and COM10 match the identified fixture serials and PnP entries. |
| C3 status-query transport | `PASS` | One open and `GET_STATE` acknowledgement; no exclusive-port conflict. |
| C3 current image / HIL-awake / injection eligibility | `NOT_VERIFIED` | Runtime flags/version missing; `sensing_live=0`, `runtime_live=0`. |
| S3 current image / product HubRuntime | `NOT_VERIFIED` | No captured startup/status response; historical image receipt is diagnostic-only. |
| Physical S3 CloudSync / authenticated ingress | `BLOCKED` | Existing backend health says ingress `NOT_CONFIGURED`; physical identity/trust/time/ownership binding absent. |
| C3 motion injection / new EventKey | `BLOCKED` | Not issued because C3 runtime and authenticated S3/backend prerequisites did not verify. |
| PostgreSQL / caregiver API / APK for a fresh physical event | `NOT_VERIFIED` | No new physical EventKey; phone origin/Home and APK observation unavailable. |
| TC-001 | `BLOCKED` | Inspection only; no injection or event delivery claim. HOST_SIM seed remains excluded. |

No flash, reset command, eFuse action, NVS write, credential operation,
ownership mutation, USB/IP detach or database mutation was issued. A serial
open can have reset effects; available evidence does not establish the
reset-line behavior of either port in general. Physical TC-001 remains
`NOT_RUN`, not PASS. Preserve existing events and GS-114 qualification status.

After inspection, existing software guard regressions ran without hardware
access: TC-001 console **17/17**, GS-179 verified endpoint **2/2**, and C3
HIL-awake/sleep profile **4/4** passed. Context preflight and
`git diff --check` passed. These checks do not promote the physical stages.

## 2026-10-24 full physical E2E readiness audit — HEAD 5328c31

Local and remote canonical HEAD were `5328c313918db7f7086752d2c9838a2ec8ccd460`;
preflight passed. The canonical worktree had no tracked changes before this
evidence update. Existing untracked Android assets, S3 components/configuration,
backups, hardware evidence and ignored build outputs were left untouched.

### Board and console observations

Passive `usbipd`, sysfs and owner-local fixture records reconfirm COM4 / BUSID
`3-1` / `ttyACM0` / USB serial `14:63:93:C5:D1:58` as the documented C3, and
COM10 / BUSID `3-2` / `ttyACM1` / USB serial `E0:72:A1:D3:8D:34` as the
owner-designated spare ESP32-S3. Both USB devices are currently attached to
WSL. No process holds either WSL TTY, but neither TTY was opened. The existing
Windows helper's read-only `List` action returns `[]`; Windows SerialPort also
reports no COM ports while USB/IP ownership remains in WSL. No `usbipd detach`
was attempted because it would change device attachment and may cause USB
re-enumeration/reset behavior. The existing Windows console therefore cannot
currently control these boards through its COM path.

Windows and WSL have no `adb`; Windows reports `ADB_NOT_INSTALLED`. No phone
debugging device was present in the passive USB inventory. The exact owner-only
TC-001 fixture receipt and phone-install receipt are absent. The console's
gates for current firmware receipts, reset-safe UART, full S3 product image,
Hub ingress and APK/Home origin consequently cannot be satisfied.

### Firmware, recovery and identity evidence

The existing C3 HIL-awake candidate is present and rehashed at 950,032 bytes,
SHA-256
`2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f`; its
ESP-IDF cache confirms target `esp32c3`, `GS_HIL_BUILD=OFF`,
`GS_HIL_CONTROL=ON`, `GS_BAT_C8_PHYSICAL_WAKE=OFF`. The separate normal
sleep-enabled candidate is 940,608 bytes, SHA-256
`eec59be390315bad53e05bb7c3c60e0fd3311ec16a11d19040d3ad36ef4c733b`, with
`GS_HIL_CONTROL=OFF`. Both are build artifacts only. No current C3 image,
partition table, active OTA slot, installed mode or firmware version was
observed; the HIL candidate is not known installed.

An owner-local Oct 9 C3 full-flash backup manifest records a digest match at
backup time for USB identity `14:63:93:C5:D1:58`, prior association to Hub
`hub-5c013bbeb9f8`, logical Node `hil-signed-fota` and seven retained pending
records. This is a historical 4 MiB full-flash snapshot, not current-image
readback or an app-only rollback image. Restoring it could replace newer NVS
and retained-event state. It is not approved or safe to use as a rollback for
the current board. Current pending EventKeys remain unknown and untouched.

The Oct 17 COM10 receipt remains the latest S3 install record: diagnostic
profile `GS68_CLOUDSYNC_DS_MTLS_HIL`, image SHA-256
`fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd`, DS
peripheral selected but not provisioned. It is not evidence of the current
running image or full product HubRuntime/CloudSync. The Oct 9 S3 backup is a
16 MiB full-flash/NVS/VFS set predating that later app install; it is not a
verified current app-only rollback. No board image or storage was changed.

The existing local TEST_ONLY database was inspected in a PostgreSQL read-only
transaction. Its configured caregiver profile is `GS179_TEST_ONLY` for
`gs177-test-product`; that database has active synthetic Hub
`test-hub-product`, active Node `test-c3-bedroom`, and one pre-existing event
row. This row is the historical HOST_SIM seed and is not TC-001. The Oct 9 C3
snapshot's Hub/Node identity differs from those TEST_ONLY enrollment identities.
This establishes no current physical Hub/Home/Node binding; no ownership,
commissioning or enrollment mutation was made. Other retained test fixtures
were not changed.

### Current service, APK and test status

The live laptop health check still reports TLS-verified PostgreSQL, caregiver
HTTPS, local backend and certificate-verified LAN endpoint `PASS`. The only
listener observed is caregiver HTTPS on the existing WSL port. Operator config
contains no Hub-ingress enablement, Hub client-certificate registry,
trusted-time/authority source or physical Hub/Home/epoch/Node binding. Existing
caregiver/PostgreSQL certificates are not a Hub client identity. The GS-179
runtime requires injected `TEST_ONLY` credentials, trusted time and authority
refresh; its synthetic integration subprocess is not an operator trust source.
No safe lifecycle-only adapter can make the physical path work without
inventing or provisioning those missing security authorities, so none was
added or enabled.

The owner-reported APK Connected state remains unverified. Its installed
package/version, HTTPS origin, authenticated Home and event rendering were not
observable without ADB or an existing phone receipt. The local TEST_ONLY
caregiver configuration is not evidence that the installed APK uses it.

Focused software validation on the existing implementation passed: TC-001
console **17/17**, C3 HIL-awake/sleep profile **4/4**, and GS-179 verified
endpoint **2/2**. The GS-179 configuration/TLS-boundary suite passed **21**
tests; its isolated runtime/mTLS/PostgreSQL E2E was skipped because no dedicated
test DSN was configured. No live caregiver database was used as a test DB.
These are software checks, not physical or phone acceptance.

| Stage | Result | Evidence |
|---|---|---|
| C3 USB identity | `PASS` | Exact documented USB serial; no current image or safe live observer. |
| S3 USB identity | `PASS` | Exact owner-local spare-S3 receipt; not the historical GS-114 S3 fixture. |
| Windows TC-001 serial discovery | `BLOCKED` | Windows helper sees no COM ports while both devices are attached to WSL. |
| C3 HIL candidate | `PASS` | Existing candidate hash/flags verified; installed image, slot and rollback remain unknown. |
| S3 full product firmware / identity | `NOT_VERIFIED` | Only historical diagnostic image and unprovisioned DS receipt. |
| Local backend/PostgreSQL | `PASS` | Existing TLS and durability health checks pass. |
| Physical S3 ingress / CloudSync | `BLOCKED` | No provisioned physical Hub identity or persistent authorized ingress configuration. |
| Physical C3-to-Hub enrollment | `BLOCKED` | Local TEST_ONLY enrollment is synthetic and does not match the C3's historical pairing snapshot. |
| APK backend/Home/event display | `NOT_VERIFIED` | No phone-side install/origin/Home observation or ADB connection. |
| TC-001 | `NOT_RUN` | No serial open, injection, new EventKey, Hub delivery, commit or APK observation. |

No hardware operation, firmware deployment, reset, USB ownership change,
credential issuance or database write occurred. Existing GS-114 passive-only
authorization remains narrower than live firmware query, injection, flash or
re-enrollment. The full blocker and recovery plan is consolidated in this
section; the earlier stage-specific evidence below remains historical.

## 2026-10-24 receipt reconciliation at canonical HEAD 063007d

This read-only update corrects the earlier 2026-10-24 note below that left
COM10 unmatched. It does not change the earlier restriction on opening either
serial port or the scope of prior hardware approvals.

Current local and origin HEAD are both
`063007ddd1f0256cf4e45c533122f1cb7a49b280` on
`feature/r1-commercial-baseline`; context preflight passed. The canonical
worktree has no tracked modifications. Existing untracked Android assets,
S3 `managed_components/` and `sdkconfig`, hardware evidence, and ignored build
outputs were preserved. Historical worktrees remain read-only references.

Fresh `usbipd.exe list` and Linux sysfs metadata show COM4 / BUSID `3-1` /
`/dev/ttyACM0` / USB serial `14:63:93:C5:D1:58`, and COM10 / BUSID `3-2` /
`/dev/ttyACM1` / USB serial `E0:72:A1:D3:8D:34`; both are native Espressif
USB Serial/JTAG devices and attached to WSL. The COM4 serial matches the
documented C3 identity. COM10 is positively identified as the separate
`GS68-SPARE-S3-OWNER-DESIGNATED` ESP32-S3 by the owner-local fixture receipt
`GS68-20261017/stack8192-authorized-usb-fixture.json`, which binds COM10,
USB serial/MAC `E0:72:A1:D3:8D:34`, 16 MiB flash and 8 MiB PSRAM to that board.
This is a spare S3, not the historical GS-114 CH343 S3 (`5CBC401023`). No
serial interface was opened; `fuser` found no process holding either WSL TTY.
These are identity/metadata checks, not current running-image or reset-safety
proof.

The latest recorded app-only image receipt for this spare S3 is dated
2026-10-17: SHA-256
`fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd`, source
commit `f501d985c1ce5b8b89f0786b42af6e5a179469cb`, profile
`GS68_CLOUDSYNC_DS_MTLS_HIL`, profile SHA-256
`d3a57024ecd0c8e0fda08f841d9aab14ca67b769d48610531ae464d747e0fd7c`, status
`WRITE_HASH_VERIFIED`. The profile selects the DS peripheral but explicitly
records `ESP32_DS_PERIPHERAL_SELECTED_NOT_PROVISIONED`; it is diagnostic/test
firmware, not the full product HubRuntime + provisioned CloudSync composition.
This receipt is historical and does not prove the image currently running.
No fresh image, OTA slot, trusted-time, Hub ownership/epoch, Node enrollment or
CloudSync session query was made.

The laptop health check was rerun. PostgreSQL (TLS `verify-full`), caregiver
HTTPS, local backend and certificate-verified LAN endpoint report `PASS`;
phone-side reachability is `NOT_VERIFIED`. The Hub-ingress runtime reports
implemented but autostart `DISABLED`, Hub identity `NO`, monitoring freshness
`UNKNOWN`, persistent ingress `NOT_CONFIGURED`, and readiness
`NOT_CONFIGURED`. The caregiver WSGI process serves the existing Home/API and
database; it does not mount or start the separate GS-179 Hub-ingress runtime.
The operator `server.env` has caregiver service settings but no Hub listener,
Hub client-certificate registry, trusted-time/authority provider or Hub/Home/
epoch/Node enrollment configuration. The existing integration test helper
uses synthetic TEST_ONLY registry/time fixtures and explicitly is not an
operator service or physical-device credential source. Turning on the flag
alone would therefore fail closed and would not safely configure a real Hub.
No replacement listener, credential, ownership entry, network rule or service
was created.

Focused GS-179 runtime-configuration and PostgreSQL/TLS boundary regression
completed: **21 passed, 1 skipped** across
`test_gs179_runtime_composition` and `test_gs179_postgres_security`. The
skipped case is the registered runtime-process/mTLS/PostgreSQL E2E, which
requires a separate `GS179_TEST_POSTGRES_DSN`; that isolated database was not
configured, and the live caregiver database was not used as a test database.
These software checks exercise default-disabled/configuration guards and TLS
failure boundaries; they do not prove physical Hub mTLS or CloudSync delivery.

The owner-reported APK `Connected` remains a report only. No Android Debug
Bridge is available on this host and no phone-side receipt identifies the
installed APK's HTTPS origin, authenticated user or Home. The current laptop
backend's healthy API and PostgreSQL therefore cannot be assumed to be the
backend/Home used by the phone. No new Home, account, APK or backend was made.

| Integration stage | Result | Evidence / limitation |
|---|---|---|
| C3 identity | `PASS` | COM4 USB serial matches the documented C3 identity; current firmware/profile and safe control path remain unverified. |
| S3 identity | `PASS` | COM10 exactly matches the owner-local GS68 spare-S3 receipt; this is identity only. |
| Current S3 image / product CloudSync | `NOT_VERIFIED` | Only the Oct 17 diagnostic image receipt is available; no current readback or active-image evidence. |
| Laptop backend / PostgreSQL | `PASS` | Existing health reports TLS-verified service and database readiness. |
| GS-179 software security regression | `PASS` | 21 passed; registered isolated runtime/PostgreSQL E2E skipped because no isolated test DSN was configured. |
| Physical Hub mTLS ingress | `BLOCKED` | No persistent composition, provisioned Hub identity, issuer/trust registry, trusted-time authority or ownership/enrollment binding is configured. |
| APK backend and Home identity | `NOT_VERIFIED` | Owner-reported Connected only; app origin, authenticated Home and phone reachability not observed. |
| Fresh physical event / durable EventKey / APK display | `NOT_RUN` | No serial command, injection, Hub transfer, database event query or phone observation occurred. HOST_SIM seed is excluded. |

### Consolidated minimum-risk physical plan

1. Obtain fixture-specific authorization for **read-only current-image and
   configuration inspection** of exact COM4 C3 and COM10 spare S3, naming the
   no-reset observer/transport. COM4 serial open has prior reset evidence;
   without independently verified reset-safe observation, use a physically
   reviewed passive UART tap or stop. COM10's historical GS68 authorization
   covered the recorded diagnostic install/query only, not a current TC-001 or
   product-CloudSync session.
2. Before any S3 update, obtain separate authorization for the exact app-only
   product/test image hash, measured active OTA app slot, expected reboot,
   preservation of bootloader/partition table/NVS and Hub state, and a verified
   app-only rollback image plus recovery method. The Oct 17 write receipt is
   not a current readback; the historical pre-update backup must be matched to
   the running image before it is considered a rollback candidate. An image
   write can make the Hub unavailable until recovery and the current app image
   must not be overwritten without that match.
3. Separately authorize the TEST_ONLY Hub identity path: certificate issuance
   and private-key location, backend client-CA and exact Hub fingerprint
   registry, authenticated trusted-time/authority source, existing Home/Hub/
   installation epoch and active Node-enrollment binding, plus a private
   ingress bind/reachability plan. Do not use APK signing material. Preserve
   the same backend, Home, credentials, trust roots and event history.
4. Verify the existing APK's origin/user/Home on the actual phone and confirm
   it reaches the same PostgreSQL-backed caregiver API. Only then run the
   existing TC-001 console: one fresh C3 injection, correlate its original
   EventKey through the identified physical S3 and mTLS ingress, verify exactly
   one durable record and caregiver projection, then observe the same event in
   the installed APK. Any phone-side evidence is `USER_CONFIRMED` unless an
   existing safe Android automation connection provides direct observation.

The required gates are the exact fixture/inspection authorization and reset-
safe path; any app-only firmware update and recovery authorization if the
current S3 image is unsuitable; TEST_ONLY identity/trust/time/ownership
configuration approval; and phone-side APK/Home evidence. No hardware or
credential operation was performed. The old “COM10 unmatched” classification
in the sections below is historical and superseded by this receipt
reconciliation.

## 2026-10-24 fresh physical/backend recheck — read-only

Starting checkpoint was canonical `feature/r1-commercial-baseline` HEAD
`44f384afaa3d3efd1c7fb48d220cf3d6f6e1dcf8`, matching origin; context
preflight passed. Existing untracked Android assets, S3 `managed_components/`
and `sdkconfig`, historical hardware evidence, and ignored build outputs were
preserved. The listed noncanonical worktrees are historical; no other canonical
R1 worktree was created.

`usbipd.exe list` and Linux USB sysfs metadata (no serial open) show COM4 / BUSID
`3-1` / `/dev/ttyACM0`, VID:PID `303a:1001`, USB serial
`14:63:93:C5:D1:58`, and COM10 / BUSID `3-2` / `/dev/ttyACM1`, same VID:PID,
USB serial `E0:72:A1:D3:8D:34`. COM4's USB identity matches the documented
historical C3 fixture identity. COM10 is not the documented S3 fixture's
CH343 serial `5CBC401023` and cannot be assigned as the S3 from its COM number
or generic Espressif descriptor. Thus C3 USB mapping is `PASS` (metadata match),
S3 identity is `NOT_VERIFIED`. `usbipd` reports both interfaces attached to
WSL; `fuser` found no WSL process holding either TTY at the snapshot. This does
not establish reset-safe open behavior or a Windows-side owner check. Neither
serial interface was opened.

No fixture-safe current-image query was established. The source's `HIL_READY`
startup record and read-only `GET_STATE` response include firmware version and
power/HIL flags, but both require the serial control path. Existing GS-114
evidence records a C3 `USB_UART_CHIP_RESET` during serial observation and
explicitly rejects assuming that lowering DTR/RTS after open prevents reset.
The documented future candidate is a receive-only, high-impedance UART0 TX tap
with no DTR/RTS/reset connection after the exact board revision, pin routing and
electrical path are verified; that path is not established on this fixture and
would not itself provide a live `GET_STATE` query. Current installed image,
partition/OTA slot, HIL flags and sleep state therefore remain
`NOT_VERIFIED`.

The existing ignored HIL-awake image is present and rehashed at 950,032 bytes,
SHA-256 `2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f`
(`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`). The separately built normal sleep image is
940,608 bytes, SHA-256
`eec59be390315bad53e05bb7c3c60e0fd3311ec16a11d19040d3ad36ef4c733b`.
Neither is installed. Because the running C3 image, active slot and preserved
rollback image are unknown, whether an update is needed is `NOT_VERIFIED` and
there is no safe exact app-only deployment/rollback package yet. If later
required, approval must name the matched C3, candidate hash, existing authorized
app-only transport, expected reboot, verified prior-image recovery path, and
preservation of bootloader, partition table, NVS, credentials, enrollment and
retained events. No update or reboot was attempted.

Latest GS-114 authorization remains Jira comment 11145: Stage 1 read-only
preflight only, and stop before opening an interface whose reset behavior is
uncertain. TC-001's exact local `fixture.json` and phone-install receipt are
absent. The historical `code/tools/hil/gs130_fixture.json` contains the old
pair identities and artifact provenance, not current flash readback or current
approval. No serial command, sensor stimulus, flash, reset, commissioning or
ownership change is authorized by those records.

The fresh `gs179-laptop-server.sh health` check reports PostgreSQL, caregiver
HTTPS, backend and certificate-verified LAN endpoint `PASS`; Hub-ingress source
is implemented, but autostart is disabled, authenticated Hub identity is `NO`,
monitoring freshness is `UNKNOWN`, and persistent ingress/readiness are
`NOT_CONFIGURED`. The live S3 image/configuration, trusted-time source,
Hub/Home/epoch ownership and Node enrollment cannot be read through the safe
interfaces available. Real S3 CloudSync-to-backend is therefore `BLOCKED` at
ingress readiness and has no physical receipt. The prior GS-68 evidence says
the production trust provider is fail-closed when unprovisioned; it does not
identify this board's installed state.

The owner-reported existing APK `Connected` state is retained as owner report,
not app verification. Current health reports phone-side reachability
`NOT_VERIFIED`; neither WSL nor Windows exposes `adb`, and the physical APK's
backend origin and authorized Home could not be matched to this laptop backend.
No second APK, Home or account was created or changed.

| TC-001 stage | Result | Evidence |
|---|---|---|
| C3 USB mapping | `PASS` | COM4 serial matches documented C3 USB identity; firmware/runtime not inferred. |
| S3 identity | `NOT_VERIFIED` | COM10 descriptor does not match historical S3 adapter identity. |
| C3 installed HIL-awake profile / safe serial | `BLOCKED` | No current image receipt; no demonstrated reset-safe query path or exact fixture receipt. |
| New C3 EventKey / authenticated ESP-NOW / S3 durable admission | `NOT_VERIFIED` | Injection was not run; no physical source event. |
| S3 CloudSync / authenticated backend ingress | `BLOCKED` | Existing listener is not configured/authenticated for a physical Hub. |
| PostgreSQL and caregiver backend health | `PASS` | Current service health only; no event row was created or correlated. |
| Same Home on actual APK / event display | `NOT_VERIFIED` | Owner-reported Connected only; no phone-side origin/Home/EventKey observation. |

No new EventKey exists. The preserved HOST_SIM seed
`test-c3-bedroom / session 10 / sequence 1` is not a physical event and was not
reused. TC-001 remains `NOT_RUN`; Android acceptance is not claimed.

## 2026-10-24 C3 USB-serial / HIL-awake audit

The C3 sleep audit found an existing reusable awake profile; no new sleep flag
or second power-management implementation was added. Use the product-runtime
profile `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`. `GS_HIL_CONTROL` is default OFF. The existing
`physical_wake_permitted()` gate keeps this profile from entering light sleep;
the runtime continues its normal 20 ms `kPirPollMs` delay while sleep is
ineligible. EventKey, ESP-NOW/security, storage, retry/ACK and normal production
sleep paths are unchanged. `INJECT_MOTION` remains compile-time disabled when
`GS_BAT_C8_PHYSICAL_WAKE=ON`; the console now requires the running `GET_STATE`
to report `power_mode=HIL_AWAKE_TEST_ONLY hil_build=0 hil_control=1
physical_wake=0` before it sends the existing injection command. The console
displays the claimed image profile before observation and the reported active
mode after the read-only status stage.

Read-only USB discovery on 2026-10-24 found Windows USB/IP devices COM4 and
COM10 attached to WSL, exposed as `/dev/ttyACM0` and `/dev/ttyACM1`. Their
native Espressif USB Serial/JTAG serial IDs are `14:63:93:C5:D1:58` and
`E0:72:A1:D3:8D:34`. The first matches the historical C3 USB identity; the
second is not independently matched to the expected S3 identity. No serial
device was opened. Current running firmware, HIL flags, partition/OTA slot,
sleep state, and current Home/Hub enrollment therefore remain unverified.
Current exact per-fixture approval/image receipts are absent, and the existing
GS-114 approval permits passive enumeration only; it explicitly stops before
opening a possibly resetting serial interface. No `GET_STATE`, injection,
flash, or reset was performed.

The C3 CloudSync chain is distinct from the APK's “Connected” report. Owner
reports that the existing APK previously showed Connected; this was not
verified from the phone in this run. A fresh owner-laptop health check shows
PostgreSQL, caregiver HTTPS and the local backend `PASS`, while phone-side
reachability is `NOT_VERIFIED`; Hub ingress autostart is disabled, authenticated
Hub identity is absent, persistent ingress is not configured and Hub monitoring
freshness is unknown. No S3-to-backend CloudSync success is claimed.

Build/deployment plan: produce and hash the profile above using ESP-IDF 6.0.3
into a unique ignored build directory; separately build production defaults
with `GS_HIL_CONTROL=OFF`, `GS_HIL_BUILD=OFF`, and
`GS_BAT_C8_PHYSICAL_WAKE=OFF`. Do not use a blind serial flash command. If the
current C3 image lacks the required HIL flags or status report, first obtain
separate explicit approval for the identified C3, exact candidate hash, allowed
app-only update method, expected reboot and recovery plan. Preserve bootloader,
partition table, NVS, credentials, enrollment and active data; use only an
already authorized app-only update path and stop if no such path is documented.
Then verify running hash/profile and reset-safe serial behavior before creating
the fixture receipt or running TC-001. The S3 is not to be changed for this
serial-availability issue.

Focused software coverage: TC-001 console 17/17, verified endpoint 2/2, C3
profile 4/4, BAT-C8 invariants 11/11, validation framework 51/51, feature
traceability 22/22 and physical catalogue 111 cases PASS (`device_access=NONE`).
The non-flashing ESP-IDF 6.0.3 C3 HIL-awake build passed at 950,032 bytes,
SHA-256 `2497e6bbecc0f8b09954c9e3ac83b994b17f72621abb19eddd719d5dda4df67f`.
Separate normal sleep-enabled C3 build passed at 940,608 bytes, SHA-256
`eec59be390315bad53e05bb7c3c60e0fd3311ec16a11d19040d3ad36ef4c733b`. Each
fits the configured 1,966,080-byte smallest app partition. Build caches and
images are ignored under `code/build/gs117-c3-*`; neither image was installed.

These tests verify the existing sleep-gate matrix, idle task delay, unchanged
retry/durable-ACK paths, repeatable software orchestration and fail-closed
behavior for missing/wrong mode evidence. Physical idle serial availability and
repeated board injections remain `NOT_RUN`; GS-114 sleep/wake qualification
results and optical PIR evidence are unchanged.

## 2026-10-24 delivery checkpoint and next action

Implementation commit `15b983ef604cd9fc6ba2ab9f8865d64f0f5bec84` is pushed to
`feature/r1-commercial-baseline`; `git ls-remote` matched that SHA before this
documentation-only checkpoint. Context preflight passed on that source.
Jira updates: [GS-117 comment 11602](https://udaybhan200683.atlassian.net/browse/GS-117)
and [GS-114 comment 11603](https://udaybhan200683.atlassian.net/browse/GS-114).
Tracked source/test/docs for the implementation commit are clean. Existing
untracked Android assets, S3 `managed_components/` and `sdkconfig`, historical
hardware evidence and ignored C3 build outputs remain preserved; none were
staged or removed.

Exact next action: obtain separate fixture-specific approval for no-reset
current-image/OTA identity inspection and the exact C3/S3 serial endpoints;
then complete current installed-image and ownership receipts without sending
an HIL command. If the C3 does not report the built HIL-awake profile, separately
authorize a documented app-only update with an expected reboot and recovery
plan, preserving partition table, NVS, credentials and enrollment. After
rechecking idle serial availability, repeated injection and reset-safe behavior,
complete the existing authenticated GS-179 Hub-ingress identity/listener and
phone-install receipts for the same Home, then run TC-001 and verify the new
EventKey on the existing Android APK. Do not alter the distinct GS-114 optical
PIR or battery qualification gates.

## Scope and checkpoint

This is a bounded readiness checkpoint for the first genuine
`REAL PIR → C3 → authenticated S3 → backend → Parivar Saathi Android APK`
event. No board was opened, reset, stimulated, flashed, or accessed over USB or
serial. No listener, Windows network rule, firewall, router, Render service, or
customer data was changed. No real Hub credentials were installed. No physical
event was generated, so there is no EventKey or caregiver event to correlate.

The canonical worktree is `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, at `ec9076aa1326999de32d5ecc1e8ceb055cdff96e`,
matching the live origin at the start of this checkpoint. Tracked source was
clean, context preflight passed (`2026-10-13.001`), and the existing 301
untracked and 174,518 ignored assets were preserved. The full Jira inventory
contains 173 issues. GS-117 was To Do and Rank 52 at task start; it was moved to
In Progress for this active execution, without changing Rank. GS-114 remains
ahead at Rank 31 and In Progress. GS-60 remains To Do.

The runtime/test/catalogue/work-state implementation was committed as
`32460ef93dac3695a84467e8a6d84efcfef080e4` and pushed normally to the canonical
branch; origin matched that commit after push. GS-117 remains In Progress and
its Rank is unchanged. Jira comments 11528 (GS-117) and 11529 (GS-179) record
the update and remaining physical gates.

## Existing / reuse / gap / minimum change / Jira owner

| EXISTING | REUSE | GENUINE GAP | MINIMUM CHANGE | JIRA_OWNER |
|---|---|---|---|---|
| C3 PIR sensing, EventKey and authenticated Node transport are implemented; current physical C3 identity, image, slot, session and pending-event state are unverified. | Existing C3 event and retained-delivery path; GS-130 motion observer/HIL tooling. | No current-image or genuine AM312 GPIO4 trigger evidence; no qualified current no-reset observer. | Before target observation, owner must identify fixture/current image and approve a reset-safe observer; separately authorize one optical PIR stimulus. | GS-117, GS-40, GS-114 |
| S3 ESP-NOW admission, durable journal and CloudSync source exist; S3 production composition defaults to `UnprovisionedS3CloudTrust`. Current board/image, Hub identity, epoch, Node enrollment, trusted time and CloudSync session are unverified. | Existing S3 production-domain admission/CloudSync, GS-40 health and GS-109 authority contracts. | No verified currently authenticated physical Hub or approved current Home/Hub/epoch/Node authority for this run. GS-D032 leaves production identity/registry/receipt mechanisms unresolved. | Security/authority owner must supply or approve the exact identity, trust, Home/epoch, enrollment and trusted-time inputs for the selected isolated or commercial profile. Do not install or invent them. | GS-40, GS-68, GS-109, GS-148 |
| GS-148 durable PostgreSQL API and GS-179 TEST_ONLY runtime composition exist. Local PostgreSQL health currently passes. Runtime defaults to disabled and loopback. | Existing `TestOnlyMtlsListener`, durable COMMITTED/EventKey transaction, trust/readiness callbacks and caregiver projection. | Before this checkpoint, runtime composition rejected a private bind even though the listener supported guarded RFC1918 binding. No persistent Hub ingress is configured; real Hub authentication is `NO`; monitoring freshness is `UNKNOWN`. | Added an explicit TEST_ONLY opt-in requiring `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1`, a specific RFC1918 IPv4 address and a fixed port. Runtime remains disabled by default; no listener/network was activated. | GS-59, GS-148, GS-179 |
| Laptop caregiver HTTPS and PostgreSQL are running and healthy. Existing Windows forwarding/certificate/profile still use `192.168.1.6`; current Windows Wi-Fi is `192.168.1.10`. | Existing no-cost WSL2 service and Android LAN TEST_ONLY profile. | Current phone route is blocked by address mismatch; the GS-179 mTLS ingress is not composed into an externally reachable service. | Network owner must choose the exact laptop address and authorize coordinated certificate/origin/forwarding changes. Reuse the current service and database. | GS-58, GS-59, GS-179 |
| GS-177 Android APK and shared Home/Activity authorization/UI exist. Latest identified APK targets Render, not laptop PostgreSQL. | Existing APK, shared UI, Home authorization and API; no UI redesign is indicated. | Physical phone’s installed binary cannot be independently identified from this workspace; the APK artifact’s backend differs from the laptop’s database. | Once the approved same-backend HTTPS origin, matching SAN/CA and route exist, build only the existing GS-177 LAN TEST_ONLY variant and have the owner verify/install it. | GS-177, GS-117, GS-60 |
| GS-130 physical case and existing HIL runners exist. | `gs130_motion_hil.py`, `gs130_board_hil.py`, `gs130_hil_common.py`, and `gs40_qualification.py`; no new HIL framework. | `PHY-GS117` has no current physical run or current image/fixture receipt. The historic serial capture is not current proof. | Use the existing accepted GS-117 plan after the fixture and observer gates; preserve unique evidence and distinguish REAL_SENSOR from HOST_SIM. | GS-117, GS-121, GS-130 |

A minimal source correction was justified: the existing runtime exposed a bind
host setting but categorically rejected the private address needed for an
authorized WSL2-to-LAN Hub route. The new opt-in delegates to the listener's
existing private-bind guard and still rejects wildcard, public, non-RFC1918,
IPv6 and ephemeral-port private bindings. It does not configure or attest
network isolation. The remaining blockers are current hardware, trust, network
configuration and operator authorization; the source change alone does not
establish a physical event.

## Observed product path and readiness

```text
AM312 optical movement / C3 GPIO4          NOT VERIFIED — physical fixture not inspected
  → C3 sensing and EventKey                REAL SOFTWARE EXISTS; no current target/image evidence
  → authenticated ESP-NOW to S3            REAL SOFTWARE EXISTS; no current physical session evidence
  → S3 durable admission / CloudSync       REAL SOFTWARE EXISTS; current Hub trust is unverified
  → laptop application-terminated mTLS     SOFTWARE IMPLEMENTED; TEST_ONLY, disabled; RFC1918 binding opt-in added
  → local PostgreSQL COMMITTED             HOST_SIM evidence exists; no physical source event
  → authorized caregiver projection        REAL LOCAL SERVICE READY; no same physical event
  → Android Home/Activity                   APK artifact exists; physical installed binary not verified
```

Latest local `code/tools/local/gs179-laptop-server.sh health` reported:

```text
POSTGRES_READY=PASS tls=verify-full durability=fsync,synchronous_commit,full_page_writes
CAREGIVER_HTTPS_READY=PASS tls=ca_and_ip_san_verified
LOCAL_BACKEND_READY=PASS
PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH expected_address=192.168.1.6 observed_address=192.168.1.10
HUB_INGRESS_RUNTIME_IMPLEMENTED=YES
HUB_INGRESS_AUTOSTART=DISABLED
HUB_IDENTITY_AUTHENTICATED=NO
HUB_MONITORING_FRESHNESS=UNKNOWN
PERSISTENT_HUB_INGRESS=NOT_CONFIGURED
HUB_INGRESS_READY=NOT_CONFIGURED
```

Read-only Windows inspection found the existing forwarding row
`192.168.1.6:443 → 172.17.152.10:8444`; Windows Wi-Fi currently reports
`192.168.1.10`. The public metadata of the local Android HTTPS leaf has
`CN=192.168.1.6`, IP SAN `192.168.1.6`, and issuer
`Ghar Sajag GS-179 Local Android TEST ONLY CA`. No network setting or
certificate was changed. Render's currently live caregiver service is on
commit `3c0fec898d5cb2caae662f3dcc6324faaabf6b30`; its deployed WSGI entry
only calls `connected_lite.build_app()`. Render terminates incoming TLS before
the app, so it cannot provide a verified Hub TLS peer to the existing
application-terminated Hub mTLS listener. No forwarded identity header is
accepted as a substitute.

The latest identified Android workflow is
[run 39711096218](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39711096218),
successful for source `acde2183c74351db403b49b441deea67a3474142`. Its artifact
metadata reports package `in.gharsajag.caregiver`, version
`0.4.0-connected-lite-staging`, origin
`https://parivar-saathi-lite-staging.onrender.com`,
`gs179_local_lan_test_only=0`, and runner-generated testing-only debug signing
(an uninstall of a differently signed build may be required). APK SHA-256 is
`fa0a53b7f9cff822e27409701d7b60d78f142f08989d8362e672594d1f5e8c72`.
The owner reports installing the latest available APK, but no handset package,
version, signer or active Home/API response was read during this checkpoint.
That Render-targeted APK does not share the laptop PostgreSQL data source.

The only inspected S3 receive-only physical capture is dated 2026-10-16 and
records source HEAD `d738dc51a25e72de570a11fc39f0e26522ead3d8`; it is historical
and not evidence of the currently installed S3 image or its effective config.
GS-114 attempt06 is also historical. No current C3/S3 identity, running image,
partition/slot, pending EventKey journal, Home/epoch, enrollment, trusted-time
readiness, live Hub credential, AM312 wiring, operator, or reset-safe observation
method was verified. No serial port was opened.

## Validation and evidence classification

Read-only deployment/fixture checks included `git rev-parse HEAD`,
`git ls-remote`, `tools/context/ghar_sajag_context_preflight.sh`, the local
laptop `health` command, Windows IP/portproxy reads, public TLS certificate
metadata, current Render deployment metadata, and Android workflow artifact
metadata/hash. No browser session, APK installation, HIL `--observe` or `--run`,
Node input injection, or hardware operation was run.

The implementation change is in `code/backend/ghar_sajag/gs179_hub_ingress_runtime.py`
and its registered integration test. The new setting defaults off; private
binding requires `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1`, a specific RFC1918
IPv4 and fixed nonzero port. Public, wildcard, non-RFC1918, IPv6, private port
0, invalid flag values and missing opt-in are rejected. The existing complete
runtime process E2E continues to use loopback; no private-address socket was
opened in this validation.

Focused results:

- First `make -C code gs179-postgres-e2e` attempt: **exit 2**, expected guard
  because `GS179_TEST_POSTGRES_DSN` was absent from the shell environment.
- Rerun with the existing mode-0600 local server config and its local,
  hostname-verified TLS DSN, whose fixture creates/drops isolated random
  schemas: **51/51 PASS**, `physical=NOT_RUN`. This includes 18 GS-178
  Node-origin vertical cases, 15 security cases, 14 GS-179 PostgreSQL/lifecycle
  cases and 4 runtime-composition cases. The source-linked EventKey evidence is
  HOST_SIM only; private-bind validation tests configuration rules, not a LAN
  socket or real Hub.
- `make -C code validation-framework-test`: **51/51 PASS**.
- `make -C code feature-coverage-test`: **PASS**, 223 features, 278 modules,
  26 physical cases; mapping tests **22/22 PASS**.
- `git diff --check` and `PHY-GS117` CSV schema/status assertion: **PASS**.

These results establish the existing source-linked isolated software path and
the new private-bind fail-closed configuration behavior. They do not establish
REAL_SENSOR, REAL_HUB, current target firmware, or physical Android acceptance.
There is no physical EventKey, PostgreSQL receipt, caregiver record, duplicate
count, source-health transition, or Android presentation for this checkpoint.

`PHY-GS117` remains `NOT_RUN`. The catalogue now names the Android APK as the
physical caregiver endpoint per owner direction; browser checks remain
supporting shared-UI evidence only. GS-117, GS-60, GS-121 and GS-114 acceptance
remain open. No commercial release claim is made.

## Exact next action and gates

1. The fixture owner identifies the exact C3/S3 fixture and confirms the
   installed images, partition/slot, pending state, Home/Hub/epoch/enrollment,
   PIR wiring and operator. The owner separately approves a named, reset-safe
   passive observer and the single genuine optical PIR stimulus. The historical
   COM9/CH343 receive-only session is not reused as current observer approval.
2. The security/authority owner supplies the already-approved client/server
   trust, current Hub/Home/epoch and Node enrollment, revocation state and
   trusted-time source for the selected isolated or commercial profile. No
   credential issuance, Home claim, epoch mutation or installation is implied
   by this checkpoint.
3. The network owner confirms whether `192.168.1.6` is reserved for this laptop
   or approves a coordinated new origin. Any Windows IP, forwarding/firewall,
   private-bind runtime configuration/activation or certificate change requires
   its own exact approval. If approved, the runtime's RFC1918 setting is
   `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1` together with a specific address
   and fixed port. The caregiver APK and Hub ingress must reach the same
   PostgreSQL authority; Render is not a verified mTLS ingress path.
4. Only after those gates, configure and start the already-implemented GS-179
   runtime with the approved inputs; verify the Android CA-pinned origin and
   owner-installed APK; then perform one real PIR event and correlate its
   original EventKey through Hub COMMITTED and the Android Activity. Perform the
   second PIR event only after the first one passes.

The next physical step is blocked on those fixture, trust/authority, trusted
time and network approvals. Do not substitute HOST_SIM or a direct backend
insert, and do not infer a real Hub connection from local PostgreSQL or HTTPS
readiness.

## 2026-10-23 — TC-001 injected-motion console checkpoint

**Scope:** GS-117 TC-001 with GS-179 TEST_ONLY backend. This is an injected
sensor stimulus on a physical C3, separate from the genuine optical PIR case
`PHY-GS117`. No current board was opened, reset, flashed, stimulated or
commissioned in this checkpoint. Starting canonical branch/HEAD and origin
were `feature/r1-commercial-baseline` /
`f5b2042bf36ebd01da85dc147ae2ae3e873c9c2f`; context preflight PASS at
`2026-10-13.001`. The tracked worktree was clean at start. Existing untracked
Android/build/evidence assets and historical worktrees were preserved.

| Reuse class | Finding | Action |
|---|---|---|
| Implemented/reusable | C3 `INJECT_MOTION` enters `hil_inject_motion`; NodeRuntime owns EventKey/retry/ACK. S3 full product composition owns authenticated radio, durable HubRuntime and CloudSync. GS-179 owns TEST_ONLY mTLS, PostgreSQL and caregiver APIs; GS-177 owns APK UI. GS-130 owns existing HIL evidence rules. | The controller issues only the existing C3 command and reads the existing DB/API. No new event pipeline, ingress API or store. |
| Implemented/configuration gap | GS-179 laptop PostgreSQL and caregiver HTTPS pass; Hub ingress remains disabled/unconfigured, no authenticated physical Hub identity. WSL cannot resolve the Windows `.local` name in Node's Playwright request worker. | The browser helper now routes API fetches through the current Wi-Fi IP with the owner-private CA and current certificate IP SAN; Python keeps the original `.local` SNI and hostname validation. Existing `browser` command passes against the one prior HOST_SIM event. No ingress was activated. |
| Implemented/physical proof missing | Source HIL flags do not prove the installed C3 image. The source S3 composition does not prove the installed S3 image, Node enrollment, trusted time, ownership or TLS credential. | The console refuses the Run path without a current fixture-specific image/USB/approval receipt and authenticated ingress receipt. |
| Genuinely missing | Local one-click test UI, multi-run orchestration and stage/evidence ledger. | Added localhost-only TC-001 console, Windows COM helper, read-only PostgreSQL/API helper, bounded run history and explicit phone confirmation. |

The existing `browser` command initially failed on WSL `.local` DNS. A first
Chromium-only resolver rule left Playwright's separate Node request worker
unresolved; routing that worker through the current IP with CA/IP SAN
validation reached the real API. Two subsequent assertions had stale GS-177
UI copy/markup expectations; they were updated to assert the current TEST_ONLY
label and device-state attribute. The final command exited 0 with
`HOST_SIM_PASS`, preserved EventKey `test-c3-bedroom / 10 / 1`, one displayed
event and authorized Home API responses. This result is not a TC-001 physical
or Android result.

**Use after prerequisites:** Double-click
`code/tools/local/GS117-TC001-Console.cmd` from Windows, open
`http://127.0.0.1:18791/`, then press **Run Test**. The launcher starts the
controller in the canonical WSL worktree and starts only the already-installed
GS-179 caregiver systemd service if inactive. It does not refresh Windows
network rules or activate Hub ingress. Windows Python 3 with pyserial is used
for exact COM access. No PowerShell execution-policy change is needed.
The console binds only to loopback, checks Host/Origin and an ephemeral CSRF
token, accepts one active run, bounds serial/backend waits, and stores each
sanitized report under owner-only `~/.local/state/ghar-sajag/gs117-tc001/`.
It never invokes the GS-179 one-time seed helper or deletes prior data.
Immediately before injection, a read-only PostgreSQL lookup also requires
the selected Hub to remain ACTIVE for the exact Home/installation epoch and
the physical C3/logical bedroom Node to have one ACTIVE enrollment. The
recorded enrollment generation must match the new durable commit. On the
existing HOST_SIM seed authority, this read returned `authority_ready=true`,
generation `1`, and the preserved key `[10,1]`; it does not establish a
connected physical Hub.

The owner-only `~/.config/ghar-sajag/gs117-tc001/fixture.json` must be mode
0600 and contain `schema_version=1`, `test_id=TC-001`,
`profile=GS179_TEST_ONLY`, `home_id=gs177-test-product`,
`logical_node_id=bedroom`, the exact TEST_ONLY `physical_device_id`,
`hub_id`, positive `installation_epoch`, a dated fixture `approval_ref`,
`expected_caregiver_origin` as the current verified HTTPS `.local` name,
`approval_scope="C3 GET_STATE and INJECT_MOTION; C3/S3 UART observation"`, and
`reset_safe_uart_verified=true`. Each `c3`/`s3` object must name its exact
Windows `port`, `usb_hwid`, `serial_number`, local image path/SHA-256,
`firmware_source_head` and `installed_image_receipt`; the C3 additionally
needs `hil_control=true`, `hil_build=false`, `physical_wake=false`, and the S3 needs
`full_product_composition=true`. Both installed-image receipts must contain
matching target/USB/source/running-image hash, installation date and a
timezone-aware observation within 24 hours, plus active OTA slot, partition
table hash and measured flash capacity; the S3 receipt must also identify its
N16R8 PSRAM capacity. `hub_ingress_receipt` must name
the verified GS-179 TEST_ONLY Hub/Home/epoch, enrolled Node, both certificate
fingerprints, trusted-time readiness, authenticated physical Hub identity and
an active persistent listener, observed within 24 hours. These receipts are
operator evidence, not automatically issued credentials or proof invented by
the console. Do not create them until the corresponding real checks and
fixture-specific approval have occurred.
The separate `phone_install_receipt` must record the installed TEST_ONLY APK
package, public signer SHA-256, exact backend origin, authorized Home and a
timezone-aware observation within 24 hours; the console still requires
post-run confirmation that the *new* event appeared on that phone.

The Win32 read-only pyserial scan found only `COM10` at this checkpoint; it
returned one USB identity and no second board interface. The current fixture
approval/image receipts are absent. `gs179-laptop-server.sh health` returned
PostgreSQL `PASS`, caregiver HTTPS `PASS`, Wi-Fi TLS endpoint `PASS`, but Hub
ingress `NOT_CONFIGURED`. No `adb` executable was found. The console smoke
check returned HTTP 200 for status, HTTP 403 for missing CSRF, and a TC-001
run report `BLOCKED` at environment before opening serial. This report is
software guard evidence only. No new physical EventKey exists. The older
`test-c3-bedroom / session 10 / sequence 1` is the preserved HOST_SIM seed,
not a TC-001 result.
Local source C3 CMake defaults keep `GS_HIL_CONTROL=OFF`; the HIL command is
disabled in physical-wake builds. A historical ignored C3 GS-114 P9 signed
image and an untracked S3 `sdkconfig` using a development partition table are
present but do not identify either installed board or establish its OTA slot.
The S3 product CMake rejects `GS_HIL_CONTROL`; no diagnostic-only Hub image is
used by TC-001. These local artifacts were inspected read-only and preserved.

**Stage acceptance:** A valid run must see `HIL_OK`, one new C3 NodeRuntime
session/sequence, the same authenticated S3 event with durable ACK, a new
matching PostgreSQL row carrying the exact Hub identity, ownership epoch and
Node enrollment generation, and one authorized caregiver API presentation.
This source-linked durable commit is the CloudSync delivery evidence; a row
without ownership provenance fails that stage. Android remains `NOT_VERIFIED`
until explicit operator confirmation of the exact new EventKey in the actual
APK, recorded as `USER_CONFIRMED`; a browser PASS cannot fill this stage.
Receipt-loss recovery, cross-Home negative physical testing, repeated physical
runs, installed APK identity and genuine PIR remain `NOT_RUN`.

**Validation:** focused TC-001 console tests **15/15 PASS**, verified-endpoint
tests **2/2 PASS**, HIL catalogue **8/8 PASS**, GS-120 exact registry
**6/6 PASS**, the read-only GS-179 backend/API probe, registered feature
mapping and the live GS-179 browser helper were executed. Final aggregate
gate results and exact Git checkpoint are recorded in the dated Jira update.
The browser result was `HOST_SIM_PASS`
for the preserved event only. The new `PHY-GS117-TC001` case remains
`NOT_RUN` and is distinct from optical `PHY-GS117`. Release qualification is
`NOT_RUN`, and no RC/commercial promotion is implied.

Adjacent gate triage before correction:
`BUG_CLASSIFICATION=TEST_INFRA_ONLY`,
`REQUIREMENT_SOURCE=docs/validation/MASTER_VALIDATION.md`,
`DECISION_IDS=NONE`,
`TASK_SCOPE=TC-001 physical traceability and affected validation`,
`OUT_OF_SCOPE=GS-177 visual payload optimization`.
The required HIL catalogue checker treated an existing GS-177 semicolon-separated
pair of evidence paths as one filename, so the tooling gate failed even though
both files exist. It now validates each path separately; its focused suite
passes 8/8 and the existing catalogue status remains unchanged. The same
initial tooling run also failed the pre-existing Phase 3A CSS byte budget
(`29,576` actual vs `18,432` maximum). That UI performance problem is not
altered by TC-001 and is recorded as an unresolved component-gate failure,
not a PASS. No rule, threshold or assertion was weakened.
The backend component gate also found the GS-120 diagnostic registry test's
exact expected list had not been updated for four already registered GS-58/75
stages or the two new TC-001/GS-179 stages. The test's exact expected set was
updated while preserving its parent-stage no-loss assertion; its focused
registration suite passes 6/6. This is `TEST_INFRA_ONLY` within affected
registry validation, not a diagnostic product change. The backend gate's
`p0-full-product-e2e` stage still fails its required product-status check:
26/26 scenario assertions pass, but `product_status=PARTIAL` and physical
qualification remains `NOT_RUN`.
The PWA gate's actual Chromium stage passed **86/86**. Its GS-177 connected
Lite API stage passed **22/22** and diagnostic-foundation passed **98/98**
after the additive registry correction. Its separate GS-68 offline browser
stage failed before running tests because this WSL Python lacks the
`websocket` package. The aggregate PWA gate therefore remains **FAIL**;
the P0 stage also remains **FAIL** with 26/26 scenario assertions and
`product_status=PARTIAL`. These unrelated environment/product gaps are not
claimed as TC-001 physical evidence.
The isolated `make gs179-postgres-e2e` regression passed **55/55** with
`physical=NOT_RUN`, using the existing owner-local dependency paths and
temporary isolated PostgreSQL schemas. Its first attempt failed before tests
because that shell omitted the packaged `psycopg` path; the corrected rerun
passed. No historical business event was modified.

At the precommit handoff checkpoint, local and origin HEAD were both
`f5b2042bf36ebd01da85dc147ae2ae3e873c9c2f` on
`feature/r1-commercial-baseline`. Only the reviewed TC-001, GS-179 endpoint,
traceability, affected test-registry and dated handoff files were changed.
Pre-existing untracked/ignored Android, firmware build and historical
evidence assets were preserved. The dated GS-117/GS-179 Jira comments carry
the pushed implementation SHA and final remote verification.

**Next exact action:** Obtain the exact C3/S3 fixture and reset-safe UART
authorization; independently verify current running images, HIL flags,
partition/slot and Node/Home/Hub/epoch enrollment. Configure the existing
GS-179 TEST_ONLY mTLS ingress only after its identity, trust and trusted-time
inputs are approved and present. Verify the installed APK package/signer,
backend origin and authorized Home on the phone. Then complete the owner-only
receipts and run TC-001. Preserve all stored events and the separate optical
PIR qualification gate.

### 2026-10-24 current-source C3 HIL-awake deployment — HEAD 60574c4

**Authorization:** Owner explicitly authorized current-source HIL-awake
TEST_ONLY C3 app firmware on COM4 / `14:63:93:C5:D1:58`, including the
expected app reboot, after partition, compatibility and recovery verification.
No S3 write, whole-chip erase, eFuse, NVS, credentials, enrollment, ownership
or database mutation was authorized or performed. The inactive C3 OTA app
partition alone was erased/written by the app-only update. COM10 identity
inspection used the expected read-only `flash-id` reset and wrote no S3 flash.

**Build:** Context preflight passed (`2026-10-13.001`) at
`60574c4d3b98ded68bd18df611335afea48862fc`. ESP-IDF 6.0.3 C3 HIL-awake
candidate version `60574c4-gs117-hilawake-20261024`, 945,584 bytes,
SHA-256 `d1e7f89d473d3443b4b0380a53764f7521e88df2a452251f8a326656a8d74136`;
flags `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`, `IDF_TARGET=esp32c3`. A separate normal
sleep-enabled C3 image built from the same source, with HIL control disabled;
it was not installed. GS-114 physical-wake/battery qualification is
unchanged.

**App-only installation:** Live COM4 identity was rechecked as ESP32-C3 rev
0.4 / 4 MiB XMC flash. The live partition table matched the candidate. Before
the update, `ota_0` was active, `ota_1` was entirely erased, and a complete
`ota_0` readback was preserved under the ignored build directory. The
bootloader matched a build with rollback support enabled; it was not written.
The existing `otatool.py write_ota_partition` wrapper failed before writing
because of its `input`/`input_file` parameter mismatch. The ESP-IDF
`parttool.py write_partition --partition-name ota_1` then erased/wrote only
the blank inactive app slot, and the full slot readback matched the candidate
byte-for-byte. `otatool.py switch_ota_partition --slot 1` changed the OTA
selector in `otadata`; it did not touch application data in NVS.

The installed app reported `ota_slot=ota_1`,
`power_mode=HIL_AWAKE_TEST_ONLY`, `hil_build=0`, `hil_control=1`,
`physical_wake=0`. Windows COM4/USB identity remained stable during 27
read-only `GET_STATE` queries spanning approximately 15–132 seconds, with
stable later heap values. However, `sensing_live=0` and `runtime_live=0`
throughout. The source marks NodeRuntime owner-start only after its
authenticated Hub session/channel path; the current authenticated Hub
readiness is therefore not established. Do not issue `INJECT_MOTION` until
that gate and the console's owner-only fixture receipts pass.

COM10 was independently identified read-only as ESP32-S3 rev 0.2 with
16 MiB flash / 8 MiB PSRAM. Its running firmware composition is still
unverified. The existing console's owner-only fixture file is absent, and its
read-only backend readiness reports PostgreSQL, caregiver HTTPS, local
backend and LAN TLS `PASS`, but Hub ingress `NOT_CONFIGURED`. No TC-001
injection/EventKey/database event/APK event was generated. The existing
HOST_SIM seed remains historical only.

The untouched `ota_0` image is available for manual selector restoration.
Automatic rollback is not claimed: the external selector switch preserves
the prior OTA image-state field rather than setting `ESP_OTA_IMG_NEW`, and no
automatic return to `ota_0` occurred during observation. If recovery is needed,
use the official ESP-IDF selector to return to slot 0; do not erase the device.

Focused tests passed: C3 USB-stable profile **4/4**, TC-001 console **17/17**.
The normal sleep-enabled C3 image built successfully and was not flashed.
`make -C code validation-node` completed with exit **2**,
`software_status=FAIL`, `physical_status=NOT_RUN`, and source unchanged.
The C3 HIL profile stage passed **4/4**; 29 other registered stages passed.
`p0-full-product-e2e` remains a gate FAIL because `product_status=PARTIAL`
while physical qualification is `NOT_RUN` (all 26 scenario assertions
passed). `gs178-node-caregiver-e2e` ran 33 tests and failed one existing
browser assertion: `[data-event-key]` expected 2 elements and found 0 in
`test_07_actual_shared_caregiver_browser_and_actions`; product source was
unchanged. Host board-stack simulation passed 10 groups but is not physical
evidence. Build outputs and readbacks are ignored/local and are intentionally
not staged. Full hashes, flash ranges and stage evidence are in
[`GS117_C3_HIL_AWAKE_FLASH_20261024`](../../hw/evidence/GS117_C3_HIL_AWAKE_FLASH_20261024/README.md).

**Next exact action:** Before any TC-001 injection, establish the running
S3 product image and authenticated Hub/Home/epoch/Node relationship, configure
the existing approved TEST_ONLY ingress, verify trusted time/mTLS, install
fresh owner-only C3/S3/APK/ingress receipts, and confirm C3 `runtime_live`
advances. Then use the existing console for one controlled motion and verify
the same original EventKey through the physical S3, durable backend and actual
Android APK. Preserve both OTA application slots, the current Home and all
stored events.

## 2026-10-24 S3 authenticated-session and configurable-infrastructure policy

**Source checkpoint:** canonical branch `feature/r1-commercial-baseline`,
local/remote HEAD `afc248610f897882482bad0d2eb830bd37b61a3b`; context preflight
PASS (`2026-10-13.001`). Tracked files were clean before these documentation
edits. Historical worktrees were left untouched. Existing untracked Android,
firmware `sdkconfig`/managed-component and hardware-evidence assets were
preserved.

**Live S3 identity/image:** Windows COM10 / WSL `/dev/ttyACM1` and USB identity
`E0:72:A1:D3:8D:34` identify the owner-designated ESP32-S3 rev 0.2 with 16 MiB
flash and 8 MiB PSRAM. One reset-aware, read-only `esptool` inspection read the
partition table/OTA selector and active application; it made no write. The
partition-table SHA-256 is
`101adada9e724af39b0ff503d609f7cf90378f5aa3a6be03799ba695160337d9`;
`ota_0` is selected. It has two 4 MiB OTA app slots and the existing 2 MiB
`gs_journal` partition. The 278,480-byte active image SHA-256 is
`fd072a0a02729fb7c0f2cadb27a30b4cbb3ef6c8f5d2dee89fa2f9049a33b8dd`; its
ESP-IDF image hash is
`d60b1c4730e86dc4f1d0d8f034b5e3e170c10c0df6abae0d2399113920686346`. The
active image readback exactly matches the owner-local Oct 17 GS-68 installation
receipt: `GS68_CLOUDSYNC_DS_MTLS_HIL`, source
`f501d985c1ce5b8b89f0786b42af6e5a179469cb`, diagnostic-only composition,
DS selected but not provisioned. Receipt path:
`~/.local/share/ghar-sajag/GS68-20261017/stack8192-installed-test-image-receipt.json`.
Readback files remain in the mode-0700 owner evidence directory
`~/.local/share/ghar-sajag/GS117-20261024-readonly/`; NVS-containing bytes are
not copied into the repository. The physical board is not running the full
`gs_r1_s3_hub` product HubRuntime image.

**C3/S3 session result:** no authenticated C3↔S3 session was demonstrated. The
C3 HIL-awake image was not rebuilt or reflashed. Its most recent state had
`runtime_live=0`, `sensing_live=0`; source confirms NodeRuntime admission
begins after `security_link.ready()` and authenticated channel setup. The live
S3 image is diagnostic-only, not HubRuntime, so this is an S3 composition
blocker rather than evidence of a C3 firmware defect. Current physical Node
enrollment and Home/Hub/ownership-epoch binding are not verified. No serial
motion command was issued.

**Cloud/backend/APK:** product S3 CloudSync cannot be inferred from the
diagnostic image. Existing `GS40_TEST_ONLY_CLOUDSYNC` is default-OFF, rejects
diagnostic-only composition and composes the existing full product Hub with
the isolated software-key TEST_ONLY trust path. Its config-root public DER and
one-session envelope are explicit inputs; secret fields are memory-only. The
GS-179 backend remains healthy for TLS-verified PostgreSQL, caregiver HTTPS
and APIs, but Hub-ingress autostart is disabled and no physical Hub credential/
registry, trusted-time authority or Home/epoch/Node binding is configured. The
one HOST_SIM event remains historical and is not TC-001. The installed APK's
package, backend origin, authorized Home and current event projection are not
verified on the phone; ADB is unavailable.

**Policy applied:** owner direction is product-first, configurable supporting
infrastructure. Existing JSON inputs are narrow (`node_health.json`,
`service_access.json`, Home configuration); compile-time feature flags and
target-profile CMake options already exist. No general JSON infrastructure
feature map was found, so no second flag system was added. Advanced provisioning
automation, credential lifecycle and fleet management remain outside TC-001.
The existing S3 TEST_ONLY profile stays explicitly opt-in; authentication,
TLS, trusted identity/time, ownership and durable event rules remain mandatory.
GS40 test credentials remain ephemeral; no NVS secret persistence is
introduced. This policy does not approve the separately PROPOSED `GS40T/1`
contract details, create an identity, or authorize S3 flash.

**Regression:**
`make -C code gs40-test-only-bootstrap-test gs40-config-test cloudsync-security-ut rejoin-host-test p2d-https-channel-host-test p2d-cloud-contract-host-test`
exited 0. Results: TEST_ONLY bootstrap 47 checks; JSON NodeHealth configuration
17 tests; CloudSync mTLS adapter 9, TEST_ONLY adapter 5, trust-provider 5
suites; backend CloudSync security 14, identity/time integration 4, issuer 10,
NodeHealth API 5; secure rejoin PASS; HTTPS transport 8 modes; CloudSync
receipt validation 15 invalid modes and persistence recovery 2 modes. Software
only; no hardware test executed.

**Stage disposition:**

| TC-001 stage | Result | Evidence/status |
|---|---|---|
| C3 identity and HIL-awake firmware | PASS | COM4 identity and installed HIL-awake image were verified in the authorized deployment receipt; no C3 rebuild or flash this checkpoint. |
| S3 identity and installed image | PASS | COM10 identity and active image were read back; image is GS-68 diagnostic-only. |
| Authenticated C3→S3 session | BLOCKED | Current S3 image lacks full product HubRuntime; live enrollment/owner/epoch binding also remains unverified. |
| Product S3 durable-storage compatibility | BLOCKED | Live `gs_journal` is 2 MiB NVS; product requires 4 MiB LittleFS `gs_outbox` and 256 KiB `gs_state`. Existing candidate table overlaps the current journal; migration/recovery is unapproved and unverified. |
| S3 journal admission and CloudSync | BLOCKED | No compatible product storage table, product HubRuntime image or physical mTLS/trusted-time/authority binding was demonstrated. |
| GS-179 Hub ingress / PostgreSQL event | PARTIAL | PostgreSQL and caregiver HTTPS health PASS; physical Hub ingress is disabled/unconfigured; no new event row. |
| Existing caregiver API / APK Home | NOT_VERIFIED | No phone-side package/origin/Home or event observation. |
| Fresh TC-001 EventKey and actual APK presentation | NOT_RUN | No `INJECT_MOTION`, new EventKey, commit or APK display; HOST_SIM seed excluded. |

**Owner-local side-effect disclosure:** an earlier invocation of
`gs179-laptop-server.sh health-source`, mistaken for a read-only health probe,
ran the existing HOST_SIM scenario and updated only the synthetic
`test-c3-bedroom` NodeHealth projection to source revision 8. It did not insert
or change a business-event row; PostgreSQL still has the single preserved
historical HOST_SIM seed. The command was not repeated and no compensating
mutation was made. This result is excluded from physical evidence.

**Remaining exact physical/storage prerequisite:** TC-001 cannot continue on
the currently installed diagnostic S3 image. A source/partition comparison
establishes that app-only replacement is insufficient: the live development
table has a 2 MiB NVS partition named `gs_journal` at `0x820000`; product
`LittleFsSegmentStore` requires a 4 MiB LittleFS partition named `gs_outbox`
and a `gs_state` partition. The product mount sets
`format_if_mount_failed=false`, so it fails closed instead of formatting the
missing label. The source-controlled outbox candidate table would
reinterpret the existing `gs_journal` address range and is a persistent-layout
migration. The current journal bytes have not been read/backed up; no
migration, compatibility or rollback plan has been validated. The previously
suggested app-only-update path is superseded by this finding.

No S3 image or partition table may be written until an authorized, verified
preservation/migration path exists for old `gs_journal` data and the exact
candidate outbox/state layout, together with the TEST_ONLY identity/trusted-time
inputs and rollback procedure. Existing board-inspection approval does not
authorize S3 flashing, repartitioning, credential issuance, ownership mutation
or trust-root replacement. Do not inject on COM4 before those gates,
product-compatible durable storage and `runtime_live=1` pass. C3 and S3
persistent data remain untouched.

## 2026-10-24 owner-approved S3 product storage deployment and Agrim network recheck

**Source checkpoint:** canonical branch feature/r1-commercial-baseline,
source HEAD e9e610b353309996cb69a5865373a05f9ab1a30a; context preflight
PASS. No tracked source changes were made. Existing untracked owner Android
assets, S3 sdkconfig/managed components and historical hardware evidence were
preserved.

**Owner decision and backup gate:** the owner explicitly approved OPTION 1 for
the development COM10 ESP32-S3 N16R8, allowing the existing product storage
layout after backup, empty-pending-data and recovery checks. The live chip was
identified as MAC e0:72:a1:d3:8d:34, ESP32-S3 rev 0.2, 16 MiB flash and 8 MiB
PSRAM. The old 2 MiB NVS gs_journal partition at 0x820000 was fully read back
and contained no allocated records; the proposed 4 MiB outbox and 256 KiB
state regions were erased before installation. The old ota_0 4 MiB application
image, bootloader region, partition table, OTA selector, old journal, OTA1
slot, outbox and NVS readbacks remain in the owner-only directory
~/.local/share/ghar-sajag/GS117-20261024-s3-storage-deploy/. The complete old
OTA0 image is retained for manual recovery. Automatic rollback is not claimed.
Existing base-NVS keys gs68time.boot_gen and gs68time.utc_floor were compared
before/after and their stored value bytes are unchanged. No bootloader, eFuse,
C3, protected base-NVS value, credential or ownership data was intentionally
written.

**Installed product image and storage layout:** built the complete
gs_r1_s3_hub application from this source HEAD with ESP-IDF 6.0.3; the
diagnostic-only composition and HIL controls are OFF. The existing candidate
partition table preserves both 4 MiB OTA slots and maps gs_outbox LittleFS
4 MiB at 0x820000 plus gs_state NVS 256 KiB at 0xC20000. The 4 MiB LittleFS
image was explicitly initialized before write; product
format_if_mount_failed=false remains unchanged. The first product app was
2,198,224 bytes, SHA-256
8f93d05a7c890e9d5d0f8ff9a075dc54d1bbc6796048d63b3890d3a910e45429.
After the UART0 console produced no COM10 startup output, a second same-source
product build changed only the primary debug console to native USB
Serial/JTAG. That 2,194,768-byte app, SHA-256
a46c843ef66f4a0862668304b27f6cf6079ee70c0e2e48a3acbaa6e307462fa7, was
written app-only to the already selected OTA1 address 0x420000. Esptool
identified the expected MAC and verified the write; an independent post-write
readback compared byte-for-byte to the candidate. OTA0, partition table,
selector, outbox and NVS were not targeted by this second app update.

After the initial product app boot, the physical table/outbox readbacks matched
the intended table and formatted filesystem image, and the state partition was
still erased. No storage readback was taken after the later console-only app
update. Runtime
LittleFS-mount and HubRuntime-startup evidence remain NOT_VERIFIED: the existing
bounded COM10 boot observer first captured no lines, and its subsequent attempt
timed out during Windows PnP enumeration before opening the port. The
identity-pinned helper was not bypassed. The installed profile has
GS40_TEST_ONLY_CLOUDSYNC=OFF; no authenticated Hub/Home/epoch identity,
current Node enrollment, trusted-time/authority material or Hub-ingress client
credential is configured. The product image installation is verified; Hub
admission and CloudSync are not ready or proven.

**Agrim network recheck:** Windows currently reports Wi-Fi profile
Airtel_Agrim, category Private, address 192.168.1.10/24; current WSL NAT
address is 172.17.152.10. The existing owner-configured TLS certificate and
service settings were previously refreshed for the current address. Fresh
backend health still reports TLS-verified PostgreSQL and local caregiver HTTPS
PASS. The phone-facing probe fails because the existing Windows portproxy
still listens at stale address 192.168.1.7:443 and targets the current WSL
listener at 172.17.152.10:8444. Firewall-rule reads are blocked by the
current non-administrator Windows token; the existing scoped proxy start
requires that token, so this recheck made no new firewall or forwarding
mutation. Phone-side reachability and APK origin/Home remain NOT_VERIFIED.

| Stage | Result | Evidence |
|---|---|---|
| COM10 physical S3 identity and installed app | PASS | Exact USB serial and esptool MAC match; post-write app readback SHA-256 matches the USB-console product candidate. |
| Product partition table and outbox initialization | PASS | Product table and preformatted outbox image were written/read back; old journal was empty before replacement; base-NVS values checked unchanged. |
| S3 LittleFS mount and HubRuntime startup | NOT_VERIFIED | Current identity-pinned boot observer did not capture startup output; PnP preflight timed out before serial open. |
| C3 current image / authenticated C3-S3 session | PARTIAL / BLOCKED | C3 was not reflashed; latest GET_STATE remains runtime_live=0, sensing_live=0; no authenticated session or enrollment binding is available. |
| S3 CloudSync / persistent Hub ingress | BLOCKED | TEST_ONLY CloudSync is disabled in this build; authenticated Hub identity, trusted-time/authority inputs, ownership binding and ingress credential/configuration are absent. |
| Backend local service | PASS | PostgreSQL durability/TLS and local caregiver HTTPS pass. |
| Laptop LAN endpoint / existing APK | PARTIAL / NOT_VERIFIED | Current Wi-Fi is Agrim, but stale Windows forwarding blocks the new IP; no phone-side APK origin/Home/event observation exists. |
| Fresh TC-001 event / APK presentation | NOT_RUN | No INJECT_MOTION, new EventKey, physical Hub receipt, durable event commit or APK observation occurred; HOST_SIM history is excluded. |

The existing focused storage, association, recovery, CloudSync security and
TEST_ONLY bootstrap regressions passed before the console-only app change. The
console-only product build and esptool write verification also passed. No
software behavior test claims physical runtime qualification. GS-114 battery
and physical-wake qualification remains unchanged; no optical PIR test ran.
The next physical gate is a verified S3 startup/mount and an existing approved
TEST_ONLY Home/Hub/Node identity, time and mTLS binding. Do not inject while
C3 runtime and authenticated-session readiness remain false.
