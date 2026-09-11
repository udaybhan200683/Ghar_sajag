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

"""One-time mechanical instrumentation of C++ implementation units."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "firmware/node/components/sensing/sensing.cpp": ("Node", "N01"),
    "firmware/node/components/radio/node_radio.cpp": ("Radio", "N02"),
    "firmware/node/components/power/power.cpp": ("Node", "N03"),
    "firmware/node/components/lifecycle/lifecycle.cpp": ("Node", "N04"),
    "firmware/node/components/storage/node_store.cpp": ("Storage", "N05"),
    "firmware/node/runtime/node_runtime.cpp": ("Node", "N00"),
    "firmware/hub/components/ingest/ingest.cpp": ("Hub", "H01"),
    "firmware/hub/components/storage/journal.cpp": ("Storage", "H02"),
    "firmware/hub/components/time/clock.cpp": ("Hub", "H03"),
    "firmware/hub/components/coverage/coverage.cpp": ("Hub", "H04"),
    "firmware/hub/components/rules/routine_service.cpp": ("Rules", "H05"),
    "firmware/hub/components/ui/resident_ui.cpp": ("Hub", "H06"),
    "firmware/hub/components/lifecycle/config_service.cpp": ("Hub", "H07"),
    "firmware/hub/components/cloud/cloud_sync.cpp": ("Hub", "H08"),
    "firmware/hub/runtime/hub_runtime.cpp": ("Hub", "H00"),
    "firmware/common/security/security.cpp": ("Security", "S01"),
    "shared/src/rules.cpp": ("Rules", "S00"),
}

pattern = re.compile(
    r"(^[\w:<>,&*~ \t]+::([A-Za-z_]\w*)\([^;{}]*?\)(?:\s+const)?\s*\{)",
    re.MULTILINE,
)
for relative, (category, module) in MODULES.items():
    path = ROOT / relative
    text = path.read_text()
    if '#include "gs/logging.hpp"' not in text:
        lines = text.splitlines(keepends=True)
        insert_at = next(i for i, line in enumerate(lines) if line.startswith("#include")) + 1
        lines.insert(insert_at, '#include "gs/logging.hpp"\n')
        text = "".join(lines)
    def add(match):
        name = match.group(2)
        marker = f'GS_TRACE(gs::log::Category::{category}, "{module}", "{name}.enter", "-");'
        return match.group(1) + "\n    " + marker
    text = pattern.sub(add, text)
    path.write_text(text)
