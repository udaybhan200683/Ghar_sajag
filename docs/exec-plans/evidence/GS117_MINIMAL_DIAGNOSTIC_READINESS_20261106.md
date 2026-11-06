# GS-117 minimal diagnostic readiness — 2026-11-06

## Decision

Owner direction GS-117#11925 authorizes offline diagnostic preparation only.
Recommendation: CONDITIONAL GO for preserving the reviewed offline diagnostic
package; NO-GO for installing either image or performing another physical
observation. Session 134 remains the only consumed observation and its radio
root cause/watchdog relationship remain NOT_PROVEN.

The canonical worktree is /home/udaybhan/projects/Ghar_sajag_r1 on
feature/r1-commercial-baseline. Starting local and origin HEAD were both
a8f1753f5f86bb895ab23ede40c66b8e5b755b92. Repository context preflight passed.
The seven previously modified tracked implementation/test files were reviewed
and retained. The 79 previously preserved untracked paths were left untouched.
No firmware, hardware, serial port, authorization, network, router or Windows
configuration operation occurred. No source, test, requirement or product
implementation outside the existing offline diagnostic correction was added.

## Shortest remaining path to TC-001

| Stage | Existing behavior/evidence | Current gap and smallest next step | Owner / validation |
| --- | --- | --- | --- |
| C3 authenticated rejoin to S3 | Session 127 previously completed authenticated rejoin. Session 134 reached the C3 Hello send path on channels 3/4; delivered=0 did not identify the send stage. New TEST_ONLY C3/S3 evidence and result classification are implemented offline. | Candidate is not installed; session 134 had no confirmed C3/S3 channel overlap or S3 callback evidence. First obtain fresh authorized installed-image, bootloader, partition and selector receipts. Only then review a separately approved candidate install and bounded observation. | GS-117; focused radio/collector tests and target builds passed; physical status NOT_RUN. |
| Real optical PIR through C3 | Existing GPIO4 sensing and event admission remain in product source; historical physical events exist but do not count as TC-001. | After authenticated readiness, use actual AM312 optical motion and preserve sensor origin, Node identity, EventKey and Node time. No injected event can count. | GS-117; real fixture observation needs new exact hardware authority. |
| S3 durability and backend delivery | Existing durable Hub, ACK and CloudSync path; prior events 123/1 and 126/1 were physically delivered. Event 123/1's approximately 6h53m delay remains unresolved. P0 controlled API/DB scenario checks exist but are not physical evidence. | Correlate the same EventKey through Hub persistence/ACK, CloudSync and PostgreSQL; verify retry/replay creates one business event and preserves chronology. | GS-117, GS-148; existing focused backend/API regressions, then authorized physical evidence. |
| Caregiver API and Android app | Existing caregiver API and actual APK are available; prior limited observations are not fresh accepted TC-001 cases. | Observe the same committed physical event in the authenticated caregiver API and actual installed APK, with correct Home/room/type/severity/time and no duplicate. | GS-117; physical campaign authorization required. |
| Five accepted cases and recovery | TC-001 remains 0/5. | Complete five fresh real PIR cases and the original offline/online, reset/recovery, deduplication, latency and caregiver-visibility criteria. | GS-117 and applicable GS-116/130/173 gates; separate campaign authorization. |

No downstream stage warrants redesign before the earliest readiness blocker is
resolved. Existing product components are reused.

## Diagnostic implementation and result limits

The reviewed changes remain in the existing seven tracked files: the Windows
serial observer, bootstrap evidence redactor, S3 Hub runtime adapter/header,
and their registered Python/host-probe tests. The S3 receive path records
TEST_ONLY callback arrival, invalid input, source/channel/RSSI/frame metadata,
queue enqueue/drop/loss, and owner dequeue/processing with a local boot ID and
receive sequence. Callback work is bounded and nonblocking; reporting occurs
outside callback context. No keys, credentials or authentication payloads are
logged. No wire, authentication, retry, queue policy, durability or ACK decision
changed. Production builds do not contain the TEST_ONLY diagnostic markers.

ESP-NOW's callback provides no application transaction identifier. Same-peer
callback timing is therefore not presented as transaction proof. A missing S3
response remains unclassified unless captured target evidence establishes a
specific stage. Lack of confirmed same-channel C3/S3 opportunity is
INCONCLUSIVE, as are unavailable telemetry, uncorrelated cross-device clocks,
and an owner-processed frame with no outbound response. Positive callback,
queue, owner-processing and authenticated-response records can establish their
respective stages. They cannot prove that an unobserved RF frame was received.

The existing helper enforces one monotonic 90-second observation budget after
separately permitted bootstrap/reset. It has no extra post-observation drain.
Bootstrap and cleanup are timed separately; cleanup performs no further device
sampling. The 90-second budget is strict but cannot guarantee a channel overlap.

## Channel overlap and future observation scope

The existing India channel policy scans channels 1 through 13 and advances only
when it sends a rejoin Hello. Its retry schedule is 1.5, 3, 10, 20, 40, then
60 seconds, with at most 100 ms deterministic jitter per delay; once saturated,
Hello attempts are about one minute apart. Session 134 recorded channels 3 and
4 roughly a minute apart, while S3's channel was not preserved. A 90-second run
can be useful only if the recorded S3 owner channel coincides with an observed
C3 Hello channel. It cannot guarantee that condition and cannot turn a
no-overlap result into a radio failure.

For a future diagnostic only, a 900-second post-bootstrap observation would
allow at least one full 13-channel sequence at the existing saturated cadence,
with margin for initial backoff, jitter and capture. This does not guarantee RF
delivery, change channel selection or retry behavior, and is not authorized.
The current helper rejects requests above 90 seconds, so a 900-second run would
require a separately reviewed bounded-helper revision, exact new helper hash,
offline deadline tests, and a new exact owner-approved hardware scope. No reset
or channel override is proposed. The decisive observation must log S3's local
STA/owner-ready channel and C3's actual per-Hello channel, record positive S3
callback/queue/owner/security outcomes, and classify missing overlap or
uncorrelated absence as INCONCLUSIVE. Target uptimes from separate devices must
not be subtracted.

## Candidate artifacts and offline checks

Build-only artifacts are retained under
~/.local/state/ghar-sajag/gs117-minimal-diagnostic-readiness-20261106/.
Its manifest records hashes and profile. The matching build inputs remain in
the ignored code/build directories. No binary is installed.

Fixture remains Home gs177-test-product; C3 c3-146393c5d158, COM4,
USB 14:63:93:C5:D1:58; S3 hub-e072a1d38d34, COM10,
USB E0:72:A1:D3:8D:34. Last preserved installed-app receipts are C3
589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7 and S3
ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5; both are
STALE. Session 134 observed S3 boot version 8acab96-dirty with ELF prefix
7584a1f80. The historical S3 bootloader hash is
ae304441aaaad2b52765d48f4b37752f2ab26a65a480f5f1f9586cd54ebe1580, but no
trusted build provenance proves rollback support. No fresh device identity,
partition, selector, bootloader or image receipt was collected here.

| Target/profile | App version | BIN SHA-256 | ELF SHA-256 | Size / slot |
| --- | --- | --- | --- | --- |
| C3 TEST_ONLY diagnostic | 113d45d-gs117d-bf0ea8a3 | 8cca8460fe5fab1fed547026023cee7f6038b6c150ec522969be2336d1f24b38 | a11eef6637cdd592fb4dcf5c63db4f70e5b86cca7861826b18d995d06d0173cb | 966,832 / 1,966,080 bytes |
| S3 TEST_ONLY receive diagnostic | a8f1753-rxdiag-2 | a8f9d98b8fa355f6e02cc016c3dbd2429effd183faaa3612cd059d280b3d1f62 | bfd84228df491f20a6782c68c7e689a0df722b2bd82da5b599b4b8de32ca1e7d | 2,314,368 / 4,194,304 bytes |

Current S3 adapter source SHA-256 is
9648a7b7025185e2c674c3d2c4343f272ab14bf8770e23455f6ddbbb8c5b354d; its
header is 1a51460b4ce0606cc9b34ecabb694bea887fe0d5d658eeac572d63b9a77fbb19.
C3 target adapter source SHA-256 remains
68d5bc72d7ee1f2cd14ac3c1913677656118f1af44d649def37fe5f2ba169036. The S3
binary contains the exact C3 diagnostic BIN once. S3 TEST_ONLY markers are
present in the diagnostic image and absent from the production S3 image. The
diagnostic S3 build used ESP-IDF 6.0.3, 16 MiB flash and octal PSRAM settings,
GS40_TEST_ONLY_CLOUDSYNC=ON, GS_HIL_BUILD=OFF, GS_HIL_CONTROL=OFF,
GS_HIL_COMMISSIONING=ON, no ACK-fault/FOTA test flags, and the existing public
test root DER (SHA-256 53c5e81b87d1510c0d137d64a2e0b8989e250dcf981c33a34c5783db314e887a).
Current collector/helper SHA-256 is
44a2669593ff367fcb9d0a59d4c2d289070906fbb0270b9f1f3929c183f5b8dd; the
bootstrap evidence redactor SHA-256 is
21967680bde4f052d3c697ccac43ea334eff5e04fa82cb428b5f91c9257479f3. The old
90-second v18 procedure pin 7cd38e60b291e12ee51572b30f55a83fc8fb393ca188328c06f8e3541eff7ccb
is historical approval for its old helper/image identity and cannot authorize
these changed artifacts or any 900-second observation. A candidate-specific
procedure/hash does not yet exist.
The paired production S3 image hash is
2c374320ce5c3f51fdac61f79cda8d502fc419ac7b796faa402b96d749f8dd76; its
TEST_ONLY radio markers are absent. These are build/profile facts only.

The diagnostic S3 partition table generated by the build is 3,072 bytes
(SHA-256 bb0066feee7368e621c6f0f0d7bfdf47cbc5bbbf4cfdd9eccab9525ad683f82a).
Its OTA1 slot is 0x420000/0x400000 and the 2,314,368-byte app fits. The
candidate map is 4 MiB LittleFS gs_outbox at 0x820000 plus 256 KiB NVS gs_state
at 0xC20000. The last preserved physical S3 partition receipt, from the
2026-10-31 provenance observation, is 4,096 bytes with SHA-256
338f4a83ba90609b4ed0a04514f6378dc90b5d21769e186f49dc3086fd9feabc. The
generated candidate table is byte-identical to its first 3,072 bytes; the
receipt remainder is erased 0xFF fill. The decoded entries match exactly.
Thus the last-known partition map is compatible; there is no demonstrated
layout mismatch. That receipt is stale and does not establish today's target
state. No readback was performed for this review.

The build's sdkconfig requests ESP-IDF app rollback, but the installed
bootloader's provenance and automatic rollback behavior remain UNVERIFIED.
Historical manual app-only updates/restoration do not establish GS-D029
automatic rollback. The current installed S3's active image/selector,
bootloader, and fresh C3/S3 installed-image receipts remain unverified under the
24-hour rule. The old v18/helper hashes do not authorize these changed images.

### Minimum future hardware procedure, not authorized

1. First obtain a new exact-scope owner authorization for existing read-only
   C3/S3 identity and installed-image receipt capture, including S3 bootloader,
   partition table, both OTA selector copies and selected application, using
   the existing qualified receipt mechanism. Preserve #11886 and #11897; do
   not clear/reissue them or consume another hardware attempt without a lawful
   successor.
2. Compare the fresh partition entries with the pinned diagnostic table above;
   require the application to fit the selected slot. Stop on any mismatch and
   do not repartition. Verify current bootloader provenance supports the
   required automatic rollback; if it cannot be established, do not install.
3. Only after those read-only results pass, seek a separate exact owner-approved
   installation/observation scope for these BIN/ELF/source/helper hashes and
   the fixture. Use the existing audited install/recovery process; do not write
   a bootloader, partition table, credentials, OTA selector, storage data or
   event input unless a separately reviewed and approved plan requires it.
   Record pre/post receipts and verify restored/expected application identity
   and automatic rollback behavior. A manual recovery recipe is not a
   substitute for GS-D029.
4. If approved and all guards pass, perform one 900-second maximum observation
   after separate installation/bootstrap/reset phases, each explicitly
   bounded. Capture C3 local send stages and actual channels; S3 channel,
   callback/queue/dequeue/processing/security outcomes; TWDT records; and C3
   GET_STATE at the existing cadence. Stop at deadline or first identity,
   security, boot, receipt or recovery mismatch. Preserve cleanup evidence.
   This proposed 900-second scope is not an extension of #11897.

## Validation and remaining gates

New offline results: collector tests 25/25; radio/owner tests 4 tests with 194
host-mock assertions under ASan/UBSan; console/authorization tests 136/136;
USB awake-profile tests 4/4; Wi-Fi host tests 77 checks; rejoin host tests
PASS; GS40 bootstrap tests 91 checks; framework tests 55/55. Target compilation:
production C3 and S3 passed; the affected S3 TEST_ONLY diagnostic build passed;
the existing C3 diagnostic artifact was reused against the unchanged exact C3
source hash. ESP-IDF image-info validated chip/version/ELF identity and image
checksum; the partition table decoded and was compared with the historical
receipt. These checks do not establish installation, RF behavior, rollback or
physical acceptance.

The current make -C code validation-hub run is FAIL: 53/56 stages passed,
physical NOT_RUN, release not approved. Its three failures are retained:

| Failure | Classification / owner | Diagnostic impact | R1 release impact |
| --- | --- | --- | --- |
| s3-fixture-commissioning: 17/18 assertions; test rejects the presence of the GS_HIL_COMMISSIONING token even though the effective production build cache explicitly sets it OFF. | TEST_INFRA_ONLY; GS-116/GS-130 | Does not block this isolated TEST_ONLY diagnostic. The failing registered assertion still needs owning-gate disposition; it is not deleted or skipped here. | Registered aggregate gate remains FAIL until GS-116/130 resolves it. |
| Hub legacy journal clean-migration assertion. | DEFER_POST_R1 for unsupported legacy development-format migration under the fresh-install R1 contract; registered-gate disposition remains with GS-116/GS-173. | Does not block this isolated diagnostic. No storage migration or format change is undertaken. | Hub aggregate remains FAIL while the registered gate fails or lacks approved disposition. |
| P0 full product E2E: 26 scenario checks pass and subprocess exits zero, but product_status=PARTIAL and physical=NOT_RUN. | R1 product/release blocker; GS-148 with GS-117/GS-116/GS-130/GS-173 | Does not block an isolated TEST_ONLY diagnostic. | Blocks full R1 product/release acceptance. Production Hub authentication/enrollment binding and physical acceptance remain incomplete. |

The latest retained Node report remains 30/32 FAIL and the latest retained
Contract report remains 48/50 FAIL (source HEAD 113d45d, fingerprint
7e77cc8bf7edd96f910944685e06ddae952188c948300ba0c29dd7b26f51a183). They were
not rerun for this S3-only diagnostic change; wire/shared protocol contracts
were unchanged. The current Hub report is
code/evidence/validation_framework/hub-1793940517515065690/report.json and
records source_unchanged=true at starting HEAD a8f1753. All three aggregate
gate failures remain visible; no full release PASS is claimed.

## Product and authorization status

GS-117 remains Highest / In Progress. #11897 remains SAFETY_LATCHED, 1/1 used;
historical #11886 remains preserved. No successor was created or activated.
Installed firmware is unchanged; installed-image receipts are STALE;
TC001_READY=NO; real TC-001 acceptance=0/5. Session-134 root cause and
watchdog causality remain NOT_PROVEN. GS-179 networking remains completed and
separate.

One next action: prepare and obtain exact owner authorization for a read-only
fresh C3/S3 installed-image, bootloader, partition and OTA-selector receipt
capture through the existing mechanism. Proceed to artifact installation
review only if those current receipts and GS-D029 rollback provenance pass.
