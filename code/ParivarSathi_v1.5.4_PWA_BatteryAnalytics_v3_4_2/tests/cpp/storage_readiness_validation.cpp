// Focused HOST-ONLY readiness checks. PASS includes reproduction of explicitly
// named blockers; it does NOT mean production integration is ready.
#include "host/storage/admission_model.hpp"
#include "firmware/hub/components/storage/durable_transition.hpp"
#include "firmware/hub/components/storage/node_retirement_snapshot.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>

namespace {
namespace model = gs::host::storage;
namespace life = model::lifecycle;
namespace admission = model::admission;
namespace durable = gs::hub::durable;
using gs::security::Key32;
using gs::security::Bytes;
using gs::host::security::OpenSslCommissioningCrypto;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

void conditional_bound() {
    // W=32/C=0 is a proof parameter, NOT an approved critical policy.
    admission::Gate<32, 0> gate;
    Key32 digest{}; digest.fill(0x51);
    for (unsigned n = 0; n < 6; ++n) {
        life::Report report;
        report.generation = 2; report.high = 32; report.count = 32;
        for (unsigned s = 1; s <= 32; ++s)
            report.pending[s - 1] = {static_cast<std::uint8_t>(n), 1, 1, s};
        require(gate.select(n, report), "complete report selection");
        for (unsigned s = 1; s <= 64; ++s)
            require(gate.accept({static_cast<std::uint8_t>(n), 1, 1, s}, digest,
                    admission::Class::Normal) == life::Result::New, "bounded admission");
        require(gate.uncovered(n) == 32, "uncovered charge");
        require(gate.accept({static_cast<std::uint8_t>(n), 1, 1, 65}, digest,
                admission::Class::Normal) == life::Result::Full, "lost report stops new keys");
        const model::Key retry{static_cast<std::uint8_t>(n), 1, 1, 64};
        require(gate.accept(retry, digest, admission::Class::Normal) == life::Result::Duplicate,
                "full gate still permits exact retry");
        auto changed = digest; changed[0] ^= 1;
        require(gate.accept(retry, changed, admission::Class::Normal) == life::Result::Conflict,
                "changed retry conflicts");
        require(!gate.select(n, report), "replayed report cannot replenish");
        ++report.generation;
        require(gate.select(n, report) && gate.uncovered(n) == 32,
                "generation-only report cannot replenish");
        auto invalid = report; invalid.count = 33;
        require(!gate.select(n, invalid) && gate.uncovered(n) == 32,
                "invalid report cannot replenish");
    }
    require(gate.size() == 384, "six-owner conditional maximum");
    auto restored = gate; // Explicit atomic model assumption, not flash proof.
    require(restored.size() == 384 && restored.uncovered(0) == 32,
            "copied snapshot preserves charges");
    life::Report advanced;
    advanced.generation = 4; advanced.high = 64;
    advanced.count = 1; advanced.pending[0] = {0, 1, 1, 64};
    require(restored.select(0, advanced) && restored.size() == 321 &&
            restored.uncovered(0) == 0, "complete progress retires only absent covered keys");
    require(restored.accept({0, 1, 1, 64}, digest, admission::Class::Normal) == life::Result::Duplicate,
            "accepted but unretired key survives progress");
    require(restored.accept({0, 1, 1, 63}, digest, admission::Class::Normal) == life::Result::Stale,
            "retired key cannot resurrect");
    auto resurrect = advanced; ++resurrect.generation;
    resurrect.pending[0].sequence = 63;
    require(!restored.select(0, resurrect), "newer report cannot resurrect retired key");
    require(restored.accept({0, 2, 1, 65}, digest, admission::Class::Normal) == life::Result::Invalid,
            "replacement enrollment not implicitly authorized");
    std::cout << "CONDITIONAL_ADMISSION_PASS keys=384 lost_report=stop retry=preserved atomic_model_only=1\n";
}

void production_credit_counterexample() {
    durable::ExactEventKeyLedger ledger;
    durable::RetirementSnapshot report;
    report.storage_epoch = 7; report.generation = 1;
    Key32 digest{}; digest.fill(0x51);
    // One Node can admit, receive durable ACK and retire sequentially with
    // queue peak 1 while its later report is lost. Queue size is not lifetime.
    for (std::uint64_t s = 1; s <= 33; ++s) {
        require(ledger.classify(report, 0, 1, 1, s, digest) == durable::ExactEventResult::New,
                "existing ledger counterexample classification changed");
        require(ledger.insert({0, 1, 1, s, digest}), "existing ledger insert");
    }
    require(ledger.size() == 33 && !ledger.erase_retirement_eligible(report),
            "missing reports must not erase evidence");
    std::cout << "PRODUCTION_CREDIT_BLOCKER uncovered_one_owner=33 node_queue_peak_can_be=1\n";
}

void selected_root_counterexample(OpenSslCommissioningCrypto& crypto, const Key32& key,
                                  bool missing) {
    durable::MemoryBlobStore blobs;
    durable::DurableStore store(blobs, crypto, key, 7);
    durable::Checkpoint cp;
    cp.storage_epoch = 7; cp.generation = 1;
    cp.reducer_state = {0x11};
    require(store.checkpoint(cp), "old root publication");
    cp.generation = 2; cp.reducer_state = {0x22};
    require(store.checkpoint(cp), "new root publication");
    durable::RecoveryState state;
    require(store.recover(state) && state.checkpoint_generation == 2 &&
            state.checkpoint.reducer_state == Bytes{0x22}, "new root verified");
    Bytes bank; bool found = false;
    require(blobs.read("cp1", bank, found) && found, "selected bank read");
    if (missing) require(blobs.erase_if_equals("cp1", bank), "remove selected bank fixture");
    else { bank.back() ^= 1; require(blobs.replace("cp1", bank), "damage selected bank fixture"); }
    blobs.power_cycle();
    durable::DurableStore reboot(blobs, crypto, key, 7);
    require(reboot.recover(state) && state.checkpoint_generation == 1 &&
            state.checkpoint.reducer_state == Bytes{0x11}, "selected root fallback reproduced");
    // This expectation records a blocker, NOT desired future acceptance behavior.
    std::cout << "ROOT_FRESHNESS_BLOCKER selected_child=" << (missing ? "missing" : "corrupt")
              << " published_generation=2 recovered_generation=1 reducer=old\n";
}

void report_reference_protection(OpenSslCommissioningCrypto& crypto, const Key32& key) {
    durable::MemoryBlobStore blobs;
    durable::RetirementSnapshotRepository repository(blobs, crypto, key, 7);
    durable::RetirementSnapshot snapshot;
    snapshot.storage_epoch = 7; snapshot.generation = 1;
    durable::RetirementSnapshotReference old, selected, candidate;
    require(repository.prepare_bank(snapshot, 0, old), "old report bank");
    ++snapshot.generation;
    require(repository.prepare_bank(snapshot, 1U << old.bank, selected), "selected report bank");
    ++snapshot.generation;
    blobs.inject(durable::FaultMode::PartialWrite);
    require(!repository.prepare_bank(snapshot, 1U << selected.bank, candidate), "candidate torn");
    blobs.power_cycle();
    durable::RetirementSnapshot loaded;
    require(repository.load(selected, loaded) && !repository.load(old, loaded),
            "selected-only mask overwrites old-root dependency");
    std::cout << "REPORT_OWNER_BLOCKER selected_only_mask=old_root_child_damaged selected_child=valid\n";

    // Smallest reuse: the same repository can protect both live root references.
    durable::MemoryBlobStore safe_blobs;
    durable::RetirementSnapshotRepository safe(safe_blobs, crypto, key, 7);
    snapshot.generation = 1;
    require(safe.prepare_bank(snapshot, 0, old), "safe old bank");
    ++snapshot.generation;
    require(safe.prepare_bank(snapshot, 1U << old.bank, selected), "safe selected bank");
    ++snapshot.generation;
    safe_blobs.inject(durable::FaultMode::PartialWrite);
    require(!safe.prepare_bank(snapshot, (1U << old.bank) | (1U << selected.bank), candidate),
            "protected candidate torn");
    safe_blobs.power_cycle();
    require(safe.load(old, loaded) && safe.load(selected, loaded), "both root dependencies preserved");
    std::cout << "REPORT_UNION_MASK_PASS both_old_and_selected_children_survive=1\n";
}
}

int main() {
    try {
        conditional_bound();
        production_credit_counterexample();
        OpenSslCommissioningCrypto crypto;
        Key32 key{}; key.fill(0x77); // Synthetic host key only.
        selected_root_counterexample(crypto, key, false);
        selected_root_counterexample(crypto, key, true);
        report_reference_protection(crypto, key);
        std::cout << "STORAGE_READINESS_HOST_PASS readiness=NO blockers_reproduced=4\n";
    } catch (const std::exception& error) {
        std::cerr << "STORAGE_READINESS_HOST_FAIL " << error.what() << '\n';
        return 1;
    }
}
