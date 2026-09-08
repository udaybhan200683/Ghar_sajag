#!/usr/bin/env python3
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
