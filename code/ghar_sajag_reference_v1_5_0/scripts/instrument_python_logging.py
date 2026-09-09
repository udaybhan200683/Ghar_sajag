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

"""One-time decorator insertion for hardware-independent backend modules."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "backend" / "ghar_sajag"
MODULES = {
    "identity.py": "B01", "homes.py": "B02", "ingest.py": "B03", "incidents.py": "B04",
    "notifications.py": "B05", "fleet.py": "B06", "queries.py": "B07", "operations.py": "B08",
    "store.py": "B09", "service.py": "B10", "http_api.py": "B11", "model.py": "B12",
}
for filename, module_id in MODULES.items():
    path = ROOT / filename
    source = path.read_text()
    if "from .logging_config import traced" not in source:
        lines = source.splitlines(keepends=True)
        position = 0
        while position < len(lines) and (lines[position].strip() == "" or lines[position].startswith(('"""', "'''", "from __future__"))):
            position += 1
        lines.insert(position, "from .logging_config import traced\n")
        source = "".join(lines)
    source = re.sub(
        r"(?m)^(\s*)(def (?!__)[A-Za-z_]\w*\()",
        lambda m: f'{m.group(1)}@traced("{module_id}")\n{m.group(1)}{m.group(2)}', source
    )
    path.write_text(source)
