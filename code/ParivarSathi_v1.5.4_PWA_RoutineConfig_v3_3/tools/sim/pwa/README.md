# Parivar Sathi PWA Prototype

A responsive, installable web app/PWA prototype for the Parivar Sathi family-care dashboard.

## What is included
- Responsive Home / Devices / Reports / Settings screens.
- Mobile and laptop layouts from the same codebase.
- Away toggle with Home Safety mode behavior.
- Normal and attention-required Home states.
- Device active/inactive, battery percentage, estimated time left, last-updated time.
- Recent important events.
- Weekly report view and insights.
- Local persistence using `localStorage`.
- Browser notification permission and local notifications while the app is open.
- Service worker for installability/offline shell.
- Pilot simulation controls temporarily shown on the left side of the Home page for verification.

## Run locally
Service workers/PWA installation require HTTP/HTTPS, not `file://`.

From this folder:

```bash
python -m http.server 8080
```

Then open:

http://localhost:8080

For phone testing on the same Wi-Fi, use the PC LAN IP, for example:

http://192.168.1.20:8080

Some PWA features require HTTPS, so for a true installable pilot deploy to an HTTPS host.

## Install on Android
Open the HTTPS deployment in Chrome, then use:
Menu → Add to Home screen / Install app.

## Integration with your public site
Current marketing site:
https://ghar-sajag.rahuljnvakg.chatgpt.site/

Recommended structure:

- Public marketing site remains the landing page.
- Add a prominent `Open Family Dashboard` button.
- Point that button to the deployed PWA, for example:
  `https://app.your-domain.in/`
- In this prototype, Settings already includes a link back to the public site.

Suggested button markup for any editable HTML site:

```html
<a class="dashboard-cta" href="https://app.your-domain.in/">
  Open Family Dashboard
</a>
```

## Pilot backend integration
Replace local state in `app.js` with backend API/WebSocket/MQTT-to-cloud data.

Recommended flow:
ESP32 nodes → Hub → HTTPS/MQTT backend → PWA API/WebSocket

The browser should never connect directly to ESP32 devices over the public internet.

Suggested backend fields:
- `home_status`
- `away_mode`
- `morning_routine`
- `iam_ok`
- `main_door`
- `last_indoor_activity_at`
- `night_bathroom_visits`
- `devices[]`
- `events[]`

## Important limitation
This package is a front-end pilot. True background push notifications when the PWA is closed require a backend Web Push implementation (VAPID keys + push subscriptions + server push). The included browser notification demo works while the app is running and permission is granted.


## Battery-status behavior
Low/critical battery is shown as a highlighted maintenance warning in the
**Device health** card and the Devices screen only. Battery level alone does
not change the main Home banner to **Attention needed**.

The main care/safety status remains positive unless there is a care/safety
condition such as a missed routine, missing check-in, unusual night activity,
door/safety issue, or monitoring coverage lost because a device is offline.


## Verification build v5
- Reset returns all simulated scenarios to PASS.
- Simulation controls inject negative scenarios only.
- Added low-battery simulation for Bathroom Node.
- Low battery changes Device Health to bad/red, but does not affect the main Home banner.
- Away mode disabled temporarily.
- New local-storage key avoids stale negative state from older builds.


## Verification build v6
- Every scenario button is now a true **toggle**:
  - first press: PASS → negative
  - second press: negative → PASS
- Applies to morning routine, I am OK, main door, night activity, and battery health.
- Battery health still never changes the main Home care/safety banner.
- Every scenario transition writes a new **Recent Important Event** with the current timestamp.
- Recent events are sorted newest first automatically.
- Reset returns all scenarios to PASS and starts a fresh event history with a reset confirmation.
