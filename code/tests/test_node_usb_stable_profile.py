"""Physical-wake qualification can run without the unrelated UART HIL controls."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
NODE=ROOT/'firmware/node/target/esp32c3'

class UsbStableProfile(unittest.TestCase):
    def test_sleep_gate_profile_matrix(self):
        harness='''
#include "firmware/node/target/esp32c3/physical_wake_capability.hpp"
using gs::node::target::physical_wake_permitted;
static_assert(physical_wake_permitted(false, false, false), "production default sleep remains available");
static_assert(physical_wake_permitted(false, false, true), "minimal C8 qualification can use real wake and sleep");
static_assert(physical_wake_permitted(false, false, true), "minimal C8 qualification can sleep");
static_assert(physical_wake_permitted(false, true, true), "controlled C8 physical-wake build can sleep");
static_assert(!physical_wake_permitted(false, true, false), "USB-stable HIL build stays awake");
static_assert(!physical_wake_permitted(true, true, false), "legacy HIL build stays awake");
int main() { return 0; }
'''
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'profile.cpp';binary=Path(tmp)/'profile'
            source.write_text(harness)
            subprocess.run(['g++','-std=c++17','-I'+str(ROOT),'-I'+str(ROOT/'firmware/common/shared/include'),
                            str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

    def test_usb_stable_build_flags_preserve_product_composition(self):
        cmake=(NODE/'idf/CMakeLists.txt').read_text()
        self.assertIn('GS_HIL_BUILD "Enable the USB HIL control plane',cmake)
        self.assertIn('GS_HIL_CONTROL "Enable test-only UART controls',cmake)
        self.assertIn('GS_BAT_C8_PHYSICAL_WAKE "Enable BAT-C8 physical-wake telemetry',cmake)
        self.assertIn('GS_BAT_C8_PHYSICAL_WAKE requires GS_HIL_BUILD=OFF',cmake)
        self.assertIn('GS_BAT_C8_PHYSICAL_WAKE=$<BOOL:${GS_BAT_C8_PHYSICAL_WAKE}>',
                      (NODE/'idf/main/CMakeLists.txt').read_text())
        adapter=(NODE/'node_runtime_adapter.cpp').read_text()
        self.assertIn('#if GS_HIL_CONTROL || GS_BAT_C8_PHYSICAL_WAKE',adapter)
        control=(NODE/'idf/main/app_main.cpp').read_text()
        self.assertIn('#if GS_HIL_CONTROL\n    start_hil_control();',control)
        control_source=(NODE/'idf/main/hil_control.cpp').read_text()
        runtime_source=(NODE/'node_runtime_adapter.cpp').read_text()
        self.assertIn('power_mode=%s hil_build=%d hil_control=%d physical_wake=%d', control_source)
        self.assertIn('power_mode=%s hil_build=%d hil_control=%d physical_wake=%d', runtime_source)
        self.assertIn('"HIL_AWAKE_TEST_ONLY"', control_source)
        self.assertIn('if (!returned_from_light_sleep) vTaskDelay(pdMS_TO_TICKS(kPirPollMs));', adapter)
        serial_helper=(ROOT/'tools/local/gs117_tc001_serial_windows.py').read_text()
        self.assertIn('finally:', serial_helper)
        self.assertIn('if c3_stream.is_open:\n            c3_stream.close()', serial_helper)
        self.assertIn('if s3_stream.is_open:\n            s3_stream.close()', serial_helper)

    def test_get_state_remains_enabled_in_both_hil_profiles(self):
        source=(NODE/'idf/main/hil_control.cpp').read_text()
        start=source.index('std::strcmp(command, "GET_STATE")')
        end=source.index('std::strcmp(command, "GET_TEST_QR")',start)
        branch=source[start:end]
        self.assertIn('hil_log_state()',branch)
        self.assertNotIn('#if GS_BAT_C8_PHYSICAL_WAKE',branch)

    def test_ack_retry_and_recovery_paths_are_unmodified_by_sleep_profile(self):
        adapter=(NODE/'node_runtime_adapter.cpp').read_text()
        store=(ROOT/'firmware/node/storage/node_store.cpp').read_text()
        self.assertIn('runtime.acknowledge(key, decoded.value->ack_type)',adapter)
        self.assertIn('if (retired)',adapter)
        self.assertIn('runtime.persisted() != retained_before',adapter)
        self.assertIn('runtime.next_retry_deadline()',adapter)
        self.assertIn('runtime.persisted()',adapter)
        self.assertRegex(store,r'bool NodeStore::acknowledge\(')
        self.assertIn('AckClass::Durable',store)

if __name__=='__main__':unittest.main()
