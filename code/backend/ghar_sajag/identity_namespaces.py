"""Strict identity shapes accepted by the isolated GS-179 TEST_ONLY profile.

Physical identities retain the firmware MAC-derived form. Accepting that shape
does not authenticate or enroll a device; callers must still resolve the exact
certificate/identity, active Home and epoch, and Node enrollment through the
existing authority and durable transaction guards.
"""
from __future__ import annotations

import re


_TEST_HUB_ID = re.compile(r"^test-hub-[A-Za-z0-9_-]{1,64}$")
_PHYSICAL_HUB_ID = re.compile(r"^hub-[0-9a-f]{12}$")
_TEST_NODE_ID = re.compile(r"^test-c3-[A-Za-z0-9_-]{1,64}$")
_PHYSICAL_NODE_ID = re.compile(r"^c3-[0-9a-f]{12}$")


def is_gs179_test_hub_id(value: object) -> bool:
    """Allow preserved HOST_SIM IDs or a MAC-derived Hub ID in TEST_ONLY."""
    return isinstance(value, str) and bool(
        _TEST_HUB_ID.fullmatch(value) or _PHYSICAL_HUB_ID.fullmatch(value)
    )


def is_gs179_test_node_id(value: object) -> bool:
    """Allow preserved HOST_SIM IDs or a MAC-derived C3 ID in TEST_ONLY."""
    return isinstance(value, str) and bool(
        _TEST_NODE_ID.fullmatch(value) or _PHYSICAL_NODE_ID.fullmatch(value)
    )


def is_physical_hub_id(value: object) -> bool:
    return isinstance(value, str) and _PHYSICAL_HUB_ID.fullmatch(value) is not None


def is_physical_node_id(value: object) -> bool:
    return isinstance(value, str) and _PHYSICAL_NODE_ID.fullmatch(value) is not None
