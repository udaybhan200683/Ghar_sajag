#!/usr/bin/env python3
# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module S05 Diagnostics facade and sinks
# @requirements AI08, E10, NFR-05, NFR-09
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The atomic sink pointer only makes pointer publication atomic; it does not make sink lifetime or writes
# thread-safe. The host file sink performs synchronous I/O and rotation. Production should enqueue fixed
# records to one writer, reserve error capacity and expose drops; this future writer is not in the current
# source.

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
