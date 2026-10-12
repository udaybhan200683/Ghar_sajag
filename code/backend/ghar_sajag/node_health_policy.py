"""GS-40 build/startup policy. Trusted deployment data, never client input."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config/node_health.json"
MIN_INTERVAL = 15  # Existing lifecycle configuration support.
MAX_INTERVAL = 3600

@dataclass(frozen=True)
class NodeHealthPolicy:
    heartbeat_seconds: int = 300
    @property
    def offline_seconds(self):
        return 3 * self.heartbeat_seconds + 10

@dataclass(frozen=True)
class DeploymentPolicy:
    configured: NodeHealthPolicy
    profiles: dict
    def for_device(self, device_id):
        profile = self.profiles.get(device_id)
        if profile == "configured":
            return self.configured
        if profile == "legacy_60":
            return NodeHealthPolicy(60)
        if profile == "legacy_120":
            # Preserve the actually deployed BAT-C5 lease, not a new formula.
            return Legacy120Policy(120)
        return None  # No profile inference from schema, MAC success or silence.

@dataclass(frozen=True)
class Legacy120Policy(NodeHealthPolicy):
    @property
    def offline_seconds(self):
        return 310

def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate configuration key: " + key)
        result[key] = value
    return result

def validate(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "node_health", "deployment_profiles"}:
        raise ValueError("configuration fields must match schema 1")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported configuration schema")
    health = value["node_health"]
    if not isinstance(health, dict) or set(health) != {"heartbeat_interval_seconds", "piggyback_on_events"}:
        raise ValueError("missing or unknown NodeHealth field")
    interval = health["heartbeat_interval_seconds"]
    if type(interval) is not int or not MIN_INTERVAL <= interval <= MAX_INTERVAL:
        raise ValueError("heartbeat interval must be an integer from 15 to 3600 seconds")
    if health["piggyback_on_events"] is not True:
        raise ValueError("GS-40 requires event piggybacking")
    profiles = value["deployment_profiles"]
    if not isinstance(profiles, dict) or len(profiles) > 10:
        raise ValueError("at most ten trusted Node deployment profiles")
    for identity, profile in profiles.items():
        if not re.fullmatch(r"c3-[0-9a-f]{12}", identity) or not isinstance(profile, str) or profile not in {"configured", "legacy_60", "legacy_120"}:
            raise ValueError("invalid physical Node identity/profile")
    return DeploymentPolicy(NodeHealthPolicy(interval), dict(profiles))

def load(path=DEFAULT_CONFIG):
    # Build/service startup fails closed on missing/corrupt/invalid input.
    return validate(json.loads(Path(path).read_text(), object_pairs_hook=_object))
