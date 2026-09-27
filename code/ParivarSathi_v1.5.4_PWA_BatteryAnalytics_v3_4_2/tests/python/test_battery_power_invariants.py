from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
NODE = ROOT / "firmware/node"
ADAPTER = NODE / "target/esp32c3/node_runtime_adapter.cpp"


class BatteryPowerInvariantTest(unittest.TestCase):
    def test_authenticated_application_ack_restores_outage_profile(self):
        source = ADAPTER.read_text()
        ack_start = source.index("const bool matched_pending = runtime.has_pending_key(key)")
        ack_end = source.index("breadcrumb = retired", ack_start)
        ack_path = source[ack_start:ack_end]

        self.assertIn("const bool retired = runtime.acknowledge(key, decoded.value->ack_type)", ack_path)
        self.assertIn("if (matched_pending) health_cadence.observe_authenticated_contact(now)", ack_path)
        self.assertIn("if (retired)", ack_path)
        self.assertIn("power_policy.observe_authenticated_contact()", ack_path)
        self.assertIn("runtime.set_outage_profile(false, now)", ack_path)
        self.assertIn("security_link.persist_recovery(runtime)", ack_path)
        self.assertIn("runtime.pending() != pending_before", ack_path)
        self.assertIn("runtime.persisted() != retained_before", ack_path)

        outage_test = (ROOT / "tests/cpp/test_main.cpp").read_text()
        outage_start = outage_test.index("void test_node_outage_profile()")
        outage_end = outage_test.index("void test_data_plane_codec_and_ack_policy()", outage_start)
        recovery_test = outage_test[outage_start:outage_end]
        for invariant in (
            "volatile ACK cannot retire durable outage evidence",
            "authenticated recovery clears outage and schedules retained work",
            "matching durable ACKs retire the original event identities",
        ):
            self.assertIn(invariant, recovery_test)

    def test_policy_and_retry_paths_do_not_add_nvs_writes(self):
        power_header = (NODE / "components/power/power.hpp").read_text()
        power_source = (NODE / "components/power/power.cpp").read_text()
        adapter = ADAPTER.read_text()

        self.assertNotRegex(power_header + power_source, r"\b(nvs_|persist_recovery|nvs_commit)")
        retry_start = adapter.index("SendResult send_result;")
        retry_end = adapter.index("const bool maintenance =", retry_start)
        retry_path = adapter[retry_start:retry_end]
        self.assertIn("power_policy.observe_unacknowledged_attempt()", retry_path)
        self.assertIn("runtime.set_outage_profile(true, now)", retry_path)
        self.assertNotIn("persist_recovery", retry_path)

        counters_start = adapter.index("energy.record_sensing_loop(")
        counters_end = adapter.index("vTaskDelay(pdMS_TO_TICKS(kPirPollMs))", counters_start)
        counter_update_path = adapter[counters_start:counters_end]
        self.assertNotIn("persist_recovery", counter_update_path)

        # Durable writes remain on product recovery boundaries: event admission,
        # a newly required gap marker, and changed ACK-retirement state.
        self.assertIn("// Commit the event and its retry identity before any", adapter)
        self.assertIn("Node recovery ACK retirement commit failed", adapter)

    def test_energy_counters_are_owner_local_and_not_new_wire_telemetry(self):
        power_header = (NODE / "components/power/power.hpp").read_text()
        adapter = ADAPTER.read_text()
        codec_header = (ROOT / "firmware/common/transport/data_plane_codec.hpp").read_text()
        codec_source = (ROOT / "firmware/common/transport/data_plane_codec.cpp").read_text()

        self.assertIn("struct EnergyCounters", power_header)
        self.assertIn("EnergyCounters energy;", adapter)
        self.assertNotIn("EnergyCounters", codec_header + codec_source)
        self.assertIn("NodeHealthCadence health_cadence", adapter)
        self.assertIn("NodeProtocolPolicy::heartbeat_seconds", adapter)
        self.assertIn("health_cadence.due(now, application_due", adapter)
        self.assertEqual(adapter.count("xTaskCreate("), 1)
        self.assertNotIn("esp_timer_create", adapter)
        self.assertNotIn("esp_timer_start", adapter)

    def test_light_sleep_is_owner_local_radio_quiescent_and_ram_only(self):
        adapter = ADAPTER.read_text()
        power = (NODE / "components/power/power.cpp").read_text()
        makefile = (ROOT / "Makefile").read_text()

        self.assertEqual(adapter.count("xTaskCreate("), 1)
        self.assertIn("LightSleepDecision evaluate_light_sleep", power)
        self.assertIn("esp_now_deinit()", adapter)
        self.assertIn("esp_wifi_stop()", adapter)
        self.assertIn("esp_sleep_enable_gpio_wakeup()", adapter)
        self.assertIn("GPIO_INTR_HIGH_LEVEL", adapter)
        self.assertIn("esp_sleep_enable_timer_wakeup", adapter)
        self.assertIn("esp_light_sleep_start()", adapter)
        self.assertIn("esp_sleep_get_wakeup_causes()", adapter)
        self.assertIn("gpio_get_level(static_cast<gpio_num_t>(kPirGpio)) != 0", adapter)
        self.assertIn("pir.sample(raw_pir, now)", adapter)
        self.assertIn("if (outcome.entered && outcome.error == ESP_OK)", adapter)
        self.assertIn("if (!returned_from_light_sleep) vTaskDelay(pdMS_TO_TICKS(kPirPollMs))", adapter)

        sleep_start = adapter.index("LightSleepReturn enter_light_sleep(")
        sleep_end = adapter.index("#if !GS_HIL_BUILD\nbool send_security_message", sleep_start)
        sleep_adapter = adapter[sleep_start:sleep_end]
        self.assertNotRegex(sleep_adapter, r"\b(nvs_|persist_recovery|nvs_commit)")
        self.assertIn("validation-fast:", makefile)
        self.assertIn("battery-c8-host-test", makefile)


if __name__ == "__main__":
    unittest.main()
