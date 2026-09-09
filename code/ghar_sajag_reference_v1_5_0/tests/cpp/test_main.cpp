// Ghar Sajag traceability edition 2.0 | source release 1.4.2
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
    gs::HomeConfig desired{1, "home-1", "Asia/Kolkata", gs::HomeMode::Home, config};
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
