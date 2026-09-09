#!/usr/bin/env python3
# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module T01 Simulation/CI
# @requirements E08, E10, V01, AI01, AI03, NFR-08
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The Makefile builds host C++17 and runs Python/JavaScript tests plus simulator fixtures. Tests prove
# their asserted paths, not every SRD criterion. Keep a clean command transcript and attach additional
# scenario tests as requirements are integrated.

"""Dependency-free structural checks for the source-of-truth contracts."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    required = {
        "node.schema.json": {"schema", "source_id", "session_id", "sequence", "kind", "location", "monotonic_ms"},
        "cloud.schema.json": {"schema", "home_id", "event_id", "kind", "occurred_at", "hub_received_at"},
        "config.schema.json": {"schema", "home_id", "version", "timezone", "mode", "morning"},
    }
    for name, expected in required.items():
        value = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert value["type"] == "object"
        assert set(value["required"]) == expected
        assert value["additionalProperties"] is False
    openapi = (ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert "openapi: 3.1.0" in openapi
    assert "/v1/homes/{homeId}/events:" in openapi
    print("contracts: 3 JSON schemas and OpenAPI surface verified")


if __name__ == "__main__":
    main()
