#include "firmware/common/security/commissioning_protocol.hpp"

#include <algorithm>
#include <limits>
#include <utility>

namespace gs::security {
namespace {
constexpr std::uint64_t kMaximumWindowMs = 10 * 60 * 1000;

void append(Bytes& out, const std::uint8_t* data, std::size_t size) {
    out.insert(out.end(), data, data + size);
}

void append_string(Bytes& out, const std::string& value) {
    out.push_back(static_cast<std::uint8_t>(value.size()));
    append(out, reinterpret_cast<const std::uint8_t*>(value.data()), value.size());
}

void domain(Bytes& out, const char* label) {
    while (*label != '\0') out.push_back(static_cast<std::uint8_t>(*label++));
    out.push_back(0);
}

bool valid_id(const std::string& value) { return !value.empty() && value.size() <= 64; }

bool valid_window(std::uint64_t now, std::uint64_t duration) {
    return duration > 0 && duration <= kMaximumWindowMs &&
           now <= std::numeric_limits<std::uint64_t>::max() - duration;
}

Bytes offer_bytes(const CommissioningOffer& offer) {
    Bytes out;
    domain(out, "GS-P2-COM-OFFER-v1");
    out.push_back(offer.version);
    append_string(out, offer.device_id);
    append_string(out, offer.hub_id);
    append_string(out, offer.home_id);
    append_string(out, offer.logical_id);
    append_string(out, offer.room);
    append_string(out, offer.function);
    append(out, offer.device_public_key.data(), offer.device_public_key.size());
    append(out, offer.hub_public_key.data(), offer.hub_public_key.size());
    append(out, offer.hub_ephemeral_key.data(), offer.hub_ephemeral_key.size());
    append(out, offer.hub_challenge.data(), offer.hub_challenge.size());
    return out;
}

Bytes transcript_bytes(const CommissioningOffer& offer, const NodeProof& proof) {
    Bytes out = offer_bytes(offer);
    append(out, offer.installer_authorization.data(), offer.installer_authorization.size());
    append(out, proof.node_ephemeral_key.data(), proof.node_ephemeral_key.size());
    append(out, proof.node_challenge.data(), proof.node_challenge.size());
    return out;
}

Bytes hub_signature_bytes(const Bytes& transcript, const P256Signature& node_signature) {
    Bytes out;
    domain(out, "GS-P2-COM-HUB-PROOF-v1");
    append(out, transcript.data(), transcript.size());
    append(out, node_signature.data(), node_signature.size());
    return out;
}

Bytes confirmation_bytes(const Bytes& transcript, const NodeProof& node,
                         const HubProof& hub, const char* label) {
    Bytes out;
    domain(out, label);
    append(out, transcript.data(), transcript.size());
    append(out, node.device_signature.data(), node.device_signature.size());
    append(out, hub.hub_signature.data(), hub.hub_signature.size());
    return out;
}

bool derive_installation_key(CommissioningCrypto& crypto, const EphemeralP256& local,
                             const P256PublicKey& remote,
                             const CommissioningOffer& offer, const NodeProof& proof,
                             Key32& key) {
    Key32 shared{};
    if (!crypto.derive_shared(local, remote, shared)) return false;
    Bytes salt;
    append(salt, offer.hub_challenge.data(), offer.hub_challenge.size());
    append(salt, proof.node_challenge.data(), proof.node_challenge.size());
    Bytes context;
    domain(context, "GS-P2-INSTALL-KEY-v1");
    const auto transcript = transcript_bytes(offer, proof);
    append(context, transcript.data(), transcript.size());
    const bool okay = crypto.hkdf_sha256(shared, salt, context, key);
    std::fill(shared.begin(), shared.end(), 0);
    return okay;
}

bool matches(CommissioningCrypto& crypto, const Key32& left, const Key32& right) {
    return crypto.constant_time_equal(left.data(), right.data(), left.size());
}
}  // namespace

HubCommissioning::HubCommissioning(CommissioningCrypto& crypto, std::string hub_key_reference,
                                   std::string hub_id, std::string home_id,
                                   std::string expected_device_id,
                                   P256PublicKey expected_device_key, Key32 installer_code,
                                   std::string logical_id, std::string room,
                                   std::string function)
    : crypto_(crypto), hub_key_reference_(std::move(hub_key_reference)),
      hub_id_(std::move(hub_id)), home_id_(std::move(home_id)),
      expected_device_id_(std::move(expected_device_id)),
      logical_id_(std::move(logical_id)), room_(std::move(room)),
      function_(std::move(function)),
      expected_device_key_(expected_device_key), installer_code_(installer_code) {}

std::optional<CommissioningOffer> HubCommissioning::open(std::uint64_t now,
                                                          std::uint64_t duration) {
    if (state_ != State::Idle || !valid_window(now, duration) ||
        !valid_id(hub_id_) || !valid_id(home_id_) || !valid_id(expected_device_id_) ||
        !valid_id(logical_id_) || !valid_id(room_) || !valid_id(function_) ||
        !crypto_.identity_public_key(hub_key_reference_, offer_.hub_public_key) ||
        !crypto_.generate_ephemeral(ephemeral_) ||
        !crypto_.random_bytes(offer_.hub_challenge.data(), offer_.hub_challenge.size()))
        return std::nullopt;
    offer_.device_id = expected_device_id_;
    offer_.hub_id = hub_id_;
    offer_.home_id = home_id_;
    offer_.logical_id = logical_id_;
    offer_.room = room_;
    offer_.function = function_;
    offer_.device_public_key = expected_device_key_;
    offer_.hub_ephemeral_key = ephemeral_.public_key;
    if (!crypto_.hmac_sha256(installer_code_, offer_bytes(offer_),
                             offer_.installer_authorization)) return std::nullopt;
    deadline_ms_ = now + duration;
    state_ = State::Offered;
    return offer_;
}

std::optional<HubProof> HubCommissioning::accept(const NodeProof& proof, std::uint64_t now) {
    if (state_ != State::Offered || now > deadline_ms_) return std::nullopt;
    const auto transcript = transcript_bytes(offer_, proof);
    if (!crypto_.verify_identity(expected_device_key_, transcript, proof.device_signature) ||
        !derive_installation_key(crypto_, ephemeral_, proof.node_ephemeral_key,
                                 offer_, proof, installation_key_)) return std::nullopt;
    node_proof_ = proof;
    if (!crypto_.sign_identity(hub_key_reference_,
                               hub_signature_bytes(transcript, proof.device_signature),
                               hub_proof_.hub_signature) ||
        !crypto_.hmac_sha256(installation_key_,
                             confirmation_bytes(transcript, proof, hub_proof_,
                                                "GS-P2-COM-HUB-CONFIRM-v1"),
                             hub_proof_.confirmation)) return std::nullopt;
    state_ = State::ProofSent;
    return hub_proof_;
}

std::optional<CommissioningAck> HubCommissioning::confirm(const CommissioningFinal& final,
                                                            std::uint64_t now) {
    if ((state_ != State::ProofSent && state_ != State::Committed) || now > deadline_ms_)
        return std::nullopt;
    const auto transcript = transcript_bytes(offer_, node_proof_);
    Key32 expected{};
    if (!crypto_.hmac_sha256(installation_key_,
                             confirmation_bytes(transcript, node_proof_, hub_proof_,
                                                "GS-P2-COM-NODE-FINAL-v1"), expected) ||
        !matches(crypto_, expected, final.confirmation)) return std::nullopt;
    CommissioningAck ack;
    if (!crypto_.hmac_sha256(installation_key_,
                             confirmation_bytes(transcript, node_proof_, hub_proof_,
                                                "GS-P2-COM-HUB-ACK-v1"), ack.confirmation))
        return std::nullopt;
    binding_ = CommissioningBinding{expected_device_id_, hub_id_, home_id_,
                                    logical_id_, room_, function_,
                                    expected_device_key_, offer_.hub_public_key,
                                    installation_key_};
    std::fill(installer_code_.begin(), installer_code_.end(), 0);
    state_ = State::Committed;
    return ack;
}

NodeCommissioning::NodeCommissioning(CommissioningCrypto& crypto,
                                     std::string device_key_reference,
                                     std::string device_id, Key32 installer_code)
    : crypto_(crypto), device_key_reference_(std::move(device_key_reference)),
      device_id_(std::move(device_id)), installer_code_(installer_code) {}

bool NodeCommissioning::enable_window(std::uint64_t now, std::uint64_t duration) {
    if (state_ != State::Idle || !valid_window(now, duration) || !valid_id(device_id_))
        return false;
    deadline_ms_ = now + duration;
    state_ = State::Window;
    return true;
}

std::optional<NodeProof> NodeCommissioning::respond(const CommissioningOffer& offer,
                                                     std::uint64_t now) {
    if (state_ != State::Window || now > deadline_ms_ || offer.version != 1 ||
        offer.device_id != device_id_ || !valid_id(offer.hub_id) || !valid_id(offer.home_id) ||
        !valid_id(offer.logical_id) || !valid_id(offer.room) || !valid_id(offer.function))
        return std::nullopt;
    P256PublicKey own_public{};
    if (!crypto_.identity_public_key(device_key_reference_, own_public) ||
        !crypto_.constant_time_equal(own_public.data(), offer.device_public_key.data(),
                                     own_public.size())) return std::nullopt;
    Key32 expected{};
    if (!crypto_.hmac_sha256(installer_code_, offer_bytes(offer), expected) ||
        !matches(crypto_, expected, offer.installer_authorization) ||
        !crypto_.generate_ephemeral(ephemeral_) ||
        !crypto_.random_bytes(proof_.node_challenge.data(), proof_.node_challenge.size()))
        return std::nullopt;
    offer_ = offer;
    proof_.node_ephemeral_key = ephemeral_.public_key;
    if (!crypto_.sign_identity(device_key_reference_, transcript_bytes(offer_, proof_),
                               proof_.device_signature)) return std::nullopt;
    state_ = State::ProofSent;
    return proof_;
}

std::optional<CommissioningFinal> NodeCommissioning::finish(const HubProof& proof,
                                                             std::uint64_t now) {
    if (state_ != State::ProofSent || now > deadline_ms_) return std::nullopt;
    const auto transcript = transcript_bytes(offer_, proof_);
    if (!crypto_.verify_identity(offer_.hub_public_key,
                                 hub_signature_bytes(transcript, proof_.device_signature),
                                 proof.hub_signature) ||
        !derive_installation_key(crypto_, ephemeral_, offer_.hub_ephemeral_key,
                                 offer_, proof_, installation_key_)) return std::nullopt;
    Key32 expected{};
    if (!crypto_.hmac_sha256(installation_key_,
                             confirmation_bytes(transcript, proof_, proof,
                                                "GS-P2-COM-HUB-CONFIRM-v1"), expected) ||
        !matches(crypto_, expected, proof.confirmation)) return std::nullopt;
    hub_proof_ = proof;
    CommissioningFinal final;
    if (!crypto_.hmac_sha256(installation_key_,
                             confirmation_bytes(transcript, proof_, proof,
                                                "GS-P2-COM-NODE-FINAL-v1"), final.confirmation))
        return std::nullopt;
    state_ = State::FinalSent;
    return final;
}

bool NodeCommissioning::commit(const CommissioningAck& ack, std::uint64_t now) {
    if ((state_ != State::FinalSent && state_ != State::Committed) || now > deadline_ms_)
        return false;
    const auto transcript = transcript_bytes(offer_, proof_);
    Key32 expected{};
    if (!crypto_.hmac_sha256(installation_key_,
                             confirmation_bytes(transcript, proof_, hub_proof_,
                                                "GS-P2-COM-HUB-ACK-v1"), expected) ||
        !matches(crypto_, expected, ack.confirmation)) return false;
    P256PublicKey own_public{};
    if (!crypto_.identity_public_key(device_key_reference_, own_public)) return false;
    binding_ = CommissioningBinding{device_id_, offer_.hub_id, offer_.home_id,
                                    offer_.logical_id, offer_.room, offer_.function,
                                    own_public, offer_.hub_public_key,
                                    installation_key_};
    std::fill(installer_code_.begin(), installer_code_.end(), 0);
    state_ = State::Committed;
    return true;
}

}  // namespace gs::security
