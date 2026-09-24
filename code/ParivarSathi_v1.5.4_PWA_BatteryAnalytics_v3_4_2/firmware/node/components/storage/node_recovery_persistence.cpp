#include "firmware/node/components/storage/node_recovery_persistence.hpp"

#include <algorithm>
#include <cstring>
#include <limits>

namespace gs::node {
namespace {
using security::Bytes;
constexpr std::size_t kHeaderSize = 27;
constexpr std::size_t kMaximumBlob = 8192;
constexpr std::size_t kMaximumEvents = 32;

void put_u64(Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}
void put_u32(Bytes& out, std::uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}
void put_u16(Bytes& out, std::uint16_t value) {
    out.push_back(static_cast<std::uint8_t>(value >> 8));
    out.push_back(static_cast<std::uint8_t>(value));
}
bool get_unsigned(const Bytes& in, std::size_t& pos, unsigned bytes,
                  std::uint64_t& value) {
    if (pos > in.size() || bytes > in.size() - pos) return false;
    value = 0;
    for (unsigned i = 0; i < bytes; ++i) value = (value << 8) | in[pos++];
    return true;
}
void put_i64(Bytes& out, std::int64_t value) {
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    put_u64(out, bits);
}
bool get_i64(const Bytes& in, std::size_t& pos, std::int64_t& value) {
    std::uint64_t bits = 0;
    if (!get_unsigned(in, pos, 8, bits)) return false;
    std::memcpy(&value, &bits, sizeof(bits));
    return true;
}
bool put_string(Bytes& out, const std::string& value) {
    if (value.empty() || value.size() > 64) return false;
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
    return true;
}
bool get_string(const Bytes& in, std::size_t& pos, std::string& value) {
    if (pos >= in.size()) return false;
    const std::size_t size = in[pos++];
    if (size == 0 || size > 64 || size > in.size() - pos) return false;
    value.assign(reinterpret_cast<const char*>(in.data() + pos), size);
    pos += size;
    return true;
}
bool encode(const NodeRuntimeRecoveryState& state, Bytes& out) {
    if (!put_string(out, state.node_id) || state.pending.size() > kMaximumEvents) return false;
    put_u64(out, state.prior_boot_session);
    out.push_back(state.gap_marker_required ? 1 : 0);
    out.push_back(static_cast<std::uint8_t>(state.pending.size()));
    for (const auto& pending : state.pending) {
        const auto& event = pending.event;
        const auto retained = std::find_if(state.retained.begin(), state.retained.end(),
            [&event](const DomainEvent& value) {
                return value.key.session_id == event.key.session_id &&
                       value.key.sequence == event.key.sequence;
            });
        if (pending.attempt > 255 ||
            !put_string(out, event.location)) return false;
        put_u64(out, event.key.session_id);
        put_u64(out, event.key.sequence);
        out.push_back(static_cast<std::uint8_t>(event.kind));
        put_i64(out, event.monotonic_ms);
        put_i64(out, event.occurred_at);
        put_i64(out, event.received_at);
        put_u32(out, event.uncertainty_s);
        put_u16(out, event.battery_mv);
        out.push_back(event.is_test ? 1 : 0);
        out.push_back(static_cast<std::uint8_t>(event.sensor_type));
        std::uint16_t rssi_bits = 0;
        std::memcpy(&rssi_bits, &event.rssi_dbm, sizeof(rssi_bits));
        put_u16(out, rssi_bits);
        out.push_back(static_cast<std::uint8_t>(pending.attempt));
        out.push_back(pending.periodic_backoff_counted ? 1 : 0);
        out.push_back(retained != state.retained.end() ? 1 : 0);
    }
    return true;
}
bool decode(const Bytes& in, NodeRuntimeRecoveryState& state) {
    std::size_t pos = 0;
    std::uint64_t value = 0;
    if (!get_string(in, pos, state.node_id) ||
        !get_unsigned(in, pos, 8, state.prior_boot_session) ||
        pos + 2 > in.size() || in[pos] > 1 || in[pos + 1] > kMaximumEvents)
        return false;
    state.gap_marker_required = in[pos++] != 0;
    const auto count = in[pos++];
    for (unsigned i = 0; i < count; ++i) {
        PendingTx pending;
        auto& event = pending.event;
        event.key.source_id = state.node_id;
        if (!get_string(in, pos, event.location) ||
            !get_unsigned(in, pos, 8, event.key.session_id) ||
            !get_unsigned(in, pos, 8, event.key.sequence) ||
            pos >= in.size() || in[pos] > static_cast<std::uint8_t>(EventKind::Gap))
            return false;
        event.kind = static_cast<EventKind>(in[pos++]);
        if (!get_i64(in, pos, event.monotonic_ms) ||
            !get_i64(in, pos, event.occurred_at) ||
            !get_i64(in, pos, event.received_at) ||
            !get_unsigned(in, pos, 4, value)) return false;
        event.uncertainty_s = static_cast<std::uint32_t>(value);
        if (!get_unsigned(in, pos, 2, value)) return false;
        event.battery_mv = static_cast<std::uint16_t>(value);
        if (pos + 2 > in.size() || in[pos] > 1 ||
            in[pos + 1] > static_cast<std::uint8_t>(SensorType::System)) return false;
        event.is_test = in[pos++] != 0;
        event.sensor_type = static_cast<SensorType>(in[pos++]);
        if (!get_unsigned(in, pos, 2, value)) return false;
        const auto rssi_bits = static_cast<std::uint16_t>(value);
        std::memcpy(&event.rssi_dbm, &rssi_bits, sizeof(rssi_bits));
        if (pos + 3 > in.size() || in[pos + 1] > 1 || in[pos + 2] > 1)
            return false;
        pending.attempt = in[pos++];
        pending.periodic_backoff_counted = in[pos++] != 0;
        const bool retained = in[pos++] != 0;
        if (retained) state.retained.push_back(event);
        state.pending.push_back(std::move(pending));
    }
    return pos == in.size();
}
bool valid_identity(const std::string& value) {
    return !value.empty() && value.size() <= 64;
}
}  // namespace

NodeRecoveryRepository::NodeRecoveryRepository(
    security::CommissioningCrypto& crypto, security::SecurityBlobStore& store,
    const security::Key32& protected_wrapping_key, std::string home_id,
    std::string hub_id, std::string node_id)
    : crypto_(crypto), store_(store), wrapping_key_(protected_wrapping_key),
      home_id_(std::move(home_id)), hub_id_(std::move(hub_id)),
      node_id_(std::move(node_id)) {}

NodeRecoveryRepository::~NodeRecoveryRepository() {
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
}

bool NodeRecoveryRepository::valid(const NodeRuntimeRecoveryState& state) const {
    if (!valid_identity(home_id_) || !valid_identity(hub_id_) ||
        !valid_identity(node_id_) || state.node_id != node_id_ ||
        state.prior_boot_session == 0 ||
        state.prior_boot_session == std::numeric_limits<std::uint64_t>::max() ||
        state.pending.size() > kMaximumEvents || state.retained.size() > kMaximumEvents ||
        !std::any_of(wrapping_key_.begin(), wrapping_key_.end(),
                     [](std::uint8_t byte) { return byte != 0; })) return false;
    NodeRuntime candidate(node_id_, state.prior_boot_session + 1);
    return candidate.restore_recovery(state, 0);
}

NodeRecoveryLoad NodeRecoveryRepository::load() {
    Bytes blob;
    bool found = false;
    if (!store_.read(blob, found)) return {NodeRecoveryLoadStatus::IoError, 0, std::nullopt};
    if (!found) return {};
    if (blob.size() < kHeaderSize + security::GcmTag{}.size() ||
        blob.size() > kMaximumBlob || blob[0] != 'G' || blob[1] != 'S' ||
        blob[2] != 'N' || blob[3] != 'R' || blob[4] != 1)
        return {NodeRecoveryLoadStatus::Corrupt, 0, std::nullopt};
    std::size_t pos = 5;
    std::uint64_t generation = 0;
    if (!get_unsigned(blob, pos, 8, generation) || generation == 0)
        return {NodeRecoveryLoadStatus::Corrupt, 0, std::nullopt};
    security::Nonce12 nonce{};
    std::copy_n(blob.begin() + pos, nonce.size(), nonce.begin());
    pos += nonce.size();
    std::uint64_t length = 0;
    if (!get_unsigned(blob, pos, 2, length) ||
        blob.size() != kHeaderSize + length + security::GcmTag{}.size())
        return {NodeRecoveryLoadStatus::Corrupt, 0, std::nullopt};
    Bytes aad(blob.begin(), blob.begin() + kHeaderSize);
    if (!put_string(aad, home_id_) || !put_string(aad, hub_id_) ||
        !put_string(aad, node_id_))
        return {NodeRecoveryLoadStatus::Corrupt, 0, std::nullopt};
    Bytes cipher(blob.begin() + kHeaderSize, blob.end() - security::GcmTag{}.size());
    security::GcmTag tag{};
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    Bytes plain;
    if (!crypto_.open_aes256_gcm(wrapping_key_, nonce, aad, cipher, tag, plain))
        return {NodeRecoveryLoadStatus::Corrupt, 0, std::nullopt};
    NodeRuntimeRecoveryState state;
    const bool okay = decode(plain, state) && valid(state);
    crypto_.secure_zero(plain.data(), plain.size());
    if (!okay) return {NodeRecoveryLoadStatus::Corrupt, 0, std::nullopt};
    return {NodeRecoveryLoadStatus::Ready, generation, std::move(state)};
}

bool NodeRecoveryRepository::save(const NodeRuntimeRecoveryState& state) {
    if (!valid(state)) return false;
    const auto current = load();
    if (current.status != NodeRecoveryLoadStatus::Missing &&
        current.status != NodeRecoveryLoadStatus::Ready) return false;
    if (current.state &&
        state.prior_boot_session < current.state->prior_boot_session) return false;
    if (current.generation == std::numeric_limits<std::uint64_t>::max()) return false;
    Bytes plain;
    if (!encode(state, plain) ||
        plain.size() + kHeaderSize + security::GcmTag{}.size() > kMaximumBlob) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    security::Nonce12 nonce{};
    if (!crypto_.random_bytes(nonce.data(), nonce.size())) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    Bytes blob{'G', 'S', 'N', 'R', 1};
    put_u64(blob, current.generation + 1);
    blob.insert(blob.end(), nonce.begin(), nonce.end());
    put_u16(blob, static_cast<std::uint16_t>(plain.size()));
    Bytes aad = blob;
    if (!put_string(aad, home_id_) || !put_string(aad, hub_id_) ||
        !put_string(aad, node_id_)) {
        crypto_.secure_zero(plain.data(), plain.size());
        return false;
    }
    Bytes cipher;
    security::GcmTag tag{};
    const bool sealed = crypto_.seal_aes256_gcm(wrapping_key_, nonce, aad,
                                                 plain, cipher, tag);
    crypto_.secure_zero(plain.data(), plain.size());
    if (!sealed || cipher.size() + kHeaderSize + tag.size() > kMaximumBlob) return false;
    blob.insert(blob.end(), cipher.begin(), cipher.end());
    blob.insert(blob.end(), tag.begin(), tag.end());
    return store_.write(blob);
}

}  // namespace gs::node
