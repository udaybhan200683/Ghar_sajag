# Parivar Saathi caregiver Android app

## Current build scope

The Android app starts the existing shared PWA bundled in the APK. It does not
show a server-address form. The app label is **Parivar Saathi**; launcher,
adaptive, round and monochrome icons use the approved family/home/shield mark.
The Android launch splash combines that mark with the supplied Parivar Saathi
wordmark and tagline. The PWA header and install manifest use the same logo and
brand spelling.

The app can start without a network and shows the familiar Home, Devices,
Reports and Settings navigation with an explicit **Offline / Unable to connect**
state. It contains no cached or simulated household status. Monitoring,
notifications and calls remain unavailable until an authenticated caregiver
service exists. Production sign-in, current-Home authorization, persistent
household APIs, FCM delivery and S3 WebRTC are not implemented or qualified by
this dashboard build.

The approved logo was copied to `branding/source/Parivar_Saathi_Logo.png` from
the owner-provided GS-40 source. Regenerate the PNG resources with:

```sh
python3 branding/generate_parivar_saathi_assets.py
```

The generator uses Python's standard library. It does not alter the source logo.
The monochrome notification image is a resource only; FCM and Android
notifications are disabled.

## HTTPS origin configuration

The origin is an internal build setting, never an in-app prompt. Builds reject
HTTP, local/reserved hosts, credentials, paths, query strings, fragments and
nonstandard ports. A debug endpoint can be supplied as a Gradle property:

```sh
gradle --no-daemon -PcaregiverDebugBackendOrigin="$CAREGIVER_API_ORIGIN" \
  :app:testDebugUnitTest :app:assembleDebug
```

Set `CAREGIVER_API_ORIGIN` locally to an approved HTTPS service domain, not a
simulator or local development server.
The current PWA runtime still sets `caregiverApiConfigured=false`; adding an
origin alone does not enable login or fetch household data. The default build
therefore remains honestly offline. The release build does not allow the debug
endpoint option. No secrets, Firebase configuration or signing key belong in
Gradle properties committed to this repository.

## Hosted APK and install

The isolated workflow
`.github/workflows/gs177-android-dashboard-apk.yml` runs JDK 17, Gradle 8.9,
Android SDK 35 and Build Tools 35.0.0. It checks the logo provenance and Android
resource dimensions, runs the PWA runtime and Kotlin origin tests, builds the
debug APK, verifies its signature and APK resources, writes `SHA256SUMS` and
build metadata, and uploads the artifact for 14 days. The signing key is
runner-generated and testing-only.

After the current GS-177 branch workflow succeeds, download
`parivar-saathi-caregiver-debug-<commit-sha>` from that run. Verify the APK with
the included `SHA256SUMS`, uninstall any earlier debug APK signed by another
runner key, then install the new APK on Android API 26 or later. Launch
**Parivar Saathi**; it opens the bundled UI immediately, including when the
phone has no network. The startup UI does not imply live monitoring, household
authorization, notifications or calling.

The hosted runner can prove build and packaging only. It cannot prove a physical
phone install, live HTTPS login, mobile-data operation, FCM display/answer, or
Hub-to-phone audio. Keep GS-177 open until those real acceptance gates pass.
