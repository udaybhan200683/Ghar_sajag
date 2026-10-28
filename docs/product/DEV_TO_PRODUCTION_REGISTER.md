# Development-to-production register

**Owner:** GS-173. **Gate enforcement:** GS-116. **Coverage:** GS-130.
The item-level source of truth is [`DEV_TO_PRODUCTION_REGISTER.json`](DEV_TO_PRODUCTION_REGISTER.json);
stable DTP IDs below are identical in both files. Each implementation status uses the owner-requested `IMPLEMENTED_DISABLED`,
`PARTIAL`, `MISSING`, or `BLOCKED` vocabulary. The register tracks current
implementation, effective DEV use, and production readiness separately. It is
not a new feature-configuration service and does not authorize production
activation or hardware operations. It implements the release-stage reference
in [R1_RELEASE_CONTRACT.md](R1_RELEASE_CONTRACT.md) and reuses the existing
GS-116 `release-gate-final` registry and GS-130 traceability/physical catalogues.

**Latest verified controller/register source:** `d6a37dc113ead8fe5559a990dcce2974d271e182`.
DTP-010 is qualified narrowly for production profile isolation based on a
clean paired C3/S3 target build from `732b848df157859cffaf813332d8ab1e0058ad7a`;
this does not qualify production identity, signing, or release. Current
TEST_ONLY configuration is isolated to the existing GS-40/GS-179 profile and
Home `gs177-test-product`. Production identity issuance, routes, deployment and
irreversible hardware security remain inactive. A compile-time option or
source default is not evidence of the effective built or deployed value.

## Gate inventory

| Gate | Area | Implementation | Scope | DEV effective state | Production readiness | RC blocking |
|---|---|---|---|---|---|---|
| DTP-001 | Hub identity and client-auth trust | PARTIAL | MANDATORY_R1 | Isolated TEST_ONLY profile; fresh physical receipt unverified | BLOCKED | Yes |
| DTP-002 | Hub ingress, ownership and durable receipt | PARTIAL | MANDATORY_R1 | Local TEST_ONLY service; physical S3 receipt unverified | BLOCKED | Yes |
| DTP-003 | Caregiver identity and Settings authority | PARTIAL | MANDATORY_R1 | TEST_ONLY session and Settings only | BLOCKED | Yes |
| DTP-004 | Desired/applied policy delivery | PARTIAL | MANDATORY_R1 | Software integration only; no physical S3 apply evidence | BLOCKED | Yes |
| DTP-005 | Signed firmware and device root of trust | PARTIAL | MANDATORY_R1 | TEST_ONLY profile; commercial qualification absent | BLOCKED | Yes |
| DTP-006 | Hosting, PostgreSQL operations and recovery | PARTIAL | MANDATORY_R1 | Local development service/profile | NOT_VERIFIED | Yes |
| DTP-007 | Notifications, calls and WAN delivery | BLOCKED | SCOPE_PENDING | Caregiver projection only; external delivery unverified | NOT_VERIFIED | Yes |
| DTP-008 | Physical C3/S3 fixture and sensor qualification | BLOCKED | MANDATORY_R1 | BLOCKED by fixture/image/authentication guards | BLOCKED | Yes |
| DTP-009 | Installed Android business outcome | PARTIAL | MANDATORY_R1 | Historical HOST_SIM-to-APK; exact Hub-decision observer host-mocked, physical outcome unverified | NOT_VERIFIED | Yes |
| DTP-010 | TEST_ONLY build isolation | IMPLEMENTED_DISABLED | MANDATORY_R1 | Production target cache/root guard PASS; TEST_ONLY profile remains opt-in and isolated | QUALIFIED (profile isolation only) | Yes |

The clean paired target report is
`code/build/validation_targets/gs116-ktfj60_m/report.json`; it records C3
944,272 bytes (`6d65ce18…`) and S3 2,201,168 bytes (`9544d3af…`) with the
TEST_ONLY/HIL profile disabled and no TEST_ONLY root. The isolated S3
TEST_ONLY profile also compiled with an external public root; no image was
installed. These are build/profile checks only. The JSON record gives exact
source paths/configuration, current state, TEST_ONLY data boundary, production replacement/activation, dependencies, security and
rollback implications, tests, acceptance, evidence, reviewer, approval and
last verified source commit for each gate. No entry claims physical, production
or release PASS from a host test or design decision.

## RC reactivation checklist

Run this at a frozen release candidate; do not run it as a substitute for
development feature validation.

1. **Resolve scope and owners (GS-173).** Adjudicate any `SCOPE_PENDING` rows
   against locked product requirements. An unapproved deferral is NO-GO.
2. **Complete production trust (GS-68/109/148/165–172).** Approve issuer and
   key custody/lifecycle; qualify per-Hub identity, trusted time, secure boot,
   signing and recovery. Credential issuance and irreversible hardware work
   require their separate approvals.
3. **Activate authenticated services (GS-76/109/148/177/179).** Deploy the
   approved caregiver session and Hub middleware, authoritative Home/Hub/epoch
   registry, TLS endpoints, durable PostgreSQL and verified backup/restore.
   TEST_ONLY identities/routes/roots must terminate outside the production
   profile.
4. **Qualify policy application (GS-148/179).** Authorized Settings writes a
   versioned desired policy; the actual S3 fetches it under current authority,
   validates the full policy, durably checkpoints it before ACK, and reports the
   exact applied version after supported restart/outage.
5. **Prove target and caregiver outcomes (GS-117/114/130/177).** Verify current
   image/fixture, authenticated physical Node-to-Hub admission, durable ACK,
   CloudSync, unique backend record and the same real decision in the installed
   Android APK. Qualify optical PIR separately from USB input.
6. **Prove the effective release build (GS-116).** Run the paired C3/S3 builder
   from clean ignored outputs. Confirm `GS40_TEST_ONLY_CLOUDSYNC`,
   `GS_HIL_BUILD`, `GS_HIL_CONTROL`, `GS_HIL_COMMISSIONING` are OFF and the
   external TEST_ONLY root is absent. Run the focused register/trace and source
   consistency check plus `make release-gate-final` for the frozen RC.
7. **Release decision (GS-173 G1/G6/G7).** Every mandatory row must be current,
   evidenced, `gate_status=PASS`, `prod_readiness=QUALIFIED`, owner/security
   approved and consistent with the actual source/build/deployment. Otherwise
   record NO-GO; never convert `NOT_RUN`, `BLOCKED`, `PARTIAL` or stale evidence
   into PASS.

Current dev work may reuse the existing TEST_ONLY stack without waiting for
commercial issuer/hosting activation, but physical USB/HIL use remains subject
to its independent fixture and operation approvals. See GS-117/179 for current
Morning Routine readiness and GS-173 for release adjudication.
