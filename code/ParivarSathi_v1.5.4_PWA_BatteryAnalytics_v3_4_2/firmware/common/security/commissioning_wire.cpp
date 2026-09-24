#include "firmware/common/security/commissioning_wire.hpp"

#include <algorithm>
#include <cstring>
#include <limits>
#include <utility>

namespace gs::security::wire {
namespace {

constexpr std::uint8_t kMagic0 = 0x47;
constexpr std::uint8_t kMagic1 = 0x53;
constexpr std::uint8_t kVersion = 1;
constexpr std::size_t kFragmentPayloadBytes = kMaximumPacketBytes - kFragmentHeaderBytes;

bool valid_kind(std::uint8_t value) {
    return value >= static_cast<std::uint8_t>(Kind::Offer) &&
           value <= static_cast<std::uint8_t>(Kind::RejoinAck);
}

void put_u64(Bytes& out, std::uint64_t value) {
    for (unsigned i = 0; i < 8; ++i) out.push_back(static_cast<std::uint8_t>(value >> (i * 8)));
}

bool put_string(Bytes& out, const std::string& value) {
    if (value.empty() || value.size() > 64) return false;
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
    return true;
}

template <std::size_t N>
void put_array(Bytes& out, const std::array<std::uint8_t, N>& value) {
    out.insert(out.end(), value.begin(), value.end());
}

struct Reader {
    const Bytes& bytes;
    std::size_t offset{0};

    bool octet(std::uint8_t& value) {
        if (offset >= bytes.size()) return false;
        value = bytes[offset++];
        return true;
    }
    bool text(std::string& value) {
        std::uint8_t length = 0;
        if (!octet(length) || length == 0 || length > 64 ||
            length > bytes.size() - offset) return false;
        value.assign(reinterpret_cast<const char*>(bytes.data() + offset), length);
        offset += length;
        return true;
    }
    template <std::size_t N>
    bool array(std::array<std::uint8_t, N>& value) {
        if (N > bytes.size() - offset) return false;
        std::copy_n(bytes.data() + offset, N, value.data());
        offset += N;
        return true;
    }
    bool u64(std::uint64_t& value) {
        if (8 > bytes.size() - offset) return false;
        value = 0;
        for (unsigned i = 0; i < 8; ++i) value |= std::uint64_t{bytes[offset++]} << (i * 8);
        return true;
    }
    bool done() const { return offset == bytes.size(); }
};

bool begin_decode(const Message& message, Kind expected) {
    return message.kind == expected && !message.body.empty() &&
           message.body.size() <= kMaximumMessageBytes;
}

bool finish_encode(Kind kind, Bytes&& body, Message& out) {
    if (body.empty() || body.size() > kMaximumMessageBytes) return false;
    out = {kind, std::move(body)};
    return true;
}

std::uint32_t get_u32(const std::uint8_t* bytes) {
    return std::uint32_t{bytes[0]} | (std::uint32_t{bytes[1]} << 8) |
           (std::uint32_t{bytes[2]} << 16) | (std::uint32_t{bytes[3]} << 24);
}

void put_u32(std::uint8_t* bytes, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) bytes[i] = static_cast<std::uint8_t>(value >> (i * 8));
}

}  // namespace

bool encode(const CommissioningOffer& value, Message& out) {
    if (value.version != 1 || value.device_public_key[0] != 0x04 ||
        value.hub_public_key[0] != 0x04 || value.hub_ephemeral_key[0] != 0x04)
        return false;
    Bytes body{value.version};
    if (!put_string(body, value.device_id) || !put_string(body, value.hub_id) ||
        !put_string(body, value.home_id) || !put_string(body, value.logical_id) ||
        !put_string(body, value.room) || !put_string(body, value.function)) return false;
    put_array(body, value.device_public_key);
    put_array(body, value.hub_public_key);
    put_array(body, value.hub_ephemeral_key);
    put_array(body, value.hub_challenge);
    put_array(body, value.installer_authorization);
    return finish_encode(Kind::Offer, std::move(body), out);
}

bool decode(const Message& message, CommissioningOffer& out) {
    if (!begin_decode(message, Kind::Offer)) return false;
    Reader read{message.body};
    CommissioningOffer value;
    if (!read.octet(value.version) || value.version != 1 ||
        !read.text(value.device_id) || !read.text(value.hub_id) ||
        !read.text(value.home_id) || !read.text(value.logical_id) ||
        !read.text(value.room) || !read.text(value.function) ||
        !read.array(value.device_public_key) || value.device_public_key[0] != 0x04 ||
        !read.array(value.hub_public_key) || value.hub_public_key[0] != 0x04 ||
        !read.array(value.hub_ephemeral_key) || value.hub_ephemeral_key[0] != 0x04 ||
        !read.array(value.hub_challenge) ||
        !read.array(value.installer_authorization) || !read.done()) return false;
    out = std::move(value);
    return true;
}

bool encode(const NodeProof& value, Message& out) {
    if (value.node_ephemeral_key[0] != 0x04) return false;
    Bytes body;
    put_array(body, value.node_ephemeral_key);
    put_array(body, value.node_challenge);
    put_array(body, value.device_signature);
    return finish_encode(Kind::NodeProof, std::move(body), out);
}

bool decode(const Message& message, NodeProof& out) {
    if (!begin_decode(message, Kind::NodeProof)) return false;
    Reader read{message.body};
    NodeProof value;
    if (!read.array(value.node_ephemeral_key) || value.node_ephemeral_key[0] != 0x04 ||
        !read.array(value.node_challenge) || !read.array(value.device_signature) ||
        !read.done()) return false;
    out = value;
    return true;
}

bool encode(const HubProof& value, Message& out) {
    Bytes body;
    put_array(body, value.hub_signature);
    put_array(body, value.confirmation);
    return finish_encode(Kind::HubProof, std::move(body), out);
}

bool decode(const Message& message, HubProof& out) {
    if (!begin_decode(message, Kind::HubProof)) return false;
    Reader read{message.body};
    HubProof value;
    if (!read.array(value.hub_signature) || !read.array(value.confirmation) ||
        !read.done()) return false;
    out = value;
    return true;
}

bool encode(const CommissioningFinal& value, Message& out) {
    Bytes body;
    put_array(body, value.confirmation);
    return finish_encode(Kind::CommissioningFinal, std::move(body), out);
}

bool decode(const Message& message, CommissioningFinal& out) {
    if (!begin_decode(message, Kind::CommissioningFinal)) return false;
    Reader read{message.body};
    CommissioningFinal value;
    if (!read.array(value.confirmation) || !read.done()) return false;
    out = value;
    return true;
}

bool encode(const CommissioningAck& value, Message& out) {
    Bytes body;
    put_array(body, value.confirmation);
    return finish_encode(Kind::CommissioningAck, std::move(body), out);
}

bool decode(const Message& message, CommissioningAck& out) {
    if (!begin_decode(message, Kind::CommissioningAck)) return false;
    Reader read{message.body};
    CommissioningAck value;
    if (!read.array(value.confirmation) || !read.done()) return false;
    out = value;
    return true;
}

bool encode(const RejoinHello& value, Message& out) {
    if (value.version != 1 || value.session == 0) return false;
    Bytes body{value.version};
    if (!put_string(body, value.device_id) || !put_string(body, value.hub_id) ||
        !put_string(body, value.home_id) || !put_string(body, value.logical_id))
        return false;
    put_u64(body, value.session);
    put_array(body, value.node_challenge);
    put_array(body, value.authentication);
    return finish_encode(Kind::RejoinHello, std::move(body), out);
}

bool decode(const Message& message, RejoinHello& out) {
    if (!begin_decode(message, Kind::RejoinHello)) return false;
    Reader read{message.body};
    RejoinHello value;
    if (!read.octet(value.version) || value.version != 1 ||
        !read.text(value.device_id) || !read.text(value.hub_id) ||
        !read.text(value.home_id) || !read.text(value.logical_id) ||
        !read.u64(value.session) || value.session == 0 ||
        !read.array(value.node_challenge) || !read.array(value.authentication) ||
        !read.done()) return false;
    out = std::move(value);
    return true;
}

bool encode(const RejoinChallenge& value, Message& out) {
    Bytes body;
    put_array(body, value.hub_challenge);
    put_array(body, value.authentication);
    return finish_encode(Kind::RejoinChallenge, std::move(body), out);
}

bool decode(const Message& message, RejoinChallenge& out) {
    if (!begin_decode(message, Kind::RejoinChallenge)) return false;
    Reader read{message.body};
    RejoinChallenge value;
    if (!read.array(value.hub_challenge) || !read.array(value.authentication) ||
        !read.done()) return false;
    out = value;
    return true;
}

bool encode(const RejoinFinal& value, Message& out) {
    Bytes body;
    put_array(body, value.confirmation);
    return finish_encode(Kind::RejoinFinal, std::move(body), out);
}

bool decode(const Message& message, RejoinFinal& out) {
    if (!begin_decode(message, Kind::RejoinFinal)) return false;
    Reader read{message.body};
    RejoinFinal value;
    if (!read.array(value.confirmation) || !read.done()) return false;
    out = value;
    return true;
}

bool encode(const RejoinAck& value, Message& out) {
    Bytes body;
    put_array(body, value.confirmation);
    return finish_encode(Kind::RejoinAck, std::move(body), out);
}

bool decode(const Message& message, RejoinAck& out) {
    if (!begin_decode(message, Kind::RejoinAck)) return false;
    Reader read{message.body};
    RejoinAck value;
    if (!read.array(value.confirmation) || !read.done()) return false;
    out = value;
    return true;
}

bool fragment(const Message& message, std::uint32_t transaction_id,
              std::vector<Packet>& out) {
    if (!valid_kind(static_cast<std::uint8_t>(message.kind)) || transaction_id == 0 ||
        message.body.empty() || message.body.size() > kMaximumMessageBytes)
        return false;
    const auto count = (message.body.size() + kFragmentPayloadBytes - 1) /
                       kFragmentPayloadBytes;
    if (count == 0 || count > kMaximumFragments) return false;
    std::vector<Packet> packets;
    for (std::size_t index = 0; index < count; ++index) {
        Packet packet;
        const auto offset = index * kFragmentPayloadBytes;
        const auto part = std::min(kFragmentPayloadBytes, message.body.size() - offset);
        packet.size = kFragmentHeaderBytes + part;
        packet.bytes[0] = kMagic0;
        packet.bytes[1] = kMagic1;
        packet.bytes[2] = kVersion;
        packet.bytes[3] = static_cast<std::uint8_t>(message.kind);
        put_u32(packet.bytes.data() + 4, transaction_id);
        packet.bytes[8] = static_cast<std::uint8_t>(index);
        packet.bytes[9] = static_cast<std::uint8_t>(count);
        packet.bytes[10] = static_cast<std::uint8_t>(message.body.size());
        packet.bytes[11] = static_cast<std::uint8_t>(message.body.size() >> 8);
        std::copy_n(message.body.data() + offset, part,
                    packet.bytes.data() + kFragmentHeaderBytes);
        packets.push_back(packet);
    }
    out = std::move(packets);
    return true;
}

Assembler::Assembler(std::uint64_t timeout_ms) : timeout_ms_(timeout_ms) {}

void Assembler::reset() {
    deadline_ms_ = 0;
    transaction_id_ = 0;
    total_length_ = 0;
    kind_ = {};
    expected_fragments_ = 0;
    next_fragment_ = 0;
    received_.clear();
}

std::optional<Message> Assembler::push(const std::uint8_t* packet,
                                       std::size_t length, std::uint64_t now_ms) {
    if (packet == nullptr || length <= kFragmentHeaderBytes ||
        length > kMaximumPacketBytes || packet[0] != kMagic0 ||
        packet[1] != kMagic1 || packet[2] != kVersion ||
        !valid_kind(packet[3]) || timeout_ms_ == 0 ||
        now_ms > std::numeric_limits<std::uint64_t>::max() - timeout_ms_) {
        reset();
        return std::nullopt;
    }
    const auto transaction = get_u32(packet + 4);
    const auto index = packet[8];
    const auto count = packet[9];
    const auto total = static_cast<std::uint16_t>(packet[10] | (packet[11] << 8));
    const auto expected_count = (total + kFragmentPayloadBytes - 1) /
                                kFragmentPayloadBytes;
    const auto offset = static_cast<std::size_t>(index) * kFragmentPayloadBytes;
    const auto part = length - kFragmentHeaderBytes;
    if (transaction == 0 || total == 0 || total > kMaximumMessageBytes ||
        count == 0 || count > kMaximumFragments || count != expected_count ||
        index >= count || offset >= total ||
        part != std::min(kFragmentPayloadBytes, total - offset)) {
        reset();
        return std::nullopt;
    }
    if (next_fragment_ != 0 && now_ms > deadline_ms_) reset();
    if (index == 0 && next_fragment_ == 0) {
        transaction_id_ = transaction;
        kind_ = static_cast<Kind>(packet[3]);
        total_length_ = total;
        expected_fragments_ = count;
        deadline_ms_ = now_ms + timeout_ms_;
        received_.reserve(total);
    }
    if (expected_fragments_ == 0 || transaction != transaction_id_ ||
        packet[3] != static_cast<std::uint8_t>(kind_) ||
        total != total_length_ || count != expected_fragments_ ||
        index != next_fragment_) {
        reset();
        return std::nullopt;
    }
    received_.insert(received_.end(), packet + kFragmentHeaderBytes,
                     packet + length);
    ++next_fragment_;
    if (next_fragment_ != expected_fragments_) return std::nullopt;
    Message completed{kind_, std::move(received_)};
    reset();
    return completed;
}

}  // namespace gs::security::wire
