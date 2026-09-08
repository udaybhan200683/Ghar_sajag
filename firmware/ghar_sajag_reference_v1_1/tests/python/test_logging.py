from pathlib import Path
import tempfile
import unittest

from ghar_sajag import logging_config as logs


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
