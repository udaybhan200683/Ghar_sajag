"""Focused parser/build-isolation tests for the S3-only commissioning fixture."""
from pathlib import Path
import hashlib
import ast
import json
import os
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "firmware/hub/target/esp32/idf/main/fixture_commissioning_control.cpp"
OUTBOX_BUILDER = ROOT / "firmware/hub/target/esp32s3/idf/build-outbox.sh"
OUTBOX_PARTITIONS = ROOT / "firmware/hub/target/esp32s3/idf/partitions.s3-outbox-candidate.csv"
sys.path.insert(0, str(ROOT))
from scripts.build_gs114_fixture_pair import (
    build_environment,
    c3_p9_build_profile,
    parse_partitions_from_text,
    stage_node_firmware_asset,
    validate_c3_p9_ack_trace_profile,
    validate_s3_fixture_artifact,
)


class S3FixtureCommissioning(unittest.TestCase):
    def control_transport_resolver(self):
        # Execute the production resolver from the canonical script's Python
        # input stage; these tests never configure IDF or access a serial port.
        source=OUTBOX_BUILDER.read_text().split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        tree=ast.parse(source)
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fixture_control_transport')
        def fail(message):raise ValueError(message)
        scope={'fail':fail}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(OUTBOX_BUILDER),'exec'),scope)
        return scope['fixture_control_transport']

    def test_registered_native_usb_selects_existing_usb_receiver(self):
        resolve=self.control_transport_resolver()
        self.assertEqual(resolve({'s3':{'port':'COM10','serial_number':'E0:72:A1:D3:8D:34',
            'usb_hwid':'USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2:x.0'}}),'usb_serial_jtag')

    def test_registered_uart_bridge_selects_existing_uart_profile(self):
        resolve=self.control_transport_resolver()
        self.assertEqual(resolve({'s3':{'port':'COM10','serial_number':'E0:72:A1:D3:8D:34',
            'usb_hwid':'USB VID:PID=1A86:55D3 SER=E0:72:A1:D3:8D:34 LOCATION=1-2'}}),'uart0')

    def test_unknown_or_mismatched_control_transport_rejects(self):
        resolve=self.control_transport_resolver()
        for board in ({},{'port':'COM4','serial_number':'E0:72:A1:D3:8D:34'},
                {'port':'COM10','serial_number':'E0:72:A1:D3:8D:34','usb_hwid':'unknown'}):
            with self.subTest(board=board),self.assertRaises(ValueError):resolve({'s3':board})

    def test_missing_engineering_fixture_fails_before_toolchain(self):
        with tempfile.TemporaryDirectory() as folder:
            env={**os.environ,'XDG_CONFIG_HOME':folder,'IDF_PATH':'/missing-idf'}
            result=subprocess.run(['bash',str(OUTBOX_BUILDER)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('registered Engineering fixture is missing',result.stderr)

    def test_ambiguous_fixture_asset_fails_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'config/ghar-sajag/gs117-tc001';config.mkdir(parents=True)
            state=root/'state/ghar-sajag/gs117-tc001';state.mkdir(parents=True)
            image=b'unit-test-only-image'
            fixture={'schema_version':1,'test_id':'TC-001','profile':'GS179_TEST_ONLY',
                'qualification_profile':'GS117_DEV_TEST_ONLY','home_id':'gs177-test-product',
                'hub_id':'hub-e072a1d38d34','physical_device_id':'c3-146393c5d158',
                'c3':{'image_sha256':hashlib.sha256(image).hexdigest()}}
            (config/'fixture.json').write_text(json.dumps(fixture));(config/'config-root-public.der').write_bytes(b'test-only')
            for name in ('provenance-refresh-one','provenance-refresh-two'):
                p=state/name/'trusted-artifacts';p.mkdir(parents=True);(p/'c3-current-app.bin').write_bytes(image)
            env={**os.environ,'XDG_CONFIG_HOME':str(root/'config'),'XDG_STATE_HOME':str(root/'state'),'IDF_PATH':'/missing-idf'}
            env.pop('GS_NODE_FIRMWARE_ASSET',None);env.pop('GS40_TEST_ONLY_CONFIG_ROOT_DER',None)
            result=subprocess.run(['bash',str(OUTBOX_BUILDER)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertIn('found 2',result.stderr)

    def test_outbox_builder_rejects_incompatible_gs_journal_profile(self):
        result = subprocess.run(["bash", str(OUTBOX_BUILDER), "gs_journal"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Partition layouts cannot be selected as profiles", result.stderr)

    def test_outbox_release_requires_existing_production_pair(self):
        env = os.environ.copy()
        env.pop("GS_NODE_FIRMWARE_ASSET", None)
        env.pop("GS40_TEST_ONLY_CONFIG_ROOT_DER", None)
        result = subprocess.run(["bash", str(OUTBOX_BUILDER), "release"], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("release profile requires GS_NODE_FIRMWARE_ASSET", result.stderr)

    def test_outbox_candidate_matches_physical_partition_contract(self):
        partitions = parse_partitions_from_text(OUTBOX_PARTITIONS.read_text())
        self.assertEqual(partitions, {
            "nvs": ("data", "nvs", 0x9000, 0x6000),
            "otadata": ("data", "ota", 0xF000, 0x2000),
            "phy_init": ("data", "phy", 0x11000, 0x1000),
            "ota_0": ("app", "ota_0", 0x20000, 0x400000),
            "ota_1": ("app", "ota_1", 0x420000, 0x400000),
            "gs_outbox": ("data", "littlefs", 0x820000, 0x400000),
            "gs_state": ("data", "nvs", 0xC20000, 0x40000),
        })
        self.assertNotIn("gs_journal", partitions)

    def test_s3_build_exports_paired_asset_during_component_discovery(self):
        env = build_environment(["GS_HIL_BUILD=OFF", "GS_NODE_FIRMWARE_ASSET=/tmp/node_firmware.bin"], {})
        self.assertEqual(env["GS_NODE_FIRMWARE_ASSET"], "/tmp/node_firmware.bin")
        self.assertNotIn("GS_NODE_FIRMWARE_ASSET", build_environment(["GS_HIL_BUILD=OFF"], {}))

    def test_p8_s3_only_build_stages_exact_existing_c3_asset_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_p8_existing_node_") as temp:
            root = Path(temp)
            source = root / "installed_c3.bin"
            source.write_bytes(b"verified installed C3 application")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            staged, report = stage_node_firmware_asset(root / "build", source, expected)
            self.assertEqual(staged.name, "node_firmware.bin")
            self.assertEqual(staged.read_bytes(), source.read_bytes())
            self.assertEqual(report["sha256"], expected)
            self.assertTrue(report["reused_existing_image"])
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                stage_node_firmware_asset(root / "bad_build", source, "0" * 64)

    def test_p8_existing_node_cli_requires_isolated_ack_drop_and_expected_hash(self):
        script = ROOT / "scripts/build_gs114_fixture_pair.py"
        invalid = subprocess.run(
            [sys.executable, str(script), "--s3-node-firmware-asset", "/tmp/node_firmware.bin"],
            capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("only supported with --s3-c8-p8-ack-drop", invalid.stderr)
        missing_hash = subprocess.run(
            [sys.executable, str(script), "--s3-c8-p8-ack-drop",
             "--s3-node-firmware-asset", "/tmp/node_firmware.bin"],
            capture_output=True, text=True)
        self.assertEqual(missing_hash.returncode, 2)
        self.assertIn("--expected-node-sha256 is required", missing_hash.stderr)

    def test_idf_partition_decoder_size_suffixes_are_supported(self):
        parsed = parse_partitions_from_text("nvs,data,nvs,0x9000,24K\nota_0,app,ota_0,0x20000,4M\n")
        self.assertEqual(parsed["nvs"][3], 24 * 1024)
        self.assertEqual(parsed["ota_0"][3], 4 * 1024 * 1024)

    def test_p9_c3_profile_omits_uart_hil_controls_and_hil_sdkconfig(self):
        defaults, options = c3_p9_build_profile()
        self.assertEqual(defaults, ["sdkconfig.defaults"])
        self.assertEqual(options, ["-D", "GS_HIL_CONTROL=OFF",
                                   "-D", "GS_BAT_C8_PHYSICAL_WAKE=ON",
                                   "-D", "GS_BAT_C8_ACK_TRACE=ON",
                                   "-D", "GS_BAT_C8_FIXTURE_SECURITY=ON"])

    def test_p9_c3_profile_validator_requires_sleep_trace_identity_and_no_commands(self):
        with tempfile.TemporaryDirectory(prefix="gs_c3_p9_profile_") as temp:
            root = Path(temp)
            sdkconfig = root / "sdkconfig"
            sdkconfig.write_text('''CONFIG_ESPTOOLPY_FLASHSIZE="4MB"
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"
# CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG is not set
CONFIG_ESP_CONSOLE_UART_DEFAULT=y
CONFIG_ESP_CONSOLE_UART_NUM=0
''')
            cmake = root / "CMakeCache.txt"
            cmake.write_text('''GS_HIL_BUILD:BOOL=OFF
GS_HIL_CONTROL:BOOL=OFF
GS_BAT_C8_PHYSICAL_WAKE:BOOL=ON
GS_BAT_C8_ACK_TRACE:BOOL=ON
GS_BAT_C8_FIXTURE_SECURITY:BOOL=ON
''')
            app = root / "app.bin"
            app.write_bytes(b"GS114_ACK_WAIT_TRACE_SCHEMA=1STA MAC does not match qualified C3"
                            b"GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF"
                            b"gs_dev_ident")
            profile = validate_c3_p9_ack_trace_profile(sdkconfig, cmake, app)
            self.assertTrue(profile["qualified_node_mac_guard"])
            self.assertTrue(profile["ack_wait_trace"])
            self.assertFalse(profile["usb_hil_console"])

            cmake.write_text(cmake.read_text().replace(
                "GS_HIL_CONTROL:BOOL=OFF", "GS_HIL_CONTROL:BOOL=ON"))
            with self.assertRaisesRegex(ValueError, "HIL controls off"):
                validate_c3_p9_ack_trace_profile(sdkconfig, cmake, app)

            cmake.write_text(cmake.read_text().replace(
                "GS_HIL_CONTROL:BOOL=ON", "GS_HIL_CONTROL:BOOL=OFF"))
            app.write_bytes(app.read_bytes() + b"SOFTWARE_RESTART")
            with self.assertRaisesRegex(ValueError, "unrelated UART HIL controls"):
                validate_c3_p9_ack_trace_profile(sdkconfig, cmake, app)

    def _profile_files(self, root: Path):
        sdkconfig = root / "sdkconfig"
        sdkconfig.write_text('''CONFIG_ESPTOOLPY_FLASHSIZE=\"16MB\"
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME=\"partitions.s3-outbox-candidate.csv\"
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_SPIRAM_SPEED=40
CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y
CONFIG_ESPTOOLPY_FLASHMODE=\"dio\"
CONFIG_ESPTOOLPY_FLASHFREQ=\"40m\"
# CONFIG_SECURE_BOOT is not set
# CONFIG_FLASH_ENCRYPTION_ENABLED is not set
# CONFIG_APP_ANTI_ROLLBACK is not set
''')
        cmake = root / "CMakeCache.txt"
        cmake.write_text('''GS_HIL_BUILD:BOOL=OFF
GS_HIL_CONTROL:BOOL=OFF
GS_HIL_COMMISSIONING:BOOL=ON
GS_S3_DIAGNOSTIC_ONLY:BOOL=OFF
GS_HIL_C8_ACK_DROP:BOOL=OFF
''')
        partitions = root / "partitions.s3-outbox-candidate.csv"
        partitions.write_text('''nvs, data, nvs, 0x9000, 0x6000,
otadata, data, ota, 0xf000, 0x2000,
phy_init, data, phy, 0x11000, 0x1000,
ota_0, app, ota_0, 0x20000, 0x400000,
ota_1, app, ota_1, 0x420000, 0x400000,
gs_outbox, data, littlefs, 0x820000, 0x400000,
gs_state, data, nvs, 0xC20000, 0x40000,
''')
        node_asset = root / "node.bin"
        node_asset.write_bytes(
            b"W (%lu) %s: HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake"
            b"STA MAC does not match qualified C3"
            b"GS114_ACK_WAIT_TRACE_SCHEMA=1")
        app = root / "app.bin"
        app.write_bytes(b"image" + b" ".join(
            [*(f"RPF0{i}".encode() for i in range(9)),
             b"S3 replay fence failed stage=%s",
             b"COMMISSION_EXPECTED_NODE", b"FIXTURE_STATUS", b"HIL_FIXTURE_READY"])
            + node_asset.read_bytes())
        return sdkconfig, cmake, partitions, app, node_asset

    def test_fixture_rpf_profile_accepts_matching_app_and_partitions(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_rpf_profile_") as temp:
            paths = self._profile_files(Path(temp))
            result = validate_s3_fixture_artifact(*paths)
            self.assertEqual(result["ota_slot_capacity_bytes"], 0x400000)
            self.assertEqual(result["app_free_bytes"], 0x400000 - paths[3].stat().st_size)
            self.assertEqual(result["rpf_markers_present"], [f"RPF0{i}" for i in range(9)])
            self.assertTrue(result["s3_runtime_image_broad_hil_markers_absent"])

    def test_p9_ack_hold_profile_requires_exact_marker_and_flags(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_p9_hold_") as temp:
            sdkconfig, cache, partitions, app, node = self._profile_files(Path(temp))
            node.write_bytes(b"GS114_ACK_WAIT_TRACE_SCHEMA=1STA MAC does not match qualified C3"
                             b"GS114_C8_FIXTURE_SECURITY=TEST_ONLY; UART_HIL_CONTROL=OFF"
                             b"gs_dev_ident")
            app.write_bytes(b"image" + b" ".join(
                [*(f"RPF0{i}".encode() for i in range(9)),
                 b"S3 replay fence failed stage=%s", b"ARM_C8_ACK_HOLD"])
                + node.read_bytes())
            cache.write_text(cache.read_text().replace(
                "GS_HIL_COMMISSIONING:BOOL=ON", "GS_HIL_COMMISSIONING:BOOL=OFF"))
            cache.write_text(cache.read_text() + "GS_HIL_C8_ACK_HOLD:BOOL=ON\nGS_HIL_SIGNED_FOTA:BOOL=OFF\n")
            profile = validate_s3_fixture_artifact(sdkconfig, cache, partitions,
                                                   app, node, c8_ack_hold=True,
                                                   fixture_commissioning=False)
            self.assertTrue(profile["c8_ack_hold_fixture_enabled"])
            self.assertTrue(profile["embedded_node_asset_hil_command_plane_absent"])
            self.assertTrue(profile["embedded_node_asset_qualified_mac_guard_verified"])
            self.assertTrue(profile["embedded_node_asset_fixture_security_verified"])
            self.assertTrue(profile["embedded_node_asset_ack_wait_trace_verified"])
            self.assertEqual(profile["commissioning_markers_present"], [])
            app.write_bytes(app.read_bytes().replace(b"ARM_C8_ACK_HOLD", b""))
            with self.assertRaisesRegex(ValueError, "ACK-hold command"):
                validate_s3_fixture_artifact(sdkconfig, cache, partitions,
                                             app, node, c8_ack_hold=True,
                                             fixture_commissioning=False)
            cache.write_text(cache.read_text().replace("GS_HIL_C8_ACK_HOLD:BOOL=ON",
                                                       "GS_HIL_C8_ACK_HOLD:BOOL=OFF"))
            with self.assertRaisesRegex(ValueError, "CMake options"):
                validate_s3_fixture_artifact(sdkconfig, cache, partitions,
                                             app, node, c8_ack_hold=True,
                                             fixture_commissioning=False)

    def test_fixture_rpf_profile_rejects_wrong_build_flags(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_rpf_flags_") as temp:
            paths = self._profile_files(Path(temp))
            paths[1].write_text(paths[1].read_text().replace(
                "GS_HIL_COMMISSIONING:BOOL=ON", "GS_HIL_COMMISSIONING:BOOL=OFF"))
            with self.assertRaisesRegex(ValueError, "CMake options"):
                validate_s3_fixture_artifact(*paths)

    def test_fixture_rpf_profile_rejects_development_partition_map(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_rpf_partition_") as temp:
            paths = self._profile_files(Path(temp))
            paths[2].write_text(paths[2].read_text().replace("gs_outbox, data, littlefs",
                                                              "gs_journal, data, nvs"))
            with self.assertRaisesRegex(ValueError, "partition table"):
                validate_s3_fixture_artifact(*paths)

    def test_fixture_rpf_profile_rejects_missing_diagnostics_or_oversized_app(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_rpf_image_") as temp:
            paths = self._profile_files(Path(temp))
            paths[3].write_bytes(b"RPF00" + b"COMMISSION_EXPECTED_NODE" + paths[4].read_bytes())
            with self.assertRaisesRegex(ValueError, "RPF diagnostics missing"):
                validate_s3_fixture_artifact(*paths)
            paths[3].write_bytes(b"x" * (0x400000 + 1))
            with self.assertRaisesRegex(ValueError, "outside OTA slot"):
                validate_s3_fixture_artifact(*paths)

    def test_fixture_rpf_profile_rejects_hub_control_outside_embedded_node_asset(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_rpf_hub_control_") as temp:
            paths = self._profile_files(Path(temp))
            paths[3].write_bytes(paths[3].read_bytes() + b" INJECT_MOTION")
            with self.assertRaisesRegex(ValueError, "broad HIL control marker"):
                validate_s3_fixture_artifact(*paths)

    def test_fixture_rpf_profile_rejects_unproven_embedded_node_guard(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_rpf_node_guard_") as temp:
            paths = self._profile_files(Path(temp))
            paths[4].write_bytes(b"INJECT_MOTION")
            paths[3].write_bytes(paths[3].read_bytes().replace(
                b"W (%lu) %s: HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake",
                paths[4].read_bytes()))
            with self.assertRaisesRegex(ValueError, "physical-wake motion guard"):
                validate_s3_fixture_artifact(*paths)

    def test_c8_p8_ack_drop_requires_explicit_profile_and_image_marker(self):
        with tempfile.TemporaryDirectory(prefix="gs_s3_c8_ack_drop_") as temp:
            paths = self._profile_files(Path(temp))
            with self.assertRaisesRegex(ValueError, "CMake options"):
                validate_s3_fixture_artifact(*paths, c8_ack_drop=True)
            paths[1].write_text(paths[1].read_text().replace(
                "GS_HIL_C8_ACK_DROP:BOOL=OFF", "GS_HIL_C8_ACK_DROP:BOOL=ON"))
            with self.assertRaisesRegex(ValueError, "C8 ACK-drop command"):
                validate_s3_fixture_artifact(*paths, c8_ack_drop=True)
            paths[3].write_bytes(paths[3].read_bytes() + b" DROP_NEXT_DURABLE_ACK")
            result = validate_s3_fixture_artifact(*paths, c8_ack_drop=True)
            self.assertTrue(result["c8_ack_drop_fixture_enabled"])

    def test_command_parser_is_exact_and_limited_to_commissioning_and_status(self):
        self.assertEqual(subprocess.run(["g++", "--version"], capture_output=True).returncode, 0,
                         "g++ is mandatory for this adapter test")
        with tempfile.TemporaryDirectory(prefix="gs_s3_fixture_") as temp:
            root = Path(temp)
            fake = root / "firmware/hub/target/esp32"
            fake.mkdir(parents=True)
            (fake / "hub_runtime_adapter.hpp").write_text("""#pragma once
#include "firmware/hub/target/esp32/fixture_commissioning_status.hpp"
#include <array>
#include <cstdint>
#include <string>
namespace gs::hub::target {
struct HubSecurityLink { struct ExpectedNode {
 std::array<std::uint8_t,6> radio_mac{}; std::string device_id;
 std::array<std::uint8_t,65> public_key{}; std::array<std::uint8_t,32> installer_code{};
 std::string logical_id,room,function;
};};
bool request_node_commissioning(HubSecurityLink::ExpectedNode);
FixtureCommissioningStatus fixture_commissioning_status();
}
""")
            headers = {
                "esp_err.h": "#pragma once\nusing esp_err_t=int; constexpr int ESP_OK=0, ESP_ERR_NO_MEM=1;\n#define ESP_ERROR_CHECK(x) do{(void)(x);}while(0)\n",
                "esp_log.h": "#pragma once\n#define ESP_LOGI(...) do{}while(0)\n#define ESP_LOGW(...) do{}while(0)\n",
                "freertos/task.h": "#pragma once\nconstexpr int pdPASS=1; inline int xTaskCreate(void(*)(void*),const char*,unsigned,void*,unsigned,void*){return pdPASS;} inline void vTaskDelay(int){}\n#define pdMS_TO_TICKS(x) (x)\n",
                "mbedtls/platform_util.h": "#pragma once\n#include <cstring>\ninline void mbedtls_platform_zeroize(void*p,unsigned long n){std::memset(p,0,n);}\n",
            }
            for name, body in headers.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            harness = root / "test.cpp"
            harness.write_text(f'''#include <cassert>
#include <atomic>
#include <cstring>
#include <string>
#include <thread>
#include <utility>
#include "{SOURCE.as_posix()}"
using namespace gs::hub::target;
int accepted=0;
HubSecurityLink::ExpectedNode captured;
namespace gs::hub::target {{
bool request_node_commissioning(HubSecurityLink::ExpectedNode n) {{ ++accepted; captured=std::move(n); return true; }}
FixtureCommissioningStatus fixture_commissioning_status() {{ return FixtureCommissioningStatus::OfferActive; }}
}}
int main() {{
 std::string input="COMMISSION_EXPECTED_NODE c3-146393c5d158 146393c5d158 04"+std::string(128,'a')+" "+std::string(64,'b')+" node-01 bedroom motion";
 dispatch(input.data());
 assert(accepted==1 && captured.device_id=="c3-146393c5d158");
 assert(captured.radio_mac[0]==0x14 && captured.radio_mac[5]==0x58);
 assert(captured.public_key[0]==0x04 && captured.public_key[1]==0xaa);
 assert(captured.installer_code[0]==0xbb && captured.installer_code[31]==0xbb);
 char malformed[]="COMMISSION_EXPECTED_NODE c3-1 000000000000 00 00 node room function";
 dispatch(malformed); assert(accepted==1);
 std::string extra="COMMISSION_EXPECTED_NODE c3-1 000000000000 04"+std::string(128,'1')+" "+std::string(64,'0')+" n r f injected";
 dispatch(extra.data()); assert(accepted==1);
 char unsupported[]="REBOOT"; dispatch(unsupported); assert(accepted==1);
 char status[]="FIXTURE_STATUS"; dispatch(status);
 FixtureCommissioningState state; std::atomic<bool> go{{false}}; std::atomic<int> wins{{0}};
 std::thread a([&]{{while(!go.load()){{}} if(state.try_reserve_request())++wins;}});
 std::thread b([&]{{while(!go.load()){{}} if(state.try_reserve_request())++wins;}});
 go.store(true); a.join(); b.join(); assert(wins.load()==1);
 state.publish(FixtureCommissioningStatus::OfferActive); assert(!state.try_reserve_request());
 state.publish(FixtureCommissioningStatus::TimedOut); assert(state.try_reserve_request());
}}
'''.replace("\n+", "\n"))
            built = subprocess.run(["g++", "-std=c++17", "-pthread", "-DGS_HIL_COMMISSIONING=1",
                                    "-I", str(root), "-I", str(ROOT),
                                    str(harness), "-o", str(root / "test")],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(root / "test")], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_s3_option_is_opt_in_and_legacy_broad_hil_stays_rejected(self):
        cmake = (ROOT / "firmware/hub/target/esp32s3/idf/CMakeLists.txt").read_text()
        main_cmake = (ROOT / "firmware/hub/target/esp32/idf/main/CMakeLists.txt").read_text()
        app = (ROOT / "firmware/hub/target/esp32/idf/main/app_main.cpp").read_text()
        owner = (ROOT / "firmware/hub/target/esp32/hub_runtime_adapter.cpp").read_text()
        state = (ROOT / "firmware/hub/target/esp32/fixture_commissioning_status.hpp").read_text()
        build_script = (ROOT / "scripts/build_validation_targets.py").read_text()
        self.assertIn('option(GS_HIL_COMMISSIONING', cmake)
        self.assertIn('option(GS_HIL_C8_ACK_DROP', cmake)
        self.assertRegex(cmake, r'if\(GS_HIL_C8_ACK_DROP AND \(NOT GS_HIL_COMMISSIONING')
        self.assertRegex(cmake, r'if\(GS_HIL_BUILD OR GS_HIL_CONTROL\)\s+message\(FATAL_ERROR')
        gs40_guard = cmake.split('if(GS40_TEST_ONLY_CLOUDSYNC AND (', 1)[1].split('))', 1)[0]
        self.assertNotIn('GS_HIL_COMMISSIONING', gs40_guard,
                         'the exact-node commissioning adapter must compose with TEST_ONLY CloudSync')
        for forbidden in ('GS_HIL_BUILD', 'GS_HIL_CONTROL', 'GS_HIL_C8_ACK_DROP',
                          'GS_HIL_C8_ACK_HOLD', 'GS_HIL_SIGNED_FOTA'):
            self.assertIn(forbidden, gs40_guard,
                          f'GS40 TEST_ONLY CloudSync must continue rejecting {forbidden}')
        self.assertIn('if(GS_HIL_COMMISSIONING OR GS_HIL_C8_ACK_HOLD OR GS_HIL_SIGNED_FOTA)', main_cmake)
        self.assertIn('if(GS_HIL_COMMISSIONING AND GS_S3_DIAGNOSTIC_ONLY)', cmake)
        self.assertIn('#if GS_HIL_COMMISSIONING || GS_HIL_C8_ACK_HOLD || GS_HIL_SIGNED_FOTA\n    start_fixture_commissioning_control();', app)
        self.assertIn('try_reserve_request', owner)
        self.assertIn('compare_exchange_weak', state)
        self.assertIn('FixtureCommissioningStatus::TimedOut', owner)
        self.assertIn('FixtureCommissioningStatus::AuthenticatedRejoin', owner)
        # Explicit OFF is the production contract; mentioning the option is safe.
        self.assertIn('GS_HIL_COMMISSIONING=OFF', build_script)
        self.assertNotIn('GS_HIL_COMMISSIONING=ON', build_script)
        self.assertNotIn('set(GS_HIL_COMMISSIONING ON', cmake)
        self.assertIn('GS_HIL_COMMISSIONING=OFF',
                      (ROOT / "scripts/build_secure_fota_hub.py").read_text())

    def test_gs40_uart_profile_reuses_the_signed_envelope_receiver(self):
        defaults = (ROOT / "firmware/hub/target/esp32s3/idf/"
                    "sdkconfig.gs40_test_only_uart.defaults").read_text()
        runtime = (ROOT / "firmware/hub/target/esp32s3/gs40_test_only_runtime.cpp").read_text()
        main_cmake = (ROOT / "firmware/hub/target/esp32/idf/main/CMakeLists.txt").read_text()
        self.assertIn("CONFIG_ESP_CONSOLE_UART_NUM=0", defaults)
        self.assertIn("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=n", defaults)
        self.assertIn("CONFIG_ESP_CONSOLE_UART_DEFAULT=y", defaults)
        self.assertIn("CONFIG_ESP_TLS_USE_DS_PERIPHERAL=n", defaults)
        self.assertIn("CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192", defaults)
        self.assertIn("uart_read_bytes(UART_NUM_0", runtime)
        self.assertIn("usb_serial_jtag_read_bytes", runtime)
        self.assertIn("Gs40TestOnlyEnvelopeSession session", runtime)
        self.assertIn("session.begin(challenge, target_public)", runtime)
        self.assertIn("session.accept(envelope, config)", runtime)
        self.assertIn("esp_driver_uart\n        esp_event", main_cmake)

    def test_c8_ack_drop_is_postcommit_durable_and_profile_scoped(self):
        owner = (ROOT / "firmware/hub/target/esp32/hub_runtime_adapter.cpp").read_text()
        control = SOURCE.read_text()
        gate = (ROOT / "firmware/hub/target/esp32/hil_c8_ack_drop_gate.hpp").read_text()
        self.assertIn('processed->ack == AckClass::Durable', owner)
        self.assertIn('C8AckDropGate::eligible(', owner)
        self.assertIn('key_lookup == storage::IdentityLookup::Found', owner)
        self.assertIn('runtime.durable_admission_open()', owner)
        self.assertIn('ack_sent=NO', owner)
        self.assertIn('DROP_NEXT_DURABLE_ACK', control)
        self.assertIn('if (next_token(cursor) != nullptr)', control)
        self.assertIn('processed->state_changed', owner)
        self.assertIn('state_changed &&', gate)

        builder = (ROOT / "scripts/build_gs114_fixture_pair.py").read_text()
        self.assertIn('"GS_HIL_C8_ACK_DROP": "ON" if c8_ack_drop else "OFF"', builder)
        self.assertIn('if args.s3_rpf_diagnostic or args.s3_c8_p8_ack_drop or args.s3_c8_p9_ack_hold:', builder)
        self.assertIn('"c8_ack_drop_fixture_enabled": c8_ack_drop', builder)


class S3ApplicationUpdateGuard(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'tools/local'))
        import gs117_tc001_serial_windows
        self.guard = gs117_tc001_serial_windows.validate_s3_application_update
        self.command_guard = gs117_tc001_serial_windows.validate_s3_update_tool_command
        self.image = bytes([0xe9])+bytes(11)+bytes([9, 0])+bytes(18)+bytes.fromhex('3254cdab')+bytes(220)
        self.sha = hashlib.sha256(self.image).hexdigest()
        self.baseline = dict(device_id='hub-e072a1d38d34', port='COM10',
            serial_number='E0:72:A1:D3:8D:34', home_id='gs177-test-product',
            bootloader_sha256='a'*64, partition_table_sha256='b'*64,
            ota_contract='EXISTING_ENGINEERING_SLOT_SELECTION', active_slot=1)
        self.observed = dict(self.baseline)
        self.layout = {k: v[2:] for k,v in
                       parse_partitions_from_text(OUTBOX_PARTITIONS.read_text()).items()}

    def plan(self, writes=None):
        return self.guard(self.image,self.sha,self.baseline,self.observed,self.layout,writes)

    def test_artifact_binding_snapshots_exact_image_and_never_reuses_session(self):
        from gs117_tc001_serial_windows import bind_s3_update_artifact
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); artifact=root/'candidate.bin'; artifact.write_bytes(self.image)
            evidence,snapshot,manifest=bind_s3_update_artifact(artifact,self.sha,root,'a'*32)
            self.assertEqual(snapshot.read_bytes(),self.image)
            self.assertEqual(manifest['application_sha256'],self.sha)
            self.assertEqual(manifest['target']['device_id'],'hub-e072a1d38d34')
            self.assertEqual(manifest['partition_contract'],
                             'S3_R1_OUTBOX_4M_STATE_256K_OTA_4M')
            artifact.write_bytes(b'changed')
            self.assertEqual(snapshot.read_bytes(),self.image)
            with self.assertRaisesRegex(ValueError,'digest_mismatch'):
                bind_s3_update_artifact(artifact,self.sha,root,'b'*32)
            artifact.write_bytes(self.image)
            with self.assertRaises(FileExistsError):
                bind_s3_update_artifact(artifact,self.sha,root,'a'*32)
            second,_,_=bind_s3_update_artifact(artifact,self.sha,root,'b'*32)
            self.assertNotEqual(evidence,second)

    def test_writer_binding_rejects_tampered_snapshot_or_session(self):
        from gs117_tc001_serial_windows import bind_s3_update_artifact, verify_s3_update_binding
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); artifact=root/'candidate.bin'; artifact.write_bytes(self.image)
            evidence,snapshot,_=bind_s3_update_artifact(artifact,self.sha,root,'a'*32)
            self.assertEqual(verify_s3_update_binding(evidence,'a'*32,self.sha)[1],self.image)
            with self.assertRaisesRegex(ValueError,'binding_invalid'):
                verify_s3_update_binding(evidence,'b'*32,self.sha)
            snapshot.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'binding_mismatch'):
                verify_s3_update_binding(evidence,'a'*32,self.sha)

    def test_artifact_binding_rejects_missing_wrong_target_and_bad_session(self):
        from gs117_tc001_serial_windows import bind_s3_update_artifact
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); artifact=root/'candidate.bin'
            with self.assertRaisesRegex(ValueError,'binding_invalid'):
                bind_s3_update_artifact(artifact,self.sha,root,'a'*32)
            artifact.write_bytes(bytes(256)); bad=hashlib.sha256(artifact.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'image_incompatible'):
                bind_s3_update_artifact(artifact,bad,root,'a'*32)
            artifact.write_bytes(self.image)
            with self.assertRaisesRegex(ValueError,'evidence_binding_invalid'):
                bind_s3_update_artifact(artifact,self.sha,root,'../bad')

    def test_inactive_application_and_supported_selector_only(self):
        plan = self.plan([('application',0x20000,0x400000),('ota_selection',0xF000,0x2000)])
        self.assertEqual(plan['target_slot'],0)
        self.assertEqual(plan['application_offset'],0x20000)

    def test_installed_baseline_port_must_match_current_target(self):
        self.baseline['port'] = 'COM4'
        with self.assertRaisesRegex(ValueError, 'installed_contract_requires_revalidation'):
            self.plan()

    def test_protected_and_active_regions_reject_before_writer(self):
        for name,offset,size in [('bootloader',0,0x8000),('table',0x8000,0x1000),
                ('nvs',0x9000,0x6000),('outbox',0x820000,0x400000),
                ('state',0xC20000,0x40000),('application',0x420000,0x1000),
                ('ota_data_initial',0xF000,0x2000),('whole_flash',0,0x1000000)]:
            with self.subTest(region=name),self.assertRaisesRegex(ValueError,'protected_write'):
                self.plan([(name,offset,size)])

    def test_changed_installed_contract_requires_revalidation(self):
        for field in ('bootloader_sha256','partition_table_sha256','ota_contract'):
            with self.subTest(field=field):
                self.observed=dict(self.baseline); self.observed[field]='c'*64
                with self.assertRaisesRegex(ValueError,'requires_revalidation'): self.plan()

    def test_generated_bootloader_does_not_invalidate_installed_baseline(self):
        self.observed['generated_bootloader_sha256']='c'*64
        self.assertTrue(self.plan()['baseline_reused'])

    def test_wrong_device_and_home_rejected(self):
        for field in ('device_id','serial_number','port','home_id'):
            self.observed=dict(self.baseline);self.observed[field]='wrong'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'identity_mismatch'):self.plan()

    def test_journal_layout_rejected(self):
        self.layout['gs_journal']=self.layout.pop('gs_outbox')
        with self.assertRaisesRegex(ValueError,'layout_incompatible'):self.plan()

    def test_wrong_chip_or_corrupt_image_rejected(self):
        self.image=self.image[:12]+bytes([5])+self.image[13:]
        self.sha=hashlib.sha256(self.image).hexdigest()
        with self.assertRaisesRegex(ValueError,'image_incompatible'):self.plan()

    def test_slot_overflow_rejected(self):
        self.image += bytes(0x400000)
        self.sha=hashlib.sha256(self.image).hexdigest()
        with self.assertRaisesRegex(ValueError,'exceeds_slot'):self.plan()

    def test_official_tool_protected_commands_reject(self):
        plan=self.plan()
        for args in (['erase-flash','0','1'],['erase-region','0','0x8000'],
                     ['erase-region','0x8000','0x1000'],
                     ['erase-region','0x820000','0x400000'],
                     ['write-flash','0','bootloader.bin'],
                     ['write-flash','0x8000','partition-table.bin']):
            with self.subTest(args=args),self.assertRaises(ValueError):
                self.command_guard(args,plan,'app.bin',bytes(8192))
        self.command_guard(['erase-region','0x20000','0x400000'],plan,'app.bin',bytes(8192))

    def test_selector_requires_verified_app_and_preserves_active_copy(self):
        import binascii
        old=bytearray(b'\xff'*8192)
        for copy,seq,state in ((0,29,2),(1,30,0xffffffff)):
            at=copy*4096;old[at:at+4]=seq.to_bytes(4,'little')
            old[at+24:at+28]=state.to_bytes(4,'little')
            old[at+28:at+32]=(binascii.crc32(old[at:at+4],0xffffffff)&0xffffffff).to_bytes(4,'little')
        with self.assertRaisesRegex(ValueError,'selector_erase_not_interruption_safe'):
            self.command_guard(['erase-region','0xf000','0x2000'],self.plan(),
                               'app.bin',bytes(old),application_verified=True)
        new=bytearray(old[:4096]);new[:4]=(31).to_bytes(4,'little')
        new[28:32]=(binascii.crc32(new[:4],0xffffffff)&0xffffffff).to_bytes(4,'little')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'selector.bin';path.write_bytes(new)
            args=['write-flash','0xf000',str(path)]
            with self.assertRaisesRegex(ValueError,'protected_write'):
                self.command_guard(args,self.plan(),'app.bin',bytes(old))
            self.command_guard(args,self.plan(),'app.bin',bytes(old),application_verified=True)
            new[24]=3;path.write_bytes(new)
            with self.assertRaisesRegex(ValueError,'selector_change'):
                self.command_guard(args,self.plan(),'app.bin',bytes(old),application_verified=True)
            path.write_bytes(bytes(old[:4096]))
            with self.assertRaisesRegex(ValueError,'active_copy_write_rejected'):
                self.command_guard(['write-flash','0x10000',str(path)],self.plan(),
                                   'app.bin',bytes(old),application_verified=True)
            self.command_guard(args,self.plan(),'app.bin',bytes(old),application_verified=True)

    def test_official_application_write_binds_exact_path_and_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'app.bin';path.write_bytes(self.image)
            args=['write-flash','0x20000',str(path)]
            self.command_guard(args,self.plan(),path,bytes(8192))
            path.write_bytes(self.image+b'x')
            with self.assertRaisesRegex(ValueError,'application_changed'):
                self.command_guard(args,self.plan(),path,bytes(8192))

    def test_idf_target_uses_keywords_despite_added_bootloader_parameters(self):
        import gs117_tc001_serial_windows as helper
        from types import SimpleNamespace
        calls=[]
        class Parttool:
            def __init__(self,port=None,baud=None,partition_table_offset=0x8000,
                         primary_bootloader_offset=None,recovery_bootloader_offset=None,
                         partition_table_file=None,esptool_args=None):
                calls.append((port,primary_bootloader_offset,recovery_bootloader_offset,
                              partition_table_file,esptool_args))
        class Ota:
            def __init__(self,*args,**kwargs):
                raise AssertionError('obsolete positional constructor must not run')
        result=helper.s3_official_application_target(OUTBOX_PARTITIONS,bytes(8192),
            port='COM10',
            parttool_module=SimpleNamespace(ParttoolTarget=Parttool),
            otatool_module=SimpleNamespace(OtatoolTarget=Ota))
        self.assertEqual(calls,[('COM10',None,None,str(OUTBOX_PARTITIONS),
            ['chip=esp32s3','before=no-reset','after=no-reset'])])
        self.assertEqual(result.otadata,bytes(8192))
        self.assertEqual(result.spi_flash_sec_size,8192)


if __name__ == "__main__":
    unittest.main()
