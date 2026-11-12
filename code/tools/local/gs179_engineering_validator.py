"""Installed Task Scheduler adapter for the EXISTING GS-179 validator.

Run with isolated Python (-I -S) from the administrator-owned installation.
The Windows/WSL operating system and its administrators are trusted. Project
sources and request data are not executable authority: use pinned snapshots.
"""
from pathlib import Path
import hashlib
import json
import sys
import types

ROOT = Path('/home/udaybhan/projects/Ghar_sajag_r1/code/tools/local')


def load_snapshot(base):
    manifest = json.loads((base / 'installation.json').read_text(encoding='utf-8-sig'))
    required = {'gs179-windows-lan-proxy.ps1', 'gs179_engineering_validator.py',
                'gs179_verified_endpoint.py', 'gs117_hil_authorization.py'}
    if (manifest.get('schema') != 'GS179_ENGINEERING_EXECUTOR_V1' or
            set(manifest.get('sources', {})) != required):
        raise ValueError('protected_manifest_invalid')
    for name, expected in manifest['sources'].items():
        if (Path(name).name != name or len(expected) != 64 or
                any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('snapshot_name_invalid')
        logical = ROOT / name
        if logical.is_symlink() or hashlib.sha256(logical.read_bytes()).hexdigest() != expected:
            raise ValueError('reviewed_project_source_changed')
    snapshots = {}
    for name in ('gs117_hil_authorization', 'gs179_verified_endpoint'):
        file = base / (name + '.py')
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['sources'][file.name]:
            raise ValueError('protected_snapshot_changed')
        snapshots[name] = data
    # Validate all executable bytes before loading either module.
    for name, data in snapshots.items():
        file = base / (name + '.py')
        module = types.ModuleType(name)
        module.__file__ = str(ROOT / file.name)
        module.__name__ = '__main__' if name == 'gs179_verified_endpoint' else name
        sys.modules[name] = module
        # Only the pinned protected bytes execute. Logical paths retain the
        # existing owner's canonical source/data identity and integrity checks.
        exec(compile(data, module.__file__, 'exec'), module.__dict__)


if __name__ == '__main__':
    load_snapshot(Path(__file__).resolve().parent)
