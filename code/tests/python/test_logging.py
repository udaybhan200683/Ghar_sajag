# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module S05 Diagnostics facade and sinks
# @requirements AI08, E10, NFR-05, NFR-09
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The atomic sink pointer only makes pointer publication atomic; it does not make sink lifetime or writes
# thread-safe. The host file sink performs synchronous I/O and rotation. Production should enqueue fixed
# records to one writer, reserve error capacity and expose drops; this future writer is not in the current
# source.

from pathlib import Path
import tempfile
import unittest

from ghar_sajag import logging_config as logs
from ghar_sajag.feature_flags import DEFAULTS, snapshot


class LoggingTest(unittest.TestCase):
    def setUp(self):
        for handler in list(logs._LOGGER.handlers):
            handler.close()
            logs._LOGGER.removeHandler(handler)

    def test_production_keeps_error_and_filters_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "production.txt"
            logs.configure_logging(str(path), trace_enabled=False)
            logs.trace("TEST", "T02", "trace.hidden")
            logs.error("TEST", "T02", "error.visible", "forced")
            text = path.read_text()
            self.assertIn("level=ERROR", text)
            self.assertNotIn("level=TRACE", text)

    def test_development_trace_records_flow(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "development.txt"
            logs.configure_logging(str(path), trace_enabled=True)
            logs.trace("TEST", "T02", "flow.enter")
            self.assertIn("level=TRACE", path.read_text())

    def test_feature_flags_are_safe_by_default(self):
        self.assertTrue(DEFAULTS["morning_routine"])
        self.assertFalse(DEFAULTS["fall_detection"])
        self.assertEqual(set(snapshot()), set(DEFAULTS))
