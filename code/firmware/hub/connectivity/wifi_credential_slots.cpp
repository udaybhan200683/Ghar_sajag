#include "firmware/hub/connectivity/wifi_credential_slots.hpp"

#include <algorithm>
#include <array>
#include <cstring>

namespace gs::hub::connectivity {
namespace {
constexpr std::array<std::uint8_t, 4> kRecordMagic{'W', 'C', 'R', 1};
constexpr std::array<std::uint8_t, 4> kSelectorMagic{'W', 'C', 'S', 1};
constexpr std::size_t kRecordHeaderSize = 10;
constexpr std::size_t kRecordCrcSize = 4;
constexpr std::size_t kSelectorSize = 13;
constexpr std::uint8_t kTombstoneSlot = 0xff;

struct SensitiveBuffer {
    std::array<std::uint8_t, WifiCredentialSlotStorage::kMaxEncodedBytes> bytes{};
    ~SensitiveBuffer() {
        volatile std::uint8_t* data = bytes.data();
        for (std::size_t i = 0; i < bytes.size(); ++i) data[i] = 0;
    }
};

std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffu;
    for (std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

void put_u32(std::uint8_t* out, std::uint32_t value) {
    out[0] = static_cast<std::uint8_t>(value);
    out[1] = static_cast<std::uint8_t>(value >> 8);
    out[2] = static_cast<std::uint8_t>(value >> 16);
    out[3] = static_cast<std::uint8_t>(value >> 24);
}

std::uint32_t get_u32(const std::uint8_t* in) {
    return static_cast<std::uint32_t>(in[0]) |
           (static_cast<std::uint32_t>(in[1]) << 8) |
           (static_cast<std::uint32_t>(in[2]) << 16) |
           (static_cast<std::uint32_t>(in[3]) << 24);
}

bool constant_bytes_equal(const std::uint8_t* a, const std::uint8_t* b,
                          std::size_t size) {
    std::uint8_t diff = 0;
    for (std::size_t i = 0; i < size; ++i) diff |= a[i] ^ b[i];
    return diff == 0;
}

bool encode_record(const WifiCredentialRecord& record, std::uint32_t generation,
                   std::array<std::uint8_t,
                              WifiCredentialSlotStorage::kMaxEncodedBytes>& out,
                   std::size_t& size) {
    if (!record.valid() || generation == 0) return false;
    size = kRecordHeaderSize + record.ssid_size + record.password_size + kRecordCrcSize;
    if (size > out.size()) return false;
    std::copy(kRecordMagic.begin(), kRecordMagic.end(), out.begin());
    put_u32(out.data() + 4, generation);
    out[8] = record.ssid_size;
    out[9] = record.password_size;
    std::copy_n(record.ssid.begin(), record.ssid_size, out.begin() + kRecordHeaderSize);
    std::copy_n(record.password.begin(), record.password_size,
                out.begin() + kRecordHeaderSize + record.ssid_size);
    put_u32(out.data() + size - kRecordCrcSize, crc32(out.data(), size - kRecordCrcSize));
    return true;
}

bool decode_record(const std::uint8_t* data, std::size_t size,
                   std::uint32_t expected_generation, WifiCredentialRecord& out) {
    if (data == nullptr || size < kRecordHeaderSize + kRecordCrcSize ||
        size > WifiCredentialSlotStorage::kMaxEncodedBytes ||
        !constant_bytes_equal(data, kRecordMagic.data(), kRecordMagic.size()))
        return false;
    const auto generation = get_u32(data + 4);
    const auto ssid_size = data[8];
    const auto password_size = data[9];
    const auto expected_size = kRecordHeaderSize + ssid_size + password_size + kRecordCrcSize;
    if (generation == 0 || generation != expected_generation ||
        ssid_size == 0 || ssid_size > WifiCredentialRecord::kSsidCapacity ||
        password_size > WifiCredentialRecord::kPasswordCapacity || size != expected_size ||
        get_u32(data + size - kRecordCrcSize) != crc32(data, size - kRecordCrcSize))
        return false;
    out.clear();
    out.ssid_size = ssid_size;
    out.password_size = password_size;
    std::copy_n(data + kRecordHeaderSize, ssid_size, out.ssid.begin());
    std::copy_n(data + kRecordHeaderSize + ssid_size, password_size, out.password.begin());
    if (!out.valid()) {
        out.clear();
        return false;
    }
    return true;
}

std::array<std::uint8_t, kSelectorSize> encode_selector(
    std::uint8_t slot, std::uint32_t generation, bool tombstone) {
    std::array<std::uint8_t, kSelectorSize> encoded{};
    std::copy(kSelectorMagic.begin(), kSelectorMagic.end(), encoded.begin());
    encoded[4] = tombstone ? kTombstoneSlot : slot;
    put_u32(encoded.data() + 5, generation);
    put_u32(encoded.data() + 9, crc32(encoded.data(), 9));
    return encoded;
}

bool decode_selector(const std::uint8_t* data, std::size_t size,
                     std::uint8_t& slot, std::uint32_t& generation,
                     bool& tombstone) {
    if (data == nullptr || size != kSelectorSize ||
        !constant_bytes_equal(data, kSelectorMagic.data(), kSelectorMagic.size()) ||
        get_u32(data + 9) != crc32(data, 9)) return false;
    slot = data[4];
    generation = get_u32(data + 5);
    tombstone = slot == kTombstoneSlot;
    return generation != 0 && (tombstone || slot <= 1);
}

WifiCredentialStoreResult map_io(WifiCredentialIoResult result) {
    switch (result) {
        case WifiCredentialIoResult::Ok: return WifiCredentialStoreResult::Ok;
        case WifiCredentialIoResult::NotFound: return WifiCredentialStoreResult::NotFound;
        case WifiCredentialIoResult::Rejected: return WifiCredentialStoreResult::CommitRejected;
        case WifiCredentialIoResult::OutcomeUnknown:
            return WifiCredentialStoreResult::CommitOutcomeUnknown;
        case WifiCredentialIoResult::IoError: return WifiCredentialStoreResult::IoError;
    }
    return WifiCredentialStoreResult::IoError;
}
}  // namespace

WifiCredentialProtection TwoSlotWifiCredentialStoreBackend::protection() const {
    return storage_.protection();
}

WifiCredentialStoreResult TwoSlotWifiCredentialStoreBackend::read_state(ActiveState& state) {
    state = ActiveState{};
    SensitiveBuffer encoded;
    std::size_t size = 0;
    const auto io = storage_.read(WifiCredentialSlot::Selector, encoded.bytes.data(),
                                  encoded.bytes.size(), size);
    if (io == WifiCredentialIoResult::NotFound) {
        SensitiveBuffer probe;
        std::size_t probe_size = 0;
        const auto a = storage_.read(WifiCredentialSlot::SlotA, probe.bytes.data(), probe.bytes.size(), probe_size);
        const auto b = storage_.read(WifiCredentialSlot::SlotB, probe.bytes.data(), probe.bytes.size(), probe_size);
        if (a == WifiCredentialIoResult::NotFound && b == WifiCredentialIoResult::NotFound)
            return WifiCredentialStoreResult::NotFound;
        return WifiCredentialStoreResult::CorruptRecord;
    }
    if (io != WifiCredentialIoResult::Ok) return map_io(io);
    std::uint8_t slot = 0;
    std::uint32_t generation = 0;
    bool tombstone = false;
    if (!decode_selector(encoded.bytes.data(), size, slot, generation, tombstone))
        return WifiCredentialStoreResult::CorruptRecord;
    state.generation = generation;
    state.tombstone = tombstone;
    state.slot = slot;
    if (tombstone) return WifiCredentialStoreResult::NotFound;

    size = 0;
    const auto record_io = storage_.read(slot == 0 ? WifiCredentialSlot::SlotA : WifiCredentialSlot::SlotB,
                                         encoded.bytes.data(), encoded.bytes.size(), size);
    if (record_io != WifiCredentialIoResult::Ok)
        return record_io == WifiCredentialIoResult::NotFound
            ? WifiCredentialStoreResult::CorruptRecord : map_io(record_io);
    if (!decode_record(encoded.bytes.data(), size, generation, state.record))
        return WifiCredentialStoreResult::CorruptRecord;
    return WifiCredentialStoreResult::Ok;
}

WifiCredentialStoreResult TwoSlotWifiCredentialStoreBackend::load(WifiCredentialRecord& record) {
    record.clear();
    if (protection() != WifiCredentialProtection::EncryptedWithVerifiedDeviceKey)
        return WifiCredentialStoreResult::ProtectedStorageUnavailable;
    ActiveState state;
    const auto result = read_state(state);
    if (result == WifiCredentialStoreResult::Ok) record = state.record;
    else record.clear();
    return result;
}

WifiCredentialStoreResult TwoSlotWifiCredentialStoreBackend::replace_atomically(
    const WifiCredentialRecord& record) {
    if (protection() != WifiCredentialProtection::EncryptedWithVerifiedDeviceKey)
        return WifiCredentialStoreResult::ProtectedStorageUnavailable;
    if (!record.valid()) return WifiCredentialStoreResult::InvalidRecord;

    ActiveState previous;
    const auto previous_result = read_state(previous);
    if (previous_result != WifiCredentialStoreResult::Ok &&
        previous_result != WifiCredentialStoreResult::NotFound)
        return previous_result;
    const std::uint32_t previous_generation = previous.generation;
    if (previous_generation == UINT32_MAX) return WifiCredentialStoreResult::CommitRejected;
    const std::uint32_t next_generation = previous_generation + 1;
    const std::uint8_t next_slot = previous_result == WifiCredentialStoreResult::Ok
        ? static_cast<std::uint8_t>(1u - previous.slot) : 0;

    SensitiveBuffer candidate_bytes;
    std::size_t candidate_size = 0;
    if (!encode_record(record, next_generation, candidate_bytes.bytes, candidate_size))
        return WifiCredentialStoreResult::InvalidRecord;
    const auto slot = next_slot == 0 ? WifiCredentialSlot::SlotA : WifiCredentialSlot::SlotB;
    const auto write_result = storage_.write(slot, candidate_bytes.bytes.data(), candidate_size);
    SensitiveBuffer readback;
    std::size_t readback_size = 0;
    const auto read_result = storage_.read(slot, readback.bytes.data(), readback.bytes.size(), readback_size);
    const bool slot_verified = read_result == WifiCredentialIoResult::Ok &&
        readback_size == candidate_size &&
        constant_bytes_equal(readback.bytes.data(), candidate_bytes.bytes.data(), candidate_size);
    if (!slot_verified) {
        return write_result == WifiCredentialIoResult::Rejected
            ? WifiCredentialStoreResult::CommitRejected
            : (write_result == WifiCredentialIoResult::OutcomeUnknown ||
               read_result == WifiCredentialIoResult::IoError
                ? WifiCredentialStoreResult::CommitOutcomeUnknown
                : WifiCredentialStoreResult::CommitRejected);
    }

    return write_selector_verified(next_slot, next_generation, false, previous);
}

WifiCredentialStoreResult TwoSlotWifiCredentialStoreBackend::write_selector_verified(
    std::uint8_t slot, std::uint32_t generation, bool tombstone,
    const ActiveState& previous) {
    const auto selector = encode_selector(slot, generation, tombstone);
    const auto write_result = storage_.write(WifiCredentialSlot::Selector,
                                              selector.data(), selector.size());
    ActiveState current;
    const auto read_result = read_state(current);
    if (tombstone) {
        if (read_result == WifiCredentialStoreResult::NotFound &&
            current.tombstone && current.generation == generation)
            return WifiCredentialStoreResult::Ok;
    } else if (read_result == WifiCredentialStoreResult::Ok && current.slot == slot &&
               current.generation == generation) {
        return WifiCredentialStoreResult::Ok;
    }

    const bool previous_still_active =
        (previous.generation == 0 && read_result == WifiCredentialStoreResult::NotFound &&
         !current.tombstone && current.generation == 0) ||
        (previous.generation != 0 && current.generation == previous.generation &&
         current.tombstone == previous.tombstone &&
         (previous.tombstone || current.slot == previous.slot) &&
         (previous.tombstone
              ? read_result == WifiCredentialStoreResult::NotFound
              : read_result == WifiCredentialStoreResult::Ok));
    if (previous_still_active && write_result == WifiCredentialIoResult::Rejected)
        return WifiCredentialStoreResult::CommitRejected;
    if (previous_still_active && write_result == WifiCredentialIoResult::Ok)
        return WifiCredentialStoreResult::CommitRejected;
    return WifiCredentialStoreResult::CommitOutcomeUnknown;
}

WifiCredentialStoreResult TwoSlotWifiCredentialStoreBackend::erase() {
    if (protection() != WifiCredentialProtection::EncryptedWithVerifiedDeviceKey)
        return WifiCredentialStoreResult::ProtectedStorageUnavailable;
    ActiveState previous;
    const auto previous_result = read_state(previous);
    if (previous_result == WifiCredentialStoreResult::NotFound && previous.tombstone) {
        const auto erase_a = storage_.erase(WifiCredentialSlot::SlotA);
        const auto erase_b = storage_.erase(WifiCredentialSlot::SlotB);
        return (erase_a == WifiCredentialIoResult::Ok || erase_a == WifiCredentialIoResult::NotFound) &&
               (erase_b == WifiCredentialIoResult::Ok || erase_b == WifiCredentialIoResult::NotFound)
            ? WifiCredentialStoreResult::Ok : WifiCredentialStoreResult::IoError;
    }
    if (previous_result != WifiCredentialStoreResult::Ok &&
        previous_result != WifiCredentialStoreResult::NotFound)
        return previous_result;
    if (previous.generation == UINT32_MAX) return WifiCredentialStoreResult::CommitRejected;
    const auto tombstone_generation = previous.generation + 1;
    auto result = write_selector_verified(kTombstoneSlot, tombstone_generation, true, previous);
    if (result != WifiCredentialStoreResult::Ok) return result;

    const auto erase_a = storage_.erase(WifiCredentialSlot::SlotA);
    const auto erase_b = storage_.erase(WifiCredentialSlot::SlotB);
    auto erase_result = [](WifiCredentialIoResult io) {
        return io == WifiCredentialIoResult::Ok || io == WifiCredentialIoResult::NotFound;
    };
    return erase_result(erase_a) && erase_result(erase_b)
        ? WifiCredentialStoreResult::Ok : WifiCredentialStoreResult::IoError;
}

}  // namespace gs::hub::connectivity
