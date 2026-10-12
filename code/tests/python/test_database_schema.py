from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ghar_sajag.database import APPLICATION_TABLES, MIGRATIONS, REQUIRED_TABLES, initialize_sqlite, table_names
from ghar_sajag.model import CloudEvent, Resident
from ghar_sajag.service import GharSajagService
from ghar_sajag.sqlite_events import SQLiteEventMap
from ghar_sajag.store import InMemoryStore


class DatabaseSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        initialize_sqlite(self.db)
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("h1", "Home", "Asia/Kolkata", 1, 1),
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_p0_tables_exist(self) -> None:
        self.assertTrue(REQUIRED_TABLES.issubset(table_names(self.db)))

    def test_migrations_are_versioned_and_preserve_existing_household(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.sqlite"
            old = sqlite3.connect(path)
            old.execute("CREATE TABLE households (home_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, timezone TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'en-IN', mode TEXT NOT NULL DEFAULT 'HOME', consent_state TEXT NOT NULL DEFAULT 'ACTIVE', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
            old.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('h1','Existing home','Asia/Kolkata',1,1)")
            old.commit()
            initialize_sqlite(old)
            applied = old.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
            initialize_sqlite(old)
            self.assertEqual(old.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], applied)
            self.assertEqual(old.execute("SELECT display_name FROM households WHERE home_id='h1'").fetchone()[0], "Existing home")
            self.assertTrue(APPLICATION_TABLES.issubset(table_names(old)))
            old.close()

    def test_006_to_007_preserves_history_reports_order_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "phase3b-006.sqlite"
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute(
                "CREATE TABLE schema_migrations (name TEXT PRIMARY KEY, "
                "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                if migration.name >= "007_":
                    continue
                db.executescript(migration.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migrations(name) VALUES(?)", (migration.name,))

            homes = (("upgrade-home-a", "Owner A"), ("upgrade-home-b", "Owner B"))
            for home_id, name in homes:
                db.execute(
                    "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
                    "VALUES(?,?,?,?,?)",
                    (home_id, name, "Asia/Kolkata", 1, 1),
                )
            db.execute(
                "INSERT INTO device_registry(device_id,home_id,display_name,kind,capability,room,"
                "registration_source,registered,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("removed-node-a", "upgrade-home-a", "Removed Bathroom Node", "NODE", "MOTION",
                 "Bathroom", "SIMULATOR", 0, 1, 2),
            )

            now = 1_800_000_000
            event_rows = [
                ("legacy-a-motion-z", "upgrade-home-a", "removed-node-a", "MOTION", "Bathroom", now - 100, {}),
                ("legacy-a-motion-a", "upgrade-home-a", "src-a-a", "MOTION", "Bathroom", now - 100, {}),
                ("legacy-a-call", "upgrade-home-a", "src-a-call", "CALL_FAMILY", "Bedroom", now - 99, {}),
                ("legacy-a-door", "upgrade-home-a", "src-a-door", "DOOR_OPEN", "Main door", now - 98,
                 {"unexpected": True}),
                ("legacy-b-motion-z", "upgrade-home-b", "src-b-z", "MOTION", "Common room", now - 100, {}),
                ("legacy-b-motion-a", "upgrade-home-b", "src-b-a", "MOTION", "Common room", now - 100, {}),
                ("legacy-b-ok", "upgrade-home-b", "src-b-ok", "OK_PRESSED", "Bedroom", now - 99, {}),
            ]
            for sequence, (event_id, home_id, source_id, kind, location, occurred_at, payload) in enumerate(event_rows):
                db.execute(
                    "INSERT INTO events(event_id,home_id,source_id,source_type,session_id,sequence_number,"
                    "sensor_type,event_type,location,occurred_at,received_at,hub_received_at,payload_json) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (event_id, home_id, source_id, "RESIDENT_CONTROL" if kind in {"CALL_FAMILY", "OK_PRESSED"} else "NODE",
                     1, sequence, kind, kind, location, occurred_at, occurred_at + 1, occurred_at + 1,
                     json.dumps(payload, sort_keys=True)),
                )
            db.execute(
                "INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,?)",
                ("care-a", "Caregiver A", 1),
            )
            db.execute(
                "INSERT INTO alerts(alert_id,home_id,stable_key,alert_type,severity,state,source_event_id,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                ("alert-a", "upgrade-home-a", "call:legacy-a-call", "CALL_FAMILY", "URGENT", "OPEN",
                 "legacy-a-call", now - 99),
            )
            db.execute(
                "INSERT INTO acknowledgements(acknowledgement_id,alert_id,caregiver_id,action,occurred_at) "
                "VALUES(?,?,?,?,?)",
                ("ack-a", "alert-a", "care-a", "CLAIM", now - 90),
            )
            db.execute(
                "INSERT INTO notification_jobs(job_id,alert_id,home_id,recipient_id,stage,due_at,state,idempotency_key) "
                "VALUES(?,?,?,?,?,?,?,?)",
                ("job-a", "alert-a", "upgrade-home-a", "care-a", 1, now - 80, "CREATED", "job:alert-a"),
            )
            db.execute(
                "INSERT INTO notification_records(record_id,home_id,source_event_id,category,severity,state,title,"
                "message,correlation_key,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("record-a", "upgrade-home-a", "legacy-a-call", "SAFETY", "URGENT", "DELIVERED",
                 "Call Family requested", "Family assistance was requested.", "event:legacy-a-call", now - 99),
            )
            db.commit()

            legacy_columns = [row[1] for row in db.execute("PRAGMA table_info(events)")]
            self.assertNotIn("canonical_event_id", legacy_columns)
            before_events = [dict(row) for row in db.execute("SELECT * FROM events ORDER BY event_id")]
            before_order = {
                home_id: [row[0] for row in db.execute(
                    "SELECT event_id FROM events WHERE home_id=? ORDER BY occurred_at DESC,event_id DESC",
                    (home_id,),
                )]
                for home_id, _ in homes
            }
            before_references = {
                "alert": tuple(db.execute(
                    "SELECT alert_id,home_id,source_event_id FROM alerts WHERE alert_id='alert-a'"
                ).fetchone()),
                "ack": tuple(db.execute(
                    "SELECT acknowledgement_id,alert_id,caregiver_id FROM acknowledgements WHERE acknowledgement_id='ack-a'"
                ).fetchone()),
                "job": tuple(db.execute(
                    "SELECT job_id,alert_id,home_id,recipient_id FROM notification_jobs WHERE job_id='job-a'"
                ).fetchone()),
                "record": tuple(db.execute(
                    "SELECT record_id,home_id,source_event_id FROM notification_records WHERE record_id='record-a'"
                ).fetchone()),
            }

            def reports(events):
                service = GharSajagService(InMemoryStore(events=events))
                for home_id, name in homes:
                    owner = f"owner-{home_id[-1]}"
                    service.homes.create(
                        home_id, name, "Asia/Kolkata", "en-IN", owner,
                        [Resident(f"resident-{home_id[-1]}", "Resident", True, 1)], 1,
                    )
                return {
                    (home_id, period): service.queries.report(home_id, f"owner-{home_id[-1]}", now, period)
                    for home_id, _ in homes for period in ("TODAY", "WEEK", "MONTH")
                }

            reference_events = {}
            for row in before_events:
                event = CloudEvent(
                    row["home_id"], row["event_id"], row["event_type"], row["location"],
                    row["occurred_at"], row["hub_received_at"], row["received_at"],
                    int(row["uncertainty_ms"] or 0) // 1000, bool(row["is_test"]),
                    json.loads(row["payload_json"]),
                )
                reference_events[(event.home_id, event.event_id)] = event
            before_reports = reports(reference_events)
            self.assertIn(
                {"location": "Bathroom", "count": 2},
                before_reports[("upgrade-home-a", "TODAY")]["room_activity"],
            )

            initialize_sqlite(db)

            after_events = [dict(row) for row in db.execute("SELECT * FROM events ORDER BY event_id")]
            self.assertEqual(len(after_events), len(before_events))
            self.assertEqual(
                [{key: row[key] for key in legacy_columns} for row in after_events],
                before_events,
            )
            self.assertTrue(all(row["canonical_event_id"] == row["event_id"] for row in after_events))
            self.assertEqual(
                {row["event_id"]: row["home_id"] for row in after_events},
                {row["event_id"]: row["home_id"] for row in before_events},
            )
            after_order = {
                home_id: [row[0] for row in db.execute(
                    "SELECT canonical_event_id FROM events WHERE home_id=? "
                    "ORDER BY occurred_at DESC,canonical_event_id DESC",
                    (home_id,),
                )]
                for home_id, _ in homes
            }
            self.assertEqual(after_order, before_order)
            self.assertEqual(reports(SQLiteEventMap(db)), before_reports)
            self.assertEqual(
                tuple(db.execute("SELECT alert_id,home_id,source_event_id FROM alerts WHERE alert_id='alert-a'").fetchone()),
                before_references["alert"],
            )
            self.assertEqual(
                tuple(db.execute("SELECT acknowledgement_id,alert_id,caregiver_id FROM acknowledgements WHERE acknowledgement_id='ack-a'").fetchone()),
                before_references["ack"],
            )
            self.assertEqual(
                tuple(db.execute("SELECT job_id,alert_id,home_id,recipient_id FROM notification_jobs WHERE job_id='job-a'").fetchone()),
                before_references["job"],
            )
            self.assertEqual(
                tuple(db.execute("SELECT record_id,home_id,source_event_id FROM notification_records WHERE record_id='record-a'").fetchone()),
                before_references["record"],
            )
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                db.execute("SELECT registered FROM device_registry WHERE device_id='removed-node-a'").fetchone()[0], 0
            )

            applied = db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            stable_snapshot = [dict(row) for row in db.execute("SELECT * FROM events ORDER BY event_id")]
            initialize_sqlite(db)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], applied)
            self.assertEqual([dict(row) for row in db.execute("SELECT * FROM events ORDER BY event_id")], stable_snapshot)

            event_map = SQLiteEventMap(db)
            legacy = event_map[("upgrade-home-a", "legacy-a-call")]
            same_id_other_home = CloudEvent(
                "upgrade-home-b", legacy.event_id, "MOTION", "Kitchen", now - 50, now - 49, now - 49
            )
            _, duplicate = event_map.accept_once(same_id_other_home)
            self.assertFalse(duplicate)
            _, duplicate = event_map.accept_once(same_id_other_home)
            self.assertTrue(duplicate)
            self.assertEqual(event_map[("upgrade-home-a", legacy.event_id)].kind, "CALL_FAMILY")
            self.assertEqual(event_map[("upgrade-home-b", legacy.event_id)].kind, "MOTION")
            self.assertEqual(
                db.execute("SELECT event_id FROM events WHERE home_id='upgrade-home-a' AND canonical_event_id=?",
                           (legacy.event_id,)).fetchone()[0],
                legacy.event_id,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM events WHERE canonical_event_id=?", (legacy.event_id,)).fetchone()[0], 2
            )
            db.close()

    def test_event_identity_suppresses_duplicates(self) -> None:
        self.db.execute(
            "INSERT INTO rooms(room_id,home_id,name,room_type) VALUES(?,?,?,?)",
            ("r1", "h1", "Kitchen", "KITCHEN"),
        )
        self.db.execute(
            "INSERT INTO hubs(hub_id,home_id,board_profile,firmware_version) VALUES(?,?,?,?)",
            ("hub1", "h1", "esp32-devkit-v1", "1.5.4"),
        )
        self.db.execute(
            "INSERT INTO nodes(node_id,home_id,hub_id,room_id,location,board_profile,capability_profile,firmware_version) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("n1", "h1", "hub1", "r1", "Kitchen", "esp32-c3", "pir", "1.5.4"),
        )
        row = ("e1", "h1", "n1", "NODE", "n1", "r1", 7, 9, "PIR", "MOTION", "Kitchen", 10, 11)
        sql = (
            "INSERT INTO events(event_id,home_id,source_id,source_type,node_id,room_id,session_id,sequence_number,"
            "sensor_type,event_type,location,occurred_at,received_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        self.db.execute(sql, row)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(sql, ("e2",) + row[1:])

    def test_alert_stable_key_is_idempotent(self) -> None:
        sql = "INSERT INTO alerts(alert_id,home_id,stable_key,alert_type,severity,state,created_at) VALUES(?,?,?,?,?,?,?)"
        self.db.execute(sql, ("a1", "h1", "missing:morning", "MISSING_MORNING_ACTIVITY", "CONCERN", "OPEN", 100))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(sql, ("a2", "h1", "missing:morning", "MISSING_MORNING_ACTIVITY", "CONCERN", "OPEN", 101))

    def test_routine_window_is_persistable_for_reboot_recovery(self) -> None:
        self.db.execute(
            "INSERT INTO routines(routine_id,home_id,name,routine_type,window_start_minute,window_end_minute,"
            "grace_seconds,config_version,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("morning", "h1", "Morning activity", "MORNING_ACTIVITY", 420, 570, 900, 4, 10),
        )
        self.db.execute(
            "INSERT INTO routine_windows(window_id,routine_id,home_id,start_at,end_at,grace_end_at,state,"
            "coverage_state,evidence_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("2026-09-11:morning", "morning", "h1", 100, 200, 215, "OPEN", "COVERED", "[]", 120),
        )
        row = self.db.execute(
            "SELECT state,coverage_state FROM routine_windows WHERE window_id=?", ("2026-09-11:morning",)
        ).fetchone()
        self.assertEqual(row, ("OPEN", "COVERED"))

    def test_notification_job_idempotency_and_human_ack_are_separate(self) -> None:
        self.db.execute(
            "INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,?)", ("c1", "Family", 1)
        )
        self.db.execute(
            "INSERT INTO alerts(alert_id,home_id,stable_key,alert_type,severity,state,created_at) VALUES(?,?,?,?,?,?,?)",
            ("a1", "h1", "call:e1", "CALL_FAMILY", "URGENT", "OPEN", 100),
        )
        sql = (
            "INSERT INTO notification_jobs(job_id,alert_id,home_id,recipient_id,stage,due_at,state,idempotency_key) "
            "VALUES(?,?,?,?,?,?,?,?)"
        )
        self.db.execute(sql, ("j1", "a1", "h1", "c1", 0, 100, "PROVIDER_ACCEPTED", "notify:a1:c1:0"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(sql, ("j2", "a1", "h1", "c1", 0, 100, "PROVIDER_ACCEPTED", "notify:a1:c1:0"))
        # Provider acceptance did not mutate the human incident state.
        state = self.db.execute("SELECT state FROM alerts WHERE alert_id='a1'").fetchone()[0]
        self.assertEqual(state, "OPEN")

    def test_battery_analytics_schema_persists_calibration_and_usage(self) -> None:
        self.db.execute(
            "INSERT INTO battery_power_profiles(device_id,usable_capacity_mah,reserve_percent,sleep_current_ma,"
            "awake_base_current_ma,sensor_extra_current_ma,radio_tx_extra_current_ma,radio_rx_extra_current_ma,"
            "high_drain_ratio,calibration_source,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("n1", 2700.0, 8.0, 0.2, 18.0, 0.8, 70.0, 45.0, 1.75, "BENCH_MEASURED", 10),
        )
        self.db.execute(
            "INSERT INTO battery_usage_history(home_id,device_id,sampled_at,battery_mv,deep_sleep_ms,awake_ms,"
            "sensor_active_ms,radio_tx_ms,radio_rx_ms,estimated_percent,estimated_daily_mah,"
            "estimated_remaining_days,confidence,drain_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("h1", "n1", 100, 3920, 86000000, 400000, 100000, 10000, 10000, 68, 6.2, 250.0, "HIGH", "NORMAL"),
        )
        row = self.db.execute(
            "SELECT estimated_percent,confidence,drain_status FROM battery_usage_history WHERE device_id='n1'"
        ).fetchone()
        self.assertEqual(row, (68, "HIGH", "NORMAL"))

    def test_device_health_is_not_resident_activity(self) -> None:
        self.db.execute(
            "INSERT INTO device_health_history(home_id,device_type,device_id,sampled_at,status,error_code) "
            "VALUES(?,?,?,?,?,?)",
            ("h1", "NODE", "n-offline", 100, "OFFLINE", "GS-N003"),
        )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
