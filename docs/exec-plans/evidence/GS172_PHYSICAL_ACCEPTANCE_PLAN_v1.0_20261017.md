# GS-172 First S3 Security and GS-40 Physical Acceptance Plan — v1.0

**State:** PLAN ONLY / PHYSICAL NO-GO / NOT RUN
**Execution boundary:** No hardware, serial, USB, power, network stimulus,
credential issue, flash, reset, eFuse, Secure Boot, Flash Encryption, or test
operation is authorized by this plan. A new approval must identify the exact
fixture, image, test, interface, actions, expiry and recovery plan.

## 1. Scope and evidence separation

This plan joins the existing GS-68 physical cases `GS68-PHY-001..010` and the
existing GS-40 cases `PHY-GS40-01..06`. It does not add a HIL framework or
repeat GS-114 BAT-C8 work. Use existing GS-68 runner/catalogue and GS-130
physical catalogue. A host TEST_ONLY result, compiled DS path, normalized
observation bundle, or synthetic evidence never creates a physical PASS.

Keep two evidence classes separate:

- **Wave T — TEST_ONLY hardware qualification:** disposable non-customer S3,
  isolated TEST_ONLY issuer/time/backend and no production credentials. This
  can demonstrate that the selected device/image performs DS signing and the
  source-to-caregiver path under a test trust domain. It does not prove
  production issuer custody or commercial readiness.
- **Wave P — production security qualification:** only after decisions P2–P8
  are approved, production target providers and signed recovery are implemented,
  and a separately authorized sacrificial device is available. Production
  credentials, endpoint, DS/eFuse, Secure Boot/Flash Encryption, and service
  activation are all outside current authorization.

No key, certificate, signer, time authority, registry state, or evidence may
cross from Wave T to Wave P. Each wave gets distinct trust roots, endpoints,
registry namespace and evidence manifest.

## 2. Pre-entry gates

Before any first physical interface action:

1. Complete and approve the [decision matrix](GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md)
   rows applicable to the requested stage. `DEFERRED` is a blocker.
2. Complete the [fixture readiness checklist](GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md)
   for the exact board(s), cable, adapter, power path, image/config/session,
   observer, evidence path and recovery owner. Explicitly exclude C8 assets.
3. Obtain signed fixture-owner and user authorization listing board/Node IDs,
   planned case IDs and order, actions (observe/connect/power/flash/credential/
   fuse/network/motion separately), interface, expected image digest, plan
   digest, evidence directory, expiry and stop/recovery procedure. Security
   signs any key/certificate/eFuse/security configuration action.
4. Confirm the TEST_ONLY root/certificate/time authority/backend are isolated
   and production CA/roots/endpoints are untrusted and unreachable from the
   test configuration.
5. Build/inspect the source-matched test image and provisioner software-only.
   Record commit, IDF 6.0.3/tool versions, build profile, sdkconfig, partition
   layout, binary SHA-256, signed-image verification and SBOM/config hashes.
   Do not install it without separate exact approval.
6. Close the known software gaps: production application currently remains
   `UnprovisionedS3CloudTrust`; the target does not instantiate the signer,
   registry/ownership source, or D06 runtime provider. A physical DS/mTLS/time
   PASS requires a target-capable implementation and source-bound test build,
   not only the host provider tests. Commercial Wave P also requires the
   signed OTA/recovery and anti-rollback path (GS-118/D15).

## 3. GS-68 case sequence and acceptance evidence

Use the existing case definitions in
`GS68_CLOUDSYNC_PHYSICAL_HIL_AUTOMATION_20261016.md`; case IDs and catalogue
expectations remain authoritative.

| Case | Purpose and minimum correlated evidence | PASS requirement | Present state |
|---|---|---|---|
| GS68-PHY-001 | S3 RSA-3072 DS signs a fresh challenge; backend validates exact enrolled leaf/fingerprint. Capture image/fixture/key-purpose identifiers, public key/cert fingerprint and signature verification result. | Signature verifies under the enrolled public key; no private material emitted; actual DS peripheral is used, not software signer. | **BLOCKED — no target signer/key/fixture** |
| GS68-PHY-002 | TLS 1.2 mutual-auth handshake to isolated TEST_ONLY backend; verify server hostname/chain and client-auth chain. | Both peers validate configured trust; unauthorized roots and missing time fail closed. | **BLOCKED — physical trust setup absent** |
| GS68-PHY-003 | Validity and trust-root checks for current, not-yet-valid, expired, malformed and wrong-purpose certs. | Only exact allowed TEST_ONLY certificate and active registry mapping succeeds. | **BLOCKED** |
| GS68-PHY-004 | Revoke/quarantine certificate and retry; also exercise expired/unknown issuer. | Next backend request is denied; NodeHealth is not refreshed and caregiver coverage becomes stale/UNKNOWN on policy boundary. | **BLOCKED** |
| GS68-PHY-005 | Wrong permanent Hub ID, Home, ownership epoch, Node source/session or stale epoch. | Request rejected before latest-state mutation; after transfer only new epoch is accepted. | **BLOCKED** |
| GS68-PHY-006 | WAN/backend outage, bounded retry and recovery. | No false healthy cloud status; retry is bounded; status resumes only after time and authority revalidation. Durable event priority/ACK semantics unchanged. | **BLOCKED** |
| GS68-PHY-007 | Reboot/rejoin with retained EventKey and new boot/session generation. | No replay or duplicate logical effect; accepted retry retains exact EventKey. | **BLOCKED; preserve existing C8 claims without rerun** |
| GS68-PHY-008 | Durable event completion and ACK behavior under lost ACK/retry. | Exactly-once logical effect, durable-before-ACK and event retirement invariant preserved. | **BLOCKED; existing software/ C8 evidence scoped only to proven claims** |
| GS68-PHY-009 | Bounded publication/retry latency and resource observations. | Meet separately approved D16 limits; no event starvation or unbounded queue/memory. | **BLOCKED — bounds not approved** |
| GS68-PHY-010 | Signed image install/update, failed-health rollback and recovery. | Valid signed image accepted; invalid/old image rejected per approved anti-rollback; failed candidate recovers without data loss. | **BLOCKED — GS-118/D15 and OTA/recovery absent** |

### D06/ownership submatrix required before GS68-PHY-002/003

Use the existing signed-time proof state machine and add hardware-correlated
evidence only after the target provider exists:

1. Cold boot with no proof and no Internet: CloudSync stays unavailable; local
   Hub safety remains active. This is a correct fail-closed observation, not a
   test failure.
2. Fresh valid signed nonce/boot-generation proof restores time and CloudSync
   only after floor commit and current Home/epoch/credential revalidation.
3. Reject bad signature, altered nonce, replay, wrong boot generation,
   not-yet-valid, expired, excessive validity, corrupted/missing floor, and
   rollback according to approved numeric policy.
4. In a running boot, correlate trusted UTC to monotonic elapsed time through
   WAN loss/restoration; Hub contact, backend receive, and caregiver snapshot
   timestamps remain distinct.
5. On reboot during outage, require a new proof; never trust NVS alone. If a
   later approved policy requires offline cold-boot trust, use a qualified
   protected counter/store; the NVS adapter is insufficient.
6. Transfer/revoke ownership while proof recovery is in progress; old epoch
   and revoked credential remain denied even if time proof is valid.
7. For each test attach proof digest, nonce hash (not secrets), boot generation,
   authority/anchor version, trust floor outcome, monotonic observations,
   backend decision, Home/epoch, and image/config hash.

## 4. GS-40 PHY-01..06 execution order

Use `GS40_REAL_TARGET_READINESS_20261016.md` and its current correlated evidence
schema. Keep existing R1 timing profiles: configured 300/910, legacy 60/190,
legacy 120/310. Preserve Hub authenticated Node contact, Node session and
enrollment generation. EventKey, durable ACK, retry, replay and retirement
semantics remain unchanged.

| Case | Physical scenario | PASS evidence / guard | Current blocker |
|---|---|---|---|
| PHY-GS40-01 | Six quiet configured 300-second health opportunities; authenticate each Hub receipt. | Six unique authenticated contacts; expected liveness; exact S3/C3 images/config/session; matching backend/PWA status. | No matched fixture/current image/session or authorization. |
| PHY-GS40-02 | At a due opportunity, authenticated event contact suppresses redundant standalone health. | Real approved stimulus, Hub application acceptance, EventKey, durable ACK and scheduler evidence correlate; MAC send success alone is insufficient. Reuse C8 event subclaims only. | Stimulus and fixture approval absent. |
| PHY-GS40-03 | Silent Node lease expiry with Hub/WAN controls and no new Node packet. | Observe before, at and strictly after configured lease boundary; Node becomes OFFLINE while Hub/backend are fresh; EventKey baseline captured if preservation is claimed. | NVS-preserving silence method and fixture approval absent. |
| PHY-GS40-04 | Same Node recovery by authenticated rejoin. | Fresh session/contact restores ONLINE; compare pending EventKeys/chronology; no reset/storage clear or forced motion. | Current enrollment/session and approved recovery observer absent. |
| PHY-GS40-05 | Configured and legacy profile timing. | Exercise 300/910, 60/190, 120/310 and unknown/untrusted profile; at least two enrolled Nodes or explicitly approved qualified profile fixture (three if all concurrent). | Second Node/profile fixture unavailable. |
| PHY-GS40-06 | Caregiver projection during Hub loss and Internet/backend staleness, then recovery. | Distinguish Node OFFLINE from source UNKNOWN; stale source cannot show healthy coverage; correlate API and actual PWA snapshot, identity, epoch and timestamps. | Isolated qualified API/PWA account and network plan absent. |

For PHY-GS40-03 use strict `age > configured offline timeout` behavior; at the
inclusive lease boundary, do not claim OFFLINE. Maintain source freshness
independently from Node liveness. `UNKNOWN` coverage does not imply resident
inactivity.

## 5. PASS / FAIL / BLOCKED rules

**GO for a case** only if all applicable approvals and pre-entry gates are
complete; the exact fixture/image/trust environment is verified; all required
observers are reset-safe; an isolated backend and recovery owner are ready; and
the evidence path is writable before the run. A plan or dry-run is not GO.

**PASS** requires all case assertions plus matching fixture, source/image,
configuration, credential/authority, Home/epoch, Node/session, backend receipt
and caregiver timestamps, with raw evidence hashes and independent review. A
negative case passes only when unauthorized data is not accepted and no
caregiver-visible healthy state is created.

**FAIL** means an assertion or security invariant failed. Preserve the run,
quarantine the fixture, stop subsequent cases, revoke compromised test
credentials and obtain review. Do not reflash/reset or rerun to erase evidence.

**BLOCKED / NOT_RUN** means a prerequisite, approval, expected image, source,
proof, observer, fixture, or evidence item was missing. Never relabel a blocked
test as pass due to host simulation or absence of an error.

## 6. Reuse and excluded work

- Reuse existing BAT-C8 evidence only for its exact image-scoped sleep/wake,
  ESP-NOW, authenticated EventKey/ACK claims. Do not rerun those cases merely
  to recreate evidence.
- Reuse GS-68 host/provider, TLS, backend registry and NodeHealth/PWA tests as
  software evidence. They do not prove real DS hardware, production key custody,
  eFuse state, running image, electrical behavior or physical caregiver path.
- Keep the known Hub journal migration failure and required P0
  `product_status=PARTIAL` visible. No gate expectation changes are part of
  this plan.
- Do not run `--observe`, `--run`, board HIL, serial or flash commands under
  this documentation task. The runner's typed phrase is not user approval.

Related: [SOP](GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md),
[decision matrix](GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md),
[fixture checklist](GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md),
[GS-68 S3 plan](GS68_S3_FIRST_PHYSICAL_QUALIFICATION_PLAN_20261016.md),
[GS-68 test catalogue](GS68_CLOUDSYNC_PHYSICAL_HIL_AUTOMATION_20261016.md),
[GS-40 readiness](GS40_REAL_TARGET_READINESS_20261016.md).
