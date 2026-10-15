# GS-114 C8 physical execution

## Resumed host execution checkpoint — 2026-10-15 19:31 UTC

This checkpoint resumes the owner-requested GS-114 P9 work from the prior
15:23 UTC pause. `/status` reported 80% of the five-hour limit
remaining; the owner requested continued three-minute checks and a pause below
12%. The canonical worktree is `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, local and verified remote HEAD
`a5428cfa97bb110573eea7d490ce1c0c0bbad2e9`; context preflight PASS at
`2026-10-13.001`. Tracked source was clean at this checkpoint. All pre-existing
untracked PWA files, managed components and physical logs/readbacks remain
untouched; the host artifact manifest marks the worktree dirty because those
untracked entries (including S3 managed components) exist.

The C3 is connected to laptop USB power per the owner, may be in light sleep,
and is not attached to WSL. That does **not** block host-side compilation,
artifact generation, or host tests; no C3 binary flashing was required for any
work in this checkpoint. A read-only Windows serial enumeration found zero COM
ports. No serial port was opened and no board, power, reset, flash, erase,
recommission, OTA or motion operation occurred.

### P9 fixture and signed artifact results

The first resumed signed-artifact attempt at
`code/build/gs114_p9_signed/20261015T185114Z/` stopped at the S3 N profile
guard. It exposed a real compatibility defect: the S3 packager required C3
generic HIL controls even though the required C3 signed physical-wake profile
deliberately disables them. The guard now accepts only the S3-specific
`signed-app-on-update`, `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`,
`physical_wake=true` C3 profile; the legacy classic-Hub path still requires
explicit C3 HIL controls. Commit `a5428cfa97bb110573eea7d490ce1c0c0bbad2e9`
contains this narrow fix and its positive/negative regressions. It was pushed
and remote HEAD was verified before rebuilding artifacts.

The corrected run emitted the consolidated host-only manifest
`code/build/gs114_p9_signed/20261015T185926Z/gs114_p9_artifacts.json` from
source HEAD `a5428cfa97bb110573eea7d490ce1c0c0bbad2e9`. Signed C3 A/B/N/R are
each 987,136 bytes (within the 1,966,080-byte historical C3 OTA app slot), use
distinct versions and keep generic HIL controls OFF while preserving the real
GPIO4/timer path. A/B/R use trusted test signer fingerprint
`bba0cbb27599281bd3ed47ec3225b2df35e24215e88af8c3c98b5ade35bcb553`; N uses
`f201abde5e129ed5fa1042dfcf07c903d5f7398b165a1c825683f8f858d4efa3`. The C3
builder accepted A/B/R signatures and explicitly rejected N against A's trust
key. Private keys are external test-only RSA-3072 material; no private path or
key material is in the repository or report.

Matching S3 Hub N/B/R apps are each 1,936,256 bytes, below their 4 MiB
candidate OTA slot. The S3 profile has `GS_HIL_SIGNED_FOTA=ON` while broad HIL,
commissioning, ACK-drop and ACK-hold controls are OFF. The image builder
verified the exact embedded C3 SHA for each variant, the S3 app version and
profile, and the narrow `START_SIGNED_C3_FOTA` marker without commissioning or
legacy raw-FOTA controls. Independent manifest checks passed 7/7 image
hash/profile/size/embed assertions. All artifacts are candidates only and are
NOT_INSTALLED. Details and the fixture-specific physical boundary are in the
[P9 execution manifest](P9_EXECUTION_MANIFEST_20261015.json). The previous
`20261015T180941Z` artifacts remain preserved but superseded because their C3
images carried unrelated HIL controls; do not use them physically.

Focused validation after the guard fix: `PYTHONPATH=tests/python python3 -m
unittest test_gs114_p9_artifacts test_secure_signed_fota_fixture -q` ran 29
tests, PASS/exit 0; `make s3-fixture-commissioning-test` ran 15 tests, PASS/
exit 0; the consolidated BAT-C8/GS-150/S3 fixture/signed-FOTA/artifact command
ran 55 tests, PASS/exit 0. The P9-A ACK-hold host gate remains 34/34 PASS and
its ASan/UBSan run 34/34 PASS from the previous checkpoint. The new P9-A S3
candidate from source `fbda53a32958cc3c428397f95d96687f77431c6e` remains
`c96bbdf91956a8e3fbc9245c272f69d5347a7468fd873e7e4aa215a9afb8890f`, embeds
exact existing C3 candidate `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`,
and is also NOT_INSTALLED.

`make validation-hub` ran against unchanged committed source HEAD `a5428cf`
with source fingerprint
`e8e84609eacdc43bab27c23962d61490098e13dce7f4c4aad38b3d2f479c4092` and exited
2: 42/44 registered stages PASS. The two failures are the preserved
`hub-journal-migration-host-test` assertion `clean migration commits` (count
0, exit 2) and required `p0-full-product-e2e` stage (runner exit 0, 26/26
scenario checks plus browser test pass, but the aggregate correctly fails
`product_status=PARTIAL`, `physical=NOT_RUN`). P9 ACK-hold 34, signed-artifact
safety 7, ACK-drop 16, S3 fixture 15, target host build, board-stack E2E,
FOTA/security, replay, persistence and sanitizer stages passed. Do not repair
the unrelated migration/P0 issues in this GS-114 task or call the Hub gate an
aggregate PASS. The prior Node gate remains 25/26 stages PASS; its sole
aggregate failure is the same mandatory P0 PARTIAL condition.

The canonical report, work state, traceability row, physical catalogue and
qualification matrix are now updated. `make feature-coverage-test` passed with
204 features, 211 modules, 17 physical definitions and 22 tests. The first
physical-catalogue run rejected a semicolon-joined evidence field as one path;
the entries now point to the report (which links this manifest), and the final
`make physical-hil-catalogue-test` passed all 101 cases. JSON parsing,
`git diff --check` and the context preflight pass. No physical disposition was
changed by these documentation checks.

### Physical disposition and exact resume boundary

Physical dispositions are unchanged: P1/P2/P6/P7 PASS; controlled P4 q16,
controlled P5 q24 and P8 q14 PASS; P3 remains PARTIAL because no trustworthy
readback binds the S3 bytes actually running during the P3 trace; P4's
historical q10–q12 extra-event observation remains OPEN; P5 retry identity
per-attempt visibility remains LIMITED. P9-A and P9-B remain BLOCKED / NOT_RUN;
P10 remains GS-149. Existing run04 partition/OTA readbacks and P8 installed
hashes are historical and do not establish current running images, active
slots or the current pending-EventKey inventory.

GS-146 comment 10734 authorizes reusable clean use of the named R&D pair, but
GS-114 comments 11107/11109 require exact P9 authorization. No P9 hardware
operation is currently authorized. In addition, the C3 native USB console can
go silent in light sleep and no reset-safe continuous C3 sleep/reset observer
has been qualified. P9-A does not require C3 flashing, but still needs the S3
fixture image, exact-key ledger baseline, safe target observation and explicit
P9 scope approval. P9-B has host-signed artifacts, but actual image/trust/slot
state and the safe restore route remain unknown; GS-118's rollback stack is
provisional at 12 KiB and its stack high-water has not been measured. No Secure
Boot, eFuse, commercial trust-root or production ACK/retry/sleep policy change
was made.

The precise proposed operations, board identities (historical, not reverified),
image hashes, slot evidence limits, recovery plan, stop criteria and missing
authorization are recorded in the linked JSON manifest. Report/work-state and
matrix updates are committed as `280fd44ce004b9ee68cc9f776c053ff3fcf6b9ff`;
local and remote HEAD match. Jira progress comments are GS-114 #11110, GS-110
#11111 and GS-118 #11112. The latest observed `/status` was 80% remaining at
19:31 UTC; the requested three-minute monitor remains active with a 12% pause
threshold. Follow-up handoff commit `7775f0b5f7dbe5198eb761b68358f1ffee8c7099`
was also pushed and origin HEAD verified before this 19:31 status refresh.

**Resume boundary:** wait for the owner's explicit response to the single
consolidated P9 approval request. Before any test, verify board identity/port,
current image and slots, pending EventKeys, authenticated session, continuous
reset-safe Node observation and app-only restore route. If any prerequisite
fails or needs destructive state/security changes, stop and preserve evidence.
The C3's laptop USB power and lack of WSL attachment do not block host builds;
no C3 flash is proposed for P9-A. Do not open ports or operate boards before
authorization. Keep GS-114 In Progress; do not claim physical P9 PASS or
transition GS-114 to Done.

## Pause/resume checkpoint — 2026-10-15 15:23 UTC

The owner requested a `/status` check every three minutes and a pause below
8% of the five-hour limit. `/status` reported **6% remaining**; work stopped
at that threshold. The host artifact driver and Hub component gate were
interrupted intentionally, exit 130, after their partial logs were preserved.
No board process was running or board interface opened. The S3 signed-FOTA N
build had reached step 1052/1120; its `ninja process terminated` message is
the deliberate interruption, **not** an established source compile failure.
The completed signed C3 A/B/N/R files and their sidecars remain under ignored
`code/build/gs114_p9_signed/20261015T150818Z/`; no S3 signed candidate BIN
or consolidated manifest was produced. The incomplete N S3 build is preserved
under ignored `code/build/gs114_signed_s3/gs114p9N-261015T150818/`.

The Hub component gate passed its new ACK-hold gate (34 checks), signed
artifact safety (3 tests), ACK-drop gate (16 checks), S3 fixture test (15
tests) and host build (1 build). It was interrupted during board-stack E2E;
there is **no aggregate Hub PASS**. Focused BAT-C8 72 C++/11 Python, GS-150
1,500 checks, 39 fixture/signing Python tests, ACK-hold ASan/UBSan 34 checks,
traceability 204 features/211 modules/17 definitions plus 22 tests, framework
46 tests, physical catalogue 101 cases, P9-A S3 target build/profile checks,
and context preflight all PASS. Physical P9-A/B stay BLOCKED / NOT_RUN.

At pause, local/remote starting HEAD were still
`d0869cd6c128a61aff7fbc58ca448ebf439c33a9`; all GS-114 edits are staged
except this final handoff paragraph. Existing unrelated untracked PWA assets,
managed components, physical logs, readbacks and manifests remain unstaged.
No reset, cleanup, worktree switch, board operation or Jira workflow change.

**Exact resume:** Verify canonical writer/branch/HEAD/remote, context preflight
and this handoff; run the existing incremental S3 N build using
`python scripts/build_secure_fota_hub.py --s3-fixture --build-dir gs114p9N-261015T150818 --node-image build/gs114_p9_signed/20261015T150818Z/c3-n.signed.bin --output build/gs114_p9_signed/20261015T150818Z/hub-n.bin --label gs114p9N-261015T150818`
from `code/` with ESP-IDF 6.0.3 activated. Build B and R from the same reusable
S3 build directory with corresponding C3 image, output and version labels;
verify each exact embedded C3 hash, S3 profile and app version. If any build
fails, debug and retest. Then rerun affected Node/Hub/contract regressions
from a stable source snapshot, record genuine pass/fail counts, finish the
fixture observer and physical manifest prerequisites, and seek one exact P9
hardware approval. Do not mark physical PASS or deploy the dirty-source host
candidates. Preserve all current partial build logs and artifacts.


## 2026-10-15 — P9 fixture implementation and physical execution boundary

Owning Jira GS-114; scope is the default-off S3 ACK-hold and signed-FOTA
qualification fixtures. Canonical branch is `feature/r1-commercial-baseline` in
`/home/udaybhan/projects/Ghar_sajag_r1`; starting local and remote HEAD were
`d0869cd6c128a61aff7fbc58ca448ebf439c33a9`, tracked tree clean, context
preflight PASS `2026-10-13.001`. A second Codex process with the canonical cwd
was inspected and found quiescent without child work or tracked changes. All
pre-existing untracked PWA files, managed components, raw physical logs,
readbacks, manifests and firmware evidence were preserved. No board, serial,
USB, power, flash, reset, storage, commissioning, sensor or OTA operation has
been performed during this fixture implementation.

### Software work and current evidence

- The isolated S3 commissioning profile now offers `GS_HIL_C8_ACK_HOLD=ON` only
  when explicitly selected; commercial/default builds keep it OFF. The gate
  must be armed before a real PIR event. It binds the first authenticated,
  durably committed, exact-outbox EventKey `K`, holds repeated application
  Durable ACK attempts only for `K`, and restores the ordinary authenticated
  ACK path after controlled release or a 15-second watchdog. Release permits a
  freshly constructed ACK on the next exact-key retry; it does not cache or
  synthesize an ACK. The 12-second hold and 15-second watchdog are fixture
  intervals, not product latency rules. The existing GS-150 distinction between
  successful MAC/pending ACK and confirmed outage retry sleep remains unchanged.
- S3 P9-A candidate app SHA-256
  `fd9fefaecdaf34b7dadaef764882a0119bd093a8a8151a2433f79aa9144e9222`
  compiled with ESP-IDF 6.0.3, commissioning ON, broad HIL OFF, ACK-hold ON,
  ACK-drop OFF and signed-FOTA OFF. The standalone app is 1,896,112 bytes and
  embeds exactly one byte-identical existing C3 physical-wake app SHA-256
  `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
  The host build receipt is in ignored local
  `code/build/gs114_fixture_pair/build-5ig83c8k/fixture_pair_report.json`;
  the image is **not installed**. The S3 build version embeds the
  starting Git HEAD plus the working-source fingerprint; it is not proof of a
  current running image.
- The S3 signed-FOTA profile has a narrow `START_SIGNED_C3_FOTA` UART command
  for fixture C3 `c3-146393c5d158`; it queues the existing authenticated owner
  FOTA path. The command's `QUEUED` response is not an update success. Broad
  `GS_HIL_CONTROL`/`GS_HIL_BUILD` remain OFF. The host artifact workflow uses
  external 0700/0600 RSA-3072 test keys, distinct A/B/N/R versions, exact
  signed-C3 embedding and manifest hashes. It never changes commercial trust,
  burns eFuses or opens a device. The first build exposed a missing explicit
  C3 target selection; that failure log is preserved and the builder now sets
  `IDF_TARGET=esp32c3`.
- Host signed C3 candidates completed with RSA-3072 signed-on-update and
  physical-wake test controls (987,136 bytes each): A version
  `gs114A-261015T150818`, SHA `cc39459360da9bd2253c9f10254444d27b8abbeedaef46631a6f1d47561290b6`;
  B version `gs114B-261015T150818`, SHA
  `27cf9d4054bc8e4f08b1a9fd9dfbc0f2c45781ab4902fc568773f64532e94bee`;
  wrong-key N version `gs114N-261015T150818`, SHA
  `cf31eaae7f8e420b11bc36bc1f13acfa97ef4325562e264e3ec2b2ded07bf5b3`;
  recovery R version `gs114R-261015T150818`, SHA
  `6fd93f443181938e4c6efa4d1b23d6835adca0a20d7ff1b0cb4c7b2098b28dd1`.
  A/B/R public-key SHA-256 fingerprint is
  `ea49cb1b1828ec098939d3fc6c82be043713c1c213133900d61052f105b0af5f`;
  N's is `cd005db6ad63162207ea6093592d8d9dec320c75e3446af29a6540344707be4d`.
  N verification against the A trust key was rejected as expected by the host
  tool. These candidates are ignored local artifacts built from a dirty source
  checkpoint; they are not approved for target installation. S3 exact-image
  variants and the consolidated manifest remain in progress.
- Focused results so far: ACK-hold state machine 34 checks PASS; signed-FOTA and
  S3 fixture Python tests 36 PASS; artifact safety 3 PASS; P9-A S3 target
  build/profile/hash checks PASS; traceability consistency 204 features/211
  modules/17 physical definitions and 22 mapping tests PASS; framework 46
  tests PASS; physical catalogue 101 cases PASS. BAT-C8, GS-150, durable storage, recovery, FOTA and
  rejoin host regressions are being executed separately. These are **software
  and candidate-image** results, never physical P9 acceptance.
- The same ACK-hold state-machine test under ASan/UBSan passed 34 checks (exit
  0). Focused BAT-C8 passed 72 C++ checks and 11 Python tests; GS-150 passed
  1,500 checks; Hub
  durability, Node persistence, secure FOTA adapter and rejoin tests completed
  with exit 0. The component Hub gate was started with registered P9 tests;
  its final aggregate result is pending, and it cannot be reported PASS from
  partial stage output.
- Final focused Python fixture/signing/artifact-safety rerun: 39 tests PASS,
  exit 0. `tools/context/ghar_sajag_context_preflight.sh` still PASS, context
  `2026-10-13.001`. `git diff --check` and staged diff check PASS. The Hub
  component gate and S3 signed-FOTA build remain running at this checkpoint.

### Exact physical execution manifest and stop boundary

| Item | Candidate / current evidence | Before-operation requirement |
|---|---|---|
| C3 Node | MAC `14:63:93:c5:d1:58`; prior run04 installed C3 SHA `70c638…d530`; AM312 OUT GPIO4, USB-only power | Reidentify actual chip/port, active OTA slot, running app and retained EventKeys without resetting it. |
| S3 Hub | MAC `7c:4f:ad:b7:2a:20`, N16R8; prior P8 S3 app SHA `f296c984…69a8`; P9-A app candidate SHA `fd9fefae…9222` | Reidentify actual chip/port/slot and exact running bytes before any installation. Candidate build is not an installed hash. |
| Serial | Prior by-id C3 `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00`; S3 `usb-1a86_USB_Single_Serial_5CBC401023-if00` | Verify current mapping and prove reset-safe C3 observation; native USB silence after light sleep cannot prove sleep or wake. |
| P9-A operations | Install only the exact approved S3 fixture image if required; observe both boards, arm ACK hold, one real PIR event, query exact K, wait 12 s, release, verify retry/retirement and one durable logical effect | Obtain exact-operation authorization, actual pending-key inventory, current-image and observer proof first. Preserve every pre-existing key. Stop on unexpected reset, session/admission loss, unmatched K, extra event/effect or observer gap. Cancel or watchdog restores normal ACK path; do not erase storage to recover. |
| P9-B operations | Test-only signed C3 A baseline, negative N, distinct valid B, recovery R and matching S3 embedded images; authenticated trigger, target signature/slot/boot-health checks | Host artifacts are not permission to install or OTA. Verify trusted test signer fingerprint, actual C3 partition/slot, current identity/retained events, rollback route and known-good signed recovery before A/N/B/R hardware action. Stop on signer mismatch, slot uncertainty, retained-key mismatch, boot-health anomaly, observer loss or recovery unavailable. No Secure Boot/eFuse/trust-root changes. |
| Authorization | GS-146 comment 10734 accepts repeated clean use of the named disposable pair, but GS-114 comment 11107 says this does not authorize P9 board access, flashing, OTA or signed target artifacts without a specific manifest/approval. | One consolidated exact P9-A/P9-B hardware approval remains required after current board state and observer/recovery prerequisites are known. |

P9-A and P9-B remain **BLOCKED / NOT_RUN physically**. P3 remains PARTIAL
because no trustworthy existing running-S3 readback binds its controlled trace
to the candidate hash. P4's historical q10–q12 extra EventKeys remain OPEN;
there is no GPIO-edge trace to assign a cause. P5's controlled outage/recovery
PASS remains, with per-attempt retry identity LIMITED. P1/P2/P6/P7 and the
controlled P4/P5/P8 results are reused without new physical runs. P10 stays
under GS-149. GS-40 300-second heartbeat and 910-second offline threshold are
not promoted from this fixture work; caregiver PWA visibility remains separate.


## 2026-10-15 — battery-first P1–P9 closure reconciliation and resume handoff

This is the current evidence handoff following GS-114 comment 11029 and GS-110
comment 11030. It reconciles the dated case reports with the current
[qualification procedure](../TEST_PLAN.md). It is a documentation-only
checkpoint: no USB/serial access, board operation, flash, reset, erase, OTA,
power operation, motion stimulus, or commissioning was performed; no software
tests or full release gate were rerun.

**Checkpoint:** canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`,
branch `feature/r1-commercial-baseline`, local HEAD and actual origin HEAD
`97eff6c2ed927d641cd3ee3b9854dd8c38cb176b` before this documentation update;
context preflight PASS (`2026-10-13.001`). Tracked tree was clean before edits.
Pre-existing untracked PWA assets, ESP-IDF managed components, raw GS-114 logs,
binary readbacks, manifests and installation evidence remain preserved and
unstaged.

### P1–P9 physical closure matrix

The same R&D fixture is the C3 `14:63:93:c5:d1:58` with AM312 OUT on GPIO4 and
the S3 `7c:4f:ad:b7:2a:20`, USB powered; the case reports retain run-specific
power, wiring, source and image details. P1/P2 use test checkpoint
`9674075f1911dbad076fdcdb1c541a283dfbb748`, firmware build source
`72a223fc3b290c01c9f93fbb90db83d87601ad54`, C3 SHA-256
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814`, and S3
SHA-256 `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`.
The later case-specific provenance is kept in each linked report.

| Case | Reconciled disposition | Preserved physical evidence and provenance | Limitation / blocker |
|---|---|---|---|
| P1 timer sleep/wake | **PASS** | 10 real timer sleep/wake cycles; radio/runtime recovery and no false event; same run03 image pair above. [Case report](run03_20261014/C8_P1.md) | C3 console unavailable during sleep; authenticated Hub NodeHealth used. |
| P2 real AM312 wake | **PASS** | Real EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1`; one durable effect, Durable ACK and Node retirement; same run03 pair. [Case report](run03_20261014/C8_P2.md) | No latency claim beyond the captured case timestamps. |
| P3 held-HIGH inhibition | **PARTIAL — behavior PASS** | C3 installed SHA `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; measured 28,518 ms continuous GPIO4 HIGH, +1,425 inhibit samples, zero sleep entries while HIGH, one event/ACK/retirement, then 11 timer sleep/wake cycles after LOW. [Controlled report](run04_20261014/C8_P3_CONTROLLED_20261014.md) | S3 build candidate `ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379` is **not** the verified running S3 hash. Boot/UART and existing local build artifacts do not establish byte-for-byte running provenance. No hash is inferred; catalogue remains PARTIAL. |
| P4 motion → ACK → retirement | **PASS for controlled q16 retest** | C3/S3 hashes are the run03 pair; checkpoint `72716c141a788b251e6b630f4684df12028ea847`; q16 durable effect, same-key duplicate idempotence, authenticated ACK and retirement. [Case report](run03_20261014/C8_P4.md) | Preserve the earlier q10–q12 three-event observation as an unresolved separate FAIL: exact GPIO edges were not captured and cause is unknown. Retest did not reproduce it. Light-sleep C3 UART is unavailable; GPIO wake counter proves functional path but not internal marker order or PIR-to-ACK latency. |
| P5 Hub outage/recovery | **PASS for controlled run03 q24** | Checkpoint `988fa44ee1207ed67a3a253a5eb2c9dc7813277b`; run03 image pair above; one real event during Hub outage, newer authenticated session/RPF00 OPEN, one durable effect, ACK and retirement, no Node reset. [Case report](run03_20261014/C8_P5.md) | Retry aggregate advanced by three, but the exact key was observed at Hub admission, not logged on every failed Node radio attempt; per-attempt key identity is inferred. Preserve run02 as inconclusive. |
| P6 Hub-only reboot/rejoin | **PASS** | Checkpoint `1e433477f67cbc01dad8cffa0655e2eec257d409`; run03 image pair; newer authenticated session and unchanged Node reset counter. [Case report](run03_20261014/C8_P6.md) | Earlier run01 startup-banner capture gap remains in its case report. |
| P7 first PIR after Hub reboot | **PASS** | Same checkpoint and pair as P6; q22 first post-reboot event, one durable effect, authenticated ACK and retirement without Node reset. [Case report](run03_20261014/C8_P7.md) | Physical stimulus onset was not instrumented. |
| P8 lost application ACK | **PASS for q14** | S3 image SHA `f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`, build source `ce9c436f0e9a8324c0785bad996ed9c4a421de3d`, C3 SHA `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; active `ota_0` app write was verified. q14 was durably committed once, first application ACK withheld, same key retried, duplicate effect suppressed and Node retired. [Physical report](run04_20261014/C8_P8_PHYSICAL_20261014.md) | Operator movement preceded the direct prompt; onset/latency unavailable. No separate post-run full-partition readback. Later capture failure is outside the PASS interval. |
| P9-A authenticated ACK hold/release | **BLOCKED / NOT_RUN** | No qualifying physical run exists. Software regression is separately PASS and documented in [P9 software report](run05_software_20261014/C8_P9_SOFTWARE_VALIDATION_20261014.md). | Need bounded hold >10,000 ms, exact-key ledger view, continuously verified reset-safe target observation, then authenticated release/retirement. Existing P8 one-shot drop and fixture are insufficient. |
| P9-B signed-FOTA sleep inhibition | **BLOCKED / NOT_RUN** | Host/state-machine coverage is PASS only; no current matched signed physical image campaign. | Need trusted A/B/N signing manifest and target trust config, exact Hub embedded image, supported authenticated trigger, actual slot readback, reset-safe capture, and proven signed recovery/rollback. |

**Aggregate:** GS-114 is **PARTIAL / In Progress**. P1, P2, P4, P5, P6, P7 and P8 have reusable PASS evidence. P3 behavior passed but source/image provenance remains partial. P9 has two blocked physical subcases. P10 is separate under GS-149. No test case or overall ticket is promoted to PASS from host simulation.

### P3 provenance investigation and P4/P5 limitations

P3's controlled report ties the C3 trace to installed image SHA
`70c638…d530` and source trace commit `c69960fb064a60c3e6dc52b27d90fbbbe30b560a`.
The S3 candidate hash is recorded, but the S3 running app was not read back and
the available boot/capture evidence does not bind the running bytes to that
candidate. P3's measured GPIO behavior remains valid evidence for its observed
run, but it is not an image-matched full qualification; do not replace the
unknown hash with a build hash. Resolving this provenance would require a
separately approved, read-only target identity/image observation or a focused
repeat only if the provenance remains necessary and cannot be recovered safely.

P4 retains its first q10–q12 single-reported-episode trial as a failed,
unexplained observation while the later controlled q16 retest passed. Since
GPIO4 transitions were not captured during the first trial, do not diagnose a
sensor or firmware defect from it. P5's controlled run03 passes the outage and
recovery behavior, but per-attempt retry-key identity was not directly logged;
the exact key is visible at Hub admission. Preserve that evidence limit and the
earlier run02 capture gap.

### P9 fixture procedures and hard prerequisites

The [C8-P9 procedure in TEST_PLAN](../TEST_PLAN.md#c8-p9--authenticated-ack-hold-and-signed-fota-sleep-inhibition)
now defines separate P9-A ACK-hold/release and P9-B signed-FOTA cases. P9-A's
fixture must hold the valid ACK for 12 seconds after durable commit, with a
15-second watchdog, preserve Node-to-Hub uplink, prove one exact-key durable
effect, continuously observe no Node sleep entry, then release the original
authenticated ACK and prove retirement. The current P8 one-shot suppresses
only one ACK and cannot supply that interval; the confirmed setup has no
directional RF attenuator/shield or per-key read-only ledger.

P9-B requires a signed baseline A, valid distinct-version B, wrong-key N,
external disposable signing keys with public fingerprints, matching C3 trust
configuration, exact B bytes embedded in the authenticated Hub image, actual
OTA slot/partition verification, a supported authenticated target trigger,
boot-health and rejoin observation, and known-good recovery/rollback that
preserves identity and retained EventKeys. The current S3 fixture profile has
no supported FOTA trigger. The older Phase-2 signed-FOTA physical campaign
(target-qualified code `60f91b421cc244c2b12fd92c244683c7f69ce0a6`, evidence
directory `evidence/hil/runs/20260925T194530.402772Z`) is retained as
historical evidence only; it does not qualify current C8 P9 sleep inhibition or
current firmware provenance. CloudSync RSA/mTLS work does not provide FOTA
signing authority.

No physical case may start until the applicable authorization names the exact
C3/S3 pair and ports, image hashes and OTA/reset actions, power/wiring,
reset-safe observer, pending-state checkpoint, stop conditions and recovery
steps. No eFuse changes, factory reset, storage erase, full-device flash or
recommissioning is part of this plan.

### GS-40 heartbeat and GS-144 workload coordination

**GS-40 remains open for real-target acceptance.** The C8 P1–P8 evidence proves
its stated functional cases only; it does not prove a matched real-target
300-second NodeHealth cadence over six quiet opportunities, event piggyback
suppression, 910-second silent-Node expiry/recovery, mixed legacy identity
profiles, or actual caregiver PWA visibility. `PHY-GS40` remains NOT_RUN.
Reuse overlapping C8 evidence only when the exact GS-40 source/image/config and
physical profile match; do not rerun completed GS-40 software tests.

**GS-144 remains product-PENDING.** The 150–180-day aspiration, proposed
`>=150 day` minimum, event rates, candidate DMEGC 18650 usable capacity/reserve,
Hub-offline workload and numeric caregiver latency/reliability bounds are not
approved. One consolidated owner decision sheet must resolve:

| Owner input | Current state |
|---|---|
| Reproducible ordinary events/day, PIR bursts and time distribution | OPEN; define a representative household profile |
| Idle health policy | GS-D031-approved 300-second standalone opportunity; validate event-contact piggyback under that profile |
| Hub-offline/rejoin | OPEN; define outage frequency/duration, retry/recovery workload and installation/RF assumptions |
| Battery and usable reserve | OPEN; choose the commercial cell and approve capacity, reserve, ageing and temperature basis; nominal 2,900 mAh and DMEGC candidate are not accepted values |
| Measurement boundary | OPEN; include cell, regulator, C3 board, PIR, LEDs and other leakage; identify the instrument and calibration profile |
| Caregiver reliability and latency | OPEN; set acceptable first-event delivery/ACK and offline/recovery visibility bounds |
| Endurance target | 150–180 days remains aspiration; proposed `>=150 days` minimum is not approved; owner must select minimum and preferred target |

After approval, follow the ordered prerequisites in GS-110: GS-140 instrument
and measurement boundary; GS-41/GS-42/GS-141/GS-43 BEFORE cases; GS-44 baseline
review; matched GS-51 AFTER; GS-119 residual C1–C4, GS-46 first-motion latency
and GS-69 12-hour soak. Then feed qualified results to GS-149. No current or
endurance is inferred from software counters.

### Next Plan

1. Keep GS-114 In Progress and reuse the valid P1/P2/P4–P8 evidence; keep P3
   PARTIAL until exact S3 provenance is recovered or an approved focused run
   supplies it; preserve P4's unresolved initial failure and P5's retry-key
   visibility limitation.
2. Resolve P9-A's bounded ACK fixture, read-only exact-key ledger and reset-safe
   target observer; resolve P9-B's signed A/B/N artifacts, trusted verifier,
   authenticated trigger, verified slots and recovery route. Submit one
   fixture-specific operation request only after all non-hardware prerequisites
   are reviewable.
3. Coordinate GS-40's real-target 300/910-second plus caregiver-view evidence
   without repeating completed software coverage. Prepare one GS-144 owner
   approval sheet with the still-open workload, battery, reserve, measurement
   boundary and reliability values before B0–B4/GS-51/GS-149 measurement work.
4. Do not touch hardware or run a release gate as part of this handoff. No
   software test was repeated; P10 remains GS-149 and C9–C11 remain out of this
   task.

## 2026-10-14 — P9 software validation complete; physical fixtures remain blocked

P9 software coverage was audited and completed without hardware access. The
production-code GS-150 Node/Hub simulation now includes an explicit pending
authenticated Durable ACK → sleep-inhibited beyond the 10,000 ms receive
budget → exact-key retirement → normal idle sleep eligibility transition.
`make gs150-host-test` and its ASan/UBSan run passed at 1,500 checks. Existing
P9-related evidence was reused: BAT-C8 72 C++/11 Python checks, secure-FOTA
adapter 2 groups, FOTA host 34 checks, board-stack E2E 8 groups/325 checks,
signed-FOTA fixture orchestration 16/16 and feature-coverage mapping
175 features/205 modules/15 physical cases passed. Details, commands, limits
and fixture requirements are in
[P9 software evidence](run05_software_20261014/C8_P9_SOFTWARE_VALIDATION_20261014.md).

**P9 ACK software simulation: PASS; physical ACK sleep-inhibition: BLOCKED /
NOT_RUN. P9 FOTA software state/signing-fixture coverage: PASS;
physical signed-FOTA: BLOCKED / NOT_RUN.** The Python signed-FOTA fixture
checks validate host orchestration and artifact guards, not cryptographic
acceptance by an ESP32 target. No board, serial port, image or commissioning
state was accessed or changed. A bounded long ACK-hold fixture with trusted
per-key evidence is still required for physical ACK qualification. Signed FOTA
still requires a matched signed test/recovery pair, trusted signer provenance,
supported authenticated trigger and safe rollback plan. P10 remains GS-149.

`make validation-node` and `make validation-contract` reached the registered
P0 product E2E and returned gate FAIL because `product_status=PARTIAL` and
`physical=NOT_RUN`, despite all 26 P0 scenario assertions passing. This
existing release gap is independent of P9 and remains visible. GS-114 remains
In Progress. Previous RPF07 and C8 P1–P8 physical PASS evidence is reused;
none was repeated in this software-only run.

## 2026-10-14 12:12 UTC — C8-P8 physical lost-ACK PASS

The source-matched S3 P8 fixture was installed app-only at the verified
`ota_0` offset `0x20000`. The installed app write hash was verified by esptool;
the boot log reports `ce9c436f0e9a-gs114-c8p8-59b8341` on that slot. Candidate
S3 app SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`; its
embedded C3 app SHA-256 matches the installed C3 diagnostic image
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.

At `12:11:57Z`, the one-shot postcommit ACK-drop fixture armed for 30 seconds.
At `12:12:11Z`, the Hub received EventKey
`p15:c3-146393c5d158n8:gs114-c8s16q14` under OPEN RPF00 admission, committed it
durably (`state_changed=1`, `records=43`, exact outbox key found), then withheld
the application ACK. Same-key retransmissions were observed with
`state_changed=0` and unchanged records. Authenticated Durable ACK sends
returned `ESP_OK`; NodeHealth at `12:12:13Z` showed `retained=0`,
`durable_ack=14` (+1), and `retry=15` (+2). The deferred GPIO trace reported a
GPIO wake, radio restoration OK and owner resumed. This establishes **C8-P8
physical PASS**: a single durable logical effect, same-key retry, duplicate
idempotence, and eventual authenticated Node retirement.

The operator later clarified that the real movement occurred before the direct
action prompt. Its exact timestamp is unavailable, so the prompt is not claimed
as the cause of q14 and no stimulus-to-event latency is claimed. The event and
GPIO/PIR counters occurred inside the armed window. A separate later arm at
`12:14:59Z` had no following event/health in its capture; USB/IP URB errors
(`-104`) and serial write timeouts were observed. That later interval is not
part of the PASS evidence. Logs and details are in
[`C8_P8_PHYSICAL_20261014.md`](run04_20261014/C8_P8_PHYSICAL_20261014.md).
No source code changed. After the later capture attempt stalled, no further
reset, reattach, flash, power operation or serial command was performed.

## 2026-10-14 11:32 UTC — S3 P8 app write verified; runtime verification blocked

The operator approved the bounded S3-only procedure. Windows identified the
S3 CH343 as BUSID `3-1`, COM9, VID:PID `1a86:55d3`, serial `5CBC401023`,
`Attached`; WSL's stable by-id path mapped to `/dev/ttyACM0`. C3 remained the
Windows `0000:0002` descriptor-error device and was not attached, opened,
reset, flashed, or otherwise accessed.

One controlled S3 ROM-mode entry identified ESP32-S3 revision 0.2, MAC
`7c:4f:ad:b7:2a:20`, 16 MiB flash, and 8 MiB PSRAM. Read-only security
information showed Secure Boot disabled, Secure Download disabled, and
`FLASH_CRYPT_CNT=0`. The actual partition table matched the candidate's
compiled table byte for byte over its 3,072-byte payload; the remainder of
the 4,096-byte read region was erased `0xff`. The valid `otadata` copy 0 had
sequence 1, state 2, and valid CRC, selecting `ota_0` at `0x20000`. The table
retained `ota_1`, `gs_outbox`, and `gs_state` at their expected offsets.

The selected current-source S3 app was written **only** at `0x20000`:
`gs_r1_s3_hub.bin`, 1,894,496 bytes, source/build commit
`ce9c436f0e9a8324c0785bad996ed9c4a421de3d`, SHA-256
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`.
Esptool reported the erase/write range as `0x00020000–0x001eefff`, verified
the written data hash, and performed the expected hard reset. No bootloader,
partition table, `otadata`, NVS, `gs_outbox`, `gs_state`, C3, commissioning,
or security data was written.

An exclusive ESP-IDF monitor was opened on the stable S3 by-id path with
`--no-reset` and remained attached for at least one 300-second NodeHealth
interval. The USB/IP device remained `Attached` and the monitor owned the
port, but **no S3 UART bytes** were received. Two read-only `FIXTURE_STATUS`
commands were attempted through that monitor and no response was observed.
The monitor was then closed cleanly; the S3 port is now unowned. There is no
boot banner, running app identity, fresh authenticated C3 rejoin, NodeHealth
schema-3 trace, RPF00 OPEN evidence, or post-install Durable ACK evidence.
The app-partition write is verified, but the running firmware and Hub runtime
are **not verified**. The exact cause of the silence is unknown; it does not
by itself prove a Hub crash or a USB/IP disconnect.

**C8-P8 disposition: BLOCKED before physical stimulus / physical test NOT RUN.**
No PIR movement or ACK-drop command was issued. P8 requires a verified running
Hub, fresh authenticated C3 rejoin, schema-3 trace, and RPF00 OPEN before the
one-shot postcommit ACK-drop fixture can be armed. No further reset, flash,
power operation, or recovery image is authorized by the present scope. P3 and
previous RPF07/P1/P2/P4/P5/P6/P7 PASS evidence is preserved and reused. P9
ACK/FOTA remain BLOCKED; P10 remains under GS-149.

Readback, selector validation, flash log and monitor capture are in
[`run04_20261014`](run04_20261014); the detailed installation record is
[`C8_P8_BUILD_VALIDATION_20261014.md`](run04_20261014/C8_P8_BUILD_VALIDATION_20261014.md).
No firmware source changed. Current local/remote source HEAD before this
evidence update was `ead9a83b9df0a1cc928280760496747f1901e38e`.

## 2026-10-14 11:07 UTC — source-matched P8 S3 candidate build PASS

The operator approved Python 3 for the existing ESP-IDF 6.0.3 P8 build and
offline validation. Tooling commit
`ce9c436f0e9a8324c0785bad996ed9c4a421de3d` adds an S3-only mode to the
existing builder: it verifies and embeds the installed C3 app by SHA-256,
skips the C3 build, and does not access hardware. The current S3 image built
successfully with ACK-drop ON and broad Hub HIL control OFF. Candidate app
SHA-256:
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`;
size 1,894,496 bytes. Embedded C3 SHA-256 exactly matches installed C3
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
The generated and compiled S3 partition tables match the commissioned
16-MiB/8-MiB PSRAM layout with `ota_0`/`ota_1`, `gs_outbox` and `gs_state`.

Focused validation: S3 fixture suite 14/14 PASS, ACK-drop gate 16/16 PASS,
ASan/UBSan 16/16 PASS, TSan 16/16 PASS, and offline ESP-IDF image/profile,
embedded-asset and partition compatibility checks PASS. See [P8 build
evidence](run04_20261014/C8_P8_BUILD_VALIDATION_20261014.md) and local ignored
build manifest `code/build/gs114_fixture_pair/build-snmafa7y/fixture_pair_report.json`.
No device/serial access, reset, flash, erase, commissioning change or physical
test occurred.

The last captured S3 boot banner reports active app offset `0x20000` (`ota_0`)
at 03:34:27 UTC, but its app version is
`72a223fc3b29-gs114-rpfdiag-1eec`; exact current running S3 hash and a fresh
post-detach OTA-selector readback are still unverified. The installation plan
requires reattachment of only the identified S3, restored exclusive capture,
fresh active-slot verification, then an S3 app-only write at `0x20000` only
if that same `ota_0` selection is confirmed. No generated full-device flash
bundle will be used. The detailed recovery and capture-restoration plan is in
the P8 evidence and awaits explicit installation approval. C3 remains
untouched.

P3 remains a controlled physical PASS. Reuse previous RPF07/P1/P2/P4/P5/P6/P7
PASS evidence. P8 is still physical NOT_RUN until the candidate is installed
and an exact-key real ACK-loss/retry/durable-effect/retirement trace is
captured. P9 ACK/FOTA remain blocked on their separate fixtures; P10 is
GS-149. GS-114 remains In Progress.

## 2026-10-14 10:08 UTC repeat S3 USB/IP observation loss

After P3, the S3 capture received authenticated session-16 health sequence 25
at `10:06:33Z`, then stopped. Windows `usbipd-win` logged release of the exact
S3 CH343 at `10:07:57Z` and socket abort 10053 at `10:07:58Z`; Windows now
reports it **Shared** rather than Attached. WSL's by-id `/dev/ttyACM1` and
capture PID 324978 remain visible but are stale observer evidence. This is a
second host USB/IP transport interruption, not proof of Node/Hub firmware
failure. No new attach, reset, port writer or physical test was attempted.
See [repeat failure evidence](run04_20261014/S3_USBIP_CAPTURE_DIAGNOSIS_20261014.md).
P3's completed controlled evidence remains valid; P8 must await a verified
source-matched image and working S3 observer.

## 2026-10-14 controlled P3 physical retest — measured held HIGH PASS

The operator reattached only the identified S3 CH343 to WSL. The existing
exclusive capture PID 324978 recovered on `/dev/ttyACM1` without a competing
reader or observed Hub reset; the previously blocked status writer had exited.
The returning stream showed continuous Hub uptime, authenticated C3 session 16
and health sequence 19 at `09:49:06Z`, decoded schema-3 trace and `RPF00`
admission OPEN. Thus the earlier missing 300-second reports were a USB/IP
observation gap, not evidence of a C3 or Hub application stoppage. C3 Windows
USB remains descriptor-error `0000:0002` and was not accessed.

One controlled real AM312 movement was prompted at `09:50:56.473Z`; the
operator replied DONE at `09:51:50.807Z`. The authenticated C3 trace measured
**one continuous GPIO4 HIGH episode of 28,518 ms** (total/highest duration
delta), **1,425** additional sleep decisions inhibited by HIGH, and **zero**
sleep entries with GPIO4 HIGH. Exactly one PIR event was qualified, EventKey
`p15:c3-146393c5d158n8:gs114-c8s16q2`. The Hub recorded one new durable
effect (`records=31`, exact outbox key found, admission OPEN); the same-key
repeat had `state_changed=0` and unchanged record count. Both authenticated
Durable ACK sends returned `ESP_OK`; Node health advanced durable ACK count by
one and retained count stayed zero. At `09:56:40Z`, a fresh authenticated
schema-3 trace showed GPIO4 LOW, **11** further sleep entries and **11** timer
wakes after the previous sample, last wake TIMER, radio restore OK and owner
resumed. No additional PIR event, GPIO wake, reset or stall was observed.

**C8-P3 physical behavior PASS** under the test-only authenticated trace.
See [controlled case evidence](run04_20261014/C8_P3_CONTROLLED_20261014.md),
[focused S3 excerpt](run04_20261014/p3_run01_s3_excerpt.log) and the preserved
untracked full raw capture. The C3 app SHA-256 is verified as
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
The exact running S3 app hash remains unverified; candidate build SHA-256
`ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`
is not presented as installed-image proof. This provenance limit remains open
for release reconciliation. Prior P3 unsuccessful/unstimulated windows remain
separate evidence. RPF07/P1/P2/controlled P4/P5/P6/P7 PASS cases are reused.
P8 physical ACK-loss is next; the currently paired S3 build has the ACK-drop
fixture OFF and the older ON build is source-mismatched, so no P8 flash/test
has been attempted. P9 ACK/FOTA remain fixture-blocked and P10 is GS-149.
GS-114 remains In Progress.

Post-window observation: the same exclusive raw capture later received q3
`MOTION`, q4 `MOTION_SUMMARY` and q5 `MOTION` at `09:58:48–10:01:33Z`, after
the controlled q2 run and its `09:56:40Z` GPIO4 LOW/timer-recovery sample.
Authenticated trace reported three separate short GPIO4 HIGH episodes and
LOW between reports. Each distinct key had one durable logical effect and an
authenticated ACK; the source of the later PIR activity is unknown. See the
case report's later-activity section. These observations are not folded into
the controlled P3 stimulus or represented as a false alarm finding.

## 2026-10-14 S3 USB/IP observation failure diagnosed

Read-only Windows event evidence now explains the missing S3 UART output after
the prior P3 readiness check. At `08:37:43Z`, `usbipd-win` recorded a socket
abort (10053) and release of the exact CH343 S3 serial device
`1a86:55d3` / `5CBC401023` on BUSID `3-1`. This occurred after the last
authenticated session-16 NodeHealth/schema-3 trace at `08:35:48Z` and before
the next 300-second heartbeat was due. Windows now reports the S3 as `Shared`,
while WSL retains a stale by-id tty and capture PID 324978 still holds its old
fd. A single attempted `FIXTURE_STATUS` through that fd blocked during open
and **sent no bytes**. The absence of the later heartbeat or `online=0` UART
line cannot be used to diagnose C3 or Hub firmware liveness. Source review
found the expected 1000 ms Hub liveness check and 910-second authenticated
contact lease; no firmware defect has been demonstrated.

See [the dated S3 transport diagnosis](run04_20261014/S3_USBIP_CAPTURE_DIAGNOSIS_20261014.md)
and preserved first-failure snapshot. The exact cause of the host USB/IP socket
abort remains unknown. No reset, flash, erase, recommission or new physical
test occurred. A bounded S3-only serial reattachment requires operator
authorization because reopening the serial path may reset the Hub. C3's current
Windows USB descriptor error is separate from its unverified ESP-NOW state;
do not attach that unknown device. P3 remains BLOCKED / NOT RUN, P8 physical
NOT_RUN, and P9 ACK/FOTA BLOCKED. Reuse the prior RPF07/P1/P2/controlled
P4/P5/P6/P7 physical PASS evidence.

## 2026-10-14 P3 readiness recheck — movement deferred because liveness is stale

The operator is available for one controlled AM312 movement episode. The
fixture was not ready, so no movement request was issued. The exclusive S3
capture PID 324978 remains the sole `/dev/ttyACM0` owner and targets the run04
log, but it has received no bytes after the authenticated schema-3 trace at
`08:35:48.465006359Z`; the log mtime is unchanged. A running reader process
does not establish that serial output is arriving.

The last authenticated NodeHealth is session 16 / health_seq 4 at
`08:35:48.443225859Z`, followed by its trace at `08:35:48.465006359Z`. The
trace reports GPIO4 LOW, no retained work, timer wake, radio restore OK and
owner resumed. With heartbeat=300 s, another report was expected at about
08:40:48 UTC. None was captured. The configured 910 s offline lease from the
last health elapsed at `08:50:58.443225859Z`, before the 08:59:02 UTC check.
There is no explicit `online=0` line, so current evidence cannot identify
whether the Node stopped, Hub runtime stopped logging, or the observation path
failed. Current authenticated liveness and fresh OPEN replay-admission evidence
are unverified.

No reset, USB/IP attach, port probe, Hub command, flash, erase, recommission,
or power change occurred. The previously authorized single C3 reset has
already been used; no repeat was made. **C8-P3 remains BLOCKED / NOT RUN.**
Resume with passive capture until new authenticated session/health, schema-3
trace and OPEN replay admission are observed. Then issue one 20–30 s movement
request and correlate the actual GPIO4 HIGH duration, sleep inhibition, event
keys, durable effects, ACK/retirement and LOW recovery. Preserve the known
C3 image SHA; the exact running S3 image SHA remains unverified.

At this checkpoint local and remote HEAD were both
`e4e036a5d3c92bd7d53ce478a5d4e8099cc957b9`, and context preflight passed as
`2026-10-13.001`. No code or firmware changed. Existing untracked evidence and
unrelated assets remain preserved. GS-114 stays In Progress; prior RPF07, P1,
P2, controlled P4/P5, P6 and P7 physical PASS evidence remains reused without
retest. P8 remains next after P3; P9 ACK/FOTA stays blocked; P10 belongs to
GS-149.

## 2026-10-14 controlled C3 reset recovery — P3 stimulus pending

The operator authorized one C3-only EN/RST reset after the pre-reset Hub
capture was preserved. The existing S3 reader observed authenticated C3
rejoin as session 16 at `08:15:49.543439605Z`, liveness online at
`08:15:50.028801212Z`, RPF00 `PREPARED admission=OPEN` at
`08:15:59.778409608Z`, and authenticated retirement ACK send `ESP_OK` at
`08:15:59.786565707Z`. Authenticated NodeHealth and schema-3 sleep traces
arrived on the configured heartbeat at 08:20:49, 08:25:48, 08:30:48 and
08:35:48 UTC. Across health_seq 1–4 the Node remained in session 16 with no
retained events, no PIR edges, GPIO4 LOW, no GPIO wakes, timer sleep/wake
counts 10→20→30→40, radio restoration OK, owner resume OK, and no offline
transition by 08:36:11.
This verifies successful post-reset operation and sustained authenticated
liveness. `reset=1` was preserved as the raw reported field; because it was
also present before reset and there is no C3 boot UART for this action, it does
not alone identify the physical reset source.

The operator is away, so no P3 motion occurred. The zero-HIGH trace is a quiet
baseline, not a P3 attempt; **P3 remains BLOCKED / NOT RUN** pending one
controlled real AM312 stimulus after fresh readiness is confirmed. No new
`usbipd attach`, C3 USB serial probe, flash, erase, S3 reset, recommission, or security
change occurred. The current C3 app remains SHA-256
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; exact
active S3 image hash remains unverified. See the [reset recovery evidence and
resume handoff](run04_20261014/C3_RESET_RECOVERY_AND_P3_HANDOFF_20261014.md).

**Current matrix:** RPF07 PASS (reused); P1 PASS (reused); P2 PASS (reused);
P3 BLOCKED / NOT RUN awaiting operator stimulus; P4 PASS (controlled retest
reused, earlier q10–q12 issue retained); P5 PASS (controlled outage retest
reused, retry observability limitation retained); P6 PASS (reused); P7 PASS
(reused); P8 physical NOT_RUN; P9 ACK and signed-FOTA BLOCKED; P10 remains
separate under GS-149. GS-114 remains In Progress.

## 2026-10-14 diagnostic installation checkpoint — C3 image verified; physical P3 pending

The committed c69960f observer build was verified against its manifest and the
C3 app-only update completed without erasing commissioning or durable state.
The C3 image SHA-256 is
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; the
actual C3 MAC/revision/flash were `14:63:93:c5:d1:58`, ESP32-C3 v0.4, 4 MiB.
The active `ota_0` slot at `0x20000` was verified, the write hash matched,
and a later partition/otadata read again selected `ota_0`. The C3 then sent
authenticated NodeHealth schema 3 and a physical GPIO/sleep trace through the
Hub. The Hub's S3 runtime decoded the trace and answered `FIXTURE_STATUS`.
The candidate S3 image hash is
`ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`; its
exact active flash hash was not read back, so it is not asserted as the exact
running S3 SHA.

The latest authenticated trace (session 15, health_seq 1 at 06:37:24.506Z)
reported one sampled GPIO4 HIGH episode with 6,793 ms max duration, 339
sleep-inhibition samples, zero sleep entries while HIGH, GPIO wake, successful
radio restoration and owner resume. This proves the deferred trace is received
and decoded. The associated setup events were unsolicited and have no
controlled stimulus timestamp, so they are not counted as a P3 result. The Hub
later reported Node liveness offline at 06:52:38.225Z. `FIXTURE_STATUS` at
06:58:28.214Z returned `state=idle`. A later sustained-motion action was
requested, but no completion confirmation or new authenticated Hub line was
received; P3 therefore remains BLOCKED and no reset/reflash/recommission was
performed. Full provenance and limits are in
[the run04 installation/trace note](run04_20261014/C8_C3_DIAGNOSTIC_INSTALL_AND_TRACE.md).

**Current matrix:** RPF07 PASS (reused); P1 PASS (reused); P2 PASS (reused);
P3 BLOCKED; P4 PASS (controlled retest reused, earlier q10–q12 issue retained);
P5 PASS (controlled outage retest reused, retry observability limitation
retained); P6 PASS (reused); P7 PASS (reused); P8 physical NOT_RUN; P9 ACK and
signed-FOTA BLOCKED; P10 is separate under GS-149. GS-114 remains In Progress.

P8's c699 S3 image profile has ACK-drop disabled. The older ACK-drop image
recorded in run03 is from a different source checkpoint and cannot be installed
as the source-matched pair without a current-source build. P9 still lacks the
long ACK-hold observation fixture and a qualified signed test/recovery image,
authenticated trigger and recovery plan.

## Latest run03 checkpoint — 2026-10-14 03:58 UTC

The controlled P7 first-event-after-reboot case now **PASSes**. Hub-only
reboot booted with `POWERON` at 03:34:27.008Z; authenticated Node rejoin
advanced to session 4 at 03:41:27.932Z; RPF00 remained OPEN. The first
post-reboot event after pre-reboot q21 was the operator-requested real AM312
event q22 `p15:c3-146393c5d158n8:gs114-c8s1q22` at 03:52:15.856Z. The Hub
committed one effect, two same-key repeats made no further state changes, and
authenticated retirement ACK send returned `ESP_OK`. NodeHealth at 03:57:15
confirmed `reset=11 retained=0 durable_ack=22 pir_ok=27 gpio_wakes=27`.
The Hub boot banner was captured in full. See [P6 run 02](run03_20261014/C8_P6.md)
and [controlled P7 run 02](run03_20261014/C8_P7.md).

Current statuses: P1/P2 PASS; P3 BLOCKED because the held-HIGH interval lacks
direct GPIO-level/sleep-inhibition evidence; P4 PASS on controlled retest while
the original q10–q12 multiplicity failure remains unresolved; P5 retest is
pending a reconnect-aware exclusive S3 reader; P6/P7 PASS; P8 physical NOT_RUN;
P9 ACK/FOTA blocked on separate fixture prerequisites. No firmware or image
change occurred. Existing authenticated commissioning and image hashes remain
unchanged. Next, transition the single S3 observer to reconnect-aware capture,
then execute P5 with one isolated real motion while only the Hub USB is off.
GS-114 remains In Progress; P10 remains separate under GS-149.

## Latest run03 checkpoint — 2026-10-14 03:25 UTC

The installed, commissioned R&D images remain unchanged. The operator completed
another real sustained-movement P3 attempt. Four distinct PIR EventKeys q17–q20
were durably accepted and ACKed, with same-key retries deduplicated. Authenticated
NodeHealth at 03:25:04.945156252 UTC confirmed `pir_raw=0`, retained=0, reset=11,
durable_ack=20, and continued timer/sleep counters. No C3 UART or direct GPIO4
trace captured the active-HIGH interval, so P3 remains BLOCKED for held-HIGH
sleep inhibition and the four distinct motion events remain unexplained. The
post-stop LOW and normal timer/sleep recovery are observed. Details are in
[C8-P3](run03_20261014/C8_P3.md); the complete live Hub capture is
`run03_20261014/s3_uart_timestamped.log`.

P4's controlled q16 retest remains PASS; its earlier q10–q12 one-stimulus
multi-event failure remains separately preserved. P5 remains BLOCKED/inconclusive,
P6 PASS, and P7 requires a controlled first motion after a new Hub-only reboot.
Before P5, replace the current S3 reader with a single reconnect-capable reader;
the current exclusive reader does not reopen after the Hub USB interface
disappears. Keep P8 physical NOT_RUN and P9 ACK/FOTA blocked on their fixture
prerequisites. No firmware change, reset, reflash or recommission occurred.
GS-114 remains In Progress; P10 remains separate under GS-149.

## Latest run03 checkpoint — 2026-10-14 03:13 UTC (campaign active)

The run03 code checkpoint is `72716c141a788b251e6b630f4684df12028ea847`; the
bounded default-off P8 implementation and target evidence are committed there.
The subsequent q15/q16 evidence and handoff commits are `610c3f3d754ef647d9b0ab0faa284b0465928470`,
`9664b4b9848a67f290dabfe2108c8dd06051675c`, and
`0ae61bd2234da0af8fb1a636cc58f4ef4380347d`; local and GitHub HEAD matched at
the last check. The existing physical pair remains on the previously verified
commissioned images; no reset, reflash or recommission occurred. The exclusive
timestamped S3 capture remains active.

Authenticated NodeHealth at `2026-10-14T02:53:43.472786229Z` was session 3,
health_seq=115, reset=11, retained=0, durable_ack=14, pir_ok=19, gpio_wakes=19,
sleep_entries=1212, timer_wakes=1193, last_wake=TIMER. Four seconds later, with
no controlled motion request/window established, the S3 recorded a qualified
PIR event `p15:c3-146393c5d158n8:gs114-c8s1q15`: first authenticated durable
effect at 02:53:47.987Z (`state_changed=1`, records=15, exact-key outbox found,
admission OPEN), Durable event ACK `ESP_OK`, same-key repeat with
`state_changed=0`, and RPF00 remaining OPEN. An authenticated retirement ACK
send under Hub session 3 returned ESP_OK. The event is an unsolicited physical
observation with no attributable operator stimulus; it is not counted as a
controlled P7 PASS. Authenticated NodeHealth at `02:58:47.560721096Z`
(health_seq=116) then confirmed `retained=0`, `durable_ack=15`, `pir_ok=20`,
`gpio_wakes=20`, reset=11. q15's physical wake and Node retirement are
confirmed; its external motion source and exact GPIO assertion time remain
unknown. P7 stays BLOCKED for the controlled stimulus/timestamp evidence.

The operator then completed one brief, controlled real motion episode for a P4
retest (approximate chat action window 03:00:06–03:00:21 UTC; exact message
receipt time is unavailable). At `03:00:23.713208665Z` the S3 accepted
`p15:c3-146393c5d158n8:gs114-c8s1q16`: first delivery changed the durable
state once (`records=16`, exact-key outbox found, admission OPEN); same-key
delivery at `03:00:23.845314170Z` left `state_changed=0`. The Durable ACK send
returned ESP_OK and the authenticated retirement ACK under Hub session 3
returned ESP_OK at `03:00:24.164475782Z`, with RPF00 admission OPEN. NodeHealth
at `03:05:23.259112457Z` (session 3 / health_seq 117) confirmed reset=11,
retained=0, durable_ack=16, `pir_ok=21`, `gpio_wakes=21`, `last_wake=TIMER`.
There was no additional EventKey during the three-minute post-DONE quiet
window. This is a PASS for the controlled P4 retest; the earlier q10–q12
multi-event FAIL remains preserved and its cause is unproven. No source/image
change, reset or reflash occurred.

Capture verification at 03:06 UTC found the original S3 reader (PID 283926)
still owning the S3 stable by-id port; no C3 port reader was present. No new
reader was opened. Installed hashes remain C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`, with
the diagnostic manifest's build source `72a223fc3b290c01c9f93fbb90db83d87601ad54`.

The offline P8 ACK-loss target pair remains unflashed: C3 app
SHA-256 `5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`,
S3 commissioning/ACK-drop app SHA-256
`f94192a7c59fa1a7221a7dc4a8394c1bd8c448c2009553e35dfed2f074eccd08`.
`make -C code c8-ack-drop-gate-host-test` passed 16 checks; the S3 fixture
profile suite passed 12/12; GS-130 traceability passed (175 features, 205
modules, 15 physical cases) and its 19 tests passed; physical catalogue
consistency passed for 99 cases with no device access. Previous ASan/UBSan and
TSan runs passed. A Hub validation attempt was intentionally interrupted before
the `host-build` stage could invoke Python: the ACK-drop gate passed 16 checks
and S3 fixture commissioning passed 12 checks; the Hub gate is INCOMPLETE, not
PASS (exit 130). P8 remains physically NOT_RUN; P9 remains blocked on its
independent ACK-hold and signed FOTA prerequisites. Jira GS-114 comment 10861
records the offline build/test milestone. GS-114 remains In Progress.

## Latest run03 checkpoint — 2026-10-14 02:04 UTC (campaign active)

The installed diagnostic firmware remains unchanged on the verified C3/S3 pair. The consolidated results now include actual P1/P2 PASS, P3 held-HIGH BLOCKED, P4 FAIL due three distinct qualified event keys during one requested motion episode, P5 BLOCKED/inconclusive because the S3 capture missed the first outage-recovery key, and P6 PASS for Hub-only reboot recovery. P6 established authenticated session 3 and healthy RPF00 admission without a C3 reset; the S3 boot banner was missed because capture attached after USB enumeration. Case records: [P1](run03_20261014/C8_P1.md), [P2](run03_20261014/C8_P2.md), [P3](run03_20261014/C8_P3.md), [P4](run03_20261014/C8_P4.md), [P5](run03_20261014/C8_P5.md), [P6](run03_20261014/C8_P6.md). The live single-reader S3 capture is `run03_20261014/s3_uart_timestamped.log`.

P7 requires one real PIR event under the post-reboot session. Authenticated NodeHealth at 01:58:46 UTC remained session 3 with no event/pending/reset changes and ten additional timer wakes. Per the operator's instruction, do not request motion until the operator sends **available**. The P8/P9 read-only fixture review found a narrow S3 ACK-drop test profile is feasible after P7, while the P9 ACK hold and signed FOTA image/trigger/recovery prerequisites remain unavailable. Do not reset/reflash/recommission; keep S3 capture running. GS-114 remains In Progress; P10 remains separate under GS-149. No firmware defect has yet been demonstrated by the P4/P5 event anomalies, so no source change or new image was made.

## Operator-requested pause handoff — 2026-10-13 16:56 UTC

## Operator-requested pause handoff — 2026-10-13 16:56 UTC

The owner requested a pause before the session limit. Physical measurement stopped at the logical checkpoint **after the repaired first-retirement RPF07 physical retest succeeded and before any run-02 PIR stimulus**. The run-02 capture process was closed with SIGINT; its C3/S3 serial readers exited and both ttyACM ports were unowned. The credential-bearing raw capture remains in ignored `code/build/gs114_clean_install/session-diagnostic-20261013T1653Z/`; [C3](diagnostic_run02_c3_redacted.log) and [S3](diagnostic_run02_s3_redacted.log) redacted copies are retained here, 108 and 122 lines respectively. No unexpected reset was logged during the run-02 measurement interval. The S3's `POWERON` and C3's `USB_UART_CHIP_RESET` occurred at initial setup capture opening before measurement. Capture stopped before the first five-minute authenticated NodeHealth report; do not infer P1 from that interrupted interval.

Installed on the **only authorized USB-powered R&D pair**: ESP32-C3 MAC `14:63:93:c5:d1:58`, 4 MiB, C3 app SHA-256 `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814`; ESP32-S3 MAC `7c:4f:ad:b7:2a:20`, 16 MiB/8 MiB PSRAM profile, S3 app SHA-256 `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. Both full clean installations and all image writes were verified. The exact nine-file [manifest](diagnostic_manifest.json), [S3 verify](diagnostic_run02_s3_verify.log), [C3 verify](diagnostic_run02_c3_verify.log) and first [C3 USB probe failure](diagnostic_run02_c3_probe_failure.log) are preserved. Fresh exact-identity test-only commissioning succeeded. The S3 reported `RPF00 path=PREPARED admission=OPEN report_generation=2` and authenticated retirement ACK send `ESP_OK` at 16:52:50 UTC. **RPF07 repair physical first-report retest PASS; C8 P1–P9 have no full PASS.** Run-01 real PIR evidence remains partial, not a substituted run-02 test.

The C3 built-in USB Serial/JTAG observer again stopped emitting after its first light-sleep entry; this is distinct from firmware liveness. The earlier C3 installer probe failure was a WSL USBIP attachment fault, resolved by operator C3-only reconnect and exact Windows `usbipd attach --wsl --busid 3-4`; no C3 erase occurred before fresh ROM identity verification. Do not blindly erase, reflash, reopen an occupied port or infer the USB bus ID will remain `3-4` on resume. The S3 commissioning image supports `FIXTURE_STATUS`, not broad `GET_STATE` or ACK-drop/FOTA controls. P8 still lacks a postcommit ACK-loss fixture; P9 FOTA still lacks a qualified signed pair/trigger/recovery plan. An independent 3.3 V UART/GPIO observer may be required if literal continuous C3 UART and held-HIGH traces remain mandatory. Prior migration FAIL and product P0 PARTIAL remain separate.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`, source/evidence checkpoint `b3217b977b6bf77070bc1a52c0c6706eb9cf7a29` matched actual GitHub remote HEAD before this pause update. Context preflight PASS `2026-10-13.001`. This report and `docs/product/R1_WORK_STATE.md` plus new run-02 verification/redacted evidence are the scoped handoff changes to commit and push. Nine pre-existing unrelated untracked entries, ignored build/raw logs and old failure reports are preserved; no reset/rebase/merge/stash/clean. Jira comments 10818 and 10819 record the physical milestones; a dated pause comment will follow the handoff commit.

**Exact resume action:** verify canonical Git/remote/status and context preflight; read this handoff, Jira GS-114 latest comment, the test plan and diagnostic manifest. Recheck the two stable by-id links, serial owners, C3/S3 power and AM312 3.3 V/GND/GPIO4 wiring before opening a port. Reuse the installed images and preserved commissioning state; do not start with another erase. Start one independent timestamped reader per port with a live stdin/control channel (`tty=true` or equivalent; the last capture lost stdin when launched after IDF shell activation), documenting setup resets separately. Verify authenticated rejoin, fresh `RPF00`/admission health and a five-minute NodeHealth baseline with timer wakes and zero false PIR events. Then ask the operator for real P2 motion and correlate GPIO-wake increment, exact EventKey, `HIL_AUTH_EVENT` outbox lookup/state change, Hub Durable ACK, and subsequent authenticated NodeHealth durable-ACK/retained counters. Continue P3–P9 only where their distinct physical fixtures and prerequisites are met. If Node UART remains silent, keep literal UART-dependent cases BLOCKED or obtain an approved equivalent observation decision; do not call incomplete counters PASS. Do not start GS-148 CloudSync while this explicit pause is in force.

## Repaired-image physical run 01 — 2026-10-13 16:17–16:32 UTC

The canonical local and remote HEAD matched `72a223fc3b290c01c9f93fbb90db83d87601ad54`; context preflight passed. Stable by-id ports had exchanged ttyACM numbers. Direct ROM probes verified the authorized C3 (`14:63:93:c5:d1:58`, 4 MiB) and S3 (`7c:4f:ad:b7:2a:20`, 16 MiB; 8 MiB PSRAM profile). The operator's USB-only supply and AM312 3.3 V/GND/GPIO4 arrangement remained the authorized setup. No other serial owner was present. The ignored installer guard was corrected to resolve stable by-id targets and reject occupied or non-ttyACM links; it no longer assumes fixed ttyACM numbering. All nine repair-manifest hashes and partition/profile bounds were rechecked before writing.

Using the already authorized disposable R&D scope, the S3 was erased, written and `verify-flash` checked at 16:17:42–16:18:59 UTC; the C3 followed at 16:19:00–16:19:08 UTC. Both installer runs exited zero. The installed C3 application SHA-256 was `89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`; S3 was `c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`. The S3 commissioning-only profile retained two 4 MiB OTA slots, `gs_outbox`, `gs_state`, and 16 MiB flash/8 MiB PSRAM. Installer transcripts and credential-bearing raw captures remain ignored under `code/build/gs114_clean_install/`; [C3 redacted log](repair_run01_c3_redacted.log) and [S3 redacted log](repair_run01_s3_redacted.log) are preserved here. Opening the capture caused setup resets before measurement; there was no observed reset afterward. Neither eFuses nor security settings were changed.

Both devices booted. The supported `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` flow freshly commissioned exact device `c3-146393c5d158` as logical `gs114-c8`; the Hub logged authenticated rejoin session 1 at 16:19:26.333 UTC. The Node logged PIR ready at 16:19:36, then `BAT_SLEEP_DECISION eligible=1` and `BAT_SLEEP_ENTER gpio4=1 timer=1`. The authenticated Hub NodeHealth at 16:24:25 reported 10 light-sleep entries and 10 timer wakes, zero GPIO wakes, no retained event. This proves the Node remained operational and could restore its radio to transmit authenticated health.

The operator performed one real AM312 motion episode for P2 and replied DONE. At 16:26:55.880 and 16:26:56.081 UTC, the Hub accepted the **same** exact EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1` twice, both `ack=0` (`AckClass::Durable`) with `ESP_OK` send. At 16:31:55, authenticated NodeHealth showed `gpio_wakes=1`, `sleep_entries=26`, `timer_wakes=25`, `retained=0`. This is positive physical GPIO wake, authenticated PIR transport and durable ACK evidence. It does not alone prove the exact C3 ACK retirement or one authoritative logical effect. No RPF error appeared, and the successful event confirms admission was open, but this image emits no `RPF00` success record, so the exact first-retirement-report reconciliation remains unproven directly.

The C3 native USB Serial/JTAG reader emitted no bytes after its first light-sleep entry, including after a queued `GET_STATE`, while authenticated radio health/events continued. ESP-IDF 6.0.3's USB Serial/JTAG documentation warns that light sleep can interrupt host enumeration. The continuous Node UART ordering and Hub counter snapshots required by the test plan therefore are unavailable. **P1/P2 remain BLOCKED on observer completeness, P3–P9 remain NOT_RUN/BLOCKED; no physical PASS is claimed.** Capture was closed at 16:32:21 without reopening either port. This is an observation failure; the live C3 did not show a runtime stall.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md`; `DECISION_IDS=GS-D020`; `TASK_SCOPE=GS-114 physical observer and RPF07 retest`; `OUT_OF_SCOPE=CloudSync, storage redesign, C9–C11`. A commissioning-profile-only read-only S3 diagnostic was added to log authenticated NodeHealth detail, successful `RPF00`, retirement ACK send result, and authoritative per-key outbox lookup. It changes no protocol, eFuse, durable admission or production profile. Retest requires source-matched target build/hash/verify and a justified fresh R&D installation. If post-sleep Node UART is still required literally, an independent GPIO/UART measurement interface is an external fixture prerequisite.

The paired diagnostic build subsequently passed with source fingerprint `1eec58fa1f77902c589e416db661b793d842320e33b1acc8073d677c460d1879`, ESP-IDF 6.0.3, C3 app SHA-256 `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3 app SHA-256 `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. All nine exact artifacts passed independent manifest hash checks; S3 remains commissioning ON, broad HIL OFF, two 4 MiB OTA slots, `gs_outbox`/`gs_state` and 16 MiB/8 MiB PSRAM. Focused Hub replay/checkpoint host regression, 19 traceability framework tests and `git diff --check` passed. This new pair has **not** yet been installed; the boards still carry the run-01 repair images at this checkpoint.

## Diagnostic physical run 02 — 2026-10-13 16:47 UTC onward

The source/evidence checkpoint was committed and pushed as `b3217b977b6bf77070bc1a52c0c6706eb9cf7a29`; exact GitHub remote HEAD matched, and tracked files were clean. Context preflight passed. The [diagnostic manifest](diagnostic_manifest.json) was rechecked against all nine artifact hashes and build receipt. Both stable by-id ports were unowned. The S3 re-probe matched ESP32-S3 MAC `7c:4f:ad:b7:2a:20`, 16 MiB and unchanged disabled Secure Boot/Flash Encryption. It was clean erased, written and [verified](diagnostic_run02_s3_verify.log) at 16:47:36–16:48:52 UTC. This verification left the board in the expected setup bootloader state until capture opened.

The first C3 read-only identity probe then failed at the USB serial RTS ioctl with `OSError: [Errno 62] Timer expired`; [the first failure](diagnostic_run02_c3_probe_failure.log) is preserved. The installer stopped **before C3 erase** and did not repeat S3 erase. WSL's by-id link still existed but the native-USB interface was unresponsive after light sleep/manual `screen`; WSL logged USBIP URB errors. On the operator's requested C3-only USB disconnect/reconnect, Windows `usbipd list` showed COM4, VID:PID `303a:1001`, bus `3-4` as `Shared` rather than attached to WSL. A targeted `usbipd attach --wsl --busid 3-4` restored only that identified C3 interface. A new ROM probe independently returned ESP32-C3 MAC `14:63:93:c5:d1:58`, 4 MiB. The guarded C3-only continuation rechecked exact identity, security and hashes, then erased, wrote and [verified](diagnostic_run02_c3_verify.log) at 16:52:09–16:52:17 UTC. The [continuation installer](execute_install_run02.py) required the five successful prior S3 verify digests and refused any other role sequence. This was a USB/WSL fixture transport failure, not a C3 firmware or flash error. No eFuse operation occurred.

Opening the two independent capture readers caused documented setup resets before measurements: C3 `USB_UART_CHIP_RESET`, S3 `POWERON`. Both diagnostic images booted. Fresh `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` succeeded; authenticated rejoin device `c3-146393c5d158`, logical `gs114-c8`, session 1 was logged at 16:52:39.929 UTC. **At 16:52:50.150 UTC the S3 logged `S3 replay fence healthy stage=RPF00 path=PREPARED admission=OPEN report_generation=2` for the first authenticated Node retirement report, followed at 16:52:50.151 by `Authenticated retirement ACK session=1 generation=2 send=ESP_OK`.** This is direct physical confirmation that the repaired first-report reconciliation no longer fails at RPF07. The C3 entered light sleep at 16:52:50.441; no P1–P9 PASS is inferred from commissioning or this first report alone. The full ongoing raw capture remains private under `code/build/gs114_clean_install/session-diagnostic-20261013T1653Z/`; redacted copies and later case dispositions will be added after observation.

## Resume checkpoint — 2026-10-13 UTC

GS-114 Jira comment 10800 and the pause handoff were reconciled against the
canonical branch. Local and remote HEAD remained
`93935e345a29e3b119f460fda5e9294477b6f798` at resume; all scoped dirty
source/evidence and pre-existing untracked data were preserved. Context
preflight PASS. The old S3 esptool process is gone and no serial reader owns a
port, but **neither authorized `/dev/ttyACM0` nor `/dev/ttyACM1` currently
exists in WSL**. No serial port was opened and no repair erase, write, reset,
recommissioning or P1–P4 stimulus was attempted on resume. Operator USB
reattachment and renewed power/wiring confirmation are pending.

All nine selected repair artifacts exist and their byte lengths and SHA-256
match [the corrected repair manifest](repair_manifest.json) and actual build
receipt. The manifest's previously copied S3 profile fields were updated to
the verified repair receipt: S3 app 1,889,280 bytes and embedded C3 SHA-256
`89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`.
The fixture remains the commissioning-enabled 16 MiB/8 MiB PSRAM profile with
`gs_outbox`/`gs_state`. `GS114_REPAIR_MANIFEST_CHECK=PASS`. This is offline
artifact evidence; installed boards still run the first failed image.

Focused `hub-runtime-checkpoint-host-test`, `hub-fresh-install-host-test`,
`feature-coverage-test` and the paired target build PASS. The completed
`make validation-hub` receipt at
`code/evidence/validation_framework/hub-1791904599768894359/report.json`
records 38/40 stages PASS, source unchanged, exit 2: known journal migration
failure (`clean migration commits`) and product P0 `PARTIAL`; checkpoint,
fresh-install, board-stack, storage correctness and sanitizers PASS. The
completed `make validation-contract` receipt at
`code/evidence/validation_framework/contract-1791905308298399721/report.json`
records 33/34 stages PASS, source unchanged, exit 2: only product P0 `PARTIAL`;
the contracts, board-stack, fresh-install and affected Hub cases PASS. Both
receipts use source fingerprint
`51484c36451d1502c75e4f4ba2a101b1144b416407bfbe6adbc79695e391f3bc`
and classify physical evidence NOT_RUN. These known broader gates are not
reported as PASS. The initial interrupted Hub invocation remains recorded
as interrupted in the pause checkpoint below; this completed rerun supersedes
its incomplete gate status.

## Pause/resume handoff — 2026-10-13 UTC

The operator requested a pause before the session limit. Physical execution is
stopped at the first-failure repair checkpoint: original clean images are still
on the C3/S3 boards; repaired images are built and hash-verified but **have not
been flashed**. Phase A is FAIL at fresh-install S3 `RPF07`; P1–P9 have no
physical PASS. No repeat erase or flash for the repair was attempted.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, pre-handoff local HEAD
`93935e345a29e3b119f460fda5e9294477b6f798`; remote matched at task
startup. Context preflight PASS `2026-10-13.001`. This report, the four scoped
Hub source/test files, and the validation traceability CSV were modified for
this checkpoint; new redacted logs, verification logs and repair manifest are
being committed. Nine pre-existing unrelated untracked entries and ignored
private raw logs/builds remain untouched. No reset/rebase/merge/stash/clean.

Repair target build: ESP-IDF 6.0.3, C3 app SHA-256
`89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`,
S3 app SHA-256
`c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`.
[Repair manifest](repair_manifest.json) records bootloader, partition, OTA,
outbox, image and build-receipt hashes. The S3 build uses its 16 MiB
commissioning profile with `gs_outbox`/`gs_state`, 4 MiB OTA slots and 8 MiB
PSRAM; C3 is 4 MiB. At-build source fingerprint
`ee9fe393cfed897ef392547dc92cc3b5bd85d9e8e7f78f124505d5a80ab2a249`;
the only later source-fingerprint input change was registering the new test in
`MASTER_TRACEABILITY.csv`, not a firmware source edit.

`make hub-runtime-checkpoint-host-test`, `make hub-fresh-install-host-test`,
`make feature-coverage-test`, target paired fixture build and `git diff --check`
PASS. `make validation-hub` was interrupted for this requested pause after the
known `hub-journal-migration-host-test` failure was reproduced; no full gate
PASS is claimed. Contract and physical repair retest NOT_RUN. The attempted
read-only S3 `flash-id` re-probe hung in uninterruptible kernel I/O before an
identity result; its parent and the validation gate were terminated. The C3
re-probe was not reached. S3 boot/serial state is therefore unknown at pause.

Resume at USB/process inspection, then independently reidentify both exact
authorized chips/ports and verify repair image/profile hashes before any
further erase/write. If safe, perform one controlled clean repair installation,
verify flash, recommission via `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE`,
capture independent timestamped logs, and physically retest admission/RPF00
and durable authenticated transaction. Start P1–P4 only after stable Phase A;
retain the test plan's separate P5–P9 operator actions and prerequisites.
Never infer a physical PASS from these software results.

2026-10-13 UTC. Current checkpoint: Phase A clean installation and authenticated commissioning were executed; first Hub replay-fence reconciliation **FAILED**, and admission closed. A targeted source repair passed focused host validation; rebuilt target images and physical retest are pending. P1–P9 are not qualified.

## Phase A first physical attempt, 11:58–12:05 UTC

The operator confirmed USB-only power, no competing supply, and AM312 VCC at 3.3 V/GND shared/OUT to C3 GPIO4. Stable USB interfaces matched COM4 (`/dev/ttyACM0`) and COM9 (`/dev/ttyACM1`). Direct ROM probes before the first erase identified C3 revision 0.4, MAC `14:63:93:c5:d1:58`, embedded 4 MiB XMC flash; S3 revision 0.2, MAC `7c:4f:ad:b7:2a:20`, 16 MiB flash and reported 8 MiB PSRAM. Both reported Secure Boot and flash encryption disabled. No eFuse operation occurred. Probe outputs are retained in private ignored storage.

The first, hash-checked manifest was installed only on those identified boards. Both complete flashes were erased, written and `esptool verify-flash`-verified, including S3's empty 4 MiB `gs_outbox` image. C3 app SHA-256 `ad173384e827614bcbb62c0deac60b5d866dd144088528523c5711e5c2409e43`; S3 app SHA-256 `8c53b999c001095030c7f150854b9637404b666364470131f1511cffdc34a4f7`. [C3 verification](install_c3_verify.log) and [S3 verification](install_s3_verify.log) are retained. Setup resets on opening the UARTs occurred before any qualification measurement; they are not claimed as stable observation.

Both images booted. The first host bridge sent LF-only S3 commands that produced no usable fixture response; a bounded `FIXTURE_STATUS` probe with CR framing returned `state=idle`. The bridge was corrected in private ignored test tooling to pace S3 UART bytes and terminate with CR. No reflash was used for this fixture-side correction. The corrected setup accepted `GET_TEST_QR` on C3 and `COMMISSION_EXPECTED_NODE` on S3, then the Hub logged exact authenticated rejoin of `c3-146393c5d158`, logical `gs114-c8`, session 2 at 12:04:37.803 UTC. S3 `FIXTURE_STATUS` returned `authenticated_rejoin`; C3 started its runtime and reported PIR ready on GPIO4. Credentials remain only in ignored private raw logs; the [C3](setup02_first_rpf07_c3_redacted.log) and [S3](setup02_first_rpf07_s3_redacted.log) evidence copies redact them.

At 12:04:48.028 UTC, before any qualified PIR event, the S3 logged `RPF07 SELECTED_CHECKPOINT_MISSING path=PREPARED admission=CLOSED report_ack=withheld`. Capture stopped immediately. The authenticated report had advanced the NVS selected checkpoint, while `HubDurabilityOwner::recovery_state()` still held the initial boot snapshot with no report reference. `HubRuntime::reconcile_replay_fence()` reloaded the new selection for publication but its binding check compared the old owner cache. This is a fresh-install runtime defect, not a residual from erased experimental state. No EventKey-to-Durable-ACK physical PASS exists.

`BUG_CLASSIFICATION=R1_BLOCKER`; `REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/product/CANONICAL_REQUIREMENTS_INDEX.md (durable-before-ACK and replay-fence invariants)`; `DECISION_IDS=GS-D020; GS-D030`; `TASK_SCOPE=GS-114 Phase A targeted durability repair`; `OUT_OF_SCOPE=storage redesign, CloudSync, C9-C11`.

The scoped repair refreshes the owner cache from the authenticated selected durable store during runtime fence reconciliation, checks the store/epoch binding, and closes admission if refresh fails. A new production-code host regression reproduces fresh genesis → first authenticated retirement report → selected checkpoint advance → fence bind, plus a failed-refresh negative case. `make hub-runtime-checkpoint-host-test` and `make hub-fresh-install-host-test` passed with `TMPDIR=code/build/gs114_tmp` after the default 1.9 GiB `/tmp` tmpfs proved full. This is software evidence only; the physical retest is pending.

Historical preparation source: `5ee96fd24b4a82b2a11b928cb40f2638eaee9616`, canonical `feature/r1-commercial-baseline`; actual GitHub HEAD matched at that preparation startup. Context preflight PASS `2026-10-13.001`.

This execution follows GS-114 10732, which supersedes old experimental-state preservation for the identified disposable R&D C3/S3 pair. Prior failure logs and STOP reports are preserved.

Verified current-source fingerprint: `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`; build receipt records `774da5c2ee8073c535df2fe56ecdbf548c16ebf0` with the Option A working-source implementation. Both current app hashes match that receipt. ESP-IDF 6.0.3 and esptool 5.4.0 activated. No source changes or repeat GS-148 fault campaign.

See [preparation manifest](preparation_manifest.json) for first-install bootloader/table/otadata/app/outbox hashes, offsets, profiles and exact command argument arrays, and [USB inventory](usb_inventory.txt). Artifact verification and compiled partition decode PASS. Fresh 4 MiB empty LittleFS generated with the component-pinned littlefs-python 0.15.0; host mount with target read/program/cache configuration and empty directory check PASS. A preliminary host validation invocation used an incorrect UserContext constructor and failed; corrected API invocation passed without changing the generated image.

Prior `USB_UART_CHIP_RESET` and replay-fence admission closure remain UNRESOLVED HISTORICAL REGRESSIONS. Clean installation cannot qualify recovery of that discarded old state.

## Execution scope

Owning Jira GS-114; affected C3/S3 fixture setup, USB capture, authenticated commissioning, Hub replay-fence runtime, GPIO4 light sleep, EventKey/ACK/durability contracts. Existing GS-150 and GS-148 software receipts are reused after exact source/artifact checks. The scoped Hub runtime owner-cache repair changes no protocol, security, persistent format or app/backend behavior. Physical tests require actual operator stimuli. Full release/current/GS-148 fault campaigns NOT_RUN; prior mandatory migration FAIL and product P0 PARTIAL remain.

## Case results

| Case | Disposition | Evidence / blocker |
|---|---|---|
| Phase A | PASS for RPF07 repair / fresh authenticated fixture; C3 USB observer limitation remains | Repaired image install/verification and fresh commissioning; first authenticated retirement report produced `RPF00 admission=OPEN` and ACK send; continued physical event admission confirmed |
| P1 | PASS | Ten timer sleep/wake cycles plus 25 more; authenticated post-wake health, no false PIR event or Node reset; see [P1](run03_20261014/C8_P1.md) |
| P2 | PASS | Real AM312 motion, exact q1 EventKey, GPIO wake, one durable effect, authenticated Durable ACK and retained=0/durable_ack increment; see [P2](run03_20261014/C8_P2.md) |
| P3 | PASS — controlled physical retest 2026-10-14 | One measured continuous AM312 GPIO4 HIGH interval of 28,518 ms; 1,425 additional HIGH sleep-inhibition decisions; zero sleep entries while HIGH; one qualified event q2 with one durable effect, same-key idempotence, authenticated Durable ACK and retirement; LOW recovery with 11 timer sleep/wake cycles and radio/owner restoration. See [controlled P3](run04_20261014/C8_P3_CONTROLLED_20261014.md). |
| P4 | PASS on controlled retest; original trial FAIL retained | Controlled brief motion produced q16, one Hub durable effect, same-key duplicate suppression, authenticated Durable ACK and Node retirement; no extra key in the three-minute quiet window. Earlier q10/q11/q12 remain distinct durable events with unexplained cause; see [P4](run03_20261014/C8_P4.md) |
| P5 | PASS — controlled reconnect-aware run 03; initial run02 remains inconclusive | One real AM312 event during Hub power-off arrived as q24 after authenticated session 6, changed durable state once, received Durable ACK, and was retired with reset unchanged; post-ACK retained=0, durable_ack +1. See [P5](run03_20261014/C8_P5.md). |
| P6 | PASS | Run 02 captured full Hub POWERON boot, authenticated session 4, RPF00 admission OPEN and Node reset counter unchanged at 11; see [P6](run03_20261014/C8_P6.md) |
| P7 | PASS — controlled run 02 | First event q22 during prompted AM312 action window; one durable effect, two same-key idempotent repeats, authenticated retirement ACK, post-event health confirms retained=0 and durable_ack increment; see [P7](run03_20261014/C8_P7.md) |
| P8 | PASS — physical q14 lost-ACK/retry | S3 one-shot ACK-drop was armed; exact PIR EventKey `p15:c3-146393c5d158n8:gs114-c8s16q14` committed once, first ACK withheld, same-key duplicate deliveries had no second effect, and authenticated Durable ACK/retirement followed. Stimulus timestamp is imprecise because the operator moved before the direct prompt; the prompt is not attributed as the cause. See [P8 physical evidence](run04_20261014/C8_P8_PHYSICAL_20261014.md). |
| P9 ACK | BLOCKED | No qualified directional ACK hold fixture; P8 one-shot loss alone is shorter than the required pending-ACK observation window; see [P9](run03_20261014/C8_P9.md) |
| P9 FOTA | BLOCKED | No matched signed C3 test/recovery image pair, supported signed trigger or known recovery procedure; see [P9](run03_20261014/C8_P9.md) |
| P10 | NOT_RUN | GS-149 owns quantitative acceptance; no instrument/current measurements |

Next action: preserve the commissioned S3/C3 state and pause hardware interaction after the later USB/IP transport loss. P8 is physically PASS on the captured q14 transaction; the later `12:14:59Z` arm has no event evidence and is not counted. P9 ACK/FOTA remain blocked on their specific fixtures; P10 remains GS-149. Do not move GS-114 to Done while applicable criteria remain incomplete or blocked.

## Validation and precise operator checkpoint

- `tools/context/ghar_sajag_context_preflight.sh`: PASS, exit 0, context `2026-10-13.001`, at startup and after documentation edits.
- Retained fixture app hash/size, exact embedded C3, current source fingerprint and S3 profile verification: PASS, exit 0. Both compiled partition tables decoded with IDF's `gen_esp32part.py`; OTA fit and outbox offsets checked. Build reuse only; target compilation was not repeated.
- `idf.py --version`: ESP-IDF v6.0.3, exit 0. Offline C3 `esptool image-info`: valid checksum/hash, C3/4 MB/DIO/80 MHz, ESP-IDF 6.0.3, exit 0. S3 independent image-info is retained in the matching build receipt.
- `littlefs-python create ... --fs-size=4194304 --block-size=4096 --name-max=64`: exit 0. Corrected host read-only image mount with target geometry: empty root directory, exit 0. S3 actual mount NOT_RUN.
- `make physical-hil-catalogue-test`: PASS, exit 0; 99 cases, 68 required and 40 conditional feature mappings checked, `device_access=NONE`.
- `python3 -m py_compile code/build/gs114_clean_install/prepare-20261013T111214Z/live_capture.py`: exit 0. This is an ignored session wrapper around existing `tools.hil.core.SerialCapture` and `FixtureLock`, not a new HIL framework or an executed capture. It requests DTR/RTS low before opening, keeps one reader per port, never automatically reopens a disconnected port, and stores credential-bearing raw commissioning output only under ignored private storage. Syntax check does not prove observation reliability.
- `git diff --check`: exit 0. The later scoped Hub firmware repair and its focused tests are recorded in the pause handoff above. Backend/PWA and release campaigns were not run. Prior GS-148 migration FAIL and product P0 PARTIAL remain independently recorded.

The owner subsequently supplied the exact board, power, wiring and Phase A erase/flash authorization. The first manifest's operations above were executed and verified. A repair retest must reidentify both exact chips/ports and verify new image hashes before another clean installation. Use only fresh private test credentials and `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE`, never the incompatible generic factory driver.

The S3 commissioning-only image accepts `FIXTURE_STATUS`, **not** `GET_STATE`, broad HIL, ACK-drop or FOTA controls. Canonical P1/P4 Hub-counter snapshots therefore require a verified compatible read-only observation path before complete acceptance; do not label unsupported commands or counter-only reasoning PASS. The current RPF diagnostic emits failure stages only; absence of RPF errors alone is not an observed `RPF00` success. Confirm healthy admission through authenticated durable transactions and capture the required fence proof before qualification. These instrumentation limits remain explicit; no acceptance criterion is waived.

## Subsequent measured work

GS-144 still needs owner acceptance of representative event/outage workload rates, selected battery/power-path usable capacity and reserve, minimum endurance and caregiver latency/reliability bounds. The 150–180 day goal remains aspirational; no measured battery-life claim. Its separate historical workload branch is a read-only provenance source and was not integrated or recreated.

GS-140/B0 requires a real identified instrument, range/burden/sample rate/uncertainty, voltage and measurement boundary. GS-41/42/141/43/44 own comparable B1–B4 BEFORE and GS-51 owns AFTER; current C3/S3 images are not interchangeable with the old `bb34f5e` baseline without a matched-profile decision. None was physically measured here. GS-149 P10 remains blocked by those inputs and GS-114 acceptance; GS-146 also needs GS-119, GS-46 and GS-69 accepted evidence. GS-115 decisions remain C9 REQUIRES_MEASUREMENT/product semantics, C10 MEASURE_ACTUAL_WRITES_FIRST, C11 POST_R1, C12 DEFERRED. No subsequent firmware implementation is approved by these statuses.
