# Phase-2 Device Identity and Provisioning Design

**Decision status:** unique asymmetric Node identity approved; protocol and
irreversible manufacturing settings remain under review.

## Trust identities

- A physical C3 has an immutable Device ID and unique P-256 identity keypair.
  The private key stays on that C3. The QR/manufacturing record carries its
  Device ID and public key or a verifiable certificate, never the private key.
- A Hub has its own installation identity and keypair. A random Home ID binds
  the installation. A Node pins the authenticated Hub identity and Home ID
  after commissioning. Physical identity and logical room/function assignment
  remain separate so replacement hardware retains the logical slot without
  inheriting the old physical identity.
- A manufacturer firmware-signing trust root is distinct from each Node's
  identity key. Firmware delivery is authorized under the Hub/Node session;
  image authenticity and boot enforcement require the trusted firmware signer.

## Commissioning protocol requirements

The installer scans the exact Node QR and authorizes a bounded Hub pairing
window. The Node must also receive proof of installer authorization for this
Hub; seeing an arbitrary Hub public key over ESP-NOW is insufficient. A
one-time installation authorization code in the QR is a **proposed** offline
mechanism. It may authorize enrollment but must never be a credential that
alone enables Node impersonation. Physical Node intent and bounded time reduce
radio exposure. The precise code reset/recovery workflow needs a protocol
review before release.

The proof transcript must bind fresh Hub and Node challenges, both public
identities, Home ID, intended logical assignment, ephemeral key exchange and
protocol version. Standard P-256 signature verification, ephemeral ECDH,
HKDF-SHA-256 and authenticated encryption should be supplied by reviewed
ESP-IDF cryptographic libraries. Reject replay, wrong Home/Hub, wrong Device
ID/public key, interrupted transactions and ambiguous clones. The registry
must receive an authenticated result only after the entire proof completes.

Runtime data, ACK, health, maintenance and FOTA control use symmetric session
keys and authenticated encryption. Nonces must be unique per key/direction
across restart; session and sequence metadata must be authenticated. A fresh
authenticated rejoin establishes a new session without QR scanning.

## Storage and manufacturing

| Profile | Private-key and association policy |
|---|---|
| Development/HIL | Generate distinct test keys at runtime or provision explicit test-only keys. Prototype storage may be unprotected for software qualification and must be labelled non-production. Do not commit generated private keys or burn eFuses. |
| Production C3 | Prefer on-device factory key generation, export public identity only, then place the private key in a protected store. ESP-IDF 6.0.3 documents C3 HMAC-eFuse-derived NVS encryption and flash-encryption-protected NVS key partitions. Select the exact eFuse block/purpose, partition layout, read protection and firmware policy in a separate manufacturing-security approval. Ordinary plaintext NVS is unacceptable. |
| Production Hub | Generate or provision a unique Hub key and Home ID; protect Hub private key, enrolled public identities, derived association secrets and replay counters. The current ESP32 target lacks the C3 HMAC storage option in its generated configuration; ESP-IDF documents a flash-encryption-protected NVS key partition. Select the Hub secure-boot, flash-encryption and recovery policy before manufacturing. |

The current target `sdkconfig` has secure boot and flash encryption disabled
for both boards and C3 NVS encryption disabled. The current ESP32 Hub reports
Secure Boot V1 support; C3 reports Secure Boot V2 RSA support. None of these
features is claimed active in the Phase-1 or current Phase-2 physical fixture.
Do not burn eFuses or claim protected production storage on these boards.

Factory reset clears Home/Hub association and derived runtime keys; the
factory Device ID and private identity key survive. Removing a Node revokes
its association and sessions; replacing it requires a new physical keypair.
An automated Hub-key migration or escrow policy is not defined. Baseline Hub
replacement requires explicitly recommissioning Nodes. A perfect clone after
private-key compromise cannot be distinguished cryptographically; conflicting
MAC/session contexts must be quarantined where observable, with service audit
evidence.

The manufacturing process must specify key-generation audit, public-key/QR
binding, factory test, firmware signer custody, debug access, eFuse programming
verification, failure/rework, replacement and lost-key policy. No production
private key, signing key, test credential masquerading as production or local
fixture MAC belongs in the repository.

## Host protocol checkpoint

The P2.3 host foundation implements P-256 identity signatures, ephemeral
ECDH, HKDF-SHA-256, HMAC-SHA-256 and AES-256-GCM through a crypto-provider
interface. The OpenSSL provider creates test-only identities at runtime. The
commissioning transcript authenticates the Device ID, Hub/Home IDs, logical
ID, room, function, both public identities, fresh challenges and ephemeral
keys. Host tests cover changed assignment fields, wrong identity, a changed
transcript, expiry and replay. The Node commits its binding only after a
verified Hub confirmation and final ACK.

This checkpoint is not target commissioning. ESP-IDF crypto and protected-key
providers, target transport, persistent association, authenticated rejoin and
runtime packet AEAD remain to be implemented and qualified. A copied installer
authorization code can race enrollment while a window is open; it cannot
impersonate the Node without the Node private key. A half-completed transaction
still needs a persistent recovery protocol before production use.

The host multi-node transport now derives separate uplink/downlink AES-256-GCM
keys from each installation key and an authenticated session salt. Its common
security envelope authenticates the physical and logical identity, Home/Hub,
direction, session and packet counter. A 64-packet replay window is advanced
only after a valid tag. The current host harness supplies the fresh session
salt directly after commissioning; that is not an authenticated target rejoin
protocol. Target delivery must verify fresh rejoin before using a new salt or
resetting counters. The conservative 250-byte frame budget leaves 222 bytes
for the existing encoded data-plane frame after the 28-byte security overhead.

The ESP-IDF 6.0.3 PSA adapter is compiled for both current target projects.
It uses PSA P-256, SHA-256, ECDH, HKDF, HMAC and AES-GCM operations and
delegates identity public-key lookup and signing to an `IdentitySigner`.
No target identity store implements that interface yet. Compiling this adapter
does not prove that a private key is protected, that the hardware accelerates
an operation, or that secure boot/flash encryption is active. The signer must
be backed by the selected protected production store after the separate
manufacturing-security decision; HIL may use isolated test-only keys.

## Source inspection

This design uses the repository's generated ESP-IDF 6.0.3 `sdkconfig` files
and the installed ESP-IDF 6.0.3 NVS encryption guide
(`components/nvs_flash` and `docs/en/api-reference/storage/nvs_encryption.rst`).
The effective eFuse layout, secure-boot mode and protected partition design
still require target-specific manufacturing review and explicit approval.
