"""Compile and exercise the actual target functions against bounded host mocks."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def between(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


class RadioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = (ROOT / "firmware/node/target/esp32c3/node_runtime_adapter.cpp").read_text()
        hub = (ROOT / "firmware/hub/target/esp32/hub_runtime_adapter.cpp").read_text()
        cls.source = (ROOT / "tests/support/host/gs117_diagnostics_probe.cpp.in").read_text()
        fragments = {
            "SEND_RESULT": between(node, "// Evidence-only instrumentation", "StaticQueue_t g_ack_queue_state"),
            "RX_DIAG_TYPES": between(hub, "constexpr UBaseType_t kGs117ReceiveDiagnosticQueueDepth", "StaticQueue_t g_gs117_receive_diagnostic_queue_state"),
            "RX_DIAGNOSTICS": between(hub, "void queue_gs117_receive_diagnostic", "#if ESP_IDF_VERSION_MAJOR >= 6\nvoid send_callback"),
            "CALLBACK": between(node, "#if ESP_IDF_VERSION_MAJOR >= 6\nvoid send_callback", "esp_err_t initialize_gpio"),
            "SECURITY_SEND": between(node, "bool send_security_message(", "bool send_rejoin_message("),
            "REJOIN": between(node, "bool send_rejoin_message(", "\n#endif\n\nvoid owner_task"),
            "HUB_RECEIVE": between(hub, "#if defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) && GS40_TEST_ONLY_CLOUDSYNC_BUILD\nconst char* gs117_receive_stage_name", "\nvoid secure_owner_task"),
            "PEER": between(hub, "esp_err_t add_runtime_peer(", "bool send_security_message("),
            "OWNER_LOOP": between(hub, "    for (const auto& mac : security_link.enrolled_macs())", "    // Recover the durable owner"),
        }
        for key, value in fragments.items():
            cls.source = cls.source.replace("@" + key + "@", value)

    def compile_run(self, source, *, sdk=6, diagnostic=True, extra_flags=()):
        with tempfile.TemporaryDirectory(prefix="gs117-radio-host-") as directory:
            code, binary = Path(directory) / "probe.cpp", Path(directory) / "probe"
            code.write_text(source)
            command = ["g++", "-B/usr/bin", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                       "-I.",
                       *extra_flags,
                       "-DGS_HIL_CONTROL=" + str(int(diagnostic)), "-DGS_HIL_BUILD=0",
                       "-DGS_BAT_C8_PHYSICAL_WAKE=0", "-DGS40_TEST_ONLY_CLOUDSYNC_BUILD=" + str(int(diagnostic)),
                       "-DESP_IDF_VERSION_MAJOR=" + str(sdk),
                       str(code), "firmware/common/security/commissioning_wire.cpp", "-o", str(binary)]
            compile_result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            return subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)

    def test_target_send_callback_and_owner_paths_sdk6(self):
        """GS117-DIAG-TX: stage/callback/peer/timeout/owner integration, no radio."""
        result = self.compile_run(self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"GS117 RADIO DIAGNOSTICS checks=[1-9][0-9]* PASS")
        print(result.stdout.strip())

    def test_legacy_callback_and_production_profile_keep_transport_behavior(self):
        for sdk, diagnostic in ((5, True), (6, False)):
            with self.subTest(sdk=sdk, diagnostic=diagnostic):
                result = self.compile_run(self.source, sdk=sdk, diagnostic=diagnostic)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_owner_predicate_fails_at_the_real_caller(self):
        """The registered regression must detect the actual70d577e defect."""
        original = self.source.replace("if (add_runtime_peer(mac) != ESP_OK)",
                                       "if (!add_runtime_peer(mac))")
        self.assertNotEqual(original, self.source)
        result = self.compile_run(original)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("owner_existing_peer", result.stderr)

    def test_target_receive_and_send_boundaries_under_address_undefined_sanitizers(self):
        result = self.compile_run(
            self.source,
            extra_flags=("-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                         "-fno-sanitize-recover=all", "-pthread"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"GS117 RADIO DIAGNOSTICS checks=[1-9][0-9]* PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
