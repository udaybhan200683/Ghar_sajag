#!/usr/bin/env python3
"""Installation-only text configuration; never opens a device or serial port."""
import argparse
import json
from pathlib import Path
import re

BEGIN = '# >>> GHAR_SAJAG_USB >>>'
END = '# <<< GHAR_SAJAG_USB <<<'
EXPORTS = ('export GS_HUB_PORT=/dev/ghar-sajag-hub\n'
           'export GS_NODE_PORT=/dev/ghar-sajag-node\n')
RULES = '''# Managed by Ghar Sajag zero-touch installer; one board of each role.
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="ghar-sajag-hub", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", IMPORT{builtin}="usb_id"
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", ENV{ID_USB_INTERFACE_NUM}=="00", SYMLINK+="ghar-sajag-node", GROUP="dialout", MODE="0660"
'''


def managed_block(text, content=None):
    """Remove all previous complete blocks, then prepend exactly one block."""
    if text.count(BEGIN) != text.count(END):
        raise ValueError('Incomplete GHAR_SAJAG_USB block; refusing to alter shell configuration')
    stripped = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?',
                      '', text, flags=re.S)
    if BEGIN in stripped or END in stripped:
        raise ValueError('Malformed nested GHAR_SAJAG_USB block')
    if content is None:
        return stripped
    return f'{BEGIN}\n{content}{END}\n' + stripped


def boot_command(text, value=None):
    """Read/update only [boot] command; preserve other config and comments."""
    lines = text.splitlines(keepends=True)
    section = None
    boot_end = len(lines)
    found_boot = False
    command_line = None
    old = ''
    for index, line in enumerate(lines):
        match = re.match(r'\s*\[([^]]+)\]', line)
        if match:
            if section == 'boot':
                boot_end = index
            section = match[1].lower()
            found_boot |= section == 'boot'
        elif section == 'boot' and re.match(r'\s*command\s*=', line, re.I):
            if command_line is not None:
                raise ValueError('Multiple [boot] commands; refusing ambiguous config')
            command_line = index
            old = line.split('=', 1)[1].strip()
            if len(old) >= 2 and old[0] == old[-1] and old[0] in "\"'":
                old = old[1:-1]
    if value is None:
        return old
    if command_line is not None:
        lines[command_line] = f'command={value}\n' if value else ''
    elif value:
        if found_boot:
            if boot_end and not lines[boot_end-1].endswith('\n'):
                lines[boot_end-1] += '\n'
            lines.insert(boot_end, f'command={value}\n')
        else:
            if lines and not lines[-1].endswith('\n'):
                lines[-1] += '\n'
            lines.extend(['[boot]\n', f'command={value}\n'])
    return ''.join(lines)


def rewrite(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text() if path.exists() else ''
    path.write_text(managed_block(old, content))


def configure(root, home, remove=False):
    profile = root / 'etc/profile.d/ghar-sajag-usb.sh'
    rules = root / 'etc/udev/rules.d/99-ghar-sajag-usb.rules'
    state_path = root / 'etc/ghar-sajag-usb/install-state.json'
    wsl_conf = root / 'etc/wsl.conf'
    # Validate all managed inputs before altering any configuration files.
    current = wsl_conf.read_text() if wsl_conf.exists() else ''
    previous = boot_command(current)
    shell_files = ['.bashrc', '.profile', '.zshenv'] + [name for name in ('.bash_profile', '.bash_login') if (home / name).exists()]
    for name in shell_files:
        path = home / name
        managed_block(path.read_text() if path.exists() else '', None if remove else EXPORTS)
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if not isinstance(state.get('previous_boot_command'), str):
            raise ValueError('Invalid installation metadata')
        if not remove and previous != '/usr/local/sbin/gs-usb-boot':
            raise ValueError('WSL boot command changed after installation; review before reinstall')
    elif not remove and previous == '/usr/local/sbin/gs-usb-boot':
        raise ValueError('Managed boot command without installation metadata')
    for name in shell_files:
        rewrite(home / name, None if remove else EXPORTS)
    fish = home / '.config/fish/conf.d/ghar-sajag-usb.fish'
    if remove:
        for path in (profile, rules, fish):
            path.unlink(missing_ok=True)
        if state_path.exists():
            state = json.loads(state_path.read_text())
            current = wsl_conf.read_text() if wsl_conf.exists() else ''
            if boot_command(current) == '/usr/local/sbin/gs-usb-boot':
                wsl_conf.write_text(boot_command(current, state['previous_boot_command']))
            state_path.unlink()
        return
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(EXPORTS)
    rules.parent.mkdir(parents=True, exist_ok=True)
    rules.write_text(RULES)
    fish.parent.mkdir(parents=True, exist_ok=True)
    fish.write_text('set -gx GS_HUB_PORT /dev/ghar-sajag-hub\n'
                    'set -gx GS_NODE_PORT /dev/ghar-sajag-node\n')
    current = wsl_conf.read_text() if wsl_conf.exists() else ''
    if not state_path.exists():
        previous = boot_command(current)
        if previous == '/usr/local/sbin/gs-usb-boot':
            raise ValueError('Managed boot command without installation metadata')
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({'previous_boot_command': previous}) + '\n')
    elif boot_command(current) != '/usr/local/sbin/gs-usb-boot':
        raise ValueError('WSL boot command changed after installation; review before reinstall')
    wsl_conf.write_text(boot_command(current, '/usr/local/sbin/gs-usb-boot'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    configure(args.root, args.home, args.remove)
