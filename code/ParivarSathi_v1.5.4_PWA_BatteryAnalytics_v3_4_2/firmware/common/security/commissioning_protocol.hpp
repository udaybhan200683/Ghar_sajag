#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"

#include <array>
#include <cstdint>
#include <optional>
#include <string>

namespace gs::security {

using Challenge16 = std::array<std::uint8_t, 16>;

struct CommissioningOffer {
    std::uint8_t version{1};
    std::string device_id;
    std::string hub_id;
    std::string home_id;
    std::string logical_id;
    std::string room;
    std::string function;
    P256PublicKey device_public_key{};
    P256PublicKey hub_public_key{};
    P256PublicKey hub_ephemeral_key{};
    Challenge16 hub_challenge{};
    Key32 installer_authorization{};
};

struct NodeProof {
    P256PublicKey node_ephemeral_key{};
    Challenge16 node_challenge{};
    P256Signature device_signature{};
};

struct HubProof {
    P256Signature hub_signature{};
    Key32 confirmation{};
};

struct CommissioningFinal { Key32 confirmation{}; };
struct CommissioningAck { Key32 confirmation{}; };

struct CommissioningBinding {
    std::string device_id;
    std::string hub_id;
    std::string home_id;
    std::string logical_id;
    std::string room;
    std::string function;
    P256PublicKey device_public_key{};
    P256PublicKey hub_public_key{};
    Key32 installation_key{};
};

// The installer must have scanned an exact public identity plus a distinct
// one-time authorization code. The latter grants enrollment intent but cannot
// produce the Node's private-key signature. No radio discovery auto-enrolls.
class HubCommissioning {
public:
    HubCommissioning(CommissioningCrypto& crypto, std::string hub_key_reference,
                     std::string hub_id, std::string home_id,
                     std::string expected_device_id, P256PublicKey expected_device_key,
                     Key32 installer_code, std::string logical_id,
                     std::string room, std::string function);
    std::optional<CommissioningOffer> open(std::uint64_t now_ms, std::uint64_t duration_ms);
    std::optional<HubProof> accept(const NodeProof& proof, std::uint64_t now_ms);
    std::optional<CommissioningAck> confirm(const CommissioningFinal& final,
                                             std::uint64_t now_ms);
    const std::optional<CommissioningBinding>& binding() const { return binding_; }

private:
    CommissioningCrypto& crypto_;
    std::string hub_key_reference_;
    std::string hub_id_;
    std::string home_id_;
    std::string expected_device_id_;
    std::string logical_id_;
    std::string room_;
    std::string function_;
    P256PublicKey expected_device_key_{};
    Key32 installer_code_{};
    EphemeralP256 ephemeral_{};
    CommissioningOffer offer_{};
    NodeProof node_proof_{};
    HubProof hub_proof_{};
    Key32 installation_key_{};
    std::uint64_t deadline_ms_{0};
    enum class State { Idle, Offered, ProofSent, Committed } state_{State::Idle};
    std::optional<CommissioningBinding> binding_;
};

class NodeCommissioning {
public:
    NodeCommissioning(CommissioningCrypto& crypto, std::string device_key_reference,
                      std::string device_id, Key32 installer_code);
    bool enable_window(std::uint64_t now_ms, std::uint64_t duration_ms);
    std::optional<NodeProof> respond(const CommissioningOffer& offer, std::uint64_t now_ms);
    std::optional<CommissioningFinal> finish(const HubProof& proof, std::uint64_t now_ms);
    bool commit(const CommissioningAck& ack, std::uint64_t now_ms);
    const std::optional<CommissioningBinding>& binding() const { return binding_; }

private:
    CommissioningCrypto& crypto_;
    std::string device_key_reference_;
    std::string device_id_;
    Key32 installer_code_{};
    EphemeralP256 ephemeral_{};
    CommissioningOffer offer_{};
    NodeProof proof_{};
    HubProof hub_proof_{};
    Key32 installation_key_{};
    std::uint64_t deadline_ms_{0};
    enum class State { Idle, Window, ProofSent, FinalSent, Committed } state_{State::Idle};
    std::optional<CommissioningBinding> binding_;
};

}  // namespace gs::security
