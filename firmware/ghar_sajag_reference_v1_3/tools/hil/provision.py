#!/usr/bin/env python3
"""T02 provisioning-plan generator. Real USB writes require an approved adapter."""
from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path


def build_plan(kit_id: str, hub_id: str, node_ids: list[str]) -> dict:
    if len(node_ids) != 4 or len(set(node_ids)) != 4:
        raise ValueError("P0 kit requires four unique node IDs")
    return {
        "schema": 1,
        "kit_id": kit_id,
        "hub_id": hub_id,
        "node_ids": node_ids,
        "claim_token": secrets.token_urlsafe(24),
        "actions": ["erase_test_credentials", "write_device_identity", "verify_readback", "lock_service_mode", "record_board_profile"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", required=True)
    parser.add_argument("--hub", required=True)
    parser.add_argument("--nodes", nargs=4, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = build_plan(args.kit, args.hub, args.nodes)
    safe_view = {**plan, "claim_token": "<redacted>"}
    print(json.dumps(safe_view, indent=2))
    if args.output:
        args.output.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"Sensitive one-use plan written to {args.output}; do not commit it")


if __name__ == "__main__":
    main()
