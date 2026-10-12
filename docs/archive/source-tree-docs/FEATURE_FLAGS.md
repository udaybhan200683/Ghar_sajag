# Feature flags and simulation guide

Feature flags prevent unfinished or unsafe capabilities from entering a build. They are build/deployment configuration, not remote switches that silently change a household’s behaviour.

## Defaults

| Flag | Default | Release boundary |
|---|---:|---|
| `morning_routine` | on | P0 |
| `call_family` | on | P0 |
| `door_history` | on | P0 |
| `daily_summary` | on | P0 |
| `local_offline` | on | P0 |
| `temperature_context` | off | P1 experiment; not a fire/cooking claim |
| `external_camera` | off | P1 privacy/integration review |
| `fall_detection` | off | Separate validation and liability review |
| `professional_response` | off | Service operations and regulatory review |

## C++ build

The default is the P0 profile. Override a flag when compiling the host simulator or firmware:

```bash
make cpp-test TRACE_FLAGS='-DGS_ENABLE_TRACE=0 -DGS_FEATURE_CALL_FAMILY=0'
make simulator TRACE_FLAGS='-DGS_FEATURE_MORNING_ROUTINE=0'
```

The compile-time values are exposed by `gs::FeatureFlags::enabled()` and `name()`. Do not enable P1 flags for a pilot without a new acceptance review.

## Backend and app

The backend reads `GS_FEATURE_<NAME>=1` only when a deployment explicitly opts in; unknown names are false. The web app can receive a build-injected `globalThis.__GS_FEATURES__` object. A missing flag uses the safe default. Flags are logged as configuration metadata, never as resident data.

## Simulation before hardware

Run `make verify` for the normal P0 path. Run `make simulator TRACE_FLAGS='-DGS_FEATURE_LOCAL_OFFLINE=0'` to exercise a build where local-offline behaviour is unavailable; the result must be explicit and must not silently claim local operation. The existing C++/Python/JavaScript tests are deterministic and can run without any ESP32 board.

