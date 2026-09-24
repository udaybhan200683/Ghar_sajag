#pragma once

#include "firmware/common/security/rejoin_protocol.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>

namespace gs::security::wire {

// Commissioning is larger than one ESP-NOW v1 packet. Fragments are bounded;
// the completed protocol message is authenticated by the existing handshake.
// The fragment header itself grants no authorization.
constexpr std::size_t kMaximumPacketBytes = 250;
constexpr std::size_t kFragmentHeaderBytes = 12;
constexpr std::size_t kMaximumMessageBytes = 768;
constexpr std::size_t kMaximumFragments = 4;

enum class Kind : std::uint8_t {
    Offer = 1,
    NodeProof = 2,
    HubProof = 3,
    CommissioningFinal = 4,
    CommissioningAck = 5,
    RejoinHello = 6,
    RejoinChallenge = 7,
    RejoinFinal = 8,
    RejoinAck = 9,
};

struct Message {
    Kind kind{};
    Bytes body;
};

struct Packet {
    std::array<std::uint8_t, kMaximumPacketBytes> bytes{};
    std::size_t size{0};
};

bool encode(const CommissioningOffer& value, Message& out);
bool encode(const NodeProof& value, Message& out);
bool encode(const HubProof& value, Message& out);
bool encode(const CommissioningFinal& value, Message& out);
bool encode(const CommissioningAck& value, Message& out);
bool encode(const RejoinHello& value, Message& out);
bool encode(const RejoinChallenge& value, Message& out);
bool encode(const RejoinFinal& value, Message& out);
bool encode(const RejoinAck& value, Message& out);

bool decode(const Message& message, CommissioningOffer& out);
bool decode(const Message& message, NodeProof& out);
bool decode(const Message& message, HubProof& out);
bool decode(const Message& message, CommissioningFinal& out);
bool decode(const Message& message, CommissioningAck& out);
bool decode(const Message& message, RejoinHello& out);
bool decode(const Message& message, RejoinChallenge& out);
bool decode(const Message& message, RejoinFinal& out);
bool decode(const Message& message, RejoinAck& out);

// transaction_id is fresh for each complete protocol message. A caller must
// retry the whole message if a fragment is lost; the receiver never combines
// fragments from different transactions or source MAC addresses.
bool fragment(const Message& message, std::uint32_t transaction_id,
              std::vector<Packet>& out);

class Assembler {
public:
    explicit Assembler(std::uint64_t timeout_ms = 3000);
    void reset();
    std::optional<Message> push(const std::uint8_t* packet, std::size_t length,
                                std::uint64_t now_ms);

private:
    std::uint64_t timeout_ms_;
    std::uint64_t deadline_ms_{0};
    std::uint32_t transaction_id_{0};
    std::uint16_t total_length_{0};
    Kind kind_{};
    std::uint8_t expected_fragments_{0};
    std::uint8_t next_fragment_{0};
    Bytes received_;
};

}  // namespace gs::security::wire
