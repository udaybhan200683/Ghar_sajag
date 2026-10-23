# GS-179 DNS-SD automatic discovery investigation — 2026-10-23

## Scope and starting checkpoint

Owning Jira: GS-179 (In Progress). Related UI evidence: GS-177 five-reference
caregiver refinements, already integrated on the canonical branch. Current
branch is `feature/r1-commercial-baseline`, starting HEAD
`f023319ec1e49bf69e27e314a964b1ab43812367`, and `origin` matched that SHA at
task start. The tracked worktree was clean. Existing untracked build outputs,
reference images, alternate-stream files, and physical evidence are preserved.

`BUG_CLASSIFICATION=R1_FIX`
`REQUIREMENT_SOURCE=GS179-LAN-01 in MASTER_TRACEABILITY.csv; user-provided GS-179 acceptance scope`
`DECISION_IDS=NONE`
`TASK_SCOPE=Diagnose/fix TEST_ONLY Windows DNS-SD advertisement and Android paired-laptop discovery; add failure diagnostics; preserve verified manual-IP access; reuse integrated GS-177 UI; build one combined TEST_ONLY APK.`
`OUT_OF_SCOPE=Backend redesign; TLS bypass or CA changes; production security changes; Windows profile/firewall/portproxy edits; persistent privileged watcher activation; app uninstall/data clear; Hub, board, PIR or credential operations.`

Affected components/interfaces: Windows TEST_ONLY advertiser in
`code/tools/local/gs179-windows-mdns-advertiser.ps1`; Android foreground NSD,
resolver, IPv4 selection, TLS readiness probe, endpoint/SPKI store, and WebView
origin in `code/parivar_saathi_android_app/android`; existing shared PWA UI and
its browser regressions. Hub, Node, backend API and caregiver identity contracts
are not changed.

## Existing evidence and audit findings before edits

- Owner reports worker PID 9192 alive, Windows Wi-Fi profile `Private`, Windows
  and WSL HTTPS checks passing, manual `https://192.168.1.8` login/Home loading
  passing, `Use paired laptop` failing with `Failed to fetch`, and no entries in
  the `ParivarSaathiLan:I` logcat filter.
- Latest prior GS-179 evidence (Jira comment 11589 and
  `GS179_LOCAL_WSL2_ANDROID_HOST_20261020.md`) only established manual-IP phone
  success. It explicitly left automatic DNS-SD and Yogi → Agrim → Yogi NOT_RUN.
- The Windows worker currently catches ordinary `DnsServiceRegister` failures
  and retries silently; callback failure status is discarded. A live process
  therefore proves only that its loop is running.
- Android currently has no success-stage logs for NSD start/found/resolved,
  service/TXT rejection, IPv4 selection, TLS/SAN/SPKI/readiness rejection, or
  endpoint persistence. Several resolve/stop/network callback errors are also
  swallowed. A zero-line filtered log is not evidence that NSD is disabled or
  that Windows registration succeeded.
- `Use paired laptop` cleared the saved working endpoint and immediately loaded
  the configured `.local` origin, before the asynchronous DNS-SD flow had
  resolved and verified an IP endpoint. This makes the WebView request fail
  while discovery is pending or when discovery does not complete. It also
  cleared the saved SPKI pin. Manual endpoint selection still uses the existing
  platform CA/hostname validation.
- The canonical branch already contains the GS-75 UI-branch five-reference
  refinement source and tests (commit `ec1c450` equivalent to the source change
  in the GS-75 UI branch). The remaining canonical UI diff adds later evidence;
  no stale UI-branch code will be replayed over current GS-179 discovery work.
- The existing Android manifest grants network state, Wi-Fi state and multicast
  receive permissions only in the TEST_ONLY source set; its network security
  config still requires system trust plus the local TEST_ONLY CA. The app still
  cancels all WebView TLS errors.

## Validation plan

Existing prior-feature suites: GS-179 PostgreSQL/security and lifecycle
regressions; GS-177 connected-lite API/runtime and PWA/browser regressions;
Android dashboard/API/voice component stages; Android unit tests and APK build;
GS-116/GS-130 feature and traceability framework. Add deterministic tests for
IPv4 byte ordering, service/TXT acceptance and rejection, bounded IPv4 candidate
selection, endpoint/SPKI continuity, and diagnostic reason classification.

Run the affected registered GS-179 and caregiver-app suites, PWA browser suite,
Android Gradle tests/build through the repository workflow, and feature coverage
mapping. Hardware/phone Yogi → Agrim → Yogi, Android mDNS visibility, installed
APK compatibility, real Hub identity and real PIR remain separate physical
acceptance items; do not mark them PASS from host/CI evidence.

## Safety and release impact

This is a TEST_ONLY local discovery fix and diagnostics change. Preserve platform
certificate-chain and hostname checks, the expected laptop DNS SAN, IP SAN,
persisted SPKI comparison after first verified discovery, bounded private IPv4
probing, database readiness, and the existing manual-IP HTTPS path. No persistent
watcher, profile/firewall/portproxy mutation, app installation, data clear, or
hardware access is in scope. The updated APK is a candidate for owner-run
physical acceptance, not release qualification.

## Execution results

### Root cause and implementation

- Confirmed code-path cause for the immediate `Failed to fetch`: the paired-
  laptop action threw away the phone's working manually selected IP, switched
  the WebView to the raw `.local` host, and reloaded before NSD had completed
  service resolution, certificate checks, key continuity and `/readyz`.
  Android's DNS-SD browse is asynchronous; the WebView's ordinary HTTPS request
  is not the discovery result. The action now retains the working origin and
  asks the foreground NSD client to restart. The origin changes only when the
  existing platform TLS, expected DNS SAN, saved SPKI and database readiness
  checks succeed. The saved key remains in place.
- Added TEST_ONLY stage diagnostics from app foreground/network callback through
  browse start, no-expected-service timeout, found/lost, resolve and TXT checks,
  private IPv4 selection, HTTPS CA/IP-hostname/DNS-SAN/SPKI/readiness stages,
  endpoint persistence and delivery. Registration errors and callback failures
  now appear in an atomic read-only Windows status record.
- Verified the byte-order hypothesis against Microsoft's `IP4_ADDRESS`
  definition: Windows expects host byte order. The original conversion was
  correct and was retained. The policy check asserts the host-order values for
  `192.168.1.8` and `10.20.30.40`.
- The active Windows worker was stopped and restarted to load status reporting.
  Current status: PID 4280, state `REGISTERED`, service
  `GharSajag-GS179-desktop-3qqu64b._https._tcp.local`, IPv4 `192.168.1.8`,
  interface index 18, `DnsServiceRegister` return 9506 (`DNS_REQUEST_PENDING`),
  registration callback status 0, and no persistent privileged task. This is
  Windows registration evidence only; it does not establish phone visibility.
- No `adb` executable/device is available in this environment. Android phone
  browse/resolve and Yogi → Agrim → Yogi therefore remain NOT_RUN until the
  owner exercises the combined APK and supplies its `ParivarSaathiLan` log.
- The GS-75 UI refinements already present on the canonical branch are retained
  unchanged in the combined build. No historical branch files were copied.

### Local validation before hosted CI

At this initial checkpoint, hosted combined regressions and APK verification
were pending. No physical phone, app install, data clear, privileged watcher,
firewall or production-security changes were performed.

Executed before APK workflow dispatch:

- Windows `-Action Validate`: PASS, 14 RFC1918/profile cases, service record
  construction and host-order `IP4_ADDRESS` values; it opened no socket or
  registration. Microsoft documents `IP4_ADDRESS` as a DWORD in host byte
  order. The initial test invocation without a DSN failed at the explicit
  `GS179_TEST_POSTGRES_DSN` guard (exit 2); it did not create a schema. Using
  the documented local TLS fixture and per-test random schemas, the full
  `make -C code gs179-postgres-e2e` rerun passed 55/55 in 388.797 seconds.
- `python3 code/validation/run_gs177_connected_lite.py`: PASS, 22 API tests,
  3 scenarios and 10 shared runtime tests.
- `GS177_BACKEND_ORIGIN=https://desktop-3qqu64b.local
  GS177_LOCAL_LAN_TEST_ONLY=1 python3 code/validation/run_gs177_android.py`:
  source and branding checks PASS; shared PWA runtime 10/10 PASS. Local APK
  build stopped at `dependency=gradle` (exit 127); this environment has no
  Gradle/Android SDK, so the hosted workflow is required for unit tests/build.
- `make -C code feature-coverage-test`: PASS, 225 feature rows, 280 source
  modules, 26 physical cases, and traceability checks 22/22.
- Windows PowerShell parse/policy execution, Bash syntax, Python byte-compilation
  of the source gate, and `git diff --check`: PASS.
- The current worker (PID 4280) remains registered with callback status 0 and
  API pending status 9506. `adb` is unavailable on both WSL and Windows. No
  phone browse result is claimed. Browser regression and Android Gradle tests
  were pending at this checkpoint; the completed hosted results follow below.

### Combined regressions and deliverable APK — 2026-10-23

The push-triggered default-origin workflow
[39887820771](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39887820771)
completed SUCCESS on source `dce8a52e6a294c40d6f8fe949430418c54042a3c`. Its
browser and registered caregiver/Android stages, Android unit tests, APK
assembly, signature verification and artifact upload passed. Its default
staging-origin APK is not the GS-179 deliverable.

The explicit Local-LAN TEST_ONLY workflow
[39887837848](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39887837848)
completed SUCCESS on that same source with origin
`https://desktop-3qqu64b.local` and `GS177_LOCAL_LAN_TEST_ONLY=1`. Results:

- PWA browser regression: 92/92 rendered assertions PASS, including
  authenticated caregiver, offline, session gating and connected-lite browser
  cases.
- Registered caregiver gates: connected-lite API 22 PASS, Android dashboard
  19 PASS, voice prototype 28 PASS.
- Android `:app:testDebugUnitTest` and `:app:assembleDebug`: PASS.
- APK signature scheme v2 verification, SHA-256 verification and upload: PASS.
- `make -C code feature-coverage-test`: 225 feature rows, 280 source modules,
  26 physical cases and 22/22 mapping checks PASS. Earlier local GS-179
  PostgreSQL E2E (55/55), connected-lite API/runtime (22 API, 3 scenarios,
  runtime 10/10), Windows policy validation (14/14) and source/branding checks
  are recorded above.

The one deliverable is
[`parivar-saathi-caregiver-debug.apk`](GS179_DNSSD_AUTODISCOVERY_20261023/apk/parivar-saathi-caregiver-debug.apk)
(2,962,184 bytes), artifact ID `12473876313`, source `dce8a52e`, package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, TEST_ONLY
origin `https://desktop-3qqu64b.local`, local CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`, and APK
SHA-256
`0ae141221233ba39a997396bb496a818250668ccf1b4d354372dad5add630c80`.
The runner-generated debug signer fingerprint is
`61710682d9c43052a1e1f07dbe6fef7ae7671391d82335d91b61bd0cf3a564cf`. Its
compatibility with the APK installed on the physical phone has not been
checked; earlier installed-build evidence records a different signer. The
APK was not installed, and the working app was not uninstalled or cleared.

Windows DNS-SD registration remains host-verified only: API return 9506
(`DNS_REQUEST_PENDING`), callback status 0, service
`GharSajag-GS179-desktop-3qqu64b._https._tcp.local`, address `192.168.1.8`,
interface 18. Android phone browse/resolve and Yogi → Agrim → Yogi remain
NOT_RUN because no phone/ADB access is available here. This workflow reports
`PHYSICAL NOT_RUN`; its Android tests do not prove phone multicast visibility.
The persistent privileged watcher remains unregistered, and no network,
firewall, forwarding, production-security, device or app-data changes were
made.

### Next physical acceptance checkpoint

Before installing this artifact, compare its signer to the currently installed
package or arrange an owner-approved signing path that preserves the working
app. Do not uninstall or clear data. With a compatible install path, capture
`ParivarSaathiLan` logs while checking service discovery, resolution, TXT
validation, IPv4 selection, TLS/SAN/SPKI, `/readyz`, endpoint persistence and
the Yogi → Agrim → Yogi transition. Save device observations and logs without
credentials, cookies or certificate private keys. A successful Windows
registration and this APK's CI PASS are not phone-discovery PASS.

### Side-by-side discovery acceptance APK preparation — 2026-10-23

The canonical source already contains the approved GS-75 interface and the
corrected GS-179 discovery path. No prior UI branch was replayed. The current
build change is confined to the explicit GS-179 local-LAN debug profile:

- Commercial and ordinary debug/release builds retain
  `in.gharsajag.caregiver`; only this profile uses
  `in.gharsajag.caregiver.discoverytest` and the launcher label
  `Parivar Saathi TEST_ONLY`. Android therefore treats it as a separate app
  with separate preferences; it does not replace the installed commercial
  package.
- TEST_ONLY APK signing now requires a dedicated persistent PKCS#12 key. Its
  public certificate fingerprint is pinned in source and checked against the
  built APK. The encrypted identity is kept outside the repository in
  `/home/udaybhan/.config/ghar-sajag/gs179-discoverytest-signing` (directory
  mode 0700; private files mode 0600) and in GitHub Actions encrypted secrets
  named `GS179_DISCOVERY_TEST_*`. No signing key or password was committed or
  printed. Its signer certificate SHA-256 is
  `d336ae68479da03de932a44b16c8de730c86e3cf68aee52fe92261e74e596b85`. No
  production signing secret was changed.
- The existing HTTPS CA trust, IP SAN and expected laptop DNS SAN checks,
  saved SPKI continuity, caregiver authentication/Home authorization and
  manual-IP fallback were not changed. Certificate verification remains
  mandatory.

Pre-build validation on base `c8ad185b235cd73346e3bc90501cbcb56d8b2853`:

- `make -C code feature-coverage-test`: PASS, 225 feature rows, 280 modules,
  26 physical cases, 22/22 traceability checks.
- Python byte-compilation, `suites.json` parsing, workflow YAML parsing and
  `git diff --check`: PASS.
- Hosted Android/browser regression and APK build are pending push. Local
  Gradle/Android SDK and ADB are unavailable here; no APK was installed and no
  phone app data/settings were touched.
- Physical Agrim discovery is NOT_RUN. The required first handset attempt is
  the side-by-side APK on Agrim with “Use paired laptop”, without entering a
  laptop IP. DNS-SD reception must be assessed from `SERVICE_FOUND` and
  `SERVICE_RESOLVED_VALID`; TLS/readiness is a later result requiring
  `HTTPS_PROBE_VERIFIED`, followed by endpoint delivery and authorized login.

Capture Android diagnostics without clearing the log buffer:

```bash
adb devices -l
adb install -r parivar-saathi-discoverytest-debug.apk
adb shell pm list packages | grep in.gharsajag.caregiver
adb logcat -v threadtime -s ParivarSaathiLan:I > gs179-agrim-discovery.log
```

With the log capture running, launch the app named **Parivar Saathi TEST_ONLY**
and select **Use paired laptop** without configuring an IP. `SERVICE_FOUND` and
`SERVICE_RESOLVED_VALID` prove Android received and validated the DNS-SD
record/TXT data; they do not prove HTTPS. `HTTPS_PROBE_VERIFIED` records
platform CA/IP-hostname, laptop DNS SAN, saved SPKI continuity (or first-use
pin establishment) and `/readyz` success. `ENDPOINT_SAVED` and
`VERIFIED_ENDPOINT_DELIVERED` prove endpoint persistence/delivery; caregiver
login and authorized Home are a separate acceptance result. Keep the original
commercial package installed throughout.

Only after Agrim passes those separate discovery and secure-readiness checks,
continue Yogi → Agrim → Yogi on the TEST_ONLY app and retain the same test-app
data. The persistent privileged network watcher remains unregistered and
requires separate explicit approval. Physical Hub/PIR operation is not part of
this task.
