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
constexpr std::size_t kMaximumBlob = 5077;
constexpr std::size_t kEnrollmentSlotCount = kMaxEnrollmentSlots;

void append_u32(Bytes& out, std::uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

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

bool read_u32(const Bytes& in, std::size_t& cursor, std::uint32_t& value) {
    if (cursor > in.size() || in.size() - cursor < 4) return false;
    value = 0;
    for (unsigned i = 0; i < 4; ++i) value = (value << 8) | in[cursor++];
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

bool fresh_registry_metadata(const RegistryMigrationBarrier& barrier) {
    return barrier.phase == RegistryMigrationPhase::FreshInstallation &&
        barrier.source_epoch == 0 && barrier.source_checkpoint_generation == 0 &&
        std::all_of(barrier.target_checkpoint_digest.begin(), barrier.target_checkpoint_digest.end(),
                    [](std::uint8_t b) { return b == 0; });
}

bool encode_v2(const HubRegistryState& state, Bytes& out) {
    if (!append_string(out, state.registry.home_id, 64) ||
        !append_string(out, state.registry.hub_id, 64) ||
        state.registry.active.size() > 255 ||
        state.registry.revoked_device_ids.size() > 255 ||
        state.migration.phase == RegistryMigrationPhase::Uninitialized ||
        (state.migration.phase == RegistryMigrationPhase::FreshInstallation
            ? !fresh_registry_metadata(state.migration)
            : state.migration.source_epoch == 0 || state.migration.source_checkpoint_generation == 0)) return false;
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
        out.push_back(record.enrollment_slot);
    }
    for (const auto& id : state.registry.revoked_device_ids)
        if (!append_string(out, id, 64)) return false;
    out.insert(out.end(), {'G', 'O', 'W', 'N'});
    out.push_back(static_cast<std::uint8_t>(kEnrollmentSlotCount));
    out.push_back(0);  // Reserved flags.
    for (const auto& descriptor : state.registry.enrollment_slots) {
        const auto state_code = static_cast<std::uint8_t>(descriptor.state);
        if (state_code > static_cast<std::uint8_t>(EnrollmentSlotState::Retired) ||
            descriptor.device_id.size() > 64) return false;
        if (descriptor.state == EnrollmentSlotState::NeverOwned) {
            if (descriptor.generation != 0 || !descriptor.device_id.empty() ||
                std::any_of(descriptor.owner_digest.begin(), descriptor.owner_digest.end(),
                            [](std::uint8_t b) { return b != 0; })) return false;
        } else if (descriptor.state == EnrollmentSlotState::Active ||
                   descriptor.state == EnrollmentSlotState::Retired) {
            if (descriptor.generation == 0 || descriptor.device_id.empty() ||
                std::all_of(descriptor.owner_digest.begin(), descriptor.owner_digest.end(),
                            [](std::uint8_t b) { return b == 0; })) return false;
        } else {
            return false;  // Released is reserved until a proved release protocol exists.
        }
        out.push_back(state_code);
        append_u32(out, descriptor.generation);
        out.push_back(static_cast<std::uint8_t>(descriptor.device_id.size()));
        out.insert(out.end(), descriptor.device_id.begin(), descriptor.device_id.end());
        append_array(out, descriptor.owner_digest);
    }
    out.push_back(static_cast<std::uint8_t>(state.migration.phase));
    append_u32(out, state.migration.source_epoch);
    append_u64(out, state.migration.source_checkpoint_generation);
    append_array(out, state.migration.target_checkpoint_digest);
    const bool target_digest_present=std::any_of(state.migration.target_checkpoint_digest.begin(),
        state.migration.target_checkpoint_digest.end(),[](std::uint8_t b){return b!=0;});
    if ((state.migration.phase == RegistryMigrationPhase::Activated) != target_digest_present)
        return false;
    return true;
}

bool decode(const Bytes& in, std::uint8_t schema, HubRegistryState& state) {
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
        if (schema == 2) {
            if (cursor >= in.size()) return false;
            record.enrollment_slot = in[cursor++];
        }
        state.registry.active.push_back(std::move(record));
        state.bindings.push_back(std::move(binding));
    }
    for (unsigned i = 0; i < revoked_count; ++i) {
        std::string id;
        if (!read_string(in, cursor, id, 64)) return false;
        state.registry.revoked_device_ids.push_back(std::move(id));
    }
    if (schema == 2) {
        if (in.size() - cursor < 6 || in[cursor++] != 'G' || in[cursor++] != 'O' ||
            in[cursor++] != 'W' || in[cursor++] != 'N' ||
            in[cursor++] != kEnrollmentSlotCount || in[cursor++] != 0) return false;
        for (auto& descriptor : state.registry.enrollment_slots) {
            std::uint8_t state_code = 0;
            if (cursor >= in.size()) return false;
            state_code = in[cursor++];
            if (state_code > static_cast<std::uint8_t>(EnrollmentSlotState::Retired) ||
                !read_u32(in, cursor, descriptor.generation) || cursor >= in.size()) return false;
            descriptor.state = static_cast<EnrollmentSlotState>(state_code);
            const auto id_length = in[cursor++];
            if (id_length > 64 || id_length > in.size() - cursor) return false;
            descriptor.device_id.assign(reinterpret_cast<const char*>(in.data() + cursor),
                                        id_length);
            cursor += id_length;
            if (!read_array(in, cursor, descriptor.owner_digest)) return false;
        }
        std::uint8_t phase = 0;
        if (cursor >= in.size()) return false;
        phase = in[cursor++];
        if (phase < static_cast<std::uint8_t>(RegistryMigrationPhase::Prepared) ||
            phase > static_cast<std::uint8_t>(RegistryMigrationPhase::FreshInstallation) ||
            !read_u32(in, cursor, state.migration.source_epoch) ||
            !read_u64(in, cursor, state.migration.source_checkpoint_generation) ||
            !read_array(in, cursor, state.migration.target_checkpoint_digest)) return false;
        state.migration.phase = static_cast<RegistryMigrationPhase>(phase);
        if (state.migration.phase == RegistryMigrationPhase::FreshInstallation &&
            !fresh_registry_metadata(state.migration)) return false;
        const bool target_digest_present=std::any_of(state.migration.target_checkpoint_digest.begin(),
            state.migration.target_checkpoint_digest.end(),[](std::uint8_t b){return b!=0;});
        if ((state.migration.phase == RegistryMigrationPhase::Activated) != target_digest_present)
            return false;
        for (auto& record : state.registry.active) {
            if (record.enrollment_slot >= state.registry.enrollment_slots.size()) return false;
            const auto& descriptor = state.registry.enrollment_slots[record.enrollment_slot];
            if (descriptor.state != EnrollmentSlotState::Active ||
                descriptor.device_id != record.device_id || descriptor.generation == 0)
                return false;
            record.enrollment_generation = descriptor.generation;
        }
    }
    return cursor == in.size();
}

void wipe_bindings(security::CommissioningCrypto& crypto, HubRegistryState& state) {
    for (auto& binding : state.bindings)
        crypto.secure_zero(binding.installation_key.data(), binding.installation_key.size());
}

struct RegistryStateWiper {
    security::CommissioningCrypto& crypto;
    HubRegistryState& state;
    ~RegistryStateWiper() { wipe_bindings(crypto, state); }
};

bool compute_owner_digest(security::CommissioningCrypto& crypto,
                          const security::Key32& key, const EnrolledNode& record,
                          std::uint8_t slot, security::Key32& digest) {
    constexpr char domain[] = "gs-enrollment-owner-v2";
    Bytes message(domain, domain + sizeof(domain) - 1U);
    if (!append_string(message, record.home_id, 64) ||
        !append_string(message, record.hub_id, 64) ||
        !append_string(message, record.device_id, 64)) return false;
    append_array(message, record.p256_public_key);
    if (!append_string(message, record.logical_id, 24)) return false;
    message.push_back(slot);
    append_u32(message, record.enrollment_generation);
    const bool okay = crypto.hmac_sha256(key, message, digest);
    crypto.secure_zero(message.data(), message.size());
    return okay;
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

bool HubRegistryRepository::valid(const HubRegistryState& state,
                                  std::uint8_t schema_version) const {
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
    const bool owner_valid = schema_version == 1 || valid_owner_digests(state);
    return owner_valid;
}

bool HubRegistryRepository::prepare_owner_digests(HubRegistryState& state) const {
    const bool descriptors_present = std::any_of(
        state.registry.enrollment_slots.begin(), state.registry.enrollment_slots.end(),
        [](const EnrollmentSlotDescriptor& descriptor) {
            return descriptor.state != EnrollmentSlotState::NeverOwned ||
                   descriptor.generation != 0 || !descriptor.device_id.empty();
    });
    if (!descriptors_present && !state.registry.active.empty()) {
        // Prepare only identities that the authenticated v1 table still
        // proves. A bare tombstone remains preserved without a fabricated
        // descriptor; migration preflight must separately prove that no
        // recoverable evidence still depends on that historical owner.
        if (state.registry.active.size() > kEnrollmentSlotCount) return false;
        std::sort(state.registry.active.begin(), state.registry.active.end(),
            [](const EnrolledNode& left, const EnrolledNode& right) {
                return left.device_id < right.device_id;
            });
        state.registry.enrollment_slots = {};
        for (std::size_t slot = 0; slot < state.registry.active.size(); ++slot) {
            auto& record = state.registry.active[slot];
            record.enrollment_slot = static_cast<std::uint8_t>(slot);
            record.enrollment_generation = 1;
            auto& descriptor = state.registry.enrollment_slots[slot];
            descriptor.state = EnrollmentSlotState::Active;
            descriptor.generation = 1;
            descriptor.device_id = record.device_id;
        }
    }
    for (std::size_t slot = 0; slot < state.registry.enrollment_slots.size(); ++slot) {
        auto& descriptor = state.registry.enrollment_slots[slot];
        if (descriptor.state != EnrollmentSlotState::Active) continue;
        const auto record = std::find_if(state.registry.active.begin(), state.registry.active.end(),
            [slot](const EnrolledNode& node) {
                return node.enrollment_slot == slot && node.enrollment_generation != 0;
            });
        if (record == state.registry.active.end() ||
            record->enrollment_generation != descriptor.generation ||
            record->device_id != descriptor.device_id) return false;
        if (!compute_owner_digest(crypto_, wrapping_key_, *record,
                                  static_cast<std::uint8_t>(slot),
                                  descriptor.owner_digest)) return false;
    }
    return true;
}

bool HubRegistryRepository::prepare_v2(const HubRegistryState& authenticated_source,
        std::uint32_t source_epoch, std::uint64_t source_checkpoint_generation,
        HubRegistryState& prepared) const {
    if (source_epoch == 0 || source_checkpoint_generation == 0) return false;
    const bool has_descriptors = std::any_of(
        authenticated_source.registry.enrollment_slots.begin(),
        authenticated_source.registry.enrollment_slots.end(),
        [](const EnrollmentSlotDescriptor& descriptor) {
            return descriptor.state != EnrollmentSlotState::NeverOwned ||
                   descriptor.generation != 0 || !descriptor.device_id.empty() ||
                   std::any_of(descriptor.owner_digest.begin(), descriptor.owner_digest.end(),
                               [](std::uint8_t byte) { return byte != 0; });
        });
    if (authenticated_source.migration.phase != RegistryMigrationPhase::Uninitialized) {
        if (authenticated_source.migration.phase != RegistryMigrationPhase::Prepared ||
            authenticated_source.migration.source_epoch != source_epoch ||
            authenticated_source.migration.source_checkpoint_generation !=
                source_checkpoint_generation ||
            !valid(authenticated_source) ||
            std::any_of(authenticated_source.migration.target_checkpoint_digest.begin(),
                        authenticated_source.migration.target_checkpoint_digest.end(),
                        [](std::uint8_t byte) { return byte != 0; })) return false;
        prepared = authenticated_source;
        return true;
    }
    if (has_descriptors || !valid(authenticated_source, 1)) return false;
    prepared = authenticated_source;
    prepared.registry.enrollment_slots = {};
    for (auto& record : prepared.registry.active) {
        record.enrollment_slot = 0xff;
        record.enrollment_generation = 0;
    }
    prepared.migration = {};
    prepared.migration.phase = RegistryMigrationPhase::Prepared;
    prepared.migration.source_epoch = source_epoch;
    prepared.migration.source_checkpoint_generation = source_checkpoint_generation;
    if (!prepare_owner_digests(prepared) || !valid(prepared)) return false;
    return true;
}

bool HubRegistryRepository::enrollment_table_digest(const HubRegistryState& state,
        std::array<std::uint8_t, 32>& digest) const {
    digest.fill(0);
    if (!valid(state) || !valid_owner_digests(state)) return false;
    Bytes canonical{'G','R','T','2',static_cast<std::uint8_t>(kEnrollmentSlotCount)};
    for (std::size_t slot = 0; slot < state.registry.enrollment_slots.size(); ++slot) {
        const auto& descriptor = state.registry.enrollment_slots[slot];
        const bool occupied = descriptor.state == EnrollmentSlotState::Active ||
                              descriptor.state == EnrollmentSlotState::Retired;
        canonical.push_back(occupied ? 1U : 0U);
        canonical.push_back(static_cast<std::uint8_t>(slot));
        append_u32(canonical, occupied ? descriptor.generation : 0U);
        if (occupied) {
            if (!append_string(canonical, descriptor.device_id, 64)) return false;
            append_array(canonical, descriptor.owner_digest);
        } else {
            canonical.push_back(0);
            canonical.insert(canonical.end(), 32, 0);
        }
    }
    constexpr char domain[] = "gs-enrollment-table-v2";
    Bytes message(domain, domain + sizeof(domain) - 1U);
    message.insert(message.end(), canonical.begin(), canonical.end());
    const bool okay = crypto_.hmac_sha256(wrapping_key_, message, digest);
    crypto_.secure_zero(canonical.data(), canonical.size());
    crypto_.secure_zero(message.data(), message.size());
    return okay && std::any_of(digest.begin(), digest.end(), [](std::uint8_t b) { return b != 0; });
}

bool HubRegistryRepository::valid_owner_digests(const HubRegistryState& state) const {
    for (std::size_t slot = 0; slot < state.registry.enrollment_slots.size(); ++slot) {
        const auto& descriptor = state.registry.enrollment_slots[slot];
        if (descriptor.state == EnrollmentSlotState::NeverOwned) {
            if (descriptor.generation != 0 || !descriptor.device_id.empty() ||
                std::any_of(descriptor.owner_digest.begin(), descriptor.owner_digest.end(),
                            [](std::uint8_t b) { return b != 0; })) return false;
            continue;
        }
        if (descriptor.state == EnrollmentSlotState::Released ||
            descriptor.generation == 0 || descriptor.device_id.empty() ||
            std::all_of(descriptor.owner_digest.begin(), descriptor.owner_digest.end(),
                        [](std::uint8_t b) { return b == 0; })) return false;
        if (descriptor.state == EnrollmentSlotState::Retired) {
            if (std::find(state.registry.revoked_device_ids.begin(),
                          state.registry.revoked_device_ids.end(), descriptor.device_id) ==
                state.registry.revoked_device_ids.end()) return false;
            continue;
        }
        if (descriptor.state != EnrollmentSlotState::Active) return false;
        const auto record = std::find_if(state.registry.active.begin(), state.registry.active.end(),
            [slot](const EnrolledNode& node) { return node.enrollment_slot == slot; });
        if (record == state.registry.active.end() || record->device_id != descriptor.device_id ||
            record->enrollment_generation != descriptor.generation) return false;
        security::Key32 expected{};
        const bool valid = compute_owner_digest(crypto_, wrapping_key_, *record,
                                                static_cast<std::uint8_t>(slot), expected) &&
            crypto_.constant_time_equal(expected.data(), descriptor.owner_digest.data(),
                                        descriptor.owner_digest.size());
        crypto_.secure_zero(expected.data(), expected.size());
        if (!valid) return false;
    }
    return true;
}

bool HubRegistryRepository::preserves_security_state(const HubRegistryState& previous,
                                                     const HubRegistryState& next) const {
    if (next.migration.phase < previous.migration.phase ||
        (previous.migration.phase != RegistryMigrationPhase::Uninitialized &&
         (next.migration.source_epoch != previous.migration.source_epoch ||
          next.migration.source_checkpoint_generation != previous.migration.source_checkpoint_generation)) ||
        (previous.migration.phase == RegistryMigrationPhase::Activated &&
         (next.migration.phase != RegistryMigrationPhase::Activated ||
          next.migration.target_checkpoint_digest != previous.migration.target_checkpoint_digest)))
        return false;
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
            (!crypto_.constant_time_equal(old_binding->installation_key.data(),
                                          new_binding->installation_key.data(),
                                          old_binding->installation_key.size()) &&
             (old.last_session != 0 || fresh->last_session != 0 ||
              old.quarantined || fresh->quarantined))) return false;
        if (old.enrollment_generation != 0 &&
            (fresh->enrollment_slot != old.enrollment_slot ||
             fresh->enrollment_generation != old.enrollment_generation)) return false;
    }
    for (std::size_t slot = 0; slot < previous.registry.enrollment_slots.size(); ++slot) {
        const auto& old = previous.registry.enrollment_slots[slot];
        if (old.state == EnrollmentSlotState::NeverOwned) continue;
        const auto& fresh = next.registry.enrollment_slots[slot];
        if (fresh.generation != old.generation || fresh.device_id != old.device_id ||
            fresh.owner_digest != old.owner_digest ||
            (old.state == EnrollmentSlotState::Retired &&
             fresh.state != EnrollmentSlotState::Retired) ||
            (old.state == EnrollmentSlotState::Active &&
             fresh.state != EnrollmentSlotState::Active &&
             fresh.state != EnrollmentSlotState::Retired)) return false;
    }
    return true;
}

HubRegistryLoad HubRegistryRepository::load() {
    Bytes blob;
    bool found = false;
    if (!store_.read(blob, found)) return {HubRegistryLoadStatus::IoError, 0, 0, std::nullopt};
    if (!found) return {HubRegistryLoadStatus::Missing, 0, 0, std::nullopt};
    if (blob.size() < kHeaderSize + security::GcmTag{}.size() ||
        blob.size() > kMaximumBlob || blob[0] != 'G' || blob[1] != 'S' ||
        blob[2] != 'R' || blob[3] != 'G' ||
        (blob[4] != 1 && blob[4] != 2) || blob[5] != 0)
        return {HubRegistryLoadStatus::Corrupt, 0, 0, std::nullopt};
    const auto schema_version = blob[4];
    std::size_t header_cursor = 6;
    std::uint64_t generation = 0;
    if (!read_u64(blob, header_cursor, generation) || generation == 0)
        return {HubRegistryLoadStatus::Corrupt, 0, 0, std::nullopt};
    security::Nonce12 nonce{};
    std::copy_n(blob.begin() + header_cursor, nonce.size(), nonce.begin());
    const auto length = static_cast<std::size_t>((blob[26] << 8) | blob[27]);
    if (blob.size() != kHeaderSize + length + security::GcmTag{}.size())
        return {HubRegistryLoadStatus::Corrupt, 0, 0, std::nullopt};
    const Bytes aad(blob.begin(), blob.begin() + kHeaderSize);
    const Bytes cipher(blob.begin() + kHeaderSize, blob.begin() + kHeaderSize + length);
    security::GcmTag tag{};
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    Bytes plain;
    if (!crypto_.open_aes256_gcm(wrapping_key_, nonce, aad, cipher, tag, plain) ||
        plain.size() != length) {
        crypto_.secure_zero(plain.data(), plain.size());
        return {HubRegistryLoadStatus::Corrupt, 0, 0, std::nullopt};
    }
    HubRegistryState state;
    const bool okay = decode(plain, schema_version, state) && valid(state, schema_version);
    crypto_.secure_zero(plain.data(), plain.size());
    if (!okay) {
        wipe_bindings(crypto_, state);
        return {HubRegistryLoadStatus::Corrupt, 0, 0, std::nullopt};
    }
    return {HubRegistryLoadStatus::Ready, generation, schema_version, std::move(state)};
}

bool HubRegistryRepository::save(const HubRegistryState& state) {
    HubRegistryState prepared = state;
    RegistryStateWiper prepared_wiper{crypto_, prepared};
    if (!prepare_owner_digests(prepared) || !valid(prepared)) return false;
    auto previous = load();
    if (previous.status != HubRegistryLoadStatus::Missing &&
        previous.status != HubRegistryLoadStatus::Ready) return false;
    if (previous.status == HubRegistryLoadStatus::Missing &&
        prepared.migration.phase == RegistryMigrationPhase::Uninitialized) {
        if (prepared.migration.source_epoch != 0 || prepared.migration.source_checkpoint_generation != 0 ||
            std::any_of(prepared.migration.target_checkpoint_digest.begin(), prepared.migration.target_checkpoint_digest.end(),
                        [](std::uint8_t b) { return b != 0; })) return false;
        prepared.migration.phase = RegistryMigrationPhase::FreshInstallation;
    }
    const bool allowed = previous.status == HubRegistryLoadStatus::Missing ||
        (previous.generation < std::numeric_limits<std::uint64_t>::max() &&
         preserves_security_state(*previous.state, prepared));
    if (previous.status == HubRegistryLoadStatus::Ready && previous.schema_version == 1 &&
        prepared.migration.phase != RegistryMigrationPhase::Prepared) {
        if (previous.state) wipe_bindings(crypto_, *previous.state);
        return false;
    }
    if (previous.state) wipe_bindings(crypto_, *previous.state);
    if (!allowed) return false;
    Bytes plain;
    if (!encode_v2(prepared, plain) || plain.size() + kHeaderSize + security::GcmTag{}.size() >
                                      kMaximumBlob) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    security::Nonce12 nonce{};
    if (!crypto_.random_bytes(nonce.data(), nonce.size())) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    Bytes blob{'G', 'S', 'R', 'G', 2, 0};
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
    const bool api_result = store_.write(blob);
    Bytes readback;
    bool found = false;
    if (!store_.read(readback, found) || !found || readback != blob) return false;
    auto verified = load();
    if (verified.status != HubRegistryLoadStatus::Ready ||
        verified.schema_version != 2 || verified.generation != previous.generation + 1 ||
        !verified.state || !valid(*verified.state)) {
        if (verified.state) {
            auto state_copy = *verified.state;
            wipe_bindings(crypto_, state_copy);
        }
        return false;
    }
    const bool same_generation = verified.generation == previous.generation + 1;
    wipe_bindings(crypto_, *verified.state);
    (void)api_result; // Exact authenticated readback resolves PersistThenFail.
    return same_generation;
}

}  // namespace gs::hub
