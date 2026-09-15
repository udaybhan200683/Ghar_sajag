#!/usr/bin/env python3
"""T01 local integration laboratory, release 1.5.4.

@requirements E01-E05,F01,F05-F08,F10,F12,F13,NFR-08,NFR-09.
One WSGI owner drives one C++ child. Pipes substitute for device transport;
JsonApi and the existing backend services handle the API-side business logic.
Never deploy this test-identity/in-memory adapter as a production service.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from io import BytesIO
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import selectors
import subprocess
import sys
import time
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIRequestHandler, WSGIServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from ghar_sajag.http_api import JsonApi
from ghar_sajag.model import HomeMode
from ghar_sajag.battery import BatteryPowerProfile, BatterySample, EnergyCounters
from ghar_sajag.service import GharSajagService
from ghar_sajag.foundation import FoundationService, FoundationError

HOME = "simulation-home"
OWNER = "simulation-owner"
NODES = ["room1", "kitchen", "entry", "pooja", "bathroom", "common"]
KINDS = ["MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY", "HEARTBEAT"]
NODE_CAPABILITIES = {
    "room1": {"MOTION", "OK_PRESSED", "CALL_FAMILY", "HEARTBEAT"},
    "kitchen": {"MOTION", "HEARTBEAT"},
    "entry": {"DOOR_OPEN", "DOOR_CLOSED", "HEARTBEAT"},
    "pooja": {"MOTION", "HEARTBEAT"},
    "bathroom": {"MOTION", "HEARTBEAT"},
    "common": {"MOTION", "HEARTBEAT"},
}
NODE_LOCATIONS = {"room1": "Bedroom / Room 1", "kitchen": "Kitchen", "entry": "Main door", "pooja": "Pooja room",
                  "bathroom": "Bathroom", "common": "Common room"}
NODE_FAULTS = {
    "LOW_BATTERY": ("GS-N001", "Battery low; recharge/replace soon", "DEGRADED", True),
    "BATTERY_DEPLETED": ("GS-N002", "Battery depleted or node power absent", "OFFLINE", False),
    "LINK_LOSS": ("GS-N003", "Node-to-hub communication unavailable", "OFFLINE", False),
    "SENSOR_FAULT": ("GS-N004", "Sensor input is stuck or not responding", "DEGRADED", True),
    "OVER_TEMP": ("GS-N005", "Node over-temperature shutdown", "OFFLINE", False),
    "WATCHDOG": ("GS-N006", "Node firmware watchdog/boot-loop condition", "OFFLINE", False),
}
HUB_FAULTS = {
    "POWER_LOSS": ("GS-H001", "Hub power unavailable", "OFFLINE", False),
    "NODE_RADIO_FAILURE": ("GS-H002", "Hub node-radio interface unavailable", "OFFLINE", False),
    "INTERNET_LOSS": ("GS-H003", "Internet/WAN path unavailable", "DEGRADED", True),
    "OVER_TEMP": ("GS-H004", "Hub over-temperature shutdown", "OFFLINE", False),
    "WATCHDOG": ("GS-H005", "Hub software/watchdog failure", "OFFLINE", False),
}

# Host-lab battery profiles. These are device calibration inputs, not family/person
# behaviour settings. Production values must come from bench measurements on the
# exact board, regulator, sensor and battery configuration.
BATTERY_PROFILES = {
    "hub": BatteryPowerProfile("hub", 5200.0, 10.0, 0.0, 115.0, 0.0, 25.0, 20.0),
    "room1": BatteryPowerProfile("room1", 2700.0, 8.0, 0.20, 18.0, 0.8, 70.0, 45.0),
    "kitchen": BatteryPowerProfile("kitchen", 2700.0, 8.0, 0.22, 18.0, 0.8, 70.0, 45.0),
    "entry": BatteryPowerProfile("entry", 2700.0, 8.0, 0.18, 18.0, 0.4, 72.0, 45.0),
    "pooja": BatteryPowerProfile("pooja", 2700.0, 8.0, 0.20, 18.0, 0.8, 70.0, 45.0),
    "bathroom": BatteryPowerProfile("bathroom", 2700.0, 8.0, 0.23, 18.0, 0.8, 70.0, 45.0),
    "common": BatteryPowerProfile("common", 2700.0, 8.0, 0.21, 18.0, 0.8, 70.0, 45.0),
}
BATTERY_BASE_MV = {"hub": 4020, "room1": 3950, "kitchen": 3920, "entry": 3860, "pooja": 4020, "bathroom": 3960, "common": 3980}
BATTERY_DAILY_AWAKE_MS = {"hub": 86_400_000, "room1": 180_000, "kitchen": 150_000, "entry": 120_000, "pooja": 100_000, "bathroom": 240_000, "common": 190_000}

DEFAULT_HOUSEHOLD_SETTINGS = {
    # Provisioning defaults only. Every field below is versioned per-home configuration and editable
    # under PWA Settings -> Device Schedules; rule code never relies on hidden family-specific constants.
    "quiet_hours_enabled": True,
    "quiet_start_minute": 22 * 60,
    "quiet_end_minute": 6 * 60,
    "door_open_timeout_seconds": 2 * 60 * 60,
    "daytime_inactivity_enabled": True,
    "daytime_start_minute": 8 * 60,
    "daytime_end_minute": 21 * 60,
    "daytime_inactivity_seconds": 3 * 60 * 60,
    "morning_sequence_enabled": True,
    "morning_start_minute": 6 * 60,
    "morning_end_minute": 11 * 60,
    "morning_sequence_window_seconds": 4 * 60 * 60,
    "morning_bedroom_location": "room1",
    "morning_bathroom_location": "bathroom",
    "morning_kitchen_location": "kitchen",
    "night_activity_enabled": True,
    "night_start_minute": 22 * 60,
    "night_end_minute": 6 * 60,
    "night_bathroom_location": "bathroom",
    "night_bathroom_visit_threshold": 4,
    "night_common_location": "common",
    "night_common_visit_threshold": 4,
    "night_visit_merge_seconds": 5 * 60,
    "post_door_inactivity_enabled": True,
    "post_door_inactivity_seconds": 2 * 60 * 60,
    "battery_alert_percent": 20,
    "critical_battery_percent": 5,
    "abnormal_drain_alert_enabled": True,
}

DEFAULT_REGISTRY = [
    {"id":"hub","name":"Hub","kind":"HUB","capability":"HUB","room":"Central hub"},
    {"id":"room1","name":"Bedroom Node","kind":"NODE","capability":"MOTION_BUTTON","room":"Bedroom / Room 1"},
    {"id":"kitchen","name":"Kitchen Node","kind":"NODE","capability":"MOTION","room":"Kitchen"},
    {"id":"entry","name":"Main Door Node","kind":"NODE","capability":"DOOR","room":"Main door"},
    {"id":"pooja","name":"Pooja Room Node","kind":"NODE","capability":"MOTION","room":"Pooja room"},
    {"id":"bathroom","name":"Bathroom Sensor","kind":"NODE","capability":"MOTION","room":"Bathroom"},
    {"id":"common","name":"Common Room Sensor","kind":"NODE","capability":"MOTION","room":"Common room"},
]


class Lab:
    """Owns process lifetime, synthetic clock, fixture data and bounded diagnostic trail."""
    def __init__(self, data_path=":memory:"):
        (ROOT / "logs").mkdir(exist_ok=True)
        self.log = logging.getLogger("simulation_lab")
        if not self.log.handlers:
            h = RotatingFileHandler(ROOT / "logs/e2e_flow.txt", maxBytes=131072, backupCount=2)
            h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self.log.addHandler(h)
            self.log.setLevel(logging.INFO)
            self.log.propagate = False
        self.stderr = open(ROOT / "logs/e2e_child_stderr.txt", "w", encoding="utf-8")
        self.proc = subprocess.Popen([str(ROOT / "build/ghar_sajag_interactive")], cwd=ROOT,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                                     text=True, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.report = {"status": "NOT_RUN", "cases": []}
        self.foundation = FoundationService(data_path, HOME, OWNER, clock=lambda: getattr(self, "state", {}).get("now", 1000))
        self.foundation.seed(DEFAULT_HOUSEHOLD_SETTINGS, DEFAULT_REGISTRY)
        try:
            self.reset()
        except Exception:
            self.close()
            raise

    def close(self):
        self.foundation.close()
        self.selector.close()
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.stderr):
            stream.close()

    def command(self, line):
        # Only server-generated fixed command tokens cross this boundary.
        if self.proc.poll() is not None:
            raise RuntimeError("C++ simulator stopped; restart the laboratory")
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        if not self.selector.select(timeout=5):
            self.proc.kill()
            raise RuntimeError("C++ simulator timed out; restart the laboratory")
        output = self.proc.stdout.readline()
        if not output:
            raise RuntimeError("C++ simulator exited")
        self.state = json.loads(output)
        if "error" in self.state:
            raise ValueError("Simulator refused command; reset after capacity exhaustion")
        self.log.info("category=SIM module=T01 event=command command=%s sim_time=%s", line, self.state["now"])
        return self.state

    def api_call(self, method, path, body=None, actor=OWNER):
        """Run the real WSGI JSON adapter, including JSON encoding and route matching."""
        raw = json.dumps(body or {}).encode()
        captured = []
        chunks = self.api({"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_X_ACTOR_ID": actor,
                           "CONTENT_LENGTH": str(len(raw)), "wsgi.input": BytesIO(raw)},
                          lambda status, headers: captured.append(status))
        result = json.loads(b"".join(chunks))
        if not captured[0].startswith("2"):
            raise ValueError(result.get("error", captured[0]))
        return result

    def reset(self, test_fixture=False):
        self.command("reset")
        if test_fixture:
            self.foundation.reset_test_fixture(DEFAULT_HOUSEHOLD_SETTINGS, DEFAULT_REGISTRY)
        self.service = GharSajagService()
        self.api = JsonApi(self.service, now=lambda: self.state["now"])
        self.api_call("POST", "/v1/homes", {"home_id": HOME, "display_name": "Synthetic demo home",
                      "timezone": "Asia/Kolkata", "residents": [{"resident_id": "demo-resident",
                      "display_name": "Demo resident", "consent_active": True}]})
        self.service.homes.set_caregivers(HOME, OWNER, "primary", "backup", self.state["now"])
        self.heartbeat_id = 0
        self.device_faults = {**{node: None for node in NODES}, "hub": None}
        self.diagnostics = {}
        self.pending_event_contexts = []
        self.pending_derived_events = []
        self.door = {"open": False, "opened_at": None, "open_event_id": None,
                     "quiet_hours": False, "left_open_emitted": False}
        self.household_settings = dict(self.foundation.policy(OWNER)["settings"])
        self.config_version = self._publish_household_settings()
        self.reported_coverage = self.state.get("coverage", "COVERED")
        self.sync()
        # PWA verification/telemetry adapter. This is intentionally outside the
        # deterministic C++ rules core so the v1.5.4 domain logic remains unchanged.
        self.pwa_flags = {
            "morning_negative": False,
            "ok_negative": False,
            "ok_acknowledged": False,
            "night_negative": False,
            "battery_negative": False,
            "door_negative": False,
        }
        self.pwa_audit = []
        self._seed_battery_analytics()

    @staticmethod
    def _minute_in_window(minute, start, end):
        if start == end:
            return True
        return start <= minute < end if start < end else minute >= start or minute < end

    def _config_body(self):
        return {
            "schema": 1,
            "home_id": HOME,
            "timezone": "Asia/Kolkata",
            "mode": "HOME",
            "morning": {
                "enabled": bool(self.household_settings["morning_sequence_enabled"]),
                "start_minute": self.household_settings["morning_start_minute"],
                "end_minute": self.household_settings["morning_end_minute"],
                "grace_minutes": max(0, self.household_settings["morning_sequence_window_seconds"] // 60),
                "qualifying_locations": [
                    self.household_settings["morning_bathroom_location"],
                    self.household_settings["morning_kitchen_location"],
                ],
            },
            "activity_rules": dict(self.household_settings),
        }

    def _publish_household_settings(self):
        r = self.household_settings
        self.command("config {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {}".format(
            int(r["quiet_hours_enabled"]), r["quiet_start_minute"], r["quiet_end_minute"],
            r["door_open_timeout_seconds"], int(r["daytime_inactivity_enabled"]),
            r["daytime_start_minute"], r["daytime_end_minute"], r["daytime_inactivity_seconds"],
            int(r["morning_sequence_enabled"]), r["morning_start_minute"], r["morning_end_minute"],
            r["morning_sequence_window_seconds"], r["morning_bedroom_location"], r["morning_bathroom_location"],
            r["morning_kitchen_location"], int(r["night_activity_enabled"]), r["night_start_minute"],
            r["night_end_minute"], r["night_bathroom_location"], r["night_bathroom_visit_threshold"],
            r["night_common_location"], r["night_common_visit_threshold"], r["night_visit_merge_seconds"],
            int(r["post_door_inactivity_enabled"]), r["post_door_inactivity_seconds"]))
        result = self.api_call("POST", f"/v1/homes/{HOME}/config", self._config_body())
        return int(result["version"])

    def _validate_household_settings(self, values):
        if not isinstance(values, dict):
            raise ValueError("settings object required")
        expected = set(DEFAULT_HOUSEHOLD_SETTINGS)
        if set(values) != expected:
            raise ValueError("settings fields mismatch")
        bool_fields = ("quiet_hours_enabled", "daytime_inactivity_enabled", "morning_sequence_enabled",
                       "night_activity_enabled", "post_door_inactivity_enabled")
        for key in bool_fields:
            if type(values[key]) is not bool:
                raise ValueError(f"{key} must be boolean")
        minute_fields = ("quiet_start_minute", "quiet_end_minute", "daytime_start_minute", "daytime_end_minute",
                         "morning_start_minute", "morning_end_minute", "night_start_minute", "night_end_minute")
        for key in minute_fields:
            if type(values[key]) is not int or not 0 <= values[key] <= 1439:
                raise ValueError(f"{key} must be minute 0..1439")
        if values["morning_start_minute"] >= values["morning_end_minute"] or values["daytime_start_minute"] >= values["daytime_end_minute"]:
            raise ValueError("morning/daytime start must precede end")
        if values["quiet_start_minute"] == values["quiet_end_minute"] or values["night_start_minute"] == values["night_end_minute"]:
            raise ValueError("quiet/night window cannot have zero length")
        bounded = {
            "door_open_timeout_seconds": (30, 86400), "daytime_inactivity_seconds": (300, 86400),
            "morning_sequence_window_seconds": (60, 86400), "night_visit_merge_seconds": (0, 7200),
            "post_door_inactivity_seconds": (300, 86400),
            "night_bathroom_visit_threshold": (0, 50), "night_common_visit_threshold": (0, 50),
            "battery_alert_percent": (1, 50),
            "critical_battery_percent": (1, 49),
        }
        for key, (lo, hi) in bounded.items():
            if type(values[key]) is not int or not lo <= values[key] <= hi:
                raise ValueError(f"{key} must be {lo}..{hi}")
        if values["critical_battery_percent"] >= values["battery_alert_percent"]:
            raise ValueError("critical battery threshold must be below low threshold")
        if type(values["abnormal_drain_alert_enabled"]) is not bool:
            raise ValueError("abnormal_drain_alert_enabled must be boolean")
        location_fields = ("morning_bedroom_location", "morning_bathroom_location", "morning_kitchen_location",
                           "night_bathroom_location", "night_common_location")
        for key in location_fields:
            if values[key] not in NODES:
                raise ValueError(f"{key} must reference a configured location")
    def _update_household_settings(self, values):
        self._save_policy_from_api(OWNER, values)

    def _save_policy_from_api(self, actor, values):
        policy = self.foundation.save_policy(actor, values, self._validate_household_settings)
        self.household_settings = dict(values)
        self.config_version = self._publish_household_settings()
        self.sync()
        return policy

    @staticmethod
    def _counter_add(base, delta):
        values = {}
        for key, value in asdict(base).items():
            values[key] = int(value) + int(getattr(delta, key))
        return EnergyCounters(**values)

    def _daily_energy_delta(self, device_id, intensity=1.0):
        if device_id == "hub":
            awake = 86_400_000
            return EnergyCounters(
                deep_sleep_ms=0, awake_ms=awake, sensor_active_ms=0,
                radio_tx_ms=int(20_000 * intensity), radio_rx_ms=int(40_000 * intensity),
                radio_tx_packets=int(1440 * intensity), radio_retries=int(2 * intensity),
                wake_count=0, heartbeat_count=1440, boot_count=0, brownout_count=0)
        awake = min(86_400_000, int(BATTERY_DAILY_AWAKE_MS[device_id] * intensity))
        return EnergyCounters(
            deep_sleep_ms=86_400_000 - awake,
            awake_ms=awake,
            sensor_active_ms=min(awake, int(awake * 0.45)),
            radio_tx_ms=min(awake, int(8_000 * intensity)),
            radio_rx_ms=min(awake, int(10_000 * intensity)),
            radio_tx_packets=max(1, int(60 * intensity)),
            radio_retries=max(0, int(2 * intensity)),
            wake_count=max(1, int(35 * intensity)),
            heartbeat_count=24, boot_count=0, brownout_count=0)

    def _seed_battery_analytics(self):
        self.service.store.battery_profiles.clear()
        self.service.store.battery_samples.clear()
        self.battery_counters = {}
        variation = (0.92, 1.03, 0.98, 1.08, 0.95, 1.02, 1.00, 1.04)
        for device_id, profile in BATTERY_PROFILES.items():
            self.service.battery.set_profile(profile)
            counters = EnergyCounters(boot_count=1)
            base_mv = BATTERY_BASE_MV[device_id]
            for day, factor in enumerate(variation):
                delta = self._daily_energy_delta(device_id, factor)
                counters = self._counter_add(counters, delta)
                # Earlier samples are slightly higher voltage; latest day lands on base_mv.
                mv = base_mv + (len(variation) - 1 - day) * 4
                sampled_at = int(self.state["now"]) - (len(variation) - 1 - day) * 86_400
                self.service.battery.record(BatterySample(device_id, sampled_at, mv, counters))
            self.battery_counters[device_id] = counters

    def _battery_add_usage(self, device_id, days=1, intensity=1.0, battery_mv=None):
        if device_id not in BATTERY_PROFILES or type(days) is not int or not 1 <= days <= 14:
            raise ValueError("invalid battery usage target/days")
        if not isinstance(intensity, (int, float)) or isinstance(intensity, bool) or not 0.1 <= float(intensity) <= 25.0:
            raise ValueError("invalid battery usage intensity")
        history = self.service.store.battery_samples.get(device_id, [])
        if not history:
            raise ValueError("battery telemetry missing")
        counters = self.battery_counters[device_id]
        at = history[-1].sampled_at
        mv = history[-1].battery_mv if battery_mv is None else int(battery_mv)
        for _ in range(days):
            counters = self._counter_add(counters, self._daily_energy_delta(device_id, float(intensity)))
            at += 86_400
            self.service.battery.record(BatterySample(device_id, at, mv, counters))
        self.battery_counters[device_id] = counters
        return self.service.battery.estimate(device_id).as_dict()

    def _battery_counter_reset(self, device_id, battery_mv=None):
        if device_id not in BATTERY_PROFILES:
            raise ValueError("invalid battery target")
        history = self.service.store.battery_samples.get(device_id, [])
        if not history:
            raise ValueError("battery telemetry missing")
        # Simulate a reboot where cumulative counters restart. The analytics layer
        # must skip the negative interval rather than inventing negative energy.
        counters = EnergyCounters(boot_count=history[-1].counters.boot_count + 1)
        short = self._daily_energy_delta(device_id, 1.0)
        # Keep only two hours of the new boot segment.
        scale = 2.0 / 24.0
        values = {k: int(v * scale) for k, v in asdict(short).items()}
        values["boot_count"] = counters.boot_count
        counters = EnergyCounters(**values)
        at = history[-1].sampled_at + 7200
        mv = history[-1].battery_mv if battery_mv is None else int(battery_mv)
        self.service.battery.record(BatterySample(device_id, at, mv, counters))
        self.battery_counters[device_id] = counters
        return self.service.battery.estimate(device_id).as_dict()

    def _battery_set_low(self, device_id):
        # Three consecutive low-voltage samples make the simulated filtered voltage
        # unambiguously low while retaining the real estimator path.
        return self._battery_add_usage(device_id, days=3, intensity=1.0, battery_mv=3500)

    @staticmethod
    def _format_battery_runtime(estimate, hub=False):
        if estimate.get("charging"):
            return "charging"
        # Do not show a precise runtime promise from an immature usage history.
        # LOW confidence still keeps the internal estimate available for diagnostics,
        # but the family-facing UI remains in a learning state.
        if estimate.get("confidence") == "LOW" and (estimate.get("percent") or 0) > 8:
            return "calculating"
        days = estimate.get("estimated_days")
        if days is None:
            if estimate.get("percent") is not None and estimate.get("percent") <= 8:
                return "recharge now"
            return "calculating"
        if hub and days < 3:
            return f"~{max(1, round(days * 24))} hrs"
        if days < 2:
            return f"~{max(1, round(days * 24))} hrs"
        return f"~{max(1, round(days))} days"

    def _context_for(self, event):
        for index, context in enumerate(self.pending_event_contexts):
            if (context["node"] == event.get("location") and context["kind"] == event.get("kind")
                    and context["occurred_at"] == event.get("occurred_at")):
                return self.pending_event_contexts.pop(index)
        return {}

    def _evaluate_door_open(self):
        if not self.door["open"] or self.door["left_open_emitted"]:
            return
        opened_at = self.door["opened_at"]
        if opened_at is None or self.state["now"] - opened_at < self.household_settings["door_open_timeout_seconds"]:
            return
        self.door["left_open_emitted"] = True
        self.pending_derived_events.append({
            "event_id": f"door-left-open:{self.door['open_event_id'] or opened_at}",
            "kind": "DOOR_LEFT_OPEN",
            "location": "entry",
            "occurred_at": opened_at + self.household_settings["door_open_timeout_seconds"],
            "hub_received_at": opened_at + self.household_settings["door_open_timeout_seconds"],
            "payload": {"opened_at": opened_at, "duration_s": self.state["now"] - opened_at,
                        "source_event_id": self.door["open_event_id"] or "unknown"},
        })

    def sync(self):
        if not self.state.get("hub_online", True) or not self.state["wan"]:
            return
        events = list(self.state["events"])
        signals = list(self.state.get("rule_signals", []))
        unexpected_keys = {item["stable_key"].removeprefix("unexpected-door:") for item in signals if item["kind"] == "UNEXPECTED_DOOR_OPEN"}
        close_signals = [item for item in signals if item["kind"] == "DOOR_CLOSED_AFTER_LONG_OPEN"]
        for event in events:
            wire = dict(event)
            context = self._context_for(event)
            payload = dict(wire.get("payload", {}))
            if event["kind"] == "DOOR_OPEN":
                unexpected = event["event_id"] in unexpected_keys
                payload.update({"quiet_hours": unexpected, "unexpected": unexpected,
                                "left_open_timeout_s": self.household_settings["door_open_timeout_seconds"]})
            elif event["kind"] == "DOOR_CLOSED":
                matching = next((item for item in close_signals if item["stable_key"].startswith("door-left-open:")), None)
                if matching is not None:
                    payload.update({"open_duration_s": matching["duration_s"], "was_left_open": True,
                                    "resolved_left_open": True, "unexpected": False})
                else:
                    for key in ("open_duration_s", "was_left_open", "resolved_left_open", "unexpected"):
                        if key in context:
                            payload[key] = context[key]
            wire["payload"] = payload
            result = self.api_call("POST", f"/v1/homes/{HOME}/events", wire)
            self.log.info("category=SIM module=B03 event=ingest id=%s duplicate=%s", wire["event_id"], result["duplicate"])
            if result.get("commit") != "DURABLE":
                raise RuntimeError("Missing backend model acknowledgement")
            if event["kind"] == "OK_PRESSED" and getattr(self, "pwa_flags", {}).get("ok_negative"):
                self.pwa_flags["ok_negative"] = False
                self.pwa_flags["ok_acknowledged"] = True
            self.command("ack " + wire["event_id"])

        for signal in signals:
            if signal["kind"] not in {"DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY", "MORNING_ROUTINE_COMPLETED",
                                          "UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY",
                                          "POST_DOOR_INACTIVITY"}:
                continue
            kind = signal["kind"]
            locations = {
                "DOOR_LEFT_OPEN": "entry", "POST_DOOR_INACTIVITY": "entry",
                "UNUSUAL_NIGHT_BATHROOM_ACTIVITY": self.household_settings["night_bathroom_location"],
                "UNUSUAL_NIGHT_COMMON_ACTIVITY": self.household_settings["night_common_location"],
                "MORNING_ROUTINE_COMPLETED": "home", "DAYTIME_INACTIVITY": "home",
            }
            event = {
                "event_id": f"rule:{signal['stable_key']}",
                "kind": kind,
                "location": locations.get(kind, "home"),
                "occurred_at": int(signal.get("detected_at", self.state["now"])),
                "hub_received_at": int(signal.get("detected_at", self.state["now"])),
                "payload": {"duration_s": signal.get("duration_s", 0), "reason": signal.get("reason", "")},
            }
            self.api_call("POST", f"/v1/homes/{HOME}/events", event)
        if signals:
            self.command("clear_signals")
        if self.state["missing_pending"]:
            # The legacy host morning-window adapter is retained for regression
            # compatibility. When the household disables the configurable morning
            # sequence, do not publish a contradictory legacy missing-morning event.
            if self.household_settings["morning_sequence_enabled"]:
                self.api_call("POST", f"/v1/homes/{HOME}/events", {"event_id": "missing:sim-morning",
                              "kind": "MISSING_MORNING_ACTIVITY", "occurred_at": self.state["missing_at"],
                              "hub_received_at": self.state["missing_at"], "payload": {"window_id": "sim-morning"}})
            self.command("ack_missing")
        self.heartbeat_id += 1
        self.api_call("POST", f"/v1/homes/{HOME}/events", {"event_id": f"hub:{self.heartbeat_id}",
                      "kind": "HUB_HEARTBEAT", "occurred_at": self.state["now"],
                      "hub_received_at": self.state["now"]})
        current_coverage = self.state.get("coverage", "UNKNOWN")
        if current_coverage != self.reported_coverage:
            reason = "coverage_restored" if current_coverage == "COVERED" else "coverage_lost"
            self.api_call("POST", f"/v1/homes/{HOME}/events", {
                "event_id": f"coverage:{reason}:{self.state['now']}", "kind": "COVERAGE_CHANGED",
                "location": "home", "occurred_at": self.state["now"],
                "hub_received_at": self.state["now"], "payload": {"reason": reason}})
            self.reported_coverage = current_coverage

    def _record_manual_event_context(self, node, kind, body):
        context = {"node": node, "kind": kind, "occurred_at": self.state["now"]}
        if kind == "DOOR_OPEN":
            self.door = {"open": True, "opened_at": self.state["now"], "open_event_id": None,
                         "quiet_hours": False, "left_open_emitted": False}
            pending = [e for e in self.state.get("events", []) if e["kind"] == kind and e["location"] == node and e["occurred_at"] == self.state["now"]]
            if pending:
                self.door["open_event_id"] = pending[-1]["event_id"]
        elif kind == "DOOR_CLOSED":
            if self.door["open"] and self.door["opened_at"] is not None:
                duration = max(0, self.state["now"] - self.door["opened_at"])
                context.update({"open_duration_s": duration, "was_left_open": duration >= self.household_settings["door_open_timeout_seconds"],
                                "resolved_left_open": self.door["left_open_emitted"],
                                "unexpected": False})
            self.door = {"open": False, "opened_at": None, "open_event_id": None,
                         "quiet_hours": False, "left_open_emitted": False}
        if kind in {"DOOR_OPEN", "DOOR_CLOSED"}:
            self.pending_event_contexts.append(context)

    def _fault_info(self, target):
        fault = self.device_faults.get(target)
        table = HUB_FAULTS if target == "hub" else NODE_FAULTS
        return None if fault is None else table[fault]

    def _inject_fault(self, target, fault):
        table = HUB_FAULTS if target == "hub" else NODE_FAULTS
        if target != "hub" and target not in NODES:
            raise ValueError("invalid device")
        if fault not in table:
            raise ValueError("invalid fault")
        self.device_faults[target] = fault
        if target == "hub":
            if fault == "INTERNET_LOSS":
                self.command("wan 0")
            elif table[fault][2] == "OFFLINE":
                self.command("hub 0")
        elif table[fault][2] == "OFFLINE":
            self.command(f"node {NODES.index(target)} 0")
        self.diagnostics[target] = {"code": table[fault][0], "message": table[fault][1],
                                    "result": "Fault injected for simulation"}

    def _clear_fault(self, target):
        if target not in self.device_faults:
            raise ValueError("invalid device")
        previous = self.device_faults[target]
        self.device_faults[target] = None
        if target == "hub" and previous == "INTERNET_LOSS":
            self.command("wan 1")
        self.diagnostics[target] = {"code": "GS-OK000", "message": "Injected fault cleared",
                                    "result": "Use Reboot if the device is still offline"}

    def _troubleshoot(self, target):
        if target not in self.device_faults:
            raise ValueError("invalid device")
        info = self._fault_info(target)
        if info is None:
            if target == "hub" and not self.state["wan"]:
                info = HUB_FAULTS["INTERNET_LOSS"]
            elif target == "hub" and not self.state.get("hub_online", True):
                info = HUB_FAULTS["WATCHDOG"]
            elif target != "hub" and not self.state["nodes"][NODES.index(target)]["online"]:
                info = NODE_FAULTS["LINK_LOSS"]
        if info is None:
            result = {"code": "GS-OK000", "message": "No simulated fault detected", "result": "Device path looks healthy"}
        else:
            result = {"code": info[0], "message": info[1], "result": "Check power, temperature, link and last-seen diagnostics before service"}
        self.diagnostics[target] = result
        return result

    def _reboot(self, target):
        if target not in self.device_faults:
            raise ValueError("invalid device")
        fault = self.device_faults[target]
        recoverable = {"LINK_LOSS", "WATCHDOG"} if target != "hub" else {"NODE_RADIO_FAILURE", "WATCHDOG"}
        if fault in recoverable:
            self.device_faults[target] = None
            self.command("hub 1" if target == "hub" else f"node {NODES.index(target)} 1")
            self.diagnostics[target] = {"code": "GS-OK000", "message": "Reboot successful", "result": "Device is active again"}
            self.sync()
            return
        if fault is None:
            self.command("hub 1" if target == "hub" else f"node {NODES.index(target)} 1")
            self.diagnostics[target] = {"code": "GS-OK000", "message": "Reboot completed", "result": "No blocking fault detected"}
            self.sync()
            return
        info = self._fault_info(target)
        self.diagnostics[target] = {"code": info[0], "message": info[1],
                                    "result": "Reboot cannot clear this condition; correct the physical/network cause first"}

    def action(self, body):
        """Translate lab controls only; eligibility decisions stay inside the original C++ rules."""
        action = body.get("action")
        if action == "reset":
            self.reset(test_fixture=body.get("test_fixture") is True)
        elif action == "event":
            node = body.get("node")
            kind_name = body.get("kind")
            if node not in NODES or kind_name not in KINDS:
                raise ValueError("invalid node or event")
            if kind_name not in NODE_CAPABILITIES[node]:
                raise ValueError("event not supported by selected simulated device")
            registered = self.foundation.device(OWNER, node)
            if not registered["registered"] or not registered["enabled"]:
                raise ValueError("device is not registered and enabled")
            if body.get("late_night") is True:
                minute = int(self.household_settings["quiet_start_minute"])
                self.command(f"time {minute}")
            kind = KINDS.index(kind_name)
            self.command(f"event {NODES.index(node)} {kind}")
            self._record_manual_event_context(node, kind_name, body)
            self.sync()
        elif action == "advance":
            seconds = body.get("seconds")
            if type(seconds) is not int or not 0 <= seconds <= 86400:
                raise ValueError("seconds must be an integer from 0 to 86400")
            remaining = seconds
            while remaining > 0:
                step = min(3600, remaining)
                self.command(f"advance {step}")
                self.sync()
                remaining -= step
            if seconds == 0:
                self.sync()
        elif action in ("wan", "clock", "node"):
            if type(body.get("enabled")) is not bool:
                raise ValueError("enabled must be a boolean")
            value = int(body["enabled"])
            if action == "node":
                node = body.get("node")
                if node not in NODES:
                    raise ValueError("invalid node")
                self.device_faults[node] = None if body["enabled"] else "LINK_LOSS"
                token = f"node {NODES.index(node)} {value}"
            else:
                token = f"{action} {value}"
                if action == "wan":
                    self.device_faults["hub"] = None if body["enabled"] else "INTERNET_LOSS"
            self.command(token)
            self.sync()
        elif action == "time":
            minute = body.get("minute")
            if type(minute) is not int or not 0 <= minute <= 1439:
                raise ValueError("minute must be an integer from 0 to 1439")
            self.command(f"time {minute}")
            self.sync()
        elif action == "mode":
            mode = body.get("mode")
            if mode not in {"HOME", "AWAY", "PAUSED", "VISITOR"}:
                raise ValueError("invalid mode")
            self.command(f"mode {mode}")
            self.service.store.homes[HOME].mode = HomeMode(mode)
            self.service.store.homes[HOME].version += 1
            self.sync()
        elif action in ("duplicate", "deadline"):
            self.command(action)
            self.sync()
        elif action == "fault":
            self._inject_fault(body.get("target"), body.get("fault"))
            self.sync()
        elif action == "clear_fault":
            self._clear_fault(body.get("target"))
            self.sync()
        elif action == "troubleshoot":
            self._troubleshoot(body.get("target"))
        elif action == "reboot":
            self._reboot(body.get("target"))
        elif action == "battery_usage":
            self._battery_add_usage(body.get("target"), body.get("days", 1), body.get("intensity", 1.0), body.get("battery_mv"))
        elif action == "battery_counter_reset":
            self._battery_counter_reset(body.get("target"), body.get("battery_mv"))
        elif action == "battery_profile_patch":
            target = body.get("target")
            if target not in self.service.store.battery_profiles or not isinstance(body.get("values"), dict):
                raise ValueError("invalid battery profile patch")
            current = asdict(self.service.store.battery_profiles[target])
            allowed = {"usable_capacity_mah", "reserve_percent", "sleep_current_ma", "awake_base_current_ma",
                       "sensor_extra_current_ma", "radio_tx_extra_current_ma", "radio_rx_extra_current_ma", "high_drain_ratio"}
            if not set(body["values"]).issubset(allowed):
                raise ValueError("invalid battery profile field")
            current.update(body["values"])
            self.service.battery.set_profile(BatteryPowerProfile(**current))
        elif action == "settings":
            self._update_household_settings(body.get("settings"))
        elif action == "notify":
            for job in self.service.notifications.due(self.state["now"]):
                self.service.notifications.provider_result(job.job_id, body.get("accepted", True) is True, "FAKE-PROVIDER")
        elif action in ("claim", "acknowledge", "resolve"):
            incident = body.get("incident_id")
            if not isinstance(incident, str) or not incident.startswith("inc_") or not incident[4:].isalnum():
                raise ValueError("invalid incident id")
            actor = body.get("actor", "primary")
            if actor not in ("primary", "backup"):
                raise ValueError("invalid simulation caregiver")
            self.api_call("POST", f"/v1/homes/{HOME}/incidents/{incident}/{action}", actor=actor)
        else:
            raise ValueError("unknown action")
        return self.snapshot()

    def _devices(self):
        devices = []
        for i, node in enumerate(NODES):
            info = self._fault_info(node)
            online = bool(self.state["nodes"][i]["online"])
            if info:
                health = info[2]
                code, message = info[0], info[1]
            else:
                health = "ACTIVE" if online else "OFFLINE"
                code, message = ("GS-OK000", "No fault detected") if online else ("GS-N003", "Node-to-hub communication unavailable")
            devices.append({"id": node, "kind": "NODE", "location": NODE_LOCATIONS[node], "active": online,
                            "health": health, "code": code, "message": message,
                            "diagnostic": self.diagnostics.get(node)})
        hub_info = self._fault_info("hub")
        hub_online = bool(self.state.get("hub_online", True))
        if hub_info:
            health, code, message = hub_info[2], hub_info[0], hub_info[1]
        elif not self.state["wan"]:
            health, code, message = "DEGRADED", *HUB_FAULTS["INTERNET_LOSS"][:2]
        else:
            health, code, message = ("ACTIVE", "GS-OK000", "No fault detected") if hub_online else ("OFFLINE", "GS-H005", "Hub unavailable")
        devices.insert(0, {"id": "hub", "kind": "HUB", "location": "Central hub", "active": hub_online,
                           "health": health, "code": code, "message": message,
                           "diagnostic": self.diagnostics.get("hub")})
        return devices

    def snapshot(self):
        home = self.api_call("GET", f"/v1/homes/{HOME}/snapshot")
        return {"simulation": {k: v for k, v in self.state.items() if k != "events"},
                "home": home,
                "settings": {**self.household_settings, "config_version": self.config_version},
                "devices": self._devices(),
                "incidents": [asdict(v) for v in self.service.store.incidents.values()],
                "notifications": [asdict(v) for v in self.service.store.notification_jobs.values()],
                "timeline": self.service.queries.timeline(HOME, OWNER, self.state["now"], limit=40),
                "battery_analytics": self.service.battery.all_estimates(),
                "limitations": ["Synthetic sensors, clock, transport and notification provider",
                                "Node, hub and backend data are volatile; reset/restart clears them",
                                "Coverage is a current lease, not proof of continuous historical coverage",
                                "Duplicate journal writes are suppressed; duplicate reducer evidence remains a known gap",
                                "Fault and temperature diagnoses are injected simulations until hardware telemetry exists",
                                "Battery runtime prediction uses synthetic activity counters and unverified current calibration until bench measurements are loaded",
                                "No physical prompts, SMS, push, OTA or RF acceptance in the host lab"]}


    @staticmethod
    def _pwa_event_presentation(event):
        labels = {
            "MOTION": ("Activity detected", "blue", "🏃"),
            "DOOR_OPEN": ("Main door opened", "red", "🚪"),
            "DOOR_CLOSED": ("Main door closed", "green", "🚪"),
            "OK_PRESSED": ("I'm OK received", "green", "❤"),
            "CALL_FAMILY": ("Call Family requested", "red", "☎"),
            "MISSING_MORNING_ACTIVITY": ("Morning activity not completed", "red", "☀"),
            "DAYTIME_INACTIVITY": ("No indoor activity for longer than expected", "red", "⚠"),
            "DOOR_LEFT_OPEN": ("Main door left open", "red", "🚪"),
            "MORNING_ROUTINE_COMPLETED": ("Morning routine completed", "green", "☀"),
            "UNUSUAL_NIGHT_BATHROOM_ACTIVITY": ("Unusual bathroom activity at night", "red", "☾"),
            "UNUSUAL_NIGHT_COMMON_ACTIVITY": ("Unusual common-room activity at night", "red", "☾"),
            "POST_DOOR_INACTIVITY": ("No indoor activity after main door closed", "red", "🚪"),
            "COVERAGE_CHANGED": ("Monitoring coverage changed", "blue", "📶"),
        }
        title, tone, icon = labels.get(event.get("kind"), (event.get("kind","Activity").replace("_"," ").title(), "green", "•"))
        location = event.get("location") or ""
        if event.get("kind") == "MOTION" and location:
            title = f"Motion in {NODE_LOCATIONS.get(location, location)}"
        if event.get("kind") == "COVERAGE_CHANGED":
            reason = (event.get("details") or {}).get("reason")
            title, tone = (("Monitoring coverage lost", "red") if reason == "coverage_lost" else
                           ("Monitoring coverage restored", "green") if reason == "coverage_restored" else
                           ("Monitoring coverage changed", "blue"))
        return {
            "id": event.get("event_id", f"evt-{event.get('occurred_at',0)}"),
            "at": int(event.get("occurred_at", 0)),
            "title": title,
            "tone": tone if event.get("tone") != "danger" else "red",
            "icon": icon,
        }

    def _pwa_add_audit(self, title, tone="green", icon="•", domain="care"):
        # Manual PWA scenario toggles may rebuild the deterministic simulator back
        # to its baseline clock. Keep UI audit/event chronology monotonic so the
        # most recently requested user action remains the newest visible event.
        previous_at = max((int(item.get("at", 0)) for item in self.pwa_audit), default=0)
        event_at = max(int(self.state["now"]), previous_at + 1)
        self.pwa_audit.append({
            "id": f"pwa-{len(self.pwa_audit)+1}-{event_at}",
            "at": event_at,
            "title": title,
            "tone": tone,
            "icon": icon,
            "domain": domain,
        })
        self.pwa_audit = self.pwa_audit[-40:]

    def _pwa_rebuild_base(self):
        """Rebuild current verification state through the existing simulator/backend path."""
        flags = dict(getattr(self, "pwa_flags", {}))
        audit = list(getattr(self, "pwa_audit", []))
        self.reset()
        self.pwa_flags.update(flags)
        self.pwa_audit = audit
        if not self.pwa_flags["morning_negative"]:
            self.action({"action":"event","node":"room1","kind":"MOTION"})
            self.action({"action":"event","node":"bathroom","kind":"MOTION"})
            self.action({"action":"event","node":"kitchen","kind":"MOTION"})
        if not self.pwa_flags["ok_negative"]:
            self.action({"action":"advance","seconds":60})
            self.action({"action":"event","node":"room1","kind":"OK_PRESSED"})
        if self.pwa_flags["morning_negative"]:
            self.action({"action":"deadline"})
        if self.pwa_flags.get("door_negative"):
            self.action({"action":"event","node":"entry","kind":"DOOR_OPEN"})
            self.action({"action":"advance","seconds":self.household_settings["door_open_timeout_seconds"]})
        if self.pwa_flags["battery_negative"]:
            self._inject_fault("kitchen", "LOW_BATTERY")
            self._battery_set_low("kitchen")
            self.sync()

    def pwa_reset_pass(self):
        self.reset(test_fixture=True)
        self.pwa_flags["door_negative"] = False
        self.action({"action":"event","node":"room1","kind":"MOTION"})
        self.action({"action":"event","node":"bathroom","kind":"MOTION"})
        self.action({"action":"event","node":"kitchen","kind":"MOTION"})
        self.action({"action":"advance","seconds":60})
        self.action({"action":"event","node":"room1","kind":"OK_PRESSED"})
        self.pwa_audit = []
        self._pwa_add_audit("All verification scenarios reset to PASS", "green", "✓")
        return self.pwa_view()

    def pwa_toggle(self, scenario):
        if scenario not in {"morning","ok","door","night","battery"}:
            raise ValueError("invalid PWA scenario")
        if scenario == "morning":
            self.pwa_flags["morning_negative"] = not self.pwa_flags["morning_negative"]
            self._pwa_add_audit(
                "Morning activity not completed" if self.pwa_flags["morning_negative"] else "Morning routine restored",
                "red" if self.pwa_flags["morning_negative"] else "green", "☀")
            self._pwa_rebuild_base()
        elif scenario == "ok":
            self.pwa_flags["ok_negative"] = not self.pwa_flags["ok_negative"]
            self.pwa_flags["ok_acknowledged"] = False
            self._pwa_add_audit(
                "I'm OK not confirmed" if self.pwa_flags["ok_negative"] else "I'm OK received",
                "red" if self.pwa_flags["ok_negative"] else "green", "❤")
            self._pwa_rebuild_base()
        elif scenario == "door":
            self.pwa_flags["door_negative"] = not self.pwa_flags["door_negative"]
            if self.pwa_flags["door_negative"]:
                self.action({"action":"event","node":"entry","kind":"DOOR_OPEN"})
                self._pwa_add_audit("Main door opened", "blue", "🚪")
                self.action({"action":"advance","seconds":self.household_settings["door_open_timeout_seconds"]})
            else:
                self.action({"action":"event","node":"entry","kind":"DOOR_CLOSED"})
                self._pwa_add_audit("Main door closed", "green", "🚪")
        elif scenario == "night":
            self.pwa_flags["night_negative"] = not self.pwa_flags["night_negative"]
            self._pwa_add_audit(
                "Unusual night activity: 8 bathroom visits" if self.pwa_flags["night_negative"] else "Night activity back to normal",
                "red" if self.pwa_flags["night_negative"] else "green", "☾")
        elif scenario == "battery":
            self.pwa_flags["battery_negative"] = not self.pwa_flags["battery_negative"]
            if self.pwa_flags["battery_negative"]:
                self._inject_fault("kitchen", "LOW_BATTERY")
                estimate = self._battery_set_low("kitchen")
                self._pwa_add_audit(f"Kitchen sensor battery low: {estimate['percent']}%", "red", "🔋", "device_health")
            else:
                self._clear_fault("kitchen")
                self._seed_battery_analytics()
                estimate = self.service.battery.estimate("kitchen").as_dict()
                self._pwa_add_audit(f"Kitchen sensor battery restored: {estimate['percent']}%", "green", "🔋", "device_health")
            self.sync()
        return self.pwa_view()

    def pwa_view(self):
        snap = self.snapshot()
        sim = snap["simulation"]
        home = snap["home"]
        now = int(sim["now"])
        coverage_lost = sim.get("coverage") != "COVERED"
        care_kinds = {"MISSING_MORNING_ACTIVITY","DAYTIME_INACTIVITY","CALL_FAMILY","DOOR_LEFT_OPEN",
                      "UNUSUAL_NIGHT_BATHROOM_ACTIVITY","UNUSUAL_NIGHT_COMMON_ACTIVITY","POST_DOOR_INACTIVITY"}
        current_door_open = (home.get("door_status") or {}).get("state") == "OPEN" or bool(self.pwa_flags.get("door_negative"))
        care_alert = any(i.get("state") != "RESOLVED" and i.get("kind") in care_kinds and
                         not (i.get("kind") == "DOOR_LEFT_OPEN" and not current_door_open)
                         for i in snap["incidents"])
        timeline_concern = next((e for e in snap["timeline"] if e.get("kind") in care_kinds and
                                 not (e.get("kind") == "DOOR_LEFT_OPEN" and not current_door_open)), None)
        unexpected_door = bool((home.get("door_status") or {}).get("unexpected", False))
        if timeline_concern is not None or unexpected_door:
            care_alert = True
        if (self.pwa_flags.get("morning_negative") or self.pwa_flags.get("ok_negative")
                or self.pwa_flags.get("night_negative")):
            care_alert = True
        if coverage_lost:
            care_alert = True
        # An explicit care/activity allowlist prevents new diagnostic event kinds
        # from leaking into the caregiver's important-event feed by default.
        important_kinds = {"MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY",
                           "MISSING_MORNING_ACTIVITY", "DAYTIME_INACTIVITY", "DOOR_LEFT_OPEN",
                           "MORNING_ROUTINE_COMPLETED", "UNUSUAL_NIGHT_BATHROOM_ACTIVITY",
                           "UNUSUAL_NIGHT_COMMON_ACTIVITY", "POST_DOOR_INACTIVITY", "COVERAGE_CHANGED"}
        recent = []
        for item in snap["timeline"]:
            if item.get("kind") not in important_kinds:
                continue
            if item.get("kind") == "COVERAGE_CHANGED" and (item.get("details") or {}).get("reason") not in {"coverage_lost", "coverage_restored"}:
                continue
            recent.append(self._pwa_event_presentation(item))
        # Battery telemetry remains in backend analytics/audit history, but is a
        # maintenance condition rather than a household safety event.  Only
        # care-domain audit entries belong in Home's important-event feed.
        recent.extend(item for item in getattr(self, "pwa_audit", [])
                      if item.get("domain", "care") != "device_health")
        dedup = {item["id"]: item for item in recent}
        recent = sorted(dedup.values(), key=lambda x: (x["at"], x["id"]), reverse=True)[:20]
        latest_activity = home.get("latest_activity")
        indoor_age_min = None
        if latest_activity and latest_activity.get("occurred_at") is not None:
            indoor_age_min = max(0, (now - int(latest_activity["occurred_at"])) // 60)
        door = home.get("door_status") or {"state":"CLOSED","since":None}
        devices = []
        name_map = {
            "hub": ("Hub","Central Hub"),
            "room1": ("Bedroom Node","Motion Sensor"),
            "kitchen": ("Kitchen Node","Motion Sensor"),
            "entry": ("Main Door Node","Door Sensor"),
            "pooja": ("Pooja Room Node","Motion Sensor"),
            "bathroom": ("Bathroom Sensor","Motion Sensor"),
            "common": ("Common Room Sensor","Motion Sensor"),
        }
        battery_estimates = snap.get("battery_analytics", {})
        self.foundation.expire_stale(now, exclude=NODES)
        registry = {d["device_id"]: d for d in self.foundation.devices(OWNER)}
        for d in snap["devices"]:
            if d["id"] not in registry:
                continue
            estimate = battery_estimates.get(d["id"], {})
            nm, typ = name_map.get(d["id"], (d["location"], d["kind"]))
            record = registry[d["id"]]
            nm = record["display_name"]
            active = bool(d["active"] and record["enabled"])
            health = d["health"] if active else "OFFLINE"
            self.foundation.record_health(d["id"], active, health, estimate.get("battery_mv"), estimate.get("percent"), estimate.get("drain_status", "LEARNING"))
            devices.append({
                "id": d["id"], "name": nm, "type": typ, "active": active,
                "kind": record["kind"], "capability": record["capability"], "room": record["room"],
                "registered": True, "enabled": bool(record["enabled"]), "registration_source": record["registration_source"],
                "firmware_version": record["firmware_version"], "last_seen_at": record["last_seen_at"],
                "health": health, "code": d["code"], "message": d["message"],
                "battery": estimate.get("percent"),
                "battery_mv": estimate.get("battery_mv"),
                "left": self._format_battery_runtime(estimate, d["id"] == "hub"),
                "estimated_days": estimate.get("estimated_days"),
                "daily_mah": estimate.get("daily_mah"),
                "confidence": estimate.get("confidence", "LOW"),
                "drain_status": estimate.get("drain_status", "LEARNING"),
                "recent_daily_mah": estimate.get("recent_daily_mah"),
                "baseline_daily_mah": estimate.get("baseline_daily_mah"),
                "wakeups_per_day": estimate.get("recent_wakeups_per_day"),
                "retries_per_day": estimate.get("recent_retries_per_day"),
                "tx_packets_per_day": estimate.get("recent_tx_packets_per_day"),
                "observation_hours": estimate.get("observation_hours", 0),
                "updated": "just now",
            })
        for did, record in registry.items():
            if did in {d["id"] for d in devices}: continue
            devices.append({"id":did,"name":record["display_name"],"type":record["capability"],"kind":record["kind"],
                            "capability":record["capability"],"room":record["room"],"active":bool(record["online"]),
                            "health":record["health"],"battery":record["battery_percent"],"battery_mv":record["battery_mv"],
                            "drain_status":record["drain_status"],"left":"calculating","daily_mah":None,"confidence":"LOW",
                            "registration_source":record["registration_source"],"registered":True,"enabled":bool(record["enabled"]),
                            "firmware_version":record["firmware_version"],"last_seen_at":record["last_seen_at"],"updated":"never"})
        for d in devices:
            pct = d.get("battery")
            d["battery_health"] = "UNKNOWN" if pct is None else "CRITICAL" if pct <= self.household_settings["critical_battery_percent"] else "LOW" if pct <= self.household_settings["battery_alert_percent"] else "NORMAL"
        low = min((d for d in devices if d["battery"] is not None), key=lambda d:d["battery"], default=None)
        drain_attention = [d for d in devices if d.get("drain_status") == "HIGH"] if self.household_settings["abnormal_drain_alert_enabled"] else []
        morning_ok = (not self.household_settings["morning_sequence_enabled"] or bool(sim.get("morning_sequence_completed", False))) and not self.pwa_flags.get("morning_negative", False)
        ok = not self.pwa_flags.get("ok_negative", False)
        ok_status = "OVERDUE" if not ok else "ACKNOWLEDGED" if self.pwa_flags.get("ok_acknowledged", False) else "NORMAL"
        night_bathroom = int(sim.get("night_bathroom_visits", 0))
        night_common = int(sim.get("night_common_visits", 0))
        if self.pwa_flags.get("night_negative"):
            night_bathroom = self.household_settings["night_bathroom_visit_threshold"] + 1
        night_unusual = (night_bathroom > self.household_settings["night_bathroom_visit_threshold"] or
                         night_common > self.household_settings["night_common_visit_threshold"])
        night_concerns = []
        if night_bathroom > self.household_settings["night_bathroom_visit_threshold"]:
            night_concerns.append("Bathroom visits are higher than the configured night limit.")
        if night_common > self.household_settings["night_common_visit_threshold"]:
            night_concerns.append("Common-room visits are higher than the configured night limit.")
        night_concern_text = " ".join(night_concerns) if night_concerns else ""
        active_kinds = [i.get("kind") for i in snap["incidents"] if i.get("state") != "RESOLVED"]
        latest_concern = timeline_concern
        problem_map = {
            "MISSING_MORNING_ACTIVITY": "Morning activity not completed.",
            "DAYTIME_INACTIVITY": "No indoor activity for longer than expected.",
            "CALL_FAMILY": "Call Family was requested.",
            "DOOR_LEFT_OPEN": "Main door has remained open longer than configured.",
            "UNUSUAL_NIGHT_BATHROOM_ACTIVITY": "Bathroom visits are higher than the configured night limit.",
            "UNUSUAL_NIGHT_COMMON_ACTIVITY": "Common-room visits are higher than the configured night limit.",
            "POST_DOOR_INACTIVITY": "No indoor activity was detected after the main door closed.",
            "UNEXPECTED_DOOR_OPEN": "Main door opened during the configured quiet-hours window.",
        }
        concern_kind = ("UNEXPECTED_DOOR_OPEN" if unexpected_door else
                        (latest_concern.get("kind") if latest_concern else (active_kinds[0] if active_kinds else "I_AM_OK_OVERDUE" if not ok else "MONITORING_COVERAGE_LOST" if coverage_lost else None)))
        subtitle = problem_map.get(concern_kind, "Please check the home status.") if care_alert else "All is well at home."
        post_door_alert = bool(sim.get("post_door_inactivity_alerted", False)) or concern_kind == "POST_DOOR_INACTIVITY"
        door_left_open_alert = current_door_open and (concern_kind == "DOOR_LEFT_OPEN" or any(e.get("kind")=="DOOR_LEFT_OPEN" for e in snap["timeline"]))
        morning_missing = concern_kind == "MISSING_MORNING_ACTIVITY" or self.pwa_flags.get("morning_negative", False)
        if morning_missing:
            morning_status = "MISSED"
        elif bool(sim.get("morning_sequence_completed", False)):
            morning_status = "COMPLETED"
        elif bool(sim.get("morning_sequence_started", False)) and self.household_settings["morning_sequence_enabled"]:
            morning_status = "IN_PROGRESS"
        elif self.household_settings["morning_sequence_enabled"]:
            morning_status = "NOT_STARTED"
        else:
            morning_status = "UNAVAILABLE"
        return {
            "source": "Ghar Sajag v1.5.4 C++ rules + Python backend + PWA bridge",
            "simulation_now": now,
            "care": {"alert": care_alert, "title": "Attention needed at home" if care_alert else "Home looks normal", "subtitle": subtitle, "problem_kind": concern_kind},
            "morning": {
                "ok": morning_ok,
                "sequence_completed": bool(sim.get("morning_sequence_completed", False)),
                "missing": morning_missing,
                "status": morning_status,
            },
            "iam_ok": {"ok": ok, "status": ok_status},
            "door": {"open": door.get("state") == "OPEN" or bool(self.pwa_flags.get("door_negative")), "open_for_s": max(0, now-int(door.get("since") or now)) if door.get("state") == "OPEN" else 0, "indoor_activity_age_min": indoor_age_min, "post_close_inactivity_alert": post_door_alert, "left_open_alert": door_left_open_alert, "unexpected_alert": unexpected_door},
            "night": {"bathroom_visits": night_bathroom, "common_visits": night_common, "unusual": night_unusual,
                      "concern_text": night_concern_text,
                      "bathroom_threshold": self.household_settings["night_bathroom_visit_threshold"],
                      "common_threshold": self.household_settings["night_common_visit_threshold"]},
            "device_health": {
                "low_id": low["id"] if low else None, "low_name": low["name"] if low else "No battery telemetry", "low_percent": low["battery"] if low else None,
                "runtime": low["left"] if low else "calculating", "daily_mah": low.get("daily_mah") if low else None, "confidence": low.get("confidence") if low else "LOW",
                "wakeups_per_day": low.get("wakeups_per_day") if low else None, "retries_per_day": low.get("retries_per_day") if low else None,
                "drain_status": low.get("drain_status") if low else "LEARNING", "high_drain_devices": [d["id"] for d in drain_attention],
                "offline_devices": [d["id"] for d in devices if not d["active"]],
                "monitoring_coverage_lost": coverage_lost,
                "alert_percent": self.household_settings["battery_alert_percent"],
                "critical_percent": self.household_settings["critical_battery_percent"],
                "critical": low is not None and low["battery_health"] == "CRITICAL",
                "attention": coverage_lost or (low is not None and low["battery"] <= self.household_settings["battery_alert_percent"]) or bool(drain_attention) or any(not d["active"] for d in devices),
            },
            "coverage": {"state": sim.get("coverage", "UNKNOWN"), "lost": coverage_lost},
            "devices": devices,
            "events": recent,
            "schedules": dict(self.household_settings),
            "home_details": self.foundation.home(OWNER),
            "family_members": self.foundation.members(OWNER),
            "network": {"hub_online":bool(sim.get("hub_online",True)),"wan_online":bool(sim.get("wan",True)),"provisioning":"HW_REQUIRED"},
            "raw": {"home_mode": home.get("mode"), "settings_version": snap["settings"].get("config_version")},
        }

    def run_suite(self):
        """Run the declarative release functional catalog through this connected lab."""
        validation_dir = ROOT / "tools" / "validation"
        if str(validation_dir) not in sys.path:
            sys.path.insert(0, str(validation_dir))
        from functional_scenarios import run_catalog

        report = run_catalog(self)
        report["scope"] = (
            "Declarative synthetic functional regression through C++ node/hub, Python backend and read models; "
            "physical ESP32/RF/power acceptance remains separate"
        )
        report["limitations"] = self.snapshot()["limitations"]
        self.report = report
        (ROOT / "logs/e2e_report.json").write_text(json.dumps(report, indent=2) + "\n")
        lines = [f"Ghar Sajag host functional regression {report['release']}",
                 f"{report['status']} {report['passed']}/{report['total']}"]
        for item in report["cases"]:
            detail = "; ".join(item.get("failures", []))
            lines.append(f"{'PASS' if item['passed'] else 'FAIL'} {item['id']}: {item['title']}" + (f" :: {detail}" if detail else ""))
        (ROOT / "logs/e2e_report.txt").write_text("\n".join(lines) + "\n")
        return report


    def pwa_validation_catalog(self):
        validation_dir = ROOT / "tools" / "validation"
        if str(validation_dir) not in sys.path:
            sys.path.insert(0, str(validation_dir))
        from pwa_frontend_validation import catalog_for_frontend
        return catalog_for_frontend()

    def pwa_validation_run(self, scenario_id):
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ValueError("scenario id required")
        validation_dir = ROOT / "tools" / "validation"
        if str(validation_dir) not in sys.path:
            sys.path.insert(0, str(validation_dir))
        from pwa_frontend_validation import execute_for_frontend
        return execute_for_frontend(self, scenario_id)



class WebLab:
    def __init__(self, lab, port):
        self.lab, self.port = lab, port

    def __call__(self, environ, start_response):
        # Restrict the local lab to its own origin. No wildcard bind/CORS or real user authentication.
        host = environ.get("HTTP_HOST", "")
        allowed = {f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"parivar.test:{self.port}"}
        origin = environ.get("HTTP_ORIGIN")
        if host not in allowed or (origin and origin not in {"http://"+h for h in allowed}):
            status, result = "403 Forbidden", {"error":"local_origin_required"}
        else:
            try:
                return self.route(environ, start_response)
            except KeyError as error:
                status, result = "404 Not Found", {"error":str(error)[:200]}
            except (ValueError, TypeError) as error:
                status, result = "400 Bad Request", {"error":str(error)[:200]}
            except PermissionError:
                status, result = "403 Forbidden", {"error":"not_authorized"}
            except RuntimeError as error:
                status, result = "409 Conflict", {"error":str(error)[:200]}
            except Exception:
                self.lab.log.exception("category=SIM module=T01 event=request_failed")
                status, result = "500 Internal Server Error", {"error":"See logs/e2e_flow.txt"}
        return self.json_response(start_response, result, status)

    @staticmethod
    def json_response(start, result, status="200 OK"):
        data = json.dumps(result).encode()
        start(status, [("Content-Type","application/json"),("Content-Length",str(len(data))),("Cache-Control","no-store")])
        return [data]

    def route(self, env, start):
        path, method = env.get("PATH_INFO","/"), env.get("REQUEST_METHOD","GET")
        if path.startswith("/pwa/foundation/"):
            actor = env.get("HTTP_X_ACTOR_ID", "")
            if method in {"POST", "PATCH", "DELETE"}:
                if not env.get("CONTENT_TYPE", "").startswith("application/json"): raise ValueError("application/json required")
                length = int(env.get("CONTENT_LENGTH") or 0)
                if not 0 <= length <= 8192: raise ValueError("request too large")
                body = json.loads(env["wsgi.input"].read(length) or b"{}")
                if not isinstance(body, dict): raise ValueError("object required")
            else: body = {}
            foundation = self.lab.foundation
            tail = path.removeprefix("/pwa/foundation/").split("/")
            if tail == ["home"]:
                result = foundation.home(actor) if method == "GET" else foundation.update_home(actor, body) if method == "PATCH" else None
            elif tail == ["members"]:
                result = foundation.members(actor) if method == "GET" else foundation.add_member(actor, body) if method == "POST" else None
            elif len(tail) == 2 and tail[0] == "members":
                result = foundation.update_member(actor, tail[1], body) if method == "PATCH" else foundation.deactivate_member(actor, tail[1]) if method == "DELETE" else None
            elif tail == ["devices"]:
                result = foundation.devices(actor) if method == "GET" else foundation.register_device(actor, body) if method == "POST" else None
            elif len(tail) == 2 and tail[0] == "devices":
                result = foundation.device(actor, tail[1]) if method == "GET" else foundation.update_device(actor, tail[1], body) if method == "PATCH" else foundation.unregister_device(actor, tail[1]) if method == "DELETE" else None
            elif len(tail) == 3 and tail[0] == "devices" and tail[2] == "health" and method == "POST":
                foundation._authorize(actor, True)
                if set(body) != {"online", "health", "battery_mv", "battery_percent", "drain_status"}: raise ValueError("health_fields_mismatch")
                foundation.validate_health(**body)
                device = foundation.device(actor, tail[1])
                if not device["registered"]: raise ValueError("device_unregistered")
                if tail[1] in NODES:
                    self.lab.action({"action":"node","node":tail[1],"enabled":body["online"]})
                foundation.record_health(tail[1], heartbeat=True, **body)
                result = foundation.device(actor, tail[1])
            elif tail == ["policy"]:
                result = foundation.policy(actor) if method == "GET" else self.lab._save_policy_from_api(actor, body) if method == "PATCH" else None
            elif tail == ["network"] and method == "GET":
                foundation._authorize(actor)
                result = self.lab.pwa_view()["network"]
            else: result = None
            if result is None: return self.json_response(start,{"error":"route_not_found"},"404 Not Found")
            return self.json_response(start,result,"201 Created" if method == "POST" and tail in (["members"],["devices"]) else "200 OK")
        if method == "GET" and path == "/sim/state":
            return self.json_response(start,self.lab.snapshot())
        if method == "GET" and path == "/pwa/state":
            return self.json_response(start,self.lab.pwa_view())
        if method == "GET" and path == "/pwa/validation/catalog":
            return self.json_response(start,self.lab.pwa_validation_catalog())
        if method == "GET" and path == "/sim/report":
            return self.json_response(start,self.lab.report)
        if method == "POST" and path in ("/sim/action","/sim/run-suite","/pwa/action","/pwa/validation/run"):
            if not env.get("CONTENT_TYPE", "").startswith("application/json"):
                raise ValueError("application/json required")
            length = int(env.get("CONTENT_LENGTH") or 0)
            if not 0 <= length <= 8192:
                raise ValueError("request too large")
            body = json.loads(env["wsgi.input"].read(length) or b"{}")
            if not isinstance(body,dict):
                raise ValueError("object required")
            if path.endswith("run-suite"):
                result = self.lab.run_suite()
            elif path == "/pwa/validation/run":
                result = self.lab.pwa_validation_run(body.get("scenario_id"))
            elif path == "/pwa/action":
                action = body.get("action")
                if action == "reset_pass":
                    result = self.lab.pwa_reset_pass()
                elif action == "toggle":
                    result = self.lab.pwa_toggle(body.get("scenario"))
                elif action == "settings_save":
                    self.lab._update_household_settings(body.get("settings"))
                    result = self.lab.pwa_view()
                else:
                    raise ValueError("invalid PWA action")
            else:
                result = self.lab.action(body)
            return self.json_response(start,result)
        if path.startswith("/v1/") or path == "/healthz":
            if int(env.get("CONTENT_LENGTH") or 0)>8192:
                raise ValueError("request too large")
            return self.lab.api(env,start)
        # Exact allowlist keeps source/config/log files out of the HTTP file surface.
        assets = {"/":("tools/sim/pwa/index.html","text/html"),
                  "/index.html":("tools/sim/pwa/index.html","text/html"),
                  "/app.js":("tools/sim/pwa/app.js","text/javascript"),
                  "/validation_engine.mjs":("tools/sim/pwa/validation_engine.mjs","text/javascript"),
                  "/schedule_feedback.mjs":("tools/sim/pwa/schedule_feedback.mjs","text/javascript"),
                  "/styles.css":("tools/sim/pwa/styles.css","text/css"),
                  "/sw.js":("tools/sim/pwa/sw.js","text/javascript"),
                  "/manifest.webmanifest":("tools/sim/pwa/manifest.webmanifest","application/manifest+json"),
                  "/assets/icon.svg":("tools/sim/pwa/assets/icon.svg","image/svg+xml"),
                  "/lab":("tools/sim/web/index.html","text/html"),
                  "/lab.mjs":("tools/sim/web/lab.mjs","text/javascript"),
                  "/lab.css":("tools/sim/web/lab.css","text/css"),
                  "/src/features/home/index.mjs":("app/src/features/home/index.mjs","text/javascript"),
                  "/src/features/incidents/index.mjs":("app/src/features/incidents/index.mjs","text/javascript"),
                  "/src/features/routines/index.mjs":("app/src/features/routines/index.mjs","text/javascript"),
                  "/src/platform/logging.mjs":("app/src/platform/logging.mjs","text/javascript")}
        if method != "GET" or path not in assets:
            return self.json_response(start,{"error":"not_found"},"404 Not Found")
        file, mime = assets[path]
        data = (ROOT/file).read_bytes()
        start("200 OK",[("Content-Type",mime),("Content-Length",str(len(data))),("Cache-Control","no-store"),("X-Content-Type-Options","nosniff")])
        return [data]


class QuietRequests(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    # Browsers request HTML, JS, CSS, manifest, service-worker assets and API
    # endpoints concurrently. The original single-threaded wsgiref server could
    # intermittently stall Chromium navigation while another request was active.
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--test",action="store_true")
    args=parser.parse_args()
    lab=Lab(":memory:" if args.test else os.environ.get("GS_APP_DB", str(ROOT / "logs" / "application.sqlite")))
    try:
        if args.test:
            report=lab.run_suite()
            print(json.dumps(report,indent=2))
            return 0 if report["status"]=="PASS" else 1
        with make_server("127.0.0.1",args.port,WebLab(lab,args.port),server_class=ThreadingWSGIServer,handler_class=QuietRequests) as server:
            print(f"Ghar Sajag local simulation: http://localhost:{args.port}",flush=True)
            print("Synthetic data only. Ctrl+C stops both processes. Reset clears scenario state.",flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        lab.close()

if __name__ == "__main__":
    raise SystemExit(main())
