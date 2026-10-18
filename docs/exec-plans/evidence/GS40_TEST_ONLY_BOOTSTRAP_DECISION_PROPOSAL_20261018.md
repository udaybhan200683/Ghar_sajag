# GS-40 TEST_ONLY S3 bootstrap and authority contract — decision proposal

**Status:** PROPOSED — NOT APPROVED / NOT LOCKED

**Date:** 2026-10-18

**Owner:** GS-40; shared boundaries GS-109, GS-148, GS-168, GS-68

**Checkpoint:** `f8dc5ca44cdf4fabf85f481fa269d1c14112a62e`, branch
`feature/r1-commercial-baseline`

**Scope:** isolated host/lab TEST_ONLY S3 product composition only. This is not a
production identity, credential, time, Wi-Fi provisioning, or factory decision.

## Decision requested

Approve or reject the bounded TEST_ONLY contract below, called `GS40T/1`, so
implementation can connect the existing `ProvisionedS3CloudTrust`,
`AuthenticatedHubTimeProvider`, GS-168 issuer/registry, S3 CloudSync worker and
local NodeHealth service. Approval would authorize implementing and testing this
test-only data path. It would not authorize physical board access, credential
installation, production activation, commercial trust, changes to GS-D032, or a
claim of production rollback resistance.

If rejected, the required replacement decision is the same contract boundary:
name the authorized target input for (1) test Wi-Fi/backend configuration,
(2) pre-TLS authenticated-time bootstrap and trust anchor, and (3) fresh
GS-168/current Home-epoch authority material. Until one is approved, product
startup must remain on `UnprovisionedS3CloudTrust`.

## Why existing interfaces do not authorize implementation

- GS-D032 locks permanent Hub identity, current Home/epoch, proof of possession,
  revocation/transfer fences and audit behavior. It explicitly leaves credential
  technology, issuance, proof freshness/challenge and recovery mechanisms open;
  it says not to invent these mechanisms or credentials.
- `S3CloudTrustMaterialSource` requires one authenticated immutable snapshot of
  permanent Hub ID, active current Home/epoch, credential state/generation and
  key material. There is no S3 target implementation for this interface.
- `AuthenticatedHubTimeProvider` and `Rsa3072Sha256TimeProofVerifier` already
  implement nonce/boot-generation-bound RSA-3072/SHA-256 proof verification.
  No product transport supplies its challenge response or authenticated public
  key before TLS. CloudSync HTTPS requires trusted time for X.509 validity, so
  using that same HTTPS request to bootstrap time is circular.
- GS-168 is a host TEST_ONLY issuer/registry. It has no target delivery protocol,
  current Home/epoch lease endpoint, or revocation refresh path.
- Product Wi-Fi startup initializes STA but has no bounded runtime source for
  credentials, backend origin, trusted server CA/hostname or provisioning
  references.

Therefore, using unsigned NVS fields as authority, using a client Home/epoch
claim, accepting SNTP/host wall clock, skipping certificate-time checks, or
selecting a time key from an unauthenticated response would invent or weaken a
security interface. No product source change can safely fill this gap under the
current LOCKED decisions alone.

## Recommended `GS40T/1` contract

### 1. Trust roots and strict isolation

1. The isolated TEST_ONLY S3 build contains only public verification material:
   a GS-168 TEST_ONLY provisioning/issuer verification key and its distinct
   TEST_ONLY time-authority public key (or the time key authenticated inside the
   signed provisioning envelope). Private signing keys remain in the isolated
   host fixture process or protected test secret store and are never compiled,
   committed, logged, or sent to the target.
2. Test-only keys, certificate markers, issuer namespace, server CA and service
   hostname are disjoint from all commercial roots/endpoints. Build guards
   reject TEST_ONLY identity fields unless `GS40_TEST_ONLY_CLOUDSYNC_BUILD=1`
   and the explicit TEST_ONLY profile is selected. Commercial startup remains
   DS-only/fail-closed with `UnprovisionedS3CloudTrust` until commercial
   provisioning is separately approved.
3. The source of credential truth remains the existing GS-168 TEST_ONLY
   issuer/registry plus the existing backend `HubOwnershipRegistry`; this
   proposal adds adapters/contracts, not another issuer or ownership database.

### 2. Runtime configuration and initial credential delivery

Use a bounded signed-and-encrypted one-session fixture envelope, delivered by
the isolated test harness over the existing USB diagnostic/configuration
channel. This channel is TEST_ONLY and is not a production provisioning path.

- On boot, the target obtains a fresh PSA random P-256 ECDH session keypair and
  32-byte challenge. The host sends the signed envelope to that session public
  key using ECDH + HKDF-SHA-256 + AES-256-GCM. Since the target has no approved
  permanent cloud identity yet, the USB/PnP fixture selection and exclusive
  operator-controlled cable are the lab trust point; this handshake does not
  cryptographically attest the physical S3 to the host. Active USB substitution
  is outside this TEST_ONLY lab threat model and must not be represented as
  production-grade provisioning.
- The envelope signature is verified under the pinned GS-168 TEST_ONLY
  provisioning verification key, with a domain string `GS40T/1/CONFIG`.
- The authenticated plaintext has a strict length cap of 24 KiB and contains:
  schema/version, one-use target challenge, fixture ID, monotonic bundle
  generation, expiry fields, isolated SSID/PSK, fixed HTTPS origin, exact server
  hostname and CA certificate, time-proof authority endpoint/key reference,
  permanent test Hub ID, GS-168 test client certificate/private key, credential
  generation/fingerprint, and profile marker. The material is accepted only
  into bounded RAM buffers; PSK and private key are cleared on shutdown,
  expiry, authority rejection and error. Do not persist this envelope or its
  secrets in NVS, firmware, logs, or evidence.
- Before trusted time exists, the target verifies envelope signature, AEAD,
  challenge and schema, but does not use wall-clock/host time to declare the
  certificate or envelope current. It may use only the network bootstrap fields
  needed to obtain authenticated time. After time is accepted, it verifies
  envelope `not_before`/expiry and client-certificate validity before TLS.
- A used challenge, malformed/oversized envelope, unsupported profile, wrong
  signature, wrong recipient key, missing field or generation rollback is a
  hard failure. Configuration replacement requires a fresh challenge and
  another complete signed envelope. No automatic fallback to a prior bundle.

The host sees a test Wi-Fi PSK because it provisions the test fixture. It must
be a disposable isolated-lab credential, never a customer or production secret.
Envelope encryption protects against passive capture on the controlled USB
link; the lab trust assumption above excludes an active USB interposer. TEST_ONLY
software-key and RAM handling do not claim hardware-protected key custody.

### 3. Authenticated time before normal TLS

1. After loading only the signed envelope's bootstrap network fields, connect to
   the isolated network and request time using a bounded UDP exchange. UDP is an
   untrusted carrier and supplies no trust by itself.
2. Start `AuthenticatedHubTimeProvider`, increment its existing persisted boot
   generation and generate its fresh 32-byte PSA nonce. Send exactly the nonce
   and boot generation to the configured test-time endpoint. Accept exactly one
   fixed 456-byte `GSTP/1` RSA-3072/SHA-256 proof through the existing verifier.
3. Require exact nonce and boot-generation match, valid signature, bounded
   issued/validity interval, response age and monotonic challenge deadline; reject
   replay, stale generation, malformed proof, expired/not-yet-valid statement,
   zero nonce, clock rollback and corrupt/unavailable time-floor storage.
   Persist the authenticated time floor using the existing provider interface.
4. Only after provider readiness set the system clock from the authenticated
   snapshot and permit TLS. Never use SNTP, RTC, host timestamp, TLS certificate
   time or unsigned endpoint JSON as proof of time.
5. Lost network leaves CloudSync unready. On recovery, perform a new challenge
   bound to the current boot generation; do not reuse a prior proof. After
   restart, require a new signed proof even if a persisted floor exists.

For this isolated test build, the proposed injected time policy is: maximum
proof response age 30 seconds, maximum signed statement lifetime 300 seconds,
and authenticated floor checkpoint at least once per 60 seconds while running.
These are proposed TEST_ONLY values, not production thresholds. `NvsAuthenticatedTimeFloorStore`
provides restart persistence only and is not resistant to a restored older flash
image; this contract makes no malicious full-flash rollback-resistance claim.

### 4. Current authority and credential refresh

Once authenticated time is ready, use the configured CA and exact hostname to
establish TLS 1.2 mTLS to the isolated backend/authority service using the
GS-168-issued RSA-3072 ClientAuth test credential. No redirects or alternate
hosts are permitted.

- A bounded TEST_ONLY authority-refresh operation presents the client
  certificate and a fresh request nonce/boot generation. The existing server
  adapter verifies certificate chain, ClientAuth purpose, fingerprint, active
  GS-168 registry state, permanent Hub association, and current backend Home
  ownership/epoch. A caller-supplied Hub/Home/epoch, MAC, serial or QR never
  establishes authority.
- A successful response contains one immutable authority lease: Hub ID, current
  Home ID, ownership epoch, authority revision, credential fingerprint and
  generation, state ACTIVE, request nonce/boot generation, issued/expiry times,
  and any registry/enrollment generation needed to validate NodeHealth. The
  response is bound to the authenticated TLS session and signed by the
  TEST_ONLY authority key with domain `GS40T/1/AUTHORITY`.
- The target verifies the response signature, nonce/generation, expiry and exact
  match to the TLS client certificate/material before publishing an atomic
  `S3CloudTrustMaterial` snapshot. Its source refreshes at most every 15 seconds
  and before every NodeHealth batch; proposed lease TTL is 60 seconds. On
  refresh failure, transfer, revoked/superseded cert, epoch change, invalid
  enrollment or lease expiry, fence new CloudSync sends immediately and clear
  the authenticated snapshot. Do not fall back to a cached prior Home/epoch.
- Backend authorization independently checks the presented credential and
  active Home/epoch/Node enrollment in the existing registry in the same
  transaction that accepts the health update. Thus an ownership transfer or
  revocation rejects the old authority even if an unexpired local lease is
  replayed or the Hub has not yet refreshed. A rejected update cannot project
  ONLINE. The caregiver source ages to UNKNOWN according to the existing
  freshness contract; Node lease expiry remains OFFLINE only while source
  freshness is trustworthy.
- Existing HubRuntime liveness, default 300-second contact policy, 910-second
  offline threshold, configured legacy profiles, durable EventKey/ACK/retry and
  event-priority semantics remain unchanged. NodeHealth remains a bounded
  current-state publication, not a synthetic durable event.

Proposed TEST_ONLY freshness values are a 60-second authority lease and refresh
every 15 seconds/before publication. They bound, but do not eliminate, the
offline interval before an isolated test service can notify the target. The
backend transaction check is the immediate acceptance fence.

### 5. State and failure behavior

State machine: `UNCONFIGURED -> CONFIG_VERIFIED -> WIFI_UP -> TIME_TRUSTED ->
TLS_AUTHENTICATED -> AUTHORITY_CURRENT -> CLOUDSYNC_READY`.

Any missing prerequisite moves to a non-ready state; retries are bounded with
backoff and do not change trust state. Only time bootstrap may use pre-TLS UDP;
all credential/ownership refresh and CloudSync use CA/hostname-validated TLS.
No events are ACKed/retired based on a failed CloudSync response. Durable events
retain their existing priority and idempotent EventKey handling. Current-status
failure is surfaced as stale/UNKNOWN, never as resident inactivity. A revoked or
transferred identity immediately blocks sends and requires a fresh authorized
fixture envelope; no local factory reset or unsigned Home edit can recover it.

### 6. Threat model and limits

This TEST_ONLY profile addresses malicious network response/replay, forged time,
wrong issuer, certificate/key mismatch, unauthorized Home/epoch claim, stale or
revoked test credential, cross-Home request, malformed/oversized config,
accidental production endpoint/root selection, startup with missing inputs, and
WAN loss/recovery. It assumes the isolated fixture harness and its short-lived
test signing keys are controlled, and that test-network credentials are
disposable. It does **not** claim resistance to physical extraction, malicious
host/fixture operator, test-key compromise, flash-image rollback, S3 software
private-key extraction, Secure Boot/Flash Encryption absence, production CA
misissuance, or live production attacks. Those remain GS-68/GS-172 decisions and
qualification gates.

### 7. Alternatives considered

| Alternative | Disposition |
|---|---|
| Unsigned Home/epoch or NVS configuration as authority | Reject: not an authenticated current owner and replayable. |
| SNTP/host wall-clock or HTTPS certificate time as bootstrap | Reject: not an authenticated authority and/or circular TLS dependency. |
| Disable certificate date checks during bootstrap | Reject: weakens certificate validation and hides the time dependency. |
| Put credentials, PSK, private keys or authority claims in source/image | Reject: leaks secrets and fixes mutable authority into firmware. |
| Reuse GS-168 issuer/registry and existing ownership registry through a test-only signed envelope, signed-time challenge and mTLS refresh | Recommend: smallest path through existing identity/time/transport abstractions; isolates tests without another PKI or registry. |
| Production CA, DS/eFuse, factory provisioning or live commercial endpoint | Not appropriate for this test-only unblock; requires separate GS-68/GS-172 approvals. |

## Acceptance tests required if approved

Register permanent test IDs in the current GS-116/GS-130 registries. Tests must
exercise the actual target adapters and composed product startup, plus local
integration service paths:

1. Correct config signature, recipient challenge and decrypt; reject wrong
   signature, replayed challenge, malformed/oversized input, wrong profile,
   substituted endpoint/CA and repeated generation.
2. Confirm PSK/client key are absent from image/source/NVS/logs and cleared from
   RAM at expiry/failure; verify normal commercial build has no TEST_ONLY
   material path and remains fail-closed.
3. Time: cold start, valid proof, bad signature, nonce mismatch, boot-generation
   mismatch, replay, expired/not-yet-valid, corrupt/missing floor, rollback,
   timeout, restart and network recovery. Confirm no HTTPS before trusted time.
4. Authority: valid active GS-168 credential/current Home+epoch; wrong Hub,
   wrong Home, old epoch, revoked/superseded/expired credential, enrollment
   mismatch, signed lease replay, lease expiry, transfer during refresh and
   failure/recovery. Confirm old authority cannot create a backend health
   acceptance or caregiver ONLINE state.
5. Cloud path: valid HubRuntime authenticated contact -> bounded CloudSync
   NodeHealth HTTPS/mTLS ingest -> backend ownership check/storage -> caregiver
   ONLINE; silent 910-second expiry -> OFFLINE; stale Hub/backend -> UNKNOWN;
   authenticated recovery -> ONLINE. Include configured 300/910 and approved
   legacy profiles, without changing EventKey/ACK/retirement behavior.
6. Startup fail-closed on missing configuration, Wi-Fi, time authority, time
   proof, server CA/hostname, credential, binding or registry service. Verify
   retry bounds and that untrusted transport errors never become readiness.
7. ESP-IDF 6.0.3 non-flashing S3 product build with source/profile/config
   provenance; independently test that commercial build does not link or select
   TEST_ONLY composition. Host E2E is software evidence only; physical
   acceptance remains NOT_RUN until separately authorized and evidenced.

## Decision impact

Approval authorizes only the software interface and isolated test fixtures
specified here. The numerical test-only freshness values, encrypted USB
envelope, TEST_ONLY key-purpose separation, UDP signed-time carrier and
TLS authority-refresh response are all parts of the same proposed contract and
must be accepted together or changed explicitly. Approval does not lock
commercial security architecture, alter `CONTEXT_VERSION`, satisfy physical
GS-40 acceptance, resolve Hub migration, change P0 `product_status=PARTIAL`, or
close GS-109/GS-148/GS-68 production gates.

## Source checkpoint and evidence

The provider/runtime gap and already completed host results are recorded in
[`GS40_TEST_ONLY_RUNTIME_COMPOSITION_20261018.md`](GS40_TEST_ONLY_RUNTIME_COMPOSITION_20261018.md)
and Jira GS-40 comment 11371, GS-109 comment 11372 and GS-148 comment 11373.
At source checkpoint `f8dc5ca`, S3 product startup still selects
`UnprovisionedS3CloudTrust`; prior provider and localhost E2E results are host
evidence only. No new source tests, firmware build, hardware, production
service, credential or endpoint were used to create this proposal.
