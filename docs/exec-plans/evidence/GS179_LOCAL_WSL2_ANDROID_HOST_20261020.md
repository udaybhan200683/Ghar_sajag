# GS-179 local WSL2 caregiver validation host — 2026-10-20

> **Recovery update (2026-10-20):** The earlier forwarding description below
> records the setup at the time it was validated. The current Wi-Fi address is
> `192.168.1.3`, while the existing certificate, Android origin and Windows
> forwarding mapping use `192.168.1.6`. No Windows network setting was changed.
> The recovered WSL backend is locally ready, but the Windows-to-phone route is
> currently unavailable. The current service lifecycle and network findings
> are recorded in
> [`GS-179 laptop service recovery`](GS179_LAPTOP_SERVICE_RECOVERY_20261020.md).

## Result and scope

The owner selected the existing Windows 10 laptop and WSL2 for no-cost,
same-trusted-Wi-Fi R1 Android validation in GS-179 comment 11452. This checkpoint
configures the canonical GS-148 caregiver API/PWA and PostgreSQL on that laptop,
adds a narrowly scoped Windows-to-WSL HTTPS route, and prepares a debug-only
Android build profile for the current laptop origin. It does not change Render,
production services, router configuration, hardware, production credentials, or
commercial security policy.

The software path exercised is the existing GS-178 host Node/Hub code → the
existing TEST_ONLY application-terminated TLS 1.2/mTLS listener and GS-148
durable API → the local PostgreSQL commit store → authenticated caregiver API
and canonical PWA. It is **HOST_SIM_PASS** only. The persistent laptop service
is the caregiver HTTPS API plus PostgreSQL. It is not a continuously running
physical Hub mTLS endpoint: the source-linked host-simulation command runs the
existing TEST_ONLY Hub mTLS listener using ephemeral test credentials. No
physical Hub identity or client credential is installed on this laptop.

## Runtime and network boundary

- Current caregiver origin: `https://192.168.1.6` (RFC1918 Wi-Fi address; it
  may change with DHCP. The Android trust profile and server certificate are
  bound to this exact address and must be deliberately renewed together if it
  changes).
- The existing Windows mapping is `192.168.1.6:443` to the current WSL NAT
  address on TCP 8444. It is not usable while Wi-Fi is `192.168.1.3`; read-only
  inspection found no Windows TCP 443 listener. The firewall rule's current
  presence/scope could not be verified using the non-administrator account.
  No router port-forward or public listener is configured.
- The app binds to the WSL interface and serves TLS 1.2 or later. Windows can
  reach the WSL TCP listener, but Windows curl's Schannel validation returned
  `CERT_TRUST_REVOCATION_STATUS_UNKNOWN` when supplied the local CA. This was
  not bypassed. WSL's CA- and IP-SAN-verified `/readyz` check passes.
- The PostgreSQL listener is only `127.0.0.1:55432`. Its HBA rejects remote
  hosts; the application role uses SCRAM and `sslmode=verify-full` against the
  private local PostgreSQL test CA.
- PostgreSQL was checked with `fsync=on`, `synchronous_commit=on`, and
  `full_page_writes=on`. A service restart preserved the committed event.
  A separate machine-loss backup/restore rehearsal was not run.
- The observed Windows Wi-Fi profile is Public. The firewall rule was
  previously configured with an interface/address/subnet scope, but that scope
  could not be re-read without administrator permission. Re-run the read-only
  audit after a network or WSL address change; mismatched addresses fail
  closed.
- The laptop must remain awake, logged in to WSL and connected to the same
  trusted Wi-Fi while the phone test is running. Mobile-data access is not
  configured. Do not add a router port-forward; any off-LAN VPN/overlay remains
  a separate decision.

## TEST_ONLY HTTPS identity

The Android profile includes only the public local TEST_ONLY CA certificate;
its private key remains owner-only under the user's local data directory and
was not committed. The standards-shaped CA has `CA:TRUE,pathlen:0` and
`keyCertSign,cRLSign`; its file SHA-256 is
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5` and its
certificate fingerprint is
`124e28f34b8d73aa9fdd3f0f0fa2b7ff216e601c25162d1d6a224f1d63372b7c`.

During review, the original server leaf was found to have no IP SAN. Although
the current curl/OpenSSL environment accepted its legacy common-name identity,
that was insufficient evidence for Android's IP hostname check. The local
TEST_ONLY leaf was reissued under that CA with `IP:192.168.1.6`, `CA:FALSE`,
and `serverAuth`. Its file SHA-256 is
`390e1505b37a47f0dd08272a52fbd96a5a716828e7e6dc580a38abd2629b6119`.
`openssl verify -CAfile <private-ca.pem> -verify_ip 192.168.1.6 <server.pem>`
and a live CA-verified HTTPS `/readyz` request both passed after service restart.
The leaf and CA private keys remain mode 0600 outside the repository.

The local APK trust profile is conditional on the explicit
`gs179LocalLanTestOnly=true` Gradle property. It pins the exact LAN origin to a
single matching `network_security_config` domain and trusts the embedded local
test CA only for that domain. Release builds and ordinary debug builds retain
the public-DNS-only origin rule and do not include the local CA/profile. The
LAN build runner also verifies the manifest/resource binding, exact origin
match, and that the bundled certificate is a current self-signed CA with
critical CA constraints and certificate-signing usages. The
LAN APK always uses a runner-generated debug signing key, not a pilot or
production key. The build runner rejects an origin that differs from the
profile's pinned domain.

## Repeatable laptop commands

Run these from the canonical WSL worktree:

```bash
code/tools/local/gs179-laptop-server.sh start
code/tools/local/gs179-laptop-server.sh status
code/tools/local/gs179-laptop-server.sh health
code/tools/local/gs179-laptop-server.sh logs 100
code/tools/local/gs179-laptop-server.sh restart
code/tools/local/gs179-laptop-server.sh health-source
code/tools/local/gs179-laptop-server.sh browser
code/tools/local/gs179-laptop-server.sh stop
```

`provision` is a first-time operation and is idempotent only when the complete
private PostgreSQL/configuration state already exists. It refuses partial
state. The `event` command intentionally creates a source-linked event only
for an empty GS-179 persistent test Home; it refuses if an event already
exists. Do not run it to repeat the already committed event.

`start` and `restart` start the WSL user service and PostgreSQL only, wait up to
30 seconds for verified local PostgreSQL and caregiver HTTPS readiness, then
report phone-LAN and Hub-ingress states separately. They do not start or stop
Windows forwarding. `proxy-audit` is read-only. `proxy-start` and `proxy-stop`
remain explicit Windows network mutation commands and were not invoked during
this recovery. `status`/`logs` are for diagnosis. The service does not install
a Windows startup task; after a Windows/WSL restart, open the existing WSL
distro and run `start`.

## Validation evidence

Source state before delivery was canonical `feature/r1-commercial-baseline`
at `ef85e5b1ae0fe859fd666164976c0a293598c097`, equal to origin; context
preflight returned `GHAR_SAJAG_CONTEXT_PREFLIGHT=PASS`. No new branch or
worktree was created. The GS-58 worktree was left untouched.

Observed focused results:

- Existing GS-178 production-code host simulation generated one Node motion
  event, preserved its original EventKey, received the matching GS-148
  `COMMITTED` receipt and stored exactly one durable PostgreSQL row. Existing
  caregiver login/API returned that same event. The correlated EventKey is
  `{"physical_device_id":"test-c3-bedroom","logical_node_id":"bedroom","origin_session_id":10,"event_sequence":1}`.
  It is a TEST_ONLY fixture identifier, not a physical Node identity.
- After an application/PostgreSQL service restart, the same row and caregiver
  session remained available; no new event was inserted.
- After backend source freshness expired, the caregiver API reported source
  `STALE`, monitoring `UNKNOWN`, and Node `UNKNOWN`; it did not infer resident
  wellbeing from missing observations. A later authenticated host-simulator
  NodeHealth refresh restored source `CURRENT`, monitoring `COVERED`, and Node
  `ONLINE`.
- `code/tools/local/gs179-laptop-server.sh browser`: **HOST_SIM_PASS**. The
  canonical bundled PWA used the laptop HTTPS API, verified the committed
  event key/kind/room, showed current authenticated source freshness and
  `ONLINE`/`COVERED`, then reloaded with one event and no duplicate.
- `PYTHONPATH=/tmp/gs179-python-deps python3 -m unittest discover -s code/parivar_saathi_android_app/server/tests -p test_connected_lite.py -v`:
  **15/15 PASS**.
- `node --test code/tests/js/caregiver_runtime.test.mjs`: **8/8 PASS**.
- `GS177_BACKEND_ORIGIN=https://192.168.1.6 GS177_LOCAL_LAN_TEST_ONLY=1 python3 code/validation/run_gs177_android.py`:
  local profile/origin/CA-pinning checks, branding checks and 8 PWA runtime
  tests passed; the runner then returned **BLOCKED (127)** because Gradle and
  Android SDK are not installed in WSL. The negative profile check with
  `https://192.168.1.7` returned the expected **FAIL (1)** before invoking
  Gradle because it did not match the CA-pinned profile domain.
- The repository's `make -C code pwa-68-browser-test` reported **0 run, 1
  skipped** because system Chromium is not installed. The dedicated Playwright
  browser executable already present in the test cache was used by the local
  browser validation above, which passed against the live HTTPS API.
- GS-179 PostgreSQL/security focused tests: **7/7 PASS**; GS-178 host vertical
  focused cases: **3/3 PASS** in the preceding execution. These were not
  rerun after the Android-only pinned-domain guard change.
- TLS: `openssl verify ... -verify_ip 192.168.1.6` **PASS**; `curl --cacert
  <private-ca.pem> https://192.168.1.6/readyz` **HTTP 200**; OpenSSL live
  `s_client -verify_ip 192.168.1.6 -verify_return_error` returned **0 (ok)**.
- No phone APK build/install/foreground/background acceptance, physical C3/S3,
  phone data use, production service or hardware test was executed in this
  evidence checkpoint.

The source-matched local-LAN Android build completed in GitHub Actions run
[39326071201](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39326071201)
on commit `b8af8b37f3de4334a672588e5f5c8fad0dd855d4` with
`backend_origin=https://192.168.1.6` and
`gs179_local_lan_test_only=true`. The run passed the PWA browser/offline stage,
the registered caregiver app gates (Connected Lite API 15/15, Android dashboard
7/7, voice prototype 21/21), `:app:testDebugUnitTest`, `:app:assembleDebug`,
APK signature verification and artifact upload. The CI artifact is
`parivar-saathi-caregiver-debug-b8af8b37f3de4334a672588e5f5c8fad0dd855d4`
(artifact ID `12222706843`, archive SHA-256
`5e637ab363eb208c95f1f0217199175c3d696d7aef4e2992bff9d048ebbbd7ef`). Its
APK is 2,913,584 bytes, SHA-256
`6935f71d06c38087f09b2bf95c6a216e4dae30836449e367c773e7afa65eab42`; the
downloaded file passed `sha256sum --check` and APK archive integrity. CI
verified APK Signature Scheme v2. Build metadata binds it to the exact LAN
origin, local TEST_ONLY flag, and CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
Signing is runner-generated debug signing, not a pilot key. This proves APK
build and software gates only; it does not prove installation or behavior on
the owner's phone.

## Phone acceptance steps after artifact availability

1. Keep the Windows laptop awake, connected to the same trusted Wi-Fi, and WSL
   running. In canonical WSL, execute `code/tools/local/gs179-laptop-server.sh
   start`; require both `/readyz` probes to report ready. If the Wi-Fi address,
   subnet, certificate SAN, or CA-pinned profile changed, stop and reissue the
   local TEST_ONLY leaf/rebuild the APK; do not bypass certificate checks.
2. Install the `GS179_LOCAL_LAN_TEST_ONLY=true` debug APK artifact from the
   source-matched GitHub Actions run. It is signed with a runner-generated
   debug key. If Android reports a signature conflict with the previously
   installed pilot/debug package, remove that prior package only after
   preserving any desired local app state; server-side caregiver data remains
   in the laptop database.
3. On the phone, join the same trusted Wi-Fi (not mobile data/VPN), open
   Parivar Saathi and sign in using the already provisioned private
   GS-179 TEST_ONLY caregiver account. Confirm the bedroom motion appears once
   with its original event time and room; Devices shows `ONLINE`/`COVERED`;
   Home monitoring/source freshness shows current authenticated data.
4. Background and foreground the app, reload it, and verify the event remains
   once. Allow source freshness to expire without generating a new NodeHealth
   contact; refresh the caregiver view and require `UNKNOWN`/stale instead of
   false connected/wellbeing status. Run the existing `health-source` command,
   reload and require the authenticated source to recover to current and
   `ONLINE`/`COVERED`.
5. Record the phone model/Android version privately, APK artifact/source/hash,
   screenshots and timestamps. No credentials, private keys, or full
   identifiers go into public Git/Jira. Mark phone acceptance only after these
   observations are actually collected.

## Status

`LAPTOP_SERVICE`: PASS (local TEST_ONLY API/PostgreSQL running)
`HOST_SIM_NODE_EVENT_TO_POSTGRES_COMMITTED`: PASS
`CAREGIVER_BROWSER_PROJECTION`: PASS (host Playwright)
`ANDROID_LOCAL_LAN_APK_BUILD`: PASS (run 39326071201; source b8af8b37; APK
SHA-256 6935f71d06c38087f09b2bf95c6a216e4dae30836449e367c773e7afa65eab42)
`PHONE_FOREGROUND_BACKGROUND_ACCEPTANCE`: NOT_RUN
`C3_S3_PHYSICAL_TARGET_ACCEPTANCE`: NOT_RUN
`LIVE_STAGING_SOFTWARE_E2E_PASS`: NO (Render was not changed or accessed for
this local-host validation)
`PRODUCT_OR_RELEASE_PASS`: NO; broader P0 and physical release gates are not
reclassified by this local demonstration.

## 2026-10-22 — owner-approved Windows/WSL2 LAN configuration

Owner approval was recorded in GS-179 comment 11546 and GS-117 comment 11547.
This section supersedes the earlier statement in this file that no LAN
endpoint/forwarding/firewall changes were made; it does not change the physical
acceptance boundary.

### Current endpoint and trust

- Windows Wi-Fi is connected to SSID `Yogi`, IPv4 `192.168.1.6/24`,
  network category Public. The address is DHCP; the observed lease expires
  2026-10-23 15:36 local time. No router reservation was inspected or changed,
  so this is a verified current endpoint, not a guaranteed stable address.
- WSL2 address is `172.17.152.10`; caregiver HTTPS listens on that address at
  port 8444. PostgreSQL listens on WSL loopback port 55432.
- Existing TEST_ONLY server certificate already has the `192.168.1.6`
  address SAN and serverAuth purpose. Existing local CA SHA-256 is
  `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`,
  matching the Android local-LAN CA pin. The certificate verified for
  `192.168.1.6`; no CA, leaf certificate, key, or Android pin was changed.
- Caregiver HTTPS and Hub-ingress configuration use the same verified local
  PostgreSQL database: `gs179_monitoring`, role `gs179_app`, endpoint
  `127.0.0.1:55432`, PostgreSQL `verify-full`, with fsync,
  synchronous_commit, and full_page_writes enabled. Secret DSN contents are
  held only in the owner-private mode-600 configuration.

### Reversible LAN configuration

The existing portproxy row was `192.168.1.6:443 ->
172.17.152.10:8444`, but Windows had no active TCP 443 listener. The
owner-approved start helper now refreshes the same row when it is dormant and
fails closed unless the listener appears. It restores a replaced prior row and
removes only a newly created firewall rule if startup fails.

The Windows helper created rule `GS179-Local-LAN-HTTPS` for inbound TCP 443,
local address `192.168.1.6`, remote subnet `192.168.1.0/24`, Wi-Fi
interface, Public profile, and blocked edge traversal. It does not add a
router rule or Internet exposure. The current firewall query from WSL is
limited by Windows administrator-read permissions. The elevated Start
operation successfully created the rule with the exact parameters above;
post-change audit confirmed the listener and forwarding row, while firewall
rule readback remained blocked for the non-administrator WSL token.

Private rollback material is preserved at
`/home/udaybhan/.local/state/ghar-sajag/gs179-laptop/lan-rollback-20261022T103148Z`.
The saved private config is mode 600. To roll back: remove only firewall rule
`GS179-Local-LAN-HTTPS` from an elevated PowerShell prompt; restore
`server.env.before` to
`/home/udaybhan/.config/ghar-sajag/gs179-laptop/server.env` with mode 600;
and remove the newly created
`/home/udaybhan/.local/state/ghar-sajag/gs179-laptop/windows-wsl-target`
marker. The portproxy entry had the same target before this task; removing the
firewall rule restores the prior effective network access. If the forwarding
row itself is intentionally removed, first compare it to the saved
`windows-proxy-audit` snapshot and remove only that exact GS-179 row.
No certificate rollback is required.

### Live and isolated validation

After setup, `code/tools/local/gs179-laptop-server.sh health` reported
PostgreSQL durability PASS, caregiver HTTPS PASS, local backend PASS, and
`LAPTOP_LAN_ENDPOINT_TLS_READY=PASS` with a verified CA/IP-SAN HTTPS request
from WSL through the Windows endpoint. It correctly reported
`PHONE_LAN_REACHABLE=NOT_VERIFIED`. Hub ingress remains implemented but
default-disabled: `HUB_INGRESS_AUTOSTART=DISABLED`,
`HUB_IDENTITY_AUTHENTICATED=NO`, freshness UNKNOWN and
`PERSISTENT_HUB_INGRESS=NOT_CONFIGURED`.

`code/tools/local/gs179-laptop-server.sh browser` returned HOST_SIM_PASS
against the live laptop HTTPS caregiver API. It logged in, read the same
PostgreSQL-backed authorized Home, rendered the existing source-linked
TEST_ONLY event once after reload, and displayed stale source/UNKNOWN
monitoring. EventKey:
`{"physical_device_id":"test-c3-bedroom","logical_node_id":"bedroom","origin_session_id":10,"event_sequence":1}`.
Event kind/room were MOTION/bedroom; provenance was HOST_SIM TEST_ONLY.
This is not a real Node, Hub, phone, or PIR event.

The registered `make -C code gs179-postgres-e2e` run passed **52/52** with
the isolated local PostgreSQL database, including source-linked Node/Hub
HOST_SIM, durable commit/retry/restart/caregiver projection, listener and
authority negatives, runtime lifecycle, and the added dormant-portproxy
regression. The two previously stale browser-helper cases passed directly
(2/2) after updating selectors to the current four-tab navigation and
asserting its current fail-closed UNKNOWN state. The independent focused
`test_gs179_postgres_security.py` suite passed 15/15. Shell and Node syntax
checks and `git diff --check` passed. Initial direct focused invocations
without the repository's backend/support Python paths failed at import time;
the registered Make target supplied those paths and completed successfully.

No phone-side reachability probe, APK installation, S3 authentication,
persistent Hub-ingress activation, customer enrollment, physical board
operation, or PIR stimulus was performed. The current Windows DHCP lease is
short-lived; a stable router reservation or hostname would require separate
network-owner approval if the endpoint changes before phone validation.

### Source-matched local-LAN APK — 2026-10-22

The existing GS-177 Android workflow was manually dispatched with
`backend_origin=https://192.168.1.6` and
`gs179_local_lan_test_only=true` against source commit
`8c134487a4afdde0869aad0e0c5b9c9b19f1b544`.
[GitHub Actions run 39766494060](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39766494060)
completed SUCCESS. Artifact
[parivar-saathi-caregiver-debug-8c134487a4afdde0869aad0e0c5b9c9b19f1b544](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39766494060/artifacts/12420842385)
(ID 12420842385, 14-day retention) was downloaded and checked locally.

Artifact contents:

- APK: `parivar-saathi-caregiver-debug.apk`, 2,929,936 bytes,
  SHA-256 `ab61481bbdaf9b8d98b86b0c67ef8b7bdfb10be0605dc4a425f6343de03754f9`.
  `sha256sum --check` and APK ZIP integrity checks passed.
- Package `in.gharsajag.caregiver`, version name
  `0.4.0-connected-lite-staging`, version code 3, existing Parivar Saathi app.
- Origin `https://192.168.1.6`, local-LAN TEST_ONLY enabled, CA SHA-256
  `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
- CI `apksigner` verified one RSA-2048 debug signer. Certificate SHA-256
  `58f9d58042af12a1eca6b4fadd8bb836e3b04220995fb710ad3eac0d1b1972ac`.
  This is a runner-generated debug key, not the installed APK's verified
  signer or a production signing key; an update-signature conflict may require
  uninstall/reinstall and a new sign-in.
- Workflow gates passed: PWA browser/offline 4 tests and 92 rendered cases;
  registered caregiver API 20, Android dashboard 10, and voice prototype 26;
  Android debug unit/build/signature/artifact stages. Validation reported
  SOFTWARE PASS, PHYSICAL NOT_RUN.

The physical phone was not accessed and the APK was not installed. Current
Windows DHCP lease has no confirmed reservation and may change; if it changes,
recheck the certificate/SAN and rebuild against the new verified origin before
phone-side login. No PIN, TLS-validation bypass, or untrusted certificate was
introduced.

A separate live caregiver browser rerun initially got a transient
`route.fetch: socket hang up` on the Windows forwarded `/devices` request while
a read-only proxy audit was also running. The service health/TLS checks stayed
PASS; the browser rerun by itself passed with the same EventKey and no source
change. The transient was not reproduced.

## 2026-10-22 — router-independent TEST_ONLY reconnect implementation

This follow-up adds a reusable reconnect path for the existing laptop host and
Parivar Saathi app. It remains TEST_ONLY and leaves the commercial release
origin and trust configuration unchanged. The Android app can restore a
previously paired `https://<computer-name>.local` origin or use an explicit
private IPv4 fallback in the bundled reconnect flow. It persists the selected
origin, while WebView continues normal TLS hostname and certificate
verification. Address discovery is never treated as authentication. The
caregiver server permits the `.local` HTTPS origin only under its explicit
TEST_ONLY LAN setting.

The Windows helper now reads the active Wi-Fi IPv4 and current WSL2 address and
can retarget only its owned portproxy/firewall configuration. A bounded,
opt-in watcher is available for operator activation but was not registered:
the current Windows session is not elevated. No broad firewall rule, router
change, server restart, or phone operation was performed.

At final read-only inspection, Windows was connected to `Airtel_Agrim` at
`192.168.1.8/24` and WSL2 was `172.17.152.10`. PostgreSQL, caregiver HTTPS and
local service checks were healthy. The existing Windows portproxy still
targeted the previous `192.168.1.6`, so
`LAPTOP_LAN_ENDPOINT_TLS_READY=FAIL`; phone reachability remains NOT_VERIFIED.
The server certificate covers the stable computer-name `.local` origin. The
stale route was left unchanged to preserve the live network/server state. No
phone-side Yogi → Agrim → Yogi test has been performed.

Focused validation on this source passed: PWA runtime JS 10/10; caregiver API
22/22; GS-179 security 18/18; source-linked GS-179 PostgreSQL E2E 55/55;
GS-177 connected-lite runner (22 API tests, 10 JS tests, 3 source scenarios,
10 runtime checks); validation framework 51/51; feature coverage and
traceability; PWA browser 4/4 tests and 92/92 rendered checks; and GS-178
caregiver integration 33/33. Python, Node, shell and JSON syntax checks and
`git diff --check` passed. The broader backend/PWA aggregates retain the
existing mandatory P0 `product_status=PARTIAL`, diagnostic-foundation's
stale-stage registration assertion, and an initial offline-browser attempt
that lacked the Python `websocket` dependency; the isolated browser target
passed after that dependency was supplied outside the repository. These
results were not suppressed or altered. Local Gradle and ADB are unavailable,
so the updated combined APK was not built. Physical phone, Hub and PIR
validation remain NOT_RUN.

This is the Wi-Fi source checkpoint only. GS-177 UX commit integration is
deferred until this checkpoint is committed and pushed. Starting local and
remote HEAD was `aeb2ab52a4f1c0e286817b77026d4fe13f03580b`; pre-existing
untracked and ignored assets remain preserved.
