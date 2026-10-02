#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/transport/node_retirement_protocol.hpp"
#include "firmware/node/components/storage/node_recovery_persistence.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>

namespace {
using namespace gs;
using namespace gs::transport;
using gs::host::security::OpenSslCommissioningCrypto;
using gs::node::NodeRuntime;
using gs::security::Bytes;
using gs::security::Key32;

void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}

EncodedFrame authenticated_roundtrip(gs::security::RuntimeFrameSecurity& frames,
                                     const EncodedFrame& plain) {
    gs::security::SecureFrame sealed;
    require(frames.seal(gs::security::RuntimeDirection::Uplink, plain, sealed),
            "fragment did not seal under authenticated Node uplink");
    EncodedFrame opened;
    require(frames.open(gs::security::RuntimeDirection::Uplink, sealed, opened),
            "authenticated fragment did not open");
    return opened;
}

void fragments_and_mac(OpenSslCommissioningCrypto& crypto) {
    Key32 install{}; install.fill(0x41);
    Key32 report_key{};
    require(derive_retirement_report_key(crypto, install, report_key),
            "retirement key derivation failed");
    NodeRuntime node("sensor", 10);
    require(node.set_retirement_epoch(7), "Hub epoch was not installed");
    for (unsigned i = 0; i < 32; ++i) {
        const auto kind = i % 2 == 0 ? EventKind::DoorOpen : EventKind::Heartbeat;
        require(node.record(kind, "room", i, 0).has_value(),
                "max report pending key setup failed");
    }
    NodeRetirementReportV1 report;
    require(make_retirement_report(node.recovery_snapshot(), report),
            "report did not come from recovery snapshot");
    Bytes logical;
    require(encode_retirement_report(report, logical) &&
            logical.size() == kMaxRetirementReportBytes && logical.size() == 542,
            "maximum report encoding size changed");
    RetirementFragmentSet fragments;
    require(fragment_retirement_report(crypto, report_key, report, fragments) &&
            fragments.count == 4, "maximum report was not split into four fragments");

    gs::security::CommissioningBinding binding;
    binding.home_id = "home"; binding.hub_id = "hub";
    binding.device_id = "device"; binding.logical_id = "sensor";
    binding.installation_key = install;
    gs::security::RuntimeFrameSecurity node_frames(crypto, binding);
    Key32 salt{}; salt.fill(0x22);
    require(node_frames.start(101, salt), "runtime frame session did not start");
    gs::security::RuntimeFrameSecurity hub_frames(crypto, binding);
    require(hub_frames.start(101, salt), "Hub runtime frame session did not start");
    const auto epoch_offer = encode_hub_storage_epoch(7);
    require(epoch_offer && classify_frame(epoch_offer.frame.bytes.data(),
                epoch_offer.frame.size) == FrameClass::HubStorageEpoch,
            "Hub epoch offer did not use the authenticated data plane");
    gs::security::SecureFrame protected_epoch;
    require(hub_frames.seal(gs::security::RuntimeDirection::Downlink,
                            epoch_offer.frame, protected_epoch),
            "Hub epoch offer did not seal");
    auto spoofed_epoch = protected_epoch;
    spoofed_epoch.bytes[spoofed_epoch.size - 1] ^= 1U;
    EncodedFrame spoof_plain;
    require(!node_frames.open(gs::security::RuntimeDirection::Downlink,
                              spoofed_epoch, spoof_plain),
            "spoofed Hub epoch passed authenticated frame verification");
    require(node_frames.open(gs::security::RuntimeDirection::Downlink,
                             protected_epoch, spoof_plain),
            "valid Hub epoch failed authenticated frame verification");
    const auto decoded_epoch = decode_hub_storage_epoch(spoof_plain.bytes.data(),
                                                         spoof_plain.size);
    require(decoded_epoch && *decoded_epoch.value == 7,
            "authenticated Hub epoch did not decode to its value");
    require(!encode_hub_storage_epoch(0),
            "epoch codec accepted zero");
    RetirementReportReassembler assembly;
    NodeRetirementReportV1 completed;
    Key32 completed_hmac{};
    const unsigned order[] = {3, 1, 1, 0, 2};
    bool complete = false;
    for (const auto index : order) {
        const auto plain = authenticated_roundtrip(node_frames, fragments.frames[index]);
        const auto result = assembly.accept(crypto, report_key, plain,
                                            completed, completed_hmac);
        if (index == 1 && result == RetirementAssemblyResult::DuplicateFragment) continue;
        if (index == 2) complete = result == RetirementAssemblyResult::Complete;
        else require(result == RetirementAssemblyResult::AcceptedFragment,
                     "out-of-order fragment was rejected or completed too early");
    }
    require(complete && completed.generation == report.generation &&
            completed.pending_count == 32 && completed_hmac == fragments.report_hmac,
            "authenticated out-of-order reassembly failed");
    require(fragments.frames[0].size <= 222,
            "plaintext fragment exceeds the secure frame input budget");

    assembly.reset();
    auto lost = authenticated_roundtrip(node_frames, fragments.frames[0]);
    require(assembly.accept(crypto, report_key, lost, completed, completed_hmac) ==
                RetirementAssemblyResult::AcceptedFragment,
            "partial report setup failed");
    assembly.reset();  // Timeout/abandon discards the bounded partial report.
    require(!assembly.active(), "abandoned report retained assembly state");

    auto newer = report;
    ++newer.generation;
    RetirementFragmentSet newer_fragments;
    require(fragment_retirement_report(crypto, report_key, newer, newer_fragments),
            "second report generation did not fragment");
    assembly.reset();
    auto first = authenticated_roundtrip(node_frames, fragments.frames[0]);
    auto mixed = authenticated_roundtrip(node_frames, newer_fragments.frames[1]);
    require(assembly.accept(crypto, report_key, first, completed, completed_hmac) ==
                RetirementAssemblyResult::AcceptedFragment &&
            assembly.accept(crypto, report_key, mixed, completed, completed_hmac) ==
                RetirementAssemblyResult::Rejected,
            "fragments from distinct report generations were combined");

    NodeRetirementAckV1 ack{7, report.generation, fragments.report_hmac};
    const auto encoded_ack = encode_node_retirement_ack(ack);
    NodeRetirementAckV1 decoded_ack;
    require(encoded_ack && decode_node_retirement_ack(encoded_ack.frame.bytes.data(),
                encoded_ack.frame.size, decoded_ack) && decoded_ack.epoch == ack.epoch &&
            decoded_ack.generation == ack.generation &&
            decoded_ack.report_hmac == ack.report_hmac,
            "report ACK codec roundtrip failed");
}

void heartbeat_retirement_and_admission() {
    NodeRuntime node("sensor", 5);
    require(node.set_retirement_epoch(7), "epoch set failed");
    const auto key = node.record(EventKind::Heartbeat, "", 1, 0);
    require(key && node.pending() == 1 && node.persisted() == 0,
            "sequenced heartbeat admission failed");
    auto before = node.recovery_snapshot();
    NodeRetirementReportV1 report;
    require(make_retirement_report(before, report) && report.pending_count == 1 &&
            report.pending[0] == RetirementEventKey{5, key->sequence} &&
            report.durable_admission_highwater == key->sequence,
            "heartbeat missing from complete pending EventKey report");

    NodeRuntime rebooted("sensor", 6);
    require(rebooted.restore_recovery(before, 0), "heartbeat did not restore after reboot");
    auto after_boot = rebooted.recovery_snapshot();
    require(after_boot.pending.size() == 1 &&
            after_boot.pending[0].event.kind == EventKind::Heartbeat &&
            after_boot.pending[0].event.key.session_id == 5,
            "heartbeat EventKey changed during reboot");

    const auto pending_gen = rebooted.pending_generation();
    const auto report_gen = after_boot.report_generation;
    // Existing API reports false because NodeStore has no heartbeat record;
    // the queue mutation is separately observable and persisted by the owner.
    require(!rebooted.acknowledge(*key, AckClass::Durable) &&
            rebooted.pending() == 0 &&
            rebooted.pending_generation() > pending_gen,
            "heartbeat ACK did not expose pending-set change");
    const auto retired = rebooted.recovery_snapshot();
    require(retired.report_generation > report_gen && retired.pending.empty() &&
            make_retirement_report(retired, report) && report.pending_count == 0,
            "heartbeat retirement did not advance report state");

    NodeRuntime failed("sensor", 30, 0, 32);
    require(!failed.record(EventKind::Motion, "room", 3, 0),
            "zero-capacity business admission unexpectedly succeeded");
    const auto failed_state = failed.recovery_snapshot();
    require(failed_state.durable_admission_highwater == 0 &&
            failed_state.pending.empty(),
            "failed admission advanced durable highwater or became retryable");
    NodeRuntime failed_reboot("sensor", 31);
    require(failed_reboot.restore_recovery(failed_state, 0) &&
            failed_reboot.pending() == 0 &&
            failed_reboot.recovery_snapshot().durable_admission_highwater == 0,
            "failed sequence became retransmittable after reboot");
}

void highwater_and_health_scope(OpenSslCommissioningCrypto& crypto) {
    NodeRuntime node("sensor", 40);
    require(node.set_retirement_epoch(7), "epoch setup failed");
    for (unsigned i = 0; i < 9; ++i)
        require(node.record(EventKind::Motion, "room", i, 0).has_value(),
                "highwater prefix admission failed");
    require(node.record(EventKind::Motion, "room", 10, 0).has_value() &&
            node.record(EventKind::Heartbeat, "", 11, 0).has_value() &&
            node.record(EventKind::DoorOpen, "door", 12, 0).has_value(),
            "interleaved sequenced NodeMessages were not admitted");
    NodeRetirementReportV1 report;
    require(make_retirement_report(node.recovery_snapshot(), report) &&
            report.durable_admission_highwater == 12 && report.pending_count == 12 &&
            report.pending[9] == RetirementEventKey{40, 10} &&
            report.pending[10] == RetirementEventKey{40, 11} &&
            report.pending[11] == RetirementEventKey{40, 12},
            "Heartbeat did not participate in durable admission highwater");
    gs::NodeHealthSnapshot health;
    health.node_id = "sensor"; health.session_id = 40; health.health_sequence = 1;
    const auto health_frame = encode_node_health(health);
    require(health_frame && classify_frame(health_frame.frame.bytes.data(),
                health_frame.frame.size) == FrameClass::NodeHealth,
            "periodic NodeHealth did not use its separate control path");
    NodeRetirementReportV1 after_health;
    require(make_retirement_report(node.recovery_snapshot(), after_health) &&
            after_health.generation == report.generation &&
            after_health.durable_admission_highwater == report.durable_admission_highwater &&
            after_health.pending_count == report.pending_count,
            "unsequenced NodeHealth changed retirement EventKey state");
    const auto prior_generation = node.recovery_snapshot().report_generation;
    require(node.set_retirement_epoch(8) &&
            node.recovery_snapshot().report_generation == prior_generation + 1 &&
            node.recovery_snapshot().pending.size() == 12 &&
            !node.set_retirement_epoch(7),
            "epoch change did not preserve pending keys or reject a stale epoch");
    RetirementEnrollmentBinding identity_binding;
    Key32 journal_key{}; journal_key.fill(0x5a);
    require(derive_retirement_enrollment_binding(crypto, journal_key, "sensor",
                identity_binding) && identity_binding.slot < 10 &&
            identity_binding.generation != 0,
            "authenticated enrollment coordinate derivation failed");
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        fragments_and_mac(crypto);
        heartbeat_retirement_and_admission();
        highwater_and_health_scope(crypto);
        std::cout << "NODE RETIREMENT PROTOCOL HOST PASS bounded authenticated report and heartbeat retirement\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "NODE RETIREMENT PROTOCOL HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
