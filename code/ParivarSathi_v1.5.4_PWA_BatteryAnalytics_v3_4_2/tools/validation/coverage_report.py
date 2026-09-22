#!/usr/bin/env python3
"""Summarize an LCOV tracefile without introducing a Python dependency."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACE = ROOT / "evidence/coverage/coverage.info"
OUT = TRACE.parent
CRITICAL = (
    "firmware/node/fota/fota_receiver.cpp",
    "firmware/node/runtime/node_runtime.cpp",
    "firmware/node/components/radio/node_radio.cpp",
    "firmware/node/components/sensing/sensing.cpp",
    "firmware/common/transport/data_plane_codec.cpp",
    "firmware/hub/runtime/hub_runtime.cpp",
)


def ratio(hit: int, total: int) -> float:
    return round(100.0 * hit / total, 2) if total else 100.0


def main() -> int:
    files: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in TRACE.read_text().splitlines():
        if raw.startswith("SF:"):
            source = Path(raw[3:])
            try:
                name = str(source.relative_to(ROOT))
            except ValueError:
                name = str(source)
            current = {"file": name, "line_hits": {}, "branches": []}
        elif raw.startswith("DA:") and current is not None:
            line, hits, *_ = raw[3:].split(",")
            current["line_hits"][int(line)] = int(hits)  # type: ignore[index]
        elif raw.startswith("BRDA:") and current is not None:
            line, _block, _branch, taken = raw[5:].split(",")
            current["branches"].append((int(line), taken != "-" and int(taken) > 0))  # type: ignore[index]
        elif raw == "end_of_record" and current is not None:
            line_hits = current.pop("line_hits")
            branches = current.pop("branches")
            current.update({
                "lines": len(line_hits),
                "lines_hit": sum(value > 0 for value in line_hits.values()),
                "line_percent": ratio(sum(value > 0 for value in line_hits.values()), len(line_hits)),
                "branches": len(branches),
                "branches_hit": sum(hit for _, hit in branches),
                "branch_percent": ratio(sum(hit for _, hit in branches), len(branches)),
                "uncovered_lines": sorted(line for line, hits in line_hits.items() if hits == 0)[:20],
                "uncovered_branch_lines": sorted({line for line, hit in branches if not hit})[:20],
            })
            files.append(current)
            current = None

    lines = sum(int(row["lines"]) for row in files)
    lines_hit = sum(int(row["lines_hit"]) for row in files)
    branches = sum(int(row["branches"]) for row in files)
    branches_hit = sum(int(row["branches_hit"]) for row in files)
    critical = [row for row in files if row["file"] in CRITICAL]
    report = {
        "schema": 1,
        "status": "PASS",
        "scope": ["firmware", "shared"],
        "line": {"hit": lines_hit, "total": lines, "percent": ratio(lines_hit, lines)},
        "branch": {"hit": branches_hit, "total": branches, "percent": ratio(branches_hit, branches)},
        "files": files,
        "critical_uncovered": [
            {"file": row["file"],
             "uncovered_lines": row["uncovered_lines"],
             "uncovered_branch_lines": row["uncovered_branch_lines"]}
            for row in critical if row["uncovered_lines"] or row["uncovered_branch_lines"]
        ],
        "target_only_exclusions": [
            "ESP-IDF OTA partition write and boot selection adapter",
            "ESP-NOW callback/queue timing and target heap/reset metrics",
            "bootloader reboot, validation, rollback, and physical flash interruption",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    text = [
        "Ghar Sajag host production coverage",
        f"Lines: {lines_hit}/{lines} ({report['line']['percent']:.2f}%)",
        f"Branches: {branches_hit}/{branches} ({report['branch']['percent']:.2f}%)",
        "",
        "Critical production files (uncovered line / branch-line locations):",
    ]
    for row in critical:
        text.append(f"- {row['file']}: lines={row['uncovered_lines']} branches={row['uncovered_branch_lines']}")
    text += ["", "HTML: evidence/coverage/html/index.html", "LCOV: evidence/coverage/coverage.info"]
    (OUT / "summary.txt").write_text("\n".join(text) + "\n")
    print("\n".join(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
