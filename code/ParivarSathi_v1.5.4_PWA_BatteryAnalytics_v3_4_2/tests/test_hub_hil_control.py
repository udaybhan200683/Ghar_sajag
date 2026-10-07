"""Compile and exercise the real Hub HIL dispatcher without ESP-IDF or ports."""
from pathlib import Path
import contextlib
import importlib.util
import io
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class HubControl(unittest.TestCase):
    def test_commissioning_command_and_rejected_input(self):
        headers = {
            'esp_err.h': '''#pragma once
#include <cstdlib>
using esp_err_t=int;
constexpr int ESP_OK=0,ESP_ERR_NO_MEM=1;
#define ESP_ERROR_CHECK(x) do { if((x)!=ESP_OK) std::abort(); } while(false)
''',
            'esp_log.h': '''#pragma once
#include <cstring>
extern int unknown;
inline void record(const char* format){if(std::strcmp(format,"HIL_ERROR unknown_command")==0)++unknown;}
#define ESP_LOGI(tag,format,...) record(format)
#define ESP_LOGW(tag,format,...) record(format)
''',
            'esp_app_desc.h': '''#pragma once
struct App {const char* version;};
inline App* esp_app_get_description(){static App app{"offline-test"};return &app;}
''',
            'esp_system.h': '#pragma once\ninline void esp_restart(){}\n',
            'freertos/task.h': '''#pragma once
constexpr int pdPASS=1;
inline int xTaskCreate(void(*)(void*),const char*,unsigned,void*,unsigned,void*){return pdPASS;}
struct EndOfInput {};
inline void vTaskDelay(int){throw EndOfInput{};}
#define pdMS_TO_TICKS(x) (x)
''',
            'firmware/hub/target/esp32/hub_runtime_adapter.hpp': '''#pragma once
#include <array>
#include <cstdint>
#include <string>
namespace gs::hub::target {
struct HubSecurityLink {struct ExpectedNode {
std::string device_id,logical_id,room,function;
std::array<unsigned char,6> radio_mac{};
std::array<unsigned char,65> public_key{};
std::array<unsigned char,32> installer_code{};
};};
bool request_node_commissioning(HubSecurityLink::ExpectedNode);
inline void hil_reboot_after_next_durable_commit(){}
inline void hil_set_logical_online(bool){}
inline void hil_log_state(){}
inline void hil_log_test_identity(){}
}
''',
        }
        source = r'''
#include <cassert>
#include "firmware/hub/target/esp32/idf/main/hil_control.cpp"
int unknown=0,queued=0;
namespace gs::hub::target {
bool request_node_commissioning(HubSecurityLink::ExpectedNode node){
    ++queued;
    assert(node.device_id=="c3-146393c5d158");
    assert(node.logical_id=="hil-signed-fota");
    assert(node.radio_mac[0]==0x14 && node.radio_mac[5]==0x58);
    return true;
}
bool hil_request_authenticated_fota(FotaStartRequest){return false;}
}
int main(){
    // Exactly the controller's command shape and production parser branch.
    const std::string command="COMMISSION_TEST_NODE c3-146393c5d158 146393c5d158 04"+
        std::string(128,'1')+" "+std::string(64,'0')+" hil-signed-fota test pir";
    assert(command.size()<511);
    dispatch_command(command.c_str());
    assert(queued==1 && unknown==0);
    dispatch_command("unrecognized-one");
    dispatch_command("unrecognized-two");
    assert(queued==1 && unknown==2);
    dispatch_command("COMMISSION_TEST_NODE invalid");
    dispatch_command("");
    assert(queued==1 && unknown==2);
    // Exercise the actual RX loop, including CRLF and EOF handling.
    FILE* input=std::tmpfile(); assert(input);
    const auto wire=command+"\r\n";
    assert(std::fwrite(wire.data(),1,wire.size(),input)==wire.size());
    std::rewind(input); FILE* saved=stdin; stdin=input;
    try {control_task(nullptr);} catch(const EndOfInput&) {}
    stdin=saved; std::fclose(input);
    assert(queued==2 && unknown==2);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for name, text in headers.items():
                file = path / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(text)
            cpp = path / 'test.cpp'
            cpp.write_text(source)
            binary = path / 'test'
            subprocess.run(['g++', '-std=c++17', '-DGS_HIL_BUILD=0',
                            '-DGS_HIL_CONTROL=1', '-I' + str(path), '-I' + str(ROOT),
                            str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
