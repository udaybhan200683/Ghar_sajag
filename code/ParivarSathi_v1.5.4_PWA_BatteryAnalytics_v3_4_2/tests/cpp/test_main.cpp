// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module T01 Simulation/CI
// @requirements E08, E10, V01, AI01, AI03, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The Makefile builds host C++17 and runs Python/JavaScript tests plus simulator fixtures. Tests prove
// their asserted paths, not every SRD criterion. Keep a clean command transcript and attach additional
// scenario tests as requirements are integrated.

#include "cloud/cloud_sync.hpp"
#include "coverage/coverage.hpp"
#include "gs/rules.hpp"
#include "gs/protocol.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/common/transport/session_id.hpp"
#include "ingest/ingest.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "lifecycle/config_service.hpp"
#include "lifecycle/lifecycle.hpp"
#include "power/power.hpp"
#include "radio/node_radio.hpp"
#include "rules/routine_service.hpp"
#include "security.hpp"
#include "sensing/sensing.hpp"
#include "storage/journal.hpp"
#include "storage/node_store.hpp"
#include "time/clock.hpp"
#include "ui/resident_ui.hpp"
#include "host/logging/file_log_sink.hpp"
#include "gs/feature_flags.hpp"

#include <iostream>
#include <cstdlib>
#include <array>
#include <stdexcept>
#include <string>

namespace {

int checks = 0;

class CountingSink final : public gs::log::Sink {
public:
    // @requirements E08, E10, V01, AI01, AI03, NFR-08
    // Perform host file output synchronously; target firmware needs a single-owner bounded asynchronous
    // writer.
    void write(const char* record, std::size_t length) noexcept override {
        ++records;
        const std::string value(record, length);
        if (value.find("level=ERROR") != std::string::npos) ++errors;
        if (value.find("level=TRACE") != std::string::npos) ++traces;
    }
    int records{0}; int errors{0}; int traces{0};
};

void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

gs::DomainEvent event(std::uint64_t sequence, gs::EventKind kind, gs::EpochSeconds at,
                      const std::string& source = "node-1", const std::string& location = "kitchen") {
    return {{source, 7, sequence}, kind, location, at * 1000, at, at, 0, 3800, false};
}

class AcceptingVerifier final : public gs::SignatureVerifier {
public:
    bool verify(const std::string& payload, const std::string& signature) const override {
        return payload.find("esp32-c3") != std::string::npos && signature == "test-signature";
    }
};

class FakeSessionStore final : public gs::transport::SessionCounterStore {
public:
    bool load(std::uint64_t& value, bool& found) override {
        if (!load_ok) return false;
        value = persisted;
        found = has_value;
        return true;
    }

    bool save(std::uint64_t value) override {
        if (!save_ok) return false;
        persisted = value;
        has_value = true;
        return true;
    }

    std::uint64_t persisted{0};
    bool has_value{false};
    bool load_ok{true};
    bool save_ok{true};
};

void test_node_modules() {
    gs::node::QualifiedInput pir(gs::EventKind::Motion, std::nullopt, 25, 1000);
    check(!pir.sample(false, 0), "initial PIR sample must not emit");
    check(!pir.sample(true, 10), "edge must debounce");
    check(pir.sample(true, 40) == gs::EventKind::Motion, "stable PIR rise must emit motion");
    check(!pir.sample(false, 50), "PIR inactive edge has no business event");

    gs::node::NodeStore store(2);
    check(store.append(event(1, gs::EventKind::Motion, 100)), "business event persists");
    check(!store.acknowledge({"node-1", 7, 1}, gs::AckClass::ReceivedVolatile), "volatile ack cannot retire business event");
    check(store.acknowledge({"node-1", 7, 1}, gs::AckClass::Durable), "durable ack retires event");

    gs::node::NodeRadio radio(2);
    check(radio.enqueue(event(2, gs::EventKind::DoorOpen, 101), 0), "radio queue accepts event");
    check(radio.next_due(0).has_value(), "queued event is due immediately");
    check(!radio.apply_ack({"node-1", 7, 2}, gs::AckClass::ReceivedVolatile), "radio preserves business event on volatile ack");
    check(radio.apply_ack({"node-1", 7, 2}, gs::AckClass::Durable), "radio retires durable ack");

    gs::node::NodeRadio paced_radio(2);
    check(paced_radio.enqueue(event(10, gs::EventKind::DoorOpen, 101), 0) &&
          paced_radio.enqueue(event(11, gs::EventKind::DoorClosed, 102), 0),
          "paced radio admits bounded work");
    const auto paced_first = paced_radio.next_due(0);
    check(paced_first && paced_first->key.sequence == 10,
          "paced radio selects the first due identity");
    paced_radio.record_transport_result(paced_first->key, false, 0);
    check(!paced_radio.next_due(200),
          "global opportunity gate prevents retry bursts before backoff");
    const auto paced_second = paced_radio.next_due(400);
    check(paced_second && paced_second->key.sequence == 11,
          "round-robin retry selection prevents one identity monopolizing transport");

    gs::node::NodeRadio outage_motion_radio(4);
    const auto old_motion = event(20, gs::EventKind::Motion, 100);
    check(outage_motion_radio.enqueue(old_motion, 0), "outage motion retry is queued");
    const auto old_attempt = outage_motion_radio.next_due(0);
    check(old_attempt && old_attempt->key.sequence == 20,
          "outage motion retry starts immediately");
    outage_motion_radio.record_transport_result(old_attempt->key, false, 0);
    outage_motion_radio.set_outage_profile(true, 1000);
    outage_motion_radio.record_transport_result(old_attempt->key, false, 1000);
    const auto new_motion = event(21, gs::EventKind::Motion, 200);
    check(outage_motion_radio.enqueue(new_motion, 2000),
          "fresh activity is retained during confirmed outage");
    check(outage_motion_radio.next_due_at() == 2000,
          "power deadline wakes for the prompt fresh-motion opportunity");
    const auto prompt_motion = outage_motion_radio.next_due(2000);
    check(prompt_motion && prompt_motion->key.sequence == 21,
          "fresh motion gets a prompt first transmission despite the old retry gate");
    outage_motion_radio.record_transport_result(prompt_motion->key, false, 2000);
    const auto next_motion = event(22, gs::EventKind::Motion, 300);
    check(outage_motion_radio.enqueue(next_motion, 3000),
          "subsequent fresh activity remains bounded in outage");
    const auto next_prompt_ms = 62000U + ((21U * 37U) % 101U);
    check(!outage_motion_radio.next_due(next_prompt_ms - 1U),
          "new-motion opportunity remains rate limited while Hub is unavailable");
    const auto next_prompt = outage_motion_radio.next_due(next_prompt_ms);
    check(next_prompt && next_prompt->key.sequence == 22,
          "the next fresh motion receives the next bounded prompt opportunity");

    gs::node::LifecycleService lifecycle;
    check(!lifecycle.apply({1, "node-1", "kitchen", false, false, 60}).applied, "input-less config is rejected");
    check(lifecycle.apply({1, "node-1", "kitchen", true, false, 60}).applied, "valid node config applies");
    check(!lifecycle.apply({1, "node-1", "kitchen", true, false, 60}).applied, "stale version is rejected");
    lifecycle.open_service_window(1000);
    check(lifecycle.service_window_open(120000), "physical service window is bounded and open");
    check(!lifecycle.service_window_open(122000), "service window closes");

    gs::node::PowerPolicy power;
    check(power.classify(3500, true).band == gs::node::BatteryBand::Low, "calibrated low battery classification");
    check(power.classify(3500, false).band == gs::node::BatteryBand::Unknown, "uncalibrated voltage stays unknown");
    check(power.plan({1, "n", "room", true, false, 60}, true, gs::node::BatteryBand::Normal).wake_after_ms == 10000,
          "pending retry shortens wake interval");
    gs::node::PowerObservation power_input;
    power_input.now_ms = 100;
    power_input.next_health_ms = 60000;
    auto decision = power.evaluate(power_input);
    check(decision.state == gs::node::PowerRuntimeState::BootAuth &&
          !decision.future_sleep_eligible &&
          (decision.inhibitors & gs::node::PowerInhibitAuthentication) != 0,
          "power policy fails awake during authentication");
    power_input.authenticated = true;
    power_input.sensor_ready = true;
    power_input.sensor_safe = true;
    power_input.persistence_clean = true;
    decision = power.evaluate(power_input);
    check(decision.state == gs::node::PowerRuntimeState::ReadyIdle &&
          !decision.future_sleep_eligible &&
          (decision.inhibitors & gs::node::PowerInhibitWakeUnproven) != 0,
          "no proven wake path means no target sleep");
    power_input.wake_proven = true;
    power_input.next_retry_ms = 250;
    decision = power.evaluate(power_input);
    check(decision.future_sleep_eligible && decision.next_deadline_ms == 250,
          "future deadline selects earliest required work");
    power_input.maintenance = true;
    check((power.evaluate(power_input).inhibitors & gs::node::PowerInhibitMaintenance) != 0,
          "maintenance inhibits future sleep");
    power_input.maintenance = false;
    power_input.persistence_clean = false;
    check((power.evaluate(power_input).inhibitors & gs::node::PowerInhibitPersistence) != 0,
          "dirty recovery inhibits future sleep");
    power_input.persistence_clean = true;
    power_input.now_ms = 250;
    check((power.evaluate(power_input).inhibitors & gs::node::PowerInhibitDueWork) != 0,
          "overdue retry cannot sleep");
    power_input.now_ms = 100;
    power_input.pending_work = true;
    for (int attempt = 0; attempt < 3; ++attempt)
        power.observe_unacknowledged_attempt();
    check(power.evaluate(power_input).state == gs::node::PowerRuntimeState::Outage,
          "three unacknowledged attempts select outage policy without changing radio");
    power.observe_authenticated_contact();
    check(power.evaluate(power_input).state == gs::node::PowerRuntimeState::ReadyIdle,
          "authenticated progress exits outage");

    gs::node::EnergyCounters energy;
    energy.record_sensing_loop(2, true);
    energy.record_sensing_loop(3, false);
    energy.record_mac_attempt(true, true);
    energy.record_mac_attempt(false, false);
    energy.record_recovery_commit();
    energy.observe_pending(2);
    energy.observe_pending(1);
    check(energy.sensing_loops == 2 && energy.qualified_pir == 1 &&
          energy.sensor_active_ms == 5 && energy.application_tx_attempts == 1 &&
          energy.mac_send_attempts == 2 && energy.radio_tx_packets == 1 &&
          energy.recovery_nvs_commits == 1 && energy.queue_high_water == 2,
          "owner counters accumulate without event or retry state mutation");
    energy.deep_sleep_ms = 23ULL * 60ULL * 60ULL * 1000ULL;
    energy.awake_ms = 60ULL * 60ULL * 1000ULL;
    energy.sensor_active_ms = 10ULL * 60ULL * 1000ULL;
    energy.radio_tx_ms = 2ULL * 60ULL * 1000ULL;
    energy.radio_rx_ms = 3ULL * 60ULL * 1000ULL;
    gs::node::PowerCalibration calibration;
    calibration.usable_capacity_mah = 2700.0;
    calibration.reserve_percent = 5.0;
    calibration.sleep_current_ma = 0.2;
    calibration.awake_base_current_ma = 18.0;
    calibration.sensor_extra_current_ma = 1.0;
    calibration.radio_tx_extra_current_ma = 70.0;
    calibration.radio_rx_extra_current_ma = 45.0;
    const auto energy_estimate = power.estimate_runtime(energy, calibration, 3900, true);
    check(power.estimate_percent(3900, true) == 65, "battery voltage maps through non-linear SOC curve");
    check(energy_estimate.valid && energy_estimate.average_daily_mah > 20.0 && energy_estimate.estimated_days > 50.0,
          "calibrated usage counters produce a finite battery-life estimate");
    check(!power.estimate_runtime(energy, calibration, 3900, false).valid,
          "uncalibrated voltage cannot produce a runtime promise");

    gs::node::NodeRuntime runtime("node-rt", 3);
    const auto key = runtime.record(gs::EventKind::Motion, "room", 100, 10);
    check(key.has_value() && runtime.persisted() == 1, "node runtime persists before transmit");
    check(runtime.next_transmission(100).has_value(), "node runtime exposes due transmission");
    check(runtime.next_retry_deadline() == 100,
          "power deadline observes existing radio retry without mutating it");
    check(runtime.acknowledge(*key, gs::AckClass::Durable) && runtime.persisted() == 0, "node runtime retires durable ack");
}

void test_hub_modules() {
    gs::hub::PeerRegistry peers;
    peers.authorize("node-1", 7);
    gs::hub::IngestQueue ingest(2);
    check(ingest.callback_copy(event(1, gs::EventKind::Motion, 100), peers), "authorized packet copied");
    auto received = ingest.pop();
    check(received && received->key.sequence == 1, "state task receives copied packet");
    check(!ingest.callback_copy(event(2, gs::EventKind::Motion, 100, "unknown"), peers), "unknown peer rejected");

    gs::hub::HubJournal journal(8);
    check(journal.commit(event(1, gs::EventKind::Motion, 100)) == gs::hub::CommitResult::Stored, "journal stores event");
    check(journal.commit(event(1, gs::EventKind::Motion, 100)) == gs::hub::CommitResult::Duplicate, "journal deduplicates event");

    gs::hub::TrustedClock clock;
    check(!clock.valid_for_absence(0), "unanchored clock blocks absence");
    clock.anchor(1000, 0, 2);
    check(clock.valid_for_absence(10000), "trusted bounded clock permits absence evaluation");

    gs::hub::CoverageTracker coverage;
    coverage.require_node("node-1");
    check(coverage.current(100) == gs::CoverageState::Unknown, "unseen node means unknown coverage");
    coverage.observe("node-1", 100, 3800);
    check(coverage.current(200) == gs::CoverageState::Covered, "fresh required node covers window");
    check(coverage.current(291) == gs::CoverageState::Unknown, "expired lease becomes unknown");
    coverage.forget_node("node-1");
    check(coverage.reasons(291).empty(), "removed Node still affected coverage");

    gs::RoutineConfig config{"2026-09-07-morning", 100, 200, 230, {"kitchen", "common"}, true};
    gs::hub::RoutineService routine;
    routine.start_window(config, gs::HomeMode::Home);
    routine.set_coverage(gs::CoverageState::Covered);
    routine.apply(event(3, gs::EventKind::Motion, 150));
    check(!routine.deadline(230, true).create, "activity suppresses missing routine incident");

    gs::hub::RoutineService missing;
    missing.start_window(config, gs::HomeMode::Home);
    missing.set_coverage(gs::CoverageState::Covered);
    check(missing.deadline(230, true).create, "covered window without evidence creates incident");
    check(!missing.deadline(231, true).create, "stable window creates one incident");

    gs::hub::RoutineService unknown;
    unknown.start_window(config, gs::HomeMode::Home);
    unknown.set_coverage(gs::CoverageState::Unknown);
    check(!unknown.deadline(230, true).create && unknown.deadline(230, true).reason == "coverage_unknown",
          "coverage unknown never becomes confident inactivity");

    gs::hub::RoutineService private_mode;
    private_mode.start_window(config, gs::HomeMode::Privacy);
    private_mode.set_coverage(gs::CoverageState::Covered);
    check(!private_mode.deadline(230, true).create, "privacy suppresses passive incident");

    gs::hub::ResidentUi ui;
    auto call = ui.make_action(gs::hub::ResidentAction::CallFamily, "hub-1", 9, 1, 250);
    check(call.kind == gs::EventKind::CallFamily, "call button produces explicit action");
    check(ui.feedback_for(gs::hub::ResidentAction::CallFamily, false).display_text.find("internet") != std::string::npos,
          "offline feedback is explicit");

    gs::hub::ConfigService configs;
    gs::HomeConfig desired{1, "home-1", "Asia/Kolkata", gs::HomeMode::Home, config, {}};
    check(configs.apply(desired).applied, "valid home config applies");
    check(!configs.apply(desired).applied, "same config version is rejected");

    journal.commit(call);
    gs::hub::CloudSync cloud(journal);
    cloud.set_connected(true, 0);
    const auto batch = cloud.next_batch(0);
    check(!batch.empty() && batch.front().kind == gs::EventKind::CallFamily, "contact requests are replayed first");
    check(cloud.application_commit_ack(call.key), "application commit ack retires outbox item");

    gs::hub::HubRuntime runtime(4, 8);
    runtime.authorize_node("node-1", 7, true);
    runtime.start_window(config, gs::HomeMode::Home);
    check(runtime.radio_callback(event(20, gs::EventKind::Motion, 150)), "runtime callback admits known node");
    const auto processed = runtime.run_state_once();
    check(processed && processed->ack == gs::AckClass::Durable, "state owner commits before durable ack");
    check(runtime.routine_state().activity_seen, "runtime routes committed event to rules");
    const auto evidence_before_retry = runtime.routine_state().evidence_ids.size();
    check(runtime.radio_callback(event(20, gs::EventKind::Motion, 150)),
          "retry of known event enters bounded ingest");
    const auto retry = runtime.run_state_once();
    check(retry && retry->ack == gs::AckClass::Durable && !retry->state_changed &&
          retry->rule_signals.empty() && runtime.journal().size() == 1 &&
          runtime.routine_state().evidence_ids.size() == evidence_before_retry,
          "duplicate event replayed reducer effects after lost ACK");

    gs::hub::HubRuntime replacement_runtime(4, 8);
    replacement_runtime.authorize_node("node-1", 7, true);
    const auto same_logical_event = gs::node_message_from_event(
        event(1, gs::EventKind::Motion, 150));
    check(replacement_runtime.authenticated_radio_message_callback(
              same_logical_event, "node-1", "physical-A", 7, 150) &&
          replacement_runtime.run_state_once().has_value(),
          "old physical device was not admitted");
    check(replacement_runtime.authenticated_radio_message_callback(
              same_logical_event, "node-1", "physical-B", 7, 150) &&
          replacement_runtime.run_state_once().has_value() &&
          replacement_runtime.journal().size() == 2,
          "replacement hardware reused old physical event identity");
    check(replacement_runtime.authenticated_radio_message_callback(
              same_logical_event, "node-1", "physical-A", 7, 150),
          "same physical replay was not admitted for dedupe");
    const auto physical_retry = replacement_runtime.run_state_once();
    check(physical_retry && physical_retry->ack == gs::AckClass::Durable &&
          !physical_retry->state_changed && replacement_runtime.journal().size() == 2,
          "same physical identity was not deduplicated");
    auto queued_before_removal = same_logical_event;
    queued_before_removal.sequence_number = 2;
    check(replacement_runtime.authenticated_radio_message_callback(
              queued_before_removal, "node-1", "physical-A", 7, 150),
          "pre-removal event did not enter ingest");
    replacement_runtime.revoke_node("node-1");
    check(replacement_runtime.ingest_depth() == 0,
          "removed node left an uncommitted event in Hub ingest");
    check(!replacement_runtime.authenticated_radio_message_callback(
              same_logical_event, "node-1", "physical-A", 7, 150),
          "removed node retained HubRuntime admission");
    replacement_runtime.authorize_node("node-1", 8, true);
    check(replacement_runtime.authenticated_radio_message_callback(
              same_logical_event, "node-1", "physical-B", 8, 150, 500) &&
          replacement_runtime.node_online("node-1", 500),
          "new authenticated replacement could not reuse logical slot");
    gs::NodeHealthSnapshot health_one;
    health_one.node_id = "node-1";
    health_one.session_id = 8;
    health_one.health_sequence = 1;
    health_one.free_heap = 50000;
    replacement_runtime.authorize_node("node-2", 3, true);
    auto health_two = health_one;
    health_two.node_id = "node-2";
    health_two.session_id = 3;
    health_two.free_heap = 40000;
    check(replacement_runtime.observe_authenticated_health(health_one, "node-1", 8, 1000) &&
          replacement_runtime.observe_authenticated_health(health_two, "node-2", 3, 1000),
          "independent authenticated health was not recorded");
    check(replacement_runtime.node_health("node-1")->snapshot.free_heap == 50000 &&
          replacement_runtime.node_health("node-2")->snapshot.free_heap == 40000,
          "per-node health state was contaminated");
    check(!replacement_runtime.observe_authenticated_health(health_one, "node-2", 3, 2000) &&
          !replacement_runtime.observe_authenticated_health(health_one, "node-1", 7, 2000) &&
          !replacement_runtime.observe_authenticated_health(health_one, "node-1", 8, 2000),
          "wrong identity/session or stale health sequence was accepted");
    check(replacement_runtime.node_online("node-1", 310000) &&
          !replacement_runtime.node_online("node-1", 311001),
          "authenticated health lease did not expire");
    replacement_runtime.authorize_node("node-1", 9, true);
    check(!replacement_runtime.node_health("node-1") &&
          !replacement_runtime.node_online("node-1", 2000) &&
          replacement_runtime.node_health("node-2").has_value(),
          "one Node rejoin disturbed another Node's health");
    replacement_runtime.revoke_node("node-2");
    check(!replacement_runtime.node_health("node-2") &&
          !replacement_runtime.node_online("node-2", 2000),
          "removed Node retained health/liveness state");
    check(gs::EventKey{"a/b", 7, 1, "c"}.str() !=
          gs::EventKey{"b", 7, 1, "c/a"}.str(),
          "physical and logical delimiters collided");
}

void test_bat_c5_health_and_lease() {
    constexpr gs::Milliseconds quiet_ms =
        static_cast<gs::Milliseconds>(gs::NodeProtocolPolicy::heartbeat_seconds) * 1000;
    constexpr gs::Milliseconds lease_ms =
        gs::NodeProtocolPolicy::offline_after_seconds * 1000;
    check(quiet_ms == 120000 && lease_ms == 310000 &&
          lease_ms - 2 * quiet_ms == 70000,
          "quiet health and Hub lease have a retry/scheduling safety margin");

    gs::node::NodeHealthCadence cadence(quiet_ms, quiet_ms);
    check(!cadence.due(quiet_ms - 1, false, false, false, false) &&
          cadence.due(quiet_ms, false, false, false, false),
          "quiet Node offers health at the bounded silence deadline");
    cadence.observe_authenticated_contact(90000);
    check(!cadence.due(209999, false, false, false, false) &&
          cadence.due(210000, false, false, false, false),
          "authenticated application contact defers redundant NodeHealth");
    check(!cadence.due(210000, true, false, false, false) &&
          !cadence.due(210000, false, true, false, false) &&
          !cadence.due(210000, false, true, true, false) &&
          !cadence.due(210000, false, false, false, true),
          "application work, outage and maintenance outrank routine health");
    cadence.observe_health_attempt(210000);
    check(!cadence.due(329999, false, false, false, false) &&
          cadence.due(330000, false, false, false, false),
          "quiet health repeats without a new task or telemetry type");

    gs::hub::HubRuntime hub(4, 8);
    hub.authorize_node("quiet-node", 7, false);
    check(!hub.observe_authenticated_contact("unknown", 7, 1) &&
          !hub.observe_authenticated_contact("quiet-node", 8, 1) &&
          !hub.node_online("quiet-node", 1),
          "unknown or stale-session contact cannot refresh Hub liveness");
    check(hub.observe_authenticated_contact("quiet-node", 7, 1000) &&
          hub.node_online("quiet-node", 241000) &&
          hub.node_online("quiet-node", 311000) &&
          !hub.node_online("quiet-node", 311001),
          "authenticated rejoin covers two quiet health opportunities then expires");
    check(!hub.observe_authenticated_contact("quiet-node", 7, 999) &&
          !hub.node_online("quiet-node", 311001),
          "older contact cannot move the Hub lease backward");

    hub.authorize_node("quiet-node", 8, false);
    check(!hub.node_online("quiet-node", 120000) &&
          !hub.observe_authenticated_contact("quiet-node", 7, 120000) &&
          hub.observe_authenticated_contact("quiet-node", 8, 120000),
          "fresh authenticated rejoin replaces the previous session lease");
    auto app = gs::node_message_from_event(
        event(1, gs::EventKind::Motion, 150, "quiet-node"));
    app.session_id = 8;
    check(hub.authenticated_radio_message_callback(
              app, "quiet-node", "physical-quiet", 8, 0, 200000) &&
          hub.node_online("quiet-node", 510000) &&
          !hub.node_online("quiet-node", 510001),
          "authenticated application event refreshes Hub liveness without health");
    hub.revoke_node("quiet-node");
    check(!hub.observe_authenticated_contact("quiet-node", 8, 510002) &&
          !hub.node_online("quiet-node", 510002),
          "revoked Node cannot refresh Hub liveness");
}


void test_protocol_and_generic_rules() {
    check(gs::NodeProtocolPolicy::heartbeat_seconds == 120,
          "quiet authenticated health interval is 120 seconds");
    check(gs::NodeProtocolPolicy::offline_after_seconds == 310,
          "Hub lease covers two quiet health opportunities plus 70 seconds");
    check(gs::NodeProtocolPolicy::retry_delays_ms[0] == 200 &&
          gs::NodeProtocolPolicy::retry_delays_ms[3] == 10000 &&
          gs::NodeProtocolPolicy::retry_delays_ms[4] == 60000,
          "retry schedule reaches a controlled periodic offline probe");

    gs::node::NodeRuntime node_runtime("proto-node", 11);
    gs::NodePowerTelemetry wire_power;
    wire_power.deep_sleep_ms = 900000;
    wire_power.awake_ms = 100000;
    wire_power.sensor_active_ms = 25000;
    wire_power.radio_tx_ms = 5000;
    wire_power.radio_rx_ms = 7000;
    wire_power.radio_tx_packets = 44;
    wire_power.radio_retries = 2;
    wire_power.wake_count = 18;
    wire_power.heartbeat_count = 14;
    wire_power.boot_count = 1;
    node_runtime.set_power_telemetry(wire_power);
    const auto key = node_runtime.record(gs::EventKind::Motion, "bedroom", 1000, 100,
                                         0, 3770, false, gs::SensorType::Pir, -61);
    check(key.has_value(), "canonical node event records before transmission");
    const auto tx = node_runtime.next_transmission(1000);
    check(tx.has_value() && tx->sensor_type == gs::SensorType::Pir && tx->rssi_dbm == -61,
          "node event carries sensor type and RSSI independently of GPIO");
    const auto wire = node_runtime.next_message(1000);
    check(wire.has_value() && wire->schema == 2 && wire->node_id == "proto-node" &&
          wire->sequence_number == key->sequence && wire->event_type == gs::EventKind::Motion &&
          wire->battery_mv == 3770 && wire->rssi_dbm == -61,
          "typed node wire message preserves canonical protocol fields");
    check(wire->power.has_value() && wire->power->wake_count == 18 && wire->power->radio_retries == 2,
          "typed node wire message carries cumulative power telemetry");
    auto invalid_power_wire = *wire;
    invalid_power_wire.power->radio_tx_ms = invalid_power_wire.power->awake_ms + 1;
    check(!gs::valid_node_message(invalid_power_wire),
          "node protocol rejects impossible power telemetry ranges");
    const auto decoded = gs::domain_event_from_node_message(*wire, 101);
    check(decoded.key.str() == tx->key.str() && decoded.received_at == 101 &&
          decoded.sensor_type == gs::SensorType::Pir,
          "hub adapter converts canonical wire message into the same generic DomainEvent");
    const auto ack = gs::make_node_ack(decoded.key, gs::AckClass::Durable, 102, "journal_committed");
    check(ack.schema == 1 && ack.sequence_number == key->sequence && ack.ack_type == gs::AckClass::Durable,
          "typed durable ACK preserves the node event identity");

    gs::ActivityRuleConfig policy;
    policy.door_open_timeout_seconds = 300;
    policy.daytime_inactivity_seconds = 3600;
    gs::ActivityRuleState state;

    const auto quiet_open = gs::RulesCore::apply_activity_event(
        state, policy, event(50, gs::EventKind::DoorOpen, 100, "entry", "entry"), 2 * 60 + 30);
    check(quiet_open.size() == 1 && quiet_open[0].kind == gs::RuleSignalKind::UnexpectedDoorOpen,
          "door opening during quiet hours is a pure rule decision");

    const auto left_open = gs::RulesCore::evaluate_activity_timers(state, policy, 400, 2 * 60 + 35);
    check(left_open.size() == 1 && left_open[0].kind == gs::RuleSignalKind::DoorLeftOpen,
          "door open for five minutes creates a rule signal");
    check(gs::RulesCore::evaluate_activity_timers(state, policy, 401, 2 * 60 + 36).empty(),
          "door-left-open signal is latched and not duplicated");

    const auto close = gs::RulesCore::apply_activity_event(
        state, policy, event(51, gs::EventKind::DoorClosed, 460, "entry", "entry"), 2 * 60 + 40);
    check(close.size() == 1 && close[0].resolves_prior && close[0].duration_seconds == 360,
          "door close resolves prior left-open state and preserves duration");

    gs::RulesCore::apply_activity_event(state, policy, event(52, gs::EventKind::Motion, 1000), 10 * 60);
    const auto inactivity = gs::RulesCore::evaluate_activity_timers(state, policy, 4600, 11 * 60);
    check(inactivity.size() == 1 && inactivity[0].kind == gs::RuleSignalKind::DaytimeInactivity,
          "daytime no-activity threshold creates a check-in rule signal");
    check(gs::RulesCore::evaluate_activity_timers(state, policy, 4700, 11 * 60 + 2).empty(),
          "daytime inactivity is not repeatedly emitted until new activity");
    gs::RulesCore::apply_activity_event(state, policy, event(53, gs::EventKind::Motion, 4800), 11 * 60 + 5);
    check(!state.inactivity_alerted, "new generic activity rearms the inactivity rule");

    gs::ActivityRuleState no_activity_state;
    gs::RulesCore::start_activity_monitor(no_activity_state, 1000);
    const gs::RuleEvaluationContext unavailable{gs::HomeMode::Home, gs::CoverageState::Unknown, true};
    check(gs::RulesCore::evaluate_activity_timers(no_activity_state, policy, 4600, 11 * 60, unavailable).empty(),
          "no-activity timer never turns unavailable sensor coverage into an inactivity concern");
    const gs::RuleEvaluationContext eligible{gs::HomeMode::Home, gs::CoverageState::Covered, true};
    const auto no_activity = gs::RulesCore::evaluate_activity_timers(
        no_activity_state, policy, 4600, 11 * 60, eligible);
    check(no_activity.size() == 1 && no_activity[0].kind == gs::RuleSignalKind::DaytimeInactivity &&
          no_activity[0].duration_seconds == 3600,
          "daytime inactivity works even when no activity event has occurred since monitoring began");

    const gs::RuleEvaluationContext away{gs::HomeMode::Away, gs::CoverageState::Covered, true};
    gs::ActivityRuleState away_state;
    const auto away_door = gs::RulesCore::apply_activity_event(
        away_state, policy, event(55, gs::EventKind::DoorOpen, 5000, "entry", "entry"), 2 * 60, away);
    check(away_door.empty(), "quiet-hour concern is suppressed while monitoring mode is away");

    check(gs::RulesCore::minute_in_window(90, 60, 300), "quiet-hour window includes 01:30");
    check(!gs::RulesCore::minute_in_window(600, 60, 300), "quiet-hour window excludes daytime");
    check(gs::RulesCore::minute_in_window(30, 22 * 60, 6 * 60), "time windows may cross midnight");

    gs::hub::HubRuntime hub_runtime(4, 16);
    hub_runtime.authorize_node("entry", 7, false);
    hub_runtime.start_window({"w", 0, 10, 20, {}, true}, gs::HomeMode::Home);
    const auto hub_wire = gs::node_message_from_event(event(54, gs::EventKind::DoorOpen, 100, "entry", "entry"));
    check(hub_runtime.radio_message_callback(hub_wire, 100),
          "hub accepts the canonical node message and converts it to a generic event");
    const auto saved_power = hub_runtime.latest_power_telemetry("entry");
    check(!saved_power.has_value(), "hub does not invent power telemetry when node message omits it");
    auto hub_wire_with_power = hub_wire;
    hub_wire_with_power.sequence_number = 55;
    hub_wire_with_power.power = wire_power;
    check(hub_runtime.radio_message_callback(hub_wire_with_power, 101),
          "hub accepts an authenticated node message carrying power telemetry");
    const auto retained_power = hub_runtime.latest_power_telemetry("entry");
    check(retained_power.has_value() && retained_power->radio_tx_packets == 44,
          "hub retains latest accepted node power telemetry for cloud/analytics adapter");
    const auto processed = hub_runtime.run_state_once(2 * 60);
    check(processed.has_value() && processed->rule_signals.size() == 1 &&
          processed->rule_signals[0].kind == gs::RuleSignalKind::UnexpectedDoorOpen,
          "hub adapter feeds generic events into the hardware-independent rule engine");

    gs::ActivityRuleConfig routines;
    routines.morning_start_minute = 6 * 60; routines.morning_end_minute = 11 * 60;
    routines.morning_sequence_window_seconds = 7200;
    gs::ActivityRuleState routine_state;
    check(gs::RulesCore::apply_activity_event(routine_state, routines, event(60, gs::EventKind::Motion, 100, "room1", "room1"), 7*60).empty(),
          "bedroom starts configured morning sequence without completing it");
    check(gs::RulesCore::apply_activity_event(routine_state, routines, event(61, gs::EventKind::Motion, 200, "bathroom", "bathroom"), 7*60+2).empty(),
          "bathroom is recorded as morning sequence evidence");
    const auto morning_done = gs::RulesCore::apply_activity_event(routine_state, routines, event(62, gs::EventKind::Motion, 300, "kitchen", "kitchen"), 7*60+4);
    check(morning_done.size()==1 && morning_done[0].kind==gs::RuleSignalKind::MorningRoutineCompleted,
          "configured bedroom then bathroom+kitchen completes morning routine");

    auto morning_sequence = [&](gs::EpochSeconds bathroom_at, gs::EpochSeconds kitchen_at) {
        gs::ActivityRuleState state;
        gs::RulesCore::apply_activity_event(state, routines, event(70, gs::EventKind::Motion, 100, "room1", "room1"), 7*60);
        gs::RulesCore::apply_activity_event(state, routines, event(71, gs::EventKind::Motion, bathroom_at, "bathroom", "bathroom"), 7*60+1);
        return gs::RulesCore::apply_activity_event(state, routines, event(72, gs::EventKind::Motion, kitchen_at, "kitchen", "kitchen"), 7*60+2);
    };
    check(morning_sequence(101, 102).size() == 1,
          "subsequent morning evidence within the window completes the sequence");
    check(morning_sequence(101, 100 + routines.morning_sequence_window_seconds + 1).empty(),
          "morning evidence after the sequence window does not complete it");
    check(morning_sequence(99, 101).empty(),
          "late-arriving bathroom evidence before bedroom start does not complete the sequence");
    check(morning_sequence(101, 100 + routines.morning_sequence_window_seconds).size() == 1,
          "morning evidence at the exact sequence-window boundary completes it");

    gs::ActivityRuleState night_state;
    routines.night_bathroom_visit_threshold=1; routines.night_visit_merge_seconds=60;
    check(gs::RulesCore::apply_activity_event(night_state,routines,event(63,gs::EventKind::Motion,1000,"bathroom","bathroom"),23*60).empty(),
          "night bathroom visit at configured limit stays normal");
    const auto night_bad=gs::RulesCore::apply_activity_event(night_state,routines,event(64,gs::EventKind::Motion,1061,"bathroom","bathroom"),23*60+1);
    check(night_bad.size()==1 && night_bad[0].kind==gs::RuleSignalKind::UnusualNightBathroomActivity,
          "night bathroom visit greater than configured limit raises concern");

    gs::ActivityRuleState post_door;
    routines.post_door_inactivity_seconds=7200;
    gs::RulesCore::apply_activity_event(post_door,routines,event(65,gs::EventKind::DoorOpen,2000,"entry","entry"),12*60);
    gs::RulesCore::apply_activity_event(post_door,routines,event(66,gs::EventKind::DoorClosed,2010,"entry","entry"),12*60);
    const auto post_bad=gs::RulesCore::evaluate_activity_timers(post_door,routines,9210,14*60);
    check(!post_bad.empty() && post_bad.back().kind==gs::RuleSignalKind::PostDoorInactivity,
          "post-door inactivity uses configured threshold");
}

void test_node_offline_resilience() {
    gs::node::NodeRuntime offline("offline-node", 21, 32, 32);
    std::size_t admitted = 0;
    for (std::uint64_t index = 0; index < 1000; ++index) {
        const auto now = static_cast<gs::Milliseconds>(index * 2000U);
        if (offline.record(gs::EventKind::Motion, "room1", now, 0)) {
            ++admitted;
        }
        // Simulate one bounded owner-loop radio opportunity while the Hub is
        // unavailable. No sensor event is ever allowed to wait for it.
        const auto attempt = offline.next_message(now);
        if (attempt) {
            offline.transport_result({attempt->node_id, attempt->session_id,
                                      attempt->sequence_number}, false, now);
        }
    }
    check(admitted == 28, "motion backlog preserves four priority reserve slots");
    check(offline.persisted() == admitted && offline.pending() == admitted,
          "offline store and retry queue remain consistent and bounded");
    check(offline.stats().record_calls == 1000 && offline.stats().accepted == admitted &&
          offline.stats().dropped_motion == 1000 - admitted,
          "one thousand local motions are accounted without blocking");
    check(offline.next_sequence() == 1001,
          "every qualified event attempt consumes one explicit sequence identity");
    check(offline.radio_stats().transport_results <= 1000 &&
          offline.radio_stats().periodic_backoff_entries > 0,
          "long offline retry work stays bounded and reaches periodic backoff");

    for (std::size_t index = 0; index < admitted; ++index) {
        const auto pending = offline.next_message(3000000);
        check(pending.has_value(), "Hub return exposes retained work without a new PIR event");
        const gs::EventKey key{pending->node_id, pending->session_id,
                               pending->sequence_number};
        check(offline.acknowledge(key, gs::AckClass::Durable),
              "Hub Durable ACK retires exactly one retained offline event");
    }
    check(offline.persisted() == 0 && offline.pending() == 0,
          "offline backlog drains without stranded store entries");
    const auto after_recovery = offline.record(gs::EventKind::Motion, "room1", 3001000, 0);
    check(after_recovery && after_recovery->sequence == 1001,
          "fresh sensing works after Hub recovery and preserves sequence gaps");

    gs::node::NodeRuntime retry("retry-node", 22, 1, 1);
    const auto retry_key = retry.record(gs::EventKind::Motion, "room1", 0, 0);
    check(retry_key.has_value(), "Hub-unavailable-from-boot retains first event");
    const auto first = retry.next_message(0);
    check(first && first->sequence_number == retry_key->sequence,
          "first offline transmission is immediately due");
    retry.transport_result(*retry_key, false, 0);
    check(!retry.next_message(200), "retry honors deterministic delay and jitter");
    const auto mac_retry = retry.next_message(300);
    check(mac_retry && mac_retry->sequence_number == retry_key->sequence,
          "MAC failure recovers on timer with the same EventKey");
    retry.transport_result(*retry_key, true, 300);
    check(!retry.next_message(800), "MAC success still waits for application ACK timeout");
    const auto app_ack_retry = retry.next_message(1000);
    check(app_ack_retry && app_ack_retry->sequence_number == retry_key->sequence,
          "missing application ACK retries without a new PIR event");
    check(!retry.acknowledge({"retry-node", 22, 99}, gs::AckClass::Durable) &&
          retry.persisted() == 1,
          "stale ACK cannot retire current retained evidence");
    check(retry.acknowledge(*retry_key, gs::AckClass::Durable) && retry.persisted() == 0,
          "correct Durable ACK retires after recovery");

    gs::node::NodeRuntime store_limited("store-node", 23, 2, 8);
    check(store_limited.record(gs::EventKind::DoorOpen, "entry", 0, 0).has_value() &&
          store_limited.record(gs::EventKind::DoorClosed, "entry", 1, 0).has_value(),
          "priority evidence fills configured store capacity");
    check(!store_limited.record(gs::EventKind::CallFamily, "entry", 2, 0) &&
          store_limited.stats().store_full == 1 &&
          store_limited.persisted() == store_limited.pending(),
          "store-full policy rejects explicitly without stranding");

    gs::node::NodeRuntime priority("priority-node", 24, 32, 32);
    for (std::uint64_t index = 0; index < 28; ++index) {
        check(priority.record(gs::EventKind::Motion, "room1", index, 0).has_value(),
              "motion fits within repetitive-event allocation");
    }
    for (std::uint64_t index = 0; index < 4; ++index) {
        check(priority.record(gs::EventKind::CallFamily, "room1", 100 + index, 0).has_value(),
              "reserved capacity admits higher-priority non-motion evidence");
    }
    check(!priority.record(gs::EventKind::CallFamily, "room1", 200, 0) &&
          priority.stats().priority_rejected == 1,
          "priority exhaustion is explicit rather than silently coalesced");

    gs::NodeHealthSnapshot health;
    health.node_id = "offline-node";
    health.session_id = 21;
    health.health_sequence = 7;
    health.uptime_ms = 60000;
    health.raw_pir_edges = 2000;
    health.accepted_pir = 1000;
    health.rejected_pir = 972;
    health.retained_count = 28;
    health.oldest_sequence = 1;
    health.last_breadcrumb = gs::NodeBreadcrumb::RetryBackoff;
    health.last_error = gs::NodeHealthError::TxQueueFull;
    health.free_heap = 120000;
    health.minimum_free_heap = 110000;
    const auto encoded_health = gs::transport::encode_node_health(health);
    check(encoded_health && encoded_health.frame.size <= gs::transport::kMaxFrameBytes,
          "health snapshot is compact and bounded");
    check(gs::transport::classify_frame(encoded_health.frame.bytes.data(),
                                        encoded_health.frame.size) ==
              gs::transport::FrameClass::NodeHealth,
          "health uses a separate non-business frame type");
    const auto decoded_health = gs::transport::decode_node_health(
        encoded_health.frame.bytes.data(), encoded_health.frame.size);
    check(decoded_health && decoded_health.value->health_sequence == 7 &&
          decoded_health.value->accepted_pir == 1000 &&
          decoded_health.value->oldest_sequence == 1,
          "health snapshot round trip preserves endurance diagnostics");

    gs::node::QualifiedInput pir(gs::EventKind::Motion, std::nullopt, 1, 1);
    check(!pir.sample(false, 0), "offline sensing initializes independently");
    std::size_t local_events = 0;
    for (gs::Milliseconds now = 2; now < 4002; now += 4) {
        (void)pir.sample(true, now);
        if (pir.sample(true, now + 1)) ++local_events;
        (void)pir.sample(false, now + 2);
        (void)pir.sample(false, now + 3);
    }
    check(local_events == 1000,
          "local sensing continues for one thousand cycles independent of transport capacity");

    for (int cycle = 0; cycle < 3; ++cycle) {
        gs::node::NodeRuntime cycling("cycle-node", 30 + cycle, 2, 2);
        const auto key = cycling.record(gs::EventKind::Motion, "room1", 0, 0);
        check(key && cycling.next_message(0), "Hub-off cycle starts bounded retry work");
        cycling.transport_result(*key, false, 0);
        const auto recovered = cycling.next_message(300);
        check(recovered && cycling.acknowledge(*key, gs::AckClass::Durable),
              "repeated Hub off/on cycle recovers without reboot or new PIR");
    }
}

void test_node_power_diagnostics() {
    gs::node::QualifiedInput pir(gs::EventKind::Motion, std::nullopt, 150, 1000);
    gs::node::PirNoiseMonitor noise;
    check(!pir.sample(false, 0), "PIR starts idle");
    check(!pir.sample(true, 10), "PIR rise still requires debounce");
    const auto first = pir.sample(true, 160);
    check(first == gs::EventKind::Motion &&
          !noise.observe(true, first.has_value(), 160),
          "first qualified PIR is delivered without a noise fault");
    bool warned = false;
    for (int index = 0; index < 24; ++index)
        warned |= noise.observe(index % 2 == 0, false, 200 + index * 10);
    check(warned && noise.snapshot().noisy_windows == 1 &&
          noise.snapshot().rapid_edges >= 20,
          "rapid PIR edges produce one bounded diagnostic per window");
    check(!noise.observe(true, false, 500) &&
          noise.snapshot().noisy_windows == 1,
          "additional noisy edges do not flood the same window");
    check(noise.observe(true, false, 300500) &&
          noise.snapshot().stuck_high && noise.snapshot().stuck_high_reports == 1,
          "sustained PIR high is observable without disabling sensing");
    check(!noise.observe(true, false, 300520) &&
          noise.snapshot().stuck_high_reports == 1,
          "stuck-high fault is reported once per continuous high interval");
    check(pir.sample(false, 300530) == std::nullopt &&
          !noise.observe(false, false, 300530) &&
          !noise.snapshot().stuck_high,
          "PIR low clears diagnostic state while sensing remains active");
    check(!pir.sample(false, 300690) && !pir.sample(true, 300700) &&
          pir.sample(true, 300860) == gs::EventKind::Motion,
          "a valid later PIR event still qualifies after noisy input");

    gs::node::NodeLedPolicy led;
    check(!led.active(0) && !led.on(0), "LED defaults off");
    led.trigger(gs::node::LedSignal::Ready, 100);
    check(led.on(100) && !led.on(250) && led.on(400) &&
          !led.active(550), "ready indication uses two bounded nonblocking pulses");
    led.trigger(gs::node::LedSignal::Delivery, 600);
    check(led.on(600) && !led.active(680),
          "delivery indication ends without blocking owner work");
    led.trigger(gs::node::LedSignal::Fault, 700);
    led.trigger(gs::node::LedSignal::Delivery, 710);
    check(led.on(710) && led.active(1180) && !led.active(1240),
          "fault indication is bounded and not displaced by delivery");
}

void test_node_outage_profile() {
    gs::node::NodeRuntime node("outage-node", 50, 8, 8);
    const auto motion = node.record(gs::EventKind::Motion, "room", 0, 0);
    check(motion && node.has_pending_key(*motion),
          "outage fixture retains the original motion identity");
    auto due = node.next_message(0);
    check(due && due->sequence_number == motion->sequence,
          "first normal attempt remains immediate");
    node.transport_result(*motion, false, 0);
    check(!node.next_message(200) && node.next_message(300),
          "normal initial backoff remains unchanged");
    node.transport_result(*motion, false, 300);
    check(!node.next_message(800) && node.next_message(1000),
          "normal second retry remains on the existing ladder");
    gs::node::PowerPolicy policy;
    policy.observe_unacknowledged_attempt();
    policy.observe_unacknowledged_attempt();
    check(policy.consecutive_unacknowledged() == 2 &&
          !node.outage_profile(), "two failed attempts do not enter outage");
    policy.observe_unacknowledged_attempt();
    node.set_outage_profile(policy.consecutive_unacknowledged() >= 3, 1000);
    check(node.outage_profile(), "confirmed outage selects periodic profile");
    node.transport_result(*motion, false, 1000);
    const auto next = node.next_retry_deadline();
    check(next && *next >= 61000 && *next <= 61200 &&
          !node.next_message(60000),
          "confirmed outage limits ordinary retry opportunities to about one per minute");

    const auto door = node.record(gs::EventKind::DoorOpen, "entry", 2000, 0);
    check(door && node.next_retry_deadline() == 2000,
          "new priority work remains due despite ordinary recovery gate");
    due = node.next_message(2000);
    check(due && due->sequence_number == door->sequence,
          "new door event bypasses the motion probe gate once");
    node.transport_result(*door, false, 2000);
    check(!node.next_message(3000) && node.has_pending_key(*motion) &&
          node.has_pending_key(*door),
          "outage retains both identities and does not create a retry burst");
    due = node.next_message(62500);
    check(due && due->sequence_number == door->sequence,
          "priority retained work wins the next bounded recovery opportunity");
    node.transport_result(*door, false, 62500);
    check(!node.next_message(120000) &&
          node.next_retry_deadline() && *node.next_retry_deadline() >= 122500 &&
          node.radio_stats().periodic_backoff_entries >= 1,
          "confirmed outage remains periodic without an all-pending retry storm");
    check(!node.acknowledge(*motion, gs::AckClass::ReceivedVolatile) &&
          node.has_pending_key(*motion),
          "volatile ACK cannot retire durable outage evidence");
    policy.observe_authenticated_contact();
    node.set_outage_profile(false, 120001);
    check(!node.outage_profile() && policy.consecutive_unacknowledged() == 0 &&
          node.next_retry_deadline() && *node.next_retry_deadline() <= 120001 &&
          node.next_message(120001),
          "authenticated recovery clears outage and schedules retained work");
    check(node.acknowledge(*motion, gs::AckClass::Durable) &&
          node.acknowledge(*door, gs::AckClass::Durable) &&
          node.pending() == 0 && node.persisted() == 0,
          "matching durable ACKs retire the original event identities");
}

void test_data_plane_codec_and_ack_policy() {
    namespace wire = gs::transport;

    gs::NodeMessage message;
    message.node_id = std::string(wire::kMaxSourceIdBytes, 'n');
    message.session_id = 0x0102030405060708ULL;
    message.sequence_number = 0x1112131415161718ULL;
    message.sensor_type = gs::SensorType::Pir;
    message.event_type = gs::EventKind::Motion;
    message.location = std::string(wire::kMaxLocationBytes, 'l');
    message.monotonic_ms = 123456789;
    message.occurred_at = 1700000000;
    message.time_uncertainty_ms = 2300;
    message.battery_mv = 3775;
    message.rssi_dbm = -67;
    message.is_test = true;
    gs::NodePowerTelemetry power;
    power.deep_sleep_ms = 900000;
    power.awake_ms = 100000;
    power.sensor_active_ms = 25000;
    power.radio_tx_ms = 5000;
    power.radio_rx_ms = 7000;
    power.radio_tx_packets = 44;
    power.radio_retries = 2;
    power.wake_count = 18;
    power.heartbeat_count = 14;
    power.boot_count = 3;
    power.brownout_count = 1;
    message.power = power;
    message.payload_json = std::string(wire::kMaxPayloadJsonBytes, 'p');

    const auto encoded = wire::encode_node_message(message);
    check(encoded && encoded.frame.size <= wire::kMaxFrameBytes && encoded.frame.size < 250,
          "maximum data-plane message fits bounded ESP-NOW payload");
    check(encoded.frame.bytes[0] == 0x47 && encoded.frame.bytes[1] == 0x53 &&
          encoded.frame.bytes[2] == 0x44 && encoded.frame.bytes[3] == 0x50 &&
          encoded.frame.bytes[4] == wire::kDataPlaneVersion &&
          encoded.frame.bytes[5] == static_cast<std::uint8_t>(wire::FrameType::NodeMessage),
          "data-plane envelope has deterministic magic, version and type");
    check(wire::classify_frame(encoded.frame.bytes.data(), encoded.frame.size) ==
              wire::FrameClass::NodeMessage,
          "node message frame discriminator is recognized");

    const auto decoded = wire::decode_node_message(encoded.frame.bytes.data(), encoded.frame.size);
    check(decoded && decoded.value->node_id == message.node_id &&
          decoded.value->session_id == message.session_id &&
          decoded.value->sequence_number == message.sequence_number &&
          decoded.value->event_type == message.event_type &&
          decoded.value->sensor_type == message.sensor_type &&
          decoded.value->location == message.location,
          "NodeMessage round trip preserves EventKey, event, sensor and location");
    check(decoded.value->monotonic_ms == message.monotonic_ms &&
          decoded.value->occurred_at == message.occurred_at &&
          decoded.value->time_uncertainty_ms == message.time_uncertainty_ms &&
          decoded.value->battery_mv == message.battery_mv &&
          decoded.value->rssi_dbm == message.rssi_dbm &&
          decoded.value->is_test == message.is_test &&
          decoded.value->payload_json == message.payload_json,
          "NodeMessage round trip preserves timing, battery, RSSI, flags and payload");
    check(decoded.value->power.has_value() &&
          decoded.value->power->deep_sleep_ms == power.deep_sleep_ms &&
          decoded.value->power->awake_ms == power.awake_ms &&
          decoded.value->power->sensor_active_ms == power.sensor_active_ms &&
          decoded.value->power->radio_tx_ms == power.radio_tx_ms &&
          decoded.value->power->radio_rx_ms == power.radio_rx_ms &&
          decoded.value->power->radio_tx_packets == power.radio_tx_packets &&
          decoded.value->power->radio_retries == power.radio_retries &&
          decoded.value->power->wake_count == power.wake_count &&
          decoded.value->power->heartbeat_count == power.heartbeat_count &&
          decoded.value->power->boot_count == power.boot_count &&
          decoded.value->power->brownout_count == power.brownout_count,
          "NodeMessage round trip preserves all power telemetry");

    gs::NodeAckMessage ack = gs::make_node_ack(
        {message.node_id, message.session_id, message.sequence_number},
        gs::AckClass::Durable, 1700000001,
        std::string(wire::kMaxAckReasonBytes, 'r'));
    const auto encoded_ack = wire::encode_node_ack(ack);
    check(encoded_ack && wire::classify_frame(encoded_ack.frame.bytes.data(), encoded_ack.frame.size) ==
              wire::FrameClass::NodeAck,
          "NodeAckMessage encodes within the data-plane ACK envelope");
    const auto decoded_ack = wire::decode_node_ack(
        encoded_ack.frame.bytes.data(), encoded_ack.frame.size);
    check(decoded_ack && decoded_ack.value->node_id == ack.node_id &&
          decoded_ack.value->session_id == ack.session_id &&
          decoded_ack.value->sequence_number == ack.sequence_number &&
          decoded_ack.value->ack_type == gs::AckClass::Durable &&
          decoded_ack.value->hub_received_at == ack.hub_received_at &&
          decoded_ack.value->reason == ack.reason,
          "NodeAckMessage round trip preserves identity, class, time and reason");

    check(wire::decode_node_message(encoded.frame.bytes.data(), encoded.frame.size - 1).error ==
              wire::CodecError::Truncated,
          "truncated frame is rejected");
    auto bad = encoded.frame;
    bad.bytes[0] ^= 0x01U;
    check(wire::decode_node_message(bad.bytes.data(), bad.size).error == wire::CodecError::BadMagic,
          "bad magic is rejected");
    bad = encoded.frame;
    bad.bytes[4] = static_cast<std::uint8_t>(wire::kDataPlaneVersion + 1U);
    check(wire::decode_node_message(bad.bytes.data(), bad.size).error ==
              wire::CodecError::UnsupportedVersion,
          "unsupported data-plane version is rejected");
    bad = encoded.frame;
    bad.bytes[5] = 0x7FU;
    check(wire::decode_node_message(bad.bytes.data(), bad.size).error ==
              wire::CodecError::UnknownFrameType,
          "unknown frame type is rejected");

    const std::size_t source_length = message.node_id.size();
    const std::size_t sensor_offset = 29U + source_length;
    const std::size_t event_offset = sensor_offset + 1U;
    const std::size_t location_length_offset = event_offset + 1U;
    const std::size_t flags_offset = location_length_offset + 1U + message.location.size() + 8U;
    bad = encoded.frame;
    bad.bytes[sensor_offset] = 0x7FU;
    check(wire::decode_node_message(bad.bytes.data(), bad.size).error == wire::CodecError::InvalidValue,
          "impossible SensorType is rejected");
    bad = encoded.frame;
    bad.bytes[event_offset] = 0x7FU;
    check(wire::decode_node_message(bad.bytes.data(), bad.size).error == wire::CodecError::InvalidValue,
          "impossible EventKind is rejected");
    bad = encoded.frame;
    bad.bytes[12] = static_cast<std::uint8_t>(wire::kMaxSourceIdBytes + 1U);
    check(!wire::decode_node_message(bad.bytes.data(), bad.size),
          "oversized encoded source length is rejected");
    bad = encoded.frame;
    bad.bytes[flags_offset] |= 0x80U;
    check(wire::decode_node_message(bad.bytes.data(), bad.size).error ==
              wire::CodecError::MalformedFlags,
          "unknown optional-presence flags are rejected");
    bad = encoded.frame;
    bad.bytes[bad.size] = 0U;
    check(wire::decode_node_message(bad.bytes.data(), bad.size + 1U).error ==
              wire::CodecError::TrailingData,
          "trailing bytes are rejected");

    auto bad_ack = encoded_ack.frame;
    const std::size_t ack_class_offset = 29U + ack.node_id.size();
    bad_ack.bytes[ack_class_offset] = 0x7FU;
    check(wire::decode_node_ack(bad_ack.bytes.data(), bad_ack.size).error ==
              wire::CodecError::InvalidValue,
          "invalid AckClass is rejected");

    const std::array<std::uint8_t, 8> fota_frame{{0x4F, 0x46, 0x53, 0x47, 1, 1, 0, 0}};
    check(wire::classify_frame(fota_frame.data(), fota_frame.size()) ==
              wire::FrameClass::ControlFota &&
          wire::decode_node_message(fota_frame.data(), fota_frame.size()).error ==
              wire::CodecError::BadMagic,
          "FOTA control frame is classified separately and never decoded as NodeMessage");

    gs::node::NodeRuntime runtime("ack-node", 42);
    const auto retained_key = runtime.record(gs::EventKind::Motion, "room1", 0, 0,
                                             86400, 0, false, gs::SensorType::Pir, 0);
    check(retained_key.has_value() && runtime.persisted() == 1,
          "business event is retained before transport");
    const auto first_attempt = runtime.next_message(0);
    check(first_attempt && first_attempt->session_id == 42 && first_attempt->sequence_number == 1,
          "runtime creates first typed message identity");
    runtime.transport_result(*retained_key, true, 0);
    check(runtime.persisted() == 1,
          "ESP-NOW MAC delivery success alone does not retire durable evidence");
    check(!runtime.acknowledge(*retained_key, gs::AckClass::ReceivedVolatile) &&
          runtime.persisted() == 1,
          "ReceivedVolatile does not retire a business event");
    check(!runtime.acknowledge({"ack-node", 42, 99}, gs::AckClass::Durable) &&
          runtime.persisted() == 1,
          "wrong EventKey ACK cannot retire another event");
    const auto retry = runtime.next_message(237);
    check(retry && retry->node_id == first_attempt->node_id &&
          retry->session_id == first_attempt->session_id &&
          retry->sequence_number == first_attempt->sequence_number,
          "retry preserves the complete EventKey");
    check(runtime.acknowledge(*retained_key, gs::AckClass::Durable) && runtime.persisted() == 0,
          "Durable application ACK retires the intended retained event");

    gs::node::NodeRuntime next_boot("ack-node", 43);
    const auto next_boot_key = next_boot.record(gs::EventKind::Motion, "room1", 0, 0);
    check(next_boot_key && next_boot_key->sequence == retained_key->sequence &&
          next_boot_key->session_id != retained_key->session_id,
          "different boot sessions distinguish identical sequence numbers");

    gs::hub::HubRuntime hub(4, 8);
    hub.authorize_node("ack-node", 43, false);
    check(!hub.radio_message_callback(*first_attempt, 0),
          "HubRuntime rejects an unauthorized stale session");

    FakeSessionStore session_store;
    const auto first_session = wire::next_boot_session(session_store);
    const auto second_session = wire::next_boot_session(session_store);
    check(first_session == 1 && second_session == 2 && session_store.persisted == 2,
          "persistent boot-session policy advances across boots");
    session_store.save_ok = false;
    check(!wire::next_boot_session(session_store),
          "boot-session policy fails closed when durable commit fails");
}

void test_security_seams() {
    gs::security::CredentialRegistry registry;
    check(registry.install({"node-1", "nvs:key:1", 1}), "credential reference installs");
    check(!registry.install({"node-1", "nvs:key:old", 1}), "credential rollback rejected");
    check(registry.revoke("node-1"), "credential can be revoked");

    AcceptingVerifier verifier;
    gs::security::UpdatePolicy updates(verifier);
    const gs::security::UpdateManifest manifest{"esp32-c3", 2, std::string(64, 'a'), "test-signature"};
    check(updates.validate(manifest, "esp32-c3", 1).accepted, "valid signed manifest policy accepts");
    check(!updates.validate(manifest, "esp32-s3", 1).accepted, "wrong board manifest rejected");
    check(!updates.validate(manifest, "esp32-c3", 2).accepted, "firmware rollback rejected");
}

void test_logging_policy() {
    CountingSink sink;
    gs::log::set_sink(&sink);
    GS_ERROR(gs::log::Category::Test, "T01", "forced.error", "test_only");
    GS_TRACE(gs::log::Category::Test, "T01", "forced.trace", "test_only");
    check(sink.errors == 1, "ERROR logging is always compiled");
#if GS_ENABLE_TRACE
    check(sink.traces == 1, "TRACE logging is enabled in development build");
#else
    check(sink.traces == 0, "TRACE logging compiles out in production build");
#endif
}

void test_feature_flag_defaults() {
    check(gs::FeatureFlags::enabled(gs::Feature::MorningRoutine) == (GS_FEATURE_MORNING_ROUTINE != 0), "morning flag maps to build");
    check(gs::FeatureFlags::enabled(gs::Feature::TemperatureContext) == (GS_FEATURE_TEMP_CONTEXT != 0), "P1 flag maps to build");
    check(std::string(gs::FeatureFlags::name(gs::Feature::CallFamily)) == "call_family", "flag names are stable");
}

}  // namespace

int main() {
    const char* configured = std::getenv("GS_LOG_FILE");
    gs::host::FileLogSink sink(configured ? configured : "logs/cpp_validation.txt", 65536, 2);
    gs::log::set_sink(&sink);
    try {
        test_node_modules();
        test_hub_modules();
        test_bat_c5_health_and_lease();
        test_protocol_and_generic_rules();
        test_node_offline_resilience();
        test_node_power_diagnostics();
        test_node_outage_profile();
        test_data_plane_codec_and_ack_policy();
        test_security_seams();
        test_logging_policy();
        test_feature_flag_defaults();
        std::cout << "cpp: " << checks << " checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "cpp test failure: " << error.what() << "\n";
        return 1;
    }
}
