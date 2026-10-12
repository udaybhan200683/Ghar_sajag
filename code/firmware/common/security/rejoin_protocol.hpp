#pragma once

#include "firmware/common/security/commissioning_protocol.hpp"

#include <cstdint>
#include <optional>

namespace gs::security {

inline constexpr std::uint32_t kHealthAckCapability = 1U;

struct RejoinHello {
    std::uint8_t version{1};
    std::uint32_t offered_capabilities{0};
    std::string device_id;
    std::string hub_id;
    std::string home_id;
    std::string logical_id;
    std::uint64_t session{0};
    Challenge16 node_challenge{};
    Key32 authentication{};
};

struct RejoinChallenge {
    std::uint8_t version{1};
    std::uint32_t selected_capabilities{0};
    Challenge16 hub_challenge{};
    Key32 authentication{};
};

struct RejoinFinal { Key32 confirmation{}; };
struct RejoinAck { Key32 confirmation{}; };

// A fresh monotonic session from the Node's committed boot counter is required.
// The Hub must persist the accepted session before admitting application data.
// This protocol authenticates the rejoin exchange but does not itself persist
// either side's association or settle an interrupted final ACK.
class HubRejoin {
public:
    HubRejoin(CommissioningCrypto& crypto, const CommissioningBinding& binding,
              std::uint64_t last_accepted_session);
    ~HubRejoin();
    HubRejoin(const HubRejoin&) = delete;
    HubRejoin& operator=(const HubRejoin&) = delete;
    std::optional<RejoinChallenge> accept(const RejoinHello& hello);
    std::optional<RejoinAck> confirm(const RejoinFinal& final);
    const std::optional<Key32>& session_salt() const { return session_salt_; }
    std::uint64_t authenticated_session() const { return accepted_session_; }
    std::uint32_t negotiated_capabilities() const { return challenge_.selected_capabilities; }

private:
    CommissioningCrypto& crypto_;
    const CommissioningBinding& binding_;
    std::uint64_t last_session_{0};
    std::uint64_t accepted_session_{0};
    RejoinHello hello_{};
    RejoinChallenge challenge_{};
    std::optional<Key32> session_salt_;
    enum class State { Idle, Challenged, Confirmed } state_{State::Idle};
};

class NodeRejoin {
public:
    NodeRejoin(CommissioningCrypto& crypto, const CommissioningBinding& binding,
               std::uint64_t next_session, std::uint8_t version = 1,
               std::uint32_t offered_capabilities = kHealthAckCapability);
    ~NodeRejoin();
    NodeRejoin(const NodeRejoin&) = delete;
    NodeRejoin& operator=(const NodeRejoin&) = delete;
    std::optional<RejoinHello> begin();
    std::optional<RejoinFinal> accept(const RejoinChallenge& challenge);
    bool commit(const RejoinAck& ack);
    const std::optional<Key32>& session_salt() const { return session_salt_; }
    std::uint32_t negotiated_capabilities() const { return challenge_.selected_capabilities; }

private:
    CommissioningCrypto& crypto_;
    const CommissioningBinding& binding_;
    std::uint64_t next_session_{0};
    std::uint8_t version_{1};
    std::uint32_t offered_capabilities_{0};
    RejoinHello hello_{};
    RejoinChallenge challenge_{};
    std::optional<Key32> session_salt_;
    enum class State { Idle, HelloSent, FinalSent, Committed } state_{State::Idle};
};

}  // namespace gs::security
