# Ghar Sajag: hardware-independent verification

Code release **1.5.4**, local simulation addition to reference 1.4.2. Documentation edition 2.0 remains your engineering baseline; this guide and `docs/SIMULATION_LLD_v1.0.md` describe the new adapter. Immediate scope is **Base / Parivar Saathi P0**.

## What changed

Previously, `make verify` ran separate component tests and a small C++ simulation. The sample app used hard-coded data and its incident buttons were not connected. Passing those tests did not establish an integrated sensor-to-browser workflow.

This release adds a local web laboratory that executes the existing C++ node and hub components, serializes their cloud events into the existing Python JSON API adapter, and displays the actual backend snapshot. Caregiver buttons call the existing incident API over HTTP. It does not replace the domain algorithms with a JavaScript imitation.

You can now verify a connected subset of P0, plus run all previously supplied component suites. **This is not complete acceptance of every P0 requirement.** Onboarding, configuration rollout, OTA, durable restart recovery, production authentication, provider delivery and full prompt/grace orchestration are not completed end-to-end flows. AI interaction remains outside this Base lab.

## 1. Install tools once

These package-install commands assume Ubuntu 24.04 or newer.

Use the **Ubuntu terminal** from the Windows Start menu if you installed WSL. Do not use Git Bash for these commands. If you installed Linux as a separate operating system, boot Linux and use its terminal instead.

```bash
sudo apt update
sudo apt install -y build-essential python3 nodejs unzip
make --version
g++ --version
python3 --version
node --version
```

Use Python 3.10 or newer and Node 18 or newer. `build-essential` supplies the host compiler and Make. No ESP-IDF, ESP32 board, Docker, MQTT broker, npm installation or cloud account is required for the lab.

Reference: [Ubuntu build-essential](https://packages.ubuntu.com/en/noble/build-essential).

## 2. Extract the new code separately

Keep your documentation v2.0 package. Extract the new ZIP into your existing `firmware` folder so the result is:

`F:\Home_risk_alert\Ghar_sajag\firmware\ghar_sajag_reference_v1_5_4\Makefile`

Do not merge the new folder into `ghar_sajag_reference_v1_3` or overwrite the documentation package. This ZIP contains the complete reference source plus new simulation files; it does not contain the nine Word documents again.

In WSL Ubuntu:

```bash
cd /mnt/f/Home_risk_alert/Ghar_sajag/firmware/ghar_sajag_reference_v1_5_4
ls Makefile SIMULATION_START_HERE.md
```

The `/mnt/f` path is for WSL. In a separately booted Linux installation, use the directory where you extracted the ZIP. Run every command below from the directory containing `Makefile`.

## 3. Run the component and connected checks

Run these sequentially. The original scenario matrix deletes the build directory, so do not use `make -j` or run it concurrently with a lab build.

```bash
mkdir -p logs
set -o pipefail
make verify PRODUCT=base 2>&1 | tee logs/base_verification.txt
make e2e-test PRODUCT=base 2>&1 | tee logs/e2e_verification.txt
make http-e2e-test PRODUCT=base 2>&1 | tee logs/http_verification.txt
```

Expected results:

| Command | What must pass | Scope |
|---|---|---|
| `make verify PRODUCT=base` | 80 C++ checks, 24 Python tests, 10 JavaScript tests, contract checks, four simulator variants, Base product tests | Component and limited composition tests; not full SRD coverage |
| `make e2e-test PRODUCT=base` | JSON `status: PASS`, 68 scenario entries | Connected C++ → Python adapter flows |
| `make http-e2e-test PRODUCT=base` | `Ran 16 tests`, `OK` | Real local HTTP routes, API actions, assets, invalid input and local-origin boundaries; includes running the 68-scenario release suite |

An exit code of zero means the command's assertions passed. Check `echo $?` immediately after a command if unsure. `set -o pipefail` prevents `tee` from hiding a failed Make command. A known-gap observation, such as duplicate reducer evidence, is explicitly described in the case result; it is not a claim that the defect was fixed.

For shared code changes affecting both product profiles, also run `make verify-products`. The connected laboratory is Base-only; the AI profile tests use the existing fake provider/controller.

## 4. Open the working dashboard

```bash
make lab PRODUCT=base
```

Leave this terminal running. On the same computer, open **http://localhost:8765** in Edge, Chrome or Firefox. In WSL, Windows can normally open Linux services using localhost: [Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking).

This is a local address on your computer, not the public Ghar Sajag marketing website. No public website, survey records or customer data is modified.

The page has connected areas for simulated home controls, hub state, an authorised **family/caregiver dashboard**, device health/troubleshooting, notification jobs and backend event timeline. The same dashboard is used whether the authorised responder is a family member or a caregiver; P0 does not require a separate family webpage. There is no user-facing Privacy ON/OFF simulation control; consent/privacy enforcement remains internal. The browser uses the same `buildHomeView`, `incidentActions` and `actionCommand` functions as the existing app. The older `app/public/index.html` remains a static design sample; use the new lab URL for connected testing.

Click **Run release suite** for an automated demonstration. It resets the lab repeatedly and ends in the final test state. Click **Reset scenario** before your own manual test. Download the report using the page link.

Stop with **Ctrl+C**. This also stops the C++ child process. Restart/reset intentionally loses the in-memory scenario state.

## 5. First manual test: normal morning

1. Click **Reset scenario**. Time is `t=1000`.
2. Select **Kitchen**, event **MOTION**, then **Send sensor event**.
3. Confirm hub `Activity seen = true`; the caregiver activity card says kitchen; the backend timeline contains the node event ID.
4. Click **Go to morning deadline**. The clock advances to `t=2300` without waiting 1,300 real seconds.
5. Confirm decision reason `evidence_present` and no missing-activity incident.

Current reference rules accept one qualifying event. Kitchen and pooja qualify in this fixture; Room 1 and entry motion appear in the timeline but do not qualify for this particular morning window. PIR events do not identify a person or prove continuous occupancy.

## 6. Manual failure and caregiver tests

Start each row with **Reset scenario** unless it explicitly continues a previous row.

| Scenario | Your actions | Expected observation |
|---|---|---|
| Quiet but covered | No motion; go to deadline | `no_qualifying_evidence`; one missing-activity incident; primary and backup notification jobs |
| Missing sensor coverage | Disconnect kitchen node; go to deadline | `coverage_unknown`; no missing-activity incident; distinguish unavailable coverage from quiet home |
| Untrusted clock | Distrust clock; go to deadline | `time_untrusted`; no missing-activity incident |
| Resident check-in | Room 1 → OK_PRESSED; go to deadline | `explicit_ok=true`; no missing-activity incident |
| I am OK presentation | Send Room 1 → OK_PRESSED | Recent events show **I am OK** in green with location and elapsed time |
| Call then OK | Send CALL_FAMILY, then OK_PRESSED | Newest-first timeline shows I am OK above Call Family; Call Family incident remains open until human workflow resolves it |
| Normal door activity | Main door → DOOR_OPEN, then DOOR_CLOSED | Exact “Main door opened/closed” activity is shown as normal/green |
| Late-night door | Use **Simulate late-night door open** | Door opening is marked unexpected/red; close is recorded chronologically |
| Door left open | Open main door; advance the configured timeout | Red “Main door kept open” event appears; closing later returns current door state to green and reports total open duration |
| Configurable policy | In Household settings set door warning to 2 min and disable quiet-hours alert; save; simulate late-night open and advance 2 min | Config version increments; late-night open stays normal while the 2-minute left-open warning still fires |
| Post-missing activity | Create Missing morning activity, then send room/kitchen/pooja/door events | Missing-morning incident remains visible while newer household activity is shown newest-first |
| Device diagnostics | Inject a node/hub fault; Troubleshoot/Reboot | Dashboard shows status circle, location, stable error code and diagnosis; reboot clears only recoverable restart faults |
| Internet loss | Disconnect internet; send kitchen motion; advance 60 seconds four times | Hub retains activity and pending cloud records; backend has not received that motion; caregiver hub status becomes unavailable after its lease expires |
| Internet replay | Continue above: reconnect internet | Pending cloud becomes zero; motion arrives once in backend; timeline can indicate delayed receipt |
| Manual call while offline | Disconnect internet; Room 1 → CALL_FAMILY; reconnect | One CALL_FAMILY incident after reconnect; no real phone call or buzzer is generated |
| Node link loss | Disconnect kitchen node; inject kitchen motion; reconnect that node | Its retained count increases then returns to zero; event reaches hub and backend. This simulates link loss, not removing node power |
| Duplicate replay | Send kitchen motion; replay last node event | One backend MOTION; reducer evidence count becomes 2, explicitly exposing existing gap G02 |
| Notification accepted | Quiet-covered scenario; fake provider accepts due jobs | Primary job accepted; incident remains OPEN. Acceptance does not mean a human saw it |
| Notification rejected | Quiet-covered scenario; fake provider rejects due jobs | Due job becomes FAILED. Automatic retry for FAILED jobs is not implemented |
| Backup due | Quiet-covered scenario; advance 60 seconds five times; fake provider accepts due jobs | Both due stages can be accepted; no real delivery occurs |
| Caregiver ownership | Quiet-covered scenario; primary clicks I'll check; change actor to backup | Primary owns the incident during its lease; backup cannot claim during that lease |
| Acknowledge and resolve | Primary acknowledges, then resolves | ACKNOWLEDGED then RESOLVED; pending escalation cancelled |

The test fixture requires all four nodes, emits heartbeat events every simulated 60 seconds and uses the hub's current 190-second lease. These are fixture settings, not a final placement policy. The current coverage model does not prove uninterrupted coverage over the whole morning; short historical gaps can remain invisible.

## 7. Logs and evidence

| File | Meaning |
|---|---|
| `logs/e2e_report.json` / `.txt` | Latest 68-scenario result; also downloadable in browser |
| `logs/e2e_flow.txt` | Lab command and event-ID breadcrumbs; rotating 128 KiB with two backups |
| `logs/e2e_cpp.txt` | Existing C++ ERROR/optional TRACE sink; rotating 128 KiB with two backups |
| `logs/backend.txt` | Existing backend ERROR/optional TRACE sink; rotating 128 KiB with two backups |
| `logs/e2e_child_stderr.txt` | Child process stderr for the current launch |
| Browser log download | Bounded browser error log, useful for failed fetch/actions |

Trace-enabled laboratory:

```bash
GS_TRACE=1 make lab PRODUCT=base TRACE_FLAGS=-DGS_ENABLE_TRACE=1
```

The environment enables Python traces; the compiler flag enables C++ traces. The lab's own flow breadcrumbs are always collected for synthetic test scenarios. Existing browser TRACE is not enabled by this command; browser errors remain available. Empty ERROR logs during a successful run are normal. This is synchronous host logging, not a completed embedded crash recorder.

Optional C++ memory-error instrumentation from the existing package: `make verify-sanitize`. It runs the selected C++ component test executable with AddressSanitizer/UBSan, not every process or a complete end-to-end crash simulation.

## 8. Release regression framework

For normal development use `make validation-fast`. Before creating a software/reference release run:

```bash
make release-gate
```

This runs contract checks, C++ unit tests, backend/database/logging tests, app tests, product profiles, feature variants, five dummy sensor streams, the 68-case connected functional catalog, HTTP integration, sanitizers and a trace build. The detailed design is in `docs/VALIDATION_FRAMEWORK.md`.

The manual checklist is generated from the same functional catalog:

```bash
make manual-test-plan
```

Then review `tests/MANUAL_FUNCTIONAL_VALIDATION.md`. This is especially important for visual wording/color/accessibility when Playwright is unavailable.

## 9. Browser automation and current evidence

Normal use needs only your installed browser. Optional `tests/simulation_browser_test.cjs` drives the actual page with Playwright: sensor injection, morning decision, caregiver lifecycle, suite button and mobile-width overflow check. Install Playwright only if you want this extra automation:

```bash
sudo apt install -y npm
npm install --no-save playwright
npx playwright install chromium
node tests/simulation_browser_test.cjs
```

Keep `make lab` running in a separate terminal first. Node/npm and browser downloads are additional dependencies for this optional test only. Do not commit `node_modules` or local generated logs.

The release's automated HTTP and component evidence is in `evidence/`. Actual Chromium execution could not be completed in the authoring environment because the browser download timed out. The browser test script is included but is **not recorded as passed**. Run the manual walkthrough on your Windows browser before treating the visual interface as accepted.

## 10. Troubleshooting

- `make` or `sudo` not found: confirm you are in Ubuntu, not Git Bash. Install the tools in step 1.
- Directory not found: verify the actual extraction path. In WSL, `F:` is normally `/mnt/f`; Linux mounted-disk paths differ.
- Port occupied: after `make lab-build`, run `python3 tools/sim/local_lab.py --port 8766`, then open `http://localhost:8766`.
- Page will not open: keep the server terminal open; try `http://127.0.0.1:8765`. In a second Ubuntu terminal, `curl http://127.0.0.1:8765/healthz` should return `{"status":"ok"}`. If that works only inside WSL, check its localhost networking setup using the Microsoft link above.
- Simulator binary missing: run `make lab-build`. `make clean` and the original feature matrix remove the build folder.
- Duplicate event action fails immediately after reset: send a business event first; heartbeats are not the duplicate target.
- C++ process failure/timeout: stop the lab, inspect logs and restart. It does not silently rebuild lost business state.
- Capacity reached after many simulated hours: reset. The reference journal does not reclaim cloud-acknowledged entries yet.
- Passing simulation but missing P0 features: use the v2.0 open-work register. A host PASS must not mark an unfinished production requirement green.

## 11. What to develop next

Use this lab to reproduce and then close G02 duplicate reducer effects, followed by durable storage/restart recovery and coverage-history tracking. Add a regression scenario for each fix. After those, integrate the prompt/grace state machine and actual configuration/onboarding adapters. Hardware testing must still measure RF behaviour, reboot recovery, power consumption, flash failure handling and real button/PIR operation.
