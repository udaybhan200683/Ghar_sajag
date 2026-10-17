# Parivar Saathi caregiver Android app

**Current artifact scope:** installable Android **dashboard-only test build**. It
loads the existing remote Parivar Saathi PWA in a WebView after the user enters
an approved HTTPS service origin. It contains no local caregiver account, sample
dashboard, simulated backend, or `example.invalid` runtime default. The configured
origin is persisted locally; HTTPS navigation is restricted to that host, HTTP
and mixed content are disabled, SSL errors are rejected, third-party cookies and
privileged JavaScript bridges are not enabled, and WebView permissions are
denied.

Push notifications, FCM token registration, call invitations, microphone access,
WebRTC, automatic abnormality calling and backup escalation are **disabled and
not included in the dashboard APK**. The imported Android call classes are kept
under `prototype/android/`, outside the Gradle app source tree; signaling and
FCM files remain prototype source only. Production identity/session issuance, current Home role
and epoch checks, revocation, a live authenticated HTTPS deployment, durable call
management, TURN credentials and S3 Hub media are still upstream dependencies.
No screen or local state in this APK substitutes for those services.

## Hosted build and install

The isolated GS-177 branch workflow
`.github/workflows/gs177-android-dashboard-apk.yml` builds with JDK 17, Gradle
8.9, Android SDK platform 35 and Build Tools 35.0.0. It runs the Kotlin
origin-validation unit tests, builds the debug APK, verifies its Android debug
signature, writes `SHA256SUMS` and source/build metadata, and uploads the
artifacts for 14 days. It also runs the separately registered call-signaling
prototype contract tests and JavaScript/XML checks. The workflow uses no
repository secrets and no Firebase configuration.

After a successful run, download and unzip the artifact named
`parivar-saathi-caregiver-debug-<commit-sha>` from that GitHub Actions run. On an
Android device with API 26 or later:

1. Verify the downloaded APK against the included `SHA256SUMS` file.
2. Open the APK and allow installation from that file source if Android asks.
3. Launch **Parivar Saathi** and enter the real HTTPS domain supplied by the
   Ghar Sajag service owner. Do not enter a simulator, localhost, test domain,
   or an unapproved server.
4. The app opens that server's existing PWA. PWA authentication, authorization,
   data freshness and available screens come from the server and must be
   verified there; this build does not create or grant a caregiver session.

This is a runner-generated Android **debug-signed testing APK**, not a
pilot/release-signed binary. The runner's debug signing key is not retained or
committed. Keep the exact artifact for reinstall; a later build signed by a
different runner key will not update it in place. Uninstall the prior debug app
before installing an APK with a different signing certificate. No keystore or
private signing key is stored in this repository.

## Local build

Install JDK 17, Android SDK platform 35 and Build Tools 35.0.0, then run from
`android/`:

```sh
gradle --no-daemon :app:testDebugUnitTest :app:assembleDebug
```

The output is `android/app/build/outputs/apk/debug/app-debug.apk`. The APK opens
the server configuration screen because no service endpoint is embedded. This
build command is reproducible from the pinned Gradle/plugin/SDK versions, but
the runner-generated debug signing key is intentionally not reproducible or
reused.

`verify.sh` runs the isolated signaling/provider prototype tests and JavaScript
syntax/XML checks. Those tests do not qualify the Android APK, production auth,
FCM delivery, deployed backend, S3 media or full product behavior.
