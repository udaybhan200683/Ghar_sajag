from __future__ import annotations

import sqlite3
import unittest

from ghar_sajag.database import REQUIRED_TABLES, initialize_sqlite, table_names


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
