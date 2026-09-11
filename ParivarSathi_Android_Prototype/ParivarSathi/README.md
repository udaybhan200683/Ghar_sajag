# Parivar Sathi Android prototype

Jetpack Compose Android Studio project based on the supplied Home, Alert, Devices, Reports, and Settings layouts.

## Included interactions
- Bottom navigation between Home / Devices / Reports / Settings.
- Away toggle switches the Home screen into home-safety monitoring mode.
- Home demo can switch between normal and alert scenarios.
- Device cards are tappable and expand to show basic details.
- Reports period selector works (Today / This Week / This Month UI state).
- Settings rows are tappable and show prototype dialogs.
- Battery state, device status, estimated remaining time, and last-updated text are represented.

## Run
1. Open this folder in Android Studio.
2. Let Gradle sync.
3. Run on an Android emulator/device (minSdk 26).

## Next integration step
Replace the in-memory mock state in `MainActivity.kt` with real ESP32/Hub data over your chosen backend (MQTT, HTTPS/REST, WebSocket, Firebase, etc.).

The supplied reference PNGs are included at the project root for comparison; the UI itself is implemented natively in Compose rather than embedding the screenshots.
