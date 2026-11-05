"""Production collector tests; fake ports/clocks only, never calls serial.Serial."""
from datetime import datetime, timezone
import ast
import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/local"))
import gs117_tc001_serial_windows as serial_tool
import gs117_bootstrap_evidence as evidence


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Stream:
    def __init__(self, clock):
        self.clock = clock
        self.port = ""
        self.is_open = False
        self.data = bytearray()
        self.reads = []
        self.writes = []
        self.write_delay = 0.0
        self.raise_at_read = None
        self.read_error = None

    @property
    def in_waiting(self):
        return len(self.data)

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False
        self.clock.sleep(0.25)  # Cleanup is separately timed, never reads UART.

    def read(self, count):
        self.reads.append((self.clock(), count, self.timeout))
        if len(self.reads) == self.raise_at_read:
            raise self.read_error
        self.clock.sleep(min(0.1, self.timeout))
        result = bytes(self.data[:count])
        del self.data[:count]
        return result

    def write(self, value):
        self.writes.append((self.clock(), value, self.write_timeout))
        self.clock.sleep(min(self.write_delay, self.write_timeout))
        self.data.extend(b"I (100) HIL_STATE role=c3 session=1 runtime_live=0 sensing_live=0\n")
        return len(value)


class CollectionTests(unittest.TestCase):
    def run_observation(self, *, bootstrap_seconds=0, configure=None):
        clock = Clock()
        streams = [Stream(clock), Stream(clock)]
        boards = [{"port": "COM4", "serial_number": "14:63:93:C5:D1:58", "usb_hwid": "fake-c3"},
                  {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34", "usb_hwid": "fake-s3"}]
        if configure:
            configure(streams, clock)

        def bootstrap(*_args, **_kwargs):
            clock.sleep(bootstrap_seconds)
            return 7323

        result = serial_tool.observe(
            {"c3": boards[0], "s3": boards[1], "profile": "GS117_DEV_TEST_ONLY",
             "observation_seconds": 90, "c3_status_interval_seconds": 10},
            serial_factory=iter(streams).__next__, port_finder=lambda: boards,
            clock=clock, sleep=clock.sleep, wall_clock=lambda: 1000 + clock(),
            bootstrap_exchange=bootstrap if bootstrap_seconds else None)
        return result, streams, clock

    def assert_bounded(self, result, streams):
        timing = result["phase_timing"]
        self.assertAlmostEqual(timing["observation_elapsed_ms"], 90000, places=5)
        self.assertEqual(timing["termination_reason"], "deadline")
        self.assertAlmostEqual(timing["cleanup_elapsed_ms"], 500)
        deadline = timing["observation_deadline_monotonic"]
        for stream in streams:
            self.assertFalse(stream.is_open)
            self.assertTrue(all(at < deadline and at + timeout <= deadline + 1e-8
                                for at, _, timeout in stream.reads))
            self.assertTrue(all(at < deadline and at + timeout <= deadline + 1e-8
                                for at, _, timeout in stream.writes))
            self.assertTrue(all(value == b"GET_STATE\n" for _, value, _ in stream.writes))

    def test_readiness_budget_above_ninety_is_rejected_before_open(self):
        with self.assertRaisesRegex(ValueError, "OBSERVATION_SECONDS_OUT_OF_RANGE"):
            serial_tool.observe({"c3": {}, "s3": {}, "profile": "GS117_DEV_TEST_ONLY",
                                 "observation_seconds": 91},
                                serial_factory=lambda: self.fail("must not open"))

    def test_plain_observation_has_one_deadline_and_nine_samples(self):
        result, streams, _ = self.run_observation()
        self.assert_bounded(result, streams)
        self.assertEqual(result["c3_status_queries"], 9)

    def test_bootstrap_never_adds_a_second_observation_or_drain(self):
        result, streams, clock = self.run_observation(bootstrap_seconds=17)
        self.assert_bounded(result, streams)
        self.assertEqual(result["phase_timing"]["bootstrap_elapsed_ms"], 17000)
        self.assertEqual(result["phase_timing"]["observation_start_monotonic"], 17)
        self.assertAlmostEqual(clock(), 107.5)
        self.assertEqual(result["c3_status_queries"], 9)

    def test_slow_io_collects_only_the_queries_that_fit(self):
        result, streams, _ = self.run_observation(
            configure=lambda streams, clock: setattr(streams[1], "write_delay", 1))
        self.assert_bounded(result, streams)
        self.assertLess(result["c3_status_queries"], 9)
        self.assertGreater(result["c3_status_queries"], 0)

    def test_exception_timeout_and_cancellation_retain_partial_evidence(self):
        for error in (TimeoutError("mock read timeout"), RuntimeError("mock driver"), KeyboardInterrupt()):
            streams_saved = []

            def configure(streams, clock):
                streams_saved.extend(streams)
                streams[0].data.extend(b"E (12) task_wdt: Tasks currently running:\n")
                streams[0].raise_at_read = 4
                streams[0].read_error = error

            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)) as raised:
                self.run_observation(configure=configure)
            partial = raised.exception.captured_observation
            self.assertIn("Tasks currently running", partial["s3"][0])
            self.assertEqual(partial["phase_timing"]["termination_reason"], type(error).__name__)
            self.assertTrue(all(not stream.is_open for stream in streams_saved))
            self.assertGreater(partial["phase_timing"]["cleanup_elapsed_ms"], 0)
            self.assertTrue(partial["serial_capture"]["s3"]["records"])

    def test_broken_driver_overrun_is_reported_and_never_collected(self):
        clock = Clock()
        stream = Stream(clock)

        def broken_read(count):
            clock.sleep(91)
            return b"HIL_STATE outside_budget=1\n"

        stream.read = broken_read
        lines, capture = [], serial_tool.capture_state()
        serial_tool.collect(stream, "", lines, capture=capture, deadline=90, clock=clock)
        self.assertEqual(lines, [])
        self.assertGreater(capture["late_read_bytes"], 0)
        self.assertEqual(capture["deadline_overruns"], 1)

    def test_empty_driver_overrun_also_fails_closed(self):
        handles = []

        def configure(streams, clock):
            handles.extend(streams)

            def empty_late_read(_count):
                clock.sleep(91)
                return b""

            streams[1].read = empty_late_read

        with self.assertRaisesRegex(ValueError, "READ_EXCEEDED_OBSERVATION_DEADLINE") as raised:
            self.run_observation(configure=configure)
        capture = raised.exception.captured_observation["serial_capture"]["c3"]
        self.assertEqual(capture["late_read_bytes"], 0)
        self.assertEqual(capture["deadline_overruns"], 1)
        self.assertTrue(all(not stream.is_open for stream in handles))
        self.assertEqual(handles[0].reads, [])  # No S3 collection after the overrun.

    def test_unterminated_final_line_loss_is_visible_without_leaking_its_text(self):
        def configure(streams, _clock):
            streams[0].data.extend(b"E (30) task_wdt: secret=DO_NOT_PERSIST")

        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_CAPTURE_INCOMPLETE") as raised:
            self.run_observation(configure=configure)
        partial = raised.exception.captured_observation
        self.assertGreater(partial["serial_capture"]["s3"]["unterminated_tail_chars"], 0)
        self.assertNotIn("DO_NOT_PERSIST", json.dumps(partial))

    def test_cleanup_error_still_closes_the_other_handle(self):
        handles = []

        def configure(streams, clock):
            handles.extend(streams)

            def close_error():
                streams[1].is_open = False
                raise OSError("mock close failure")

            streams[1].close = close_error

        with self.assertRaisesRegex(ValueError, "SERIAL_CLEANUP_FAILED") as raised:
            self.run_observation(configure=configure)
        self.assertTrue(all(not stream.is_open for stream in handles))
        self.assertEqual(raised.exception.captured_observation["phase_timing"]["cleanup_errors"], 1)

    def test_cli_cooperative_cancellation_emits_bounded_partial_response(self):
        # Execute the actual CLI branch with a raising observe stub; never open
        # a port or call the authorization framework.
        source = Path(serial_tool.__file__).read_text()
        entry = ast.parse(source).body[-1]
        self.assertIsInstance(entry, ast.If)
        namespace = dict(vars(serial_tool))

        def interrupted(_config):
            error = KeyboardInterrupt()
            error.captured_observation = {"s3": ["E task_wdt: CPU 1: worker"]}
            raise error

        namespace["observe"] = interrupted
        output = io.StringIO()
        args = ["helper", base64.b64encode(b'{"action":"Observe"}').decode()]
        with patch.object(sys, "argv", args), redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            exec(compile(ast.Module(body=entry.body, type_ignores=[]), "collector-cli", "exec"), namespace)
        self.assertEqual(raised.exception.code, 2)
        response = json.loads(output.getvalue())
        self.assertEqual(response["error"], "KeyboardInterrupt")
        self.assertIn("CPU 1", response["observation"]["s3"][0])

    def collect_text(self, text, capture=None, clock=None):
        clock = clock or Clock()
        stream = Stream(clock)
        stream.timeout = 0
        stream.data.extend(text.encode())
        lines, pending = [], ""
        capture = capture if capture is not None else serial_tool.capture_state()
        while stream.in_waiting:
            pending = serial_tool.collect(stream, pending, lines, capture=capture,
                                           clock=clock, wall_clock=lambda: 1234.5)
        return lines, capture

    def test_twdt_headings_tasks_and_frames_keep_order_and_timestamps(self):
        text = ("E (85936) task_wdt: Task watchdog got triggered.\n"
                "E (85936) task_wdt: The following tasks/users did not reset the watchdog in time:\n"
                "E (85936) task_wdt:  - IDLE1 (CPU 1)\n"
                "E (85936) task_wdt: Tasks currently running:\n"
                "E (85936) task_wdt: CPU 1: gs_hub_cloud_health\n"
                "E (85936) task_wdt: Print CPU 1 backtrace\n"
                "Backtrace: 0x4037775A:0x3FC9A160 0x4200D926:0x3FCD5810\n")
        lines, capture = self.collect_text(text)
        self.assertEqual(lines, text.splitlines())
        self.assertEqual([v["line_index"] for v in capture["records"]], list(range(7)))
        self.assertEqual(capture["records"][0]["target_uptime_ms"], 85936)
        self.assertEqual(capture["records"][0]["host_received_at"],
                         datetime.fromtimestamp(1234.5, timezone.utc).isoformat())
        self.assertIsNone(capture["records"][-1]["target_uptime_ms"])

    def test_boot_epochs_are_evidence_markers_not_cross_device_clocks(self):
        lines, capture = self.collect_text("ESP-ROM:esp32s3\nI (2) app_init: App version: one\n"
                                           "E (30) task_wdt: CPU 1: worker\n"
                                           "ESP-ROM:esp32s3\nI (2) app_init: App version: two\n")
        self.assertEqual([v["boot_epoch"] for v in capture["records"]], [1, 1, 1, 2, 2])
        self.assertEqual(len(capture["boot_markers"]), 2)
        self.assertIn("version: one", lines[1])
        self.assertIn("version: two", lines[-1])

    def test_line_and_chunk_limits_report_loss_and_redact_secrets(self):
        lines, capture = self.collect_text("\n".join(
            "E task_wdt: CPU 1: worker password='two word secret' payload=AUTH_BYTES " + "x" * 1100
            for _ in range(305)) + "\n")
        self.assertEqual(len(lines), 300)
        self.assertEqual(len(capture["records"]), 300)
        self.assertEqual(capture["dropped_lines"], 5)
        self.assertGreater(capture["truncated_chars"], 0)
        self.assertNotIn("secret", "\n".join(lines))
        self.assertNotIn("AUTH_BYTES", "\n".join(lines))
        self.assertTrue(all(len(line) <= 1024 for line in lines))

    def test_overlong_partial_line_cannot_leak_secret_suffix(self):
        lines, capture = self.collect_text("password=" + "S" * 9000 +
                                           " task_wdt: secret_suffix\nHIL_STATE safe=1\n")
        self.assertEqual(lines, ["HIL_STATE safe=1"])
        self.assertGreater(capture["pending_truncated_chars"], 0)

    def test_incomplete_capture_cannot_return_successful_observation(self):
        handles = []

        def configure(streams, clock):
            handles.extend(streams)
            streams[0].data.extend(b"E task_wdt: CPU 1: worker\n" * 305)

        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_CAPTURE_INCOMPLETE") as raised:
            self.run_observation(configure=configure)
        partial = raised.exception.captured_observation
        self.assertEqual(partial["serial_capture"]["s3"]["dropped_lines"], 5)
        self.assertEqual(len(partial["s3"]), 300)
        self.assertTrue(all(not stream.is_open for stream in handles))

    def test_new_metadata_survives_parent_redaction_with_strict_bounds(self):
        result, _, _ = self.run_observation(bootstrap_seconds=2)
        result["serial_capture"]["s3"]["private_key"] = "must-drop"
        result["phase_timing"]["payload"] = "must-drop"
        safe = evidence._safe_response(json.dumps(result))
        self.assertEqual(safe["phase_timing"]["observation_budget_ms"], 90000)
        self.assertEqual(len(safe["serial_capture"]["c3"]["records"]), 9)
        self.assertNotIn("must-drop", json.dumps(safe))
        self.assertNotIn("private_key", safe["serial_capture"]["s3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
