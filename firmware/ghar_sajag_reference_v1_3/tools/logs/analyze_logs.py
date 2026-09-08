#!/usr/bin/env python3
"""Validate and summarize bounded Ghar Sajag text logs."""
from collections import Counter
from pathlib import Path
import re
import sys

LINE = re.compile(r"^level=(ERROR|TRACE) category=([A-Z]+) module=([A-Z][0-9]+) event=([^ ]+) detail=(.*)$")

def analyze(path: Path) -> int:
    counters = {key: Counter() for key in ("level", "category", "module", "event")}
    malformed = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = LINE.fullmatch(raw)
        if not match:
            malformed += 1
            continue
        for key, value in zip(counters, match.groups()[:4]):
            counters[key][value] += 1
    print(f"file={path} records={sum(counters['level'].values())} malformed={malformed}")
    for key, values in counters.items():
        print(f"{key}: " + ", ".join(f"{name}={count}" for name, count in sorted(values.items())))
    return 1 if malformed else 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_logs.py LOG.txt")
    raise SystemExit(analyze(Path(sys.argv[1])))
