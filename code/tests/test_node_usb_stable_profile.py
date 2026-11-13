"""Physical-wake qualification can run without the unrelated UART HIL controls."""
from pathlib import Path
import ast
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
NODE=ROOT/'firmware/node/target/esp32c3'
sys.path.insert(0,str(ROOT))
from tools.local import gs117_tc001_serial_windows as serial_tool

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
        observe = next(node for node in ast.parse(serial_helper).body
                       if isinstance(node, ast.FunctionDef) and node.name == 'observe')
        cleanup = next(node.finalbody for node in observe.body
                       if isinstance(node, ast.Try) and node.finalbody)
        loops = [node for statement in cleanup for node in ast.walk(statement)
                 if isinstance(node, ast.For) and ast.unparse(node.iter) == 'reversed(streams)']
        self.assertEqual(len(loops), 1)
        calls = [node.func for node in ast.walk(loops[0])
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertTrue(any(ast.unparse(call) == 'stream.close' for call in calls))
        # The existing registered collector tests execute close failures and
        # prove the other handle is still closed. Cleanup must never sample.
        self.assertFalse(any(call.attr in {'read', 'write', 'flush'} for call in calls))
        self.assertIn('if c3_stream.is_open:\n            c3_stream.close()', serial_helper)

    def test_get_state_remains_enabled_in_both_hil_profiles(self):
        source=(NODE/'idf/main/hil_control.cpp').read_text()
        start=source.index('std::strcmp(command, "GET_STATE")')
        end=source.index('std::strcmp(command, "GET_TEST_QR")',start)
        branch=source[start:end]
        self.assertIn('hil_log_state()',branch)
        self.assertNotIn('#if GS_BAT_C8_PHYSICAL_WAKE',branch)

    # GS117-HIL-CMD-LINE-001: bounded malformed-line rejection and recovery.
    def test_hil_command_parser_recovers_after_oversized_serial_line(self):
        source=ROOT/'tests/cpp/hil_command_line_validation.cpp'
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'hil_command_line_validation'
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-pedantic',
                            '-I'+str(ROOT),str(source),'-o',str(binary)],check=True)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
        self.assertIn('C3 HIL command parser PASS checks=7',result.stdout)

    # GS117-C3-REOPEN-001: repeated bounded observations release and reacquire COM4.
    def test_c3_readonly_observer_reopens_registered_port_for_following_run(self):
        class Clock:
            def __init__(self): self.value=0.0
            def __call__(self):
                value=self.value
                self.value+=0.05
                return value

        class FakeSerial:
            def __init__(self):
                self.port='';self.buffer=bytearray();self.is_open=False;self.writes=[]
                self.timeout=None;self.write_timeout=None;self.dtr=True;self.rts=True
                self.opens=0;self.closes=0
            @property
            def in_waiting(self): return len(self.buffer)
            def open(self):
                self.is_open=True;self.opens+=1
            def write(self,value):
                self.writes.append(value)
                if value==b'GET_STATE\n':
                    self.buffer.extend(
                        b'I (100) HIL_STATE role=c3 session=141 '
                        b'power_mode=HIL_AWAKE_TEST_ONLY hil_build=0 hil_control=1 '
                        b'physical_wake=0 runtime_live=11 sensing_live=12 '
                        b'pending_inject=0 retained=0 in_flight=0\n'
                        b'I (101) HIL_OK command=GET_STATE\n')
                return len(value)
            def flush(self): pass
            def read(self,count):
                value=bytes(self.buffer[:count]);del self.buffer[:count];return value
            def close(self):
                self.is_open=False;self.closes+=1

        c3={'port':'COM4','serial_number':'14:63:93:C5:D1:58',
            'usb_hwid':'USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58'}
        s3={'port':'COM10','serial_number':'E0:72:A1:D3:8D:34',
            'usb_hwid':'USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34'}
        streams=[FakeSerial(),FakeSerial()]
        clock=Clock()
        with (patch.object(serial_tool,'ports',return_value=[c3,s3]),
              patch.object(serial_tool.serial,'Serial',side_effect=streams),
              patch.object(serial_tool.time,'monotonic',side_effect=clock),
              patch.object(serial_tool.time,'sleep',return_value=None)):
            results=[serial_tool.observe_node(
                {'c3':c3,'s3':s3,'observation_seconds':10}) for _ in range(2)]

        self.assertEqual(len(results),2)
        for stream,result in zip(streams,results):
            self.assertEqual(stream.port,'COM4')
            self.assertEqual(stream.opens,1)
            self.assertEqual(stream.closes,1)
            self.assertFalse(stream.is_open)
            self.assertEqual(stream.writes,[b'GET_STATE\n'])
            self.assertEqual(result['get_state_ack_count'],1)
            self.assertFalse(result['s3_serial_opened'])
            self.assertFalse(result['motion_injection'])

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
