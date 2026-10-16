# GS-166 — Pilot Provisioning Station v1: minimal trust and state contract

**Owner-approved scope (16 October 2026):** single home-based operator, sequential preparation of the first 50–100 ESP32-S3 N16R8 Hubs. This is a **design for software simulation**, not authorization to provision a real device. GS-165 is the umbrella; GS-167 CLI, GS-168 mock X.509 issuer, GS-169 registry/QR, GS-170 QA, GS-171 negative tests and GS-172 real-device security gate are separate owners.

## Trust boundaries

| Identity | Authority / owner | Meaning |
|---|---|---|
| Permanent Hub/manufacturing identifier | Future GS-169 local registry | Public lookup and audit only; not proof of identity or Home ownership |
| Hub cloud certificate | Real GS-68/172 issuer, verified by GS-109/backend | Per-Hub X.509 TLS 1.2 client identity only after issuer, key custody and revocation are qualified |
| Home ID and installation/ownership epoch | Authoritative GS-109 ownership registry | Backend Home/Hub authorization; NEVER assigned by factory CLI or QR |
| C3 Node identity and commissioning session | Existing Node/Hub commissioning, GS-109 Add Device | Independent P-256 exact-Node proof; not the Hub cloud TLS certificate |
| Public QR lookup handle | GS-169 registry | Random opaque public reference, not a claim token or secret |
| TEST_ONLY test issuer and leaf | GS-168 self-contained simulator | Host simulation evidence only, never customer-device authentication |

GS-68 owner decision comment 11217 approves the **architecture direction**: unique Hub X.509/RSA-3072 DS-backed mTLS, current Home/epoch verification, protected S3 key strategy. It does not approve private-key generation/transfer, eFuse programming, actual trusted-time bootstrap, factory issuance, physical qualification or production activation. Recent GS-109/68/148 CloudSync source commits do not change this boundary.

## Minimal interfaces and data flow

1. GS-167 CLI will later offer **sequential** simulate-one / simulate-batch / status / resume / quarantine / verify / export-public. No parallel factory orchestration or web dashboard.
2. GS-168 test issuer accepts RSA-3072 signed CSR with exact \`CN=TEST_ONLY:test-hub-...\`, performs issue/verify/revoke/explicit renew, and exports public certificate or SHA-256 fingerprint. The signing CA key remains in **host process memory only**. A non-test \`environment\` fails closed \`NOT_READY_SECURITY_APPROVAL\`.
3. GS-169 SQLite registry will later bind unique permanent public Hub ID, model/revision, issuer/cert fingerprint, firmware identity, reserved public QR handle and QA state. Its records NEVER assert valid customer TLS credentials merely because a simulation passed.
4. GS-170 QA will later record source/image/config hashes and **actual** per-board evidence. Simulation results have a separate category and may not be promoted to hardware PASS or DELIVERY_READY.
5. GS-109/148 verified ownership and CloudSync use their **existing** authoritative services; the factory simulator never becomes an alternate Home registry or verifier.

## Simulated state machine

\`NEW -> RESERVED -> TEST_CREDENTIAL_ISSUED -> SIMULATED_QA_PASS\`

\`NEW / RESERVED / ISSUED -> QUARANTINED\` on identity conflict, expired/revoked credential, unknown provenance or interrupted unrecoverable operation. A manual, documented review may lead to a new attempt, but cannot silently turn a failed or simulated unit into hardware-qualified READY.

**Future, not implemented:** \`SECURITY_APPROVED -> REAL_KEY_PROVISIONED -> CERT_VERIFIED -> PHYSICAL_QA_PASS -> DELIVERY_READY\`; this requires GS-172's separate hardware/credential permissions and acceptance evidence.

## Failure and recovery policy

| Condition | Required result |
|---|---|
| Duplicate test Hub ID / CSR from different Hub | Reject; no silent rekey or duplicate |
| Explicit renewal with currently active test cert | Atomically supersede old cert; reject old cert on verification |
| Test cert expired, revoked, wrong issuer, mismatched public key | Reject, not HEALTHY/READY |
| Test issuer unavailable | No record advance; retry only on explicit recovery |
| Restart metadata DB with the **same in-memory** TestOnlyAuthority | Reopen and verify public metadata |
| Restart after ephemeral CA was lost | CA fingerprint mismatch; reject existing DB, never substitute new CA |
| QR duplicate, identity conflict or registry corruption | Fail closed, quarantine; no automatic Home grant |
| Missing trusted time/real issuer/S3 protected-key qualification | \`NOT_READY_SECURITY_APPROVAL\`; no USB/eFuse/flash changes |

The test CA is deliberately ephemeral. Test SQLite holds only **public certificates and metadata**, never private keys or live Home assignments. This is not the durability model for a future protected real CA.

## Minimal security review

- Exact certificate subject and CSR signature and RSA-3072 public key.
- Leaf clientAuth, non-CA role, valid time bounds, issuing CA signature, distinct certificate fingerprint.
- Critical \`TEST_ONLY\` extension in both CA and leaves; **the real verifier must additionally exclude that CA entirely**.
- Reject unknown/revoked/superseded issuer or leaf, wrong Hub, compromised namespace and attempted production crossover.
- Do not log/export private keys, CSR secret material, bearer QR values or resident information.
- No source modification to active Hub firmware, CloudSync, production authenticator or PWA.

## Test and evidence map

GS-168 isolated unit tests exercise signed CSR/public-key match, unique certificate, real X.509 public cert, expiry, renewal and invalidation, revocation, simulated issuer outage, persisted public metadata restart, wrong CA/Hub/CSR and forbidden production mode, plus sequential batch (10 normally; 100 with \`GS168_TEST_100=1\`). GS-171 owns future permanent station CLI→registry→QA end-to-end integration and GS-116 registration. No physical or customer readiness assertion follows from this test-only software.

**Dependencies:** GS-165 approved pilot scope; GS-68 security direction, GS-109 authoritative ownership, GS-148 trusted CloudSync, GS-116 focused validation; future GS-167/169/170/171 station and separately authorized GS-172 real provisioning.
