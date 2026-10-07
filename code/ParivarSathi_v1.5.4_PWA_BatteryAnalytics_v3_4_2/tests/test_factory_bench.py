"""Offline factory-tool safety checks: no physical ports are opened."""
import importlib.util
import os
from pathlib import Path
import struct
import binascii
import unittest
import tempfile
import contextlib
import io
from types import SimpleNamespace
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bench',root/'tools/factory/bench.py')
bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)

class Safety(unittest.TestCase):
    def table(self):
        import sys
        sys.path.insert(0,str(Path(os.environ['IDF_PATH'])/'components/partition_table'))
        import gen_esp32part
        return gen_esp32part.PartitionTable.from_csv((root/'firmware/hub/target/esp32/idf/partitions.csv').read_text()).to_binary()
    def ota(self,seq,state=2):
        data=bytearray(b'\xff'*0x2000)
        struct.pack_into('<I',data,0,seq);struct.pack_into('<I',data,24,state)
        struct.pack_into('<I',data,28,binascii.crc32(struct.pack('<I',seq),0xffffffff)&0xffffffff)
        return bytes(data)
    def test_erased_ota(self):
        self.assertEqual(bench.active_app_offset(self.table(),b'\xff'*0x2000,'hub'),0x20000)
    def test_confirmed_slots(self):
        for seq,offset in [(1,0x20000),(2,0x200000),(3,0x20000)]:
            self.assertEqual(bench.active_app_offset(self.table(),self.ota(seq),'hub'),offset)
    def test_pending_refused(self):
        with self.assertRaises(ValueError):bench.active_app_offset(self.table(),self.ota(1,1),'hub')
    def test_invalid_ota_refused(self):
        with self.assertRaises(ValueError):bench.active_app_offset(self.table(),bytes(0x2000),'hub')
    def test_accelerated_aes_profile_is_node_initializer_only(self):
        for role in ['hub','node']:
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)
                (path/'gs_dev_fresh_init.bin').write_bytes(b'\xe9')
                args=SimpleNamespace(role=role,build=path,normal_hub=False)
                with patch.object(bench,'run') as run, contextlib.redirect_stdout(io.StringIO()):
                    bench.build(args)
                defaults=next(str(a) for a in run.call_args[0][0] if str(a).startswith('-DSDKCONFIG_DEFAULTS='))
                self.assertEqual('sdkconfig.node.defaults' in defaults,role=='node')
        profile=(root/'tools/factory/esp32_init/sdkconfig.node.defaults').read_text()
        self.assertIn('CONFIG_MBEDTLS_HARDWARE_AES=y',profile)
    def test_cached_software_node_initializer_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            (path/'sdkconfig').write_text('# CONFIG_MBEDTLS_HARDWARE_AES is not set\n')
            with patch.object(bench,'run') as run:
                with self.assertRaises(ValueError):
                    bench.build(SimpleNamespace(role='node',build=path,normal_hub=False))
                run.assert_not_called()
    def test_non_app_flash_refused(self):
        with patch.object(bench,'run') as run:
            for offset in [0x9000,0x8000,0xf000,0x3e0000]:
                with self.assertRaises(ValueError):bench.app_flash('hub','NEVER_OPEN',offset,Path('/missing'))
            run.assert_not_called()

if __name__=='__main__':unittest.main()
