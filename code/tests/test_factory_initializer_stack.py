"""Target ELF stack-budget regression; does not connect to hardware.

A native host stack does not reproduce ESP-IDF's bounded task stack. Instead
use the actual Xtensa frames on the reported nested genesis call path.
"""
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
ELF=os.environ.get('GS_FACTORY_STACK_ELF','/tmp/gs_r1_factory_hub_crash_f26574a80.elf')
OBJDUMP='/home/udaybhan/.espressif/tools/xtensa-esp-elf/esp-15.2.0_20251204/xtensa-esp-elf/bin/xtensa-esp32-elf-objdump'
PATH=[
    '(anonymous namespace)::run(void*)',
    '(anonymous namespace)::initialize(std::array<unsigned char, 6u> const&)',
    'gs::hub::durable::HubDurabilityOwner::recover(std::array<unsigned char, 32u> const*)',
    'gs::hub::durable::HubDurabilityOwner::initialize_epoch_one(bool)',
    'gs::hub::durable::DurableStore::checkpoint(gs::hub::durable::Checkpoint const&)',
    'gs::hub::durable::DurableStore::recover(gs::hub::durable::RecoveryState&)']

def frames():
    text=subprocess.check_output([OBJDUMP,'-dC',ELF],text=True)
    result={}
    for name in PATH:
        pattern=r'^[0-9a-f]+ <'+re.escape(name)+r'>:\n[^\n]*entry\s+a1,\s+(0x[0-9a-f]+|[0-9]+)'
        match=re.search(pattern,text,re.M)
        if not match:raise AssertionError('Missing target frame: '+name)
        result[name]=int(match[1],0)
    return result

@unittest.skipUnless(Path(ELF).is_file() and Path(OBJDUMP).is_file(),
                     "Requires initializer target ELF and Xtensa toolchain")
class StackBudget(unittest.TestCase):
    def test_old_budget_reproduces_failure(self):
        self.assertGreater(sum(frames().values()),20480)
    def test_configured_hub_budget_includes_nested_frames_and_reserve(self):
        source=(ROOT/'tools/factory/esp32_init/main/app_main.cpp').read_text()
        configured=re.search(r'kHubInitializerStackBytes\s*=\s*(\d+)',source)
        budget=int(configured[1]) if configured else 20480
        required=sum(frames().values())
        print(f'Target nested frames={required} configured={budget} reserve={budget-required}')
        # Reserve for NVS, crypto, allocator, window spills, logging and RTOS.
        self.assertGreaterEqual(budget,required+16384)

if __name__=='__main__':unittest.main()
