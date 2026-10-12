# GS-114 Part 2C — Diagnostic deployment and observation plan

**Date:** 2026-10-12 UTC

**Authorization:** GS-114 Jira comment 10503; planning and review only.

**Source reviewed:** `cbbf12d1b4fba9cd1e38730685ccede32f23f558` on
`feature/r1-commercial-baseline`; local and origin agreed at review start.
**Result:** **NO-GO** for diagnostic deployment, device observation, or PIR
qualification. No USB/serial interface or physical device was accessed.

## Decision and current blockers

The recorded GS-148 S3 application binary exists locally and contains the
`RPF00`–`RPF08` diagnostic strings. Its recorded SHA-256 matches the file. It is
not the commissioned fixture profile: the build has
`GS_HIL_COMMISSIONING=OFF`, while the paired disposable S3 stores its fixture
identity and wrapping material in the development NVS path selected by
`GS_HIL_COMMISSIONING=ON`. The current candidate also packages the standard
development partition table, which omits the `gs_outbox` and `gs_state`
partitions used by the commissioned fixture. Its full-flash manifest would
write bootloader, partition table, initial OTA metadata, and application, and
requests reset before and after flashing. **Do not use this package on the
fixture.**

An app-only update could leave the installed partition table in place, and the
two S3 profiles have the same 4 MiB OTA slot offsets. That does not make the
candidate safe: there is no supported S3 self-OTA/update caller in the target,
the installed OTA slot is unknown, the candidate is built for the wrong
fixture identity profile, and persistent-state compatibility/recovery is not
proven. Starting the updated Hub with the paired Node can also invoke replay
fence reconciliation, which may publish the lifecycle root. That is a normal
persistent write attempt, not a read-only diagnostic.

The existing serial observer cannot be treated as reset-safe. Its requested
DTR/RTS-low state is applied after the serial device is opened; the saved C3
capture reported `USB_UART_CHIP_RESET`. The reset's precise timing and cause
remain unproven. No currently reviewed independent observation path is
physically established for both boards.

Consequently, the current diagnostic image is **not deployable as-is**, the
fixture state cannot be demonstrated recoverable with an existing supported
mechanism, and no observation or PIR action is approved by this plan. GS-114
remains In Progress and physical NO-GO; GS-148 remains OnHold.

## Evidence and provenance

| State | Evidence available offline | What it establishes | What it does not establish |
|---|---|---|---|
| Last observed running fixture | Stopped baseline redacted logs under [`GS114_PART2_20261012T032500Z_baseline`](GS114_PART2_20261012T032500Z_baseline/). C3 and S3 boot banners reported app version `73e1e842ff84-gs114-16fca85b`, ESP-IDF 6.0.3, expected MACs; S3 reported 16 MiB flash/8 MiB PSRAM. | Those identities and runtime banner were observed during the 2026-10-12 capture. C3 reset marker and S3 replay-fence admission failure were observed. | Installed app hashes, active OTA slots, exact live partition-table bytes, current persistent contents, or current state after that attempt. The logs are not a flash readback. |
| Part 1 commissioned fixture images | [`attempt06/physical_results.json`](../GS114_PART1_CLEAN_FIXTURE_20261011/attempt06/physical_results.json) and [Part 1 evidence](../GS114_PART1_CLEAN_FIXTURE_20261011.md): C3 app hash `b03b3b2ed7996b594f9fe7d59241f558a6af82774db07a661e5346731db83014`; S3 app hash `f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1`. Both binaries are currently present under `build/gs114_fixture_pair/build-t66a98xh/`; their local SHA-256 values match the saved report. The S3 build script selected `sdkconfig.defaults.outbox`; S3 profile was commissioning-only. | The currently available build artifacts match the recorded Part 1 application hashes and intended fixture profiles. The saved physical report records prior fixture installation and commissioning. | These are build artifacts, not flash readbacks or proof of the currently installed images. The final fixture report does not record a verified on-device partition-table hash or a current storage inventory. |
| GS-148 diagnostic candidate | `build/validation_targets/gs116-whsxuzya/report.json`, `s3/gs_r1_s3_hub.bin`, `s3/flasher_args.json`, generated `s3-sdkconfig`, and generated CMake cache. S3 app: 1,870,944 bytes, SHA-256 `3a432fa7bd671e91cb6b4f93d437f81b0892aa878ad5e4173e196fb4623f098a`; C3 app: 934,192 bytes, SHA-256 `50cd6cc007e84c25898fc86fadff1784a8bf85a4237b52699206f4ced816c067`. | Offline hash checks match the report. Binary strings include `RPF00`–`RPF08` and the sanitized replay-fence failure template. Report says ESP-IDF 6.0.3, `esp32s3`, 16 MiB flash, 8 MiB Octal PSRAM at 40 MHz, `GS_HIL_BUILD=OFF`; CMake cache says `GS_HIL_COMMISSIONING=OFF`. | It is target-compiled only; no installed-image match, boot, signing, or hardware qualification. The report source is `abacd8ce1fc54b8641dcefbdcdb8f585c758c20f` with fingerprint `5082c629…`; current source fingerprint computes to `db36475d…`, so the report is not exact-current-tree provenance. The binary must be rebuilt in a corrected fixture profile before any review for deployment. |

The saved Part 1 report includes an earlier, subsequently superseded production/default package whose partition-table hash is `4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe`. That hash is also the generated table in the present diagnostic package. It identifies the development map, **not** a readback of the final commissioned fixture map. The final Part 1 fixture build explicitly used the outbox defaults, but its final partition-table hash is not recorded. Do not conflate these two artifact generations.

The historic device probe recorded Secure Boot and flash encryption disabled on both dedicated boards. The current diagnostic S3 sdkconfig also has `CONFIG_SECURE_BOOT` and `CONFIG_FLASH_ENCRYPTION_ENABLED` unset, and its flasher metadata marks images `encrypted=false`; app anti-rollback is disabled while ESP-IDF app rollback support is enabled. These are development-fixture conditions, not commercial trust qualification. No signing/eFuse change is proposed.

## Image and partition compatibility

The current diagnostic app build selected `partitions.development.csv` through
the generated sdkconfig. The fixture build helper
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/scripts/build_gs114_fixture_pair.py`
instead explicitly selects both
`sdkconfig.defaults` and `sdkconfig.defaults.outbox`. The source-defined maps
are:

| S3 range | Commissioned Part 1 outbox/state profile | Current diagnostic package development profile |
|---|---|---|
| `0x00009000`, `0x6000` | default `nvs` | default `nvs` |
| `0x0000f000`, `0x2000` | `otadata` | `otadata` |
| `0x00011000`, `0x1000` | `phy_init` | `phy_init` |
| `0x00020000`, `0x400000` | `ota_0` | `ota_0` |
| `0x00420000`, `0x400000` | `ota_1` | `ota_1` |
| `0x00820000` | `gs_outbox`, LittleFS, `0x400000` | `gs_journal`, NVS, `0x200000` |
| `0x00c20000` | `gs_state`, NVS, `0x40000` | no `gs_state`; remainder unallocated |

Both maps use the same app-slot offsets/sizes, so an app image does not itself
carry the partition table. Runtime partition lookup uses the installed table.
But the **bundle** at `s3/flasher_args.json` lists writes at `0x0` (bootloader),
`0x8000` (development partition table), `0xf000` (`ota_data_initial.bin`),
and `0x20000` (app), with `before=default-reset` and `after=hard-reset`.
Installing that bundle would replace the table and OTA selection metadata. It
would not directly write the `gs_outbox`/`gs_state` address range, but would
reinterpret the old LittleFS bytes as a differently named/typed 2 MiB NVS
partition and remove the `gs_state` label. The current S3 runtime requires
`gs_outbox`, mounts it with `format_if_mount_failed=false`, and fails closed
when it is absent. This package is therefore structurally unsafe for the
commissioned layout as a full bundle.

### Persistent state that must remain associated with its owner

| Device/area | Relevant state | Preservation concern |
|---|---|---|
| S3 default `nvs` | Fixture Hub identity/wrapping/installer material and secure Node association are created under the development commissioning profile. | The Part 1 identity path is selected by `GS_HIL_COMMISSIONING=ON`. In the current diagnostic candidate it is OFF; the production path expects protected provisioned key material and fails closed when required secure-boot/flash-encryption prerequisites are absent. An app-only update to this candidate is not compatible with the fixture's existing test identity path. |
| S3 `gs_state` | Durable checkpoint selection, retirement snapshots, reducer/runtime checkpoint state and associated owner records. | Missing from the current diagnostic table; exact live contents/generation are unknown. No supported export/restore or schema-compatibility proof is recorded. |
| S3 `gs_outbox` LittleFS | Event bodies, exact EventKey identities/completions, publication heads, lifecycle/replay-fence root and other durable outbox state. | The observed error may occur during a publication attempt. A failed publish can have reached persistent media; do not retry or “repair” by resetting the fence. Exact live files and pending records are unknown. |
| C3 Node NVS/storage | Permanent Node/test identity and association/session recovery material; retained pending EventKeys and retry state. | No C3 update is necessary for S3 logging, and none is approved. A Hub reboot/update can cause rejoin/retirement-report traffic without PIR; do not assume C3 has no pending records. |
| S3 `otadata` and app slots | Active/previous OTA slot selection and rollback metadata. | The active slot is not known. Replacing initial OTA metadata is not rollback-safe. App rollback does not reverse NVS/LittleFS writes or restore their prior interpretation. |

No target-state backup was collected. Existing build/flash tooling provides no
demonstrated S3 self-OTA path: the S3 target has storage/runtime integration,
but no S3 application `esp_ota` receiver/caller was found. Existing paired
build/package tooling is not an updater. The Part 1 HIL updater was an explicit
fixture operation and is not evidence of a safe application-only path here.
An older app binary alone is not a recovery plan.

**State-preservation conclusion:** not demonstrated. Any future update needs a
separately reviewed and approved preservation/recovery strategy covering the
fixture NVS, `gs_state`, `gs_outbox`, OTA slot metadata, credential
confidentiality, and rollback of application *and* persistent interpretation.
Until then, firmware installation is blocked. Do not use full-chip erase or
storage initialization as a workaround.

## Reset-safe observation assessment

| Method | Available evidence | Assessment |
|---|---|---|
| Existing bounded pySerial observer | `ReadOnlyCapture.open()` sets requested DTR/RTS low before calling `open()`, but the POSIX driver performs `os.open()` before modem-control ioctls. The prior C3 capture produced `USB_UART_CHIP_RESET` during the observation window. | Not qualified as non-resetting. Do not repeat on this fixture under the current plan. The S3 adapter's reset exposure has not been independently shown harmless. Receive-only means no payload command; it does not mean no reset or no application-side persistent write. |
| Passive receive-only tap on an existing target TX | No approved, attached tap or physical connector/pin validation is recorded. C3 uses USB Serial/JTAG console in the fixture profile. S3 build config uses UART0 console at 115200; repository notes mention a possible S3 UART0 TX path but explicitly leave exact board routing unverified. | Best future candidate only after board schematic/continuity and electrical-level review. A high-impedance isolated RX-only attachment must have no target RX, DTR, RTS, reset or power connection. This would require a separately approved fixture access/wiring operation. It is not yet proven safe or available for both devices. |
| Existing network/API diagnostics | No existing authenticated remote channel that exports these local RPF stage details and independent C3 logs is established by the reviewed HIL interfaces. | Not an available substitute. Do not add a telemetry command or infer diagnostics from ordinary NodeHealth. |
| Rebuild console or add diagnostic transport | Would require a different image and possibly GPIO/console/persistent changes. | Out of scope for this plan. Requires separate code/image review and hardware authorization; do not assume pin assignments. |

**Recommendation:** no observation method is currently cleared. First pursue
the passive TX-only candidate after physical board documentation and electrical
review; do not wire or attach it without separate authorization. If that
candidate cannot be validated, stop and request a new reviewed observation
design. Reopening the existing UART with DTR/RTS-low is not the approved
fallback.

## Gated supervised procedure — draft only

Every gate below is a future authorization boundary. Passing a gate does not
authorize the next hardware action. The previous Part 1 erase/install approval
does not authorize a new update, reset, backup, storage operation, observer
attachment, or motion test under this plan.

### Gate A — State and artifact preservation

1. Before any connection, agree a state-preservation strategy. It must account
   for S3 `nvs`, `gs_state`, `gs_outbox`, `otadata`, both app slots, C3 pending
   EventKeys and association state, while keeping keys/codes/event payloads out
   of ordinary logs and Git.
2. Define exact operator-accessible evidence for current board identity,
   firmware/version, installed partition map, active OTA slot, S3 storage
   generation/fence and pending-event counts, and C3 retained/in-flight counts.
   The existing serial method cannot satisfy this gate until reset exposure is
   addressed.
3. Prove an approved recovery path for the same persistent layout. No current
   backup/restore procedure meets that standard. Do not presume the prior clean
   flash left the current state empty.

**Stop:** if exact state cannot be inventoried/preserved or recovery requires
erasure/recommissioning not separately authorized, deployment remains blocked.

### Gate B — Image compatibility

1. Do not reuse the `gs116-whsxuzya` bundle or app as a deployment artifact.
2. After separate build approval, create a fresh isolated S3 fixture diagnostic
   build from the then-current canonical HEAD with ESP-IDF 6.0.3 and explicit
   profile: `IDF_TARGET=esp32s3`; 16 MiB flash; Octal 8 MiB PSRAM/40 MHz;
   `GS_HIL_BUILD=OFF`; `GS_HIL_CONTROL=OFF`; `GS_HIL_COMMISSIONING=ON` to use
   the already provisioned fixture identity store; full product S3 composition
   (`GS_S3_DIAGNOSTIC_ONLY=OFF`); and both
   `sdkconfig.defaults` plus `sdkconfig.defaults.outbox` so the generated
   table contains `gs_outbox` and `gs_state` at the fixture offsets. Retain a
   provenance-checked embedded C3 image asset; do not transmit it or update the
   C3 during this work.
3. Verify current source fingerprint, IDF version, chip target, PSRAM/flash
   settings, partition table binary/hash, app slot sizes, commissioning flag,
   RPF log strings, bootloader/security settings, image size/hash, and package
   offsets. Keep Secure Boot/eFuse/encryption unchanged. The fixture-only
   commissioning flag is not commercial Add Device and must remain isolated.
4. Obtain a supported S3 application-update method that preserves the existing
   table and chooses a verified inactive OTA slot. None is presently
   established. Do not call `idf.py flash`, execute `flasher_args.json`, use
   esptool, or install via the bootloader without a separate exact-scope
   approval after preservation review.

**Stop:** if the new app, full partition map, existing development identity,
storage formats, signature/update mechanism or rollback behavior do not match
verified fixture provenance, do not install.

### Gate C — Observation safety

1. Review schematic/board markings and verify the target's existing console TX
   route and electrical level without guessing from a generic chip pinout.
2. If a passive method is approved, document that it is high-impedance,
   receive-only and has no DTR/RTS/RX/reset/power path. Test its behavior on an
   approved non-sensitive fixture before attaching it to the paired boards.
3. Separate S3 and C3 log files; use UTC host timestamps, preserve original
   redacted bytes, avoid multiple readers, and redact secrets before evidence
   retention. Record any clock skew; correlate only by public RPF stage,
   firmware version and EventKey when observed.

**Stop:** if a reset-safe route cannot be demonstrated, do not open the UART or
continue. Host tests cannot qualify an electrical observation method.

### Gate D — Diagnostic deployment authorization

After Gates A–C have evidence, present the exact image hash, source fingerprint,
profile, partition map, updater command, exact S3 identity/interface, expected
reset/reboot behavior, possible replay-fence writes, preserved state, recovery
steps and logging method. Obtain a **new explicit approval for S3 installation**
and any reset inherent in it. This is separate from the Part 1 clean-flash
authorization and separate from observer approval. No C3 installation,
recommissioning, erase, format, or eFuse/security change is included.

### Gate E — First controlled S3 diagnostic observation

Only after an approved install and approved observer, capture baseline before
allowing C3 interaction. The paired Node can automatically rejoin and send a
retirement report; there is no proven way in the current fixture to prevent
that report without another state/security change. `reconcile_replay_fence`
may publish the lifecycle root. Treat this step as potentially state-mutating.
Do not describe the observation as read-only at the application/storage layer.

If an approved strategy accepts that specific normal replay-fence publication
attempt, capture the single sanitized terminal record:

`S3 replay fence failed stage=RPFnn result=CATEGORY path=... admission=... report_ack=...`

Do not send UART commands or intentionally provoke retries. Preserve the first
failure and stop on any reset, unexpected state change, admission closure,
identity/session mismatch, or uncertain write outcome. No PIR movement occurs
at this gate.

### Gate F — Interpret the observed stage

| Stage | Meaning available from software | Required interpretation limit |
|---|---|---|
| `RPF00` | Replay-fence reconciliation ready/bound. | Does not prove capacity, endurance, or absence of other storage defects. A successful publication may have written the lifecycle root. |
| `RPF01` | Selected durable checkpoint recovery failed. | Generic checkpoint recovery category; no deeper native NVS code. Stop. |
| `RPF02` | Selected checkpoint has no retirement snapshot reference. | Selected state is inconsistent/incomplete; do not synthesize one. Stop. |
| `RPF03` | Referenced retirement snapshot reload/verification failed. | Underlying adapter reports a boolean; read/authentication/digest cause may remain ambiguous. Stop. |
| `RPF04` | Reducer checkpoint reload failed. | Underlying adapter reports a boolean; do not infer a filesystem errno. Stop. |
| `RPF05` | Reducer checkpoint is absent. | Do not create or restore one in this diagnostic session. Stop. |
| `RPF06` | Outbox witness prevalidation/publication/readback failed. | Use the emitted result category. A publish failure may have reached media; do not retry/reboot/repair automatically. Stop. |
| `RPF07` | Runtime refused to bind the fence. | Use the named mismatch category; do not relax identity/epoch checks. Stop. |
| `RPF08` | Required retirement storage owner unavailable. | Boot/runtime composition is incomplete; do not admit events or recommission. Stop. |

`RPF03`/`RPF04` do not expose a low-level storage return code. `RPF06`
publication failure does not establish that no bytes were written. Preserve
that uncertainty in the report.

### Gate G — Recovery authorization

For a localized result, produce a minimal recovery proposal that names the
affected persistent record, expected owner/epoch, whether a write may already
have persisted, validation against an image-matched backup, and rollback
effects. **No recovery write, firmware repair, reset, restore, journal import,
fence reset, NVS/LittleFS reinitialization or state deletion is included in
this plan.** Obtain separate explicit approval before any such action. If
the observed category is still ambiguous, preserve state and stop for a
security/storage owner decision; do not pick a recovery from symptoms.

### Gate H — Resume GS-114 real PIR qualification

Resume only when all are true:

- approved fixture identity and current image/profile/partition provenance are
  verified without relying on historical port numbers;
- the S3 fixture identity and authenticated C3 association still work under the
  approved commissioning profile, with no re-enrollment;
- the replay-fence error is resolved or `RPF00`/ready is observed without an
  unresolved write/state concern;
- retained EventKeys and their owner context have been reconciled and preserved;
- independent C3/S3 observation is safe and image-matched;
- user separately approves the exact observation and real PIR stimulus sequence.

Then perform only the specifically approved case. The first motion test must
correlate real AM312/GPIO4 wake, Node EventKey and durable pending state,
authenticated Hub reception, S3 durable commit, matching application ACK and
exact Node retirement. MAC send success is not Durable ACK. Missing internal
evidence means BLOCKED, not PASS. Do not infer caregiver-level deduplication
from radio counters.

## P1–P9 disposition and later intervention gates

No case is executed by this plan. Existing stopped-attempt evidence controls;
Part 1 PASS results are not upgraded.

| BAT-C8 case | Current physical result | Later prerequisite / boundary |
|---|---|---|
| C8-P1 timer-only sleep/wake | NOT_RUN | First prove state is known, no pending work/inhibitor exists, S3 admission is healthy, and timer/radio evidence is available through an approved observer. |
| C8-P2 real AM312 GPIO4 wake | BLOCKED | Gates A–H through a healthy S3; separately approved real movement prompt. Never substitute injection. |
| C8-P3 held-HIGH PIR and recovery | BLOCKED | Safe natural sensor observation and an approved motion sequence; do not rewire or force GPIO. |
| C8-P4 wake, radio restore, durable ACK | BLOCKED | Healthy S3 admission plus independent logs proving the exact EventKey, durable commit, app ACK and Node retirement. |
| C8-P5 Hub unavailable/return | BLOCKED | Requires a separately approved Hub power interruption/restoration and recovery plan. Not authorized here. |
| C8-P6 Hub-only reboot | BLOCKED | Requires separately approved Hub reset/reboot; not authorized here. |
| C8-P7 first real motion after Hub reboot | BLOCKED | Depends on approved P6, confirmed authenticated rejoin, then separately approved real PIR motion. |
| C8-P8 lost application ACK/stable-key replay | BLOCKED | Requires separately approved ACK suppression/controlled RF fixture, authoritative durable EventKey ledger, and recovery plan. |
| C8-P9 ACK/FOTA sleep inhibition | BLOCKED | Requires separately approved ACK-loss and physical signed-FOTA operations plus safe rollback evidence. No FOTA is authorized. |

P10 quantitative power belongs to GS-149. GS-46 owns first-event latency
acceptance and GS-69 owns the extended sensing soak; neither is claimed here.

## Evidence handling and stop conditions

Use a unique dated evidence directory. Record source HEAD and fingerprint,
board profile/MAC, independently verified running image/profile and partition
metadata, exact observer method, UTC start/end, operator-confirmed stimulus,
redacted C3/S3 logs, RPF stage/result, EventKey correlation (if any), and each
case verdict. Keep raw secret-bearing commissioning material and private keys
out of the evidence directory. Preserve the first failure before any approved
later action.

Immediately stop on any unexpected reset, unknown board/image, storage-layout
mismatch, missing state-preservation proof, failed replay-fence/admission,
unauthorized write/format/migration, ownership/session mismatch, event loss or
duplication, unavailable safe log route, or deviation from the explicitly
approved action. Do not attempt automatic recovery.

## Exact future approvals needed

No approval is requested to operate a device under this planning task. Before a
later supervised attempt, the user must review and separately authorize:

1. A state-preservation/recovery strategy for existing fixture identities,
   C3 pending records, S3 checkpoint/outbox/replay-fence and OTA metadata. The
   current repository has no demonstrated backup/restore procedure for this
   state; the user must decide whether to fund/approve one or make an explicit
   data-disposition decision. The prior clean-flash scope does not carry forward.
2. A corrected S3 fixture diagnostic build and its exact image/package hashes;
   the current build is incompatible with the fixture identity profile and its
   full bundle uses the wrong partition map.
3. A physically reviewed observation route. The existing UART observer is
   not reset-safe; a passive TX-only tap would require verified connector/pin
   and electrical evidence and separate authorization to attach it.
4. The exact S3 application installation method and reset/write consequences.
   No supported S3 self-OTA method is presently established.
5. Only after healthy S3 admission is demonstrated, the real AM312 motion
   sequence and any additional intervention-specific cases.

## Validation performed for this planning record

- Context preflight: PASS at `cbbf12d1b4fba9cd1e38730685ccede32f23f558`.
- Local/remote branch check: both `feature/r1-commercial-baseline` at that
  checkpoint before this documentation change.
- Offline SHA-256 verification: both diagnostic app files match the GS-148
  target report; C3 and S3 bundle copies match their standalone app files.
- Offline SHA-256 verification: the currently present Part 1 fixture-pair C3
  and S3 application artifacts match the hashes in the saved fixture report;
  this does not identify the images now installed on the boards.
- Offline S3 partition-table binary check: generated table hash
  `4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe`,
  configured as `partitions.development.csv`.
- Offline S3 binary-string check: `RPF00`–`RPF08` and sanitized failure format
  are present.
- Source/configuration inspection only; no build, target test, serial/USB
  access, physical HIL or hardware state change was performed.
- Product/release tests: NOT_RUN; this is a documentation-only plan.

## Related qualification ownership

- GS-148 comment 10501 records diagnostic implementation and the still-unknown
  physical root cause. The current candidate artifact/profile mismatch is
  cross-reported there; GS-148 remains OnHold and P2-E/P2-F remain out of scope.
- GS-145 owns fresh current-format S3 durability/reboot/dedupe qualification;
  it does not authorize this diagnostic deployment or legacy migration.
- The separate historical `hub-journal-migration-host-test` failure remains
  independent. Nothing here changes its result or expectation.
- GS-114 remains In Progress, physical NO-GO. This plan does not close any
  P1–P9 case or qualify the product for release.
