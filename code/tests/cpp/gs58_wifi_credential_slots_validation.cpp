#include "firmware/hub/connectivity/wifi_credential_slots.hpp"

#include <algorithm>
#include <array>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <utility>

namespace {
using namespace gs::hub::connectivity;
unsigned checks = 0;
void expect(bool ok, const char* label) {
    ++checks;
    if (!ok) throw std::runtime_error(label);
}

class MemorySlots final : public WifiCredentialSlotStorage {
public:
    struct Cell { bool present{false}; std::array<std::uint8_t, kMaxEncodedBytes> bytes{}; std::size_t size{0}; };
    enum class PowerCut { None, BeforeWrite, AfterWrite };
    WifiCredentialProtection protection_state{WifiCredentialProtection::EncryptedWithVerifiedDeviceKey};
    std::array<Cell, 3> cells{};
    WifiCredentialSlot fail_slot{WifiCredentialSlot::Selector};
    WifiCredentialIoResult next_write{WifiCredentialIoResult::Ok};
    bool persist_unknown{false};
    std::size_t write_count{0};
    std::size_t cut_on_write{0};
    PowerCut power_cut{PowerCut::None};
    WifiCredentialProtection protection() const override { return protection_state; }
    static std::size_t index(WifiCredentialSlot slot) { return static_cast<std::size_t>(slot); }
    WifiCredentialIoResult read(WifiCredentialSlot slot, std::uint8_t* output,
                                std::size_t capacity, std::size_t& size) override {
        const auto& cell = cells[index(slot)];
        size = 0;
        if (!cell.present) return WifiCredentialIoResult::NotFound;
        if (output == nullptr || capacity < cell.size) return WifiCredentialIoResult::IoError;
        std::copy_n(cell.bytes.begin(), cell.size, output);
        size = cell.size;
        return WifiCredentialIoResult::Ok;
    }
    WifiCredentialIoResult write(WifiCredentialSlot slot, const std::uint8_t* input,
                                 std::size_t size) override {
        ++write_count;
        const bool cut_here = cut_on_write != 0 && write_count == cut_on_write;
        if (cut_here && power_cut == PowerCut::BeforeWrite)
            throw std::runtime_error("simulated_power_loss_before_write");
        auto outcome = WifiCredentialIoResult::Ok;
        if (slot == fail_slot) {
            outcome = next_write;
            next_write = WifiCredentialIoResult::Ok;
            if (outcome == WifiCredentialIoResult::Rejected ||
                (outcome == WifiCredentialIoResult::OutcomeUnknown && !persist_unknown))
                return outcome;
        }
        auto& cell = cells[index(slot)];
        if (input == nullptr || size > cell.bytes.size()) return WifiCredentialIoResult::IoError;
        cell = Cell{};
        cell.present = true;
        cell.size = size;
        std::copy_n(input, size, cell.bytes.begin());
        if (cut_here && power_cut == PowerCut::AfterWrite)
            throw std::runtime_error("simulated_power_loss_after_write");
        return outcome;
    }
    WifiCredentialIoResult erase(WifiCredentialSlot slot) override {
        cells[index(slot)] = Cell{};
        return WifiCredentialIoResult::Ok;
    }
};

WifiCredentialRecord record(const char* ssid, const char* password) {
    WifiCredentialRecord out;
    out.ssid_size = static_cast<std::uint8_t>(std::strlen(ssid));
    out.password_size = static_cast<std::uint8_t>(std::strlen(password));
    std::copy_n(reinterpret_cast<const std::uint8_t*>(ssid), out.ssid_size, out.ssid.begin());
    std::copy_n(reinterpret_cast<const std::uint8_t*>(password), out.password_size, out.password.begin());
    return out;
}

bool same(const WifiCredentialRecord& a, const WifiCredentialRecord& b) {
    return a.ssid_size == b.ssid_size && a.password_size == b.password_size &&
        std::equal(a.ssid.begin(), a.ssid.begin() + a.ssid_size, b.ssid.begin()) &&
        std::equal(a.password.begin(), a.password.begin() + a.password_size, b.password.begin());
}

WifiCredentialStoreResult stage_and_activate(
    TwoSlotWifiCredentialStoreBackend& backend,
    const WifiCredentialRecord& candidate) {
    std::uint32_t generation = 0;
    const auto staged = backend.stage_candidate(candidate, generation);
    if (staged != WifiCredentialStoreResult::CandidateStaged) return staged;
    return backend.activate_candidate(generation);
}

void test_commit_and_restart_recovery() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    const auto first = record("Home24", "first-password-123");
    std::uint32_t first_generation = 0;
    expect(backend.stage_candidate(first, first_generation) ==
               WifiCredentialStoreResult::CandidateStaged && first_generation == 2,
           "first credential is durably staged behind a non-active tombstone");
    WifiCredentialRecord loaded;
    expect(backend.load(loaded) == WifiCredentialStoreResult::NotFound,
           "staging first-time credentials does not report an active configuration");
    std::uint32_t recovered_generation = 0;
    TwoSlotWifiCredentialStoreBackend after_restart(memory);
    expect(after_restart.load_candidate(recovered_generation, loaded) ==
               WifiCredentialStoreResult::CandidateStaged &&
               recovered_generation == first_generation && same(loaded, first),
           "staged first-time credential survives backend reconstruction");
    expect(after_restart.activate_candidate(first_generation) ==
               WifiCredentialStoreResult::Ok,
           "explicit activation commits only the exact staged generation");
    expect(after_restart.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, first),
           "activated first credential loads from active selector");

    const auto second = record("Home24", "second-password-456");
    std::uint32_t second_generation = 0;
    expect(after_restart.stage_candidate(second, second_generation) ==
               WifiCredentialStoreResult::CandidateStaged && second_generation == 3,
           "replacement credential stages as the next generation");
    TwoSlotWifiCredentialStoreBackend rebooted(memory);
    expect(rebooted.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, first),
           "restart continues using the prior active credential before verification");
    expect(rebooted.activate_candidate(second_generation) == WifiCredentialStoreResult::Ok &&
               rebooted.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, second),
           "explicit generation activation changes the active credential");
    expect(memory.cells[MemorySlots::index(WifiCredentialSlot::SlotA)].present &&
           memory.cells[MemorySlots::index(WifiCredentialSlot::SlotB)].present,
           "two slots retain the prior record through candidate activation");
}

void test_failure_and_unknown_commit() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    const auto first = record("Home24", "first-password-123");
    const auto second = record("Home24", "second-password-456");
    expect(stage_and_activate(backend, first) == WifiCredentialStoreResult::Ok,
           "baseline credential commits");

    memory.fail_slot = WifiCredentialSlot::SlotB;
    memory.next_write = WifiCredentialIoResult::Rejected;
    std::uint32_t candidate_generation = 0;
    expect(backend.stage_candidate(second, candidate_generation) ==
               WifiCredentialStoreResult::CommitRejected && candidate_generation == 0,
           "rejected inactive candidate write stays rejected");
    WifiCredentialRecord loaded;
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, first),
           "rejected replacement preserves prior active credential");

    memory.fail_slot = WifiCredentialSlot::Selector;
    memory.next_write = WifiCredentialIoResult::OutcomeUnknown;
    memory.persist_unknown = true;
    expect(backend.stage_candidate(second, candidate_generation) ==
               WifiCredentialStoreResult::CandidateStaged,
           "candidate stage does not touch the active selector");
    expect(backend.activate_candidate(candidate_generation) == WifiCredentialStoreResult::Ok,
           "unknown selector commit resolves only from exact active readback");
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, second),
           "verified selector readback selects the exact candidate");

    memory.next_write = WifiCredentialIoResult::OutcomeUnknown;
    memory.persist_unknown = false;
    const auto third = record("Home24", "third-password-789");
    expect(backend.stage_candidate(third, candidate_generation) ==
               WifiCredentialStoreResult::CandidateStaged,
           "third credential stages while second remains active");
    expect(backend.activate_candidate(candidate_generation) ==
               WifiCredentialStoreResult::CommitOutcomeUnknown,
           "uncertain selector with prior state remains unknown");
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, second),
           "uncertain activation does not retire the verified current credential");
}

void test_corruption_protection_and_tombstone() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    auto credential = record("Home24", "first-password-123");
    memory.protection_state = WifiCredentialProtection::PlaintextOnly;
    std::uint32_t generation = 0;
    expect(backend.stage_candidate(credential, generation) == WifiCredentialStoreResult::ProtectedStorageUnavailable,
           "plaintext storage is refused");
    memory.protection_state = WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    expect(stage_and_activate(backend, credential) == WifiCredentialStoreResult::Ok,
           "protected backend accepts and explicitly activates valid credential");

    const auto active = memory.cells[MemorySlots::index(WifiCredentialSlot::SlotA)];
    memory.cells[MemorySlots::index(WifiCredentialSlot::SlotA)].bytes[10] ^= 0x01;
    WifiCredentialRecord loaded;
    expect(backend.load(loaded) == WifiCredentialStoreResult::CorruptRecord,
           "corrupt record fails closed rather than trying stale slot");
    memory.cells[MemorySlots::index(WifiCredentialSlot::SlotA)] = active;
    expect(backend.erase() == WifiCredentialStoreResult::Ok,
           "explicit erase commits tombstone and clears slots");
    expect(backend.load(loaded) == WifiCredentialStoreResult::NotFound,
           "tombstone prevents credential resurrection");
    expect(backend.stage_candidate(credential, generation) ==
               WifiCredentialStoreResult::CandidateStaged && generation == 4 &&
               backend.load(loaded) == WifiCredentialStoreResult::NotFound,
           "later setup stages after tombstone without activating automatically");
}

void test_candidate_rejection_and_discard_keep_active_selector() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    const auto active_record = record("Home24", "verified-password-123");
    const auto rejected_candidate = record("Home24", "unverified-password-456");
    expect(stage_and_activate(backend, active_record) == WifiCredentialStoreResult::Ok,
           "verified network baseline is active before candidate checks");
    std::uint32_t candidate_generation = 0;
    expect(backend.stage_candidate(rejected_candidate, candidate_generation) ==
               WifiCredentialStoreResult::CandidateStaged,
           "candidate can be staged without replacing selected credential");
    expect(backend.activate_candidate(candidate_generation + 1) ==
               WifiCredentialStoreResult::CommitRejected,
           "wrong generation cannot activate staged candidate");
    expect(backend.discard_candidate(candidate_generation + 1) ==
               WifiCredentialStoreResult::CommitRejected,
           "wrong generation cannot discard a candidate");
    WifiCredentialRecord loaded;
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok &&
               same(loaded, active_record),
           "failed verification or mismatched generation retains prior active credential");
    expect(backend.discard_candidate(candidate_generation) == WifiCredentialStoreResult::Ok,
           "authorized recovery can discard the exact unverified candidate");
    std::uint32_t recovered_generation = 0;
    expect(backend.load_candidate(recovered_generation, loaded) ==
               WifiCredentialStoreResult::NotFound &&
               backend.load(loaded) == WifiCredentialStoreResult::Ok &&
               same(loaded, active_record),
           "discard recovery leaves no candidate and preserves prior active selector");
}

void test_power_loss_boundaries_preserve_verified_state() {
    const auto first = record("Home24", "first-password-123");
    const auto second = record("Home24", "second-password-456");

    // First install has two durable writes: a non-active tombstone marker,
    // then the candidate slot. Cover the before/after boundary of each write.
    const std::array<std::pair<std::size_t, MemorySlots::PowerCut>, 4> initial_cuts{{
        {1, MemorySlots::PowerCut::BeforeWrite},
        {1, MemorySlots::PowerCut::AfterWrite},
        {2, MemorySlots::PowerCut::BeforeWrite},
        {2, MemorySlots::PowerCut::AfterWrite},
    }};
    for (const auto& [cut_write, cut] : initial_cuts) {
        MemorySlots memory;
        TwoSlotWifiCredentialStoreBackend backend(memory);
        memory.cut_on_write = cut_write;
        memory.power_cut = cut;
        try {
            std::uint32_t generation = 0;
            (void)backend.stage_candidate(first, generation);
        } catch (const std::runtime_error&) {}
        TwoSlotWifiCredentialStoreBackend recovered(memory);
        WifiCredentialRecord active;
        expect(recovered.load(active) == WifiCredentialStoreResult::NotFound,
               "power loss during first provisioning never selects an unverified credential");
        std::uint32_t candidate_generation = 0;
        const auto candidate = recovered.load_candidate(candidate_generation, active);
        expect(candidate == WifiCredentialStoreResult::NotFound ||
                   candidate == WifiCredentialStoreResult::CandidateStaged,
               "first-provisioning restart exposes only absent or explicitly staged candidate");
    }

    // During a Wi-Fi change, candidate staging writes only the inactive slot.
    // Loss before or after that write leaves the previous selector untouched.
    for (const auto cut : {MemorySlots::PowerCut::BeforeWrite,
                           MemorySlots::PowerCut::AfterWrite}) {
        MemorySlots memory;
        TwoSlotWifiCredentialStoreBackend backend(memory);
        expect(stage_and_activate(backend, first) == WifiCredentialStoreResult::Ok,
               "baseline is active before replacement fault injection");
        memory.write_count = 0;
        memory.cut_on_write = 1;
        memory.power_cut = cut;
        try {
            std::uint32_t generation = 0;
            (void)backend.stage_candidate(second, generation);
        } catch (const std::runtime_error&) {}
        TwoSlotWifiCredentialStoreBackend recovered(memory);
        WifiCredentialRecord active;
        expect(recovered.load(active) == WifiCredentialStoreResult::Ok && same(active, first),
               "power loss while staging replacement retains the previous active credential");
        std::uint32_t candidate_generation = 0;
        const auto candidate = recovered.load_candidate(candidate_generation, active);
        expect(candidate == WifiCredentialStoreResult::NotFound ||
                   (candidate == WifiCredentialStoreResult::CandidateStaged &&
                    same(active, second)),
               "replacement restart distinguishes absent candidate from recoverable staged candidate");
    }

    // The activation selector is the commit point. If power is lost after its
    // durable write, restart may observe the new generation; it must never
    // infer success from the interrupted call itself.
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    expect(stage_and_activate(backend, first) == WifiCredentialStoreResult::Ok,
           "baseline is active before selector interruption test");
    std::uint32_t generation = 0;
    expect(backend.stage_candidate(second, generation) ==
               WifiCredentialStoreResult::CandidateStaged,
           "replacement is staged before selector interruption test");
    memory.write_count = 0;
    memory.cut_on_write = 1;
    memory.power_cut = MemorySlots::PowerCut::AfterWrite;
    try {
        (void)backend.activate_candidate(generation);
    } catch (const std::runtime_error&) {}
    TwoSlotWifiCredentialStoreBackend recovered(memory);
    WifiCredentialRecord active;
    expect(recovered.load(active) == WifiCredentialStoreResult::Ok &&
               same(active, second),
           "restart resolves post-selector power loss from exact active record readback");
}
}  // namespace

int main() {
    try {
        test_commit_and_restart_recovery();
        test_failure_and_unknown_commit();
        test_corruption_protection_and_tombstone();
        test_candidate_rejection_and_discard_keep_active_selector();
        test_power_loss_boundaries_preserve_verified_state();
        std::cout << "GS-58 credential slots checks=" << checks << " PASS\n";
    } catch (const std::exception& error) {
        std::cerr << "GS-58 credential slots FAIL: " << error.what() << '\n';
        return 1;
    }
}
