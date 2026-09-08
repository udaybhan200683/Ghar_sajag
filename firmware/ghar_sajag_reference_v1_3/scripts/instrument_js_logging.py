#!/usr/bin/env python3
"""One-time entry tracing for application modules."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "app/src/features/onboarding/index.mjs": "A01",
    "app/src/features/home/index.mjs": "A02",
    "app/src/features/routines/index.mjs": "A03",
    "app/src/features/incidents/index.mjs": "A04",
    "app/src/platform/index.mjs": "A05",
}
for relative, module_id in MODULES.items():
    path = ROOT / relative
    source = path.read_text()
    import_path = "./logging.mjs" if module_id == "A05" else "../../platform/logging.mjs"
    if "logTrace" not in source:
        source = f'import {{ logTrace, logError }} from "{import_path}";\n' + source
    source = re.sub(
        r"(?m)^(export function ([A-Za-z_]\w*)\([^\n]*\) \{)$",
        lambda m: m.group(1) + f'\n  logTrace("APP", "{module_id}", "{m.group(2)}.enter");', source
    )
    path.write_text(source)
