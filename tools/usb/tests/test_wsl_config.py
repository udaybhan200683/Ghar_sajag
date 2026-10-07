import importlib.util
from pathlib import Path
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('config', Path(__file__).parents[1] / 'gs-usb-wsl-config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

class ConfigurationTests(unittest.TestCase):
    def test_install_twice_and_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / 'home/user'
            home.mkdir(parents=True)
            original = '# custom\ncase $- in *i*) ;; *) return;; esac\n'
            (home / '.bashrc').write_text(original)
            (root / 'etc').mkdir()
            (root / 'etc/wsl.conf').write_text('[boot]\ncommand=echo existing\n[network]\ngenerateHosts=false\n')
            config.configure(root, home)
            before = {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            config.configure(root, home)
            after = {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertTrue((home / '.bashrc').read_text().startswith(config.BEGIN))
            config.configure(root, home, remove=True)
            self.assertEqual((home / '.bashrc').read_text(), original)
            self.assertIn('command=echo existing', (root / 'etc/wsl.conf').read_text())
            self.assertFalse((root / 'etc/udev/rules.d/99-ghar-sajag-usb.rules').exists())
    def test_duplicate_blocks(self):
        block=config.managed_block('',config.EXPORTS)
        self.assertEqual(config.managed_block(block+block,config.EXPORTS).count(config.BEGIN),1)
    def test_incomplete_block_rejected(self):
        with self.assertRaises(ValueError): config.managed_block(config.BEGIN)
    def test_rules(self):
        self.assertIn('10c4',config.RULES)
        self.assertIn('303a',config.RULES)
        self.assertIn('IMPORT{builtin}="usb_id"',config.RULES)
        self.assertIn('ENV{ID_USB_INTERFACE_NUM}=="00"',config.RULES)
        self.assertNotIn('ttyUSB0',config.RULES)
        self.assertNotIn('ttyACM0',config.RULES)
    def test_boot_preservation(self):
        text='[network]\ngenerateHosts=false\n'
        new=config.boot_command(text,'/our/helper')
        self.assertTrue(new.startswith(text))
        self.assertEqual(config.boot_command(new),'/our/helper')
    def test_changed_boot_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            home=root/'home/user'
            home.mkdir(parents=True)
            config.configure(root,home)
            (root/'etc/wsl.conf').write_text('[boot]\ncommand=changed\n')
            (home/'.bashrc').write_text('custom unchanged\n')
            with self.assertRaises(ValueError): config.configure(root,home)
            self.assertEqual((home/'.bashrc').read_text(),'custom unchanged\n')
    def test_installer_contract(self):
        script=(Path(__file__).parents[1]/'install-gs-usb-zero-touch.ps1').read_text()
        self.assertNotIn('wslpath',script)
        self.assertIn('ConvertTo-GsWslPath',script)
        self.assertIn('Stop-ScheduledTask',script)
        self.assertIn('-Force | Out-Null',script)
        self.assertIn('-RunLevel Highest',script)
        self.assertIn("$installed.State -ne 'Running'",script)

if __name__=='__main__': unittest.main()
