# GS-172 First-Device Security Decision and Approval Matrix — v1.0

**State:** Proposed; no production security decision is approved by this document.
**Purpose:** Route only the remaining small-pilot decisions for the first 50–100 Hubs.
**Product authority:** GS-D032 / GS-HUB-02 permanent identity and epoch-fenced Home authority; GS-109; GS-68 D05/D12/D06; GS-118/D15 firmware security. GS-165–GS-171 define related pilot scope and factory contracts; this package reuses existing source seams and does not imply that every planned station component is implemented.
**Pilot scale:** One non-customer S3 qualification fixture, one operator, one isolated station; no enterprise PKI or factory orchestration platform.

## Approval matrix

| ID / decision | Proposed choice and alternatives | Threat addressed / operational cost | Required approver | Reversibility | Evidence required before GO | Status |
|---|---|---|---|---|---|---|
| P0 — qualification boundary | Approve a disposable, non-customer S3 and isolated TEST_ONLY issuer/time/backend as the first physical qualification environment. Production issuer, Home data and commercial endpoints remain excluded. Alternative: defer physical work until production provisioning exists. | Prevents test credentials or household authority crossing into production; costs a separate test fixture/environment. | Product owner + Security + fixture owner | Reversible before any fuse/credential operation | Fixture ID, isolated endpoint/root inventory, expiry-scoped test plan, no-production-network check | **Ready for owner approval** as a scope recommendation; does not authorize physical work. |
| P1 — permanent Hub identity and registry model | Approve unique immutable Hub ID; RSA-3072 ClientAuth leaf fingerprint maps through the authoritative registry to Hub ID, enrollment/source association, current Home/epoch, credential generation and active/revoked/quarantined status. Home binding comes only from GS-109 authorized ownership operation. | Blocks spoofed identity, stale/transfer authority, cross-Home leakage. Requires an authoritative registry transaction and audit trail. | Product owner + GS-109 owner + Backend owner | Registry policy reversible; identities/fingerprints are append-only lifecycle records | Contract mapping, atomic transfer/revocation/replacement tests, issuer/backend negative tests | **Ready for owner approval**; production registry implementation/approval remains open. |
| P2 — issuer and root custody | Prefer an existing approved private CA/KMS/HSM service. Keep root under current offline/root custody; use one constrained issuing key. If no such service exists, security may approve one small HSM-backed issuing intermediate under an offline root. Do not create a new PKI or store signing keys on the station filesystem. | Protects CA compromise and unauthorized issuance. HSM/KMS account, backups, access control and incident procedures add operational work. | Security authority + issuer/platform owner | Trust roots and issued leafs are revocable, but key exposure/issuance is not reversible | Named service/custodian, key type and permissions, backup/recovery, audit retention, trust bundle and CA compromise drill | **Security review required.** Vendor/service and custody not selected. |
| P3 — device TLS key / DS path | Preferred candidate: generate RSA-3072 key on a Secure-Boot-verified S3 provisioning image, issue CSR, encrypt parameters for DS using a unique HMAC eFuse key, zeroize plaintext, prove possession. Alternative: isolated station key generation only with explicit exposure controls and security acceptance. | Limits private-key export. DS does not generate RSA keys; the key-generation/loading window, RAM and debug/rework are in scope. Adds provisioning firmware and review. | Security + Hardware/firmware + factory owner | DS HMAC/eFuse programming and locked debug are irreversible; certificate is revocable, device private key generally is not | Source-pinned S3 flow, actual DS sign verification, eFuse purpose/state, zeroization, debug/rework analysis, per-unit certificate challenge | **Security review required.** Production signer and key custody are not implemented. |
| P4 — Secure Boot, Flash Encryption, anti-rollback and recovery | Candidate: signed bootloader/application; unique per-device FE key in Release mode; follow pinned IDF external-provisioning order (FE protection before SBv2 irreversible digest/protection in that flow); set anti-rollback only with proven signed update/recovery; close ROM/debug paths last. Alternative: keep non-customer unit development-only and do not claim production qualification. | Stops unsigned/old firmware and flash extraction. Irreversible fuses can strand a unit; current S3 OTA/recovery path is absent. | Security + firmware release owner + hardware/factory | eFuse settings are irreversible | Exact board/fuse map, source/build/signed-image hashes, verified update and rollback/recovery on disposable device, approved fuse order and stop/recovery plan | **Security review required; production NO-GO.** GS-118/D15 recovery path is not qualified. |
| P5 — authenticated-time signer and trust anchor | Candidate: reuse GSTP v1 signed proof, separate RSA-3072/SHA-256 authority key, independent pinned trust anchor, nonce/boot-generation binding; obtain a fresh proof on every cold boot before CloudSync. Alternatives: reviewed authenticated-time protocol or secure time module. No unauthenticated SNTP as authority. | Prevents wrong certificate-validity decisions, stale/replayed time, and bootstrap circularity. Requires a small signer service and pinned-key lifecycle. | Security + backend/time-service owner + firmware owner | Proof key and anchor can rotate only through an approved authenticated update/overlap mechanism | Endpoint/audience, signer custody, protocol version, anchor/rotation, nonce source, freshness/validity/error limits, outage behavior and negative tests | **Security review required.** The shared verifier path is implemented and tested with TEST_ONLY keys; production authority/anchor and thresholds remain open. |
| P6 — rollback floor and boot generation | Candidate for pilot: always require a new signed proof on cold boot; use monotonic elapsed time during a boot; use NVS floor for diagnostics/rejection only. If offline cold-boot trusted time is a requirement, select a protected monotonic counter/secure element and qualify it. Alternatives: deny cloud after offline cold boot (current safest option). | NVS can roll back with restored flash; old valid firmware may bypass policy absent anti-rollback. Protected counter adds hardware/provisioning complexity. | Security + product owner | NVS policy reversible; eFuse/secure-counter choice may not be | Threat model for flash restoration, old-image attempt, outage/reboot matrix; approved maximum outage, interval and wear bounds | **Security review required.** Production rollback guarantee not established. |
| P7 — time and credential numeric policy | Set maximum proof age, signed validity interval, tolerated monotonic/UTC error, certificate validity/renewal overlap, retry/backoff and offline maximum. Keep unspecified values fail closed. | Avoids stale trust and DoS from overly strict policy; numeric choices affect battery/network and availability. | Security + product/SRE owner | Policy tunable before deployment; issued certificate validity is fixed | Threat rationale, support horizon, outage/recovery tests, renewal/revocation scenarios | **Security review required.** No values are selected here. |
| P8 — ownership and certificate lifecycle | Registry transaction atomically tracks Hub, cert fingerprint/generation/status, active Home+epoch and Node enrollment/source association; revalidate each request; revoke old state on transfer/replacement/quarantine. Define renewal, expiry, overlap and emergency revocation response. | Prevents stale or transferred authority and revoked devices publishing healthy status. Requires a single system of record and operational SLA. | GS-109/Product + Backend + Security/operations | Registry and cert state reversible through audited updates; already disclosed keys not reversible | Concurrency/transfer/revocation tests, outage behavior, operator roles, audit/reconciliation and replacement drill | **Design ready for owner approval; lifecycle service and security review remain.** |
| P9 — first-device physical authorization | For each session, approve named S3/C3 IDs, observed board revision, operation class, cases, image/plan hashes, interface, evidence path, start/expiry, operator, recovery. Handle connect/read, flash, credential, fuse, stimulus and network separately. | Prevents scope creep into protected hardware and preserves evidence. Costs explicit review per fixture/stage. | Fixture owner + authorized user; Security for credential/fuse actions | Authorization expires; physical state changes may be irreversible | Signed approval record bound to exact plan and fixture, recovery procedure and stop conditions | **Not granted.** This design task authorizes no physical operation. |
| P10 — station/manufacturing QA and repair | One isolated station, one named operator, independent QA reviewer; per-unit identity/image/registry/evidence checklist; quarantine failed units; replace with new identity; no ad hoc reflash/reset or identity reuse. | Reduces process error and false provenance. Independent reviewer adds one bounded check, not a large enterprise system. | Factory/QA + Security | QA controls reversible; eFuse failure/rework may be irreversible | Station isolation, operator/reviewer roles, per-device evidence bundle, quarantine and recovery drill | **Ready for owner approval as a pilot procedure; security review of key handling required.** |

## Ready for owner approval

1. Restrict first physical qualification to one disposable, non-customer S3
   fixture and isolated TEST_ONLY trust/backend; keep commercial traffic disabled.
2. Adopt the permanent Hub ID and registry mapping model, with Home/epoch
   exclusively controlled through GS-109 and transfer/revocation fencing.
3. Require fail-closed CloudSync until a fresh signed time proof and current
   identity/ownership checks succeed; local safety continues if the WAN is down.
4. Keep any irreversible fuse/security lock-down outside the first TEST_ONLY
   observation wave and require separately approved signed recovery first.
5. Use one operator and one independent evidence reviewer for the 50–100 Hub
   pilot; reuse GS-165–171 scope/contracts and existing source seams rather
   than building a parallel factory identity stack. Only GS-168 is currently
   implemented as the TEST_ONLY issuer; the planned GS-167/169–171 station
   integration is not claimed complete.

These are proposals for owner disposition. The listed approvers must record
acceptance in Jira or a signed decision record. Nothing in this package accepts
a vendor, CA, key location, numeric threshold, test action, or physical fixture.

## Decisions still requiring Security review

- Actual pilot CA/root and issuing-key custody, HSM/KMS capability, backup and
  compromise response.
- On-device vs isolated-station RSA-3072 key generation; DS HMAC/eFuse key
  origin, handling and read/write protection; plaintext lifetime; debug and
  rework threat model.
- GSTP authority, endpoint/bootstrap transport, independent trust anchor,
  key rotation, audience, signature profile, freshness/validity/error bounds,
  outage/recovery and signer custody.
- Whether cold-boot online proof is the accepted pilot policy or a protected
  monotonic counter is required; flash-restoration and old signed-image
  rollback threat response.
- Exact S3 Secure Boot v2 / Flash Encryption / anti-rollback / ROM/debug
  sequence, per-device key purposes and irreversible recovery point.
- Registry deployment/security, renewal, expiry, revocation propagation,
  ownership transfer, quarantine and replacement lifecycle.
- Any fixture-specific physical, certificate, DS/eFuse, signed-image or
  production-service operation. Those require separate explicit authorization.

## Required approval record

Record each row as `APPROVED`, `REJECTED`, or `DEFERRED` with approver name and
role, date, scope/limits, selected alternative, evidence reference, and
reversal/incident action. A decision marked DEFERRED is a blocking prerequisite
to the affected activity. Never infer approval from Jira assignment or a
successful test. Keep GS-40/GS-68 workflow states unchanged until their
acceptance criteria pass.

Related records: [SOP](GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md),
[fixture checklist](GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md),
[physical plan](GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md),
[GS-68 provider evidence](GS68_D05_D12_D06_PROVIDER_E2E_20261017.md).
