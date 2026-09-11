#!/usr/bin/env python3
# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module T02 Hardware-in-loop tools
# @requirements F03, E09, E10, NFR-05
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The HIL scripts model provisioning plans, installation checks and current summaries. They do not operate
# a board without serial, power and instrument adapters. Record measured evidence and instrument settings
# rather than marking a design target green.

"""T02 current-profile summarizer for later bench CSV captures."""
from __future__ import annotations

import csv
import statistics
from pathlib import Path


def summarize(path: Path) -> dict[str, float]:
    with path.open(newline="", encoding="utf-8") as handle:
        values = [float(row["current_ma"]) for row in csv.DictReader(handle)]
    if not values:
        raise ValueError("empty_capture")
    return {
        "samples": float(len(values)),
        "mean_ma": statistics.fmean(values),
        "peak_ma": max(values),
        "p95_ma": sorted(values)[max(0, int(len(values) * 0.95) - 1)],
    }
