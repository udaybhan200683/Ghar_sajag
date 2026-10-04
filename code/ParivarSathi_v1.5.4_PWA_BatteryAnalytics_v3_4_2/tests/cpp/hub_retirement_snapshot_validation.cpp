#include "firmware/common/transport/node_retirement_protocol.hpp"
#include "firmware/hub/components/storage/node_retirement_snapshot.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>

namespace {
using namespace gs::hub::durable;
using namespace gs::transport;
using gs::security::Bytes;
using gs::security::Key32;
using gs::host::security::OpenSslCommissioningCrypto;

void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}

NodeRetirementReportV1 report(std::uint64_t generation,
                              std::uint64_t current_session,
                              std::uint64_t highwater,
                              std::initializer_list<RetirementEventKey> keys) {
    NodeRetirementReportV1 value;
    value.epoch = 7; value.generation = generation;
    value.current_origin_session = current_session;
    value.durable_admission_highwater = highwater;
    value.pending_count = static_cast<std::uint8_t>(keys.size());
    std::copy(keys.begin(), keys.end(), value.pending.begin());
    return value;
}

void report_replay_and_ledger(OpenSslCommissioningCrypto& crypto,
                              const Key32& key) {
    MemoryBlobStore blobs;
    RetirementSnapshotRepository repository(blobs, crypto, key, 7);
    RetirementSnapshot empty;
    empty.storage_epoch = 7; empty.generation = 1;
    std::array<std::uint8_t, 32> binding{}; binding.fill(0x44);
    Key32 mac1{}; mac1.fill(0x11);
    const auto first = report(1, 10, 12, {{10, 10}, {10, 11}, {10, 12}});
    RetirementSnapshot staged;
    require(repository.apply_authenticated_report(empty, binding, 0, 3, 10,
                first, mac1, staged) == RetirementReportApply::Prepared &&
            staged.node_count() == 1 && staged.occupancy_mask == 1 && staged.generation == 2,
            "first authenticated report was not staged");
    RetirementSnapshotReference ref;
    require(repository.prepare_bank(staged, 0, ref) && ref.valid() && ref.bank < 3,
            "verified report bank was not prepared");
    RetirementSnapshot restored;
    require(repository.load(ref, restored) && restored.generation == staged.generation &&
            restored.nodes[0].pending_count == 3,
            "selected report snapshot reference did not verify");
    require(repository.apply_authenticated_report(restored, binding, 0, 3, 10,
                first, mac1, staged) == RetirementReportApply::Duplicate,
            "same-generation identical report was not idempotent");
    auto conflict = first; conflict.durable_admission_highwater = 13;
    Key32 mac2{}; mac2.fill(0x22);
    require(repository.apply_authenticated_report(restored, binding, 0, 3, 10,
                conflict, mac2, staged) == RetirementReportApply::Conflict,
            "same-generation report conflict was accepted");
    auto older = first; older.generation = 0;
    require(repository.apply_authenticated_report(restored, binding, 0, 3, 10,
                older, mac1, staged) == RetirementReportApply::Invalid,
            "invalid zero-generation report accepted");

    ExactEventKeyLedger ledger;
    std::array<std::uint8_t, 32> digest{}; digest.fill(0xA1);
    require(ledger.classify(restored, 0, 3, 10, 11, digest) == ExactEventResult::New,
            "pending EventKey was rejected as new evidence");
    require(ledger.insert({0, 3, 10, 11, digest}), "exact evidence insert failed");
    require(ledger.classify(restored, 0, 3, 10, 11, digest) == ExactEventResult::Duplicate,
            "same EventKey and digest was not a duplicate");
    auto changed = digest; changed[0] ^= 1;
    require(ledger.classify(restored, 0, 3, 10, 11, changed) == ExactEventResult::Conflict,
            "same EventKey with changed digest was not fail-closed");

    const auto drained = report(2, 10, 12, {});
    Key32 mac3{}; mac3.fill(0x33);
    RetirementSnapshot retired;
    require(repository.apply_authenticated_report(restored, binding, 0, 3, 10,
                drained, mac3, retired) == RetirementReportApply::Prepared,
            "newer complete drained report was rejected");
    require(ledger.classify(retired, 0, 3, 10, 11, digest) == ExactEventResult::Stale &&
            ledger.erase_retirement_eligible(retired) && ledger.size() == 0,
            "report absence did not retire exact digest evidence");
    const auto resurrected = report(3, 10, 12, {{10, 11}});
    Key32 mac4{}; mac4.fill(0x44);
    require(repository.apply_authenticated_report(retired, binding, 0, 3, 10,
                resurrected, mac4, staged) == RetirementReportApply::Conflict,
            "newer report resurrected a previously retired EventKey");
}

void bounds_and_crashes(OpenSslCommissioningCrypto& crypto, const Key32& key) {
    RetirementSnapshot full;
    full.storage_epoch = 7; full.generation = 9; full.occupancy_mask = 0x03ff;
    for (std::size_t n = 0; n < full.node_count(); ++n) {
        auto& node = full.nodes[n];
        node.binding_digest.fill(static_cast<std::uint8_t>(n + 1));
        node.enrollment_generation = 1;
        node.report_generation = 1;
        node.report_hmac.fill(0x55);
        node.current_origin_session = 99;
        node.durable_admission_highwater = 100;
        node.pending_count = 32;
        for (std::size_t i = 0; i < node.pending_count; ++i)
            node.pending[i] = {99, i + 1};
    }
    Bytes blob;
    require(RetirementSnapshotRepository::encode(crypto, key, full, blob) &&
            blob.size() == kRetirementSnapshotBankBytes && blob.size() == 5777,
            "maximum compact report bank byte size changed");
    RetirementSnapshot decoded;
    require(RetirementSnapshotRepository::decode(crypto, key, blob, decoded) &&
            decoded.node_count() == 10 && decoded.nodes[9].pending_count == 32 &&
            blob.size() <= 5777,
            "maximum report bank failed authenticated roundtrip");

    MemoryBlobStore blobs;
    RetirementSnapshotRepository repository(blobs, crypto, key, 7);
    RetirementSnapshot prior;
    prior.storage_epoch = 7; prior.generation = 1;
    std::array<std::uint8_t, 32> identity{}; identity.fill(2);
    Key32 mac{}; mac.fill(1);
    auto first = report(1, 10, 0, {});
    RetirementSnapshot next;
    require(repository.apply_authenticated_report(prior, identity, 0, 1, 10,
                first, mac, next) == RetirementReportApply::Prepared,
            "baseline report setup failed");
    RetirementSnapshotReference old_ref;
    require(repository.prepare_bank(next, 0, old_ref), "prior bank setup failed");
    blobs.inject(FaultMode::PartialWrite);
    auto second = report(2, 10, 0, {}); second.generation = 2;
    Key32 mac2{}; mac2.fill(3);
    RetirementSnapshot newer;
    require(repository.apply_authenticated_report(next, identity, 0, 1, 10,
                second, mac2, newer) == RetirementReportApply::Prepared,
            "new report candidate setup failed");
    RetirementSnapshotReference bad_ref;
    require(!repository.prepare_bank(newer, static_cast<std::uint8_t>(1U << old_ref.bank),
                                     bad_ref),
            "partial bank write was accepted");
    blobs.power_cycle();
    require(repository.load(old_ref, decoded),
            "partial inactive bank damaged prior referenced snapshot");
}

void heartbeat_keeps_prior_session_open(OpenSslCommissioningCrypto& crypto,
                                        const Key32& key) {
    MemoryBlobStore blobs;RetirementSnapshotRepository repository(blobs,crypto,key,7);
    RetirementSnapshot state;state.storage_epoch=7;state.generation=1;
    std::array<std::uint8_t,32> binding{};binding.fill(0x61);
    Key32 mac1{};mac1.fill(0x71);RetirementSnapshot next;
    require(repository.apply_authenticated_report(state,binding,0,1,10,
                report(1,10,1,{{10,1}}),mac1,next)==RetirementReportApply::Prepared,
            "prior session heartbeat report was rejected");
    Key32 mac2{};mac2.fill(0x72);RetirementSnapshot newer;
    require(repository.apply_authenticated_report(next,binding,0,1,11,
                report(2,11,0,{{10,1}}),mac2,newer)==RetirementReportApply::Prepared,
            "new origin session incorrectly closed a pending heartbeat session");
    ExactEventKeyLedger ledger;std::array<std::uint8_t,32> digest{};digest.fill(0x81);
    require(ledger.classify(newer,0,1,10,1,digest)==ExactEventResult::New&&
            ledger.insert({0,1,10,1,digest}),
            "old-session heartbeat was treated as retired before its ACK");
    Key32 mac3{};mac3.fill(0x73);RetirementSnapshot drained;
    require(repository.apply_authenticated_report(newer,binding,0,1,11,
                report(3,11,0,{}),mac3,drained)==RetirementReportApply::Prepared &&
            ledger.classify(drained,0,1,10,1,digest)==ExactEventResult::Stale &&
            ledger.erase_retirement_eligible(drained) && ledger.size()==0,
            "verified drained report did not close old heartbeat session");
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        Key32 key{}; key.fill(0x77);
        report_replay_and_ledger(crypto, key);
        bounds_and_crashes(crypto, key);
        heartbeat_keeps_prior_session_open(crypto, key);
        std::cout << "HUB RETIREMENT SNAPSHOT HOST PASS bounded report bank and exact digest rules\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "HUB RETIREMENT SNAPSHOT HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
