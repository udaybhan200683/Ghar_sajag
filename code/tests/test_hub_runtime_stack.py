"""Offline regression against actual Xtensa frames; never opens a port.

The original task's entry frame exceeds its entire allocation. Native host
threads cannot reproduce ESP-IDF's task boundary, so inspect the target ELF.
"""
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
OLD_ELF = Path(os.environ.get('GS_HUB_OLD_STACK_ELF',
                            '/tmp/gs_r1_normal_hub/gs_hw_m1_hub.elf'))
NEW_ELF = Path(os.environ.get('GS_HUB_STACK_ELF',
                             ROOT / 'build/hub_owner_stackfix/gs_hw_m1_hub.elf'))
OBJDUMP = '/home/udaybhan/.espressif/tools/xtensa-esp-elf/esp-15.2.0_20251204/xtensa-esp-elf/bin/xtensa-esp32-elf-objdump'
OWNER = 'gs::hub::target::(anonymous namespace)::secure_owner_task(void*)'
RECOVER = 'gs::hub::durable::HubDurabilityOwner::recover(std::array<unsigned char, 32u> const*)'
GENESIS = 'gs::hub::durable::HubDurabilityOwner::initialize_epoch_one(bool)'
CHECKPOINT = 'gs::hub::durable::DurableStore::checkpoint(gs::hub::durable::Checkpoint const&)'
STORE_RECOVER = 'gs::hub::durable::DurableStore::recover(gs::hub::durable::RecoveryState&)'


def frames(elf):
    text = subprocess.check_output([OBJDUMP, '-dC', str(elf)], text=True)
    return {m[1]: int(m[2], 0) for m in re.finditer(
        r'^[0-9a-f]+ <([^\n]+)>:\n[^\n]*entry\s+a1,\s+(0x[0-9a-f]+|[0-9]+)',
        text, re.M)}


@unittest.skipUnless(Path(OBJDUMP).is_file(), 'Requires Xtensa objdump')
class TargetStackBudget(unittest.TestCase):
    @unittest.skipUnless(OLD_ELF.is_file(), 'Requires original Hub target ELF (GS_HUB_OLD_STACK_ELF)')
    def test_original_owner_frame_alone_exceeds_allocation(self):
        measured = frames(OLD_ELF)[OWNER]
        self.assertEqual(measured, 23456)
        self.assertGreater(measured, 16384)

    @unittest.skipUnless(NEW_ELF.is_file(), 'Requires corrected Hub target ELF (GS_HUB_STACK_ELF)')
    def test_recovery_hook_really_blocks_for_one_tick_in_target_elf(self):
        # Verify compiled target behavior; taskYIELD would not run IDLE1 while
        # the higher-priority owner remains ready.
        text = subprocess.check_output([OBJDUMP, '-dC', str(NEW_ELF)], text=True)
        blocks = re.split(r'(?m)^(?=[0-9a-f]+ <)', text)
        hooks = [block for block in blocks if
                 'secure_owner_task(void*)::{lambda()' in block.split('\n', 1)[0]
                 and '::_FUN()>' in block.split('\n', 1)[0]]
        self.assertEqual(len(hooks), 1)
        self.assertIn('<vTaskDelay>', hooks[0])
        self.assertRegex(hooks[0], r'movi\.n\s+a10, 1')

    @unittest.skipUnless(NEW_ELF.is_file(), 'Requires corrected Hub target ELF (GS_HUB_STACK_ELF)')
    def test_corrected_target_allocation_covers_nested_frames_and_reserve(self):
        measured = frames(NEW_ELF)
        source = (ROOT / 'firmware/hub/target/esp32/hub_runtime_adapter.cpp').read_text()
        budget = int(re.search(r'kSecureOwnerStackBytes\s*=\s*(\d+)', source)[1])
        self.assertIn('"gs_hub_owner", kSecureOwnerStackBytes', source)
        # Conservative nested fresh/restart checkpoint path, including the
        # checkpoint's own authenticated readback recovery. Additional reserve
        # covers NVS, crypto, logging, allocator and Xtensa window spills.
        required = sum(measured[f] for f in
                       [OWNER, RECOVER, GENESIS, CHECKPOINT, STORE_RECOVER])
        print(f'HUB TARGET STACK frames={required} allocation={budget} reserve={budget-required}')
        self.assertGreaterEqual(budget, required + 16384)
        self.assertIn('uxTaskGetStackHighWaterMark(nullptr)', source)


if __name__ == '__main__':
    unittest.main()
