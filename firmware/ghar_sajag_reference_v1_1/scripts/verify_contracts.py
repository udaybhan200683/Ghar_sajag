#!/usr/bin/env python3
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
