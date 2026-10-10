#!/usr/bin/env python3
"""Validate GS-40 JSON and compile its typed representation into firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from ghar_sajag.node_health_policy import load

def generate(source, output):
    policy = load(source)
    canonical = json.dumps(json.loads(Path(source).read_text()), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    rows = []
    for identity in sorted(policy.profiles):
        effective = policy.for_device(identity)
        rows.append('    {"%s", %d, %d},' % (identity, effective.heartbeat_seconds, effective.offline_seconds))
    header = '''// Generated from validated GS-40 JSON; do not edit.
#pragma once
#include "gs/node_health_policy.hpp"
#include <array>
#include <optional>
#include <string_view>
namespace gs::deployment {
inline constexpr unsigned schema_version = 1;
inline constexpr NodeHealthPolicy policy{%d, %d};
static_assert(policy.valid(), "invalid embedded NodeHealth policy");
inline constexpr char json[] = R"gs40(%s)gs40";
inline constexpr char sha256[] = "%s";
struct Profile { std::string_view device; unsigned heartbeat_seconds; unsigned offline_seconds; };
inline constexpr std::array<Profile, %d> profiles{{
%s
}};
inline std::optional<Profile> for_device(std::string_view device) {
    for (const auto& profile : profiles) if (profile.device == device) return profile;
    return std::nullopt;
}
} // namespace gs::deployment
''' % (policy.configured.heartbeat_seconds, policy.configured.offline_seconds, canonical, digest, len(rows), "\n".join(rows))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists() or output.read_text() != header:
        output.write_text(header)
    return digest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/node_health.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print("GS40_CONFIG_SHA256=" + generate(args.config, args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, "GS40_CONFIG_INVALID: %s\n" % error)
