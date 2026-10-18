# Parivar Saathi caregiver Android app

## Current build scope

The Android app starts the existing shared PWA bundled in the APK. It does not
show a server-address form. The app label is **Parivar Saathi**; launcher,
adaptive, round and monochrome icons use the approved family/home/shield mark.
The Android launch splash combines that mark with the supplied Parivar Saathi
wordmark and tagline. The PWA header and install manifest use the same logo and
brand spelling.

The app can start without a network and shows an explicit unavailable state
without inventing household status. With the configured staging HTTPS origin,
the shared PWA provides Connected Lite authentication and TEST_ONLY caregiver
views. This does not provide physical Hub monitoring or resident status.
Notifications, incoming calls and S3 WebRTC remain unavailable and unqualified.

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
simulator or local development server. The release build does not allow the
debug endpoint option. No secrets, Firebase configuration or signing key belong
in Gradle properties committed to this repository.

## Hosted APK and install

The Connected Lite workflow
`.github/workflows/gs177-android-dashboard-apk.yml` runs JDK 17, Gradle 8.9,
Android SDK 35 and Build Tools 35.0.0. It checks the logo provenance and Android
resource dimensions, runs the PWA runtime and Kotlin origin tests, builds the
debug APK, verifies its signature and APK resources, writes `SHA256SUMS` and
build metadata, and uploads the artifact for 14 days. The signing key is
runner-generated and testing-only unless an owner-controlled pilot key is
separately configured.

After the workflow succeeds, download
`parivar-saathi-caregiver-debug-<commit-sha>` from that run. Verify the APK with
the included `SHA256SUMS`, uninstall any earlier debug APK signed by another
runner key, then install the new APK on Android API 26 or later. Launch
**Parivar Saathi**; it opens the bundled UI immediately, including when the
phone has no network. With an approved backend origin, the shared PWA uses the
authenticated Connected Lite API for caregiver views; the server-verified
TEST_ONLY admin role also exposes Simulation Lab and the existing GS-124
Engineering areas. These views do not imply physical monitoring or resident
well-being.

## Current integration limits

Simulation runs use the existing host scenario engine and persist with
TEST_ONLY provenance. They do not execute on an S3 Hub or exercise production
GS-148 ingress. The Render Free service still needs its source branch migrated
to canonical before this canonical revision can be deployed there. Backend
deployment and mobile-data phone acceptance are not claimed here.

FCM and call signaling remain prototypes. Notifications, incoming calls and
WebRTC media are not enabled in this APK. Older canonical Android call
experiments are preserved under `prototype/android/` and excluded from the
compiled application. No persistent pilot signing key is configured, so a
runner-generated debug APK may require uninstalling an earlier APK before
update.

The hosted runner can prove build and packaging only. It cannot prove a physical
phone install, live HTTPS login, mobile-data operation, FCM display/answer, or
Hub-to-phone audio. Keep GS-177 open until those real acceptance gates pass.
