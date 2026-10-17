# GS-172 First ESP32-S3 Hub Provisioning SOP — v1.0

**State:** DRAFT FOR OWNER AND SECURITY APPROVAL; DESIGN ONLY; NON-EXECUTABLE
**Scope:** One non-customer ESP32-S3 N16R8 qualification fixture; design sized for a 50–100 Hub pilot, one operator, one isolated station.
**Authority:** GS-172 comment 11296; links GS-165–GS-171, GS-68 D05/D12/D06, GS-109 ownership, GS-40, and GS-118/D15.
**No authorization:** This SOP does not authorize connecting, powering, reading, provisioning, issuing credentials, signing, flashing, resetting, changing eFuses, enabling Secure Boot/Flash Encryption, or running a physical case.

## 1. Purpose and controlled boundary

This procedure defines the proposed first-device identity, custody, qualification,
manufacturing QA, and recovery flow. It reuses GS-168's TEST_ONLY issuer and
registry contract, existing backend `CloudCredentialRegistry`,
`cloud_client_identity.py`, `ownership_registry.py`, the S3 cloud-trust provider
seam, and the existing GS-68/GS-40 physical case catalogues. It creates no new
PKI, CloudSync transport, ownership model, or validation framework.

The current product composition remains fail closed at
`UnprovisionedS3CloudTrust`. GS-168 refuses non-TEST_ONLY issuance. The local
ESP-IDF 6.0.3 DS APIs support RSA-3072 signing, but the production application
does not yet instantiate a device DS signer or a provisioned identity/time
provider. Consequently this SOP is a reviewable design, not a claim that the
first device can be provisioned today.

The first physical qualification wave, if separately approved, is limited to a
disposable, non-customer fixture and isolated TEST_ONLY issuer, time authority,
and backend. A production leaf, commercial endpoint, owner Home, or customer
data must never enter that wave. Production credentials and irreversible
security configuration require separate approvals and a later qualification
record.

## 2. Identity and authority model

1. Assign one permanent, random, immutable `HubId` to the S3 device. The Hub ID
   is not a MAC address, serial number, QR bearer value, Home ID, or Node
   commissioning identity.
2. Issue one RSA-3072 X.509 leaf with client-auth purpose to that Hub after the
   Hub proves possession of its enrolled public key. The backend authenticates
   the TLS chain and purpose, then maps the certificate SHA-256 fingerprint
   through the authoritative registry to `HubId`, credential generation,
   status, and enrollment/source association.
3. The registry joins the permanent Hub to exactly one current Home and
   monotonically increasing ownership epoch. GS-109's authorized claim/transfer
   operation changes that binding. The issuer cannot choose or infer Home from
   a CSR, QR, MAC, HTTP header, or JSON claim.
4. The backend revalidates credential status and current Home/epoch on every
   accepted request. Transfer, revocation, quarantine, wrong Hub, stale epoch,
   and unknown credential deny publication before the NodeHealth read model is
   updated. Old-Home events are not reparented.
5. GS-40 NodeHealth source identity/session/enrollment association remains
   registry-derived and authenticated by HubRuntime. Permanent Hub identity is
   separate from Node P-256 commissioning identity.
6. The manufacturing QR/label contains only a public opaque lookup identifier
   and manufacturing lot reference. It carries no private key, one-time
   bearer secret, Home authority, or certificate private material.

Registry changes are atomic and auditable. A transfer increments the epoch and
invalidates old authority before new publication is accepted. A certificate
replacement marks the old fingerprint superseded/revoked in the same logical
transaction that activates the replacement. Registry unavailability fails
closed; cached Hub-side status is not authority to continue cloud publication.

## 3. Issuer and secret custody proposal

For 50–100 devices, first reuse an existing organization-approved private CA
and managed KMS/HSM issuer if one already exists and supports the needed
X.509/client-auth profile. Keep the root offline or under the existing root
custody policy, with one constrained issuing key and one accountable operator.
Do not buy or build an enterprise PKI solely for this pilot. If no approved
issuer exists, the smallest fallback candidate is an offline root plus a
single HSM-backed issuing intermediate; Security must approve the custodian,
backup, recovery, access audit, and compromise process before any issuance.
No local filesystem PEM key or station-held unencrypted CA key is acceptable.

GS-168's ephemeral TEST_ONLY root and SQLite public-certificate metadata stay
isolated from every production trust bundle and registry. TEST_ONLY roots are
never trusted by production. The test issuer's private extension is a routing
marker only; the issuer/backend must additionally require the exact registry
entry and `TEST_ONLY` environment. No issuer key is copied to a Hub, station
image, source tree, QR, log, or evidence bundle.

### Device key generation and D12 / DS protection

**Preferred design candidate, subject to Security approval:** generate the Hub
TLS RSA-3072 key on the target in a Secure-Boot-verified provisioning image,
create a CSR from the public key, pass the private-key parameters directly to
the S3 DS encryption flow, and zeroize plaintext key material and transient
buffers before leaving the provisioning operation. Enroll only the resulting
public key after a challenge proves the device can sign. This minimizes export
but does not itself prove non-exportability or prevent observation before the
device is locked.

ESP32-S3 DS uses an HMAC eFuse key to use encrypted RSA private-key parameters
stored in flash; DS is not a private-key generator. The pinned ESP-IDF 6.0.3
header and official documentation state that the RSA parameters must first be
generated/provided and the plaintext input must be destroyed after encryption.
Therefore the design must explicitly protect the generation/loading window,
station, firmware, RAM, debug path, and failed-unit handling. A successful DS
API call or compile is not evidence that the private key was never exposed.

Before implementation or a physical key operation, Security and Hardware must
choose and approve: (a) the on-device generation path above, or (b) an isolated
station-generation path with a documented key-exposure threat model, dual
control, short-lived RAM-only handling, verified zeroization, and no export or
backup of device private material. The preferred path is not yet implemented
or approved. A Hub DS HMAC key, per-device Flash Encryption key, Secure Boot
signing key, TLS private key, and authenticated-time signing key are distinct
keys with distinct purposes. No key is derived from or reused as another.

The individual device's certificate renewals may reuse the same DS-held public
key only if Security approves that limited pilot policy and revocation/recovery
is proven. A key replacement uses a new key, new CSR, new certificate
fingerprint and registry generation; the prior credential is revoked. A lost,
compromised, or irrecoverably provisioned Hub is quarantined and replaced with
a new permanent identity. Identity reuse is prohibited.

## 4. D06 authenticated time proposal

Reuse the existing bounded GSTP v1 signed-time proof implementation as the
TEST_ONLY protocol candidate: RSA-3072/SHA-256/PKCS#1 v1.5 signature over a
fixed header containing format/suite, boot generation, a one-use 32-byte
PSA-CSPRNG nonce, issued-at, valid-from, and valid-until. The device accepts
one proof for its outstanding nonce, checks signature, boot generation,
freshness and interval, compares against its time floor, and commits the floor
before marking cloud time ready. The proof's signer and trust anchor are
separate from Hub TLS, Secure Boot, and issuer keys.

Proposed startup rule: at every cold boot, production CloudSync and TLS remain
disabled until a fresh signed proof is verified. While a boot remains alive,
derive UTC only from that verified UTC sample plus a monotonic clock. If the
network is unavailable at cold boot, local Hub/Node safety continues but
CloudSync stays unavailable; no unauthenticated SNTP, RTC value, or NVS floor
alone marks time trusted. On restoration, obtain a new nonce-bound proof and
resume only after validating current Home/epoch/credential authority. A proof
for an old owner epoch must not restore publication.

The existing NVS floor and boot counter are ordinary flash state and can be
rolled back with a restored image. They are useful for state-machine checks,
not a rollback-resistant hardware counter. The online fresh-proof-on-every-cold-
boot proposal reduces reliance on prior wall-clock state but does not by itself
stop an attacker from booting an older, still-valid signed image that bypasses
current policy. Production therefore also needs a reviewed Secure Boot and
firmware anti-rollback policy (GS-118/D15). If offline cold-boot time trust is
required, Security must approve and qualify an actual protected monotonic
counter or secure element; otherwise it remains unavailable.

The existing GSTP wire format has no key-id field. The proposed pilot trust
anchor is pinned in a Secure-Boot-verified image with an approved overlap
rotation procedure. An anchor rotation that cannot be safely delivered through
the current signed-update/recovery path is a blocker, not a reason to disable
signature validation. Numeric maximum proof age, statement lifetime, clock
error, outage behavior, floor checkpoint/wear bounds, and time-authority
availability are OPEN; no threshold is invented here.

The proof response contains no credential and needs no secret-bearing request.
The transport/bootstrap endpoint still needs Security approval: it must not
depend on unauthenticated SNTP or date-only TLS acceptance. Signed nonce-bound
proof verification is the time-authentication boundary; transport tampering or
replay must fail verification, while delay/unavailability fails closed.

## 5. Secure Boot / Flash Encryption / recovery sequence

These are gated design stages, not fuse instructions. The exact eFuse map,
fields, key-block purposes, read/write protection, debug policy, and irreversible
order must be reviewed against the identified board's actual revision and
read-only security-state evidence before any operation.

1. Preserve the unit's source/lot/board provenance and record a read-only
   security-state summary without exposing key-block contents.
2. Approve the signed provisioning and recovery images, signing-key custody,
   partition map, verified update/rollback behavior, and image provenance.
   Current S3 app does not yet provide the required production OTA receiver and
   recovery path; this is a hard NO-GO for commercial irreversible lock-down.
3. Allocate a unique per-device Flash Encryption key and an approved FE key
   purpose/custody flow. Never reuse a key. Verify encrypted image boot and
   recovery before locking the unit.
4. Follow the pinned ESP-IDF 6.0.3 external-provisioning workflow's required
   ordering. In that documented flow FE key/enablement precedes the Secure Boot
   v2 irreversible digest/write-protection stage because later protection can
   prevent protecting the FE key. Verify the exact supported sequence for the
   board and selected mode; do not translate this summary into commands.
5. Enroll the distinct Secure Boot v2 RSA-PSS image-signing public digest and
   verify the signed bootloader/application. Configure any firmware
   anti-rollback counter only with a tested signed update and recovery image.
6. Enable final ROM/download/debug restrictions only after signing, FE, DS/TLS,
   update, outage, failed-boot recovery, and replacement procedures pass on a
   disposable fixture. Apply read/write protections last in the approved
   sequence. Do not consume irreversible eFuse steps in the first
   TEST_ONLY observation wave.

Espressif documents Secure Boot v2 image signatures, Flash Encryption Release
mode, and the external provisioning workflow here:
[ESP32-S3 DS peripheral](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/api-reference/peripherals/ds.html),
[Secure Boot v2](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/security/secure-boot-v2.html),
[Flash Encryption](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/security/flash-encryption.html),
[security-feature enablement workflows](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/security/security-features-enablement-workflows.html).
The project's SDK is pinned to ESP-IDF 6.0.3; the locally inspected v6.0.3
`esp_ds.h` exposes the DS RSA-3072 API and documents the encrypted-parameter
input boundary. The version-specific exact eFuse operations remain subject to
review and a source-pinned procedure before authorization.

## 6. Non-executable station SOP and evidence

| Stage | Operator action after a separate scoped authorization | Required evidence / pass gate |
|---|---|---|
| A. Approval packet | Confirm signed GS-172 decision matrix, exact fixture, environment, allowed actions, expiry, named operator, independent reviewer, recovery owner, and case-plan digest. | Approval references fixture ID and hashes; all applicable decisions are resolved; otherwise STOP. |
| B. Intake | Identify lot, PCB revision, N16R8 flash/PSRAM provenance, serial/MAC for anti-collision only, and board documentation. Exclude all GS-114/C8 fixtures, cables, ports, and evidence directories. | Two-person fixture match to inventory; photos and redacted public identifiers; no customer fixture. |
| C. Read-only baseline | Under a separate observation approval, collect current image/source/profile identity and summarized security state; do not open an unapproved interface or read/export key material. | Stable fixture identity, installed-image proof, config/session baseline, read-only state record, no unexpected reset. |
| D. Identity reservation | Reserve a unique permanent Hub ID and pending registry row. Do not assign Home from manufacturing label or CSR. | Registry audit record, unused-ID check, fixture/lot association, state `PENDING`. |
| E. Issuer/key operation | Run only the security-approved key-generation/DS path and issuer. Obtain CSR/public key, prove possession, validate RSA-3072/client-auth profile and issue leaf in the approved environment. | Issuer and CA fingerprints/serial, CSR digest, leaf fingerprint/chain, signature challenge result, key custody/zeroization attestation; no secret in evidence. |
| F. Authority binding | GS-109 authorized enrollment/claim binds Hub ID to Home and epoch; registry activation joins fingerprint, enrollment/source association, Home, epoch, credential generation and active state. | Independent registry readback and backend negative checks for wrong Home/epoch, old epoch, revoked/quarantined, expired, unknown. |
| G. Secure boot/FE | Only after separate security authorization and signed recovery GO, perform the reviewed order on a disposable unit. | Per-unit key-purpose summary, signed image digests, encrypted boot result, anti-rollback and recovery result, reviewer-signed fuse-state summary. |
| H. Signed time | With TEST_ONLY time authority first, challenge with fresh nonce/boot generation; verify valid proof, replay rejection, missing/corrupt floor, clock rollback, reboot/outage and owner-epoch change. | Captured redacted request/proof digest, verifier result, trusted floor/generation state, expected fail-closed result on each negative case. |
| I. GS-68/GS-40 acceptance | Execute only separately authorized GS68-PHY/GS40 cases in their recorded order and environments. | Per-case evidence, correlated Hub/Home/epoch/Node/session/sequence, backend receipt, caregiver snapshot, timestamps and EventKey/ACK invariants. |
| J. Closeout | Independent QA reviews source/image and evidence hashes, registry/certificate state, security profile, unresolved warnings, and unit disposition. | Signed checklist, state `QUALIFIED_TEST_ONLY` or `QUARANTINED`; never infer production readiness. |

Every evidence directory is new, access controlled and hash-manifested. Record
source commit, tool/SDK versions, build profile and config/image hashes, fixture
and approval IDs, timestamps, case IDs, result, operator, reviewer, and
redacted public credential identifiers. Never collect private keys, raw
eFuse key contents, bearer claims, household data, or production secrets in
logs, Git, Jira, serial output, or qualification captures.

## 7. Manufacturing QA, exception and recovery policy

- A device passes identity QA only if permanent Hub ID, CSR public key,
  certificate fingerprint, registry state, and proof-of-possession result agree.
- It passes authority QA only if current Home and epoch agree between GS-109,
  the authoritative registry, backend verifier, and accepted NodeHealth source
  association. Transfer and revocation must deny the old authority before any
  subsequent healthy status is accepted.
- It passes time QA only if valid fresh proof succeeds and invalid signature,
  nonce replay, wrong boot generation, expired/future proof, corrupt/missing
  state, clock rollback, reboot without time, outage, and epoch change fail
  exactly as approved. Numeric thresholds must come from signed approval.
- It passes hardware key QA only with an actual device DS sign operation
  verified by the enrolled public certificate, plus approved evidence for
  key origin, DS HMAC-key purpose/state, transient zeroization, and disabled
  unauthorized debug/export. Host crypto tests do not satisfy this criterion.
- It passes recovery QA only after an authorized signed recovery/update path
  restores a known valid image without erasing durable user/event state or
  bypassing anti-rollback. The current product path does not yet demonstrate
  this; mark recovery `NOT_READY` and keep commercial lock-down NO-GO.
- Any identity, cert, time, boot, image, registry, fixture, or evidence mismatch
  stops processing. Preserve logs, mark `QUARANTINED`, revoke the cert, and
  require owner/security disposition. Do not retry key/fuse writes or reset the
  device as an ad-hoc recovery.
- Failed irreversible provisioning is never repaired by reusing identity or
  secret. Use a newly approved recovery path or permanently quarantine and
  replace with a new Hub ID and new independent keys/certificate.
- Certificate expiry/renewal, overlap, emergency revocation, CA compromise,
  authority-key rotation, station compromise, operator turnover and unit
  replacement are tested/approved before the first production issuance.

## 8. Global stop conditions

Stop before the applicable action when an approver, fixture, board revision,
current security-state record, signed source/image, signer, time authority,
registry binding, recovery method, safe observer, expiry, or evidence path is
missing or inconsistent. The first stage requiring a physical interface or
power remains separately unauthorized. Never use TEST_ONLY credentials in
production or describe a compile/host test as a physical pass.

Related records: [decision and approval matrix](GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md),
[fixture readiness checklist](GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md),
[physical acceptance plan](GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md),
[GS-68 provider evidence](GS68_D05_D12_D06_PROVIDER_E2E_20261017.md),
[GS-68 first physical plan](GS68_S3_FIRST_PHYSICAL_QUALIFICATION_PLAN_20261016.md),
[GS-40 readiness](GS40_REAL_TARGET_READINESS_20261016.md).
