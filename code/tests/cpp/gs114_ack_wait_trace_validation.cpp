#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "power/power.hpp"
#include "tests/support/host/security/openssl_commissioning_crypto.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

unsigned checks = 0;

void check(bool condition, const char* message) {
    ++checks;
    if (!condition) throw std::runtime_error(message);
}

gs::node::LightSleepObservation idle_observation(gs::Milliseconds now) {
    gs::node::LightSleepObservation result;
    result.now_ms = now;
    result.next_health_ms = now + 300000;
    result.next_retry_ms = now + 60000;
    result.authenticated = true;
    result.product_ready = true;
    result.persistence_clean = true;
    result.pir_high = false;
    result.pir_low_stable = true;
    result.debounce_safe = true;
    result.wake_source_ready = true;
    result.runtime_state_known = true;
    return result;
}

gs::node::LightSleepDecision blocked_ack_decision() {
    gs::node::LightSleepDecision result;
    result.inhibitors = gs::node::LightSleepInhibitPendingTx |
                        gs::node::LightSleepInhibitAckWait;
    result.eligible = false;
    return result;
}

void test_successful_mac_waits_for_exact_durable_ack() {
    using namespace gs;
    using namespace gs::node;
    const EventKey key{"node-01", 77, 9};
    C8AckWaitTraceRecorder recorder(key.source_id, 0x10203040U);
    AckListeningWindow listening;
    recorder.note_mac_result(key, true, 1000);
    listening.application_transport_completed(1000, true);

    auto waiting = idle_observation(12000);
    waiting.outage_active = true;
    observe_retained_delivery(waiting, listening, true, true);
    const auto decision = evaluate_light_sleep(waiting);
    check(!decision.eligible && waiting.ack_wait &&
              (decision.inhibitors & LightSleepInhibitPendingTx) != 0U &&
              (decision.inhibitors & LightSleepInhibitAckWait) != 0U,
          "successful MAC keeps exact pending K awake beyond receive budget");
    recorder.note_sleep_decision(waiting.ack_wait, &key, decision, waiting.now_ms);
    check(recorder.snapshot().interval_open && !recorder.report_ready(),
          "wait stays open until authenticated Durable ACK");

    recorder.note_durable_ack(key, AckClass::Durable, true, true, 13000);
    listening.authenticated_progress(true);
    auto idle = idle_observation(13001);
    observe_retained_delivery(idle, listening, false, false);
    const auto idle_decision = evaluate_light_sleep(idle);
    check(idle_decision.eligible,
          "normal sleep eligibility returns after exact Durable ACK retirement");
    recorder.note_sleep_decision(false, nullptr, idle_decision, idle.now_ms);
    recorder.note_sleep_entry(13010, false);
    recorder.note_wake(13050, 1U, 1U);

    const auto trace = recorder.snapshot();
    check(recorder.report_ready() && trace.evidence_complete &&
              trace.sleep_entries_during_ack_wait == 0U &&
              trace.post_ack_sleep_entries == 1U &&
              (trace.flags & NodeHealthSnapshot::C8AckWaitTrace::PostAckWakeObserved) != 0U,
          "completed trace contains ordered wait, retirement, real sleep entry and wake");
}

void test_failed_transport_window_and_retry_sleep() {
    using namespace gs;
    using namespace gs::node;
    const EventKey key{"node-02", 78, 10};
    C8AckWaitTraceRecorder recorder(key.source_id, 0x20304050U);
    AckListeningWindow listening;
    recorder.note_mac_result(key, false, 1000);
    listening.application_transport_completed(1000, false);

    auto bounded = idle_observation(10999);
    bounded.outage_active = true;
    observe_retained_delivery(bounded, listening, true, true);
    auto decision = evaluate_light_sleep(bounded);
    check(!decision.eligible && bounded.ack_wait,
          "failed transport preserves bounded application receive opportunity");
    recorder.note_sleep_decision(bounded.ack_wait, &key, decision, bounded.now_ms);

    auto after_window = idle_observation(11000);
    after_window.outage_active = true;
    observe_retained_delivery(after_window, listening, true, true);
    decision = evaluate_light_sleep(after_window);
    check(!after_window.ack_wait && decision.eligible,
          "confirmed failed transport permits sleep after the receive boundary");
    recorder.note_sleep_decision(false, &key, decision, after_window.now_ms);
    recorder.note_sleep_entry(11010, false);
    recorder.note_wake(41010, 1U, 1U);

    recorder.note_mac_result(key, true, 61000);
    recorder.note_sleep_decision(true, &key, blocked_ack_decision(), 61001);
    recorder.note_durable_ack(key, AckClass::Durable, true, true, 61020);
    auto idle = idle_observation(61021);
    const auto idle_decision = evaluate_light_sleep(idle);
    recorder.note_sleep_decision(false, nullptr, idle_decision, idle.now_ms);
    recorder.note_sleep_entry(61030, false);
    recorder.note_wake(61070, 2U, 1U);

    const auto trace = recorder.snapshot();
    check(trace.evidence_complete && trace.sleep_entries_during_ack_wait == 0U,
          "retry wait and exact-key retirement remain independently traceable");
    bool retry_sleep = false;
    bool post_ack_sleep = false;
    for (std::size_t i = 0; i < trace.event_count; ++i) {
        const auto& event = trace.events[i];
        if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepEntry &&
            event.value == 2U) retry_sleep = true;
        if (event.kind == NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepEntry &&
            event.value == 0U) post_ack_sleep = true;
    }
    check(retry_sleep && post_ack_sleep,
          "trace distinguishes legitimate sleep between retries from post-ACK sleep");
}

void test_late_ack_after_bounded_window_is_incomplete() {
    using namespace gs;
    using namespace gs::node;
    const EventKey key{"node-05", 78, 10};
    C8AckWaitTraceRecorder recorder(key.source_id, 105U);
    recorder.note_mac_result(key, false, 1000);
    recorder.note_sleep_decision(true, &key, blocked_ack_decision(), 2000);
    const LightSleepDecision retry_sleep{LightSleepInhibitNone, 70000, 30000, true};
    recorder.note_sleep_decision(false, &key, retry_sleep, 10000);
    recorder.note_durable_ack(key, AckClass::Durable, true, true, 10100);

    const auto trace = recorder.snapshot();
    check(recorder.report_ready(),
          "late exact authenticated Durable ACK is recorded after bounded receive closure");
    check((trace.flags & NodeHealthSnapshot::C8AckWaitTrace::MissingInterval) != 0U &&
              trace.missing_intervals != 0U && !trace.evidence_complete,
          "late ACK without an observed receive interval cannot claim complete evidence");
}

void test_bad_keys_watchdog_overflow_and_reset_are_incomplete() {
    using namespace gs;
    using namespace gs::node;
    const EventKey key{"node-03", 79, 11};
    C8AckWaitTraceRecorder wrong_key_trace(key.source_id, 101U);
    wrong_key_trace.note_mac_result(key, true, 1000);
    const EventKey wrong{key.source_id, key.session_id, key.sequence + 1U};
    wrong_key_trace.note_durable_ack(wrong, AckClass::Durable, true, true, 1100);
    wrong_key_trace.note_durable_ack(key, AckClass::Durable, false, true, 1200);
    wrong_key_trace.note_durable_ack(key, AckClass::ReceivedVolatile, true, true, 1300);
    check(!wrong_key_trace.report_ready() &&
              (wrong_key_trace.snapshot().flags &
               NodeHealthSnapshot::C8AckWaitTrace::EventKeyMismatch) != 0U,
          "wrong-key ACK is recorded as mismatch and unauthenticated/volatile ACKs do not retire");

    C8AckWaitTraceRecorder watchdog(key.source_id, 102U);
    watchdog.note_mac_result(key, true, 1000);
    watchdog.note_sleep_decision(true, &key, blocked_ack_decision(), 31001);
    check(watchdog.snapshot().interval_open &&
              (watchdog.snapshot().flags &
               NodeHealthSnapshot::C8AckWaitTrace::WatchdogExpired) != 0U,
          "diagnostic watchdog marks incomplete while leaving product ACK wait open");
    watchdog.note_session_replaced(32000);
    check(!watchdog.snapshot().evidence_complete &&
              watchdog.snapshot().missing_intervals != 0U,
          "session replacement preserves incomplete pre-reset evidence");

    C8AckWaitTraceRecorder overflow(key.source_id, 103U);
    for (std::uint32_t attempt = 0; attempt < 4U; ++attempt) {
        const auto start = static_cast<Milliseconds>(1000U + attempt * 100U);
        overflow.note_mac_result(key, false, start);
        const auto eligible = LightSleepDecision{LightSleepInhibitNone, start + 60000,
                                                  30000, true};
        overflow.note_sleep_decision(false, &key, eligible, start + 1);
        overflow.note_sleep_entry(start + 2, false);
        overflow.note_wake(start + 3, 1U, 1U);
    }
    check(overflow.snapshot().overflow_count != 0U &&
              (overflow.snapshot().flags &
               NodeHealthSnapshot::C8AckWaitTrace::Overflow) != 0U &&
              !overflow.snapshot().evidence_complete,
          "bounded event buffer reports overflow instead of claiming completeness");

    C8AckWaitTraceRecorder next_boot(key.source_id, 104U);
    check(next_boot.snapshot().boot_generation != watchdog.snapshot().boot_generation,
          "each boot generation is distinguishable and never spliced across reset");
}

void test_exact_key_retirement_contract() {
    using namespace gs;
    using namespace gs::security;
    using gs::host::security::OpenSslCommissioningCrypto;
    node::NodeRuntime runtime("node-04", 80);
    const auto admitted = runtime.record(EventKind::Motion, "room", 100, 1700000000);
    check(admitted.has_value(), "production NodeRuntime admits test event");
    const auto key = *admitted;
    const EventKey wrong{key.source_id, key.session_id, key.sequence + 1U};
    OpenSslCommissioningCrypto crypto;
    CommissioningBinding binding;
    binding.device_id = "test-device";
    binding.logical_id = "node-04";
    binding.home_id = "test-home";
    binding.hub_id = "test-hub";
    binding.installation_key.fill(5U);
    auto foreign_binding = binding;
    foreign_binding.home_id = "wrong-home";
    RuntimeFrameSecurity node_frames(crypto, binding);
    RuntimeFrameSecurity hub_frames(crypto, binding);
    RuntimeFrameSecurity foreign_frames(crypto, foreign_binding);
    Key32 salt{};
    salt.fill(7U);
    check(node_frames.start(key.session_id, salt) &&
              hub_frames.start(key.session_id, salt) &&
              foreign_frames.start(key.session_id, salt),
          "ACK endpoints use an authenticated session context");
    const auto encode_ack = [&](const EventKey& event_key, AckClass ack_class) {
        NodeAckMessage ack;
        ack.node_id = event_key.source_id;
        ack.session_id = event_key.session_id;
        ack.sequence_number = event_key.sequence;
        ack.ack_type = ack_class;
        return transport::encode_node_ack(ack);
    };
    transport::EncodedFrame plain;
    SecureFrame unauthenticated;
    check(!node_frames.open(RuntimeDirection::Downlink, unauthenticated, plain),
          "unprotected bytes cannot enter ACK acceptance");
    const auto wrong_key_payload = encode_ack(wrong, AckClass::Durable);
    SecureFrame foreign_ack;
    check(wrong_key_payload && foreign_frames.seal(RuntimeDirection::Downlink,
              wrong_key_payload.frame, foreign_ack) &&
              !node_frames.open(RuntimeDirection::Downlink, foreign_ack, plain),
          "wrong-owner authenticated Durable ACK is rejected by frame authentication");

    const auto volatile_payload = encode_ack(key, AckClass::ReceivedVolatile);
    SecureFrame volatile_ack;
    check(volatile_payload && hub_frames.seal(RuntimeDirection::Downlink,
              volatile_payload.frame, volatile_ack) &&
              node_frames.open(RuntimeDirection::Downlink, volatile_ack, plain),
          "same-session volatile ACK is authenticated but decoded separately");
    auto volatile_decoded = transport::decode_node_ack(plain.bytes.data(), plain.size);
    check(volatile_decoded && !runtime.acknowledge(
              EventKey{volatile_decoded.value->node_id,
                       volatile_decoded.value->session_id,
                       volatile_decoded.value->sequence_number},
              volatile_decoded.value->ack_type) && runtime.pending() == 1U,
          "authenticated non-Durable ACK retains the event");

    const auto durable_payload = encode_ack(key, AckClass::Durable);
    SecureFrame durable_ack;
    check(durable_payload && hub_frames.seal(RuntimeDirection::Downlink,
              durable_payload.frame, durable_ack) &&
              node_frames.open(RuntimeDirection::Downlink, durable_ack, plain),
          "matching authenticated Durable ACK opens");
    auto durable_decoded = transport::decode_node_ack(plain.bytes.data(), plain.size);
    check(durable_decoded && runtime.acknowledge(
              EventKey{durable_decoded.value->node_id,
                       durable_decoded.value->session_id,
                       durable_decoded.value->sequence_number},
              durable_decoded.value->ack_type) && runtime.pending() == 0U &&
              runtime.persisted() == 0U,
          "only exact-key Durable ACK retires the event");
    check(!node_frames.open(RuntimeDirection::Downlink, durable_ack, plain) &&
              !runtime.acknowledge(key, AckClass::Durable),
          "replayed authenticated ACK cannot produce a second retirement");
}

gs::NodeHealthSnapshot completed_report() {
    using namespace gs;
    using namespace gs::node;
    const EventKey key{"abcdefghijklmnopqrstuvwx", 81, 13};
    C8AckWaitTraceRecorder recorder(key.source_id, 0xaabbccddU);
    recorder.note_mac_result(key, true, 1000);
    recorder.note_sleep_decision(true, &key, blocked_ack_decision(), 12000);
    recorder.note_durable_ack(key, AckClass::Durable, true, true, 13000);
    const auto idle = LightSleepDecision{LightSleepInhibitNone, 300000, 30000, true};
    recorder.note_sleep_decision(false, nullptr, idle, 13001);
    recorder.note_sleep_entry(13010, false);
    recorder.note_wake(13050, 1U, 1U);

    NodeHealthSnapshot health;
    health.schema = NodeHealthSnapshot::c8_ack_wait_trace_schema_version;
    health.node_id = key.source_id;
    health.session_id = key.session_id;
    health.health_sequence = 1;
    health.uptime_ms = 13050;
    health.reset_reason = 3;
    health.c8_ack_wait_trace = recorder.snapshot();
    return health;
}

void test_authenticated_nodehealth_round_trip_and_size() {
    using namespace gs;
    using namespace gs::security;
    using gs::host::security::OpenSslCommissioningCrypto;
    auto health = completed_report();
    const auto encoded = transport::encode_node_health(health);
    check(encoded && health.c8_ack_wait_trace->evidence_complete,
          "complete C8 trace serializes as NodeHealth schema 4");
    check(encoded.frame.size <= kMaximumSecureFrameBytes - kSecureFrameOverhead,
          "maximum EventKey and trace fit authenticated ESP-NOW plaintext limit");

    OpenSslCommissioningCrypto crypto;
    CommissioningBinding binding;
    binding.device_id = "test-device";
    binding.logical_id = health.node_id;
    binding.home_id = "test-home";
    binding.hub_id = "test-hub";
    binding.installation_key.fill(9U);
    RuntimeFrameSecurity node(crypto, binding);
    RuntimeFrameSecurity hub(crypto, binding);
    Key32 salt{};
    salt.fill(3U);
    check(node.start(health.session_id, salt) && hub.start(health.session_id, salt),
          "test endpoints establish same authenticated session context");
    SecureFrame protected_health;
    check(node.seal(RuntimeDirection::Uplink, encoded.frame, protected_health) &&
              protected_health.size <= kMaximumSecureFrameBytes,
          "schema 4 report fits the secured 250-byte frame");
    auto tampered = protected_health;
    tampered.bytes[tampered.size - 1U] ^= 0x80U;
    transport::EncodedFrame plain;
    check(!hub.open(RuntimeDirection::Uplink, tampered, plain),
          "altered diagnostic report fails authentication");
    check(hub.open(RuntimeDirection::Uplink, protected_health, plain),
          "authenticated diagnostic report opens after tamper rejection");
    const auto decoded = transport::decode_node_health(plain.bytes.data(), plain.size);
    check(decoded && decoded.value->c8_ack_wait_trace &&
              decoded.value->c8_ack_wait_trace->event_key_sequence == 13U &&
              decoded.value->c8_ack_wait_trace->evidence_complete,
          "Hub decodes the authenticated exact-key, ordered trace");

    auto malformed = *health.c8_ack_wait_trace;
    malformed.event_count = static_cast<std::uint8_t>(malformed.events.size() + 1U);
    health.c8_ack_wait_trace = malformed;
    check(!transport::encode_node_health(health),
          "trace count above the fixed buffer is rejected before serialization");
}

void test_hub_accepts_trace_without_replacing_full_health() {
    using namespace gs;
    auto trace_report = completed_report();
    hub::HubRuntime runtime(32, 128);
    runtime.authorize_node(trace_report.node_id, trace_report.session_id, true);

    NodeHealthSnapshot baseline;
    baseline.schema = NodeHealthSnapshot::schema_version;
    baseline.node_id = trace_report.node_id;
    baseline.session_id = trace_report.session_id;
    baseline.health_sequence = 1;
    baseline.free_heap = 41000;
    check(runtime.observe_authenticated_health(
              baseline, baseline.node_id, baseline.session_id, 1000),
          "Hub accepts ordinary authenticated NodeHealth first");

    trace_report.health_sequence = 2;
    trace_report.free_heap = 0;
    check(runtime.observe_authenticated_health(
              trace_report, trace_report.node_id, trace_report.session_id, 2000),
          "Hub accepts authenticated compact trace as a contact refresh");
    const auto retained = runtime.node_health(trace_report.node_id);
    check(retained && retained->snapshot.health_sequence == 1U &&
              retained->snapshot.free_heap == 41000U,
          "compact trace does not replace the last full operational health snapshot");
}

void test_maximum_compact_trace_frame() {
    using namespace gs;
    NodeHealthSnapshot health;
    health.schema = NodeHealthSnapshot::c8_ack_wait_trace_schema_version;
    health.node_id = std::string(transport::kMaxSourceIdBytes, 'n');
    health.session_id = 82;
    health.health_sequence = 1;
    NodeHealthSnapshot::C8AckWaitTrace trace;
    trace.boot_generation = 1;
    trace.event_key_session_id = 82;
    trace.event_key_sequence = 14;
    trace.sleep_reason_count = 1;
    trace.sleep_reason_masks[0] = node::LightSleepInhibitAckWait;
    trace.event_count = static_cast<std::uint8_t>(trace.events.size());
    for (std::size_t i = 0; i < trace.events.size(); ++i) {
        const auto slot = i % 4U;
        auto& event = trace.events[i];
        event.uptime_ms = static_cast<std::uint32_t>(i * 100U);
        if (slot == 0U) {
            event.kind = NodeHealthSnapshot::C8AckWaitTrace::EventKind::MacResult;
            event.value = 0U;
        } else if (slot == 1U) {
            event.kind = NodeHealthSnapshot::C8AckWaitTrace::EventKind::AckWaitStart;
            event.value = 0U;
        } else if (slot == 2U) {
            event.kind = NodeHealthSnapshot::C8AckWaitTrace::EventKind::SleepInhibited;
            event.value = 0U;
        } else {
            event.kind = NodeHealthSnapshot::C8AckWaitTrace::EventKind::AckWaitEnd;
            event.value = static_cast<std::uint8_t>(
                NodeHealthSnapshot::C8AckWaitTrace::EndReason::ReceiveWindowElapsed);
        }
    }
    trace.sleep_inhibit_decisions = 4;
    trace.sleep_inhibitor_mask = node::LightSleepInhibitAckWait;
    health.c8_ack_wait_trace = trace;
    const auto encoded = transport::encode_node_health(health);
    check(encoded && encoded.frame.size == 220U && encoded.frame.size <=
              security::kMaximumSecureFrameBytes - security::kSecureFrameOverhead,
          "full 16-event trace is 220 plaintext bytes and remains within AEAD budget");
}

}  // namespace

int main() {
    try {
        test_successful_mac_waits_for_exact_durable_ack();
        test_failed_transport_window_and_retry_sleep();
        test_late_ack_after_bounded_window_is_incomplete();
        test_bad_keys_watchdog_overflow_and_reset_are_incomplete();
        test_exact_key_retirement_contract();
        test_authenticated_nodehealth_round_trip_and_size();
        test_hub_accepts_trace_without_replacing_full_health();
        test_maximum_compact_trace_frame();
        std::cout << "GS114 ACK-wait trace PASS checks=" << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "GS114 ACK-wait trace FAIL: " << error.what() << '\n';
        return 1;
    }
}
