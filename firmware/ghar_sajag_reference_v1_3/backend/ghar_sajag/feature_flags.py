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
