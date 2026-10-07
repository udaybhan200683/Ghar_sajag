"""Offline lost-ACK operator flow; every serial object is simulated."""
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/factory'))
import lost_ack
import bench
import serial_command

PHYSICAL = 'c3-146393c5d158'
KEY = f'p{len(PHYSICAL)}:{PHYSICAL}n5:node1s1527q1'
EXTRA = f'p{len(PHYSICAL)}:{PHYSICAL}n5:node1s1527q2'
OWNER = 'NodeRuntime owner started session=1527 channel=6 tx_power_qdbm=44\nPIR ready on GPIO4\n'
READY = 'HIL_JOURNAL_RECOVERED records=5\nHIL_READY role=hub protocol=1 version=test\n'
STATE = 'HIL_STATE role=c3 session=1527 retained=0 in_flight=0 sensing_live=4462 runtime_live=4462 pending_inject=0 heap=197812 min_heap=189548 ota_slot=ota_0\nHIL_OK command=GET_STATE\n'


class Simulation:
    def __init__(self, root, mode='pass'):
        self.root = root; self.mode = mode; self.now = 0
        self.opened = []; self.writes = {'node': [], 'hub': []}; self.closed = []
        self.cued = self.first = self.retry = False
        self.queues = {'node': [OWNER.encode()], 'hub': [READY.encode()]}
        self.output = io.StringIO()
        simulation = self
        class Screen:
            def write(self, text):
                simulation.output.write(text)
                if lost_ack.CUE in text: simulation.cued = True
                return len(text)
            def flush(self): pass
        self.screen = Screen()

    def clock(self): return self.now

    def open(self, port, max_wait):
        self.opened.append(port)
        simulation = self
        class Serial:
            wire = b''
            def __enter__(self): return self
            def __exit__(self, *args): simulation.closed.append(port)
            def write(self, data):
                self.wire += data
                if b'\n' in self.wire:
                    command, self.wire = self.wire.split(b'\n', 1)
                    command = command.decode(); simulation.writes[port].append(command)
                    if command == 'GET_STATE': simulation.queues[port].append(STATE.encode())
                    if command == lost_ack.ARM and simulation.mode != 'never_arms':
                        text = 'HIL_OK command=' + lost_ack.ARM + '\n'
                        if simulation.mode == 'garbled': text = '\ufffd' + text
                        simulation.queues[port].append(text.encode())
                return len(data)
            def flush(self): pass
            def read(self, count):
                simulation.now += .05
                if simulation.cued and simulation.mode == 'disconnect': raise OSError('simulated transport lost')
                if simulation.cued and simulation.mode != 'no_pir' and not simulation.first and port == 'node':
                    simulation.first = True
                    simulation.queues['node'].append(b'PIR -> NodeRuntime session=1527 seq=1\nNodeMessage sent session=1527 seq=1 bytes=80\n')
                    simulation.queues['hub'].append((f'HIL_EVENT_RESULT event_id={KEY} ack=0 state_changed=1 records=6\n'
                                                     f'HIL_LOST_ACK_REBOOT event_id={KEY} durable=YES ack_sent=NO records=6\n').encode())
                elif simulation.first and not simulation.retry and port == 'node':
                    simulation.retry = True
                    seq = 2 if simulation.mode == 'wrong_retry' else 1
                    ack_class = 1 if simulation.mode == 'bad_ack' else 0
                    retired = 0 if simulation.mode == 'not_retired' else 1
                    simulation.queues['node'].append((f'NodeMessage sent session=1527 seq={seq} bytes=80\n'
                                                      f'Application ACK session=1527 seq=1 class={ack_class} retired={retired}\n').encode())
                    hub = '' if simulation.mode == 'no_recovery' else 'HIL_JOURNAL_RECOVERED records=6\nHIL_READY role=hub protocol=1 version=test\n'
                    records = 7 if simulation.mode in ('bad_duplicate', 'extra') else 6
                    changed = 1 if simulation.mode == 'bad_duplicate' else 0
                    if simulation.mode == 'extra':
                        simulation.queues['node'].append(b'PIR -> NodeRuntime session=1527 seq=2\nNodeMessage sent session=1527 seq=2 bytes=80\nApplication ACK session=1527 seq=2 class=0 retired=1\n')
                        hub += f'HIL_EVENT_RESULT event_id={EXTRA} ack=0 state_changed=1 records=7\n'
                    hub += f'HIL_EVENT_RESULT event_id={KEY} ack=0 state_changed={changed} records={records}\n'
                    simulation.queues['hub'].append(hub.encode())
                data = simulation.queues[port].pop(0) if simulation.queues[port] else b''
                if simulation.mode == 'fragmented' and len(data) > 32:
                    simulation.queues[port].insert(0, data[32:])
                    data = data[:32]
                return data
        return Serial()

    def run(self):
        args = SimpleNamespace(node_port='node', hub_port='hub', seconds=10,
                               ready_timeout=2, arm_timeout=1, event_timeout=4, evidence_dir=self.root)
        for role in ('node', 'hub'): (self.root / (role + '.log')).touch()
        with tempfile.TemporaryFile() as status_log:
            args.status_fd = status_log.fileno()
            with contextlib.redirect_stdout(self.screen), patch.object(lost_ack.time, 'sleep'):
                code = lost_ack.worker(args, self.open, clock=self.clock)
            status_log.seek(0)
            status = json.loads(status_log.read().splitlines()[-1])
        return code, status['verdict']


class LostAckTests(unittest.TestCase):
    def simulate(self, mode='pass'):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        simulation = Simulation(Path(directory.name), mode)
        code, verdict = simulation.run()
        return simulation, code, verdict

    def test_complete_pass_single_arm_cue_and_evidence(self):
        sim, code, verdict = self.simulate()
        self.assertEqual(code, 0)
        self.assertEqual(verdict['LOST_ACK_TEST'], 'PASS', verdict)
        self.assertEqual(sim.opened, ['node', 'hub'])
        self.assertEqual(set(sim.closed), {'node', 'hub'})
        self.assertEqual(sim.writes['hub'], [lost_ack.ARM])
        self.assertEqual(sim.writes['node'], ['GET_STATE', 'GET_STATE'])
        self.assertEqual(sim.output.getvalue().count(lost_ack.CUE), 1)
        self.assertIn('\a', sim.output.getvalue())
        self.assertEqual(verdict['event_id'], KEY)
        self.assertEqual([verdict[key] for key in ('records_before', 'records_after_unique', 'records_after_duplicate')], [5, 6, 6])
        self.assertEqual(verdict['node_retirement']['ack_class'], 0)
        self.assertEqual(verdict['node_retirement']['retired'], 1)
        self.assertEqual((verdict['final_retained'], verdict['final_in_flight']), (0, 0))
        self.assertIn('NodeMessage sent', (sim.root / 'node.log').read_text())
        self.assertIn('HIL_LOST_ACK_REBOOT', (sim.root / 'hub.log').read_text())

    def test_hub_never_arms_no_cue(self):
        sim, _, verdict = self.simulate('never_arms')
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        self.assertIn('never confirmed', verdict['REASON'])
        self.assertFalse(sim.cued)
        self.assertEqual(sim.writes['hub'], [lost_ack.ARM])

    def test_no_pir_event(self):
        sim, _, verdict = self.simulate('no_pir')
        self.assertTrue(sim.cued)
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        self.assertIn('No intended PIR', verdict['REASON'])

    def test_partial_lines_and_cross_port_capture_order(self):
        _, _, verdict = self.simulate('fragmented')
        self.assertEqual(verdict['LOST_ACK_TEST'], 'PASS', verdict)
        self.assertTrue(verdict['node_retry_same_event_proven'])

    def test_lost_ack_marker_requires_actual_recovery(self):
        _, _, verdict = self.simulate('no_recovery')
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        self.assertIn('without Hub journal recovery', verdict['REASON'])

    def test_node_retry_must_be_same_eventkey(self):
        _, _, verdict = self.simulate('wrong_retry')
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        self.assertIn('Node retry of selected EventKey', verdict['REASON'])

    def selected_proof(self):
        proof = lost_ack.Proof(); proof.session = 1527; proof.pir_ready = True
        proof.arm_sent = proof.armed = proof.cued = True; proof.records = 5
        proof.feed('hub', f'HIL_EVENT_RESULT event_id={KEY} ack=0 state_changed=1 records=6')
        proof.feed('hub', f'HIL_LOST_ACK_REBOOT event_id={KEY} durable=YES ack_sent=NO records=6')
        proof.feed('hub', 'HIL_JOURNAL_RECOVERED records=6')
        return proof

    def test_duplicate_second_record_fails(self):
        _, _, verdict = self.simulate('bad_duplicate')
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        self.assertIn('Selected duplicate', verdict['REASON'])
        proof = self.selected_proof()
        proof.feed('hub', f'HIL_EVENT_RESULT event_id={KEY} ack=0 state_changed=0 records=7')
        self.assertIn('record count', proof.verdict()['REASON'])

    def test_node_retirement_requires_both_fields(self):
        for mode in ('bad_ack', 'not_retired'):
            with self.subTest(mode=mode):
                _, _, verdict = self.simulate(mode)
                self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
                self.assertIn('class=0 retired=1', verdict['REASON'])

    def test_extra_independent_event_keeps_selected_event(self):
        _, _, verdict = self.simulate('extra')
        self.assertEqual(verdict['LOST_ACK_TEST'], 'PASS', verdict)
        self.assertEqual(verdict['event_id'], KEY)
        self.assertEqual(verdict['records_after_unique'], 6)
        self.assertEqual(verdict['records_after_duplicate'], 7)
        self.assertEqual(verdict['independent_record_growth'], 1)
        self.assertEqual(verdict['selected_duplicate_record_growth'], 0)
        self.assertEqual(verdict['records_after_duplicate_excluding_independent'], 6)
        self.assertEqual(verdict['additional_events'][0]['event_id'], EXTRA)
        self.assertEqual(verdict['additional_node_events'], [dict(session=1527, seq=2)])

    def test_transport_disconnect_preserves_partial_logs(self):
        sim, code, verdict = self.simulate('disconnect')
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        self.assertIn('transport unusable', verdict['REASON'])
        self.assertIn('PIR ready', (sim.root / 'node.log').read_text())
        self.assertIn('HIL_OK command=', (sim.root / 'hub.log').read_text())

    def test_garbled_nonmatching_lines_never_arm_or_pass(self):
        sim, _, verdict = self.simulate('garbled')
        self.assertFalse(sim.cued)
        self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
        proof = self.selected_proof()
        for line in ('garbage HIL_EVENT_RESULT event_id=' + KEY + ' ack=0 state_changed=0 records=6',
                     f'HIL_EVENT_RESULT event_id={KEY} ack=0 state_changed=0 records=6\ufffd',
                     f'\x0bHIL_EVENT_RESULT event_id={KEY} ack=0 state_changed=0 records=6\x0c',
                     'HIL_EVENT_RESULT event_id=broken ack=0 state_changed=0 records=6'):
            proof.feed('hub', line)
        self.assertFalse(proof.duplicate)
        self.assertEqual(proof.verdict()['LOST_ACK_TEST'], 'FAIL')

    def test_parent_wallclock_timeout_and_unique_partial_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'home').mkdir()
            (root / 'serial.py').write_text('''
import time
class SerialException(Exception): pass
class Serial:
    def __init__(self): self.calls=0
    def open(self): pass
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,count):
        self.calls+=1
        if self.calls==1: return b'NodeRuntime owner started session=1527 channel=6 tx_power_qdbm=44\\nPIR ready on GPIO4\\n'
        time.sleep(30)
        return b''
''')
            node = root / 'fake-node'; hub = root / 'fake-hub'; node.touch(); hub.touch()
            env = os.environ.copy(); env['PYTHONPATH'] = str(root); env['HOME'] = str(root / 'home')
            command = [sys.executable, str(ROOT / 'tools/factory/bench.py'), 'lost-ack-test',
                       '--node-port', str(node), '--hub-port', str(hub), '--seconds', '1',
                       '--evidence-dir', str(root / 'evidence')]
            started = time.monotonic()
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
            self.assertLess(time.monotonic() - started, 4)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('LOST_ACK_TEST=FAIL', result.stdout)
            run = next((root / 'evidence').iterdir())
            status = json.loads((run / 'status.json').read_text())
            self.assertEqual(status['LOST_ACK_TEST'], 'FAIL')
            self.assertIn('NodeRuntime owner started', (run / 'node.log').read_text())
            self.assertTrue((run / 'hub.log').exists())
            self.assertTrue((run / 'output.log').exists())
            subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(len(list((root / 'evidence').iterdir())), 2)
            self.assertIn('PIR ready', (run / 'node.log').read_text())

    def test_serial_config_is_115200_8n1_exclusive_no_flow_control(self):
        class Serial:
            def open(self): pass
        fake = SimpleNamespace(Serial=Serial, SerialException=OSError)
        with patch.dict(sys.modules, serial=fake): ser = bench.open_serial('offline-only')
        self.assertEqual((ser.baudrate, ser.bytesize, ser.parity, ser.stopbits), (115200, 8, 'N', 1))
        self.assertFalse(ser.xonxoff or ser.rtscts or ser.dsrdtr or ser.dtr or ser.rts)
        self.assertTrue(ser.exclusive)

    def test_cli_pass_and_blocked_arm_preserve_verdict_and_checkpoints(self):
        for mode in ('pass', 'stall_after_arm'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); (root / 'home').mkdir()
                # Reuse the simulated transcript transport in the real child process.
                (root / 'serial.py').write_text('''
import builtins,time
from pathlib import Path
from tests.test_factory_lost_ack import Simulation
from lost_ack import ARM,CUE
simulation=Simulation(Path('.'))
original_print=builtins.print
def print_with_cue(*args,**kwargs):
    if any(CUE in str(arg) for arg in args): simulation.cued=True
    return original_print(*args,**kwargs)
builtins.print=print_with_cue
class SerialException(Exception): pass
class Serial:
    def open(self):
        self.role=Path(self.port).name.removeprefix('fake-')
        self.transport=simulation.open(self.role,0)
    def close(self): self.transport.__exit__()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def write(self,data): return self.transport.write(data)
    def flush(self): pass
    def read(self,count):
        if MODE=='stall_after_arm' and self.role=='hub' and ARM in simulation.writes['hub']:
            time.sleep(30)
        return self.transport.read(count)
'''.replace('MODE', repr(mode)))
                node = root / 'fake-node'; hub = root / 'fake-hub'; node.touch(); hub.touch()
                env = os.environ.copy(); env['PYTHONPATH'] = os.pathsep.join([str(root), str(ROOT)])
                env['HOME'] = str(root / 'home')
                result = subprocess.run([sys.executable, str(ROOT / 'tools/factory/bench.py'),
                                         'lost-ack-test', '--node-port', str(node), '--hub-port', str(hub),
                                         '--seconds', '2' if mode == 'pass' else '1',
                                         '--evidence-dir', str(root / 'evidence')],
                                        env=env, capture_output=True, text=True, timeout=5)
                run = next((root / 'evidence').iterdir())
                verdict = json.loads((run / 'status.json').read_text())
                if mode == 'pass':
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    self.assertEqual(verdict['LOST_ACK_TEST'], 'PASS')
                    self.assertEqual(verdict['event_id'], KEY)
                    self.assertEqual(verdict['records_after_duplicate'], 6)
                    self.assertEqual(verdict['final_retained'], 0)
                    self.assertIn('LOST_ACK_TEST=PASS', result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
                    self.assertTrue(verdict['hub_arm_sent'])
                    self.assertFalse(verdict['operator_cue_issued'])
                    self.assertIn('Parent wall-clock timeout', verdict['REASON'])
                    self.assertIn('HUB_LOST_ACK_ARM_MAY_REMAIN_ACTIVE=YES', result.stdout)

    def test_both_ports_share_alias_resolved_supervisor_locks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); node = root / 'node'; hub = root / 'hub'
            node.touch(); hub.touch(); alias = root / 'hub-alias'; alias.symlink_to(hub)
            state = root / 'state'; state.mkdir()
            digest = hashlib.sha256(os.fsencode(os.path.realpath(hub))).hexdigest()[:24]
            args = SimpleNamespace(action='lost-ack-test', port=str(node), ports=[str(node), str(alias)],
                                   node_port=str(node), hub_port=str(alias), seconds=1,
                                   ready_timeout=1, arm_timeout=1, event_timeout=1, evidence_dir=root / 'evidence')
            with (state / (digest + '.lock')).open('w+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock.write(json.dumps(dict(worker_pid=123))); lock.flush()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    def forbidden(*a, **kw): raise AssertionError('worker must not launch')
                    code = serial_command.supervise(args, ROOT / 'tools/factory/bench.py',
                                                    state_root=state, process_factory=forbidden)
                self.assertEqual(code, serial_command.EXIT['SERIAL_WORKER_STUCK'])
                run = next((root / 'evidence').iterdir())
                self.assertEqual(json.loads((run / 'status.json').read_text())['LOST_ACK_TEST'], 'FAIL')
            args.ports = [str(hub), str(alias)]
            with self.assertRaisesRegex(ValueError, 'different serial devices'):
                serial_command.supervise(args, ROOT / 'tools/factory/bench.py', state_root=state)

    def test_worker_launch_failure_still_preserves_status_and_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = SimpleNamespace(action='lost-ack-test', port='offline-node', ports=['offline-node', 'offline-hub'],
                                   node_port='offline-node', hub_port='offline-hub', seconds=1,
                                   ready_timeout=1, arm_timeout=1, event_timeout=1, evidence_dir=root / 'evidence')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                def failed(*a, **kw): raise OSError('simulated spawn failure')
                code = serial_command.supervise(args, ROOT / 'tools/factory/bench.py',
                                                state_root=root / 'state', process_factory=failed)
            self.assertNotEqual(code, 0)
            run = next((root / 'evidence').iterdir())
            verdict = json.loads((run / 'status.json').read_text())
            self.assertEqual(verdict['LOST_ACK_TEST'], 'FAIL')
            self.assertIn('spawn failure', verdict['REASON'])
            for name in ('node.log', 'hub.log', 'output.log'):
                self.assertTrue((run / name).exists())

    def test_event_key_decodes_canonical_and_legacy(self):
        self.assertEqual(lost_ack.event_key(KEY), dict(source_id='node1', physical_device_id=PHYSICAL, session=1527, seq=1))
        self.assertEqual(lost_ack.event_key('node1:1527:1')['seq'], 1)
        self.assertIsNone(lost_ack.event_key('p15:broken'))


if __name__ == '__main__': unittest.main()
