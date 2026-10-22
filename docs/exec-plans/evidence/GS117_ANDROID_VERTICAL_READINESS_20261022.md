# GS-117 Android sensor vertical readiness — 2026-10-22

## Scope and checkpoint

This is a bounded readiness checkpoint for the first genuine
`REAL PIR → C3 → authenticated S3 → backend → Parivar Saathi Android APK`
event. No board was opened, reset, stimulated, flashed, or accessed over USB or
serial. No listener, Windows network rule, firewall, router, Render service, or
customer data was changed. No real Hub credentials were installed. No physical
event was generated, so there is no EventKey or caregiver event to correlate.

The canonical worktree is `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, at `ec9076aa1326999de32d5ecc1e8ceb055cdff96e`,
matching the live origin at the start of this checkpoint. Tracked source was
clean, context preflight passed (`2026-10-13.001`), and the existing 301
untracked and 174,518 ignored assets were preserved. The full Jira inventory
contains 173 issues. GS-117 was To Do and Rank 52 at task start; it was moved to
In Progress for this active execution, without changing Rank. GS-114 remains
ahead at Rank 31 and In Progress. GS-60 remains To Do.

## Existing / reuse / gap / minimum change / Jira owner

| EXISTING | REUSE | GENUINE GAP | MINIMUM CHANGE | JIRA_OWNER |
|---|---|---|---|---|
| C3 PIR sensing, EventKey and authenticated Node transport are implemented; current physical C3 identity, image, slot, session and pending-event state are unverified. | Existing C3 event and retained-delivery path; GS-130 motion observer/HIL tooling. | No current-image or genuine AM312 GPIO4 trigger evidence; no qualified current no-reset observer. | Before target observation, owner must identify fixture/current image and approve a reset-safe observer; separately authorize one optical PIR stimulus. | GS-117, GS-40, GS-114 |
| S3 ESP-NOW admission, durable journal and CloudSync source exist; S3 production composition defaults to `UnprovisionedS3CloudTrust`. Current board/image, Hub identity, epoch, Node enrollment, trusted time and CloudSync session are unverified. | Existing S3 production-domain admission/CloudSync, GS-40 health and GS-109 authority contracts. | No verified currently authenticated physical Hub or approved current Home/Hub/epoch/Node authority for this run. GS-D032 leaves production identity/registry/receipt mechanisms unresolved. | Security/authority owner must supply or approve the exact identity, trust, Home/epoch, enrollment and trusted-time inputs for the selected isolated or commercial profile. Do not install or invent them. | GS-40, GS-68, GS-109, GS-148 |
| GS-148 durable PostgreSQL API and GS-179 TEST_ONLY runtime composition exist. Local PostgreSQL health currently passes. Runtime defaults to disabled and loopback. | Existing `TestOnlyMtlsListener`, durable COMMITTED/EventKey transaction, trust/readiness callbacks and caregiver projection. | Before this checkpoint, runtime composition rejected a private bind even though the listener supported guarded RFC1918 binding. No persistent Hub ingress is configured; real Hub authentication is `NO`; monitoring freshness is `UNKNOWN`. | Added an explicit TEST_ONLY opt-in requiring `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1`, a specific RFC1918 IPv4 address and a fixed port. Runtime remains disabled by default; no listener/network was activated. | GS-59, GS-148, GS-179 |
| Laptop caregiver HTTPS and PostgreSQL are running and healthy. Existing Windows forwarding/certificate/profile still use `192.168.1.6`; current Windows Wi-Fi is `192.168.1.10`. | Existing no-cost WSL2 service and Android LAN TEST_ONLY profile. | Current phone route is blocked by address mismatch; the GS-179 mTLS ingress is not composed into an externally reachable service. | Network owner must choose the exact laptop address and authorize coordinated certificate/origin/forwarding changes. Reuse the current service and database. | GS-58, GS-59, GS-179 |
| GS-177 Android APK and shared Home/Activity authorization/UI exist. Latest identified APK targets Render, not laptop PostgreSQL. | Existing APK, shared UI, Home authorization and API; no UI redesign is indicated. | Physical phone’s installed binary cannot be independently identified from this workspace; the APK artifact’s backend differs from the laptop’s database. | Once the approved same-backend HTTPS origin, matching SAN/CA and route exist, build only the existing GS-177 LAN TEST_ONLY variant and have the owner verify/install it. | GS-177, GS-117, GS-60 |
| GS-130 physical case and existing HIL runners exist. | `gs130_motion_hil.py`, `gs130_board_hil.py`, `gs130_hil_common.py`, and `gs40_qualification.py`; no new HIL framework. | `PHY-GS117` has no current physical run or current image/fixture receipt. The historic serial capture is not current proof. | Use the existing accepted GS-117 plan after the fixture and observer gates; preserve unique evidence and distinguish REAL_SENSOR from HOST_SIM. | GS-117, GS-121, GS-130 |

A minimal source correction was justified: the existing runtime exposed a bind
host setting but categorically rejected the private address needed for an
authorized WSL2-to-LAN Hub route. The new opt-in delegates to the listener's
existing private-bind guard and still rejects wildcard, public, non-RFC1918,
IPv6 and ephemeral-port private bindings. It does not configure or attest
network isolation. The remaining blockers are current hardware, trust, network
configuration and operator authorization; the source change alone does not
establish a physical event.

## Observed product path and readiness

```text
AM312 optical movement / C3 GPIO4          NOT VERIFIED — physical fixture not inspected
  → C3 sensing and EventKey                REAL SOFTWARE EXISTS; no current target/image evidence
  → authenticated ESP-NOW to S3            REAL SOFTWARE EXISTS; no current physical session evidence
  → S3 durable admission / CloudSync       REAL SOFTWARE EXISTS; current Hub trust is unverified
  → laptop application-terminated mTLS     SOFTWARE IMPLEMENTED; TEST_ONLY, disabled; RFC1918 binding opt-in added
  → local PostgreSQL COMMITTED             HOST_SIM evidence exists; no physical source event
  → authorized caregiver projection        REAL LOCAL SERVICE READY; no same physical event
  → Android Home/Activity                   APK artifact exists; physical installed binary not verified
```

Latest local `code/tools/local/gs179-laptop-server.sh health` reported:

```text
POSTGRES_READY=PASS tls=verify-full durability=fsync,synchronous_commit,full_page_writes
CAREGIVER_HTTPS_READY=PASS tls=ca_and_ip_san_verified
LOCAL_BACKEND_READY=PASS
PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH expected_address=192.168.1.6 observed_address=192.168.1.10
HUB_INGRESS_RUNTIME_IMPLEMENTED=YES
HUB_INGRESS_AUTOSTART=DISABLED
HUB_IDENTITY_AUTHENTICATED=NO
HUB_MONITORING_FRESHNESS=UNKNOWN
PERSISTENT_HUB_INGRESS=NOT_CONFIGURED
HUB_INGRESS_READY=NOT_CONFIGURED
```

Read-only Windows inspection found the existing forwarding row
`192.168.1.6:443 → 172.17.152.10:8444`; Windows Wi-Fi currently reports
`192.168.1.10`. The public metadata of the local Android HTTPS leaf has
`CN=192.168.1.6`, IP SAN `192.168.1.6`, and issuer
`Ghar Sajag GS-179 Local Android TEST ONLY CA`. No network setting or
certificate was changed. Render's currently live caregiver service is on
commit `3c0fec898d5cb2caae662f3dcc6324faaabf6b30`; its deployed WSGI entry
only calls `connected_lite.build_app()`. Render terminates incoming TLS before
the app, so it cannot provide a verified Hub TLS peer to the existing
application-terminated Hub mTLS listener. No forwarded identity header is
accepted as a substitute.

The latest identified Android workflow is
[run 39711096218](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39711096218),
successful for source `acde2183c74351db403b49b441deea67a3474142`. Its artifact
metadata reports package `in.gharsajag.caregiver`, version
`0.4.0-connected-lite-staging`, origin
`https://parivar-saathi-lite-staging.onrender.com`,
`gs179_local_lan_test_only=0`, and runner-generated testing-only debug signing
(an uninstall of a differently signed build may be required). APK SHA-256 is
`fa0a53b7f9cff822e27409701d7b60d78f142f08989d8362e672594d1f5e8c72`.
The owner reports installing the latest available APK, but no handset package,
version, signer or active Home/API response was read during this checkpoint.
That Render-targeted APK does not share the laptop PostgreSQL data source.

The only inspected S3 receive-only physical capture is dated 2026-10-16 and
records source HEAD `d738dc51a25e72de570a11fc39f0e26522ead3d8`; it is historical
and not evidence of the currently installed S3 image or its effective config.
GS-114 attempt06 is also historical. No current C3/S3 identity, running image,
partition/slot, pending EventKey journal, Home/epoch, enrollment, trusted-time
readiness, live Hub credential, AM312 wiring, operator, or reset-safe observation
method was verified. No serial port was opened.

## Validation and evidence classification

Read-only deployment/fixture checks included `git rev-parse HEAD`,
`git ls-remote`, `tools/context/ghar_sajag_context_preflight.sh`, the local
laptop `health` command, Windows IP/portproxy reads, public TLS certificate
metadata, current Render deployment metadata, and Android workflow artifact
metadata/hash. No browser session, APK installation, HIL `--observe` or `--run`,
Node input injection, or hardware operation was run.

The implementation change is in `code/backend/ghar_sajag/gs179_hub_ingress_runtime.py`
and its registered integration test. The new setting defaults off; private
binding requires `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1`, a specific RFC1918
IPv4 and fixed nonzero port. Public, wildcard, non-RFC1918, IPv6, private port
0, invalid flag values and missing opt-in are rejected. The existing complete
runtime process E2E continues to use loopback; no private-address socket was
opened in this validation.

Focused results:

- First `make -C code gs179-postgres-e2e` attempt: **exit 2**, expected guard
  because `GS179_TEST_POSTGRES_DSN` was absent from the shell environment.
- Rerun with the existing mode-0600 local server config and its local,
  hostname-verified TLS DSN, whose fixture creates/drops isolated random
  schemas: **51/51 PASS**, `physical=NOT_RUN`. This includes 18 GS-178
  Node-origin vertical cases, 15 security cases, 14 GS-179 PostgreSQL/lifecycle
  cases and 4 runtime-composition cases. The source-linked EventKey evidence is
  HOST_SIM only; private-bind validation tests configuration rules, not a LAN
  socket or real Hub.
- `make -C code validation-framework-test`: **51/51 PASS**.
- `make -C code feature-coverage-test`: **PASS**, 223 features, 278 modules,
  26 physical cases; mapping tests **22/22 PASS**.
- `git diff --check` and `PHY-GS117` CSV schema/status assertion: **PASS**.

These results establish the existing source-linked isolated software path and
the new private-bind fail-closed configuration behavior. They do not establish
REAL_SENSOR, REAL_HUB, current target firmware, or physical Android acceptance.
There is no physical EventKey, PostgreSQL receipt, caregiver record, duplicate
count, source-health transition, or Android presentation for this checkpoint.

`PHY-GS117` remains `NOT_RUN`. The catalogue now names the Android APK as the
physical caregiver endpoint per owner direction; browser checks remain
supporting shared-UI evidence only. GS-117, GS-60, GS-121 and GS-114 acceptance
remain open. No commercial release claim is made.

## Exact next action and gates

1. The fixture owner identifies the exact C3/S3 fixture and confirms the
   installed images, partition/slot, pending state, Home/Hub/epoch/enrollment,
   PIR wiring and operator. The owner separately approves a named, reset-safe
   passive observer and the single genuine optical PIR stimulus. The historical
   COM9/CH343 receive-only session is not reused as current observer approval.
2. The security/authority owner supplies the already-approved client/server
   trust, current Hub/Home/epoch and Node enrollment, revocation state and
   trusted-time source for the selected isolated or commercial profile. No
   credential issuance, Home claim, epoch mutation or installation is implied
   by this checkpoint.
3. The network owner confirms whether `192.168.1.6` is reserved for this laptop
   or approves a coordinated new origin. Any Windows IP, forwarding/firewall,
   private-bind runtime configuration/activation or certificate change requires
   its own exact approval. If approved, the runtime's RFC1918 setting is
   `GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND=1` together with a specific address
   and fixed port. The caregiver APK and Hub ingress must reach the same
   PostgreSQL authority; Render is not a verified mTLS ingress path.
4. Only after those gates, configure and start the already-implemented GS-179
   runtime with the approved inputs; verify the Android CA-pinned origin and
   owner-installed APK; then perform one real PIR event and correlate its
   original EventKey through Hub COMMITTED and the Android Activity. Perform the
   second PIR event only after the first one passes.

The next physical step is blocked on those fixture, trust/authority, trusted
time and network approvals. Do not substitute HOST_SIM or a direct backend
insert, and do not infer a real Hub connection from local PostgreSQL or HTTPS
readiness.
