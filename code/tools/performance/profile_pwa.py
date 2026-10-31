#!/usr/bin/env python3
"""Deterministic, socket-free PWA size/profile contract for Phase 3."""
from __future__ import annotations

import argparse
import json
import re
import resource
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.sim.local_lab import HOME, OWNER, Lab, WebLab  # noqa: E402

CAREGIVER_STARTUP_FILES = (
    "tools/sim/pwa/index.html",
    "tools/sim/pwa/boot.mjs",
    "tools/sim/pwa/connected_lite.mjs",
    "tools/sim/pwa/password_visibility.mjs",
    "tools/sim/pwa/runtime_mode.mjs",
    "tools/sim/pwa/caregiver.css",
    "tools/sim/pwa/manifest.webmanifest",
    "tools/sim/pwa/assets/parivar-saathi-icon-192.png",
)
INSTALL_ICON_FILES = ("tools/sim/pwa/assets/parivar-saathi-icon-maskable-512.png",)
BUDGET_PATH = ROOT / "tests/validation/phase3a_performance_budget.json"


def _call(web, method, path, *, query="", body=None):
    raw = json.dumps(body or {}, separators=(",", ":")).encode()
    captured = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "HTTP_HOST": "127.0.0.1:8766",
        "HTTP_X_ACTOR_ID": OWNER,
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": BytesIO(raw),
    }
    encoded = b"".join(web(environ, lambda status, headers: captured.append(status)))
    return int(captured[0][:3]), encoded, json.loads(encoded)


def _rss_bytes():
    # Linux reports KiB and macOS reports bytes. This is diagnostic only.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _static_metrics():
    # Count the real Connected Lite caregiver runtime graph. The local
    # simulator's app.js, engineering validation UI, and service worker are
    # development-only and are not requested by caregiver mode.
    sizes = {path: (ROOT / path).stat().st_size for path in CAREGIVER_STARTUP_FILES}
    runtime_config = {
        "mode": "caregiver",
        "backendOrigin": "https://care.gharsajag.in",
        "caregiverApiConfigured": True,
        "appVersion": "1.5.4-r1",
        "sourceRevision": "0123456789ab",
    }
    runtime_config_bytes = len((
        "window.PARIVAR_SAATHI_RUNTIME=Object.freeze(" +
        json.dumps(runtime_config, separators=(",", ":")) + ");"
    ).encode())
    sizes["caregiver-runtime-config.js"] = runtime_config_bytes
    install_icon_bytes = sum((ROOT / path).stat().st_size for path in INSTALL_ICON_FILES)
    service_worker = (ROOT / "tools/sim/pwa/sw.js").read_text(encoding="utf-8")
    allowlist = re.search(r"const\s+ASSETS\s*=\s*\[(.*?)\]\s*;", service_worker, re.S)
    if not allowlist:
        raise RuntimeError("service-worker static allowlist is missing")
    service_worker_cache_entries = len(re.findall(r"(['\"])[^'\"]*\1", allowlist.group(1)))
    return {
        "profile": "connected-caregiver-startup",
        "files": sizes,
        "html_bytes": sizes["tools/sim/pwa/index.html"],
        "javascript_bytes": sum(size for path, size in sizes.items() if path.endswith((".js", ".mjs"))),
        "css_bytes": sizes["tools/sim/pwa/caregiver.css"],
        # The worker is measured against its existing implementation bound,
        # but is excluded from caregiver startup because only local-simulator
        # mode registers it.
        "service_worker_bytes": (ROOT / "tools/sim/pwa/sw.js").stat().st_size,
        "service_worker_cache_entries": service_worker_cache_entries,
        "manifest_and_icon_bytes": sizes["tools/sim/pwa/manifest.webmanifest"] + sum(
            sizes[path] for path in CAREGIVER_STARTUP_FILES if "/assets/" in path
        ),
        "install_icon_bytes": install_icon_bytes,
        "total_bytes": sum(sizes.values()),
    }


def _seed_notification_history(lab, count=24):
    for index in range(count):
        at = int(lab.state["now"])
        lab.api_call("POST", f"/v1/homes/{HOME}/events", {
            "event_id": f"profile-call-{index:03d}",
            "kind": "CALL_FAMILY",
            "location": "room1",
            "occurred_at": at,
            "hub_received_at": at,
            "payload": {},
        })


def _get_bytes(web, path, query=""):
    status, encoded, payload = _call(web, "GET", path, query=query)
    if status != 200:
        raise RuntimeError(f"{path}?{query} returned {status}")
    return len(encoded), payload


def _flatten(prefix, value, output):
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten(f"{prefix}.{key}" if prefix else key, child, output)
    elif isinstance(value, (int, float)):
        output[prefix] = value


def _check_budgets(result, budget):
    actual = {}
    _flatten("", result, actual)
    failures = []
    for key, maximum in budget["limits"].items():
        value = actual.get(key)
        if value is None:
            failures.append({"metric": key, "error": "metric_missing"})
        elif value > maximum:
            failures.append({"metric": key, "actual": value, "maximum": maximum})
    return failures


def run_profile(check=True):
    started = time.perf_counter()
    rss_before = _rss_bytes()
    static = _static_metrics()
    with tempfile.TemporaryDirectory(prefix="ghar-sajag-profile-") as directory:
        db_path = Path(directory) / "profile.sqlite"
        lab = Lab(db_path)
        web = WebLab(lab, 8766)
        try:
            payloads = {}
            payloads["home_compact_bytes"], home = _get_bytes(web, "/pwa/state", "scope=home")
            payloads["full_state_bytes"], full = _get_bytes(web, "/pwa/state")
            payloads["devices_bytes"], _ = _get_bytes(web, "/pwa/foundation/devices")
            payloads["home_details_bytes"], _ = _get_bytes(web, "/pwa/foundation/home")
            payloads["family_members_bytes"], _ = _get_bytes(web, "/pwa/foundation/members")
            payloads["policy_bytes"], _ = _get_bytes(web, "/pwa/foundation/policy")
            payloads["network_bytes"], _ = _get_bytes(web, "/pwa/foundation/network")
            payloads["notification_preferences_bytes"], _ = _get_bytes(web, "/pwa/foundation/notifications/preferences")
            reports = {}
            for period in ("TODAY", "WEEK", "MONTH"):
                payloads[f"report_{period.lower()}_bytes"], reports[period] = _get_bytes(
                    web, f"/v1/homes/{HOME}/reports", f"period={period}"
                )
            _, catalog_bytes, _ = _call(web, "GET", "/pwa/validation/catalog")
            _seed_notification_history(lab)
            payloads["notification_history_bytes"], history = _get_bytes(web, "/pwa/foundation/notifications/records")
            lab.foundation.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            database_bytes = db_path.stat().st_size
            event_count = lab.foundation.db.execute("SELECT COUNT(*) FROM events WHERE home_id=?", (HOME,)).fetchone()[0]
            notification_count = lab.foundation.db.execute("SELECT COUNT(*) FROM notification_records WHERE home_id=?", (HOME,)).fetchone()[0]
            bounds = {
                "home_recent_events": len(home["events"]),
                "notification_history_records": len(history),
                "report_highlights": max(len(report["highlights"]) for report in reports.values()),
                "report_room_activity": max(len(report["room_activity"]) for report in reports.values()),
                "report_month_buckets": len(reports["MONTH"]["trend"]),
                "service_worker_cache_entries": static["service_worker_cache_entries"],
            }
            result = {
                "schema_version": 1,
                "profile": "P3A_DETERMINISTIC",
                "static": static,
                "payloads": payloads,
                "startup": {
                    "initial_dynamic_bytes": payloads["home_compact_bytes"],
                    "validation_catalog_on_demand_bytes": len(catalog_bytes),
                    "reports_requested_initially": 0,
                    "full_state_requested_initially": 0,
                },
                "bounds": bounds,
                "storage": {
                    "database_bytes": database_bytes,
                    "event_history_count": int(event_count),
                    "notification_count": int(notification_count),
                },
                "diagnostics": {
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "process_max_rss_before_bytes": rss_before,
                    "process_max_rss_after_bytes": _rss_bytes(),
                },
            }
        finally:
            lab.close()
    budget = json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
    failures = _check_budgets(result, budget) if check else []
    result["correctness_gate"] = {
        "status": "PASS" if not failures else "FAIL",
        "budget": str(BUDGET_PATH.relative_to(ROOT)),
        "failures": failures,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-check", action="store_true", help="Report diagnostics without enforcing structural budgets")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    result = run_profile(check=not args.no_check)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["correctness_gate"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
