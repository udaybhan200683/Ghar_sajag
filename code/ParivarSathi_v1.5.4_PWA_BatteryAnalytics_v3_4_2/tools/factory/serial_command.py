"""Bounded foreground supervisor for factory serial commands and lost-ACK tests.

The child owns the tty and the per-port flock. A kernel D-state child can
survive SIGKILL; the parent never waits indefinitely for it.
"""
from __future__ import annotations
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time

EXIT = {'NORMAL_COMMAND_COMPLETE': 0, 'COMMAND_TIMEOUT': 2,
        'USB_DEVICE_DISAPPEARED': 3, 'SERIAL_OPEN_FAILED': 4,
        'SERIAL_WORKER_STUCK': 5}


def _state_root():
    return Path.home() / '.local/state/ghar-sajag/factory-command'


def _emit(fd, classification, detail='', state=None):
    os.write(fd, (json.dumps({'classification': classification, 'detail': detail,
                              'state': state}) + '\n').encode())


def worker(args, open_serial, clock=time.monotonic, sleep=time.sleep):
    """Runs only in the isolated worker process. Never called by the parent."""
    deadline = clock() + args.seconds
    try:
        ser = open_serial(args.port, max_wait=min(15, max(.2, args.seconds / 3)))
    except Exception as error:
        # This catch also covers pyserial's SerialException without importing it
        # in the parent. The serial open helper may itself hang in close().
        _emit(args.status_fd, 'SERIAL_OPEN_FAILED', str(error))
        return EXIT['SERIAL_OPEN_FAILED']
    try:
        with ser:
            delay = getattr(args, 'delay_before_send', 0)
            if delay:
                delay_until = clock() + delay
                while clock() < delay_until:
                    line = ser.readline().decode(errors='replace').rstrip()
                    if line:
                        print(line, flush=True)
                if clock() >= deadline:
                    _emit(args.status_fd, 'COMMAND_TIMEOUT', 'Deadline reached before command was sent.')
                    return EXIT['COMMAND_TIMEOUT']
            for text in args.text:
                for start in range(0, len(text), 24):
                    accepted = ser.write(text[start:start+24].encode())
                    if accepted != len(text[start:start+24].encode()):
                        raise OSError(errno.EIO, 'short serial write')
                    ser.flush()
                    sleep(.03)
                ser.write(b'\n'); ser.flush()
            received = False
            hil_ok = False
            state = None
            expected = ('HIL_STATE ' if args.text == ['GET_STATE'] else
                        'HIL_TEST_QR ' if args.text == ['GET_TEST_QR'] else None)
            while clock() < deadline:
                line = ser.readline().decode(errors='replace').rstrip()
                if line:
                    print(line, flush=True)
                    if args.text == ['GET_STATE'] and 'HIL_STATE role=c3 ' in line:
                        fields = dict(re.findall(r'\b(retained|in_flight|sensing_live|runtime_live)=(\d+)\b', line))
                        if len(fields) == 4:
                            state = {key: int(value) for key, value in fields.items()}
                    if 'HIL_OK command=GET_STATE' in line:
                        hil_ok = True
                    if expected is None or expected in line:
                        received = True
        require_complete_state = args.text == ['GET_STATE'] and getattr(args, 'delay_before_send', 0) > 0
        result = 'NORMAL_COMMAND_COMPLETE' if received and (not require_complete_state or (state is not None and hil_ok)) else 'COMMAND_TIMEOUT'
        _emit(args.status_fd, result, state=state)
        return EXIT[result]
    except Exception as error:
        # SerialException, ENODEV/EIO and close failures indicate transport
        # loss from this operator command's perspective, never a HIL verdict.
        _emit(args.status_fd, 'USB_DEVICE_DISAPPEARED', str(error))
        return EXIT['USB_DEVICE_DISAPPEARED']


def _stop_without_waiting_forever(proc):
    """Best effort only: SIGKILL cannot reap a process stuck in kernel D-state."""
    if proc.poll() is None:
        try: proc.terminate()
        except ProcessLookupError: pass
        try: proc.wait(timeout=.2)
        except subprocess.TimeoutExpired: pass
    if proc.poll() is None:
        try: proc.kill()
        except ProcessLookupError: pass
        try: proc.wait(timeout=.2)
        except subprocess.TimeoutExpired: pass
    return proc.poll() is None


def supervise(args, script_path, worker_builder=None, process_factory=subprocess.Popen,
              state_root=None, clock=time.monotonic):
    """Return an exit code and always write a per-run status.json + output.log."""
    if args.seconds < 1:
        raise ValueError('--seconds must be at least 1')
    delay = getattr(args, 'delay_before_send', 0)
    if delay < 0 or delay >= args.seconds:
        raise ValueError('--delay-before-send must be nonnegative and less than --seconds')
    lost_ack = getattr(args, 'action', '') == 'lost-ack-test'
    ports = getattr(args, 'ports', [args.port])
    if len(set(os.path.realpath(port) for port in ports)) != len(ports):
        raise ValueError('Node and Hub must use different serial devices')
    if lost_ack:
        import math
        if any(not math.isfinite(value) or value <= 0 for value in
               (args.ready_timeout, args.arm_timeout, args.event_timeout)):
            raise ValueError('Stage timeouts must be finite and positive')
    root = Path(state_root) if state_root else _state_root()
    root.mkdir(parents=True, exist_ok=True)
    evidence_parent = Path(args.evidence_dir) if args.evidence_dir else root
    evidence_parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='lost-ack-' if lost_ack else 'command-', dir=str(evidence_parent)))
    evidence.chmod(0o700)
    log_path = evidence / 'output.log'
    status_path = evidence / 'status.json'
    port = args.port
    started = clock()
    lockfds = []
    if lost_ack:
        for role in ('node', 'hub'):
            with (evidence / f'{role}.log').open('xb'): pass
    proc = None
    classification = None
    detail = ''
    worker_alive = False
    worker_pid = None
    child_status = None
    readfd = None

    def save():
        data = {'classification': classification, 'port': port,
                'elapsed_seconds': round(clock() - started, 3),
                'worker_pid': worker_pid, 'worker_alive': worker_alive,
                'detail': detail, 'output_log': str(log_path),
                'state': (child_status or {}).get('state'),
                'recovery': ('WAIT_FOR_USB_TRANSPORT_RELEASE; SAME_PORT_LOCKED'
                             if worker_alive else 'NONE')}
        if lost_ack:
            from lost_ack import empty_verdict
            verdict = empty_verdict()
            verdict.update((child_status or {}).get('verdict') or {})
            if classification != 'NORMAL_COMMAND_COMPLETE':
                verdict['LOST_ACK_TEST'] = 'FAIL'
                verdict['REASON'] = detail or classification
            data.update(verdict)
            data['ports'] = ports
        temporary = status_path.with_suffix('.json.tmp')
        with temporary.open('x') as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
        os.replace(temporary, status_path)
        print(f'STATUS={classification} port={port} elapsed={data["elapsed_seconds"]} '
              f'worker_pid={worker_pid} worker_alive={worker_alive} evidence={evidence}',
              file=sys.stderr, flush=True)
        if lost_ack:
            print(f'EVENT_ID={data["event_id"]}\n'
                  f'RECORDS_BEFORE={data["records_before"]} RECORDS_AFTER_UNIQUE={data["records_after_unique"]} '
                  f'RECORDS_AFTER_DUPLICATE={data["records_after_duplicate"]}\n'
                  f'INDEPENDENT_RECORD_GROWTH={data["independent_record_growth"]}\n'
                  f'FINAL_NODE_STATE retained={data["final_retained"]} in_flight={data["final_in_flight"]}\n'
                  f'LOST_ACK_TEST={data["LOST_ACK_TEST"]}\nREASON={data["REASON"]}\nEVIDENCE={evidence}', flush=True)
            if data.get('hub_arm_may_remain_active'):
                print('HUB_LOST_ACK_ARM_MAY_REMAIN_ACTIVE=YES; keep PIR area clear.', flush=True)

    try:
        try:
            for device in sorted(ports, key=os.path.realpath):
                digest = hashlib.sha256(os.fsencode(os.path.realpath(device))).hexdigest()[:24]
                lockfd = os.open(root / f'{digest}.lock', os.O_CREAT | os.O_RDWR, 0o600)
                lockfds.append(lockfd)
                fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.lseek(lockfd, 0, os.SEEK_SET)
            try: worker_pid = json.loads(os.read(lockfd, 4096)).get('worker_pid')
            except (ValueError, OSError): pass
            classification = 'SERIAL_WORKER_STUCK'
            worker_alive = True
            detail = 'Another command still owns this port; no serial command sent.'
            with log_path.open('xb'): pass
            save()
            return EXIT[classification]
        readfd, writefd = os.pipe()
        try:
            if worker_builder is None:
                if lost_ack:
                    argv = [sys.executable, str(script_path), '_lost_ack_worker',
                            '--node-port', args.node_port, '--hub-port', args.hub_port,
                            '--seconds', str(args.seconds), '--status-fd', str(writefd),
                            '--evidence-dir', str(evidence),
                            '--ready-timeout', str(args.ready_timeout),
                            '--arm-timeout', str(args.arm_timeout),
                            '--event-timeout', str(args.event_timeout)]
                else:
                    argv = [sys.executable, str(script_path), '_command_worker',
                        '--port', port, '--seconds', str(args.seconds),
                        '--status-fd', str(writefd), '--delay-before-send', str(delay), *args.text]
            else:
                argv = worker_builder(writefd, lockfd)
            proc = process_factory(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pass_fds=(*lockfds, writefd), start_new_session=True,
                                   bufsize=0)
            worker_pid = proc.pid
            for lockfd in lockfds:
                os.ftruncate(lockfd, 0); os.lseek(lockfd, 0, os.SEEK_SET)
                os.write(lockfd, json.dumps({'worker_pid': worker_pid, 'evidence': str(evidence)}).encode())
        finally:
            os.close(writefd)
            # The worker now owns the lock until it exits, including in D-state.
            for lockfd in lockfds: os.close(lockfd)
            lockfds = []
        selector = selectors.DefaultSelector()
        for stream, label in ((proc.stdout, 'out'), (proc.stderr, 'err')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        os.set_blocking(readfd, False)
        selector.register(readfd, selectors.EVENT_READ, 'status')
        deadline = started + args.seconds + 1.0  # process startup / IPC allowance
        status_buffer = b''
        with log_path.open('xb') as evidence_log:
            while True:
                remaining = deadline - clock()
                if remaining <= 0:
                    break
                ready = selector.select(min(.1, remaining))
                for key, _ in ready:
                    try: chunk = os.read(key.fd, 65536)
                    except BlockingIOError: continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == 'out':
                        evidence_log.write(chunk); evidence_log.flush()
                        sys.stdout.write(chunk.decode(errors='replace')); sys.stdout.flush()
                    elif key.data == 'status':
                        status_buffer += chunk
                        while b'\n' in status_buffer:
                            raw, status_buffer = status_buffer.split(b'\n', 1)
                            try: child_status = json.loads(raw)
                            except ValueError: pass
                    else:
                        # Internal worker errors, never a firmware verdict.
                        detail = (detail + chunk.decode(errors='replace'))[-2048:]
                if proc.poll() is not None and not selector.get_map():
                    break
            # Drain bytes already delivered before reporting timeout/disconnect.
            for key in list(selector.get_map().values()):
                for _ in range(64):
                    try: chunk = os.read(key.fd, 65536)
                    except BlockingIOError: break
                    if not chunk: break
                    if key.data == 'out':
                        evidence_log.write(chunk); evidence_log.flush()
                        sys.stdout.write(chunk.decode(errors='replace')); sys.stdout.flush()
                    elif key.data == 'status':
                        status_buffer += chunk
                selector.unregister(key.fileobj)
            if status_buffer:
                for raw in status_buffer.splitlines():
                    try: child_status = json.loads(raw)
                    except ValueError: pass
        selector.close()
        os.close(readfd)
        readfd = None
        parent_expired = clock() >= deadline and proc.poll() is None
        worker_alive = _stop_without_waiting_forever(proc)
        if worker_alive:
            classification = 'SERIAL_WORKER_STUCK'
            detail = ((child_status or {}).get('classification', '') + ' ' + detail).strip()
        elif parent_expired:
            classification = 'COMMAND_TIMEOUT'
            detail = 'Parent wall-clock timeout; ' + (child_status or {}).get('detail', 'worker did not report completion')
        elif child_status and child_status.get('classification') in EXIT:
            classification = child_status['classification']
            detail = child_status.get('detail', '')
        elif any(not os.path.exists(device) for device in ports):
            classification = 'USB_DEVICE_DISAPPEARED'
            detail = 'Port path disappeared before the worker reported completion.'
        else:
            classification = 'COMMAND_TIMEOUT'
            detail = 'Worker exited or was stopped without a completion status.'
        save()
        if lost_ack and (child_status or {}).get('verdict', {}).get('LOST_ACK_TEST') != 'PASS':
            return EXIT[classification] or 2
        return EXIT[classification]
    except OSError as error:
        classification = 'SERIAL_OPEN_FAILED'
        detail = 'Supervisor I/O or worker launch failed: ' + str(error)
        if proc is not None:
            worker_alive = _stop_without_waiting_forever(proc)
            if worker_alive: classification = 'SERIAL_WORKER_STUCK'
        if not log_path.exists():
            with log_path.open('xb'): pass
        save()
        return EXIT[classification]
    finally:
        if readfd is not None: os.close(readfd)
        for lockfd in lockfds: os.close(lockfd)
