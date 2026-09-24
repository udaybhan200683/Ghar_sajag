#include "firmware/hub/components/registry/registry_persistence.hpp"

#include <algorithm>
#include <limits>
#include <set>
#include <utility>

namespace gs::hub {
namespace {
using security::Bytes;
using security::CommissioningBinding;

constexpr std::size_t kHeaderSize = 28;
constexpr std::size_t kMaximumBlob = 8192;

void append_u64(Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

bool read_u64(const Bytes& in, std::size_t& cursor, std::uint64_t& value) {
    if (cursor > in.size() || in.size() - cursor < 8) return false;
    value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8) | in[cursor++];
    return true;
}

bool append_string(Bytes& out, const std::string& value, std::size_t maximum) {
    if (value.empty() || value.size() > maximum) return false;
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
    return true;
}

bool read_string(const Bytes& in, std::size_t& cursor,
                 std::string& value, std::size_t maximum) {
    if (cursor >= in.size()) return false;
    const auto length = in[cursor++];
    if (length == 0 || length > maximum || length > in.size() - cursor) return false;
    value.assign(reinterpret_cast<const char*>(in.data() + cursor), length);
    cursor += length;
    return true;
}

template <std::size_t N>
bool read_array(const Bytes& in, std::size_t& cursor, std::array<std::uint8_t, N>& value) {
    if (cursor > in.size() || N > in.size() - cursor) return false;
    std::copy_n(in.begin() + cursor, N, value.begin());
    cursor += N;
    return true;
}

template <std::size_t N>
void append_array(Bytes& out, const std::array<std::uint8_t, N>& value) {
    out.insert(out.end(), value.begin(), value.end());
}

bool encode(const HubRegistryState& state, Bytes& out) {
    if (!append_string(out, state.registry.home_id, 64) ||
        !append_string(out, state.registry.hub_id, 64) ||
        state.registry.active.size() > 255 ||
        state.registry.revoked_device_ids.size() > 255) return false;
    out.push_back(static_cast<std::uint8_t>(state.registry.active.size()));
    out.push_back(static_cast<std::uint8_t>(state.registry.revoked_device_ids.size()));
    for (const auto& record : state.registry.active) {
        const auto binding = std::find_if(state.bindings.begin(), state.bindings.end(),
            [&record](const CommissioningBinding& item) {
                return item.device_id == record.device_id;
            });
        if (binding == state.bindings.end() ||
            !append_string(out, record.device_id, 64) ||
            !append_string(out, record.logical_id, 24) ||
            !append_string(out, record.room, 24) ||
            !append_string(out, record.function, 24)) return false;
        append_array(out, record.p256_public_key);
        append_array(out, record.radio_mac);
        append_u64(out, record.last_session);
        out.push_back(record.quarantined ? 1 : 0);
        append_array(out, binding->hub_public_key);
        append_array(out, binding->installation_key);
    }
    for (const auto& id : state.registry.revoked_device_ids)
        if (!append_string(out, id, 64)) return false;
    return true;
}

bool decode(const Bytes& in, HubRegistryState& state) {
    std::size_t cursor = 0;
    if (!read_string(in, cursor, state.registry.home_id, 64) ||
        !read_string(in, cursor, state.registry.hub_id, 64) ||
        in.size() - cursor < 2) return false;
    const auto active_count = in[cursor++];
    const auto revoked_count = in[cursor++];
    state.registry.active.reserve(active_count);
    state.bindings.reserve(active_count);
    for (unsigned i = 0; i < active_count; ++i) {
        EnrolledNode record;
        record.home_id = state.registry.home_id;
        record.hub_id = state.registry.hub_id;
        if (!read_string(in, cursor, record.device_id, 64) ||
            !read_string(in, cursor, record.logical_id, 24) ||
            !read_string(in, cursor, record.room, 24) ||
            !read_string(in, cursor, record.function, 24) ||
            !read_array(in, cursor, record.p256_public_key) ||
            !read_array(in, cursor, record.radio_mac) ||
            !read_u64(in, cursor, record.last_session) || cursor >= in.size() ||
            in[cursor] > 1) return false;
        record.quarantined = in[cursor++] != 0;
        CommissioningBinding binding;
        binding.device_id = record.device_id;
        binding.home_id = record.home_id;
        binding.hub_id = record.hub_id;
        binding.logical_id = record.logical_id;
        binding.room = record.room;
        binding.function = record.function;
        binding.device_public_key = record.p256_public_key;
        if (!read_array(in, cursor, binding.hub_public_key) ||
            !read_array(in, cursor, binding.installation_key)) return false;
        state.registry.active.push_back(std::move(record));
        state.bindings.push_back(std::move(binding));
    }
    for (unsigned i = 0; i < revoked_count; ++i) {
        std::string id;
        if (!read_string(in, cursor, id, 64)) return false;
        state.registry.revoked_device_ids.push_back(std::move(id));
    }
    return cursor == in.size();
}

void wipe_bindings(security::CommissioningCrypto& crypto, HubRegistryState& state) {
    for (auto& binding : state.bindings)
        crypto.secure_zero(binding.installation_key.data(), binding.installation_key.size());
}
}  // namespace

HubRegistryRepository::HubRegistryRepository(security::CommissioningCrypto& crypto,
                                             security::SecurityBlobStore& store,
                                             const security::Key32& protected_wrapping_key,
                                             std::string home_id, std::string hub_id,
                                             const security::P256PublicKey& hub_public_key,
                                             std::size_t installed_capacity,
                                             std::size_t tombstone_capacity)
    : crypto_(crypto), store_(store), wrapping_key_(protected_wrapping_key),
      home_id_(std::move(home_id)), hub_id_(std::move(hub_id)),
      hub_public_key_(hub_public_key),
      installed_capacity_(installed_capacity), tombstone_capacity_(tombstone_capacity) {}

HubRegistryRepository::~HubRegistryRepository() {
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
}

void HubRegistryRepository::clear_keys(HubRegistryState& state) {
    wipe_bindings(crypto_, state);
}

bool HubRegistryRepository::valid(const HubRegistryState& state) const {
    if (!std::any_of(wrapping_key_.begin(), wrapping_key_.end(),
                     [](std::uint8_t byte) { return byte != 0; }) ||
        state.registry.home_id != home_id_ || state.registry.hub_id != hub_id_ ||
        state.registry.active.size() != state.bindings.size()) return false;
    NodeRegistry checked(home_id_, hub_id_, installed_capacity_, tombstone_capacity_);
    if (!checked.restore(state.registry)) return false;
    std::set<std::string> seen;
    for (const auto& binding : state.bindings) {
        const auto record = checked.find(binding.device_id);
        if (!record || !seen.insert(binding.device_id).second ||
            binding.home_id != home_id_ || binding.hub_id != hub_id_ ||
            binding.logical_id != record->logical_id || binding.room != record->room ||
            binding.function != record->function ||
            binding.device_public_key != record->p256_public_key ||
            hub_public_key_[0] != 0x04 ||
            binding.hub_public_key != hub_public_key_ ||
            !std::any_of(binding.installation_key.begin(), binding.installation_key.end(),
                         [](std::uint8_t byte) { return byte != 0; })) return false;
    }
    return true;
}

bool HubRegistryRepository::preserves_security_state(const HubRegistryState& previous,
                                                     const HubRegistryState& next) const {
    for (const auto& id : previous.registry.revoked_device_ids)
        if (std::find(next.registry.revoked_device_ids.begin(),
                      next.registry.revoked_device_ids.end(), id) ==
            next.registry.revoked_device_ids.end()) return false;
    for (const auto& old : previous.registry.active) {
        const auto fresh = std::find_if(next.registry.active.begin(), next.registry.active.end(),
            [&old](const EnrolledNode& item) { return item.device_id == old.device_id; });
        if (fresh == next.registry.active.end()) {
            if (std::find(next.registry.revoked_device_ids.begin(),
                          next.registry.revoked_device_ids.end(), old.device_id) ==
                next.registry.revoked_device_ids.end()) return false;
            continue;
        }
        if (fresh->p256_public_key != old.p256_public_key ||
            fresh->radio_mac != old.radio_mac || fresh->logical_id != old.logical_id ||
            fresh->room != old.room || fresh->function != old.function ||
            fresh->last_session < old.last_session ||
            (old.quarantined && !fresh->quarantined)) return false;
        const auto old_binding = std::find_if(previous.bindings.begin(), previous.bindings.end(),
            [&old](const CommissioningBinding& item) { return item.device_id == old.device_id; });
        const auto new_binding = std::find_if(next.bindings.begin(), next.bindings.end(),
            [&old](const CommissioningBinding& item) { return item.device_id == old.device_id; });
        if (old_binding == previous.bindings.end() || new_binding == next.bindings.end() ||
            old_binding->hub_public_key != new_binding->hub_public_key ||
            !crypto_.constant_time_equal(old_binding->installation_key.data(),
                                         new_binding->installation_key.data(),
                                         old_binding->installation_key.size())) return false;
    }
    return true;
}

HubRegistryLoad HubRegistryRepository::load() {
    Bytes blob;
    bool found = false;
    if (!store_.read(blob, found)) return {HubRegistryLoadStatus::IoError, 0, std::nullopt};
    if (!found) return {HubRegistryLoadStatus::Missing, 0, std::nullopt};
    if (blob.size() < kHeaderSize + security::GcmTag{}.size() ||
        blob.size() > kMaximumBlob || blob[0] != 'G' || blob[1] != 'S' ||
        blob[2] != 'R' || blob[3] != 'G' || blob[4] != 1 || blob[5] != 0)
        return {HubRegistryLoadStatus::Corrupt, 0, std::nullopt};
    std::size_t header_cursor = 6;
    std::uint64_t generation = 0;
    if (!read_u64(blob, header_cursor, generation) || generation == 0)
        return {HubRegistryLoadStatus::Corrupt, 0, std::nullopt};
    security::Nonce12 nonce{};
    std::copy_n(blob.begin() + header_cursor, nonce.size(), nonce.begin());
    const auto length = static_cast<std::size_t>((blob[26] << 8) | blob[27]);
    if (blob.size() != kHeaderSize + length + security::GcmTag{}.size())
        return {HubRegistryLoadStatus::Corrupt, 0, std::nullopt};
    const Bytes aad(blob.begin(), blob.begin() + kHeaderSize);
    const Bytes cipher(blob.begin() + kHeaderSize, blob.begin() + kHeaderSize + length);
    security::GcmTag tag{};
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    Bytes plain;
    if (!crypto_.open_aes256_gcm(wrapping_key_, nonce, aad, cipher, tag, plain) ||
        plain.size() != length) {
        crypto_.secure_zero(plain.data(), plain.size());
        return {HubRegistryLoadStatus::Corrupt, 0, std::nullopt};
    }
    HubRegistryState state;
    const bool okay = decode(plain, state) && valid(state);
    crypto_.secure_zero(plain.data(), plain.size());
    if (!okay) {
        wipe_bindings(crypto_, state);
        return {HubRegistryLoadStatus::Corrupt, 0, std::nullopt};
    }
    return {HubRegistryLoadStatus::Ready, generation, std::move(state)};
}

bool HubRegistryRepository::save(const HubRegistryState& state) {
    if (!valid(state)) return false;
    auto previous = load();
    if (previous.status != HubRegistryLoadStatus::Missing &&
        previous.status != HubRegistryLoadStatus::Ready) return false;
    const bool allowed = previous.status == HubRegistryLoadStatus::Missing ||
        (previous.generation < std::numeric_limits<std::uint64_t>::max() &&
         preserves_security_state(*previous.state, state));
    if (previous.state) wipe_bindings(crypto_, *previous.state);
    if (!allowed) return false;
    Bytes plain;
    if (!encode(state, plain) || plain.size() + kHeaderSize + security::GcmTag{}.size() >
                                      kMaximumBlob) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    security::Nonce12 nonce{};
    if (!crypto_.random_bytes(nonce.data(), nonce.size())) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    Bytes blob{'G', 'S', 'R', 'G', 1, 0};
    append_u64(blob, previous.generation + 1);
    append_array(blob, nonce);
    blob.push_back(static_cast<std::uint8_t>(plain.size() >> 8));
    blob.push_back(static_cast<std::uint8_t>(plain.size()));
    Bytes cipher;
    security::GcmTag tag{};
    const bool sealed = crypto_.seal_aes256_gcm(wrapping_key_, nonce, blob,
                                                 plain, cipher, tag);
    crypto_.secure_zero(plain.data(), plain.size());
    if (!sealed || cipher.size() + kHeaderSize + tag.size() > kMaximumBlob) return false;
    blob.insert(blob.end(), cipher.begin(), cipher.end());
    append_array(blob, tag);
    return store_.write(blob);
}

}  // namespace gs::hub
