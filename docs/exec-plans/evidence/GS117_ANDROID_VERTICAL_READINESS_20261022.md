# GS-117 Android sensor vertical readiness — 2026-10-22

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
