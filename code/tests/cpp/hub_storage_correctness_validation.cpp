// Production persistence/runtime fixtures, shared with the existing checkpoint
// and mixed-body suites. No replica storage state machine.
#define GS_CHECKPOINT_EMBEDDED
#include "hub_runtime_checkpoint_validation.cpp"

namespace {
class HaltedBlobStore final : public gs::hub::durable::BlobStore {
public:
    gs::hub::durable::MemoryBlobStore backing;
    std::string halt_after;
    bool halted{false};
    bool read(const std::string& name, Bytes& bytes, bool& found) override {
        return !halted && backing.read(name, bytes, found);
    }
    bool write_immutable(const std::string& name, const Bytes& bytes) override {
        if (halted) return false;
        const bool result = backing.write_immutable(name, bytes);
        if (result && name == halt_after) { halted = true; return false; }
        return result;
    }
    bool replace(const std::string& name, const Bytes& bytes) override {
        if (halted) return false;
        const bool result = backing.replace(name, bytes);
        if (result && name == halt_after) { halted = true; return false; }
        return result;
    }
    bool erase_if_equals(const std::string& name, const Bytes& bytes) override {
        return !halted && backing.erase_if_equals(name, bytes);
    }
    void power_cycle() { halted = false; halt_after.clear(); backing.power_cycle(); }
};

void admission_refusal_test() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    OutboxLimits limits;
    limits.segment_count = 1;
    limits.segment_bytes = 512;
    limits.filesystem_workspace_bytes = 512;
    limits.protected_capacity_bytes = 512;
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    DurableEventOutbox outbox(segments, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "capacity fixture recovery");
    OutboxJournalBackend backend(outbox);
    RuntimeStateStore state(files, crypto, key);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    require(runtime.restore_from_journal(), "capacity fixture initialization");
    for (std::uint64_t seq = 1; seq <= 12; ++seq) {
        auto e = event(seq);
        runtime.authorize_node(e.key.source_id, e.key.session_id, true);
        require(runtime.radio_callback(e), "ordinary refusal queued");
        const auto original = files.files;
        const auto writes = files.writes;
        const auto result = runtime.run_state_once(100);
        require(result && result->ack == gs::AckClass::Rejected &&
                !result->state_changed && outbox.record_count() == 0,
                "ordinary reserve refusal must withhold Durable ACK");
        require(files.files == original && files.writes == writes && state.identities() == 0,
                "GS148-ARCH-010 predictable Full stranded a prepared identity");
        require(runtime.durable_admission_open(), "predictable refusal must preserve admission health");
    }
    for (int boot = 0; boot < 2; ++boot) {
        RuntimeStateStore restored(files, crypto, key);
        gs::hub::HubRuntime reboot(32, backend);
        reboot.bind_runtime_state(restored);
        require(reboot.restore_from_journal() && restored.identities() == 0,
                "repeated refusal reboot must have no prepared owner");
    }
    auto protected_event = event(100);
    protected_event.kind = gs::EventKind::DoorOpen;
    require(runtime.radio_callback(protected_event), "protected event queued after refusal");
    auto accepted = runtime.run_state_once(101);
    require(accepted && accepted->ack == gs::AckClass::Durable && accepted->state_changed &&
            state.identities() == 1 && outbox.record_count() == 1,
            "fresh protected EventKey must own next ordinal after ordinary refusal");
    require(runtime.radio_callback(protected_event), "lost ACK retry queued");
    const auto retry = runtime.run_state_once(999);
    require(retry && retry->ack == gs::AckClass::Durable && !retry->state_changed &&
            retry->rule_signals.empty(), "lost ACK must not duplicate application effect");
    std::cout << "GS148-ARCH-010 PASS repeated_refusals=12 reboot_count=2\n";
}

void recovery_bank_test() {
    using namespace gs::hub::durable;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemoryBlobStore blobs;
    DurableStore store(blobs, crypto, key, 7);
    RetirementSnapshotRepository reports(blobs, crypto, key, 7);
    RetirementSnapshot snapshot;
    snapshot.storage_epoch = 7;
    snapshot.generation = 1;
    RetirementSnapshotReference first, second, third;
    require(reports.prepare_bank(snapshot, 0, first), "first report prepared");
    Checkpoint cp;
    cp.storage_epoch = 7; cp.generation = 1; cp.report_snapshot = first;
    require(store.checkpoint(cp), "first report selected");
    snapshot.generation = 2;
    require(reports.prepare_bank(snapshot, std::uint8_t(1U << first.bank), second),
            "second report prepared");
    cp.generation = 2; cp.report_snapshot = second;
    require(store.checkpoint(cp), "second report selected");
    RecoveryState before;
    require(store.recover(before), "selected/fallback root recovery");
    const auto pinned = before.recovery_report_bank_mask;
    snapshot.generation = 3;
    require(reports.prepare_bank(snapshot, pinned, third), "third report prepared");
    RetirementSnapshot fallback;
    require(reports.load(first, fallback),
            "GS148-ARCH-012 staging overwrote recovery-eligible fallback report");
    require(third.bank != first.bank && third.bank != second.bank,
            "candidate must use the unreferenced third bank");
    // Crash before checkpoint selection. Damaging the newer checkpoint exposes
    // the still-authenticated fallback selector and its exact original report.
    require(blobs.replace("cp1", Bytes{0}), "inject interrupted newest checkpoint");
    for (int boot = 0; boot < 2; ++boot) {
        DurableStore reboot(blobs, crypto, key, 7);
        RecoveryState recovered;
        require(reboot.recover(recovered) && recovered.checkpoint_generation == 1 &&
                recovered.checkpoint.report_snapshot->digest == first.digest &&
                reports.load(*recovered.checkpoint.report_snapshot, fallback),
                "fallback selected bank must retain exact generation/digest after reboot");
    }
    std::cout << "GS148-ARCH-012 PASS protected_selected_and_fallback=2\n";
}

void witness_epoch_test() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    DurableEventOutbox outbox(segments, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty, "witness fixture recovery");
    gs::hub::durable::ReportSnapshotReference reference;
    reference.bank = 0; reference.generation = 1; reference.digest.fill(0x41);
    require(outbox.publish_replay_fence(7, reference, 0), "initial witness publication");
    auto next = reference;
    next.bank = 1; next.generation = 2; next.digest.fill(0x42);
    require(!outbox.publish_replay_fence(8, next, 0) &&
            outbox.replay_fence_matches(7, reference),
            "GS148-ARCH-016 higher generation must not change witness epoch");
    DurableEventOutbox reboot(segments, crypto, key);
    require(reboot.recover() == OutboxRecovery::Empty &&
            reboot.replay_fence_matches(7, reference), "cross-epoch rejection preserves root");
    std::cout << "GS148-ARCH-016 PASS cross_epoch_higher_generation_refused\n";
}

void workspace_boundary_test() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    DurableEventOutbox outbox(segments, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty, "workspace recovery");
    OutboxJournalBackend backend(outbox);
    RuntimeStateStore state(files, crypto, key);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    require(runtime.restore_from_journal(), "workspace runtime recovery");
    auto e = event(1);
    runtime.authorize_node("room1", 42, true);
    require(runtime.radio_callback(e), "workspace queue");
    Bytes checkpoint;
    std::uint64_t workspace = 0;
    require(gs::hub::HubCheckpointCodec::encode_after_event(runtime, e, 100, checkpoint) &&
            state.admission_workspace(e, 1, checkpoint.size(), workspace), "workspace sizing");
    // Combined filesystem ledger: runtime candidate + identity growth/head +
    // outbox body growth/head. One byte below the rounded requirement refuses
    // before prepare; the exact immediate boundary permits the same EventKey.
    const auto required = workspace + 8192U;
    segments.additional_usage = segments.partition_capacity_bytes() - required + 1U;
    const auto original = files.files;
    const auto writes = files.writes;
    const auto rejected = runtime.run_state_once(100);
    require(rejected && rejected->ack == gs::AckClass::Rejected && files.files == original &&
            files.writes == writes && state.identities() == 0 && outbox.record_count() == 0,
            "GS148-ARCH-030 whole immediate workspace refused before identity write");
    segments.additional_usage -= 1U;
    require(runtime.radio_callback(e), "workspace exact boundary queue");
    const auto accepted = runtime.run_state_once(100);
    require(accepted && accepted->ack == gs::AckClass::Durable && state.identities() == 1,
            "rounded immediate boundary permits same original identity");
    std::uint64_t ignored = 0;
    require(!state.admission_workspace(event(2), 2, 65537U, ignored) && state.healthy(),
            "GS148-ARCH-035 oversize checkpoint refused without persistent mutation");
    std::cout << "GS148-ARCH-030 PASS immediate_workspace=" << required << " boundary=one_byte\n";
}

void prepared_cut_tests() {
    unsigned cuts = 0;
    for (unsigned cut = 0; cut < 13; ++cut) {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = storage_key();
        MemorySegments segments(4U * 1024U * 1024U);
        StateFiles files;
        auto e = event(1);
        {
            DurableEventOutbox outbox(segments, crypto, key);
            require(outbox.recover() == OutboxRecovery::Empty, "cut initial outbox");
            OutboxJournalBackend backend(outbox);
            RuntimeStateStore state(files, crypto, key);
            gs::hub::HubRuntime runtime(32, backend);
            runtime.bind_runtime_state(state);
            runtime.authorize_node("room1", 42, true);
            require(runtime.restore_from_journal() && runtime.radio_callback(e), "cut initialization");
            const auto seed = runtime.run_state_once(100);
            require(seed && seed->ack == gs::AckClass::Durable, "cut authenticated prior publication");
            e = event(3);
            require(runtime.radio_callback(e), "cut interrupted next event queued");
            if (cut == 0) files.partial_append = true;
            if (cut == 1) files.fail_replace = "identity.head";
            if (cut == 2) files.persist_then_fail = "identity.head";
            if (cut >= 3 && cut <= 5) segments.append_fault = cut - 2U;
            if (cut == 6) segments.fail_sync_once = true;
            if (cut == 7) segments.fail_next_publication();
            if (cut == 8) files.fail_replace = "application.head";
            if (cut == 9) files.persist_then_fail = "application.head";
            if (cut == 10) segments.missing_read_once = true;
            if (cut == 11) segments.corrupt_read_once = true;
            if (cut == 12) files.fail_read = "identity.head";
            const auto result = runtime.run_state_once(100);
            require(result && result->ack == gs::AckClass::Rejected,
                    "GS148-ARCH-002/003/004/005/006 uncertain cut must withhold ACK");
            require(state.identities() <= 2 && outbox.record_count() <= 2,
                    "interrupted transaction owns at most one identity/body");
        }
        files.halted = false; files.fail_replace.clear(); files.persist_then_fail.clear();
        files.fail_read.clear();
        for (int boot = 0; boot < 2; ++boot) {
            DurableEventOutbox outbox(segments, crypto, key);
            const auto recovered = outbox.recover();
            if (recovered != OutboxRecovery::Empty && recovered != OutboxRecovery::Ready)
                std::cerr << "prepared cut=" << cut << " boot=" << boot
                          << " recovery=" << int(recovered) << '\n';
            require(recovered == OutboxRecovery::Empty || recovered == OutboxRecovery::Ready,
                    "cut reboot recovers authenticated complete/prefix boundary");
            OutboxJournalBackend backend(outbox);
            RuntimeStateStore state(files, crypto, key);
            gs::hub::HubRuntime runtime(32, backend);
            runtime.bind_runtime_state(state);
            runtime.authorize_node("room1", 42, true);
            require(runtime.restore_from_journal(), "cut runtime checkpoint+tail recovery");
            if (state.identities() == 2 && outbox.record_count() == 1) {
                require(runtime.radio_callback(event(2)), "different prepared key queue");
                const auto conflict = runtime.run_state_once(999);
                require(conflict && conflict->ack == gs::AckClass::Rejected &&
                        state.identities() == 2 && outbox.record_count() == 1,
                        "GS148-ARCH-010 prepared owner cannot be replaced by another EventKey");
            }
            require(runtime.radio_callback(e), "cut exact retry queue");
            Bytes before_retry;
            require(gs::hub::HubCheckpointCodec::encode(runtime, before_retry), "retry baseline reducer");
            const auto retry = runtime.run_state_once(999);
            require(retry && retry->ack == gs::AckClass::Durable && state.identities() == 2 &&
                    outbox.record_count() == 2, "cut retry completes exactly one logical identity");
            std::optional<std::uint16_t> original_minute;
            require(state.identity_context(e.key, 2, original_minute, &e) &&
                    original_minute == std::optional<std::uint16_t>(cut >= 2 ? 100 : 999),
                    "GS148-ARCH-009 exact retry preserves selected original local-minute context");
            if (boot == 1) {
                Bytes after_retry;
                require(!retry->state_changed && retry->rule_signals.empty() &&
                        gs::hub::HubCheckpointCodec::encode(runtime, after_retry) &&
                        before_retry == after_retry,
                        "GS148-ARCH-007 duplicate after reboot has no second logical effect");
            }
            auto altered = e; altered.kind = gs::EventKind::DoorOpen;
            require(runtime.radio_callback(altered), "conflicting immutable payload queue");
            const auto conflict = runtime.run_state_once(999);
            require(conflict && conflict->ack == gs::AckClass::Rejected && !conflict->state_changed,
                    "GS148-ARCH-008 changed payload under identical EventKey cannot ACK");
            if (boot == 1) {
                require(runtime.radio_callback(event(2)), "cut fresh event queue after two reboots");
                const auto fresh = runtime.run_state_once(101);
                require(fresh && fresh->ack == gs::AckClass::Durable && state.identities() == 3 &&
                        outbox.record_count() == 3 && outbox.retired_through() == 0,
                        "cut recovery preserves pending set and admits fresh event after two boots");
            }
        }
        ++cuts;
    }
    std::cout << "GS148-ARCH-002/003/004/005/006/007/008/009/010 PASS cuts=" << cuts
              << " reboot_per_cut=2\n";
}

void reducer_bound_test() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemorySegments segments(4U * 1024U * 1024U);
    StateFiles files;
    DurableEventOutbox outbox(segments, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty, "reducer bound initial outbox");
    OutboxJournalBackend backend(outbox);
    RuntimeStateStore state(files, crypto, key);
    gs::hub::HubRuntime runtime(32, backend);
    runtime.bind_runtime_state(state);
    runtime.authorize_node("room1", 42, true);
    require(runtime.restore_from_journal(), "reducer bound checkpoint genesis");
    gs::RoutineConfig window;
    window.window_id = "morning"; window.start_at = 1; window.end_at = 5000;
    window.grace_end_at = 5100;
    runtime.start_window(window, gs::HomeMode::Home);
    bool refused = false;
    for (std::uint64_t seq = 1; seq <= 1024; ++seq) {
        auto e = event(seq); e.key.physical_device_id.assign(64, 'p');
        require(runtime.radio_callback(e), "bounded evidence queue");
        const auto before = files.files;
        const auto identities = state.identities();
        const auto records = outbox.record_count();
        const auto result = runtime.run_state_once(100);
        require(result.has_value(), "bounded evidence owner consumes event");
        if (result->ack == gs::AckClass::Rejected) {
            Bytes checkpoint;
            const auto encoded = gs::hub::HubCheckpointCodec::encode(runtime, checkpoint);
            require(!result->state_changed && files.files == before &&
                    identities == state.identities() && records == outbox.record_count() &&
                    encoded &&
                    checkpoint.size() <= 65536U && runtime.durable_admission_open(),
                    "GS148-ARCH-035 exact next reducer bound refuses before identity/body/live state");
            refused = true;
            std::cout << "GS148-ARCH-035 PASS accepted=" << records
                      << " checkpoint_bytes=" << checkpoint.size() << " next_refused=1\n";
            break;
        }
        require(result->ack == gs::AckClass::Durable, "bounded evidence accepted ACK");
    }
    require(refused, "reducer fixture must reach existing serialization bound");
    DurableEventOutbox reboot(segments, crypto, key);
    require(reboot.recover() == OutboxRecovery::Ready, "bounded reducer body recovery");
    OutboxJournalBackend rb(reboot);
    RuntimeStateStore rs(files, crypto, key);
    gs::hub::HubRuntime restored(32, rb);
    restored.bind_runtime_state(rs);
    require(restored.restore_from_journal() && restored.durable_admission_open(),
            "refused oversized reducer never installs an unreadable checkpoint");
}

void first_admission_recovery_gap_test() {
    // The existing v1 publication codec forbids ordinal zero. Missing first
    // head cannot distinguish an interrupted write from loss of ACK authority.
    // Keep this compatibility blocker observable; do not relax recovery.
    for (unsigned cut = 0; cut < 3; ++cut) {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = storage_key();
        MemorySegments segments(4U * 1024U * 1024U);
        StateFiles files;
        DurableEventOutbox outbox(segments, crypto, key);
        require(outbox.recover() == OutboxRecovery::Empty, "first admission gap fixture");
        OutboxJournalBackend backend(outbox);
        RuntimeStateStore state(files, crypto, key);
        gs::hub::HubRuntime runtime(32, backend);
        runtime.bind_runtime_state(state);
        runtime.authorize_node("room1", 42, true);
        require(runtime.restore_from_journal() && runtime.radio_callback(event(1)), "first admission queue");
        if (cut == 0) segments.append_fault = 3;
        if (cut == 1) segments.fail_sync_once = true;
        if (cut == 2) segments.fail_next_publication();
        const auto result = runtime.run_state_once(100);
        require(result && result->ack == gs::AckClass::Rejected && state.identities() == 1 &&
                outbox.record_count() == 0, "first ambiguous write has no premature ACK");
        for (int boot = 0; boot < 2; ++boot) {
            DurableEventOutbox reboot(segments, crypto, key);
            require(reboot.recover() == OutboxRecovery::IntegrityFailure && !reboot.healthy(),
                    "missing first publication authority must remain fail closed");
        }
    }
    std::cout << "GS148-ARCH-001/004/005 FIRST_ADMISSION_RECOVERY_BLOCKED cuts=3 fail_closed=PASS\n";
}

void root_publication_cut_tests() {
    using namespace gs::hub::durable;
    unsigned cuts = 0;
    for (const auto mode : {FaultMode::FailBeforeWrite, FaultMode::PartialWrite,
                           FaultMode::PersistThenFail, FaultMode::PowerLossAfterPersist}) {
        for (unsigned boundary = 0; boundary < 3; ++boundary) {
            gs::host::security::OpenSslCommissioningCrypto crypto;
            const auto key = storage_key();
            MemoryBlobStore blobs;
            DurableStore store(blobs, crypto, key, 7);
            RetirementSnapshotRepository reports(blobs, crypto, key, 7);
            RetirementSnapshot snapshot; snapshot.storage_epoch = 7;
            ReportSnapshotReference refs[3];
            Checkpoint cp; cp.storage_epoch = 7;
            for (unsigned i = 0; i < 2; ++i) {
                snapshot.generation = i + 1U;
                require(reports.prepare_bank(snapshot, i == 0 ? 0 : std::uint8_t(1U << refs[0].bank),
                                             refs[i]), "root cut seed bank");
                cp.generation = i + 1U; cp.report_snapshot = refs[i];
                require(store.checkpoint(cp), "root cut seed checkpoint");
            }
            RecoveryState before;
            require(store.recover(before), "root cut initial selectors");
            snapshot.generation = 3;
            blobs.inject_after(boundary, mode);
            if (reports.prepare_bank(snapshot, before.recovery_report_bank_mask, refs[2])) {
                cp.generation = 3; cp.report_snapshot = refs[2];
                (void)store.checkpoint(cp);
            }
            blobs.power_cycle();
            for (int boot = 0; boot < 2; ++boot) {
                DurableStore reboot(blobs, crypto, key, 7);
                RecoveryState recovered;
                RetirementSnapshot selected, prior;
                require(reboot.recover(recovered) &&
                        (recovered.checkpoint_generation == 2 || recovered.checkpoint_generation == 3) &&
                        recovered.checkpoint.report_snapshot &&
                        reports.load(*recovered.checkpoint.report_snapshot, selected) &&
                        selected.generation == recovered.checkpoint_generation &&
                        reports.load(refs[1], prior) && prior.generation == 2,
                        "GS148-ARCH-012/013 report/cp/selector cut retains exact authoritative roots");
            }
            ++cuts;
        }
    }
    std::cout << "GS148-ARCH-012/013 PASS publication_cuts=" << cuts << " reboot_per_cut=2\n";
}

void all_roots_and_conflict_test() {
    using namespace gs::hub::durable;
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    MemoryBlobStore blobs;
    DurableStore store(blobs, crypto, key, 7);
    RetirementSnapshotRepository reports(blobs, crypto, key, 7);
    MemorySegments segments(4U * 1024U * 1024U);
    DurableEventOutbox outbox(segments, crypto, key);
    require(outbox.recover() == OutboxRecovery::Empty, "all root witness recovery");
    RetirementSnapshot snapshot; snapshot.storage_epoch = 7;
    Checkpoint cp; cp.storage_epoch = 7;
    ReportSnapshotReference refs[3];
    for (unsigned i = 0; i < 3; ++i) {
        RecoveryState current;
        require(store.recover(current), "all root selector inventory");
        std::uint8_t mask = 0;
        require(outbox.retirement_report_bank_mask(current, mask), "all root combined inventory");
        snapshot.generation = i + 1U;
        require(reports.prepare_bank(snapshot, mask, refs[i]), "all root prepare free bank");
        cp.generation = i + 1U; cp.report_snapshot = refs[i];
        require(store.checkpoint(cp), "all root select checkpoint");
        if (i == 0) require(outbox.publish_replay_fence(7, refs[i], 0), "old witness seeded");
    }
    RecoveryState current;
    require(store.recover(current), "three pinned roots recovered");
    std::uint8_t mask = 0;
    require(outbox.retirement_report_bank_mask(current, mask) && mask == 7,
            "GS148-ARCH-018 two NVS roots plus independent witness pin all banks");
    const auto writes = blobs.write_count();
    snapshot.generation = 4;
    ReportSnapshotReference unused;
    require(!reports.prepare_bank(snapshot, mask, unused) && blobs.write_count() == writes,
            "all three pinned banks refuse publication without mutation");
    require(outbox.publish_replay_fence(7, refs[2], 0) &&
            outbox.retirement_report_bank_mask(current, mask) && mask != 7 &&
            reports.prepare_bank(snapshot, mask, unused),
            "NVS-ahead witness reconciliation releases only unreferenced bank for standard staging");
    auto stale = current; stale.checkpoint.report_snapshot = refs[1];
    require(!outbox.retirement_report_bank_mask(stale, mask),
            "GS148-ARCH-015 LittleFS-ahead stale NVS authority refuses mutation");
    auto conflicting = current; conflicting.checkpoint.report_snapshot->digest[0] ^= 1;
    require(!outbox.retirement_report_bank_mask(conflicting, mask),
            "GS148-ARCH-016 equal generation conflicting digest refuses mutation");
    // Existing codecs can represent two independently valid authorities with
    // equal generation. Recovery must reject their conflict deterministically.
    MemoryBlobStore conflict_blobs;
    for (std::uint8_t bank = 0; bank < 2; ++bank) {
        Checkpoint other; other.storage_epoch = 7; other.generation = 1;
        other.reducer_state = {bank};
        Bytes encoded, selector;
        require(Codec::encode_checkpoint(crypto, key, other, encoded) &&
                conflict_blobs.replace(bank == 0 ? "cp0" : "cp1", encoded) &&
                Codec::encode_selector(crypto, key, 1, bank, selector) &&
                conflict_blobs.replace(bank == 0 ? "sel0" : "sel1", selector),
                "install valid conflicting selector authorities");
    }
    for (int boot = 0; boot < 2; ++boot) {
        DurableStore reboot(conflict_blobs, crypto, key, 7);
        RecoveryState recovered;
        require(!reboot.recover(recovered), "equal-generation conflicting roots fail closed");
    }
    // Identical authority encrypted independently is not a conflict.
    for (std::uint8_t bank = 0; bank < 2; ++bank) {
        Checkpoint same; same.storage_epoch = 7; same.generation = 1;
        Bytes encoded;
        require(Codec::encode_checkpoint(crypto, key, same, encoded) &&
                conflict_blobs.replace(bank == 0 ? "cp0" : "cp1", encoded),
                "install independently encrypted identical checkpoint authorities");
    }
    DurableStore equivalent(conflict_blobs, crypto, key, 7);
    RecoveryState equivalent_state;
    require(equivalent.recover(equivalent_state) && equivalent_state.checkpoint_generation == 1,
            "different AEAD nonces do not create a checkpoint authority conflict");
    std::cout << "GS148-ARCH-014/015/016/018 PASS all_roots_pinned_conflict_closed\n";
}

void checkpoint_selection_crash_tests() {
    using namespace gs::hub::durable;
    for (const auto& boundary : {std::string("ret2"), std::string("cp0"), std::string("sel1")}) {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = storage_key();
        HaltedBlobStore blobs;
        DurableStore store(blobs, crypto, key, 7);
        RetirementSnapshotRepository reports(blobs, crypto, key, 7);
        RetirementSnapshot snapshot; snapshot.storage_epoch = 7;
        Checkpoint cp; cp.storage_epoch = 7;
        ReportSnapshotReference refs[3];
        for (unsigned i = 0; i < 2; ++i) {
            snapshot.generation = i + 1U;
            require(reports.prepare_bank(snapshot, i == 0 ? 0 : std::uint8_t(1U << refs[0].bank),
                                         refs[i]), "halted crash seed report");
            cp.generation = i + 1U; cp.report_snapshot = refs[i];
            cp.reducer_state = {static_cast<std::uint8_t>(i + 1U)};
            require(store.checkpoint(cp), "halted crash seed selected checkpoint");
        }
        RecoveryState before;
        require(store.recover(before), "halted crash prior-root inventory");
        blobs.halt_after = boundary;
        snapshot.generation = 3;
        bool ready = reports.prepare_bank(snapshot, before.recovery_report_bank_mask, refs[2]);
        if (ready) {
            cp.generation = 3; cp.report_snapshot = refs[2]; cp.reducer_state = {3};
            ready = store.checkpoint(cp);
        }
        require(blobs.halted && !ready, "crash stops readback/selector and cannot authorize report ACK");
        blobs.power_cycle();
        const auto expected = boundary == "sel1" ? 3U : 2U;
        for (int boot = 0; boot < 2; ++boot) {
            DurableStore reboot(blobs, crypto, key, 7);
            RecoveryState recovered;
            RetirementSnapshot selected;
            require(reboot.recover(recovered) && recovered.checkpoint_generation == expected &&
                    recovered.checkpoint.reducer_state == Bytes{static_cast<std::uint8_t>(expected)} &&
                    recovered.checkpoint.report_snapshot &&
                    reports.load(*recovered.checkpoint.report_snapshot, selected) &&
                    selected.generation == expected && selected.occupancy_mask == 0 &&
                    recovered.tail.empty(),
                    "GS148-ARCH-012/013 crash before/after selector chooses exact authority twice");
        }
    }
    std::cout << "GS148-ARCH-012/013 PASS halted_crashes=3 reboot_per_cut=2\n";
}
}

int main(int argc, char** argv) {
    try {
        const std::string selected = argc == 2 ? argv[1] : "all";
        if (selected == "all" || selected == "admission") admission_refusal_test();
        if (selected == "all" || selected == "roots") recovery_bank_test();
        if (selected == "all" || selected == "epoch") witness_epoch_test();
        if (selected == "all") {
            workspace_boundary_test(); prepared_cut_tests(); root_publication_cut_tests();
            all_roots_and_conflict_test(); checkpoint_selection_crash_tests();
            first_admission_recovery_gap_test(); reducer_bound_test();
        }
        if (selected != "all" && selected != "admission" && selected != "roots" &&
            selected != "epoch") throw std::runtime_error("unknown correctness case");
        std::cout << "PASS: GS148 bounded admission and recovery correctness\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "GS148 correctness FAIL: " << e.what() << '\n';
        return 1;
    }
}
