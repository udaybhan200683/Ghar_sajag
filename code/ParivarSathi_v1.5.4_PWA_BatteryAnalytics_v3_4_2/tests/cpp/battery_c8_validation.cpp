#include "gs/protocol.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "power/power.hpp"
#include "sensing/sensing.hpp"
#include "firmware/node/target/esp32c3/physical_wake_capability.hpp"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int checks = 0;

void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

gs::node::LightSleepObservation healthy_idle() {
    gs::node::LightSleepObservation value;
    value.now_ms = 1000;
    value.next_health_ms = 121000;
    value.authenticated = true;
    value.product_ready = true;
    value.persistence_clean = true;
    value.pir_high = false;
    value.pir_low_stable = true;
    value.debounce_safe = true;
    value.wake_source_ready = true;
    value.runtime_state_known = true;
    return value;
}

void test_physical_wake_profile() {
    using gs::node::target::physical_wake_permitted;
    check(physical_wake_permitted(false, false, false),
          "ordinary production retains physical wake permission");
    check(!physical_wake_permitted(true, true, false) &&
          !physical_wake_permitted(true, true, true),
          "synthetic raw HIL build cannot receive physical wake permission");
    check(!physical_wake_permitted(false, true, false),
          "existing HIL-control images remain awake");
    check(physical_wake_permitted(false, true, true),
          "explicit HIL-control physical qualification permits real wake");
    auto observation = healthy_idle();
    observation.wake_source_ready = false;
    check(!evaluate_light_sleep(observation).eligible,
          "security controls alone do not grant sleep eligibility");
}

void test_health_timing_profiles() {
    using namespace gs;
    using namespace gs::node;
    using gs::node::target::initial_node_health_deadline;
    constexpr Milliseconds now = 5000;
    constexpr Milliseconds interval =
        static_cast<Milliseconds>(NodeProtocolPolicy::heartbeat_seconds) * 1000;
    check(initial_node_health_deadline(now, interval, false, false) == 305000,
          "ordinary production first health remains 300 seconds after owner start");
    check(initial_node_health_deadline(now, interval, true, false) == 1000,
          "ordinary HIL control retains its absolute early first health deadline");
    check(initial_node_health_deadline(now, interval, true, true) == 305000,
          "physical wake HIL profile uses ordinary battery first health deadline");
    NodeHealthCadence battery(interval,
        initial_node_health_deadline(now, interval, true, true));
    check(!battery.due(304999, false, false, false, false) &&
          battery.due(305000, false, false, false, false),
          "physical wake quiet health opportunity remains at 300 seconds");
    battery.observe_health_attempt(305000);
    check(battery.next_due_ms() == 605000,
          "repeated physical wake NodeHealth remains on the product interval");
    battery.observe_authenticated_contact(150000);
    check(battery.next_due_ms() == 450000,
          "authenticated application contact defers quiet health normally");
    auto deadline = healthy_idle();
    deadline.next_health_ms = 4000;
    const auto health_bounded = evaluate_light_sleep(deadline);
    check(health_bounded.eligible && health_bounded.earliest_deadline_ms == 4000 &&
          health_bounded.requested_sleep_ms == 2500,
          "health deadline still bounds physical sleep");
    deadline.next_retry_ms = 2000;
    const auto retry_bounded = evaluate_light_sleep(deadline);
    check(retry_bounded.eligible && retry_bounded.earliest_deadline_ms == 2000 &&
          retry_bounded.requested_sleep_ms == 500,
          "earlier retry deadline still bounds physical sleep");
    check(NodeProtocolPolicy::offline_after_seconds == 910 &&
          NodeProtocolPolicy::coverage_after_seconds == 190,
          "Hub lease and historical coverage contracts remain independent");
}

void test_sleep_eligibility_and_inhibitors() {
    using namespace gs::node;
    const auto eligible = evaluate_light_sleep(healthy_idle());
    check(eligible.eligible && eligible.inhibitors == LightSleepInhibitNone,
          "authenticated stable idle can sleep");
    check(eligible.earliest_deadline_ms == 121000 &&
          eligible.requested_sleep_ms == kLightSleepMaximumMs,
          "sleep is capped and bounded by the earliest health deadline");

    struct Case {
        const char* name;
        std::uint32_t inhibitor;
        void (*set)(LightSleepObservation&);
    };
    const std::vector<Case> cases{
        {"invalid clock", LightSleepInhibitClock, [](auto& o) { o.now_ms = -1; }},
        {"authentication", LightSleepInhibitAuthentication, [](auto& o) { o.authenticated = false; }},
        {"rejoin", LightSleepInhibitRejoin, [](auto& o) { o.rejoin_active = true; }},
        {"product readiness", LightSleepInhibitProductNotReady, [](auto& o) { o.product_ready = false; }},
        {"pending transmission", LightSleepInhibitPendingTx, [](auto& o) { o.pending_tx = true; }},
        {"in-flight event", LightSleepInhibitEventInFlight, [](auto& o) { o.event_in_flight = true; }},
        {"application ACK wait", LightSleepInhibitAckWait, [](auto& o) { o.ack_wait = true; }},
        {"due retry", LightSleepInhibitRetryDue, [](auto& o) { o.retry_due = true; }},
        {"retained recovery", LightSleepInhibitRecoveryWork, [](auto& o) { o.recovery_work = true; }},
        {"persistence state", LightSleepInhibitPersistence, [](auto& o) { o.persistence_clean = false; }},
        {"FOTA", LightSleepInhibitFota, [](auto& o) { o.fota_active = true; }},
        {"boot health", LightSleepInhibitBootHealth, [](auto& o) { o.boot_health_active = true; }},
        {"maintenance", LightSleepInhibitMaintenance, [](auto& o) { o.maintenance_active = true; }},
        {"due health", LightSleepInhibitHealthDue, [](auto& o) { o.health_due = true; }},
        {"security work", LightSleepInhibitSecurityDue, [](auto& o) { o.security_due = true; }},
        {"PIR high", LightSleepInhibitPirHigh, [](auto& o) { o.pir_high = true; }},
        {"unstable PIR", LightSleepInhibitPirUnstable, [](auto& o) { o.pir_low_stable = false; }},
        {"unsafe debounce", LightSleepInhibitDebounce, [](auto& o) { o.debounce_safe = false; }},
        {"GPIO wake unavailable", LightSleepInhibitWakeUnavailable, [](auto& o) { o.wake_source_ready = false; }},
        {"unknown runtime", LightSleepInhibitRuntimeUnknown, [](auto& o) { o.runtime_state_known = false; }},
        {"other owner work", LightSleepInhibitOtherOwnerWork, [](auto& o) { o.other_owner_work = true; }},
        {"outage", LightSleepInhibitOutage, [](auto& o) { o.outage_active = true; }}
    };
    for (const auto& item : cases) {
        auto observation = healthy_idle();
        item.set(observation);
        const auto decision = evaluate_light_sleep(observation);
        check(!decision.eligible && decision.requested_sleep_ms == 0 &&
              (decision.inhibitors & item.inhibitor) != 0,
              std::string(item.name) + " inhibits sleep and fails awake");
    }

    auto deadlines = healthy_idle();
    deadlines.next_retry_ms = 50000;
    deadlines.next_maintenance_ms = 60000;
    deadlines.next_security_ms = 70000;
    const auto earliest = evaluate_light_sleep(deadlines);
    check(earliest.eligible && earliest.earliest_deadline_ms == 50000 &&
          earliest.requested_sleep_ms == 30000,
          "earliest of health, retry, maintenance and security deadlines wins");
    deadlines.next_retry_ms = 1000;
    const auto due = evaluate_light_sleep(deadlines);
    check(!due.eligible && (due.inhibitors & LightSleepInhibitRetryDue) != 0,
          "a retry at the current time inhibits sleep");
    deadlines = healthy_idle();
    deadlines.next_health_ms = 1900;
    const auto short_window = evaluate_light_sleep(deadlines);
    check(!short_window.eligible && short_window.requested_sleep_ms == 0 &&
          (short_window.inhibitors & LightSleepInhibitShortWindow) != 0,
          "a window consumed by the 500 ms margin remains awake");
    deadlines.next_health_ms = 310000;
    const auto cap = evaluate_light_sleep(deadlines);
    check(cap.eligible && cap.requested_sleep_ms == kLightSleepMaximumMs,
          "a distant deadline cannot exceed the 30 s owner recheck cap");
}

void test_pir_wake_handoff_and_timer_wake() {
    using namespace gs;
    node::QualifiedInput pir(EventKind::Motion, std::nullopt, 150, 1000);
    check(!pir.sample(false, 0), "initial LOW is a baseline, not an event");
    check(pir.safe_for_sleep(150), "stable LOW after existing debounce is sleep safe");
    check(!pir.sample(true, 200), "GPIO wake HIGH begins normal debounce");
    const auto first_motion = pir.sample(true, 350);
    check(first_motion == EventKind::Motion,
          "wake-causing HIGH becomes the first normal Motion observation");
    check(!pir.sample(true, 351), "held HIGH does not fabricate another event");
    check(!pir.safe_for_sleep(351), "lingering HIGH cannot immediately re-enter sleep");

    node::QualifiedInput timer_pir(EventKind::Motion, std::nullopt, 150, 1000);
    check(!timer_pir.sample(false, 0), "timer fixture starts with a LOW baseline");
    check(!timer_pir.sample(false, 300), "timer wake at LOW does not fabricate Motion");
}

void test_qualification_diagnostics() {
    using namespace gs::node;
    const auto idle = healthy_idle();
    const auto before = evaluate_light_sleep(idle);
    check(std::string(light_sleep_wake_name(classify_light_sleep_wake(true, false))) == "GPIO",
          "GPIO wake has a production log label");
    check(std::string(light_sleep_wake_name(classify_light_sleep_wake(false, true))) == "TIMER",
          "timer wake has a production log label");
    check(std::string(light_sleep_wake_name(classify_light_sleep_wake(false, false))) == "OTHER",
          "unknown wake has a production log label");
    check(classify_light_sleep_wake(true, true) == LightSleepWakeKind::Gpio,
          "GPIO is retained when multiple wake bits are set");

    LightSleepTelemetry telemetry;
    check(telemetry.light_sleep_entry_count == 0 &&
          telemetry.timer_wake_count == 0 && telemetry.gpio_wake_count == 0 &&
          telemetry.other_wake_count == 0 &&
          telemetry.last_wake_cause == LightSleepWakeKind::Unknown,
          "RAM-only sleep counters start empty until real sleep instrumentation runs");
    telemetry.record_sleep_attempt(30000);
    check(telemetry.light_sleep_entry_count == 1 &&
          telemetry.last_sleep_requested_ms == 30000 &&
          telemetry.timer_wake_count == 0 && telemetry.gpio_wake_count == 0,
          "real sleep attempt records requested duration without fabricating a wake");
    telemetry.record_sleep_return(false, false, true, 7);
    check(telemetry.timer_wake_count == 0 && telemetry.gpio_wake_count == 0 &&
          telemetry.other_wake_count == 0,
          "failed light-sleep call does not count a wake source");
    telemetry.record_sleep_return(true, false, true, 30012);
    check(telemetry.timer_wake_count == 1 && telemetry.gpio_wake_count == 0 &&
          telemetry.other_wake_count == 0 &&
          telemetry.last_wake_cause == LightSleepWakeKind::Timer &&
          telemetry.last_sleep_elapsed_ms == 30012,
          "timer wake is counted after successful return with measured elapsed time");
    telemetry.record_sleep_attempt(12000);
    telemetry.record_sleep_return(true, true, false, 4500);
    check(telemetry.light_sleep_entry_count == 2 &&
          telemetry.gpio_wake_count == 1 && telemetry.timer_wake_count == 1 &&
          telemetry.last_wake_cause == LightSleepWakeKind::Gpio &&
          telemetry.last_sleep_requested_ms == 12000 &&
          telemetry.last_sleep_elapsed_ms == 4500,
          "GPIO wake retains the requested and elapsed durations");
    telemetry.record_sleep_attempt(8000);
    telemetry.record_sleep_return(true, false, false, 8001);
    check(telemetry.other_wake_count == 1 &&
          telemetry.last_wake_cause == LightSleepWakeKind::Other &&
          telemetry.last_sleep_elapsed_ms == 8001,
          "successful unclassified wake is counted as OTHER");

    check(std::string(light_sleep_deadline_name(idle, before.earliest_deadline_ms)) == "health",
          "limiting deadline is labeled");
    check(before.requested_sleep_ms == 30000 &&
          evaluate_light_sleep(idle).requested_sleep_ms == before.requested_sleep_ms,
          "diagnostic projection preserves the requested interval and eligibility");
}

void test_existing_health_and_motion_identity_contracts() {
    using namespace gs;
    using namespace gs::node;
    NodeHealthCadence health(120000, 120000);
    check(health.due(120000, false, false, false, false),
          "quiet NodeHealth remains due at 120 seconds");
    health.observe_authenticated_contact(1000);
    check(health.next_due_ms() == 121000,
          "authenticated application contact alone defers health");
    check(NodeProtocolPolicy::offline_after_seconds == 910 &&
          NodeProtocolPolicy::coverage_after_seconds == 190 &&
          NodeProtocolPolicy::heartbeat_seconds == 300,
          "300 s configured health, 910 s Node liveness and historical 190 s coverage default are distinct");

    ActivityEpisode episode;
    check(episode.needs_first("room", 1000, false), "new motion episode needs first event");
    episode.note_first("room", 1000, false);
    check(!episode.needs_first("room", 2000, false), "repeat remains in the same episode");
    episode.note_repeat(2000);
    episode.poll(47000, false);
    check(episode.pending() && episode.pending()->aggregate.additional_count == 1,
          "compatible repeated motion remains an independent summary aggregate");

    NodeRuntime runtime("c8-node", 4, 8, 8);
    const auto first = runtime.record(EventKind::Motion, "room", 1000, 0);
    const auto summary = runtime.record(EventKind::MotionSummary, "room", 47000, 0,
        86400, 0, false, SensorType::Pir, 0, episode.pending()->aggregate);
    check(first && summary && first->sequence != summary->sequence,
          "first motion and MotionSummary retain independent immutable identities");
}

void test_fresh_critical_work_keeps_existing_retry_priority() {
    using namespace gs;
    node::NodeRuntime runtime("c8-priority", 8, 8, 8);
    const auto old_motion = runtime.record(EventKind::Motion, "room", 0, 0);
    check(old_motion.has_value(), "first motion is admitted before outage retry");
    const auto first = runtime.next_message(0);
    check(first && first->sequence_number == old_motion->sequence,
          "first meaningful motion keeps its immediate normal opportunity");
    runtime.transport_result(*old_motion, false, 0);
    runtime.set_outage_profile(true, 1);
    const auto critical = runtime.record(EventKind::DoorOpen, "entry", 10, 0);
    const auto next = runtime.next_message(10);
    check(critical && next && next->sequence_number == critical->sequence,
          "fresh critical work retains BAT-C4 priority over delayed motion retry");
}

}  // namespace

int main() {
    try {
        test_physical_wake_profile();
        test_health_timing_profiles();
        test_sleep_eligibility_and_inhibitors();
        test_pir_wake_handoff_and_timer_wake();
        test_qualification_diagnostics();
        test_existing_health_and_motion_identity_contracts();
        test_fresh_critical_work_keeps_existing_retry_priority();
        std::cout << "BAT-C8 focused validation PASS checks=" << checks << '\n';
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "BAT-C8 focused validation FAIL: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
