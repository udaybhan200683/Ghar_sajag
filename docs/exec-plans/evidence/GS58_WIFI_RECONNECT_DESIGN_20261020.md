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

## GS58-D3 — India regulatory profile and bounded channel recovery

Jira comment 11457 selects the India-only R1 pilot profile: country code `IN`,
2.4 GHz primary channels 1–13 inclusive, and channel 14 excluded. One shared,
versioned profile is compiled into both C3 Node and S3 Hub. On each boot, after
`esp_wifi_init` and before `esp_wifi_start`, both targets call the pinned
ESP-IDF 6.0.3 `esp_wifi_set_country_code("IN", false)` API and read the active
country code back. A setter/getter error or mismatch fails Wi-Fi startup. The
profile is not configurable from AP country information, phone locale, SSID,
QR, or unsigned input. ESP-IDF 6.0.3 source maps `IN` to the WPC regulatory
profile whose 2.4 GHz rule is channels 1–13; this source inspection and target
build do not establish RF qualification.

The Hub's station associates on the router's actual supported channel; ESP-NOW
peers continue to use channel 0, which follows the active S3 radio. No post-
association channel-1 pin is used. The C3 has no station association, so it
advances one channel only when the existing bounded rejoin policy schedules an
existing `RejoinHello` transmission. It does not run a rapid scan loop or add
transmissions/wakeups. A response is considered only on a profile channel and
the existing NodeSecurityLink still checks the exact previously authorized Hub
MAC and the authenticated rejoin transcript. An authenticated challenge pins
that channel for the `RejoinFinal`/ACK retries. The channel becomes the preferred
channel for later outages only after the existing handshake completes; a failed
handshake keeps rotating within channels 1–13. No wire, session, ownership,
EventKey, retry, or persistent format is changed. Radio restoration after C3
light sleep preserves the current scan/session channel. The normal C3 bounded
rejoin deadlines continue to control scan pace and queued durable Events remain
retained until the existing authenticated ACK path succeeds.

First-time Node commissioning still uses its existing installer-controlled
commissioning flow and does not gain a new discovery frame or persistent channel
state in this change. Multi-channel physical recovery, sleep current, RF range,
and router association remain physical acceptance items.

## D1/D2 dependency boundary

GS-165 and GS-172 still have no owner-approved source/lifecycle contract for
the unique installer proof. Do not enable a commercial BLE service or substitute
the TEST_ONLY issuer. The credential store implementation is limited to the
approved encrypted-device-key boundary and an opaque atomic backend operation;
it defines no on-flash record encoding and has no target provider. A backend is
usable only when it attests that encrypted NVS and the verified per-device key
are available. The target continues to fail closed without that provider.
Partition label/geometry, key creation and recovery, hardware security
configuration, and physical key custody remain gated by GS-68/GS-172. No
credential provisioning or hardware operation is enabled.

## Current status

This resume adds the shared India profile/country guard and a bounded C3
channel cursor around the existing authenticated rejoin, plus a fail-closed
protected credential-store port with no target backend. The existing S3
reconnect policy and target event/task hook remain unchanged. D1 proof issuer
and D2 production key/partition inputs remain external prerequisites; no BLE
service or real credential persistence is enabled. D4 continues to use
existing CloudSync authority, transport and committed-event boundaries;
Wi-Fi routing is only permission to attempt CloudSync, not Internet,
authentication, or current monitoring evidence. See the GS-58 Jira handoff
for exact test and build results.

The current Hub target has no approved surfaced status contract that publishes
Wi-Fi association, Internet reachability, CloudSync authentication, and current
monitoring freshness as separate caregiver-visible states. This change does not
add an API or change the active GS-179 Android/backend work. Until those states
are mapped to an approved existing interface, this branch makes no
caregiver-visible `monitoring ready` claim; status-surface integration remains
an explicit canonical integration dependency.

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
