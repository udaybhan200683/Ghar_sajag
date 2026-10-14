# C8-P8 fixture software validation — 2026-10-14 UTC

This software-only checkpoint was run from the canonical source working tree
at base commit `ec469303d17ea2037019a5bb18d29ce070c249e2`. The new fixture and
test files were uncommitted during validation; this result is tied to that
working-tree source. No serial port, installed image or persistent device state
was accessed. A separate matched target build was later completed offline as
recorded below. The installed pair remains on C3 app
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3 app
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`, both from
firmware build source `72a223fc3b290c01c9f93fbb90db83d87601ad54`.

Source file fingerprints at evidence capture: `hil_c8_ack_drop_gate.hpp`
SHA-256 `f3cd3e0806273f1186f4c00f68ada7d3937fed26e9790ff1a2c923291c095211`;
`c8_ack_drop_gate_validation.cpp` SHA-256
`0f80e8042532a9da8f3306356c0fdbe05122e1a55317f9e8df7baffffff9535e`.

## Host gate

Working directory: `code/`.

```text
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -pthread -I. tests/cpp/c8_ack_drop_gate_validation.cpp -o /tmp/gs114-c8-ack-drop-gate-validation
exit 0
/tmp/gs114-c8-ack-drop-gate-validation
C8 ACK-drop gate PASS checks=16
exit 0
```

The 16 checks cover the exact durable/new-effect/outbox/admission conjunction,
default-off state, active-window arm rejection, ineligible preservation,
one-shot consumption, expiry, rearm, overflow rejection, and two concurrent
eligible consumers producing exactly one suppression.

AddressSanitizer and UndefinedBehaviorSanitizer:

```text
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -pthread -fsanitize=address,undefined -fno-omit-frame-pointer -I. tests/cpp/c8_ack_drop_gate_validation.cpp -o /tmp/gs114-c8-ack-drop-gate-sanitized
exit 0
/tmp/gs114-c8-ack-drop-gate-sanitized
C8 ACK-drop gate PASS checks=16
exit 0
```

ThreadSanitizer:

```text
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -pthread -fsanitize=thread -fno-omit-frame-pointer -I. tests/cpp/c8_ack_drop_gate_validation.cpp -o /tmp/gs114-c8-ack-drop-gate-tsan
exit 0
/tmp/gs114-c8-ack-drop-gate-tsan
C8 ACK-drop gate PASS checks=16
exit 0
```

The invalid-profile guard was checked from the repository root. The expected
nonzero configure exit confirms an ACK-drop build is rejected without the S3
commissioning fixture profile:

```text
cmake -S code/firmware/hub/target/esp32s3/idf -B /tmp/gs114-c8-invalid-profile-20261014 -DGS_HIL_BUILD=OFF -DGS_HIL_CONTROL=OFF -DGS_HIL_COMMISSIONING=OFF -DGS_HIL_C8_ACK_DROP=ON
CMake Error: GS_HIL_C8_ACK_DROP requires the complete S3 commissioning fixture profile
exit 1 (expected rejection)
```

`git diff --check`, `jq -e . code/validation/suites.json`, and the
`MASTER_TRACEABILITY.csv` row-width check all passed. The gate is registered in
`code/validation/suites.json` and `docs/validation/MASTER_TRACEABILITY.csv`.
The S3 fixture-profile suite was run with the configured `python` interpreter:

```text
/home/udaybhan/.espressif/python_env/idf6.0_py3.14_env/bin/python -m unittest tests.python.test_s3_fixture_commissioning -v
Ran 12 tests in 0.945s
OK
exit 0
```

The first run found one test-source anchor error: it searched for the
`processed->state_changed` expression in the gate header, although that
production condition is in `hub_runtime_adapter.cpp`. The test now checks the
owner expression and the gate's `state_changed` input independently. The
corrected suite passed 12/12. This did not require a firmware source change and
does not alter the already-built target image inputs.

## Fixture and traceability registry checks

```text
python validation/physical_hil_catalogue.py --check
PHYSICAL HIL CATALOGUE: PASS cases=99 physical_required_features=69 physical_conditional_features=40 device_access=NONE
exit 0

python scripts/check_feature_traceability.py
GS130 TRACEABILITY PASS features=175 modules=205 physical_cases=15; consistency only, not semantic/physical PASS
exit 0

PYTHONPATH=backend:. python -m unittest tests.python.test_feature_traceability -v
Ran 19 tests in 0.802s
OK
exit 0
```

The first traceability run identified that this fixture needed canonical
requirement links, a `PHYSICAL_QUALIFICATION.csv` entry and a reciprocal source
inventory row. Those were added. The first matrix-suite run then exposed a test
that assumes the first feature row has a component gate; the new row was moved
to the end to preserve that existing test assumption. The corrected consistency
checker and all 19 tests pass. These registry checks do not qualify hardware.

## Paired target build — 2026-10-14 UTC

From the same canonical base commit and scoped working-tree source, ESP-IDF
6.0.3 built the physical-wake C3 application and the S3 commissioning profile
with `GS_HIL_C8_ACK_DROP=ON`. The build root is
`code/build/gs114_c8_p8_20261014/`; both target build commands exited 0. The
C3 application is 939,024 bytes, 4-MiB flash profile, SHA-256
`5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`. Its
staged S3 embed input has the same byte length and hash.

The first S3 configure attempt exited 2 before compilation because the paired
Node asset was passed as a CMake cache argument, while the Hub component
discovery reads `GS_NODE_FIRMWARE_ASSET` from the environment and requires the
embedded filename `node_firmware.bin`. The preserved diagnostic is
`code/build/gs114_c8_p8_20261014/s3/log/idf_py_stderr_output_292297`. The
correction staged the byte-identical C3 app under the required basename and
exported the environment variable. The following S3 build completed; no
device/serial access occurred during either attempt.

The S3 application is 1,891,728 bytes, SHA-256
`f94192a7c59fa1a7221a7dc4a8394c1bd8c448c2009553e35dfed2f074eccd08`. Its
build cache records `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`,
`GS_HIL_COMMISSIONING=ON`, `GS_HIL_C8_ACK_DROP=ON`, and
`GS_S3_DIAGNOSTIC_ONLY=OFF`. The generated configuration selects the candidate
16-MiB DIO/40-MHz profile with octal PSRAM configuration at 40 MHz and the
`ota_0`/`ota_1`, `gs_outbox`, and `gs_state` table. The partition binary
contains all five expected labels; `strings` on the app confirms the exact
`DROP_NEXT_DURABLE_ACK` command and the postcommit suppression log marker.
The registered host test was run through
`make -C code c8-ack-drop-gate-host-test` and passed 16 checks (exit 0).
Offline `esptool v5.4.0 image-info` returned exit 0 for both apps and validated
their image checksums: the C3 file is detected as ESP32-C3 / 4-MiB DIO at
80 MHz, app version `gs114-c8p8-20261014-ec469`, ELF SHA-256
`da0a1b3338aae8d71fe3ba571d83be70f1d0cc4d57765933dfc77e26421b34fa`; the S3
file is detected as ESP32-S3 / 16-MiB DIO at 40 MHz with the same app version,
ELF SHA-256 `62378445c691d6579c2be252f1e323f8488145cab0658a9cfd54d40c9e2f6b64`.

Firmware/build source fingerprints at target-build time:

```text
hil_c8_ack_drop_gate.hpp f3cd3e0806273f1186f4c00f68ada7d3937fed26e9790ff1a2c923291c095211
hub_runtime_adapter.cpp 9f6aa647831fc86296225505d97f944f59968909ae5553260b319e63432663b8
hub_runtime_adapter.hpp e0896c018d4932702e01d131806f59a0c1394bc69fd9b764dff0a378c6284898
fixture_commissioning_control.cpp ade72fb9ca04a322095a567b65407e7de83cb65ff3fcae386625ce7882c9eede
Hub main CMakeLists.txt d71fc8b52b0d7fd6b58d461dfbd3aebe7e7ee0f6b35a978991dca53d2780bfc0
S3 target CMakeLists.txt ea51ef107450b3b27636bb91f54aca9cd932746b55161943d8d45fad135f51d6
c8_ack_drop_gate_validation.cpp 0f80e8042532a9da8f3306356c0fdbe05122e1a55317f9e8df7baffffff9535e
build_gs114_fixture_pair.py 828057912a6a348e82e3382c3606c961eec686241c158bb66acf01b6bf1b98fd
```

The S3 fixture unittest source was corrected after the image build; its tested
current SHA-256 is
`d300333884416b595a1349c50f80f51433aa90aebf32f32cd338786e1ee91ccf`. The
correction affected only the test's source anchor, not firmware inputs.

No target image was flashed. Current installed apps remain C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`.
P7 remains the next physical case and waits for the operator's `available`
signal. This target build does not claim physical P8 evidence.
