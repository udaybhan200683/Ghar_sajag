#include "firmware/common/security/association_persistence.hpp"

#include <algorithm>
#include <limits>

namespace gs::security {
namespace {
constexpr std::size_t kHeaderSize = 28;
constexpr std::size_t kMaximumBlob = 1024;
constexpr std::uint8_t kPaired = 1;
constexpr std::uint8_t kReset = 2;

void append_u64(Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

std::uint64_t read_u64(const std::uint8_t* data) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < 8; ++i) value = (value << 8) | data[i];
    return value;
}

void append_string(Bytes& out, const std::string& value) {
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
}

bool read_string(const Bytes& data, std::size_t& cursor, std::string& out) {
    if (cursor >= data.size()) return false;
    const auto length = data[cursor++];
    if (length == 0 || length > 64 || cursor + length > data.size()) return false;
    out.assign(reinterpret_cast<const char*>(data.data() + cursor), length);
    cursor += length;
    return true;
}

bool valid_binding(const CommissioningBinding& binding) {
    for (const auto* field : {&binding.device_id, &binding.hub_id, &binding.home_id,
                              &binding.logical_id, &binding.room, &binding.function})
        if (field->empty() || field->size() > 64) return false;
    return binding.device_public_key[0] == 0x04 && binding.hub_public_key[0] == 0x04 &&
           std::any_of(binding.installation_key.begin(), binding.installation_key.end(),
                       [](std::uint8_t value) { return value != 0; });
}

Bytes encode_binding(const CommissioningBinding& binding) {
    Bytes out;
    append_string(out, binding.device_id);
    append_string(out, binding.hub_id);
    append_string(out, binding.home_id);
    append_string(out, binding.logical_id);
    append_string(out, binding.room);
    append_string(out, binding.function);
    out.insert(out.end(), binding.device_public_key.begin(), binding.device_public_key.end());
    out.insert(out.end(), binding.hub_public_key.begin(), binding.hub_public_key.end());
    out.insert(out.end(), binding.installation_key.begin(), binding.installation_key.end());
    return out;
}

bool decode_binding(const Bytes& data, CommissioningBinding& binding) {
    std::size_t cursor = 0;
    if (!read_string(data, cursor, binding.device_id) ||
        !read_string(data, cursor, binding.hub_id) ||
        !read_string(data, cursor, binding.home_id) ||
        !read_string(data, cursor, binding.logical_id) ||
        !read_string(data, cursor, binding.room) ||
        !read_string(data, cursor, binding.function) ||
        data.size() - cursor != binding.device_public_key.size() +
                                binding.hub_public_key.size() +
                                binding.installation_key.size()) return false;
    std::copy_n(data.begin() + cursor, binding.device_public_key.size(),
                binding.device_public_key.begin());
    cursor += binding.device_public_key.size();
    std::copy_n(data.begin() + cursor, binding.hub_public_key.size(),
                binding.hub_public_key.begin());
    cursor += binding.hub_public_key.size();
    std::copy_n(data.begin() + cursor, binding.installation_key.size(),
                binding.installation_key.begin());
    return valid_binding(binding);
}
}  // namespace

AssociationRepository::AssociationRepository(CommissioningCrypto& crypto,
                                             AssociationBlobStore& store,
                                             const Key32& protected_wrapping_key)
    : crypto_(crypto), store_(store), wrapping_key_(protected_wrapping_key) {}

AssociationRepository::~AssociationRepository() {
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
}

AssociationState AssociationRepository::load() {
    Bytes blob;
    bool found = false;
    if (!store_.read(blob, found)) return {AssociationStatus::IoError, 0, std::nullopt};
    if (!found) return {AssociationStatus::Missing, 0, std::nullopt};
    if (blob.size() < kHeaderSize + GcmTag{}.size() || blob.size() > kMaximumBlob ||
        blob[0] != 'G' || blob[1] != 'S' || blob[2] != 'A' || blob[3] != 'S' ||
        blob[4] != 1 || (blob[5] != kPaired && blob[5] != kReset))
        return {AssociationStatus::Corrupt, 0, std::nullopt};
    const auto generation = read_u64(blob.data() + 6);
    const auto length = static_cast<std::size_t>((blob[26] << 8) | blob[27]);
    if (generation == 0 || blob.size() != kHeaderSize + length + GcmTag{}.size())
        return {AssociationStatus::Corrupt, 0, std::nullopt};
    Nonce12 nonce{};
    std::copy_n(blob.begin() + 14, nonce.size(), nonce.begin());
    const Bytes aad(blob.begin(), blob.begin() + kHeaderSize);
    const Bytes cipher(blob.begin() + kHeaderSize, blob.begin() + kHeaderSize + length);
    GcmTag tag{};
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    Bytes opened;
    if (!crypto_.open_aes256_gcm(wrapping_key_, nonce, aad, cipher, tag, opened) ||
        opened.size() != length) return {AssociationStatus::Corrupt, 0, std::nullopt};
    if (blob[5] == kReset) {
        const bool empty = opened.empty();
        crypto_.secure_zero(opened.data(), opened.size());
        return {empty ? AssociationStatus::Unpaired : AssociationStatus::Corrupt,
                empty ? generation : 0, std::nullopt};
    }
    CommissioningBinding binding;
    const bool valid = decode_binding(opened, binding);
    crypto_.secure_zero(opened.data(), opened.size());
    if (!valid) {
        crypto_.secure_zero(binding.installation_key.data(), binding.installation_key.size());
        return {AssociationStatus::Corrupt, 0, std::nullopt};
    }
    AssociationState state;
    state.status = AssociationStatus::Paired;
    state.generation = generation;
    state.binding = binding;
    crypto_.secure_zero(binding.installation_key.data(), binding.installation_key.size());
    return state;
}

bool AssociationRepository::write_record(std::uint64_t generation, bool paired,
                                          const CommissioningBinding* binding) {
    if (generation == 0 || (paired && (binding == nullptr || !valid_binding(*binding))))
        return false;
    Bytes plain = paired ? encode_binding(*binding) : Bytes{};
    if (plain.size() + kHeaderSize + GcmTag{}.size() > kMaximumBlob) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    Nonce12 nonce{};
    if (!crypto_.random_bytes(nonce.data(), nonce.size())) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    Bytes blob{'G', 'S', 'A', 'S', 1, paired ? kPaired : kReset};
    append_u64(blob, generation);
    blob.insert(blob.end(), nonce.begin(), nonce.end());
    blob.push_back(static_cast<std::uint8_t>(plain.size() >> 8));
    blob.push_back(static_cast<std::uint8_t>(plain.size()));
    Bytes cipher;
    GcmTag tag{};
    const bool sealed = crypto_.seal_aes256_gcm(wrapping_key_, nonce, blob,
                                                 plain, cipher, tag);
    crypto_.secure_zero(plain.data(), plain.size());
    if (!sealed || cipher.size() + kHeaderSize + tag.size() > kMaximumBlob)
        return false;
    blob.insert(blob.end(), cipher.begin(), cipher.end());
    blob.insert(blob.end(), tag.begin(), tag.end());
    return store_.write(blob);
}

bool AssociationRepository::save_initial(const CommissioningBinding& binding) {
    const auto current = load();
    if (current.status != AssociationStatus::Missing &&
        current.status != AssociationStatus::Unpaired) return false;
    if (current.generation == std::numeric_limits<std::uint64_t>::max()) return false;
    return write_record(current.generation + 1, true, &binding);
}

bool AssociationRepository::factory_reset() {
    const auto current = load();
    if (current.status == AssociationStatus::Unpaired ||
        current.status == AssociationStatus::Missing) return true;
    if (current.status != AssociationStatus::Paired ||
        current.generation == std::numeric_limits<std::uint64_t>::max()) return false;
    return write_record(current.generation + 1, false, nullptr);
}

}  // namespace gs::security
