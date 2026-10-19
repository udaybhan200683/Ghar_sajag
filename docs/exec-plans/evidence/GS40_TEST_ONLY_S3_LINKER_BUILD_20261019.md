# GS-40 TEST_ONLY S3 linker correction and build — 2026-10-19

Owning work: GS-40 dependency of GS-178. Canonical branch:
`feature/r1-commercial-baseline`. Source fix commit:
`26e49162071975873881e88294216d08fe5e20c7`.

## Correction

At the starting canonical commit `50fbb6886af07cb7412ec3dbe3531e6692b7c542`,
the isolated S3 TEST_ONLY build failed during final link. The component embedded
the external public DER at its caller-supplied basename `config-root.der`, so
ESP-IDF generated `_binary_config_root_der_start/end`; the guarded runtime
references `_binary_gs40_test_config_root_der_start/end`. `nm` on
`esp-idf/main/libmain.a` showed the two runtime references unresolved, while
`config-root.der.S` defined only `_binary_config_root_der_start/end`.

The fix in `code/firmware/hub/target/esp32/idf/main/CMakeLists.txt` copies the
supplied external public DER with `configure_file(COPYONLY)` to the stable
component-build basename `gs40_test_config_root.der`, then embeds that copy.
This keeps the expected linker names independent of the external temporary
directory or filename. The input remains an external public TEST_ONLY root;
no private key or credential is embedded. The copy and generated assembly stay
in the ignored build directory. Commercial composition does not enter this
conditional.

## Source-bound target build

ESP-IDF 6.0.3, esptool 5.4.0. The final build command was:

```bash
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
export GS_NODE_FIRMWARE_ASSET=/home/udaybhan/projects/Ghar_sajag_r1/code/build/validation_targets/gs40t1-R8RkWQ/node_firmware.bin
idf.py -C /home/udaybhan/projects/Ghar_sajag_r1/code/firmware/hub/target/esp32s3/idf \
  -B /home/udaybhan/projects/Ghar_sajag_r1/code/build/validation_targets/gs40t1-R8RkWQ/s3 \
  -DGS40_TEST_ONLY_CLOUDSYNC=ON \
  -DGS40_TEST_ONLY_CONFIG_ROOT_DER=/home/udaybhan/projects/Ghar_sajag_r1/code/build/validation_targets/gs40t1-R8RkWQ/config-root.der \
  -DGS_HIL_BUILD=OFF -DPROJECT_VER=26e4916-gs40t1 \
  -DSDKCONFIG_DEFAULTS='/home/udaybhan/projects/Ghar_sajag_r1/code/firmware/hub/target/esp32s3/idf/sdkconfig.defaults;/home/udaybhan/projects/Ghar_sajag_r1/code/firmware/hub/target/esp32s3/idf/sdkconfig.gs40_test_only.defaults' \
  reconfigure build size
```

Result: **PASS**, source commit `26e49162071975873881e88294216d08fe5e20c7`.
The embedded copy and supplied DER both have SHA-256
`c7239547fe6cbf266bf04f5a54d0c0a0de3909d47acb2a955acfd36746656429` (422
bytes). The generated object defines `_binary_gs40_test_config_root_der_start`
and `_binary_gs40_test_config_root_der_end`, and the final ELF contains both
symbols and the guarded `gs40_test_only_receive_config` / signed-time bootstrap
functions. Compile commands carry `GS40_TEST_ONLY_CLOUDSYNC_BUILD=1`.

Image facts:

- Application: `gs_r1_s3_hub.bin`, 2,211,104 bytes (`0x21bd20`).
- Image SHA-256: `1f247cbcdbe1bbc326b5224abf18c2fdb377a9005c37724b4f48e08be50430d8`.
- ESP image validation hash: `1e9cf8c57ab03ee3a5f6415f58b3749b4be8e619aa1637822d5136924cd406d5` (valid per esptool image-info).
- ELF SHA-256: `a5ad540d07975aec6380a774a607cd9c52768e2166ef432699c58bbdaced169b`.
- App descriptor: `gs_r1_s3_hub`, `26e4916-gs40t1`; ESP-IDF `v6.0.3`; 16 MiB flash image header.
- OTA application slot: 4 MiB; the image fits with 1,983,200 bytes free.
- Partition profile: NVS `0x9000/24K`, otadata `0xf000/8K`, PHY init `0x11000/4K`, OTA0 `0x20000/4M`, OTA1 `0x420000/4M`, journal `0x820000/2M`.
- Effective build `sdkconfig` SHA-256: `e18bccdaf876c0442ff6119d9d8dac49ed67cde964cf4f8c9281edb9eeb7f065`.
- Default sdkconfig input SHA-256: `be0624e0d4efb47d6e3868a42c7a5925c5be1dea8520df644271ad2e66a4c024`.
- TEST_ONLY sdkconfig input SHA-256: `7339aa689a054a849ac14d29c0eb79de543d966a6440c18c8467ead4756cd073`.
- External TEST_ONLY public root SHA-256: `c7239547fe6cbf266bf04f5a54d0c0a0de3909d47acb2a955acfd36746656429`.
- Paired C3 firmware asset: 937,536 bytes, SHA-256
  `d9541f3947ca65df0a80a949912d7b05191c85aab51459815a37b595ba4804fe`.
- Generated GS-40 NodeHealth configuration digest: `fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862` (300-second heartbeat / 910-second offline policy).

Effective TEST_ONLY settings include `GS40_TEST_ONLY_CLOUDSYNC=ON`,
`GS_HIL_BUILD=OFF`, `CONFIG_ESP_TLS_USE_DS_PERIPHERAL` unset,
`CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`, and UART default console unset. The
image is compile/build evidence only; it was not installed or executed on a
target. No physical or production security claim follows from the build.

## Commercial separation

The existing production-profile S3 build configuration was checked: its cache
has `GS40_TEST_ONLY_CLOUDSYNC=OFF`, compile commands use
`GS40_TEST_ONLY_CLOUDSYNC_BUILD=0`, and its linked ELF contains
`UnprovisionedS3CloudTrust`. The target CMake option defaults OFF, and the new
asset copy is inside the `if(GS40_TEST_ONLY_CLOUDSYNC)` branch. The earlier
production-profile build record remains at
`docs/exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md`; no production
credential or service was used.

## Tests and boundary

- `make -C code gs40-test-only-bootstrap-test`: PASS, 33 checks.
- `make -C code cloudsync-security-ut`: PASS: mTLS 9, TEST_ONLY mTLS 5,
  Cloud Trust 5 suites, backend security 14, identity/time E2E 4, GS-168 issuer
  10, NodeHealth 5.
- `python -m esptool --chip esp32s3 image-info <image>`: PASS; checksum and
  validation hash valid, image format ESP32-S3.
- `cmp <external-public-root.der> <generated-embedded-public-root.der>`: PASS;
  exact bytes match.
- `git diff --check`: PASS.

Previously completed GS-178 software E2E remains 27/27 PASS and was not rerun
because the correction changes only build-time asset naming. Host simulation,
target build, and physical qualification remain distinct. No board, serial port,
flash, eFuse, production credential, or production endpoint was accessed.
GS-40/GS-117/GS-121 physical acceptance remains NOT_RUN; GS-178 and P0 remain
In Progress/PARTIAL. Hub-derived rule checkpoint atomicity and trusted local
minute input remain separate target-runtime gaps.
