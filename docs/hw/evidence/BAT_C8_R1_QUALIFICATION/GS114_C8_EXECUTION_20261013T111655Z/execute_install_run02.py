#!/usr/bin/env python3
"""One-shot GS-114 authorized clean install, fail closed on first mismatch."""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

os.umask(0o077)
ROOT = Path(__file__).resolve().parents[4]
MANIFEST = Path(os.environ.get('GS114_INSTALL_MANIFEST', str(ROOT / 'docs/hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/preparation_manifest.json')))
OUT = Path(os.environ.get('GS114_INSTALL_OUT', str(ROOT / 'code/build/gs114_clean_install/install-20261013T')))
EXPECTED = {
    's3': ('ESP32-S3', '7c:4f:ad:b7:2a:20', '16MB', 'usb-1a86_USB_Single_Serial_5CBC401023-if00'),
    'c3': ('ESP32-C3', '14:63:93:c5:d1:58', '4MB', 'usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00'),
}

def stamp():
    return datetime.now(timezone.utc).isoformat()

def run(role, name, args):
    print(f'{stamp()} {role} {name} START', flush=True)
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (OUT / f'{role}_{name}.log').write_text(result.stdout)
    print(f'{stamp()} {role} {name} exit={result.returncode}', flush=True)
    if result.returncode:
        print(result.stdout[-1800:], flush=True)
        raise RuntimeError(f'{role} {name} failed; no further operations attempted')
    return result.stdout

def check(role, board):
    chip, mac, flash, usb_name = EXPECTED[role]
    port = Path(board['stable_port'])
    if port.name != usb_name or not port.is_symlink() or not re.fullmatch(r'ttyACM\d+', port.resolve().name):
        raise RuntimeError(f'{role} USB target changed')
    if subprocess.run(['fuser', '-s', str(port.resolve())],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise RuntimeError(f'{role} serial port is already owned')
    for artifact in board['artifacts']:
        path = Path(artifact['path'])
        if not path.is_file() or path.stat().st_size != artifact['bytes']:
            raise RuntimeError(f'{role} artifact missing or size changed: {path}')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != artifact['sha256']:
            raise RuntimeError(f'{role} artifact hash changed: {path}')
    output = run(role, 'identity_pre_erase', board['planned_commands']['identity'])
    if f'Connected to {chip} ' not in output or f'MAC:                {mac}' not in output or f'Detected flash size: {flash}' not in output:
        raise RuntimeError(f'{role} chip/MAC/flash identity mismatch; no erase')
    security = run(role, 'security_pre_erase', board['planned_commands']['security_read'])
    if 'Secure Boot: Disabled' not in security or 'Flash Encryption: Disabled' not in security:
        raise RuntimeError(f'{role} security state differs; no erase')
    print(f'{stamp()} {role} VERIFIED {chip} mac={mac} flash={flash} artifacts={len(board["artifacts"])}', flush=True)

def main():
    if OUT.exists():
        raise RuntimeError('install evidence directory already exists; refusing to repeat')
    OUT.mkdir(parents=True)
    data = json.loads(MANIFEST.read_text())
    receipt = json.loads(Path(data['receipt_path']).read_text())
    if data['source_fingerprint'] != receipt['source_fingerprint'] or data['source_head'] != receipt['source_head']:
        raise RuntimeError('manifest/build receipt provenance mismatch')
    roles = tuple(os.environ.get('GS114_INSTALL_ROLES', 's3,c3').split(','))
    if roles == ('c3',):
        prior = Path(os.environ.get('GS114_PREVIOUS_INSTALL_OUT', ''))
        verify_log = prior / 's3_verify.log'
        if not prior.is_dir() or not verify_log.is_file() or \
                verify_log.read_text().count('Verification successful (digest matched).') != 5:
            raise RuntimeError('C3-only continuation lacks the five verified S3 writes')
    elif roles != ('s3', 'c3'):
        raise RuntimeError('unsupported install role sequence')
    for role in roles:
        board = data['boards'][role]
        check(role, board)
        run(role, 'erase', board['planned_commands']['erase'])
        run(role, 'write', board['planned_commands']['write'])
        verify = board['planned_commands']['verify'][:]
        write = board['planned_commands']['write']
        flags = write[write.index('write-flash')+1:write.index('0x0')]
        verify[verify.index('verify-flash')+1:verify.index('verify-flash')+1] = flags
        run(role, 'verify', verify)
        print(f'{stamp()} {role} INSTALL_VERIFIED', flush=True)
    print(f'{stamp()} INSTALL_SEQUENCE_VERIFIED roles={",".join(roles)}', flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'{stamp()} INSTALL_STOP {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
