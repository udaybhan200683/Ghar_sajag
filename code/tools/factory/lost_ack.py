"""Physical lost-ACK proof in the factory supervisor's isolated serial worker."""
from collections import Counter
from contextlib import ExitStack
import json
import os
import re
import time

from serial_command import EXIT

ARM = 'REBOOT_AFTER_NEXT_DURABLE_COMMIT'
CUE = ('=' * 60 + '\n'
       '>>> NOW TRIGGER EXACTLY ONE PIR MOTION ON THE NODE <<<\n'
       '>>> THEN MOVE AWAY AND DO NOT TRIGGER ANOTHER MOTION <<<\n' + '=' * 60)


def empty_verdict():
    return dict(LOST_ACK_TEST='FAIL', REASON='Worker did not complete the proof',
                event_id=None, EventKey=None, records_before=None,
                records_after_unique=None, records_after_duplicate=None,
                independent_record_growth=0, additional_events=[],
                node_retirement=None, final_retained=None, final_in_flight=None)


def event_key(text):
    """Decode both EventKey::str encodings; never guess from a garbled suffix."""
    if re.match(r'p\d+:', text):
        match = re.match(r'p(\d+):', text)
        if not match: return None
        start = match.end(); end = start + int(match[1])
        physical = text[start:end]
        match = re.match(r'n(\d+):', text[end:])
        if not match: return None
        start = end + match.end(); end = start + int(match[1])
        source = text[start:end]
        match = re.fullmatch(r's(\d+)q(\d+)', text[end:])
        if not match or not physical or not source: return None
        return dict(source_id=source, physical_device_id=physical,
                    session=int(match[1]), seq=int(match[2]))
    match = re.fullmatch(r'([^:]+):(\d+):(\d+)', text)
    if match:
        return dict(source_id=match[1], physical_device_id='',
                    session=int(match[2]), seq=int(match[3]))
    return None


def clean_line(line):
    line = re.sub(r'\x1b\[[0-9;]*m', '', line).strip(' \r\n')
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in line): return ''
    return re.sub(r'^[IWE] \(\d+\) [A-Za-z0-9_]+: ', '', line)


class Proof:
    """Accept only complete source log records, preserving one selected EventKey."""
    def __init__(self):
        self.result = empty_verdict()
        self.failure = None
        self.session = None
        self.pir_ready = False
        self.node_state_requested = False
        self.initial_state = None
        self.initial_ok = False
        self.hub_ready = False
        self.records = None
        self.arm_sent = False
        self.armed = False
        self.cued = False
        self.unique = {}
        self.admitted = set()
        self.sends = Counter()
        self.post_loss_sends = Counter()
        self.retirements = {}
        self.loss = False
        self.recovered = False
        self.reboot_ready = False
        self.duplicate = False
        self.final_sent = False
        self.final_state = None
        self.final_ok = False
        self.final_waiting = False

    def fail(self, reason):
        if self.failure is None: self.failure = reason

    @property
    def node_ready(self):
        return self.session is not None and self.pir_ready

    @property
    def ready_to_arm(self):
        return (self.node_ready and self.initial_state is not None and self.initial_ok
                and self.hub_ready and self.records is not None and not self.failure)

    def selected_pair(self):
        key = self.result['EventKey']
        return (key['session'], key['seq']) if key else None

    @property
    def retired(self):
        pair = self.selected_pair()
        return pair is not None and self.retirements.get(pair) == (0, 1)

    @property
    def event_proven(self):
        pair = self.selected_pair()
        # The ports have independent buffers: host read order is not event time.
        # Two Node sends prove retransmission; the same-key Hub duplicate after
        # journal recovery proves reception on the recovered Hub.
        return (self.loss and self.recovered and self.reboot_ready and self.duplicate
                and pair in self.admitted and self.sends[pair] >= 2
                and self.retired and not self.failure)

    def feed(self, role, raw):
        line = clean_line(raw)
        if not line: return
        if re.search(r"Guru Meditation|panic'ed|Stack protection|security bootstrap failed|runtime admission disabled|Node recovery .*failed|stopping owner", line):
            self.fail(role.upper() + '_RUNTIME_FAULT: ' + line)
        if role == 'node':
            if self.session is not None and 'rst:' in line:
                self.fail('Node reset during test')
            if line == 'HIL synthetic sensing boundary accepted':
                self.fail('Synthetic PIR event observed; physical proof invalid')
            match = re.fullmatch(r'NodeRuntime owner started session=(\d+) channel=\d+ tx_power_qdbm=-?\d+', line)
            if match:
                if self.session is not None:
                    self.fail('Node restarted during test')
                self.session = int(match[1])
            if line == 'PIR ready on GPIO4': self.pir_ready = True
            match = re.fullmatch(r'PIR -> NodeRuntime session=(\d+) seq=(\d+)', line)
            if match and self.cued: self.admitted.add((int(match[1]), int(match[2])))
            match = re.fullmatch(r'NodeMessage sent session=(\d+) seq=(\d+) bytes=\d+', line)
            if match and self.cued:
                pair = (int(match[1]), int(match[2]))
                self.sends[pair] += 1
                if self.loss: self.post_loss_sends[pair] += 1
            match = re.fullmatch(r'Application ACK session=(\d+) seq=(\d+) class=(\d+) retired=([01])', line)
            if match and self.cued:
                pair = (int(match[1]), int(match[2]))
                value = (int(match[3]), int(match[4]))
                if self.retirements.get(pair) != (0, 1):
                    self.retirements[pair] = value
                if pair == self.selected_pair():
                    value = self.retirements[pair]
                    self.result['node_retirement'] = dict(session=pair[0], seq=pair[1],
                                                         ack_class=value[0], retired=value[1])
            match = re.fullmatch(r'HIL_STATE role=c3 session=(\d+) retained=(\d+) in_flight=([01]) sensing_live=(\d+) runtime_live=(\d+) pending_inject=(\d+) heap=\d+ min_heap=\d+ ota_slot=\S+', line)
            if match and self.node_state_requested:
                state = dict(session=int(match[1]), retained=int(match[2]),
                             in_flight=int(match[3]), sensing_live=int(match[4]),
                             runtime_live=int(match[5]), pending_inject=int(match[6]))
                if state['pending_inject']:
                    self.fail('Synthetic PIR injection pending')
                if not state['sensing_live'] or not state['runtime_live']:
                    self.fail('Node liveness not established')
                if self.final_sent:
                    self.final_state = state
                    self.result['final_retained'] = state['retained']
                    self.result['final_in_flight'] = state['in_flight']
                    self.result['final_node_state'] = state
                else:
                    self.initial_state = state
                    if state['session'] != self.session or state['retained'] or state['in_flight']:
                        self.fail('Initial Node state is not empty in the captured startup session')
            if line == 'HIL_OK command=GET_STATE' and self.node_state_requested:
                if self.final_sent:
                    self.final_ok = True
                    self.final_waiting = False
                else: self.initial_ok = True
            return

        match = re.fullmatch(r'HIL_READY role=hub protocol=1 version=\S+', line)
        if match:
            if self.loss: self.reboot_ready = True
            else: self.hub_ready = True
        match = re.fullmatch(r'HIL_JOURNAL_RECOVERED records=(\d+)', line)
        if match:
            records = int(match[1])
            if self.loss:
                if records != self.records:
                    self.fail('Hub recovered record count differs from pre-reboot durable count')
                self.recovered = True
            self.records = records
        if line == 'HIL_OK command=' + ARM and self.arm_sent and not self.armed:
            self.armed = True
        match = re.fullmatch(r'HIL_EVENT_RESULT event_id=(\S+) ack=(\d+) state_changed=([01]) records=(\d+)', line)
        if match:
            identity, ack, changed, records = match[1], int(match[2]), int(match[3]), int(match[4])
            if event_key(identity) is None: return
            before = self.records
            if self.arm_sent and not self.cued:
                self.fail('Event reached Hub before operator cue')
            if identity == self.result['event_id'] and self.loss:
                if not self.recovered:
                    self.fail('Selected duplicate arrived without Hub journal recovery evidence')
                if ack != 0 or changed != 0:
                    self.fail('Selected duplicate was not durable ACK class=0 with state_changed=0')
                expected = self.result['records_after_unique'] + self.result['independent_record_growth']
                if records != before or records != expected:
                    self.fail('Selected duplicate changed journal record count')
                self.result['records_after_duplicate'] = records
                self.result['records_before_duplicate'] = before
                self.result['records_after_duplicate_excluding_independent'] = records - self.result['independent_record_growth']
                self.result['selected_duplicate_record_growth'] = records - before if before is not None else None
                self.duplicate = not self.failure
            elif changed == 1:
                if identity in self.unique:
                    self.fail('Independent event created a second durable record')
                if ack != 0 or before is None or records != before + 1:
                    self.fail('Unique event lacks a one-record durable commit')
                self.unique[identity] = dict(before=before, after=records, cued=self.cued)
                if self.loss:
                    self.result['independent_record_growth'] += records - before
                    self.result['additional_events'].append(dict(event_id=identity, records=records))
            self.records = records
        match = re.fullmatch(r'HIL_LOST_ACK_REBOOT event_id=(\S+) durable=YES ack_sent=NO records=(\d+)', line)
        if match:
            identity, records = match[1], int(match[2])
            key = event_key(identity)
            unique = self.unique.get(identity)
            if self.loss:
                self.fail('More than one lost-ACK reboot marker')
            elif not self.armed or not self.cued or key is None or unique is None or not unique['cued']:
                self.fail('Lost-ACK marker lacks armed, cued, matching unique-event evidence')
            elif key['session'] != self.session or records != unique['after']:
                self.fail('Lost-ACK event does not match Node startup session or durable record count')
            else:
                self.loss = True
                self.result.update(event_id=identity, EventKey=key,
                                   records_before=unique['before'], records_after_unique=records)
                pair = self.selected_pair()
                if pair in self.retirements:
                    value = self.retirements[pair]
                    self.result['node_retirement'] = dict(session=pair[0], seq=pair[1],
                                                         ack_class=value[0], retired=value[1])

    def verdict(self):
        if self.event_proven and self.final_ok and self.final_state and not self.final_state['retained'] and not self.final_state['in_flight']:
            self.result.update(LOST_ACK_TEST='PASS', REASON='All selected-event invariants proven')
        else:
            self.result.update(LOST_ACK_TEST='FAIL', REASON=self.failure or self.missing())
        self.result['additional_node_events'] = [dict(session=s, seq=q) for s, q in sorted(self.admitted)
                                                  if (s, q) != self.selected_pair()]
        self.result.update(hub_arm_sent=self.arm_sent, hub_arm_confirmed=self.armed,
                           operator_cue_issued=self.cued,
                           hub_arm_may_remain_active=self.arm_sent and not self.loss,
                           lost_ack_marker=self.loss, hub_journal_recovered=self.recovered,
                           hub_reboot_hil_ready=self.reboot_ready,
                           same_event_duplicate=self.duplicate,
                           node_retry_same_event_proven=self.duplicate and self.sends[self.selected_pair()] >= 2,
                           node_selected_sends=self.sends[self.selected_pair()],
                           node_sends_captured_after_loss_marker=self.post_loss_sends[self.selected_pair()])
        return self.result

    def missing(self):
        if not self.node_ready: return 'Node startup readiness not captured (owner started and PIR ready required)'
        if not self.initial_state or not self.initial_ok: return 'Initial live, empty Node GET_STATE not confirmed'
        if not self.hub_ready or self.records is None: return 'Hub HIL readiness or journal baseline not captured'
        if not self.armed: return 'Hub never confirmed lost-ACK command armed'
        if not self.loss: return 'No intended PIR event with durable lost-ACK reboot evidence'
        if not self.recovered or not self.reboot_ready: return 'Hub reboot/recovery not proven'
        if self.selected_pair() not in self.admitted: return 'Selected event lacks Node PIR admission evidence'
        if self.sends[self.selected_pair()] < 2: return 'Node retry of selected EventKey not proven'
        if not self.duplicate: return 'Same-event duplicate with unchanged records not proven'
        if not self.retired: return 'Selected Node Application ACK class=0 retired=1 not proven'
        return 'Final Node GET_STATE retained=0 in_flight=0 with HIL_OK not confirmed'


def worker(args, open_serial, clock=time.monotonic):
    proof = Proof()
    started = clock(); deadline = started + args.seconds
    stage_deadline = min(deadline, started + args.ready_timeout)
    role = 'node'
    classification = 'COMMAND_TIMEOUT'
    detail = ''
    last_checkpoint = None

    def publish(final_classification='COMMAND_TIMEOUT', force=False):
        nonlocal last_checkpoint
        verdict = proof.verdict()
        payload = json.dumps(dict(classification=final_classification,
                                  detail='' if final_classification == 'NORMAL_COMMAND_COMPLETE' else verdict['REASON'],
                                  verdict=verdict))
        if force or payload != last_checkpoint:
            os.write(args.status_fd, (payload + '\n').encode())
            last_checkpoint = payload

    publish()
    try:
        with ExitStack() as stack:
            logs = {name: stack.enter_context((args.evidence_dir / (name + '.log')).open('ab'))
                    for name in ('node', 'hub')}
            serials = {'node': stack.enter_context(open_serial(args.node_port, max_wait=0))}
            pending = {'node': b'', 'hub': b''}
            next_final_query = 0

            def send(name, command):
                nonlocal role
                role = name
                wire = (command + '\n').encode('ascii')
                # Existing factory framing: short chunks, one LF, no resend.
                for offset in range(0, len(wire), 24):
                    part = wire[offset:offset + 24]
                    if serials[name].write(part) != len(part):
                        raise OSError('Ambiguous short serial write; command not retried')
                    serials[name].flush()
                    time.sleep(.03)
                print('TX ' + name + ': ' + command, flush=True)

            print('Waiting for captured NodeRuntime owner startup and PIR ready on GPIO4.', flush=True)
            while clock() < deadline and clock() < stage_deadline and not proof.failure:
                drained = True
                for role, ser in list(serials.items()):
                    data = ser.read(4096)
                    drained = drained and not data
                    if data:
                        logs[role].write(data); logs[role].flush()
                        pending[role] += data
                        while b'\n' in pending[role]:
                            raw, pending[role] = pending[role].split(b'\n', 1)
                            proof.feed(role, raw.decode('utf-8', errors='replace').rstrip('\r'))
                        if len(pending[role]) > 65536:
                            raise OSError(role + ' console line framing unusable')
                if proof.failure: break
                publish()
                # Drain startup output and all partial lines before any command/cue.
                if drained and not any(pending.values()):
                    if proof.node_ready and 'hub' not in serials:
                        role = 'hub'
                        serials['hub'] = stack.enter_context(open_serial(args.hub_port, max_wait=0))
                        proof.node_state_requested = True
                        send('node', 'GET_STATE')
                        stage_deadline = min(deadline, clock() + args.ready_timeout)
                        print('Waiting for Hub HIL readiness and captured journal baseline.', flush=True)
                    elif proof.ready_to_arm and not proof.arm_sent:
                        proof.arm_sent = True
                        publish()
                        send('hub', ARM)
                        stage_deadline = min(deadline, clock() + args.arm_timeout)
                        print('Waiting for exact Hub arm confirmation; keep clear of PIR.', flush=True)
                    elif proof.armed and not proof.cued:
                        proof.cued = True
                        stage_deadline = min(deadline, clock() + args.event_timeout)
                        print('\a' + CUE, flush=True)
                    elif proof.event_proven:
                        if proof.final_ok and proof.final_state and not proof.final_state['retained'] and not proof.final_state['in_flight']:
                            classification = 'NORMAL_COMMAND_COMPLETE'
                            break
                        if not proof.final_waiting and clock() >= next_final_query:
                            proof.final_sent = True
                            proof.final_ok = False
                            proof.final_state = None
                            proof.final_waiting = True
                            send('node', 'GET_STATE')
                            next_final_query = clock() + 1
                            print('Selected event retired; confirming final Node queues are empty.', flush=True)
            detail = proof.failure or proof.missing()
    except Exception as error:
        classification = 'USB_DEVICE_DISAPPEARED'
        detail = role + ' transport unusable: ' + str(error)
        proof.fail(detail)
    verdict = proof.verdict()
    if verdict['LOST_ACK_TEST'] == 'PASS':
        classification = 'NORMAL_COMMAND_COMPLETE'; detail = ''
    else:
        detail = verdict['REASON']
    publish(classification, force=True)
    return EXIT[classification]
