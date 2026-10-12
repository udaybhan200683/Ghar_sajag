#include "firmware/common/security/runtime_frame_security.hpp"

#include <algorithm>
#include <limits>
#include <utility>

namespace gs::security {
namespace {
constexpr std::size_t kHeaderBytes = 12;
constexpr std::uint8_t kMagic0 = 0x47;
constexpr std::uint8_t kMagic1 = 0x53;
constexpr std::uint8_t kVersion = 2;

void append_u64(Bytes& bytes, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        bytes.push_back(static_cast<std::uint8_t>(value >> shift));
}

std::uint64_t read_u64(const std::uint8_t* bytes) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < 8; ++i) value = (value << 8) | bytes[i];
    return value;
}

void append_string(Bytes& bytes, const std::string& value) {
    bytes.push_back(static_cast<std::uint8_t>(value.size()));
    bytes.insert(bytes.end(), value.begin(), value.end());
}

Nonce12 nonce_for(std::uint64_t counter) {
    Nonce12 nonce{};
    for (int i = 0; i < 8; ++i)
        nonce[4 + i] = static_cast<std::uint8_t>(counter >> (56 - 8 * i));
    return nonce;
}

bool replayed(std::uint64_t counter, std::uint64_t highest, std::uint64_t window) {
    if (counter == 0 || counter > highest) return counter == 0;
    const auto age = highest - counter;
    return age >= 64 || (window & (std::uint64_t{1} << age)) != 0;
}

void mark_received(std::uint64_t counter, std::uint64_t& highest, std::uint64_t& window) {
    if (counter > highest) {
        const auto distance = counter - highest;
        window = distance >= 64 ? 1 : (window << distance) | 1;
        highest = counter;
    } else {
        window |= std::uint64_t{1} << (highest - counter);
    }
}
}  // namespace

RuntimeFrameSecurity::RuntimeFrameSecurity(CommissioningCrypto& crypto,
                                           const CommissioningBinding& binding)
    : crypto_(crypto), binding_(binding) {}

RuntimeFrameSecurity::~RuntimeFrameSecurity() {
    crypto_.secure_zero(binding_.installation_key.data(), binding_.installation_key.size());
    crypto_.secure_zero(uplink_.key.data(), uplink_.key.size());
    crypto_.secure_zero(downlink_.key.data(), downlink_.key.size());
}

RuntimeFrameSecurity::DirectionState& RuntimeFrameSecurity::state(RuntimeDirection direction) {
    return direction == RuntimeDirection::Uplink ? uplink_ : downlink_;
}

bool RuntimeFrameSecurity::start(std::uint64_t session, const Key32& authenticated_salt) {
    if (session == 0 || session <= session_ ||
        std::all_of(authenticated_salt.begin(), authenticated_salt.end(),
                    [](std::uint8_t value) { return value == 0; }) ||
        binding_.device_id.empty() || binding_.device_id.size() > 64 ||
        binding_.hub_id.empty() || binding_.hub_id.size() > 64 ||
        binding_.home_id.empty() || binding_.home_id.size() > 64 ||
        binding_.logical_id.empty() || binding_.logical_id.size() > 64) return false;
    Bytes salt(authenticated_salt.begin(), authenticated_salt.end());
    append_u64(salt, session);
    Bytes context{'G', 'S', '-', 'P', '2', '-', 'R', 'U', 'N', '-', 'v', '1', 0};
    append_string(context, binding_.device_id);
    append_string(context, binding_.hub_id);
    append_string(context, binding_.home_id);
    append_string(context, binding_.logical_id);
    Key32 uplink_key{}, downlink_key{};
    context.push_back(static_cast<std::uint8_t>(RuntimeDirection::Uplink));
    const bool uplink_ok = crypto_.hkdf_sha256(binding_.installation_key,
                                               salt, context, uplink_key);
    context.back() = static_cast<std::uint8_t>(RuntimeDirection::Downlink);
    const bool downlink_ok = uplink_ok && crypto_.hkdf_sha256(binding_.installation_key,
                                                               salt, context, downlink_key);
    if (!uplink_ok || !downlink_ok) {
        crypto_.secure_zero(uplink_key.data(), uplink_key.size());
        crypto_.secure_zero(downlink_key.data(), downlink_key.size());
        return false;
    }
    crypto_.secure_zero(uplink_.key.data(), uplink_.key.size());
    crypto_.secure_zero(downlink_.key.data(), downlink_.key.size());
    uplink_ = DirectionState{};
    downlink_ = DirectionState{};
    uplink_.key = uplink_key;
    downlink_.key = downlink_key;
    crypto_.secure_zero(uplink_key.data(), uplink_key.size());
    crypto_.secure_zero(downlink_key.data(), downlink_key.size());
    session_ = session;
    return true;
}

Bytes RuntimeFrameSecurity::associated_data(const std::uint8_t* header) const {
    Bytes out(header, header + kHeaderBytes);
    append_u64(out, session_);
    append_string(out, binding_.device_id);
    append_string(out, binding_.hub_id);
    append_string(out, binding_.home_id);
    append_string(out, binding_.logical_id);
    return out;
}

bool RuntimeFrameSecurity::seal(RuntimeDirection direction,
                                const transport::EncodedFrame& plain, SecureFrame& output) {
    if (session_ == 0 || (direction != RuntimeDirection::Uplink &&
                          direction != RuntimeDirection::Downlink) ||
        plain.size == 0 || plain.size > transport::kMaxFrameBytes ||
        plain.size + kSecureFrameOverhead > output.bytes.size()) return false;
    auto& direction_state = state(direction);
    if (direction_state.next_send == std::numeric_limits<std::uint64_t>::max()) return false;
    std::array<std::uint8_t, kHeaderBytes> header{};
    header[0] = kMagic0;
    header[1] = kMagic1;
    header[2] = kVersion;
    header[3] = static_cast<std::uint8_t>(direction);
    const auto counter = direction_state.next_send;
    for (int i = 0; i < 8; ++i)
        header[4 + i] = static_cast<std::uint8_t>(counter >> (56 - 8 * i));
    const Bytes body(plain.bytes.begin(), plain.bytes.begin() + plain.size);
    Bytes cipher;
    GcmTag tag{};
    if (!crypto_.seal_aes256_gcm(direction_state.key, nonce_for(counter),
                                  associated_data(header.data()), body, cipher, tag) ||
        cipher.size() != body.size()) return false;
    std::copy(header.begin(), header.end(), output.bytes.begin());
    std::copy(cipher.begin(), cipher.end(), output.bytes.begin() + kHeaderBytes);
    std::copy(tag.begin(), tag.end(), output.bytes.begin() + kHeaderBytes + cipher.size());
    output.size = kHeaderBytes + cipher.size() + tag.size();
    ++direction_state.next_send;
    return true;
}

bool RuntimeFrameSecurity::open(RuntimeDirection expected_direction,
                                const SecureFrame& input,
                                transport::EncodedFrame& plain) {
    plain.size = 0;
    plain.bytes.fill(0);
    if (session_ == 0 || (expected_direction != RuntimeDirection::Uplink &&
                          expected_direction != RuntimeDirection::Downlink) ||
        input.size <= kSecureFrameOverhead || input.size > input.bytes.size() ||
        input.bytes[0] != kMagic0 || input.bytes[1] != kMagic1 ||
        input.bytes[2] != kVersion ||
        input.bytes[3] != static_cast<std::uint8_t>(expected_direction)) {
        ++rejected_frames_;
        return false;
    }
    const auto counter = read_u64(input.bytes.data() + 4);
    auto& direction_state = state(expected_direction);
    if (replayed(counter, direction_state.highest_received,
                 direction_state.received_window)) {
        ++rejected_frames_;
        return false;
    }
    const auto body_size = input.size - kSecureFrameOverhead;
    if (body_size > plain.bytes.size()) {
        ++rejected_frames_;
        return false;
    }
    const Bytes cipher(input.bytes.begin() + kHeaderBytes,
                       input.bytes.begin() + kHeaderBytes + body_size);
    GcmTag tag{};
    std::copy_n(input.bytes.begin() + kHeaderBytes + body_size,
                tag.size(), tag.begin());
    Bytes opened;
    if (!crypto_.open_aes256_gcm(direction_state.key, nonce_for(counter),
                                  associated_data(input.bytes.data()), cipher, tag, opened) ||
        opened.size() != body_size) {
        ++rejected_frames_;
        return false;
    }
    std::copy(opened.begin(), opened.end(), plain.bytes.begin());
    plain.size = opened.size();
    mark_received(counter, direction_state.highest_received,
                  direction_state.received_window);
    return true;
}

}  // namespace gs::security
