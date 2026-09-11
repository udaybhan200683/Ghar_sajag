# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module S04 Product profile
# @requirements V01, AI01, AI07, E07, E10, NFR-08
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# Product::ai is decided by GS_PRODUCT_AI and exposed through PRODUCT=base or ai in the Makefile. Invalid
# values fail the build. The runtime returns Disabled before calling a provider in the Base profile; the
# shared core remains identical. The older per-feature flags need separate enforcement review.

"""Build/deployment feature gates. P1 capabilities are deny-by-default."""
from __future__ import annotations
import os

DEFAULTS = {
    "morning_routine": True, "call_family": True, "door_history": True,
    "daily_summary": True, "local_offline": True, "temperature_context": False,
    "external_camera": False, "fall_detection": False, "professional_response": False,
}

def enabled(name: str) -> bool:
    if name not in DEFAULTS:
        return False
    raw = os.getenv("GS_FEATURE_" + name.upper(), "")
    return raw.lower() in {"1", "true", "yes", "on"} if raw else DEFAULTS[name]

def snapshot() -> dict[str, bool]:
    return {name: enabled(name) for name in DEFAULTS}
