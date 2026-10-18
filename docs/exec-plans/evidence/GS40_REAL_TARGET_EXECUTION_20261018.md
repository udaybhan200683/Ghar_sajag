# GS-40 real-target qualification execution — 2026-10-18

## Scope and disposition

This checkpoint resumes GS-40 against canonical `feature/r1-commercial-baseline`
at starting HEAD `65caf93df0011e6de29fb3d0e6310334b4e09036`. Context preflight
passed with `2026-10-13.001`; local and remote HEAD matched before work. The
only source change in this checkpoint is a focused caregiver-view regression
test and its existing GS-130 traceability row. No firmware, backend behavior,
security profile, or physical qualification status changed.

No board, USB/serial interface, C8 Hub, C3 Node, or spare-S3 diagnostic was
accessed. No flash, reset, motion, network outage, credential, eFuse, or
production service operation occurred. The prior spare-S3 GS-68 TEST_ONLY
authorization is not a GS-40 C3/S3 fixture authorization.

## Current source and image audit

| Layer | Current source / build evidence | Qualification limit |
|---|---|---|
| C3 heartbeat | `code/config/node_health.json` selects 300 seconds and event piggyback; the raw JSON SHA-256 is `2e42da92784c6eed807d8df240d1c33a178c1c088a568cbf9cb6d5d20817aadb`. Generated effective-config SHA-256 is `fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862`. The internal lease is `3 × interval + 10`, so the configured profile is 300/910. Backend profile assignments also retain trusted legacy 60/190 and 120/310. | These are source/package facts, not a current on-device config read. |
| Recent production-profile build candidates | ESP-IDF 6.0.3 candidates recorded by the 2026-10-17 paired build: C3 `b4e2b1c1d370fd2da2a30aae52cfbc2f85e91d0ff3b39da41eef23816829fedb` (937,536 bytes); S3 `e09e9651160719673958fffdc5c06f7a1787eb31403384324fd421b8f15a3ea1` (2,168,128 bytes). S3 sdkconfig SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. | Build candidates only. No current physical board's installed/running image is proven to match them. No new build was needed for this checkpoint. |
| S3 runtime | `hub_runtime_adapter.cpp` authenticates Node application contact, refreshes a bounded current-state snapshot, and schedules the separate bounded CloudSync NodeHealth worker. It maps configured 300/910 and trusted legacy 60/190 and 120/310 profiles; silent lease expiry is published without a new Node packet. EventKey, durable ACK, retry, and retirement remain on the event path. | Product `app_main` still constructs `UnprovisionedS3CloudTrust` and empty endpoint/trust settings. Commercial publication therefore fails closed. |
| Backend | Existing mTLS verifier, current Hub/Home/epoch and Node-enrollment checks, bounded latest-state model, replay/order fencing, lease expiry and separate Hub/backend receive timestamps are exercised by the local TEST_ONLY TLS tests. | This is an isolated local backend path, not a production deployment or a physical S3 connection. |
| Caregiver PWA | Existing home view maps fresh authenticated status to ONLINE or OFFLINE, coverage to COVERED only when ONLINE, and stale/unavailable sources to UNKNOWN. The empty-activity state explicitly does not imply nobody is present. | The direct end-to-end integration asserts the backend caregiver snapshot; JS tests separately assert the caregiver home view model. No live caregiver session was used. |

The GS-114 C8 record remains reusable only for its image-scoped claims. Its
recorded C3/S3 pair (`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` /
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`) showed
timer sleep/wake with authenticated Hub NodeHealth (C8-P1) and a genuine AM312
event with durable EventKey/ACK/retirement (C8-P2). The GS-114 attempt06 record
also contains one authenticated 300-second NodeHealth opportunity. Those
observations do not match the recent build candidates, do not prove six quiet
heartbeat opportunities, 910-second offline transition, mixed profiles,
backend/PWA status, or a current installation. No historical physical case was
repeated or reclassified.

## Minimum TEST_ONLY physical end-to-end prerequisites

Commercial approval for a pilot CA, production RSA-3072 DS/eFuse key custody,
Secure Boot/Flash Encryption, production registry lifecycle, and production D06
trust anchors is **not inherently required** for an isolated TEST_ONLY
NodeHealth demonstration. The physical TEST_ONLY path still needs all of the
following and none is silently supplied by the host tests:

1. A reviewed TEST_ONLY S3 runtime composition that uses the existing GS-168
   issuer/registry and existing `ProvisionedS3CloudTrust` / signed-time
   interfaces with isolated test material. The current product target selects
   `UnprovisionedS3CloudTrust`; the GS-68 diagnostic's signed-time command is a
   separate target and does not publish GS-40 NodeHealth. A test-only software
   credential/signing path may avoid DS/eFuse operations, but must be
   explicitly TEST_ONLY, isolated from production trust and endpoint
   configuration, and fail closed outside its test profile.
2. An isolated backend endpoint reachable only on the test network, with the
   TEST_ONLY CA/registry, signed-time authority and caregiver account/view. No
   production credentials, endpoint, or service is needed or appropriate.
3. An exact authorized C3/S3 fixture pair with current image/profile hashes,
   enrolled Node/session/profile and pending-EventKey baseline. GS-114/C8 is
   protected and was not authorized or accessed in this execution. The prior
   GS-68 spare S3 is not a substitute for the GS-40 enrolled Hub/Node pair.
4. A qualified timestamped observation and recovery method that does not lose
   Node identity, session, or retained EventKeys, plus fixture-specific
   authorization for the required observation, controlled silence, genuine
   sensor stimulus, and any install/reset operations required by the chosen
   plan.
5. PHY-GS40-05 additionally requires a second independently enrolled C3 with a
   trusted legacy profile, or a separately reviewed qualified profile fixture.

Therefore the next technical unblock is a TEST_ONLY-only product-runtime
composition and source-bound S3 test image, followed by owner-authorized
fixture selection and test-network setup. Production DS/eFuse decisions are a
separate commercial-activation gate, not a prerequisite for that isolated
software-profile design. No build/flash is claimed in this report.

## Validation executed

All commands ran in the canonical worktree; every test was software-only.

| Command | Result |
|---|---|
| `make -C code gs40-host-test` | PASS, 1,320 checks; includes quiet cadence, event-contact suppression, exact lease boundaries and recovery scenarios. |
| `make -C code gs40-config-test` | PASS, 17 tests; includes 300/910, mixed configured/legacy profiles, silent expiry/recovery, WAN loss/recovery and no-activity-versus-coverage semantics. |
| `make -C code gs40-qualification-test` | PASS, 17 tests across GS40-TC01..TC07 and observer/provenance guards. |
| `make -C code cloudsync-security-ut` | PASS: TLS adapter 9/9; trust-provider 5 suites; backend security 14/14; GS-68/GS-40 identity/time/caregiver local TLS integration 4/4; GS-168 issuer 10/10; backend NodeHealth model 5/5. |
| `make -C code app-test` | PASS, 25/25 JS tests, including new `GS40 caregiver NodeHealth preserves ONLINE/OFFLINE/UNKNOWN coverage semantics`. |
| `make -C code board-stack-e2e-host-test` | PASS, 10 cases / 398 checks; `physical=NOT_RUN`. |
| `make -C code cloudsync-security-sim-hil` | PASS, 18/18 cases including WAN recovery, retries, transfer/revocation and stale authority; `physical=NOT_RUN`. |
| `make -C code cloudsync-mtls-integration-test` | PASS, 1/1 real local TLS worker/API bridge; `physical=NOT_RUN`. |
| `make -C code feature-coverage-test physical-hil-catalogue-test` | PASS, 22/22 mapping tests; 208 features, 220 source modules, 24 physical cases; catalogue 108 cases; `device_access=NONE`. |

One initial traceability check rejected an assertion-anchor string that joined
two separate test titles; the anchor was corrected to the exact new test title
and the complete traceability and catalogue command passed on rerun. No
acceptance criteria or test expectations were weakened.

The focused tests pass. Prior aggregate results remain as documented: the P0
vertical status is `PARTIAL`; the Hub journal migration gate reports the
unchanged `clean migration commits` failure. Neither is changed or waived here.
No full release gate or target build was run; neither was needed for the JS
test-only change.

## Physical disposition

No PHY-GS40-01..06 case was run in this execution. They remain `NOT_RUN` /
`BLOCKED`; aggregate GS-40 physical acceptance remains NOT_RUN. C8-P1/P2 and
HIL-A03 are accepted historical GS-114 evidence only for the claims and image
pair above. TC05 still needs the second Node/profile fixture. Current installed
image/session, reset-safe observer, current Node enrollment, live backend
reachability and fixture authorization remain unverified for the GS-40 pair.

No GS-40/GS-68/GS-114 ticket was moved to Done. P0 remains PARTIAL and the
Hub-migration assertion remains FAIL. The C8 Hub, C3 Node, GS-177 process and
all pre-existing untracked evidence were left untouched.
