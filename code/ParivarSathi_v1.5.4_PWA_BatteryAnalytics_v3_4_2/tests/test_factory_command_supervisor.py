"""Deterministic factory command tests; never open physical tty devices."""
import contextlib
import fcntl
import hashlib
import importlib.util
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

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tools/factory/serial_command.py'
spec=importlib.util.spec_from_file_location('serial_command',MODULE)
cmd=importlib.util.module_from_spec(spec);spec.loader.exec_module(cmd)

class SerialFake:
    def __init__(self, lines=(), failure=None):
        self.lines=list(lines)
        self.failure=failure
        self.writes=[]
        self.closed=False
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def write(self,data):self.writes.append(data);return len(data)
    def flush(self):pass
    def readline(self):
        if self.failure:raise self.failure
        return self.lines.pop(0) if self.lines else b''

class CommandTests(unittest.TestCase):
    def args(self,root,seconds=1):
        return SimpleNamespace(port='/dev/ghar-sajag-node',seconds=seconds,
                               text=['GET_STATE'],evidence_dir=root/'evidence')
    def worker_case(self,root,ser=None,open_error=None,clock=None):
        args=self.args(root)
        fake=ser or SerialFake()
        def open_serial(port,max_wait):
            self.assertEqual(port,args.port)
            self.assertGreater(max_wait,0)
            if open_error:raise open_error
            return fake
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with os.fdopen(os.dup(2),'w') if False else contextlib.nullcontext():
                readfd,writefd=os.pipe()
                try:
                    args.status_fd=writefd
                    result=cmd.worker(args,open_serial,clock=clock or iter([0,0,2]).__next__,sleep=lambda _:None)
                    os.close(writefd)
                    status=json.loads(os.read(readfd,4096))
                finally:
                    os.close(readfd)
        return result,status,output.getvalue(),fake
    def test_normal_completion_and_read_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            code,status,output,ser=self.worker_case(root,SerialFake([b'HIL_STATE retained=0\n']))
            self.assertEqual(status['classification'],'NORMAL_COMMAND_COMPLETE')
            self.assertIn('HIL_STATE retained=0',output)
            self.assertTrue(ser.closed)
            self.assertEqual(ser.writes,[b'GET_STATE',b'\n'])
            code,status,output,ser=self.worker_case(root,SerialFake([b'']))
            self.assertEqual(status['classification'],'COMMAND_TIMEOUT')
            self.assertTrue(ser.closed)
            code,status,output,ser=self.worker_case(root,SerialFake([b'boot warning\n']))
            self.assertEqual(status['classification'],'COMMAND_TIMEOUT')
            self.assertIn('boot warning',output)
    def test_delayed_get_state_keeps_one_open_and_captures_startup(self):
        class Clock:
            now = 0.0
            def __call__(self): return self.now
        class DelayedSerial(SerialFake):
            def readline(self):
                if clock.now < 20:
                    clock.now += .1
                    return b'startup log\n' if clock.now < .2 else b''
                clock.now += .1
                return self.lines.pop(0) if self.lines else b''
            def write(self, data):
                self.written_at.append(clock.now)
                return super().write(data)
        clock=Clock()
        ser=DelayedSerial([b'HIL_STATE role=c3 session=1 retained=0 in_flight=0 sensing_live=42 runtime_live=43\n',
                           b'HIL_OK command=GET_STATE\n'])
        ser.written_at=[]
        args=SimpleNamespace(port='fake-node',seconds=25,delay_before_send=20,
                             text=['GET_STATE'])
        opens=[]
        readfd,writefd=os.pipe()
        try:
            args.status_fd=writefd
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result=cmd.worker(args,lambda port,max_wait: (opens.append(port) or ser),
                                  clock=clock,sleep=lambda seconds:None)
            os.close(writefd)
            status=json.loads(os.read(readfd,4096))
        finally:
            os.close(readfd)
        self.assertEqual(result,0)
        self.assertEqual(opens,['fake-node'])
        self.assertTrue(ser.closed)
        self.assertEqual(ser.writes,[b'GET_STATE',b'\n'])
        self.assertGreaterEqual(min(ser.written_at),20)
        self.assertIn('startup log',output.getvalue())
        self.assertIn('HIL_OK command=GET_STATE',output.getvalue())
        self.assertEqual(status['state'],{'retained':0,'in_flight':0,
                                          'sensing_live':42,'runtime_live':43})
    def test_open_failure_and_disconnect(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            code,status,_,_=self.worker_case(root,open_error=OSError('missing tty'))
            self.assertEqual(status['classification'],'SERIAL_OPEN_FAILED')
            code,status,_,ser=self.worker_case(root,SerialFake(failure=OSError(5,'USB disconnected')))
            self.assertEqual(status['classification'],'USB_DEVICE_DISAPPEARED')
            self.assertTrue(ser.closed)
    def fake_builder(self,source):
        return lambda statusfd,lockfd: [sys.executable,'-u','-c',source.format(statusfd=statusfd)]
    def test_supervised_normal_and_partial_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); args=self.args(root)
            source='import os,sys;print("HIL_STATE retained=0",flush=True);os.write({statusfd},b\'{{"classification":"NORMAL_COMMAND_COMPLETE"}}\\n\')'
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code=cmd.supervise(args,MODULE,self.fake_builder(source),state_root=root/'state')
            self.assertEqual(code,0)
            run=next((root/'evidence').iterdir())
            self.assertIn('HIL_STATE retained=0',(run/'output.log').read_text())
            self.assertEqual(json.loads((run/'status.json').read_text())['classification'],'NORMAL_COMMAND_COMPLETE')
            # A later invocation gets a fresh directory and cannot overwrite evidence.
            source='import os;os.write({statusfd},b\'{{"classification":"COMMAND_TIMEOUT"}}\\n\')'
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code=cmd.supervise(args,MODULE,self.fake_builder(source),state_root=root/'state')
            self.assertEqual(code,cmd.EXIT['COMMAND_TIMEOUT'])
            self.assertEqual(len(list((root/'evidence').iterdir())),2)
            self.assertIn('HIL_STATE retained=0',(run/'output.log').read_text())
    def test_bench_cli_end_to_end_with_fake_pyserial(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'home').mkdir()
            (root/'serial.py').write_text('''
class SerialException(Exception): pass
class Serial:
    def __init__(self): self.calls=0
    def open(self): pass
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def write(self,data): return len(data)
    def flush(self): pass
    def readline(self):
        self.calls+=1
        return b'HIL_STATE retained=0\\n' if self.calls==1 else b''
''')
            port=root/'fake-port';port.touch()
            env=os.environ.copy();env['PYTHONPATH']=str(root);env['HOME']=str(root/'home')
            result=subprocess.run([sys.executable,str(ROOT/'tools/factory/bench.py'),
                                   'command','--port',str(port),'--seconds','1',
                                   '--evidence-dir',str(root/'evidence'),'GET_STATE'],
                                  capture_output=True,text=True,env=env,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('HIL_STATE retained=0',result.stdout)
            run=next((root/'evidence').iterdir())
            self.assertEqual(json.loads((run/'status.json').read_text())['classification'],
                             'NORMAL_COMMAND_COMPLETE')
    def test_supervised_disconnect_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.args(root)
            source='import os;print("partial",flush=True);os.write({statusfd},b\'{{"classification":"USB_DEVICE_DISAPPEARED"}}\\n\')'
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code=cmd.supervise(args,MODULE,self.fake_builder(source),state_root=root/'state')
            self.assertEqual(code,cmd.EXIT['USB_DEVICE_DISAPPEARED'])
            run=next((root/'evidence').iterdir())
            self.assertEqual((run/'output.log').read_text(),'partial\n')
    def test_ignores_sigterm_parent_returns(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.args(root)
            args.port=str(root/'present-tty-placeholder')
            Path(args.port).touch()  # No device is opened; this tests timeout classification.
            source='import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("partial",flush=True);time.sleep(20)'
            start=time.monotonic()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code=cmd.supervise(args,MODULE,lambda statusfd,lockfd:[sys.executable,'-u','-c',source],state_root=root/'state')
            self.assertLess(time.monotonic()-start,3.5)
            self.assertEqual(code,cmd.EXIT['COMMAND_TIMEOUT'])
            run=next((root/'evidence').iterdir())
            self.assertIn('partial',(run/'output.log').read_text())
    def test_d_state_simulation_and_same_port_lock(self):
        class Unkillable:
            pid=424242
            def poll(self):return None
            def terminate(self):pass
            def kill(self):pass
            def wait(self,timeout):raise subprocess.TimeoutExpired('fake',timeout)
        self.assertTrue(cmd._stop_without_waiting_forever(Unkillable()))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.args(root);state=root/'state';state.mkdir()
            digest=hashlib.sha256(os.fsencode(os.path.abspath(args.port))).hexdigest()[:24]
            with (state/f'{digest}.lock').open('w+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                lock.write(json.dumps({'worker_pid':424242}));lock.flush()
                def forbidden(*a,**kw):raise AssertionError('second serial worker launched')
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    code=cmd.supervise(args,MODULE,process_factory=forbidden,state_root=state)
                self.assertEqual(code,cmd.EXIT['SERIAL_WORKER_STUCK'])
                run=next((root/'evidence').iterdir())
                status=json.loads((run/'status.json').read_text())
                self.assertEqual(status['worker_pid'],424242)
                self.assertTrue(status['worker_alive'])
                self.assertIn('SAME_PORT_LOCKED',status['recovery'])
    def test_parent_returns_while_simulated_worker_remains_alive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.args(root);state=root/'state'
            class Unkillable:
                pid=424243
                def __init__(self, lockfd, statusfd):
                    self.lock_copy=os.dup(lockfd)
                    self.status_copy=os.dup(statusfd)
                    out_r,out_w=os.pipe();os.close(out_w)
                    err_r,err_w=os.pipe();os.close(err_w)
                    self.stdout=os.fdopen(out_r,'rb',buffering=0)
                    self.stderr=os.fdopen(err_r,'rb',buffering=0)
                def poll(self):return None
                def terminate(self):pass
                def kill(self):pass
                def wait(self,timeout):raise subprocess.TimeoutExpired('fake',timeout)
                def close(self):
                    self.stdout.close();self.stderr.close()
                    os.close(self.lock_copy);os.close(self.status_copy)
            fake=[]
            def spawn(argv,**kwargs):
                item=Unkillable(*kwargs['pass_fds']);fake.append(item);return item
            started=time.monotonic()
            try:
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    code=cmd.supervise(args,MODULE,process_factory=spawn,state_root=state)
                self.assertLess(time.monotonic()-started,3.0)
                self.assertEqual(code,cmd.EXIT['SERIAL_WORKER_STUCK'])
                run=next((root/'evidence').iterdir())
                status=json.loads((run/'status.json').read_text())
                self.assertEqual(status['worker_pid'],424243)
                self.assertTrue(status['worker_alive'])
                def forbidden(*a,**kw):raise AssertionError('another worker launched')
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    again=cmd.supervise(args,MODULE,process_factory=forbidden,state_root=state)
                self.assertEqual(again,cmd.EXIT['SERIAL_WORKER_STUCK'])
            finally:
                for item in fake:item.close()

if __name__=='__main__':unittest.main()
