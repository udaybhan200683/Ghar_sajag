# GS-109 / GS-148 Production CloudSync Security Decision Package

**Date:** 2026-10-15
**Status:** Proposal for owner/security approval — **no new decision is approved by this document**
**Repository checkpoint:** `bb2b77cb26ac88aaea244b7d1f73b124d18f6a3f`, branch `feature/r1-commercial-baseline`; local and `origin` matched at preparation. Context preflight PASS (`2026-10-13.001`).
**Related Jira:** [GS-109](https://udaybhan200683.atlassian.net/browse/GS-109), [GS-148](https://udaybhan200683.atlassian.net/browse/GS-148), GS-109 comments 10595 (existing independent design review), 10601 (D01–D16 register), 11008 (this proposal), and GS-148 comments 11007 (CloudSync checkpoint), 11009 (cross-reference).

## Owner approval record — requested, pending

Prepared for the GS-117 Morning Routine configuration path at canonical
checkpoint `f3223a1a687c9c3729a3ad3b5960e620b9039622`. This is a decision
request, not an approval or credential/hardware authorization. The detailed
D01–D16 register and 2026-10-28 configuration delta below remain the technical
rationale.

### A. Product-security architecture disposition

Approve the proposed direction, select an alternative, or defer each row. An
architecture disposition authorizes only implementation of the agreed
interfaces and contracts; it does not authorize issuing credentials or
operating a board.

| Decision | Proposed direction for approval | Still to decide |
|---|---|---|
| Hub identity | Reuse the GS-68/GS-109/GS-148 RSA-3072 DS-backed client-certificate/mTLS candidate; resolve its verified fingerprint to the permanent Hub identity. | Confirm the identity and proof contract, issuer authority, key-custody profile dependency (GS-68 D12), trust-root ownership, and rotation/revocation/recovery rules. |
| Caregiver authority | Reuse GS-76 `HumanAuthenticationBoundary`; only a verified credential may create a server-owned, revocable `ActorSession`. | Approve issuer/audience and verification-key lifecycle, expiry/revocation source, Android handoff, and current Home-settings membership/role authority. |
| Home and epoch | Keep the existing backend Hub ownership registry as the sole current Hub → Home → installation-epoch authority. | Choose authenticated versioned binding manifest or online authority lookup; settle offline, stale/revoked, transfer and recovery behavior. |
| Trusted middleware | Prefer the application-owned mTLS verifier constructing `VerifiedHubContext`; allow a proxy only with a trusted, integrity-protected peer-identity handoff and strict header stripping. | Select TLS termination, verifier/runtime owner and deployment boundary. Caller-provided identity headers are not trusted. |
| Configuration apply | Use the existing versioned desired/applied repository; bind fetch and acknowledgement to Hub, Home, epoch, schema and version, and report applied only after durable S3 persistence. | Approve the exact fetch/ack payload, stale/revoke/rollback behavior and supported restart/offline persistence contract. |

**Owner/security response:** `APPROVE PROPOSED DIRECTION`, `SELECT ALTERNATIVE:
<contract>`, or `DEFER` for each row; record the approver, authority and date.
No response has yet been recorded here. Deferral keeps production Settings and
Hub configuration routes/transport disabled.

### B. Separate credential-provisioning approval

Architecture approval is not permission to create, sign, export, install,
replace or revoke a key/certificate; alter a trust root; enroll a Hub; or change
hardware security state. Before any such operation, obtain a separately scoped
provisioning authorization naming the exact issuer, Hub identity, artifacts,
target operation, custody and recovery procedure, and stop conditions. No
production credential is requested or issued by this record.

### C. Separate physical-operation approval

The first Bedroom-only Run requires its own current, bounded hardware approval
for the exact C3 `INJECT_MOTION` USB operation and its COM4 reset risk, plus
verified current C3/S3 image, JEDEC/capacity, enrollment, applied policy and
fresh authenticated S3 ingress. Any COM10 access or Hub reset requires separate
explicit scope. This is independent of (A), (B), and the five-run TC-001
campaign approval. No physical operation is authorized here.

## Purpose and disposition

This package closes the source-to-decision gap for activating the existing GS-148 CloudSync path. It reuses the GS-109 audit and D01–D16 register; it is not a second architecture review. The nine listed decisions remain open. Approval of a recommendation will authorize its contract definition only to the extent stated by the approver; it does not itself deploy credentials or turn on S3 sending.

At this checkpoint, the bounded `CloudSyncWorker` and its injected host path are implemented and the approved Hub validation has been completed. Target S3 does not instantiate that worker. The test-injected `CloudAuthoritySource` is not a production issuer or verifier. Commercial target sending must remain disabled until the authority, credential, receipt and runtime-coordination contracts below are approved and implemented.

**Technical refinement:** The linked [2026-10-15 contract addendum](GS109_CLOUDSYNC_CONTRACT_ADDENDUM_20261015.md) records the source-grounded D12 key-custody findings and provides measurable D06/D16 proposals plus exact D03/D04/D07/D11/D15 schemas. It supersedes the earlier conditional P-256-reuse recommendation as the default D05 path: protected, non-exportable P-256 is not demonstrated in the current source or diagnostic profile. All alternatives and values remain unapproved.

## Accepted invariants — not reopened here

- GS-D032 and the accepted GS-109 ownership policy distinguish permanent physical Hub identity, mutable Home binding and installation epoch, permanent Node identity, logical assignment, and Node enrollment generation.
- Hub/Home/epoch authorization and fresh proof of device possession are required. A MAC, serial, QR, factory reset, fixture command, caller-constructed `Verified*` object or development identity header is not production authorization.
- Original `EventKey`, event timestamp, original Node identity and the generation recorded when the event was admitted are immutable. Retries reuse the same event identity and provenance.
- The backend accepts a new logical effect only under current authorized ownership and generation. An exact already-durable event may be retried idempotently only under its original matching domain/provenance; conflicts fail closed.
- Hub local Durable ACK and backend COMMITTED are distinct. Backend COMMITTED follows the durable transaction. The Hub completes its local CloudSync record only after a valid response bound to that exact request. HTTP transport success alone is not a commit.
- Ownership transfer does not reassign old events or silently carry old Home Nodes/credentials into a new Home. Factory reset alone is not a transfer authorization. Old pending data requires an explicit disposition; do not wipe or reparent it by timeout.
- Local monitoring and durable event admission remain functional during WAN outage under current product behavior. Invalid, stale or missing cloud authority blocks cloud operations; it must not weaken local sensing, replay, authentication, ACK, storage or FOTA behavior.
- No eFuse/security operation, production credential, trust-root edit, hardware action, storage-format migration or commercial send activation is authorized by this package.

## Decision recommendations

### D03 — Installation incarnation and local Home binding

**Preferred solution.** Make the existing backend ownership registry authoritative for current permanent Hub identity → Home → installation epoch. Issue a versioned, authenticated installation-binding manifest through that same approved authority, anchored to the already selected Hub identity roots. The manifest is durable state for the Hub; it is not a second independently chosen trust root. Bind it to the physical Hub identity/key fingerprint, Home ID, epoch/incarnation, schema/key IDs, issuance and validity/revocation state, and anti-rollback version. On missing, corrupt, stale, conflicting or unsupported state enter an explicit recovery-required state and keep cloud sending off; never infer a new Home or erase state to recover.

**Alternatives and trade-offs.** Per-request backend lookup avoids a local signed manifest but requires online authority for each operation and still needs a safe offline event-owner mapping. A Hub-self-asserted Home/epoch is simpler but has no authority. A new independent NVS root duplicates trust and risks split-brain ownership. The recommendation favors one issuer and a durable authenticated representation while preserving offline event provenance.

**Risk if unresolved/wrong.** A stale or forged binding could route caregiver data across Homes, accept revoked Hub state, or strand original events after rebind/recovery.

**Interfaces.** Current `CloudAuthorityBinding`/`CloudAuthoritySource` is injected into the host worker only. Required production interfaces are an authority-verified binding provider in the S3 runtime, a versioned manifest codec/repository, and backend ownership-registry claim/transfer checks. Cloud request construction must use this trusted binding and recheck it around I/O; no caller-owned identity strings.

**Security requirements.** Authenticate issuer and Hub binding; anti-rollback; reject unknown versions/key IDs; bind all fields; do not log manifest secrets; transfer/revocation invalidates old cloud authority; recovery is separately authorized and audited.

**Validation criteria.** Verify fresh claim and reboot; wrong Hub/Home/epoch, altered signature, rollback, unknown schema, revoked key and partial write all fail closed. Exercise ownership transfer race during a request, preserve old pending event ownership, and prove no cross-Home backend effect. Power cuts at each manifest write/activation boundary recover to old valid state or recovery-required without erase/rebind.

**Exact approval requested.** GS-109/GS-148 owners approve: (1) backend ownership registry as sole current Home/epoch authority; (2) an authority-issued versioned binding manifest signed/authenticated through the selected Hub identity root; and (3) the field list, epoch/incarnation relation, aliases policy, offline validity, anti-rollback and recovery/rebind/reset behavior. GS-68 must confirm the issuer/root and protected-key dependency under D12. State any exception explicitly.

### D05 — Hub credential and proof of possession

**Preferred solution.** Conditional on D12 proving suitable protected key custody: use the already registered device-specific P-256 Hub identity through a restricted signer. Authenticate each CloudSync request with a fresh backend challenge and a canonical request proof covering method, path, body digest, permanent Hub identity, Home, epoch, audience, nonce and bounded validity. Backend verification maps the proof to the authoritative ownership registry; it does not trust request-supplied owner fields. If the existing identity key cannot meet the threat model or purpose separation, select a dedicated non-exportable cloud key instead.

**Alternatives and trade-offs.** Mutual TLS provides standard channel client authentication and revocation but requires certificate issuance, device provisioning, renewal and backend CA lifecycle; request-level domain proof may still be needed. A separate cloud-signing key isolates purposes but adds factory provisioning and rotation. Server-authenticated TLS with a static opaque Authorization string is not sufficient Hub authentication. The current recommendation avoids a new key only if D12 establishes that reuse is safe.

**Risk if unresolved/wrong.** A copied/static credential or replayable proof can impersonate a Hub; a broad signer can become a cross-purpose signing oracle; weak challenge binding can authorize another request or owner epoch.

**Interfaces.** `HttpsBackendChannel` currently verifies server TLS/hostname and accepts caller-supplied origin, CA and opaque Authorization; it has no client issuer/proof implementation. Required additions are a restricted signer interface, challenge/proof codec, backend middleware verifier, and binding to `ownership_registry.py`. Never expose private key material to the CloudSync worker or backend API caller.

**Security requirements.** Fresh unpredictable server nonce, one-time/replay-protected challenge, strict canonical encoding, fixed audience, request/body binding, current Home/epoch binding, key ID and revocation/rotation policy, server-authenticated TLS, bounded clock assumptions, no secret logging, fail closed if verification or time/nonce service fails.

**Validation criteria.** Positive proof for exact request; reject altered body/path/method, wrong Hub/Home/epoch/audience, expired or repeated nonce, wrong key, revoked key, malformed signature and signer policy escalation. Test rotation overlap/revocation, boot without trusted time, and no credential leakage in logs. Separately validate the production verifier and target signer; injected test capabilities are not evidence of deployment trust.

**Exact approval requested.** GS-68 + GS-109 + GS-148 choose one: (A) reuse the registered P-256 identity through a restricted request signer, conditional on D12, or (B) issue a dedicated non-exportable CloudSync key and certificate. Approve the proof protocol or mTLS profile, algorithm/encoding/canonicalization, trust root and verifier owner, audience, challenge/replay rules, rotation/revocation, and whether the same Hub key may serve commissioning and cloud purposes. No key is created by this proposal.

### D04 — Factory identity, QR and installer-code lifecycle (D05 prerequisite)

**Preferred solution.** QR is a public identifier/lookup handle that resolves only through an authenticated registry. Any installer proof is per-device, high entropy, securely delivered, one-use and narrowly scoped to an authorized commissioning claim with expiry/rate limits; it is not a Hub cloud credential. Fresh Hub possession proof under D05 remains mandatory. Never accept printed QR/code by itself as Home ownership or cloud authorization.

**Alternatives and trade-offs.** A signed QR can prove issuer origin offline but exposes a durable bearer artifact and needs signing-key rotation/recovery. A registry lookup gives revocation and less offline complexity but requires online manufacturing/onboarding availability. Reusable installer codes are operationally easier and have unacceptable replay/redistribution risk.

**Risk if unresolved/wrong.** Cloned packaging, code reuse or leaked factory records can claim devices or authorize an unintended Home.

**Interfaces.** No commercial factory issuer is present in the GS-148 path. Define factory provisioning/registry issuance, QR resolution and one-use proof consumption in the GS-109 onboarding service; connect to D03 ownership claim and D05 Hub proof. Keep the current test fixture API separate.

**Security requirements.** Per-device uniqueness, protected custody and access audit, one-use atomic consumption, expiry/rate limiting, revocation/rework/returns handling, no secret in QR/logs, proof-of-possession and actor authorization independent of device identifier.

**Validation criteria.** Reject forged/altered QR, wrong-device proof, replayed/expired/already-used code, concurrent duplicate claim, rate-limit bypass, revoked/reworked unit and wrong-Home actor. Verify manufacturing retry does not duplicate identity and secrets are excluded from output.

**Exact approval requested.** GS-68/GS-109 select signed QR or authenticated registry lookup (recommended), installer-code presence/absence and scope, generation and delivery/custody owner, one-use/expiry/reset/rework/compromise lifecycle, and whether R1 requires online claim. This decision does not authorize production issuance now.

### D06 — Credential expiry, clock, renewal and time budgets (D05 prerequisite)

**Preferred solution.** Let the backend's trusted clock decide credential/certificate/challenge validity. Use a fresh server nonce and a bounded monotonic Hub lease only for the lifetime of an in-flight operation. If secure time, nonce or renewal is unavailable, pause cloud requests; preserve local sensing and durable queue. Do not disable TLS certificate expiry checks or accept expired credentials to improve availability.

**Alternatives and trade-offs.** A provisioned trusted RTC/time source can support offline certificate checks but adds hardware/provisioning and rollback trust. Hub wall-clock-only validation is vulnerable to unset/rolled-back clocks. Pure online challenge validation is simpler but requires connectivity for every new proof.

**Risk if unresolved/wrong.** A clock rollback can revive expired/revoked authority; too-short validity can strand devices during outages; excessive validity increases compromise exposure.

**Interfaces.** Backend challenge/credential verifier and issuer, target secure-time/monotonic clock adapter, and `HttpsBackendChannel` certificate validation/timeout path. Current 3-second per-call timeout and 5-second soft deadline are transport behavior, not a credential TTL contract.

**Security requirements.** Explicit skew/TTL bounds, monotonic lease not persisted across reboot, TLS validity always enforced, nonce one-use, refresh overlap/revocation policy, no authorization from wall clock alone, safe bootstrap and audit.

**Validation criteria.** Expiry and skew boundaries, unset/rollback clock, reboot during lease, delayed response, nonce replay, renewal overlap/revocation, online recovery and prolonged offline operation. Assert local event durability remains available while cloud stays paused.

**Exact approval requested.** GS-68/GS-109/GS-148 set numeric credential/challenge TTL, accepted skew, renewal lead/overlap, nonce lifetime, rate limits and bootstrap-time source. Approve fail-closed cloud behavior when each time prerequisite is missing. Values must be explicitly supplied; none are inferred here.

### D07 — Backend-global Node generation and original-event mapping

**Preferred solution.** Backend transactionally reserves a monotonically increasing generation per permanent physical Node during authorized enrollment. Hub enrollment activation binds the reservation to the exact Home, Hub and local enrollment identity. At Node event admission, persist the immutable backend generation alongside the original local owner/event record; CloudSync sends that original mapping. Never derive a new generation on reconnect, reuse an aborted reservation, rewrite old event provenance or send when mapping is missing. Gaps from abandoned reservations are valid.

**Alternatives and trade-offs.** Hub-local slot generation is already useful locally but is not a globally unique authority across Hub/Home replacement. Backend assignment only at first CloudSync avoids provisioning changes but cannot safely distinguish old queued data from a replacement enrollment without immutable admission mapping. Rejecting every old generation would strand exact already-committed retries; existing backend policy permits exact matching durable replay only.

**Risk if unresolved/wrong.** Cross-Home or replacement Node data can be accepted as current; stale generations may create new effects; a generation rewrite destroys audit and retry identity.

**Interfaces.** Current `cloud_sync.cpp` reconstructs v2 original ownership/generation from the durable journal; `CloudAuthoritySource` gates current Home/Hub/epoch. Backend `ownership_registry.py` enforces active generation and exact durable replay. Missing approved pieces are an idempotent reservation/activation API, persistent local reservation-to-enrollment mapping, and write-time provenance capture that survives reboot and is consumed by CloudSync unchanged.

**Security requirements.** Allocation must be atomic/idempotent and authorized; generation cannot be caller-selected or reused; bind generation to permanent Node identity and Home/Hub epoch; retain immutable audit and old-event domain; overflow/exhaustion fails closed; old exact durable duplicates cannot authorize new events.

**Validation criteria.** Concurrent reservations; lost reservation response/retry; aborted gap; reboot between reserve/commission/activation; replacement/revocation; mapping corruption; generation exhaustion; old exact committed replay; old uncommitted event after revocation; wrong Home/Hub/epoch. Assert stable EventKey/time/generation and one logical effect.

**Exact approval requested.** GS-109/GS-148 approve backend as sole monotonic allocator, reserve-before-commission and activation semantics, idempotency key/state machine, generation width/exhaustion behavior, local mapping format/owner and abort/recovery behavior. GS-68 confirms any factory identity input. GS-D032 old-pending disposition still applies and is not overridden.

### D11 — Authenticated, request-bound durable COMMITTED receipt

**Preferred solution.** Use a response authenticated by the approved TLS/client-auth session and bound to the exact submitted request. Require COMMITTED only after backend durable transaction success. Bind the response to a canonical request digest plus complete original EventKey, payload/schema digest, Home, permanent Hub, epoch, permanent Node, original Node generation and commit/duplicate result. `HttpBackendTransport` must compare every field against the request before the local completion write. A detached signature is unnecessary unless receipts must be independently verified or retained outside the authenticated channel.

**Alternatives and trade-offs.** Current strict parser expects HTTP 200/201 and `{event_key,status:"COMMITTED",duplicate}` while the HTTPS channel authenticates the server. This is sufficient only if D05 authenticated channel identity and the backend's in-transaction ownership check bind all omitted provenance to the request. A signed portable receipt supports later offline verification but adds a backend signing service, canonical envelope, key lifecycle and format migration.

**Risk if unresolved/wrong.** A generic success, mismatched receipt or replay from a different owner domain can clear the Hub's durable queue without a matching durable backend effect.

**Interfaces.** `durable_commit.py`/durable API commit and ownership guard; `HttpBackendTransport` strict parser; `CloudSync::handle_backend_reply` and local journal completion. Current response is exact-key/status/duplicate only; full receipt provenance and D05-bound TLS principal are not established. Any response expansion is a new protocol contract, not an implementation detail.

**Security requirements.** TLS server verification plus approved client authentication; exact request/response binding; COMMITTED emitted only after transaction commit; duplicate means exact same immutable event; schema/version strictness; no redirect; reject truncation, extra/unknown security-critical values, conflict, wrong identity or stale epoch. Never turn transport send/HTTP 2xx into completion.

**Validation criteria.** New commit, exact duplicate, lost HTTP reply then same-key retry, response tampering/replay, wrong digest/key/Home/Hub/epoch/Node/generation, conflicting body, transaction rollback, post-commit response loss and Hub reboot before local completion. Verify one durable event/effect and one correct caregiver projection; Hub completion only after exact valid response.

**Exact approval requested.** GS-109/GS-148/GS-137 choose (A) request-bound TLS receipt with strict canonical provenance comparison (recommended if no portable/offline receipt need), or (B) independently signed receipt. Approve exact fields, canonical digest/encoding, wire version and compatibility policy, duplicate semantics, backend signing key/rotation if B, and whether Home/Hub/epoch/Node generation are explicit response fields or cryptographically bound by the authenticated request context. No current receipt contract is changed by this recommendation.

### D12 — Production protected-key custody and threat scope

**Preferred solution.** Require a production target with a documented restricted, non-exportable P-256 signing operation (existing identity key only if purpose and compromise risks are accepted; otherwise dedicated cloud key), protected boot and storage policy appropriate to credential/manifest confidentiality and integrity, and controlled debug/rework/revocation procedure. Verify actual silicon/configuration and recovery process before selecting the key path. This is a requirement proposal, not a claim that current R&D boards meet it.

**Alternatives and trade-offs.** External secure element offers stronger key isolation but adds BOM, driver and factory lifecycle. ESP32-S3 hardware-backed/flash-protection choices may fit existing hardware but depend on approved eFuse/provisioning and recovery policy. Software key in ordinary NVS is not acceptable for a commercial device credential under the stated threat model.

**Risk if unresolved/wrong.** Extracted or cloned Hub credentials permit impersonation and cross-Home data access; irreversible protection without recovery can brick service units or prevent safe rework.

**Interfaces.** GS-68 factory/security profile, target signer abstraction consumed by D05, manifest verifier/storage consumed by D03, signed update/rollback and debug/rework lifecycle. Current R&D source/build and board evidence do not establish commercial eFuse, Secure Boot, flash encryption, protected NVS or key non-exportability.

**Security requirements.** Threat model covers physical possession, debug access, key extraction/cloning, firmware rollback, factory/rework access and compromise response. Separate identity and cloud purposes unless explicitly accepted; restrict signer to approved algorithms/domains; audit key lifecycle; no private material in logs or host tests.

**Validation criteria.** Manufacturing/security review of exact target profile; negative export/signing-policy tests; boot/rollback policy checks; recovery and compromised-key revocation drill; documented factory separation and audit. Any irreversible eFuse/provisioning test requires a separate approved target procedure and is outside this package.

**Exact approval requested.** GS-68/security owner approves the threat model, target key-custody mechanism, key reuse vs dedicated key, Secure Boot/flash/NVS/debug/rework requirements, recovery and compromise response, and the evidence/authority allowed to assert production compliance. No hardware security settings are changed now.

### D15 — Commercial schema and rollback compatibility

**Preferred solution.** Version and validate the ownership registry, binding manifest, Node-generation mapping and COMMITTED receipt as one documented compatibility set. Define supported readers/writers and rollout order for currently supported signed S3 images; reject unknown or downgraded security-critical versions without erasing data. Preserve the existing partition layout and durable journals. Use additive dual-read/write only where an approved migration says exactly how and when it ends; do not waive the known historical journal migration failure.

**Alternatives and trade-offs.** One-shot coordinated fleet upgrade reduces dual-format code but makes partial rollout/recovery harder. Long-lived multi-version support improves rollback but expands parser and attack surface. A new partition or journal migration is not required by this decision and needs separate approval if proposed.

**Risk if unresolved/wrong.** A rollback may misread ownership/generation and misattribute retained events; downgrade could re-enable weaker authorization or lose a durable completion marker.

**Interfaces.** Manifest/registry/receipt codecs; Hub NVS and existing `gs_outbox`/`gs_state` persistence; CloudSync request/response parser; OTA image version policy and current partition table. No commercial schema is currently active, so this is a pre-activation compatibility contract.

**Security requirements.** Anti-downgrade for security policy; explicit minimum reader/writer versions; fail closed and preserve bytes on unknown/corrupt records; no silent reset; compatible replay/durable completion behavior across supported reboot/rollback.

**Validation criteria.** Old→new upgrade, interrupted upgrade, supported rollback, unsupported downgrade, mixed reader/writer versions, exact queued-event retry across image change, unknown/corrupt schema and storage-full behavior. Verify no data loss, no cross-domain acceptance and old readers cannot weaken security. Keep the historical migration FAIL separately visible.

**Exact approval requested.** GS-148/GS-68/GS-109 approve the concrete schema/version matrix, minimum supported image versions, deployment order, rollback ceiling, dual-read/write period and recovery procedure. Confirm whether any existing supported image must read new records; do not infer from current R&D firmware.

### D16 — Bounded resources, audit and shared S3 network ownership

**Preferred solution.** Instantiate one bounded CloudSync worker under the existing single S3 Wi-Fi/runtime owner. Keep ESP-NOW admission and durable ACK work higher priority; do not hold event-store or ownership locks over network I/O. Serialize Wi-Fi/channel transitions through one owner. Start with one in-flight HTTPS request and existing bounded event batches only if measurement supports it; treat each limit as a proposal needing owner values. Keep a sanitized, bounded audit of state/outcome/key digest and reason codes, never credentials or event payloads.

**Alternatives and trade-offs.** Independent Wi-Fi clients/workers risk channel changes and resource contention on the shared radio. Fully serialized access protects ESP-NOW but may delay near-real-time CloudSync. Larger batches/parallel requests improve throughput but raise RAM, socket and starvation risk. S3 has one shared Wi-Fi radio for infrastructure networking and ESP-NOW; the current Hub adapter selects the ESP-NOW channel and the HTTPS channel performs blocking calls. Existing 3-second call timeout/5-second soft deadline is not a proven hard worker deadline.

**Risk if unresolved/wrong.** Cloud traffic can starve event admission/ACK, disconnect ESP-NOW, exceed heap/stack budgets, or create unbounded retry/audit growth. Static channel choice can prevent AP association or degrade peer reachability.

**Interfaces.** `CloudSyncWorker` (host-injected, bounded batch/retry); `hub_runtime_adapter.cpp` Wi-Fi/ESP-NOW startup and owner loop; `HttpsBackendChannel` blocking transport; durable outbox query/completion. Required target design is a coordinator/task boundary with bounded mailbox and cancellation/deadline semantics; do not call synchronous HTTP from the ESP-NOW receive/admission owner.

**Security and safety requirements.** Strict payload/queue/connection bounds, finite retry/backoff, memory-pressure behavior, no lock across I/O, priority for authenticated event path, sanitized audit and credential secrecy, channel/reassociation policy preserving authenticated ESP-NOW, and fail-safe cloud pause under WAN/TLS/auth errors.

**Validation criteria.** Static/resource budget plus target load tests for queue full, max event/batch, slow server, connect/TLS timeout, WAN flap, reboot, cancellation, repeated errors and audit capacity; prove event admission/ACK latency remains within already approved GS-46/GS-69 budgets and no event is dropped. Verify AP channel coordination and ESP-NOW behavior on actual supported S3 profile in a separately approved HIL test before production activation.

**Exact approval requested.** GS-109/GS-148/GS-76 owners specify and approve numeric values for in-flight requests, poll interval, backoff bounds, batch and payload maxima, connect/read/overall hard deadlines, task stack/priority/heap budget, queue/audit capacity and retention, and CloudSync SLO. Approve the single shared Wi-Fi owner/channel coordination model and acceptable impact to event/ACK latency. No current soft timeout is promoted to a hard bound by this proposal.

## Compatibility with the delivered GS-148 implementation

The current worker preserves exact original event identity and checks injected current authority before/after network I/O. The backend ownership registry binds active Home/Hub/epoch and generation; the durable API commits transactionally and the strict Hub parser accepts only exact-key COMMITTED. These are useful implementation seams and already validated host behavior. They do not supply production authority, issuer/verifier, generation allocator, signed/request-bound provenance envelope, S3 task ownership or a radio coordination policy. Therefore they are compatible foundations, not authorization to activate target sending.

The S3 target uses one Wi-Fi radio shared by station networking and ESP-NOW; the current runtime channel and blocking HTTPS implementation must be reconciled under D16. The delivered GS-148 host validation is not evidence of commercial credentials, target key custody, target CloudSync runtime safety or a physical RF/network coexistence result.

## Minimal consolidated approval response

Please record one owner disposition for each row in GS-109 and identify the named approver/authority. `APPROVE RECOMMENDATION`, `SELECT ALTERNATIVE`, or `DEFER` is sufficient for the disposition, with the noted values where required. A recommendation marked approved is still not implementation authority for a different row or physical operation.

| Decision | Preferred disposition | Owner response required |
|---|---|---|
| D03 | Sole backend ownership authority + authenticated versioned binding manifest | Approve issuer, fields, epoch/alias/offline/recovery rules |
| D04 | Registry-resolved public QR + one-use scoped per-device installer proof | Choose signed QR vs lookup; approve generation/custody/recovery |
| D05 | Existing registered P-256 restricted signer only if D12 permits; otherwise dedicated protected key | Choose key and mTLS vs request proof; approve root, verifier, audience, replay/rotation |
| D06 | Backend trusted time + one-use challenge; fail closed for cloud | Supply TTL, skew, renewal, nonce and bootstrap values |
| D07 | Backend monotonic per-Node reservation mapped immutably at enrollment/event admission | Approve reserve/activate state machine, width/exhaustion and abort/recovery |
| D11 | Request-bound TLS receipt unless portable receipt is needed | Choose TLS-bound vs signed; approve exact fields/version and signature owner if needed |
| D12 | Verified restricted non-exportable production key custody and target threat profile | Approve exact target protections, recovery, rework and compromise lifecycle |
| D15 | Versioned schema compatibility/rollback matrix; fail closed, preserve data | Approve versions, image support, rollout, rollback and migration rules |
| D16 | One bounded worker under shared network owner, ESP-NOW priority | Supply finite runtime/resource values and channel/coexistence policy |

No values for D06/D16 are guessed. If those values or the D12 production target profile are not ready, approve the other contract direction independently and leave production sending disabled until prerequisites are complete.

## Implementation sequence after approval

1. **GS-68 / D12 and D04:** approve and implement the production identity/custody profile and factory registry/code lifecycle; provide security evidence and issuer ownership.
2. **GS-109 / D03 and D05:** implement authorized Home claim, authenticated Hub binding manifest, challenge/proof verification and recovery/revocation lifecycle against the existing ownership registry.
3. **GS-109 + GS-148 / D07 and D15:** implement transactional global generation reservation/activation, immutable local mapping, versioned codecs and supported image/rollback matrix without changing old event identity.
4. **GS-137/GS-148 / D11:** implement the approved canonical receipt contract and strict backend/Hub verification; test durable commit, lost response, exact retry and one caregiver effect.
5. **GS-76/GS-109/GS-148 / D06 and D16:** implement time/nonce lifecycle and one S3 network-owner coordinator with hard bounded operations and approved runtime budgets.
6. Run focused production-code and security regressions, affected Hub/contract/backend gates, sanitizers and S3 target builds. Then perform separately authorized target/HIL qualification for key custody, Wi-Fi/ESP-NOW coexistence, durable completion and recovery. Enable commercial sending only after all applicable reviews and tests pass.

## Work performed for this package

Document and Jira preparation only. No source implementation, test execution, hardware operation, credential issuance, root change or Jira workflow transition occurred. GS-148 Hub validation receipts and known independent blockers (historical migration assertion FAIL and P0 `product_status=PARTIAL`) remain as recorded in `R1_WORK_STATE.md`; neither is reclassified by this proposal.

## 2026-10-28 — Approval delta for caregiver-to-Hub configuration integration

**Disposition: pending owner/security decision.** This delta reuses the GS-68 / GS-109 / GS-148 RSA-3072 DS-backed mTLS feasibility candidate and the GS-76 `HumanAuthenticationBoundary`; it does not convert either candidate seam into an approved production identity. The current Hub TLS verifier, caregiver issuer/session directory, current Home membership authority, and deployment middleware are not installed. The versioned configuration repository added in this source checkpoint is inert until these authorities are approved and injected.

| Decision to approve | Proposed reuse/direction | Required owner/security disposition |
|---|---|---|
| **Hub identity and issuer lifecycle** (GS-68; GS-109 D04/D05/D12; GS-148 P2-D) | Dedicated Hub identity using the existing RSA-3072 ClientAuth/DS-backed mTLS candidate, resolved by fingerprint to the permanent Hub identity. Keep certificate issuance, key custody, trust-root ownership, proof freshness, enrollment, rotation, revocation, recovery and compromise handling inside the approved provisioning authority. | Name the issuer/security owner; approve the key custody and enrollment lifecycle, root distribution, proof/challenge freshness, renewal/rotation/revocation and recovery contract; or select a documented alternative. No credentials are created by this proposal. |
| **Caregiver issuer and session** (GS-76; GS-109 D03; GS-148) | Use `HumanAuthenticationBoundary` to turn a cryptographically verified access/session credential into a server-owned revocable `ActorSession`; obtain current account and Home membership/role from server authorities on each protected configuration write/read. Never accept role, Home or actor identity from request claims or headers. | Select issuer URL, audience, access-token versus session-token boundary, verification-key rotation/pinning, session expiry/revocation/offboarding source, and current Home-settings permission source; approve the Android/WebView credential handoff. |
| **Home and installation-epoch authority** (GS-D032; GS-109 D03; GS-148 ownership registry) | Keep the existing backend `hub_ownership_registry` as the sole current Hub→Home→epoch authority. The existing manifest direction is a candidate for conveying the registry decision durably to the Hub, bound to Hub identity and anti-rollback version. | Approve the registry as sole authority and choose an authenticated versioned manifest versus current online authority lookup, including offline behavior, transfer/recovery, stale epoch and revocation handling. |
| **Trusted middleware and deployment boundary** (GS-109; GS-148; GS-179) | Prefer the existing application-owned mTLS boundary to validate the peer and construct `VerifiedHubContext`, then pass that typed context only through trusted server context. Do not trust caller-supplied identity headers. A reverse proxy is acceptable only with an explicitly authenticated, integrity-protected peer-identity handoff and strict header stripping. | Select where TLS terminates, how authenticated peer identity reaches the application, which process owns trusted time/current ownership checks, and the production deployment/runtime that will host the boundary. The current Render TLS termination and local TEST_ONLY ingress do not satisfy this choice. |

After those four dispositions, approve the exact config fetch/apply contract separately: schema/version and canonical payload identity; authenticated request/ack binding to Hub/Home/epoch; durable S3 apply and restart behavior; stale/revoked/rollback handling; and desired-versus-applied status semantics. The repository now validates the existing household policy schema, serializes writers, uses expected-version conflict checks, retains the last applied version separately from the latest desired version, and requires trusted caregiver/Hub authorization callbacks. It adds no route, issuer, credential, or device behavior.

**Approval response:** for each table row, record `APPROVE PROPOSED DIRECTION`, `SELECT ALTERNATIVE: <contract>`, or `DEFER`, with the approving owner/security authority. Defer keeps production config routes and S3 fetch/apply disabled. This is the smallest decision set needed before implementation can connect the existing Settings and Hub seams; hardware campaign approval remains independent.
