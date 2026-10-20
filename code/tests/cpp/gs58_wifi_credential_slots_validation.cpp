#include "firmware/hub/connectivity/wifi_credential_slots.hpp"

#include <algorithm>
#include <array>
#include <cstring>
#include <iostream>
#include <stdexcept>

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
    WifiCredentialProtection protection_state{WifiCredentialProtection::EncryptedWithVerifiedDeviceKey};
    std::array<Cell, 3> cells{};
    WifiCredentialSlot fail_slot{WifiCredentialSlot::Selector};
    WifiCredentialIoResult next_write{WifiCredentialIoResult::Ok};
    bool persist_unknown{false};
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

void test_commit_and_restart_recovery() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    const auto first = record("Home24", "first-password-123");
    expect(backend.replace_atomically(first) == WifiCredentialStoreResult::Ok,
           "first record commits");
    WifiCredentialRecord loaded;
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, first),
           "first record loads from active selector");

    const auto second = record("Home24", "second-password-456");
    TwoSlotWifiCredentialStoreBackend after_restart(memory);
    expect(after_restart.replace_atomically(second) == WifiCredentialStoreResult::Ok,
           "second generation commits after backend reconstruction");
    TwoSlotWifiCredentialStoreBackend rebooted(memory);
    expect(rebooted.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, second),
           "reconstructed backend selects complete newest generation");
    expect(memory.cells[MemorySlots::index(WifiCredentialSlot::SlotA)].present &&
           memory.cells[MemorySlots::index(WifiCredentialSlot::SlotB)].present,
           "two slots retain the previous generation until next replacement");
}

void test_failure_and_unknown_commit() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    const auto first = record("Home24", "first-password-123");
    const auto second = record("Home24", "second-password-456");
    expect(backend.replace_atomically(first) == WifiCredentialStoreResult::Ok,
           "baseline credential commits");

    memory.fail_slot = WifiCredentialSlot::SlotB;
    memory.next_write = WifiCredentialIoResult::Rejected;
    expect(backend.replace_atomically(second) == WifiCredentialStoreResult::CommitRejected,
           "rejected inactive-slot write stays rejected");
    WifiCredentialRecord loaded;
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, first),
           "rejected replacement preserves prior active credential");

    memory.fail_slot = WifiCredentialSlot::Selector;
    memory.next_write = WifiCredentialIoResult::OutcomeUnknown;
    memory.persist_unknown = true;
    expect(backend.replace_atomically(second) == WifiCredentialStoreResult::Ok,
           "unknown selector commit resolves only from exact readback");
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, second),
           "resolved ambiguous selector selects candidate");

    memory.next_write = WifiCredentialIoResult::OutcomeUnknown;
    memory.persist_unknown = false;
    const auto third = record("Home24", "third-password-789");
    expect(backend.replace_atomically(third) == WifiCredentialStoreResult::CommitOutcomeUnknown,
           "uncertain selector with prior state remains unknown");
    expect(backend.load(loaded) == WifiCredentialStoreResult::Ok && same(loaded, second),
           "uncertain selector does not retire verified current credential");
}

void test_corruption_protection_and_tombstone() {
    MemorySlots memory;
    TwoSlotWifiCredentialStoreBackend backend(memory);
    auto credential = record("Home24", "first-password-123");
    memory.protection_state = WifiCredentialProtection::PlaintextOnly;
    expect(backend.replace_atomically(credential) == WifiCredentialStoreResult::ProtectedStorageUnavailable,
           "plaintext storage is refused");
    memory.protection_state = WifiCredentialProtection::EncryptedWithVerifiedDeviceKey;
    expect(backend.replace_atomically(credential) == WifiCredentialStoreResult::Ok,
           "protected backend accepts valid credential");

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
    expect(backend.replace_atomically(credential) == WifiCredentialStoreResult::Ok,
           "later explicit setup advances generation after tombstone");
}
}  // namespace

int main() {
    try {
        test_commit_and_restart_recovery();
        test_failure_and_unknown_commit();
        test_corruption_protection_and_tombstone();
        std::cout << "GS-58 credential slots checks=" << checks << " PASS\n";
    } catch (const std::exception& error) {
        std::cerr << "GS-58 credential slots FAIL: " << error.what() << '\n';
        return 1;
    }
}
