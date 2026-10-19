# GS-58 Wi-Fi onboarding and reconnect design — 2026-10-20

## Scope and source authority

Owning Jira: GS-58. Affected components are the ESP32-S3 Hub network startup,
ESP-IDF provisioning integration, the C3/S3 radio recovery path, the existing
Hub CloudSync worker and its current status/freshness consumers. The approved
direction is Jira comment 11451 (D1–D4), bounded by the current LOCKED
requirements and existing GS-68/GS-109/GS-148 seams. This document records an
implementation design, not a new product requirement or production activation.

The GS-179 canonical worktree remains separately owned. No files there are
changed by this branch. No Android source is changed here; Android integration
is limited to the stable provisioning wire contract pending its reviewed
integration window.

## Existing architecture and constraints

- The commercial S3 target composes `hub_runtime_adapter.cpp`, S3 storage,
  `CloudSyncWorker`, `S3CloudRuntimeAuthorityProvider` and
  `HttpsBackendChannel`. Production cloud trust is `UnprovisionedS3CloudTrust`
  unless the separately approved provider is supplied.
- The existing GS-40 TEST_ONLY path is a test profile. It selects
  `WIFI_STORAGE_RAM`, accepts only signed TEST_ONLY input, and currently
  rejects an AP primary channel other than 1. It is not the production
  credential store or onboarding authority.
- The Hub and C3 currently set ESP-NOW channel 1. C3 rejoin already establishes
  a fresh authenticated session and retained EventKeys are restored only after
  that session is ready. Channel discovery must leave this order and the
  durable-before-ACK / exact retry behavior unchanged.
- ESP-IDF 6.0.3 provides `protocomm` but does not include the Wi-Fi provisioning
  manager in its in-tree components. The current S3 target has no BLE
  provisioning dependency. The approved integration is Espressif's managed
  `network_provisioning` component over BLE with Security 2, not a hand-written
  transport or cryptographic protocol. The host must remain the existing
  Android caregiver application at its reviewed integration window.
- The current S3 development partition table and boot profile do not establish
  a production encrypted-NVS partition/key source. No real Wi-Fi credentials
  may be stored until the GS-68/GS-172 per-device key and partition lifecycle
  review is complete.
- The existing `cloud_wan_ready()` helper proves only AP association, IP and a
  gateway. It does not prove Internet reachability, TLS peer authentication,
  current Home authority, backend COMMITTED, or actual monitoring freshness.

## Approved software design

### D1 — installer-authorized BLE network configuration

Use the existing Espressif provisioning manager and protocomm Security 2
(SRP6a/AES-GCM), subject to the pinned ESP-IDF 6.0.3 target build and Android
wire compatibility check. The manager is an adapter around the S3 station; it
does not own Hub/Home identity or cloud authority.

The station accepts a device-specific Security 2 username/password proof
material from a factory proof provider. Its source and recovery/enrollment
lifecycle remain an explicit GS-165/GS-172 prerequisite. If no valid proof
material is available, provisioning does not start. The public QR is a
non-authorizing Hub reference and never contains this secret. A valid local
proof permits only Wi-Fi configuration; it cannot create/transfer a Home
binding, authorize a Hub claim, or add a Node.

Do not add the customer-facing Android screen in this branch. The integration
contract is the ESP provisioning BLE service identity, Security 2 session,
standard Wi-Fi scan/configure endpoints, and an explicit success/failure result;
the app obtains the setup secret only through the separately approved installer
process. Do not log or include credentials, proof material, SSIDs or QR secrets
in operator reports.

### D2 — protected credential persistence

Define the provisioning workflow against an encrypted credential-store port.
The concrete S3 adapter must initialize and use an explicitly encrypted NVS
partition through ESP-IDF's secure NVS APIs and a verified per-device key
provider. It must refuse initialization if encryption/key provenance cannot be
verified; no call may fall back to `nvs_flash_init`, plaintext NVS, a global
key, or RAM-only persistence while claiming restart recovery.

Credential replacement is an atomic store operation. The new values are not
used for station reconnect unless persistence has committed; on a failed
replacement, keep the previously committed credential generation. Explicit
authorized deprovisioning erases the credential record. The exact NVS label,
partition geometry, key source, erase/recovery behavior and migration policy
remain gated by GS-68/GS-172 review; this branch must not enable hardware key
provisioning, Flash Encryption, Secure Boot or eFuses.

### D3 — channel discovery and authenticated recovery

Use the existing ESP-NOW peer interface and existing versioned authenticated
rejoin handshake. A C3 may transmit rejoin attempts only on channels permitted
by the approved shared regulatory-domain configuration. A channel observation
or unauthenticated discovery hint can select a candidate but cannot authorize
the Hub, create trust, change ownership or retire a retained event. The Node
must complete the current authenticated fresh-session handshake before normal
runtime admission and event replay/retirement.

No new wire frame, persistent channel field, alternate radio or protocol
fallback is included in this design. Existing retries remain bounded by the
current recovery policy; candidate search must be bounded and must not prevent
the retained event queue from retrying after authenticated recovery.

**Implementation is held pending one additional product/regulatory decision:**
no current R1 source selects the allowed C3 channel list/country domain or its
configuration source. The active decision request is to use an explicit shared
approved country setting and scan only its allowed channels, or select a
different explicit policy. No D3 target/protocol changes are made until that
answer identifies the approved source and permitted channel set.

### D4 — reconnect, CloudSync and truthful state

Keep the existing `CloudSyncWorker`, `S3CloudRuntimeAuthorityProvider`,
`HttpsBackendChannel`, durable EventKey outbox and NodeHealth freshness policy.
The network task continues to retry when Wi-Fi has an address and route, but
such a route is not labelled Internet, authentication or monitoring success.
CloudSync remains fail closed unless current permanent Hub identity, current
Home/epoch, trusted time, verified TLS identity and the existing backend
COMMITTED path are available.

Maintain separate internal observations for Wi-Fi association/addressing,
Internet/verified transport, cloud authentication/authority, and monitoring
freshness. Report `UNKNOWN`, `OFFLINE` or `STALE` when the existing inputs do
not establish a stronger state. `READY`/monitoring-active requires a current
accepted health publication under the existing NodeHealth freshness contract;
link-up, a TEST_ONLY result or an unverified HTTP response is insufficient.
No backend route, PWA API, NodeHealth schema or GS-179 Android API change is
included.

## Validation design and execution scope

Permanent coverage will use the existing GS-116/GS-130 host, component,
contract and source-traceability infrastructure. New cases will exercise the
actual production connectivity/provisioning policy code, including missing or
invalid installer proof, encrypted-key unavailable, atomic replacement failure
and recovery, wrong Wi-Fi credentials, AP loss/restart/DHCP recovery, state
truthfulness, CloudSync authority unavailable/changed, and ensuring an AP/IP/
gateway or TEST_ONLY result cannot become monitoring-active.

When D3's regulatory source is approved, tests will include AP channel change,
Node offline/reboot, authenticated rejoin, unknown versions, six-Node contention,
wrong-Hub discovery and duplicate/replay preservation. If any such case requires
a new wire or persistent compatibility field, pause that change for the narrow
security/compatibility approval requested by Jira comment 11451.

The affected development regressions are S3 Hub, C3 Node (only if its source is
changed), Hub/Node shared contract and CloudSync. Build with the pinned ESP-IDF
6.0.3 using non-flashing S3 and (if C3 source changes) C3 commands. Do not run
physical HIL or any device/credential/key operation. Physical Wi-Fi association,
router-loss recovery, BLE commissioning, encrypted-NVS key custody and channel
rejoin remain NOT_RUN until a separately authorized fixture plan is approved.

## Current status

This checkpoint implements the bounded S3 reconnect scheduling policy and its
target event/task hook. The policy ignores disconnect and driver-failure events
until the secure credential-ready handoff, and target event/task callers
serialize access to policy state. Host tests cover this fail-closed boundary.
D3 is awaiting the country/channel-domain decision. D1 proof issuer and D2
production key/partition inputs remain named external prerequisites; no BLE
service or credential persistence is enabled by this change. See the GS-58
Jira handoff for exact test and build results.

## Validation infrastructure triage

```text
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=docs/validation/MASTER_VALIDATION.md
DECISION_IDS=NONE
TASK_SCOPE=GS-58 bounded Hub station reconnect policy and affected regressions
OUT_OF_SCOPE=CloudSync product logic, journal migration semantics, and PWA/browser behavior
```

The Hub component suite exposed that `cloudsync-security-ut` invoked the
GS-40 TEST_ONLY adapter binary without declaring it as a build prerequisite.
The Makefile now declares the existing target so the stage can run from a clean
build directory. No CloudSync or TEST_ONLY implementation code changed.
