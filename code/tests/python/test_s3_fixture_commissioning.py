"""Focused parser/build-isolation tests for the S3-only commissioning fixture."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "firmware/hub/target/esp32/idf/main/fixture_commissioning_control.cpp"


class S3FixtureCommissioning(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
