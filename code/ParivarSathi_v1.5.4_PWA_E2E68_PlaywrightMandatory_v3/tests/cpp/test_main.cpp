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

    gs::node::NodeRuntime runtime("node-rt", 3);
    const auto key = runtime.record(gs::EventKind::Motion, "room", 100, 10);
    check(key.has_value() && runtime.persisted() == 1, "node runtime persists before transmit");
    check(runtime.next_transmission(100).has_value(), "node runtime exposes due transmission");
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
}


void test_protocol_and_generic_rules() {
    check(gs::NodeProtocolPolicy::heartbeat_seconds == 60, "node heartbeat interval is frozen at 60 seconds");
    check(gs::NodeProtocolPolicy::offline_after_seconds == 190, "three missed heartbeats plus grace means offline");
    check(gs::NodeProtocolPolicy::retry_delays_ms[0] == 200 && gs::NodeProtocolPolicy::retry_delays_ms[3] == 10000,
          "bounded retry schedule is shared by protocol code");

    gs::node::NodeRuntime node_runtime("proto-node", 11);
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
    const auto processed = hub_runtime.run_state_once(2 * 60);
    check(processed.has_value() && processed->rule_signals.size() == 1 &&
          processed->rule_signals[0].kind == gs::RuleSignalKind::UnexpectedDoorOpen,
          "hub adapter feeds generic events into the hardware-independent rule engine");
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
        test_protocol_and_generic_rules();
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
