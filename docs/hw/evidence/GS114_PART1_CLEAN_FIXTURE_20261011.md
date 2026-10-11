# GS-114 Part 1 — Authorized clean-fixture preparation checkpoint

**Run date:** 2026-10-11 UTC
**Source HEAD:** `5201abcbe930a4e1f47863ab1a7b3b974a0dd9ca`
**Branch:** `feature/r1-commercial-baseline`
**Result:** board identities and fresh images verified; erase/flash and HIL campaign **BLOCKED before erase** because no existing supported test-only commissioning path can pair the fresh boards without an unavailable provisioning procedure.

## Authorized fixtures and observed identities

The user authorized full-chip erase and fresh firmware only for the dedicated
boards identified below. User-provided stable USB links resolved to the exact
specified ports. All esptool commands used explicit target and port arguments;
there was no automatic port selection.

| Role | Stable USB ID / port | Observed chip and MAC | Flash / PSRAM | Security |
|---|---|---|---|---|
| C3 Node | `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` → `/dev/ttyACM1` (COM4 / BUSID 5-4 per user) | ESP32-C3 QFN32 rev 0.4; `14:63:93:c5:d1:58` | 4 MB flash; embedded flash manufacturer 46 / device 4016 (XMC) | Secure Boot disabled; flash encryption disabled; crypt count 0 |
| S3 Hub | `usb-1a86_USB_Single_Serial_5CBC401023-if00` → `/dev/ttyACM0` (COM9 / BUSID 5-1 per user) | ESP32-S3 QFN56 rev 0.2; `7c:4f:ad:b7:2a:20` | 16 MB flash; manufacturer 68 / device 4018; 8 MB embedded PSRAM AP_3v3 | Secure Boot disabled; flash encryption disabled; crypt count 0 |

ESP-IDF was sourced from `/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh`;
`idf.py --version` reported `ESP-IDF v6.0.3`. esptool reported `v5.4.0`.
Identity and flash/security probes use RTS reset sequencing; this was within
the user's explicit setup authorization. No flash erase or write occurred.

Exact identity commands (each explicitly targets its authorized port):

```sh
python -m esptool --chip auto --port /dev/ttyACM1 chip-id
python -m esptool --chip auto --port /dev/ttyACM0 chip-id
python -m esptool --chip esp32c3 --port /dev/ttyACM1 flash-id
python -m esptool --chip esp32c3 --port /dev/ttyACM1 get-security-info
python -m esptool --chip esp32s3 --port /dev/ttyACM0 flash-id
python -m esptool --chip esp32s3 --port /dev/ttyACM0 get-security-info
```

No eFuse, secure-boot, flash-encryption, or security configuration was changed.
The detected targets/capacity/security states do not trip the user's stop
conditions.

## Fresh source-matched firmware artifacts

At the verified current source HEAD, `scripts/build_validation_targets.py`
completed PASS with ESP-IDF 6.0.3 and the production profile
`GS_HIL_BUILD=OFF`. It produced an isolated, matching C3/S3 pair and GS-40
configuration bundle at:

`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/build/validation_targets/gs116-26s4vrei/`

The build report is `report.json`; `bundle/manifest.json` records offsets,
sizes, hashes, source HEAD, JSON configuration hash and the 300 s / 910 s
NodeHealth policy. The current bundle—not an older `build/gs40_bundle`—is the
only candidate artifact. The old bundle directory was inspected and rejected
as stale because it reported source `e36bd883...`; no artifact was flashed.

| Role/artifact | Offset | Bytes | SHA-256 |
|---|---:|---:|---|
| C3 bootloader | `0x0` | 21,408 | `fed92ca36766f487c91c62f26aed2391446ea0e10168e8a04aa35768b0def0d2` |
| C3 partition table | `0x8000` | 3,072 | `1b86379629900670bd43147c3a873a424695a67765fd1bdb28b1bffc21be137a` |
| C3 initial OTA metadata | `0xf000` | 8,192 | `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f` |
| C3 app | `0x20000` | 934,192 | `e9f902f597f9f63063d7ca19831ea17485e7e173e98bf60503046c191919b853` |
| S3 bootloader | `0x0` | 21,264 | `de0802a633625eb71c035895d304f7ff9fb68e4d20bf14556dbcbe7cb444dc54` |
| S3 partition table | `0x8000` | 3,072 | `4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe` |
| S3 initial OTA metadata | `0xf000` | 8,192 | `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f` |
| S3 app (includes exact C3 app) | `0x20000` | 1,868,800 | `95563bc6d28ff9a7e0fcbb767a28e1b54b6334dd5d4b4e95d5b392a663662051` |

Image headers independently report C3/4 MB/DIO/80 MHz and S3/16 MB/DIO/40 MHz,
both ESP-IDF 6.0.3, version `5201abc-gs116-50833308`. C3 OTA slots are 1,920 KiB;
S3 OTA slots are 4 MiB each. The S3 build configuration selects octal PSRAM,
40 MHz, boot initialization, startup memtest, and capability allocation. The
compiled S3 partition table matches the current development CSV, including the
2 MiB `gs_journal`; the C3 table matches `partitions.csv`. Both tables passed
ESP-IDF partition parser verification. The matching source C3 app is embedded
in the S3 app and verified by the packaging script.

Build command:

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
python scripts/build_validation_targets.py
```

Build result: PASS (C3 934,192 bytes; S3 1,868,800 bytes). This is target
compilation only; no board boot or firmware runtime has yet been observed.

## Stop condition: fresh test pairing is not currently available

Before erasing, source review showed that a fresh supported authenticated pair
cannot be established through the current S3 production target without a
separate provisioning procedure and test credentials/material:

- The identity/lifecycle guide says kit preparation and secure distribution of
  exact expected-Node records is not implemented, and the product commissioning
  entry point / fully authorized external control channel is incomplete.
- Hub commissioning requires an exact `ExpectedNode` record (physical MAC,
  Device ID, public key, installer code, Home/Hub, logical/room/function
  assignments). `request_node_commissioning()` is only called by the legacy
  ESP32 HIL control path; the S3 target rejects `GS_HIL_BUILD` and
  `GS_HIL_CONTROL` and provides no compatible request interface.
- The C3 `GET_TEST_QR` command is part of the test-only Node control path. It
  does not provision the S3 Hub's expected record. We will not invent an
  installer code, Home/Hub identity, ownership record, or alternate protocol.

The user directed the campaign to pause if a different provisioning procedure
is required. Therefore the full-chip erase/firmware write was **not started**;
this avoids leaving the fixtures freshly erased but unable to pair. No flash
erase or write was issued. The identity probes reset both MCUs via RTS; the
existing applications may then have performed normal boot/rejoin activity and
persistence. Pending-event count/content and post-probe NVS/session state were
not inspected and are not claimed unchanged. Boot logs and current running
firmware versions were not captured.

Required to resume: provide/approve the supported test-only commissioning
provisioning path for these exact boards, including an authorized test Home/Hub
identity and exact C3 `ExpectedNode` record/installer authorization, or approve
a narrowly scoped S3 commissioning control/tooling implementation. The latter
would be a software scope change and requires a new validated firmware build
before erase. No secret may be placed in Git or evidence logs.

## HIL-A01 through HIL-A08 status

| Test | Status | Evidence/limitation |
|---|---|---|
| HIL-A01 firmware and board identity | **BLOCKED (identity subcheck PASS)** | C3/S3 silicon, MAC, flash and security state verified; current running firmware/config/hash and boot identity not observed. Candidate image manifest is verified but not installed. |
| HIL-A02 authenticated existing Node–Hub link | **BLOCKED** | Clean pairing needs the unavailable supported provisioning path. Existing board association was not inspected or reused. |
| HIL-A03 NodeHealth | **BLOCKED** | No runtime logs or authenticated contact captured; 300-second interval not observed. |
| HIL-A04 Hub liveness | **BLOCKED** | No current pair or installed candidate firmware; no offline transition was induced. Live connectivity alone would not establish the 910-second timeout. |
| HIL-A05 Durable ACK/EventKey | **BLOCKED** | No authenticated pair; no event stimulus or actual app-level Durable ACK observed. |
| HIL-A06 runtime stability | **BLOCKED** | No startup/serial runtime logs; heap, session continuity, queue and reset diagnostics unavailable. |
| HIL-A07 timer/light-sleep | **BLOCKED** | No candidate firmware installed; no firmware runtime or physical wake behavior observed. |
| HIL-A08 negative-case compatibility | **BLOCKED** | Existing cases require test controls, fault injection, reset/rejoin, or state changes; none is supported for the current S3 production image. |

No HIL campaign, smoke, regression, manual PIR, physical FOTA, current/power,
storage operation, erase or flash command was run. No serial log path exists for
this checkpoint. Existing historical physical evidence remains tied to its
original images and fixtures.

## Repository and next action

- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- HEAD/remote at build: `5201abcbe930a4e1f47863ab1a7b3b974a0dd9ca`
- Context preflight: PASS
- `make release-gate-final`, broad GS-108 campaign: NOT_RUN
- Physical tests: NOT_RUN / BLOCKED; Part 2 human-motion PIR remains out of scope
- Hardware actions: target-detection/flash-ID/security-info probes only; these
  performed RTS resets. No erase, write, eFuse change, or destructive action.
- Pending Node records: not read, erased, or inspected by this task; exact
  post-probe state is unverified.
- Next: resolve the commissioning prerequisite above; then resume without
  rebuilding unchanged images unless source/profile changes, reverify the exact
  ports/identities and hashes, erase/write only these two boards, boot/log,
  provision a test-only pair through the approved path, and run supported
  Part 1 cases only.

## Approved fixture commissioning adapter — 2026-10-11

Following user approval, a narrowly gated S3 UART adapter is being added for
this disposable fixture only. It accepts an exact `ExpectedNode` commissioning
request and a status query, calls the existing Hub owner API, and exposes the
owner's queued/offer/rejected/timeout/authenticated-rejoin state. The Hub's
existing 120-second commissioning window and the C3's existing test-only
`GET_TEST_QR` flow supply fresh, per-board test identity material. No credentials
are fixed in source or retained in logs/evidence. The UART boundary is permitted
only for this isolated fixture and is not the authenticated installer control
path owned by GS-109.

The new `GS_HIL_COMMISSIONING` option defaults OFF. It is rejected on the legacy
ESP32 target, cannot be combined with broad S3 `GS_HIL_CONTROL`/`GS_HIL_BUILD`,
and compiles only the small commissioning/status adapter. Test identity scalar,
installer code and wrapping key generation is enabled only in this test build;
these values use development NVS and are not production-protected. Production
defaults continue to require preprovisioned protected identity material.

The standard S3 development partition map lacks `gs_state` and `gs_outbox`,
which the current S3 runtime requires and therefore fails closed on. The fixture
build must use the existing isolated `sdkconfig.defaults.outbox` candidate map
so current runtime initialization can be tested. This remains a development
candidate, not an approved commercial layout or storage-capacity qualification.
No erase/flash is performed until production-default and fixture target builds,
focused regressions, commit/push, and exact board re-identification are complete.

Software adapter validation is recorded at the eventual committed checkpoint.
Physical HIL-A01..A08 remain BLOCKED/NOT_RUN until the fresh fixture boots,
commissioning and persistence/rejoin are observed, and each supported case is
run with secret-bearing input redacted from retained evidence.

## Final authorized fixture implementation and Part 1 observations — 2026-10-11

This section supersedes the earlier “until ...” status above. The earlier
attempt history is retained as provenance; the attempts before `attempt06`
failed safely and contained only redacted output.

### Fixture-only adapter and software checks

The approved Option A adapter is implemented. It is S3-only, opt-in through
`GS_HIL_COMMISSIONING=ON`, OFF by default, rejected with the legacy broad
`GS_HIL_BUILD`/`GS_HIL_CONTROL` path, and unavailable in the production
`scripts/build_validation_targets.py` profile. It provides only bounded
`COMMISSION_EXPECTED_NODE` and `FIXTURE_STATUS` UART commands and calls the
existing `request_node_commissioning(ExpectedNode)` owner. Exact public Node
identity and installer-code proof continue through the existing commissioning
crypto, identity pinning, ECDH/HKDF, secure-session, persistent association and
authenticated-rejoin implementation. It adds no packet or storage format.
The existing 120-second owner commissioning offer remains the timeout. The
UART fixture is suitable only for these isolated disposable engineering
boards; it is not GS-109 product authorization.

The Node's existing test-only `GET_TEST_QR` supplied ephemeral exact identity
material. The host bridge redacted the public-key/code fields before retaining
logs and zeroed its code buffer. No installer code, private scalar, wrapping
key, or session secret is in the repository evidence. Test-only S3 identity
material is development-generated and stored in this disposable board's NVS;
Secure Boot and flash encryption are disabled on both fixtures. This is not a
production security profile.

Focused software checks:

| Command | Result |
|---|---|
| `python3 -m unittest tests.python.test_s3_fixture_commissioning -v` | PASS, 2 tests: exact bounded parser behavior, option-off/release-script isolation and broad-HIL rejection |
| `make s3-fixture-commissioning-test` | PASS, same 2 registered focused tests |
| `python3 -m unittest discover -s tests -p 'test_hub_hil_control.py' -v` | PASS, existing broad-HIL rejection test |
| `make validation-node` | PASS; complete Node suite including fixture stage; evidence `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/evidence/validation_framework/node-1791713574444033429/report.json` |
| `make validation-contract` | PASS; affected contract suite; evidence `.../contract-1791713664193996757/report.json` |
| `make validation-hub` | FAIL, exit 2 only at the preserved historical `hub-journal-migration-host-test`, assertion `clean migration commits` in `tests/cpp/hub_journal_migration_validation.cpp:194`; evidence `.../hub-1791713842164674753/report.json` |
| `make commissioning-crypto-host-test rejoin-host-test association-host-test hub-fresh-install-host-test` | PASS; exact identity/installer proof, association, authenticated rejoin and fresh-install regressions |
| `source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh && python scripts/build_validation_targets.py` | PASS; production defaults, fixture option OFF; C3 934,192 bytes, S3 1,868,880 bytes; report `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/build/validation_targets/gs116-3fuypjmb/report.json` |
| Production S3 image string check for `COMMISSION_EXPECTED_NODE` and `HIL_FIXTURE_READY` | PASS; neither fixture command string is present in the production app image |

The registry executed 22 Node stages in 85.405 s (exit 0), 28 contract stages
in 172.789 s (exit 0), and 34 Hub stages in 253.540 s (exit 2; 33 stages
passed, migration failed). Registry stage `count` values combine different
count kinds, so they are not presented as unique test-case totals. The JSON
reports preserve per-stage command, count kind, elapsed time, exit and log
hash.

The migration failure remains owned by GS-148. The GS-114 adapter neither
changes the journal importer nor relaxes the test or ownership checks.

### Dedicated physical fixture and artifact evidence

After software tests passed, the two previously authorized dedicated boards
were reidentified on their explicitly named ports before the authorized erase
and install. Observed profiles matched: C3 `14:63:93:c5:d1:58`, 4 MiB; S3
`7c:4f:ad:b7:2a:20`, 16 MiB flash and 8 MiB PSRAM. Secure Boot and flash
encryption were disabled; no eFuse writes occurred. The fixture uses ESP-IDF
6.0.3 and the S3 outbox candidate partition map. Its empty LittleFS image was
initialized only on the just-erased disposable S3 `gs_outbox` partition so the
existing fail-closed runtime could mount it; production firmware was not
changed to format storage automatically.

Final fixture app artifacts:

| Board | Firmware version string | App bytes | SHA-256 | Profile |
|---|---|---:|---|---|
| C3 | `73e1e842ff84-gs114-16fca85b` | 939,024 | `b03b3b2ed7996b594f9fe7d59241f558a6af82774db07a661e5346731db83014` | C3 HIL controls + physical-wake test profile, USB Serial/JTAG console |
| S3 | `73e1e842ff84-gs114-16fca85b` | 1,877,344 | `f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1` | S3 commissioning-only; candidate `gs_outbox`/`gs_state` partition layout |

These are fixture-development images, not release artifacts. The C3 was
full-erased and flashed with its complete bootable image; the S3 was full-erased
and flashed with its bootloader, partition table, OTA metadata and app, then
only its blank test outbox partition was initialized. The final embedded C3
image was subsequently installed in the S3 app update. The C3 log reports
ESP-IDF v6.0.3, C3 revision 0.4, 4 MiB flash, the expected OTA layout and
NodeHealth interval 300 s / derived offline timeout 910 s. The S3 image
contains the same version string and ran the fixture status adapter and
authenticated Hub runtime. No production credential was reused.

The hashes above identify the built fixture app artifacts, not flash readback
hashes. The S3 app update completed and the Hub then ran the fixture status
command and accepted an authenticated NodeHealth at session 5. Production
profile artifact hashes from the post-change build are C3
`7c8f4e0ab5f4afaf28dec4df7260d2cbcfb67ff4343f5ef3659d5f492ae04644` and S3
`d286905bcf05a9a54f46e6504b4880d43644968b9807da4ba00b286e57ed6790`; these
compile-only images were not flashed.

### Physical observations

`attempt06/commissioning_result.json` records the first exact-identity
commissioning and authenticated rejoin. The C3 then received an authorized
software-only restart. The S3 log records a second authenticated rejoin at
session 4, with the same exact C3 identity/logical assignment. After the S3 app
was updated/restarted, a 330-second read-only UART observation captured a new
authenticated NodeHealth at Hub session 5, without new PIR activity. Reported
Node telemetry was `sleep_entries=149`, `timer_wakes=149`,
`gpio_wakes=0`, `other_wakes=0`, `last_wake=TIMER`; the Hub accepted that
authenticated health report and reported heap/minimum-heap values. This
demonstrates timer-scheduled Node wake and authenticated link recovery in this
fixture. The C3 USB Serial/JTAG device disappeared while the Node entered
light sleep, so no C3-side serial wake trace was available. The health log is
retained at `attempt06/s3_post_update_observation_redacted.log`.

Machine-readable observations and per-case statuses are in
`attempt06/physical_results.json`. Summary:

| Test | Result | Evidence limit |
|---|---|---|
| HIL-A01 firmware/board identity | PASS | Exact silicon/MAC/flash/PSRAM, build profile and artifact hashes recorded; C3 boot banner verified. S3 runtime is evidenced by active adapter/NodeHealth, but its post-update boot banner was not captured. |
| HIL-A02 authenticated Node–Hub link | PASS | Exact pinned commissioning, authenticated rejoin, C3 software restart/rejoin, and S3 app restart followed by authenticated health contact. |
| HIL-A03 NodeHealth | PASS | Authenticated NodeHealth observed at the configured 300-second opportunity; no MAC-only contact was counted. |
| HIL-A04 910-second offline detection | NOT_RUN | No Hub outage/offline threshold was induced or observed. |
| HIL-A05 durable ACK/EventKey | NOT_RUN | No genuine event transaction occurred; no ACK/EventKey retirement claim. |
| HIL-A06 runtime stability | PASS (bounded observation) | No unexpected reset in the observation window; Hub heap reported. This is not a soak or resource qualification. |
| HIL-A07 timer/light-sleep | PASS (timer evidence only) | Hub accepted Node telemetry showing timer wakes/sleep entries; GPIO4/PIR wake is not proven. |
| HIL-A08 negative cases | BLOCKED | Lost-ACK/replay/outage tests require deliberate stimulus or fault injection outside this Part 1 scope. |

No physical human-motion test, `INJECT_MOTION`, power interruption, FOTA,
offline induction, RF fault injection, battery/current measurement, or broad
GS-108 campaign was run. HIL-A05 genuine Durable ACK/EventKey evidence and
GS-114 P1–P9 qualification remain open. No claim of complete physical
qualification or commercial release approval is made. Part 2 real PIR motion
remains a separately authorized activity.

The validated implementation source began at
`73e1e842ff843a696d592bd7c2004b72a512082c`. Implementation and evidence commit
`fee4b230ce954ea8b429390f1d89c44f105458f0` was pushed normally to
`origin/feature/r1-commercial-baseline`; the remote matched at verification.
The original untracked S3 `managed_components/` and redacted earlier attempt
logs remain preserved outside the commit.

Jira closeout: GS-114 comment `10428`; GS-109 cross-reference comment `10429`.
The GS-114↔GS-109 issue link records the limited fixture dependency only; it
does not imply GS-109 product acceptance or change either ticket status/rank.
