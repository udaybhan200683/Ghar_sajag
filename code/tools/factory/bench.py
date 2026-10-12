#!/usr/bin/env python3
"""Explicit development bench tools. Import/build never connects to a board."""
from __future__ import annotations
import argparse
import binascii
import struct
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / 'tools/factory/esp32_init'
TARGETS = {'hub': 'esp32', 'node': 'esp32c3'}
PARTITIONS = {'hub': [('normal_nvs', 0x9000, 0x6000), ('gs_journal', 0x3e0000, 0x20000)],
              'node': [('normal_nvs', 0x9000, 0x6000)]}

def run(args):
    subprocess.run([str(x) for x in args], check=True)

def build(args):
    path = args.build.resolve(); path.mkdir(parents=True, exist_ok=True)
    role = args.role
    target = ROOT / f'firmware/{role}/target/{TARGETS[role]}/idf'
    defaults = [target / 'sdkconfig.defaults']
    if role == 'node': defaults.append(target / 'sdkconfig.hil.defaults')
    if args.normal_hub:
        if role != 'hub': raise ValueError('--normal-hub requires hub')
        project = target
        defaults.append(ROOT / 'tools/factory/sdkconfig.size.defaults')
        flags = ['-DGS_HIL_BUILD=OFF', '-DGS_HIL_CONTROL=ON', '-DPROJECT_VER=cfec7d2-r1-fresh-bench']
    else:
        project = FACTORY
        defaults.append(FACTORY / 'sdkconfig.defaults')
        if role == 'node': defaults.append(FACTORY / 'sdkconfig.node.defaults')
        flags = [f'-DGS_FACTORY_ROLE={role}']
    if role == 'node' and not args.normal_hub:
        cached = path / 'sdkconfig'
        if cached.exists() and '# CONFIG_MBEDTLS_HARDWARE_AES is not set' in cached.read_text().splitlines():
            raise ValueError('Cached Node initializer disables accelerated AES; use a new isolated build directory')
    fragment = path / 'role.defaults'
    fragment.write_text(f'CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="{target / "partitions.csv"}"\n')
    defaults.append(fragment)
    os.environ.setdefault('IDF_PY_BUILD_JOBS', '4')
    run(['idf.py', '-C', project, '-B', path, f'-DIDF_TARGET={TARGETS[role]}',
         f'-DSDKCONFIG={path / "sdkconfig"}', '-DSDKCONFIG_DEFAULTS=' + ';'.join(map(str, defaults)), *flags, 'build'])
    binary = path / ('gs_hw_m1_hub.bin' if args.normal_hub else 'gs_dev_fresh_init.bin')
    size = binary.stat().st_size
    if size > 0x1e0000: raise ValueError('App exceeds existing OTA slot; do not flash')
    print(json.dumps({'binary': str(binary), 'bytes': size, 'ota_free': 0x1e0000-size,
                      'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}))

def open_serial(port, max_wait=15):
    import serial
    deadline = time.monotonic() + max_wait
    while True:
        ser = serial.Serial(); ser.port = port; ser.baudrate = 115200
        ser.bytesize = 8; ser.parity = 'N'; ser.stopbits = 1
        ser.xonxoff = False; ser.rtscts = False; ser.dsrdtr = False
        ser.exclusive = True
        ser.timeout = .1; ser.write_timeout = 3; ser.dtr = False; ser.rts = False
        try:
            ser.open(); return ser
        except (OSError, serial.SerialException):
            ser.close()
            if time.monotonic() >= deadline: raise
            time.sleep(.2)


def app_flash(role, port, offset, binary):
    if offset not in (0x20000, 0x200000): raise ValueError('Only a verified active OTA app slot is permitted')
    if not binary.is_file() or binary.stat().st_size > 0x1e0000: raise ValueError('Invalid app/slot fit')
    run([sys.executable, '-m', 'esptool', '--chip', TARGETS[role], '--port', port,
         'write-flash', hex(offset), binary.resolve()])

def active_app_offset(table_bytes, otadata, role):
    # Official IDF partition and OTA decoding. Never instantiate OtatoolTarget:
    # its constructor opens a port. Only its pure _get_otadata_info is used.
    idf = Path(os.environ['IDF_PATH'])
    sys.path.insert(0, str(idf / 'components/partition_table'))
    sys.path.insert(0, str(idf / 'components/app_update'))
    import gen_esp32part
    from otatool import OtatoolTarget, SPI_FLASH_SEC_SIZE
    table = gen_esp32part.PartitionTable.from_binary(table_bytes)
    expected = {'nvs': (0x9000,0x6000), 'otadata': (0xf000,0x2000),
                'ota_0': (0x20000,0x1e0000), 'ota_1': (0x200000,0x1e0000)}
    if role == 'hub': expected['gs_journal']=(0x3e0000,0x20000)
    for name,(offset,size) in expected.items():
        found=[p for p in table if p.name==name]
        if len(found)!=1 or (found[0].offset,found[0].size)!=(offset,size):
            raise ValueError('Physical partition table is outside initializer allowlist')
    decoded = object.__new__(OtatoolTarget)
    decoded.otadata=otadata;decoded.spi_flash_sec_size=SPI_FLASH_SEC_SIZE
    valid=[]
    for bank,item in enumerate(decoded._get_otadata_info()):
        state=struct.unpack_from('<I',otadata,bank*0x1000+24)[0]
        crc=binascii.crc32(struct.pack('<I',item.seq),0xffffffff)&0xffffffff
        # Exact bootloader_common_ota_select_valid criteria, plus reject
        # pending rollback to keep the selected application stable.
        if item.seq != 0xffffffff and state not in (3,4) and item.crc==crc:
            if item.seq==0 or state not in (2,0xffffffff):
                raise ValueError('OTA state is pending/unconfirmed; do not reset this bench yet')
            valid.append(item.seq)
    if not valid:
        if otadata != b'\xff'*0x2000:
            raise ValueError('Non-erased invalid OTA metadata; require explicit read-only diagnosis')
        return 0x20000
    return 0x20000 if (max(valid)-1)%2==0 else 0x200000

def reset(args):
    if not args.confirm_development_disposal:
        raise ValueError('Explicit --confirm-development-disposal required')
    binary = args.build.resolve() / 'gs_dev_fresh_init.bin'
    for app in (binary,args.normal_app):
        if not app.is_file() or app.stat().st_size>0x1e0000 or app.read_bytes()[:1]!=b'\xe9':
            raise ValueError('Both initializer and normal app must already exist and fit')
    evidence = args.evidence.resolve(); evidence.mkdir(parents=True, exist_ok=True)
    evidence.chmod(0o700)
    manifest = {'role': args.role, 'device': args.device, 'archived_development_retained': 28 if args.role=='node' else None,
                'partitions': []}
    # Capture physical NVS BEFORE app flashing/reset. Never overwrite old evidence.
    for name, offset, size in [('partition_table',0x8000,0x1000),('otadata',0xf000,0x2000),*PARTITIONS[args.role]]:
        out = evidence / f'{args.role}_{name}.bin'
        with out.open('xb'): pass
        out.chmod(0o600)
        run([sys.executable, '-m', 'esptool', '--chip', TARGETS[args.role], '--port', args.port,
             'read-flash', hex(offset), hex(size), out])
        if out.stat().st_size != size: raise ValueError('Incomplete forensic dump')
        manifest['partitions'].append({'path': str(out), 'offset': offset, 'size': size,
                                       'sha256': hashlib.sha256(out.read_bytes()).hexdigest()})
    offset=active_app_offset((evidence/f'{args.role}_partition_table.bin').read_bytes(),
                             (evidence/f'{args.role}_otadata.bin').read_bytes(),args.role)
    manifest['active_app_offset']=offset
    with (evidence / 'manifest.json').open('x') as stream: json.dump(manifest, stream, indent=2)
    app_flash(args.role, args.port, offset, binary)
    transcript = []
    with open_serial(args.port) as ser:
        pending = b''; deadline = time.monotonic() + 90; sent = False
        while time.monotonic() < deadline:
            pending += ser.read(4096)
            while b'\n' in pending:
                raw, pending = pending.split(b'\n',1); line = raw.decode(errors='replace').rstrip()
                transcript.append(line); print(line)
                (evidence/'initializer.log').write_text('\n'.join(transcript)+'\n')
                match = re.search(r'FACTORY_READY role=(hub|node) device=(\S+) confirm=(DEV_FRESH_RESET .+)',line)
                if match and not sent:
                    if match[1] != args.role or match[2] != args.device:
                        raise ValueError('Wrong physical device; reset confirmation withheld')
                    ser.write((match[3]+'\n').encode()); ser.flush(); sent=True
                if 'FACTORY_FAILED' in line: raise ValueError('Initializer failed closed; normal image not restored')
                if f'FACTORY_DONE role={args.role}' in line:
                    (evidence/'initializer.log').write_text('\n'.join(transcript)+'\n')
                    app = args.normal_app.resolve()
                    # Close the serial owner before esptool takes the port.
                    ser.close(); app_flash(args.role,args.port,offset,app)
                    return
        raise TimeoutError('Initializer did not complete; no automatic repair or retry')

def command(args):
    from serial_command import supervise
    return supervise(args, Path(__file__))

def command_worker(args):
    from serial_command import worker
    return worker(args, open_serial)

def lost_ack_test(args):
    from serial_command import supervise
    args.port = args.node_port
    args.ports = [args.node_port, args.hub_port]
    return supervise(args, Path(__file__))

def lost_ack_worker(args):
    from lost_ack import worker
    return worker(args, open_serial)

def commission(args):
    # No resets, no forwarding of console input, and no command-level retries.
    if not re.fullmatch(r'c3-[0-9a-f]{12}', args.device):
        raise ValueError('Invalid physical identity')
    args.evidence.mkdir(parents=True, exist_ok=True)
    with (args.evidence/'enrollment.log').open('x') as log, open_serial(args.node_port) as node, open_serial(args.hub_port) as hub:
        pending = {'node': b'', 'hub': b''}
        node_ready = hub_ready = owner_ready = qr_sent = sent = False
        epoch = owner_epoch = None
        public = secret = None
        redactions = []
        deadline = time.monotonic() + getattr(args, 'timeout', 60)

        def evidence(text):
            text = re.sub(r'installer_code=\S+', 'installer_code=REDACTED', text)
            for sensitive in redactions:
                text = text.replace(sensitive, 'REDACTED')
            print(text); log.write(text + '\n'); log.flush()

        def transmit(ser, text):
            # A short/failed write is ambiguous: stop; never resend the command.
            wire = (text + '\n').encode('ascii')
            for start in range(0, len(wire), 24):
                part = wire[start:start+24]
                accepted = ser.write(part)
                if accepted != len(part):
                    evidence(f'TX_SHORT_WRITE offset={start} expected={len(part)} accepted={accepted}')
                    raise ValueError('Incomplete serial write; command not retried')
                ser.flush(); time.sleep(.03)
            evidence('TX_COMPLETE bytes=' + str(len(wire)))

        while time.monotonic() < deadline:
            drained = True
            for label, ser in [('node', node), ('hub', hub)]:
                data = ser.read(4096)
                drained = drained and not data
                pending[label] += data
                if len(pending[label]) > 16384:
                    raise ValueError('Unterminated console output; command withheld')
                while b'\n' in pending[label]:
                    raw, pending[label] = pending[label].split(b'\n', 1)
                    line = raw.decode(errors='replace').rstrip('\r')
                    evidence(f'RX phase={"POST_TX" if sent else "PRE_TX"} {label}: {line}')
                    if re.search(r"Guru Meditation|panic'ed|Stack protection|IllegalInstruction|watchdog|\bwdt\b|WDT_SYS_RESET|Durability owner unavailable|admission closed|journal_(?:fault|rejected)|durable event store unavailable|security bootstrap failed|StorageFault|storage.*(?:fault|failed)|NVS.*(?:error|failed)|HIL_DURABILITY owner=(?!Ready)|FACTORY_FAILED", line, re.I):
                        raise ValueError(f'{label} failed closed; commissioning stopped')
                    if 'rst:' in line and (sent or (label == 'node' and node_ready) or (label == 'hub' and (hub_ready or epoch is not None or owner_ready))):
                        raise ValueError('Board restarted during commissioning; no retry')
                    if label == 'node' and re.search(r'HIL_READY role=(?:c3|node)\b', line):
                        if node_ready:
                            raise ValueError('Node restarted during commissioning; no retry')
                        node_ready = True
                        evidence('TX node: GET_TEST_QR terminator=LF')
                        transmit(node, 'GET_TEST_QR'); qr_sent = True
                    if label == 'hub':
                        if 'HIL_READY role=hub ' in line:
                            if hub_ready:
                                raise ValueError('Hub restarted during commissioning; no retry')
                            hub_ready = True
                        durability = re.search(r'HIL_DURABILITY owner=Ready epoch=(\d+) .*native=1 migration=NONE\b', line)
                        if durability:
                            epoch = int(durability[1])
                        owner = re.search(r'Authenticated Hub owner started enrolled=\d+ storage_epoch=(\d+)', line)
                        if owner:
                            owner_ready = True; owner_epoch = int(owner[1])
                        if sent and ('HIL_ERROR' in line or 'commissioning request rejected' in line):
                            raise ValueError('Hub rejected commissioning input; command not retried')
                        if sent and f'Authenticated rejoin device={args.device} ' in line:
                            evidence('ENROLLMENT_AUTHENTICATED'); return
                    if label == 'node' and qr_sent:
                        qr = re.search(r'HIL_TEST_QR .*device_id=(\S+) public_key=([0-9a-f]+)', line)
                        code = re.search(r'HIL_TEST_CODE .*device_id=(\S+) installer_code=([0-9a-f]+)', line)
                        if qr:
                            if qr[1] != args.device or len(qr[2]) != 130:
                                raise ValueError('Wrong Node identity/public key')
                            public = qr[2]
                        if code:
                            if code[1] != args.device or len(code[2]) != 64:
                                raise ValueError('Wrong Node identity/installer code')
                            secret = code[2]; redactions.append(secret)
            # Read both consoles through an empty iteration before TX. Startup
            # text and partial lines are consumed only as evidence, never input.
            if not sent and drained and not any(pending.values()) and node_ready and hub_ready and owner_ready and epoch and epoch == owner_epoch and public and secret:
                text = f'COMMISSION_TEST_NODE {args.device} {args.device[3:]} {public} {secret} hil-signed-fota test pir'
                evidence('READY_GATE node=YES hub=YES owner=YES native=YES epoch=' + str(epoch))
                evidence(f'TX hub bytes={len(text)+1} terminator=LF command={text}')
                sent = True  # Set before any write; ambiguous failure never retries.
                transmit(hub, text); secret = None
        evidence(f'TIMEOUT node_ready={node_ready} hub_ready={hub_ready} owner_ready={owner_ready} epoch_match={bool(epoch and epoch == owner_epoch)} qr_complete={bool(public and redactions)} commission_tx={sent}')
        raise TimeoutError('Fresh authenticated enrollment not observed; command not retried')

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__); subs=parser.add_subparsers(dest='action',required=True)
    p=subs.add_parser('build');p.add_argument('--role',choices=TARGETS,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--normal-hub',action='store_true');p.set_defaults(func=build)
    p=subs.add_parser('reset');p.add_argument('--role',choices=TARGETS,required=True);p.add_argument('--port',required=True);p.add_argument('--device',required=True)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--normal-app',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--confirm-development-disposal',action='store_true');p.set_defaults(func=reset)
    p=subs.add_parser('command');p.add_argument('--port',required=True);p.add_argument('--seconds',type=int,default=10)
    p.add_argument('--delay-before-send',type=float,default=0)
    p.add_argument('--evidence-dir',type=Path,help='parent directory for a new per-command evidence directory')
    p.add_argument('text',nargs='+');p.set_defaults(func=command)
    p=subs.add_parser('_command_worker',help=argparse.SUPPRESS);p.add_argument('--port',required=True)
    p.add_argument('--seconds',type=int,required=True);p.add_argument('--status-fd',type=int,required=True)
    p.add_argument('--delay-before-send',type=float,default=0)
    p.add_argument('text',nargs='+');p.set_defaults(func=command_worker)
    for action, function in [('lost-ack-test', lost_ack_test), ('_lost_ack_worker', lost_ack_worker)]:
        p=subs.add_parser(action,help=argparse.SUPPRESS if action.startswith('_') else 'Supervised physical lost-ACK test; operator supplies one real PIR motion')
        p.add_argument('--node-port',required=True);p.add_argument('--hub-port',required=True)
        p.add_argument('--seconds',type=int,default=300,help='total wall-clock budget, including startup and operator wait')
        p.add_argument('--ready-timeout',type=float,default=60)
        p.add_argument('--arm-timeout',type=float,default=10)
        p.add_argument('--event-timeout',type=float,default=120)
        p.add_argument('--evidence-dir',type=Path,required=True)
        if action.startswith('_'): p.add_argument('--status-fd',type=int,required=True)
        p.set_defaults(func=function)
    p=subs.add_parser('commission');p.add_argument('--hub-port',required=True);p.add_argument('--node-port',required=True);p.add_argument('--device',required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--timeout',type=float,default=60);p.set_defaults(func=commission)
    args=parser.parse_args();result=args.func(args)
    if isinstance(result, int): return result
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,TimeoutError,OSError,subprocess.CalledProcessError) as error:
        print(f'FAILED: {error}',file=sys.stderr);sys.exit(1)
