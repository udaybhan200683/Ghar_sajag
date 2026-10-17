#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
python3 -m unittest discover -s server/tests -v
node --check web/caregiver/call.mjs
python3 - <<'PY'
from xml.etree import ElementTree
from pathlib import Path
for path in Path('android/app/src/main').rglob('*.xml'):
    ElementTree.parse(path)
print('Android XML structure PASS')
PY
