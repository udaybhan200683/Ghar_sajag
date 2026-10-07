"""Commissioning transport/state-machine regression; entirely fake serial."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('factory_bench', ROOT / 'tools/factory/bench.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
DEVICE = 'c3-146393c5d158'
PUBLIC = '04' + '1' * 128
CODE = 'a' * 64  # Synthetic, never physical credentials.
NODE_READY = b'HIL_READY role=c3 protocol=1\r\n'
HUB_READY = b'HIL_READY role=hub protocol=1\r\n'
DURABILITY = b'HIL_DURABILITY owner=Ready epoch=1 generation=2 native=1 migration=NONE\r\n'
OWNER = b'Authenticated Hub owner started enrolled=0 storage_epoch=1\r\n'


class Commission(unittest.TestCase):
    def run_flow(self, hub_lines=None, node_lines=None, success=True, short_write=False, reply=None):
        clock = [0.0]
        writes = []
        holder = {}

        class Serial:
            def __init__(self, role, lines):
                self.role = role; self.lines = list(lines); self.written = bytearray()
                self.qr_returned = self.rejoin_returned = False
                self.ready = self.owner = self.durable = False
                self.seen = b''
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def flush(self): pass
            def write(self, data):
                writes.append((self.role, bytes(data)))
                if self.role == 'node':
                    assert self.ready, 'QR requested before Node ready'
                else:
                    assert self.ready, 'Commissioning before Hub HIL_READY'
                    assert self.owner and self.durable, 'Commissioning before owner Ready'
                if short_write and self.role == 'hub':
                    self.written.extend(data[:-1]); return len(data)-1
                self.written.extend(data); return len(data)
            def read(self, size):
                clock[0] += .1
                if self.lines:
                    data = self.lines.pop(0)
                elif self.role == 'node' and self.written and not self.qr_returned:
                    self.qr_returned = True
                    data = (f'HIL_TEST_QR device_id={DEVICE} public_key={PUBLIC}\r\n'
                            f'HIL_TEST_CODE device_id={DEVICE} installer_code={CODE}\r\n').encode()
                elif self.role == 'hub' and self.written.endswith(b'\n') and success and not self.rejoin_returned:
                    self.rejoin_returned = True
                    data = reply if reply is not None else f'Authenticated rejoin device={DEVICE} session=10\r\n'.encode()
                else:
                    data = b''
                self.seen += data
                ready = NODE_READY if self.role == 'node' else HUB_READY
                self.ready = ready in self.seen
                self.owner = OWNER in self.seen
                self.durable = DURABILITY in self.seen
                return data

        node = Serial('node', node_lines if node_lines is not None else [b'booting\r\n', NODE_READY])
        hub = Serial('hub', hub_lines if hub_lines is not None else
                     [b'rst:0x1 booting\r\n', b'', DURABILITY, b'', HUB_READY, b'', OWNER])
        holder.update(node=node, hub=hub, writes=writes, error=None)
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(node_port='NO_NODE', hub_port='NO_HUB', device=DEVICE,
                                   evidence=Path(folder), timeout=5)
            with patch.object(bench, 'open_serial', side_effect=[node, hub]) as opened, \
                    patch.object(bench.time, 'monotonic', side_effect=lambda: clock[0]), \
                    patch.object(bench.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                try:
                    bench.commission(args)
                except (ValueError, TimeoutError) as error:
                    holder['error'] = error
                self.assertEqual([c.args[0] for c in opened.call_args_list], ['NO_NODE', 'NO_HUB'])
            holder['evidence'] = (Path(folder)/'enrollment.log').read_text()
        return holder

    def assert_one(self, result):
        expected = f'COMMISSION_TEST_NODE {DEVICE} {DEVICE[3:]} {PUBLIC} {CODE} hil-signed-fota test pir\n'.encode()
        self.assertEqual(result['hub'].written, expected)
        self.assertEqual(result['hub'].written.count(b'\n'), 1)
        self.assertEqual(result['evidence'].count('TX hub bytes='), 1)
        self.assertNotIn(CODE, result['evidence'])
        self.assertIn('REDACTED', result['evidence'])

    def test_ready_gates_and_success(self):
        result = self.run_flow()
        self.assertIsNone(result['error']); self.assert_one(result)
        self.assertEqual(result['node'].written, b'GET_TEST_QR\n')
        self.assertIn('ENROLLMENT_AUTHENTICATED', result['evidence'])

    def test_no_tx_before_hub_hil_ready(self):
        result = self.run_flow(hub_lines=[DURABILITY, OWNER])
        self.assertIsInstance(result['error'], TimeoutError)
        self.assertFalse(result['hub'].written)

    def test_no_tx_before_owner_ready(self):
        for lines in [[HUB_READY, DURABILITY], [HUB_READY, OWNER]]:
            result = self.run_flow(hub_lines=lines)
            self.assertIsInstance(result['error'], TimeoutError)
            self.assertFalse(result['hub'].written)

    def test_no_qr_before_node_ready(self):
        result = self.run_flow(node_lines=[b'booting\r\n'])
        self.assertFalse(result['node'].written)
        self.assertFalse(result['hub'].written)

    def test_crlf_and_partial_rx_are_one_line(self):
        result = self.run_flow(hub_lines=[HUB_READY[:7], HUB_READY[7:-1], HUB_READY[-1:], DURABILITY, OWNER])
        self.assertIsNone(result['error']); self.assert_one(result)
        self.assertEqual(result['evidence'].count('hub: HIL_READY'), 1)

    def test_stale_boot_text_and_rejoin_are_not_commands_or_success(self):
        stale = (f'COMMISSION_TEST_NODE old-input\r\n'
                 f'Authenticated rejoin device={DEVICE} session=2\r\n'
                 'HIL_ERROR unknown_command\r\nHIL_ERROR unknown_command\r\n').encode()
        result = self.run_flow(hub_lines=[stale, HUB_READY, DURABILITY, OWNER], success=False)
        self.assertIsInstance(result['error'], TimeoutError); self.assert_one(result)
        self.assertNotIn('ENROLLMENT_AUTHENTICATED', result['evidence'])
        self.assertIn('RX phase=PRE_TX hub: HIL_ERROR unknown_command', result['evidence'])

    def test_timeout_never_duplicates_send(self):
        result = self.run_flow(success=False)
        self.assertIsInstance(result['error'], TimeoutError); self.assert_one(result)

    def test_mismatched_epoch_withholds_command(self):
        result = self.run_flow(hub_lines=[HUB_READY, DURABILITY.replace(b'epoch=1', b'epoch=2'), OWNER])
        self.assertIsInstance(result['error'], TimeoutError)
        self.assertFalse(result['hub'].written)

    def test_unknown_after_tx_fails_without_retry(self):
        result = self.run_flow(reply=b'HIL_ERROR unknown_command\r\n')
        self.assertIsInstance(result['error'], ValueError); self.assert_one(result)
        self.assertIn('RX phase=POST_TX hub: HIL_ERROR unknown_command', result['evidence'])

    def test_short_write_fails_without_resend(self):
        result = self.run_flow(short_write=True)
        self.assertIsInstance(result['error'], ValueError)
        self.assertEqual(len([w for w in result['writes'] if w[0]=='hub']), 1)

    def test_panic_watchdog_and_storage_failure_withhold_command(self):
        for fault in [b'Guru Meditation panic\n', b'rst:0x8 (TG1WDT_SYS_RESET)\n',
                      b'Durability owner unavailable state=4 error=5; admission closed\n']:
            result = self.run_flow(hub_lines=[fault, HUB_READY, DURABILITY, OWNER])
            self.assertIsInstance(result['error'], ValueError)
            self.assertFalse(result['hub'].written)


if __name__ == '__main__': unittest.main()
