#!/usr/bin/env python3
# Ghar Sajag traceability edition 2.0 | source release 1.5.3
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
        "node.schema.json": {"schema", "node_id", "session_id", "sequence_number", "sensor_type", "event_type", "location", "monotonic_ms", "occurred_at", "time_uncertainty_ms", "battery_mv", "rssi_dbm"},
        "node_ack.schema.json": {"schema", "node_id", "session_id", "sequence_number", "ack_type", "hub_received_at"},
        "cloud.schema.json": {"schema", "home_id", "event_id", "kind", "occurred_at", "hub_received_at"},
        "config.schema.json": {"schema", "home_id", "version", "timezone", "mode", "morning", "activity_rules"},
    }
    for name, expected in required.items():
        value = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
        assert value["type"] == "object"
        assert set(value["required"]) == expected
        assert value["additionalProperties"] is False
    node_schema = json.loads((ROOT / "contracts" / "node.schema.json").read_text(encoding="utf-8"))
    ack_schema = json.loads((ROOT / "contracts" / "node_ack.schema.json").read_text(encoding="utf-8"))
    config_schema = json.loads((ROOT / "contracts" / "config.schema.json").read_text(encoding="utf-8"))
    assert node_schema["properties"]["schema"]["const"] == 2
    assert "power" in node_schema["properties"]
    power = node_schema["properties"]["power"]
    assert power["type"] == "object"
    assert power["additionalProperties"] is False
    for field in ("deep_sleep_ms", "awake_ms", "sensor_active_ms", "radio_tx_ms", "radio_rx_ms", "radio_tx_packets", "radio_retries", "wake_count", "heartbeat_count", "boot_count", "brownout_count"):
        assert field in power["properties"]
    assert "activity_rules" in config_schema["properties"]
    assert "battery_alert_percent" in config_schema["properties"]["activity_rules"]["properties"]

    # Dependency-free golden-payload checks: exact required fields plus enum/range values that are
    # most likely to drift when the ESP32 serializer is added.
    node_example = json.loads((ROOT / "contracts" / "examples" / "node_message_v2.json").read_text(encoding="utf-8"))
    ack_example = json.loads((ROOT / "contracts" / "examples" / "node_ack_v1.json").read_text(encoding="utf-8"))
    assert set(node_schema["required"]).issubset(node_example)
    assert node_example["schema"] == node_schema["properties"]["schema"]["const"]
    assert node_example["sensor_type"] in node_schema["properties"]["sensor_type"]["enum"]
    assert node_example["event_type"] in node_schema["properties"]["event_type"]["enum"]
    assert -127 <= node_example["rssi_dbm"] <= 20
    assert "power" in node_example
    assert set(node_example["power"]).issubset(power["properties"])
    assert set(ack_schema["required"]).issubset(ack_example)
    assert ack_example["ack_type"] in ack_schema["properties"]["ack_type"]["enum"]

    openapi = (ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert "openapi: 3.1.0" in openapi
    assert "/v1/homes/{homeId}/events:" in openapi
    assert "/v1/homes/{homeId}/config:" in openapi
    print("contracts: 4 JSON schemas, node/hub protocol examples, optional power telemetry, battery threshold config and OpenAPI verified")


if __name__ == "__main__":
    main()
