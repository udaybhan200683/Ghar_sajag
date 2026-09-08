# Host verification report — v1.1

Date: 8 September 2026

## Logging verification

- Production profile: 54 C++ checks, 12 Python tests, 7 JavaScript tests, contract verification and simulator passed.
- Development trace profile: the same functional suite passed with C++ call-flow tracing compiled in and backend tracing enabled.
- ASan/UBSan C++ suite passed (`detect_leaks=0` is used because leak instrumentation is unavailable in this container; address and undefined-behaviour checks remain active).
- Production sample contains ERROR only; development sample contains ERROR and TRACE records spanning N00–N05, H00–H08 and S00–S01.
- Hardware/ESP-IDF memory, flash-wear, watchdog, brown-out and coredump validation remains pending physical boards.

## Simulation and feature-flag verification

- `make simulate-matrix` passed four deterministic simulator builds: P0 default, morning routine disabled, family-call disabled and local-offline disabled.
- Each simulator result reports the active flags and changes the expected outcome explicitly; no disabled feature is silently treated as available.
- Web application tests remain runnable with mock API responses; real browser hosting, service worker deployment and push-provider credentials are hardware/service integration work.

Command: `make verify`

| Check | Result |
|---|---|
| Contract structure | 3 JSON schemas plus OpenAPI surface passed |
| Portable C++ | Built with `g++ 13.3.0`, C++17, `-Wall -Wextra -Werror -pedantic`; 52 assertions passed |
| End-to-end host simulator | Activity persisted locally, missing-activity incident suppressed by evidence, one offline record replayed |
| Python backend domain | 10 `unittest` cases passed |
| Caregiver app domain | 6 Node.js tests passed |

No physical-board, RF, GPIO, power, flash-partition, MQTT broker, OIDC provider, Web Push delivery or OTA-signature test is represented by this report. Those remain separate gates.
