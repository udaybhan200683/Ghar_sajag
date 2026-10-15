"""Focused parser/build-isolation tests for the S3-only commissioning fixture."""
from pathlib import Path
import hashlib
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "firmware/hub/target/esp32/idf/main/fixture_commissioning_control.cpp"
sys.path.insert(0, str(ROOT))
from scripts.build_gs114_fixture_pair import (
    build_environment,
    parse_partitions_from_text,
    stage_node_firmware_asset,
    validate_s3_fixture_artifact,
)


class S3FixtureCommissioning(unittest.TestCase):
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
        node_asset.write_bytes(b"W (%lu) %s: HIL_ERROR command=INJECT_MOTION disabled_for_physical_wake")
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
            cache.write_text(cache.read_text() + "GS_HIL_C8_ACK_HOLD:BOOL=ON\nGS_HIL_SIGNED_FOTA:BOOL=OFF\n")
            app.write_bytes(app.read_bytes() + b"ARM_C8_ACK_HOLD")
            profile = validate_s3_fixture_artifact(sdkconfig, cache, partitions,
                                                   app, node, c8_ack_hold=True)
            self.assertTrue(profile["c8_ack_hold_fixture_enabled"])
            app.write_bytes(app.read_bytes().replace(b"ARM_C8_ACK_HOLD", b""))
            with self.assertRaisesRegex(ValueError, "ACK-hold command"):
                validate_s3_fixture_artifact(sdkconfig, cache, partitions,
                                             app, node, c8_ack_hold=True)
            cache.write_text(cache.read_text().replace("GS_HIL_C8_ACK_HOLD:BOOL=ON",
                                                       "GS_HIL_C8_ACK_HOLD:BOOL=OFF"))
            with self.assertRaisesRegex(ValueError, "CMake options"):
                validate_s3_fixture_artifact(sdkconfig, cache, partitions,
                                             app, node, c8_ack_hold=True)

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
            built = subprocess.run(["g++", "-std=c++17", "-pthread", "-I", str(root), "-I", str(ROOT),
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
        self.assertIn('if(GS_HIL_COMMISSIONING)', main_cmake)
        self.assertIn('if(GS_HIL_COMMISSIONING AND GS_S3_DIAGNOSTIC_ONLY)', cmake)
        self.assertIn('#if GS_HIL_COMMISSIONING\n    start_fixture_commissioning_control();', app)
        self.assertIn('try_reserve_request', owner)
        self.assertIn('compare_exchange_weak', state)
        self.assertIn('FixtureCommissioningStatus::TimedOut', owner)
        self.assertIn('FixtureCommissioningStatus::AuthenticatedRejoin', owner)
        self.assertNotIn('GS_HIL_COMMISSIONING', build_script)
        self.assertNotIn('set(GS_HIL_COMMISSIONING ON', cmake)

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


if __name__ == "__main__":
    unittest.main()
