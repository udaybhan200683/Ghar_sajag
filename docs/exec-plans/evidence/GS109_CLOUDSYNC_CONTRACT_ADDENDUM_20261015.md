# GS-109 / GS-148 CloudSync Contract Addendum

**Date:** 2026-10-15
**Status:** Technical recommendations only — all new values and choices are `PROPOSED_NOT_APPROVED` unless explicitly marked otherwise.
**Starting canonical checkpoint:** `3ddfabdb6d5ce1d33ea20dfc60714e8722a29493`, branch `feature/r1-commercial-baseline`; local and origin matched; context preflight PASS (`2026-10-13.001`).
**Inputs:** GS-68 comment 11014; GS-109 comments 11012 and 11015; GS-148 comments 11013 and 11016; the existing [CloudSync decision package](GS109_GS148_CLOUDSYNC_DECISION_PACKAGE_20261015.md); GS-109 audit/register; current GS-148 source and accepted GS-D032 invariants.

This addendum supplies the technical detail requested in the latest GS-68/109/148 work orders. It supersedes the earlier D05 suggestion that reuse of the registered P-256 identity is the default conditional path: current source and target evidence do not establish production-protected, non-exportable P-256 custody. The addendum does not approve an algorithm, credential, root, wire format, numeric limit, hardware change or commercial sending.

## Evidence classification and actual S3 feasibility

| Finding | Evidence class | What is established |
|---|---|---|
| ESP32-S3 has a Digital Signature path | `SDK_CAPABILITY` | ESP-IDF 6.0 documents RSA signing through DS, with encrypted RSA parameters in flash and an HMAC key in eFuse. The DS operation keeps the HMAC/private RSA parameters out of software during signing. RSA lengths include 2048, 3072 and 4096 bits. ESP-TLS accepts `ds_data`; the ESP-IDF documentation describes DS-backed TLS mutual authentication. This is a feasible silicon/SDK option, not a provisioned product identity. |
| Current P-256 fixture key | `TEST_FIXTURE` | `code/firmware/common/security/target_identity_signer.cpp:21-72,90-107` generates a P-256 private scalar with `PSA_KEY_USAGE_EXPORT`, exports it, and stores the scalar in NVS namespace `gs_dev_ident`, key `private_p256`, in HIL/commissioning builds. This explicitly is not production custody. |
| Current production P-256 source path | `SOURCE_DESIGNED_ONLY` | `target_identity_signer.cpp:109-129` requires Secure Boot and Flash Encryption macros, then checks P-256/256-bit/ECDSA-SHA256, sign-hash usage and nonvolatile PSA lifetime. It does not reject `PSA_KEY_USAGE_EXPORT`, identify a hardware-backed PSA driver/location, demonstrate PSA storage encryption, or show production key provisioning. The source comment itself says persistent PSA storage alone is not evidence of protected storage. |
| Current C8 diagnostic S3 build configuration | `TEST_FIXTURE` | The inspected artifact `code/build/gs114_fixture_pair/build-dcp0j4h_/s3/config/sdkconfig.json` has `SECURE_BOOT=false`, `SECURE_FLASH_ENC_ENABLED=false`, `NVS_ENCRYPTION=false`, `ESP_TLS_USE_DS_PERIPHERAL=true`, and `MBEDTLS_SECURE_ELEMENT_DRIVER_ENABLED=false`. This proves only that this diagnostic build has DS capability compiled and those protections/secure-element driver disabled. It is not a commercial profile or readout of chip eFuses. |
| Current target CloudSync authentication | `SOURCE_DESIGNED_ONLY` | `HttpsBackendChannel` verifies the server CA/hostname and sends caller-supplied opaque `Authorization`; it has no client certificate/DS signer integration. The S3 target does not instantiate the CloudSync worker. The SDK header supports `ds_data`, but no product caller supplies it. |
| Physical eFuse/security state and production signer custody | `UNVERIFIED / UNDEFINED` | No device/eFuse inspection was performed or authorized. No production factory key-provisioning, HSM custody, certificate issuer, external secure-element BOM, rework process or recovery evidence was found in this source audit. |

The primary SDK references are [ESP-IDF v6.0 ESP32-S3 Digital Signature](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/api-reference/peripherals/ds.html) and [ESP-IDF ESP32-S3 Security Overview](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/security/security.html). Espressif documents Secure Boot, unique per-device Flash Encryption, debug/download controls, NVS Encryption and OTA rollback/anti-rollback as parts of a production security design; none is inferred from the C8 diagnostic build.

## D12 — proposed production key-custody contract

**Recommendation (`PROPOSED_NOT_APPROVED`):** For the locked ESP32-S3 N16R8 product direction, evaluate a dedicated per-Hub RSA-3072 client key through ESP32-S3 DS and TLS mutual authentication as the first feasibility candidate. Use a unique eFuse HMAC key per Hub, read-protected and usable by the DS peripheral only; keep the DS-encrypted RSA parameters in the supported secure-certificate storage flow. Generate/provision the client identity through a controlled factory service/HSM process; no reusable fleet private key. Keep this cloud identity separate from the commissioning P-256 identity. Proceed only if the backend verifier/issuer accepts the profile and the production line can protect, audit, revoke and recover each unit.

RSA-3072 is a proposal because it is in the S3 DS size set and gives a concrete certificate profile for backend review; target handshake cost, RAM and server compatibility must be measured. The exact TLS version/signature-scheme profile and whether the pinned ESP-IDF 6.0.3 client path accepts this DS profile must be proven in a non-production integration build before D12 is locked.

| Alternative | Benefits | Risks / dependencies | Recommendation |
|---|---|---|---|
| Dedicated RSA-3072 + S3 DS/eFuse HMAC | No added secure-element BOM; hardware-backed RSA signing is documented on S3; ESP-TLS has DS support. | Irreversible per-unit HMAC eFuse provisioning; factory/HSM and unique-key controls; secure boot/flash policy, certificate issuance/renewal/revocation and rework/replacement process; RSA handshake resource cost. | Preferred candidate for S3 if backend and manufacturing owners approve and qualification passes. |
| Dedicated P-256 key in an external secure element | Preserves ECDSA P-256; key can remain in the part; separate cloud purpose. | No such part is identified on the current fixture/product BOM; requires selected component, bus/pin, driver, provisioning, board revision, supply and tamper/rework analysis. | Preferred fallback only if P-256 is a product/backend requirement. Hardware/BOM owner must select the part. |
| P-256 key in PSA/flash/NVS with Secure Boot + Flash Encryption | Small certificate/signature and avoids new part. | At-rest flash protections do not prove runtime non-exportability; compromised authorized firmware may call the signer; current source fails to disallow export usage or prove hardware location; key lifecycle/recovery undefined. | Does not meet the proposed strong device-impersonation threat model without explicit security-owner acceptance of residual risk. Not the default. |
| Reuse the commissioning P-256 identity for CloudSync | No second identity to provision. | No protected-key evidence; fixture path exports it; shared use creates cross-purpose coupling and a potential signing oracle; separate revocation/lifetime and backend scopes are unclear. | Reject as current recommendation. Reconsider only with verified non-exportability, a narrowly scoped API, and explicit approval to share purposes. |

**Minimum D12 contract if RSA-DS is selected:**

1. Threat model explicitly covers possession, flash extraction/cloning, malicious or rolled-back firmware, debug/download access, compromised backend credentials, factory/rework access, unit replacement and key revocation.
2. One unique Hub key/certificate per physical Hub. The registry binds certificate fingerprint/key ID to the permanent Hub ID. A Home or installation epoch is mutable registry data and is not encoded as trusted solely from certificate subject fields.
3. Factory private material is generated in or imported through an approved HSM-controlled procedure, never retained as plaintext on a general build host, checked into the repository, or emitted to logs. Each device receives a unique DS HMAC eFuse key with the DS HMAC key purpose, read-protected and associated encrypted RSA parameters; factory verifies the key/cert pair and destroys plaintext inputs according to an audited ceremony.
4. Production firmware profile requires Secure Boot v2, per-device Flash Encryption Release Mode, protected NVS for credentials/configuration that use NVS, signed OTA, and approved debug/ROM-download policy. DS data may use its documented encrypted parameter format, but this does not replace the wider flash policy. D15 must specify the rollback image/version policy; a firmware/NVS counter is not accepted as hardware anti-rollback evidence by itself.
5. Credential revocation takes effect at the backend verifier before accepting a new event effect. Expiry/renewal is governed by D06. Lost/reworked devices are revoked; reset does not regenerate identity or transfer Home ownership. Recovery is service replacement/rebinding under an authenticated owner/factory authorization path, preserving old event provenance.
6. Signer API accepts only TLS client-auth operations for the cloud certificate/key ID; no arbitrary digest/sign operation is exposed to CloudSync or application callers. Commissioning and CloudSync identities remain separate.

**Security risks:** eFuse misprovisioning is irreversible and can strand a unit; shared factory secrets can clone a fleet; plaintext provisioning material can escape; missing revocation/rework records can leave a stolen Hub valid; rollback can restore a revoked signer. Secure Boot/Flash Encryption introduce their own OTA/service constraints and require a tested recovery plan. No such operation is in this scope.

**Acceptance evidence before D12 approval:** production BOM/SoC revision and provisioning flow; signed security profile; factory HSM and key-disposal procedure; test-device proof that exported flash cannot yield the private key and that DS signs only with the per-device HMAC slot; rejection of a cloned image/key on another Hub; JTAG/download/rework/recovery drill; signed OTA/rollback compatibility; key rotation/revocation drill; target handshake latency/heap measurements; and security-owner threat-model sign-off. A simulator or the current R&D board cannot establish these physical claims.

**Exact approval requested:** GS-68/security owner selects D12 threat scope and either (A) RSA-3072 S3 DS/mTLS candidate subject to target/factory proof, (B) a named external P-256 secure element and board/BOM change, or (C) a documented lower assurance threat model for software P-256. Approve production boot/storage/debug/rework/rollback requirements and identify security, factory and hardware approvers. This proposal does not provision any key or authorize any fuse operation.

## D05 — proposed Hub authentication contract, conditional on D12

**Recommendation (`PROPOSED_NOT_APPROVED`):** Use TLS mutual authentication with the D12-selected, dedicated cloud key. For the current leading RSA-DS candidate, use the Hub's RSA-3072 client certificate and S3 DS-backed signer through ESP-TLS/ESP HTTP Client. Backend authenticates the certificate chain to its issuing CA, maps its fingerprint/key ID to the permanent Hub ID, checks current registry status/revocation, and derives current Home and installation epoch from the ownership registry. The Hub continues validating server CA and hostname. No static bearer `Authorization` value is an identity proof.

The TLS client certificate proves the Hub possesses its key for that connection. It does not establish Home ownership by itself: every event request must carry the D03/D07 provenance and the backend must compare it with the registry inside the durable commit transaction. D11 then binds the receipt to the exact request. Do not add a custom nonce/signature layer if the approved mTLS profile and exact-event idempotency already meet the threat model. If D12 selects external P-256, use its client-auth signer instead, subject to the same backend mapping and proof tests.

| Interface | Proposed contract |
|---|---|
| TLS client | Proposed baseline: TLS 1.2 with the RSA-3072 client certificate and SHA-256 CertificateVerify profile accepted by the pinned IDF 6.0.3 and backend. TLS 1.3 is allowed only after the exact RSA-PSS/DS signer path is demonstrated; the documented `esp_ds_rsa_sign` output is PKCS#1 v1.5, so do not assume TLS 1.3 compatibility. Verify server chain, SAN/hostname, validity time and configured trust bundle. Present per-device client certificate; private key stays in DS/secure element. Redirects disabled. |
| Device identity | `client_cert_fingerprint`/key ID resolves to one permanent `hub_device_id`; certificate subject strings are informational only. Unknown, expired, revoked or wrong-purpose cert fails closed. |
| Ownership | Backend registry provides current `home_id` and `installation_epoch`; request fields are claims to compare, never authority. Binding change during a transaction prevents a new effect. |
| Request | HTTPS POST carries original EventKey, immutable event timestamp/body/schema digest, permanent Node identity and original enrollment generation, plus Hub/Home/epoch and protocol version. D11 defines digest and receipt fields below. |
| Failure | On unknown/revoked certificate, TLS validation/time failure, registry unavailability or mismatch, do not submit/complete CloudSync. Retain local durable outbox, continue local sensing/admission and retry only under bounded D16 policy. |

**Alternatives:** request-level proof using a fresh server challenge and restricted signer gives application-layer binding but needs nonce issue/consumption, canonicalization and time rules; it remains the fallback if mTLS cannot be terminated safely. A static API key/token is rejected because it is cloneable bearer material and cannot prove current Hub ownership. A signed QR or MAC/serial is not Hub authentication.

**Validation:** correct cert and current binding; wrong Hub cert/key, wrong audience/purpose, revoked/expired cert, wrong Home/epoch, server CA/SAN/time failure, TLS version mismatch, endpoint redirect, loss/retry, concurrent revoke/rebind, no secret logs, and local queue survival for all cloud failures. Target mTLS handshake and revocation behavior require future approved test fixtures.

**Exact approval requested:** GS-68/GS-109/GS-148 choose mTLS with dedicated RSA-DS or external P-256; set accepted TLS versions/signature profile and issuer/verifier owner; approve registry binding and revocation semantics, trust-bundle ownership/rotation, and confirm no app challenge is required. D12 approval is prerequisite. No credential is issued here.

## D03 / D04 / D07 / D11 — concrete proposal schemas and transitions

The fields below are `PROPOSED_NOT_APPROVED`; they are not current wire/storage contracts. UTF-8 strings use bounded canonical encoding; numeric fields are unsigned, network-order integers. Unknown security-critical version/field values fail closed. Hashes are SHA-256. Exact JSON canonicalization/CBOR selection is a D11 owner choice; until selected, no wire parser change is authorized.

### D03 binding manifest v1

Proposed canonical signed object:

```text
manifest_version: 1
audience: "ghar-sajag-hub-binding"
issuer_key_id: <selected D12/D05 authority key id>
hub_device_id: <permanent physical Hub identity>
hub_key_id: <D05 client certificate fingerprint/key id>
home_id: <backend Home identity>
installation_epoch: uint64, backend-monotonic; increment on authorized rebind
binding_revision: uint64, backend-monotonic within the epoch
registry_status: ACTIVE | REVOKED
issued_at: UTC seconds
validity: D06-approved lease/expiry representation
schema_version: 1
manifest_digest: SHA256(canonical fields excluding digest/signature)
signature: <selected D12/D05 authority signature>
```

Issuance flow: authenticated owner action (GS-76 identity) and Hub possession proof → registry checks current ownership → registry reserves/advances epoch → issuer returns manifest → Hub verifies issuer/audience/Hub key/digest/version and anti-rollback revision → Hub stages and atomically activates it → backend confirms active binding. Reboot reads and verifies the last complete manifest. Missing, corrupt, stale, unknown-key, lower-revision or mismatched manifests enter `CLOUD_AUTHORITY_RECOVERY_REQUIRED`; never create a Home, reset an epoch, or erase outbox data to recover. Rebind is an explicit owner/factory-authorized operation with old data disposition under D10/GS-D032.

**D06 coupling:** lifetime/lease duration and offline validity are not selected here. If owner policy requires online revocation freshness, the backend remains authoritative on each commit; the manifest cannot permit an expired/revoked binding. Until a trusted clock/lease contract exists, do not infer time validity from the Hub wall clock.

**D04 public QR / claim proposal:** QR contains only `format_version`, public `device_lookup_id` (at least 128 random bits), and checksum. It contains no cloud credential, private proof or Home assignment. Claim requires authenticated owner (GS-76 OIDC contract) + explicit Home selection/consent + fresh D05 Hub proof and backend registry availability. Do not require a separate installer secret for R1 if those proofs are available. If an installer proof is retained by product choice, proposed minimum is 128 bits random, single-use, claim-scoped, server-side hashed, 15-minute validity, at most five failed attempts per device per 15-minute window, atomic consume, and revocable on return/rework; these numeric limits are `PROPOSED_NOT_APPROVED`. QR scan alone never claims ownership.

### D07 Node generation reservation state machine

Proposed allocator is backend-global and monotonically increasing per permanent Node ID, `uint64`; gaps are permitted and values are never reused. Proposed API:

```text
ReserveNodeEnrollment(
  idempotency_key, permanent_node_id, target_home_id,
  permanent_hub_id, installation_epoch, authenticated_owner_id
) -> reservation_id, enrollment_generation, expires_at, state=RESERVED
ActivateNodeEnrollment(reservation_id, node_possession_proof) -> state=ACTIVE
Abort/expire reservation -> state=ABORTED (generation remains consumed)
Revoke active enrollment -> state=REVOKED (never reuse generation)
```

The same idempotency key and identical request returns the same reservation; same key with changed fields is a conflict. Proposed reservation validity is 15 minutes, `PROPOSED_NOT_APPROVED`, aligned with the D04 installer flow. Activation is one-time and binds exact Node/Home/Hub/epoch/generation. Before an event is admitted locally, the exact active generation must be durably recorded in original-owner provenance; EventKey, original timestamp and generation are immutable on retry. Missing/corrupt mapping blocks CloudSync. At generation exhaustion, stop new enrollment and require authenticated service recovery; never wrap. A revoked generation cannot create new backend effects. An exact already-durable event may only receive idempotent duplicate treatment under its original exact provenance/domain, per accepted GS-D032 rules.

Validation: duplicate reservation/reply loss, concurrent reserves, changed-body idempotency conflict, crash between reserve/activate, abort then reserve (generation gap), stale/revoked generation, overflow and retry across Hub reboot/rebind; one logical backend effect and unchanged original EventKey/time/generation.

### D11 event request and COMMITTED receipt v1

Proposed request carries:

```text
protocol_version=1
event_key
event_timestamp_utc
event_schema_version
event_body (original immutable payload)
event_body_digest = SHA256(exact canonical event-body bytes)
node_id (permanent)
node_enrollment_generation (original admission generation)
hub_device_id (permanent)
home_id
installation_epoch
binding_revision
```

`request_digest = SHA256(exact canonical request bytes including all fields above)`. Proposed canonical encoding is UTF-8 JSON with the field order shown in the schema above, no insignificant whitespace, integer-only identity/time fields, and duplicate-key rejection; both sides hash the exact transmitted octets, and a retry must reproduce the same bytes. The backend validates TLS client principal, active Home/Hub/epoch, active Node generation and event ownership in the same transaction that writes the immutable event and logical effects. The EventKey is the idempotency key. New event/effects and the COMMITTED result become visible atomically; the response is sent after database commit.

Proposed response:

```text
receipt_version=1
status="COMMITTED"
event_key
request_digest
event_body_digest
node_id, node_enrollment_generation
hub_device_id, home_id, installation_epoch, binding_revision
backend_transaction_id
committed_at_utc
duplicate: true | false
```

The approved D05 authenticated TLS response is the receipt authenticator; no independent receipt signature is proposed for the online Hub completion path. `duplicate=true` is valid only for an exact immutable request/domain match to a prior durable transaction. Same EventKey with different timestamp/body/provenance returns conflict and no receipt. `HttpBackendTransport` must compare every request-bound field; truncation, unknown receipt version, missing field, wrong domain/digest, generic HTTP 2xx, HTTP 202, unauthenticated response or response after rollback is not completion. If offline/portable receipt verification becomes a requirement, it is a separate D11 alternative with backend signing-key lifecycle approval.

Validation: fresh commit, exact duplicate, response loss then byte-identical retry, duplicate across backend/Hub reboot, altered body/timestamp/schema/key/Node generation/Home/Hub/epoch/revision, wrong TLS principal, revoke/rebind race, DB rollback before commit, post-commit HTTP loss, malformed/truncated/unknown receipt and caregiver-projection idempotence. Verify one durable effect and Hub local completion only on exact valid receipt.

## D06 — measurable credential/time proposals

All values are `PROPOSED_NOT_APPROVED` and depend on D05/D12/D15:

| Parameter | Proposed value | Reason / fail-closed rule |
|---|---:|---|
| Hub client certificate lifetime | 90 days | Limits exposure of a stolen device credential while leaving an operational rotation window. Backend checks expiry/revocation using its trusted clock on every new authenticated connection/commit. |
| Renewal start | At 14 days remaining | 14 days is 4.7× the GS-D025 72-hour internet-only design target; renewal begins early enough to cover a multi-day outage. No guarantee is inferred for powered-off Hub or arbitrary outage. |
| Old/new certificate overlap | Maximum 24 hours | Allows staged rotation but limits two-key acceptance; backend registry pins both fingerprints only during the approved overlap, then revokes the old one. |
| Clock uncertainty tolerance | Maximum ±120 seconds | Candidate tolerance for validity-boundary comparison only; never extends backend certificate expiry by more than this. Secure source must measure ≤±60 seconds to leave half the budget for transport/RTC drift. |
| Application challenge, if D05 does not use mTLS-only | 60 seconds, one use, server-issued, audience/request-bound | Keeps request-proof replay window short. Challenge is measured by backend monotonic time; Hub reboot discards local challenge state. Under recommended mTLS-only, do not add this challenge. |
| Trusted-time gate | No authenticated server time → no CloudSync | Unauthenticated SNTP may be a hint but cannot authorize server or client certificate validity. A production first-boot/bootstrap source is unresolved: prefer a qualified trusted RTC or a separately pinned/signed time bootstrap anchored in the D05/D12 authority; owner/security must select and qualify one. |
| Renewal retries | Existing D16 bounded 1/5/30/120/300-second backoff while connected; retry from notification/connectivity recovery | No credential or event is dropped. At expiry, pause CloudSync and retain the durable outbox; local safety behavior continues. |

At first boot and after time loss/rollback, CloudSync must not disable TLS date checks or accept an expired credential. The trusted-time bootstrap must verify a signed response under the already-approved trust chain and bind a fresh nonce/device identity; it must not introduce an unreviewed root or an unauthenticated clock bypass. If neither RTC nor a secure bootstrap is selected, this is a production blocker, not permission to ignore certificate dates.

Validation boundaries: exact `notBefore`, expiry−1/expiry/expiry+1, ±120s and beyond, 14-day renewal, old/new overlap start/end, revocation during request, time rollback/reboot, stale bootstrap nonce, incorrect signer/root, no WAN beyond 72h, recovery after WAN returns, and local event retention while cloud is paused. Backend and target clocks are tested independently.

## D15 — version and rollback compatibility proposal

Proposed pre-activation contract set:

| Contract | Initial proposed version | Compatibility rule |
|---|---:|---|
| Binding manifest | 1 | Strict signature/audience/identity/revision checks; unknown version fails closed and bytes remain preserved. |
| Node generation reservation/mapping | 1 | Backend allocator is authoritative; persisted local mapping is immutable per admitted event; no generation reuse or wrap. |
| Cloud event request / receipt | 1 | Explicit request and receipt versions; only the proposed exact v1 pair can complete; legacy exact-key-only receipt does not silently satisfy new D11 fields. |
| Credential profile | 1 | Dedicated D05 identity only; commissioning key is not implicitly accepted as a CloudSync credential. |
| S3 image/storage writer | Product release manifest must declare min-reader/max-writer and persistent-schema capabilities | Only signed images tested against the same or newer persistent records may be in the supported rollback set. |

No commercial schema has been deployed, and the currently present R&D images are not evidence of supported commercial readers. Before a production rollout, inventory every allowed signed S3 image and require each rollback candidate to read all already-committed persistent schemas, preserve queued event provenance and honor current credential/revocation rules. Candidate OTA must be marked valid only after schema mount/reconciliation and a successful authenticated backend round trip; do not write an incompatible schema before that check. If an older signed app cannot read data written by the candidate, block rollback or defer the schema write; do not erase/format to recover.

Security anti-rollback cannot be claimed from an NVS version alone if whole-flash rollback can restore it. D12 must decide Secure Boot/anti-rollback fuse policy, and all one-way hardware/security operations require a separate approved manufacturing plan. Rollback tests include interrupted dual-slot manifest write, old/new reader matrix, backend old/new compatibility, exact queued retry across OTA rollback, revoked credential after downgrade, unknown schema, corrupt/torn data and migration failure. Preserve the existing Hub migration `FAIL` as an independent blocker.

**Exact approval requested:** GS-68/109/148 select the supported image set, contract versions, minimum reader/writer policy, OTA mark-valid checkpoint, rollback ceiling, security-version/eFuse policy and migration/recovery steps. Until approved, no D03/D07/D11 schema is a product contract.

## D16 — measurable single-owner and resource proposal

### Existing source limits (not yet S3 runtime policy)

`CloudSync::kMaximumBatch=16`, `kMaximumRetryEntries=64`; `CloudSyncWorker::run_once()` defaults to 4 events per pass. `HttpBackendTransport` caps one request at 2048 bytes and one response at 1024 bytes. Cloud retry backoff is 1s, 5s, 30s, 120s, then capped at 300s. The existing S3 HTTP channel uses 1KiB RX/TX buffers and `timeout_ms=3000`, plus a 5-second soft deadline checked between operations. A blocking ESP HTTP call can overrun that soft deadline, so it is not an end-to-end hard bound. These are code limits, not measured production budgets. The worker has no target instantiation yet.

### Proposed S3 runtime limits — all `PROPOSED_NOT_APPROVED`

| Resource/behavior | Proposed bound | Evidence/rationale and acceptance |
|---|---:|---|
| Network/radio owner | One `HubNetworkOwner`; one CloudSync worker; at most 1 TLS/HTTP request in flight | One S3 Wi-Fi radio is shared with ESP-NOW; no second Wi-Fi client or cloud-owned channel changes. All association/channel changes route through the single owner. No storage/ownership lock across network I/O. |
| Worker mailbox | One coalescing wake slot; durable outbox is the work queue | Notifications may coalesce; after wake, rescan durable queue. No volatile event backlog or dropped event on mailbox full. |
| Worker slice | At most 4 event requests per pass, one event per HTTP request; yield/check ESP-NOW work between requests | Matches current worker default 4 and caps synchronous work below `kMaximumBatch=16`. Urgent local admission/ACK always preempts CloudSync. |
| Payload caps | Request ≤2048 bytes; response ≤1024 bytes | Preserve current parser caps. Oversize/malformed data pauses/rejects cloud completion and leaves the original record durable. |
| Trigger/poll | Durable-commit notification starts sync within 1s while online; 5s maximum online fallback rescan; no faster than 30s periodic check while offline | Near-real-time path without busy polling; connectivity changes wake immediately. Measure from Hub durable commit to worker start. |
| Per-request wall deadline | 8s absolute from connect start through TLS, write, full response and close; each individual blocking phase ≤3s and shares the same absolute deadline | Replaces current 3s per-call/5s soft check only after transport supports interruption/deadline propagation. A timeout is a retry, never a receipt. Must prove measured wall time ≤8s on target. |
| Retry | 1s, 5s, 30s, 120s, 300s maximum delay | Reuses source schedule. Backoff affects only CloudSync; local Node/Hub ACK path and durable admission remain live. Keep per-event hints bounded at 64; hint eviction cannot evict the durable event. |
| Worker task stack | 16KiB allocated; maintain ≥4KiB high-water free in worst TLS/JSON case | Initial qualification target only; gather FreeRTOS high-water mark across connect, TLS failure, maximum request and response, DS signer, reconnect and cancellation. |
| Dynamic network memory | ≤96KiB incremental peak per transaction across internal RAM + PSRAM; before TLS start require ≥128KiB free allocatable total and ≥32KiB largest contiguous internal block; after cleanup retain ≥32KiB internal free | Initial measurable admission ceiling, not proof that current build satisfies it. If a guard fails, defer CloudSync attempt and retain data. Measure both heaps/high-water under production crypto/profile. Do not borrow the ESP-NOW safety reserve. |
| Bounded diagnostic audit | 64 summaries × 96 bytes = 6KiB; retain outcome/time/reason and an 8-byte keyed EventKey digest only | RAM ring may evict oldest diagnostics; it never owns correctness state. No payload, Home/Node IDs, certificates, tokens, nonces or private material in logs. No unbounded persistent audit writes. |
| Connected-event target | Worker start ≤1s; Hub-durable-commit to backend COMMITTED ≤10s p95 for one event on stable WAN; 192-event backlog recovery ≤30min when service is available | Proposed cloud SLO, distinct from GS-46 local motion-to-Hub latency. With a hard 8s/request, 192 sequential requests need ≤25.6min pure request time; 30min leaves 4.4min for scheduling/overhead. Qualify normal/high profile and burst; service outages are reported separately, not counted as latency passes. |

### Six-Node workload basis and limits of derivation

The existing GS-148 review's 72-hour candidate trace has NORMAL `728 exact + 197 candidate summaries = 925 rows` (12.85/hour) and HIGH `3278 exact + 298 candidate summaries = 3576 rows` (49.67/hour, about `0.0138 rows/second`). It also proposes a six-Node simultaneous 32-event backlog: `6 × 32 = 192` events. These are existing modeled/qualification inputs, not approved contractual event rates or physical measurements. The six-Node HIGH average is comfortably below the proposed one-request/8s ceiling (450 requests/hour), but burst service and target RF/channel coexistence still need HIL. The separately modeled STRESS trace is not selected as the supported commercial rate here.

GS-46 requires a defined first-event latency but its current Jira/evidence catalogue has no numeric maximum; GS-69 requires a 12-hour soak but does not state an event rate or CloudSync SLO. Therefore these sources cannot yield an approved numeric bound. The proposed ≤10s CloudSync p95 is a new owner choice and must not replace or weaken GS-46 local wake/admission/ACK limits. GS-69 soak remains a separate 12-hour physical acceptance with event profile supplied by its owner. No target latency, heap, RF or throughput measurement was performed for this addendum.

**Validation needed after D16 approval:** local production-code tests for mailbox coalescing/full, four-request slices, retry/backoff and durable-event retention; Hub/API request maximum and timeout/receipt error tests; S3 target build and stack/heap accounting; slow connect/TLS/read/cancel and WAN flap; six-node HIGH trace and 192-event burst drain; priority/fairness under concurrent ESP-NOW events; no queue/audit leaks over GS-69 soak; and separately authorized S3 RF/channel HIL. The current host-injected worker tests do not validate those target properties.

## Dependency/approval order and remaining blockers

1. **GS-68/security + hardware/factory:** decide D12 threat model and RSA-DS vs named secure element; approve manufacturing custody, boot/storage/debug/rollback requirements and proof of production feasibility.
2. **GS-68/GS-109/GS-148:** on the selected D12 path, decide D05 TLS/mTLS profile, issuer/verifier, registry fingerprint mapping, root/certificate rotation and revocation; confirm whether request challenge is omitted under mTLS.
3. **GS-109/GS-76:** approve D03 manifest/claim authority and D04 public QR/owner proof; GS-76's production OIDC actor contract remains a dependency.
4. **GS-109/GS-148/GS-137:** approve D07 allocator state/width and D11 exact request/receipt v1 fields and durable transaction semantics.
5. **GS-68/GS-109/GS-148:** approve D06 TTL/skew/renewal/trusted-time source and D15 supported images/schema/anti-rollback matrix.
6. **GS-109/GS-148/GS-76:** approve D16 worker, limits and cloud SLO; then implement/register target coordinator and run tests/HIL before considering commercial sending.

Actual blockers remain: no approved production signer/custody or manufacturing process; no selected trust-root/issuer/verifier; no trusted first-boot time source; no approved generation reservation or exact wire/receipt v1 contract; no production supported-image/rollback matrix; no S3 target worker/network-owner implementation or qualified D16 measurements; production owner actor/OIDC dependency; and no authorization to issue credentials or activate sending. Product P0 `PARTIAL` and historical Hub journal migration `FAIL` remain separate release blockers.

## Approval table for owner disposition

| Decision | Recommended option | Required disposition before implementation |
|---|---|---|
| D12 / GS-68 | Dedicated RSA-3072 client identity via S3 DS/eFuse HMAC if factory/backend feasibility passes; otherwise select a named external P-256 secure element. Do not assume current PSA P-256 is protected. | Security owner + hardware/factory owner approve threat model, exact key path, secure boot/storage/debug/rework/rollback and evidence. |
| D05 | Dedicated-key TLS mTLS; registry maps cert fingerprint to permanent Hub, registry supplies Home/epoch. | Security/backend owners approve TLS/signature profile, issuer/verifier/root owner, revocation/rotation and no app nonce under mTLS. Depends on D12. |
| D03 / D04 | Backend-authoritative signed binding manifest; public registry QR; OIDC owner consent + Hub possession proof. | GS-109/GS-76/GS-68 approve exact fields, claim flow, time/lease, anti-rollback, reset/rework and recovery. |
| D06 | 90-day cert; renew with 14 days left; ≤24-hour overlap; ±120-second maximum tolerance; no CloudSync without trusted time; 60-second one-use challenge only if request-proof option chosen. | Security/product owners accept or replace values and choose trusted RTC vs pinned/signed time bootstrap. All numeric values remain proposals. |
| D07 | Backend-global monotonic `uint64` generation, idempotent reserve → activate; abort consumes value; never reuse/wrap. | GS-109/GS-148 approve exact API/state/persistence/exhaustion/old-event handling. Depends on D03/D15. |
| D11 | TLS-authenticated, exact request-bound COMMITTED receipt v1; `request_digest` and all identity/generation/epoch fields echoed; no detached signature for online path. | GS-109/GS-148/GS-137 approve encoding, fields, duplicate/conflict and compatibility. Depends on D05/D07/D15. |
| D15 | Versioned v1 manifest/generation/request/receipt; explicit minimum reader/writer and compatible signed rollback set; preserve bytes on unknown state. | GS-68/GS-109/GS-148 approve supported image matrix, rollback ceiling and anti-rollback policy. |
| D16 | Single network owner, one in-flight request, ≤4 events/pass, existing 2KiB/1KiB payload caps and capped retry; proposed 8s hard request, 16KiB stack, 96KiB transaction peak, 64×96B audit, ≤10s p95 single event and ≤30min 192-event catch-up. | GS-109/GS-148/GS-76 accept/replace numeric budgets and channel model; GS-46 owner supplies local-latency bound; target/RF/soak measurements required before release. |

**Execution status:** source review and documentation only. No code, credential, trust root, hardware, eFuse, firmware, security setting, Jira workflow or release gate changed. No tests were rerun. Existing GS-148 host receipts remain reusable because implementation/source was unchanged. Historical migration `FAIL`, P0 `PARTIAL`, and GS-114 physical evidence remain unchanged.
